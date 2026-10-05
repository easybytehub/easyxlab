#!/usr/bin/env python3
"""Download the Catastro INSPIRE Buildings (BU) package of every municipality of the province of
Valencia that the observed flood extent touches (any variant in work/extent/extent_summary.json).

    python3 scripts/fetch_catastro.py            # -> data/raw/catastro/A.ES.SDGC.BU.<code>.zip
    python3 scripts/fetch_catastro.py --map-only # only (re)build the Catastro <-> INE code map

The province feed is the INSPIRE ATOM of the Dirección General del Catastro
(https://www.catastro.hacienda.gob.es/INSPIRE/buildings/46/ES.SDGC.bu.atom_46.xml). Catastro
numbers municipalities with its own codes, which differ from the INE codes used by the IGN
(Paiporta is 46188 in Catastro and 46186 in the INE). Each feed entry carries the municipality's
bounding box; we pair it with the IGN municipality whose bounding box overlaps it most
(intersection over union) and check the pairing against the names.

Requests go through polite.py (fixed User-Agent, at most 1 request per second per host,
robots.txt read and logged; the FNMT intermediate certificates the server does not send are
added to the trust store, verification stays on). Resumable: packages on disk are skipped."""
import glob
import json
import os
import re
import sys
import unicodedata
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(R, "data", "raw", "catastro")
ATOM_URL = "https://www.catastro.hacienda.gob.es/INSPIRE/buildings/46/ES.SDGC.bu.atom_46.xml"
ATOM = os.path.join(R, "data", "raw", "catastro", "ES.SDGC.bu.atom_46.xml")
MAP = os.path.join(R, "data", "municipality_codes.csv")


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


def atom_entries():
    if not os.path.exists(ATOM):
        polite.fetch(ATOM_URL, ATOM, accept="application/atom+xml")
    s = open(ATOM, encoding="latin-1").read()
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", s, re.S):
        t = re.search(r"<title>\s*(\d{5})-(.*?) buildings\s*</title>", e)
        url = re.search(r'<link rel="enclosure" href="([^"]+)"', e).group(1)
        poly = [float(x) for x in re.search(r"<georss:polygon>(.*?)</georss:polygon>", e).group(1).split()]
        lats, lons = poly[0::2], poly[1::2]
        out.append({"cat": t.group(1), "name": t.group(2).strip(), "url": url,
                    "bbox_ll": (min(lons), min(lats), max(lons), max(lats))})
    return out


def name_score(ign_name, cat_name):
    """Similarity of an IGN name (possibly bilingual, 'A/B') and a Catastro name (upper case, no
    accents, letters such as ç sometimes dropped): best SequenceMatcher ratio over the parts and the
    whole, after removing accents, articles and non-letters."""
    import difflib
    c = norm(cat_name)
    parts = [norm(x) for x in ign_name.split("/")] + [norm(ign_name)]
    return max(difflib.SequenceMatcher(None, p, c).ratio() for p in parts if p)


def code_map():
    """Pair each Catastro feed entry with an IGN (INE) municipality: the best name match among the
    municipalities whose bounding box overlaps the entry's; ties broken by bounding-box overlap."""
    from pyproj import Transformer
    import s19lib
    t = Transformer.from_crs(4326, 25830, always_xy=True)
    ign = {k: (nm, g.bounds) for k, (nm, g) in s19lib.load_municipalities().items()}
    rows = []
    for e in atom_entries():
        x0, y0 = t.transform(e["bbox_ll"][0], e["bbox_ll"][1])
        x1, y1 = t.transform(e["bbox_ll"][2], e["bbox_ll"][3])
        cands = []
        for ine, (nm, (a0, b0, a1, b1)) in ign.items():
            iw = max(0, min(x1, a1) - max(x0, a0)); ih = max(0, min(y1, b1) - max(y0, b0))
            inter = iw * ih
            if inter <= 0:
                continue
            union = (x1 - x0) * (y1 - y0) + (a1 - a0) * (b1 - b0) - inter
            cands.append((round(name_score(nm, e["name"]), 3), inter / union, ine))
        sc, iou, best = max(cands)
        rows.append({"ine": best, "catastro": e["cat"], "ign_name": ign[best][0], "catastro_name": e["name"],
                     "bbox_iou": round(iou, 3), "name_score": sc, "url": e["url"]})
    with open(MAP, "w", encoding="utf-8") as f:
        f.write("ine_code,catastro_code,ign_name,catastro_name,bbox_iou,name_score\n")
        for r in sorted(rows, key=lambda r: r["ine"]):
            f.write(f'{r["ine"]},{r["catastro"]},"{r["ign_name"]}","{r["catastro_name"]}",{r["bbox_iou"]},{r["name_score"]}\n')
    dup = [k for k in {r["ine"] for r in rows} if sum(r["ine"] == k for r in rows) > 1]
    weak = [(r["ign_name"], r["catastro_name"], r["name_score"]) for r in rows if r["name_score"] < 0.8]
    print(len(rows), "feed entries;", len(dup), "INE codes paired twice", dup, "; weak name matches:", weak)
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = code_map()
    if "--map-only" in sys.argv:
        return
    summ = json.load(open(os.path.join(R, "work", "extent", "extent_summary.json")))
    want = set()
    for v in summ["variants"].values():
        want |= set(v["municipalities"])
    by_ine = {r["ine"]: r for r in rows}
    missing = sorted(want - set(by_ine))
    if missing:
        print("no Catastro feed entry for INE codes", missing)
    todo = [by_ine[c] for c in sorted(want) if c in by_ine]
    print(len(todo), "municipalities to fetch", flush=True)
    for r in todo:
        dst = os.path.join(OUT, f"A.ES.SDGC.BU.{r['catastro']}.zip")
        if os.path.exists(dst):
            continue
        # municipality names in the feed URLs contain spaces: percent-encode the path
        st, _ = polite.fetch(urllib.parse.quote(r["url"], safe=":/"), dst)
        print(st, r["ine"], r["catastro"], r["catastro_name"], os.path.getsize(dst) if os.path.exists(dst) else "-", flush=True)


if __name__ == "__main__":
    main()
