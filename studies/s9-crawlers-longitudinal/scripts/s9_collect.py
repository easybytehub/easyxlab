#!/usr/bin/env python3
"""s9_collect.py — EasyxLab study S9, weekly collector.

For each site and ISO week (Monday 00:00 to Monday 00:00 UTC) it:

  1. reads the origin access logs (local files, or streamed over SSH: raw lines stay in memory and
     are never written to disk), including the monthly-rotated copies;
  2. runs study S2's verifier (imported unchanged, see s9_common.py) on every request that claims a
     known crawler, EXCLUDING the trap prefix, and writes S2's standard aggregated tables;
  3. classifies every request under the trap prefix by arm, phase and label (PROTOCOL.md §5) and
     writes trap.csv, exposure.csv and, if configured, active_arm.csv;
  4. lists crawler-like names that S2's registry does not know (new_tokens.csv, >= 3 requests);
  5. optionally (--cf-env) pulls Cloudflare's edge view for the same week and reads, read-only, the
     zone's bot settings;
  6. for the most recent week, checks the live robots.txt, study pages and footer links
     (checks.json); a missing piece is a DEVIATION (exit status 2).

Outputs are aggregates only, under <out>/<YYYY-Www>/<site-label>/, plus <out>/<YYYY-Www>/MANIFEST.json.
Nothing written may contain a client IP, a studied domain or a trap path: every file is checked
before the week directory is published (atomic rename). A week that already exists is skipped
(the first, as-of-week computation is canonical) unless --force.

Usage:
  s9_collect.py --config private/sites.json --week last --out data/weekly [--asn] [--cf-env .env]
  s9_collect.py --config private/sites.json --backfill-from 2026-W31 --week 2026-W40 --out data/weekly

Exit status: 0 ok (or nothing to do), 1 error, 2 deviation found by the live checks.
"""
from __future__ import annotations

import argparse
import csv
import concurrent.futures as cfut
import glob
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s9_common as c  # noqa: E402

abv = c.abv
ASSISTANT_OPERATOR = {"ChatGPT": "OpenAI", "Claude": "Anthropic", "Perplexity": "Perplexity",
                      "Le Chat": "Mistral", "Gemini": "Google"}
TS_RX = re.compile(r"\[(\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4})\]")
SAFE_DIR = re.compile(r"^[A-Za-z0-9_./~-]+$")


# ----------------------------------------------------------------------------------------------
# Reading logs
# ----------------------------------------------------------------------------------------------

def local_lines(spec: dict, include_gz: bool):
    files = []
    for pat in spec.get("files", []):
        files += sorted(glob.glob(os.path.expanduser(pat)))
    files = [f for f in files if include_gz or not f.endswith(".gz")]
    yield from abv.read_lines(files)


def ssh_stream(host: str, sites: list, include_gz: bool):
    """One SSH connection per host for all its sites. Yields (label, line)."""
    parts = []
    for s in sites:
        d = s.log["dir"]
        if not SAFE_DIR.match(d) or not re.match(r"^[a-z0-9-]+$", s.label):
            raise ValueError(f"{s.label}: unsafe log dir or label")
        gz = (" for f in $(ls -1 access.log.*.gz 2>/dev/null | sort -t. -k3,3nr); do gzip -dc \"$f\"; done;"
              if include_gz else "")
        parts.append(f"printf '\\036S9 {s.label}\\n'; if cd {d}; then{gz} "
                     f"[ -f access.log.1 ] && cat access.log.1; [ -f access.log ] && cat access.log; cd; fi")
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", host, "; ".join(parts)]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    label = None
    for raw in p.stdout:
        line = raw.decode("utf-8", errors="replace")
        if line.startswith("\x1eS9 "):
            label = line[4:].strip()
            continue
        if label:
            yield label, line
    p.wait()
    if p.returncode != 0:
        raise RuntimeError(f"ssh {host}: exit {p.returncode}: {p.stderr.read().decode(errors='replace')[:200]}")


