#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StarMoney-CSV zu PDF-Kontoauszug -- Windows-Portierung
=======================================================

Reines Python-Aequivalent des urspruenglichen Linux-Bash-Skripts (urspruenglich
fuer die Lutherschule Hannover entstanden, mittlerweile fuer beliebige Schulen/
Einrichtungen konfigurierbar). Lauffaehig unter Windows (und weiterhin auch
unter Linux/macOS), ohne die externen Kommandozeilen-Tools des Originals
(ghostscript, paps, ImageMagick, qpdf, iconv, column, curl, perl-rename).
Die PDFs werden direkt mit reportlab erzeugt.

Einzige externe Abhaengigkeit: reportlab
    pip install reportlab

Verwendung:
    python starmoney_export.py [Exportverzeichnis] [--delete-csv]
        [--logo DATEI] [--header-font NAME] [--header-font-file DATEI]
        [--save-config]

Ohne Pfadangabe wird der Ordner "export_auszuege" neben diesem Skript
verwendet. Mit --delete-csv werden die Original-CSV-Dateien nach
erfolgreicher Verarbeitung geloescht (so wie im Original-Bash-Skript);
ohne dieses Flag bleiben sie erhalten (sichererer Standard fuer diese
neue Portierung).

Logo und Kopf-Schriftart sind frei konfigurierbar (kein fest einprogrammiertes
Schullogo mehr) - entweder je Aufruf per --logo/--header-font(-file), oder
dauerhaft in config.json (siehe load_config()/save_config(), bzw. bequem
ueber starmoney_gui.py).

Entstanden mit Unterstuetzung von Claude (Anthropic).
Lizenz: MIT
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# Zentrale Versionsnummer (wird auch von starmoney_gui.py angezeigt).
# Bei Aenderung README, /docs und Wiki angleichen.
__version__ = "0.2"

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
DEFAULT_HINT_TEXT = ("Hinweis: Buchungen innerhalb eines Tages sind evtl. nicht "
                     "in der richtigen Reihenfolge gelistet.")
# Harte Obergrenze fuer den frei editierbaren Hinweistext. Der Text steht
# einzeilig (kein Umbruch) rechts neben dem Logo; bei Courier (der breitesten
# der drei Standard-Kopfschriften) und 7pt Schriftgroesse passen im
# verfuegbaren Platz konservativ gerechnet ca. 100-110 Zeichen ohne dass die
# Zeile über den rechten Seitenrand hinauslaeuft -- 100 als rund und sicher
# gewählte Grenze, unabhaengig davon welche Kopfschrift gewaehlt ist.
HINT_TEXT_MAX_LENGTH = 100

# Schriftart der Buchungstabelle selbst -- bewusst NICHT konfigurierbar,
# da eine Monospace-Schrift fuer die Spaltenausrichtung noetig ist.
TABLE_FONT_NAME = "Courier"
TABLE_FONT_NAME_BOLD = "Courier-Bold"
FONT_SIZE = 7
LINE_HEIGHT = FONT_SIZE * 1.15

# Kopf-Schriftart (Kontoname/Datum/Hinweis) -- frei waehlbar, siehe
# resolve_header_fonts(). Diese drei PDF-Standardschriften brauchen keine
# externe Schriftdatei und funktionieren immer.
STANDARD_HEADER_FONTS = {
    "Helvetica": "Helvetica-Bold",
    "Times-Roman": "Times-Bold",
    "Courier": "Courier-Bold",
}
DEFAULT_HEADER_FONT = "Helvetica"

TOP_MARGIN_PAGE1 = 100   # Platz fuer Logo/Kontoname/Datum -- nur auf Seite 1
# Zusaetzlicher Leerraum zwischen Kopfbereich und der eigentlichen
# Buchungstabelle, in "Zeilen" der Tabelle selbst gemessen (siehe
# LINE_HEIGHT oben), damit es bei anderer Schriftgroesse konsistent bleibt.
HEADER_TABLE_GAP_LINES = 2
TOP_MARGIN_OTHER = 36
BOTTOM_MARGIN = 36
SIDE_MARGIN = 28

# Dunkles, gut lesbares Rot fuer negative Betraege -- bewusst kein grelles
# Signalrot (255,0,0), das auf Papier/Bildschirm schnell unruhig wirkt.
NEGATIVE_COLOR = colors.Color(0.70, 0, 0)

# Fusszeile "Weiterfuehrende Dokumente" -- Standard-Hyperlink-Blau (aehnlich
# dem in Office/Google Docs uebliche Linkfarbe), damit klar erkennbar ist,
# dass es sich um klickbare Links handelt.
LINK_COLOR = colors.Color(0.067, 0.333, 0.8)
FOOTER_LINE_HEIGHT = 12
FOOTER_TOP_GAP = 14  # Abstand zwischen letzter Buchungszeile und Fusszeilenbereich
# 2pt kleiner als die entsprechenden Kopfbereich-Groessen (Titel vs. Konto-
# name-Zeile 9pt dort waere 11pt, Linktext vs. "Kontoauszug vom..."/Summary
# waere 8pt dort) -- der Fussbereich soll sich optisch dezent unterordnen.
FOOTER_TITLE_SIZE = 7
FOOTER_LINK_SIZE = 6

