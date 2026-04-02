from __future__ import annotations
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
    QWidget, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, Signal

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.i18n import tr


class OnboardingWizard(QDialog):
    """
    Semetra Onboarding – der WOW-Moment:
    Willkommen → FH auswählen → Studienplan generieren → BOOM!
    """

    finished_setup = Signal()

    def _load_fh_options(self) -> list:
        """Load all FH/Studiengang options from fh_database.json.
        Returns list of (label, studiengang_id, kuerzel) tuples.
        FFHS programs appear first (primary target audience).
        """
        import pathlib
        import json as _json
        db_path = pathlib.Path(__file__).parent.parent / "fh_database.json"
        options = []
        try:
            with open(db_path, encoding="utf-8") as _f:
                db = _json.load(_f)
            for hs in db.get("hochschulen", []):
                kuerzel = hs.get("kuerzel", hs["id"].upper())
                for sg in hs.get("studiengaenge", []):
                    label = f"{kuerzel} – {sg['abschluss']} {sg['name']}"
                    options.append((label, sg["id"], kuerzel))
        except Exception:
            pass
        # FFHS programs first (richest data, primary audience), rest alphabetically by school
        ffhs_opts = [o for o in options if o[2] == "FFHS"]
        other_opts = [o for o in options if o[2] != "FFHS"]
        options = ffhs_opts + other_opts
        options.append(("✏️  Manuell einrichten", "manual", ""))
        return options

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self._repo = repo
        self.setWindowTitle("Willkommen bei Semetra 🎓")
        self.setMinimumSize(560, 560)
        self.resize(600, 600)
        self._page = 0
        self._FH_OPTIONS = self._load_fh_options()
        self._selected_fh = self._FH_OPTIONS[0][1] if self._FH_OPTIONS else "manual"
        self._imported_count = 0
        self._build()
        self._show_page(0)

    def _build(self):
        self._stack = QStackedWidget()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(18)
        lay.addWidget(self._stack, 1)

        # Navigation
        nav = QHBoxLayout()
        self._back_btn = QPushButton("← Zurück")
        self._back_btn.setObjectName("SecondaryBtn")
        self._back_btn.clicked.connect(self._prev)
        nav.addWidget(self._back_btn)
        nav.addStretch()
        self._prog_lbl = QLabel("Schritt 1 von 3")
        self._prog_lbl.setStyleSheet("color:#6B7280;font-size:12px;")
        nav.addWidget(self._prog_lbl)
        nav.addStretch()
        self._next_btn = QPushButton("Weiter →")
        self._next_btn.setObjectName("PrimaryBtn")
        self._next_btn.clicked.connect(self._next)
        nav.addWidget(self._next_btn)
        lay.addLayout(nav)

        # ── Page 0: Welcome ─────────────────────────────────────────────────
        p0 = QWidget()
        p0l = QVBoxLayout(p0)
        p0l.setSpacing(14)
        p0l.addStretch()

        logo_lbl = QLabel("🎓")
        logo_lbl.setStyleSheet("font-size:56px;")
        logo_lbl.setAlignment(Qt.AlignCenter)
        p0l.addWidget(logo_lbl)

        p0_title = QLabel("Dein Studium.\nAutomatisch organisiert.")
        p0_title.setObjectName("PageTitle")
        p0_title.setAlignment(Qt.AlignCenter)
        p0_title.setStyleSheet("font-size:24px;font-weight:bold;line-height:1.3;")
        p0l.addWidget(p0_title)

        p0_pill = QLabel("✨  Studienplan automatisch generiert aus deiner Fachhochschule")
        p0_pill.setAlignment(Qt.AlignCenter)
        p0_pill.setStyleSheet(
            "background:#7C3AED;color:white;border-radius:16px;"
            "padding:8px 18px;font-size:13px;font-weight:bold;"
        )
        p0l.addWidget(p0_pill)

        p0_sub = QLabel(
            "Wähle deine FH – Semetra erstellt deinen\n"
            "vollständigen Studienplan automatisch.\n\n"
            "Kein manuelles Eintippen. Kein leeres Dashboard.\n"
            "Einfach sofort loslegen."
        )
        p0_sub.setAlignment(Qt.AlignCenter)
        p0_sub.setStyleSheet("color:#6B7280;font-size:14px;line-height:1.6;")
        p0_sub.setWordWrap(True)
        p0l.addWidget(p0_sub)
        p0l.addStretch()
        self._stack.addWidget(p0)

        # ── Page 1: FH auswählen ─────────────────────────────────────────────
        p1 = QWidget()
        p1l = QVBoxLayout(p1)
        p1l.setSpacing(10)

        p1_title = QLabel("🏫  Deine Fachhochschule")
        p1_title.setObjectName("PageTitle")
        p1l.addWidget(p1_title)

        p1_sub = QLabel("Wähle Hochschule & Studiengang – Semetra lädt deinen Studienplan automatisch.")
        p1_sub.setStyleSheet("color:#6B7280;font-size:13px;")
        p1_sub.setWordWrap(True)
        p1l.addWidget(p1_sub)

        # Scrollable list of FH options
        fh_scroll = QScrollArea()
        fh_scroll.setFrameShape(QFrame.NoFrame)
        fh_scroll.setWidgetResizable(True)
        fh_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        fh_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        fh_inner = QWidget()
        fh_inner_lay = QVBoxLayout(fh_inner)
        fh_inner_lay.setSpacing(4)
        fh_inner_lay.setContentsMargins(0, 0, 8, 0)

        self._fh_buttons: list = []
        _last_kuerzel = None
        for entry in self._FH_OPTIONS:
            label, key = entry[0], entry[1]
            kuerzel = entry[2] if len(entry) > 2 else ""
            # Section header when school changes
            if kuerzel and kuerzel != _last_kuerzel and key != "manual":
                sec_lbl = QLabel(f"  {kuerzel}")
                sec_lbl.setStyleSheet(
                    "font-size:10px;font-weight:700;color:#7C3AED;"
                    "letter-spacing:0.6px;text-transform:uppercase;"
                    "padding:6px 0 2px 4px;"
                )
                fh_inner_lay.addWidget(sec_lbl)
                _last_kuerzel = kuerzel

            btn = QPushButton(f"  {label}")
            btn.setCheckable(True)
            btn.setFixedHeight(44)
            btn.setCursor(Qt.PointingHandCursor)
            if key == "manual":
                btn.setStyleSheet(
                    "QPushButton{text-align:left;padding:0 16px;border:2px dashed #D1D5DB;"
                    "border-radius:10px;font-size:13px;background:#FAFAFA;color:#6B7280;}"
                    "QPushButton:checked{border-color:#7C3AED;background:#F5F3FF;color:#7C3AED;font-weight:bold;}"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton{text-align:left;padding:0 16px;border:1.5px solid #E5E7EB;"
                    "border-radius:10px;font-size:13px;background:white;}"
                    "QPushButton:checked{border-color:#7C3AED;background:#F5F3FF;color:#7C3AED;font-weight:bold;}"
                    "QPushButton:hover{border-color:#C4B5FD;background:#FAFAFF;}"
                )
            btn.clicked.connect(lambda checked, k=key, b=btn: self._select_fh(k, b))
            fh_inner_lay.addWidget(btn)
            self._fh_buttons.append((key, btn))

        fh_inner_lay.addStretch()
        fh_scroll.setWidget(fh_inner)
        p1l.addWidget(fh_scroll, 1)

        # Auto-select first
        if self._fh_buttons:
            self._fh_buttons[0][1].setChecked(True)

        p1_note = QLabel("💡 Alle Daten sind lokal gespeichert – 100% offline.")
        p1_note.setStyleSheet("color:#9CA3AF;font-size:11px;")
        p1_note.setWordWrap(True)
        p1l.addWidget(p1_note)

        self._stack.addWidget(p1)

        # ── Page 2: Generieren / BOOM ────────────────────────────────────────
        p2 = QWidget()
        p2l = QVBoxLayout(p2)
        p2l.setSpacing(16)
        p2l.addStretch()

        p2_icon = QLabel("⚡")
        p2_icon.setStyleSheet("font-size:52px;")
        p2_icon.setAlignment(Qt.AlignCenter)
        p2l.addWidget(p2_icon)

        p2_title = QLabel("Studienplan generieren")
        p2_title.setObjectName("PageTitle")
        p2_title.setAlignment(Qt.AlignCenter)
        p2l.addWidget(p2_title)

        self._fh_confirm_lbl = QLabel()
        self._fh_confirm_lbl.setAlignment(Qt.AlignCenter)
        self._fh_confirm_lbl.setStyleSheet("color:#6B7280;font-size:13px;")
        p2l.addWidget(self._fh_confirm_lbl)

        self._gen_btn = QPushButton("🚀  Studienplan generieren")
        self._gen_btn.setObjectName("PrimaryBtn")
        self._gen_btn.setFixedHeight(52)
        self._gen_btn.setStyleSheet(
            "font-size:16px;font-weight:bold;background:#7C3AED;color:white;"
            "border-radius:12px;border:none;"
        )
        self._gen_btn.setCursor(Qt.PointingHandCursor)
        self._gen_btn.clicked.connect(self._generate_plan)
        p2l.addWidget(self._gen_btn)

        self._gen_progress = QLabel()
        self._gen_progress.setAlignment(Qt.AlignCenter)
        self._gen_progress.setStyleSheet("color:#10B981;font-size:13px;font-weight:bold;")
        self._gen_progress.setVisible(False)
        p2l.addWidget(self._gen_progress)

        p2l.addStretch()
        self._stack.addWidget(p2)

        # ── Page 3: BOOM – Alles da! ─────────────────────────────────────────
        p3 = QWidget()
        p3l = QVBoxLayout(p3)
        p3l.setSpacing(14)
        p3l.addStretch()

        p3_icon = QLabel("🎉")
        p3_icon.setStyleSheet("font-size:56px;")
        p3_icon.setAlignment(Qt.AlignCenter)
        p3l.addWidget(p3_icon)

        p3_title = QLabel("Dein Studienplan ist da!")
        p3_title.setObjectName("PageTitle")
        p3_title.setAlignment(Qt.AlignCenter)
        p3l.addWidget(p3_title)

        self._boom_lbl = QLabel()
        self._boom_lbl.setAlignment(Qt.AlignCenter)
        self._boom_lbl.setStyleSheet("color:#10B981;font-size:15px;font-weight:bold;")
        p3l.addWidget(self._boom_lbl)

        tips_frame = QFrame()
        tips_frame.setObjectName("Card")
        tl = QVBoxLayout(tips_frame)
        tl.setContentsMargins(16, 12, 16, 12)
        tl.setSpacing(8)
        tl.addWidget(QLabel("<b>Was als nächstes?</b>"))
        for tip in [
            "📊  Studienplan ansehen → alle Semester auf einen Blick",
            "📅  Prüfungstermine eintragen → Modul-Detailansicht",
            "✅  Lernziele & Aufgaben pro Fach erstellen",
            "💬  Studien-Coach fragen → Chat-Button links unten",
        ]:
            lbl = QLabel(tip)
            lbl.setStyleSheet("font-size:13px;color:#4C1D95;")
            tl.addWidget(lbl)
        p3l.addWidget(tips_frame)
        p3l.addStretch()
        self._stack.addWidget(p3)

    def _select_fh(self, key: str, clicked_btn):
        self._selected_fh = key
        for k, btn in self._fh_buttons:
            btn.setChecked(k == key)

    def _show_page(self, idx: int):
        self._page = idx
        self._stack.setCurrentIndex(idx)
        self._back_btn.setVisible(idx > 0 and idx < 3)
        total = 3
        self._prog_lbl.setText(f"Schritt {idx + 1} von {total}")
        if idx == 2:
            # update confirm label (handle both 2-tuple and 3-tuple entries)
            label = next((e[0] for e in self._FH_OPTIONS if e[1] == self._selected_fh), self._selected_fh)
            self._fh_confirm_lbl.setText(f"📚  {label}")
            self._next_btn.setVisible(False)
        elif idx == 3:
            self._next_btn.setText("Los geht's! 🎉")
            self._next_btn.setVisible(True)
            self._back_btn.setVisible(False)
        else:
            self._next_btn.setText("Weiter →")
            self._next_btn.setVisible(True)

    def _prev(self):
        if self._page > 0:
            self._show_page(self._page - 1)

    def _next(self):
        if self._page == 0:
            self._show_page(1)
        elif self._page == 1:
            self._show_page(2)
        elif self._page == 3:
            self.finished_setup.emit()
            self.accept()

    def _generate_plan(self):
        """Lädt den Studienplan der gewählten FH und importiert alle Module."""
        from PySide6.QtWidgets import QApplication

        # Manual setup: skip to final page immediately
        if self._selected_fh == "manual":
            self._imported_count = 0
            self._repo.set_setting("fh_name", "")
            self._repo.set_setting("studiengang", "")
            self._boom_lbl.setText("✅  Bereit! Richte deinen Plan manuell ein.")
            self._show_page(3)
            return

        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("⏳  Wird geladen…")
        self._gen_progress.setVisible(True)
        self._gen_progress.setText("Lade Module…")
        QApplication.processEvents()

        try:
            # FFHS Informatik: use the richer dedicated importer (36 real modules)
            if self._selected_fh in ("ffhs_bsc_informatik", "ffhs_ict"):
                from semetra.adapters.ffhs_importer import load_ffhs_modules
                modules = load_ffhs_modules(live=False)
                count = 0
                for m in modules:
                    try:
                        self._repo.add_module({
                            "name": m["name"],
                            "semester": str(m.get("_semester_int") or m.get("semester") or ""),
                            "ects": float(m.get("ects") or 0),
                            "module_type": m.get("_module_type") or "Pflicht",
                            "status": "planned",
                            "link": m.get("link") or "",
                        })
                        count += 1
                    except Exception:
                        pass
                self._imported_count = count
                self._repo.set_setting("fh_name", "FFHS")
                self._repo.set_setting("studiengang", "BSc Informatik")

            else:
                # All other FHs: load from fh_database.json
                import pathlib as _pl
                import json as _js
                db_path = _pl.Path(__file__).parent.parent / "fh_database.json"
                with open(db_path, encoding="utf-8") as _f:
                    _db = _js.load(_f)

                sg_data = None
                fh_name = ""
                sg_label = ""
                for hs in _db.get("hochschulen", []):
                    for sg in hs.get("studiengaenge", []):
                        if sg["id"] == self._selected_fh:
                            sg_data = sg
                            fh_name = hs.get("kuerzel", hs["name"])
                            sg_label = f"{sg['abschluss']} {sg['name']}"
                            break
                    if sg_data:
                        break

                if sg_data is None:
                    raise ValueError(f"Studiengang '{self._selected_fh}' nicht in Datenbank gefunden.")

                count = 0
                for m in sg_data.get("module", []):
                    try:
                        self._repo.add_module({
                            "name": m["name"],
                            "semester": str(m.get("semester", "")),
                            "ects": float(m.get("ects") or 0),
                            "module_type": m.get("typ", "Pflicht"),
                            "status": "planned",
                            "link": "",
                        })
                        count += 1
                    except Exception:
                        pass
                self._imported_count = count
                self._repo.set_setting("fh_name", fh_name)
                self._repo.set_setting("studiengang", sg_label)

        except Exception as exc:
            self._gen_progress.setText(f"⚠️  Fehler: {exc}")
            self._gen_btn.setEnabled(True)
            self._gen_btn.setText("🚀  Nochmals versuchen")
            return

        # BOOM!
        label = next((e[0] for e in self._FH_OPTIONS if e[1] == self._selected_fh), "")
        if self._imported_count > 0:
            self._boom_lbl.setText(
                f"✅  {self._imported_count} Module aus\n\"{label}\" importiert!\n\n"
                "Dein Studienplan ist vollständig aufgebaut."
            )
        else:
            self._boom_lbl.setText("✅  Bereit! Richte deinen Plan manuell ein.")
        self._show_page(3)
