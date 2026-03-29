from __future__ import annotations

import json
import sqlite3
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from semetra.infra.db import connect


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
                name, code, semester, ects, lecturer, link, status, exam_date, weighting,
                github_link, sharepoint_link, literature_links, notes_link, module_type, in_plan
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                data["name"],
                data.get("code", ""),
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
                data.get("module_type", "pflicht"),
                int(data.get("in_plan", 1)),
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

    def add_topic(self, module_id: int, title: str, knowledge_level: int = 0,
                  notes: str = "", task_id: Optional[int] = None) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO topics(module_id,title,knowledge_level,notes,task_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (module_id, title, knowledge_level, notes, task_id, now, now),
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
            """
            SELECT t.*, tk.title AS task_title
            FROM topics t
            LEFT JOIN tasks tk ON tk.id = t.task_id
            WHERE t.module_id = ?
            ORDER BY t.title
            """,
            (module_id,)
        ))

    def knowledge_summary(self, module_id: int) -> Dict[str, int]:
        """Returns count per knowledge level {0:n, 1:n, 2:n, 3:n, 4:n}."""
        rows = self.list_topics(module_id)
        counts: Dict[str, int] = {str(i): 0 for i in range(5)}
        for r in rows:
            level = str(int(r["knowledge_level"]))
            counts[level] = counts.get(level, 0) + 1
        return counts

    def exam_readiness_score(self, module_id: int) -> Dict[str, Any]:
        """Calculates a 0-100 exam readiness score with component breakdown.

        Components (only included when data exists):
          - topic_score  (weight 0.50): avg(knowledge_level) / 5 * 100
          - hours_score  (weight 0.30): studied_seconds / target_seconds * 100 (capped 100)
          - task_score   (weight 0.20): done_tasks / total_tasks * 100

        Returns a dict with keys:
          total          int        0-100 overall score
          has_data       bool       False if no component had any data
          topic_score    int|None   component score or None if no topics
          hours_score    int|None   component score or None if no time logs
          task_score     int|None   component score or None if no tasks
          topic_count    int        number of topics tracked
          hours_studied  float      total hours tracked
          hours_target   float      target hours (ECTS * hours_per_ects)
          tasks_done     int
          tasks_total    int
          days_until_exam int|None  positive = future, negative = past, None = no date
          exam_date_str  str        raw exam_date value
        """
        # ── Component 1: Topic knowledge ──────────────────────────────────
        topics = self.list_topics(module_id)
        topic_count = len(topics)
        if topic_count > 0:
            avg_level = sum(int(t["knowledge_level"]) for t in topics) / topic_count
            topic_score: Optional[float] = (avg_level / 5.0) * 100.0
        else:
            topic_score = None

        # ── Component 2: Study hours vs target ────────────────────────────
        target_secs = self.ects_target_hours(module_id) * 3600.0
        studied_secs = float(self.seconds_studied_for_module(module_id))
        hours_studied = studied_secs / 3600.0
        hours_target = target_secs / 3600.0
        if studied_secs > 0 and target_secs > 0:
            hours_score: Optional[float] = min(100.0, (studied_secs / target_secs) * 100.0)
        else:
            hours_score = None

        # ── Component 3: Task completion ──────────────────────────────────
        tasks = self.list_tasks(module_id=module_id)
        tasks_total = len(tasks)
        tasks_done = sum(1 for t in tasks if t["status"] == "Done")
        if tasks_total > 0:
            task_score: Optional[float] = (tasks_done / tasks_total) * 100.0
        else:
            task_score = None

        # ── Weighted average (only count present components) ──────────────
        pairs: list = []
        if topic_score is not None:
            pairs.append((topic_score, 0.50))
        if hours_score is not None:
            pairs.append((hours_score, 0.30))
        if task_score is not None:
            pairs.append((task_score, 0.20))

        has_data = len(pairs) > 0
        if has_data:
            w_total = sum(w for _, w in pairs)
            total = round(sum(v * w / w_total for v, w in pairs))
        else:
            total = 0

        # ── Exam countdown ────────────────────────────────────────────────
        m = self.get_module(module_id)
        exam_date_str = (m["exam_date"] if m else "") or ""
        days_until: Optional[int] = None
        if exam_date_str:
            d = _parse_date(exam_date_str)
            if d:
                days_until = (d - date.today()).days

        return {
            "total": total,
            "has_data": has_data,
            "topic_score": round(topic_score) if topic_score is not None else None,
            "hours_score": round(hours_score) if hours_score is not None else None,
            "task_score": round(task_score) if task_score is not None else None,
            "topic_count": topic_count,
            "hours_studied": round(hours_studied, 1),
            "hours_target": round(hours_target, 1),
            "tasks_done": tasks_done,
            "tasks_total": tasks_total,
            "days_until_exam": days_until,
            "exam_date_str": exam_date_str,
        }

    # ---- grades --------------------------------------------------------

    def add_grade(self, module_id: int, title: str, grade: float,
                  max_grade: float = 100.0, weight: float = 1.0,
                  date_str: str = "", notes: str = "",
                  grade_mode: str = "points") -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO grades(module_id,title,grade,max_grade,weight,date,notes,created_at,grade_mode) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (module_id, title, grade, max_grade, weight, date_str, notes, now, grade_mode),
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
        """Returns weighted average grade as percentage (0-100), or None if no grades.

        Handles two grade_mode values:
        - 'points': grade/max_grade  → percentage
        - 'direct': grade is a 1-6 Swiss value → converted back to % via (grade-1)/5
        """
        rows = self.list_grades(module_id)
        if not rows:
            return None
        total_weight = sum(float(r["weight"]) for r in rows)
        if total_weight == 0:
            return None
        weighted_sum = 0.0
        for r in rows:
            mode = r["grade_mode"] if "grade_mode" in r.keys() else "points"
            if mode == "direct":
                # grade is already a 1-6 Swiss grade — convert to % space
                pct = (float(r["grade"]) - 1.0) / 5.0
            else:
                pct = float(r["grade"]) / float(r["max_grade"])
            weighted_sum += pct * float(r["weight"])
        return (weighted_sum / total_weight) * 100.0

    def ects_weighted_gpa(self) -> Optional[float]:
        """Returns ECTS-weighted GPA (1.0-6.0 Swiss scale) across all in-plan modules.

        Only modules with at least one grade entry are included.
        Formula per module: pct/100 * 5 + 1 → 1-6 grade
        Final GPA = Σ(grade_i × ects_i) / Σ(ects_i)
        """
        modules = self.list_modules("all")
        total_ects = 0.0
        weighted_sum = 0.0
        for m in modules:
            in_plan = int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1
            if not in_plan:
                continue
            pct = self.module_weighted_grade(m["id"])
            if pct is None:
                continue
            grade = (pct / 100.0) * 5.0 + 1.0  # convert % to 1-6
            ects = float(m["ects"])
            weighted_sum += grade * ects
            total_ects += ects
        return weighted_sum / total_ects if total_ects > 0 else None

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

    # ---- SM-2 Spaced Repetition -----------------------------------------

    def sm2_review(self, topic_id: int, quality: int) -> Dict[str, Any]:
        """Process an SM-2 review for a topic.

        quality: 0–5
          0 = complete blackout / nicht gewusst
          1 = wrong but remembered after seeing answer
          2 = wrong but easy to recall
          3 = correct with significant difficulty
          4 = correct after brief hesitation
          5 = perfect recall

        Updates the topic's SR state and knowledge_level, returns new state.
        """
        row = self.conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
        if not row:
            return {}

        ef       = float(row["sr_easiness"]    or 2.5)
        reps     = int(row["sr_repetitions"]   or 0)
        interval = int(row["sr_interval"]      or 0)

        # ── SM-2 core ─────────────────────────────────────────────────────
        if quality >= 3:
            if reps == 0:
                interval = 1
            elif reps == 1:
                interval = 6
            else:
                interval = max(1, round(interval * ef))
            reps += 1
        else:
            reps     = 0
            interval = 1

        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ef = max(1.3, round(ef, 3))

        # Map quality → knowledge_level (0-4); never regress more than 1 step
        q_to_level = {0: 0, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4}
        target_level = q_to_level.get(max(0, min(5, quality)), 2)
        current_level = int(row["knowledge_level"] or 0)
        if quality >= 3:
            new_level = max(current_level, target_level)
        else:
            new_level = max(0, current_level - 1)

        next_review   = (date.today() + timedelta(days=interval)).isoformat()
        today_str     = date.today().isoformat()

        self.update_topic(
            topic_id,
            sr_easiness    = ef,
            sr_interval    = interval,
            sr_repetitions = reps,
            sr_next_review = next_review,
            last_reviewed  = today_str,
            knowledge_level= new_level,
        )
        return {
            "interval":     interval,
            "next_review":  next_review,
            "repetitions":  reps,
            "easiness":     ef,
            "new_level":    new_level,
        }

    def sm2_due_topics(self, module_id: Optional[int] = None) -> List[sqlite3.Row]:
        """Return topics due for review today or overdue (for in-plan modules)."""
        today = date.today().isoformat()
        q = """
            SELECT t.*, m.name AS module_name
            FROM topics t
            JOIN modules m ON m.id = t.module_id
            WHERE (m.in_plan = 1 OR m.in_plan IS NULL)
              AND (
                (t.sr_next_review IS NOT NULL AND t.sr_next_review != '' AND t.sr_next_review <= ?)
                OR (t.sr_next_review IS NULL OR t.sr_next_review = '')
              )
        """
        params: list = [today]
        if module_id is not None:
            q += " AND t.module_id = ?"
            params.append(module_id)
        q += " ORDER BY t.sr_next_review ASC, t.module_id, t.title"
        return list(self.conn.execute(q, params))

    def sm2_stats(self) -> Dict[str, int]:
        """Global SM-2 stats: due today, total tracked, upcoming."""
        today = date.today().isoformat()
        due_count = len(self.sm2_due_topics())
        total = int(self.conn.execute(
            "SELECT COUNT(*) AS n FROM topics t "
            "JOIN modules m ON m.id=t.module_id "
            "WHERE (m.in_plan=1 OR m.in_plan IS NULL)"
        ).fetchone()["n"])
        scheduled = int(self.conn.execute(
            "SELECT COUNT(*) AS n FROM topics "
            "WHERE sr_next_review != '' AND sr_next_review IS NOT NULL AND sr_next_review > ?",
            (today,)
        ).fetchone()["n"])
        return {"due": due_count, "total": total, "scheduled": scheduled}


    # ---- module scraped data -----------------------------------------------

    def save_scraped_data(self, module_id: int, scraped: Dict[str, Any]) -> None:
        """
        Store scraped objectives, content sections and assessments for a module.
        Replaces any existing scraped data for this module.

        scraped keys used:
            objectives        list[str]
            content_sections  list[{title, items:[str]}]
            assessments       list[{art, zeitpunkt, dauer, inhalt, weight}]
        """
        # Wipe existing data for this module
        self.conn.execute(
            "DELETE FROM module_scraped_data WHERE module_id=?", (module_id,)
        )

        rows: List[tuple] = []

        for i, obj in enumerate(scraped.get("objectives", [])):
            rows.append((module_id, "objective", obj, "", 0.0, i))

        for i, sec in enumerate(scraped.get("content_sections", [])):
            body = json.dumps(sec.get("items", []), ensure_ascii=False)
            rows.append((module_id, "content_section", sec.get("title", ""), body, 0.0, i))

        for i, ass in enumerate(scraped.get("assessments", [])):
            detail = ass.get("inhalt", "") or ass.get("zeitpunkt", "")
            rows.append((module_id, "assessment", ass.get("art", ""), detail, float(ass.get("weight", 0)), i))

        self.conn.executemany(
            """
            INSERT INTO module_scraped_data(module_id,data_type,title,body,weight,sort_order)
            VALUES(?,?,?,?,?,?)
            """,
            rows,
        )
        self.conn.commit()

    def list_scraped_data(
        self, module_id: int, data_type: Optional[str] = None
    ) -> List[sqlite3.Row]:
        """Return scraped data rows for a module, optionally filtered by type."""
        if data_type:
            return list(self.conn.execute(
                "SELECT * FROM module_scraped_data WHERE module_id=? AND data_type=? ORDER BY sort_order",
                (module_id, data_type),
            ))
        return list(self.conn.execute(
            "SELECT * FROM module_scraped_data WHERE module_id=? ORDER BY data_type, sort_order",
            (module_id,),
        ))

    def has_scraped_data(self, module_id: int) -> bool:
        """Return True if module has any scraped data."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM module_scraped_data WHERE module_id=?",
            (module_id,),
        ).fetchone()
        return bool(row and row["cnt"] > 0)

    def set_objective_checked(self, scraped_id: int, checked: bool) -> None:
        """Toggle the checked state of a single scraped-data row (used for exam-prep checklists)."""
        self.conn.execute(
            "UPDATE module_scraped_data SET checked=? WHERE id=?",
            (1 if checked else 0, scraped_id),
        )
        self.conn.commit()

    def reset_objectives_checked(self, module_id: int) -> None:
        """Uncheck all objectives for a module (reset exam-prep progress)."""
        self.conn.execute(
            "UPDATE module_scraped_data SET checked=0 WHERE module_id=? AND data_type='objective'",
            (module_id,),
        )
        self.conn.commit()

    def add_scraped_data(self, module_id: int, data_type: str, title: str,
                         body: str = "", weight: float = 0.0, sort_order: int = 0) -> None:
        """Insert a new scraped-data row (e.g. a manually added objective)."""
        self.conn.execute(
            """INSERT INTO module_scraped_data
               (module_id, data_type, title, body, weight, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (module_id, data_type, title, body, weight, sort_order),
        )
        self.conn.commit()

    def update_scraped_data(self, scraped_id: int, **fields) -> None:
        """Update arbitrary columns on a scraped-data row (e.g. checked=1)."""
        if not fields:
            return
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [scraped_id]
        self.conn.execute(
            f"UPDATE module_scraped_data SET {set_clause} WHERE id=?", values
        )
        self.conn.commit()

    def delete_scraped_data(self, module_id: int) -> None:
        """Remove all scraped data for a module."""
        self.conn.execute(
            "DELETE FROM module_scraped_data WHERE module_id=?", (module_id,)
        )
        self.conn.commit()


    # ---- stundenplan (weekly timetable) ----------------------------------

    def list_stundenplan(self) -> List[sqlite3.Row]:
        """Return all timetable entries ordered by day and start time."""
        return list(self.conn.execute(
            "SELECT * FROM stundenplan ORDER BY day_of_week, time_from"
        ))

    def add_stundenplan_entry(self, data: Dict[str, Any]) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO stundenplan
                (day_of_week, time_from, time_to, subject, room, lecturer, color, module_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(data.get("day_of_week", 0)),
                data.get("time_from", "08:00"),
                data.get("time_to", "10:00"),
                data.get("subject", ""),
                data.get("room", ""),
                data.get("lecturer", ""),
                data.get("color", "#7C3AED"),
                data.get("module_id"),
                data.get("notes", ""),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_stundenplan_entry(self, entry_id: int, **fields: Any) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [entry_id]
        self.conn.execute(
            f"UPDATE stundenplan SET {set_clause} WHERE id=?", vals
        )
        self.conn.commit()

    def delete_stundenplan_entry(self, entry_id: int) -> None:
        self.conn.execute("DELETE FROM stundenplan WHERE id=?", (entry_id,))
        self.conn.commit()

    def clear_stundenplan(self) -> None:
        """Remove all timetable entries."""
        self.conn.execute("DELETE FROM stundenplan")
        self.conn.commit()


def _parse_date(s: str | None) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None
