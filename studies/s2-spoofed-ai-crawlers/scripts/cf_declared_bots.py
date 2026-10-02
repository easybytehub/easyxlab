#!/usr/bin/env python3
"""cf_declared_bots.py — the same verification as ai-bot-verify, applied to Cloudflare's
edge view (GraphQL Analytics, httpRequestsAdaptiveGroups) instead of the origin log.

Why a second view: the origin only sees what Cloudflare let through, and the sites' nginx
does not log some scanner paths (it closes them with 444 and `access_log off`). The edge
sees every request, plus what Cloudflare did with it (securityAction).

Reads a Cloudflare API token (Zone Analytics: Read) from an env file. The token is never
printed. Client IPs are used in memory for range/FCrDNS checks and dropped; only
aggregates are written, behind the same privacy guard as ai-bot-verify.

Usage:
    cf_declared_bots.py --env /path/to/.env --zones a.com b.com --site-map map.json --days 30 --out data/cloudflare
"""
import argparse
import datetime as dt
import json
import re
import socket
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_bot_verify as abv  # noqa: E402

# (kept for reference; no longer used as a server-side filter)
TOKENS = ["gptbot", "oai-searchbot", "chatgpt-user", "oai-adsbot", "claudebot", "claude-user",
          "claude-searchbot", "claude-web", "anthropic-ai", "claude-code", "perplexitybot",
          "perplexity-user", "mistralai", "duckassistbot", "duckduckbot", "ccbot", "applebot",
          "googlebot", "google-", "googleother", "adsbot-google", "mediapartners", "bingbot",
          "bingpreview", "msnbot", "adidxbot", "yandex", "amazonbot", "amzn-", "bytespider",
          "meta-external", "facebookbot", "feedfetcher"]
# Free-plan zones expose no ASN fields (clientAsn/clientASNDescription are refused), so the
# ASN of NON-verified IPs is looked up afterwards via Team Cymru, as in ai-bot-verify.
DIMS = ["userAgent", "clientIP", "clientRequestPath", "edgeResponseStatus", "securityAction"]
OPTIONAL = {"clientRequestPath", "edgeResponseStatus", "securityAction"}


def token_from_env(path: Path) -> str:
    m = re.search(r"^CLOUDFLARE_API_TOKEN=(.+)$", path.read_text(), re.M)
    if not m:
        sys.exit("CLOUDFLARE_API_TOKEN not found in env file")
    return m.group(1).strip().strip("\"'")


