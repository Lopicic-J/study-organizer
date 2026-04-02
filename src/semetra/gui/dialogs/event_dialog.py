from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QTextEdit, QDateEdit, QDialogButtonBox, QMessageBox,
)
from PySide6.QtCore import Qt, QDate

from semetra.repo.sqlite_repo import SqliteRepo


class EventDialog(QDialog):
    """Dialog to create a custom calendar event."""
    def __init__(self, repo: SqliteRepo, default_date: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.setWindowTitle("Neues Ereignis")
        self.setMinimumWidth(400)
        self._build()
        if default_date:
            try:
                d = datetime.strptime(default_date, "%Y-%m-%d").date()
                self.start_date.setDate(QDate(d.year, d.month, d.day))
                self.end_date.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                pass

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        self.title = QLineEdit()
        self.title.setPlaceholderText("Ereignistitel *")

        self.kind_cb = QComboBox()
        self.kind_cb.addItems(["custom", "lecture", "exercise", "study", "other"])

        self.module_cb = QComboBox()
        self.module_cb.addItem("— Kein Modul —", None)
        for m in self.repo.list_modules("all"):
            self.module_cb.addItem(m["name"], m["id"])

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())

        self.start_time = QLineEdit()
        self.start_time.setPlaceholderText("HH:MM (optional)")

        self.end_time = QLineEdit()
        self.end_time.setPlaceholderText("HH:MM (optional)")

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(70)
        self.notes.setPlaceholderText("Notizen...")

        form.addRow("Titel *:", self.title)
        form.addRow("Typ:", self.kind_cb)
        form.addRow("Modul:", self.module_cb)
        form.addRow("Von:", self.start_date)
        form.addRow("Bis:", self.end_date)
        form.addRow("Startzeit:", self.start_time)
        form.addRow("Endzeit:", self.end_time)
        form.addRow("Notizen:", self.notes)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _accept(self):
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        self.repo.add_event({
            "title": title,
            "kind": self.kind_cb.currentText(),
            "module_id": self.module_cb.currentData(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date.date().toString("yyyy-MM-dd"),
            "start_time": self.start_time.text().strip(),
            "end_time": self.end_time.text().strip(),
            "notes": self.notes.toPlainText(),
        })
        self.accept()
