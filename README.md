# Comau Sim-Sequence Studio

> **v0.8.0** — Native PyQt6 desktop application for automation sequence scheduling, interactive Gantt visualization, and executable packaging.

A Python-based engineering tool for defining, scheduling, and visualizing automation sequences. Supports a native `.cseq` file format, bidirectional Excel import/export (including original Honda sequence sheets), an interactive dark-themed desktop UI with Comau branding, live drag-to-resize duration, interactive drag-and-drop dependency linking, and standalone `.exe` packaging.

---

## Quick Start

### Desktop App (Recommended)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch the studio
python studio_app.py

# Open a sequence file directly:
python studio_app.py inputs/honda_weld_sequence.cseq

# Or import from an Excel template:
python studio_app.py inputs/sequence_template.xlsx
```

### Standalone Executable (No Python Required)

```bash
# Build standalone Windows .exe:
python build_exe.py

# Output: dist/SimSequenceStudio.exe

# Register .cseq file association in Windows Explorer:
# Double-click register_cseq.reg
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
├── build_exe.py               # ← One-click PyInstaller build script (.exe + .ico + .reg)
├── SimSequenceStudio.spec     # ← PyInstaller build specification
├── register_cseq.reg          # ← Windows Registry file association for .cseq
│
├── studio/                    # ← PyQt6 desktop app package
│   ├── main_window.py         #   QMainWindow — layout, menus, toolbar, scheduler thread
│   ├── gantt_canvas.py        #   Interactive Gantt (drag-resize, dependency links, arrows)
│   ├── task_panel.py          #   Editable Resources + Tasks tables
│   ├── settings_panel.py      #   Project settings form
│   ├── kpi_bar.py             #   Live KPI metric cards & dependency legend
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
│   ├── honda_seq_dev_111826.xlsx  # Original Honda weld sequence Excel sheet (22 tasks, 6 resources)
│   ├── sequence_template.xlsx     # Standard 3-sheet Excel input template
│   └── example_sequence.yaml      # Sample YAML input
│
├── outputs/                   # Generated reports land here
│   └── sim_sequence_standalone.xlsm
│
├── sim_sequence/              # Core scheduling + reporting package
│   ├── __init__.py            #   Package version (0.8.0)
│   ├── models.py              #   Data classes: Task, Resource, GlobalSettings, SequenceModel
│   ├── loader.py              #   YAML → SequenceModel
│   ├── excel_loader.py        #   Excel template & Honda sheet → SequenceModel parser
│   ├── cseq_io.py             #   .cseq (JSON) save/load
│   ├── scheduler.py           #   NetworkX DAG scheduler (FS + SS dependencies)
│   ├── reporter.py            #   XlsxWriter Excel report & Gantt generator
│   ├── embedder.py            #   Packs Python source for Excel embedding
│   └── assets.py              #   Embedded Comau logo (base64)
│
├── resources/
│   ├── Logo-COMAU.png         # Comau logo used in app header + Excel reports
│   └── Logo-COMAU.ico         # Generated multi-resolution Windows application icon
│
└── tests/
    ├── test_cseq_io.py        # Tests for .cseq file format serializer/deserializer
    ├── test_loader.py
    ├── test_excel_loader.py   # Tests for 3-sheet and Honda sequence sheet parsing
    ├── test_embedder.py
    └── test_scheduler.py
```

---

## Desktop App Features

| Feature | Detail |
|---|---|
| **Interactive Gantt Canvas** | Hardware-accelerated `QGraphicsScene` with coloured task bars, dashed Comau-Red takt marker, hover tooltips |
| **Drag-to-Resize Duration** | Hover over the right edge of any task bar (cursor changes to `↔`) and drag horizontally to alter duration; live DAG recalculation occurs on mouse release |
| **Dependency Arrows** | Visual elbow paths with directional arrowheads: **Finish-to-Start (FS)** as solid grey arrows, **Start-to-Start (SS)** as dashed amber arrows |
| **Drag-and-Drop Dependency Linking** | Right-click and drag from Task A to Task B to draw an elastic connection line; release to choose FS or SS dependency via instant popup |
| **Interactive Dependency Removal** | Right-click any dependency arrow in the Gantt to delete it; hovering over arrows highlights them in blue |
| **Zoom & Pan** | `Ctrl+Scroll` to zoom (4 px/s to 80 px/s), scroll bars or middle-mouse drag to pan |
| **Click-to-Select** | Click any task bar to inspect details and automatically focus/select the row in the Tasks table |
| **Live KPI Bar** | Instant calculation of Total Cycle Time, Takt Time, Utilization %, Task & Resource counts, and `✓ BALANCED` / `⚠ OVER TAKT` badge |
| **Dependency Legend** | Visual guide in the KPI bar distinguishing solid FS from dashed SS arrows |
| **Resource & Task Editors** | Inline table editors for ID, Name, Resource, Duration, and comma-separated Predecessors; double-click color to open color picker |
| **Load Sample Honda Sequence** | Accessible directly from **Help -> Load Sample Honda Sequence (from Excel)**; immediately loads and visualizes the full 22-task Honda dataset |
| **Background Scheduling** | Scheduling and DAG analysis run asynchronously in a dedicated `QThread`, ensuring zero UI lockup |
| **Native `.cseq` File Format** | Clean, version-controlled JSON format for sequences |
| **Bidirectional Excel Integration** | Import both 3-sheet templates and original Honda timing sheets; export presentation-ready Excel reports with drill-downs |
| **Comau Brand Theme** | Professional industrial dark palette (Executive Navy `#0B2341`, Comau Red `#C8102E`, Slate `#1A2E40`) |

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

## Standalone Executable Packaging & File Association

To distribute the application to users without requiring a Python environment:

1. **Build the single-file executable:**
   ```bash
   python build_exe.py
   ```
   This generates `dist/SimSequenceStudio.exe` (~50 MB, self-contained).

2. **Register the `.cseq` file extension:**
   - Double-click `register_cseq.reg` generated in the root folder.
   - Now double-clicking any `.cseq` file in Windows Explorer will open it directly in Sim-Sequence Studio.

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
| `predecessors_fs` | **Finish-to-Start** — Task B starts after Task A finishes | `B.start ≥ A.end` |
| `predecessors_ss` | **Start-to-Start** — Task B starts when Task A starts | `B.start ≥ A.start` |

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

The `.xlsm` workbook embeds the entire Python engine inside a hidden sheet and uses a VBA macro to extract and run it in-place.

```bash
# Regenerate the standalone workbook
python make_standalone.py

# Generate a blank (no demo data)
python make_standalone.py --blank --output outputs/my_blank.xlsm
```

---

## Running Tests

```bash
pytest tests/
# or
python -m pytest tests/
```

All 21 unit tests validate loaders (including 3-sheet templates and original Honda sheets), DAG scheduling, Excel output, embedding, and `.cseq` serialization.

---

## Dependencies

| Package | Purpose |
|---|---|
| `PyQt6` | Desktop GUI framework |
| `PyQt6-Charts` | Charting components |
| `networkx` | DAG scheduling engine |
| `XlsxWriter` | Excel report generation |
| `openpyxl` | Excel input template reading |
| `PyYAML` | YAML input format |
| `pillow` | Image handling & `.ico` generation |
| `pyinstaller` | Standalone `.exe` packaging |
| `pywin32` | COM automation for `.xlsm` generation |

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full revision history and versioning scheme.

---

## Repository

[github.com/crashingtardis/Sim-Sequence-Utility](https://github.com/crashingtardis/Sim-Sequence-Utility)
