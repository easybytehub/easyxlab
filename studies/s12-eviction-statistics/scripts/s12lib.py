"""S12 shared code: locked inputs, readers for the CGPJ and Ministry files, phase assignment.

Every reader works on the files in data/raw/ (git-ignored; `scripts/fetch.py` downloads them again
and checks their SHA-256 against the vintage locked in PROTOCOL.md §3.3).
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DATA = ROOT / "data"
WORK = ROOT / "work"

UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"

CGPJ_CRISIS = "https://www.poderjudicial.es/stfls/ESTADISTICA/FICHEROS/Crisis/"
CGPJ_POB = "https://www.poderjudicial.es/stfls/ESTADISTICA/FICHEROS/Poblacion/"
PHASE_XLS = ("https://www.administraciondejusticia.gob.es/documents/d/asset-library-5650231/"
             "cambios-lexnet-numo-fase-1-2-y-3-v1-0-1-xls")

# Vintage lock (PROTOCOL.md §3.3). local name -> (url, sha256)
LOCKED = {
    "series_provincias_1T2026_revisado.xlsx": (
        CGPJ_CRISIS + "Series - Efecto de la crisis en los organos judiciales por provincias 1T-2026_revisado.xlsx",
        "065ba5674539dad999dda6e15e93ba0b41884162115c7cfe20e23672c2f8c5a7"),
    "series_tsj_1T2026_revisado.xlsx": (
        CGPJ_CRISIS + "Series - Efecto de la crisis en los organos judiciales por TSJ 1T-2026_revisado.xlsx",
        "6c72240817fc88e2fdef7543c7c708aee57a23707700d175c419d5b4c65a8f05"),
    "lanzamientos_pj_2013_2025.xlsx": (
        CGPJ_CRISIS + "Lanzamientos por PJs_2013_ 2025.xlsx",
        "6d6023a2b5c738ae0ff4360722209e50ac8ea7be971033d480869bca741c7218"),
    "release_2026T1_revisado.xlsx": (
        CGPJ_CRISIS + "Datos sobre el efecto de la crisis en los organos judiciales 1T-2026- con Microempresas_revisado.xlsx",
        "50be1668f168c950a91ce0f41af77b3f69ae97697571797e7fd7dfdc6465658c"),
    "release_2025_anual.xlsx": (
        CGPJ_CRISIS + "Datos sobre el efecto de la crisis en los organos judiciales - Anual 2025.xlsx",
        "c96015b93e36fde0c618c467f5938e3830cbbd8b1c9e03d49c79b012a61a8873"),
    "release_2025T4.xlsx": (
        CGPJ_CRISIS + "Datos sobre el efecto de la crisis en los organos judiciales 4T-2025- con Microempresas.xlsx",
        "8a6e0fe34ab7fca4e549e546edeb8f91c6f97ff4f7fe30ecc8cf95056bbf1470"),
    "release_2025T3.xlsx": (
        CGPJ_CRISIS + "Datos sobre el efecto de la crisis en los organos judiciales 3T-2025- con Microempresas.xlsx",
        "fe520fd7b028b690739ce90c5ceff74c74f11e95ce1d63532b6bdcf44f1ce1fd"),
    "release_2025T2.xlsx": (
        CGPJ_CRISIS + "Datos sobre el efecto de la crisis en los organos judiciales 2T-2025- con Microempresas.xlsx",
        "2d2450efb4119ab4424ed77ba3d22bff0222f4efb9cb8f08c96cd1ca0f96cbfb"),
    "release_2025T1.xlsx": (
        CGPJ_CRISIS + "Datos sobre el efecto de la crisis en los organos judiciales 1T 2025- con Microempresas.xlsx",
        "0c98a475284d988fdcab69abb69750f49394bcf59265e9ef4bf10e9cc6e409eb"),
    "lexnet_numo_fases.xls": (
        PHASE_XLS,
        "12925b64224211b58c343d9e8f79baf7c15f9e4dcda06623df50591a74e76e2b"),
}
# Not in the §3.3 table: the district-to-province table named in §3.2 (logged in PROTOCOL.md §14).
SUPPORT = {
    "poblacion_pj_2025.xlsx": (
        CGPJ_POB + "Población por Partido Judicial- Año 2025.xlsx",
        "665bb817a8c197ab60e20589361555c376180470ccbb8499b371b74aa2101b94"),
}

RELEASES = [  # (quarter, local file, first-vintage note sheet if any)
    ("2025Q1", "release_2025T1.xlsx"),
    ("2025Q2", "release_2025T2.xlsx"),
    ("2025Q3", "release_2025T3.xlsx"),
    ("2025Q4", "release_2025T4.xlsx"),
    ("2026Q1", "release_2026T1_revisado.xlsx"),
]

# Series id -> sheet name in the province series file (names carry the CGPJ's own spacing).
SERIES_SHEETS = {
    "P-TOT": "Lanzamientos pract. Total prov",
    "P-HIP": "Lanzamientos E.hipotecaria prov",
    "P-LAU": "Lanzamientos L.A.U. prov",
    "P-OTR": "Lanzamientos. Otros prov",
    "SC-REC": "Lanzamientos SC recibidos prov ",
    "SC-POS": "Lanzamientos SC c.positivo prov",
    "NC-EH": " Ej.Hipot por provincias",
    "NC-DES": "Despidos presentados Provincia ",
    "PC-MON": "Monitorios por provincias ",
}
TSJ_SHEETS = {
    "P-TOT": "Lanzamientos practic. total TSJ",
    "P-HIP": "Lanzamientos E.hipotecaria TSJ",
    "P-LAU": "Lanzamientos L.A.U  TSJ",
    "P-OTR": "Lanzamientos. Otros TSJ",
    "SC-REC": "Lanzamientos SC recibidos TSJ",
    "SC-POS": "Lanzamientos con Cump ptivo TSJ",
}

PHASE_QUARTER = {1: "2025Q3", 2: "2025Q4", 3: "2026Q1"}


# ----------------------------------------------------------------------------- helpers
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_locked(strict: bool = True) -> dict:
    """Check every locked input against its registered hash."""
    out = {}
    for name, (_, digest) in {**LOCKED, **SUPPORT}.items():
        p = RAW / name
        ok = p.exists() and sha256(p) == digest
        out[name] = ok
        if strict and not ok:
            raise SystemExit(f"locked input missing or changed: {p} (run scripts/fetch.py)")
    return out


def norm(s) -> str:
    """Normalise a place name for matching: no accents, lower case, articles moved, punctuation out."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = s.replace("'", " ").replace("’", " ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    m = re.match(r"^(.*) (el|la|los|las|l|o|a|es|els)$", s)  # "linea de la concepcion, la"
    if m:
        s = f"{m.group(2)} {m.group(1)}"
    return s


