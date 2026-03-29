"""
structured_scraper.py
=====================
Parses Excel (.xlsx / .xls) and JSON files containing scraped module data.

This allows any student (from any school) to import module data they scraped
from websites into the Semetra.

Supported file types
--------------------
  .xlsx / .xls  –  Microsoft Excel (requires openpyxl)
  .json         –  JSON array or single object

Excel column names (case-insensitive, German & English aliases accepted)
----------------------------------------------------------------------
  Required (at least one): code, name
  Optional:
    ects, semester,
    lernziele       (newline / semicolon / pipe separated text, or JSON array)
    lerninhalte     (same)
    pruefungen      (same)
    gewichtung      (number or "70%" – applied to all pruefungen if single value,
                     or comma/newline list matching pruefungen rows)

JSON schema (array of objects)
------------------------------
  Each object may contain:
    code, name, ects, semester
    objectives  | lernziele        – list[str] or newline text
    content_sections | lerninhalte – list[str] or list[{title, items}]
    assessments  | pruefungen      – list[{art, weight/gewichtung}] or list[str]

  Also accepts a top-level object with a "modules" or "data" key.

Usage
-----
  from semetra.adapters.structured_scraper import parse_excel, parse_json, parse_file

  results = parse_file("path/to/modules.xlsx")
  # returns list[dict] – same structure as pdf_scraper.scrape_module_pdf()
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Public entry points ────────────────────────────────────────────────────

def parse_file(path: str | Path) -> List[Dict[str, Any]]:
    """Auto-dispatch based on file extension."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext in (".xlsx", ".xls"):
        return parse_excel(path)
    elif ext == ".json":
        return parse_json(path)
    else:
        return [_error_result(path.name, f"Unbekannter Dateityp: {ext}")]


def parse_excel(path: str | Path) -> List[Dict[str, Any]]:
    """Parse an Excel file and return ScrapedModule-compatible dicts."""
    path = Path(path)
    try:
        import openpyxl
    except ImportError:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "openpyxl", "--quiet"],
                check=True, capture_output=True,
            )
            import openpyxl  # type: ignore
        except Exception as e:
            return [_error_result(path.name, f"openpyxl nicht installiert: {e}")]

    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
    except Exception as e:
        return [_error_result(path.name, str(e))]

    if not rows:
        return []

    # Build column index from header row
    headers = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    col = _build_col_map(headers)

    results = []
    for row in rows[1:]:
        if all(c is None for c in row):
            continue
        results.append(_parse_excel_row(row, col, path.name))

    return results


