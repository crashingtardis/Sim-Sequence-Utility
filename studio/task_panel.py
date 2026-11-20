"""
task_panel.py — Resources and Tasks editors.

Both panels are views over a shared :class:`ProjectStore`.  Cells that refer
to other rows use dropdown delegates that are rebuilt from the store every
time they open, so newly added resources / tasks are always selectable:

  * Task ▸ Resource            single-select dropdown of all resources
  * Task ▸ FS / SS predecessors multi-select (checkable) dropdown of all
                               tasks that can legally be a predecessor
                               (never itself, never something that would
                               create a circular dependency)
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import (QAbstractTableModel, QEvent, QModelIndex, Qt,
                          QTimer, pyqtSignal)
from PyQt6.QtGui import (QColor, QKeySequence, QPainter, QPen, QShortcut,
                         QStandardItem, QStandardItemModel)
from PyQt6.QtWidgets import (QAbstractItemDelegate, QAbstractItemView,
                             QColorDialog, QComboBox, QHBoxLayout,
                             QHeaderView, QLabel, QMessageBox, QPushButton,
                             QStyledItemDelegate, QTableView, QVBoxLayout,
                             QWidget)

from .project_store import ProjectStore
from .theme import contrast_color

_ROW_H = 28
_DANGER = QColor("#E74C3C")
_NO_HINT = QAbstractItemDelegate.EndEditHint.NoHint


# ---------------------------------------------------------------------------
# Delegates
# ---------------------------------------------------------------------------
class ColourSwatchDelegate(QStyledItemDelegate):
    """Paints the colour column as a rounded swatch with its hex code."""

    def paint(self, painter, option, index):
        hex_color = index.data(Qt.ItemDataRole.DisplayRole)
        if not (hex_color and str(hex_color).startswith("#")):
            super().paint(painter, option, index)
            return
        color = QColor(hex_color)
        rect = option.rect.adjusted(4, 3, -4, -3)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(QPen(QColor(0, 0, 0, 70)))
        painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(contrast_color(color))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(hex_color).upper())
        painter.restore()


class ResourceComboDelegate(QStyledItemDelegate):
    """Dropdown of every resource currently defined in the project."""

    def __init__(self, store: ProjectStore, parent=None):
        super().__init__(parent)
        self._store = store

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(self._store.resource_ids())
        combo.activated.connect(lambda _i, c=combo: self._finish(c))
        QTimer.singleShot(0, lambda c=combo: self._open_popup(c))
        return combo

    @staticmethod
    def _open_popup(combo):
        try:
            combo.showPopup()
        except RuntimeError:      # editor already destroyed
            pass

    def _finish(self, combo):
        self.commitData.emit(combo)
        self.closeEditor.emit(combo, _NO_HINT)

    def setEditorData(self, editor, index):
        current = str(index.data(Qt.ItemDataRole.EditRole) or "")
        pos = editor.findText(current)
        if pos < 0 and current:                  # dangling reference: keep it visible
            editor.insertItem(0, current)
            pos = 0
        editor.setCurrentIndex(max(pos, 0))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class CheckableComboBox(QComboBox):
    """A combo box whose popup items are tick-boxes; the popup stays open
    while ticking so several items can be chosen in one go."""

    popupClosed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.view().setItemDelegate(QStyledItemDelegate(self.view()))   # draws the tick-boxes
        self.view().pressed.connect(self._toggle)
        self.view().viewport().installEventFilter(self)
        self._model.itemChanged.connect(lambda _i: self._update_text())

    def set_items(self, items: List[str], checked: List[str]) -> None:
        self._model.blockSignals(True)
        self._model.clear()
        for text in items:
            item = QStandardItem(text)
            item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.Checked if text in checked else Qt.CheckState.Unchecked)
            self._model.appendRow(item)
        self._model.blockSignals(False)
        self._update_text()

    def checked_items(self) -> List[str]:
        out = []
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(item.text())
        return out

    def _toggle(self, index):
        item = self._model.itemFromIndex(index)
        if item is not None:
            item.setCheckState(Qt.CheckState.Unchecked
                               if item.checkState() == Qt.CheckState.Checked
                               else Qt.CheckState.Checked)

    def _update_text(self):
        self.lineEdit().setText(", ".join(self.checked_items()))

    def eventFilter(self, obj, event):
        # Swallow the release so the popup doesn't close after each tick.
        if obj is self.view().viewport() and event.type() == QEvent.Type.MouseButtonRelease:
            return True
        return super().eventFilter(obj, event)

    def hidePopup(self):
        super().hidePopup()
        self.popupClosed.emit()


class PredecessorDelegate(QStyledItemDelegate):
    """Multi-select dropdown of tasks that may be a predecessor of this row."""

    def __init__(self, store: ProjectStore, parent=None):
        super().__init__(parent)
        self._store = store

    def createEditor(self, parent, option, index):
        combo = CheckableComboBox(parent)
        combo._finished = False
        combo.popupClosed.connect(lambda c=combo: self._finish(c))
        QTimer.singleShot(0, lambda c=combo: self._open_popup(c))
        return combo

    @staticmethod
    def _open_popup(combo):
        try:
            combo.showPopup()
        except RuntimeError:
            pass

    def _finish(self, combo):
        if getattr(combo, "_finished", True):
            return
        combo._finished = True
        self.commitData.emit(combo)
        self.closeEditor.emit(combo, _NO_HINT)

    def setEditorData(self, editor, index):
        current = [p.strip() for p in str(index.data(Qt.ItemDataRole.EditRole) or "").split(",") if p.strip()]
        candidates = self._store.candidate_predecessors(index.row())
        extras = [c for c in current if c not in candidates]     # keep unknown refs visible
        editor.set_items(candidates + extras, current)

    def setModelData(self, editor, model, index):
        model.setData(index, ", ".join(editor.checked_items()), Qt.ItemDataRole.EditRole)


# ---------------------------------------------------------------------------
# Table models (thin views over the store)
# ---------------------------------------------------------------------------
class _StoreModel(QAbstractTableModel):
    rejected = pyqtSignal(str)

    def __init__(self, store: ProjectStore, parent=None):
        super().__init__(parent)
        self._store = store
        store.structure_changed.connect(self._on_structure)
        store.data_changed.connect(self._on_data)

    def _on_structure(self):
        self.beginResetModel()
        self.endResetModel()

    def _on_data(self):
        if self.rowCount():
            self.dataChanged.emit(self.index(0, 0),
                                  self.index(self.rowCount() - 1, self.columnCount() - 1))


class ResourceTableModel(_StoreModel):
    COLUMNS = ["Resource ID", "Colour"]

    def rowCount(self, _=QModelIndex()):
        return len(self._store.resources)

    def columnCount(self, _=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        res = self._store.resources[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return res.id if index.column() == 0 else (res.color or "")
        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 1:
            return "Double-click to change colour"
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole or index.column() != 0:
            return False
        ok, msg = self._store.rename_resource(index.row(), str(value))
        if not ok:
            self.rejected.emit(msg)
        return ok

    def flags(self, index):
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return base | Qt.ItemFlag.ItemIsEditable if index.column() == 0 else base


class TaskTableModel(_StoreModel):
    COLUMNS = ["ID", "Name", "Resource", "Duration (s)", "FS Predecessors", "SS Predecessors"]
    HEADER_TIPS = [
        "Unique task ID",
        "Description shown on the Gantt bar",
        "Resource that performs this task (dropdown)",
        "Duration in seconds",
        "Finish-to-Start: this task starts after ALL of these finish (dropdown, multi-select)",
        "Start-to-Start: this task starts no earlier than these start (dropdown, multi-select)",
    ]

    def rowCount(self, _=QModelIndex()):
        return len(self._store.tasks)

    def columnCount(self, _=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self.COLUMNS[section]
            if role == Qt.ItemDataRole.ToolTipRole:
                return self.HEADER_TIPS[section]
        return None

    def _text(self, task, col):
        return [task.id, task.name, task.resource, f"{task.duration:g}",
                ", ".join(task.predecessors_fs), ", ".join(task.predecessors_ss)][col]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        task = self._store.tasks[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.EditRole:
            return self._text(task, col)
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 2 and not task.resource:
                return "\u26a0 unassigned"
            return self._text(task, col)
        if role == Qt.ItemDataRole.ForegroundRole and col == 2:
            if task.resource not in self._store.resource_ids():
                return _DANGER
        if role == Qt.ItemDataRole.ToolTipRole:
            if col == 2 and task.resource not in self._store.resource_ids():
                return "This task has no valid resource, so it is not shown on the Gantt. Pick one from the dropdown."
            return self._text(task, col) or None
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        row, col, st = index.row(), index.column(), self._store
        text = str(value).strip()
        ok, msg = True, ""
        if col == 0:
            ok, msg = st.rename_task(row, text)
        elif col == 1:
            st.set_task_name(row, text)
        elif col == 2:
            st.set_task_resource(row, text)
        elif col == 3:
            ok, msg = st.set_task_duration(row, text)
        elif col in (4, 5):
            ids = [p.strip() for p in text.split(",") if p.strip()]
            st.set_task_predecessors(row, "FS" if col == 4 else "SS", ids)
        if not ok and msg:
            self.rejected.emit(msg)
        return ok

    def flags(self, index):
        return (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------
def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("SectionLabel")
    return lbl


def _button(text: str, name: str = "") -> QPushButton:
    btn = QPushButton(text)
    if name:
        btn.setObjectName(name)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _style_table(view: QTableView) -> None:
    view.setAlternatingRowColors(True)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                         | QAbstractItemView.EditTrigger.SelectedClicked
                         | QAbstractItemView.EditTrigger.EditKeyPressed
                         | QAbstractItemView.EditTrigger.AnyKeyPressed)
    view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    view.setWordWrap(False)
    view.setTextElideMode(Qt.TextElideMode.ElideRight)
    view.verticalHeader().setVisible(False)
    view.verticalHeader().setDefaultSectionSize(_ROW_H)
    view.horizontalHeader().setStretchLastSection(True)
    view.horizontalHeader().setHighlightSections(False)


def _delete_shortcut(view: QTableView, slot) -> None:
    sc = QShortcut(QKeySequence("Delete"), view)
    sc.setContext(Qt.ShortcutContext.WidgetShortcut)
    sc.activated.connect(slot)


class ResourcePanel(QWidget):
    """Editor for the Resources list."""
    message = pyqtSignal(str)

    def __init__(self, store: ProjectStore, parent=None):
        super().__init__(parent)
        self._store = store
        self._model = ResourceTableModel(store, self)
        self._model.rejected.connect(self.message)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(_section_label("Resources"))

        self._view = QTableView()
        self._view.setModel(self._model)
        _style_table(self._view)
        hdr = self._view.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.resizeSection(1, 96)
        self._view.setItemDelegateForColumn(1, ColourSwatchDelegate(self._view))
        self._view.doubleClicked.connect(self._on_double_click)
        _delete_shortcut(self._view, self._remove)
        layout.addWidget(self._view, stretch=1)

        row = QHBoxLayout()
        row.setSpacing(6)
        btn_add, btn_col, btn_rem = _button("+ Add", "addBtn"), _button("Colour\u2026"), _button("\u2212 Remove", "removeBtn")
        btn_add.clicked.connect(self._add)
        btn_col.clicked.connect(self._pick_colour_for_current)
        btn_rem.clicked.connect(self._remove)
        for b in (btn_add, btn_col, btn_rem):
            row.addWidget(b)
        row.addStretch()
        layout.addLayout(row)

    def _current_row(self) -> int:
        idx = self._view.currentIndex()
        return idx.row() if idx.isValid() else -1

    def _add(self):
        row = self._store.add_resource()
        self._view.selectRow(row)
        self._view.scrollTo(self._model.index(row, 0))
        self.message.emit("Resource added \u2014 it is now available in every task's Resource dropdown.")

    def _remove(self):
        row = self._current_row()
        if row < 0:
            return
        n = self._store.tasks_using_resource(row)
        if n:
            rid = self._store.resources[row].id
            reply = QMessageBox.question(
                self, "Remove resource",
                f"'{rid}' is used by {n} task(s). They will become unassigned.\n\nRemove it anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._store.remove_resource(row)
        count = self._model.rowCount()
        if count:
            self._view.selectRow(min(row, count - 1))

    def _on_double_click(self, index: QModelIndex):
        if index.column() == 1:
            self._pick_colour(index.row())

    def _pick_colour_for_current(self):
        row = self._current_row()
        if row >= 0:
            self._pick_colour(row)

    def _pick_colour(self, row: int):
        current = self._store.resources[row].color or "#FFFFFF"
        color = QColorDialog.getColor(QColor(current), self, "Pick resource colour")
        if color.isValid():
            self._store.set_resource_color(row, color.name())


class TaskPanel(QWidget):
    """Editor for the Tasks list."""
    message = pyqtSignal(str)
    task_selected = pyqtSignal(str)

    def __init__(self, store: ProjectStore, parent=None):
        super().__init__(parent)
        self._store = store
        self._model = TaskTableModel(store, self)
        self._model.rejected.connect(self.message)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(_section_label("Tasks"))

        self._view = QTableView()
        self._view.setModel(self._model)
        _style_table(self._view)
        hdr = self._view.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for col, width in enumerate((90, 160, 120, 90, 130, 130)):
            hdr.resizeSection(col, width)
        self._view.setItemDelegateForColumn(2, ResourceComboDelegate(self._store, self._view))
        self._view.setItemDelegateForColumn(4, PredecessorDelegate(self._store, self._view))
        self._view.setItemDelegateForColumn(5, PredecessorDelegate(self._store, self._view))
        self._view.selectionModel().currentRowChanged.connect(self._on_current_row)
        _delete_shortcut(self._view, self._remove)
        layout.addWidget(self._view, stretch=1)

        row = QHBoxLayout()
        row.setSpacing(6)
        btn_add, btn_rem = _button("+ Add Task", "addBtn"), _button("\u2212 Remove", "removeBtn")
        btn_add.clicked.connect(self._add)
        btn_rem.clicked.connect(self._remove)
        row.addWidget(btn_add)
        row.addWidget(btn_rem)
        row.addStretch()
        layout.addLayout(row)

    def _on_current_row(self, current: QModelIndex, _previous: QModelIndex):
        if current.isValid() and current.row() < len(self._store.tasks):
            self.task_selected.emit(self._store.tasks[current.row()].id)

    def _add(self):
        row = self._store.add_task()
        self._view.selectRow(row)
        self._view.scrollTo(self._model.index(row, 0))

    def _remove(self):
        idx = self._view.currentIndex()
        if not idx.isValid():
            return
        row = idx.row()
        self._store.remove_task(row)
        count = self._model.rowCount()
        if count:
            self._view.selectRow(min(row, count - 1))

    def select_task(self, task_id: Optional[str]):
        row = self._store.row_of_task(task_id) if task_id else -1
        if row >= 0:
            self._view.selectRow(row)
            self._view.scrollTo(self._model.index(row, 0))
