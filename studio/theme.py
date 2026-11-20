"""
theme.py — Comau brand colours and the dark / light themes.

A :class:`Theme` is a flat palette.  ``build_stylesheet(theme)`` turns it into
the application stylesheet, and the Gantt canvas reads its colours straight
from the same object, so switching theme is a single call chain with no
per-widget inline colours to chase down.

Widgets are styled by ``objectName`` / dynamic property in the stylesheet
(e.g. ``QLabel#KpiValue[tone="bad"]``) instead of inline ``setStyleSheet``.
"""

from __future__ import annotations

from dataclasses import dataclass
from string import Template

from PyQt6.QtGui import QColor

# ---------------------------------------------------------------------------
# Brand constants (theme independent)
# ---------------------------------------------------------------------------
COMAU_RED = "#C8102E"
EXEC_NAVY = "#0B2341"
WHITE = "#FFFFFF"
ACCENT_BLUE = "#2979FF"

# Default resource colour palette (cycled when a resource has no colour)
RESOURCE_PALETTE = [
    "#1F4E78",   # deep blue
    "#4CAF50",   # green
    "#FF9800",   # orange
    "#9C27B0",   # purple
    "#00BCD4",   # cyan
    "#F44336",   # red
    "#795548",   # brown
    "#607D8B",   # blue-grey
]


@dataclass(frozen=True)
class Theme:
    name: str
    is_dark: bool

    # surfaces
    window_bg: str
    panel_bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    toolbar_bg: str
    selection_bg: str
    selection_fg: str
    button_bg: str
    button_hover: str

    # brand header (navy in both themes)
    header_bg: str

    # status colours
    success: str
    danger: str
    warning: str
    accent: str

    # gantt canvas
    gantt_bg: str
    gantt_row_alt: str
    gantt_header_bg: str
    gantt_label_bg: str
    gantt_grid: str
    gantt_grid_strong: str
    gantt_text: str
    gantt_text_muted: str

    # dependency links
    arrow_fs: str
    arrow_ss: str
    link_color: str        # drag preview / selection / FS handle
    link_ok: str
    link_bad: str


DARK = Theme(
    name="dark", is_dark=True,
    window_bg="#0B2341", panel_bg="#0D1B2A", surface="#122035", surface_alt="#0F1F30",
    border="#1F3348", text="#E8EDF2", text_muted="#8FA1B3", toolbar_bg="#0B2341",
    selection_bg="#1F4E78", selection_fg="#FFFFFF",
    button_bg="#1A2E40", button_hover="#1F4E78",
    header_bg=EXEC_NAVY,
    success="#2ECC71", danger="#E74C3C", warning="#F39C12", accent=ACCENT_BLUE,
    gantt_bg="#0D1B2A", gantt_row_alt="#0F1F30", gantt_header_bg="#0B2341",
    gantt_label_bg="#0B2341", gantt_grid="#152838", gantt_grid_strong="#1E3A54",
    gantt_text="#E8EDF2", gantt_text_muted="#8FA1B3",
    arrow_fs="#B0BAC4", arrow_ss="#F39C12",
    link_color="#4C8DFF", link_ok="#2ECC71", link_bad="#E74C3C",
)

LIGHT = Theme(
    name="light", is_dark=False,
    window_bg="#EEF1F5", panel_bg="#FFFFFF", surface="#FFFFFF", surface_alt="#F3F6F9",
    border="#C9D2DC", text="#1B2733", text_muted="#5B6B7B", toolbar_bg="#E3E8EE",
    selection_bg="#CFE0FF", selection_fg="#0B2341",
    button_bg="#E3E8EE", button_hover="#D2DCE8",
    header_bg=EXEC_NAVY,
    success="#1E9E57", danger="#C62828", warning="#C77700", accent=ACCENT_BLUE,
    gantt_bg="#FFFFFF", gantt_row_alt="#F4F7FA", gantt_header_bg="#E3E8EE",
    gantt_label_bg="#E9EDF2", gantt_grid="#E1E7ED", gantt_grid_strong="#C3CED9",
    gantt_text="#1B2733", gantt_text_muted="#5B6B7B",
    arrow_fs="#5B6B7B", arrow_ss="#C77700",
    link_color="#2A6FE8", link_ok="#1E9E57", link_bad="#C62828",
)

THEMES = {"dark": DARK, "light": LIGHT}


def contrast_color(color: QColor) -> QColor:
    """Dark or white text, whichever is more legible on *color*."""
    lum = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    return QColor("#101820") if lum > 150 else QColor("#FFFFFF")


def set_prop(widget, name: str, value: str) -> None:
    """Set a dynamic property and re-polish so the stylesheet re-evaluates."""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------
