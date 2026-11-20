"""
graph_ops.py — Pure helpers for editing the task / resource graph.

Everything here is plain Python (no Qt) so it can be unit-tested and reused
by the CLI as well as the desktop studio.  The studio's ``ProjectStore`` is a
thin Qt wrapper around these functions.

Conventions
-----------
* "FS" = Finish-to-Start, "SS" = Start-to-Start.
* A dependency ``src -> dst`` means *dst* lists *src* as a predecessor.
* Functions that can fail return ``(ok, message)``; ``message`` is a short,
  user-presentable explanation (empty when ``ok`` is True).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .models import Task

FS = "FS"
SS = "SS"
DEP_TYPES = (FS, SS)


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------
def unique_id(prefix: str, existing: Iterable[str]) -> str:
    """Return ``prefix_N`` with the smallest N >= 1 that is not in *existing*."""
    taken = set(existing)
    n = 1
    while f"{prefix}_{n}" in taken:
        n += 1
    return f"{prefix}_{n}"


def validate_id(new: str, existing: Iterable[str], current: Optional[str] = None) -> Tuple[bool, str]:
    """Check that *new* is usable as a task / resource ID."""
    new = (new or "").strip()
    if not new:
        return False, "ID cannot be empty."
    if "," in new:
        return False, "IDs cannot contain commas."
    if new != current and new in set(existing):
        return False, f"'{new}' already exists."
    return True, ""


# ---------------------------------------------------------------------------
# Dependency graph queries
# ---------------------------------------------------------------------------
def _all_preds(task: Task) -> Set[str]:
    return set(task.predecessors_fs) | set(task.predecessors_ss)


def descendants(tasks: Sequence[Task], task_id: str) -> Set[str]:
    """All tasks that (transitively) depend on *task_id*."""
    succ: Dict[str, Set[str]] = {}
    for t in tasks:
        for p in _all_preds(t):
            succ.setdefault(p, set()).add(t.id)

    seen: Set[str] = set()
    stack = [task_id]
    while stack:
        cur = stack.pop()
        for nxt in succ.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def candidate_predecessors(tasks: Sequence[Task], task_id: str) -> List[str]:
    """IDs that may safely be added as a predecessor of *task_id*.

    Excludes the task itself and anything that already depends on it
    (adding those would create a cycle).  Order follows the task list.
    """
    blocked = descendants(tasks, task_id) | {task_id}
    return [t.id for t in tasks if t.id not in blocked]


def check_link(tasks: Sequence[Task], src_id: str, dst_id: str, dep_type: str) -> Tuple[bool, str]:
    """Would adding ``src -> dst`` be valid?  (Does not modify anything.)"""
    if dep_type not in DEP_TYPES:
        return False, f"Unknown dependency type '{dep_type}'."
    by_id = {t.id: t for t in tasks}
    if src_id not in by_id or dst_id not in by_id:
        return False, "Both tasks must exist."
    if src_id == dst_id:
        return False, "A task cannot depend on itself."
    dst = by_id[dst_id]
    existing = dst.predecessors_fs if dep_type == FS else dst.predecessors_ss
    if src_id in existing:
        return False, f"{src_id} \u2192 {dst_id} ({dep_type}) already exists."
    if src_id in descendants(tasks, dst_id):
        return False, f"{src_id} \u2192 {dst_id} would create a circular dependency."
    return True, ""


# ---------------------------------------------------------------------------
# Dependency edits
# ---------------------------------------------------------------------------
def add_dependency(tasks: Sequence[Task], src_id: str, dst_id: str, dep_type: str) -> Tuple[bool, str]:
    ok, msg = check_link(tasks, src_id, dst_id, dep_type)
    if not ok:
        return False, msg
    dst = next(t for t in tasks if t.id == dst_id)
    (dst.predecessors_fs if dep_type == FS else dst.predecessors_ss).append(src_id)
    return True, f"Added {dep_type} link {src_id} \u2192 {dst_id}."


def remove_dependency(tasks: Sequence[Task], src_id: str, dst_id: str, dep_type: str) -> bool:
    dst = next((t for t in tasks if t.id == dst_id), None)
    if dst is None:
        return False
    lst = dst.predecessors_fs if dep_type == FS else dst.predecessors_ss
    if src_id in lst:
        lst.remove(src_id)
        return True
    return False


# ---------------------------------------------------------------------------
# Renames / removals (keep references consistent)
# ---------------------------------------------------------------------------
def rename_task(tasks: Sequence[Task], old: str, new: str) -> None:
    """Rename task *old* to *new* and update every predecessor list."""
    for t in tasks:
        if t.id == old:
            t.id = new
        t.predecessors_fs = [new if p == old else p for p in t.predecessors_fs]
        t.predecessors_ss = [new if p == old else p for p in t.predecessors_ss]


def remove_task(tasks: List[Task], task_id: str) -> None:
    """Delete a task in place and strip it from all predecessor lists."""
    tasks[:] = [t for t in tasks if t.id != task_id]
    for t in tasks:
        t.predecessors_fs = [p for p in t.predecessors_fs if p != task_id]
        t.predecessors_ss = [p for p in t.predecessors_ss if p != task_id]


def rename_resource(tasks: Sequence[Task], old: str, new: str) -> int:
    """Point every task on resource *old* at *new*.  Returns tasks updated."""
    n = 0
    for t in tasks:
        if t.resource == old:
            t.resource = new
            n += 1
    return n


def tasks_on_resource(tasks: Sequence[Task], resource_id: str) -> int:
    return sum(1 for t in tasks if t.resource == resource_id)


def unassign_resource(tasks: Sequence[Task], resource_id: str) -> int:
    """Clear the resource on every task that used *resource_id*."""
    return rename_resource(tasks, resource_id, "")


# ---------------------------------------------------------------------------
# Layout helper for the Gantt
# ---------------------------------------------------------------------------
def assign_lanes(tasks: Sequence[Task]) -> Tuple[Dict[str, int], int]:
    """Stack overlapping tasks of one resource into sub-lanes.

    Returns ``({task_id: lane_index}, lane_count)``.  Tasks that do not
    overlap in time share lane 0.  Unscheduled tasks are ignored.
    """
    scheduled = [t for t in tasks if t.start_time is not None and t.end_time is not None]
    scheduled.sort(key=lambda t: (t.start_time, t.end_time))

    lane_ends: List[float] = []
    lanes: Dict[str, int] = {}
    for t in scheduled:
        for i, end in enumerate(lane_ends):
            if t.start_time >= end - 1e-9:
                lane_ends[i] = t.end_time
                lanes[t.id] = i
                break
        else:
            lane_ends.append(t.end_time)
            lanes[t.id] = len(lane_ends) - 1
    return lanes, max(1, len(lane_ends))


def nice_tick_step(px_per_s: float, min_px: float = 56.0) -> float:
    """Smallest 'round' time step whose on-screen width is >= *min_px*."""
    steps = (1, 2, 5, 10, 15, 20, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 14400)
    for s in steps:
        if s * px_per_s >= min_px:
            return float(s)
    return float(steps[-1])
