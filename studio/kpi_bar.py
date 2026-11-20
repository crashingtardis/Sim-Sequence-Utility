"""
kpi_bar.py — KPI strip shown below the Gantt.

Cards flow onto extra lines when the window is narrow (FlowLayout) instead of
overlapping.  All colours come from the stylesheet via dynamic properties, so
the bar follows the dark / light theme automatically.
"""

from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from sim_sequence.models import SequenceModel

from .flow_layout import FlowLayout
from .theme import set_prop


class _KpiCard(QFrame):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("KpiCard")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(6)
        self._label = QLabel(label.upper())
        self._label.setObjectName("KpiLabel")
        self.value = QLabel("\u2014")
        self.value.setObjectName("KpiValue")
        lay.addWidget(self._label)
        lay.addWidget(self.value)

    def set_value(self, text: str, tone: str = "") -> None:
        self.value.setText(text)
        set_prop(self.value, "tone", tone)


class KpiBar(QFrame):
    """Cycle / takt / utilisation / counts + balance badge."""

    _METRICS = (("cycle", "Cycle"), ("takt", "Takt"), ("util", "Utilisation"),
                ("tasks", "Tasks"), ("resources", "Resources"))

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("KpiBar")
        self._cards: Dict[str, _KpiCard] = {}
        flow = FlowLayout(self, margin=8, h_spacing=8, v_spacing=6)
        for key, label in self._METRICS:
            card = _KpiCard(label)
            self._cards[key] = card
            flow.addWidget(card)
        self._badge = QLabel("No data")
        self._badge.setObjectName("StatusBadge")
        flow.addWidget(self._badge)

    def _clear(self) -> None:
        for card in self._cards.values():
            card.set_value("\u2014")
        self._badge.setText("No data")
        set_prop(self._badge, "state", "")

    def update_from_model(self, model: Optional[SequenceModel]) -> None:
        if model is None:
            self._clear()
            return
        scheduled = [t for t in model.tasks if t.end_time is not None]
        if not scheduled:
            self._clear()
            return

        cycle = max(t.end_time for t in scheduled)
        takt = model.settings.takt_time
        util = (cycle / takt * 100.0) if takt > 0 else 0.0
        balanced = cycle <= takt

        self._cards["cycle"].set_value(f"{cycle:.1f} s")
        self._cards["takt"].set_value(f"{takt:.1f} s")
        self._cards["util"].set_value(f"{util:.1f} %", "good" if balanced else "bad")
        self._cards["tasks"].set_value(str(len(model.tasks)))
        self._cards["resources"].set_value(str(len(model.resources)))

        if balanced:
            self._badge.setText("\u2713  BALANCED")
            set_prop(self._badge, "state", "ok")
        else:
            self._badge.setText("\u26a0  OVER TAKT")
            set_prop(self._badge, "state", "over")
