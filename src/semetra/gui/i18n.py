"""Internationalization (i18n) — translations, language switching, and locale functions."""

from datetime import datetime
from typing import Dict

from semetra.gui import state
from semetra.gui.constants import KNOWLEDGE_LABELS

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


def set_lang(lang: str) -> None:
    """Set the current language for translations."""
    state._LANG = lang if lang in TRANSLATIONS else "de"


def tr(key: str) -> str:
    """Translate a key using the current language."""
    return TRANSLATIONS.get(state._LANG, TRANSLATIONS["de"]).get(key, key)


def tr_know(k: int) -> str:
    """Translate knowledge level by ID."""
    _map = {0: "know.not_started", 1: "know.basics", 2: "know.familiar", 3: "know.good", 4: "know.expert"}
    return tr(_map[k]) if k in _map else KNOWLEDGE_LABELS.get(k, str(k))


def tr_status(s: str) -> str:
    """Translate a status string to the current language."""
    _map = {
        "planned": "status.planned",
        "active": "status.active",
        "completed": "status.completed",
        "paused": "status.paused",
        "Done": "status.done",
        "Open": "status.open"
    }
    return tr(_map[s]) if s in _map else s


def greeting() -> str:
    """Get the appropriate greeting for the current time of day."""
    hr = datetime.now().hour
    if hr < 12:
        return tr("greet.morning")
    if hr < 18:
        return tr("greet.day")
    return tr("greet.evening")
