# Semetra – Produkt-Roadmap

> Letztes Update: April 2026

---

## 🔴 Aktuelle Priorität — Retention & Mehrwert

### 1. Fortschritts-Dashboard & Lernsträhnen
Studierende brauchen einen täglichen Grund, Semetra zu öffnen. Das Dashboard muss die Frage beantworten: **"Bin ich auf Kurs?"**

**Fortschritts-Dashboard:**
- [ ] "Wie stehe ich?"-Übersicht: ECTS-Fortschritt (X von 180), Notenschnitt, Semester N von M
- [ ] Wöchentliche Lernzeit-Übersicht (aus time_logs) mit Vergleich zur Vorwoche
- [ ] Modul-Ampel: grün = bestanden, gelb = aktiv, rot = Prüfung bald
- [ ] Themen-Fortschritt pro Modul: wie viele Lernziele auf "understood" vs. "not_started"
- [ ] Trend-Grafik: Notendurchschnitt über Semester hinweg

**Lernsträhnen (Streak-System):**
- [ ] Tägliche Lernsträhne basierend auf time_logs (mind. 15 Min. = 1 Tag)
- [ ] Streak-Anzeige im Dashboard und Sidebar ("🔥 14 Tage")
- [ ] Wochenübersicht: Tage als Punkte (wie GitHub Contribution Graph)
- [ ] Meilensteine: "7 Tage", "30 Tage", "100 Tage" mit visueller Belohnung
- [ ] Sanfte Erinnerung per Notification wenn Streak gefährdet

**Persönliche Meilensteine:**
- [ ] "Erstes Modul bestanden", "100 Flashcards gelernt", "50 Stunden studiert"
- [ ] Semester-Zusammenfassung am Ende jedes Semesters
- [ ] Fortschritts-Badges (dezent, Apple-Watch-Ringe-Stil — nicht kindisch)

### 2. KI-Lernassistent (Pro)
Grösster Treiber für Pro-Konversionen. Claude-basiert, aufbauend auf bestehender Flashcard-KI.

**Dokument → Lernmaterial Pipeline:**
- [ ] Dokument/PDF hochladen → KI erstellt automatisch:
  - Zusammenfassung (kurz + ausführlich)
  - Flashcards (bestehende API erweitern)
  - Lernziele/Topics
  - Übungsfragen mit Lösungen
- [ ] Batch-Import: ganzer Ordner Vorlesungsfolien → komplettes Lernset
- [ ] Quellenverweis: jede generierte Karte zeigt die Originaldatei

**"Erkläre mir das"-Modus:**
- [ ] Thema aus Lernzielen auswählen → KI erklärt auf Studierenden-Niveau
- [ ] Kontext-bewusst: KI kennt das Modul, den Studiengang, das Semester
- [ ] Follow-up Fragen stellen ("Kannst du ein Beispiel geben?")
- [ ] Erklärungen als Notiz speichern

**Prüfungsvorbereitung:**
- [ ] KI-generierte Übungsfragen basierend auf Topics eines Moduls
- [ ] Schwierigkeitsgrade: einfach → mittel → Prüfungsniveau
- [ ] Mock-Exams: KI erstellt eine komplette Probeprüfung
- [ ] Schwächen-Analyse: "Diese Themen solltest du nochmal anschauen"

**Gating:**
- Free: 5 KI-Aktionen/Tag
- Pro: Unbegrenzt

### 3. Prüfungscountdown & Lernplan-Generator (Pro)
Konkreter Nutzen in der Stressphase — wenn Studierende am ehesten bereit sind zu zahlen.

