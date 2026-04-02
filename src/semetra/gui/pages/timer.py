"""Timer/Pomodoro page."""
from __future__ import annotations

import time as _time
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QProgressBar, QMessageBox, QFrame, QCheckBox, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import QComboBox, make_scroll, CircularTimer
from semetra.gui.helpers import mod_color, days_until, fmt_hms
from semetra.gui.i18n import tr
from semetra.gui.colors import _tc



class TimerPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._running = False
        self._total = 25 * 60
        self._remaining = 25 * 60
        self._start_ts: Optional[int] = None
        self._session_count = 0          # total sessions this page-visit
        self._pomodoro_cycle = 0         # 0-3 within current 4-session block
        self._is_break = False           # currently in break phase
        self._qtimer = QTimer(self)
        self._qtimer.setInterval(1000)
        self._qtimer.timeout.connect(self._tick)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 20, 40, 20)
        lay.setSpacing(16)

        title = QLabel(tr("page.timer"))
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        top_row = QHBoxLayout()
        top_row.addStretch()
        self.mod_cb = QComboBox()
        self.mod_cb.setMinimumWidth(220)
        top_row.addWidget(QLabel("Modul:"))
        top_row.addWidget(self.mod_cb)
        top_row.addStretch()
        lay.addLayout(top_row)

        preset_row = QHBoxLayout()
        preset_row.addStretch()
        for label, mins in [("25 min", 25), ("50 min", 50), ("5 min Pause", 5), ("15 min Pause", 15)]:
            btn = QPushButton(label)
            btn.setObjectName("SecondaryBtn")
            btn.clicked.connect(lambda checked, m=mins: self._set_duration(m))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        lay.addLayout(preset_row)

        self.circle = CircularTimer()
        self.circle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.circle, 1, Qt.AlignCenter)

        self.mode_lbl = QLabel("🎯  Fokus-Phase")
        self.mode_lbl.setAlignment(Qt.AlignCenter)
        self.mode_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #7C3AED;")
        lay.addWidget(self.mode_lbl)

        self.session_lbl = QLabel("Sitzungen: 0")
        self.session_lbl.setAlignment(Qt.AlignCenter)
        self.session_lbl.setStyleSheet("color: #6B7280; font-size: 13px;")
        lay.addWidget(self.session_lbl)

        # Pomodoro cycle dots: 🍅🍅🍅🍅
        self.cycle_lbl = QLabel("🍅 ○ ○ ○")
        self.cycle_lbl.setAlignment(Qt.AlignCenter)
        self.cycle_lbl.setStyleSheet("font-size: 18px; letter-spacing: 4px;")
        lay.addWidget(self.cycle_lbl)

        # Auto-Pomodoro toggle
        self.auto_pomo_cb = QCheckBox("  Auto-Pomodoro  (Pause startet automatisch nach Fokus-Phase)")
        self.auto_pomo_cb.setChecked(True)
        lay.addWidget(self.auto_pomo_cb, 0, Qt.AlignCenter)

        ctrl = QHBoxLayout()
        ctrl.addStretch()
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("PrimaryBtn")
        self.start_btn.setMinimumWidth(120)
        self.start_btn.clicked.connect(self._toggle)
        ctrl.addWidget(self.start_btn)
        reset_btn = QPushButton("Reset")
        reset_btn.setObjectName("SecondaryBtn")
        reset_btn.clicked.connect(self._reset)
        ctrl.addWidget(reset_btn)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Notiz zur Sitzung (optional)...")
        lay.addWidget(self.note_edit)

    def refresh(self):
        # Retranslate mode label and session count
        if not self._running and not self._is_break:
            self.mode_lbl.setText(f"🎯  {tr('timer.focus')}")
            self.mode_lbl.setStyleSheet("font-size:16px;font-weight:bold;color:#7C3AED;")
        self.session_lbl.setText(tr("sec.sessions").format(n=self._session_count))
        self.note_edit.setPlaceholderText(tr("timer.note"))
        if not self._running:
            self.start_btn.setText(tr("timer.start"))
        self._update_cycle_display()

        cur = self.mod_cb.currentData()
        self.mod_cb.blockSignals(True)
        self.mod_cb.clear()
        mods = self.repo.list_modules("active")
        if not mods:
            mods = self.repo.list_modules("all")
        for m in mods:
            self.mod_cb.addItem(m["name"], m["id"])
        if cur:
            for i in range(self.mod_cb.count()):
                if self.mod_cb.itemData(i) == cur:
                    self.mod_cb.setCurrentIndex(i)
                    break
        self.mod_cb.blockSignals(False)
        self._update_circle()

    def _set_duration(self, mins: int):
        if self._running:
            return
        self._total = mins * 60
        self._remaining = mins * 60
        if mins <= 15:
            self._is_break = True
            self.mode_lbl.setText(f"🌿  {tr('timer.break')} ({mins} min)")
            self.mode_lbl.setStyleSheet("font-size:16px;font-weight:bold;color:#10B981;")
            self.circle._color = "#10B981"
        else:
            self._is_break = False
            self.mode_lbl.setText(f"🎯  {tr('timer.focus')}")
            self.mode_lbl.setStyleSheet("font-size:16px;font-weight:bold;color:#7C3AED;")
            self.circle._color = "#7C3AED"
        self._update_cycle_display()
        self._update_circle()

    def _toggle(self):
        if self._running:
            self._running = False
            self._qtimer.stop()
            self.start_btn.setText(tr("timer.start"))
        else:
            self._running = True
            if not self._start_ts:
                self._start_ts = int(_time.time())
            self._qtimer.start()
            self.start_btn.setText(tr("timer.stop"))

    def _reset(self):
        self._running = False
        self._qtimer.stop()
        self._remaining = self._total
        self._start_ts = None
        self.start_btn.setText(tr("timer.start"))
        self._update_circle()

    def _tick(self):
        if self._remaining > 0:
            self._remaining -= 1
            self._update_circle()
        else:
            self._qtimer.stop()
            self._running = False
            self._on_complete()

    def _update_circle(self):
        self.circle.set_state(self._remaining, self._total)

    def _update_cycle_display(self):
        """Update the 🍅 cycle indicator dots."""
        dots = []
        for i in range(4):
            if i < self._pomodoro_cycle:
                dots.append("🍅")
            elif i == self._pomodoro_cycle and not self._is_break:
                dots.append("⏳")
            else:
                dots.append("○")
        self.cycle_lbl.setText("  ".join(dots))

    def _on_complete(self):
        was_break = self._is_break
        mid = self.mod_cb.currentData()

        if not was_break:
            # Completed a focus session
            self._session_count += 1
            self.session_lbl.setText(tr("sec.sessions").format(n=self._session_count))
            self._pomodoro_cycle += 1
            if mid and self._start_ts:
                end_ts = int(_time.time())
                note = self.note_edit.text().strip()
                self.repo.add_time_log(mid, self._start_ts, end_ts, self._total, "pomodoro", note)
                self.note_edit.clear()
            self._start_ts = None
            # Lern-Rückblick dialog
            from semetra.gui.dialogs.lern_rueckblick import LernRueckblickDialog
            dlg = LernRueckblickDialog(self.repo, mid, parent=self)
            dlg.exec()
            if self._global_refresh:
                QTimer.singleShot(0, self._global_refresh)

            # Auto-Pomodoro: set up break
            if self.auto_pomo_cb.isChecked():
                long_break = (self._pomodoro_cycle >= 4)
                break_mins = 15 if long_break else 5
                self._is_break = True
                self._total = break_mins * 60
                self._remaining = break_mins * 60
                self.mode_lbl.setText(f"{'☕  Lange Pause' if long_break else '🌿  Kurze Pause'} ({break_mins} min)")
                self.mode_lbl.setStyleSheet("font-size:16px;font-weight:bold;color:#10B981;")
                self.circle._color = "#10B981"
                self._update_circle()
                self._update_cycle_display()
                if long_break:
                    self._pomodoro_cycle = 0
                # Auto-start break
                self._running = True
                self._qtimer.start()
                self.start_btn.setText(tr("timer.stop"))
            else:
                self._remaining = self._total
                self._update_circle()
                self.start_btn.setText(tr("timer.start"))
        else:
            # Completed a break
            self._is_break = False
            self._total = 25 * 60
            self._remaining = 25 * 60
            self._start_ts = None
            self.mode_lbl.setText("🎯  Fokus-Phase")
            self.mode_lbl.setStyleSheet("font-size:16px;font-weight:bold;color:#7C3AED;")
            self.circle._color = "#7C3AED"
            self._update_circle()
            self._update_cycle_display()
            self.start_btn.setText(tr("timer.start"))


