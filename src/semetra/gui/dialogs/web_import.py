"""Web-based module importer dialog."""

from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QTableWidget, QTableWidgetItem, QCheckBox,
    QWidget, QProgressBar, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QHeaderView

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.colors import _tc
from semetra.gui.workers import _ScraperWorker
from semetra.gui.i18n import tr


class WebImportDialog(QDialog):
    """
    Web-basierter Modul-Importer.
    Nutzer gibt eine Hochschul-URL ein → KI-Scraper extrahiert Semester,
    Module, Lernziele, Lerninhalte und zeigt eine Vorschau zum Import.
    """

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self._modules: List[Dict[str, Any]] = []
        self._checkboxes: List[QCheckBox] = []
        self._worker: Optional[_ScraperWorker] = None
        self.setWindowTitle("📄 Modulplan per PDF importieren")
        self.setMinimumWidth(820)
        self.setMinimumHeight(600)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(14)

        # ── Header ──────────────────────────────────────────────────────
        hdr_lbl = QLabel("📄 Modulplan per PDF importieren")
        hdr_lbl.setStyleSheet("font-size:18px;font-weight:bold;")
        lay.addWidget(hdr_lbl)

        info = QLabel(
            "Gib die URL der Studiengangsseite deiner Hochschule ein. "
            "Der Scraper analysiert die Seiten automatisch und extrahiert "
            "Module, Semester, ECTS und Modultypen — ohne externe API, 100 % lokal."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{_tc('#555','#AAA')};font-size:12px;")
        lay.addWidget(info)

        # ── URL ──────────────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(10)
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://www.ffhs.ch/de/bachelor/informatik")
        form.addRow("Hochschul-URL:", self._url_edit)
        lay.addLayout(form)

        # ── Scrape button + progress ─────────────────────────────────────
        scrape_row = QHBoxLayout()
        self._scrape_btn = QPushButton("📤 PDF importieren")
        self._scrape_btn.setObjectName("PrimaryBtn")
        self._scrape_btn.clicked.connect(self._start_scrape)
        scrape_row.addWidget(self._scrape_btn)
        self._stop_btn = QPushButton("⏹ Stopp")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_scrape)
        scrape_row.addWidget(self._stop_btn)
        scrape_row.addStretch()
        lay.addLayout(scrape_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)   # indeterminate
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(6)
        lay.addWidget(self._progress_bar)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color:{_tc('#706C86','#9B93B0')};font-size:11px;")
        self._status_lbl.setWordWrap(True)
        lay.addWidget(self._status_lbl)

        # ── Preview table ────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{_tc('#DDE3F0','#383850')};")
        lay.addWidget(sep)

        preview_hdr = QHBoxLayout()
        preview_hdr.addWidget(QLabel("Vorschau der gefundenen Module:"))
        preview_hdr.addStretch()
        self._sel_all_btn = QPushButton("Alle auswählen")
        self._sel_all_btn.setEnabled(False)
        self._sel_all_btn.clicked.connect(self._select_all)
        preview_hdr.addWidget(self._sel_all_btn)
        self._sel_none_btn = QPushButton("Keine auswählen")
        self._sel_none_btn.setEnabled(False)
        self._sel_none_btn.clicked.connect(self._select_none)
        preview_hdr.addWidget(self._sel_none_btn)
        lay.addLayout(preview_hdr)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["✓", "Name", "Semester", "ECTS", "Typ"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setColumnWidth(0, 32)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.setAlternatingRowColors(True)
        lay.addWidget(self._table, 1)

        # ── Footer buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._import_btn = QPushButton("📥 Ausgewählte importieren")
        self._import_btn.setObjectName("PrimaryBtn")
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self._do_import)
        btn_row.addWidget(self._import_btn)
        lay.addLayout(btn_row)

    # ── Helpers ─────────────────────────────────────────────────────────

    def _start_scrape(self):
        url = self._url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "URL fehlt", "Bitte eine Hochschul-URL eingeben.")
            return

        # Check dependencies
        try:
            from semetra.adapters.web_scraper import check_dependencies
            missing = check_dependencies()
            if missing:
                QMessageBox.warning(
                    self, "Fehlende Pakete",
                    f"Folgende Python-Pakete fehlen:\n{', '.join(missing)}\n\n"
                    "Bitte installieren mit:\n"
                    f"pip install {' '.join(missing)}"
                )
                return
        except ImportError as e:
            QMessageBox.critical(self, "Import-Fehler", str(e))
            return

        self._scrape_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._progress_bar.setVisible(True)
        self._import_btn.setEnabled(False)
        self._sel_all_btn.setEnabled(False)
        self._sel_none_btn.setEnabled(False)
        self._table.setRowCount(0)
        self._checkboxes.clear()
        self._modules.clear()
        self._status_lbl.setText("⏳ PDF wird verarbeitet…")

        self._worker = _ScraperWorker(url)   # kein parent=self → kein vorzeitiges Delete
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop_scrape(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
        self._reset_ui()
        self._status_lbl.setText("⏹ Scraping gestoppt.")

    def closeEvent(self, event):
        """Sicherstellen dass der Worker-Thread gestoppt ist bevor der Dialog schliesst."""
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
        super().closeEvent(event)

    def reject(self):
        """Auch beim Schliessen via Escape/X den Worker stoppen."""
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
        super().reject()

    def _reset_ui(self):
        self._scrape_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress_bar.setVisible(False)

    def _on_progress(self, msg: str):
        self._status_lbl.setText(f"⏳ {msg}")

    def _on_error(self, msg: str):
        self._reset_ui()
        self._status_lbl.setText(f"❌ Fehler: {msg}")
        QMessageBox.critical(self, "Scraping-Fehler", msg)

    def _on_finished(self, modules: List[Dict[str, Any]]):
        self._reset_ui()
        self._modules = modules
        if not modules:
            self._status_lbl.setText("⚠️ Keine Module gefunden. Versuche eine spezifischere URL.")
            return
        self._status_lbl.setText(f"✅ {len(modules)} Module gefunden. Auswahl treffen und importieren.")
        self._populate_table(modules)
        self._import_btn.setEnabled(True)
        self._sel_all_btn.setEnabled(True)
        self._sel_none_btn.setEnabled(True)

    def _populate_table(self, modules: List[Dict[str, Any]]):
        self._checkboxes.clear()
        self._table.setRowCount(0)
        for mod in modules:
            row = self._table.rowCount()
            self._table.insertRow(row)

            cb = QCheckBox()
            cb.setChecked(True)
            cb_widget = QWidget()
            cb_lay = QHBoxLayout(cb_widget)
            cb_lay.setContentsMargins(4, 0, 0, 0)
            cb_lay.addWidget(cb)
            self._table.setCellWidget(row, 0, cb_widget)
            self._checkboxes.append(cb)

            self._table.setItem(row, 1, QTableWidgetItem(mod.get("name", "")))
            sem = str(mod.get("semester", ""))
            self._table.setItem(row, 2, QTableWidgetItem(sem if sem != "0" else "–"))
            self._table.setItem(row, 3, QTableWidgetItem(str(mod.get("ects", 0))))
            mt = mod.get("_module_type", mod.get("module_type", "Pflicht"))
            self._table.setItem(row, 4, QTableWidgetItem(mt))

    def _select_all(self):
        for cb in self._checkboxes:
            cb.setChecked(True)

    def _select_none(self):
        for cb in self._checkboxes:
            cb.setChecked(False)

    def _do_import(self):
        selected = [m for m, cb in zip(self._modules, self._checkboxes) if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "Keine Auswahl", "Bitte mindestens ein Modul auswählen.")
            return
        imported = 0
        skipped = 0
        for mod in selected:
            try:
                # Normalise module_type → lowercase key for DB
                mt_raw = mod.get("_module_type", mod.get("module_type", "Pflicht"))
                mt_map = {"Pflicht": "pflicht", "Wahl": "wahl", "Vertiefung": "vertiefung",
                          "pflicht": "pflicht", "wahl": "wahl", "vertiefung": "vertiefung"}
                mod["module_type"] = mt_map.get(mt_raw, "pflicht")
                mod["in_plan"] = 1
                mod["status"] = mod.get("status", "planned")
                mod_id = self.repo.add_module(mod)

                # Import scraped data (objectives / content / assessments)
                for item in mod.get("_scraped_data", []):
                    self.repo.add_scraped_data(
                        mod_id,
                        data_type=item.get("data_type", "objective"),
                        title=item.get("title", ""),
                        body=item.get("body", ""),
                        weight=item.get("weight"),
                    )
                imported += 1
            except Exception:
                skipped += 1

        msg = f"{imported} Module importiert."
        if skipped:
            msg += f" {skipped} übersprungen (Fehler)."
        QMessageBox.information(self, "Import abgeschlossen", msg)
        self.accept()
