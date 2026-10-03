#!/usr/bin/env python3
"""Download the Inside Airbnb listings.csv.gz files named in snapshots.py (polite fetcher,
robots.txt checked) into data/raw/insideairbnb/. Skips files already present."""
import os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from snapshots import SNAPSHOTS, url, raw_path
import polite
for area, path, before, after in SNAPSHOTS:
    for d in (before, after):
        out = raw_path(area, d)
        if os.path.exists(out):
            print("have", out); continue
        st, final = polite.fetch(url(path, d), out)
        h = hashlib.sha256(open(out, "rb").read()).hexdigest() if os.path.exists(out) else "-"
        print(st, area, d, os.path.getsize(out) if os.path.exists(out) else 0, h[:16])
