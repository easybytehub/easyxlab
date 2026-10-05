#!/usr/bin/env python3
"""Flag every kept building (work/buildings/<INE>.pkl) against the official flood maps:
SNCZI fluvial hazard zones T10, T100, T500 (raster masks from scripts/fetch_snczi.py) and
PATRICOVA hazard levels 1-6 and geomorphological hazard (data/raw/patricova/).

    .venv/bin/python scripts/classify.py      # -> work/flags/<INE>.pkl (one dict per kept building)

Two rules, as for the extent:
  fp  the footprint meets the zone: for SNCZI, at least one 2 m pixel centre inside the footprint
      is in the zone (the building's representative point when no pixel centre falls inside it);
      for PATRICOVA, the footprint intersects a zone polygon;
  ct  the footprint's centroid lies in the zone.
Resumable per municipality. Row-level output stays in work/ and is never published."""
import glob
import os
import pickle
import sys
import zipfile
from functools import lru_cache

import numpy as np
import pyogrio.raw as raw
import shapely
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s19lib as L

R = L.R
TILES = os.path.join(R, "work", "snczi", "tiles")
OUT = os.path.join(R, "work", "flags")
LAYERS = {"t10": "NZ.Flood.FluvialT10", "t100": "NZ.Flood.FluvialT100", "t500": "NZ.Flood.FluvialT500"}
TILE, PXM, PX_N = 2048, 2.0, 1024
MISSING = set()


PARENT = {"NZ.Flood.FluvialT100": "NZ.Flood.FluvialT500", "NZ.Flood.FluvialT10": "NZ.Flood.FluvialT100"}


@lru_cache(maxsize=160)
def mask(layer, x0, y0):
    p = os.path.join(TILES, layer, f"{x0}_{y0}.png")
    if not os.path.exists(p):
        # not fetched because the same tile of the enclosing zone is empty (fetch_snczi.py)
        if layer in PARENT:
            m = mask(PARENT[layer], x0, y0)
            if m is not None and not m.any():
                return m
        return None
    im = Image.open(p).convert("RGBA")
    return np.asarray(im)[:, :, 3] > 0


# Hole-filling thresholds (enclosed dry areas up to this size are filled), at 2 m per pixel:
# 0.5 ha, 2 ha (the reference) and 5 ha. The threshold is a choice, reported as a sensitivity.
ENV = {"05": 1250, "2": 5000, "5": 12500}


@lru_cache(maxsize=40)
def _holes(layer, x0, y0):
    """Label the holes that the zone encloses, on the 3 x 3 mosaic of neighbouring tiles (so that
    holes cut by a tile edge are closed too), and return the centre tile's mask, its hole labels
    and the size in pixels of every hole."""
    from scipy import ndimage
    n = PX_N
    mos = np.zeros((3 * n, 3 * n), bool)
    centre = None
    for i, dy in enumerate((1, 0, -1)):
        for j, dx in enumerate((-1, 0, 1)):
            m = mask(layer, x0 + dx * TILE, y0 + dy * TILE)
            if m is not None:
                mos[i * n:(i + 1) * n, j * n:(j + 1) * n] = m
                if dx == 0 and dy == 0:
                    centre = m
    if centre is None:
        return None
    holes = ndimage.binary_fill_holes(mos) & ~mos
    lab, k = ndimage.label(holes)
    sizes = np.zeros(k + 1)
    if k:
        sizes[1:] = ndimage.sum(holes, lab, index=np.arange(1, k + 1))
    return centre, lab[n:2 * n, n:2 * n].copy(), sizes


@lru_cache(maxsize=150)
def mask_filled(layer, x0, y0, max_px=ENV["2"]):
    """The tile's mask with every enclosed hole of up to max_px pixels filled (added after the plan
    was frozen, METHOD.md section 9). The view service renders water-depth grids, and the hydraulic
    models leave buildings (and often whole blocks) dry, so inside a flood zone each building is a
    hole. Filling the holes the zone encloses gives a zone envelope; larger enclosed areas stay
    out. Whether the official zone polygons do the same could not be checked (their download is
    behind an ALTCHA challenge). Closing holes can only add zone pixels."""
    h = _holes(layer, x0, y0)
    if h is None:
        return None
    centre, lab, sizes = h
    small = sizes <= max_px
    small[0] = False
    return centre | small[lab]


def in_mask(layer, xs, ys, filled=None):
    """Boolean per point: is the pixel under (x, y) inside the zone? False where the tile is missing.
    filled: None for the depth grid as rendered, or a hole-size threshold in pixels (envelope)."""
    getter = mask if filled is None else (lambda l, a, b: mask_filled(l, a, b, filled))
    out = np.zeros(len(xs), dtype=bool)
    tx = (np.floor(xs / TILE) * TILE).astype(int)
    ty = (np.floor(ys / TILE) * TILE).astype(int)
    for (a, b) in set(zip(tx.tolist(), ty.tolist())):
        sel = (tx == a) & (ty == b)
        m = getter(layer, a, b)
        if m is None:
            MISSING.add((layer, a, b))   # a tile the building needs was not fetched
            continue
        col = np.clip(((xs[sel] - a) / PXM).astype(int), 0, m.shape[1] - 1)
        row = np.clip(((b + TILE - ys[sel]) / PXM).astype(int), 0, m.shape[0] - 1)
        out[sel] = m[row, col]
    return out


