"""
project_store.py — Single source of truth for the project being edited.

The Settings / Resources / Tasks panels, their dropdown delegates and the
Gantt are all views over this one object, so anything added, renamed or
removed here shows up everywhere (e.g. a new resource immediately appears in
every task's Resource dropdown, and renaming a task rewrites every
predecessor list that mentions it).

The rules themselves live in ``sim_sequence.graph_ops`` (pure Python, unit
tested); this class only adds Qt change notification.

Signals
-------
structure_changed  rows were added / removed / the whole model was replaced
data_changed       cell values changed (rows unchanged)
edited             the user changed something (drives dirty flag + auto-run)
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

from sim_sequence import graph_ops
from sim_sequence.models import GlobalSettings, Resource, SequenceModel, Task

from .theme import RESOURCE_PALETTE


class ProjectStore(QObject):
    structure_changed = pyqtSignal()
    data_changed = pyqtSignal()
    edited = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = GlobalSettings(available_time=3600, takt_time=60)
        self.resources: List[Resource] = []
        self.tasks: List[Task] = []

    # -- whole model -------------------------------------------------------------
    def load(self, model: SequenceModel) -> None:
        self.settings = model.settings
        self.resources = list(model.resources)
        self.tasks = list(model.tasks)
        self.structure_changed.emit()

    def to_model(self) -> SequenceModel:
        """A SequenceModel sharing this store's Task / Resource objects."""
        return SequenceModel(self.settings, list(self.resources), list(self.tasks))

    # -- lookups -------------------------------------------------------------------
    def resource_ids(self) -> List[str]:
        return [r.id for r in self.resources]

    def task_ids(self) -> List[str]:
        return [t.id for t in self.tasks]

    def row_of_task(self, task_id: str) -> int:
        for i, t in enumerate(self.tasks):
            if t.id == task_id:
                return i
        return -1

    def candidate_predecessors(self, row: int) -> List[str]:
        return graph_ops.candidate_predecessors(self.tasks, self.tasks[row].id)

    def check_link(self, src_id: str, dst_id: str, dep_type: str) -> Tuple[bool, str]:
        return graph_ops.check_link(self.tasks, src_id, dst_id, dep_type)

    # -- notification ----------------------------------------------------------------
    def _notify(self, structure: bool = False) -> None:
        (self.structure_changed if structure else self.data_changed).emit()
        self.edited.emit()

    # -- resources -------------------------------------------------------------------
    def add_resource(self) -> int:
        rid = graph_ops.unique_id("Resource", self.resource_ids())
        color = RESOURCE_PALETTE[len(self.resources) % len(RESOURCE_PALETTE)]
        self.resources.append(Resource(id=rid, color=color))
        self._notify(structure=True)
        return len(self.resources) - 1

    def tasks_using_resource(self, row: int) -> int:
        return graph_ops.tasks_on_resource(self.tasks, self.resources[row].id)

    def remove_resource(self, row: int) -> int:
        """Remove a resource; its tasks become unassigned.  Returns how many."""
        rid = self.resources[row].id
        n = graph_ops.unassign_resource(self.tasks, rid)
        del self.resources[row]
        self._notify(structure=True)
        return n

    def rename_resource(self, row: int, new: str) -> Tuple[bool, str]:
        res = self.resources[row]
        new = new.strip()
        ok, msg = graph_ops.validate_id(new, self.resource_ids(), current=res.id)
        if not ok:
            return False, msg
        if new != res.id:
            graph_ops.rename_resource(self.tasks, res.id, new)
            res.id = new
            self._notify()
        return True, ""

    def set_resource_color(self, row: int, color: str) -> None:
        self.resources[row].color = color
        self._notify()

    # -- tasks -------------------------------------------------------------------------
    def add_task(self) -> int:
        tid = graph_ops.unique_id("Task", self.task_ids())
        resource = self.resources[0].id if self.resources else ""
        self.tasks.append(Task(id=tid, name=tid.replace("_", " "), resource=resource, duration=5.0))
        self._notify(structure=True)
        return len(self.tasks) - 1

    def remove_task(self, row: int) -> None:
        graph_ops.remove_task(self.tasks, self.tasks[row].id)
        self._notify(structure=True)

    def rename_task(self, row: int, new: str) -> Tuple[bool, str]:
        task = self.tasks[row]
        new = new.strip()
        ok, msg = graph_ops.validate_id(new, self.task_ids(), current=task.id)
        if not ok:
            return False, msg
        if new != task.id:
            graph_ops.rename_task(self.tasks, task.id, new)
            self._notify()
        return True, ""

    def set_task_name(self, row: int, name: str) -> None:
        self.tasks[row].name = name.strip() or self.tasks[row].id
        self._notify()

    def set_task_resource(self, row: int, resource_id: str) -> None:
        self.tasks[row].resource = resource_id
        self._notify()

    def set_task_duration(self, row: int, value) -> Tuple[bool, str]:
        try:
            dur = float(value)
        except (TypeError, ValueError):
            return False, "Duration must be a number."
        if not (dur >= 0) or dur == float("inf"):
            return False, "Duration must be zero or greater."
        self.tasks[row].duration = dur
        self._notify()
        return True, ""

    def set_duration_by_id(self, task_id: str, duration: float) -> None:
        row = self.row_of_task(task_id)
        if row >= 0:
            self.set_task_duration(row, duration)

    def set_task_predecessors(self, row: int, dep_type: str, ids: List[str]) -> None:
        """Replace one predecessor list, silently dropping invalid entries."""
        task = self.tasks[row]
        current = task.predecessors_fs if dep_type == graph_ops.FS else task.predecessors_ss
        allowed = set(self.candidate_predecessors(row)) | set(current)
        cleaned: List[str] = []
        for i in ids:
            if i in allowed and i not in cleaned:
                cleaned.append(i)
        if dep_type == graph_ops.FS:
            task.predecessors_fs = cleaned
        else:
            task.predecessors_ss = cleaned
        self._notify()

    # -- dependencies (Gantt) ------------------------------------------------------------
    def add_dependency(self, src_id: str, dst_id: str, dep_type: str) -> Tuple[bool, str]:
        ok, msg = graph_ops.add_dependency(self.tasks, src_id, dst_id, dep_type)
        if ok:
            self._notify()
        return ok, msg

    def remove_dependency(self, src_id: str, dst_id: str, dep_type: str) -> bool:
        if graph_ops.remove_dependency(self.tasks, src_id, dst_id, dep_type):
            self._notify()
            return True
        return False