ALIASES = {  # normalised variant -> normalised canonical (CGPJ population-table spelling)
    "cangas de narcea": "cangas del narcea",
    "mao mahon": "mahon",
    "mao": "mahon",
    "palma": "palma de mallorca",
    "villarobledo": "villarrobledo",
    "vila real": "villarreal vila real",
}


def canon(name) -> str:
    """Canonical matching key of a district or seat name."""
    n = norm(name)
    return ALIASES.get(n, n)


def q_index(q: str) -> int:
    """'2025Q3' -> integer quarter index."""
    y, k = int(q[:4]), int(q[-1])
    return y * 4 + (k - 1)


def q_label(i: int) -> str:
    return f"{i // 4}Q{i % 4 + 1}"


def q_from_cgpj(label: str) -> str | None:
    """CGPJ column label '26-T1' -> '2026Q1'."""
    m = re.match(r"^\s*(\d{2})-T([1-4])\s*(\(\d+\))?\s*\*?\s*$", str(label))  # '13-T3(1)', '25-T3*'
    if not m:
        return None
    return f"20{m.group(1)}Q{m.group(2)}"


# ----------------------------------------------------------------------------- readers
def _open_xlsx(path: Path):
    import openpyxl
    return openpyxl.load_workbook(path, read_only=True, data_only=True)


def read_series(path: Path, sheet: str, label_col: int = 1) -> dict:
    """Read the first block of a CGPJ series sheet: {unit: {quarter: value}}.

    The header row is the first row whose cells include quarter labels ('13-T1' …); the block runs
    down to the row labelled TOTAL (included). Quarter columns are identified by their labels and
    checked to be consecutive (DQ5).
    """
    wb = _open_xlsx(path)
    rows = list(wb[sheet].iter_rows(values_only=True))
    for hi, r in enumerate(rows):
        qs = [(j, q_from_cgpj(v)) for j, v in enumerate(r) if v is not None and q_from_cgpj(v)]
        if len(qs) >= 4:
            break
    else:
        raise ValueError(f"no quarter header in {path.name}:{sheet}")
    idx = [q_index(q) for _, q in qs]
    if idx != list(range(idx[0], idx[0] + len(idx))):
        raise ValueError(f"non-consecutive quarter labels in {path.name}:{sheet}")
    out = {}
    for r in rows[hi + 1:]:
        name = r[label_col]
        if name is None:
            if out:
                break
            continue
        name = str(name).strip()
        vals = {}
        for j, q in qs:
            v = r[j] if j < len(r) else None
            vals[q] = None if v in (None, "", "-") else float(v)
        out[name] = vals
        if name.upper() == "TOTAL":
            break
    return out