# Maximale Logo-Groesse im Kopfbereich. Entspricht exakt der Box, auf die
# das Original-Bash-Skript das feste Lutherschullogo per ImageMagick
# begrenzt hat ("convert -resize 156x120" auf einer 2x-aufgeloesten
# Kopfseite -> 156/2=78pt breit, 120/2=60pt hoch). Ein frei gewaehltes
# eigenes Logo wird proportional in dieselbe Box eingepasst (nie groesser),
# damit der Kopfbereich unabhaengig vom gewaehlten Logo gleich aussieht.
LOGO_MAX_WIDTH = 78.0
LOGO_MAX_HEIGHT = 60.0

MAX_LINE_WIDTH = 120                  # entspricht "column -c 120"
FIXED_WIDTHS = {2: 30, 3: 10, 4: 10}   # 1-indiziert wie im Original (Spalte 2/3/4)
RIGHT_ALIGN_COLUMNS = {3, 4}           # entspricht "-R 3,4"
TRUNCATE_COLUMNS = {5}                 # entspricht "-T 5"
SEPARATOR = "||"                       # entspricht "column -o '||'"
# Nach diesen Spalten (Buchungstag/Begünstigter/Betrag/Saldo) wird die
# linke Haelfte des "||"-Trenners durch ein Leerzeichen ersetzt (" |"
# statt "||") -- rein optisch, aendert nichts an der Spaltenbreite/
# Ausrichtung. Trenner nach weiteren, hier nicht genannten Spalten
# (z.B. nach Verwendungszweck, falls noch mehr Spalten folgen) bleiben "||".
LEFT_SPACE_AFTER_COLUMNS = {1, 2, 3, 4}
LEFT_SPACE_SEPARATOR = " " + SEPARATOR[1:]

SHORTEN_RE = re.compile(r'^([^.]+)_([^.]+)_([^.]+)_([^.]+)_([^.]+)$')

# Dauerhafte Einstellungen (Logo, Kopf-Schriftart, ...) -- eine einzige,
# von CLI und GUI gemeinsam genutzte Datei neben dem Skript.
DEFAULT_CONFIG = {
    "export_dir": "",
    "delete_csv": False,
    "logo_path": "",
    "header_font": DEFAULT_HEADER_FONT,
    "header_font_path": "",
    "hint_text": DEFAULT_HINT_TEXT,
    # Liste von {"name": ..., "url": ...} fuer den Fussbereich
    # "Weiterfuehrende Dokumente" (siehe draw_footer_links()).
    "footer_links": [],
    # Intervall (Sekunden) fuer die optionale automatische Ordnerueberwachung
    # in der GUI (siehe starmoney_gui.py) bzw. Standardwert fuer --watch.
    "watch_interval_seconds": 30,
}


def config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    """Liest config.json neben dem Skript. Fehlt die Datei oder ist sie
    beschaedigt, werden einfach die Standardwerte zurueckgegeben."""
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(config_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return cfg


def save_config(updates):
    """Schreibt die uebergebenen Schluessel dauerhaft in config.json,
    bestehende (nicht uebergebene) Werte bleiben erhalten."""
    merged = load_config()
    merged.update({k: v for k, v in updates.items() if k in DEFAULT_CONFIG})
    with open(config_path(), "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
    return merged


# ---------------------------------------------------------------------------
# Encoding-Fix (Portierung von: BOM-Entfernung + iconv-Autodetektion)
# ---------------------------------------------------------------------------
def read_csv_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # Original: einzelne im erkannten Encoding ungueltige Bytes verwerfen,
        # statt die ganze Datei zu verlieren.
        text = raw.decode("windows-1252", errors="ignore")
    return text.replace("\r\n", "\n").replace("\r", "\n")


# ---------------------------------------------------------------------------
# Tagesgruppierung + Sortierung (Portierung des ersten AWK-Blocks)
# ---------------------------------------------------------------------------
def to_number(value):
    v = value.replace('"', "").replace(".", "").replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return 0.0


def format_amount_de(value):
    """Formatiert eine Zahl im deutschen Format (Tausenderpunkt,
    Dezimalkomma), z.B. -1234.5 -> "-1.234,50"."""
    sign = "-" if value < 0 else ""
    s = f"{abs(value):,.2f}"          # zunaechst "1,234.50" (en-US-Zwischenschritt)
    s = s.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return sign + s


def compute_summary(body_lines):
    """Berechnet aus den Datenzeilen:
    - soll: Summe aller negativen Betraege (Spalte 3)
    - haben: Summe aller positiven Betraege (Spalte 3)
    - gesamtsaldo: schlicht soll + haben (Netto aus allen Buchungen dieser
      Datei).

    Bewusst NICHT der Saldo-Wert (Spalte 4) irgendeiner einzelnen Zeile:
    die Saldo-Spalte enthaelt einen bereits vor dem Exportzeitraum
    bestehenden Kontostand, den Soll/Haben gar nicht kennen -- ein Vergleich
    mit einer einzelnen Saldo-Zeile fuehrt daher zu einem falschen,
    unzusammenhaengenden Wert (z.B. Soll -624,00 / Haben 624,00, aber
    Gesamtsaldo faelschlich -8,00 aus einer beliebigen Saldo-Zelle statt
    korrekt 0,00)."""
    soll = 0.0
    haben = 0.0
    for line in body_lines:
        if line == "":
            continue
        fields = line.split(";")
        if len(fields) > 2:
            amount = to_number(fields[2])
            if amount < 0:
                soll += amount
            else:
                haben += amount
    gesamtsaldo = soll + haben
    return soll, haben, gesamtsaldo


DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})")