- [ ] Countdown-Widget pro Prüfung im Dashboard ("Analysis II in 12 Tagen")
- [ ] Auto-Lernplan: basierend auf Prüfungsterminen + Themenanzahl + knowledge_level
- [ ] Vorschlag: "Diese Woche Analysis fokussieren, nächste Woche Statistik"
- [ ] Tagesplan: "Heute 2h Analysis (Kapitel 3-4), 1h Datenbanken (Repetition)"
- [ ] Anpassbar: Studierende können verfügbare Stunden pro Tag eingeben
- [ ] Berücksichtigt Spaced Repetition: Themen mit niedrigem knowledge_level priorisiert
- [ ] Integration mit Timer: "Jetzt starten" öffnet Pomodoro für das geplante Thema

---

## 🟡 Nächste Phase — Wachstum & Bindung

### 4. Semester-Report PDF (Pro)
Steht in Pro-Features, ist aber noch nicht implementiert.

- [ ] Schöner PDF-Report am Semesterende
- [ ] Inhalte: Noten-Übersicht, ECTS-Fortschritt, investierte Stunden/Modul
- [ ] Trend-Grafiken: Notenentwicklung, Lernzeit-Verteilung
- [ ] Vergleich mit Vorjahr/Vorsemester
- [ ] Druckbar und teilbar (für Eltern, Stipendien, Bewerbungen)

### 5. Notiz-Sharing & Kollaboration (Viralität)
Natürlicher Wachstumskanal — jeder geteilte Link bringt potenzielle Nutzer.

- [ ] Notizen per Link teilen (read-only, kein Account nötig zum Lesen)
- [ ] Flashcard-Sets teilen (öffentliche Bibliothek pro Studiengang)
- [ ] Mind Maps teilen
- [ ] Teilbare Links mit Semetra-Branding ("Erstellt mit Semetra")
- [ ] Import: geteilte Flashcard-Sets in eigene Sammlung übernehmen
- [ ] Community-Bibliothek: beste Flashcard-Sets pro Modul/FH anzeigen
- [ ] Anonyme Notenstatistiken pro Studiengang (Durchschnitt, Verteilung)

### 6. Mobile PWA / Responsive
Studierende leben auf dem Handy. Semetra muss dort funktionieren.

- [ ] Progressive Web App (PWA) mit Service Worker
- [ ] Offline-fähig: Flashcards, Timer, Dashboard auch ohne Internet
- [ ] Push-Notifications: Prüfungserinnerungen, Deadline-Alerts, Streak-Warnung
- [ ] Responsive Optimierung: alle 23 Seiten auf Mobile (< 640px) testen und fixen
- [ ] "Quick Actions" auf Mobile: Flashcard-Review, Timer starten, Aufgabe abhaken
- [ ] App-Icon auf Homescreen (PWA Install Prompt)

### 7. Hochschul-Datenbank erweitern
- [x] 30+ Hochschulen in CH, DE, AT, FR, IT, NL, ES, UK
- [ ] FHNW — Informatik, Wirtschaftsinformatik
- [ ] OST — Informatik
- [ ] HES-SO — Medieningenieurwesen
- [ ] Weitere Unis auf User-Anfrage ergänzen
- [ ] Community-Vorschläge: User können fehlende Studiengänge melden
- [ ] Automatischer Studiengang-Request per Formular

---

## 🔵 Mittelfristig — Differenzierung

### 8. Erweiterte Analytics (Pro)
- [ ] Lernzeit-Heatmap (GitHub-Stil) — wann und wie viel gelernt
- [ ] ECTS-Prognose: "Bei aktuellem Tempo fertig in Semester X"
- [ ] Modul-Schwierigkeits-Ranking basierend auf eigener Lernzeit
- [ ] Notenprognosen basierend auf bisherigem Trend
- [ ] Vergleich mit anonymisierten Kohorten-Daten

### 9. Erweiterte Gamification
- [ ] Wochen-Challenges: "Lerne diese Woche 10h" mit visuellem Fortschritt
- [ ] Semester-Goals: eigene Ziele setzen und tracken
- [ ] "Study Recap": monatliche Zusammenfassung per E-Mail oder In-App
- [ ] Achievements-System (dezent): freischaltbare Badges für Meilensteine

