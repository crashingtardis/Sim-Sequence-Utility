# Comau Sim-Sequence Studio

> **v0.9.0** — Native PyQt6 desktop application for automation sequence scheduling, interactive Gantt visualization, and executable packaging.

A Python-based engineering tool for defining, scheduling, and visualizing automation sequences. Supports a native `.cseq` file format, bidirectional Excel import/export, an interactive desktop UI with Comau branding and a dark / light theme toggle, live drag-to-resize duration, drag-from-handle dependency linking, and standalone `.exe` packaging.

---

## Quick Start

### Desktop App (Recommended)

```bash
# 1. Install dependencies
pip install -r requirements.txt        # runtime
pip install -r requirements-dev.txt    # + pytest, pyinstaller, pillow (to run tests / build the .exe)

# 2. Launch the studio
python studio_app.py

# Open a sequence file directly:
python studio_app.py inputs/sample_weld_sequence.cseq

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
python main.py inputs/sample_weld_sequence.cseq
```

---

## Project Structure

```
Sim-Sequence-Utility/
│
├── studio_app.py              # ← Desktop app entry point
├── build_exe.py               # ← One-click PyInstaller build script (.exe + .ico + .reg; spec/.reg are generated, git-ignored)
│
├── studio/                    # ← PyQt6 desktop app package
│   ├── main_window.py         #   QMainWindow — layout, menus, toolbar, theme toggle, auto-run
│   ├── project_store.py       #   ProjectStore — single source of truth; panels/dropdowns/Gantt are views
│   ├── task_panel.py          #   Resources + Tasks tables, dropdown delegates (resource / predecessors)
│   ├── gantt_canvas.py        #   Interactive Gantt (link handles, selectable links, sticky labels, lanes)
│   ├── gantt_toolbar.py       #   Zoom / Fit buttons + link legend (wraps when narrow)
│   ├── kpi_bar.py             #   KPI cards + balance badge (wraps when narrow)
│   ├── settings_panel.py      #   Project settings form
│   ├── flow_layout.py         #   Wrapping layout used by the KPI bar and Gantt toolbar
│   └── theme.py               #   Theme dataclass, DARK / LIGHT palettes, stylesheet generator
│
├── main.py                    # CLI entry point (.cseq / .xlsx / .yaml)
├── main_embedded.py           # Entry point invoked by standalone .xlsm macro
├── make_template.py           # Generates blank Excel input template
├── make_standalone.py         # Generates standalone .xlsm with embedded code
├── requirements.txt
│
├── inputs/
│   ├── sample_weld_sequence.cseq  # Sample native sequence file (17 tasks, 4 resources)
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
│   ├── excel_loader.py        #   Excel template & timing-matrix sheet → SequenceModel parser
│   ├── cseq_io.py             #   .cseq (JSON) save/load
│   ├── graph_ops.py           #   Pure edit rules: link validation, cycle check, renames, lane layout
│   ├── sample_data.py         #   Built-in sample sequence (Help menu)
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
    ├── test_excel_loader.py   # Tests for 3-sheet and timing-matrix sheet parsing
    ├── test_graph_ops.py      # Tests for link validation, renames, lane layout
    ├── test_embedder.py
    └── test_scheduler.py
```

---

## Desktop App Features

| Feature | Detail |
|---|---|
| **Interactive Gantt Canvas** | `QGraphicsScene` with coloured task bars, dashed Comau-Red takt marker, hover tooltips. Resource column and time header stay pinned while scrolling |
| **Drag-to-Create Links** | Every bar has two handles: drag the **blue right handle** onto another bar for a **Finish-to-Start (FS)** link, or the **amber left handle** for a **Start-to-Start (SS)** link. The target bar turns green (valid) or red (self-link, duplicate, or circular) while dragging; `Esc` cancels. No menus |
| **Easy Link Removal** | Links have a wide click target. Click one to select it, then press `Delete` or click its red ✕ badge. Right-click → Remove also works |
| **Dropdown-driven Editing** | Task **Resource** is a dropdown of all resources; **FS / SS Predecessors** are multi-select dropdowns of all tasks that can legally be predecessors (never itself or anything that would create a cycle). New resources/tasks appear in them immediately; renames propagate; removing a resource unassigns its tasks |
| **Drag-to-Resize Duration** | Drag the right edge of a bar; snaps to 0.1 s and reschedules on release |
| **Overlap-free Layout** | Parallel tasks on one resource stack in sub-lanes; bar text is elided to the bar; time ticks adapt to zoom; tasks with no valid resource show in an "Unassigned" row instead of vanishing |
| **Fit & Zoom** | `Fit` fits the sequence to the window and stays fitted as you resize; `Ctrl+Scroll` / buttons zoom manually (0.5–120 px/s) |
| **Resizable Panes** | Splitter between the editor pane and Gantt (no width cap); KPI bar and Gantt toolbar wrap instead of overlapping on narrow windows; window geometry and splitter position are remembered |
| **Dark / Light Theme** | `View → Dark mode` (`Ctrl+Shift+D`) or toolbar toggle; choice is remembered |
| **Auto-run** | Schedule re-runs ~0.3 s after any edit (toggle in the Simulation menu); `F5` runs immediately |
| **Live KPI Bar** | Cycle Time, Takt Time, Utilisation %, Task & Resource counts, `✓ BALANCED` / `⚠ OVER TAKT` badge |
| **Load Sample Sequence** | `Help → Load Sample Sequence (Body-Shop Cell)` loads the built-in 22-task, 6-resource example |
| **Native `.cseq` File Format** | Clean, version-controlled JSON format for sequences |
| **Bidirectional Excel Integration** | Import 3-sheet templates and timing-matrix sheets; export presentation-ready Excel reports with drill-downs |
| **Comau Brand Theme** | Executive Navy `#0B2341`, Comau Red `#C8102E`, in both dark and light variants |

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
| `Ctrl+9` | Fit to window |
| `Ctrl+0` | Reset zoom (100%) |
| `Ctrl+Shift+D` | Toggle dark / light mode |
| `Delete` | Remove selected link (Gantt) or selected row (Resources / Tasks tables) |
| `Esc` | Cancel a link drag |
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

The suite covers loaders (3-sheet templates and timing-matrix sheets), DAG scheduling, embedding, `.cseq` serialization and the pure graph-editing rules in `sim_sequence/graph_ops.py` (link validation, cycle detection, renames, lane layout). The Qt widgets themselves are not covered by automated tests.

---

## Dependencies

| Package | Purpose |
|---|---|
| `PyQt6` | Desktop GUI framework |
| `networkx` | DAG scheduling engine |
| `XlsxWriter` | Excel report generation |
| `openpyxl` | Excel input template reading |
| `PyYAML` | YAML input format |
| `pywin32` | COM automation for `.xlsm` generation (Windows only) |

Dev-only (`requirements-dev.txt`): `pytest`, `pyinstaller` (standalone `.exe`), `pillow` (`.ico` generation).

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full revision history and versioning scheme.

---

## Repository

[github.com/crashingtardis/Sim-Sequence-Utility](https://github.com/crashingtardis/Sim-Sequence-Utility)
