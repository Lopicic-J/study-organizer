"""Main window for Semetra GUI."""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QDockWidget, QComboBox, QFrame, QDialog,
)
from PySide6.QtCore import (
    Qt, QTimer, QEvent, QPoint,
)
from PySide6.QtGui import (
    QKeySequence,
)

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.i18n import tr, set_lang
from semetra.gui.colors import (
    ACCENT_PRESETS, set_accent, set_theme, get_accent_color,
)
from semetra.gui.theme import get_qss, restyle_widgets_accent
from semetra.gui.sidebar import SidebarWidget, SidebarDock, SidebarDockTitleBar

# Import all pages at top level since they're created in __init__
from semetra.gui.pages.dashboard import DashboardPage
from semetra.gui.pages.modules import ModulesPage
from semetra.gui.pages.tasks import TasksPage
from semetra.gui.pages.calendar_page import CalendarPage
from semetra.gui.pages.stundenplan import StundenplanPage
from semetra.gui.pages.study_plan import StudyPlanPage
from semetra.gui.pages.knowledge import KnowledgePage
from semetra.gui.pages.timer import TimerPage
from semetra.gui.pages.exam import ExamPage
from semetra.gui.pages.grades import GradesPage
from semetra.gui.pages.settings import SettingsPage
from semetra.gui.pages.credits import CreditsPage


