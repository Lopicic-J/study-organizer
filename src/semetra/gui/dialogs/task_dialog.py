from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QTextEdit, QDateEdit, QDialogButtonBox,
    QMessageBox, QPushButton, QLabel, QFrame, QFileDialog,
    QScrollArea, QWidget, QSizePolicy, QInputDialog,
)
from PySide6.QtCore import Qt, QDate, QUrl
from PySide6.QtGui import QDesktopServices

from semetra.repo.sqlite_repo import SqliteRepo


# ── Helpers ─────────────────────────────────────────────────────────
_FILE_ICONS = {
    "pdf": "📄", "docx": "📝", "doc": "📝", "xlsx": "📊", "xls": "📊",
    "csv": "📊", "pptx": "📽️", "ppt": "📽️", "png": "🖼️", "jpg": "🖼️",
    "jpeg": "🖼️", "gif": "🖼️", "svg": "🖼️", "zip": "📦", "rar": "📦",
    "txt": "📃", "py": "🐍", "js": "📜", "ts": "📜", "html": "🌐",
    "mp4": "🎬", "mp3": "🎵",
}

def _icon_for(kind: str, file_type: str) -> str:
    if kind == "link":
        return "🔗"
    return _FILE_ICONS.get(file_type.lower(), "📎")

def _attachments_dir(repo: SqliteRepo) -> Path:
    """Return (and create) the local attachments directory next to study.db."""
    db = Path(repo.db_path) if hasattr(repo, "db_path") else Path("study.db")
    d = db.parent / "attachments"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _human_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    elif nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.0f} KB"
    else:
        return f"{nbytes / (1024 * 1024):.1f} MB"


