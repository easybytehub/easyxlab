#!/usr/bin/env python3
"""Download the GVA's frozen "historical" list of tourist dwellings (dataset
dades-turisme-habitatges-comunitat-valenciana-2025, CC BY), which unlike tur-gestur-vt keeps
cancelled entries with their status and cancellation date, and the "last period" list of the
same dataset. Only non-personal columns are kept; name, address parts, building, web are
dropped while streaming. Two booleans are derived from floor and door first.

Output (git-ignored): data/raw/registries/gvahist_<label>.csv
    python3 scripts/fetch_gva_hist.py
"""
import csv, io, json, os, re, sys, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import polite

BASE = "https://dadesobertes.gva.es/dataset/8a1c4fa3-4696-4b3b-8a1a-6bff038abf0c/resource/"
FILES = {"historico": BASE + "9f3d18dc-3150-4075-8dd4-4f96d5dd1868/download/listaviviendas_19600101.csv",
         "ultimo": BASE + "2c1e8aa4-5238-47c4-9404-f574ee1269a4/download/listaviviendas_20250126.csv"}
KEEP = ["Signatura", "Cod. Estado", "Estado", "Cod.Tipo", "Tipo", "Cod. Provincia", "Cod. Municipio",
        "Municipio", "Cod. Situacion", "Plazas", "Fecha alta", "Fecha baja"]
OUT = ["signatura", "cod_estado", "estado", "cod_tipo", "tipo", "cod_provincia", "cod_municipio", "municipio",
       "cod_situacion", "plazas", "fecha_alta", "fecha_baja", "has_floor", "has_door"]


def iso(d):
    m = re.match(r"\s*(\d{2})/(\d{2})/(\d{4})", d or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def main():
    os.makedirs("data/raw/registries", exist_ok=True)
    meta = json.load(open("data/sources.json")) if os.path.exists("data/sources.json") else {}
    for label, url in FILES.items():
        t = time.gmtime()
        out = f"data/raw/registries/gvahist_{label}.csv"
        resp = polite.open_stream(url)
        rd = csv.DictReader(io.TextIOWrapper(resp, encoding="latin1", newline=""), delimiter=";")
        cols = rd.fieldnames
        n = 0
        with open(out + ".part", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(OUT)
            for r in rd:
                w.writerow([r["Signatura"].strip(), r["Cod. Estado"].strip(), r["Estado"].strip(),
                            r["Cod.Tipo"].strip(), r["Tipo"].strip(), r["Cod. Provincia"].strip(),
                            r["Cod. Municipio"].strip(), r["Municipio"].strip(), r["Cod. Situacion"].strip(),
                            r["Plazas"].strip(), iso(r["Fecha alta"]), iso(r["Fecha baja"]),
                            int(bool((r.get("Piso") or "").strip())), int(bool((r.get("Puerta") or "").strip()))])
                n += 1
        os.replace(out + ".part", out)
        meta.setdefault("gva_historical", {})[label] = {
            "url": url, "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", t), "rows": n,
            "source_columns": cols, "columns_kept": KEEP, "columns_derived": ["has_floor", "has_door"],
            "sha256_minimal_file": hashlib.sha256(open(out, "rb").read()).hexdigest(),
            "licence": "Creative Commons Attribution (dataset page), dadesobertes.gva.es"}
        print(out, n)
    json.dump(meta, open("data/sources.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
