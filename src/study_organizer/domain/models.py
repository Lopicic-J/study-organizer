from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Module:
    code: str  # e.g. "SE101"
    title: str


@dataclass(frozen=True)
class Deadline:
    module_code: str
    title: str
    due_date: str  # ISO date: YYYY-MM-DD
    notes: str | None = None
