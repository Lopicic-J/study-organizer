from __future__ import annotations

from semetra.app import build_repo
from semetra.gui import gui_main


def main() -> None:
    repo = build_repo("study.db")
    gui_main(repo)


if __name__ == "__main__":
    main()
