"""S12 step 4 (after the §7 freeze and the independent review): checks the review asked for.

Nothing here changes a registered result. The frozen files (build.py, dq.py, analyse.py, s12lib.py
and their outputs in data/) are only imported and read. Every number written here is labelled either
"registered, run as written" (S3 with Madrid) or "exploratory, post-review".

Writes data/review_checks.json and data/review_slopes.csv.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

import analyse as A
from s12lib import DATA, load_json, read_csv, wls, write_csv, write_json

S = A.S
T1, T0 = "2026Q1", "2025Q4"


def g(sid, p, t):
    vals = [A.Y(sid, p, t), A.Y(sid, p, A.qs(t, -4))]
    if any(v is None or v <= 0 for v in vals):
        return None
    return math.log(vals[0]) - math.log(vals[1])


def same_sample(test_name):
    """Provinces used by a frozen test = all provinces minus those excluded for it."""
    excl = {r["province"] for r in read_csv(DATA / "exclusions.csv") if r["test"] == test_name}
    return [p for p in A.PROVS if p not in excl]


def slope(name, provs, outcome, cols=("W3", "W2"), direction=-1, permute=False):
    """Same estimator as the frozen xtest, on a fixed set of provinces."""
    drop = tuple(p for p in A.PROVS if p not in provs)
    return A.xtest(name, "derived", T1, cols, direction, drop=drop, outcome=outcome, permute=permute,
                   tag="post-review")


def main():
    out, rows = {}, []

    # 1. S3 as registered: also drop Madrid (its Q1-2026 rent/«otros» split is «*Dato estimado»).
    flagged = {n["series_province"] for n in A.NOTES if n["release"] in ("2025Q4", "2026Q1")}
    s3 = A.xtest("H1a S3 as registered (flagged provinces and Madrid dropped)", "P-TOT", T1, ("W3", "W2"), -1,
                 drop=tuple(sorted(flagged | {"MADRID"})), permute=True, tag="post-review")
    s3_madrid_only = A.xtest("H1a without Madrid only", "P-TOT", T1, ("W3", "W2"), -1, drop=("MADRID",),
                             permute=False, tag="post-review")
    out["S3_registered"] = {k: s3[k] for k in ("b", "se_hc3", "n", "p_one_sided", "p_perm")}
    out["S3_registered"]["dropped"] = sorted(flagged | {"MADRID"})
    out["H1a_without_Madrid_only"] = {k: s3_madrid_only[k] for k in ("b", "se_hc3", "n", "p_one_sided")}
    rows += [s3, s3_madrid_only]

    # 2. Where do H1a, H2, H3 and the SC-REC test come from? Split Δg(Q1-26) = g(Q1-26) − g(Q4-25)
    #    and regress each part on (W3, W2), on the same provinces as the frozen test.
    def ratio_g(p, t):
        a, b = g("P-TOT", p, t), g("SC-POS", p, t)
        return None if a is None or b is None else a - b
    splits = {}
    for test, sid in (("H1a", "P-TOT"), ("H2", "SC-POS"), ("H2-SC-REC (exploratory)", "SC-REC"), ("H3", None)):
        provs = same_sample(test)
        parts = {}
        for label, t in (("g_2026Q1", T1), ("g_2025Q4", T0)):
            fn = (lambda p, t=t: ratio_g(p, t)) if sid is None else (lambda p, t=t, sid=sid: g(sid, p, t))
            r = slope(f"{test}: slope of {label}", provs, fn)
            parts[label] = {"b": r["b"], "se_hc3": r["se_hc3"], "p_two_sided": r["p_two_sided"], "n": r["n"]}
            rows.append(r)
        splits[test] = parts
    out["delta_g_split"] = splits

    # 3. Exploratory placebo inside the reform window: Δg(2025-Q4) on (W3, W2), the quarter before
    #    phase 3 was transformed (phase 2 moves from −1 to 0, phase 1 from 0 to 1).
    pre = {}
    for sid in ("P-TOT", "SC-POS", "SC-REC"):
        r = A.xtest(f"placebo-in-window Δg(2025Q4) {sid}", sid, "2025Q4", ("W3", "W2"), -1, permute=True,
                    tag="post-review", extra_filter=A.sc_covered if sid.startswith("SC") else None)
        pre[sid] = {k: r[k] for k in ("b", "se_hc3", "n", "p_two_sided", "p_perm")}
        rows.append(r)
    out["placebo_2025Q4_exploratory"] = pre

    # 4. The common-service series around the transformation.
    nat = S["SC-REC"]["TOTAL"], S["SC-POS"]["TOTAL"], S["P-TOT"]["TOTAL"]
    out["national_yoy"] = {
        sid: {q: S[sid]["TOTAL"][q] / S[sid]["TOTAL"][A.qs(q, -4)] - 1 for q in ("2025Q4", "2026Q1")}
        for sid in ("SC-REC", "SC-POS", "P-TOT")}
    out["national_yoy_pooled_Q4_Q1"] = {
        sid: (S[sid]["TOTAL"]["2025Q4"] + S[sid]["TOTAL"]["2026Q1"])
             / (S[sid]["TOTAL"]["2024Q4"] + S[sid]["TOTAL"]["2025Q1"]) - 1
        for sid in ("SC-REC", "SC-POS", "P-TOT")}
    out["province_detail"] = {
        p: {sid: {q: S[sid][p][q] for q in ("2024Q4", "2025Q1", "2025Q4", "2026Q1")}
            for sid in ("P-TOT", "P-LAU", "SC-REC", "SC-POS")}
        for p in ("MADRID", "LAS PALMAS", "BARCELONA")}

    # 5. Leave Las Palmas out of H1a (264 → 18 in one quarter, not flagged by the CGPJ).
    lp = A.xtest("H1a without Las Palmas", "P-TOT", T1, ("W3", "W2"), -1, drop=("LAS PALMAS",), permute=False,
                 tag="post-review")
    out["H1a_without_Las_Palmas"] = {k: lp[k] for k in ("b", "se_hc3", "n", "p_one_sided")}
    rows.append(lp)

    # 6. H5 where the 2025 district file is within 5% of the province series, and by direction.
    dq1 = read_csv(DATA / "dq1_district_vs_province.csv")
    diff = {r["province"]: float(r["difference"]) for r in dq1 if r["year"] == "2025" and r["series"] == "P-TOT"}
    ser = {p: sum(S["P-TOT"][p][f"2025Q{k}"] for k in range(1, 5)) for p in A.PROVS}
    rel = {p: diff.get(p, 0.0) / ser[p] for p in A.PROVS}
    out["H5_by_consistency"] = {
        "within_5pct": h5_subset({p for p in A.PROVS if abs(rel[p]) <= 0.05}),
        "district_file_below_series": h5_subset({p for p in A.PROVS if rel[p] < -0.05}),
        "district_file_above_series": h5_subset({p for p in A.PROVS if rel[p] > 0.05}),
    }

    # 7. Registered results the paper did not show, collected here for the text.
    pooled = load_json(DATA / "pooled_model.json")
    out["S7_poisson_levels_rho"] = pooled["S7_poisson_levels_rho"]
    tests = {r["test"]: r for r in read_csv(DATA / "tests.csv")}
    out["PC_MON_H1b"] = {k: float(tests["PC-MON on H1b model"][k]) for k in ("b", "se_hc3", "p_two_sided")}
    dq = load_json(DATA / "dq_summary.json")
    out["DQ8"] = dq["DQ8"]
    hist = sorted((v, q) for q, v in S["P-TOT"]["TOTAL"].items() if "2013Q1" <= q <= "2025Q4")
    out["lowest_earlier_quarters"] = [{"quarter": q, "value": v} for v, q in hist[:3]]
    # Ávila: phase 3 by complement, in Ministry-managed territory, absent from the MJU phase-3 sheet.
    d = [r for r in A.DISTRICTS if r["phase"] == 3 and not r["in_mju_phase3_sheet"]
         and r["province"] in ("AVILA", "BURGOS", "LEON", "PALENCIA", "SALAMANCA", "SEGOVIA", "SORIA", "VALLADOLID",
                               "ZAMORA", "ALBACETE", "CIUDAD REAL", "CUENCA", "GUADALAJARA", "TOLEDO", "BADAJOZ",
                               "CACERES", "MURCIA", "ILLES BALEARS", "CEUTA", "MELILLA")]
    out["mju_territory_phase3_not_in_sheet"] = [r["district"] for r in d]

    write_json(DATA / "review_checks.json", out)
    write_csv(DATA / "review_slopes.csv", rows)
    print(f"S3 registered: b {s3['b']:.3f}, p {s3['p_one_sided']:.3f}, perm {s3['p_perm']:.3f}, n {s3['n']}")
    print(f"placebo Δg(2025Q4) P-TOT: b {pre['P-TOT']['b']:.3f}, p2 {pre['P-TOT']['p_two_sided']:.3f}")


def h5_subset(provs):
    """H5 (2025) restricted to districts whose series province is in `provs`; same estimator as analyse.h5."""
    flagged = {(f["district"], f["year"]) for f in A.P["dq1_outliers"]}
    rows = []
    for r in A.DISTRICTS:
        if r["series_province"] not in provs:
            continue
        if any((r["district"], y) in flagged for y in (2023, 2024, 2025)):
            continue
        v = [r.get(f"tot_{y}") for y in (2023, 2024, 2025)]
        if any(x is None for x in v) or v[0] + v[1] <= 0:
            continue
        rows.append((r["province"], r["phase"], math.log(v[2] + 1) - math.log(v[1] + 1), v[0] + v[1]))
    pv = sorted({r[0] for r in rows})
    pi = {p: i for i, p in enumerate(pv)}
    n = len(rows)
    X = np.zeros((n, 2 + len(pv)))
    for i, (p, ph, _, _) in enumerate(rows):
        X[i, 0], X[i, 1], X[i, 2 + pi[p]] = ph == 1, ph == 2, 1
    keep = np.any(X != 0, axis=0)
    X = X[:, keep]
    y = np.array([r[2] for r in rows])
    w = np.array([r[3] for r in rows])
    sw = np.sqrt(w)
    Xs, ys = X * sw[:, None], y * sw
    XtXi = np.linalg.pinv(Xs.T @ Xs)
    beta = XtXi @ Xs.T @ ys
    e = ys - Xs @ beta
    cl = np.array([pi[r[0]] for r in rows])
    G = len(pv)
    meat = sum(np.outer(Xs[cl == k].T @ e[cl == k], Xs[cl == k].T @ e[cl == k]) for k in range(G))
    k = np.linalg.matrix_rank(Xs)
    V = XtXi @ meat @ XtXi * (G / (G - 1)) * ((n - 1) / (n - k))
    se = float(np.sqrt(V[0, 0]))
    return {"delta1": float(beta[0]), "se": se, "pct": math.exp(beta[0]) - 1, "n_districts": n,
            "n_provinces": G, "p_one_sided": float(stats.t.cdf(beta[0] / se, G - 1))}


if __name__ == "__main__":
    main()
