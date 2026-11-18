"""
test_cseq_io.py — Tests for .cseq JSON serializer and deserializer.
"""

import json
from pathlib import Path
import pytest

from sim_sequence.models import GlobalSettings, Resource, SequenceModel, Task
from sim_sequence.cseq_io import save_cseq, load_cseq


def test_roundtrip_cseq(tmp_path: Path):
    target = tmp_path / "test_sample.cseq"
    model = SequenceModel(
        settings=GlobalSettings(available_time=1200, takt_time=45.0, time_increment=0.5, output_file="out.xlsx"),
        resources=[
            Resource(id="Robot_1", color="#1F4E78"),
            Resource(id="Operator_1", color="#4CAF50"),
        ],
        tasks=[
            Task(id="T1", name="Part Pick", resource="Operator_1", duration=4.5),
            Task(id="T2", name="Weld Seam", resource="Robot_1", duration=12.0, predecessors_fs=["T1"]),
            Task(id="T3", name="Sync Check", resource="Robot_1", duration=2.0, predecessors_ss=["T2"]),
        ],
    )

    saved_path = save_cseq(model, target)
    assert saved_path.exists()
    assert saved_path.suffix == ".cseq"

    loaded = load_cseq(saved_path)
    assert loaded.settings.available_time == 1200
    assert loaded.settings.takt_time == 45.0
    assert loaded.settings.time_increment == 0.5
    assert len(loaded.resources) == 2
    assert loaded.resources[0].id == "Robot_1"
    assert loaded.resources[0].color == "#1F4E78"
    assert len(loaded.tasks) == 3
    assert loaded.tasks[1].predecessors_fs == ["T1"]
    assert loaded.tasks[2].predecessors_ss == ["T2"]


def test_load_cseq_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_cseq(tmp_path / "non_existent.cseq")


def test_auto_suffix(tmp_path: Path):
    target = tmp_path / "no_suffix_specified"
    model = SequenceModel(
        settings=GlobalSettings(available_time=100, takt_time=10),
        resources=[Resource(id="R1")],
        tasks=[Task(id="T1", name="T1", resource="R1", duration=1.0)],
    )
    saved = save_cseq(model, target)
    assert saved.name == "no_suffix_specified.cseq"
    assert saved.exists()