def normalize_date_field(field):
    """Ergaenzt Tag/Monat in einem Datum (z.B. "1.3.2024") um eine
    fuehrende Null ("01.03.2024"). Funktioniert auch bei Anfuehrungszeichen
    um den Wert, da nur nach dem Zahlenmuster gesucht wird. Das Jahr bleibt
    unveraendert. Ohne erkennbares Datumsmuster wird das Feld unveraendert
    zurueckgegeben."""
    def repl(m):
        day, month, year = m.group(1), m.group(2), m.group(3)
        return f"{int(day):02d}.{int(month):02d}.{year}"
    return DATE_RE.sub(repl, field, count=1)


def group_and_sort(lines):
    """Gruppiert Zeilen nach Datum (Spalte 1) und sortiert innerhalb jeder
    Gruppe: Gutschriften (positiv) aufsteigend zuerst, danach Abbuchungen
    (negativ) absteigend -- auf Basis des rohen Betrags (Spalte 3). Die
    Tagesgruppen selbst werden in umgekehrter Reihenfolge ausgegeben
    (neuestes Datum zuerst oben). Leerzeilen bleiben als eigene Gruppen
    an ihrer relativen Position erhalten."""
    if not lines:
        return []
    header, body = lines[0], lines[1:]

    groups = []
    pos_buf, neg_buf = [], []
    prev_date = None

    def close_group():
        nonlocal pos_buf, neg_buf
        if not pos_buf and not neg_buf:
            return
        pos_sorted = sorted(pos_buf, key=lambda item: item[1])
        neg_sorted = sorted(neg_buf, key=lambda item: item[1], reverse=True)
        groups.append([ln for ln, _ in pos_sorted] + [ln for ln, _ in neg_sorted])
        pos_buf, neg_buf = [], []

    for line in body:
        if line == "":
            close_group()
            groups.append([line])
            continue
        # Anfuehrungszeichen in Datenzeilen durch ein Leerzeichen ersetzen
        # (nur hier, nicht in der Kopfzeile -- die wird in format_table()
        # separat behandelt und ihre Anfuehrungszeichen komplett entfernt,
        # nicht durch ein Leerzeichen ersetzt).
        line = line.replace('"', " ")
        fields = line.split(";")
        if fields:
            # Datum vor der Gruppierung normalisieren (fuehrende Null),
            # damit "1.3.2024" und "01.03.2024" auch als derselbe Tag
            # erkannt werden und die Anzeige einheitlich ist.
            fields[0] = normalize_date_field(fields[0])
            line = ";".join(fields)
        date = fields[0] if fields else ""
        if date != prev_date and (pos_buf or neg_buf):
            close_group()
        amount = to_number(fields[2]) if len(fields) > 2 else 0.0
        (neg_buf if amount < 0 else pos_buf).append((line, amount))
        prev_date = date

    close_group()

    ordered = []
    for g in reversed(groups):
        ordered.extend(g)
    return [header] + ordered


# ---------------------------------------------------------------------------
# Spaltenformatierung (Portierung von sprintf-Padding + "column -t")
# ---------------------------------------------------------------------------
def apply_fixed_widths(fields):
    out = list(fields)
    for idx, width in FIXED_WIDTHS.items():
        i = idx - 1
        if i < len(out):
            val = out[i][:width]
            out[i] = val.rjust(width) if idx in RIGHT_ALIGN_COLUMNS else val.ljust(width)
    return out


def format_table(lines):
    """Gibt pro Zeile eine Liste von (Text, ist_negativ)-Segmenten zurueck
    (Zellen und Trenner abwechselnd), statt eines fertigen Strings -- so
    kann make_pdf() negative Betraege/Salden gezielt rot einfaerben, ohne
    die Monospace-Ausrichtung zu verlieren (Trenner sind immer schwarz)."""
    if not lines:
        return []
    header_fields = [f.replace('"', "") for f in lines[0].split(";")]
    data_lines = lines[1:]
    data_field_rows = [ln.split(";") for ln in data_lines if ln != ""]

    all_field_rows = [header_fields] + data_field_rows
    ncols = max((len(r) for r in all_field_rows), default=0)

    def pad_row(fields):
        fields = fields + [""] * (ncols - len(fields))
        return apply_fixed_widths(fields)

    padded_header = pad_row(header_fields)
    padded_rows = [pad_row(r) for r in data_field_rows]
    all_padded = [padded_header] + padded_rows

    # Welche Zellen (Spalte 3 = Betrag, Spalte 4 = Saldo) sind negativ --
    # anhand der ORIGINALEN (ungepaddeten) Werte ermittelt, quotes-robust
    # ueber to_number().
    neg_flags_per_row = []
    for row in data_field_rows:
        flags = set()
        if len(row) > 2 and to_number(row[2]) < 0:
            flags.add(3)
        if len(row) > 3 and to_number(row[3]) < 0:
            flags.add(4)
        neg_flags_per_row.append(flags)

    widths = []
    for c in range(ncols):
        col_idx = c + 1
        if col_idx in FIXED_WIDTHS:
            widths.append(FIXED_WIDTHS[col_idx])
        else:
            widths.append(max((len(r[c]) for r in all_padded), default=0))

    total = sum(widths) + len(SEPARATOR) * max(ncols - 1, 0)
    if total > MAX_LINE_WIDTH:
        overflow = total - MAX_LINE_WIDTH
        for col_idx in TRUNCATE_COLUMNS:
            c = col_idx - 1
            if 0 <= c < len(widths):
                widths[c] = max(5, widths[c] - overflow)
                break

    def render(fields, neg_cols):
        segments = []
        for c in range(ncols):
            col_idx = c + 1
            val = fields[c][: widths[c]]
            cell = val.rjust(widths[c]) if col_idx in RIGHT_ALIGN_COLUMNS else val.ljust(widths[c])
            if c > 0:
                after_col = c  # 1-indizierte Spalte, die vor diesem Trenner steht
                sep = LEFT_SPACE_SEPARATOR if after_col in LEFT_SPACE_AFTER_COLUMNS else SEPARATOR
                segments.append((sep, False))
            segments.append((cell, col_idx in neg_cols))
        return segments

    out_lines = [render(padded_header, set())]
    idx = 0
    for ln in data_lines:
        if ln == "":
            out_lines.append([("", False)])
        else:
            out_lines.append(render(padded_rows[idx], neg_flags_per_row[idx]))
            idx += 1
    return out_lines


