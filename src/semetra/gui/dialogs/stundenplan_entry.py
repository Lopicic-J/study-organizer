from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QFormLayout, QFrame,
)
from PySide6.QtCore import Qt

from semetra.repo.sqlite_repo import SqliteRepo


class StundenplanEntryDialog(QDialog):
    """Dialog zum Hinzufügen oder Bearbeiten eines Stundenplan-Eintrags."""

    DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
            "Freitag", "Samstag", "Sonntag"]
    COLORS = [
        ("#7C3AED", "Lila"),
        ("#2563EB", "Blau"),
        ("#059669", "Grün"),
        ("#D97706", "Orange"),
        ("#DC2626", "Rot"),
        ("#0891B2", "Cyan"),
        ("#BE185D", "Pink"),
        ("#65A30D", "Limette"),
        ("#374151", "Grau"),
    ]

    def __init__(self, repo: SqliteRepo, entry: dict = None,
                 day: int = None, hour: int = None, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._entry = entry
        self._color = (entry or {}).get("color", self.COLORS[0][0])
        self.setWindowTitle("Eintrag bearbeiten" if entry else "Neuer Eintrag")
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build(day, hour)

    def _build(self, default_day: int = None, default_hour: int = None):
        e = self._entry or {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        title_lbl = QLabel("✏️  " + ("Eintrag bearbeiten" if self._entry else "Neuer Eintrag"))
        title_lbl.setObjectName("SectionTitle")
        lay.addWidget(title_lbl)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        # Subject
        self._subj = QLineEdit(e.get("subject", ""))
        self._subj.setPlaceholderText("Modulname oder Kursbezeichnung")
        form.addRow("Fach / Modul:", self._subj)

        # Day dropdown
        self._day_cb = QComboBox()
        for d in self.DAYS:
            self._day_cb.addItem(d)
        day_val = e.get("day_of_week", default_day)
        if day_val is not None:
            self._day_cb.setCurrentIndex(int(day_val))
        form.addRow("Tag:", self._day_cb)

        # Time from – to
        times = [f"{h:02d}:{m:02d}" for h in range(6, 23) for m in (0, 15, 30, 45)]
        time_row = QHBoxLayout()
        self._from_cb = QComboBox()
        self._to_cb = QComboBox()
        for t in times:
            self._from_cb.addItem(t)
            self._to_cb.addItem(t)
        dh = default_hour or 8
        default_from = e.get("time_from", f"{dh:02d}:00")
        default_to   = e.get("time_to",   f"{min(dh + 2, 22):02d}:00")
        self._from_cb.setCurrentIndex(times.index(default_from) if default_from in times else 0)
        self._to_cb.setCurrentIndex(times.index(default_to) if default_to in times else
                                    min(8, len(times) - 1))
        dash = QLabel("–")
        dash.setAlignment(Qt.AlignCenter)
        time_row.addWidget(self._from_cb, 1)
        time_row.addWidget(dash)
        time_row.addWidget(self._to_cb, 1)
        form.addRow("Zeit:", time_row)

        # Room
        self._room = QLineEdit(e.get("room", ""))
        self._room.setPlaceholderText("z.B. Raum B101 (optional)")
        form.addRow("Raum:", self._room)

        # Lecturer
        self._lec = QLineEdit(e.get("lecturer", ""))
        self._lec.setPlaceholderText("optional")
        form.addRow("Dozent:", self._lec)

        # Notes
        self._notes = QLineEdit(e.get("notes", ""))
        self._notes.setPlaceholderText("optional")
        form.addRow("Notizen:", self._notes)

        lay.addLayout(form)

        # Color chooser
        lay.addWidget(QLabel("Farbe:"))
        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        self._color_btns: list = []
        for hex_c, name in self.COLORS:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setToolTip(name)
            checked = (hex_c == self._color)
            btn.setStyleSheet(
                f"QPushButton{{background:{hex_c};border-radius:14px;"
                f"border:{'3px solid #111' if checked else '2px solid transparent'};}}"
                f"QPushButton:hover{{border:2px solid #555;}}"
            )
            btn.clicked.connect(lambda _, h=hex_c: self._pick_color(h))
            color_row.addWidget(btn)
            self._color_btns.append((hex_c, btn))
        color_row.addStretch()
        lay.addLayout(color_row)

        # Action buttons
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#E5E7EB;")
        lay.addWidget(sep)

        btns = QHBoxLayout()
        if self._entry:
            del_btn = QPushButton("🗑  Löschen")
            del_btn.setStyleSheet(
                "QPushButton{background:#FEF2F2;color:#DC2626;border:1.5px solid #FECACA;"
                "border-radius:8px;padding:6px 14px;font-weight:600;}"
                "QPushButton:hover{background:#FEE2E2;}"
            )
            del_btn.clicked.connect(self._delete)
            btns.addWidget(del_btn)
        btns.addStretch()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Speichern")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.clicked.connect(self._save)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        lay.addLayout(btns)

    def _pick_color(self, hex_color: str):
        self._color = hex_color
        for h, btn in self._color_btns:
            checked = (h == hex_color)
            btn.setStyleSheet(
                f"QPushButton{{background:{h};border-radius:14px;"
                f"border:{'3px solid #111' if checked else '2px solid transparent'};}}"
                f"QPushButton:hover{{border:2px solid #555;}}"
            )

    def _save(self):
        subject = self._subj.text().strip()
        if not subject:
            self._subj.setFocus()
            self._subj.setStyleSheet("border:1.5px solid #DC2626;border-radius:8px;")
            return
        data = {
            "subject":     subject,
            "day_of_week": self._day_cb.currentIndex(),
            "time_from":   self._from_cb.currentText(),
            "time_to":     self._to_cb.currentText(),
            "room":        self._room.text().strip(),
            "lecturer":    self._lec.text().strip(),
            "color":       self._color,
            "notes":       self._notes.text().strip(),
        }
        if self._entry:
            self._repo.update_stundenplan_entry(self._entry["id"], **data)
        else:
            self._repo.add_stundenplan_entry(data)
        self.accept()

    def _delete(self):
        if self._entry:
            self._repo.delete_stundenplan_entry(self._entry["id"])
            self.accept()
