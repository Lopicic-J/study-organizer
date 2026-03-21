from __future__ import annotations

SCHEMA_VERSION = 1

DDL = [
    """
    PRAGMA foreign_keys = ON;
    """,
    """
    CREATE TABLE IF NOT EXISTS modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        semester TEXT NOT NULL,
        ects REAL NOT NULL DEFAULT 0,
        lecturer TEXT DEFAULT '',
        link TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'planned',
        exam_date TEXT DEFAULT '',
        weighting REAL NOT NULL DEFAULT 1.0,
        github_link TEXT DEFAULT '',
        sharepoint_link TEXT DEFAULT '',
        literature_links TEXT DEFAULT '',
        notes_link TEXT DEFAULT ''
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        priority TEXT NOT NULL DEFAULT 'Medium',
        status TEXT NOT NULL DEFAULT 'Open',
        due_date TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER,
        title TEXT NOT NULL,
        kind TEXT NOT NULL,                 -- 'study_block' | 'custom'
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        start_time TEXT DEFAULT '',
        end_time TEXT DEFAULT '',
        recurrence TEXT DEFAULT 'none',      -- none|daily|weekly
        recurrence_until TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE SET NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS time_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        start_ts INTEGER NOT NULL,
        end_ts INTEGER NOT NULL,
        seconds INTEGER NOT NULL,
        kind TEXT NOT NULL DEFAULT 'study',  -- study|pomodoro
        note TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        knowledge_level INTEGER NOT NULL DEFAULT 0,
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        grade REAL NOT NULL,
        max_grade REAL NOT NULL DEFAULT 100,
        weight REAL NOT NULL DEFAULT 1.0,
        date TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
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
