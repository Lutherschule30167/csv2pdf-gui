#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StarMoney-CSV zu PDF-Kontoauszug -- Windows-Portierung
=======================================================

Reines Python-Aequivalent des urspruenglichen Linux-Bash-Skripts fuer die
Lutherschule Hannover. Lauffaehig unter Windows (und weiterhin auch unter
Linux/macOS), ohne die externen Kommandozeilen-Tools des Originals
(ghostscript, paps, ImageMagick, qpdf, iconv, column, curl, perl-rename).
Die PDFs werden direkt mit reportlab erzeugt.

Einzige externe Abhaengigkeit: reportlab
    pip install reportlab

Verwendung:
    python starmoney_export.py [Exportverzeichnis] [--delete-csv]

Ohne Pfadangabe wird der Ordner "export_auszuege" neben diesem Skript
verwendet. Mit --delete-csv werden die Original-CSV-Dateien nach
erfolgreicher Verarbeitung geloescht (so wie im Original-Bash-Skript);
ohne dieses Flag bleiben sie erhalten (sichererer Standard fuer diese
neue Portierung).

Entstanden mit Unterstuetzung von Claude (Anthropic).
Lizenz: MIT
"""

import argparse
import glob
import os
import re
import sys
import urllib.request
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
LOGO_URL = "https://lutherschule.eu/iserv/logo/logo.5e444978.png"
LOGO_FILENAME = ".lutherschule-logo.png"
HINWEIS_TEXT = ("Hinweis: Buchungen innerhalb eines Tages sind evtl. nicht "
                "in der richtigen Reihenfolge gelistet.")

FONT_NAME = "Courier"
FONT_NAME_BOLD = "Courier-Bold"
FONT_SIZE = 7
LINE_HEIGHT = FONT_SIZE * 1.15

TOP_MARGIN_PAGE1 = 100   # Platz fuer Logo/Kontoname/Datum -- nur auf Seite 1
TOP_MARGIN_OTHER = 36
BOTTOM_MARGIN = 36
SIDE_MARGIN = 28

MAX_LINE_WIDTH = 120                  # entspricht "column -c 120"
FIXED_WIDTHS = {2: 30, 3: 10, 4: 10}   # 1-indiziert wie im Original (Spalte 2/3/4)
RIGHT_ALIGN_COLUMNS = {3, 4}           # entspricht "-R 3,4"
TRUNCATE_COLUMNS = {5}                 # entspricht "-T 5"
SEPARATOR = "||"                       # entspricht "column -o '||'"

SHORTEN_RE = re.compile(r'^([^.]+)_([^.]+)_([^.]+)_([^.]+)_([^.]+)$')


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
        fields = line.split(";")
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

    def render(fields, is_header=False):
        cells = []
        for c in range(ncols):
            col_idx = c + 1
            val = fields[c][: widths[c]]
            cells.append(val.rjust(widths[c]) if col_idx in RIGHT_ALIGN_COLUMNS else val.ljust(widths[c]))
        if is_header:
            for c in range(min(4, ncols)):
                cells[c] = cells[c] + "  "
        return SEPARATOR.join(cells)

    out_lines = [render(padded_header, is_header=True)]
    idx = 0
    for ln in data_lines:
        if ln == "":
            out_lines.append("")
        else:
            out_lines.append(render(padded_rows[idx]))
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
# Logo
# ---------------------------------------------------------------------------
def ensure_logo(export_dir, log_err=None):
    log_err = log_err or (lambda m: print(m, file=sys.stderr))
    path = os.path.join(export_dir, LOGO_FILENAME)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    try:
        urllib.request.urlretrieve(LOGO_URL, path)
        if os.path.getsize(path) == 0:
            raise IOError("leere Datei")
        return path
    except Exception as exc:
        log_err(f"Warnung: Logo konnte nicht heruntergeladen werden ({exc}) "
                f"- Kopfseite ohne Logo.")
        return None


# ---------------------------------------------------------------------------
# PDF-Erzeugung (ersetzt paps+ghostscript fuer den Text und
# ImageMagick+qpdf fuer die untergelegte Kopfseite -- hier direkt in
# einem Durchgang mit reportlab statt zweier separat verschmolzener PDFs)
# ---------------------------------------------------------------------------
def make_pdf(out_path, formatted_lines, account, datum, run_time, logo_path):
    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4

    # -- Kopfbereich nur auf Seite 1 --
    text_x = SIDE_MARGIN
    if logo_path:
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            max_h = 60.0
            scale = max_h / ih
            w = iw * scale
            c.drawImage(logo_path, SIDE_MARGIN, height - 90, width=w, height=max_h,
                        mask="auto", preserveAspectRatio=True)
            text_x = SIDE_MARGIN + w + 15
        except Exception as exc:
            print(f"Warnung: Logo konnte nicht eingebettet werden ({exc}).", file=sys.stderr)

    c.setFont(FONT_NAME_BOLD, 11)
    c.drawString(text_x, height - 45, account)
    c.setFont(FONT_NAME, 8)
    c.drawString(text_x, height - 60, f"Kontoauszug vom {datum}, {run_time} Uhr")
    c.setFont(FONT_NAME, 7)
    c.drawString(text_x, height - 78, HINWEIS_TEXT)

    # -- Buchungszeilen --
    y = height - TOP_MARGIN_PAGE1
    on_first_page = True
    for i, line in enumerate(formatted_lines):
        if y < BOTTOM_MARGIN:
            c.showPage()
            on_first_page = False
            y = height - TOP_MARGIN_OTHER
        font = FONT_NAME_BOLD if i == 0 else FONT_NAME
        c.setFont(font, FONT_SIZE)
        c.drawString(SIDE_MARGIN, y, line)
        y -= LINE_HEIGHT

    c.save()


# ---------------------------------------------------------------------------
# Hauptverarbeitung
# ---------------------------------------------------------------------------
def process_csv(path, export_dir, logo_path, run_time, delete_csv, log=None):
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

    stem = os.path.splitext(os.path.basename(path))[0]
    final_stem = shorten_stem(stem)
    account, datum = parse_account_and_date(final_stem)

    out_pdf = os.path.join(export_dir, final_stem + ".pdf")
    make_pdf(out_pdf, formatted, account, datum, run_time, logo_path)
    log(f"OK: {os.path.basename(path)} -> {os.path.basename(out_pdf)}")

    if delete_csv:
        os.remove(path)


def run_export(export_dir, delete_csv=False, log=None, log_err=None):
    """Verarbeitet alle CSV-Dateien in export_dir. Wird sowohl von der
    Kommandozeile (main()) als auch von der GUI (starmoney_gui.py) genutzt,
    damit beide exakt dieselbe Logik verwenden.

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

    csv_files = sorted(glob.glob(os.path.join(export_dir, "*.csv")))
    if not csv_files:
        log("Keine CSV-Dateien gefunden.")
        return 0, 0

    logo_path = ensure_logo(export_dir, log_err=log_err)
    run_time = datetime.now().strftime("%H:%M:%S")

    processed, errors = 0, 0
    for path in csv_files:
        try:
            process_csv(path, export_dir, logo_path, run_time, delete_csv, log=log)
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
    p.add_argument("verzeichnis", nargs="?", default=None,
                    help="Exportverzeichnis (Standard: 'export_auszuege' neben diesem Skript)")
    p.add_argument("--delete-csv", action="store_true",
                    help="Original-CSV nach erfolgreicher Verarbeitung loeschen "
                         "(Verhalten des Original-Bash-Skripts; Standard hier: nein)")
    return p.parse_args()


def main():
    args = parse_args()
    export_dir = args.verzeichnis or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "export_auszuege")

    try:
        processed, errors = run_export(export_dir, delete_csv=args.delete_csv)
    except FileNotFoundError:
        print(f"Verzeichnis nicht gefunden: {export_dir}", file=sys.stderr)
        sys.exit(1)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
