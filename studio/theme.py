"""
theme.py — Comau brand colours, fonts, and stylesheet constants.
"""

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
COMAU_RED       = "#C8102E"
EXEC_NAVY       = "#0B2341"
SLATE           = "#1A2E40"
SILVER          = "#B0BAC4"
WHITE           = "#FFFFFF"
LIGHT_BG        = "#F4F6F8"
PANEL_BG        = "#1E2D3D"
ACCENT_BLUE     = "#2979FF"
SUCCESS_GREEN   = "#2ECC71"
WARNING_ORANGE  = "#F39C12"
DANGER_RED      = "#E74C3C"
GRID_LINE       = "#2C3E50"
TASK_HOVER      = "#3D5A80"

# Default resource colour palette (cycled when user doesn't set colour)
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

# ---------------------------------------------------------------------------
# App-level stylesheet (dark theme)
# ---------------------------------------------------------------------------
DARK_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #0B2341;
}

QWidget {
    background-color: #0D1B2A;
    color: #E8EDF2;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
}

/* ── Menus ─────────────────────────────────────────────────────────────── */
QMenuBar {
    background-color: #0B2341;
    color: #E8EDF2;
    border-bottom: 1px solid #1A2E40;
}
QMenuBar::item:selected {
    background-color: #1A2E40;
}
QMenu {
    background-color: #122035;
    border: 1px solid #1A2E40;
}
QMenu::item:selected {
    background-color: #1F4E78;
}
QMenu::separator {
    height: 1px;
    background: #1A2E40;
}

/* ── Toolbar ────────────────────────────────────────────────────────────── */
QToolBar {
    background-color: #0B2341;
    border-bottom: 1px solid #1A2E40;
    spacing: 4px;
    padding: 4px 8px;
}
QToolButton {
    background-color: transparent;
    color: #B0BAC4;
    border-radius: 4px;
    padding: 4px 8px;
}
QToolButton:hover {
    background-color: #1A2E40;
    color: #FFFFFF;
}
QToolButton:pressed {
    background-color: #C8102E;
    color: #FFFFFF;
}

/* ── Status Bar ─────────────────────────────────────────────────────────── */
QStatusBar {
    background-color: #0B2341;
    color: #B0BAC4;
    border-top: 1px solid #1A2E40;
}

/* ── Splitter ────────────────────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #1A2E40;
    width: 2px;
    height: 2px;
}

/* ── Tab Widget ─────────────────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #1A2E40;
    background-color: #0D1B2A;
}
QTabBar::tab {
    background-color: #122035;
    color: #B0BAC4;
    padding: 6px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #0D1B2A;
    color: #FFFFFF;
    border-bottom: 2px solid #C8102E;
}
QTabBar::tab:hover {
    background-color: #1A2E40;
}

/* ── Tables / Trees ─────────────────────────────────────────────────────── */
QTableWidget, QTreeWidget, QListWidget {
    background-color: #0D1B2A;
    alternate-background-color: #122035;
    color: #E8EDF2;
    gridline-color: #1A2E40;
    border: 1px solid #1A2E40;
    selection-background-color: #1F4E78;
}
QHeaderView::section {
    background-color: #0B2341;
    color: #B0BAC4;
    padding: 6px;
    border: none;
    border-right: 1px solid #1A2E40;
    border-bottom: 1px solid #1A2E40;
    font-weight: bold;
    font-size: 9pt;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Input Controls ─────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #122035;
    color: #E8EDF2;
    border: 1px solid #1A2E40;
    border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #2979FF;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #122035;
    selection-background-color: #1F4E78;
    border: 1px solid #1A2E40;
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
QPushButton {
    background-color: #1A2E40;
    color: #E8EDF2;
    border: 1px solid #2C3E50;
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #1F4E78;
    border-color: #2979FF;
}
QPushButton:pressed {
    background-color: #0B2341;
}
QPushButton#run_btn {
    background-color: #C8102E;
    color: white;
    font-size: 11pt;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 10px 24px;
}
QPushButton#run_btn:hover {
    background-color: #E8142F;
}
QPushButton#run_btn:pressed {
    background-color: #A00C23;
}
QPushButton#export_btn {
    background-color: #1F4E78;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: 600;
}
QPushButton#export_btn:hover {
    background-color: #2563A3;
}

/* ── Scroll Bars ─────────────────────────────────────────────────────────── */
QScrollBar:horizontal, QScrollBar:vertical {
    background-color: #0D1B2A;
    border: none;
}
QScrollBar:horizontal { height: 8px; }
QScrollBar:vertical   { width:  8px; }
QScrollBar::handle:horizontal, QScrollBar::handle:vertical {
    background-color: #1A2E40;
    border-radius: 4px;
}
QScrollBar::handle:hover {
    background-color: #2979FF;
}
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }

/* ── Group Box ───────────────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #1A2E40;
    border-radius: 6px;
    margin-top: 12px;
    padding: 8px;
    color: #B0BAC4;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #B0BAC4;
}

/* ── Tooltip ──────────────────────────────────────────────────────────────── */
QToolTip {
    background-color: #122035;
    color: #E8EDF2;
    border: 1px solid #1A2E40;
    padding: 4px 8px;
    border-radius: 3px;
}

/* ── Progress / Slider ───────────────────────────────────────────────────── */
QSlider::groove:horizontal {
    height: 4px;
    background: #1A2E40;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #2979FF;
    width: 14px; height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
"""
