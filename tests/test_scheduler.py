"""
tests/test_scheduler.py — Unit tests for the DAG scheduling engine.
"""

import pytest
from sim_sequence.models import GlobalSettings, Resource, SequenceModel, Task
from sim_sequence.scheduler import schedule


def _make_model(tasks):
    settings = GlobalSettings(available_time=3600, takt_time=60)
    return SequenceModel(settings=settings, resources=[], tasks=tasks)


# ---------------------------------------------------------------------------
# Basic scheduling
# ---------------------------------------------------------------------------

def test_single_task_starts_at_zero():
    model = _make_model([Task("A", "Task A", "R1", duration=5)])
    schedule(model)
    t = model.task_by_id("A")
    assert t.start_time == 0.0
    assert t.end_time == 5.0


def test_finish_to_start_chain():
    tasks = [
        Task("A", "A", "R1", duration=5),
        Task("B", "B", "R1", duration=3, predecessors_fs=["A"]),
    ]
    schedule(_make_model(tasks))
    assert tasks[1].start_time == 5.0
    assert tasks[1].end_time == 8.0


def test_start_to_start_interlock():
    tasks = [
        Task("A", "A", "R1", duration=10),
        Task("B", "B", "R2", duration=4, predecessors_ss=["A"]),
    ]
    schedule(_make_model(tasks))
    # B starts at same time as A
    assert tasks[1].start_time == 0.0
    assert tasks[1].end_time == 4.0


def test_multiple_predecessors_takes_max():
    tasks = [
        Task("A", "A", "R1", duration=5),
        Task("B", "B", "R2", duration=3),
        Task("C", "C", "R3", duration=2, predecessors_fs=["A", "B"]),
    ]
    schedule(_make_model(tasks))
    # C must wait for the later of A.end (5) and B.end (3)
    assert tasks[2].start_time == 5.0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_cycle_raises_value_error():
    tasks = [
        Task("A", "A", "R1", duration=5, predecessors_fs=["B"]),
        Task("B", "B", "R1", duration=3, predecessors_fs=["A"]),
    ]
    with pytest.raises(ValueError, match="cycle"):
        schedule(_make_model(tasks))


def test_unknown_predecessor_raises_key_error():
    tasks = [Task("A", "A", "R1", duration=5, predecessors_fs=["GHOST"])]
    with pytest.raises(KeyError):
        schedule(_make_model(tasks))
