from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton,
    QScrollArea, QFrame, QWidget, QDialogButtonBox,
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
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
        return (d - date.today()).days
    except Exception:
        return None


class StudyPlanGeneratorDialog(QDialog):
    """
    Generiert einen personalisierten Lernplan für die nächsten 2 Wochen.
    Basiert auf: Prüfungsdaten, ECTS-Gewichtung, aktuellem Lernfortschritt.
    Kein KI-API nötig — smarte, regelbasierte Verteilung.
    """

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("📅  Lernplan Generator")
        self.resize(820, 600)
        self._build()
        self._generate()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel("📅  Dein persönlicher Lernplan")
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        lay.addLayout(hdr)

        sub = QLabel("Basiert auf deinen Prüfungsterminen, ECTS-Gewichtung und aktuellem Lernstand.")
        sub.setStyleSheet("color:#6B7280;font-size:12px;")
        lay.addWidget(sub)

        # Settings row
        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("Lernen pro Tag:"))
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(1, 12)
        self.hours_spin.setValue(3)
        self.hours_spin.setSuffix(" h")
        settings_row.addWidget(self.hours_spin)
        settings_row.addSpacing(20)
        settings_row.addWidget(QLabel("Tage voraus:"))
        self.days_spin = QSpinBox()
        self.days_spin.setRange(7, 28)
        self.days_spin.setValue(14)
        self.days_spin.setSuffix(" Tage")
        settings_row.addWidget(self.days_spin)
        settings_row.addStretch()
        regen_btn = QPushButton("🔄  Neu generieren")
        regen_btn.setObjectName("PrimaryBtn")
        regen_btn.clicked.connect(self._generate)
        settings_row.addWidget(regen_btn)
        lay.addLayout(settings_row)

        # Plan output
        self.plan_area = QScrollArea()
        self.plan_area.setWidgetResizable(True)
        self.plan_area.setFrameShape(QFrame.NoFrame)
        self.plan_container = QWidget()
        self.plan_layout = QVBoxLayout(self.plan_container)
        self.plan_layout.setSpacing(6)
        self.plan_layout.setContentsMargins(0, 0, 0, 0)
        self.plan_area.setWidget(self.plan_container)
        lay.addWidget(self.plan_area, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _generate(self):
        # Clear existing plan
        while self.plan_layout.count():
            item = self.plan_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        hours_per_day = self.hours_spin.value()
        days_ahead = self.days_spin.value()
        today = date.today()

        # ── Gather modules with upcoming exams ───────────────────────────────
        modules_data: list[dict] = []
        all_active = self.repo.list_modules("active")
        if not all_active:
            all_active = self.repo.list_modules("all")

        for m in all_active:
            exam_d = days_until(m["exam_date"]) if m["exam_date"] else None
            if exam_d is not None and exam_d < 0:
                continue  # exam passed
            ects = float(m["ects"]) if m["ects"] else 3.0
            target_h = self.repo.ects_target_hours(m["id"])
            studied_h = self.repo.seconds_studied_for_module(m["id"]) / 3600
            remaining_h = max(0.0, target_h - studied_h)
            # urgency: higher if exam is closer; scale 0.1–1.0
            if exam_d is not None and exam_d <= days_ahead:
                urgency = max(0.1, 1.0 - exam_d / (days_ahead + 1))
            elif exam_d is not None:
                urgency = 0.1
            else:
                urgency = 0.05  # no exam → low urgency but still include

            # Spaced rep topics due for review
            sr_due = 0
            for t in self.repo.list_topics(m["id"]):
                lr = t["last_reviewed"] if "last_reviewed" in t.keys() else ""
                lvl = int(t["knowledge_level"]) if t["knowledge_level"] else 0
                if lr and lvl < 3:
                    try:
                        ds = (today - datetime.fromisoformat(lr).date()).days
                        if ds >= 3:
                            sr_due += 1
                    except Exception:
                        pass

            modules_data.append({
                "id": m["id"],
                "name": m["name"],
                "ects": ects,
                "exam_date": m["exam_date"],
                "exam_days": exam_d,
                "remaining_h": remaining_h,
                "urgency": urgency,
                "sr_due": sr_due,
                "color": mod_color(m["id"]),
            })

        if not modules_data:
            lbl = QLabel("Keine aktiven Module gefunden. Füge zuerst Module hinzu.")
            lbl.setStyleSheet("color:#6B7280;font-size:13px;padding:20px;")
            self.plan_layout.addWidget(lbl)
            return

        # ── Distribute study time per day ─────────────────────────────────────
        # Normalize urgency weights
        total_urgency = sum(m["urgency"] for m in modules_data) or 1.0
        for m in modules_data:
            m["daily_share_h"] = (m["urgency"] / total_urgency) * hours_per_day
            m["daily_share_h"] = round(min(m["daily_share_h"], m["remaining_h"] / max(1, m["exam_days"] or days_ahead), 2.5), 1)
            m["daily_share_h"] = max(m["daily_share_h"], 0.25 if m["remaining_h"] > 0 else 0)

        # ── Render day cards ────────────────────────────────────────────────
        for day_offset in range(days_ahead):
            day_date = today + timedelta(days=day_offset)
            weekday_name = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][day_date.weekday()]
            is_weekend = day_date.weekday() >= 5

            # Day header
            day_frame = QFrame()
            day_frame.setObjectName("Card")
            day_lay = QVBoxLayout(day_frame)
            day_lay.setContentsMargins(14, 10, 14, 10)
            day_lay.setSpacing(4)

            day_hdr = QHBoxLayout()
            date_lbl = QLabel(f"<b>{weekday_name}, {day_date.strftime('%d.%m.')}</b>")
            date_lbl.setTextFormat(Qt.RichText)
            if is_weekend:
                date_lbl.setStyleSheet("color:#10B981;font-size:13px;")
            else:
                date_lbl.setStyleSheet("font-size:13px;")
            day_hdr.addWidget(date_lbl)

            # Check for exams on this day
            exam_today_mods = [m for m in modules_data if m["exam_date"] == day_date.isoformat()]
            if exam_today_mods:
                for em in exam_today_mods:
                    exam_badge = QLabel(f"  🎯 PRÜFUNG: {em['name']}")
                    exam_badge.setStyleSheet("color:#DC2626;font-weight:bold;font-size:13px;")
                    day_hdr.addWidget(exam_badge)

            day_hdr.addStretch()
            total_h_today = sum(m["daily_share_h"] for m in modules_data
                                if m["daily_share_h"] > 0 and not is_weekend)
            if not is_weekend:
                total_lbl = QLabel(f"{total_h_today:.1f}h")
                total_lbl.setStyleSheet("color:#7C3AED;font-weight:bold;font-size:12px;")
                day_hdr.addWidget(total_lbl)
            day_lay.addLayout(day_hdr)

            if is_weekend:
                rest_lbl = QLabel("  🌿  Erholungstag — gönn dir eine Pause!")
                rest_lbl.setStyleSheet("color:#6B7280;font-size:12px;")
                day_lay.addWidget(rest_lbl)
            else:
                # Show tasks per module for this day
                active_modules = [m for m in modules_data if m["daily_share_h"] > 0]
                # Sort by urgency for display
                active_modules = sorted(active_modules, key=lambda x: -x["urgency"])
                for m in active_modules[:3]:  # show top 3 modules
                    task_row = QHBoxLayout()
                    dot = QLabel("●")
                    dot.setStyleSheet(f"color:{m['color']};font-size:10px;")
                    task_row.addWidget(dot)
                    hours_txt = f"{m['daily_share_h']:.1f}h"
                    mod_lbl = QLabel(f"<b>{m['name']}</b>  —  {hours_txt}")
                    mod_lbl.setTextFormat(Qt.RichText)
                    mod_lbl.setStyleSheet("font-size:12px;")
                    task_row.addWidget(mod_lbl, 1)
                    hints = []
                    if m["exam_days"] is not None and m["exam_days"] <= 7:
                        hints.append(f"⚠ Prüfung in {m['exam_days']}d")
                    if m["sr_due"] > 0:
                        hints.append(f"🧠 {m['sr_due']} Wiederholung(en)")
                    if hints:
                        hint_lbl = QLabel("  ".join(hints))
                        hint_lbl.setStyleSheet("color:#D97706;font-size:11px;")
                        task_row.addWidget(hint_lbl)
                    day_lay.addLayout(task_row)

            self.plan_layout.addWidget(day_frame)

        self.plan_layout.addStretch()
