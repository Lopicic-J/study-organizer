"""Helper functions for widget creation."""
from __future__ import annotations

from PySide6.QtWidgets import QScrollArea, QFrame, QWidget
from PySide6.QtCore import Qt

from semetra.gui.colors import _tc


def make_scroll(widget: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    # Transparent viewport so the dark/light page background shows through
    sa.viewport().setAutoFillBackground(False)
    sa.setWidget(widget)
    return sa


def separator() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(_tc("color: #EAE8F2;", "color: #1E1B2C;"))
    return f
