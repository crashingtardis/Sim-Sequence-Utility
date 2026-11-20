"""
settings_panel.py — Project settings sidebar widget.

Edits: available_time, takt_time, time_increment, output_file name.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout,
    QDoubleSpinBox, QLineEdit, QGroupBox,
)

from sim_sequence.models import GlobalSettings


class SettingsPanel(QWidget):
    """Compact settings form."""
    changed = pyqtSignal()

    def __init__(self, settings: GlobalSettings, parent=None):
        super().__init__(parent)
        self._s = settings
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)

        grp = QGroupBox("Project Settings")
        form = QFormLayout(grp)
        form.setSpacing(8)
        # Let fields grow with the pane and wrap labels above fields when narrow.
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self._avail = QDoubleSpinBox()
        self._avail.setRange(0, 86400); self._avail.setSuffix(" s"); self._avail.setDecimals(1)
        self._avail.setValue(self._s.available_time)
        self._avail.valueChanged.connect(self._on_change)

        self._takt = QDoubleSpinBox()
        self._takt.setRange(0.1, 86400); self._takt.setSuffix(" s"); self._takt.setDecimals(1)
        self._takt.setValue(self._s.takt_time)
        self._takt.valueChanged.connect(self._on_change)

        self._inc = QDoubleSpinBox()
        self._inc.setRange(0.01, 60); self._inc.setSuffix(" s"); self._inc.setDecimals(2)
        self._inc.setValue(self._s.time_increment)
        self._inc.valueChanged.connect(self._on_change)

        self._outfile = QLineEdit(self._s.output_file)
        self._outfile.textChanged.connect(self._on_change)

        form.addRow("Available Time:", self._avail)
        form.addRow("Takt Time:", self._takt)
        form.addRow("Time Increment:", self._inc)
        form.addRow("Output File:", self._outfile)

        outer.addWidget(grp)
        outer.addStretch()

    def _on_change(self):
        self._s.available_time = self._avail.value()
        self._s.takt_time = self._takt.value()
        self._s.time_increment = self._inc.value()
        self._s.output_file = self._outfile.text().strip()
        self.changed.emit()

    def settings(self) -> GlobalSettings:
        return self._s

    def set_settings(self, s: GlobalSettings):
        self._s = s
        self._avail.blockSignals(True);  self._avail.setValue(s.available_time);  self._avail.blockSignals(False)
        self._takt.blockSignals(True);   self._takt.setValue(s.takt_time);         self._takt.blockSignals(False)
        self._inc.blockSignals(True);    self._inc.setValue(s.time_increment);     self._inc.blockSignals(False)
        self._outfile.blockSignals(True); self._outfile.setText(s.output_file);   self._outfile.blockSignals(False)
