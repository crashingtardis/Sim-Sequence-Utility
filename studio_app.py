"""
studio_app.py — Entry point for the Comau Sim-Sequence Studio desktop app.

Usage:
    python studio_app.py
    python studio_app.py inputs/honda_weld_sequence.cseq
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure the project root is on sys.path regardless of CWD
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from studio.main_window import MainWindow


def main():
    # On Windows, set DPI awareness before creating the app
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Comau Sim-Sequence Studio")
    app.setOrganizationName("Comau")
    app.setOrganizationDomain("comau.com")

    # App icon (use logo if available)
    logo_path = ROOT / "resources" / "Logo-COMAU.png"
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    window = MainWindow()

    # If a file was passed as argument, open it
    if len(sys.argv) > 1:
        file_arg = Path(sys.argv[1])
        if file_arg.exists():
            if file_arg.suffix.lower() == ".cseq":
                from sim_sequence.cseq_io import load_cseq
                try:
                    model = load_cseq(file_arg)
                    window._current_path = file_arg
                    window._load_model_into_panels(model)
                    window._mark_dirty(False)
                except Exception as exc:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.critical(window, "Open Error", str(exc))
            elif file_arg.suffix.lower() in (".xlsx", ".xlsm"):
                from sim_sequence.excel_loader import load_excel
                try:
                    model = load_excel(str(file_arg))
                    window._load_model_into_panels(model)
                    window._mark_dirty(True)
                except Exception as exc:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.critical(window, "Import Error", str(exc))

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