# ── Task Dialog ─────────────────────────────────────────────────────
class TaskDialog(QDialog):
    def __init__(self, repo: SqliteRepo, task_id: Optional[int] = None,
                 default_module_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.task_id = task_id
        self.setWindowTitle("Aufgabe bearbeiten" if task_id else "Neue Aufgabe")
        self.setMinimumWidth(500)
        self._pending_files: list[dict] = []   # files to attach after task creation
        self._build()
        if task_id:
            self._load(task_id)
        elif default_module_id:
            self._set_module(default_module_id)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        form = QFormLayout()
        form.setSpacing(10)

        self.title = QLineEdit()
        self.module_cb = QComboBox()
        for m in self.repo.list_modules("all"):
            self.module_cb.addItem(m["name"], m["id"])

        self.priority = QComboBox()
        self.priority.addItems(["Critical", "High", "Medium", "Low"])
        self.priority.setCurrentIndex(2)
        self.status = QComboBox()
        self.status.addItems(["Open", "In Progress", "Done"])
        self.due_date = QDateEdit()
        self.due_date.setCalendarPopup(True)
        self.due_date.setDate(QDate.currentDate())
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)

        form.addRow("Titel *:", self.title)
        form.addRow("Modul:", self.module_cb)
        form.addRow("Priorität:", self.priority)
        form.addRow("Status:", self.status)
        form.addRow("Fällig:", self.due_date)
        form.addRow("Notizen:", self.notes)
        lay.addLayout(form)

        # ── Attachments section ─────────────────────────────────────
        att_frame = QFrame()
        att_frame.setObjectName("Card")
        att_frame.setAttribute(Qt.WA_StyledBackground, True)
        att_lay = QVBoxLayout(att_frame)
        att_lay.setContentsMargins(12, 10, 12, 10)
        att_lay.setSpacing(8)

        att_hdr = QHBoxLayout()
        att_title = QLabel("📎  Materialien & Links")
        att_title.setStyleSheet("font-size:13px; font-weight:bold;")
        att_hdr.addWidget(att_title)
        att_hdr.addStretch()

        self._btn_add_link = QPushButton("🔗 Link")
        self._btn_add_link.setFixedHeight(28)
        self._btn_add_link.setCursor(Qt.PointingHandCursor)
        self._btn_add_link.clicked.connect(self._add_link)
        att_hdr.addWidget(self._btn_add_link)

        self._btn_add_file = QPushButton("📁 Datei")
        self._btn_add_file.setFixedHeight(28)
        self._btn_add_file.setCursor(Qt.PointingHandCursor)
        self._btn_add_file.clicked.connect(self._add_file)
        att_hdr.addWidget(self._btn_add_file)
        att_lay.addLayout(att_hdr)

        # Scrollable attachment list
        self._att_scroll = QScrollArea()
        self._att_scroll.setWidgetResizable(True)
        self._att_scroll.setFrameShape(QFrame.NoFrame)
        self._att_scroll.setMaximumHeight(150)
        self._att_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        att_inner = QWidget()
        att_inner.setAttribute(Qt.WA_StyledBackground, False)
        self._att_list_layout = QVBoxLayout(att_inner)
        self._att_list_layout.setSpacing(4)
        self._att_list_layout.setContentsMargins(0, 0, 0, 0)
        self._att_list_layout.addStretch()
        self._att_scroll.setWidget(att_inner)
        att_lay.addWidget(self._att_scroll)

        self._att_empty_lbl = QLabel("Noch keine Materialien angehängt.")
        self._att_empty_lbl.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        self._att_empty_lbl.setAlignment(Qt.AlignCenter)
        att_lay.addWidget(self._att_empty_lbl)

        lay.addWidget(att_frame)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # ── Attachment UI helpers ───────────────────────────────────────
    def _refresh_attachments(self):
        """Rebuild the attachment list from DB + pending."""
        # Clear existing
        while self._att_list_layout.count():
            item = self._att_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        items: list[dict] = []

        # From DB (existing task)
        if self.task_id:
            for row in self.repo.list_task_attachments(self.task_id):
                items.append({
                    "id": row["id"], "kind": row["kind"], "label": row["label"],
                    "url": row["url"], "file_type": row["file_type"],
                    "file_size": row["file_size"], "pending": False,
                })

        # Pending (not yet saved)
        for p in self._pending_files:
            items.append({**p, "pending": True})

        self._att_empty_lbl.setVisible(len(items) == 0)
        self._att_scroll.setVisible(len(items) > 0)

        for item in items:
            row_w = QWidget()
            row_w.setAttribute(Qt.WA_StyledBackground, True)
            row_w.setStyleSheet(
                "background: #F9FAFB; border-radius: 8px; border: 1px solid #E5E7EB;"
            )
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(10, 6, 10, 6)
            row_l.setSpacing(8)

            icon = QLabel(_icon_for(item["kind"], item.get("file_type", "")))
            icon.setStyleSheet("font-size: 16px; background: transparent; border: none;")
            icon.setFixedWidth(22)
            row_l.addWidget(icon)

            label_text = item["label"] or item["url"]
            if len(label_text) > 45:
                label_text = label_text[:42] + "…"
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 12px; font-weight: 500; background: transparent; border: none;")
            lbl.setToolTip(item["url"])
            row_l.addWidget(lbl, 1)

            if item["kind"] == "file" and item.get("file_size", 0) > 0:
                size_lbl = QLabel(_human_size(item["file_size"]))
                size_lbl.setStyleSheet("font-size: 10px; color: #9CA3AF; background: transparent; border: none;")
                row_l.addWidget(size_lbl)

            # Open button
            open_btn = QPushButton("Öffnen")
            open_btn.setFixedHeight(24)
            open_btn.setFixedWidth(60)
            open_btn.setCursor(Qt.PointingHandCursor)
            open_btn.setStyleSheet("font-size: 11px;")
            url = item["url"]
            open_btn.clicked.connect(lambda checked=False, u=url: self._open_attachment(u))
            row_l.addWidget(open_btn)

            # Delete button
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet("font-size: 12px; color: #EF4444; background: transparent; border: none;")
            if item.get("pending"):
                idx = self._pending_files.index(item) if item in self._pending_files else -1
                del_btn.clicked.connect(lambda checked=False, i=idx: self._remove_pending(i))
            else:
                aid = item["id"]
                del_btn.clicked.connect(lambda checked=False, a=aid: self._delete_attachment(a))
            row_l.addWidget(del_btn)

            self._att_list_layout.insertWidget(self._att_list_layout.count() - 1, row_w)

    def _open_attachment(self, url: str):
        """Open a link in browser or a file in default app."""
        if url.startswith("http://") or url.startswith("https://"):
            QDesktopServices.openUrl(QUrl(url))
        elif os.path.exists(url):
            QDesktopServices.openUrl(QUrl.fromLocalFile(url))
        else:
            QMessageBox.warning(self, "Nicht gefunden", f"Datei nicht gefunden:\n{url}")

    def _add_link(self):
        url, ok = QInputDialog.getText(self, "Link hinzufügen", "URL:")
        if not ok or not url.strip():
            return
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        label, _ = QInputDialog.getText(self, "Bezeichnung", "Name (optional):", text=url)
        label = (label or "").strip() or url

        if self.task_id:
            self.repo.add_task_attachment(self.task_id, kind="link", label=label, url=url)
        else:
            self._pending_files.append({"kind": "link", "label": label, "url": url, "file_type": "", "file_size": 0})
        self._refresh_attachments()

    def _add_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Dateien auswählen", "",
            "Alle Dateien (*);;PDF (*.pdf);;Word (*.docx *.doc);;Excel (*.xlsx *.xls);;Bilder (*.png *.jpg *.jpeg)"
        )
        if not paths:
            return
        for src_path in paths:
            src = Path(src_path)
            ext = src.suffix.lstrip(".").lower()
            size = src.stat().st_size

            # Copy file to attachments dir
            dest_dir = _attachments_dir(self.repo)
            # Make unique name
            dest = dest_dir / src.name
            if dest.exists():
                stem = src.stem
                i = 1
                while dest.exists():
                    dest = dest_dir / f"{stem}_{i}{src.suffix}"
                    i += 1
            shutil.copy2(str(src), str(dest))

            if self.task_id:
                self.repo.add_task_attachment(
                    self.task_id, kind="file", label=src.name,
                    url=str(dest), file_type=ext, file_size=size,
                )
            else:
                self._pending_files.append({
                    "kind": "file", "label": src.name, "url": str(dest),
                    "file_type": ext, "file_size": size,
                })
        self._refresh_attachments()

    def _delete_attachment(self, aid: int):
        self.repo.delete_task_attachment(aid)
        self._refresh_attachments()

    def _remove_pending(self, idx: int):
        if 0 <= idx < len(self._pending_files):
            self._pending_files.pop(idx)
        self._refresh_attachments()

    # ── Existing methods ────────────────────────────────────────────
    def _set_module(self, mid: int):
        for i in range(self.module_cb.count()):
            if self.module_cb.itemData(i) == mid:
                self.module_cb.setCurrentIndex(i)
                break

    def _load(self, tid: int):
        t = self.repo.get_task(tid)
        if not t:
            return
        self.title.setText(t["title"])
        self._set_module(t["module_id"])
        idx = self.priority.findText(t["priority"])
        if idx >= 0:
            self.priority.setCurrentIndex(idx)
        idx2 = self.status.findText(t["status"])
        if idx2 >= 0:
            self.status.setCurrentIndex(idx2)
        if t["due_date"]:
            try:
                d = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
                self.due_date.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                pass
        self.notes.setPlainText(t["notes"] or "")
        self._refresh_attachments()

    def _accept(self):
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        mid = self.module_cb.currentData()
        due = self.due_date.date().toString("yyyy-MM-dd")
        if self.task_id:
            self.repo.update_task(
                self.task_id,
                title=title, module_id=mid,
                priority=self.priority.currentText(),
                status=self.status.currentText(),
                due_date=due, notes=self.notes.toPlainText(),
            )
        else:
            self.task_id = self.repo.add_task(
                mid, title,
                priority=self.priority.currentText(),
                status=self.status.currentText(),
                due_date=due, notes=self.notes.toPlainText(),
            )
            # Save pending attachments
            for p in self._pending_files:
                self.repo.add_task_attachment(
                    self.task_id, kind=p["kind"], label=p["label"],
                    url=p["url"], file_type=p.get("file_type", ""),
                    file_size=p.get("file_size", 0),
                )
        self.accept()
