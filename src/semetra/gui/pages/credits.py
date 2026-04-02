"""Credits/About page."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import make_scroll
from semetra.gui.platform import _open_url
from semetra.gui.colors import _tc
from semetra.gui.i18n import tr



class CreditsPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._stat_labels: dict = {}
        self._build()

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _section_title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"font-size:11px;font-weight:700;letter-spacing:2px;"
            f"color:{_tc('#706C86','#6B7280')};text-transform:uppercase;"
            f"margin-bottom:2px;"
        )
        return lbl

    @staticmethod
    def _hsep() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setStyleSheet(f"color:{_tc('#E4E8F0','#2A2A3A')};")
        return f

    def _stat_card(self, key: str, value: str, label: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumWidth(130)
        cly = QVBoxLayout(card)
        cly.setContentsMargins(16, 14, 16, 14)
        cly.setSpacing(2)
        val_lbl = QLabel(value)
        val_lbl.setAlignment(Qt.AlignCenter)
        val_lbl.setStyleSheet("font-size:28px;font-weight:800;color:#4A86E8;")
        lbl_lbl = QLabel(label)
        lbl_lbl.setAlignment(Qt.AlignCenter)
        lbl_lbl.setStyleSheet(f"font-size:11px;color:{_tc('#706C86','#6B7280')};")
        cly.addWidget(val_lbl)
        cly.addWidget(lbl_lbl)
        self._stat_labels[key] = val_lbl
        return card

    @staticmethod
    def _badge(text: str, bg: str, fg: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:12px;"
            f"padding:5px 14px;font-size:12px;font-weight:700;"
        )
        return lbl

    @staticmethod
    def _feature_row(icon: str, title: str, desc: str) -> QFrame:
        row = QFrame()
        row.setObjectName("Card")
        rly = QHBoxLayout(row)
        rly.setContentsMargins(16, 12, 16, 12)
        rly.setSpacing(14)
        ico = QLabel(icon)
        ico.setStyleSheet("font-size:22px;")
        ico.setFixedWidth(32)
        txt_col = QVBoxLayout()
        txt_col.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet(f"font-size:13px;font-weight:700;color:{_tc('#1A1A2E','#CDD6F4')};")
        d = QLabel(desc)
        d.setStyleSheet(f"font-size:11px;color:{_tc('#706C86','#6B7280')};")
        txt_col.addWidget(t)
        txt_col.addWidget(d)
        rly.addWidget(ico)
        rly.addLayout(txt_col, 1)
        return row

    @staticmethod
    def _roadmap_row(icon: str, title: str, tag: str, tag_color: str) -> QFrame:
        row = QFrame()
        row.setObjectName("Card")
        rly = QHBoxLayout(row)
        rly.setContentsMargins(16, 10, 16, 10)
        rly.setSpacing(12)
        ico = QLabel(icon)
        ico.setStyleSheet("font-size:18px;")
        ico.setFixedWidth(28)
        t = QLabel(title)
        t.setStyleSheet(f"font-size:13px;color:{_tc('#1A1A2E','#CDD6F4')};")
        rly.addWidget(ico)
        rly.addWidget(t, 1)
        badge = QLabel(tag)
        badge.setStyleSheet(
            f"background:{tag_color}22;color:{tag_color};border-radius:8px;"
            f"padding:3px 10px;font-size:10px;font-weight:700;"
        )
        rly.addWidget(badge)
        return row

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self):
        page_lay = QVBoxLayout(self)
        page_lay.setContentsMargins(0, 0, 0, 0)
        page_lay.setSpacing(0)

        scroll_w = QWidget()
        scroll_w.setAttribute(Qt.WA_StyledBackground, True)
        page_lay.addWidget(make_scroll(scroll_w))

        outer = QVBoxLayout(scroll_w)
        outer.setContentsMargins(0, 0, 0, 32)
        outer.setSpacing(0)

        # ── Hero header ───────────────────────────────────────────────────────
        hero = QFrame()
        hero.setObjectName("credits_hero")
        hero.setStyleSheet(
            "QFrame#credits_hero{"
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {_tc('#1A3A8A','#0D1B4A')},"
            f"stop:1 {_tc('#2E5FC8','#1A2E7A')});"
            "border:none;}"
        )
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(40, 48, 40, 48)
        hero_lay.setSpacing(10)

        logo = QLabel("📚")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("font-size:56px;background:transparent;")
        hero_lay.addWidget(logo)

        app_name = QLabel("Semetra")
        app_name.setAlignment(Qt.AlignCenter)
        app_name.setStyleSheet(
            "font-size:36px;font-weight:800;color:#FFFFFF;"
            "letter-spacing:3px;background:transparent;"
        )
        hero_lay.addWidget(app_name)

        tagline = QLabel("Dein Studium. Dein Plan. Dein Erfolg.")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet(
            "font-size:14px;color:rgba(255,255,255,0.75);"
            "letter-spacing:1px;background:transparent;"
        )
        hero_lay.addWidget(tagline)

        hero_lay.addSpacing(12)

        # Tech stack badges in hero
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        badge_row.addStretch()
        for tech, bg, fg in [
            ("🐍 Python", "#306998", "#FFD43B"),
            ("⚡ PySide6", "#1A6B3C", "#A6E3A1"),
            ("🗄 SQLite",  "#003B57", "#89CFF0"),
        ]:
            badge_row.addWidget(self._badge(tech, bg, fg))
        badge_row.addStretch()
        hero_lay.addLayout(badge_row)

        outer.addWidget(hero)

        # ── Content wrapper (centered, max-width) ─────────────────────────────
        content_w = QWidget()
        content_w.setMaximumWidth(760)
        content_lay = QVBoxLayout(content_w)
        content_lay.setContentsMargins(32, 32, 32, 0)
        content_lay.setSpacing(28)

        # ── Live stats row ────────────────────────────────────────────────────
        content_lay.addWidget(self._section_title("Deine Daten auf einen Blick"))

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        stats_row.addWidget(self._stat_card("modules",  "–", "Module"))
        stats_row.addWidget(self._stat_card("ects",     "–", "ECTS geplant"))
        stats_row.addWidget(self._stat_card("done",     "–", "Abgeschlossen"))
        stats_row.addWidget(self._stat_card("tasks",    "–", "Offene Aufgaben"))
        content_lay.addLayout(stats_row)

        content_lay.addWidget(self._hsep())

        # ── Creator card ──────────────────────────────────────────────────────
        content_lay.addWidget(self._section_title("Erstellt von"))

        creator = QFrame()
        creator.setObjectName("Card")
        cly = QVBoxLayout(creator)
        cly.setContentsMargins(28, 24, 28, 24)
        cly.setSpacing(6)

        avatar = QLabel("👨‍💻")
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("font-size:40px;")
        cly.addWidget(avatar)

        cname = QLabel("Lopicic Technologies")
        cname.setAlignment(Qt.AlignCenter)
        cname.setStyleSheet(
            "font-size:24px;font-weight:800;"
            f"color:{_tc('#1A1A2E','#CDD6F4')};letter-spacing:1px;"
        )
        cly.addWidget(cname)

        crole = QLabel("Entwickler  ·  Gestalter  ·  FH-Student")
        crole.setAlignment(Qt.AlignCenter)
        crole.setStyleSheet(f"font-size:12px;color:{_tc('#706C86','#6B7280')};")
        cly.addWidget(crole)

        cly.addSpacing(4)
        cemail = QLabel("✉  info@semetra.ch")
        cemail.setAlignment(Qt.AlignCenter)
        cemail.setStyleSheet(f"font-size:12px;color:#4A86E8;")
        cly.addWidget(cemail)

        cwebsite = QLabel("🌐  www.semetra.ch")
        cwebsite.setAlignment(Qt.AlignCenter)
        cwebsite.setStyleSheet(
            "font-size:12px;color:#4A86E8;text-decoration:underline;"
        )
        cwebsite.setCursor(Qt.PointingHandCursor)
        cwebsite.mousePressEvent = lambda _e: _open_url("https://www.semetra.ch")
        cly.addWidget(cwebsite)

        cmission = QLabel(
            "Semetra entstand, weil ich selbst als FH-Student täglich die fehlenden Tools\n"
            "gespürt habe. Kein Chaos, kein Abo-Modell, kein Login — einfach ein Tool,\n"
            "das wirklich funktioniert. 100% offline, 100% in deiner Hand."
        )
        cmission.setAlignment(Qt.AlignCenter)
        cmission.setWordWrap(True)
        cmission.setStyleSheet(
            f"font-size:12px;color:{_tc('#6B7899','#706C86')};"
            f"margin-top:8px;font-style:italic;"
        )
        cly.addWidget(cmission)
        content_lay.addWidget(creator)

        content_lay.addWidget(self._hsep())

        # ── Features ─────────────────────────────────────────────────────────
        content_lay.addWidget(self._section_title("Was Semetra bietet"))

        features = [
            ("📚", "Module & Semester",
             "Vollständige Semester-Roadmap mit ECTS-Tracking und Studienplan"),
            ("✅", "Aufgabenverwaltung",
             "Aufgaben mit Prioritäten, Fälligkeiten und Statusverfolgung"),
            ("📅", "Kalender",
             "Alle Ereignisse, Prüfungen & Aufgaben auf einen Blick"),
            ("🗓", "Stundenplan",
             "Wochenplan mit manuellem Eintrag und PDF/Excel/Bild-Import (Pro)"),
            ("🧠", "Wissens-Map",
             "Lernthemen pro Modul mit Kenntnisniveau 0–5 und Spaced Repetition"),
            ("⏱",  "Pomodoro-Timer",
             "Fokussiertes Lernen mit Zeiterfassung und persönlichen Statistiken"),
            ("🎯", "Prüfungsübersicht",
             "Alle Prüfungstermine, Gewichtungen und automatische Prüfungswarnung"),
            ("📈", "Notenrechner",
             "Gewichtete Noten, Durchschnitt und Ziel-Tracking auf einen Blick"),
            ("🤖", "KI-Studien-Coach",
             "Offline-Assistent mit YouTube-Videos, Lernplänen & Ressourcen (Pro)"),
            ("📄", "PDF-Import",
             "Modulhandbücher und Studienunterlagen automatisch auslesen (Pro)"),
            ("📊", "Studienplan-Generator",
             "Intelligenter Lernplan basierend auf Prüfungen und ECTS (Pro)"),
            ("🏫", "FH-Datenbank",
             "Automatischer Import für FFHS, ZHAW, FHNW, BFH, OST & HES-SO"),
        ]
        feat_col = QVBoxLayout()
        feat_col.setSpacing(6)
        for icon, title, desc in features:
            feat_col.addWidget(self._feature_row(icon, title, desc))
        content_lay.addLayout(feat_col)

        content_lay.addWidget(self._hsep())

        # ── Roadmap ───────────────────────────────────────────────────────────
        content_lay.addWidget(self._section_title("Was als nächstes kommt"))

        roadmap = [
            ("🔄", "Stripe-Zahlung & automatische Lizenzaktivierung", "In Arbeit",    "#FF8C42"),
            ("☁️", "Cloud-Sync (Desktop ↔ Web, via Supabase)",        "Geplant",      "#9B59B6"),
            ("🌐", "Web-App (Browser-Version)",                        "Geplant",      "#9B59B6"),
            ("📱", "Mobile App (iOS & Android)",                       "Langfristig",  "#2CB67D"),
            ("🎓", "Weitere FH-Daten (ZHAW, FHNW, BFH vollständig)",  "Geplant",      "#4A86E8"),
            ("🏪", "Windows Store Release",                            "Geplant",      "#4A86E8"),
        ]
        road_col = QVBoxLayout()
        road_col.setSpacing(6)
        for icon, title, tag, color in roadmap:
            road_col.addWidget(self._roadmap_row(icon, title, tag, color))
        content_lay.addLayout(road_col)

        content_lay.addWidget(self._hsep())

        # ── Pro CTA ───────────────────────────────────────────────────────────
        cta_card = QFrame()
        cta_card.setObjectName("QuoteCard")
        cta_card.setAttribute(Qt.WA_StyledBackground, True)
        cta_lay = QVBoxLayout(cta_card)
        cta_lay.setContentsMargins(28, 24, 28, 24)
        cta_lay.setSpacing(10)
        cta_lbl = QLabel(
            "<b style='font-size:16px;'>⭐ Semetra Pro</b><br><br>"
            "Schalte alle Premium-Funktionen frei:<br>"
            "KI-Coach · PDF-Import · Lernplan-Generator · Prüfungs-Crashplan"
        )
        cta_lbl.setTextFormat(Qt.RichText)
        cta_lbl.setAlignment(Qt.AlignCenter)
        cta_lbl.setWordWrap(True)
        cta_lay.addWidget(cta_lbl)
        pro_btn = QPushButton("⭐  Semetra Pro freischalten")
        pro_btn.setObjectName("PrimaryBtn")
        pro_btn.setFixedHeight(40)
        pro_btn.clicked.connect(
            lambda: _open_url("https://semetra.ch/#pricing"))
        cta_lay.addWidget(pro_btn, alignment=Qt.AlignHCenter)
        content_lay.addWidget(cta_card)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QLabel(
            "\u00a9 2026 Lopicic Technologies  \u00b7  Semetra v2.0  "
            "\u00b7  Made with \u2764\ufe0f for students  \u00b7  semetra.ch"
        )
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet(
            f"font-size:11px;color:{_tc('#706C86','#6B7280')};margin-top:8px;"
        )
        content_lay.addWidget(footer)

        # Center content
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(content_w)
        h.addStretch()
        outer.addLayout(h)

    def refresh(self):
        """Update live stats from DB."""
        all_mods   = self.repo.list_modules("all")
        plan_mods  = [m for m in all_mods
                      if (int(m["in_plan"]) if "in_plan" in m.keys() and m["in_plan"] is not None else 1)]
        total_ects = int(sum(float(m["ects"]) for m in plan_mods))
        completed  = sum(1 for m in plan_mods if m["status"] == "completed")
        open_tasks = len([t for t in self.repo.list_tasks() if t["status"] != "Done"])
        self._stat_labels["modules"].setText(str(len(plan_mods)))
        self._stat_labels["ects"].setText(str(total_ects))
        self._stat_labels["done"].setText(str(completed))
        self._stat_labels["tasks"].setText(str(open_tasks))


