# csv2pdf-gui

Version 0.2

csv2pdf-gui macht aus StarMoney-CSV-Exporten übersichtliche PDF-Kontoauszüge
mit Logo, Kontoname und Datum. Herunterladen, doppelklicken, fertig.

Website: https://lutherschule30167.github.io/csv2pdf-gui/

## Schnellstart (Windows 10 und 11)

1. **Programm herunterladen:**
   [csv2pdf-gui.exe](https://github.com/Lutherschule30167/csv2pdf-gui/releases/latest/download/csv2pdf-gui.exe)
2. **In einen eigenen Ordner legen,** zum Beispiel in „Dokumente“ einen
   Ordner `csv2pdf` anlegen und die Datei dorthin verschieben. Dort merkt
   sich das Programm später auch Ihre Einstellungen.
3. **Doppelklick zum Starten.** Beim allerersten Start zeigt Windows
   eventuell den blauen Hinweis „Der Computer wurde durch Windows
   geschützt“. Das ist normal bei kleinen Programmen ohne kostenpflichtige
   Signatur. Auf **Weitere Informationen** und dann auf **Trotzdem
   ausführen** klicken. Danach startet das Programm ohne Rückfrage.
4. **Kontoauszüge erstellen:** Mit **Ordner waehlen…** den Ordner mit den
   StarMoney-Exporten auswählen und auf **Kontoauszuege erstellen** klicken.

Es wird nichts installiert, und Sie brauchen keine Administratorrechte.

## StarMoney vorbereiten (einmalig)

In StarMoney unter **Verwaltung → Datenexport → CSV-Spaltenkonfiguration**
eine Exportvorlage mit genau diesen Spalten anlegen:

- „Buchungstag“
- „Begünstigter/Absender – Name“
- „Betrag“
- „Saldo“

Nur Exporte in diesem Format werden richtig verarbeitet.

## Woher kommt der Kontoname auf dem Auszug?

csv2pdf-gui übernimmt ihn aus dem Kontonamen, den StarMoney beim Export in
den Dateinamen schreibt, und zwar alles bis zum ersten Unterstrich (`_`).
Aus einem Export „Klassenkasse 5b_…“ wird so „Klassenkasse 5b“.

Benennen Sie Ihre Unterkonten in StarMoney deshalb so, wie sie auf dem
Auszug stehen sollen, und verwenden Sie im Namen selbst keinen Unterstrich.

## Das Programm benutzen

- **Ordner waehlen…** – den Ordner mit den StarMoney-Exporten auswählen.
  Das Programm merkt sich den Ordner für den nächsten Start.
- **Kontoauszuege erstellen** – erstellt für jeden Export ein PDF. Was
  passiert, steht im Protokollfeld darunter.
- **Ordner oeffnen** – zeigt die fertigen PDFs. Sie liegen im selben
  Ordner wie die Exporte, benannt nach Kontoname und Datum.
- **Original-CSV-Dateien … loeschen** – normalerweise aus. Die Exporte aus
  StarMoney bleiben dann unangetastet.
- **Ordner automatisch … ueberwachen** – schaut regelmäßig in den Ordner
  und verarbeitet neue Exporte von selbst. Bereits erledigte bleiben
  unangetastet. Muss bei jedem Programmstart neu angehakt werden.

## Logo, Schrift und Links einstellen

Alles liegt im Programm unter **Optionen → Einstellungen** und wird sofort
gespeichert:

- **Logo:** ein beliebiges Bild (PNG, JPG, GIF oder BMP), zum Beispiel das
  Schullogo. Es wird automatisch passend verkleinert. Kein Logo? Dann
  bleibt der Kopf einfach leer.
- **Kopf-Schriftart:** Schrift für Kontoname, Datum und Hinweistext.
  Mehrere Schriften stehen zur Auswahl, auf Wunsch auch eine eigene
  Schriftdatei.
- **Hinweistext:** ein kurzer Text im Kopf des Auszugs.
- **Weiterführende Dokumente:** beliebig viele anklickbare Links am Ende
  jedes Auszugs, etwa zur Schulordnung, zum Kontakt oder zur
  Datenschutzerklärung. Sichtbar ist nur der Name, der Link steckt dahinter.

## Häufige Fragen

**Windows warnt beim Start.** Siehe Schritt 3 im Schnellstart. Die Warnung
kommt nur beim ersten Start.

**Wo werden meine Einstellungen gespeichert?** In der Datei `config.json`
neben `csv2pdf-gui.exe`. Darf das Programm dort nicht schreiben (zum
Beispiel unter „C:\Programme“), landen sie unter
`%APPDATA%\csv2pdf\config.json`.

**Welche Version habe ich?** Sie steht in der Titelleiste des Programms.

**Etwas funktioniert nicht?** Melden Sie es unter
[Probleme melden](https://github.com/Lutherschule30167/csv2pdf-gui/issues).

---

## Für Fortgeschrittene

Alles ab hier ist nur nötig, wenn Sie das Tool ohne die EXE nutzen
möchten, etwa auf einem Mac, unter Linux oder automatisiert.

### Mit Python starten (Windows, macOS, Linux)

1. Python 3 installieren (https://www.python.org/downloads/). Unter Windows
   im Installer **„Add python.exe to PATH“** ankreuzen.
2. Im Projektordner die einzige Abhängigkeit installieren:
   ```
   pip install -r requirements.txt
   ```
   (unter macOS `pip3`). Optional `pip install Pillow`, damit die
   Logovorschau auch JPG und BMP anzeigt.
3. Starten:
   ```
   python starmoney_gui.py        # grafische Oberfläche
   python starmoney_export.py     # Kommandozeile
   ```
   Unter Windows geht das auch per Doppelklick auf `start_gui.bat` bzw.
   `start_export.bat`.

**macOS:** `python3` statt `python` verwenden. Die Starter
`start_gui_mac.command` und `start_export_mac.command` vor dem ersten
Doppelklick einmal mit `chmod +x start_gui_mac.command start_export_mac.command`
ausführbar machen und beim ersten Mal per Rechtsklick → **Öffnen** starten.
Bei einer Homebrew-Installation fehlt manchmal `tkinter`
(`brew install python-tk`). Weitere Fehlermeldungen samt Lösung stehen in
[TROUBLESHOOTING_MACOS.md](TROUBLESHOOTING_MACOS.md).

### Kommandozeile

```
python starmoney_export.py [Exportverzeichnis] [--delete-csv] [--watch [SEKUNDEN]]
```

Als EXE heißt die Kommandozeilenversion `csv2pdf.exe` (am
[Release](https://github.com/Lutherschule30167/csv2pdf-gui/releases)
unter „Assets“) und kennt dieselben Optionen.

- Ohne Pfadangabe wird der Ordner `export_auszuege` neben dem Programm
  verwendet.
- `--delete-csv` löscht die Original-CSVs nach erfolgreicher Verarbeitung.
  Ohne diese Option bleiben sie erhalten.
- `--watch [SEKUNDEN]` läuft dauerhaft (bis Strg+C) und verarbeitet alle
  SEKUNDEN (Standard 30) neu hinzugekommene Exporte, z. B. als geplante
  Aufgabe: `python starmoney_export.py --watch 60`
- `--version` zeigt die Version an.
- `--logo`, `--header-font`, `--header-font-file` setzen Logo und
  Kopf-Schriftart; mit `--save-config` werden sie dauerhaft gespeichert:
  ```
  python starmoney_export.py --logo "C:\Pfad\logo.png" --header-font Times-Roman --save-config
  ```

Die Einstellungen liegen in `config.json` (einfaches JSON, auch von Hand
bearbeitbar). Die Links im Fußbereich stehen dort unter `footer_links`:
```json
"footer_links": [
    {"name": "Schulordnung", "url": "https://schule.example/ordnung.pdf"},
    {"name": "Kontakt", "url": "https://schule.example/kontakt"}
]
```

### EXE bauen und Releases

Beim Veröffentlichen eines Releases baut GitHub Actions
(`.github/workflows/build-windows-exe.yml`) `csv2pdf-gui.exe` und
`csv2pdf.exe` mit PyInstaller und hängt sie ans Release. Manuell geht das
unter **Actions → Windows-EXE bauen → Run workflow** (die EXEs liegen dann
als Artefakt am Lauf) oder lokal unter Windows per Doppelklick auf
`build_exe.bat` (Ergebnis in `dist\`). Die Version wird nur in
`starmoney_export.py` (`__version__`) gepflegt.

### Technischer Hintergrund

csv2pdf-gui ist eine Python-Neuimplementierung des Original-Bash-Skripts
der Lutherschule Hannover und kommt ohne dessen Linux-Werkzeuge
(Ghostscript, paps, ImageMagick, qpdf, iconv, column, curl, perl-rename)
aus. Einzige Abhängigkeit ist `reportlab`.

1:1 übernommen:

- **Zeichensatz:** UTF-8-BOM wird entfernt, die Kodierung pro Datei erkannt
  (UTF-8, sonst Windows-1252); einzelne kaputte Bytes werden verworfen statt
  die ganze Datei zu verlieren.
- **Sortierung:** Buchungen pro Tag gruppiert, innerhalb eines Tages erst
  Gutschriften aufsteigend, dann Abbuchungen absteigend; neuester Tag oben.
- **Dateiname:** Bei genau fünf durch `_` getrennten Teilen bleiben nur
  Teil 1 (Kontoname) und Teil 4 (Datum), siehe
  [Woher kommt der Kontoname](#woher-kommt-der-kontoname-auf-dem-auszug).

Anders gelöst, im Ergebnis gleich:

- Der Kopfbereich wird direkt beim PDF-Bau auf Seite 1 gezeichnet statt per
  `qpdf --underlay` untergelegt. Logo und Schrift sind dabei frei wählbar
  geworden.
- Statt `paps` und Ghostscript setzt `reportlab` die Tabelle direkt in
  Courier 7 pt, A4 hoch.

Nicht vollständig geprüft: Die Spaltenausrichtung bildet
`column -t ... -T 5 -E 2 -R 3,4 -l 12` nach (Spalten 2/3/4 fest 30/10/10
Zeichen, übrige dynamisch, Gesamtbreite höchstens 120 Zeichen, Spalte 5
wird bei Bedarf gekürzt). Am besten einmal mit einem echten, anonymisierten
Export gegenprüfen.
