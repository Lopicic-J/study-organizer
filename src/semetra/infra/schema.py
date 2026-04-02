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
        code TEXT DEFAULT '',
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
        notes_link TEXT DEFAULT '',
        module_type TEXT NOT NULL DEFAULT 'pflicht',
        in_plan     INTEGER NOT NULL DEFAULT 1
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
    """
    CREATE TABLE IF NOT EXISTS module_scraped_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        data_type TEXT NOT NULL,   -- 'objective' | 'content_section' | 'assessment'
        title TEXT NOT NULL,       -- section title or assessment type
        body TEXT DEFAULT '',      -- sub-items as JSON array (for content_section) or details text
        weight REAL DEFAULT 0.0,   -- assessment weight in %
        sort_order INTEGER DEFAULT 0,
        FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS task_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        kind TEXT NOT NULL DEFAULT 'link',   -- 'link' | 'file'
        label TEXT NOT NULL DEFAULT '',
        url TEXT NOT NULL DEFAULT '',         -- URL or local file path
        file_type TEXT DEFAULT '',            -- pdf, docx, xlsx, png, etc.
        file_size INTEGER DEFAULT 0,         -- bytes (for files)
        created_at TEXT NOT NULL,
        FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS stundenplan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day_of_week INTEGER NOT NULL,   -- 0=Montag … 6=Sonntag
        time_from TEXT NOT NULL,        -- "08:00"
        time_to TEXT NOT NULL,          -- "10:00"
        subject TEXT NOT NULL DEFAULT '',
        room TEXT DEFAULT '',
        lecturer TEXT DEFAULT '',
        color TEXT DEFAULT '#7C3AED',
        module_id INTEGER DEFAULT NULL,
        notes TEXT DEFAULT '',
        FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE SET NULL
    );
    """,
]


def ensure_schema(conn) -> None:
    cur = conn.cursor()
    for stmt in DDL:
        cur.execute(stmt)

    # Migration: add columns / tables to existing databases
    tables = {r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    # Add columns to modules if they don't exist yet
    existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(modules)").fetchall()}
    if "code" not in existing_cols:
        cur.execute("ALTER TABLE modules ADD COLUMN code TEXT DEFAULT ''")
    if "module_type" not in existing_cols:
        cur.execute("ALTER TABLE modules ADD COLUMN module_type TEXT NOT NULL DEFAULT 'pflicht'")
    if "in_plan" not in existing_cols:
        cur.execute("ALTER TABLE modules ADD COLUMN in_plan INTEGER NOT NULL DEFAULT 1")
    if "target_grade" not in existing_cols:
        cur.execute("ALTER TABLE modules ADD COLUMN target_grade REAL DEFAULT NULL")

    # Add grade_mode column to grades (backward compatible migration)
    grades_cols = {r[1] for r in cur.execute("PRAGMA table_info(grades)").fetchall()}
    if "grade_mode" not in grades_cols:
        cur.execute("ALTER TABLE grades ADD COLUMN grade_mode TEXT NOT NULL DEFAULT 'points'")

    # Add checked column to module_scraped_data for exam-prep checklists
    scraped_cols = {r[1] for r in cur.execute("PRAGMA table_info(module_scraped_data)").fetchall()}
    if "checked" not in scraped_cols:
        cur.execute("ALTER TABLE module_scraped_data ADD COLUMN checked INTEGER NOT NULL DEFAULT 0")

    # Add task_id and last_reviewed to topics
    topics_cols = {r[1] for r in cur.execute("PRAGMA table_info(topics)").fetchall()}
    if "task_id" not in topics_cols:
        cur.execute("ALTER TABLE topics ADD COLUMN task_id INTEGER DEFAULT NULL")
    if "last_reviewed" not in topics_cols:
        cur.execute("ALTER TABLE topics ADD COLUMN last_reviewed TEXT DEFAULT ''")
    # SM-2 Spaced Repetition fields
    if "sr_easiness" not in topics_cols:
        cur.execute("ALTER TABLE topics ADD COLUMN sr_easiness REAL DEFAULT 2.5")
    if "sr_interval" not in topics_cols:
        cur.execute("ALTER TABLE topics ADD COLUMN sr_interval INTEGER DEFAULT 0")
    if "sr_repetitions" not in topics_cols:
        cur.execute("ALTER TABLE topics ADD COLUMN sr_repetitions INTEGER DEFAULT 0")
    if "sr_next_review" not in topics_cols:
        cur.execute("ALTER TABLE topics ADD COLUMN sr_next_review TEXT DEFAULT ''")

    # Migration: fix modules where semester was accidentally set to a PDF validity tag
    # (e.g. "FS26", "HS25/26") instead of a study-semester number.
    # Those values are never purely numeric, so we blank them out.
    cur.execute("""
        UPDATE modules
        SET semester = ''
        WHERE semester != ''
          AND CAST(semester AS INTEGER) = 0
          AND semester NOT IN ('0')
    """)

    # Migration: ensure task_attachments table exists
    if "task_attachments" not in tables:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                kind TEXT NOT NULL DEFAULT 'link',
                label TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                file_type TEXT DEFAULT '',
                file_size INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)
        tables.add("task_attachments")

    # Migration: ensure stundenplan table exists (added in v2.1)
    if "stundenplan" not in tables:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stundenplan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_of_week INTEGER NOT NULL,
                time_from TEXT NOT NULL,
                time_to TEXT NOT NULL,
                subject TEXT NOT NULL DEFAULT '',
                room TEXT DEFAULT '',
                lecturer TEXT DEFAULT '',
                color TEXT DEFAULT '#7C3AED',
                module_id INTEGER DEFAULT NULL,
                notes TEXT DEFAULT '',
                FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE SET NULL
            )
        """)
        tables.add("stundenplan")

    if "module_scraped_data" not in tables:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS module_scraped_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL,
                data_type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT DEFAULT '',
                weight REAL DEFAULT 0.0,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
            )
        """)
        # Refresh table set after creating it
        tables.add("module_scraped_data")

    # Migration: merge duplicate modules where a newer module's code equals an older
    # module's name.  Example: scraper created "Development Operations" code="DevOps"
    # but user already had module "DevOps" — consolidate them.
    dup_rows = cur.execute("""
        SELECT d.id AS dup_id, d.code AS dup_code, o.id AS orig_id
        FROM modules d
        JOIN modules o ON LOWER(d.code) = LOWER(o.name)
        WHERE d.id != o.id AND d.code != ''
          AND d.id > o.id
    """).fetchall()
    for dup_id, dup_code, orig_id in dup_rows:
        # Move scraped data: remove existing for orig, transfer from dup
        cur.execute("DELETE FROM module_scraped_data WHERE module_id=?", (orig_id,))
        cur.execute("UPDATE module_scraped_data SET module_id=? WHERE module_id=?",
                    (orig_id, dup_id))
        # Store code on original if it didn't have one
        cur.execute("UPDATE modules SET code=? WHERE id=? AND (code='' OR code IS NULL)",
                    (dup_code, orig_id))
        # Cascade delete will clean up tasks/grades/etc of the duplicate
        cur.execute("DELETE FROM modules WHERE id=?", (dup_id,))

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
