#!/usr/bin/env python3
"""SNCZI fluvial flood-hazard zones (T10, T100, T500) as raster masks, from the INSPIRE view
service of the Sistema Nacional de Cartografía de Zonas Inundables published through the IDEE:
https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones (layers
NZ.Flood.FluvialT10, NZ.Flood.FluvialT100, NZ.Flood.FluvialT500; MITECO, CC BY 4.0).

Why masks and not the vector layers: the MITECO download page for the shapefiles puts an ALTCHA
proof-of-work challenge in front of every file, which is an access control we do not bypass, and
the MITECO WMS of the zone polygons (wms.mapama.gob.es/sig/agua/ZI_Laminas*) answered every
request with a server error on 2026-10-04. The INSPIRE service renders the hazard (water-depth)
maps of each return period; a pixel is inside the zone when the rendered image is not
transparent there.

Tiles are 2,048 m squares on a fixed EPSG:25830 grid, requested at 1,024 x 1,024 pixels (2 m per
pixel), only where a building that meets any variant of the observed extent lies
(work/buildings/*.pkl). PNG tiles are kept in work/snczi/tiles/<layer>/<x0>_<y0>.png.

    .venv/bin/python scripts/fetch_snczi.py        # resumable; at most 1 request per second

The preferential flow zone (zona de flujo preferente) is not in this service. We try the MITECO
WMS once per run and record its answer in work/snczi/zfp_probe.txt.
"""
import glob
import os
import pickle
import sys

import shapely

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(R, "work", "snczi", "tiles")
WMS = "https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones"
LAYERS = ["NZ.Flood.FluvialT500", "NZ.Flood.FluvialT100", "NZ.Flood.FluvialT10"]
# the zones are nested (T10 within T100 within T500): a tile is requested for a layer only when the
# same tile of the next larger zone is not empty. scripts/check_nesting.py measures the nesting on
# the tiles where all three layers were fetched.
PARENT = {"NZ.Flood.FluvialT100": "NZ.Flood.FluvialT500", "NZ.Flood.FluvialT10": "NZ.Flood.FluvialT100"}
TILE = 2048
PX = 1024


def tile_of(x, y):
    return int(x // TILE) * TILE, int(y // TILE) * TILE


def needed_tiles():
    tiles = set()
    for f in sorted(glob.glob(os.path.join(R, "work", "buildings", "*.pkl"))):
        for r in pickle.load(open(f, "rb")):
            x0, y0, x1, y1 = shapely.from_wkb(r["wkb"]).bounds
            for tx in range(int(x0 // TILE) * TILE, int(x1 // TILE) * TILE + 1, TILE):
                for ty in range(int(y0 // TILE) * TILE, int(y1 // TILE) * TILE + 1, TILE):
                    tiles.add((tx, ty))
    return sorted(tiles)


def empty(layer, x0, y0):
    """True when the tile exists and has no zone pixel."""
    from PIL import Image
    import numpy as np
    p = os.path.join(TILES, layer, f"{x0}_{y0}.png")
    if not os.path.exists(p):
        return False
    return not (np.asarray(Image.open(p).convert("RGBA"))[:, :, 3] > 0).any()


def url(layer, x0, y0):
    return (f"{WMS}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS={layer}&STYLES=&CRS=EPSG:25830"
            f"&BBOX={x0},{y0},{x0 + TILE},{y0 + TILE}&WIDTH={PX}&HEIGHT={PX}&FORMAT=image/png&TRANSPARENT=TRUE")


def probe_zfp():
    out = os.path.join(R, "work", "snczi", "zfp_probe.txt")
    u = ("https://wms.mapama.gob.es/sig/agua/ZI_LaminasZFP?service=wms&request=GetCapabilities")
    try:
        st, _ = polite.fetch(u, out)
        body = open(out if os.path.exists(out) else out + f".http{st}", encoding="utf-8", errors="replace").read(300)
        print("ZFP WMS:", st, body[:160].replace("\n", " "), flush=True)
    except Exception as e:
        print("ZFP WMS error", repr(e)[:200], flush=True)


def main():
    probe_zfp()
    tiles = needed_tiles()
    print(len(tiles), "tiles x", len(LAYERS), "layers", flush=True)
    for layer in LAYERS:
        d = os.path.join(TILES, layer)
        os.makedirs(d, exist_ok=True)
        for i, (x0, y0) in enumerate(tiles):
            dst = os.path.join(d, f"{x0}_{y0}.png")
            if os.path.exists(dst):
                continue
            if layer in PARENT and empty(PARENT[layer], x0, y0):
                continue
            for attempt in range(3):
                try:
                    st, _ = polite.fetch(url(layer, x0, y0), dst, accept="image/png")
                    if st == 200:
                        break
                except Exception as e:
                    print("retry", layer, x0, y0, repr(e)[:120], flush=True)
            if i % 50 == 0:
                print(layer, i, "/", len(tiles), flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
