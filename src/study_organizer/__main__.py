from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="study", description="Study Organizer (CLI)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show current status (placeholder)")

    args = parser.parse_args()

    if args.cmd == "status":
        print(
            "Study Organizer is installed and running. Next: implement modules/deadlines."
        )


if __name__ == "__main__":
    main()
