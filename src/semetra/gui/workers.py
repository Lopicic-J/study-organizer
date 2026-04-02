from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from semetra.gui.i18n import tr


class _ScraperWorker(QThread):
    """QThread wrapper around UniversityWebScraper.scrape()."""
    progress = Signal(str)      # status message
    finished = Signal(list)     # list[dict] of extracted modules
    error    = Signal(str)      # error message

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            from semetra.adapters.web_scraper import UniversityWebScraper
            scraper = UniversityWebScraper()
            modules = scraper.scrape(self._url, progress_cb=lambda msg: self.progress.emit(msg))
            self.finished.emit(modules)
        except Exception as exc:
            self.error.emit(str(exc))
