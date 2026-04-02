"""Grades tracking page."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QLineEdit, QDialog, QDialogButtonBox, QSpinBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QComboBox as _QCBBase, QSizePolicy, QProgressBar, QScrollArea,
    QSplitter,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import QComboBox, StatCard, make_scroll
from semetra.gui.i18n import tr
from semetra.gui.colors import _tc, pct_to_ch_grade, _grade_color, _grade_bg, _grade_border, _grade_label, _grade_icon
from semetra.gui.helpers import mod_color, _active_sem_filter, _filter_mods_by_sem



class GradesPage(QWidget):
    """Noten-Übersicht — realitätsnah am Schweizer FH-Notensystem (1–6) ausgerichtet.

    Aufbau:
      • KPI-Leiste: Gesamt-GPA (ECTS-gewichtet), bestandene Module, kritische Module
      • Semester-Filter + Modulübersicht als Ampel-Cards (scrollbar)
      • Detailpanel rechts: einzelne Prüfungsleistungen des gewählten Moduls
        mit Note 1–6, Gewichtung und Zielvergleich
    """

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._sel_module_id: Optional[int] = None   # currently selected module
        self._build()

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        # Header ──────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel(tr("page.grades"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = QPushButton("+ Note hinzufügen")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_grade)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        # KPI cards ───────────────────────────────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        self._kpi_gpa   = self._make_kpi_card("Gesamt-GPA", "—", "ECTS-gewichtet")
        self._kpi_pass  = self._make_kpi_card("Bestanden", "—/—", "Module ≥ 4.0")
        self._kpi_warn  = self._make_kpi_card("⚠ Kritisch", "—", "< 4.0 · Handlungsbedarf")
        for card, _v, _s in (self._kpi_gpa, self._kpi_pass, self._kpi_warn):
            kpi_row.addWidget(card)
        kpi_row.addStretch()
        lay.addLayout(kpi_row)

        # Semester filter ─────────────────────────────────────────────────────
        filt_row = QHBoxLayout()
        filt_lbl = QLabel("Semester:")
        filt_lbl.setStyleSheet("font-size: 12px;")
        filt_row.addWidget(filt_lbl)
        self.sem_filter = QComboBox()
        self.sem_filter.setFixedWidth(160)
        self.sem_filter.currentIndexChanged.connect(self._rebuild_cards)
        filt_row.addWidget(self.sem_filter)
        filt_row.addStretch()
        # Note-Info label (Swiss grading reminder)
        info = QLabel("Notensystem 1–6  ·  Bestehensgrenze ≥ 4.0  ·  60 % = Note 4.0")
        info.setStyleSheet(f"font-size: 11px; color: {_tc('#888','#aaa')};")
        filt_row.addWidget(info)
        lay.addLayout(filt_row)

        # Main splitter: left=module cards, right=detail ──────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── LEFT: Modulübersicht ──────────────────────────────────────────────
        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        cards_lbl = QLabel("Modulübersicht")
        cards_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        left_lay.addWidget(cards_lbl)

        self._cards_scroll = QScrollArea()
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setFrameShape(QFrame.NoFrame)
        self._cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._cards_w = QWidget()
        self._cards_lay = QVBoxLayout(self._cards_w)
        self._cards_lay.setContentsMargins(2, 2, 2, 2)
        self._cards_lay.setSpacing(6)
        self._cards_lay.addStretch()
        self._cards_scroll.setWidget(self._cards_w)
        left_lay.addWidget(self._cards_scroll, 1)

        # ── RIGHT: Detailpanel ────────────────────────────────────────────────
        right_w = QWidget()
        right_lay = QVBoxLayout(right_w)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(8)

        # Module name + grade display
        self._detail_name = QLabel("← Modul auswählen")
        self._detail_name.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._detail_name.setWordWrap(True)
        right_lay.addWidget(self._detail_name)

        # Grade + status bar
        grade_row = QHBoxLayout()
        self._detail_grade = QLabel()
        self._detail_grade.setStyleSheet("font-size: 32px; font-weight: bold;")
        grade_row.addWidget(self._detail_grade)
        self._detail_status = QLabel()
        self._detail_status.setStyleSheet("font-size: 14px; font-weight: bold;")
        grade_row.addWidget(self._detail_status)
        grade_row.addStretch()
        self._detail_target = QLabel()
        self._detail_target.setStyleSheet("font-size: 12px;")
        grade_row.addWidget(self._detail_target)
        right_lay.addLayout(grade_row)

        # Progress bar for the module grade
        self._detail_bar = QProgressBar()
        self._detail_bar.setRange(0, 100)
        self._detail_bar.setTextVisible(False)
        self._detail_bar.setFixedHeight(6)
        right_lay.addWidget(self._detail_bar)

        # Prediction label (what grade is needed next?)
        self._detail_predict = QLabel()
        self._detail_predict.setStyleSheet(f"font-size: 11px; color: {_tc('#555','#aaa')};")
        self._detail_predict.setWordWrap(True)
        right_lay.addWidget(self._detail_predict)

        # Assessment table (Einzelnoten)
        detail_hdr = QLabel("Einzelleistungen")
        detail_hdr.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 6px;")
        right_lay.addWidget(detail_hdr)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Titel", "Eingabe", "Note (1–6)", "Gewicht %", "Datum", "ID"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnHidden(5, True)   # hidden ID column
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._edit_grade)
        self.table.setAlternatingRowColors(True)
        right_lay.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        edit_btn = QPushButton("✏ Bearbeiten")
        edit_btn.clicked.connect(self._edit_grade)
        del_btn = QPushButton("🗑 Löschen")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_grade)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        right_lay.addLayout(btn_row)

        splitter.addWidget(left_w)
        splitter.addWidget(right_w)
        splitter.setSizes([340, 560])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        lay.addWidget(splitter, 1)

    # ── KPI card factory ─────────────────────────────────────────────────────

    def _make_kpi_card(self, label: str, value: str, sublabel: str):
        """Returns (card_widget, value_label, sublabel_label)."""
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(186)
        card.setFixedHeight(88)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(2)
        lbl_w = QLabel(label)
        lbl_w.setStyleSheet(f"font-size: 11px; color: {_tc('#666','#aaa')};")
        val_w = QLabel(value)
        val_w.setStyleSheet("font-size: 26px; font-weight: bold;")
        sub_w = QLabel(sublabel)
        sub_w.setStyleSheet(f"font-size: 10px; color: {_tc('#888','#888')};")
        cl.addWidget(lbl_w)
        cl.addWidget(val_w)
        cl.addWidget(sub_w)
        return card, val_w, sub_w

    # ── Refresh (called from MainWindow on page switch) ───────────────────────

    def refresh(self):
        # Rebuild semester selector
        sem_f = _active_sem_filter(self.repo)
        mods_all = _filter_mods_by_sem(self.repo.list_modules("all"), sem_f)
        sems = sorted({str(m["semester"]) for m in mods_all if m["semester"]},
                      key=lambda s: int(s) if s.isdigit() else 99)

        cur_sem = self.sem_filter.currentData()
        self.sem_filter.blockSignals(True)
        self.sem_filter.clear()
        self.sem_filter.addItem("Alle Semester", "")
        for s in sems:
            self.sem_filter.addItem(f"Semester {s}", s)
        # Restore selection
        for i in range(self.sem_filter.count()):
            if self.sem_filter.itemData(i) == cur_sem:
                self.sem_filter.setCurrentIndex(i)
                break
        self.sem_filter.blockSignals(False)

        self._update_kpis()
        self._rebuild_cards()

    # ── KPI update ────────────────────────────────────────────────────────────

    def _update_kpis(self):
        all_mods = self.repo.list_modules("all")
        plan_mods = [m for m in all_mods
                     if (int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1)]

        graded = 0
        passed = 0
        critical = 0
        for m in plan_mods:
            avg = self.repo.module_weighted_grade(m["id"])
            if avg is None:
                continue
            ch = pct_to_ch_grade(avg)
            graded += 1
            if ch >= 4.0:
                passed += 1
            if ch < 4.0:
                critical += 1

        gpa = self.repo.ects_weighted_gpa()
        if gpa is not None:
            gpa_lbl = f"{gpa:.2f}"
            col = _grade_color(gpa)
            self._kpi_gpa[1].setText(gpa_lbl)
            self._kpi_gpa[1].setStyleSheet(f"font-size: 26px; font-weight: bold; color: {col};")
        else:
            self._kpi_gpa[1].setText("—")
            self._kpi_gpa[1].setStyleSheet("font-size: 26px; font-weight: bold;")

        self._kpi_pass[1].setText(f"{passed}/{graded}" if graded else "—/—")
        self._kpi_pass[1].setStyleSheet(
            f"font-size: 26px; font-weight: bold; "
            f"color: {_tc('#2E7D32','#4CAF50') if passed == graded and graded > 0 else _tc('#888','#aaa')};"
        )

        warn_col = _tc("#B71C1C", "#EF5350") if critical > 0 else _tc("#888", "#aaa")
        self._kpi_warn[1].setText(str(critical) if graded else "—")
        self._kpi_warn[1].setStyleSheet(
            f"font-size: 26px; font-weight: bold; color: {warn_col};"
        )

    # ── Module cards ─────────────────────────────────────────────────────────

    def _rebuild_cards(self):
        # Clear existing cards (keep trailing stretch)
        while self._cards_lay.count() > 1:
            item = self._cards_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sem_f = _active_sem_filter(self.repo)
        sel_sem = self.sem_filter.currentData() or ""
        mods = _filter_mods_by_sem(self.repo.list_modules("all"), sem_f)
        if sel_sem:
            mods = [m for m in mods if str(m["semester"]) == sel_sem]
        # Sort: in-plan first, then by semester, then name
        mods = sorted(mods,
                      key=lambda m: (
                          0 if (int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1) else 1,
                          int(m["semester"]) if str(m["semester"]).isdigit() else 99,
                          m["name"]
                      ))

        for m in mods:
            card = self._make_module_card(m)
            self._cards_lay.insertWidget(self._cards_lay.count() - 1, card)

        # If selected module still exists, keep its detail; else reset
        if self._sel_module_id not in {m["id"] for m in mods}:
            self._sel_module_id = None
            self._clear_detail()

    def _make_module_card(self, m) -> QFrame:
        """Build a compact module card with Ampel-color and grade display."""
        in_plan = int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1
        avg_pct = self.repo.module_weighted_grade(m["id"])
        has_grade = avg_pct is not None

        if has_grade:
            ch = pct_to_ch_grade(avg_pct)
            bg = _grade_bg(ch)
            border = _grade_border(ch)
        else:
            bg = _tc("#F5F5F5", "#2A2A2A")
            border = _tc("#DDD", "#444")

        is_selected = (m["id"] == self._sel_module_id)
        sel_border = _tc("#7C3AED", "#A78BFA") if is_selected else border

        card = QFrame()
        card.setFixedHeight(84)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 2px solid {sel_border}; "
            f"border-radius: 8px; }} "
            f"QFrame:hover {{ border-color: {_tc('#7C3AED','#A78BFA')}; }}"
        )

        lay = QHBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        # Left: name + meta
        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(m["name"])
        name_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: bold; "
            f"color: {_tc('#333','#eee') if in_plan else _tc('#aaa','#555')};"
            + ("text-decoration: line-through;" if not in_plan else "")
        )
        name_lbl.setWordWrap(True)
        info.addWidget(name_lbl)

        sem_txt = f"Sem. {m['semester']}  ·  {float(m['ects']):.0f} ECTS"
        meta_lbl = QLabel(sem_txt)
        meta_lbl.setStyleSheet(f"font-size: 10px; color: {_tc('#777','#999')};")
        info.addWidget(meta_lbl)

        # Target grade hint
        tg = m["target_grade"] if "target_grade" in m.keys() else None
        if tg is not None and has_grade:
            tg_diff = ch - float(tg)
            tg_icon = "✅" if tg_diff >= 0 else "❌"
            tg_lbl = QLabel(f"{tg_icon} Ziel {float(tg):.1f}  ({tg_diff:+.2f})")
            tg_lbl.setStyleSheet(
                f"font-size: 10px; color: "
                f"{'#2E7D32' if tg_diff >= 0 else '#C62828'};"
            )
            info.addWidget(tg_lbl)
        elif tg is not None:
            tg_lbl = QLabel(f"🎯 Ziel: {float(tg):.1f}")
            tg_lbl.setStyleSheet(f"font-size: 10px; color: {_tc('#777','#999')};")
            info.addWidget(tg_lbl)

        lay.addLayout(info, 1)

        # Right: big grade number
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right.setSpacing(2)
        if has_grade:
            grade_lbl = QLabel(f"{ch:.2f}")
            grade_lbl.setStyleSheet(
                f"font-size: 22px; font-weight: bold; color: {_grade_color(ch)};"
            )
            grade_lbl.setAlignment(Qt.AlignRight)
            status_lbl = QLabel(_grade_icon(ch) + " " + _grade_label(ch))
            status_lbl.setStyleSheet(
                f"font-size: 10px; color: {_grade_color(ch)}; font-weight: bold;"
            )
            status_lbl.setAlignment(Qt.AlignRight)
            right.addWidget(grade_lbl)
            right.addWidget(status_lbl)
        else:
            no_lbl = QLabel("keine\nNoten")
            no_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            no_lbl.setStyleSheet(f"font-size: 10px; color: {_tc('#bbb','#555')};")
            right.addWidget(no_lbl)
        lay.addLayout(right)

        # Click: select module
        card.mousePressEvent = lambda _e, mid=m["id"]: self._select_module(mid)
        return card

    def _select_module(self, module_id: int):
        self._sel_module_id = module_id
        self._rebuild_cards()        # re-render to update selection highlight
        self._load_detail(module_id)

    # ── Detail panel ─────────────────────────────────────────────────────────

    def _clear_detail(self):
        self._detail_name.setText("← Modul auswählen")
        self._detail_grade.setText("")
        self._detail_status.setText("")
        self._detail_target.setText("")
        self._detail_predict.setText("")
        self._detail_bar.setValue(0)
        self.table.setRowCount(0)

    def _load_detail(self, module_id: int):
        mod = self.repo.get_module(module_id)
        if not mod:
            self._clear_detail()
            return

        self._detail_name.setText(mod["name"])
        avg_pct = self.repo.module_weighted_grade(module_id)

        if avg_pct is not None:
            ch = pct_to_ch_grade(avg_pct)
            col = _grade_color(ch)
            self._detail_grade.setText(f"{ch:.2f}")
            self._detail_grade.setStyleSheet(
                f"font-size: 32px; font-weight: bold; color: {col};"
            )
            self._detail_status.setText(f"{_grade_icon(ch)}  {_grade_label(ch)}")
            self._detail_status.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {col};"
            )
            # Progress bar: map 1–6 grade to 0–100% for visual
            bar_val = int((ch - 1.0) / 5.0 * 100)
            self._detail_bar.setValue(bar_val)
            bar_style = (
                f"QProgressBar::chunk {{ background: {col}; border-radius: 3px; }} "
                f"QProgressBar {{ background: {_tc('#EEE','#333')}; border-radius: 3px; border: none; }}"
            )
            self._detail_bar.setStyleSheet(bar_style)
        else:
            self._detail_grade.setText("—")
            self._detail_grade.setStyleSheet("font-size: 32px; font-weight: bold;")
            self._detail_status.setText("Noch keine Noten")
            self._detail_status.setStyleSheet(f"font-size: 14px; color: {_tc('#888','#aaa')};")
            self._detail_bar.setValue(0)

        # Target grade comparison
        tg = mod["target_grade"] if "target_grade" in mod.keys() else None
        if tg is not None and avg_pct is not None:
            diff = pct_to_ch_grade(avg_pct) - float(tg)
            icon = "✅" if diff >= 0 else "❌"
            self._detail_target.setText(f"{icon} Zielnote: {float(tg):.1f}  ({diff:+.2f})")
            self._detail_target.setStyleSheet(
                f"font-size: 12px; color: "
                f"{'#2E7D32' if diff >= 0 else '#C62828'}; font-weight: bold;"
            )
        elif tg is not None:
            self._detail_target.setText(f"🎯 Zielnote: {float(tg):.1f}")
            self._detail_target.setStyleSheet(f"font-size: 12px; color: {_tc('#555','#aaa')};")
        else:
            self._detail_target.setText("")

        # Prediction: what CH grade is needed on next assessment to reach target?
        if tg is not None and avg_pct is not None:
            grades = self.repo.list_grades(module_id=module_id)
            total_w = sum(float(g["weight"]) for g in grades)
            tg_pct = (float(tg) - 1.0) / 5.0 * 100.0   # target as %
            # needed score for 1 more unit-weight assessment:
            needed_pct = tg_pct * (total_w + 1.0) - avg_pct * total_w
            if needed_pct > 100:
                self._detail_predict.setText(
                    f"⚠ Zielnote {float(tg):.1f} ist mit einer weiteren Leistung nicht mehr erreichbar."
                )
            elif needed_pct >= 0:
                needed_ch = pct_to_ch_grade(needed_pct)
                self._detail_predict.setText(
                    f"ℹ Für Zielnote {float(tg):.1f}: nächste Leistung mind. "
                    f"{needed_ch:.1f} (≈ {needed_pct:.0f} %)"
                )
            else:
                self._detail_predict.setText(
                    f"✅ Zielnote {float(tg):.1f} bereits sicher erreicht."
                )
        else:
            self._detail_predict.setText("")

        # Fill assessment table
        self._load_grades_table(module_id)

    def _load_grades_table(self, module_id: int):
        grades = self.repo.list_grades(module_id=module_id)
        self.table.setRowCount(len(grades))
        total_w = sum(float(g["weight"]) for g in grades)

        for r, g in enumerate(grades):
            mode = g["grade_mode"] if "grade_mode" in g.keys() else "points"

            # Column 0: Title
            self.table.setItem(r, 0, QTableWidgetItem(g["title"]))

            # Column 1: Raw input display
            if mode == "direct":
                raw_txt = f"Note {float(g['grade']):.1f}"
            else:
                pct = float(g["grade"]) / float(g["max_grade"]) * 100
                raw_txt = f"{g['grade']:.1f} / {g['max_grade']:.0f}  ({pct:.0f} %)"
            self.table.setItem(r, 1, QTableWidgetItem(raw_txt))

            # Column 2: Swiss grade 1–6
            if mode == "direct":
                ch = float(g["grade"])
            else:
                ch = pct_to_ch_grade(float(g["grade"]) / float(g["max_grade"]) * 100)

            note_item = QTableWidgetItem(f"{_grade_icon(ch)}  {ch:.2f}")
            note_item.setForeground(QColor(_grade_color(ch)))
            self.table.setItem(r, 2, note_item)

            # Column 3: Weight (as % of total)
            w_pct = float(g["weight"]) / total_w * 100 if total_w > 0 else 0
            self.table.setItem(r, 3, QTableWidgetItem(f"{w_pct:.0f} %"))

            # Column 4: Date
            self.table.setItem(r, 4, QTableWidgetItem(g["date"] or "—"))

            # Column 5: hidden ID
            self.table.setItem(r, 5, QTableWidgetItem(str(g["id"])))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add_grade(self):
        # Free-plan limit: max 3 Noten gesamt
        from semetra.infra.license import LicenseManager
        from semetra.gui.dialogs.pro_feature import ProFeatureDialog
        from semetra.gui.dialogs.grade_dialog import GradeDialog
        lm = LicenseManager(self.repo)
        if not lm.is_pro():
            total_grades = len(self.repo.list_grades())
            if total_grades >= 3:
                dlg = ProFeatureDialog("Mehr als 3 Noten", self.repo, parent=self)
                if dlg.exec() != QDialog.Accepted:
                    return
                lm._cached = None
                if not lm.is_pro():
                    return
        dlg = GradeDialog(self.repo, default_module_id=self._sel_module_id, parent=self)
        if dlg.exec():
            self._update_kpis()
            self._rebuild_cards()
            if self._sel_module_id:
                self._load_detail(self._sel_module_id)

    def _edit_grade(self):
        row = self.table.currentRow()
        if row < 0:
            return
        gid = int(self.table.item(row, 5).text())
        from semetra.gui.dialogs.grade_dialog import GradeDialog
        if GradeDialog(self.repo, grade_id=gid, parent=self).exec():
            self._update_kpis()
            self._rebuild_cards()
            if self._sel_module_id:
                self._load_detail(self._sel_module_id)

    def _delete_grade(self):
        row = self.table.currentRow()
        if row < 0:
            return
        gid = int(self.table.item(row, 5).text())
        if QMessageBox.question(
            self, "Löschen", "Eintrag löschen?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.repo.delete_grade(gid)
            self._update_kpis()
            self._rebuild_cards()
            if self._sel_module_id:
                self._load_detail(self._sel_module_id)


