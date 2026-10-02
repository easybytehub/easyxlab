#!/usr/bin/env python3
"""Builds the study-level tables in data/ from the per-site outputs of ai-bot-verify
(data/logs/<label>/) and cf_declared_bots.py (data/cloudflare/). Aggregates only.
Sites are referred to by public label only (site-a, site-b, site-c); the mapping to real
domains is private (see scripts/run_study.py)."""
import csv
import datetime as dt
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "data"
SITES = ["site-a", "site-b", "site-c"]
VERDICTS = ("verified", "spoofed", "unverifiable", "indeterminate")


def rows(p):
    return list(csv.DictReader(open(p))) if Path(p).exists() else []


def write(name, rs):
    if rs:
        with open(D / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rs[0].keys()))
            w.writeheader()
            w.writerows(rs)


# 1. verification rate per declared bot (origin logs; per site and pooled as "ALL")
per = defaultdict(Counter)
meta = {}
for s in SITES:
    for r in rows(D / "logs" / s / "by_bot.csv"):
        for key in ((s, r["bot"]), ("ALL", r["bot"])):
            per[key][r["verdict"]] += int(r["requests"])
        meta[r["bot"]] = (r["operator"], r["purpose"], r["method"])
out = []
for (s, b), c in sorted(per.items(), key=lambda kv: (kv[0][0] != "ALL", kv[0][0], -sum(kv[1].values()))):
    tot = sum(c.values())
    testable = c["verified"] + c["spoofed"]
    out.append({"site": s, "bot": b, "operator": meta[b][0], "purpose": meta[b][1], "method": meta[b][2],
                "requests": tot, "verified": c["verified"], "spoofed": c["spoofed"],
                "unverifiable": c["unverifiable"], "indeterminate": c["indeterminate"],
                "pct_verified_of_testable": round(100 * c["verified"] / testable, 1) if testable else "",
                "pct_spoofed_of_all": round(100 * c["spoofed"] / tot, 1) if tot else ""})
write("verification_by_bot.csv", out)

# 2. purpose-level summary (pooled)
pur = defaultdict(Counter)
for r in out:
    if r["site"] == "ALL":
        for v in VERDICTS:
            pur[r["purpose"]][v] += r[v]
write("verification_by_purpose.csv",
      [{"purpose": p, **{v: c[v] for v in VERDICTS}, "pct_spoofed": round(100 * c["spoofed"] / sum(c.values()), 1)}
       for p, c in sorted(pur.items(), key=lambda kv: -sum(kv[1].values()))])

# 3. spoofing sources by ASN and heuristic network type (pooled; counts only)
asn = defaultdict(Counter)
asninfo = {}
for s in SITES:
    for r in rows(D / "logs" / s / "by_asn.csv"):
        k = r["asn"] or "none"
        for col in ("spoofed_requests", "unverifiable_requests", "indeterminate_requests"):
            asn[k][col] += int(r[col])
        asn[k]["unique_ips_summed_over_sites"] += int(r["unique_ips"])
        asninfo[k] = (r["as_name"], r["country"], r["net_type"])
asn_rows = [{"asn": k, "as_name": asninfo[k][0], "country": asninfo[k][1], "net_type": asninfo[k][2], **c}
            for k, c in sorted(asn.items(), key=lambda kv: -kv[1]["spoofed_requests"])]
write("spoofing_by_asn.csv", asn_rows)
nt = defaultdict(Counter)
for r in asn_rows:
    nt[r["net_type"]]["spoofed_requests"] += r["spoofed_requests"]
    nt[r["net_type"]]["asns_with_spoofing"] += 1 if r["spoofed_requests"] else 0
write("spoofing_by_net_type.csv", [{"net_type": k, **c} for k, c in sorted(nt.items(), key=lambda kv: -kv[1]["spoofed_requests"])])

