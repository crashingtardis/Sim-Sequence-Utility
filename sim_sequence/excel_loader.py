"""
excel_loader.py — Parses the Excel input template and returns a SequenceModel.

Expected workbook structure (3 sheets):

  ┌─────────────┐
  │  Settings   │  Key / Value pairs (see SETTINGS_KEYS)
  ├─────────────┤
  │  Resources  │  ID | Color
  ├─────────────┤
  │    Tasks    │  ID | Name | Resource | Duration | Predecessors_FS | Predecessors_SS
  └─────────────┘

Predecessors_FS and Predecessors_SS are comma-separated task IDs.
Any row whose first cell is empty or starts with '#' is treated as a comment
and skipped.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from .models import GlobalSettings, Resource, SequenceModel, Task


# ---------------------------------------------------------------------------
# Sheet / column names (case-insensitive comparison is used throughout)
# ---------------------------------------------------------------------------
_SHEET_SETTINGS  = "Settings"
_SHEET_RESOURCES = "Resources"
_SHEET_TASKS     = "Tasks"

_SETTINGS_REQUIRED_KEYS = {
    "available_time", "takt_time", "time_increment"
}


def load_excel(path: str | Path) -> SequenceModel:
    """Parse an Excel input template and return a :class:`SequenceModel`."""
    path = Path(path)
    wb   = openpyxl.load_workbook(str(path), data_only=True)

    _assert_sheet(wb, _SHEET_SETTINGS,  path)
    _assert_sheet(wb, _SHEET_RESOURCES, path)
    _assert_sheet(wb, _SHEET_TASKS,     path)

    settings  = _parse_settings(wb[_SHEET_SETTINGS],  path)
    resources = _parse_resources(wb[_SHEET_RESOURCES], path)
    tasks     = _parse_tasks(wb[_SHEET_TASKS],         path)

    return SequenceModel(settings=settings, resources=resources, tasks=tasks)


# ---------------------------------------------------------------------------
# Sheet parsers
# ---------------------------------------------------------------------------

def _parse_settings(ws: Worksheet, path: Path) -> GlobalSettings:
    """
    Expect two columns:  A = key,  B = value.
    Row 1 is treated as a header and skipped.
    """
    raw: Dict[str, Any] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        key, value = (row[0] if len(row) > 0 else None), (row[1] if len(row) > 1 else None)
        if _is_blank(key) or str(key).startswith("#"):
            continue
        raw[str(key).strip().lower()] = value

    missing = _SETTINGS_REQUIRED_KEYS - set(raw.keys())
    if missing:
        raise ValueError(
            f"Settings sheet in '{path.name}' is missing keys: {missing}"
        )

    out_file = str(raw.get("output_file") or "outputs/honda_seq_dev_111826.xlsx")

    return GlobalSettings(
        available_time = float(raw["available_time"]),
        takt_time      = float(raw["takt_time"]),
        time_increment = float(raw["time_increment"]),
        output_file    = out_file,
    )


def _parse_resources(ws: Worksheet, path: Path) -> List[Resource]:
    """
    Expect columns:  A = ID,  B = Color (optional hex string).
    Row 1 is treated as a header and skipped.
    """
    resources: List[Resource] = []
    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        rid   = row[0] if len(row) > 0 else None
        color = row[1] if len(row) > 1 else None

        if _is_blank(rid) or str(rid).startswith("#"):
            continue

        resources.append(Resource(
            id    = str(rid).strip(),
            color = str(color).strip() if not _is_blank(color) else None,
        ))

    if not resources:
        raise ValueError(f"Resources sheet in '{path.name}' has no data rows.")

    return resources


def _parse_tasks(ws: Worksheet, path: Path) -> List[Task]:
    """
    Expected columns (row 1 = header, skipped):
      A: ID
      B: Name
      C: Resource
      D: Duration
      E: Predecessors_FS   (comma-separated task IDs, may be blank)
      F: Predecessors_SS   (comma-separated task IDs, may be blank)
    """
    tasks: List[Task] = []
    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # Pad to 6 columns
        row = tuple(row) + (None,) * max(0, 6 - len(row))

        tid, name, resource, duration, pfs_raw, pss_raw = row[:6]

        if _is_blank(tid) or str(tid).startswith("#"):
            continue

        if _is_blank(resource):
            raise ValueError(
                f"Tasks sheet row {row_num}: task '{tid}' has no Resource."
            )
        if _is_blank(duration):
            raise ValueError(
                f"Tasks sheet row {row_num}: task '{tid}' has no Duration."
            )

        tasks.append(Task(
            id              = str(tid).strip(),
            name            = str(name).strip() if not _is_blank(name) else str(tid).strip(),
            resource        = str(resource).strip(),
            duration        = float(duration),
            predecessors_fs = _split_ids(pfs_raw),
            predecessors_ss = _split_ids(pss_raw),
        ))

    if not tasks:
        raise ValueError(f"Tasks sheet in '{path.name}' has no data rows.")

    return tasks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_blank(val: Any) -> bool:
    return val is None or str(val).strip() == ""


def _split_ids(raw: Any) -> List[str]:
    """Split a comma-separated cell value into a list of stripped IDs."""
    if _is_blank(raw):
        return []
    return [s.strip() for s in str(raw).split(",") if s.strip()]


def _assert_sheet(wb: openpyxl.Workbook, name: str, path: Path) -> None:
    if name not in wb.sheetnames:
        raise ValueError(
            f"Required sheet '{name}' not found in '{path.name}'. "
            f"Available sheets: {wb.sheetnames}"
        )
