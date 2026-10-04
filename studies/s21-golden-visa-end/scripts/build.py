#!/usr/bin/env python3
"""Turn the MIVAU workbooks in data/raw/ into the aggregate tables in data/.

Inputs (downloaded by scripts/fetch.py):
- data/raw/fx/ecb_EXR_Q.*.EUR.SP00.A.csv  ECB reference rates, quarterly
- data/raw/mivau/340101d0.XLS  table 1.6, transactions by buyer residence, one sheet per quarter
- data/raw/mivau/340101l0.XLS  table 1.7, free-market transactions by value band, one quarter
- data/raw/mivau/34010120.XLS  table 1.1, free-market transactions
- data/raw/mivau/34020110.XLS  table 3.1, value of free-market transactions (thousand euros)
- data/raw/wayback/*.XLS       Internet Archive copies of tables 1.6 and 1.7 (earlier vintages)

Outputs (aggregates of public tables only):
- data/province_quarter.csv    52 provinces + Spain x 2007Q1-2026Q2 x buyer group
- data/vintages.csv            the same counts in each archived vintage, for the revision check
- data/value_bands.csv         free-market transactions by value band, Q1 of 2021, 2022, 2025, 2026
- data/value_quarter.csv       free-market transactions and their value, by province and quarter
- data/fx_quarter.csv          ECB reference rates, quarterly averages (USD, GBP, CNY per euro)
Requires xlrd (requirements.txt)."""
import csv
import glob
import json
import os
import sys

import xlrd

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, "scripts"))
from s21lib import GROUPS, CODE_LABEL, province_code, sheet_quarter, qid  # noqa: E402

RAW = os.path.join(R, "data", "raw")
OUT = os.path.join(R, "data")


