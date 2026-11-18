# Sim-Sequence Utility

A Python tool that generates an **interactive Excel sequence report and Gantt chart** from an automation sequence definition.

It supports two modes of operation:
1. **Standalone Excel Package (.xlsm)**: The entire Python engine is embedded into an Excel macro-enabled workbook. Users edit their sequence directly in Excel and click a **"▶ Run Sequence"** button on the sheet.
2. **CLI / Developer Pipeline**: Generate sequence reports from either `.xlsx` templates or `.yaml` files via `python main.py`.

## Project Structure

```
Sim-Sequence-Utility/
├── main.py                        # Standard CLI entry point (.xlsx or .yaml)
├── main_embedded.py               # Entry point invoked by the standalone .xlsm macro
├── make_template.py               # Generates static Excel input template (.xlsx)
├── make_standalone.py             # Generates standalone Excel workbook with embedded code (.xlsm)
├── requirements.txt
├── inputs/
│   ├── sequence_template.xlsx     # Static input template
│   └── example_sequence.yaml      # Sample YAML input
├── outputs/
│   ├── sim_sequence_standalone.xlsm # Standalone all-in-one workbook
│   └── honda_seq_dev_111826.xlsx  # Generated output report & Gantt chart
├── sim_sequence/                  # Core package
│   ├── __init__.py
│   ├── models.py                  # Data classes (Task, Resource, SequenceModel)
│   ├── loader.py                  # YAML → SequenceModel parser
│   ├── excel_loader.py            # Excel template → SequenceModel parser
│   ├── embedder.py                # Packs Python source code for Excel embedding
│   ├── scheduler.py               # NetworkX DAG scheduler (FS + SS dependencies)
│   └── reporter.py                # XlsxWriter Excel report & Gantt generator
└── tests/
    ├── test_loader.py
    ├── test_excel_loader.py
    ├── test_embedder.py
    └── test_scheduler.py
```

## Option 1: Standalone Excel Workbook (100% In-Workbook Execution)

1. Open [`outputs/sim_sequence_standalone.xlsm`](outputs/sim_sequence_standalone.xlsm) in Microsoft Excel.
2. If prompted, click **"Enable Content"** (to allow the embedded runner macro).
3. Edit your tasks, resources, and settings on the `Settings`, `Resources`, and `Tasks` sheets.
4. Click the **"▶ RUN SEQUENCE SIMULATION"** button on the `Settings` launchpad.
5. The embedded engine calculates the DAG, resolves all interlocks, and **creates/refreshes the `Overall_Sequence` Master Gantt and granular resource drill-down tabs directly inside this same workbook!** No external files are needed.

To generate a new blank or updated standalone workbook:
```bash
python make_standalone.py
# or for an empty template without example tasks:
python make_standalone.py --blank --output outputs/my_blank_standalone.xlsm
```

## Option 2: CLI Usage

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run against an Excel input template:
python main.py inputs/sequence_template.xlsx

# ...or run against a YAML file:
python main.py inputs/example_sequence.yaml
```

## Input Format (YAML)

See [`inputs/example_sequence.yaml`](inputs/example_sequence.yaml) for a full annotated example.

| Key | Description |
|---|---|
| `settings.available_time` | Total cycle time budget (seconds) |
| `settings.takt_time` | Target line rate / takt time |
| `settings.time_increment` | Column resolution on granular sheets |
| `settings.output_file` | Output path for the `.xlsx` |
| `resources[].id` | Resource name (used as tab name) |
| `resources[].color` | Hex colour for Gantt bars |
| `tasks[].predecessors_fs` | Finish-to-Start dependencies (list of task IDs) |
| `tasks[].predecessors_ss` | Start-to-Start dependencies (list of task IDs) |

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full revision history and versioning scheme.

## Running Tests

```bash
pytest tests/
```
