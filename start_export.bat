@echo off
REM Doppelklick-Starter fuer Windows.
REM Erwartet Python im PATH (Installer-Option "Add python.exe to PATH").
cd /d "%~dp0"
python starmoney_export.py export_auszuege
pause
