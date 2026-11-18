"""
scheduler.py — DAG-based task scheduler using NetworkX.

Implements the two dependency types defined in the spec:
  - Finish-to-Start  (FS): B.start  >= A.end
  - Start-to-Start   (SS): B.start  >= A.start

Algorithm
---------
1. Build a directed graph where each node is a Task and each edge
   encodes the dependency type.
2. Topologically sort the graph (raises if a cycle is detected).
3. Walk the sorted order, computing start/end times greedily.
"""

from __future__ import annotations

from typing import Dict

import networkx as nx

from .models import SequenceModel, Task


_FS = "FS"
_SS = "SS"


def schedule(model: SequenceModel) -> SequenceModel:
    """
    Compute ``start_time`` / ``end_time`` for every task in *model*
    **in-place** and return the model for convenience.

    Raises
    ------
    ValueError
        If the dependency graph contains a cycle.
    KeyError
        If a predecessor ID is not found in the task list.
    """
    task_map: Dict[str, Task] = {t.id: t for t in model.tasks}

    # -- 1. Build the directed graph --------------------------------------
    G = nx.DiGraph()
    G.add_nodes_from(task_map.keys())

    for task in model.tasks:
        for pred_id in task.predecessors_fs:
            _assert_known(pred_id, task_map, task.id)
            G.add_edge(pred_id, task.id, dep=_FS)
        for pred_id in task.predecessors_ss:
            _assert_known(pred_id, task_map, task.id)
            G.add_edge(pred_id, task.id, dep=_SS)

    # -- 2. Topological sort ---------------------------------------------
    try:
        order = list(nx.topological_sort(G))
    except nx.NetworkXUnfeasible as exc:
        raise ValueError("Dependency graph contains a cycle.") from exc

    # -- 3. Compute times ------------------------------------------------
    for task_id in order:
        task = task_map[task_id]

        earliest_start = 0.0

        for pred_id, _, data in G.in_edges(task_id, data=True):
            pred = task_map[pred_id]
            if data["dep"] == _FS:
                # Must wait until predecessor finishes
                earliest_start = max(earliest_start, pred.end_time)
            else:  # SS
                # Must start no earlier than predecessor starts
                earliest_start = max(earliest_start, pred.start_time)

        task.start_time = earliest_start
        task.end_time = earliest_start + task.duration

    return model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_known(pred_id: str, task_map: Dict[str, Task], owner_id: str) -> None:
    if pred_id not in task_map:
        raise KeyError(
            f"Task '{owner_id}' references unknown predecessor '{pred_id}'."
        )
