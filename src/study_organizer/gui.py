from __future__ import annotations

import sys
import time as _time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QScrollArea, QFrame,
    QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QGridLayout,
    QSizePolicy, QMessageBox, QCalendarWidget, QProgressBar,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QCheckBox, QGroupBox, QSplitter, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, QTimer, QDate, QSize, Signal, Slot
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPixmap,
    QPainterPath, QLinearGradient,
)

from study_organizer.repo.sqlite_repo import SqliteRepo

# ── Constants ──────────────────────────────────────────────────────────────

MODULE_COLORS = [
    "#4A86E8", "#E84A5F", "#2CB67D", "#FF8C42", "#9B59B6",
    "#00B4D8", "#F72585", "#3A86FF", "#F4A261", "#2EC4B6",
]

KNOWLEDGE_COLORS = {0: "#9E9E9E", 1: "#F44336", 2: "#FF9800", 3: "#8BC34A", 4: "#4CAF50"}
KNOWLEDGE_LABELS = {0: "Nicht begonnen", 1: "Grundlagen", 2: "Vertraut", 3: "Gut", 4: "Experte"}
PRIORITY_COLORS = {"Critical": "#F44336", "High": "#FF9800", "Medium": "#2196F3", "Low": "#9E9E9E"}
STATUS_LABELS = {"planned": "Geplant", "active": "Aktiv", "completed": "Abgeschlossen", "paused": "Pausiert"}


def mod_color(mid: int) -> str:
    return MODULE_COLORS[mid % len(MODULE_COLORS)]


def days_until(s: str) -> Optional[int]:
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
        return (d - date.today()).days
    except Exception:
        return None


def fmt_hms(secs: int) -> str:
    h, r = divmod(abs(secs), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ── Translations ──────────────────────────────────────────────────────────

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "de": {
        "nav.dashboard": "Dashboard",    "nav.modules": "Module",
        "nav.tasks": "Aufgaben",         "nav.calendar": "Kalender",
        "nav.timeline": "Zeitplan",      "nav.knowledge": "Wissen",
        "nav.timer": "Timer",            "nav.exams": "Prüfungen",
        "nav.grades": "Noten",           "nav.settings": "Einstellungen",
        "nav.credits": "Credits",
        "greet.morning": "Guten Morgen", "greet.day": "Guten Tag",
        "greet.evening": "Guten Abend",
        "page.dashboard": "Dashboard",   "page.modules": "Module",
        "page.tasks": "Aufgaben",        "page.calendar": "Kalender",
        "page.timeline": "Zeitplan & Fristen",
        "page.knowledge": "Wissensübersicht",
        "page.timer": "Fokus-Timer",
        "page.exams": "Prüfungsvorbereitung",
        "page.grades": "Noten",          "page.settings": "Einstellungen",
        "page.credits": "Credits",
    },
    "en": {
        "nav.dashboard": "Dashboard",    "nav.modules": "Modules",
        "nav.tasks": "Tasks",            "nav.calendar": "Calendar",
        "nav.timeline": "Timeline",      "nav.knowledge": "Knowledge",
        "nav.timer": "Timer",            "nav.exams": "Exams",
        "nav.grades": "Grades",          "nav.settings": "Settings",
        "nav.credits": "Credits",
        "greet.morning": "Good Morning", "greet.day": "Good Afternoon",
        "greet.evening": "Good Evening",
        "page.dashboard": "Dashboard",   "page.modules": "Modules",
        "page.tasks": "Tasks",           "page.calendar": "Calendar",
        "page.timeline": "Timeline & Deadlines",
        "page.knowledge": "Knowledge Overview",
        "page.timer": "Focus Timer",
        "page.exams": "Exam Preparation",
        "page.grades": "Grades",         "page.settings": "Settings",
        "page.credits": "Credits",
    },
    "fr": {
        "nav.dashboard": "Tableau de bord", "nav.modules": "Modules",
        "nav.tasks": "Tâches",           "nav.calendar": "Calendrier",
        "nav.timeline": "Planning",      "nav.knowledge": "Connaissances",
        "nav.timer": "Minuteur",         "nav.exams": "Examens",
        "nav.grades": "Notes",           "nav.settings": "Paramètres",
        "nav.credits": "Crédits",
        "greet.morning": "Bonjour",      "greet.day": "Bonjour",
        "greet.evening": "Bonsoir",
        "page.dashboard": "Tableau de bord", "page.modules": "Modules",
        "page.tasks": "Tâches",          "page.calendar": "Calendrier",
        "page.timeline": "Planning & Échéances",
        "page.knowledge": "Connaissances",
        "page.timer": "Minuteur Focus",
        "page.exams": "Préparation aux Examens",
        "page.grades": "Notes",          "page.settings": "Paramètres",
        "page.credits": "Crédits",
    },
    "it": {
        "nav.dashboard": "Dashboard",    "nav.modules": "Moduli",
        "nav.tasks": "Attività",         "nav.calendar": "Calendario",
        "nav.timeline": "Cronologia",    "nav.knowledge": "Conoscenze",
        "nav.timer": "Timer",            "nav.exams": "Esami",
        "nav.grades": "Voti",            "nav.settings": "Impostazioni",
        "nav.credits": "Crediti",
        "greet.morning": "Buongiorno",   "greet.day": "Buon pomeriggio",
        "greet.evening": "Buonasera",
        "page.dashboard": "Dashboard",   "page.modules": "Moduli",
        "page.tasks": "Attività",        "page.calendar": "Calendario",
        "page.timeline": "Cronologia & Scadenze",
        "page.knowledge": "Panoramica Conoscenze",
        "page.timer": "Timer Focus",
        "page.exams": "Preparazione Esami",
        "page.grades": "Voti",           "page.settings": "Impostazioni",
        "page.credits": "Crediti",
    },
}

_LANG: str = "de"


def set_lang(lang: str) -> None:
    global _LANG
    _LANG = lang if lang in TRANSLATIONS else "de"


def tr(key: str) -> str:
    return TRANSLATIONS.get(_LANG, TRANSLATIONS["de"]).get(key, key)


def greeting() -> str:
    hr = datetime.now().hour
    if hr < 12:
        return tr("greet.morning")
    if hr < 18:
        return tr("greet.day")
    return tr("greet.evening")


# ── QSS ───────────────────────────────────────────────────────────────────

LIGHT_QSS = """
* { font-family: 'Noto Color Emoji', 'Apple Color Emoji', 'Segoe UI Emoji', 'Inter', 'Segoe UI', 'Ubuntu', Arial, sans-serif; font-size: 13px; }
QMainWindow, QDialog { background: #F0F4FA; }
QWidget { background: transparent; color: #1A1A2E; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* ── Sidebar ─────────────────────────────── */
QWidget#Sidebar {
    background: #1E2340;
    border-right: none;
}
QLabel#AppTitle {
    font-size: 14px; font-weight: bold;
    color: #FFFFFF; letter-spacing: 1px;
    padding: 4px 16px;
}
QLabel#AppVersion { font-size: 10px; color: #6B7DB3; padding: 0 16px 8px 16px; }
QPushButton#NavBtn {
    background: transparent; border: none; border-radius: 10px;
    text-align: left; padding: 10px 14px 10px 14px;
    font-size: 13px; color: #9BA8D0;
}
QPushButton#NavBtn:hover { background: rgba(255,255,255,0.08); color: #FFFFFF; }
QPushButton#NavBtn[active="true"] {
    background: rgba(74,134,232,0.25);
    color: #FFFFFF; font-weight: bold;
    border-left: 3px solid #4A86E8;
    padding-left: 11px;
}

/* ── Page background ─────────────────────── */
QWidget#PageContent { background: #F0F4FA; }

/* ── Cards ───────────────────────────────── */
QFrame#Card {
    background: #FFFFFF;
    border-radius: 16px;
    border: 1px solid #DDE3F0;
}
QLabel#CardTitle { font-size: 11px; color: #8B8FA8; text-transform: uppercase; letter-spacing: 1px; }
QLabel#CardValue { font-size: 30px; font-weight: bold; }
QLabel#CardUnit { font-size: 12px; color: #8B8FA8; margin-bottom: 4px; }

/* ── Typography ──────────────────────────── */
QLabel#PageTitle { font-size: 24px; font-weight: bold; color: #1A1A2E; }
QLabel#SectionTitle { font-size: 14px; font-weight: bold; color: #1A1A2E; letter-spacing: 0.3px; }
QLabel { color: #1A1A2E; }

/* ── Buttons ─────────────────────────────── */
QPushButton#PrimaryBtn {
    background: #4A86E8; color: white; border: none;
    border-radius: 12px; padding: 8px 20px; font-size: 13px; font-weight: bold;
}
QPushButton#PrimaryBtn:hover { background: #3570D4; }
QPushButton#PrimaryBtn:pressed { background: #2A5DB8; }
QPushButton#DangerBtn {
    background: #E84A5F; color: white; border: none;
    border-radius: 12px; padding: 8px 20px; font-size: 13px;
}
QPushButton#DangerBtn:hover { background: #C73850; }
QPushButton#SecondaryBtn {
    background: #EEF3FF; color: #4A86E8; border: 1px solid #C8D8F8;
    border-radius: 12px; padding: 8px 20px; font-size: 13px;
}
QPushButton#SecondaryBtn:hover { background: #DCE8FF; }

/* ── Inputs ──────────────────────────────── */
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background: #FFFFFF; border: 1.5px solid #DDE3F0; border-radius: 10px;
    padding: 7px 10px; font-size: 13px; color: #1A1A2E; selection-background-color: #4A86E8;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus {
    border-color: #4A86E8;
    background: #FAFCFF;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox::down-arrow { width: 10px; height: 10px; }
QComboBox QAbstractItemView {
    background: #FFFFFF; color: #1A1A2E;
    selection-background-color: #4A86E8;
    selection-color: #FFFFFF;
    border: 1px solid #DDE3F0;
    border-radius: 8px;
}
QComboBox QAbstractItemView::item {
    min-height: 28px; padding: 4px 10px;
}
QComboBox QAbstractItemView::item:selected {
    background: #4A86E8; color: #FFFFFF;
}

/* ── Scrollbar ───────────────────────────── */
QScrollBar:vertical { background: transparent; width: 5px; margin: 0; }
QScrollBar::handle:vertical { background: #C8D0E8; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 5px; }
QScrollBar::handle:horizontal { background: #C8D0E8; border-radius: 3px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Progress ────────────────────────────── */
QProgressBar { background: #E8EDF8; border-radius: 6px; border: none; max-height: 8px; }
QProgressBar::chunk { background: #4A86E8; border-radius: 6px; }

/* ── Table ───────────────────────────────── */
QTableWidget {
    background: #FFFFFF; border: 1px solid #DDE3F0;
    border-radius: 14px; gridline-color: #F0F4FA; outline: none;
}
QTableWidget::item { padding: 8px; color: #1A1A2E; border: none; }
QTableWidget::item:selected { background: #EEF3FF; color: #4A86E8; }
QHeaderView::section {
    background: #F5F8FF; border: none; border-bottom: 1px solid #DDE3F0;
    padding: 9px 8px; font-weight: bold; color: #6B7899; font-size: 12px;
}
QHeaderView { border: none; }

/* ── List ────────────────────────────────── */
QListWidget { border: 1px solid #DDE3F0; border-radius: 14px; background: #FFFFFF; outline: none; }
QListWidget::item { padding: 7px 10px; border-radius: 8px; }
QListWidget::item:selected { background: #EEF3FF; color: #4A86E8; }
QListWidget::item:hover { background: #F5F8FF; }

/* ── GroupBox ────────────────────────────── */
QGroupBox {
    border: 1.5px solid #DDE3F0; border-radius: 14px;
    margin-top: 14px; padding-top: 6px; font-weight: bold; color: #6B7899;
}
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; background: #F0F4FA; }

/* ── Calendar ────────────────────────────── */
QCalendarWidget QAbstractItemView { background: #FFFFFF; selection-background-color: #4A86E8; border-radius: 8px; }
QCalendarWidget QWidget { background: #FFFFFF; border-radius: 8px; }

/* ── Dialog ──────────────────────────────── */
QDialog { border-radius: 14px; }
QDialogButtonBox QPushButton { border-radius: 10px; padding: 6px 18px; min-width: 80px; }
"""

