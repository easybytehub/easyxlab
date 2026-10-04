#!/usr/bin/env python3
"""Optional, and not used by the analysis any more: bring in study S11's minimal copy of the GVA registry (fetched 2026-10-03T10:57Z, same URL,
columns signatura, municipality, province, fecha_alta only) as a third dated snapshot, after
checking its SHA-256 against the value S11 recorded. Plazas and the rural flag were not kept by
S11 and stay empty.

    python3 scripts/import_s11_copy.py
"""
import csv, hashlib, json, os, sys
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
S11 = "../s11-str-registration-numbers"
SRC = f"{S11}/data/raw/registries/gva_min.csv"
SHA = "7bfe50771b2eab4cf12e5cc8a1ca66c4f314d60de42fdb4cc89af9d81e386d9b"
PROV = {"ALICANTE/ALACANT": "03", "CASTELLÓN/CASTELLÓ": "12", "VALENCIA/VALÈNCIA": "46"}
OUT = "data/raw/registries/gva_min_2026-10-03.csv"

if not os.path.exists(SRC):
    print(f"{SRC} not found: the S11 copy is optional (it only confirms one day of churn), skipping")
    sys.exit(0)
h = hashlib.sha256(open(SRC, "rb").read()).hexdigest()
if h != SHA:
    print(f"S11 copy changed ({h}): skipping")
    sys.exit(0)
n = 0
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["signatura", "cod_provincia", "cod_municipio", "municipio", "provincia", "fecha_alta", "plazas_totales", "rural"])
    for r in csv.DictReader(open(SRC, encoding="utf-8")):
        w.writerow([r["number"], PROV.get(r["province"], ""), r["municipality_code"], r["municipality"], r["province"], r["date"], "", ""])
        n += 1
meta = json.load(open("data/sources.json"))
meta["gva_snapshots"]["2026-10-03"] = {
    "source": "EasyxLab study S11 copy (dadesobertes.gva.es, same resource URL)",
    "url": json.load(open(f"{S11}/data/sources_registries.json"))["gva"]["url"],
    "fetched_utc": "2026-10-03T10:57:00Z", "rows": n, "sha256_s11_file": SHA,
    "columns_kept": ["signatura", "cod_municipio", "municipio", "provincia", "fecha_alta"]}
json.dump(meta, open("data/sources.json", "w"), indent=1, ensure_ascii=False)
print(OUT, n)
