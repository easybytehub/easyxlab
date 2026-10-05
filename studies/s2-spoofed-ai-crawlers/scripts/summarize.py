#!/usr/bin/env python3
"""Write data/summary.json: every number that claims.csv checks, computed from the published data/.

Offline, standard library only. Shares are fractions at full precision (0.3926..., not 39.3);
claims.csv rounds them with its `fmt` column (tools/render.py).

    python3 scripts/summarize.py          # from the study folder or anywhere

Inputs: data/verification_by_bot.csv, behaviour_by_verdict.csv, paths_by_verdict.csv, spoofing_by_asn.csv,
spoofing_by_net_type.csv, edge_vs_origin_30d.csv, cloudflare/{summary.json,by_security_action.csv},
logs/site-*/{summary.json,status.csv}. data/raw/ is not read.
"""
from __future__ import annotations

import csv
import ipaddress
import json
import re
from datetime import date
from pathlib import Path

S = Path(__file__).resolve().parent.parent
D = S / "data"
VERDICTS = ("verified", "spoofed", "unverifiable", "indeterminate")
USER_FETCH_FOUR = ("Claude-User", "Perplexity-User", "MistralAI-User", "DuckAssistBot")
# methods the operators publish: range files, forward-confirmed reverse DNS, and Google's own
# statement that Google-Extended is never sent as a User-Agent (METHOD §3)
OPERATOR_METHODS = ("ranges", "fcrdns", "ranges+fcrdns", "never-a-UA")
TOP_ASN = "396982"  # the one cloud provider's customer space named in the text (GOOGLE-CLOUD-PLATFORM)