def num(v):
    if isinstance(v, float):
        return v
    s = str(v).strip().replace(".", "").replace(",", ".")
    if s in ("", "-", "—"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def parse_16(path):
    """{(quarter, code): {group: count}, ...}, plus set of provisional quarters."""
    b = xlrd.open_workbook(path)
    out, prov = {}, set()
    for i in range(b.nsheets):
        s = b.sheet_by_index(i)
        q = sheet_quarter(b.sheet_names()[i])
        hdr = None
        for r in range(s.nrows):
            v1 = str(s.cell_value(r, 1))
            if "(**)" in v1 and "trimestre" in v1.lower():
                prov.add(q)
            if str(s.cell_value(r, 3)).strip() == "TOTAL":
                hdr = r
                break
        assert hdr is not None, (path, q)
        sub = [str(s.cell_value(hdr + 1, c)).strip() for c in range(s.ncols)]
        assert sub[4:12] == ["Total", "Españoles", "Extranjeros", "No consta"] * 2, sub
        for r in range(hdr + 2, s.nrows):
            name = str(s.cell_value(r, 1)).strip()
            if not name or not isinstance(s.cell_value(r, 3), float):
                continue
            code = "00" if name.upper() == "TOTAL NACIONAL" else province_code(name)
            if code is None:
                continue
            vals = [num(s.cell_value(r, c)) for c in range(3, 13)]
            out[(q, code)] = dict(zip(GROUPS, vals))
    return out, prov


def check_identities(d):
    bad = []
    for (q, c), v in d.items():
        if abs(v["res_total"] - (v["res_es"] + v["res_fx"] + v["res_nc"])) > 0.5:
            bad.append((q, c, "res"))
        if abs(v["nres_total"] - (v["nres_es"] + v["nres_fx"] + v["nres_nc"])) > 0.5:
            bad.append((q, c, "nres"))
        if abs(v["total"] - (v["res_total"] + v["nres_total"] + v["nc"])) > 0.5:
            bad.append((q, c, "total"))
    # provinces add up to Spain
    qs = sorted({q for q, _ in d})
    for q in qs:
        for g in GROUPS:
            s = sum(d[(q, c)][g] for c in CODE_LABEL if (q, c) in d)
            if abs(s - d[(q, "00")][g]) > 0.5:
                bad.append((q, "sum", g, s, d[(q, "00")][g]))
    return bad


BANDS = ["0-150k", "150-300k", "300-450k", "450-600k", "600-750k", "750-900k", "900-1050k", "over-1050k"]


def parse_17(path):
    """{code: {band: count, 'total': n}} for the 'Total' surface row of each territory sheet."""
    b = xlrd.open_workbook(path)
    out, label = {}, None
    for i in range(b.nsheets):
        s = b.sheet_by_index(i)
        name = b.sheet_names()[i]
        code = "00" if name.strip() == "España" else province_code(name)
        hdr = None
        for r in range(s.nrows):
            v1 = str(s.cell_value(r, 1))
            if label is None and "trimestre de" in v1.lower():
                label = v1.strip()
            if "(0-150.000)" in [str(s.cell_value(r, c)).strip() for c in range(s.ncols)]:
                hdr = r
                break
        if code is None or hdr is None:
            continue
        cols = [str(s.cell_value(hdr, c)).strip() for c in range(s.ncols)]
        c0 = cols.index("(0-150.000)")
        for r in range(hdr + 1, s.nrows):
            if str(s.cell_value(r, 1)).strip().lower().startswith("total"):
                vals = [num(s.cell_value(r, c)) for c in range(c0, c0 + 9)]
                out[code] = dict(zip(BANDS + ["total"], vals))
                break
    words = {"Primer": 1, "Segundo": 2, "Tercer": 3, "Cuarto": 4}
    w, _, _, y = label.split()[:4]
    return qid(int(y), words[w]), out


def parse_year_quarter_table(path):
    """Tables 1.1 / 3.1: sheets of several years, columns 1º..4º per year. {(q, code): value}."""
    b = xlrd.open_workbook(path)
    out = {}
    for i in range(b.nsheets):
        s = b.sheet_by_index(i)
        yr_row = qrow = None
        for r in range(s.nrows):
            if any(str(s.cell_value(r, c)).strip().startswith("Año ") for c in range(s.ncols)):
                yr_row = r
            if str(s.cell_value(r, 2)).strip().startswith("1º"):
                qrow = r
                break
        years, cur = [], None
        for c in range(s.ncols):
            v = str(s.cell_value(yr_row, c)).strip()
            if v.startswith("Año "):
                cur = int(v.split()[1])
            years.append(cur)
        for r in range(qrow + 1, s.nrows):
            name = str(s.cell_value(r, 1)).strip()
            code = "00" if name.upper() == "TOTAL NACIONAL" else province_code(name)
            if code is None:
                continue
            for c in range(2, s.ncols):
                qv = str(s.cell_value(qrow, c)).strip()
                if not qv or years[c] is None:
                    continue
                v = s.cell_value(r, c)
                if isinstance(v, float):
                    out[(qid(years[c], int(qv[0])), code)] = v
    return out


def build_fx():
    """data/raw/fx/ecb_EXR_Q.<CUR>.EUR.SP00.A.csv (ECB Data Portal, csvdata) -> data/fx_quarter.csv."""
    rows = []
    for p in sorted(glob.glob(os.path.join(RAW, "fx", "ecb_EXR_Q.*.EUR.SP00.A.csv"))):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            if r["OBS_VALUE"]:
                y, q = r["TIME_PERIOD"].split("-Q")
                rows.append([qid(int(y), int(q)), r["CURRENCY"], float(r["OBS_VALUE"]), r["KEY"]])
    with open(os.path.join(OUT, "fx_quarter.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["quarter", "currency", "eur_rate", "ecb_series"])
        for r in sorted(rows):
            w.writerow([r[0], r[1], round(r[2], 6), r[3]])
    return len(rows)


def sha(path):
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    cur, prov = parse_16(os.path.join(RAW, "mivau", "340101d0.XLS"))
    bad = check_identities(cur)
    # The live workbook is internally consistent; anything else is reported, not hidden.
    with open(os.path.join(OUT, "province_quarter.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["quarter", "code", "province"] + GROUPS + ["provisional"])
        for (q, c) in sorted(cur, key=lambda k: (k[0], k[1])):
            w.writerow([q, c, "Spain" if c == "00" else CODE_LABEL[c]] +
                       [int(cur[(q, c)][g]) for g in GROUPS] + [1 if q in prov else 0])
    # vintages
    vint = {"2026-10-01": cur}
    for p in sorted(glob.glob(os.path.join(RAW, "wayback", "340101d0_*.XLS"))):
        ts = os.path.basename(p).split("_")[1][:8]
        vint[f"{ts[:4]}-{ts[4:6]}-{ts[6:]}"] = parse_16(p)[0]
    with open(os.path.join(OUT, "vintages.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["vintage", "quarter", "code", "total", "nres_fx", "res_fx", "nres_es", "res_es"])
        for v, d in sorted(vint.items()):
            for (q, c) in sorted(d):
                if q >= "2021Q1":
                    w.writerow([v, q, c] + [int(d[(q, c)][g]) for g in
                                            ("total", "nres_fx", "res_fx", "nres_es", "res_es")])
    # value bands
    bands = {}
    srcs = [os.path.join(RAW, "mivau", "340101l0.XLS")] + sorted(glob.glob(os.path.join(RAW, "wayback", "340101l0_*.XLS")))
    for p in srcs:
        q, d = parse_17(p)
        if q in bands:
            if bands[q][1] != d:
                print(f"note: two different copies of table 1.7 for {q}; keeping {bands[q][0]}")
            continue
        bands[q] = (os.path.basename(p), d)
    with open(os.path.join(OUT, "value_bands.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["quarter", "source_file", "code", "province"] + BANDS + ["total"])
        for q in sorted(bands):
            src, d = bands[q]
            for c in sorted(d):
                w.writerow([q, src, c, "Spain" if c == "00" else CODE_LABEL[c]] +
                           [int(d[c][k]) for k in BANDS + ["total"]])
    # counts and values of free-market transactions
    n11 = parse_year_quarter_table(os.path.join(RAW, "mivau", "34010120.XLS"))
    v31 = parse_year_quarter_table(os.path.join(RAW, "mivau", "34020110.XLS"))
    with open(os.path.join(OUT, "value_quarter.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["quarter", "code", "province", "free_market_n", "free_market_value_keur", "mean_value_eur"])
        for k in sorted(set(n11) & set(v31)):
            q, c = k
            n, v = n11[k], v31[k]
            w.writerow([q, c, "Spain" if c == "00" else CODE_LABEL[c], int(n), round(v, 1),
                        round(1000 * v / n, 1) if n else ""])
    srcinfo = {
        "fetched": "2026-10-04",
        "mivau_last_modified": "Thu, 01 Oct 2026 06:48:35 GMT (table 1.6), 06:48:38 GMT (table 1.7)",
        "files": {os.path.relpath(p, R): sha(p) for p in sorted(glob.glob(os.path.join(RAW, "*", "*.XLS")))},
        "identity_failures_live_table_1_6": len(bad),
        "provisional_quarters": sorted(prov),
        "value_band_quarters": {q: bands[q][0] for q in sorted(bands)},
    }
    old = {}
    sp = os.path.join(OUT, "sources.json")
    if os.path.exists(sp):
        old = json.load(open(sp))
    old.update({"mivau": srcinfo})
    json.dump(old, open(sp, "w"), indent=1, ensure_ascii=False)
    print(f"fx: {build_fx()} currency-quarters")
    print(f"table 1.6: {len(cur)} province-quarter rows, {len(bad)} identity failures, provisional {sorted(prov)}")
    for b in bad[:10]:
        print("  ", b)
    print(f"table 1.7 quarters: {sorted(bands)}")
    print(f"vintages: {sorted(vint)}")


if __name__ == "__main__":
    main()
