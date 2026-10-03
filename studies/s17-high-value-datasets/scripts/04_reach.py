# SPDX-License-Identifier: Apache-2.0
"""Reachability sample (METHOD.md §7). Network step: reads data/raw/census.jsonl.gz, draws the
stratified sample, probes it through fetch.get (robots.txt first, 1 req/s per host), and writes
data/reach_sample.csv (no full URLs: dataset ID, distribution ID, host, outcome) and
data/raw/reach_results.jsonl (with URLs, never published)."""
import collections
import concurrent.futures as cf
import csv
import gzip
import json
import os
import random
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch  # noqa: E402
import hvd_rules as R  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
MS = {"at", "be", "bg", "cy", "cz", "de", "dk", "ee", "gr", "es", "fi", "fr", "hr", "hu", "ie", "it", "lt", "lu",
      "lv", "mt", "nl", "pl", "pt", "ro", "se", "si", "sk"}
PER_STRATUM, PER_HOST = 100, 10
IPLIT = __import__("re").compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def frame():
    fr = collections.defaultdict(dict)  # country -> url -> (dataset, distribution)
    for line in gzip.open(os.path.join(RAW, "census.jsonl.gz"), "rt"):
        r = json.loads(line)
        c = (r.get("country") or {}).get("id")
        if c not in MS:
            continue
        for d in r.get("distributions") or []:
            urls = (d.get("download_url") or []) or (d.get("access_url") or [])
            if not urls:
                continue
            u = str(urls[0]).strip()
            fr[c].setdefault(u, (r["id"], d.get("id")))
    return fr


def draw(fr):
    sample = []
    for c in sorted(fr):
        urls = sorted(fr[c])
        rnd = random.Random(17)
        rnd.shuffle(urls)
        per_host = collections.Counter()
        for u in urls:
            h = urllib.parse.urlsplit(u).netloc.lower() if u.lower().startswith(("http://", "https://")) else ""
            if h and per_host[h] >= PER_HOST:
                continue
            per_host[h] += 1
            sample.append({"country": c, "url": u, "dataset_id": fr[c][u][0], "distribution_id": fr[c][u][1],
                           "host": h, "frame_size": len(urls)})
            if sum(1 for s in sample if s["country"] == c) >= PER_STRATUM:
                break
    return sample


def classify(r):
    if r.skipped:
        return "skipped_robots"
    if r.error:
        return "too_many_redirects" if r.error == "too-many-redirects" else "network"
    s = r.status or 0
    if 200 <= s < 300:
        return "ok"
    if s in (401, 403):
        return "client_error_auth"
    if s in (404, 410):
        return "client_error_notfound"
    if 400 <= s < 500:
        return "client_error_other"
    if s >= 500:
        return "server_error"
    return "other"


def probe(item):
    u = item["url"]
    if not u.lower().startswith(("http://", "https://")) or not item["host"]:
        return {**item, "method": "", "outcome": "bad_url", "status": None, "ctype": "", "hops": 0}
    if R.is_ogc_service(u):
        method, target = "getcapabilities", R.getcapabilities_url(u)
        r = fetch.get(target, max_bytes=2048, timeout=20)
    else:
        method, target = "range-get", u
        r = fetch.get(target, headers={"Range": "bytes=0-2047"}, max_bytes=2048, timeout=20)
    ct = (r.headers.get("Content-Type") or r.headers.get("content-type") or "").split(";")[0].strip().lower()
    hops = len(json.loads(r.headers.get("x-hops", "[]") or "[]"))
    return {**item, "method": method, "outcome": classify(r), "status": r.status, "ctype": ct, "hops": hops,
            "skip_reason": r.skipped or "", "error": (r.error or "")[:120]}


def public_host(r):
    """Host name only: no user-info (one URL carried an e-mail-like user-info part), IP literals masked."""
    h = (urllib.parse.urlsplit(r["url"]).hostname or "") if r.get("url") else r["host"]
    return "ip-literal" if IPLIT.match(h) or ":" in h else h


def write_csv(results):
    fields = ["country", "dataset_id", "distribution_id", "host", "frame_size", "method", "outcome", "status",
              "ctype", "hops", "skip_reason"]
    results = sorted(results, key=lambda r: (r["country"], r["dataset_id"], str(r["distribution_id"])))
    with open(os.path.join(ROOT, "data", "reach_sample.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in results:
            w.writerow({**r, "host": public_host(r)})


def main():
    sample = draw(frame())
    by_host = collections.defaultdict(list)
    for s in sample:
        by_host[s["host"]].append(s)
    t0 = time.time()
    results = []
    with cf.ThreadPoolExecutor(max_workers=24) as ex:
        futs = [ex.submit(lambda items: [probe(i) for i in items], items) for items in by_host.values()]
        for f in cf.as_completed(futs):
            results += f.result()
            print(len(results), "/", len(sample), round(time.time() - t0), "s", flush=True)
    with open(os.path.join(RAW, "reach_results.jsonl"), "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_csv(results)
    json.dump({"utc_end": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n": len(results),
               "seconds": round(time.time() - t0)}, open(os.path.join(RAW, "reach_meta.json"), "w"))


if __name__ == "__main__":
    if sys.argv[1:] == ["--rewrite-csv"]:  # rebuild data/reach_sample.csv from data/raw/reach_results.jsonl
        write_csv([json.loads(line) for line in open(os.path.join(RAW, "reach_results.jsonl"))])
    else:
        main()
