from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QTextEdit, QDateEdit, QDialogButtonBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, QDate

from semetra.repo.sqlite_repo import SqliteRepo


class TaskDialog(QDialog):
    def __init__(self, repo: SqliteRepo, task_id: Optional[int] = None,
                 default_module_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.task_id = task_id
        self.setWindowTitle("Aufgabe bearbeiten" if task_id else "Neue Aufgabe")
        self.setMinimumWidth(420)
        self._build()
        if task_id:
            self._load(task_id)
        elif default_module_id:
            self._set_module(default_module_id)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        form = QFormLayout()
        form.setSpacing(10)

        self.title = QLineEdit()
        self.module_cb = QComboBox()
        for m in self.repo.list_modules("all"):
            self.module_cb.addItem(m["name"], m["id"])

        self.priority = QComboBox()
        self.priority.addItems(["Critical", "High", "Medium", "Low"])
        self.priority.setCurrentIndex(2)
        self.status = QComboBox()
        self.status.addItems(["Open", "In Progress", "Done"])
        self.due_date = QDateEdit()
        self.due_date.setCalendarPopup(True)
        self.due_date.setDate(QDate.currentDate())
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)

        form.addRow("Titel *:", self.title)
        form.addRow("Modul:", self.module_cb)
        form.addRow("Priorität:", self.priority)
        form.addRow("Status:", self.status)
        form.addRow("Fällig:", self.due_date)
        form.addRow("Notizen:", self.notes)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _set_module(self, mid: int):
        for i in range(self.module_cb.count()):
            if self.module_cb.itemData(i) == mid:
                self.module_cb.setCurrentIndex(i)
                break

    def _load(self, tid: int):
        t = self.repo.get_task(tid)
        if not t:
            return
        self.title.setText(t["title"])
        self._set_module(t["module_id"])
        idx = self.priority.findText(t["priority"])
        if idx >= 0:
            self.priority.setCurrentIndex(idx)
        idx2 = self.status.findText(t["status"])
        if idx2 >= 0:
            self.status.setCurrentIndex(idx2)
        if t["due_date"]:
            try:
                d = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
                self.due_date.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                pass
        self.notes.setPlainText(t["notes"] or "")

    def _accept(self):
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        mid = self.module_cb.currentData()
        due = self.due_date.date().toString("yyyy-MM-dd")
        if self.task_id:
            self.repo.update_task(
                self.task_id,
                title=title, module_id=mid,
                priority=self.priority.currentText(),
                status=self.status.currentText(),
                due_date=due, notes=self.notes.toPlainText(),
            )
        else:
            self.repo.add_task(
                mid, title,
                priority=self.priority.currentText(),
                status=self.status.currentText(),
                due_date=due, notes=self.notes.toPlainText(),
            )
        self.accept()
