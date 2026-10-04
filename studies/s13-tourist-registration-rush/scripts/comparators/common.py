"""Shared helpers for the S13 comparator registries (stdlib only). Written by the comparator
survey of 2026-10-04 and moved here from work/comparators/; paths now point to data/raw/."""
import csv, os, re, json, time, hashlib, unicodedata, collections, sys
STUDY = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(STUDY, "scripts"))
import polite  # noqa: E402
COMP = os.path.join(STUDY, "data", "raw", "comparators")      # daily aggregates (git-ignored)
INE_DICT = os.path.join(STUDY, "data", "raw", "ine", "ine_municipios.csv")
RAWDIR = os.path.join(STUDY, "data", "raw", "registries")
TODAY = time.strftime("%Y-%m-%d", time.gmtime())


def norm(s):
    """Upper-case, strip accents and punctuation; move trailing articles ('PUERTO, EL' -> 'EL PUERTO')."""
    s = (s or "").strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    m = re.match(r"^(.*),\s*(EL|LA|LOS|LAS|L'|LES|ELS|O|A|OS|AS|SA|ES|SES|S')$", s)
    if m:
        s = m.group(2) + " " + m.group(1)
    return re.sub(r"[^A-Z0-9]", "", s)


def ine_lookup():
    """{(cpro, normalised name): ine5}; bilingual names 'A/B' are indexed under both halves."""
    d = {}
    for r in csv.DictReader(open(INE_DICT, encoding="utf-8")):
        names = [r["nombre"]] + [x for x in re.split(r"[/]", r["nombre"]) if x.strip()]
        for nm in names:
            d.setdefault((r["cpro"], norm(nm)), r["ine5"])
    for (cpro, alias), canon in ALIASES.items():
        if (cpro, norm(canon)) in d:
            d[(cpro, norm(alias))] = d[(cpro, norm(canon))]
    return d


# registry spelling -> INE spelling (same province)
ALIASES = {("11", "ZAHARA DE LA SIERRA"): "Zahara"}


def write_daily(region, rows, note=""):
    """rows: iterable of (date_iso, province_code, municipality_code). Writes <region>_daily.csv."""
    c = collections.Counter(rows)
    os.makedirs(COMP, exist_ok=True)
    p = os.path.join(COMP, f"{region}_daily.csv")
    with open(p, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "province_code", "municipality_code", "n"])
        for k in sorted(c):
            w.writerow([*k, c[k]])
    return p, sum(c.values())


def write_min(region, header, rows):
    p = os.path.join(RAWDIR, f"{region}_min_{TODAY}.csv")
    os.makedirs(RAWDIR, exist_ok=True)
    with open(p + ".part", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(header); n = 0
        for r in rows:
            w.writerow(r); n += 1
    os.replace(p + ".part", p)
    return p, n, hashlib.sha256(open(p, "rb").read()).hexdigest()


def record_source(region, **kw):
    p = os.path.join(STUDY, "data", "sources.json")
    try:
        meta = json.load(open(p))
    except Exception:
        meta = {}
    kw.setdefault("fetched_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    meta.setdefault("comparators", {})[region] = kw
    json.dump(meta, open(p, "w"), indent=1, ensure_ascii=False)
