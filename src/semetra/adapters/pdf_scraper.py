"""
pdf_scraper.py
==============
Universal module-plan PDF scraper.

Extracts the following from any structured module-plan PDF:
  - Module code & name
  - ECTS credits
  - "Zu entwickelnde Kompetenzen" / learning objectives
  - "Lerninhalte" / content sections with sub-topics
  - "Leistungsnachweis" / assessments with weights
  - Literature list

The parser is intentionally lenient – it works on FFHS-style PDFs and any
reasonably formatted academic module description.

Usage:
    from semetra.adapters.pdf_scraper import scrape_module_pdf, scrape_folder

    result = scrape_module_pdf("path/to/module.pdf")
    # result is a dict – see ScrapedModule structure below

    all_results = scrape_folder("/path/to/pdfs/")
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Type alias ────────────────────────────────────────────────────────────
# A ScrapedModule dict has the following keys:
#   code              str   – e.g. "JaF"
#   name              str   – full name, e.g. "Java – Fundamentals"
#   ects              float – ECTS credit points
#   semester_tag      str   – "FS26", "HS25/26", etc.  (or "")
#   objectives        list[str]
#   content_sections  list[{title:str, items:list[str]}]
#   assessments       list[{art:str, zeitpunkt:str, dauer:str,
#                            inhalt:str, hilfsmittel:str, weight:float}]
#   literature        list[str]
#   source_file       str   – basename of the PDF


# ── Entry points ──────────────────────────────────────────────────────────

def scrape_module_pdf(path: str | Path) -> Dict[str, Any]:
    """Scrape a single module-plan PDF.  Always returns a dict (never raises)."""
    path = Path(path)
    try:
        import pdfplumber
    except ImportError:
        # Try auto-install once
        import subprocess as _sp
        try:
            _sp.run(
                [__import__("sys").executable, "-m", "pip", "install", "pdfplumber", "--quiet"],
                check=True, capture_output=True,
            )
            import pdfplumber  # type: ignore
        except Exception as _e:
            return _empty(str(path.name), f"pdfplumber nicht installiert (auto-install fehlgeschlagen: {_e})")

    pages_text: List[str] = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for pg in pdf.pages:
                pages_text.append(pg.extract_text() or "")
    except Exception as exc:
        return _empty(str(path.name), str(exc))

    full_text = "\n".join(pages_text)
    result = _parse(full_text, pages_text, str(path.name))
    result["source_file"] = path.name
    return result


def scrape_folder(folder: str | Path) -> List[Dict[str, Any]]:
    """Scrape every PDF in *folder* and return a list of ScrapedModule dicts."""
    folder = Path(folder)
    results = []
    for pdf_path in sorted(folder.glob("*.pdf")):
        results.append(scrape_module_pdf(pdf_path))
    return results


# ── Core parser ───────────────────────────────────────────────────────────

def _parse(full: str, pages: List[str], filename: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "code": "",
        "name": "",
        "ects": 0.0,
        "semester_tag": "",
        "objectives": [],
        "content_sections": [],
        "assessments": [],
        "literature": [],
        "source_file": filename,
        "_error": "",
    }

    # ── Priority 1: extract code + name from filename (most reliable) ────
    stem = Path(filename).stem
    parts = stem.split("_", 1)
    # Accept any 2-12 char alphanumeric code (with &, -, mixed case)
    if len(parts) == 2 and re.match(r"^[A-Za-z0-9&\-]{2,12}$", parts[0]):
        result["code"] = parts[0]
        result["name"] = parts[1].replace("_", " ")
    elif len(parts) == 1:
        result["code"] = stem
        result["name"] = stem

    # ── Priority 2: refine using PDF text ───────────────────────────────
    _extract_header(full, result)
    _extract_objectives(full, result)
    _extract_content(full, result)
    _extract_assessments(full, result)
    _extract_literature(full, result)

    # Ensure code and name are set even if both sources failed
    if not result["name"]:
        result["name"] = stem.replace("_", " ")
    if not result["code"]:
        result["code"] = result["name"].split()[0] if result["name"] else stem

    return result


# ── Header: code, name, ECTS, semester ───────────────────────────────────

def _extract_header(text: str, out: dict) -> None:
    # Semester validity tag:  "Gültig ab FS26" / "Gültig ab HS25/26"
    m = re.search(r"[Gg][üu]ltig\s+ab\s+([A-Z]{2}\d{2}(?:/\d{2,4})?)", text)
    if m:
        out["semester_tag"] = m.group(1)

    # ECTS: "5 ECTS" or "5 ECTS / 150 h" or "ECTS-Credits\n5"
    m = re.search(r"(\d{1,2}(?:\.\d)?)\s*ECTS", text)
    if m:
        out["ects"] = float(m.group(1))

    # Module code: look for "Code XXX" (space, colon, or newline separated)
    # Only use this to set code if filename didn't already give a short uppercase code
    m = re.search(r"\bCode\b[\s:]+([A-ZÄÖÜa-z0-9&\-]{2,20})\b", text)
    if m:
        candidate = m.group(1).strip()
        # Prefer short uppercase codes from the PDF over filename if they look right
        if re.match(r"^[A-Z0-9&\-]{2,10}$", candidate):
            out["code"] = candidate
    # Also try "Modulplan XYZ" on same line
    m2 = re.search(r"Modulplan\s+([A-Z0-9&\-]{2,10})\b", text)
    if m2 and re.match(r"^[A-Z0-9&\-]{2,10}$", m2.group(1)):
        out["code"] = m2.group(1).strip()

    # Module full name: only extract from page-1 header area (first ~1500 chars)
    # and only if we don't already have a good filename-based name
    page1 = text[:1500]
    lines = [l.strip() for l in page1.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        # "Modulplan XYZ" where XYZ is a short code (page header style)
        if re.match(r"^Modulplan\s+[A-Za-z0-9&\-]{2,12}$", line):
            for j in range(i + 1, min(i + 6, len(lines))):
                candidate = lines[j]
                if (len(candidate) > 8
                        and not re.match(r"^(Modulplan|G[üu]ltig|Code\b|\d)", candidate)
                        and not re.match(r"^[A-Z0-9]{2,12}$", candidate)
                        and "ECTS" not in candidate):
                    out["name"] = candidate
                    break
            break


# ── Learning objectives ───────────────────────────────────────────────────

_OBJ_HEADERS = [
    r"Zu entwickelnde\s+Kompetenzen",
    r"Kompetenzen",
    r"Learning\s+Outcomes?",
    r"Lernziele",
]

_NEXT_SECTION = r"\n(?:Unterrichtssprache|Leistungsnachweis|Vorkenntnisse|Lehrmittel|1\s+Lerninhalte|Bemerkungen)"

# Bullet characters including letter "o" when followed by space (FFHS style)
_BULLET_PAT = re.compile(r"^(?:[•·\-\*–—▪◦\u2022]|o(?=\s))\s*")


def _extract_objectives(text: str, out: dict) -> None:
    for hdr in _OBJ_HEADERS:
        # Allow objectives to start on same line as header (no required \n)
        pat = re.compile(
            hdr + r"\s*(.*?)(?=" + _NEXT_SECTION + ")",
            re.DOTALL | re.IGNORECASE,
        )
        m = pat.search(text)
        if m:
            block = m.group(1)
            objs = _parse_bullet_block(block)
            if objs:
                out["objectives"] = objs
                return


def _parse_bullet_block(block: str) -> List[str]:
    """Extract bullet-point items from a text block, merging wrapped continuation lines."""
    items: List[str] = []
    current: Optional[str] = None

    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        is_bullet = bool(_BULLET_PAT.match(stripped))
        if is_bullet:
            if current is not None:
                items.append(current)
            # Strip bullet prefix
            current = _BULLET_PAT.sub("", stripped)
        else:
            # Continuation of previous bullet OR non-bullet line
            if current is not None:
                # Merge continuation (handle hyphenated line breaks)
                if current.endswith("-"):
                    current = current[:-1] + stripped
                else:
                    current = current + " " + stripped
            # else: non-bullet preamble text, skip

    if current is not None:
        items.append(current)

    # Filter out very short fragments
    return [i for i in items if len(i) > 8]


# ── Learning content ──────────────────────────────────────────────────────

_CONTENT_START = re.compile(
    r"(?:^|\n)\s*1\s+Lerninhalte|Lerninhalt\b",
    re.IGNORECASE,
)
_CONTENT_END = re.compile(
    r"(?:^|\n)\s*(?:2\s+Lehrmittel|Literatur\b|Leistungsnachweis\b)",
    re.IGNORECASE,
)


def _is_bullet_line(s: str) -> bool:
    """Return True if the line starts with a recognised bullet character."""
    return bool(_BULLET_PAT.match(s))


def _is_garbage_title(s: str) -> bool:
    """Return True if a content-section title looks like a PDF layout artefact."""
    # Page headers / footers
    if re.match(r"^\d{1,2}\.\d{2}\.\d{4}", s):   # date line
        return True
    if re.match(r"^Seite\s+\d", s):               # "Seite 2 von 4"
        return True
    if re.match(r"^Modulplan\b", s):              # repeated module header
        return True
    # Validity line ("Gültig ab FS26")
    if re.match(r"^G[üu]ltig\b", s):
        return True
    # Very short and no real content
    if len(s) < 6:
        return True
    # Ends with a hyphen word-break: "Program-", "opti-"
    if re.search(r"\w-$", s):
        return True
    # Starts lowercase → continuation fragment
    if s and s[0].islower():
        return True
    # Looks like a module full-name + date header: "GTI Grundlagen … 16.07.2025 Seite …"
    if re.search(r"\d{2}\.\d{2}\.\d{4}\s+Seite", s):
        return True
    return False


def _extract_content(text: str, out: dict) -> None:
    m_start = _CONTENT_START.search(text)
    if not m_start:
        return
    start = m_start.end()

    m_end = _CONTENT_END.search(text, start)
    block = text[start: m_end.start() if m_end else start + 4000]

    sections: List[Dict] = []
    current_section: Optional[Dict] = None
    # Buffer for merging split paragraph lines into a proper section title
    _pending_title: List[str] = []

    def _flush_pending():
        nonlocal _pending_title
        if not _pending_title:
            return
        merged = " ".join(_pending_title)
        # Remove hyphen line-breaks ("Betriebssy- stem" → "Betriebssystem")
        merged = re.sub(r"-\s+", "", merged)
        _pending_title = []
        return merged

    lines = [l.strip() for l in block.splitlines() if l.strip()]

    for stripped in lines:
        if _is_garbage_title(stripped):
            continue

        # Numbered section header like "1. Einführung in Java"
        m_sec = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if m_sec:
            merged = _flush_pending()
            if merged and current_section:
                sections.append(current_section)
            elif current_section:
                sections.append(current_section)
            current_section = {"title": m_sec.group(2).strip(), "items": []}
            continue

        if _is_bullet_line(stripped):
            # Flush any pending title first
            merged = _flush_pending()
            if merged:
                if current_section:
                    sections.append(current_section)
                current_section = {"title": merged, "items": []}
            if current_section is None:
                current_section = {"title": "Inhalte", "items": []}
            item = _BULLET_PAT.sub("", stripped)
            if item and len(item) > 3:
                current_section["items"].append(item)
        else:
            # Non-bullet, non-numbered line — could be:
            # (a) A real section title (capitalised, standalone, long enough)
            # (b) A continuation fragment from a wrapped paragraph
            # Strategy: buffer it; flush to a real section title only when we
            # encounter the next "real" content (numbered header or bullet).
            _pending_title.append(stripped)

    # Flush remaining
    merged = _flush_pending()
    if merged:
        if current_section:
            sections.append(current_section)
        current_section = {"title": merged, "items": []}
    if current_section and (current_section["items"] or len(current_section["title"]) > 10):
        sections.append(current_section)

    # Post-filter: drop sections with no bullets AND whose title looks like
    # a paragraph fragment (no capital structure, too long to be a heading, etc.)
    def _keep_section(s: Dict) -> bool:
        title = s["title"]
        if s["items"]:
            return True   # has sub-items → always keep
        # Keep short-ish proper headings (≤ 60 chars, starts with capital)
        if len(title) <= 60 and title and title[0].isupper():
            return True
        # Drop long paragraph-style sentences with no sub-items
        return False

    out["content_sections"] = [s for s in sections if _keep_section(s)]


# ── Assessments ───────────────────────────────────────────────────────────

_ASSESS_START = re.compile(
    r"(?:^|\n)\s*3\s+Leistungsnachweis|Leistungsnachweis\b",
    re.IGNORECASE,
)


def _extract_assessments(text: str, out: dict) -> None:
    m_start = _ASSESS_START.search(text)
    if not m_start:
        # Try compact overview form: "Leistungsnachweis • X (70%)"
        _extract_assessments_compact(text, out)
        return

    block = text[m_start.end():]
    assessments = _parse_assessment_block(block)
    if assessments:
        out["assessments"] = assessments
    else:
        _extract_assessments_compact(text, out)


def _parse_assessment_block(block: str) -> List[Dict]:
    """Parse detailed assessment table (Art / Zeitpunkt / Notengewicht rows)."""
    assessments: List[Dict] = []
    current: Optional[Dict] = None
    field_map = {
        "art": "art",
        "zeitpunkt": "zeitpunkt",
        "dauer": "dauer",
        "inhalt": "inhalt",
        "zugelassene hilfsmittel": "hilfsmittel",
        "notengewicht": "weight_str",
        "bewertung": "inhalt",  # DBS uses "Bewertung"
        "sonstiges": "",        # skip
        "nachprüfungsregelung": "",
    }

    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Check if line starts a new field
        matched_field = None
        for key, attr in field_map.items():
            if stripped.lower().startswith(key):
                matched_field = (key, attr, stripped[len(key):].lstrip(" \t:").strip())
                break

        if matched_field:
            key, attr, val = matched_field

            # "Art" starts a new assessment block
            if key == "art":
                if current:
                    assessments.append(_finalize_assessment(current))
                current = {"art": val, "zeitpunkt": "", "dauer": "",
                           "inhalt": "", "hilfsmittel": "", "weight_str": ""}
                continue

            if current and attr:
                current[attr] = (current.get(attr, "") + " " + val).strip()
            continue

        # Continuation line for current field (indented or continuation)
        if current and stripped:
            # Append to the last non-empty field
            for attr in ("inhalt", "hilfsmittel", "dauer"):
                if current.get(attr):
                    current[attr] = current[attr] + " " + stripped
                    break

    if current:
        assessments.append(_finalize_assessment(current))

    return assessments


def _finalize_assessment(d: dict) -> dict:
    weight = 0.0
    ws = d.pop("weight_str", "")
    m = re.search(r"(\d{1,3}(?:\.\d)?)\s*%", ws)
    if m:
        weight = float(m.group(1))
    return {
        "art": d.get("art", ""),
        "zeitpunkt": d.get("zeitpunkt", ""),
        "dauer": d.get("dauer", ""),
        "inhalt": d.get("inhalt", "")[:400],
        "hilfsmittel": d.get("hilfsmittel", "")[:200],
        "weight": weight,
    }


def _extract_assessments_compact(text: str, out: dict) -> None:
    """
    Fallback: parse compact overview form from page 1:
        • Modulprüfung (70%)
        • Kurztests (24%)
    or plain text without bullets.
    """
    # Look for patterns like "• X (NN%)" or "- X NN%"
    assessments = []
    for m in re.finditer(
        r"[•·\-\*–—▪]\s*(.+?)\s*\((\d{1,3})\s*%\)",
        text
    ):
        assessments.append({
            "art": m.group(1).strip(),
            "zeitpunkt": "", "dauer": "", "inhalt": "", "hilfsmittel": "",
            "weight": float(m.group(2)),
        })

    # Also scan for inline % patterns like "Modulprüfung 70%"
    if not assessments:
        for m in re.finditer(r"([A-ZÄÖÜa-zäöü][\w\- ]{3,40})\s{1,10}(\d{1,3})\s*%", text):
            name = m.group(1).strip()
            if len(name) > 4 and name.lower() not in ("seite", "seit", "gültig"):
                assessments.append({
                    "art": name,
                    "zeitpunkt": "", "dauer": "", "inhalt": "", "hilfsmittel": "",
                    "weight": float(m.group(2)),
                })

    if assessments and not out["assessments"]:
        out["assessments"] = assessments


# ── Literature ────────────────────────────────────────────────────────────

_LIT_START = re.compile(
    r"(?:^|\n)\s*2\s+Lehrmittel|Literatur\b",
    re.IGNORECASE,
)
_LIT_END = re.compile(
    r"(?:^|\n)\s*3\s+Leistungsnachweis|\bLeistungsnachweis\b",
    re.IGNORECASE,
)


def _extract_literature(text: str, out: dict) -> None:
    m_start = _LIT_START.search(text)
    if not m_start:
        return
    start = m_start.end()
    m_end = _LIT_END.search(text, start)
    block = text[start: m_end.start() if m_end else start + 2000]

    items = []
    for line in block.splitlines():
        stripped = line.strip()
        # Skip header lines
        if not stripped or len(stripped) < 10:
            continue
        if re.match(r"^(Lehrmittel|Art der Beschaffung|Moodle|Digitale|Selbst|Von FFHS)", stripped):
            continue
        # Clean leading number/bracket like "[1]"
        stripped = re.sub(r"^\[?\d+\]?\s*", "", stripped)
        if len(stripped) > 10:
            items.append(stripped)

    out["literature"] = items[:10]  # cap at 10


# ── Helpers ───────────────────────────────────────────────────────────────

def _empty(filename: str, error: str) -> Dict[str, Any]:
    stem = Path(filename).stem
    parts = stem.split("_", 1)
    if len(parts) == 2 and re.match(r"^[A-Za-z0-9&\-]{2,12}$", parts[0]):
        code = parts[0]
        name = parts[1].replace("_", " ")   # "Analyse mit Python", not "AnPy Analyse…"
    else:
        code = stem[:12]
        name = stem.replace("_", " ")
    return {
        "code": code,
        "name": name,
        "ects": 0.0,
        "semester_tag": "",
        "objectives": [],
        "content_sections": [],
        "assessments": [],
        "literature": [],
        "source_file": filename,
        "_error": error,
    }
