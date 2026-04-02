"""Settings page."""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QDialog, QDialogButtonBox,
    QSizePolicy, QMessageBox, QFileDialog, QTabWidget, QFormLayout, QGroupBox,
    QApplication,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import QComboBox, StatCard, make_scroll
from semetra.gui.i18n import tr
from semetra.gui.colors import ACCENT_PRESETS, ACCENT_PRESET_LABELS, _tc, set_accent, set_theme, get_accent_color
from semetra.gui.platform import _open_url



class SettingsPage(QWidget):
    theme_changed  = Signal(str)
    lang_changed   = Signal(str)   # emits language code ("de"/"en"/"fr"/"it")
    accent_changed = Signal(str)   # emits preset key ("violet", "ocean", …)

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build()

    def _build(self):
        _page_lay = QVBoxLayout(self)
        _page_lay.setContentsMargins(0, 0, 0, 0)
        _page_lay.setSpacing(0)
        _scroll_w = QWidget()
        _scroll_w.setAttribute(Qt.WA_StyledBackground, True)
        _page_lay.addWidget(make_scroll(_scroll_w))
        lay = QVBoxLayout(_scroll_w)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(20)

        title = QLabel(tr("page.settings"))
        title.setObjectName("PageTitle")
        lay.addWidget(title)

        app_grp = QGroupBox("Darstellung")
        app_lay = QFormLayout(app_grp)
        app_lay.setSpacing(12)
        self.theme_cb = QComboBox()
        self.theme_cb.addItems(["Hell", "Dunkel"])
        theme = self.repo.get_setting("theme") or "light"
        self.theme_cb.setCurrentIndex(0 if theme == "light" else 1)
        self.theme_cb.currentIndexChanged.connect(self._on_theme)
        app_lay.addRow("Design:", self.theme_cb)

        # ── Accent / Layout colour preset ────────────────────────────────────
        self.accent_cb = QComboBox()
        self.accent_cb.setMinimumWidth(220)
        for label, key in ACCENT_PRESET_LABELS:
            self.accent_cb.addItem(label, key)
        saved_accent = self.repo.get_setting("accent_preset") or "violet"
        for i in range(self.accent_cb.count()):
            if self.accent_cb.itemData(i) == saved_accent:
                self.accent_cb.setCurrentIndex(i)
                break
        self.accent_cb.currentIndexChanged.connect(self._on_accent)
        app_lay.addRow("Akzentfarbe / Layout:", self.accent_cb)

        accent_note = QLabel("Ändert die Hauptfarbe der gesamten Oberfläche sofort.")
        accent_note.setStyleSheet("color: #706C86; font-size: 11px;")
        accent_note.setWordWrap(True)
        app_lay.addRow("", accent_note)

        self.lang_cb = QComboBox()
        self.lang_cb.addItems(["Deutsch 🇩🇪", "English 🇬🇧", "Français 🇫🇷", "Italiano 🇮🇹"])
        lang_map = {"de": 0, "en": 1, "fr": 2, "it": 3}
        lang = self.repo.get_setting("language") or "de"
        self.lang_cb.setCurrentIndex(lang_map.get(lang, 0))
        self.lang_cb.currentIndexChanged.connect(self._on_lang)
        app_lay.addRow("Sprache:", self.lang_cb)

        self._lang_note = QLabel(
            "Navigationsleiste wird sofort übersetzt. "
            "Alle anderen Texte beim nächsten Neustart."
        )
        self._lang_note.setStyleSheet("color: #706C86; font-size: 11px;")
        self._lang_note.setWordWrap(True)
        app_lay.addRow("", self._lang_note)
        lay.addWidget(app_grp)

        study_grp = QGroupBox("Lerneinstellungen")
        study_lay = QFormLayout(study_grp)
        study_lay.setSpacing(12)
        self.ects_spin = QSpinBox()
        self.ects_spin.setRange(1, 100)
        self.ects_spin.setValue(self.repo.hours_per_ects())
        self.ects_spin.setSuffix(" Stunden / ECTS")
        study_lay.addRow("Arbeitsstunden pro ECTS:", self.ects_spin)
        save_btn = QPushButton("Speichern")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.clicked.connect(self._save)
        study_lay.addRow("", save_btn)
        lay.addWidget(study_grp)

        stats_grp = QGroupBox("Statistiken")
        stats_lay = QFormLayout(stats_grp)
        self.total_modules_lbl = QLabel()
        self.total_tasks_lbl = QLabel()
        self.total_hours_lbl = QLabel()
        stats_lay.addRow("Module:", self.total_modules_lbl)
        stats_lay.addRow("Aufgaben:", self.total_tasks_lbl)
        stats_lay.addRow("Gesamte Lernzeit:", self.total_hours_lbl)
        lay.addWidget(stats_grp)

        # ── Datensicherung ───────────────────────────────────────────────────
        backup_grp = QGroupBox("Datensicherung")
        backup_lay = QFormLayout(backup_grp)
        backup_lay.setSpacing(10)

        backup_note = QLabel(
            "Exportiere deine gesamten Semetra-Daten als ZIP-Datei. "
            "So kannst du deine Daten sichern oder auf einen anderen Computer übertragen."
        )
        backup_note.setWordWrap(True)
        backup_note.setStyleSheet("color:#706C86;font-size:11px;")
        backup_lay.addRow("", backup_note)

        export_row = QHBoxLayout()
        export_btn = QPushButton("💾 Daten exportieren (ZIP)")
        export_btn.setObjectName("SecondaryBtn")
        export_btn.setFixedHeight(32)
        export_btn.clicked.connect(self._export_data)
        export_row.addWidget(export_btn)
        export_row.addStretch()
        backup_lay.addRow("Backup:", export_row)

        import_row = QHBoxLayout()
        import_btn = QPushButton("📂 Backup wiederherstellen")
        import_btn.setObjectName("SecondaryBtn")
        import_btn.setFixedHeight(32)
        import_btn.clicked.connect(self._import_data)
        import_row.addWidget(import_btn)
        import_row.addStretch()
        backup_lay.addRow("Wiederherstellen:", import_row)

        lay.addWidget(backup_grp)

        # ── Account & Login ──────────────────────────────────────────────────
        acct_grp = QGroupBox("Account & Cloud-Sync")
        acct_lay = QFormLayout(acct_grp)
        acct_lay.setSpacing(10)

        from semetra.infra.license import LicenseManager
        lm = LicenseManager(self.repo)
        self._lm = lm
        self._is_pro = lm.is_pro()

        # Account status
        self._acct_status = QLabel()
        self._acct_status.setWordWrap(True)
        self._update_acct_status()
        acct_lay.addRow("Account:", self._acct_status)

        # Login form (hidden when already logged in)
        self._login_widget = QWidget()
        login_lay = QVBoxLayout(self._login_widget)
        login_lay.setContentsMargins(0, 0, 0, 0)
        login_lay.setSpacing(6)
        self._email_edit = QLineEdit()
        self._email_edit.setPlaceholderText("E-Mail")
        self._email_edit.setFixedHeight(32)
        login_lay.addWidget(self._email_edit)
        self._pw_edit = QLineEdit()
        self._pw_edit.setPlaceholderText("Passwort")
        self._pw_edit.setEchoMode(QLineEdit.Password)
        self._pw_edit.setFixedHeight(32)
        self._pw_edit.returnPressed.connect(self._do_login)
        login_lay.addWidget(self._pw_edit)
        login_btn_row = QHBoxLayout()
        login_btn = QPushButton("Einloggen")
        login_btn.setObjectName("PrimaryBtn")
        login_btn.setFixedHeight(32)
        login_btn.clicked.connect(self._do_login)
        login_btn_row.addWidget(login_btn)
        register_lbl = QLabel('<a href="https://semetra.ch/register" style="color:#7C3AED;">Noch kein Account?</a>')
        register_lbl.setStyleSheet("font-size:11px;")
        register_lbl.setOpenExternalLinks(False)
        register_lbl.linkActivated.connect(lambda url: _open_url(url))
        login_btn_row.addWidget(register_lbl)
        login_btn_row.addStretch()
        login_lay.addLayout(login_btn_row)
        acct_lay.addRow("", self._login_widget)

        # Logout button (hidden when not logged in)
        self._logout_btn = QPushButton("Abmelden")
        self._logout_btn.setFixedHeight(28)
        self._logout_btn.setStyleSheet(
            "QPushButton{background:#E53E3E;color:white;border:none;"
            "border-radius:6px;padding:0 10px;font-size:11px;}"
            "QPushButton:hover{background:#C53030;}"
        )
        self._logout_btn.clicked.connect(self._do_logout)
        acct_lay.addRow("", self._logout_btn)

        acct_note = QLabel(
            "Optional: Ohne Account funktioniert Semetra komplett offline. "
            "Mit Account kannst du deine Daten auf allen Geräten synchronisieren."
        )
        acct_note.setStyleSheet("color:#706C86;font-size:11px;")
        acct_note.setWordWrap(True)
        acct_lay.addRow("", acct_note)

        # ── Sync controls ────────────────────────────────────────────────────
        sync_sep = QFrame()
        sync_sep.setFrameShape(QFrame.HLine)
        sync_sep.setStyleSheet(_tc("color:#EAE8F2;", "color:#1E1B2C;"))
        acct_lay.addRow(sync_sep)

        sync_row = QHBoxLayout()
        self._sync_btn = QPushButton("🔄 Jetzt synchronisieren")
        self._sync_btn.setObjectName("PrimaryBtn")
        self._sync_btn.setFixedHeight(32)
        self._sync_btn.clicked.connect(self._do_sync)
        sync_row.addWidget(self._sync_btn)
        self._sync_status_lbl = QLabel("")
        self._sync_status_lbl.setStyleSheet("color:#706C86;font-size:11px;")
        sync_row.addWidget(self._sync_status_lbl, 1)
        acct_lay.addRow("Cloud-Sync:", sync_row)

        # Auto-sync toggle
        self._auto_sync_cb = QCheckBox("Automatisch synchronisieren beim Start")
        auto_sync = self.repo.get_setting("auto_sync") or "1"
        self._auto_sync_cb.setChecked(auto_sync == "1")
        self._auto_sync_cb.toggled.connect(
            lambda checked: self.repo.set_setting("auto_sync", "1" if checked else "0")
        )
        acct_lay.addRow("", self._auto_sync_cb)

        # Last sync info
        try:
            from semetra.infra.sync import SyncManager
            sm = SyncManager(self.repo, lm.account)
            last = sm.last_sync_at()
            if last:
                try:
                    from datetime import datetime as _dt
                    dt = _dt.fromisoformat(last.replace("Z", "+00:00"))
                    self._sync_status_lbl.setText(f"Letzter Sync: {dt.strftime('%d.%m.%Y %H:%M')}")
                except Exception:
                    self._sync_status_lbl.setText(f"Letzter Sync: {last[:16]}")
        except ImportError:
            pass  # sync.py noch nicht implementiert

        self._update_login_visibility()
        lay.addWidget(acct_grp)

        # ── Lizenz ───────────────────────────────────────────────────────────
        lic_grp = QGroupBox("Lizenz")
        lic_lay = QFormLayout(lic_grp)
        lic_lay.setSpacing(10)

        if self._is_pro:
            self._lic_status = QLabel("✅ Semetra Pro — aktiviert")
            self._lic_status.setStyleSheet("color:#1A7A5A;font-weight:bold;")
        else:
            self._lic_status = QLabel("🔒 Keine Pro-Lizenz")
            self._lic_status.setStyleSheet(f"color:{_tc('#888','#AAA')};")

        # Status row: label + optional deactivate button
        status_row = QHBoxLayout()
        status_row.addWidget(self._lic_status)
        status_row.addStretch()
        self._deact_btn = QPushButton("🔓 Deaktivieren")
        self._deact_btn.setFixedHeight(28)
        self._deact_btn.setStyleSheet(
            "QPushButton{background:#E53E3E;color:white;border:none;"
            "border-radius:6px;padding:0 10px;font-size:11px;}"
            "QPushButton:hover{background:#C53030;}"
        )
        self._deact_btn.setVisible(self._is_pro)
        self._deact_btn.clicked.connect(self._deactivate_license)
        status_row.addWidget(self._deact_btn)
        lic_lay.addRow("Status:", status_row)

        self._lic_code_lbl = QLabel(lm.current_code() or "—")
        self._lic_code_lbl.setStyleSheet(f"color:{_tc('#555','#AAA')};font-size:11px;")
        if lm.current_code():
            lic_lay.addRow("Code:", self._lic_code_lbl)

        lic_input_row = QHBoxLayout()
        self._lic_edit = QLineEdit()
        self._lic_edit.setPlaceholderText("XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX")
        self._lic_edit.setFixedHeight(32)
        self._lic_edit.returnPressed.connect(self._activate_license)
        lic_input_row.addWidget(self._lic_edit, 1)
        lic_act_btn = QPushButton("Aktivieren")
        lic_act_btn.setObjectName("PrimaryBtn")
        lic_act_btn.setFixedHeight(32)
        lic_act_btn.clicked.connect(self._activate_license)
        lic_input_row.addWidget(lic_act_btn)
        lic_lay.addRow("Lizenzcode:", lic_input_row)

        lic_note = QLabel('<a href="https://semetra.ch/#preise" style="color:#7C3AED;">Alle Pläne auf semetra.ch ansehen →</a>')
        lic_note.setStyleSheet("font-size:11px;")
        lic_note.setOpenExternalLinks(False)
        lic_note.linkActivated.connect(lambda url: _open_url(url))
        lic_lay.addRow("", lic_note)

        # ── Desktop Pro Einmalkauf Hinweis ───────────────────────────────────
        if not self._is_pro:
            from semetra.infra.license import STRIPE_DESKTOP_PRO_URL
            einmal_lbl = QLabel(
                '<b>💡 Tipp:</b> <a href="' + STRIPE_DESKTOP_PRO_URL + '" style="color:#059669;">'
                'Desktop Pro Einmalkauf (CHF 49.90)</a> — Einmal zahlen, dauerhaft Pro. Kein Abo!'
            )
            einmal_lbl.setStyleSheet("font-size:11px;background:#ECFDF5;padding:8px;border-radius:8px;")
            einmal_lbl.setWordWrap(True)
            einmal_lbl.setOpenExternalLinks(False)
            einmal_lbl.linkActivated.connect(lambda url: _open_url(url))
            lic_lay.addRow("", einmal_lbl)

        lay.addWidget(lic_grp)

        lay.addStretch()

        about = QLabel("Semetra v2.0  |  Powered by PySide6 + SQLite")
        about.setStyleSheet("color: #706C86; font-size: 12px;")
        about.setAlignment(Qt.AlignCenter)
        lay.addWidget(about)

    def refresh(self):
        self.ects_spin.setValue(self.repo.hours_per_ects())
        theme = self.repo.get_setting("theme") or "light"
        self.theme_cb.blockSignals(True)
        self.theme_cb.setCurrentIndex(0 if theme == "light" else 1)
        self.theme_cb.blockSignals(False)
        lang_map = {"de": 0, "en": 1, "fr": 2, "it": 3}
        lang = self.repo.get_setting("language") or "de"
        self.lang_cb.blockSignals(True)
        self.lang_cb.setCurrentIndex(lang_map.get(lang, 0))
        self.lang_cb.blockSignals(False)
        saved_accent = self.repo.get_setting("accent_preset") or "violet"
        self.accent_cb.blockSignals(True)
        for i in range(self.accent_cb.count()):
            if self.accent_cb.itemData(i) == saved_accent:
                self.accent_cb.setCurrentIndex(i)
                break
        self.accent_cb.blockSignals(False)
        modules = self.repo.list_modules("all")
        tasks = self.repo.list_tasks()
        logs = self.repo.list_time_logs()
        total_secs = sum(int(l["seconds"]) for l in logs)
        self.total_modules_lbl.setText(str(len(modules)))
        self.total_tasks_lbl.setText(str(len(tasks)))
        self.total_hours_lbl.setText(f"{total_secs/3600:.1f}h")

    def _on_accent(self):
        preset = self.accent_cb.currentData() or "violet"
        self.repo.set_setting("accent_preset", preset)
        self.accent_changed.emit(preset)

    def _on_theme(self):
        theme = "dark" if self.theme_cb.currentIndex() == 1 else "light"
        self.repo.set_setting("theme", theme)
        self.theme_changed.emit(theme)

    def _on_lang(self):
        langs = ["de", "en", "fr", "it"]
        idx = self.lang_cb.currentIndex()
        lang = langs[idx] if 0 <= idx < len(langs) else "de"
        self.repo.set_setting("language", lang)
        self.lang_changed.emit(lang)   # live update — no restart needed

    def _save(self):
        self.repo.set_setting("hours_per_ects", str(self.ects_spin.value()))
        QMessageBox.information(self, "Gespeichert", "Einstellungen wurden gespeichert.")

    def _activate_license(self):
        from semetra.infra.license import LicenseManager
        code = self._lic_edit.text().strip()
        if not code:
            QMessageBox.warning(self, "Code fehlt", "Bitte einen Lizenzcode eingeben.")
            return
        lm = LicenseManager(self.repo)
        ok, msg = lm.activate(code)
        if ok:
            # Store activation date (first activation only)
            import datetime as _dt
            if not self.repo.get_setting("pro_activated_at"):
                self.repo.set_setting(
                    "pro_activated_at", _dt.date.today().isoformat()
                )
            self._lic_status.setText("✅ Semetra Pro — aktiviert")
            self._lic_status.setStyleSheet("color:#1A7A5A;font-weight:bold;")
            self._lic_edit.clear()
            QMessageBox.information(
                self, "✅ Aktiviert!",
                "Semetra Pro wurde erfolgreich aktiviert.\n"
                "Danke für deine Unterstützung! 🎉"
            )
            # Refresh sidebar badge immediately
            parent = self.parent()
            while parent is not None:
                if hasattr(parent, "_update_plan_badge"):
                    parent._update_plan_badge()
                    break
                parent = parent.parent() if hasattr(parent, "parent") else None
        else:
            QMessageBox.warning(
                self, "Ungültiger Code",
                f"{msg}\n\nDen Lizenzcode findest du in der E-Mail, die du nach dem Kauf erhalten hast."
            )

    def _export_data(self):
        import zipfile, shutil
        from pathlib import Path
        db_path = Path(self.repo.db_path) if hasattr(self.repo, "db_path") else None
        if db_path is None:
            # Try to find db via repo connection
            try:
                db_path = Path(self.repo._conn.database if hasattr(self.repo, "_conn") else "")
            except Exception:
                db_path = None
        # Fallback: search common locations
        if not db_path or not db_path.exists():
            candidates = [
                Path.home() / "AppData" / "Local" / "Semetra" / "semetra.db",
                Path.home() / ".local" / "share" / "Semetra" / "semetra.db",
                Path("study.db"),
                Path("semetra.db"),
            ]
            for c in candidates:
                if c.exists():
                    db_path = c
                    break
        if not db_path or not db_path.exists():
            QMessageBox.warning(self, "Export fehlgeschlagen",
                "Datenbankdatei konnte nicht gefunden werden.")
            return

        from datetime import date
        default_name = f"semetra_backup_{date.today().isoformat()}.zip"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Backup speichern", default_name, "ZIP-Archiv (*.zip)"
        )
        if not save_path:
            return
        try:
            with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(db_path, "semetra.db")
                # Write a small manifest
                import json as _json
                from semetra import __version__
                manifest = {
                    "version": __version__,
                    "exported": date.today().isoformat(),
                    "source": str(db_path),
                }
                zf.writestr("manifest.json", _json.dumps(manifest, indent=2))
            QMessageBox.information(
                self, "✅ Export erfolgreich",
                f"Deine Daten wurden gespeichert:\n{save_path}\n\n"
                "Bewahre diese Datei sicher auf!"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export fehlgeschlagen", str(e))

    def _import_data(self):
        import zipfile, shutil
        from pathlib import Path
        reply = QMessageBox.warning(
            self, "Backup wiederherstellen",
            "⚠️  Alle aktuellen Daten werden durch das Backup ersetzt!\n\n"
            "Möchtest du wirklich fortfahren?",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return
        zip_path, _ = QFileDialog.getOpenFileName(
            self, "Backup auswählen", "", "ZIP-Archiv (*.zip)"
        )
        if not zip_path:
            return
        db_path = Path(self.repo.db_path) if hasattr(self.repo, "db_path") else None
        if not db_path:
            candidates = [
                Path.home() / "AppData" / "Local" / "Semetra" / "semetra.db",
                Path.home() / ".local" / "share" / "Semetra" / "semetra.db",
                Path("study.db"),
                Path("semetra.db"),
            ]
            for c in candidates:
                if c.exists():
                    db_path = c
                    break
        if not db_path:
            QMessageBox.warning(self, "Fehler", "Datenbankpfad konnte nicht ermittelt werden.")
            return
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                if "semetra.db" not in names:
                    QMessageBox.critical(self, "Ungültiges Backup",
                        "Diese ZIP-Datei enthält keine Semetra-Datenbank.")
                    return
                # Backup current db before overwrite
                bak = db_path.with_suffix(".db.bak")
                if db_path.exists():
                    shutil.copy2(db_path, bak)
                with zf.open("semetra.db") as src, open(db_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            QMessageBox.information(
                self, "✅ Wiederhergestellt",
                "Das Backup wurde erfolgreich wiederhergestellt.\n"
                "Starte Semetra neu, um alle Daten zu laden."
            )
        except Exception as e:
            QMessageBox.critical(self, "Wiederherstellung fehlgeschlagen", str(e))

    # ── Account / Login / Sync helpers ────────────────────────────────────

    def _update_acct_status(self):
        """Update the account status label."""
        if self._lm.account.is_logged_in():
            email = self._lm.account.get_email()
            self._acct_status.setText(f"Eingeloggt als {email}")
            self._acct_status.setStyleSheet("color:#1A7A5A;font-weight:bold;")
        else:
            self._acct_status.setText("Nicht eingeloggt (Offline-Modus)")
            self._acct_status.setStyleSheet(f"color:{_tc('#888','#AAA')};")

    def _update_login_visibility(self):
        """Toggle visibility of login form vs logout button."""
        logged_in = self._lm.account.is_logged_in()
        self._login_widget.setVisible(not logged_in)
        self._logout_btn.setVisible(logged_in)
        self._sync_btn.setEnabled(logged_in)

    def _do_login(self):
        """Handle login button click."""
        email = self._email_edit.text().strip()
        pw = self._pw_edit.text().strip()
        if not email or not pw:
            QMessageBox.warning(self, "Fehlende Daten", "Bitte E-Mail und Passwort eingeben.")
            return
        ok, msg = self._lm.account.login(email, pw)
        if ok:
            self._pw_edit.clear()
            self._update_acct_status()
            self._update_login_visibility()
            self._is_pro = self._lm.is_pro()
            if self._is_pro:
                self._lic_status.setText("✅ Semetra Pro — aktiviert")
                self._lic_status.setStyleSheet("color:#1A7A5A;font-weight:bold;")
                self._deact_btn.setVisible(True)
            QMessageBox.information(self, "Login", msg)
            # Refresh sidebar badge
            self._notify_badge_update()
        else:
            QMessageBox.warning(self, "Login fehlgeschlagen", msg)

    def _do_logout(self):
        """Handle logout button click."""
        reply = QMessageBox.question(
            self, "Abmelden",
            "Möchtest du dich wirklich abmelden?\n"
            "Deine lokalen Daten bleiben erhalten.",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return
        self._lm.account.logout()
        self._update_acct_status()
        self._update_login_visibility()
        self._is_pro = self._lm.is_pro()
        if not self._is_pro:
            self._lic_status.setText("🔒 Keine Pro-Lizenz")
            self._lic_status.setStyleSheet(f"color:{_tc('#888','#AAA')};")
            self._deact_btn.setVisible(False)
        self._notify_badge_update()

    def _do_sync(self):
        """Handle sync button click."""
        try:
            from semetra.infra.sync import SyncManager
        except ImportError:
            QMessageBox.information(self, "Sync", "Cloud-Sync ist noch in Entwicklung.")
            return
        sm = SyncManager(self.repo, self._lm.account)
        if not sm.can_sync():
            QMessageBox.warning(
                self, "Sync nicht möglich",
                "Bitte zuerst einloggen und sicherstellen, dass eine Internetverbindung besteht."
            )
            return
        self._sync_btn.setEnabled(False)
        self._sync_btn.setText("Synchronisiere…")
        self._sync_status_lbl.setText("")
        # Run sync (blocking for now — could use QThread for large datasets)
        QApplication.processEvents()
        stats = sm.sync_full()
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("🔄 Jetzt synchronisieren")
        if stats.get("errors"):
            self._sync_status_lbl.setText(f"Fehler: {stats['errors'][0]}")
            self._sync_status_lbl.setStyleSheet("color:#E53E3E;font-size:11px;")
        else:
            up = stats.get("uploaded", 0)
            down = stats.get("downloaded", 0)
            from datetime import datetime as _dt
            now_str = _dt.now().strftime("%d.%m.%Y %H:%M")
            self._sync_status_lbl.setText(
                f"Letzter Sync: {now_str} ({up} hoch, {down} runter)"
            )
            self._sync_status_lbl.setStyleSheet("color:#1A7A5A;font-size:11px;")
        # Refresh all pages after sync
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "_refresh_all"):
                parent._refresh_all()
                break
            parent = parent.parent() if hasattr(parent, "parent") else None

    def _notify_badge_update(self):
        """Walk up to the main window and trigger badge refresh."""
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "_update_plan_badge"):
                parent._update_plan_badge()
                break
            parent = parent.parent() if hasattr(parent, "parent") else None

    def _deactivate_license(self):
        from semetra.infra.license import LicenseManager
        reply = QMessageBox.question(
            self,
            "Pro-Lizenz deaktivieren",
            "Möchtest du Semetra Pro wirklich deaktivieren?\n\n"
            "Du kannst den Lizenzcode jederzeit wieder eingeben.",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return
        lm = LicenseManager(self.repo)
        lm.deactivate()
        self._lic_status.setText("🔒 Keine Pro-Lizenz")
        self._lic_status.setStyleSheet(f"color:{_tc('#888','#AAA')};")
        self._deact_btn.setVisible(False)
        if hasattr(self, "_lic_code_lbl"):
            self._lic_code_lbl.setText("—")
        # Notify parent window to refresh sidebar badge
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "_update_plan_badge"):
                parent._update_plan_badge()
                break
            parent = parent.parent() if hasattr(parent, "parent") else None


