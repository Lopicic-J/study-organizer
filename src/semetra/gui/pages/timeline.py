"""Timeline page — chronological study view."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox,
)
from PySide6.QtCore import Qt

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import make_scroll
from semetra.gui.colors import _tc
from semetra.gui.helpers import mod_color
from semetra.gui.i18n import tr
from semetra.gui.state import _LANG



class TimelinePage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel(tr("page.timeline"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        self.range_cb = QComboBox()
        self.range_cb.addItems(["Nachste 7 Tage", "Nachste 30 Tage", "Nachste 90 Tage", "Alles"])
        self.range_cb.currentIndexChanged.connect(self.refresh)
        hdr.addWidget(QLabel("Zeitraum:"))
        hdr.addWidget(self.range_cb)
        lay.addLayout(hdr)

        self.scroll_w = QWidget()
        self.scroll_lay = QVBoxLayout(self.scroll_w)
        self.scroll_lay.setSpacing(8)
        self.scroll_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(make_scroll(self.scroll_w), 1)

    def refresh(self):
        while self.scroll_lay.count():
            item = self.scroll_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        days_map = {"Nachste 7 Tage": 7, "Nachste 30 Tage": 30,
                    "Nachste 90 Tage": 90, "Alles": 3650}
        max_days = days_map.get(self.range_cb.currentText(), 30)
        today = date.today()
        items = []

        for t in self.repo.list_tasks():
            if t["due_date"] and t["status"] != "Done":
                try:
                    d = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
                    delta = (d - today).days
                    if -3 <= delta <= max_days:
                        items.append({"date": d, "delta": delta, "type": "task",
                                      "title": t["title"], "sub": t["module_name"],
                                      "color": mod_color(t["module_id"])})
                except Exception:
                    pass

        for m in self.repo.all_exams():
            try:
                d = datetime.strptime(m["exam_date"], "%Y-%m-%d").date()
                delta = (d - today).days
                if -3 <= delta <= max_days:
                    items.append({"date": d, "delta": delta, "type": "exam",
                                  "title": f"Prüfung: {m['name']}", "sub": m["semester"],
                                  "color": mod_color(m["id"])})
            except Exception:
                pass

        items.sort(key=lambda x: x["date"])

        if not items:
            lbl = QLabel("Keine Fristen im gewahlten Zeitraum.")
            lbl.setStyleSheet("color: #706C86; font-size: 14px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.scroll_lay.addWidget(lbl)
        else:
            last_date = None
            for item in items:
                if item["date"] != last_date:
                    delta = item["delta"]
                    if delta == 0:
                        ds = tr("sec.today")
                    elif delta == 1:
                        ds = {"de":"Morgen","en":"Tomorrow","fr":"Demain","it":"Domani"}.get(_LANG,"Tomorrow")
                    elif delta < 0:
                        over = {"de":"überfällig","en":"overdue","fr":"en retard","it":"scaduto"}.get(_LANG,"overdue")
                        ds = f"{item['date'].strftime('%d. %b')} ({over})"
                    else:
                        ds = item["date"].strftime("%A, %d. %B %Y")
                    h = QLabel(ds)
                    h.setStyleSheet("font-weight: bold; color: #706C86; font-size: 12px; padding-top: 8px;")
                    self.scroll_lay.addWidget(h)
                    last_date = item["date"]
                self.scroll_lay.addWidget(self._make_item(item))

        self.scroll_lay.addStretch()

    def _make_item(self, item: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedHeight(60)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(12)

        bar = QWidget()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background:{item['color']};border-radius:2px;")
        lay.addWidget(bar)

        icon = "Prüfung" if item["type"] == "exam" else "Aufgabe"
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        tl = QLabel(item["title"])
        tl.setStyleSheet("font-weight: bold; font-size: 13px;")
        text_col.addWidget(tl)
        sl = QLabel(f"{icon}  |  {item['sub']}")
        sl.setStyleSheet("color: #706C86; font-size: 11px;")
        text_col.addWidget(sl)
        lay.addLayout(text_col, 1)

        delta = item["delta"]
        if delta < 0:
            bt, bc = f"{abs(delta)}d uberfällig", "#F44336"
        elif delta == 0:
            bt, bc = "HEUTE", "#F44336"
        elif delta <= 3:
            bt, bc = f"in {delta}d", "#FF9800"
        elif delta <= 14:
            bt, bc = f"in {delta}d", "#4A86E8"
        else:
            bt, bc = f"in {delta}d", "#9E9E9E"

        badge = QLabel(bt)
        badge.setStyleSheet(
            f"background:{bc};color:white;border-radius:10px;"
            f"padding:2px 8px;font-size:11px;font-weight:bold;"
        )
        lay.addWidget(badge)
        return card