# ---------------------------------------------------------------------------
# Dateinamen (Portierung von batch_rename + shorten_names)
# ---------------------------------------------------------------------------
def shorten_stem(stem):
    m = SHORTEN_RE.match(stem)
    if m:
        return f"{m.group(1)}_{m.group(4)}"
    return stem


def parse_account_and_date(final_stem):
    if "_" in final_stem:
        account, datepart = final_stem.rsplit("_", 1)
    else:
        account, datepart = final_stem, ""
    if len(datepart) == 8 and datepart.isdigit():
        datum = f"{datepart[6:8]}.{datepart[4:6]}.{datepart[0:4]}"
    else:
        datum = datepart
    return account, datum


# ---------------------------------------------------------------------------
# Logo (lokale Bilddatei, frei konfigurierbar -- kein fester Download mehr)
# ---------------------------------------------------------------------------
def resolve_logo(logo_path, log_err=None):
    """Prueft eine vom Anwender konfigurierte Logo-Bilddatei. Leer/None
    bedeutet bewusst "kein Logo" (kein Standardlogo mehr eingebaut)."""
    log_err = log_err or (lambda m: print(m, file=sys.stderr))
    if not logo_path:
        return None
    if not os.path.isfile(logo_path):
        log_err(f"Warnung: Logo-Datei nicht gefunden: {logo_path} - Kopfseite ohne Logo.")
        return None
    try:
        ImageReader(logo_path)  # frueh pruefen, ob reportlab die Datei lesen kann
    except Exception as exc:
        log_err(f"Warnung: Logo-Datei konnte nicht gelesen werden ({exc}) - Kopfseite ohne Logo.")
        return None
    return logo_path


# ---------------------------------------------------------------------------
# Kopf-Schriftart (frei waehlbar: PDF-Standardschrift oder eigene .ttf/.otf)
# ---------------------------------------------------------------------------
_registered_fonts = {}  # Cache: Dateipfad -> registrierter Fontname


def resolve_header_fonts(header_font, header_font_path, log_err=None):
    """Liefert (normale_schrift, fette_schrift) fuer den Kopfbereich.

    - Wenn header_font_path gesetzt ist, wird diese .ttf/.otf-Datei geladen
      und fuer normalen UND fetten Text verwendet (eine echte Fettvariante
      gibt es nur bei den drei PDF-Standardschriften unten).
    - Sonst wird header_font als Name einer PDF-Standardschrift erwartet
      (Helvetica, Times-Roman, Courier).
    - Bei Fehlern (Datei fehlt, unbekannter Name, ...) wird auf Helvetica
      zurueckgefallen und eine Warnung geloggt."""
    log_err = log_err or (lambda m: print(m, file=sys.stderr))

    if header_font_path:
        if header_font_path in _registered_fonts:
            name = _registered_fonts[header_font_path]
            return name, name
        if not os.path.isfile(header_font_path):
            log_err(f"Warnung: Schriftdatei nicht gefunden: {header_font_path} "
                     f"- verwende {DEFAULT_HEADER_FONT}.")
            return DEFAULT_HEADER_FONT, STANDARD_HEADER_FONTS[DEFAULT_HEADER_FONT]
        name = "custom-" + re.sub(r"[^A-Za-z0-9_-]", "_", os.path.splitext(os.path.basename(header_font_path))[0])
        try:
            pdfmetrics.registerFont(TTFont(name, header_font_path))
            _registered_fonts[header_font_path] = name
            return name, name
        except Exception as exc:
            log_err(f"Warnung: Schriftdatei konnte nicht geladen werden ({exc}) "
                     f"- verwende {DEFAULT_HEADER_FONT}.")
            return DEFAULT_HEADER_FONT, STANDARD_HEADER_FONTS[DEFAULT_HEADER_FONT]

    if header_font in STANDARD_HEADER_FONTS:
        return header_font, STANDARD_HEADER_FONTS[header_font]

    log_err(f"Warnung: Unbekannte Schriftart '{header_font}' - verwende {DEFAULT_HEADER_FONT}.")
    return DEFAULT_HEADER_FONT, STANDARD_HEADER_FONTS[DEFAULT_HEADER_FONT]


