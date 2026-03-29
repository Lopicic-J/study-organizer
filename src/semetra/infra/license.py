"""
license.py — Lizenzvalidierung für Semetra Pro.

Unterstützte Lizenz-Formate:
  1. SOAPP-Code (primär, automatisch nach Stripe-Kauf per E-Mail):
       SOAPP-XXXXXX-YY
       → lokale HMAC-Prüfsumme + Supabase-Einmal-Aktivierung
  2. Gumroad UUID (Legacy — bestehende Kunden vor Stripe-Migration):
       XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX
       → wird via Gumroad-API verifiziert (online) oder im Grace-Mode erlaubt

Supabase (SOAPP-Codes):
  Tabelle "license_codes": id, code, used, used_at, machine_id, created_at
  → Row wird beim Kauf via Stripe-Webhook eingetragen (stripe-webhook Edge Function)

Stripe Payment Links (werden in der App und auf der Website verwendet):
  → Produkte auf dashboard.stripe.com anlegen, dann STRIPE_*_URL unten ersetzen.
"""

from __future__ import annotations

import hmac
import hashlib
import hashlib as _hl
import secrets
import re
import os
import platform
from typing import Optional

# ─── Stripe Payment Links ────────────────────────────────────────────────────
# Nach dem Anlegen der Produkte in dashboard.stripe.com die Links hier eintragen.
# Format: https://buy.stripe.com/XXXXXXXXXXXXXXXX
STRIPE_MONTHLY_URL   = "https://buy.stripe.com/14A3cxbsw2Oo7ui9arfYY01"
STRIPE_HALFYEAR_URL  = "https://buy.stripe.com/dRmdRb548agQdSGcmDfYY00"
STRIPE_YEARLY_URL    = "https://buy.stripe.com/7sY5kFfIM9cM9Cq5YffYY02"

# ─── Gumroad (Legacy — nur für bestehende Kunden mit alten UUID-Codes) ────────
GUMROAD_PRODUCT_PERMALINK = "semetra-pro"

# ─── SOAPP / Stripe Secret ───────────────────────────────────────────────────
# Wird zur Laufzeit aus Umgebungsvariable oder lokaler .env geladen.
# Lokal: .env Datei mit SOAPP_HMAC_SECRET=... (nie ins Repo!)
_SECRET_STR = os.getenv("SOAPP_HMAC_SECRET", "")
_SECRET = _SECRET_STR.encode() if _SECRET_STR else b""

# ─── Supabase (nur für Online-Aktivierung) ───────────────────────────────────
# Lokal: .env Datei mit SOAPP_SB_URL und SOAPP_SB_KEY (nie ins Repo!)
SUPABASE_URL = os.getenv("SOAPP_SB_URL", "")
SUPABASE_KEY = os.getenv("SOAPP_SB_KEY", "")
ONLINE_CHECK_ENABLED = bool(SUPABASE_URL and SUPABASE_KEY)

# ─────────────────────────────────────────────────────────────────────────────

PRO_FEATURES = {
    "auto_studienplan":  "Automatische Studienplan-Generierung",
    "ki_coach":          "KI-Studien-Coach",
    "semester_updates":  "Semester-Updates & neue FH-Pläne",
    "lernplan_gen":      "Lernplan-Generator",
    "web_import":        "Web Import (Hochschul-Scraper)",
}

# Aliases für Rückwärtskompatibilität (gui.py importiert diese Namen)
GUMROAD_MONTHLY_URL    = STRIPE_MONTHLY_URL
GUMROAD_HALFYEAR_URL   = STRIPE_HALFYEAR_URL
GUMROAD_YEARLY_URL     = STRIPE_YEARLY_URL

