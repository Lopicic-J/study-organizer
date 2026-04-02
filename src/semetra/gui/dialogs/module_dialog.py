from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QDoubleSpinBox, QComboBox, QCheckBox,
    QDateEdit, QDialogButtonBox, QMessageBox,
)
from PySide6.QtCore import Qt, QDate

from semetra.repo.sqlite_repo import SqliteRepo


class ModuleDialog(QDialog):
    def __init__(self, repo: SqliteRepo, module_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.module_id = module_id
        self.setWindowTitle("Modul bearbeiten" if module_id else "Neues Modul")
        self.setMinimumWidth(460)
        self._build()
        if module_id:
            self._load(module_id)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        self.name = QLineEdit()
        self.semester = QLineEdit()
        self.ects = QDoubleSpinBox()
        self.ects.setRange(0, 60)
        self.ects.setSingleStep(0.5)
        self.lecturer = QLineEdit()
        self.link = QLineEdit()
        self.github_link = QLineEdit()
        self.sharepoint_link = QLineEdit()
        self.notes_link = QLineEdit()
        self.literature_links = QLineEdit()
        self.status = QComboBox()
        self.status.addItems(["planned", "active", "completed", "paused"])
        self.module_type = QComboBox()
        self.module_type.addItems(["pflicht", "wahl", "vertiefung"])

        # Prüfungsdatum: optional via checkbox
        self._exam_date_check = QCheckBox("Prüfungsdatum festlegen")
        self._exam_date_check.setChecked(False)
        self.exam_date = QDateEdit()
        self.exam_date.setCalendarPopup(True)
        self.exam_date.setDate(QDate.currentDate())
        self.exam_date.setEnabled(False)
        self._exam_date_check.toggled.connect(self.exam_date.setEnabled)

        self.weighting = QDoubleSpinBox()
        self.weighting.setRange(0.1, 10.0)
        self.weighting.setSingleStep(0.1)
        self.weighting.setValue(1.0)

        # Target grade
        self.target_grade = QDoubleSpinBox()
        self.target_grade.setRange(0.0, 6.0)
        self.target_grade.setSingleStep(0.1)
        self.target_grade.setDecimals(1)
        self.target_grade.setSpecialValueText("— kein Ziel —")
        self.target_grade.setValue(0.0)  # 0.0 = no target (shown as "— kein Ziel —")

        # ── Pflichtfelder ────────────────────────────────────────────────
        form.addRow("Name *:", self.name)
        form.addRow("Semester *:", self.semester)
        form.addRow("ECTS *:", self.ects)
        form.addRow("Modultyp *:", self.module_type)

        # ── Optionale Felder ────────────────────────────────────────────
        form.addRow("Gewichtung:", self.weighting)
        form.addRow("Status:", self.status)

        # Exam date row: checkbox + date picker side by side
        exam_row = QHBoxLayout()
        exam_row.setSpacing(6)
        exam_row.addWidget(self._exam_date_check)
        exam_row.addWidget(self.exam_date)
        exam_row.addStretch()
        form.addRow("Prüfung:", exam_row)

        form.addRow("Dozent:", self.lecturer)
        form.addRow("Zielnote:", self.target_grade)
        form.addRow("Kurs-Link:", self.link)
        form.addRow("GitHub:", self.github_link)
        form.addRow("SharePoint:", self.sharepoint_link)
        form.addRow("Literatur:", self.literature_links)
        form.addRow("Notizen-Link:", self.notes_link)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _load(self, mid: int):
        m = self.repo.get_module(mid)
        if not m:
            return
        self.name.setText(m["name"])
        self.semester.setText(m["semester"])
        self.ects.setValue(float(m["ects"]))
        self.lecturer.setText(m["lecturer"] or "")
        self.link.setText(m["link"] or "")
        self.github_link.setText(m["github_link"] or "")
        self.sharepoint_link.setText(m["sharepoint_link"] or "")
        self.notes_link.setText(m["notes_link"] or "")
        self.literature_links.setText(m["literature_links"] or "")
        idx = self.status.findText(m["status"])
        if idx >= 0:
            self.status.setCurrentIndex(idx)
        if m["exam_date"]:
            try:
                d = datetime.strptime(m["exam_date"], "%Y-%m-%d").date()
                self.exam_date.setDate(QDate(d.year, d.month, d.day))
                self._exam_date_check.setChecked(True)
            except Exception:
                pass
        self.weighting.setValue(float(m["weighting"]))
        mt = m["module_type"] if "module_type" in m.keys() else "pflicht"
        mt_idx = self.module_type.findText(mt or "pflicht")
        if mt_idx >= 0:
            self.module_type.setCurrentIndex(mt_idx)
        tg = (m["target_grade"] if "target_grade" in m.keys() and m["target_grade"] is not None else 0.0)
        self.target_grade.setValue(float(tg))

    def _accept(self):
        name = self.name.text().strip()
        sem = self.semester.text().strip()
        if not name or not sem:
            QMessageBox.warning(self, "Fehler",
                "Name, Semester, ECTS und Modultyp sind Pflichtfelder.")
            return
        if self.ects.value() <= 0:
            QMessageBox.warning(self, "Fehler",
                "Bitte gib eine gültige ECTS-Anzahl an (> 0).")
            return

        # Free-plan limit: max 2 Module pro Semester
        if not self.module_id:  # only for new modules, not edits
            from semetra.infra.license import LicenseManager
            lm = LicenseManager(self.repo)
            if not lm.is_pro():
                all_mods = self.repo.list_modules("all")
                sem_count = sum(1 for m in all_mods if m["semester"] == sem)
                if sem_count >= 2:
                    from semetra.gui.dialogs import ProFeatureDialog
                    dlg = ProFeatureDialog(
                        "Mehr als 2 Module pro Semester",
                        self.repo, parent=self
                    )
                    if dlg.exec() != QDialog.Accepted:
                        return
                    # Re-check after potential upgrade
                    lm._cached = None
                    if not lm.is_pro():
                        return

        exam_str = (self.exam_date.date().toString("yyyy-MM-dd")
                    if self._exam_date_check.isChecked() else "")
        tg_val = self.target_grade.value()
        data = {
            "name": name, "semester": sem,
            "module_type": self.module_type.currentText(),
            "ects": self.ects.value(),
            "lecturer": self.lecturer.text().strip(),
            "link": self.link.text().strip(),
            "github_link": self.github_link.text().strip(),
            "sharepoint_link": self.sharepoint_link.text().strip(),
            "notes_link": self.notes_link.text().strip(),
            "literature_links": self.literature_links.text().strip(),
            "status": self.status.currentText(),
            "exam_date": exam_str,
            "weighting": self.weighting.value(),
            "target_grade": tg_val if tg_val > 0 else None,
        }
        if self.module_id:
            self.repo.update_module(self.module_id, **data)
        else:
            self.repo.add_module(data)
        self.accept()
