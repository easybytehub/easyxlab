#!/usr/bin/env python3
"""Comment detectors over the stored robots.txt bodies, and the deviations that follow from them.
No network. Replaces apply_detector_v2.py (deviation D2), whose effect is kept.

    python3 scripts/apply_detectors.py prepare   # once: D4 deletion, request-log scrub, D5 re-scan list
    python3 scripts/apply_detectors.py merge     # once: put the D5 re-scan records in place of the old ones
    python3 scripts/apply_detectors.py           # idempotent (run.sh): v3 flags + verdicts for every record

Rules (METHOD.md, D2/D4/D5):
  * D2 hosts (92) whose v3 flag is still a general prohibition stay robots-only; their deleted data
    are never restored. D2 hosts that v3 no longer flags are re-read in the D5 re-scan.
  * D4: a host read in the scan that v3 flags as a general prohibition (actu.fr) has every field
    beyond robots.txt deleted and is classified on robots.txt alone.
  * Request log: for D2 and D4 hosts, the response status of every request beyond robots.txt is
    removed; URL and time are kept as the accountability record.
"""
import base64
import csv
import json
import os
import sys
from urllib.parse import urlsplit

import nlcomments as N
import optout_check as O

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "scan.jsonl")
LOG = os.path.join(ROOT, "data", "raw", "requests.tsv")
D = os.path.join(ROOT, "data")


def load():
    return [json.loads(line) for line in open(RAW)]


