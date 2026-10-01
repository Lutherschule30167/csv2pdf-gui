@echo off
REM Baut die Windows-EXEs lokal (dieselben Befehle wie der GitHub-Workflow
REM .github\workflows\build-windows-exe.yml). Ergebnis liegt in dist\.
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller Pillow || goto :fehler
python make_version_info.py || goto :fehler
python -m PyInstaller --noconfirm --clean --onefile --windowed --icon csv2pdf.ico --version-file version_info.txt --add-data "csv2pdf.ico;." --name csv2pdf-gui starmoney_gui.py || goto :fehler
python -m PyInstaller --noconfirm --clean --onefile --console --icon csv2pdf.ico --version-file version_info.txt --name csv2pdf starmoney_export.py || goto :fehler
echo.
echo Fertig: dist\csv2pdf-gui.exe und dist\csv2pdf.exe
pause
exit /b 0
:fehler
echo.
echo Build fehlgeschlagen.
pause
exit /b 1
