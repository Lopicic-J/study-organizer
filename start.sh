#!/bin/bash
# Semetra starten
# Dieses Skript aus dem Projektordner ausführen:
#   bash start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f ".venv/bin/activate" ]; then
    echo "Fehler: .venv nicht gefunden. Bitte zuerst ausführen:"
    echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi

source .venv/bin/activate

# WSLg (Windows Subsystem for Linux GUI) compatibility:
# Use Wayland backend only when a Wayland compositor is actually running.
# Forcing it unconditionally causes a segfault when only X11/XCB is available.
# Note: drag-to-edge snap is not possible on Wayland (compositor controls window
# positioning during drag). Use Win+Left/Right/Up/Down keyboard shortcuts instead.
if [ -z "$QT_QPA_PLATFORM" ]; then
    if [ -n "$WAYLAND_DISPLAY" ] || [ "$XDG_SESSION_TYPE" = "wayland" ]; then
        export QT_QPA_PLATFORM=wayland
    fi
fi

# Auto-install any missing dependencies declared in pyproject.toml
python -c "import pdfplumber" 2>/dev/null || pip install pdfplumber -q
python -c "import openpyxl"   2>/dev/null || pip install openpyxl   -q

python -m semetra

# Auto-install web scraper dependencies
python -c "import anthropic"    2>/dev/null || pip install anthropic    -q
python -c "import requests"     2>/dev/null || pip install requests      -q
python -c "import bs4"          2>/dev/null || pip install beautifulsoup4 -q
