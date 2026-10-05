#!/usr/bin/env python3
"""Check that the SNCZI zones are nested (T10 within T100 within T500) on every tile where the
smaller and the larger zone were both fetched, and report the pixels that break the nesting.
fetch_snczi.py skips a tile of a smaller zone when the same tile of the larger zone is empty;
this check bounds the error of that shortcut.

    .venv/bin/python scripts/check_nesting.py     # -> data/snczi_nesting.json"""
import glob
import json
import os

import numpy as np
from PIL import Image

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(R, "work", "snczi", "tiles")


def m(layer, name):
    return np.asarray(Image.open(os.path.join(T, layer, name)).convert("RGBA"))[:, :, 3] > 0


def main():
    out = {}
    for small, big in (("NZ.Flood.FluvialT10", "NZ.Flood.FluvialT100"), ("NZ.Flood.FluvialT100", "NZ.Flood.FluvialT500"),
                       ("NZ.Flood.FluvialT10", "NZ.Flood.FluvialT500")):
        names = sorted(set(os.listdir(os.path.join(T, small))) & set(os.listdir(os.path.join(T, big))))
        n_small = n_out = tiles_out = 0
        empty_big_nonempty_small = 0
        for nm in names:
            a, b = m(small, nm), m(big, nm)
            n_small += int(a.sum())
            k = int((a & ~b).sum())
            n_out += k
            tiles_out += k > 0
            if a.any() and not b.any():
                empty_big_nonempty_small += 1
        out[f"{small[-3:].lstrip('T')}_in_{big[-4:].lstrip('T')}"] = {
            "tiles_compared": len(names), "pixels_in_smaller_zone": n_small, "pixels_outside_larger_zone": n_out,
            "share_outside": n_out / n_small if n_small else None, "tiles_with_any_pixel_outside": tiles_out,
            "tiles_where_larger_is_empty_but_smaller_is_not": empty_big_nonempty_small}
    json.dump(out, open(os.path.join(R, "data", "snczi_nesting.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
