#!/usr/bin/env python3
"""Build every S7 table from the PUBLISHED files only (no raw answers needed):
data/answers.csv, data/citations.csv, data/facts.json, data/review_agent.csv, data/fn_check.csv,
data/second_reader_sample.csv + data/second_reader.csv, data/error_attribution_r*.csv, data/page_checks_r*.csv.

Scored set = every fact except F16, which is reported separately as a case study (its rule moved twice in the
48 hours before collection). "Wrong" = outdated + mixed + incorrect (final verdict, i.e. after the AI agent's
re-reading); the regex-only count is reported next to it.

Writes data/summary.json, data/by_fact.csv, data/by_area.csv, data/by_age.csv, data/citation_types.csv,
data/stability.csv, data/f16_case.csv. Stdlib only.
"""
import csv, json, math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
WRONG = ("outdated", "mixed", "incorrect")
CASE = "F16"
OFFICIAL = ("boe", "aeat", "social_security", "other_public")
SOCIAL = ("youtube.com", "m.youtube.com", "facebook.com", "m.facebook.com", "instagram.com")


def wilson(k, n, z=1.96):
    if not n:
        return [None, None]
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1)]


def pct(k, n):
    return round(100 * k / n, 1) if n else None


def rows(name):
    return list(csv.DictReader(open(D / name, encoding="utf-8")))


def write(name, rs):
    if rs:
        with open(D / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rs[0])); w.writeheader(); w.writerows(rs)


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0, round(100 * po, 1)