_QSS = Template("""
QWidget { color: $text; font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt; }
QMainWindow, QDialog, QMessageBox { background-color: $window_bg; }
QLabel { background: transparent; }

/* Menus / toolbar / status bar */
QMenuBar { background-color: $toolbar_bg; border-bottom: 1px solid $border; }
QMenuBar::item { padding: 4px 10px; background: transparent; }
QMenuBar::item:selected { background-color: $button_hover; }
QMenu { background-color: $surface; border: 1px solid $border; padding: 4px; }
QMenu::item { padding: 5px 22px; border-radius: 3px; }
QMenu::item:selected { background-color: $selection_bg; color: $selection_fg; }
QMenu::separator { height: 1px; background: $border; margin: 4px 6px; }
QToolBar { background-color: $toolbar_bg; border: none; border-bottom: 1px solid $border; spacing: 4px; padding: 3px 6px; }
QToolButton { background: transparent; border-radius: 4px; padding: 4px 8px; }
QToolButton:hover { background-color: $button_hover; }
QToolButton:checked { background-color: $selection_bg; color: $selection_fg; }
QStatusBar { background-color: $toolbar_bg; border-top: 1px solid $border; color: $text_muted; }
QToolTip { background-color: $surface; color: $text; border: 1px solid $border; padding: 4px 8px; }

/* Layout furniture */
QSplitter::handle { background-color: $border; }
QSplitter::handle:horizontal { width: 5px; }
QSplitter::handle:hover { background-color: $accent; }
QFrame#LeftPanel { background-color: $window_bg; }
QTabWidget::pane { border: 1px solid $border; background-color: $panel_bg; top: -1px; }
QTabBar::tab { background-color: $surface; color: $text_muted; padding: 6px 12px; border: 1px solid $border;
               border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background-color: $panel_bg; color: $text; border-bottom: 2px solid $accent; }
QTabBar::tab:hover:!selected { background-color: $button_hover; }

/* Header, KPI bar, Gantt toolbar */
QFrame#HeaderBar { background-color: $header_bg; }
QLabel#HeaderTitle { color: #FFFFFF; font-size: 15pt; font-weight: bold; }
QLabel#HeaderVersion { color: #8FA1B3; font-size: 9pt; }
QFrame#KpiBar, QFrame#GanttToolbar { background-color: $toolbar_bg; }
QFrame#KpiBar { border-top: 1px solid $border; }
QFrame#GanttToolbar { border-bottom: 1px solid $border; }
QFrame#KpiCard { background-color: $surface; border: 1px solid $border; border-radius: 4px; }
QLabel#KpiLabel { color: $text_muted; font-size: 8pt; font-weight: bold; }
QLabel#KpiValue { font-weight: bold; }
QLabel#KpiValue[tone="good"] { color: $success; }
QLabel#KpiValue[tone="bad"] { color: $danger; }
QLabel#StatusBadge { font-weight: bold; border-radius: 4px; padding: 4px 10px;
                     color: $text_muted; background-color: $surface; border: 1px solid $border; }
QLabel#StatusBadge[state="ok"] { color: $success; border: 1px solid $success; }
QLabel#StatusBadge[state="over"] { color: $danger; border: 1px solid $danger; }
QLabel#SectionLabel { color: $text_muted; font-size: 9pt; font-weight: bold; padding: 4px 0 2px 0; }
QLabel#LegendLabel { color: $text_muted; font-size: 8pt; }

/* Tables */
QTableView { background-color: $surface; alternate-background-color: $surface_alt; gridline-color: $border;
             border: 1px solid $border; selection-background-color: $selection_bg; selection-color: $selection_fg; }
QTableView::item { padding: 0 4px; }
QHeaderView::section { background-color: $toolbar_bg; color: $text_muted; padding: 5px 6px; border: none;
                       border-right: 1px solid $border; border-bottom: 1px solid $border; font-weight: bold; font-size: 9pt; }
QTableCornerButton::section { background-color: $toolbar_bg; border: none; }

/* Inputs */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: $surface; border: 1px solid $border;
             border-radius: 4px; padding: 3px 6px; selection-background-color: $selection_bg; selection-color: $selection_fg; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid $accent; }
QTableView QComboBox, QTableView QLineEdit { padding: 0 4px; border-radius: 0; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background-color: $surface; border: 1px solid $border;
             selection-background-color: $selection_bg; selection-color: $selection_fg; outline: 0; }
QCheckBox { spacing: 6px; }
QGroupBox { border: 1px solid $border; border-radius: 6px; margin-top: 12px; padding: 10px 8px 8px 8px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px; color: $text_muted; }

/* Buttons */
QPushButton { background-color: $button_bg; border: 1px solid $border; border-radius: 4px; padding: 5px 12px; }
QPushButton:hover { background-color: $button_hover; border-color: $accent; }
QPushButton:pressed { background-color: $selection_bg; }
QPushButton:disabled { color: $text_muted; }
QPushButton#run_btn { background-color: $brand_red; color: #FFFFFF; font-size: 11pt; font-weight: bold;
                      border: none; border-radius: 6px; padding: 9px 20px; }
QPushButton#run_btn:hover { background-color: #E8142F; }
QPushButton#run_btn:pressed { background-color: #A00C23; }
QPushButton#addBtn { background-color: #1F4E78; color: #FFFFFF; border: none; }
QPushButton#addBtn:hover { background-color: #2563A3; }
QPushButton#removeBtn { background-color: #8E2430; color: #FFFFFF; border: none; }
QPushButton#removeBtn:hover { background-color: #B02A3A; }
QPushButton#toolBtn { padding: 3px 9px; }

/* Scroll bars */
QScrollBar:horizontal { height: 10px; background: transparent; margin: 0; }
QScrollBar:vertical { width: 10px; background: transparent; margin: 0; }
QScrollBar::handle:horizontal, QScrollBar::handle:vertical { background-color: $border; border-radius: 5px; min-width: 24px; min-height: 24px; }
QScrollBar::handle:hover { background-color: $accent; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
""")


def build_stylesheet(theme: Theme) -> str:
    values = {k: getattr(theme, k) for k in theme.__dataclass_fields__}
    values["brand_red"] = COMAU_RED
    return _QSS.safe_substitute(values)
