import sqlite3

from study_organizer.domain.models import Module
from study_organizer.infra.schema import init_db
from study_organizer.infra.sqlite_repo import SQLiteRepository
from study_organizer.service.errors import ConflictError


def test_add_and_list_module(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    repo = SQLiteRepository(conn)

    repo.add_module(Module(code="SE101", title="Software Engineering"))
    modules = repo.list_modules()

    assert len(modules) == 1
    assert modules[0].code == "SE101"


def test_duplicate_module_raises(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    repo = SQLiteRepository(conn)

    repo.add_module(Module(code="SE101", title="A"))
    try:
        repo.add_module(Module(code="SE101", title="B"))
        assert False, "Expected ConflictError"
    except ConflictError:
        assert True
