#!/bin/bash
# Doppelklick-Starter für macOS (Kommandozeilenversion, nutzt den Ordner
# "export_auszuege" neben dieser Datei).
cd "$(dirname "$0")"
python3 starmoney_export.py export_auszuege
read -p "Fertig - Enter zum Schließen drücken..."