def read_tsj_release_block(path: Path, sheet: str) -> tuple[dict, list]:
    """Quarter block of a TSJ sheet in a quarterly release (all labelled columns; labels can slip, DQ5)."""
    wb = _open_xlsx(path)
    rows = list(wb[sheet].iter_rows(values_only=True))
    for hi, r in enumerate(rows):
        labels = [v for v in r if v is not None and q_from_cgpj(v)]
        if len(labels) >= 5:
            break
    hdr = rows[hi]
    cols = [j for j, v in enumerate(hdr) if v is not None and q_from_cgpj(v)]
    out = {}
    for r in rows[hi + 1:]:
        if r[1] is None:
            if out:
                break
            continue
        out[str(r[1]).strip()] = [None if r[j] is None else float(r[j]) for j in cols]
        if str(r[1]).strip().upper() == "TOTAL":
            break
    return out, [hdr[j] for j in cols]


def read_release_provinces(path: Path) -> dict:
    """'Provincias' sheet of a quarterly release (first vintage of that quarter)."""
    wb = _open_xlsx(path)
    rows = list(wb["Provincias"].iter_rows(values_only=True))
    hdr = None
    for hi, r in enumerate(rows):
        if any(isinstance(v, str) and v.strip().startswith("Total Lanzamientos practicados") for v in r):
            hdr = r
            break
    col = {}
    for j, v in enumerate(hdr):
        if not isinstance(v, str):
            continue
        t = v.strip().rstrip("*").strip()
        if t.startswith("Total Lanzamientos practicados"):
            col["P-TOT"] = j
        elif t.startswith("Lanzamientos derivados EH"):
            col["P-HIP"] = j
        elif t.startswith("Lanzamientos derivados LAU"):
            col["P-LAU"] = j
        elif t.startswith("Resto lanzamientos"):
            col["P-OTR"] = j
        elif t.startswith("Ejecuciones hipotecarias"):
            col["NC-EH"] = j
        elif t.startswith("Demandas despido"):
            col["NC-DES"] = j
        elif t.startswith("Monitorios"):
            col["PC-MON"] = j
    out = {}
    for r in rows[hi + 1:]:
        if r[1] is None:
            if out:
                break
            continue
        out[str(r[1]).strip()] = {k: (None if r[j] is None else float(r[j])) for k, j in col.items()}
        if str(r[1]).strip().upper() == "TOTAL":
            break
    return out


def read_district_file() -> dict:
    """D1: {district (CGPJ spelling): {year: {'tot','hip','lau','otr'}}}."""
    wb = _open_xlsx(RAW / "lanzamientos_pj_2013_2025.xlsx")
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    years = {}
    for hi, r in enumerate(rows):
        ys = [(j, int(v)) for j, v in enumerate(r) if v is not None and re.fullmatch(r"\d{4}", str(v).strip())]
        if len(ys) >= 10:
            years = dict(ys)
            break
    out = {}
    for r in rows[hi + 2:]:
        if r[0] is None:
            continue
        name = str(r[0]).strip()
        if name.upper().startswith("TOTAL"):
            continue
        rec = {}
        for j, y in years.items():
            vals = [r[j + k] for k in range(4)]
            rec[y] = {key: (None if v is None else float(v)) for key, v in zip(("tot", "hip", "lau", "otr"), vals)}
        out[name] = rec
    return out


def read_population_table() -> list[dict]:
    """CGPJ 'Población por partido judicial' 2025: CCAA / province / district rows."""
    wb = _open_xlsx(RAW / "poblacion_pj_2025.xlsx")
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    out, ccaa, prov = [], None, None
    for r in rows[2:]:
        if r[0] and not r[1] and not r[2]:
            ccaa = str(r[0]).strip()
        elif r[1] and not r[2]:
            prov = str(r[1]).strip()
        elif r[2] and str(r[2]).strip().upper() != "TOTAL":
            out.append({"ccaa": ccaa, "province": prov, "district": str(r[2]).strip(),
                        "population_2025": int(r[3]) if r[3] is not None else None})
    return out