# ---------------------------------------------------------------------------
# PDF-Erzeugung (ersetzt paps+ghostscript fuer den Text und
# ImageMagick+qpdf fuer die untergelegte Kopfseite -- hier direkt in
# einem Durchgang mit reportlab statt zweier separat verschmolzener PDFs)
# ---------------------------------------------------------------------------
def draw_bold_text(c, x, y, text, font_normal, font_bold, size):
    """Zeichnet Text fett. Bei den drei PDF-Standardschriften gibt es eine
    echte Fettvariante (font_bold != font_normal), die einfach verwendet
    wird. Bei einer eigenen .ttf/.otf-Datei ohne separate Fettvariante
    (siehe resolve_header_fonts: dort ist font_bold == font_normal) wird
    stattdessen ein "Fake Bold" gezeichnet -- Buchstaben werden gefuellt
    UND konturiert, was optisch fetter wirkt als reines Fuellen."""
    if font_bold != font_normal:
        c.setFont(font_bold, size)
        c.drawString(x, y, text)
        return
    c.saveState()
    c.setLineWidth(size * 0.03)  # Konturbreite -- Grafikstatus des Canvas, nicht des Textobjekts
    t = c.beginText(x, y)
    t.setFont(font_normal, size)
    t.setFillColor(colors.black)
    t.setStrokeColor(colors.black)
    t.setTextRenderMode(2)  # 2 = Fuellen + Konturieren
    t.textOut(text)
    c.drawText(t)
    c.restoreState()


def draw_colored_segments(c, x, y, segments, font_normal, size, font_bold=None):
    """Zeichnet eine Zeile aus Segmenten hintereinander in derselben Zeile.
    Jedes Segment ist (Text, ist_negativ) oder (Text, ist_negativ, ist_fett).
    Negative Segmente in NEGATIVE_COLOR, alles andere in Schwarz. Fett
    markierte Segmente nutzen font_bold (falls angegeben); hat die
    Kopfschrift keine echte Fettvariante (font_bold == font_normal, siehe
    resolve_header_fonts bei eigenen .ttf-Dateien), wird stattdessen wie
    bei draw_bold_text ein Fake-Bold (Fuellen + Konturieren) gezeichnet.
    Ein einzelnes Textobjekt haelt dabei die Cursor-Position ueber alle
    Segmente hinweg konsistent, die Spaltenausrichtung geht nicht verloren."""
    c.saveState()
    c.setLineWidth(size * 0.03)
    t = c.beginText(x, y)
    for seg in segments:
        text = seg[0]
        is_negative = seg[1] if len(seg) > 1 else False
        is_bold = seg[2] if len(seg) > 2 else False
        if text == "":
            continue
        color = NEGATIVE_COLOR if is_negative else colors.black
        use_real_bold = is_bold and font_bold and font_bold != font_normal
        use_fake_bold = is_bold and font_bold and font_bold == font_normal
        t.setFont(font_bold if use_real_bold else font_normal, size)
        t.setFillColor(color)
        if use_fake_bold:
            t.setStrokeColor(color)
            t.setTextRenderMode(2)  # Fuellen + Konturieren
        else:
            t.setTextRenderMode(0)  # nur Fuellen
        t.textOut(text)
    c.drawText(t)
    c.restoreState()


def draw_footer_links(c, width, height, y, links, font_normal, font_bold):
    """Zeichnet den Fussbereich "Weiterfuehrende Dokumente" mit anklickbaren
    Hyperlinks DIREKT IM ANSCHLUSS an die letzte Buchungszeile (nicht am
    unteren Seitenrand verankert). Passt der GESAMTE Block nicht mehr auf
    die aktuelle Seite, wird er als Ganzes -- nicht zeilenweise aufgeteilt
    -- auf eine neue Seite verschoben, die dann oben (wie jede
    Folgeseite) beginnt.

    links: Liste von (name, url)-Tupeln (bereits gefiltert -- beide Werte
    nicht leer). Der Linktext (name) erscheint sichtbar, die URL selbst
    nicht -- sie steckt nur als Klickziel hinter dem Text.

    Gibt die y-Position zurueck, an der der Fussbereich endet (aktuell
    ungenutzt, da der Fussbereich das letzte Element auf der Seite ist)."""
    if not links:
        return y

    footer_height = (1 + len(links)) * FOOTER_LINE_HEIGHT

    # Passt der komplette Block (Titel + alle Links) nicht mehr unterhalb
    # der aktuellen Position auf die Seite, komplett auf eine neue Seite
    # verschieben -- so wird er nie mitten in der Liste umgebrochen.
    if y - FOOTER_TOP_GAP - footer_height < BOTTOM_MARGIN:
        c.showPage()
        y = height - TOP_MARGIN_OTHER

    fy = y - FOOTER_TOP_GAP

    # Duenne Trennlinie oberhalb des Fussbereichs zur optischen Abgrenzung
    # von der Buchungstabelle.
    c.setStrokeColor(colors.Color(0.6, 0.6, 0.6))
    c.setLineWidth(0.5)
    c.line(SIDE_MARGIN, fy + FOOTER_LINE_HEIGHT - 2, width - SIDE_MARGIN, fy + FOOTER_LINE_HEIGHT - 2)

    draw_bold_text(c, SIDE_MARGIN, fy, "Weiterfuehrende Dokumente", font_normal, font_bold, FOOTER_TITLE_SIZE)
    fy -= FOOTER_LINE_HEIGHT

    for name, url in links:
        if fy < BOTTOM_MARGIN:
            # Sicherheitsnetz fuer den (unrealistischen) Fall, dass so
            # viele Links konfiguriert sind, dass selbst eine leere Seite
            # nicht reicht -- dann lieber sauber weiterlaufen als ueber
            # den Rand zu zeichnen.
            c.showPage()
            fy = height - TOP_MARGIN_OTHER
        c.setFont(font_normal, FOOTER_LINK_SIZE)
        c.setFillColor(LINK_COLOR)
        c.drawString(SIDE_MARGIN, fy, name)
        w = c.stringWidth(name, font_normal, FOOTER_LINK_SIZE)
        # Unsichtbare Klickflaeche ueber dem Linktext -- die URL selbst
        # wird nirgends als Text ausgegeben, nur als Klickziel hinterlegt.
        c.linkURL(url, (SIDE_MARGIN, fy - 2, SIDE_MARGIN + w, fy + 8), relative=0)
        c.setStrokeColor(LINK_COLOR)
        c.setLineWidth(0.5)
        c.line(SIDE_MARGIN, fy - 1, SIDE_MARGIN + w, fy - 1)
        fy -= FOOTER_LINE_HEIGHT

    c.setFillColor(colors.black)
    return fy


