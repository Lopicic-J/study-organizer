from __future__ import annotations

import sqlite3

from study_organizer.domain.models import Deadline, Module
from study_organizer.service.repository import Repository


class SQLiteRepository(Repository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add_module(self, module: Module) -> None:
        self.conn.execute(
            "INSERT INTO modules (code, title) VALUES (?, ?)",
            (module.code.strip(), module.title.strip()),
        )
        self.conn.commit()

    def list_modules(self) -> list[Module]:
        rows = self.conn.execute(
            "SELECT code, title FROM modules ORDER BY code"
        ).fetchall()
        return [Module(code=row["code"], title=row["title"]) for row in rows]

    def add_deadline(self, deadline: Deadline) -> None:
        self.conn.execute(
            "INSERT INTO deadlines (module_code, title, due_date, notes) VALUES (?, ?, ?, ?)",
            (
                deadline.module_code.strip(),
                deadline.title.strip(),
                deadline.due_date.strip(),
                deadline.notes.strip() if deadline.notes else None,
            ),
        )
        self.conn.commit()

    def list_deadlines(self, module_code: str | None = None) -> list[Deadline]:
        if module_code:
            rows = self.conn.execute(
                """
                SELECT module_code, title, due_date, notes
                FROM deadlines
                WHERE module_code = ?
                ORDER BY due_date
                """,
                (module_code.strip(),),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT module_code, title, due_date, notes
                FROM deadlines
                ORDER BY due_date
                """
            ).fetchall()

        return [
            Deadline(
                module_code=row["module_code"],
                title=row["title"],
                due_date=row["due_date"],
                notes=row["notes"],
            )
            for row in rows
        ]