# Regex für beide Code-Formate
_GUMROAD_RE = re.compile(
    r'^[0-9A-F]{8}-[0-9A-F]{8}-[0-9A-F]{8}-[0-9A-F]{8}$', re.IGNORECASE
)
_SOAPP_RE = re.compile(r'^SOAPP-([0-9A-F]{6})-([0-9A-F]{2})$', re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
#  Format-Erkennung
# ─────────────────────────────────────────────────────────────────────────────

def _is_gumroad_format(code: str) -> bool:
    """True wenn der Code ein Gumroad UUID-Key ist."""
    return bool(_GUMROAD_RE.match(code.strip()))


def _is_soapp_format(code: str) -> bool:
    """True wenn der Code ein gültiger SOAPP-Code mit korrekter Prüfsumme ist."""
    m = _SOAPP_RE.match(code.strip().upper())
    if not m:
        return False
    payload, cs = m.group(1), m.group(2)
    mac = hmac.new(_SECRET, payload.upper().encode(), hashlib.sha256)
    expected = mac.hexdigest()[:2].upper()
    return hmac.compare_digest(expected, cs.upper())


def _is_any_valid_format(code: str) -> bool:
    return _is_gumroad_format(code) or _is_soapp_format(code)


# ─────────────────────────────────────────────────────────────────────────────
#  Gumroad API-Validierung
# ─────────────────────────────────────────────────────────────────────────────

def _verify_gumroad(code: str) -> tuple[bool, str]:
    """
    Prüft einen Gumroad Lizenzcode via Gumroad API.
    Returns: (success: bool, message: str)
    Grace-Mode bei Netzwerkfehler (offline → erlauben).
    """
    try:
        import urllib.request
        import urllib.parse
        import json

        data = urllib.parse.urlencode({
            "product_permalink": GUMROAD_PRODUCT_PERMALINK,
            "license_key": code.strip(),
            "increment_uses_count": "false",
        }).encode()

        req = urllib.request.Request(
            "https://api.gumroad.com/v2/licenses/verify",
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())

        if not result.get("success"):
            return False, "Lizenzcode ungültig oder nicht gefunden."

        purchase = result.get("purchase", {})
        if purchase.get("refunded"):
            return False, "Dieser Kauf wurde erstattet — Code ungültig."
        if purchase.get("chargebacked"):
            return False, "Dieser Kauf wurde zurückgebucht — Code ungültig."
        if purchase.get("disputed") and not purchase.get("dispute_won"):
            return False, "Dieser Kauf ist gesperrt — Code ungültig."

        return True, "activated"

    except Exception as exc:
        # Netzwerkfehler → Grace-Mode (offline erlauben)
        return True, f"offline:{exc}"


# ─────────────────────────────────────────────────────────────────────────────
#  Machine-ID (anonymisiert)
# ─────────────────────────────────────────────────────────────────────────────

def _machine_id() -> str:
    raw = f"{platform.node()}-{platform.machine()}-{platform.system()}"
    return _hl.sha256(raw.encode()).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────────────
#  Supabase (Legacy SOAPP-Codes)
# ─────────────────────────────────────────────────────────────────────────────

def _supabase_check_and_claim(code: str) -> tuple[bool, str]:
    """
    Prüft in Supabase ob ein SOAPP-Code ungenutzt ist und markiert ihn.
    Returns: (success: bool, message: str)
    """
    if not ONLINE_CHECK_ENABLED:
        return True, "offline"

    try:
        import urllib.request
        import json

        code_upper = code.strip().upper()
        mid = _machine_id()

        auth_headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
            "sb-anon-key": SUPABASE_KEY,
        }
        url = (
            f"{SUPABASE_URL}/rest/v1/license_codes"
            f"?code=eq.{code_upper}&select=id,used,machine_id"
        )
        req = urllib.request.Request(url, headers=auth_headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            rows = json.loads(resp.read())

        if not rows:
            return False, "Code nicht in der Datenbank gefunden."

        row = rows[0]
        if row.get("used"):
            if (row.get("machine_id") or "") == mid:
                return True, "reactivation"
            return False, "Dieser Code wurde bereits auf einem anderen Gerät aktiviert."

        import datetime
        patch_url = f"{SUPABASE_URL}/rest/v1/license_codes?code=eq.{code_upper}"
        payload = json.dumps({
            "used": True,
            "used_at": datetime.datetime.utcnow().isoformat() + "Z",
            "machine_id": mid,
        }).encode()
        patch_req = urllib.request.Request(
            patch_url, data=payload, method="PATCH",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "sb-anon-key": SUPABASE_KEY,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
        )
        with urllib.request.urlopen(patch_req, timeout=8):
            pass

        return True, "activated"

    except Exception as exc:
        return True, f"offline:{exc}"


# ─────────────────────────────────────────────────────────────────────────────
#  Legacy SOAPP Codegenerierung (für manuelle Ausgabe)
# ─────────────────────────────────────────────────────────────────────────────

def generate_code() -> str:
    payload = secrets.token_hex(3).upper()
    mac = hmac.new(_SECRET, payload.encode(), hashlib.sha256)
    cs = mac.hexdigest()[:2].upper()
    return f"SOAPP-{payload}-{cs}"


# ─────────────────────────────────────────────────────────────────────────────
#  LicenseManager
# ─────────────────────────────────────────────────────────────────────────────

class LicenseManager:
    """
    Hochlevel-API für Lizenzprüfung und -aktivierung.
    Unterstützt Gumroad UUID-Keys (primär) und SOAPP Legacy-Codes.
    """

    _SETTING_KEY = "pro_license_code"

    def __init__(self, repo):
        self.repo = repo
        self._cached: Optional[bool] = None

    def is_pro(self) -> bool:
        """True wenn eine gültige Pro-Lizenz aktiviert ist."""
        if self._cached is None:
            code = self.repo.get_setting(self._SETTING_KEY) or ""
            self._cached = _is_any_valid_format(code)
        return self._cached

    def activate(self, code: str) -> tuple[bool, str]:
        """
        Versucht einen Lizenzcode zu aktivieren.
        Unterstützt Gumroad UUID-Keys und SOAPP Legacy-Codes.

        Returns: (success: bool, message: str)
          "activated"       → erfolgreich aktiviert
          "reactivation"    → gleiche Maschine, bereits aktiviert (SOAPP)
          "offline:..."     → offline aktiviert (Grace-Mode)
          Fehlermeldung     → bei Misserfolg
        """
        code = code.strip()

        if _is_gumroad_format(code):
            # ── Gumroad UUID-Key ──────────────────────────────────────────
            ok, msg = _verify_gumroad(code)
            if not ok:
                return False, msg
            self.repo.set_setting(self._SETTING_KEY, code.upper())
            self._cached = True
            return True, msg

        else:
            # ── Legacy SOAPP-Code ─────────────────────────────────────────
            code_upper = code.upper()
            if not _is_soapp_format(code_upper):
                return False, "Ungültiges Code-Format. Bitte den Lizenzcode aus der Kaufbestätigung eingeben."
            ok, msg = _supabase_check_and_claim(code_upper)
            if not ok:
                return False, msg
            self.repo.set_setting(self._SETTING_KEY, code_upper)
            self._cached = True
            return True, msg

    def deactivate(self) -> None:
        self.repo.set_setting(self._SETTING_KEY, "")
        self._cached = False

    def current_code(self) -> str:
        return self.repo.get_setting(self._SETTING_KEY) or ""