# 4. behaviour of sources (pooled). Per-site files count unique IPs per (bot, verdict);
# summing them across bots and sites counts (site, bot, IP) TRIPLES, not distinct IPs, so
# the pooled columns say so. Distinct IPs per verdict (summed over sites, an upper bound
# because one IP may hit several sites) are in distinct_ips_upper_bound.
beh = defaultdict(Counter)
for s in SITES:
    for r in rows(D / "logs" / s / "behaviour.csv"):
        for k, v in r.items():
            if k.startswith("ips_"):
                beh[r["verdict"]]["site_bot_ip_triples_" + k[4:]] += int(v)
            elif k.startswith("req_"):
                beh[r["verdict"]]["requests_" + k[4:]] += int(v)
distinct = Counter()
for s in SITES:
    p = D / "logs" / s / "summary.json"
    if p.exists():
        for v, n in json.loads(p.read_text())["unique_ips_by_verdict"].items():
            distinct[v] += n
write("behaviour_by_verdict.csv",
      [{"verdict": v, "distinct_ips_upper_bound": distinct[v], **c} for v, c in beh.items()])

# 5. what is requested, by verdict (pooled)
cat = defaultdict(Counter)
for s in SITES:
    for r in rows(D / "logs" / s / "by_category.csv"):
        cat[r["verdict"]][r["category"]] += int(r["requests"])
write("paths_by_verdict.csv", [{"verdict": v, "category": c, "requests": n, "share": round(n / sum(cc.values()), 3)}
                               for v, cc in cat.items() for c, n in cc.most_common()])

# 6. time: hour-of-day profile, day concentration and weekly series (site-a, the only long window)
hrs = defaultdict(Counter)
for r in rows(D / "logs" / "site-a" / "hours.csv"):
    hrs[r["verdict"]][int(r["hour_utc"])] += int(r["requests"])
write("hours_by_verdict_site-a.csv", [{"hour_utc": h, **{v: hrs[v][h] for v in VERDICTS}} for h in range(24)])
days = defaultdict(Counter)
for r in rows(D / "logs" / "site-a" / "days.csv"):
    days[r["verdict"]][r["date"]] += int(r["requests"])
conc = []
for v, c in days.items():
    vals = sorted(c.values(), reverse=True)
    tot = sum(vals)
    conc.append({"verdict": v, "active_days": len(vals), "requests": tot,
                 "share_top5_days": round(sum(vals[:5]) / tot, 3), "max_day": vals[0]})
write("day_concentration_site-a.csv", conc)
weekly = defaultdict(Counter)
for v, c in days.items():
    for d, n in c.items():
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        weekly[f"{y}-W{w:02d}"][v] += n
write("weekly_site-a.csv", [{"iso_week": w, **{v: c[v] for v in VERDICTS}} for w, c in sorted(weekly.items())])

# 7. range files used (metadata + hash, not the prefixes)
rf = []
for f in sorted((D / "raw" / "cache").glob("*.json")):
    j = json.loads(f.read_text())
    rf.append({"key": f.stem, "creationTime": j.get("creationTime"), "prefixes": len(j.get("prefixes", [])),
               "sha256": hashlib.sha256(f.read_bytes()).hexdigest()[:16]})
write("range_files_used.csv", rf)

# 8. edge vs origin, same 30-day window (labels on both sides)
cmp = defaultdict(Counter)
for r in rows(D / "cloudflare" / "by_bot.csv"):
    cmp[(r["zone"], r["verdict"])]["edge"] += int(r["requests"])
for s in SITES:
    for r in rows(D / "raw" / "cmp" / s / "by_bot.csv"):
        cmp[(s, r["verdict"])]["origin"] += int(r["requests"])
write("edge_vs_origin_30d.csv", [{"site": z, "verdict": v, "edge_requests": c["edge"], "origin_requests": c["origin"]}
                                 for (z, v), c in sorted(cmp.items())])

for r in out:
    if r["site"] == "ALL":
        print(f"{r['bot']:<20}{r['requests']:>6}{r['verified']:>6}{r['spoofed']:>6}{r['unverifiable']:>5}"
              f"{r['indeterminate']:>5}  {r['pct_verified_of_testable']}")
