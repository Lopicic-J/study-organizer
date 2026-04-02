from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QScrollArea,
    QFrame, QWidget, QDialogButtonBox,
)
from PySide6.QtCore import Qt

from semetra.repo.sqlite_repo import SqliteRepo


# Module colors (from gui.py)
MODULE_COLORS = [
    "#4A86E8", "#E84A5F", "#2CB67D", "#FF8C42", "#9B59B6",
    "#00B4D8", "#F72585", "#3A86FF", "#F4A261", "#2EC4B6",
]


def mod_color(mid: int) -> str:
    return MODULE_COLORS[mid % len(MODULE_COLORS)]


def days_until(s: str) -> Optional[int]:
    from datetime import datetime
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
        return (d - date.today()).days
    except Exception:
        return None


class NotfallModusDialog(QDialog):
    """
    Crashplan-Modus wenn eine Prüfung in <7 Tagen ist.
    Zeigt: verfügbare Zeit, schwache Themen, Stundenplan für verbleibende Tage.
    """

    def __init__(self, repo: SqliteRepo, module_id: int = None, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._module_id = module_id
        self.setWindowTitle("🚨  Notfall-Crashplan")
        self.resize(640, 560)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel("🚨  Crashplan")
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        mod_lbl = QLabel("Modul:")
        hdr.addWidget(mod_lbl)
        self.mod_cb = QComboBox()
        self.mod_cb.setMinimumWidth(200)
        exams = self._repo.upcoming_exams(within_days=30)
        if not exams:
            exams = self._repo.all_exams()
        for m in exams:
            self.mod_cb.addItem(m["name"], m["id"])
        if self._module_id:
            for i in range(self.mod_cb.count()):
                if self.mod_cb.itemData(i) == self._module_id:
                    self.mod_cb.setCurrentIndex(i)
                    break
        self.mod_cb.currentIndexChanged.connect(self._refresh_plan)
        hdr.addWidget(self.mod_cb)
        lay.addLayout(hdr)

        self.plan_sa = QScrollArea()
        self.plan_sa.setWidgetResizable(True)
        self.plan_sa.setFrameShape(QFrame.NoFrame)
        self.plan_w = QWidget()
        self.plan_lay = QVBoxLayout(self.plan_w)
        self.plan_lay.setSpacing(8)
        self.plan_sa.setWidget(self.plan_w)
        lay.addWidget(self.plan_sa, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._refresh_plan()

    def _refresh_plan(self):
        while self.plan_lay.count():
            item = self.plan_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        mid = self.mod_cb.currentData()
        if not mid:
            return
        mod = self._repo.get_module(mid)
        if not mod:
            return

        exam_d = days_until(mod["exam_date"]) if mod["exam_date"] else None
        topics = self._repo.list_topics(mid)
        color = mod_color(mid)

        # ── Summary card ────────────────────────────────────────────────────
        summary = QFrame()
        summary.setObjectName("QuoteCard")
        summary.setAttribute(Qt.WA_StyledBackground, True)
        sl = QVBoxLayout(summary)
        sl.setContentsMargins(16, 12, 16, 12)
        sl.setSpacing(6)

        if exam_d is None:
            title_txt = f"📅 Kein Prüfungsdatum für {mod['name']} gesetzt"
        elif exam_d == 0:
            title_txt = f"🔴 Prüfung HEUTE: {mod['name']}"
        elif exam_d < 0:
            title_txt = f"✅ Prüfung für {mod['name']} ist vorbei"
        else:
            title_txt = f"⏳ Prüfung {mod['name']} in {exam_d} Tag{'en' if exam_d != 1 else ''}"

        tl = QLabel(title_txt)
        tl.setStyleSheet(f"font-size:15px;font-weight:bold;color:{color};background:transparent;")
        sl.addWidget(tl)

        studied_h = self._repo.seconds_studied_for_module(mid) / 3600
        target_h = self._repo.ects_target_hours(mid)
        remaining_h = max(0, target_h - studied_h)
        available_h = (exam_d or 1) * 5  # assume 5h/day available

        info_txt = (f"Schon gelernt: {studied_h:.1f}h / {target_h:.0f}h Ziel  ·  "
                    f"Noch verfügbar: ~{available_h:.0f}h ({exam_d or 0} Tage × 5h)")
        il = QLabel(info_txt)
        il.setStyleSheet("font-size:12px;color:#6B7280;background:transparent;")
        sl.addWidget(il)
        self.plan_lay.addWidget(summary)

        # ── Topics sorted by weakness ────────────────────────────────────────
        if topics:
            topics_hdr = QLabel("📋  Themen nach Priorität")
            topics_hdr.setObjectName("SectionTitle")
            self.plan_lay.addWidget(topics_hdr)

            # Sort: unknown/weak first
            sorted_topics = sorted(topics, key=lambda t: int(t["knowledge_level"]) if t["knowledge_level"] else 0)

            for t in sorted_topics:
                lvl = int(t["knowledge_level"]) if t["knowledge_level"] else 0
                icons = {0: "🔴", 1: "🔴", 2: "🟠", 3: "🟡", 4: "✅"}
                labels = {0: "Unbekannt", 1: "Grundlagen", 2: "Vertraut", 3: "Gut", 4: "Experte"}
                tf = QFrame()
                tf.setObjectName("Card")
                tfl = QHBoxLayout(tf)
                tfl.setContentsMargins(12, 8, 12, 8)
                tfl.setSpacing(10)
                icon_lbl = QLabel(icons[lvl])
                icon_lbl.setStyleSheet("font-size:16px;")
                tfl.addWidget(icon_lbl)
                name_lbl = QLabel(f"<b>{t['title']}</b>")
                name_lbl.setTextFormat(Qt.RichText)
                tfl.addWidget(name_lbl, 1)
                lvl_lbl = QLabel(labels[lvl])
                lvl_lbl.setStyleSheet(
                    f"font-size:11px;color:{'#DC2626' if lvl <= 1 else '#D97706' if lvl == 2 else '#6B7280'};"
                )
                tfl.addWidget(lvl_lbl)
                self.plan_lay.addWidget(tf)
        else:
            no_topics = QLabel("⚠ Noch keine Lernthemen für dieses Modul. Füge sie auf der Wissensseite hinzu.")
            no_topics.setStyleSheet("color:#D97706;font-size:13px;padding:8px;")
            no_topics.setWordWrap(True)
            self.plan_lay.addWidget(no_topics)

        # ── Day-by-day plan ──────────────────────────────────────────────────
        if exam_d and exam_d > 0 and topics:
            plan_hdr = QLabel("📅  Tagesplan bis zur Prüfung")
            plan_hdr.setObjectName("SectionTitle")
            self.plan_lay.addWidget(plan_hdr)

            weak_topics = [t for t in sorted_topics if (int(t["knowledge_level"]) if t["knowledge_level"] else 0) < 4]
            topics_per_day = max(1, len(weak_topics) // max(1, exam_d))
            topic_idx = 0
            for day in range(min(exam_d, 7)):
                day_date = date.today() + timedelta(days=day)
                day_name = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][day_date.weekday()]
                day_topics = weak_topics[topic_idx:topic_idx + topics_per_day]
                topic_idx += topics_per_day

                df = QFrame()
                df.setObjectName("Card")
                dfl = QVBoxLayout(df)
                dfl.setContentsMargins(12, 8, 12, 8)
                dfl.setSpacing(4)
                day_hdr_lbl = QLabel(
                    f"<b>{day_name}, {day_date.strftime('%d.%m.')}</b>"
                    + (" — <span style='color:#DC2626'>Prüfungstag!</span>" if day == exam_d - 1 else "")
                )
                day_hdr_lbl.setTextFormat(Qt.RichText)
                dfl.addWidget(day_hdr_lbl)
                if day == exam_d - 1:
                    dfl.addWidget(QLabel("  🔁 Alles wiederholen + ausschlafen!"))
                elif day_topics:
                    for dt in day_topics:
                        lvl = int(dt["knowledge_level"]) if dt["knowledge_level"] else 0
                        dfl.addWidget(QLabel(f"  {'🔴' if lvl <= 1 else '🟠'} {dt['title']}"))
                else:
                    dfl.addWidget(QLabel("  📖 Freie Wiederholung / Nachfragen klären"))
                self.plan_lay.addWidget(df)

        self.plan_lay.addStretch()
