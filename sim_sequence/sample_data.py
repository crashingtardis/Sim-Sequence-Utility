"""
sample_data.py — Built-in sample automation sequence definitions.

Stored in Python code so sample data can be loaded directly from the UI
without any external file dependencies or customer-specific names.
"""

from __future__ import annotations

from .models import GlobalSettings, Resource, SequenceModel, Task


def get_sample_sequence() -> SequenceModel:
    """Return a standard automotive body-shop welding cell sequence (22 tasks, 6 resources).

    Includes:
      - Operator loading and unloading
      - Geo clamping tool open/close cycles
      - Dual-robot coordinated welding passes with interlocks
      - Material handling robot part transfer
      - Unload conveyor indexing
    """
    settings = GlobalSettings(
        available_time=3600.0,
        takt_time=60.0,
        time_increment=1.0,
        output_file="outputs/sequence_report.xlsx",
    )

    resources = [
        Resource(id="Operator 1",         color="#1F4E78"),  # Navy Blue
        Resource(id="Geo Tool 1",         color="#9C27B0"),  # Purple
        Resource(id="Robot 1 (Geo Weld)", color="#4CAF50"),  # Green
        Resource(id="Robot 2 (Geo Weld)", color="#FF9800"),  # Orange
        Resource(id="Robot 3 (MH)",       color="#00BCD4"),  # Cyan
        Resource(id="Unload Conveyor",    color="#795548"),  # Brown
    ]

    tasks = [
        # ── Operator 1 ───────────────────────────────────────────────────────
        Task(
            id="a1",
            name="Load parts, hit palm buttons",
            resource="Operator 1",
            duration=10.0,
            predecessors_fs=[],
            predecessors_ss=[],
        ),
        Task(
            id="a2",
            name="Get next set of parts and set near light screen",
            resource="Operator 1",
            duration=13.0,
            predecessors_fs=["a1"],
            predecessors_ss=[],
        ),
        Task(
            id="a3",
            name="Unload part from conveyor and load in dunnage",
            resource="Operator 1",
            duration=10.0,
            predecessors_fs=["a2", "f1"],
            predecessors_ss=[],
        ),

        # ── Geo Tool 1 ───────────────────────────────────────────────────────
        Task(
            id="b1",
            name="Close clamps, dumps, pins",
            resource="Geo Tool 1",
            duration=2.0,
            predecessors_fs=["a1"],
            predecessors_ss=[],
        ),
        Task(
            id="b2",
            name="Open clamps, dumps, pins",
            resource="Geo Tool 1",
            duration=2.0,
            predecessors_fs=["b1", "c3", "d4"],
            predecessors_ss=[],
        ),

        # ── Robot 1 (Geo Weld) ───────────────────────────────────────────────
        Task(
            id="c1",
            name="Move to pounce",
            resource="Robot 1 (Geo Weld)",
            duration=2.0,
            predecessors_fs=["a1"],
            predecessors_ss=[],
        ),
        Task(
            id="c2",
            name="Geo weld segment 1",
            resource="Robot 1 (Geo Weld)",
            duration=8.0,
            predecessors_fs=["c1", "b1"],
            predecessors_ss=[],
        ),
        Task(
            id="c3",
            name="Geo weld segment 2",
            resource="Robot 1 (Geo Weld)",
            duration=7.0,
            predecessors_fs=["c2", "d3"],
            predecessors_ss=[],
        ),
        Task(
            id="c4",
            name="Move to home",
            resource="Robot 1 (Geo Weld)",
            duration=5.0,
            predecessors_fs=["c3"],
            predecessors_ss=[],
        ),
        Task(
            id="c5",
            name="Tip dress",
            resource="Robot 1 (Geo Weld)",
            duration=13.0,
            predecessors_fs=["c4"],
            predecessors_ss=[],
        ),

        # ── Robot 2 (Geo Weld) ───────────────────────────────────────────────
        Task(
            id="d1",
            name="Move to pounce",
            resource="Robot 2 (Geo Weld)",
            duration=2.0,
            predecessors_fs=["a1"],
            predecessors_ss=[],
        ),
        Task(
            id="d2",
            name="Geo weld segment 1",
            resource="Robot 2 (Geo Weld)",
            duration=6.0,
            predecessors_fs=["d1", "b1"],
            predecessors_ss=[],
        ),
        Task(
            id="d3",
            name="Geo weld segment 2",
            resource="Robot 2 (Geo Weld)",
            duration=4.0,
            predecessors_fs=["d2"],
            predecessors_ss=[],
        ),
        Task(
            id="d4",
            name="Geo weld segment 3",
            resource="Robot 2 (Geo Weld)",
            duration=5.0,
            predecessors_fs=["d3"],
            predecessors_ss=[],
        ),
        Task(
            id="d5",
            name="Move to home",
            resource="Robot 2 (Geo Weld)",
            duration=6.0,
            predecessors_fs=["d4"],
            predecessors_ss=[],
        ),
        Task(
            id="d6",
            name="Tip dress",
            resource="Robot 2 (Geo Weld)",
            duration=10.0,
            predecessors_fs=["d5"],
            predecessors_ss=[],
        ),

        # ── Robot 3 (MH) ─────────────────────────────────────────────────────
        Task(
            id="e1",
            name="Move to pounce",
            resource="Robot 3 (MH)",
            duration=5.0,
            predecessors_fs=[],
            predecessors_ss=[],
        ),
        Task(
            id="e2",
            name="Pick part and clear",
            resource="Robot 3 (MH)",
            duration=9.0,
            predecessors_fs=["e1", "b2"],
            predecessors_ss=[],
        ),
        Task(
            id="e3",
            name="Move to conveyor",
            resource="Robot 3 (MH)",
            duration=3.0,
            predecessors_fs=["e2"],
            predecessors_ss=[],
        ),
        Task(
            id="e4",
            name="Drop and clear",
            resource="Robot 3 (MH)",
            duration=4.0,
            predecessors_fs=["e3"],
            predecessors_ss=[],
        ),
        Task(
            id="e5",
            name="Return home",
            resource="Robot 3 (MH)",
            duration=7.0,
            predecessors_fs=["e4"],
            predecessors_ss=[],
        ),

        # ── Unload Conveyor ──────────────────────────────────────────────────
        Task(
            id="f1",
            name="Index conveyor",
            resource="Unload Conveyor",
            duration=8.0,
            predecessors_fs=["e4"],
            predecessors_ss=[],
        ),
    ]

    return SequenceModel(settings=settings, resources=resources, tasks=tasks)
