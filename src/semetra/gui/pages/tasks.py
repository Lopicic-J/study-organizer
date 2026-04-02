"""Tasks page — manage module tasks."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QDialog, QDialogButtonBox, QMessageBox, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSizePolicy, QCheckBox, QSplitter, QTextEdit,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import QComboBox, make_scroll
from semetra.gui.helpers import mod_color, days_until, _active_sem_filter, _filter_mods_by_sem
from semetra.gui.widgets.helpers import separator
from semetra.gui.i18n import tr, tr_status
from semetra.gui.constants import PRIORITY_COLORS
from semetra.gui.colors import _tc
from semetra.gui.state import _LANG



class TasksPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._current_detail_tid: Optional[int] = None
        self._build()

    def _build(self):
        _page_lay = QVBoxLayout(self)
        _page_lay.setContentsMargins(0, 0, 0, 0)
        _page_lay.setSpacing(0)
        _scroll_w = QWidget()
        _scroll_w.setAttribute(Qt.WA_StyledBackground, True)
        _page_lay.addWidget(make_scroll(_scroll_w))
        outer = QVBoxLayout(_scroll_w)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel(tr("page.tasks"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = QPushButton("+ Neue Aufgabe")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_task)
        hdr.addWidget(add_btn)
        outer.addLayout(hdr)

        frow = QHBoxLayout()
        frow.setSpacing(10)
        self.mod_filter = QComboBox()
        self.mod_filter.addItem("Alle Module", None)
        self.mod_filter.currentIndexChanged.connect(self.refresh)
        frow.addWidget(QLabel("Modul:"))
        frow.addWidget(self.mod_filter)
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Alle", "Open", "In Progress", "Done"])
        self.status_filter.currentIndexChanged.connect(self.refresh)
        frow.addWidget(QLabel("Status:"))
        frow.addWidget(self.status_filter)
        self.prio_filter = QComboBox()
        self.prio_filter.addItems(["Alle", "Critical", "High", "Medium", "Low"])
        self.prio_filter.currentIndexChanged.connect(self.refresh)
        frow.addWidget(QLabel("Priorität:"))
        frow.addWidget(self.prio_filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen...")
        self.search.textChanged.connect(self.refresh)
        frow.addWidget(self.search, 1)
        outer.addLayout(frow)

        # Splitter: table left | detail right
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        # splitter handle colour is set by the global QSS (QSplitter::handle)

        # Left: table + count/delete
        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(8)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Titel", "Modul", "Priorität", "Status", "Fällig", "ID"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnHidden(5, True)
        self.table.doubleClicked.connect(self._edit_task)
        self.table.currentCellChanged.connect(self._on_row_changed)
        left_lay.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.count_lbl = QLabel()
        self.count_lbl.setStyleSheet("color: #706C86; font-size: 12px;")
        bottom.addWidget(self.count_lbl)
        bottom.addStretch()
        del_btn = QPushButton("Gewählte löschen")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_task)
        bottom.addWidget(del_btn)
        left_lay.addLayout(bottom)
        splitter.addWidget(left_w)

        # Right: detail panel
        detail_w = QFrame()
        detail_w.setObjectName("Card")
        detail_lay = QVBoxLayout(detail_w)
        detail_lay.setContentsMargins(16, 14, 16, 14)
        detail_lay.setSpacing(10)

        self._det_placeholder = QLabel("← Aufgabe auswählen\nfür Details & Lerninhalt")
        self._det_placeholder.setAlignment(Qt.AlignCenter)
        self._det_placeholder.setStyleSheet("color:#706C86;font-size:13px;")
        self._det_placeholder.setWordWrap(True)
        detail_lay.addWidget(self._det_placeholder)

        self._det_content = QWidget()
        dc_lay = QVBoxLayout(self._det_content)
        dc_lay.setContentsMargins(0, 0, 0, 0)
        dc_lay.setSpacing(8)

        self._det_title = QLabel()
        self._det_title.setStyleSheet("font-size:14px;font-weight:bold;")
        self._det_title.setWordWrap(True)
        dc_lay.addWidget(self._det_title)

        self._det_meta = QLabel()
        self._det_meta.setStyleSheet("color:#706C86;font-size:12px;")
        dc_lay.addWidget(self._det_meta)

        # Quick status buttons
        sq_row = QHBoxLayout()
        sq_row.setSpacing(4)
        self._det_btn_open = QPushButton("⬜ Offen")
        self._det_btn_ip   = QPushButton("🔄 In Arbeit")
        self._det_btn_done = QPushButton("✅ Erledigt")
        for b in [self._det_btn_open, self._det_btn_ip, self._det_btn_done]:
            b.setObjectName("SecondaryBtn")
            b.setFixedHeight(28)
            sq_row.addWidget(b)
        sq_row.addStretch()
        self._det_btn_open.clicked.connect(lambda: self._quick_status("Open"))
        self._det_btn_ip.clicked.connect(lambda: self._quick_status("In Progress"))
        self._det_btn_done.clicked.connect(lambda: self._quick_status("Done"))
        dc_lay.addLayout(sq_row)

        dc_lay.addWidget(separator())

        notes_lbl = QLabel("📖 Lerninhalt:")
        notes_lbl.setStyleSheet("font-weight:bold;font-size:12px;color:#4A86E8;")
        dc_lay.addWidget(notes_lbl)

        self._det_notes = QTextEdit()
        self._det_notes.setObjectName("NotesArea")
        self._det_notes.setReadOnly(True)
        self._det_notes.setStyleSheet("font-size:12px;")
        dc_lay.addWidget(self._det_notes, 1)

        self._det_content.hide()
        detail_lay.addWidget(self._det_content)
        splitter.addWidget(detail_w)

        splitter.setSizes([720, 420])
        outer.addWidget(splitter, 1)

    def refresh(self):
        # Retranslate static labels
        self.table.setHorizontalHeaderLabels([
            tr("task.title"), tr("task.module"), tr("task.priority"),
            tr("task.status"), tr("task.due"), "ID"
        ])
        self.search.setPlaceholderText(tr("task.search"))

        # Build semester-filtered module list
        sem_f = _active_sem_filter(self.repo)
        mods_filtered = _filter_mods_by_sem(self.repo.list_modules("all"), sem_f)
        mod_ids_allowed = {m["id"] for m in mods_filtered}

        cur_mod = self.mod_filter.currentData()
        self.mod_filter.blockSignals(True)
        self.mod_filter.clear()
        self.mod_filter.addItem(tr("grade.all_modules"), None)
        for m in mods_filtered:
            self.mod_filter.addItem(m["name"], m["id"])
        if cur_mod and cur_mod in mod_ids_allowed:
            for i in range(self.mod_filter.count()):
                if self.mod_filter.itemData(i) == cur_mod:
                    self.mod_filter.setCurrentIndex(i)
                    break
        self.mod_filter.blockSignals(False)

        mid = self.mod_filter.currentData()
        st = self.status_filter.currentText()
        pr = self.prio_filter.currentText()
        tasks = self.repo.list_tasks(
            module_id=mid,
            status="all" if st in ("Alle", "All") else st,
            priority="all" if pr in ("Alle", "All") else pr,
        )
        # Apply semester filter: keep only tasks whose module is in the filtered set
        if sem_f:
            tasks = [t for t in tasks if t["module_id"] in mod_ids_allowed]
        q = self.search.text().lower()
        if q:
            tasks = [t for t in tasks if q in t["title"].lower()]

        # Build exam-proximity map: module_id → days_until_exam
        _exam_proximity: dict[int, int] = {}
        for m in self.repo.all_exams():
            d = days_until(m["exam_date"])
            if d is not None and 0 <= d <= 10:
                _exam_proximity[m["id"]] = d

        # Sort: exam-urgent tasks first, then by due_date
        today_str_t = date.today().isoformat()
        def _task_sort_key(t):
            exam_d = _exam_proximity.get(t["module_id"], 999)
            due = t["due_date"] or "9999"
            overdue = 0 if due >= today_str_t else -1
            return (overdue, exam_d, due)
        tasks = sorted(tasks, key=_task_sort_key)

        self.table.setRowCount(len(tasks))
        for r, t in enumerate(tasks):
            exam_d = _exam_proximity.get(t["module_id"])
            # Title: append exam badge if close
            title_text = t["title"]
            if exam_d is not None:
                badge = "🔴" if exam_d <= 3 else "🟠"
                title_text += f"  {badge} Prüfung in {exam_d}d"
            title_item = QTableWidgetItem(title_text)
            if exam_d is not None and exam_d <= 3:
                title_item.setForeground(QColor("#DC2626"))
            elif exam_d is not None:
                title_item.setForeground(QColor("#D97706"))
            self.table.setItem(r, 0, title_item)
            mod_item = QTableWidgetItem(t["module_name"])
            mod_item.setForeground(QColor(mod_color(t["module_id"])))
            self.table.setItem(r, 1, mod_item)
            p_item = QTableWidgetItem(t["priority"])
            p_item.setForeground(QColor(PRIORITY_COLORS.get(t["priority"], "#333")))
            self.table.setItem(r, 2, p_item)
            self.table.setItem(r, 3, QTableWidgetItem(tr_status(t["status"])))
            due_str = t["due_date"] or "—"
            due_item = QTableWidgetItem(due_str)
            if due_str != "—" and due_str < today_str_t:
                due_item.setForeground(QColor("#DC2626"))
            self.table.setItem(r, 4, due_item)
            self.table.setItem(r, 5, QTableWidgetItem(str(t["id"])))
        n = len(tasks)
        self.count_lbl.setText(
            {"de": f"{n} Aufgabe(n)", "en": f"{n} task(s)",
             "fr": f"{n} tâche(s)", "it": f"{n} attività"}.get(_LANG, f"{n}")
        )

    def _on_row_changed(self, cur_row, cur_col, prev_row, prev_col):
        tid_item = self.table.item(cur_row, 5)
        if not tid_item:
            return
        tid = int(tid_item.text())
        self._current_detail_tid = tid
        task = self.repo.get_task(tid)
        if not task:
            return
        mod_item = self.table.item(cur_row, 1)
        mod_name = mod_item.text() if mod_item else ""
        title = task["title"]
        self._det_title.setText(title)
        self._det_meta.setText(
            f"📚 {mod_name}  ·  Status: {task['status']}  ·  Priorität: {task['priority']}"
        )
        notes = task["notes"] or ""
        if notes:
            lines = notes.split("\n")
            html = ['<div style="font-family:sans-serif;font-size:12px;line-height:1.6;">']
            for line in lines:
                line = line.strip()
                if not line:
                    html.append("<br>")
                elif line.startswith("•"):
                    html.append(f'<div style="padding:1px 0 1px 12px;">• {line[1:].strip()}</div>')
                elif line.startswith("📝") or line.startswith("📊"):
                    html.append(f'<div style="color:#4A86E8;font-weight:bold;margin-top:8px;">{line}</div>')
                elif line.startswith("ECTS:"):
                    html.append(f'<div style="color:#706C86;font-size:11px;margin-top:4px;">{line}</div>')
                else:
                    html.append(f'<div>{line}</div>')
            html.append("</div>")
            self._det_notes.setHtml("".join(html))
        else:
            self._det_notes.setPlainText("Keine Notizen vorhanden.")
        self._det_placeholder.hide()
        self._det_content.show()

    def _quick_status(self, status: str):
        if not self._current_detail_tid:
            return
        self.repo.update_task(self._current_detail_tid, status=status)
        self.refresh()

    def _current_task_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 5)
        return int(item.text()) if item else None

    def _add_task(self):
        from semetra.gui.dialogs.task_dialog import TaskDialog
        if TaskDialog(self.repo, parent=self).exec():
            self.refresh()

    def _edit_task(self):
        tid = self._current_task_id()
        if tid:
            from semetra.gui.dialogs.task_dialog import TaskDialog
            if TaskDialog(self.repo, task_id=tid, parent=self).exec():
                self.refresh()

    def _delete_task(self):
        tid = self._current_task_id()
        if not tid:
            return
        if QMessageBox.question(self, "Löschen", "Aufgabe löschen?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_task(tid)
            self.refresh()


