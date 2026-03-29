# Semetra – Produkt-Roadmap

## 🔴 Aktuelle Priorität

### FH-Datenbank befüllen
- [x] **FFHS** – Fernfachhochschule Schweiz ✅
  - Informatik (9 Sem, 180 ECTS, 36 Module)
  - Cyber Security (9 Sem, 180 ECTS, 36 Module)
  - Wirtschaftsinformatik (9 Sem, 180 ECTS, 36 Module)
- [ ] ZHAW – bestehende Einträge mit echten ECTS/Semesterdaten ergänzen
- [ ] FHNW – Informatik, WI
- [ ] BFH – Informatik, BWL
- [ ] OST – Informatik
- [ ] HSLU – Informatik, WI
- [ ] HES-SO – Medieningenieurwesen

---

## 🟡 Nächste Phase

### Gumroad → Stripe Wechsel
- [ ] Stripe-Konto einrichten und Produkte anlegen (Monatlich / Halbjährlich / Jährlich)
- [ ] Neue Zahlungslinks in `infra/license.py` + `gui.py` eintragen
- [ ] Webhook für automatische Lizenzaktivierung (Stripe → Semetra)
- [ ] Gumroad-Links aus App und Website entfernen

---

## 🔵 Mittelfristig

### Web-App (synchronisiert mit Desktop-App)
- [ ] Backend/Sync-Server wählen (Empfehlung: Supabase – kostenlos, Echtzeit-Sync)
- [ ] Authentifizierung (E-Mail / Magic Link)
- [ ] Sync-Protokoll: SQLite lokal ↔ Supabase Cloud
  - Module, Aufgaben, Lernziele, Prüfungen, Noten
- [ ] Web-Frontend (React / Next.js)
- [ ] Offline-first: App funktioniert ohne Internet, synct wenn online

---

## 🟢 Langfristig

### Mobile App (iOS & Android)
- [ ] Framework-Entscheidung (Empfehlung: React Native oder Flutter)
- [ ] Gemeinsame Sync-Schicht mit Web-App (Supabase)
- [ ] Feature-Parität: Dashboard, Aufgaben, Module, Timer, Prüfungen
- [ ] App Store / Play Store Veröffentlichung
- [ ] Push-Notifications (Prüfungserinnerungen, Deadlines)

---

## ✅ Erledigt
- [x] Website online (semetra.ch via Cloudflare Pages)
- [x] www.semetra.ch aktiviert (Mobile-Fix)
- [x] App-Icon erstellt (.ico)
- [x] Dashboard-Crash behoben (mod_grid takeAt)
- [x] Dashboard Scroll-Wrapper (kein Überlappen mehr)
- [x] SettingsPage + TasksPage Scroll-Wrapper
- [x] Pro-Button Gumroad-Redirect repariert
- [x] Web-Scraping Button entfernt (Rechtsschutz)
- [x] FH-Datenbank Dialog gebaut (offline, kein Scraping)
- [x] Modul-Import → Studienplan automatische Synchronisation
- [x] Professioneller Installer (Inno Setup)
- [x] Windows Defender Ausnahme-Anleitung
- [x] version_info.txt für AV-Erkennung

---

## 📝 Notizen

**Sync-Architektur (Web + Mobile + Desktop):**
Supabase eignet sich ideal: PostgreSQL-Datenbank, Echtzeit-Websockets,
kostenloser Free-Tier bis 500MB. Die Desktop-App hält SQLite lokal,
synct Änderungen via REST/Realtime-API. Web und Mobile greifen direkt
auf Supabase zu. Stripe-Lizenzprüfung läuft serverseitig.

**Stripe vs. Gumroad:**
Stripe hat tiefere Gebühren (2.9% + 30¢ vs. ~10% bei Gumroad),
bessere Webhook-Integration für automatische Lizenzschlüssel-Vergabe,
und einen professionelleren Eindruck bei Schweizer Kunden.
