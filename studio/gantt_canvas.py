"""
gantt_canvas.py — Interactive Gantt chart (QGraphicsScene / QGraphicsView).

Interaction
-----------
* Drag the **right handle** (blue) of a bar onto another bar  -> FS link
  (target starts after the source finishes).
* Drag the **left handle** (amber) of a bar onto another bar  -> SS link
  (target starts no earlier than the source starts).
  While dragging, the bar under the cursor turns green (valid) or red
  (invalid: self-link, duplicate, or would create a cycle).  Esc cancels.
* Click a link to select it, then press **Delete** or click its red ✕ to
  remove it.  Right-click a link also offers "Remove".
* Drag the right edge of a bar to change its duration.
* Ctrl+Wheel zooms; "Fit" fits the sequence to the window and keeps it fitted
  as the window is resized until you zoom manually.

Layout
------
* The resource column and time header are "sticky": they stay visible while
  you scroll.
* Tasks of one resource that overlap in time are stacked in sub-lanes so
  bars never draw on top of each other.
* Bar text is elided to fit its bar; tick spacing adapts to the zoom level.

The scene never mutates the model.  It emits signals (by task ID) and the
main window applies the change through the ProjectStore.  Signals fired from
inside an item's mouse handler are deferred with a zero-delay timer because
handling them rebuilds the scene (and would otherwise delete the item whose
handler is still running).
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QCursor, QFont, QFontMetrics,
                         QPainter, QPainterPath, QPainterPathStroker, QPen,
                         QPolygonF)
from PyQt6.QtWidgets import (QFrame, QGraphicsEllipseItem, QGraphicsItem,
                             QGraphicsLineItem, QGraphicsPathItem,
                             QGraphicsPolygonItem, QGraphicsRectItem,
                             QGraphicsScene, QGraphicsSimpleTextItem,
                             QGraphicsView, QMenu)

from sim_sequence.graph_ops import assign_lanes, nice_tick_step
from sim_sequence.models import SequenceModel, Task

from .theme import COMAU_RED, DARK, RESOURCE_PALETTE, Theme, contrast_color

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
HEADER_H = 34
BAR_H = 24
LANE_H = 30                      # bar height + gap between stacked lanes
ROW_PAD = 8                      # space above / below the lanes of a resource row
MIN_LABEL_W, MAX_LABEL_W = 110, 260
MIN_PX_PER_S, MAX_PX_PER_S = 0.5, 120.0
DEFAULT_PX_S = 14.0
RESIZE_HANDLE_W = 8
PORT_R = 5.0                     # link handle radius
PORT_GAP = 9.0                   # distance from bar edge to handle centre
ARROW_HEAD = 8.0
ROUTE_GAP = 12.0                 # stub length when routing around bars
HIT_WIDTH = 10.0                 # clickable width of a link

FS, SS = "FS", "SS"


def _fmt_time(t: float) -> str:
    if t >= 120:
        return f"{int(t // 60)}:{int(t % 60):02d}"
    return f"{t:g}s"


# ---------------------------------------------------------------------------
# Dependency arrow
# ---------------------------------------------------------------------------
class DeleteBadge(QGraphicsEllipseItem):
    """Red ✕ shown on a selected link; clicking removes the link."""
    R = 8.0

    def __init__(self, arrow: "DependencyArrow"):
        super().__init__(-self.R, -self.R, 2 * self.R, 2 * self.R, arrow)
        self._arrow = arrow
        self.setZValue(10)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip("Remove this link")

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(self._arrow.theme.link_bad)))
        painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
        painter.drawEllipse(self.rect())
        painter.setPen(QPen(QColor("#FFFFFF"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        d = 3.0
        painter.drawLine(QPointF(-d, -d), QPointF(d, d))
        painter.drawLine(QPointF(-d, d), QPointF(d, -d))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._arrow.request_delete()
            event.accept()
        else:
            event.ignore()


class DependencyArrow(QGraphicsPathItem):
    """An FS (solid) or SS (dashed) link between two bars."""

    def __init__(self, pred_id: str, task_id: str, dep_type: str, theme: Theme):
        super().__init__()
        self.pred_id, self.task_id, self.dep_type = pred_id, task_id, dep_type
        self.theme = theme
        self._base = QColor(theme.arrow_fs if dep_type == FS else theme.arrow_ss)
        self._hover = False
        self._shape = QPainterPath()
        self._bounds = QRectF()

        self.setZValue(0.5)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setToolTip(f"{dep_type} link: {pred_id} \u2192 {task_id}\n"
                        f"Click to select, then press Delete (or click \u2715) to remove")

        self._head = QGraphicsPolygonItem(self)
        self._head.setPen(QPen(Qt.PenStyle.NoPen))
        self._head.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._badge = DeleteBadge(self)
        self._badge.setVisible(False)
        self._restyle()

    # -- geometry ------------------------------------------------------------------
    def set_points(self, pts: List[QPointF]) -> None:
        path = QPainterPath(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        stroker = QPainterPathStroker()
        stroker.setWidth(HIT_WIDTH)
        self.prepareGeometryChange()
        self._shape = stroker.createStroke(path)
        self._bounds = self._shape.boundingRect().adjusted(-2, -2, 2, 2)
        self.setPath(path)
        self._place_head(pts[-2], pts[-1])
        self._badge.setPos(path.pointAtPercent(0.5))

    def _place_head(self, a: QPointF, b: QPointF) -> None:
        angle = math.atan2(b.y() - a.y(), b.x() - a.x())
        s = ARROW_HEAD
        p1 = QPointF(b.x() - s * math.cos(angle - 0.45), b.y() - s * math.sin(angle - 0.45))
        p2 = QPointF(b.x() - s * math.cos(angle + 0.45), b.y() - s * math.sin(angle + 0.45))
        self._head.setPolygon(QPolygonF([b, p1, p2]))

    def shape(self):
        return self._shape

    def boundingRect(self):
        return self._bounds

    # -- look ------------------------------------------------------------------------
    def _restyle(self) -> None:
        selected = self.isSelected()
        if selected or self._hover:
            color, width = QColor(self.theme.link_color), (3.0 if selected else 2.6)
        else:
            color, width = self._base, 1.6
        style = Qt.PenStyle.SolidLine if self.dep_type == FS else Qt.PenStyle.DashLine
        self.setPen(QPen(color, width, style))
        self._head.setBrush(QBrush(color))
        self._badge.setVisible(selected)
        self.setZValue(5 if selected else 0.5)
        self.update()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(self.pen())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._restyle()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        self._hover = True
        self._restyle()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hover = False
        self._restyle()
        super().hoverLeaveEvent(event)

    # -- actions -----------------------------------------------------------------------
    def request_delete(self) -> None:
        sc = self.scene()
        if isinstance(sc, GanttScene):
            sc.emit_later(sc.dependency_removed, self.pred_id, self.task_id, self.dep_type)

    def contextMenuEvent(self, event):
        menu = QMenu()
        act = menu.addAction(f"\u2715  Remove {self.dep_type} link: {self.pred_id} \u2192 {self.task_id}")
        if menu.exec(event.screenPos()) == act:
            self.request_delete()
        event.accept()


# ---------------------------------------------------------------------------
# Link handle + task bar
# ---------------------------------------------------------------------------
class LinkPort(QGraphicsEllipseItem):
    """Small handle beside a bar; drag from it onto another bar to link."""

    def __init__(self, bar: "TaskBarItem", kind: str):
        super().__init__(-PORT_R, -PORT_R, 2 * PORT_R, 2 * PORT_R, bar)
        self.bar, self.kind = bar, kind          # kind: "finish" (-> FS) or "start" (-> SS)
        self._hover = False
        self.setZValue(3)
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setToolTip("Drag onto another task to create a Finish\u2192Start (FS) link"
                        if kind == "finish" else
                        "Drag onto another task to create a Start\u2192Start (SS) link")

    def paint(self, painter, option, widget=None):
        th = self.bar.theme
        color = QColor(th.link_color if self.kind == "finish" else th.arrow_ss)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor("#FFFFFF") if self._hover else QColor(th.gantt_bg), 2.0 if self._hover else 1.5))
        r = self.rect()
        if self._hover:
            r = r.adjusted(-1.5, -1.5, 1.5, 1.5)
        painter.drawEllipse(r)

    def hoverEnterEvent(self, event):
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        sc = self.scene()
        if event.button() == Qt.MouseButton.LeftButton and isinstance(sc, GanttScene):
            sc.start_linking(self.bar, self.kind, event.scenePos())
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        sc = self.scene()
        if isinstance(sc, GanttScene) and sc.is_linking():
            sc.update_linking(event.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event):
        sc = self.scene()
        if event.button() == Qt.MouseButton.LeftButton and isinstance(sc, GanttScene) and sc.is_linking():
            sc.finish_linking(event.scenePos())
        event.accept()


class TaskBarItem(QGraphicsRectItem):
    """One task bar.  Right edge resizes; the two side handles start links."""

    def __init__(self, task: Task, x: float, y: float, w: float, h: float,
                 color: QColor, theme: Theme, px_per_s: float):
        super().__init__(x, y, w, h)
        self.task = task
        self.theme = theme
        self.row_top = self.row_bottom = y          # set by the scene (used for link routing)
        self._color = color
        self._fg = contrast_color(color)
        self._px = px_per_s
        self._hover = False
        self._link_state = ""                       # "", "good", "bad"
        self._resizing = False
        self._resize_x0 = 0.0
        self._resize_w0 = w
        self._preview = task.duration

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        self._label = QGraphicsSimpleTextItem(self)
        self._label.setFont(QFont("Segoe UI", 8))
        self._label.setBrush(QBrush(self._fg))
        self._label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._port_finish = LinkPort(self, "finish")
        self._port_start = LinkPort(self, "start")
        self._refresh_tooltip()
        self._relayout()

    # -- geometry helpers ---------------------------------------------------------------
    def edge_point(self, kind: str) -> QPointF:
        r = self.rect()
        return self.mapToScene(QPointF(r.right() if kind == "finish" else r.left(), r.center().y()))

    def _relayout(self) -> None:
        r = self.rect()
        cy = r.center().y()
        self._port_finish.setPos(r.right() + PORT_GAP, cy)
        self._port_start.setPos(r.left() - PORT_GAP, cy)
        avail = r.width() - RESIZE_HANDLE_W - 10
        fm = QFontMetrics(self._label.font())
        text = fm.elidedText(self.task.name, Qt.TextElideMode.ElideRight, int(avail)) if avail > 20 else ""
        self._label.setText(text)
        self._label.setPos(r.left() + 6, r.top() + (r.height() - fm.height()) / 2)

    def _refresh_tooltip(self) -> None:
        t = self.task
        dash = "\u2014"
        fs = ", ".join(t.predecessors_fs) or dash
        ss = ", ".join(t.predecessors_ss) or dash
        resource = t.resource or dash
        times = ""
        if t.start_time is not None and t.end_time is not None:
            times = f"Start {t.start_time:.1f}s \u2192 End {t.end_time:.1f}s<br>"
        self.setToolTip(
            f"<b>{t.name}</b> <small>({t.id})</small><br>"
            f"Resource: {resource}<br>Duration: {t.duration:g} s<br>{times}"
            f"<small>After (FS): {fs}<br>With (SS): {ss}</small><br>"
            f"<i>Drag the right edge to resize \u2022 drag a side handle to link</i>")

    def set_link_state(self, state: str) -> None:
        self._link_state = state
        self.update()

    # -- painting ---------------------------------------------------------------------------
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        fill = QColor(self._color)
        if self._hover and not self._link_state:
            fill = fill.lighter(112)

        if self._link_state == "good":
            pen = QPen(QColor(self.theme.link_ok), 3.0)
        elif self._link_state == "bad":
            pen = QPen(QColor(self.theme.link_bad), 3.0)
        elif self.isSelected():
            pen = QPen(QColor(self.theme.link_color), 2.5)
        else:
            pen = QPen(fill.darker(145), 1.2)
        painter.setBrush(QBrush(fill))
        painter.setPen(pen)
        painter.drawRoundedRect(r, 3, 3)

        if r.width() > 28:                      # resize grip
            grip = QColor(self._fg)
            grip.setAlpha(120)
            painter.setPen(QPen(grip, 1.0))
            x = r.right() - 3.5
            painter.drawLine(QPointF(x, r.top() + 6), QPointF(x, r.bottom() - 6))
            painter.drawLine(QPointF(x - 3, r.top() + 6), QPointF(x - 3, r.bottom() - 6))

    # -- hover ---------------------------------------------------------------------------------
    def _in_resize_zone(self, pos: QPointF) -> bool:
        r = self.rect()
        zone = min(RESIZE_HANDLE_W, r.width() / 3.0)
        return pos.x() >= r.right() - zone

    def hoverEnterEvent(self, event):
        self._hover = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        shape = Qt.CursorShape.SizeHorCursor if self._in_resize_zone(event.pos()) else Qt.CursorShape.ArrowCursor
        self.setCursor(QCursor(shape))
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self._hover = False
        self.update()
        super().hoverLeaveEvent(event)

    # -- resize drag -------------------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._in_resize_zone(event.pos()):
            self._resizing = True
            self._resize_x0 = event.scenePos().x()
            self._resize_w0 = self.rect().width()
            self._preview = self.task.duration
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            new_w = max(2.0, self._resize_w0 + (event.scenePos().x() - self._resize_x0))
            self._preview = max(0.1, round(new_w / self._px, 1))
            r = self.rect()
            self.setRect(r.x(), r.y(), self._preview * self._px, r.height())
            self._relayout()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing and event.button() == Qt.MouseButton.LeftButton:
            self._resizing = False
            sc = self.scene()
            if isinstance(sc, GanttScene) and abs(self._preview - self.task.duration) > 1e-9:
                sc.emit_later(sc.task_resized, self.task.id, float(self._preview))
            event.accept()
        else:
            super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------
class GanttScene(QGraphicsScene):
    task_clicked = pyqtSignal(object)               # Task | None
    task_resized = pyqtSignal(str, float)           # task_id, new duration
    dependency_added = pyqtSignal(str, str, str)    # src_id, dst_id, "FS" | "SS"
    dependency_removed = pyqtSignal(str, str, str)
    link_hint = pyqtSignal(str)                     # live status text while dragging a link
    rebuilt = pyqtSignal()

    def __init__(self, theme: Theme = DARK, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._model: Optional[SequenceModel] = None
        self._px = DEFAULT_PX_S
        self._label_w = float(MIN_LABEL_W)
        self._content_s = 60.0
        self._selected_task_id: Optional[str] = None
        self._bars: Dict[str, TaskBarItem] = {}
        self._grp_x: List[QGraphicsItem] = []        # follow horizontal scroll
        self._grp_y: List[QGraphicsItem] = []        # follow vertical scroll
        self._grp_xy: List[QGraphicsItem] = []       # follow both
        self.link_validator: Optional[Callable[[str, str, str], Tuple[bool, str]]] = None
        self._reset_link_state()

    def _reset_link_state(self) -> None:
        self._link_src: Optional[TaskBarItem] = None
        self._link_kind = ""
        self._link_line: Optional[QGraphicsLineItem] = None
        self._hl_bar: Optional[TaskBarItem] = None

    # -- public API ---------------------------------------------------------------------------------
    def emit_later(self, signal, *args) -> None:
        QTimer.singleShot(0, lambda: signal.emit(*args))

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self._rebuild()

    def set_model(self, model: Optional[SequenceModel]) -> None:
        self._model = model
        self._rebuild()

    def set_zoom(self, px_per_s: float) -> None:
        px = max(MIN_PX_PER_S, min(MAX_PX_PER_S, px_per_s))
        if abs(px - self._px) < 1e-6:
            return
        self._px = px
        self._rebuild()

    def get_zoom(self) -> float:
        return self._px

    @property
    def label_width(self) -> float:
        return self._label_w

    @property
    def content_seconds(self) -> float:
        return self._content_s

    def select_task(self, task_id: Optional[str]) -> None:
        self._selected_task_id = task_id
        for tid, bar in self._bars.items():
            bar.setSelected(tid == task_id)

    def update_sticky(self, left: float, top: float) -> None:
        for item in self._grp_x:
            item.setX(left)
        for item in self._grp_y:
            item.setY(top)
        for item in self._grp_xy:
            item.setPos(left, top)

    # -- link dragging ------------------------------------------------------------------------------------
    def is_linking(self) -> bool:
        return self._link_src is not None

    def _dep_type(self) -> str:
        return FS if self._link_kind == "finish" else SS

    def start_linking(self, bar: TaskBarItem, kind: str, pos: QPointF) -> None:
        self._link_src, self._link_kind = bar, kind
        pen = QPen(QColor(self._theme.link_color), 2.0, Qt.PenStyle.DashLine)
        self._link_line = self.addLine(QLineF(bar.edge_point(kind), pos), pen)
        self._link_line.setZValue(20)
        self.link_hint.emit("Drop on the task that should follow\u2026")

    def _bar_at(self, pos: QPointF, exclude: Optional[TaskBarItem]) -> Optional[TaskBarItem]:
        for item in self.items(pos):
            while item is not None and not isinstance(item, TaskBarItem):
                item = item.parentItem()
            if item is not None and item is not exclude:
                return item
        return None

    def _validate(self, target: TaskBarItem) -> Tuple[bool, str]:
        if self.link_validator is None or self._link_src is None:
            return True, ""
        return self.link_validator(self._link_src.task.id, target.task.id, self._dep_type())

    def update_linking(self, pos: QPointF) -> None:
        if self._link_src is None or self._link_line is None:
            return
        self._link_line.setLine(QLineF(self._link_src.edge_point(self._link_kind), pos))
        bar = self._bar_at(pos, self._link_src)
        if bar is self._hl_bar:
            return
        if self._hl_bar is not None:
            self._hl_bar.set_link_state("")
        self._hl_bar = bar
        if bar is None:
            self.link_hint.emit("Drop on the task that should follow\u2026")
            return
        ok, msg = self._validate(bar)
        bar.set_link_state("good" if ok else "bad")
        src = self._link_src.task.id
        self.link_hint.emit(f"{src} \u2192 {bar.task.id} ({self._dep_type()})" if ok else msg)

    def _end_link_drag(self) -> Tuple[Optional[TaskBarItem], str]:
        src, kind = self._link_src, self._link_kind
        if self._link_line is not None:
            self.removeItem(self._link_line)
        if self._hl_bar is not None:
            self._hl_bar.set_link_state("")
        self._reset_link_state()
        return src, kind

    def cancel_linking(self) -> None:
        if self.is_linking():
            self._end_link_drag()
            self.link_hint.emit("")

    def finish_linking(self, pos: QPointF) -> None:
        if self._link_src is None:
            return
        target = self._bar_at(pos, self._link_src)
        dep = self._dep_type()
        ok, msg = self._validate(target) if target is not None else (False, "")
        src, _kind = self._end_link_drag()
        if target is None or src is None:
            self.link_hint.emit("")
        elif ok:
            self.emit_later(self.dependency_added, src.task.id, target.task.id, dep)
            self.link_hint.emit("")
        else:
            self.link_hint.emit(msg)

    # -- build ----------------------------------------------------------------------------------------------
    def _rebuild(self) -> None:
        self._reset_link_state()
        self.clear()
        self._bars = {}
        self._grp_x, self._grp_y, self._grp_xy = [], [], []
        th = self._theme
        self.setBackgroundBrush(QBrush(QColor(th.gantt_bg)))

        model = self._model
        if model is None:
            self.setSceneRect(0, 0, 10, 10)
            self.rebuilt.emit()
            return

        # ---- rows: one per resource, plus "Unassigned" if needed ---------------------------
        rid_set = {r.id for r in model.resources}
        rows: List[Tuple[str, str, QColor]] = []
        for i, res in enumerate(model.resources):
            color = QColor(res.color) if res.color and res.color.startswith("#") \
                else QColor(RESOURCE_PALETTE[i % len(RESOURCE_PALETTE)])
            rows.append((res.id, res.id, color))

        scheduled = [t for t in model.tasks if t.start_time is not None and t.end_time is not None]
        by_row: Dict[str, List[Task]] = {key: [] for key, _, _ in rows}
        orphans = [t for t in scheduled if t.resource not in rid_set]
        for t in scheduled:
            if t.resource in rid_set:
                by_row[t.resource].append(t)
        if orphans:
            rows.append(("", "\u26a0 Unassigned", QColor(th.link_bad)))
            by_row[""] = orphans

        lanes_per_row = [assign_lanes(by_row[key]) for key, _, _ in rows]
        heights = [2 * ROW_PAD + (LANE_H * n - (LANE_H - BAR_H)) for _, n in lanes_per_row]
        tops: List[float] = []
        y = float(HEADER_H)
        for h in heights:
            tops.append(y)
            y += h
        body_h = y - HEADER_H

        # ---- extents ------------------------------------------------------------------------------
        label_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        fm = QFontMetrics(label_font)
        text_w = max((fm.horizontalAdvance(lbl) for _, lbl, _ in rows), default=0)
        self._label_w = float(max(MIN_LABEL_W, min(MAX_LABEL_W, text_w + 30)))
        lw, px = self._label_w, self._px

        max_t = max((t.end_time for t in scheduled), default=0.0)
        takt = model.settings.takt_time
        self._content_s = max(max_t, takt) * 1.04 + 2.0
        canvas_w = lw + self._content_s * px
        canvas_h = HEADER_H + max(body_h, 1.0)
        self.setSceneRect(0, 0, canvas_w, canvas_h)

        # ---- body: stripes, grid, separators, takt -----------------------------------------------
        no_pen = QPen(Qt.PenStyle.NoPen)
        for i, top in enumerate(tops):
            stripe = self.addRect(QRectF(0, top, canvas_w, heights[i]), no_pen,
                                  QBrush(QColor(th.gantt_row_alt if i % 2 else th.gantt_bg)))
            stripe.setZValue(-10)

        step = nice_tick_step(px)
        header_items: List[QGraphicsItem] = []
        tick_font = QFont("Segoe UI", 8)
        t, n = 0.0, 0
        while t <= self._content_s + 1e-9:
            x = lw + t * px
            strong = (n % 2 == 0)
            grid = self.addLine(x, HEADER_H, x, canvas_h,
                                QPen(QColor(th.gantt_grid_strong if strong else th.gantt_grid), 1))
            grid.setZValue(-9)
            header_items.append(self.addLine(x, HEADER_H - 5, x, HEADER_H, QPen(QColor(th.gantt_text_muted), 1)))
            if strong or step * px >= 90:
                lbl = self.addSimpleText(_fmt_time(t))
                lbl.setFont(tick_font)
                lbl.setBrush(QBrush(QColor(th.gantt_text_muted)))
                lbl.setPos(x + 3, HEADER_H - 22)
                header_items.append(lbl)
            t += step
            n += 1

        sep_pen = QPen(QColor(th.gantt_grid_strong), 1)
        for top, h in zip(tops, heights):
            self.addLine(0, top + h, canvas_w, top + h, sep_pen).setZValue(-8)

        takt_x = lw + takt * px
        takt_line = self.addLine(takt_x, HEADER_H, takt_x, canvas_h, QPen(QColor(COMAU_RED), 2, Qt.PenStyle.DashLine))
        takt_line.setZValue(-1)
        takt_lbl = self.addSimpleText(f"Takt {takt:g}s")
        takt_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        takt_lbl.setBrush(QBrush(QColor(COMAU_RED)))
        takt_lbl.setPos(takt_x + 4, 2)
        header_items.append(takt_lbl)

        # ---- bars -----------------------------------------------------------------------------------
        for i, (key, _lbl, color) in enumerate(rows):
            lanes, _n = lanes_per_row[i]
            for task in by_row[key]:
                bx = lw + task.start_time * px
                by = tops[i] + ROW_PAD + lanes[task.id] * LANE_H
                bar = TaskBarItem(task, bx, by, max(task.duration * px, 2.0), BAR_H, color, th, px)
                bar.row_top, bar.row_bottom = tops[i], tops[i] + heights[i]
                bar.setZValue(1)
                self.addItem(bar)
                self._bars[task.id] = bar
                if task.id == self._selected_task_id:
                    bar.setSelected(True)

        self._draw_links(model)

        # ---- sticky header / resource column / corner ----------------------------------------
        hdr_bg = self.addRect(QRectF(0, 0, canvas_w, HEADER_H), no_pen, QBrush(QColor(th.gantt_header_bg)))
        hdr_line = self.addLine(0, HEADER_H, canvas_w, HEADER_H, QPen(QColor(th.gantt_grid_strong), 1))
        hdr_bg.setZValue(-1)
        header_group = self.createItemGroup([hdr_bg, hdr_line] + header_items)
        header_group.setZValue(6)
        self._grp_y.append(header_group)

        col_items: List[QGraphicsItem] = []
        col_items.append(self.addRect(QRectF(0, HEADER_H, lw, max(body_h, 1.0)), no_pen, QBrush(QColor(th.gantt_label_bg))))
        col_items.append(self.addLine(lw, HEADER_H, lw, canvas_h, QPen(QColor(th.gantt_grid_strong), 1)))
        for i, (_key, label, color) in enumerate(rows):
            chip = self.addRect(QRectF(0, tops[i] + 5, 5, heights[i] - 10), no_pen, QBrush(color))
            text = self.addSimpleText(fm.elidedText(label, Qt.TextElideMode.ElideRight, int(lw - 22)))
            text.setFont(label_font)
            text.setBrush(QBrush(QColor(th.gantt_text)))
            text.setPos(12, tops[i] + (heights[i] - fm.height()) / 2)
            text.setToolTip(label)
            col_items += [chip, text]
            col_items.append(self.addLine(0, tops[i] + heights[i], lw, tops[i] + heights[i],
                                          QPen(QColor(th.gantt_grid_strong), 1)))
        col_group = self.createItemGroup(col_items)
        col_group.setZValue(5)
        self._grp_x.append(col_group)

        corner_bg = self.addRect(QRectF(0, 0, lw, HEADER_H), no_pen, QBrush(QColor(th.gantt_header_bg)))
        corner_txt = self.addSimpleText("RESOURCE")
        corner_txt.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        corner_txt.setBrush(QBrush(QColor(th.gantt_text_muted)))
        corner_txt.setPos(12, (HEADER_H - QFontMetrics(corner_txt.font()).height()) / 2)
        corner_lines = [self.addLine(lw, 0, lw, HEADER_H, QPen(QColor(th.gantt_grid_strong), 1)),
                        self.addLine(0, HEADER_H, lw, HEADER_H, QPen(QColor(th.gantt_grid_strong), 1))]
        corner = self.createItemGroup([corner_bg, corner_txt] + corner_lines)
        corner.setZValue(7)
        self._grp_xy.append(corner)

        self.rebuilt.emit()

    # -- links ------------------------------------------------------------------------------------------------
    def _route(self, kind: str, src: TaskBarItem, dst: TaskBarItem) -> List[QPointF]:
        rs, rd = src.rect(), dst.rect()
        y1, y2 = rs.center().y(), rd.center().y()
        x2 = rd.left()
        if kind == SS:
            x1 = rs.left()
            cx = min(x1, x2) - ROUTE_GAP
            return [QPointF(x1, y1), QPointF(cx, y1), QPointF(cx, y2), QPointF(x2, y2)]

        x1 = rs.right()
        if x2 - x1 >= 2 * ROUTE_GAP:                    # normal elbow
            mx = (x1 + x2) / 2.0
            return [QPointF(x1, y1), QPointF(mx, y1), QPointF(mx, y2), QPointF(x2, y2)]
        # target starts before the source ends: go round through the row gap
        if abs(y2 - y1) < 1.0:
            ymid = y1 + LANE_H / 2.0
        else:
            ymid = src.row_bottom if y2 > y1 else src.row_top
        return [QPointF(x1, y1), QPointF(x1 + ROUTE_GAP, y1), QPointF(x1 + ROUTE_GAP, ymid),
                QPointF(x2 - ROUTE_GAP, ymid), QPointF(x2 - ROUTE_GAP, y2), QPointF(x2, y2)]

    def _draw_links(self, model: SequenceModel) -> None:
        for task in model.tasks:
            dst = self._bars.get(task.id)
            if dst is None:
                continue
            for kind, preds in ((FS, task.predecessors_fs), (SS, task.predecessors_ss)):
                for pred_id in preds:
                    src = self._bars.get(pred_id)
                    if src is None:
                        continue
                    arrow = DependencyArrow(pred_id, task.id, kind, self._theme)
                    self.addItem(arrow)
                    arrow.set_points(self._route(kind, src, dst))

    # -- mouse -----------------------------------------------------------------------------------------------------
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        for view in self.views():
            view.setFocus()
        if event.button() != Qt.MouseButton.LeftButton or self.is_linking():
            return
        bars = [i for i in self.selectedItems() if isinstance(i, TaskBarItem)]
        self._selected_task_id = bars[0].task.id if bars else None
        self.task_clicked.emit(bars[0].task if bars else None)


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------
class GanttView(QGraphicsView):
    task_clicked = pyqtSignal(object)
    task_resized = pyqtSignal(str, float)
    dependency_added = pyqtSignal(str, str, str)
    dependency_removed = pyqtSignal(str, str, str)
    link_hint = pyqtSignal(str)

    def __init__(self, theme: Theme = DARK, parent=None):
        super().__init__(parent)
        self._scene = GanttScene(theme)
        self.setScene(self._scene)
        self._scene.task_clicked.connect(self.task_clicked)
        self._scene.task_resized.connect(self.task_resized)
        self._scene.dependency_added.connect(self.dependency_added)
        self._scene.dependency_removed.connect(self.dependency_removed)
        self._scene.link_hint.connect(self.link_hint)
        self._scene.rebuilt.connect(self._on_rebuilt)

        self._fit_mode = True
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(40)
        self._fit_timer.timeout.connect(self._apply_fit)

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setBackgroundBrush(QBrush(QColor(theme.gantt_bg)))

    # -- API ----------------------------------------------------------------------------------------------
    def set_link_validator(self, fn: Callable[[str, str, str], Tuple[bool, str]]) -> None:
        self._scene.link_validator = fn

    def set_theme(self, theme: Theme) -> None:
        self.setBackgroundBrush(QBrush(QColor(theme.gantt_bg)))
        self._scene.set_theme(theme)

    def load_model(self, model: Optional[SequenceModel]) -> None:
        self._scene.set_model(model)
        if self._fit_mode:
            self._apply_fit()

    def select_task(self, task_id: Optional[str]) -> None:
        self._scene.select_task(task_id)

    def zoom_by(self, factor: float) -> None:
        self._fit_mode = False
        self._scene.set_zoom(self._scene.get_zoom() * factor)

    def reset_zoom(self) -> None:
        self._fit_mode = False
        self._scene.set_zoom(DEFAULT_PX_S)

    def fit_to_window(self) -> None:
        self._fit_mode = True
        self._apply_fit()

    # -- internals --------------------------------------------------------------------------------------------
    def _apply_fit(self) -> None:
        avail = self.viewport().width() - self._scene.label_width - 12
        secs = self._scene.content_seconds
        if avail > 0 and secs > 0:
            self._scene.set_zoom(avail / secs)

    def _on_rebuilt(self) -> None:
        self._sync_sticky()
        QTimer.singleShot(0, self._sync_sticky)

    def _sync_sticky(self) -> None:
        top_left = self.mapToScene(0, 0)
        self._scene.update_sticky(max(0.0, top_left.x()), max(0.0, top_left.y()))

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self._sync_sticky()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_mode:
            self._fit_timer.start()
        self._sync_sticky()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_by(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            arrows = [i for i in self._scene.selectedItems() if isinstance(i, DependencyArrow)]
            for a in arrows:
                a.request_delete()
            if arrows:
                event.accept()
                return
        elif key == Qt.Key.Key_Escape and self._scene.is_linking():
            self._scene.cancel_linking()
            event.accept()
            return
        super().keyPressEvent(event)
