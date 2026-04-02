"""
FFHS BSc-Informatik Modul-Importer
====================================
Lädt alle BSc-Informatik-Module der FFHS und gibt sie als Liste von Dicts zurück,
die direkt mit SqliteRepo.add_module() importiert werden können.

Verwendung:
    from semetra.adapters.ffhs_importer import load_ffhs_modules
    modules = load_ffhs_modules()
    for m in modules:
        repo.add_module(m)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_BUNDLED_JSON = Path(__file__).parent / "ffhs_modules.json"
_FFHS_URL = "https://www.ffhs.ch/de/bachelor/informatik"


def load_ffhs_modules(*, live: bool = True) -> List[Dict[str, Any]]:
    """
    Lädt FFHS BSc-Informatik Module als Liste von add_module()-kompatiblen Dicts.

    Versucht zuerst Live-Scraping (erfordert requests + beautifulsoup4).
    Fällt automatisch auf die gebündelte JSON zurück.

    Extra-Schlüssel im Dict (für Dialog-Filterung, werden von add_module ignoriert):
        _module_type   : "Pflicht" | "Vertiefung" | "Wahlfach"
        _description   : Kurzbeschreibung des Moduls
        _semester_int  : Semester als Integer (1-9)
    """
    if live:
        try:
            modules = _scrape_live()
            if modules:
                logger.info("Live-Scraping: %d Module geladen.", len(modules))
                return modules
        except Exception as exc:
            logger.info("Live-Scraping nicht verfügbar (%s) – nutze gebündelte Daten.", exc)

    return _load_bundled()


# ------------------------------------------------------------------ live scraper

def _scrape_live() -> List[Dict[str, Any]]:
    """Versucht Module live von www.ffhs.ch zu scrapen."""
    import importlib
    if not (importlib.util.find_spec("requests") and importlib.util.find_spec("bs4")):
        raise RuntimeError("requests/beautifulsoup4 nicht installiert")

    import requests
    from bs4 import BeautifulSoup

    session = requests.Session()
    session.headers["User-Agent"] = "Semetra/1.0 (student FFHS importer)"
    resp = session.get(_FFHS_URL, timeout=12)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    modules = _parse_tables(soup)
    return modules


def _parse_tables(soup: Any) -> List[Dict[str, Any]]:
    import re
    modules = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not any(kw in " ".join(headers) for kw in ["modul", "ects", "credits"]):
            continue
        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 2:
                continue
            name = cells[0].strip()
            if len(name) < 3:
                continue
            ects = 0.0
            for c in cells:
                m = re.search(r"\b(\d{1,2})\b", c)
                if m:
                    ects = float(m.group(1))
                    break
            modules.append(_make_module_dict(name, 0, ects, "Pflicht", _FFHS_URL, ""))
    return modules


# ------------------------------------------------------------------ bundled

def _load_bundled() -> List[Dict[str, Any]]:
    """Lädt die gebündelte Modulliste."""
    raw = json.loads(_BUNDLED_JSON.read_text(encoding="utf-8"))
    result = []
    for entry in raw.get("modules", []):
        result.append(
            _make_module_dict(
                name=entry["name"],
                semester=entry.get("semester", 0),
                ects=float(entry.get("ects", 0)),
                module_type=entry.get("module_type", "Pflicht"),
                link=entry.get("link", ""),
                description=entry.get("description", ""),
            )
        )
    return result


# ------------------------------------------------------------------ helper

def _make_module_dict(
    name: str,
    semester: int,
    ects: float,
    module_type: str,
    link: str,
    description: str,
) -> Dict[str, Any]:
    """Erstellt ein add_module()-kompatibles Dict."""
    return {
        # ── Felder für SqliteRepo.add_module() ──────────────────────────
        "name": name,
        "semester": str(semester),     # schema: TEXT
        "ects": ects,
        "lecturer": "",
        "link": link,
        "status": "planned",
        "exam_date": "",
        "weighting": 1.0,
        "github_link": "",
        "sharepoint_link": "",
        "literature_links": "",
        "notes_link": "",
        # ── Extra-Metadaten (für Import-Dialog; werden von add_module ignoriert) ──
        "_module_type": module_type,
        "_description": description,
        "_semester_int": semester,
    }