def api(tok, path, body=None):
    req = urllib.request.Request("https://api.cloudflare.com/client/v4" + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                return {"errors": [{"message": type(e).__name__}]}
            time.sleep(3)


def fetch_zone_day(tok, zone_id, start, end):
    """All request groups for [start, end), UNFILTERED: GraphQL's userAgent_like is
    case-sensitive (a "%googlebot%" filter silently returns 0 rows for "Googlebot"), so the
    bot match is done locally with the same case-insensitive matcher as ai-bot-verify.
    Splits the window in halves when the 10,000-group limit is reached."""
    q = ('{viewer{zones(filter:{zoneTag:"%s"}){httpRequestsAdaptiveGroups(limit:10000,'
         'filter:{datetime_geq:"%s",datetime_lt:"%s"}){count avg{sampleInterval} dimensions{%s}}}}}'
         % (zone_id, start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ"), " ".join(DIMS)))
    r = api(tok, "/graphql", {"query": q})
    if r.get("errors"):
        msg = r["errors"][0].get("message", "")
        m = re.search(r"access to the field '(\w+)'", msg)
        if m:   # drop a field the plan does not expose and retry
            for d in list(DIMS):
                if d.lower() == m.group(1).lower() and d in OPTIONAL:
                    DIMS.remove(d)
                    return fetch_zone_day(tok, zone_id, start, end)
        return None, [e.get("message", "")[:200] for e in r["errors"]]
    rows = r["data"]["viewer"]["zones"][0]["httpRequestsAdaptiveGroups"]
    if len(rows) >= 10000 and (end - start) > dt.timedelta(minutes=30):
        mid = start + (end - start) / 2
        r1, e1 = fetch_zone_day(tok, zone_id, start, mid)
        r2, e2 = fetch_zone_day(tok, zone_id, mid, end)
        return (r1 or []) + (r2 or []), e1 + e2
    return rows, []


def cymru_asn_names(asns):
    """ASN -> registered name, via Team Cymru (ASN numbers only; no IPs are sent)."""
    out = {}
    if not asns:
        return out
    payload = "begin\nverbose\n" + "\n".join(f"AS{a}" for a in asns) + "\nend\n"
    try:
        with socket.create_connection(("whois.cymru.com", 43), timeout=60) as s:
            s.sendall(payload.encode())
            buf = b""
            while True:
                d = s.recv(65536)
                if not d:
                    break
                buf += d
        for line in buf.decode(errors="replace").splitlines():
            p = [x.strip() for x in line.split("|")]
            if len(p) >= 5 and p[0].isdigit():
                out[int(p[0])] = (p[-1], p[1])
    except OSError:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", type=Path, required=True)
    ap.add_argument("--zones", nargs="+", required=True)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cache-dir", type=Path, default=Path.home() / ".cache" / "ai-bot-verify")
    ap.add_argument("--exclude-ip-file", type=Path)
    ap.add_argument("--site-map", type=Path, required=True,
                    help="JSON {zone domain: public label}; outputs carry only the label")
    ap.add_argument("--withhold-asn-file", type=Path)
    args = ap.parse_args()
    tok = token_from_env(args.env)
    label = json.loads(args.site_map.read_text())
    withhold = set()
    if args.withhold_asn_file:
        withhold = {x.strip() for x in args.withhold_asn_file.read_text().splitlines()
                    if x.strip() and not x.startswith("#")}
    excl = set(args.exclude_ip_file.read_text().split()) if args.exclude_ip_file else set()

    zones = {z["name"]: z["id"] for z in (api(tok, "/zones?per_page=50").get("result") or [])}
    ranges = abv.RangeStore(args.cache_dir)
    resolver = abv.Resolver()
    today = dt.datetime.now(dt.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    sampled = defaultdict(Counter)   # zone -> raw sampled count vs count x sampleInterval
    rows_all = []      # (zone, day, count, ua, ip, asn, path, status, action)  -- memory only
    errors = []
    for name in args.zones:
        zid = zones.get(name)
        if not zid:
            errors.append(f"{label.get(name, '?')}: zone not visible to token")
            continue
        for d in range(args.days, -1, -1):
            start = today - dt.timedelta(days=d)
            end = start + dt.timedelta(days=1)
            if d == args.days:
                start = start + dt.timedelta(hours=2)   # stay inside the retention limit
            rows, errs = fetch_zone_day(tok, zid, start, end)
            if errs:
                errors.append(f"{label[name]} {start.date()}: {errs[0]}")
                continue
            for r in rows:
                dm = r["dimensions"]
                si = (r.get("avg") or {}).get("sampleInterval") or 1
                sampled[label[name]]["rows"] += r["count"]
                sampled[label[name]]["estimated"] += r["count"] * si
                if abv.match_bot(dm["userAgent"] or "") is None:
                    continue
                sampled[label[name] + "|declared-bots"]["rows"] += r["count"]
                sampled[label[name] + "|declared-bots"]["estimated"] += r["count"] * si
                if si > 1:
                    sampled[label[name] + "|declared-bots"]["rows_in_sampled_groups"] += r["count"]
                if dm["clientIP"] in excl:
                    continue
                rows_all.append((label[name], start.date().isoformat(), r["count"], dm["userAgent"] or "",
                                 dm["clientIP"], None, dm.get("clientRequestPath") or "/",
                                 dm.get("edgeResponseStatus") or 0, dm.get("securityAction") or "unknown"))

    # FCrDNS for rDNS-verifiable bots outside published ranges, in parallel
    import concurrent.futures as cf
    need = set()
    for z, day, n, ua, ip, asn, path, st, act in rows_all:
        b = abv.match_bot(ua)
        if b and b.rdns and not b.never_a_ua:
            if not any(ranges.load(k) and abv.in_nets(ip, ranges.load(k)) for k in b.ranges):
                need.add((ip, b.rdns))
    with cf.ThreadPoolExecutor(max_workers=32) as ex:
        list(ex.map(lambda t: resolver.fcrdns(*t), need))

    nonver = sorted({ip for z, day, n, ua, ip, *_ in rows_all if abv.match_bot(ua) and
                     abv.verdict_for(abv.match_bot(ua), ip, ranges, resolver) != "verified"})
    ipasn = abv.cymru_asn(nonver)
    rows_all = [(z, day, n, ua, ip, (ipasn.get(ip) or {}).get("asn"), path, st, act)
                for z, day, n, ua, ip, _a, path, st, act in rows_all]

    by_bot = defaultdict(Counter)        # (zone, bot, verdict) -> requests / ips
    ips = defaultdict(set)
    by_action = Counter()                # (zone, verdict, securityAction)
    by_status = Counter()                # (zone, verdict, status class)
    by_cat = Counter()                   # (zone, verdict, category)
    by_asn = defaultdict(Counter)        # asn -> verdict counts (non-verified only)
    asn_ips = defaultdict(set)
    by_day = Counter()                   # (zone, day, verdict)
    seen = set()
    for z, day, n, ua, ip, asn, path, st, act in rows_all:
        b = abv.match_bot(ua)
        if b is None:
            continue
        seen.add(ip)
        v = abv.verdict_for(b, ip, ranges, resolver)
        by_bot[(z, b.name, b.operator, v)]["requests"] += n
        ips[(z, b.name, v)].add(ip)
        by_action[(z, v, act)] += n
        by_status[(z, v, f"{st // 100}xx")] += n
        by_cat[(z, v, abv.path_category(path))] += n
        by_day[(z, day, v)] += n
        if v != "verified":
            by_asn[asn][v] += n
            by_asn[asn]["bot:" + b.name] += n
            asn_ips[asn].add(ip)

    names = {(i["asn"]): (i["as_name"], i["cc"]) for i in ipasn.values() if i.get("asn")}
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    def write(fname, rows):
        import csv
        abv.assert_no_ips(rows, seen)
        if not rows:
            return
        with open(out / fname, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    write("by_bot.csv", [{"zone": z, "bot": b, "operator": o, "verdict": v, "requests": c["requests"],
                          "unique_ips": len(ips[(z, b, v)])}
                         for (z, b, o, v), c in sorted(by_bot.items(), key=lambda kv: -kv[1]["requests"])])
    write("by_security_action.csv", [{"zone": z, "verdict": v, "security_action": a, "requests": n}
                                     for (z, v, a), n in sorted(by_action.items())])
    write("by_status.csv", [{"zone": z, "verdict": v, "status": s, "requests": n}
                            for (z, v, s), n in sorted(by_status.items())])
    write("by_category.csv", [{"zone": z, "verdict": v, "category": c, "requests": n}
                              for (z, v, c), n in sorted(by_cat.items())])
    write("by_day.csv", [{"zone": z, "date": d, "verdict": v, "requests": n}
                         for (z, d, v), n in sorted(by_day.items())])
    asn_rows = []
    for a, c in sorted(by_asn.items(), key=lambda kv: -sum(v for k, v in kv[1].items() if not k.startswith("bot:"))):
        nm, cc = names.get(a, ("", ""))
        if a is not None and str(a) in withhold:
            a, nm, cc = "withheld", abv.WITHHELD_AS_NAME, ""
        bots = Counter({k[4:]: v for k, v in c.items() if k.startswith("bot:")})
        asn_rows.append({"asn": a, "as_name": nm, "country": cc, "net_type": abv.net_type(nm),
                         "spoofed_requests": c["spoofed"], "unverifiable_requests": c["unverifiable"],
                         "indeterminate_requests": c["indeterminate"], "unique_ips": len(asn_ips[a]),
                         "claimed_bots": ";".join(f"{k}:{v}" for k, v in bots.most_common(8))})
    write("by_asn.csv", asn_rows)
    tot = Counter()
    for (z, b, o, v), c in by_bot.items():
        tot[(z, v)] += c["requests"]
    summary = {"source": "Cloudflare GraphQL httpRequestsAdaptiveGroups (sampled, adaptive)",
               "days": args.days, "zones": [label[z] for z in args.zones],
               "verdict_totals": {f"{z}|{v}": n for (z, v), n in sorted(tot.items())},
               "unique_ips_by_verdict": {v: len({ip for (z, b, vv), s in ips.items() if vv == v for ip in s})
                                         for v in abv.VERDICTS},
               "dimensions_used": DIMS,
               "all_requests_sampled_vs_estimated": {z: dict(c) for z, c in sampled.items()}, "range_files": ranges.meta, "warnings": ranges.warnings, "errors": errors[:50]}
    abv.assert_no_ips(summary, seen)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1)[:3000])


if __name__ == "__main__":
    main()
