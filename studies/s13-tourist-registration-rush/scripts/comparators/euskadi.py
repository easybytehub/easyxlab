#!/usr/bin/env python3
"""País Vasco — REATE, "Viviendas y habitaciones de vivienda particular para uso turístico en Euskadi"
(opendata.euskadi.eus, file viviendas.json). The JSON array is read into memory and only
non-personal fields are kept (address, phone, e-mail, name are dropped before anything is written).
INE code = Codigoprovincia (2 digits) + Codigomunicipio (3 digits).
    python3 scripts/comparators/euskadi.py"""
import json, re, collections, os
from common import polite, write_min, write_daily, record_source
URL = "https://opendata.euskadi.eus/contenidos/ds_recursos_turisticos/habitaciones_viviendas_turisti/opendata/viviendas.json"
URL_H = URL.replace("viviendas.json", "habitaciones.json")


def iso(d):
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", (d or "").strip())
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def load(url):
    r = polite.open_stream(url)
    lm = r.headers.get("Last-Modified")
    data = json.loads(r.read().decode("utf-8-sig"))
    return data, lm


def main():
    rows, keys, stats = [], collections.Counter(), collections.Counter()
    lms = {}
    for kind, url in (("vivienda", URL), ("habitacion", URL_H)):
        data, lms[kind] = load(url)
        for o in data:
            keys.update(o.keys())
            cp, cm = (o.get("Codigoprovincia") or "").strip(), (o.get("Codigomunicipio") or "").strip()
            ine5 = cp.zfill(2) + cm.zfill(3) if cp.isdigit() and cm.isdigit() else ""
            rows.append([o.get("Nregistro", ""), kind, o.get("Tipoalojamiento", ""), o.get("Modalidad", ""),
                         o.get("Provincia", ""), cp.zfill(2) if cp else "", o.get("Municipio", ""), ine5,
                         iso(o.get("FechainscripcionREATE"))])
            stats[(kind, o.get("Tipoalojamiento", ""))] += 1
            stats[(kind, "no_date")] += 0 if rows[-1][-1] else 1
    p, n, sha = write_min("euskadi", ["registration_number", "file", "type", "modality", "province", "province_code",
                                      "municipality", "municipality_code", "registration_date"], rows)
    viv = [x for x in rows if x[1] == "vivienda"]
    dp, dn = write_daily("euskadi", [(x[8], x[5], x[7]) for x in viv if x[8]])
    record_source("euskadi", url=URL, url_rooms=URL_H, source_last_modified=lms, rows=n, minimal_file=os.path.basename(p),
                  sha256_minimal_file=sha, date_column="FechainscripcionREATE",
                  types_in_daily=["Vivienda para uso turístico (viviendas.json; rooms in private homes excluded)"],
                  source_keys=sorted(keys), licence="Dataset page: 'Licencia: Información legal' (link to portal legal notice; not followed)")
    print(stats); print(sorted(keys)); print(p, n, sha, dp, dn)


if __name__ == "__main__":
    main()
