"""Validate every Inline XBRL file kept by 02_collect.py with Arelle + the pinned ESMA package, then delete it.
Run as a single process (about 5 s and up to ~0.8 GB of RAM per file): python scripts/03_validate.py
Output: work/validate/<sha256>.json (one per distinct file)."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mica_wp_check import verdict  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "data/raw/taxonomy/mica_taxonomy_2025.zip"
PKG_SHA = "19921398b16cb2521f808965e5d058be8f68591c8f9d77d24eb9df2c14aae033"
DOCS = ROOT / "work/docs"
OUT = ROOT / "work/validate"


def main():
    assert hashlib.sha256(PKG.read_bytes()).hexdigest() == PKG_SHA, "taxonomy package does not match the pin"
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(DOCS.glob("*.xhtml"))
    print(len(files), "files", flush=True)
    tmp = ROOT / "work/tmp"
    tmp.mkdir(exist_ok=True)
    for n, p in enumerate(files, 1):
        sha = p.stem
        o = OUT / f"{sha}.json"
        if not o.exists():
            t = time.time()
            data = p.read_bytes()
            try:
                v = verdict(data, "application/xhtml+xml", p.name, PKG, True, tmpdir=tmp)
            except Exception as e:  # keep going; record the failure
                v = {"error": f"{type(e).__name__}: {e}"[:300]}
            v["seconds"] = round(time.time() - t, 1)
            v["size"] = len(data)
            o.write_text(json.dumps(v, default=str))
        p.unlink()
        if n % 10 == 0:
            print(n, flush=True)
    print("finished", flush=True)


if __name__ == "__main__":
    main()
