#!/usr/bin/env python3
"""Write data/sources.json: every input file under data/raw/ with its size, SHA-256 and the time and
URL of the request that fetched it (from work/fetch_log.jsonl when present), plus the licence
and attribution of each source. Run after the fetch steps.

    python3 scripts/make_sources.py"""
import glob
import hashlib
import json
import os

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCES = {
    "ems": {"name": "Copernicus EMS Rapid Mapping, activation EMSR773 (Flood in Valencia Region, Spain)",
            "url": "https://rapidmapping.emergency.copernicus.eu/EMSR773",
            "licence": "free, full and open access under Regulation (EU) 2021/696 (CEMS On-Demand Mapping terms and conditions)",
            "attribution": "Copernicus Emergency Management Service (© 2024 European Union), EMSR773"},
    "ems_prev": {"name": "Copernicus EMS EMSR773, earlier product versions", "url": "https://rapidmapping.emergency.copernicus.eu/EMSR773",
                 "licence": "as above", "attribution": "Copernicus Emergency Management Service (© 2024 European Union), EMSR773"},
    "catastro": {"name": "Dirección General del Catastro, INSPIRE Buildings (BU), province 46",
                 "url": "https://www.catastro.hacienda.gob.es/INSPIRE/buildings/46/ES.SDGC.bu.atom_46.xml",
                 "licence": "Licencia de acceso y uso de los servicios y conjuntos de datos INSPIRE de la DG del Catastro (v1.0, July 2016); "
                            "feed rights: free of charge 'as long as that the D. G. of the Cadastre (Ministry of Finance) is mentioned as author and owner of the information'",
                 "attribution": "Fuente: Dirección General del Catastro"},
    "patricova": {"name": "PATRICOVA: Peligrosidad por inundación (Generalitat Valenciana, ICV)",
                  "url": "https://dadesobertes.gva.es/es/dataset/patricova-peligrosidad-por-inundacion-plan-de-accion-territorial-de-caracter-sectorial-sobre-pr",
                  "licence": "CC BY 4.0", "attribution": "PATRICOVA: Peligrosidad por Inundación CC BY 4.0, Generalitat"},
    "ign": {"name": "IGN, INSPIRE Administrative Units (municipalities of the province of Valencia)",
            "url": "https://www.ign.es/wfs-inspire/unidades-administrativas", "licence": "CC BY 4.0",
            "attribution": "© Instituto Geográfico Nacional"},
    "gva": {"name": "Generalitat Valenciana, DANA 2024 layers (ICV terramapas 00_DANA2024)",
            "url": "https://terramapas.icv.gva.es/00_DANA2024",
            "licence": "HuellaInundacion: CC BY-NC-ND 4.0 (sensitivity count only, not redistributed); municipal layers: CC BY 4.0",
            "attribution": "Generalitat Valenciana, Institut Cartogràfic Valencià"},
    "snczi": {"name": "SNCZI fluvial hazard maps T10/T100/T500 (MITECO), INSPIRE view service",
              "url": "https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones",
              "licence": "CC BY 4.0 (MITECO open-data catalogue)",
              "attribution": "© Ministerio para la Transición Ecológica y el Reto Demográfico"},
}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    log = {}
    lp = os.path.join(R, "work", "fetch_log.jsonl")
    if os.path.exists(lp):
        for line in open(lp):
            r = json.loads(line)
            log.setdefault(os.path.basename(r["url"].split("?")[0]), r)
    out = {"sources": SOURCES, "files": []}
    for p in sorted(glob.glob(os.path.join(R, "data", "raw", "*", "*"))):
        if p.endswith((".part", ".json")) or ".http" in p:
            continue
        key = os.path.basename(os.path.dirname(p))
        rec = log.get(os.path.basename(p), {})
        out["files"].append({"source": key, "file": os.path.relpath(p, os.path.join(R, "data")),
                             "bytes": os.path.getsize(p), "sha256": sha256(p),
                             "fetched": rec.get("t")})
    tiles = sorted(glob.glob(os.path.join(R, "work", "snczi", "tiles", "*", "*.png")))
    h = hashlib.sha256()
    for t in tiles:
        h.update(os.path.relpath(t, R).encode() + b"\0" + open(t, "rb").read())
    out["snczi_tiles"] = {"count": len(tiles), "sha256_of_all": h.hexdigest(),
                          "fetched": "2026-10-04", "grid": "2,048 m tiles on EPSG:25830, 1,024 px (2 m)"}
    json.dump(out, open(os.path.join(R, "data", "sources.json"), "w"), indent=1, ensure_ascii=False)
    print(len(out["files"]), "files,", len(tiles), "tiles")


if __name__ == "__main__":
    main()
