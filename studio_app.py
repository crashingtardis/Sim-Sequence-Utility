"""
studio_app.py — Entry point for the Comau Sim-Sequence Studio desktop app.

Usage:
    python studio_app.py
    python studio_app.py inputs/sample_weld_sequence.cseq
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable regardless of the working directory.
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from studio.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Comau Sim-Sequence Studio")
    app.setOrganizationName("Comau")
    app.setOrganizationDomain("comau.com")
    app.setStyle("Fusion")          # consistent base look; the theme stylesheet sits on top

    logo = ROOT / "resources" / "Logo-COMAU.png"
    if logo.exists():
        app.setWindowIcon(QIcon(str(logo)))

    window = MainWindow()
    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        window.open_path(sys.argv[1])
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
