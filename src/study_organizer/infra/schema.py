import sqlite3


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS modules (
            code TEXT PRIMARY KEY,
            title TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deadlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (module_code) REFERENCES modules(code) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
