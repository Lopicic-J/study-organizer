"""Exam management page."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QLineEdit, QDialog, QDialogButtonBox, QDateEdit, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSizePolicy, QComboBox as _QCBBase, QCheckBox, QProgressBar, QSplitter,
    QTextEdit,
)
from PySide6.QtCore import Qt, QTimer, QDate

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import QComboBox, StatCard, make_scroll, ColorDot
from semetra.gui.i18n import tr
from semetra.gui.helpers import mod_color, days_until, _active_sem_filter, _filter_mods_by_sem, exam_priority
from semetra.gui.colors import _tc



class ExamPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._selected_mid: Optional[int] = None
        self._global_refresh: Optional[callable] = None
        self._build()

    def set_global_refresh(self, cb):
        self._global_refresh = cb

    # ── layout ───────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel(tr("page.exams"))
        title.setObjectName("PageTitle")
        outer.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # ── Left: exam list ──────────────────────────────────────────────────
        left_w = QWidget()
        left_w.setAttribute(Qt.WA_StyledBackground, True)
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(0)

        self._list_w = QWidget()
        self._list_lay = QVBoxLayout(self._list_w)
        self._list_lay.setContentsMargins(0, 0, 8, 0)
        self._list_lay.setSpacing(8)
        left_lay.addWidget(make_scroll(self._list_w), 1)
        splitter.addWidget(left_w)

        # ── Right: checklist detail panel ────────────────────────────────────
        right_w = QWidget()
        right_w.setAttribute(Qt.WA_StyledBackground, True)
        self._right_lay = QVBoxLayout(right_w)
        self._right_lay.setContentsMargins(16, 0, 0, 0)
        self._right_lay.setSpacing(12)
        self._right_lay.addWidget(self._empty_right())
        splitter.addWidget(right_w)

        splitter.setSizes([420, 560])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        outer.addWidget(splitter, 1)

    @staticmethod
    def _empty_right() -> QLabel:
        lbl = QLabel("← Prüfung auswählen um\ndie Lernziel-Checkliste zu sehen")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color:{_tc('#706C86','#6B7280')};font-size:14px;")
        return lbl

    # ── data loading ─────────────────────────────────────────────────────────

    def refresh(self):
        # Rebuild exam list
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Apply global semester filter
        sem_f = _active_sem_filter(self.repo)
        exams = _filter_mods_by_sem(self.repo.all_exams(), sem_f)

        if not exams:
            lbl = QLabel("Keine Prüfungen erfasst.\nPrüfungsdaten in den Modulen hinzufügen.")
            lbl.setStyleSheet(f"color:{_tc('#706C86','#6B7280')};font-size:13px;")
            lbl.setAlignment(Qt.AlignCenter)
            self._list_lay.addWidget(lbl)
        else:
            for m in exams:
                self._list_lay.addWidget(self._make_card(m))
        self._list_lay.addStretch()

        # Re-populate detail if a module was already selected
        if self._selected_mid is not None:
            self._populate_detail(self._selected_mid)

    def _make_card(self, m) -> QFrame:
        mid = m["id"]
        color = mod_color(mid)
        selected = (mid == self._selected_mid)

        card = QFrame()
        card.setObjectName("Card")
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(
            f"QFrame#Card{{border:2px solid "
            f"{'#4A86E8' if selected else _tc('#E4E8F0','#2A2A3A')};border-radius:8px;}}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(7)

        # Header row
        hdr = QHBoxLayout()
        hdr.addWidget(ColorDot(color, 12))
        name_lbl = QLabel(m["name"])
        name_lbl.setStyleSheet(
            f"font-size:14px;font-weight:700;color:{_tc('#1A1A2E','#CDD6F4')};"
        )
        hdr.addWidget(name_lbl, 1)

        d = days_until(m["exam_date"])
        if d is None:   d_txt, d_col = "Kein Datum", "#9E9E9E"
        elif d < 0:     d_txt, d_col = f"Vor {abs(d)} T.", "#9E9E9E"
        elif d == 0:    d_txt, d_col = "HEUTE!", "#F44336"
        elif d <= 7:    d_txt, d_col = f"in {d} T.", "#FF9800"
        else:           d_txt, d_col = f"in {d} T.", "#4A86E8"
        date_lbl = QLabel(f"📅 {m['exam_date']}  ·  {d_txt}")
        date_lbl.setStyleSheet(f"font-size:11px;color:{d_col};font-weight:700;")
        hdr.addWidget(date_lbl)
        lay.addLayout(hdr)

        # Study-hour progress bar
        target   = self.repo.ects_target_hours(mid)
        studied_h = self.repo.seconds_studied_for_module(mid) / 3600
        pct = min(100, int(studied_h / target * 100)) if target > 0 else 0
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setFixedHeight(6)
        bar.setTextVisible(False)
        bar.setStyleSheet(
            f"QProgressBar{{background:{_tc('#EAEAEA','#2A2A3A')};border-radius:3px;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:3px;}}"
        )
        lay.addWidget(bar)

        # Objective checklist progress
        objs = self.repo.list_scraped_data(mid, "objective")
        tasks_m  = self.repo.list_tasks(module_id=mid)
        t_done_m = sum(1 for t in tasks_m if t["status"] == "Done")
        t_total_m = len(tasks_m)
        tasks_txt = f"  ·  ☑ {t_done_m}/{t_total_m} Aufgaben" if t_total_m else ""
        if objs:
            done = sum(1 for o in objs if int(o["checked"] if "checked" in o.keys() and o["checked"] is not None else 0))
            total = len(objs)
            obj_pct = int(done / total * 100) if total else 0
            obj_bar = QProgressBar()
            obj_bar.setRange(0, 100)
            obj_bar.setValue(obj_pct)
            obj_bar.setFixedHeight(6)
            obj_bar.setTextVisible(False)
            obj_bar.setStyleSheet(
                f"QProgressBar{{background:{_tc('#EAEAEA','#2A2A3A')};border-radius:3px;}}"
                f"QProgressBar::chunk{{background:#2CB67D;border-radius:3px;}}"
            )
            lay.addWidget(obj_bar)
            meta = QLabel(
                f"📚 {studied_h:.1f}h / {target:.0f}h  ·  "
                f"✅ {done}/{total} Lernziele{tasks_txt}"
            )
        else:
            meta = QLabel(
                f"📚 {studied_h:.1f}h / {target:.0f}h  ·  "
                f"Keine Lernziele{tasks_txt}"
            )
        meta.setStyleSheet(f"font-size:11px;color:{_tc('#706C86','#6B7280')};")
        lay.addWidget(meta)

        # Click handler
        def _on_click(_, _mid=mid):
            self._selected_mid = _mid
            self.refresh()

        card.mousePressEvent = _on_click
        return card

    # ── right panel ───────────────────────────────────────────────────────────

    def _clear_right(self):
        while self._right_lay.count():
            item = self._right_lay.takeAt(0)
            if item.widget():
                item.widget().hide()       # hide immediately so old widgets don't overlap new ones
                item.widget().deleteLater()

    def _populate_detail(self, mid: int):
        self._clear_right()
        m = self.repo.get_module(mid)
        if not m:
            self._right_lay.addWidget(self._empty_right())
            return

        color = mod_color(mid)

        # ── Module header ─────────────────────────────────────────────────────
        hdr_frame = QFrame()
        hdr_frame.setObjectName("Card")
        hdr_lay = QVBoxLayout(hdr_frame)
        hdr_lay.setContentsMargins(16, 14, 16, 14)
        hdr_lay.setSpacing(6)

        name_row = QHBoxLayout()
        dot = ColorDot(color, 14)
        name_row.addWidget(dot)
        name_lbl = QLabel(m["name"])
        name_lbl.setStyleSheet(
            f"font-size:16px;font-weight:800;color:{_tc('#1A1A2E','#CDD6F4')};"
        )
        name_row.addWidget(name_lbl, 1)

        # + Lernziel button
        add_obj_btn = QPushButton("+ Lernziel")
        add_obj_btn.setStyleSheet(
            f"QPushButton{{background:{_tc('#F0F7FF','#1A2A3A')};color:#4A86E8;"
            f"border:1px solid #4A86E840;border-radius:6px;padding:4px 10px;font-size:11px;}}"
            f"QPushButton:hover{{background:#4A86E820;}}"
        )
        add_obj_btn.setToolTip("Lernziel manuell hinzufügen")
        add_obj_btn.clicked.connect(lambda: self._add_objective_inline(mid))
        name_row.addWidget(add_obj_btn)

        # Reset button
        reset_btn = QPushButton("↺ Reset")
        reset_btn.setStyleSheet(
            f"QPushButton{{background:{_tc('#FFF0F0','#2A1A1A')};color:#F44336;"
            f"border:1px solid #F4433640;border-radius:6px;padding:4px 10px;font-size:11px;}}"
            f"QPushButton:hover{{background:#F4433620;}}"
        )
        reset_btn.setToolTip("Alle Lernziele als unbearbeitet markieren")
        reset_btn.clicked.connect(lambda: self._reset_objectives(mid))
        name_row.addWidget(reset_btn)
        hdr_lay.addLayout(name_row)

        d = days_until(m["exam_date"])
        if d is None:   d_txt, d_col = "Kein Prüfungsdatum", "#9E9E9E"
        elif d < 0:     d_txt, d_col = f"Prüfung war vor {abs(d)} Tagen", "#9E9E9E"
        elif d == 0:    d_txt, d_col = "PRÜFUNG HEUTE!", "#F44336"
        elif d <= 7:    d_txt, d_col = f"Prüfung in {d} Tagen — bald!", "#FF9800"
        else:           d_txt, d_col = f"Prüfung in {d} Tagen  ({m['exam_date']})", "#4A86E8"
        date_lbl = QLabel(f"📅  {d_txt}")
        date_lbl.setStyleSheet(f"font-size:13px;color:{d_col};font-weight:700;")
        hdr_lay.addWidget(date_lbl)

        self._right_lay.addWidget(hdr_frame)

        # ── Lernziele checklist ───────────────────────────────────────────────
        objs = self.repo.list_scraped_data(mid, "objective")
        if not objs:
            no_lbl = QLabel(
                "Keine Lernziele vorhanden.\n"
                "PDF-Import in den Modul-Einstellungen starten."
            )
            no_lbl.setAlignment(Qt.AlignCenter)
            no_lbl.setStyleSheet(f"color:{_tc('#706C86','#6B7280')};font-size:13px;margin-top:24px;")
            self._right_lay.addWidget(no_lbl)
            self._right_lay.addStretch()
            return

        done  = sum(1 for o in objs if int(o["checked"] if "checked" in o.keys() and o["checked"] is not None else 0))
        total = len(objs)

        # Progress summary bar
        summary_frame = QFrame()
        summary_frame.setObjectName("Card")
        sl = QHBoxLayout(summary_frame)
        sl.setContentsMargins(14, 10, 14, 10)
        sl.setSpacing(12)
        self._obj_progress_lbl = QLabel()
        self._obj_progress_lbl.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{_tc('#1A1A2E','#CDD6F4')};"
        )
        sl.addWidget(self._obj_progress_lbl)
        sl.addStretch()
        self._obj_bar = QProgressBar()
        self._obj_bar.setRange(0, 100)
        self._obj_bar.setFixedHeight(8)
        self._obj_bar.setFixedWidth(160)
        self._obj_bar.setTextVisible(False)
        self._obj_bar.setStyleSheet(
            f"QProgressBar{{background:{_tc('#EAEAEA','#2A2A3A')};border-radius:4px;}}"
            f"QProgressBar::chunk{{background:#2CB67D;border-radius:4px;}}"
        )
        sl.addWidget(self._obj_bar)
        self._right_lay.addWidget(summary_frame)
        self._update_obj_progress(done, total)

        # Checklist scroll area
        checklist_w = QWidget()
        checklist_w.setAttribute(Qt.WA_StyledBackground, True)
        checklist_lay = QVBoxLayout(checklist_w)
        checklist_lay.setContentsMargins(0, 0, 0, 0)
        checklist_lay.setSpacing(4)

        section_lbl = QLabel("Lernziele")
        section_lbl.setObjectName("SectionTitle")
        checklist_lay.addWidget(section_lbl)

        for obj in objs:
            obj_id  = obj["id"]
            checked = bool(int(obj["checked"] if "checked" in obj.keys() and obj["checked"] is not None else 0))
            row = self._make_obj_row(obj_id, obj["title"], checked, mid)
            checklist_lay.addWidget(row)

        # ── Aufgaben section ──────────────────────────────────────────────────
        all_tasks = self.repo.list_tasks(module_id=mid)
        t_done_count = sum(1 for t in all_tasks if t["status"] == "Done")

        # Horizontal rule separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(
            f"color:{_tc('#E4E8F0','#2A2A3A')};margin-top:10px;margin-bottom:2px;"
        )
        checklist_lay.addWidget(sep)

        # Check for knowledge weaknesses in this module
        topics = self.repo.list_topics(mid)
        weak_count = sum(1 for tp in topics if int(tp["knowledge_level"]) <= 1)
        has_weak = weak_count > 0

        # Tasks header row
        t_hdr_lay = QHBoxLayout()
        t_hdr_lay.setContentsMargins(0, 4, 0, 0)
        t_title_lbl = QLabel("Aufgaben")
        t_title_lbl.setObjectName("SectionTitle")
        t_hdr_lay.addWidget(t_title_lbl)
        t_hdr_lay.addStretch()
        t_stats_lbl = QLabel(f"☑ {t_done_count} / {len(all_tasks)} erledigt")
        t_stats_lbl.setStyleSheet(f"font-size:11px;color:{_tc('#706C86','#6B7280')};")
        t_hdr_lay.addWidget(t_stats_lbl)
        checklist_lay.addLayout(t_hdr_lay)

        # Knowledge-weakness warning banner
        if has_weak:
            warn_frame = QFrame()
            warn_frame.setStyleSheet(
                "background:#FF980018;border-radius:5px;"
            )
            warn_inner = QHBoxLayout(warn_frame)
            warn_inner.setContentsMargins(8, 5, 8, 5)
            warn_lbl = QLabel(
                f"⚠️  {weak_count} Thema(en) mit Wissenslücken — Aufgaben priorisiert"
            )
            warn_lbl.setStyleSheet(
                "font-size:11px;color:#FF9800;font-weight:600;"
            )
            warn_inner.addWidget(warn_lbl)
            checklist_lay.addWidget(warn_frame)

        if not all_tasks:
            no_t = QLabel("Keine Aufgaben für dieses Modul erstellt.")
            no_t.setStyleSheet(
                f"color:{_tc('#706C86','#6B7280')};font-size:12px;margin:4px 0 8px 0;"
            )
            checklist_lay.addWidget(no_t)
        else:
            PRIO_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
            sorted_tasks = sorted(
                all_tasks,
                key=lambda t: (t["status"] == "Done", PRIO_ORDER.get(t["priority"], 4))
            )
            for t in sorted_tasks:
                checklist_lay.addWidget(self._make_exam_task_row(t, mid))

        checklist_lay.addStretch()
        self._right_lay.addWidget(make_scroll(checklist_w), 1)

    def _add_objective_inline(self, mid: int):
        """Lightweight dialog to manually add a Lernziel to this module."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Lernziel hinzufügen")
        dlg.setMinimumWidth(400)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowModality(Qt.ApplicationModal)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(10)

        title_edit = QLineEdit()
        title_edit.setPlaceholderText("Lernziel-Titel *")
        lay.addWidget(title_edit)

        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText("Beschreibung / Details (optional)")
        notes_edit.setMaximumHeight(80)
        lay.addWidget(notes_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        lay.addWidget(btns)

        def _save():
            title = title_edit.text().strip()
            if not title:
                QMessageBox.warning(dlg, "Fehler", "Titel darf nicht leer sein.")
                return
            # Count existing objectives to set sort_order
            existing = self.repo.list_scraped_data(mid, "objective")
            sort_order = len(existing)
            self.repo.conn.execute(
                "INSERT INTO module_scraped_data"
                "(module_id, data_type, title, body, weight, sort_order) "
                "VALUES (?, 'objective', ?, ?, 0, ?)",
                (mid, title, notes_edit.toPlainText().strip(), sort_order),
            )
            self.repo.conn.commit()
            dlg.accept()
            # Defer so the dialog fully closes before we rebuild widgets
            if self._global_refresh:
                QTimer.singleShot(0, self._global_refresh)
            else:
                QTimer.singleShot(0, self.refresh)

        btns.accepted.connect(_save)
        btns.rejected.connect(dlg.reject)
        dlg.exec()

    def _make_exam_task_row(self, t, mid: int) -> QFrame:
        """Task row for the ExamPage detail panel with exam-date-based priority."""
        is_done = t["status"] == "Done"
        PRIO_COLORS = {
            "Critical": "#E53935", "High": "#F44336",
            "Medium": "#FF9800", "Low": "#4A86E8",
        }

        # Compute priority from module exam date
        mod = self.repo.get_module(mid)
        exam_date_str = mod["exam_date"] if mod else None
        auto_prio = exam_priority(exam_date_str)

        row = QFrame()
        row.setObjectName("Card")
        rly = QHBoxLayout(row)
        rly.setContentsMargins(12, 7, 12, 7)
        rly.setSpacing(10)

        cb = QCheckBox()
        cb.setChecked(is_done)
        cb.setFixedSize(18, 18)
        rly.addWidget(cb)

        title_lbl = QLabel(t["title"])
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(
            f"font-size:12px;"
            f"color:{_tc('#706C86','#6B7280') if is_done else _tc('#1A1A2E','#CDD6F4')};"
            f"{'text-decoration:line-through;' if is_done else ''}"
        )
        rly.addWidget(title_lbl, 1)

        # Auto-priority badge (from exam date)
        pc = PRIO_COLORS.get(auto_prio, "#706C86")
        prio_lbl = QLabel(auto_prio)
        prio_lbl.setStyleSheet(
            f"background:{pc}22;color:{pc};"
            f"border-radius:5px;padding:1px 6px;font-size:10px;font-weight:700;"
        )
        prio_lbl.setToolTip("Priorität automatisch berechnet aus Prüfungsdatum")
        rly.addWidget(prio_lbl)

        if t["due_date"]:
            due_lbl = QLabel(f"📅 {t['due_date']}")
            due_lbl.setStyleSheet(f"font-size:10px;color:{_tc('#706C86','#6B7280')};")
            rly.addWidget(due_lbl)

        def _toggle(state, _tid=t["id"], _mid=mid):
            new_status = "Done" if state else "Open"
            self.repo.update_task(_tid, status=new_status)
            self._selected_mid = _mid
            # Defer — destroying widgets inside stateChanged causes free() crash
            if self._global_refresh:
                QTimer.singleShot(0, self._global_refresh)
            else:
                QTimer.singleShot(0, self.refresh)

        cb.stateChanged.connect(_toggle)
        return row

    def _make_obj_row(self, obj_id: int, title: str, checked: bool, mid: int) -> QFrame:
        row = QFrame()
        row.setObjectName("Card")
        rly = QHBoxLayout(row)
        rly.setContentsMargins(12, 8, 12, 8)
        rly.setSpacing(10)

        cb = QCheckBox()
        cb.setChecked(checked)
        cb.setFixedSize(18, 18)
        rly.addWidget(cb)

        lbl = QLabel(title)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"font-size:12px;color:{_tc('#1A1A2E','#CDD6F4') if not checked else _tc('#706C86','#6B7280')};"
            f"{'text-decoration:line-through;' if checked else ''}"
        )
        rly.addWidget(lbl, 1)

        def _toggle(state, _oid=obj_id, _mid=mid, _lbl=lbl):
            is_checked = bool(state)
            self.repo.set_objective_checked(_oid, is_checked)
            _lbl.setStyleSheet(
                f"font-size:12px;"
                f"color:{_tc('#706C86','#6B7280') if is_checked else _tc('#1A1A2E','#CDD6F4')};"
                f"{'text-decoration:line-through;' if is_checked else ''}"
            )
            # Update progress live
            objs = self.repo.list_scraped_data(_mid, "objective")
            done  = sum(1 for o in objs if int(o["checked"] if "checked" in o.keys() and o["checked"] is not None else 0))
            self._update_obj_progress(done, len(objs))

        cb.stateChanged.connect(_toggle)
        return row

    def _update_obj_progress(self, done: int, total: int):
        pct = int(done / total * 100) if total else 0
        self._obj_progress_lbl.setText(f"✅ {done} / {total} Lernziele abgehakt  ({pct}%)")
        self._obj_bar.setValue(pct)

    def _reset_objectives(self, mid: int):
        if QMessageBox.question(
            self, "Reset", "Alle Lernziele als unbearbeitet markieren?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.repo.reset_objectives_checked(mid)
            self._selected_mid = mid
            if self._global_refresh:
                self._global_refresh()
            else:
                self.refresh()


