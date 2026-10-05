#!/usr/bin/env python3
"""How the SNCZI/ARPSI depth grid treats buildings, and how PATRICOVA does.

For the buildings inside the Copernicus extent whose footprint touches the 500-year depth grid
in six municipalities of l'Horta Sud and the Ribera (Paiporta 46186, Alfafar 46022, Catarroja
46094, Sedaví 46223, Massanassa 46165, Algemesí 46029), the share of each footprint's 2 m pixel
centres that lie in the grid; and, for the buildings that touch a PATRICOVA level 1-6 polygon in
those municipalities, the share of the footprint area inside it. Also counts the dwellings in
buildings recorded as 'declined' or 'ruin', and those dated 2026.

    .venv/bin/python scripts/qa_holes.py      # -> data/qa_holes.json"""
import json
import os
import pickle
import sys

import numpy as np
import shapely

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classify as C

R = C.R
SIX = {"46186": "Paiporta", "46022": "Alfafar", "46094": "Catarroja", "46223": "Sedaví",
       "46165": "Massanassa", "46029": "Algemesí"}


def main():
    pg, lvl = C.patricova()
    pat = pg[(lvl >= 1) & (lvl <= 6)]
    tree = shapely.STRtree(pat)
    grid, poly = [], []
    for ine in SIX:
        rows = pickle.load(open(os.path.join(R, "work", "buildings", f"{ine}.pkl"), "rb"))
        flags = pickle.load(open(os.path.join(R, "work", "flags", f"{ine}.pkl"), "rb"))
        for r, f in zip(rows, flags):
            if not r["fp"]["all"]:
                continue
            g = shapely.from_wkb(r["wkb"])
            if f["t500_fp"]:
                xs, ys = C.pixel_centres(g)
                grid.append(float(C.in_mask("NZ.Flood.FluvialT500", xs, ys).mean()))
            if f["pat16_fp"]:
                idx = tree.query(g, predicate="intersects")
                u = shapely.union_all(pat[idx])
                poly.append(float(shapely.area(shapely.intersection(g, u)) / g.area))
    cond = {"declined": 0, "ruin": 0}
    y2026 = 0
    for f in sorted(os.listdir(os.path.join(R, "work", "buildings"))):
        if not f.endswith(".pkl"):
            continue
        for r in pickle.load(open(os.path.join(R, "work", "buildings", f), "rb")):
            if r["fp"]["all"] and r["dwellings"] > 0:
                if r["condition"] in cond:
                    cond[r["condition"]] += r["dwellings"]
                if r["year"] == 2026:
                    y2026 += r["dwellings"]
    out = {"municipalities": SIX,
           "t500_grid": {"buildings": len(grid), "median_share_of_footprint_pixels_in_zone": round(float(np.median(grid)), 3),
                         "quartiles": [round(float(q), 3) for q in np.percentile(grid, [25, 75])]},
           "patricova_1_6": {"buildings": len(poly), "median_share_of_footprint_area_in_zone": round(float(np.median(poly)), 3),
                             "share_of_buildings_fully_inside": round(float(np.mean(np.array(poly) > 0.999)), 3)},
           "dwellings_in_extent_condition": cond, "dwellings_in_extent_dated_2026": y2026}
    json.dump(out, open(os.path.join(R, "data", "qa_holes.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