def parse_json(path: str | Path) -> List[Dict[str, Any]]:
    """Parse a JSON file and return ScrapedModule-compatible dicts."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        return [_error_result(path.name, str(e))]

    if isinstance(data, dict):
        if "modules" in data:
            data = data["modules"]
        elif "data" in data:
            data = data["data"]
        else:
            data = [data]  # single-module object

    if not isinstance(data, list):
        return [_error_result(path.name, "JSON muss eine Liste oder ein Objekt mit 'modules' sein")]

    results = []
    for item in data:
        if isinstance(item, dict):
            results.append(_parse_json_object(item, path.name))

    return results


# ── Column alias registry ──────────────────────────────────────────────────

_COL_ALIASES: Dict[str, List[str]] = {
    "code":        ["code", "kürzel", "kurzzeichen", "modulcode", "module_code", "kode"],
    "name":        ["name", "modulname", "module_name", "bezeichnung", "titel", "title", "modul"],
    "ects":        ["ects", "credits", "kreditpunkte", "credit_points", "lp", "leistungspunkte"],
    "semester":    ["semester", "sem", "gültig_ab", "valid_from", "gueltig_ab", "period"],
    "lernziele":   ["lernziele", "objectives", "learning_objectives", "kompetenzen",
                    "zu entwickelnde kompetenzen", "ziele", "learning outcomes"],
    "lerninhalte": ["lerninhalte", "content", "contents", "inhalte", "topics", "themen",
                    "inhalt", "lerninhalte"],
    "pruefungen":  ["prüfungen", "pruefungen", "assessments", "leistungsnachweis",
                    "prüfung", "pruefung", "leistungsnachweise", "exam", "exams"],
    "gewichtung":  ["gewichtung", "weight", "notengewicht", "anteil", "prozent",
                    "gewicht", "weighting", "%", "note"],
}


def _build_col_map(headers: List[str]) -> Dict[str, int]:
    """Return a field→column_index mapping from the header row."""
    col: Dict[str, int] = {}
    for field, aliases in _COL_ALIASES.items():
        for i, h in enumerate(headers):
            if h in aliases or any(a in h for a in aliases):
                if field not in col:
                    col[field] = i
    return col


# ── Excel row parser ───────────────────────────────────────────────────────

def _cell(row, col: Dict[str, int], field: str, default="") -> Any:
    """Extract a cell value from a row tuple by field name."""
    idx = col.get(field)
    if idx is None or idx >= len(row):
        return default
    v = row[idx]
    return default if v is None else v


def _parse_excel_row(row, col: Dict[str, int], filename: str) -> Dict[str, Any]:
    code     = str(_cell(row, col, "code") or "").strip()
    name     = str(_cell(row, col, "name") or "").strip()
    ects_raw = _cell(row, col, "ects", 0)
    semester = str(_cell(row, col, "semester") or "").strip()

    try:
        ects = float(ects_raw) if ects_raw else 0.0
    except (ValueError, TypeError):
        ects = 0.0

    objectives     = _split_list(_cell(row, col, "lernziele", ""))
    content_raw    = _split_list(_cell(row, col, "lerninhalte", ""))
    content_sections = [{"title": c, "items": []} for c in content_raw]
    pruefungen_raw = _split_list(_cell(row, col, "pruefungen", ""))
    gewichtung_raw = _cell(row, col, "gewichtung", "")
    assessments    = _parse_assessments_from_list(pruefungen_raw, gewichtung_raw)

    # Ensure code & name are populated
    if not name and not code:
        name = Path(filename).stem
        code = name[:10]
    elif not name:
        name = code
    elif not code:
        code = (name.split()[0])[:10]

    return _make_result(code, name, ects, semester,
                        objectives, content_sections, assessments, filename)


# ── JSON object parser ─────────────────────────────────────────────────────

def _parse_json_object(obj: dict, filename: str) -> Dict[str, Any]:
    code     = str(obj.get("code") or obj.get("kürzel") or "").strip()
    name     = str(obj.get("name") or obj.get("modulname") or obj.get("title") or "").strip()
    semester = str(obj.get("semester") or obj.get("sem") or "").strip()

    try:
        ects = float(obj.get("ects") or obj.get("credits") or 0)
    except (ValueError, TypeError):
        ects = 0.0

    # Objectives
    raw_obj = (obj.get("objectives") or obj.get("lernziele")
               or obj.get("kompetenzen") or obj.get("learning_outcomes") or [])
    objectives = _coerce_list(raw_obj)

    # Content sections
    raw_content = (obj.get("content_sections") or obj.get("lerninhalte")
                   or obj.get("inhalte") or obj.get("topics") or [])
    content_sections = _parse_content_sections(raw_content)

    # Assessments
    raw_assess = (obj.get("assessments") or obj.get("pruefungen")
                  or obj.get("prüfungen") or obj.get("leistungsnachweis") or [])
    assessments = _parse_assessments_json(raw_assess)

    if not name and not code:
        name = Path(filename).stem
        code = name[:10]
    elif not name:
        name = code
    elif not code:
        code = (name.split()[0])[:10]

    return _make_result(code, name, ects, semester,
                        objectives, content_sections, assessments, filename)


# ── Shared helpers ─────────────────────────────────────────────────────────

def _coerce_list(val) -> List[str]:
    """Ensure val is a list of non-empty strings."""
    if isinstance(val, list):
        return [str(v).strip() for v in val if str(v).strip()]
    return _split_list(val)


def _split_list(val) -> List[str]:
    """Split a cell value into a list (handles text, JSON array, newlines, semicolons)."""
    if isinstance(val, list):
        return [str(v).strip() for v in val if str(v).strip()]
    s = str(val).strip()
    if not s:
        return []
    # Attempt JSON parse
    if s.startswith("["):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except Exception:
            pass
    # Newline / semicolon / pipe split
    parts = re.split(r"[\n;|]+", s)
    return [p.strip() for p in parts if p.strip()]


def _parse_content_sections(raw) -> List[Dict]:
    if not raw:
        return []
    if isinstance(raw, str):
        raw = _split_list(raw)
    if isinstance(raw, list):
        sections = []
        for item in raw:
            if isinstance(item, dict):
                sections.append({
                    "title": str(item.get("title") or item.get("titel") or ""),
                    "items": [str(i) for i in item.get("items", []) if i],
                })
            elif item:
                sections.append({"title": str(item).strip(), "items": []})
        return sections
    return []


def _parse_assessments_json(raw) -> List[Dict]:
    if not raw:
        return []
    if isinstance(raw, str):
        raw = _split_list(raw)
    if isinstance(raw, list):
        assessments = []
        for item in raw:
            if isinstance(item, dict):
                weight_raw = (item.get("weight") or item.get("gewichtung")
                              or item.get("notengewicht") or 0)
                try:
                    w = float(str(weight_raw).replace("%", "").strip())
                except (ValueError, TypeError):
                    w = 0.0
                assessments.append({
                    "art": str(item.get("art") or item.get("name")
                               or item.get("type") or item.get("typ") or ""),
                    "zeitpunkt":  str(item.get("zeitpunkt") or ""),
                    "dauer":      str(item.get("dauer") or ""),
                    "inhalt":     str(item.get("inhalt") or ""),
                    "hilfsmittel": str(item.get("hilfsmittel") or ""),
                    "weight": w,
                })
            elif item:
                # Plain string like "Modulprüfung (70%)"
                art_str = str(item).strip()
                w = 0.0
                m = re.search(r"\((\d+)\s*%\)", art_str)
                if m:
                    w = float(m.group(1))
                    art_str = re.sub(r"\s*\(\d+\s*%\)", "", art_str).strip()
                assessments.append({
                    "art": art_str,
                    "zeitpunkt": "", "dauer": "", "inhalt": "", "hilfsmittel": "",
                    "weight": w,
                })
        return assessments
    return []


def _parse_assessments_from_list(pruefungen: List[str], gewichtung_raw) -> List[Dict]:
    """Build assessment list from a pruefungen list + optional weight column."""
    # Parse weights column
    weights: List[float] = []
    if gewichtung_raw:
        for w in _split_list(gewichtung_raw):
            try:
                weights.append(float(str(w).replace("%", "").strip()))
            except (ValueError, TypeError):
                weights.append(0.0)

    assessments = []
    for i, p in enumerate(pruefungen):
        weight = weights[i] if i < len(weights) else (weights[0] if len(weights) == 1 else 0.0)
        # Embedded weight like "Modulprüfung (70%)"
        m = re.search(r"\((\d+)\s*%\)", p)
        if m:
            weight = float(m.group(1))
            p = re.sub(r"\s*\(\d+\s*%\)", "", p).strip()
        assessments.append({
            "art": p, "zeitpunkt": "", "dauer": "", "inhalt": "", "hilfsmittel": "",
            "weight": weight,
        })
    return assessments


# ── Result builders ────────────────────────────────────────────────────────

def _make_result(
    code: str, name: str, ects: float, semester: str,
    objectives: List[str], content_sections: List[Dict],
    assessments: List[Dict], filename: str,
) -> Dict[str, Any]:
    return {
        "code":             code,
        "name":             name,
        "ects":             ects,
        "semester_tag":     semester,
        "objectives":       objectives,
        "content_sections": content_sections,
        "assessments":      assessments,
        "literature":       [],
        "source_file":      filename,
        "_error":           "",
    }


def _error_result(filename: str, error: str) -> Dict[str, Any]:
    stem = Path(filename).stem
    result = _make_result(
        code=stem[:10], name=stem,
        ects=0.0, semester="",
        objectives=[], content_sections=[], assessments=[],
        filename=filename,
    )
    result["_error"] = error
    return result