def make_pdf(out_path, formatted_lines, account, datum, run_time, logo_path,
             header_font_normal=DEFAULT_HEADER_FONT,
             header_font_bold=STANDARD_HEADER_FONTS[DEFAULT_HEADER_FONT],
             hint_text=DEFAULT_HINT_TEXT,
             soll=0.0, haben=0.0, gesamtsaldo=0.0,
             footer_links=None):
    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4

    # -- Kopfbereich nur auf Seite 1 --
    # Feste Textspalte, unabhaengig von der tatsaechlichen Logobreite (wie im
    # Original: dort war die Textposition ebenfalls fix, da die Logo-Box eine
    # feste Groesse hatte). So bleibt der Kopfbereich immer gleich ausgerichtet,
    # egal welches Logo (oder gar keins) eingestellt ist.
    text_x = SIDE_MARGIN + LOGO_MAX_WIDTH + 15
    if logo_path:
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            # In die feste Box (LOGO_MAX_WIDTH x LOGO_MAX_HEIGHT) einpassen,
            # Seitenverhaeltnis erhalten -- das Logo wird also nie groesser
            # dargestellt als das bisherige Lutherschullogo. min(..., 1.0):
            # kleinere Logos werden nur verkleinert, nie hochskaliert (das
            # wuerde bei kleinen Bildern nur zu Pixelbrei fuehren).
            scale = min(LOGO_MAX_WIDTH / iw, LOGO_MAX_HEIGHT / ih, 1.0)
            w, h = iw * scale, ih * scale
            top_y = height - 30
            c.drawImage(logo_path, SIDE_MARGIN, top_y - h, width=w, height=h,
                        mask="auto", preserveAspectRatio=True)
        except Exception as exc:
            print(f"Warnung: Logo konnte nicht eingebettet werden ({exc}).", file=sys.stderr)

    # Defensiv nochmal kappen (nicht nur beim Speichern in der GUI/CLI
    # pruefen), falls config.json von Hand bearbeitet wurde.
    hint_text = (hint_text or "").replace('"', " ")[:HINT_TEXT_MAX_LENGTH]

    draw_bold_text(c, text_x, height - 45, account, header_font_normal, header_font_bold, 11)
    c.setFont(header_font_normal, 8)
    c.drawString(text_x, height - 60, f"Kontoauszug vom {datum}, {run_time} Uhr")

    # Gesamtsaldo/Soll/Haben -- direkt unter "Kontoauszug vom..." ohne
    # Leerzeile. Negative Betraege (typischerweise Soll, ggf. auch ein im
    # Minus stehender Gesamtsaldo) in Rot.
    summary_segments = [
        ("Gesamtsaldo: ", False),
        (format_amount_de(gesamtsaldo), gesamtsaldo < 0),
        ("    Soll: ", False),
        (format_amount_de(soll), soll < 0),
        ("    Haben: ", False),
        (format_amount_de(haben), haben < 0),
    ]
    draw_colored_segments(c, text_x, height - 73, summary_segments, header_font_normal, 8)

    c.setFont(header_font_normal, 7)
    c.drawString(text_x, height - 87, hint_text)

    # -- Buchungszeilen (immer Monospace, siehe TABLE_FONT_NAME oben) --
    # Zusaetzlicher Abstand zum Kopfbereich (siehe HEADER_TABLE_GAP_LINES).
    y = height - TOP_MARGIN_PAGE1 - HEADER_TABLE_GAP_LINES * LINE_HEIGHT
    for i, segments in enumerate(formatted_lines):
        if y < BOTTOM_MARGIN:
            c.showPage()
            y = height - TOP_MARGIN_OTHER
        font = TABLE_FONT_NAME_BOLD if i == 0 else TABLE_FONT_NAME
        draw_colored_segments(c, SIDE_MARGIN, y, segments, font, FONT_SIZE)
        y -= LINE_HEIGHT

    if footer_links:
        draw_footer_links(c, width, height, y, footer_links, header_font_normal, header_font_bold)

    c.save()


