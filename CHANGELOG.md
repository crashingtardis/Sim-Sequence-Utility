# Sim-Sequence Utility — Changelog

## Versioning Scheme

**`MAJOR.MINOR.PATCH`**

| Digit | Bumps when… |
| --- | --- |
| **MAJOR** | Input schema or output structure changes in a **breaking** way (e.g. renamed required columns, restructured sheets) |
| **MINOR** | New **feature** added in a backward-compatible way (new input format, new sheet type, new dependency type, new CLI flag) |
| **PATCH** | Bug fix, formatting tweak, refactor, or test addition — no behaviour change visible to the user |

Pre-`1.0.0` versions are considered **development** builds; the input template format may still evolve.

---

## [0.5.0] — 2026-11-18

### Added
- **In-Workbook Tab Generation (100% Truly Standalone)**:
  - When the user clicks **`▶ RUN SEQUENCE SIMULATION`**, generated sequence tabs (`Overall_Sequence`, `Operator_1`, `Robot_A`, etc.) are created and refreshed directly **inside the same `.xlsm` workbook**!
  - No new external workbook is created; previous simulation runs are cleanly replaced in place and the Master Gantt dashboard is immediately activated.
- **Comau Brand Identity & Executive UI Design**:
  - Embedded official **Comau logo** (`resources/Logo-COMAU.png`) stored as resilient base64 assets in `sim_sequence/assets.py` to ensure visual presentation remains intact anywhere the workbook is opened.
  - Implemented Comau color theme: Comau Red (`#C8102E`), Executive Navy (`#0B2341`), and Slate (`#1A2E40`).
- **Master Gantt & Executive KPI Cards**:
  - Added high-visibility KPI summary metrics cards to `Overall_Sequence`:
    - **Total Cycle Time** (s)
    - **Line Takt Time** (s)
    - **Utilization %**
    - **Line Balance Status Badge** (`✓ BALANCED` / `⚠ OVER TAKT`)
    - **Task & Resource Counts**
- **Enhanced Settings Launchpad**:
  - Header banner with Comau logo and subtitle.
  - Styled action button: `▶ RUN SEQUENCE SIMULATION`.
  - Quick action links: `📊 View Master Gantt`, `📋 Tasks`, `🔧 Resources`.
  - Form-style parameters with units and descriptions.
  - Quick Reference table for Finish-to-Start (FS) and Start-to-Start (SS) rules.
- **Granular Grid Aesthetics**:
  - Color-coded tabs matching resource Gantt bar colors.
  - Top navigation bar with `⮌ Master Gantt` return button.
  - Major time markers tinted on every 5th second.

---

## [0.4.1] — 2026-11-18

### Fixed

- **Windows Console / Redirect `UnicodeEncodeError`**:
  - Reconfigured standard output and error streams in `main_embedded.py` and `main.py` with UTF-8 encoding and error replacement.
  - Replaced unicode arrow `\u2192` (`→`) with ASCII `->` to avoid crash on Windows systems with `cp1252` redirect code page.
  - Added `set PYTHONIOENCODING=utf-8` and `chcp 65001` in runner batch wrapper.
- **Python Subshell Fallback masking exit code**:
  - Replaced fragile `(py ... || python ...)` shell chaining with a clean runner batch script (`run.bat`) that verifies whether `py.exe` exists before falling back to `python.exe`. This prevents the Windows Store stub error (*"Python was not found..."*) from masking real application tracebacks.
- **File lock handling during generation**:
  - Added graceful error handling in `make_standalone.py` when target `.xlsm` is open in Excel.

---

## [0.4.0] — 2026-11-18

### Added

