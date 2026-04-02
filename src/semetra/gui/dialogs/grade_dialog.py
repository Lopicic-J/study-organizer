from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QDoubleSpinBox, QComboBox,
    QDateEdit, QDialogButtonBox, QMessageBox,
)
from PySide6.QtCore import Qt, QDate

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.colors import _tc


def pct_to_ch_grade(pct: float) -> float:
    """Convert percentage (0–100) to Swiss FH grade (1.0–6.0).
    Result is NOT rounded — use for display rounding separately."""
    return (pct / 100.0) * 5.0 + 1.0


def ch_grade_rounded(pct: float) -> float:
    """Convert percentage to Swiss FH grade rounded to nearest 0.5 step."""
    raw = pct_to_ch_grade(pct)
    return round(raw * 2) / 2


def _grade_color(grade: float) -> str:
    """Theme-adaptive text colour for a Swiss 1–6 grade."""
    if grade >= 5.5: return _tc("#1B5E20", "#69F0AE")
    if grade >= 5.0: return _tc("#2E7D32", "#4CAF50")
    if grade >= 4.5: return _tc("#558B2F", "#8BC34A")
    if grade >= 4.0: return _tc("#E65100", "#FFA726")
    if grade >= 3.5: return _tc("#BF360C", "#FF7043")
    return _tc("#B71C1C", "#EF5350")


def _grade_label(grade: float) -> str:
    """Human-readable status label for Swiss 1–6 grade."""
    if grade >= 5.5: return "Sehr gut"
    if grade >= 5.0: return "Gut"
    if grade >= 4.5: return "Befriedigend"
    if grade >= 4.0: return "Genügend"
    if grade >= 3.5: return "⚠ Gefährdet!"
    return "✗ Nicht bestanden"


def _grade_icon(grade: float) -> str:
    """Emoji icon for Swiss grade status."""
    if grade >= 5.5: return "✨"
    if grade >= 5.0: return "✅"
    if grade >= 4.5: return "🟢"
    if grade >= 4.0: return "🟡"
    if grade >= 3.5: return "🟠"
    return "🔴"


