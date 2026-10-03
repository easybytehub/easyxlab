#!/usr/bin/env python3
"""Run optout_check over every host of data/frame.csv.

    python3 scripts/scan.py [--workers 16] [--out data/raw/scan.jsonl]

Raw records (with the robots.txt body, for the comment audit) go to data/raw/ (never published);
the request log to data/raw/requests.tsv. Resumable: hosts already in the output are skipped.
"""
import argparse
import base64
import csv
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import nlcomments
import optout_check as O
import politefetch as P

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "raw", "scan.jsonl"))
    ap.add_argument("--frame", default=os.path.join(ROOT, "data", "frame.csv"))
    ap.add_argument("--hosts", help="file with one host per line: scan only these frame hosts (D5 re-scan)")
    a = ap.parse_args()
    frame = list(csv.DictReader(open(a.frame)))
    if a.hosts:
        keep = {h.strip() for h in open(a.hosts) if h.strip()}
        frame = [r for r in frame if r["host"] in keep]
    done = set()
    if os.path.exists(a.out):
        for line in open(a.out):
            try:
                done.add(json.loads(line)["host"])
            except ValueError:
                pass
    todo = [r for r in frame if r["host"] not in done]
    print(f"{len(frame)} hosts, {len(done)} done, {len(todo)} to do", file=sys.stderr)
    s = P.Session(per_host=8)
    lock = threading.Lock()
    out = open(a.out, "a")

    def one(row):
        try:
            rec = O.check(row["host"], s)
        except Exception as e:  # noqa: BLE001
            rec = dict(host=row["host"], crash=f"{type(e).__name__}: {e}"[:300])
        rb = s.robots_for(row["host"])
        body = rb.get("body") or b""
        rec["_raw"] = dict(robots_b64=base64.b64encode(body).decode() if body else "",
                           comment_blocks=nlcomments.comment_blocks(body) if body else [])
        rec["country"] = row["country"]
        rec["wikidata"] = row["wikidata"]
        rec["crux_rank_bucket"] = row["crux_rank_bucket"]
        rec.pop("legal_basis", None)
        with lock:
            out.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            out.flush()
        return rec

    n = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(one, r) for r in todo]):
            n += 1
            if n % 100 == 0:
                print(n, "done", file=sys.stderr)
    out.close()
    with open(os.path.join(ROOT, "data", "raw", "requests.tsv"), "a") as f:
        for row in s.log:
            f.write("\t".join(str(x) for x in row) + "\n")
    print("max requests to one host:", s.max_requests_per_host(), file=sys.stderr)


if __name__ == "__main__":
    main()
