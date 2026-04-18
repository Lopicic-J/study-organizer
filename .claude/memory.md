# Memory

## Now
- **SEMETRA IST LIVE** (Launch 16.04.2026) — app.semetra.ch
- Massive Session: 97 Commits — grösste Transformation seit Launch
- Performance + Engines + UX + Features + Bugs + 6 Migrationen deployed
- Sidebar 40→13, 8+ Lernmethoden, Lernraum + Prüfungsrelevanz-System
- 458 Tests grün, 209 Pages, 6 Sprachen i18n, 17 Notensysteme
- Neue Features: Lernraum, Exam Relevance, Guided Session, Exam Simulator,
  Exam Prep, Challenges, Module Setup, Semester Review, Quick Review,
  Reflections, Wellness, Community Flashcards, Ambient Sounds
- Decision Engine: planned=active, learningType, examRelevanceBoost

## Project: Semetra
- **Was**: Smarter Studienplaner für Schweizer FH-Studierende (SaaS)
- **Firma**: Lopicic Technologies / JL DevTech
- **Stack Desktop**: Python 3.12, PySide6, SQLite, PyInstaller
- **Stack Web**: Next.js 16, React 18, TypeScript, Tailwind, Supabase, Stripe
- **Stack Marketing**: semetra.ch auf Cloudflare Pages (ZIP-Upload)
- **Hosting**: Vercel (Web-App), Cloudflare Pages (Marketing)
- **Monitoring**: Sentry
- **Testing**: Vitest (295 Tests), pytest
- **Pfad Desktop**: `src/semetra/`
- **Pfad Web**: `semetra-web/`
- **Pfad Marketing**: `website/`

## Status
- Web-App: 7-Phasen-Masterplan abgeschlossen, Optimization Sprint done, Masterplan 100% + Cortex Engine abgeschlossen
- Desktop-App: Stabil, wird gepflegt aber nicht aktiv erweitert
- Marketing: semetra.ch v8 live, Instagram (semetra.official) aufgesetzt
- Migrationen: 047-074+ aufgestaut, manuell zu deployen
- Tests: 295 grün, 100+ neue geplant (Schedule, Decision, Timer, E2E)
- i18n: 2039 Keys in 6 Sprachen (de, en, fr, it, es, nl)

## Deadline
- **August 2026**: Studienstart = Launch-Deadline (FFHS als erste FH mit echten Daten)

## Workflow-Muster
- Solo-Entwickler: Code, Design, Produkt, Marketing — alles eine Person
- Lange Deep-Work-Sessions, klare Vision, systematische Abarbeitung
- Springt zwischen Fronten (Web, Desktop, Marketing, Infra)
- Kein externes PM-Tool — alles über Markdown (Task Board, Roadmap, Daily Notes)
- Zwischen Sessions: Supabase-Migrationen, Vercel-Deploys, Stripe-Config manuell

## Zeitfresser (Automatisierungspotential)
- Supabase-Migrationen (repetitiv, fehleranfällig)
- UI-Komponenten (jede Engine = 4-6 neue Dateien)
- i18n-Pflege (6 Sprachen, jedes Feature = 6x Keys)
- Marketing-Content (Website, Instagram, Texte)
- FH-Daten-Import (individuelle Aufbereitung pro Hochschule)
- Testing-Ausbau (100+ Tests noch offen)
- Deployment (manuell, kein CI/CD)

## Open Threads
- Launch-Vorbereitung semetra.ch finalisieren
- Migrationen 047-074+ deployen
- Test-Coverage ausbauen
- CI/CD-Pipeline einrichten

## Blockers
- (none)
