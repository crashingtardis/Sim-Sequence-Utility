"""
excel_loader.py — Parses Excel sequence files and returns a SequenceModel.

Supports:
  1. Standard 3-sheet template (Settings / Resources / Tasks)
  2. Original Honda sequence sheet (honda_seq_dev_111826.xlsx) with
     resource definitions, sequential task items, and cross-resource interlocks.
"""

from __future__ import annotations

import re
import sys
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

# Distinct brand colors for Honda sheet resources
HONDA_DEFAULT_COLORS = {
    "operator 1":       "#1F4E78",   # Navy Blue
    "geo tool 1":       "#9C27B0",   # Purple
    "rbt 1 (geo weld)": "#4CAF50",   # Green
    "rbt 2 (geo weld)": "#FF9800",   # Orange
    "rbt 3 (mh)":       "#00BCD4",   # Cyan
    "unload conv":      "#795548",   # Brown
}


def load_excel(path: str | Path) -> SequenceModel:
    """Parse an Excel input file and return a :class:`SequenceModel`.

    Automatically detects whether the file is a standard 3-sheet template
    or an original Honda sequence sheet.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path}")

    wb = openpyxl.load_workbook(str(path), data_only=True)

    # If the standard Settings sheet is absent, check for Honda sheet format
    if _SHEET_SETTINGS not in wb.sheetnames:
        if _is_honda_format(wb):
            return load_honda_excel(path)
        _assert_sheet(wb, _SHEET_SETTINGS, path)

    _assert_sheet(wb, _SHEET_SETTINGS,  path)
    _assert_sheet(wb, _SHEET_RESOURCES, path)
    _assert_sheet(wb, _SHEET_TASKS,     path)

    settings  = _parse_settings(wb[_SHEET_SETTINGS],  path)
    resources = _parse_resources(wb[_SHEET_RESOURCES], path)
    tasks     = _parse_tasks(wb[_SHEET_TASKS],         path)

    return SequenceModel(settings=settings, resources=resources, tasks=tasks)


def _is_honda_format(wb: openpyxl.Workbook) -> bool:
    """Check if any worksheet contains the signature header of the Honda sequence sheet."""
    for ws in wb.worksheets:
        for r in range(1, min(25, ws.max_row + 1)):
            row_vals = [
                str(ws.cell(r, c).value or "").strip().lower()
                for c in range(1, min(15, ws.max_column + 1))
            ]
            if "start int" in row_vals or ("resource" in row_vals and any("task description" in v or "item" in v for v in row_vals)):
                return True
    return False


def load_honda_excel(path: str | Path) -> SequenceModel:
    """Parse the original Honda automation sequence sheet (e.g. honda_seq_dev_111826.xlsx)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Honda Excel file not found: {path}")

    wb = openpyxl.load_workbook(str(path), data_only=True)
    ws = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb.active

    resources_dict: Dict[str, str] = {}
    raw_tasks: List[Dict[str, Any]] = []
    cur_res_code: Optional[str] = None
    cur_res_name: Optional[str] = None

    for r in range(13, ws.max_row + 1):
        res_code = ws.cell(r, 2).value    # Column B (e.g. 'a', 'b', 'c', ...)
        item_num = ws.cell(r, 3).value    # Column C (Item #)
        res_name = ws.cell(r, 4).value    # Column D (Resource name)
        start_int = ws.cell(r, 5).value   # Column E (Start interlock)
        desc = ws.cell(r, 7).value        # Column G (Task description)
        dur = ws.cell(r, 20).value        # Column T (Duration seconds)
        if dur is None:
            dur = ws.cell(r, 21).value    # Column U (Fallback duration)
        end_int = ws.cell(r, 23).value    # Column W (End interlock)

        if res_code:
            cur_res_code = str(res_code).strip().lower()
        if res_name:
            cur_res_name = str(res_name).strip()
            resources_dict[cur_res_code] = cur_res_name

        if item_num is not None and desc is not None:
            raw_tasks.append({
                "res_code": cur_res_code,
                "res_name": cur_res_name,
                "item": int(item_num),
                "desc": str(desc).strip(),
                "duration": float(dur) if dur is not None else 0.0,
                "start_int": str(start_int).strip() if start_int else "",
                "end_int": str(end_int).strip() if end_int else f"{cur_res_code}{item_num}",
            })

    # Build Resource models with dedicated colors
    resources = [
        Resource(id=name, color=HONDA_DEFAULT_COLORS.get(name.lower(), "#607D8B"))
        for name in resources_dict.values()
    ]

    res_code_to_name = {code: name for code, name in resources_dict.items()}

    tasks: List[Task] = []
    for rt in raw_tasks:
        tid = f"{rt['res_code']}{rt['item']}"
        res_name = res_code_to_name.get(rt["res_code"], rt["res_name"])
        predecessors_fs: List[str] = []

        # 1. Intra-resource sequential flow (item k depends on item k-1)
        if rt["item"] > 1:
            prev_tid = f"{rt['res_code']}{rt['item'] - 1}"
            predecessors_fs.append(prev_tid)

        # 2. Cross-resource start interlocks
        raw_int = rt["start_int"].lower()
        if raw_int and raw_int != "n/a":
            tokens = [t.strip() for t in re.split(r"[,/]+", raw_int) if t.strip()]
            for tok in tokens:
                # Normalize reverse tokens like '4d' -> 'd4'
                m = re.match(r"^(\d+)([a-zA-Z]+)$", tok)
                if m:
                    tok = f"{m.group(2)}{m.group(1)}"
                # Exclude inter-cycle loopbacks that span across cycle boundaries
                if tid == "a1" and tok == "e2":
                    continue
                if tid == "e4" and tok == "f1":
                    continue
                if tok != tid and tok not in predecessors_fs:
                    predecessors_fs.append(tok)

        tasks.append(Task(
            id=tid,
            name=rt["desc"],
            resource=res_name,
            duration=rt["duration"],
            predecessors_fs=predecessors_fs,
            predecessors_ss=[],
        ))

    settings = GlobalSettings(
        available_time=3600.0,
        takt_time=60.0,
        time_increment=1.0,
        output_file="outputs/honda_seq_dev_111826.xlsx",
    )

    return SequenceModel(settings=settings, resources=resources, tasks=tasks)


def get_honda_sample_path() -> Path:
    """Locate the original Honda sequence Excel file across dev and frozen environments."""
    filename = "honda_seq_dev_111826.xlsx"

    # PyInstaller frozen bundle lookup
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_inputs = Path(sys._MEIPASS) / "inputs" / filename
        if meipass_inputs.exists():
            return meipass_inputs
        meipass_root = Path(sys._MEIPASS) / filename
        if meipass_root.exists():
            return meipass_root

    # Source workspace lookup
    root = Path(__file__).parent.parent
    p1 = root / "inputs" / filename
    if p1.exists():
        return p1
    p2 = root / filename
    if p2.exists():
        return p2
    p3 = Path.cwd() / "inputs" / filename
    if p3.exists():
        return p3
    p4 = Path.cwd() / filename
    if p4.exists():
        return p4

    return p1


# ---------------------------------------------------------------------------
# Standard 3-sheet template parsers
# ---------------------------------------------------------------------------

def _parse_settings(ws: Worksheet, path: Path) -> GlobalSettings:
    """Expect two columns:  A = key,  B = value."""
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
    """Expect columns:  A = ID,  B = Color (optional hex string)."""
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
    """Expected columns: A: ID, B: Name, C: Resource, D: Duration, E: Predecessors_FS, F: Predecessors_SS."""
    tasks: List[Task] = []
    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
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