### 10. Desktop-App Synchronisation verfeinern
- [x] Sync-Protokoll: SQLite lokal ↔ Supabase Cloud
- [x] Offline-first: App funktioniert ohne Internet
- [ ] Desktop-App Feature-Parität mit Web App sicherstellen
- [ ] Auto-Update Mechanismus für Desktop-App
- [ ] macOS Version der Desktop-App
- [ ] Sync-Status-Anzeige in beiden Apps

---

## 🟢 Langfristig — Skalierung

### 11. Native Mobile App (iOS & Android)
- [ ] Framework: React Native (geteilte Logik mit Web App)
- [ ] Gemeinsame Sync-Schicht (Supabase)
- [ ] Kernfeatures: Dashboard, Aufgaben, Karteikarten, Timer
- [ ] Push-Notifications (Prüfungserinnerungen, Deadlines, Streaks)
- [ ] App Store / Play Store Veröffentlichung
- [ ] Widgets: Nächste Prüfung, Streak, Tagesplan

### 12. Monetarisierung erweitern
- [ ] Team/Institutional Plan (für Hochschulen / Lerngruppen)
- [ ] Affiliate-Programm für Studierendenvertretungen
- [ ] Premium KI-Features als Add-on (höheres Volumen)
- [ ] Referral-Programm: "Empfehle Semetra, erhalte 1 Monat Pro gratis"

### 13. Website (semetra.ch) Ausbau
- [ ] Mehrsprachige Landing Page (mindestens EN + DE)
- [ ] SEO-Optimierung: strukturierte Daten, Sitemap, hreflang-Tags
- [ ] Performance: Bilder optimieren, Critical CSS
- [ ] Blog mit Lerntipps (SEO-Traffic)
- [ ] Testimonials und Erfolgsgeschichten

---

## 🟣 Vision — Semetra als Studierenden-Plattform

### 14. User-Profil & Personalisierung
Semetra wird persönlich — jeder Studierende hat eine eigene Identität auf der Plattform.

- [ ] Öffentliches Profil: Benutzername, Profilbild, Titelbild
- [ ] Persönliche Angaben: Name, Bio, Studiengang, Semester, FH/Uni
- [ ] Profil-URL: semetra.ch/u/username
- [ ] Sichtbare Studien-Infos: wo studiert die Person, welches Fach, welches Semester
- [ ] Privatsphäre-Einstellungen: was öffentlich, was nur für Kontakte sichtbar
- [ ] Profilbild-Upload mit Crop/Resize
- [ ] Supabase Storage für Bilder (Profilbild + Titelbild)
- [ ] Profil-Badges: Pro-User, Streak-Rekorde, Meilensteine

### 15. Community-Chat & Vernetzung (Pro)
Studierende verbinden sich FH-übergreifend — Semetra wird zum Studierenden-Netzwerk.

- [ ] Direktnachrichten (1:1 Chat) zwischen Usern
- [ ] Gruppenchats (pro Modul, pro Studiengang, pro FH)
- [ ] Automatische Gruppen: "FFHS Informatik Semester 3" basierend auf Profildaten
- [ ] FH-übergreifende Kanäle: "Informatik allgemein", "Prüfungstipps", "Werkstudenten"
- [ ] Supabase Realtime für Live-Chat
- [ ] Nachrichten-Notifications (In-App + Push)
- [ ] User suchen/finden nach FH, Studiengang, Semester
- [ ] Kontaktliste / Connections (wie LinkedIn-Light für Studierende)
- [ ] Hilfe anbieten/anfragen: "Wer kann mir bei Analysis II helfen?"
- [ ] Moderation: Melden-Funktion, Community-Regeln
- [ ] Ende-zu-Ende-Verschlüsselung für Direktnachrichten (langfristig)

