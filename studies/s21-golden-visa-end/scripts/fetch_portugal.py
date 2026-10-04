#!/usr/bin/env python3
"""Statistics Portugal (INE): transactions of family dwellings by buyer's tax domicile.

Indicators 0012785 (number) and 0012786 (value, thousand euros), quarterly 2009Q1-2026Q2, by NUTS
2024 region; dwelling category = total (H1); buyer's institutional sector = total (T); buyer's
tax domicile = total / national territory / European Union / other countries.

    python3 scripts/fetch_portugal.py          download what is missing (resumable), then build
    python3 scripts/fetch_portugal.py build    only rebuild data/portugal_quarter.csv

Raw JSON goes to data/raw/portugal/ (not published); the aggregate to data/portugal_quarter.csv.
Every request goes through polite.py (User-Agent, robots.txt, <= 1 request/s).
"""
import csv
import json
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, "scripts"))
import polite  # noqa: E402

RAW = os.path.join(R, "data", "raw", "portugal")
IND = {"0012785": "n_transactions", "0012786": "value_keur"}
DOM = {"T": "total", "1": "PT", "2": "EU", "3": "nonEU"}
YEARS = range(2009, 2027)


def chunks():
    qs = [f"S5A{y}{q}" for y in YEARS for q in range(1, 5) if (y, q) <= (2026, 2)]
    for i in range(0, len(qs), 12):
        yield i // 12, qs[i:i + 12]


def fetch():
    os.makedirs(RAW, exist_ok=True)
    for var in IND:
        meta = os.path.join(RAW, f"meta_{var}.json")
        if not os.path.exists(meta):
            polite.fetch(f"https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?varcd={var}&lang=PT", meta)
        for k, qs in chunks():
            out = os.path.join(RAW, f"{var}_{k:02d}.json")
            if os.path.exists(out):
                continue
            url = (f"https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd={var}"
                   f"&Dim1={','.join(qs)}&Dim3=H1&Dim5=T&lang=PT")
            st, _ = polite.fetch(url, out)
            print(var, k, st)


def build():
    rows = {}
    for var, col in IND.items():
        for k, qs in chunks():
            p = os.path.join(RAW, f"{var}_{k:02d}.json")
            d = json.load(open(p, encoding="utf-8"))
            d = d[0] if isinstance(d, list) else d
            for qlabel, vals in d["Dados"].items():
                n, _, _, y = qlabel.split()[:4]
                q = f"{y}Q{n[0]}"
                for v in vals:
                    if v["dim_3"] != "H1" or v["dim_5"] != "T" or v["dim_4"] not in DOM:
                        continue
                    key = (q, v["geocod"], v["geodsg"], DOM[v["dim_4"]])
                    val = v.get("valor")
                    rows.setdefault(key, {})[col] = float(val) if val not in (None, "", "x") else ""
    with open(os.path.join(R, "data", "portugal_quarter.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["quarter", "region_code", "region", "domicile_group", "n_transactions", "value_keur"])
        for key in sorted(rows):
            r = rows[key]
            w.writerow(list(key) + [int(r["n_transactions"]) if r.get("n_transactions") != "" else "",
                                    r.get("value_keur", "")])
    print(f"data/portugal_quarter.csv: {len(rows)} rows")


if __name__ == "__main__":
    if sys.argv[1:] != ["build"]:
        fetch()
    build()