DARK_QSS = """
* { font-family: 'Noto Color Emoji', 'Apple Color Emoji', 'Segoe UI Emoji', 'Inter', 'Segoe UI', 'Ubuntu', Arial, sans-serif; font-size: 13px; }
QMainWindow, QDialog { background: #0F0F1A; }
QWidget { background: transparent; color: #E2E8F0; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* ── Sidebar ─────────────────────────────── */
QWidget#Sidebar { background: #0A0A14; border-right: none; }
QLabel#AppTitle { font-size: 14px; font-weight: bold; color: #FFFFFF; letter-spacing: 1px; padding: 4px 16px; }
QLabel#AppVersion { font-size: 10px; color: #404060; padding: 0 16px 8px 16px; }
QPushButton#NavBtn {
    background: transparent; border: none; border-radius: 10px;
    text-align: left; padding: 10px 14px; font-size: 13px; color: #6070A0;
}
QPushButton#NavBtn:hover { background: rgba(255,255,255,0.06); color: #C0CFFF; }
QPushButton#NavBtn[active="true"] {
    background: rgba(80,128,255,0.2); color: #FFFFFF; font-weight: bold;
    border-left: 3px solid #5080FF; padding-left: 11px;
}

/* ── Page background ─────────────────────── */
QWidget#PageContent { background: #0F0F1A; }

/* ── Cards ───────────────────────────────── */
QFrame#Card { background: #161626; border-radius: 16px; border: 1px solid #252545; }
QLabel#CardTitle { font-size: 11px; color: #505080; text-transform: uppercase; letter-spacing: 1px; }
QLabel#CardValue { font-size: 30px; font-weight: bold; }
QLabel#CardUnit { font-size: 12px; color: #505080; margin-bottom: 4px; }

/* ── Typography ──────────────────────────── */
QLabel#PageTitle { font-size: 24px; font-weight: bold; color: #E2E8F0; }
QLabel#SectionTitle { font-size: 14px; font-weight: bold; color: #C0CFFF; letter-spacing: 0.3px; }
QLabel { color: #E2E8F0; }

/* ── Buttons ─────────────────────────────── */
QPushButton#PrimaryBtn {
    background: #5080FF; color: white; border: none;
    border-radius: 12px; padding: 8px 20px; font-size: 13px; font-weight: bold;
}
QPushButton#PrimaryBtn:hover { background: #4070EE; }
QPushButton#DangerBtn {
    background: #A0203A; color: white; border: none;
    border-radius: 12px; padding: 8px 20px; font-size: 13px;
}
QPushButton#DangerBtn:hover { background: #882030; }
QPushButton#SecondaryBtn {
    background: #1E1E38; color: #8090FF; border: 1px solid #303060;
    border-radius: 12px; padding: 8px 20px; font-size: 13px;
}
QPushButton#SecondaryBtn:hover { background: #252545; }

/* ── Inputs ──────────────────────────────── */
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background: #1A1A2E; border: 1.5px solid #252545; border-radius: 10px;
    padding: 7px 10px; font-size: 13px; color: #E2E8F0;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus { border-color: #5080FF; background: #1E1E38; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #1A1A2E; color: #E2E8F0;
    selection-background-color: #5080FF;
    selection-color: #FFFFFF;
    border: 1px solid #303060;
    border-radius: 8px;
}
QComboBox QAbstractItemView::item {
    min-height: 28px; padding: 4px 10px;
}
QComboBox QAbstractItemView::item:selected {
    background: #5080FF; color: #FFFFFF;
}

/* ── Scrollbar ───────────────────────────── */
QScrollBar:vertical { background: transparent; width: 5px; }
QScrollBar::handle:vertical { background: #303050; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

/* ── Progress ────────────────────────────── */
QProgressBar { background: #1E1E38; border-radius: 6px; border: none; max-height: 8px; }
QProgressBar::chunk { background: #5080FF; border-radius: 6px; }

/* ── Table ───────────────────────────────── */
QTableWidget { background: #161626; border: 1px solid #252545; border-radius: 14px; gridline-color: #1E1E38; outline: none; }
QTableWidget::item { padding: 8px; color: #E2E8F0; border: none; }
QTableWidget::item:selected { background: #1E1E38; color: #8090FF; }
QHeaderView::section { background: #0F0F1A; border: none; border-bottom: 1px solid #252545; padding: 9px 8px; font-weight: bold; color: #404060; font-size: 12px; }
QHeaderView { border: none; }

/* ── List ────────────────────────────────── */
QListWidget { border: 1px solid #252545; border-radius: 14px; background: #161626; outline: none; }
QListWidget::item { padding: 7px 10px; border-radius: 8px; }
QListWidget::item:selected { background: #1E1E38; color: #8090FF; }
QListWidget::item:hover { background: #1A1A2E; }

/* ── GroupBox ────────────────────────────── */
QGroupBox { border: 1.5px solid #252545; border-radius: 14px; margin-top: 14px; padding-top: 6px; font-weight: bold; color: #404060; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; background: #0F0F1A; }

/* ── Calendar ────────────────────────────── */
QCalendarWidget QAbstractItemView { background: #161626; selection-background-color: #5080FF; color: #E2E8F0; border-radius: 8px; }
QCalendarWidget QWidget { background: #161626; color: #E2E8F0; border-radius: 8px; }

/* ── Dialog ──────────────────────────────── */
QDialog { border-radius: 14px; }
QDialogButtonBox QPushButton { border-radius: 10px; padding: 6px 18px; min-width: 80px; }
"""

# ── Reusable Widgets ───────────────────────────────────────────────────────

class StatCard(QFrame):
    def __init__(self, title: str, value: str, unit: str = "", color: str = "#4A86E8", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFixedHeight(110)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)

        bar = QWidget()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background:{color};border-radius:2px;")
        lay.addWidget(bar)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("CardTitle")
        lay.addWidget(self.title_lbl)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.val_lbl = QLabel(value)
        self.val_lbl.setStyleSheet(f"color:{color};font-size:26px;font-weight:bold;")
        row.addWidget(self.val_lbl)
        if unit:
            u = QLabel(unit)
            u.setObjectName("CardUnit")
            u.setAlignment(Qt.AlignBottom)
            row.addWidget(u)
        row.addStretch()
        lay.addLayout(row)

    def set_value(self, v: str):
        self.val_lbl.setText(v)


class CircularTimer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self._total = 25 * 60
        self._remaining = 25 * 60
        self._color = "#4A86E8"

    def set_state(self, remaining: int, total: int, color: str = ""):
        self._remaining = remaining
        self._total = total
        if color:
            self._color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        size = min(w, h) - 20
        x = (w - size) // 2
        y = (h - size) // 2
        from PySide6.QtCore import QRect
        rect_f = QRect(x, y, size, size)

        pen = QPen(QColor("#E8EBF2"), 12, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect_f, 0, 360 * 16)

        frac = self._remaining / self._total if self._total > 0 else 0
        span = int(frac * 360 * 16)
        pen2 = QPen(QColor(self._color), 12, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen2)
        p.drawArc(rect_f, 90 * 16, span)

        p.setPen(QPen(QColor("#1A1A2E")))
        font = QFont("Segoe UI", 26, QFont.Bold)
        p.setFont(font)
        time_str = fmt_hms(self._remaining)[3:]  # mm:ss
        p.drawText(rect_f, Qt.AlignCenter, time_str)
        p.end()


class ColorDot(QWidget):
    def __init__(self, color: str, size: int = 10, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(self._color)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, self.width(), self.height())
        p.end()