def save(recs):
    with open(RAW + ".tmp", "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    os.replace(RAW + ".tmp", RAW)


def body_of(r):
    return base64.b64decode(r["_raw"]["robots_b64"]) if r["_raw"].get("robots_b64") else b""


def flags(r, v):
    b = body_of(r)
    if not b:
        return dict(nl_reservation=False, nl_prohibition=False, nl_reservation_evidence="", nl_prohibition_evidence="")
    return N.scan(b, v)


def delete_beyond_robots(r, tag):
    r["robots"]["state"] = "nl_prohibition"
    r["read"] = dict(tdmrep=False, home=False, llms=False, reason="not read: natural-language prohibition",
                     deleted_after_collection=tag)
    r["tdmrep_file"] = dict(state="deleted_" + tag, root=None, any_reservation=False)
    r["home"] = dict(fetched=False, reason="deleted_" + tag)
    r["llms_txt"] = dict(state="deleted_" + tag)


def apply_v3(r):
    """Current detector version (N.VERSION, 4 since D7) over the stored body."""
    rb = r["robots"]
    nl = flags(r, N.VERSION)
    if "nl_v2" not in rb and "nl_v1" in rb:
        f2 = flags(r, 2)
        rb["nl_v2"] = dict(reservation=bool(f2["nl_reservation"]), prohibition=bool(f2["nl_prohibition"]))
    rb.update(nl_reservation=bool(nl["nl_reservation"]), nl_reservation_evidence=nl["nl_reservation_evidence"],
              nl_prohibition=bool(nl["nl_prohibition"]), nl_prohibition_evidence=nl["nl_prohibition_evidence"],
              detector_version=N.VERSION)
    return nl


def prepare():
    recs = load()
    d2 = set(json.load(open(os.path.join(D, "deviation_d2.json")))["hosts_data_deleted"])
    changes, d4, rescan = [], [], []
    for r in recs:
        if "robots" not in r:
            continue
        rb = r["robots"]
        old_p = rb["state"] == "nl_prohibition"
        old_ev = rb.get("nl_prohibition_evidence", "")
        nl = apply_v3(r)
        if rb["state"] == "ok" and nl["nl_prohibition"]:
            delete_beyond_robots(r, "d4")
            d4.append((r["host"], nl["nl_prohibition_evidence"]))
        elif old_p and not nl["nl_prohibition"]:
            rescan.append(r["host"])
            changes.append(dict(host=r["host"], was_d2=int(r["host"] in d2), old_evidence=old_ev[:120],
                                v3_reservation_evidence=nl["nl_reservation_evidence"][:80]))
        r["verdict"] = O.verdict(r)
    save(recs)
    d4h = {h for h, _ in d4}
    scrub = d2 | d4h
    lines, n_scrubbed, d4_req = [], 0, []
    for line in open(LOG):
        p = line.rstrip("\n").split("\t")
        h = (urlsplit(p[2]).hostname or "").lower()
        if h in scrub and urlsplit(p[2]).path != "/robots.txt" and p[3] != "":
            p[3] = ""
            n_scrubbed += 1
            if h in d4h:
                d4_req.append(p[0])
        lines.append("\t".join(p) + "\n")
    open(LOG, "w").writelines(lines)
    json.dump(dict(hosts=sorted(d4h), evidence=dict(d4), requests_beyond_robots=len(d4_req),
                   request_times_utc=d4_req,
                   note="read in the scan although robots.txt comments prohibit automated access (missed by "
                        "detectors v1 and v2: list-style notice); data deleted, response status removed from the log."),
              open(os.path.join(D, "deviation_d4.json"), "w"), indent=1, ensure_ascii=False)
    with open(os.path.join(D, "d5_status_changes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["host", "was_d2", "old_evidence", "v3_reservation_evidence"], lineterminator="\n")
        w.writeheader()
        w.writerows(changes)
    open(os.path.join(ROOT, "work", "rescan_hosts.txt"), "w").write("\n".join(rescan) + "\n")
    print(f"D4: {sorted(d4h)} ({len(d4_req)} requests); status removed from {n_scrubbed} log lines; "
          f"D5 re-scan list: {len(rescan)} hosts ({sum(c['was_d2'] for c in changes)} from D2)")


def merge():
    recs = load()
    new = {}
    for line in open(os.path.join(ROOT, "data", "raw", "rescan_d5.jsonl")):
        r = json.loads(line)
        r["rescan_d5"] = True
        new[r["host"]] = r
    times = sorted(r["checked_utc"] for r in new.values())
    out = [new.get(r["host"], r) for r in recs]
    for r in out:
        if r.get("rescan_d5") and "robots" in r:
            apply_v3(r)
            r["verdict"] = O.verdict(r)
    save(out)
    st = {}
    for r in new.values():
        st[r["robots"]["state"]] = st.get(r["robots"]["state"], 0) + 1
    json.dump(dict(n_hosts=len(new), first_check_utc=times[0], last_check_utc=times[-1], robots_states=st,
                   note="targeted re-scan (frozen fetch rules: robots.txt first, 1 request/s/host) of the hosts "
                        "that detector v3 no longer flags as a general prohibition"),
              open(os.path.join(D, "deviation_d5.json"), "w"), indent=1)
    print(len(new), times[0], times[-1], st)


def d7():
    """Deviation D7 (re-review): hosts read in the D5 re-scan that detector v4 flags as a general
    prohibition. Their beyond-robots data are deleted and the response status of those requests is
    removed from the log (URL and time kept)."""
    recs = load()
    hit = []
    for r in recs:
        if "robots" not in r:
            continue
        nl = apply_v3(r)
        if r["robots"]["state"] == "ok" and nl["nl_prohibition"]:
            if not r.get("rescan_d5"):
                sys.exit(f"{r['host']}: newly prohibited but not from the D5 re-scan; stop and report")
            delete_beyond_robots(r, "d7")
            hit.append((r["host"], nl["nl_prohibition_evidence"]))
        r["verdict"] = O.verdict(r)
    save(recs)
    hs = {h for h, _ in hit}
    d5 = json.load(open(os.path.join(D, "deviation_d5.json")))
    lines, total, beyond, scrubbed = [], 0, 0, 0
    for line in open(LOG):
        p = line.rstrip("\n").split("\t")
        h = (urlsplit(p[2]).hostname or "").lower()
        if h in hs and p[0] >= d5["first_check_utc"][:19]:
            total += 1
            if urlsplit(p[2]).path != "/robots.txt":
                beyond += 1
                if p[3] != "":
                    p[3] = ""
                    scrubbed += 1
        lines.append("\t".join(p) + "\n")
    open(LOG, "w").writelines(lines)
    prev = {}
    pth = os.path.join(D, "deviation_d7.json")
    if os.path.exists(pth):
        prev = json.load(open(pth))
    out = dict(hosts=sorted(hs | set(prev.get("hosts", []))), n_hosts=len(hs | set(prev.get("hosts", []))),
               requests_in_rescan=max(total, prev.get("requests_in_rescan", 0)),
               requests_beyond_robots=max(beyond, prev.get("requests_beyond_robots", 0)),
               evidence={**prev.get("evidence", {}), **{h: e[:120] for h, e in hit}},
               note="read in the D5 re-scan although their robots.txt comments prohibit automated collection "
                    "(general prohibition with an open clause); the study's instructions classed the notice as "
                    "purpose-specific; data deleted, response status removed from the log, URL and time kept.")
    json.dump(out, open(pth, "w"), indent=1, ensure_ascii=False)
    print(out["n_hosts"], "hosts;", out["requests_in_rescan"], "requests in the re-scan,", out["requests_beyond_robots"],
          "beyond robots.txt; statuses removed now:", scrubbed)


def apply_all():
    recs = load()
    for r in recs:
        if "robots" not in r:
            continue
        nl = apply_v3(r)
        if r["robots"]["state"] == "ok" and nl["nl_prohibition"]:
            sys.exit(f"{r['host']}: read although v3 finds a general prohibition; run 'prepare' first")
        r["verdict"] = O.verdict(r)
    save(recs)
    print(len(recs), "records: v3 flags and verdicts applied")


if __name__ == "__main__":
    {"prepare": prepare, "merge": merge, "d7": d7}.get(sys.argv[1] if len(sys.argv) > 1 else "", apply_all)()