class GradeDialog(QDialog):
    """Dialog zum Erfassen/Bearbeiten einer Prüfungsleistung.

    Zwei Eingabemodi (per Toggle wählbar):
    • Punkte-Modus  — Eingabe: Erreichte Punkte + Max. Punkte → Note wird live berechnet
    • Direkte Note  — Eingabe: Note 1.0–6.0 direkt (in 0.5-Schritten), z. B. aus Zeugnis
    """

    def __init__(self, repo: SqliteRepo, grade_id: Optional[int] = None,
                 default_module_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.grade_id = grade_id
        self._mode = "points"
        self.setWindowTitle("Note bearbeiten" if grade_id else "Note hinzufügen")
        self.setMinimumWidth(420)
        self._build()
        if grade_id:
            self._load(grade_id)
        elif default_module_id:
            self._set_module(default_module_id)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # ── Mode toggle ───────────────────────────────────────────────────────
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Eingabe-Modus:"))
        self._btn_points = QPushButton("📊 Punkte")
        self._btn_points.setCheckable(True)
        self._btn_points.setChecked(True)
        self._btn_points.clicked.connect(lambda: self._set_mode("points"))
        self._btn_direct = QPushButton("🎓 Direkte Note (1–6)")
        self._btn_direct.setCheckable(True)
        self._btn_direct.setChecked(False)
        self._btn_direct.clicked.connect(lambda: self._set_mode("direct"))
        mode_row.addWidget(self._btn_points)
        mode_row.addWidget(self._btn_direct)
        mode_row.addStretch()
        lay.addLayout(mode_row)

        # ── Form ──────────────────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(10)

        self.title = QLineEdit()
        form.addRow("Titel *:", self.title)

        self.module_cb = QComboBox()
        for m in self.repo.list_modules("all"):
            self.module_cb.addItem(m["name"], m["id"])
        form.addRow("Modul:", self.module_cb)

        # Points mode widgets
        self.grade_pts = QDoubleSpinBox()
        self.grade_pts.setRange(0, 10000)
        self.grade_pts.setDecimals(2)
        self.grade_pts.setSuffix(" Pkt")
        self.grade_pts.valueChanged.connect(self._update_preview)

        self.max_grade_pts = QDoubleSpinBox()
        self.max_grade_pts.setRange(1, 10000)
        self.max_grade_pts.setDecimals(2)
        self.max_grade_pts.setValue(100)
        self.max_grade_pts.setSuffix(" Pkt")
        self.max_grade_pts.valueChanged.connect(self._update_preview)

        self._row_pts  = form.addRow("Erreichte Punkte:", self.grade_pts)
        self._row_max  = form.addRow("Max. Punkte:", self.max_grade_pts)

        # Direct mode widget
        self.grade_direct = QDoubleSpinBox()
        self.grade_direct.setRange(1.0, 6.0)
        self.grade_direct.setSingleStep(0.5)
        self.grade_direct.setDecimals(1)
        self.grade_direct.setValue(4.0)
        self.grade_direct.setSpecialValueText("")
        self.grade_direct.setToolTip(
            "Schweizer FH-Note: 1.0–6.0\n"
            "Bestehensgrenze: 4.0\n"
            "Schritte: 0.5  (1.0 / 1.5 / 2.0 … 5.5 / 6.0)"
        )
        self.grade_direct.valueChanged.connect(self._update_preview)
        self._row_direct = form.addRow("Note (1.0–6.0):", self.grade_direct)

        # Weight
        self.weight = QDoubleSpinBox()
        self.weight.setRange(0.01, 100)
        self.weight.setDecimals(2)
        self.weight.setValue(1.0)
        self.weight.setToolTip(
            "Relative Gewichtung dieser Leistung.\n"
            "Beispiel: Prüfung = 2.0, Testat = 1.0  →  Prüfung zählt doppelt."
        )
        form.addRow("Gewichtung:", self.weight)

        self.date_e = QDateEdit()
        self.date_e.setCalendarPopup(True)
        self.date_e.setDate(QDate.currentDate())
        form.addRow("Datum:", self.date_e)

        self.notes = QLineEdit()
        form.addRow("Notizen:", self.notes)
        lay.addLayout(form)

        # ── Live preview ──────────────────────────────────────────────────────
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setStyleSheet(
            f"font-size: 15px; font-weight: bold; padding: 8px; "
            f"border-radius: 6px; background: {_tc('#F5F5F5','#2A2A2A')};"
        )
        self._preview.setMinimumHeight(44)
        lay.addWidget(self._preview)

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._set_mode("points")

    # ── Mode switching ────────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        self._mode = mode
        is_pts = (mode == "points")
        self._btn_points.setChecked(is_pts)
        self._btn_direct.setChecked(not is_pts)
        self.grade_pts.setVisible(is_pts)
        self.max_grade_pts.setVisible(is_pts)
        self.grade_direct.setVisible(not is_pts)
        self._update_preview()

    # ── Preview update ────────────────────────────────────────────────────────

    def _update_preview(self):
        try:
            if self._mode == "points":
                pts = self.grade_pts.value()
                maxp = self.max_grade_pts.value()
                if maxp <= 0:
                    self._preview.setText("—")
                    return
                pct = pts / maxp * 100.0
                ch = pct_to_ch_grade(pct)
                ch_r = ch_grade_rounded(pct)
                col = _grade_color(ch)
                self._preview.setText(
                    f"Note: <span style='color:{col}'>{ch:.2f}</span>  "
                    f"(gerundet: {ch_r:.1f})  ·  "
                    f"{_grade_icon(ch)} {_grade_label(ch)}"
                )
            else:
                ch = self.grade_direct.value()
                col = _grade_color(ch)
                self._preview.setText(
                    f"Note: <span style='color:{col}'>{ch:.1f}</span>  ·  "
                    f"{_grade_icon(ch)} {_grade_label(ch)}"
                )
        except Exception:
            self._preview.setText("—")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_module(self, mid: int):
        for i in range(self.module_cb.count()):
            if self.module_cb.itemData(i) == mid:
                self.module_cb.setCurrentIndex(i)
                break

    def _load(self, gid: int):
        rows = self.repo.list_grades()
        g = next((r for r in rows if r["id"] == gid), None)
        if not g:
            return
        self.title.setText(g["title"])
        self._set_module(g["module_id"])

        mode = g["grade_mode"] if "grade_mode" in g.keys() else "points"
        self._set_mode(mode)
        if mode == "direct":
            self.grade_direct.setValue(float(g["grade"]))
        else:
            self.grade_pts.setValue(float(g["grade"]))
            self.max_grade_pts.setValue(float(g["max_grade"]))

        self.weight.setValue(float(g["weight"]))
        if g["date"]:
            try:
                d = datetime.strptime(g["date"], "%Y-%m-%d").date()
                self.date_e.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                pass
        self.notes.setText(g["notes"] or "")
        self._update_preview()

    # ── Accept / Save ─────────────────────────────────────────────────────────

    def _accept(self):
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        mid = self.module_cb.currentData()
        date_str = self.date_e.date().toString("yyyy-MM-dd")

        if self._mode == "direct":
            grade_val = self.grade_direct.value()
            max_val = 6.0
        else:
            grade_val = self.grade_pts.value()
            max_val = self.max_grade_pts.value()

        if self.grade_id:
            self.repo.update_grade(
                self.grade_id,
                title=title, module_id=mid,
                grade=grade_val, max_grade=max_val,
                weight=self.weight.value(), date=date_str,
                notes=self.notes.text(),
                grade_mode=self._mode,
            )
        else:
            self.repo.add_grade(
                mid, title,
                grade=grade_val, max_grade=max_val,
                weight=self.weight.value(), date_str=date_str,
                notes=self.notes.text(),
                grade_mode=self._mode,
            )
        self.accept()
