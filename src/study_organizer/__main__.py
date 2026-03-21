from __future__ import annotations

from study_organizer.app import build_repo
from study_organizer.gui import gui_main


def main() -> None:
    repo = build_repo("study.db")
    gui_main(repo)


if __name__ == "__main__":
    main()
