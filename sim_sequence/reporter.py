"""
reporter.py — Excel report generator using XlsxWriter with Comau branding.

Builds two types of sheets from a *scheduled* SequenceModel:
  1. ``Overall_Sequence``  — Executive KPI dashboard, Master Gantt chart,
                             resource breakdown with drill-down hyperlinks.
  2. ``<Resource ID>``     — Conditionally formatted granular time-grids,
                             frozen labels, zebra striping, and back-navigation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import xlsxwriter
import xlsxwriter.utility

from .assets import get_logo_path
from .models import Resource, SequenceModel, Task


# ---------------------------------------------------------------------------
# Comau brand & industrial color palette
# ---------------------------------------------------------------------------
COMAU_RED       = "#C8102E"   # Primary brand accent
COMAU_NAVY      = "#0B2341"   # Executive header navy
COMAU_SLATE     = "#1A2E40"   # Secondary header slate
COMAU_LIGHT_BG  = "#F4F7FA"   # Card background
COMAU_BORDER    = "#D0D7DE"   # Card border
STATUS_GREEN    = "#2E7D32"   # Balanced status green
STATUS_GREEN_BG = "#E8F5E9"
STATUS_RED      = "#C62828"   # Over-takt status red
STATUS_RED_BG   = "#FFEBEE"

# Default Gantt series colors (cycled if resource color is omitted)
_DEFAULT_COLOURS = [
    "#1F4E78",  # Steel Blue
    "#2E7D32",  # Forest Green
    "#E65100",  # Industrial Amber / Orange
    "#6A1B9A",  # Deep Purple
    "#00838F",  # Teal Cyan
    "#C8102E",  # Comau Red
    "#4E342E",  # Bronze / Brown
    "#37474F",  # Charcoal Gray
]

_COL_W_TASK  = 26
_COL_W_START = 10
_COL_W_END   = 10
_COL_W_GRID  = 2.8   # Narrow time grid columns


def generate_report(model: SequenceModel, output_path: str | Path | None = None) -> Path:
    """
    Write the Excel report for *model* (must already be scheduled).

    Returns the absolute :class:`Path` of the written file.
    """
    dest = Path(output_path or model.settings.output_file)
    dest.parent.mkdir(parents=True, exist_ok=True)

    wb = xlsxwriter.Workbook(str(dest))
    wb.set_properties({
        "title": "Comau Automation Sequence Simulation",
        "subject": "Cycle Time & Line Balance Report",
        "company": "Comau LLC",
    })

    fmt       = _build_formats(wb)
    hex_map   = _resource_hex_map(model)
    block_map = _resource_block_formats(wb, hex_map)

    # 1. Summary sheet (Master Dashboard)
    _write_summary_sheet(wb, model, fmt, hex_map)

    # 2. Granular drill-down sheets per resource
    for resource in model.resources:
        _write_resource_sheet(wb, model, resource, fmt, block_map, hex_map)

    wb.close()
    return dest.resolve()


# ---------------------------------------------------------------------------
# Format builders
# ---------------------------------------------------------------------------

def _build_formats(wb: xlsxwriter.Workbook) -> Dict[str, object]:
    f = "Segoe UI"
    return {
        # Banners
        "banner": wb.add_format({
            "font_name": f, "font_size": 14, "bold": True,
            "font_color": "#FFFFFF", "bg_color": COMAU_NAVY,
            "align": "left", "valign": "vcenter",
        }),
        "banner_sub": wb.add_format({
            "font_name": f, "font_size": 9, "italic": True,
            "font_color": "#DCE6F1", "bg_color": COMAU_NAVY,
            "align": "left", "valign": "vcenter",
        }),

        # KPI Cards
        "kpi_label": wb.add_format({
            "font_name": f, "font_size": 8, "bold": True,
            "font_color": "#5A6B7C", "bg_color": COMAU_LIGHT_BG,
            "align": "center", "valign": "vcenter",
            "top": 1, "left": 1, "right": 1, "border_color": COMAU_BORDER,
        }),
        "kpi_value": wb.add_format({
            "font_name": f, "font_size": 16, "bold": True,
            "font_color": COMAU_NAVY, "bg_color": COMAU_LIGHT_BG,
            "align": "center", "valign": "vcenter",
            "bottom": 1, "left": 1, "right": 1, "border_color": COMAU_BORDER,
        }),
        "kpi_status_ok": wb.add_format({
            "font_name": f, "font_size": 12, "bold": True,
            "font_color": STATUS_GREEN, "bg_color": STATUS_GREEN_BG,
            "align": "center", "valign": "vcenter",
            "bottom": 1, "left": 1, "right": 1, "border_color": COMAU_BORDER,
        }),
        "kpi_status_over": wb.add_format({
            "font_name": f, "font_size": 12, "bold": True,
            "font_color": STATUS_RED, "bg_color": STATUS_RED_BG,
            "align": "center", "valign": "vcenter",
            "bottom": 1, "left": 1, "right": 1, "border_color": COMAU_BORDER,
        }),

        # Table headers
        "th_navy": wb.add_format({
            "font_name": f, "font_size": 10, "bold": True,
            "font_color": "#FFFFFF", "bg_color": COMAU_SLATE,
            "border": 1, "border_color": "#2E4057", "align": "center", "valign": "vcenter",
        }),
        "th_navy_left": wb.add_format({
            "font_name": f, "font_size": 10, "bold": True,
            "font_color": "#FFFFFF", "bg_color": COMAU_SLATE,
            "border": 1, "border_color": "#2E4057", "align": "left", "valign": "vcenter",
        }),

        # Standard grid cells
        "cell_left": wb.add_format({
            "font_name": f, "font_size": 10, "border": 1,
            "border_color": "#E0E0E0", "valign": "vcenter",
        }),
        "cell_center": wb.add_format({
            "font_name": f, "font_size": 10, "border": 1,
            "border_color": "#E0E0E0", "align": "center", "valign": "vcenter",
        }),
        "cell_num": wb.add_format({
            "font_name": f, "font_size": 10, "border": 1,
            "border_color": "#E0E0E0", "align": "center", "valign": "vcenter",
            "num_format": "0.0#",
        }),
        "link_btn": wb.add_format({
            "font_name": f, "font_size": 9, "bold": True,
            "font_color": "#0056B3", "underline": 1, "align": "center", "valign": "vcenter",
            "border": 1, "border_color": "#E0E0E0", "bg_color": "#F0F7FF",
        }),
        "back_btn": wb.add_format({
            "font_name": f, "font_size": 10, "bold": True,
            "font_color": "#FFFFFF", "bg_color": COMAU_RED,
            "align": "center", "valign": "vcenter", "border": 1,
        }),

        # Time grid headers
        "time_hdr": wb.add_format({
            "font_name": f, "font_size": 8, "bold": True,
            "bg_color": "#F2F4F8", "border": 1, "border_color": "#DCE2E6",
            "align": "center", "valign": "vcenter", "rotation": 90, "num_format": "0.##",
        }),
        "time_hdr_major": wb.add_format({
            "font_name": f, "font_size": 8, "bold": True,
            "bg_color": "#D6E4F0", "border": 1, "border_color": "#B8CCE4",
            "align": "center", "valign": "vcenter", "rotation": 90, "num_format": "0.##",
        }),
    }


def _resource_hex_map(model: SequenceModel) -> Dict[str, str]:
    return {
        r.id: (r.color or _DEFAULT_COLOURS[i % len(_DEFAULT_COLOURS)])
        for i, r in enumerate(model.resources)
    }


def _resource_block_formats(
    wb: xlsxwriter.Workbook,
    hex_map: Dict[str, str],
) -> Dict[str, object]:
    return {
        res_id: wb.add_format({
            "bg_color": colour,
            "border": 1,
            "border_color": _darken(colour),
        })
        for res_id, colour in hex_map.items()
    }


# ---------------------------------------------------------------------------
# Summary Sheet (Executive Master Dashboard)
# ---------------------------------------------------------------------------

def _write_summary_sheet(
    wb: xlsxwriter.Workbook,
    model: SequenceModel,
    fmt: Dict,
    hex_map: Dict[str, str],
) -> None:
    ws = wb.add_worksheet("Overall_Sequence")
    ws.set_zoom(90)
    ws.set_tab_color(COMAU_RED)

    # Column dimensions
    ws.set_column(0, 0, 4)    # Margin
    ws.set_column(1, 1, 20)   # Resource name
    ws.set_column(2, 2, 11)   # Start Time
    ws.set_column(3, 3, 11)   # End Time
    ws.set_column(4, 4, 11)   # Duration
    ws.set_column(5, 5, 14)   # Drill-down link
    ws.set_column(6, 6, 3)    # Spacer
    ws.set_column(7, 15, 8)   # Gantt Chart area

    # --- Header Banner with Logo ---
    ws.set_row(0, 36)
    ws.set_row(1, 18)

    # Fill banner background from col B to col O
    for c in range(1, 16):
        ws.write(0, c, "", fmt["banner"])
        ws.write(1, c, "", fmt["banner_sub"])

    ws.write(0, 1, "  COMAU AUTOMATION SEQUENCE SIMULATION", fmt["banner"])
    ws.write(1, 1, "  Master Gantt & Line Balancing Dashboard", fmt["banner_sub"])

    # Insert Comau logo at top-left margin if present
    logo_path = get_logo_path()
    if logo_path.exists():
        ws.insert_image("A1", str(logo_path), {
            "x_offset": 6, "y_offset": 3,
            "x_scale": 0.095, "y_scale": 0.095,
            "object_position": 1,
        })

    # --- KPI Metrics calculation ---
    takt_time  = model.settings.takt_time
    cycle_time = max((t.end_time for t in model.tasks), default=0.0)
    utilization = (cycle_time / takt_time * 100.0) if takt_time > 0 else 0.0
    is_balanced = cycle_time <= takt_time

    # --- KPI Metric Cards (Rows 3 & 4) ---
    ws.set_row(3, 16)
    ws.set_row(4, 28)

    # Card 1: Cycle Time
    ws.write(3, 1, "TOTAL CYCLE TIME", fmt["kpi_label"])
    ws.write(4, 1, f"{cycle_time:.1f} s", fmt["kpi_value"])

    # Card 2: Takt Time
    ws.write(3, 2, "LINE TAKT TIME", fmt["kpi_label"])
    ws.write(4, 2, f"{takt_time:.1f} s", fmt["kpi_value"])

    # Card 3: Line Utilization
    ws.write(3, 3, "UTILIZATION", fmt["kpi_label"])
    ws.write(4, 3, f"{utilization:.1f}%", fmt["kpi_value"])

    # Card 4: Status Badge
    ws.write(3, 4, "LINE BALANCE", fmt["kpi_label"])
    if is_balanced:
        ws.write(4, 4, "✓ BALANCED", fmt["kpi_status_ok"])
    else:
        ws.write(4, 4, "⚠ OVER TAKT", fmt["kpi_status_over"])

    # Card 5: Counts
    ws.write(3, 5, "TASKS / RESOURCES", fmt["kpi_label"])
    ws.write(4, 5, f"{len(model.tasks)} / {len(model.resources)}", fmt["kpi_value"])

    # --- Resource Summary Table ---
    start_row = 7
    ws.set_row(start_row, 24)
    ws.write(start_row, 1, "Resource",        fmt["th_navy_left"])
    ws.write(start_row, 2, "Start (s)",       fmt["th_navy"])
    ws.write(start_row, 3, "End (s)",         fmt["th_navy"])
    ws.write(start_row, 4, "Active Span (s)", fmt["th_navy"])
    ws.write(start_row, 5, "Drill-Down",      fmt["th_navy"])

    data_rows: List[Tuple[str, float, float, float]] = []
    for resource in model.resources:
        res_tasks = model.tasks_for_resource(resource.id)
        if not res_tasks:
            continue
        min_start = min(t.start_time for t in res_tasks)
        max_end   = max(t.end_time   for t in res_tasks)
        duration  = max_end - min_start
        data_rows.append((resource.id, min_start, max_end, duration))

    for idx, (res_id, r_start, r_end, r_dur) in enumerate(data_rows, start=start_row + 1):
        ws.set_row(idx, 20)
        ws.write(idx, 1, res_id,  fmt["cell_left"])
        ws.write(idx, 2, r_start, fmt["cell_num"])
        ws.write(idx, 3, r_end,   fmt["cell_num"])
        ws.write(idx, 4, r_dur,   fmt["cell_num"])
        ws.write_url(
            idx, 5,
            f"internal:'{res_id}'!A1",
            fmt["link_btn"],
            string="▶ Open Grid",
        )

    if not data_rows:
        return

    last_data_row = start_row + len(data_rows)

    # --- Stacked Bar Master Gantt Chart ---
    chart = wb.add_chart({"type": "bar", "subtype": "stacked"})

    # Series 1: Invisible base (Start Time offset)
    chart.add_series({
        "name":       "Start Offset",
        "categories": ["Overall_Sequence", start_row + 1, 1, last_data_row, 1],
        "values":     ["Overall_Sequence", start_row + 1, 2, last_data_row, 2],
        "fill":       {"none": True},
        "border":     {"none": True},
    })

    # Individual Series per Resource (each gets its brand color)
    for row_idx, (res_id, _, _, _) in enumerate(data_rows, start=start_row + 1):
        colour = hex_map.get(res_id, _DEFAULT_COLOURS[0])
        chart.add_series({
            "name":       res_id,
            "categories": ["Overall_Sequence", start_row + 1, 1, last_data_row, 1],
            "values":     ["Overall_Sequence", row_idx, 4, row_idx, 4],
            "fill":       {"color": colour},
            "border":     {"color": _darken(colour)},
        })

    chart.set_title({
        "name": "Overall Automation Sequence — Master Gantt",
        "name_font": {"name": "Segoe UI", "size": 11, "bold": True},
    })
    chart.set_x_axis({
        "name": "Time (Seconds)",
        "name_font": {"name": "Segoe UI", "size": 9, "bold": True},
        "num_font":  {"name": "Segoe UI", "size": 9},
        "major_gridlines": {"visible": True, "line": {"color": "#E5E5E5"}},
    })
    chart.set_y_axis({
        "reverse": True,
        "num_font": {"name": "Segoe UI", "size": 9, "bold": True},
    })
    chart.set_legend({
        "position": "bottom",
        "font": {"name": "Segoe UI", "size": 9},
    })
    chart.set_size({"width": 640, "height": 320})
    chart.set_chartarea({
        "border": {"color": "#DCE2E6"},
        "fill":   {"color": "#FFFFFF"},
    })

    ws.insert_chart("G8", chart, {"x_offset": 10, "y_offset": 0})


# ---------------------------------------------------------------------------
# Granular Resource Sheet (Micro-level timing grid)
# ---------------------------------------------------------------------------

def _write_resource_sheet(
    wb: xlsxwriter.Workbook,
    model: SequenceModel,
    resource: Resource,
    fmt: Dict,
    block_map: Dict[str, object],
    hex_map: Dict[str, str],
) -> None:
    ws = wb.add_worksheet(resource.id)
    ws.set_zoom(85)

    # Set tab color to match resource's Gantt bar color!
    tab_color = hex_map.get(resource.id, _DEFAULT_COLOURS[0])
    ws.set_tab_color(tab_color)

    res_tasks = model.tasks_for_resource(resource.id)
    if not res_tasks:
        ws.write(0, 0, f"No tasks assigned to {resource.id}", fmt["th_navy_left"])
        return

    inc   = model.settings.time_increment
    max_t = max(t.end_time for t in res_tasks)
    n_cols = int(max_t / inc) + 3

    # Navigation & Title banner row
    ws.set_row(0, 32)
    ws.set_column(0, 0, 20)  # Back button / Task ID
    ws.set_column(1, 1, 24)  # Task Name
    ws.set_column(2, 2, 9)   # Start
    ws.set_column(3, 3, 9)   # End
    ws.set_column(4, 4, 9)   # Dur
    ws.set_column(5, 5 + n_cols, _COL_W_GRID)

    # Navigation button back to Master Gantt
    ws.write_url(0, 0, "internal:'Overall_Sequence'!A1", fmt["back_btn"], string="⮌ Master Gantt")
    ws.write(0, 1, f"Resource: {resource.id}", fmt["th_navy_left"])
    ws.write(0, 2, f"{len(res_tasks)} Tasks", fmt["th_navy"])
    ws.write(0, 3, f"Span: {max_t:.1f}s", fmt["th_navy"])

    # Header row for columns & time increments
    header_row = 2
    ws.set_row(header_row, 50)
    ws.write(header_row, 0, "Task ID",      fmt["th_navy_left"])
    ws.write(header_row, 1, "Task Name",    fmt["th_navy_left"])
    ws.write(header_row, 2, "Start (s)",    fmt["th_navy"])
    ws.write(header_row, 3, "End (s)",      fmt["th_navy"])
    ws.write(header_row, 4, "Dur (s)",      fmt["th_navy"])

    # Time scale headers (every 5s highlighted with a tint)
    for col_idx in range(n_cols):
        t_val = round(col_idx * inc, 10)
        is_major = (col_idx % 5 == 0)
        hdr_format = fmt["time_hdr_major"] if is_major else fmt["time_hdr"]
        ws.write(header_row, col_idx + 5, t_val, hdr_format)

    # Freeze panes: keep task labels & time headers visible
    ws.freeze_panes(header_row + 1, 5)

    # Task rows + conditional formatting
    block_fmt = block_map[resource.id]

    for r_idx, task in enumerate(res_tasks, start=header_row + 1):
        ws.set_row(r_idx, 20)
        ws.write(r_idx, 0, task.id,              fmt["cell_left"])
        ws.write(r_idx, 1, task.name or task.id, fmt["cell_left"])
        ws.write(r_idx, 2, task.start_time,      fmt["cell_num"])
        ws.write(r_idx, 3, task.end_time,        fmt["cell_num"])
        ws.write(r_idx, 4, task.duration,        fmt["cell_num"])

        last_col = xlsxwriter.utility.xl_col_to_name(n_cols + 4)
        grid_range = f"F{r_idx + 1}:{last_col}{r_idx + 1}"
        formula    = f"=AND(F${header_row + 1}>=$C{r_idx + 1},F${header_row + 1}<$D{r_idx + 1})"

        ws.conditional_format(
            grid_range,
            {"type": "formula", "criteria": formula, "format": block_fmt},
        )


# ---------------------------------------------------------------------------
# Helper: darken hex colour for border contrast
# ---------------------------------------------------------------------------

def _darken(hex_colour: str, factor: float = 0.72) -> str:
    h = hex_colour.lstrip("#")
    if len(h) != 6:
        return hex_colour
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r2, g2, b2 = int(r * factor), int(g * factor), int(b * factor)
    return f"#{r2:02X}{g2:02X}{b2:02X}"
