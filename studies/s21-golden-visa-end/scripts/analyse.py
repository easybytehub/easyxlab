#!/usr/bin/env python3
"""S21 analysis: every published table, from the aggregates in data/ (METHOD.md §1).

Inputs: data/province_quarter.csv, data/value_bands.csv, data/fx_quarter.csv (built by build.py).
Outputs (aggregates only):
- data/windows.csv            four-quarter sums B, A, P per territory and buyer group, and ratios
- data/core_quarterly.csv     Madrid, Barcelona and the rest, quarter by quarter, every group
- data/placebo_dates.csv      the core two's relative rush and falls at 58 earlier dates
- data/event_study.csv        exposure x quarter coefficients (WLS, unit x season and quarter FE)
- data/did_windows.csv        window differences-in-differences across the 19 units
- data/units.csv              the 19 units, their exposures and window counts
- data/price_segment.csv      first-quarter value bands, 2025Q1 against 2026Q1
- data/summary.json           headline numbers
Standard library only.
"""
import csv
import json
import math
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, "scripts"))
from s21lib import (CODE_LABEL, CORE_TWO, OFFICIAL_SIX, GROUPS, qrange, qshift, qindex,  # noqa: E402
                    demean, window_sum, pct, rel_change, rank_p, quantile, wls_fe, wslope,
                    permute_slopes, poisson_ratio_ci)

D = os.path.join(R, "data")
B = qrange("2023Q2", "2024Q1")
A = qrange("2024Q2", "2025Q1")
P = qrange("2025Q2", "2026Q1")
LAST_DEF = "2026Q1"
SHARE_YEARS = qrange("2019Q1", "2023Q4")
ES_RANGE = qrange("2019Q1", LAST_DEF)
MIN_B = 100            # units analysed one by one: at least this many nres_fx purchases in B
POOLED = "RP"          # code of the pooled unit (all other provinces)
HV = ["600-750k", "750-900k", "900-1050k", "over-1050k"]
LV = ["0-150k", "150-300k", "300-450k"]
BUYERS = ["nres_fx", "res_fx", "nres_es", "res_es", "total"]


def load():
    d = {}
    for r in csv.DictReader(open(os.path.join(D, "province_quarter.csv"), encoding="utf-8")):
        d[(r["quarter"], r["code"])] = {g: int(r[g]) for g in GROUPS}
    return d


def series(d, codes, g):
    """Quarter -> sum of group g over the province codes."""
    out = {}
    for (q, c), v in d.items():
        if c in codes:
            out[q] = out.get(q, 0) + v[g]
    return out


def ratios(s):
    b, a, p = window_sum(s, B), window_sum(s, A), window_sum(s, P)
    return {"B": b, "A": a, "P": p, "A_B": a / b if b else None, "P_B": p / b if b else None,
            "P_A": p / a if a else None}


def rel(t, c, num, den):
    """Treated vs comparison change between two windows, in %."""
    return rel_change(window_sum(t, num), window_sum(t, den), window_sum(c, num), window_sum(c, den))


