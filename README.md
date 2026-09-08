# StarMoney-Kontoauszug-Generator (Windows-Portierung)

Python-Neuimplementierung des Original-Bash-Skripts fuer die Lutherschule
Hannover. Erzeugt aus StarMoney-CSV-Exporten formatierte PDF-Kontoauszuege
mit Kopfbereich (Logo/Kontoname/Datum) - lauffaehig unter Windows, ohne die
Linux-Kommandozeilentools des Originals (ghostscript, paps, ImageMagick,
qpdf, iconv, column, curl, perl-rename). Alles passiert direkt in Python.

## Vorbereitung in StarMoney

In Starmoney ist es notwendig, unter Verwaltung/Datenexport/CSV-Spaltenkonfiguration ein Exporttemplate mit den Spalten "Buchungstag", "Begünstigter/Absender - Name", "Betrag" und "Saldo" anzulegen. Nur CSVs in diesem Format werden aktuell korrekt verarbeitet.

## Installation (einmalig)

1. Python installieren: https://www.python.org/downloads/windows/
   Beim Installer unbedingt **"Add python.exe to PATH"** ankreuzen.
2. Abhaengigkeit installieren (Eingabeaufforderung / PowerShell):
   ```
   pip install -r requirements.txt
   ```
   (einzige Abhaengigkeit: `reportlab`)
3. Optional, nur fuer die GUI-Logovorschau: `pip install Pillow`. Ohne
   Pillow funktioniert die Vorschau fuer PNG/GIF trotzdem (tkinter kann
   das von Haus aus); erst bei JPG/BMP als Logo-Format braucht es Pillow
   fuer eine Vorschau (die Verarbeitung/PDF-Erzeugung selbst funktioniert
   mit allen genannten Formaten auch ohne Pillow).

## Logo und Kopf-Schriftart einstellen

Kein festes Schullogo mehr eingebaut - beides ist frei konfigurierbar:

- **Logo:** eine beliebige lokale Bilddatei (PNG/JPG/GIF/BMP). Leer lassen
  = kein Logo im Kopfbereich. Wird im PDF-Kopfbereich auf maximal
  78×60 pt (≈156×120 Pixel) skaliert, Seitenverhältnis bleibt erhalten -
  das entspricht exakt der bisherigen Größe des Lutherschullogos. Größere
  Logos werden also automatisch verkleinert, kleinere nicht künstlich
  vergrößert (sonst wirkt das schnell pixelig). In der GUI wird direkt eine
  Vorschau des gewählten Logos angezeigt (Format/Auflösung egal - die
  Vorschau zeigt bereits, wie es proportional im PDF landet).
- **Kopf-Schriftart** (Kontoname/Datum/Hinweistext): entweder eine der drei
  PDF-Standardschriften **Helvetica**, **Times-Roman** oder **Courier**
  (brauchen keine externe Datei), oder eine eigene **.ttf/.otf-Datei**
  (hat Vorrang, falls angegeben). Die Buchungstabelle selbst bleibt bewusst
  immer Courier (Monospace), da die Spaltenausrichtung darauf aufbaut.

In der GUI: alle Felder liegen unter **Optionen -> Einstellungen** und
werden sofort bei jeder Aenderung (Auswahl, Entfernen, Verlassen eines
Feldes) automatisch in `config.json` gespeichert - nicht erst beim Klick
auf "Kontoauszuege erstellen".

Auf der Kommandozeile:
```
python starmoney_export.py --logo "C:\Pfad\logo.png" --header-font Times-Roman --save-config
python starmoney_export.py --logo "" --header-font-file "C:\Pfad\Schrift.ttf" --save-config
```
`--save-config` schreibt die Werte dauerhaft nach `config.json` (liegt
neben dem Skript, einfacher Text/JSON, kann bei Bedarf auch von Hand
bearbeitet werden). Ohne `--save-config` gilt die Angabe nur fuer diesen
einen Aufruf.

## Weiterfuehrende Dokumente (Fussbereich mit Links)

Am Fuss jedes Kontoauszugs (auf der letzten Seite, unten verankert - reicht
der Platz dort nicht mehr, wird automatisch eine zusaetzliche Seite nur
dafuer angehaengt) kann ein Bereich "Weiterfuehrende Dokumente" mit
anklickbaren Links erscheinen, z.B. Links zur Schulordnung, zum Kontakt
oder zur Datenschutzerklaerung.

Pro Eintrag: ein **Name** (erscheint sichtbar als Linktext) und ein
**Link/URL** (wird NICHT sichtbar ausgegeben, steckt nur als Klickziel
hinter dem Namen). In der GUI unter **Optionen -> Einstellungen** ganz
unten - beliebig viele ueber "+ Dokument hinzufuegen", einzelne Eintraege
per "Entfernen" wieder loeschen. Nutzt dieselbe Kopf-Schriftart wie der
Rest des Kopfbereichs. Sind weder Logo noch Links konfiguriert, erscheint
gar kein Fussbereich.

Auf der Kommandozeile/in `config.json` (kein eigenes CLI-Flag, da eine
Liste): der Schluessel `footer_links` erwartet eine Liste von Objekten
mit `name` und `url`, z.B.:
```json
"footer_links": [
    {"name": "Schulordnung", "url": "https://schule.example/ordnung.pdf"},
    {"name": "Kontakt", "url": "https://schule.example/kontakt"}
]
```

## Benutzung - grafische Oberflaeche (fuer Endbenutzer)

Doppelklick auf `start_gui.bat` (oder `python starmoney_gui.py`) oeffnet ein
Fenster:

