# Semetra – Produkt-Roadmap

> Letztes Update: April 2026

---

## 🔴 Aktuelle Priorität — Launch-Ready machen

### 1. Mehrsprachigkeit (i18n)
Die Web App ist aktuell komplett auf Deutsch. Mit 8 unterstützten Ländern (CH, DE, AT, FR, IT, NL, ES, UK) muss die UI in den jeweiligen Sprachen verfügbar sein.

**Sprachen (nach Priorität):**
- [x] Deutsch (de) — aktuell einzige Sprache
- [ ] Englisch (en) — UK + internationaler Fallback
- [ ] Französisch (fr) — Frankreich + Westschweiz
- [ ] Italienisch (it) — Italien + Tessin
- [ ] Spanisch (es) — Spanien
- [ ] Niederländisch (nl) — Niederlande

**Technische Umsetzung:**
- [ ] i18n-Bibliothek einrichten (next-intl oder react-i18next)
- [ ] Translation-Dateien pro Sprache anlegen (JSON)
- [ ] Alle 23 Dashboard-Seiten auf Translation-Keys umstellen
- [ ] Sidebar, Navigation, Dialoge, Fehlermeldungen übersetzen
- [ ] Sprachauswahl in Settings-Seite einbauen
- [ ] Automatische Spracherkennung basierend auf Land des Studiengangs
- [ ] Locale für Datumsformatierung (date-fns) pro Sprache
- [ ] HTML lang-Attribut dynamisch setzen

### 2. Bestehende Features perfektionieren
Alle 23 Seiten sind funktional, aber müssen für den Launch poliert werden.

**UX & Konsistenz:**
- [ ] Einheitliche Fehlerbehandlung auf allen Seiten (Error Boundaries)
- [ ] Loading-States konsistent (Skeleton-Loader statt Spinner)
- [ ] Leere Zustände (Empty States) auf allen Seiten prüfen und verbessern
- [ ] Responsive Design: alle Seiten auf Mobile (< 640px) testen und fixen
- [ ] Tastatur-Navigation und Accessibility (a11y) Audit

**Funktionale Verbesserungen:**
- [ ] Settings: Export-Funktion — dynamisches Notensystem statt hardcoded `max_grade: 6`
- [ ] Grades: Notenprognosen und Trend-Charts (Pro)
- [ ] Dashboard: Widgets konfigurierbar machen
- [ ] Timer: Session-Historie und Statistiken verbessern
- [ ] Flashcards: KI-Import aus Dokumenten stabilisieren (Beta → Stable)
- [ ] Math: Formel-Datenbank erweitern

**Technische Schulden:**
- [ ] `utils.ts` — veraltete Swiss-hardcoded Funktionen (gradeColor, gradeLabel, roundGrade) deprecaten oder entfernen
- [ ] FH_INFO und COUNTRY_TABS aus modules/page.tsx und studiengaenge/page.tsx in shared Datei extrahieren
- [ ] TypeScript Errors bereinigen (Stripe-Types, Supabase-Cookie-Handlers, Flashcards)

### 3. Website (semetra.ch) Launch-Polish
- [x] Internationale Hochschulen auf Landing Page — 8 Länder mit Flaggen
- [x] Legal Disclaimer im Impressum
- [x] FAQ zu unterstützten Ländern
- [ ] Mehrsprachige Landing Page (mindestens EN + DE)
- [ ] SEO-Optimierung: strukturierte Daten, Sitemap, hreflang-Tags
- [ ] Performance: Bilder optimieren, Critical CSS

---

## 🟡 Nächste Phase — Post-Launch

### 4. Hochschul-Datenbank erweitern
- [x] FFHS — Informatik, Cyber Security, Wirtschaftsinformatik
- [x] ZHAW — Informatik, Wirtschaftsinformatik
- [x] BFH — Informatik, BWL
- [x] HSLU — Informatik, Wirtschaftsinformatik, Digital Ideation
- [x] FHGR — Computational and Data Science
- [x] SUPSI — Informatica, Ingegneria Elettronica
- [x] 30+ Hochschulen in DE, AT, FR, IT, NL, ES, UK
- [ ] FHNW — Informatik, Wirtschaftsinformatik
- [ ] OST — Informatik
- [ ] HES-SO — Medieningenieurwesen
- [ ] Weitere Unis auf User-Anfrage ergänzen
- [ ] Community-Vorschläge: User können fehlende Studiengänge melden

