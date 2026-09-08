# macOS: Bekannte Python-Probleme beim Einrichten

Diese Datei dokumentiert die Stolpersteine, die beim Einrichten des Tools auf
macOS (Homebrew-Python, zsh) tatsaechlich aufgetreten sind, und wie sie
geloest wurden - als Referenz fuer alle, die es der naechsten Person (oder
sich selbst in ein paar Monaten) ersparen wollen, das Ganze erneut
herauszufinden.

Kurzfassung der Ursache: macOS bringt kein aktuelles Python mit, und
Homebrew installiert Python bewusst "minimal" (Tk-Unterstuetzung und
pip-Verhalten unterscheiden sich vom offiziellen python.org-Installer bzw.
von Windows). Jedes einzelne Problem unten ist eine direkte Folge davon.

---

## 1. "permission denied" beim Start von `start_gui_mac.command`

**Symptom:**
```
zsh: permission denied: ./start_gui_mac.command
```

**Ursache:** Beim Herunterladen/Entpacken geht das Ausfuehrungsrecht der
Datei verloren (ist kein Python-Problem, sondern ein normales
Dateisystem-Flag).

**Loesung:** Einmalig ausfuehrbar machen:
```bash
chmod +x start_gui_mac.command start_export_mac.command
```
Danach per Doppelklick im Finder oder mit `./start_gui_mac.command`
starten.

**Falls danach eine macOS-Sicherheitsmeldung kommt** ("kann nicht geoeffnet
werden, da der Entwickler nicht verifiziert werden kann" - das ist
Gatekeeper, nicht mehr "permission denied"): im Finder mit **Rechtsklick ->
Oeffnen** starten. Das ist nur beim allerersten Start noetig.

---

## 2. `ModuleNotFoundError: No module named '_tkinter'`

**Symptom:**
```
File ".../tkinter/__init__.py", line 38, in <module>
    import _tkinter
ModuleNotFoundError: No module named '_tkinter'
```

**Ursache:** Der Homebrew-Formula `python@X.Y` installiert die
Tcl/Tk-Anbindung (fuer die grafische Oberflaeche) NICHT automatisch mit -
das ist ein separates Paket. Der offizielle python.org-Installer hat dieses
Problem nicht (Tk ist dort direkt dabei).

**Loesung:** Das zur Python-Version passende Tk-Paket nachinstallieren
(Version aus der Fehlermeldung ablesen, im Beispiel oben war es 3.14):
```bash
brew install python-tk@3.14
```
Falls dieses Paket fuer eine sehr neue Python-Version noch nicht existiert,
erst schauen, was verfuegbar ist:
```bash
brew search python-tk
```
und die passende Version installieren. Alternativ auf eine von Homebrew
bereits unterstuetzte Python-Version ausweichen (z.B. `python@3.12` +
`python-tk@3.12`) oder komplett auf den offiziellen python.org-Installer
wechseln, der dieses Thema von vornherein vermeidet.

Kein Neustart noetig - nach der Installation einfach das Tool erneut
starten.

---

## 3. `command not found: pip`

**Symptom:**
```
zsh: command not found: pip
```

**Ursache:** Homebrew-Python installiert (bewusst) keinen blanken
`pip`-Befehl im PATH, nur `pip3`, um Verwechslungen mit einem eventuell
vorhandenen System-Python 2 zu vermeiden.

**Loesung:** `pip3` statt `pip` verwenden:
```bash
pip3 install -r requirements.txt
```
Falls auch das nicht gefunden wird, geht es garantiert ueber das Python
selbst (unabhaengig vom PATH):
```bash
python3 -m pip install -r requirements.txt
```

---

## 4. `error: externally-managed-environment`

**Symptom:**
```
error: externally-managed-environment

× This environment is externally managed
╰─> ...
```

**Ursache:** Neuere Python-Versionen (PEP 668) verhindern per Standard,
dass `pip install` direkt in die vom Betriebssystem/von Homebrew verwaltete
Python-Umgebung schreibt - das soll verhindern, dass Pakete mit denen von
Homebrew selbst verwalteten kollidieren.

**Loesung A (empfohlen): virtuelle Umgebung**
```bash
cd <Projektordner>
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python starmoney_gui.py
```
Sobald `venv` aktiv ist (Prompt zeigt `(venv)` davor), heissen die Befehle
schlicht `python`/`pip` statt `python3`/`pip3`. Tkinter bleibt dabei
nutzbar, da das venv die `_tkinter`-Anbindung des Basis-Python
mitverwendet (Problem 2 muss also vorher trotzdem geloest sein).

Fuer jeden weiteren Start reicht danach:
```bash
cd <Projektordner>
source venv/bin/activate
python starmoney_gui.py
```

**Loesung B (schneller, aber weniger sauber): Schutz gezielt umgehen**
```bash
pip3 install --break-system-packages -r requirements.txt
```
Installiert `reportlab` direkt systemweit. Fuer dieses kleine Tool
unproblematisch, aber generell nicht der von Python empfohlene Weg (kann
theoretisch mit anderen, von Homebrew verwalteten Paketen kollidieren).

---

## Ablaufuebersicht (alles zusammen, macOS + Homebrew-Python)

```bash
# 1) Tk-Unterstuetzung fuer die installierte Python-Version nachruesten
brew install python-tk@3.14        # Versionsnummer an "python3 --version" anpassen

# 2) Ins Projektverzeichnis wechseln
cd <Projektordner>

# 3) Ausfuehrungsrecht der Starter-Skripte setzen (falls per Download erhalten)
chmod +x start_gui_mac.command start_export_mac.command

# 4) Virtuelle Umgebung anlegen und Abhaengigkeiten installieren
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5) Starten
python starmoney_gui.py
```

Bei jedem weiteren Start reichen Schritt 2, `source venv/bin/activate` aus
Schritt 4, und Schritt 5.
