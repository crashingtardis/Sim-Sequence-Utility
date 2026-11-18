"""
tests/test_excel_loader.py — Tests for the Excel input template parser.
"""

from pathlib import Path
import pytest
import openpyxl
from openpyxl import Workbook

from sim_sequence.excel_loader import load_excel


# ---------------------------------------------------------------------------
# Helpers — build a minimal in-memory workbook and save to tmp_path
# ---------------------------------------------------------------------------

def _make_workbook(tmp_path: Path,
                   settings=None, resources=None, tasks=None) -> Path:
    wb = Workbook()
    del wb["Sheet"]  # remove default sheet

    # Settings
    ws_s = wb.create_sheet("Settings")
    ws_s.append(["Setting", "Value", "Notes"])
    for row in (settings or [
        ("available_time", 3600,  ""),
        ("takt_time",      60,    ""),
        ("time_increment", 1,     ""),
        ("output_file",    "outputs/test.xlsx", ""),
    ]):
        ws_s.append(list(row))

    # Resources
    ws_r = wb.create_sheet("Resources")
    ws_r.append(["ID", "Color"])
    for row in (resources or [("Operator_1", "#1F4E78")]):
        ws_r.append(list(row))

    # Tasks
    ws_t = wb.create_sheet("Tasks")
    ws_t.append(["ID", "Name", "Resource", "Duration", "Predecessors_FS", "Predecessors_SS"])
    for row in (tasks or [
        ("T1", "Task One", "Operator_1", 5, "", ""),
    ]):
        ws_t.append(list(row))

    out = tmp_path / "test_input.xlsx"
    wb.save(str(out))
    return out


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_basic_load(tmp_path):
    path  = _make_workbook(tmp_path)
    model = load_excel(path)

    assert model.settings.available_time == 3600
    assert model.settings.takt_time      == 60
    assert model.settings.time_increment == 1
    assert len(model.resources) == 1
    assert model.resources[0].id == "Operator_1"
    assert len(model.tasks) == 1
    assert model.tasks[0].id == "T1"
    assert model.tasks[0].duration == 5.0


def test_predecessors_parsed(tmp_path):
    tasks = [
        ("A", "Task A", "Operator_1", 5,  "",     ""),
        ("B", "Task B", "Operator_1", 3,  "A",    ""),
        ("C", "Task C", "Operator_1", 2,  "A, B", "A"),
    ]
    model = load_excel(_make_workbook(tmp_path, tasks=tasks))

    b = model.task_by_id("B")
    assert b.predecessors_fs == ["A"]
    assert b.predecessors_ss == []

    c = model.task_by_id("C")
    assert c.predecessors_fs == ["A", "B"]
    assert c.predecessors_ss == ["A"]


def test_blank_rows_skipped(tmp_path):
    tasks = [
        ("T1", "Task 1", "Operator_1", 5, "", ""),
        (None, None, None, None, None, None),   # blank row — should be skipped
        ("T2", "Task 2", "Operator_1", 3, "T1", ""),
    ]
    model = load_excel(_make_workbook(tmp_path, tasks=tasks))
    assert len(model.tasks) == 2


def test_comment_rows_skipped(tmp_path):
    tasks = [
        ("# This is a comment", "", "", "", "", ""),
        ("T1", "Task 1", "Operator_1", 5, "", ""),
    ]
    model = load_excel(_make_workbook(tmp_path, tasks=tasks))
    assert len(model.tasks) == 1


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------

def test_missing_sheet_raises(tmp_path):
    wb = Workbook()
    wb.create_sheet("Settings")
    wb.create_sheet("Resources")
    # Tasks sheet intentionally omitted
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    path = tmp_path / "bad.xlsx"
    wb.save(str(path))
    with pytest.raises(ValueError, match="Tasks"):
        load_excel(path)


def test_missing_setting_key_raises(tmp_path):
    settings = [
        ("available_time", 3600, ""),
        # takt_time intentionally omitted
        ("time_increment", 1,    ""),
        ("output_file",    "out.xlsx", ""),
    ]
    path = _make_workbook(tmp_path, settings=settings)
    with pytest.raises(ValueError, match="takt_time"):
        load_excel(path)
