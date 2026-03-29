"""
Tests for the validation / service layer.

Runnable without pytest:
    python tests/test_validation.py
Or with pytest:
    pytest tests/test_validation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from semetra.service.validation import (
    validate_free_code,
    validate_iso_date,
    validate_hhmm,
)
from semetra.service.errors import ValidationError

PASS = FAIL = 0


def chk(cond: bool) -> None:
    if not cond:
        raise AssertionError("condition is False")


def T(label: str, fn) -> None:
    global PASS, FAIL
    try:
        fn()
        print(f"  [PASS] {label}")
        PASS += 1
    except Exception as e:
        print(f"  [FAIL] {label}  →  {e}")
        FAIL += 1


def raises(exc_type, fn) -> None:
    try:
        fn()
        raise AssertionError(f"Expected {exc_type.__name__} but nothing was raised")
    except exc_type:
        pass


# ── validate_free_code ────────────────────────────────────────────────────
print("\n=== validate_free_code ===")
T("valid code passes",     lambda: chk(validate_free_code("SE101") == "SE101"))
T("trims whitespace",      lambda: chk(validate_free_code("  BPR ") == "BPR"))
T("empty → ValueError",    lambda: raises(ValueError, lambda: validate_free_code("")))
T("spaces-only → error",   lambda: raises(ValueError, lambda: validate_free_code("   ")))

# ── validate_iso_date ─────────────────────────────────────────────────────
print("\n=== validate_iso_date ===")
T("valid date passes",         lambda: chk(validate_iso_date("2026-03-05") == "2026-03-05"))
T("invalid month → error",     lambda: raises(ValueError, lambda: validate_iso_date("2026-13-01")))
T("invalid day → error",       lambda: raises(ValueError, lambda: validate_iso_date("2026-01-99")))
T("wrong format → error",      lambda: raises(ValueError, lambda: validate_iso_date("05.03.2026")))
T("empty → error",             lambda: raises(ValueError, lambda: validate_iso_date("")))
T("Feb 29 leap year ok",       lambda: chk(validate_iso_date("2024-02-29") == "2024-02-29"))
T("Feb 29 non-leap → error",   lambda: raises(ValueError, lambda: validate_iso_date("2025-02-29")))

# ── validate_hhmm ─────────────────────────────────────────────────────────
print("\n=== validate_hhmm ===")
T("valid time 09:30",     lambda: chk(validate_hhmm("09:30") == "09:30"))
T("valid time 00:00",     lambda: chk(validate_hhmm("00:00") == "00:00"))
T("valid time 23:59",     lambda: chk(validate_hhmm("23:59") == "23:59"))
T("hour > 23 → error",    lambda: raises(ValueError, lambda: validate_hhmm("24:00")))
T("minute > 59 → error",  lambda: raises(ValueError, lambda: validate_hhmm("12:60")))
T("wrong format → error", lambda: raises(ValueError, lambda: validate_hhmm("9:30")))
T("empty → error",        lambda: raises(ValueError, lambda: validate_hhmm("")))

print(f"\n{'='*50}")
print(f"  ERGEBNIS: {PASS} passed  |  {FAIL} failed")
print(f"{'='*50}")

if FAIL:
    sys.exit(1)
