"""Modules management page."""
from __future__ import annotations
import re

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QLineEdit, QDialog, QDialogButtonBox, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QComboBox as _QCBBase, QFormLayout, QGroupBox, QListWidget, QListWidgetItem,
    QProgressBar, QStackedWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import QComboBox, StatCard, make_scroll, ColorDot
from semetra.gui.helpers import mod_color, _active_sem_filter, _filter_mods_by_sem
from semetra.gui.colors import _tc
from semetra.gui.widgets.helpers import separator
from semetra.gui.i18n import tr
from semetra.gui.constants import PRIORITY_COLORS, STATUS_LABELS
from semetra.gui.platform import _open_url_safe



class ModulesPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._selected_id: Optional[int] = None
        self._global_refresh = None
        self._build()

    def set_global_refresh(self, cb):
        self._global_refresh = cb

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left panel
        left = QWidget()
        left.setObjectName("ModuleLeftPanel")
        left.setMinimumWidth(220)
        left.setMaximumWidth(320)
        left.setAttribute(Qt.WA_StyledBackground, True)
        llay = QVBoxLayout(left)
        llay.setContentsMargins(12, 16, 12, 12)
        llay.setSpacing(8)

        hdr = QHBoxLayout()
        title = QLabel(tr("page.modules"))
        title.setObjectName("SectionTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = QPushButton("+ Neu")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.setFixedHeight(30)
        add_btn.clicked.connect(self._add_module)
        hdr.addWidget(add_btn)
        llay.addLayout(hdr)

        # Import toolbar (second row) – compact, avoids overflow in narrow panel
        import_row = QHBoxLayout()
        import_row.setSpacing(4)
        import_row.setContentsMargins(0, 0, 0, 0)
        db_btn = QPushButton("🏫 FH-Datenbank")
        db_btn.setObjectName("SecondaryBtn")
        db_btn.setFixedHeight(28)
        db_btn.setToolTip("Module aus eingebauter FH-Datenbank importieren (offline)")
        db_btn.clicked.connect(self._import_fh_database)
        db_btn.setStyleSheet(
            "QPushButton{font-size:11px;padding:4px 8px;border-radius:8px;}"
        )
        import_row.addWidget(db_btn)
        import_btn = QPushButton("📄 PDF Import")
        import_btn.setObjectName("SecondaryBtn")
        import_btn.setFixedHeight(28)
        import_btn.setToolTip("Module aus PDF, Excel oder JSON lokal importieren")
        import_btn.clicked.connect(self._import_scraping)
        import_btn.setStyleSheet(
            "QPushButton{font-size:11px;padding:4px 8px;border-radius:8px;}"
        )
        import_row.addWidget(import_btn)
        import_row.addStretch()
        clear_all_btn = QPushButton("🗑 Alle")
        clear_all_btn.setObjectName("DangerBtn")
        clear_all_btn.setFixedHeight(28)
        clear_all_btn.setToolTip("Alle Module auf einmal löschen\n(z.B. nach einem Fehlimport)")
        clear_all_btn.clicked.connect(self._delete_all_modules)
        clear_all_btn.setStyleSheet(
            "QPushButton{font-size:11px;padding:4px 8px;border-radius:8px;}"
        )
        import_row.addWidget(clear_all_btn)
        llay.addLayout(import_row)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen...")
        self.search.textChanged.connect(self._populate_list)
        llay.addWidget(self.search)

        self.filter_cb = QComboBox()
        self.filter_cb.addItems(["Alle", "Aktiv", "Geplant", "Abgeschlossen", "Pausiert"])
        self.filter_cb.currentIndexChanged.connect(self._populate_list)
        llay.addWidget(self.filter_cb)

        self.mod_list = QListWidget()
        self.mod_list.setStyleSheet(
            "QListWidget { border: none; background: transparent; }"
            "QListWidget::item { border-radius: 8px; padding: 6px; margin: 2px; }"
            "QListWidget::item:selected { background: #EBF1FF; }"
        )
        self.mod_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # Use itemSelectionChanged (signal on QListWidget itself) instead of
        # selectionModel().selectionChanged — the selection model may be
        # replaced after clear(), which would silently break the connection.
        self.mod_list.itemSelectionChanged.connect(self._on_selection_changed)
        llay.addWidget(self.mod_list, 1)

        # Bulk-action bar — shown only when ≥2 modules are selected
        self._bulk_bar = QFrame()
        self._bulk_bar.setAttribute(Qt.WA_StyledBackground, True)
        self._bulk_bar.setStyleSheet(
            f"QFrame{{background:{_tc('#FFF3F3','#3B1F1F')};"
            f"border:1px solid {_tc('#F5C6C6','#7A3535')};"
            f"border-radius:8px;padding:2px;}}"
        )
        bb_lay = QHBoxLayout(self._bulk_bar)
        bb_lay.setContentsMargins(10, 6, 10, 6)
        bb_lay.setSpacing(8)
        self._bulk_lbl = QLabel("0 ausgewählt")
        self._bulk_lbl.setStyleSheet("font-size:12px;font-weight:bold;")
        bb_lay.addWidget(self._bulk_lbl, 1)
        bulk_del_btn = QPushButton("🗑 Alle löschen")
        bulk_del_btn.setObjectName("DangerBtn")
        bulk_del_btn.setFixedHeight(26)
        bulk_del_btn.clicked.connect(self._delete_selected)
        bb_lay.addWidget(bulk_del_btn)
        self._bulk_bar.hide()
        llay.addWidget(self._bulk_bar)

        outer.addWidget(left)

        # Right panel
        self.detail_stack = QStackedWidget()
        ph = QLabel("Wahle ein Modul aus der Liste")
        ph.setAlignment(Qt.AlignCenter)
        ph.setStyleSheet("color: #706C86; font-size: 14px;")
        self.detail_stack.addWidget(ph)
        self.detail_stack.addWidget(self._build_detail())
        outer.addWidget(self.detail_stack, 1)

    def _build_detail(self) -> QWidget:
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        self.detail_dot = ColorDot("#4A86E8", 14)
        hdr.addWidget(self.detail_dot)
        self.detail_name = QLabel("Modulname")
        self.detail_name.setObjectName("PageTitle")
        hdr.addWidget(self.detail_name, 1)
        edit_btn = QPushButton("Bearbeiten")
        edit_btn.setObjectName("SecondaryBtn")
        edit_btn.clicked.connect(self._edit_module)
        hdr.addWidget(edit_btn)
        del_btn = QPushButton("Löschen")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_module)
        hdr.addWidget(del_btn)
        lay.addLayout(hdr)

        self.detail_info = QLabel()
        self.detail_info.setStyleSheet("color: #706C86; font-size: 13px;")
        lay.addWidget(self.detail_info)

        prog_row = QHBoxLayout()
        self.detail_bar = QProgressBar()
        self.detail_bar.setFixedHeight(8)
        self.detail_bar.setTextVisible(False)
        prog_row.addWidget(self.detail_bar, 1)
        self.detail_prog_lbl = QLabel("0h / 0h")
        self.detail_prog_lbl.setStyleSheet("color: #706C86; font-size: 12px;")
        prog_row.addWidget(self.detail_prog_lbl)
        lay.addLayout(prog_row)

        lay.addWidget(separator())

        links_grp = QGroupBox("Links")
        links_lay = QFormLayout(links_grp)
        links_lay.setSpacing(6)
        self.lnk_course = QLabel()
        self.lnk_course.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.lnk_course.linkActivated.connect(_open_url_safe)
        self.lnk_github = QLabel()
        self.lnk_github.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.lnk_github.linkActivated.connect(_open_url_safe)
        self.lnk_share = QLabel()
        self.lnk_share.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.lnk_share.linkActivated.connect(_open_url_safe)
        self.lnk_notes = QLabel()
        self.lnk_notes.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.lnk_notes.linkActivated.connect(_open_url_safe)
        self.lnk_lit = QLabel()
        self.lnk_lit.setWordWrap(True)
        links_lay.addRow("Kurs:", self.lnk_course)
        links_lay.addRow("GitHub:", self.lnk_github)
        links_lay.addRow("SharePoint:", self.lnk_share)
        links_lay.addRow("Notizen:", self.lnk_notes)
        links_lay.addRow("Literatur:", self.lnk_lit)
        lay.addWidget(links_grp)

        task_hdr = QHBoxLayout()
        t_lbl = QLabel("Aufgaben")
        t_lbl.setObjectName("SectionTitle")
        task_hdr.addWidget(t_lbl)
        task_hdr.addStretch()
        add_task_btn = QPushButton("+ Aufgabe")
        add_task_btn.setObjectName("SecondaryBtn")
        add_task_btn.clicked.connect(self._add_task_for_module)
        task_hdr.addWidget(add_task_btn)
        lay.addLayout(task_hdr)

        self.task_table = QTableWidget(0, 4)
        self.task_table.setHorizontalHeaderLabels(["Titel", "Priorität", "Status", "Fällig"])
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.task_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.task_table.setFixedHeight(180)
        lay.addWidget(self.task_table)

        # ── Ressourcen-Bereich ──────────────────────────────────────────────
        res_hdr_row = QHBoxLayout()
        res_lbl = QLabel("🔗 Ressourcen & Hilfsmittel")
        res_lbl.setObjectName("SectionTitle")
        res_hdr_row.addWidget(res_lbl)
        res_hdr_row.addStretch()
        add_res_btn = QPushButton("+ Ressource")
        add_res_btn.setObjectName("SecondaryBtn")
        add_res_btn.clicked.connect(self._add_resource)
        res_hdr_row.addWidget(add_res_btn)
        lay.addLayout(res_hdr_row)

        res_info = QLabel(
            "Videos (YouTube), Artikel, Bücher, Tools, Dokumentationen — alles an einem Ort."
        )
        res_info.setStyleSheet("color:#706C86;font-size:11px;")
        res_info.setWordWrap(True)
        lay.addWidget(res_info)

        self.res_container = QWidget()
        self.res_lay = QVBoxLayout(self.res_container)
        self.res_lay.setSpacing(4)
        self.res_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.res_container)
        lay.addStretch()

        scroll = make_scroll(container)
        return scroll

    def refresh(self):
        self._populate_list()

    def _populate_list(self):
        # Block signals on the widget itself — NOT on selectionModel().
        # Caching selectionModel() before clear() is dangerous: PySide6 6.10 may
        # invalidate the old model during clear(), turning the cached pointer stale
        # and causing "munmap_chunk(): invalid pointer" on blockSignals(False).
        self.mod_list.blockSignals(True)
        self.mod_list.clear()
        mapping = {"Alle": "all", "Aktiv": "active", "Geplant": "planned",
                   "Abgeschlossen": "completed", "Pausiert": "paused"}
        status = mapping.get(self.filter_cb.currentText(), "all")
        q = self.search.text().lower()
        modules = [m for m in self.repo.list_modules(status)
                   if not q or q in m["name"].lower()]

        # Apply global semester filter
        modules = _filter_mods_by_sem(modules, _active_sem_filter(self.repo))

        # Sort: semester (numeric first, then unassigned), then type order, then name
        _type_order = {"pflicht": 0, "wahl": 1, "vertiefung": 2}
        def _sort_key(m):
            sem = str(m["semester"]).strip()
            sem_n = int(sem) if sem.isdigit() else 999
            mt = (m["module_type"] if "module_type" in m.keys() else "pflicht") or "pflicht"
            return (sem_n, _type_order.get(mt, 9), m["name"].lower())
        modules.sort(key=_sort_key)

        # Group by semester, with sub-headers for type changes within a semester
        _type_labels = {"pflicht": "Pflichtmodule", "wahl": "Wahlmodule",
                        "vertiefung": "Vertiefungsmodule"}
        _type_colors = {"pflicht": "#4A86E8", "wahl": "#9B59B6", "vertiefung": "#16A085"}

        current_sem = object()   # sentinel
        current_type = object()  # sentinel

        def _sem_header(sem: str) -> str:
            if sem.isdigit():
                return f"── {sem}. Semester"
            return "── Semester nicht zugeordnet"

        for m in modules:
            sem = str(m["semester"]).strip()
            mt = (m["module_type"] if "module_type" in m.keys() else "pflicht") or "pflicht"

            # Semester separator — use parent-constructor so C++ owns the item immediately,
            # avoiding premature Python GC of the wrapper in PySide6 6.10.
            if sem != current_sem:
                current_sem = sem
                current_type = object()  # reset type tracker
                sep_item = QListWidgetItem(_sem_header(sem), self.mod_list)
                sep_item.setFlags(Qt.ItemIsEnabled)
                sep_item.setForeground(QColor("#706C86"))
                f = sep_item.font()
                f.setBold(True)
                f.setPointSize(f.pointSize() - 1)
                sep_item.setFont(f)
                sep_item.setData(Qt.UserRole, -1)

            # Type sub-header within same semester (only when type changes)
            if mt != current_type:
                current_type = mt
                type_item = QListWidgetItem(f"   {_type_labels.get(mt, mt)}", self.mod_list)
                type_item.setFlags(Qt.ItemIsEnabled)
                type_item.setForeground(QColor(_type_colors.get(mt, "#706C86")))
                f2 = type_item.font()
                f2.setItalic(True)
                f2.setPointSize(f2.pointSize() - 1)
                type_item.setFont(f2)
                type_item.setData(Qt.UserRole, -1)

            item = QListWidgetItem(f"     {m['name']}", self.mod_list)
            item.setData(Qt.UserRole, m["id"])
            item.setForeground(QColor(mod_color(m["id"])))

        self.mod_list.blockSignals(False)
        # Restore previously selected item (or select first selectable)
        if self._selected_id:
            for i in range(self.mod_list.count()):
                if self.mod_list.item(i).data(Qt.UserRole) == self._selected_id:
                    self.mod_list.setCurrentRow(i)
                    return
        self._bulk_bar.hide()
        for i in range(self.mod_list.count()):
            uid = self.mod_list.item(i).data(Qt.UserRole)
            if uid is not None and uid > 0:
                self.mod_list.setCurrentRow(i)
                break

    def _selected_ids(self) -> List[int]:
        """Return list of module IDs for all currently selected list items (skip separators)."""
        return [
            self.mod_list.item(i).data(Qt.UserRole)
            for i in range(self.mod_list.count())
            if self.mod_list.item(i).isSelected()
            and (self.mod_list.item(i).data(Qt.UserRole) or -1) > 0
        ]

    def _on_selection_changed(self):
        ids = self._selected_ids()
        n = len(ids)
        if n == 0:
            self._bulk_bar.hide()
            self.detail_stack.setCurrentIndex(0)
            self._selected_id = None
        elif n == 1:
            self._bulk_bar.hide()
            self._selected_id = ids[0]
            self._show_detail(ids[0])
        else:
            # Multiple selected — show bulk bar, keep last detail visible
            self._bulk_lbl.setText(f"{n} Module ausgewählt")
            self._bulk_bar.show()
            self._selected_id = ids[-1]
            self._show_detail(ids[-1])

    def _show_detail(self, mid: int):
        m = self.repo.get_module(mid)
        if not m:
            return
        color = mod_color(mid)
        self.detail_dot._color = color
        self.detail_dot.update()
        self.detail_name.setText(m["name"])
        self.detail_info.setText(
            f"Semester: {m['semester']}  |  {m['ects']} ECTS  |  "
            f"Dozent: {m['lecturer'] or '—'}  |  "
            f"Status: {STATUS_LABELS.get(m['status'], m['status'])}"
        )
        target = self.repo.ects_target_hours(mid)
        studied_h = self.repo.seconds_studied_for_module(mid) / 3600
        pct = min(100, int(studied_h / target * 100)) if target > 0 else 0
        self.detail_bar.setValue(pct)
        self.detail_bar.setStyleSheet(
            f"QProgressBar::chunk {{background: {color}; border-radius: 4px;}}"
        )
        self.detail_prog_lbl.setText(f"{studied_h:.1f}h / {target:.0f}h")

        def lh(url: str) -> str:
            return f'<a href="{url}" style="color:#4A86E8">{url[:60]}</a>' if url else "—"

        self.lnk_course.setText(lh(m["link"]))
        self.lnk_github.setText(lh(m["github_link"]))
        self.lnk_share.setText(lh(m["sharepoint_link"]))
        self.lnk_notes.setText(lh(m["notes_link"]))
        self.lnk_lit.setText(m["literature_links"] or "—")

        tasks = self.repo.list_tasks(module_id=mid)
        self.task_table.setRowCount(len(tasks))
        for r, t in enumerate(tasks):
            self.task_table.setItem(r, 0, QTableWidgetItem(t["title"]))
            p_item = QTableWidgetItem(t["priority"])
            p_item.setForeground(QColor(PRIORITY_COLORS.get(t["priority"], "#333")))
            self.task_table.setItem(r, 1, p_item)
            self.task_table.setItem(r, 2, QTableWidgetItem(t["status"]))
            self.task_table.setItem(r, 3, QTableWidgetItem(t["due_date"] or "—"))

        # Load resources from settings
        self._load_resources(mid)
        self.detail_stack.setCurrentIndex(1)

    def _load_resources(self, mid: int):
        """Load and display saved resource links for this module."""
        while self.res_lay.count():
            item = self.res_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        key = f"resources_mod_{mid}"
        raw = self.repo.get_setting(key) or ""
        if not raw.strip():
            hint = QLabel("Noch keine Ressourcen — klicke '+ Ressource' um Videos,\nBücher oder Tools hinzuzufügen.")
            hint.setStyleSheet("color:#706C86;font-size:11px;")
            hint.setWordWrap(True)
            self.res_lay.addWidget(hint)
            return
        type_icons = {"youtube": "▶️", "video": "🎬", "book": "📖", "article": "📄",
                      "tool": "🔧", "doc": "📚", "web": "🌐", "other": "🔗"}
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # Format: TYPE|LABEL|URL  or just URL
            parts = line.split("|", 2)
            if len(parts) == 3:
                rtype, label, url = parts[0].strip(), parts[1].strip(), parts[2].strip()
            elif len(parts) == 2:
                rtype, label, url = "other", parts[0].strip(), parts[1].strip()
            else:
                rtype, label, url = "other", line, line
            icon = type_icons.get(rtype.lower(), "🔗")
            row_w = QFrame()
            row_w.setObjectName("ResourceRow")
            row_w.setAttribute(Qt.WA_StyledBackground, True)
            row_lay = QHBoxLayout(row_w)
            row_lay.setContentsMargins(10, 5, 10, 5)
            row_lay.setSpacing(8)
            icon_lbl = QLabel(icon)
            icon_lbl.setFixedWidth(20)
            row_lay.addWidget(icon_lbl)
            link_lbl = QLabel(f'<a href="{url}" style="color:#4A86E8;text-decoration:none;">{label}</a>')
            link_lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
            link_lbl.linkActivated.connect(_open_url_safe)
            link_lbl.setStyleSheet("font-size:12px;")
            row_lay.addWidget(link_lbl, 1)
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(20, 20)
            del_btn.setStyleSheet("QPushButton{background:#F44336;color:white;border-radius:4px;"
                                  "font-size:10px;font-weight:bold;border:none;}"
                                  "QPushButton:hover{background:#C73850;}")
            del_btn.clicked.connect(lambda checked, _line=line, _mid=mid: self._delete_resource(_mid, _line))
            row_lay.addWidget(del_btn)
            self.res_lay.addWidget(row_w)

    def _add_resource(self):
        if not self._selected_id:
            return
        from semetra.gui.dialogs.resource_dialog import ResourceDialog
        dlg = ResourceDialog(parent=self)
        if dlg.exec():
            rtype, label, url = dlg.get_values()
            key = f"resources_mod_{self._selected_id}"
            raw = self.repo.get_setting(key) or ""
            entry = f"{rtype}|{label}|{url}"
            new_raw = (raw.strip() + "\n" + entry).strip()
            self.repo.set_setting(key, new_raw)
            self._load_resources(self._selected_id)

    def _delete_resource(self, mid: int, line_to_remove: str):
        key = f"resources_mod_{mid}"
        raw = self.repo.get_setting(key) or ""
        lines = [l for l in raw.strip().split("\n") if l.strip() and l.strip() != line_to_remove.strip()]
        self.repo.set_setting(key, "\n".join(lines))
        self._load_resources(mid)

    def _add_module(self):
        from semetra.gui.dialogs.module_dialog import ModuleDialog
        if ModuleDialog(self.repo, parent=self).exec():
            self.refresh()
            if self._global_refresh:
                QTimer.singleShot(50, self._global_refresh)

    def _edit_module(self):
        if not self._selected_id:
            return
        from semetra.gui.dialogs.module_dialog import ModuleDialog
        if ModuleDialog(self.repo, self._selected_id, parent=self).exec():
            self.refresh()
            self._show_detail(self._selected_id)
            if self._global_refresh:
                QTimer.singleShot(50, self._global_refresh)

    def _delete_module(self):
        """Delete the single currently-shown module (called from detail panel button)."""
        if not self._selected_id:
            return
        m = self.repo.get_module(self._selected_id)
        ans = QMessageBox.question(
            self, "Löschen",
            f"Modul '{m['name']}' wirklich löschen?\n"
            "Alle Aufgaben und Zeitlogs werden ebenfalls gelöscht.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            self.repo.delete_module(self._selected_id)
            self._selected_id = None
            self._bulk_bar.hide()
            self.detail_stack.setCurrentIndex(0)
            self.refresh()
            if self._global_refresh:
                QTimer.singleShot(50, self._global_refresh)

    def _delete_selected(self):
        """Bulk-delete all currently selected modules."""
        ids = self._selected_ids()
        if not ids:
            return
        names = []
        for mid in ids:
            m = self.repo.get_module(mid)
            if m:
                names.append(m["name"])
        preview = "\n".join(f"  • {n}" for n in names[:8])
        if len(names) > 8:
            preview += f"\n  … und {len(names) - 8} weitere"
        ans = QMessageBox.question(
            self, f"{len(ids)} Module löschen",
            f"Folgende {len(ids)} Module und alle zugehörigen Aufgaben,\n"
            f"Zeitlogs und Notizen werden unwiderruflich gelöscht:\n\n"
            f"{preview}\n\nFortfahren?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            for mid in ids:
                self.repo.delete_module(mid)
            self._selected_id = None
            self._bulk_bar.hide()
            self.detail_stack.setCurrentIndex(0)
            self.refresh()
            if self._global_refresh:
                QTimer.singleShot(50, self._global_refresh)

    def _delete_all_modules(self):
        """Alle Module (und zugehörige Daten) auf einmal löschen — z.B. nach Fehlimport."""
        all_mods = self.repo.list_modules("all")
        if not all_mods:
            QMessageBox.information(self, "Keine Module", "Es sind keine Module vorhanden.")
            return
        n = len(all_mods)
        ans = QMessageBox.question(
            self, f"Alle {n} Module löschen?",
            f"Möchtest du wirklich ALLE {n} Module und alle zugehörigen\n"
            "Aufgaben, Zeitlogs und Notizen unwiderruflich löschen?\n\n"
            "Diese Aktion kann nicht rückgängig gemacht werden.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if ans == QMessageBox.Yes:
            for m in all_mods:
                self.repo.delete_module(m["id"])
            self._selected_id = None
            self._bulk_bar.hide()
            self.detail_stack.setCurrentIndex(0)
            self.refresh()
            if self._global_refresh:
                QTimer.singleShot(50, self._global_refresh)

    def _add_task_for_module(self):
        if not self._selected_id:
            return
        from semetra.gui.dialogs.task_dialog import TaskDialog
        if TaskDialog(self.repo, default_module_id=self._selected_id, parent=self).exec():
            self._show_detail(self._selected_id)

    def _import_fh_database(self):
        from semetra.infra.license import LicenseManager
        from semetra.gui.dialogs.pro_feature import ProFeatureDialog
        from semetra.gui.dialogs.fh_database_import import FHDatabaseImportDialog
        lm = LicenseManager(self.repo)
        if not lm.is_pro():
            if ProFeatureDialog("FH-Datenbank Import", self.repo, parent=self).exec() != QDialog.Accepted:
                return
        if FHDatabaseImportDialog(self.repo, parent=self).exec():
            self.refresh()
            if self._global_refresh:
                QTimer.singleShot(50, self._global_refresh)

    def _import_scraping(self):
        from semetra.infra.license import LicenseManager
        from semetra.gui.dialogs.pro_feature import ProFeatureDialog
        from semetra.gui.dialogs.scraping_import import ScrapingImportDialog
        lm = LicenseManager(self.repo)
        if not lm.is_pro():
            if ProFeatureDialog("PDF / Datei Import", self.repo, parent=self).exec() != QDialog.Accepted:
                return
        if ScrapingImportDialog(self.repo, parent=self).exec():
            self.refresh()
            if self._global_refresh:
                QTimer.singleShot(50, self._global_refresh)


