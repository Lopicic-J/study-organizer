from __future__ import annotations

import argparse
import sqlite3
import sys

from study_organizer.infra.schema import init_db
from study_organizer.domain.models import Deadline, Module
from study_organizer.infra.sqlite_repo import SQLiteRepository
from study_organizer.service.errors import (
    ConflictError,
    NotFoundError,
    StorageError,
    ValidationError,
)
from study_organizer.service.validation import (
    validate_iso_date,
    validate_module_code,
    validate_title,
)


def build_repo() -> SQLiteRepository:
    conn = sqlite3.connect("study.db")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return SQLiteRepository(conn)


def cmd_module_add(args: argparse.Namespace) -> int:
    repo = build_repo()
    repo.add_module(
        Module(
            code=validate_module_code(args.code),
            title=validate_title(args.title),
        )
    )
    print("Module added.")
    return 0


def cmd_deadline_add(args: argparse.Namespace) -> int:
    repo = build_repo()
    repo.add_deadline(
        Deadline(
            module_code=validate_module_code(args.module),
            title=validate_title(args.title),
            due_date=validate_iso_date(args.due),
            notes=args.notes,
        )
    )
    print("Deadline added.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="study")
    sub = parser.add_subparsers(dest="cmd", required=True)

    module = sub.add_parser("module")
    module_sub = module.add_subparsers(dest="subcmd", required=True)

    m_add = module_sub.add_parser("add")
    m_add.add_argument("--code", required=True)
    m_add.add_argument("--title", required=True)
    m_add.set_defaults(func=cmd_module_add)

    m_list = module_sub.add_parser("list")
    m_list.set_defaults(func=cmd_module_list)

    deadline = sub.add_parser("deadline")
    deadline_sub = deadline.add_subparsers(dest="subcmd", required=True)

    d_add = deadline_sub.add_parser("add")
    d_add.add_argument("--module", required=True)
    d_add.add_argument("--title", required=True)
    d_add.add_argument("--due", required=True)
    d_add.add_argument("--notes", required=False)
    d_add.set_defaults(func=cmd_deadline_add)

    args = parser.parse_args()
    func = getattr(args, "func")

    try:
        sys.exit(func(args))
    except (ValidationError, ConflictError, NotFoundError) as e:
        print(f"Error: {e}")
        sys.exit(2)
    except StorageError as e:
        print(f"Storage error: {e}")
        sys.exit(3)


def cmd_module_list(args: argparse.Namespace) -> int:
    repo = build_repo()
    modules = repo.list_modules()
    if not modules:
        print("No modules yet.")
        return 0
    for m in modules:
        print(f"{m.code}\t{m.title}")
    return 0


if __name__ == "__main__":
    main()
