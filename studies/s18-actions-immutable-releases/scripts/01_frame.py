"""Step 1: enumerate the two sampling frames with the GitHub search API (REST) and draw the samples.

Frame A: public, non-fork, non-archived repositories with >= 20,000 stars pushed on or after
PUSHED_SINCE; population A = the first 1,000 by stars (ties broken by repository id).
Frame B: the same filters with 1,000-5,000 stars; population B = a seeded random sample of 500.
Each search slice must return fewer than 1,000 results (the search API's cap); slices are adapted
automatically and every query is logged with its total_count.
Writes data/raw/frame_{a,b}.jsonl (not published) and data/frame_queries.csv (published).
"""
from __future__ import annotations

import csv
import json
import random
import time
import urllib.parse

from common import DATA, RAW, api

PUSHED_SINCE = "2026-07-05"          # 90 days before 2026-10-03
QUAL = f"pushed:>={PUSHED_SINCE} archived:false fork:false is:public"
SEED = 20261003
N_A, N_B = 1000, 500
log_rows: list[dict] = []


def search(stars: str, page: int):
    q = f"stars:{stars} {QUAL}"
    url = ("/search/repositories?sort=stars&order=desc&per_page=100&page=%d&q=%s"
           % (page, urllib.parse.quote(q)))
    for _ in range(5):
        s, js = api(url, use_cache=False)
        if s == 200 and js is not None:
            log_rows.append({"frame": FRAME, "query": q, "page": page, "total_count": js["total_count"],
                             "incomplete_results": js["incomplete_results"], "items": len(js["items"]),
                             "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            return js
        time.sleep(10)
    raise RuntimeError(f"search failed: {q} page {page} status {s}")


def reduce(it: dict) -> dict:
    return {"id": it["id"], "full_name": it["full_name"], "owner_type": it["owner"]["type"],
            "stars": it["stargazers_count"], "pushed_at": it["pushed_at"], "created_at": it["created_at"],
            "fork": it["fork"], "archived": it["archived"], "default_branch": it["default_branch"],
            "language": it.get("language")}


def collect_range(lo: int, hi: int | None, out: dict) -> int:
    stars = f">={lo}" if hi is None else f"{lo}..{hi}"
    js = search(stars, 1)
    total = js["total_count"]
    if total >= 1000:
        return -1
    for it in js["items"]:
        out[it["id"]] = reduce(it)
    pages = (total + 99) // 100
    for p in range(2, pages + 1):
        for it in search(stars, p)["items"]:
            out[it["id"]] = reduce(it)
    return total


def adaptive(lo: int, hi_max: int, out: dict, width: int) -> None:
    while True:
        hi = min(lo + width - 1, hi_max)
        got = collect_range(lo, hi, out)
        if got < 0:
            if hi == lo:
                raise RuntimeError(f"single star value {lo} has >= 1000 results")
            width = max(1, width // 2)
            continue
        print(f"  {FRAME} stars {lo}..{hi}: {got}", flush=True)
        if hi >= hi_max:
            return
        lo = hi + 1
        if got < 400:
            width = int(width * 1.6) + 1


def main() -> None:
    global FRAME
    RAW.mkdir(parents=True, exist_ok=True)
    # Frame A: >= 20,000 stars. Fixed top slice, then adaptive slices downwards from 20,000.
    FRAME = "A"
    a: dict = {}
    got = collect_range(100000, None, a)
    assert got >= 0
    adaptive(20000, 99999, a, 10000)
    frame_a = sorted(a.values(), key=lambda r: (-r["stars"], r["id"]))
    FRAME = "B"
    b: dict = {}
    adaptive(1000, 5000, b, 40)
    frame_b = sorted(b.values(), key=lambda r: r["id"])
    for name, fr in (("frame_a", frame_a), ("frame_b", frame_b)):
        with open(RAW / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for r in fr:
                f.write(json.dumps(r, sort_keys=True) + "\n")
    rng = random.Random(SEED)
    sample_b_ids = sorted(rng.sample([r["id"] for r in frame_b], N_B))
    pop = {"A": [r["id"] for r in frame_a[:N_A]], "B": sample_b_ids,
           "frame_sizes": {"A": len(frame_a), "B": len(frame_b)},
           "a_cutoff_stars": frame_a[N_A - 1]["stars"], "seed": SEED, "pushed_since": PUSHED_SINCE,
           "qualifiers": QUAL, "enumerated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (RAW / "population.json").write_text(json.dumps(pop, indent=1))
    with open(DATA / "frame_queries.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(log_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(log_rows)
    print("frame A", len(frame_a), "cutoff stars", pop["a_cutoff_stars"], "| frame B", len(frame_b))


if __name__ == "__main__":
    main()
