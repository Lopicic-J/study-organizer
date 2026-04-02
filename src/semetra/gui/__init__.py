"""Semetra GUI package."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from semetra.gui import state
from semetra.gui import constants
from semetra.gui import i18n
from semetra.gui.i18n import set_lang
from semetra.gui.colors import set_theme
from semetra.gui.main_window import SemetraWindow
from semetra.repo.sqlite_repo import SqliteRepo

__all__ = ["state", "constants", "i18n", "gui_main"]


def gui_main(repo: SqliteRepo) -> None:
    """Entry point for the Semetra GUI application.

    Args:
        repo: The SqliteRepo instance for database access.
    """
    # AA_NativeWindows must be set before QApplication creation on Windows
    # so that Aero Snap (drag-to-edge) and other native WM integrations work.
    if sys.platform == "win32":
        QApplication.setAttribute(Qt.AA_NativeWindows, True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Semetra")
    # Fusion style = consistent look on all platforms (Linux/Windows/Mac)
    app.setStyle("Fusion")
    # Apply saved language AND theme BEFORE any widget is created, so tr()/_tc() return correct values
    set_lang(repo.get_setting("language") or "de")
    set_theme(repo.get_setting("theme") or "light")
    window = SemetraWindow(repo)
    window.show()
    sys.exit(app.exec())