def read_phase_xls() -> dict:
    """Ministry xls: {phase: set of (province, seat municipality)} from the former first-instance courts."""
    import xlrd
    wb = xlrd.open_workbook(RAW / "lexnet_numo_fases.xls")
    layouts = {1: (2, 3, 4, 5), 2: (1, 2, 3, 4), 3: (0, 2, 3, 4)}  # sheet, province, municipality, old name
    out = {}
    for phase, (si, pc, mc, oc) in layouts.items():
        sh = wb.sheet_by_index(si)
        seats = set()
        for r in range(1, sh.nrows):
            row = sh.row_values(r)
            old = str(row[oc])
            if re.search(r"INST|1A", old, re.I) and not re.search("paz", old, re.I):
                seats.add((str(row[pc]).strip(), str(row[mc]).strip()))
        out[phase] = seats
    out["sheet_names"] = [wb.sheet_by_index(i).name for i in range(3)]
    return out


def old_court_types(phase: int) -> dict:
    """For DQ6: the set of former court names per seat in sheets 1 and 2."""
    import xlrd
    wb = xlrd.open_workbook(RAW / "lexnet_numo_fases.xls")
    si, pc, mc, oc = {1: (2, 3, 4, 5), 2: (1, 2, 3, 4)}[phase]
    sh = wb.sheet_by_index(si)
    out = {}
    for r in range(1, sh.nrows):
        row = sh.row_values(r)
        old = re.sub(r"\s+", " ", str(row[oc])).strip()
        if not old or re.search("paz", old, re.I):
            continue
        out.setdefault((str(row[pc]).strip(), str(row[mc]).strip()), set()).add(old)
    return out


# Province names: population table / phase xls spelling -> province series spelling.
def province_key(name: str) -> str:
    n = norm(name)
    table = {
        "almeria": "ALMERIA", "cadiz": "CADIZ", "cordoba": "CORDOBA", "granada": "GRANADA",
        "huelva": "HUELVA", "jaen": "JAEN", "malaga": "MALAGA", "sevilla": "SEVILLA",
        "huesca": "HUESCA", "teruel": "TERUEL", "zaragoza": "ZARAGOZA", "asturias": "ASTURIAS",
        "illes balears": "ILLES BALEARS", "islas balears": "ILLES BALEARS", "islas baleares": "ILLES BALEARS", "balears illes": "ILLES BALEARS",
        "baleares": "ILLES BALEARS", "las palmas": "LAS PALMAS", "palmas las": "LAS PALMAS",
        "santa cruz de tenerife": "SANTA CRUZ DE TENERIFE", "cantabria": "CANTABRIA",
        "avila": "AVILA", "burgos": "BURGOS", "leon": "LEON", "palencia": "PALENCIA",
        "salamanca": "SALAMANCA", "segovia": "SEGOVIA", "soria": "SORIA", "valladolid": "VALLADOLID",
        "zamora": "ZAMORA", "albacete": "ALBACETE", "ciudad real": "CIUDAD REAL", "cuenca": "CUENCA",
        "guadalajara": "GUADALAJARA", "toledo": "TOLEDO", "barcelona": "BARCELONA", "girona": "GIRONA",
        "gerona": "GIRONA", "lleida": "LLEIDA", "lerida": "LLEIDA", "tarragona": "TARRAGONA",
        "alicante": "ALICANTE", "alicante alacant": "ALICANTE", "alacant": "ALICANTE",
        "castellon": "CASTELLON", "castellon castello": "CASTELLON", "castello": "CASTELLON",
        "valencia": "VALENCIA", "valencia valencia": "VALENCIA", "badajoz": "BADAJOZ",
        "caceres": "CACERES", "a coruna": "A CORUNA", "coruna a": "A CORUNA", "la coruna": "A CORUNA",
        "lugo": "LUGO", "ourense": "OURENSE", "orense": "OURENSE", "pontevedra": "PONTEVEDRA",
        "madrid": "MADRID", "murcia": "MURCIA", "navarra": "NAVARRA", "araba alava": "ARABA/ALAVA",
        "alava": "ARABA/ALAVA", "araba": "ARABA/ALAVA", "gipuzkoa": "GIPUZKOA", "guipuzcoa": "GIPUZKOA",
        "bizkaia": "BIZKAIA", "vizcaya": "BIZKAIA", "la rioja": "LA RIOJA", "rioja la": "LA RIOJA",
        "ceuta": "CEUTA", "melilla": "MELILLA",
    }
    if n not in table:
        raise KeyError(f"unknown province name: {name!r}")
    return table[n]


