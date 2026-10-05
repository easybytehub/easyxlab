#!/usr/bin/env python3
"""S23: search the national open-data catalogue (datos.gob.es linked-data API, /apidata/ is
allowed by its robots.txt) for public/social housing stock datasets, and for anything that could
be the art. 32 inventory or annual report of Ley 12/2023. Writes data/catalogue_search.csv
(query, hits, dataset title, publisher, URL). Raw JSON in data/raw/catalogues/ (git-ignored).
Resumable: an existing raw file is reused."""
import csv, json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite
from s23lib import RAW, DATA

TERMS = ["vivienda social", "viviendas sociales", "parque público", "parque de vivienda", "vivienda pública",
         "viviendas públicas", "parque público de vivienda", "inventario", "alquiler social", "vivienda protegida",
         "viviendas protegidas", "Agencia de Vivienda Social", "parc públic", "habitatge", "habitatges",
         "Alokabide", "etxebizitza", "vivienda en alquiler", "viviendas de titularidad pública", "mapa de la vivienda"]
API = "https://datos.gob.es/apidata/catalog/dataset/title/{}.json?_pageSize=200&_page={}"


def first(v):
    if isinstance(v, list):
        for x in v:
            if isinstance(x, dict) and x.get("_lang") == "es":
                return x.get("_value", "")
        v = v[0] if v else ""
    if isinstance(v, dict):
        return v.get("_value", "")
    return v or ""


def search(term):
    items, page = [], 0
    while True:
        out = os.path.join(RAW, "catalogues", f"datosgob_{term.replace(' ', '_')}_{page}.json")
        if not os.path.exists(out):
            st, _ = polite.fetch(API.format(urllib.parse.quote(term), page), out, "application/json")
            if st != 200:
                return items, st
        d = json.load(open(out, encoding="utf-8"))["result"]
        items += d.get("items", [])
        if len(d.get("items", [])) < 200 or page >= 4:
            return items, 200
        page += 1


def main():
    rows = []
    for t in TERMS:
        items, st = search(t)
        for it in items:
            rows.append({"query": t, "status": st, "title": first(it.get("title")),
                         "publisher": it.get("publisher", ""), "modified": first(it.get("modified")),
                         "url": it.get("_about", "")})
        if not items:
            rows.append({"query": t, "status": st, "title": "", "publisher": "", "modified": "", "url": ""})
        print(t, st, len(items), flush=True)
    with open(os.path.join(DATA, "catalogue_search.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
