"""
task_panel.py — Left-panel tree: Resources and Tasks editor.

Provides:
  - ResourceModel / TaskModel table models for editing
  - ResourcePanel (QWidget with Add/Remove/colour-pick)
  - TaskPanel    (QWidget with Add/Remove/predecessor combos)
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import (Qt, QAbstractTableModel, QModelIndex,
                           pyqtSignal, QVariant)
from PyQt6.QtGui import QColor, QBrush, QFont, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableView, QHeaderView, QAbstractItemView, QColorDialog,
    QLabel, QSizePolicy, QFrame, QStyledItemDelegate,
    QMessageBox,
)

from sim_sequence.models import Resource, Task
from .theme import COMAU_RED, SILVER, WHITE, RESOURCE_PALETTE


# ---------------------------------------------------------------------------
# Colour swatch delegate
# ---------------------------------------------------------------------------
class ColourSwatchDelegate(QStyledItemDelegate):
    """Renders a coloured rectangle for the colour column."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        hex_color = index.data(Qt.ItemDataRole.DisplayRole)
        if hex_color and hex_color.startswith("#"):
            rect = option.rect.adjusted(6, 4, -6, -4)
            painter.fillRect(rect, QColor(hex_color))


# ---------------------------------------------------------------------------
# Resource table model
# ---------------------------------------------------------------------------
class ResourceTableModel(QAbstractTableModel):
    COLUMNS = ["ID", "Color"]

    def __init__(self, resources: List[Resource], parent=None):
        super().__init__(parent)
        self._data: List[Resource] = list(resources)

    def rowCount(self, _=QModelIndex()): return len(self._data)
    def columnCount(self, _=QModelIndex()): return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        r = self._data[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return [r.id, r.color or ""][index.column()]
        if role == Qt.ItemDataRole.BackgroundRole and index.column() == 1:
            if r.color: return QBrush(QColor(r.color))
        if role == Qt.ItemDataRole.ForegroundRole:
            return QBrush(QColor(WHITE))
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole: return False
        r = self._data[index.row()]
        if index.column() == 0:
            r.id = str(value).strip()
        elif index.column() == 1:
            r.color = str(value).strip()
        self.dataChanged.emit(index, index)
        return True

    def flags(self, index):
        base = super().flags(index)
        if index.column() == 0:
            return base | Qt.ItemFlag.ItemIsEditable
        return base  # colour edited via dialog

    def resources(self) -> List[Resource]:
        return list(self._data)

    def add_resource(self):
        idx = len(self._data)
        default_color = RESOURCE_PALETTE[idx % len(RESOURCE_PALETTE)]
        self.beginInsertRows(QModelIndex(), idx, idx)
        self._data.append(Resource(id=f"Resource_{idx+1}", color=default_color))
        self.endInsertRows()

    def remove_resource(self, row: int):
        if 0 <= row < len(self._data):
            self.beginRemoveRows(QModelIndex(), row, row)
            del self._data[row]
            self.endRemoveRows()

    def set_color(self, row: int, color: str):
        if 0 <= row < len(self._data):
            self._data[row].color = color
            idx = self.index(row, 1)
            self.dataChanged.emit(idx, idx)


# ---------------------------------------------------------------------------
# Task table model
# ---------------------------------------------------------------------------
class TaskTableModel(QAbstractTableModel):
    COLUMNS = ["ID", "Name", "Resource", "Duration (s)", "FS Predecessors", "SS Predecessors"]

    def __init__(self, tasks: List[Task], parent=None):
        super().__init__(parent)
        self._data: List[Task] = list(tasks)

    def rowCount(self, _=QModelIndex()): return len(self._data)
    def columnCount(self, _=QModelIndex()): return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        t = self._data[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return [
                t.id, t.name, t.resource,
                str(t.duration),
                ", ".join(t.predecessors_fs),
                ", ".join(t.predecessors_ss),
            ][col]
        if role == Qt.ItemDataRole.ForegroundRole:
            return QBrush(QColor(WHITE))
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole: return False
        t = self._data[index.row()]
        col = index.column()
        v = str(value).strip()
        if col == 0: t.id = v
        elif col == 1: t.name = v
        elif col == 2: t.resource = v
        elif col == 3:
            try: t.duration = float(v)
            except ValueError: return False
        elif col == 4: t.predecessors_fs = [p.strip() for p in v.split(",") if p.strip()]
        elif col == 5: t.predecessors_ss = [p.strip() for p in v.split(",") if p.strip()]
        self.dataChanged.emit(index, index)
        return True

    def flags(self, index):
        return super().flags(index) | Qt.ItemFlag.ItemIsEditable

    def tasks(self) -> List[Task]:
        return list(self._data)

    def add_task(self):
        idx = len(self._data)
        self.beginInsertRows(QModelIndex(), idx, idx)
        self._data.append(Task(id=f"Task_{idx+1}", name=f"Task {idx+1}", resource="", duration=5.0))
        self.endInsertRows()

    def remove_task(self, row: int):
        if 0 <= row < len(self._data):
            self.beginRemoveRows(QModelIndex(), row, row)
            del self._data[row]
            self.endRemoveRows()

    def highlight_task(self, task_id: Optional[str]):
        """Highlight the row matching task_id."""
        pass  # visual feedback handled by selection on the view


# ---------------------------------------------------------------------------
# Panel widgets
# ---------------------------------------------------------------------------
def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #B0BAC4; font-size: 9pt; font-weight: bold; "
        "letter-spacing: 1px; text-transform: uppercase; padding: 6px 0 2px 0;"
    )
    return lbl


def _small_btn(text: str, color: str = "#1A2E40") -> QPushButton:
    btn = QPushButton(text)
    btn.setFixedHeight(26)
    btn.setStyleSheet(
        f"background:{color}; color:white; border:none; border-radius:3px;"
        f"padding: 2px 10px; font-size:9pt;"
    )
    return btn


class ResourcePanel(QWidget):
    """Editor for the Resources list."""
    changed = pyqtSignal()

    def __init__(self, resources: List[Resource], parent=None):
        super().__init__(parent)
        self._model = ResourceTableModel(resources)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(_section_label("Resources"))

        self._view = QTableView()
        self._view.setModel(self._model)
        self._view.setAlternatingRowColors(True)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._view.horizontalHeader().resizeSection(1, 70)
        self._view.setItemDelegateForColumn(1, ColourSwatchDelegate())
        self._view.doubleClicked.connect(self._on_double_click)
        self._view.setFixedHeight(130)
        layout.addWidget(self._view)

        btn_row = QHBoxLayout()
        btn_add = _small_btn("+ Add", "#1F4E78")
        btn_rem = _small_btn("− Remove", "#5D2020")
        btn_add.clicked.connect(self._add)
        btn_rem.clicked.connect(self._remove)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_rem)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _add(self):
        self._model.add_resource()
        self.changed.emit()

    def _remove(self):
        idx = self._view.currentIndex()
        if idx.isValid():
            self._model.remove_resource(idx.row())
            self.changed.emit()

    def _on_double_click(self, index: QModelIndex):
        if index.column() == 1:
            cur = self._model.resources()[index.row()].color or "#FFFFFF"
            color = QColorDialog.getColor(QColor(cur), self, "Pick Resource Color")
            if color.isValid():
                self._model.set_color(index.row(), color.name())
                self.changed.emit()

    def resources(self) -> List[Resource]:
        return self._model.resources()

    def set_resources(self, resources: List[Resource]):
        self._model = ResourceTableModel(resources)
        self._view.setModel(self._model)


