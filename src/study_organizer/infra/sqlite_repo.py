from __future__ import annotations

import sqlite3

from study_organizer.domain.models import Module, SubTask, Task
from study_organizer.service.errors import ConflictError, NotFoundError, StorageError


class SQLiteRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute("PRAGMA foreign_keys = ON")

    # ---------- Modules ----------
    def add_module(self, module: Module) -> None:
        try:
            self.conn.execute(
                "INSERT INTO modules (code, title) VALUES (?, ?)",
                (module.code.strip(), module.title.strip()),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(f"Module '{module.code}' already exists.") from e
        except sqlite3.Error as e:
            raise StorageError("Database error while adding module.") from e

    def update_module(self, code: str, new_title: str) -> None:
        try:
            cur = self.conn.execute(
                "UPDATE modules SET title = ?, updated_at = datetime('now') WHERE code = ?",
                (new_title.strip(), code.strip()),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Module '{code}' not found.")
            self.conn.commit()
        except sqlite3.Error as e:
            raise StorageError("Database error while updating module.") from e

    def delete_module(self, code: str) -> None:
        try:
            cur = self.conn.execute(
                "DELETE FROM modules WHERE code = ?", (code.strip(),)
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Module '{code}' not found.")
            self.conn.commit()
        except sqlite3.Error as e:
            raise StorageError("Database error while deleting module.") from e

    def list_modules(self) -> list[Module]:
        try:
            rows = self.conn.execute(
                "SELECT code, title FROM modules ORDER BY code"
            ).fetchall()
            return [Module(code=row["code"], title=row["title"]) for row in rows]
        except sqlite3.Error as e:
            raise StorageError("Database error while listing modules.") from e

    # ---------- Tasks ----------
    def add_task(self, task: Task) -> int:
        try:
            cur = self.conn.execute(
                """
                INSERT INTO tasks (module_code, title, due_date, notes, status, priority)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    task.module_code.strip(),
                    task.title.strip(),
                    task.due_date,
                    task.notes,
                    task.status,
                    task.priority,
                ),
            )
            self.conn.commit()
            return int(cur.lastrowid)
        except sqlite3.IntegrityError as e:
            raise NotFoundError(
                f"Module '{task.module_code}' not found. Add the module first."
            ) from e
        except sqlite3.Error as e:
            raise StorageError("Database error while adding task.") from e

    def update_task(
        self,
        task_id: int,
        *,
        module_code: str,
        title: str,
        due_date: str | None,
        notes: str | None,
    ) -> None:
        try:
            cur = self.conn.execute(
                """
                UPDATE tasks
                SET module_code = ?, title = ?, due_date = ?, notes = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (module_code.strip(), title.strip(), due_date, notes, task_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Task {task_id} not found.")
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            raise NotFoundError(
                f"Module '{module_code}' not found. Add the module first."
            ) from e
        except sqlite3.Error as e:
            raise StorageError("Database error while updating task.") from e

    def delete_task(self, task_id: int) -> None:
        try:
            cur = self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            if cur.rowcount == 0:
                raise NotFoundError(f"Task {task_id} not found.")
            self.conn.commit()
        except sqlite3.Error as e:
            raise StorageError("Database error while deleting task.") from e

    def list_tasks(
        self,
        module_code: str | None = None,
        status: str | None = None,
        q: str | None = None,
        priority_min: int | None = None,
        priority_max: int | None = None,
    ) -> list[Task]:
        where: list[str] = []
        params: list[object] = []

        if module_code:
            where.append("module_code = ?")
            params.append(module_code.strip())
        if status:
            where.append("status = ?")
            params.append(status)
        if q:
            where.append("(title LIKE ? OR notes LIKE ?)")
            like = f"%{q.strip()}%"
            params.extend([like, like])
        if priority_min is not None:
            where.append("priority >= ?")
            params.append(priority_min)
        if priority_max is not None:
            where.append("priority <= ?")
            params.append(priority_max)

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        sql = (
            "SELECT id, module_code, title, due_date, notes, status, priority "
            "FROM tasks"
            + where_sql
            + " ORDER BY (due_date IS NULL), due_date, priority DESC, id DESC"
        )

        try:
            rows = self.conn.execute(sql, tuple(params)).fetchall()
            return [
                Task(
                    id=int(row["id"]),
                    module_code=row["module_code"],
                    title=row["title"],
                    due_date=row["due_date"],
                    notes=row["notes"],
                    status=row["status"],
                    priority=int(row["priority"]),
                )
                for row in rows
            ]
        except sqlite3.Error as e:
            raise StorageError("Database error while listing tasks.") from e

    def set_task_status(self, task_id: int, status: str) -> None:
        try:
            cur = self.conn.execute(
                "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (status, task_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Task {task_id} not found.")
            self.conn.commit()
        except sqlite3.Error as e:
            raise StorageError("Database error while updating task status.") from e

    def set_task_priority(self, task_id: int, priority: int) -> None:
        try:
            cur = self.conn.execute(
                "UPDATE tasks SET priority = ?, updated_at = datetime('now') WHERE id = ?",
                (priority, task_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Task {task_id} not found.")
            self.conn.commit()
        except sqlite3.Error as e:
            raise StorageError("Database error while updating task priority.") from e

    # ---------- Subtasks ----------
    def add_subtask(self, st: SubTask) -> int:
        try:
            cur = self.conn.execute(
                """
                INSERT INTO subtasks (parent_task_id, title, due_date, notes, status, priority)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    st.parent_task_id,
                    st.title.strip(),
                    st.due_date,
                    st.notes,
                    st.status,
                    st.priority,
                ),
            )
            self.conn.commit()
            return int(cur.lastrowid)
        except sqlite3.IntegrityError as e:
            raise NotFoundError(f"Parent task {st.parent_task_id} not found.") from e
        except sqlite3.Error as e:
            raise StorageError("Database error while adding subtask.") from e

    def list_subtasks(self, parent_task_id: int) -> list[SubTask]:
        try:
            rows = self.conn.execute(
                """
                SELECT id, parent_task_id, title, due_date, notes, status, priority
                FROM subtasks
                WHERE parent_task_id = ?
                ORDER BY (due_date IS NULL), due_date, priority DESC, id DESC
                """,
                (parent_task_id,),
            ).fetchall()
            return [
                SubTask(
                    id=int(r["id"]),
                    parent_task_id=int(r["parent_task_id"]),
                    title=r["title"],
                    due_date=r["due_date"],
                    notes=r["notes"],
                    status=r["status"],
                    priority=int(r["priority"]),
                )
                for r in rows
            ]
        except sqlite3.Error as e:
            raise StorageError("Database error while listing subtasks.") from e

    def update_subtask(
        self,
        subtask_id: int,
        *,
        title: str,
        due_date: str | None,
        notes: str | None,
    ) -> None:
        try:
            cur = self.conn.execute(
                """
                UPDATE subtasks
                SET title = ?, due_date = ?, notes = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (title.strip(), due_date, notes, subtask_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Subtask {subtask_id} not found.")
            self.conn.commit()
        except sqlite3.Error as e:
            raise StorageError("Database error while updating subtask.") from e

    def delete_subtask(self, subtask_id: int) -> None:
        try:
            cur = self.conn.execute("DELETE FROM subtasks WHERE id = ?", (subtask_id,))
            if cur.rowcount == 0:
                raise NotFoundError(f"Subtask {subtask_id} not found.")
            self.conn.commit()
        except sqlite3.Error as e:
            raise StorageError("Database error while deleting subtask.") from e

    def set_subtask_status(self, subtask_id: int, status: str) -> None:
        try:
            cur = self.conn.execute(
                "UPDATE subtasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (status, subtask_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Subtask {subtask_id} not found.")
            self.conn.commit()
        except sqlite3.Error as e:
            raise StorageError("Database error while updating subtask status.") from e

    def set_subtask_priority(self, subtask_id: int, priority: int) -> None:
        try:
            cur = self.conn.execute(
                "UPDATE subtasks SET priority = ?, updated_at = datetime('now') WHERE id = ?",
                (priority, subtask_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Subtask {subtask_id} not found.")
            self.conn.commit()
        except sqlite3.Error as e:
            raise StorageError("Database error while updating subtask priority.") from e
