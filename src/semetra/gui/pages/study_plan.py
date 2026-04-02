"""Study plan generation and management."""
from __future__ import annotations
import re

from typing import Optional, Dict, List
from datetime import date, datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QLineEdit, QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QSpinBox, QComboBox as _QCBBase,
    QCheckBox, QSizePolicy, QProgressBar, QSplitter, QToolButton, QStackedWidget,
    QGroupBox, QGridLayout, QDoubleSpinBox, QFormLayout, QListWidget, QListWidgetItem,
    QTextEdit,
)
from PySide6.QtCore import Qt, QTimer, Property
from PySide6.QtGui import QColor

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import QComboBox, StatCard, make_scroll, ColorDot
from semetra.gui.i18n import tr, tr_status
from semetra.gui.helpers import mod_color, days_until
from semetra.gui.colors import _tc
from semetra.gui.widgets.helpers import separator



class StudyPlanPage(QWidget):
    """Der Fels in der Brandung – vollständige Studienübersicht mit Semester-Roadmap."""

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._selected_mid: Optional[int] = None
        self._task_filter = "all"
        self._current_detail_task_id: Optional[int] = None
        self._dashboard = None  # set by MainWindow after construction
        self._build()

    def set_dashboard(self, dashboard) -> None:
        """Give StudyPlanPage a reference to DashboardPage for live updates."""
        self._dashboard = dashboard

    def _refresh_dashboard(self) -> None:
        """Refresh the dashboard if a reference is available."""
        if self._dashboard is not None and hasattr(self._dashboard, "refresh"):
            self._dashboard.refresh()

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        # splitter handle colour is set by the global QSS (QSplitter::handle)

        # ── Left: Semester overview ─────────────────────────────────────
        left_w = QWidget()
        left_w.setAttribute(Qt.WA_StyledBackground, True)
        left_w.setMinimumWidth(320)   # keep semester list readable
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(24, 20, 16, 20)
        left_lay.setSpacing(14)

        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Studienplan")
        title.setObjectName("PageTitle")
        title_col.addWidget(title)
        subtitle_lbl = QLabel()
        subtitle_lbl.setObjectName("StudienplanSubtitle")
        subtitle_lbl.setStyleSheet("color:#7C3AED;font-size:12px;font-weight:600;")
        # Will be populated in refresh()
        self._studienplan_subtitle = subtitle_lbl
        title_col.addWidget(subtitle_lbl)
        hdr.addLayout(title_col)
        hdr.addStretch()
        web_import_btn = QPushButton("📄 PDF Import")
        web_import_btn.setObjectName("SecondaryBtn")
        web_import_btn.setFixedHeight(32)
        web_import_btn.setToolTip("Modulplan der FH als PDF importieren")
        web_import_btn.clicked.connect(self._open_web_import)
        web_import_btn.setStyleSheet(
            "QPushButton{font-size:12px;padding:5px 14px;border-radius:9px;}"
        )
        hdr.addWidget(web_import_btn)
        left_lay.addLayout(hdr)

        # Overall stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self.stat_ects = StatCard("ECTS Gesamt", "0 / 0", "", "#4A86E8")
        self.stat_tasks = StatCard("Aufgaben erledigt", "0%", "", "#2CB67D")
        self.stat_mods = StatCard("Module abgeschlossen", "0 / 0", "", "#FF8C42")
        for c in [self.stat_ects, self.stat_tasks, self.stat_mods]:
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            stats_row.addWidget(c)
        left_lay.addLayout(stats_row)

        # Scrollable semester blocks
        self._sem_container = QWidget()
        self._sem_lay = QVBoxLayout(self._sem_container)
        self._sem_lay.setSpacing(12)
        self._sem_lay.setContentsMargins(0, 0, 8, 0)
        left_lay.addWidget(make_scroll(self._sem_container), 1)

        splitter.addWidget(left_w)

        # ── Right: Module + Task detail ──────────────────────────────────
        right_w = QWidget()
        right_w.setAttribute(Qt.WA_StyledBackground, True)
        right_w.setMinimumWidth(180)   # allow narrow resizing
        self._right_lay = QVBoxLayout(right_w)
        self._right_lay.setContentsMargins(16, 20, 24, 20)
        self._right_lay.setSpacing(10)

        self._right_placeholder = QLabel("← Modul auswählen\nfür den Lernplan")
        self._right_placeholder.setAlignment(Qt.AlignCenter)
        self._right_placeholder.setStyleSheet("color:#706C86;font-size:14px;")
        self._right_placeholder.setWordWrap(True)
        self._right_lay.addWidget(self._right_placeholder)

        # Module detail (hidden until selected)
        self._right_detail = QWidget()
        rd_lay = QVBoxLayout(self._right_detail)
        rd_lay.setContentsMargins(0, 0, 0, 0)
        rd_lay.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self._rd_title = QLabel()
        self._rd_title.setStyleSheet("font-size:16px;font-weight:bold;")
        self._rd_title.setWordWrap(True)
        title_row.addWidget(self._rd_title, 1)
        # Compact icon buttons to save horizontal space
        self._rd_plan_btn = QToolButton()
        self._rd_plan_btn.setText("⊘")
        self._rd_plan_btn.setToolTip("Modul ausschließen / einschließen")
        self._rd_plan_btn.setFixedSize(30, 30)
        self._rd_plan_btn.setCursor(Qt.PointingHandCursor)
        self._rd_plan_btn.clicked.connect(self._toggle_plan_from_detail)
        title_row.addWidget(self._rd_plan_btn)
        self._rd_edit_btn = QToolButton()
        self._rd_edit_btn.setText("✏")
        self._rd_edit_btn.setToolTip("Modul bearbeiten")
        self._rd_edit_btn.setFixedSize(30, 30)
        self._rd_edit_btn.setCursor(Qt.PointingHandCursor)
        self._rd_edit_btn.clicked.connect(self._edit_selected_module)
        title_row.addWidget(self._rd_edit_btn)
        rd_lay.addLayout(title_row)

        self._rd_info = QLabel()
        self._rd_info.setStyleSheet("color:#706C86;font-size:12px;")
        rd_lay.addWidget(self._rd_info)

        # ── Readiness Card ─────────────────────────────────────────────────
        self._rd_readiness = QFrame()
        self._rd_readiness.setObjectName("ReadinessCard")
        self._rd_readiness.setStyleSheet(
            f"QFrame#ReadinessCard{{background:{_tc('#F4F7FF','#252535')};"
            f"border:1px solid {_tc('#DDE3F0','#383850')};border-radius:8px;"
            f"padding:0px;}}"
        )
        rc_lay = QHBoxLayout(self._rd_readiness)
        rc_lay.setContentsMargins(10, 8, 10, 8)
        rc_lay.setSpacing(10)

        # Left: big score circle
        self._rc_score_lbl = QLabel("–")
        self._rc_score_lbl.setFixedSize(44, 44)
        self._rc_score_lbl.setAlignment(Qt.AlignCenter)
        self._rc_score_lbl.setStyleSheet(
            "font-size:16px;font-weight:bold;color:#706C86;"
            "background:#E0E4F0;border-radius:22px;border:none;"
        )
        rc_lay.addWidget(self._rc_score_lbl)

        # Middle: label + component breakdown
        rc_mid = QVBoxLayout()
        rc_mid.setSpacing(2)
        rc_title = QLabel("Prüfungsbereitschaft")
        rc_title.setStyleSheet(f"font-size:11px;font-weight:600;color:{_tc('#4A5A8A','#89B4FA')};")
        rc_mid.addWidget(rc_title)
        self._rc_components = QLabel("Noch keine Lerndaten erfasst")
        self._rc_components.setStyleSheet("font-size:10px;color:#706C86;")
        self._rc_components.setWordWrap(True)
        rc_mid.addWidget(self._rc_components)
        rc_lay.addLayout(rc_mid, 1)

        # Right: exam countdown
        self._rc_exam_lbl = QLabel("")
        self._rc_exam_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._rc_exam_lbl.setStyleSheet("font-size:10px;color:#706C86;")
        self._rc_exam_lbl.setWordWrap(True)
        self._rc_exam_lbl.setFixedWidth(70)
        rc_lay.addWidget(self._rc_exam_lbl)

        rd_lay.addWidget(self._rd_readiness)

        prog_row = QHBoxLayout()
        self._rd_bar = QProgressBar()
        self._rd_bar.setFixedHeight(8)
        self._rd_bar.setTextVisible(False)
        prog_row.addWidget(self._rd_bar, 1)
        self._rd_prog_lbl = QLabel("0/0")
        self._rd_prog_lbl.setStyleSheet("color:#706C86;font-size:12px;")
        prog_row.addWidget(self._rd_prog_lbl)
        rd_lay.addLayout(prog_row)

        rd_lay.addWidget(separator())

        # ── Tab buttons ───────────────────────────────────────────────────
        tab_row = QHBoxLayout()
        tab_row.setSpacing(3)
        tab_row.setContentsMargins(0, 0, 0, 0)
        self._tab_btns: Dict[str, QPushButton] = {}
        tab_defs = [
            ("tasks",       "📋 Aufgaben"),
            ("objectives",  "🎯 Lernziele"),
            ("content",     "📚 Lerninhalte"),
            ("exams",       "📝 Prüfungen"),
        ]
        for key, label in tab_defs:
            btn = QPushButton(label)
            btn.setObjectName("SecondaryBtn")
            btn.setFixedHeight(28)
            btn.setMinimumWidth(0)          # allow shrinking
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet(
                "QPushButton{font-size:11px;padding:4px 6px;}"
                "QPushButton:checked{font-weight:bold;}"
            )
            btn.clicked.connect(lambda checked=False, k=key: self._set_right_tab(k))
            tab_row.addWidget(btn)
            self._tab_btns[key] = btn
        rd_lay.addLayout(tab_row)

        # ── Stacked content area ──────────────────────────────────────────
        self._right_stack = QStackedWidget()
        rd_lay.addWidget(self._right_stack, 1)

        # Page 0 – Tasks
        tasks_page = QWidget()
        tp_lay = QVBoxLayout(tasks_page)
        tp_lay.setContentsMargins(0, 0, 0, 0)
        tp_lay.setSpacing(6)

        self._task_list = QListWidget()
        self._task_list.setSpacing(2)
        self._task_list.currentItemChanged.connect(self._on_task_selected)
        tp_lay.addWidget(self._task_list, 1)

        td_grp = QGroupBox("Aufgabe")
        td_lay = QVBoxLayout(td_grp)
        td_lay.setSpacing(6)
        status_row = QHBoxLayout()
        status_row.setSpacing(4)
        self._btn_open = QPushButton("Offen")
        self._btn_ip   = QPushButton("In Arbeit")
        self._btn_done = QPushButton("✓ Erledigt")
        for b in [self._btn_open, self._btn_ip, self._btn_done]:
            b.setObjectName("SecondaryBtn")
            b.setFixedHeight(26)
            status_row.addWidget(b)
        status_row.addStretch()
        self._btn_open.clicked.connect(lambda: self._set_task_status("Open"))
        self._btn_ip.clicked.connect(lambda: self._set_task_status("In Progress"))
        self._btn_done.clicked.connect(lambda: self._set_task_status("Done"))
        td_lay.addLayout(status_row)
        self._task_notes = QTextEdit()
        self._task_notes.setReadOnly(True)
        self._task_notes.setFixedHeight(140)
        td_lay.addWidget(self._task_notes)
        tp_lay.addWidget(td_grp)
        self._right_stack.addWidget(tasks_page)          # index 0

        # ── Helper: build a tab page with a fixed toolbar + scrollable body ──
        def _make_tab_page(add_label, add_slot):
            outer = QWidget()
            outer.setAttribute(Qt.WA_StyledBackground, True)
            vlay = QVBoxLayout(outer)
            vlay.setContentsMargins(0, 4, 0, 0)
            vlay.setSpacing(4)
            tb = QHBoxLayout()
            tb.setSpacing(4)
            add_btn = QPushButton(add_label)
            add_btn.setObjectName("SecondaryBtn")
            add_btn.setFixedHeight(26)
            add_btn.clicked.connect(add_slot)
            tb.addWidget(add_btn)
            imp_btn = QPushButton("📄 PDF importieren")
            imp_btn.setObjectName("SecondaryBtn")
            imp_btn.setFixedHeight(26)
            imp_btn.clicked.connect(self._quick_import)
            tb.addWidget(imp_btn)
            tb.addStretch()
            vlay.addLayout(tb)
            body = QWidget()
            body.setAttribute(Qt.WA_StyledBackground, True)
            body_lay = QVBoxLayout(body)
            body_lay.setContentsMargins(0, 0, 0, 0)
            body_lay.setSpacing(6)
            vlay.addWidget(make_scroll(body), 1)
            return outer, body_lay

        # Page 1 – Objectives (Lernziele)
        _obj_page, self._obj_lay = _make_tab_page(
            "+ Lernziel",
            lambda: self._add_obj_manual(self._selected_mid)
        )
        self._right_stack.addWidget(_obj_page)   # index 1

        # Page 2 – Content sections (Lerninhalte)
        _cont_page, self._cont_lay = _make_tab_page(
            "+ Lerninhalt",
            lambda: self._add_content_manual(self._selected_mid)
        )
        self._right_stack.addWidget(_cont_page)  # index 2

        # Page 3 – Assessments (Prüfungen & Gewichtung)
        _exam_page, self._exam_lay = _make_tab_page(
            "+ Prüfung",
            lambda: self._add_pruefung_manual(self._selected_mid)
        )
        self._right_stack.addWidget(_exam_page)  # index 3

        self._right_detail.hide()
        self._right_lay.addWidget(self._right_detail)

        splitter.addWidget(right_w)
        splitter.setSizes([600, 400])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setCollapsible(0, False)   # left panel never collapses
        splitter.setCollapsible(1, True)    # right panel can fully collapse
        self._splitter = splitter
        outer.addWidget(splitter)

    def _open_web_import(self):
        """Open the Web Import (KI-Scraper) dialog — Pro feature."""
        from semetra.infra.license import LicenseManager
        from semetra.gui.dialogs.pro_feature import ProFeatureDialog
        from semetra.gui.dialogs.web_import import WebImportDialog
        lm = LicenseManager(self.repo)
        if not lm.is_pro():
            if ProFeatureDialog("Web Import", self.repo, parent=self).exec() != QDialog.Accepted:
                return
        dlg = WebImportDialog(self.repo, parent=self)
        if dlg.exec():
            self._update_global_stats()
            self._rebuild_semesters()
            if self._dashboard is not None and hasattr(self._dashboard, "refresh"):
                self._dashboard.refresh()

    def _quick_import(self):
        """Open the Scraping Import dialog directly from the detail panel (Pro only)."""
        from semetra.infra.license import LicenseManager
        from semetra.gui.dialogs.pro_feature import ProFeatureDialog
        from semetra.gui.dialogs.scraping_import import ScrapingImportDialog
        lm = LicenseManager(self.repo)
        if not lm.is_pro():
            if ProFeatureDialog("PDF / Datei Import", self.repo, parent=self).exec() != QDialog.Accepted:
                return
        dlg = ScrapingImportDialog(self.repo, parent=self)
        if dlg.exec():
            self.refresh()

    def _toggle_plan_from_detail(self):
        """Toggle in_plan for the currently selected module from the detail panel."""
        if not self._selected_mid:
            return
        m = self.repo.get_module(self._selected_mid)
        if not m:
            return
        cur = (int(m["in_plan"]) if m["in_plan"] is not None else 1) if "in_plan" in m.keys() else 1
        self.repo.update_module(self._selected_mid, in_plan=(0 if cur else 1))
        self._update_global_stats()
        self._populate_detail(self._selected_mid)
        self._rebuild_semesters()
        self._refresh_dashboard()

    def _edit_selected_module(self):
        """Open the ModuleDialog for the currently selected module."""
        if not self._selected_mid:
            return
        from semetra.gui.dialogs.module_dialog import ModuleDialog
        if ModuleDialog(self.repo, self._selected_mid, parent=self).exec():
            self._populate_detail(self._selected_mid)
            self._rebuild_semesters()
            self._update_global_stats()
            self._refresh_dashboard()

    def _set_right_tab(self, key: str):
        self._task_filter = key
        idx_map = {"tasks": 0, "objectives": 1, "content": 2, "exams": 3}
        self._right_stack.setCurrentIndex(idx_map.get(key, 0))
        # Highlight active tab
        for k, btn in self._tab_btns.items():
            btn.setProperty("active", k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if self._selected_mid:
            self._populate_detail(self._selected_mid)

    def refresh(self):
        self._rebuild_semesters()
        self._update_global_stats()
        if self._selected_mid:
            self._populate_detail(self._selected_mid)
        # Update subtitle with FH/Studiengang from settings
        try:
            fh_name = self.repo.get_setting("fh_name") or ""
            studiengang = self.repo.get_setting("studiengang") or ""
            if fh_name and studiengang:
                self._studienplan_subtitle.setText(
                    f"✨ Automatisch generiert · {fh_name} – {studiengang}"
                )
            elif fh_name:
                self._studienplan_subtitle.setText(
                    f"✨ Automatisch generiert · {fh_name}"
                )
            else:
                self._studienplan_subtitle.setText(
                    "✨ Automatisch generiert aus deiner Fachhochschule"
                )
        except Exception:
            pass

    def _update_global_stats(self):
        modules = self.repo.list_modules("all")
        # Only count modules that are active in the plan
        plan_mods = [m for m in modules if (int(m["in_plan"]) if "in_plan" in m.keys() and m["in_plan"] is not None else 1)]
        total_ects = sum(float(m["ects"]) for m in plan_mods)
        done_ects  = sum(float(m["ects"]) for m in plan_mods if m["status"] == "completed")
        completed  = sum(1 for m in plan_mods if m["status"] == "completed")
        all_tasks  = self.repo.list_tasks()
        done_tasks = sum(1 for t in all_tasks if t["status"] == "Done")
        total_tasks = len(all_tasks)
        pct = int(done_tasks / total_tasks * 100) if total_tasks > 0 else 0
        self.stat_ects.set_value(f"{int(done_ects)} / {int(total_ects)}")
        self.stat_tasks.set_value(f"{pct}%")
        self.stat_mods.set_value(f"{completed} / {len(plan_mods)}")

    def _rebuild_semesters(self):
        while self._sem_lay.count():
            item = self._sem_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                pass

        modules = self.repo.list_modules("all")
        tasks_by_mod: Dict[int, Dict] = {}
        for t in self.repo.list_tasks():
            mid = t["module_id"]
            if mid not in tasks_by_mod:
                tasks_by_mod[mid] = {"total": 0, "done": 0}
            tasks_by_mod[mid]["total"] += 1
            if t["status"] == "Done":
                tasks_by_mod[mid]["done"] += 1

        by_sem: Dict[str, List] = {}
        for m in modules:
            by_sem.setdefault(str(m["semester"]), []).append(m)

        def _sem_sort_key(s: str) -> int:
            return int(s) if s.isdigit() else (999 if s == "" else 998)

        def _sem_display(s: str) -> str:
            if s.isdigit():
                return f"{s}. Semester"
            elif s == "":
                return "Semester (nicht zugeordnet)"
            else:
                # Raw PDF tag like "FS26" – show it, but suggest editing
                return f"Semester  ·  {s}"

        for sem in sorted(by_sem.keys(), key=_sem_sort_key):
            mods = by_sem[sem]
            # Only count active (in-plan) modules for ECTS and progress totals
            active_mods = [m for m in mods if (int(m["in_plan"]) if "in_plan" in m.keys() and m["in_plan"] is not None else 1)]
            sem_ects = sum(float(m["ects"]) for m in active_mods)
            sem_done_ects = sum(float(m["ects"]) for m in active_mods if m["status"] == "completed")
            sem_total = sum(tasks_by_mod.get(m["id"], {}).get("total", 0) for m in active_mods)
            sem_done  = sum(tasks_by_mod.get(m["id"], {}).get("done",  0) for m in active_mods)
            sem_pct = int(sem_done / sem_total * 100) if sem_total > 0 else 0

            # Determine semester status color (based on active modules only)
            all_done = bool(active_mods) and all(m["status"] == "completed" for m in active_mods)
            any_active = any(m["status"] == "active" for m in active_mods)
            sem_color = "#2CB67D" if all_done else ("#4A86E8" if any_active else "#706C86")

            sem_frame = QFrame()
            sem_frame.setObjectName("Card")
            sem_fl = QVBoxLayout(sem_frame)
            sem_fl.setContentsMargins(16, 12, 16, 14)
            sem_fl.setSpacing(8)

            hdr_row = QHBoxLayout()
            sem_indicator = QWidget()
            sem_indicator.setFixedSize(12, 12)
            sem_indicator.setStyleSheet(f"background:{sem_color};border-radius:6px;")
            hdr_row.addWidget(sem_indicator)
            sem_lbl = QLabel(_sem_display(sem))
            sem_lbl.setStyleSheet("font-size:16px;font-weight:bold;")
            hdr_row.addWidget(sem_lbl)
            hdr_row.addStretch()
            ects_lbl = QLabel(f"{int(sem_done_ects)}/{int(sem_ects)} ECTS  |  {sem_pct}% erledigt")
            ects_lbl.setStyleSheet("color:#706C86;font-size:12px;")
            hdr_row.addWidget(ects_lbl)
            sem_fl.addLayout(hdr_row)

            sem_bar = QProgressBar()
            sem_bar.setRange(0, 100)
            sem_bar.setValue(sem_pct)
            sem_bar.setFixedHeight(4)
            sem_bar.setTextVisible(False)
            sem_bar.setStyleSheet(
                f"QProgressBar{{background:{_tc('#E8EDF8','#313244')};border-radius:2px;border:none;}}"
                f"QProgressBar::chunk{{background:{sem_color};border-radius:2px;}}"
            )
            sem_fl.addWidget(sem_bar)

            # Responsive columns: 1 col when the scroll container is narrow
            _avail_w = self._sem_container.width() or 600
            _cols = 1 if _avail_w < 560 else 2
            mod_grid = QGridLayout()
            mod_grid.setSpacing(6)
            for i, m in enumerate(mods):
                card = self._make_mod_card(m, tasks_by_mod.get(m["id"], {}))
                mod_grid.addWidget(card, i // _cols, i % _cols)
            sem_fl.addLayout(mod_grid)

            self._sem_lay.addWidget(sem_frame)

        self._sem_lay.addStretch()

    def _make_mod_card(self, m, task_stats: dict) -> QFrame:
        card = QFrame()
        color = mod_color(m["id"])
        in_plan = int(m["in_plan"]) if "in_plan" in m.keys() else 1
        is_selected = (m["id"] == self._selected_mid)

        # Greyed out style for disabled modules
        if not in_plan:
            color_used = "#AAAAAA"
            bg = _tc("#F0F0F0", "#252535")
            border = f"1.5px solid {_tc('#CCCCCC','#3A3A4A')}"
            hover_bg = _tc("#EBEBEB", "#2E2E40")
        else:
            color_used = color
            border = f"2px solid {color}" if is_selected else f"1.5px solid {_tc('#DDE3F0','#45475A')}"
            bg = _tc("#EEF3FF","#313244") if is_selected else _tc("#F8FAFF","#2A2A3E")
            hover_bg = _tc("#EEF3FF","#313244")

        card.setStyleSheet(f"QFrame{{background:{bg};border:{border};border-radius:10px;}}"
                           f"QFrame:hover{{background:{hover_bg};border:1.5px solid {color_used};}}")
        card.setCursor(Qt.PointingHandCursor)
        card.setFixedHeight(100)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(4)

        mid = m["id"]

        # ── Row 1: name + status badge + plan toggle ──────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        dot = ColorDot(color_used, 9)
        hdr.addWidget(dot)
        name_lbl = QLabel(m["name"])
        name_color = "#999999" if not in_plan else _tc("#1A1A2E","#CDD6F4")
        name_lbl.setStyleSheet(f"font-weight:bold;font-size:13px;color:{name_color};"
                               f"{'text-decoration:line-through;' if not in_plan else ''}")
        name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        hdr.addWidget(name_lbl, 1)

        if in_plan:
            s_colors = {"completed":"#2CB67D","active":"#4A86E8","planned":"#706C86","paused":"#FF8C42"}
            sc = s_colors.get(m["status"], "#9E9E9E")
            badge = QLabel(tr_status(m["status"]))
            badge.setStyleSheet(f"background:{sc};color:white;border-radius:8px;"
                                f"padding:2px 8px;font-size:10px;font-weight:bold;")
            hdr.addWidget(badge)

        # Plan toggle button (⊘ = deactivate, ⊕ = activate)
        toggle_btn = QPushButton("⊘" if in_plan else "⊕")
        toggle_btn.setFixedSize(22, 22)
        toggle_btn.setCursor(Qt.PointingHandCursor)
        if in_plan:
            toggle_btn.setToolTip("Modul aus Studienplan ausschließen")
            toggle_btn.setStyleSheet(
                "QPushButton{background:transparent;color:#BBBBBB;border:none;font-size:14px;}"
                "QPushButton:hover{color:#E05050;}"
            )
        else:
            toggle_btn.setToolTip("Modul in Studienplan aufnehmen")
            toggle_btn.setStyleSheet(
                "QPushButton{background:transparent;color:#2CB67D;border:none;font-size:14px;font-weight:bold;}"
                "QPushButton:hover{color:#1A9A60;}"
            )

        def _toggle_plan(_checked=False, _mid=mid, _cur=in_plan):
            self.repo.update_module(_mid, in_plan=(0 if _cur else 1))
            self._update_global_stats()
            self._rebuild_semesters()
            if self._selected_mid == _mid:
                self._populate_detail(_mid)
            self._refresh_dashboard()

        toggle_btn.clicked.connect(_toggle_plan)
        hdr.addWidget(toggle_btn)
        lay.addLayout(hdr)

        # ── Row 2: semester picker + module type badge ────────────────────
        meta_row = QHBoxLayout()
        meta_row.setSpacing(5)
        meta_row.setContentsMargins(15, 0, 0, 0)

        _sv = str(m["semester"]).strip()
        sem_label = f"📅 {_sv}. Sem." if _sv.isdigit() else "📅 Sem. —"
        sem_btn = QPushButton(sem_label)
        sem_btn.setFixedHeight(20)
        sem_btn.setCursor(Qt.PointingHandCursor)
        sem_btn.setToolTip("Studiensemester setzen")
        sem_btn.setStyleSheet(
            f"QPushButton{{background:{_tc('#EEF3FF','#2A3A5A')};color:{_tc('#3A5A9A','#89B4FA')};"
            f"border-radius:6px;padding:0px 7px;font-size:10px;font-weight:600;"
            f"border:1px solid {_tc('#C8D8F8','#3A5A8A')};}}"
            f"QPushButton:hover{{background:{_tc('#D8E8FF','#354875')};border-color:#4A86E8;}}"
        )

        def _pick_sem(_checked=False, _mid=mid, _btn=sem_btn):
            from PySide6.QtWidgets import QMenu
            from PySide6.QtGui import QCursor
            menu = QMenu(self)
            menu.setStyleSheet(
                f"QMenu{{background:{_tc('#FFFFFF','#1E2030')};color:{_tc('#1A1A2E','#CDD6F4')};"
                f"border:1px solid {_tc('#D0D8F0','#3A4060')};border-radius:6px;padding:4px;}}"
                f"QMenu::item{{padding:6px 20px;border-radius:4px;}}"
                f"QMenu::item:selected{{background:{_tc('#EEF3FF','#2A3A5A')};"
                f"color:{_tc('#3A5A9A','#89B4FA')};}}"
            )
            menu.addAction("— nicht zugeordnet")
            for s in range(1, 10):
                menu.addAction(f"{s}. Semester")
            act = menu.exec(QCursor.pos())
            if act is None:
                return
            txt = act.text()
            new_sem = "" if txt.startswith("—") else txt.split(".")[0].strip()
            self.repo.update_module(_mid, semester=new_sem)
            _btn.setText(f"📅 {new_sem}. Sem." if new_sem else "📅 Sem. —")
            self._rebuild_semesters()

        sem_btn.clicked.connect(_pick_sem)
        meta_row.addWidget(sem_btn)

        _mt = m["module_type"] if "module_type" in m.keys() else "pflicht"
        if in_plan:
            # Light bg / dark fg for light mode; muted dark bg / bright fg for dark mode
            _mt_colors = {
                "pflicht":    (_tc("#E8F0FF","#1E2D4A"), _tc("#3A5A9A","#89B4FA"), "Pflicht"),
                "wahl":       (_tc("#F3E8FF","#2D1A40"), _tc("#7B3FA0","#CBA6F7"), "Wahl"),
                "vertiefung": (_tc("#E8FFF5","#102A20"), _tc("#1A7A5A","#A6E3A1"), "Vertiefung"),
            }
            _bg, _fg, _mt_label = _mt_colors.get(_mt or "pflicht", _mt_colors["pflicht"])
        else:
            _bg = _tc("#EEEEEE", "#2A2A3A")
            _fg = _tc("#AAAAAA", "#6B7280")
            _mt_labels_g = {"pflicht": "Pflicht", "wahl": "Wahl", "vertiefung": "Vertiefung"}
            _mt_label = _mt_labels_g.get(_mt or "pflicht", "Pflicht") + " · nicht gewählt"
        type_badge = QLabel(_mt_label)
        type_badge.setStyleSheet(
            f"background:{_bg};color:{_fg};border-radius:6px;"
            f"padding:2px 7px;font-size:10px;font-weight:600;"
            f"border:1px solid {_bg};"
        )
        meta_row.addWidget(type_badge)
        meta_row.addStretch()
        lay.addLayout(meta_row)

        # ── Row 3: progress bar + ECTS + readiness badge ─────────────────
        total = task_stats.get("total", 0)
        done  = task_stats.get("done", 0)
        pct   = int(done / total * 100) if total > 0 else 0

        bot_row = QHBoxLayout()
        bot_row.setContentsMargins(15, 0, 0, 0)
        bot_row.setSpacing(8)
        prog  = QProgressBar()
        prog.setRange(0, 100)
        prog.setValue(pct)
        prog.setFixedHeight(5)
        prog.setTextVisible(False)
        bar_color = color_used if in_plan else "#CCCCCC"
        prog.setStyleSheet(
            f"QProgressBar{{background:{_tc('#E8EDF8','#313244')};border-radius:2px;border:none;}}"
            f"QProgressBar::chunk{{background:{bar_color};border-radius:2px;}}"
        )
        bot_row.addWidget(prog, 1)
        ects_text = f"{m['ects']} ECTS" if in_plan else f"{m['ects']} ECTS (nicht geplant)"
        sub = QLabel(f"{done}/{total}  ·  {ects_text}")
        sub.setStyleSheet(f"color:{'#CCCCCC' if not in_plan else '#9BA8C0'};font-size:10px;")
        bot_row.addWidget(sub)

        # Readiness badge — only for active in-plan modules
        if in_plan:
            rs = self.repo.exam_readiness_score(mid)
            if rs["has_data"]:
                sc = rs["total"]
                if sc >= 85:
                    rb_bg, rb_fg = "#1A5C3A", "#2CB67D"
                elif sc >= 70:
                    rb_bg, rb_fg = "#3A4A1A", "#A6E028"
                elif sc >= 40:
                    rb_bg, rb_fg = "#5A3A00", "#FF8C42"
                else:
                    rb_bg, rb_fg = "#5A1A1A", "#E05050"
                rb_bg = _tc(rb_fg + "22", rb_bg)
                rb_lbl = QLabel(f"🎯 {sc}%")
                rb_lbl.setStyleSheet(
                    f"background:{rb_bg};color:{rb_fg};border-radius:5px;"
                    f"padding:1px 5px;font-size:9px;font-weight:bold;"
                )
                rb_lbl.setToolTip(
                    f"Prüfungsbereitschaft: {sc}%\n"
                    + (f"Wissen: {rs['topic_score']}%  " if rs['topic_score'] is not None else "")
                    + (f"Stunden: {rs['hours_score']}%  " if rs['hours_score'] is not None else "")
                    + (f"Aufgaben: {rs['task_score']}%" if rs['task_score'] is not None else "")
                )
                bot_row.addWidget(rb_lbl)
            else:
                # No tracking data yet — subtle invite
                rb_lbl = QLabel("📊")
                rb_lbl.setStyleSheet("font-size:11px;")
                rb_lbl.setToolTip("Noch keine Lerndaten — Tracking starten für Prüfungsbereitschafts-Score")
                bot_row.addWidget(rb_lbl)

        lay.addLayout(bot_row)

        card.mousePressEvent = lambda e, _m=mid: self._on_module_click(_m)
        return card

    def _on_module_click(self, mid: int):
        self._selected_mid = mid
        self._populate_detail(mid)
        self._rebuild_semesters()

    def _populate_detail(self, mid: int):
        """Populate the entire right panel for the selected module."""
        m = self.repo.get_module(mid)
        if not m:
            return

        color = mod_color(mid)
        in_plan = int(m["in_plan"]) if "in_plan" in m.keys() else 1
        self._rd_title.setText(m["name"])
        title_color = color if in_plan else "#AAAAAA"
        self._rd_title.setStyleSheet(f"font-size:16px;font-weight:bold;color:{title_color};"
                                     f"{'text-decoration:line-through;' if not in_plan else ''}")
        # Update plan toggle button (compact icon + tooltip)
        if in_plan:
            self._rd_plan_btn.setText("⊘")
            self._rd_plan_btn.setToolTip("Modul aus Studienplan ausschließen")
            self._rd_plan_btn.setStyleSheet(
                "QToolButton{background:#FFF0F0;color:#CC4444;border:1px solid #FFCCCC;"
                "border-radius:6px;font-size:14px;}"
                "QToolButton:hover{background:#FFE0E0;border-color:#CC4444;}"
            )
        else:
            self._rd_plan_btn.setText("⊕")
            self._rd_plan_btn.setToolTip("Modul in Studienplan aufnehmen")
            self._rd_plan_btn.setStyleSheet(
                "QToolButton{background:#F0FFF5;color:#1A7A50;border:1px solid #AADDC0;"
                "border-radius:6px;font-size:14px;}"
                "QToolButton:hover{background:#D0FFE8;border-color:#1A7A50;}"
            )
        _sem_val = m["semester"]
        _sem_str = (f"{_sem_val}. Semester" if str(_sem_val).isdigit()
                    else (_sem_val if _sem_val else "Semester nicht gesetzt"))
        _mt = m["module_type"] if "module_type" in m.keys() else "pflicht"
        _mt_labels = {"pflicht": "Pflichtmodul", "wahl": "Wahlmodul", "vertiefung": "Vertiefungsmodul"}
        _mt_str = _mt_labels.get(_mt or "pflicht", "Pflichtmodul")
        _plan_str = "" if in_plan else "  ·  ⚠ nicht im Studienplan"
        self._rd_info.setText(
            f"{_sem_str}  ·  {m['ects']} ECTS  ·  {_mt_str}  ·  Status: {tr_status(m['status'])}{_plan_str}"
        )

        # ── Readiness Card update ──────────────────────────────────────────
        self._update_readiness_card(mid, in_plan)

        tasks = self.repo.list_tasks(module_id=mid)
        total = len(tasks)
        done  = sum(1 for t in tasks if t["status"] == "Done")
        pct   = int(done / total * 100) if total > 0 else 0
        self._rd_bar.setValue(pct)
        self._rd_bar.setStyleSheet(
            f"QProgressBar{{background:{_tc('#E8EDF8','#313244')};border-radius:4px;border:none;max-height:8px;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:4px;}}"
        )
        self._rd_prog_lbl.setText(f"{done}/{total} erledigt")

        # ── Page 0: Tasks ──────────────────────────────────────────────
        self._task_list.clear()
        for task in tasks:
            is_done = task["status"] == "Done"
            in_prog = task["status"] == "In Progress"
            icon = "✅ " if is_done else ("🔄 " if in_prog else "⬜ ")
            prio_icons = {"Critical": "🔴", "High": "🟠", "Medium": "🔵", "Low": "⚪"}
            p_icon = prio_icons.get(task["priority"], "⚪")
            title_clean = task["title"]
            for prefix in ["[Lernziel] ", "[Prüfung] "]:
                title_clean = title_clean.replace(prefix, "")
            item = QListWidgetItem(f"{icon}{p_icon} {title_clean}")
            item.setData(Qt.UserRole, task["id"])
            if is_done:
                item.setForeground(QColor("#9E9E9E"))
            self._task_list.addItem(item)
        self._task_notes.clear()

        # ── Pages 1-3: Scraped data ────────────────────────────────────
        self._populate_objectives(mid)
        self._populate_content(mid)
        self._populate_exams(mid)

        self._right_placeholder.hide()
        self._right_detail.show()

        # Show the currently-active tab
        idx_map = {"tasks": 0, "objectives": 1, "content": 2, "exams": 3}
        self._right_stack.setCurrentIndex(idx_map.get(self._task_filter, 0))

    # ── Readiness card helper ──────────────────────────────────────────────

    def _update_readiness_card(self, mid: int, in_plan: int):
        """Update the readiness card in the detail panel for module `mid`."""
        if not in_plan:
            self._rd_readiness.hide()
            return
        self._rd_readiness.show()

        rs = self.repo.exam_readiness_score(mid)
        sc = rs["total"]

        # Score circle color
        if not rs["has_data"]:
            circ_bg  = _tc("#E8EDF8", "#2A2A3E")
            circ_fg  = "#706C86"
            score_text = "–"
        elif sc >= 85:
            circ_bg = _tc("#D0F5E8", "#0A2E1E"); circ_fg = "#2CB67D"; score_text = f"{sc}%"
        elif sc >= 70:
            circ_bg = _tc("#E8F5C0", "#1E2E08"); circ_fg = "#7AAF00"; score_text = f"{sc}%"
        elif sc >= 40:
            circ_bg = _tc("#FFE8CC", "#2E1800"); circ_fg = "#E07000"; score_text = f"{sc}%"
        else:
            circ_bg = _tc("#FFD8D8", "#2E0808"); circ_fg = "#CC3333"; score_text = f"{sc}%"

        self._rc_score_lbl.setText(score_text)
        self._rc_score_lbl.setStyleSheet(
            f"font-size:{'14px' if len(score_text)>3 else '16px'};font-weight:bold;"
            f"color:{circ_fg};background:{circ_bg};border-radius:22px;border:none;"
        )

        # Component breakdown text
        parts = []
        if rs["topic_score"] is not None:
            parts.append(f"🧠 Wissen {rs['topic_score']}%")
        elif rs["topic_count"] == 0:
            parts.append("🧠 Keine Topics")
        if rs["hours_score"] is not None:
            parts.append(f"⏱ Stunden {rs['hours_score']}%")
        elif rs["hours_target"] > 0:
            parts.append(f"⏱ 0 / {rs['hours_target']:.0f}h")
        if rs["task_score"] is not None:
            parts.append(f"✅ Aufgaben {rs['task_score']}%")

        if parts:
            self._rc_components.setText("  ·  ".join(parts))
        else:
            self._rc_components.setText("Starte Tracking: Topics erfassen, Pomodoro nutzen, Aufgaben abhaken")

        # Exam countdown
        days = rs["days_until_exam"]
        if days is None:
            self._rc_exam_lbl.setText("")
        elif days < 0:
            self._rc_exam_lbl.setText(f"📅 Vor\n{abs(days)} Tagen")
            self._rc_exam_lbl.setStyleSheet("font-size:10px;color:#706C86;")
        elif days == 0:
            self._rc_exam_lbl.setText("📅 Heute!")
            self._rc_exam_lbl.setStyleSheet("font-size:10px;font-weight:bold;color:#E05050;")
        elif days <= 7:
            self._rc_exam_lbl.setText(f"🔥 {days} Tage")
            self._rc_exam_lbl.setStyleSheet("font-size:10px;font-weight:bold;color:#E05050;")
        elif days <= 30:
            self._rc_exam_lbl.setText(f"⚡ {days} Tage")
            self._rc_exam_lbl.setStyleSheet("font-size:10px;font-weight:600;color:#FF8C42;")
        else:
            self._rc_exam_lbl.setText(f"📅 {days} Tage")
            self._rc_exam_lbl.setStyleSheet("font-size:10px;color:#706C86;")

    # ── Manual entry helpers for objectives / content / exams ─────────────

    def _add_obj_manual(self, mid: int):
        """Manually add a Lernziel (objective) to the selected module."""
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowTitle("Lernziel hinzufügen")
        dlg.setMinimumWidth(380)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Lernziel:"))
        edit = QLineEdit()
        edit.setPlaceholderText("z.B. Kann relationale Datenbanken modellieren")
        lay.addWidget(edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.Accepted and edit.text().strip():
            self.repo.add_scraped_data(mid, "objective", edit.text().strip())
            self._populate_objectives(mid)

    def _add_content_manual(self, mid: int):
        """Manually add a Lerninhalt (content section) to the selected module."""
        import json as _json
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowTitle("Lerninhalt hinzufügen")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        title_edit = QLineEdit()
        title_edit.setPlaceholderText("z.B. Kapitel 3: Datenstrukturen")
        form.addRow("Abschnittstitel:", title_edit)
        items_edit = QTextEdit()
        items_edit.setPlaceholderText("Unterpunkte – einer pro Zeile:\nArrays\nLinked Lists\nStacks & Queues")
        items_edit.setFixedHeight(100)
        form.addRow("Unterpunkte:", items_edit)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            title = title_edit.text().strip()
            if title:
                items = [l.strip() for l in items_edit.toPlainText().splitlines() if l.strip()]
                body = _json.dumps(items, ensure_ascii=False)
                self.repo.add_scraped_data(mid, "content_section", title, body=body)
                self._populate_content(mid)

    def _add_pruefung_manual(self, mid: int):
        """Manually add a Prüfung (assessment) entry to the selected module."""
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowTitle("Prüfung hinzufügen")
        dlg.setMinimumWidth(400)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        form.setSpacing(8)
        title_edit = QLineEdit()
        title_edit.setPlaceholderText("z.B. Schriftliche Abschlussprüfung")
        form.addRow("Prüfungsform:", title_edit)
        weight_spin = QDoubleSpinBox()
        weight_spin.setRange(0, 100)
        weight_spin.setSingleStep(5)
        weight_spin.setSuffix(" %")
        weight_spin.setValue(100)
        form.addRow("Gewichtung:", weight_spin)
        notes_edit = QLineEdit()
        notes_edit.setPlaceholderText("z.B. 90 Min, offene Bücher erlaubt")
        form.addRow("Notizen:", notes_edit)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            title = title_edit.text().strip()
            if title:
                body = notes_edit.text().strip()
                weight = weight_spin.value()
                self.repo.add_scraped_data(mid, "assessment", title,
                                            body=body, weight=weight)
                self._populate_exams(mid)

    # ── Scraped-data populators ────────────────────────────────────────────

    def _clear_layout(self, lay):
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _no_data_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#706C86;font-size:12px;padding:12px;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        return lbl

    def _populate_objectives(self, mid: int):
        self._clear_layout(self._obj_lay)
        rows = self.repo.list_scraped_data(mid, "objective")
        if not rows:
            self._obj_lay.addWidget(self._no_data_label(
                "Keine Lernziele vorhanden.\n"
                "Füge Lernziele manuell hinzu oder importiere den Modulplan der FH als PDF."
            ))
            self._obj_lay.addStretch()
            return

        hdr = QLabel(f"Lernziele  ({len(rows)})")
        hdr.setStyleSheet("font-weight:bold;font-size:13px;")
        self._obj_lay.addWidget(hdr)

        for i, row in enumerate(rows):
            card = QFrame()
            card.setAttribute(Qt.WA_StyledBackground, True)
            card.setStyleSheet(
                f"QFrame{{background:{_tc('#F8FAFF','#2A2A3E')};"
                f"border:1px solid {_tc('#DDE3F0','#45475A')};"
                f"border-radius:8px;padding:4px;}}"
            )
            lay = QHBoxLayout(card)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setSpacing(10)

            num = QLabel(f"{i+1}")
            num.setStyleSheet(
                f"background:{_tc('#4A86E8','#89B4FA')};color:white;"
                f"border-radius:10px;padding:2px 6px;font-size:11px;font-weight:bold;"
            )
            num.setFixedWidth(28)
            num.setAlignment(Qt.AlignCenter)
            lay.addWidget(num)

            txt = QLabel(row["title"])
            txt.setWordWrap(True)
            txt.setStyleSheet("font-size:12px;")
            lay.addWidget(txt, 1)
            self._obj_lay.addWidget(card)

        self._obj_lay.addStretch()

    def _populate_content(self, mid: int):
        self._clear_layout(self._cont_lay)
        rows = self.repo.list_scraped_data(mid, "content_section")
        if not rows:
            self._cont_lay.addWidget(self._no_data_label(
                "Keine Lerninhalte vorhanden.\n"
                "Füge Lerninhalte manuell hinzu oder importiere den Modulplan der FH als PDF."
            ))
            self._cont_lay.addStretch()
            return

        import json as _json
        hdr = QLabel(f"Lerninhalte  ({len(rows)} Abschnitte)")
        hdr.setStyleSheet("font-weight:bold;font-size:13px;")
        self._cont_lay.addWidget(hdr)

        for row in rows:
            # Section header as collapsible-style card
            sec_frame = QFrame()
            sec_frame.setAttribute(Qt.WA_StyledBackground, True)
            sec_frame.setStyleSheet(
                f"QFrame{{background:{_tc('#EEF3FF','#313244')};"
                f"border:1px solid {_tc('#C8D8F8','#45475A')};"
                f"border-radius:8px;}}"
            )
            sec_lay = QVBoxLayout(sec_frame)
            sec_lay.setContentsMargins(12, 8, 12, 8)
            sec_lay.setSpacing(4)

            sec_title = QLabel(f"▸  {row['title']}")
            sec_title.setStyleSheet("font-weight:bold;font-size:12px;")
            sec_lay.addWidget(sec_title)

            # Sub-items from JSON body
            try:
                items = _json.loads(row["body"]) if row["body"] else []
            except Exception:
                items = []
            for item in items:
                item_lbl = QLabel(f"  •  {item}")
                item_lbl.setWordWrap(True)
                item_lbl.setStyleSheet("font-size:11px;color:#5A5F7A;padding-left:8px;")
                sec_lay.addWidget(item_lbl)

            self._cont_lay.addWidget(sec_frame)

        self._cont_lay.addStretch()

    def _populate_exams(self, mid: int):
        self._clear_layout(self._exam_lay)
        rows = self.repo.list_scraped_data(mid, "assessment")
        if not rows:
            self._exam_lay.addWidget(self._no_data_label(
                "Keine Prüfungsdaten vorhanden.\n"
                "Füge Prüfungsinfos manuell hinzu oder importiere den Modulplan der FH als PDF."
            ))
            self._exam_lay.addStretch()
            return

        # Weight sum check
        total_w = sum(float(r["weight"]) for r in rows)
        hdr = QLabel(f"Prüfungen & Gewichtung  ·  Σ {total_w:.0f}%")
        hdr.setStyleSheet("font-weight:bold;font-size:13px;")
        self._exam_lay.addWidget(hdr)

        weight_colors = [(70, "#E74C3C"), (50, "#E67E22"), (30, "#F1C40F"), (0, "#2CB67D")]

        for row in rows:
            w = float(row["weight"])
            wcolor = next((c for threshold, c in weight_colors if w >= threshold), "#706C86")

            card = QFrame()
            card.setAttribute(Qt.WA_StyledBackground, True)
            card.setStyleSheet(
                f"QFrame{{background:{_tc('#F8FAFF','#2A2A3E')};"
                f"border-left:4px solid {wcolor};"
                f"border-top:1px solid {_tc('#DDE3F0','#45475A')};"
                f"border-right:1px solid {_tc('#DDE3F0','#45475A')};"
                f"border-bottom:1px solid {_tc('#DDE3F0','#45475A')};"
                f"border-radius:8px;}}"
            )
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(14, 10, 14, 10)
            c_lay.setSpacing(4)

            # Title row with weight badge
            title_row = QHBoxLayout()
            exam_name = QLabel(row["title"])
            exam_name.setStyleSheet("font-weight:bold;font-size:13px;")
            title_row.addWidget(exam_name, 1)

            if w > 0:
                weight_badge = QLabel(f"{w:.0f}%")
                weight_badge.setStyleSheet(
                    f"background:{wcolor};color:white;border-radius:10px;"
                    f"padding:2px 10px;font-size:12px;font-weight:bold;"
                )
                title_row.addWidget(weight_badge)
            c_lay.addLayout(title_row)

            # Progress bar showing weight
            if w > 0:
                w_bar = QProgressBar()
                w_bar.setRange(0, 100)
                w_bar.setValue(int(w))
                w_bar.setFixedHeight(5)
                w_bar.setTextVisible(False)
                w_bar.setStyleSheet(
                    f"QProgressBar{{background:{_tc('#E8EDF8','#313244')};border-radius:2px;border:none;}}"
                    f"QProgressBar::chunk{{background:{wcolor};border-radius:2px;}}"
                )
                c_lay.addWidget(w_bar)

            # Details from body field
            if row["body"]:
                detail = QLabel(row["body"][:200])
                detail.setWordWrap(True)
                detail.setStyleSheet("font-size:11px;color:#706C86;margin-top:2px;")
                c_lay.addWidget(detail)

            self._exam_lay.addWidget(card)

        self._exam_lay.addStretch()

    def _on_task_selected(self, current, previous):
        if not current:
            return
        tid = current.data(Qt.UserRole)
        if tid is None:
            return
        self._current_detail_task_id = tid
        task = self.repo.get_task(tid)
        if not task:
            return
        notes = task["notes"] or ""
        if notes:
            lines = notes.split("\n")
            html_parts = ['<div style="font-family:sans-serif;font-size:12px;line-height:1.5;">']
            for line in lines:
                line = line.strip()
                if not line:
                    html_parts.append("<br>")
                elif line.startswith("•"):
                    html_parts.append(f'<div style="padding:1px 0 1px 8px;">• {line[1:].strip()}</div>')
                elif line.startswith("📝") or line.startswith("📊"):
                    html_parts.append(f'<div style="color:#4A86E8;font-weight:bold;margin-top:6px;">{line}</div>')
                elif line.startswith("ECTS:"):
                    html_parts.append(f'<div style="color:#706C86;font-size:11px;margin-top:4px;">{line}</div>')
                else:
                    html_parts.append(f'<div>{line}</div>')
            html_parts.append("</div>")
            self._task_notes.setHtml("".join(html_parts))
        else:
            self._task_notes.setPlainText("Keine Notizen vorhanden.")

    def _set_task_status(self, status: str):
        if not self._current_detail_task_id:
            return
        self.repo.update_task(self._current_detail_task_id, status=status)
        if self._selected_mid:
            self._populate_detail(self._selected_mid)
        self._update_global_stats()


