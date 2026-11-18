"""
make_standalone.py — Generates a self-contained Excel macro workbook (.xlsm)
with Comau branding and in-workbook tab generation.

The output .xlsm file:
  • Contains input sheets (Settings / Resources / Tasks) with Comau branding,
    color swatches, and example weld sequence data.
  • Contains a hidden "_py" sheet with the full Python source code embedded.
  • Contains a VBA module "SimSequence" that:
      1. Extracts the Python engine into %TEMP%\SimSeq\
      2. Executes main_embedded.py against the workbook
      3. Copies generated tabs (Overall_Sequence, Operator_1, Robot_A, etc.)
         directly INTO ThisWorkbook in real time!
  • Contains a styled "▶ RUN SEQUENCE SIMULATION" button on the Settings sheet.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl
from openpyxl import Workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from sim_sequence.assets import get_logo_path
from sim_sequence.embedder import collect_sources, source_rows

# ---------------------------------------------------------------------------
# Comau Brand Colors & Styles
# ---------------------------------------------------------------------------
COMAU_RED       = "C8102E"   # Primary brand accent
COMAU_NAVY      = "0B2341"   # Executive header navy
COMAU_SLATE     = "1A2E40"   # Secondary header slate
COMAU_LIGHT_BG  = "F4F7FA"   # Card / alternate row background
COMAU_BORDER    = "D0D7DE"   # Card border
KEY_FILL_HEX    = "D6E4F0"

# ---------------------------------------------------------------------------
# VBA source injected into the workbook
# ---------------------------------------------------------------------------
VBA_CODE = r"""
Option Explicit

' ============================================================
'  Comau Automation Sequence Utility — Standalone Runner
'  Generates and refreshes sequence tabs directly in this workbook!
' ============================================================

Sub RunSequence()
    Dim tmpDir      As String
    Dim logPath     As String
    Dim pyScript    As String
    Dim wbPath      As String
    Dim tempReport  As String
    Dim oShell      As Object
    Dim fso         As Object
    Dim q           As String
    Dim cmd         As String
    Dim retCode     As Long
    Dim batPath     As String
    Dim batText     As String

    q = Chr(34)
    tmpDir = Environ("TEMP") & "\SimSeq\"
    logPath = tmpDir & "run.log"
    pyScript = tmpDir & "main_embedded.py"
    batPath = tmpDir & "run.bat"
    tempReport = tmpDir & "temp_report.xlsx"
    wbPath = ThisWorkbook.FullName

    Set fso = CreateObject("Scripting.FileSystemObject")
    Set oShell = CreateObject("WScript.Shell")

    ' Delete previous temporary report if present
    If fso.FileExists(tempReport) Then
        On Error Resume Next
        fso.DeleteFile tempReport, True
        On Error GoTo 0
    End If

    ' ── 1. Reconstruct Python package in temp dir ──────────────────────
    If Not fso.FolderExists(tmpDir) Then fso.CreateFolder tmpDir
    If Not fso.FolderExists(tmpDir & "sim_sequence") Then fso.CreateFolder tmpDir & "sim_sequence"

    ExtractPython tmpDir

    ' ── 2. Create runner batch file (handles UTF-8 and Python detection) ──
    batText = "@echo off" & vbCrLf & _
              "chcp 65001 >nul" & vbCrLf & _
              "set PYTHONIOENCODING=utf-8" & vbCrLf & _
              "where py >nul 2>&1" & vbCrLf & _
              "if %errorlevel% equ 0 (" & vbCrLf & _
              "    py %1 %2" & vbCrLf & _
              ") else (" & vbCrLf & _
              "    python %1 %2" & vbCrLf & _
              ")" & vbCrLf & _
              "exit /b %errorlevel%" & vbCrLf
    SaveUtf8File batPath, batText

    ' ── 3. Execute runner batch file ───────────────────────────────────
    cmd = "cmd /c " & q & q & batPath & q & " " & q & pyScript & q & " " & q & wbPath & q & " > " & q & logPath & q & " 2>&1" & q
    retCode = oShell.Run(cmd, 0, True)   ' 0 = hidden window, True = wait

    ' ── 4. Import generated tabs into ThisWorkbook ─────────────────────
    If retCode = 0 And fso.FileExists(tempReport) Then
        ImportGeneratedSheets tempReport

        Dim msg As String
        msg = "Sequence simulation completed successfully!" & vbCrLf & vbCrLf & _
              "All sequence tabs have been generated and updated directly in this workbook:" & vbCrLf & _
              "  • Overall_Sequence (Master Gantt & KPI Dashboard)" & vbCrLf & _
              "  • Granular resource drill-down tabs" & vbCrLf & vbCrLf & _
              "Switched to Overall_Sequence dashboard."
        MsgBox msg, vbInformation, "Comau Automation Sequence Utility"
    Else
        MsgBox "Simulation pipeline failed (exit code " & retCode & ")." & vbCrLf & vbCrLf & _
               ReadFile(logPath), vbCritical, "Comau Automation Sequence Utility — Error"
    End If