def make_scroll(widget: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setWidget(widget)
    return sa


def separator() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color: #E0E4EC;")
    return f


# ── Dialogs ────────────────────────────────────────────────────────────────

class ModuleDialog(QDialog):
    def __init__(self, repo: SqliteRepo, module_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.module_id = module_id
        self.setWindowTitle("Modul bearbeiten" if module_id else "Neues Modul")
        self.setMinimumWidth(460)
        self._build()
        if module_id:
            self._load(module_id)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        self.name = QLineEdit()
        self.semester = QLineEdit()
        self.ects = QDoubleSpinBox()
        self.ects.setRange(0, 60)
        self.ects.setSingleStep(0.5)
        self.lecturer = QLineEdit()
        self.link = QLineEdit()
        self.github_link = QLineEdit()
        self.sharepoint_link = QLineEdit()
        self.notes_link = QLineEdit()
        self.literature_links = QLineEdit()
        self.status = QComboBox()
        self.status.addItems(["planned", "active", "completed", "paused"])
        self.exam_date = QDateEdit()
        self.exam_date.setCalendarPopup(True)
        self.exam_date.setDate(QDate.currentDate())
        self.exam_date.setSpecialValueText("Kein Datum")
        self.weighting = QDoubleSpinBox()
        self.weighting.setRange(0.1, 10.0)
        self.weighting.setSingleStep(0.1)
        self.weighting.setValue(1.0)

        form.addRow("Name *:", self.name)
        form.addRow("Semester *:", self.semester)
        form.addRow("ECTS:", self.ects)
        form.addRow("Dozent:", self.lecturer)
        form.addRow("Status:", self.status)
        form.addRow("Prüfungsdatum:", self.exam_date)
        form.addRow("Gewichtung:", self.weighting)
        form.addRow("Kurs-Link:", self.link)
        form.addRow("GitHub:", self.github_link)
        form.addRow("SharePoint:", self.sharepoint_link)
        form.addRow("Literatur:", self.literature_links)
        form.addRow("Notizen-Link:", self.notes_link)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _load(self, mid: int):
        m = self.repo.get_module(mid)
        if not m:
            return
        self.name.setText(m["name"])
        self.semester.setText(m["semester"])
        self.ects.setValue(float(m["ects"]))
        self.lecturer.setText(m["lecturer"] or "")
        self.link.setText(m["link"] or "")
        self.github_link.setText(m["github_link"] or "")
        self.sharepoint_link.setText(m["sharepoint_link"] or "")
        self.notes_link.setText(m["notes_link"] or "")
        self.literature_links.setText(m["literature_links"] or "")
        idx = self.status.findText(m["status"])
        if idx >= 0:
            self.status.setCurrentIndex(idx)
        if m["exam_date"]:
            try:
                d = datetime.strptime(m["exam_date"], "%Y-%m-%d").date()
                self.exam_date.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                pass
        self.weighting.setValue(float(m["weighting"]))

    def _accept(self):
        name = self.name.text().strip()
        sem = self.semester.text().strip()
        if not name or not sem:
            QMessageBox.warning(self, "Fehler", "Name und Semester sind Pflichtfelder.")
            return
        qd = self.exam_date.date()
        exam_str = qd.toString("yyyy-MM-dd")
        data = {
            "name": name, "semester": sem,
            "ects": self.ects.value(),
            "lecturer": self.lecturer.text().strip(),
            "link": self.link.text().strip(),
            "github_link": self.github_link.text().strip(),
            "sharepoint_link": self.sharepoint_link.text().strip(),
            "notes_link": self.notes_link.text().strip(),
            "literature_links": self.literature_links.text().strip(),
            "status": self.status.currentText(),
            "exam_date": exam_str,
            "weighting": self.weighting.value(),
        }
        if self.module_id:
            self.repo.update_module(self.module_id, **data)
        else:
            self.repo.add_module(data)
        self.accept()


class TaskDialog(QDialog):
    def __init__(self, repo: SqliteRepo, task_id: Optional[int] = None,
                 default_module_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.task_id = task_id
        self.setWindowTitle("Aufgabe bearbeiten" if task_id else "Neue Aufgabe")
        self.setMinimumWidth(420)
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

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

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
            self.repo.add_task(
                mid, title,
                priority=self.priority.currentText(),
                status=self.status.currentText(),
                due_date=due, notes=self.notes.toPlainText(),
            )
        self.accept()


class GradeDialog(QDialog):
    def __init__(self, repo: SqliteRepo, grade_id: Optional[int] = None,
                 default_module_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.grade_id = grade_id
        self.setWindowTitle("Note bearbeiten" if grade_id else "Note hinzufügen")
        self.setMinimumWidth(380)
        self._build()
        if grade_id:
            self._load(grade_id)
        elif default_module_id:
            self._set_module(default_module_id)

    def _build(self):
        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.title = QLineEdit()
        self.module_cb = QComboBox()
        for m in self.repo.list_modules("all"):
            self.module_cb.addItem(m["name"], m["id"])
        self.grade = QDoubleSpinBox()
        self.grade.setRange(0, 10000)
        self.grade.setDecimals(2)
        self.max_grade = QDoubleSpinBox()
        self.max_grade.setRange(1, 10000)
        self.max_grade.setDecimals(2)
        self.max_grade.setValue(100)
        self.weight = QDoubleSpinBox()
        self.weight.setRange(0.01, 100)
        self.weight.setDecimals(2)
        self.weight.setValue(1.0)
        self.date_e = QDateEdit()
        self.date_e.setCalendarPopup(True)
        self.date_e.setDate(QDate.currentDate())
        self.notes = QLineEdit()

        form.addRow("Titel *:", self.title)
        form.addRow("Modul:", self.module_cb)
        form.addRow("Erreichte Punkte:", self.grade)
        form.addRow("Max. Punkte:", self.max_grade)
        form.addRow("Gewichtung:", self.weight)
        form.addRow("Datum:", self.date_e)
        form.addRow("Notizen:", self.notes)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _set_module(self, mid: int):
        for i in range(self.module_cb.count()):
            if self.module_cb.itemData(i) == mid:
                self.module_cb.setCurrentIndex(i)
                break

    def _load(self, gid: int):
        rows = self.repo.list_grades()
        g = next((r for r in rows if r["id"] == gid), None)
        if not g:
            return
        self.title.setText(g["title"])
        self._set_module(g["module_id"])
        self.grade.setValue(float(g["grade"]))
        self.max_grade.setValue(float(g["max_grade"]))
        self.weight.setValue(float(g["weight"]))
        if g["date"]:
            try:
                d = datetime.strptime(g["date"], "%Y-%m-%d").date()
                self.date_e.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                pass
        self.notes.setText(g["notes"] or "")

    def _accept(self):
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        mid = self.module_cb.currentData()
        date_str = self.date_e.date().toString("yyyy-MM-dd")
        if self.grade_id:
            self.repo.update_grade(
                self.grade_id,
                title=title, module_id=mid,
                grade=self.grade.value(), max_grade=self.max_grade.value(),
                weight=self.weight.value(), date=date_str,
                notes=self.notes.text(),
            )
        else:
            self.repo.add_grade(
                mid, title,
                grade=self.grade.value(), max_grade=self.max_grade.value(),
                weight=self.weight.value(), date_str=date_str,
                notes=self.notes.text(),
            )
        self.accept()


class TopicDialog(QDialog):
    def __init__(self, repo: SqliteRepo, module_id: int,
                 topic_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.module_id = module_id
        self.topic_id = topic_id
        self.setWindowTitle("Thema bearbeiten" if topic_id else "Neues Thema")
        self.setMinimumWidth(360)
        self._build()
        if topic_id:
            self._load(topic_id)

    def _build(self):
        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)
        self.title = QLineEdit()
        self.level = QComboBox()
        for k, v in KNOWLEDGE_LABELS.items():
            self.level.addItem(v, k)
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        form.addRow("Titel *:", self.title)
        form.addRow("Kenntnisstand:", self.level)
        form.addRow("Notizen:", self.notes)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _load(self, tid: int):
        topics = self.repo.list_topics(self.module_id)
        t = next((r for r in topics if r["id"] == tid), None)
        if not t:
            return
        self.title.setText(t["title"])
        idx = self.level.findData(int(t["knowledge_level"]))
        if idx >= 0:
            self.level.setCurrentIndex(idx)
        self.notes.setPlainText(t["notes"] or "")

    def _accept(self):
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        level = self.level.currentData()
        notes = self.notes.toPlainText()
        if self.topic_id:
            self.repo.update_topic(self.topic_id, title=title,
                                   knowledge_level=level, notes=notes)
        else:
            self.repo.add_topic(self.module_id, title, knowledge_level=level, notes=notes)
        self.accept()


# ── Pages ─────────────────────────────────────────────────────────────────

class DashboardPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(20)

        self.greet_lbl = QLabel()
        self.greet_lbl.setObjectName("PageTitle")
        self.sub_lbl = QLabel()
        self.sub_lbl.setStyleSheet("color: #8B8FA8; font-size: 13px;")
        outer.addWidget(self.greet_lbl)
        outer.addWidget(self.sub_lbl)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)
        self.card_streak = StatCard("Lernserie", "0", "Tage", "#FF8C42")
        self.card_hours = StatCard("Diese Woche", "0.0", "h", "#4A86E8")
        self.card_modules = StatCard("Aktive Module", "0", "", "#2CB67D")
        self.card_tasks = StatCard("Offene Aufgaben", "0", "", "#9B59B6")
        for c in [self.card_streak, self.card_hours, self.card_modules, self.card_tasks]:
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            stats_row.addWidget(c)
        outer.addLayout(stats_row)

        exam_lbl = QLabel("Bevorstehende Prufungen")
        exam_lbl.setObjectName("SectionTitle")
        outer.addWidget(exam_lbl)

        self.exam_container = QWidget()
        self.exam_row = QHBoxLayout(self.exam_container)
        self.exam_row.setSpacing(14)
        self.exam_row.setContentsMargins(0, 0, 0, 0)
        self.exam_row.addStretch()
        exam_sa = QScrollArea()
        exam_sa.setWidgetResizable(True)
        exam_sa.setFrameShape(QFrame.NoFrame)
        exam_sa.setFixedHeight(115)
        exam_sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        exam_sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        exam_sa.setWidget(self.exam_container)
        outer.addWidget(exam_sa)

        mod_lbl = QLabel("Modul-Fortschritt")
        mod_lbl.setObjectName("SectionTitle")
        outer.addWidget(mod_lbl)

        self.mod_container = QWidget()
        self.mod_grid = QGridLayout(self.mod_container)
        self.mod_grid.setSpacing(12)
        mod_sa = make_scroll(self.mod_container)
        outer.addWidget(mod_sa, 1)

    def refresh(self):
        now = datetime.now()
        self.greet_lbl.setText(f"{greeting()} — {now.strftime('%A, %d. %B %Y')}")

        streak = self.repo.get_study_streak()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_secs = self.repo.seconds_studied_week(week_start)
        active_mods = len(self.repo.list_modules("active"))
        open_tasks = len([t for t in self.repo.list_tasks(status="Open")])

        self.card_streak.set_value(str(streak))
        self.card_hours.set_value(f"{week_secs/3600:.1f}")
        self.card_modules.set_value(str(active_mods))
        self.card_tasks.set_value(str(open_tasks))

        if streak == 0:
            self.sub_lbl.setText("Fang heute an — eine neue Lernserie wartet auf dich!")
        else:
            self.sub_lbl.setText(f"{streak} Tage Lernserie — grossartig, weiter so!")

        # Exam cards
        while self.exam_row.count() > 1:
            item = self.exam_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        exams = self.repo.upcoming_exams(within_days=60)
        if not exams:
            lbl = QLabel("Keine Prufungen in den nachsten 60 Tagen.")
            lbl.setStyleSheet("color: #8B8FA8; font-size: 13px;")
            self.exam_row.insertWidget(0, lbl)
        else:
            for i, m in enumerate(exams):
                self.exam_row.insertWidget(i, self._make_exam_card(m))

        # Module progress grid
        for i in reversed(range(self.mod_grid.count())):
            w = self.mod_grid.itemAt(i).widget()
            if w:
                w.deleteLater()

        modules = self.repo.list_modules("all")
        for idx, m in enumerate(modules):
            row, col = divmod(idx, 3)
            self.mod_grid.addWidget(self._make_module_card(m), row, col)

    def _make_exam_card(self, m) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedSize(175, 95)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(3)
        color = mod_color(m["id"])
        name_lbl = QLabel(m["name"])
        name_lbl.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {color};")
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl)
        d = days_until(m["exam_date"])
        if d is None:
            d_txt, d_col = "—", "#8B8FA8"
        elif d < 0:
            d_txt, d_col = "Vergangen", "#9E9E9E"
        elif d == 0:
            d_txt, d_col = "HEUTE!", "#F44336"
        elif d <= 7:
            d_txt, d_col = f"in {d} Tagen", "#FF9800"
        else:
            d_txt, d_col = f"in {d} Tagen", "#4A86E8"
        days_lbl = QLabel(d_txt)
        days_lbl.setStyleSheet(f"color: {d_col}; font-size: 13px; font-weight: bold;")
        lay.addWidget(days_lbl)
        date_lbl = QLabel(m["exam_date"])
        date_lbl.setStyleSheet("color: #8B8FA8; font-size: 11px;")
        lay.addWidget(date_lbl)
        return card

    def _make_module_card(self, m) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setFixedHeight(95)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)
        color = mod_color(m["id"])

        hdr = QHBoxLayout()
        dot = ColorDot(color, 10)
        hdr.addWidget(dot)
        name_lbl = QLabel(m["name"])
        name_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        hdr.addWidget(name_lbl, 1)
        status_lbl = QLabel(STATUS_LABELS.get(m["status"], m["status"]))
        status_lbl.setStyleSheet("color: #8B8FA8; font-size: 11px;")
        hdr.addWidget(status_lbl)
        lay.addLayout(hdr)

        target = self.repo.ects_target_hours(m["id"])
        studied_h = self.repo.seconds_studied_for_module(m["id"]) / 3600
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setFixedHeight(6)
        bar.setTextVisible(False)
        pct = min(100, int(studied_h / target * 100)) if target > 0 else 0
        bar.setValue(pct)
        bar.setStyleSheet(f"QProgressBar::chunk {{background: {color};border-radius:3px;}}")
        lay.addWidget(bar)

        sub = QLabel(f"{studied_h:.1f}h / {target:.0f}h  |  {m['ects']} ECTS  |  {m['semester']}")
        sub.setStyleSheet("color: #8B8FA8; font-size: 11px;")
        lay.addWidget(sub)
        return card


class ModulesPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._selected_id: Optional[int] = None
        self._build()

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left panel
        left = QWidget()
        left.setFixedWidth(280)
        left.setAttribute(Qt.WA_StyledBackground, True)
        left.setStyleSheet("background: #FFFFFF; border-right: 1px solid #DDE3F0;")
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
        add_btn.clicked.connect(self._add_module)
        hdr.addWidget(add_btn)
        llay.addLayout(hdr)

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
        self.mod_list.currentRowChanged.connect(self._on_select)
        llay.addWidget(self.mod_list, 1)
        outer.addWidget(left)

        # Right panel
        self.detail_stack = QStackedWidget()
        ph = QLabel("Wahle ein Modul aus der Liste")
        ph.setAlignment(Qt.AlignCenter)
        ph.setStyleSheet("color: #8B8FA8; font-size: 14px;")
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
        del_btn = QPushButton("Loschen")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_module)
        hdr.addWidget(del_btn)
        lay.addLayout(hdr)

        self.detail_info = QLabel()
        self.detail_info.setStyleSheet("color: #8B8FA8; font-size: 13px;")
        lay.addWidget(self.detail_info)

        prog_row = QHBoxLayout()
        self.detail_bar = QProgressBar()
        self.detail_bar.setFixedHeight(8)
        self.detail_bar.setTextVisible(False)
        prog_row.addWidget(self.detail_bar, 1)
        self.detail_prog_lbl = QLabel("0h / 0h")
        self.detail_prog_lbl.setStyleSheet("color: #8B8FA8; font-size: 12px;")
        prog_row.addWidget(self.detail_prog_lbl)
        lay.addLayout(prog_row)

        lay.addWidget(separator())

        links_grp = QGroupBox("Links")
        links_lay = QFormLayout(links_grp)
        links_lay.setSpacing(6)
        self.lnk_course = QLabel()
        self.lnk_course.setOpenExternalLinks(True)
        self.lnk_github = QLabel()
        self.lnk_github.setOpenExternalLinks(True)
        self.lnk_share = QLabel()
        self.lnk_share.setOpenExternalLinks(True)
        self.lnk_notes = QLabel()
        self.lnk_notes.setOpenExternalLinks(True)
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
        self.task_table.setHorizontalHeaderLabels(["Titel", "Prioritat", "Status", "Fallig"])
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.task_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.task_table.setFixedHeight(180)
        lay.addWidget(self.task_table)
        lay.addStretch()

        scroll = make_scroll(container)
        return scroll

    def refresh(self):
        self._populate_list()

    def _populate_list(self):
        self.mod_list.clear()
        mapping = {"Alle": "all", "Aktiv": "active", "Geplant": "planned",
                   "Abgeschlossen": "completed", "Pausiert": "paused"}
        status = mapping.get(self.filter_cb.currentText(), "all")
        q = self.search.text().lower()
        for m in self.repo.list_modules(status):
            if q and q not in m["name"].lower():
                continue
            item = QListWidgetItem(f"  {m['name']}")
            item.setData(Qt.UserRole, m["id"])
            item.setForeground(QColor(mod_color(m["id"])))
            self.mod_list.addItem(item)
        # Re-select
        if self._selected_id:
            for i in range(self.mod_list.count()):
                if self.mod_list.item(i).data(Qt.UserRole) == self._selected_id:
                    self.mod_list.setCurrentRow(i)
                    return
        if self.mod_list.count():
            self.mod_list.setCurrentRow(0)

    def _on_select(self, row: int):
        if row < 0:
            self.detail_stack.setCurrentIndex(0)
            return
        mid = self.mod_list.item(row).data(Qt.UserRole)
        self._selected_id = mid
        self._show_detail(mid)

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

        self.detail_stack.setCurrentIndex(1)

    def _add_module(self):
        if ModuleDialog(self.repo, parent=self).exec():
            self.refresh()

    def _edit_module(self):
        if not self._selected_id:
            return
        if ModuleDialog(self.repo, self._selected_id, parent=self).exec():
            self.refresh()
            self._show_detail(self._selected_id)

    def _delete_module(self):
        if not self._selected_id:
            return
        m = self.repo.get_module(self._selected_id)
        ans = QMessageBox.question(self, "Loschen",
                                   f"Modul '{m['name']}' wirklich loschen?\n"
                                   "Alle Aufgaben und Zeitlogs werden ebenfalls geloscht.",
                                   QMessageBox.Yes | QMessageBox.No)
        if ans == QMessageBox.Yes:
            self.repo.delete_module(self._selected_id)
            self._selected_id = None
            self.detail_stack.setCurrentIndex(0)
            self.refresh()

    def _add_task_for_module(self):
        if not self._selected_id:
            return
        if TaskDialog(self.repo, default_module_id=self._selected_id, parent=self).exec():
            self._show_detail(self._selected_id)


class TasksPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel(tr("page.tasks"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = QPushButton("+ Neue Aufgabe")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_task)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        frow = QHBoxLayout()
        frow.setSpacing(10)
        self.mod_filter = QComboBox()
        self.mod_filter.addItem("Alle Module", None)
        self.mod_filter.currentIndexChanged.connect(self.refresh)
        frow.addWidget(QLabel("Modul:"))
        frow.addWidget(self.mod_filter)
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Alle", "Open", "In Progress", "Done"])
        self.status_filter.currentIndexChanged.connect(self.refresh)
        frow.addWidget(QLabel("Status:"))
        frow.addWidget(self.status_filter)
        self.prio_filter = QComboBox()
        self.prio_filter.addItems(["Alle", "Critical", "High", "Medium", "Low"])
        self.prio_filter.currentIndexChanged.connect(self.refresh)
        frow.addWidget(QLabel("Prioritat:"))
        frow.addWidget(self.prio_filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen...")
        self.search.textChanged.connect(self.refresh)
        frow.addWidget(self.search, 1)
        lay.addLayout(frow)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Titel", "Modul", "Prioritat", "Status", "Fallig", "ID"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnHidden(5, True)
        self.table.doubleClicked.connect(self._edit_task)
        lay.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.count_lbl = QLabel()
        self.count_lbl.setStyleSheet("color: #8B8FA8; font-size: 12px;")
        bottom.addWidget(self.count_lbl)
        bottom.addStretch()
        del_btn = QPushButton("Gewahlte loschen")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_task)
        bottom.addWidget(del_btn)
        lay.addLayout(bottom)

    def refresh(self):
        cur_mod = self.mod_filter.currentData()
        self.mod_filter.blockSignals(True)
        self.mod_filter.clear()
        self.mod_filter.addItem("Alle Module", None)
        for m in self.repo.list_modules("all"):
            self.mod_filter.addItem(m["name"], m["id"])
        if cur_mod:
            for i in range(self.mod_filter.count()):
                if self.mod_filter.itemData(i) == cur_mod:
                    self.mod_filter.setCurrentIndex(i)
                    break
        self.mod_filter.blockSignals(False)

        mid = self.mod_filter.currentData()
        st = self.status_filter.currentText()
        pr = self.prio_filter.currentText()
        tasks = self.repo.list_tasks(
            module_id=mid,
            status="all" if st == "Alle" else st,
            priority="all" if pr == "Alle" else pr,
        )
        q = self.search.text().lower()
        if q:
            tasks = [t for t in tasks if q in t["title"].lower()]

        self.table.setRowCount(len(tasks))
        for r, t in enumerate(tasks):
            self.table.setItem(r, 0, QTableWidgetItem(t["title"]))
            mod_item = QTableWidgetItem(t["module_name"])
            mod_item.setForeground(QColor(mod_color(t["module_id"])))
            self.table.setItem(r, 1, mod_item)
            p_item = QTableWidgetItem(t["priority"])
            p_item.setForeground(QColor(PRIORITY_COLORS.get(t["priority"], "#333")))
            self.table.setItem(r, 2, p_item)
            self.table.setItem(r, 3, QTableWidgetItem(t["status"]))
            self.table.setItem(r, 4, QTableWidgetItem(t["due_date"] or "—"))
            self.table.setItem(r, 5, QTableWidgetItem(str(t["id"])))
        self.count_lbl.setText(f"{len(tasks)} Aufgabe(n)")

    def _current_task_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 5)
        return int(item.text()) if item else None

    def _add_task(self):
        if TaskDialog(self.repo, parent=self).exec():
            self.refresh()

    def _edit_task(self):
        tid = self._current_task_id()
        if tid and TaskDialog(self.repo, task_id=tid, parent=self).exec():
            self.refresh()

    def _delete_task(self):
        tid = self._current_task_id()
        if not tid:
            return
        if QMessageBox.question(self, "Loschen", "Aufgabe loschen?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_task(tid)
            self.refresh()


class EventDialog(QDialog):
    """Dialog to create a custom calendar event."""
    def __init__(self, repo: SqliteRepo, default_date: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("Neues Ereignis")
        self.setMinimumWidth(400)
        self._build()
        if default_date:
            try:
                d = datetime.strptime(default_date, "%Y-%m-%d").date()
                self.start_date.setDate(QDate(d.year, d.month, d.day))
                self.end_date.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                pass

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        self.title = QLineEdit()
        self.title.setPlaceholderText("Ereignistitel *")

        self.kind_cb = QComboBox()
        self.kind_cb.addItems(["custom", "lecture", "exercise", "study", "other"])

        self.module_cb = QComboBox()
        self.module_cb.addItem("— Kein Modul —", None)
        for m in self.repo.list_modules("all"):
            self.module_cb.addItem(m["name"], m["id"])

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())

        self.start_time = QLineEdit()
        self.start_time.setPlaceholderText("HH:MM (optional)")

        self.end_time = QLineEdit()
        self.end_time.setPlaceholderText("HH:MM (optional)")

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(70)
        self.notes.setPlaceholderText("Notizen...")

        form.addRow("Titel *:", self.title)
        form.addRow("Typ:", self.kind_cb)
        form.addRow("Modul:", self.module_cb)
        form.addRow("Von:", self.start_date)
        form.addRow("Bis:", self.end_date)
        form.addRow("Startzeit:", self.start_time)
        form.addRow("Endzeit:", self.end_time)
        form.addRow("Notizen:", self.notes)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _accept(self):
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        self.repo.add_event({
            "title": title,
            "kind": self.kind_cb.currentText(),
            "module_id": self.module_cb.currentData(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date.date().toString("yyyy-MM-dd"),
            "start_time": self.start_time.text().strip(),
            "end_time": self.end_time.text().strip(),
            "notes": self.notes.toPlainText(),
        })
        self.accept()


class CalendarPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(20)

        left = QVBoxLayout()
        # Header row: title + add-event button
        hdr = QHBoxLayout()
        title = QLabel(tr("page.calendar"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        add_ev_btn = QPushButton("+ Ereignis")
        add_ev_btn.setObjectName("PrimaryBtn")
        add_ev_btn.clicked.connect(self._add_event)
        hdr.addWidget(add_ev_btn)
        left.addLayout(hdr)

        self.cal = QCalendarWidget()
        self.cal.setGridVisible(True)
        self.cal.setMinimumWidth(340)
        self.cal.selectionChanged.connect(self._on_date_selected)
        left.addWidget(self.cal)
        left.addStretch()
        lay.addLayout(left)

        right = QVBoxLayout()
        day_hdr = QHBoxLayout()
        self.day_title = QLabel("Heute")
        self.day_title.setObjectName("SectionTitle")
        day_hdr.addWidget(self.day_title)
        day_hdr.addStretch()
        del_ev_btn = QPushButton("Ereignis löschen")
        del_ev_btn.setObjectName("DangerBtn")
        del_ev_btn.clicked.connect(self._delete_selected_event)
        day_hdr.addWidget(del_ev_btn)
        right.addLayout(day_hdr)

        self.day_list = QListWidget()
        self.day_list.setStyleSheet("QListWidget { border: 1px solid #E8EBF2; border-radius: 8px; }")
        self.day_list.setFixedHeight(200)
        right.addWidget(self.day_list)

        upcoming_lbl = QLabel("Nächste 14 Tage")
        upcoming_lbl.setObjectName("SectionTitle")
        right.addWidget(upcoming_lbl)
        self.upcoming_list = QListWidget()
        self.upcoming_list.setStyleSheet("QListWidget { border: 1px solid #E8EBF2; border-radius: 8px; }")
        right.addWidget(self.upcoming_list, 1)
        lay.addLayout(right, 1)

    def refresh(self):
        self._on_date_selected()
        self._load_upcoming()

    def _add_event(self):
        qd = self.cal.selectedDate()
        default_date = qd.toString("yyyy-MM-dd")
        if EventDialog(self.repo, default_date=default_date, parent=self).exec():
            self.refresh()

    def _delete_selected_event(self):
        item = self.day_list.currentItem()
        if not item:
            return
        eid = item.data(Qt.UserRole)
        if eid is None:
            QMessageBox.information(self, "Hinweis", "Aufgaben und Prüfungen können nur in den jeweiligen Tabs gelöscht werden.")
            return
        if QMessageBox.question(self, "Löschen", "Ereignis löschen?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_event(eid)
            self.refresh()

    def _on_date_selected(self):
        qd = self.cal.selectedDate()
        d_str = qd.toString("yyyy-MM-dd")
        self.day_title.setText(qd.toString("dddd, d. MMMM yyyy"))
        self.day_list.clear()

        # Custom events from events table
        for ev in self.repo.list_events():
            if ev["start_date"] <= d_str <= (ev["end_date"] or ev["start_date"]):
                kind_icon = {"lecture": "📖", "exercise": "✏️", "study": "📚", "exam": "🎯", "custom": "📌"}.get(ev["kind"], "📌")
                mod_str = f" ({ev['module_name']})" if ev.get("module_name") else ""
                time_str = f" {ev['start_time']}" if ev.get("start_time") else ""
                item = QListWidgetItem(f"{kind_icon} {ev['title']}{mod_str}{time_str}")
                item.setData(Qt.UserRole, ev["id"])
                item.setForeground(QColor("#2CB67D"))
                self.day_list.addItem(item)

        # Tasks due on this date
        for t in self.repo.list_tasks():
            if t["due_date"] == d_str:
                color = PRIORITY_COLORS.get(t["priority"], "#333")
                item = QListWidgetItem(f"✅ Aufgabe: {t['title']} ({t['module_name']})")
                item.setData(Qt.UserRole, None)  # no event_id
                item.setForeground(QColor(color))
                self.day_list.addItem(item)

        # Exam dates from modules
        for m in self.repo.list_modules("all"):
            if m["exam_date"] == d_str:
                item = QListWidgetItem(f"🎯 PRÜFUNG: {m['name']}")
                item.setData(Qt.UserRole, None)
                item.setForeground(QColor("#F44336"))
                self.day_list.addItem(item)

        if not self.day_list.count():
            self.day_list.addItem("Keine Einträge für diesen Tag")

    def _load_upcoming(self):
        self.upcoming_list.clear()
        today = date.today()
        items = []

        # Custom events
        for ev in self.repo.list_events():
            try:
                d = datetime.strptime(ev["start_date"], "%Y-%m-%d").date()
                delta = (d - today).days
                if 0 <= delta <= 14:
                    mod_str = f" ({ev['module_name']})" if ev.get("module_name") else ""
                    items.append((delta, f"📌 {ev['title']}{mod_str} — in {delta} Tag(en)"))
            except Exception:
                pass

        for t in self.repo.list_tasks():
            if t["due_date"] and t["status"] != "Done":
                try:
                    d = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
                    delta = (d - today).days
                    if 0 <= delta <= 14:
                        items.append((delta, f"✅ Aufgabe: {t['title']} — in {delta} Tag(en)"))
                except Exception:
                    pass
        for m in self.repo.all_exams():
            try:
                d = datetime.strptime(m["exam_date"], "%Y-%m-%d").date()
                delta = (d - today).days
                if 0 <= delta <= 14:
                    items.append((delta, f"🎯 Prüfung: {m['name']} — in {delta} Tag(en)"))
            except Exception:
                pass
        items.sort(key=lambda x: x[0])
        for _, text in items:
            self.upcoming_list.addItem(text)
        if not items:
            self.upcoming_list.addItem("Keine Einträge in den nächsten 14 Tagen")


class TimelinePage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel(tr("page.timeline"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        self.range_cb = QComboBox()
        self.range_cb.addItems(["Nachste 7 Tage", "Nachste 30 Tage", "Nachste 90 Tage", "Alles"])
        self.range_cb.currentIndexChanged.connect(self.refresh)
        hdr.addWidget(QLabel("Zeitraum:"))
        hdr.addWidget(self.range_cb)
        lay.addLayout(hdr)

        self.scroll_w = QWidget()
        self.scroll_lay = QVBoxLayout(self.scroll_w)
        self.scroll_lay.setSpacing(8)
        self.scroll_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(make_scroll(self.scroll_w), 1)

    def refresh(self):
        while self.scroll_lay.count():
            item = self.scroll_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        days_map = {"Nachste 7 Tage": 7, "Nachste 30 Tage": 30,
                    "Nachste 90 Tage": 90, "Alles": 3650}
        max_days = days_map.get(self.range_cb.currentText(), 30)
        today = date.today()
        items = []

        for t in self.repo.list_tasks():
            if t["due_date"] and t["status"] != "Done":
                try:
                    d = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
                    delta = (d - today).days
                    if -3 <= delta <= max_days:
                        items.append({"date": d, "delta": delta, "type": "task",
                                      "title": t["title"], "sub": t["module_name"],
                                      "color": mod_color(t["module_id"])})
                except Exception:
                    pass

        for m in self.repo.all_exams():
            try:
                d = datetime.strptime(m["exam_date"], "%Y-%m-%d").date()
                delta = (d - today).days
                if -3 <= delta <= max_days:
                    items.append({"date": d, "delta": delta, "type": "exam",
                                  "title": f"Prufung: {m['name']}", "sub": m["semester"],
                                  "color": mod_color(m["id"])})
            except Exception:
                pass

        items.sort(key=lambda x: x["date"])

        if not items:
            lbl = QLabel("Keine Fristen im gewahlten Zeitraum.")
            lbl.setStyleSheet("color: #8B8FA8; font-size: 14px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.scroll_lay.addWidget(lbl)
        else:
            last_date = None
            for item in items:
                if item["date"] != last_date:
                    delta = item["delta"]
                    if delta == 0:
                        ds = "Heute"
                    elif delta == 1:
                        ds = "Morgen"
                    elif delta < 0:
                        ds = f"{item['date'].strftime('%d. %b')} (uberfällig)"
                    else:
                        ds = item["date"].strftime("%A, %d. %B %Y")
                    h = QLabel(ds)
                    h.setStyleSheet("font-weight: bold; color: #8B8FA8; font-size: 12px; padding-top: 8px;")
                    self.scroll_lay.addWidget(h)
                    last_date = item["date"]
                self.scroll_lay.addWidget(self._make_item(item))

        self.scroll_lay.addStretch()

    def _make_item(self, item: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedHeight(60)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(12)

        bar = QWidget()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background:{item['color']};border-radius:2px;")
        lay.addWidget(bar)

        icon = "Prufung" if item["type"] == "exam" else "Aufgabe"
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        tl = QLabel(item["title"])
        tl.setStyleSheet("font-weight: bold; font-size: 13px;")
        text_col.addWidget(tl)
        sl = QLabel(f"{icon}  |  {item['sub']}")
        sl.setStyleSheet("color: #8B8FA8; font-size: 11px;")
        text_col.addWidget(sl)
        lay.addLayout(text_col, 1)

        delta = item["delta"]
        if delta < 0:
            bt, bc = f"{abs(delta)}d uberfällig", "#F44336"
        elif delta == 0:
            bt, bc = "HEUTE", "#F44336"
        elif delta <= 3:
            bt, bc = f"in {delta}d", "#FF9800"
        elif delta <= 14:
            bt, bc = f"in {delta}d", "#4A86E8"
        else:
            bt, bc = f"in {delta}d", "#9E9E9E"

        badge = QLabel(bt)
        badge.setStyleSheet(
            f"background:{bc};color:white;border-radius:10px;"
            f"padding:2px 8px;font-size:11px;font-weight:bold;"
        )
        lay.addWidget(badge)
        return card


class KnowledgePage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._selected_mid: Optional[int] = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel(tr("page.knowledge"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        self.mod_cb = QComboBox()
        self.mod_cb.setMinimumWidth(200)
        self.mod_cb.currentIndexChanged.connect(self._load_topics)
        hdr.addWidget(QLabel("Modul:"))
        hdr.addWidget(self.mod_cb)
        add_btn = QPushButton("+ Thema")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_topic)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        # Summary
        self.summary_frame = QFrame()
        self.summary_frame.setObjectName("Card")
        sf_lay = QHBoxLayout(self.summary_frame)
        sf_lay.setContentsMargins(16, 10, 16, 10)
        self.summary_labels: Dict[int, QLabel] = {}
        for k in range(5):
            col = QVBoxLayout()
            col.setSpacing(3)
            bar = QLabel()
            bar.setFixedHeight(8)
            bar.setStyleSheet(f"background:{KNOWLEDGE_COLORS[k]};border-radius:4px;")
            col.addWidget(bar)
            lbl = QLabel(f"{KNOWLEDGE_LABELS[k]}\n0")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 11px; color: #8B8FA8;")
            col.addWidget(lbl)
            self.summary_labels[k] = lbl
            sf_lay.addLayout(col)
        lay.addWidget(self.summary_frame)

        self.topic_table = QTableWidget(0, 4)
        self.topic_table.setHorizontalHeaderLabels(["Thema", "Kenntnisstand", "Notizen", "ID"])
        self.topic_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.topic_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.topic_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.topic_table.setColumnHidden(3, True)
        self.topic_table.verticalHeader().setVisible(False)
        self.topic_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.topic_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.topic_table.doubleClicked.connect(self._edit_topic)
        lay.addWidget(self.topic_table, 1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        del_btn = QPushButton("Gewahltes loschen")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_topic)
        bottom.addWidget(del_btn)
        lay.addLayout(bottom)

    def refresh(self):
        cur_id = self.mod_cb.currentData()
        self.mod_cb.blockSignals(True)
        self.mod_cb.clear()
        for m in self.repo.list_modules("all"):
            self.mod_cb.addItem(m["name"], m["id"])
        if cur_id:
            for i in range(self.mod_cb.count()):
                if self.mod_cb.itemData(i) == cur_id:
                    self.mod_cb.setCurrentIndex(i)
                    break
        self.mod_cb.blockSignals(False)
        self._load_topics()

    def _load_topics(self):
        mid = self.mod_cb.currentData()
        self._selected_mid = mid
        if not mid:
            self.topic_table.setRowCount(0)
            return
        topics = self.repo.list_topics(mid)
        summary = self.repo.knowledge_summary(mid)
        for k in range(5):
            cnt = summary.get(str(k), 0)
            self.summary_labels[k].setText(f"{KNOWLEDGE_LABELS[k]}\n{cnt}")

        self.topic_table.setRowCount(len(topics))
        for r, t in enumerate(topics):
            self.topic_table.setItem(r, 0, QTableWidgetItem(t["title"]))
            level = int(t["knowledge_level"])
            lvl_item = QTableWidgetItem(KNOWLEDGE_LABELS.get(level, str(level)))
            lvl_item.setForeground(QColor(KNOWLEDGE_COLORS.get(level, "#333")))
            self.topic_table.setItem(r, 1, lvl_item)
            self.topic_table.setItem(r, 2, QTableWidgetItem(t["notes"] or ""))
            self.topic_table.setItem(r, 3, QTableWidgetItem(str(t["id"])))

    def _add_topic(self):
        if not self._selected_mid:
            QMessageBox.warning(self, "Hinweis", "Bitte zuerst ein Modul auswahlen.")
            return
        if TopicDialog(self.repo, self._selected_mid, parent=self).exec():
            self._load_topics()

    def _edit_topic(self):
        row = self.topic_table.currentRow()
        if row < 0 or not self._selected_mid:
            return
        tid = int(self.topic_table.item(row, 3).text())
        if TopicDialog(self.repo, self._selected_mid, topic_id=tid, parent=self).exec():
            self._load_topics()

    def _delete_topic(self):
        row = self.topic_table.currentRow()
        if row < 0:
            return
        tid = int(self.topic_table.item(row, 3).text())
        if QMessageBox.question(self, "Loschen", "Thema loschen?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_topic(tid)
            self._load_topics()


class TimerPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._running = False
        self._total = 25 * 60
        self._remaining = 25 * 60
        self._start_ts: Optional[int] = None
        self._session_count = 0
        self._qtimer = QTimer(self)
        self._qtimer.setInterval(1000)
        self._qtimer.timeout.connect(self._tick)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 20, 40, 20)
        lay.setSpacing(16)

        title = QLabel(tr("page.timer"))
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        top_row = QHBoxLayout()
        top_row.addStretch()
        self.mod_cb = QComboBox()
        self.mod_cb.setMinimumWidth(220)
        top_row.addWidget(QLabel("Modul:"))
        top_row.addWidget(self.mod_cb)
        top_row.addStretch()
        lay.addLayout(top_row)

        preset_row = QHBoxLayout()
        preset_row.addStretch()
        for label, mins in [("25 min", 25), ("50 min", 50), ("5 min Pause", 5), ("15 min Pause", 15)]:
            btn = QPushButton(label)
            btn.setObjectName("SecondaryBtn")
            btn.clicked.connect(lambda checked, m=mins: self._set_duration(m))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        lay.addLayout(preset_row)

        self.circle = CircularTimer()
        self.circle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.circle, 1, Qt.AlignCenter)

        self.mode_lbl = QLabel("Fokus-Phase")
        self.mode_lbl.setAlignment(Qt.AlignCenter)
        self.mode_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #4A86E8;")
        lay.addWidget(self.mode_lbl)

        self.session_lbl = QLabel("Sitzungen: 0")
        self.session_lbl.setAlignment(Qt.AlignCenter)
        self.session_lbl.setStyleSheet("color: #8B8FA8; font-size: 13px;")
        lay.addWidget(self.session_lbl)

        ctrl = QHBoxLayout()
        ctrl.addStretch()
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("PrimaryBtn")
        self.start_btn.setMinimumWidth(120)
        self.start_btn.clicked.connect(self._toggle)
        ctrl.addWidget(self.start_btn)
        reset_btn = QPushButton("Reset")
        reset_btn.setObjectName("SecondaryBtn")
        reset_btn.clicked.connect(self._reset)
        ctrl.addWidget(reset_btn)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Notiz zur Sitzung (optional)...")
        lay.addWidget(self.note_edit)

    def refresh(self):
        cur = self.mod_cb.currentData()
        self.mod_cb.blockSignals(True)
        self.mod_cb.clear()
        mods = self.repo.list_modules("active")
        if not mods:
            mods = self.repo.list_modules("all")
        for m in mods:
            self.mod_cb.addItem(m["name"], m["id"])
        if cur:
            for i in range(self.mod_cb.count()):
                if self.mod_cb.itemData(i) == cur:
                    self.mod_cb.setCurrentIndex(i)
                    break
        self.mod_cb.blockSignals(False)
        self._update_circle()

    def _set_duration(self, mins: int):
        if self._running:
            return
        self._total = mins * 60
        self._remaining = mins * 60
        if mins <= 5:
            self.mode_lbl.setText("Kurze Pause")
            self.circle._color = "#4CAF50"
        elif mins <= 15:
            self.mode_lbl.setText("Lange Pause")
            self.circle._color = "#2CB67D"
        else:
            self.mode_lbl.setText("Fokus-Phase")
            self.circle._color = "#4A86E8"
        self._update_circle()

    def _toggle(self):
        if self._running:
            self._running = False
            self._qtimer.stop()
            self.start_btn.setText("Fortsetzen")
        else:
            self._running = True
            if not self._start_ts:
                self._start_ts = int(_time.time())
            self._qtimer.start()
            self.start_btn.setText("Pause")

    def _reset(self):
        self._running = False
        self._qtimer.stop()
        self._remaining = self._total
        self._start_ts = None
        self.start_btn.setText("Start")
        self._update_circle()

    def _tick(self):
        if self._remaining > 0:
            self._remaining -= 1
            self._update_circle()
        else:
            self._qtimer.stop()
            self._running = False
            self._on_complete()

    def _update_circle(self):
        self.circle.set_state(self._remaining, self._total)

    def _on_complete(self):
        self._session_count += 1
        self.session_lbl.setText(f"Sitzungen: {self._session_count}")
        self.start_btn.setText("Start")
        mid = self.mod_cb.currentData()
        if mid and self._start_ts:
            end_ts = int(_time.time())
            note = self.note_edit.text().strip()
            self.repo.add_time_log(mid, self._start_ts, end_ts, self._total, "pomodoro", note)
            self.note_edit.clear()
        QMessageBox.information(self, "Timer abgelaufen!",
                                f"Zeit ist um! Sitzung #{self._session_count} abgeschlossen.\n"
                                "Mach eine kurze Pause!")
        self._remaining = self._total
        self._start_ts = None
        self._update_circle()


class ExamPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        title = QLabel(tr("page.exams"))
        title.setObjectName("PageTitle")
        lay.addWidget(title)
        self.scroll_w = QWidget()
        self.scroll_lay = QVBoxLayout(self.scroll_w)
        self.scroll_lay.setSpacing(12)
        lay.addWidget(make_scroll(self.scroll_w), 1)

    def refresh(self):
        while self.scroll_lay.count():
            item = self.scroll_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        exams = self.repo.all_exams()
        if not exams:
            lbl = QLabel("Keine Prufungen erfasst. Fuge Prufungsdaten in den Modulen hinzu.")
            lbl.setStyleSheet("color: #8B8FA8; font-size: 14px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.scroll_lay.addWidget(lbl)
        else:
            for m in exams:
                self.scroll_lay.addWidget(self._make_card(m))
        self.scroll_lay.addStretch()

    def _make_card(self, m) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        color = mod_color(m["id"])

        hdr = QHBoxLayout()
        dot = ColorDot(color, 12)
        hdr.addWidget(dot)
        name_lbl = QLabel(m["name"])
        name_lbl.setStyleSheet("font-size: 15px; font-weight: bold;")
        hdr.addWidget(name_lbl, 1)
        d = days_until(m["exam_date"])
        if d is None:
            d_txt, d_col = "Kein Datum", "#9E9E9E"
        elif d < 0:
            d_txt, d_col = f"Vor {abs(d)} Tagen", "#9E9E9E"
        elif d == 0:
            d_txt, d_col = "HEUTE!", "#F44336"
        elif d <= 7:
            d_txt, d_col = f"in {d} Tagen", "#FF9800"
        else:
            d_txt, d_col = f"in {d} Tagen", "#4A86E8"
        date_lbl = QLabel(f"{m['exam_date']}  —  {d_txt}")
        date_lbl.setStyleSheet(f"color: {d_col}; font-weight: bold;")
        hdr.addWidget(date_lbl)
        lay.addLayout(hdr)

        target = self.repo.ects_target_hours(m["id"])
        studied_h = self.repo.seconds_studied_for_module(m["id"]) / 3600
        pct = min(100, int(studied_h / target * 100)) if target > 0 else 0
        prog_row = QHBoxLayout()
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setFixedHeight(8)
        bar.setTextVisible(False)
        bar.setStyleSheet(f"QProgressBar::chunk {{background:{color};border-radius:4px;}}")
        prog_row.addWidget(bar, 1)
        prog_lbl = QLabel(f"{studied_h:.1f}h / {target:.0f}h ({pct}%)")
        prog_lbl.setStyleSheet("color: #8B8FA8; font-size: 12px; min-width: 130px;")
        prog_row.addWidget(prog_lbl)
        lay.addLayout(prog_row)

        summary = self.repo.knowledge_summary(m["id"])
        total_topics = sum(summary.values())
        if total_topics > 0:
            known = summary.get("3", 0) + summary.get("4", 0)
            unknown = summary.get("0", 0) + summary.get("1", 0)
            topic_lbl = QLabel(
                f"{total_topics} Themen  |  {known} gut beherrscht  |  {unknown} offen"
            )
            topic_lbl.setStyleSheet("color: #8B8FA8; font-size: 12px;")
            lay.addWidget(topic_lbl)
        return card


class GradesPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel(tr("page.grades"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = QPushButton("+ Note hinzufugen")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_grade)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        frow = QHBoxLayout()
        frow.addWidget(QLabel("Modul:"))
        self.mod_filter = QComboBox()
        self.mod_filter.addItem("Alle Module", None)
        self.mod_filter.currentIndexChanged.connect(self._load_grades)
        frow.addWidget(self.mod_filter)
        frow.addStretch()
        self.avg_lbl = QLabel()
        self.avg_lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #4A86E8;")
        frow.addWidget(self.avg_lbl)
        lay.addLayout(frow)

        self.summary_w = QWidget()
        self.summary_row = QHBoxLayout(self.summary_w)
        self.summary_row.setSpacing(12)
        self.summary_row.addStretch()
        sum_sa = QScrollArea()
        sum_sa.setWidgetResizable(True)
        sum_sa.setFrameShape(QFrame.NoFrame)
        sum_sa.setFixedHeight(105)
        sum_sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sum_sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sum_sa.setWidget(self.summary_w)
        lay.addWidget(sum_sa)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Modul", "Titel", "Punkte", "Max", "Gewicht", "Datum", "ID"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col in range(2, 7):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.setColumnHidden(6, True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._edit_grade)
        lay.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        del_btn = QPushButton("Gewahlte loschen")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_grade)
        bottom.addWidget(del_btn)
        lay.addLayout(bottom)

    def refresh(self):
        cur = self.mod_filter.currentData()
        self.mod_filter.blockSignals(True)
        self.mod_filter.clear()
        self.mod_filter.addItem("Alle Module", None)
        for m in self.repo.list_modules("all"):
            self.mod_filter.addItem(m["name"], m["id"])
        if cur:
            for i in range(self.mod_filter.count()):
                if self.mod_filter.itemData(i) == cur:
                    self.mod_filter.setCurrentIndex(i)
                    break
        self.mod_filter.blockSignals(False)
        self._load_summary()
        self._load_grades()

    def _load_summary(self):
        while self.summary_row.count() > 1:
            item = self.summary_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, m in enumerate(self.repo.list_modules("all")):
            avg = self.repo.module_weighted_grade(m["id"])
            if avg is None:
                continue
            card = QFrame()
            card.setObjectName("Card")
            card.setFixedSize(155, 82)
            clay = QVBoxLayout(card)
            clay.setContentsMargins(12, 8, 12, 8)
            color = mod_color(m["id"])
            nl = QLabel(m["name"])
            nl.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: bold;")
            nl.setWordWrap(True)
            clay.addWidget(nl)
            al = QLabel(f"{avg:.1f}%")
            al.setStyleSheet(
                f"font-size: 22px; font-weight: bold; "
                f"color: {'#4CAF50' if avg >= 60 else '#F44336'};"
            )
            clay.addWidget(al)
            self.summary_row.insertWidget(i, card)

    def _load_grades(self):
        mid = self.mod_filter.currentData()
        grades = self.repo.list_grades(module_id=mid)
        self.table.setRowCount(len(grades))
        for r, g in enumerate(grades):
            self.table.setItem(r, 0, QTableWidgetItem(g["module_name"]))
            self.table.setItem(r, 1, QTableWidgetItem(g["title"]))
            pct = float(g["grade"]) / float(g["max_grade"]) * 100
            pi = QTableWidgetItem(f"{g['grade']:.1f} ({pct:.1f}%)")
            pi.setForeground(QColor("#4CAF50" if pct >= 60 else "#F44336"))
            self.table.setItem(r, 2, pi)
            self.table.setItem(r, 3, QTableWidgetItem(f"{g['max_grade']:.0f}"))
            self.table.setItem(r, 4, QTableWidgetItem(f"{g['weight']:.2f}"))
            self.table.setItem(r, 5, QTableWidgetItem(g["date"] or "—"))
            self.table.setItem(r, 6, QTableWidgetItem(str(g["id"])))
        if mid:
            avg = self.repo.module_weighted_grade(mid)
            self.avg_lbl.setText(f"Durchschnitt: {avg:.1f}%" if avg is not None else "—")
        else:
            self.avg_lbl.setText("")

    def _add_grade(self):
        mid = self.mod_filter.currentData()
        if GradeDialog(self.repo, default_module_id=mid, parent=self).exec():
            self.refresh()

    def _edit_grade(self):
        row = self.table.currentRow()
        if row < 0:
            return
        gid = int(self.table.item(row, 6).text())
        if GradeDialog(self.repo, grade_id=gid, parent=self).exec():
            self.refresh()

    def _delete_grade(self):
        row = self.table.currentRow()
        if row < 0:
            return
        gid = int(self.table.item(row, 6).text())
        if QMessageBox.question(self, "Loschen", "Note loschen?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_grade(gid)
            self.refresh()


class SettingsPage(QWidget):
    theme_changed = Signal(str)

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
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

        self.lang_cb = QComboBox()
        self.lang_cb.addItems(["Deutsch 🇩🇪", "English 🇬🇧", "Français 🇫🇷", "Italiano 🇮🇹"])
        lang_map = {"de": 0, "en": 1, "fr": 2, "it": 3}
        lang = self.repo.get_setting("language") or "de"
        self.lang_cb.setCurrentIndex(lang_map.get(lang, 0))
        self.lang_cb.currentIndexChanged.connect(self._on_lang)
        app_lay.addRow("Sprache:", self.lang_cb)

        lang_note = QLabel("* Sprachänderung wird beim nächsten Start vollständig angewendet.")
        lang_note.setStyleSheet("color: #8B8FA8; font-size: 11px;")
        lang_note.setWordWrap(True)
        app_lay.addRow("", lang_note)
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
        lay.addStretch()

        about = QLabel("Study Organizer v2.0  |  Powered by PySide6 + SQLite")
        about.setStyleSheet("color: #8B8FA8; font-size: 12px;")
        about.setAlignment(Qt.AlignCenter)
        lay.addWidget(about)

    def refresh(self):
        self.ects_spin.setValue(self.repo.hours_per_ects())
        theme = self.repo.get_setting("theme") or "light"
        self.theme_cb.setCurrentIndex(0 if theme == "light" else 1)
        lang_map = {"de": 0, "en": 1, "fr": 2, "it": 3}
        lang = self.repo.get_setting("language") or "de"
        self.lang_cb.blockSignals(True)
        self.lang_cb.setCurrentIndex(lang_map.get(lang, 0))
        self.lang_cb.blockSignals(False)
        modules = self.repo.list_modules("all")
        tasks = self.repo.list_tasks()
        logs = self.repo.list_time_logs()
        total_secs = sum(int(l["seconds"]) for l in logs)
        self.total_modules_lbl.setText(str(len(modules)))
        self.total_tasks_lbl.setText(str(len(tasks)))
        self.total_hours_lbl.setText(f"{total_secs/3600:.1f}h")

    def _on_theme(self):
        theme = "dark" if self.theme_cb.currentIndex() == 1 else "light"
        self.repo.set_setting("theme", theme)
        self.theme_changed.emit(theme)

    def _on_lang(self):
        langs = ["de", "en", "fr", "it"]
        idx = self.lang_cb.currentIndex()
        lang = langs[idx] if 0 <= idx < len(langs) else "de"
        self.repo.set_setting("language", lang)

    def _save(self):
        self.repo.set_setting("hours_per_ects", str(self.ects_spin.value()))
        QMessageBox.information(self, "Gespeichert", "Einstellungen wurden gespeichert.")


# ── Credits Page ──────────────────────────────────────────────────────────

class CreditsPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addStretch(1)

        content = QWidget()
        content.setMaximumWidth(680)
        content.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(24)

        # App logo area
        logo_lbl = QLabel("📚")
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet("font-size: 64px;")
        lay.addWidget(logo_lbl)

        app_name = QLabel("Study Organizer")
        app_name.setAlignment(Qt.AlignCenter)
        app_name.setStyleSheet(
            "font-size: 32px; font-weight: bold; color: #4A86E8; letter-spacing: 2px;"
        )
        lay.addWidget(app_name)

        version_lbl = QLabel("v2.0  —  Powered by Python · PySide6 · SQLite")
        version_lbl.setAlignment(Qt.AlignCenter)
        version_lbl.setStyleSheet("font-size: 13px; color: #8B8FA8; margin-bottom: 8px;")
        lay.addWidget(version_lbl)

        # Divider
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("color: #DDE3F0;")
        lay.addWidget(sep1)

        # Mission statement
        mission_title = QLabel("Unsere Mission")
        mission_title.setObjectName("SectionTitle")
        mission_title.setAlignment(Qt.AlignCenter)
        lay.addWidget(mission_title)

        mission_text = QLabel(
            "Study Organizer wurde entwickelt, um tausenden Studierenden\n"
            "das Studium realistisch einfacher zu machen.\n\n"
            "Ob Prüfungsvorbereitung, Aufgabenverwaltung, Zeitplanung oder\n"
            "Notentracking — alles an einem Ort, übersichtlich und effizient."
        )
        mission_text.setAlignment(Qt.AlignCenter)
        mission_text.setWordWrap(True)
        mission_text.setStyleSheet("font-size: 14px; color: #6B7899; line-height: 1.6;")
        lay.addWidget(mission_text)

        # Divider
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #DDE3F0;")
        lay.addWidget(sep2)

        # Creator card
        creator_card = QFrame()
        creator_card.setObjectName("Card")
        card_lay = QVBoxLayout(creator_card)
        card_lay.setContentsMargins(24, 20, 24, 20)
        card_lay.setSpacing(8)

        created_by = QLabel("Erstellt von")
        created_by.setAlignment(Qt.AlignCenter)
        created_by.setStyleSheet("font-size: 11px; color: #8B8FA8; text-transform: uppercase; letter-spacing: 1px;")
        card_lay.addWidget(created_by)

        author_name = QLabel("Lopicic")
        author_name.setAlignment(Qt.AlignCenter)
        author_name.setStyleSheet(
            "font-size: 28px; font-weight: bold; color: #4A86E8;"
        )
        card_lay.addWidget(author_name)

        author_email = QLabel("ziqcreate@gmail.com")
        author_email.setAlignment(Qt.AlignCenter)
        author_email.setStyleSheet("font-size: 13px; color: #8B8FA8;")
        card_lay.addWidget(author_email)

        author_sub = QLabel("Student · Entwickler · Gestalter")
        author_sub.setAlignment(Qt.AlignCenter)
        author_sub.setStyleSheet("font-size: 12px; color: #9BA8D0; margin-top: 4px;")
        card_lay.addWidget(author_sub)
        lay.addWidget(creator_card)

        # Features list
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet("color: #DDE3F0;")
        lay.addWidget(sep3)

        features_title = QLabel("Was der Study Organizer bietet")
        features_title.setObjectName("SectionTitle")
        features_title.setAlignment(Qt.AlignCenter)
        lay.addWidget(features_title)

        features = [
            ("📚", "Module & Semester verwalten"),
            ("✅", "Aufgaben mit Prioritäten tracken"),
            ("📅", "Kalender mit Ereignissen & Prüfungen"),
            ("🧠", "Wissensstand pro Thema bewerten"),
            ("⏱", "Pomodoro-Timer mit Zeiterfassung"),
            ("🎯", "Prüfungsvorbereitung im Überblick"),
            ("📈", "Noten & Durchschnitt berechnen"),
        ]
        feat_grid = QGridLayout()
        feat_grid.setSpacing(10)
        for i, (icon, text) in enumerate(features):
            row, col = divmod(i, 2)
            feat_lbl = QLabel(f"{icon}  {text}")
            feat_lbl.setStyleSheet("font-size: 13px; color: #6B7899; padding: 4px 0;")
            feat_grid.addWidget(feat_lbl, row, col)
        lay.addLayout(feat_grid)

        # Footer
        footer = QLabel("© 2024 Lopicic  |  Open Source  |  Made with ❤️ for students")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("font-size: 11px; color: #8B8FA8; margin-top: 8px;")
        lay.addWidget(footer)

        # Center the card
        h_center = QHBoxLayout()
        h_center.addStretch(1)
        h_center.addWidget(content)
        h_center.addStretch(1)
        outer.addLayout(h_center)
        outer.addStretch(1)

    def refresh(self):
        pass  # static page


# ── Sidebar ───────────────────────────────────────────────────────────────

class SidebarWidget(QWidget):
    page_selected = Signal(int)

    # (emoji, translation_key)  — all emojis have U+FE0F selector for consistent rendering
    NAV_ITEMS = [
        ("🏠\uFE0F", "nav.dashboard"),
        ("📚\uFE0F", "nav.modules"),
        ("✅\uFE0F", "nav.tasks"),
        ("📅\uFE0F", "nav.calendar"),
        ("📊\uFE0F", "nav.timeline"),
        ("🧠\uFE0F", "nav.knowledge"),
        ("⏱\uFE0F",  "nav.timer"),
        ("🎯\uFE0F", "nav.exams"),
        ("📈\uFE0F", "nav.grades"),
        ("⚙\uFE0F",  "nav.settings"),
        ("ℹ\uFE0F",  "nav.credits"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(225)
        # CRITICAL: needed on Linux for background-color to render
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._buttons: List[QPushButton] = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 24, 10, 20)
        lay.setSpacing(2)

        title = QLabel("StudyOrganizer")
        title.setObjectName("AppTitle")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        ver = QLabel("v2.0")
        ver.setObjectName("AppVersion")
        ver.setAlignment(Qt.AlignCenter)
        lay.addWidget(ver)

        lay.addSpacing(8)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #252545;")
        lay.addWidget(sep)
        lay.addSpacing(8)

        for idx, (icon, key) in enumerate(self.NAV_ITEMS):
            label = tr(key)
            btn = QPushButton(f"  {icon}  {label}")
            btn.setObjectName("NavBtn")
            btn.setFixedHeight(42)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self._select(i))
            self._buttons.append(btn)
            lay.addWidget(btn)

        lay.addStretch()
        self._highlight(0)

    def _select(self, idx: int):
        self._highlight(idx)
        self.page_selected.emit(idx)

    def _highlight(self, idx: int):
        for i, btn in enumerate(self._buttons):
            active = "true" if i == idx else "false"
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def select(self, idx: int):
        self._highlight(idx)


# ── Main Window ───────────────────────────────────────────────────────────

class StudyOrganizerWindow(QMainWindow):
    def __init__(self, repo: SqliteRepo):
        super().__init__()
        self.repo = repo
        self.setWindowTitle("Study Organizer")
        self.setMinimumSize(900, 600)
        self.resize(1280, 800)
        self._build()
        self._apply_theme(repo.get_setting("theme") or "light")
        self._switch_page(0)

    def mouseDoubleClickEvent(self, event):
        """Double-click anywhere in the window to toggle maximize/restore."""
        if event.button() == Qt.LeftButton:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()
        super().mouseDoubleClickEvent(event)

    def _build(self):
        central = QWidget()
        central.setObjectName("PageContent")
        # CRITICAL: needed on Linux for background-color to render
        central.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(central)

        main_lay = QHBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        self.sidebar = SidebarWidget()
        self.sidebar.page_selected.connect(self._switch_page)
        main_lay.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        main_lay.addWidget(self.stack, 1)

        self.dashboard = DashboardPage(self.repo)
        self.modules_page = ModulesPage(self.repo)
        self.tasks_page = TasksPage(self.repo)
        self.calendar_page = CalendarPage(self.repo)
        self.timeline_page = TimelinePage(self.repo)
        self.knowledge_page = KnowledgePage(self.repo)
        self.timer_page = TimerPage(self.repo)
        self.exam_page = ExamPage(self.repo)
        self.grades_page = GradesPage(self.repo)
        self.settings_page = SettingsPage(self.repo)
        self.credits_page = CreditsPage(self.repo)

        self.settings_page.theme_changed.connect(self._apply_theme)

        for page in [self.dashboard, self.modules_page, self.tasks_page,
                     self.calendar_page, self.timeline_page, self.knowledge_page,
                     self.timer_page, self.exam_page, self.grades_page,
                     self.settings_page, self.credits_page]:
            self.stack.addWidget(page)

    def _switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self.sidebar.select(idx)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def _apply_theme(self, theme: str):
        qss = DARK_QSS if theme == "dark" else LIGHT_QSS
        # Apply to app so ALL widgets (dialogs, etc.) get the theme
        QApplication.instance().setStyleSheet(qss)


# ── Entry point ───────────────────────────────────────────────────────────

def gui_main(repo: SqliteRepo) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Study Organizer")
    # Fusion style = consistent look on all platforms (Linux/Windows/Mac)
    app.setStyle("Fusion")
    # Apply saved language BEFORE any widget is created, so tr() returns correct strings
    set_lang(repo.get_setting("language") or "de")
    window = StudyOrganizerWindow(repo)
    window.show()
    sys.exit(app.exec())
