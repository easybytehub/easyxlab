"""S22 shared code: locked INE tables, a reader for INE's jaxi CSV files, region names.

Every reader works on the files in data/raw/ (git-ignored). `scripts/fetch.py` downloads them
again and checks each SHA-256 against the vintage locked in PROTOCOL.md §3. INE replaces tables in
place when it revises them (the 2024 tables were «revisados y modificados con fecha 17/10/2025»),
so a changed hash is a different vintage, not a download error.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DATA = ROOT / "data"
WORK = ROOT / "work"

UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
INE_CSV = "https://www.ine.es/jaxi/files/tpx/es/csv_bdsc/{}.csv"

LOCKED = ROOT / "scripts" / "locked_inputs.json"  # every input file: local path, URL, SHA-256


def locked_inputs() -> list[dict]:
    import json
    return json.loads(LOCKED.read_text(encoding="utf-8"))


MISSING = {"", "..", ".", "-", "…"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def raw_path(edition: int, table: int) -> Path:
    return RAW / f"ine{edition}" / f"{table}.csv"


def is_decimal_indicator(label: str) -> bool:
    """Indicators INE writes with a decimal comma: shares, ratios, percentages, means per centre."""
    s = label.lower()
    return any(k in s for k in ("%", "ratio", "porcentaje", "tasa", "gasto medio"))


def parse_number(text: str, indicator: str = "") -> tuple[float | None, str]:
    """Parse one INE jaxi cell. Returns (value, flag).

    INE writes counts with a dot for thousands («1.376») and shares with a decimal comma («26,2»).
    Some tables break the rule: 75683 (2024) writes «1,092» for 1,092 dwellings. A count written as
    d{1,3}(,ddd)+ is read as thousands and flagged «comma_thousands». Missing or suppressed cells
    («..», «.», «-», empty) return None with flag «missing».
    """
    t = (text or "").strip().replace(" ", "").replace(" ", "")
    if t in MISSING:
        return None, "missing"
    if is_decimal_indicator(indicator):
        t2 = t.replace(".", "").replace(",", ".") if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", t) \
            else t.replace(",", ".")
        return float(t2), ""
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):
        return float(t.replace(".", "")), ""
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+", t):
        return float(t.replace(",", "")), "comma_thousands"
    if re.fullmatch(r"-?\d+", t):
        return float(t), ""
    if re.fullmatch(r"-?\d+,\d+", t):
        return float(t.replace(",", ".")), "decimal_in_count"
    raise ValueError(f"unparseable INE cell {text!r} (indicator {indicator!r})")


def read_table(edition: int, table: int) -> tuple[list[str], list[dict]]:
    """Read an INE csv_bdsc file. Returns (header, rows); each row maps header -> cell text and
    adds 'value' (float or None) and 'flag'. The value column is the last one («Total»)."""
    p = raw_path(edition, table)
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=";") if any(c.strip() for c in r)]
    header = [h.strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        r = r + [""] * (len(header) - len(r))
        d = {header[i]: r[i].strip() for i in range(len(header))}
        ind = next((d[h] for h in header if "indicador" in h.lower()), d[header[-2]] if len(header) > 1 else "")
        d["value"], d["flag"] = parse_number(r[len(header) - 1], ind)
        out.append(d)
    return header, out


def canon(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]+", " ", s).strip()


REGIONS = {  # canonical key -> English label used in data/
    "andalucia": "Andalucía", "aragon": "Aragón", "asturias principado de": "Asturias",
    "balears illes": "Balearic Islands", "canarias": "Canary Islands", "cantabria": "Cantabria",
    "castilla y leon": "Castilla y León", "castilla la mancha": "Castilla-La Mancha",
    "cataluna": "Catalonia", "comunitat valenciana": "Valencian Community",
    "extremadura": "Extremadura", "galicia": "Galicia", "madrid comunidad de": "Madrid",
    "murcia region de": "Murcia", "navarra comunidad foral de": "Navarre",
    "pais vasco": "Basque Country", "rioja la": "La Rioja", "ceuta": "Ceuta", "melilla": "Melilla",
}


def region(label: str) -> str | None:
    """Map INE's region labels across editions («01 Andalucía», «Andalucía», «Total nacional»)."""
    c = canon(re.sub(r"^\d+\s*", "", label))
    if c in ("total nacional", "total", ""):
        return "Spain"
    return REGIONS.get(c)


SEGMENTS = {  # INE «Especialización del centro» -> short code
    "Especializado en inmigrantes": "IMM",
    "Especializado en mujeres víctimas de violencia de género": "GBV",
    "Sin especialización/Otra especialización": "OTH",
}


def segment(label: str) -> str | None:
    if label.startswith("Total"):
        return "ALL"
    return SEGMENTS.get(label)