End Sub

' ── In-Workbook Sheet Importer ─────────────────────────────────────────────

Private Sub ImportGeneratedSheets(tempReportPath As String)
    Dim tempWb        As Workbook
    Dim ws            As Worksheet
    Dim prevAlerts    As Boolean
    Dim prevUpdating  As Boolean
    Dim sheetNames()  As String
    Dim numSheets     As Long
    Dim i             As Long
    Dim sName         As String

    prevUpdating = Application.ScreenUpdating
    prevAlerts = Application.DisplayAlerts
    Application.ScreenUpdating = False
    Application.DisplayAlerts = False

    ' Open temporary report workbook invisibly
    Set tempWb = Workbooks.Open(tempReportPath, ReadOnly:=True)

    numSheets = tempWb.Sheets.Count
    ReDim sheetNames(1 To numSheets)
    For i = 1 To numSheets
        sheetNames(i) = tempWb.Sheets(i).Name
    Next i

    ' Delete existing sheets in ThisWorkbook matching incoming names
    For i = 1 To numSheets
        sName = sheetNames(i)
        DeleteSheetIfExists sName
    Next i

    ' Copy each sheet into ThisWorkbook after the last sheet
    For i = 1 To numSheets
        tempWb.Sheets(sheetNames(i)).Copy After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count)
    Next i

    tempWb.Close SaveChanges:=False

    ' Clean up temporary report file
    On Error Resume Next
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    fso.DeleteFile tempReportPath, True
    On Error GoTo 0

    ' Activate Master Gantt sheet
    On Error Resume Next
    ThisWorkbook.Sheets("Overall_Sequence").Activate
    On Error GoTo 0

    Application.DisplayAlerts = prevAlerts
    Application.ScreenUpdating = prevUpdating
End Sub

Private Sub DeleteSheetIfExists(sName As String)
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets(sName)
    If Not ws Is Nothing Then
        ws.Delete
    End If
    On Error GoTo 0
End Sub

' ── Helpers ────────────────────────────────────────────────────────────────

