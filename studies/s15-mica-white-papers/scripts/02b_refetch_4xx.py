"""Deviation D1 (METHOD.md): re-fetch, once, every registered URL whose main request or one-hop request was skipped
because /robots.txt answered 401/403 (frozen rule). The new record replaces the old one in work/collect/urls.jsonl;
the old one is kept under "frozen" so the frozen-rule outcome can still be computed."""
import importlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import fetch
assert fetch.RFC9309_4XX
collect = importlib.import_module("02_collect")
OUT = collect.OUT
BLOCK = ("robots:blocked-fetch", "robots-on-redirect:blocked-fetch")


def affected(d):
    return any((x.get("reason") or "") in BLOCK for x in [d["main"]] + d.get("hops", []))


recs = [json.loads(l) for l in OUT.open()]
codes, _ = collect.url_codes(collect.load_rows())
f = fetch.Fetcher(collect.WORK / "requests.log")
todo = [d for d in recs if affected(d) and "frozen" not in d]
print(len(todo), "records to re-fetch", flush=True)
done = {}
for d in todo:
    new = collect.process_url(f, d["url"], codes[d["url"]])
    new["cohort"] = d["cohort"]
    new["frozen"] = {"main": d["main"], "hops": d.get("hops", [])}
    done[d["url"]] = new
tmp = OUT.with_suffix(".tmp")
with tmp.open("w") as fh:
    for d in recs:
        fh.write(json.dumps(done.get(d["url"], d)) + "\n")
tmp.replace(OUT)
print("rewritten", len(done))