# ---------------------------------------------------------------------------
# Hauptverarbeitung
# ---------------------------------------------------------------------------
def process_csv(path, export_dir, logo_path, run_time, delete_csv,
                 header_font_normal=DEFAULT_HEADER_FONT,
                 header_font_bold=STANDARD_HEADER_FONTS[DEFAULT_HEADER_FONT],
                 hint_text=DEFAULT_HINT_TEXT,
                 footer_links=None,
                 log=None):
    log = log or print
    text = read_csv_text(path)
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        log(f"Leere Datei uebersprungen: {os.path.basename(path)}")
        return

    ordered = group_and_sort(lines)
    formatted = format_table(ordered)
    soll, haben, gesamtsaldo = compute_summary(lines[1:])

    stem = os.path.splitext(os.path.basename(path))[0]
    final_stem = shorten_stem(stem)
    account, datum = parse_account_and_date(final_stem)
    # Kontoname stammt aus dem Dateinamen, nicht aus dem CSV-Inhalt -- daher
    # hier defensiv saeubern, falls ein Anfuehrungszeichen im Dateinamen
    # steckt (auf Windows ohnehin unzulaessig, auf Linux/macOS theoretisch
    # moeglich).
    account = account.replace('"', " ")

    out_pdf = os.path.join(export_dir, final_stem + ".pdf")
    make_pdf(out_pdf, formatted, account, datum, run_time, logo_path,
              header_font_normal=header_font_normal, header_font_bold=header_font_bold,
              hint_text=hint_text, soll=soll, haben=haben, gesamtsaldo=gesamtsaldo,
              footer_links=footer_links)
    log(f"OK: {os.path.basename(path)} -> {os.path.basename(out_pdf)}")

    if delete_csv:
        os.remove(path)


def run_export(export_dir, delete_csv=False, logo_path=None, header_font=None,
                header_font_path=None, hint_text=None, footer_links=None,
                files=None, log=None, log_err=None):
    """Verarbeitet CSV-Dateien in export_dir. Wird sowohl von der
    Kommandozeile (main()) als auch von der GUI (starmoney_gui.py) genutzt,
    damit beide exakt dieselbe Logik verwenden.

    files: wenn None (Normalfall), werden ALLE *.csv in export_dir
    verarbeitet. Wird eine Liste konkreter Pfade uebergeben, werden NUR
    diese verarbeitet -- das nutzt der Ueberwachungsmodus (--watch bzw.
    die GUI-Ordnerueberwachung), um gezielt nur neu aufgetauchte Dateien
    zu verarbeiten statt bei jeder Pruefung alle CSVs erneut.

    logo_path / header_font / header_font_path / hint_text: wenn None, wird
    der jeweilige Wert aus config.json gelesen (siehe load_config()).
    Explizite Werte (auch "" fuer "kein Logo") ueberschreiben die
    Konfiguration nur fuer diesen Aufruf, ohne sie zu veraendern.

    log / log_err: Callables, die jeweils eine Textzeile entgegennehmen.
    Standardmaessig gehen normale Meldungen nach stdout, Warnungen/Fehler
    nach stderr (wie beim reinen Kommandozeilenaufruf).

    Gibt (anzahl_verarbeitet, anzahl_fehler) zurueck. Wirft
    FileNotFoundError, wenn export_dir nicht existiert.
    """
    log = log or (lambda m: print(m))
    log_err = log_err or (lambda m: print(m, file=sys.stderr))

    if not os.path.isdir(export_dir):
        raise FileNotFoundError(export_dir)

    cfg = load_config()
    effective_logo = cfg.get("logo_path", "") if logo_path is None else logo_path
    effective_font = cfg.get("header_font", DEFAULT_HEADER_FONT) if header_font is None else header_font
    effective_font_path = cfg.get("header_font_path", "") if header_font_path is None else header_font_path
    effective_hint = cfg.get("hint_text", DEFAULT_HINT_TEXT) if hint_text is None else hint_text
    effective_hint = (effective_hint or "")[:HINT_TEXT_MAX_LENGTH]
    raw_links = cfg.get("footer_links", []) if footer_links is None else footer_links
    # Nur vollstaendige Eintraege (Name UND Link gesetzt) landen im PDF.
    effective_links = [
        (entry.get("name", "").strip(), entry.get("url", "").strip())
        for entry in (raw_links or [])
        if entry.get("name", "").strip() and entry.get("url", "").strip()
    ]

    if files is None:
        csv_files = sorted(glob.glob(os.path.join(export_dir, "*.csv")))
    else:
        csv_files = sorted(files)
    if not csv_files:
        log("Keine CSV-Dateien gefunden.")
        return 0, 0

    resolved_logo = resolve_logo(effective_logo, log_err=log_err)
    header_font_normal, header_font_bold = resolve_header_fonts(
        effective_font, effective_font_path, log_err=log_err)
    run_time = datetime.now().strftime("%H:%M:%S")

    processed, errors = 0, 0
    for path in csv_files:
        try:
            process_csv(path, export_dir, resolved_logo, run_time, delete_csv,
                        header_font_normal=header_font_normal,
                        header_font_bold=header_font_bold,
                        hint_text=effective_hint, footer_links=effective_links, log=log)
            processed += 1
        except Exception as exc:
            errors += 1
            log_err(f"FEHLER bei {os.path.basename(path)}: {exc}")

    if errors:
        log_err(f"Fertig mit {errors} Fehler(n).")
    else:
        log("Alle Kontoauszuege erfolgreich erstellt.")
    return processed, errors