def rows(rel: str) -> list[dict]:
    with open(D / rel, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def published_ip_addresses() -> int:
    """IP addresses written anywhere in the published data/ (data/raw/ excluded). Must be 0.
    A dotted quad after '/' is a software version in a User-Agent (Chrome/131.0.0.0), not an address."""
    v4 = re.compile(r"(?<![\w./])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
    v6 = re.compile(r"(?<![\w:])[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}(?![\w:])")
    found = set()
    for p in D.rglob("*"):
        if not p.is_file() or "raw" in p.relative_to(D).parts or p.name == "summary.json":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in list(v4.finditer(text)) + list(v6.finditer(text)):
            try:
                ipaddress.ip_address(m.group(0))
            except ValueError:
                continue
            found.add(m.group(0))
    return len(found)


def main() -> None:
    bots = [r for r in rows("verification_by_bot.csv") if r["site"] == "ALL"]
    by_bot = {r["bot"]: r for r in bots}
    v = {k: sum(int(r[k]) for r in bots) for k in VERDICTS}
    requests = sum(int(r["requests"]) for r in bots)
    assert requests == sum(v.values())
    testable = v["verified"] + v["spoofed"]

    sites = sorted(p.name for p in (D / "logs").iterdir() if p.is_dir())
    site_summ = {s: json.loads((D / "logs" / s / "summary.json").read_text()) for s in sites}
    log_days = {}
    for s, js in site_summ.items():
        a, b = (date.fromisoformat(t[:10]) for t in js["window_utc"])
        log_days[s] = (b - a).days + 1  # calendar days, both ends included
    short = [d for s, d in log_days.items() if s != "site-a"]

    uf = [r for r in bots if r["purpose"] == "user-fetch"]
    uf_req = sum(int(r["requests"]) for r in uf)
    uf_spoof = sum(int(r["spoofed"]) for r in uf)
    genuine = {b: int(by_bot[b]["verified"]) / (int(by_bot[b]["verified"]) + int(by_bot[b]["spoofed"]))
               for b in USER_FETCH_FOUR}
    genuine_testable = {b: int(by_bot[b]["verified"]) + int(by_bot[b]["spoofed"]) for b in USER_FETCH_FOUR}

    purposes = sorted({r["purpose"] for r in bots})
    purpose_spoofed_share = {
        p.replace("-", "_"): sum(int(r["spoofed"]) for r in bots if r["purpose"] == p)
        / sum(int(r["requests"]) for r in bots if r["purpose"] == p) for p in purposes}
    testable_by_operator_method = sum(int(r["verified"]) + int(r["spoofed"]) for r in bots
                                      if r["method"] in OPERATOR_METHODS)
    verified_by_ranges_or_fcrdns = sum(int(r["verified"]) for r in bots
                                       if r["method"] in ("ranges", "fcrdns", "ranges+fcrdns"))
    # spoofed verdicts by where they come from: an IP that fails the ranges or FCrDNS, or a
    # token the operator says is never sent as a User-Agent (Google-Extended in this data)
    spoofed_by_ranges_or_fcrdns = sum(int(r["spoofed"]) for r in bots
                                      if r["method"] in ("ranges", "fcrdns", "ranges+fcrdns"))
    spoofed_by_never_a_ua = sum(int(r["spoofed"]) for r in bots if r["method"] == "never-a-UA")

    sp_paths = {r["category"]: int(r["requests"]) for r in rows("paths_by_verdict.csv") if r["verdict"] == "spoofed"}
    assert sum(sp_paths.values()) == v["spoofed"]

    beh = {r["verdict"]: r for r in rows("behaviour_by_verdict.csv")}
    sp = beh["spoofed"]
    sp_beh_total = sum(int(sp[f"requests_{k}"]) for k in ("probe", "content-only", "other"))

    nets = {r["net_type"]: int(r["spoofed_requests"]) for r in rows("spoofing_by_net_type.csv")}
    asn = {r["asn"]: int(r["spoofed_requests"]) for r in rows("spoofing_by_asn.csv")}

    status = [r for s in sites for r in rows(f"logs/{s}/status.csv") if r["verdict"] == "spoofed"]
    sp_status_total = sum(int(r["requests"]) for r in status)
    sp_4xx = sum(int(r["requests"]) for r in status if r["status"] == "4xx")

    eo = {(r["site"], r["verdict"]): r for r in rows("edge_vs_origin_30d.csv")}
    edge_a = int(eo[("site-a", "spoofed")]["edge_requests"])
    origin_a = int(eo[("site-a", "spoofed")]["origin_requests"])
    cf = json.loads((D / "cloudflare" / "summary.json").read_text())
    sec = rows("cloudflare/by_security_action.csv")
    blocked_a = sum(int(r["requests"]) for r in sec
                    if r["zone"] == "site-a" and r["verdict"] == "spoofed" and r["security_action"] == "block")
    edge_a_sec = sum(int(r["requests"]) for r in sec if r["zone"] == "site-a" and r["verdict"] == "spoofed")
    assert edge_a_sec == edge_a

    out = {
        "sites": len(sites),
        "bots": len(bots),
        "operators": len({r["operator"] for r in bots}),
        "requests": requests,
        "sites_declared_bot_requests": sum(js["declared_bot_requests"] for js in site_summ.values()),
        "verdicts": v,
        "share": {**{k: v[k] / requests for k in VERDICTS},
                  "unverifiable_or_indeterminate": (v["unverifiable"] + v["indeterminate"]) / requests},
        "testable": testable,
        "spoofed_of_testable": v["spoofed"] / testable,
        "fcrdns_bots": sum("fcrdns" in r["method"] for r in bots),
        "testable_by_operator_method": testable_by_operator_method,
        "verified_by_ranges_or_fcrdns": verified_by_ranges_or_fcrdns,
        "spoofed_by_ranges_or_fcrdns": spoofed_by_ranges_or_fcrdns,
        "spoofed_by_never_a_ua": spoofed_by_never_a_ua,
        "purpose_spoofed_share": purpose_spoofed_share,
        "log_days": log_days,
        "log_days_short_min": min(short),
        "log_days_short_max": max(short),
        "user_fetch": {"bots": len(uf), "requests": uf_req, "spoofed": uf_spoof, "spoofed_share": uf_spoof / uf_req},
        "genuine_share": genuine,
        "genuine_testable": genuine_testable,
        "genuine_share_min_four": min(genuine.values()),
        "genuine_share_max_four": max(genuine.values()),
        "google_extended": {k: int(by_bot["Google-Extended"][k]) for k in ("requests",) + VERDICTS},
        "spoofed_ips_upper_bound": int(sp["distinct_ips_upper_bound"]),
        "spoofed_requests_by_behaviour": sp_beh_total,
        "spoofed_cloud_share": nets["cloud/hosting"] / v["spoofed"],
        "spoofed_top_asn": TOP_ASN,
        "spoofed_top_asn_share": asn[TOP_ASN] / v["spoofed"],
        "spoofed_probe_share": int(sp["requests_probe"]) / v["spoofed"],
        "spoofed_probe_path_share": sp_paths["vuln-probe"] / v["spoofed"],
        "spoofed_multi_operator_share": int(sp["requests_multi_operator"]) / v["spoofed"],
        "spoofed_status_total": sp_status_total,
        "spoofed_4xx_share": sp_4xx / sp_status_total,
        "edge": {"days": cf["days"], "site_a_spoofed_edge": edge_a, "site_a_spoofed_origin": origin_a,
                 "site_a_ratio": edge_a / origin_a, "site_a_blocked": blocked_a,
                 "site_a_blocked_share": blocked_a / edge_a},
        "published_ip_addresses": published_ip_addresses(),
    }
    (D / "summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {D / 'summary.json'}")


if __name__ == "__main__":
    main()
