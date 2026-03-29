# Semetra — Projektdokumentation für Claude

> Dieses Dokument am Anfang jeder neuen Claude-Session einfügen/hochladen,
> damit Claude sofort den vollen Projektkontext hat.

---

## Was ist dieses Projekt?

Ein **Desktop-Studienorganizer** für Fachhochschul-Studenten, aufgebaut mit Python + PySide6 (Qt).
Herzstück ist die semester- und modulweise Strukturierung des Studiums — exakt wie im offiziellen Studienplan.

**Unique Selling Point:**
- Einziger Organizer der ein FH-Studium 1:1 abbildet: Semester → Module → Lernziele → Lerninhalte
- Smarter PDF-Import: Modulhandbücher werden automatisch gescrapt (Lernziele, Lerninhalte, Prüfungen)
- Modul-Aktivierung: Wahl-/Vertiefungsmodule können im Studienplan deaktiviert werden → ECTS-Gesamtrechnung passt sich an
- Geplantes Premium-Feature: KI-Lernplan-Generator (OpenAI/Claude API)

**Zielgruppe:** MINT-nahe Studiengänge mit standardisierten Studienplänen (Start: FFHS Informatik BSc)
**Betrieb:** Lokale SQLite-Datenbank, keine Cloud, keine Accounts

---

## Projektstruktur

```
semetra/
├── start.sh                          # App starten: bash start.sh
├── study.db                          # SQLite-Datenbank (persistiert)
├── pyproject.toml                    # Dependencies
├── .venv/                            # Python virtualenv (PySide6 6.10.2!)
└── src/semetra/
    ├── __main__.py                   # Einstiegspunkt
    ├── app.py                        # QApplication setup
    ├── gui.py                        # HAUPT-DATEI: gesamte UI (~5400 Zeilen)
    ├── infra/
    │   ├── schema.py                 # SQLite DDL + Migrationen
    │   └── db.py                     # DB-Verbindung
    ├── repo/
    │   └── sqlite_repo.py            # Datenbankzugriff (~455 Zeilen)
    ├── adapters/
    │   ├── pdf_scraper.py            # PDF-Parser für Modulhandbücher (~558 Zeilen)
    │   ├── ffhs_importer.py          # FFHS-spezifischer Importer
    │   └── structured_scraper.py     # Strukturierter Scraper
    └── service/
        ├── repository.py             # Service-Layer
        └── validation.py
```

---

## Datenbankschema (SQLite)

### Tabelle `modules` — Kernentität
```sql
CREATE TABLE modules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    code            TEXT DEFAULT '',
    semester        TEXT NOT NULL,          -- '1'..'9' oder '' für nicht zugeordnet
    ects            REAL NOT NULL DEFAULT 0,
    lecturer        TEXT DEFAULT '',
    link            TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'planned',  -- planned|active|completed|paused
    exam_date       TEXT DEFAULT '',
    weighting       REAL NOT NULL DEFAULT 1.0,
    github_link     TEXT DEFAULT '',
    sharepoint_link TEXT DEFAULT '',
    literature_links TEXT DEFAULT '',
    notes_link      TEXT DEFAULT '',
    module_type     TEXT NOT NULL DEFAULT 'pflicht',  -- pflicht|wahl|vertiefung
    in_plan         INTEGER NOT NULL DEFAULT 1        -- 1=aktiv, 0=deaktiviert
);
```

### Weitere Tabellen
- **`tasks`** — Aufgaben pro Modul (title, priority, status, due_date, notes)
- **`events`** — Kalendereinträge (study_block, custom; Wiederholung: none/daily/weekly)
- **`time_logs`** — Lernzeit-Tracking (Pomodoro + manuelle Einträge)
- **`app_settings`** — Key-Value-Einstellungen (theme, language, etc.)
- **`topics`** — Wissensthemen pro Modul mit Kenntnisniveau 0-5
- **`grades`** — Noten pro Modul
- **`module_scraped_data`** — Gescrapte Inhalte:
  - `data_type`: `'objective'` (Lernziel) | `'content_section'` (Lerninhalt) | `'assessment'` (Prüfung)
  - `body`: JSON-Array von Sub-Items (für content_section) oder Freitext
  - `weight`: Gewichtung in % (für assessments)

