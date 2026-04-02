"""StatCard widget for displaying metrics."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt, Signal


class StatCard(QFrame):
    """Modern metric card with a gradient accent bar and large bold value."""
    clicked = Signal()

    def __init__(self, title: str, value: str, unit: str = "", color: str = "#7C3AED", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._color = color
        self._clickable = False
        self.setMinimumHeight(108)
        self.setMaximumHeight(132)
        self.setMinimumWidth(118)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(3)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("CardTitle")
        lay.addWidget(self.title_lbl)

        lay.addStretch()

        row = QHBoxLayout()
        row.setSpacing(5)
        row.setContentsMargins(0, 0, 0, 0)
        self.val_lbl = QLabel(value)
        self.val_lbl.setStyleSheet(
            f"color:{color}; font-size:28px; font-weight:800; letter-spacing:-1px;"
        )
        row.addWidget(self.val_lbl)
        if unit:
            u = QLabel(unit)
            u.setObjectName("CardUnit")
            u.setAlignment(Qt.AlignBottom)
            u.setStyleSheet("padding-bottom:4px;")
            row.addWidget(u)
        row.addStretch()
        lay.addLayout(row)

        # Slim gradient accent at bottom-left
        accent = QWidget()
        accent.setFixedHeight(3)
        accent.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {color}, stop:0.6 {color}88, stop:1 transparent);"
            f"border-radius:2px; margin-top:4px;"
        )
        lay.addWidget(accent)

    def make_clickable(self) -> "StatCard":
        """Enable pointer cursor + emits clicked() on left click. Returns self."""
        self._clickable = True
        self.setCursor(Qt.PointingHandCursor)
        return self

    def mousePressEvent(self, event):
        if self._clickable and event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_value(self, v: str):
        self.val_lbl.setText(v)
