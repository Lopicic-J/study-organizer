#!/bin/bash
# Study Organizer starten
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
python -m study_organizer
