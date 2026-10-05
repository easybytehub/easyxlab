#!/usr/bin/env python3
"""Build the observed flood extent of the DANA of 29 October 2024 from the Copernicus EMS
Rapid Mapping activation EMSR773, in several variants, and find the municipalities of the
province of Valencia that each variant touches.

    .venv/bin/python scripts/build_extent.py     # -> work/extent/*.wkb, work/extent/extent_summary.json

Variants (all restricted to the AOIs in the province of Valencia; see s19lib.NON_VALENCIA_AOIS):
  all            primary: every delivered product, latest version, observedEventA polygons noted
                 'Flooded area' or 'Flood trace', plus the AOI01 'Maximum flood extent' layers
  first          only the first delivery of each AOI (no monitoring products)
  aoi01_first    only AOI01 DEL_PRODUCT v1 (Sentinel-2 / Landsat-8, 30-31 Oct): the scouting pilot
  flooded_only   as 'all' without 'Flood trace' polygons
  earlier_versions  as 'all' with version 1 of the two products re-issued with changes to the
                 delineation or map (AOI03 GRA, AOI02 DEL), where version 1 is still downloadable
  gva_footprint  the Generalitat Valenciana's 'Huella inundación' (ICV), an independent footprint
                 (CC BY-NC-ND 4.0: used for a sensitivity count only, never redistributed)
Buffered versions of 'all' (+/-10 m, +/-25 m) are built for the edge sensitivity.
"""
import glob
import json
import os
import re
import sys
import time

import numpy as np
import pyogrio.raw as raw
import shapely
from pyproj import Transformer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s19lib as L

R = L.R
OUT = os.path.join(R, "work", "extent")
T4326 = Transformer.from_crs(4326, 25830, always_xy=True)


def to25830(geoms):
    return shapely.transform(geoms, lambda xy: np.column_stack(T4326.transform(xy[:, 0], xy[:, 1])))


def read_layer(zip_path, kind):
    import zipfile
    # the layer keeps its own version suffix: a v2 package re-issued only for the map keeps _v1 layers
    names = [n for n in zipfile.ZipFile(zip_path).namelist() if re.search(rf"_{kind}_v\d+\.shp$", n)]
    if not names:
        return []
    meta, _, wkb, fields = raw.read(f"/vsizip/{zip_path}/{names[0]}")
    cols = list(meta["fields"])
    g = to25830(shapely.from_wkb(wkb))
    g = shapely.make_valid(g)
    out = []
    for i in range(len(g)):
        rec = {c: fields[j][i] for j, c in enumerate(cols)}
        out.append((g[i], rec))
    return out


def polys_of(items, notations):
    keep = []
    for g, rec in items:
        if rec.get("event_type") not in (None, "5-Flood"):
            continue
        if notations is not None and rec.get("notation") not in notations:
            continue
        keep.append(g)
    return keep


def municipalities():
    return L.load_municipalities()


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    latest = sorted(glob.glob(os.path.join(R, "data", "raw", "ems", "EMSR773_AOI*.zip")))
    prev = sorted(glob.glob(os.path.join(R, "data", "raw", "ems_prev", "EMSR773_AOI*.zip")))
    layers = {}
    for p in latest + prev:
        info = L.product_name(p)
        if info["aoi"] in L.NON_VALENCIA_AOIS:
            continue
        key = os.path.basename(p)[:-4]
        layers[key] = {"info": info, "obs": read_layer(p, "observedEventA"), "max": read_layer(p, "maximumFloodExtentA")}
        print(key, len(layers[key]["obs"]), len(layers[key]["max"]), flush=True)

    latest_keys = {os.path.basename(p)[:-4] for p in latest}
    prev_keys = {os.path.basename(p)[:-4] for p in prev}

    cache = {}

    def product_union(k, notations, with_max):
        key = (k, tuple(sorted(notations)) if notations else None, with_max)
        if key not in cache:
            gs = polys_of(layers[k]["obs"], notations)
            # 'Maximum flood extent' is cumulative over the AOI01 monitoring series: only the
            # latest monitoring product's layer is needed (MONIT04 contains MONIT01-03)
            if with_max and k == latest_max:
                gs += [g for g, _ in layers[k]["max"]]
            cache[key] = shapely.union_all(np.array(gs, dtype=object)) if gs else shapely.Polygon()
        return cache[key]

    def collect(keys, notations=L.FLOOD_NOTATIONS, with_max=True):
        parts = [product_union(k, notations, with_max) for k in sorted(keys) if k in layers]
        return shapely.union_all(np.array(parts, dtype=object))

    latest_max = max((k for k in latest_keys if k in layers and layers[k]["max"]), key=lambda k: layers[k]["info"]["kind"])
    print("cumulative maximum extent from", latest_max, flush=True)
    replaced = {k.replace("_v1", "_v2") for k in prev_keys}
    variants = {
        "all": collect(latest_keys),
        "first": collect({k for k in latest_keys if layers.get(k, {}).get("info", {}).get("kind") == "PRODUCT"}, with_max=False),
        "aoi01_first": collect({"EMSR773_AOI01_DEL_PRODUCT_v1"}, with_max=False),
        "flooded_only": collect(latest_keys, notations={"Flooded area"}),
        "earlier_versions": collect((latest_keys - replaced) | prev_keys),
    }
    gva = os.path.join(R, "data", "raw", "gva", "DANA2024.ZonasInundadas.HuellaInundacion.gpkg")
    if os.path.exists(gva):
        _, _, wkb, _ = raw.read(gva)
        variants["gva_footprint"] = shapely.union_all(shapely.make_valid(shapely.from_wkb(wkb)))
    for d in (10, 25):
        variants[f"all_plus{d}m"] = shapely.buffer(variants["all"], d, quad_segs=4)
        variants[f"all_minus{d}m"] = shapely.buffer(variants["all"], -d, quad_segs=4)
    print("unions built", round(time.time() - t0), "s", flush=True)

    mun = municipalities()
    prov = shapely.union_all([g for _, g in mun.values()])
    summary = {"products_used": sorted(latest_keys - {k for k in latest_keys if layers.get(k) is None}),
               "products_earlier_versions": sorted(prev_keys), "variants": {}}
    for name, geom in variants.items():
        shapely.prepare(geom)
        with open(os.path.join(OUT, f"{name}.wkb"), "wb") as f:
            f.write(shapely.to_wkb(geom))
        inside = shapely.intersection(geom, prov)
        touched = {}
        for code, (mname, mg) in mun.items():
            if shapely.intersects(geom, mg):
                a = shapely.area(shapely.intersection(geom, mg)) / 1e4
                touched[code] = {"name": mname, "flooded_ha": round(a, 2)}
        summary["variants"][name] = {
            "area_ha": round(shapely.area(geom) / 1e4, 1),
            "area_in_province_ha": round(shapely.area(inside) / 1e4, 1),
            "municipalities_touched": len(touched),
            "municipalities": touched,
        }
        print(name, summary["variants"][name]["area_ha"], summary["variants"][name]["area_in_province_ha"], len(touched), flush=True)
    json.dump(summary, open(os.path.join(OUT, "extent_summary.json"), "w"), indent=1, ensure_ascii=False)
    print("done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
