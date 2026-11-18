"""
tests/test_embedder.py — Unit tests for the Python source code embedding system.
"""

from pathlib import Path
from sim_sequence.embedder import collect_sources, source_rows, _EMBED_FILES


def test_collect_sources_includes_all_modules():
    sources = collect_sources()
    paths = [rel for rel, _ in sources]

    for expected in _EMBED_FILES:
        assert expected in paths, f"Expected {expected} to be in embedded sources"


def test_collect_sources_content_not_empty():
    sources = collect_sources()
    for rel, content in sources:
        assert len(content.strip()) > 0, f"Embedded file {rel} is empty"


def test_source_rows_format():
    sample_sources = [
        ("test_mod.py", "line1\nline2\n"),
        ("sub/mod2.py", "foo = 1\n"),
    ]
    rows = source_rows(sample_sources)

    # First row should be file header
    assert rows[0] == ("test_mod.py", "")
    assert rows[1] == ("", "line1")
    assert rows[2] == ("", "line2")
    # Next file
    assert rows[3] == ("sub/mod2.py", "")
    assert rows[4] == ("", "foo = 1")
