# Comau Sim-Sequence Studio

> **v0.6.0** — Native PyQt6 desktop application for automation sequence scheduling and Gantt visualization.

A Python-based engineering tool for defining, scheduling, and visualizing automation sequences. Supports a native `.cseq` file format, bidirectional Excel import/export, and an interactive dark-themed desktop UI with Comau branding.

---

## Quick Start

### Desktop App (Recommended)

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the studio
python studio_app.py

# Open a sequence file directly
python studio_app.py inputs/honda_weld_sequence.cseq

# Import from an Excel template
python studio_app.py inputs/sequence_template.xlsx
```

### CLI (Headless / Scripting)

```bash
# From an Excel input template
python main.py inputs/sequence_template.xlsx

# From a YAML file
python main.py inputs/example_sequence.yaml

# From a native .cseq file
python main.py inputs/honda_weld_sequence.cseq
```

---

## Project Structure

```
Sim-Sequence-Utility/
│
├── studio_app.py              # ← Desktop app entry point
├── studio/                    # ← PyQt6 desktop app package
│   ├── main_window.py         #   QMainWindow — layout, menus, file I/O, scheduler thread
│   ├── gantt_canvas.py        #   Interactive Gantt (QGraphicsScene/View)
│   ├── task_panel.py          #   Editable Resources + Tasks tables
│   ├── settings_panel.py      #   Project settings form
│   ├── kpi_bar.py             #   Live KPI metric cards
│   └── theme.py               #   Comau dark-mode stylesheet & brand palette
│
├── main.py                    # CLI entry point (.cseq / .xlsx / .yaml)
├── main_embedded.py           # Entry point invoked by standalone .xlsm macro
├── make_template.py           # Generates blank Excel input template
├── make_standalone.py         # Generates standalone .xlsm with embedded code
├── requirements.txt
│
├── inputs/
│   ├── honda_weld_sequence.cseq   # Sample native sequence file (17 tasks, 4 resources)
│   ├── sequence_template.xlsx     # Excel input template
│   └── example_sequence.yaml      # Sample YAML input
│
├── outputs/                   # Generated reports land here
│   └── sim_sequence_standalone.xlsm
│
├── sim_sequence/              # Core scheduling + reporting package
│   ├── __init__.py            #   Package version
│   ├── models.py              #   Data classes: Task, Resource, GlobalSettings, SequenceModel
│   ├── loader.py              #   YAML → SequenceModel
│   ├── excel_loader.py        #   Excel template → SequenceModel
│   ├── cseq_io.py             #   .cseq (JSON) save/load
│   ├── scheduler.py           #   NetworkX DAG scheduler (FS + SS dependencies)
│   ├── reporter.py            #   XlsxWriter Excel report & Gantt generator
│   ├── embedder.py            #   Packs Python source for Excel embedding
│   └── assets.py              #   Embedded Comau logo (base64)
│
├── resources/
│   └── Logo-COMAU.png         # Comau logo used in app header + Excel reports
│
└── tests/
    ├── test_loader.py
    ├── test_excel_loader.py
    ├── test_embedder.py
    └── test_scheduler.py
```

---

## Desktop App Features

| Feature | Detail |
|---|---|
| **Interactive Gantt** | Hardware-accelerated `QGraphicsScene` — coloured task bars per resource, dashed Comau-Red takt marker, hover tooltips |
| **Zoom & Pan** | `Ctrl+Scroll` to zoom, scroll bars / middle-mouse to pan |
| **Click-to-select** | Click any task bar → highlights the row in the Tasks table |
| **Live KPI bar** | Cycle Time, Takt Time, Utilization %, Task & Resource counts, ✓ BALANCED / ⚠ OVER TAKT badge |
| **Resource editor** | Add/remove resources, double-click colour column to pick a colour |
| **Task editor** | Inline-edit all fields: ID, Name, Resource, Duration, FS and SS predecessors |
| **Background scheduling** | Runs in a `QThread` — UI stays responsive during compute |
| **Native file format** | `.cseq` — clean JSON, Git-friendly, diffable |
| **Excel import** | Load any existing `.xlsx` input template into the studio |
| **Excel export** | Generate the full executive Gantt report `.xlsx` from the studio |
| **Comau branding** | Dark theme, Comau Red `#C8102E`, Executive Navy `#0B2341`, Comau logo in header |

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New sequence |
| `Ctrl+O` | Open `.cseq` file |
| `Ctrl+S` | Save |
| `Ctrl+Shift+S` | Save As |
| `F5` | Run simulation |
| `Ctrl+=` | Zoom in |
| `Ctrl+-` | Zoom out |
| `Ctrl+0` | Reset zoom |
| `Ctrl+Q` | Quit |

