"""Calendar cell widget for day display."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt

from semetra.gui.colors import _tc
from semetra.gui.i18n import tr

if TYPE_CHECKING:
    from semetra.gui.pages.calendar_page import CalendarPage


class _CalCell(QFrame):
    """A single clickable day cell in the custom month calendar grid."""

    def __init__(self, page: "CalendarPage", parent=None):
        super().__init__(parent)
        self.setObjectName("cal_day_cell")
        self._page = page
        self._day_date: Optional[date] = None
        self.setMinimumHeight(68)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(1)
        self._day_lbl = QLabel()
        lay.addWidget(self._day_lbl)
        self._ev_lay = QVBoxLayout()
        self._ev_lay.setSpacing(1)
        self._ev_lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self._ev_lay)
        lay.addStretch()
        self._apply_style(empty=True, is_selected=False)

    def set_day(self, d: Optional[date], events: list, is_today: bool, is_selected: bool,
                stress_level: int = 0):
        self._day_date = d
        self._stress_level = stress_level
        # Clear old event labels
        while self._ev_lay.count():
            item = self._ev_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if d is None:
            self._day_lbl.setText("")
            self._apply_style(empty=True, is_selected=False, stress_level=0)
            self.setCursor(Qt.ArrowCursor)
            return
        self.setCursor(Qt.PointingHandCursor)
        # Day number
        if is_today:
            self._day_lbl.setStyleSheet(
                "font-size:13px;font-weight:800;color:#FFFFFF;"
                "background:#7C3AED;border-radius:10px;padding:1px 7px;"
            )
        else:
            self._day_lbl.setStyleSheet(
                f"font-size:13px;font-weight:700;"
                f"color:{_tc('#1A1523','#EAE6F4')};background:transparent;"
            )
        self._day_lbl.setText(str(d.day))
        self._apply_style(empty=False, is_selected=is_selected, stress_level=stress_level)
        # Event blocks — max 2 visible + overflow label
        MAX_VISIBLE = 2
        for icon, title, color in events[:MAX_VISIBLE]:
            ev_lbl = QLabel(f"{icon} {title}")
            ev_lbl.setWordWrap(False)
            ev_lbl.setMaximumHeight(17)
            ev_lbl.setStyleSheet(
                f"background:{color}28;color:{color};border-radius:4px;"
                f"padding:1px 5px;font-size:11px;font-weight:700;"
            )
            self._ev_lay.addWidget(ev_lbl)
        if len(events) > MAX_VISIBLE:
            more = QLabel(f"+{len(events) - MAX_VISIBLE} mehr")
            more.setStyleSheet(
                f"font-size:11px;font-weight:600;"
                f"color:{_tc('#6E6882','#8A849C')};background:transparent;"
            )
            self._ev_lay.addWidget(more)

    def _apply_style(self, empty: bool, is_selected: bool, stress_level: int = 0):
        if empty:
            bg     = _tc("#F4F4F6", "#16162A")
            border = _tc("#E4E4E8", "#22223A")
        elif is_selected:
            bg     = _tc("#EEF3FF", "#1E2D4A")
            border = "#4A86E8"
        else:
            # Stress tint — subtle background color based on week load
            _stress_bg_light = ["#FFFFFF", "#FFFEF0", "#FFF5E8", "#FFF0EE"]
            _stress_bg_dark  = ["#1E2030", "#1E1E18", "#1E1810", "#1E1010"]
            bg     = _tc(_stress_bg_light[min(stress_level, 3)],
                         _stress_bg_dark[min(stress_level, 3)])
            border = _tc("#E4E4E8", "#2A2A3A")
        self.setStyleSheet(
            f"QFrame#cal_day_cell{{background:{bg};border:1px solid {border};border-radius:4px;}}"
            f"QLabel{{background:transparent;}}"
        )

    def mousePressEvent(self, event):
        if self._day_date is not None:
            self._page._on_cell_clicked(self._day_date)
        super().mousePressEvent(event)
