from __future__ import annotations

import re
from datetime import date


def validate_free_code(value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError("Code is required.")
    return v


def validate_iso_date(value: str) -> str:
    v = (value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError("Date must be ISO format YYYY-MM-DD.")
    y, m, d = (int(x) for x in v.split("-"))
    date(y, m, d)  # validation
    return v


def validate_hhmm(value: str) -> str:
    v = (value or "").strip()
    if not re.fullmatch(r"\d{2}:\d{2}", v):
        raise ValueError("Time must be HH:MM.")
    hh, mm = (int(x) for x in v.split(":"))
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        raise ValueError("Time must be valid HH:MM.")
    return v
