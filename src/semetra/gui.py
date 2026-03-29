from __future__ import annotations

import sys
import time as _time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QScrollArea, QFrame,
    QLineEdit, QTextEdit, QComboBox as _QCBBase, QSpinBox, QDoubleSpinBox,
    QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QGridLayout,
    QSizePolicy, QMessageBox, QCalendarWidget, QProgressBar,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QCheckBox, QGroupBox, QSplitter, QHeaderView, QAbstractItemView,
    QFileDialog, QTabWidget, QDockWidget, QToolButton,
)
from PySide6.QtCore import (
    Qt, QTimer, QDate, QSize, Signal, Slot, QEvent, QObject, QPoint,
    QUrl, QThread, QPropertyAnimation, QEasingCurve, Property,
)
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPixmap,
    QPainterPath, QLinearGradient, QDragEnterEvent, QDropEvent,
)

from pathlib import Path
import subprocess as _subprocess

from semetra.repo.sqlite_repo import SqliteRepo

# ── WSL-aware URL opener ───────────────────────────────────────────────────
# On WSL, QDesktopServices.openUrl() calls xdg-open which fails when no
# Linux browser is installed.  Detect WSL once at import time and use
# cmd.exe /c start as a fallback so links open in the Windows browser.
def _is_running_on_wsl() -> bool:
    try:
        with open("/proc/version") as _f:
            return "microsoft" in _f.read().lower()
    except Exception:
        return False

_ON_WSL: bool = _is_running_on_wsl()


def _open_url_safe(url: str) -> None:
    """Open *url* in the system browser.

    On WSL the standard QDesktopServices path goes through xdg-open which
    usually fails because no Linux browser is configured.  We detect WSL and
    delegate to ``cmd.exe /c start`` instead, which opens the URL in whatever
    Windows browser the user has set as default.
    """
    from PySide6.QtGui import QDesktopServices  # local import — gui module only
    from PySide6.QtCore import QUrl as _QUrl
    if _ON_WSL:
        try:
            # cmd.exe expects an empty first arg when the target contains query strings
            _subprocess.Popen(["cmd.exe", "/c", "start", "", url])
            return
        except Exception:
            pass  # fall through to Qt default
    QDesktopServices.openUrl(_QUrl(url))

# Alias for convenience
_open_url = _open_url_safe

# ── Wayland-safe QComboBox ─────────────────────────────────────────────────
# On Wayland the native QComboBox popup is a compositor surface that receives
# hover events but swallows mouse-click events, so items can't be selected.
# We shadow QComboBox throughout this module with a subclass that replaces
# showPopup() with a QFrame *child* of the parent window — no separate OS
# window means no WM/compositor positioning interference.  Position is
# computed with mapTo() which is pure Qt and perfectly accurate.

class QComboBox(_QCBBase):
    """Drop-in QComboBox replacement: in-window overlay popup, zero WM involvement."""

    _popup: Optional[QFrame] = None

    def showPopup(self) -> None:
        n = self.count()
        if n == 0:
            return
        self.hidePopup()   # close any previous popup first

        # Attach the overlay to the topmost ancestor so it can float above
        # all sibling widgets without leaving the window coordinate space.
        root = self.window()

        frm = QFrame(root)
        frm.setObjectName("ComboPopupOverlay")
        frm.setAttribute(Qt.WA_StyledBackground, True)
        frm.raise_()
        self._popup = frm

        lay = QVBoxLayout(frm)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(0)

        lw = QListWidget()
        lw.setFrameShape(QFrame.NoFrame)
        lw.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for i in range(n):
            it = QListWidgetItem(self.itemText(i))
            it.setData(Qt.UserRole, self.itemData(i))
            lw.addItem(it)
        if 0 <= self.currentIndex() < n:
            lw.setCurrentRow(self.currentIndex())
        lay.addWidget(lw)

        # ── Event filter: dismiss on click outside ──────────────────────
        class _OutsideFilter(QObject):
            def eventFilter(_, obj, event):   # type: ignore[override]
                if event.type() == QEvent.MouseButtonPress:
                    try:
                        gp = event.globalPosition().toPoint()
                    except AttributeError:
                        gp = event.globalPos()
                    if not frm.rect().contains(frm.mapFromGlobal(gp)):
                        _close()
                return False

        _filter = _OutsideFilter(frm)
        frm._outside_filter = _filter        # keep alive
        QApplication.instance().installEventFilter(_filter)

        def _close():
            if self._popup is frm:
                self._popup = None
            try:
                QApplication.instance().removeEventFilter(
                    frm._outside_filter)  # type: ignore[attr-defined]
            except Exception:
                pass
            frm.hide()
            frm.deleteLater()

        def _pick(_item=None):
            row = lw.currentRow()
            _close()
            if row >= 0 and row != self.currentIndex():
                self.setCurrentIndex(row)
                self.activated.emit(row)

        lw.itemClicked.connect(_pick)
        lw.itemActivated.connect(_pick)   # keyboard Enter / Return

        # ── Position: flush below the combo, in root coordinates ────────
        pos_in_root = self.mapTo(root, QPoint(0, self.height()))
        row_h = max(lw.sizeHintForRow(0), 28) if n > 0 else 28
        pw = max(self.width(), 220)
        ph = min(row_h * n + 8, 360)
        frm.setGeometry(pos_in_root.x(), pos_in_root.y(), pw, ph)
        frm.show()
        frm.raise_()

    def hidePopup(self) -> None:
        if self._popup is not None:
            p = self._popup
            self._popup = None
            try:
                QApplication.instance().removeEventFilter(
                    p._outside_filter)   # type: ignore[attr-defined]
            except Exception:
                pass
            p.hide()
            p.deleteLater()


# ── Constants ──────────────────────────────────────────────────────────────

MODULE_COLORS = [
    "#4A86E8", "#E84A5F", "#2CB67D", "#FF8C42", "#9B59B6",
    "#00B4D8", "#F72585", "#3A86FF", "#F4A261", "#2EC4B6",
]

KNOWLEDGE_COLORS = {0: "#9E9E9E", 1: "#F44336", 2: "#FF9800", 3: "#8BC34A", 4: "#4CAF50"}
KNOWLEDGE_LABELS = {0: "Nicht begonnen", 1: "Grundlagen", 2: "Vertraut", 3: "Gut", 4: "Experte"}
def tr_know(k: int) -> str:
    _map = {0:"know.not_started",1:"know.basics",2:"know.familiar",3:"know.good",4:"know.expert"}
    return tr(_map[k]) if k in _map else KNOWLEDGE_LABELS.get(k, str(k))
PRIORITY_COLORS = {"Critical": "#F44336", "High": "#FF9800", "Medium": "#7C3AED", "Low": "#9E9E9E"}
STATUS_LABELS = {"planned": "Geplant", "active": "Aktiv", "completed": "Abgeschlossen", "paused": "Pausiert"}

# ── Motivational Quotes ─────────────────────────────────────────────────────
# Shown daily on the Dashboard — one per day, deterministic (date-based index).
STUDENT_QUOTES: list[tuple[str, str]] = [
    ("Du musst nicht perfekt sein. Du musst nur anfangen.", ""),
    ("Jeder Experte war einmal ein Anfänger.", "Helen Hayes"),
    ("Investiere in dein Wissen — es trägt Zinsen dein Leben lang.", "Benjamin Franklin"),
    ("Der Anfang ist die Hälfte des Ganzen.", "Aristoteles"),
    ("Bildung ist das mächtigste Werkzeug, das du nutzen kannst, um die Welt zu verändern.", "Nelson Mandela"),
    ("Du schaffst das. Schritt für Schritt, Tag für Tag.", ""),
    ("Misserfolg ist nur eine Umleitung, kein Ende.", ""),
    ("Konzentrier dich auf den Fortschritt, nicht auf Perfektion.", ""),
    ("Die meisten Menschen scheitern nicht, weil sie versagen — sondern weil sie aufhören.", ""),
    ("Wer aufhört zu lernen, hört auf zu wachsen.", ""),
    ("Kleine Fortschritte jeden Tag summieren sich zu großen Ergebnissen.", ""),
    ("Dein zukünftiges Ich dankt dir für das, was du heute tust.", ""),
    ("Es wird schwer — und das ist genau der Punkt. Das Schwere ist es, was es wertvoll macht.", ""),
    ("Nicht die Zeit fehlt, sondern die Entscheidung, sie zu nutzen.", ""),
    ("Lerne nicht für die Note. Lerne für das Verständnis.", ""),
    ("Jeder Schritt vorwärts — egal wie klein — ist ein Sieg.", ""),
    ("Du bist fähiger, als du glaubst.", "A. A. Milne"),
    ("Die Hürden, die du überwindest, formen dich mehr als die Wege ohne Hindernisse.", ""),
    ("Motiviere dich nicht durch Angst vor Misserfolg, sondern durch Freude am Wachsen.", ""),
    ("Fang an. Das ist alles, was du jetzt tun musst.", ""),
    ("Wissen ist der einzige Besitz, den dir niemand nehmen kann.", ""),
    ("Heute ist der beste Tag, um etwas Neues zu lernen.", ""),
    ("Eine Stunde konzentriertes Lernen schlägt drei Stunden passives Lesen.", ""),
    ("Glaub nicht an die Grenzen, die andere für dich gesetzt haben.", ""),
    ("Dein Gehirn ist flexibler als du denkst — nutze es.", ""),
    ("Du musst nicht schnell lernen. Du musst nur nicht aufhören.", ""),
    ("Studieren ist keine Last — es ist ein Privileg.", ""),
    ("Die Energie, die du in dein Wissen investierst, kehrt tausendfach zurück.", ""),
    ("Zwischen heute und deinem Ziel liegt nur Ausdauer.", ""),
    ("Rückschläge sind keine Niederlagen. Sie sind Hinweise.", ""),
]
# tr_status() returns a translated status string (use in refresh() contexts)
def tr_status(s: str) -> str:
    _map = {"planned": "status.planned", "active": "status.active",
            "completed": "status.completed", "paused": "status.paused",
            "Done": "status.done", "Open": "status.open"}
    return tr(_map[s]) if s in _map else s


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


def exam_priority(exam_date_str: Optional[str]) -> str:
    """Auto-compute task priority based on days remaining until exam.

    ≤5 days  → Critical
    ≤10 days → High
    ≤15 days → Medium
    otherwise → Low
    """
    d = days_until(exam_date_str)
    if d is None or d < 0:
        return "Low"
    if d <= 5:
        return "Critical"
    if d <= 10:
        return "High"
    if d <= 15:
        return "Medium"
    return "Low"


# ── Swiss FH Grading Helpers ────────────────────────────────────────────────
# FFHS / Swiss FH grade scale: 1.0 (worst) – 6.0 (best), passing ≥ 4.0
# Conversion formula:  Note = (Punkte / MaxPunkte) × 5 + 1
# → 60 % →  Note 4.0  (Bestehensgrenze)
# → 80 % →  Note 5.0  (Gut)
# → 100% →  Note 6.0  (Sehr gut)

def pct_to_ch_grade(pct: float) -> float:
    """Convert percentage (0–100) to Swiss FH grade (1.0–6.0).
    Result is NOT rounded — use for display rounding separately."""
    return (pct / 100.0) * 5.0 + 1.0


def ch_grade_rounded(pct: float) -> float:
    """Convert percentage to Swiss FH grade rounded to nearest 0.5 step."""
    raw = pct_to_ch_grade(pct)
    return round(raw * 2) / 2


def _grade_color(grade: float) -> str:
    """Theme-adaptive text colour for a Swiss 1–6 grade."""
    if grade >= 5.5: return _tc("#1B5E20", "#69F0AE")   # excellent  (deep/bright green)
    if grade >= 5.0: return _tc("#2E7D32", "#4CAF50")   # good
    if grade >= 4.5: return _tc("#558B2F", "#8BC34A")   # satisfactory
    if grade >= 4.0: return _tc("#E65100", "#FFA726")   # just passing (amber)
    if grade >= 3.5: return _tc("#BF360C", "#FF7043")   # at risk      (deep orange)
    return _tc("#B71C1C", "#EF5350")                     # fail          (red)


def _grade_bg(grade: float) -> str:
    """Subtle card background colour for a Swiss grade (theme-adaptive)."""
    if grade >= 5.5: return _tc("#E8F5E9", "#1B3A2B")
    if grade >= 5.0: return _tc("#F1F8E9", "#1A2E1A")
    if grade >= 4.5: return _tc("#F9FBE7", "#1E2A10")
    if grade >= 4.0: return _tc("#FFF3E0", "#3A2200")
    if grade >= 3.5: return _tc("#FBE9E7", "#3A1800")
    return _tc("#FFEBEE", "#3A0000")


def _grade_border(grade: float) -> str:
    """Card border colour for a Swiss grade."""
    if grade >= 5.5: return _tc("#A5D6A7", "#388E3C")
    if grade >= 5.0: return _tc("#C5E1A5", "#558B2F")
    if grade >= 4.5: return _tc("#DCE775", "#827717")
    if grade >= 4.0: return _tc("#FFCC80", "#E65100")
    if grade >= 3.5: return _tc("#FFAB91", "#BF360C")
    return _tc("#EF9A9A", "#B71C1C")


def _grade_label(grade: float) -> str:
    """Human-readable status label for Swiss 1–6 grade."""
    if grade >= 5.5: return "Sehr gut"
    if grade >= 5.0: return "Gut"
    if grade >= 4.5: return "Befriedigend"
    if grade >= 4.0: return "Genügend"
    if grade >= 3.5: return "⚠ Gefährdet!"
    return "✗ Nicht bestanden"


def _grade_icon(grade: float) -> str:
    """Emoji icon for Swiss grade status."""
    if grade >= 5.5: return "✨"
    if grade >= 5.0: return "✅"
    if grade >= 4.5: return "🟢"
    if grade >= 4.0: return "🟡"
    if grade >= 3.5: return "🟠"
    return "🔴"


# ─────────────────────────────────────────────────────────────────────────────

def _active_sem_filter(repo: "SqliteRepo") -> str:
    """Returns the currently selected semester filter value, or '' for all."""
    return (repo.get_setting("filter_semester") or "").strip()


def _filter_mods_by_sem(modules, sem: str) -> list:
    """Filter a list of module rows to those matching *sem*.  '' = show all."""
    if not sem:
        return list(modules)
    return [m for m in modules if str(m["semester"] or "").strip() == sem]


def fmt_hms(secs: int) -> str:
    h, r = divmod(abs(secs), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ── Translations ──────────────────────────────────────────────────────────

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "de": {
        # ── Nav ──
        "nav.dashboard": "Dashboard",    "nav.focus": "Fokus-Modus",
        "nav.modules": "Module",         "nav.tasks": "Aufgaben",
        "nav.calendar": "Kalender",      "nav.timeline": "Studienplan",
        "nav.knowledge": "Wissen",       "nav.timer": "Timer",
        "nav.exams": "Prüfungen",        "nav.grades": "Noten",
        "nav.settings": "Einstellungen", "nav.credits": "Credits",
        "nav.stundenplan": "Stundenplan",
        # ── Greetings ──
        "greet.morning": "Guten Morgen", "greet.day": "Guten Tag",
        "greet.evening": "Guten Abend",
        # ── Page titles ──
        "page.dashboard": "Dashboard",   "page.modules": "Module",
        "page.tasks": "Aufgaben",        "page.calendar": "Kalender",
        "page.timeline": "Studienplan & Überblick",
        "page.knowledge": "Wissensübersicht",
        "page.timer": "Fokus-Timer",     "page.exams": "Prüfungsvorbereitung",
        "page.grades": "Noten",          "page.settings": "Einstellungen",
        "page.credits": "Credits",
        # ── Common buttons ──
        "btn.new": "+ Neu",              "btn.save": "Speichern",
        "btn.cancel": "Abbrechen",       "btn.delete": "Löschen",
        "btn.edit": "Bearbeiten",        "btn.close": "Schließen",
        "btn.add": "Hinzufügen",         "btn.search": "Suchen...",
        "btn.import": "Importieren",     "btn.export": "Exportieren",
        # ── Section titles ──
        "sec.modules": "Module & Fächer",
        "sec.tasks": "Aufgaben",         "sec.calendar": "Kalender",
        "sec.upcoming": "Nächste 14 Tage",
        "sec.today": "Heute",
        "sec.knowledge": "Wissensstand",
        "sec.resources": "Ressourcen",
        "sec.notes": "📖 Lerninhalt:",
        "sec.topics": "Themen",
        "sec.sessions": "Sitzungen: {n}",
        "sec.study_time": "Lernzeit",
        "sec.overview": "Übersicht",
        "sec.exams_upcoming": "Bevorstehende Prüfungen",
        "sec.progress": "Fortschritt",
        # ── Status labels ──
        "status.planned": "Geplant",     "status.active": "Aktiv",
        "status.completed": "Abgeschlossen", "status.paused": "Pausiert",
        "status.done": "Erledigt",       "status.open": "Offen",
        # ── Priority labels ──
        "prio.critical": "Kritisch",     "prio.high": "Hoch",
        "prio.medium": "Mittel",         "prio.low": "Niedrig",
        # ── Timer ──
        "timer.focus": "Fokus-Phase",    "timer.break": "Pause",
        "timer.start": "Start",          "timer.stop": "Stop",
        "timer.reset": "Reset",          "timer.module": "Modul:",
        "timer.note": "Notiz zur Sitzung (optional)...",
        # ── Dashboard ──
        "dash.modules_active": "Aktive Module",
        "dash.tasks_open": "Offene Aufgaben",
        "dash.tasks_due": "Fällig heute",
        "dash.study_hours": "Lernstunden (7T)",
        "dash.upcoming_exams": "Bevorstehende Prüfungen",
        "dash.recent_tasks": "Aktuelle Aufgaben",
        "dash.no_exams": "Keine bevorstehenden Prüfungen",
        "dash.no_tasks": "Keine offenen Aufgaben",
        # ── Modules ──
        "mod.add_resource": "Ressource hinzufügen",
        "mod.no_module": "Kein Modul ausgewählt",
        "mod.select_hint": "Wähle ein Modul aus der Liste links",
        "mod.target_hours": "Zielstunden",
        "mod.studied_hours": "Studiert",
        # ── Tasks ──
        "task.title": "Titel",           "task.module": "Modul",
        "task.priority": "Priorität",    "task.status": "Status",
        "task.due": "Fällig",            "task.search": "Aufgaben suchen...",
        "task.new": "+ Neue Aufgabe",
        "task.delete_sel": "Ausgewählte löschen",
        # ── Grades ──
        "grade.add": "+ Note hinzufügen",
        "grade.all_modules": "Alle Module",
        "grade.avg": "Durchschnitt: {val}%",
        "grade.delete_sel": "Ausgewählte löschen",
        "grade.col.module": "Modul",     "grade.col.title": "Titel",
        "grade.col.points": "Punkte",    "grade.col.max": "Max",
        "grade.col.weight": "Gewicht",   "grade.col.date": "Datum",
        # ── Settings ──
        "set.theme": "Thema",            "set.language": "Sprache",
        "set.dark": "Dunkel",            "set.light": "Hell",
        "set.lang_note": "Sprachänderung gilt sofort.",
        # ── Calendar ──
        "cal.add_event": "+ Ereignis",
        "cal.delete_event": "Löschen",
        "cal.no_events": "Keine Ereignisse",
        # ── Knowledge ──
        "know.level": "Wissensstufe",
        "know.not_started": "Nicht begonnen",
        "know.basics": "Grundlagen",
        "know.familiar": "Vertraut",
        "know.good": "Gut",
        "know.expert": "Experte",
        # ── Exam ──
        "exam.add": "+ Prüfung",
        "exam.no_exams": "Keine Prüfungen",
        "exam.days_left": "{n} Tage",
        "exam.today": "Heute",
        "exam.passed": "Vorbei",
    },
    "en": {
        # ── Nav ──
        "nav.dashboard": "Dashboard",    "nav.focus": "Focus Mode",
        "nav.modules": "Modules",        "nav.tasks": "Tasks",
        "nav.calendar": "Calendar",      "nav.timeline": "Study Plan",
        "nav.knowledge": "Knowledge",    "nav.timer": "Timer",
        "nav.exams": "Exams",            "nav.grades": "Grades",
        "nav.settings": "Settings",      "nav.credits": "Credits",
        "nav.stundenplan": "Timetable",
        # ── Greetings ──
        "greet.morning": "Good Morning", "greet.day": "Good Afternoon",
        "greet.evening": "Good Evening",
        # ── Page titles ──
        "page.dashboard": "Dashboard",   "page.modules": "Modules",
        "page.tasks": "Tasks",           "page.calendar": "Calendar",
        "page.timeline": "Study Plan & Overview",
        "page.knowledge": "Knowledge Overview",
        "page.timer": "Focus Timer",     "page.exams": "Exam Preparation",
        "page.grades": "Grades",         "page.settings": "Settings",
        "page.credits": "Credits",
        # ── Common buttons ──
        "btn.new": "+ New",              "btn.save": "Save",
        "btn.cancel": "Cancel",          "btn.delete": "Delete",
        "btn.edit": "Edit",              "btn.close": "Close",
        "btn.add": "Add",                "btn.search": "Search...",
        "btn.import": "Import",          "btn.export": "Export",
        # ── Section titles ──
        "sec.modules": "Modules & Subjects",
        "sec.tasks": "Tasks",            "sec.calendar": "Calendar",
        "sec.upcoming": "Next 14 Days",
        "sec.today": "Today",
        "sec.knowledge": "Knowledge Level",
        "sec.resources": "Resources",
        "sec.notes": "📖 Study Content:",
        "sec.topics": "Topics",
        "sec.sessions": "Sessions: {n}",
        "sec.study_time": "Study Time",
        "sec.overview": "Overview",
        "sec.exams_upcoming": "Upcoming Exams",
        "sec.progress": "Progress",
        # ── Status labels ──
        "status.planned": "Planned",     "status.active": "Active",
        "status.completed": "Completed", "status.paused": "Paused",
        "status.done": "Done",           "status.open": "Open",
        # ── Priority labels ──
        "prio.critical": "Critical",     "prio.high": "High",
        "prio.medium": "Medium",         "prio.low": "Low",
        # ── Timer ──
        "timer.focus": "Focus Phase",    "timer.break": "Break",
        "timer.start": "Start",          "timer.stop": "Stop",
        "timer.reset": "Reset",          "timer.module": "Module:",
        "timer.note": "Session note (optional)...",
        # ── Dashboard ──
        "dash.modules_active": "Active Modules",
        "dash.tasks_open": "Open Tasks",
        "dash.tasks_due": "Due Today",
        "dash.study_hours": "Study Hours (7d)",
        "dash.upcoming_exams": "Upcoming Exams",
        "dash.recent_tasks": "Recent Tasks",
        "dash.no_exams": "No upcoming exams",
        "dash.no_tasks": "No open tasks",
        # ── Modules ──
        "mod.add_resource": "Add Resource",
        "mod.no_module": "No module selected",
        "mod.select_hint": "Select a module from the list on the left",
        "mod.target_hours": "Target Hours",
        "mod.studied_hours": "Studied",
        # ── Tasks ──
        "task.title": "Title",           "task.module": "Module",
        "task.priority": "Priority",     "task.status": "Status",
        "task.due": "Due",               "task.search": "Search tasks...",
        "task.new": "+ New Task",
        "task.delete_sel": "Delete selected",
        # ── Grades ──
        "grade.add": "+ Add Grade",
        "grade.all_modules": "All Modules",
        "grade.avg": "Average: {val}%",
        "grade.delete_sel": "Delete selected",
        "grade.col.module": "Module",    "grade.col.title": "Title",
        "grade.col.points": "Points",    "grade.col.max": "Max",
        "grade.col.weight": "Weight",    "grade.col.date": "Date",
        # ── Settings ──
        "set.theme": "Theme",            "set.language": "Language",
        "set.dark": "Dark",              "set.light": "Light",
        "set.lang_note": "Language change takes effect immediately.",
        # ── Calendar ──
        "cal.add_event": "+ Event",
        "cal.delete_event": "Delete",
        "cal.no_events": "No events",
        # ── Knowledge ──
        "know.level": "Knowledge Level",
        "know.not_started": "Not Started",
        "know.basics": "Basics",
        "know.familiar": "Familiar",
        "know.good": "Good",
        "know.expert": "Expert",
        # ── Exam ──
        "exam.add": "+ Exam",
        "exam.no_exams": "No exams",
        "exam.days_left": "{n} days",
        "exam.today": "Today",
        "exam.passed": "Past",
    },
    "fr": {
        # ── Nav ──
        "nav.dashboard": "Tableau de bord", "nav.focus": "Mode Focus",
        "nav.modules": "Modules",        "nav.tasks": "Tâches",
        "nav.calendar": "Calendrier",    "nav.timeline": "Planning",
        "nav.knowledge": "Connaissances","nav.timer": "Minuteur",
        "nav.exams": "Examens",          "nav.grades": "Notes",
        "nav.settings": "Paramètres",    "nav.credits": "Crédits",
        # ── Greetings ──
        "greet.morning": "Bonjour",      "greet.day": "Bonjour",
        "greet.evening": "Bonsoir",
        # ── Page titles ──
        "page.dashboard": "Tableau de bord", "page.modules": "Modules",
        "page.tasks": "Tâches",          "page.calendar": "Calendrier",
        "page.timeline": "Planning & Échéances",
        "page.knowledge": "Connaissances",
        "page.timer": "Minuteur Focus",  "page.exams": "Préparation aux Examens",
        "page.grades": "Notes",          "page.settings": "Paramètres",
        "page.credits": "Crédits",
        # ── Common buttons ──
        "btn.new": "+ Nouveau",          "btn.save": "Enregistrer",
        "btn.cancel": "Annuler",         "btn.delete": "Supprimer",
        "btn.edit": "Modifier",          "btn.close": "Fermer",
        "btn.add": "Ajouter",            "btn.search": "Rechercher...",
        "btn.import": "Importer",        "btn.export": "Exporter",
        # ── Section titles ──
        "sec.modules": "Modules & Matières",
        "sec.tasks": "Tâches",           "sec.calendar": "Calendrier",
        "sec.upcoming": "14 prochains jours",
        "sec.today": "Aujourd'hui",
        "sec.knowledge": "Niveau de connaissance",
        "sec.resources": "Ressources",
        "sec.notes": "📖 Contenu d'étude:",
        "sec.topics": "Sujets",
        "sec.sessions": "Séances: {n}",
        "sec.study_time": "Temps d'étude",
        "sec.overview": "Aperçu",
        "sec.exams_upcoming": "Examens à venir",
        "sec.progress": "Progression",
        # ── Status labels ──
        "status.planned": "Planifié",    "status.active": "Actif",
        "status.completed": "Terminé",   "status.paused": "En pause",
        "status.done": "Fait",           "status.open": "Ouvert",
        # ── Priority labels ──
        "prio.critical": "Critique",     "prio.high": "Élevée",
        "prio.medium": "Moyenne",        "prio.low": "Faible",
        # ── Timer ──
        "timer.focus": "Phase de focus", "timer.break": "Pause",
        "timer.start": "Démarrer",       "timer.stop": "Arrêter",
        "timer.reset": "Réinitialiser",  "timer.module": "Module:",
        "timer.note": "Note de séance (optionnel)...",
        # ── Dashboard ──
        "dash.modules_active": "Modules actifs",
        "dash.tasks_open": "Tâches ouvertes",
        "dash.tasks_due": "Dues aujourd'hui",
        "dash.study_hours": "Heures d'étude (7j)",
        "dash.upcoming_exams": "Examens à venir",
        "dash.recent_tasks": "Tâches récentes",
        "dash.no_exams": "Aucun examen à venir",
        "dash.no_tasks": "Aucune tâche ouverte",
        # ── Modules ──
        "mod.add_resource": "Ajouter ressource",
        "mod.no_module": "Aucun module sélectionné",
        "mod.select_hint": "Sélectionner un module dans la liste",
        "mod.target_hours": "Heures cibles",
        "mod.studied_hours": "Étudié",
        # ── Tasks ──
        "task.title": "Titre",           "task.module": "Module",
        "task.priority": "Priorité",     "task.status": "Statut",
        "task.due": "Échéance",          "task.search": "Rechercher...",
        "task.new": "+ Nouvelle tâche",
        "task.delete_sel": "Supprimer la sélection",
        # ── Grades ──
        "grade.add": "+ Ajouter note",
        "grade.all_modules": "Tous les modules",
        "grade.avg": "Moyenne: {val}%",
        "grade.delete_sel": "Supprimer la sélection",
        "grade.col.module": "Module",    "grade.col.title": "Titre",
        "grade.col.points": "Points",    "grade.col.max": "Max",
        "grade.col.weight": "Poids",     "grade.col.date": "Date",
        # ── Settings ──
        "set.theme": "Thème",            "set.language": "Langue",
        "set.dark": "Sombre",            "set.light": "Clair",
        "set.lang_note": "Le changement de langue est immédiat.",
        # ── Calendar ──
        "cal.add_event": "+ Événement",
        "cal.delete_event": "Supprimer",
        "cal.no_events": "Aucun événement",
        # ── Knowledge ──
        "know.level": "Niveau",
        "know.not_started": "Non commencé",
        "know.basics": "Bases",
        "know.familiar": "Familier",
        "know.good": "Bon",
        "know.expert": "Expert",
        # ── Exam ──
        "exam.add": "+ Examen",
        "exam.no_exams": "Aucun examen",
        "exam.days_left": "{n} jours",
        "exam.today": "Aujourd'hui",
        "exam.passed": "Passé",
    },
    "it": {
        # ── Nav ──
        "nav.dashboard": "Dashboard",    "nav.focus": "Modalità Focus",
        "nav.modules": "Moduli",         "nav.tasks": "Attività",
        "nav.calendar": "Calendario",    "nav.timeline": "Cronologia",
        "nav.knowledge": "Conoscenze",   "nav.timer": "Timer",
        "nav.exams": "Esami",            "nav.grades": "Voti",
        "nav.settings": "Impostazioni",  "nav.credits": "Crediti",
        # ── Greetings ──
        "greet.morning": "Buongiorno",   "greet.day": "Buon pomeriggio",
        "greet.evening": "Buonasera",
        # ── Page titles ──
        "page.dashboard": "Dashboard",   "page.modules": "Moduli",
        "page.tasks": "Attività",        "page.calendar": "Calendario",
        "page.timeline": "Cronologia & Scadenze",
        "page.knowledge": "Panoramica Conoscenze",
        "page.timer": "Timer Focus",     "page.exams": "Preparazione Esami",
        "page.grades": "Voti",           "page.settings": "Impostazioni",
        "page.credits": "Crediti",
        # ── Common buttons ──
        "btn.new": "+ Nuovo",            "btn.save": "Salva",
        "btn.cancel": "Annulla",         "btn.delete": "Elimina",
        "btn.edit": "Modifica",          "btn.close": "Chiudi",
        "btn.add": "Aggiungi",           "btn.search": "Cerca...",
        "btn.import": "Importa",         "btn.export": "Esporta",
        # ── Section titles ──
        "sec.modules": "Moduli & Materie",
        "sec.tasks": "Attività",         "sec.calendar": "Calendario",
        "sec.upcoming": "Prossimi 14 giorni",
        "sec.today": "Oggi",
        "sec.knowledge": "Livello di conoscenza",
        "sec.resources": "Risorse",
        "sec.notes": "📖 Contenuto di studio:",
        "sec.topics": "Argomenti",
        "sec.sessions": "Sessioni: {n}",
        "sec.study_time": "Tempo di studio",
        "sec.overview": "Panoramica",
        "sec.exams_upcoming": "Esami in arrivo",
        "sec.progress": "Progresso",
        # ── Status labels ──
        "status.planned": "Pianificato", "status.active": "Attivo",
        "status.completed": "Completato","status.paused": "In pausa",
        "status.done": "Fatto",          "status.open": "Aperto",
        # ── Priority labels ──
        "prio.critical": "Critico",      "prio.high": "Alto",
        "prio.medium": "Medio",          "prio.low": "Basso",
        # ── Timer ──
        "timer.focus": "Fase focus",     "timer.break": "Pausa",
        "timer.start": "Avvia",          "timer.stop": "Ferma",
        "timer.reset": "Reimposta",      "timer.module": "Modulo:",
        "timer.note": "Nota sessione (opzionale)...",
        # ── Dashboard ──
        "dash.modules_active": "Moduli attivi",
        "dash.tasks_open": "Attività aperte",
        "dash.tasks_due": "In scadenza oggi",
        "dash.study_hours": "Ore di studio (7gg)",
        "dash.upcoming_exams": "Esami in arrivo",
        "dash.recent_tasks": "Attività recenti",
        "dash.no_exams": "Nessun esame in arrivo",
        "dash.no_tasks": "Nessuna attività aperta",
        # ── Modules ──
        "mod.add_resource": "Aggiungi risorsa",
        "mod.no_module": "Nessun modulo selezionato",
        "mod.select_hint": "Seleziona un modulo dalla lista",
        "mod.target_hours": "Ore obiettivo",
        "mod.studied_hours": "Studiato",
        # ── Tasks ──
        "task.title": "Titolo",          "task.module": "Modulo",
        "task.priority": "Priorità",     "task.status": "Stato",
        "task.due": "Scadenza",          "task.search": "Cerca attività...",
        "task.new": "+ Nuova attività",
        "task.delete_sel": "Elimina selezionati",
        # ── Grades ──
        "grade.add": "+ Aggiungi voto",
        "grade.all_modules": "Tutti i moduli",
        "grade.avg": "Media: {val}%",
        "grade.delete_sel": "Elimina selezionati",
        "grade.col.module": "Modulo",    "grade.col.title": "Titolo",
        "grade.col.points": "Punti",     "grade.col.max": "Max",
        "grade.col.weight": "Peso",      "grade.col.date": "Data",
        # ── Settings ──
        "set.theme": "Tema",             "set.language": "Lingua",
        "set.dark": "Scuro",             "set.light": "Chiaro",
        "set.lang_note": "Il cambio lingua è immediato.",
        # ── Calendar ──
        "cal.add_event": "+ Evento",
        "cal.delete_event": "Elimina",
        "cal.no_events": "Nessun evento",
        # ── Knowledge ──
        "know.level": "Livello",
        "know.not_started": "Non iniziato",
        "know.basics": "Basi",
        "know.familiar": "Familiare",
        "know.good": "Buono",
        "know.expert": "Esperto",
        # ── Exam ──
        "exam.add": "+ Esame",
        "exam.no_exams": "Nessun esame",
        "exam.days_left": "{n} giorni",
        "exam.today": "Oggi",
        "exam.passed": "Passato",
    },
}

_LANG: str = "de"
_THEME: str = "light"
_ACCENT_PRESET: str = "violet"

# ── Accent-colour presets ──────────────────────────────────────────────────
# Each entry: base, d1-d4 (darker), l1-l5 (lighter).
ACCENT_PRESETS: dict = {
    "violet": {
        "base": "#7C3AED", "d1": "#6D28D9", "d2": "#5B21B6", "d3": "#4C1D95",
        "d4": "#2D1B69", "l1": "#A78BFA", "l2": "#C4B5FD", "l3": "#DDD6FE",
        "l4": "#EDE9FE", "l5": "#F3E8FF",
    },
    "ocean": {
        "base": "#2563EB", "d1": "#1D4ED8", "d2": "#1E40AF", "d3": "#1E3A8A",
        "d4": "#1E2D5A", "l1": "#60A5FA", "l2": "#93C5FD", "l3": "#BFDBFE",
        "l4": "#DBEAFE", "l5": "#EFF6FF",
    },
    "forest": {
        "base": "#059669", "d1": "#047857", "d2": "#065F46", "d3": "#064E3B",
        "d4": "#022C22", "l1": "#34D399", "l2": "#6EE7B7", "l3": "#A7F3D0",
        "l4": "#D1FAE5", "l5": "#ECFDF5",
    },
    "sunset": {
        "base": "#EA580C", "d1": "#C2410C", "d2": "#9A3412", "d3": "#7C2D12",
        "d4": "#431407", "l1": "#FB923C", "l2": "#FDBA74", "l3": "#FED7AA",
        "l4": "#FFEDD5", "l5": "#FFF7ED",
    },
    "rose": {
        "base": "#DB2777", "d1": "#BE185D", "d2": "#9D174D", "d3": "#831843",
        "d4": "#4A0E28", "l1": "#F472B6", "l2": "#F9A8D4", "l3": "#FBCFE8",
        "l4": "#FCE7F3", "l5": "#FDF2F8",
    },
    "slate": {
        "base": "#475569", "d1": "#334155", "d2": "#1E293B", "d3": "#0F172A",
        "d4": "#0A0F1A", "l1": "#94A3B8", "l2": "#CBD5E1", "l3": "#E2E8F0",
        "l4": "#F1F5F9", "l5": "#F8FAFC",
    },
}

ACCENT_PRESET_LABELS: list = [
    ("🟣  Violet  (Standard)", "violet"),
    ("🔵  Ocean Blue",         "ocean"),
    ("🟢  Forest Green",       "forest"),
    ("🟠  Sunset Orange",      "sunset"),
    ("🌸  Rose Pink",          "rose"),
    ("⬛  Slate Grey",         "slate"),
]


def set_lang(lang: str) -> None:
    global _LANG
    _LANG = lang if lang in TRANSLATIONS else "de"


def set_theme(t: str) -> None:
    global _THEME
    _THEME = t


def set_accent(preset: str) -> None:
    global _ACCENT_PRESET
    if preset in ACCENT_PRESETS:
        _ACCENT_PRESET = preset


def get_accent_color() -> str:
    """Return the current primary accent hex colour."""
    return ACCENT_PRESETS.get(_ACCENT_PRESET, ACCENT_PRESETS["violet"])["base"]


def _tc(light: str, dark: str) -> str:
    """Return the light or dark colour string based on the active theme."""
    return dark if _THEME == "dark" else light


def _hex_rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB + float alpha (0-1) → proper rgba() string for QSS.

    Qt interprets 8-digit hex as #AARRGGBB (not #RRGGBBAA), so we must use
    rgba() to get semi-transparent tinted backgrounds.
    """
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    else:
        r, g, b = 128, 128, 128   # fallback
    return f"rgba({r},{g},{b},{alpha:.2f})"


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
* { font-family: 'Inter', 'Segoe UI', 'Ubuntu', Arial, sans-serif, 'Noto Color Emoji', 'Apple Color Emoji', 'Segoe UI Emoji'; font-size: 13px; }
QWidget { background: transparent; color: #1A1523; }
QMainWindow { background: #F6F5FA; }
QDialog { background: #F6F5FA; border-radius: 16px; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget { background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* ── Sidebar ─────────────────────────────── */
QWidget#Sidebar {
    background: #FFFFFF;
    border-right: 1px solid #EAE8F2;
}
QLabel#AppTitle {
    font-size: 14px; font-weight: 800;
    color: #1A1523; letter-spacing: -0.3px;
    padding: 2px 6px;
}
QLabel#AppVersion { font-size: 10px; color: #9B95B5; padding: 0 6px 2px 6px; letter-spacing: 0.3px; }
QLabel#NavSectionLabel {
    font-size: 10px; font-weight: 700; color: #A8A2BE;
    letter-spacing: 1.5px; padding: 0px 14px;
}
QPushButton#NavBtn {
    background: transparent; border: none; border-radius: 9px;
    text-align: left; padding: 10px 14px;
    font-size: 13px; color: #6E6882; font-weight: 500;
}
QPushButton#NavBtn:hover { background: #F3F1FA; color: #1A1523; }
QPushButton#NavBtn[active="true"] {
    background: #EDE9FE; color: #6D28D9; font-weight: 700;
    border-left: 3px solid #7C3AED; padding-left: 11px;
}
QPushButton#QuickAddBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #A78BFA);
    color: white; border: none; border-radius: 10px;
    padding: 10px 14px; font-size: 13px; font-weight: 700; text-align: left;
}
QPushButton#QuickAddBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6D28D9, stop:1 #8B5CF6);
}
QPushButton#QuickAddBtn:pressed {
    background: #5B21B6;
}

/* ── Page background ─────────────────────── */
QWidget#PageContent { background: #F6F5FA; }

/* ── Cards ───────────────────────────────── */
QFrame#Card {
    background: #FFFFFF;
    border-radius: 16px;
    border: 1px solid #EAE8F2;
}
QFrame#QuoteCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #F0EAFF, stop:0.55 #FAF6FF, stop:1 #FEF3FF);
    border-radius: 16px;
    border: 1px solid #DDD6FE;
}
QFrame#FocusCard {
    background: #FFFFFF;
    border-radius: 16px;
    border: 1.5px solid #DDD6FE;
}
QLabel#CardTitle { font-size: 12px; color: #8C87A3; letter-spacing: 0.3px; font-weight: 600; }
QLabel#CardValue { font-size: 30px; font-weight: 800; letter-spacing: -1px; }
QLabel#CardUnit { font-size: 12px; color: #8C87A3; margin-bottom: 4px; }

/* ── Typography ──────────────────────────── */
QLabel#PageTitle { font-size: 22px; font-weight: 800; color: #1A1523; letter-spacing: -0.5px; }
QLabel#SectionTitle { font-size: 12px; font-weight: 700; color: #6D28D9; letter-spacing: 0.8px; text-transform: uppercase; }
QLabel { color: #1A1523; }

/* ── Buttons ─────────────────────────────── */
QPushButton#PrimaryBtn {
    background: #7C3AED; color: white; border: none;
    border-radius: 10px; padding: 9px 22px; font-size: 13px; font-weight: 700;
}
QPushButton#PrimaryBtn:hover { background: #6D28D9; }
QPushButton#PrimaryBtn:pressed { background: #5B21B6; }
QPushButton#DangerBtn {
    background: #EF4444; color: white; border: none;
    border-radius: 10px; padding: 9px 22px; font-size: 13px; font-weight: 600;
}
QPushButton#DangerBtn:hover { background: #DC2626; }
QPushButton#SecondaryBtn {
    background: #F0EAFF; color: #7C3AED; border: 1.5px solid #DDD6FE;
    border-radius: 10px; padding: 8px 18px; font-size: 13px; font-weight: 600;
}
QPushButton#SecondaryBtn:hover { background: #EDE9FE; border-color: #C4B5FD; }
QPushButton#CoachBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #7C3AED, stop:1 #A78BFA);
    color: white; border: none; border-radius: 10px;
    padding: 9px 16px; font-size: 13px; font-weight: 700;
}
QPushButton#CoachBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6D28D9, stop:1 #7C3AED);
}
QComboBox#SemesterFilter {
    background: #F0EAFF; border: 1.5px solid #DDD6FE; border-radius: 12px;
    padding: 5px 12px; font-size: 12px; color: #6D28D9; font-weight: 700;
    selection-background-color: #7C3AED;
}
QComboBox#SemesterFilter::drop-down { border: none; width: 20px; }
QComboBox#SemesterFilter:hover { border-color: #7C3AED; background: #EDE9FE; }

/* ── Inputs ──────────────────────────────── */
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background: #FFFFFF; border: 1.5px solid #E2DEF0; border-radius: 10px;
    padding: 8px 12px; font-size: 13px; color: #1A1523; selection-background-color: #7C3AED;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus {
    border-color: #7C3AED; background: #FDFBFF;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox::down-arrow { width: 10px; height: 10px; }
QComboBox QAbstractItemView {
    background: #FFFFFF; color: #1A1523;
    selection-background-color: #7C3AED; selection-color: #FFFFFF;
    border: 1px solid #E2DEF0; border-radius: 10px;
}
QComboBox QAbstractItemView::item { min-height: 30px; padding: 5px 12px; }
QComboBox QAbstractItemView::item:selected { background: #7C3AED; color: #FFFFFF; }
QComboBox QAbstractItemView::item:hover { background: #F0EAFF; }

/* ── Checkboxes & Radiobuttons ───────────── */
QCheckBox { color: #1A1523; spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; border-radius: 5px;
    border: 1.5px solid #D4D0E3; background: #FFFFFF; }
QCheckBox::indicator:checked { background: #7C3AED; border-color: #7C3AED; }
QCheckBox::indicator:hover { border-color: #7C3AED; }
QRadioButton { color: #1A1523; spacing: 8px; }
QRadioButton::indicator { width: 17px; height: 17px; border-radius: 9px;
    border: 1.5px solid #D4D0E3; background: #FFFFFF; }
QRadioButton::indicator:checked { background: #7C3AED; border-color: #7C3AED; }

/* ── Scrollbar ───────────────────────────── */
QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
QScrollBar::handle:vertical { background: #E2DEF0; border-radius: 3px; min-height: 40px; }
QScrollBar::handle:vertical:hover { background: #C4B5FD; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 6px; }
QScrollBar::handle:horizontal { background: #E2DEF0; border-radius: 3px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Progress ────────────────────────────── */
QProgressBar { background: #EDE9FE; border-radius: 5px; border: none; max-height: 6px; text-align: center; }
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #A78BFA);
    border-radius: 5px;
}

/* ── Table ───────────────────────────────── */
QTableWidget {
    background: #FFFFFF; border: 1px solid #EAE8F2;
    border-radius: 14px; gridline-color: #F3F1FA; outline: none;
}
QTableWidget::item { padding: 10px 8px; color: #1A1523; border: none; }
QTableWidget::item:selected { background: #F0EAFF; color: #6D28D9; }
QTableWidget::item:hover { background: #FAF8FF; }
QHeaderView::section {
    background: #FAF8FF; border: none; border-bottom: 1px solid #EAE8F2;
    padding: 10px 8px; font-weight: 700; color: #8C87A3; font-size: 12px; letter-spacing: 0.3px;
}
QHeaderView { border: none; }

/* ── List ────────────────────────────────── */
QListWidget { border: 1px solid #EAE8F2; border-radius: 14px; background: #FFFFFF; outline: none; }
QListWidget::item { padding: 8px 12px; border-radius: 8px; }
QListWidget::item:selected { background: #F0EAFF; color: #6D28D9; }
QListWidget::item:hover { background: #FAF8FF; }

/* ── GroupBox ────────────────────────────── */
QGroupBox {
    border: 1.5px solid #EAE8F2; border-radius: 14px;
    margin-top: 14px; padding-top: 8px; font-weight: 700; color: #6D28D9; font-size: 12px;
    background: transparent;
}
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; background: transparent; color: #6D28D9; }

/* ── Calendar ────────────────────────────── */
QCalendarWidget QAbstractItemView { background: #FFFFFF; selection-background-color: #7C3AED; border-radius: 8px; }
QCalendarWidget QWidget { background: #FFFFFF; border-radius: 8px; }

/* ── Dialog ──────────────────────────────── */
QDialog { background: #F6F5FA; border-radius: 16px; }
QDialog QFrame { background: #F6F5FA; }
QDialogButtonBox QPushButton {
    background: #7C3AED; color: white; border: none;
    border-radius: 10px; padding: 8px 22px; min-width: 90px; font-weight: 700;
}
QDialogButtonBox QPushButton:hover { background: #6D28D9; }
QDialogButtonBox QPushButton[text="Cancel"],
QDialogButtonBox QPushButton[text="Abbrechen"] {
    background: #F0EAFF; color: #7C3AED; border: 1.5px solid #DDD6FE;
}
QDialogButtonBox QPushButton[text="Cancel"]:hover,
QDialogButtonBox QPushButton[text="Abbrechen"]:hover { background: #EDE9FE; }

/* ── Panel / Splitter ────────────────────── */
QWidget#ModuleLeftPanel { background: #FFFFFF; border-right: 1px solid #EAE8F2; }
QSplitter::handle { background: #EAE8F2; width: 1px; }
QTextEdit#NotesArea { background: #FDFBFF; border: 1px solid #EAE8F2; border-radius: 10px; }
QFrame#ResourceRow { background: #FAF8FF; border: 1px solid #EAE8F2; border-radius: 10px; }

/* ── Combo Popup Overlay ─────────────────── */
QFrame#ComboPopupOverlay {
    background: #FFFFFF; border: 1.5px solid #E2DEF0; border-radius: 12px;
}
QFrame#ComboPopupOverlay QListWidget {
    background: transparent; border: none; border-radius: 8px; outline: none;
}
QFrame#ComboPopupOverlay QListWidget::item { padding: 7px 14px; border-radius: 7px; color: #1A1523; }
QFrame#ComboPopupOverlay QListWidget::item:selected { background: #7C3AED; color: #FFFFFF; }
QFrame#ComboPopupOverlay QListWidget::item:hover { background: #F0EAFF; }

/* ── Tab Widget ──────────────────────────── */
QTabWidget::pane { border: 1px solid #EAE8F2; border-radius: 12px; background: #FFFFFF; top: -1px; }
QTabBar::tab {
    background: transparent; border: none; padding: 8px 18px;
    font-size: 13px; font-weight: 600; color: #ABA6C2; border-radius: 8px 8px 0 0;
}
QTabBar::tab:selected { color: #7C3AED; border-bottom: 2px solid #7C3AED; background: #FAFAFF; }
QTabBar::tab:hover { color: #6D28D9; background: #F6F4FF; }

/* ── Dock Widget (Sidebar) ──────────────── */
QDockWidget#SidebarDock { border: none; }
QDockWidget#SidebarDock::title { background: transparent; padding: 0; }
"""

DARK_QSS = """
* { font-family: 'Inter', 'Segoe UI', 'Ubuntu', Arial, sans-serif, 'Noto Color Emoji', 'Apple Color Emoji', 'Segoe UI Emoji'; font-size: 13px; }
QWidget { background: transparent; color: #EAE6F4; }
QMainWindow { background: #0D0B12; }
QDialog { background: #0D0B12; border-radius: 16px; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget { background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* ── Sidebar ─────────────────────────────── */
QWidget#Sidebar {
    background: #111019;
    border-right: 1px solid #1E1B2C;
}
QLabel#AppTitle { font-size: 14px; font-weight: 800; color: #EAE6F4; letter-spacing: -0.3px; padding: 2px 6px; }
QLabel#AppVersion { font-size: 10px; color: #6B657E; padding: 0 6px 2px 6px; letter-spacing: 0.3px; }
QLabel#NavSectionLabel {
    font-size: 10px; font-weight: 700; color: #5E5876;
    letter-spacing: 1.5px; padding: 0px 14px;
}
QPushButton#NavBtn {
    background: transparent; border: none; border-radius: 9px;
    text-align: left; padding: 10px 14px; font-size: 13px; color: #7A7492; font-weight: 500;
}
QPushButton#NavBtn:hover { background: #1A1728; color: #EAE6F4; }
QPushButton#NavBtn[active="true"] {
    background: #281E48; color: #C4B5FD; font-weight: 700;
    border-left: 3px solid #7C3AED; padding-left: 11px;
}
QPushButton#QuickAddBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6D28D9, stop:1 #8B5CF6);
    color: white; border: none; border-radius: 10px;
    padding: 10px 14px; font-size: 13px; font-weight: 700; text-align: left;
}
QPushButton#QuickAddBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5B21B6, stop:1 #7C3AED);
}
QPushButton#QuickAddBtn:pressed { background: #4C1D95; }

/* ── Page background ─────────────────────── */
QWidget#PageContent { background: #0D0B12; }

/* ── Cards ───────────────────────────────── */
QFrame#Card { background: #15121E; border-radius: 16px; border: 1px solid #1E1B2C; }
QFrame#QuoteCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1A1535, stop:0.55 #15121E, stop:1 #1A1030);
    border-radius: 16px; border: 1px solid #322860;
}
QFrame#FocusCard { background: #15121E; border-radius: 16px; border: 1.5px solid #322860; }
QLabel#CardTitle { font-size: 12px; color: #7A7492; letter-spacing: 0.3px; font-weight: 600; }
QLabel#CardValue { font-size: 30px; font-weight: 800; letter-spacing: -1px; color: #EAE6F4; }
QLabel#CardUnit { font-size: 12px; color: #7A7492; margin-bottom: 4px; }

/* ── Typography ──────────────────────────── */
QLabel#PageTitle { font-size: 22px; font-weight: 800; color: #EAE6F4; letter-spacing: -0.5px; }
QLabel#SectionTitle { font-size: 12px; font-weight: 700; color: #A78BFA; letter-spacing: 0.8px; }
QLabel { color: #EAE6F4; background: transparent; }

/* ── Buttons ─────────────────────────────── */
QPushButton { color: #EAE6F4; background: #1D1A2A; border: 1px solid #2D2040; border-radius: 8px; padding: 6px 14px; }
QPushButton:hover { background: #251E3A; border-color: #4C3D78; }
QPushButton#PrimaryBtn {
    background: #7C3AED; color: #FFFFFF; border: none;
    border-radius: 10px; padding: 9px 22px; font-size: 13px; font-weight: 700;
}
QPushButton#PrimaryBtn:hover { background: #6D28D9; }
QPushButton#PrimaryBtn:pressed { background: #5B21B6; }
QPushButton#DangerBtn {
    background: #DC2626; color: #FFFFFF; border: none;
    border-radius: 10px; padding: 9px 22px; font-size: 13px; font-weight: 600;
}
QPushButton#DangerBtn:hover { background: #B91C1C; }
QPushButton#SecondaryBtn {
    background: #1D1A2A; color: #C4B5FD; border: 1px solid #2D2040;
    border-radius: 10px; padding: 8px 18px; font-size: 13px; font-weight: 600;
}
QPushButton#SecondaryBtn:hover { background: #251E3A; border-color: #4C3D78; }
QPushButton#CoachBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6D28D9, stop:1 #8B5CF6);
    color: white; border: none; border-radius: 10px;
    padding: 9px 16px; font-size: 13px; font-weight: 700;
}
QPushButton#CoachBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5B21B6, stop:1 #7C3AED);
}
QToolButton { background: transparent; border: none; color: #EAE6F4; }
QToolButton:hover { background: #1D1A2A; border-radius: 6px; }
QComboBox#SemesterFilter {
    background: #1D1A2A; border: 1.5px solid #2D2040; border-radius: 12px;
    padding: 5px 12px; font-size: 12px; color: #C4B5FD; font-weight: 700;
    selection-background-color: #7C3AED;
}
QComboBox#SemesterFilter::drop-down { border: none; width: 20px; }
QComboBox#SemesterFilter:hover { border-color: #7C3AED; background: #251E3A; }

/* ── Inputs ──────────────────────────────── */
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background: #15121E; border: 1.5px solid #232035; border-radius: 10px;
    padding: 8px 12px; font-size: 13px; color: #EAE6F4; selection-background-color: #7C3AED;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus { border-color: #7C3AED; background: #1D1A2A; }
QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled { color: #5E5876; background: #111019; border-color: #1E1B2C; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #15121E; color: #EAE6F4;
    selection-background-color: #7C3AED; selection-color: #FFFFFF;
    border: 1px solid #232035; border-radius: 10px;
}
QComboBox QAbstractItemView::item { min-height: 30px; padding: 5px 12px; color: #EAE6F4; }
QComboBox QAbstractItemView::item:selected { background: #7C3AED; color: #FFFFFF; }
QComboBox QAbstractItemView::item:hover { background: #1D1A2A; color: #EAE6F4; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { background: #1D1A2A; border: none; width: 16px; }
QSpinBox::up-arrow, QSpinBox::down-arrow,
QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow { width: 8px; height: 8px; }
QDateEdit::drop-down { border: none; width: 20px; background: #1D1A2A; }

/* ── Checkboxes & Radiobuttons ───────────── */
QCheckBox { color: #EAE6F4; spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 17px; height: 17px; border-radius: 5px;
    border: 1.5px solid #2D2040; background: #15121E; }
QCheckBox::indicator:checked { background: #7C3AED; border-color: #7C3AED; }
QCheckBox::indicator:hover { border-color: #8B5CF6; }
QRadioButton { color: #EAE6F4; spacing: 8px; background: transparent; }
QRadioButton::indicator { width: 17px; height: 17px; border-radius: 9px;
    border: 1.5px solid #2D2040; background: #15121E; }
QRadioButton::indicator:checked { background: #7C3AED; border-color: #7C3AED; }

/* ── Scrollbar ───────────────────────────── */
QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
QScrollBar::handle:vertical { background: #232035; border-radius: 3px; min-height: 40px; }
QScrollBar::handle:vertical:hover { background: #3D3060; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 6px; }
QScrollBar::handle:horizontal { background: #232035; border-radius: 3px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Progress ────────────────────────────── */
QProgressBar { background: #1D1A2A; border-radius: 5px; border: none; max-height: 6px; text-align: center; color: #EAE6F4; }
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #A78BFA);
    border-radius: 5px;
}

/* ── Table ───────────────────────────────── */
QTableWidget { background: #15121E; border: 1px solid #1E1B2C; border-radius: 14px; gridline-color: #1A1728; outline: none; color: #EAE6F4; }
QTableWidget::item { padding: 10px 8px; color: #EAE6F4; border: none; background: transparent; }
QTableWidget::item:selected { background: #281E48; color: #C4B5FD; }
QTableWidget::item:hover { background: #1A1728; }
QHeaderView { border: none; background: transparent; }
QHeaderView::section { background: #111019; border: none; border-bottom: 1px solid #1E1B2C; padding: 10px 8px; font-weight: 700; color: #7A7492; font-size: 12px; letter-spacing: 0.3px; }

/* ── List ────────────────────────────────── */
QListWidget { border: 1px solid #1E1B2C; border-radius: 14px; background: #15121E; outline: none; color: #EAE6F4; }
QListWidget::item { padding: 8px 12px; border-radius: 8px; color: #EAE6F4; background: transparent; }
QListWidget::item:selected { background: #281E48; color: #C4B5FD; }
QListWidget::item:hover { background: #1A1728; }

/* ── GroupBox ────────────────────────────── */
QGroupBox {
    border: 1.5px solid #1E1B2C; border-radius: 14px;
    margin-top: 14px; padding-top: 8px; font-weight: 700; color: #A78BFA; font-size: 12px;
    background: transparent;
}
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; background: transparent; color: #A78BFA; }

/* ── Calendar ────────────────────────────── */
QCalendarWidget { background: #15121E; color: #EAE6F4; }
QCalendarWidget QAbstractItemView { background: #15121E; selection-background-color: #7C3AED; color: #EAE6F4; border-radius: 8px; }
QCalendarWidget QWidget { background: #15121E; color: #EAE6F4; }
QCalendarWidget QToolButton { background: transparent; color: #EAE6F4; border: none; }
QCalendarWidget QToolButton:hover { background: #1D1A2A; }
QCalendarWidget QSpinBox { background: #15121E; color: #EAE6F4; border: 1px solid #232035; }
QCalendarWidget QMenu { background: #15121E; color: #EAE6F4; border: 1px solid #232035; }

/* ── Dialog content ──────────────────────── */
QDialog QWidget { background: transparent; color: #EAE6F4; }
QDialog QFrame { background: transparent; }
QDialog QScrollArea { background: transparent; border: none; }
QDialog QGroupBox { border-color: #1E1B2C; }
QDialogButtonBox QPushButton {
    background: #7C3AED; color: #FFFFFF; border: none;
    border-radius: 10px; padding: 8px 22px; min-width: 90px; font-weight: 700;
}
QDialogButtonBox QPushButton:hover { background: #6D28D9; }
QDialogButtonBox QPushButton[text="Cancel"],
QDialogButtonBox QPushButton[text="Abbrechen"] {
    background: #1D1A2A; color: #C4B5FD; border: 1px solid #2D2040;
}
QDialogButtonBox QPushButton[text="Cancel"]:hover,
QDialogButtonBox QPushButton[text="Abbrechen"]:hover { background: #251E3A; }

/* ── Panel / Splitter ────────────────────── */
QWidget#ModuleLeftPanel { background: #15121E; border-right: 1px solid #1E1B2C; }
QSplitter::handle { background: #1E1B2C; width: 1px; }
QTextEdit#NotesArea { background: #15121E; border: 1px solid #1E1B2C; border-radius: 10px; color: #EAE6F4; }
QFrame#ResourceRow { background: #1A1728; border: 1px solid #1E1B2C; border-radius: 10px; }

/* ── Message Box ─────────────────────────── */
QMessageBox { background: #0D0B12; }
QMessageBox QLabel { color: #EAE6F4; background: transparent; }

/* ── Combo Popup Overlay ─────────────────── */
QFrame#ComboPopupOverlay {
    background: #15121E; border: 1.5px solid #232035; border-radius: 12px;
}
QFrame#ComboPopupOverlay QListWidget {
    background: transparent; border: none; border-radius: 8px; outline: none;
}
QFrame#ComboPopupOverlay QListWidget::item { padding: 7px 14px; border-radius: 7px; color: #EAE6F4; }
QFrame#ComboPopupOverlay QListWidget::item:selected { background: #7C3AED; color: #FFFFFF; }
QFrame#ComboPopupOverlay QListWidget::item:hover { background: #1D1A2A; }

/* ── Tab Widget ──────────────────────────── */
QTabWidget::pane { border: 1px solid #1E1B2C; border-radius: 12px; background: #15121E; top: -1px; }
QTabBar { background: transparent; }
QTabBar::tab {
    background: transparent; border: none; padding: 8px 18px;
    font-size: 13px; font-weight: 600; color: #7A7492; border-radius: 8px 8px 0 0;
}
QTabBar::tab:selected { color: #A78BFA; border-bottom: 2px solid #8B5CF6; background: #1D1A2A; }
QTabBar::tab:hover { color: #C4B5FD; background: #1A1728; }

/* ── Dock Widget (Sidebar) ──────────────── */
QDockWidget#SidebarDock { border: none; background: transparent; }
QDockWidget#SidebarDock::title { background: transparent; padding: 0; }

/* ── Misc ─────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] { color: #1E1B2C; background: transparent; }
"""


def _accent_replace_pairs(old_preset: dict, new_preset: dict) -> list:
    """Build ordered (old, new) hex substitution pairs: most-specific first."""
    return [
        (old_preset["l5"], new_preset["l5"]),
        (old_preset["l4"], new_preset["l4"]),
        (old_preset["l3"], new_preset["l3"]),
        (old_preset["l2"], new_preset["l2"]),
        (old_preset["l1"], new_preset["l1"]),
        (old_preset["d4"], new_preset["d4"]),
        (old_preset["d3"], new_preset["d3"]),
        (old_preset["d2"], new_preset["d2"]),
        (old_preset["d1"], new_preset["d1"]),
        (old_preset["base"], new_preset["base"]),
    ]


def restyle_widgets_accent(root: "QWidget", old_preset: dict, new_preset: dict) -> None:
    """Walk every widget under *root* and swap old accent hex values for new ones
    in their individual inline stylesheets.  This is needed because hundreds of
    widgets use setStyleSheet() with hard-coded violet values that are not covered
    by QApplication.setStyleSheet()."""
    if old_preset is new_preset:          # same object → no-op
        return
    pairs = _accent_replace_pairs(old_preset, new_preset)
    for widget in root.findChildren(QWidget):
        ss = widget.styleSheet()
        if not ss:
            continue
        new_ss = ss
        for old, new in pairs:
            if old in new_ss:
                new_ss = new_ss.replace(old, new)
            old_l = old.lower()
            if old_l in new_ss:
                new_ss = new_ss.replace(old_l, new)
        if new_ss != ss:
            widget.setStyleSheet(new_ss)


def get_qss(theme: str) -> str:
    """Return QSS with the currently selected accent palette applied."""
    base_qss = DARK_QSS if theme == "dark" else LIGHT_QSS
    violet  = ACCENT_PRESETS["violet"]
    chosen  = ACCENT_PRESETS.get(_ACCENT_PRESET, violet)
    if chosen is violet:
        return base_qss
    result = base_qss
    for old, new in _accent_replace_pairs(violet, chosen):
        result = result.replace(old, new)
        result = result.replace(old.lower(), new)
    return result


# ── Reusable Widgets ───────────────────────────────────────────────────────

class StatCard(QFrame):
    """Modern metric card with a gradient accent bar and large bold value."""
    clicked = Signal()

    def __init__(self, title: str, value: str, unit: str = "", color: str = "#7C3AED", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._color = color
        self._clickable = False
        self.setMinimumHeight(108)
        self.setMaximumHeight(132)
        self.setMinimumWidth(118)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(3)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("CardTitle")
        lay.addWidget(self.title_lbl)

        lay.addStretch()

        row = QHBoxLayout()
        row.setSpacing(5)
        row.setContentsMargins(0, 0, 0, 0)
        self.val_lbl = QLabel(value)
        self.val_lbl.setStyleSheet(
            f"color:{color}; font-size:28px; font-weight:800; letter-spacing:-1px;"
        )
        row.addWidget(self.val_lbl)
        if unit:
            u = QLabel(unit)
            u.setObjectName("CardUnit")
            u.setAlignment(Qt.AlignBottom)
            u.setStyleSheet("padding-bottom:4px;")
            row.addWidget(u)
        row.addStretch()
        lay.addLayout(row)

        # Slim gradient accent at bottom-left
        accent = QWidget()
        accent.setFixedHeight(3)
        accent.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {color}, stop:0.6 {color}88, stop:1 transparent);"
            f"border-radius:2px; margin-top:4px;"
        )
        lay.addWidget(accent)

    def make_clickable(self) -> "StatCard":
        """Enable pointer cursor + emits clicked() on left click. Returns self."""
        self._clickable = True
        self.setCursor(Qt.PointingHandCursor)
        return self

    def mousePressEvent(self, event):
        if self._clickable and event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

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

        pen = QPen(QColor(_tc("#E8EBF2", "#313244")), 12, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect_f, 0, 360 * 16)

        frac = self._remaining / self._total if self._total > 0 else 0
        span = int(frac * 360 * 16)
        pen2 = QPen(QColor(self._color), 12, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen2)
        p.drawArc(rect_f, 90 * 16, span)

        p.setPen(QPen(QColor(_tc("#1A1A2E", "#E2D9F3"))))
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
    # Transparent viewport so the dark/light page background shows through
    sa.viewport().setAutoFillBackground(False)
    sa.setWidget(widget)
    return sa


def separator() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(_tc("color: #EAE8F2;", "color: #1E1B2C;"))
    return f


# ── Dialogs ────────────────────────────────────────────────────────────────

class ModuleDialog(QDialog):
    def __init__(self, repo: SqliteRepo, module_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
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
        self.module_type = QComboBox()
        self.module_type.addItems(["pflicht", "wahl", "vertiefung"])

        # Prüfungsdatum: optional via checkbox
        self._exam_date_check = QCheckBox("Prüfungsdatum festlegen")
        self._exam_date_check.setChecked(False)
        self.exam_date = QDateEdit()
        self.exam_date.setCalendarPopup(True)
        self.exam_date.setDate(QDate.currentDate())
        self.exam_date.setEnabled(False)
        self._exam_date_check.toggled.connect(self.exam_date.setEnabled)

        self.weighting = QDoubleSpinBox()
        self.weighting.setRange(0.1, 10.0)
        self.weighting.setSingleStep(0.1)
        self.weighting.setValue(1.0)

        # Target grade
        self.target_grade = QDoubleSpinBox()
        self.target_grade.setRange(0.0, 6.0)
        self.target_grade.setSingleStep(0.1)
        self.target_grade.setDecimals(1)
        self.target_grade.setSpecialValueText("— kein Ziel —")
        self.target_grade.setValue(0.0)  # 0.0 = no target (shown as "— kein Ziel —")

        # ── Pflichtfelder ────────────────────────────────────────────────
        form.addRow("Name *:", self.name)
        form.addRow("Semester *:", self.semester)
        form.addRow("ECTS *:", self.ects)
        form.addRow("Modultyp *:", self.module_type)

        # ── Optionale Felder ────────────────────────────────────────────
        form.addRow("Gewichtung:", self.weighting)
        form.addRow("Status:", self.status)

        # Exam date row: checkbox + date picker side by side
        exam_row = QHBoxLayout()
        exam_row.setSpacing(6)
        exam_row.addWidget(self._exam_date_check)
        exam_row.addWidget(self.exam_date)
        exam_row.addStretch()
        form.addRow("Prüfung:", exam_row)

        form.addRow("Dozent:", self.lecturer)
        form.addRow("Zielnote:", self.target_grade)
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
                self._exam_date_check.setChecked(True)
            except Exception:
                pass
        self.weighting.setValue(float(m["weighting"]))
        mt = m["module_type"] if "module_type" in m.keys() else "pflicht"
        mt_idx = self.module_type.findText(mt or "pflicht")
        if mt_idx >= 0:
            self.module_type.setCurrentIndex(mt_idx)
        tg = (m["target_grade"] if "target_grade" in m.keys() and m["target_grade"] is not None else 0.0)
        self.target_grade.setValue(float(tg))

    def _accept(self):
        name = self.name.text().strip()
        sem = self.semester.text().strip()
        if not name or not sem:
            QMessageBox.warning(self, "Fehler",
                "Name, Semester, ECTS und Modultyp sind Pflichtfelder.")
            return
        if self.ects.value() <= 0:
            QMessageBox.warning(self, "Fehler",
                "Bitte gib eine gültige ECTS-Anzahl an (> 0).")
            return

        # Free-plan limit: max 2 Module pro Semester
        if not self.module_id:  # only for new modules, not edits
            from semetra.infra.license import LicenseManager
            lm = LicenseManager(self.repo)
            if not lm.is_pro():
                all_mods = self.repo.list_modules("all")
                sem_count = sum(1 for m in all_mods if m["semester"] == sem)
                if sem_count >= 2:
                    dlg = ProFeatureDialog(
                        "Mehr als 2 Module pro Semester",
                        self.repo, parent=self
                    )
                    if dlg.exec() != QDialog.Accepted:
                        return
                    # Re-check after potential upgrade
                    lm._cached = None
                    if not lm.is_pro():
                        return

        exam_str = (self.exam_date.date().toString("yyyy-MM-dd")
                    if self._exam_date_check.isChecked() else "")
        tg_val = self.target_grade.value()
        data = {
            "name": name, "semester": sem,
            "module_type": self.module_type.currentText(),
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
            "target_grade": tg_val if tg_val > 0 else None,
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
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
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
    """Dialog zum Erfassen/Bearbeiten einer Prüfungsleistung.

    Zwei Eingabemodi (per Toggle wählbar):
    • Punkte-Modus  — Eingabe: Erreichte Punkte + Max. Punkte → Note wird live berechnet
    • Direkte Note  — Eingabe: Note 1.0–6.0 direkt (in 0.5-Schritten), z. B. aus Zeugnis
    """

    def __init__(self, repo: SqliteRepo, grade_id: Optional[int] = None,
                 default_module_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.grade_id = grade_id
        self._mode = "points"   # 'points' | 'direct'
        self.setWindowTitle("Note bearbeiten" if grade_id else "Note hinzufügen")
        self.setMinimumWidth(420)
        self._build()
        if grade_id:
            self._load(grade_id)
        elif default_module_id:
            self._set_module(default_module_id)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # ── Mode toggle ───────────────────────────────────────────────────────
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Eingabe-Modus:"))
        self._btn_points = QPushButton("📊 Punkte")
        self._btn_points.setCheckable(True)
        self._btn_points.setChecked(True)
        self._btn_points.clicked.connect(lambda: self._set_mode("points"))
        self._btn_direct = QPushButton("🎓 Direkte Note (1–6)")
        self._btn_direct.setCheckable(True)
        self._btn_direct.setChecked(False)
        self._btn_direct.clicked.connect(lambda: self._set_mode("direct"))
        mode_row.addWidget(self._btn_points)
        mode_row.addWidget(self._btn_direct)
        mode_row.addStretch()
        lay.addLayout(mode_row)

        # ── Form ──────────────────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(10)

        self.title = QLineEdit()
        form.addRow("Titel *:", self.title)

        self.module_cb = QComboBox()
        for m in self.repo.list_modules("all"):
            self.module_cb.addItem(m["name"], m["id"])
        form.addRow("Modul:", self.module_cb)

        # Points mode widgets
        self.grade_pts = QDoubleSpinBox()
        self.grade_pts.setRange(0, 10000)
        self.grade_pts.setDecimals(2)
        self.grade_pts.setSuffix(" Pkt")
        self.grade_pts.valueChanged.connect(self._update_preview)

        self.max_grade_pts = QDoubleSpinBox()
        self.max_grade_pts.setRange(1, 10000)
        self.max_grade_pts.setDecimals(2)
        self.max_grade_pts.setValue(100)
        self.max_grade_pts.setSuffix(" Pkt")
        self.max_grade_pts.valueChanged.connect(self._update_preview)

        self._row_pts  = form.addRow("Erreichte Punkte:", self.grade_pts)
        self._row_max  = form.addRow("Max. Punkte:", self.max_grade_pts)

        # Direct mode widget
        self.grade_direct = QDoubleSpinBox()
        self.grade_direct.setRange(1.0, 6.0)
        self.grade_direct.setSingleStep(0.5)
        self.grade_direct.setDecimals(1)
        self.grade_direct.setValue(4.0)
        self.grade_direct.setSpecialValueText("")
        self.grade_direct.setToolTip(
            "Schweizer FH-Note: 1.0–6.0\n"
            "Bestehensgrenze: 4.0\n"
            "Schritte: 0.5  (1.0 / 1.5 / 2.0 … 5.5 / 6.0)"
        )
        self.grade_direct.valueChanged.connect(self._update_preview)
        self._row_direct = form.addRow("Note (1.0–6.0):", self.grade_direct)

        # Weight
        self.weight = QDoubleSpinBox()
        self.weight.setRange(0.01, 100)
        self.weight.setDecimals(2)
        self.weight.setValue(1.0)
        self.weight.setToolTip(
            "Relative Gewichtung dieser Leistung.\n"
            "Beispiel: Prüfung = 2.0, Testat = 1.0  →  Prüfung zählt doppelt."
        )
        form.addRow("Gewichtung:", self.weight)

        self.date_e = QDateEdit()
        self.date_e.setCalendarPopup(True)
        self.date_e.setDate(QDate.currentDate())
        form.addRow("Datum:", self.date_e)

        self.notes = QLineEdit()
        form.addRow("Notizen:", self.notes)
        lay.addLayout(form)

        # ── Live preview ──────────────────────────────────────────────────────
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setStyleSheet(
            f"font-size: 15px; font-weight: bold; padding: 8px; "
            f"border-radius: 6px; background: {_tc('#F5F5F5','#2A2A2A')};"
        )
        self._preview.setMinimumHeight(44)
        lay.addWidget(self._preview)

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._set_mode("points")   # init visibility

    # ── Mode switching ────────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        self._mode = mode
        is_pts = (mode == "points")
        self._btn_points.setChecked(is_pts)
        self._btn_direct.setChecked(not is_pts)
        # Show/hide rows
        self.grade_pts.setVisible(is_pts)
        self.max_grade_pts.setVisible(is_pts)
        self.grade_direct.setVisible(not is_pts)
        # Update form labels visibility via widget show/hide
        # (QFormLayout labels track widget visibility)
        self._update_preview()

    # ── Preview update ────────────────────────────────────────────────────────

    def _update_preview(self):
        try:
            if self._mode == "points":
                pts = self.grade_pts.value()
                maxp = self.max_grade_pts.value()
                if maxp <= 0:
                    self._preview.setText("—")
                    return
                pct = pts / maxp * 100.0
                ch = pct_to_ch_grade(pct)
                ch_r = ch_grade_rounded(pct)
                col = _grade_color(ch)
                self._preview.setText(
                    f"Note: <span style='color:{col}'>{ch:.2f}</span>  "
                    f"(gerundet: {ch_r:.1f})  ·  "
                    f"{_grade_icon(ch)} {_grade_label(ch)}"
                )
            else:
                ch = self.grade_direct.value()
                col = _grade_color(ch)
                self._preview.setText(
                    f"Note: <span style='color:{col}'>{ch:.1f}</span>  ·  "
                    f"{_grade_icon(ch)} {_grade_label(ch)}"
                )
        except Exception:
            self._preview.setText("—")

    # ── Helpers ───────────────────────────────────────────────────────────────

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

        mode = g["grade_mode"] if "grade_mode" in g.keys() else "points"
        self._set_mode(mode)
        if mode == "direct":
            self.grade_direct.setValue(float(g["grade"]))
        else:
            self.grade_pts.setValue(float(g["grade"]))
            self.max_grade_pts.setValue(float(g["max_grade"]))

        self.weight.setValue(float(g["weight"]))
        if g["date"]:
            try:
                d = datetime.strptime(g["date"], "%Y-%m-%d").date()
                self.date_e.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                pass
        self.notes.setText(g["notes"] or "")
        self._update_preview()

    # ── Accept / Save ─────────────────────────────────────────────────────────

    def _accept(self):
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        mid = self.module_cb.currentData()
        date_str = self.date_e.date().toString("yyyy-MM-dd")

        if self._mode == "direct":
            grade_val = self.grade_direct.value()
            max_val = 6.0
        else:
            grade_val = self.grade_pts.value()
            max_val = self.max_grade_pts.value()

        if self.grade_id:
            self.repo.update_grade(
                self.grade_id,
                title=title, module_id=mid,
                grade=grade_val, max_grade=max_val,
                weight=self.weight.value(), date=date_str,
                notes=self.notes.text(),
                grade_mode=self._mode,
            )
        else:
            self.repo.add_grade(
                mid, title,
                grade=grade_val, max_grade=max_val,
                weight=self.weight.value(), date_str=date_str,
                notes=self.notes.text(),
                grade_mode=self._mode,
            )
        self.accept()


class TopicDialog(QDialog):
    def __init__(self, repo: SqliteRepo, module_id: int,
                 topic_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
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

        # Task assignment dropdown (tasks belonging to this module)
        self.task_cb = QComboBox()
        self.task_cb.addItem("— keine Aufgabe —", None)
        for t in self.repo.list_tasks(module_id=self.module_id):
            self.task_cb.addItem(t["title"], t["id"])

        form.addRow("Titel *:", self.title)
        form.addRow("Kenntnisstand:", self.level)
        form.addRow("Aufgabe:", self.task_cb)
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
        # Restore linked task
        task_id = (int(t["task_id"]) if "task_id" in t.keys() and t["task_id"] is not None else None)
        cb_idx = self.task_cb.findData(task_id)
        if cb_idx >= 0:
            self.task_cb.setCurrentIndex(cb_idx)

    def _accept(self):
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        level = self.level.currentData()
        notes = self.notes.toPlainText()
        task_id = self.task_cb.currentData()   # None = no task assigned
        now_str = datetime.now().isoformat()
        if self.topic_id:
            self.repo.update_topic(self.topic_id, title=title,
                                   knowledge_level=level, notes=notes,
                                   task_id=task_id, last_reviewed=now_str)
        else:
            self.repo.add_topic(self.module_id, title, knowledge_level=level,
                                notes=notes, task_id=task_id)
            # Set last_reviewed on the just-created topic
            topics = self.repo.list_topics(self.module_id)
            new_t = next((t for t in topics if t["title"] == title), None)
            if new_t:
                self.repo.update_topic(new_t["id"], last_reviewed=now_str)
        self.accept()


# ── Pages ─────────────────────────────────────────────────────────────────

# ── Lern-Rückblick Dialog (nach Timer-Session) ─────────────────────────────

class LernRueckblickDialog(QDialog):
    """Zeigt nach jeder Timer-Session: abgehakte Lernziele + schnelles Thema eintragen."""

    def __init__(self, repo: SqliteRepo, module_id: Optional[int], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.mid = module_id
        self.setWindowTitle("🎉 Session abgeschlossen!")
        self.setMinimumWidth(400)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        title = QLabel("🎉 Gut gemacht! Was hast du in dieser Session erarbeitet?")
        title.setWordWrap(True)
        title.setStyleSheet("font-size:14px;font-weight:bold;")
        lay.addWidget(title)

        # Lernziel abhaken (only if module selected with objectives)
        if self.mid:
            objectives = [o for o in self.repo.list_scraped_data(self.mid, "objective")
                          if not int(o["checked"] or 0)]
            if objectives:
                sep = QFrame(); sep.setFrameShape(QFrame.HLine)
                lay.addWidget(sep)
                lay.addWidget(QLabel("Lernziel als erledigt markieren:"))
                self._lz_cb = QComboBox()
                self._lz_cb.addItem("— nichts Bestimmtes —", None)
                for o in objectives:
                    self._lz_cb.addItem(o["title"], o["id"])
                lay.addWidget(self._lz_cb)
            else:
                self._lz_cb = None
        else:
            self._lz_cb = None

        # Quick topic entry
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        lay.addWidget(sep2)
        lay.addWidget(QLabel("Neues Wissensthema schnell eintragen (optional):"))
        self._topic_edit = QLineEdit()
        self._topic_edit.setPlaceholderText("z.B. 'Rekursion verstanden', 'Kapitel 3 erledigt'…")
        lay.addWidget(self._topic_edit)

        know_row = QHBoxLayout()
        know_row.addWidget(QLabel("Kenntnisstand:"))
        self._know_cb = QComboBox()
        for k, v in KNOWLEDGE_LABELS.items():
            self._know_cb.addItem(v, k)
        self._know_cb.setCurrentIndex(2)  # default: "Ich verstehe es"
        know_row.addWidget(self._know_cb)
        know_row.addStretch()
        lay.addLayout(know_row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Speichern & Schließen")
        btns.button(QDialogButtonBox.Cancel).setText("Schließen ohne Speichern")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _save(self):
        # Mark Lernziel as checked
        if self._lz_cb is not None:
            oid = self._lz_cb.currentData()
            if oid is not None:
                self.repo.update_scraped_data(oid, checked=1)
        # Add quick topic
        if self.mid:
            topic_title = self._topic_edit.text().strip()
            if topic_title:
                level = self._know_cb.currentData()
                now_str = datetime.now().isoformat()
                self.repo.add_topic(self.mid, topic_title,
                                    knowledge_level=level, notes="")
                # Set last_reviewed to now for new topic
                topics = self.repo.list_topics(self.mid)
                new_t = next((t for t in topics if t["title"] == topic_title), None)
                if new_t:
                    self.repo.update_topic(new_t["id"], last_reviewed=now_str)
        self.accept()


# ── Fokus-Modus ────────────────────────────────────────────────────────────

class FocusPage(QWidget):
    """v3 Fokus-Modus — alles für ein Modul in einem Screen mit Tabs.
    Ersetzt Wissen-, Prüfungs- und Timer-Seite komplett."""

    PRIO_COLORS = {"Critical": "#F44336", "High": "#FF9800",
                   "Medium": "#FFC107", "Low": "#4CAF50"}

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._global_refresh: Optional[callable] = None
        self._timer_running = False
        self._timer_remaining = 25 * 60
        self._timer_total = 25 * 60
        self._timer_start_ts: Optional[int] = None
        self._qtimer = QTimer(self)
        self._qtimer.setInterval(1000)
        self._qtimer.timeout.connect(self._timer_tick)
        self._build()

    def set_global_refresh(self, cb):
        self._global_refresh = cb

    # ══════════════════════════ LAYOUT ══════════════════════════════════════

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 12)
        outer.setSpacing(10)

        # ── Top bar: title + module picker ──────────────────────────────────
        top = QHBoxLayout()
        title_lbl = QLabel("🎯  Fokus-Modus")
        title_lbl.setObjectName("PageTitle")
        top.addWidget(title_lbl)
        top.addStretch()
        top.addWidget(QLabel("Modul:"))
        self._mod_cb = QComboBox()
        self._mod_cb.setMinimumWidth(260)
        self._mod_cb.currentIndexChanged.connect(self._on_module_changed)
        top.addWidget(self._mod_cb)
        outer.addLayout(top)

        # ── Exam banner + progress badges + timer (always visible) ──────────
        info_frame = QFrame()
        info_frame.setObjectName("Card")
        info_lay = QVBoxLayout(info_frame)
        info_lay.setContentsMargins(16, 10, 16, 10)
        info_lay.setSpacing(8)

        # Row 1: module name + countdown
        banner_row = QHBoxLayout()
        self._exam_name_lbl = QLabel("← Modul wählen")
        self._exam_name_lbl.setStyleSheet("font-size:15px;font-weight:bold;")
        banner_row.addWidget(self._exam_name_lbl)
        banner_row.addStretch()
        self._exam_days_lbl = QLabel()
        self._exam_days_lbl.setStyleSheet("font-size:22px;font-weight:bold;")
        banner_row.addWidget(self._exam_days_lbl)
        self._exam_date_lbl = QLabel()
        self._exam_date_lbl.setStyleSheet("color:#706C86;font-size:12px;margin-left:6px;")
        banner_row.addWidget(self._exam_date_lbl)
        info_lay.addLayout(banner_row)

        # Row 2: progress badges + timer controls
        mid_row = QHBoxLayout()
        mid_row.setSpacing(8)
        self._stat_lz  = self._make_badge("0/0 Lernziele", "#4A86E8")
        self._stat_auf = self._make_badge("0/0 Aufgaben",  "#2CB67D")
        self._stat_wis = self._make_badge("Ø Wissen —",    "#9B59B6")
        for b in [self._stat_lz, self._stat_auf, self._stat_wis]:
            mid_row.addWidget(b)
        mid_row.addStretch()
        # Timer inline
        for label, mins in [("25′", 25), ("50′", 50), ("5′ Pause", 5)]:
            btn = QPushButton(label)
            btn.setObjectName("SecondaryBtn")
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda c, m=mins: self._timer_set(m))
            mid_row.addWidget(btn)
        self._timer_lbl = QLabel("25:00")
        self._timer_lbl.setStyleSheet(
            "font-size:18px;font-weight:bold;color:#4A86E8;min-width:62px;")
        self._timer_lbl.setAlignment(Qt.AlignCenter)
        mid_row.addWidget(self._timer_lbl)
        self._timer_btn = QPushButton("▶")
        self._timer_btn.setObjectName("PrimaryBtn")
        self._timer_btn.setFixedSize(36, 28)
        self._timer_btn.clicked.connect(self._timer_toggle)
        mid_row.addWidget(self._timer_btn)
        self._timer_note = QLineEdit()
        self._timer_note.setPlaceholderText("Notiz zur Session…")
        self._timer_note.setFixedWidth(180)
        mid_row.addWidget(self._timer_note)
        info_lay.addLayout(mid_row)
        outer.addWidget(info_frame)

        # ── Tabs: Lernziele | Aufgaben | Wissen ─────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        outer.addWidget(self._tabs, 1)

        self._tabs.addTab(self._build_lz_tab(),  "📖  Lernziele")
        self._tabs.addTab(self._build_auf_tab(), "✅  Aufgaben")
        self._tabs.addTab(self._build_wis_tab(), "🧠  Wissen")

    @staticmethod
    def _make_badge(text: str, color: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"background:{color};color:white;border-radius:10px;"
            f"padding:3px 10px;font-size:12px;font-weight:bold;")
        return lbl

    # ── Tab builders ─────────────────────────────────────────────────────────

    def _build_lz_tab(self) -> QWidget:
        w = QWidget()
        w.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(6)
        # toolbar
        tb = QHBoxLayout()
        add_btn = QPushButton("+ Lernziel")
        add_btn.setObjectName("SecondaryBtn")
        add_btn.clicked.connect(self._add_lernziel)
        tb.addWidget(add_btn)
        reset_btn = QPushButton("↺ Zurücksetzen")
        reset_btn.setObjectName("SecondaryBtn")
        reset_btn.clicked.connect(self._reset_lernziele)
        tb.addWidget(reset_btn)
        tb.addStretch()
        self._lz_prog_lbl = QLabel()
        self._lz_prog_lbl.setStyleSheet("color:#706C86;font-size:12px;")
        tb.addWidget(self._lz_prog_lbl)
        lay.addLayout(tb)
        # progress bar
        self._lz_bar = QProgressBar()
        self._lz_bar.setRange(0, 100)
        self._lz_bar.setFixedHeight(6)
        self._lz_bar.setTextVisible(False)
        self._lz_bar.setStyleSheet(
            "QProgressBar{border-radius:3px;background:#E0E0E0;}"
            "QProgressBar::chunk{background:#4A86E8;border-radius:3px;}")
        lay.addWidget(self._lz_bar)
        # scroll list
        self._lz_container = QWidget()
        self._lz_lay = QVBoxLayout(self._lz_container)
        self._lz_lay.setSpacing(2)
        self._lz_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(make_scroll(self._lz_container), 1)
        return w

    def _build_auf_tab(self) -> QWidget:
        w = QWidget()
        w.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(6)
        # toolbar
        tb = QHBoxLayout()
        add_btn = QPushButton("+ Aufgabe")
        add_btn.setObjectName("SecondaryBtn")
        add_btn.clicked.connect(self._add_aufgabe)
        tb.addWidget(add_btn)
        tb.addStretch()
        tb.addWidget(QLabel("Filter:"))
        self._auf_filter = QComboBox()
        self._auf_filter.addItems(["Offen", "Alle", "Erledigt"])
        self._auf_filter.currentIndexChanged.connect(self._reload_aufgaben)
        tb.addWidget(self._auf_filter)
        lay.addLayout(tb)
        # scroll list
        self._auf_container = QWidget()
        self._auf_lay = QVBoxLayout(self._auf_container)
        self._auf_lay.setSpacing(2)
        self._auf_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(make_scroll(self._auf_container), 1)
        return w

    def _build_wis_tab(self) -> QWidget:
        w = QWidget()
        w.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(6)
        # toolbar
        tb = QHBoxLayout()
        add_btn = QPushButton("+ Thema")
        add_btn.setObjectName("SecondaryBtn")
        add_btn.clicked.connect(self._add_thema)
        tb.addWidget(add_btn)
        self._wis_edit_btn = QPushButton("Bearbeiten")
        self._wis_edit_btn.setObjectName("SecondaryBtn")
        self._wis_edit_btn.clicked.connect(self._edit_thema)
        tb.addWidget(self._wis_edit_btn)
        self._wis_del_btn = QPushButton("Löschen")
        self._wis_del_btn.setObjectName("DangerBtn")
        self._wis_del_btn.clicked.connect(self._delete_thema)
        tb.addWidget(self._wis_del_btn)
        tb.addStretch()
        self._wis_summary_lbl = QLabel()
        self._wis_summary_lbl.setStyleSheet("color:#706C86;font-size:12px;")
        tb.addWidget(self._wis_summary_lbl)
        lay.addLayout(tb)
        # table
        self._wis_table = QTableWidget(0, 4)
        self._wis_table.setHorizontalHeaderLabels(["Thema", "Kenntnisstand", "Notizen", "ID"])
        self._wis_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._wis_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._wis_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._wis_table.verticalHeader().setVisible(False)
        self._wis_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._wis_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._wis_table.setColumnHidden(3, True)
        self._wis_table.doubleClicked.connect(self._edit_thema)
        lay.addWidget(self._wis_table, 1)
        return w

    # ══════════════════════════ REFRESH / POPULATE ══════════════════════════

    def refresh(self):
        cur = self._mod_cb.currentData()
        self._mod_cb.blockSignals(True)
        self._mod_cb.clear()
        self._mod_cb.addItem("— Modul wählen —", None)
        mods = self.repo.list_modules("active") or self.repo.list_modules("all")
        for m in mods:
            self._mod_cb.addItem(m["name"], m["id"])
        if cur:
            for i in range(self._mod_cb.count()):
                if self._mod_cb.itemData(i) == cur:
                    self._mod_cb.setCurrentIndex(i)
                    break
        self._mod_cb.blockSignals(False)
        self._populate()

    def _on_module_changed(self):
        self._populate()

    def _populate(self):
        mid = self._mod_cb.currentData()
        if not mid:
            self._exam_name_lbl.setText("← Modul wählen")
            self._exam_days_lbl.setText("")
            self._exam_date_lbl.setText("")
            self._stat_lz.setText("0/0 Lernziele")
            self._stat_auf.setText("0/0 Aufgaben")
            self._stat_wis.setText("Ø Wissen —")
            self._clear_lay(self._lz_lay)
            self._clear_lay(self._auf_lay)
            self._wis_table.setRowCount(0)
            return

        mod = self.repo.get_module(mid)
        if not mod:
            return

        # ── banner ──────────────────────────────────────────────────────────
        color = mod_color(mid)
        self._exam_name_lbl.setText(mod["name"])
        self._exam_name_lbl.setStyleSheet(
            f"font-size:15px;font-weight:bold;color:{color};")
        d = days_until(mod["exam_date"])
        exam_date_str = (mod["exam_date"] or "")
        if not exam_date_str or d is None:
            self._exam_days_lbl.setText("Kein Prüfungsdatum")
            self._exam_days_lbl.setStyleSheet("font-size:15px;color:#706C86;")
        elif d < 0:
            self._exam_days_lbl.setText("Prüfung vorbei")
            self._exam_days_lbl.setStyleSheet("font-size:15px;color:#9E9E9E;")
        elif d == 0:
            self._exam_days_lbl.setText("⚠ HEUTE!")
            self._exam_days_lbl.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#F44336;")
        elif d <= 5:
            self._exam_days_lbl.setText(f"🔴 {d} Tage")
            self._exam_days_lbl.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#F44336;")
        elif d <= 10:
            self._exam_days_lbl.setText(f"🟠 {d} Tage")
            self._exam_days_lbl.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#FF9800;")
        elif d <= 15:
            self._exam_days_lbl.setText(f"🟡 {d} Tage")
            self._exam_days_lbl.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#FFC107;")
        else:
            self._exam_days_lbl.setText(f"🟢 {d} Tage")
            self._exam_days_lbl.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#4CAF50;")
        self._exam_date_lbl.setText(exam_date_str)

        # ── badges ──────────────────────────────────────────────────────────
        objs  = self.repo.list_scraped_data(mid, "objective")
        tasks = self.repo.list_tasks(module_id=mid)
        topics = self.repo.list_topics(mid)
        lz_done = sum(1 for o in objs if int(o["checked"] or 0))
        t_done  = sum(1 for t in tasks if t["status"] == "Done")
        avg_k   = (sum(int(t["knowledge_level"]) for t in topics) / len(topics)
                   if topics else 0)
        self._stat_lz.setText(f"{lz_done}/{len(objs)} Lernziele ✓")
        self._stat_auf.setText(f"{t_done}/{len(tasks)} Aufgaben ✓")
        self._stat_wis.setText(f"Ø Wissen {avg_k:.1f}/4")

        # ── tabs ────────────────────────────────────────────────────────────
        self._populate_lernziele(mid, objs)
        self._reload_aufgaben()
        self._populate_wissen(mid, topics)

    # ── Tab: Lernziele ───────────────────────────────────────────────────────

    def _populate_lernziele(self, mid: int, objectives):
        self._clear_lay(self._lz_lay)
        total = len(objectives)
        done  = sum(1 for o in objectives if int(o["checked"] or 0))
        self._lz_prog_lbl.setText(f"{done} / {total} erledigt")
        self._lz_bar.setValue(int(done / total * 100) if total else 0)
        if not objectives:
            lbl = QLabel("Keine Lernziele — importiere Moduldaten oder füge manuell hinzu.")
            lbl.setStyleSheet("color:#706C86;font-size:12px;font-style:italic;")
            self._lz_lay.addWidget(lbl)
            self._lz_lay.addStretch()
            return
        for obj in objectives:
            row_w = QWidget()
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(4, 2, 4, 2)
            row_h.setSpacing(8)
            cb = QCheckBox()
            cb.setChecked(bool(int(obj["checked"] or 0)))
            oid = int(obj["id"])
            def _tog(state, o=oid):
                self.repo.update_scraped_data(o, checked=1 if state else 0)
                QTimer.singleShot(0, self._populate)
                if self._global_refresh:
                    QTimer.singleShot(10, self._global_refresh)
            cb.stateChanged.connect(_tog)
            row_h.addWidget(cb)
            checked = bool(int(obj["checked"] or 0))
            lbl = QLabel(obj["title"])
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                "color:#706C86;text-decoration:line-through;font-size:12px;"
                if checked else "font-size:12px;")
            row_h.addWidget(lbl, 1)
            self._lz_lay.addWidget(row_w)
        self._lz_lay.addStretch()

    def _reset_lernziele(self):
        mid = self._mod_cb.currentData()
        if not mid:
            return
        if QMessageBox.question(
                self, "Lernziele zurücksetzen",
                "Alle Lernziele als unerledigt markieren?",
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.reset_objectives_checked(mid)
            QTimer.singleShot(0, self._populate)
            if self._global_refresh:
                QTimer.singleShot(10, self._global_refresh)

    # ── Tab: Aufgaben ────────────────────────────────────────────────────────

    def _reload_aufgaben(self):
        mid = self._mod_cb.currentData()
        if not mid:
            self._clear_lay(self._auf_lay)
            return
        tasks = self.repo.list_tasks(module_id=mid)
        filt = self._auf_filter.currentText()
        if filt == "Offen":
            tasks = [t for t in tasks if t["status"] != "Done"]
        elif filt == "Erledigt":
            tasks = [t for t in tasks if t["status"] == "Done"]
        prio_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        tasks = sorted(tasks, key=lambda t: (
            t["status"] == "Done", prio_order.get(t["priority"] or "Low", 4)))
        self._clear_lay(self._auf_lay)
        if not tasks:
            lbl = QLabel("Keine Aufgaben vorhanden.")
            lbl.setStyleSheet("color:#706C86;font-size:12px;font-style:italic;")
            self._auf_lay.addWidget(lbl)
            self._auf_lay.addStretch()
            return
        for t in tasks:
            row_w = QWidget()
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(4, 2, 4, 2)
            row_h.setSpacing(8)
            cb = QCheckBox()
            cb.setChecked(t["status"] == "Done")
            tid = int(t["id"])
            def _tog_t(state, i=tid):
                self.repo.update_task(i, status="Done" if state else "Open")
                QTimer.singleShot(0, self._reload_aufgaben)
                if self._global_refresh:
                    QTimer.singleShot(10, self._global_refresh)
            cb.stateChanged.connect(_tog_t)
            row_h.addWidget(cb)
            prio_col = self.PRIO_COLORS.get(t["priority"] or "Low", "#999")
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{prio_col};font-size:10px;")
            row_h.addWidget(dot)
            lbl = QLabel(t["title"])
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                "color:#706C86;text-decoration:line-through;font-size:12px;"
                if t["status"] == "Done" else "font-size:12px;")
            row_h.addWidget(lbl, 1)
            prio_lbl = QLabel(t["priority"] or "")
            prio_lbl.setStyleSheet(
                f"color:{prio_col};font-size:10px;font-weight:bold;")
            row_h.addWidget(prio_lbl)
            self._auf_lay.addWidget(row_w)
        self._auf_lay.addStretch()

    # ── Tab: Wissen ──────────────────────────────────────────────────────────

    def _populate_wissen(self, mid: int, topics):
        self._wis_table.setRowCount(len(topics))
        review_count = 0
        for r, t in enumerate(topics):
            level = int(t["knowledge_level"])
            lr = (t["last_reviewed"] if "last_reviewed" in t.keys() else "") or ""
            needs_review = False
            if lr:
                try:
                    days_since = (date.today() -
                                  datetime.fromisoformat(lr).date()).days
                    if days_since >= 3 and level < 3:
                        needs_review = True
                        review_count += 1
                except Exception:
                    pass
            title_txt = ("⚠ " + t["title"]) if needs_review else t["title"]
            ti = QTableWidgetItem(title_txt)
            if needs_review:
                ti.setForeground(QColor("#FF9800"))
                ti.setToolTip(f"Review empfohlen — zuletzt: {lr[:10]}")
            self._wis_table.setItem(r, 0, ti)
            know_col = KNOWLEDGE_COLORS.get(level, "#333")
            ki = QTableWidgetItem(tr_know(level))
            ki.setForeground(QColor(know_col))
            self._wis_table.setItem(r, 1, ki)
            self._wis_table.setItem(r, 2, QTableWidgetItem(t["notes"] or ""))
            self._wis_table.setItem(r, 3, QTableWidgetItem(str(t["id"])))
        review_txt = (f"  ⚠ {review_count} Review fällig"
                      if review_count else "")
        self._wis_summary_lbl.setText(
            f"{len(topics)} Themen{review_txt}")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _clear_lay(self, lay: QVBoxLayout):
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def _require_module(self) -> Optional[int]:
        mid = self._mod_cb.currentData()
        if not mid:
            QMessageBox.warning(self, "Kein Modul",
                                "Bitte zuerst ein Modul auswählen.")
        return mid

    # ── Add / Edit / Delete actions ───────────────────────────────────────

    def _add_lernziel(self):
        mid = self._require_module()
        if not mid:
            return
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowTitle("Lernziel hinzufügen")
        dlg.setMinimumWidth(340)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Titel:"))
        edit = QLineEdit()
        lay.addWidget(edit)
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            t = edit.text().strip()
            if t:
                self.repo.add_scraped_data(mid, "objective", t)
                QTimer.singleShot(0, self._populate)
                if self._global_refresh:
                    QTimer.singleShot(10, self._global_refresh)

    def _add_aufgabe(self):
        mid = self._require_module()
        if not mid:
            return
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowTitle("Aufgabe hinzufügen")
        dlg.setMinimumWidth(340)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        t_edit = QLineEdit()
        prio_cb = QComboBox()
        prio_cb.addItems(["Low", "Medium", "High", "Critical"])
        mod = self.repo.get_module(mid)
        prio_cb.setCurrentText(
            exam_priority(mod["exam_date"] if mod else None))
        form.addRow("Titel *:", t_edit)
        form.addRow("Priorität:", prio_cb)
        lay.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            t = t_edit.text().strip()
            if t:
                self.repo.add_task(mid, t,
                                   priority=prio_cb.currentText(),
                                   status="Open")
                QTimer.singleShot(0, self._populate)
                if self._global_refresh:
                    QTimer.singleShot(10, self._global_refresh)

    def _add_thema(self):
        mid = self._require_module()
        if not mid:
            return
        if TopicDialog(self.repo, mid, parent=self).exec() == QDialog.Accepted:
            QTimer.singleShot(0, self._populate)
            if self._global_refresh:
                QTimer.singleShot(10, self._global_refresh)

    def _edit_thema(self):
        mid = self._require_module()
        if not mid:
            return
        row = self._wis_table.currentRow()
        if row < 0:
            return
        tid = int(self._wis_table.item(row, 3).text())
        if TopicDialog(self.repo, mid, topic_id=tid,
                       parent=self).exec() == QDialog.Accepted:
            QTimer.singleShot(0, self._populate)
            if self._global_refresh:
                QTimer.singleShot(10, self._global_refresh)

    def _delete_thema(self):
        row = self._wis_table.currentRow()
        if row < 0:
            return
        tid = int(self._wis_table.item(row, 3).text())
        title = self._wis_table.item(row, 0).text()
        if QMessageBox.question(
                self, "Thema löschen",
                f'"{title}" wirklich löschen?',
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_topic(tid)
            QTimer.singleShot(0, self._populate)
            if self._global_refresh:
                QTimer.singleShot(10, self._global_refresh)

    # ── Timer ────────────────────────────────────────────────────────────────

    def _timer_set(self, mins: int):
        if self._timer_running:
            return
        self._timer_total = mins * 60
        self._timer_remaining = mins * 60
        self._timer_update_lbl()

    def _timer_toggle(self):
        if self._timer_running:
            self._timer_running = False
            self._qtimer.stop()
            self._timer_btn.setText("▶")
        else:
            self._timer_running = True
            if not self._timer_start_ts:
                self._timer_start_ts = int(_time.time())
            self._qtimer.start()
            self._timer_btn.setText("⏹")

    def _timer_tick(self):
        if self._timer_remaining > 0:
            self._timer_remaining -= 1
            self._timer_update_lbl()
        else:
            self._qtimer.stop()
            self._timer_running = False
            self._timer_btn.setText("▶")
            self._timer_done()

    def _timer_update_lbl(self):
        m, s = divmod(self._timer_remaining, 60)
        self._timer_lbl.setText(f"{m:02d}:{s:02d}")

    def _timer_done(self):
        mid = self._mod_cb.currentData()
        if mid and self._timer_start_ts:
            end_ts = int(_time.time())
            note = self._timer_note.text().strip()
            self.repo.add_time_log(mid, self._timer_start_ts, end_ts,
                                   self._timer_total, "pomodoro", note)
            self._timer_note.clear()
        self._timer_start_ts = None
        self._timer_remaining = self._timer_total
        self._timer_update_lbl()
        LernRueckblickDialog(self.repo, mid, parent=self).exec()
        if self._global_refresh:
            QTimer.singleShot(0, self._global_refresh)


class DashboardPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._global_refresh = None
        self._navigate_cb = None   # set by main window to navigate between pages
        self._build()

    def set_global_refresh(self, cb):
        self._global_refresh = cb

    def set_navigate_cb(self, cb):
        """Register a callback(page_index) to switch to another page."""
        self._navigate_cb = cb

    def _build(self):
        # Wrap everything in a scroll area so content never overlaps on small screens
        _page_lay = QVBoxLayout(self)
        _page_lay.setContentsMargins(0, 0, 0, 0)
        _page_lay.setSpacing(0)
        _scroll_w = QWidget()
        _scroll_w.setAttribute(Qt.WA_StyledBackground, True)
        _page_lay.addWidget(make_scroll(_scroll_w))

        outer = QVBoxLayout(_scroll_w)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(16)

        # ── Semetra Killer Feature Banner ────────────────────────────────────
        self._fh_banner = QFrame()
        self._fh_banner.setObjectName("KillerFeatureBanner")
        self._fh_banner.setAttribute(Qt.WA_StyledBackground, True)
        self._fh_banner.setStyleSheet(
            "QFrame#KillerFeatureBanner{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #7C3AED,stop:1 #6D28D9);"
            "border-radius:12px;}"
        )
        self._fh_banner.setFixedHeight(54)
        fh_banner_lay = QHBoxLayout(self._fh_banner)
        fh_banner_lay.setContentsMargins(20, 0, 20, 0)
        fh_banner_lay.setSpacing(12)
        fh_banner_icon = QLabel("✨")
        fh_banner_icon.setStyleSheet("font-size:20px;")
        fh_banner_lay.addWidget(fh_banner_icon)
        self._fh_banner_lbl = QLabel("Studienplan automatisch generiert aus deiner Fachhochschule")
        self._fh_banner_lbl.setStyleSheet(
            "color:white;font-size:13px;font-weight:bold;"
        )
        fh_banner_lay.addWidget(self._fh_banner_lbl, 1)
        fh_banner_lay.addStretch()
        outer.addWidget(self._fh_banner)

        # ── Header row: greeting + semester selector ─────────────────────
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(12)
        self.greet_lbl = QLabel()
        self.greet_lbl.setObjectName("PageTitle")
        hdr_row.addWidget(self.greet_lbl, 1)

        sem_box = QFrame()
        sem_box.setObjectName("Card")
        sem_box.setAttribute(Qt.WA_StyledBackground, True)
        sem_box_lay = QHBoxLayout(sem_box)
        sem_box_lay.setContentsMargins(12, 6, 12, 6)
        sem_box_lay.setSpacing(6)
        sem_icon = QLabel("🎓")
        sem_icon.setStyleSheet("font-size:16px;")
        sem_box_lay.addWidget(sem_icon)
        sem_lbl_text = QLabel("Semester:")
        sem_lbl_text.setStyleSheet("font-size:12px; color:#7C3AED; font-weight:600;")
        sem_box_lay.addWidget(sem_lbl_text)
        self._sem_cb = QComboBox()
        self._sem_cb.setObjectName("SemesterFilter")
        self._sem_cb.setFixedWidth(175)
        self._sem_cb.setFixedHeight(32)
        self._sem_cb.setCursor(Qt.PointingHandCursor)
        self._sem_cb.setToolTip("Semester-Filter — wirkt auf Module, Aufgaben, Wissen, Prüfungen und Noten")
        self._sem_cb.currentIndexChanged.connect(self._on_sem_changed)
        sem_box_lay.addWidget(self._sem_cb)
        hdr_row.addWidget(sem_box)
        outer.addLayout(hdr_row)

        self.sub_lbl = QLabel()
        self.sub_lbl.setStyleSheet(
            f"color: {_tc('#8A849C','#5C5672')}; font-size: 13px;"
        )
        outer.addWidget(self.sub_lbl)

        # ── Daily motivational quote card ────────────────────────────────────
        self._quote_frame = QFrame()
        self._quote_frame.setObjectName("QuoteCard")
        self._quote_frame.setAttribute(Qt.WA_StyledBackground, True)
        q_lay = QHBoxLayout(self._quote_frame)
        q_lay.setContentsMargins(20, 16, 20, 16)
        q_lay.setSpacing(14)
        quote_icon = QLabel("✨\uFE0F")
        quote_icon.setStyleSheet("font-size:20px;")
        q_lay.addWidget(quote_icon)
        q_inner = QVBoxLayout()
        q_inner.setSpacing(4)
        self._quote_text_lbl = QLabel()
        self._quote_text_lbl.setWordWrap(True)
        self._quote_text_lbl.setStyleSheet(
            f"font-size:13px; font-weight:600;"
            f"color:{_tc('#3B1F7A','#C4B5FD')};"
        )
        self._quote_author_lbl = QLabel()
        self._quote_author_lbl.setStyleSheet(
            f"font-size:11px; color:{_tc('#7C3AED','#8B5CF6')};"
        )
        q_inner.addWidget(self._quote_text_lbl)
        q_inner.addWidget(self._quote_author_lbl)
        q_lay.addLayout(q_inner, 1)
        outer.addWidget(self._quote_frame)

        # ── Streak-Feier card (versteckt, erscheint bei Meilensteinen) ──────
        self._streak_cel_frame = QFrame()
        self._streak_cel_frame.setObjectName("QuoteCard")
        self._streak_cel_frame.setAttribute(Qt.WA_StyledBackground, True)
        sc_lay = QHBoxLayout(self._streak_cel_frame)
        sc_lay.setContentsMargins(20, 14, 20, 14)
        sc_lay.setSpacing(14)
        self._streak_cel_icon = QLabel("🎉\uFE0F")
        self._streak_cel_icon.setStyleSheet("font-size:26px;")
        sc_lay.addWidget(self._streak_cel_icon)
        sc_inner = QVBoxLayout()
        sc_inner.setSpacing(3)
        self._streak_cel_title = QLabel()
        self._streak_cel_title.setStyleSheet(
            f"font-size:15px;font-weight:800;color:{_tc('#3B1F7A','#C4B5FD')};"
        )
        self._streak_cel_sub = QLabel()
        self._streak_cel_sub.setStyleSheet(
            f"font-size:12px;color:{_tc('#7C3AED','#8B5CF6')};"
        )
        sc_inner.addWidget(self._streak_cel_title)
        sc_inner.addWidget(self._streak_cel_sub)
        sc_lay.addLayout(sc_inner, 1)
        self._streak_cel_frame.setVisible(False)
        outer.addWidget(self._streak_cel_frame)

        # ── Was jetzt? — Smarter Tages-Fokus ────────────────────────────────
        self._focus_frame = QFrame()
        self._focus_frame.setObjectName("FocusCard")
        self._focus_frame.setAttribute(Qt.WA_StyledBackground, True)
        # Cap height so it doesn't swallow the whole dashboard; items scroll.
        self._focus_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        focus_main = QVBoxLayout(self._focus_frame)
        focus_main.setContentsMargins(20, 16, 20, 16)
        focus_main.setSpacing(10)
        focus_hdr = QHBoxLayout()
        focus_title_lbl = QLabel("🎯\uFE0F  Was jetzt?")
        focus_title_lbl.setStyleSheet(
            f"font-size:14px;font-weight:800;"
            f"color:{_tc('#1A1523','#EAE6F4')};"
        )
        focus_hdr.addWidget(focus_title_lbl)
        focus_hdr.addStretch()
        self._focus_plan_btn = QPushButton("📅  Lernplan")
        self._focus_plan_btn.setObjectName("SecondaryBtn")
        self._focus_plan_btn.setFixedHeight(30)
        self._focus_plan_btn.clicked.connect(self._open_study_plan_generator)
        focus_hdr.addWidget(self._focus_plan_btn)

        self._notfall_btn = QPushButton("🚨  Notfall")
        self._notfall_btn.setObjectName("DangerBtn")
        self._notfall_btn.setFixedHeight(30)
        self._notfall_btn.clicked.connect(self._open_notfall_modus)
        focus_hdr.addWidget(self._notfall_btn)
        focus_main.addLayout(focus_hdr)

        # Scroll area so long lists don't blow up the card height
        self._focus_scroll = QScrollArea()
        self._focus_scroll.setWidgetResizable(True)
        self._focus_scroll.setFrameShape(QFrame.NoFrame)
        self._focus_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._focus_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._focus_scroll.setMaximumHeight(180)
        self._focus_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        _focus_inner = QWidget()
        _focus_inner.setAttribute(Qt.WA_StyledBackground, False)
        self._focus_items_layout = QVBoxLayout(_focus_inner)
        self._focus_items_layout.setSpacing(4)
        self._focus_items_layout.setContentsMargins(0, 0, 4, 0)
        self._focus_items_layout.addStretch()
        self._focus_scroll.setWidget(_focus_inner)
        focus_main.addWidget(self._focus_scroll)
        outer.addWidget(self._focus_frame)

        # ── Spaced-Rep Warnung (clickable → Wissensseite) ────────────────
        self._spaced_rep_frame = QFrame()
        self._spaced_rep_frame.setObjectName("Card")
        self._spaced_rep_frame.setAttribute(Qt.WA_StyledBackground, True)
        self._spaced_rep_frame.setCursor(Qt.PointingHandCursor)
        self._spaced_rep_frame.setToolTip("Klicken → zur Wissensseite")
        sr_lay = QHBoxLayout(self._spaced_rep_frame)
        sr_lay.setContentsMargins(18, 12, 18, 12)
        sr_lay.setSpacing(14)
        sr_icon = QLabel("🧠\uFE0F")
        sr_icon.setStyleSheet("font-size:20px;")
        sr_lay.addWidget(sr_icon)
        self._sr_lbl = QLabel()
        self._sr_lbl.setWordWrap(True)
        self._sr_lbl.setStyleSheet(
            f"font-size:13px; font-weight:500; color:{_tc('#3B1F7A','#C4B5FD')};"
        )
        sr_lay.addWidget(self._sr_lbl, 1)
        sr_arrow = QLabel("→")
        sr_arrow.setStyleSheet(f"font-size:16px; font-weight:bold; color:{_tc('#7C3AED','#A78BFA')};")
        sr_lay.addWidget(sr_arrow)
        self._spaced_rep_frame.setVisible(False)
        # Install mouse handler to navigate on click
        self._spaced_rep_frame.mousePressEvent = lambda e: (
            self._go_to_knowledge() if e.button() == Qt.LeftButton else None
        )
        outer.addWidget(self._spaced_rep_frame)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self.card_streak  = StatCard("Lernserie",       "0",   "Tage", "#F59E0B")
        self.card_hours   = StatCard("Diese Woche",     "0.0", "h",    "#7C3AED")
        self.card_modules = StatCard("Aktive Module",   "0",   "",     "#10B981")
        self.card_tasks   = StatCard("Offene Aufgaben", "0",   "",     "#F43F5E")
        self.card_sr_due  = StatCard("SR Reviews",      "0",   "fällig", "#FF8C42").make_clickable()
        self.card_sr_due.clicked.connect(self._go_to_knowledge)
        self.card_sr_due.setToolTip("Klicken → zur Wissensseite (SR-Reviews starten)")
        for c in [self.card_streak, self.card_hours, self.card_modules, self.card_tasks, self.card_sr_due]:
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            stats_row.addWidget(c)
        outer.addLayout(stats_row)

        # ── Overall study progress row ───────────────────────────────────────
        prog_row2 = QHBoxLayout()
        prog_row2.setSpacing(14)
        self.card_ects      = StatCard("ECTS Gesamt", "0 / 0", "", "#7C3AED")
        self.card_tasks_pct = StatCard("Aufgaben erledigt", "0%", "", "#10B981")
        self.card_overall   = StatCard("Studienfortschritt", "0%", "", "#A78BFA")
        for c in [self.card_ects, self.card_tasks_pct, self.card_overall]:
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            prog_row2.addWidget(c)
        outer.addLayout(prog_row2)

        # Overall progress bar
        prog_frame = QFrame()
        prog_frame.setObjectName("Card")
        prog_fl = QVBoxLayout(prog_frame)
        prog_fl.setContentsMargins(16, 10, 16, 12)
        prog_fl.setSpacing(6)
        prog_hdr = QHBoxLayout()
        prog_title_lbl = QLabel("Studium Gesamtfortschritt")
        prog_title_lbl.setStyleSheet("font-weight:bold;font-size:13px;")
        prog_hdr.addWidget(prog_title_lbl)
        prog_hdr.addStretch()
        self._overall_pct_lbl = QLabel("0%")
        self._overall_pct_lbl.setStyleSheet("color:#7C3AED;font-weight:bold;font-size:13px;")
        prog_hdr.addWidget(self._overall_pct_lbl)
        prog_fl.addLayout(prog_hdr)
        self._overall_bar = QProgressBar()
        self._overall_bar.setRange(0, 100)
        self._overall_bar.setFixedHeight(10)
        self._overall_bar.setTextVisible(False)
        prog_fl.addWidget(self._overall_bar)
        self._overall_sub = QLabel()
        self._overall_sub.setStyleSheet("color:#6B7280;font-size:11px;")
        prog_fl.addWidget(self._overall_sub)
        outer.addWidget(prog_frame)

        self._exam_section_lbl = QLabel(tr("dash.upcoming_exams"))
        self._exam_section_lbl.setObjectName("SectionTitle")
        outer.addWidget(self._exam_section_lbl)

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

        self._mod_section_lbl = QLabel(tr("sec.progress"))
        self._mod_section_lbl.setObjectName("SectionTitle")
        outer.addWidget(self._mod_section_lbl)

        self.mod_container = QWidget()
        self.mod_grid = QGridLayout(self.mod_container)
        self.mod_grid.setSpacing(12)
        outer.addWidget(self.mod_container)

    def _on_sem_changed(self):
        """Persist selected semester and trigger a global refresh."""
        sem = self._sem_cb.currentData() or ""
        self.repo.set_setting("filter_semester", sem)
        if self._global_refresh:
            QTimer.singleShot(0, self._global_refresh)

    def refresh(self):
        now = datetime.now()
        _day_name = now.strftime("%A")
        _date_str = now.strftime("%d. %B %Y")
        self.greet_lbl.setText(f"{greeting()}, {_day_name} · {_date_str}")

        # ── Update FH banner with saved FH/Studiengang ────────────────────
        fh_name = self.repo.get_setting("fh_name") or ""
        studiengang = self.repo.get_setting("studiengang") or ""
        if fh_name and studiengang:
            self._fh_banner_lbl.setText(
                f"✨  Studienplan automatisch generiert aus {fh_name} · {studiengang}"
            )
        elif fh_name:
            self._fh_banner_lbl.setText(
                f"✨  Studienplan automatisch generiert aus {fh_name}"
            )
        else:
            self._fh_banner_lbl.setText(
                "✨  Studienplan automatisch generiert aus deiner Fachhochschule"
            )

        # ── Populate semester selector (keep current selection) ──────────
        all_mods_raw = self.repo.list_modules("all")
        sems_raw = sorted(
            {str(m["semester"] or "").strip() for m in all_mods_raw if m["semester"]},
            key=lambda s: int(s) if s.isdigit() else 999,
        )
        saved_sem = _active_sem_filter(self.repo)
        self._sem_cb.blockSignals(True)
        self._sem_cb.clear()
        self._sem_cb.addItem("Alle Semester", "")
        for s in sems_raw:
            label = f"{s}. Semester" if s.isdigit() else s
            self._sem_cb.addItem(label, s)
        # Restore saved selection
        for i in range(self._sem_cb.count()):
            if self._sem_cb.itemData(i) == saved_sem:
                self._sem_cb.setCurrentIndex(i)
                break
        self._sem_cb.blockSignals(False)

        # ── Apply semester filter to stat cards ──────────────────────────
        sem_f = saved_sem
        filtered_mods = _filter_mods_by_sem(all_mods_raw, sem_f)
        mod_ids_f = {m["id"] for m in filtered_mods}

        # Daily quote — deterministic by day-of-year so it stays stable during a session
        q_idx = date.today().timetuple().tm_yday % len(STUDENT_QUOTES)
        q_text, q_author = STUDENT_QUOTES[q_idx]
        self._quote_text_lbl.setText("\u201E" + q_text + "\u201C")
        self._quote_author_lbl.setText(f"— {q_author}" if q_author else "")
        self._quote_author_lbl.setVisible(bool(q_author))

        streak = self.repo.get_study_streak()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_secs = self.repo.seconds_studied_week(week_start)
        active_mods = len([m for m in filtered_mods if m["status"] == "active"])
        open_tasks = len([t for t in self.repo.list_tasks(status="Open")
                          if t["module_id"] in mod_ids_f])

        self.card_streak.set_value(str(streak))
        self.card_hours.set_value(f"{week_secs/3600:.1f}")
        self.card_modules.set_value(str(active_mods))
        self.card_tasks.set_value(str(open_tasks))
        _sr_due_now = self.repo.sm2_stats()["due"]
        self.card_sr_due.set_value(str(_sr_due_now))
        self.card_sr_due.setStyleSheet(
            "" if _sr_due_now == 0
            else "border:1px solid #FF8C4288;" if _THEME == "light"
            else "border:1px solid #FF8C4266;"
        )

        # Overall progress stats — filtered by semester, only plan modules
        plan_modules = [m for m in filtered_mods if (int(m["in_plan"]) if "in_plan" in m.keys() and m["in_plan"] is not None else 1)]
        total_ects = sum(float(m["ects"]) for m in plan_modules)
        done_ects  = sum(float(m["ects"]) for m in plan_modules if m["status"] == "completed")
        completed_mods = sum(1 for m in plan_modules if m["status"] == "completed")
        all_tasks  = [t for t in self.repo.list_tasks() if t["module_id"] in mod_ids_f]
        total_tasks = len(all_tasks)
        done_tasks  = sum(1 for t in all_tasks if t["status"] == "Done")
        task_pct = int(done_tasks / total_tasks * 100) if total_tasks > 0 else 0
        overall_pct = int(((done_ects / total_ects) * 0.5 + (done_tasks / total_tasks) * 0.5) * 100) \
                      if (total_ects > 0 and total_tasks > 0) else 0
        self.card_ects.set_value(f"{int(done_ects)} / {int(total_ects)}")
        self.card_tasks_pct.set_value(f"{task_pct}%")
        self.card_overall.set_value(f"{overall_pct}%")
        self._overall_bar.setValue(overall_pct)
        self._overall_pct_lbl.setText(f"{overall_pct}%")
        # Retranslate section labels and stat card titles
        self._exam_section_lbl.setText(tr("dash.upcoming_exams"))
        self._mod_section_lbl.setText(tr("sec.progress"))
        self.card_streak.title_lbl.setText(tr("dash.study_hours").replace("(7d)","").replace("(7j)","").replace("(7T)","").strip() if False else (
            {"de": "Lernserie", "en": "Study Streak", "fr": "Série d'étude", "it": "Sequenza studio"}.get(_LANG, "Lernserie")
        ))
        self.card_hours.title_lbl.setText(tr("dash.study_hours"))
        self.card_modules.title_lbl.setText(tr("dash.modules_active"))
        self.card_tasks.title_lbl.setText(tr("dash.tasks_open"))

        mods_done_txt = {"de": f"{completed_mods}/{len(plan_modules)} Module abgeschlossen",
                         "en": f"{completed_mods}/{len(plan_modules)} modules completed",
                         "fr": f"{completed_mods}/{len(plan_modules)} modules terminés",
                         "it": f"{completed_mods}/{len(plan_modules)} moduli completati"}.get(_LANG, f"{completed_mods}/{len(plan_modules)} modules")
        tasks_done_txt = {"de": f"{done_tasks}/{total_tasks} Aufgaben erledigt",
                          "en": f"{done_tasks}/{total_tasks} tasks done",
                          "fr": f"{done_tasks}/{total_tasks} tâches terminées",
                          "it": f"{done_tasks}/{total_tasks} attività fatte"}.get(_LANG, f"{done_tasks}/{total_tasks} tasks")
        self._overall_sub.setText(f"{mods_done_txt}  ·  {tasks_done_txt}  ·  {int(done_ects)}/{int(total_ects)} ECTS (geplante Module)")

        # ── Streak sub-label ─────────────────────────────────────────────────
        if streak == 0:
            self.sub_lbl.setText("Starte deine Lernserie — jeder Anfang zählt. 🚀")
        elif streak == 1:
            self.sub_lbl.setText("Tag 1 ist der wichtigste — bleib dran! 🌱")
        else:
            self.sub_lbl.setText(f"🔥 {streak} Tage am Ball — du bist auf Kurs!")

        # ── Streak-Feier bei Meilensteinen ───────────────────────────────────
        milestones = {7: ("7 Tage Streak!", "Eine Woche konsequent. Das ist echter Fortschritt! 💪"),
                      14: ("14 Tage Streak!", "Zwei Wochen am Ball — du bist auf einem guten Weg! 🌟"),
                      30: ("30 Tage Streak!", "Ein ganzer Monat. Du bist jetzt ein Profi! 🏆"),
                      60: ("60 Tage Streak!", "Zwei Monate — unglaubliche Ausdauer! 🎖️"),
                      100: ("100 Tage Streak!", "LEGENDÄR. 100 Tage in Folge! 🎊")}
        if streak in milestones:
            title, sub = milestones[streak]
            self._streak_cel_title.setText(title)
            self._streak_cel_sub.setText(sub)
            self._streak_cel_frame.setVisible(True)
        else:
            self._streak_cel_frame.setVisible(False)

        # ── Smarter Tages-Fokus: Was jetzt? ─────────────────────────────────
        # Clear old focus items
        while self._focus_items_layout.count():
            item = self._focus_items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        focus_actions: list[tuple[str, str, str]] = []  # (icon, text, urgency_color)
        today_str = date.today().isoformat()

        # 1. Exams within 3 days → highest urgency
        for m in self.repo.upcoming_exams(within_days=3):
            d = days_until(m["exam_date"])
            if d is not None and d >= 0:
                label = "HEUTE!" if d == 0 else f"in {d} Tag{'en' if d != 1 else ''}"
                focus_actions.append(("🚨", f"Prüfung <b>{m['name']}</b> {label} — alles stehen lassen!", "#DC2626"))

        # 2. Tasks due today (overdue first)
        overdue = [t for t in self.repo.list_tasks(status="Open")
                   if (t["due_date"] or "") < today_str and (t["due_date"] or "") != ""]
        due_today_list = [t for t in self.repo.list_tasks(status="Open")
                          if (t["due_date"] or "") == today_str]
        for t in overdue[:2]:
            focus_actions.append(("⚠️", f"Überfällig: <b>{t['title']}</b>", "#D97706"))
        for t in due_today_list[:2]:
            focus_actions.append(("✅", f"Heute fällig: <b>{t['title']}</b>", "#7C3AED"))

        # 3. Exams within 7 days → prep reminder
        for m in self.repo.upcoming_exams(within_days=7):
            d = days_until(m["exam_date"])
            if d is not None and d >= 4:
                focus_actions.append(("📖", f"Prüfungsvorbereitung: <b>{m['name']}</b> in {d} Tagen", "#D97706"))

        # 4. SM-2 Spaced Repetition — due topics (real algorithm)
        sr_due_all = self.repo.sm2_due_topics()
        sr_due_count = len(sr_due_all)
        if sr_due_count > 0:
            # Group by module
            sr_by_mod: dict = {}
            for t in sr_due_all:
                mn = t["module_name"] if "module_name" in t.keys() else "?"
                sr_by_mod.setdefault(mn, 0)
                sr_by_mod[mn] += 1
            mod_parts = [f"{n}×{mn[:20]}" for mn, n in list(sr_by_mod.items())[:2]]
            mods_str  = ", ".join(mod_parts) + ("…" if len(sr_by_mod) > 2 else "")
            focus_actions.append((
                "🧠",
                f"<b>{sr_due_count} SR-Review{'s' if sr_due_count != 1 else ''}</b> fällig ({mods_str})"
                f" — Wissensseite öffnen",
                "#7C3AED"
            ))

        # 5. Readiness-Score Alarm — module has exam coming up but low readiness
        for m in self.repo.list_modules("all"):
            if not (int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1):
                continue
            if m["status"] == "completed":
                continue
            rs = self.repo.exam_readiness_score(m["id"])
            days_ex = rs["days_until_exam"]
            score   = rs["total"]
            if days_ex is None or days_ex < 0 or days_ex > 45:
                continue
            if not rs["has_data"] and days_ex > 14:
                continue
            # Compute recommended daily minutes
            hrs_target  = rs["hours_target"]
            hrs_studied = rs["hours_studied"]
            remaining_h = max(0.0, hrs_target - hrs_studied)
            if days_ex > 0 and remaining_h > 0:
                daily_min = max(15, min(120, int((remaining_h * 60) / days_ex)))
            else:
                daily_min = 30
            # Show warning for low-readiness urgent modules
            if score < 70 and days_ex <= 30:
                if score < 30:
                    icon_r, col_r = "🔴", "#DC2626"
                elif score < 60:
                    icon_r, col_r = "⚡", "#D97706"
                else:
                    icon_r, col_r = "📈", "#7C3AED"
                mn_short = m["name"][:28]
                focus_actions.append((
                    icon_r,
                    f"<b>{mn_short}</b>: {score}% bereit, Prüfung in {days_ex}d "
                    f"→ heute <b>{daily_min} min</b> empfohlen",
                    col_r
                ))

        # 6. Weekly hours nudge
        if week_secs < 3600:
            focus_actions.append(("⏱", "Diese Woche noch <b>unter 1 Stunde</b> gelernt — starte jetzt!", "#6B7280"))

        if not focus_actions:
            empty_w = QWidget()
            empty_w.setAttribute(Qt.WA_StyledBackground, True)
            empty_w.setStyleSheet(
                "background: transparent; border-radius: 10px;"
            )
            e_lay = QHBoxLayout(empty_w)
            e_lay.setContentsMargins(10, 8, 10, 8)
            e_lay.setSpacing(10)
            e_icon = QLabel("✅\uFE0F")
            e_icon.setStyleSheet("font-size:18px;")
            e_lay.addWidget(e_icon)
            e_txt = QLabel("Alles im Griff — bleib locker und gönn dir eine Pause.")
            e_txt.setStyleSheet(f"color:{_tc('#059669','#34D399')};font-size:13px;font-weight:600;")
            e_lay.addWidget(e_txt, 1)
            self._focus_items_layout.insertWidget(0, empty_w)
        else:
            for i, (icon, text, color) in enumerate(focus_actions[:6]):  # show max 6 items
                # Pill-style row: left accent border + very light tinted bg
                row_w = QWidget()
                row_w.setAttribute(Qt.WA_StyledBackground, True)
                # Use rgba() — Qt 8-digit hex is #AARRGGBB not #RRGGBBAA!
                _bg = _hex_rgba(color, _tc(0.08, 0.13))
                _txt_color = _tc("#1E1033", "#EAE6F4")
                row_w.setStyleSheet(
                    f"background: {_bg};"
                    f"border-radius: 10px;"
                    f"border-left: 3px solid {color};"
                )
                row_l = QHBoxLayout(row_w)
                row_l.setContentsMargins(12, 8, 14, 8)
                row_l.setSpacing(10)
                ico_lbl = QLabel(icon)
                ico_lbl.setStyleSheet("font-size:16px; background: transparent; border: none;")
                ico_lbl.setFixedWidth(24)
                row_l.addWidget(ico_lbl)
                txt_lbl = QLabel(text)
                txt_lbl.setTextFormat(Qt.RichText)
                txt_lbl.setWordWrap(True)
                txt_lbl.setStyleSheet(
                    f"font-size:13px; font-weight:500; background: transparent; border: none;"
                    f"color: {_txt_color};"
                )
                row_l.addWidget(txt_lbl, 1)
                self._focus_items_layout.insertWidget(i, row_w)

        # ── SM-2 Zusammenfassung (Banner) ─────────────────────────────────────
        sr_stats = self.repo.sm2_stats()
        if sr_stats["due"] > 0:
            due_n      = sr_stats["due"]
            sched_n    = sr_stats["scheduled"]
            total_n    = sr_stats["total"]
            self._sr_lbl.setText(
                f"<b>{due_n} SR-Review{'s' if due_n != 1 else ''}</b> fällig "
                f"({sched_n} geplant · {total_n} Topics gesamt). "
                f"Öffne die <b>Wissensseite</b> und starte eine Review-Session."
            )
            self._sr_lbl.setTextFormat(Qt.RichText)
            self._spaced_rep_frame.setVisible(True)
        else:
            self._spaced_rep_frame.setVisible(False)

        # Exam cards
        while self.exam_row.count() > 1:
            item = self.exam_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        exams = self.repo.upcoming_exams(within_days=60)
        if not exams:
            lbl = QLabel(tr("dash.no_exams"))
            lbl.setStyleSheet("color: #706C86; font-size: 13px;")
            self.exam_row.insertWidget(0, lbl)
        else:
            for i, m in enumerate(exams):
                self.exam_row.insertWidget(i, self._make_exam_card(m))

        # Module progress grid
        while self.mod_grid.count():
            item = self.mod_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        modules = self.repo.list_modules("all")
        for idx, m in enumerate(modules):
            row, col = divmod(idx, 3)
            self.mod_grid.addWidget(self._make_module_card(m), row, col)

    def _go_to_knowledge(self):
        """Navigate to the Wissen/Knowledge page (index 5)."""
        if self._navigate_cb:
            self._navigate_cb(5)

    def _open_study_plan_generator(self):
        dlg = StudyPlanGeneratorDialog(self.repo, parent=self)
        dlg.exec()

    def _open_notfall_modus(self):
        dlg = NotfallModusDialog(self.repo, parent=self)
        dlg.exec()

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
            d_txt, d_col = "—", "#706C86"
        elif d < 0:
            d_txt, d_col = tr("exam.passed"), "#9E9E9E"
        elif d == 0:
            d_txt, d_col = tr("exam.today").upper() + "!", "#F44336"
        elif d <= 7:
            d_txt, d_col = tr("exam.days_left").format(n=d), "#FF9800"
        else:
            d_txt, d_col = tr("exam.days_left").format(n=d), "#4A86E8"
        days_lbl = QLabel(d_txt)
        days_lbl.setStyleSheet(f"color: {d_col}; font-size: 13px; font-weight: bold;")
        lay.addWidget(days_lbl)
        date_lbl = QLabel(m["exam_date"])
        date_lbl.setStyleSheet("color: #706C86; font-size: 11px;")
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
        status_lbl = QLabel(tr_status(m["status"]))
        status_lbl.setStyleSheet("color: #706C86; font-size: 11px;")
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
        sub.setStyleSheet("color: #706C86; font-size: 11px;")
        lay.addWidget(sub)
        return card


# ── Web Import ──────────────────────────────────────────────────────────────

class _ScraperWorker(QThread):
    """QThread wrapper around UniversityWebScraper.scrape()."""
    progress = Signal(str)      # status message
    finished = Signal(list)     # list[dict] of extracted modules
    error    = Signal(str)      # error message

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            from semetra.adapters.web_scraper import UniversityWebScraper
            scraper = UniversityWebScraper()
            modules = scraper.scrape(self._url, progress_cb=lambda msg: self.progress.emit(msg))
            self.finished.emit(modules)
        except Exception as exc:
            self.error.emit(str(exc))


# ── Pro Feature Gate ─────────────────────────────────────────────────────────

class ProFeatureDialog(QDialog):
    """
    Wird gezeigt wenn ein Free-User ein Pro-Feature nutzen will.
    Zeigt die 3 Abo-Optionen (monatl./halbjährl./jährl.) und ermöglicht
    die Aktivierung eines bereits gekauften Lizenzcodes.
    Returns Accepted wenn eine Lizenz erfolgreich aktiviert wurde.
    """
    def __init__(self, feature_name: str, repo, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.feature_name = feature_name
        self.setWindowTitle("Semetra Pro")
        self.setMinimumWidth(500)
        self.setMaximumWidth(560)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(14)

        # ── Header ──────────────────────────────────────────────────────────
        top = QHBoxLayout()
        icon = QLabel("⭐")
        icon.setStyleSheet("font-size:36px;")
        top.addWidget(icon)
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title_lbl = QLabel("Semetra Pro")
        title_lbl.setStyleSheet("font-size:20px;font-weight:bold;")
        sub_lbl = QLabel(f"Um <b>\"{self.feature_name}\"</b> zu nutzen,\nbenötigst du Semetra Pro.")
        sub_lbl.setStyleSheet(f"color:{_tc('#555','#AAA')};font-size:13px;")
        sub_lbl.setWordWrap(True)
        sub_lbl.setTextFormat(Qt.RichText)
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        top.addLayout(title_col, 1)
        lay.addLayout(top)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{_tc('#DDE3F0','#383850')};")
        lay.addWidget(sep)

        # ── Feature-Liste ────────────────────────────────────────────────────
        features_lbl = QLabel(
            "<b>Pro beinhaltet:</b><br>"
            "🤖 &nbsp;KI-Studien-Coach (unbegrenzt)<br>"
            "📄 &nbsp;PDF-Import (Modulplan direkt einlesen)<br>"
            "⏱️ &nbsp;Lern-Timer mit Statistiken &amp; Streaks<br>"
            "📊 &nbsp;Lernplan-Generator &amp; Prognosen<br>"
            "🏅 &nbsp;Erweiterte Notenanalyse &amp; Trends<br>"
            "🔮 &nbsp;Alle zukünftigen Pro-Features inklusive"
        )
        features_lbl.setTextFormat(Qt.RichText)
        features_lbl.setWordWrap(True)
        features_lbl.setStyleSheet("font-size:13px;line-height:1.8;")
        lay.addWidget(features_lbl)

        # ── Pricing Cards ────────────────────────────────────────────────────
        pricing_lbl = QLabel("<b>Plan wählen:</b>")
        pricing_lbl.setTextFormat(Qt.RichText)
        lay.addWidget(pricing_lbl)

        plans = [
            ("Monatlich",   "CHF 4.90",  "/Monat",     "",                    "monthly"),
            ("Halbjährlich","CHF 24.90", "/6 Monate",  "CHF 2.50 sparen",     "halfyear"),
            ("Jährlich",    "CHF 39.90", "/Jahr",       "CHF 19 sparen – Best Value 🏆", "yearly"),
        ]
        plans_row = QHBoxLayout()
        plans_row.setSpacing(8)
        self._plan_btns: list = []
        for label, price, period, badge, key in plans:
            card = QFrame()
            card.setFixedHeight(100)
            card.setCursor(Qt.PointingHandCursor)
            card.setStyleSheet(
                "QFrame{border:2px solid #E5E7EB;border-radius:10px;"
                "background:white;}"
            )
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(10, 8, 10, 8)
            c_lay.setSpacing(2)
            lbl_plan = QLabel(label)
            lbl_plan.setStyleSheet("font-size:11px;font-weight:bold;color:#6B7280;")
            lbl_price = QLabel(price)
            lbl_price.setStyleSheet("font-size:18px;font-weight:bold;")
            lbl_period = QLabel(period)
            lbl_period.setStyleSheet("font-size:10px;color:#9CA3AF;")
            if badge:
                lbl_badge = QLabel(badge)
                lbl_badge.setStyleSheet(
                    "font-size:9px;color:#059669;font-weight:bold;"
                )
                lbl_badge.setWordWrap(True)
            c_lay.addWidget(lbl_plan)
            c_lay.addWidget(lbl_price)
            c_lay.addWidget(lbl_period)
            if badge:
                c_lay.addWidget(lbl_badge)
            buy_btn = QPushButton("Kaufen →")
            buy_btn.setFixedHeight(26)
            buy_btn.setStyleSheet(
                "QPushButton{background:#7C3AED;color:white;border-radius:6px;"
                "font-size:11px;font-weight:bold;border:none;}"
                "QPushButton:hover{background:#6D28D9;}"
            )
            buy_btn.setCursor(Qt.PointingHandCursor)
            buy_btn.clicked.connect(lambda checked, k=key: self._open_buy(k))
            c_lay.addWidget(buy_btn)
            plans_row.addWidget(card)
            self._plan_btns.append((key, card))
        lay.addLayout(plans_row)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"color:{_tc('#DDE3F0','#383850')};")
        lay.addWidget(sep2)

        # ── Lizenzcode Eingabe ───────────────────────────────────────────────
        already_lbl = QLabel("Hast du bereits einen Lizenzcode?")
        already_lbl.setStyleSheet("font-size:12px;font-weight:bold;")
        lay.addWidget(already_lbl)

        code_row = QHBoxLayout()
        self._code_edit = QLineEdit()
        self._code_edit.setPlaceholderText("XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX")
        self._code_edit.setFixedHeight(34)
        self._code_edit.returnPressed.connect(self._activate)
        code_row.addWidget(self._code_edit, 1)
        activate_btn = QPushButton("Aktivieren")
        activate_btn.setObjectName("PrimaryBtn")
        activate_btn.setFixedHeight(34)
        activate_btn.clicked.connect(self._activate)
        code_row.addWidget(activate_btn)
        lay.addLayout(code_row)

        self._error_lbl = QLabel("")
        self._error_lbl.setStyleSheet("color:#E05050;font-size:11px;")
        lay.addWidget(self._error_lbl)

        cancel_btn = QPushButton("Abbrechen — im Free-Plan bleiben")
        cancel_btn.setStyleSheet(f"color:{_tc('#9CA3AF','#6B7280')};border:none;background:transparent;")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setFixedHeight(30)
        lay.addWidget(cancel_btn, alignment=Qt.AlignCenter)

    def _open_buy(self, plan_key: str):
        from semetra.infra.license import (
            STRIPE_MONTHLY_URL, STRIPE_HALFYEAR_URL, STRIPE_YEARLY_URL
        )
        urls = {
            "monthly":  STRIPE_MONTHLY_URL,
            "halfyear": STRIPE_HALFYEAR_URL,
            "yearly":   STRIPE_YEARLY_URL,
        }
        _open_url(urls.get(plan_key, STRIPE_MONTHLY_URL))

    def _activate(self):
        from semetra.infra.license import LicenseManager
        code = self._code_edit.text().strip()
        if not code:
            self._error_lbl.setText("Bitte einen Lizenzcode eingeben.")
            return
        lm = LicenseManager(self.repo)
        ok, msg = lm.activate(code)
        if ok:
            QMessageBox.information(
                self, "✅ Aktiviert!",
                "Semetra Pro wurde erfolgreich aktiviert.\n"
                "Danke für deine Unterstützung! 🎉"
            )
            self.accept()
        else:
            self._error_lbl.setText(f"❌ {msg}")


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


class FHDatabaseImportDialog(QDialog):
    """Import-Dialog für die eingebaute Offline-FH-Datenbank.
    Zeigt FH → Studiengang → Modulvorschau, importiert ausgewählte Module.
    Keine Online-Verbindung, keine Scraping-Risiken.
    """

    def __init__(self, repo: "SqliteRepo", parent=None):
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
        import json, pathlib
        db_path = pathlib.Path(__file__).parent / "fh_database.json"
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
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
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


class ResourceDialog(QDialog):
    """Dialog to add a study resource (video, book, tool, article, etc.) to a module."""

    TYPES = [
        ("youtube", "▶️  YouTube Video"),
        ("video",   "🎬  Video (anderes)"),
        ("book",    "📖  Buch / Lehrmittel"),
        ("article", "📄  Artikel / Blog"),
        ("doc",     "📚  Dokumentation"),
        ("tool",    "🔧  Tool / Programm"),
        ("web",     "🌐  Website"),
        ("other",   "🔗  Sonstiges"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowTitle("Ressource hinzufügen")
        self.setMinimumWidth(440)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        self.type_cb = QComboBox()
        for key, label in self.TYPES:
            self.type_cb.addItem(label, key)
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("z.B. Java Tutorial für Anfänger")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://...")

        form.addRow("Typ:", self.type_cb)
        form.addRow("Bezeichnung *:", self.label_edit)
        form.addRow("URL *:", self.url_edit)
        lay.addLayout(form)

        hint = QLabel(
            "💡 Tipp: YouTube, Bücher, Moodle-Kurse, Stack Overflow, GitHub, "
            "offizielle Docs — alles was beim Lernen hilft."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#706C86;font-size:11px;padding:4px 0;")
        lay.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _accept(self):
        label = self.label_edit.text().strip()
        url = self.url_edit.text().strip()
        if not label or not url:
            QMessageBox.warning(self, "Fehler", "Bezeichnung und URL sind Pflichtfelder.")
            return
        if not url.startswith("http"):
            url = "https://" + url
        self.accept()

    def get_values(self):
        return (
            self.type_cb.currentData(),
            self.label_edit.text().strip(),
            self.url_edit.text().strip() if self.url_edit.text().strip().startswith("http")
            else "https://" + self.url_edit.text().strip(),
        )


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
        if ModuleDialog(self.repo, parent=self).exec():
            self.refresh()
            if self._global_refresh:
                QTimer.singleShot(50, self._global_refresh)

    def _edit_module(self):
        if not self._selected_id:
            return
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
        if TaskDialog(self.repo, default_module_id=self._selected_id, parent=self).exec():
            self._show_detail(self._selected_id)

    def _import_fh_database(self):
        from semetra.infra.license import LicenseManager
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
        lm = LicenseManager(self.repo)
        if not lm.is_pro():
            if ProFeatureDialog("PDF / Datei Import", self.repo, parent=self).exec() != QDialog.Accepted:
                return
        if ScrapingImportDialog(self.repo, parent=self).exec():
            self.refresh()
            if self._global_refresh:
                QTimer.singleShot(50, self._global_refresh)


class TasksPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._current_detail_tid: Optional[int] = None
        self._build()

    def _build(self):
        _page_lay = QVBoxLayout(self)
        _page_lay.setContentsMargins(0, 0, 0, 0)
        _page_lay.setSpacing(0)
        _scroll_w = QWidget()
        _scroll_w.setAttribute(Qt.WA_StyledBackground, True)
        _page_lay.addWidget(make_scroll(_scroll_w))
        outer = QVBoxLayout(_scroll_w)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel(tr("page.tasks"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = QPushButton("+ Neue Aufgabe")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_task)
        hdr.addWidget(add_btn)
        outer.addLayout(hdr)

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
        frow.addWidget(QLabel("Priorität:"))
        frow.addWidget(self.prio_filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen...")
        self.search.textChanged.connect(self.refresh)
        frow.addWidget(self.search, 1)
        outer.addLayout(frow)

        # Splitter: table left | detail right
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        # splitter handle colour is set by the global QSS (QSplitter::handle)

        # Left: table + count/delete
        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(8)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Titel", "Modul", "Priorität", "Status", "Fällig", "ID"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnHidden(5, True)
        self.table.doubleClicked.connect(self._edit_task)
        self.table.currentCellChanged.connect(self._on_row_changed)
        left_lay.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.count_lbl = QLabel()
        self.count_lbl.setStyleSheet("color: #706C86; font-size: 12px;")
        bottom.addWidget(self.count_lbl)
        bottom.addStretch()
        del_btn = QPushButton("Gewählte löschen")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_task)
        bottom.addWidget(del_btn)
        left_lay.addLayout(bottom)
        splitter.addWidget(left_w)

        # Right: detail panel
        detail_w = QFrame()
        detail_w.setObjectName("Card")
        detail_lay = QVBoxLayout(detail_w)
        detail_lay.setContentsMargins(16, 14, 16, 14)
        detail_lay.setSpacing(10)

        self._det_placeholder = QLabel("← Aufgabe auswählen\nfür Details & Lerninhalt")
        self._det_placeholder.setAlignment(Qt.AlignCenter)
        self._det_placeholder.setStyleSheet("color:#706C86;font-size:13px;")
        self._det_placeholder.setWordWrap(True)
        detail_lay.addWidget(self._det_placeholder)

        self._det_content = QWidget()
        dc_lay = QVBoxLayout(self._det_content)
        dc_lay.setContentsMargins(0, 0, 0, 0)
        dc_lay.setSpacing(8)

        self._det_title = QLabel()
        self._det_title.setStyleSheet("font-size:14px;font-weight:bold;")
        self._det_title.setWordWrap(True)
        dc_lay.addWidget(self._det_title)

        self._det_meta = QLabel()
        self._det_meta.setStyleSheet("color:#706C86;font-size:12px;")
        dc_lay.addWidget(self._det_meta)

        # Quick status buttons
        sq_row = QHBoxLayout()
        sq_row.setSpacing(4)
        self._det_btn_open = QPushButton("⬜ Offen")
        self._det_btn_ip   = QPushButton("🔄 In Arbeit")
        self._det_btn_done = QPushButton("✅ Erledigt")
        for b in [self._det_btn_open, self._det_btn_ip, self._det_btn_done]:
            b.setObjectName("SecondaryBtn")
            b.setFixedHeight(28)
            sq_row.addWidget(b)
        sq_row.addStretch()
        self._det_btn_open.clicked.connect(lambda: self._quick_status("Open"))
        self._det_btn_ip.clicked.connect(lambda: self._quick_status("In Progress"))
        self._det_btn_done.clicked.connect(lambda: self._quick_status("Done"))
        dc_lay.addLayout(sq_row)

        dc_lay.addWidget(separator())

        notes_lbl = QLabel("📖 Lerninhalt:")
        notes_lbl.setStyleSheet("font-weight:bold;font-size:12px;color:#4A86E8;")
        dc_lay.addWidget(notes_lbl)

        self._det_notes = QTextEdit()
        self._det_notes.setObjectName("NotesArea")
        self._det_notes.setReadOnly(True)
        self._det_notes.setStyleSheet("font-size:12px;")
        dc_lay.addWidget(self._det_notes, 1)

        self._det_content.hide()
        detail_lay.addWidget(self._det_content)
        splitter.addWidget(detail_w)

        splitter.setSizes([720, 420])
        outer.addWidget(splitter, 1)

    def refresh(self):
        # Retranslate static labels
        self.table.setHorizontalHeaderLabels([
            tr("task.title"), tr("task.module"), tr("task.priority"),
            tr("task.status"), tr("task.due"), "ID"
        ])
        self.search.setPlaceholderText(tr("task.search"))

        # Build semester-filtered module list
        sem_f = _active_sem_filter(self.repo)
        mods_filtered = _filter_mods_by_sem(self.repo.list_modules("all"), sem_f)
        mod_ids_allowed = {m["id"] for m in mods_filtered}

        cur_mod = self.mod_filter.currentData()
        self.mod_filter.blockSignals(True)
        self.mod_filter.clear()
        self.mod_filter.addItem(tr("grade.all_modules"), None)
        for m in mods_filtered:
            self.mod_filter.addItem(m["name"], m["id"])
        if cur_mod and cur_mod in mod_ids_allowed:
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
            status="all" if st in ("Alle", "All") else st,
            priority="all" if pr in ("Alle", "All") else pr,
        )
        # Apply semester filter: keep only tasks whose module is in the filtered set
        if sem_f:
            tasks = [t for t in tasks if t["module_id"] in mod_ids_allowed]
        q = self.search.text().lower()
        if q:
            tasks = [t for t in tasks if q in t["title"].lower()]

        # Build exam-proximity map: module_id → days_until_exam
        _exam_proximity: dict[int, int] = {}
        for m in self.repo.all_exams():
            d = days_until(m["exam_date"])
            if d is not None and 0 <= d <= 10:
                _exam_proximity[m["id"]] = d

        # Sort: exam-urgent tasks first, then by due_date
        today_str_t = date.today().isoformat()
        def _task_sort_key(t):
            exam_d = _exam_proximity.get(t["module_id"], 999)
            due = t["due_date"] or "9999"
            overdue = 0 if due >= today_str_t else -1
            return (overdue, exam_d, due)
        tasks = sorted(tasks, key=_task_sort_key)

        self.table.setRowCount(len(tasks))
        for r, t in enumerate(tasks):
            exam_d = _exam_proximity.get(t["module_id"])
            # Title: append exam badge if close
            title_text = t["title"]
            if exam_d is not None:
                badge = "🔴" if exam_d <= 3 else "🟠"
                title_text += f"  {badge} Prüfung in {exam_d}d"
            title_item = QTableWidgetItem(title_text)
            if exam_d is not None and exam_d <= 3:
                title_item.setForeground(QColor("#DC2626"))
            elif exam_d is not None:
                title_item.setForeground(QColor("#D97706"))
            self.table.setItem(r, 0, title_item)
            mod_item = QTableWidgetItem(t["module_name"])
            mod_item.setForeground(QColor(mod_color(t["module_id"])))
            self.table.setItem(r, 1, mod_item)
            p_item = QTableWidgetItem(t["priority"])
            p_item.setForeground(QColor(PRIORITY_COLORS.get(t["priority"], "#333")))
            self.table.setItem(r, 2, p_item)
            self.table.setItem(r, 3, QTableWidgetItem(tr_status(t["status"])))
            due_str = t["due_date"] or "—"
            due_item = QTableWidgetItem(due_str)
            if due_str != "—" and due_str < today_str_t:
                due_item.setForeground(QColor("#DC2626"))
            self.table.setItem(r, 4, due_item)
            self.table.setItem(r, 5, QTableWidgetItem(str(t["id"])))
        n = len(tasks)
        self.count_lbl.setText(
            {"de": f"{n} Aufgabe(n)", "en": f"{n} task(s)",
             "fr": f"{n} tâche(s)", "it": f"{n} attività"}.get(_LANG, f"{n}")
        )

    def _on_row_changed(self, cur_row, cur_col, prev_row, prev_col):
        tid_item = self.table.item(cur_row, 5)
        if not tid_item:
            return
        tid = int(tid_item.text())
        self._current_detail_tid = tid
        task = self.repo.get_task(tid)
        if not task:
            return
        mod_item = self.table.item(cur_row, 1)
        mod_name = mod_item.text() if mod_item else ""
        title = task["title"]
        self._det_title.setText(title)
        self._det_meta.setText(
            f"📚 {mod_name}  ·  Status: {task['status']}  ·  Priorität: {task['priority']}"
        )
        notes = task["notes"] or ""
        if notes:
            lines = notes.split("\n")
            html = ['<div style="font-family:sans-serif;font-size:12px;line-height:1.6;">']
            for line in lines:
                line = line.strip()
                if not line:
                    html.append("<br>")
                elif line.startswith("•"):
                    html.append(f'<div style="padding:1px 0 1px 12px;">• {line[1:].strip()}</div>')
                elif line.startswith("📝") or line.startswith("📊"):
                    html.append(f'<div style="color:#4A86E8;font-weight:bold;margin-top:8px;">{line}</div>')
                elif line.startswith("ECTS:"):
                    html.append(f'<div style="color:#706C86;font-size:11px;margin-top:4px;">{line}</div>')
                else:
                    html.append(f'<div>{line}</div>')
            html.append("</div>")
            self._det_notes.setHtml("".join(html))
        else:
            self._det_notes.setPlainText("Keine Notizen vorhanden.")
        self._det_placeholder.hide()
        self._det_content.show()

    def _quick_status(self, status: str):
        if not self._current_detail_tid:
            return
        self.repo.update_task(self._current_detail_tid, status=status)
        self.refresh()

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
        if QMessageBox.question(self, "Löschen", "Aufgabe löschen?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_task(tid)
            self.refresh()


class EventDialog(QDialog):
    """Dialog to create a custom calendar event."""
    def __init__(self, repo: SqliteRepo, default_date: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
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


# ── Stress-Heatmap helpers ────────────────────────────────────────────────────

# Stress level → (light-bg, dark-bg, accent-color, label)
_STRESS_PALETTE = {
    0: (_tc("#EEF6EE", "#0D2010"), _tc("#EEF6EE", "#0D2010"), "#2CB67D", "Entspannt"),
    1: (_tc("#FFFBE6", "#2A2400"), _tc("#FFFBE6", "#2A2400"), "#D4A800", "Moderat"),
    2: (_tc("#FFF2E0", "#2A1200"), _tc("#FFF2E0", "#2A1200"), "#E07000", "Erhöht"),
    3: (_tc("#FFECEC", "#2A0808"), _tc("#FFECEC", "#2A0808"), "#CC2222", "Hoch"),
}


def _week_stress_data(repo, weeks: int = 12) -> list:
    """Return a list of dicts for the next `weeks` calendar weeks.

    Each dict:
        week_start  date
        week_end    date
        exams       int
        tasks       int
        level       int  0-3
        exam_names  list[str]
    """
    import calendar as _c
    today   = date.today()
    ws0     = today - timedelta(days=today.weekday())   # this Monday

    all_mods  = repo.list_modules("all")
    all_tasks = repo.list_tasks()

    result = []
    for i in range(weeks):
        ws = ws0 + timedelta(weeks=i)
        we = ws + timedelta(days=6)

        # Exams in this week (in-plan modules only)
        exam_names = []
        for m in all_mods:
            ip = int(m["in_plan"] or 1) if "in_plan" in m.keys() and m["in_plan"] is not None else 1
            if not ip:
                continue
            ex = m["exam_date"] or ""
            if not ex:
                continue
            try:
                d = date.fromisoformat(ex[:10])
                if ws <= d <= we:
                    exam_names.append(m["name"])
            except Exception:
                pass
        n_exams = len(exam_names)

        # Open tasks due this week
        n_tasks = 0
        for t in all_tasks:
            if t["status"] == "Done":
                continue
            dd = (t["due_date"] or "")
            if not dd:
                continue
            try:
                d = date.fromisoformat(dd[:10])
                if ws <= d <= we:
                    n_tasks += 1
            except Exception:
                pass

        # Stress level
        if n_exams >= 2:
            level = 3
        elif n_exams == 1:
            level = 2 if n_tasks >= 2 else 2
        elif n_tasks >= 5:
            level = 2
        elif n_tasks >= 2:
            level = 1
        else:
            level = 0

        result.append({
            "week_start": ws,
            "week_end":   we,
            "exams":      n_exams,
            "tasks":      n_tasks,
            "level":      level,
            "exam_names": exam_names,
        })
    return result


class WeekHeatmapWidget(QFrame):
    """Horizontal strip showing study-stress level for the next N weeks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WeekHeatmap")
        self.setStyleSheet(
            f"QFrame#WeekHeatmap{{background:{_tc('#FAFBFF','#1A1A2A')};"
            f"border:1px solid {_tc('#DDE3F0','#2A2A3A')};border-radius:8px;}}"
        )
        self._week_widgets: list = []
        self._build()

    def _build(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(12, 10, 12, 10)
        main.setSpacing(8)

        # ── Header row: title + legend ──────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        title_lbl = QLabel("📊\uFE0F  Wochen-Stresslevel")
        title_lbl.setStyleSheet(
            f"font-size:13px;font-weight:700;"
            f"color:{_tc('#1A1523','#EAE6F4')};"
        )
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        for level, (_, _, fg, label) in _STRESS_PALETTE.items():
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{fg};font-size:11px;padding:0;")
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"font-size:11px;font-weight:600;"
                f"color:{_tc('#6E6882','#8A849C')};padding:0;"
            )
            hdr.addWidget(dot)
            hdr.addWidget(lbl)
            hdr.addSpacing(6)
        main.addLayout(hdr)

        # ── Week blocks row ─────────────────────────────────────────────
        self._weeks_row = QHBoxLayout()
        self._weeks_row.setSpacing(3)
        self._weeks_row.setContentsMargins(0, 0, 0, 0)
        main.addLayout(self._weeks_row)

    def update_data(self, week_data: list):
        """Rebuild the week blocks from fresh data."""
        for w in self._week_widgets:
            w.deleteLater()
        self._week_widgets.clear()
        while self._weeks_row.count():
            self._weeks_row.takeAt(0)

        today = date.today()
        for wd in week_data:
            level = wd["level"]
            _, _, fg, _ = _STRESS_PALETTE[level]
            bg = _tc(
                ["#EEF6EE","#FFFBE6","#FFF2E0","#FFECEC"][level],
                ["#0D2010","#2A2400","#2A1200","#2A0808"][level],
            )
            is_current = wd["week_start"] <= today <= wd["week_end"]
            border = f"2px solid {fg}" if is_current else f"1px solid {fg}55"

            block = QFrame()
            block.setFixedSize(54, 56)
            block.setStyleSheet(
                f"background:{bg};border:{border};border-radius:8px;"
            )
            b_lay = QVBoxLayout(block)
            b_lay.setContentsMargins(3, 4, 3, 4)
            b_lay.setSpacing(1)

            # KW label
            kw = wd["week_start"].isocalendar()[1]
            kw_lbl = QLabel(f"KW{kw}")
            kw_lbl.setAlignment(Qt.AlignCenter)
            kw_lbl.setStyleSheet(
                f"font-size:11px;color:{fg};font-weight:800;background:transparent;"
            )
            b_lay.addWidget(kw_lbl)

            # Icon summary
            icons = ""
            if wd["exams"]:
                icons += f"🎯{wd['exams']}"
            if wd["tasks"]:
                icons += f" ✅{min(wd['tasks'], 9)}{'+'if wd['tasks']>9 else ''}"
            if icons:
                ico = QLabel(icons.strip())
                ico.setAlignment(Qt.AlignCenter)
                ico.setStyleSheet("font-size:10px;background:transparent;")
                b_lay.addWidget(ico)

            # Tooltip
            ws_s = wd["week_start"].strftime("%d.%m")
            we_s = wd["week_end"].strftime("%d.%m")
            tip  = [f"KW {kw}  ({ws_s} – {we_s})"]
            if wd["exams"]:
                names = ", ".join(wd["exam_names"][:3])
                if len(wd["exam_names"]) > 3:
                    names += "…"
                tip.append(f"🎯 {wd['exams']} Prüfung(en): {names}")
            if wd["tasks"]:
                tip.append(f"✅ {wd['tasks']} Aufgabe(n) fällig")
            if not wd["exams"] and not wd["tasks"]:
                tip.append("Keine Termine — freie Woche ✓")
            block.setToolTip("\n".join(tip))

            self._weeks_row.addWidget(block)
            self._week_widgets.append(block)

        self._weeks_row.addStretch()


class _CalCell(QFrame):
    """A single clickable day cell in the custom month calendar grid."""

    def __init__(self, page: "CalendarPage", parent=None):
        super().__init__(parent)
        self.setObjectName("cal_day_cell")
        self._page = page
        self._day_date: Optional[date] = None
        self.setMinimumHeight(68)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(1)
        self._day_lbl = QLabel()
        lay.addWidget(self._day_lbl)
        self._ev_lay = QVBoxLayout()
        self._ev_lay.setSpacing(1)
        self._ev_lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self._ev_lay)
        lay.addStretch()
        self._apply_style(empty=True, is_selected=False)

    def set_day(self, d: Optional[date], events: list, is_today: bool, is_selected: bool,
                stress_level: int = 0):
        self._day_date = d
        self._stress_level = stress_level
        # Clear old event labels
        while self._ev_lay.count():
            item = self._ev_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if d is None:
            self._day_lbl.setText("")
            self._apply_style(empty=True, is_selected=False, stress_level=0)
            self.setCursor(Qt.ArrowCursor)
            return
        self.setCursor(Qt.PointingHandCursor)
        # Day number
        if is_today:
            self._day_lbl.setStyleSheet(
                "font-size:13px;font-weight:800;color:#FFFFFF;"
                "background:#7C3AED;border-radius:10px;padding:1px 7px;"
            )
        else:
            self._day_lbl.setStyleSheet(
                f"font-size:13px;font-weight:700;"
                f"color:{_tc('#1A1523','#EAE6F4')};background:transparent;"
            )
        self._day_lbl.setText(str(d.day))
        self._apply_style(empty=False, is_selected=is_selected, stress_level=stress_level)
        # Event blocks — max 2 visible + overflow label
        MAX_VISIBLE = 2
        for icon, title, color in events[:MAX_VISIBLE]:
            ev_lbl = QLabel(f"{icon} {title}")
            ev_lbl.setWordWrap(False)
            ev_lbl.setMaximumHeight(17)
            ev_lbl.setStyleSheet(
                f"background:{color}28;color:{color};border-radius:4px;"
                f"padding:1px 5px;font-size:11px;font-weight:700;"
            )
            self._ev_lay.addWidget(ev_lbl)
        if len(events) > MAX_VISIBLE:
            more = QLabel(f"+{len(events) - MAX_VISIBLE} mehr")
            more.setStyleSheet(
                f"font-size:11px;font-weight:600;"
                f"color:{_tc('#6E6882','#8A849C')};background:transparent;"
            )
            self._ev_lay.addWidget(more)

    def _apply_style(self, empty: bool, is_selected: bool, stress_level: int = 0):
        if empty:
            bg     = _tc("#F4F4F6", "#16162A")
            border = _tc("#E4E4E8", "#22223A")
        elif is_selected:
            bg     = _tc("#EEF3FF", "#1E2D4A")
            border = "#4A86E8"
        else:
            # Stress tint — subtle background color based on week load
            _stress_bg_light = ["#FFFFFF", "#FFFEF0", "#FFF5E8", "#FFF0EE"]
            _stress_bg_dark  = ["#1E2030", "#1E1E18", "#1E1810", "#1E1010"]
            bg     = _tc(_stress_bg_light[min(stress_level, 3)],
                         _stress_bg_dark[min(stress_level, 3)])
            border = _tc("#E4E4E8", "#2A2A3A")
        self.setStyleSheet(
            f"QFrame#cal_day_cell{{background:{bg};border:1px solid {border};border-radius:4px;}}"
            f"QLabel{{background:transparent;}}"
        )

    def mousePressEvent(self, event):
        if self._day_date is not None:
            self._page._on_cell_clicked(self._day_date)
        super().mousePressEvent(event)


class CalendarPage(QWidget):
    _MONTH_NAMES = ["Januar","Februar","März","April","Mai","Juni",
                    "Juli","August","September","Oktober","November","Dezember"]
    _DAY_NAMES   = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        today = date.today()
        self._cur_year  = today.year
        self._cur_month = today.month
        self._selected_date = today
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(20)

        # ── Left: custom calendar grid ───────────────────────────────────────
        left = QVBoxLayout()

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

        # Month navigation bar
        nav = QHBoxLayout()
        prev_btn = QPushButton("‹")
        prev_btn.setFixedSize(28, 28)
        prev_btn.clicked.connect(self._prev_month)
        self._month_lbl = QLabel()
        self._month_lbl.setAlignment(Qt.AlignCenter)
        self._month_lbl.setStyleSheet("font-weight:700;font-size:14px;")
        next_btn = QPushButton("›")
        next_btn.setFixedSize(28, 28)
        next_btn.clicked.connect(self._next_month)
        today_btn = QPushButton("Heute")
        today_btn.clicked.connect(self._go_today)
        nav.addWidget(prev_btn)
        nav.addWidget(self._month_lbl, 1)
        nav.addWidget(next_btn)
        nav.addSpacing(10)
        nav.addWidget(today_btn)
        left.addLayout(nav)

        # Weekday header + cell grid in one container
        grid_w = QWidget()
        grid_w.setAttribute(Qt.WA_StyledBackground, True)
        grid_outer = QVBoxLayout(grid_w)
        grid_outer.setContentsMargins(0, 4, 0, 0)
        grid_outer.setSpacing(4)

        day_hdr = QHBoxLayout()
        day_hdr.setSpacing(2)
        for name in ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]:
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedHeight(22)
            lbl.setStyleSheet(
                f"font-size:11px;font-weight:700;color:{_tc('#706C86','#6B7280')};"
            )
            day_hdr.addWidget(lbl, 1)
        grid_outer.addLayout(day_hdr)

        self._grid_lay = QGridLayout()
        self._grid_lay.setSpacing(2)
        self._grid_lay.setContentsMargins(0, 0, 0, 0)
        # Equal column + row stretching so all cells are the same size
        for col in range(7):
            self._grid_lay.setColumnStretch(col, 1)
        for row in range(6):
            self._grid_lay.setRowStretch(row, 1)
        self._cells: list = []
        for row in range(6):
            row_cells = []
            for col in range(7):
                cell = _CalCell(self)
                cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self._grid_lay.addWidget(cell, row, col)
                row_cells.append(cell)
            self._cells.append(row_cells)
        grid_outer.addLayout(self._grid_lay)

        left.addWidget(grid_w, 1)
        lay.addLayout(left, 3)

        # ── Right: day detail + upcoming ─────────────────────────────────────
        right = QVBoxLayout()
        day_hdr2 = QHBoxLayout()
        self.day_title = QLabel("Heute")
        self.day_title.setObjectName("SectionTitle")
        day_hdr2.addWidget(self.day_title)
        day_hdr2.addStretch()
        del_ev_btn = QPushButton("Ereignis löschen")
        del_ev_btn.setObjectName("DangerBtn")
        del_ev_btn.clicked.connect(self._delete_selected_event)
        day_hdr2.addWidget(del_ev_btn)
        right.addLayout(day_hdr2)

        self.day_list = QListWidget()
        self.day_list.setFixedHeight(200)
        right.addWidget(self.day_list)

        # ── Stress-Heatmap ───────────────────────────────────────────────
        self._heatmap = WeekHeatmapWidget()
        right.addWidget(self._heatmap)

        self._upcoming_lbl = QLabel(tr("sec.upcoming"))
        self._upcoming_lbl.setObjectName("SectionTitle")
        right.addWidget(self._upcoming_lbl)
        self.upcoming_list = QListWidget()
        right.addWidget(self.upcoming_list, 1)
        lay.addLayout(right, 2)

    # ── Navigation ───────────────────────────────────────────────────────────

    def _prev_month(self):
        if self._cur_month == 1:
            self._cur_month, self._cur_year = 12, self._cur_year - 1
        else:
            self._cur_month -= 1
        self.refresh()

    def _next_month(self):
        if self._cur_month == 12:
            self._cur_month, self._cur_year = 1, self._cur_year + 1
        else:
            self._cur_month += 1
        self.refresh()

    def _go_today(self):
        today = date.today()
        self._cur_year, self._cur_month = today.year, today.month
        self._selected_date = today
        self.refresh()

    def _on_cell_clicked(self, d: date):
        self._selected_date = d
        self._rebuild_grid()
        self._on_date_selected()

    # ── Data helpers ─────────────────────────────────────────────────────────

    def _events_for_month(self) -> dict:
        """Return {date: [(icon, title, color)]} for the currently displayed month."""
        y, m = self._cur_year, self._cur_month
        result: dict = {}

        for ev in self.repo.list_events():
            try:
                d = datetime.strptime(ev["start_date"], "%Y-%m-%d").date()
                if d.year == y and d.month == m:
                    icon = {"lecture":"📖","exercise":"✏️","study":"📚",
                            "exam":"🎯","custom":"📌"}.get(ev["kind"], "📌")
                    result.setdefault(d, []).append((icon, ev["title"], "#2CB67D"))
            except Exception:
                pass

        for t in self.repo.list_tasks():
            if t["due_date"] and t["status"] != "Done":
                try:
                    d = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
                    if d.year == y and d.month == m:
                        color = PRIORITY_COLORS.get(t["priority"], "#FF8C42")
                        result.setdefault(d, []).append(("✅", t["title"], color))
                except Exception:
                    pass

        for mod in self.repo.list_modules("all"):
            if mod["exam_date"]:
                try:
                    d = datetime.strptime(mod["exam_date"], "%Y-%m-%d").date()
                    if d.year == y and d.month == m:
                        result.setdefault(d, []).append(("🎯", mod["name"], "#F44336"))
                except Exception:
                    pass

        return result

    # ── Grid rendering ───────────────────────────────────────────────────────

    def _rebuild_grid(self):
        import calendar as _cal
        y, m = self._cur_year, self._cur_month
        self._month_lbl.setText(f"{self._MONTH_NAMES[m - 1]} {y}")
        today = date.today()
        ev_map = self._events_for_month()

        # Build a day → stress_level map from this month's week data
        # Use the cached _stress_by_week if available, else recompute
        day_stress: dict = {}
        for wd in getattr(self, "_stress_weeks", []):
            lvl = wd["level"]
            ws, we = wd["week_start"], wd["week_end"]
            d_iter = ws
            while d_iter <= we:
                if d_iter.year == y and d_iter.month == m:
                    day_stress[d_iter] = lvl
                d_iter += timedelta(days=1)

        weeks = _cal.monthcalendar(y, m)
        while len(weeks) < 6:
            weeks.append([0] * 7)
        for row, week in enumerate(weeks):
            for col, day_num in enumerate(week):
                cell = self._cells[row][col]
                if day_num == 0:
                    cell.set_day(None, [], False, False, stress_level=0)
                else:
                    d = date(y, m, day_num)
                    cell.set_day(d, ev_map.get(d, []), d == today, d == self._selected_date,
                                 stress_level=day_stress.get(d, 0))

    # ── Actions ──────────────────────────────────────────────────────────────

    def _add_event(self):
        default_date = self._selected_date.strftime("%Y-%m-%d")
        if EventDialog(self.repo, default_date=default_date, parent=self).exec():
            self.refresh()

    def _delete_selected_event(self):
        item = self.day_list.currentItem()
        if not item:
            return
        eid = item.data(Qt.UserRole)
        if eid is None or eid < 0:
            QMessageBox.information(self, "Hinweis",
                "Aufgaben und Prüfungen können nur in den jeweiligen Tabs gelöscht werden.")
            return
        if QMessageBox.question(self, "Löschen", "Ereignis löschen?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_event(eid)
            self.refresh()

    def _on_date_selected(self):
        d = self._selected_date
        d_str = d.strftime("%Y-%m-%d")
        self.day_title.setText(
            f"{self._DAY_NAMES[d.weekday()]}, {d.day}. {self._MONTH_NAMES[d.month - 1]} {d.year}"
        )
        self.day_list.clear()

        for ev in self.repo.list_events():
            if ev["start_date"] <= d_str <= (ev["end_date"] or ev["start_date"]):
                kind_icon = {"lecture":"📖","exercise":"✏️","study":"📚",
                             "exam":"🎯","custom":"📌"}.get(ev["kind"], "📌")
                mod_str  = f" ({ev['module_name']})" if ev["module_name"] else ""
                time_str = f" {ev['start_time']}" if ev["start_time"] else ""
                item = QListWidgetItem(f"{kind_icon} {ev['title']}{mod_str}{time_str}")
                item.setData(Qt.UserRole, ev["id"])
                item.setForeground(QColor("#2CB67D"))
                self.day_list.addItem(item)

        for t in self.repo.list_tasks():
            if t["due_date"] == d_str:
                color = PRIORITY_COLORS.get(t["priority"], "#333")
                item = QListWidgetItem(f"✅ Aufgabe: {t['title']} ({t['module_name']})")
                item.setData(Qt.UserRole, -1)
                item.setForeground(QColor(color))
                self.day_list.addItem(item)

        for mod in self.repo.list_modules("all"):
            if mod["exam_date"] == d_str:
                item = QListWidgetItem(f"🎯 PRÜFUNG: {mod['name']}")
                item.setData(Qt.UserRole, -1)
                item.setForeground(QColor("#F44336"))
                self.day_list.addItem(item)

        if not self.day_list.count():
            self.day_list.addItem("Keine Einträge für diesen Tag")

    def _load_upcoming(self):
        self.upcoming_list.clear()
        today = date.today()
        items = []
        for ev in self.repo.list_events():
            try:
                d = datetime.strptime(ev["start_date"], "%Y-%m-%d").date()
                delta = (d - today).days
                if 0 <= delta <= 14:
                    mod_str = f" ({ev['module_name']})" if ev["module_name"] else ""
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
        for mod in self.repo.all_exams():
            try:
                d = datetime.strptime(mod["exam_date"], "%Y-%m-%d").date()
                delta = (d - today).days
                if 0 <= delta <= 14:
                    items.append((delta, f"🎯 Prüfung: {mod['name']} — in {delta} Tag(en)"))
            except Exception:
                pass
        items.sort(key=lambda x: x[0])
        for _, text in items:
            self.upcoming_list.addItem(text)
        if not items:
            self.upcoming_list.addItem("Keine Einträge in den nächsten 14 Tagen")

    def refresh(self):
        self._upcoming_lbl.setText(tr("sec.upcoming"))
        # Compute stress data once, cache for grid coloring + heatmap strip
        self._stress_weeks = _week_stress_data(self.repo, weeks=12)
        self._heatmap.update_data(self._stress_weeks)
        self._rebuild_grid()
        self._on_date_selected()
        self._load_upcoming()


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
                                  "title": f"Prüfung: {m['name']}", "sub": m["semester"],
                                  "color": mod_color(m["id"])})
            except Exception:
                pass

        items.sort(key=lambda x: x["date"])

        if not items:
            lbl = QLabel("Keine Fristen im gewahlten Zeitraum.")
            lbl.setStyleSheet("color: #706C86; font-size: 14px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.scroll_lay.addWidget(lbl)
        else:
            last_date = None
            for item in items:
                if item["date"] != last_date:
                    delta = item["delta"]
                    if delta == 0:
                        ds = tr("sec.today")
                    elif delta == 1:
                        ds = {"de":"Morgen","en":"Tomorrow","fr":"Demain","it":"Domani"}.get(_LANG,"Tomorrow")
                    elif delta < 0:
                        over = {"de":"überfällig","en":"overdue","fr":"en retard","it":"scaduto"}.get(_LANG,"overdue")
                        ds = f"{item['date'].strftime('%d. %b')} ({over})"
                    else:
                        ds = item["date"].strftime("%A, %d. %B %Y")
                    h = QLabel(ds)
                    h.setStyleSheet("font-weight: bold; color: #706C86; font-size: 12px; padding-top: 8px;")
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

        icon = "Prüfung" if item["type"] == "exam" else "Aufgabe"
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        tl = QLabel(item["title"])
        tl.setStyleSheet("font-weight: bold; font-size: 13px;")
        text_col.addWidget(tl)
        sl = QLabel(f"{icon}  |  {item['sub']}")
        sl.setStyleSheet("color: #706C86; font-size: 11px;")
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


# ── StudyPlanPage ─────────────────────────────────────────────────────────

class StudyPlanPage(QWidget):
    """Der Fels in der Brandung – vollständige Studienübersicht mit Semester-Roadmap."""

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._selected_mid: Optional[int] = None
        self._task_filter = "all"
        self._current_detail_task_id: Optional[int] = None
        self._dashboard = None  # set by MainWindow after construction
        self._build()

    def set_dashboard(self, dashboard) -> None:
        """Give StudyPlanPage a reference to DashboardPage for live updates."""
        self._dashboard = dashboard

    def _refresh_dashboard(self) -> None:
        """Refresh the dashboard if a reference is available."""
        if self._dashboard is not None and hasattr(self._dashboard, "refresh"):
            self._dashboard.refresh()

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        # splitter handle colour is set by the global QSS (QSplitter::handle)

        # ── Left: Semester overview ─────────────────────────────────────
        left_w = QWidget()
        left_w.setAttribute(Qt.WA_StyledBackground, True)
        left_w.setMinimumWidth(320)   # keep semester list readable
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(24, 20, 16, 20)
        left_lay.setSpacing(14)

        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Studienplan")
        title.setObjectName("PageTitle")
        title_col.addWidget(title)
        subtitle_lbl = QLabel()
        subtitle_lbl.setObjectName("StudienplanSubtitle")
        subtitle_lbl.setStyleSheet("color:#7C3AED;font-size:12px;font-weight:600;")
        # Will be populated in refresh()
        self._studienplan_subtitle = subtitle_lbl
        title_col.addWidget(subtitle_lbl)
        hdr.addLayout(title_col)
        hdr.addStretch()
        web_import_btn = QPushButton("📄 PDF Import")
        web_import_btn.setObjectName("SecondaryBtn")
        web_import_btn.setFixedHeight(32)
        web_import_btn.setToolTip("Modulplan der FH als PDF importieren")
        web_import_btn.clicked.connect(self._open_web_import)
        web_import_btn.setStyleSheet(
            "QPushButton{font-size:12px;padding:5px 14px;border-radius:9px;}"
        )
        hdr.addWidget(web_import_btn)
        left_lay.addLayout(hdr)

        # Overall stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self.stat_ects = StatCard("ECTS Gesamt", "0 / 0", "", "#4A86E8")
        self.stat_tasks = StatCard("Aufgaben erledigt", "0%", "", "#2CB67D")
        self.stat_mods = StatCard("Module abgeschlossen", "0 / 0", "", "#FF8C42")
        for c in [self.stat_ects, self.stat_tasks, self.stat_mods]:
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            stats_row.addWidget(c)
        left_lay.addLayout(stats_row)

        # Scrollable semester blocks
        self._sem_container = QWidget()
        self._sem_lay = QVBoxLayout(self._sem_container)
        self._sem_lay.setSpacing(12)
        self._sem_lay.setContentsMargins(0, 0, 8, 0)
        left_lay.addWidget(make_scroll(self._sem_container), 1)

        splitter.addWidget(left_w)

        # ── Right: Module + Task detail ──────────────────────────────────
        right_w = QWidget()
        right_w.setAttribute(Qt.WA_StyledBackground, True)
        right_w.setMinimumWidth(180)   # allow narrow resizing
        self._right_lay = QVBoxLayout(right_w)
        self._right_lay.setContentsMargins(16, 20, 24, 20)
        self._right_lay.setSpacing(10)

        self._right_placeholder = QLabel("← Modul auswählen\nfür den Lernplan")
        self._right_placeholder.setAlignment(Qt.AlignCenter)
        self._right_placeholder.setStyleSheet("color:#706C86;font-size:14px;")
        self._right_placeholder.setWordWrap(True)
        self._right_lay.addWidget(self._right_placeholder)

        # Module detail (hidden until selected)
        self._right_detail = QWidget()
        rd_lay = QVBoxLayout(self._right_detail)
        rd_lay.setContentsMargins(0, 0, 0, 0)
        rd_lay.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self._rd_title = QLabel()
        self._rd_title.setStyleSheet("font-size:16px;font-weight:bold;")
        self._rd_title.setWordWrap(True)
        title_row.addWidget(self._rd_title, 1)
        # Compact icon buttons to save horizontal space
        self._rd_plan_btn = QToolButton()
        self._rd_plan_btn.setText("⊘")
        self._rd_plan_btn.setToolTip("Modul ausschließen / einschließen")
        self._rd_plan_btn.setFixedSize(30, 30)
        self._rd_plan_btn.setCursor(Qt.PointingHandCursor)
        self._rd_plan_btn.clicked.connect(self._toggle_plan_from_detail)
        title_row.addWidget(self._rd_plan_btn)
        self._rd_edit_btn = QToolButton()
        self._rd_edit_btn.setText("✏")
        self._rd_edit_btn.setToolTip("Modul bearbeiten")
        self._rd_edit_btn.setFixedSize(30, 30)
        self._rd_edit_btn.setCursor(Qt.PointingHandCursor)
        self._rd_edit_btn.clicked.connect(self._edit_selected_module)
        title_row.addWidget(self._rd_edit_btn)
        rd_lay.addLayout(title_row)

        self._rd_info = QLabel()
        self._rd_info.setStyleSheet("color:#706C86;font-size:12px;")
        rd_lay.addWidget(self._rd_info)

        # ── Readiness Card ─────────────────────────────────────────────────
        self._rd_readiness = QFrame()
        self._rd_readiness.setObjectName("ReadinessCard")
        self._rd_readiness.setStyleSheet(
            f"QFrame#ReadinessCard{{background:{_tc('#F4F7FF','#252535')};"
            f"border:1px solid {_tc('#DDE3F0','#383850')};border-radius:8px;"
            f"padding:0px;}}"
        )
        rc_lay = QHBoxLayout(self._rd_readiness)
        rc_lay.setContentsMargins(10, 8, 10, 8)
        rc_lay.setSpacing(10)

        # Left: big score circle
        self._rc_score_lbl = QLabel("–")
        self._rc_score_lbl.setFixedSize(44, 44)
        self._rc_score_lbl.setAlignment(Qt.AlignCenter)
        self._rc_score_lbl.setStyleSheet(
            "font-size:16px;font-weight:bold;color:#706C86;"
            "background:#E0E4F0;border-radius:22px;border:none;"
        )
        rc_lay.addWidget(self._rc_score_lbl)

        # Middle: label + component breakdown
        rc_mid = QVBoxLayout()
        rc_mid.setSpacing(2)
        rc_title = QLabel("Prüfungsbereitschaft")
        rc_title.setStyleSheet(f"font-size:11px;font-weight:600;color:{_tc('#4A5A8A','#89B4FA')};")
        rc_mid.addWidget(rc_title)
        self._rc_components = QLabel("Noch keine Lerndaten erfasst")
        self._rc_components.setStyleSheet("font-size:10px;color:#706C86;")
        self._rc_components.setWordWrap(True)
        rc_mid.addWidget(self._rc_components)
        rc_lay.addLayout(rc_mid, 1)

        # Right: exam countdown
        self._rc_exam_lbl = QLabel("")
        self._rc_exam_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._rc_exam_lbl.setStyleSheet("font-size:10px;color:#706C86;")
        self._rc_exam_lbl.setWordWrap(True)
        self._rc_exam_lbl.setFixedWidth(70)
        rc_lay.addWidget(self._rc_exam_lbl)

        rd_lay.addWidget(self._rd_readiness)

        prog_row = QHBoxLayout()
        self._rd_bar = QProgressBar()
        self._rd_bar.setFixedHeight(8)
        self._rd_bar.setTextVisible(False)
        prog_row.addWidget(self._rd_bar, 1)
        self._rd_prog_lbl = QLabel("0/0")
        self._rd_prog_lbl.setStyleSheet("color:#706C86;font-size:12px;")
        prog_row.addWidget(self._rd_prog_lbl)
        rd_lay.addLayout(prog_row)

        rd_lay.addWidget(separator())

        # ── Tab buttons ───────────────────────────────────────────────────
        tab_row = QHBoxLayout()
        tab_row.setSpacing(3)
        tab_row.setContentsMargins(0, 0, 0, 0)
        self._tab_btns: Dict[str, QPushButton] = {}
        tab_defs = [
            ("tasks",       "📋 Aufgaben"),
            ("objectives",  "🎯 Lernziele"),
            ("content",     "📚 Lerninhalte"),
            ("exams",       "📝 Prüfungen"),
        ]
        for key, label in tab_defs:
            btn = QPushButton(label)
            btn.setObjectName("SecondaryBtn")
            btn.setFixedHeight(28)
            btn.setMinimumWidth(0)          # allow shrinking
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet(
                "QPushButton{font-size:11px;padding:4px 6px;}"
                "QPushButton:checked{font-weight:bold;}"
            )
            btn.clicked.connect(lambda checked=False, k=key: self._set_right_tab(k))
            tab_row.addWidget(btn)
            self._tab_btns[key] = btn
        rd_lay.addLayout(tab_row)

        # ── Stacked content area ──────────────────────────────────────────
        self._right_stack = QStackedWidget()
        rd_lay.addWidget(self._right_stack, 1)

        # Page 0 – Tasks
        tasks_page = QWidget()
        tp_lay = QVBoxLayout(tasks_page)
        tp_lay.setContentsMargins(0, 0, 0, 0)
        tp_lay.setSpacing(6)

        self._task_list = QListWidget()
        self._task_list.setSpacing(2)
        self._task_list.currentItemChanged.connect(self._on_task_selected)
        tp_lay.addWidget(self._task_list, 1)

        td_grp = QGroupBox("Aufgabe")
        td_lay = QVBoxLayout(td_grp)
        td_lay.setSpacing(6)
        status_row = QHBoxLayout()
        status_row.setSpacing(4)
        self._btn_open = QPushButton("Offen")
        self._btn_ip   = QPushButton("In Arbeit")
        self._btn_done = QPushButton("✓ Erledigt")
        for b in [self._btn_open, self._btn_ip, self._btn_done]:
            b.setObjectName("SecondaryBtn")
            b.setFixedHeight(26)
            status_row.addWidget(b)
        status_row.addStretch()
        self._btn_open.clicked.connect(lambda: self._set_task_status("Open"))
        self._btn_ip.clicked.connect(lambda: self._set_task_status("In Progress"))
        self._btn_done.clicked.connect(lambda: self._set_task_status("Done"))
        td_lay.addLayout(status_row)
        self._task_notes = QTextEdit()
        self._task_notes.setReadOnly(True)
        self._task_notes.setFixedHeight(140)
        td_lay.addWidget(self._task_notes)
        tp_lay.addWidget(td_grp)
        self._right_stack.addWidget(tasks_page)          # index 0

        # ── Helper: build a tab page with a fixed toolbar + scrollable body ──
        def _make_tab_page(add_label, add_slot):
            outer = QWidget()
            outer.setAttribute(Qt.WA_StyledBackground, True)
            vlay = QVBoxLayout(outer)
            vlay.setContentsMargins(0, 4, 0, 0)
            vlay.setSpacing(4)
            tb = QHBoxLayout()
            tb.setSpacing(4)
            add_btn = QPushButton(add_label)
            add_btn.setObjectName("SecondaryBtn")
            add_btn.setFixedHeight(26)
            add_btn.clicked.connect(add_slot)
            tb.addWidget(add_btn)
            imp_btn = QPushButton("📄 PDF importieren")
            imp_btn.setObjectName("SecondaryBtn")
            imp_btn.setFixedHeight(26)
            imp_btn.clicked.connect(self._quick_import)
            tb.addWidget(imp_btn)
            tb.addStretch()
            vlay.addLayout(tb)
            body = QWidget()
            body.setAttribute(Qt.WA_StyledBackground, True)
            body_lay = QVBoxLayout(body)
            body_lay.setContentsMargins(0, 0, 0, 0)
            body_lay.setSpacing(6)
            vlay.addWidget(make_scroll(body), 1)
            return outer, body_lay

        # Page 1 – Objectives (Lernziele)
        _obj_page, self._obj_lay = _make_tab_page(
            "+ Lernziel",
            lambda: self._add_obj_manual(self._selected_mid)
        )
        self._right_stack.addWidget(_obj_page)   # index 1

        # Page 2 – Content sections (Lerninhalte)
        _cont_page, self._cont_lay = _make_tab_page(
            "+ Lerninhalt",
            lambda: self._add_content_manual(self._selected_mid)
        )
        self._right_stack.addWidget(_cont_page)  # index 2

        # Page 3 – Assessments (Prüfungen & Gewichtung)
        _exam_page, self._exam_lay = _make_tab_page(
            "+ Prüfung",
            lambda: self._add_pruefung_manual(self._selected_mid)
        )
        self._right_stack.addWidget(_exam_page)  # index 3

        self._right_detail.hide()
        self._right_lay.addWidget(self._right_detail)

        splitter.addWidget(right_w)
        splitter.setSizes([600, 400])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setCollapsible(0, False)   # left panel never collapses
        splitter.setCollapsible(1, True)    # right panel can fully collapse
        self._splitter = splitter
        outer.addWidget(splitter)

    def _open_web_import(self):
        """Open the Web Import (KI-Scraper) dialog — Pro feature."""
        from semetra.infra.license import LicenseManager
        lm = LicenseManager(self.repo)
        if not lm.is_pro():
            if ProFeatureDialog("Web Import", self.repo, parent=self).exec() != QDialog.Accepted:
                return
        dlg = WebImportDialog(self.repo, parent=self)
        if dlg.exec():
            self._update_global_stats()
            self._rebuild_semesters()
            if self._dashboard is not None and hasattr(self._dashboard, "refresh"):
                self._dashboard.refresh()

    def _quick_import(self):
        """Open the Scraping Import dialog directly from the detail panel (Pro only)."""
        from semetra.infra.license import LicenseManager
        lm = LicenseManager(self.repo)
        if not lm.is_pro():
            if ProFeatureDialog("PDF / Datei Import", self.repo, parent=self).exec() != QDialog.Accepted:
                return
        dlg = ScrapingImportDialog(self.repo, parent=self)
        if dlg.exec():
            self.refresh()

    def _toggle_plan_from_detail(self):
        """Toggle in_plan for the currently selected module from the detail panel."""
        if not self._selected_mid:
            return
        m = self.repo.get_module(self._selected_mid)
        if not m:
            return
        cur = (int(m["in_plan"]) if m["in_plan"] is not None else 1) if "in_plan" in m.keys() else 1
        self.repo.update_module(self._selected_mid, in_plan=(0 if cur else 1))
        self._update_global_stats()
        self._populate_detail(self._selected_mid)
        self._rebuild_semesters()
        self._refresh_dashboard()

    def _edit_selected_module(self):
        """Open the ModuleDialog for the currently selected module."""
        if not self._selected_mid:
            return
        if ModuleDialog(self.repo, self._selected_mid, parent=self).exec():
            self._populate_detail(self._selected_mid)
            self._rebuild_semesters()
            self._update_global_stats()
            self._refresh_dashboard()

    def _set_right_tab(self, key: str):
        self._task_filter = key
        idx_map = {"tasks": 0, "objectives": 1, "content": 2, "exams": 3}
        self._right_stack.setCurrentIndex(idx_map.get(key, 0))
        # Highlight active tab
        for k, btn in self._tab_btns.items():
            btn.setProperty("active", k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if self._selected_mid:
            self._populate_detail(self._selected_mid)

    def refresh(self):
        self._rebuild_semesters()
        self._update_global_stats()
        if self._selected_mid:
            self._populate_detail(self._selected_mid)
        # Update subtitle with FH/Studiengang from settings
        try:
            fh_name = self.repo.get_setting("fh_name") or ""
            studiengang = self.repo.get_setting("studiengang") or ""
            if fh_name and studiengang:
                self._studienplan_subtitle.setText(
                    f"✨ Automatisch generiert · {fh_name} – {studiengang}"
                )
            elif fh_name:
                self._studienplan_subtitle.setText(
                    f"✨ Automatisch generiert · {fh_name}"
                )
            else:
                self._studienplan_subtitle.setText(
                    "✨ Automatisch generiert aus deiner Fachhochschule"
                )
        except Exception:
            pass

    def _update_global_stats(self):
        modules = self.repo.list_modules("all")
        # Only count modules that are active in the plan
        plan_mods = [m for m in modules if (int(m["in_plan"]) if "in_plan" in m.keys() and m["in_plan"] is not None else 1)]
        total_ects = sum(float(m["ects"]) for m in plan_mods)
        done_ects  = sum(float(m["ects"]) for m in plan_mods if m["status"] == "completed")
        completed  = sum(1 for m in plan_mods if m["status"] == "completed")
        all_tasks  = self.repo.list_tasks()
        done_tasks = sum(1 for t in all_tasks if t["status"] == "Done")
        total_tasks = len(all_tasks)
        pct = int(done_tasks / total_tasks * 100) if total_tasks > 0 else 0
        self.stat_ects.set_value(f"{int(done_ects)} / {int(total_ects)}")
        self.stat_tasks.set_value(f"{pct}%")
        self.stat_mods.set_value(f"{completed} / {len(plan_mods)}")

    def _rebuild_semesters(self):
        while self._sem_lay.count():
            item = self._sem_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                pass

        modules = self.repo.list_modules("all")
        tasks_by_mod: Dict[int, Dict] = {}
        for t in self.repo.list_tasks():
            mid = t["module_id"]
            if mid not in tasks_by_mod:
                tasks_by_mod[mid] = {"total": 0, "done": 0}
            tasks_by_mod[mid]["total"] += 1
            if t["status"] == "Done":
                tasks_by_mod[mid]["done"] += 1

        by_sem: Dict[str, List] = {}
        for m in modules:
            by_sem.setdefault(str(m["semester"]), []).append(m)

        def _sem_sort_key(s: str) -> int:
            return int(s) if s.isdigit() else (999 if s == "" else 998)

        def _sem_display(s: str) -> str:
            if s.isdigit():
                return f"{s}. Semester"
            elif s == "":
                return "Semester (nicht zugeordnet)"
            else:
                # Raw PDF tag like "FS26" – show it, but suggest editing
                return f"Semester  ·  {s}"

        for sem in sorted(by_sem.keys(), key=_sem_sort_key):
            mods = by_sem[sem]
            # Only count active (in-plan) modules for ECTS and progress totals
            active_mods = [m for m in mods if (int(m["in_plan"]) if "in_plan" in m.keys() and m["in_plan"] is not None else 1)]
            sem_ects = sum(float(m["ects"]) for m in active_mods)
            sem_done_ects = sum(float(m["ects"]) for m in active_mods if m["status"] == "completed")
            sem_total = sum(tasks_by_mod.get(m["id"], {}).get("total", 0) for m in active_mods)
            sem_done  = sum(tasks_by_mod.get(m["id"], {}).get("done",  0) for m in active_mods)
            sem_pct = int(sem_done / sem_total * 100) if sem_total > 0 else 0

            # Determine semester status color (based on active modules only)
            all_done = bool(active_mods) and all(m["status"] == "completed" for m in active_mods)
            any_active = any(m["status"] == "active" for m in active_mods)
            sem_color = "#2CB67D" if all_done else ("#4A86E8" if any_active else "#706C86")

            sem_frame = QFrame()
            sem_frame.setObjectName("Card")
            sem_fl = QVBoxLayout(sem_frame)
            sem_fl.setContentsMargins(16, 12, 16, 14)
            sem_fl.setSpacing(8)

            hdr_row = QHBoxLayout()
            sem_indicator = QWidget()
            sem_indicator.setFixedSize(12, 12)
            sem_indicator.setStyleSheet(f"background:{sem_color};border-radius:6px;")
            hdr_row.addWidget(sem_indicator)
            sem_lbl = QLabel(_sem_display(sem))
            sem_lbl.setStyleSheet("font-size:16px;font-weight:bold;")
            hdr_row.addWidget(sem_lbl)
            hdr_row.addStretch()
            ects_lbl = QLabel(f"{int(sem_done_ects)}/{int(sem_ects)} ECTS  |  {sem_pct}% erledigt")
            ects_lbl.setStyleSheet("color:#706C86;font-size:12px;")
            hdr_row.addWidget(ects_lbl)
            sem_fl.addLayout(hdr_row)

            sem_bar = QProgressBar()
            sem_bar.setRange(0, 100)
            sem_bar.setValue(sem_pct)
            sem_bar.setFixedHeight(4)
            sem_bar.setTextVisible(False)
            sem_bar.setStyleSheet(
                f"QProgressBar{{background:{_tc('#E8EDF8','#313244')};border-radius:2px;border:none;}}"
                f"QProgressBar::chunk{{background:{sem_color};border-radius:2px;}}"
            )
            sem_fl.addWidget(sem_bar)

            # Responsive columns: 1 col when the scroll container is narrow
            _avail_w = self._sem_container.width() or 600
            _cols = 1 if _avail_w < 560 else 2
            mod_grid = QGridLayout()
            mod_grid.setSpacing(6)
            for i, m in enumerate(mods):
                card = self._make_mod_card(m, tasks_by_mod.get(m["id"], {}))
                mod_grid.addWidget(card, i // _cols, i % _cols)
            sem_fl.addLayout(mod_grid)

            self._sem_lay.addWidget(sem_frame)

        self._sem_lay.addStretch()

    def _make_mod_card(self, m, task_stats: dict) -> QFrame:
        card = QFrame()
        color = mod_color(m["id"])
        in_plan = int(m["in_plan"]) if "in_plan" in m.keys() else 1
        is_selected = (m["id"] == self._selected_mid)

        # Greyed out style for disabled modules
        if not in_plan:
            color_used = "#AAAAAA"
            bg = _tc("#F0F0F0", "#252535")
            border = f"1.5px solid {_tc('#CCCCCC','#3A3A4A')}"
            hover_bg = _tc("#EBEBEB", "#2E2E40")
        else:
            color_used = color
            border = f"2px solid {color}" if is_selected else f"1.5px solid {_tc('#DDE3F0','#45475A')}"
            bg = _tc("#EEF3FF","#313244") if is_selected else _tc("#F8FAFF","#2A2A3E")
            hover_bg = _tc("#EEF3FF","#313244")

        card.setStyleSheet(f"QFrame{{background:{bg};border:{border};border-radius:10px;}}"
                           f"QFrame:hover{{background:{hover_bg};border:1.5px solid {color_used};}}")
        card.setCursor(Qt.PointingHandCursor)
        card.setFixedHeight(100)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(4)

        mid = m["id"]

        # ── Row 1: name + status badge + plan toggle ──────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        dot = ColorDot(color_used, 9)
        hdr.addWidget(dot)
        name_lbl = QLabel(m["name"])
        name_color = "#999999" if not in_plan else _tc("#1A1A2E","#CDD6F4")
        name_lbl.setStyleSheet(f"font-weight:bold;font-size:13px;color:{name_color};"
                               f"{'text-decoration:line-through;' if not in_plan else ''}")
        name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        hdr.addWidget(name_lbl, 1)

        if in_plan:
            s_colors = {"completed":"#2CB67D","active":"#4A86E8","planned":"#706C86","paused":"#FF8C42"}
            sc = s_colors.get(m["status"], "#9E9E9E")
            badge = QLabel(tr_status(m["status"]))
            badge.setStyleSheet(f"background:{sc};color:white;border-radius:8px;"
                                f"padding:2px 8px;font-size:10px;font-weight:bold;")
            hdr.addWidget(badge)

        # Plan toggle button (⊘ = deactivate, ⊕ = activate)
        toggle_btn = QPushButton("⊘" if in_plan else "⊕")
        toggle_btn.setFixedSize(22, 22)
        toggle_btn.setCursor(Qt.PointingHandCursor)
        if in_plan:
            toggle_btn.setToolTip("Modul aus Studienplan ausschließen")
            toggle_btn.setStyleSheet(
                "QPushButton{background:transparent;color:#BBBBBB;border:none;font-size:14px;}"
                "QPushButton:hover{color:#E05050;}"
            )
        else:
            toggle_btn.setToolTip("Modul in Studienplan aufnehmen")
            toggle_btn.setStyleSheet(
                "QPushButton{background:transparent;color:#2CB67D;border:none;font-size:14px;font-weight:bold;}"
                "QPushButton:hover{color:#1A9A60;}"
            )

        def _toggle_plan(_checked=False, _mid=mid, _cur=in_plan):
            self.repo.update_module(_mid, in_plan=(0 if _cur else 1))
            self._update_global_stats()
            self._rebuild_semesters()
            if self._selected_mid == _mid:
                self._populate_detail(_mid)
            self._refresh_dashboard()

        toggle_btn.clicked.connect(_toggle_plan)
        hdr.addWidget(toggle_btn)
        lay.addLayout(hdr)

        # ── Row 2: semester picker + module type badge ────────────────────
        meta_row = QHBoxLayout()
        meta_row.setSpacing(5)
        meta_row.setContentsMargins(15, 0, 0, 0)

        _sv = str(m["semester"]).strip()
        sem_label = f"📅 {_sv}. Sem." if _sv.isdigit() else "📅 Sem. —"
        sem_btn = QPushButton(sem_label)
        sem_btn.setFixedHeight(20)
        sem_btn.setCursor(Qt.PointingHandCursor)
        sem_btn.setToolTip("Studiensemester setzen")
        sem_btn.setStyleSheet(
            f"QPushButton{{background:{_tc('#EEF3FF','#2A3A5A')};color:{_tc('#3A5A9A','#89B4FA')};"
            f"border-radius:6px;padding:0px 7px;font-size:10px;font-weight:600;"
            f"border:1px solid {_tc('#C8D8F8','#3A5A8A')};}}"
            f"QPushButton:hover{{background:{_tc('#D8E8FF','#354875')};border-color:#4A86E8;}}"
        )

        def _pick_sem(_checked=False, _mid=mid, _btn=sem_btn):
            from PySide6.QtWidgets import QMenu
            from PySide6.QtGui import QCursor
            menu = QMenu(self)
            menu.setStyleSheet(
                f"QMenu{{background:{_tc('#FFFFFF','#1E2030')};color:{_tc('#1A1A2E','#CDD6F4')};"
                f"border:1px solid {_tc('#D0D8F0','#3A4060')};border-radius:6px;padding:4px;}}"
                f"QMenu::item{{padding:6px 20px;border-radius:4px;}}"
                f"QMenu::item:selected{{background:{_tc('#EEF3FF','#2A3A5A')};"
                f"color:{_tc('#3A5A9A','#89B4FA')};}}"
            )
            menu.addAction("— nicht zugeordnet")
            for s in range(1, 10):
                menu.addAction(f"{s}. Semester")
            act = menu.exec(QCursor.pos())
            if act is None:
                return
            txt = act.text()
            new_sem = "" if txt.startswith("—") else txt.split(".")[0].strip()
            self.repo.update_module(_mid, semester=new_sem)
            _btn.setText(f"📅 {new_sem}. Sem." if new_sem else "📅 Sem. —")
            self._rebuild_semesters()

        sem_btn.clicked.connect(_pick_sem)
        meta_row.addWidget(sem_btn)

        _mt = m["module_type"] if "module_type" in m.keys() else "pflicht"
        if in_plan:
            # Light bg / dark fg for light mode; muted dark bg / bright fg for dark mode
            _mt_colors = {
                "pflicht":    (_tc("#E8F0FF","#1E2D4A"), _tc("#3A5A9A","#89B4FA"), "Pflicht"),
                "wahl":       (_tc("#F3E8FF","#2D1A40"), _tc("#7B3FA0","#CBA6F7"), "Wahl"),
                "vertiefung": (_tc("#E8FFF5","#102A20"), _tc("#1A7A5A","#A6E3A1"), "Vertiefung"),
            }
            _bg, _fg, _mt_label = _mt_colors.get(_mt or "pflicht", _mt_colors["pflicht"])
        else:
            _bg = _tc("#EEEEEE", "#2A2A3A")
            _fg = _tc("#AAAAAA", "#6B7280")
            _mt_labels_g = {"pflicht": "Pflicht", "wahl": "Wahl", "vertiefung": "Vertiefung"}
            _mt_label = _mt_labels_g.get(_mt or "pflicht", "Pflicht") + " · nicht gewählt"
        type_badge = QLabel(_mt_label)
        type_badge.setStyleSheet(
            f"background:{_bg};color:{_fg};border-radius:6px;"
            f"padding:2px 7px;font-size:10px;font-weight:600;"
            f"border:1px solid {_bg};"
        )
        meta_row.addWidget(type_badge)
        meta_row.addStretch()
        lay.addLayout(meta_row)

        # ── Row 3: progress bar + ECTS + readiness badge ─────────────────
        total = task_stats.get("total", 0)
        done  = task_stats.get("done", 0)
        pct   = int(done / total * 100) if total > 0 else 0

        bot_row = QHBoxLayout()
        bot_row.setContentsMargins(15, 0, 0, 0)
        bot_row.setSpacing(8)
        prog  = QProgressBar()
        prog.setRange(0, 100)
        prog.setValue(pct)
        prog.setFixedHeight(5)
        prog.setTextVisible(False)
        bar_color = color_used if in_plan else "#CCCCCC"
        prog.setStyleSheet(
            f"QProgressBar{{background:{_tc('#E8EDF8','#313244')};border-radius:2px;border:none;}}"
            f"QProgressBar::chunk{{background:{bar_color};border-radius:2px;}}"
        )
        bot_row.addWidget(prog, 1)
        ects_text = f"{m['ects']} ECTS" if in_plan else f"{m['ects']} ECTS (nicht geplant)"
        sub = QLabel(f"{done}/{total}  ·  {ects_text}")
        sub.setStyleSheet(f"color:{'#CCCCCC' if not in_plan else '#9BA8C0'};font-size:10px;")
        bot_row.addWidget(sub)

        # Readiness badge — only for active in-plan modules
        if in_plan:
            rs = self.repo.exam_readiness_score(mid)
            if rs["has_data"]:
                sc = rs["total"]
                if sc >= 85:
                    rb_bg, rb_fg = "#1A5C3A", "#2CB67D"
                elif sc >= 70:
                    rb_bg, rb_fg = "#3A4A1A", "#A6E028"
                elif sc >= 40:
                    rb_bg, rb_fg = "#5A3A00", "#FF8C42"
                else:
                    rb_bg, rb_fg = "#5A1A1A", "#E05050"
                rb_bg = _tc(rb_fg + "22", rb_bg)
                rb_lbl = QLabel(f"🎯 {sc}%")
                rb_lbl.setStyleSheet(
                    f"background:{rb_bg};color:{rb_fg};border-radius:5px;"
                    f"padding:1px 5px;font-size:9px;font-weight:bold;"
                )
                rb_lbl.setToolTip(
                    f"Prüfungsbereitschaft: {sc}%\n"
                    + (f"Wissen: {rs['topic_score']}%  " if rs['topic_score'] is not None else "")
                    + (f"Stunden: {rs['hours_score']}%  " if rs['hours_score'] is not None else "")
                    + (f"Aufgaben: {rs['task_score']}%" if rs['task_score'] is not None else "")
                )
                bot_row.addWidget(rb_lbl)
            else:
                # No tracking data yet — subtle invite
                rb_lbl = QLabel("📊")
                rb_lbl.setStyleSheet("font-size:11px;")
                rb_lbl.setToolTip("Noch keine Lerndaten — Tracking starten für Prüfungsbereitschafts-Score")
                bot_row.addWidget(rb_lbl)

        lay.addLayout(bot_row)

        card.mousePressEvent = lambda e, _m=mid: self._on_module_click(_m)
        return card

    def _on_module_click(self, mid: int):
        self._selected_mid = mid
        self._populate_detail(mid)
        self._rebuild_semesters()

    def _populate_detail(self, mid: int):
        """Populate the entire right panel for the selected module."""
        m = self.repo.get_module(mid)
        if not m:
            return

        color = mod_color(mid)
        in_plan = int(m["in_plan"]) if "in_plan" in m.keys() else 1
        self._rd_title.setText(m["name"])
        title_color = color if in_plan else "#AAAAAA"
        self._rd_title.setStyleSheet(f"font-size:16px;font-weight:bold;color:{title_color};"
                                     f"{'text-decoration:line-through;' if not in_plan else ''}")
        # Update plan toggle button (compact icon + tooltip)
        if in_plan:
            self._rd_plan_btn.setText("⊘")
            self._rd_plan_btn.setToolTip("Modul aus Studienplan ausschließen")
            self._rd_plan_btn.setStyleSheet(
                "QToolButton{background:#FFF0F0;color:#CC4444;border:1px solid #FFCCCC;"
                "border-radius:6px;font-size:14px;}"
                "QToolButton:hover{background:#FFE0E0;border-color:#CC4444;}"
            )
        else:
            self._rd_plan_btn.setText("⊕")
            self._rd_plan_btn.setToolTip("Modul in Studienplan aufnehmen")
            self._rd_plan_btn.setStyleSheet(
                "QToolButton{background:#F0FFF5;color:#1A7A50;border:1px solid #AADDC0;"
                "border-radius:6px;font-size:14px;}"
                "QToolButton:hover{background:#D0FFE8;border-color:#1A7A50;}"
            )
        _sem_val = m["semester"]
        _sem_str = (f"{_sem_val}. Semester" if str(_sem_val).isdigit()
                    else (_sem_val if _sem_val else "Semester nicht gesetzt"))
        _mt = m["module_type"] if "module_type" in m.keys() else "pflicht"
        _mt_labels = {"pflicht": "Pflichtmodul", "wahl": "Wahlmodul", "vertiefung": "Vertiefungsmodul"}
        _mt_str = _mt_labels.get(_mt or "pflicht", "Pflichtmodul")
        _plan_str = "" if in_plan else "  ·  ⚠ nicht im Studienplan"
        self._rd_info.setText(
            f"{_sem_str}  ·  {m['ects']} ECTS  ·  {_mt_str}  ·  Status: {tr_status(m['status'])}{_plan_str}"
        )

        # ── Readiness Card update ──────────────────────────────────────────
        self._update_readiness_card(mid, in_plan)

        tasks = self.repo.list_tasks(module_id=mid)
        total = len(tasks)
        done  = sum(1 for t in tasks if t["status"] == "Done")
        pct   = int(done / total * 100) if total > 0 else 0
        self._rd_bar.setValue(pct)
        self._rd_bar.setStyleSheet(
            f"QProgressBar{{background:{_tc('#E8EDF8','#313244')};border-radius:4px;border:none;max-height:8px;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:4px;}}"
        )
        self._rd_prog_lbl.setText(f"{done}/{total} erledigt")

        # ── Page 0: Tasks ──────────────────────────────────────────────
        self._task_list.clear()
        for task in tasks:
            is_done = task["status"] == "Done"
            in_prog = task["status"] == "In Progress"
            icon = "✅ " if is_done else ("🔄 " if in_prog else "⬜ ")
            prio_icons = {"Critical": "🔴", "High": "🟠", "Medium": "🔵", "Low": "⚪"}
            p_icon = prio_icons.get(task["priority"], "⚪")
            title_clean = task["title"]
            for prefix in ["[Lernziel] ", "[Prüfung] "]:
                title_clean = title_clean.replace(prefix, "")
            item = QListWidgetItem(f"{icon}{p_icon} {title_clean}")
            item.setData(Qt.UserRole, task["id"])
            if is_done:
                item.setForeground(QColor("#9E9E9E"))
            self._task_list.addItem(item)
        self._task_notes.clear()

        # ── Pages 1-3: Scraped data ────────────────────────────────────
        self._populate_objectives(mid)
        self._populate_content(mid)
        self._populate_exams(mid)

        self._right_placeholder.hide()
        self._right_detail.show()

        # Show the currently-active tab
        idx_map = {"tasks": 0, "objectives": 1, "content": 2, "exams": 3}
        self._right_stack.setCurrentIndex(idx_map.get(self._task_filter, 0))

    # ── Readiness card helper ──────────────────────────────────────────────

    def _update_readiness_card(self, mid: int, in_plan: int):
        """Update the readiness card in the detail panel for module `mid`."""
        if not in_plan:
            self._rd_readiness.hide()
            return
        self._rd_readiness.show()

        rs = self.repo.exam_readiness_score(mid)
        sc = rs["total"]

        # Score circle color
        if not rs["has_data"]:
            circ_bg  = _tc("#E8EDF8", "#2A2A3E")
            circ_fg  = "#706C86"
            score_text = "–"
        elif sc >= 85:
            circ_bg = _tc("#D0F5E8", "#0A2E1E"); circ_fg = "#2CB67D"; score_text = f"{sc}%"
        elif sc >= 70:
            circ_bg = _tc("#E8F5C0", "#1E2E08"); circ_fg = "#7AAF00"; score_text = f"{sc}%"
        elif sc >= 40:
            circ_bg = _tc("#FFE8CC", "#2E1800"); circ_fg = "#E07000"; score_text = f"{sc}%"
        else:
            circ_bg = _tc("#FFD8D8", "#2E0808"); circ_fg = "#CC3333"; score_text = f"{sc}%"

        self._rc_score_lbl.setText(score_text)
        self._rc_score_lbl.setStyleSheet(
            f"font-size:{'14px' if len(score_text)>3 else '16px'};font-weight:bold;"
            f"color:{circ_fg};background:{circ_bg};border-radius:22px;border:none;"
        )

        # Component breakdown text
        parts = []
        if rs["topic_score"] is not None:
            parts.append(f"🧠 Wissen {rs['topic_score']}%")
        elif rs["topic_count"] == 0:
            parts.append("🧠 Keine Topics")
        if rs["hours_score"] is not None:
            parts.append(f"⏱ Stunden {rs['hours_score']}%")
        elif rs["hours_target"] > 0:
            parts.append(f"⏱ 0 / {rs['hours_target']:.0f}h")
        if rs["task_score"] is not None:
            parts.append(f"✅ Aufgaben {rs['task_score']}%")

        if parts:
            self._rc_components.setText("  ·  ".join(parts))
        else:
            self._rc_components.setText("Starte Tracking: Topics erfassen, Pomodoro nutzen, Aufgaben abhaken")

        # Exam countdown
        days = rs["days_until_exam"]
        if days is None:
            self._rc_exam_lbl.setText("")
        elif days < 0:
            self._rc_exam_lbl.setText(f"📅 Vor\n{abs(days)} Tagen")
            self._rc_exam_lbl.setStyleSheet("font-size:10px;color:#706C86;")
        elif days == 0:
            self._rc_exam_lbl.setText("📅 Heute!")
            self._rc_exam_lbl.setStyleSheet("font-size:10px;font-weight:bold;color:#E05050;")
        elif days <= 7:
            self._rc_exam_lbl.setText(f"🔥 {days} Tage")
            self._rc_exam_lbl.setStyleSheet("font-size:10px;font-weight:bold;color:#E05050;")
        elif days <= 30:
            self._rc_exam_lbl.setText(f"⚡ {days} Tage")
            self._rc_exam_lbl.setStyleSheet("font-size:10px;font-weight:600;color:#FF8C42;")
        else:
            self._rc_exam_lbl.setText(f"📅 {days} Tage")
            self._rc_exam_lbl.setStyleSheet("font-size:10px;color:#706C86;")

    # ── Manual entry helpers for objectives / content / exams ─────────────

    def _add_obj_manual(self, mid: int):
        """Manually add a Lernziel (objective) to the selected module."""
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowTitle("Lernziel hinzufügen")
        dlg.setMinimumWidth(380)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Lernziel:"))
        edit = QLineEdit()
        edit.setPlaceholderText("z.B. Kann relationale Datenbanken modellieren")
        lay.addWidget(edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.Accepted and edit.text().strip():
            self.repo.add_scraped_data(mid, "objective", edit.text().strip())
            self._populate_objectives(mid)

    def _add_content_manual(self, mid: int):
        """Manually add a Lerninhalt (content section) to the selected module."""
        import json as _json
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowTitle("Lerninhalt hinzufügen")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        title_edit = QLineEdit()
        title_edit.setPlaceholderText("z.B. Kapitel 3: Datenstrukturen")
        form.addRow("Abschnittstitel:", title_edit)
        items_edit = QTextEdit()
        items_edit.setPlaceholderText("Unterpunkte – einer pro Zeile:\nArrays\nLinked Lists\nStacks & Queues")
        items_edit.setFixedHeight(100)
        form.addRow("Unterpunkte:", items_edit)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            title = title_edit.text().strip()
            if title:
                items = [l.strip() for l in items_edit.toPlainText().splitlines() if l.strip()]
                body = _json.dumps(items, ensure_ascii=False)
                self.repo.add_scraped_data(mid, "content_section", title, body=body)
                self._populate_content(mid)

    def _add_pruefung_manual(self, mid: int):
        """Manually add a Prüfung (assessment) entry to the selected module."""
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowTitle("Prüfung hinzufügen")
        dlg.setMinimumWidth(400)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        form.setSpacing(8)
        title_edit = QLineEdit()
        title_edit.setPlaceholderText("z.B. Schriftliche Abschlussprüfung")
        form.addRow("Prüfungsform:", title_edit)
        weight_spin = QDoubleSpinBox()
        weight_spin.setRange(0, 100)
        weight_spin.setSingleStep(5)
        weight_spin.setSuffix(" %")
        weight_spin.setValue(100)
        form.addRow("Gewichtung:", weight_spin)
        notes_edit = QLineEdit()
        notes_edit.setPlaceholderText("z.B. 90 Min, offene Bücher erlaubt")
        form.addRow("Notizen:", notes_edit)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            title = title_edit.text().strip()
            if title:
                body = notes_edit.text().strip()
                weight = weight_spin.value()
                self.repo.add_scraped_data(mid, "assessment", title,
                                            body=body, weight=weight)
                self._populate_exams(mid)

    # ── Scraped-data populators ────────────────────────────────────────────

    def _clear_layout(self, lay):
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _no_data_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#706C86;font-size:12px;padding:12px;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        return lbl

    def _populate_objectives(self, mid: int):
        self._clear_layout(self._obj_lay)
        rows = self.repo.list_scraped_data(mid, "objective")
        if not rows:
            self._obj_lay.addWidget(self._no_data_label(
                "Keine Lernziele vorhanden.\n"
                "Füge Lernziele manuell hinzu oder importiere den Modulplan der FH als PDF."
            ))
            self._obj_lay.addStretch()
            return

        hdr = QLabel(f"Lernziele  ({len(rows)})")
        hdr.setStyleSheet("font-weight:bold;font-size:13px;")
        self._obj_lay.addWidget(hdr)

        for i, row in enumerate(rows):
            card = QFrame()
            card.setAttribute(Qt.WA_StyledBackground, True)
            card.setStyleSheet(
                f"QFrame{{background:{_tc('#F8FAFF','#2A2A3E')};"
                f"border:1px solid {_tc('#DDE3F0','#45475A')};"
                f"border-radius:8px;padding:4px;}}"
            )
            lay = QHBoxLayout(card)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setSpacing(10)

            num = QLabel(f"{i+1}")
            num.setStyleSheet(
                f"background:{_tc('#4A86E8','#89B4FA')};color:white;"
                f"border-radius:10px;padding:2px 6px;font-size:11px;font-weight:bold;"
            )
            num.setFixedWidth(28)
            num.setAlignment(Qt.AlignCenter)
            lay.addWidget(num)

            txt = QLabel(row["title"])
            txt.setWordWrap(True)
            txt.setStyleSheet("font-size:12px;")
            lay.addWidget(txt, 1)
            self._obj_lay.addWidget(card)

        self._obj_lay.addStretch()

    def _populate_content(self, mid: int):
        self._clear_layout(self._cont_lay)
        rows = self.repo.list_scraped_data(mid, "content_section")
        if not rows:
            self._cont_lay.addWidget(self._no_data_label(
                "Keine Lerninhalte vorhanden.\n"
                "Füge Lerninhalte manuell hinzu oder importiere den Modulplan der FH als PDF."
            ))
            self._cont_lay.addStretch()
            return

        import json as _json
        hdr = QLabel(f"Lerninhalte  ({len(rows)} Abschnitte)")
        hdr.setStyleSheet("font-weight:bold;font-size:13px;")
        self._cont_lay.addWidget(hdr)

        for row in rows:
            # Section header as collapsible-style card
            sec_frame = QFrame()
            sec_frame.setAttribute(Qt.WA_StyledBackground, True)
            sec_frame.setStyleSheet(
                f"QFrame{{background:{_tc('#EEF3FF','#313244')};"
                f"border:1px solid {_tc('#C8D8F8','#45475A')};"
                f"border-radius:8px;}}"
            )
            sec_lay = QVBoxLayout(sec_frame)
            sec_lay.setContentsMargins(12, 8, 12, 8)
            sec_lay.setSpacing(4)

            sec_title = QLabel(f"▸  {row['title']}")
            sec_title.setStyleSheet("font-weight:bold;font-size:12px;")
            sec_lay.addWidget(sec_title)

            # Sub-items from JSON body
            try:
                items = _json.loads(row["body"]) if row["body"] else []
            except Exception:
                items = []
            for item in items:
                item_lbl = QLabel(f"  •  {item}")
                item_lbl.setWordWrap(True)
                item_lbl.setStyleSheet("font-size:11px;color:#5A5F7A;padding-left:8px;")
                sec_lay.addWidget(item_lbl)

            self._cont_lay.addWidget(sec_frame)

        self._cont_lay.addStretch()

    def _populate_exams(self, mid: int):
        self._clear_layout(self._exam_lay)
        rows = self.repo.list_scraped_data(mid, "assessment")
        if not rows:
            self._exam_lay.addWidget(self._no_data_label(
                "Keine Prüfungsdaten vorhanden.\n"
                "Füge Prüfungsinfos manuell hinzu oder importiere den Modulplan der FH als PDF."
            ))
            self._exam_lay.addStretch()
            return

        # Weight sum check
        total_w = sum(float(r["weight"]) for r in rows)
        hdr = QLabel(f"Prüfungen & Gewichtung  ·  Σ {total_w:.0f}%")
        hdr.setStyleSheet("font-weight:bold;font-size:13px;")
        self._exam_lay.addWidget(hdr)

        weight_colors = [(70, "#E74C3C"), (50, "#E67E22"), (30, "#F1C40F"), (0, "#2CB67D")]

        for row in rows:
            w = float(row["weight"])
            wcolor = next((c for threshold, c in weight_colors if w >= threshold), "#706C86")

            card = QFrame()
            card.setAttribute(Qt.WA_StyledBackground, True)
            card.setStyleSheet(
                f"QFrame{{background:{_tc('#F8FAFF','#2A2A3E')};"
                f"border-left:4px solid {wcolor};"
                f"border-top:1px solid {_tc('#DDE3F0','#45475A')};"
                f"border-right:1px solid {_tc('#DDE3F0','#45475A')};"
                f"border-bottom:1px solid {_tc('#DDE3F0','#45475A')};"
                f"border-radius:8px;}}"
            )
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(14, 10, 14, 10)
            c_lay.setSpacing(4)

            # Title row with weight badge
            title_row = QHBoxLayout()
            exam_name = QLabel(row["title"])
            exam_name.setStyleSheet("font-weight:bold;font-size:13px;")
            title_row.addWidget(exam_name, 1)

            if w > 0:
                weight_badge = QLabel(f"{w:.0f}%")
                weight_badge.setStyleSheet(
                    f"background:{wcolor};color:white;border-radius:10px;"
                    f"padding:2px 10px;font-size:12px;font-weight:bold;"
                )
                title_row.addWidget(weight_badge)
            c_lay.addLayout(title_row)

            # Progress bar showing weight
            if w > 0:
                w_bar = QProgressBar()
                w_bar.setRange(0, 100)
                w_bar.setValue(int(w))
                w_bar.setFixedHeight(5)
                w_bar.setTextVisible(False)
                w_bar.setStyleSheet(
                    f"QProgressBar{{background:{_tc('#E8EDF8','#313244')};border-radius:2px;border:none;}}"
                    f"QProgressBar::chunk{{background:{wcolor};border-radius:2px;}}"
                )
                c_lay.addWidget(w_bar)

            # Details from body field
            if row["body"]:
                detail = QLabel(row["body"][:200])
                detail.setWordWrap(True)
                detail.setStyleSheet("font-size:11px;color:#706C86;margin-top:2px;")
                c_lay.addWidget(detail)

            self._exam_lay.addWidget(card)

        self._exam_lay.addStretch()

    def _on_task_selected(self, current, previous):
        if not current:
            return
        tid = current.data(Qt.UserRole)
        if tid is None:
            return
        self._current_detail_task_id = tid
        task = self.repo.get_task(tid)
        if not task:
            return
        notes = task["notes"] or ""
        if notes:
            lines = notes.split("\n")
            html_parts = ['<div style="font-family:sans-serif;font-size:12px;line-height:1.5;">']
            for line in lines:
                line = line.strip()
                if not line:
                    html_parts.append("<br>")
                elif line.startswith("•"):
                    html_parts.append(f'<div style="padding:1px 0 1px 8px;">• {line[1:].strip()}</div>')
                elif line.startswith("📝") or line.startswith("📊"):
                    html_parts.append(f'<div style="color:#4A86E8;font-weight:bold;margin-top:6px;">{line}</div>')
                elif line.startswith("ECTS:"):
                    html_parts.append(f'<div style="color:#706C86;font-size:11px;margin-top:4px;">{line}</div>')
                else:
                    html_parts.append(f'<div>{line}</div>')
            html_parts.append("</div>")
            self._task_notes.setHtml("".join(html_parts))
        else:
            self._task_notes.setPlainText("Keine Notizen vorhanden.")

    def _set_task_status(self, status: str):
        if not self._current_detail_task_id:
            return
        self.repo.update_task(self._current_detail_task_id, status=status)
        if self._selected_mid:
            self._populate_detail(self._selected_mid)
        self._update_global_stats()


# ── SM-2 Spaced Repetition Review Dialog ──────────────────────────────────────

class SRReviewDialog(QDialog):
    """Flashcard-style SM-2 review session.

    Shows topics due for review one by one.
    The user rates recall quality → SM-2 algorithm schedules the next review.
    """

    def __init__(self, repo, topics: list, parent=None):
        super().__init__(parent)
        self.repo    = repo
        self.topics  = list(topics)
        self._idx    = 0
        self._results: list = []   # (topic_id, quality, next_review) per review
        self._revealed = False
        self.setWindowTitle("Wissens-Review")
        self.setMinimumSize(560, 380)
        self.resize(600, 420)
        self._build()
        self._show_current()

    def _build(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(28, 24, 28, 24)
        main.setSpacing(12)

        # ── Header: progress ──────────────────────────────────────────────
        hdr = QHBoxLayout()
        self._progress_lbl = QLabel()
        self._progress_lbl.setStyleSheet(f"font-size:12px;color:{_tc('#706C86','#6B7280')};")
        hdr.addWidget(self._progress_lbl)
        hdr.addStretch()
        self._module_lbl = QLabel()
        self._module_lbl.setStyleSheet(f"font-size:11px;color:{_tc('#706C86','#6B7280')};")
        hdr.addWidget(self._module_lbl)
        main.addLayout(hdr)

        # Progress bar
        self._prog_bar = QProgressBar()
        self._prog_bar.setFixedHeight(4)
        self._prog_bar.setTextVisible(False)
        self._prog_bar.setStyleSheet(
            f"QProgressBar{{background:{_tc('#E8EDF8','#2A2A3E')};border-radius:2px;border:none;}}"
            f"QProgressBar::chunk{{background:#4A86E8;border-radius:2px;}}"
        )
        main.addWidget(self._prog_bar)

        # ── Card: topic title (large, centered) ───────────────────────────
        self._card = QFrame()
        self._card.setObjectName("SRCard")
        self._card.setStyleSheet(
            f"QFrame#SRCard{{background:{_tc('#F8FAFF','#252535')};"
            f"border:1px solid {_tc('#DDE3F0','#383850')};border-radius:12px;}}"
        )
        self._card.setMinimumHeight(140)
        card_lay = QVBoxLayout(self._card)
        card_lay.setContentsMargins(24, 20, 24, 20)
        card_lay.setSpacing(8)

        self._topic_lbl = QLabel()
        self._topic_lbl.setAlignment(Qt.AlignCenter)
        self._topic_lbl.setWordWrap(True)
        self._topic_lbl.setStyleSheet(
            f"font-size:20px;font-weight:bold;color:{_tc('#1A1A2E','#CDD6F4')};"
        )
        card_lay.addWidget(self._topic_lbl, 1)

        self._notes_lbl = QLabel()
        self._notes_lbl.setAlignment(Qt.AlignCenter)
        self._notes_lbl.setWordWrap(True)
        self._notes_lbl.setStyleSheet(f"font-size:13px;color:{_tc('#6B7280','#9BA8C0')};")
        self._notes_lbl.hide()
        card_lay.addWidget(self._notes_lbl)

        main.addWidget(self._card, 1)

        # ── Reveal / SR rating buttons ─────────────────────────────────────
        self._reveal_btn = QPushButton("🔍  Aufdecken")
        self._reveal_btn.setFixedHeight(36)
        self._reveal_btn.setObjectName("PrimaryBtn")
        self._reveal_btn.clicked.connect(self._reveal)
        main.addWidget(self._reveal_btn)

        self._rating_row = QHBoxLayout()
        self._rating_row.setSpacing(6)
        _rating_defs = [
            ("Nicht gewusst",    "#E05050", "#FF8080", 0),
            ("Mit Mühe",         "#E07000", "#FFAA00", 2),
            ("Gut gewusst",      "#1A7A50", "#2CB67D", 4),
            ("Sofort! ⚡",        "#1A5A9A", "#4A86E8", 5),
        ]
        self._rating_btns = []
        for label, bg_dark, bg_light, quality in _rating_defs:
            btn = QPushButton(label)
            btn.setFixedHeight(36)
            _bg = _tc(bg_light + "33", bg_dark + "44")
            _fg = _tc(bg_dark, bg_light)
            btn.setStyleSheet(
                f"QPushButton{{background:{_bg};color:{_fg};border:1px solid {_fg}55;"
                f"border-radius:7px;font-size:12px;font-weight:600;padding:0 10px;}}"
                f"QPushButton:hover{{background:{_fg}33;border-color:{_fg};}}"
            )
            btn.clicked.connect(lambda _c=False, q=quality: self._rate(q))
            self._rating_btns.append(btn)
            self._rating_row.addWidget(btn)
        main.addLayout(self._rating_row)

        # Done / summary row
        self._done_btn = QPushButton("Session beenden")
        self._done_btn.setObjectName("SecondaryBtn")
        self._done_btn.setFixedHeight(36)
        self._done_btn.clicked.connect(self.accept)
        self._done_btn.hide()
        main.addWidget(self._done_btn)

    def _show_current(self):
        total = len(self.topics)
        if self._idx >= total:
            self._show_summary()
            return

        t = self.topics[self._idx]
        self._progress_lbl.setText(f"Topic {self._idx + 1} von {total}")
        self._prog_bar.setRange(0, total)
        self._prog_bar.setValue(self._idx)
        self._module_lbl.setText(t["module_name"] if "module_name" in t.keys() else "")

        self._topic_lbl.setText(t["title"])
        notes = (t["notes"] if "notes" in t.keys() else "") or ""
        self._notes_lbl.setText(notes)
        self._notes_lbl.setVisible(False)

        self._revealed = False
        self._reveal_btn.show()
        for btn in self._rating_btns:
            btn.hide()
        self._done_btn.hide()

    def _reveal(self):
        self._revealed = True
        t = self.topics[self._idx]
        notes = (t["notes"] if "notes" in t.keys() else "") or ""
        if notes:
            self._notes_lbl.setText(notes)
            self._notes_lbl.show()
        self._reveal_btn.hide()
        for btn in self._rating_btns:
            btn.show()

    def _rate(self, quality: int):
        t = self.topics[self._idx]
        result = self.repo.sm2_review(t["id"], quality)
        self._results.append({
            "title":       t["title"],
            "quality":     quality,
            "next_review": result.get("next_review", ""),
            "interval":    result.get("interval", 1),
        })
        self._idx += 1
        self._show_current()

    def _show_summary(self):
        """Replace card content with a summary after all topics reviewed."""
        total = len(self._results)
        knew   = sum(1 for r in self._results if r["quality"] >= 3)
        missed = total - knew

        self._topic_lbl.setText(
            f"✅  Review abgeschlossen!\n\n"
            f"{knew} gewusst  ·  {missed} nicht gewusst\n\n"
            f"{total} Topics bewertet"
        )
        self._topic_lbl.setStyleSheet(
            f"font-size:16px;font-weight:600;color:{_tc('#1A1A2E','#CDD6F4')};"
        )
        self._notes_lbl.hide()
        self._reveal_btn.hide()
        for btn in self._rating_btns:
            btn.hide()
        self._done_btn.show()
        self._prog_bar.setValue(total)
        self._progress_lbl.setText(f"Alle {total} Topics bewertet")

    def reviewed_count(self) -> int:
        return len(self._results)


# ── Knowledge Page ─────────────────────────────────────────────────────────────

class KnowledgePage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._selected_mid: Optional[int] = None
        self._global_refresh: Optional[callable] = None
        self._build()

    def set_global_refresh(self, cb):
        self._global_refresh = cb

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel(tr("page.knowledge"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()

        # Module filter
        self.mod_cb = QComboBox()
        self.mod_cb.setMinimumWidth(200)
        self.mod_cb.currentIndexChanged.connect(self._load_topics)
        hdr.addWidget(QLabel("Modul:"))
        hdr.addWidget(self.mod_cb)

        # Task filter (populated once a module is selected)
        self.task_filter_cb = QComboBox()
        self.task_filter_cb.setMinimumWidth(170)
        self.task_filter_cb.addItem("Alle Themen", None)
        self.task_filter_cb.currentIndexChanged.connect(self._apply_topic_filter)
        hdr.addWidget(QLabel("Aufgabe:"))
        hdr.addWidget(self.task_filter_cb)

        add_task_btn = QPushButton("+ Aufgabe")
        add_task_btn.setObjectName("SecondaryBtn")
        add_task_btn.clicked.connect(self._add_task_inline)
        hdr.addWidget(add_task_btn)

        add_btn = QPushButton("+ Thema")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_topic)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        # ── SR due-topics banner ─────────────────────────────────────────────
        self._sr_banner = QFrame()
        self._sr_banner.setObjectName("SRBanner")
        self._sr_banner.setStyleSheet(
            f"QFrame#SRBanner{{background:{_tc('#FFF7E6','#2A2010')};"
            f"border-left:3px solid #FF8C42;border-radius:6px;}}"
        )
        sr_ban_lay = QHBoxLayout(self._sr_banner)
        sr_ban_lay.setContentsMargins(14, 8, 14, 8)
        sr_ban_lay.setSpacing(12)
        self._sr_banner_lbl = QLabel()
        self._sr_banner_lbl.setStyleSheet(f"color:{_tc('#7A4A00','#FFAA55')};font-size:12px;font-weight:600;")
        sr_ban_lay.addWidget(self._sr_banner_lbl, 1)
        self._sr_review_btn = QPushButton("📚  Review starten")
        self._sr_review_btn.setFixedHeight(28)
        self._sr_review_btn.setCursor(Qt.PointingHandCursor)
        self._sr_review_btn.setStyleSheet(
            f"QPushButton{{background:{_tc('#FF8C4222','#FF8C4233')};color:{_tc('#7A4A00','#FFAA55')};"
            f"border:1px solid #FF8C4299;border-radius:6px;padding:0 12px;font-weight:600;font-size:11px;}}"
            f"QPushButton:hover{{background:#FF8C4244;}}"
        )
        self._sr_review_btn.clicked.connect(self._start_sr_review)
        sr_ban_lay.addWidget(self._sr_review_btn)
        self._sr_banner.hide()
        lay.addWidget(self._sr_banner)

        # Knowledge-level summary bar
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
            lbl.setStyleSheet("font-size: 11px; color: #706C86;")
            col.addWidget(lbl)
            self.summary_labels[k] = lbl
            sf_lay.addLayout(col)
        lay.addWidget(self.summary_frame)

        # ── Topics table ─────────────────────────────────────────────────────
        topics_hdr = QHBoxLayout()
        topics_title = QLabel("Wissensthemen")
        topics_title.setObjectName("SectionTitle")
        topics_hdr.addWidget(topics_title)
        topics_hdr.addStretch()
        del_btn = QPushButton("Thema löschen")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_topic)
        topics_hdr.addWidget(del_btn)
        lay.addLayout(topics_hdr)

        self.topic_table = QTableWidget(0, 6)
        self.topic_table.setHorizontalHeaderLabels(
            ["Thema", "Kenntnisstand", "Notizen", "Aufgabe", "Nächste Wdh.", "ID"]
        )
        self.topic_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.topic_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.topic_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.topic_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.topic_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.topic_table.setColumnHidden(5, True)  # hidden ID column
        self.topic_table.verticalHeader().setVisible(False)
        self.topic_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.topic_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.topic_table.doubleClicked.connect(self._edit_topic)
        lay.addWidget(self.topic_table, 3)

        # ── Tasks section (inline, directly below topics — no splitter) ───────
        tasks_card = QFrame()
        tasks_card.setObjectName("Card")
        tasks_card_lay = QVBoxLayout(tasks_card)
        tasks_card_lay.setContentsMargins(12, 10, 12, 10)
        tasks_card_lay.setSpacing(6)

        self._tasks_title = QLabel("Aufgaben")
        self._tasks_title.setObjectName("SectionTitle")
        tasks_card_lay.addWidget(self._tasks_title)

        self._task_list_w = QWidget()
        self._task_list_w.setAttribute(Qt.WA_StyledBackground, True)
        self._task_list_lay = QVBoxLayout(self._task_list_w)
        self._task_list_lay.setContentsMargins(0, 0, 0, 0)
        self._task_list_lay.setSpacing(4)
        tasks_card_lay.addWidget(make_scroll(self._task_list_w), 1)
        lay.addWidget(tasks_card, 2)

    def refresh(self):
        # Sync Lernziele → tasks for ALL modules (silent, deduped by title)
        for m in self.repo.list_modules("all"):
            self._sync_objectives_as_tasks(m["id"])

        sem_f = _active_sem_filter(self.repo)
        mods_filtered = _filter_mods_by_sem(self.repo.list_modules("all"), sem_f)
        mod_ids_allowed = {m["id"] for m in mods_filtered}

        cur_id = self.mod_cb.currentData()
        self.mod_cb.blockSignals(True)
        self.mod_cb.clear()
        for m in mods_filtered:
            self.mod_cb.addItem(m["name"], m["id"])
        if cur_id and cur_id in mod_ids_allowed:
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
            self._load_tasks(None)
            # Reset task filter
            self.task_filter_cb.blockSignals(True)
            self.task_filter_cb.clear()
            self.task_filter_cb.addItem("Alle Themen", None)
            self.task_filter_cb.blockSignals(False)
            return

        # Auto-sync Lernziele → tasks (silently, deduped by title)
        new_from_obj = self._sync_objectives_as_tasks(mid)

        # Repopulate task-filter combobox (preserve previous selection if possible)
        prev_tid = self.task_filter_cb.currentData()
        self.task_filter_cb.blockSignals(True)
        self.task_filter_cb.clear()
        self.task_filter_cb.addItem("Alle Themen", None)
        for t in self.repo.list_tasks(module_id=mid):
            self.task_filter_cb.addItem(t["title"], t["id"])
        # Restore previous selection
        restored = False
        if prev_tid is not None:
            idx = self.task_filter_cb.findData(prev_tid)
            if idx >= 0:
                self.task_filter_cb.setCurrentIndex(idx)
                restored = True
        if not restored:
            self.task_filter_cb.setCurrentIndex(0)
        self.task_filter_cb.blockSignals(False)

        self._apply_topic_filter()

    def _apply_topic_filter(self):
        """Filter the topic table by the currently selected task (or show all)."""
        mid = self._selected_mid
        if not mid:
            return

        all_topics = self.repo.list_topics(mid)
        filter_tid = self.task_filter_cb.currentData()   # None = show all

        if filter_tid is None:
            topics = all_topics
        else:
            topics = [
                t for t in all_topics
                if "task_id" in t.keys()
                and t["task_id"] is not None
                and int(t["task_id"]) == filter_tid
            ]

        # Update knowledge summary based on the filtered subset
        from collections import Counter
        counts = Counter(int(t["knowledge_level"]) for t in topics)
        for k in range(5):
            self.summary_labels[k].setText(f"{tr_know(k)}\n{counts.get(k, 0)}")

        # Populate table
        today = date.today()
        self.topic_table.setRowCount(len(topics))
        for r, t in enumerate(topics):
            level = int(t["knowledge_level"])
            # ── Col 0: Thema (with SM-2 overdue indicator) ──────────────
            nr_str = (t["sr_next_review"] if "sr_next_review" in t.keys() else "") or ""
            is_overdue = False
            if nr_str:
                try:
                    nr_date = date.fromisoformat(nr_str[:10])
                    is_overdue = nr_date <= today
                except Exception:
                    pass
            title_text = ("⚠ " + t["title"]) if is_overdue else t["title"]
            title_item = QTableWidgetItem(title_text)
            if is_overdue:
                title_item.setForeground(QColor("#FF9800"))
                title_item.setToolTip(f"SR-Review fällig! Nächste Wdh. war: {nr_str[:10]}")
            self.topic_table.setItem(r, 0, title_item)
            # ── Col 1: Kenntnisstand ─────────────────────────────────────
            lvl_item = QTableWidgetItem(tr_know(level))
            lvl_item.setForeground(QColor(KNOWLEDGE_COLORS.get(level, "#333")))
            self.topic_table.setItem(r, 1, lvl_item)
            self.topic_table.setItem(r, 2, QTableWidgetItem(t["notes"] or ""))
            # ── Col 3: linked task name ──────────────────────────────────
            task_name = (t["task_title"] if "task_title" in t.keys() and t["task_title"] else "")
            task_item = QTableWidgetItem(f"☑ {task_name}" if task_name else "")
            task_item.setForeground(QColor(_tc("#4A86E8", "#7BAAF7")))
            self.topic_table.setItem(r, 3, task_item)
            # ── Col 4: SR next review ────────────────────────────────────
            if not nr_str:
                sr_text  = "—"
                sr_color = _tc("#BBBBBB", "#555577")
                sr_tip   = "Noch kein Review gestartet"
            else:
                try:
                    nr_date = date.fromisoformat(nr_str[:10])
                    diff = (nr_date - today).days
                    if diff < 0:
                        sr_text  = f"Überfällig ({abs(diff)}d)"
                        sr_color = "#E05050"
                        sr_tip   = f"Review überfällig seit {abs(diff)} Tag(en)"
                    elif diff == 0:
                        sr_text  = "Heute"
                        sr_color = "#FF8C42"
                        sr_tip   = "Review heute fällig"
                    elif diff == 1:
                        sr_text  = "Morgen"
                        sr_color = "#F5C518"
                        sr_tip   = "Review morgen fällig"
                    else:
                        sr_text  = f"in {diff}d"
                        sr_color = _tc("#2CB67D", "#2CB67D")
                        sr_tip   = f"Nächste Wiederholung in {diff} Tagen ({nr_str[:10]})"
                except Exception:
                    sr_text  = nr_str[:10]
                    sr_color = "#706C86"
                    sr_tip   = ""
            sr_item = QTableWidgetItem(sr_text)
            sr_item.setForeground(QColor(sr_color))
            sr_item.setToolTip(sr_tip)
            self.topic_table.setItem(r, 4, sr_item)
            # ── Col 5: hidden ID ─────────────────────────────────────────
            self.topic_table.setItem(r, 5, QTableWidgetItem(str(t["id"])))

        # ── Update SR banner ─────────────────────────────────────────────
        self._update_sr_banner(mid)
        self._load_tasks(mid)

    # ── SM-2 helpers ────────────────────────────────────────────────────────

    def _update_sr_banner(self, mid: Optional[int] = None):
        """Show/hide the SR banner based on how many topics are due."""
        due_topics = self.repo.sm2_due_topics(module_id=mid)
        if due_topics:
            n = len(due_topics)
            self._sr_banner_lbl.setText(
                f"🔁  {n} Topic{'s' if n > 1 else ''} zur Wiederholung fällig"
                + (f"  (dieses Modul)" if mid else "")
            )
            self._sr_banner.show()
        else:
            self._sr_banner.hide()

    def _start_sr_review(self):
        """Launch the SR review dialog for due topics in the current module."""
        mid = self._selected_mid
        due_topics = self.repo.sm2_due_topics(module_id=mid)
        if not due_topics:
            return
        dlg = SRReviewDialog(self.repo, due_topics, parent=self)
        dlg.exec()
        # Refresh after review
        n = dlg.reviewed_count()
        self._load_topics()
        if n > 0 and self._global_refresh:
            self._global_refresh()

    # ── Objectives → Tasks auto-sync ──────────────────────────────────────────

    def _sync_objectives_as_tasks(self, mid: int) -> int:
        """Convert module Lernziele into tasks (skip titles that already exist).

        Returns the number of newly created tasks so the caller can show feedback.
        """
        objectives = self.repo.list_scraped_data(mid, "objective")
        if not objectives:
            return 0

        existing_tasks  = self.repo.list_tasks(module_id=mid)
        existing_titles = {(t["title"] or "").strip().lower() for t in existing_tasks}

        mod  = self.repo.get_module(mid)
        prio = exam_priority(mod["exam_date"] if mod else None)

        created = 0
        for obj in objectives:
            title = (obj["title"] or "").strip()
            if not title:
                continue
            if title.lower() not in existing_titles:
                self.repo.add_task(mid, title, priority=prio, status="Open")
                existing_titles.add(title.lower())   # avoid duplicates within this run
                created += 1
        return created

    def _load_tasks(self, mid: Optional[int]):
        # Clear old task rows
        while self._task_list_lay.count():
            item = self._task_list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not mid:
            self._tasks_title.setText("Aufgaben")
            placeholder = QLabel("Modul auswählen um Aufgaben zu sehen.")
            placeholder.setStyleSheet(f"color:{_tc('#706C86','#6B7280')};font-size:12px;")
            self._task_list_lay.addWidget(placeholder)
            self._task_list_lay.addStretch()
            return

        tasks = [t for t in self.repo.list_tasks() if t["module_id"] == mid]
        open_t = [t for t in tasks if t["status"] != "Done"]
        done_t = [t for t in tasks if t["status"] == "Done"]
        self._tasks_title.setText(
            f"Aufgaben  —  {len(open_t)} offen · {len(done_t)} erledigt"
        )

        # Show a subtle banner if this module has Lernziele (tasks auto-sourced from objectives)
        obj_count = len(self.repo.list_scraped_data(mid, "objective"))
        if obj_count:
            info = QFrame()
            info.setStyleSheet(
                "background:#4A86E815;border-left:3px solid #4A86E8;border-radius:4px;"
            )
            info_lay = QHBoxLayout(info)
            info_lay.setContentsMargins(10, 5, 10, 5)
            info_lbl = QLabel(
                f"📘  {obj_count} Lernziel(e) als Aufgaben importiert — "
                f"Themen zuordnen um Wissen zu strukturieren"
            )
            info_lbl.setStyleSheet(
                f"font-size:11px;color:{_tc('#4A86E8','#7BAAF7')};font-weight:500;"
            )
            info_lbl.setWordWrap(True)
            info_lay.addWidget(info_lbl)
            self._task_list_lay.addWidget(info)

        if not tasks:
            placeholder = QLabel("Keine Aufgaben für dieses Modul.")
            placeholder.setStyleSheet(f"color:{_tc('#706C86','#6B7280')};font-size:12px;")
            self._task_list_lay.addWidget(placeholder)
            self._task_list_lay.addStretch()
            return

        # Auto-priority: compute from module exam date
        mod = self.repo.get_module(mid)
        exam_date_str = mod["exam_date"] if mod else None
        auto_prio = exam_priority(exam_date_str)

        PRIO_COLORS = {
            "Critical": "#E53935", "High": "#F44336",
            "Medium": "#FF9800", "Low": "#4A86E8",
        }
        PRIO_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

        for t in sorted(tasks, key=lambda x: (x["status"] == "Done", PRIO_ORDER.get(auto_prio, 3))):
            is_done = t["status"] == "Done"
            row = QFrame()
            row.setObjectName("Card")
            rly = QHBoxLayout(row)
            rly.setContentsMargins(10, 7, 10, 7)
            rly.setSpacing(10)

            cb = QCheckBox()
            cb.setChecked(is_done)
            cb.setFixedSize(18, 18)

            title_lbl = QLabel(t["title"])
            title_lbl.setStyleSheet(
                f"font-size:12px;"
                f"color:{_tc('#706C86','#6B7280') if is_done else _tc('#1A1A2E','#CDD6F4')};"
                f"{'text-decoration:line-through;' if is_done else ''}"
            )
            title_lbl.setWordWrap(False)

            # Show auto-computed priority badge (based on exam date)
            pc = PRIO_COLORS.get(auto_prio, "#706C86")
            prio_lbl = QLabel(auto_prio)
            prio_lbl.setStyleSheet(
                f"background:{pc}22;color:{pc};"
                f"border-radius:6px;padding:1px 7px;font-size:10px;font-weight:700;"
            )
            prio_lbl.setToolTip("Priorität automatisch berechnet aus Prüfungsdatum")

            due_lbl = QLabel(f"📅 {t['due_date']}" if t["due_date"] else "")
            due_lbl.setStyleSheet(f"font-size:10px;color:{_tc('#706C86','#6B7280')};")

            rly.addWidget(cb)
            rly.addWidget(title_lbl, 1)
            rly.addWidget(prio_lbl)
            rly.addWidget(due_lbl)

            def _toggle_task(state, _tid=t["id"], _lbl=title_lbl):
                new_status = "Done" if state else "Open"
                self.repo.update_task(_tid, status=new_status)
                _lbl.setStyleSheet(
                    f"font-size:12px;"
                    f"color:{_tc('#706C86','#6B7280') if new_status == 'Done' else _tc('#1A1A2E','#CDD6F4')};"
                    f"{'text-decoration:line-through;' if new_status == 'Done' else ''}"
                )
                # Defer rebuild — calling it directly inside stateChanged destroys
                # the checkbox widget while its signal is still on the stack → crash
                if self._global_refresh:
                    QTimer.singleShot(0, self._global_refresh)
                else:
                    QTimer.singleShot(0, lambda: self._load_tasks(self._selected_mid))

            cb.stateChanged.connect(_toggle_task)
            self._task_list_lay.addWidget(row)

        self._task_list_lay.addStretch()

    def _add_task_inline(self):
        """Open TaskDialog pre-set to the current module; sync all pages on save."""
        if TaskDialog(self.repo, default_module_id=self._selected_mid, parent=self).exec():
            if self._global_refresh:
                self._global_refresh()
            else:
                self.refresh()

    def _add_topic(self):
        if not self._selected_mid:
            QMessageBox.warning(self, "Hinweis", "Bitte zuerst ein Modul auswahlen.")
            return
        if TopicDialog(self.repo, self._selected_mid, parent=self).exec():
            if self._global_refresh:
                self._global_refresh()
            else:
                self._load_topics()

    def _edit_topic(self):
        row = self.topic_table.currentRow()
        if row < 0 or not self._selected_mid:
            return
        tid = int(self.topic_table.item(row, 5).text())
        if TopicDialog(self.repo, self._selected_mid, topic_id=tid, parent=self).exec():
            if self._global_refresh:
                self._global_refresh()
            else:
                self._load_topics()

    def _delete_topic(self):
        row = self.topic_table.currentRow()
        if row < 0:
            return
        tid = int(self.topic_table.item(row, 5).text())
        if QMessageBox.question(self, "Löschen", "Thema löschen?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_topic(tid)
            if self._global_refresh:
                self._global_refresh()
            else:
                self._load_topics()


class TimerPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._running = False
        self._total = 25 * 60
        self._remaining = 25 * 60
        self._start_ts: Optional[int] = None
        self._session_count = 0          # total sessions this page-visit
        self._pomodoro_cycle = 0         # 0-3 within current 4-session block
        self._is_break = False           # currently in break phase
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

        self.mode_lbl = QLabel("🎯  Fokus-Phase")
        self.mode_lbl.setAlignment(Qt.AlignCenter)
        self.mode_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #7C3AED;")
        lay.addWidget(self.mode_lbl)

        self.session_lbl = QLabel("Sitzungen: 0")
        self.session_lbl.setAlignment(Qt.AlignCenter)
        self.session_lbl.setStyleSheet("color: #6B7280; font-size: 13px;")
        lay.addWidget(self.session_lbl)

        # Pomodoro cycle dots: 🍅🍅🍅🍅
        self.cycle_lbl = QLabel("🍅 ○ ○ ○")
        self.cycle_lbl.setAlignment(Qt.AlignCenter)
        self.cycle_lbl.setStyleSheet("font-size: 18px; letter-spacing: 4px;")
        lay.addWidget(self.cycle_lbl)

        # Auto-Pomodoro toggle
        self.auto_pomo_cb = QCheckBox("  Auto-Pomodoro  (Pause startet automatisch nach Fokus-Phase)")
        self.auto_pomo_cb.setChecked(True)
        lay.addWidget(self.auto_pomo_cb, 0, Qt.AlignCenter)

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
        # Retranslate mode label and session count
        if not self._running and not self._is_break:
            self.mode_lbl.setText(f"🎯  {tr('timer.focus')}")
            self.mode_lbl.setStyleSheet("font-size:16px;font-weight:bold;color:#7C3AED;")
        self.session_lbl.setText(tr("sec.sessions").format(n=self._session_count))
        self.note_edit.setPlaceholderText(tr("timer.note"))
        if not self._running:
            self.start_btn.setText(tr("timer.start"))
        self._update_cycle_display()

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
        if mins <= 15:
            self._is_break = True
            self.mode_lbl.setText(f"🌿  {tr('timer.break')} ({mins} min)")
            self.mode_lbl.setStyleSheet("font-size:16px;font-weight:bold;color:#10B981;")
            self.circle._color = "#10B981"
        else:
            self._is_break = False
            self.mode_lbl.setText(f"🎯  {tr('timer.focus')}")
            self.mode_lbl.setStyleSheet("font-size:16px;font-weight:bold;color:#7C3AED;")
            self.circle._color = "#7C3AED"
        self._update_cycle_display()
        self._update_circle()

    def _toggle(self):
        if self._running:
            self._running = False
            self._qtimer.stop()
            self.start_btn.setText(tr("timer.start"))
        else:
            self._running = True
            if not self._start_ts:
                self._start_ts = int(_time.time())
            self._qtimer.start()
            self.start_btn.setText(tr("timer.stop"))

    def _reset(self):
        self._running = False
        self._qtimer.stop()
        self._remaining = self._total
        self._start_ts = None
        self.start_btn.setText(tr("timer.start"))
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

    def _update_cycle_display(self):
        """Update the 🍅 cycle indicator dots."""
        dots = []
        for i in range(4):
            if i < self._pomodoro_cycle:
                dots.append("🍅")
            elif i == self._pomodoro_cycle and not self._is_break:
                dots.append("⏳")
            else:
                dots.append("○")
        self.cycle_lbl.setText("  ".join(dots))

    def _on_complete(self):
        was_break = self._is_break
        mid = self.mod_cb.currentData()

        if not was_break:
            # Completed a focus session
            self._session_count += 1
            self.session_lbl.setText(tr("sec.sessions").format(n=self._session_count))
            self._pomodoro_cycle += 1
            if mid and self._start_ts:
                end_ts = int(_time.time())
                note = self.note_edit.text().strip()
                self.repo.add_time_log(mid, self._start_ts, end_ts, self._total, "pomodoro", note)
                self.note_edit.clear()
            self._start_ts = None
            # Lern-Rückblick dialog
            dlg = LernRueckblickDialog(self.repo, mid, parent=self)
            dlg.exec()
            if self._global_refresh:
                QTimer.singleShot(0, self._global_refresh)

            # Auto-Pomodoro: set up break
            if self.auto_pomo_cb.isChecked():
                long_break = (self._pomodoro_cycle >= 4)
                break_mins = 15 if long_break else 5
                self._is_break = True
                self._total = break_mins * 60
                self._remaining = break_mins * 60
                self.mode_lbl.setText(f"{'☕  Lange Pause' if long_break else '🌿  Kurze Pause'} ({break_mins} min)")
                self.mode_lbl.setStyleSheet("font-size:16px;font-weight:bold;color:#10B981;")
                self.circle._color = "#10B981"
                self._update_circle()
                self._update_cycle_display()
                if long_break:
                    self._pomodoro_cycle = 0
                # Auto-start break
                self._running = True
                self._qtimer.start()
                self.start_btn.setText(tr("timer.stop"))
            else:
                self._remaining = self._total
                self._update_circle()
                self.start_btn.setText(tr("timer.start"))
        else:
            # Completed a break
            self._is_break = False
            self._total = 25 * 60
            self._remaining = 25 * 60
            self._start_ts = None
            self.mode_lbl.setText("🎯  Fokus-Phase")
            self.mode_lbl.setStyleSheet("font-size:16px;font-weight:bold;color:#7C3AED;")
            self.circle._color = "#7C3AED"
            self._update_circle()
            self._update_cycle_display()
            self.start_btn.setText(tr("timer.start"))


class ExamPage(QWidget):
    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._selected_mid: Optional[int] = None
        self._global_refresh: Optional[callable] = None
        self._build()

    def set_global_refresh(self, cb):
        self._global_refresh = cb

    # ── layout ───────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel(tr("page.exams"))
        title.setObjectName("PageTitle")
        outer.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # ── Left: exam list ──────────────────────────────────────────────────
        left_w = QWidget()
        left_w.setAttribute(Qt.WA_StyledBackground, True)
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(0)

        self._list_w = QWidget()
        self._list_lay = QVBoxLayout(self._list_w)
        self._list_lay.setContentsMargins(0, 0, 8, 0)
        self._list_lay.setSpacing(8)
        left_lay.addWidget(make_scroll(self._list_w), 1)
        splitter.addWidget(left_w)

        # ── Right: checklist detail panel ────────────────────────────────────
        right_w = QWidget()
        right_w.setAttribute(Qt.WA_StyledBackground, True)
        self._right_lay = QVBoxLayout(right_w)
        self._right_lay.setContentsMargins(16, 0, 0, 0)
        self._right_lay.setSpacing(12)
        self._right_lay.addWidget(self._empty_right())
        splitter.addWidget(right_w)

        splitter.setSizes([420, 560])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        outer.addWidget(splitter, 1)

    @staticmethod
    def _empty_right() -> QLabel:
        lbl = QLabel("← Prüfung auswählen um\ndie Lernziel-Checkliste zu sehen")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color:{_tc('#706C86','#6B7280')};font-size:14px;")
        return lbl

    # ── data loading ─────────────────────────────────────────────────────────

    def refresh(self):
        # Rebuild exam list
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Apply global semester filter
        sem_f = _active_sem_filter(self.repo)
        exams = _filter_mods_by_sem(self.repo.all_exams(), sem_f)

        if not exams:
            lbl = QLabel("Keine Prüfungen erfasst.\nPrüfungsdaten in den Modulen hinzufügen.")
            lbl.setStyleSheet(f"color:{_tc('#706C86','#6B7280')};font-size:13px;")
            lbl.setAlignment(Qt.AlignCenter)
            self._list_lay.addWidget(lbl)
        else:
            for m in exams:
                self._list_lay.addWidget(self._make_card(m))
        self._list_lay.addStretch()

        # Re-populate detail if a module was already selected
        if self._selected_mid is not None:
            self._populate_detail(self._selected_mid)

    def _make_card(self, m) -> QFrame:
        mid = m["id"]
        color = mod_color(mid)
        selected = (mid == self._selected_mid)

        card = QFrame()
        card.setObjectName("Card")
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(
            f"QFrame#Card{{border:2px solid "
            f"{'#4A86E8' if selected else _tc('#E4E8F0','#2A2A3A')};border-radius:8px;}}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(7)

        # Header row
        hdr = QHBoxLayout()
        hdr.addWidget(ColorDot(color, 12))
        name_lbl = QLabel(m["name"])
        name_lbl.setStyleSheet(
            f"font-size:14px;font-weight:700;color:{_tc('#1A1A2E','#CDD6F4')};"
        )
        hdr.addWidget(name_lbl, 1)

        d = days_until(m["exam_date"])
        if d is None:   d_txt, d_col = "Kein Datum", "#9E9E9E"
        elif d < 0:     d_txt, d_col = f"Vor {abs(d)} T.", "#9E9E9E"
        elif d == 0:    d_txt, d_col = "HEUTE!", "#F44336"
        elif d <= 7:    d_txt, d_col = f"in {d} T.", "#FF9800"
        else:           d_txt, d_col = f"in {d} T.", "#4A86E8"
        date_lbl = QLabel(f"📅 {m['exam_date']}  ·  {d_txt}")
        date_lbl.setStyleSheet(f"font-size:11px;color:{d_col};font-weight:700;")
        hdr.addWidget(date_lbl)
        lay.addLayout(hdr)

        # Study-hour progress bar
        target   = self.repo.ects_target_hours(mid)
        studied_h = self.repo.seconds_studied_for_module(mid) / 3600
        pct = min(100, int(studied_h / target * 100)) if target > 0 else 0
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setFixedHeight(6)
        bar.setTextVisible(False)
        bar.setStyleSheet(
            f"QProgressBar{{background:{_tc('#EAEAEA','#2A2A3A')};border-radius:3px;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:3px;}}"
        )
        lay.addWidget(bar)

        # Objective checklist progress
        objs = self.repo.list_scraped_data(mid, "objective")
        tasks_m  = self.repo.list_tasks(module_id=mid)
        t_done_m = sum(1 for t in tasks_m if t["status"] == "Done")
        t_total_m = len(tasks_m)
        tasks_txt = f"  ·  ☑ {t_done_m}/{t_total_m} Aufgaben" if t_total_m else ""
        if objs:
            done = sum(1 for o in objs if int(o["checked"] if "checked" in o.keys() and o["checked"] is not None else 0))
            total = len(objs)
            obj_pct = int(done / total * 100) if total else 0
            obj_bar = QProgressBar()
            obj_bar.setRange(0, 100)
            obj_bar.setValue(obj_pct)
            obj_bar.setFixedHeight(6)
            obj_bar.setTextVisible(False)
            obj_bar.setStyleSheet(
                f"QProgressBar{{background:{_tc('#EAEAEA','#2A2A3A')};border-radius:3px;}}"
                f"QProgressBar::chunk{{background:#2CB67D;border-radius:3px;}}"
            )
            lay.addWidget(obj_bar)
            meta = QLabel(
                f"📚 {studied_h:.1f}h / {target:.0f}h  ·  "
                f"✅ {done}/{total} Lernziele{tasks_txt}"
            )
        else:
            meta = QLabel(
                f"📚 {studied_h:.1f}h / {target:.0f}h  ·  "
                f"Keine Lernziele{tasks_txt}"
            )
        meta.setStyleSheet(f"font-size:11px;color:{_tc('#706C86','#6B7280')};")
        lay.addWidget(meta)

        # Click handler
        def _on_click(_, _mid=mid):
            self._selected_mid = _mid
            self.refresh()

        card.mousePressEvent = _on_click
        return card

    # ── right panel ───────────────────────────────────────────────────────────

    def _clear_right(self):
        while self._right_lay.count():
            item = self._right_lay.takeAt(0)
            if item.widget():
                item.widget().hide()       # hide immediately so old widgets don't overlap new ones
                item.widget().deleteLater()

    def _populate_detail(self, mid: int):
        self._clear_right()
        m = self.repo.get_module(mid)
        if not m:
            self._right_lay.addWidget(self._empty_right())
            return

        color = mod_color(mid)

        # ── Module header ─────────────────────────────────────────────────────
        hdr_frame = QFrame()
        hdr_frame.setObjectName("Card")
        hdr_lay = QVBoxLayout(hdr_frame)
        hdr_lay.setContentsMargins(16, 14, 16, 14)
        hdr_lay.setSpacing(6)

        name_row = QHBoxLayout()
        dot = ColorDot(color, 14)
        name_row.addWidget(dot)
        name_lbl = QLabel(m["name"])
        name_lbl.setStyleSheet(
            f"font-size:16px;font-weight:800;color:{_tc('#1A1A2E','#CDD6F4')};"
        )
        name_row.addWidget(name_lbl, 1)

        # + Lernziel button
        add_obj_btn = QPushButton("+ Lernziel")
        add_obj_btn.setStyleSheet(
            f"QPushButton{{background:{_tc('#F0F7FF','#1A2A3A')};color:#4A86E8;"
            f"border:1px solid #4A86E840;border-radius:6px;padding:4px 10px;font-size:11px;}}"
            f"QPushButton:hover{{background:#4A86E820;}}"
        )
        add_obj_btn.setToolTip("Lernziel manuell hinzufügen")
        add_obj_btn.clicked.connect(lambda: self._add_objective_inline(mid))
        name_row.addWidget(add_obj_btn)

        # Reset button
        reset_btn = QPushButton("↺ Reset")
        reset_btn.setStyleSheet(
            f"QPushButton{{background:{_tc('#FFF0F0','#2A1A1A')};color:#F44336;"
            f"border:1px solid #F4433640;border-radius:6px;padding:4px 10px;font-size:11px;}}"
            f"QPushButton:hover{{background:#F4433620;}}"
        )
        reset_btn.setToolTip("Alle Lernziele als unbearbeitet markieren")
        reset_btn.clicked.connect(lambda: self._reset_objectives(mid))
        name_row.addWidget(reset_btn)
        hdr_lay.addLayout(name_row)

        d = days_until(m["exam_date"])
        if d is None:   d_txt, d_col = "Kein Prüfungsdatum", "#9E9E9E"
        elif d < 0:     d_txt, d_col = f"Prüfung war vor {abs(d)} Tagen", "#9E9E9E"
        elif d == 0:    d_txt, d_col = "PRÜFUNG HEUTE!", "#F44336"
        elif d <= 7:    d_txt, d_col = f"Prüfung in {d} Tagen — bald!", "#FF9800"
        else:           d_txt, d_col = f"Prüfung in {d} Tagen  ({m['exam_date']})", "#4A86E8"
        date_lbl = QLabel(f"📅  {d_txt}")
        date_lbl.setStyleSheet(f"font-size:13px;color:{d_col};font-weight:700;")
        hdr_lay.addWidget(date_lbl)

        self._right_lay.addWidget(hdr_frame)

        # ── Lernziele checklist ───────────────────────────────────────────────
        objs = self.repo.list_scraped_data(mid, "objective")
        if not objs:
            no_lbl = QLabel(
                "Keine Lernziele vorhanden.\n"
                "PDF-Import in den Modul-Einstellungen starten."
            )
            no_lbl.setAlignment(Qt.AlignCenter)
            no_lbl.setStyleSheet(f"color:{_tc('#706C86','#6B7280')};font-size:13px;margin-top:24px;")
            self._right_lay.addWidget(no_lbl)
            self._right_lay.addStretch()
            return

        done  = sum(1 for o in objs if int(o["checked"] if "checked" in o.keys() and o["checked"] is not None else 0))
        total = len(objs)

        # Progress summary bar
        summary_frame = QFrame()
        summary_frame.setObjectName("Card")
        sl = QHBoxLayout(summary_frame)
        sl.setContentsMargins(14, 10, 14, 10)
        sl.setSpacing(12)
        self._obj_progress_lbl = QLabel()
        self._obj_progress_lbl.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{_tc('#1A1A2E','#CDD6F4')};"
        )
        sl.addWidget(self._obj_progress_lbl)
        sl.addStretch()
        self._obj_bar = QProgressBar()
        self._obj_bar.setRange(0, 100)
        self._obj_bar.setFixedHeight(8)
        self._obj_bar.setFixedWidth(160)
        self._obj_bar.setTextVisible(False)
        self._obj_bar.setStyleSheet(
            f"QProgressBar{{background:{_tc('#EAEAEA','#2A2A3A')};border-radius:4px;}}"
            f"QProgressBar::chunk{{background:#2CB67D;border-radius:4px;}}"
        )
        sl.addWidget(self._obj_bar)
        self._right_lay.addWidget(summary_frame)
        self._update_obj_progress(done, total)

        # Checklist scroll area
        checklist_w = QWidget()
        checklist_w.setAttribute(Qt.WA_StyledBackground, True)
        checklist_lay = QVBoxLayout(checklist_w)
        checklist_lay.setContentsMargins(0, 0, 0, 0)
        checklist_lay.setSpacing(4)

        section_lbl = QLabel("Lernziele")
        section_lbl.setObjectName("SectionTitle")
        checklist_lay.addWidget(section_lbl)

        for obj in objs:
            obj_id  = obj["id"]
            checked = bool(int(obj["checked"] if "checked" in obj.keys() and obj["checked"] is not None else 0))
            row = self._make_obj_row(obj_id, obj["title"], checked, mid)
            checklist_lay.addWidget(row)

        # ── Aufgaben section ──────────────────────────────────────────────────
        all_tasks = self.repo.list_tasks(module_id=mid)
        t_done_count = sum(1 for t in all_tasks if t["status"] == "Done")

        # Horizontal rule separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(
            f"color:{_tc('#E4E8F0','#2A2A3A')};margin-top:10px;margin-bottom:2px;"
        )
        checklist_lay.addWidget(sep)

        # Check for knowledge weaknesses in this module
        topics = self.repo.list_topics(mid)
        weak_count = sum(1 for tp in topics if int(tp["knowledge_level"]) <= 1)
        has_weak = weak_count > 0

        # Tasks header row
        t_hdr_lay = QHBoxLayout()
        t_hdr_lay.setContentsMargins(0, 4, 0, 0)
        t_title_lbl = QLabel("Aufgaben")
        t_title_lbl.setObjectName("SectionTitle")
        t_hdr_lay.addWidget(t_title_lbl)
        t_hdr_lay.addStretch()
        t_stats_lbl = QLabel(f"☑ {t_done_count} / {len(all_tasks)} erledigt")
        t_stats_lbl.setStyleSheet(f"font-size:11px;color:{_tc('#706C86','#6B7280')};")
        t_hdr_lay.addWidget(t_stats_lbl)
        checklist_lay.addLayout(t_hdr_lay)

        # Knowledge-weakness warning banner
        if has_weak:
            warn_frame = QFrame()
            warn_frame.setStyleSheet(
                "background:#FF980018;border-radius:5px;"
            )
            warn_inner = QHBoxLayout(warn_frame)
            warn_inner.setContentsMargins(8, 5, 8, 5)
            warn_lbl = QLabel(
                f"⚠️  {weak_count} Thema(en) mit Wissenslücken — Aufgaben priorisiert"
            )
            warn_lbl.setStyleSheet(
                "font-size:11px;color:#FF9800;font-weight:600;"
            )
            warn_inner.addWidget(warn_lbl)
            checklist_lay.addWidget(warn_frame)

        if not all_tasks:
            no_t = QLabel("Keine Aufgaben für dieses Modul erstellt.")
            no_t.setStyleSheet(
                f"color:{_tc('#706C86','#6B7280')};font-size:12px;margin:4px 0 8px 0;"
            )
            checklist_lay.addWidget(no_t)
        else:
            PRIO_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
            sorted_tasks = sorted(
                all_tasks,
                key=lambda t: (t["status"] == "Done", PRIO_ORDER.get(t["priority"], 4))
            )
            for t in sorted_tasks:
                checklist_lay.addWidget(self._make_exam_task_row(t, mid))

        checklist_lay.addStretch()
        self._right_lay.addWidget(make_scroll(checklist_w), 1)

    def _add_objective_inline(self, mid: int):
        """Lightweight dialog to manually add a Lernziel to this module."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Lernziel hinzufügen")
        dlg.setMinimumWidth(400)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setWindowModality(Qt.ApplicationModal)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(10)

        title_edit = QLineEdit()
        title_edit.setPlaceholderText("Lernziel-Titel *")
        lay.addWidget(title_edit)

        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText("Beschreibung / Details (optional)")
        notes_edit.setMaximumHeight(80)
        lay.addWidget(notes_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        lay.addWidget(btns)

        def _save():
            title = title_edit.text().strip()
            if not title:
                QMessageBox.warning(dlg, "Fehler", "Titel darf nicht leer sein.")
                return
            # Count existing objectives to set sort_order
            existing = self.repo.list_scraped_data(mid, "objective")
            sort_order = len(existing)
            self.repo.conn.execute(
                "INSERT INTO module_scraped_data"
                "(module_id, data_type, title, body, weight, sort_order) "
                "VALUES (?, 'objective', ?, ?, 0, ?)",
                (mid, title, notes_edit.toPlainText().strip(), sort_order),
            )
            self.repo.conn.commit()
            dlg.accept()
            # Defer so the dialog fully closes before we rebuild widgets
            if self._global_refresh:
                QTimer.singleShot(0, self._global_refresh)
            else:
                QTimer.singleShot(0, self.refresh)

        btns.accepted.connect(_save)
        btns.rejected.connect(dlg.reject)
        dlg.exec()

    def _make_exam_task_row(self, t, mid: int) -> QFrame:
        """Task row for the ExamPage detail panel with exam-date-based priority."""
        is_done = t["status"] == "Done"
        PRIO_COLORS = {
            "Critical": "#E53935", "High": "#F44336",
            "Medium": "#FF9800", "Low": "#4A86E8",
        }

        # Compute priority from module exam date
        mod = self.repo.get_module(mid)
        exam_date_str = mod["exam_date"] if mod else None
        auto_prio = exam_priority(exam_date_str)

        row = QFrame()
        row.setObjectName("Card")
        rly = QHBoxLayout(row)
        rly.setContentsMargins(12, 7, 12, 7)
        rly.setSpacing(10)

        cb = QCheckBox()
        cb.setChecked(is_done)
        cb.setFixedSize(18, 18)
        rly.addWidget(cb)

        title_lbl = QLabel(t["title"])
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(
            f"font-size:12px;"
            f"color:{_tc('#706C86','#6B7280') if is_done else _tc('#1A1A2E','#CDD6F4')};"
            f"{'text-decoration:line-through;' if is_done else ''}"
        )
        rly.addWidget(title_lbl, 1)

        # Auto-priority badge (from exam date)
        pc = PRIO_COLORS.get(auto_prio, "#706C86")
        prio_lbl = QLabel(auto_prio)
        prio_lbl.setStyleSheet(
            f"background:{pc}22;color:{pc};"
            f"border-radius:5px;padding:1px 6px;font-size:10px;font-weight:700;"
        )
        prio_lbl.setToolTip("Priorität automatisch berechnet aus Prüfungsdatum")
        rly.addWidget(prio_lbl)

        if t["due_date"]:
            due_lbl = QLabel(f"📅 {t['due_date']}")
            due_lbl.setStyleSheet(f"font-size:10px;color:{_tc('#706C86','#6B7280')};")
            rly.addWidget(due_lbl)

        def _toggle(state, _tid=t["id"], _mid=mid):
            new_status = "Done" if state else "Open"
            self.repo.update_task(_tid, status=new_status)
            self._selected_mid = _mid
            # Defer — destroying widgets inside stateChanged causes free() crash
            if self._global_refresh:
                QTimer.singleShot(0, self._global_refresh)
            else:
                QTimer.singleShot(0, self.refresh)

        cb.stateChanged.connect(_toggle)
        return row

    def _make_obj_row(self, obj_id: int, title: str, checked: bool, mid: int) -> QFrame:
        row = QFrame()
        row.setObjectName("Card")
        rly = QHBoxLayout(row)
        rly.setContentsMargins(12, 8, 12, 8)
        rly.setSpacing(10)

        cb = QCheckBox()
        cb.setChecked(checked)
        cb.setFixedSize(18, 18)
        rly.addWidget(cb)

        lbl = QLabel(title)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"font-size:12px;color:{_tc('#1A1A2E','#CDD6F4') if not checked else _tc('#706C86','#6B7280')};"
            f"{'text-decoration:line-through;' if checked else ''}"
        )
        rly.addWidget(lbl, 1)

        def _toggle(state, _oid=obj_id, _mid=mid, _lbl=lbl):
            is_checked = bool(state)
            self.repo.set_objective_checked(_oid, is_checked)
            _lbl.setStyleSheet(
                f"font-size:12px;"
                f"color:{_tc('#706C86','#6B7280') if is_checked else _tc('#1A1A2E','#CDD6F4')};"
                f"{'text-decoration:line-through;' if is_checked else ''}"
            )
            # Update progress live
            objs = self.repo.list_scraped_data(_mid, "objective")
            done  = sum(1 for o in objs if int(o["checked"] if "checked" in o.keys() and o["checked"] is not None else 0))
            self._update_obj_progress(done, len(objs))

        cb.stateChanged.connect(_toggle)
        return row

    def _update_obj_progress(self, done: int, total: int):
        pct = int(done / total * 100) if total else 0
        self._obj_progress_lbl.setText(f"✅ {done} / {total} Lernziele abgehakt  ({pct}%)")
        self._obj_bar.setValue(pct)

    def _reset_objectives(self, mid: int):
        if QMessageBox.question(
            self, "Reset", "Alle Lernziele als unbearbeitet markieren?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.repo.reset_objectives_checked(mid)
            self._selected_mid = mid
            if self._global_refresh:
                self._global_refresh()
            else:
                self.refresh()


class GradesPage(QWidget):
    """Noten-Übersicht — realitätsnah am Schweizer FH-Notensystem (1–6) ausgerichtet.

    Aufbau:
      • KPI-Leiste: Gesamt-GPA (ECTS-gewichtet), bestandene Module, kritische Module
      • Semester-Filter + Modulübersicht als Ampel-Cards (scrollbar)
      • Detailpanel rechts: einzelne Prüfungsleistungen des gewählten Moduls
        mit Note 1–6, Gewichtung und Zielvergleich
    """

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._sel_module_id: Optional[int] = None   # currently selected module
        self._build()

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        # Header ──────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel(tr("page.grades"))
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = QPushButton("+ Note hinzufügen")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_grade)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        # KPI cards ───────────────────────────────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        self._kpi_gpa   = self._make_kpi_card("Gesamt-GPA", "—", "ECTS-gewichtet")
        self._kpi_pass  = self._make_kpi_card("Bestanden", "—/—", "Module ≥ 4.0")
        self._kpi_warn  = self._make_kpi_card("⚠ Kritisch", "—", "< 4.0 · Handlungsbedarf")
        for card, _v, _s in (self._kpi_gpa, self._kpi_pass, self._kpi_warn):
            kpi_row.addWidget(card)
        kpi_row.addStretch()
        lay.addLayout(kpi_row)

        # Semester filter ─────────────────────────────────────────────────────
        filt_row = QHBoxLayout()
        filt_lbl = QLabel("Semester:")
        filt_lbl.setStyleSheet("font-size: 12px;")
        filt_row.addWidget(filt_lbl)
        self.sem_filter = QComboBox()
        self.sem_filter.setFixedWidth(160)
        self.sem_filter.currentIndexChanged.connect(self._rebuild_cards)
        filt_row.addWidget(self.sem_filter)
        filt_row.addStretch()
        # Note-Info label (Swiss grading reminder)
        info = QLabel("Notensystem 1–6  ·  Bestehensgrenze ≥ 4.0  ·  60 % = Note 4.0")
        info.setStyleSheet(f"font-size: 11px; color: {_tc('#888','#aaa')};")
        filt_row.addWidget(info)
        lay.addLayout(filt_row)

        # Main splitter: left=module cards, right=detail ──────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── LEFT: Modulübersicht ──────────────────────────────────────────────
        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        cards_lbl = QLabel("Modulübersicht")
        cards_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        left_lay.addWidget(cards_lbl)

        self._cards_scroll = QScrollArea()
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setFrameShape(QFrame.NoFrame)
        self._cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._cards_w = QWidget()
        self._cards_lay = QVBoxLayout(self._cards_w)
        self._cards_lay.setContentsMargins(2, 2, 2, 2)
        self._cards_lay.setSpacing(6)
        self._cards_lay.addStretch()
        self._cards_scroll.setWidget(self._cards_w)
        left_lay.addWidget(self._cards_scroll, 1)

        # ── RIGHT: Detailpanel ────────────────────────────────────────────────
        right_w = QWidget()
        right_lay = QVBoxLayout(right_w)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(8)

        # Module name + grade display
        self._detail_name = QLabel("← Modul auswählen")
        self._detail_name.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._detail_name.setWordWrap(True)
        right_lay.addWidget(self._detail_name)

        # Grade + status bar
        grade_row = QHBoxLayout()
        self._detail_grade = QLabel()
        self._detail_grade.setStyleSheet("font-size: 32px; font-weight: bold;")
        grade_row.addWidget(self._detail_grade)
        self._detail_status = QLabel()
        self._detail_status.setStyleSheet("font-size: 14px; font-weight: bold;")
        grade_row.addWidget(self._detail_status)
        grade_row.addStretch()
        self._detail_target = QLabel()
        self._detail_target.setStyleSheet("font-size: 12px;")
        grade_row.addWidget(self._detail_target)
        right_lay.addLayout(grade_row)

        # Progress bar for the module grade
        self._detail_bar = QProgressBar()
        self._detail_bar.setRange(0, 100)
        self._detail_bar.setTextVisible(False)
        self._detail_bar.setFixedHeight(6)
        right_lay.addWidget(self._detail_bar)

        # Prediction label (what grade is needed next?)
        self._detail_predict = QLabel()
        self._detail_predict.setStyleSheet(f"font-size: 11px; color: {_tc('#555','#aaa')};")
        self._detail_predict.setWordWrap(True)
        right_lay.addWidget(self._detail_predict)

        # Assessment table (Einzelnoten)
        detail_hdr = QLabel("Einzelleistungen")
        detail_hdr.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 6px;")
        right_lay.addWidget(detail_hdr)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Titel", "Eingabe", "Note (1–6)", "Gewicht %", "Datum", "ID"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnHidden(5, True)   # hidden ID column
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._edit_grade)
        self.table.setAlternatingRowColors(True)
        right_lay.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        edit_btn = QPushButton("✏ Bearbeiten")
        edit_btn.clicked.connect(self._edit_grade)
        del_btn = QPushButton("🗑 Löschen")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_grade)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        right_lay.addLayout(btn_row)

        splitter.addWidget(left_w)
        splitter.addWidget(right_w)
        splitter.setSizes([340, 560])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        lay.addWidget(splitter, 1)

    # ── KPI card factory ─────────────────────────────────────────────────────

    def _make_kpi_card(self, label: str, value: str, sublabel: str):
        """Returns (card_widget, value_label, sublabel_label)."""
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(186)
        card.setFixedHeight(88)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(2)
        lbl_w = QLabel(label)
        lbl_w.setStyleSheet(f"font-size: 11px; color: {_tc('#666','#aaa')};")
        val_w = QLabel(value)
        val_w.setStyleSheet("font-size: 26px; font-weight: bold;")
        sub_w = QLabel(sublabel)
        sub_w.setStyleSheet(f"font-size: 10px; color: {_tc('#888','#888')};")
        cl.addWidget(lbl_w)
        cl.addWidget(val_w)
        cl.addWidget(sub_w)
        return card, val_w, sub_w

    # ── Refresh (called from MainWindow on page switch) ───────────────────────

    def refresh(self):
        # Rebuild semester selector
        sem_f = _active_sem_filter(self.repo)
        mods_all = _filter_mods_by_sem(self.repo.list_modules("all"), sem_f)
        sems = sorted({str(m["semester"]) for m in mods_all if m["semester"]},
                      key=lambda s: int(s) if s.isdigit() else 99)

        cur_sem = self.sem_filter.currentData()
        self.sem_filter.blockSignals(True)
        self.sem_filter.clear()
        self.sem_filter.addItem("Alle Semester", "")
        for s in sems:
            self.sem_filter.addItem(f"Semester {s}", s)
        # Restore selection
        for i in range(self.sem_filter.count()):
            if self.sem_filter.itemData(i) == cur_sem:
                self.sem_filter.setCurrentIndex(i)
                break
        self.sem_filter.blockSignals(False)

        self._update_kpis()
        self._rebuild_cards()

    # ── KPI update ────────────────────────────────────────────────────────────

    def _update_kpis(self):
        all_mods = self.repo.list_modules("all")
        plan_mods = [m for m in all_mods
                     if (int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1)]

        graded = 0
        passed = 0
        critical = 0
        for m in plan_mods:
            avg = self.repo.module_weighted_grade(m["id"])
            if avg is None:
                continue
            ch = pct_to_ch_grade(avg)
            graded += 1
            if ch >= 4.0:
                passed += 1
            if ch < 4.0:
                critical += 1

        gpa = self.repo.ects_weighted_gpa()
        if gpa is not None:
            gpa_lbl = f"{gpa:.2f}"
            col = _grade_color(gpa)
            self._kpi_gpa[1].setText(gpa_lbl)
            self._kpi_gpa[1].setStyleSheet(f"font-size: 26px; font-weight: bold; color: {col};")
        else:
            self._kpi_gpa[1].setText("—")
            self._kpi_gpa[1].setStyleSheet("font-size: 26px; font-weight: bold;")

        self._kpi_pass[1].setText(f"{passed}/{graded}" if graded else "—/—")
        self._kpi_pass[1].setStyleSheet(
            f"font-size: 26px; font-weight: bold; "
            f"color: {_tc('#2E7D32','#4CAF50') if passed == graded and graded > 0 else _tc('#888','#aaa')};"
        )

        warn_col = _tc("#B71C1C", "#EF5350") if critical > 0 else _tc("#888", "#aaa")
        self._kpi_warn[1].setText(str(critical) if graded else "—")
        self._kpi_warn[1].setStyleSheet(
            f"font-size: 26px; font-weight: bold; color: {warn_col};"
        )

    # ── Module cards ─────────────────────────────────────────────────────────

    def _rebuild_cards(self):
        # Clear existing cards (keep trailing stretch)
        while self._cards_lay.count() > 1:
            item = self._cards_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sem_f = _active_sem_filter(self.repo)
        sel_sem = self.sem_filter.currentData() or ""
        mods = _filter_mods_by_sem(self.repo.list_modules("all"), sem_f)
        if sel_sem:
            mods = [m for m in mods if str(m["semester"]) == sel_sem]
        # Sort: in-plan first, then by semester, then name
        mods = sorted(mods,
                      key=lambda m: (
                          0 if (int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1) else 1,
                          int(m["semester"]) if str(m["semester"]).isdigit() else 99,
                          m["name"]
                      ))

        for m in mods:
            card = self._make_module_card(m)
            self._cards_lay.insertWidget(self._cards_lay.count() - 1, card)

        # If selected module still exists, keep its detail; else reset
        if self._sel_module_id not in {m["id"] for m in mods}:
            self._sel_module_id = None
            self._clear_detail()

    def _make_module_card(self, m) -> QFrame:
        """Build a compact module card with Ampel-color and grade display."""
        in_plan = int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1
        avg_pct = self.repo.module_weighted_grade(m["id"])
        has_grade = avg_pct is not None

        if has_grade:
            ch = pct_to_ch_grade(avg_pct)
            bg = _grade_bg(ch)
            border = _grade_border(ch)
        else:
            bg = _tc("#F5F5F5", "#2A2A2A")
            border = _tc("#DDD", "#444")

        is_selected = (m["id"] == self._sel_module_id)
        sel_border = _tc("#7C3AED", "#A78BFA") if is_selected else border

        card = QFrame()
        card.setFixedHeight(84)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 2px solid {sel_border}; "
            f"border-radius: 8px; }} "
            f"QFrame:hover {{ border-color: {_tc('#7C3AED','#A78BFA')}; }}"
        )

        lay = QHBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        # Left: name + meta
        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(m["name"])
        name_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: bold; "
            f"color: {_tc('#333','#eee') if in_plan else _tc('#aaa','#555')};"
            + ("text-decoration: line-through;" if not in_plan else "")
        )
        name_lbl.setWordWrap(True)
        info.addWidget(name_lbl)

        sem_txt = f"Sem. {m['semester']}  ·  {float(m['ects']):.0f} ECTS"
        meta_lbl = QLabel(sem_txt)
        meta_lbl.setStyleSheet(f"font-size: 10px; color: {_tc('#777','#999')};")
        info.addWidget(meta_lbl)

        # Target grade hint
        tg = m["target_grade"] if "target_grade" in m.keys() else None
        if tg is not None and has_grade:
            tg_diff = ch - float(tg)
            tg_icon = "✅" if tg_diff >= 0 else "❌"
            tg_lbl = QLabel(f"{tg_icon} Ziel {float(tg):.1f}  ({tg_diff:+.2f})")
            tg_lbl.setStyleSheet(
                f"font-size: 10px; color: "
                f"{'#2E7D32' if tg_diff >= 0 else '#C62828'};"
            )
            info.addWidget(tg_lbl)
        elif tg is not None:
            tg_lbl = QLabel(f"🎯 Ziel: {float(tg):.1f}")
            tg_lbl.setStyleSheet(f"font-size: 10px; color: {_tc('#777','#999')};")
            info.addWidget(tg_lbl)

        lay.addLayout(info, 1)

        # Right: big grade number
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right.setSpacing(2)
        if has_grade:
            grade_lbl = QLabel(f"{ch:.2f}")
            grade_lbl.setStyleSheet(
                f"font-size: 22px; font-weight: bold; color: {_grade_color(ch)};"
            )
            grade_lbl.setAlignment(Qt.AlignRight)
            status_lbl = QLabel(_grade_icon(ch) + " " + _grade_label(ch))
            status_lbl.setStyleSheet(
                f"font-size: 10px; color: {_grade_color(ch)}; font-weight: bold;"
            )
            status_lbl.setAlignment(Qt.AlignRight)
            right.addWidget(grade_lbl)
            right.addWidget(status_lbl)
        else:
            no_lbl = QLabel("keine\nNoten")
            no_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            no_lbl.setStyleSheet(f"font-size: 10px; color: {_tc('#bbb','#555')};")
            right.addWidget(no_lbl)
        lay.addLayout(right)

        # Click: select module
        card.mousePressEvent = lambda _e, mid=m["id"]: self._select_module(mid)
        return card

    def _select_module(self, module_id: int):
        self._sel_module_id = module_id
        self._rebuild_cards()        # re-render to update selection highlight
        self._load_detail(module_id)

    # ── Detail panel ─────────────────────────────────────────────────────────

    def _clear_detail(self):
        self._detail_name.setText("← Modul auswählen")
        self._detail_grade.setText("")
        self._detail_status.setText("")
        self._detail_target.setText("")
        self._detail_predict.setText("")
        self._detail_bar.setValue(0)
        self.table.setRowCount(0)

    def _load_detail(self, module_id: int):
        mod = self.repo.get_module(module_id)
        if not mod:
            self._clear_detail()
            return

        self._detail_name.setText(mod["name"])
        avg_pct = self.repo.module_weighted_grade(module_id)

        if avg_pct is not None:
            ch = pct_to_ch_grade(avg_pct)
            col = _grade_color(ch)
            self._detail_grade.setText(f"{ch:.2f}")
            self._detail_grade.setStyleSheet(
                f"font-size: 32px; font-weight: bold; color: {col};"
            )
            self._detail_status.setText(f"{_grade_icon(ch)}  {_grade_label(ch)}")
            self._detail_status.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {col};"
            )
            # Progress bar: map 1–6 grade to 0–100% for visual
            bar_val = int((ch - 1.0) / 5.0 * 100)
            self._detail_bar.setValue(bar_val)
            bar_style = (
                f"QProgressBar::chunk {{ background: {col}; border-radius: 3px; }} "
                f"QProgressBar {{ background: {_tc('#EEE','#333')}; border-radius: 3px; border: none; }}"
            )
            self._detail_bar.setStyleSheet(bar_style)
        else:
            self._detail_grade.setText("—")
            self._detail_grade.setStyleSheet("font-size: 32px; font-weight: bold;")
            self._detail_status.setText("Noch keine Noten")
            self._detail_status.setStyleSheet(f"font-size: 14px; color: {_tc('#888','#aaa')};")
            self._detail_bar.setValue(0)

        # Target grade comparison
        tg = mod["target_grade"] if "target_grade" in mod.keys() else None
        if tg is not None and avg_pct is not None:
            diff = pct_to_ch_grade(avg_pct) - float(tg)
            icon = "✅" if diff >= 0 else "❌"
            self._detail_target.setText(f"{icon} Zielnote: {float(tg):.1f}  ({diff:+.2f})")
            self._detail_target.setStyleSheet(
                f"font-size: 12px; color: "
                f"{'#2E7D32' if diff >= 0 else '#C62828'}; font-weight: bold;"
            )
        elif tg is not None:
            self._detail_target.setText(f"🎯 Zielnote: {float(tg):.1f}")
            self._detail_target.setStyleSheet(f"font-size: 12px; color: {_tc('#555','#aaa')};")
        else:
            self._detail_target.setText("")

        # Prediction: what CH grade is needed on next assessment to reach target?
        if tg is not None and avg_pct is not None:
            grades = self.repo.list_grades(module_id=module_id)
            total_w = sum(float(g["weight"]) for g in grades)
            tg_pct = (float(tg) - 1.0) / 5.0 * 100.0   # target as %
            # needed score for 1 more unit-weight assessment:
            needed_pct = tg_pct * (total_w + 1.0) - avg_pct * total_w
            if needed_pct > 100:
                self._detail_predict.setText(
                    f"⚠ Zielnote {float(tg):.1f} ist mit einer weiteren Leistung nicht mehr erreichbar."
                )
            elif needed_pct >= 0:
                needed_ch = pct_to_ch_grade(needed_pct)
                self._detail_predict.setText(
                    f"ℹ Für Zielnote {float(tg):.1f}: nächste Leistung mind. "
                    f"{needed_ch:.1f} (≈ {needed_pct:.0f} %)"
                )
            else:
                self._detail_predict.setText(
                    f"✅ Zielnote {float(tg):.1f} bereits sicher erreicht."
                )
        else:
            self._detail_predict.setText("")

        # Fill assessment table
        self._load_grades_table(module_id)

    def _load_grades_table(self, module_id: int):
        grades = self.repo.list_grades(module_id=module_id)
        self.table.setRowCount(len(grades))
        total_w = sum(float(g["weight"]) for g in grades)

        for r, g in enumerate(grades):
            mode = g["grade_mode"] if "grade_mode" in g.keys() else "points"

            # Column 0: Title
            self.table.setItem(r, 0, QTableWidgetItem(g["title"]))

            # Column 1: Raw input display
            if mode == "direct":
                raw_txt = f"Note {float(g['grade']):.1f}"
            else:
                pct = float(g["grade"]) / float(g["max_grade"]) * 100
                raw_txt = f"{g['grade']:.1f} / {g['max_grade']:.0f}  ({pct:.0f} %)"
            self.table.setItem(r, 1, QTableWidgetItem(raw_txt))

            # Column 2: Swiss grade 1–6
            if mode == "direct":
                ch = float(g["grade"])
            else:
                ch = pct_to_ch_grade(float(g["grade"]) / float(g["max_grade"]) * 100)

            note_item = QTableWidgetItem(f"{_grade_icon(ch)}  {ch:.2f}")
            note_item.setForeground(QColor(_grade_color(ch)))
            self.table.setItem(r, 2, note_item)

            # Column 3: Weight (as % of total)
            w_pct = float(g["weight"]) / total_w * 100 if total_w > 0 else 0
            self.table.setItem(r, 3, QTableWidgetItem(f"{w_pct:.0f} %"))

            # Column 4: Date
            self.table.setItem(r, 4, QTableWidgetItem(g["date"] or "—"))

            # Column 5: hidden ID
            self.table.setItem(r, 5, QTableWidgetItem(str(g["id"])))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add_grade(self):
        # Free-plan limit: max 3 Noten gesamt
        from semetra.infra.license import LicenseManager
        lm = LicenseManager(self.repo)
        if not lm.is_pro():
            total_grades = len(self.repo.list_grades())
            if total_grades >= 3:
                dlg = ProFeatureDialog("Mehr als 3 Noten", self.repo, parent=self)
                if dlg.exec() != QDialog.Accepted:
                    return
                lm._cached = None
                if not lm.is_pro():
                    return
        dlg = GradeDialog(self.repo, default_module_id=self._sel_module_id, parent=self)
        if dlg.exec():
            self._update_kpis()
            self._rebuild_cards()
            if self._sel_module_id:
                self._load_detail(self._sel_module_id)

    def _edit_grade(self):
        row = self.table.currentRow()
        if row < 0:
            return
        gid = int(self.table.item(row, 5).text())
        if GradeDialog(self.repo, grade_id=gid, parent=self).exec():
            self._update_kpis()
            self._rebuild_cards()
            if self._sel_module_id:
                self._load_detail(self._sel_module_id)

    def _delete_grade(self):
        row = self.table.currentRow()
        if row < 0:
            return
        gid = int(self.table.item(row, 5).text())
        if QMessageBox.question(
            self, "Löschen", "Eintrag löschen?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.repo.delete_grade(gid)
            self._update_kpis()
            self._rebuild_cards()
            if self._sel_module_id:
                self._load_detail(self._sel_module_id)


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

        # ── Lizenz ───────────────────────────────────────────────────────────
        lic_grp = QGroupBox("Lizenz")
        lic_lay = QFormLayout(lic_grp)
        lic_lay.setSpacing(10)

        from semetra.infra.license import LicenseManager
        lm = LicenseManager(self.repo)
        self._is_pro = lm.is_pro()
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

        lic_note = QLabel('<a href="https://semetra.ch/#preise" style="color:#7C3AED;">Lizenz auf semetra.ch kaufen →</a>')
        lic_note.setStyleSheet("font-size:11px;")
        lic_note.setOpenExternalLinks(False)
        lic_note.linkActivated.connect(lambda url: _open_url(url))
        lic_lay.addRow("", lic_note)
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


# ── Quick-Add Dialog (Ctrl+N) ─────────────────────────────────────────────

class QuickAddDialog(QDialog):
    """Schnelleintrag ohne Seitenwechsel: Task oder Wissensthema in 3 Klicks."""

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.setWindowTitle("⚡ Schnelleintrag")
        self.setMinimumWidth(380)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        # Header
        hdr = QLabel("⚡ Schnelleintrag")
        hdr.setStyleSheet("font-size:15px;font-weight:bold;")
        lay.addWidget(hdr)

        form = QFormLayout()
        form.setSpacing(8)

        # Module
        self._mod_cb = QComboBox()
        self._mod_cb.addItem("— Modul wählen —", None)
        for m in self.repo.list_modules("all"):
            self._mod_cb.addItem(m["name"], m["id"])
        form.addRow("Modul:", self._mod_cb)

        # Type
        self._type_cb = QComboBox()
        self._type_cb.addItems(["✅  Aufgabe (Task)", "🧠  Wissensthema"])
        form.addRow("Typ:", self._type_cb)

        # Title
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Titel eingeben…")
        form.addRow("Titel *:", self._title_edit)

        # Extra: priority (for task) or knowledge level (for topic)
        self._extra_cb = QComboBox()
        self._extra_cb.addItems(["Low", "Medium", "High", "Critical"])
        self._extra_cb.setCurrentText("Medium")
        self._extra_lbl = QLabel("Priorität:")
        form.addRow(self._extra_lbl, self._extra_cb)

        self._type_cb.currentIndexChanged.connect(self._on_type_change)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Hinzufügen")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        # Focus on title
        self._title_edit.setFocus()

    def _on_type_change(self, idx):
        if idx == 0:  # Task
            self._extra_lbl.setText("Priorität:")
            self._extra_cb.clear()
            self._extra_cb.addItems(["Low", "Medium", "High", "Critical"])
            self._extra_cb.setCurrentText("Medium")
        else:  # Topic
            self._extra_lbl.setText("Kenntnisstand:")
            self._extra_cb.clear()
            for k, v in KNOWLEDGE_LABELS.items():
                self._extra_cb.addItem(v, k)

    def _save(self):
        mid = self._mod_cb.currentData()
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Fehler", "Titel ist ein Pflichtfeld.")
            return
        if not mid:
            QMessageBox.warning(self, "Fehler", "Bitte ein Modul auswählen.")
            return
        if self._type_cb.currentIndex() == 0:
            prio = self._extra_cb.currentText()
            self.repo.add_task(mid, title, priority=prio, status="Open")
        else:
            level = self._extra_cb.currentData() or 0
            now_str = datetime.now().isoformat()
            self.repo.add_topic(mid, title, knowledge_level=level, notes="")
            topics = self.repo.list_topics(mid)
            new_t = next((t for t in topics if t["title"] == title), None)
            if new_t:
                self.repo.update_topic(new_t["id"], last_reviewed=now_str)
        self.accept()


# ── Credits Page ──────────────────────────────────────────────────────────

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


# ── KI Lernplan Generator ─────────────────────────────────────────────────

class StudyPlanGeneratorDialog(QDialog):
    """
    Generiert einen personalisierten Lernplan für die nächsten 2 Wochen.
    Basiert auf: Prüfungsdaten, ECTS-Gewichtung, aktuellem Lernfortschritt.
    Kein KI-API nötig — smarte, regelbasierte Verteilung.
    """

    def __init__(self, repo: SqliteRepo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("📅  Lernplan Generator")
        self.resize(820, 600)
        self._build()
        self._generate()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel("📅  Dein persönlicher Lernplan")
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        lay.addLayout(hdr)

        sub = QLabel("Basiert auf deinen Prüfungsterminen, ECTS-Gewichtung und aktuellem Lernstand.")
        sub.setStyleSheet("color:#6B7280;font-size:12px;")
        lay.addWidget(sub)

        # Settings row
        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("Lernen pro Tag:"))
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(1, 12)
        self.hours_spin.setValue(3)
        self.hours_spin.setSuffix(" h")
        settings_row.addWidget(self.hours_spin)
        settings_row.addSpacing(20)
        settings_row.addWidget(QLabel("Tage voraus:"))
        self.days_spin = QSpinBox()
        self.days_spin.setRange(7, 28)
        self.days_spin.setValue(14)
        self.days_spin.setSuffix(" Tage")
        settings_row.addWidget(self.days_spin)
        settings_row.addStretch()
        regen_btn = QPushButton("🔄  Neu generieren")
        regen_btn.setObjectName("PrimaryBtn")
        regen_btn.clicked.connect(self._generate)
        settings_row.addWidget(regen_btn)
        lay.addLayout(settings_row)

        # Plan output
        self.plan_area = QScrollArea()
        self.plan_area.setWidgetResizable(True)
        self.plan_area.setFrameShape(QFrame.NoFrame)
        self.plan_container = QWidget()
        self.plan_layout = QVBoxLayout(self.plan_container)
        self.plan_layout.setSpacing(6)
        self.plan_layout.setContentsMargins(0, 0, 0, 0)
        self.plan_area.setWidget(self.plan_container)
        lay.addWidget(self.plan_area, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _generate(self):
        # Clear existing plan
        while self.plan_layout.count():
            item = self.plan_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        hours_per_day = self.hours_spin.value()
        days_ahead = self.days_spin.value()
        today = date.today()

        # ── Gather modules with upcoming exams ───────────────────────────────
        modules_data: list[dict] = []
        all_active = self.repo.list_modules("active")
        if not all_active:
            all_active = self.repo.list_modules("all")

        for m in all_active:
            exam_d = days_until(m["exam_date"]) if m["exam_date"] else None
            if exam_d is not None and exam_d < 0:
                continue  # exam passed
            ects = float(m["ects"]) if m["ects"] else 3.0
            target_h = self.repo.ects_target_hours(m["id"])
            studied_h = self.repo.seconds_studied_for_module(m["id"]) / 3600
            remaining_h = max(0.0, target_h - studied_h)
            # urgency: higher if exam is closer; scale 0.1–1.0
            if exam_d is not None and exam_d <= days_ahead:
                urgency = max(0.1, 1.0 - exam_d / (days_ahead + 1))
            elif exam_d is not None:
                urgency = 0.1
            else:
                urgency = 0.05  # no exam → low urgency but still include

            # Spaced rep topics due for review
            sr_due = 0
            for t in self.repo.list_topics(m["id"]):
                lr = t["last_reviewed"] if "last_reviewed" in t.keys() else ""
                lvl = int(t["knowledge_level"]) if t["knowledge_level"] else 0
                if lr and lvl < 3:
                    try:
                        ds = (today - datetime.fromisoformat(lr).date()).days
                        if ds >= 3:
                            sr_due += 1
                    except Exception:
                        pass

            modules_data.append({
                "id": m["id"],
                "name": m["name"],
                "ects": ects,
                "exam_date": m["exam_date"],
                "exam_days": exam_d,
                "remaining_h": remaining_h,
                "urgency": urgency,
                "sr_due": sr_due,
                "color": mod_color(m["id"]),
            })

        if not modules_data:
            lbl = QLabel("Keine aktiven Module gefunden. Füge zuerst Module hinzu.")
            lbl.setStyleSheet("color:#6B7280;font-size:13px;padding:20px;")
            self.plan_layout.addWidget(lbl)
            return

        # ── Distribute study time per day ─────────────────────────────────────
        # Normalize urgency weights
        total_urgency = sum(m["urgency"] for m in modules_data) or 1.0
        for m in modules_data:
            m["daily_share_h"] = (m["urgency"] / total_urgency) * hours_per_day
            m["daily_share_h"] = round(min(m["daily_share_h"], m["remaining_h"] / max(1, m["exam_days"] or days_ahead), 2.5), 1)
            m["daily_share_h"] = max(m["daily_share_h"], 0.25 if m["remaining_h"] > 0 else 0)

        # ── Render day cards ────────────────────────────────────────────────
        for day_offset in range(days_ahead):
            day_date = today + timedelta(days=day_offset)
            weekday_name = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][day_date.weekday()]
            is_weekend = day_date.weekday() >= 5

            # Day header
            day_frame = QFrame()
            day_frame.setObjectName("Card")
            day_lay = QVBoxLayout(day_frame)
            day_lay.setContentsMargins(14, 10, 14, 10)
            day_lay.setSpacing(4)

            day_hdr = QHBoxLayout()
            date_lbl = QLabel(f"<b>{weekday_name}, {day_date.strftime('%d.%m.')}</b>")
            date_lbl.setTextFormat(Qt.RichText)
            if is_weekend:
                date_lbl.setStyleSheet("color:#10B981;font-size:13px;")
            else:
                date_lbl.setStyleSheet("font-size:13px;")
            day_hdr.addWidget(date_lbl)

            # Check for exams on this day
            exam_today_mods = [m for m in modules_data if m["exam_date"] == day_date.isoformat()]
            if exam_today_mods:
                for em in exam_today_mods:
                    exam_badge = QLabel(f"  🎯 PRÜFUNG: {em['name']}")
                    exam_badge.setStyleSheet("color:#DC2626;font-weight:bold;font-size:13px;")
                    day_hdr.addWidget(exam_badge)

            day_hdr.addStretch()
            total_h_today = sum(m["daily_share_h"] for m in modules_data
                                if m["daily_share_h"] > 0 and not is_weekend)
            if not is_weekend:
                total_lbl = QLabel(f"{total_h_today:.1f}h")
                total_lbl.setStyleSheet("color:#7C3AED;font-weight:bold;font-size:12px;")
                day_hdr.addWidget(total_lbl)
            day_lay.addLayout(day_hdr)

            if is_weekend:
                rest_lbl = QLabel("  🌿  Erholungstag — gönn dir eine Pause!")
                rest_lbl.setStyleSheet("color:#6B7280;font-size:12px;")
                day_lay.addWidget(rest_lbl)
            else:
                # Show tasks per module for this day
                active_modules = [m for m in modules_data if m["daily_share_h"] > 0]
                # Sort by urgency for display
                active_modules = sorted(active_modules, key=lambda x: -x["urgency"])
                for m in active_modules[:3]:  # show top 3 modules
                    task_row = QHBoxLayout()
                    dot = QLabel("●")
                    dot.setStyleSheet(f"color:{m['color']};font-size:10px;")
                    task_row.addWidget(dot)
                    hours_txt = f"{m['daily_share_h']:.1f}h"
                    mod_lbl = QLabel(f"<b>{m['name']}</b>  —  {hours_txt}")
                    mod_lbl.setTextFormat(Qt.RichText)
                    mod_lbl.setStyleSheet("font-size:12px;")
                    task_row.addWidget(mod_lbl, 1)
                    hints = []
                    if m["exam_days"] is not None and m["exam_days"] <= 7:
                        hints.append(f"⚠ Prüfung in {m['exam_days']}d")
                    if m["sr_due"] > 0:
                        hints.append(f"🧠 {m['sr_due']} Wiederholung(en)")
                    if hints:
                        hint_lbl = QLabel("  ".join(hints))
                        hint_lbl.setStyleSheet("color:#D97706;font-size:11px;")
                        task_row.addWidget(hint_lbl)
                    day_lay.addLayout(task_row)

            self.plan_layout.addWidget(day_frame)

        self.plan_layout.addStretch()


# ── Studien-Coach: Smarte Lernberatung mit Navigation & Web-Ressourcen ────

import webbrowser as _webbrowser
import urllib.parse as _urllib_parse
import random as _random

class _CoachEngine:
    """
    Smarte Coach-Engine: Analysiert Studentendaten + Freitext-Input,
    navigiert direkt zu App-Tabs, öffnet YouTube-Videos und Web-Ressourcen.
    Aktions-Format in Quick-Replies: "ACTION|data|Label"
      NAV|<idx>|Label   → navigiert zur Seite idx und schließt Chat
      YT|<query>|Label  → öffnet YouTube-Suche im Browser
      WEB|<url>|Label   → öffnet URL im Browser
      (kein Präfix)     → wird als Textnachricht verarbeitet
    """

    # Seitenindizes (entsprechen SidebarWidget.NAV_ITEMS)
    PAGE_DASHBOARD    = 0
    PAGE_MODULE       = 1
    PAGE_AUFGABEN     = 2
    PAGE_KALENDER     = 3
    PAGE_STUNDENPLAN  = 4   # NEW
    PAGE_STUDIENPLAN  = 5
    PAGE_WISSEN       = 6
    PAGE_TIMER        = 7
    PAGE_PRÜFUNGEN    = 8
    PAGE_NOTEN        = 9
    PAGE_EINSTELLUNGEN = 10

    INTENTS = {
        "panic":      ["prüfung morgen", "prüfung übermorgen", "exam morgen", "keine zeit",
                       "zu spät", "panic", "panik", "deadline", "abgabe morgen",
                       "klausur morgen", "klausur übermorgen", "alles vergessen"],
        "start":      ["weiß nicht wo", "wo anfangen", "nicht wissen", "keine ahnung",
                       "überfordert", "zu viel", "chaos", "verloren", "nicht klar",
                       "wo fange ich an", "was soll ich tun", "was zuerst"],
        "motivation": ["keine lust", "nicht motiviert", "unmotiviert", "faul", "müde",
                       "aufgegeben", "hoffnungslos", "sinn", "warum", "bored", "langweilig"],
        "progress":   ["wie stehe ich", "fortschritt", "wie weit", "schafft das",
                       "schaffe ich das", "reicht das", "genug gelernt", "auf kurs"],
        "time":       ["keine zeit", "zu beschäftigt", "wenig zeit", "nur kurz",
                       "heute keine", "5 minuten", "schnell", "kurz"],
        "grade":      ["note", "durchschnitt", "ziel", "bestehen", "punktzahl",
                       "wie viel brauche", "wie gut muss", "nicht bestanden"],
        "greeting":   ["hallo", "hi", "hey", "guten morgen", "guten tag", "servus",
                       "was kann", "wie funktioniert", "hilf mir", "was bist du"],
        "youtube":    ["youtube", "video", "videos", "tutorial", "erklär", "erklärung",
                       "vorlesung", "lernvideo", "schauen", "anschauen", "vl zu"],
        "resource":   ["website", "webseite", "artikel", "blog", "buch", "materialien",
                       "ressourcen", "quellen", "links", "wo lerne ich", "wo finde ich",
                       "lernmaterial", "unterlagen", "skript"],
        "explain":    ["wie funktioniert", "wie funktionieren", "was ist", "was sind",
                       "erkläre mir", "erkläre", "erklär mir", "wie geht", "wie macht man",
                       "was bedeutet", "definition von", "einführung", "grundlagen von",
                       "zeig mir wie", "ich verstehe nicht", "ich check nicht"],
        "exam_entry": ["prüfung am", "klausur am", "exam am", "prüfungstermin",
                       "prüfung eintragen", "klausur eintragen", "trage.*prüfung",
                       "trage.*ein", "füge.*prüfung", "merk dir", "merke dir",
                       "habe eine prüfung", "hab eine prüfung"],
        "navigate":   ["öffne", "gehe zu", "zeig mir die", "navigiere", "wechsel",
                       "zum timer", "zu den aufgaben", "zur noten", "zum kalender",
                       "zum studienplan", "zum wissen", "zum dashboard"],
        "exam_plan":  ["lernplan", "plan erstellen", "studienplan", "wie lerne ich",
                       "lernstrategie", "vorbereitung", "crashplan", "wie bereite ich"],
        "timer_req":  ["timer starten", "pomodoro starten", "session starten",
                       "lerneinheit starten", "starte timer", "starte pomodoro"],
    }

    # Fach-Erkennungsmuster → (Anzeigename, Suchbegriffe)
    SUBJECTS = [
        ("Mathematik",         ["mathematik", "mathe", "math", "maths"]),
        ("Analysis",           ["analysis", "differential", "integral", "ableitung"]),
        ("Lineare Algebra",    ["lineare algebra", "vektoren", "matrizen", "matrix"]),
        ("Statistik",          ["statistik", "wahrscheinlichkeit", "stochastik", "statistisch"]),
        ("Algorithmen",        ["algorithmen", "algorithmus", "datenstrukturen", "komplexität", "big o"]),
        ("Programmierung",     ["python", "java", "c++", "c#", "programmier", "coding", "code schreiben"]),
        ("Datenbanken",        ["sql", "datenbank", "database", "nosql", "mongodb", "relational"]),
        ("Netzwerke",          ["netzwerk", "tcp", "ip", "routing", "osi", "protokoll", "netzwerktechnik"]),
        ("Betriebssysteme",    ["betriebssystem", "operating system", "prozesse", "threads", "kernel"]),
        ("Webentwicklung",     ["html", "css", "javascript", "webentwicklung", "react", "frontend"]),
        ("Software Engineering",["software engineering", "design pattern", "architektur", "agile", "scrum"]),
        ("Machine Learning",   ["machine learning", "ki", "neural", "deep learning", "ml", "künstliche intelligenz"]),
        ("Physik",             ["physik", "mechanik", "thermodynamik", "elektrodynamik"]),
        ("Informatik",         ["informatik", "computer science"]),
    ]

    # Kuratierte Ressourcen pro Fach (inkl. Wikipedia-Links)
    RESOURCES: dict = {
        "Mathematik": [
            ("📐 Khan Academy Mathe", "https://de.khanacademy.org/math"),
            ("📐 Mathebibel", "https://www.mathebibel.de"),
            ("📖 Wikipedia: Mathematik", "https://de.wikipedia.org/wiki/Mathematik"),
            ("📐 Mathe online", "https://www.matheonline.at"),
        ],
        "Analysis": [
            ("📐 Khan Academy Calculus", "https://www.khanacademy.org/math/calculus-1"),
            ("📖 Wikipedia: Analysis", "https://de.wikipedia.org/wiki/Analysis"),
            ("📖 Wikipedia: Differentialrechnung", "https://de.wikipedia.org/wiki/Differentialrechnung"),
            ("📖 Wikipedia: Integralrechnung", "https://de.wikipedia.org/wiki/Integralrechnung"),
        ],
        "Lineare Algebra": [
            ("🔢 3Blue1Brown – Essence of LA", "https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab"),
            ("🔢 Khan Academy Linear Algebra", "https://www.khanacademy.org/math/linear-algebra"),
            ("📖 Wikipedia: Lineare Algebra", "https://de.wikipedia.org/wiki/Lineare_Algebra"),
        ],
        "Statistik": [
            ("📊 Khan Academy Statistics", "https://www.khanacademy.org/math/statistics-probability"),
            ("📊 StatistikGuru", "https://statistikguru.de"),
            ("📖 Wikipedia: Statistik", "https://de.wikipedia.org/wiki/Statistik"),
            ("📊 Crashkurs Statistik (YT)", "https://www.youtube.com/results?search_query=statistik+crashkurs+deutsch"),
        ],
        "Algorithmen": [
            ("🔍 Visualgo – Algorithmen visualisiert", "https://visualgo.net/de"),
            ("🔍 Big-O Cheat Sheet", "https://www.bigocheatsheet.com"),
            ("📖 Wikipedia: Algorithmus", "https://de.wikipedia.org/wiki/Algorithmus"),
            ("🔍 CS50 Harvard (kostenlos)", "https://cs50.harvard.edu/x"),
        ],
        "Programmierung": [
            ("💻 Python Dokumentation", "https://docs.python.org/3/"),
            ("💻 W3Schools", "https://www.w3schools.com"),
            ("📖 Wikipedia: Programmierung", "https://de.wikipedia.org/wiki/Programmierung"),
            ("💻 freeCodeCamp", "https://www.freecodecamp.org"),
        ],
        "Datenbanken": [
            ("🗄 SQLZoo – interaktiv SQL üben", "https://sqlzoo.net"),
            ("🗄 SQL Tutorial", "https://www.sqltutorial.org"),
            ("📖 Wikipedia: Relationale Datenbank", "https://de.wikipedia.org/wiki/Relationale_Datenbank"),
            ("📖 Wikipedia: SQL", "https://de.wikipedia.org/wiki/SQL"),
        ],
        "Netzwerke": [
            ("🌐 Cisco Networking Academy", "https://www.netacad.com"),
            ("📖 Wikipedia: Computernetz", "https://de.wikipedia.org/wiki/Computernetz"),
            ("📖 Wikipedia: OSI-Modell", "https://de.wikipedia.org/wiki/OSI-Modell"),
            ("🌐 Computerphile – Netzwerke (YT)", "https://www.youtube.com/results?search_query=netzwerke+grundlagen+deutsch"),
        ],
        "Betriebssysteme": [
            ("📖 Wikipedia: Betriebssystem", "https://de.wikipedia.org/wiki/Betriebssystem"),
            ("📖 Wikipedia: Prozess (Informatik)", "https://de.wikipedia.org/wiki/Prozess_(Informatik)"),
            ("💡 OSDev Wiki", "https://wiki.osdev.org/Main_Page"),
        ],
        "Webentwicklung": [
            ("🌐 MDN Web Docs", "https://developer.mozilla.org/de/"),
            ("🌐 W3Schools", "https://www.w3schools.com"),
            ("📖 Wikipedia: Webentwicklung", "https://de.wikipedia.org/wiki/Webentwicklung"),
            ("🌐 The Odin Project", "https://www.theodinproject.com"),
        ],
        "Machine Learning": [
            ("🤖 fast.ai (kostenlos)", "https://www.fast.ai"),
            ("🤖 Google ML Crash Course", "https://developers.google.com/machine-learning/crash-course"),
            ("📖 Wikipedia: Maschinelles Lernen", "https://de.wikipedia.org/wiki/Maschinelles_Lernen"),
            ("🤖 3Blue1Brown – Neural Networks", "https://www.youtube.com/playlist?list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi"),
        ],
        "Software Engineering": [
            ("⚙ Refactoring Guru – Design Patterns", "https://refactoring.guru/design-patterns"),
            ("📖 Wikipedia: Software Engineering", "https://de.wikipedia.org/wiki/Software_Engineering"),
            ("📖 Wikipedia: Entwurfsmuster", "https://de.wikipedia.org/wiki/Entwurfsmuster"),
            ("⚙ Clean Code – Zusammenfassung", "https://www.youtube.com/results?search_query=clean+code+deutsch"),
        ],
        "Informatik": [
            ("📖 Wikipedia: Informatik", "https://de.wikipedia.org/wiki/Informatik"),
            ("🔍 CS50 Harvard (kostenlos)", "https://cs50.harvard.edu/x"),
            ("💻 freeCodeCamp", "https://www.freecodecamp.org"),
        ],
        "Physik": [
            ("📖 Wikipedia: Physik", "https://de.wikipedia.org/wiki/Physik"),
            ("📐 Khan Academy Physik", "https://www.khanacademy.org/science/physics"),
            ("📖 Wikipedia: Mechanik", "https://de.wikipedia.org/wiki/Mechanik"),
        ],
    }

    # Modul-Code → (YouTube-Suchbegriffe, Web-Ressourcen)
    # Maßgeschneidert für FFHS Informatik BSc
    MODULE_RESOURCES: dict = {
        "AnPy": (
            ["Analysis mit Python scipy numpy", "Python numerische Methoden Tutorial Deutsch",
             "Analysis Grundlagen FH Deutsch"],
            [("🐍 scipy Docs", "https://docs.scipy.org/doc/scipy/"),
             ("🐍 numpy Tutorial", "https://numpy.org/doc/stable/user/quickstart.html")],
        ),
        "BDN": (
            ["Big Data Hadoop Spark Grundlagen Deutsch", "NoSQL MongoDB Tutorial Deutsch",
             "Big Data Architektur erklärt"],
            [("🗄 MongoDB Docs", "https://www.mongodb.com/docs/manual/"),
             ("📊 Apache Spark", "https://spark.apache.org/docs/latest/")],
        ),
        "C++": (
            ["C++ Tutorial Deutsch FH Grundlagen", "C++ Objektorientierung erklärt",
             "C++ Zeiger Pointer erklärt Deutsch"],
            [("💻 cppreference", "https://de.cppreference.com/w/"),
             ("💻 learncpp.com", "https://www.learncpp.com")],
        ),
        "ClCo": (
            ["Cloud Computing Grundlagen Deutsch AWS Azure", "IaaS PaaS SaaS erklärt",
             "Cloud Architecture Tutorial"],
            [("☁ AWS Grundlagen", "https://aws.amazon.com/de/getting-started/"),
             ("☁ Azure Fundamentals", "https://learn.microsoft.com/de-de/azure/")],
        ),
        "DBS": (
            ["SQL Tutorial Deutsch Grundlagen FH", "Datenbanksysteme ER-Modell erklärt",
             "SQL Joins GROUP BY erklärt Deutsch"],
            [("🗄 SQLZoo Übungen", "https://sqlzoo.net"),
             ("🗄 SQL Tutorial", "https://www.sqltutorial.org"),
             ("🗄 DB-Fiddle", "https://www.db-fiddle.com")],
        ),
        "D&A": (
            ["Datenstrukturen Algorithmen FH Deutsch", "Big-O Notation erklärt Deutsch",
             "Sortieralgorithmen Visualisierung"],
            [("🔍 Visualgo", "https://visualgo.net/de"),
             ("🔍 Big-O Cheatsheet", "https://www.bigocheatsheet.com"),
             ("🔍 CS50 Harvard", "https://cs50.harvard.edu/x")],
        ),
        "DevOps": (
            ["DevOps Grundlagen Deutsch CI/CD", "Docker Tutorial Deutsch Grundlagen",
             "Git Workflow DevOps erklärt"],
            [("⚙ Docker Docs", "https://docs.docker.com/get-started/"),
             ("⚙ GitHub Actions", "https://docs.github.com/de/actions")],
        ),
        "DMathLS": (
            ["Diskrete Mathematik FH Deutsch Grundlagen", "Graphentheorie erklärt Deutsch",
             "Lineare Systeme Signalverarbeitung FH"],
            [("📐 Diskrete Mathe – Khanacademy", "https://www.khanacademy.org/computing/computer-science/cryptography"),
             ("📐 Mathebibel", "https://www.mathebibel.de/diskrete-mathematik")],
        ),
        "GTI": (
            ["Grundlagen Technische Informatik FH Deutsch", "Logikgatter Schaltkreise erklärt",
             "Von-Neumann-Architektur erklärt Deutsch"],
            [("💡 nand2tetris", "https://www.nand2tetris.org"),
             ("💡 Rechnerarchitektur Wikipedia", "https://de.wikipedia.org/wiki/Rechnerarchitektur")],
        ),
        "ISich": (
            ["Informationssicherheit Grundlagen FH Deutsch", "IT-Sicherheit CIA-Prinzip erklärt",
             "Kryptographie Grundlagen Deutsch"],
            [("🔒 BSI Grundschutz", "https://www.bsi.bund.de/DE/Themen/Unternehmen-und-Organisationen/Standards-und-Zertifizierung/IT-Grundschutz/IT-Grundschutz-Kompendium/it-grundschutz-kompendium_node.html"),
             ("🔒 OWASP Top 10", "https://owasp.org/www-project-top-ten/")],
        ),
        "INSich": (
            ["Internetsicherheit TLS HTTPS erklärt Deutsch", "Netzwerksicherheit Firewall VPN",
             "Ethical Hacking Grundlagen"],
            [("🔒 OWASP", "https://owasp.org"),
             ("🔒 TryHackMe", "https://tryhackme.com")],
        ),
        "JAF": (
            ["Java Tutorial Deutsch Grundlagen FH", "Java OOP erklärt Deutsch",
             "Java Collections Streams Tutorial"],
            [("☕ Java Docs Oracle", "https://docs.oracle.com/javase/tutorial/"),
             ("☕ Baeldung Java", "https://www.baeldung.com")],
        ),
        "JEA": (
            ["Java Enterprise Spring Framework Tutorial", "JEE Jakarta EE Deutsch",
             "Spring Boot Tutorial Deutsch"],
            [("☕ Spring.io Guides", "https://spring.io/guides"),
             ("☕ Baeldung Spring", "https://www.baeldung.com/spring-tutorial")],
        ),
        "JPL": (
            ["Java Projektarbeit Best Practices", "Clean Code Java Tutorial",
             "Java Design Patterns erklärt Deutsch"],
            [("☕ Refactoring Guru", "https://refactoring.guru/de/design-patterns/java"),
             ("☕ Baeldung", "https://www.baeldung.com")],
        ),
        "LinAlg": (
            ["Lineare Algebra FH Deutsch Grundlagen", "Matrizen Vektoren erklärt Deutsch",
             "Lineare Algebra 3Blue1Brown Deutsch"],
            [("🔢 3Blue1Brown LA", "https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab"),
             ("🔢 Khan Academy", "https://www.khanacademy.org/math/linear-algebra")],
        ),
        "MaLe": (
            ["Machine Learning Grundlagen Deutsch FH", "Supervised Learning erklärt Deutsch",
             "Neural Networks Grundlagen Deutsch"],
            [("🤖 fast.ai", "https://www.fast.ai"),
             ("🤖 Google ML Crash Course", "https://developers.google.com/machine-learning/crash-course"),
             ("🤖 Kaggle Learn", "https://www.kaggle.com/learn")],
        ),
        "MCI": (
            ["Mensch-Computer-Interaktion HCI Grundlagen", "Usability UX Design Grundlagen Deutsch",
             "User Interface Design Prinzipien"],
            [("🖥 Nielsen Norman Group", "https://www.nngroup.com/articles/"),
             ("🖥 Material Design", "https://m3.material.io")],
        ),
        "OEM": (
            ["Mathematik Grundlagen FH Vorkurs Deutsch", "Analysis Grundlagen Studium Einstieg",
             "Mathe Vorkurs Studium"],
            [("📐 Khan Academy Mathe", "https://de.khanacademy.org/math"),
             ("📐 Mathebibel", "https://www.mathebibel.de")],
        ),
        "PMG": (
            ["Projektmanagement Grundlagen Deutsch FH", "PRINCE2 Agile Scrum Grundlagen",
             "Projektplanung Gantt-Diagramm"],
            [("📋 PMBOK Guide", "https://www.pmi.org/pmbok-guide-standards"),
             ("📋 Scrum.org", "https://www.scrum.org/resources/what-is-scrum")],
        ),
        "RN": (
            ["Rechnernetze Grundlagen FH Deutsch", "OSI-Modell alle Schichten erklärt Deutsch",
             "TCP/IP Routing Grundlagen Deutsch"],
            [("🌐 Computernetze Wikipedia", "https://de.wikipedia.org/wiki/Computernetz"),
             ("🌐 Cisco Networking Basics", "https://www.netacad.com/catalog/networking")],
        ),
        "SWEM": (
            ["Software Engineering Modellierung UML FH", "UML Klassendiagramm erklärt Deutsch",
             "Anforderungsanalyse Use Case Diagram"],
            [("⚙ UML Tutorial", "https://www.uml.org"),
             ("⚙ Draw.io UML", "https://app.diagrams.net")],
        ),
        "SWEA": (
            ["Software Architektur Design Patterns FH Deutsch", "Microservices vs Monolith erklärt",
             "Clean Architecture Robert Martin"],
            [("⚙ Refactoring Guru", "https://refactoring.guru/de/design-patterns"),
             ("⚙ Martin Fowler", "https://martinfowler.com/architecture/")],
        ),
        "SWQ": (
            ["Software Qualität Testing FH Deutsch", "Unit Tests JUnit Deutsch Tutorial",
             "Code Review Best Practices"],
            [("🔬 JUnit 5 Docs", "https://junit.org/junit5/docs/current/user-guide/"),
             ("🔬 Clean Code Zusammenfassung", "https://www.google.com/search?q=clean+code+zusammenfassung+deutsch")],
        ),
        "VSA": (
            ["Verteilte Systeme Grundlagen FH Deutsch", "REST API Microservices Tutorial Deutsch",
             "Kafka RabbitMQ Message Queue erklärt"],
            [("🌐 Distributed Systems Primer", "https://github.com/donnemartin/system-design-primer"),
             ("🌐 REST API Tutorial", "https://restfulapi.net")],
        ),
        "WS": (
            ["Wahrscheinlichkeitsrechnung Statistik FH Deutsch", "Normalverteilung erklärt Deutsch",
             "Statistik Hypothesentest Grundlagen"],
            [("📊 Khan Academy Statistik", "https://www.khanacademy.org/math/statistics-probability"),
             ("📊 StatistikGuru", "https://statistikguru.de")],
        ),
        "WebE": (
            ["Web Engineering Full-Stack Tutorial Deutsch", "REST API JavaScript Node.js Tutorial",
             "Web Architektur HTTP erklärt Deutsch"],
            [("🌐 MDN Web Docs", "https://developer.mozilla.org/de/"),
             ("🌐 The Odin Project", "https://www.theodinproject.com")],
        ),
        "WebG": (
            ["HTML CSS Grundlagen Tutorial Deutsch FH", "JavaScript Grundlagen Tutorial Deutsch",
             "Responsive Design CSS Flexbox erklärt"],
            [("🌐 MDN Web Docs", "https://developer.mozilla.org/de/"),
             ("🌐 W3Schools", "https://www.w3schools.com"),
             ("🌐 freeCodeCamp", "https://www.freecodecamp.org")],
        ),
        "WiAr": (
            ["Wissenschaftliches Arbeiten FH Deutsch", "Literaturrecherche Zitieren Hochschule",
             "Hausarbeit schreiben Tipps"],
            [("📝 Zitation – Uni Oldenburg", "https://www.uni-oldenburg.de/studium/schreibwerkstatt/"),
             ("📝 Citavi", "https://www.citavi.com/de")],
        ),
        "EnAr": (
            ["Enterprise Architecture TOGAF Grundlagen Deutsch", "IT-Architektur Framework FH",
             "Business Architecture Tutorial"],
            [("🏢 TOGAF", "https://www.opengroup.org/togaf"),
             ("🏢 Enterprise Architecture Wikipedia", "https://de.wikipedia.org/wiki/Enterprise-Architektur")],
        ),
        "IKS": (
            ["Linux Server Konfiguration Tutorial Deutsch", "Apache Nginx Installation Linux",
             "Server Administration Deutsch FH"],
            [("🖥 Linux Documentation", "https://www.kernel.org/doc/html/latest/"),
             ("🖥 DigitalOcean Tutorials", "https://www.digitalocean.com/community/tutorials")],
        ),
        "InnT": (
            ["Innovation Management Technologie FH Deutsch", "Design Thinking Agile FH",
             "Startup Methoden Lean Canvas"],
            [("💡 IDEO Design Thinking", "https://designthinking.ideo.com"),
             ("💡 Lean Startup", "http://theleanstartup.com")],
        ),
    }

    def __init__(self, repo: SqliteRepo):
        self.repo = repo

    # ── Hilfsmethoden ────────────────────────────────────────────────────────

    def _intent(self, text: str) -> str:
        import re as _re
        t = text.lower()
        # exam_entry: check regex patterns first (date in text = strong signal)
        if _re.search(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", t) and any(
                kw in t for kw in ["prüfung", "klausur", "exam", "trage", "eintrag"]):
            return "exam_entry"
        for intent, keywords in self.INTENTS.items():
            if any(kw in t for kw in keywords):
                return intent
        return "generic"

    def _detect_subject(self, text: str) -> Optional[str]:
        """Gibt den erkannten Fachnamen zurück, oder None."""
        t = text.lower()
        for subject, keywords in self.SUBJECTS:
            if any(kw in t for kw in keywords):
                return subject
        return None

    def _match_module(self, text: str) -> Optional[dict]:
        """
        Versucht, einen konkreten DB-Modul-Eintrag aus dem Freitext zu erkennen.
        Gibt das Modul-Dict zurück oder None.
        Scoring: jedes Wort des Modulnamens, das im Text vorkommt, zählt +1.
        Modulcode-Treffer zählt +5.
        """
        t = text.lower()
        best_mod = None
        best_score = 0
        all_modules = self.repo.list_modules("all")
        for m in all_modules:
            if not (int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1):
                continue
            score = 0
            code = (m["code"] or "").lower()
            name = (m["name"] or "").lower()
            # Exakter Code-Treffer (z.B. "DBS", "WebG")
            if code and code in t:
                score += 5
            # Wörter aus dem Modulnamen
            name_words = [w for w in name.split() if len(w) > 3]
            for w in name_words:
                if w in t:
                    score += 1
            # Kurze Schlüsselwörter
            if score == 0:
                # Partielle Treffer (Substring-Match des Namens)
                name_parts = name.split(" – ")[0].split(" & ")[0].split(" und ")[0]
                if name_parts in t or any(p in t for p in name_parts.split()[:2] if len(p) > 3):
                    score += 1
            if score > best_score:
                best_score = score
                best_mod = dict(m)
        return best_mod if best_score > 0 else None

    def _module_links(self, mod: dict) -> tuple[list[str], list[str]]:
        """
        Gibt (yt_search_queries, web_resources_as_action_strings) für ein konkretes Modul zurück.
        Priorisiert MODULE_RESOURCES, fällt auf SUBJECTS/RESOURCES zurück.
        """
        code = (mod.get("code") or "").strip()
        name = mod.get("name") or "Modul"
        yt_queries: list[str] = []
        web_actions: list[str] = []

        if code in self.MODULE_RESOURCES:
            yt_q_list, web_res = self.MODULE_RESOURCES[code]
            for q in yt_q_list[:2]:
                yt_queries.append(self._yt(q, f"▶ {q[:35]}"))
            for label, url in web_res[:2]:
                web_actions.append(self._web(url, label[:40]))
        else:
            # Fallback: generische Suche basierend auf Modulname
            q = f"{name} FH Studium Tutorial Deutsch"
            yt_queries.append(self._yt(q, f"▶ {name[:28]} Tutorial"))
            google_url = (f"https://www.google.com/search?q="
                          f"{_urllib_parse.quote(name + ' FH Lernmaterial')}")
            web_actions.append(self._web(google_url, f"🔍 Google: {name[:28]}"))
        return yt_queries, web_actions

    @staticmethod
    def _parse_exam_date(text: str) -> Optional[str]:
        """Versucht, ein Datum aus deutschem Freitext zu parsen. Gibt ISO-String zurück oder None."""
        import re as _re2
        t = text.lower()
        # Format: 28.03.2026 / 28.03.26 / 28/03/2026
        m = _re2.search(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", t)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            try:
                from datetime import date as _dt
                return _dt(y, mo, d).isoformat()
            except ValueError:
                pass
        # Format: "am 28. März" / "am 5. April 2026"
        month_map = {"januar":1,"february":2,"februar":2,"märz":3,"april":4,"mai":5,
                     "juni":6,"juli":7,"august":8,"september":9,"oktober":10,
                     "november":11,"dezember":12}
        m2 = _re2.search(r"(\d{1,2})\.\s*([a-zäöü]+)(?:\s+(\d{4}))?", t)
        if m2:
            d2, mon_str = int(m2.group(1)), m2.group(2)
            y2 = int(m2.group(3)) if m2.group(3) else date.today().year
            mo2 = month_map.get(mon_str)
            if mo2:
                try:
                    return date(y2, mo2, d2).isoformat()
                except ValueError:
                    pass
        return None

    def _build_rich_topic_html(self, topic: str, matched_mod: Optional[dict] = None) -> str:
        """Baut einen HTML-Block mit mehreren Links zu einem Thema (YouTube + Web + Wikipedia)."""
        q_de = _urllib_parse.quote(f"{topic} erklärt Deutsch")
        q_tut = _urllib_parse.quote(f"{topic} Tutorial Deutsch")
        q_fh  = _urllib_parse.quote(f"{topic} Grundlagen FH Studium")
        yt1   = f"https://www.youtube.com/results?search_query={q_de}"
        yt2   = f"https://www.youtube.com/results?search_query={q_tut}"
        yt3   = f"https://www.youtube.com/results?search_query={q_fh}"
        goog  = f"https://www.google.com/search?q={_urllib_parse.quote(topic + ' Lernmaterial Studium')}"
        wiki  = f"https://de.wikipedia.org/wiki/{_urllib_parse.quote(topic.replace(' ','_'))}"
        khan  = f"https://www.khanacademy.org/search?page_search_query={_urllib_parse.quote(topic)}"

        parts = [f"<b>🔍 Ressourcen zu &ldquo;{topic}&rdquo;:</b><br><br>"]

        # ── YouTube ──
        parts.append("<b>🎬 YouTube-Videos:</b><br>")
        parts.append(f'&nbsp;&nbsp;<a href="{yt1}">▶ {topic} erklärt (Deutsch)</a><br>')
        parts.append(f'&nbsp;&nbsp;<a href="{yt2}">▶ {topic} Tutorial (Deutsch)</a><br>')
        parts.append(f'&nbsp;&nbsp;<a href="{yt3}">▶ {topic} FH-Niveau (Deutsch)</a><br><br>')

        # ── Wikipedia (immer anzeigen) ──
        parts.append("<b>📖 Wikipedia:</b><br>")
        parts.append(f'&nbsp;&nbsp;<a href="{wiki}">📖 Wikipedia: {topic}</a><br><br>')

        # ── Modulspezifische Ressourcen ──
        if matched_mod:
            code = (matched_mod.get("code") or "").strip()
            if code in self.MODULE_RESOURCES:
                yt_qs, web_rs = self.MODULE_RESOURCES[code]
                if yt_qs:
                    extra_q = _urllib_parse.quote(yt_qs[0])
                    parts.append(f'&nbsp;&nbsp;<a href="https://www.youtube.com/results?search_query={extra_q}">'
                                  f'⭐ {yt_qs[0][:55]}</a><br><br>')
                if web_rs:
                    parts.append("<b>📚 Empfohlene Webseiten:</b><br>")
                    for label, url in web_rs[:4]:
                        parts.append(f'&nbsp;&nbsp;<a href="{url}">{label}</a><br>')
                    parts.append("<br>")
        else:
            # Generische Fach-Ressourcen
            subj = self._detect_subject(topic)
            if subj and subj in self.RESOURCES:
                parts.append("<b>📚 Empfohlene Webseiten:</b><br>")
                for label, url in self.RESOURCES[subj][:4]:
                    parts.append(f'&nbsp;&nbsp;<a href="{url}">{label}</a><br>')
                parts.append("<br>")
            else:
                parts.append("<b>🌐 Weitere Quellen:</b><br>")
                parts.append(f'&nbsp;&nbsp;<a href="{goog}">🔍 Google: {topic} Lernmaterial</a><br>')
                parts.append(f'&nbsp;&nbsp;<a href="{khan}">📐 Khan Academy: {topic}</a><br>')
                parts.append("<br>")

        parts.append(
            "<span style='font-size:11px;color:#6B7280;'>"
            "Klick auf einen Link &mdash; öffnet in deinem Browser.</span>"
        )
        return "".join(parts)

    @staticmethod
    def _nav(idx: int, label: str) -> str:
        return f"NAV|{idx}|{label}"

    @staticmethod
    def _yt(query: str, label: str) -> str:
        return f"YT|{_urllib_parse.quote(query)}|{label}"

    @staticmethod
    def _web(url: str, label: str) -> str:
        return f"WEB|{url}|{label}"

    def _situation(self) -> dict:
        """Snapshot der aktuellen Studentensituation."""
        today = date.today()
        today_str = today.isoformat()
        streak = self.repo.get_study_streak()
        week_secs = self.repo.seconds_studied_week(today - timedelta(days=today.weekday()))
        active_mods = self.repo.list_modules("active")
        all_tasks = self.repo.list_tasks(status="Open")
        overdue = [t for t in all_tasks if (t["due_date"] or "") < today_str and t["due_date"]]
        due_today = [t for t in all_tasks if (t["due_date"] or "") == today_str]
        upcoming = self.repo.upcoming_exams(within_days=14)
        most_urgent = upcoming[0] if upcoming else None
        urgent_days = days_until(most_urgent["exam_date"]) if most_urgent else None
        sr_due = 0
        for m in active_mods:
            for t in self.repo.list_topics(m["id"]):
                lr = t["last_reviewed"] if "last_reviewed" in t.keys() else ""
                lvl = int(t["knowledge_level"]) if t["knowledge_level"] else 0
                if lr and lvl < 3:
                    try:
                        if (today - datetime.fromisoformat(lr).date()).days >= 3:
                            sr_due += 1
                    except Exception:
                        pass
        return {
            "streak": streak, "week_h": week_secs / 3600,
            "active_mods": active_mods, "n_mods": len(active_mods),
            "open_tasks": len(all_tasks), "overdue": overdue, "due_today": due_today,
            "most_urgent": most_urgent, "urgent_days": urgent_days,
            "upcoming": upcoming, "sr_due": sr_due,
        }

    # ── Hauptmethode ─────────────────────────────────────────────────────────

    def respond(self, text: str, ctx: Optional[dict] = None) -> tuple[str, list[str]]:
        """
        Gibt (message_html, list_of_action_strings) zurück.
        Aktions-Format: "ACTION|data|Label" oder einfacher Text (→ als Nachricht schicken).
        ctx: Gesprächskontext {"last_subject", "last_intent", "turn"}
        """
        try:
            return self._respond_inner(text, ctx)
        except Exception as _e:
            import traceback; traceback.print_exc()
            return (
                "\u26a0\ufe0f Kurzer Fehler aufgetreten \u2014 versuch es nochmal oder nenn mir ein Fach.",
                ["Wo anfangen?", self._nav(self.PAGE_TIMER, "\u23f1 Timer"), "Lernressourcen"],
            )

    def _respond_inner(self, text: str, ctx: Optional[dict] = None) -> tuple[str, list[str]]:
        ctx = ctx or {}
        intent = self._intent(text)
        # 1) Erst: konkretes DB-Modul suchen (genaueste Erkennung)
        matched_mod = self._match_module(text)
        # 2) Dann: generische Fach-Erkennung (Fallback)
        subject = self._detect_subject(text)
        # 3) Dann: Kontext übernehmen wenn nichts erkannt
        if not subject and not matched_mod:
            subject = ctx.get("last_subject")
        last_intent = ctx.get("last_intent")
        last_mod_code = ctx.get("last_mod_code")
        turn = ctx.get("turn", 0)

        # Kontext mit Modul-Code aus Kontext befüllen falls kein neuer Treffer
        if not matched_mod and last_mod_code:
            all_m = self.repo.list_modules("all")
            for m in all_m:
                if (m["code"] if "code" in m.keys() else "") == last_mod_code:
                    matched_mod = dict(m)
                    break

        s = self._situation()
        mu = s["most_urgent"]
        name = mu["name"] if mu else "dein Modul"

        # ── Follow-up-Erkennung (kontextsensitiv) ───────────────────────────
        follow_up_kw = ["was sonst", "noch mehr", "andere", "weiteres", "mehr davon",
                        "was noch", "alternative", "sonst noch", "weitere links"]
        is_followup = any(kw in text.lower() for kw in follow_up_kw)

        if is_followup and last_intent in ("youtube", "resource"):
            if matched_mod:
                yt_actions, web_actions = self._module_links(matched_mod)
                mod_name = matched_mod.get("name", "Modul")
                msg = (f"🔎 Noch mehr zu <b>{mod_name}</b>:<br><br>"
                       f"Weitere Ressourcen und Übungslinks:")
                replies = web_actions[:2] + yt_actions[:1]
                google_url = (f"https://www.google.com/search?q="
                              f"{_urllib_parse.quote(mod_name + ' Übungsaufgaben Lösungen')}")
                replies.append(self._web(google_url, f"🔍 Übungsaufgaben: {mod_name[:20]}"))
                return msg, replies[:3]
            elif subject:
                resources = self.RESOURCES.get(subject, [])
                google_url = (f"https://www.google.com/search?q="
                              f"{_urllib_parse.quote(subject + ' Studium Übungen Aufgaben')}")
                msg = (f"🔎 Noch mehr zu <b>{subject}</b>:")
                replies = [self._web(url, label[:35]) for label, url in resources[1:3]]
                replies.append(self._web(google_url, f"🔍 Übungen: {subject}"))
                return msg, replies

        # ── Prüfungs-Eintragung (Multi-Turn) ────────────────────────────────
        pending = ctx.get("pending")

        # Fortsetzung: Modul-Auswahl nach Datum
        if pending and pending.get("action") == "exam_entry" and not pending.get("mod_id"):
            exam_date = pending.get("date")
            # Versuche Modul aus diesem Text zu erkennen
            chosen = self._match_module(text)
            if not chosen:
                # Nummern-Auswahl (1, 2, 3 …)?
                import re as _re3
                m_num = _re3.match(r"^\s*(\d+)\s*$", text.strip())
                if m_num:
                    idx_c = int(m_num.group(1)) - 1
                    pending_mods = pending.get("mod_list", [])
                    if 0 <= idx_c < len(pending_mods):
                        chosen = pending_mods[idx_c]
            if chosen:
                mod_id   = chosen.get("id")
                mod_name = chosen.get("name", "Modul")
                self.repo.update_module(mod_id, exam_date=exam_date)
                ctx["pending"] = None
                msg = (f"✅ <b>Prüfungstermin gespeichert!</b><br><br>"
                       f"📅 <b>{mod_name}</b> — "
                       f"Prüfung am <b>{exam_date}</b><br><br>"
                       f"Ich habe das Datum in deinem Modulplan eingetragen. "
                       f"Du siehst es im Kalender und im Prüfungsübersicht-Tab.")
                return msg, [
                    self._nav(self.PAGE_KALENDER, "📅 Kalender"),
                    self._nav(self.PAGE_PRÜFUNGEN, "📝 Prüfungen"),
                    f"Lernplan für {mod_name[:20]} erstellen",
                ]
            else:
                # Modul immer noch unklar
                active = self.repo.list_modules("active") or self.repo.list_modules("all")
                mod_list = [dict(m) for m in active[:6]]
                ctx["pending"]["mod_list"] = mod_list
                lines = "".join(
                    f"&nbsp;&nbsp;<b>{i+1}.</b> {m.get('name','?')} "
                    f"<span style='color:#6B7280;'>({m.get('code','')})</span><br>"
                    for i, m in enumerate(mod_list)
                )
                return (
                    f"❓ Für welches Modul ist die Prüfung am <b>{exam_date}</b>?<br><br>"
                    f"{lines}<br>Gib die Nummer oder den Namen ein:",
                    [m.get("name", "?")[:28] for m in mod_list[:3]],
                )

        # Neue Prüfungs-Eintragung
        if intent == "exam_entry":
            exam_date = self._parse_exam_date(text)
            # Modul aus Text erkennen?
            exam_mod = self._match_module(text) or (matched_mod if matched_mod else None)

            if exam_date and exam_mod:
                mod_id   = exam_mod.get("id")
                mod_name = exam_mod.get("name", "Modul")
                ctx["pending"] = None
                # Gewichtung aus Text? (z.B. "40%" / "gewichtung 40")
                import re as _re4
                w_match = _re4.search(r"(\d+)\s*%", text)
                weighting = float(w_match.group(1)) / 100.0 if w_match else None
                if weighting is not None:
                    self.repo.update_module(mod_id, exam_date=exam_date, weighting=weighting)
                    w_note = f", Gewichtung {int(weighting*100)}%"
                else:
                    self.repo.update_module(mod_id, exam_date=exam_date)
                    w_note = ""
                msg = (f"✅ <b>Eingetragen!</b><br><br>"
                       f"📅 <b>{mod_name}</b>{w_note}<br>"
                       f"Prüfung am <b>{exam_date}</b><br><br>"
                       f"Möchtest du gleich einen Lernplan dafür erstellen?")
                return msg, [
                    f"📋 Lernplan für {mod_name[:20]}",
                    self._nav(self.PAGE_KALENDER, "📅 Kalender"),
                    self._nav(self.PAGE_PRÜFUNGEN, "📝 Prüfungen"),
                ]

            if exam_date and not exam_mod:
                # Datum bekannt, Modul fehlt → nachfragen
                active = self.repo.list_modules("active") or self.repo.list_modules("all")
                mod_list = [dict(m) for m in active[:6]]
                ctx["pending"] = {"action": "exam_entry", "date": exam_date,
                                  "mod_id": None, "mod_list": mod_list}
                lines = "".join(
                    f"&nbsp;&nbsp;<b>{i+1}.</b> {m.get('name','?')} "
                    f"<span style='color:#6B7280;'>({m.get('code','')})</span><br>"
                    for i, m in enumerate(mod_list)
                )
                return (
                    f"📅 Datum erkannt: <b>{exam_date}</b><br><br>"
                    f"Für welches Modul ist diese Prüfung?<br><br>{lines}<br>"
                    f"Gib die Nummer oder den Namen ein.",
                    [m.get("name", "?")[:28] for m in mod_list[:3]],
                )

            if not exam_date:
                # Kein Datum erkannt → Datum erfragen
                ctx["pending"] = {"action": "exam_entry", "date": None, "mod_id": None}
                return (
                    "📅 <b>Prüfungstermin eintragen</b><br><br>"
                    "Wann findet die Prüfung statt? Gib das Datum ein, z.B.:<br>"
                    "<i>28.03.2026</i> oder <i>28. April 2026</i>",
                    ["28.03.2026", "15.04.2026", "01.06.2026"],
                )

        # ── Erklärung + Multi-Link Antwort ──────────────────────────────────
        if intent == "explain":
            # Extrahiere das eigentliche Thema aus dem Text
            import re as _re5
            t_low = text.lower()
            # Strip intent keywords to get the actual topic
            for kw in ["wie funktioniert", "wie funktionieren", "was ist", "was sind",
                       "erkläre mir", "erkläre", "erklär mir", "wie geht", "wie macht man",
                       "was bedeutet", "definition von", "einführung in", "grundlagen von",
                       "zeig mir wie", "ich verstehe nicht", "ich check nicht",
                       "bitte erkläre", "bitte erklär"]:
                t_low = t_low.replace(kw, "").strip()
            # Remove trailing punctuation and filler
            t_low = _re5.sub(r"[?!.,]+$", "", t_low).strip()
            topic = t_low if len(t_low) > 1 else (
                matched_mod.get("name") if matched_mod else subject or text.strip())
            # Capitalize properly
            topic = topic.strip().title() if topic == topic.lower() else topic.strip()

            html_links = self._build_rich_topic_html(topic, matched_mod)
            quick = []
            if matched_mod:
                quick.append(f"📋 Lernplan für {matched_mod.get('name','')[:20]}")
                quick.append(self._nav(self.PAGE_WISSEN, "🧠 Wissensmap"))
            else:
                quick.append(self._yt(f"{topic} erklärt Deutsch", f"▶ Mehr Videos: {topic[:22]}"))
                quick.append(self._nav(self.PAGE_TIMER, "⏱ Jetzt lernen"))
            quick.append("Noch mehr Ressourcen")
            return html_links, quick[:3]

        # ── YouTube-Suche ───────────────────────────────────────────────────
        if intent == "youtube":
            # Konkretes Modul gefunden → spezifische Queries
            if matched_mod:
                mod_name = matched_mod.get("name", "Modul")
                code = matched_mod.get("code", "")
                yt_actions, web_actions = self._module_links(matched_mod)
                has_exam_soon = mu and s.get("urgent_days") and s["urgent_days"] <= 14
                exam_note = (f"<br><br>⚠️ Prüfung in <b>{s['urgent_days']} Tagen</b> — "
                             f"Fokus auf Prüfungsrelevantes!" if has_exam_soon and
                             mu and (mu["name"] if "name" in mu.keys() else "") == mod_name else "")
                msg = (f"🎬 YouTube für <b>{mod_name}</b>:{exam_note}<br><br>"
                       f"Klick auf den Link — öffnet direkt in YouTube.")
                replies = yt_actions[:2] + web_actions[:1]
                return msg, replies[:3]

            if subject:
                q1 = f"{subject} Studium Erklärung Deutsch"
                q2 = f"{subject} Tutorial Deutsch"
                has_exam_soon = mu and s.get("urgent_days") and s["urgent_days"] <= 14
                msg = (f"🎬 YouTube für <b>{subject}</b>:<br><br>"
                       f"Klick auf den gewünschten Link — er öffnet YouTube direkt.")
                replies = [
                    self._yt(q1, f"▶ {subject} Erklärung"),
                    self._yt(q2, f"▶ {subject} Tutorial"),
                ]
                if has_exam_soon:
                    replies.append(self._yt(
                        f"{subject} Prüfungsvorbereitung kompakt", "▶ Prüfungsvorbereitung"))
                else:
                    replies.append(self._yt(f"{subject} Zusammenfassung", "▶ Zusammenfassung"))
                return msg, replies
            # Kein Fach → aus Kontext oder Module vorschlagen
            mod_names = [m["name"] for m in s["active_mods"][:3]]
            if mod_names:
                msg = (f"🎬 Zu welchem Fach suchst du Videos?<br><br>"
                       f"Deine aktiven Module:")
                replies = [self._yt(f"{n} Studium Erklärung Deutsch", f"▶ {n[:22]}") for n in mod_names[:2]]
                replies.append(self._yt("Lerntechniken Studium Motivation", "▶ Lerntipps"))
            else:
                msg = ("🎬 Zu welchem Fach suchst du Videos?<br><br>"
                       "Nenn mir das Thema, z.B. <i>&ldquo;Analysis Videos&rdquo;</i>.")
                replies = [
                    self._yt("Mathematik Studium Erklärung", "▶ Mathe"),
                    self._yt("Programmierung Python Tutorial Deutsch", "▶ Python"),
                    self._yt("Lerntechniken Studium", "▶ Lerntipps"),
                ]
            return msg, replies

        # ── Web-Ressourcen ──────────────────────────────────────────────────
        if intent == "resource":
            # Konkretes Modul → spezifische Ressourcen
            if matched_mod:
                mod_name = matched_mod.get("name", "Modul")
                yt_actions, web_actions = self._module_links(matched_mod)
                google_url = (f"https://www.google.com/search?q="
                              f"{_urllib_parse.quote(mod_name + ' FH Lernmaterial Skript')}")
                msg = (f"🌐 Ressourcen für <b>{mod_name}</b>:<br><br>"
                       f"Klick auf den Link — öffnet direkt im Browser.")
                replies = web_actions[:2] + [self._web(google_url, f"🔍 Skripte: {mod_name[:20]}")]
                return msg, replies[:3]
            if subject:
                resources = self.RESOURCES.get(subject, [])
                google_url = (f"https://www.google.com/search?q="
                              f"{_urllib_parse.quote(subject + ' Lernmaterial Studium')}")
                wiki_url = (f"https://de.wikipedia.org/wiki/"
                            f"{_urllib_parse.quote(subject.title())}")
                msg = (f"🌐 Ressourcen für <b>{subject}</b>:<br><br>"
                       f"Klick auf den Link — öffnet direkt im Browser.")
                replies = [self._web(url, label[:35]) for label, url in resources[:2]]
                if not replies:
                    replies.append(self._web(wiki_url, f"📖 Wikipedia: {subject[:20]}"))
                replies.append(self._web(google_url, f"🔍 Google: {subject} lernen"))
                return msg, replies
            # Kein Fach erkannt → Module aus DB anbieten
            all_mods = self.repo.list_modules("active")
            msg = ("🌐 Zu welchem Fach/Modul suchst du Ressourcen?<br><br>"
                   "Nenn den Modulnamen oder Code, z.B. <i>DBS</i>, <i>Algorithmen</i>.")
            replies = []
            for m in all_mods[:2]:
                yt_a, web_a = self._module_links(dict(m))
                if web_a:
                    replies.append(web_a[0])
            replies.append(self._web("https://de.khanacademy.org", "📚 Khan Academy"))
            return msg, replies[:3]

        # ── Tab-Navigation ──────────────────────────────────────────────────
        if intent == "navigate":
            t = text.lower()
            nav_map = [
                (["timer", "pomodoro"],                       self.PAGE_TIMER,        "⏱ Timer"),
                (["aufgaben", "tasks", "todo", "aufgabe"],    self.PAGE_AUFGABEN,     "✅ Aufgaben"),
                (["noten", "grade", "notenseite"],            self.PAGE_NOTEN,        "📈 Noten"),
                (["prüfungen", "exams", "exam", "klausur"],   self.PAGE_PRÜFUNGEN,    "🎯 Prüfungen"),
                (["wissen", "knowledge", "themen", "topics"], self.PAGE_WISSEN,       "🧠 Wissen"),
                (["kalender", "calendar"],                    self.PAGE_KALENDER,     "📅 Kalender"),
                (["module", "fächer", "fach"],                self.PAGE_MODULE,       "📚 Module"),
                (["studienplan", "plan"],                     self.PAGE_STUDIENPLAN,  "📊 Studienplan"),
                (["dashboard", "übersicht", "home"],          self.PAGE_DASHBOARD,    "🏠 Dashboard"),
            ]
            for keywords, idx, label in nav_map:
                if any(kw in t for kw in keywords):
                    msg = f"Navigiere zu <b>{label}</b>."
                    return msg, [self._nav(idx, f"→ {label} öffnen")]
            msg = "Wohin soll ich navigieren? Wähle eine Seite:"
            return msg, [
                self._nav(self.PAGE_DASHBOARD,   "🏠 Dashboard"),
                self._nav(self.PAGE_TIMER,       "⏱ Timer"),
                self._nav(self.PAGE_PRÜFUNGEN,   "🎯 Prüfungen"),
            ]

        # ── Timer starten ───────────────────────────────────────────────────
        if intent == "timer_req":
            mod_hint = f"Fokus: <b>{name}</b>." if mu else "Wähle dein Modul im Timer."
            msg = (f"⏱ <b>Lernsession starten!</b><br><br>"
                   f"25 Minuten Pomodoro — kein Handy, kein Social Media.<br>{mod_hint}")
            return msg, [
                self._nav(self.PAGE_TIMER, "⏱ Timer öffnen"),
                self._yt("Pomodoro Focus Music Study", "🎵 Fokus-Musik (YT)"),
            ]

        # ── Lernplan erstellen ──────────────────────────────────────────────
        if intent == "exam_plan":
            if not s["upcoming"]:
                msg = ("📋 Für einen konkreten Lernplan brauche ich deine Prüfungstermine.<br><br>"
                       "Trag dein Prüfungsdatum beim Modul ein — dann erstelle ich dir einen maßgeschneiderten Plan.")
                return msg, [
                    self._nav(self.PAGE_PRÜFUNGEN, "🎯 Prüfungstermin eintragen"),
                    self._nav(self.PAGE_MODULE,    "📚 Module anschauen"),
                ]
            if mu:
                d = s["urgent_days"] or 14
                available_h = max(d * 5, 2)
                topics = self.repo.list_topics(mu["id"])
                weak = [t for t in topics if (int(t["knowledge_level"]) if t["knowledge_level"] else 0) < 3]
                msg = (f"📋 <b>Lernplan für {name}</b> — {d} Tage verbleibend:<br><br>")
                if weak:
                    msg += f"<b>Priorisierte Themen</b> ({len(weak)} schwach):<br>"
                    for t in weak[:5]:
                        lvl = int(t["knowledge_level"]) if t["knowledge_level"] else 0
                        msg += f"&nbsp;&nbsp;{'🔴' if lvl <= 1 else '🟠'} {t['title']}<br>"
                    if len(weak) > 5:
                        msg += f"&nbsp;&nbsp;… und {len(weak) - 5} weitere<br>"
                    msg += f"<br>⏰ Verfügbar: ~{available_h:.0f}h → ~{available_h/max(len(weak),1):.1f}h/Thema"
                else:
                    msg += "✅ Alle Themen sind stark! Fokus auf Wiederholung und Übungsaufgaben."
                return msg, [
                    self._nav(self.PAGE_WISSEN,    "🧠 Themen ansehen"),
                    self._nav(self.PAGE_TIMER,     "⏱ Lernsession starten"),
                    self._nav(self.PAGE_PRÜFUNGEN, "🎯 Prüfungsübersicht"),
                ]
            return ("📋 Öffne deinen Studienplan:",
                    [self._nav(self.PAGE_STUDIENPLAN, "📊 Studienplan öffnen")])

        # ── Begrüßung ───────────────────────────────────────────────────────
        if intent == "greeting":
            if s["n_mods"] == 0:
                msg = (
                    "👋 <b>Hallo! Ich bin dein Studien-Coach.</b><br><br>"
                    "Ich helfe dir mit Lernplänen, YouTube-Videos, "
                    "Lernressourcen und App-Navigation — offline &amp; kostenlos.<br><br>"
                    "Lege zuerst deine Module an, damit ich dir gezielt helfen kann."
                )
                return msg, [
                    self._nav(self.PAGE_MODULE,       "📚 Module anlegen"),
                    self._nav(self.PAGE_STUDIENPLAN,  "📊 Studienplan ansehen"),
                    self._yt("Lerntechniken Studium Motivation",
                             "🎬 Lerntipps Videos"),
                ]
            if s["urgent_days"] is not None and s["urgent_days"] <= 5:
                msg = (
                    f"👋 <b>Hallo!</b> Ich sehe eine dringende Situation:<br><br>"
                    f"🚨 <b>{name}</b> steht in <b>{s['urgent_days']} Tagen</b> an.<br><br>"
                    f"Soll ich dir einen Crashplan erstellen?"
                )
                return msg, [
                    "🚨 Crashplan erstellen",
                    self._nav(self.PAGE_WISSEN, "🧠 Schwache Themen ansehen"),
                    self._nav(self.PAGE_TIMER,  "⏱ Lernsession starten"),
                    self._yt(f"{name} Prüfungsvorbereitung kompakt",
                             f"🎬 Videos: {name[:16]}"),
                ]
            if s["overdue"]:
                t = s["overdue"][0]
                n_over = len(s["overdue"])
                msg = (
                    f"👋 <b>Hallo!</b> Ein paar Dinge fallen mir auf:<br><br>"
                    f"⚠️ <b>{n_over} überfällige Aufgabe{'n' if n_over > 1 else ''}</b> — "
                    f"Dringlichste: <b>&ldquo;{t['title']}&rdquo;</b><br><br>"
                    f"Was willst du zuerst angehen?"
                )
                return msg, [
                    self._nav(self.PAGE_AUFGABEN, "✅ Aufgaben öffnen"),
                    "📋 Lernplan erstellen",
                    "📊 Fortschritt zeigen",
                ]
            streak_emoji = " 🔥" if s["streak"] > 2 else ""
            msg = (
                f"👋 <b>Hallo!</b> Hier ist dein aktueller Stand:<br><br>"
                f"📚 <b>{s['n_mods']} Module</b> aktiv · "
                f"✅ <b>{s['open_tasks']} Aufgaben</b> offen · "
                f"📅 Streak <b>{s['streak']} Tage</b>{streak_emoji}<br><br>"
                f"Was kann ich für dich tun?"
            )
            return msg, [
                "📊 Fortschritt zeigen",
                "🎬 Lernvideos finden",
                "📋 Lernplan erstellen",
                self._nav(self.PAGE_TIMER, "⏱ Timer starten"),
            ]

        # ── Panik / Prüfungsstress ──────────────────────────────────────────
        elif intent == "panic":
            if not s["upcoming"]:
                msg = ("🚨 Das klingt stressig — aber ich finde keine Prüfungen in deinem Kalender.<br><br>"
                       "Trag dein Prüfungsdatum ein, dann erstelle ich dir sofort einen Crashplan.")
                return msg, [
                    self._nav(self.PAGE_PRÜFUNGEN, "🎯 Prüfungsdatum eintragen"),
                    "Was soll ich ohne Datum tun?",
                ]
            if mu and s["urgent_days"] is not None:
                d = s["urgent_days"]
                available_h = max(d * 5, 2)
                topics = self.repo.list_topics(mu["id"])
                weak = [t for t in topics if (int(t["knowledge_level"]) if t["knowledge_level"] else 0) < 3]
                msg = (f"🚨 <b>Crashplan: {name}</b><br>"
                       f"⏳ <b>{d} Tag{'e' if d != 1 else ''}</b> · ~<b>{available_h:.0f}h</b> Lernzeit<br><br>")
                if weak:
                    msg += f"<b>{len(weak)} schwache Themen</b> (Priorität):<br>"
                    for t in weak[:5]:
                        lvl = int(t["knowledge_level"]) if t["knowledge_level"] else 0
                        msg += f"&nbsp;&nbsp;{'🔴' if lvl <= 1 else '🟠'} {t['title']}<br>"
                    if len(weak) > 5:
                        msg += f"&nbsp;&nbsp;… +{len(weak) - 5} weitere<br>"
                    msg += "<br>💡 <b>Rote zuerst → orange → Wiederholung</b>"
                else:
                    msg += "✅ Deine Themen sind stabil. Fokus auf Übungsaufgaben & Wiederholung."
                yt_q = f"{mu['name']} Prüfungsvorbereitung"
                return msg, [
                    self._nav(self.PAGE_TIMER,  "⏱ Session starten"),
                    self._nav(self.PAGE_WISSEN, "🧠 Themen öffnen"),
                    self._yt(yt_q, f"🎬 Videos: {mu['name'][:16]}"),
                ]
            exams_str = ", ".join(f"<b>{e['name']}</b> ({days_until(e['exam_date'])}d)"
                                  for e in s["upcoming"][:2])
            return (f"🚨 Bald: {exams_str}.", [
                "📋 Crashplan erstellen",
                self._nav(self.PAGE_TIMER, "⏱ Timer starten"),
            ])

        # ── Wo anfangen ─────────────────────────────────────────────────────
        elif intent == "start":
            if s["n_mods"] == 0:
                return ("🧭 Zuerst Module anlegen — das dauert 2 Minuten.",
                        [self._nav(self.PAGE_MODULE, "📚 Module anlegen")])
            if s["overdue"]:
                t = s["overdue"][0]
                msg = (f"🧭 <b>Priorität 1:</b> Aufgabe <b>&ldquo;{t['title']}&rdquo;</b> ist überfällig.<br>"
                       f"Danach: 25 Min für <b>{name}</b>.")
                return msg, [
                    self._nav(self.PAGE_AUFGABEN, "✅ Aufgaben öffnen"),
                    self._nav(self.PAGE_TIMER,    "⏱ Timer starten"),
                ]
            elif mu and s["urgent_days"] is not None and s["urgent_days"] <= 10:
                msg = (f"🧭 Dringlichstes: <b>{name}</b> in <b>{s['urgent_days']} Tagen</b>.<br><br>"
                       f"Starte jetzt eine 25-Min Session. Kein Handy, kein Social Media.")
                return msg, [
                    self._nav(self.PAGE_TIMER,  "⏱ 25-Min Session"),
                    "📋 Crashplan erstellen",
                    self._nav(self.PAGE_WISSEN, "🧠 Schwache Themen"),
                ]
            elif s["sr_due"] > 0:
                msg = (f"🧭 Bestes was du jetzt tun kannst: "
                       f"<b>{s['sr_due']} Thema{'s' if s['sr_due'] != 1 else ''}</b> wiederholen. "
                       f"20 Minuten — stärkt Langzeitgedächtnis.")
                return msg, [
                    self._nav(self.PAGE_WISSEN, "🧠 Zur Wissensseite"),
                    self._nav(self.PAGE_TIMER,  "⏱ 25-Min Timer"),
                ]
            else:
                return ("🧭 Starte eine 25-Min Lerneinheit. Der Anfang ist das Schwerste.", [
                    self._nav(self.PAGE_TIMER,       "⏱ Timer starten"),
                    self._nav(self.PAGE_STUDIENPLAN, "📊 Studienplan"),
                ])

        # ── Motivation ──────────────────────────────────────────────────────
        elif intent == "motivation":
            import random as _rnd
            streak_msg = (f"<br><br>💪 Du hast bereits <b>{s['streak']} Tage</b> in Folge gelernt "
                          f"— das ist bemerkenswert. Nicht aufhören!"
                          if s["streak"] > 2 else "")
            quotes = [
                ("Der Anfang ist die Hälfte des Ganzen.", "Aristoteles"),
                ("Bildung ist die mächtigste Waffe, die du einsetzen kannst, um die Welt zu verändern.", "Nelson Mandela"),
                ("Es ist nicht genug, zu wissen — man muss auch anwenden.", "Goethe"),
                ("Investiere in dich selbst — das ist die beste Investition.", "Warren Buffett"),
                ("Du musst nicht groß sein, um anzufangen — aber du musst anfangen, um groß zu sein.", "Zig Ziglar"),
            ]
            quote, author = _rnd.choice(quotes)
            mod_hint = (f"Starte mit <b>{name}</b> — auch nur 25 Minuten."
                        if mu else "Starte mit dem ersten Thema auf deiner Liste.")
            msg = (f"😊 <b>Keine Lust? Völlig normal.</b>{streak_msg}<br><br>"
                   f"🧠 <b>Trick #1:</b> Nur 5 Minuten anfangen. Dann meistens nicht mehr aufhören.<br>"
                   f"🧠 <b>Trick #2:</b> Ablenkungen weg — Handy in Flugmodus, 1 Tab offen.<br>"
                   f"🧠 <b>Trick #3:</b> {mod_hint}<br><br>"
                   f"💬 <i>&ldquo;{quote}&rdquo; — {author}</i>")
            return msg, [
                self._nav(self.PAGE_TIMER, "⏱ 5-Min Pomodoro starten"),
                self._yt("Studium Motivation Produktivität Tipps", "🎬 Motivations-Videos"),
                self._web("https://de.wikipedia.org/wiki/Pomodoro-Technik",
                          "📖 Wikipedia: Pomodoro-Technik"),
            ]

        # ── Fortschritt ─────────────────────────────────────────────────────
        elif intent == "progress":
            week_h = s["week_h"]
            if mu:
                target_h = self.repo.ects_target_hours(mu["id"])
                studied_h = self.repo.seconds_studied_for_module(mu["id"]) / 3600
                pct = min(100, int(studied_h / target_h * 100)) if target_h > 0 else 0
                msg = (f"📊 <b>Dein Fortschritt:</b><br><br>"
                       f"• Diese Woche: <b>{week_h:.1f}h</b><br>"
                       f"• Lernserie: <b>{s['streak']} Tage</b><br>"
                       f"• {name}: <b>{pct}%</b> ({studied_h:.1f}h / {target_h:.0f}h)<br>"
                       f"• Offene Aufgaben: <b>{s['open_tasks']}</b><br><br>")
                if pct < 30 and s["urgent_days"] is not None and s["urgent_days"] <= 14:
                    msg += f"⚠️ {name} braucht dringend mehr Aufmerksamkeit!"
                elif pct >= 80:
                    msg += "🎉 Super — du bist auf einem sehr guten Weg!"
                else:
                    msg += "👍 Solider Fortschritt. Bleib dran!"
            else:
                msg = (f"📊 Diese Woche: <b>{week_h:.1f}h</b> · "
                       f"Streak: <b>{s['streak']} Tage</b> · "
                       f"Aufgaben: <b>{s['open_tasks']}</b>")
            return msg, [
                self._nav(self.PAGE_NOTEN,    "📈 Noten ansehen"),
                self._nav(self.PAGE_PRÜFUNGEN,"🎯 Prüfungsübersicht"),
                "Was als nächstes?",
            ]

        # ── Wenig Zeit ──────────────────────────────────────────────────────
        elif intent == "time":
            msg = (f"⚡ Selbst <b>15 Minuten</b> bringen was!<br><br>"
                   f"In 15 Min: 1 Thema wiederholen"
                   f"{', 1 überfällige Aufgabe' if s['overdue'] else ''}"
                   f" oder Stichpunkte für {name} durchgehen.")
            return msg, [
                self._nav(self.PAGE_TIMER,    "⏱ 15-Min Timer"),
                self._nav(self.PAGE_AUFGABEN, "✅ Aufgaben"),
            ]

        # ── Noten & Ziele ────────────────────────────────────────────────────
        elif intent == "grade":
            if not mu:
                return ("📈 Für eine Notenprognose Module mit Prüfungsterminen eintragen.",
                        [self._nav(self.PAGE_MODULE, "📚 Module anlegen")])
            avg = self.repo.module_weighted_grade(mu["id"])
            mod_full = self.repo.get_module(mu["id"])
            tg_raw = (mod_full or {}).get("target_grade")
            tg = float(tg_raw) if tg_raw else None
            if avg is not None and tg is not None:
                diff = avg - tg
                if diff >= 0:
                    msg = (f"📈 <b>{name}</b>: <b>{avg:.1f}%</b> — "
                           f"<b>{diff:+.1f}%</b> über Ziel {tg:.1f}%. Sehr gut!")
                else:
                    msg = (f"📈 <b>{name}</b>: <b>{avg:.1f}%</b>, "
                           f"Ziel {tg:.1f}% — <b>{abs(diff):.1f}%</b> darunter.")
            elif avg is not None:
                msg = f"📈 Schnitt für <b>{name}</b>: <b>{avg:.1f}%</b>. Kein Ziel gesetzt."
            else:
                msg = f"📈 Noch keine Noten für <b>{name}</b> eingetragen."
            return msg, [
                self._nav(self.PAGE_NOTEN, "📈 Notenseite öffnen"),
                "Was soll ich tun?",
            ]

        # ── Generic / Modul oder Fach erkannt ───────────────────────────────
        else:
            if matched_mod:
                # Konkretes DB-Modul erkannt → maßgeschneiderte Antwort
                mod_name = matched_mod.get("name", "Modul")
                code = matched_mod.get("code", "")
                yt_actions, web_actions = self._module_links(matched_mod)
                extra = ""
                if mu and s.get("urgent_days") and s["urgent_days"] <= 14:
                    if (mu["name"] if "name" in mu.keys() else "") == mod_name:
                        extra = (f"<br><br>⚠️ Prüfung in <b>{s['urgent_days']} Tagen</b> — "
                                 f"Fokus auf Prüfungsthemen!")
                msg = (f"🔍 <b>{mod_name}</b>{extra}<br><br>"
                       f"Ich habe spezifische Ressourcen für dieses Modul:")
                replies = yt_actions[:1] + web_actions[:2]
                return msg, replies[:3]

            if subject:
                # Fach erkannt (generisch) → Ressourcen
                resources = self.RESOURCES.get(subject, [])
                google_url = (f"https://www.google.com/search?q="
                              f"{_urllib_parse.quote(subject + ' Studium Lernmaterial')}")
                extra = ""
                if mu and s.get("urgent_days") and s["urgent_days"] <= 14:
                    extra = (f"<br><br>⚠️ Prüfung in <b>{s['urgent_days']} Tagen</b> — "
                             f"Prüfungsthemen priorisieren!")
                msg = (f"🔍 <b>{subject}</b>{extra}")
                replies = [self._yt(f"{subject} Studium Erklärung Deutsch", f"🎬 YouTube: {subject[:20]}")]
                if resources:
                    label, url = resources[0]
                    replies.append(self._web(url, label[:35]))
                replies.append(self._web(google_url, f"🔍 Google: {subject[:20]}"))
                return msg, replies

            # Kein Intent, kein Fach erkannt → auf aktuelle Situation eingehen
            # Smarte Situation-basierte Antwort statt random-Tipp
            if s["overdue"]:
                t_item = s["overdue"][0]
                msg = (f"👀 Ich schaue auf deine Situation:<br><br>"
                       f"Du hast <b>{len(s['overdue'])} überfällige Aufgabe(n)</b> — "
                       f"die Dringlichste: <b>&ldquo;{t_item['title']}&rdquo;</b>.<br><br>"
                       f"Was meintest du genau? Nenn mir ein Fach, Thema oder dein Problem.")
                return msg, [
                    self._nav(self.PAGE_AUFGABEN, "✅ Aufgaben öffnen"),
                    "📋 Lernplan erstellen",
                    "🎬 Lernvideo suchen",
                ]
            if mu and s.get("urgent_days") and s["urgent_days"] <= 10:
                msg = (f"👀 Ich sehe: <b>{name}</b> steht in <b>{s['urgent_days']} Tagen</b> an.<br><br>"
                       f"Was beschäftigt dich? Nenn mir ein Thema, dann helfe ich gezielt.")
                return msg, [
                    f"🎬 Videos zu {name[:20]}",
                    "📋 Crashplan erstellen",
                    self._nav(self.PAGE_TIMER, "⏱ Session starten"),
                ]
            # Wirklich generisch → Hilfe-Menü mit aktiven Vorschlägen
            week_note = (f"Diese Woche: <b>{s['week_h']:.1f}h</b> gelernt"
                         f"{' · 🔥 ' + str(s['streak']) + ' Tage Serie' if s['streak'] > 2 else ''}.")
            msg = (
                f"💬 <b>Kein Problem — ich helfe gerne!</b><br>"
                f"<span style='color:#6B7280;font-size:12px;'>{week_note}</span><br><br>"
                "Schreib mir z.B.:<br>"
                "&rarr; Ein <b>Fach</b>: <i>&bdquo;Analysis&ldquo;</i>, <i>&bdquo;SQL&ldquo;</i><br>"
                "&rarr; Eine <b>Aktion</b>: <i>&bdquo;Videos&ldquo;</i>, <i>&bdquo;Lernplan&ldquo;</i><br>"
                "&rarr; Ein <b>Problem</b>: <i>&bdquo;Ich bin gestresst&ldquo;</i><br>"
                "&rarr; Einen <b>Termin</b>: <i>&bdquo;Prüfung DBS am 15.04&ldquo;</i>"
            )
            mod_names = [m["name"] for m in s["active_mods"][:2]]
            replies = [self._yt(f"{n} Tutorial Deutsch", f"🎬 Videos: {n[:18]}")
                       for n in mod_names]
            replies.append(self._nav(self.PAGE_TIMER, "⏱ Timer starten"))
            if not replies:
                replies = [
                    "📋 Lernplan erstellen",
                    self._nav(self.PAGE_TIMER, "⏱ Timer starten"),
                    self._web("https://de.wikipedia.org/wiki/Lerntechnik",
                              "📖 Wikipedia: Lerntechniken"),
                ]
            return msg, replies[:4]


class StudienChatPanel(QDialog):
    """
    Konversations-Coach mit Tab-Navigation, YouTube-Suche und Web-Ressourcen.
    Quick-Reply-Format: "ACTION|data|Label" oder reiner Text.
    """

    def __init__(self, repo: SqliteRepo, switch_page_cb=None, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._switch_page = switch_page_cb   # callable(int) → navigiert zur Seite
        self._engine = _CoachEngine(repo)
        self._messages: list[dict] = []
        # Gesprächskontext — wird laufend aktualisiert
        self._ctx: dict = {
            "last_subject":  None,  # zuletzt erwähntes Fach (z.B. "Analysis")
            "last_mod_code": None,  # zuletzt erkannter Modul-Code (z.B. "DBS")
            "last_intent":   None,  # letzter erkannter Intent
            "turn":          0,     # Gesprächsrunden-Zähler
            "pending":       None,  # laufender Multi-Turn-Flow (z.B. exam_entry)
        }
        self.setWindowTitle("💬  Studien-Coach")
        self.setMinimumSize(520, 640)
        self.resize(580, 700)
        self._build()
        self._welcome()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Coach Header ─────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setAttribute(Qt.WA_StyledBackground, True)
        hdr.setStyleSheet(
            "QFrame{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #6D28D9,stop:1 #7C3AED);"
            "border-bottom:1px solid rgba(255,255,255,0.15);"
            "}"
        )
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 12, 16, 12)
        hdr_lay.setSpacing(12)

        # Avatar
        avatar = QLabel("🤖")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "background:rgba(255,255,255,0.18);border-radius:21px;"
            "font-size:21px;"
        )
        hdr_lay.addWidget(avatar)

        # Title + status
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("Studien-Coach")
        title_lbl.setStyleSheet(
            "color:#FFFFFF;font-size:15px;font-weight:bold;background:transparent;"
        )
        title_col.addWidget(title_lbl)

        status_row = QHBoxLayout()
        status_row.setSpacing(5)
        status_row.setContentsMargins(0, 0, 0, 0)
        dot_lbl = QLabel("●")
        dot_lbl.setStyleSheet("color:#4ADE80;font-size:9px;background:transparent;")
        sub_lbl = QLabel("KI-Assistent · offline &amp; kostenlos")
        sub_lbl.setTextFormat(Qt.RichText)
        sub_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.72);font-size:11px;background:transparent;"
        )
        status_row.addWidget(dot_lbl)
        status_row.addWidget(sub_lbl)
        status_row.addStretch()
        title_col.addLayout(status_row)
        hdr_lay.addLayout(title_col, 1)

        # Action buttons
        clr_btn = QPushButton("🗑")
        clr_btn.setFixedSize(32, 32)
        clr_btn.setToolTip("Chat leeren")
        clr_btn.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.15);color:white;"
            "border:none;border-radius:16px;font-size:14px;}"
            "QPushButton:hover{background:rgba(255,255,255,0.28);}"
        )
        clr_btn.clicked.connect(self._clear_chat)
        hdr_lay.addWidget(clr_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip("Schließen")
        close_btn.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.15);color:white;"
            "border:none;border-radius:16px;font-size:13px;}"
            "QPushButton:hover{background:rgba(220,38,38,0.6);}"
        )
        close_btn.clicked.connect(self.reject)
        hdr_lay.addWidget(close_btn)
        lay.addWidget(hdr)

        # Chat area
        self._chat_sa = QScrollArea()
        self._chat_sa.setWidgetResizable(True)
        self._chat_sa.setFrameShape(QFrame.NoFrame)
        self._chat_container = QWidget()
        self._chat_container.setAttribute(Qt.WA_StyledBackground, True)
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setSpacing(10)
        self._chat_layout.setContentsMargins(12, 12, 12, 4)
        self._chat_layout.addStretch()
        self._chat_sa.setWidget(self._chat_container)
        lay.addWidget(self._chat_sa, 1)

        # ── Quick-Reply-Leiste ───────────────────────────────────────────────
        self._replies_scroll = QScrollArea()
        self._replies_scroll.setFrameShape(QFrame.NoFrame)
        self._replies_scroll.setFixedHeight(48)
        self._replies_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._replies_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._replies_scroll.setWidgetResizable(True)
        self._replies_w = QWidget()
        self._replies_w.setStyleSheet("background:transparent;")
        self._replies_lay = QHBoxLayout(self._replies_w)
        self._replies_lay.setContentsMargins(12, 6, 12, 6)
        self._replies_lay.setSpacing(8)
        self._replies_lay.addStretch()
        self._replies_scroll.setWidget(self._replies_w)
        lay.addWidget(self._replies_scroll)

        # Eingabefeld
        inp_frame = QFrame()
        inp_frame.setObjectName("Card")
        inp_lay = QHBoxLayout(inp_frame)
        inp_lay.setContentsMargins(12, 8, 12, 8)
        inp_lay.setSpacing(8)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Fach, Thema oder Frage eingeben … (Enter zum Senden)")
        self._input.returnPressed.connect(self._send)
        inp_lay.addWidget(self._input, 1)
        send_btn = QPushButton("→")
        send_btn.setObjectName("PrimaryBtn")
        send_btn.setFixedSize(36, 36)
        send_btn.clicked.connect(self._send)
        inp_lay.addWidget(send_btn)
        lay.addWidget(inp_frame)

    def _welcome(self):
        """Zeigt eine kontextabhängige Begrüßung mit hilfreichen Starter-Chips."""
        try:
            s = self._engine._situation()
        except Exception:
            s = {"n_mods": 0, "open_tasks": 0, "streak": 0,
                 "most_urgent": None, "urgent_days": None,
                 "active_mods": [], "overdue": []}

        n_mods = s.get("n_mods", 0)
        mu = s.get("most_urgent")
        urgent_days = s.get("urgent_days")
        streak = s.get("streak", 0)

        # ── Nachricht ────────────────────────────────────────────────────────
        if n_mods == 0:
            html = (
                "<b>👋 Willkommen beim Studien-Coach!</b><br><br>"
                "Ich bin dein persönlicher Lernassistent — "
                "offline, kostenlos, immer verfügbar.<br><br>"
                "<b>Was ich für dich tun kann:</b><br>"
                "🎬 &nbsp;YouTube-Videos zu jedem Fach finden<br>"
                "📋 &nbsp;Lernpläne &amp; Crashpläne erstellen<br>"
                "🌐 &nbsp;Lernwebsites &amp; Wikipedia-Links öffnen<br>"
                "📅 &nbsp;Prüfungstermine eintragen &amp; tracken<br>"
                "⏱️ &nbsp;Timer starten &amp; App navigieren<br><br>"
                "<i>Leg zuerst deine Module an – dann helfe ich gezielt.</i>"
            )
            chips = [
                self._engine._nav(self._engine.PAGE_MODULE,    "📚 Module anlegen"),
                self._engine._nav(self._engine.PAGE_STUDIENPLAN, "📊 Studienplan ansehen"),
                self._engine._yt("Lerntechniken Studium Tipps Deutsch", "🎬 Lerntipps Videos"),
                self._engine._web("https://de.wikipedia.org/wiki/Lernstrategie",
                                  "📖 Wikipedia: Lernstrategien"),
            ]

        elif mu and urgent_days is not None and urgent_days <= 5:
            mod_name = mu.get("name", "Prüfung")
            html = (
                f"<b>👋 Hallo! Ich bin dein Studien-Coach.</b><br><br>"
                f"🚨 <b>Achtung:</b> <b>{mod_name}</b> steht in "
                f"<b>{urgent_days} Tag{'en' if urgent_days != 1 else ''}</b> an!<br><br>"
                f"Soll ich dir sofort einen Crashplan erstellen?"
            )
            chips = [
                "🚨 Crashplan erstellen",
                self._engine._nav(self._engine.PAGE_WISSEN,  "🧠 Schwache Themen"),
                self._engine._nav(self._engine.PAGE_TIMER,   "⏱ Lernsession starten"),
                self._engine._yt(f"{mod_name} Prüfungsvorbereitung kompakt",
                                 f"🎬 Videos: {mod_name[:20]}"),
            ]

        else:
            streak_note = (f" · 🔥 {streak} Tage Serie" if streak > 2 else "")
            task_note   = (f" · {s['open_tasks']} Aufgaben" if s.get("open_tasks") else "")
            html = (
                f"<b>👋 Hallo! Ich bin dein Studien-Coach.</b><br><br>"
                f"<b>{n_mods} Module aktiv</b>{task_note}{streak_note}<br><br>"
                "Schreib mir, was dich beschäftigt &mdash; oder klick einen Vorschlag unten.<br><br>"
                "<span style='color:#6B7280;font-size:12px;'>"
                "Tipps: <i>&bdquo;Analysis&ldquo;</i> &middot; <i>&bdquo;Prüfung am 15.04&ldquo;</i>"
                " &middot; <i>&bdquo;Wo anfangen?&ldquo;</i> &middot; <i>&bdquo;Videos zu SQL&ldquo;</i>"
                "</span>"
            )
            chips = []
            # Dringlichstes Modul als erster Chip
            if mu and urgent_days is not None and urgent_days <= 21:
                mod_name = mu.get("name", "Modul")
                chips.append(f"📋 Lernplan: {mod_name[:22]}")
            # Aktive Module als Video-Chips
            for m in s.get("active_mods", [])[:2]:
                chips.append(
                    self._engine._yt(
                        f"{m['name']} Studium Tutorial Deutsch",
                        f"🎬 {m['name'][:22]}"
                    )
                )
            chips.append("📊 Wie stehe ich?")
            chips.append(self._engine._nav(self._engine.PAGE_TIMER, "⏱ Timer starten"))

        self._add_bot_message(html, chips[:5])

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._add_user_message(text)
        self._ctx["turn"] += 1
        # _ctx wird als Referenz übergeben; engine schreibt pending/etc. direkt rein
        msg, replies = self._engine.respond(text, ctx=self._ctx)
        # Kontext für nächste Runde aktualisieren (nur wenn kein pending-Flow läuft)
        if not self._ctx.get("pending"):
            subj = self._engine._detect_subject(text)
            if subj:
                self._ctx["last_subject"] = subj
            mod = self._engine._match_module(text)
            if mod and mod.get("code"):
                self._ctx["last_mod_code"] = mod["code"]
                self._ctx["last_subject"] = mod.get("name")
            self._ctx["last_intent"] = self._engine._intent(text)
        QTimer.singleShot(300, lambda: self._add_bot_message(msg, replies))

    def _add_user_message(self, text: str):
        bubble = QFrame()
        bubble.setStyleSheet(
            "background:#7C3AED;border-radius:14px 14px 4px 14px;padding:8px 14px;")
        bubble.setAttribute(Qt.WA_StyledBackground, True)
        bl = QHBoxLayout(bubble)
        bl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#FFFFFF;font-size:13px;background:transparent;")
        bl.addWidget(lbl)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(bubble)
        container = QWidget()
        container.setLayout(row)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, container)
        self._scroll_to_bottom()

    def _add_bot_message(self, html: str, quick_replies: list[str] = None):
        bubble = QFrame()
        bubble.setObjectName("Card")
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(8)
        lbl = QLabel(html)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.RichText)
        lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        lbl.linkActivated.connect(_open_url_safe)
        lbl.setStyleSheet("font-size:13px;line-height:1.6;")
        bl.addWidget(lbl)
        bubble.setMaximumWidth(480)

        row = QHBoxLayout()
        row.addWidget(bubble)
        row.addStretch()
        container = QWidget()
        container.setLayout(row)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, container)

        # Quick-Reply-Buttons aktualisieren
        while self._replies_lay.count() > 1:
            item = self._replies_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if quick_replies:
            for action_str in quick_replies[:5]:
                label = self._parse_label(action_str)
                btn = QPushButton(label)
                btn.setFixedHeight(32)
                btn.setStyleSheet(
                    "QPushButton{"
                    "background:#F3F0FF;color:#6D28D9;"
                    "border:1.5px solid #C4B5FD;"
                    "border-radius:16px;"
                    "font-size:12px;font-weight:600;"
                    "padding:4px 12px;"
                    "}"
                    "QPushButton:hover{"
                    "background:#EDE9FE;border-color:#7C3AED;"
                    "}"
                    "QPushButton:pressed{background:#DDD6FE;}"
                )
                btn.clicked.connect(
                    lambda checked, a=action_str: self._execute_action(a))
                self._replies_lay.insertWidget(self._replies_lay.count() - 1, btn)

        self._scroll_to_bottom()

    @staticmethod
    def _parse_label(action_str: str) -> str:
        """Extrahiert den Anzeigetext aus einem Aktions-String."""
        parts = action_str.split("|")
        if len(parts) == 3 and parts[0] in ("NAV", "YT", "WEB"):
            return parts[2]
        return action_str  # Klartext

    def _execute_action(self, action_str: str):
        """Führt eine Quick-Reply-Aktion aus."""
        parts = action_str.split("|")
        kind = parts[0] if len(parts) >= 1 else ""

        if kind == "NAV" and len(parts) == 3:
            # Zur Seite navigieren und Chat schließen
            try:
                idx = int(parts[1])
            except ValueError:
                return
            label = parts[2]
            self._add_user_message(label)
            if self._switch_page:
                QTimer.singleShot(300, lambda: (self._switch_page(idx), self.accept()))
            return

        if kind == "YT" and len(parts) == 3:
            query = _urllib_parse.unquote(parts[1])
            label = parts[2]
            self._add_user_message(label)
            url = f"https://www.youtube.com/results?search_query={_urllib_parse.quote(query)}"
            # Link im Chat anzeigen — User entscheidet selbst ob er klickt
            confirm_msg = (
                f"🎬 <b>YouTube-Suche:</b> {query}<br><br>"
                f'<a href="{url}">▶ Auf YouTube öffnen</a><br><br>'
                f"<span style='font-size:11px;color:#6B7280;'>"
                f"Klick auf den Link — öffnet in deinem Browser.</span>"
            )
            # Kontext aktualisieren
            subj = self._engine._detect_subject(query)
            if subj:
                self._ctx["last_subject"] = subj
            self._ctx["last_intent"] = "youtube"
            self._ctx["turn"] += 1
            # Smarte Follow-ups basierend auf Kontext
            subject = self._ctx.get("last_subject")
            followups: list[str] = []
            if subject:
                resources = self._engine.RESOURCES.get(subject, [])
                if resources:
                    _lbl, _url = resources[0]
                    followups.append(self._engine._web(_url, _lbl[:35]))
            followups.append(self._engine._yt(query + " Zusammenfassung", "▶ Kompaktere Erklärung"))
            followups.append("🌐 Weitere Ressourcen")
            QTimer.singleShot(300, lambda: self._add_bot_message(confirm_msg, followups[:3]))
            return

        if kind == "WEB" and len(parts) >= 3:
            # URL kann Pipe-Zeichen enthalten → alles zwischen erstem und letztem "|" ist URL
            url = "|".join(parts[1:-1])
            label = parts[-1]
            self._add_user_message(label)
            # Anzeigenamen bereinigen
            display = label
            for pfx in ("🌐 ", "📐 ", "🔍 ", "🤖 ", "💻 ", "🗄 ", "📊 ", "🔢 ", "⚙ "):
                display = display.replace(pfx, "")
            display = display.strip()
            # Link im Chat anzeigen
            confirm_msg = (
                f"🌐 <b>{display}</b><br><br>"
                f'<a href="{url}">{url[:65]}{"…" if len(url) > 65 else ""}</a><br><br>'
                f"<span style='font-size:11px;color:#6B7280;'>"
                f"Klick auf den Link — öffnet in deinem Browser.</span>"
            )
            # Kontext & Follow-ups
            self._ctx["last_intent"] = "resource"
            self._ctx["turn"] += 1
            subject = self._ctx.get("last_subject")
            followups: list[str] = []
            if subject:
                followups.append(self._engine._yt(
                    f"{subject} Studium Erklärung", f"🎬 YouTube: {subject[:20]}"))
                resources = self._engine.RESOURCES.get(subject, [])
                if len(resources) > 1:
                    _lbl2, _url2 = resources[1]
                    followups.append(self._engine._web(_url2, _lbl2[:35]))
            followups.append("📋 Lernplan dazu erstellen")
            QTimer.singleShot(300, lambda: self._add_bot_message(confirm_msg, followups[:3]))
            return

        # Kein spezielles Format → als normaler Text senden
        self._add_user_message(action_str)
        self._ctx["turn"] += 1
        msg, replies = self._engine.respond(action_str, ctx=self._ctx)
        subj = self._engine._detect_subject(action_str)
        if subj:
            self._ctx["last_subject"] = subj
        mod = self._engine._match_module(action_str)
        if mod and mod.get("code"):
            self._ctx["last_mod_code"] = mod["code"]
            self._ctx["last_subject"] = mod.get("name")
        self._ctx["last_intent"] = self._engine._intent(action_str)
        QTimer.singleShot(300, lambda: self._add_bot_message(msg, replies))

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._chat_sa.verticalScrollBar().setValue(
            self._chat_sa.verticalScrollBar().maximum()
        ))

    def _clear_chat(self):
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._welcome()


# ── Onboarding Wizard ──────────────────────────────────────────────────────

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
        db_path = pathlib.Path(__file__).parent / "fh_database.json"
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
                db_path = _pl.Path(__file__).parent / "fh_database.json"
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


# ── Notfall-Modus ──────────────────────────────────────────────────────────

class NotfallModusDialog(QDialog):
    """
    Crashplan-Modus wenn eine Prüfung in <7 Tagen ist.
    Zeigt: verfügbare Zeit, schwache Themen, Stundenplan für verbleibende Tage.
    """

    def __init__(self, repo: SqliteRepo, module_id: int = None, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._module_id = module_id
        self.setWindowTitle("🚨  Notfall-Crashplan")
        self.resize(640, 560)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel("🚨  Crashplan")
        title.setObjectName("PageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        mod_lbl = QLabel("Modul:")
        hdr.addWidget(mod_lbl)
        self.mod_cb = QComboBox()
        self.mod_cb.setMinimumWidth(200)
        exams = self._repo.upcoming_exams(within_days=30)
        if not exams:
            exams = self._repo.all_exams()
        for m in exams:
            self.mod_cb.addItem(m["name"], m["id"])
        if self._module_id:
            for i in range(self.mod_cb.count()):
                if self.mod_cb.itemData(i) == self._module_id:
                    self.mod_cb.setCurrentIndex(i)
                    break
        self.mod_cb.currentIndexChanged.connect(self._refresh_plan)
        hdr.addWidget(self.mod_cb)
        lay.addLayout(hdr)

        self.plan_sa = QScrollArea()
        self.plan_sa.setWidgetResizable(True)
        self.plan_sa.setFrameShape(QFrame.NoFrame)
        self.plan_w = QWidget()
        self.plan_lay = QVBoxLayout(self.plan_w)
        self.plan_lay.setSpacing(8)
        self.plan_sa.setWidget(self.plan_w)
        lay.addWidget(self.plan_sa, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._refresh_plan()

    def _refresh_plan(self):
        while self.plan_lay.count():
            item = self.plan_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        mid = self.mod_cb.currentData()
        if not mid:
            return
        mod = self._repo.get_module(mid)
        if not mod:
            return

        exam_d = days_until(mod["exam_date"]) if mod["exam_date"] else None
        topics = self._repo.list_topics(mid)
        color = mod_color(mid)

        # ── Summary card ────────────────────────────────────────────────────
        summary = QFrame()
        summary.setObjectName("QuoteCard")
        summary.setAttribute(Qt.WA_StyledBackground, True)
        sl = QVBoxLayout(summary)
        sl.setContentsMargins(16, 12, 16, 12)
        sl.setSpacing(6)

        if exam_d is None:
            title_txt = f"📅 Kein Prüfungsdatum für {mod['name']} gesetzt"
        elif exam_d == 0:
            title_txt = f"🔴 Prüfung HEUTE: {mod['name']}"
        elif exam_d < 0:
            title_txt = f"✅ Prüfung für {mod['name']} ist vorbei"
        else:
            title_txt = f"⏳ Prüfung {mod['name']} in {exam_d} Tag{'en' if exam_d != 1 else ''}"

        tl = QLabel(title_txt)
        tl.setStyleSheet(f"font-size:15px;font-weight:bold;color:{color};background:transparent;")
        sl.addWidget(tl)

        studied_h = self._repo.seconds_studied_for_module(mid) / 3600
        target_h = self._repo.ects_target_hours(mid)
        remaining_h = max(0, target_h - studied_h)
        available_h = (exam_d or 1) * 5  # assume 5h/day available

        info_txt = (f"Schon gelernt: {studied_h:.1f}h / {target_h:.0f}h Ziel  ·  "
                    f"Noch verfügbar: ~{available_h:.0f}h ({exam_d or 0} Tage × 5h)")
        il = QLabel(info_txt)
        il.setStyleSheet("font-size:12px;color:#6B7280;background:transparent;")
        sl.addWidget(il)
        self.plan_lay.addWidget(summary)

        # ── Topics sorted by weakness ────────────────────────────────────────
        if topics:
            topics_hdr = QLabel("📋  Themen nach Priorität")
            topics_hdr.setObjectName("SectionTitle")
            self.plan_lay.addWidget(topics_hdr)

            # Sort: unknown/weak first
            sorted_topics = sorted(topics, key=lambda t: int(t["knowledge_level"]) if t["knowledge_level"] else 0)

            for t in sorted_topics:
                lvl = int(t["knowledge_level"]) if t["knowledge_level"] else 0
                icons = {0: "🔴", 1: "🔴", 2: "🟠", 3: "🟡", 4: "✅"}
                labels = {0: "Unbekannt", 1: "Grundlagen", 2: "Vertraut", 3: "Gut", 4: "Experte"}
                tf = QFrame()
                tf.setObjectName("Card")
                tfl = QHBoxLayout(tf)
                tfl.setContentsMargins(12, 8, 12, 8)
                tfl.setSpacing(10)
                icon_lbl = QLabel(icons[lvl])
                icon_lbl.setStyleSheet("font-size:16px;")
                tfl.addWidget(icon_lbl)
                name_lbl = QLabel(f"<b>{t['title']}</b>")
                name_lbl.setTextFormat(Qt.RichText)
                tfl.addWidget(name_lbl, 1)
                lvl_lbl = QLabel(labels[lvl])
                lvl_lbl.setStyleSheet(
                    f"font-size:11px;color:{'#DC2626' if lvl <= 1 else '#D97706' if lvl == 2 else '#6B7280'};"
                )
                tfl.addWidget(lvl_lbl)
                self.plan_lay.addWidget(tf)
        else:
            no_topics = QLabel("⚠ Noch keine Lernthemen für dieses Modul. Füge sie auf der Wissensseite hinzu.")
            no_topics.setStyleSheet("color:#D97706;font-size:13px;padding:8px;")
            no_topics.setWordWrap(True)
            self.plan_lay.addWidget(no_topics)

        # ── Day-by-day plan ──────────────────────────────────────────────────
        if exam_d and exam_d > 0 and topics:
            plan_hdr = QLabel("📅  Tagesplan bis zur Prüfung")
            plan_hdr.setObjectName("SectionTitle")
            self.plan_lay.addWidget(plan_hdr)

            weak_topics = [t for t in sorted_topics if (int(t["knowledge_level"]) if t["knowledge_level"] else 0) < 4]
            topics_per_day = max(1, len(weak_topics) // max(1, exam_d))
            topic_idx = 0
            for day in range(min(exam_d, 7)):
                day_date = date.today() + timedelta(days=day)
                day_name = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][day_date.weekday()]
                day_topics = weak_topics[topic_idx:topic_idx + topics_per_day]
                topic_idx += topics_per_day

                df = QFrame()
                df.setObjectName("Card")
                dfl = QVBoxLayout(df)
                dfl.setContentsMargins(12, 8, 12, 8)
                dfl.setSpacing(4)
                day_hdr_lbl = QLabel(
                    f"<b>{day_name}, {day_date.strftime('%d.%m.')}</b>"
                    + (" — <span style='color:#DC2626'>Prüfungstag!</span>" if day == exam_d - 1 else "")
                )
                day_hdr_lbl.setTextFormat(Qt.RichText)
                dfl.addWidget(day_hdr_lbl)
                if day == exam_d - 1:
                    dfl.addWidget(QLabel("  🔁 Alles wiederholen + ausschlafen!"))
                elif day_topics:
                    for dt in day_topics:
                        lvl = int(dt["knowledge_level"]) if dt["knowledge_level"] else 0
                        dfl.addWidget(QLabel(f"  {'🔴' if lvl <= 1 else '🟠'} {dt['title']}"))
                else:
                    dfl.addWidget(QLabel("  📖 Freie Wiederholung / Nachfragen klären"))
                self.plan_lay.addWidget(df)

        self.plan_lay.addStretch()


# ── Stundenplan ──────────────────────────────────────────────────────────


class StundenplanEntryDialog(QDialog):
    """Dialog zum Hinzufügen oder Bearbeiten eines Stundenplan-Eintrags."""

    DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
            "Freitag", "Samstag", "Sonntag"]
    COLORS = [
        ("#7C3AED", "Lila"),
        ("#2563EB", "Blau"),
        ("#059669", "Grün"),
        ("#D97706", "Orange"),
        ("#DC2626", "Rot"),
        ("#0891B2", "Cyan"),
        ("#BE185D", "Pink"),
        ("#65A30D", "Limette"),
        ("#374151", "Grau"),
    ]

    def __init__(self, repo: SqliteRepo, entry: dict = None,
                 day: int = None, hour: int = None, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._entry = entry
        self._color = (entry or {}).get("color", self.COLORS[0][0])
        self.setWindowTitle("Eintrag bearbeiten" if entry else "Neuer Eintrag")
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build(day, hour)

    def _build(self, default_day: int = None, default_hour: int = None):
        e = self._entry or {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        title_lbl = QLabel("✏️  " + ("Eintrag bearbeiten" if self._entry else "Neuer Eintrag"))
        title_lbl.setObjectName("SectionTitle")
        lay.addWidget(title_lbl)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        # Subject
        self._subj = QLineEdit(e.get("subject", ""))
        self._subj.setPlaceholderText("Modulname oder Kursbezeichnung")
        form.addRow("Fach / Modul:", self._subj)

        # Day dropdown
        self._day_cb = QComboBox()
        for d in self.DAYS:
            self._day_cb.addItem(d)
        day_val = e.get("day_of_week", default_day)
        if day_val is not None:
            self._day_cb.setCurrentIndex(int(day_val))
        form.addRow("Tag:", self._day_cb)

        # Time from – to
        times = [f"{h:02d}:{m:02d}" for h in range(6, 23) for m in (0, 15, 30, 45)]
        time_row = QHBoxLayout()
        self._from_cb = QComboBox()
        self._to_cb = QComboBox()
        for t in times:
            self._from_cb.addItem(t)
            self._to_cb.addItem(t)
        dh = default_hour or 8
        default_from = e.get("time_from", f"{dh:02d}:00")
        default_to   = e.get("time_to",   f"{min(dh + 2, 22):02d}:00")
        self._from_cb.setCurrentIndex(times.index(default_from) if default_from in times else 0)
        self._to_cb.setCurrentIndex(times.index(default_to) if default_to in times else
                                    min(8, len(times) - 1))
        dash = QLabel("–")
        dash.setAlignment(Qt.AlignCenter)
        time_row.addWidget(self._from_cb, 1)
        time_row.addWidget(dash)
        time_row.addWidget(self._to_cb, 1)
        form.addRow("Zeit:", time_row)

        # Room
        self._room = QLineEdit(e.get("room", ""))
        self._room.setPlaceholderText("z.B. Raum B101 (optional)")
        form.addRow("Raum:", self._room)

        # Lecturer
        self._lec = QLineEdit(e.get("lecturer", ""))
        self._lec.setPlaceholderText("optional")
        form.addRow("Dozent:", self._lec)

        # Notes
        self._notes = QLineEdit(e.get("notes", ""))
        self._notes.setPlaceholderText("optional")
        form.addRow("Notizen:", self._notes)

        lay.addLayout(form)

        # Color chooser
        lay.addWidget(QLabel("Farbe:"))
        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        self._color_btns: list = []
        for hex_c, name in self.COLORS:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setToolTip(name)
            checked = (hex_c == self._color)
            btn.setStyleSheet(
                f"QPushButton{{background:{hex_c};border-radius:14px;"
                f"border:{'3px solid #111' if checked else '2px solid transparent'};}}"
                f"QPushButton:hover{{border:2px solid #555;}}"
            )
            btn.clicked.connect(lambda _, h=hex_c: self._pick_color(h))
            color_row.addWidget(btn)
            self._color_btns.append((hex_c, btn))
        color_row.addStretch()
        lay.addLayout(color_row)

        # Action buttons
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#E5E7EB;")
        lay.addWidget(sep)

        btns = QHBoxLayout()
        if self._entry:
            del_btn = QPushButton("🗑  Löschen")
            del_btn.setStyleSheet(
                "QPushButton{background:#FEF2F2;color:#DC2626;border:1.5px solid #FECACA;"
                "border-radius:8px;padding:6px 14px;font-weight:600;}"
                "QPushButton:hover{background:#FEE2E2;}"
            )
            del_btn.clicked.connect(self._delete)
            btns.addWidget(del_btn)
        btns.addStretch()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Speichern")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.clicked.connect(self._save)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        lay.addLayout(btns)

    def _pick_color(self, hex_color: str):
        self._color = hex_color
        for h, btn in self._color_btns:
            checked = (h == hex_color)
            btn.setStyleSheet(
                f"QPushButton{{background:{h};border-radius:14px;"
                f"border:{'3px solid #111' if checked else '2px solid transparent'};}}"
                f"QPushButton:hover{{border:2px solid #555;}}"
            )

    def _save(self):
        subject = self._subj.text().strip()
        if not subject:
            self._subj.setFocus()
            self._subj.setStyleSheet("border:1.5px solid #DC2626;border-radius:8px;")
            return
        data = {
            "subject":     subject,
            "day_of_week": self._day_cb.currentIndex(),
            "time_from":   self._from_cb.currentText(),
            "time_to":     self._to_cb.currentText(),
            "room":        self._room.text().strip(),
            "lecturer":    self._lec.text().strip(),
            "color":       self._color,
            "notes":       self._notes.text().strip(),
        }
        if self._entry:
            self._repo.update_stundenplan_entry(self._entry["id"], **data)
        else:
            self._repo.add_stundenplan_entry(data)
        self.accept()

    def _delete(self):
        if self._entry:
            self._repo.delete_stundenplan_entry(self._entry["id"])
            self.accept()


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
        dlg = StundenplanEntryDialog(
            self._repo, day=day, hour=hour, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._rebuild_grid()

    def _edit_entry(self, entry: dict):
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


# ── Sidebar ───────────────────────────────────────────────────────────────

# ── Sidebar Dock Title Bar ─────────────────────────────────────────────────
class SidebarDockTitleBar(QWidget):
    """
    Custom title bar for the dockable sidebar.
    Acts as the drag handle for QDockWidget and hosts the pin toggle button.
    """
    pin_toggled = Signal(bool)   # True = pinned (expanded stays)

    def __init__(self, sidebar: "SidebarWidget", parent=None):
        super().__init__(parent)
        self._sidebar = sidebar
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(30)
        self.setStyleSheet(
            "SidebarDockTitleBar{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6D28D9,stop:1 #7C3AED);"
            "border-bottom:1px solid rgba(255,255,255,0.12);"
            "}"
        )
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 3, 8, 3)
        lay.setSpacing(6)

        # Drag-grip indicator
        grip = QLabel("\u22EE\u22EE")   # ⋮⋮
        grip.setStyleSheet("color:rgba(255,255,255,0.45);font-size:13px;letter-spacing:2px;")
        lay.addWidget(grip)

        # App title
        name = QLabel("Semetra")
        name.setStyleSheet("color:white;font-weight:700;font-size:11px;letter-spacing:0.5px;")
        lay.addWidget(name)
        lay.addStretch()

        # Pin / unpin button
        self._pin_btn = QToolButton()
        self._pin_btn.setCheckable(True)
        self._pin_btn.setChecked(True)
        self._pin_btn.setFixedSize(22, 22)
        self._pin_btn.setText("📌")
        self._pin_btn.setToolTip("Sidebar fixieren / ablösen\n"
                                  "Fixiert: Sidebar bleibt geöffnet\n"
                                  "Gelöst: automatisch ein-/ausklappen und verschiebbar")
        self._pin_btn.setStyleSheet(
            "QToolButton{background:transparent;border:none;"
            "font-size:13px;border-radius:4px;}"
            "QToolButton:hover{background:rgba(255,255,255,0.18);}"
            "QToolButton:checked{background:rgba(255,255,255,0.12);opacity:1;}"
            "QToolButton:!checked{opacity:0.55;}"
        )
        self._pin_btn.toggled.connect(self._on_pin_toggled)
        lay.addWidget(self._pin_btn)

    def _on_pin_toggled(self, checked: bool):
        self._sidebar.set_pinned(checked)
        self.pin_toggled.emit(checked)


# ── Sidebar ────────────────────────────────────────────────────────────────
class SidebarWidget(QWidget):
    page_selected = Signal(int)
    coach_clicked = Signal()

    # (emoji, translation_key) — flat list, index = page stack index
    # All emojis have U+FE0F selector for consistent rendering
    NAV_ITEMS = [
        ("🏠\uFE0F", "nav.dashboard"),      # 0
        ("📚\uFE0F", "nav.modules"),        # 1
        ("✅\uFE0F", "nav.tasks"),          # 2
        ("📅\uFE0F", "nav.calendar"),       # 3
        ("🗓\uFE0F", "nav.stundenplan"),    # 4  ← NEW
        ("📊\uFE0F", "nav.timeline"),       # 5
        ("🧠\uFE0F", "nav.knowledge"),      # 6
        ("⏱\uFE0F",  "nav.timer"),         # 7
        ("🎯\uFE0F", "nav.exams"),          # 8
        ("📈\uFE0F", "nav.grades"),         # 9
        ("⚙\uFE0F",  "nav.settings"),      # 10
        ("ℹ\uFE0F",  "nav.credits"),       # 11
    ]

    # Visual groupings: (section_label, [page_indices])
    # Empty label = no section header shown
    _NAV_GROUPS = [
        ("",         [0, 1, 2]),
        ("PLANUNG",  [3, 4, 5]),
        ("WISSEN",   [6, 7, 8]),
        ("ANALYSE",  [9]),
    ]
    _BOTTOM_PAGES = [10, 11]

    EXPANDED_W  = 240   # px — full width
    COLLAPSED_W = 56    # px — icon-only width

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        # CRITICAL: needed on Linux for background-color to render
        self.setAttribute(Qt.WA_StyledBackground, True)
        # Pre-allocate list so _buttons[page_idx] always works
        self._buttons: List[Optional[QPushButton]] = [None] * len(self.NAV_ITEMS)
        self._section_labels: List[QLabel] = []
        self._btn_icons: Dict[int, str] = {}

        # Collapse/expand state
        self._pinned   = True   # pinned = always expanded
        self._expanded = True

        # Delayed collapse timer (avoids flicker when mouse briefly leaves)
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.setInterval(420)
        self._collapse_timer.timeout.connect(self._do_collapse)
        self._anim: Optional[QPropertyAnimation] = None

        self.setFixedWidth(self.EXPANDED_W)
        self._build()

    # ── Animatable width property ────────────────────────────────────────
    def _get_anim_width(self) -> int:
        return self.width()

    def _set_anim_width(self, v: int) -> None:
        self.setFixedWidth(v)

    anim_width = Property(int, _get_anim_width, _set_anim_width)

    # ── Build ────────────────────────────────────────────────────────────
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 18, 12, 14)
        lay.setSpacing(0)

        # ── App Identity ────────────────────────────────────────────────
        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(4, 0, 4, 0)
        logo_row.setSpacing(8)
        self._logo_lbl = QLabel("📖\uFE0F")
        self._logo_lbl.setStyleSheet("font-size: 18px;")
        self._logo_lbl.setFixedWidth(26)
        logo_row.addWidget(self._logo_lbl)

        # Wrap app identity text in a widget so we can show/hide it together
        self._id_col_widget = QWidget()
        self._id_col_widget.setAttribute(Qt.WA_StyledBackground, False)
        id_col = QVBoxLayout(self._id_col_widget)
        id_col.setContentsMargins(0, 0, 0, 0)
        id_col.setSpacing(1)
        title = QLabel("Semetra")
        title.setObjectName("AppTitle")
        ver = QLabel("v2.0  ·  FH Edition")
        ver.setObjectName("AppVersion")
        id_col.addWidget(title)
        id_col.addWidget(ver)
        self._plan_badge = QLabel("Free Plan")
        self._plan_badge.setObjectName("PlanBadge")
        self._plan_badge.setStyleSheet(
            "background:#F3F4F6;color:#6B7280;border-radius:8px;"
            "padding:1px 8px;font-size:10px;font-weight:bold;"
        )
        id_col.addWidget(self._plan_badge)
        logo_row.addWidget(self._id_col_widget)
        logo_row.addStretch()
        lay.addLayout(logo_row)

        lay.addSpacing(14)

        # ── Quick Add Button ─────────────────────────────────────────────
        self._qa_btn = QPushButton("  ＋  Schnell hinzufügen")
        self._qa_btn.setObjectName("QuickAddBtn")
        self._qa_btn.setFixedHeight(40)
        self._qa_btn.setCursor(Qt.PointingHandCursor)
        self._qa_btn.setToolTip("Ctrl+N — Aufgabe oder Thema schnell erfassen")
        self._qa_btn.clicked.connect(self._on_quick_add)
        lay.addWidget(self._qa_btn)

        lay.addSpacing(14)

        # ── Grouped Navigation ──────────────────────────────────────────
        for section_label, page_indices in self._NAV_GROUPS:
            if section_label:
                lay.addSpacing(6)
                sec_lbl = QLabel(section_label)
                sec_lbl.setObjectName("NavSectionLabel")
                self._section_labels.append(sec_lbl)
                lay.addWidget(sec_lbl)
                lay.addSpacing(2)
            for page_idx in page_indices:
                icon, key = self.NAV_ITEMS[page_idx]
                self._btn_icons[page_idx] = icon
                btn = QPushButton(f"  {icon}  {tr(key)}")
                btn.setObjectName("NavBtn")
                btn.setFixedHeight(42)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda checked, i=page_idx: self._select(i))
                self._buttons[page_idx] = btn
                lay.addWidget(btn)

        lay.addStretch()

        # ── Bottom: Settings + Credits ──────────────────────────────────
        bot_sep = QFrame()
        bot_sep.setFrameShape(QFrame.HLine)
        bot_sep.setStyleSheet(_tc("color: #EAE8F2;", "color: #1E1B2C;"))
        lay.addWidget(bot_sep)
        lay.addSpacing(4)

        for page_idx in self._BOTTOM_PAGES:
            icon, key = self.NAV_ITEMS[page_idx]
            self._btn_icons[page_idx] = icon
            btn = QPushButton(f"  {icon}  {tr(key)}")
            btn.setObjectName("NavBtn")
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=page_idx: self._select(i))
            self._buttons[page_idx] = btn
            lay.addWidget(btn)

        lay.addSpacing(8)

        # ── Coach Button ─────────────────────────────────────────────────
        self._coach_btn = QPushButton("  💬\uFE0F  Studien-Coach  ⭐ Pro")
        self._coach_btn.setObjectName("CoachBtn")
        self._coach_btn.setFixedHeight(42)
        self._coach_btn.setCursor(Qt.PointingHandCursor)
        self._coach_btn.setToolTip("Ctrl+H — KI-Coach öffnen (Semetra Pro)")
        self._coach_btn.clicked.connect(self.coach_clicked.emit)
        lay.addWidget(self._coach_btn)

        self._highlight(0)

    # ── Collapse / Expand ────────────────────────────────────────────────
    def set_pinned(self, pinned: bool):
        """
        Toggle pin state.
        Pinned  = sidebar always stays expanded (current position fixed).
        Unpinned= sidebar collapses when mouse leaves; can be moved via dock.
        """
        self._pinned = pinned
        if pinned and not self._expanded:
            self._do_expand()
        elif not pinned:
            # Start collapsed when first unpinned
            if self._expanded:
                self._collapse_timer.start()

    def enterEvent(self, event):
        """Hover over sidebar — cancel any pending collapse; expand if collapsed."""
        if not self._pinned:
            self._collapse_timer.stop()
            if not self._expanded:
                self._do_expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse left sidebar — schedule collapse when unpinned."""
        if not self._pinned and self._expanded:
            self._collapse_timer.start()
        super().leaveEvent(event)

    def _do_expand(self):
        if self._expanded:
            return
        self._expanded = True
        self._set_labels_visible(True)
        self._animate_width(self.EXPANDED_W)

    def _do_collapse(self):
        if not self._expanded:
            return
        self._expanded = False
        self._set_labels_visible(False)
        self._animate_width(self.COLLAPSED_W)

    def _animate_width(self, target: int):
        if self._anim is not None:
            self._anim.stop()
        self._anim = QPropertyAnimation(self, b"anim_width", self)
        self._anim.setDuration(210)
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._anim.start()

    def _set_labels_visible(self, visible: bool):
        """Switch between full (expanded) and icon-only (collapsed) display."""
        # App identity text block
        self._id_col_widget.setVisible(visible)
        # Section header labels
        for lbl in self._section_labels:
            lbl.setVisible(visible)
        # Nav + bottom buttons
        for page_idx, btn in enumerate(self._buttons):
            if btn is None:
                continue
            icon = self._btn_icons.get(page_idx, "")
            if visible:
                _, key = self.NAV_ITEMS[page_idx]
                btn.setText(f"  {icon}  {tr(key)}")
                btn.setToolTip("")
            else:
                btn.setText(f"  {icon}")
                _, key = self.NAV_ITEMS[page_idx]
                btn.setToolTip(tr(key))
        # Quick-Add button
        if visible:
            self._qa_btn.setText("  ＋  Schnell hinzufügen")
            self._qa_btn.setToolTip("Ctrl+N — Aufgabe oder Thema schnell erfassen")
        else:
            self._qa_btn.setText("  ＋")
            self._qa_btn.setToolTip("Schnell hinzufügen (Ctrl+N)")
        # Coach button — save/restore full text
        if not visible:
            self._coach_btn.setProperty("_full_text", self._coach_btn.text())
            self._coach_btn.setText("  💬\uFE0F")
            self._coach_btn.setToolTip("KI-Studien-Coach öffnen (Ctrl+H)")
        else:
            saved = self._coach_btn.property("_full_text")
            if saved:
                self._coach_btn.setText(saved)
            self._coach_btn.setToolTip("")

    # ── Internal helpers ─────────────────────────────────────────────────
    def _on_quick_add(self):
        """Delegate to main window's _quick_add if available."""
        win = self.window()
        if hasattr(win, "_quick_add"):
            win._quick_add()

    def _select(self, idx: int):
        self._highlight(idx)
        self.page_selected.emit(idx)

    def _highlight(self, idx: int):
        for i, btn in enumerate(self._buttons):
            if btn is None:
                continue
            active = "true" if i == idx else "false"
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def select(self, idx: int):
        self._highlight(idx)


# ── Sidebar Dock ──────────────────────────────────────────────────────────

class SidebarDock(QDockWidget):
    """
    QDockWidget subclass that:
    - Forwards hover events to the inner SidebarWidget (fixes expand-on-hover when docked)
    - Prevents free floating (only snaps to left/right edges like Windows taskbar)
    """

    def enterEvent(self, event):
        sidebar = self.widget()
        if isinstance(sidebar, SidebarWidget) and not sidebar._pinned:
            sidebar._collapse_timer.stop()
            if not sidebar._expanded:
                sidebar._do_expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        sidebar = self.widget()
        if isinstance(sidebar, SidebarWidget) and not sidebar._pinned and sidebar._expanded:
            sidebar._collapse_timer.start()
        super().leaveEvent(event)


# ── Main Window ───────────────────────────────────────────────────────────

class SemetraWindow(QMainWindow):

    def __init__(self, repo: SqliteRepo):
        super().__init__()
        self.repo = repo
        self.setWindowTitle("Semetra")
        self.setMinimumSize(620, 480)
        self.resize(1280, 860)
        # Restore saved accent before building so get_qss() uses the right palette
        _saved_accent = repo.get_setting("accent_preset") or "violet"
        set_accent(_saved_accent)
        self._build()
        self._apply_theme(repo.get_setting("theme") or "light")
        # Patch every inline setStyleSheet() that hardcodes violet hex values
        # (needed when the saved accent is not violet, since _build() always
        #  uses the hard-coded violet defaults in the Python source)
        _violet = ACCENT_PRESETS["violet"]
        _chosen = ACCENT_PRESETS.get(_saved_accent, _violet)
        restyle_widgets_accent(self, _violet, _chosen)
        self._switch_page(0)
        self._setup_snap_shortcuts()
        self._setup_coach_shortcut()
        self._update_plan_badge()
        # Show onboarding wizard on first launch (no modules yet)
        if not self.repo.list_modules("all"):
            QTimer.singleShot(200, self._show_onboarding)
        # Check for updates silently in background (5 s delay so UI loads first)
        QTimer.singleShot(5000, self._check_for_update)

    def _setup_snap_shortcuts(self):
        """
        Keyboard snap shortcuts — reliable alternative to drag-to-edge on WSLg/Wayland.
        Wayland gives the compositor full control over window positioning during drags,
        so moveEvent never fires mid-drag and drag-to-edge cannot be intercepted in Qt.

        Shortcuts:
          Super+Left  / Ctrl+Super+Left  → snap to left half
          Super+Right / Ctrl+Super+Right → snap to right half
          Super+Up                       → maximise
          Super+Down                     → restore
        """
        from PySide6.QtGui import QShortcut, QKeySequence
        snap_map = {
            "Meta+Left":        lambda: self._snap("left"),
            "Ctrl+Meta+Left":   lambda: self._snap("left"),
            "Meta+Right":       lambda: self._snap("right"),
            "Ctrl+Meta+Right":  lambda: self._snap("right"),
            "Meta+Up":          self.showMaximized,
            "Meta+Down":        self.showNormal,
        }
        for key, slot in snap_map.items():
            QShortcut(QKeySequence(key), self).activated.connect(slot)
        # ── Global Quick-Add: Ctrl+N ────────────────────────────────────────
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._quick_add)

    def _quick_add(self):
        """Globaler Schnelleintrag (Ctrl+N) — Task oder Thema ohne Seitenwechsel."""
        dlg = QuickAddDialog(self.repo, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_all()

    def _setup_coach_shortcut(self):
        """Ctrl+H öffnet den Studien-Coach von überall."""
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(self._open_coach_chat)
        self.sidebar.coach_clicked.connect(self._open_coach_chat)

    def _open_coach_chat(self):
        """Öffnet den Studien-Coach als nicht-modales Fenster (Pro only)."""
        from semetra.infra.license import LicenseManager
        lm = LicenseManager(self.repo)
        if not lm.is_pro():
            if ProFeatureDialog("KI-Studien-Coach", self.repo, parent=self).exec() != QDialog.Accepted:
                return
        dlg = StudienChatPanel(self.repo, switch_page_cb=self._switch_page, parent=self)
        dlg.exec()

    def _on_sidebar_pin_toggled(self, pinned: bool):
        """
        Called when the pin button in the sidebar title bar is toggled.
        Pinned  → sidebar is fixed in place, stays expanded, dock cannot be moved.
        Unpinned→ sidebar auto-collapses on mouse leave, can be dragged to any edge.
        """
        if pinned:
            self._sidebar_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
            # Ensure expanded when re-pinned
            if not self.sidebar._expanded:
                self.sidebar._do_expand()
        else:
            # Movable between left/right edges only — no free floating
            self._sidebar_dock.setFeatures(QDockWidget.DockWidgetMovable)
            # Immediately collapse when first unpinned
            self.sidebar._do_collapse()

    def _show_onboarding(self):
        """Zeigt den Onboarding-Wizard beim ersten Start (keine Module vorhanden)."""
        wizard = OnboardingWizard(self.repo, parent=self)
        wizard.finished_setup.connect(self._on_onboarding_done)
        wizard.exec()

    def _on_onboarding_done(self):
        """Nach dem Onboarding alles auffrischen und Dashboard zeigen."""
        self._refresh_all()
        self._switch_page(0)

    def _check_for_update(self):
        """Lädt latest_version.json von semetra.app und zeigt Banner bei neuer Version."""
        try:
            import urllib.request as _ur, json as _json
            from semetra import __version__
            url = "https://semetra.app/latest_version.json"
            req = _ur.Request(url, headers={"User-Agent": f"Semetra/{__version__}"})
            with _ur.urlopen(req, timeout=4) as resp:
                data = _json.loads(resp.read().decode())
            latest = data.get("version", "")
            if not latest:
                return
            # Compare versions: split on "." and compare tuple of ints
            def _v(s):
                try:
                    return tuple(int(x) for x in s.split("."))
                except Exception:
                    return (0,)
            if _v(latest) > _v(__version__):
                download_url = data.get("download_url", "https://semetra.app")
                self._show_update_banner(latest, download_url)
        except Exception:
            pass  # Silently ignore — no network, firewall, or server issues

    def _show_update_banner(self, latest_version: str, download_url: str):
        """Zeigt einen nicht-blockierenden Update-Banner oben im Fenster."""
        banner = QWidget(self)
        banner.setStyleSheet(
            "background:#7C3AED;color:white;border-radius:0px;"
        )
        banner.setAttribute(Qt.WA_StyledBackground, True)
        b_lay = QHBoxLayout(banner)
        b_lay.setContentsMargins(16, 6, 16, 6)
        lbl = QLabel(f"🚀 Semetra {latest_version} ist verfügbar!")
        lbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        b_lay.addWidget(lbl)
        b_lay.addStretch()
        dl_btn = QPushButton("Jetzt herunterladen")
        dl_btn.setStyleSheet(
            "QPushButton{background:white;color:#7C3AED;border:none;"
            "border-radius:6px;padding:4px 14px;font-weight:bold;}"
            "QPushButton:hover{background:#EDE9FE;}"
        )
        import webbrowser as _wb
        dl_btn.clicked.connect(lambda: _wb.open(download_url))
        b_lay.addWidget(dl_btn)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton{background:transparent;color:white;border:none;"
            "font-size:14px;font-weight:bold;}"
        )
        close_btn.clicked.connect(banner.deleteLater)
        b_lay.addWidget(close_btn)
        # Position at the top of the central widget
        central = self.centralWidget()
        banner.setFixedWidth(central.width())
        banner.move(0, 0)
        banner.resize(central.width(), 40)
        banner.show()
        banner.raise_()
        # Resize banner when window resizes
        central.installEventFilter(self)
        self._update_banner = banner

    def eventFilter(self, obj, event):
        """Resize update banner when central widget is resized."""
        if hasattr(self, "_update_banner") and self._update_banner and not self._update_banner.isHidden():
            from PySide6.QtCore import QEvent as _QE
            if event.type() == _QE.Resize:
                self._update_banner.setFixedWidth(obj.width())
        return super().eventFilter(obj, event)

    def _snap(self, side: str):
        """Resize and position the window to fill the left or right screen half."""
        screen = self.screen()
        if not screen:
            return
        sg = screen.availableGeometry()
        half_w = sg.width() // 2
        if side == "left":
            self.setGeometry(sg.x(), sg.y(), half_w, sg.height())
        else:
            self.setGeometry(sg.x() + half_w, sg.y(), half_w, sg.height())

    def mouseDoubleClickEvent(self, event):
        """Double-click anywhere in the window to toggle maximize/restore."""
        if event.button() == Qt.LeftButton:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()
        super().mouseDoubleClickEvent(event)

    def _build(self):
        # ── Central widget — contains only the page stack ─────────────────
        central = QWidget()
        central.setObjectName("PageContent")
        # CRITICAL: needed on Linux for background-color to render
        central.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(central)

        central_lay = QHBoxLayout(central)
        central_lay.setContentsMargins(0, 0, 0, 0)
        central_lay.setSpacing(0)

        self.stack = QStackedWidget()
        central_lay.addWidget(self.stack)

        # ── Dockable sidebar ─────────────────────────────────────────────
        self.sidebar = SidebarWidget()
        self.sidebar.page_selected.connect(self._switch_page)

        # Title bar (drag handle + pin button)
        self._sidebar_title_bar = SidebarDockTitleBar(self.sidebar)

        self._sidebar_dock = SidebarDock(self)
        self._sidebar_dock.setObjectName("SidebarDock")
        self._sidebar_dock.setTitleBarWidget(self._sidebar_title_bar)
        self._sidebar_dock.setWidget(self.sidebar)
        # Only left and right docking — no free floating (Windows taskbar style)
        self._sidebar_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        # Initial features: not movable when pinned (pin=True by default)
        self._sidebar_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        # When pin is toggled, update dock features
        self._sidebar_title_bar.pin_toggled.connect(self._on_sidebar_pin_toggled)
        self.addDockWidget(Qt.LeftDockWidgetArea, self._sidebar_dock)

        self.dashboard          = DashboardPage(self.repo)       # 0
        self.modules_page       = ModulesPage(self.repo)         # 1
        self.tasks_page         = TasksPage(self.repo)           # 2
        self.calendar_page      = CalendarPage(self.repo)        # 3
        self.stundenplan_page   = StundenplanPage(self.repo)     # 4  ← NEW
        self.timeline_page      = StudyPlanPage(self.repo)       # 5
        self.knowledge_page     = KnowledgePage(self.repo)       # 6
        self.timer_page         = TimerPage(self.repo)           # 7
        self.exam_page          = ExamPage(self.repo)            # 8
        self.grades_page        = GradesPage(self.repo)          # 9
        self.settings_page      = SettingsPage(self.repo)        # 10
        self.credits_page       = CreditsPage(self.repo)         # 11

        self.settings_page.theme_changed.connect(self._apply_theme)
        self.settings_page.lang_changed.connect(self._apply_lang)
        self.settings_page.accent_changed.connect(self._apply_accent_preset)
        self.timeline_page.set_dashboard(self.dashboard)

        # Give every page that supports it a global-refresh callback so data
        # changes made on one page are immediately reflected on all others.
        _pages = [
            self.dashboard, self.modules_page, self.tasks_page,
            self.calendar_page, self.stundenplan_page, self.timeline_page,
            self.knowledge_page, self.timer_page, self.exam_page,
            self.grades_page, self.settings_page, self.credits_page,
        ]
        for page in _pages:
            if hasattr(page, "set_global_refresh"):
                page.set_global_refresh(self._refresh_all)
            if hasattr(page, "set_navigate_cb"):
                page.set_navigate_cb(self._switch_page)
            self.stack.addWidget(page)

    def _refresh_all(self):
        """Refresh every page so any data change is immediately visible everywhere."""
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "refresh"):
                page.refresh()
        self._update_plan_badge()

    def _update_plan_badge(self):
        """Aktualisiert das Free/Pro-Badge in der Sidebar."""
        try:
            from semetra.infra.license import LicenseManager
            lm = LicenseManager(self.repo)
            if lm.is_pro():
                self.sidebar._plan_badge.setText("⭐ Pro")
                self.sidebar._plan_badge.setStyleSheet(
                    "background:#7C3AED;color:white;border-radius:8px;"
                    "padding:1px 8px;font-size:10px;font-weight:bold;"
                )
                activated_at = self.repo.get_setting("pro_activated_at") or ""
                tip_lines = ["Semetra Pro aktiv"]
                if activated_at:
                    tip_lines.append(f"Aktiviert: {activated_at}")
                tip_lines.append("Lizenz: Unbegrenzt")
                self.sidebar._plan_badge.setToolTip("\n".join(tip_lines))
                # Coach-Button ohne Pro-Hinweis für Pro-User
                self.sidebar._coach_btn.setText("  💬\uFE0F  Studien-Coach")
                self.sidebar._coach_btn.setToolTip("Ctrl+H — KI-Coach öffnen")
            else:
                self.sidebar._plan_badge.setText("Free Plan")
                self.sidebar._plan_badge.setStyleSheet(
                    "background:#F3F4F6;color:#6B7280;border-radius:8px;"
                    "padding:1px 8px;font-size:10px;font-weight:bold;"
                )
                self.sidebar._plan_badge.setToolTip(
                    "Kostenloser Plan aktiv\nUpgrade auf Pro für alle Features"
                )
                self.sidebar._coach_btn.setText("  💬\uFE0F  Studien-Coach  ⭐ Pro")
                self.sidebar._coach_btn.setToolTip(
                    "Ctrl+H — KI-Coach (Semetra Pro erforderlich)"
                )
        except Exception:
            pass

    def _switch_page(self, idx: int):
        # Close any floating combo-box popup before switching pages.
        # On Linux/Wayland the popup is a separate OS window that otherwise
        # stays visible even after the stack switches.
        for combo in self.findChildren(QComboBox):
            combo.hidePopup()
        self.stack.setCurrentIndex(idx)
        self.sidebar.select(idx)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def _apply_theme(self, theme: str):
        set_theme(theme)
        # Apply global QSS (covers all QSS-controlled widgets)
        QApplication.instance().setStyleSheet(get_qss(theme))
        # Fix inline QSS styles on persistent sidebar widgets that use _tc()
        sep_color = "#EAE8F2" if theme == "light" else "#1E1B2C"
        for child in self.sidebar.findChildren(QFrame):
            if child.frameShape() in (QFrame.HLine, QFrame.VLine):
                child.setStyleSheet(f"color: {sep_color};")
        # Refresh every page so dynamic/data-driven inline styles re-render
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "refresh"):
                page.refresh()
        # Force full repaint of main window and central widget
        self.update()
        if self.centralWidget():
            self.centralWidget().update()

    def _apply_accent_preset(self, preset: str):
        """Switch accent palette live without changing theme.

        Strategy:
          1. Apply new QSS string (covers all QSS-defined rules).
          2. Refresh pages (redraws data; may regenerate inline styles with
             hardcoded violet values in the Python source).
          3. Walk every widget and swap hardcoded violet hex → new accent in
             all inline setStyleSheet() calls (covers the >100 widgets that use
             hardcoded '#7C3AED' etc. in their individual stylesheets).
        """
        set_accent(preset)
        theme = self.repo.get_setting("theme") or "light"
        QApplication.instance().setStyleSheet(get_qss(theme))
        # Refresh pages so data/labels are current
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "refresh"):
                page.refresh()
        # Patch every inline stylesheet in the whole window:
        # always compare against the violet defaults (what the Python source hardcodes)
        violet  = ACCENT_PRESETS["violet"]
        chosen  = ACCENT_PRESETS.get(preset, violet)
        restyle_widgets_accent(self, violet, chosen)
        self.update()
        if self.centralWidget():
            self.centralWidget().update()

    def _apply_lang(self, lang: str):
        """
        Retranslate navigation buttons immediately.
        Full page translation requires a restart (labels set at build-time).
        """
        set_lang(lang)
        # Update sidebar nav buttons
        expanded = self.sidebar._expanded
        for i, (icon, key) in enumerate(self.sidebar.NAV_ITEMS):
            btn = self.sidebar._buttons[i]
            if btn is not None:
                if expanded:
                    btn.setText(f"  {icon}  {tr(key)}")
                else:
                    btn.setToolTip(tr(key))
        # Update coach button tooltip in sidebar
        self.sidebar._coach_btn.setToolTip(
            "Ctrl+H — " + ("KI-Coach öffnen" if lang == "de" else "Open AI Coach")
        )
        # Refresh all pages (updates dynamic data labels)
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "refresh"):
                page.refresh()


# ── Entry point ───────────────────────────────────────────────────────────

def gui_main(repo: SqliteRepo) -> None:
    # AA_NativeWindows must be set before QApplication creation on Windows
    # so that Aero Snap (drag-to-edge) and other native WM integrations work.
    if sys.platform == "win32":
        QApplication.setAttribute(Qt.AA_NativeWindows, True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Semetra")
    # Fusion style = consistent look on all platforms (Linux/Windows/Mac)
    app.setStyle("Fusion")
    # Apply saved language AND theme BEFORE any widget is created, so tr()/_tc() return correct values
    set_lang(repo.get_setting("language") or "de")
    set_theme(repo.get_setting("theme") or "light")
    window = SemetraWindow(repo)
    window.show()
    sys.exit(app.exec())