def pixel_centres(g):
    x0, y0, x1, y1 = g.bounds
    xs = np.arange(np.floor(x0 / PXM) * PXM + PXM / 2, x1, PXM)
    ys = np.arange(np.floor(y0 / PXM) * PXM + PXM / 2, y1, PXM)
    if len(xs) == 0 or len(ys) == 0:
        p = g.representative_point()
        return np.array([p.x]), np.array([p.y])
    X, Y = np.meshgrid(xs, ys)
    X, Y = X.ravel(), Y.ravel()
    inside = shapely.contains_xy(g, X, Y)
    if not inside.any():
        p = g.representative_point()
        return np.array([p.x]), np.array([p.y])
    return X[inside], Y[inside]


def patricova():
    f = os.path.join(R, "data", "raw", "patricova", "orde_patricova_peligrosidad_inun.zip")
    shp = [n for n in zipfile.ZipFile(f).namelist() if n.endswith(".shp")][0]
    meta, _, wkb, fields = raw.read(f"/vsizip/{f}/{shp}")
    cols = list(meta["fields"])
    lvl = np.asarray(fields[cols.index("n_pelig")], dtype=float)
    geoms = shapely.make_valid(shapely.from_wkb(wkb))
    return geoms, lvl


def main():
    os.makedirs(OUT, exist_ok=True)
    pg, plvl = patricova()
    trees = {"pat16": shapely.STRtree(pg[(plvl >= 1) & (plvl <= 6)]), "patgeo": shapely.STRtree(pg[plvl == 7])}
    for f in sorted(glob.glob(os.path.join(R, "work", "buildings", "*.pkl"))):
        ine = os.path.basename(f)[:-4]
        dst = os.path.join(OUT, f"{ine}.pkl")
        # recompute when the buildings or this script are newer than the flags (or with --force)
        newest = max(os.path.getmtime(f), os.path.getmtime(os.path.abspath(__file__)))
        if "--force" not in sys.argv and os.path.exists(dst) and os.path.getmtime(dst) > newest:
            continue
        rows = pickle.load(open(f, "rb"))
        geoms = np.array([shapely.from_wkb(r["wkb"]) for r in rows], dtype=object)
        cents = shapely.centroid(geoms) if len(geoms) else geoms
        flags = [dict() for _ in rows]
        for key, tree in trees.items():
            hit_fp = np.zeros(len(rows), bool)
            hit_ct = np.zeros(len(rows), bool)
            if len(rows):
                a, _ = tree.query(geoms, predicate="intersects")
                hit_fp[np.unique(a)] = True
                a, _ = tree.query(cents, predicate="intersects")
                hit_ct[np.unique(a)] = True
            for i in range(len(rows)):
                flags[i][key + "_fp"] = bool(hit_fp[i])
                flags[i][key + "_ct"] = bool(hit_ct[i])
                for h in ENV:   # PATRICOVA polygons have no building holes: envelope = polygon
                    flags[i][f"{key}_env{h}fp"] = bool(hit_fp[i])
                    flags[i][f"{key}_env{h}ct"] = bool(hit_ct[i])
        variants = [("", None)] + [(f"env{h}", px) for h, px in ENV.items()]
        for i, g in enumerate(geoms):
            xs, ys = pixel_centres(g)
            c = cents[i]
            # footprint pixel centres plus the centroid (last), located once
            X, Y = np.append(xs, c.x), np.append(ys, c.y)
            tx = (np.floor(X / TILE) * TILE).astype(int)
            ty = (np.floor(Y / TILE) * TILE).astype(int)
            col = np.clip(((X - tx) / PXM).astype(int), 0, PX_N - 1)
            row = np.clip(((ty + TILE - Y) / PXM).astype(int), 0, PX_N - 1)
            tiles = sorted(set(zip(tx.tolist(), ty.tolist())))
            sels = [(a, b, (tx == a) & (ty == b)) for a, b in tiles]
            for key, layer in LAYERS.items():
                for name, px in variants:
                    vals = np.zeros(len(X), bool)
                    for a, b, sel in sels:
                        m = mask(layer, a, b) if px is None else mask_filled(layer, a, b, px)
                        if m is None:
                            MISSING.add((layer, a, b))
                            continue
                        vals[sel] = m[row[sel], col[sel]]
                    flags[i][f"{key}_{name}fp" if name else f"{key}_fp"] = bool(vals[:-1].any())
                    flags[i][f"{key}_{name}ct" if name else f"{key}_ct"] = bool(vals[-1])
        pickle.dump(flags, open(dst + ".tmp", "wb"))
        os.replace(dst + ".tmp", dst)
        print(ine, len(rows), "missing tiles so far", len(MISSING), flush=True)
    if MISSING:
        print("WARNING: missing SNCZI tiles:", len(MISSING))


if __name__ == "__main__":
    main()