1. **"Ordner waehlen..."** - Ordner mit den StarMoney-CSV-Exporten auswaehlen
   (wird gemerkt, muss beim naechsten Start nicht erneut gewaehlt werden).
2. Bei Bedarf Logo und Kopf-Schriftart einstellen (siehe oben).
3. Haekchen setzen, falls die Original-CSVs danach geloescht werden sollen
   (Standard: aus - CSVs bleiben erhalten).
4. **"Kontoauszuege erstellen"** klicken. Der Fortschritt und alle Meldungen
   erscheinen im Protokollfeld; am Ende gibt es eine kurze Zusammenfassung.
5. **"Ordner oeffnen"** oeffnet den Ordner mit den fertigen PDFs im
   Explorer.
6. **"Ordner automatisch auf neue CSV-Dateien ueberwachen"**: prueft den
   Exportordner fortlaufend im eingestellten Intervall (Standard 30s,
   einstellbar 5-3600s) und verarbeitet automatisch nur neu hinzugekommene
   CSV-Dateien - bereits verarbeitete werden nicht erneut angefasst, auch
   wenn sie (weil "loeschen" aus ist) weiterhin im Ordner liegen. Startet
   bewusst nie automatisch beim Programmstart, muss also jede Sitzung
   erneut angehakt werden. Ergebnisse laufender Ueberwachung erscheinen nur
   im Protokoll (kein Popup, das die Ueberwachung blockieren wuerde).

`starmoney_gui.py` benoetigt `starmoney_export.py` im selben Ordner (nutzt
dessen Logik direkt) sowie `tkinter`, das im offiziellen Windows-Installer
von python.org standardmaessig enthalten ist (bei einer benutzerdefinierten
Installation darauf achten, dass "tcl/tk and IDLE" angehakt bleibt).

## macOS

Das Tool ist reines Python (einzige Abhaengigkeit: `reportlab`) und laeuft
genauso unter macOS - nichts davon ist Windows-spezifisch.

1. Python installieren, falls noch nicht vorhanden: entweder von
   https://www.python.org/downloads/macos/ oder per Homebrew
   (`brew install python`). macOS bringt oft eine sehr alte Python-2-Version
   mit - `python3`/`pip3` verwenden, nicht `python`/`pip`.
2. Terminal im entpackten Ordner oeffnen und installieren:
   ```
   pip3 install -r requirements.txt
   ```
3. Starten:
   ```
   python3 starmoney_export.py            # Kommandozeile
   python3 starmoney_gui.py               # grafische Oberflaeche
   ```
   Alternativ liegen `start_gui_mac.command` und `start_export_mac.command`
   bei - vor dem ersten Doppelklick einmalig im Terminal ausfuehrbar machen:
   ```
   chmod +x start_gui_mac.command start_export_mac.command
   ```
   Da die Dateien aus dem Internet/Chat heruntergeladen wurden, blockiert
   Gatekeeper den ersten Start eventuell ("nicht verifizierter Entwickler").
   In dem Fall im Finder mit Rechtsklick -> **Oeffnen** starten (nur beim
   ersten Mal noetig) statt per Doppelklick.
4. `tkinter` ist im offiziellen python.org-Installer für macOS enthalten.
   Bei einer Homebrew-Installation ggf. zusaetzlich `brew install python-tk`
   ausfuehren, falls beim Start von `starmoney_gui.py` ein Fehler zu
   `tkinter` erscheint.

Bei Problemen (Rechte, fehlendes tkinter, `pip`/`externally-managed-
environment`) siehe **TROUBLESHOOTING_MACOS.md** - dort stehen die in der
Praxis aufgetretenen Fehlermeldungen mit Loesung im Wortlaut.

## Benutzung - Kommandozeile

```
python starmoney_export.py [Exportverzeichnis] [--delete-csv] [--watch [SEKUNDEN]]
```

- Ohne Pfadangabe wird der Ordner `export_auszuege` neben dem Skript
  verwendet - dort die StarMoney-CSV-Exporte hineinlegen.
- `--delete-csv` loescht die Original-CSVs nach erfolgreicher Verarbeitung
  (so wie im Original-Bash-Skript). **Ohne** dieses Flag bleiben die
  CSV-Originale erhalten - das ist der sicherere Standard dieser
  Portierung und weicht bewusst vom Original ab.
- `--watch [SEKUNDEN]` laesst das Skript dauerhaft laufen (bis Strg+C) und
  prueft den Ordner alle SEKUNDEN (Standard 30) auf neu hinzugekommene
  CSV-Dateien - nuetzlich z.B. als Hintergrundprozess/geplante Aufgabe.
  Bereits verarbeitete Dateien werden bei folgenden Pruefungen nicht
  erneut angefasst, auch wenn sie (ohne `--delete-csv`) im Ordner bleiben.
  Beispiel: `python starmoney_export.py --watch 60`
- Alternativ Doppelklick auf `start_export.bat` (nutzt den Ordner
  `export_auszuege` neben der .bat-Datei, ohne GUI, einmaliger Lauf ohne
  `--watch`).

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

## Wo es funktional aequivalent, aber technisch anders geloest ist

- Kopfbereich (Logo, Kontoname, Datum, Hinweistext) wird direkt beim
  PDF-Bau auf Seite 1 gezeichnet, statt separat als Kopf-PDF erzeugt und per
  `qpdf --underlay` untergelegt zu werden. Optisch/funktional das Gleiche,
  ohne die drei externen Tools. Logo und Schriftart sind hier zusaetzlich
  frei konfigurierbar geworden (siehe oben) - im Original war beides fest
  einprogrammiert (Lutherschul-Logo per URL, DejaVu-Sans via ImageMagick).
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
