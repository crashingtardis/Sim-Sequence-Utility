"""
loader.py — Parses the YAML input file and returns a SequenceModel.

Expected YAML shape (see inputs/example_sequence.yaml for a full sample):

    settings:
      available_time: 3600
      takt_time: 60
      time_increment: 1
      output_file: honda_seq_dev_111826.xlsx

    resources:
      - id: Operator_1
        color: "#1F4E78"
      - id: Robot_A
        color: "#4CAF50"

    tasks:
      - id: Op1_Load
        name: "Load Part"
        resource: Operator_1
        duration: 5
        predecessors_fs: []
        predecessors_ss: []
      - id: RobA_Weld1
        name: "Weld Pass 1"
        resource: Robot_A
        duration: 12
        predecessors_fs: [Op1_Load]
"""

from __future__ import annotations

import yaml
from pathlib import Path

from .models import GlobalSettings, Resource, SequenceModel, Task


def load_yaml(path: str | Path) -> SequenceModel:
    """Parse *path* (YAML) and return a fully constructed :class:`SequenceModel`."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    settings = GlobalSettings(**raw["settings"])

    resources = [Resource(**r) for r in raw.get("resources", [])]

    tasks = []
    for t in raw.get("tasks", []):
        tasks.append(
            Task(
                id=t["id"],
                name=t.get("name", t["id"]),
                resource=t["resource"],
                duration=float(t["duration"]),
                predecessors_fs=[str(p) for p in t.get("predecessors_fs", [])],
                predecessors_ss=[str(p) for p in t.get("predecessors_ss", [])],
            )
        )

    return SequenceModel(settings=settings, resources=resources, tasks=tasks)
