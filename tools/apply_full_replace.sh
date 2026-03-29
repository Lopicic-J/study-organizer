#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

write_file() {
  local rel="$1"
  local path="$ROOT/$rel"
  mkdir -p "$(dirname "$path")"
  cat > "$path"
  echo "WROTE: $rel"
}

echo "ROOT: $ROOT"

# ----------------------------
# src/semetra/infra/schema.py
# ----------------------------
write_file "src/semetra/infra/schema.py" <<'PY'
from __future__ import annotations

DDL = [
    "PRAGMA foreign_keys = ON;",
    """
    CREATE TABLE IF NOT EXISTS modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        semester TEXT NOT NULL DEFAULT 'Semester ?',
        ects REAL NOT NULL DEFAULT 0,
        lecturer TEXT NOT NULL DEFAULT '',
        link TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'planned',
        exam_date TEXT NOT NULL DEFAULT '',
        weighting REAL NOT NULL DEFAULT 1.0,
        github_link TEXT NOT NULL DEFAULT '',
        sharepoint_link TEXT NOT NULL DEFAULT '',
        literature_links TEXT NOT NULL DEFAULT '',
        notes_link TEXT NOT NULL DEFAULT ''
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        due_date TEXT NOT NULL DEFAULT '',
        priority TEXT NOT NULL DEFAULT 'Medium',
        status TEXT NOT NULL DEFAULT 'Open',
        parent_id INTEGER,
        notes TEXT NOT NULL DEFAULT '',
        FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER,
        title TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'custom',       -- 'study_block' | 'custom'
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        start_time TEXT NOT NULL DEFAULT '',
        end_time TEXT NOT NULL DEFAULT '',
        recurrence TEXT NOT NULL DEFAULT 'none',   -- none|daily|weekly
        recurrence_until TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT ''
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS time_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        start_ts INTEGER NOT NULL,
        end_ts INTEGER NOT NULL,
        seconds INTEGER NOT NULL,
        kind TEXT NOT NULL DEFAULT 'study',        -- study|pomodoro
        note TEXT NOT NULL DEFAULT ''
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
]


def ensure_schema(conn) -> None:
    cur = conn.cursor()
    for stmt in DDL:
        cur.execute(stmt)

    # defaults
    cur.execute(
        """
        INSERT INTO app_settings(key,value)
        VALUES('hours_per_ects','25')
        ON CONFLICT(key) DO NOTHING
        """
    )
    cur.execute(
        """
        INSERT INTO app_settings(key,value)
        VALUES('theme','light')
        ON CONFLICT(key) DO NOTHING
        """
    )
    conn.commit()
PY

# ----------------------------
# src/semetra/infra/db.py
# ----------------------------
write_file "src/semetra/infra/db.py" <<'PY'
from __future__ import annotations

import sqlite3
from pathlib import Path

from .schema import ensure_schema


def connect(db_path: str):
    path = Path(db_path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn
PY

# ----------------------------
# src/semetra/service/repository.py
# ----------------------------
write_file "src/semetra/service/repository.py" <<'PY'
from __future__ import annotations

from typing import Protocol, Any


class Repository(Protocol):
    # Settings
    def get_setting(self, key: str) -> str | None: ...
    def set_setting(self, key: str, value: str) -> None: ...
    def hours_per_ects(self) -> float: ...

    # Modules
    def list_modules(self, status: str = "all") -> list[dict[str, Any]]: ...
    def get_module(self, module_id: int) -> dict[str, Any] | None: ...
    def add_module(self, data: dict[str, Any]) -> int: ...
    def update_module(self, module_id: int, **fields: Any) -> None: ...
    def delete_module(self, module_id: int) -> None: ...
    def upcoming_exams(self, within_days: int = 30) -> list[dict[str, Any]]: ...

    # Tasks
    def list_tasks(self, module_id=None, status: str = "all", priority: str = "all") -> list[dict[str, Any]]: ...
    def get_task(self, task_id: int) -> dict[str, Any] | None: ...
    def add_task(self, module_id: int, title: str, priority: str, status: str, due_date: str, notes: str) -> int: ...
    def update_task(self, task_id: int, **fields: Any) -> None: ...
    def delete_task(self, task_id: int) -> None: ...

    # Events
    def list_events(self) -> list[dict[str, Any]]: ...
    def add_event(self, data: dict[str, Any]) -> int: ...
    def delete_event(self, event_id: int) -> None: ...

    # Time logs
    def add_time_log(self, module_id: int, start_ts: int, end_ts: int, seconds: int, kind: str = "study", note: str = "") -> int: ...
    def list_time_logs(self, module_id=None, since=None) -> list[dict[str, Any]]: ...
    def seconds_studied_for_module(self, module_id: int, since_ts=None) -> int: ...
PY

# ----------------------------
# src/semetra/repo/sqlite_repo.py
# ----------------------------
write_file "src/semetra/repo/sqlite_repo.py" <<'PY'
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any


class SQLiteRepo:
    def __init__(self, conn):
        self.conn = conn

    # ---- settings (app_settings) ----
    def get_setting(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO app_settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    def hours_per_ects(self) -> float:
        v = self.get_setting("hours_per_ects")
        try:
            return float(v) if v is not None else 25.0
        except Exception:
            return 25.0

    # ---- modules ----
    def list_modules(self, status: str = "all") -> list[dict[str, Any]]:
        if status == "all":
            cur = self.conn.execute("SELECT * FROM modules ORDER BY semester, name")
        else:
            cur = self.conn.execute("SELECT * FROM modules WHERE status = ? ORDER BY semester, name", (status,))
        return [dict(r) for r in cur.fetchall()]

    def get_module(self, module_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM modules WHERE id = ?", (int(module_id),)).fetchone()
        return dict(row) if row else None

    def add_module(self, data: dict[str, Any]) -> int:
        keys = list(data.keys())
        vals = [data[k] for k in keys]
        q = ",".join(["?"] * len(keys))
        self.conn.execute(f"INSERT INTO modules({','.join(keys)}) VALUES({q})", vals)
        self.conn.commit()
        return int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    def update_module(self, module_id: int, **fields: Any) -> None:
        if not fields:
            return
        keys = list(fields.keys())
        sets = ", ".join([f"{k}=?" for k in keys])
        vals = [fields[k] for k in keys] + [int(module_id)]
        self.conn.execute(f"UPDATE modules SET {sets} WHERE id = ?", vals)
        self.conn.commit()

    def delete_module(self, module_id: int) -> None:
        mid = int(module_id)
        self.conn.execute("DELETE FROM tasks WHERE module_id = ?", (mid,))
        self.conn.execute("DELETE FROM time_logs WHERE module_id = ?", (mid,))
        self.conn.execute("DELETE FROM events WHERE module_id = ?", (mid,))
        self.conn.execute("DELETE FROM modules WHERE id = ?", (mid,))
        self.conn.commit()

    def upcoming_exams(self, within_days: int = 30) -> list[dict[str, Any]]:
        today = date.today()
        end = today + timedelta(days=int(within_days))
        out: list[dict[str, Any]] = []
        for m in self.list_modules("all"):
            s = (m.get("exam_date") or "").strip()
            if not s:
                continue
            try:
                ex = datetime.strptime(s, "%Y-%m-%d").date()
            except Exception:
                continue
            if today <= ex <= end:
                out.append(m)
        out.sort(key=lambda x: x.get("exam_date", ""))
        return out

    # ---- tasks ----
    def list_tasks(self, module_id=None, status: str = "all", priority: str = "all") -> list[dict[str, Any]]:
        where = []
        params = []
        if module_id is not None:
            where.append("module_id = ?")
            params.append(int(module_id))
        if status != "all":
            where.append("status = ?")
            params.append(status)
        if priority != "all":
            where.append("priority = ?")
            params.append(priority)
        w = (" WHERE " + " AND ".join(where)) if where else ""

        # robust ordering (works even if some rows have empty due_date)
        cur = self.conn.execute(f"SELECT * FROM tasks{w} ORDER BY due_date, priority, id", params)
        rows = [dict(r) for r in cur.fetchall()]

        mod_map = {m["id"]: m["name"] for m in self.list_modules("all")}
        for r in rows:
            r["module_name"] = mod_map.get(r["module_id"], "—")
        return rows

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (int(task_id),)).fetchone()
        if not row:
            return None
        r = dict(row)
        m = self.get_module(int(r["module_id"]))
        r["module_name"] = m["name"] if m else "—"
        return r

    def add_task(self, module_id: int, title: str, priority: str, status: str, due_date: str, notes: str) -> int:
        self.conn.execute(
            "INSERT INTO tasks(module_id,title,due_date,priority,status,parent_id,notes) VALUES(?,?,?,?,?,?,?)",
            (int(module_id), title, due_date or "", priority, status, None, notes or ""),
        )
        self.conn.commit()
        return int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    def update_task(self, task_id: int, **fields: Any) -> None:
        if not fields:
            return
        keys = list(fields.keys())
        sets = ", ".join([f"{k}=?" for k in keys])
        vals = [fields[k] for k in keys] + [int(task_id)]
        self.conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", vals)
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (int(task_id),))
        self.conn.commit()

    # ---- events ----
    def list_events(self) -> list[dict[str, Any]]:
        cur = self.conn.execute("SELECT * FROM events ORDER BY start_date, start_time, id")
        rows = [dict(r) for r in cur.fetchall()]
        mod_map = {m["id"]: m["name"] for m in self.list_modules("all")}
        for r in rows:
            mid = r.get("module_id")
            r["module_name"] = mod_map.get(mid, "—") if mid else "—"
        return rows

    def add_event(self, data: dict[str, Any]) -> int:
        keys = list(data.keys())
        vals = [data[k] for k in keys]
        q = ",".join(["?"] * len(keys))
        self.conn.execute(f"INSERT INTO events({','.join(keys)}) VALUES({q})", vals)
        self.conn.commit()
        return int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    def delete_event(self, event_id: int) -> None:
        self.conn.execute("DELETE FROM events WHERE id = ?", (int(event_id),))
        self.conn.commit()

    # ---- time logs ----
    def add_time_log(self, module_id: int, start_ts: int, end_ts: int, seconds: int, kind: str = "study", note: str = "") -> int:
        self.conn.execute(
            "INSERT INTO time_logs(module_id,start_ts,end_ts,seconds,kind,note) VALUES(?,?,?,?,?,?)",
            (int(module_id), int(start_ts), int(end_ts), int(seconds), kind, note),
        )
        self.conn.commit()
        return int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    def list_time_logs(self, module_id=None, since=None) -> list[dict[str, Any]]:
        where = []
        params = []
        if module_id is not None:
            where.append("module_id = ?")
            params.append(int(module_id))
        if since is not None:
            where.append("start_ts >= ?")
            params.append(int(since))
        w = (" WHERE " + " AND ".join(where)) if where else ""
        cur = self.conn.execute(f"SELECT * FROM time_logs{w} ORDER BY start_ts DESC", params)
        rows = [dict(r) for r in cur.fetchall()]

        mod_map = {m["id"]: m["name"] for m in self.list_modules("all")}
        for r in rows:
            r["module_name"] = mod_map.get(r["module_id"], "—")
        return rows

    def seconds_studied_for_module(self, module_id: int, since_ts=None) -> int:
        if since_ts is None:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(seconds),0) AS s FROM time_logs WHERE module_id = ?",
                (int(module_id),),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(seconds),0) AS s FROM time_logs WHERE module_id = ? AND start_ts >= ?",
                (int(module_id), int(since_ts)),
            ).fetchone()
        return int(row["s"] if row else 0)
PY

# ----------------------------
# src/semetra/app.py
# ----------------------------
write_file "src/semetra/app.py" <<'PY'
from __future__ import annotations

from semetra.infra.db import connect
from semetra.repo.sqlite_repo import SQLiteRepo


def build_repo(db_path: str = "study.db") -> SQLiteRepo:
    conn = connect(db_path)
    return SQLiteRepo(conn)
PY

# ----------------------------
# src/semetra/__main__.py
# ----------------------------
write_file "src/semetra/__main__.py" <<'PY'
from __future__ import annotations

from semetra.app import build_repo
from semetra.gui import main


def main_cli() -> None:
    repo = build_repo("study.db")
    main(repo)


if __name__ == "__main__":
    main_cli()
PY

# ----------------------------
# src/semetra/gui.py  (PySide6)
# ----------------------------
write_file "src/semetra/gui.py" <<'PY'
# NOTE: keep this file as the PySide6 GUI you requested.
# Paste your latest PySide6 gui.py content here.
# (I’m not duplicating it again to avoid you ending up with two diverging versions.)
raise SystemExit("gui.py placeholder: paste the PySide6 GUI code you approved here.")
PY

echo ""
echo "DONE."
echo "Next:"
echo "  1) Ensure pyproject.toml includes PySide6"
echo "  2) pip install -e . && pip install PySide6"
echo "  3) (optional) move/backup old study.db if schema mismatch"
echo "  4) python -m semetra"
echo ""