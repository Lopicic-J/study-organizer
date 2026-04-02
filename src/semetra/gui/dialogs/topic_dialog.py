from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QTextEdit, QDialogButtonBox, QMessageBox,
)
from PySide6.QtCore import Qt

from semetra.repo.sqlite_repo import SqliteRepo

# Import constants from main gui module
KNOWLEDGE_LABELS = {0: "Nicht begonnen", 1: "Grundlagen", 2: "Vertraut", 3: "Gut", 4: "Experte"}


class TopicDialog(QDialog):
    def __init__(self, repo: SqliteRepo, module_id: int,
                 topic_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.module_id = module_id
        self.topic_id = topic_id
        self.setWindowTitle("Thema bearbeiten" if topic_id else "Neues Thema")
        self.setMinimumWidth(360)
        self._build()
        if topic_id:
            self._load(topic_id)

    def _build(self):
        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.title = QLineEdit()
        self.level = QComboBox()
        for k, v in KNOWLEDGE_LABELS.items():
            self.level.addItem(v, k)
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)

        # Task assignment dropdown (tasks belonging to this module)
        self.task_cb = QComboBox()
        self.task_cb.addItem("— keine Aufgabe —", None)
        for t in self.repo.list_tasks(module_id=self.module_id):
            self.task_cb.addItem(t["title"], t["id"])

        form.addRow("Titel *:", self.title)
        form.addRow("Kenntnisstand:", self.level)
        form.addRow("Aufgabe:", self.task_cb)
        form.addRow("Notizen:", self.notes)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _load(self, tid: int):
        topics = self.repo.list_topics(self.module_id)
        t = next((r for r in topics if r["id"] == tid), None)
        if not t:
            return
        self.title.setText(t["title"])
        idx = self.level.findData(int(t["knowledge_level"]))
        if idx >= 0:
            self.level.setCurrentIndex(idx)
        self.notes.setPlainText(t["notes"] or "")
        # Restore linked task
        task_id = (int(t["task_id"]) if "task_id" in t.keys() and t["task_id"] is not None else None)
        cb_idx = self.task_cb.findData(task_id)
        if cb_idx >= 0:
            self.task_cb.setCurrentIndex(cb_idx)

    def _accept(self):
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        level = self.level.currentData()
        notes = self.notes.toPlainText()
        task_id = self.task_cb.currentData()
        now_str = datetime.now().isoformat()
        if self.topic_id:
            self.repo.update_topic(self.topic_id, title=title,
                                   knowledge_level=level, notes=notes,
                                   task_id=task_id, last_reviewed=now_str)
        else:
            self.repo.add_topic(self.module_id, title, knowledge_level=level,
                                notes=notes, task_id=task_id)
            # Set last_reviewed on the just-created topic
            topics = self.repo.list_topics(self.module_id)
            new_t = next((t for t in topics if t["title"] == title), None)
            if new_t:
                self.repo.update_topic(new_t["id"], last_reviewed=now_str)
        self.accept()