def main():
    d = load()
    provs = sorted(CODE_LABEL)
    allq = sorted({q for q, _ in d})
    S = {"windows": {"B": [B[0], B[-1]], "A": [A[0], A[-1]], "P": [P[0], P[-1]]}}

    # ------------------------------------------------------------ 1.3 windows and the two cities
    terr = {c: [c] for c in provs}
    terr["00"] = ["00"]
    terr["core2"] = CORE_TWO
    terr["rest"] = [c for c in provs if c not in CORE_TWO]
    terr["six"] = OFFICIAL_SIX
    terr["rest6"] = [c for c in provs if c not in OFFICIAL_SIX]
    label = dict(CODE_LABEL, **{"00": "Spain", "core2": "Madrid + Barcelona",
                                "rest": "Spain without Madrid and Barcelona",
                                "six": "official six provinces", "rest6": "Spain without the six"})
    rows = []
    for t, codes in terr.items():
        for g in BUYERS:
            r = ratios(series(d, codes, g))
            rows.append([t, label[t], g, r["B"], r["A"], r["P"]] +
                        [round(100 * (r[k] - 1), 2) if r[k] else "" for k in ("A_B", "P_B", "P_A")])
    with open(os.path.join(D, "windows.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["territory", "label", "group", "B", "A", "P", "pct_A_vs_B", "pct_P_vs_B", "pct_P_vs_A"])
        w.writerows(rows)

    rest = {g: series(d, terr["rest"], g) for g in BUYERS}
    cities = {}
    for name, codes in (("core2", CORE_TWO), ("28", ["28"]), ("08", ["08"])):
        cities[name] = {}
        for g in BUYERS:
            s = series(d, codes, g)
            r = ratios(s)
            rr = ratios(rest[g])
            cities[name][g] = {
                "B": r["B"], "A": r["A"], "P": r["P"],
                "rush_pct": round(100 * (r["A_B"] - 1), 1),
                "net_fall_pct": round(100 * (r["P_B"] - 1), 1),
                "fall_from_rush_pct": round(100 * (r["P_A"] - 1), 1),
                "rest_rush_pct": round(100 * (rr["A_B"] - 1), 1),
                "rest_net_pct": round(100 * (rr["P_B"] - 1), 1),
                "rest_from_rush_pct": round(100 * (rr["P_A"] - 1), 1),
                "rel_rush_pct": round(rel(s, rest[g], A, B), 1),
                "rel_net_pct": round(rel(s, rest[g], P, B), 1),
                "rel_from_rush_pct": round(rel(s, rest[g], P, A), 1),
            }
            if g == "nres_fx":
                c = cities[name][g]
                c["excess_A"] = round(r["A"] - r["B"] * rr["A_B"])
                c["deficit_P"] = round(r["B"] * rr["P_B"] - r["P"])
                lo_hi = poisson_ratio_ci(r["P"], r["B"])
                c["P_B_ci95"] = [round(lo_hi[1], 3), round(lo_hi[2], 3)]
    S["cities"] = cities

    # quarterly view
    with open(os.path.join(D, "core_quarterly.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["quarter", "group", "madrid", "barcelona", "rest", "spain", "provisional"])
        for q in qrange("2019Q1", allq[-1]):
            for g in BUYERS:
                w.writerow([q, g, d[(q, "28")][g], d[(q, "08")][g], rest[g][q], d[(q, "00")][g],
                            1 if q > LAST_DEF else 0])

    # ------------------------------------------------------------ 1.4 placebo dates
    core = series(d, CORE_TWO, "nres_fx")
    rs = rest["nres_fx"]
    pl = []
    for a in qrange("2008Q1", "2022Q2"):
        b_, a_, p_ = qrange(qshift(a, -4), qshift(a, -1)), qrange(a, qshift(a, 3)), qrange(qshift(a, 4), qshift(a, 7))
        pl.append({"announce_q": a, "rel_rush_pct": rel(core, rs, a_, b_),
                   "rel_net_pct": rel(core, rs, p_, b_), "rel_from_rush_pct": rel(core, rs, p_, a_),
                   "spaced": 1 if (qindex(a) - qindex("2008Q1")) % 4 == 0 else 0})
    with open(os.path.join(D, "placebo_dates.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["announce_q", "rel_rush_pct", "rel_net_pct", "rel_from_rush_pct", "spaced"])
        for r in pl:
            w.writerow([r["announce_q"], round(r["rel_rush_pct"], 2), round(r["rel_net_pct"], 2),
                        round(r["rel_from_rush_pct"], 2), r["spaced"]])
    real = cities["core2"]["nres_fx"]
    pd = {}
    for key, side in (("rel_rush_pct", "upper"), ("rel_net_pct", "lower"), ("rel_from_rush_pct", "lower")):
        vals = [r[key] for r in pl]
        sp = [r[key] for r in pl if r["spaced"]]
        pd[key] = {"real": real[key], "n": len(vals), "p": round(rank_p(real[key], vals, side), 4),
                   "n_spaced": len(sp), "p_spaced": round(rank_p(real[key], sp, side), 4),
                   "placebo_min": round(min(vals), 1), "placebo_max": round(max(vals), 1)}
    S["placebo_dates"] = pd

    # ------------------------------------------------------------ units and exposures
    bcount = {c: window_sum(series(d, [c], "nres_fx"), B) for c in provs}
    single = sorted([c for c in provs if bcount[c] >= MIN_B])
    pooled = [c for c in provs if c not in single]
    units = {c: [c] for c in single}
    units[POOLED] = pooled
    ulabel = {c: CODE_LABEL[c] for c in single}
    ulabel[POOLED] = f"rest pooled ({len(pooled)} provinces)"
    bands = {}
    for r in csv.DictReader(open(os.path.join(D, "value_bands.csv"), encoding="utf-8")):
        bands[(r["quarter"], r["code"])] = r
    expo = {}
    for u, codes in units.items():
        nr = sum(d[(q, c)]["nres_fx"] for q in SHARE_YEARS for c in codes)
        tot = sum(d[(q, c)]["total"] for q in SHARE_YEARS for c in codes)
        hv = sum(int(bands[(q, c)][k]) for q in ("2021Q1", "2022Q1") for c in codes for k in HV)
        bt = sum(int(bands[(q, c)]["total"]) for q in ("2021Q1", "2022Q1") for c in codes)
        expo[u] = {"share": nr / tot, "core2": 1.0 if u in CORE_TWO else 0.0,
                   "six": 1.0 if u in OFFICIAL_SIX else 0.0, "hv600": hv / bt}
    useries = {u: series(d, codes, "nres_fx") for u, codes in units.items()}
    rseries = {u: series(d, codes, "res_fx") for u, codes in units.items()}
    with open(os.path.join(D, "units.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["unit", "label", "provinces", "share_nres_fx_2019_2023", "hv600_share_q1_2021_2022",
                    "official_six", "core_two", "B", "A", "P", "res_fx_B", "res_fx_A", "res_fx_P"])
        for u in sorted(units):
            w.writerow([u, ulabel[u], len(units[u]), round(expo[u]["share"], 4), round(expo[u]["hv600"], 4),
                        int(expo[u]["six"]), int(expo[u]["core2"])] +
                       [window_sum(useries[u], x) for x in (B, A, P)] +
                       [window_sum(rseries[u], x) for x in (B, A, P)])
    S["units"] = {"n": len(units), "single": len(single), "pooled_provinces": len(pooled), "min_B": MIN_B}

    # ------------------------------------------------------------ 1.5 event study
    ref = set(B)
    evq = [q for q in ES_RANGE if q not in ref]
    es_rows = []
    es_sum = {}
    for ex in ("share", "core2", "six", "hv600"):
        for weighted in (1, 0):
            y, X, fe_us, fe_q, wts, cl = [], [], [], [], [], []
            for u in sorted(units):
                for q in ES_RANGE:
                    v = useries[u].get(q, 0)
                    if v <= 0:
                        continue
                    y.append(math.log(v))
                    X.append([expo[u][ex] if q == k else 0.0 for k in evq])
                    fe_us.append((u, q[-1]))
                    fe_q.append(q)
                    wts.append(float(bcount_u(useries[u])) if weighted else 1.0)
                    cl.append(u)
            beta, se = wls_fe(y, X, [fe_us, fe_q], wts, cl)
            for k, bb, ss in zip(evq, beta, se):
                es_rows.append([ex, weighted, k, round(bb, 4), round(ss, 4)])
            post = [bb for k, bb in zip(evq, beta) if k in P]
            anti = [bb for k, bb in zip(evq, beta) if k in A]
            pre = [bb for k, bb in zip(evq, beta) if k < B[0]]
            es_sum[f"{ex}_w{weighted}"] = {"mean_beta_A": round(sum(anti) / 4, 4),
                                           "mean_beta_P": round(sum(post) / 4, 4),
                                           "max_abs_pre": round(max(abs(x) for x in pre), 4)}
    with open(os.path.join(D, "event_study.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["exposure", "weighted", "quarter", "beta", "se_cluster_unit"])
        w.writerows(es_rows)
    S["event_study"] = es_sum

    # ------------------------------------------------------------ 1.5 window DiD across units
    did_rows = []
    did = {}
    U = sorted(units)
    for contrast, (n1, n0) in {"A_vs_B": (A, B), "P_vs_B": (P, B), "P_vs_A": (P, A)}.items():
        dy = [math.log(window_sum(useries[u], n1)) - math.log(window_sum(useries[u], n0)) for u in U]
        dr = [math.log(window_sum(rseries[u], n1)) - math.log(window_sum(rseries[u], n0)) for u in U]
        wt = [float(window_sum(useries[u], B)) for u in U]
        for outcome, yy in (("nres_fx", dy), ("nres_fx_minus_res_fx", [a - b for a, b in zip(dy, dr)])):
            for ex in ("share", "core2", "six", "hv600"):
                xs = [expo[u][ex] for u in U]
                for weighted in (1, 0):
                    ww = wt if weighted else [1.0] * len(U)
                    beta, se = wls_fe(yy, [[x] for x in xs], [[0] * len(U)], ww)
                    b0 = wslope(xs, yy, ww)
                    perms = permute_slopes(xs, yy, ww, n=9999, seed=21)
                    p2 = rank_p(b0, perms, "two")
                    did_rows.append([contrast, outcome, ex, weighted, round(b0, 4), round(se[0], 4),
                                     round(p2, 4), len(U)])
                    did[f"{contrast}|{outcome}|{ex}|w{weighted}"] = {"slope": round(b0, 4),
                                                                      "se_hc1": round(se[0], 4),
                                                                      "perm_p_two_sided": round(p2, 4)}
    with open(os.path.join(D, "did_windows.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["contrast", "outcome", "exposure", "weighted", "slope_log_points", "se_hc1",
                    "perm_p_two_sided", "units"])
        w.writerows(did_rows)
    S["did"] = did
    # per-unit window changes, ranked (where did it fall?)
    rank = []
    for u in U:
        rank.append({"unit": u, "label": ulabel[u],
                     "P_vs_B_pct": round(100 * (window_sum(useries[u], P) / window_sum(useries[u], B) - 1), 1),
                     "A_vs_B_pct": round(100 * (window_sum(useries[u], A) / window_sum(useries[u], B) - 1), 1),
                     "P_vs_A_pct": round(100 * (window_sum(useries[u], P) / window_sum(useries[u], A) - 1), 1),
                     "res_fx_P_vs_B_pct": round(100 * (window_sum(rseries[u], P) / window_sum(rseries[u], B) - 1), 1)})
    rank.sort(key=lambda r: r["P_vs_B_pct"])
    S["unit_ranking_P_vs_B"] = rank

    # ------------------------------------------------------------ 1.6 price segment
    ps_rows = []
    for t, codes in list(terr.items()):
        if t in ("six", "rest6"):
            continue
        out = {}
        for q in ("2021Q1", "2022Q1", "2025Q1", "2026Q1"):
            if all((q, c) in bands for c in codes):
                out[q] = {"hv": sum(int(bands[(q, c)][k]) for c in codes for k in HV),
                          "lv": sum(int(bands[(q, c)][k]) for c in codes for k in LV),
                          "tot": sum(int(bands[(q, c)]["total"]) for c in codes)}
        if "2025Q1" in out and "2026Q1" in out:
            a, b = out["2025Q1"], out["2026Q1"]
            ps_rows.append([t, label[t]] + [out[q][k] for q in ("2021Q1", "2022Q1", "2025Q1", "2026Q1")
                                            for k in ("hv", "lv", "tot")] +
                           [round(pct(b["hv"], a["hv"]), 1) if a["hv"] else "",
                            round(pct(b["lv"], a["lv"]), 1) if a["lv"] else ""])
    with open(os.path.join(D, "price_segment.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["territory", "label"] + [f"{q}_{k}" for q in ("2021Q1", "2022Q1", "2025Q1", "2026Q1")
                                            for k in ("ge600k", "lt450k", "all")] +
                   ["pct_ge600k_2026Q1_vs_2025Q1", "pct_lt450k_2026Q1_vs_2025Q1"])
        w.writerows(ps_rows)
    psd = {r[0]: r for r in ps_rows}

    def seg(t):
        r = psd[t]
        return {"ge600k_2025Q1": r[8], "ge600k_2026Q1": r[11], "lt450k_2025Q1": r[9],
                "lt450k_2026Q1": r[12], "pct_ge600k": r[14], "pct_lt450k": r[15],
                "ge600k_2022Q1": r[5]}
    S["price_segment"] = {t: seg(t) for t in ("28", "08", "core2", "rest", "00")}
    for t in ("28", "08"):
        q1 = {q: d[(q, t)]["nres_fx"] for q in ("2025Q1", "2026Q1")}
        S["price_segment"][t]["nres_fx_2025Q1"] = q1["2025Q1"]
        S["price_segment"][t]["nres_fx_2026Q1"] = q1["2026Q1"]

    # ------------------------------------------------------------ 1.7 currency
    fxp = os.path.join(D, "fx_quarter.csv")
    if os.path.exists(fxp):
        fx = {}
        for r in csv.DictReader(open(fxp, encoding="utf-8")):
            fx.setdefault(r["currency"], {})[r["quarter"]] = float(r["eur_rate"])
        curs = ["USD", "GBP", "CNY"]
        missing = [c for c in curs if c not in fx]
        if missing:
            sys.exit(f"data/fx_quarter.csv lacks {missing}: the ECB download failed; "
                     "run `bash scripts/run.sh fetch` again, then `bash scripts/run.sh`")
        idx = {q: sum(math.log(fx[c][q]) for c in curs) / 3 for q in allq if all(q in fx[c] for c in curs)}
        relc = {q: math.log(core[q]) - math.log(rs[q]) for q in allq}
        est = qrange("2010Q1", "2024Q1")
        y = [relc[q] for q in est]
        X = [[idx[q]] for q in est]
        season = [q[-1] for q in est]
        beta, se = wls_fe(y, X, [season], [1.0] * len(est))
        ib = sum(idx[q] for q in B) / 4
        ip = sum(idx[q] for q in P) / 4
        chg = {c: round(100 * (sum(fx[c][q] for q in P) / sum(fx[c][q] for q in B) - 1), 1) for c in curs}
        obs = math.log(window_sum(core, P) / window_sum(rs, P)) - math.log(window_sum(core, B) / window_sum(rs, B))
        S["currency"] = {"pct_change_B_to_P": chg, "index_change_log": round(ip - ib, 4),
                         "elasticity": round(beta[0], 3), "elasticity_se": round(se[0], 3),
                         "implied_log_change": round(beta[0] * (ip - ib), 4),
                         "implied_pct": round(100 * (math.exp(beta[0] * (ip - ib)) - 1), 1),
                         "observed_log_change": round(obs, 4),
                         "observed_pct": round(100 * (math.exp(obs) - 1), 1),
                         "estimation": [est[0], est[-1]]}

    S["additions"] = additions(d, core, rs, pl)
    S["portugal"] = portugal()
    S["post_review"] = post_review(d, core, rs, pl, fx if os.path.exists(fxp) else None, psd)

    json.dump(S, open(os.path.join(D, "summary.json"), "w"), indent=1, ensure_ascii=False)
    c = cities["core2"]["nres_fx"]
    print("core two nres_fx: B %d A %d P %d | rush %+.1f%% net %+.1f%% from rush %+.1f%% | rel net %+.1f%%"
          % (c["B"], c["A"], c["P"], c["rush_pct"], c["net_fall_pct"], c["fall_from_rush_pct"], c["rel_net_pct"]))
    print("placebo dates:", json.dumps(pd))
    print("units:", S["units"])


def bcount_u(s):
    return window_sum(s, B)


# ---------------------------------------------------------------- additions after the freeze (METHOD §9)
PERIODS = [("2014-2017", "2014Q1", "2017Q4"), ("2018-2019", "2018Q1", "2019Q4"),
           ("2020Q2-2022Q1", "2020Q2", "2022Q1"), ("2022Q2-2023Q1", "2022Q2", "2023Q1"),
           ("B", B[0], B[-1]), ("A", A[0], A[-1]), ("P", P[0], P[-1]),
           ("2025Q3-2026Q2 (2026Q2 provisional)", "2025Q3", "2026Q2")]
COVID = set(qrange("2020Q1", "2021Q4"))


def additions(d, core, rs, pl):
    """§9.1 history of the two cities' share; §9.2 placebo dates without pandemic windows;
    §9.3 how sharp the 2025Q1->2025Q2 break is."""
    out = {}
    spain = series(d, ["00"], "nres_fx")
    rows = []
    for name, a, b in PERIODS:
        qs = qrange(a, b)
        n = sum(spain[q] for q in qs)
        for lab, codes in (("Madrid", ["28"]), ("Barcelona", ["08"]), ("Madrid + Barcelona", CORE_TWO)):
            x = sum(d[(q, c)]["nres_fx"] for q in qs for c in codes)
            rows.append([name, lab, len(qs), round(4 * x / len(qs)), round(100 * x / n, 2)])
    with open(os.path.join(D, "history_shares.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["period", "territory", "quarters", "per_year", "share_of_spain_pct"])
        w.writerows(rows)
    out["history_shares"] = {f"{r[0]}|{r[1]}": {"per_year": r[3], "share_pct": r[4]} for r in rows}
    # placebo dates whose windows do not touch 2020Q1-2021Q4
    clean = []
    for r in pl:
        a = r["announce_q"]
        span = set(qrange(qshift(a, -4), qshift(a, 7)))
        if not span & COVID:
            clean.append(r)
    real = {"rel_net_pct": rel(core, rs, P, B), "rel_from_rush_pct": rel(core, rs, P, A),
            "rel_rush_pct": rel(core, rs, A, B)}
    out["placebo_without_pandemic"] = {
        k: {"n": len(clean), "p": round(rank_p(real[k], [r[k] for r in clean], side), 4),
            "placebo_min": round(min(r[k] for r in clean), 1), "placebo_max": round(max(r[k] for r in clean), 1)}
        for k, side in (("rel_net_pct", "lower"), ("rel_from_rush_pct", "lower"), ("rel_rush_pct", "upper"))}
    # the one-quarter break: change in log(core) - log(rest) from Q1 to Q2 of each year
    relq = {q: math.log(core[q]) - math.log(rs[q]) for q in core if q in rs and core[q] > 0}
    br = {y: relq[f"{y}Q2"] - relq[f"{y}Q1"] for y in range(2007, 2026)}
    allq = sorted(relq)
    steps = [relq[allq[i]] - relq[allq[i - 1]] for i in range(1, len(allq)) if allq[i] <= LAST_DEF]
    real_b = br[2025]
    out["break_2025Q2"] = {"log_change": round(real_b, 4), "pct": round(100 * (math.exp(real_b) - 1), 1),
                           "rank_among_Q1_to_Q2_2007_2025": sorted(br.values()).index(real_b) + 1,
                           "n_years": len(br),
                           "p_vs_other_Q1_to_Q2": round(rank_p(real_b, [v for y, v in br.items() if y != 2025], "lower"), 4),
                           "p_vs_all_quarter_steps": round(rank_p(real_b, [x for x in steps if x != real_b], "lower"), 4),
                           "n_steps": len(steps) - 1,
                           "q1_to_q2_by_year": {y: round(v, 3) for y, v in br.items()}}
    return out


def post_review(d, core, rs, pl, fx, psd):
    """Added after the independent review of 2026-10-04 (METHOD §9.7): non-overlapping placebo
    dates; the euro's quarterly moves and differenced currency models; baseline-year numbers;
    the within-territory price contrast; Portugal around DL 14/2021 (1 January 2022)."""
    out = {}
    real = rel(core, rs, P, B)
    # non-overlapping 12-quarter windows, anchored at the last allowed date (2022Q2)
    dates = ["2010Q2", "2013Q2", "2016Q2", "2019Q2", "2022Q2"]
    vals = {r["announce_q"]: r["rel_net_pct"] for r in pl if r["announce_q"] in dates}
    out["placebo_non_overlapping"] = {"dates": {k: round(v, 1) for k, v in vals.items()},
                                      "real": round(real, 1),
                                      "p": round(rank_p(real, list(vals.values()), "lower"), 4),
                                      "min_attainable_p": round(1 / (len(vals) + 1), 4)}
    if fx:
        curs = ["USD", "GBP", "CNY"]
        allq = sorted(q for q in fx["USD"] if all(q in fx[c] for c in curs))
        moves = {}
        for c in ("USD", "CNY", "GBP"):
            ch = {allq[i]: 100 * (fx[c][allq[i]] / fx[c][allq[i - 1]] - 1) for i in range(1, len(allq))
                  if allq[i] >= "2007Q2" and allq[i] <= "2026Q2"}
            ranked = sorted(ch, key=lambda q: -ch[q])
            moves[c] = {"2025Q1": round(fx[c]["2025Q1"], 4), "2025Q2": round(fx[c]["2025Q2"], 4),
                        "pct_2025Q2": round(ch["2025Q2"], 1), "rank_2025Q2_largest_rise": ranked.index("2025Q2") + 1,
                        "n_quarters": len(ch), "next_largest": [[q, round(ch[q], 1)] for q in ranked[:3] if q != "2025Q2"][:2]}
        idx = {q: sum(math.log(fx[c][q]) for c in curs) / 3 for q in allq}
        relc = {q: math.log(core[q]) - math.log(rs[q]) for q in core if q in rs}
        est = qrange("2010Q1", "2024Q1")
        season = [q[-1] for q in est]
        y = [relc[q] for q in est]
        x = [idx[q] for q in est]
        beta, se = wls_fe(y, [[v] for v in x], [season], [1.0] * len(est))
        yd = demean(y, [season], [1.0] * len(est))
        xd = demean(x, [season], [1.0] * len(est))
        e = [a - beta[0] * b for a, b in zip(yd, xd)]
        dw = sum((e[i] - e[i - 1]) ** 2 for i in range(1, len(e))) / sum(v * v for v in e)
        dI = sum(idx[q] for q in P) / 4 - sum(idx[q] for q in B) / 4
        y4 = [relc[q] - relc[qshift(q, -4)] for q in est]
        x4 = [idx[q] - idx[qshift(q, -4)] for q in est]
        b4, s4 = wls_fe(y4, [[v] for v in x4], [[0] * len(est)], [1.0] * len(est))
        y1 = [relc[q] - relc[qshift(q, -1)] for q in est]
        x1 = [idx[q] - idx[qshift(q, -1)] for q in est]
        b1, s1 = wls_fe(y1, [[v] for v in x1], [season], [1.0] * len(est))
        out["currency"] = {"quarterly_moves": moves, "levels_elasticity": round(beta[0], 3),
                           "levels_durbin_watson": round(dw, 2),
                           "levels_implied_pct": round(100 * (math.exp(beta[0] * dI) - 1), 1),
                           "diff4_elasticity": round(b4[0], 2), "diff4_se_hc1": round(s4[0], 2),
                           "diff4_implied_pct": round(100 * (math.exp(b4[0] * dI) - 1), 1),
                           "diff1_elasticity": round(b1[0], 2), "diff1_se_hc1": round(s1[0], 2),
                           "diff1_implied_pct": round(100 * (math.exp(b1[0] * dI) - 1), 1)}
    # baseline year
    spain = series(d, ["00"], "nres_fx")

    def shr(codes, qs):
        return 100 * sum(d[(q, c)]["nres_fx"] for q in qs for c in codes) / sum(spain[q] for q in qs)
    y1819 = qrange("2018Q1", "2019Q4")
    out["baseline"] = {
        "madrid_P": window_sum(series(d, ["28"], "nres_fx"), P),
        "madrid_2019": sum(d[(q, "28")]["nres_fx"] for q in qrange("2019Q1", "2019Q4")),
        "barcelona_share_2019": round(shr(["08"], qrange("2019Q1", "2019Q4")), 2),
        "core_share_change_vs_2018_2019_pct": round(100 * (shr(CORE_TWO, P) / shr(CORE_TWO, y1819) - 1), 1),
        "core_share_change_vs_B_pct": round(100 * (shr(CORE_TWO, P) / shr(CORE_TWO, B) - 1), 1),
        "madrid_share_change_vs_2018_2019_pct": round(100 * (shr(["28"], P) / shr(["28"], y1819) - 1), 1),
        "barcelona_share_change_vs_2018_2019_pct": round(100 * (shr(["08"], P) / shr(["08"], y1819) - 1), 1)}
    # within-territory price contrast: (>= 600k change) - (< 450k change), Madrid against the rest
    m, r_ = psd["28"], psd["rest"]
    dm = float(m[14]) - float(m[15])
    dr = float(r_[14]) - float(r_[15])
    out["price_within"] = {"madrid_pp": round(dm, 1), "rest_pp": round(dr, 1), "gap_pp": round(dm - dr, 1),
                           "gap_purchases": round((dm - dr) / 100 * int(m[8]))}
    out["portugal_2022"] = portugal_2022()
    return out


def portugal_2022():
    """Portugal, national, by buyer's tax domicile, around 1 January 2022, when DL 14/2021 removed
    Lisbon, Porto and the coast from the residential route (published 12 Feb 2021)."""
    p = os.path.join(D, "portugal_quarter.csv")
    if not os.path.exists(p):
        return None
    pt = {}
    for r in csv.DictReader(open(p, encoding="utf-8")):
        if r["region_code"] == "PT" and r["n_transactions"] != "":
            pt[(r["quarter"], r["domicile_group"])] = int(r["n_transactions"])
    qs = sorted({q for q, g in pt if g == "nonEU" and (q, "EU") in pt})
    lr = {q: math.log(pt[(q, "nonEU")]) - math.log(pt[(q, "EU")]) for q in qs}
    steps = {qs[i]: lr[qs[i]] - lr[qs[i - 1]] for i in range(1, len(qs))}
    low = sorted(steps, key=lambda q: steps[q])
    high = sorted(steps, key=lambda q: -steps[q])
    years = {}
    for y in range(int(qs[0][:4]), 2026):
        yq = [f"{y}Q{k}" for k in range(1, 5)]
        if all((q, "nonEU") in pt for q in yq):
            years[y] = {"nonEU": sum(pt[(q, "nonEU")] for q in yq), "EU": sum(pt[(q, "EU")] for q in yq)}
    A_, P_ = qrange("2021Q1", "2021Q4"), qrange("2022Q1", "2022Q4")
    return {"first_quarter": qs[0], "quarters": {q: {"nonEU": pt[(q, "nonEU")], "EU": pt[(q, "EU")]}
                                                for q in qrange("2021Q2", "2022Q3")},
            "step_2021Q4": round(steps["2021Q4"], 3), "step_2022Q1": round(steps["2022Q1"], 3),
            "most_negative_steps": [[q, round(steps[q], 3)] for q in low[:3]],
            "most_positive_steps": [[q, round(steps[q], 3)] for q in high[:3]],
            "n_steps": len(steps), "years": years,
            "rel_2022_vs_2021_pct": round(rel_change(sum(pt[(q, "nonEU")] for q in P_), sum(pt[(q, "nonEU")] for q in A_),
                                                     sum(pt[(q, "EU")] for q in P_), sum(pt[(q, "EU")] for q in A_)), 1)}


def portugal():
    """Portugal (INE, indicator 0012785): transactions by buyer's tax domicile. Plan announced 16 Feb 2023
    (2023Q1); real-estate route ended by Lei 56/2023 from 7 Oct 2023 (2023Q4). Windows: B = 2022Q1-Q4,
    A = 2023Q1-Q3 against 2022Q1-Q3, P = 2023Q4-2024Q3 against B."""
    p = os.path.join(D, "portugal_quarter.csv")
    if not os.path.exists(p):
        return None
    pt = {}
    for r in csv.DictReader(open(p, encoding="utf-8")):
        if r["n_transactions"] != "":
            pt[(r["quarter"], r["region_code"], r["domicile_group"])] = int(r["n_transactions"])
    regions = {"PT": "Portugal", "1A": "Grande Lisboa", "11": "Norte", "15": "Algarve", "1B": "Península de Setúbal"}
    PB = qrange("2022Q1", "2022Q4")
    PA, PA0 = qrange("2023Q1", "2023Q3"), qrange("2022Q1", "2022Q3")
    PP = qrange("2023Q4", "2024Q3")
    out, rows = {}, []
    for code, lab in regions.items():
        ser = {g: {q: pt.get((q, code, g)) for q in {k[0] for k in pt}} for g in ("nonEU", "EU", "PT", "total")}
        if any(v is None for q in PB + PP for v in [ser["nonEU"].get(q), ser["EU"].get(q)]):
            continue
        res = {}
        for g in ("nonEU", "EU", "PT", "total"):
            b, pp = window_sum(ser[g], PB), window_sum(ser[g], PP)
            a, a0 = window_sum(ser[g], PA), window_sum(ser[g], PA0)
            res[g] = {"B": b, "P": pp, "P_vs_B_pct": round(pct(pp, b), 1), "A_vs_sameQ_2022_pct": round(pct(a, a0), 1)}
            rows.append([lab, code, g, b, pp, res[g]["P_vs_B_pct"], a0, a, res[g]["A_vs_sameQ_2022_pct"]])
        res["nonEU_vs_EU_P_vs_B_pct"] = round(rel_change(res["nonEU"]["P"], res["nonEU"]["B"], res["EU"]["P"], res["EU"]["B"]), 1)
        res["nonEU_vs_EU_A_pct"] = round(rel_change(window_sum(ser["nonEU"], PA), window_sum(ser["nonEU"], PA0),
                                                    window_sum(ser["EU"], PA), window_sum(ser["EU"], PA0)), 1)
        # placebo end dates: same contrast for end quarters 2010Q4..2021Q4 (windows end before 2023Q1)
        plac = []
        for e in qrange("2010Q1", "2021Q4"):
            b_ = qrange(qshift(e, -7), qshift(e, -4))
            p_ = qrange(e, qshift(e, 3))
            if qshift(e, 3) >= "2023Q1":
                continue
            try:
                plac.append(rel_change(window_sum(ser["nonEU"], p_), window_sum(ser["nonEU"], b_),
                                       window_sum(ser["EU"], p_), window_sum(ser["EU"], b_)))
            except (TypeError, ZeroDivisionError, ValueError):
                pass
        res["placebo_n"] = len(plac)
        res["placebo_p_lower"] = round(rank_p(res["nonEU_vs_EU_P_vs_B_pct"], plac, "lower"), 4) if plac else None
        res["placebo_min"] = round(min(plac), 1) if plac else None
        out[code] = res
    with open(os.path.join(D, "portugal_windows.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["region", "code", "domicile", "B_2022", "P_2023Q4_2024Q3", "pct_P_vs_B",
                    "2022Q1_Q3", "2023Q1_Q3", "pct_2023Q1_Q3_vs_2022"])
        w.writerows(rows)
    return out


if __name__ == "__main__":
    main()
