#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StarMoney-Kontoauszuege -- einfache GUI fuer Endbenutzer
=========================================================

Grafische Oberflaeche fuer starmoney_export.py. Muss im selben Ordner wie
diese Datei liegen. Verwendet nur die Python-Standardbibliothek (tkinter)
fuer die Oberflaeche -- keine zusaetzliche Abhaengigkeit noetig ausser
reportlab (siehe requirements.txt), das starmoney_export.py fuer die
PDF-Erzeugung braucht.

Logo und Kopf-Schriftart sind hier ebenfalls einstellbar (kein festes
Schullogo mehr) und werden in derselben config.json gespeichert, die auch
die Kommandozeilenversion (--save-config) nutzt.

Start (Doppelklick oder):
    python starmoney_gui.py

Entstanden mit Unterstuetzung von Claude (Anthropic).
Lizenz: MIT
"""

import glob
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# starmoney_export.py muss im selben Ordner liegen. Konfiguration
# (Logo/Schriftart/Exportordner/...) wird komplett von dort uebernommen,
# damit CLI und GUI dieselbe config.json teilen.
try:
    sys.path.insert(0, SCRIPT_DIR)
    import starmoney_export as backend
except Exception as exc:  # pragma: no cover - nur zur Laufzeit relevant
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Fehler beim Start",
        "starmoney_export.py konnte nicht geladen werden.\n"
        "Bitte sicherstellen, dass die Datei im selben Ordner liegt wie "
        "starmoney_gui.py, und dass 'reportlab' installiert ist "
        "(pip install -r requirements.txt).\n\nFehlermeldung:\n" + str(exc),
    )
    sys.exit(1)

HEADER_FONT_CHOICES = list(backend.STANDARD_HEADER_FONTS.keys())
BILD_FILETYPES = [
    ("Bilddateien", "*.png *.jpg *.jpeg *.gif *.bmp"),
    ("Alle Dateien", "*.*"),
]
FONT_FILETYPES = [
    ("Schriftdateien", "*.ttf *.otf"),
    ("Alle Dateien", "*.*"),
]

# Vorschaugroesse in Pixel -- bewusst im selben Seitenverhaeltnis wie die
# tatsaechliche Begrenzung im PDF (siehe backend.LOGO_MAX_WIDTH/HEIGHT,
# 78x60 pt), nur groesser dargestellt, damit man im Fenster etwas erkennt.
PREVIEW_MAX_W = 156
PREVIEW_MAX_H = 120


def open_folder(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as exc:
        messagebox.showwarning("Ordner oeffnen", f"Ordner konnte nicht geoeffnet werden:\n{exc}")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"StarMoney-Kontoauszuege erstellen (Version {backend.__version__})")
        self.geometry("760x600")
        self.minsize(640, 480)

        self.log_queue = queue.Queue()
        self.worker_running = False

        cfg = backend.load_config()
        default_dir = cfg.get("export_dir") or os.path.join(backend.app_dir(), "export_auszuege")
        self.export_dir = tk.StringVar(value=default_dir)
        self.delete_csv = tk.BooleanVar(value=cfg.get("delete_csv", False))
        self.logo_path = tk.StringVar(value=cfg.get("logo_path", ""))
        header_font = cfg.get("header_font", backend.DEFAULT_HEADER_FONT)
        self.header_font_choice = tk.StringVar(
            value=header_font if header_font in HEADER_FONT_CHOICES else backend.DEFAULT_HEADER_FONT
        )
        self.header_font_path = tk.StringVar(value=cfg.get("header_font_path", ""))
        self.hint_text = tk.StringVar(value=cfg.get("hint_text", backend.DEFAULT_HINT_TEXT))
        self.footer_links = list(cfg.get("footer_links", []))  # Liste von {"name":..., "url":...}
        self.watch_enabled = tk.BooleanVar(value=False)  # startet immer aus, bewusst nicht persistiert
        self.watch_interval = tk.IntVar(value=int(cfg.get("watch_interval_seconds", 30)))
        self._watch_after_id = None
        self._watch_known_files = set()
        self._logo_preview_image = None  # Referenz halten, sonst sammelt Tk das Bild vorzeitig ein

        self._build_widgets()
        self._refresh_csv_count()
        self._update_logo_preview()
        self.after(100, self._poll_log_queue)

    # ------------------------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)
        options_menu = tk.Menu(menubar, tearoff=False)
        options_menu.add_command(label="Einstellungen...", command=self._open_settings)
        menubar.add_cascade(label="Optionen", menu=options_menu)
        self.config(menu=menubar)

    def _build_widgets(self):
        pad = {"padx": 10, "pady": 6}

        self._build_menu()

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Exportordner:").pack(side="left")
        ttk.Entry(top, textvariable=self.export_dir).pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(top, text="Ordner waehlen...", command=self._choose_dir).pack(side="left")

        info = ttk.Frame(self)
        info.pack(fill="x", **pad)
        self.count_label = ttk.Label(info, text="")
        self.count_label.pack(side="left")

        # -- Nur die Anzeige des aktuell eingestellten Logos bleibt im
        # Hauptfenster sichtbar; Aendern geschieht ueber Optionen ->
        # Einstellungen (siehe _open_settings).
        logo_display = ttk.Frame(self)
        logo_display.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(logo_display, text="Aktuelles Logo:").pack(side="left")
        self.logo_preview_label = ttk.Label(
            logo_display, text="(kein Logo eingestellt)", foreground="#555555",
            relief="groove", anchor="center", justify="center",
        )
        self.logo_preview_label.pack(side="left", padx=(8, 0))
        ttk.Label(
            logo_display, text="(aenderbar unter Optionen -> Einstellungen)",
            foreground="#777777",
        ).pack(side="left", padx=(10, 0))

        opts = ttk.Frame(self)
        opts.pack(fill="x", **pad)
        ttk.Checkbutton(
            opts,
            text="Original-CSV-Dateien nach erfolgreicher Verarbeitung loeschen",
            variable=self.delete_csv,
            command=self._save_settings,
        ).pack(side="left")

        actions = ttk.Frame(self)
        actions.pack(fill="x", **pad)
        self.run_button = ttk.Button(actions, text="Kontoauszuege erstellen", command=self._start_run)
        self.run_button.pack(side="left")
        self.open_button = ttk.Button(actions, text="Ordner oeffnen", command=self._open_export_dir)
        self.open_button.pack(side="left", padx=(8, 0))

        watch_row = ttk.Frame(self)
        watch_row.pack(fill="x", **pad)
        ttk.Checkbutton(
            watch_row,
            text="Ordner automatisch auf neue CSV-Dateien ueberwachen, alle",
            variable=self.watch_enabled,
            command=self._toggle_watch,
        ).pack(side="left")
        ttk.Spinbox(
            watch_row, from_=5, to=3600, increment=5, width=6,
            textvariable=self.watch_interval, justify="right",
        ).pack(side="left", padx=(4, 4))
        ttk.Label(watch_row, text="Sekunden").pack(side="left")
        self.watch_status_label = ttk.Label(watch_row, text="Ueberwachung inaktiv", foreground="#555555")
        self.watch_status_label.pack(side="left", padx=(10, 0))

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", **pad)

        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True, **pad)
        ttk.Label(log_frame, text="Protokoll:").pack(anchor="w")
        self.log_widget = scrolledtext.ScrolledText(log_frame, height=14, state="disabled", wrap="word")
        self.log_widget.pack(fill="both", expand=True)

        self.export_dir.trace_add("write", lambda *_: self._refresh_csv_count())
        self.logo_path.trace_add("write", lambda *_: self._update_logo_preview())
        self.hint_text.trace_add("write", self._update_hint_counter)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    def _open_settings(self):
        """Oeffnet den Einstellungen-Dialog (Optionen -> Einstellungen).
        Die Widgets darin sind an dieselben StringVar/BooleanVar gebunden
        wie ueberall sonst -- Aenderungen dort aktualisieren live auch die
        Logo-Vorschau im Hauptfenster (ueber den bestehenden trace_add),
        ganz ohne doppelten Zustand."""
        if getattr(self, "_settings_win", None) is not None and self._settings_win.winfo_exists():
            self._settings_win.lift()
            self._settings_win.focus_set()
            return

        win = tk.Toplevel(self)
        win.title("Einstellungen fuer den Kopfbereich der PDFs")
        win.resizable(False, False)
        win.transient(self)
        self._settings_win = win

        pad = {"padx": 8, "pady": 6}

        logo_row = ttk.Frame(win)
        logo_row.pack(fill="x", **pad)
        ttk.Label(logo_row, text="Logo:", width=16).pack(side="left")
        logo_entry = ttk.Entry(logo_row, textvariable=self.logo_path, width=42)
        logo_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        logo_entry.bind("<FocusOut>", lambda *_: self._save_settings())
        ttk.Button(logo_row, text="Durchsuchen...", command=self._choose_logo).pack(side="left")
        ttk.Button(logo_row, text="Entfernen", command=self._clear_logo).pack(side="left", padx=(6, 0))

        ttk.Label(
            win,
            text=(f"Wird im Kopfbereich auf max. {backend.LOGO_MAX_WIDTH:.0f}\u00d7"
                  f"{backend.LOGO_MAX_HEIGHT:.0f} pt skaliert (Seitenverhaeltnis bleibt erhalten) -\n"
                  f"das entspricht der bisherigen Groesse des Lutherschullogos. Groessere Logos werden\n"
                  f"automatisch verkleinert, kleinere nicht vergroessert dargestellt."),
            foreground="#555555", justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 8))

        font_row = ttk.Frame(win)
        font_row.pack(fill="x", **pad)
        ttk.Label(font_row, text="Kopf-Schriftart:", width=16).pack(side="left")
        font_combo = ttk.Combobox(
            font_row, textvariable=self.header_font_choice, values=HEADER_FONT_CHOICES,
            state="readonly", width=20,
        )
        font_combo.pack(side="left")
        font_combo.bind("<<ComboboxSelected>>", lambda *_: self._save_settings())

        font_file_row = ttk.Frame(win)
        font_file_row.pack(fill="x", **pad)
        ttk.Label(font_file_row, text="eigene Schriftdatei:", width=16).pack(side="left")
        font_file_entry = ttk.Entry(font_file_row, textvariable=self.header_font_path, width=42)
        font_file_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        font_file_entry.bind("<FocusOut>", lambda *_: self._save_settings())
        ttk.Button(font_file_row, text="Durchsuchen...", command=self._choose_font).pack(side="left")
        ttk.Button(font_file_row, text="Entfernen", command=self._clear_font).pack(side="left", padx=(6, 0))

        ttk.Label(
            win,
            text="Ist eine eigene Schriftdatei (.ttf/.otf) angegeben, hat sie Vorrang vor der Auswahl oben.",
            foreground="#555555",
        ).pack(anchor="w", padx=8, pady=(0, 8))

        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=8, pady=(0, 8))

        hint_row = ttk.Frame(win)
        hint_row.pack(fill="x", **pad)
        ttk.Label(hint_row, text="Hinweistext:", width=16).pack(side="left")
        vcmd = (self.register(self._validate_hint_text), "%P")
        hint_entry = ttk.Entry(
            hint_row, textvariable=self.hint_text, width=42,
            validate="key", validatecommand=vcmd,
        )
        hint_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        hint_entry.bind("<FocusOut>", lambda *_: self._save_settings())

        counter_row = ttk.Frame(win)
        counter_row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(counter_row, text="", width=16).pack(side="left")  # Einrueckung passend zu hint_row
        self.hint_counter_label = ttk.Label(counter_row, text="", foreground="#555555")
        self.hint_counter_label.pack(side="left")
        self._update_hint_counter()

        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=8, pady=(0, 8))

        ttk.Label(win, text="Weiterfuehrende Dokumente (Fussbereich der PDFs):").pack(
            anchor="w", padx=8)
        ttk.Label(
            win,
            text=("Der Name erscheint als klickbarer Link am Fuss jedes Kontoauszugs; der Link\n"
                  "selbst wird nirgends sichtbar ausgegeben, nur als Klickziel hinterlegt."),
            foreground="#555555", justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 6))

        self.links_frame = ttk.Frame(win)
        self.links_frame.pack(fill="x", padx=8)
        self.link_rows = []
        for entry in (self.footer_links or [{}, {}, {}]):
            self._add_link_row(entry.get("name", ""), entry.get("url", ""), save=False)

        ttk.Button(win, text="+ Dokument hinzufuegen", command=lambda: self._add_link_row()).pack(
            anchor="w", padx=8, pady=(4, 8))

        ttk.Button(win, text="Schliessen", command=win.destroy).pack(pady=(0, 10))

    # ------------------------------------------------------------------
    def _save_settings(self):
        """Speichert alle aktuellen Einstellungen sofort in config.json --
        aufgerufen bei jeder bewussten Aenderung (Logo/Schriftart waehlen
        oder entfernen, Haekchen umschalten, Ordner ausserhalb eines
        Entry-Feldes verlassen) sowie beim Schliessen des Fensters, damit
        nichts verloren geht, auch wenn nie "Kontoauszuege erstellen"
        geklickt wird. Das Ueberwachen-Haekchen selbst wird bewusst NICHT
        gespeichert (siehe watch_enabled in __init__) -- nur das Intervall."""
        try:
            watch_interval = int(self.watch_interval.get())
        except (ValueError, tk.TclError):
            watch_interval = 30
        try:
            backend.save_config({
                "export_dir": self.export_dir.get().strip(),
                "delete_csv": self.delete_csv.get(),
                "logo_path": self.logo_path.get().strip(),
                "header_font": self.header_font_choice.get(),
                "header_font_path": self.header_font_path.get().strip(),
                "hint_text": self.hint_text.get(),
                "footer_links": self.footer_links,
                "watch_interval_seconds": watch_interval,
            })
        except Exception:
            pass  # Auto-Save ist reine Komfortfunktion, kein kritischer Fehler

    def _on_close(self):
        self._stop_watch()
        self._save_settings()
        self.destroy()

    def _choose_dir(self):
        chosen = filedialog.askdirectory(
            title="Exportordner mit den StarMoney-CSV-Dateien waehlen",
            initialdir=self.export_dir.get() if os.path.isdir(self.export_dir.get()) else backend.app_dir(),
        )
        if chosen:
            self.export_dir.set(chosen)
            self._save_settings()

    def _choose_logo(self):
        chosen = filedialog.askopenfilename(title="Logo-Bilddatei waehlen", filetypes=BILD_FILETYPES)
        if chosen:
            self.logo_path.set(chosen)
            self._save_settings()

    def _clear_logo(self):
        self.logo_path.set("")
        self._save_settings()

    def _clear_font(self):
        self.header_font_path.set("")
        self._save_settings()

    def _add_link_row(self, name="", url="", save=True):
        row = ttk.Frame(self.links_frame)
        row.pack(fill="x", pady=2)
        name_var = tk.StringVar(value=name)
        url_var = tk.StringVar(value=url)
        ttk.Label(row, text="Name:").pack(side="left")
        name_entry = ttk.Entry(row, textvariable=name_var, width=18)
        name_entry.pack(side="left", padx=(2, 8))
        ttk.Label(row, text="Link:").pack(side="left")
        url_entry = ttk.Entry(row, textvariable=url_var, width=28)
        url_entry.pack(side="left", padx=(2, 8), fill="x", expand=True)
        ttk.Button(row, text="Entfernen", width=10,
                   command=lambda: self._remove_link_row(row)).pack(side="left")
        name_entry.bind("<FocusOut>", lambda *_: self._save_footer_links())
        url_entry.bind("<FocusOut>", lambda *_: self._save_footer_links())
        self.link_rows.append((name_var, url_var, row))
        if save:
            self._save_footer_links()

    def _remove_link_row(self, row_frame):
        self.link_rows = [(n, u, r) for (n, u, r) in self.link_rows if r is not row_frame]
        row_frame.destroy()
        self._save_footer_links()

    def _save_footer_links(self):
        links = []
        for name_var, url_var, _ in self.link_rows:
            name = name_var.get().strip()
            url = url_var.get().strip()
            if name or url:
                links.append({"name": name, "url": url})
        self.footer_links = links
        self._save_settings()

    def _validate_hint_text(self, proposed):
        return len(proposed) <= backend.HINT_TEXT_MAX_LENGTH

    def _update_hint_counter(self, *_):
        label = getattr(self, "hint_counter_label", None)
        if label is not None and label.winfo_exists():
            n = len(self.hint_text.get())
            label.config(text=f"{n}/{backend.HINT_TEXT_MAX_LENGTH} Zeichen")

    def _update_logo_preview(self):
        path = self.logo_path.get().strip()
        if not path:
            self.logo_preview_label.config(image="", text="(kein Logo ausgewaehlt)")
            self._logo_preview_image = None
            return
        if not os.path.isfile(path):
            self.logo_preview_label.config(image="", text="(Datei nicht gefunden)")
            self._logo_preview_image = None
            return
        try:
            if PIL_AVAILABLE:
                img = Image.open(path)
                img.thumbnail((PREVIEW_MAX_W, PREVIEW_MAX_H))
                photo = ImageTk.PhotoImage(img)
            else:
                photo = tk.PhotoImage(file=path)
                photo = self._shrink_photoimage(photo, PREVIEW_MAX_W, PREVIEW_MAX_H)
            self._logo_preview_image = photo  # Referenz halten!
            self.logo_preview_label.config(image=photo, text="")
        except Exception:
            self._logo_preview_image = None
            hint = "" if PIL_AVAILABLE else "\n(Tipp: fuer JPG/BMP 'pip install Pillow')"
            self.logo_preview_label.config(image="", text=f"Vorschau nicht moeglich.{hint}")

    @staticmethod
    def _shrink_photoimage(photo, max_w, max_h):
        """Grobe Verkleinerung ohne Pillow -- tk.PhotoImage kann nur um
        ganzzahlige Faktoren verkleinern (subsample), das reicht fuer eine
        Vorschau."""
        w, h = photo.width(), photo.height()
        if w <= max_w and h <= max_h or w == 0 or h == 0:
            return photo
        factor = max(1, -(-max(w / max_w, h / max_h) // 1))  # aufrunden
        return photo.subsample(int(factor), int(factor))

    def _choose_font(self):
        chosen = filedialog.askopenfilename(title="Schriftdatei waehlen", filetypes=FONT_FILETYPES)
        if chosen:
            self.header_font_path.set(chosen)
            self._save_settings()

    def _refresh_csv_count(self):
        d = self.export_dir.get()
        if os.path.isdir(d):
            try:
                n = len([f for f in os.listdir(d) if f.lower().endswith(".csv")])
                self.count_label.config(text=f"{n} CSV-Datei(en) in diesem Ordner gefunden.")
            except Exception:
                self.count_label.config(text="Ordner kann nicht gelesen werden.")
        else:
            self.count_label.config(text="Ordner existiert noch nicht.")

    def _open_export_dir(self):
        d = self.export_dir.get()
        if os.path.isdir(d):
            open_folder(d)
        else:
            messagebox.showinfo("Ordner oeffnen", "Dieser Ordner existiert noch nicht.")

    # ------------------------------------------------------------------
    def _toggle_watch(self):
        """Ein-/Ausschalten der automatischen Ordnerueberwachung. Startet
        nie automatisch beim Programmstart -- muss jede Sitzung bewusst
        angeschaltet werden, da sie selbststaendig Dateien anlegt (und bei
        aktivem "loeschen"-Haekchen auch loescht)."""
        if self.watch_enabled.get():
            d = self.export_dir.get().strip()
            if not d or not os.path.isdir(d):
                messagebox.showwarning(
                    "Kein Ordner", "Bitte zuerst einen bestehenden Exportordner waehlen.")
                self.watch_enabled.set(False)
                return
            try:
                interval = int(self.watch_interval.get())
                if interval < 1:
                    raise ValueError
            except (ValueError, tk.TclError):
                messagebox.showwarning("Ungueltiges Intervall", "Bitte eine ganze Zahl (Sekunden) angeben.")
                self.watch_enabled.set(False)
                return

            try:
                backend.save_config({"watch_interval_seconds": interval})
            except Exception:
                pass

            # Aktuellen Stand einmal normal verarbeiten (wie ein manueller
            # Klick), danach gelten alle jetzt vorhandenen CSVs als
            # "bekannt" -- nur wirklich neu hinzukommende werden von der
            # Ueberwachung selbst noch verarbeitet.
            self._watch_known_files = set(glob.glob(os.path.join(d, "*.csv")))
            self._launch_run(d, files=None, clear_log=True, silent=True)
            self.watch_status_label.config(text="Ueberwachung aktiv")
            self._schedule_watch_tick(interval)
        else:
            self._stop_watch()

    def _stop_watch(self):
        if self._watch_after_id is not None:
            self.after_cancel(self._watch_after_id)
            self._watch_after_id = None
        self.watch_status_label.config(text="Ueberwachung inaktiv")

    def _schedule_watch_tick(self, interval_seconds):
        self._watch_after_id = self.after(int(interval_seconds * 1000), self._watch_tick)

    def _watch_tick(self):
        if not self.watch_enabled.get():
            return  # zwischenzeitlich ausgeschaltet
        d = self.export_dir.get().strip()
        try:
            interval = max(1, int(self.watch_interval.get()))
        except (ValueError, tk.TclError):
            interval = 30

        if os.path.isdir(d) and not self.worker_running:
            current = set(glob.glob(os.path.join(d, "*.csv")))
            new_files = current - self._watch_known_files
            if new_files:
                self._append_log(f"Ueberwachung: {len(new_files)} neue CSV-Datei(en) gefunden.")
                self._launch_run(d, files=sorted(new_files), clear_log=False, silent=True)
            # Unabhaengig vom Ergebnis als bekannt vermerken -- verhindert
            # endloses erneutes Verarbeiten, auch wenn "loeschen" aus ist.
            self._watch_known_files |= current

        self._schedule_watch_tick(interval)

    def _append_log(self, text):
        self.log_widget.config(state="normal")
        self.log_widget.insert("end", text + "\n")
        self.log_widget.see("end")
        self.log_widget.config(state="disabled")

    # ------------------------------------------------------------------
    def _start_run(self):
        d = self.export_dir.get().strip()
        if not d:
            messagebox.showwarning("Kein Ordner", "Bitte zuerst einen Exportordner waehlen.")
            return
        if not os.path.isdir(d):
            create = messagebox.askyesno(
                "Ordner nicht gefunden",
                f"Der Ordner\n{d}\nexistiert noch nicht. Jetzt anlegen?",
            )
            if create:
                try:
                    os.makedirs(d, exist_ok=True)
                except Exception as exc:
                    messagebox.showerror("Fehler", f"Ordner konnte nicht angelegt werden:\n{exc}")
                    return
            else:
                return
        self._launch_run(d, files=None, clear_log=True)

    def _launch_run(self, export_dir, files=None, clear_log=False, silent=False):
        """Startet einen Hintergrund-Lauf. files=None verarbeitet den
        gesamten Ordner (manueller Klick auf "Kontoauszuege erstellen");
        eine konkrete Liste verarbeitet nur diese (von der automatischen
        Ueberwachung genutzt). silent=True unterdrueckt den abschliessenden
        Popup-Dialog (der ist modal und wuerde die automatische
        Ueberwachung blockieren, bis er weggeklickt wird) -- das Ergebnis
        landet dann nur im Protokoll. Gibt False zurueck, wenn bereits ein
        Lauf aktiv ist (dann passiert nichts -- weder manuell noch
        automatisch ueberlappen sich zwei Laeufe)."""
        if self.worker_running:
            return False

        logo_path = self.logo_path.get().strip()
        header_font = self.header_font_choice.get()
        header_font_path = self.header_font_path.get().strip()
        hint_text = self.hint_text.get()
        footer_links = list(self.footer_links)
        delete_csv = self.delete_csv.get()

        self._save_settings()

        if clear_log:
            self.log_widget.config(state="normal")
            self.log_widget.delete("1.0", "end")
            self.log_widget.config(state="disabled")

        self.worker_running = True
        self.run_button.config(state="disabled")
        self.progress.start(12)

        thread = threading.Thread(
            target=self._worker,
            args=(export_dir, delete_csv, logo_path, header_font, header_font_path,
                  hint_text, footer_links, files, silent),
            daemon=True,
        )
        thread.start()
        return True

    def _worker(self, export_dir, delete_csv, logo_path, header_font, header_font_path,
                hint_text, footer_links, files=None, silent=False):
        try:
            processed, errors = backend.run_export(
                export_dir,
                delete_csv=delete_csv,
                logo_path=logo_path,
                header_font=header_font,
                header_font_path=header_font_path,
                hint_text=hint_text,
                footer_links=footer_links,
                files=files,
                log=self.log_queue.put,
                log_err=self.log_queue.put,
            )
            self.log_queue.put(("__DONE__", processed, errors, silent))
        except FileNotFoundError:
            self.log_queue.put(f"Verzeichnis nicht gefunden: {export_dir}")
            self.log_queue.put(("__DONE__", 0, 1, silent))
        except Exception as exc:
            self.log_queue.put(f"Unerwarteter Fehler: {exc}")
            self.log_queue.put(("__DONE__", 0, 1, silent))

    def _poll_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple) and item and item[0] == "__DONE__":
                    _, processed, errors, silent = item
                    self._finish_run(processed, errors, silent)
                else:
                    self._append_log(str(item))
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _finish_run(self, processed, errors, silent=False):
        self.worker_running = False
        self.run_button.config(state="normal")
        self.progress.stop()
        self._refresh_csv_count()
        if silent:
            # Automatischer Lauf (Ueberwachung): kein modaler Dialog, der
            # den Hintergrundbetrieb blockieren wuerde -- nur ins Protokoll.
            if errors:
                self._append_log(f"Ueberwachung: {processed} verarbeitet, {errors} Fehler.")
            elif processed:
                self._append_log(f"Ueberwachung: {processed} Kontoauszug/-zuege erstellt.")
            return
        if errors:
            messagebox.showwarning(
                "Fertig mit Fehlern",
                f"{processed} Kontoauszug/-zuege erstellt, {errors} Fehler.\n"
                "Details siehe Protokoll.",
            )
        elif processed:
            messagebox.showinfo("Fertig", f"{processed} Kontoauszug/-zuege erfolgreich erstellt.")
        else:
            messagebox.showinfo("Fertig", "Keine CSV-Dateien gefunden.")


if __name__ == "__main__":
    App().mainloop()
