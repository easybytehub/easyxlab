#!/usr/bin/env python3
"""Andalucía — Registro de Turismo de Andalucía (OpenRTA), pipe-delimited export.

Repair rule. The header has 72 names but most rows (VUT/VTAR) carry 92 fields: 20 unnamed fields sit
before `municipalities`, so every named column from `municipalities` onward is RIGHT-ANCHORED
(index = len(row) - (72 - header_index)); the left-anchored reading puts the code in
`tourism_office_ownership` and the date in `url`. A few rows have extra '|' inside quoted text
(address, name) and are off by one or two more; for those we anchor on the field that matches the
registration-code pattern (XXX/PP/digits) followed by an 8-digit date, and read type/province at fixed
offsets from it; the municipality is the nearest (text, numeric id) pair 18-20 fields to its left.
Personal columns (holder, e-mail, phone, address, name, cadastral ref, url) are never written.

    python3 scripts/comparators/andalucia.py
"""
import re, collections, csv, os
from common import polite, norm, ine_lookup, write_min, write_daily, record_source, TODAY, COMP
URL = "https://datos.juntadeandalucia.es/api/v0/openrta/all?format=csv"
PROV = {"ALMERIA": "04", "CADIZ": "11", "CORDOBA": "14", "GRANADA": "18", "HUELVA": "21", "JAEN": "23",
        "MALAGA": "29", "SEVILLA": "41"}
code_re = re.compile(r"^[A-Z]{1,6}/[A-Z]{2}/\d{3,}$")
d8 = re.compile(r"^(19|20)\d{6}$")
num = re.compile(r"^\d+(\.0)?$")


def iso(s):
    s = s.strip()
    return f"{s[:4]}-{s[4:6]}-{s[6:]}" if d8.match(s) else ""


def main():
    ine = ine_lookup()
    r = polite.open_stream(URL)
    lastmod = r.headers.get("Last-Modified")
    hdr = r.readline().decode("utf-8-sig").rstrip("\r\n").split("|")
    N = len(hdr); H = {h: i for i, h in enumerate(hdr)}
    off_code = N - H["registration_code"]          # 23
    stats = collections.Counter(); rows = []
    for raw in r:
        f = raw.decode("utf-8", "replace").rstrip("\r\n").split("|")
        stats["lines"] += 1
        a = len(f) - off_code
        if 0 <= a < len(f) - 1 and code_re.match(f[a].strip()) and d8.match(f[a + 1].strip()):
            how = "aligned" if len(f) == N else f"right-anchored+{len(f) - N}"
        else:
            cands = [i for i in range(20, len(f) - 1) if code_re.match(f[i].strip()) and d8.match(f[i + 1].strip())]
            if not cands:
                stats["no_code_or_date"] += 1
                stats[("no_code_type_rightanchored", f[len(f) - (N - H["objects_type_id"])].strip()[:40])] += 1
                continue
            a = cands[-1]; how = "code-anchored"
        typ = f[a - 9].strip()
        prov = f[a - 2].strip()
        mun, how_m = "", ""
        for k in (a - 18, a - 19, a - 20, a - 17):
            if k + 1 < len(f) and num.match(f[k + 1].strip()) and f[k].strip() and not num.match(f[k].strip()):
                mun = f[k].strip(); break
        cpro = PROV.get(norm(prov), "")
        ine5 = ine.get((cpro, norm(mun)), "") if cpro else ""
        stats[("how", how)] += 1
        rows.append([f[a].strip(), typ, prov, cpro, mun, ine5, iso(f[a + 1]), iso(f[1]), how])
    vut = [x for x in rows if x[1] == "Vivienda de uso turístico"]
    stats["rows_with_code"] = len(rows); stats["vut"] = len(vut)
    stats["vut_mun_matched"] = sum(1 for x in vut if x[5])
    stats["vut_reg_eq_start"] = sum(1 for x in vut if x[6] == x[7])
    stats["vut_codes_by_prefix"] = dict(collections.Counter(x[0].split("/")[0] for x in vut))
    unmatched = collections.Counter((x[3], x[4]) for x in vut if not x[5])
    p, n, sha = write_min("andalucia", ["registration_code", "type", "province", "province_code", "municipality",
                                        "municipality_code", "registration_date", "activity_start_date", "repair"], rows)
    dp, dn = write_daily("andalucia", [(x[6], x[3], x[5]) for x in vut if x[6]])
    record_source("andalucia", url=URL, source_last_modified=lastmod, rows=n, vut_rows=len(vut), minimal_file=os.path.basename(p),
                  sha256_minimal_file=sha, licence="Reconocimiento 4.0 Internacional (CC BY 4.0) (CKAN dataset 'openrta', juntadeandalucia.es/datosabiertos)",
                  types_in_daily=["Vivienda de uso turístico (object_type_id 46; codes VUT/.. and legacy VFT/..)"],
                  date_column="registration_date", repair_stats={str(k): v for k, v in stats.items()})
    for k, v in stats.items():
        print(k, v)
    print("unmatched municipality names (top):", unmatched.most_common(15))
    print(p, n, sha, dp, dn)


if __name__ == "__main__":
    main()
