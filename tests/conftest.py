"""
pytest fixtures fuer tests/test_repo_sqlite.py.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from semetra.repo.sqlite_repo import SqliteRepo


@pytest.fixture(scope="session")
def repo():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    r = SqliteRepo(db_path=f.name)
    yield r
    try:
        os.unlink(f.name)
    except OSError:
        pass


@pytest.fixture(scope="session")
def mid(repo: SqliteRepo) -> int:
    return repo.add_module(
        {"name": "Mathematik", "semester": "1", "ects": 4, "status": "active"}
    )


@pytest.fixture(scope="session")
def tid(repo: SqliteRepo, mid: int) -> int:
    return repo.add_task(mid, "Aufgabe 1", priority="High", due_date="2026-05-01")
