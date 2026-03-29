"""
University Web Scraper — pure Python, zero external AI dependency.

Extracts module plans from Swiss FH websites (FFHS, OST, ZHAW, BFH, HSLU, …)
using heuristic table/list/text analysis.  No API key needed — runs 100 % locally.

Supported extraction strategies (tried in order):
  1. HTML table detection  — best for structured module-plan pages
  2. Definition-list / dl  — some FHs use <dl><dt><dd> for module details
  3. Heading + metadata    — h2/h3 headings followed by ECTS/Semester info
  4. Regex text patterns   — fallback for unstructured pages

Crawl behaviour:
  • BFS from start URL, follows only in-domain links that look like study/module pages
  • MAX_PAGES = 25, MAX_DEPTH = 3
  • Tries requests first, optionally falls back to Playwright for JS-rendered pages
"""

from __future__ import annotations

import re
import time
import logging
from typing import List, Dict, Any, Optional, Callable, Tuple
from urllib.parse import urljoin, urlparse
from collections import deque

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Regex patterns
# ─────────────────────────────────────────────────────────────────────────────

_ECTS_RE = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(?:ECTS|KP|CP|Credits?|Kreditpunkte)',
    re.IGNORECASE,
)
_ECTS_BARE = re.compile(r'^\s*(\d+(?:[.,]\d+)?)\s*$')

_SEM_PATTERNS = [
    re.compile(r'(\d+)\.\s*(?:Semester|Sem\.?)', re.IGNORECASE),
    re.compile(r'Semester\s+(\d+)', re.IGNORECASE),
    re.compile(r'\bSem(?:ester)?\s*(\d+)\b', re.IGNORECASE),
    re.compile(r'\b(\d+)\s*\.\s*Sem\b', re.IGNORECASE),
]
_SEM_BARE = re.compile(r'^\s*(\d{1,2})\s*$')

# ─────────────────────────────────────────────────────────────────────────────
#  Keyword sets
# ─────────────────────────────────────────────────────────────────────────────

_HEADER_MODULE = {'modul', 'module', 'fach', 'subject', 'bezeichnung',
                  'lehrveranstaltung', 'title', 'titre', 'name', 'modulbezeichnung'}
_HEADER_CODE   = {'code', 'kürzel', 'abkürzung', 'id', 'nr', 'nummer', 'abk'}
_HEADER_ECTS   = {'ects', 'kp', 'cp', 'credits', 'punkte', 'kreditpunkte',
                  'leistungspunkte', 'anrechnungspunkte'}
_HEADER_SEM    = {'semester', 'sem', 'period', 'periode', 'term', 'studienjahr'}
_HEADER_TYPE   = {'typ', 'type', 'art', 'kategorie', 'category', 'pflicht',
                  'modultyp', 'modulkategorie'}

_TYPE_MAP: Dict[str, str] = {}
for _kw in ['pflicht', 'compulsory', 'mandatory', 'obligatoire', 'required', 'core',
            'kern', 'grundlagen', 'basis', 'grund']:
    _TYPE_MAP[_kw] = 'pflicht'
for _kw in ['wahl', 'elective', 'optional', 'optionnel', 'choice', 'freiwillig',
            'wahlpflicht', 'ergänzung', 'complement']:
    _TYPE_MAP[_kw] = 'wahl'
for _kw in ['vertiefung', 'specialisation', 'specialization', 'spécialisation',
            'major', 'minor', 'schwerpunkt', 'profil', 'profile']:
    _TYPE_MAP[_kw] = 'vertiefung'

_LINK_KEYWORDS = re.compile(
    r'modul|lehrplan|studienplan|curriculum|module|subject|course|semester|'
    r'stundenplan|fach|leistung|kredit|credit|bachelor|master|informatik|'
    r'wirtschaft|ingenieur|programme|program|overview|studium|studiengang',
    re.IGNORECASE,
)
_LINK_SKIP = re.compile(
    r'\.pdf$|\.jpg$|\.png$|\.docx?$|\.xlsx?$|'
    r'login|logout|signin|signout|register|imprint|impressum|'
    r'datenschutz|privacy|contact|kontakt|news|blog|jobs|career|'
    r'facebook|twitter|linkedin|youtube|instagram',
    re.IGNORECASE,
)

