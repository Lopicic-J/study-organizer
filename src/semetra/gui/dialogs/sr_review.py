"""Spaced Repetition (SM-2) review session dialog."""

from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar
)
from PySide6.QtCore import Qt

from semetra.gui.colors import _tc


class SRReviewDialog(QDialog):
    """Flashcard-style SM-2 review session.

    Shows topics due for review one by one.
    The user rates recall quality → SM-2 algorithm schedules the next review.
    """

    def __init__(self, repo, topics: list, parent=None):
        super().__init__(parent)
        self.repo    = repo
        self.topics  = list(topics)
        self._idx    = 0
        self._results: list = []   # (topic_id, quality, next_review) per review
        self._revealed = False
        self.setWindowTitle("Wissens-Review")
        self.setMinimumSize(560, 380)
        self.resize(600, 420)
        self._build()
        self._show_current()

    def _build(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(28, 24, 28, 24)
        main.setSpacing(12)

        # ── Header: progress ──────────────────────────────────────────────
        hdr = QHBoxLayout()
        self._progress_lbl = QLabel()
        self._progress_lbl.setStyleSheet(f"font-size:12px;color:{_tc('#706C86','#6B7280')};")
        hdr.addWidget(self._progress_lbl)
        hdr.addStretch()
        self._module_lbl = QLabel()
        self._module_lbl.setStyleSheet(f"font-size:11px;color:{_tc('#706C86','#6B7280')};")
        hdr.addWidget(self._module_lbl)
        main.addLayout(hdr)

        # Progress bar
        self._prog_bar = QProgressBar()
        self._prog_bar.setFixedHeight(4)
        self._prog_bar.setTextVisible(False)
        self._prog_bar.setStyleSheet(
            f"QProgressBar{{background:{_tc('#E8EDF8','#2A2A3E')};border-radius:2px;border:none;}}"
            f"QProgressBar::chunk{{background:#4A86E8;border-radius:2px;}}"
        )
        main.addWidget(self._prog_bar)

        # ── Card: topic title (large, centered) ───────────────────────────
        self._card = QFrame()
        self._card.setObjectName("SRCard")
        self._card.setStyleSheet(
            f"QFrame#SRCard{{background:{_tc('#F8FAFF','#252535')};"
            f"border:1px solid {_tc('#DDE3F0','#383850')};border-radius:12px;}}"
        )
        self._card.setMinimumHeight(140)
        card_lay = QVBoxLayout(self._card)
        card_lay.setContentsMargins(24, 20, 24, 20)
        card_lay.setSpacing(8)

        self._topic_lbl = QLabel()
        self._topic_lbl.setAlignment(Qt.AlignCenter)
        self._topic_lbl.setWordWrap(True)
        self._topic_lbl.setStyleSheet(
            f"font-size:20px;font-weight:bold;color:{_tc('#1A1A2E','#CDD6F4')};"
        )
        card_lay.addWidget(self._topic_lbl, 1)

        self._notes_lbl = QLabel()
        self._notes_lbl.setAlignment(Qt.AlignCenter)
        self._notes_lbl.setWordWrap(True)
        self._notes_lbl.setStyleSheet(f"font-size:13px;color:{_tc('#6B7280','#9BA8C0')};")
        self._notes_lbl.hide()
        card_lay.addWidget(self._notes_lbl)

        main.addWidget(self._card, 1)

        # ── Reveal / SR rating buttons ─────────────────────────────────────
        self._reveal_btn = QPushButton("🔍  Aufdecken")
        self._reveal_btn.setFixedHeight(36)
        self._reveal_btn.setObjectName("PrimaryBtn")
        self._reveal_btn.clicked.connect(self._reveal)
        main.addWidget(self._reveal_btn)

        self._rating_row = QHBoxLayout()
        self._rating_row.setSpacing(6)
        _rating_defs = [
            ("Nicht gewusst",    "#E05050", "#FF8080", 0),
            ("Mit Mühe",         "#E07000", "#FFAA00", 2),
            ("Gut gewusst",      "#1A7A50", "#2CB67D", 4),
            ("Sofort! ⚡",        "#1A5A9A", "#4A86E8", 5),
        ]
        self._rating_btns = []
        for label, bg_dark, bg_light, quality in _rating_defs:
            btn = QPushButton(label)
            btn.setFixedHeight(36)
            _bg = _tc(bg_light + "33", bg_dark + "44")
            _fg = _tc(bg_dark, bg_light)
            btn.setStyleSheet(
                f"QPushButton{{background:{_bg};color:{_fg};border:1px solid {_fg}55;"
                f"border-radius:7px;font-size:12px;font-weight:600;padding:0 10px;}}"
                f"QPushButton:hover{{background:{_fg}33;border-color:{_fg};}}"
            )
            btn.clicked.connect(lambda _c=False, q=quality: self._rate(q))
            self._rating_btns.append(btn)
            self._rating_row.addWidget(btn)
        main.addLayout(self._rating_row)

        # Done / summary row
        self._done_btn = QPushButton("Session beenden")
        self._done_btn.setObjectName("SecondaryBtn")
        self._done_btn.setFixedHeight(36)
        self._done_btn.clicked.connect(self.accept)
        self._done_btn.hide()
        main.addWidget(self._done_btn)

    def _show_current(self):
        total = len(self.topics)
        if self._idx >= total:
            self._show_summary()
            return

        t = self.topics[self._idx]
        self._progress_lbl.setText(f"Topic {self._idx + 1} von {total}")
        self._prog_bar.setRange(0, total)
        self._prog_bar.setValue(self._idx)
        self._module_lbl.setText(t["module_name"] if "module_name" in t.keys() else "")

        self._topic_lbl.setText(t["title"])
        notes = (t["notes"] if "notes" in t.keys() else "") or ""
        self._notes_lbl.setText(notes)
        self._notes_lbl.setVisible(False)

        self._revealed = False
        self._reveal_btn.show()
        for btn in self._rating_btns:
            btn.hide()
        self._done_btn.hide()

    def _reveal(self):
        self._revealed = True
        t = self.topics[self._idx]
        notes = (t["notes"] if "notes" in t.keys() else "") or ""
        if notes:
            self._notes_lbl.setText(notes)
            self._notes_lbl.show()
        self._reveal_btn.hide()
        for btn in self._rating_btns:
            btn.show()

    def _rate(self, quality: int):
        t = self.topics[self._idx]
        result = self.repo.sm2_review(t["id"], quality)
        self._results.append({
            "title":       t["title"],
            "quality":     quality,
            "next_review": result.get("next_review", ""),
            "interval":    result.get("interval", 1),
        })
        self._idx += 1
        self._show_current()

    def _show_summary(self):
        """Replace card content with a summary after all topics reviewed."""
        total = len(self._results)
        knew   = sum(1 for r in self._results if r["quality"] >= 3)
        missed = total - knew

        self._topic_lbl.setText(
            f"✅  Review abgeschlossen!\n\n"
            f"{knew} gewusst  ·  {missed} nicht gewusst\n\n"
            f"{total} Topics bewertet"
        )
        self._topic_lbl.setStyleSheet(
            f"font-size:16px;font-weight:600;color:{_tc('#1A1A2E','#CDD6F4')};"
        )
        self._notes_lbl.hide()
        self._reveal_btn.hide()
        for btn in self._rating_btns:
            btn.hide()
        self._done_btn.show()
        self._prog_bar.setValue(total)
        self._progress_lbl.setText(f"Alle {total} Topics bewertet")

    def reviewed_count(self) -> int:
        return len(self._results)
