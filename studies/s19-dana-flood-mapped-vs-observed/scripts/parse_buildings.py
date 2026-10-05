#!/usr/bin/env python3
"""Read the Catastro INSPIRE buildings of each touched municipality, one municipality at a time,
and keep the buildings whose footprint meets any variant of the observed flood extent.

    .venv/bin/python scripts/parse_buildings.py          # -> work/buildings/<INE>.pkl, work/buildings/totals.json

For every kept building we store only what the analysis needs: footprint (EPSG:25830), use,
number of dwellings, construction year, condition, and for each extent variant whether the
footprint intersects it ('fp'), whether its centroid lies inside it ('ct'), and the share of its
footprint inside the primary extent. No cadastral reference, address or identifier is kept.
These files stay in work/ (git-ignored) and are never published. Resumable: municipalities
already parsed are skipped. Run through heavy.sh: the largest municipalities need ~1 GB."""
import csv
import json
import os
import pickle
import sys
import time

import numpy as np
import shapely

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s19lib as L

R = L.R
OUT = os.path.join(R, "work", "buildings")
EXT = os.path.join(R, "work", "extent")


def load_variants():
    v = {}
    for f in sorted(os.listdir(EXT)):
        if f.endswith(".wkb"):
            v[f[:-4]] = shapely.from_wkb(open(os.path.join(EXT, f), "rb").read())
    return v


def main():
    os.makedirs(OUT, exist_ok=True)
    summ = json.load(open(os.path.join(EXT, "extent_summary.json")))
    want = set()
    for v in summ["variants"].values():
        want |= set(v["municipalities"])
    codes = {r["ine_code"]: r for r in csv.DictReader(open(os.path.join(R, "data", "municipality_codes.csv"), encoding="utf-8"))}
    mun = L.load_municipalities()
    variants = load_variants()
    totals_path = os.path.join(OUT, "totals.json")
    totals = json.load(open(totals_path)) if os.path.exists(totals_path) else {}
    for ine in sorted(want):
        dst = os.path.join(OUT, f"{ine}.pkl")
        if os.path.exists(dst) and ine in totals:
            continue
        cat = codes[ine]["catastro_code"]
        zp = os.path.join(R, "data", "raw", "catastro", f"A.ES.SDGC.BU.{cat}.zip")
        if not os.path.exists(zp):
            print("missing", zp, flush=True)
            continue
        t0 = time.time()
        rows = list(L.iter_buildings(L.open_building_gml(zp)))
        geoms = np.array([r["geom"] for r in rows], dtype=object)
        ok = np.array([g is not None for g in geoms])
        tot = {"name": mun[ine][0], "catastro_code": cat, "buildings": int(len(rows)),
               "buildings_with_dwellings": int(sum(r["dwellings"] > 0 for r in rows)),
               "dwellings": int(sum(r["dwellings"] for r in rows)),
               "no_geometry": int((~ok).sum())}
        geoms_ok = geoms[ok]
        idx_ok = np.nonzero(ok)[0]
        tree = shapely.STRtree(geoms_ok)
        cents = shapely.centroid(geoms_ok)
        bbox = shapely.total_bounds(geoms_ok) if len(geoms_ok) else None
        hit = {}
        for name, vg in variants.items():
            if bbox is None:
                hit[name] = set(); continue
            vc = shapely.clip_by_rect(vg, *bbox)
            if shapely.is_empty(vc):
                hit[name] = set(); continue
            shapely.prepare(vc)
            fp = set(tree.query(vc, predicate="intersects").tolist())
            ct = set(np.nonzero(shapely.contains_xy(vc, shapely.get_x(cents), shapely.get_y(cents)))[0].tolist())
            hit[name] = (fp, ct)
        keep = set()
        for name, h in hit.items():
            if h:
                keep |= h[0] | h[1]
        prim = shapely.clip_by_rect(variants["all"], *bbox) if bbox is not None else None
        out = []
        for j in sorted(keep):
            r = rows[idx_ok[j]]
            g = geoms_ok[j]
            rec = {k: r[k] for k in ("use", "dwellings", "units", "year", "condition")}
            rec["wkb"] = shapely.to_wkb(g)
            rec["fp"] = {n: (j in h[0]) if h else False for n, h in hit.items()}
            rec["ct"] = {n: (j in h[1]) if h else False for n, h in hit.items()}
            a = shapely.area(g)
            rec["share_all"] = float(shapely.area(shapely.intersection(g, prim)) / a) if (a > 0 and rec["fp"]["all"]) else 0.0
            out.append(rec)
        pickle.dump(out, open(dst + ".tmp", "wb"))
        os.replace(dst + ".tmp", dst)
        tot["kept"] = len(out)
        totals[ine] = tot
        json.dump(totals, open(totals_path + ".tmp", "w"), indent=1, ensure_ascii=False)
        os.replace(totals_path + ".tmp", totals_path)
        print(ine, tot["name"], tot["buildings"], "kept", len(out), round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    main()