### Migrationen (automatisch in `ensure_schema()`)
- `code` — nachträglich hinzugefügt
- `module_type` — nachträglich hinzugefügt (DEFAULT 'pflicht')
- `in_plan` — nachträglich hinzugefügt (DEFAULT 1)
- Automatische Bereinigung: Semester-Werte wie "FS26", "HS25/26" → '' (leer)

---

## Aktueller Datenstand (FFHS Informatik BSc)

41 Module, 198 ECTS total, 173 ECTS "in_plan=1" (25 ECTS deaktiviert = nicht gewählte Wahlmodule)

**Semester 1–9 Pflichtmodule** + Wahl- und Vertiefungsmodule ohne Semesterzuordnung.

Deaktivierte Module (in_plan=0):
- Blockchain (Wahl, 5 ECTS)
- Data Warehousing und Business (Wahl, 5 ECTS)
- Fortgeschrittene Web-Technologie (Wahl, 5 ECTS)
- Game-Development (Wahl, 5 ECTS)
- Quantum Computing (Wahl, 5 ECTS)

---

## UI-Seitenstruktur (gui.py)

| Seite | Klasse | Beschreibung |
|-------|--------|-------------|
| Dashboard | `DashboardPage` | Stat-Cards, Fortschritt, Prüfungen, Modulübersicht |
| Module | `ModulesPage` | Liste (sortiert nach Semester+Typ) + Detail-Panel |
| Aufgaben | `TasksPage` | Aufgaben über alle Module |
| Kalender | `CalendarPage` | Monatsansicht + Tagesdetail |
| Studienplan | `StudyPlanPage` | **Herzstück**: Semester-Cards mit Modul-Cards + Detail-Panel |
| Wissen | `KnowledgePage` | Topics + Kenntnisniveau |
| Timer | `TimerPage` | Pomodoro-Timer |
| Prüfungen | `ExamPage` | Prüfungsübersicht |
| Noten | `GradesPage` | Notenrechner |
| Einstellungen | `SettingsPage` | Theme, Sprache, etc. |

**Sidebar:** `SidebarWidget` — 260px fest, Navigation mit NavBtn-Stil

---

## Wichtige Code-Patterns

### Theme-System
```python
_THEME = "light"  # oder "dark"
def _tc(light: str, dark: str) -> str:
    return dark if _THEME == "dark" else light
# Immer _tc() verwenden für theme-adaptive Farben!
```

### in_plan — sicherer Zugriff (None-safe!)
```python
# IMMER so — m["in_plan"] kann NULL sein!
in_plan = int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1
```

### ECTS/Modul-Filterung — nur in_plan=1 zählen
```python
plan_modules = [m for m in all_modules if (int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1)]
total_ects = sum(float(m["ects"]) for m in plan_modules)
```

### QListWidget-Items (KRITISCH für PySide6 6.10.2)
```python
# RICHTIG: parent im Konstruktor → sofortige C++-Ownership
item = QListWidgetItem("text", self.list_widget)
item.setData(Qt.UserRole, some_id)  # NIEMALS None, immer -1 für Separatoren

# FALSCH (kann Crash verursachen):
# item = QListWidgetItem("text")
# self.list_widget.addItem(item)  # Python-GC könnte item zu früh löschen
```

### blockSignals — sicher
```python
# RICHTIG:
self.mod_list.blockSignals(True)
self.mod_list.clear()
# ... items hinzufügen ...
self.mod_list.blockSignals(False)

# FALSCH (Crash in PySide6 6.10.2!):
# sm = self.mod_list.selectionModel()
# sm.blockSignals(True)
# self.mod_list.clear()  # kann selectionModel invalidieren!
# sm.blockSignals(False)  # → munmap_chunk() / free(): invalid pointer
```

