#!/usr/bin/env python3
"""S22: summarise every prior-work search into data/prior_work_search.csv.

Inputs are the search logs kept in work/ (git-ignored): work/prior/searches.csv (DuckDuckGo HTML, the
failed WebSearch attempts, first Crossref/OpenAlex queries), work/prior/extra_search.json (Crossref,
OpenAlex, GitHub) and work/asylum/ddg_log.jsonl. Without them the published CSV is left as it is.
GitHub owners are withheld; only counts are kept.
"""
from __future__ import annotations

import csv
import json
import sys

from s22lib import DATA, WORK

CITED = {"10.1016/j.jpubeco.2026.105577", "10.3386/w33655", "10.26754/ojs_ried/ijds.11169",
         "10.1080/10511482.2025.2599125", "10.4324/9781003274056-8"}


def main() -> int:
    a, b, c = WORK / "prior" / "searches.csv", WORK / "prior" / "extra_search.json", WORK / "asylum" / "ddg_log.jsonl"
    if not (a.exists() and b.exists()):
        print("work/prior logs not present: data/prior_work_search.csv left unchanged")
        return 0
    rows = []
    with open(a, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r.get("error") or "").startswith(("row is a note", "note:")):
                continue
            rows.append({"source": r["source"], "query": r["query"], "time_utc": r["time_utc"][:19] + "Z",
                         "results_reported": r["results_reported"], "screened": r["screened"],
                         "relevant_cited": r["relevant_cited"], "error": r["error"]})
    for o in json.loads(b.read_text(encoding="utf-8")):
        cited = [t.get("doi") or "" for t in o["top"] if any(k in (t.get("doi") or "") for k in CITED)]
        rows.append({"source": o["source"], "query": o["query"], "time_utc": o["time"], "results_reported": o["n"],
                     "screened": min(20, len(o["top"])) if o["source"] != "github repos" else len(o["top"]),
                     "relevant_cited": " ".join(sorted(set(cited))), "error": o["error"][:60] if o["source"] != "github repos" else ""})
    if c.exists():
        for line in c.read_text(encoding="utf-8").splitlines():
            o = json.loads(line)
            rows.append({"source": "duckduckgo-html (reception series)", "query": o["query"], "time_utc": o["time"][:19] + "Z",
                         "results_reported": o["n"], "screened": o["n"], "relevant_cited": "", "error": ""})
    rows.sort(key=lambda r: r["time_utc"])
    with open(DATA / "prior_work_search.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    print(f"wrote data/prior_work_search.csv ({len(rows)} searches)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