MAX_PAGES = 25
MAX_DEPTH = 3
REQUEST_DELAY = 0.4


# ─────────────────────────────────────────────────────────────────────────────
#  Main scraper class
# ─────────────────────────────────────────────────────────────────────────────

class UniversityWebScraper:
    """
    Heuristic scraper for university module plans.
    No external API needed — fully self-contained.
    """

    def __init__(self):
        self._visited: set = set()
        self._modules: Dict[str, Dict[str, Any]] = {}

    def scrape(
        self,
        start_url: str,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Crawl start_url and return a list of module dicts compatible with
        repo.add_module().  Each dict contains at minimum:
          name, semester (int), ects (float), module_type, status, in_plan
        """
        self._visited.clear()
        self._modules.clear()
        cb = progress_cb or (lambda _: None)

        cb(f"Starte Crawl: {start_url}")
        pages = self._crawl(start_url, cb)
        cb(f"{len(pages)} Seiten gescraped — analysiere Inhalte …")

        for url, html in pages:
            cb(f"Extrahiere Module aus: {url}")
            found = self._extract(html, url)
            for m in found:
                key = m['name'].strip().lower()
                if key and key not in self._modules:
                    self._modules[key] = m

        result = list(self._modules.values())
        result.sort(key=lambda m: (m.get('semester', 99), m.get('name', '')))
        cb(f"Fertig — {len(result)} Module gefunden.")
        return result

    # ── Crawler ───────────────────────────────────────────────────────────

    def _crawl(self, start_url: str, cb: Callable) -> List[Tuple[str, str]]:
        base = urlparse(start_url)
        allowed_netloc = base.netloc
        queue: deque = deque([(start_url, 0)])
        self._visited.add(start_url)
        pages: List[Tuple[str, str]] = []

        while queue and len(pages) < MAX_PAGES:
            url, depth = queue.popleft()
            cb(f"[{len(pages)+1}/{MAX_PAGES}] Lade: {url}")
            html = self._fetch(url)
            if not html:
                continue
            pages.append((url, html))
            time.sleep(REQUEST_DELAY)

            if depth >= MAX_DEPTH:
                continue

            for link in self._extract_links(html, url, allowed_netloc):
                if link not in self._visited:
                    self._visited.add(link)
                    queue.append((link, depth + 1))

        return pages

    def _fetch(self, url: str) -> Optional[str]:
        try:
            import requests
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/122.0.0.0 Safari/537.36'
                ),
                'Accept-Language': 'de-CH,de;q=0.9,en;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            if resp.status_code == 200:
                try:
                    return resp.content.decode('utf-8')
                except Exception:
                    return resp.text
        except Exception as exc:
            log.debug("requests failed for %s: %s", url, exc)
        return self._fetch_playwright(url)

    def _fetch_playwright(self, url: str) -> Optional[str]:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=20_000, wait_until='domcontentloaded')
                page.wait_for_timeout(1500)
                html = page.content()
                browser.close()
                return html
        except Exception as exc:
            log.debug("playwright failed for %s: %s", url, exc)
            return None

    def _extract_links(self, html: str, base_url: str, allowed_netloc: str) -> List[str]:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
        except Exception:
            return []
        links: List[str] = []
        for tag in soup.find_all('a', href=True):
            href = tag['href'].strip()
            if not href or href.startswith('#') or href.startswith('mailto:'):
                continue
            full = urljoin(base_url, href).split('#')[0].split('?')[0]
            parsed = urlparse(full)
            if parsed.netloc != allowed_netloc:
                continue
            if _LINK_SKIP.search(full):
                continue
            if not _LINK_KEYWORDS.search(full) and not _LINK_KEYWORDS.search(tag.get_text()):
                continue
            links.append(full)
        return links

    # ── Extraction dispatcher ─────────────────────────────────────────────

    def _extract(self, html: str, url: str) -> List[Dict[str, Any]]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup.find_all(['script', 'style', 'nav', 'footer',
                                   'header', 'aside', 'noscript']):
            tag.decompose()

        results: List[Dict[str, Any]] = []

        # 1. Tables (most reliable for structured FH pages)
        results.extend(self._extract_tables(soup))

        # 2. Definition lists
        if len(results) < 3:
            results.extend(self._extract_definition_lists(soup))

        # 3. Heading blocks
        if len(results) < 3:
            results.extend(self._extract_heading_blocks(soup))

        # 4. Raw text regex fallback
        if not results:
            text = soup.get_text(separator='\n')
            results.extend(self._extract_text_patterns(text))

        return results

    # ── Strategy 1: HTML tables ───────────────────────────────────────────

    def _extract_tables(self, soup) -> List[Dict[str, Any]]:
        modules: List[Dict[str, Any]] = []
        for table in soup.find_all('table'):
            cols = self._identify_table_columns(table)
            if cols.get('name') is None:
                continue
            rows = table.find_all('tr')
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                m = self._cells_to_module(cells, cols)
                if m:
                    modules.append(m)
        return modules

    def _identify_table_columns(self, table) -> Dict[str, int]:
        header_row = table.find('tr')
        if not header_row:
            return {}
        headers = [th.get_text(strip=True).lower()
                   for th in header_row.find_all(['th', 'td'])]
        if not headers:
            return {}

        cols: Dict[str, int] = {}
        for i, h in enumerate(headers):
            h = h.strip().rstrip(':')
            if any(kw in h for kw in _HEADER_MODULE):
                cols.setdefault('name', i)
            if any(kw in h for kw in _HEADER_CODE):
                cols.setdefault('code', i)
            if any(kw in h for kw in _HEADER_ECTS):
                cols.setdefault('ects', i)
            if any(kw in h for kw in _HEADER_SEM):
                cols.setdefault('semester', i)
            if any(kw in h for kw in _HEADER_TYPE):
                cols.setdefault('type', i)

        if 'name' not in cols or len(cols) < 2:
            return {}
        return cols

    def _cells_to_module(
        self, cells: list, cols: Dict[str, int]
    ) -> Optional[Dict[str, Any]]:
        def cell_text(idx: int) -> str:
            if idx >= len(cells):
                return ''
            return cells[idx].get_text(separator=' ', strip=True)

        name = cell_text(cols['name'])
        if not name or len(name) < 3 or len(name) > 140:
            return None
        if name.lower() in _HEADER_MODULE:
            return None

        ects = 0.0
        if 'ects' in cols:
            ects = _parse_ects(cell_text(cols['ects']))
        if ects <= 0:
            ects = _parse_ects(name)
        ects = ects if ects > 0 else 3.0

        sem = 0
        if 'semester' in cols:
            sem = _parse_semester(cell_text(cols['semester']))
        if sem == 0:
            sem = _parse_semester(name)
        sem = sem if sem > 0 else 1

        mt = 'pflicht'
        if 'type' in cols:
            mt = _detect_type(cell_text(cols['type']))
        else:
            mt = _detect_type(name)

        m: Dict[str, Any] = {
            'name':        name,
            'ects':        ects,
            'semester':    sem,
            'module_type': mt,
            'status':      'planned',
            'in_plan':     1,
        }
        if 'code' in cols:
            m['code'] = cell_text(cols['code'])
        return m

    # ── Strategy 2: Definition lists ─────────────────────────────────────

    def _extract_definition_lists(self, soup) -> List[Dict[str, Any]]:
        modules: List[Dict[str, Any]] = []
        for dl in soup.find_all('dl'):
            items: Dict[str, str] = {}
            cur_key: Optional[str] = None
            for child in dl.children:
                tag = getattr(child, 'name', None)
                if tag == 'dt':
                    cur_key = child.get_text(strip=True).lower()
                    items[cur_key] = ''
                elif tag == 'dd' and cur_key:
                    items[cur_key] = child.get_text(separator=' ', strip=True)

            name = (items.get('modul') or items.get('module') or
                    items.get('name') or items.get('bezeichnung') or
                    items.get('modulbezeichnung') or '')
            if not name or len(name) < 3:
                continue

            ects_raw = (items.get('ects') or items.get('kp') or
                        items.get('credits') or items.get('kreditpunkte') or '')
            sem_raw  = items.get('semester') or items.get('sem') or ''
            type_raw = (items.get('typ') or items.get('type') or
                        items.get('art') or items.get('modultyp') or '')

            modules.append({
                'name':        name,
                'code':        items.get('code') or items.get('kürzel') or '',
                'ects':        _parse_ects(ects_raw) or 3.0,
                'semester':    _parse_semester(sem_raw) or 1,
                'module_type': _detect_type(type_raw or name),
                'status':      'planned',
                'in_plan':     1,
            })
        return modules

    # ── Strategy 3: Heading blocks ────────────────────────────────────────

    def _extract_heading_blocks(self, soup) -> List[Dict[str, Any]]:
        modules: List[Dict[str, Any]] = []
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            name = heading.get_text(separator=' ', strip=True)
            if not name or len(name) < 4 or len(name) > 100:
                continue
            if not re.search(r'[A-Za-zÄÖÜäöüÀ-ž]{3,}', name):
                continue

            context_parts: List[str] = []
            sib = heading.next_sibling
            for _ in range(8):
                if sib is None:
                    break
                if hasattr(sib, 'name') and sib.name in ('h1', 'h2', 'h3'):
                    break
                text = (sib.get_text(separator=' ', strip=True)
                        if hasattr(sib, 'get_text') else str(sib))
                context_parts.append(text)
                sib = sib.next_sibling
            context = ' '.join(context_parts)

            ects = _parse_ects(context) or _parse_ects(name)
            sem  = _parse_semester(context) or _parse_semester(name)
            if not ects and not sem:
                continue

            modules.append({
                'name':        name,
                'ects':        ects or 3.0,
                'semester':    sem or 1,
                'module_type': _detect_type(context + ' ' + name),
                'status':      'planned',
                'in_plan':     1,
            })
        return modules

    # ── Strategy 4: Text regex fallback ──────────────────────────────────

    def _extract_text_patterns(self, text: str) -> List[Dict[str, Any]]:
        modules: List[Dict[str, Any]] = []
        for line in text.split('\n'):
            line = line.strip()
            if len(line) < 5 or len(line) > 140:
                continue
            m_ects = _ECTS_RE.search(line)
            if not m_ects:
                continue
            ects = float(m_ects.group(1).replace(',', '.'))
            name = _ECTS_RE.sub('', line).strip(' -–|/\\')
            name = re.sub(r'\s{2,}', ' ', name).strip()
            if not name or len(name) < 3:
                continue
            modules.append({
                'name':        name,
                'ects':        ects,
                'semester':    _parse_semester(line) or 1,
                'module_type': _detect_type(line),
                'status':      'planned',
                'in_plan':     1,
            })
        return modules


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_ects(text: str) -> float:
    if not text:
        return 0.0
    m = _ECTS_RE.search(text)
    if m:
        return float(m.group(1).replace(',', '.'))
    m2 = _ECTS_BARE.match(text)
    if m2:
        val = float(m2.group(1).replace(',', '.'))
        if 0.5 <= val <= 30:
            return val
    return 0.0


def _parse_semester(text: str) -> int:
    if not text:
        return 0
    for pat in _SEM_PATTERNS:
        m = pat.search(text)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 12:
                return val
    m2 = _SEM_BARE.match(text.strip())
    if m2:
        val = int(m2.group(1))
        if 1 <= val <= 12:
            return val
    return 0


def _detect_type(text: str) -> str:
    text_l = text.lower()
    for kw, mt in _TYPE_MAP.items():
        if kw in text_l:
            return mt
    return 'pflicht'


def check_dependencies() -> List[str]:
    """Return list of missing package names. Empty = all good."""
    missing: List[str] = []
    try:
        import requests  # noqa: F401
    except ImportError:
        missing.append('requests')
    try:
        from bs4 import BeautifulSoup  # noqa: F401
    except ImportError:
        missing.append('beautifulsoup4')
    return missing
