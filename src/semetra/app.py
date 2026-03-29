from __future__ import annotations

from semetra.repo.sqlite_repo import SqliteRepo


def build_repo(db_path: str = "study.db") -> SqliteRepo:
    return SqliteRepo(db_path=db_path)
