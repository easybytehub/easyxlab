#!/usr/bin/env python3
"""Build the review queue (METHOD.md §1.7) and print lots for the one-by-one review.

    python3 scripts/review_queue.py build work/auto           # -> work/auto/review_queue.csv
    python3 scripts/review_queue.py show work/auto R1 0 40     # print queue items 0..39 of set R1

Sets: R1 every covered lot that does not comply (primary rule); R2 a random sample of 60
covered lots that comply (seed 14); R3 every undeterminable lot; R4 every excluded lot that is
not land, plus a random sample of 60 land lots (seed 14). The review itself (verdicts) is
written by the study agent to work/review/verdicts.csv; scripts/analyse.py merges it.
"""
import csv
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classify as C  # noqa: E402

SEED = 14


def build(out):
    rows = list(csv.DictReader(open(os.path.join(out, "lots_auto.csv"), encoding="utf-8")))
    q = []
    r1 = [r for r in rows if r["scope"] == "covered" and r["compliant_primary"] == "no"]
    yes = [r for r in rows if r["scope"] == "covered" and r["compliant_primary"] == "yes"]
    rng = random.Random(SEED)
    r2 = yes if len(yes) <= 60 else rng.sample(yes, 60)
    r3 = [r for r in rows if r["scope"] == "undeterminable"]
    land = [r for r in rows if r["scope"] == "excluded" and r["scope_reason"].startswith("land")]
    other_ex = [r for r in rows if r["scope"] == "excluded" and not r["scope_reason"].startswith("land")]
    rng = random.Random(SEED)
    r4 = other_ex + (land if len(land) <= 60 else rng.sample(land, 60))
    for name, part in (("R1", r1), ("R2", r2), ("R3", r3), ("R4", r4)):
        for r in sorted(part, key=lambda x: (x["boe_id"], x["lot_key"])):
            q.append({"review_set": name, "lot_key": r["lot_key"]})
    with open(os.path.join(out, "review_queue.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["review_set", "lot_key"], lineterminator="\n")
        w.writeheader()
        w.writerows(q)
    print({k: sum(1 for x in q if x["review_set"] == k) for k in ("R1", "R2", "R3", "R4")})


def show(out, rset, a, b, width=700):
    rows = {r["lot_key"]: r for r in csv.DictReader(open(os.path.join(out, "lots_auto.csv"), encoding="utf-8"))}
    q = [x for x in csv.DictReader(open(os.path.join(out, "review_queue.csv"), encoding="utf-8")) if x["review_set"] == rset]
    cache = {}
    for i, x in enumerate(q[int(a):int(b)], start=int(a)):
        r = rows[x["lot_key"]]
        if r["boe_id"] not in cache:
            cache[r["boe_id"]] = json.load(open(os.path.join(out, "lots_text", r["boe_id"] + ".json"), encoding="utf-8"))
        d = cache[r["boe_id"]]
        t = next(l["text"] for l in d["lots"] if l["lot_key"] == x["lot_key"])
        t1 = re.sub(r"\s+", " ", t)
        print(f"[{rset} {i}] {x['lot_key']} | {r['seller_group']} | {r['seller_body'][:70]} | {r['split_method']} n={r['n_lots']}")
        print(f"   auto: type={r['lot_type']} scope={r['scope']} ({r['scope_reason']}) energy={r['energy_status']}/{r['energy_level']} {r['letters']}")
        print(f"   TEXT: {t1[:width]}{' …' if len(t1) > width else ''}")
        ws = C.energy_windows(t) or (C.energy_windows(d["general"]) if r["energy_level"] == "notice" else [])
        for w in ws[:2]:
            print("   ENERGY: " + re.sub(r"\s+", " ", w)[:300])
        if i == int(a) or r["boe_id"] != rows[q[i - 1]["lot_key"]]["boe_id"]:
            g = C.energy_windows(d["general"])
            if g:
                print("   NOTICE-ENERGY: " + re.sub(r"\s+", " ", g[0])[:300])
            print(f"   TITLE: {d['title'][:200]}")


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2])
    else:
        show(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]) if len(sys.argv) > 6 else 700)
