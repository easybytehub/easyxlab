#!/usr/bin/env python3
"""INE municipality dictionary as of 1 January 2026 (diccionario26.xlsx), read with the standard
library (an .xlsx is a zip of XML) into data/raw/ine/ine_municipios.csv: ine5, cpro, cmun, nombre.
Used to give Andalusian registry rows their INE municipality code.

    python3 scripts/comparators/fetch_ine_dictionary.py
"""
import csv, io, os, re, sys, zipfile, xml.etree.ElementTree as ET
from common import polite, INE_DICT, STUDY
URL = "https://www.ine.es/daco/daco42/codmun/diccionario26.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def main():
    tmp = os.path.join(STUDY, "work", "diccionario26.xlsx")
    polite.fetch(URL, tmp)
    z = zipfile.ZipFile(tmp)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = []
    for r in sheet.iter("{%s}row" % NS["m"]):
        vals = {}
        for c in r.findall("m:c", NS):
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            v = c.find("m:v", NS)
            is_ = c.find("m:is", NS)
            if c.get("t") == "s" and v is not None:
                vals[col] = shared[int(v.text)]
            elif is_ is not None:
                vals[col] = "".join(t.text or "" for t in is_.iter("{%s}t" % NS["m"]))
            elif v is not None:
                vals[col] = v.text
        rows.append(vals)
    hdr = next(i for i, r in enumerate(rows) if [x.upper() for x in r.values()][:2] == ["CODAUTO", "CPRO"])
    cols = {v.upper(): k for k, v in rows[hdr].items()}
    os.makedirs(os.path.dirname(INE_DICT), exist_ok=True)
    with open(INE_DICT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ine5", "cpro", "cmun", "nombre"])
        for r in rows[hdr + 1:]:
            cpro, cmun, nom = r.get(cols["CPRO"], ""), r.get(cols["CMUN"], ""), r.get(cols["NOMBRE"], "")
            if cpro and cmun:
                w.writerow([cpro.zfill(2) + cmun.zfill(3), cpro.zfill(2), cmun.zfill(3), nom])
    os.remove(tmp)
    print(INE_DICT)


if __name__ == "__main__":
    main()
