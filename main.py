"""
main.py — CLI entry point for the Sim-Sequence Utility.

Usage
-----
    python main.py inputs/sequence_template.xlsx
    python main.py inputs/sequence_template.xlsx --output outputs/my_report.xlsx
    python main.py inputs/example_sequence.yaml   # YAML still supported
"""

from __future__ import annotations

import argparse
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

from sim_sequence.scheduler import schedule
from sim_sequence.reporter import generate_report


def _load(path: Path):
    """Route to the correct loader based on file extension."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm", ".xls"):
        from sim_sequence.excel_loader import load_excel
        return load_excel(path)
    elif suffix in (".yaml", ".yml"):
        from sim_sequence.loader import load_yaml
        return load_yaml(path)
    else:
        raise ValueError(
            f"Unsupported input format '{suffix}'. "
            "Use an .xlsx template or a .yaml file."
        )


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Generate an interactive Excel sequence report from an input file."
    )
    p.add_argument(
        "input", type=Path,
        help="Path to the input file (.xlsx template or .yaml).",
    )
    p.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Override the output .xlsx path (defaults to value in input settings).",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if not args.input.exists():
        print(f"ERROR: input file not found: {args.input}", file=sys.stderr)
        return 1

    fmt = "Excel" if args.input.suffix.lower() in (".xlsx", ".xlsm", ".xls") else "YAML"
    print(f"[1/3] Loading sequence definition ({fmt}): {args.input}")
    try:
        model = _load(args.input)
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"      {len(model.tasks)} tasks, {len(model.resources)} resources.")

    print("[2/3] Scheduling tasks...")
    try:
        schedule(model)
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("[3/3] Generating Excel report...")
    out = generate_report(model, output_path=args.output)
    print(f"      Saved -> {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