def main():
    facts = {f["id"]: f for f in json.load(open(D / "facts.json", encoding="utf-8"))}
    A_all = rows("answers.csv")
    for a in A_all:
        a["reading"] = int(a["reading"]); a["has_answer"] = a["has_answer"] == "True"
        a["cites_boe"] = a["cites_boe"] == "True"; a["cites_official"] = a["cites_official"] == "True"
    A = [a for a in A_all if a["fact_id"] != CASE]
    ans = [a for a in A if a["has_answer"]]
    readings = sorted({a["reading"] for a in A})
    S = {"responses_total": len(A_all), "responses_scored": len(A), "facts_scored": len({a["fact_id"] for a in A}),
         "queries_scored": len({a["qid"] for a in A}), "readings": {}, "pooled": {}}
    for n in readings:
        S["readings"][n] = {}
        for s in ("aio", "mode"):
            xs = [a for a in A if a["reading"] == n and a["surface"] == s]
            an = [a for a in xs if a["has_answer"]]
            k = Counter(a["final_verdict"] for a in an)
            S["readings"][n][s] = {"queries": len(xs), "answered": len(an), "presence_pct": pct(len(an), len(xs)),
                                   "final": {v: k.get(v, 0) for v in ("current", "mixed", "outdated", "incorrect", "not_stated")},
                                   "wrong": sum(k[v] for v in WRONG),
                                   "rule_flagged": sum(a["rule_verdict"] in ("outdated", "mixed") for a in an),
                                   "first_utc": min(a["fetched_at"] for a in xs), "last_utc": max(a["fetched_at"] for a in xs)}
    for s in ("aio", "mode"):
        an = [a for a in ans if a["surface"] == s]
        k = Counter(a["final_verdict"] for a in an)
        w = sum(k[v] for v in WRONG); t = k["outdated"] + k["mixed"]
        S["pooled"][s] = {
            "answered": len(an), "wrong": w, "wrong_pct": pct(w, len(an)), "wrong_ci95": wilson(w, len(an)),
            "temporal_wrong": t, "temporal_wrong_pct": pct(t, len(an)), "temporal_ci95": wilson(t, len(an)),
            "final": dict(k), "current_pct": pct(k["current"], len(an)),
            "rule_only_wrong": sum(a["rule_verdict"] in ("outdated", "mixed") for a in an),
            "distinct_pairs_with_error": len({a["qid"] for a in an if a["final_verdict"] in WRONG}),
            "wrong_without_invoicing": sum(a["final_verdict"] in WRONG for a in an if a["fact_id"] not in ("F26", "F27", "F28")),
            "answered_without_invoicing": sum(1 for a in an if a["fact_id"] not in ("F26", "F27", "F28")),
            "cites_boe_pct": pct(sum(a["cites_boe"] for a in an), len(an)),
            "cites_official_pct": pct(sum(a["cites_official"] for a in an), len(an)),
            "wrong_if_official": [sum(a["final_verdict"] in WRONG for a in an if a["cites_official"]), sum(a["cites_official"] for a in an)],
            "wrong_if_not_official": [sum(a["final_verdict"] in WRONG for a in an if not a["cites_official"]), sum(not a["cites_official"] for a in an)]}
    S["pooled"]["aio"]["presence_range_pct"] = [min(S["readings"][n]["aio"]["presence_pct"] for n in readings),
                                                 max(S["readings"][n]["aio"]["presence_pct"] for n in readings)]
    S["errors"] = [{k: a[k] for k in ("reading", "qid", "fact_id", "surface", "rule_verdict", "final_verdict", "extract")}
                   for a in sorted(ans, key=lambda a: (a["fact_id"], a["qid"], a["surface"], a["reading"])) if a["final_verdict"] in WRONG]

    # F16 case study, per reading and surface
    f16 = []
    for n in readings:
        for s in ("aio", "mode"):
            xs = [a for a in A_all if a["fact_id"] == CASE and a["reading"] == n and a["surface"] == s]
            k = Counter(a["final_verdict"] for a in xs)
            f16.append({"reading": n, "surface": s, "first_utc": min(a["fetched_at"] for a in xs),
                        **{v: k.get(v, 0) for v in ("current", "outdated", "mixed", "not_stated", "no_answer")}})
    write("f16_case.csv", f16)
    S["f16_case"] = f16

    # agent review and false-negative check
    rv = rows("review_agent.csv")
    S["review"] = {"items": len(rv), "flagged": sum(r["scope"] == "flagged" for r in rv),
                   "flagged_confirmed": sum(r["scope"] == "flagged" and r["agent_verdict"] in WRONG for r in rv),
                   "full_review_items": sum(r["scope"] != "flagged" for r in rv),
                   "full_review_new_errors": sum(r["scope"] != "flagged" and r["agent_verdict"] in WRONG for r in rv),
                   "changes": dict(Counter(f"{r['rule_verdict']}->{r['agent_verdict']}" for r in rv if r["rule_verdict"] != r["agent_verdict"]))}
    fn = rows("fn_check.csv")
    miss = sum(r["agent_verdict"] in WRONG for r in fn)
    S["fn_check"] = {"n": len(fn), "missed_errors": miss, "ci95": wilson(miss, len(fn)), "seed": 20261003,
                     "pool": "answered, rule verdict current/not_stated, facts not fully re-read (all except F14 F15 F16 F21 F25 F28)"}

    # second reader v2
    if (D / "second_reader.csv").exists():
        smp = {r["item"]: r for r in rows("second_reader_sample.csv")}
        fin = {(str(a["reading"]), a["qid"], a["surface"]): a["final_verdict"] for a in A_all}
        pairs = defaultdict(list)
        for r in rows("second_reader.csv"):
            m = smp[r["item"]]
            pairs[m["stratum"]].append((fin[(m["reading"], m["qid"], m["surface"])], r["second_reader_verdict"].strip()))
        allp = [p for v in pairs.values() for p in v]
        k5, ag = kappa(allp)
        kb, agb = kappa([(a in WRONG, b in WRONG) for a, b in allp])
        S["second_reader"] = {"n": len(allp), "agreement_pct": ag, "kappa": k5, "binary_wrong_agreement_pct": agb,
                              "binary_wrong_kappa": kb,
                              "per_stratum": {st: {"n": len(v), "agreement_pct": pct(sum(a == b for a, b in v), len(v)),
                                                   "binary_agreement_pct": pct(sum((a in WRONG) == (b in WRONG) for a, b in v), len(v)),
                                                   "disagreements": dict(Counter(f"{a}->{b}" for a, b in v if a != b))}
                                              for st, v in sorted(pairs.items())}}

    # per fact / area / age
    bf = []
    for fid, f in facts.items():
        r = {"fact_id": fid, "area": f["area"], "topic": f["topic"], "in_force_since": f["since"],
             "days_before_2026_10_02": (date(2026, 10, 2) - date.fromisoformat(f["since"])).days if f["since"][:1].isdigit() else ""}
        for s in ("aio", "mode"):
            xs = [a for a in A_all if a["fact_id"] == fid and a["surface"] == s]
            k = Counter(a["final_verdict"] for a in xs)
            for v in ("current", "mixed", "outdated", "incorrect", "not_stated", "no_answer"):
                r[f"{s}_{v}"] = k.get(v, 0)
        bf.append(r)
    write("by_fact.csv", bf)
    def bucket(fid):
        d = next(r["days_before_2026_10_02"] for r in bf if r["fact_id"] == fid)
        return "no change (control F05)" if d == "" else ("< 6 months" if d < 183 else ("6-12 months" if d < 366 else "> 12 months"))
    for key, fn_, name in (("area", lambda a: a["area"], "by_area.csv"), ("age", lambda a: bucket(a["fact_id"]), "by_age.csv")):
        out = []
        for g in sorted({fn_(a) for a in ans}):
            for s in ("aio", "mode"):
                xs = [a for a in ans if fn_(a) == g and a["surface"] == s]
                w = sum(a["final_verdict"] in WRONG for a in xs)
                out.append({key: g, "surface": s, "facts": len({a["fact_id"] for a in xs}), "answers": len(xs),
                            "wrong": w, "wrong_pct": pct(w, len(xs)), "ci95": wilson(w, len(xs))})
        write(name, out)

    # citations (scored facts only; F16 reported apart)
    cites = [c for c in rows("citations.csv") if c["fact_id"] != CASE]
    ct = []
    for s in ("aio", "mode"):
        xs = [c for c in cites if c["surface"] == s]
        for t, k in Counter(c["type"] for c in xs).most_common():
            ct.append({"surface": s, "type": t, "references": k, "pct": pct(k, len(xs))})
        S["pooled"][s].update({"references": len(xs), "distinct_domains": len({c["domain"] for c in xs}),
                               "forum_social_pct": pct(sum(c["type"] == "forum_social" for c in xs), len(xs)),
                               "yt_fb_ig_pct": pct(sum(c["domain"] in SOCIAL for c in xs), len(xs)),
                               "top_domains": Counter(c["domain"] for c in xs).most_common(8)})
    write("citation_types.csv", ct)

    # stability
    st, by = [], defaultdict(dict)
    for a in A:
        by[(a["qid"], a["surface"])][a["reading"]] = a["final_verdict"]
    for (q, s), d in sorted(by.items()):
        st.append({"qid": q, "surface": s, **{f"r{n}": d.get(n, "") for n in readings}, "same_all": len(set(d.values())) == 1})
    write("stability.csv", st)
    S["stability"] = {s: {"pairs": sum(r["surface"] == s for r in st), "same_pct": pct(sum(r["same_all"] for r in st if r["surface"] == s),
                                                                                     sum(r["surface"] == s for r in st))} for s in ("aio", "mode")}

    # page checks (online step, scripts/check_pages.py)
    att = []
    for f in sorted(D.glob("error_attribution_r*.csv")):
        att += rows(f.name)
    tg = [x for x in att if x["group"] == "target"]
    pages = []
    for f in sorted(D.glob("page_checks_r*.csv")):
        pages += rows(f.name)
    states = defaultdict(list)
    for x in pages:
        if x["group"] == "target":
            states[(x["reading"], x["qid"], x["surface"])].append(x["page_state"])
    three = Counter()
    for k, v in states.items():
        if "page_old" in v:
            three["a cited page states only the superseded rule"] += 1
        elif "page_mixed" in v:
            three["a cited page states both (ambiguous)"] += 1
        elif "page_current" in v:
            three["cited pages state only the current rule"] += 1
        else:
            three["pages silent on the rule or unreadable (undetermined)"] += 1
    S["page_check"] = {"errors_checked": len(tg), "strict": dict(Counter(x["attribution"] for x in tg)), "three_way": dict(three),
                       "distinct_texts_note": "identical answers in two readings are counted once per reading",
                       "control_n": sum(x["group"] == "control" for x in att),
                       "control_strict_in_source": sum(x["group"] == "control" and x["attribution"] == "in_source" for x in att),
                       "control_loose_in_source": sum(x["group"] == "control" and x.get("attribution_loose") == "in_source" for x in att)}
    (D / "summary.json").write_text(json.dumps(S, ensure_ascii=False, indent=1))
    print(json.dumps(S["pooled"], ensure_ascii=False)[:1800])


if __name__ == "__main__":
    main()
