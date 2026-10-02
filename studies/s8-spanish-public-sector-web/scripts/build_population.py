#!/usr/bin/env python3
"""Build the list of entities and the URL to test for each one.

Municipalities: the official register (Registro de Entidades Locales, REL, Ministerio de
Política Territorial) gives the full list with population and region but no website.
Websites come from, in order of precedence:
  1. regional official directories downloaded into data/raw/ (see SOURCES below);
  2. Wikidata P856 (official website) joined on P772 (INE municipality code).
Other entity types (regional governments, provincial councils, public universities,
ministries) come from the curated file data/other_entities.csv.

Output: data/population.csv (one row per entity, with the URL to test or empty).
"""
import csv, json, os, re, sys
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data", "raw")

TOURISM = re.compile(r"turism|tourism|turisme|visit|turismo|bienvenid|guia|fiesta|museo", re.I)
MUNI_HINT = re.compile(r"ayto|ayuntamiento|ajuntament|concello|udala|aiuntamentu|ayunt|"
                       r"\.gob\.es|sede|municipi|^www\.[a-z]", re.I)


def norm_url(u):
    u = (u or "").strip()
    if not u:
        return ""
    if not re.match(r"^https?://", u, re.I):
        u = "http://" + u
    p = urlsplit(u)
    host = (p.hostname or "").lower().strip(".")
    if not host or "." not in host:
        return ""
    path = p.path if p.path not in ("", "/") else "/"
    return f"{p.scheme.lower()}://{host}{path}"


def load_rel():
    import xlrd
    b = xlrd.open_workbook(os.path.join(RAW, "rel_municipios.xls"))
    s = b.sheet_by_index(0)
    hdr = None
    out, seen, dups = [], set(), []
    for i in range(s.nrows):
        row = s.row_values(i)
        if hdr is None:
            if "NUMERO_INSCRIPCION" in row:
                hdr = row
            continue
        d = dict(zip(hdr, row))
        if not d.get("DENOMINACION"):
            continue
        num = str(int(d["NUMERO_INSCRIPCION"])).zfill(8)
        ine = num[2:7]
        if ine in seen:
            # the export lists a few municipalities twice (same inscription number, rows that
            # differ only in the ANOTACION text): keep the first row
            dups.append((ine, d["DENOMINACION"].strip()))
            continue
        seen.add(ine)
        out.append(dict(entity_type="municipality", ine=ine, name=d["DENOMINACION"].strip(),
                        region=d["COMUNIDAD_AUTONOMA"].strip(), province=d["PROVINCIA"].strip(),
                        population=int(d["HABITANTES"] or 0)))
    print(f"REL: {len(out)} municipalities; duplicate rows dropped: {dups}", file=sys.stderr)
    return out


def check_against_ine(munis):
    """Compare with INE, 'Relacion de municipios y codigos por comunidades autonomas y
    provincias a 1 de enero de 2026' (data/raw/ine_diccionario26.xlsx), if downloaded."""
    path = os.path.join(RAW, "ine_diccionario26.xlsx")
    try:
        import openpyxl
    except ImportError:
        print("INE check skipped (openpyxl not installed)", file=sys.stderr)
        return
    if not os.path.exists(path):
        print("INE check skipped (file not downloaded)", file=sys.stderr)
        return
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    codes = set()
    for r in ws.iter_rows(values_only=True):
        if r and r[1] is not None and str(r[1]).strip().isdigit() and r[2] is not None and str(r[2]).strip().isdigit():
            codes.add(str(r[1]).strip().zfill(2) + str(r[2]).strip().zfill(3))
    rel = {m["ine"] for m in munis}
    print(f"INE 2026: {len(codes)} codes; REL {len(rel)}; only in REL {sorted(rel - codes)}; "
          f"only in INE {sorted(codes - rel)}", file=sys.stderr)


def load_wikidata():
    """INE code -> list of (url, rank). Deprecated statements dropped; dissolved items dropped."""
    res = {}
    path = os.path.join(RAW, "wd_ine_web.csv")
    for r in csv.DictReader(open(path, encoding="utf-8")):
        ine = r["ine"].strip()
        if not re.fullmatch(r"\d{5}", ine) or r["dis"] or not r["web"]:
            continue
        if "Deprecated" in r["rank"]:
            continue
        res.setdefault(ine, []).append((r["web"], "Preferred" in r["rank"], r["item"]))
    return res


