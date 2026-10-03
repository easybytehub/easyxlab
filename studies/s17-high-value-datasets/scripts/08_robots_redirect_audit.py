# SPDX-License-Identifier: Apache-2.0
"""Review item #6 / deviation D5: hosts whose robots.txt answered 3xx in the 2026-10-03 run were treated as
allow-all. Re-read their robots.txt following redirects (RFC 9309 2.3.1.2) and check whether any request
we made to them would have been disallowed. Reads work/requests.log; writes data/robots_redirect_audit.json
(host names and counts only)."""
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "work", "requests.log")


def key(u):
    p = urllib.parse.urlsplit(u)
    return f"{p.scheme}://{p.netloc}".lower()


lines = [l.rstrip("\n").split("\t") for l in open(LOG)]
first_robots, requested = {}, {}
for ts, m, st, url, *rest in lines:
    k = key(url)
    if url.endswith("/robots.txt"):
        first_robots.setdefault(k, st)
    elif st != "SKIP" and ts < "2026-10-03T11:25":  # requests of the original run only
        requested.setdefault(k, []).append(url)
redir = sorted(k for k, st in first_robots.items() if st in ("301", "302", "303", "307", "308"))
out = {"hosts_robots_3xx": len(redir), "hosts": []}
for k in redir:
    st = fetch.robots_for(k + "/")
    urls = requested.get(k, [])
    dis = [u for u in urls if st.parser is not None and not (st.parser.can_fetch(fetch.UA, u) and st.parser.can_fetch("*", u))]
    out["hosts"].append({"host": urllib.parse.urlsplit(k).hostname, "robots_after_redirects": st.note,
                         "status": st.status, "requests_made": len(urls), "would_be_disallowed": len(dis)})
out["requests_made_total"] = sum(h["requests_made"] for h in out["hosts"])
out["would_be_disallowed_total"] = sum(h["would_be_disallowed"] for h in out["hosts"])
out["robots_unreadable_after_redirects"] = sum(1 for h in out["hosts"] if h["status"] is None or h["robots_after_redirects"] in ("server-error",) or str(h["robots_after_redirects"]).startswith("error"))
json.dump(out, open(os.path.join(ROOT, "data", "robots_redirect_audit.json"), "w"), indent=1)
print({k: v for k, v in out.items() if k != "hosts"})
for h in out["hosts"]:
    if h["would_be_disallowed"] or h["status"] is None:
        print(h)
