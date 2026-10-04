#!/usr/bin/env python3
"""Select candidate property-sale notices from the BOE daily summaries.

    python3 scripts/select_notices.py 2025-01-01 2026-09-30 work/candidates_study.csv

Reads data/raw/sumarios/AAAAMMDD.xml.gz, keeps the items of section V (5A, 5B, 5C) whose
title matches the broad sale-of-property filter in `is_candidate` (deliberately wide: the
notice text decides later), and writes one row per item: id, date, section, department,
epigraph, title, url_html. Pure function `is_candidate` is unit-tested.
"""
import csv
import datetime as dt
import gzip
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUM = os.path.join(HERE, "data", "raw", "sumarios")


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


SALE = re.compile(r"\b(subasta|subastas|enajenacion|enajenaciones|enajenar|venta|ventas|"
                  r"adjudicacion directa|segunda licitacion|licitacion publica para la venta)\b")
PROPERTY = re.compile(r"\b(inmueble|inmuebles|finca|fincas|vivienda|viviendas|local|locales|"
                      r"edificio|edificios|edificacion|solar|solares|parcela|parcelas|terreno|"
                      r"terrenos|garaje|garajes|trastero|trasteros|nave|naves|bienes|propiedad|"
                      r"propiedades|patrimonio|piso|pisos|casa|casas|cuartel|acuartelamiento|"
                      r"oficina|oficinas|lote|lotes|urbana|urbanas|rustica|rusticas)\b")
# sellers that announce property sales with terse titles
SELLER = re.compile(r"(tesoreria general de la seguridad social|economia y hacienda|"
                    r"patrimonio del estado|instituto de vivienda, infraestructura y equipamiento de la defensa|"
                    r"invied)")


def is_candidate(title):
    t = fold(title)
    if not SALE.search(t):
        return False
    return bool(PROPERTY.search(t) or SELLER.search(t))


def items(day):
    p = os.path.join(SUM, day + ".xml.gz")
    if not os.path.exists(p):
        return
    root = ET.parse(gzip.open(p)).getroot()
    for sec in root.iter("seccion"):
        code = sec.get("codigo")
        if code not in ("5A", "5B", "5C"):
            continue
        for dep in sec.findall("departamento"):
            for node in dep.iter():
                if node.tag != "epigrafe" and node is not dep:
                    continue
                epi = node.get("nombre") if node.tag == "epigrafe" else ""
                for it in node.findall("item"):
                    yield {
                        "id": it.findtext("identificador"),
                        "date": f"{day[:4]}-{day[4:6]}-{day[6:]}",
                        "section": code,
                        "department": dep.get("nombre"),
                        "epigraph": epi,
                        "title": re.sub(r"\s+", " ", it.findtext("titulo") or "").strip(),
                        "url_html": (it.findtext("url_html") or "").strip(),
                    }


def main(start, end, out):
    d, stop = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    rows, seen, n_items, n_days = [], set(), 0, 0
    while d <= stop:
        day = d.strftime("%Y%m%d")
        any_item = False
        for r in items(day):
            any_item = True
            n_items += 1
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            if is_candidate(r["title"]):
                rows.append(r)
        n_days += any_item
        d += dt.timedelta(days=1)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{n_days} summaries with section V, {n_items} section-V items, {len(rows)} candidates -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
