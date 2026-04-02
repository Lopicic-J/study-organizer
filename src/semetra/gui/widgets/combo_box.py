"""Wayland-safe QComboBox implementation."""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QComboBox as _QCBBase, QFrame, QListWidget, QListWidgetItem,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, QPoint, QEvent, QObject


# ── Wayland-safe QComboBox ─────────────────────────────────────────────────
# On Wayland the native QComboBox popup is a compositor surface that receives
# hover events but swallows mouse-click events, so items can't be selected.
# We shadow QComboBox throughout this module with a subclass that replaces
# showPopup() with a QFrame *child* of the parent window — no separate OS
# window means no WM/compositor positioning interference.  Position is
# computed with mapTo() which is pure Qt and perfectly accurate.

class QComboBox(_QCBBase):
    """Drop-in QComboBox replacement: in-window overlay popup, zero WM involvement."""

    _popup: Optional[QFrame] = None

    def showPopup(self) -> None:
        n = self.count()
        if n == 0:
            return
        self.hidePopup()   # close any previous popup first

        # Attach the overlay to the topmost ancestor so it can float above
        # all sibling widgets without leaving the window coordinate space.
        root = self.window()

        frm = QFrame(root)
        frm.setObjectName("ComboPopupOverlay")
        frm.setAttribute(Qt.WA_StyledBackground, True)
        frm.raise_()
        self._popup = frm

        lay = QVBoxLayout(frm)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(0)

        lw = QListWidget()
        lw.setFrameShape(QFrame.NoFrame)
        lw.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for i in range(n):
            it = QListWidgetItem(self.itemText(i))
            it.setData(Qt.UserRole, self.itemData(i))
            lw.addItem(it)
        if 0 <= self.currentIndex() < n:
            lw.setCurrentRow(self.currentIndex())
        lay.addWidget(lw)

        # ── Event filter: dismiss on click outside ──────────────────────
        class _OutsideFilter(QObject):
            def eventFilter(_, obj, event):   # type: ignore[override]
                if event.type() == QEvent.MouseButtonPress:
                    try:
                        gp = event.globalPosition().toPoint()
                    except AttributeError:
                        gp = event.globalPos()
                    if not frm.rect().contains(frm.mapFromGlobal(gp)):
                        _close()
                return False

        _filter = _OutsideFilter(frm)
        frm._outside_filter = _filter        # keep alive
        QApplication.instance().installEventFilter(_filter)

        def _close():
            if self._popup is frm:
                self._popup = None
            try:
                QApplication.instance().removeEventFilter(
                    frm._outside_filter)  # type: ignore[attr-defined]
            except Exception:
                pass
            frm.hide()
            frm.deleteLater()

        def _pick(_item=None):
            row = lw.currentRow()
            _close()
            if row >= 0 and row != self.currentIndex():
                self.setCurrentIndex(row)
                self.activated.emit(row)

        lw.itemClicked.connect(_pick)
        lw.itemActivated.connect(_pick)   # keyboard Enter / Return

        # ── Position: flush below the combo, in root coordinates ────────
        pos_in_root = self.mapTo(root, QPoint(0, self.height()))
        row_h = max(lw.sizeHintForRow(0), 28) if n > 0 else 28
        pw = max(self.width(), 220)
        ph = min(row_h * n + 8, 360)
        frm.setGeometry(pos_in_root.x(), pos_in_root.y(), pw, ph)
        frm.show()
        frm.raise_()

    def hidePopup(self) -> None:
        if self._popup is not None:
            p = self._popup
            self._popup = None
            try:
                QApplication.instance().removeEventFilter(
                    p._outside_filter)   # type: ignore[attr-defined]
            except Exception:
                pass
            p.hide()
            p.deleteLater()
