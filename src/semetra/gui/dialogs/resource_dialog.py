from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QLabel, QDialogButtonBox, QMessageBox,
)
from PySide6.QtCore import Qt


class ResourceDialog(QDialog):
    """Dialog to add a study resource (video, book, tool, article, etc.) to a module."""

    TYPES = [
        ("youtube", "▶️  YouTube Video"),
        ("video",   "🎬  Video (anderes)"),
        ("book",    "📖  Buch / Lehrmittel"),
        ("article", "📄  Artikel / Blog"),
        ("doc",     "📚  Dokumentation"),
        ("tool",    "🔧  Tool / Programm"),
        ("web",     "🌐  Website"),
        ("other",   "🔗  Sonstiges"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowTitle("Ressource hinzufügen")
        self.setMinimumWidth(440)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        self.type_cb = QComboBox()
        for key, label in self.TYPES:
            self.type_cb.addItem(label, key)
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("z.B. Java Tutorial für Anfänger")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://...")

        form.addRow("Typ:", self.type_cb)
        form.addRow("Bezeichnung *:", self.label_edit)
        form.addRow("URL *:", self.url_edit)
        lay.addLayout(form)

        hint = QLabel(
            "💡 Tipp: YouTube, Bücher, Moodle-Kurse, Stack Overflow, GitHub, "
            "offizielle Docs — alles was beim Lernen hilft."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#706C86;font-size:11px;padding:4px 0;")
        lay.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _accept(self):
        label = self.label_edit.text().strip()
        url = self.url_edit.text().strip()
        if not label or not url:
            QMessageBox.warning(self, "Fehler", "Bezeichnung und URL sind Pflichtfelder.")
            return
        if not url.startswith("http"):
            url = "https://" + url
        self.accept()

    def get_values(self):
        return (
            self.type_cb.currentData(),
            self.label_edit.text().strip(),
            self.url_edit.text().strip() if self.url_edit.text().strip().startswith("http")
            else "https://" + self.url_edit.text().strip(),
        )
