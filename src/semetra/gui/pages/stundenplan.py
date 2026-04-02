"""Timetable/Stundenplan page."""
from __future__ import annotations
import re

from datetime import date, datetime, timedelta
from typing import Optional, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDialog,
    QSizePolicy, QGridLayout, QScrollArea, QFileDialog,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import make_scroll
from semetra.gui.colors import _tc
from semetra.gui.i18n import tr



class StundenplanPage(QWidget):
    """
    Interaktive Wochenplan-Ansicht.
    Manueller Eintrag kostenlos · PDF / Excel / Bild-Import (Pro).
    """

    DAYS_LONG  = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
                  "Freitag", "Samstag", "Sonntag"]
    DAYS_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    HOURS      = list(range(7, 22))   # 07:00 – 21:00
    N_DAYS     = 7

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._build()

    # ── Build UI ─────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(14)

        # ── Header ────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("🗓  Stundenplan")
        title.setObjectName("SectionTitle")
        hdr.addWidget(title)
        hdr.addStretch()

        clr_btn = QPushButton("🗑 Alles leeren")
        clr_btn.setObjectName("SecondaryBtn")
        clr_btn.setFixedHeight(30)
        clr_btn.setStyleSheet("QPushButton{font-size:11px;padding:4px 10px;border-radius:8px;}")
        clr_btn.clicked.connect(self._clear_all)
        hdr.addWidget(clr_btn)

        add_btn = QPushButton("+ Eintrag")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.setFixedHeight(32)
        add_btn.clicked.connect(lambda: self._add_entry())
        hdr.addWidget(add_btn)

        imp_btn = QPushButton("📄 Import  ⭐")
        imp_btn.setObjectName("SecondaryBtn")
        imp_btn.setFixedHeight(32)
        imp_btn.setToolTip("PDF, Excel oder Bild importieren (Pro-Funktion)")
        imp_btn.clicked.connect(self._import_file)
        hdr.addWidget(imp_btn)

        lay.addLayout(hdr)

        # ── Info hint ─────────────────────────────────────────────────────
        info = QLabel(
            "💡  Klick auf eine leere Zelle zum Hinzufügen  ·  "
            "Klick auf einen Eintrag zum Bearbeiten/Löschen"
        )
        info.setStyleSheet("color:#9CA3AF;font-size:12px;")
        lay.addWidget(info)

        # ── Grid scroll area ──────────────────────────────────────────────
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setFrameShape(QFrame.NoFrame)
        self._grid_scroll.setWidgetResizable(True)
        self._grid_w = QWidget()
        self._grid_w.setAttribute(Qt.WA_StyledBackground, True)
        self._grid_lay = QGridLayout(self._grid_w)
        self._grid_lay.setSpacing(2)
        self._grid_lay.setContentsMargins(0, 0, 4, 0)
        self._grid_scroll.setWidget(self._grid_w)
        lay.addWidget(self._grid_scroll, 1)

        self._rebuild_grid()

    # ── Grid building ─────────────────────────────────────────────────────

    def _rebuild_grid(self):
        """Clear and rebuild the full timetable grid from DB data."""
        # Remove all widgets
        while self._grid_lay.count():
            item = self._grid_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Load entries
        from collections import defaultdict
        all_entries = [dict(r) for r in self._repo.list_stundenplan()]
        slot_map: dict = defaultdict(list)
        for entry in all_entries:
            day = entry["day_of_week"]
            try:
                h = int(entry["time_from"].split(":")[0])
            except Exception:
                h = 7
            h = max(self.HOURS[0], min(h, self.HOURS[-1]))
            slot_map[(day, h)].append(entry)

        # Column sizing
        self._grid_lay.setColumnMinimumWidth(0, 58)
        for c in range(1, self.N_DAYS + 1):
            self._grid_lay.setColumnStretch(c, 1)

        # ── Header row ────────────────────────────────────────────────
        self._grid_lay.addWidget(self._hdr_cell("Zeit", is_time=True), 0, 0)
        for c, (long_name, short_name) in enumerate(
                zip(self.DAYS_LONG, self.DAYS_SHORT), start=1):
            self._grid_lay.addWidget(
                self._hdr_cell(short_name, is_weekend=(c >= 6), tooltip=long_name),
                0, c
            )
        self._grid_lay.setRowMinimumHeight(0, 36)

        # ── Time-slot rows ────────────────────────────────────────────
        for row_idx, hour in enumerate(self.HOURS, start=1):
            # Time label
            time_lbl = QLabel(f"{hour:02d}:00")
            time_lbl.setFixedWidth(58)
            time_lbl.setAlignment(Qt.AlignCenter | Qt.AlignTop)
            time_lbl.setStyleSheet(
                "font-size:11px;color:#9CA3AF;padding-top:10px;background:transparent;"
            )
            self._grid_lay.addWidget(time_lbl, row_idx, 0)

            # Day cells
            for col_idx in range(self.N_DAYS):
                entries = slot_map.get((col_idx, hour), [])
                self._grid_lay.addWidget(
                    self._make_cell(entries, col_idx, hour),
                    row_idx, col_idx + 1
                )
            self._grid_lay.setRowMinimumHeight(row_idx, 58)

    @staticmethod
    def _hdr_cell(text: str, is_time: bool = False, is_weekend: bool = False,
                  tooltip: str = "") -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setAttribute(Qt.WA_StyledBackground, True)
        if is_time:
            lbl.setStyleSheet(
                "font-size:11px;font-weight:bold;color:#9CA3AF;background:transparent;")
        elif is_weekend:
            lbl.setStyleSheet(
                "font-size:12px;font-weight:bold;color:#9CA3AF;"
                "background:#F9FAFB;border-radius:8px 8px 0 0;padding:6px 4px;")
        else:
            lbl.setStyleSheet(
                "font-size:12px;font-weight:bold;color:#374151;"
                "background:#F3F0FF;border-radius:8px 8px 0 0;padding:6px 4px;")
        if tooltip:
            lbl.setToolTip(tooltip)
        return lbl

    def _make_cell(self, entries: list, day: int, hour: int) -> QWidget:
        """Build one timetable cell (empty or with lesson cards)."""
        cell = QWidget()
        cell.setAttribute(Qt.WA_StyledBackground, True)
        is_weekend = day >= 5
        cell.setStyleSheet(
            "QWidget{"
            f"background:{'#F9FAFB' if is_weekend else '#FFFFFF'};"
            "border:1px solid #E5E7EB;border-radius:4px;"
            "}"
            "QWidget:hover{background:#F3F0FF;}"
        )
        cell_lay = QVBoxLayout(cell)
        cell_lay.setContentsMargins(3, 3, 3, 3)
        cell_lay.setSpacing(2)

        if entries:
            for entry in entries[:2]:
                cell_lay.addWidget(self._make_lesson_card(entry))
            if len(entries) > 2:
                more = QLabel(f"+{len(entries) - 2} weitere")
                more.setStyleSheet("color:#6B7280;font-size:10px;")
                cell_lay.addWidget(more)
            cell_lay.addStretch()
        else:
            cell_lay.addStretch()
            plus_lbl = QLabel("+")
            plus_lbl.setAlignment(Qt.AlignCenter)
            plus_lbl.setStyleSheet("color:#D1D5DB;font-size:22px;font-weight:300;")
            cell_lay.addWidget(plus_lbl)
            cell_lay.addStretch()
            cell.setCursor(Qt.PointingHandCursor)
            cell.mouseReleaseEvent = (
                lambda _ev, d=day, h=hour: self._add_entry(d, h)
            )
        return cell

    def _make_lesson_card(self, entry: dict) -> QFrame:
        """Compact colored lesson card for the grid."""
        color = entry.get("color", "#7C3AED")
        card = QFrame()
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(
            f"QFrame{{background:{color};border-radius:6px;border:none;}}"
            f"QFrame:hover{{opacity:0.85;}}"
        )
        card.setCursor(Qt.PointingHandCursor)
        card.setToolTip(
            f"{entry.get('subject','')}  {entry.get('time_from','')}–{entry.get('time_to','')}"
            + (f"\nRaum: {entry['room']}" if entry.get("room") else "")
            + (f"\nDozent: {entry['lecturer']}" if entry.get("lecturer") else "")
        )

        cl = QVBoxLayout(card)
        cl.setContentsMargins(6, 4, 6, 4)
        cl.setSpacing(1)

        subj_lbl = QLabel(entry.get("subject", ""))
        subj_lbl.setStyleSheet(
            "color:#FFFFFF;font-size:11px;font-weight:bold;background:transparent;")
        subj_lbl.setWordWrap(False)
        cl.addWidget(subj_lbl)

        detail_parts = [f"{entry.get('time_from','')}–{entry.get('time_to','')}"]
        if entry.get("room"):
            detail_parts.append(entry["room"])
        detail_lbl = QLabel("  ".join(detail_parts))
        detail_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.80);font-size:10px;background:transparent;")
        cl.addWidget(detail_lbl)

        card.mouseReleaseEvent = lambda _ev, en=entry: self._edit_entry(en)
        return card

    # ── Actions ───────────────────────────────────────────────────────────

    def _add_entry(self, day: int = None, hour: int = None):
        from semetra.gui.dialogs.stundenplan_entry import StundenplanEntryDialog
        dlg = StundenplanEntryDialog(
            self._repo, day=day, hour=hour, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._rebuild_grid()

    def _edit_entry(self, entry: dict):
        from semetra.gui.dialogs.stundenplan_entry import StundenplanEntryDialog
        dlg = StundenplanEntryDialog(self._repo, entry=entry, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._rebuild_grid()

    def _clear_all(self):
        all_entries = self._repo.list_stundenplan()
        if not all_entries:
            return
        reply = QMessageBox.question(
            self, "Stundenplan leeren",
            f"Wirklich alle {len(all_entries)} Einträge löschen?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._repo.clear_stundenplan()
            self._rebuild_grid()

    def _import_file(self):
        """Pro: Import timetable from PDF, Excel or image."""
        try:
            from semetra.infra.license import LicenseManager
            from semetra.gui.dialogs.pro_feature import ProFeatureDialog
            lm = LicenseManager(self._repo)
            if not lm.is_pro():
                ProFeatureDialog(self).exec()
                return
        except Exception:
            pass

        path, _ = QFileDialog.getOpenFileName(
            self, "Stundenplan importieren", "",
            "Unterstützte Dateien (*.pdf *.xlsx *.xls *.png *.jpg *.jpeg *.bmp);;"
            "PDF (*.pdf);;Excel (*.xlsx *.xls);;Bilder (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext in ("png", "jpg", "jpeg", "bmp"):
            self._show_image_reference(path)
        elif ext == "pdf":
            self._parse_pdf_import(path)
        elif ext in ("xlsx", "xls"):
            self._parse_excel_import(path)

    def _show_image_reference(self, path: str):
        dlg = QDialog(self)
        dlg.setWindowTitle("Stundenplan-Bild (Referenz)")
        dlg.resize(820, 580)
        lay = QVBoxLayout(dlg)
        info = QLabel(
            "📷  <b>Stundenplan-Bild</b> — nutze das Bild als Referenz und trage die Einträge manuell ein."
        )
        info.setTextFormat(Qt.RichText)
        lay.addWidget(info)
        pix = QPixmap(path)
        lbl = QLabel()
        if not pix.isNull():
            lbl.setPixmap(pix.scaled(780, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            lbl.setText("Bild konnte nicht geladen werden.")
        sa = QScrollArea()
        sa.setFrameShape(QFrame.NoFrame)
        sa.setWidget(lbl)
        sa.setWidgetResizable(True)
        lay.addWidget(sa, 1)
        btns = QHBoxLayout()
        close_b = QPushButton("Schließen")
        close_b.setObjectName("SecondaryBtn")
        close_b.clicked.connect(dlg.reject)
        add_b = QPushButton("+ Eintrag hinzufügen")
        add_b.setObjectName("PrimaryBtn")
        add_b.clicked.connect(lambda: (dlg.reject(), self._add_entry()))
        btns.addWidget(close_b)
        btns.addStretch()
        btns.addWidget(add_b)
        lay.addLayout(btns)
        dlg.exec()

    def _parse_pdf_import(self, path: str):
        try:
            import pdfplumber
            texts = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages[:4]:
                    t = page.extract_text() or ""
                    if t.strip():
                        texts.append(t)
            self._show_import_preview("PDF", "\n".join(texts))
        except Exception as exc:
            QMessageBox.warning(self, "PDF-Fehler",
                                f"PDF konnte nicht gelesen werden:\n{exc}")

    def _parse_excel_import(self, path: str):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, data_only=True)
            ws = wb.active
            lines = []
            for row in ws.iter_rows(max_row=40, values_only=True):
                row_str = "  |  ".join(
                    str(c) if c is not None else "" for c in (row or [])[:10]
                )
                if row_str.strip():
                    lines.append(row_str)
            self._show_import_preview("Excel", "\n".join(lines[:40]))
        except Exception as exc:
            QMessageBox.warning(self, "Excel-Fehler",
                                f"Excel konnte nicht gelesen werden:\n{exc}")

    def _show_import_preview(self, source: str, text: str):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{source}-Import — Vorschau")
        dlg.resize(620, 440)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(
            f"<b>📄 Extrahierter Text aus {source}</b><br>"
            "<small style='color:#6B7280;'>Trage die Daten anhand der Vorschau manuell in den Stundenplan ein.</small>"
        ))
        text_lbl = QLabel(text[:2500] + ("…" if len(text) > 2500 else ""))
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet("font-family:monospace;font-size:11px;")
        inner = QWidget()
        QVBoxLayout(inner).addWidget(text_lbl)
        sa = QScrollArea()
        sa.setFrameShape(QFrame.NoFrame)
        sa.setWidget(inner)
        sa.setWidgetResizable(True)
        lay.addWidget(sa, 1)
        btns = QHBoxLayout()
        cl = QPushButton("Schließen")
        cl.setObjectName("SecondaryBtn")
        cl.clicked.connect(dlg.reject)
        add = QPushButton("+ Eintrag hinzufügen")
        add.setObjectName("PrimaryBtn")
        add.clicked.connect(lambda: (dlg.reject(), self._add_entry()))
        btns.addWidget(cl)
        btns.addStretch()
        btns.addWidget(add)
        lay.addLayout(btns)
        dlg.exec()

    def refresh(self):
        self._rebuild_grid()


