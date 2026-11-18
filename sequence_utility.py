import xlsxwriter
import datetime

# 1. Define Dummy Computed Data (Post-DAG Resolution)
# In production, this data is calculated via your scheduling engine (e.g., NetworkX)
global_settings = {"line_rate": 60, "available_time": 3600}
resources = ["Operator_1", "Robot_A", "Tool_Fixture"]

tasks = [
    {"id": "Op1_Load", "resource": "Operator_1", "start": 0, "duration": 5, "end": 5},
    {"id": "RobA_Weld1", "resource": "Robot_A", "start": 5, "duration": 12, "end": 17},
    {"id": "Fix_Clamp", "resource": "Tool_Fixture", "start": 5, "duration": 2, "end": 7},
]

# 2. Initialize Workbook
workbook = xlsxwriter.Workbook("honda_seq_dev_111826.xlsx")
summary_sheet = workbook.add_worksheet("Overall_Sequence")

# Formatting
header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})
time_block_format = workbook.add_format({'bg_color': '#4CAF50'}) # Green Gantt block

# 3. Build Summary Page Data (For Stacked Bar Chart)
summary_sheet.write('A1', 'Resource', header_format)
summary_sheet.write('B1', 'Start Time', header_format)
summary_sheet.write('C1', 'Duration', header_format)
summary_sheet.write('D1', 'Detailed View', header_format)

row = 1
for res in resources:
    # Aggregating start/duration for the summary view
    res_tasks = [t for t in tasks if t['resource'] == res]
    if res_tasks:
        min_start = min(t['start'] for t in res_tasks)
        total_duration = max(t['end'] for t in res_tasks) - min_start
        
        summary_sheet.write(row, 0, res)
        summary_sheet.write(row, 1, min_start)
        summary_sheet.write(row, 2, total_duration)
        # Create interactive drill-down hyperlink
        summary_sheet.write_url(row, 3, f"internal:'{res}'!A1", link_format, string="View Details")
        row += 1

# 4. Generate the Summary Gantt Chart
gantt_chart = workbook.add_chart({'type': 'bar', 'subtype': 'stacked'})
gantt_chart.add_series({
    'name': 'Start Time',
    'categories': ['Overall_Sequence', 1, 0, row-1, 0],
    'values': ['Overall_Sequence', 1, 1, row-1, 1],
    'fill': {'none': True}, # Invisible base
})
gantt_chart.add_series({
    'name': 'Duration',
    'categories': ['Overall_Sequence', 1, 0, row-1, 0],
    'values': ['Overall_Sequence', 1, 2, row-1, 2],
    'fill': {'color': '#1F4E78'},
})
gantt_chart.set_title({'name': 'Overall Sequence Master Gantt'})
gantt_chart.set_x_axis({'name': 'Time (Seconds)'})
gantt_chart.set_y_axis({'reverse': True}) # Puts first task at the top
summary_sheet.insert_chart('F2', gantt_chart)

# 5. Build Granular Resource Sheets (Conditional Formatting Gantt)
for res in resources:
    res_sheet = workbook.add_worksheet(res)
    res_sheet.write('A1', 'Task ID', header_format)
    res_sheet.write('B1', 'Start', header_format)
    res_sheet.write('C1', 'End', header_format)
    
    # Write time scale headers (0 to 30 seconds for example)
    max_time = 30 
    for col in range(max_time):
        res_sheet.write(0, col + 3, col)
        res_sheet.set_column(col + 3, col + 3, 2.5) # narrow columns for grid look
        
    res_tasks = [t for t in tasks if t['resource'] == res]
    r_row = 1
    for t in res_tasks:
        res_sheet.write(r_row, 0, t['id'])
        res_sheet.write(r_row, 1, t['start'])
        res_sheet.write(r_row, 2, t['end'])
        
        # Apply conditional formatting across the time grid
        grid_range = f"D{r_row+1}:AH{r_row+1}"
        formula = f"=AND(D$1>=$B{r_row+1}, D$1<=$C{r_row+1})"
        res_sheet.conditional_format(grid_range, {'type': 'formula',
                                                  'criteria': formula,
                                                  'format': time_block_format})
        r_row += 1
        
    # Back button to summary
    res_sheet.write_url(r_row + 2, 0, "internal:'Overall_Sequence'!A1", link_format, string="Back to Summary")

workbook.close()