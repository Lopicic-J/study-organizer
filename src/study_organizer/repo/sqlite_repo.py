from __future__ import annotations

import sqlite3
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from study_organizer.infra.db import connect


class SqliteRepo:
    def __init__(self, db_path: str = "study.db"):
        self.db_path = db_path
        self.conn = connect(db_path)

    # ---- settings
    def get_setting(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO app_settings(key,value) VALUES(?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )
        self.conn.commit()

    def hours_per_ects(self) -> int:
        v = self.get_setting("hours_per_ects") or "25"
        try:
            return max(1, int(float(v)))
        except Exception:
            return 25

    # ---- modules
    def add_module(self, data: Dict[str, Any]) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO modules(
                name, semester, ects, lecturer, link, status, exam_date, weighting,
                github_link, sharepoint_link, literature_links, notes_link
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                data["name"],
                data["semester"],
                float(data.get("ects", 0)),
                data.get("lecturer", ""),
                data.get("link", ""),
                data.get("status", "planned"),
                data.get("exam_date", ""),
                float(data.get("weighting", 1.0)),
                data.get("github_link", ""),
                data.get("sharepoint_link", ""),
                data.get("literature_links", ""),
                data.get("notes_link", ""),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_module(self, module_id: int, **fields: Any) -> None:
        if not fields:
            return
        keys = list(fields.keys())
        vals = [fields[k] for k in keys]
        set_clause = ", ".join([f"{k}=?" for k in keys])
        self.conn.execute(f"UPDATE modules SET {set_clause} WHERE id=?", (*vals, module_id))
        self.conn.commit()

    def delete_module(self, module_id: int) -> None:
        self.conn.execute("DELETE FROM modules WHERE id=?", (module_id,))
        self.conn.commit()

    def list_modules(self, status: str = "all") -> List[sqlite3.Row]:
        if status == "all":
            return list(self.conn.execute("SELECT * FROM modules ORDER BY semester, name"))
        return list(self.conn.execute("SELECT * FROM modules WHERE status=? ORDER BY semester, name", (status,)))

    def get_module(self, module_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM modules WHERE id=?", (module_id,)).fetchone()

    # ---- tasks
    def add_task(self, module_id: int, title: str, priority: str = "Medium",
                 status: str = "Open", due_date: str = "", notes: str = "") -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO tasks(module_id,title,priority,status,due_date,notes,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (module_id, title, priority, status, due_date, notes, now, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_task(self, task_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        keys = list(fields.keys())
        vals = [fields[k] for k in keys]
        set_clause = ", ".join([f"{k}=?" for k in keys])
        self.conn.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", (*vals, task_id))
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()

    def get_task(self, task_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()

    def list_tasks(self, module_id: Optional[int] = None,
                   status: str = "all", priority: str = "all") -> List[sqlite3.Row]:
        q = "SELECT t.*, m.name as module_name, m.semester as semester FROM tasks t JOIN modules m ON m.id=t.module_id"
        where: List[str] = []
        params: List[Any] = []

        if module_id is not None:
            where.append("t.module_id=?")
            params.append(module_id)
        if status != "all":
            where.append("t.status=?")
            params.append(status)
        if priority != "all":
            where.append("t.priority=?")
            params.append(priority)

        if where:
            q += " WHERE " + " AND ".join(where)

        q += """
            ORDER BY
              CASE t.status WHEN 'Open' THEN 0 WHEN 'In Progress' THEN 1 ELSE 2 END,
              CASE t.priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
              COALESCE(NULLIF(t.due_date,''),'9999-12-31') ASC,
              t.id DESC
        """
        return list(self.conn.execute(q, tuple(params)))

    # ---- events
    def add_event(self, data: Dict[str, Any]) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO events(module_id,title,kind,start_date,end_date,start_time,end_time,recurrence,recurrence_until,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                data.get("module_id"),
                data["title"],
                data.get("kind", "custom"),
                data["start_date"],
                data["end_date"],
                data.get("start_time", ""),
                data.get("end_time", ""),
                data.get("recurrence", "none"),
                data.get("recurrence_until", ""),
                data.get("notes", ""),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def delete_event(self, event_id: int) -> None:
        self.conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        self.conn.commit()

    def list_events(self) -> List[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT e.*, m.name as module_name FROM events e LEFT JOIN modules m ON m.id=e.module_id"
        ))

    # ---- time logs
    def add_time_log(self, module_id: int, start_ts: int, end_ts: int, seconds: int,
                     kind: str = "study", note: str = "") -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO time_logs(module_id,start_ts,end_ts,seconds,kind,note,created_at)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                module_id,
                start_ts,
                end_ts,
                seconds,
                kind,
                note,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_time_logs(self, module_id: Optional[int] = None, since: Optional[int] = None) -> List[sqlite3.Row]:
        q = "SELECT tl.*, m.name as module_name FROM time_logs tl JOIN modules m ON m.id=tl.module_id"
        where: List[str] = []
        params: List[Any] = []
        if module_id is not None:
            where.append("tl.module_id=?")
            params.append(module_id)
        if since is not None:
            where.append("tl.start_ts>=?")
            params.append(since)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY tl.start_ts DESC"
        return list(self.conn.execute(q, tuple(params)))

    # ---- analytics
    def ects_target_hours(self, module_id: int) -> float:
        row = self.get_module(module_id)
        if not row:
            return 0.0
        return float(row["ects"]) * float(self.hours_per_ects())

    def seconds_studied_for_module(self, module_id: int, since_ts: Optional[int] = None) -> int:
        if since_ts is None:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(seconds),0) as s FROM time_logs WHERE module_id=?",
                (module_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(seconds),0) as s FROM time_logs WHERE module_id=? AND start_ts>=?",
                (module_id, since_ts),
            ).fetchone()
        return int(row["s"] if row else 0)

    def seconds_studied_week(self, week_start_date: date) -> int:
        start_ts = int(time.mktime(datetime.combine(week_start_date, datetime.min.time()).timetuple()))
        row = self.conn.execute(
            "SELECT COALESCE(SUM(seconds),0) as s FROM time_logs WHERE start_ts>=?",
            (start_ts,),
        ).fetchone()
        return int(row["s"] if row else 0)

    def upcoming_exams(self, within_days: int = 30) -> List[sqlite3.Row]:
        t = date.today()
        hi = t + timedelta(days=within_days)
        rows = []
        for m in self.list_modules("all"):
            d = _parse_date(m["exam_date"])
            if d and t <= d <= hi:
                rows.append(m)
        rows.sort(key=lambda r: r["exam_date"])
        return rows

    # ---- topics (knowledge map) ----------------------------------------

    def add_topic(self, module_id: int, title: str, knowledge_level: int = 0, notes: str = "") -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO topics(module_id,title,knowledge_level,notes,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (module_id, title, knowledge_level, notes, now, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_topic(self, topic_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        keys = list(fields.keys())
        vals = [fields[k] for k in keys]
        set_clause = ", ".join([f"{k}=?" for k in keys])
        self.conn.execute(f"UPDATE topics SET {set_clause} WHERE id=?", (*vals, topic_id))
        self.conn.commit()

    def delete_topic(self, topic_id: int) -> None:
        self.conn.execute("DELETE FROM topics WHERE id=?", (topic_id,))
        self.conn.commit()

    def list_topics(self, module_id: int) -> List[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM topics WHERE module_id=? ORDER BY title", (module_id,)
        ))

    def knowledge_summary(self, module_id: int) -> Dict[str, int]:
        """Returns count per knowledge level {0:n, 1:n, 2:n, 3:n, 4:n}."""
        rows = self.list_topics(module_id)
        counts: Dict[str, int] = {str(i): 0 for i in range(5)}
        for r in rows:
            level = str(int(r["knowledge_level"]))
            counts[level] = counts.get(level, 0) + 1
        return counts

    # ---- grades --------------------------------------------------------

    def add_grade(self, module_id: int, title: str, grade: float,
                  max_grade: float = 100.0, weight: float = 1.0,
                  date_str: str = "", notes: str = "") -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO grades(module_id,title,grade,max_grade,weight,date,notes,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (module_id, title, grade, max_grade, weight, date_str, notes, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_grade(self, grade_id: int, **fields: Any) -> None:
        if not fields:
            return
        keys = list(fields.keys())
        vals = [fields[k] for k in keys]
        set_clause = ", ".join([f"{k}=?" for k in keys])
        self.conn.execute(f"UPDATE grades SET {set_clause} WHERE id=?", (*vals, grade_id))
        self.conn.commit()

    def delete_grade(self, grade_id: int) -> None:
        self.conn.execute("DELETE FROM grades WHERE id=?", (grade_id,))
        self.conn.commit()

    def list_grades(self, module_id: Optional[int] = None) -> List[sqlite3.Row]:
        if module_id is not None:
            return list(self.conn.execute(
                "SELECT g.*, m.name as module_name FROM grades g JOIN modules m ON m.id=g.module_id WHERE g.module_id=? ORDER BY g.date DESC, g.id DESC",
                (module_id,)
            ))
        return list(self.conn.execute(
            "SELECT g.*, m.name as module_name FROM grades g JOIN modules m ON m.id=g.module_id ORDER BY g.date DESC, g.id DESC"
        ))

    def module_weighted_grade(self, module_id: int) -> Optional[float]:
        """Returns weighted average grade as percentage (0-100), or None if no grades."""
        rows = self.list_grades(module_id)
        if not rows:
            return None
        total_weight = sum(float(r["weight"]) for r in rows)
        if total_weight == 0:
            return None
        weighted_sum = sum(float(r["grade"]) / float(r["max_grade"]) * float(r["weight"]) for r in rows)
        return (weighted_sum / total_weight) * 100.0

    # ---- streak --------------------------------------------------------

    def get_study_streak(self) -> int:
        """Returns current consecutive study days streak."""
        today = date.today()
        streak = 0
        check = today
        for _ in range(365):
            ts_start = int(time.mktime(datetime.combine(check, datetime.min.time()).timetuple()))
            ts_end = int(time.mktime(datetime.combine(check, datetime.max.time()).timetuple()))
            row = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM time_logs WHERE start_ts>=? AND start_ts<=?",
                (ts_start, ts_end)
            ).fetchone()
            if row and row["cnt"] > 0:
                streak += 1
                check -= timedelta(days=1)
            else:
                break
        return streak

    def all_exams(self) -> List[sqlite3.Row]:
        """Returns all modules with an exam date, sorted by exam date."""
        rows = []
        for m in self.list_modules("all"):
            if m["exam_date"]:
                rows.append(m)
        rows.sort(key=lambda r: r["exam_date"])
        return rows


def _parse_date(s: str | None) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None
