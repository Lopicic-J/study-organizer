from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QFrame, QDialogButtonBox,
)
from PySide6.QtCore import Qt, QDate

from semetra.repo.sqlite_repo import SqliteRepo

KNOWLEDGE_LABELS = {0: "Nicht begonnen", 1: "Grundlagen", 2: "Vertraut", 3: "Gut", 4: "Experte"}


class LernRueckblickDialog(QDialog):
    """Zeigt nach jeder Timer-Session: abgehakte Lernziele + schnelles Thema eintragen."""

    def __init__(self, repo: SqliteRepo, module_id: Optional[int], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.mid = module_id
        self.setWindowTitle("🎉 Session abgeschlossen!")
        self.setMinimumWidth(400)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        title = QLabel("🎉 Gut gemacht! Was hast du in dieser Session erarbeitet?")
        title.setWordWrap(True)
        title.setStyleSheet("font-size:14px;font-weight:bold;")
        lay.addWidget(title)

        # Lernziel abhaken (only if module selected with objectives)
        if self.mid:
            objectives = [o for o in self.repo.list_scraped_data(self.mid, "objective")
                          if not int(o["checked"] or 0)]
            if objectives:
                sep = QFrame(); sep.setFrameShape(QFrame.HLine)
                lay.addWidget(sep)
                lay.addWidget(QLabel("Lernziel als erledigt markieren:"))
                self._lz_cb = QComboBox()
                self._lz_cb.addItem("— nichts Bestimmtes —", None)
                for o in objectives:
                    self._lz_cb.addItem(o["title"], o["id"])
                lay.addWidget(self._lz_cb)
            else:
                self._lz_cb = None
        else:
            self._lz_cb = None

        # Quick topic entry
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        lay.addWidget(sep2)
        lay.addWidget(QLabel("Neues Wissensthema schnell eintragen (optional):"))
        self._topic_edit = QLineEdit()
        self._topic_edit.setPlaceholderText("z.B. 'Rekursion verstanden', 'Kapitel 3 erledigt'…")
        lay.addWidget(self._topic_edit)

        know_row = QHBoxLayout()
        know_row.addWidget(QLabel("Kenntnisstand:"))
        self._know_cb = QComboBox()
        for k, v in KNOWLEDGE_LABELS.items():
            self._know_cb.addItem(v, k)
        self._know_cb.setCurrentIndex(2)  # default: "Vertraut"
        know_row.addWidget(self._know_cb)
        know_row.addStretch()
        lay.addLayout(know_row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Speichern & Schließen")
        btns.button(QDialogButtonBox.Cancel).setText("Schließen ohne Speichern")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _save(self):
        # Mark Lernziel as checked
        if self._lz_cb is not None:
            oid = self._lz_cb.currentData()
            if oid is not None:
                self.repo.update_scraped_data(oid, checked=1)
        # Add quick topic
        if self.mid:
            topic_title = self._topic_edit.text().strip()
            if topic_title:
                level = self._know_cb.currentData()
                now_str = datetime.now().isoformat()
                self.repo.add_topic(self.mid, topic_title,
                                    knowledge_level=level, notes="")
                # Set last_reviewed to now for new topic
                topics = self.repo.list_topics(self.mid)
                new_t = next((t for t in topics if t["title"] == topic_title), None)
                if new_t:
                    self.repo.update_topic(new_t["id"], last_reviewed=now_str)
        self.accept()