def parse_args():
    p = argparse.ArgumentParser(
        description="StarMoney-CSV-Exporte zu PDF-Kontoauszuegen verarbeiten "
                     "(Windows-Portierung des Original-Bash-Skripts).")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("verzeichnis", nargs="?", default=None,
                    help="Exportverzeichnis (Standard: 'export_auszuege' neben diesem Skript)")
    p.add_argument("--delete-csv", action="store_true",
                    help="Original-CSV nach erfolgreicher Verarbeitung loeschen "
                         "(Verhalten des Original-Bash-Skripts; Standard hier: nein)")
    p.add_argument("--logo", default=None,
                    help="Pfad zu einer Logo-Bilddatei fuer den Kopfbereich "
                         "(leer lassen/weglassen = gespeicherte Einstellung bzw. kein Logo)")
    p.add_argument("--header-font", default=None, choices=list(STANDARD_HEADER_FONTS),
                    help="PDF-Standardschrift fuer den Kopfbereich (Kontoname/Datum/Hinweis)")
    p.add_argument("--header-font-file", default=None,
                    help="Pfad zu einer eigenen .ttf/.otf-Schriftdatei fuer den Kopfbereich "
                         "(hat Vorrang vor --header-font)")
    p.add_argument("--hint-text", default=None, type=_hint_text_arg,
                    help=f"Hinweistext im Kopfbereich (max. {HINT_TEXT_MAX_LENGTH} Zeichen)")
    p.add_argument("--save-config", action="store_true",
                    help="Angegebene --logo/--header-font/--header-font-file/--hint-text dauerhaft "
                         "als Standard in config.json speichern")
    p.add_argument("--watch", nargs="?", const=30, default=None, type=int, metavar="SEKUNDEN",
                    help="Nicht nur einmal verarbeiten, sondern das Verzeichnis dauerhaft alle "
                         "SEKUNDEN (Standard: 30) auf neue CSV-Dateien pruefen. Laeuft bis "
                         "Strg+C. Bereits verarbeitete Dateien werden bei folgenden Pruefungen "
                         "nicht erneut angefasst.")
    return p.parse_args()


def _hint_text_arg(value):
    if len(value) > HINT_TEXT_MAX_LENGTH:
        raise argparse.ArgumentTypeError(
            f"--hint-text darf hoechstens {HINT_TEXT_MAX_LENGTH} Zeichen lang sein "
            f"({len(value)} Zeichen uebergeben).")
    return value


def watch_loop(export_dir, interval_seconds, run_export_kwargs, log=None, log_err=None,
                sleep_func=None, stop_check=None):
    """Prueft export_dir alle interval_seconds Sekunden auf neue CSV-Dateien
    und verarbeitet nur diese (nicht die gesamte bereits bekannte Menge
    erneut). Laeuft endlos, bis KeyboardInterrupt (Strg+C) oder -- falls
    angegeben -- stop_check() True zurueckgibt (fuer die GUI, die diese
    Funktion nicht direkt nutzt, aber dieselbe Kernlogik ueber
    find_new_csv_files() nachbildet).

    sleep_func: austauschbar fuer Tests (Standard: time.sleep).
    Gibt nie regulaer zurueck (Endlosschleife), ausser stop_check greift."""
    log = log or (lambda m: print(m))
    log_err = log_err or (lambda m: print(m, file=sys.stderr))
    sleep_func = sleep_func or time.sleep

    known = set(glob.glob(os.path.join(export_dir, "*.csv")))
    log(f"Ueberwachung gestartet: {export_dir} (Pruefung alle {interval_seconds}s, "
        f"Strg+C zum Beenden). {len(known)} vorhandene CSV-Datei(en) werden jetzt verarbeitet.")
    if known:
        run_export(export_dir, files=sorted(known), log=log, log_err=log_err, **run_export_kwargs)

    while True:
        if stop_check and stop_check():
            return
        sleep_func(interval_seconds)
        if stop_check and stop_check():
            return
        current = set(glob.glob(os.path.join(export_dir, "*.csv")))
        new_files = current - known
        if new_files:
            log(f"{len(new_files)} neue CSV-Datei(en) gefunden.")
            run_export(export_dir, files=sorted(new_files), log=log, log_err=log_err,
                       **run_export_kwargs)
        # Unabhaengig vom Ergebnis als "gesehen" merken -- verhindert
        # endloses erneutes Verarbeiten, auch wenn delete_csv aus ist oder
        # eine Datei nicht geloescht werden konnte.
        known |= current


def main():
    args = parse_args()
    export_dir = args.verzeichnis or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "export_auszuege")

    if args.save_config:
        updates = {}
        if args.logo is not None:
            updates["logo_path"] = args.logo
        if args.header_font is not None:
            updates["header_font"] = args.header_font
        if args.header_font_file is not None:
            updates["header_font_path"] = args.header_font_file
        if args.hint_text is not None:
            updates["hint_text"] = args.hint_text
        if updates:
            save_config(updates)

    run_export_kwargs = dict(
        delete_csv=args.delete_csv, logo_path=args.logo,
        header_font=args.header_font, header_font_path=args.header_font_file,
        hint_text=args.hint_text)

    if args.watch is not None:
        if not os.path.isdir(export_dir):
            print(f"Verzeichnis nicht gefunden: {export_dir}", file=sys.stderr)
            sys.exit(1)
        try:
            watch_loop(export_dir, args.watch, run_export_kwargs)
        except KeyboardInterrupt:
            print("\nUeberwachung beendet.")
        return

    try:
        processed, errors = run_export(export_dir, **run_export_kwargs)
    except FileNotFoundError:
        print(f"Verzeichnis nicht gefunden: {export_dir}", file=sys.stderr)
        sys.exit(1)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
