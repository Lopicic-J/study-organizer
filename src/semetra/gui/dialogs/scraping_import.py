"""Universal PDF, Excel, and JSON scraping import dialog."""

import sys
from typing import Any, Dict, List, Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFrame, QProgressBar, QTableWidget, QTableWidgetItem, QCheckBox,
    QWidget, QSpinBox, QFileDialog, QMessageBox, QDialogButtonBox,
    QAbstractItemView, QHeaderView, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.colors import _tc
from semetra.gui.i18n import tr


class ScrapingImportDialog(QDialog):
    """
    Universal PDF scraping import dialog.
    Lets users pick PDF module-plan files (any school), scrapes them,
    previews the results, and imports selected modules + their scraped
    learning objectives / content sections / assessment data.
    """

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setAcceptDrops(True)            # enable drag-and-drop for the whole dialog
        self.repo = repo
        self._scraped: List[Dict[str, Any]] = []      # raw scraper results
        self._checkboxes: List[QCheckBox] = []       # one per scraped item (checkbox col)
        self._semester_spinboxes: List[QSpinBox] = [] # one per scraped item (semester col)
        self.setWindowTitle("Scraping Import – PDFs, Excel & JSON")
        self.setMinimumWidth(760)
        self.setMinimumHeight(560)
        self._build()

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _best_start_dir() -> str:
        """
        Return the most useful starting directory for file dialogs.
        Prefers the mounted workspace root so Windows files are reachable.
        """
        candidates = [
            "/sessions/hopeful-keen-fermat/mnt",   # Cowork VM mount root
            str(Path.home() / "Documents"),
            str(Path.home() / "Desktop"),
            str(Path.home()),
        ]
        for c in candidates:
            if Path(c).is_dir():
                return c
        return ""

    @staticmethod
    def _build_mount_map() -> List[tuple]:
        """
        Read /proc/mounts and return [(virtiofs_source, vm_mount_point), ...]
        for every virtiofs entry that exposes Windows user files.
        Sorted longest-source-first so more-specific paths match first.
        """
        entries: List[tuple] = []
        try:
            with open("/proc/mounts") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    src, mnt = parts[0], parts[1]
                    if src.startswith("/mnt/.virtiofs-root/shared/"):
                        entries.append((src.rstrip("/"), mnt.rstrip("/")))
        except Exception:
            pass
        entries.sort(key=lambda t: len(t[0]), reverse=True)
        return entries

    @staticmethod
    def _resolve_path(raw: str) -> str:
        """
        Translate any path format to something accessible on the current system.

        Handles three environments automatically:
          1. Native Windows  – path works as-is
          2. WSL / WSL2      – C:\\... becomes /mnt/c/...
          3. Cowork VM       – C:\\... resolved via /proc/mounts virtiofs map
        """
        import re as _re
        raw = raw.strip().strip('"').strip("'")
        if not raw:
            return ""

        # 1. Already accessible (native Windows path or valid Linux path)
        if Path(raw).exists():
            return raw

        # 2. Detect Windows-style path:  C:\...  or  C:/...
        m = _re.match(r"^([A-Za-z]):[/\\](.*)", raw)
        if not m:
            return raw  # unrecognised format, return as-is

        drive = m.group(1).lower()              # e.g. "c"
        rest  = m.group(2).replace("\\", "/")   # e.g. "Users/foo/Documents/pdfs"

        # 3. WSL-style mount:  /mnt/c/Users/...
        wsl = f"/mnt/{drive}/{rest}"
        if Path(wsl).exists():
            return wsl

        # 4. Cowork virtiofs via /proc/mounts
        rel_home = _re.sub(r"^Users/[^/]+/", "", rest)
        virtiofs = "/mnt/.virtiofs-root/shared/" + rel_home
        for src, mnt_pt in ScrapingImportDialog._build_mount_map():
            if virtiofs == src:
                return mnt_pt
            if virtiofs.startswith(src + "/"):
                return mnt_pt + virtiofs[len(src):]
        try:
            if Path(virtiofs).exists():
                return virtiofs
        except PermissionError:
            pass

        # 5. Nothing worked – return WSL path so the error message is readable
        return wsl

    # ── Drag & Drop ────────────────────────────────────────────────────────

    _SUPPORTED_EXTS = (".pdf", ".xlsx", ".xls", ".json")

    def _is_supported_file(self, path: str) -> bool:
        return Path(path).suffix.lower() in self._SUPPORTED_EXTS

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            files = [u.toLocalFile() for u in event.mimeData().urls()
                     if self._is_supported_file(u.toLocalFile())]
            if files:
                event.acceptProposedAction()
                self._drop_zone.setStyleSheet(self._drop_zone_active_style())
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._drop_zone.setStyleSheet(self._drop_zone_default_style())

    def dropEvent(self, event: QDropEvent):
        self._drop_zone.setStyleSheet(self._drop_zone_default_style())
        files = [u.toLocalFile() for u in event.mimeData().urls()
                 if self._is_supported_file(u.toLocalFile())]
        if files:
            self._run_import_by_type(sorted(files))

    def _drop_zone_default_style(self) -> str:
        return (
            f"QFrame{{border:2px dashed {_tc('#C8D8F8','#45475A')};"
            f"border-radius:10px;background:{_tc('#F5F8FF','#1E1E2E')};}}"
        )

    def _drop_zone_active_style(self) -> str:
        return (
            "QFrame{border:2px dashed #4A86E8;"
            "border-radius:10px;background:#EEF3FF;}"
        )

    # ── UI construction ────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # ── Path input bar (paste any path here) ──────────────────────────
        path_frame = QFrame()
        path_frame.setAttribute(Qt.WA_StyledBackground, True)
        path_frame.setStyleSheet(
            f"QFrame{{background:{_tc('#F0F4FF','#2A2A3E')};"
            f"border:1px solid {_tc('#C8D8F8','#45475A')};border-radius:8px;padding:2px;}}"
        )
        path_lay = QVBoxLayout(path_frame)
        path_lay.setContentsMargins(10, 8, 10, 8)
        path_lay.setSpacing(4)

        path_hint = QLabel(
            "💡  Pfad einfügen (Ctrl+V) — PDFs, Excel (.xlsx) und JSON werden unterstützt:"
        )
        path_hint.setStyleSheet("font-size:11px;font-weight:bold;")
        path_lay.addWidget(path_hint)

        path_input_row = QHBoxLayout()
        path_input_row.setSpacing(6)
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText(
            "z.B.  C:\\Users\\Name\\Documents\\pdfs  oder  /sessions/.../mnt/module_pdfs  (Ordner oder Datei: .pdf, .xlsx, .json)"
        )
        self._path_input.setFixedHeight(30)
        self._path_input.returnPressed.connect(self._load_path_input)
        path_input_row.addWidget(self._path_input, 1)

        load_btn = QPushButton("Laden ↵")
        load_btn.setObjectName("PrimaryBtn")
        load_btn.setFixedHeight(30)
        load_btn.clicked.connect(self._load_path_input)
        path_input_row.addWidget(load_btn)
        path_lay.addLayout(path_input_row)
        lay.addWidget(path_frame)

        # ── Drop zone with buttons ─────────────────────────────────────────
        self._drop_zone = QFrame()
        self._drop_zone.setFixedHeight(64)
        self._drop_zone.setStyleSheet(self._drop_zone_default_style())
        dz_lay = QHBoxLayout(self._drop_zone)
        dz_lay.setSpacing(12)
        dz_lay.setContentsMargins(16, 8, 16, 8)

        dz_icon = QLabel("📄")
        dz_icon.setStyleSheet("font-size:24px;")
        dz_lay.addWidget(dz_icon)

        dz_main = QLabel("PDF / Excel / JSON hier hineinziehen  —  oder:")
        dz_main.setStyleSheet("font-size:12px;")
        dz_lay.addWidget(dz_main)

        files_btn = QPushButton("📄 Dateien wählen")
        files_btn.setObjectName("PrimaryBtn")
        files_btn.setFixedHeight(28)
        files_btn.clicked.connect(self._pick_files)
        dz_lay.addWidget(files_btn)

        folder_btn = QPushButton("📁 Ordner wählen")
        folder_btn.setObjectName("SecondaryBtn")
        folder_btn.setFixedHeight(28)
        folder_btn.clicked.connect(self._pick_folder)
        dz_lay.addWidget(folder_btn)
        dz_lay.addStretch()
        lay.addWidget(self._drop_zone)

        # ── Select all / none row ─────────────────────────────────────────
        sel_row = QHBoxLayout()
        sel_all_btn = QPushButton("Alle auswählen")
        sel_all_btn.setObjectName("SecondaryBtn")
        sel_all_btn.setFixedHeight(24)
        sel_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        sel_row.addWidget(sel_all_btn)

        sel_none_btn = QPushButton("Keine")
        sel_none_btn.setObjectName("SecondaryBtn")
        sel_none_btn.setFixedHeight(24)
        sel_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        sel_row.addWidget(sel_none_btn)
        sel_row.addStretch()
        lay.addLayout(sel_row)

        # Progress bar (hidden until scraping)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(18)
        lay.addWidget(self.progress)

        # Preview table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "☑", "Code", "Modulname", "ECTS", "Semester", "Ziele", "Sektionen", "Prüfungen"
        ])
        self.table.horizontalHeaderItem(4).setToolTip(
            "Studiensemester (1–12). 0 = noch nicht zugeordnet.\n"
            "Für bereits vorhandene Module wird der gespeicherte Wert angezeigt."
        )
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        for c in (1, 3, 5, 6, 7):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        lay.addWidget(self.table, 1)

        # Status label
        self.status_lbl = QLabel("Noch keine Dateien geladen. (PDF, Excel, JSON werden unterstützt)")
        self.status_lbl.setStyleSheet("color: #706C86; font-size: 12px;")
        lay.addWidget(self.status_lbl)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.ok_btn = btns.button(QDialogButtonBox.Ok)
        self.ok_btn.setText("Importieren")
        self.ok_btn.setEnabled(False)
        btns.accepted.connect(self._do_import)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # ── File picking ───────────────────────────────────────────────────────

    def _load_path_input(self):
        """Load files from the path typed/pasted into the path bar."""
        raw = self._path_input.text().strip()
        if not raw:
            return
        resolved = self._resolve_path(raw)
        p = Path(resolved)
        if not p.exists():
            QMessageBox.warning(
                self, "Pfad nicht gefunden",
                f"Der Pfad existiert nicht oder ist nicht zugänglich:\n{resolved}\n\n"
                "Tipp: Nutze den Dateiauswahl-Dialog und navigiere zu deinem Ordner."
            )
            return
        if p.is_dir():
            paths = sorted(
                str(f) for f in p.iterdir()
                if f.is_file() and f.suffix.lower() in self._SUPPORTED_EXTS
            )
            if not paths:
                QMessageBox.information(
                    self, "Keine Dateien",
                    f"Keine unterstützten Dateien (.pdf, .xlsx, .xls, .json) in:\n{resolved}"
                )
                return
        elif p.suffix.lower() in self._SUPPORTED_EXTS:
            paths = [str(p)]
        else:
            QMessageBox.warning(
                self, "Ungültiger Pfad",
                "Bitte einen Ordner oder eine Datei (.pdf, .xlsx, .xls, .json) angeben."
            )
            return
        self._run_import_by_type(paths)

    def _pick_files(self):
        start = self._best_start_dir()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Dateien wählen", start,
            "Alle unterstützten Dateien (*.pdf *.xlsx *.xls *.json);;"
            "PDF Dateien (*.pdf);;"
            "Excel Dateien (*.xlsx *.xls);;"
            "JSON Dateien (*.json)"
        )
        if paths:
            self._run_import_by_type(paths)

    def _pick_folder(self):
        start = self._best_start_dir()
        folder = QFileDialog.getExistingDirectory(
            self, "Ordner mit Moduldaten wählen", start
        )
        if folder:
            paths = sorted(
                str(f) for f in Path(folder).iterdir()
                if f.is_file() and f.suffix.lower() in self._SUPPORTED_EXTS
            )
            if paths:
                self._run_import_by_type(paths)
            else:
                QMessageBox.information(
                    self, "Keine Dateien",
                    "In diesem Ordner wurden keine unterstützten Dateien (.pdf, .xlsx, .xls, .json) gefunden."
                )

    # ── Scraping / Import dispatcher ───────────────────────────────────────

    def _run_import_by_type(self, paths: List[str]):
        """Dispatch files to the appropriate importer based on extension."""
        pdfs    = [p for p in paths if Path(p).suffix.lower() == ".pdf"]
        structs = [p for p in paths if Path(p).suffix.lower() in (".xlsx", ".xls", ".json")]

        self._scraped = []

        if pdfs:
            self._run_scraper(pdfs, append=True)
        if structs:
            self._run_structured_import(structs, append=True)

        if not self._scraped:
            return
        self._populate_table()

    def _run_scraper(self, paths: List[str], append: bool = False):
        """Scrape PDF files. If pdfplumber is missing, offer to auto-install it."""
        import subprocess as _sp

        try:
            from semetra.adapters.pdf_scraper import scrape_module_pdf
        except ImportError:
            reply = QMessageBox.question(
                self, "pdfplumber nicht installiert",
                "pdfplumber ist zum Lesen von PDFs erforderlich, aber nicht installiert.\n\n"
                "Jetzt automatisch installieren?\n(pip install pdfplumber)",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            self.status_lbl.setText("⏳ Installiere pdfplumber …")
            QApplication.processEvents()
            res = _sp.run(
                [sys.executable, "-m", "pip", "install", "pdfplumber", "--quiet"],
                capture_output=True, text=True,
            )
            if res.returncode != 0:
                QMessageBox.critical(
                    self, "Installation fehlgeschlagen",
                    f"pdfplumber konnte nicht installiert werden:\n{res.stderr[:500]}"
                )
                return
            # Invalidate import cache so the newly-installed module is found
            import importlib
            import semetra.adapters.pdf_scraper as _pm
            importlib.reload(_pm)
            from semetra.adapters.pdf_scraper import scrape_module_pdf

        if not append:
            self._scraped = []

        self.progress.setVisible(True)
        self.progress.setMaximum(len(paths))
        self.progress.setValue(0)

        for i, p in enumerate(paths):
            self.progress.setValue(i + 1)
            label = Path(p).name[:40]
            self.progress.setFormat(f"PDF {i+1}/{len(paths)}: {label}")
            QApplication.processEvents()
            self._scraped.append(scrape_module_pdf(p))

        self.progress.setVisible(False)
        if not append:
            self._populate_table()

    def _run_structured_import(self, paths: List[str], append: bool = False):
        """Import Excel / JSON files using the structured scraper."""
        try:
            from semetra.adapters.structured_scraper import parse_file
        except ImportError as e:
            QMessageBox.critical(self, "Import-Fehler", str(e))
            return

        if not append:
            self._scraped = []

        self.progress.setVisible(True)
        self.progress.setMaximum(len(paths))
        self.progress.setValue(0)

        for i, p in enumerate(paths):
            self.progress.setValue(i + 1)
            label = Path(p).name[:40]
            self.progress.setFormat(f"Import {i+1}/{len(paths)}: {label}")
            QApplication.processEvents()
            results = parse_file(p)
            self._scraped.extend(results)

        self.progress.setVisible(False)
        if not append:
            self._populate_table()

    # ── Table population ───────────────────────────────────────────────────

    def _build_existing_maps(self):
        """Return (name→id, code→id) maps from the current DB modules."""
        by_name: Dict[str, int] = {}
        by_code: Dict[str, int] = {}
        for row in self.repo.list_modules("all"):
            mid = row["id"]
            by_name[row["name"].lower()] = mid
            code = (row["code"] or "").strip()
            if code:
                by_code[code.lower()] = mid
        return by_name, by_code

    def _find_existing(self, sc: Dict[str, Any],
                        by_name: Dict[str, int],
                        by_code:  Dict[str, int]) -> Optional[int]:
        """
        Return the DB module_id that matches this scraped entry, or None.

        Matching order:
          1. Exact name  (case-insensitive)
          2. Code stored in DB matches scraped code
          3. Scraped code equals an existing module's name
             e.g. existing name="DevOps", scraped code="DevOps" → match
          4. Old-style "CODE Name" — modules created before the code column
             e.g. existing "AnPy Analyse mit Python" matches new code="AnPy"
          5. Scraped name is a substring of an existing module name
        """
        # 1. Exact name match
        mid = by_name.get(sc["name"].lower())
        if mid:
            return mid

        code = (sc.get("code") or "").strip()

        # 2. Code match (code stored in DB)
        if code:
            mid = by_code.get(code.lower())
            if mid:
                return mid

        # 3. Scraped code equals an existing module's name
        #    e.g. user manually created "DevOps"; PDF gives code="DevOps", name="Development Ops"
        if code:
            mid = by_name.get(code.lower())
            if mid:
                return mid

        # 4. Old "CODE Name" prefix pattern
        if code:
            prefix = code.lower() + " "
            for existing_name, mid in by_name.items():
                if existing_name.startswith(prefix):
                    return mid

        # 5. Scraped name is a substring of an existing module name
        new_name = sc["name"].lower().strip()
        if len(new_name) > 5:
            for existing_name, mid in by_name.items():
                if new_name in existing_name:
                    return mid

        return None

    def _populate_table(self):
        self.table.setRowCount(0)
        self._checkboxes = []
        self._semester_spinboxes = []
        by_name, by_code = self._build_existing_maps()

        # Pre-load DB semester values for matched modules
        all_db_mods = {row["id"]: row for row in self.repo.list_modules("all")}

        for r, sc in enumerate(self._scraped):
            self.table.insertRow(r)
            existing_id = self._find_existing(sc, by_name, by_code)
            is_existing = existing_id is not None

            # Checkbox — pre-select only new modules
            cb = QCheckBox()
            cb.setChecked(not is_existing)
            cb_widget = QWidget()
            cb_lay = QHBoxLayout(cb_widget)
            cb_lay.addWidget(cb)
            cb_lay.setAlignment(Qt.AlignCenter)
            cb_lay.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(r, 0, cb_widget)
            self._checkboxes.append(cb)

            # Data columns
            self.table.setItem(r, 1, QTableWidgetItem(sc["code"]))
            name_item = QTableWidgetItem(sc["name"])
            if is_existing:
                name_item.setForeground(QColor("#F39C12"))
                name_item.setToolTip("⚠ Modul bereits vorhanden (Scraping-Daten werden aktualisiert)")
            self.table.setItem(r, 2, name_item)
            self.table.setItem(r, 3, QTableWidgetItem(str(sc["ects"])))

            # Semester spinbox — pre-fill with DB value for existing modules
            sem_spin = QSpinBox()
            sem_spin.setRange(0, 12)
            sem_spin.setSpecialValueText("—")   # 0 shows as "—" (not assigned)
            sem_spin.setToolTip("Studiensemester (0 = noch nicht zugeordnet)")
            sem_spin.setFixedWidth(52)
            sem_spin.setAlignment(Qt.AlignCenter)
            if is_existing and existing_id in all_db_mods:
                db_sem = str(all_db_mods[existing_id]["semester"]).strip()
                sem_spin.setValue(int(db_sem) if db_sem.isdigit() else 0)
            else:
                sem_spin.setValue(0)
            sem_widget = QWidget()
            sl = QHBoxLayout(sem_widget)
            sl.addWidget(sem_spin)
            sl.setAlignment(Qt.AlignCenter)
            sl.setContentsMargins(2, 0, 2, 0)
            self.table.setCellWidget(r, 4, sem_widget)
            self._semester_spinboxes.append(sem_spin)

            self.table.setItem(r, 5, QTableWidgetItem(str(len(sc["objectives"]))))
            self.table.setItem(r, 6, QTableWidgetItem(str(len(sc["content_sections"]))))
            self.table.setItem(r, 7, QTableWidgetItem(str(len(sc["assessments"]))))

            # Colour-code errors
            if sc.get("_error"):
                for c in (1, 2, 3, 5, 6, 7):
                    item = self.table.item(r, c)
                    if item:
                        item.setForeground(QColor("#E74C3C"))
                name_item.setToolTip(f"Fehler: {sc['_error']}")

        n = len(self._scraped)
        total_ects = sum(s["ects"] for s in self._scraped)
        self.status_lbl.setText(
            f"{n} Eintrag{'' if n == 1 else 'e'} geladen  ·  {total_ects:.0f} ECTS total  "
            f"·  Orange = bereits vorhanden (Scraping-Daten werden aktualisiert)"
        )
        self.ok_btn.setEnabled(n > 0)

    def _set_all_checked(self, state: bool):
        for cb in self._checkboxes:
            cb.setChecked(state)

    # ── Import ─────────────────────────────────────────────────────────────

    def _do_import(self):
        by_name, by_code = self._build_existing_maps()
        created, updated, skipped = 0, 0, 0

        for i, sc in enumerate(self._scraped):
            if i >= len(self._checkboxes) or not self._checkboxes[i].isChecked():
                skipped += 1
                continue

            # Read semester from spinbox (0 = "—" = not assigned)
            sem_val = (self._semester_spinboxes[i].value()
                       if i < len(self._semester_spinboxes) else 0)
            sem_str = str(sem_val) if sem_val > 0 else ""

            existing_id = self._find_existing(sc, by_name, by_code)
            if existing_id:
                # Module already in DB – update scraped data + correct name/code
                upd: Dict[str, Any] = {}
                if sc["ects"] > 0:
                    upd["ects"] = sc["ects"]
                if sc.get("code"):
                    upd["code"] = sc["code"]
                # Update semester only if user explicitly set a value (> 0)
                if sem_val > 0:
                    upd["semester"] = sem_str
                # If the stored name looks like "AnPy Analyse mit Python" and we now
                # have the proper name "Analyse mit Python", update it
                stored_name = next(
                    (row["name"] for row in self.repo.list_modules("all")
                     if row["id"] == existing_id), ""
                )
                if sc["name"] and stored_name.lower() != sc["name"].lower():
                    upd["name"] = sc["name"]
                if upd:
                    self.repo.update_module(existing_id, **upd)
                self.repo.save_scraped_data(existing_id, sc)
                # Keep maps in sync so later duplicates within the same batch collapse
                by_name[sc["name"].lower()] = existing_id
                if sc.get("code"):
                    by_code[sc["code"].lower()] = existing_id
                updated += 1
            else:
                # Create new module — use spinbox semester (empty if not set)
                mod_data = {
                    "name": sc["name"],
                    "code": sc.get("code", ""),
                    "semester": sem_str,
                    "ects": sc["ects"],
                    "lecturer": "",
                    "link": "",
                    "status": "planned",
                    "exam_date": "",
                    "weighting": 1.0,
                    "github_link": "",
                    "sharepoint_link": "",
                    "literature_links": "",
                    "notes_link": "",
                }
                mod_id = self.repo.add_module(mod_data)
                self.repo.save_scraped_data(mod_id, sc)
                # Register in maps to prevent duplicates within the same batch
                by_name[sc["name"].lower()] = mod_id
                if sc.get("code"):
                    by_code[sc["code"].lower()] = mod_id
                created += 1

        parts = []
        if created:
            parts.append(f"✓ {created} neue Module erstellt")
        if updated:
            parts.append(f"↻ {updated} Module aktualisiert (Titel + Scraping-Daten)")
        if skipped:
            parts.append(f"— {skipped} übersprungen")
        QMessageBox.information(self, "Import abgeschlossen", "\n".join(parts) or "Keine Änderungen.")
        self.accept()
