"""Sidebar widget and dock for Semetra GUI."""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget, QDockWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QToolButton, QScrollArea, QFrame,
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, Property,
)

from semetra.gui.i18n import tr
from semetra.gui.colors import _tc


# ── Sidebar Dock Title Bar ─────────────────────────────────────────────────
class SidebarDockTitleBar(QWidget):
    """
    Custom title bar for the dockable sidebar.
    Acts as the drag handle for QDockWidget and hosts the pin toggle button.
    """
    pin_toggled = Signal(bool)   # True = pinned (expanded stays)

    def __init__(self, sidebar: "SidebarWidget", parent=None):
        super().__init__(parent)
        self._sidebar = sidebar
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(30)
        self.setStyleSheet(
            "SidebarDockTitleBar{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6D28D9,stop:1 #7C3AED);"
            "border-bottom:1px solid rgba(255,255,255,0.12);"
            "}"
        )
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 3, 8, 3)
        lay.setSpacing(6)

        # Drag-grip indicator
        grip = QLabel("\u22EE\u22EE")   # ⋮⋮
        grip.setStyleSheet("color:rgba(255,255,255,0.45);font-size:13px;letter-spacing:2px;")
        lay.addWidget(grip)

        # App title
        name = QLabel("Semetra")
        name.setStyleSheet("color:white;font-weight:700;font-size:11px;letter-spacing:0.5px;")
        lay.addWidget(name)
        lay.addStretch()

        # Pin / unpin button
        self._pin_btn = QToolButton()
        self._pin_btn.setCheckable(True)
        self._pin_btn.setChecked(True)
        self._pin_btn.setFixedSize(22, 22)
        self._pin_btn.setText("📌")
        self._pin_btn.setToolTip("Sidebar fixieren / ablösen\n"
                                  "Fixiert: Sidebar bleibt geöffnet\n"
                                  "Gelöst: automatisch ein-/ausklappen und verschiebbar")
        self._pin_btn.setStyleSheet(
            "QToolButton{background:transparent;border:none;"
            "font-size:13px;border-radius:4px;}"
            "QToolButton:hover{background:rgba(255,255,255,0.18);}"
            "QToolButton:checked{background:rgba(255,255,255,0.12);opacity:1;}"
            "QToolButton:!checked{opacity:0.55;}"
        )
        self._pin_btn.toggled.connect(self._on_pin_toggled)
        lay.addWidget(self._pin_btn)

    def _on_pin_toggled(self, checked: bool):
        self._sidebar.set_pinned(checked)
        self.pin_toggled.emit(checked)


