"""Color management, theme switching, and grade-based color helpers."""
from __future__ import annotations

from semetra.gui import state


# ── Accent-colour presets ──────────────────────────────────────────────────
# Each entry: base, d1-d4 (darker), l1-l5 (lighter).
ACCENT_PRESETS: dict = {
    "violet": {
        "base": "#7C3AED", "d1": "#6D28D9", "d2": "#5B21B6", "d3": "#4C1D95",
        "d4": "#2D1B69", "l1": "#A78BFA", "l2": "#C4B5FD", "l3": "#DDD6FE",
        "l4": "#EDE9FE", "l5": "#F3E8FF",
    },
    "ocean": {
        "base": "#2563EB", "d1": "#1D4ED8", "d2": "#1E40AF", "d3": "#1E3A8A",
        "d4": "#1E2D5A", "l1": "#60A5FA", "l2": "#93C5FD", "l3": "#BFDBFE",
        "l4": "#DBEAFE", "l5": "#EFF6FF",
    },
    "forest": {
        "base": "#059669", "d1": "#047857", "d2": "#065F46", "d3": "#064E3B",
        "d4": "#022C22", "l1": "#34D399", "l2": "#6EE7B7", "l3": "#A7F3D0",
        "l4": "#D1FAE5", "l5": "#ECFDF5",
    },
    "sunset": {
        "base": "#EA580C", "d1": "#C2410C", "d2": "#9A3412", "d3": "#7C2D12",
        "d4": "#431407", "l1": "#FB923C", "l2": "#FDBA74", "l3": "#FED7AA",
        "l4": "#FFEDD5", "l5": "#FFF7ED",
    },
    "rose": {
        "base": "#DB2777", "d1": "#BE185D", "d2": "#9D174D", "d3": "#831843",
        "d4": "#4A0E28", "l1": "#F472B6", "l2": "#F9A8D4", "l3": "#FBCFE8",
        "l4": "#FCE7F3", "l5": "#FDF2F8",
    },
    "slate": {
        "base": "#475569", "d1": "#334155", "d2": "#1E293B", "d3": "#0F172A",
        "d4": "#0A0F1A", "l1": "#94A3B8", "l2": "#CBD5E1", "l3": "#E2E8F0",
        "l4": "#F1F5F9", "l5": "#F8FAFC",
    },
}

ACCENT_PRESET_LABELS: list = [
    ("🟣  Violet  (Standard)", "violet"),
    ("🔵  Ocean Blue",         "ocean"),
    ("🟢  Forest Green",       "forest"),
    ("🟠  Sunset Orange",      "sunset"),
    ("🌸  Rose Pink",          "rose"),
    ("⬛  Slate Grey",         "slate"),
]


def set_accent(preset: str) -> None:
    """Set the current accent colour preset."""
    if preset in ACCENT_PRESETS:
        state._ACCENT_PRESET = preset


def get_accent_color() -> str:
    """Return the current primary accent hex colour."""
    return ACCENT_PRESETS.get(state._ACCENT_PRESET, ACCENT_PRESETS["violet"])["base"]


def set_theme(t: str) -> None:
    """Set the current theme ('light' or 'dark')."""
    state._THEME = t


def _tc(light: str, dark: str) -> str:
    """Return the light or dark colour string based on the active theme."""
    return dark if state._THEME == "dark" else light


def _hex_rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB + float alpha (0-1) → proper rgba() string for QSS.

    Qt interprets 8-digit hex as #AARRGGBB (not #RRGGBBAA), so we must use
    rgba() to get semi-transparent tinted backgrounds.
    """
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    else:
        r, g, b = 128, 128, 128   # fallback
    return f"rgba({r},{g},{b},{alpha:.2f})"


# ── Swiss FH Grading Helpers ────────────────────────────────────────────────
# FFHS / Swiss FH grade scale: 1.0 (worst) – 6.0 (best), passing ≥ 4.0
# Conversion formula:  Note = (Punkte / MaxPunkte) × 5 + 1
# → 60 % →  Note 4.0  (Bestehensgrenze)
# → 80 % →  Note 5.0  (Gut)
# → 100% →  Note 6.0  (Sehr gut)


def pct_to_ch_grade(pct: float) -> float:
    """Convert percentage (0–100) to Swiss FH grade (1.0–6.0).
    Result is NOT rounded — use for display rounding separately."""
    return (pct / 100.0) * 5.0 + 1.0


def ch_grade_rounded(pct: float) -> float:
    """Convert percentage to Swiss FH grade rounded to nearest 0.5 step."""
    raw = pct_to_ch_grade(pct)
    return round(raw * 2) / 2


def _grade_color(grade: float) -> str:
    """Theme-adaptive text colour for a Swiss 1–6 grade."""
    if grade >= 5.5: return _tc("#1B5E20", "#69F0AE")   # excellent  (deep/bright green)
    if grade >= 5.0: return _tc("#2E7D32", "#4CAF50")   # good
    if grade >= 4.5: return _tc("#558B2F", "#8BC34A")   # satisfactory
    if grade >= 4.0: return _tc("#E65100", "#FFA726")   # just passing (amber)
    if grade >= 3.5: return _tc("#BF360C", "#FF7043")   # at risk      (deep orange)
    return _tc("#B71C1C", "#EF5350")                     # fail          (red)


def _grade_bg(grade: float) -> str:
    """Subtle card background colour for a Swiss grade (theme-adaptive)."""
    if grade >= 5.5: return _tc("#E8F5E9", "#1B3A2B")
    if grade >= 5.0: return _tc("#F1F8E9", "#1A2E1A")
    if grade >= 4.5: return _tc("#F9FBE7", "#1E2A10")
    if grade >= 4.0: return _tc("#FFF3E0", "#3A2200")
    if grade >= 3.5: return _tc("#FBE9E7", "#3A1800")
    return _tc("#FFEBEE", "#3A0000")


def _grade_border(grade: float) -> str:
    """Card border colour for a Swiss grade."""
    if grade >= 5.5: return _tc("#A5D6A7", "#388E3C")
    if grade >= 5.0: return _tc("#C5E1A5", "#558B2F")
    if grade >= 4.5: return _tc("#DCE775", "#827717")
    if grade >= 4.0: return _tc("#FFCC80", "#E65100")
    if grade >= 3.5: return _tc("#FFAB91", "#BF360C")
    return _tc("#EF9A9A", "#B71C1C")


def _grade_label(grade: float) -> str:
    """Human-readable status label for Swiss 1–6 grade."""
    if grade >= 5.5: return "Sehr gut"
    if grade >= 5.0: return "Gut"
    if grade >= 4.5: return "Befriedigend"
    if grade >= 4.0: return "Genügend"
    if grade >= 3.5: return "⚠ Gefährdet!"
    return "✗ Nicht bestanden"


def _grade_icon(grade: float) -> str:
    """Emoji icon for Swiss grade status."""
    if grade >= 5.5: return "✨"
    if grade >= 5.0: return "✅"
    if grade >= 4.5: return "🟢"
    if grade >= 4.0: return "🟡"
    if grade >= 3.5: return "🟠"
    return "🔴"
