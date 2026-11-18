"""
tests/test_loader.py — Tests for YAML input parsing.
"""

import textwrap
from pathlib import Path
import pytest
from sim_sequence.loader import load_yaml


YAML_CONTENT = textwrap.dedent("""\
    settings:
      available_time: 3600
      takt_time: 60
      time_increment: 1
      output_file: outputs/test.xlsx

    resources:
      - id: Operator_1
        color: "#1F4E78"

    tasks:
      - id: Op1_Load
        name: Load Part
        resource: Operator_1
        duration: 5
        predecessors_fs: []
        predecessors_ss: []
""")


def test_load_yaml(tmp_path: Path):
    yaml_file = tmp_path / "seq.yaml"
    yaml_file.write_text(YAML_CONTENT)
    model = load_yaml(yaml_file)

    assert model.settings.takt_time == 60
    assert len(model.resources) == 1
    assert model.resources[0].id == "Operator_1"
    assert len(model.tasks) == 1
    assert model.tasks[0].duration == 5.0