Private Sub ExtractPython(tmpDir As String)
    Dim ws          As Worksheet
    Dim lastRow     As Long
    Dim i           As Long
    Dim curFile     As String
    Dim colA        As String
    Dim colB        As String
    Dim fileContent As String

    Set ws = ThisWorkbook.Sheets("_py")
    lastRow = ws.UsedRange.Row + ws.UsedRange.Rows.Count - 1
    curFile = ""
    fileContent = ""

    For i = 1 To lastRow
        colA = Trim(CStr(ws.Cells(i, 1).Value))
        colB = CStr(ws.Cells(i, 2).Value)

        If colA <> "" Then
            If curFile <> "" Then
                SaveUtf8File tmpDir & curFile, fileContent
            End If
            curFile = Replace(colA, "/", "\")
            fileContent = ""
        Else
            fileContent = fileContent & colB & vbCrLf
        End If
    Next i

    If curFile <> "" Then
        SaveUtf8File tmpDir & curFile, fileContent
    End If
End Sub

Private Sub SaveUtf8File(fullPath As String, content As String)
    Dim fso        As Object
    Dim parentDir  As String
    Dim stm        As Object

    Set fso = CreateObject("Scripting.FileSystemObject")
    parentDir = fso.GetParentFolderName(fullPath)
    If Not fso.FolderExists(parentDir) Then
        fso.CreateFolder parentDir
    End If

    Set stm = CreateObject("ADODB.Stream")
    stm.Type = 2 ' adTypeText
    stm.Charset = "utf-8"
    stm.Open
    stm.WriteText content
    stm.SaveToFile fullPath, 2 ' adSaveCreateOverWrite
    stm.Close
End Sub

Private Function ReadFile(path As String) As String
    Dim fso  As Object
    Dim ts   As Object

    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(path) Then
        ReadFile = "(log file not found)"
        Exit Function
    End If

    Set ts = fso.OpenTextFile(path, 1, False)
    If Not ts.AtEndOfStream Then
        ReadFile = ts.ReadAll
    Else
        ReadFile = "(log file was empty)"
    End If
    ts.Close

    If Len(ReadFile) > 1500 Then
        ReadFile = Left(ReadFile, 1500) & vbCrLf & "... (truncated)"
    End If
End Function
"""

# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------
FNT_FAMILY = "Segoe UI"
HDR_FILL   = PatternFill("solid", fgColor=COMAU_SLATE)
HDR_FONT   = Font(bold=True, color="FFFFFF", name=FNT_FAMILY, size=10)
HDR_ALIGN  = Alignment(horizontal="center", vertical="center", wrap_text=True)

BANNER_FILL = PatternFill("solid", fgColor=COMAU_NAVY)
BANNER_FONT = Font(bold=True, color="FFFFFF", name=FNT_FAMILY, size=13)
SUB_FONT    = Font(italic=True, color="D0D7DE", name=FNT_FAMILY, size=9)

CARD_FILL   = PatternFill("solid", fgColor=COMAU_LIGHT_BG)
CARD_HDR_FONT = Font(bold=True, color="0B2341", name=FNT_FAMILY, size=10)

KEY_FILL   = PatternFill("solid", fgColor=KEY_FILL_HEX)
KEY_FONT   = Font(bold=True, name=FNT_FAMILY, size=10)
VAL_FONT   = Font(name=FNT_FAMILY, size=10)
VAL_ALIGN  = Alignment(horizontal="left", vertical="center")
NOTE_FONT  = Font(italic=True, color="5A6B7C", name=FNT_FAMILY, size=9)

THIN_SIDE  = Side(style="thin", color="D0D7DE")
THIN_BORDER= Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)

LINK_FONT  = Font(color="0056B3", underline="single", name=FNT_FAMILY, size=9, bold=True)

EXAMPLE_SETTINGS = [
    ("available_time", 3600,  "seconds", "Total shift/cycle time budget"),
    ("takt_time",      60,    "seconds", "Target line rate / takt cycle budget"),
    ("time_increment", 1,     "seconds", "Time scale resolution on granular resource grids"),
    ("output_file",    "outputs/honda_seq_dev_111826.xlsx", "path", "Optional backup report path"),
]

EXAMPLE_RESOURCES = [
    ("Operator_1",   "#1F4E78"),
    ("Robot_A",      "#2E7D32"),
    ("Robot_B",      "#E65100"),
    ("Tool_Fixture", "#6A1B9A"),
]

EXAMPLE_TASKS = [
    ("Op1_GetPart",    "Get Part from Rack",         "Operator_1",   4,  "",                       ""),
    ("Op1_Load",       "Load Part to Fixture",        "Operator_1",   5,  "Op1_GetPart",            ""),
    ("Op1_SafetyCheck","Safety Check / Clear Zone",   "Operator_1",   2,  "Op1_Load",               ""),
    ("Op1_Unload",     "Unload Finished Part",        "Operator_1",   4,  "RobA_Weld2, RobB_Weld2", ""),
    ("RobA_MoveIn",    "Robot A Move-In",             "Robot_A",      3,  "Op1_SafetyCheck",        ""),
    ("RobA_Weld1",     "Robot A — Weld Pass 1",       "Robot_A",     10,  "RobA_MoveIn",            ""),
    ("RobA_Reposition","Robot A — Reposition",        "Robot_A",      2,  "RobA_Weld1",             ""),
    ("RobA_Weld2",     "Robot A — Weld Pass 2",       "Robot_A",      8,  "RobA_Reposition",        ""),
    ("RobA_MoveOut",   "Robot A Move-Out",            "Robot_A",      3,  "RobA_Weld2",             ""),
    ("RobB_MoveIn",    "Robot B Move-In",             "Robot_B",      3,  "Op1_SafetyCheck",        ""),
    ("RobB_Weld1",     "Robot B — Weld Pass 1",       "Robot_B",     10,  "RobB_MoveIn",            "RobA_Weld1"),
    ("RobB_Reposition","Robot B — Reposition",        "Robot_B",      2,  "RobB_Weld1",             ""),
    ("RobB_Weld2",     "Robot B — Weld Pass 2",       "Robot_B",      8,  "RobB_Reposition",        "RobA_Weld2"),
    ("RobB_MoveOut",   "Robot B Move-Out",            "Robot_B",      3,  "RobB_Weld2",             ""),
    ("Fix_Clamp",      "Clamp Part",                  "Tool_Fixture",  2,  "Op1_Load",               ""),
    ("Fix_Hold",       "Hold During Weld",            "Tool_Fixture", 24,  "Fix_Clamp",              ""),
    ("Fix_Unclamp",    "Unclamp Part",                "Tool_Fixture",  2,  "RobA_MoveOut, RobB_MoveOut", ""),
]


# ---------------------------------------------------------------------------
# Step 1 — build intermediate .xlsx using openpyxl
# ---------------------------------------------------------------------------

def _build_xlsx(path: Path, blank: bool, py_rows: list) -> None:
    wb = Workbook()
    del wb["Sheet"]

    _sheet_settings(wb, blank)
    _sheet_resources(wb, blank)
    _sheet_tasks(wb, blank)
    _sheet_py_source(wb, py_rows)

    wb.save(str(path))


def _sheet_settings(wb: Workbook, blank: bool) -> None:
    ws = wb.create_sheet("Settings")
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = COMAU_NAVY

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 46

    # Header Banner (Row 1 & 2)
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 18

    for c in range(1, 5):
        cell1 = ws.cell(row=1, column=c, value="")
        cell1.fill = BANNER_FILL
        cell2 = ws.cell(row=2, column=c, value="")
        cell2.fill = BANNER_FILL

    ws.cell(row=1, column=1, value="  COMAU AUTOMATION SEQUENCE UTILITY").font = BANNER_FONT
    ws.cell(row=2, column=1, value="  Simulation Console & Launchpad").font = SUB_FONT

    # Add Comau logo if present
    logo_path = get_logo_path()
    if logo_path.exists():
        try:
            img = OpenpyxlImage(str(logo_path))
            img.width = 44
            img.height = 48
            ws.add_image(img, "D1")
        except Exception:
            pass

    # Quick Action Buttons & Links (Row 4)
    ws.row_dimensions[4].height = 34
    btn_note = ws.cell(row=4, column=1, value="[ ▶ RUN SEQUENCE SIMULATION ]")
    btn_note.font = Font(name=FNT_FAMILY, size=10, bold=True, color="FFFFFF")
    btn_note.fill = PatternFill("solid", fgColor=COMAU_RED)
    btn_note.alignment = Alignment(horizontal="center", vertical="center")
    btn_note.border = THIN_BORDER

    # Navigation links to other sheets
    l1 = ws.cell(row=4, column=2, value="📊 View Master Gantt")
    l1.font = LINK_FONT; l1.alignment = Alignment(horizontal="center", vertical="center")
    l1.hyperlink = "#'Overall_Sequence'!A1"

    l2 = ws.cell(row=4, column=3, value="📋 Tasks")
    l2.font = LINK_FONT; l2.alignment = Alignment(horizontal="center", vertical="center")
    l2.hyperlink = "#'Tasks'!A1"

    l3 = ws.cell(row=4, column=4, value="🔧 Resources")
    l3.font = LINK_FONT; l3.alignment = Alignment(horizontal="left", vertical="center")
    l3.hyperlink = "#'Resources'!A1"

    # Section Header: Parameters (Row 6)
    ws.row_dimensions[6].height = 22
    for c, text in enumerate(["Parameter", "Value", "Unit", "Description"], start=1):
        cell = ws.cell(row=6, column=c, value=text)
        cell.font = HDR_FONT; cell.fill = HDR_FILL; cell.border = THIN_BORDER; cell.alignment = HDR_ALIGN

    rows = EXAMPLE_SETTINGS if not blank else [
        ("available_time", 3600, "seconds", "Total shift/cycle time budget"),
        ("takt_time",      60,   "seconds", "Target line rate / takt cycle budget"),
        ("time_increment", 1,    "seconds", "Time scale resolution on granular resource grids"),
        ("output_file",    "outputs/honda_seq_dev_111826.xlsx", "path", "Optional backup report path"),
    ]

    for r, (key, val, unit, desc) in enumerate(rows, start=7):
        ws.row_dimensions[r].height = 20
        kc = ws.cell(row=r, column=1, value=key)
        kc.font = KEY_FONT; kc.fill = KEY_FILL; kc.border = THIN_BORDER; kc.alignment = VAL_ALIGN

        vc = ws.cell(row=r, column=2, value=val)
        vc.font = VAL_FONT; vc.alignment = VAL_ALIGN; vc.border = THIN_BORDER

        uc = ws.cell(row=r, column=3, value=unit)
        uc.font = NOTE_FONT; uc.alignment = Alignment(horizontal="center", vertical="center"); uc.border = THIN_BORDER

        dc = ws.cell(row=r, column=4, value=desc)
        dc.font = NOTE_FONT; dc.border = THIN_BORDER

    # Section: Quick Reference Card (Rows 12-16)
    ref_start = 12
    ws.row_dimensions[ref_start].height = 22
    ref_hdr = ws.cell(row=ref_start, column=1, value="DEPENDENCY RULES QUICK REFERENCE")
    ref_hdr.font = CARD_HDR_FONT; ref_hdr.fill = CARD_FILL; ref_hdr.border = THIN_BORDER

    for c in range(2, 5):
        cell = ws.cell(row=ref_start, column=c, value="")
        cell.fill = CARD_FILL; cell.border = THIN_BORDER

    guidance = [
        ("Finish-to-Start (FS)", "Predecessors_FS", "Task starts immediately AFTER predecessor finishes."),
        ("Start-to-Start (SS)",  "Predecessors_SS", "Task starts SIMULTANEOUSLY with predecessor (e.g. welding clamp or dual robots)."),
        ("Multiple Dependencies", "Comma-separated", "e.g. 'RobA_Weld2, RobB_Weld2' — Task starts when ALL conditions are met."),
    ]
    for idx, (dep_type, col_name, rule) in enumerate(guidance, start=ref_start + 1):
        ws.row_dimensions[idx].height = 20
        c1 = ws.cell(row=idx, column=1, value=dep_type)
        c1.font = Font(name=FNT_FAMILY, size=9, bold=True); c1.border = THIN_BORDER
        c2 = ws.cell(row=idx, column=2, value=col_name)
        c2.font = Font(name=FNT_FAMILY, size=9, italic=True); c2.border = THIN_BORDER
        c3 = ws.cell(row=idx, column=3, value="")
        c3.border = THIN_BORDER
        c4 = ws.cell(row=idx, column=4, value=rule)
        c4.font = NOTE_FONT; c4.border = THIN_BORDER

    ws.freeze_panes = "A3"


def _sheet_resources(wb: Workbook, blank: bool) -> None:
    ws = wb.create_sheet("Resources")
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = COMAU_SLATE

    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 14

    ws.row_dimensions[1].height = 24
    for col, text in enumerate(["Resource ID", "Color (Hex)", "Gantt Preview"], start=1):
        c = ws.cell(row=1, column=col, value=text)
        c.font = HDR_FONT; c.fill = HDR_FILL; c.border = THIN_BORDER; c.alignment = HDR_ALIGN

    data = EXAMPLE_RESOURCES if not blank else []
    for r, (rid, colour) in enumerate(data, start=2):
        ws.row_dimensions[r].height = 20
        ic = ws.cell(row=r, column=1, value=rid)
        ic.font = VAL_FONT; ic.border = THIN_BORDER

        cc = ws.cell(row=r, column=2, value=colour)
        cc.font = VAL_FONT; cc.border = THIN_BORDER

        hex_clean = colour.lstrip("#")
        sw = ws.cell(row=r, column=3, value="")
        sw.fill   = PatternFill("solid", fgColor=hex_clean)
        sw.border = THIN_BORDER

    ws.freeze_panes = "A2"


def _sheet_tasks(wb: Workbook, blank: bool) -> None:
    ws = wb.create_sheet("Tasks")
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "1F4E78"

    col_widths = [18, 30, 16, 12, 34, 34]
    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    headers = [
        "Task ID", "Task Name", "Assigned Resource",
        "Duration (s)", "Predecessors_FS (Finish-to-Start)", "Predecessors_SS (Start-to-Start)"
    ]
    ws.row_dimensions[1].height = 30
    for col, text in enumerate(headers, start=1):
        c = ws.cell(row=1, column=col, value=text)
        c.font = HDR_FONT; c.fill = HDR_FILL; c.border = THIN_BORDER; c.alignment = HDR_ALIGN

    FILL_A = PatternFill("solid", fgColor="FFFFFF")
    FILL_B = PatternFill("solid", fgColor=COMAU_LIGHT_BG)

    data = EXAMPLE_TASKS if not blank else []
    for r, row_data in enumerate(data, start=2):
        ws.row_dimensions[r].height = 20
        fill = FILL_A if r % 2 == 0 else FILL_B
        for col, val in enumerate(row_data, start=1):
            c = ws.cell(row=r, column=col, value=val)
            c.font = VAL_FONT; c.fill = fill; c.border = THIN_BORDER
            c.alignment = Alignment(horizontal="left", vertical="center")

    ws.freeze_panes = "A2"


def _sheet_py_source(wb: Workbook, py_rows: list) -> None:
    """Hidden sheet storing Python source line-by-line."""
    ws = wb.create_sheet("_py")
    ws.sheet_state = "hidden"
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 120

    mono = Font(name="Courier New", size=9)
    hdr_font = Font(bold=True, name="Courier New", size=9, color="FFFFFF")
    hdr_fill = PatternFill("solid", fgColor="333333")

    for row_idx, (col_a, col_b) in enumerate(py_rows, start=1):
        ca = ws.cell(row=row_idx, column=1, value=col_a)
        cb = ws.cell(row=row_idx, column=2, value=col_b)
        if col_a:
            ca.font = hdr_font; ca.fill = hdr_fill
            cb.font = hdr_font; cb.fill = hdr_fill
        else:
            ca.font = mono; cb.font = mono


# ---------------------------------------------------------------------------
# Step 2 — inject VBA + button via win32com
# ---------------------------------------------------------------------------

def _inject_vba_and_save(tmp_xlsx: Path, out_xlsm: Path) -> None:
    """Open the temp xlsx with Excel COM, add VBA module + button, save as xlsm."""
    import win32com.client as win32
    import pywintypes

    xl = None
    try:
        xl = win32.gencache.EnsureDispatch("Excel.Application")
        xl.Visible       = False
        xl.DisplayAlerts = False

        wb = xl.Workbooks.Open(str(tmp_xlsx.resolve()))

        # --- VBA module -------------------------------------------------
        try:
            vb_proj = wb.VBProject
        except pywintypes.com_error as e:
            wb.Close(False)
            raise RuntimeError(
                "Cannot access the VBA project.\n"
                "In Excel → Options → Trust Center → Trust Center Settings → "
                "Macro Settings → enable 'Trust access to the VBA project object model'."
            ) from e

        mod = vb_proj.VBComponents.Add(1)   # 1 = vbext_ct_StdModule
        mod.Name = "SimSequence"
        mod.CodeModule.AddFromString(VBA_CODE.strip())

        # --- Run button on Settings sheet --------------------------------
        ws_set = wb.Sheets("Settings")

        # Clear placeholder text cell content in row 4, col 1
        ws_set.Cells(4, 1).ClearContents()

        btn = ws_set.Shapes.AddShape(
            9,          # msoShapeRoundedRectangle
            ws_set.Cells(4, 1).Left + 2,
            ws_set.Cells(4, 1).Top  + 2,
            ws_set.Cells(4, 1).Width - 4,
            ws_set.Cells(4, 1).Height - 4
        )
        btn.Fill.ForeColor.RGB    = _rgb(0xC8, 0x10, 0x2E)   # Comau Red
        btn.Line.ForeColor.RGB    = _rgb(0x9E, 0x0D, 0x24)
        btn.TextFrame.Characters().Text = "▶  RUN SEQUENCE SIMULATION"

        tf = btn.TextFrame
        tf.HorizontalAlignment = 2    # xlHAlignCenter
        tf.VerticalAlignment   = 2    # xlVAlignCenter

        tf2 = btn.TextFrame2
        tf2.TextRange.Font.Size = 10
        tf2.TextRange.Font.Bold = True
        tf2.TextRange.Font.Name = FNT_FAMILY
        tf2.TextRange.Font.Fill.ForeColor.RGB = _rgb(0xFF, 0xFF, 0xFF)

        btn.OnAction = "SimSequence.RunSequence"

        # --- Save as .xlsm (FileFormat 52) --------------------------------
        out_xlsm.parent.mkdir(parents=True, exist_ok=True)
        try:
            wb.SaveAs(str(out_xlsm.resolve()), FileFormat=52)
        except pywintypes.com_error as e:
            wb.Close(False)
            raise RuntimeError(
                f"Could not save to '{out_xlsm.name}'.\n"
                f"The file appears to be open in Excel. Please close it in Excel and re-run."
            ) from e
        wb.Close(False)
        del wb

    finally:
        if xl is not None:
            try:
                xl.Quit()
            except Exception:
                pass
            del xl
        import gc
        gc.collect()
        import time
        time.sleep(0.5)


def _rgb(r: int, g: int, b: int) -> int:
    return r + (g << 8) + (b << 16)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_standalone(output_path: Path, blank: bool = False) -> Path:
    """
    Create the standalone .xlsm workbook at *output_path*.

    Returns the resolved absolute path of the created file.
    """
    output_path = Path(output_path)
    if output_path.suffix.lower() != ".xlsm":
        output_path = output_path.with_suffix(".xlsm")

    print("Collecting Python source files…")
    sources = collect_sources()
    rows = source_rows(sources)
    total_lines = sum(1 for _, c in rows if c == "")
    print(f"  {len(sources)} modules, ~{total_lines} source lines embedded.")

    tmp = output_path.with_suffix(".tmp.xlsx")
    print("Building workbook structure with Comau branding…")
    _build_xlsx(tmp, blank=blank, py_rows=rows)

    print("Injecting VBA via Excel COM…")
    try:
        _inject_vba_and_save(tmp, output_path)
    finally:
        if tmp.exists():
            import time
            for _ in range(5):
                try:
                    tmp.unlink()
                    break
                except Exception:
                    time.sleep(0.5)

    return output_path.resolve()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Build a standalone Comau .xlsm package with embedded Python."
    )
    p.add_argument("--output", "-o", type=Path,
                   default=Path("outputs/sim_sequence_standalone.xlsm"),
                   help="Destination path (default: outputs/sim_sequence_standalone.xlsm)")
    p.add_argument("--blank", action="store_true",
                   help="Emit headers only — no example data rows.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    try:
        out = build_standalone(args.output, blank=args.blank)
        print(f"\nStandalone workbook ready → {out}")
        print("\nOpen it in Excel, fill in Settings / Resources / Tasks,")
        print('then click "▶ RUN SEQUENCE SIMULATION" to generate the report directly inside the workbook.')
        return 0
    except RuntimeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"\nUnexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
