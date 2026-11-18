# Automation Sequence Utility Specification

## Project Overview
Develop a Python-based utility that allows for the easy creation of automation sequences, outputting an interactive Excel document. The tool will calculate task timings based on user-defined inputs, dependencies, and interlocks, and visualize them using a combination of a macro-level Gantt chart and micro-level conditionally formatted grids.

**Target Output File:** `honda_seq_dev_111826.xlsx`

## Core Technologies
*   **Language:** Python
*   **Dependency/Scheduling Engine:** `networkx` (to resolve the Directed Acyclic Graph of tasks and calculate start/end times).
*   **Excel Generation Engine:** `XlsxWriter` (for writing charts, conditional formatting, grouping, and internal hyperlinks).

## Input Requirements
The user will need to input the following global and task-level variables (format TBD, e.g., JSON, YAML, or an input Excel template):
1.  **Global Parameters:** Available time, line rate (takt time).
2.  **Resources:** List of available resources (e.g., Tool_A, Operator_1, Robot_B).
3.  **Tasks / Sub-tasks:** 
    *   Task ID / Name
    *   Assigned Resource
    *   Duration
    *   Predecessors (Finish-to-Start dependencies)
    *   Interlocks (Start-to-Start dependencies / parallel operations)

## Processing Logic
Treat every sub-task as a node in a graph.
*   **Finish-to-Start (FS):** Task B cannot start until Task A finishes.
*   **Start-to-Start (SS):** Task B must start exactly when Task A starts.
*   `Start_Time(Task) = Max(End_Time(FS Predecessors), Start_Time(SS Predecessors))`
*   `End_Time(Task) = Start_Time(Task) + Duration`

## Output Excel Structure

### 1. Summary Page (Overall Sequence)
*   **Visualization:** An interactive Gantt chart using a Stacked Bar Chart.
    *   Series 1: "Start Time" (Fill and border set to 'None' for invisible padding).
    *   Series 2: "Duration" (Colored by resource type).
*   **Grouping:** Data is grouped by overall Resource, showing the macro operational blocks rather than individual micro-tasks.
*   **Interactivity:** A column next to the chart lists the resources. Each resource name is formatted as an internal Excel hyperlink pointing to its corresponding granular tab.

### 2. Granular Resource Pages (Drill-Down Tabs)
*   **Visualization:** Conditionally formatted grids (not standard charts).
    *   Columns: Time increments (e.g., 0.1s, 1s).
    *   Rows: Individual sub-tasks for that specific resource.
*   **Formatting Logic:** Use formula `=AND(Column_Time >= Start_Time, Column_Time <= End_Time)` to fill cells and create a highly granular block view.
*   **Navigation:** A "Back to Summary" hyperlink at the bottom of the tasks.

## Reference Starter Code for XlsxWriter Implementation
```python
import xlsxwriter

# Setup
workbook = xlsxwriter.Workbook("honda_seq_dev_111826.xlsx")
summary_sheet = workbook.add_worksheet("Overall_Sequence")
header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})
time_block_format = workbook.add_format({'bg_color': '#4CAF50'})

# ... Agent to implement networkx logic and dynamic generation based on this architecture ...

workbook.close()
```