"""GUI helper functions for module colors, date calculations, and filtering."""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from semetra.gui.constants import MODULE_COLORS

if TYPE_CHECKING:
    from semetra.repo.sqlite_repo import SqliteRepo


def mod_color(mid: int) -> str:
    """Return the hex color for a module ID."""
    return MODULE_COLORS[mid % len(MODULE_COLORS)]


def days_until(s: str) -> Optional[int]:
    """Calculate days from today until a date string (YYYY-MM-DD format).

    Returns None if the date cannot be parsed or is empty.
    """
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
        return (d - date.today()).days
    except Exception:
        return None


def exam_priority(exam_date_str: Optional[str]) -> str:
    """Auto-compute task priority based on days remaining until exam.

    ≤5 days  → Critical
    ≤10 days → High
    ≤15 days → Medium
    otherwise → Low
    """
    d = days_until(exam_date_str)
    if d is None or d < 0:
        return "Low"
    if d <= 5:
        return "Critical"
    if d <= 10:
        return "High"
    if d <= 15:
        return "Medium"
    return "Low"


def fmt_hms(secs: int) -> str:
    """Format seconds as HH:MM:SS."""
    h, r = divmod(abs(secs), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _active_sem_filter(repo: SqliteRepo) -> str:
    """Return the currently selected semester filter value, or '' for all."""
    return (repo.get_setting("filter_semester") or "").strip()


def _filter_mods_by_sem(modules, sem: str) -> list:
    """Filter a list of module rows to those matching *sem*. '' = show all."""
    if not sem:
        return list(modules)
    return [m for m in modules if str(m["semester"] or "").strip() == sem]
