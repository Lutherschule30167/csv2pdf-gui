# -*- coding: utf-8 -*-
"""Tests für starmoney_export.py (nur anonymisierte Testdaten).

Ausführen: python -m pytest
"""
import json
import os
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import starmoney_export as m  # noqa: E402

HEADER = '"Buchungstag";"Begünstigter";"Betrag";"Saldo";"Verwendungszweck"\n'


def write_csv(path, body, encoding="utf-8"):
    path.write_bytes((HEADER + body).encode(encoding))
    return str(path)


def row_text(segments):
    return "".join(seg[0] for seg in segments)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Jeder Test bekommt eine eigene config.json im Temp-Ordner."""
    cfg = tmp_path / "cfg" / "config.json"
    cfg.parent.mkdir()
    monkeypatch.setattr(m, "config_path", lambda: str(cfg))
    monkeypatch.setattr(m, "user_config_path", lambda: str(tmp_path / "fallback" / "config.json"))
    return cfg


# -- Beträge ------------------------------------------------------------------
@pytest.mark.parametrize("raw, expected", [
    ("-1.234,50", Decimal("-1234.50")),
    ('"12,00"', Decimal("12.00")),
    (" 0,10 ", Decimal("0.10")),
    ("", Decimal(0)),
    ("abc", Decimal(0)),
    ("NaN", Decimal(0)),
])
def test_to_number(raw, expected):
    assert m.to_number(raw) == expected


@pytest.mark.parametrize("value, expected", [
    (Decimal("-1234.5"), "-1.234,50"),
    (Decimal("1234567.891"), "1.234.567,89"),
    (Decimal("-0.00"), "0,00"),
    (Decimal("-0.001"), "0,00"),
    (0, "0,00"),
])
def test_format_amount_de(value, expected):
    assert m.format_amount_de(value) == expected


def test_summary_is_exact_no_minus_zero():
    rows = [["01.03.2026", "A", "-0,10"], ["01.03.2026", "B", "-0,20"], ["01.03.2026", "C", "0,30"]]
    soll, haben, gesamt = m.compute_summary(rows)
    assert (soll, haben, gesamt) == (Decimal("-0.30"), Decimal("0.30"), Decimal("0.00"))
    assert m.format_amount_de(gesamt) == "0,00"
    assert not gesamt < 0
    assert m.count_bookings(rows) == (2, 1)


# -- CSV einlesen -------------------------------------------------------------
def test_semicolon_and_newline_inside_quotes(tmp_path):
    path = write_csv(tmp_path / "a.csv",
                     '"01.03.2026";"Muster; Max";"-5,00";"10,00";"Zeile 1\nZeile 2; mit Semikolon"\n')
    rows = m.read_csv_rows(path)
    assert rows[1] == ["01.03.2026", "Muster; Max", "-5,00", "10,00", "Zeile 1 Zeile 2; mit Semikolon"]


def test_bom_windows1252_and_trailing_blank_lines(tmp_path):
    path = tmp_path / "a.csv"
    path.write_bytes(b"\xef\xbb\xbf" + (HEADER + '"01.03.2026";"Müller";"1,00";"1,00";"x"\r\n\r\n\r\n')
                     .encode("utf-8"))
    rows = m.read_csv_rows(str(path))
    assert rows[0][0] == "Buchungstag" and len(rows) == 2

    path2 = write_csv(tmp_path / "b.csv", '"01.03.2026";"Müller";"1,00";"1,00";"x"\n', "windows-1252")
    assert m.read_csv_rows(path2)[1][1] == "Müller"


# -- Sortierung und Tabelle -----------------------------------------------------
def test_group_and_sort_newest_day_first():
    rows = [["Buchungstag", "Begünstigter", "Betrag"],
            ["1.3.2026", "A", "-1,00"], ["01.03.2026", "B", "2,00"], ["01.03.2026", "C", "1,00"],
            ["02.03.2026", "D", "-5,00"], ["02.03.2026", "E", "-1,00"]]
    names = [r[1] for r in m.group_and_sort(rows)[1:]]
    assert names == ["E", "D", "C", "B", "A"]


def test_large_amounts_are_never_truncated():
    rows = [["Buchungstag", "Begünstigter", "Betrag", "Saldo", "Verwendungszweck"],
            ["01.03.2026", "Max Muster", "-12.345,67", "-123.456,78", "Test"],
            ["01.03.2026", "Erika Beispiel", "0,10", "1,00", "x" * 200]]
    table = m.format_table(rows)
    text = row_text(table[1])
    assert "-12.345,67" in text and "-123.456,78" in text
    widths = {len(row_text(r)) for r in table}
    assert len(widths) == 1 and widths.pop() <= m.MAX_LINE_WIDTH
    # Negative Betrag-/Saldo-Zellen sind markiert, Trenner nie.
    neg = [seg[0].strip() for seg in table[1] if seg[1]]
    assert neg == ["-12.345,67", "-123.456,78"]


def test_long_payee_is_truncated_to_fixed_width():
    rows = [["Buchungstag", "Begünstigter", "Betrag"], ["01.03.2026", "N" * 50, "1,00"]]
    assert "N" * 30 + " |" in row_text(m.format_table(rows)[1])
    assert "N" * 31 not in row_text(m.format_table(rows)[1])


# -- Dateien und Ordner ---------------------------------------------------------
def test_list_csv_files_brackets_and_uppercase(tmp_path):
    d = tmp_path / "Auszüge [2026]"
    d.mkdir()
    for name in ("a.csv", "B.CSV", "notiz.txt"):
        (d / name).write_text("x")
    (d / "ordner.csv").mkdir()
    assert [os.path.basename(p) for p in m.list_csv_files(str(d))] == ["B.CSV", "a.csv"]
    assert m.list_csv_files(str(tmp_path / "fehlt")) == []


def test_run_export_end_to_end(tmp_path):
    d = tmp_path / "export [x]"
    d.mkdir()
    write_csv(d / "Girokonto_Schule_x_20260301_y.csv",
              '"01.03.2026";"Max Muster";"-12.345,67";"-123.456,78";"Test; mit Semikolon"\n')
    logs = []
    assert m.run_export(str(d), log=logs.append, log_err=logs.append) == (1, 0)
    pdf = d / "Girokonto_20260301.pdf"
    assert pdf.read_bytes().startswith(b"%PDF")


@pytest.mark.parametrize("stem, expected", [
    ("Girokonto_Schule_x_20260301_y", ("Girokonto", "01.03.2026")),
    ("Konto_20260301", ("Konto", "01.03.2026")),
])
def test_account_and_date_from_filename(stem, expected):
    assert m.parse_account_and_date(m.shorten_stem(stem)) == expected


# -- Konfiguration -------------------------------------------------------------
def test_broken_config_is_backed_up(isolated_config):
    isolated_config.write_text('{"school_name": "Testschule",}', encoding="utf-8")
    assert m.load_config() == m.DEFAULT_CONFIG
    backup = str(isolated_config) + ".defekt"
    assert open(backup, encoding="utf-8").read() == '{"school_name": "Testschule",}'


def test_wrong_types_are_ignored(isolated_config):
    isolated_config.write_text(json.dumps({
        "school_name": "Testschule",
        "watch_interval_seconds": "dreißig",
        "delete_csv": "ja",
        "footer_links": {"name": "x"},
        "unbekannt": 1,
    }), encoding="utf-8")
    cfg = m.load_config()
    assert cfg["school_name"] == "Testschule"
    for key in ("watch_interval_seconds", "delete_csv", "footer_links"):
        assert cfg[key] == m.DEFAULT_CONFIG[key]
    assert "unbekannt" not in cfg


def test_save_config_roundtrip(isolated_config):
    m.save_config({"school_name": "Testschule", "footer_links": [{"name": "A", "url": "https://a.example"}]})
    m.save_config({"delete_csv": True})
    cfg = m.load_config()
    assert cfg["school_name"] == "Testschule" and cfg["delete_csv"] is True
    assert cfg["footer_links"] == [{"name": "A", "url": "https://a.example"}]
    assert not os.path.exists(str(isolated_config) + ".tmp")
