"""
models.py — Pure data classes for the scheduling domain.

All fields are plain Python types so the objects are trivially
serialisable and have no dependency on the scheduling or Excel layers.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GlobalSettings:
    """Project-level configuration."""
    available_time: float          # seconds (or whatever unit the user chooses)
    takt_time: float               # seconds per cycle (line rate)
    time_increment: float = 1.0   # column resolution on granular sheets (e.g. 0.1 or 1)
    output_file: str = "honda_seq_dev_111826.xlsx"


@dataclass
class Task:
    """A single unit of work assigned to one resource."""
    id: str
    name: str
    resource: str
    duration: float

    # Dependencies (by Task.id)
    predecessors_fs: List[str] = field(default_factory=list)   # Finish-to-Start
    predecessors_ss: List[str] = field(default_factory=list)   # Start-to-Start

    # Computed by the scheduler — do not set in the input file
    start_time: Optional[float] = field(default=None, init=True)
    end_time: Optional[float] = field(default=None, init=True)

    def is_scheduled(self) -> bool:
        return self.start_time is not None and self.end_time is not None


@dataclass
class Resource:
    """A named resource (operator, robot, fixture, …)."""
    id: str
    color: Optional[str] = None   # hex color for Gantt bars, e.g. "#1F4E78"


@dataclass
class SequenceModel:
    """Top-level container holding the full project definition."""
    settings: GlobalSettings
    resources: List[Resource]
    tasks: List[Task]

    # --- convenience look-ups -------------------------------------------

    def resource_by_id(self, resource_id: str) -> Optional[Resource]:
        return next((r for r in self.resources if r.id == resource_id), None)

    def tasks_for_resource(self, resource_id: str) -> List[Task]:
        return [t for t in self.tasks if t.resource == resource_id]

    def task_by_id(self, task_id: str) -> Optional[Task]:
        return next((t for t in self.tasks if t.id == task_id), None)
