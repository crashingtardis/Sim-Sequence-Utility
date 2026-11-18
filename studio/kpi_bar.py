"""
kpi_bar.py — Slim KPI status bar shown below the Gantt chart.

Displays: Cycle Time | Takt Time | Utilization | Status badge
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QFrame,
)

from sim_sequence.models import SequenceModel
from .theme import COMAU_RED, SUCCESS_GREEN, WARNING_ORANGE, SILVER, EXEC_NAVY


def _kpi_card(label: str, value: str, color: str = SILVER) -> QWidget:
    card = QWidget()
    card.setStyleSheet(
        f"background:#122035; border-radius:4px; padding: 4px 12px;"
    )
    layout = QHBoxLayout(card)
    layout.setContentsMargins(10, 4, 10, 4)
    layout.setSpacing(6)

    lbl = QLabel(label)
    lbl.setStyleSheet("color:#607D8B; font-size:8pt; font-weight:bold;")
    val = QLabel(value)
    val.setStyleSheet(f"color:{color}; font-size:10pt; font-weight:bold;")
    layout.addWidget(lbl)
    layout.addWidget(val)
    return card


class KpiBar(QWidget):
    """Horizontal bar of KPI metrics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet(f"background-color: {EXEC_NAVY};")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 4, 12, 4)
        self._layout.setSpacing(10)
        self._cards = {}
        self._build()

    def _build(self):
        metrics = [
            ("cycle",    "Cycle Time", "— s",   SILVER),
            ("takt",     "Takt Time",  "— s",   SILVER),
            ("util",     "Utilization","— %",   SILVER),
            ("tasks",    "Tasks",      "—",     SILVER),
            ("resources","Resources",  "—",     SILVER),
        ]
        for key, label, value, color in metrics:
            card = _kpi_card(label, value, color)
            self._cards[key] = card
            self._layout.addWidget(card)

        self._layout.addStretch()

        # Status badge
        self._status_lbl = QLabel("No data")
        self._status_lbl.setStyleSheet(
            "color:#607D8B; font-size:9pt; font-weight:bold; "
            "background:#0D1B2A; border-radius:4px; padding:4px 10px;"
        )
        self._layout.addWidget(self._status_lbl)

    def _update_card(self, key: str, value: str, color: str = SILVER):
        card = self._cards.get(key)
        if card is None:
            return
        # Find the value label (second child)
        labels = card.findChildren(QLabel)
        if len(labels) >= 2:
            labels[1].setText(value)
            labels[1].setStyleSheet(f"color:{color}; font-size:10pt; font-weight:bold;")

    def update_from_model(self, model: Optional[SequenceModel]):
        if model is None:
            for key in self._cards:
                self._update_card(key, "—", SILVER)
            self._status_lbl.setText("No data")
            self._status_lbl.setStyleSheet(
                "color:#607D8B; font-size:9pt; font-weight:bold; "
                "background:#0D1B2A; border-radius:4px; padding:4px 10px;"
            )
            return

        tasks_scheduled = [t for t in model.tasks if t.end_time is not None]
        if not tasks_scheduled:
            return

        cycle_t = max(t.end_time for t in tasks_scheduled)
        takt_t  = model.settings.takt_time
        util    = (cycle_t / takt_t * 100) if takt_t > 0 else 0
        balanced = cycle_t <= takt_t

        self._update_card("cycle",     f"{cycle_t:.1f} s",  SILVER)
        self._update_card("takt",      f"{takt_t:.1f} s",   SILVER)
        self._update_card("util",      f"{util:.1f} %",
                          SUCCESS_GREEN if balanced else COMAU_RED)
        self._update_card("tasks",     str(len(model.tasks)), SILVER)
        self._update_card("resources", str(len(model.resources)), SILVER)

        if balanced:
            self._status_lbl.setText("✓  BALANCED")
            self._status_lbl.setStyleSheet(
                f"color:{SUCCESS_GREEN}; font-size:9pt; font-weight:bold; "
                f"background:#0F2A1A; border-radius:4px; padding:4px 10px;"
            )
        else:
            self._status_lbl.setText("⚠  OVER TAKT")
            self._status_lbl.setStyleSheet(
                f"color:{COMAU_RED}; font-size:9pt; font-weight:bold; "
                f"background:#2A0F14; border-radius:4px; padding:4px 10px;"
            )
