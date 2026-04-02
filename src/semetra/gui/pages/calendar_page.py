"""Calendar page — visual study schedule."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCalendarWidget,
    QFrame, QProgressBar, QSizePolicy, QGridLayout, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QColor

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import make_scroll, _CalCell, WeekHeatmapWidget
from semetra.gui.widgets.heatmap import _week_stress_data
from semetra.gui.i18n import tr
from semetra.gui.colors import _tc
from semetra.gui.constants import PRIORITY_COLORS



class CalendarPage(QWidget):
    _MONTH_NAMES = ["Januar","Februar","März","April","Mai","Juni",
                    "Juli","August","September","Oktober","November","Dezember"]
    _DAY_NAMES   = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        today = date.today()
        self._cur_year  = today.year
        self._cur_month = today.month
        self._selected_date = today
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(20)

        # ── Left: custom calendar grid ───────────────────────────────────────
        left = QVBoxLayout()

        hdr = QHBoxLayout()
        title = QLabel(tr("page.calendar"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        add_ev_btn = QPushButton("+ Ereignis")
        add_ev_btn.setObjectName("PrimaryBtn")
        add_ev_btn.clicked.connect(self._add_event)
        hdr.addWidget(add_ev_btn)
        left.addLayout(hdr)

        # Month navigation bar
        nav = QHBoxLayout()
        prev_btn = QPushButton("‹")
        prev_btn.setFixedSize(28, 28)
        prev_btn.clicked.connect(self._prev_month)
        self._month_lbl = QLabel()
        self._month_lbl.setAlignment(Qt.AlignCenter)
        self._month_lbl.setStyleSheet("font-weight:700;font-size:14px;")
        next_btn = QPushButton("›")
        next_btn.setFixedSize(28, 28)
        next_btn.clicked.connect(self._next_month)
        today_btn = QPushButton("Heute")
        today_btn.clicked.connect(self._go_today)
        nav.addWidget(prev_btn)
        nav.addWidget(self._month_lbl, 1)
        nav.addWidget(next_btn)
        nav.addSpacing(10)
        nav.addWidget(today_btn)
        left.addLayout(nav)

        # Weekday header + cell grid in one container
        grid_w = QWidget()
        grid_w.setAttribute(Qt.WA_StyledBackground, True)
        grid_outer = QVBoxLayout(grid_w)
        grid_outer.setContentsMargins(0, 4, 0, 0)
        grid_outer.setSpacing(4)

        day_hdr = QHBoxLayout()
        day_hdr.setSpacing(2)
        for name in ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]:
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedHeight(22)
            lbl.setStyleSheet(
                f"font-size:11px;font-weight:700;color:{_tc('#706C86','#6B7280')};"
            )
            day_hdr.addWidget(lbl, 1)
        grid_outer.addLayout(day_hdr)

        self._grid_lay = QGridLayout()
        self._grid_lay.setSpacing(2)
        self._grid_lay.setContentsMargins(0, 0, 0, 0)
        # Equal column + row stretching so all cells are the same size
        for col in range(7):
            self._grid_lay.setColumnStretch(col, 1)
        for row in range(6):
            self._grid_lay.setRowStretch(row, 1)
        self._cells: list = []
        for row in range(6):
            row_cells = []
            for col in range(7):
                cell = _CalCell(self)
                cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self._grid_lay.addWidget(cell, row, col)
                row_cells.append(cell)
            self._cells.append(row_cells)
        grid_outer.addLayout(self._grid_lay)

        left.addWidget(grid_w, 1)
        lay.addLayout(left, 3)

        # ── Right: day detail + upcoming ─────────────────────────────────────
        right = QVBoxLayout()
        day_hdr2 = QHBoxLayout()
        self.day_title = QLabel("Heute")
        self.day_title.setObjectName("SectionTitle")
        day_hdr2.addWidget(self.day_title)
        day_hdr2.addStretch()
        del_ev_btn = QPushButton("Ereignis löschen")
        del_ev_btn.setObjectName("DangerBtn")
        del_ev_btn.clicked.connect(self._delete_selected_event)
        day_hdr2.addWidget(del_ev_btn)
        right.addLayout(day_hdr2)

        self.day_list = QListWidget()
        self.day_list.setFixedHeight(200)
        right.addWidget(self.day_list)

        # ── Stress-Heatmap ───────────────────────────────────────────────
        self._heatmap = WeekHeatmapWidget()
        right.addWidget(self._heatmap)

        self._upcoming_lbl = QLabel(tr("sec.upcoming"))
        self._upcoming_lbl.setObjectName("SectionTitle")
        right.addWidget(self._upcoming_lbl)
        self.upcoming_list = QListWidget()
        right.addWidget(self.upcoming_list, 1)
        lay.addLayout(right, 2)

    # ── Navigation ───────────────────────────────────────────────────────────

    def _prev_month(self):
        if self._cur_month == 1:
            self._cur_month, self._cur_year = 12, self._cur_year - 1
        else:
            self._cur_month -= 1
        self.refresh()

    def _next_month(self):
        if self._cur_month == 12:
            self._cur_month, self._cur_year = 1, self._cur_year + 1
        else:
            self._cur_month += 1
        self.refresh()

    def _go_today(self):
        today = date.today()
        self._cur_year, self._cur_month = today.year, today.month
        self._selected_date = today
        self.refresh()

    def _on_cell_clicked(self, d: date):
        self._selected_date = d
        self._rebuild_grid()
        self._on_date_selected()

    # ── Data helpers ─────────────────────────────────────────────────────────

    def _events_for_month(self) -> dict:
        """Return {date: [(icon, title, color)]} for the currently displayed month."""
        y, m = self._cur_year, self._cur_month
        result: dict = {}

        for ev in self.repo.list_events():
            try:
                d = datetime.strptime(ev["start_date"], "%Y-%m-%d").date()
                if d.year == y and d.month == m:
                    icon = {"lecture":"📖","exercise":"✏️","study":"📚",
                            "exam":"🎯","custom":"📌"}.get(ev["kind"], "📌")
                    result.setdefault(d, []).append((icon, ev["title"], "#2CB67D"))
            except Exception:
                pass

        for t in self.repo.list_tasks():
            if t["due_date"] and t["status"] != "Done":
                try:
                    d = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
                    if d.year == y and d.month == m:
                        color = PRIORITY_COLORS.get(t["priority"], "#FF8C42")
                        result.setdefault(d, []).append(("✅", t["title"], color))
                except Exception:
                    pass

        for mod in self.repo.list_modules("all"):
            if mod["exam_date"]:
                try:
                    d = datetime.strptime(mod["exam_date"], "%Y-%m-%d").date()
                    if d.year == y and d.month == m:
                        result.setdefault(d, []).append(("🎯", mod["name"], "#F44336"))
                except Exception:
                    pass

        return result

    # ── Grid rendering ───────────────────────────────────────────────────────

    def _rebuild_grid(self):
        import calendar as _cal
        y, m = self._cur_year, self._cur_month
        self._month_lbl.setText(f"{self._MONTH_NAMES[m - 1]} {y}")
        today = date.today()
        ev_map = self._events_for_month()

        # Build a day → stress_level map from this month's week data
        # Use the cached _stress_by_week if available, else recompute
        day_stress: dict = {}
        for wd in getattr(self, "_stress_weeks", []):
            lvl = wd["level"]
            ws, we = wd["week_start"], wd["week_end"]
            d_iter = ws
            while d_iter <= we:
                if d_iter.year == y and d_iter.month == m:
                    day_stress[d_iter] = lvl
                d_iter += timedelta(days=1)

        weeks = _cal.monthcalendar(y, m)
        while len(weeks) < 6:
            weeks.append([0] * 7)
        for row, week in enumerate(weeks):
            for col, day_num in enumerate(week):
                cell = self._cells[row][col]
                if day_num == 0:
                    cell.set_day(None, [], False, False, stress_level=0)
                else:
                    d = date(y, m, day_num)
                    cell.set_day(d, ev_map.get(d, []), d == today, d == self._selected_date,
                                 stress_level=day_stress.get(d, 0))

    # ── Actions ──────────────────────────────────────────────────────────────

    def _add_event(self):
        from semetra.gui.dialogs.event_dialog import EventDialog
        default_date = self._selected_date.strftime("%Y-%m-%d")
        if EventDialog(self.repo, default_date=default_date, parent=self).exec():
            self.refresh()

    def _delete_selected_event(self):
        item = self.day_list.currentItem()
        if not item:
            return
        eid = item.data(Qt.UserRole)
        if eid is None or eid < 0:
            QMessageBox.information(self, "Hinweis",
                "Aufgaben und Prüfungen können nur in den jeweiligen Tabs gelöscht werden.")
            return
        if QMessageBox.question(self, "Löschen", "Ereignis löschen?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_event(eid)
            self.refresh()

    def _on_date_selected(self):
        d = self._selected_date
        d_str = d.strftime("%Y-%m-%d")
        self.day_title.setText(
            f"{self._DAY_NAMES[d.weekday()]}, {d.day}. {self._MONTH_NAMES[d.month - 1]} {d.year}"
        )
        self.day_list.clear()

        for ev in self.repo.list_events():
            if ev["start_date"] <= d_str <= (ev["end_date"] or ev["start_date"]):
                kind_icon = {"lecture":"📖","exercise":"✏️","study":"📚",
                             "exam":"🎯","custom":"📌"}.get(ev["kind"], "📌")
                mod_str  = f" ({ev['module_name']})" if ev["module_name"] else ""
                time_str = f" {ev['start_time']}" if ev["start_time"] else ""
                item = QListWidgetItem(f"{kind_icon} {ev['title']}{mod_str}{time_str}")
                item.setData(Qt.UserRole, ev["id"])
                item.setForeground(QColor("#2CB67D"))
                self.day_list.addItem(item)

        for t in self.repo.list_tasks():
            if t["due_date"] == d_str:
                color = PRIORITY_COLORS.get(t["priority"], "#333")
                item = QListWidgetItem(f"✅ Aufgabe: {t['title']} ({t['module_name']})")
                item.setData(Qt.UserRole, -1)
                item.setForeground(QColor(color))
                self.day_list.addItem(item)

        for mod in self.repo.list_modules("all"):
            if mod["exam_date"] == d_str:
                item = QListWidgetItem(f"🎯 PRÜFUNG: {mod['name']}")
                item.setData(Qt.UserRole, -1)
                item.setForeground(QColor("#F44336"))
                self.day_list.addItem(item)

        if not self.day_list.count():
            self.day_list.addItem("Keine Einträge für diesen Tag")

    def _load_upcoming(self):
        self.upcoming_list.clear()
        today = date.today()
        items = []
        for ev in self.repo.list_events():
            try:
                d = datetime.strptime(ev["start_date"], "%Y-%m-%d").date()
                delta = (d - today).days
                if 0 <= delta <= 14:
                    mod_str = f" ({ev['module_name']})" if ev["module_name"] else ""
                    items.append((delta, f"📌 {ev['title']}{mod_str} — in {delta} Tag(en)"))
            except Exception:
                pass
        for t in self.repo.list_tasks():
            if t["due_date"] and t["status"] != "Done":
                try:
                    d = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
                    delta = (d - today).days
                    if 0 <= delta <= 14:
                        items.append((delta, f"✅ Aufgabe: {t['title']} — in {delta} Tag(en)"))
                except Exception:
                    pass
        for mod in self.repo.all_exams():
            try:
                d = datetime.strptime(mod["exam_date"], "%Y-%m-%d").date()
                delta = (d - today).days
                if 0 <= delta <= 14:
                    items.append((delta, f"🎯 Prüfung: {mod['name']} — in {delta} Tag(en)"))
            except Exception:
                pass
        items.sort(key=lambda x: x[0])
        for _, text in items:
            self.upcoming_list.addItem(text)
        if not items:
            self.upcoming_list.addItem("Keine Einträge in den nächsten 14 Tagen")

    def refresh(self):
        self._upcoming_lbl.setText(tr("sec.upcoming"))
        # Compute stress data once, cache for grid coloring + heatmap strip
        self._stress_weeks = _week_stress_data(self.repo, weeks=12)
        self._heatmap.update_data(self._stress_weeks)
        self._rebuild_grid()
        self._on_date_selected()
        self._load_upcoming()


