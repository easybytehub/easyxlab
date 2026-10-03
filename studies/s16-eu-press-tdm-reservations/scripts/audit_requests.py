#!/usr/bin/env python3
"""Check the request log of the scan (data/raw/requests.tsv) against the access rules:
(1) the first request to every host is /robots.txt; (2) no request other than /robots.txt went to
a host whose robots.txt carries a natural-language prohibition; (3) list the hosts whose first request was not /robots.txt.
Requests are counted by URL and time, whether or not their response status was later removed (D2,
D4, D7). Pacing is enforced in politefetch._pace; the main scan's log lines carry completion times
(D3), the D5 re-scan's lines carry start times. Writes data/request_audit.json."""
import csv, json, os
from collections import defaultdict, Counter
from urllib.parse import urlsplit
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "data", "raw", "requests.tsv"))]
recs = list(csv.DictReader(open(os.path.join(ROOT, "data", "records.csv"))))
nl_hosts = {r["host"] for r in recs if r["robots_state"] == "nl_prohibition"}
by = defaultdict(list)
for t, m, url, st in log:
    by[(urlsplit(url).hostname or "").lower()].append((t, url))
first_not_robots = [h for h, L in by.items() if urlsplit(L[0][1]).path != "/robots.txt"]
nl_violations = [(h, t, u) for h in nl_hosts for t, u in by.get(h, []) if urlsplit(u).path != "/robots.txt"]
_dev = {}
for name in ("deviation_d2.json", "deviation_d4.json", "deviation_d7.json"):
    pth = os.path.join(ROOT, "data", name)
    if os.path.exists(pth):
        j = json.load(open(pth))
        for h in j.get("hosts_data_deleted", j.get("hosts", [])):
            _dev.setdefault(h, []).append(name.split("_")[1].split(".")[0])
def _which(h, t):
    d = _dev.get(h, [])
    if "d7" in d and t >= "2026-10-03T11:55":
        return "D7"
    return "D2" if "d2" in d else ("D4" if "d4" in d else "other")
by_dev = Counter(_which(h, t) for h, t, u in nl_violations)
out = dict(requests=len(log), hosts_contacted=len(by), first_request_not_robots=len(first_not_robots), first_request_not_robots_hosts=sorted(first_not_robots),
           requests_to_those_hosts=sum(len(by[h]) for h in first_not_robots),
           nl_prohibition_hosts=len(nl_hosts), requests_beyond_robots_to_nl_hosts=len(nl_violations),
           requests_beyond_robots_to_nl_hosts_by_deviation=dict(sorted(by_dev.items())),
           status_removed_lines=sum(1 for _, _, _, st in log if st == ""),
           breach_requests_by_deviation={"D1 (before that host's robots.txt)": sum(len(by[h]) for h in first_not_robots),
                                         "D2": json.load(open(os.path.join(ROOT, "data", "deviation_d2.json")))["requests_beyond_robots_to_them"],
                                         "D4": json.load(open(os.path.join(ROOT, "data", "deviation_d4.json")))["requests_beyond_robots"],
                                         "D7": json.load(open(os.path.join(ROOT, "data", "deviation_d7.json")))["requests_beyond_robots"]},
           max_requests_one_host=max(len(L) for L in by.values()),
           status_counts=dict(Counter(st if not st.isdigit() else st[0] + "xx" for _, _, _, st in log)))
for name in ("deviation_d2.json", "deviation_d4.json", "deviation_d5.json", "deviation_d7.json"):
    p = os.path.join(ROOT, "data", name)
    if os.path.exists(p):
        out[name.split(".")[0]] = {k: v for k, v in json.load(open(p)).items() if k not in ("hosts_data_deleted", "request_times_utc", "evidence")}
out["note"] = ("'requests_beyond_robots_to_nl_hosts' counts, by URL and time, every request beyond robots.txt to a host "
               "that is robots-only in the final records (detector v4), including those whose response status was "
               "removed; each is a breach of the study's access rule, declared as D2, D4 or D7.")
json.dump(out, open(os.path.join(ROOT, "data", "request_audit.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
