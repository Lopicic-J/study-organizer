from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()  # Lädt .env aus dem Arbeitsverzeichnis (oder einem übergeordneten Ordner)

from semetra.app import build_repo
from semetra.gui import gui_main


def main() -> None:
    repo = build_repo("study.db")
    gui_main(repo)


if __name__ == "__main__":
    main()
