"""Dashboard page — main overview of study progress."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QProgressBar, QScrollArea, QGridLayout, QSizePolicy, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QCheckBox, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import QComboBox, StatCard, make_scroll, ColorDot
from semetra.gui.i18n import tr, greeting, tr_status
from semetra.gui.colors import _tc, _hex_rgba
from semetra.gui.constants import STUDENT_QUOTES
from semetra.gui.helpers import _active_sem_filter, _filter_mods_by_sem, days_until, mod_color

# Import state for theme/accent access
from semetra.gui import state
_THEME = property(lambda _: state._THEME)
_LANG = property(lambda _: state._LANG)



class DashboardPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._global_refresh = None
        self._navigate_cb = None   # set by main window to navigate between pages
        self._build()

    def set_global_refresh(self, cb):
        self._global_refresh = cb

    def set_navigate_cb(self, cb):
        """Register a callback(page_index) to switch to another page."""
        self._navigate_cb = cb

    def _build(self):
        # Wrap everything in a scroll area so content never overlaps on small screens
        _page_lay = QVBoxLayout(self)
        _page_lay.setContentsMargins(0, 0, 0, 0)
        _page_lay.setSpacing(0)
        _scroll_w = QWidget()
        _scroll_w.setAttribute(Qt.WA_StyledBackground, True)
        _page_lay.addWidget(make_scroll(_scroll_w))

        outer = QVBoxLayout(_scroll_w)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(16)

        # ── Semetra Killer Feature Banner ────────────────────────────────────
        self._fh_banner = QFrame()
        self._fh_banner.setObjectName("KillerFeatureBanner")
        self._fh_banner.setAttribute(Qt.WA_StyledBackground, True)
        self._fh_banner.setStyleSheet(
            "QFrame#KillerFeatureBanner{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #7C3AED,stop:1 #6D28D9);"
            "border-radius:12px;}"
        )
        self._fh_banner.setFixedHeight(54)
        fh_banner_lay = QHBoxLayout(self._fh_banner)
        fh_banner_lay.setContentsMargins(20, 0, 20, 0)
        fh_banner_lay.setSpacing(12)
        fh_banner_icon = QLabel("✨")
        fh_banner_icon.setStyleSheet("font-size:20px;")
        fh_banner_lay.addWidget(fh_banner_icon)
        self._fh_banner_lbl = QLabel("Studienplan automatisch generiert aus deiner Fachhochschule")
        self._fh_banner_lbl.setStyleSheet(
            "color:white;font-size:13px;font-weight:bold;"
        )
        fh_banner_lay.addWidget(self._fh_banner_lbl, 1)
        fh_banner_lay.addStretch()
        outer.addWidget(self._fh_banner)

        # ── Header row: greeting + semester selector ─────────────────────
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(12)
        self.greet_lbl = QLabel()
        self.greet_lbl.setObjectName("PageTitle")
        hdr_row.addWidget(self.greet_lbl, 1)

        sem_box = QFrame()
        sem_box.setObjectName("Card")
        sem_box.setAttribute(Qt.WA_StyledBackground, True)
        sem_box_lay = QHBoxLayout(sem_box)
        sem_box_lay.setContentsMargins(12, 6, 12, 6)
        sem_box_lay.setSpacing(6)
        sem_icon = QLabel("🎓")
        sem_icon.setStyleSheet("font-size:16px;")
        sem_box_lay.addWidget(sem_icon)
        sem_lbl_text = QLabel("Semester:")
        sem_lbl_text.setStyleSheet("font-size:12px; color:#7C3AED; font-weight:600;")
        sem_box_lay.addWidget(sem_lbl_text)
        self._sem_cb = QComboBox()
        self._sem_cb.setObjectName("SemesterFilter")
        self._sem_cb.setFixedWidth(175)
        self._sem_cb.setFixedHeight(32)
        self._sem_cb.setCursor(Qt.PointingHandCursor)
        self._sem_cb.setToolTip("Semester-Filter — wirkt auf Module, Aufgaben, Wissen, Prüfungen und Noten")
        self._sem_cb.currentIndexChanged.connect(self._on_sem_changed)
        sem_box_lay.addWidget(self._sem_cb)
        hdr_row.addWidget(sem_box)
        outer.addLayout(hdr_row)

        self.sub_lbl = QLabel()
        self.sub_lbl.setStyleSheet(
            f"color: {_tc('#8A849C','#5C5672')}; font-size: 13px;"
        )
        outer.addWidget(self.sub_lbl)

        # ── Daily motivational quote card ────────────────────────────────────
        self._quote_frame = QFrame()
        self._quote_frame.setObjectName("QuoteCard")
        self._quote_frame.setAttribute(Qt.WA_StyledBackground, True)
        q_lay = QHBoxLayout(self._quote_frame)
        q_lay.setContentsMargins(20, 16, 20, 16)
        q_lay.setSpacing(14)
        quote_icon = QLabel("✨\uFE0F")
        quote_icon.setStyleSheet("font-size:20px;")
        q_lay.addWidget(quote_icon)
        q_inner = QVBoxLayout()
        q_inner.setSpacing(4)
        self._quote_text_lbl = QLabel()
        self._quote_text_lbl.setWordWrap(True)
        self._quote_text_lbl.setStyleSheet(
            f"font-size:13px; font-weight:600;"
            f"color:{_tc('#3B1F7A','#C4B5FD')};"
        )
        self._quote_author_lbl = QLabel()
        self._quote_author_lbl.setStyleSheet(
            f"font-size:11px; color:{_tc('#7C3AED','#8B5CF6')};"
        )
        q_inner.addWidget(self._quote_text_lbl)
        q_inner.addWidget(self._quote_author_lbl)
        q_lay.addLayout(q_inner, 1)
        outer.addWidget(self._quote_frame)

        # ── Streak-Feier card (versteckt, erscheint bei Meilensteinen) ──────
        self._streak_cel_frame = QFrame()
        self._streak_cel_frame.setObjectName("QuoteCard")
        self._streak_cel_frame.setAttribute(Qt.WA_StyledBackground, True)
        sc_lay = QHBoxLayout(self._streak_cel_frame)
        sc_lay.setContentsMargins(20, 14, 20, 14)
        sc_lay.setSpacing(14)
        self._streak_cel_icon = QLabel("🎉\uFE0F")
        self._streak_cel_icon.setStyleSheet("font-size:26px;")
        sc_lay.addWidget(self._streak_cel_icon)
        sc_inner = QVBoxLayout()
        sc_inner.setSpacing(3)
        self._streak_cel_title = QLabel()
        self._streak_cel_title.setStyleSheet(
            f"font-size:15px;font-weight:800;color:{_tc('#3B1F7A','#C4B5FD')};"
        )
        self._streak_cel_sub = QLabel()
        self._streak_cel_sub.setStyleSheet(
            f"font-size:12px;color:{_tc('#7C3AED','#8B5CF6')};"
        )
        sc_inner.addWidget(self._streak_cel_title)
        sc_inner.addWidget(self._streak_cel_sub)
        sc_lay.addLayout(sc_inner, 1)
        self._streak_cel_frame.setVisible(False)
        outer.addWidget(self._streak_cel_frame)

        # ── Was jetzt? — Smarter Tages-Fokus ────────────────────────────────
        self._focus_frame = QFrame()
        self._focus_frame.setObjectName("FocusCard")
        self._focus_frame.setAttribute(Qt.WA_StyledBackground, True)
        # Cap height so it doesn't swallow the whole dashboard; items scroll.
        self._focus_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        focus_main = QVBoxLayout(self._focus_frame)
        focus_main.setContentsMargins(20, 16, 20, 16)
        focus_main.setSpacing(10)
        focus_hdr = QHBoxLayout()
        focus_title_lbl = QLabel("🎯\uFE0F  Was jetzt?")
        focus_title_lbl.setStyleSheet(
            f"font-size:14px;font-weight:800;"
            f"color:{_tc('#1A1523','#EAE6F4')};"
        )
        focus_hdr.addWidget(focus_title_lbl)
        focus_hdr.addStretch()
        self._focus_plan_btn = QPushButton("📅  Lernplan")
        self._focus_plan_btn.setObjectName("SecondaryBtn")
        self._focus_plan_btn.setFixedHeight(30)
        self._focus_plan_btn.clicked.connect(self._open_study_plan_generator)
        focus_hdr.addWidget(self._focus_plan_btn)

        self._notfall_btn = QPushButton("🚨  Notfall")
        self._notfall_btn.setObjectName("DangerBtn")
        self._notfall_btn.setFixedHeight(30)
        self._notfall_btn.clicked.connect(self._open_notfall_modus)
        focus_hdr.addWidget(self._notfall_btn)
        focus_main.addLayout(focus_hdr)

        # Scroll area so long lists don't blow up the card height
        self._focus_scroll = QScrollArea()
        self._focus_scroll.setWidgetResizable(True)
        self._focus_scroll.setFrameShape(QFrame.NoFrame)
        self._focus_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._focus_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._focus_scroll.setMaximumHeight(180)
        self._focus_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        _focus_inner = QWidget()
        _focus_inner.setAttribute(Qt.WA_StyledBackground, False)
        self._focus_items_layout = QVBoxLayout(_focus_inner)
        self._focus_items_layout.setSpacing(4)
        self._focus_items_layout.setContentsMargins(0, 0, 4, 0)
        self._focus_items_layout.addStretch()
        self._focus_scroll.setWidget(_focus_inner)
        focus_main.addWidget(self._focus_scroll)
        outer.addWidget(self._focus_frame)

        # ── Spaced-Rep Warnung (clickable → Wissensseite) ────────────────
        self._spaced_rep_frame = QFrame()
        self._spaced_rep_frame.setObjectName("Card")
        self._spaced_rep_frame.setAttribute(Qt.WA_StyledBackground, True)
        self._spaced_rep_frame.setCursor(Qt.PointingHandCursor)
        self._spaced_rep_frame.setToolTip("Klicken → zur Wissensseite")
        sr_lay = QHBoxLayout(self._spaced_rep_frame)
        sr_lay.setContentsMargins(18, 12, 18, 12)
        sr_lay.setSpacing(14)
        sr_icon = QLabel("🧠\uFE0F")
        sr_icon.setStyleSheet("font-size:20px;")
        sr_lay.addWidget(sr_icon)
        self._sr_lbl = QLabel()
        self._sr_lbl.setWordWrap(True)
        self._sr_lbl.setStyleSheet(
            f"font-size:13px; font-weight:500; color:{_tc('#3B1F7A','#C4B5FD')};"
        )
        sr_lay.addWidget(self._sr_lbl, 1)
        sr_arrow = QLabel("→")
        sr_arrow.setStyleSheet(f"font-size:16px; font-weight:bold; color:{_tc('#7C3AED','#A78BFA')};")
        sr_lay.addWidget(sr_arrow)
        self._spaced_rep_frame.setVisible(False)
        # Install mouse handler to navigate on click
        self._spaced_rep_frame.mousePressEvent = lambda e: (
            self._go_to_knowledge() if e.button() == Qt.LeftButton else None
        )
        outer.addWidget(self._spaced_rep_frame)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self.card_streak  = StatCard("Lernserie",       "0",   "Tage", "#F59E0B")
        self.card_hours   = StatCard("Diese Woche",     "0.0", "h",    "#7C3AED")
        self.card_modules = StatCard("Aktive Module",   "0",   "",     "#10B981")
        self.card_tasks   = StatCard("Offene Aufgaben", "0",   "",     "#F43F5E")
        self.card_sr_due  = StatCard("SR Reviews",      "0",   "fällig", "#FF8C42").make_clickable()
        self.card_sr_due.clicked.connect(self._go_to_knowledge)
        self.card_sr_due.setToolTip("Klicken → zur Wissensseite (SR-Reviews starten)")
        for c in [self.card_streak, self.card_hours, self.card_modules, self.card_tasks, self.card_sr_due]:
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            stats_row.addWidget(c)
        outer.addLayout(stats_row)

        # ── Overall study progress row ───────────────────────────────────────
        prog_row2 = QHBoxLayout()
        prog_row2.setSpacing(14)
        self.card_ects      = StatCard("ECTS Gesamt", "0 / 0", "", "#7C3AED")
        self.card_tasks_pct = StatCard("Aufgaben erledigt", "0%", "", "#10B981")
        self.card_overall   = StatCard("Studienfortschritt", "0%", "", "#A78BFA")
        for c in [self.card_ects, self.card_tasks_pct, self.card_overall]:
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            prog_row2.addWidget(c)
        outer.addLayout(prog_row2)

        # Overall progress bar
        prog_frame = QFrame()
        prog_frame.setObjectName("Card")
        prog_fl = QVBoxLayout(prog_frame)
        prog_fl.setContentsMargins(16, 10, 16, 12)
        prog_fl.setSpacing(6)
        prog_hdr = QHBoxLayout()
        prog_title_lbl = QLabel("Studium Gesamtfortschritt")
        prog_title_lbl.setStyleSheet("font-weight:bold;font-size:13px;")
        prog_hdr.addWidget(prog_title_lbl)
        prog_hdr.addStretch()
        self._overall_pct_lbl = QLabel("0%")
        self._overall_pct_lbl.setStyleSheet("color:#7C3AED;font-weight:bold;font-size:13px;")
        prog_hdr.addWidget(self._overall_pct_lbl)
        prog_fl.addLayout(prog_hdr)
        self._overall_bar = QProgressBar()
        self._overall_bar.setRange(0, 100)
        self._overall_bar.setFixedHeight(10)
        self._overall_bar.setTextVisible(False)
        prog_fl.addWidget(self._overall_bar)
        self._overall_sub = QLabel()
        self._overall_sub.setStyleSheet("color:#6B7280;font-size:11px;")
        prog_fl.addWidget(self._overall_sub)
        outer.addWidget(prog_frame)

        self._exam_section_lbl = QLabel(tr("dash.upcoming_exams"))
        self._exam_section_lbl.setObjectName("SectionTitle")
        outer.addWidget(self._exam_section_lbl)

        self.exam_container = QWidget()
        self.exam_row = QHBoxLayout(self.exam_container)
        self.exam_row.setSpacing(14)
        self.exam_row.setContentsMargins(0, 0, 0, 0)
        self.exam_row.addStretch()
        exam_sa = QScrollArea()
        exam_sa.setWidgetResizable(True)
        exam_sa.setFrameShape(QFrame.NoFrame)
        exam_sa.setFixedHeight(115)
        exam_sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        exam_sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        exam_sa.setWidget(self.exam_container)
        outer.addWidget(exam_sa)

        self._mod_section_lbl = QLabel(tr("sec.progress"))
        self._mod_section_lbl.setObjectName("SectionTitle")
        outer.addWidget(self._mod_section_lbl)

        self.mod_container = QWidget()
        self.mod_grid = QGridLayout(self.mod_container)
        self.mod_grid.setSpacing(12)
        outer.addWidget(self.mod_container)

    def _on_sem_changed(self):
        """Persist selected semester and trigger a global refresh."""
        sem = self._sem_cb.currentData() or ""
        self.repo.set_setting("filter_semester", sem)
        if self._global_refresh:
            QTimer.singleShot(0, self._global_refresh)

    def refresh(self):
        now = datetime.now()
        _day_name = now.strftime("%A")
        _date_str = now.strftime("%d. %B %Y")
        self.greet_lbl.setText(f"{greeting()}, {_day_name} · {_date_str}")

        # ── Update FH banner with saved FH/Studiengang ────────────────────
        fh_name = self.repo.get_setting("fh_name") or ""
        studiengang = self.repo.get_setting("studiengang") or ""
        if fh_name and studiengang:
            self._fh_banner_lbl.setText(
                f"✨  Studienplan automatisch generiert aus {fh_name} · {studiengang}"
            )
        elif fh_name:
            self._fh_banner_lbl.setText(
                f"✨  Studienplan automatisch generiert aus {fh_name}"
            )
        else:
            self._fh_banner_lbl.setText(
                "✨  Studienplan automatisch generiert aus deiner Fachhochschule"
            )

        # ── Populate semester selector (keep current selection) ──────────
        all_mods_raw = self.repo.list_modules("all")
        sems_raw = sorted(
            {str(m["semester"] or "").strip() for m in all_mods_raw if m["semester"]},
            key=lambda s: int(s) if s.isdigit() else 999,
        )
        saved_sem = _active_sem_filter(self.repo)
        self._sem_cb.blockSignals(True)
        self._sem_cb.clear()
        self._sem_cb.addItem("Alle Semester", "")
        for s in sems_raw:
            label = f"{s}. Semester" if s.isdigit() else s
            self._sem_cb.addItem(label, s)
        # Restore saved selection
        for i in range(self._sem_cb.count()):
            if self._sem_cb.itemData(i) == saved_sem:
                self._sem_cb.setCurrentIndex(i)
                break
        self._sem_cb.blockSignals(False)

        # ── Apply semester filter to stat cards ──────────────────────────
        sem_f = saved_sem
        filtered_mods = _filter_mods_by_sem(all_mods_raw, sem_f)
        mod_ids_f = {m["id"] for m in filtered_mods}

        # Daily quote — deterministic by day-of-year so it stays stable during a session
        q_idx = date.today().timetuple().tm_yday % len(STUDENT_QUOTES)
        q_text, q_author = STUDENT_QUOTES[q_idx]
        self._quote_text_lbl.setText("\u201E" + q_text + "\u201C")
        self._quote_author_lbl.setText(f"— {q_author}" if q_author else "")
        self._quote_author_lbl.setVisible(bool(q_author))

        streak = self.repo.get_study_streak()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_secs = self.repo.seconds_studied_week(week_start)
        active_mods = len([m for m in filtered_mods if m["status"] == "active"])
        open_tasks = len([t for t in self.repo.list_tasks(status="Open")
                          if t["module_id"] in mod_ids_f])

        self.card_streak.set_value(str(streak))
        self.card_hours.set_value(f"{week_secs/3600:.1f}")
        self.card_modules.set_value(str(active_mods))
        self.card_tasks.set_value(str(open_tasks))
        _sr_due_now = self.repo.sm2_stats()["due"]
        self.card_sr_due.set_value(str(_sr_due_now))
        self.card_sr_due.setStyleSheet(
            "" if _sr_due_now == 0
            else "border:1px solid #FF8C4288;" if _THEME == "light"
            else "border:1px solid #FF8C4266;"
        )

        # Overall progress stats — filtered by semester, only plan modules
        plan_modules = [m for m in filtered_mods if (int(m["in_plan"]) if "in_plan" in m.keys() and m["in_plan"] is not None else 1)]
        total_ects = sum(float(m["ects"]) for m in plan_modules)
        done_ects  = sum(float(m["ects"]) for m in plan_modules if m["status"] == "completed")
        completed_mods = sum(1 for m in plan_modules if m["status"] == "completed")
        all_tasks  = [t for t in self.repo.list_tasks() if t["module_id"] in mod_ids_f]
        total_tasks = len(all_tasks)
        done_tasks  = sum(1 for t in all_tasks if t["status"] == "Done")
        task_pct = int(done_tasks / total_tasks * 100) if total_tasks > 0 else 0
        overall_pct = int(((done_ects / total_ects) * 0.5 + (done_tasks / total_tasks) * 0.5) * 100) \
                      if (total_ects > 0 and total_tasks > 0) else 0
        self.card_ects.set_value(f"{int(done_ects)} / {int(total_ects)}")
        self.card_tasks_pct.set_value(f"{task_pct}%")
        self.card_overall.set_value(f"{overall_pct}%")
        self._overall_bar.setValue(overall_pct)
        self._overall_pct_lbl.setText(f"{overall_pct}%")
        # Retranslate section labels and stat card titles
        self._exam_section_lbl.setText(tr("dash.upcoming_exams"))
        self._mod_section_lbl.setText(tr("sec.progress"))
        self.card_streak.title_lbl.setText(tr("dash.study_hours").replace("(7d)","").replace("(7j)","").replace("(7T)","").strip() if False else (
            {"de": "Lernserie", "en": "Study Streak", "fr": "Série d'étude", "it": "Sequenza studio"}.get(_LANG, "Lernserie")
        ))
        self.card_hours.title_lbl.setText(tr("dash.study_hours"))
        self.card_modules.title_lbl.setText(tr("dash.modules_active"))
        self.card_tasks.title_lbl.setText(tr("dash.tasks_open"))

        mods_done_txt = {"de": f"{completed_mods}/{len(plan_modules)} Module abgeschlossen",
                         "en": f"{completed_mods}/{len(plan_modules)} modules completed",
                         "fr": f"{completed_mods}/{len(plan_modules)} modules terminés",
                         "it": f"{completed_mods}/{len(plan_modules)} moduli completati"}.get(_LANG, f"{completed_mods}/{len(plan_modules)} modules")
        tasks_done_txt = {"de": f"{done_tasks}/{total_tasks} Aufgaben erledigt",
                          "en": f"{done_tasks}/{total_tasks} tasks done",
                          "fr": f"{done_tasks}/{total_tasks} tâches terminées",
                          "it": f"{done_tasks}/{total_tasks} attività fatte"}.get(_LANG, f"{done_tasks}/{total_tasks} tasks")
        self._overall_sub.setText(f"{mods_done_txt}  ·  {tasks_done_txt}  ·  {int(done_ects)}/{int(total_ects)} ECTS (geplante Module)")

        # ── Streak sub-label ─────────────────────────────────────────────────
        if streak == 0:
            self.sub_lbl.setText("Starte deine Lernserie — jeder Anfang zählt. 🚀")
        elif streak == 1:
            self.sub_lbl.setText("Tag 1 ist der wichtigste — bleib dran! 🌱")
        else:
            self.sub_lbl.setText(f"🔥 {streak} Tage am Ball — du bist auf Kurs!")

        # ── Streak-Feier bei Meilensteinen ───────────────────────────────────
        milestones = {7: ("7 Tage Streak!", "Eine Woche konsequent. Das ist echter Fortschritt! 💪"),
                      14: ("14 Tage Streak!", "Zwei Wochen am Ball — du bist auf einem guten Weg! 🌟"),
                      30: ("30 Tage Streak!", "Ein ganzer Monat. Du bist jetzt ein Profi! 🏆"),
                      60: ("60 Tage Streak!", "Zwei Monate — unglaubliche Ausdauer! 🎖️"),
                      100: ("100 Tage Streak!", "LEGENDÄR. 100 Tage in Folge! 🎊")}
        if streak in milestones:
            title, sub = milestones[streak]
            self._streak_cel_title.setText(title)
            self._streak_cel_sub.setText(sub)
            self._streak_cel_frame.setVisible(True)
        else:
            self._streak_cel_frame.setVisible(False)

        # ── Smarter Tages-Fokus: Was jetzt? ─────────────────────────────────
        # Clear old focus items
        while self._focus_items_layout.count():
            item = self._focus_items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        focus_actions: list[tuple[str, str, str]] = []  # (icon, text, urgency_color)
        today_str = date.today().isoformat()

        # 1. Exams within 3 days → highest urgency
        for m in self.repo.upcoming_exams(within_days=3):
            d = days_until(m["exam_date"])
            if d is not None and d >= 0:
                label = "HEUTE!" if d == 0 else f"in {d} Tag{'en' if d != 1 else ''}"
                focus_actions.append(("🚨", f"Prüfung <b>{m['name']}</b> {label} — alles stehen lassen!", "#DC2626"))

        # 2. Tasks due today (overdue first)
        overdue = [t for t in self.repo.list_tasks(status="Open")
                   if (t["due_date"] or "") < today_str and (t["due_date"] or "") != ""]
        due_today_list = [t for t in self.repo.list_tasks(status="Open")
                          if (t["due_date"] or "") == today_str]
        for t in overdue[:2]:
            focus_actions.append(("⚠️", f"Überfällig: <b>{t['title']}</b>", "#D97706"))
        for t in due_today_list[:2]:
            focus_actions.append(("✅", f"Heute fällig: <b>{t['title']}</b>", "#7C3AED"))

        # 3. Exams within 7 days → prep reminder
        for m in self.repo.upcoming_exams(within_days=7):
            d = days_until(m["exam_date"])
            if d is not None and d >= 4:
                focus_actions.append(("📖", f"Prüfungsvorbereitung: <b>{m['name']}</b> in {d} Tagen", "#D97706"))

        # 3b. Exams within 8-30 days → upcoming exam info
        for m in self.repo.upcoming_exams(within_days=30):
            d = days_until(m["exam_date"])
            if d is not None and d >= 8:
                focus_actions.append(("🎓", f"Prüfung <b>{m['name']}</b> in {d} Tagen — frühzeitig vorbereiten", "#4A86E8"))

        # 4. SM-2 Spaced Repetition — due topics (real algorithm)
        sr_due_all = self.repo.sm2_due_topics()
        sr_due_count = len(sr_due_all)
        if sr_due_count > 0:
            # Group by module
            sr_by_mod: dict = {}
            for t in sr_due_all:
                mn = t["module_name"] if "module_name" in t.keys() else "?"
                sr_by_mod.setdefault(mn, 0)
                sr_by_mod[mn] += 1
            mod_parts = [f"{n}×{mn[:20]}" for mn, n in list(sr_by_mod.items())[:2]]
            mods_str  = ", ".join(mod_parts) + ("…" if len(sr_by_mod) > 2 else "")
            focus_actions.append((
                "🧠",
                f"<b>{sr_due_count} SR-Review{'s' if sr_due_count != 1 else ''}</b> fällig ({mods_str})"
                f" — Wissensseite öffnen",
                "#7C3AED"
            ))

        # 5. Readiness-Score Alarm — module has exam coming up but low readiness
        for m in self.repo.list_modules("all"):
            if not (int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1):
                continue
            if m["status"] == "completed":
                continue
            rs = self.repo.exam_readiness_score(m["id"])
            days_ex = rs["days_until_exam"]
            score   = rs["total"]
            if days_ex is None or days_ex < 0 or days_ex > 45:
                continue
            if not rs["has_data"] and days_ex > 14:
                continue
            # Compute recommended daily minutes
            hrs_target  = rs["hours_target"]
            hrs_studied = rs["hours_studied"]
            remaining_h = max(0.0, hrs_target - hrs_studied)
            if days_ex > 0 and remaining_h > 0:
                daily_min = max(15, min(120, int((remaining_h * 60) / days_ex)))
            else:
                daily_min = 30
            # Show warning for low-readiness urgent modules
            if score < 70 and days_ex <= 30:
                if score < 30:
                    icon_r, col_r = "🔴", "#DC2626"
                elif score < 60:
                    icon_r, col_r = "⚡", "#D97706"
                else:
                    icon_r, col_r = "📈", "#7C3AED"
                mn_short = m["name"][:28]
                focus_actions.append((
                    icon_r,
                    f"<b>{mn_short}</b>: {score}% bereit, Prüfung in {days_ex}d "
                    f"→ heute <b>{daily_min} min</b> empfohlen",
                    col_r
                ))

        # 6. Weekly hours nudge
        if week_secs < 3600:
            focus_actions.append(("⏱", "Diese Woche noch <b>unter 1 Stunde</b> gelernt — starte jetzt!", "#6B7280"))

        if not focus_actions:
            empty_w = QWidget()
            empty_w.setAttribute(Qt.WA_StyledBackground, True)
            empty_w.setStyleSheet(
                "background: transparent; border-radius: 10px;"
            )
            e_lay = QHBoxLayout(empty_w)
            e_lay.setContentsMargins(10, 8, 10, 8)
            e_lay.setSpacing(10)
            e_icon = QLabel("✅\uFE0F")
            e_icon.setStyleSheet("font-size:18px;")
            e_lay.addWidget(e_icon)
            e_txt = QLabel("Alles im Griff — bleib locker und gönn dir eine Pause.")
            e_txt.setStyleSheet(f"color:{_tc('#059669','#34D399')};font-size:13px;font-weight:600;")
            e_lay.addWidget(e_txt, 1)
            self._focus_items_layout.insertWidget(0, empty_w)
        else:
            for i, (icon, text, color) in enumerate(focus_actions[:8]):  # show max 8 items
                # Pill-style row: left accent border + very light tinted bg
                row_w = QWidget()
                row_w.setAttribute(Qt.WA_StyledBackground, True)
                # Use rgba() — Qt 8-digit hex is #AARRGGBB not #RRGGBBAA!
                _bg = _hex_rgba(color, _tc(0.08, 0.13))
                _txt_color = _tc("#1E1033", "#EAE6F4")
                row_w.setStyleSheet(
                    f"background: {_bg};"
                    f"border-radius: 10px;"
                    f"border-left: 3px solid {color};"
                )
                row_l = QHBoxLayout(row_w)
                row_l.setContentsMargins(12, 8, 14, 8)
                row_l.setSpacing(10)
                ico_lbl = QLabel(icon)
                ico_lbl.setStyleSheet("font-size:16px; background: transparent; border: none;")
                ico_lbl.setFixedWidth(24)
                row_l.addWidget(ico_lbl)
                txt_lbl = QLabel(text)
                txt_lbl.setTextFormat(Qt.RichText)
                txt_lbl.setWordWrap(True)
                txt_lbl.setStyleSheet(
                    f"font-size:13px; font-weight:500; background: transparent; border: none;"
                    f"color: {_txt_color};"
                )
                row_l.addWidget(txt_lbl, 1)
                self._focus_items_layout.insertWidget(i, row_w)

        # ── SM-2 Zusammenfassung (Banner) ─────────────────────────────────────
        sr_stats = self.repo.sm2_stats()
        if sr_stats["due"] > 0:
            due_n      = sr_stats["due"]
            sched_n    = sr_stats["scheduled"]
            total_n    = sr_stats["total"]
            self._sr_lbl.setText(
                f"<b>{due_n} SR-Review{'s' if due_n != 1 else ''}</b> fällig "
                f"({sched_n} geplant · {total_n} Topics gesamt). "
                f"Öffne die <b>Wissensseite</b> und starte eine Review-Session."
            )
            self._sr_lbl.setTextFormat(Qt.RichText)
            self._spaced_rep_frame.setVisible(True)
        else:
            self._spaced_rep_frame.setVisible(False)

        # Exam cards
        while self.exam_row.count() > 1:
            item = self.exam_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        exams = self.repo.upcoming_exams(within_days=60)
        if not exams:
            lbl = QLabel(tr("dash.no_exams"))
            lbl.setStyleSheet("color: #706C86; font-size: 13px;")
            self.exam_row.insertWidget(0, lbl)
        else:
            for i, m in enumerate(exams):
                self.exam_row.insertWidget(i, self._make_exam_card(m))

        # Module progress grid
        while self.mod_grid.count():
            item = self.mod_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        modules = self.repo.list_modules("all")
        for idx, m in enumerate(modules):
            row, col = divmod(idx, 3)
            self.mod_grid.addWidget(self._make_module_card(m), row, col)

    def _go_to_knowledge(self):
        """Navigate to the Wissen/Knowledge page (index 5)."""
        if self._navigate_cb:
            self._navigate_cb(5)

    def _open_study_plan_generator(self):
        from semetra.gui.dialogs.study_plan_generator import StudyPlanGeneratorDialog
        dlg = StudyPlanGeneratorDialog(self.repo, parent=self)
        dlg.exec()

    def _open_notfall_modus(self):
        from semetra.gui.dialogs.notfall_modus import NotfallModusDialog
        dlg = NotfallModusDialog(self.repo, parent=self)
        dlg.exec()

    def _make_exam_card(self, m) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedSize(175, 95)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(3)
        color = mod_color(m["id"])
        name_lbl = QLabel(m["name"])
        name_lbl.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {color};")
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl)
        d = days_until(m["exam_date"])
        if d is None:
            d_txt, d_col = "—", "#706C86"
        elif d < 0:
            d_txt, d_col = tr("exam.passed"), "#9E9E9E"
        elif d == 0:
            d_txt, d_col = tr("exam.today").upper() + "!", "#F44336"
        elif d <= 7:
            d_txt, d_col = tr("exam.days_left").format(n=d), "#FF9800"
        else:
            d_txt, d_col = tr("exam.days_left").format(n=d), "#4A86E8"
        days_lbl = QLabel(d_txt)
        days_lbl.setStyleSheet(f"color: {d_col}; font-size: 13px; font-weight: bold;")
        lay.addWidget(days_lbl)
        date_lbl = QLabel(m["exam_date"])
        date_lbl.setStyleSheet("color: #706C86; font-size: 11px;")
        lay.addWidget(date_lbl)
        return card

    def _make_module_card(self, m) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setFixedHeight(95)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)
        color = mod_color(m["id"])

        hdr = QHBoxLayout()
        dot = ColorDot(color, 10)
        hdr.addWidget(dot)
        name_lbl = QLabel(m["name"])
        name_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        hdr.addWidget(name_lbl, 1)
        status_lbl = QLabel(tr_status(m["status"]))
        status_lbl.setStyleSheet("color: #706C86; font-size: 11px;")
        hdr.addWidget(status_lbl)
        lay.addLayout(hdr)

        target = self.repo.ects_target_hours(m["id"])
        studied_h = self.repo.seconds_studied_for_module(m["id"]) / 3600
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setFixedHeight(6)
        bar.setTextVisible(False)
        pct = min(100, int(studied_h / target * 100)) if target > 0 else 0
        bar.setValue(pct)
        bar.setStyleSheet(f"QProgressBar::chunk {{background: {color};border-radius:3px;}}")
        lay.addWidget(bar)

        sub = QLabel(f"{studied_h:.1f}h / {target:.0f}h  |  {m['ects']} ECTS  |  {m['semester']}")
        sub.setStyleSheet("color: #706C86; font-size: 11px;")
        lay.addWidget(sub)
        return card


