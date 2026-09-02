@echo off
REM Doppelklick-Starter fuer die grafische Oberflaeche unter Windows.
REM Erwartet Python im PATH (Installer-Option "Add python.exe to PATH").
cd /d "%~dp0"
start "" pythonw starmoney_gui.py
