"""
cseq_io.py — Native file format (.cseq) serializer and deserializer.

A .cseq file is a clean, structured JSON file that stores:
  - version
  - settings (available_time, takt_time, time_increment, output_file)
  - resources (id, color)
  - tasks (id, name, resource, duration, predecessors_fs, predecessors_ss)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .models import GlobalSettings, Resource, SequenceModel, Task

CSEQ_VERSION = "1.0"


def save_cseq(model: SequenceModel, path: str | Path) -> Path:
    """Save a SequenceModel to a .cseq JSON file."""
    path = Path(path)
    if path.suffix.lower() != ".cseq":
        path = path.with_suffix(".cseq")

    path.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {
        "format": "COMAU_SEQUENCE",
        "version": CSEQ_VERSION,
        "settings": {
            "available_time": model.settings.available_time,
            "takt_time": model.settings.takt_time,
            "time_increment": model.settings.time_increment,
            "output_file": model.settings.output_file,
        },
        "resources": [
            {
                "id": r.id,
                "color": r.color or "",
            }
            for r in model.resources
        ],
        "tasks": [
            {
                "id": t.id,
                "name": t.name,
                "resource": t.resource,
                "duration": t.duration,
                "predecessors_fs": t.predecessors_fs,
                "predecessors_ss": t.predecessors_ss,
            }
            for t in model.tasks
        ],
    }

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path.resolve()


def load_cseq(path: str | Path) -> SequenceModel:
    """Load a SequenceModel from a .cseq JSON file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))

    raw_settings = raw.get("settings", {})
    settings = GlobalSettings(
        available_time=float(raw_settings.get("available_time", 3600)),
        takt_time=float(raw_settings.get("takt_time", 60)),
        time_increment=float(raw_settings.get("time_increment", 1.0)),
        output_file=str(raw_settings.get("output_file", "outputs/sequence_report.xlsx")),
    )

    resources = [
        Resource(
            id=str(r["id"]),
            color=str(r["color"]).strip() if r.get("color") else None,
        )
        for r in raw.get("resources", [])
    ]

    tasks = [
        Task(
            id=str(t["id"]),
            name=str(t.get("name") or t["id"]),
            resource=str(t["resource"]),
            duration=float(t["duration"]),
            predecessors_fs=[str(p) for p in t.get("predecessors_fs", [])],
            predecessors_ss=[str(p) for p in t.get("predecessors_ss", [])],
        )
        for t in raw.get("tasks", [])
    ]

    return SequenceModel(settings=settings, resources=resources, tasks=tasks)