class TaskPanel(QWidget):
    """Editor for the Tasks list."""
    changed = pyqtSignal()

    def __init__(self, tasks: List[Task], parent=None):
        super().__init__(parent)
        self._model = TaskTableModel(tasks)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(_section_label("Tasks"))

        self._view = QTableView()
        self._view.setModel(self._model)
        self._view.setAlternatingRowColors(True)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hdr = self._view.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(0, 110)
        hdr.resizeSection(1, 150)
        hdr.resizeSection(2, 100)
        hdr.resizeSection(3, 80)
        hdr.resizeSection(4, 120)
        hdr.resizeSection(5, 120)
        self._view.verticalHeader().setVisible(False)
        layout.addWidget(self._view)

        btn_row = QHBoxLayout()
        btn_add = _small_btn("+ Add Task", "#1F4E78")
        btn_rem = _small_btn("− Remove", "#5D2020")
        btn_add.clicked.connect(self._add)
        btn_rem.clicked.connect(self._remove)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_rem)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _add(self):
        self._model.add_task()
        self.changed.emit()

    def _remove(self):
        idx = self._view.currentIndex()
        if idx.isValid():
            self._model.remove_task(idx.row())
            self.changed.emit()

    def tasks(self) -> List[Task]:
        return self._model.tasks()

    def set_tasks(self, tasks: List[Task]):
        self._model = TaskTableModel(tasks)
        self._view.setModel(self._model)

    def select_task(self, task_id: Optional[str]):
        for row in range(self._model.rowCount()):
            if self._model.tasks()[row].id == task_id:
                self._view.selectRow(row)
                return