### 5. Erweiterte KI-Features
- [ ] KI-Zusammenfassungen von Notizen (GPT/Claude-Integration)
- [ ] Intelligenter Lerncoach: personalisierte Lernempfehlungen
- [ ] KI-generierte Prüfungsfragen aus Karteikarten
- [ ] Smart Scheduling: optimale Lernzeiten basierend auf Timer-Daten

### 6. Desktop-App Synchronisation
- [x] Sync-Protokoll: SQLite lokal ↔ Supabase Cloud
- [x] Offline-first: App funktioniert ohne Internet
- [ ] Desktop-App Feature-Parität mit Web App sicherstellen
- [ ] Auto-Update Mechanismus für Desktop-App
- [ ] macOS Version der Desktop-App

---

## 🔵 Mittelfristig

### 7. Kollaboration (Light)
- [ ] Studiengang-Link teilen: Kommilitonen können denselben Studiengang importieren
- [ ] Karteikarten-Decks teilen (öffentliche Bibliothek)
- [ ] Anonyme Notenstatistiken pro Studiengang (Durchschnitt, Verteilung)

### 8. Erweiterte Analytics (Pro)
- [ ] Semester-Report als PDF Export
- [ ] Lernzeit-Analyse mit Heatmap und Trends
- [ ] ECTS-Prognose: "Wann bin ich fertig?"
- [ ] Vergleich mit anonymisierten Kohorten-Daten

---

## 🟢 Langfristig

### 9. Mobile App (iOS & Android)
- [ ] Framework: React Native (geteilte Logik mit Web App)
- [ ] Gemeinsame Sync-Schicht (Supabase)
- [ ] Kernfeatures: Dashboard, Aufgaben, Karteikarten, Timer
- [ ] Push-Notifications (Prüfungserinnerungen, Deadlines)
- [ ] App Store / Play Store Veröffentlichung

### 10. Monetarisierung erweitern
- [ ] Team/Institutional Plan (für Hochschulen)
- [ ] Affiliate-Programm für Studierendenvertretungen
- [ ] Premium KI-Features als Add-on

---

## ✅ Erledigt

### Infrastruktur
- [x] Website online (semetra.ch via Cloudflare Pages)
- [x] www.semetra.ch aktiviert
- [x] Stripe-Integration (Monatlich, Halbjährlich, Jährlich, Lifetime)
- [x] Supabase Backend mit 22 Migrations
- [x] Authentifizierung (E-Mail, OAuth)
- [x] Row Level Security (RLS)
- [x] Desktop ↔ Web Sync (Echtzeit)
- [x] Pro/Free Feature-Gating

### Web App (23 Seiten — alle funktional)
- [x] Dashboard, Navigator, Module, Aufgaben
- [x] Studienplan, Kalender, Timeline, Stundenplan, Prüfungen
- [x] Notizen, Dokumente, Wissen, Mind Maps, Brainstorming, Karteikarten
- [x] Mathe-Raum (Rechner, Gleichungen, Matrizen, Plotter, Statistik)
- [x] Timer (Pomodoro), Noten & ECTS, Credits
- [x] Settings, About, Upgrade, Studiengänge

### Desktop App
- [x] Professioneller Installer (Inno Setup)
- [x] App-Icon, version_info.txt
- [x] FH-Datenbank Dialog (offline, kein Scraping)
- [x] Web-Scraping entfernt (Rechtsschutz)

### Internationalisierung (Daten)
- [x] 8 Notensysteme (CH, DE, AT, FR, IT, NL, ES, UK)
- [x] 30+ Hochschulen mit 45+ Studiengängen
- [x] Dynamische Notenvalidierung, Labels, Farben pro Land
- [x] Länderfilter im Studiengang-Import
- [x] Legal Disclaimers (Impressum + Import-UI)
- [x] Website aktualisiert mit internationalem Fokus

---

## 📝 Architektur-Notizen

**Tech-Stack:**
- Desktop: Python 3 + PySide6, SQLite lokal
- Web: Next.js 14 + React 18, TypeScript, Tailwind CSS
- Backend: Supabase (PostgreSQL, Auth, Realtime)
- Payments: Stripe (4 Tiers + Lifetime)
- Website: Statisches HTML auf Cloudflare Pages
- Hosting: Vercel (Web App)

**Sync:** Bidirektional SQLite ↔ Supabase, offline-first, account-basierte Lizenzierung.

**i18n-Empfehlung:** `next-intl` (nativer Next.js App Router Support, Server Components kompatibel, kompakt). Alternative: `react-i18next` (grösseres Ökosystem, aber mehr Setup nötig).
