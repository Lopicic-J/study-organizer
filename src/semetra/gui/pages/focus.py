"""Focus mode page — integrated module learning."""
from __future__ import annotations

import time as _time
from datetime import date, datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QDialog, QDialogButtonBox, QFormLayout, QComboBox as _QCBBase,
    QTableWidget, QTableWidgetItem, QCheckBox, QTabWidget,
    QProgressBar, QHeaderView, QAbstractItemView, QMessageBox, QFrame,
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import QComboBox, make_scroll
from semetra.gui.i18n import tr, tr_know
from semetra.gui.constants import KNOWLEDGE_COLORS
from semetra.gui.helpers import mod_color, days_until, exam_priority


class FocusPage(QWidget):
    """v3 Fokus-Modus — alles für ein Modul in einem Screen mit Tabs.
    Ersetzt Wissen-, Prüfungs- und Timer-Seite komplett."""

    PRIO_COLORS = {"Critical": "#F44336", "High": "#FF9800",
                   "Medium": "#FFC107", "Low": "#4CAF50"}

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._global_refresh: Optional[callable] = None
        self._timer_running = False
        self._timer_remaining = 25 * 60
        self._timer_total = 25 * 60
        self._timer_start_ts: Optional[int] = None
        self._qtimer = QTimer(self)
        self._qtimer.setInterval(1000)
        self._qtimer.timeout.connect(self._timer_tick)
        self._build()

    def set_global_refresh(self, cb):
        self._global_refresh = cb

    # ══════════════════════════ LAYOUT ══════════════════════════════════════

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 12)
        outer.setSpacing(10)

        # ── Top bar: title + module picker ──────────────────────────────────
        top = QHBoxLayout()
        title_lbl = QLabel("🎯  Fokus-Modus")
        title_lbl.setObjectName("PageTitle")
        top.addWidget(title_lbl)
        top.addStretch()
        top.addWidget(QLabel("Modul:"))
        self._mod_cb = QComboBox()
        self._mod_cb.setMinimumWidth(260)
        self._mod_cb.currentIndexChanged.connect(self._on_module_changed)
        top.addWidget(self._mod_cb)
        outer.addLayout(top)

        # ── Exam banner + progress badges + timer (always visible) ──────────
        info_frame = QFrame()
        info_frame.setObjectName("Card")
        info_lay = QVBoxLayout(info_frame)
        info_lay.setContentsMargins(16, 10, 16, 10)
        info_lay.setSpacing(8)

        # Row 1: module name + countdown
        banner_row = QHBoxLayout()
        self._exam_name_lbl = QLabel("← Modul wählen")
        self._exam_name_lbl.setStyleSheet("font-size:15px;font-weight:bold;")
        banner_row.addWidget(self._exam_name_lbl)
        banner_row.addStretch()
        self._exam_days_lbl = QLabel()
        self._exam_days_lbl.setStyleSheet("font-size:22px;font-weight:bold;")
        banner_row.addWidget(self._exam_days_lbl)
        self._exam_date_lbl = QLabel()
        self._exam_date_lbl.setStyleSheet("color:#706C86;font-size:12px;margin-left:6px;")
        banner_row.addWidget(self._exam_date_lbl)
        info_lay.addLayout(banner_row)

        # Row 2: progress badges + timer controls
        mid_row = QHBoxLayout()
        mid_row.setSpacing(8)
        self._stat_lz  = self._make_badge("0/0 Lernziele", "#4A86E8")
        self._stat_auf = self._make_badge("0/0 Aufgaben",  "#2CB67D")
        self._stat_wis = self._make_badge("Ø Wissen —",    "#9B59B6")
        for b in [self._stat_lz, self._stat_auf, self._stat_wis]:
            mid_row.addWidget(b)
        mid_row.addStretch()
        # Timer inline
        for label, mins in [("25′", 25), ("50′", 50), ("5′ Pause", 5)]:
            btn = QPushButton(label)
            btn.setObjectName("SecondaryBtn")
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda c, m=mins: self._timer_set(m))
            mid_row.addWidget(btn)
        self._timer_lbl = QLabel("25:00")
        self._timer_lbl.setStyleSheet(
            "font-size:18px;font-weight:bold;color:#4A86E8;min-width:62px;")
        self._timer_lbl.setAlignment(Qt.AlignCenter)
        mid_row.addWidget(self._timer_lbl)
        self._timer_btn = QPushButton("▶")
        self._timer_btn.setObjectName("PrimaryBtn")
        self._timer_btn.setFixedSize(36, 28)
        self._timer_btn.clicked.connect(self._timer_toggle)
        mid_row.addWidget(self._timer_btn)
        self._timer_note = QLineEdit()
        self._timer_note.setPlaceholderText("Notiz zur Session…")
        self._timer_note.setFixedWidth(180)
        mid_row.addWidget(self._timer_note)
        info_lay.addLayout(mid_row)
        outer.addWidget(info_frame)

        # ── Tabs: Lernziele | Aufgaben | Wissen ─────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        outer.addWidget(self._tabs, 1)

        self._tabs.addTab(self._build_lz_tab(),  "📖  Lernziele")
        self._tabs.addTab(self._build_auf_tab(), "✅  Aufgaben")
        self._tabs.addTab(self._build_wis_tab(), "🧠  Wissen")

    @staticmethod
    def _make_badge(text: str, color: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"background:{color};color:white;border-radius:10px;"
            f"padding:3px 10px;font-size:12px;font-weight:bold;")
        return lbl

    # ── Tab builders ─────────────────────────────────────────────────────────

    def _build_lz_tab(self) -> QWidget:
        w = QWidget()
        w.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(6)
        # toolbar
        tb = QHBoxLayout()
        add_btn = QPushButton("+ Lernziel")
        add_btn.setObjectName("SecondaryBtn")
        add_btn.clicked.connect(self._add_lernziel)
        tb.addWidget(add_btn)
        reset_btn = QPushButton("↺ Zurücksetzen")
        reset_btn.setObjectName("SecondaryBtn")
        reset_btn.clicked.connect(self._reset_lernziele)
        tb.addWidget(reset_btn)
        tb.addStretch()
        self._lz_prog_lbl = QLabel()
        self._lz_prog_lbl.setStyleSheet("color:#706C86;font-size:12px;")
        tb.addWidget(self._lz_prog_lbl)
        lay.addLayout(tb)
        # progress bar
        self._lz_bar = QProgressBar()
        self._lz_bar.setRange(0, 100)
        self._lz_bar.setFixedHeight(6)
        self._lz_bar.setTextVisible(False)
        self._lz_bar.setStyleSheet(
            "QProgressBar{border-radius:3px;background:#E0E0E0;}"
            "QProgressBar::chunk{background:#4A86E8;border-radius:3px;}")
        lay.addWidget(self._lz_bar)
        # scroll list
        self._lz_container = QWidget()
        self._lz_lay = QVBoxLayout(self._lz_container)
        self._lz_lay.setSpacing(2)
        self._lz_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(make_scroll(self._lz_container), 1)
        return w

    def _build_auf_tab(self) -> QWidget:
        w = QWidget()
        w.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(6)
        # toolbar
        tb = QHBoxLayout()
        add_btn = QPushButton("+ Aufgabe")
        add_btn.setObjectName("SecondaryBtn")
        add_btn.clicked.connect(self._add_aufgabe)
        tb.addWidget(add_btn)
        tb.addStretch()
        tb.addWidget(QLabel("Filter:"))
        self._auf_filter = QComboBox()
        self._auf_filter.addItems(["Offen", "Alle", "Erledigt"])
        self._auf_filter.currentIndexChanged.connect(self._reload_aufgaben)
        tb.addWidget(self._auf_filter)
        lay.addLayout(tb)
        # scroll list
        self._auf_container = QWidget()
        self._auf_lay = QVBoxLayout(self._auf_container)
        self._auf_lay.setSpacing(2)
        self._auf_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(make_scroll(self._auf_container), 1)
        return w

    def _build_wis_tab(self) -> QWidget:
        w = QWidget()
        w.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(6)
        # toolbar
        tb = QHBoxLayout()
        add_btn = QPushButton("+ Thema")
        add_btn.setObjectName("SecondaryBtn")
        add_btn.clicked.connect(self._add_thema)
        tb.addWidget(add_btn)
        self._wis_edit_btn = QPushButton("Bearbeiten")
        self._wis_edit_btn.setObjectName("SecondaryBtn")
        self._wis_edit_btn.clicked.connect(self._edit_thema)
        tb.addWidget(self._wis_edit_btn)
        self._wis_del_btn = QPushButton("Löschen")
        self._wis_del_btn.setObjectName("DangerBtn")
        self._wis_del_btn.clicked.connect(self._delete_thema)
        tb.addWidget(self._wis_del_btn)
        tb.addStretch()
        self._wis_summary_lbl = QLabel()
        self._wis_summary_lbl.setStyleSheet("color:#706C86;font-size:12px;")
        tb.addWidget(self._wis_summary_lbl)
        lay.addLayout(tb)
        # table
        self._wis_table = QTableWidget(0, 4)
        self._wis_table.setHorizontalHeaderLabels(["Thema", "Kenntnisstand", "Notizen", "ID"])
        self._wis_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._wis_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._wis_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._wis_table.verticalHeader().setVisible(False)
        self._wis_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._wis_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._wis_table.setColumnHidden(3, True)
        self._wis_table.doubleClicked.connect(self._edit_thema)
        lay.addWidget(self._wis_table, 1)
        return w

    # ══════════════════════════ REFRESH / POPULATE ══════════════════════════

    def refresh(self):
        cur = self._mod_cb.currentData()
        self._mod_cb.blockSignals(True)
        self._mod_cb.clear()
        self._mod_cb.addItem("— Modul wählen —", None)
        mods = self.repo.list_modules("active") or self.repo.list_modules("all")
        for m in mods:
            self._mod_cb.addItem(m["name"], m["id"])
        if cur:
            for i in range(self._mod_cb.count()):
                if self._mod_cb.itemData(i) == cur:
                    self._mod_cb.setCurrentIndex(i)
                    break
        self._mod_cb.blockSignals(False)
        self._populate()

    def _on_module_changed(self):
        self._populate()

    def _populate(self):
        mid = self._mod_cb.currentData()
        if not mid:
            self._exam_name_lbl.setText("← Modul wählen")
            self._exam_days_lbl.setText("")
            self._exam_date_lbl.setText("")
            self._stat_lz.setText("0/0 Lernziele")
            self._stat_auf.setText("0/0 Aufgaben")
            self._stat_wis.setText("Ø Wissen —")
            self._clear_lay(self._lz_lay)
            self._clear_lay(self._auf_lay)
            self._wis_table.setRowCount(0)
            return

        mod = self.repo.get_module(mid)
        if not mod:
            return

        # ── banner ──────────────────────────────────────────────────────────
        color = mod_color(mid)
        self._exam_name_lbl.setText(mod["name"])
        self._exam_name_lbl.setStyleSheet(
            f"font-size:15px;font-weight:bold;color:{color};")
        d = days_until(mod["exam_date"])
        exam_date_str = (mod["exam_date"] or "")
        if not exam_date_str or d is None:
            self._exam_days_lbl.setText("Kein Prüfungsdatum")
            self._exam_days_lbl.setStyleSheet("font-size:15px;color:#706C86;")
        elif d < 0:
            self._exam_days_lbl.setText("Prüfung vorbei")
            self._exam_days_lbl.setStyleSheet("font-size:15px;color:#9E9E9E;")
        elif d == 0:
            self._exam_days_lbl.setText("⚠ HEUTE!")
            self._exam_days_lbl.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#F44336;")
        elif d <= 5:
            self._exam_days_lbl.setText(f"🔴 {d} Tage")
            self._exam_days_lbl.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#F44336;")
        elif d <= 10:
            self._exam_days_lbl.setText(f"🟠 {d} Tage")
            self._exam_days_lbl.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#FF9800;")
        elif d <= 15:
            self._exam_days_lbl.setText(f"🟡 {d} Tage")
            self._exam_days_lbl.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#FFC107;")
        else:
            self._exam_days_lbl.setText(f"🟢 {d} Tage")
            self._exam_days_lbl.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#4CAF50;")
        self._exam_date_lbl.setText(exam_date_str)

        # ── badges ──────────────────────────────────────────────────────────
        objs  = self.repo.list_scraped_data(mid, "objective")
        tasks = self.repo.list_tasks(module_id=mid)
        topics = self.repo.list_topics(mid)
        lz_done = sum(1 for o in objs if int(o["checked"] or 0))
        t_done  = sum(1 for t in tasks if t["status"] == "Done")
        avg_k   = (sum(int(t["knowledge_level"]) for t in topics) / len(topics)
                   if topics else 0)
        self._stat_lz.setText(f"{lz_done}/{len(objs)} Lernziele ✓")
        self._stat_auf.setText(f"{t_done}/{len(tasks)} Aufgaben ✓")
        self._stat_wis.setText(f"Ø Wissen {avg_k:.1f}/4")

        # ── tabs ────────────────────────────────────────────────────────────
        self._populate_lernziele(mid, objs)
        self._reload_aufgaben()
        self._populate_wissen(mid, topics)

    # ── Tab: Lernziele ───────────────────────────────────────────────────────

    def _populate_lernziele(self, mid: int, objectives):
        self._clear_lay(self._lz_lay)
        total = len(objectives)
        done  = sum(1 for o in objectives if int(o["checked"] or 0))
        self._lz_prog_lbl.setText(f"{done} / {total} erledigt")
        self._lz_bar.setValue(int(done / total * 100) if total else 0)
        if not objectives:
            lbl = QLabel("Keine Lernziele — importiere Moduldaten oder füge manuell hinzu.")
            lbl.setStyleSheet("color:#706C86;font-size:12px;font-style:italic;")
            self._lz_lay.addWidget(lbl)
            self._lz_lay.addStretch()
            return
        for obj in objectives:
            row_w = QWidget()
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(4, 2, 4, 2)
            row_h.setSpacing(8)
            cb = QCheckBox()
            cb.setChecked(bool(int(obj["checked"] or 0)))
            oid = int(obj["id"])
            def _tog(state, o=oid):
                self.repo.update_scraped_data(o, checked=1 if state else 0)
                QTimer.singleShot(0, self._populate)
                if self._global_refresh:
                    QTimer.singleShot(10, self._global_refresh)
            cb.stateChanged.connect(_tog)
            row_h.addWidget(cb)
            checked = bool(int(obj["checked"] or 0))
            lbl = QLabel(obj["title"])
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                "color:#706C86;text-decoration:line-through;font-size:12px;"
                if checked else "font-size:12px;")
            row_h.addWidget(lbl, 1)
            self._lz_lay.addWidget(row_w)
        self._lz_lay.addStretch()

    def _reset_lernziele(self):
        mid = self._mod_cb.currentData()
        if not mid:
            return
        if QMessageBox.question(
                self, "Lernziele zurücksetzen",
                "Alle Lernziele als unerledigt markieren?",
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.reset_objectives_checked(mid)
            QTimer.singleShot(0, self._populate)
            if self._global_refresh:
                QTimer.singleShot(10, self._global_refresh)

    # ── Tab: Aufgaben ────────────────────────────────────────────────────────

    def _reload_aufgaben(self):
        mid = self._mod_cb.currentData()
        if not mid:
            self._clear_lay(self._auf_lay)
            return
        tasks = self.repo.list_tasks(module_id=mid)
        filt = self._auf_filter.currentText()
        if filt == "Offen":
            tasks = [t for t in tasks if t["status"] != "Done"]
        elif filt == "Erledigt":
            tasks = [t for t in tasks if t["status"] == "Done"]
        prio_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        tasks = sorted(tasks, key=lambda t: (
            t["status"] == "Done", prio_order.get(t["priority"] or "Low", 4)))
        self._clear_lay(self._auf_lay)
        if not tasks:
            lbl = QLabel("Keine Aufgaben vorhanden.")
            lbl.setStyleSheet("color:#706C86;font-size:12px;font-style:italic;")
            self._auf_lay.addWidget(lbl)
            self._auf_lay.addStretch()
            return
        for t in tasks:
            row_w = QWidget()
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(4, 2, 4, 2)
            row_h.setSpacing(8)
            cb = QCheckBox()
            cb.setChecked(t["status"] == "Done")
            tid = int(t["id"])
            def _tog_t(state, i=tid):
                self.repo.update_task(i, status="Done" if state else "Open")
                QTimer.singleShot(0, self._reload_aufgaben)
                if self._global_refresh:
                    QTimer.singleShot(10, self._global_refresh)
            cb.stateChanged.connect(_tog_t)
            row_h.addWidget(cb)
            prio_col = self.PRIO_COLORS.get(t["priority"] or "Low", "#999")
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{prio_col};font-size:10px;")
            row_h.addWidget(dot)
            lbl = QLabel(t["title"])
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                "color:#706C86;text-decoration:line-through;font-size:12px;"
                if t["status"] == "Done" else "font-size:12px;")
            row_h.addWidget(lbl, 1)
            prio_lbl = QLabel(t["priority"] or "")
            prio_lbl.setStyleSheet(
                f"color:{prio_col};font-size:10px;font-weight:bold;")
            row_h.addWidget(prio_lbl)
            self._auf_lay.addWidget(row_w)
        self._auf_lay.addStretch()

    # ── Tab: Wissen ──────────────────────────────────────────────────────────

    def _populate_wissen(self, mid: int, topics):
        self._wis_table.setRowCount(len(topics))
        review_count = 0
        for r, t in enumerate(topics):
            level = int(t["knowledge_level"])
            lr = (t["last_reviewed"] if "last_reviewed" in t.keys() else "") or ""
            needs_review = False
            if lr:
                try:
                    days_since = (date.today() -
                                  datetime.fromisoformat(lr).date()).days
                    if days_since >= 3 and level < 3:
                        needs_review = True
                        review_count += 1
                except Exception:
                    pass
            title_txt = ("⚠ " + t["title"]) if needs_review else t["title"]
            ti = QTableWidgetItem(title_txt)
            if needs_review:
                ti.setForeground(QColor("#FF9800"))
                ti.setToolTip(f"Review empfohlen — zuletzt: {lr[:10]}")
            self._wis_table.setItem(r, 0, ti)
            know_col = KNOWLEDGE_COLORS.get(level, "#333")
            ki = QTableWidgetItem(tr_know(level))
            ki.setForeground(QColor(know_col))
            self._wis_table.setItem(r, 1, ki)
            self._wis_table.setItem(r, 2, QTableWidgetItem(t["notes"] or ""))
            self._wis_table.setItem(r, 3, QTableWidgetItem(str(t["id"])))
        review_txt = (f"  ⚠ {review_count} Review fällig"
                      if review_count else "")
        self._wis_summary_lbl.setText(
            f"{len(topics)} Themen{review_txt}")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _clear_lay(self, lay: QVBoxLayout):
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def _require_module(self) -> Optional[int]:
        mid = self._mod_cb.currentData()
        if not mid:
            QMessageBox.warning(self, "Kein Modul",
                                "Bitte zuerst ein Modul auswählen.")
        return mid

    # ── Add / Edit / Delete actions ───────────────────────────────────────

    def _add_lernziel(self):
        mid = self._require_module()
        if not mid:
            return
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowTitle("Lernziel hinzufügen")
        dlg.setMinimumWidth(340)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Titel:"))
        edit = QLineEdit()
        lay.addWidget(edit)
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            t = edit.text().strip()
            if t:
                self.repo.add_scraped_data(mid, "objective", t)
                QTimer.singleShot(0, self._populate)
                if self._global_refresh:
                    QTimer.singleShot(10, self._global_refresh)

    def _add_aufgabe(self):
        mid = self._require_module()
        if not mid:
            return
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowTitle("Aufgabe hinzufügen")
        dlg.setMinimumWidth(340)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        t_edit = QLineEdit()
        prio_cb = _QCBBase()
        prio_cb.addItems(["Low", "Medium", "High", "Critical"])
        mod = self.repo.get_module(mid)
        prio_cb.setCurrentText(
            exam_priority(mod["exam_date"] if mod else None))
        form.addRow("Titel *:", t_edit)
        form.addRow("Priorität:", prio_cb)
        lay.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            t = t_edit.text().strip()
            if t:
                self.repo.add_task(mid, t,
                                   priority=prio_cb.currentText(),
                                   status="Open")
                QTimer.singleShot(0, self._populate)
                if self._global_refresh:
                    QTimer.singleShot(10, self._global_refresh)

    def _add_thema(self):
        mid = self._require_module()
        if not mid:
            return
        from semetra.gui.dialogs.topic_dialog import TopicDialog
        if TopicDialog(self.repo, mid, parent=self).exec() == QDialog.Accepted:
            QTimer.singleShot(0, self._populate)
            if self._global_refresh:
                QTimer.singleShot(10, self._global_refresh)

    def _edit_thema(self):
        mid = self._require_module()
        if not mid:
            return
        row = self._wis_table.currentRow()
        if row < 0:
            return
        tid = int(self._wis_table.item(row, 3).text())
        from semetra.gui.dialogs.topic_dialog import TopicDialog
        if TopicDialog(self.repo, mid, topic_id=tid,
                       parent=self).exec() == QDialog.Accepted:
            QTimer.singleShot(0, self._populate)
            if self._global_refresh:
                QTimer.singleShot(10, self._global_refresh)

    def _delete_thema(self):
        row = self._wis_table.currentRow()
        if row < 0:
            return
        tid = int(self._wis_table.item(row, 3).text())
        title = self._wis_table.item(row, 0).text()
        if QMessageBox.question(
                self, "Thema löschen",
                f'"{title}" wirklich löschen?',
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_topic(tid)
            QTimer.singleShot(0, self._populate)
            if self._global_refresh:
                QTimer.singleShot(10, self._global_refresh)

    # ── Timer ────────────────────────────────────────────────────────────────

    def _timer_set(self, mins: int):
        if self._timer_running:
            return
        self._timer_total = mins * 60
        self._timer_remaining = mins * 60
        self._timer_update_lbl()

    def _timer_toggle(self):
        if self._timer_running:
            self._timer_running = False
            self._qtimer.stop()
            self._timer_btn.setText("▶")
        else:
            self._timer_running = True
            if not self._timer_start_ts:
                self._timer_start_ts = int(_time.time())
            self._qtimer.start()
            self._timer_btn.setText("⏹")

    def _timer_tick(self):
        if self._timer_remaining > 0:
            self._timer_remaining -= 1
            self._timer_update_lbl()
        else:
            self._qtimer.stop()
            self._timer_running = False
            self._timer_btn.setText("▶")
            self._timer_done()

    def _timer_update_lbl(self):
        m, s = divmod(self._timer_remaining, 60)
        self._timer_lbl.setText(f"{m:02d}:{s:02d}")

    def _timer_done(self):
        mid = self._mod_cb.currentData()
        if mid and self._timer_start_ts:
            end_ts = int(_time.time())
            note = self._timer_note.text().strip()
            self.repo.add_time_log(mid, self._timer_start_ts, end_ts,
                                   self._timer_total, "pomodoro", note)
            self._timer_note.clear()
        self._timer_start_ts = None
        self._timer_remaining = self._timer_total
        self._timer_update_lbl()
        from semetra.gui.dialogs.lern_rueckblick import LernRueckblickDialog
        LernRueckblickDialog(self.repo, mid, parent=self).exec()
        if self._global_refresh:
            QTimer.singleShot(0, self._global_refresh)
