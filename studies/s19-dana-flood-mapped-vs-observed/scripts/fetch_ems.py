#!/usr/bin/env python3
"""Download the Copernicus EMS Rapid Mapping activation EMSR773 (Flood in Valencia Region,
Spain): the public activation record (JSON) and every delivered vector product package.

    python3 scripts/fetch_ems.py            # -> data/raw/ems/ (git-ignored)

The activation record comes from the public dashboard API; each product's `downloadPath`
is a ZIP with the vector layers (observedEventA, floodDepthA, builtUp…, source and AOI
layers) and the map PDFs. Requests go through polite.py (fixed User-Agent, at most 1 request
per second per host, robots.txt read and logged)."""
import json, os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(R, "data", "raw", "ems")
API = "https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=EMSR773"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    os.makedirs(OUT, exist_ok=True)
    act = os.path.join(OUT, "EMSR773_activation.json")
    polite.fetch(API, act, accept="application/json")
    d = json.load(open(act))["results"][0]
    manifest = []
    for a in d["aois"]:
        for p in a["products"]:
            u = p.get("downloadPath")
            if not u:
                continue
            dst = os.path.join(OUT, u.rsplit("/", 1)[1])
            if not os.path.exists(dst):
                st, _ = polite.fetch(u, dst)
                print(st, os.path.basename(dst), flush=True)
            manifest.append({"aoi": a["number"], "aoi_name": a["name"], "type": p["type"],
                             "monitoring_number": p["monitoringNumber"],
                             "version": p["version"]["number"], "file": os.path.basename(dst),
                             "bytes": os.path.getsize(dst), "sha256": sha256(dst)})
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