def bucket_lines(sites: dict, weeks: set, include_gz: bool) -> dict:
    """{(label, week): [raw lines]} for the requested weeks only."""
    out = defaultdict(list)
    windows = {w: c.week_window(w) for w in weeks}
    lo = min(s for s, _ in windows.values())
    hi = max(e for _, e in windows.values())

    def take(label, line):
        m = TS_RX.search(line)
        if not m:
            return
        try:
            ts = datetime.strptime(m[1], "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            return
        if lo <= ts < hi:
            w = c.week_of(ts)
            if w in weeks:
                out[(label, w)].append(line)

    by_host = defaultdict(list)
    for s in sites.values():
        if "ssh" in s.log:
            by_host[s.log["ssh"]].append(s)
        else:
            for line in local_lines(s.log, include_gz):
                take(s.label, line)
    for host, ss in by_host.items():
        for label, line in ssh_stream(host, ss, include_gz):
            take(label, line)
    return out


# ----------------------------------------------------------------------------------------------
# Privacy guard (on top of S2's IP guard): no studied domain, no trap path in any output
# ----------------------------------------------------------------------------------------------

def forbidden_strings(sites: dict) -> list[str]:
    out = []
    for s in sites.values():
        if s.domain:
            out.append(s.domain.lower())
        out += [p.lower() for p in s.arms]
        if s.prefix:
            out.append(s.prefix.rstrip("/").lower())
    return [x for x in out if x]


def check_dir(d: Path, known_ips: set, forbidden: list[str]) -> list[str]:
    problems = []
    for f in sorted(d.rglob("*")):
        if not f.is_file():
            continue
        text = f.read_text(errors="replace")
        try:
            abv.assert_no_ips({"x": text}, known_ips)
        except ValueError as e:
            problems.append(f"{f.name}: {e}")
        low = text.lower()
        for s in forbidden:
            if s in low:
                problems.append(f"{f.name}: contains a studied domain or trap path")
                break
    return problems


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ----------------------------------------------------------------------------------------------
# The S9 pass over one site-week
# ----------------------------------------------------------------------------------------------

def referer_class(line: str, domain: str) -> str:
    m = abv.LINE_RX.match(line.strip())
    ref = (m["ref"] if m and m["ref"] is not None else "-") or "-"
    if ref in ("-", ""):
        return "none"
    return "same-site" if domain and domain.lower() in ref.lower() else "external"


def site_week(site: c.Site, all_sites: dict, lines: list[str], week: str, ranges, resolver, excl: set,
              args, cfg: dict) -> tuple[dict, set, dict]:
    start, end = c.week_window(week)
    own = 0
    keep, trap = [], []           # raw lines for S2 (non-trap), parsed trap requests
    parsed_all = []
    foreign_prefixes = {s.prefix: s.label for s in all_sites.values() if s.prefix and s.label != site.label}
    for line in lines:
        r = abv.parse_line(line)
        if r is None or not (start <= r.ts < end):
            continue
        if c.is_own_check(r.ua):
            own += 1
            continue
        if r.ip in excl:
            continue
        arm = c.trap_arm(site, r.path)
        if arm is None:                          # another studied site's trap prefix requested here
            hit = next((lab for p, lab in foreign_prefixes.items() if r.path.startswith(p)), None)
            if hit:
                arm = "foreign-prefix:" + hit
        parsed_all.append((r, arm, line))
        if arm is None:
            keep.append(line)
        else:
            trap.append((r, arm, line))

    # 1) S2's standard tables, trap prefix excluded (PROTOCOL §5)
    agg = abv.analyse(keep, ranges, resolver, excl, start, end)
    asn_map = abv.cymru_asn(sorted(agg.ip_bots)) if args.asn else None
    withhold = frozenset()
    if args.withhold_asn_file:
        withhold = frozenset(x.strip() for x in Path(args.withhold_asn_file).read_text().splitlines()
                             if x.strip() and not x.startswith("#"))
    report = abv.build_report(agg, site.label, asn_map, ranges, withhold)
    known = abv.seen_ips(agg) | {r.ip for r, _, _ in parsed_all}

    vcache: dict = {}

    def verdict(bot, ip):
        k = (bot.name, ip)
        if k not in vcache:
            vcache[k] = abv.verdict_for(bot, ip, ranges, resolver)
        return vcache[k]

    # 2) trap table
    trows: dict = defaultdict(lambda: {"requests": 0, "ips": set()})
    miners = set()
    for r, arm, _ in trap:
        if arm == "robots-only":
            miners.add(r.ip)
    for r, arm, line in trap:
        bot = abv.match_bot(r.ua)
        v = verdict(bot, r.ip) if bot else None
        if arm.startswith("foreign-prefix:"):
            ph, lab = "n/a", "foreign-prefix"
        else:
            ph = c.trap_phase(site, arm, r.ts, bot.operator if bot else None, args.grace_hours)
            lab = c.trap_label(arm, ph, bot, v, r.ua)
        key = (arm, ph, lab, bot.name if bot else "(undeclared)", bot.operator if bot else "-",
               bot.purpose if bot else "-", c.claim_of(bot.name) if bot else "-", v or "-",
               "-" if bot else c.ua_class(r.ua), referer_class(line, site.domain))
        trows[key]["requests"] += 1
        trows[key]["ips"].add(r.ip)
    trap_rows = [{"site": site.label, "week": week, "arm": k[0], "phase": k[1], "label": k[2], "bot": k[3],
                  "operator": k[4], "purpose": k[5], "operator_claim": k[6], "verdict": k[7],
                  "client_class": k[8], "referer": k[9], "requests": d["requests"],
                  "unique_sources": len(d["ips"]),
                  "sources_also_in_robots_only": len(d["ips"] & miners)}
                 for k, d in sorted(trows.items(), key=lambda kv: (kv[0][0], kv[0][2], -kv[1]["requests"]))]

    # 3) exposure per declared crawler and verdict
    exp: dict = defaultdict(Counter)
    exp_ips: dict = defaultdict(set)
    for r, arm, _ in parsed_all:
        bot = abv.match_bot(r.ua)
        if bot is None:
            continue
        v = verdict(bot, r.ip)
        k = (bot.name, v)
        exp_ips[k].add(r.ip)
        if arm is None:
            exp[k]["requests_site"] += 1
            cat = abv.path_category(r.path)
            if cat == "robots.txt" and site.t_robots and r.ts >= site.t_robots:
                exp[k]["robots_after_t_robots"] += 1
            if cat in ("page", "home") and site.t_link and r.ts >= site.t_link:
                exp[k]["html_after_t_link"] += 1
        elif not arm.startswith("foreign-prefix:"):
            ph = c.trap_phase(site, arm, r.ts, bot.operator, args.grace_hours)
            if arm == "allowed" and ph == "active":
                exp[k]["control_active"] += 1
            elif arm == "disallowed" and ph == "active":
                exp[k]["disallowed_active"] += 1
            elif arm == "robots-only" and ph == "active":
                exp[k]["robots_only_active"] += 1
            elif ph == "grace":
                exp[k]["in_grace"] += 1
    cols = ["requests_site", "robots_after_t_robots", "html_after_t_link", "control_active",
            "disallowed_active", "robots_only_active", "in_grace"]
    exposure_rows = []
    for (name, v), cnt in sorted(exp.items(), key=lambda kv: (-kv[1]["requests_site"], kv[0])):
        b = abv.bot_by_name(name)
        exposure_rows.append({"site": site.label, "week": week, "bot": name, "operator": b.operator,
                              "purpose": b.purpose, "operator_claim": c.claim_of(name), "verdict": v,
                              **{k: cnt[k] for k in cols}, "unique_sources": len(exp_ips[(name, v)])})

    # 4) crawler-like names unknown to S2's registry
    tok_req, tok_ips = Counter(), defaultdict(set)
    for r, _, _ in parsed_all:
        for t in c.unregistered_tokens(r.ua):
            tok_req[t] += 1
            tok_ips[t].add(r.ip)
    token_rows = [{"site": site.label, "week": week, "token": t, "requests": n, "unique_sources": len(tok_ips[t])}
                  for t, n in tok_req.most_common() if n >= 3]

    # 5) optional active arm (H2): sessions declared in the private config
    active_rows = []
    for sess in cfg.get("active_sessions", []):
        if sess.get("site") != site.label:
            continue
        t0 = c.parse_utc(sess["t"])
        if not (start <= t0 < end):
            continue
        op = ASSISTANT_OPERATOR.get(sess.get("assistant", ""), sess.get("operator", ""))
        cnt = Counter()
        for r, arm, _ in trap:
            if not (t0 <= r.ts < t0 + timedelta(minutes=15)) or arm.startswith("foreign"):
                continue
            bot = abv.match_bot(r.ua)
            if bot is None or bot.operator != op:
                continue
            cnt[f"{'verified' if verdict(bot, r.ip) == 'verified' else 'unverified'}_{arm}"] += 1
        active_rows.append({"site": site.label, "session": sess.get("id", ""), "assistant": sess.get("assistant", ""),
                            "requested_arm": sess.get("arm", ""),
                            **{f"{vv}_{a}": cnt[f"{vv}_{a}"] for vv in ("verified", "unverified") for a in c.ARMS}})

    meta = {"lines_in_window": len(parsed_all) + own, "own_check_requests_excluded": own,
            "declared_bot_requests_non_trap": agg.declared, "trap_requests": len(trap),
            "first_ts": agg.first_ts.astimezone(timezone.utc).isoformat() if agg.first_ts else None,
            "last_ts": agg.last_ts.astimezone(timezone.utc).isoformat() if agg.last_ts else None}
    return {"report": report, "trap": trap_rows, "exposure": exposure_rows, "tokens": token_rows,
            "active": active_rows}, known, meta


# ----------------------------------------------------------------------------------------------
# Live checks (most recent week only) and Cloudflare (read-only)
# ----------------------------------------------------------------------------------------------

def http(url: str, method: str = "GET", timeout: int = 30):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": c.check_ua()})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, ""
    except Exception as e:  # noqa: BLE001
        return 0, {}, type(e).__name__


def robots_has_trap(txt: str, paths: list[str]) -> bool:
    """Every path appears as `Disallow: <path>` inside the `User-agent: *` group, before `Allow: /`."""
    groups, cur = [], None
    for raw in txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            if cur is None or cur["rules"]:
                cur = {"agents": [], "rules": []}
                groups.append(cur)
            cur["agents"].append(v)
        elif cur is not None and k in ("allow", "disallow"):
            cur["rules"].append((k, v))
    star = next((g for g in groups if "*" in g["agents"]), None)
    if star is None:
        return False
    rules = star["rules"]
    allow_root = next((i for i, r in enumerate(rules) if r == ("allow", "/")), len(rules))
    return all(("disallow", p) in rules[:allow_root] for p in paths)


def live_checks(site: c.Site, now: datetime) -> dict:
    out = {"deviations": []}
    if not site.domain:
        return out
    dis = [p for p, a in site.arms.items() if a in c.ARMS_DISALLOWED]
    ended = site.t_end is not None and now >= site.t_end
    if site.t_robots and not ended and dis:
        st, h, body = http(f"https://{site.domain}/robots.txt?s9={secrets.token_hex(4)}")
        out["robots_cache_busted_ok"] = st == 200 and robots_has_trap(body, dis)
        st2, h2, body2 = http(f"https://{site.domain}/robots.txt")
        out["robots_plain_ok"] = st2 == 200 and robots_has_trap(body2, dis)
        out["robots_edge_cache_status"] = h2.get("cf-cache-status", "")
        out["robots_sha256"] = hashlib.sha256(body2.encode()).hexdigest() if st2 == 200 else ""
        if not (out["robots_cache_busted_ok"] and out["robots_plain_ok"]):
            out["deviations"].append("robots.txt no longer carries the S9 Disallow lines in the * group")
    if site.t_link and not ended and site.footer_hrefs:
        ok = True
        for p in site.arms:                      # on the linked sites every arm path is served
            st, h, _ = http(f"https://{site.domain}{p}", method="HEAD")
            if st != 200 or "noindex" not in h.get("x-robots-tag", "").lower():
                ok = False
        out["study_pages_ok"] = ok
        st, _, home = http(f"https://{site.domain}/")
        out["footer_links_ok"] = st == 200 and all(f'href="{p}"' in home for p in site.footer_hrefs)
        if not ok:
            out["deviations"].append("a study page is not served as deployed (200 + X-Robots-Tag noindex)")
        if not out["footer_links_ok"]:
            out["deviations"].append("the footer links to the study pages are missing from the home page")
    return out


CF_EXPECTED_OFF = {"fight_mode": False, "is_robots_txt_managed": False, "ai_bots_protection": "disabled",
                   "crawler_protection": "disabled", "ai_training": "disabled", "ai_search": "disabled",
                   "ai_user": "disabled"}


def cf_settings(cf, tok: str, zone_ids: dict, site: c.Site) -> dict:
    zid = zone_ids.get(site.cf_zone)
    if not zid:
        return {"error": "zone not visible to token"}
    r = cf.api(tok, f"/zones/{zid}/bot_management")
    res = r.get("result") or {}
    snap = {k: res.get(k) for k in CF_EXPECTED_OFF}
    dev = [f"Cloudflare {k} is {snap[k]!r}" for k, want in CF_EXPECTED_OFF.items()
           if k in res and snap[k] != want]
    return {"bot_management": snap, "deviations": dev}


def edge_week(cf, tok: str, zid: str, site: c.Site, week: str, ranges, resolver, excl: set) -> tuple[dict, set, list]:
    start, end = c.week_window(week)
    rows, errors, seen = [], [], set()
    sampled = Counter()
    d = start
    while d < end:
        got, errs = cf.fetch_zone_day(tok, zid, d, d + timedelta(days=1))
        if errs:
            errors.append(f"{d.date()}: {errs[0][:120]}")
        for g in got or []:
            dm = g["dimensions"]
            ua, ip = dm.get("userAgent") or "", dm.get("clientIP") or ""
            si = (g.get("avg") or {}).get("sampleInterval") or 1
            if c.is_own_check(ua) or ip in excl:
                continue
            rows.append((d.date().isoformat(), g["count"], si, ua, ip, dm.get("clientRequestPath") or "/",
                         dm.get("edgeResponseStatus") or 0, dm.get("securityAction") or "unknown"))
        d += timedelta(days=1)
    if resolver is not None:                     # FCrDNS in parallel, as S2's edge script does
        need = set()
        for _, _, _, ua, ip, *_ in rows:
            b = abv.match_bot(ua)
            if b and b.rdns and not b.never_a_ua and not any(
                    ranges.load(k) and abv.in_nets(ip, ranges.load(k)) for k in b.ranges):
                need.add((ip, b.rdns))
        with cfut.ThreadPoolExecutor(max_workers=32) as ex:
            list(ex.map(lambda t: resolver.fcrdns(*t), need))
    by_bot, by_trap, robots_after = Counter(), Counter(), Counter()
    for day, n, si, ua, ip, path, st, act in rows:
        seen.add(ip)
        bot = abv.match_bot(ua)
        arm = c.trap_arm(site, path)
        v = abv.verdict_for(bot, ip, ranges, resolver) if bot else "-"
        if bot:
            sampled["declared_rows"] += n
            if si > 1:
                sampled["declared_rows_in_sampled_groups"] += n
        if arm is not None:
            by_trap[(day, arm, bot.name if bot else "(undeclared)", v, "-" if bot else c.ua_class(ua), act,
                     f"{st // 100}xx")] += n
        elif bot:
            by_bot[(bot.name, bot.operator, bot.purpose, v, act)] += n
            day_start = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
            if abv.path_category(path) == "robots.txt" and site.t_robots and day_start >= site.t_robots:
                robots_after[(bot.name, v)] += n
    out = {
        "edge_by_bot": [{"site": site.label, "week": week, "bot": k[0], "operator": k[1], "purpose": k[2],
                         "verdict": k[3], "security_action": k[4], "sampled_requests": n}
                        for k, n in sorted(by_bot.items(), key=lambda kv: -kv[1])],
        "edge_trap": [{"site": site.label, "week": week, "date": k[0], "arm": k[1], "bot": k[2], "verdict": k[3],
                       "client_class": k[4], "security_action": k[5], "edge_status": k[6], "sampled_requests": n}
                      for k, n in sorted(by_trap.items())],
        "edge_robots_after_t_robots": [{"site": site.label, "week": week, "bot": k[0], "verdict": k[1],
                                        "sampled_requests": n} for k, n in sorted(robots_after.items())],
        "edge_sampling": dict(sampled),
    }
    return out, seen, errors


# ----------------------------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------------------------

def range_files_meta(ranges, cache_dir: Path) -> dict:
    meta = {}
    for k, m in ranges.meta.items():
        f = cache_dir / f"{k}.json"
        meta[k] = {**m, "sha256": c.sha256_file(f) if f.exists() else None}
    return meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="s9_collect", description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, required=True, help="private sites.json (see sites.example.json)")
    ap.add_argument("--week", default="last", help="YYYY-Www, or 'last' (most recent complete ISO week)")
    ap.add_argument("--backfill-from", help="process every week from this one to --week (marked retroactive)")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "weekly")
    ap.add_argument("--sites", nargs="*", help="only these site labels")
    ap.add_argument("--cache-dir", type=Path, default=Path.home() / ".cache" / "easyxlab-s9")
    ap.add_argument("--ranges-dir", type=Path, help="offline <key>.json range files (tests)")
    ap.add_argument("--exclude-ip-file", type=Path, help="own monitoring addresses, one per line")
    ap.add_argument("--withhold-asn-file", type=Path)
    ap.add_argument("--asn", action="store_true", help="ASN of NON-verified sources via Team Cymru (as S2)")
    ap.add_argument("--no-dns", action="store_true")
    ap.add_argument("--cf-env", type=Path, help="env file with CLOUDFLARE_API_TOKEN (read-only use)")
    ap.add_argument("--no-live-checks", action="store_true")
    ap.add_argument("--grace-hours", type=int, help="override every operator's grace (sensitivity runs only)")
    ap.add_argument("--force", action="store_true", help="recompute a week that already exists")
    ap.add_argument("--now", help="pretend the current time is this ISO timestamp (tests)")
    args = ap.parse_args(argv)

    now = c.parse_utc(args.now) if args.now else datetime.now(timezone.utc)
    cfg = c.load_config(args.config)
    sites = {k: v for k, v in cfg["_sites"].items() if not args.sites or k in args.sites}
    last = c.last_complete_week(now) if args.week == "last" else args.week
    weeks = c.weeks_between(args.backfill_from, last) if args.backfill_from else [last]
    todo = [w for w in weeks if args.force or not (args.out / w / "MANIFEST.json").exists()]
    for w in weeks:
        if w not in todo:
            print(f"{w}: already collected, skipped (use --force to recompute)")
        elif c.week_window(w)[1] > now:
            print(f"{w}: not complete yet", file=sys.stderr)
            return 1
    if not todo:
        return 0

    excl = set()
    if args.exclude_ip_file:
        excl = {x.strip() for x in args.exclude_ip_file.read_text().split() if x.strip()}
    ranges = abv.RangeStore(args.cache_dir, args.ranges_dir)
    resolver = None if args.no_dns else abv.Resolver()
    forbidden = forbidden_strings(cfg["_sites"])
    include_gz = bool(args.backfill_from) or any(c.week_window(w)[0] < now - timedelta(days=35) for w in todo)
    lines = bucket_lines(sites, set(todo), include_gz)

    cf = tok = None
    zone_ids = {}
    if args.cf_env:
        cf = c.load_cf_module()
        tok = cf.token_from_env(args.cf_env)
        zone_ids = {z["name"]: z["id"] for z in (cf.api(tok, "/zones?per_page=50").get("result") or [])}

    status = 0
    for w in todo:
        start, end = c.week_window(w)
        tmp = args.out / f".tmp-{w}-{os.getpid()}"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        known_all: set = set()
        manifest = {"study": "EasyxLab S9", "s9_version": c.S9_VERSION, "week": w,
                    "window_utc": [start.isoformat(), end.isoformat()], "generated_utc": now.isoformat(),
                    "retroactive": now > end + timedelta(days=8), "abv_version": abv.VERSION,
                    "abv_sha256": c.ABV_SHA256, "grace_hours_override": args.grace_hours,
                    "sites": {}, "warnings": [], "deviations": []}
        for label, site in sites.items():
            res, known, meta = site_week(site, cfg["_sites"], lines.get((label, w), []), w, ranges, resolver,
                                         excl, args, cfg)
            known_all |= known
            sd = tmp / label
            abv.write_outputs(res["report"], sd, known_ips=known)
            write_csv(sd / "trap.csv", res["trap"])
            write_csv(sd / "exposure.csv", res["exposure"])
            write_csv(sd / "new_tokens.csv", res["tokens"])
            write_csv(sd / "active_arm.csv", res["active"])
            site_meta = {**meta, "t_robots_set": bool(site.t_robots), "t_link_set": bool(site.t_link)}
            if meta["lines_in_window"] == 0:
                msg = f"{label}: no log lines in the window (log unreadable, or the site was not logging)"
                (manifest["deviations"] if w == last else manifest["warnings"]).append(msg)
            if cf is not None:
                if start < now - timedelta(days=29):
                    manifest["warnings"].append(f"{label}: week beyond Cloudflare's edge retention, no edge view")
                elif site.cf_zone in zone_ids:
                    edge, seen, errs = edge_week(cf, tok, zone_ids[site.cf_zone], site, w, ranges, resolver, excl)
                    known_all |= seen
                    for k in ("edge_by_bot", "edge_trap", "edge_robots_after_t_robots"):
                        write_csv(sd / f"{k}.csv", edge[k])
                    site_meta["edge_sampling"] = edge["edge_sampling"]
                    manifest["warnings"] += [f"{label} edge {e}" for e in errs]
            if w == last and not args.no_live_checks:
                chk = live_checks(site, now)
                if cf is not None:
                    chk["cloudflare"] = cf_settings(cf, tok, zone_ids, site)
                    chk["deviations"] += chk["cloudflare"].get("deviations", [])
                (sd / "checks.json").write_text(json.dumps(chk, indent=2))
                manifest["deviations"] += [f"{label}: {d}" for d in chk["deviations"]]
            manifest["sites"][label] = site_meta
        manifest["range_files"] = range_files_meta(ranges, args.cache_dir) if not args.ranges_dir else {
            k: {**m, "sha256": None} for k, m in ranges.meta.items()}
        manifest["warnings"] += ranges.warnings
        (tmp / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
        problems = check_dir(tmp, known_all, forbidden)
        if problems:
            shutil.rmtree(tmp, ignore_errors=True)
            print(f"{w}: privacy guard refused to publish: {problems[:3]}", file=sys.stderr)
            return 1
        dest = args.out / w
        if dest.exists():
            shutil.rmtree(dest)
        os.replace(tmp, dest)
        decl = sum(m["declared_bot_requests_non_trap"] for m in manifest["sites"].values())
        trap_n = sum(m["trap_requests"] for m in manifest["sites"].values())
        print(f"{w}: {len(manifest['sites'])} sites, {decl} declared-crawler requests, {trap_n} trap requests"
              + (" (retroactive)" if manifest["retroactive"] else ""))
        for d in manifest["deviations"]:
            print(f"DEVIATION {d}")
            status = 2
    return status


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"s9_collect: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
