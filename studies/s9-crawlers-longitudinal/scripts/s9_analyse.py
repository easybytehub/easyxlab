#!/usr/bin/env python3
"""s9_analyse.py — EasyxLab study S9: weekly series, trap tables and the verdict of each
pre-registered hypothesis (PROTOCOL.md §6, §9), applied mechanically. Reads only the aggregated
weekly outputs of s9_collect.py; writes aggregated tables and hypotheses.{json,md}.

Usage:
  s9_analyse.py [--weekly-dir data/weekly] [--out data/analysis] [--first 2026-W41] [--last 2026-W52]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s9_common as c  # noqa: E402
import s9_stats as st  # noqa: E402

LINKED_SITES_NEED_ARM = "allowed"
MIN_TESTABLE_PER_WEEK = 20
MIN_WEEKS_TREND = 8


def rows(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


def write(p: Path, rs: list[dict]) -> None:
    if not rs:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rs[0].keys()))
        w.writeheader()
        w.writerows(rs)


def load(weekly: Path) -> dict:
    data = {"weeks": {}, "by_bot": [], "trap": [], "exposure": [], "tokens": [], "active": [], "edge_robots": []}
    for wd in sorted(p for p in weekly.iterdir() if p.is_dir() and not p.name.startswith(".")):
        mf = wd / "MANIFEST.json"
        if not mf.exists():
            continue
        m = json.loads(mf.read_text())
        data["weeks"][wd.name] = m
        for sd in sorted(p for p in wd.iterdir() if p.is_dir()):
            for r in rows(sd / "by_bot.csv"):
                data["by_bot"].append({**r, "week": wd.name, "retroactive": m["retroactive"]})
            for key, fname in (("trap", "trap.csv"), ("exposure", "exposure.csv"), ("tokens", "new_tokens.csv"),
                               ("active", "active_arm.csv"), ("edge_robots", "edge_robots_after_t_robots.csv")):
                data[key] += [{**r, "retroactive": m["retroactive"]} for r in rows(sd / fname)]
    return data


def prospective(week: str, retro: bool | str, first: str, last: str) -> bool:
    retro = retro in (True, "True", "true")
    return (not retro) and first <= week <= last


def series(data: dict, first: str, last: str) -> tuple[list, list]:
    per = defaultdict(Counter)
    per_bot = defaultdict(Counter)
    retro = {}
    for r in data["by_bot"]:
        k = (r["site"], r["week"])
        per[k][r["verdict"]] += int(r["requests"])
        per_bot[(r["site"], r["week"], r["bot"], r["operator"], r["purpose"])][r["verdict"]] += int(r["requests"])
        retro[k] = r["retroactive"]
    out = []
    for (site, week), cnt in sorted(per.items()):
        t = cnt["verified"] + cnt["spoofed"]
        lo, hi = st.wilson(cnt["spoofed"], t)
        out.append({"site": site, "week": week, "prospective": prospective(week, retro[(site, week)], first, last),
                    "verified": cnt["verified"], "spoofed": cnt["spoofed"], "unverifiable": cnt["unverifiable"],
                    "indeterminate": cnt["indeterminate"], "testable": t,
                    "spoofed_share": round(cnt["spoofed"] / t, 4) if t else "",
                    "ci95_lo": round(lo, 4) if t else "", "ci95_hi": round(hi, 4) if t else ""})
    out_bot = []
    for (site, week, bot, op, pur), cnt in sorted(per_bot.items()):
        t = cnt["verified"] + cnt["spoofed"]
        out_bot.append({"site": site, "week": week, "bot": bot, "operator": op, "purpose": pur,
                        **{v: cnt[v] for v in ("verified", "spoofed", "unverifiable", "indeterminate")},
                        "spoofed_share": round(cnt["spoofed"] / t, 4) if t else ""})
    return out, out_bot


def trend(points: list[dict], value: str) -> dict:
    xs = [float(p[value]) for p in points]
    mk = st.mann_kendall(xs)
    return {**mk, "sens_slope_per_week": st.sens_slope(xs), "weeks": [p["week"] for p in points]}


def trap_tables(data: dict, first: str, last: str) -> tuple[list, list]:
    labels = Counter()
    for r in data["trap"]:
        key = (r["site"], r["arm"], r["phase"], r["label"], r["bot"], r["operator"], r["operator_claim"],
               r["verdict"], r["client_class"])
        labels[key] += int(r["requests"])
    lab_rows = [{"site": k[0], "arm": k[1], "phase": k[2], "label": k[3], "bot": k[4], "operator": k[5],
                 "operator_claim": k[6], "verdict": k[7], "client_class": k[8], "requests": n}
                for k, n in sorted(labels.items())]
    exp = defaultdict(Counter)
    for r in data["exposure"]:
        k = (r["site"], r["bot"], r["operator"], r["operator_claim"], r["verdict"])
        for col in ("requests_site", "robots_after_t_robots", "html_after_t_link", "control_active",
                    "disallowed_active", "robots_only_active", "in_grace"):
            exp[k][col] += int(r[col])
    for r in data["edge_robots"]:
        b = c.abv.bot_by_name(r["bot"]) if r["bot"] in {x.name for x in c.abv.BOTS} else None
        k = (r["site"], r["bot"], b.operator if b else "", c.claim_of(r["bot"]), r["verdict"])
        exp[k]["edge_robots_after_t_robots"] += int(r["sampled_requests"])
    out = []
    for (site, bot, op, claim, v), cnt in sorted(exp.items()):
        tested_linked = cnt["control_active"] > 0
        tested_robots = (cnt["robots_after_t_robots"] + cnt["edge_robots_after_t_robots"]) > 0
        viol = cnt["disallowed_active"] + cnt["robots_only_active"]
        status = ("violates" if viol and v == "verified" else
                  "respects" if (tested_linked or tested_robots) and v == "verified" else
                  "not tested" if v == "verified" else "n/a (not verified)")
        out.append({"site": site, "bot": bot, "operator": op, "operator_claim": claim, "verdict": v, **cnt,
                    "tested_linked": tested_linked, "tested_robots": tested_robots, "status": status,
                    "upper95_violation_prob": round(st.zero_event_upper(cnt["control_active"]), 4)
                    if v == "verified" and not viol else ""})
    return lab_rows, out


def h1(trap_bot: list[dict]) -> dict:
    res = {}
    for op, bots in c.H1_BOTS.items():
        sel = [r for r in trap_bot if r["bot"] in bots and r["verdict"] == "verified"]
        viol = sum(int(r["disallowed_active"]) + int(r["robots_only_active"]) for r in sel)
        tested = any(r["tested_linked"] or r["tested_robots"] for r in sel)
        n_ctrl = sum(int(r["control_active"]) for r in sel)
        verdict = "falsified" if viol else ("not falsified" if tested else "not tested")
        res[op] = {"bots": bots, "verified_violations": viol, "tested": tested, "control_fetches": n_ctrl,
                   "upper95_violation_prob": round(st.zero_event_upper(n_ctrl), 4) if not viol else None,
                   "verdict": verdict}
    return res


H2_PRED = {"ChatGPT": "fetches-disallowed", "Perplexity": "fetches-disallowed",
           "Claude": "respects", "Le Chat": "respects"}


def h2(active: list[dict]) -> dict:
    by = defaultdict(list)
    for r in active:
        by[r["assistant"]].append(r)
    res = {}
    for a, pred in H2_PRED.items():
        ss = by.get(a, [])
        dis = [s for s in ss if s["requested_arm"] == "disallowed"]
        alw = [s for s in ss if s["requested_arm"] == "allowed"]
        got_dis = sum(1 for s in dis if int(s.get("verified_disallowed", 0)) > 0)
        got_alw = sum(1 for s in alw if int(s.get("verified_allowed", 0)) > 0)
        if not ss:
            v = "not tested in this run (manual sessions descoped on 2026-10-02)"
            res[a] = {"prediction": pred, "verdict": v}
            continue
        if len(dis) < 3 or (pred == "respects" and len(alw) < 3):
            v = "not tested"
        elif pred == "fetches-disallowed":
            v = "supported" if got_dis >= 1 else "falsified"
        else:
            v = "supported" if got_alw >= 1 and got_dis == 0 else (
                "falsified" if got_dis else "inconclusive (allowed page never fetched)")
        v = "exploratory only (not part of the registered tests): " + v   # PROTOCOL §6, H2
        res[a] = {"prediction": pred, "sessions_disallowed": len(dis), "sessions_allowed": len(alw),
                  "sessions_with_verified_disallowed_fetch": got_dis,
                  "sessions_with_verified_allowed_fetch": got_alw, "verdict": v}
    return res


def h3(trap: list[dict]) -> dict:
    linked = {r["site"] for r in trap if r["arm"] == "allowed"}
    cnt = Counter()
    for r in trap:
        if r["site"] not in linked or r["arm"] not in ("allowed", "disallowed") or r["phase"] != "active":
            continue
        if r["bot"] == "(undeclared)":
            continue
        if r["verdict"] == "verified" and r["operator_claim"] == "obeys":
            g = "verified_obeying"
        elif r["verdict"] != "verified":
            g = "unverified_claim"
        else:
            continue
        cnt[(g, r["arm"])] += int(r["requests"])
    a, b = cnt[("unverified_claim", "disallowed")], cnt[("unverified_claim", "allowed")]
    cc, d = cnt[("verified_obeying", "disallowed")], cnt[("verified_obeying", "allowed")]
    out = {"table": {"unverified_claim": {"disallowed": a, "allowed": b},
                     "verified_obeying": {"disallowed": cc, "allowed": d}}}
    if a + b < 10:
        out["verdict"] = "insufficient (fewer than 10 unverified-claim requests to the linked arms)"
        return out
    su = a / (a + b)
    sv = cc / (cc + d) if cc + d else 0.0
    f = st.fisher_exact(a, b, cc, d)
    out.update({"share_unverified": round(su, 4), "share_verified": round(sv, 4), "fisher_p_greater": f["p_greater"]})
    out["verdict"] = "falsified" if su <= sv else ("supported" if f["p_greater"] <= 0.05 else "inconclusive")
    return out


def eligible(ser: list[dict], site: str) -> list[dict]:
    return [r for r in ser if r["site"] == site and r["prospective"] and r["testable"] >= MIN_TESTABLE_PER_WEEK]


def h4(ser: list[dict]) -> dict:
    pts = eligible(ser, "site-a")
    if len(pts) < MIN_WEEKS_TREND:
        return {"weeks": len(pts), "verdict": "insufficient (fewer than 8 eligible prospective weeks)"}
    t = trend(pts, "spoofed_share")
    return {**t, "verdict": "falsified (trend)" if t["p_two"] <= 0.05 else "not falsified (no trend detected; weak evidence)"}


def h5(ser: list[dict]) -> dict:
    out = {"sites": {}}
    for s in ("site-b", "site-c"):
        pts = eligible(ser, s)
        out["sites"][s] = trend(pts, "spoofed_share") if len(pts) >= MIN_WEEKS_TREND else {
            "weeks": len(pts), "S": None, "p_increase": None}
    pooled = defaultdict(Counter)
    for r in ser:
        if r["site"] in ("site-b", "site-c") and r["prospective"]:
            pooled[r["week"]]["spoofed"] += r["spoofed"]
            pooled[r["week"]]["testable"] += r["testable"]
    weeks = sorted(pooled)
    if len(weeks) >= 8:
        f4 = [pooled[w] for w in weeks[:4]]
        l4 = [pooled[w] for w in weeks[-4:]]
        share = lambda xs: sum(x["spoofed"] for x in xs) / max(1, sum(x["testable"] for x in xs))  # noqa: E731
        out["pooled_first4"], out["pooled_last4"] = round(share(f4), 4), round(share(l4), 4)
        diff = share(l4) - share(f4)
    else:
        diff = None
    evaluated = [v for v in out["sites"].values() if v.get("S") is not None]
    if diff is None or not evaluated:
        out["verdict"] = "insufficient"
    elif any(v["p_increase"] <= 0.05 for v in evaluated) and diff >= 0.10:
        out["verdict"] = "supported"
    elif len(evaluated) == 2 and all(v["S"] <= 0 for v in evaluated):
        out["verdict"] = "falsified"
    else:
        out["verdict"] = "inconclusive"
    return out


def h6(ser: list[dict]) -> dict:
    out = {}
    for s in ("site-b", "site-c"):
        pts = [r for r in ser if r["site"] == s and r["prospective"]]
        if len(pts) < MIN_WEEKS_TREND:
            out[s] = {"weeks": len(pts), "verdict": "insufficient"}
            continue
        t = trend(pts, "verified")
        out[s] = {**t, "verdict": "supported" if t["p_increase"] <= 0.05 else "not supported"}
    return out


def tokens_table(tokens: list[dict]) -> list[dict]:
    first, weeks, req = {}, defaultdict(set), Counter()
    for r in tokens:
        t = r["token"]
        first[t] = min(first.get(t, r["week"]), r["week"])
        weeks[t].add(r["week"])
        req[t] += int(r["requests"])
    return [{"token": t, "first_week": first[t], "weeks_seen": len(weeks[t]), "requests": req[t]}
            for t in sorted(first, key=lambda x: (first[x], -req[x]))]


def main(argv=None) -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(prog="s9_analyse")
    ap.add_argument("--weekly-dir", type=Path, default=root / "data" / "weekly")
    ap.add_argument("--out", type=Path, default=root / "data" / "analysis")
    ap.add_argument("--first", default="2026-W41", help="first prospective ISO week (PROTOCOL §10)")
    ap.add_argument("--last", default="2026-W52", help="last prospective ISO week")
    args = ap.parse_args(argv)
    data = load(args.weekly_dir)
    if not data["weeks"]:
        print("no weekly data", file=sys.stderr)
        return 1
    ser, ser_bot = series(data, args.first, args.last)
    lab_rows, trap_bot = trap_tables(data, args.first, args.last)
    write(args.out / "series_by_site_week.csv", ser)
    write(args.out / "series_by_bot_week.csv", ser_bot)
    write(args.out / "trap_labels.csv", lab_rows)
    write(args.out / "trap_by_bot.csv", trap_bot)
    write(args.out / "new_tokens.csv", tokens_table(data["tokens"]))
    hyp = {"H1": h1(trap_bot), "H2": h2(data["active"]), "H3": h3(data["trap"]), "H4": h4(ser),
           "H5": h5(ser), "H6": h6(ser),
           "weeks": sorted(data["weeks"]), "prospective_range": [args.first, args.last]}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "hypotheses.json").write_text(json.dumps(hyp, indent=2, default=str))
    md = ["# S9 — hypotheses, as evaluated by s9_analyse.py", "",
          f"Weeks found: {', '.join(hyp['weeks'])}. Prospective range: {args.first}–{args.last}.", ""]
    md.append("| hypothesis | verdict |\n|---|---|")
    for op, r in hyp["H1"].items():
        md.append(f"| H1 {op} | {r['verdict']} (violations {r['verified_violations']}, control fetches {r['control_fetches']}) |")
    for a, r in hyp["H2"].items():
        md.append(f"| H2 {a} | {r['verdict']} |")
    md.append(f"| H3 | {hyp['H3']['verdict']} |")
    md.append(f"| H4 (site-a) | {hyp['H4']['verdict']} |")
    md.append(f"| H5 (site-b, site-c) | {hyp['H5']['verdict']} |")
    for s, r in hyp["H6"].items():
        md.append(f"| H6 {s} | {r['verdict']} |")
    (args.out / "hypotheses.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