### Separator-Items in QListWidget
```python
sep = QListWidgetItem("── Überschrift", self.list_widget)
sep.setFlags(Qt.ItemIsEnabled)   # NIEMALS Qt.NoItemFlags → Crash!
sep.setData(Qt.UserRole, -1)     # NIEMALS None → Crash!
```

---

## Bekannte Bugs & Fixes (wichtig!)

### Crash: "free(): invalid pointer" / "munmap_chunk(): invalid pointer"
**Ursache:** PySide6 6.10.2-spezifisches Problem.
**Fix 1:** `selectionModel().blockSignals()` ersetzt durch `listWidget.blockSignals()`
**Fix 2:** `QListWidgetItem(text, parent)` statt `addItem()` nachträglich
**Fix 3:** `Qt.NoItemFlags` → `Qt.ItemIsEnabled` für Separator-Items
**Fix 4:** `setData(Qt.UserRole, None)` → `setData(Qt.UserRole, -1)`

### ECTS-Gesamtrechnung bei deaktivierten Modulen
`_toggle_plan()` und `_toggle_plan_from_detail()` müssen **vor** `_rebuild_semesters()`
explizit `_update_global_stats()` aufrufen, sonst bleiben die Stat-Cards oben stale.

---

## StudyPlanPage — Detail-Beschreibung

### Linke Seite: Semester-Roadmap
- `_rebuild_semesters()`: baut alle QFrame-Semester-Cards neu auf
- Responsive Grid: 1 Spalte wenn Container < 560px, sonst 2 Spalten
- Nur `in_plan=1` Module zählen für Semester-ECTS und Fortschritt

### Modul-Cards (`_make_mod_card`)
- Höhe: 100px, 3 Zeilen
- Zeile 1: Farbpunkt + Name + Status-Badge + **⊘/⊕ Plan-Toggle**
- Zeile 2: 📅 Semester-Picker (QPushButton mit QMenu) + Typ-Badge (Pflicht/Wahl/Vertiefung)
- Zeile 3: Fortschrittsbalken + ECTS-Label
- Deaktivierte Module (in_plan=0): ausgegraut, Name durchgestrichen, Badge "Wahl · nicht gewählt"
- Alle Badge-/Button-Farben mit `_tc()` für Dark-/Light-Mode

### Rechte Seite: Detail-Panel
- `_rd_title`, `_rd_info`, `_rd_bar` — Modul-Übersicht
- `_rd_plan_btn` — "⊘ Ausschließen" / "⊕ Aufnehmen" (rot/grün)
- `_rd_edit_btn` — öffnet ModuleDialog
- Tabs: Aufgaben | Lernziele | Lerninhalte | Prüfungen

---

## ModulesPage — Detail-Beschreibung

### Linke Liste (`_populate_list`)
- Gruppiert nach Semester, dann nach Typ (Pflicht → Wahl → Vertiefung)
- Separator-Items: `Qt.ItemIsEnabled`, `UserRole = -1`
- Modul-Items: `UserRole = module_id` (immer > 0)

### _selected_ids() — Separatoren überspringen
```python
return [item.data(Qt.UserRole) for i in range(count)
        if item.isSelected() and (item.data(Qt.UserRole) or -1) > 0]
```

---

## PDF-Scraper (`pdf_scraper.py`)

- Liest FFHS-Modulhandbuch-PDFs
- `_is_garbage_title(s)` filtert: Datumzeilen, "Seite \d", "Modulplan", "Gültig", kurze Strings, etc.
- `_flush_pending()` puffert Titel bis Inhalt kommt (merged Split-Absätze)
- `_extract_content()` erkennt Sektionen: Lernziele, Lerninhalte, Assessments
- 244 Garbage-Sections wurden initial aus DB gelöscht und 28 PDFs neu gescrapt

---

## Fenster & Sizing

