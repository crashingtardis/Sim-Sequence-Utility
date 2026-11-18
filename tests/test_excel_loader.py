"""
tests/test_excel_loader.py — Tests for the Excel input template parser.
"""

from pathlib import Path
import pytest
import openpyxl
from openpyxl import Workbook

from sim_sequence.excel_loader import load_excel, load_timing_matrix_excel


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

def test_load_excel_happy_path(tmp_path):
    path = _make_workbook(tmp_path)
    model = load_excel(path)

    assert model.settings.available_time == 3600.0
    assert model.settings.takt_time == 60.0
    assert model.settings.time_increment == 1.0

    assert len(model.resources) == 1
    assert model.resources[0].id == "Operator_1"
    assert model.resources[0].color == "#1F4E78"

    assert len(model.tasks) == 1
    assert model.tasks[0].id == "T1"
    assert model.tasks[0].duration == 5.0
    assert model.tasks[0].predecessors_fs == []
    assert model.tasks[0].predecessors_ss == []


def test_load_excel_predecessors(tmp_path):
    tasks = [
        ("T1", "Task 1", "Operator_1", 4, "", ""),
        ("T2", "Task 2", "Operator_1", 5, "T1", ""),
        ("T3", "Task 3", "Operator_1", 2, "T1, T2", "T1"),
    ]
    path = _make_workbook(tmp_path, tasks=tasks)
    model = load_excel(path)

    assert model.tasks[1].predecessors_fs == ["T1"]
    assert model.tasks[2].predecessors_fs == ["T1", "T2"]
    assert model.tasks[2].predecessors_ss == ["T1"]


def test_load_excel_skips_blank_and_comment_rows(tmp_path):
    tasks = [
        ("#comment", "comment", "Operator_1", 0, "", ""),
        (None, None, None, None, None, None),
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


# ---------------------------------------------------------------------------
# Legacy timing matrix sheet tests
# ---------------------------------------------------------------------------

def test_load_timing_matrix_excel(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # Header at row 12
    ws.cell(12, 4, "resource")
    ws.cell(12, 5, "start int")
    ws.cell(12, 7, " task description")
    ws.cell(12, 20, "time")
    ws.cell(12, 23, "end int")

    # Row 13: Operator 1 task 1
    ws.cell(13, 2, "a")
    ws.cell(13, 3, 1)
    ws.cell(13, 4, "Operator 1")
    ws.cell(13, 5, "n/a")
    ws.cell(13, 7, "Load part")
    ws.cell(13, 20, 5)
    ws.cell(13, 23, "a1")

    # Row 14: Geo Tool 1 task 1
    ws.cell(14, 2, "b")
    ws.cell(14, 3, 1)
    ws.cell(14, 4, "Geo Tool 1")
    ws.cell(14, 5, "a1")
    ws.cell(14, 7, "Clamp part")
    ws.cell(14, 20, 2)
    ws.cell(14, 23, "b1")

    path = tmp_path / "timing_matrix.xlsx"
    wb.save(str(path))

    # Test direct load
    model = load_timing_matrix_excel(path)
    assert len(model.resources) == 2
    assert len(model.tasks) == 2
    assert model.tasks[1].predecessors_fs == ["a1"]

    # Test auto-dispatch load
    model_auto = load_excel(path)
    assert len(model_auto.tasks) == 2
    assert model_auto.tasks[0].id == "a1"
