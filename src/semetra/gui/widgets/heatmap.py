"""Week stress heatmap widget and helper functions."""
from __future__ import annotations

import calendar as _c
from datetime import date, timedelta
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt

from semetra.gui.colors import _tc

if TYPE_CHECKING:
    from semetra.repo.sqlite_repo import SqliteRepo


# ── Stress-Heatmap helpers ────────────────────────────────────────────────────

# Stress level → (light-bg, dark-bg, accent-color, label)
_STRESS_PALETTE = {
    0: (_tc("#EEF6EE", "#0D2010"), _tc("#EEF6EE", "#0D2010"), "#2CB67D", "Entspannt"),
    1: (_tc("#FFFBE6", "#2A2400"), _tc("#FFFBE6", "#2A2400"), "#D4A800", "Moderat"),
    2: (_tc("#FFF2E0", "#2A1200"), _tc("#FFF2E0", "#2A1200"), "#E07000", "Erhöht"),
    3: (_tc("#FFECEC", "#2A0808"), _tc("#FFECEC", "#2A0808"), "#CC2222", "Hoch"),
}


def _week_stress_data(repo: SqliteRepo, weeks: int = 12) -> list:
    """Return a list of dicts for the next `weeks` calendar weeks.

    Each dict:
        week_start  date
        week_end    date
        exams       int
        tasks       int
        level       int  0-3
        exam_names  list[str]
    """
    today   = date.today()
    ws0     = today - timedelta(days=today.weekday())   # this Monday

    all_mods  = repo.list_modules("all")
    all_tasks = repo.list_tasks()

    result = []
    for i in range(weeks):
        ws = ws0 + timedelta(weeks=i)
        we = ws + timedelta(days=6)

        # Exams in this week (in-plan modules only)
        exam_names = []
        for m in all_mods:
            ip = int(m["in_plan"] or 1) if "in_plan" in m.keys() and m["in_plan"] is not None else 1
            if not ip:
                continue
            ex = m["exam_date"] or ""
            if not ex:
                continue
            try:
                d = date.fromisoformat(ex[:10])
                if ws <= d <= we:
                    exam_names.append(m["name"])
            except Exception:
                pass
        n_exams = len(exam_names)

        # Open tasks due this week
        n_tasks = 0
        for t in all_tasks:
            if t["status"] == "Done":
                continue
            dd = (t["due_date"] or "")
            if not dd:
                continue
            try:
                d = date.fromisoformat(dd[:10])
                if ws <= d <= we:
                    n_tasks += 1
            except Exception:
                pass

        # Stress level
        if n_exams >= 2:
            level = 3
        elif n_exams == 1:
            level = 2 if n_tasks >= 2 else 2
        elif n_tasks >= 5:
            level = 2
        elif n_tasks >= 2:
            level = 1
        else:
            level = 0

        result.append({
            "week_start": ws,
            "week_end":   we,
            "exams":      n_exams,
            "tasks":      n_tasks,
            "level":      level,
            "exam_names": exam_names,
        })
    return result


class WeekHeatmapWidget(QFrame):
    """Horizontal strip showing study-stress level for the next N weeks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WeekHeatmap")
        self.setStyleSheet(
            f"QFrame#WeekHeatmap{{background:{_tc('#FAFBFF','#1A1A2A')};"
            f"border:1px solid {_tc('#DDE3F0','#2A2A3A')};border-radius:8px;}}"
        )
        self._week_widgets: list = []
        self._build()

    def _build(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(12, 10, 12, 10)
        main.setSpacing(8)

        # ── Header row: title + legend ──────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        title_lbl = QLabel("📊\uFE0F  Wochen-Stresslevel")
        title_lbl.setStyleSheet(
            f"font-size:13px;font-weight:700;"
            f"color:{_tc('#1A1523','#EAE6F4')};"
        )
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        for level, (_, _, fg, label) in _STRESS_PALETTE.items():
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{fg};font-size:11px;padding:0;")
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"font-size:11px;font-weight:600;"
                f"color:{_tc('#6E6882','#8A849C')};padding:0;"
            )
            hdr.addWidget(dot)
            hdr.addWidget(lbl)
            hdr.addSpacing(6)
        main.addLayout(hdr)

        # ── Week blocks row ─────────────────────────────────────────────
        self._weeks_row = QHBoxLayout()
        self._weeks_row.setSpacing(3)
        self._weeks_row.setContentsMargins(0, 0, 0, 0)
        main.addLayout(self._weeks_row)

    def update_data(self, week_data: list):
        """Rebuild the week blocks from fresh data."""
        for w in self._week_widgets:
            w.deleteLater()
        self._week_widgets.clear()
        while self._weeks_row.count():
            self._weeks_row.takeAt(0)

        today = date.today()
        for wd in week_data:
            level = wd["level"]
            _, _, fg, _ = _STRESS_PALETTE[level]
            bg = _tc(
                ["#EEF6EE","#FFFBE6","#FFF2E0","#FFECEC"][level],
                ["#0D2010","#2A2400","#2A1200","#2A0808"][level],
            )
            is_current = wd["week_start"] <= today <= wd["week_end"]
            border = f"2px solid {fg}" if is_current else f"1px solid {fg}55"

            block = QFrame()
            block.setFixedSize(54, 56)
            block.setStyleSheet(
                f"background:{bg};border:{border};border-radius:8px;"
            )
            b_lay = QVBoxLayout(block)
            b_lay.setContentsMargins(3, 4, 3, 4)
            b_lay.setSpacing(1)

            # KW label
            kw = wd["week_start"].isocalendar()[1]
            kw_lbl = QLabel(f"KW{kw}")
            kw_lbl.setAlignment(Qt.AlignCenter)
            kw_lbl.setStyleSheet(
                f"font-size:11px;color:{fg};font-weight:800;background:transparent;"
            )
            b_lay.addWidget(kw_lbl)

            # Icon summary
            icons = ""
            if wd["exams"]:
                icons += f"🎯{wd['exams']}"
            if wd["tasks"]:
                icons += f" ✅{min(wd['tasks'], 9)}{'+'if wd['tasks']>9 else ''}"
            if icons:
                ico = QLabel(icons.strip())
                ico.setAlignment(Qt.AlignCenter)
                ico.setStyleSheet("font-size:10px;background:transparent;")
                b_lay.addWidget(ico)

            # Tooltip
            ws_s = wd["week_start"].strftime("%d.%m")
            we_s = wd["week_end"].strftime("%d.%m")
            tip  = [f"KW {kw}  ({ws_s} – {we_s})"]
            if wd["exams"]:
                names = ", ".join(wd["exam_names"][:3])
                if len(wd["exam_names"]) > 3:
                    names += "…"
                tip.append(f"🎯 {wd['exams']} Prüfung(en): {names}")
            if wd["tasks"]:
                tip.append(f"✅ {wd['tasks']} Aufgabe(n) fällig")
            if not wd["exams"] and not wd["tasks"]:
                tip.append("Keine Termine — freie Woche ✓")
            block.setToolTip("\n".join(tip))

            self._weeks_row.addWidget(block)
            self._week_widgets.append(block)

        self._weeks_row.addStretch()
