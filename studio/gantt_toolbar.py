"""
gantt_toolbar.py — Slim strip above the Gantt: zoom / fit buttons plus a
legend that explains the link handles and arrow styles.  Wraps when narrow.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton

from .flow_layout import FlowLayout
from .theme import Theme


class GanttToolbar(QFrame):
    zoom_out = pyqtSignal()
    zoom_in = pyqtSignal()
    fit = pyqtSignal()
    reset = pyqtSignal()

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.setObjectName("GanttToolbar")
        flow = FlowLayout(self, margin=6, h_spacing=6, v_spacing=4)

        def btn(text, tip, signal):
            b = QPushButton(text)
            b.setObjectName("toolBtn")
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(signal)
            flow.addWidget(b)

        btn("\u2212", "Zoom out (Ctrl+\u2212)", self.zoom_out)
        btn("+", "Zoom in (Ctrl+=)", self.zoom_in)
        btn("Fit", "Fit the whole sequence to the window (Ctrl+9)", self.fit)
        btn("100%", "Reset zoom (Ctrl+0)", self.reset)

        self._legend_link = QLabel()
        self._legend_fs = QLabel()
        self._legend_remove = QLabel()
        for lbl in (self._legend_link, self._legend_fs, self._legend_remove):
            lbl.setObjectName("LegendLabel")
            lbl.setTextFormat(Qt.TextFormat.RichText)
            flow.addWidget(lbl)
        self.set_theme(theme)

    def set_theme(self, theme: Theme) -> None:
        fs, ss, handle = theme.arrow_fs, theme.arrow_ss, theme.link_color
        self._legend_link.setText(
            f"<span style='color:{handle}'>\u25cf</span> right handle \u2192 FS link (finish\u2192start) &nbsp; "
            f"<span style='color:{ss}'>\u25cf</span> left handle \u2192 SS link (start\u2192start)")
        self._legend_fs.setText(
            f"<span style='color:{fs}'>\u2501\u2501</span> FS &nbsp; "
            f"<span style='color:{ss}'>\u254c\u254c</span> SS")
        self._legend_remove.setText("Click a link, then press Delete (or click \u2715) to remove it")