def series_province_name(series_names) -> dict:
    """Map our province keys to the exact labels used in the series file (e.g. 'A CORUÑA')."""
    out = {}
    for s in series_names:
        if s.upper() == "TOTAL":
            continue
        out[province_key(s)] = s
    return out


# Ceuta and Melilla are not rows of the province series; where they are counted is checked in DQ1.
CEUTA_MELILLA_HOST = {"CEUTA": "CADIZ", "MELILLA": "MALAGA"}


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for r in rows:
            for k in r:
                if k not in fields:
                    fields.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(r.get(k)) for k in fields})


def _fmt(v):
    if isinstance(v, float):
        if v != v:
            return ""
        return f"{v:.6g}" if abs(v) < 1e6 else f"{v:.0f}"
    return "" if v is None else v


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False, default=_json_default)
        f.write("\n")


def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(type(o))


TSJ_OF_PROVINCE = {
    **{p: "ANDALUCÍA" for p in ("ALMERIA", "CADIZ", "CORDOBA", "GRANADA", "HUELVA", "JAEN", "MALAGA",
                                "SEVILLA", "CEUTA", "MELILLA")},
    **{p: "ARAGÓN" for p in ("HUESCA", "TERUEL", "ZARAGOZA")},
    "ASTURIAS": "ASTURIAS, PRINCIPADO", "ILLES BALEARS": "ILLES BALEARS",
    "LAS PALMAS": "CANARIAS", "SANTA CRUZ DE TENERIFE": "CANARIAS", "CANTABRIA": "CANTABRIA",
    **{p: "CASTILLA Y LEÓN" for p in ("AVILA", "BURGOS", "LEON", "PALENCIA", "SALAMANCA", "SEGOVIA",
                                      "SORIA", "VALLADOLID", "ZAMORA")},
    **{p: "CASTILLA - LA MANCHA" for p in ("ALBACETE", "CIUDAD REAL", "CUENCA", "GUADALAJARA", "TOLEDO")},
    **{p: "CATALUÑA" for p in ("BARCELONA", "GIRONA", "LLEIDA", "TARRAGONA")},
    **{p: "COMUNITAT VALENCIANA" for p in ("ALICANTE", "CASTELLON", "VALENCIA")},
    "BADAJOZ": "EXTREMADURA", "CACERES": "EXTREMADURA",
    **{p: "GALICIA" for p in ("A CORUNA", "LUGO", "OURENSE", "PONTEVEDRA")},
    "MADRID": "MADRID, COMUNIDAD", "MURCIA": "MURCIA, REGIÓN", "NAVARRA": "NAVARRA, COM. FORAL",
    **{p: "PAÍS VASCO" for p in ("ARABA/ALAVA", "GIPUZKOA", "BIZKAIA")},
    "LA RIOJA": "LA RIOJA",
}

# Figures published by the CGPJ for Q1-2026 (note of 22 June 2026, as relayed in its divulgative note
# and the press): practised 4,005 (-45.4%), received 16,167 (+19.2%), positive 7,696 (+16.6%).
PRESS_Q1_2026 = {"P-TOT": (4005, -0.454), "SC-REC": (16167, 0.192), "SC-POS": (7696, 0.166)}


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def wls(y, X, w):
    """Weighted least squares with HC3 standard errors; returns (beta, se, residual df)."""
    import numpy as np
    y, X, w = np.asarray(y, float), np.asarray(X, float), np.asarray(w, float)
    sw = np.sqrt(w)
    Xs, ys = X * sw[:, None], y * sw
    XtX_inv = np.linalg.pinv(Xs.T @ Xs)
    beta = XtX_inv @ Xs.T @ ys
    e = ys - Xs @ beta
    h = np.einsum("ij,jk,ik->i", Xs, XtX_inv, Xs)
    meat = (Xs * (e / np.clip(1 - h, 1e-8, None))[:, None] ** 2).T @ Xs  # HC3
    V = XtX_inv @ meat @ XtX_inv
    return beta, np.sqrt(np.clip(np.diag(V), 0, None)), len(y) - X.shape[1]


