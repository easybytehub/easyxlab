#!/usr/bin/env python3
"""Was each request of the first scan (2026-10-02, scanner version 1) allowed by robots.txt?

The first scanner ignored robots.txt files served with an HTML Content-Type, never checked
robots.txt for /.well-known/security.txt, and did not check the robots.txt of hosts it was
redirected to. This module re-decides every recorded request with RFC 9309 rules, using:

  * for the entity's own host: the robots.txt state the first scan saw (a 5xx or network
    error then meant complete disallow, a 4xx no restrictions); when that state was a 200,
    the rules come from the re-read of the same file later that day (robots_snapshot.jsonl);
  * for any other host (redirect targets, statements on another host, security.txt and
    llms.txt on the final host): the re-read, since the first scan did not read it.

Decisions: "allowed", "disallowed", or "unverifiable" (the re-read failed or disagreed in kind
with what the first scan saw). Anything not "allowed" is discarded.

The product token checked is the one the first scan sent, "EasyByteLab-research".
"""
import os, sys
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import robots9309 as R  # noqa: E402

OLD_TOKEN = "EasyByteLab-research"
ORDER = {"allowed": 0, "unverifiable": 1, "disallowed": 2}


def host_of(u):
    return (urlsplit(u or "").hostname or "").lower()


def path_of(u):
    p = urlsplit(u)
    return (p.path or "/") + (("?" + p.query) if p.query else "")


def scan_time_state(rec):
    """robots.txt state of the entity's own host as scanner v1 saw it."""
    err, st = rec.get("robots_error"), rec.get("robots_status")
    if err:
        return "unreachable"
    if isinstance(st, int):
        if 200 <= st < 300:
            return "ok"            # scanner v1 treated 2xx other than 200 as "no restrictions"
        if 400 <= st < 500:
            return "unavailable"
    return "unreachable"


def decide(host, url, own_host, own_state, snap):
    s = snap.get(host)
    if host == own_host:
        if own_state == "unreachable":
            return "disallowed"           # RFC 9309 s. 2.3.1.4: complete disallow
        if own_state == "unavailable":
            return "allowed"              # s. 2.3.1.3
        if s and s["state"] == "ok":
            return "allowed" if R.allowed(s["groups"], OLD_TOKEN, url) else "disallowed"
        return "unverifiable"
    if not s:
        return "unverifiable"
    if s["state"] == "ok":
        return "allowed" if R.allowed(s["groups"], OLD_TOKEN, url) else "disallowed"
    if s["state"] == "unavailable":
        return "allowed"
    return "unverifiable"


def requests_of(rec, p2=None):
    """(kind, host, url) of every non-robots request that scanner v1 recorded for an entity."""
    H = rec["host"]
    out = []
    if rec.get("home_status") not in ("robots_disallowed", "host_budget") and "home_final" in rec:
        out.append(("home", H, f"https://{H}{path_of(rec['url'])}"))
        fin = rec.get("home_final") or ""
        if fin and fin != f"https://{H}{path_of(rec['url'])}":
            out.append(("home", host_of(fin), fin))
    if "sectxt_status" in rec and rec.get("sectxt_status") != "host_budget" and rec.get("sectxt_host"):
        h = rec["sectxt_host"]
        out.append(("sectxt", h, f"https://{h}/.well-known/security.txt"))
    if isinstance(rec.get("stmt_status"), int) and rec.get("acc_url"):
        out.append(("stmt", host_of(rec["acc_url"]), rec["acc_url"]))
    if isinstance(rec.get("llms_status"), int):
        fh = rec.get("home_final_host") or H
        out.append(("llms", fh, f"https://{fh}/llms.txt"))
    if p2 and "sectxt_status" in p2:
        out.append(("sectxt_pass2", H, f"https://{H}/.well-known/security.txt"))
    return out


def audit(rec, p2, snap):
    """{kind: worst decision} for one entity of the first scan."""
    st = scan_time_state(rec)
    res = {}
    for kind, h, url in requests_of(rec, p2):
        d = decide(h, url, rec["host"], st, snap)
        if ORDER[d] > ORDER[res.get(kind, "allowed")]:
            res[kind] = d
        else:
            res.setdefault(kind, d)
    return res
