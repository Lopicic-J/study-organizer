from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Module:
    id: int
    code: str
    title: str
    due_iso: str | None = None


@dataclass(frozen=True)
class Task:
    id: int
    module_id: int
    title: str
    due_iso: str | None
    priority: str
    status: str
    parent_id: Optional[int] = None
    notes: str | None = None


@dataclass(frozen=True)
class Event:
    id: int
    title: str
    start_date_iso: str
    end_date_iso: str | None
    start_time: str | None
    end_time: str | None
    kind: str
    module_id: int | None
    task_id: int | None
    notes: str | None
