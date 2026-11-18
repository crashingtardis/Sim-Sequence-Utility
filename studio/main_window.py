"""
main_window.py — Top-level QMainWindow for Comau Sim-Sequence Studio.

Layout:
  ┌────────────────────────────────────────────────────────────┐
  │  MenuBar + ToolBar                                         │
  ├──────────────┬─────────────────────────────────────────────┤
  │  Left Panel  │  Right: Gantt canvas (tab: Gantt / Schedule)│
  │  (tabs):     │                                             │
  │  Settings    │                                             │
  │  Resources   │                                             │
  │  Tasks       │                                             │
  ├──────────────┴─────────────────────────────────────────────┤
  │  KPI bar                                                   │
  ├────────────────────────────────────────────────────────────┤
  │  Status bar                                                │
  └────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QObject
from PyQt6.QtGui import (QAction, QIcon, QPixmap, QKeySequence, QColor, QFont)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QTabWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox,
    QToolBar, QStatusBar, QSizePolicy, QFrame, QScrollArea,
)

from sim_sequence.models import SequenceModel, GlobalSettings, Resource, Task
from sim_sequence.cseq_io import save_cseq, load_cseq
from sim_sequence.scheduler import schedule
from sim_sequence.excel_loader import load_excel
from sim_sequence.reporter import generate_report as write_report

from .theme import DARK_STYLESHEET, COMAU_RED, EXEC_NAVY, SLATE, WHITE, SILVER
from .gantt_canvas import GanttView
from .task_panel import ResourcePanel, TaskPanel
from .settings_panel import SettingsPanel
from .kpi_bar import KpiBar

ASSETS_DIR = Path(__file__).parent.parent / "resources"
LOGO_PATH = ASSETS_DIR / "Logo-COMAU.png"


# ---------------------------------------------------------------------------
# Background worker for scheduling + reporting
# ---------------------------------------------------------------------------
class SchedulerWorker(QObject):
    finished = pyqtSignal(object)   # SequenceModel
    error    = pyqtSignal(str)

    def __init__(self, model: SequenceModel, export_excel: bool = False):
        super().__init__()
        self._model = model
        self._export = export_excel

    def run(self):
        try:
            scheduled = schedule(self._model)
            if self._export:
                write_report(scheduled)
            self.finished.emit(scheduled)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Header widget with logo + title
# ---------------------------------------------------------------------------
class HeaderBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setStyleSheet(f"background-color: {EXEC_NAVY};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)

        # Logo
        if LOGO_PATH.exists():
            logo_lbl = QLabel()
            pix = QPixmap(str(LOGO_PATH)).scaledToHeight(36, Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(pix)
            layout.addWidget(logo_lbl)

        # Title
        title = QLabel("SIM-SEQUENCE STUDIO")
        title.setStyleSheet(
            "color: white; font-size: 15pt; font-weight: bold; "
            "font-family: 'Segoe UI'; letter-spacing: 2px;"
        )
        layout.addWidget(title)

        layout.addStretch()

        # Version badge
        from sim_sequence import __version__
        ver_lbl = QLabel(f"v{__version__}")
        ver_lbl.setStyleSheet("color: #607D8B; font-size: 9pt;")
        layout.addWidget(ver_lbl)


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._model: Optional[SequenceModel] = None
        self._current_path: Optional[Path] = None
        self._dirty = False
        self._worker_thread: Optional[QThread] = None

        self.setWindowTitle("Comau Sim-Sequence Studio")
        self.setMinimumSize(1100, 680)
        self.resize(1400, 800)
        self.setStyleSheet(DARK_STYLESHEET)

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._new_sequence()   # start with a blank model

    # =========================================================================
    # UI construction
    # =========================================================================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = HeaderBar()
        root.addWidget(self._header)

        # Splitter (left panel + right canvas)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        root.addWidget(splitter, stretch=1)

        # -- Left panel (tabs: Settings / Resources / Tasks) ------------------
        left = QWidget()
        left.setMinimumWidth(240)
        left.setMaximumWidth(560)
        left.setStyleSheet("background-color: #0B2341;")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        self._left_tabs = QTabWidget()
        self._left_tabs.setTabPosition(QTabWidget.TabPosition.North)

        # Settings tab
        self._settings_panel = SettingsPanel(GlobalSettings(available_time=3600, takt_time=60))
        self._settings_panel.changed.connect(self._on_model_edited)
        self._left_tabs.addTab(self._settings_panel, "⚙ Settings")

        # Resources tab
        self._resource_panel = ResourcePanel([])
        self._resource_panel.changed.connect(self._on_model_edited)
        self._left_tabs.addTab(self._resource_panel, "🔧 Resources")

        # Tasks tab
        self._task_panel = TaskPanel([])
        self._task_panel.changed.connect(self._on_model_edited)
        self._left_tabs.addTab(self._task_panel, "📋 Tasks")

        left_layout.addWidget(self._left_tabs)

        # Run button at bottom of left panel
        self._run_btn = QPushButton("▶  RUN SIMULATION")
        self._run_btn.setObjectName("run_btn")
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.clicked.connect(self._run_simulation)
        left_layout.addWidget(self._run_btn)

        splitter.addWidget(left)

        # -- Right: Gantt view ------------------------------------------------
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._gantt_view = GanttView()
        self._gantt_view.task_clicked.connect(self._on_task_clicked)
        right_layout.addWidget(self._gantt_view, stretch=1)

        # KPI bar under the Gantt
        self._kpi_bar = KpiBar()
        right_layout.addWidget(self._kpi_bar)

        splitter.addWidget(right)
        splitter.setSizes([320, 1000])

    # =========================================================================
    # Menu
    # =========================================================================
    def _build_menu(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        self._act_new    = QAction("&New Sequence",     self, shortcut="Ctrl+N"); file_menu.addAction(self._act_new)
        self._act_open   = QAction("&Open .cseq…",     self, shortcut="Ctrl+O"); file_menu.addAction(self._act_open)
        file_menu.addSeparator()
        self._act_save   = QAction("&Save",             self, shortcut="Ctrl+S"); file_menu.addAction(self._act_save)
        self._act_saveas = QAction("Save &As…",         self, shortcut="Ctrl+Shift+S"); file_menu.addAction(self._act_saveas)
        file_menu.addSeparator()
        self._act_import = QAction("Import from &Excel…", self); file_menu.addAction(self._act_import)
        self._act_export = QAction("Export to &Excel…",   self); file_menu.addAction(self._act_export)
        file_menu.addSeparator()
        self._act_quit   = QAction("&Quit",             self, shortcut="Ctrl+Q"); file_menu.addAction(self._act_quit)

        self._act_new.triggered.connect(self._new_sequence)
        self._act_open.triggered.connect(self._open_cseq)
        self._act_save.triggered.connect(self._save)
        self._act_saveas.triggered.connect(self._save_as)
        self._act_import.triggered.connect(self._import_excel)
        self._act_export.triggered.connect(self._export_excel)
        self._act_quit.triggered.connect(self.close)

        # Simulation
        sim_menu = mb.addMenu("&Simulation")
        act_run = QAction("▶ Run Simulation", self, shortcut="F5"); sim_menu.addAction(act_run)
        act_run.triggered.connect(self._run_simulation)

        # View
        view_menu = mb.addMenu("&View")
        act_zoom_in  = QAction("Zoom In",  self, shortcut="Ctrl+="); view_menu.addAction(act_zoom_in)
        act_zoom_out = QAction("Zoom Out", self, shortcut="Ctrl+-"); view_menu.addAction(act_zoom_out)
        act_zoom_rst = QAction("Reset Zoom", self, shortcut="Ctrl+0"); view_menu.addAction(act_zoom_rst)
        act_zoom_in.triggered.connect(lambda: self._gantt_view._scene.set_zoom(self._gantt_view._scene.get_zoom() * 1.3))
        act_zoom_out.triggered.connect(lambda: self._gantt_view._scene.set_zoom(self._gantt_view._scene.get_zoom() / 1.3))
        act_zoom_rst.triggered.connect(lambda: self._gantt_view._scene.set_zoom(14.0))

        # Help
        help_menu = mb.addMenu("&Help")
        act_about = QAction("About Sim-Sequence Studio", self); help_menu.addAction(act_about)
        act_about.triggered.connect(self._about)

    # =========================================================================
    # Toolbar
    # =========================================================================
    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        def _add(text, shortcut_action):
            act = tb.addAction(text)
            act.triggered.connect(shortcut_action)
            return act

        _add("🆕 New",    self._new_sequence)
        _add("📂 Open",   self._open_cseq)
        _add("💾 Save",   self._save)
        tb.addSeparator()
        _add("📥 Import Excel", self._import_excel)
        _add("📤 Export Excel", self._export_excel)
        tb.addSeparator()
        run_act = _add("▶ Run",    self._run_simulation)

    # =========================================================================
    # Status bar
    # =========================================================================
    def _build_statusbar(self):
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_lbl = QLabel("Ready")
        self._status.addWidget(self._status_lbl)

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)

    # =========================================================================
    # Model helpers
    # =========================================================================
    def _build_model_from_panels(self) -> SequenceModel:
        """Assemble a SequenceModel from the current panel state."""
        return SequenceModel(
            settings=self._settings_panel.settings(),
            resources=self._resource_panel.resources(),
            tasks=self._task_panel.tasks(),
        )

    def _load_model_into_panels(self, model: SequenceModel):
        self._settings_panel.set_settings(model.settings)
        self._resource_panel.set_resources(model.resources)
        self._task_panel.set_tasks(model.tasks)
        self._model = model
        self._kpi_bar.update_from_model(None)
        self._gantt_view.load_model(None)

    def _mark_dirty(self, dirty: bool = True):
        self._dirty = dirty
        title = "Comau Sim-Sequence Studio"
        if self._current_path:
            title += f" — {self._current_path.name}"
        if dirty:
            title += " *"
        self.setWindowTitle(title)

    # =========================================================================
    # File operations
    # =========================================================================
    def _new_sequence(self):
        if not self._confirm_discard():
            return
        from sim_sequence.loader import load_yaml
        default_model = SequenceModel(
            settings=GlobalSettings(available_time=3600, takt_time=60, time_increment=1.0,
                                    output_file="outputs/sequence_report.xlsx"),
            resources=[
                Resource("Operator_1", "#1F4E78"),
                Resource("Robot_A",    "#4CAF50"),
            ],
            tasks=[
                Task("Task_1", "Task 1", "Operator_1", 5.0),
                Task("Task_2", "Task 2", "Robot_A",    8.0, predecessors_fs=["Task_1"]),
            ],
        )
        self._current_path = None
        self._load_model_into_panels(default_model)
        self._mark_dirty(False)
        self._set_status("New sequence created")

    def _open_cseq(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Sequence File", str(Path.cwd()),
            "Comau Sequence (*.cseq);;All Files (*.*)"
        )
        if not path:
            return
        try:
            model = load_cseq(path)
            self._current_path = Path(path)
            self._load_model_into_panels(model)
            self._mark_dirty(False)
            self._set_status(f"Opened {self._current_path.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Open Error", str(exc))

    def _save(self):
        if self._current_path is None:
            return self._save_as()
        try:
            model = self._build_model_from_panels()
            save_cseq(model, self._current_path)
            self._mark_dirty(False)
            self._set_status(f"Saved {self._current_path.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def _save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Sequence As", str(Path.cwd() / "sequence.cseq"),
            "Comau Sequence (*.cseq);;All Files (*.*)"
        )
        if not path:
            return
        self._current_path = Path(path)
        self._save()

    def _import_excel(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import from Excel", str(Path.cwd()),
            "Excel Files (*.xlsx *.xlsm);;All Files (*.*)"
        )
        if not path:
            return
        try:
            model = load_excel(path)
            self._current_path = None
            self._load_model_into_panels(model)
            self._mark_dirty(True)
            self._set_status(f"Imported from {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", str(exc))

    def _export_excel(self):
        if self._model is None:
            QMessageBox.information(self, "Export", "Run the simulation first to generate a schedule.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to Excel", str(Path.cwd() / "sequence_report.xlsx"),
            "Excel Files (*.xlsx);;All Files (*.*)"
        )
        if not path:
            return
        try:
            self._model.settings.output_file = path
            write_report(self._model)
            self._set_status(f"Excel report saved to {Path(path).name}")
            QMessageBox.information(self, "Export Complete",
                                    f"Report written to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    # =========================================================================
    # Simulation
    # =========================================================================
    def _run_simulation(self):
        self._run_btn.setEnabled(False)
        self._run_btn.setText("⏳  Scheduling…")
        self._set_status("Running simulation…")

        model = self._build_model_from_panels()

        # Run in background thread
        self._worker_thread = QThread()
        self._worker = SchedulerWorker(model)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_schedule_done)
        self._worker.error.connect(self._on_schedule_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)
        self._worker_thread.start()

    def _on_schedule_done(self, model: SequenceModel):
        self._model = model
        self._gantt_view.load_model(model)
        self._kpi_bar.update_from_model(model)
        self._run_btn.setEnabled(True)
        self._run_btn.setText("▶  RUN SIMULATION")

        cycle_t = max((t.end_time for t in model.tasks if t.end_time), default=0)
        takt_t  = model.settings.takt_time
        status = "✓ BALANCED" if cycle_t <= takt_t else "⚠ OVER TAKT"
        self._set_status(f"Simulation complete — {len(model.tasks)} tasks, cycle {cycle_t:.1f}s / takt {takt_t:.1f}s — {status}")

    def _on_schedule_error(self, msg: str):
        self._run_btn.setEnabled(True)
        self._run_btn.setText("▶  RUN SIMULATION")
        QMessageBox.critical(self, "Scheduling Error", msg)
        self._set_status(f"Error: {msg}")

    # =========================================================================
    # Task click
    # =========================================================================
    def _on_task_clicked(self, task):
        if task is not None:
            self._task_panel.select_task(task.id)
            self._left_tabs.setCurrentIndex(2)   # Tasks tab
            self._set_status(
                f"Task: {task.name} | Resource: {task.resource} | "
                f"Duration: {task.duration:.1f}s | "
                f"Start: {task.start_time:.2f}s | End: {task.end_time:.2f}s"
            )

    # =========================================================================
    # Misc events
    # =========================================================================
    def _on_model_edited(self):
        self._mark_dirty(True)

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Discard

    def _about(self):
        from sim_sequence import __version__
        QMessageBox.about(
            self, "About Sim-Sequence Studio",
            f"<h2>Comau Sim-Sequence Studio</h2>"
            f"<p>Version {__version__}</p>"
            f"<p>An interactive scheduling and sequence analysis tool "
            f"for automation engineers.</p>"
            f"<p><b>File format:</b> .cseq (JSON-based, Git-friendly)</p>"
            f"<p><b>Engine:</b> NetworkX DAG scheduler (FS + SS dependencies)</p>"
        )

    def closeEvent(self, event):
        if self._dirty:
            reply = QMessageBox.question(
                self, "Quit",
                "You have unsaved changes. Quit anyway?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Discard:
                event.ignore()
                return
        event.accept()