---

## Native File Format — `.cseq`

`.cseq` files are plain JSON — version-controllable, diffable, and email-friendly.

```json
{
  "format": "COMAU_SEQUENCE",
  "version": "1.0",
  "settings": {
    "available_time": 3600,
    "takt_time": 60,
    "time_increment": 1,
    "output_file": "outputs/report.xlsx"
  },
  "resources": [
    { "id": "Operator_1", "color": "#1F4E78" },
    { "id": "Robot_A",    "color": "#4CAF50" }
  ],
  "tasks": [
    {
      "id": "Op1_GetPart", "name": "Get Part from Rack",
      "resource": "Operator_1", "duration": 4.0,
      "predecessors_fs": [], "predecessors_ss": []
    },
    {
      "id": "RobA_Weld1", "name": "Robot A — Weld Pass 1",
      "resource": "Robot_A", "duration": 10.0,
      "predecessors_fs": ["Op1_GetPart"], "predecessors_ss": []
    }
  ]
}
```

### Dependency Types

| Type | Meaning | Formula |
|---|---|---|
| `predecessors_fs` | **Finish-to-Start** — B starts after A ends | `B.start ≥ A.end` |
| `predecessors_ss` | **Start-to-Start** — B starts when A starts | `B.start ≥ A.start` |

---

## Excel Input Template

The 3-sheet template (`inputs/sequence_template.xlsx`) works with both the CLI and the studio's import function.

| Sheet | Columns |
|---|---|
| `Settings` | Key \| Value \| Notes |
| `Resources` | ID \| Color (hex) \| Preview |
| `Tasks` | ID \| Name \| Resource \| Duration (s) \| Predecessors_FS \| Predecessors_SS |

Predecessors are comma-separated in a single cell (e.g. `RobA_Weld1, RobB_Weld1`). Rows starting with `#` or blank are ignored.

Generate a fresh blank template:
```bash
python make_template.py --blank --output inputs/my_project.xlsx
```

---

## Standalone Excel Workbook

The `.xlsm` workbook embeds the entire Python engine inside a hidden sheet and uses a VBA macro to extract and run it — no Python installation visible to the end user.

```bash
# Regenerate the standalone workbook
python make_standalone.py

# Generate a blank (no demo data)
python make_standalone.py --blank --output outputs/my_blank.xlsm
```

Usage: open `outputs/sim_sequence_standalone.xlsm`, click **Enable Content**, edit the `Settings / Resources / Tasks` sheets, and press **▶ RUN SEQUENCE SIMULATION**.

---

## Running Tests

```bash
pytest tests/
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `PyQt6` | Desktop GUI framework |
| `networkx` | DAG scheduling engine |
| `XlsxWriter` | Excel report generation |
| `openpyxl` | Excel input template reading |
| `PyYAML` | YAML input format |
| `pillow` | Image handling (logo embedding) |
| `pywin32` | COM automation for `.xlsm` generation (Windows only) |

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full revision history and versioning scheme.

---

## Repository

[github.com/crashingtardis/Sim-Sequence-Utility](https://github.com/crashingtardis/Sim-Sequence-Utility)
