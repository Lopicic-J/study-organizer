from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDialogButtonBox, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt

from semetra.repo.sqlite_repo import SqliteRepo

KNOWLEDGE_LABELS = {0: "Nicht begonnen", 1: "Grundlagen", 2: "Vertraut", 3: "Gut", 4: "Experte"}


class QuickAddDialog(QDialog):
    """Schnelleintrag ohne Seitenwechsel: Task oder Wissensthema in 3 Klicks."""

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.setWindowTitle("⚡ Schnelleintrag")
        self.setMinimumWidth(380)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        # Header
        hdr = QLabel("⚡ Schnelleintrag")
        hdr.setStyleSheet("font-size:15px;font-weight:bold;")
        lay.addWidget(hdr)

        form = QFormLayout()
        form.setSpacing(8)

        # Module
        self._mod_cb = QComboBox()
        self._mod_cb.addItem("— Modul wählen —", None)
        for m in self.repo.list_modules("all"):
            self._mod_cb.addItem(m["name"], m["id"])
        form.addRow("Modul:", self._mod_cb)

        # Type
        self._type_cb = QComboBox()
        self._type_cb.addItems(["✅  Aufgabe (Task)", "🧠  Wissensthema"])
        form.addRow("Typ:", self._type_cb)

        # Title
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Titel eingeben…")
        form.addRow("Titel *:", self._title_edit)

        # Extra: priority (for task) or knowledge level (for topic)
        self._extra_cb = QComboBox()
        self._extra_cb.addItems(["Low", "Medium", "High", "Critical"])
        self._extra_cb.setCurrentText("Medium")
        self._extra_lbl = QLabel("Priorität:")
        form.addRow(self._extra_lbl, self._extra_cb)

        self._type_cb.currentIndexChanged.connect(self._on_type_change)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Hinzufügen")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        # Focus on title
        self._title_edit.setFocus()

    def _on_type_change(self, idx):
        if idx == 0:  # Task
            self._extra_lbl.setText("Priorität:")
            self._extra_cb.clear()
            self._extra_cb.addItems(["Low", "Medium", "High", "Critical"])
            self._extra_cb.setCurrentText("Medium")
        else:  # Topic
            self._extra_lbl.setText("Kenntnisstand:")
            self._extra_cb.clear()
            for k, v in KNOWLEDGE_LABELS.items():
                self._extra_cb.addItem(v, k)

    def _save(self):
        mid = self._mod_cb.currentData()
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        if not mid:
            QMessageBox.warning(self, "Fehler", "Bitte ein Modul auswählen.")
            return
        if self._type_cb.currentIndex() == 0:
            prio = self._extra_cb.currentText()
            self.repo.add_task(mid, title, priority=prio, status="Open")
        else:
            level = self._extra_cb.currentData() or 0
            now_str = datetime.now().isoformat()
            self.repo.add_topic(mid, title, knowledge_level=level, notes="")
            topics = self.repo.list_topics(mid)
            new_t = next((t for t in topics if t["title"] == title), None)
            if new_t:
                self.repo.update_topic(new_t["id"], last_reviewed=now_str)
        self.accept()
