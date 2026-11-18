"""
gantt_canvas.py — Interactive Gantt chart canvas using QGraphicsScene/View.

Features:
  - Horizontal timeline, resources on Y-axis
  - Task bars coloured by resource
  - Vertical takt-time marker line (Comau Red)
  - Hover tooltips with task details
  - Zoom (Ctrl+Scroll) and pan (middle-mouse / scroll)
  - Click-to-select task (emits signal to update sidebar)
  - Drag right edge of bar to resize duration (live reschedule on release)
  - Dependency arrows drawn between tasks (FS = solid grey, SS = dashed amber)
  - Right-click drag from Task A to Task B to link dependencies (FS or SS)
  - Right-click on existing dependency arrow to remove it
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import (Qt, QRectF, QPointF, pyqtSignal, QObject, QLineF)
from PyQt6.QtGui import (
    QColor, QBrush, QPen, QPainter, QFont, QCursor, QPolygonF, QPainterPath,
)
from PyQt6.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsLineItem, QGraphicsItem, QGraphicsPathItem,
    QToolTip, QGraphicsSimpleTextItem, QGraphicsEllipseItem,
    QGraphicsPolygonItem, QMenu,
)

from sim_sequence.models import SequenceModel, Task, Resource
from .theme import COMAU_RED, EXEC_NAVY, SLATE, WHITE, SILVER, GRID_LINE, RESOURCE_PALETTE

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
ROW_HEIGHT   = 44
ROW_PADDING  = 6
LABEL_WIDTH  = 160
HEADER_H     = 40
TICK_MAJOR   = 5          # seconds between major tick labels
MIN_PX_PER_S = 4.0
MAX_PX_PER_S = 80.0
DEFAULT_PX_S = 14.0
RESIZE_HANDLE_W = 8       # px width of the right-edge resize handle
ARROW_HEAD_SIZE = 8       # px arrowhead length

TAKT_COLOR   = QColor(COMAU_RED)
GRID_COLOR   = QColor(GRID_LINE)
BG_COLOR     = QColor("#0D1B2A")
HDR_COLOR    = QColor(EXEC_NAVY)
ROW_ALT      = QColor("#0F1F30")
ROW_EVEN     = QColor("#0D1B2A")
LABEL_FG     = QColor(SILVER)
TASK_FG      = QColor(WHITE)
SELECT_COLOR = QColor("#2979FF")
RESIZE_COLOR = QColor("#FFFFFF")
FS_ARROW_COLOR = QColor("#B0BAC4")
SS_ARROW_COLOR = QColor("#F39C12")


# ---------------------------------------------------------------------------
# Dependency arrow
# ---------------------------------------------------------------------------
class DependencyArrow(QGraphicsPathItem):
    """Draws an elbow arrow from one task bar to another with context menu support."""

    def __init__(self, pred_id: str, task_id: str, dep_type: str, color: QColor, parent=None):
        super().__init__(parent)
        self.pred_id = pred_id
        self.task_id = task_id
        self.dep_type = dep_type   # "FS" or "SS"
        self._color = color
        style = Qt.PenStyle.SolidLine if dep_type == "FS" else Qt.PenStyle.DashLine
        pen = QPen(color, 1.4, style)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setZValue(0.5)
        self._head: Optional[QGraphicsPolygonItem] = None
        self.setAcceptHoverEvents(True)

    def set_route(self, x1: float, y1: float, x2: float, y2: float):
        """Draw an elbow path from (x1,y1) to (x2,y2) with an arrowhead at the end."""
        path = QPainterPath()
        path.moveTo(x1, y1)
        mid_x = (x1 + x2) / 2
        path.lineTo(mid_x, y1)
        path.lineTo(mid_x, y2)
        path.lineTo(x2, y2)
        self.setPath(path)
        self._draw_arrowhead(x2, y2, mid_x, y2)

    def _draw_arrowhead(self, tip_x: float, tip_y: float, from_x: float, from_y: float):
        """Draw a solid triangle arrowhead at (tip_x, tip_y) pointing from (from_x, from_y)."""
        if self._head and self._head.scene():
            self._head.scene().removeItem(self._head)

        angle = math.atan2(tip_y - from_y, tip_x - from_x)
        s = ARROW_HEAD_SIZE
        p1 = QPointF(tip_x - s * math.cos(angle - 0.4), tip_y - s * math.sin(angle - 0.4))
        p2 = QPointF(tip_x - s * math.cos(angle + 0.4), tip_y - s * math.sin(angle + 0.4))
        poly = QPolygonF([QPointF(tip_x, tip_y), p1, p2])
        self._head = QGraphicsPolygonItem(poly)
        self._head.setBrush(QBrush(self._color))
        self._head.setPen(QPen(Qt.PenStyle.NoPen))
        self._head.setZValue(0.6)
        if self.scene():
            self.scene().addItem(self._head)

    def hoverEnterEvent(self, event):
        hl_color = QColor("#2979FF")
        style = Qt.PenStyle.SolidLine if self.dep_type == "FS" else Qt.PenStyle.DashLine
        self.setPen(QPen(hl_color, 2.4, style))
        if self._head:
            self._head.setBrush(QBrush(hl_color))
        tip = (
            f"<b>{self.dep_type} Dependency</b>: <code>{self.pred_id}</code> ➔ <code>{self.task_id}</code><br>"
            f"<small style='color:#B0BAC4'>Right-click to remove dependency</small>"
        )
        QToolTip.showText(QCursor.pos(), tip)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        style = Qt.PenStyle.SolidLine if self.dep_type == "FS" else Qt.PenStyle.DashLine
        self.setPen(QPen(self._color, 1.4, style))
        if self._head:
            self._head.setBrush(QBrush(self._color))
        QToolTip.hideText()
        super().hoverLeaveEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu()
        act_remove = menu.addAction(f"❌ Remove {self.dep_type} Dependency: {self.pred_id} ➔ {self.task_id}")
        selected = menu.exec(event.screenPos())
        if selected == act_remove and self.scene():
            self.scene().dependency_removed.emit(self.pred_id, self.task_id, self.dep_type)
        event.accept()

    def cleanup(self):
        if self._head and self._head.scene():
            self._head.scene().removeItem(self._head)


# ---------------------------------------------------------------------------
# Task bar graphics item
# ---------------------------------------------------------------------------
class TaskBarItem(QGraphicsRectItem):
    """A single coloured task bar on the Gantt canvas.

    Supports:
      - Left-drag on right edge to resize duration
      - Right-drag to another task to create a dependency link
    """

    def __init__(
        self,
        task: Task,
        x: float,
        y: float,
        w: float,
        h: float,
        color: QColor,
        px_per_s: float,
        parent=None,
    ):
        super().__init__(x, y, w, h, parent)
        self.task = task
        self._color = color
        self._px_per_s = px_per_s
        self._selected = False
        self._resizing = False
        self._resize_start_x: float = 0.0
        self._orig_duration: float = task.duration
        self.setAcceptHoverEvents(True)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self._apply_style()

    # -- Style ----------------------------------------------------------------
    def _apply_style(self):
        fill = self._color if not self._selected else SELECT_COLOR
        self.setBrush(QBrush(fill))
        border = fill.darker(130)
        self.setPen(QPen(border, 1.2 if not self._selected else 2.0))

    def set_selected_state(self, selected: bool):
        self._selected = selected
        self._apply_style()
        self.update()

    # -- Hover ----------------------------------------------------------------
    def _in_resize_zone(self, pos: QPointF) -> bool:
        return pos.x() >= self.rect().right() - RESIZE_HANDLE_W

    def hoverMoveEvent(self, event):
        if self._in_resize_zone(event.pos()):
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        super().hoverMoveEvent(event)

    def hoverEnterEvent(self, event):
        if not self._resizing:
            self.setBrush(QBrush(self._color.lighter(130)))
        preds_fs = ", ".join(self.task.predecessors_fs) or "—"
        preds_ss = ", ".join(self.task.predecessors_ss) or "—"
        tip = (
            f"<b>{self.task.name}</b><br>"
            f"ID: <code>{self.task.id}</code><br>"
            f"Resource: {self.task.resource}<br>"
            f"Duration: {self.task.duration:.1f} s<br>"
            f"Start: {self.task.start_time:.2f} s &nbsp;&nbsp; End: {self.task.end_time:.2f} s<br>"
            f"<small>FS: {preds_fs}<br>SS: {preds_ss}</small><br>"
            f"<i style='color:#607D8B'>Drag right edge to resize | Right-click drag to link dependency</i>"
        )
        QToolTip.showText(QCursor.pos(), tip)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if not self._resizing:
            self._apply_style()
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        QToolTip.hideText()
        super().hoverLeaveEvent(event)

    # -- Mouse (resize drag & dependency link drag) ---------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._in_resize_zone(event.pos()):
            self._resizing = True
            self._resize_start_x = event.scenePos().x()
            self._orig_duration = self.task.duration
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            if self.scene() and hasattr(self.scene(), "start_linking"):
                self.scene().start_linking(self, event.scenePos())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta_x = event.scenePos().x() - self._resize_start_x
            delta_s = delta_x / self._px_per_s
            new_dur = max(0.1, self._orig_duration + delta_s)
            self.task.duration = round(new_dur, 2)
            # Visually resize the rect
            r = self.rect()
            self.setRect(r.x(), r.y(), new_dur * self._px_per_s, r.height())
            event.accept()
        elif self.scene() and hasattr(self.scene(), "is_linking") and self.scene().is_linking():
            self.scene().update_linking(event.scenePos())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing and event.button() == Qt.MouseButton.LeftButton:
            self._resizing = False
            self._apply_style()
            if self.scene():
                self.scene().task_resized.emit(self.task)
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            if self.scene() and hasattr(self.scene(), "is_linking") and self.scene().is_linking():
                self.scene().finish_linking(event.scenePos())
            event.accept()
        else:
            super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------
class GanttScene(QGraphicsScene):
    """Scene that owns all Gantt items."""
    task_clicked = pyqtSignal(object)           # emits Task | None
    task_resized = pyqtSignal(object)           # emits Task after drag-resize release
    dependency_added = pyqtSignal(str, str, str)   # (from_task_id, to_task_id, dep_type)
    dependency_removed = pyqtSignal(str, str, str) # (from_task_id, to_task_id, dep_type)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model: Optional[SequenceModel] = None
        self._px_per_s: float = DEFAULT_PX_S
        self._bar_items: List[TaskBarItem] = []
        self._dep_arrows: List[DependencyArrow] = []
        self._resource_colors: Dict[str, QColor] = {}
        self._linking_source_bar: Optional[TaskBarItem] = None
        self._temp_link_line: Optional[QGraphicsLineItem] = None

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

    # -- Interactive Linking API ---------------------------------------------
    def start_linking(self, source_bar: TaskBarItem, start_pos: QPointF):
        self._linking_source_bar = source_bar
        rect = source_bar.rect()
        start_pt = QPointF(rect.right(), rect.center().y())
        pen = QPen(QColor("#2979FF"), 2.0, Qt.PenStyle.DashLine)
        self._temp_link_line = self.addLine(QLineF(start_pt, start_pos), pen)
        self._temp_link_line.setZValue(10)

    def update_linking(self, current_pos: QPointF):
        if self._temp_link_line and self._linking_source_bar:
            rect = self._linking_source_bar.rect()
            start_pt = QPointF(rect.right(), rect.center().y())
            self._temp_link_line.setLine(QLineF(start_pt, current_pos))

    def is_linking(self) -> bool:
        return self._linking_source_bar is not None

    def finish_linking(self, end_pos: QPointF):
        if self._temp_link_line:
            self.removeItem(self._temp_link_line)
            self._temp_link_line = None

        source_bar = self._linking_source_bar
        self._linking_source_bar = None
        if not source_bar:
            return

        target_items = [
            i for i in self.items(end_pos)
            if isinstance(i, TaskBarItem) and i != source_bar
        ]
        if not target_items:
            return

        target_bar = target_items[0]
        src_id = source_bar.task.id
        dst_id = target_bar.task.id

        menu = QMenu()
        act_fs = menu.addAction(f"➡ Add Finish-to-Start (FS): {src_id} ➔ {dst_id}")
        act_ss = menu.addAction(f"⇥ Add Start-to-Start (SS): {src_id} ➔ {dst_id}")
        menu.addSeparator()
        act_cancel = menu.addAction("Cancel")

        selected = menu.exec(QCursor.pos())
        if selected == act_fs:
            self.dependency_added.emit(src_id, dst_id, "FS")
        elif selected == act_ss:
            self.dependency_added.emit(src_id, dst_id, "SS")

    # -- Build ----------------------------------------------------------------
    def _rebuild(self):
        for arrow in self._dep_arrows:
            arrow.cleanup()
        self.clear()
        self._bar_items.clear()
        self._dep_arrows.clear()
        self._linking_source_bar = None
        self._temp_link_line = None

        if self._model is None:
            return

        model = self._model
        resources = model.resources
        num_rows = len(resources)

        self._resource_colors = {}
        for i, res in enumerate(resources):
            if res.color and res.color.startswith("#"):
                self._resource_colors[res.id] = QColor(res.color)
            else:
                self._resource_colors[res.id] = QColor(RESOURCE_PALETTE[i % len(RESOURCE_PALETTE)])

        max_t = max(
            (t.end_time for t in model.tasks if t.end_time is not None),
            default=model.settings.takt_time,
        )
        takt_t = model.settings.takt_time
        canvas_w = LABEL_WIDTH + (max(max_t, takt_t) + 5) * self._px_per_s
        canvas_h = HEADER_H + num_rows * ROW_HEIGHT

        self.setSceneRect(0, 0, canvas_w, canvas_h)

        # Background
        self.addRect(QRectF(0, 0, canvas_w, canvas_h), QPen(Qt.PenStyle.NoPen), QBrush(BG_COLOR))

        # Header background
        self.addRect(QRectF(0, 0, canvas_w, HEADER_H), QPen(Qt.PenStyle.NoPen), QBrush(HDR_COLOR))

        # Row stripes
        for row_i in range(num_rows):
            y = HEADER_H + row_i * ROW_HEIGHT
            color = ROW_EVEN if row_i % 2 == 0 else ROW_ALT
            self.addRect(QRectF(0, y, canvas_w, ROW_HEIGHT), QPen(Qt.PenStyle.NoPen), QBrush(color))

        # Grid + tick labels
        self._draw_grid(canvas_h, max(max_t, takt_t) + 5)

        # Label column background
        self.addRect(QRectF(0, 0, LABEL_WIDTH, canvas_h), QPen(Qt.PenStyle.NoPen), QBrush(QColor(EXEC_NAVY)))
        self.addLine(LABEL_WIDTH, 0, LABEL_WIDTH, canvas_h, QPen(GRID_COLOR, 1))

        resource_index: Dict[str, int] = {res.id: i for i, res in enumerate(resources)}
        bar_map: Dict[str, TaskBarItem] = {}

        for row_i, res in enumerate(resources):
            y = HEADER_H + row_i * ROW_HEIGHT
            self.addLine(0, y, canvas_w, y, QPen(GRID_COLOR, 0.5))
            lbl = self.addText(res.id)
            lbl.setDefaultTextColor(QColor(res.color if res.color else SILVER))
            lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            lbl.setPos(8, y + (ROW_HEIGHT - lbl.boundingRect().height()) / 2)

        # Takt line
        takt_x = LABEL_WIDTH + takt_t * self._px_per_s
        self.addLine(takt_x, 0, takt_x, canvas_h, QPen(TAKT_COLOR, 2, Qt.PenStyle.DashLine))
        takt_lbl = self.addSimpleText(f"Takt {takt_t:.0f}s")
        takt_lbl.setFont(QFont("Segoe UI", 8))
        takt_lbl.setBrush(QBrush(TAKT_COLOR))
        takt_lbl.setPos(takt_x + 3, 4)

        # Task bars
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
            bar = TaskBarItem(task, x, y, w, h, color, self._px_per_s)
            self.addItem(bar)
            self._bar_items.append(bar)
            bar_map[task.id] = bar

            # Inline label
            if w > 30:
                label_text = task.name[:20] + ("…" if len(task.name) > 20 else "")
                lbl2 = self.addSimpleText(label_text)
                lbl2.setFont(QFont("Segoe UI", 7))
                lbl2.setBrush(QBrush(QColor(WHITE)))
                lbl2.setPos(x + 4, y + (h - lbl2.boundingRect().height()) / 2)
                lbl2.setZValue(1)

            # Resize handle visual (tinted grip)
            handle = self.addRect(
                QRectF(x + w - RESIZE_HANDLE_W, y + 2, RESIZE_HANDLE_W, h - 4),
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(255, 255, 255, 30)),
            )
            handle.setZValue(1.5)

        # Dependency arrows
        self._draw_dependency_arrows(model, bar_map, resource_index)

        # Bottom border
        self.addLine(0, canvas_h, canvas_w, canvas_h, QPen(GRID_COLOR, 1))

    def _draw_dependency_arrows(
        self,
        model: SequenceModel,
        bar_map: Dict[str, TaskBarItem],
        resource_index: Dict[str, int],
    ):
        task_map = {t.id: t for t in model.tasks}

        for task in model.tasks:
            dest_bar = bar_map.get(task.id)
            if dest_bar is None:
                continue
            dest_row = resource_index.get(task.resource)
            if dest_row is None:
                continue

            dest_x = dest_bar.rect().x()                              # left edge of destination
            dest_y = HEADER_H + dest_row * ROW_HEIGHT + ROW_HEIGHT / 2

            # Finish-to-Start arrows (solid, grey)
            for pred_id in task.predecessors_fs:
                src_bar = bar_map.get(pred_id)
                src_task = task_map.get(pred_id)
                if src_bar is None or src_task is None:
                    continue
                src_row = resource_index.get(src_task.resource)
                if src_row is None:
                    continue
                src_x = src_bar.rect().right()                        # right edge of source
                src_y = HEADER_H + src_row * ROW_HEIGHT + ROW_HEIGHT / 2
                arrow = DependencyArrow(pred_id, task.id, "FS", FS_ARROW_COLOR)
                self.addItem(arrow)
                arrow.set_route(src_x, src_y, dest_x, dest_y)
                self._dep_arrows.append(arrow)

            # Start-to-Start arrows (dashed, amber)
            for pred_id in task.predecessors_ss:
                src_bar = bar_map.get(pred_id)
                src_task = task_map.get(pred_id)
                if src_bar is None or src_task is None:
                    continue
                src_row = resource_index.get(src_task.resource)
                if src_row is None:
                    continue
                src_x = src_bar.rect().x()                            # left edge of source
                src_y = HEADER_H + src_row * ROW_HEIGHT + ROW_HEIGHT / 2
                arrow = DependencyArrow(pred_id, task.id, "SS", SS_ARROW_COLOR)
                self.addItem(arrow)
                arrow.set_route(src_x, src_y, dest_x, dest_y)
                self._dep_arrows.append(arrow)

    def _draw_grid(self, canvas_h: float, display_max: float):
        font_small = QFont("Segoe UI", 8)
        pen_major = QPen(QColor("#1E3A54"), 1)
        pen_minor = QPen(QColor("#152838"), 1)
        t = 0.0
        while t <= display_max:
            x = LABEL_WIDTH + t * self._px_per_s
            pen = pen_major if t % 10 == 0 else pen_minor
            self.addLine(x, HEADER_H, x, canvas_h, pen)
            lbl = self.addSimpleText(f"{t:.0f}s")
            lbl.setFont(font_small)
            lbl.setBrush(QBrush(QColor(SILVER)))
            lbl.setPos(x - lbl.boundingRect().width() / 2, HEADER_H - 20)
            self.addLine(x, HEADER_H - 4, x, HEADER_H, QPen(QColor(SILVER), 1))
            t += TICK_MAJOR

    # -- Mouse ---------------------------------------------------------------
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        items = self.selectedItems()
        bar_items_selected = [i for i in items if isinstance(i, TaskBarItem)]
        for item in self._bar_items:
            item.set_selected_state(item in bar_items_selected)
        clicked = bar_items_selected[0].task if bar_items_selected else None
        self.task_clicked.emit(clicked)


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------
class GanttView(QGraphicsView):
    """QGraphicsView wrapper with zoom (Ctrl+Scroll) and pan support."""

    task_clicked = pyqtSignal(object)
    task_resized = pyqtSignal(object)
    dependency_added = pyqtSignal(str, str, str)
    dependency_removed = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = GanttScene()
        self._scene.task_clicked.connect(self.task_clicked)
        self._scene.task_resized.connect(self.task_resized)
        self._scene.dependency_added.connect(self.dependency_added)
        self._scene.dependency_removed.connect(self.dependency_removed)
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
            self._scene.set_zoom(self._scene.get_zoom() * factor)
        else:
            super().wheelEvent(event)

    def resource_color(self, resource_id: str) -> QColor:
        return self._scene.resource_color(resource_id)
