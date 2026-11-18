"""
embedder.py — Collects the Python source files that need to be embedded
inside the standalone .xlsm workbook.

Returns a list of (relative_path, source_text) tuples, ordered so that
the reconstructed directory tree is importable.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

# Root of the project (parent of this file's directory)
_ROOT = Path(__file__).parent.parent

# Ordered list of files to embed (relative to _ROOT)
_EMBED_FILES = [
    "main_embedded.py",
    "sim_sequence/__init__.py",
    "sim_sequence/assets.py",
    "sim_sequence/models.py",
    "sim_sequence/loader.py",
    "sim_sequence/excel_loader.py",
    "sim_sequence/scheduler.py",
    "sim_sequence/reporter.py",
]


def collect_sources() -> List[Tuple[str, str]]:
    """
    Return ``[(relative_posix_path, source_text), ...]`` for every file
    that must be embedded in the standalone workbook.
    """
    result: List[Tuple[str, str]] = []
    for rel in _EMBED_FILES:
        full = _ROOT / rel
        if not full.exists():
            raise FileNotFoundError(f"Source file not found: {full}")
        source = full.read_text(encoding="utf-8")
        result.append((rel, source))
    return result


def source_rows(sources: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Flatten sources into a list of ``(col_A, col_B)`` pairs ready to be
    written row-by-row into the ``_py`` hidden sheet.

    Format:
      - File-header row:  col_A = relative path, col_B = ""
      - Content rows:     col_A = "",             col_B = source line
    """
    rows: List[Tuple[str, str]] = []
    for rel_path, text in sources:
        rows.append((rel_path, ""))            # file header
        for line in text.splitlines():
            rows.append(("", line))            # one row per source line
    return rows
