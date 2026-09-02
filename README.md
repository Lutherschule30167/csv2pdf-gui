# StarMoney-Kontoauszug-Generator (Windows-Portierung)

Python-Neuimplementierung des Original-Bash-Skripts fuer die Lutherschule
Hannover. Erzeugt aus StarMoney-CSV-Exporten formatierte PDF-Kontoauszuege
mit Kopfbereich (Logo/Kontoname/Datum) - lauffaehig unter Windows, ohne die
Linux-Kommandozeilentools des Originals (ghostscript, paps, ImageMagick,
qpdf, iconv, column, curl, perl-rename). Alles passiert direkt in Python.

In StarMoney muss zur Nutzung dieses Tools vor dem Export eine CSV Spalten-
konfiguration unter Verwaltung/Datenexport angelegt werden. Hierfuer muessen 
die Spalten Buchungstag, Beguenstigter/Absender - Name, Betrag und Saldo 
ausgewaehlt werden.

## Installation (einmalig)

1. Python installieren: https://www.python.org/downloads/windows/
   Beim Installer unbedingt **"Add python.exe to PATH"** ankreuzen.
2. Abhaengigkeit installieren (Eingabeaufforderung / PowerShell):
   ```
   pip install -r requirements.txt
   ```
   (einzige Abhaengigkeit: `reportlab`)

## Benutzung - grafische Oberflaeche (fuer Endbenutzer)

Doppelklick auf `start_gui.bat` (oder `python starmoney_gui.py`) oeffnet ein
Fenster:

1. **"Ordner waehlen..."** - Ordner mit den StarMoney-CSV-Exporten auswaehlen
   (wird gemerkt, muss beim naechsten Start nicht erneut gewaehlt werden).
2. Haekchen setzen, falls die Original-CSVs danach geloescht werden sollen
   (Standard: aus - CSVs bleiben erhalten).
3. **"Kontoauszuege erstellen"** klicken. Der Fortschritt und alle Meldungen
   erscheinen im Protokollfeld; am Ende gibt es eine kurze Zusammenfassung.
4. **"Ordner oeffnen"** oeffnet den Ordner mit den fertigen PDFs im
   Explorer.

`starmoney_gui.py` benoetigt `starmoney_export.py` im selben Ordner (nutzt
dessen Logik direkt) sowie `tkinter`, das im offiziellen Windows-Installer
von python.org standardmaessig enthalten ist (bei einer benutzerdefinierten
Installation darauf achten, dass "tcl/tk and IDLE" angehakt bleibt).

## Benutzung - Kommandozeile

```
python starmoney_export.py [Exportverzeichnis] [--delete-csv]
```

- Ohne Pfadangabe wird der Ordner `export_auszuege` neben dem Skript
  verwendet - dort die StarMoney-CSV-Exporte hineinlegen.
- `--delete-csv` loescht die Original-CSVs nach erfolgreicher Verarbeitung
  (so wie im Original-Bash-Skript). **Ohne** dieses Flag bleiben die
  CSV-Originale erhalten - das ist der sicherere Standard dieser
  Portierung und weicht bewusst vom Original ab.
- Alternativ Doppelklick auf `start_export.bat` (nutzt den Ordner
  `export_auszuege` neben der .bat-Datei, ohne GUI).

Die fertigen PDFs landen als `<Konto>_<Datum>.pdf` im selben Verzeichnis.

## Was 1:1 uebernommen wurde

- **Encoding-Fix**: UTF-8-BOM wird entfernt, Encoding wird pro Datei erkannt
  (gueltiges UTF-8 oder sonst Windows-1252), einzelne kaputte Bytes werden
  verworfen statt die ganze Datei zu verlieren - genau das Problem mit den
  Umlauten aus dem Original ist damit geloest.
- **Tages-Gruppierung/Sortierung**: Buchungen werden pro Tag gruppiert;
  innerhalb eines Tages erst Gutschriften aufsteigend, dann Abbuchungen
  absteigend (Original-AWK-Logik 1:1 nachgebaut). Die Tagesgruppen selbst
  erscheinen in umgekehrter Reihenfolge (neuestes Datum oben).
- **Dateiname kuerzen**: identische Regel wie im Original (`rename`-Regex) -
  bei genau 5 durch "_" getrennten Teilen werden nur Teil 1 und Teil 4
  behalten (z.B. Kontoname + Datum).
- **Logo**: gleiche URL wie im Original, wird einmalig im Exportverzeichnis
  zwischengespeichert.

## Wo es funktional aequivalent, aber technisch anders geloest ist

- Kopfbereich (Logo, Kontoname, Datum, Hinweistext) wird direkt beim
  PDF-Bau auf Seite 1 gezeichnet, statt separat als Kopf-PDF erzeugt und per
  `qpdf --underlay` untergelegt zu werden. Optisch/funktional das Gleiche,
  ohne die drei externen Tools.
- Statt `paps`+Ghostscript wird der Text direkt mit `reportlab` in
  Monospace-Schrift (Courier 7pt, A4 Hochformat, oben Platz fuer den
  Kopfbereich auf Seite 1) gesetzt.

## Eine Stelle, die ich nicht zu 100 % pruefen konnte

Die Spaltenausrichtung (`column -t ... -T 5 -E 2 -R 3,4 -l 12`) habe ich
funktional nachgebaut: Spalte 2/3/4 exakt wie im Original auf 30/10/10
Zeichen fixiert, alle weiteren Spalten (1, 5, ...) dynamisch wie bei
`column -t` auf die laengste vorkommende Breite ausgerichtet, Gesamtbreite
auf 120 Zeichen gedeckelt (Spalte 5 wird bei Bedarf gekuerzt, wie `-T 5`
im Original). Das ist aus dem Skript sauber ableitbar und mit Testdaten
durchgetestet - ich kenne aber das genaue Spaltenlayout eurer echten
StarMoney-Exporte nicht. Am besten einmal mit einer echten (ggf.
anonymisierten) Beispiel-CSV gegenchecken, ob die Spaltenbreiten so
passen, wie ihr sie gewohnt seid.

## Eigenstaendige .exe (optional)

Falls kein Python auf den Zielrechnern installiert werden soll, laesst
sich daraus mit PyInstaller eine eigenstaendige .exe bauen - das muss
allerdings auf einem Windows-Rechner passieren (PyInstaller kompiliert
nicht plattformuebergreifend):

```
pip install pyinstaller
pyinstaller --onefile starmoney_export.py
```

Die fertige .exe liegt danach in `dist\starmoney_export.exe`.

Fuer die GUI analog:
```
pyinstaller --onefile --windowed --add-data "starmoney_export.py;." starmoney_gui.py
```
(`--windowed` unterdrueckt das Konsolenfenster; `--add-data` bettet
`starmoney_export.py` mit ein, falls PyInstaller es nicht automatisch
findet - im Zweifel beide .py-Dateien einfach im selben Ordner lassen.)
