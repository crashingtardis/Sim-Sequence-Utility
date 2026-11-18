"""
make_template.py — Generates a formatted Excel input template.

Usage
-----
    python make_template.py                           # → inputs/sequence_template.xlsx
    python make_template.py --output my_template.xlsx
    python make_template.py --blank                   # headers only, no example data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl
from openpyxl import Workbook
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Side
)
from openpyxl.utils import get_column_letter


# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------
HDR_FILL   = PatternFill("solid", fgColor="1F4E78")   # dark blue
HDR_FONT   = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
HDR_ALIGN  = Alignment(horizontal="center", vertical="center", wrap_text=True)

KEY_FILL   = PatternFill("solid", fgColor="D6E4F0")   # light blue
KEY_FONT   = Font(bold=True, name="Calibri", size=10)

VAL_FONT   = Font(name="Calibri", size=10)
VAL_ALIGN  = Alignment(horizontal="left", vertical="center")

THIN_SIDE  = Side(style="thin", color="BFBFBF")
THIN_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)

NOTE_FONT  = Font(italic=True, color="808080", name="Calibri", size=9)

# Resource colour palette (applied to Resources sheet swatch column)
PALETTE = ["#1F4E78", "#4CAF50", "#FF9800", "#9C27B0",
           "#F44336", "#00BCD4", "#795548", "#607D8B"]


# ---------------------------------------------------------------------------
# Example data (omitted when --blank)
# ---------------------------------------------------------------------------
EXAMPLE_SETTINGS = [
    ("available_time", 3600,   "Total time budget (seconds)"),
    ("takt_time",      60,     "Target cycle time / line rate (seconds)"),
    ("time_increment", 1,      "Grid column resolution on granular sheets (seconds)"),
    ("output_file",    "outputs/honda_seq_dev_111826.xlsx", "Path for the generated report"),
]

EXAMPLE_RESOURCES = [
    ("Operator_1",   "#1F4E78"),
    ("Robot_A",      "#4CAF50"),
    ("Robot_B",      "#FF9800"),
    ("Tool_Fixture", "#9C27B0"),
]

EXAMPLE_TASKS = [
    # ID               Name                        Resource       Dur  FS                  SS
    ("Op1_GetPart",   "Get Part from Rack",        "Operator_1",   4,  "",                 ""),
    ("Op1_Load",      "Load Part to Fixture",      "Operator_1",   5,  "Op1_GetPart",      ""),
    ("Op1_SafetyCheck","Safety Check / Clear Zone","Operator_1",   2,  "Op1_Load",         ""),
    ("Op1_Unload",    "Unload Finished Part",      "Operator_1",   4,  "RobA_Weld2, RobB_Weld2", ""),
    ("RobA_MoveIn",   "Robot A Move-In",           "Robot_A",      3,  "Op1_SafetyCheck",  ""),
    ("RobA_Weld1",    "Robot A — Weld Pass 1",     "Robot_A",     10,  "RobA_MoveIn",      ""),
    ("RobA_Reposition","Robot A — Reposition",     "Robot_A",      2,  "RobA_Weld1",       ""),
    ("RobA_Weld2",    "Robot A — Weld Pass 2",     "Robot_A",      8,  "RobA_Reposition",  ""),
    ("RobA_MoveOut",  "Robot A Move-Out",          "Robot_A",      3,  "RobA_Weld2",       ""),
    ("RobB_MoveIn",   "Robot B Move-In",           "Robot_B",      3,  "Op1_SafetyCheck",  ""),
    ("RobB_Weld1",    "Robot B — Weld Pass 1",     "Robot_B",     10,  "RobB_MoveIn",      "RobA_Weld1"),
    ("RobB_Reposition","Robot B — Reposition",     "Robot_B",      2,  "RobB_Weld1",       ""),
    ("RobB_Weld2",    "Robot B — Weld Pass 2",     "Robot_B",      8,  "RobB_Reposition",  "RobA_Weld2"),
    ("RobB_MoveOut",  "Robot B Move-Out",          "Robot_B",      3,  "RobB_Weld2",       ""),
    ("Fix_Clamp",     "Clamp Part",                "Tool_Fixture",  2,  "Op1_Load",         ""),
    ("Fix_Hold",      "Hold During Weld",          "Tool_Fixture", 24,  "Fix_Clamp",        ""),
    ("Fix_Unclamp",   "Unclamp Part",              "Tool_Fixture",  2,  "RobA_MoveOut, RobB_MoveOut", ""),
]


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_template(out_path: Path, blank: bool = False) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    _build_settings_sheet(wb,  blank)
    _build_resources_sheet(wb, blank)
    _build_tasks_sheet(wb,     blank)

    # Remove default empty sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    wb.save(str(out_path))
    return out_path.resolve()


# ---------------------------------------------------------------------------
# Settings sheet
# ---------------------------------------------------------------------------

def _build_settings_sheet(wb: Workbook, blank: bool) -> None:
    ws = wb.create_sheet("Settings")
    ws.sheet_view.showGridLines = False

    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 44
    ws.column_dimensions["C"].width = 44

    # Header row
    for col, text in enumerate(["Setting", "Value", "Notes"], start=1):
        c = ws.cell(row=1, column=col, value=text)
        c.font   = HDR_FONT
        c.fill   = HDR_FILL
        c.border = THIN_BORDER
        c.alignment = HDR_ALIGN
    ws.row_dimensions[1].height = 20

    rows = EXAMPLE_SETTINGS if not blank else [
        ("available_time", None, "Total time budget (seconds)"),
        ("takt_time",      None, "Target cycle time / line rate (seconds)"),
        ("time_increment", None, "Grid column resolution on granular sheets (seconds)"),
        ("output_file",    None, "Path for the generated report"),
    ]

    for r, (key, val, note) in enumerate(rows, start=2):
        kc = ws.cell(row=r, column=1, value=key)
        kc.font = KEY_FONT; kc.fill = KEY_FILL; kc.border = THIN_BORDER

        vc = ws.cell(row=r, column=2, value=val)
        vc.font = VAL_FONT; vc.alignment = VAL_ALIGN; vc.border = THIN_BORDER

        nc = ws.cell(row=r, column=3, value=note)
        nc.font = NOTE_FONT; nc.border = THIN_BORDER

    ws.freeze_panes = "A2"


# ---------------------------------------------------------------------------
# Resources sheet
# ---------------------------------------------------------------------------

def _build_resources_sheet(wb: Workbook, blank: bool) -> None:
    ws = wb.create_sheet("Resources")
    ws.sheet_view.showGridLines = False

    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 10   # swatch

    for col, text in enumerate(["ID", "Color (hex)", "Preview"], start=1):
        c = ws.cell(row=1, column=col, value=text)
        c.font = HDR_FONT; c.fill = HDR_FILL
        c.border = THIN_BORDER; c.alignment = HDR_ALIGN
    ws.row_dimensions[1].height = 20

    data = EXAMPLE_RESOURCES if not blank else []
    for r, (rid, colour) in enumerate(data, start=2):
        ic = ws.cell(row=r, column=1, value=rid)
        ic.font = VAL_FONT; ic.border = THIN_BORDER

        cc = ws.cell(row=r, column=2, value=colour)
        cc.font = VAL_FONT; cc.border = THIN_BORDER

        # Visual colour swatch
        hex_clean = colour.lstrip("#")
        sw = ws.cell(row=r, column=3, value="")
        sw.fill   = PatternFill("solid", fgColor=hex_clean)
        sw.border = THIN_BORDER

    # Note row
    note_row = max(len(data) + 2, 2) + 1
    nc = ws.cell(row=note_row, column=1,
                 value="# Add one row per resource. Color is optional (hex e.g. #4CAF50).")
    nc.font = NOTE_FONT

    ws.freeze_panes = "A2"


# ---------------------------------------------------------------------------
# Tasks sheet
# ---------------------------------------------------------------------------

def _build_tasks_sheet(wb: Workbook, blank: bool) -> None:
    ws = wb.create_sheet("Tasks")
    ws.sheet_view.showGridLines = False

    col_widths = [18, 28, 16, 10, 36, 36]
    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    headers = ["ID", "Name", "Resource", "Duration (s)",
               "Predecessors_FS\n(comma-separated)", "Predecessors_SS\n(comma-separated)"]
    ws.row_dimensions[1].height = 36

    for col, text in enumerate(headers, start=1):
        c = ws.cell(row=1, column=col, value=text)
        c.font = HDR_FONT; c.fill = HDR_FILL
        c.border = THIN_BORDER; c.alignment = HDR_ALIGN

    # Alternating row fills
    FILL_A = PatternFill("solid", fgColor="FFFFFF")
    FILL_B = PatternFill("solid", fgColor="F5F9FF")

    data = EXAMPLE_TASKS if not blank else []
    for r, row_data in enumerate(data, start=2):
        fill = FILL_A if r % 2 == 0 else FILL_B
        for col, val in enumerate(row_data, start=1):
            c = ws.cell(row=r, column=col, value=val)
            c.font = VAL_FONT; c.fill = fill; c.border = THIN_BORDER
            c.alignment = Alignment(horizontal="left", vertical="center")

    # Notes row
    note_row = max(len(data) + 2, 2) + 1
    for col, note in enumerate([
        "# Task IDs must be unique",
        "# Human-readable label",
        "# Must match a Resources ID",
        "# Positive number",
        "# e.g. Task_A, Task_B",
        "# e.g. Task_X",
    ], start=1):
        nc = ws.cell(row=note_row, column=col, value=note)
        nc.font = NOTE_FONT

    ws.freeze_panes = "A2"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Generate a formatted Excel input template for the Sim-Sequence Utility."
    )
    p.add_argument("--output", "-o", type=Path,
                   default=Path("inputs/sequence_template.xlsx"),
                   help="Destination path (default: inputs/sequence_template.xlsx)")
    p.add_argument("--blank", action="store_true",
                   help="Emit headers only — no example data rows.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    out  = build_template(args.output, blank=args.blank)
    label = "blank" if args.blank else "pre-filled"
    print(f"Template ({label}) written → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
