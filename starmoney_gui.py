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

Start (Doppelklick oder):
    python starmoney_gui.py

Entstanden mit Unterstuetzung von Claude (Anthropic).
Lizenz: MIT
"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, ".starmoney_gui_config.json")

# starmoney_export.py muss im selben Ordner liegen.
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


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
    except Exception:
        pass  # Konfiguration ist nur Komfort, kein kritischer Fehler


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
        self.title("StarMoney-Kontoauszuege erstellen")
        self.geometry("720x520")
        self.minsize(600, 420)

        self.log_queue = queue.Queue()
        self.worker_running = False

        cfg = load_config()
        default_dir = cfg.get("export_dir") or os.path.join(SCRIPT_DIR, "export_auszuege")
        self.export_dir = tk.StringVar(value=default_dir)
        self.delete_csv = tk.BooleanVar(value=cfg.get("delete_csv", False))

        self._build_widgets()
        self._refresh_csv_count()
        self.after(100, self._poll_log_queue)

    # ------------------------------------------------------------------
    def _build_widgets(self):
        pad = {"padx": 10, "pady": 6}

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Exportordner:").pack(side="left")
        entry = ttk.Entry(top, textvariable=self.export_dir)
        entry.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(top, text="Ordner waehlen...", command=self._choose_dir).pack(side="left")

        info = ttk.Frame(self)
        info.pack(fill="x", **pad)
        self.count_label = ttk.Label(info, text="")
        self.count_label.pack(side="left")

        opts = ttk.Frame(self)
        opts.pack(fill="x", **pad)
        ttk.Checkbutton(
            opts,
            text="Original-CSV-Dateien nach erfolgreicher Verarbeitung loeschen",
            variable=self.delete_csv,
        ).pack(side="left")

        actions = ttk.Frame(self)
        actions.pack(fill="x", **pad)
        self.run_button = ttk.Button(actions, text="Kontoauszuege erstellen", command=self._start_run)
        self.run_button.pack(side="left")
        self.open_button = ttk.Button(actions, text="Ordner oeffnen", command=self._open_export_dir)
        self.open_button.pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", **pad)

        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True, **pad)
        ttk.Label(log_frame, text="Protokoll:").pack(anchor="w")
        self.log_widget = scrolledtext.ScrolledText(log_frame, height=16, state="disabled", wrap="word")
        self.log_widget.pack(fill="both", expand=True)

        self.export_dir.trace_add("write", lambda *_: self._refresh_csv_count())

    # ------------------------------------------------------------------
    def _choose_dir(self):
        chosen = filedialog.askdirectory(
            title="Exportordner mit den StarMoney-CSV-Dateien waehlen",
            initialdir=self.export_dir.get() if os.path.isdir(self.export_dir.get()) else SCRIPT_DIR,
        )
        if chosen:
            self.export_dir.set(chosen)

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

    def _append_log(self, text):
        self.log_widget.config(state="normal")
        self.log_widget.insert("end", text + "\n")
        self.log_widget.see("end")
        self.log_widget.config(state="disabled")

    # ------------------------------------------------------------------
    def _start_run(self):
        if self.worker_running:
            return
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

        save_config({"export_dir": d, "delete_csv": self.delete_csv.get()})

        self.log_widget.config(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.config(state="disabled")

        self.worker_running = True
        self.run_button.config(state="disabled")
        self.progress.start(12)

        thread = threading.Thread(
            target=self._worker, args=(d, self.delete_csv.get()), daemon=True
        )
        thread.start()

    def _worker(self, export_dir, delete_csv):
        try:
            processed, errors = backend.run_export(
                export_dir,
                delete_csv=delete_csv,
                log=self.log_queue.put,
                log_err=self.log_queue.put,
            )
            self.log_queue.put(("__DONE__", processed, errors))
        except FileNotFoundError:
            self.log_queue.put(f"Verzeichnis nicht gefunden: {export_dir}")
            self.log_queue.put(("__DONE__", 0, 1))
        except Exception as exc:
            self.log_queue.put(f"Unerwarteter Fehler: {exc}")
            self.log_queue.put(("__DONE__", 0, 1))

    def _poll_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple) and item and item[0] == "__DONE__":
                    _, processed, errors = item
                    self._finish_run(processed, errors)
                else:
                    self._append_log(str(item))
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _finish_run(self, processed, errors):
        self.worker_running = False
        self.run_button.config(state="normal")
        self.progress.stop()
        self._refresh_csv_count()
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
