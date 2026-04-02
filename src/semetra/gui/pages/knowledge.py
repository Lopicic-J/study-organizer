"""Knowledge/Spaced Repetition page."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QDialog, QDialogButtonBox, QMessageBox, QSizePolicy,
    QComboBox as _QCBBase, QCheckBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import QComboBox, StatCard, make_scroll
from semetra.gui.i18n import tr, tr_know
from semetra.gui.constants import KNOWLEDGE_COLORS, KNOWLEDGE_LABELS
from semetra.gui.helpers import mod_color, _active_sem_filter, _filter_mods_by_sem, exam_priority
from semetra.gui.colors import _tc



class KnowledgePage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._selected_mid: Optional[int] = None
        self._global_refresh: Optional[callable] = None
        self._build()

    def set_global_refresh(self, cb):
        self._global_refresh = cb

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel(tr("page.knowledge"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()

        # Module filter
        self.mod_cb = QComboBox()
        self.mod_cb.setMinimumWidth(200)
        self.mod_cb.currentIndexChanged.connect(self._load_topics)
        hdr.addWidget(QLabel("Modul:"))
        hdr.addWidget(self.mod_cb)

        # Task filter (populated once a module is selected)
        self.task_filter_cb = QComboBox()
        self.task_filter_cb.setMinimumWidth(170)
        self.task_filter_cb.addItem("Alle Themen", None)
        self.task_filter_cb.currentIndexChanged.connect(self._apply_topic_filter)
        hdr.addWidget(QLabel("Aufgabe:"))
        hdr.addWidget(self.task_filter_cb)

        add_task_btn = QPushButton("+ Aufgabe")
        add_task_btn.setObjectName("SecondaryBtn")
        add_task_btn.clicked.connect(self._add_task_inline)
        hdr.addWidget(add_task_btn)

        add_btn = QPushButton("+ Thema")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_topic)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        # ── SR due-topics banner ─────────────────────────────────────────────
        self._sr_banner = QFrame()
        self._sr_banner.setObjectName("SRBanner")
        self._sr_banner.setStyleSheet(
            f"QFrame#SRBanner{{background:{_tc('#FFF7E6','#2A2010')};"
            f"border-left:3px solid #FF8C42;border-radius:6px;}}"
        )
        sr_ban_lay = QHBoxLayout(self._sr_banner)
        sr_ban_lay.setContentsMargins(14, 8, 14, 8)
        sr_ban_lay.setSpacing(12)
        self._sr_banner_lbl = QLabel()
        self._sr_banner_lbl.setStyleSheet(f"color:{_tc('#7A4A00','#FFAA55')};font-size:12px;font-weight:600;")
        sr_ban_lay.addWidget(self._sr_banner_lbl, 1)
        self._sr_review_btn = QPushButton("📚  Review starten")
        self._sr_review_btn.setFixedHeight(28)
        self._sr_review_btn.setCursor(Qt.PointingHandCursor)
        self._sr_review_btn.setStyleSheet(
            f"QPushButton{{background:{_tc('#FF8C4222','#FF8C4233')};color:{_tc('#7A4A00','#FFAA55')};"
            f"border:1px solid #FF8C4299;border-radius:6px;padding:0 12px;font-weight:600;font-size:11px;}}"
            f"QPushButton:hover{{background:#FF8C4244;}}"
        )
        self._sr_review_btn.clicked.connect(self._start_sr_review)
        sr_ban_lay.addWidget(self._sr_review_btn)
        self._sr_banner.hide()
        lay.addWidget(self._sr_banner)

        # Knowledge-level summary bar
        self.summary_frame = QFrame()
        self.summary_frame.setObjectName("Card")
        sf_lay = QHBoxLayout(self.summary_frame)
        sf_lay.setContentsMargins(16, 10, 16, 10)
        self.summary_labels: Dict[int, QLabel] = {}
        for k in range(5):
            col = QVBoxLayout()
            col.setSpacing(3)
            bar = QLabel()
            bar.setFixedHeight(8)
            bar.setStyleSheet(f"background:{KNOWLEDGE_COLORS[k]};border-radius:4px;")
            col.addWidget(bar)
            lbl = QLabel(f"{KNOWLEDGE_LABELS[k]}\n0")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 11px; color: #706C86;")
            col.addWidget(lbl)
            self.summary_labels[k] = lbl
            sf_lay.addLayout(col)
        lay.addWidget(self.summary_frame)

        # ── Topics table ─────────────────────────────────────────────────────
        topics_hdr = QHBoxLayout()
        topics_title = QLabel("Wissensthemen")
        topics_title.setObjectName("SectionTitle")
        topics_hdr.addWidget(topics_title)
        topics_hdr.addStretch()
        del_btn = QPushButton("Thema löschen")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_topic)
        topics_hdr.addWidget(del_btn)
        lay.addLayout(topics_hdr)

        self.topic_table = QTableWidget(0, 6)
        self.topic_table.setHorizontalHeaderLabels(
            ["Thema", "Kenntnisstand", "Notizen", "Aufgabe", "Nächste Wdh.", "ID"]
        )
        self.topic_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.topic_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.topic_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.topic_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.topic_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.topic_table.setColumnHidden(5, True)  # hidden ID column
        self.topic_table.verticalHeader().setVisible(False)
        self.topic_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.topic_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.topic_table.doubleClicked.connect(self._edit_topic)
        lay.addWidget(self.topic_table, 3)

        # ── Tasks section (inline, directly below topics — no splitter) ───────
        tasks_card = QFrame()
        tasks_card.setObjectName("Card")
        tasks_card_lay = QVBoxLayout(tasks_card)
        tasks_card_lay.setContentsMargins(12, 10, 12, 10)
        tasks_card_lay.setSpacing(6)

        self._tasks_title = QLabel("Aufgaben")
        self._tasks_title.setObjectName("SectionTitle")
        tasks_card_lay.addWidget(self._tasks_title)

        self._task_list_w = QWidget()
        self._task_list_w.setAttribute(Qt.WA_StyledBackground, True)
        self._task_list_lay = QVBoxLayout(self._task_list_w)
        self._task_list_lay.setContentsMargins(0, 0, 0, 0)
        self._task_list_lay.setSpacing(4)
        tasks_card_lay.addWidget(make_scroll(self._task_list_w), 1)
        lay.addWidget(tasks_card, 2)

    def refresh(self):
        # Sync Lernziele → tasks for ALL modules (silent, deduped by title)
        for m in self.repo.list_modules("all"):
            self._sync_objectives_as_tasks(m["id"])

        sem_f = _active_sem_filter(self.repo)
        mods_filtered = _filter_mods_by_sem(self.repo.list_modules("all"), sem_f)
        mod_ids_allowed = {m["id"] for m in mods_filtered}

        cur_id = self.mod_cb.currentData()
        self.mod_cb.blockSignals(True)
        self.mod_cb.clear()
        for m in mods_filtered:
            self.mod_cb.addItem(m["name"], m["id"])
        if cur_id and cur_id in mod_ids_allowed:
            for i in range(self.mod_cb.count()):
                if self.mod_cb.itemData(i) == cur_id:
                    self.mod_cb.setCurrentIndex(i)
                    break
        self.mod_cb.blockSignals(False)
        self._load_topics()

    def _load_topics(self):
        mid = self.mod_cb.currentData()
        self._selected_mid = mid
        if not mid:
            self.topic_table.setRowCount(0)
            self._load_tasks(None)
            # Reset task filter
            self.task_filter_cb.blockSignals(True)
            self.task_filter_cb.clear()
            self.task_filter_cb.addItem("Alle Themen", None)
            self.task_filter_cb.blockSignals(False)
            return

        # Auto-sync Lernziele → tasks (silently, deduped by title)
        new_from_obj = self._sync_objectives_as_tasks(mid)

        # Repopulate task-filter combobox (preserve previous selection if possible)
        prev_tid = self.task_filter_cb.currentData()
        self.task_filter_cb.blockSignals(True)
        self.task_filter_cb.clear()
        self.task_filter_cb.addItem("Alle Themen", None)
        for t in self.repo.list_tasks(module_id=mid):
            self.task_filter_cb.addItem(t["title"], t["id"])
        # Restore previous selection
        restored = False
        if prev_tid is not None:
            idx = self.task_filter_cb.findData(prev_tid)
            if idx >= 0:
                self.task_filter_cb.setCurrentIndex(idx)
                restored = True
        if not restored:
            self.task_filter_cb.setCurrentIndex(0)
        self.task_filter_cb.blockSignals(False)

        self._apply_topic_filter()

    def _apply_topic_filter(self):
        """Filter the topic table by the currently selected task (or show all)."""
        mid = self._selected_mid
        if not mid:
            return

        all_topics = self.repo.list_topics(mid)
        filter_tid = self.task_filter_cb.currentData()   # None = show all

        if filter_tid is None:
            topics = all_topics
        else:
            topics = [
                t for t in all_topics
                if "task_id" in t.keys()
                and t["task_id"] is not None
                and int(t["task_id"]) == filter_tid
            ]

        # Update knowledge summary based on the filtered subset
        from collections import Counter
        counts = Counter(int(t["knowledge_level"]) for t in topics)
        for k in range(5):
            self.summary_labels[k].setText(f"{tr_know(k)}\n{counts.get(k, 0)}")

        # Populate table
        today = date.today()
        self.topic_table.setRowCount(len(topics))
        for r, t in enumerate(topics):
            level = int(t["knowledge_level"])
            # ── Col 0: Thema (with SM-2 overdue indicator) ──────────────
            nr_str = (t["sr_next_review"] if "sr_next_review" in t.keys() else "") or ""
            is_overdue = False
            if nr_str:
                try:
                    nr_date = date.fromisoformat(nr_str[:10])
                    is_overdue = nr_date <= today
                except Exception:
                    pass
            title_text = ("⚠ " + t["title"]) if is_overdue else t["title"]
            title_item = QTableWidgetItem(title_text)
            if is_overdue:
                title_item.setForeground(QColor("#FF9800"))
                title_item.setToolTip(f"SR-Review fällig! Nächste Wdh. war: {nr_str[:10]}")
            self.topic_table.setItem(r, 0, title_item)
            # ── Col 1: Kenntnisstand ─────────────────────────────────────
            lvl_item = QTableWidgetItem(tr_know(level))
            lvl_item.setForeground(QColor(KNOWLEDGE_COLORS.get(level, "#333")))
            self.topic_table.setItem(r, 1, lvl_item)
            self.topic_table.setItem(r, 2, QTableWidgetItem(t["notes"] or ""))
            # ── Col 3: linked task name ──────────────────────────────────
            task_name = (t["task_title"] if "task_title" in t.keys() and t["task_title"] else "")
            task_item = QTableWidgetItem(f"☑ {task_name}" if task_name else "")
            task_item.setForeground(QColor(_tc("#4A86E8", "#7BAAF7")))
            self.topic_table.setItem(r, 3, task_item)
            # ── Col 4: SR next review ────────────────────────────────────
            if not nr_str:
                sr_text  = "—"
                sr_color = _tc("#BBBBBB", "#555577")
                sr_tip   = "Noch kein Review gestartet"
            else:
                try:
                    nr_date = date.fromisoformat(nr_str[:10])
                    diff = (nr_date - today).days
                    if diff < 0:
                        sr_text  = f"Überfällig ({abs(diff)}d)"
                        sr_color = "#E05050"
                        sr_tip   = f"Review überfällig seit {abs(diff)} Tag(en)"
                    elif diff == 0:
                        sr_text  = "Heute"
                        sr_color = "#FF8C42"
                        sr_tip   = "Review heute fällig"
                    elif diff == 1:
                        sr_text  = "Morgen"
                        sr_color = "#F5C518"
                        sr_tip   = "Review morgen fällig"
                    else:
                        sr_text  = f"in {diff}d"
                        sr_color = _tc("#2CB67D", "#2CB67D")
                        sr_tip   = f"Nächste Wiederholung in {diff} Tagen ({nr_str[:10]})"
                except Exception:
                    sr_text  = nr_str[:10]
                    sr_color = "#706C86"
                    sr_tip   = ""
            sr_item = QTableWidgetItem(sr_text)
            sr_item.setForeground(QColor(sr_color))
            sr_item.setToolTip(sr_tip)
            self.topic_table.setItem(r, 4, sr_item)
            # ── Col 5: hidden ID ─────────────────────────────────────────
            self.topic_table.setItem(r, 5, QTableWidgetItem(str(t["id"])))

        # ── Update SR banner ─────────────────────────────────────────────
        self._update_sr_banner(mid)
        self._load_tasks(mid)

    # ── SM-2 helpers ────────────────────────────────────────────────────────

    def _update_sr_banner(self, mid: Optional[int] = None):
        """Show/hide the SR banner based on how many topics are due."""
        due_topics = self.repo.sm2_due_topics(module_id=mid)
        if due_topics:
            n = len(due_topics)
            self._sr_banner_lbl.setText(
                f"🔁  {n} Topic{'s' if n > 1 else ''} zur Wiederholung fällig"
                + (f"  (dieses Modul)" if mid else "")
            )
            self._sr_banner.show()
        else:
            self._sr_banner.hide()

    def _start_sr_review(self):
        """Launch the SR review dialog for due topics in the current module."""
        from semetra.gui.dialogs.sr_review import SRReviewDialog
        mid = self._selected_mid
        due_topics = self.repo.sm2_due_topics(module_id=mid)
        if not due_topics:
            return
        dlg = SRReviewDialog(self.repo, due_topics, parent=self)
        dlg.exec()
        # Refresh after review
        n = dlg.reviewed_count()
        self._load_topics()
        if n > 0 and self._global_refresh:
            self._global_refresh()

    # ── Objectives → Tasks auto-sync ──────────────────────────────────────────

    def _sync_objectives_as_tasks(self, mid: int) -> int:
        """Convert module Lernziele into tasks (skip titles that already exist).

        Returns the number of newly created tasks so the caller can show feedback.
        """
        objectives = self.repo.list_scraped_data(mid, "objective")
        if not objectives:
            return 0

        existing_tasks  = self.repo.list_tasks(module_id=mid)
        existing_titles = {(t["title"] or "").strip().lower() for t in existing_tasks}

        mod  = self.repo.get_module(mid)
        prio = exam_priority(mod["exam_date"] if mod else None)

        created = 0
        for obj in objectives:
            title = (obj["title"] or "").strip()
            if not title:
                continue
            if title.lower() not in existing_titles:
                self.repo.add_task(mid, title, priority=prio, status="Open")
                existing_titles.add(title.lower())   # avoid duplicates within this run
                created += 1
        return created

    def _load_tasks(self, mid: Optional[int]):
        # Clear old task rows
        while self._task_list_lay.count():
            item = self._task_list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not mid:
            self._tasks_title.setText("Aufgaben")
            placeholder = QLabel("Modul auswählen um Aufgaben zu sehen.")
            placeholder.setStyleSheet(f"color:{_tc('#706C86','#6B7280')};font-size:12px;")
            self._task_list_lay.addWidget(placeholder)
            self._task_list_lay.addStretch()
            return

        tasks = [t for t in self.repo.list_tasks() if t["module_id"] == mid]
        open_t = [t for t in tasks if t["status"] != "Done"]
        done_t = [t for t in tasks if t["status"] == "Done"]
        self._tasks_title.setText(
            f"Aufgaben  —  {len(open_t)} offen · {len(done_t)} erledigt"
        )

        # Show a subtle banner if this module has Lernziele (tasks auto-sourced from objectives)
        obj_count = len(self.repo.list_scraped_data(mid, "objective"))
        if obj_count:
            info = QFrame()
            info.setStyleSheet(
                "background:#4A86E815;border-left:3px solid #4A86E8;border-radius:4px;"
            )
            info_lay = QHBoxLayout(info)
            info_lay.setContentsMargins(10, 5, 10, 5)
            info_lbl = QLabel(
                f"📘  {obj_count} Lernziel(e) als Aufgaben importiert — "
                f"Themen zuordnen um Wissen zu strukturieren"
            )
            info_lbl.setStyleSheet(
                f"font-size:11px;color:{_tc('#4A86E8','#7BAAF7')};font-weight:500;"
            )
            info_lbl.setWordWrap(True)
            info_lay.addWidget(info_lbl)
            self._task_list_lay.addWidget(info)

        if not tasks:
            placeholder = QLabel("Keine Aufgaben für dieses Modul.")
            placeholder.setStyleSheet(f"color:{_tc('#706C86','#6B7280')};font-size:12px;")
            self._task_list_lay.addWidget(placeholder)
            self._task_list_lay.addStretch()
            return

        # Auto-priority: compute from module exam date
        mod = self.repo.get_module(mid)
        exam_date_str = mod["exam_date"] if mod else None
        auto_prio = exam_priority(exam_date_str)

        PRIO_COLORS = {
            "Critical": "#E53935", "High": "#F44336",
            "Medium": "#FF9800", "Low": "#4A86E8",
        }
        PRIO_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

        for t in sorted(tasks, key=lambda x: (x["status"] == "Done", PRIO_ORDER.get(auto_prio, 3))):
            is_done = t["status"] == "Done"
            row = QFrame()
            row.setObjectName("Card")
            rly = QHBoxLayout(row)
            rly.setContentsMargins(10, 7, 10, 7)
            rly.setSpacing(10)

            cb = QCheckBox()
            cb.setChecked(is_done)
            cb.setFixedSize(18, 18)

            title_lbl = QLabel(t["title"])
            title_lbl.setStyleSheet(
                f"font-size:12px;"
                f"color:{_tc('#706C86','#6B7280') if is_done else _tc('#1A1A2E','#CDD6F4')};"
                f"{'text-decoration:line-through;' if is_done else ''}"
            )
            title_lbl.setWordWrap(False)

            # Show auto-computed priority badge (based on exam date)
            pc = PRIO_COLORS.get(auto_prio, "#706C86")
            prio_lbl = QLabel(auto_prio)
            prio_lbl.setStyleSheet(
                f"background:{pc}22;color:{pc};"
                f"border-radius:6px;padding:1px 7px;font-size:10px;font-weight:700;"
            )
            prio_lbl.setToolTip("Priorität automatisch berechnet aus Prüfungsdatum")

            due_lbl = QLabel(f"📅 {t['due_date']}" if t["due_date"] else "")
            due_lbl.setStyleSheet(f"font-size:10px;color:{_tc('#706C86','#6B7280')};")

            rly.addWidget(cb)
            rly.addWidget(title_lbl, 1)
            rly.addWidget(prio_lbl)
            rly.addWidget(due_lbl)

            def _toggle_task(state, _tid=t["id"], _lbl=title_lbl):
                new_status = "Done" if state else "Open"
                self.repo.update_task(_tid, status=new_status)
                _lbl.setStyleSheet(
                    f"font-size:12px;"
                    f"color:{_tc('#706C86','#6B7280') if new_status == 'Done' else _tc('#1A1A2E','#CDD6F4')};"
                    f"{'text-decoration:line-through;' if new_status == 'Done' else ''}"
                )
                # Defer rebuild — calling it directly inside stateChanged destroys
                # the checkbox widget while its signal is still on the stack → crash
                if self._global_refresh:
                    QTimer.singleShot(0, self._global_refresh)
                else:
                    QTimer.singleShot(0, lambda: self._load_tasks(self._selected_mid))

            cb.stateChanged.connect(_toggle_task)
            self._task_list_lay.addWidget(row)

        self._task_list_lay.addStretch()

    def _add_task_inline(self):
        """Open TaskDialog pre-set to the current module; sync all pages on save."""
        from semetra.gui.dialogs.task_dialog import TaskDialog
        if TaskDialog(self.repo, default_module_id=self._selected_mid, parent=self).exec():
            if self._global_refresh:
                self._global_refresh()
            else:
                self.refresh()

    def _add_topic(self):
        if not self._selected_mid:
            QMessageBox.warning(self, "Hinweis", "Bitte zuerst ein Modul auswahlen.")
            return
        from semetra.gui.dialogs.topic_dialog import TopicDialog
        if TopicDialog(self.repo, self._selected_mid, parent=self).exec():
            if self._global_refresh:
                self._global_refresh()
            else:
                self._load_topics()

    def _edit_topic(self):
        row = self.topic_table.currentRow()
        if row < 0 or not self._selected_mid:
            return
        tid = int(self.topic_table.item(row, 5).text())
        from semetra.gui.dialogs.topic_dialog import TopicDialog
        if TopicDialog(self.repo, self._selected_mid, topic_id=tid, parent=self).exec():
            if self._global_refresh:
                self._global_refresh()
            else:
                self._load_topics()

    def _delete_topic(self):
        row = self.topic_table.currentRow()
        if row < 0:
            return
        tid = int(self.topic_table.item(row, 5).text())
        if QMessageBox.question(self, "Löschen", "Thema löschen?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_topic(tid)
            if self._global_refresh:
                self._global_refresh()
            else:
                self._load_topics()


