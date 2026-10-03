#!/usr/bin/env python3
"""Draw the comment-detector audit sample (plan frozen in METHOD.md s. 6) and print the comment
blocks of each sampled host for labelling (to work/, never published).

    python3 scripts/draw_audit_sample.py      -> work/audit_sample.txt, work/audit_sample.json
"""
import json
import os
import random

import nlcomments as N

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SEED = 20261003


def main():
    recs = [json.loads(line) for line in open(os.path.join(ROOT, "data", "raw", "scan.jsonl"))]
    recs = [r for r in recs if "robots" in r]
    for r in recs:   # the sample is defined on the detector-v1 flags of the scan (frozen plan)
        v1 = r["robots"].get("nl_v1")
        if v1:
            r["robots"]["nl_reservation"], r["robots"]["nl_prohibition"] = v1["reservation"], v1["prohibition"]
    flagged = sorted([r for r in recs if r["robots"]["nl_reservation"] or r["robots"]["nl_prohibition"]], key=lambda r: r["host"])
    unflag = sorted([r for r in recs if not (r["robots"]["nl_reservation"] or r["robots"]["nl_prohibition"])
                     and r["_raw"]["comment_blocks"]], key=lambda r: r["host"])
    rng = random.Random(SEED)
    fs = flagged if len(flagged) <= 60 else rng.sample(flagged, 60)
    us = rng.sample(unflag, min(40, len(unflag)))
    sample = [("flagged", r) for r in sorted(fs, key=lambda r: r["host"])] + [("unflagged", r) for r in sorted(us, key=lambda r: r["host"])]
    seen = {}
    lines = [f"flagged population {len(flagged)}, unflagged-with-comments population {len(unflag)}; seed {SEED}", ""]
    meta = []
    for i, (st, r) in enumerate(sample, 1):
        rb = r["robots"]
        lines.append(f"### {i} {r['host']} [{st}] res={int(rb['nl_reservation'])} pro={int(rb['nl_prohibition'])} | "
                     f"R: {rb['nl_reservation_evidence'][:60]} | P: {rb['nl_prohibition_evidence'][:80]}")
        blocks = r["_raw"]["comment_blocks"]
        if st == "flagged":      # the blocks that fired, which is what precision is about
            blocks = [b for b in blocks if N.prohibition(b) or N.reservation(b)]
        else:                    # every block: misses are what we look for
            blocks = [b for b in blocks if len(b) >= 25 or any(w in b.lower() for w in ("ai", "tdm", "bot", "crawl", "scrap", "mining"))][:25]
        for b in blocks:
            if len(b) < 4:
                continue
            key = b[:300]
            if key in seen:
                lines.append(f"   = same block as #{seen[key]}")
                continue
            seen[key] = i
            lines.append("   - " + b[:420])
        meta.append(dict(i=i, host=r["host"], stratum=st, nl_reservation=int(rb["nl_reservation"]),
                         nl_prohibition=int(rb["nl_prohibition"])))
    open(os.path.join(ROOT, "work", "audit_sample.txt"), "w").write("\n".join(lines))
    json.dump(dict(seed=SEED, flagged_population=len(flagged), unflagged_population=len(unflag), sample=meta),
              open(os.path.join(ROOT, "work", "audit_sample.json"), "w"), indent=1)
    print(len(flagged), len(unflag), len(sample))


if __name__ == "__main__":
    main()
