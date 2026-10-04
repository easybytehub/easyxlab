#!/usr/bin/env python3
"""Illes Balears / Mallorca — Consell de Mallorca register of tourist dwellings (HTV) and stays in
dwellings (ETV, ETVPL, ETV60...) (CAIB open-data CKAN, dataset habitatges-turistics-mallorca, CC BY).
(The sister dataset allotjaments-turistics-mallorca holds hotels etc. and NO tourist dwellings.)
Streams the CSV and keeps only: Signatura, Grup, Subgrup, Tipus de vivenda turística (and ETV sub-types),
Municipi, Estat, "Inici d'activitat". Operator names (Explotador/s), trade name, address are dropped.
    python3 scripts/comparators/mallorca.py [--explore]"""
import csv, io, re, sys, collections, os
from common import polite, norm, ine_lookup, write_min, write_daily, record_source
URL = "https://intranet.caib.es/opendatacataleg/files/dataset/habitatges_turistics_mallorca/habitatges_turistics_mallorca.csv"
KEEP = ["Signatura", "Grup", "Subgrup", "Tipus de vivenda turística", "Municipi", "Estat", "Inici d'activitat",
        "Tipus de vivenda turística ETV", "Tipus de vivenda turística ETV plurifamiliar",
        "Tipus de vivenda turística ETV amb limitació d'us"]


def iso(d):
    d = (d or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", d) or None
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", d)
    return m.group(0) if m else ""


def main():
    r = polite.open_stream(URL)
    lm = r.headers.get("Last-Modified")
    rd = csv.DictReader(io.TextIOWrapper(r, encoding="utf-8-sig", newline=""), delimiter=";")
    ine = ine_lookup()
    rows = []
    for o in rd:
        x = [(o.get(k) or "").strip() for k in KEEP]
        x[6] = iso(x[6]) or ("RAW:" + re.sub(r"\d", "9", x[6]) if x[6] else "")
        x.insert(5, ine.get(("07", norm(x[4])), ""))
        rows.append(x)
    hdr = ["signatura", "grup", "subgrup", "tipus_vivenda", "municipi", "municipality_code", "estat", "inici_activitat",
           "tipus_etv", "tipus_etv_plurifamiliar", "tipus_etv_limitacio_us"]
    if "--explore" in sys.argv:
        print(len(rows), "rows; Last-Modified", lm)
        for i, k in [(1, "grup"), (2, "subgrup"), (3, "tipus"), (6, "estat"), (8, "etv"), (9, "plurif"), (10, "limit")]:
            print(k, collections.Counter(x[i] for x in rows).most_common(15))
        print("sig shapes", collections.Counter(re.sub(r"\d", "9", x[0]) for x in rows).most_common(12))
        print("date shapes", collections.Counter(x[7][:2] if not x[7].startswith("RAW") else x[7] for x in rows).most_common(10))
        print("years", sorted(collections.Counter(x[7][:4] for x in rows).items())[-12:])
        print("2025-03/04 by grup", collections.Counter((x[7][:7], x[1]) for x in rows if x[7][:7] in ("2025-03", "2025-04")))
        print("mun unmatched", collections.Counter(x[4] for x in rows if not x[5]).most_common(10))
        return
    p, n, sha = write_min("mallorca", hdr, rows)
    # tourist dwellings: ETV, ETVPL, ETV60 (stays in dwellings) and VT (habitatge turístic de vacances);
    # CE (comercialitzador d'estades) and EH (empresari d'habitatge) are operators, not dwellings.
    etv = [x for x in rows if not x[1].startswith(("Comercialitzador", "Empresari"))]
    dp, dn = write_daily("mallorca", [(x[7], "07", x[5]) for x in etv if x[7][:4].isdigit()])
    # every row is Estat == "Alta" (no cancelled entries published), so no status file is written.
    record_source("mallorca", url=URL, source_last_modified=lm, rows=n, etv_rows=len(etv), minimal_file=os.path.basename(p),
                  sha256_minimal_file=sha, date_column="Inici d'activitat", licence="Creative Commons Attribution (CAIB CKAN license_id cc-by, dataset habitatges-turistics-mallorca)",
                  types_in_daily=["ETV", "ETVPL", "ETV60", "Habitatge turístic de vacances (VT)"])
    print(p, n, sha, dp, dn)


if __name__ == "__main__":
    main()