def pick(cands):
    """Choose one URL among several Wikidata values; return (url, n_candidates, note)."""
    urls = []
    for u, pref, _ in cands:
        n = norm_url(u)
        if n and n not in [x[0] for x in urls]:
            urls.append((n, pref))
    if not urls:
        return "", 0, ""
    def key(x):
        u, pref = x
        host = urlsplit(u).hostname or ""
        return (not pref, bool(TOURISM.search(u)), not MUNI_HINT.search(host), u.count("/"), u)
    urls.sort(key=key)
    note = "tourism_only" if all(TOURISM.search(u) for u, _ in urls) else ""
    return urls[0][0], len(urls), note


def load_regional():
    """Optional regional directories normalised to data/raw/regional_*.csv (ine,url,source)."""
    res = {}
    for fn in sorted(os.listdir(RAW)):
        if fn.startswith("regional_") and fn.endswith(".csv"):
            for r in csv.DictReader(open(os.path.join(RAW, fn), encoding="utf-8")):
                u = norm_url(r.get("url"))
                if u and re.fullmatch(r"\d{5}", r.get("ine", "")):
                    res[r["ine"]] = (u, r.get("source") or fn[9:-4])
    return res


def _key(name, prov):
    import unicodedata
    def n(x):
        x = unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode().lower().strip()
        m = re.match(r"^(.*), (el|la|los|las|l'|el|els|les|o|a|os|as)$", x)
        if m:
            x = m.group(2) + " " + m.group(1)
        return re.sub(r"[^a-z0-9]", "", x)
    return n(name) + "|" + n(prov)


def load_clm(munis):
    """Directorio de Entidades Locales de Castilla-La Mancha (Junta, open data), field WEB.
    Joined on normalised name + province (the file carries no INE code). Only the name,
    province, EATIM flag and WEB columns are used; the file's personal and contact fields are
    read into memory by csv.DictReader with every other column, but never written anywhere."""
    path = os.path.join(RAW, "clm_entidades.csv")
    if not os.path.exists(path):
        return {}
    idx = {}
    for m in munis:
        if m["region"] == "Castilla-La Mancha":
            idx[_key(m["name"], m["province"])] = m["ine"]
    res, unmatched = {}, 0
    rd = csv.DictReader(open(path, encoding="latin-1"), delimiter=";")
    for r in rd:
        if (r.get("EATIM") or "").strip().lower() != "no":
            continue
        k = _key(r["MUNICIPIO"], r["PROVINCIA"])
        ine = idx.get(k)
        if not ine:
            unmatched += 1
            continue
        u = norm_url(r.get("WEB"))
        if u:
            res[ine] = (u, "clm_directorio_entidades_locales")
    print(f"CLM directory: {len(res)} websites joined, {unmatched} rows unmatched", file=sys.stderr)
    return res


def load_overrides():
    path = os.path.join(ROOT, "data", "url_overrides.csv")
    res = {}
    if os.path.exists(path):
        for r in csv.DictReader(open(path, encoding="utf-8")):
            res[r["ine"]] = (norm_url(r["url"]), "override")
    return res


def main():
    munis = load_rel()
    check_against_ine(munis)
    wd = load_wikidata()
    reg = load_regional()
    reg.update(load_clm(munis))
    reg.update(load_overrides())
    rows = []
    for m in munis:
        url, src, ncand, note = "", "", 0, ""
        if m["ine"] in reg:
            url, src = reg[m["ine"]]
        elif m["ine"] in wd:
            url, ncand, note = pick(wd[m["ine"]])
            src = "wikidata_P856" if url else ""
            if note == "tourism_only":
                url, src = "", ""   # a tourism site is not the council's site
        m.update(entity_id="INE" + m["ine"], url=url, url_source=src, wd_candidates=ncand, url_note=note)
        rows.append(m)
    other = os.path.join(ROOT, "data", "other_entities.csv")
    for r in csv.DictReader(open(other, encoding="utf-8")):
        rows.append(dict(entity_id=r["entity_id"], entity_type=r["entity_type"], ine="", name=r["name"],
                         region=r["region"], province=r.get("province", ""), population="",
                         url=norm_url(r["url"]), url_source="curated", wd_candidates=0, url_note=""))
    cols = ["entity_id", "entity_type", "ine", "name", "region", "province", "population",
            "url", "url_source", "wd_candidates", "url_note"]
    with open(os.path.join(ROOT, "data", "population.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    mun = [r for r in rows if r["entity_type"] == "municipality"]
    print(f"municipalities {len(mun)}; with URL {sum(1 for r in mun if r['url'])}; "
          f"other entities {len(rows) - len(mun)}", file=sys.stderr)


if __name__ == "__main__":
    main()
