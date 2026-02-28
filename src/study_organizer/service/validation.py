from __future__ import annotations

import re
from datetime import date

from study_organizer.service.errors import ValidationError


_MODULE_RE = re.compile(r"^[A-Z]{2,10}\d{1,4}$")  # e.g. SE101, CS50


def validate_module_code(code: str) -> str:
    c = code.strip().upper()
    if not _MODULE_RE.match(c):
        raise ValidationError(
            "Invalid module code. Use format like SE101, CS50 (2-10 letters + 1-4 digits)."
        )
    return c


def validate_title(title: str) -> str:
    t = title.strip()
    if len(t) < 2:
        raise ValidationError("Title too short.")
    return t


def validate_iso_date(value: str) -> str:
    v = value.strip()
    try:
        date.fromisoformat(v)  # raises ValueError if invalid
    except ValueError as e:
        raise ValidationError("Invalid date. Use ISO format YYYY-MM-DD.") from e
    return v
