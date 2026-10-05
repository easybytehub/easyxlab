#!/usr/bin/env python3
"""S24: rebuild data/prior_work_search.csv from the search log in work/src/search/log.jsonl (git-ignored).

Each line of the log is one search (engine, query, UTC time, HTTP status, number of results, results).
A web-search tool was also tried once and refused: its session quota (200 searches) was used up; that
attempt is listed with engine "websearch (quota exhausted)".
"""
from __future__ import annotations

import csv
import json
import sys

from s24lib import D, R

LOG = R / "work" / "src" / "search" / "log.jsonl"


def main():
    if not LOG.exists():
        print(f"{LOG} not found: nothing to rebuild (data/prior_work_search.csv kept as is)")
        return 0
    rows = [{"engine": "websearch (quota exhausted)", "query": "Banco de España esfuerzo alquiler jóvenes emancipación tasa de sobreesfuerzo inquilinos selección",
             "time_utc": "2026-10-04", "http": "", "results": 0, "top_results": ""}]
    with open(LOG, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            rows.append({"engine": e["engine"], "query": e["query"], "time_utc": e["time"], "http": e["http"], "results": e["n"],
                         "top_results": " | ".join(r["url"] for r in e["results"][:5])})
    with open(D / "prior_work_search.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} searches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