class SemetraWindow(QMainWindow):

    def __init__(self, repo: SqliteRepo):
        super().__init__()
        self.repo = repo
        self._page_cache = {}  # Cache for lazy-loaded pages
        self.setWindowTitle("Semetra")
        self.setMinimumSize(620, 480)
        self.resize(1280, 860)
        # Restore saved accent before building so get_qss() uses the right palette
        _saved_accent = repo.get_setting("accent_preset") or "violet"
        set_accent(_saved_accent)
        self._build()
        self._apply_theme(repo.get_setting("theme") or "light")
        # Patch every inline setStyleSheet() that hardcodes violet hex values
        # (needed when the saved accent is not violet, since _build() always
        #  uses the hard-coded violet defaults in the Python source)
        _violet = ACCENT_PRESETS["violet"]
        _chosen = ACCENT_PRESETS.get(_saved_accent, _violet)
        restyle_widgets_accent(self, _violet, _chosen)
        self._switch_page(0)
        self._setup_snap_shortcuts()
        self._setup_coach_shortcut()
        self._update_plan_badge()
        # Show onboarding wizard on first launch (no modules yet)
        if not self.repo.list_modules("all"):
            QTimer.singleShot(200, self._show_onboarding)
        # Check for updates silently in background (5 s delay so UI loads first)
        QTimer.singleShot(5000, self._check_for_update)
        # Auto-sync on startup (8 s delay — after update check)
        QTimer.singleShot(8000, self._auto_sync_on_start)

    def _setup_snap_shortcuts(self):
        """
        Keyboard snap shortcuts — reliable alternative to drag-to-edge on WSLg/Wayland.
        Wayland gives the compositor full control over window positioning during drags,
        so moveEvent never fires mid-drag and drag-to-edge cannot be intercepted in Qt.

        Shortcuts:
          Super+Left  / Ctrl+Super+Left  → snap to left half
          Super+Right / Ctrl+Super+Right → snap to right half
          Super+Up                       → maximise
          Super+Down                     → restore
        """
        from PySide6.QtGui import QShortcut
        snap_map = {
            "Meta+Left":        lambda: self._snap("left"),
            "Ctrl+Meta+Left":   lambda: self._snap("left"),
            "Meta+Right":       lambda: self._snap("right"),
            "Ctrl+Meta+Right":  lambda: self._snap("right"),
            "Meta+Up":          self.showMaximized,
            "Meta+Down":        self.showNormal,
        }
        for key, slot in snap_map.items():
            QShortcut(QKeySequence(key), self).activated.connect(slot)
        # ── Global Quick-Add: Ctrl+N ────────────────────────────────────────
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._quick_add)

    def _quick_add(self):
        """Globaler Schnelleintrag (Ctrl+N) — Task oder Thema ohne Seitenwechsel."""
        from semetra.gui.dialogs.quick_add import QuickAddDialog
        dlg = QuickAddDialog(self.repo, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_all()

    def _setup_coach_shortcut(self):
        """Ctrl+H öffnet den Studien-Coach von überall."""
        from PySide6.QtGui import QShortcut
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(self._open_coach_chat)
        self.sidebar.coach_clicked.connect(self._open_coach_chat)

    def _open_coach_chat(self):
        """Öffnet den Studien-Coach als nicht-modales Fenster (Pro only)."""
        from semetra.infra.license import LicenseManager
        from semetra.gui.dialogs.pro_feature import ProFeatureDialog
        from semetra.gui.pages.coach import StudienChatPanel
        lm = LicenseManager(self.repo)
        if not lm.is_pro():
            if ProFeatureDialog("KI-Studien-Coach", self.repo, parent=self).exec() != QDialog.Accepted:
                return
        dlg = StudienChatPanel(self.repo, switch_page_cb=self._switch_page, parent=self)
        dlg.exec()

    def _on_sidebar_pin_toggled(self, pinned: bool):
        """
        Called when the pin button in the sidebar title bar is toggled.
        Pinned  → sidebar is fixed in place, stays expanded, dock cannot be moved.
        Unpinned→ sidebar auto-collapses on mouse leave, can be dragged to any edge.
        """
        if pinned:
            self._sidebar_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
            # Ensure expanded when re-pinned
            if not self.sidebar._expanded:
                self.sidebar._do_expand()
            # Reset dock to expanded width
            self._sidebar_dock.setFixedWidth(SidebarWidget.EXPANDED_W)
        else:
            # Movable between left/right edges only — no free floating
            self._sidebar_dock.setFeatures(QDockWidget.DockWidgetMovable)
            # Immediately collapse when first unpinned
            self.sidebar._do_collapse()

    def _show_onboarding(self):
        """Zeigt den Onboarding-Wizard beim ersten Start (keine Module vorhanden)."""
        from semetra.gui.dialogs.onboarding import OnboardingWizard
        wizard = OnboardingWizard(self.repo, parent=self)
        wizard.finished_setup.connect(self._on_onboarding_done)
        wizard.exec()

    def _on_onboarding_done(self):
        """Nach dem Onboarding alles auffrischen und Dashboard zeigen."""
        self._refresh_all()
        self._switch_page(0)

    def _check_for_update(self):
        """Lädt latest_version.json von semetra.app und zeigt Banner bei neuer Version."""
        try:
            import urllib.request as _ur, json as _json
            from semetra import __version__
            url = "https://semetra.app/latest_version.json"
            req = _ur.Request(url, headers={"User-Agent": f"Semetra/{__version__}"})
            with _ur.urlopen(req, timeout=4) as resp:
                data = _json.loads(resp.read().decode())
            latest = data.get("version", "")
            if not latest:
                return
            # Compare versions: split on "." and compare tuple of ints
            def _v(s):
                try:
                    return tuple(int(x) for x in s.split("."))
                except Exception:
                    return (0,)
            if _v(latest) > _v(__version__):
                download_url = data.get("download_url", "https://semetra.app")
                self._show_update_banner(latest, download_url)
        except Exception:
            pass  # Silently ignore — no network, firewall, or server issues

    def _show_update_banner(self, latest_version: str, download_url: str):
        """Zeigt einen nicht-blockierenden Update-Banner oben im Fenster."""
        banner = QWidget(self)
        banner.setStyleSheet(
            "background:#7C3AED;color:white;border-radius:0px;"
        )
        banner.setAttribute(Qt.WA_StyledBackground, True)
        b_lay = QHBoxLayout(banner)
        b_lay.setContentsMargins(16, 6, 16, 6)
        lbl = QLabel(f"🚀 Semetra {latest_version} ist verfügbar!")
        lbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        b_lay.addWidget(lbl)
        b_lay.addStretch()
        dl_btn = QPushButton("Jetzt herunterladen")
        dl_btn.setStyleSheet(
            "QPushButton{background:white;color:#7C3AED;border:none;"
            "border-radius:6px;padding:4px 14px;font-weight:bold;}"
            "QPushButton:hover{background:#EDE9FE;}"
        )
        import webbrowser as _wb
        dl_btn.clicked.connect(lambda: _wb.open(download_url))
        b_lay.addWidget(dl_btn)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton{background:transparent;color:white;border:none;"
            "font-size:14px;font-weight:bold;}"
        )
        close_btn.clicked.connect(banner.deleteLater)
        b_lay.addWidget(close_btn)
        # Position at the top of the central widget
        central = self.centralWidget()
        banner.setFixedWidth(central.width())
        banner.move(0, 0)
        banner.resize(central.width(), 40)
        banner.show()
        banner.raise_()
        # Resize banner when window resizes
        central.installEventFilter(self)
        self._update_banner = banner

    def eventFilter(self, obj, event):
        """Resize update banner when central widget is resized."""
        if hasattr(self, "_update_banner") and self._update_banner and not self._update_banner.isHidden():
            from PySide6.QtCore import QEvent as _QE
            if event.type() == _QE.Resize:
                self._update_banner.setFixedWidth(obj.width())
        return super().eventFilter(obj, event)

    def _auto_sync_on_start(self):
        """Silently sync on startup if enabled, logged in, and online."""
        auto_sync = self.repo.get_setting("auto_sync") or "1"
        if auto_sync != "1":
            return
        try:
            from semetra.infra.license import LicenseManager
            from semetra.infra.sync import SyncManager
            lm = LicenseManager(self.repo)
            sm = SyncManager(self.repo, lm.account)
            if not sm.can_sync():
                return
            stats = sm.sync_full()
            if stats.get("downloaded", 0) > 0:
                self._refresh_all()
        except Exception:
            pass  # Silent — no error should block app startup

    def _snap(self, side: str):
        """Resize and position the window to fill the left or right screen half."""
        screen = self.screen()
        if not screen:
            return
        sg = screen.availableGeometry()
        half_w = sg.width() // 2
        if side == "left":
            self.setGeometry(sg.x(), sg.y(), half_w, sg.height())
        else:
            self.setGeometry(sg.x() + half_w, sg.y(), half_w, sg.height())

    def mouseDoubleClickEvent(self, event):
        """Double-click anywhere in the window to toggle maximize/restore."""
        if event.button() == Qt.LeftButton:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()
        super().mouseDoubleClickEvent(event)

    def _create_page(self, idx: int):
        """Create a page instance. Called on-demand for lazy loading."""
        pages_map = {
            0: ("dashboard", DashboardPage),
            1: ("modules_page", ModulesPage),
            2: ("tasks_page", TasksPage),
            3: ("calendar_page", CalendarPage),
            4: ("stundenplan_page", StundenplanPage),
            5: ("timeline_page", StudyPlanPage),
            6: ("knowledge_page", KnowledgePage),
            7: ("timer_page", TimerPage),
            8: ("exam_page", ExamPage),
            9: ("grades_page", GradesPage),
            10: ("settings_page", SettingsPage),
            11: ("credits_page", CreditsPage),
        }

        attr_name, page_class = pages_map[idx]
        page = page_class(self.repo)

        # Store as attribute for easy access
        setattr(self, attr_name, page)

        # Setup callbacks and connections
        if hasattr(page, "set_global_refresh"):
            page.set_global_refresh(self._refresh_all)
        if hasattr(page, "set_navigate_cb"):
            page.set_navigate_cb(self._switch_page)

        # Special setup for certain pages
        if attr_name == "settings_page":
            page.theme_changed.connect(self._apply_theme)
            page.lang_changed.connect(self._apply_lang)
            page.accent_changed.connect(self._apply_accent_preset)
        elif attr_name == "timeline_page":
            # Ensure dashboard is loaded first for this reference
            dashboard = self._get_page(0)
            page.set_dashboard(dashboard)

        return page

    def _get_page(self, idx: int):
        """Get or create a page widget lazily. Only Dashboard (0) is created at startup."""
        if idx not in self._page_cache:
            page = self._create_page(idx)
            self._page_cache[idx] = page
            self.stack.addWidget(page)
        return self._page_cache[idx]

    def _build(self):
        # ── Central widget — contains only the page stack ─────────────────
        central = QWidget()
        central.setObjectName("PageContent")
        # CRITICAL: needed on Linux for background-color to render
        central.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(central)

        central_lay = QHBoxLayout(central)
        central_lay.setContentsMargins(0, 0, 0, 0)
        central_lay.setSpacing(0)

        self.stack = QStackedWidget()
        central_lay.addWidget(self.stack)

        # ── Dockable sidebar ─────────────────────────────────────────────
        self.sidebar = SidebarWidget()
        self.sidebar.page_selected.connect(self._switch_page)

        # Title bar (drag handle + pin button)
        self._sidebar_title_bar = SidebarDockTitleBar(self.sidebar)

        self._sidebar_dock = SidebarDock(self)
        self._sidebar_dock.setObjectName("SidebarDock")
        self._sidebar_dock.setTitleBarWidget(self._sidebar_title_bar)
        self._sidebar_dock.setWidget(self.sidebar)
        # Only left and right docking — no free floating (Windows taskbar style)
        self._sidebar_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        # Initial features: not movable when pinned (pin=True by default)
        self._sidebar_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        # When pin is toggled, update dock features
        self._sidebar_title_bar.pin_toggled.connect(self._on_sidebar_pin_toggled)
        self.addDockWidget(Qt.LeftDockWidgetArea, self._sidebar_dock)

        # Lazy load: only Dashboard (0) is created at startup
        # Other pages are created on-demand when the user navigates to them
        self.dashboard = self._get_page(0)

    def _refresh_all(self):
        """Refresh every page so any data change is immediately visible everywhere."""
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "refresh"):
                page.refresh()
        self._update_plan_badge()

    def _update_plan_badge(self):
        """Aktualisiert das Free/Pro-Badge in der Sidebar."""
        try:
            from semetra.infra.license import LicenseManager
            lm = LicenseManager(self.repo)
            if lm.is_pro():
                self.sidebar._plan_badge.setText("⭐ Pro")
                self.sidebar._plan_badge.setStyleSheet(
                    "background:#7C3AED;color:white;border-radius:8px;"
                    "padding:1px 8px;font-size:10px;font-weight:bold;"
                )
                activated_at = self.repo.get_setting("pro_activated_at") or ""
                tip_lines = ["Semetra Pro aktiv"]
                if activated_at:
                    tip_lines.append(f"Aktiviert: {activated_at}")
                tip_lines.append("Lizenz: Unbegrenzt")
                self.sidebar._plan_badge.setToolTip("\n".join(tip_lines))
                # Coach-Button ohne Pro-Hinweis für Pro-User
                self.sidebar._coach_btn.setText("  💬\uFE0F  Studien-Coach")
                self.sidebar._coach_btn.setToolTip("Ctrl+H — KI-Coach öffnen")
            else:
                self.sidebar._plan_badge.setText("Free Plan")
                self.sidebar._plan_badge.setStyleSheet(
                    "background:#F3F4F6;color:#6B7280;border-radius:8px;"
                    "padding:1px 8px;font-size:10px;font-weight:bold;"
                )
                self.sidebar._plan_badge.setToolTip(
                    "Kostenloser Plan aktiv\nUpgrade auf Pro für alle Features"
                )
                self.sidebar._coach_btn.setText("  💬\uFE0F  Studien-Coach  ⭐ Pro")
                self.sidebar._coach_btn.setToolTip(
                    "Ctrl+H — KI-Coach (Semetra Pro erforderlich)"
                )
        except Exception:
            pass

    def _switch_page(self, idx: int):
        # Close any floating combo-box popup before switching pages.
        # On Linux/Wayland the popup is a separate OS window that otherwise
        # stays visible even after the stack switches.
        for combo in self.findChildren(QComboBox):
            combo.hidePopup()
        # Lazy-load the page if it hasn't been created yet
        page = self._get_page(idx)
        self.stack.setCurrentIndex(idx)
        self.sidebar.select(idx)
        if hasattr(page, "refresh"):
            page.refresh()

    def _apply_theme(self, theme: str):
        set_theme(theme)
        # Apply global QSS (covers all QSS-controlled widgets)
        QApplication.instance().setStyleSheet(get_qss(theme))
        # Fix inline QSS styles on persistent sidebar widgets that use _tc()
        sep_color = "#EAE8F2" if theme == "light" else "#1E1B2C"
        for child in self.sidebar.findChildren(QFrame):
            if child.frameShape() in (QFrame.HLine, QFrame.VLine):
                child.setStyleSheet(f"color: {sep_color};")
        # Refresh every page so dynamic/data-driven inline styles re-render
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "refresh"):
                page.refresh()
        # Force full repaint of main window and central widget
        self.update()
        if self.centralWidget():
            self.centralWidget().update()

    def _apply_accent_preset(self, preset: str):
        """Switch accent palette live without changing theme.

        Strategy:
          1. Apply new QSS string (covers all QSS-defined rules).
          2. Refresh pages (redraws data; may regenerate inline styles with
             hardcoded violet values in the Python source).
          3. Walk every widget and swap hardcoded violet hex → new accent in
             all inline setStyleSheet() calls (covers the >100 widgets that use
             hardcoded '#7C3AED' etc. in their individual stylesheets).
        """
        set_accent(preset)
        theme = self.repo.get_setting("theme") or "light"
        QApplication.instance().setStyleSheet(get_qss(theme))
        # Refresh pages so data/labels are current
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "refresh"):
                page.refresh()
        # Patch every inline stylesheet in the whole window:
        # always compare against the violet defaults (what the Python source hardcodes)
        violet  = ACCENT_PRESETS["violet"]
        chosen  = ACCENT_PRESETS.get(preset, violet)
        restyle_widgets_accent(self, violet, chosen)
        self.update()
        if self.centralWidget():
            self.centralWidget().update()

    def _apply_lang(self, lang: str):
        """
        Retranslate navigation buttons immediately.
        Full page translation requires a restart (labels set at build-time).
        """
        set_lang(lang)
        # Update sidebar nav buttons
        expanded = self.sidebar._expanded
        for i, (icon, key) in enumerate(self.sidebar.NAV_ITEMS):
            btn = self.sidebar._buttons[i]
            if btn is not None:
                if expanded:
                    btn.setText(f"  {icon}  {tr(key)}")
                else:
                    btn.setToolTip(tr(key))
        # Update coach button tooltip in sidebar
        self.sidebar._coach_btn.setToolTip(
            "Ctrl+H — " + ("KI-Coach öffnen" if lang == "de" else "Open AI Coach")
        )
        # Refresh all pages (updates dynamic data labels)
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "refresh"):
                page.refresh()
