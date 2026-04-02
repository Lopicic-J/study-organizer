"""FH database import dialog."""

from typing import Any, Dict, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.colors import _tc
from semetra.gui.i18n import tr
import json
import pathlib


class FHDatabaseImportDialog(QDialog):
    """Import-Dialog für die eingebaute Offline-FH-Datenbank.
    Zeigt FH → Studiengang → Modulvorschau, importiert ausgewählte Module.
    Keine Online-Verbindung, keine Scraping-Risiken.
    """

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("FH-Datenbank Import")
        self.setMinimumSize(700, 540)
        self._db = self._load_db()
        self._selected_module_ids: list = []
        self._build()

    # ── Datenbank laden ───────────────────────────────────────────────────────
    @staticmethod
    def _load_db() -> dict:
        db_path = pathlib.Path(__file__).parent.parent / "fh_database.json"
        try:
            with open(db_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"hochschulen": []}

    # ── UI aufbauen ───────────────────────────────────────────────────────────
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(14)

        # Header
        hdr = QLabel("🏫  FH-Datenbank Import")
        hdr.setStyleSheet("font-size:16px;font-weight:800;color:#7C3AED;")
        lay.addWidget(hdr)
        sub = QLabel(
            "Wähle deine Hochschule und deinen Studiengang — die Module werden "
            "lokal importiert. Keine Internetverbindung nötig."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("font-size:12px;color:#706C86;")
        lay.addWidget(sub)

        # Auswahl-Reihe
        sel_row = QHBoxLayout()
        sel_row.setSpacing(12)

        sel_row.addWidget(QLabel("Hochschule:"))
        self._fh_cb = QComboBox()
        self._fh_cb.setMinimumWidth(200)
        for hs in self._db.get("hochschulen", []):
            self._fh_cb.addItem(hs["kuerzel"], hs)
        self._fh_cb.currentIndexChanged.connect(self._on_fh_changed)
        sel_row.addWidget(self._fh_cb)

        sel_row.addWidget(QLabel("Studiengang:"))
        self._sg_cb = QComboBox()
        self._sg_cb.setMinimumWidth(220)
        self._sg_cb.currentIndexChanged.connect(self._on_sg_changed)
        sel_row.addWidget(self._sg_cb)
        sel_row.addStretch()
        lay.addLayout(sel_row)

        # Modul-Tabelle
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["", "Modul", "ECTS", "Semester", "Typ"])
        self._table.horizontalHeader().setSectionResizeMode(1, QAbstractItemView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setAlternatingRowColors(True)
        lay.addWidget(self._table, 1)

        # Info
        self._info_lbl = QLabel("")
        self._info_lbl.setStyleSheet("font-size:11px;color:#706C86;")
        lay.addWidget(self._info_lbl)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        sel_all_btn = QPushButton("Alle auswählen")
        sel_all_btn.setObjectName("SecondaryBtn")
        sel_all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(sel_all_btn)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._import_btn = QPushButton("✅  Module importieren")
        self._import_btn.setObjectName("PrimaryBtn")
        self._import_btn.clicked.connect(self._do_import)
        btn_row.addWidget(self._import_btn)
        lay.addLayout(btn_row)

        # Initial befüllen
        self._on_fh_changed()

    def _on_fh_changed(self):
        self._sg_cb.blockSignals(True)
        self._sg_cb.clear()
        hs = self._fh_cb.currentData()
        if hs:
            for sg in hs.get("studiengaenge", []):
                self._sg_cb.addItem(sg["name"], sg)
        self._sg_cb.blockSignals(False)
        self._on_sg_changed()

    def _on_sg_changed(self):
        sg = self._sg_cb.currentData()
        self._table.setRowCount(0)
        if not sg:
            return
        module = sg.get("module", [])
        self._table.setRowCount(len(module))
        for row, m in enumerate(module):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked)
            self._table.setItem(row, 0, chk)
            self._table.setItem(row, 1, QTableWidgetItem(m["name"]))
            self._table.setItem(row, 2, QTableWidgetItem(str(m["ects"])))
            self._table.setItem(row, 3, QTableWidgetItem(f"Semester {m['semester']}"))
            self._table.setItem(row, 4, QTableWidgetItem(m.get("typ", "Pflicht")))
            for col in range(1, 5):
                item = self._table.item(row, col)
                if item:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        total_ects = sum(m["ects"] for m in module)
        self._info_lbl.setText(
            f"{len(module)} Module · {total_ects} ECTS total · "
            f"Abschluss: {sg.get('abschluss','BSc')}"
        )

    def _select_all(self):
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)

    def _do_import(self):
        sg = self._sg_cb.currentData()
        hs = self._fh_cb.currentData()
        if not sg or not hs:
            return

        module = sg.get("module", [])
        imported = 0
        skipped = 0
        existing_names = {m["name"].lower() for m in self.repo.list_modules("all")}

        for row in range(self._table.rowCount()):
            chk = self._table.item(row, 0)
            if not chk or chk.checkState() != Qt.Checked:
                continue
            m = module[row]
            if m["name"].lower() in existing_names:
                skipped += 1
                continue
            self.repo.add_module({
                "name": m["name"],
                "ects": m["ects"],
                "semester": str(m["semester"]),
                "status": "planned",
                "module_type": m.get("typ", "Pflicht"),
                "weighting": float(m.get("gewichtung", 1.0)),
            })
            imported += 1

        msg = f"✅  {imported} Module importiert"
        if skipped:
            msg += f"\n⚠  {skipped} bereits vorhanden (übersprungen)"
        QMessageBox.information(self, "Import abgeschlossen", msg)
        self.accept()
