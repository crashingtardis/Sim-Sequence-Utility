"""
main_embedded.py — Entry point invoked by the VBA macro inside the standalone .xlsm.

The VBA extracts this file (and the sim_sequence package) to a temp directory,
then shells out:
    py <tmpdir>\main_embedded.py "<path_to_caller.xlsm>"

The script reads all input from the calling workbook itself, so no separate
input files are needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure UTF-8 output even when redirected to file or non-UTF-8 console on Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ensure the temp directory's sim_sequence package is importable
sys.path.insert(0, str(Path(__file__).parent))

from sim_sequence.excel_loader import load_excel
from sim_sequence.scheduler import schedule
from sim_sequence.reporter import generate_report


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: main_embedded.py <path_to_workbook.xlsm>", file=sys.stderr)
        return 1

    wb_path = Path(sys.argv[1])
    if not wb_path.exists():
        print(f"ERROR: workbook not found: {wb_path}", file=sys.stderr)
        return 1

    print(f"[1/3] Reading input from: {wb_path.name}")
    try:
        model = load_excel(wb_path)
    except Exception as exc:
        print(f"ERROR loading workbook: {exc}", file=sys.stderr)
        return 1
    print(f"      {len(model.tasks)} tasks, {len(model.resources)} resources.")

    print("[2/3] Scheduling tasks...")
    try:
        schedule(model)
    except Exception as exc:
        print(f"ERROR scheduling: {exc}", file=sys.stderr)
        return 1

    print("[3/3] Generating report...")
    import json
    import tempfile

    temp_dir = Path(tempfile.gettempdir()) / "SimSeq"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_report_path = temp_dir / "temp_report.xlsx"

    generate_report(model, output_path=temp_report_path)
    print(f"      Report generated -> {temp_report_path}")

    # Write execution summary metadata for the Excel VBA macro
    cycle_time = max((t.end_time for t in model.tasks), default=0.0)
    meta = {
        "cycle_time": cycle_time,
        "takt_time": model.settings.takt_time,
        "tasks_count": len(model.tasks),
        "resources_count": len(model.resources),
        "sheets": ["Overall_Sequence"] + [r.id for r in model.resources],
    }
    (temp_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