### 16. Semetra Marketplace
Studierende kaufen und verkaufen studienrelevante Materialien untereinander.

- [ ] Inserate erstellen: Titel, Beschreibung, Fotos, Preis, Zustand, Kategorie
- [ ] Kategorien: Lehrbücher, Skripte, Taschenrechner, Elektronik, Sonstiges
- [ ] Filter: nach FH, Studiengang, Modul, Preis, Zustand
- [ ] Standort-basiert: Anzeigen nach Region/FH-Standort filtern
- [ ] In-App Nachrichten für Käufer/Verkäufer Kommunikation
- [ ] Bewertungssystem für Verkäufer (Vertrauen aufbauen)
- [ ] "Verschenken"-Option für kostenlose Materialien
- [ ] Semetra nimmt keine Provision (Differenzierung zu Tutti/Ricardo)
- [ ] Verknüpfung mit Modulen: "Empfohlene Bücher für Analysis II"
- [ ] Alumni können nach dem Studium weiter verkaufen (Retention über Abschluss hinaus)

---

## ✅ Erledigt

### Infrastruktur
- [x] Website online (semetra.ch via Cloudflare Pages)
- [x] www.semetra.ch aktiviert
- [x] Stripe-Integration (Monatlich, Halbjährlich, Jährlich, Lifetime)
- [x] Supabase Backend mit 23 Migrations
- [x] Authentifizierung (E-Mail, OAuth)
- [x] Row Level Security (RLS)
- [x] Desktop ↔ Web Sync (Echtzeit)
- [x] Pro/Free Feature-Gating

### Web App (23 Seiten — alle funktional)
- [x] Dashboard, Navigator, Module, Aufgaben
- [x] Studienplan, Kalender, Timeline, Stundenplan, Prüfungen
- [x] Notizen, Dokumente, Wissen, Mind Maps, Brainstorming, Karteikarten
- [x] Mathe-Raum (Rechner, Gleichungen, Matrizen, Plotter, Statistik, Einheiten)
- [x] Timer (Pomodoro), Noten & ECTS, Credits
- [x] Settings, About, Upgrade, Studiengänge

### Mehrsprachigkeit (i18n)
- [x] Custom i18n-System (React Context, dynamisches Locale-Loading)
- [x] 6 Sprachen: Deutsch, Englisch, Französisch, Italienisch, Spanisch, Niederländisch
- [x] 1099 Translation-Keys pro Sprache
- [x] Alle 23 Dashboard-Seiten übersetzt
- [x] Sidebar, Navigation, Dialoge, Fehlermeldungen übersetzt
- [x] Upgrade-Seite und ProGate-Modal übersetzt
- [x] Sprachauswahl in Settings mit Profil-Persistierung
- [x] Automatische Spracherkennung basierend auf Profil

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

---

## 📝 Architektur-Notizen

**Tech-Stack:**
- Desktop: Python 3 + PySide6, SQLite lokal
- Web: Next.js 14 + React 18, TypeScript, Tailwind CSS
- Backend: Supabase (PostgreSQL, Auth, Realtime)
- KI: Anthropic Claude Sonnet 4
- Payments: Stripe (4 Tiers + Lifetime)
- Website: Statisches HTML auf Cloudflare Pages
- Hosting: Vercel (Web App)

**Sync:** Bidirektional SQLite ↔ Supabase, offline-first, account-basierte Lizenzierung.

**i18n:** Custom React Context Provider mit dynamischem Locale-Loading, flache JSON-Dateien mit Dot-Notation-Keys, Variable Interpolation, Pipe-separated Arrays.

**Retention-Strategie:**
1. **Daten-Tiefe** — Je mehr Semester, desto wertvoller die Historie (Noten, ECTS, Lernzeit)
2. **Gewohnheit** — Tägliche Strähne + Flashcard-Reviews als Routine
3. **KI-Mehrwert** — Echte Zeitersparnis statt willkürliche Limits
