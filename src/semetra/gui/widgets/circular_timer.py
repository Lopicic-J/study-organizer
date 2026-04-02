"""CircularTimer widget for displaying countdown progress."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont

from semetra.gui.colors import _tc
from semetra.gui.helpers import fmt_hms


class CircularTimer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self._total = 25 * 60
        self._remaining = 25 * 60
        self._color = "#4A86E8"

    def set_state(self, remaining: int, total: int, color: str = ""):
        self._remaining = remaining
        self._total = total
        if color:
            self._color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        size = min(w, h) - 20
        x = (w - size) // 2
        y = (h - size) // 2
        rect_f = QRect(x, y, size, size)

        pen = QPen(QColor(_tc("#E8EBF2", "#313244")), 12, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect_f, 0, 360 * 16)

        frac = self._remaining / self._total if self._total > 0 else 0
        span = int(frac * 360 * 16)
        pen2 = QPen(QColor(self._color), 12, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen2)
        p.drawArc(rect_f, 90 * 16, span)

        p.setPen(QPen(QColor(_tc("#1A1A2E", "#E2D9F3"))))
        font = QFont("Segoe UI", 26, QFont.Bold)
        p.setFont(font)
        time_str = fmt_hms(self._remaining)[3:]  # mm:ss
        p.drawText(rect_f, Qt.AlignCenter, time_str)
        p.end()