- **Embedded standalone macro workbook (`outputs/sim_sequence_standalone.xlsm`)**:
  - Encapsulates entire Python package inside a hidden `_py` worksheet.
  - Native Excel clickable shape button: `▶ Run Sequence` on the `Settings` sheet.
  - Injected VBA runner (`SimSequence.RunSequence`) extracts Python sources to `%TEMP%\SimSeq\`, invokes `main_embedded.py`, handles fallback between `py` and `python`, displays detailed graphical error dialogs or a success message, and prompts to immediately open the generated report.
  - VBA uses `ADODB.Stream` for UTF-8 character preservation and `Scripting.FileSystemObject` for reliable directory hierarchy creation.
- **Embedded entry point (`main_embedded.py`)**:
  - Invoked directly by the Excel VBA macro with the workbook path as an argument.
  - Resolves output paths cleanly without redundant folder nesting.
- **Source embedder engine (`sim_sequence/embedder.py`)**:
  - Automatically indexes and flattens all module files (`models`, `loader`, `excel_loader`, `scheduler`, `reporter`, `main_embedded`) into two-column rows for sheet storage.
- **Standalone generator CLI (`make_standalone.py`)**:
  - Automates workbook assembly, sheet styling, hidden code embedding, and COM VBA injection.
  - Supports `--blank` flag for generating empty templates without demo data.
- **New test suite (`tests/test_embedder.py`)**:
  - Validates source collection, module coverage, non-empty file contents, and row mapping format.

---

## [0.3.0] — 2026-11-18

### Added

- **Excel input format** (`sim_sequence/excel_loader.py`) — reads a 3-sheet `.xlsx` template (Settings / Resources / Tasks) into a `SequenceModel`; predecessor lists are comma-separated in a single cell; blank and `#`-comment rows are skipped
- **Template generator** (`make_template.py`) — produces a formatted, pre-filled `.xlsx` input template with coloured headers, resource colour-swatch column, alternating row fills, frozen panes, and inline column notes; `--blank` flag emits headers only
- **Format auto-detection in `main.py`** — routes `.xlsx` → `excel_loader`, `.yaml/.yml` → `yaml_loader`; structured error messages on parse failure
- **6 new tests** (`tests/test_excel_loader.py`) — happy-path load, predecessor parsing, blank/comment-row skipping, missing-sheet error, missing-setting-key error

### Changed

- `main.py` now wraps load/schedule in try/except and prints structured errors to stderr

---

## [0.2.0] — 2026-11-18

### Added

- **Per-resource bar colours** on the Summary Gantt — one chart series per resource so each row gets its own colour rather than a uniform fill
- **`_darken()` helper** in `reporter.py` — derives a border colour from the fill colour automatically
- **Frozen panes** on all sheets (row 1 on Summary; row 1 + first 3 columns on granular sheets)
- **Rotated time-column headers** (90°) with row height set to 55 pt for readability
- **Richer example sequence** in `inputs/example_sequence.yaml` — 17 tasks across 4 resources (Operator, Robot A, Robot B, Fixture) with realistic FS and SS interlocks modelling a Honda body-shop weld cycle
- **Schedule verification script** (`scratch_debug.py`) — prints a tabular schedule dump with cycle-time vs takt-time utilisation check

### Changed

- `reporter.py` fully rewritten: extracted `_build_formats`, `_resource_hex_map`, `_resource_block_formats` helpers; column widths and zoom levels set explicitly; "View Details" link updated to "▶ View Details"
- Conditional-format formula changed from `<=` to `<` on the end-time boundary to avoid double-highlighting at exact task boundaries

---

## [0.1.0] — 2026-11-18

### Added

- **Project scaffold** — `sim_sequence/` package with clean separation of concerns:
  - `models.py` — `Task`, `Resource`, `GlobalSettings`, `SequenceModel` data classes
  - `loader.py` — YAML → `SequenceModel` parser
  - `scheduler.py` — NetworkX DAG scheduler; Finish-to-Start and Start-to-Start dependency types; cycle detection; unknown-predecessor validation
  - `reporter.py` — XlsxWriter report generator: Summary stacked-bar Gantt + per-resource conditionally formatted time-grids with drill-down hyperlinks and "Back to Summary" links
  - `main.py` — CLI entry point (`python main.py <input>`)
- **`inputs/example_sequence.yaml`** — annotated sample input (5 tasks, 3 resources)
- **`requirements.txt`** — `networkx`, `XlsxWriter`, `PyYAML`, `openpyxl`
- **`README.md`** — quick-start guide and input format reference
- **7 unit tests** (`tests/test_loader.py`, `tests/test_scheduler.py`) — single-task, FS chain, SS interlock, multi-predecessor max, cycle error, unknown-predecessor error
- **`outputs/`** directory — designated output location for generated `.xlsx` files