# ── Sidebar ────────────────────────────────────────────────────────────────
class SidebarWidget(QWidget):
    page_selected = Signal(int)
    coach_clicked = Signal()

    # (emoji, translation_key) — flat list, index = page stack index
    # All emojis have U+FE0F selector for consistent rendering
    NAV_ITEMS = [
        ("🏠\uFE0F", "nav.dashboard"),      # 0
        ("📚\uFE0F", "nav.modules"),        # 1
        ("✅\uFE0F", "nav.tasks"),          # 2
        ("📅\uFE0F", "nav.calendar"),       # 3
        ("🗓\uFE0F", "nav.stundenplan"),    # 4  ← NEW
        ("📊\uFE0F", "nav.timeline"),       # 5
        ("🧠\uFE0F", "nav.knowledge"),      # 6
        ("⏱\uFE0F",  "nav.timer"),         # 7
        ("🎯\uFE0F", "nav.exams"),          # 8
        ("📈\uFE0F", "nav.grades"),         # 9
        ("⚙\uFE0F",  "nav.settings"),      # 10
        ("ℹ\uFE0F",  "nav.credits"),       # 11
    ]

    # Visual groupings: (section_label, [page_indices])
    # Empty label = no section header shown
    _NAV_GROUPS = [
        ("",         [0, 1, 2]),
        ("PLANUNG",  [3, 4, 5]),
        ("WISSEN",   [6, 7, 8]),
        ("ANALYSE",  [9]),
    ]
    _BOTTOM_PAGES = [10, 11]

    EXPANDED_W  = 240   # px — full width
    COLLAPSED_W = 56    # px — icon-only width

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        # CRITICAL: needed on Linux for background-color to render
        self.setAttribute(Qt.WA_StyledBackground, True)
        # Pre-allocate list so _buttons[page_idx] always works
        self._buttons: List[Optional[QPushButton]] = [None] * len(self.NAV_ITEMS)
        self._section_labels: List[QLabel] = []
        self._btn_icons: Dict[int, str] = {}

        # Collapse/expand state
        self._pinned   = True   # pinned = always expanded
        self._expanded = True

        # Delayed collapse timer (avoids flicker when mouse briefly leaves)
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.setInterval(350)
        self._collapse_timer.timeout.connect(self._do_collapse)
        self._anim: Optional[QPropertyAnimation] = None

        self.setMinimumWidth(self.COLLAPSED_W)
        self.setFixedWidth(self.EXPANDED_W)
        self._build()

    # ── Animatable width property ────────────────────────────────────────
    def _get_anim_width(self) -> int:
        return self.width()

    def _set_anim_width(self, v: int) -> None:
        self.setFixedWidth(v)
        # Also resize the parent dock widget so it tracks the animation
        dock = self.parent()
        if dock is not None and isinstance(dock, QDockWidget):
            dock.setFixedWidth(v)

    anim_width = Property(int, _get_anim_width, _set_anim_width)

    # ── Build ────────────────────────────────────────────────────────────
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 18, 12, 14)
        lay.setSpacing(0)

        # ── App Identity ────────────────────────────────────────────────
        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(4, 0, 4, 0)
        logo_row.setSpacing(8)
        self._logo_lbl = QLabel("📖\uFE0F")
        self._logo_lbl.setStyleSheet("font-size: 18px;")
        self._logo_lbl.setFixedWidth(26)
        logo_row.addWidget(self._logo_lbl)

        # Wrap app identity text in a widget so we can show/hide it together
        self._id_col_widget = QWidget()
        self._id_col_widget.setAttribute(Qt.WA_StyledBackground, False)
        id_col = QVBoxLayout(self._id_col_widget)
        id_col.setContentsMargins(0, 0, 0, 0)
        id_col.setSpacing(1)
        title = QLabel("Semetra")
        title.setObjectName("AppTitle")
        ver = QLabel("v2.0  ·  FH Edition")
        ver.setObjectName("AppVersion")
        id_col.addWidget(title)
        id_col.addWidget(ver)
        self._plan_badge = QLabel("Free Plan")
        self._plan_badge.setObjectName("PlanBadge")
        self._plan_badge.setStyleSheet(
            "background:#F3F4F6;color:#6B7280;border-radius:8px;"
            "padding:1px 8px;font-size:10px;font-weight:bold;"
        )
        id_col.addWidget(self._plan_badge)
        logo_row.addWidget(self._id_col_widget)
        logo_row.addStretch()
        lay.addLayout(logo_row)

        lay.addSpacing(14)

        # ── Quick Add Button ─────────────────────────────────────────────
        self._qa_btn = QPushButton("  ＋  Schnell hinzufügen")
        self._qa_btn.setObjectName("QuickAddBtn")
        self._qa_btn.setFixedHeight(40)
        self._qa_btn.setCursor(Qt.PointingHandCursor)
        self._qa_btn.setToolTip("Ctrl+N — Aufgabe oder Thema schnell erfassen")
        self._qa_btn.clicked.connect(self._on_quick_add)
        lay.addWidget(self._qa_btn)

        lay.addSpacing(14)

        # ── Grouped Navigation (scrollable for small windows) ───────────
        self._nav_scroll = QScrollArea()
        self._nav_scroll.setWidgetResizable(True)
        self._nav_scroll.setFrameShape(QFrame.NoFrame)
        self._nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._nav_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 4px; background: transparent; }"
            "QScrollBar::handle:vertical { background: rgba(124,58,237,0.3); border-radius: 2px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        nav_container = QWidget()
        nav_container.setAttribute(Qt.WA_StyledBackground, False)
        nav_lay = QVBoxLayout(nav_container)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(0)

        for section_label, page_indices in self._NAV_GROUPS:
            if section_label:
                nav_lay.addSpacing(6)
                sec_lbl = QLabel(section_label)
                sec_lbl.setObjectName("NavSectionLabel")
                self._section_labels.append(sec_lbl)
                nav_lay.addWidget(sec_lbl)
                nav_lay.addSpacing(2)
            for page_idx in page_indices:
                icon, key = self.NAV_ITEMS[page_idx]
                self._btn_icons[page_idx] = icon
                btn = QPushButton(f"  {icon}  {tr(key)}")
                btn.setObjectName("NavBtn")
                btn.setFixedHeight(42)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda checked, i=page_idx: self._select(i))
                self._buttons[page_idx] = btn
                nav_lay.addWidget(btn)

        nav_lay.addStretch()
        self._nav_scroll.setWidget(nav_container)
        lay.addWidget(self._nav_scroll, 1)  # stretch factor 1 = takes remaining space

        # ── Bottom: Settings + Credits ──────────────────────────────────
        bot_sep = QFrame()
        bot_sep.setFrameShape(QFrame.HLine)
        bot_sep.setStyleSheet(_tc("color: #EAE8F2;", "color: #1E1B2C;"))
        lay.addWidget(bot_sep)
        lay.addSpacing(4)

        for page_idx in self._BOTTOM_PAGES:
            icon, key = self.NAV_ITEMS[page_idx]
            self._btn_icons[page_idx] = icon
            btn = QPushButton(f"  {icon}  {tr(key)}")
            btn.setObjectName("NavBtn")
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=page_idx: self._select(i))
            self._buttons[page_idx] = btn
            lay.addWidget(btn)

        lay.addSpacing(8)

        # ── Coach Button ─────────────────────────────────────────────────
        self._coach_btn = QPushButton("  💬\uFE0F  Studien-Coach  ⭐ Pro")
        self._coach_btn.setObjectName("CoachBtn")
        self._coach_btn.setFixedHeight(42)
        self._coach_btn.setCursor(Qt.PointingHandCursor)
        self._coach_btn.setToolTip("Ctrl+H — KI-Coach öffnen (Semetra Pro)")
        self._coach_btn.clicked.connect(self.coach_clicked.emit)
        lay.addWidget(self._coach_btn)

        self._highlight(0)

    # ── Collapse / Expand ────────────────────────────────────────────────
    def set_pinned(self, pinned: bool):
        """
        Toggle pin state.
        Pinned  = sidebar always stays expanded (current position fixed).
        Unpinned= sidebar collapses when mouse leaves; can be moved via dock.
        """
        self._pinned = pinned
        if pinned and not self._expanded:
            self._do_expand()
        elif not pinned:
            # Start collapsed when first unpinned
            if self._expanded:
                self._collapse_timer.start()

    def enterEvent(self, event):
        """Hover over sidebar — cancel any pending collapse; expand if collapsed."""
        if not self._pinned:
            self._collapse_timer.stop()
            if not self._expanded:
                self._do_expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse left sidebar — schedule collapse when unpinned."""
        if not self._pinned and self._expanded:
            self._collapse_timer.start()
        super().leaveEvent(event)

    def _do_expand(self):
        if self._expanded:
            return
        self._expanded = True
        # First animate width, then show labels after a short delay
        # so text doesn't flash before the width is large enough
        self._animate_width(self.EXPANDED_W)
        QTimer.singleShot(100, lambda: self._set_labels_visible(True))

    def _do_collapse(self):
        if not self._expanded:
            return
        self._expanded = False
        # First hide labels immediately, then animate
        self._set_labels_visible(False)
        self._animate_width(self.COLLAPSED_W)

    def _animate_width(self, target: int):
        if self._anim is not None:
            self._anim.stop()
        self._anim = QPropertyAnimation(self, b"anim_width", self)
        self._anim.setDuration(180)
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def _set_labels_visible(self, visible: bool):
        """Switch between full (expanded) and icon-only (collapsed) display."""
        # App identity text block
        self._id_col_widget.setVisible(visible)
        self._plan_badge.setVisible(visible)
        # Section header labels
        for lbl in self._section_labels:
            lbl.setVisible(visible)
        # Adjust margins for collapsed state (tighter for icon centering)
        lay = self.layout()
        if lay:
            if visible:
                lay.setContentsMargins(12, 18, 12, 14)
            else:
                lay.setContentsMargins(4, 18, 4, 14)
        # Nav + bottom buttons — center icon when collapsed
        for page_idx, btn in enumerate(self._buttons):
            if btn is None:
                continue
            icon = self._btn_icons.get(page_idx, "")
            if visible:
                _, key = self.NAV_ITEMS[page_idx]
                btn.setText(f"  {icon}  {tr(key)}")
                btn.setToolTip("")
                btn.setStyleSheet("")  # reset to default NavBtn style
            else:
                btn.setText(icon)
                _, key = self.NAV_ITEMS[page_idx]
                btn.setToolTip(tr(key))
                btn.setStyleSheet("text-align: center; padding-left: 0; padding-right: 0;")
        # Quick-Add button
        if visible:
            self._qa_btn.setText("  ＋  Schnell hinzufügen")
            self._qa_btn.setToolTip("Ctrl+N — Aufgabe oder Thema schnell erfassen")
            self._qa_btn.setStyleSheet("")
        else:
            self._qa_btn.setText("＋")
            self._qa_btn.setToolTip("Schnell hinzufügen (Ctrl+N)")
            self._qa_btn.setStyleSheet("text-align: center; padding-left: 0; padding-right: 0;")
        # Coach button — save/restore full text
        if not visible:
            self._coach_btn.setProperty("_full_text", self._coach_btn.text())
            self._coach_btn.setText("💬\uFE0F")
            self._coach_btn.setToolTip("KI-Studien-Coach öffnen (Ctrl+H)")
            self._coach_btn.setStyleSheet("text-align: center; padding-left: 0; padding-right: 0;")
        else:
            saved = self._coach_btn.property("_full_text")
            if saved:
                self._coach_btn.setText(saved)
            self._coach_btn.setToolTip("")
            self._coach_btn.setStyleSheet("")

    # ── Internal helpers ─────────────────────────────────────────────────
    def _on_quick_add(self):
        """Delegate to main window's _quick_add if available."""
        win = self.window()
        if hasattr(win, "_quick_add"):
            win._quick_add()

    def _select(self, idx: int):
        self._highlight(idx)
        self.page_selected.emit(idx)

    def _highlight(self, idx: int):
        for i, btn in enumerate(self._buttons):
            if btn is None:
                continue
            active = "true" if i == idx else "false"
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def select(self, idx: int):
        self._highlight(idx)


# ── Sidebar Dock ──────────────────────────────────────────────────────────

class SidebarDock(QDockWidget):
    """
    QDockWidget subclass that:
    - Forwards hover events to the inner SidebarWidget (fixes expand-on-hover when docked)
    - Prevents free floating (only snaps to left/right edges like Windows taskbar)
    - Keeps minimum width = COLLAPSED_W so collapsed dock still receives hover
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(SidebarWidget.COLLAPSED_W)

    def enterEvent(self, event):
        sidebar = self.widget()
        if isinstance(sidebar, SidebarWidget) and not sidebar._pinned:
            sidebar._collapse_timer.stop()
            if not sidebar._expanded:
                sidebar._do_expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        sidebar = self.widget()
        if isinstance(sidebar, SidebarWidget) and not sidebar._pinned and sidebar._expanded:
            sidebar._collapse_timer.start()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        """Keep dock width in sync with inner sidebar animation."""
        sidebar = self.widget()
        if isinstance(sidebar, SidebarWidget):
            w = sidebar.width()
            if w > 0:
                self.setFixedWidth(w)
        super().resizeEvent(event)
