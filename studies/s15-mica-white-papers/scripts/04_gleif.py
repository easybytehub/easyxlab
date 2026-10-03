"""Look up LEIs in GLEIF (public API, data CC0): the register's ae_lei / ae_lei_casp of cohort rows and every LEI found
in a validated file. Output: work/gleif.json {LEI: {found, registration_status, entity_status, legal_name, country}}.
Legal names are of legal entities (no personal data)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch import Fetcher  # noqa: E402
import importlib
collect = importlib.import_module("02_collect")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "work/gleif.json"
LEI_RE = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")


def main():
    leis = set()
    for r in collect.load_rows():
        for k in ("ae_lei", "ae_lei_casp"):
            v = r.get(k, "").strip().upper()
            if LEI_RE.match(v):
                leis.add(v)
    for p in (ROOT / "work/validate").glob("*.json"):
        v = json.loads(p.read_text())
        for x in (v.get("identifiers") or {}).get("leis", []):
            if LEI_RE.match(x):
                leis.add(x)
    known = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = sorted(l for l in leis if l not in known)
    print(len(leis), "LEIs,", len(todo), "to query", flush=True)
    f = Fetcher(ROOT / "work/requests.log")
    for i in range(0, len(todo), 100):
        batch = todo[i:i + 100]
        url = "https://api.gleif.org/api/v1/lei-records?page%5Bsize%5D=100&filter%5Blei%5D=" + ",".join(batch)
        r = f.get(url, headers={"Accept": "application/vnd.api+json"})
        if r["status"] != 200 or not r["body"]:
            print("GLEIF failed", r["status"], r["reason"])
            continue
        data = json.loads(r["body"])["data"]
        got = {}
        for d in data:
            a = d["attributes"]
            got[a["lei"]] = {"found": True, "registration_status": a["registration"]["status"],
                             "entity_status": a["entity"]["status"],
                             "legal_name": a["entity"]["legalName"]["name"],
                             "country": a["entity"]["legalAddress"]["country"]}
        for l in batch:
            known[l] = got.get(l, {"found": False})
    OUT.write_text(json.dumps(known, indent=0, sort_keys=True))
    print("found", sum(1 for v in known.values() if v["found"]), "of", len(known))


if __name__ == "__main__":
    main()
