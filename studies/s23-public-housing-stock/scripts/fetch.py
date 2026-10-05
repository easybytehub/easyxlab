#!/usr/bin/env python3
"""S23: download every source into data/raw/ (git-ignored). Resumable: a file already on disk is
not fetched again (delete it, or pass --force, to refresh). Every request goes through
polite.py: fixed User-Agent, robots.txt (RFC 9309) read first, <= 1 request/s per host, logged in
work/fetch_log.jsonl.

    python3 scripts/fetch.py [GROUP ...] [--force]      groups: see SOURCES; default: all
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(HERE, "data", "raw")
BOE_API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/{}/{}"

# (group, local path under data/raw, url, accept)
SOURCES = []


def add(group, path, url, accept=None):
    SOURCES.append((group, path, url, accept))


# --- Spanish law in force: consolidated texts (BOE open-data API) ---------------------------
BOE_LAWS = {
    "ley12_2023": "BOE-A-2023-12203",   # Ley 12/2023, por el derecho a la vivienda
    "rd326_2026": "BOE-A-2026-8872",    # Plan Estatal de Vivienda 2026-2030
    "rd42_2022": "BOE-A-2022-802",      # Plan Estatal de acceso a la vivienda 2022-2025
    "rd106_2018": "BOE-A-2018-3358",    # Plan Estatal de Vivienda 2018-2021
    "rd233_2013": "BOE-A-2013-3780",    # Plan Estatal 2013-2016
    "rd2066_2008": "BOE-A-2008-20051",  # Plan Estatal de Vivienda y Rehabilitación 2009-2012
    "rdl26_2026": "BOE-A-2026-20266",   # RDL 26/2026 (modified art. 3 k of Ley 12/2023)
}
for name, ident in BOE_LAWS.items():
    for part in ("texto", "metadatos", "analisis"):
        add("boe", f"boe/{name}_{part}.xml", BOE_API.format(ident, part), "application/xml")
# The resolution that ordered publication of the Congress's non-validation of RDL 26/2026
add("boe", "boe/res_2026_20526.html", "https://www.boe.es/buscar/doc.php?id=BOE-A-2026-20526")


# --- EU texts (Cellar, Publications Office) ------------------------------------------------
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
CELLAR = "http://publications.europa.eu/resource"
EU_CELEX = {
    # Council recommendations to Spain (European Semester), 2019-2026
    "32019H0905(09)": "CSR 2019 Spain", "32020H0826(09)": "CSR 2020 Spain",
    "32022H0901(09)": "CSR 2022 Spain", "32023H0901(09)": "CSR 2023 Spain",
    "32024H06816": "CSR 2024 Spain", "32025H03983": "CSR 2025 Spain", "32026H03922": "CSR 2026 Spain",
    # European Affordable Housing Plan and its staff working document
    "52025DC1025": "European Affordable Housing Plan, COM(2025) 1025",
    "52025SC1053": "SWD(2025) 1053 Understanding the housing crisis",
    # Commission country reports on Spain (European Semester), 2019-2026 (list from
    # data/raw/eu/sparql_country_reports_spain.csv)
    "52019SC1008": "Country Report Spain 2019", "52020SC0508": "Country Report Spain 2020",
    "52022SC0610": "2022 Country Report Spain", "52023SC0609": "2023 Country Report Spain",
    "52024SC0609": "2024 Country Report Spain", "52025SC0209": "2025 Country Report Spain",
    "52026SC0209": "2026 Country Report Spain",
}


def sparql_url(query):
    import urllib.parse
    return SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "text/csv"})


def manifestations(branch_xml):
    """{manifestation type: [item URLs]} from a Cellar branch notice."""
    import re
    s = open(branch_xml, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"<MANIFESTATION\b.*?</MANIFESTATION>", s, flags=re.S):
        b = m.group(0)
        t = re.search(r"<MANIFESTATION_TYPE[^>]*>.*?<VALUE>([^<]*)", b, flags=re.S)
        items = sorted(set(re.findall(r"http://publications\.europa\.eu/resource/cellar/[0-9a-f-]+\.\d+\.\d+/DOC_\d+", b)))
        if t and items:
            for i in items:
                out.setdefault(t.group(1), [])
                if i not in out[t.group(1)]:
                    out[t.group(1)].append(i)
    return out


def get_celex(celex, force=False):
    """Branch notice of a CELEX work (English), then its XHTML items (or PDF if no XHTML)."""
    import urllib.parse
    d = os.path.join(RAW, "eu", celex)
    os.makedirs(d, exist_ok=True)
    br = os.path.join(d, "branch.xml")
    if force or not os.path.exists(br):
        polite.fetch(f"{CELLAR}/celex/{urllib.parse.quote(celex)}", br, "application/xml;notice=branch",
                     extra={"Accept-Language": "eng"})
    if not os.path.exists(br):
        print(celex, "no branch notice", flush=True)
        return
    man = manifestations(br)
    kind = "xhtml" if "xhtml" in man else ("pdf" if "pdf" in man else ("pdfa2a" if "pdfa2a" in man else None))
    if not kind:
        print(celex, "no xhtml/pdf manifestation:", list(man), flush=True)
        return
    for item in man[kind]:
        out = os.path.join(d, item.rsplit("/", 1)[1] + "." + ("pdf" if kind.startswith("pdf") else kind))
        if force or not os.path.exists(out):
            st, _ = polite.fetch(item, out)
            print(st, celex, os.path.basename(out), flush=True)


Q_COUNTRY_REPORTS = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?celex ?date ?title WHERE {
  ?w cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?date .
  ?e cdm:expression_belongs_to_work ?w ; cdm:expression_title ?title ;
     cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> .
  FILTER(?date >= "2019-01-01"^^<http://www.w3.org/2001/XMLSchema#date>)
  FILTER(STRSTARTS(STR(?celex), "52") && CONTAINS(STR(?celex), "SC"))
  FILTER(CONTAINS(LCASE(STR(?title)), "country report") && CONTAINS(LCASE(STR(?title)), "spain"))
} ORDER BY ?date"""


def run_eu(force=False):
    out = os.path.join(RAW, "eu", "sparql_country_reports_spain.csv")
    if force or not os.path.exists(out):
        polite.fetch(sparql_url(Q_COUNTRY_REPORTS), out, "text/csv")
    for celex in EU_CELEX:
        try:
            get_celex(celex, force)
        except Exception as e:
            print("ERROR", celex, type(e).__name__, e, flush=True)


def run(groups, force=False):
    ok = bad = 0
    for g, path, url, acc in SOURCES:
        if groups and g not in groups:
            continue
        out = os.path.join(RAW, path)
        if os.path.exists(out) and not force:
            continue
        try:
            st, final = polite.fetch(url, out, acc)
            print(st, path, flush=True)
            ok += isinstance(st, int) and st < 400
            bad += not (isinstance(st, int) and st < 400)
        except PermissionError as e:
            print("ROBOTS", path, e, flush=True); bad += 1
        except Exception as e:
            print("ERROR", path, type(e).__name__, e, flush=True); bad += 1
    print(f"done: {ok} ok, {bad} failed", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    force = "--force" in a
    a = [x for x in a if x != "--force"]
    groups = set(a) if a and a != ["all"] else set()
    run(groups, force)
    if not groups or "eu" in groups:
        run_eu(force)
