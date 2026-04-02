# Stripe Setup — Semetra Pro

Komplette Anleitung zur Stripe-Integration. Einmalig ca. 30–45 Minuten.

---

## Übersicht: Was passiert nach dem Kauf

```
Kunde kauft auf semetra.ch
       ↓
Stripe Checkout (hosted, sicher)
       ↓
Stripe feuert Webhook → Supabase Edge Function
       ↓
Edge Function generiert SOAPP-Lizenzcode
       ↓
Code wird in Supabase gespeichert
       ↓
Kunde erhält E-Mail mit Code (automatisch, sofort)
       ↓
Kunde gibt Code in Semetra → Einstellungen → Lizenz ein ✅
```

---

## Schritt 1 — Stripe Account einrichten

1. Gehe zu **[dashboard.stripe.com](https://dashboard.stripe.com)** → Account erstellen
2. **Business-Typ:** Einzelperson / Sole Proprietor
3. **Land:** Schweiz 🇨🇭
4. **Branche:** Software / SaaS
5. Bankdaten hinterlegen (für Auszahlungen)
6. Steuernummer: Falls du MwSt-pflichtig bist, UID eintragen (sonst leer lassen)

> **Tipp:** Aktiviere zuerst den **Testmodus** (Toggle oben links). Erst nach vollständigem Test auf Live schalten.

---

## Schritt 2 — Produkte & Preise erstellen

Gehe zu **Products → + Add product**

### Produkt 1: Semetra Pro Monatlich
| Feld | Wert |
|------|------|
| Name | Semetra Pro |
| Pricing model | Recurring |
| Price | CHF 4.90 |
| Billing period | Monthly |
| Metadata (Key) | `plan` |
| Metadata (Value) | `monthly` |

→ **Save product** → Notiere die **Price ID** (z.B. `price_1ABC...`)

### Produkt 2: Semetra Pro Halbjährlich
| Feld | Wert |
|------|------|
| Name | Semetra Pro (Halbjährlich) |
| Pricing model | Recurring |
| Price | CHF 24.90 |
| Billing period | Every 6 months |
| Metadata `plan` | `halfyear` |

→ **Save** → Price ID notieren

### Produkt 3: Semetra Pro Jährlich
| Feld | Wert |
|------|------|
| Name | Semetra Pro (Jährlich) |
| Pricing model | Recurring |
| Price | CHF 39.90 |
| Billing period | Yearly |
| Metadata `plan` | `yearly` |

→ **Save** → Price ID notieren

---

## Schritt 3 — Payment Links erstellen

Für jedes Produkt: **Payment Links → + New payment link**

1. Wähle das Produkt aus
2. Sammle **E-Mail-Adresse** vom Kunden: ✅ aktivieren (Pflichtfeld)
3. Unter **After payment:** "Don't show confirmation page" ODER eigene Seite (z.B. `https://semetra.ch/#download`)
4. **Metadata** hinzufügen: `plan` = `monthly` (oder `halfyear`, `yearly`)
5. → **Create link**

Du erhältst Links im Format: `https://buy.stripe.com/XXXXXXXXXXXXXXXX`

### Diese Links eintragen in:

**`src/semetra/infra/license.py`** (Zeilen mit `REPLACE_`):
```python
STRIPE_MONTHLY_URL   = "https://buy.stripe.com/DEIN_MONATLICH_LINK"
STRIPE_HALFYEAR_URL  = "https://buy.stripe.com/DEIN_HALBJAHR_LINK"
STRIPE_YEARLY_URL    = "https://buy.stripe.com/DEIN_JAEHRLICH_LINK"
```

**`website/index.html`** — alle `REPLACE_MONTHLY`, `REPLACE_HALFYEAR`, `REPLACE_YEARLY` ersetzen.

---

## Schritt 4 — Resend (E-Mail) einrichten

Resend ist kostenlos für bis zu 3'000 E-Mails/Monat.

1. Gehe zu **[resend.com](https://resend.com)** → Account erstellen
2. **Add Domain** → `semetra.ch` eintragen
3. DNS-Einträge bei Cloudflare hinzufügen (Resend zeigt dir genau welche)
4. Nach Verifizierung: **API Keys → Create API Key**
5. Name: `semetra-webhook`, Permission: `Sending access`
6. **Key kopieren** (wird nur einmal angezeigt!) → `re_XXXXXXXXXX`

---

## Schritt 5 — Supabase Edge Function deployen

### 5a — Neue Spalten in `license_codes` hinzufügen

Führe im Supabase SQL-Editor aus:

```sql
ALTER TABLE license_codes
  ADD COLUMN IF NOT EXISTS customer_email TEXT,
  ADD COLUMN IF NOT EXISTS plan TEXT,
  ADD COLUMN IF NOT EXISTS stripe_session_id TEXT;
```

### 5b — Supabase CLI installieren (einmalig)

```bash
npm install -g supabase
supabase login
```

### 5c — Projekt verlinken

```bash
cd /pfad/zu/semetra
supabase link --project-ref DEIN_SUPABASE_PROJECT_REF
```
(Project Ref findest du in Supabase → Settings → General)

### 5d — Secrets setzen

```bash
supabase secrets set STRIPE_SECRET_KEY=sk_live_DEIN_KEY
supabase secrets set STRIPE_WEBHOOK_SECRET=whsec_WIRD_IN_SCHRITT_6_ERSTELLT
supabase secrets set SUPABASE_URL=https://DEIN_REF.supabase.co
supabase secrets set SUPABASE_SERVICE_KEY=DEIN_SERVICE_ROLE_KEY
supabase secrets set RESEND_API_KEY=re_DEIN_RESEND_KEY
supabase secrets set SOAPP_HMAC_SECRET=DEIN_GEHEIMER_HMAC_KEY
```

> **Service Role Key** findest du in Supabase → Settings → API → `service_role` (NICHT der `anon` key!)

### 5e — Function deployen

```bash
supabase functions deploy stripe-webhook --no-verify-jwt
```

Nach dem Deploy bekommst du die URL:
```
https://DEIN_REF.functions.supabase.co/stripe-webhook
```

→ Diese URL für den nächsten Schritt kopieren.

---

## Schritt 6 — Stripe Webhook einrichten

1. Stripe Dashboard → **Developers → Webhooks → + Add endpoint**
2. **Endpoint URL:** `https://DEIN_REF.functions.supabase.co/stripe-webhook`
3. **Events to send:** Wähle `checkout.session.completed`
4. → **Add endpoint**
5. Auf der Webhook-Detail-Seite: **Signing secret** anzeigen → `whsec_XXXXXXXX`
6. Diesen Secret in Supabase eintragen:

```bash
supabase secrets set STRIPE_WEBHOOK_SECRET=whsec_XXXXXXXX
```

---

## Schritt 7 — Testen

### Im Testmodus:

1. Öffne einen deiner Payment Links (Testmodus-Links zeigen "Test mode" Banner)
2. Zahle mit Testkarte: `4242 4242 4242 4242` · Datum: beliebig in der Zukunft · CVC: `123`
3. Prüfe:
   - Supabase → Table Editor → `license_codes` → neuer Eintrag vorhanden?
   - E-Mail-Postfach: Lizenzcode angekommen?
   - Stripe → Events → `checkout.session.completed` → Status 200?
4. Gib den Code in Semetra ein → Aktivierung erfolgreich?

### Edge Function Logs (bei Problemen):

```bash
supabase functions logs stripe-webhook
```

---

## Schritt 8 — Live schalten

1. Stripe Dashboard → Toggle von **Test** auf **Live**
2. Schritte 2–6 im Live-Modus wiederholen (neue Live-Keys, Live-Webhook)
3. Payment Links aktualisieren in `license.py` und `index.html`
4. Website-ZIP neu bauen und auf Cloudflare Pages hochladen

---

## Schritt 9 — Bestehende Gumroad-Kunden

Kunden mit alten Gumroad-UUID-Codes funktionieren weiterhin — die App validiert sie noch via Gumroad API (Grace-Mode bei Offline). Kein Handlungsbedarf.

---

## Preise (optional anpassen)

Aktuell:
| Plan | Preis | Monatlich effektiv |
|------|-------|--------------------|
| Monatlich | CHF 4.90/Monat | CHF 4.90 |
| Halbjährlich | CHF 24.90/6 Monate | CHF 4.15 |
| Jährlich | CHF 39.90/Jahr | CHF 3.33 |

---

## Wichtige Dateien

| Datei | Zweck |
|-------|-------|
| `supabase/functions/stripe-webhook/index.ts` | Webhook Handler (Code-Generierung + E-Mail) |
| `src/semetra/infra/license.py` | Stripe URLs + Lizenzvalidierung |
| `website/index.html` | Kaufbuttons (REPLACE_* ersetzen) |
| `generate_codes.py` | Manuelle Code-Generierung (Fallback) |

---

## Support

Bei Fragen: E-Mail an sich selbst oder Stripe Support (sehr gut für Indie-Devs).
Stripe Indie Resources: [stripe.com/indie](https://stripe.com/indie)