```python
self.setMinimumSize(620, 480)   # erlaubt Windows-Snap auf Monitoren ab 1280px
self.resize(1280, 860)          # Startgrösse
```

**Sidebar:** `setFixedWidth(260)` — NavBtns 48px Höhe, 15px Schrift

**StudyPlan-Splitter:**
```python
splitter.setSizes([600, 400])
splitter.setStretchFactor(0, 3)  # linke Seite wächst stärker
splitter.setStretchFactor(1, 2)
```

---

## Offene Aufgaben / Nächste Schritte

### Bug — ECTS-Gesamtrechnung (noch nicht vollständig gefixt)
Die ECTS-Karten auf der StudyPlan-Seite aktualisieren sich erst wenn
`_update_global_stats()` aufgerufen wird. Prüfen ob dies in allen Toggle-Pfaden
korrekt passiert. Auch Dashboard-ECTS aktualisiert sich erst beim Seitenwechsel.

### Feature — KI-Lernplan-Generator (Premium)
- Input: Modul wählen, Prüfungsdatum, verfügbare Stunden/Woche
- Output: Strukturierter Wochenplan basierend auf Lernzielen + Lerninhalten aus DB
- API: OpenAI oder Claude (Anthropic) via API-Key in Einstellungen
- UI: Neuer Tab in Detail-Panel oder eigene Seite

### Feature — Weitere Studiengänge
- Scraper für ZHAW, BFH, HSG anpassen
- Modulplan-Import für andere FFHS-Studiengänge (Wirtschaftsinformatik, etc.)

### Feature — Cloud-Sync (Premium)
- SQLite → Supabase oder eigener Server
- Sync zwischen Desktop und (zukünftiger) Mobile-App

### Plattform — Windows Store
- Paketierung mit `briefcase` als MSIX
- Voraussetzung: App läuft stabil ohne Crashes

### Plattform — Mobile (langfristig)
- Flutter-Neuentwicklung (iOS + Android + Windows)
- Python-Backend (Scraper, DB-Logik) wiederverwendbar via FastAPI

---

## Business-Idee (Zusammenfassung)

**Konzept:** Einziger FH-Studienorganizer der Semester/Modul/Lernziel-Struktur 1:1 abbildet.
**Differenzierung:** Smarter PDF-Import + KI-Lernplan als Premium-Feature.
**Zielmarkt Start:** FFHS → alle Schweizer FHs → deutsche duale Hochschulen.
**Modell:** Freemium — Basis kostenlos, KI-Features + Cloud-Sync ~6-9 CHF/Monat.
**Erster Schritt:** Windows Store (gratis) + Landingpage mit 60-Sek Demo-Video.

---

## Entwicklungsumgebung

```bash
cd ~/semetra
bash start.sh          # App starten

# Direkte DB-Abfragen:
sqlite3 study.db "SELECT name, semester, in_plan FROM modules"

# Abhängigkeiten:
# PySide6==6.10.2  (KRITISCH: andere Versionen nicht getestet)
# pdfplumber
# openpyxl
```

**Git-Branch:** `feat/tasks-v1`

---

## Wichtige Hinweise für neue Claude-Sessions

1. **PySide6 6.10.2 ist sensibel** — die Qt.NoItemFlags / None-UserRole / selectionModel-Crashes sind gefixt, aber neue QListWidget-Patterns immer mit den obigen sicheren Mustern implementieren.

2. **`_tc(light, dark)` immer verwenden** — niemals Farben hardcoden ohne Dark-Mode-Variante.

3. **`in_plan or 1` Fallback** — DB-Feld kann NULL sein, immer absichern.

4. **`_update_global_stats()` nach jeder Daten-Mutation** die ECTS oder Modulanzahl beeinflusst.

5. **gui.py ist sehr lang (~5400 Zeilen)** — beim Suchen immer `Grep` mit Zeilennummern nutzen, dann nur den relevanten Abschnitt mit `Read` laden.
