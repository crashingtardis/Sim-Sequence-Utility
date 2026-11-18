"""
gantt_canvas.py — Interactive Gantt chart canvas using QGraphicsScene/View.

Features:
  - Horizontal timeline, resources on Y-axis
  - Task bars coloured by resource
  - Vertical takt-time marker line (Comau Red)
  - Hover tooltips with task details
  - Zoom (Ctrl+Scroll) and pan (middle-mouse / scroll)
  - Click-to-select task (emits signal to update sidebar)
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from PyQt6.QtCore import (Qt, QRectF, QPointF, pyqtSignal, QObject)
from PyQt6.QtGui import (
    QColor, QBrush, QPen, QPainter, QFont, QFontMetrics, QCursor,
)
from PyQt6.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsItem,
    QToolTip, QGraphicsSimpleTextItem,
)

from sim_sequence.models import SequenceModel, Task, Resource
from .theme import COMAU_RED, EXEC_NAVY, SLATE, WHITE, SILVER, GRID_LINE, RESOURCE_PALETTE

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
ROW_HEIGHT   = 44       # px per resource row
ROW_PADDING  = 6        # px top/bottom padding inside row
LABEL_WIDTH  = 160      # px for resource-name column
HEADER_H     = 40       # px for time-axis header
TICK_MAJOR   = 5        # seconds between major tick labels
MIN_PX_PER_S = 4.0      # minimum pixels-per-second (fully zoomed out)
MAX_PX_PER_S = 80.0     # maximum pixels-per-second (fully zoomed in)
DEFAULT_PX_S = 14.0     # default scale

TAKT_COLOR   = QColor(COMAU_RED)
GRID_COLOR   = QColor(GRID_LINE)
BG_COLOR     = QColor("#0D1B2A")
HDR_COLOR    = QColor(EXEC_NAVY)
ROW_ALT      = QColor("#0F1F30")
ROW_EVEN     = QColor("#0D1B2A")
LABEL_FG     = QColor(SILVER)
TASK_FG      = QColor(WHITE)
SELECT_COLOR = QColor("#2979FF")


# ---------------------------------------------------------------------------
# Task bar graphics item
# ---------------------------------------------------------------------------
class TaskBarItem(QGraphicsRectItem):
    """A single coloured task bar on the Gantt canvas."""

    def __init__(
        self,
        task: Task,
        x: float,
        y: float,
        w: float,
        h: float,
        color: QColor,
        parent=None,
    ):
        super().__init__(x, y, w, h, parent)
        self.task = task
        self._color = color
        self._selected = False
        self.setAcceptHoverEvents(True)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self._apply_style()

    # -- Style ----------------------------------------------------------------
    def _apply_style(self):
        fill = self._color if not self._selected else SELECT_COLOR
        self.setBrush(QBrush(fill))
        border = fill.darker(130)
        pen = QPen(border, 1.2 if not self._selected else 2.0)
        self.setPen(pen)

    def set_selected_state(self, selected: bool):
        self._selected = selected
        self._apply_style()
        self.update()

    # -- Hover ----------------------------------------------------------------
    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(self._color.lighter(130)))
        preds_fs = ", ".join(self.task.predecessors_fs) or "—"
        preds_ss = ", ".join(self.task.predecessors_ss) or "—"
        tip = (
            f"<b>{self.task.name}</b><br>"
            f"ID: {self.task.id}<br>"
            f"Resource: {self.task.resource}<br>"
            f"Duration: {self.task.duration:.1f} s<br>"
            f"Start: {self.task.start_time:.2f} s &nbsp; End: {self.task.end_time:.2f} s<br>"
            f"<small>FS predecessors: {preds_fs}<br>SS predecessors: {preds_ss}</small>"
        )
        QToolTip.showText(QCursor.pos(), tip)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._apply_style()
        QToolTip.hideText()
        super().hoverLeaveEvent(event)


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------
class GanttScene(QGraphicsScene):
    """Scene that owns all Gantt items."""
    task_clicked = pyqtSignal(object)   # emits Task | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model: Optional[SequenceModel] = None
        self._px_per_s: float = DEFAULT_PX_S
        self._bar_items: List[TaskBarItem] = []
        self._resource_colors: Dict[str, QColor] = {}

    # -- Public API ----------------------------------------------------------
    def set_model(self, model: Optional[SequenceModel], px_per_s: float = DEFAULT_PX_S):
        self._model = model
        self._px_per_s = px_per_s
        self._rebuild()

    def set_zoom(self, px_per_s: float):
        self._px_per_s = max(MIN_PX_PER_S, min(MAX_PX_PER_S, px_per_s))
        self._rebuild()

    def get_zoom(self) -> float:
        return self._px_per_s

    def resource_color(self, resource_id: str) -> QColor:
        return self._resource_colors.get(resource_id, QColor("#888888"))

    # -- Build ----------------------------------------------------------------
    def _rebuild(self):
        self.clear()
        self._bar_items.clear()
        if self._model is None:
            return

        model = self._model
        resources = model.resources
        num_rows = len(resources)

        # Map resource -> colour
        self._resource_colors = {}
        for i, res in enumerate(resources):
            if res.color and res.color.startswith("#"):
                self._resource_colors[res.id] = QColor(res.color)
            else:
                self._resource_colors[res.id] = QColor(RESOURCE_PALETTE[i % len(RESOURCE_PALETTE)])

        # Compute max time
        max_t = max(
            (t.end_time for t in model.tasks if t.end_time is not None),
            default=model.settings.takt_time,
        )
        takt_t = model.settings.takt_time
        canvas_w = LABEL_WIDTH + (max(max_t, takt_t) + 5) * self._px_per_s
        canvas_h = HEADER_H + num_rows * ROW_HEIGHT

        # Background
        self.setSceneRect(0, 0, canvas_w, canvas_h)
        bg = self.addRect(QRectF(0, 0, canvas_w, canvas_h), QPen(Qt.PenStyle.NoPen), QBrush(BG_COLOR))

        # Header background
        self.addRect(QRectF(0, 0, canvas_w, HEADER_H), QPen(Qt.PenStyle.NoPen), QBrush(HDR_COLOR))

        # Row stripes
        for row_i, _ in enumerate(resources):
            y = HEADER_H + row_i * ROW_HEIGHT
            color = ROW_EVEN if row_i % 2 == 0 else ROW_ALT
            self.addRect(QRectF(0, y, canvas_w, ROW_HEIGHT), QPen(Qt.PenStyle.NoPen), QBrush(color))

        # Gridlines + tick labels
        self._draw_grid(canvas_h, max_t, takt_t)

        # Resource labels (left column background)
        self.addRect(QRectF(0, 0, LABEL_WIDTH, canvas_h), QPen(Qt.PenStyle.NoPen), QBrush(QColor(EXEC_NAVY)))

        # Divider line between label col and chart
        pen_divider = QPen(GRID_COLOR, 1)
        self.addLine(LABEL_WIDTH, 0, LABEL_WIDTH, canvas_h, pen_divider)

        for row_i, res in enumerate(resources):
            y = HEADER_H + row_i * ROW_HEIGHT
            # Row border
            self.addLine(0, y, canvas_w, y, QPen(GRID_COLOR, 0.5))
            # Label
            lbl = self.addText(res.id)
            lbl.setDefaultTextColor(QColor(res.color if res.color else SILVER))
            lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            lbl.setPos(8, y + (ROW_HEIGHT - lbl.boundingRect().height()) / 2)

        # Takt line
        takt_x = LABEL_WIDTH + takt_t * self._px_per_s
        takt_pen = QPen(TAKT_COLOR, 2, Qt.PenStyle.DashLine)
        takt_line = self.addLine(takt_x, 0, takt_x, canvas_h, takt_pen)
        takt_lbl = self.addSimpleText(f"Takt {takt_t:.0f}s")
        takt_lbl.setFont(QFont("Segoe UI", 8))
        takt_lbl.setBrush(QBrush(TAKT_COLOR))
        takt_lbl.setPos(takt_x + 3, 4)

        # Task bars
        resource_index = {res.id: i for i, res in enumerate(resources)}
        for task in model.tasks:
            if task.start_time is None or task.end_time is None:
                continue
            row_i = resource_index.get(task.resource)
            if row_i is None:
                continue
            color = self._resource_colors.get(task.resource, QColor("#888888"))
            x = LABEL_WIDTH + task.start_time * self._px_per_s
            y = HEADER_H + row_i * ROW_HEIGHT + ROW_PADDING
            w = max(task.duration * self._px_per_s, 2)
            h = ROW_HEIGHT - 2 * ROW_PADDING
            bar = TaskBarItem(task, x, y, w, h, color)
            self.addItem(bar)
            self._bar_items.append(bar)

            # Task label inside bar (if wide enough)
            if w > 30:
                task_lbl = self.addSimpleText(task.name[:20] + ("…" if len(task.name) > 20 else ""))
                task_lbl.setFont(QFont("Segoe UI", 7))
                task_lbl.setBrush(QBrush(QColor(WHITE)))
                task_lbl.setPos(x + 4, y + (h - task_lbl.boundingRect().height()) / 2)
                task_lbl.setZValue(1)

        # Bottom border
        self.addLine(0, canvas_h, canvas_w, canvas_h, QPen(GRID_COLOR, 1))

    def _draw_grid(self, canvas_h: float, max_t: float, takt_t: float):
        """Draw time-axis ticks and vertical grid lines."""
        display_max = max(max_t, takt_t) + 5
        step = TICK_MAJOR  # seconds between labels
        t = 0.0
        font_small = QFont("Segoe UI", 8)
        pen_major = QPen(QColor("#1E3A54"), 1, Qt.PenStyle.SolidLine)
        pen_minor = QPen(QColor("#152838"), 1, Qt.PenStyle.SolidLine)

        while t <= display_max:
            x = LABEL_WIDTH + t * self._px_per_s
            # grid line
            pen = pen_major if t % 10 == 0 else pen_minor
            self.addLine(x, HEADER_H, x, canvas_h, pen)
            # tick label
            lbl = self.addSimpleText(f"{t:.0f}s")
            lbl.setFont(font_small)
            lbl.setBrush(QBrush(QColor(SILVER)))
            lbl.setPos(x - lbl.boundingRect().width() / 2, HEADER_H - 20)
            # minor tick mark
            self.addLine(x, HEADER_H - 4, x, HEADER_H, QPen(QColor(SILVER), 1))
            t += step

    # -- Mouse ---------------------------------------------------------------
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        items = self.selectedItems()
        if items:
            for item in self._bar_items:
                item.set_selected_state(item in items)
            clicked = next((i.task for i in self._bar_items if i in items), None)
            self.task_clicked.emit(clicked)
        else:
            for item in self._bar_items:
                item.set_selected_state(False)
            self.task_clicked.emit(None)


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------
class GanttView(QGraphicsView):
    """QGraphicsView wrapper with zoom (Ctrl+Scroll) and pan support."""

    task_clicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = GanttScene()
        self._scene.task_clicked.connect(self.task_clicked)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setStyleSheet("background-color: #0D1B2A; border: none;")

    def load_model(self, model: Optional[SequenceModel]):
        self._scene.set_model(model)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            new_zoom = self._scene.get_zoom() * factor
            self._scene.set_zoom(new_zoom)
        else:
            super().wheelEvent(event)

    def resource_color(self, resource_id: str) -> QColor:
        return self._scene.resource_color(resource_id)
