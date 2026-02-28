from __future__ import annotations

import argparse
import sys

from study_organizer.domain.models import Deadline, Module
from study_organizer.infra.db import connect, migrate
from study_organizer.infra.sqlite_repo import SQLiteRepository


def build_repo() -> SQLiteRepository:
    conn = connect()
    migrate(conn)
    return SQLiteRepository(conn)


def cmd_module_add(args: argparse.Namespace) -> int:
    repo = build_repo()
    repo.add_module(Module(code=args.code, title=args.title))
    print(f"Added module {args.code}: {args.title}")
    return 0


def cmd_module_list(args: argparse.Namespace) -> int:
    repo = build_repo()
    modules = repo.list_modules()
    if not modules:
        print("No modules yet.")
        return 0
    for m in modules:
        print(f"{m.code}\t{m.title}")
    return 0


def cmd_deadline_add(args: argparse.Namespace) -> int:
    repo = build_repo()
    repo.add_deadline(
        Deadline(
            module_code=args.module,
            title=args.title,
            due_date=args.due,
            notes=args.notes,
        )
    )
    print(f"Added deadline for {args.module}: {args.title} ({args.due})")
    return 0


def cmd_deadline_list(args: argparse.Namespace) -> int:
    repo = build_repo()
    deadlines = repo.list_deadlines(module_code=args.module)
    if not deadlines:
        print("No deadlines yet.")
        return 0
    for d in deadlines:
        notes = f" | {d.notes}" if d.notes else ""
        print(f"{d.due_date}\t{d.module_code}\t{d.title}{notes}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="study", description="Study Organizer (CLI)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # module
    module = sub.add_parser("module", help="Manage modules")
    module_sub = module.add_subparsers(dest="subcmd", required=True)

    m_add = module_sub.add_parser("add", help="Add a module")
    m_add.add_argument("--code", required=True, help="Module code, e.g. SE101")
    m_add.add_argument("--title", required=True, help="Module title")
    m_add.set_defaults(func=cmd_module_add)

    m_list = module_sub.add_parser("list", help="List modules")
    m_list.set_defaults(func=cmd_module_list)

    # deadline
    deadline = sub.add_parser("deadline", help="Manage deadlines")
    deadline_sub = deadline.add_subparsers(dest="subcmd", required=True)

    d_add = deadline_sub.add_parser("add", help="Add a deadline")
    d_add.add_argument("--module", required=True, help="Module code, e.g. SE101")
    d_add.add_argument("--title", required=True, help="Deadline title")
    d_add.add_argument("--due", required=True, help="Due date YYYY-MM-DD")
    d_add.add_argument("--notes", required=False, help="Optional notes")
    d_add.set_defaults(func=cmd_deadline_add)

    d_list = deadline_sub.add_parser("list", help="List deadlines")
    d_list.add_argument("--module", required=False, help="Filter by module code")
    d_list.set_defaults(func=cmd_deadline_list)

    args = parser.parse_args()
    func = getattr(args, "func", None)
    if not func:
        parser.print_help()
        sys.exit(2)
    sys.exit(func(args))


if __name__ == "__main__":
    main()
