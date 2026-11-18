"""
tests/test_sample_data.py — Tests for the built-in sample sequence.
"""

from sim_sequence.sample_data import get_sample_sequence
from sim_sequence.scheduler import schedule


def test_get_sample_sequence_structure():
    model = get_sample_sequence()
    assert len(model.resources) == 6
    assert len(model.tasks) == 22
    assert model.settings.takt_time == 60.0

    res_ids = [r.id for r in model.resources]
    assert "Operator 1" in res_ids
    assert "Geo Tool 1" in res_ids
    assert "Robot 1 (Geo Weld)" in res_ids
    assert "Robot 2 (Geo Weld)" in res_ids
    assert "Robot 3 (MH)" in res_ids
    assert "Unload Conveyor" in res_ids


def test_sample_sequence_schedules_cleanly():
    model = get_sample_sequence()
    scheduled = schedule(model)
    assert all(t.is_scheduled() for t in scheduled.tasks)

    cycle_t = max(t.end_time for t in scheduled.tasks)
    assert cycle_t == 65.0
    assert cycle_t > scheduled.settings.takt_time  # Over-takt sample
