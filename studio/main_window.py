"""
main_window.py — Top-level window for Comau Sim-Sequence Studio.

  ┌──────────────────────────────────────────────────────────────┐
  │ Header (logo / title / version)                                │
  │ Menu + toolbar                                                 │
  ├───────────────┬──────────────────────────────────────────────┤
  │ Left pane     │ Gantt toolbar (zoom / fit / legend)            │
  │ (resizable):  │ Gantt canvas                                   │
  │  Settings     │ KPI bar (wraps when narrow)                    │
  │  Resources    │                                                │
  │  Tasks        │                                                │
  │ [Run]         │                                                │
  ├───────────────┴──────────────────────────────────────────────┤
  │ Status bar                                                     │
  └──────────────────────────────────────────────────────────────┘

All edits go through :class:`ProjectStore`; the panels, dropdowns and Gantt
are views over it.  Scheduling is fast, so it runs synchronously (and
automatically, debounced, after every edit unless switched off).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QByteArray, QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QPixmap
from PyQt6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout,
                             QLabel, QMainWindow, QMessageBox, QPushButton,
                             QSplitter, QTabWidget, QToolBar, QVBoxLayout,
                             QWidget)

from sim_sequence import __version__
from sim_sequence.cseq_io import load_cseq, save_cseq
from sim_sequence.excel_loader import load_excel
from sim_sequence.models import GlobalSettings, Resource, SequenceModel, Task
from sim_sequence.reporter import generate_report
from sim_sequence.sample_data import get_sample_sequence
from sim_sequence.scheduler import schedule

from .gantt_canvas import GanttView
from .gantt_toolbar import GanttToolbar
from .kpi_bar import KpiBar
from .project_store import ProjectStore
from .settings_panel import SettingsPanel
from .task_panel import ResourcePanel, TaskPanel
from .theme import DARK, LIGHT, THEMES, Theme, build_stylesheet

APP_TITLE = "Comau Sim-Sequence Studio"
LOGO_PATH = Path(__file__).parent.parent / "resources" / "Logo-COMAU.png"
SEQUENCE_FILTER = "Comau Sequence (*.cseq);;All Files (*.*)"


class HeaderBar(QFrame):
    """Brand strip: logo, title, version."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.setFixedHeight(52)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(12)

        if LOGO_PATH.exists():
            logo = QLabel()
            logo.setPixmap(QPixmap(str(LOGO_PATH)).scaledToHeight(
                34, Qt.TransformationMode.SmoothTransformation))
            lay.addWidget(logo)

        title = QLabel("SIM-SEQUENCE STUDIO")
        title.setObjectName("HeaderTitle")
        lay.addWidget(title)
        lay.addStretch()
        version = QLabel(f"v{__version__}")
        version.setObjectName("HeaderVersion")
        lay.addWidget(version)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._store = ProjectStore(self)
        self._current_path: Optional[Path] = None
        self._dirty = False
        self._scheduled: Optional[SequenceModel] = None
        self._prefs = QSettings("Comau", "SimSequenceStudio")
        self._theme: Theme = THEMES.get(str(self._prefs.value("theme", "dark")), DARK)

        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.setInterval(300)
        self._auto_timer.timeout.connect(lambda: self._run_now(interactive=False))

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(900, 580)
        self.resize(1400, 820)

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self.statusBar().showMessage("Ready")

        self._store.edited.connect(self._on_edited)
        self._apply_theme(self._theme)
        self._restore_layout()
        self._new_sequence()

    # =========================================================================
    # UI construction
    # =========================================================================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(HeaderBar())

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(5)
        root.addWidget(self._splitter, stretch=1)

        # ---- left pane: tabs + run button (freely resizable) --------------------
        left = QFrame()
        left.setObjectName("LeftPanel")
        left.setMinimumWidth(280)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(8, 8, 8, 8)
        left_lay.setSpacing(8)

        self._tabs = QTabWidget()
        self._settings_panel = SettingsPanel(self._store.settings)
        self._resource_panel = ResourcePanel(self._store)
        self._task_panel = TaskPanel(self._store)
        self._tabs.addTab(self._settings_panel, "\u2699 Settings")
        self._tabs.addTab(self._resource_panel, "\U0001F527 Resources")
        self._tabs.addTab(self._task_panel, "\U0001F4CB Tasks")
        left_lay.addWidget(self._tabs, stretch=1)

        self._run_btn = QPushButton("\u25b6  RUN SIMULATION")
        self._run_btn.setObjectName("run_btn")
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.clicked.connect(lambda: self._run_now(interactive=True))
        left_lay.addWidget(self._run_btn)
        self._splitter.addWidget(left)

        # ---- right pane: gantt toolbar, gantt, KPI bar ---------------------------
        right = QWidget()
        right.setMinimumWidth(300)
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        self._gantt_toolbar = GanttToolbar(self._theme)
        right_lay.addWidget(self._gantt_toolbar)
        self._gantt = GanttView(self._theme)
        right_lay.addWidget(self._gantt, stretch=1)
        self._kpi_bar = KpiBar()
        right_lay.addWidget(self._kpi_bar)
        self._splitter.addWidget(right)

        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([440, 960])

        # ---- wiring ------------------------------------------------------------------
        self._settings_panel.changed.connect(self._on_edited)
        for panel in (self._resource_panel, self._task_panel):
            panel.message.connect(self._flash)
        self._task_panel.task_selected.connect(self._gantt.select_task)

        self._gantt.set_link_validator(self._store.check_link)
        self._gantt.task_clicked.connect(self._on_task_clicked)
        self._gantt.task_resized.connect(self._on_task_resized)
        self._gantt.dependency_added.connect(self._on_dependency_added)
        self._gantt.dependency_removed.connect(self._on_dependency_removed)
        self._gantt.link_hint.connect(self._on_link_hint)

        self._gantt_toolbar.zoom_in.connect(lambda: self._gantt.zoom_by(1.3))
        self._gantt_toolbar.zoom_out.connect(lambda: self._gantt.zoom_by(1 / 1.3))
        self._gantt_toolbar.fit.connect(self._gantt.fit_to_window)
        self._gantt_toolbar.reset.connect(self._gantt.reset_zoom)

    def _action(self, menu, text, slot, shortcut=None, checkable=False,
                checked=False, tip=None) -> QAction:
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        if tip:
            act.setStatusTip(tip)
        if checkable:
            act.setCheckable(True)
            act.setChecked(checked)
            act.toggled.connect(slot)
        else:
            act.triggered.connect(lambda _checked=False: slot())
        menu.addAction(act)
        return act

    def _build_menu(self):
        mb = self.menuBar()

        m = mb.addMenu("&File")
        self._act_new = self._action(m, "&New Sequence", self._new_sequence, "Ctrl+N")
        self._act_open = self._action(m, "&Open .cseq\u2026", self._open_cseq, "Ctrl+O")
        m.addSeparator()
        self._act_save = self._action(m, "&Save", self._save, "Ctrl+S")
        self._act_saveas = self._action(m, "Save &As\u2026", self._save_as, "Ctrl+Shift+S")
        m.addSeparator()
        self._act_import = self._action(m, "Import from &Excel\u2026", self._import_excel)
        self._act_export = self._action(m, "Export to E&xcel\u2026", self._export_excel)
        m.addSeparator()
        self._action(m, "&Quit", self.close, "Ctrl+Q")

        m = mb.addMenu("&Simulation")
        self._act_run = self._action(m, "\u25b6 Run Simulation", lambda: self._run_now(True), "F5")
        self._act_auto = self._action(
            m, "Auto-run after edits", lambda on: self._on_auto_toggled(on),
            checkable=True, checked=True,
            tip="Re-schedule automatically a moment after every change")

        m = mb.addMenu("&View")
        self._action(m, "Zoom In", lambda: self._gantt.zoom_by(1.3), "Ctrl+=")
        self._action(m, "Zoom Out", lambda: self._gantt.zoom_by(1 / 1.3), "Ctrl+-")
        self._action(m, "Fit to Window", self._gantt.fit_to_window, "Ctrl+9")
        self._action(m, "Reset Zoom", self._gantt.reset_zoom, "Ctrl+0")
        m.addSeparator()
        self._act_dark = self._action(
            m, "\U0001F319 Dark mode", self._toggle_theme, "Ctrl+Shift+D",
            checkable=True, checked=self._theme.is_dark,
            tip="Switch between the dark and light theme")

        m = mb.addMenu("&Help")
        self._action(m, "Load &Sample Sequence (Body-Shop Cell)", self._load_sample_sequence,
                     tip="Load the built-in sample (22 tasks, 6 resources)")
        m.addSeparator()
        self._action(m, "About Sim-Sequence Studio", self._about)

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        for act in (self._act_new, self._act_open, self._act_save):
            tb.addAction(act)
        tb.addSeparator()
        tb.addAction(self._act_import)
        tb.addAction(self._act_export)
        tb.addSeparator()
        tb.addAction(self._act_run)
        tb.addSeparator()
        tb.addAction(self._act_dark)

    # =========================================================================
    # Theme / layout persistence
    # =========================================================================
    def _apply_theme(self, theme: Theme):
        self._theme = theme
        QApplication.instance().setStyleSheet(build_stylesheet(theme))
        self._gantt.set_theme(theme)
        self._gantt_toolbar.set_theme(theme)
        self._act_dark.blockSignals(True)
        self._act_dark.setChecked(theme.is_dark)
        self._act_dark.blockSignals(False)
        self._prefs.setValue("theme", theme.name)

    def _toggle_theme(self, dark: bool):
        self._apply_theme(DARK if dark else LIGHT)

    def _restore_layout(self):
        geometry = self._prefs.value("geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        state = self._prefs.value("splitter")
        if isinstance(state, QByteArray):
            self._splitter.restoreState(state)

    # =========================================================================
    # Helpers
    # =========================================================================
    def _flash(self, msg: str, ms: int = 6000):
        self.statusBar().showMessage(msg, ms)

    def _mark_dirty(self, dirty: bool = True):
        self._dirty = dirty
        title = APP_TITLE
        if self._current_path:
            title += f" \u2014 {self._current_path.name}"
        self.setWindowTitle(title + (" *" if dirty else ""))

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self, "Unsaved Changes", "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        return reply == QMessageBox.StandardButton.Discard

    def _load_model(self, model: SequenceModel, path: Optional[Path] = None, dirty: bool = False):
        self._current_path = path
        self._store.load(model)
        self._settings_panel.set_settings(self._store.settings)
        self._run_now(interactive=False)
        self._gantt.fit_to_window()
        self._mark_dirty(dirty)

    # =========================================================================
    # File operations
    # =========================================================================
    def _new_sequence(self):
        if not self._confirm_discard():
            return
        model = SequenceModel(
            settings=GlobalSettings(available_time=3600, takt_time=60, time_increment=1.0,
                                    output_file="outputs/sequence_report.xlsx"),
            resources=[Resource("Operator_1", "#1F4E78"), Resource("Robot_A", "#4CAF50")],
            tasks=[Task("Task_1", "Task 1", "Operator_1", 5.0),
                   Task("Task_2", "Task 2", "Robot_A", 8.0, predecessors_fs=["Task_1"])],
        )
        self._load_model(model)
        self._flash("New sequence created")

    def open_path(self, path) -> bool:
        """Open a .cseq / .xlsx / .xlsm / .yaml file (also used for CLI / file association)."""
        path = Path(path)
        suffix = path.suffix.lower()
        try:
            if suffix == ".cseq":
                model, keep = load_cseq(path), path
            elif suffix in (".xlsx", ".xlsm"):
                model, keep = load_excel(path), None
            elif suffix in (".yaml", ".yml"):
                from sim_sequence.loader import load_yaml
                model, keep = load_yaml(path), None
            else:
                raise ValueError(f"Unsupported file type '{suffix}'.")
        except Exception as exc:
            QMessageBox.critical(self, "Open Error", str(exc))
            return False
        self._load_model(model, keep, dirty=keep is None)
        self._flash(f"Opened {path.name}")
        return True

    def _open_cseq(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open Sequence File", str(Path.cwd()), SEQUENCE_FILTER)
        if path:
            self.open_path(path)

    def _save(self):
        if self._current_path is None:
            return self._save_as()
        try:
            save_cseq(self._store.to_model(), self._current_path)
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))
            return
        self._mark_dirty(False)
        self._flash(f"Saved {self._current_path.name}")

    def _save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Sequence As", str(Path.cwd() / "sequence.cseq"), SEQUENCE_FILTER)
        if path:
            self._current_path = Path(path)
            self._save()

    def _import_excel(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import from Excel", str(Path.cwd()), "Excel Files (*.xlsx *.xlsm);;All Files (*.*)")
        if path:
            self.open_path(path)

    def _export_excel(self):
        if not self._run_now(interactive=True):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to Excel", str(Path.cwd() / "sequence_report.xlsx"),
            "Excel Files (*.xlsx);;All Files (*.*)")
        if not path:
            return
        try:
            generate_report(self._scheduled, output_path=path)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
            return
        self._flash(f"Excel report saved to {Path(path).name}")
        QMessageBox.information(self, "Export Complete", f"Report written to:\n{path}")

    def _load_sample_sequence(self):
        if not self._confirm_discard():
            return
        model = get_sample_sequence()
        self._load_model(model)
        self._flash(f"Loaded sample sequence ({len(model.tasks)} tasks, {len(model.resources)} resources)")

    # =========================================================================
    # Simulation
    # =========================================================================
    def _on_edited(self):
        self._mark_dirty(True)
        if self._act_auto.isChecked():
            self._auto_timer.start()

    def _on_auto_toggled(self, on: bool):
        if on:
            self._auto_timer.start()
        else:
            self._auto_timer.stop()

    def _run_now(self, interactive: bool = False) -> bool:
        """Schedule immediately.  Returns True on success."""
        self._auto_timer.stop()
        model = self._store.to_model()
        try:
            schedule(model)
        except Exception as exc:
            self._scheduled = None
            self._gantt.load_model(None)
            self._kpi_bar.update_from_model(None)
            if interactive:
                QMessageBox.critical(self, "Scheduling Error", str(exc))
            self.statusBar().showMessage(f"Cannot schedule: {exc}")
            return False

        self._scheduled = model
        self._gantt.load_model(model)
        self._kpi_bar.update_from_model(model)
        cycle = max((t.end_time for t in model.tasks if t.end_time is not None), default=0.0)
        takt = model.settings.takt_time
        verdict = "\u2713 BALANCED" if cycle <= takt else "\u26a0 OVER TAKT"
        self.statusBar().showMessage(
            f"{len(model.tasks)} tasks \u2022 cycle {cycle:.1f}s / takt {takt:.1f}s \u2022 {verdict}")
        return True

    # =========================================================================
    # Gantt interaction
    # =========================================================================
    def _on_task_clicked(self, task):
        if task is None:
            return
        self._task_panel.select_task(task.id)
        self._tabs.setCurrentWidget(self._task_panel)

    def _on_task_resized(self, task_id: str, duration: float):
        self._store.set_duration_by_id(task_id, duration)
        self._run_now(interactive=False)
        self._flash(f"Set duration of {task_id} to {duration:g}s")

    def _on_dependency_added(self, src: str, dst: str, dep_type: str):
        ok, msg = self._store.add_dependency(src, dst, dep_type)
        if ok:
            self._run_now(interactive=False)
        self._flash(msg)

    def _on_dependency_removed(self, src: str, dst: str, dep_type: str):
        if self._store.remove_dependency(src, dst, dep_type):
            self._run_now(interactive=False)
            self._flash(f"Removed {dep_type} link {src} \u2192 {dst}")

    def _on_link_hint(self, msg: str):
        if msg:
            self.statusBar().showMessage(msg)
        else:
            self.statusBar().clearMessage()

    # =========================================================================
    # Misc
    # =========================================================================
    def _about(self):
        QMessageBox.about(
            self, "About Sim-Sequence Studio",
            f"<h2>{APP_TITLE}</h2><p>Version {__version__}</p>"
            "<p>An interactive scheduling and sequence analysis tool for automation engineers.</p>"
            "<p><b>File format:</b> .cseq (JSON, Git-friendly)</p>"
            "<p><b>Engine:</b> NetworkX DAG scheduler (FS + SS dependencies)</p>")

    def closeEvent(self, event):
        if self._dirty:
            reply = QMessageBox.question(
                self, "Quit", "You have unsaved changes. Quit anyway?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply != QMessageBox.StandardButton.Discard:
                event.ignore()
                return
        self._prefs.setValue("geometry", self.saveGeometry())
        self._prefs.setValue("splitter", self._splitter.saveState())
        event.accept()
