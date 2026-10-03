"""Deviation D4 (METHOD.md): re-download the iXBRL files whose identifiers were not recorded in the first validation
batch, check their sha256 against the first download, read LEI/DTI/date facts with Arelle (load only) and merge them
into work/validate/<sha>.json. Files are deleted after reading."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from fetch import Fetcher
from mica_wp_check import arelle_validate, all_leis, all_dtis

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "data/raw/taxonomy/mica_taxonomy_2025.zip"
VAL = ROOT / "work/validate"
src = {}
for line in (ROOT / "work/collect/urls.jsonl").open():
    d = json.loads(line)
    for x in [d["main"]] + d.get("hops", []):
        if x.get("outcome") == "ixbrl-esma" and x.get("sha256"):
            src.setdefault(x["sha256"], x.get("final_url") or x["url"])
f = Fetcher(ROOT / "work/requests.log")
tmp = ROOT / "work/tmp"; tmp.mkdir(exist_ok=True)
todo = [p for p in sorted(VAL.glob("*.json")) if (json.loads(p.read_text()).get("doc") or {}).get("doc_class") == "ixbrl-esma"
        and not (json.loads(p.read_text()).get("identifiers") or {}).get("from_refetch")
        and not (json.loads(p.read_text()).get("validation") or {}).get("lei_facts")]
print(len(todo), "files to re-read", flush=True)
for n, p in enumerate(todo, 1):
    v = json.loads(p.read_text())
    url = src.get(p.stem)
    if not url:
        v["refetch"] = {"status": "no-url"}; p.write_text(json.dumps(v, default=str)); continue
    dest = tmp / "refetch.xhtml"
    r = f.get(url, dest=dest)
    v["refetch"] = {"status": r["status"], "reason": r["reason"], "sha256": r["sha256"], "same_hash": r["sha256"] == p.stem}
    if r["status"] == 200 and dest.exists():
        a = arelle_validate(dest, PKG, formulas=False, validate=False)
        vv = v.setdefault("validation", {})
        for k in ("lei_facts", "dti_facts", "date_facts", "context_identifiers", "fact_count"):
            vv[k] = a.get(k)
        v["identifiers"] = {"leis": sorted(all_leis(a)), "dtis": sorted(all_dtis(a)), "dates": a.get("date_facts"), "from_refetch": True}
    dest.unlink(missing_ok=True)
    p.write_text(json.dumps(v, default=str))
    if n % 20 == 0:
        print(n, flush=True)
print("finished", flush=True)
