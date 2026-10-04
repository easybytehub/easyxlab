"""S12 step 3: the registered tests (PROTOCOL.md §5-§8) on the locked data, and the frozen Q2-2026 predictions.

Reads work/panel.json, data/province_exposure.csv, data/cgpj_notes.csv, data/dq_summary.json.
Writes (aggregates only):
  data/tests.csv                  every regression: hypothesis, sample, coefficient, SE, p-values, n
  data/sensitivity.csv            S1-S11
  data/exclusions.csv             DQ9: provinces excluded from each test by the small-count rule
  data/pooled_model.json          §6.2 staggered model, bootstrap intervals, anticipation test
  data/decomposition.json         §6.4 components and the record-low verdict
  data/h5_years.csv               H5 and its placebo years
  data/predictions_q2_2026.csv    §7 frozen predictions (one row per province)
  data/predictions_q2_2026_spec.json  how the Q2-2026 test and scoring will be computed
  data/summary.json               verdicts
Random seeds are fixed; every number is reproducible from the locked inputs.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict

import numpy as np
from scipy import optimize, stats

from s12lib import DATA, PHASE_QUARTER, WORK, load_json, q_index, q_label, read_csv, wls, write_csv, write_json

SEED = 20261004
N_PERM = 10_000
N_BOOT = 2_000
MIN_COUNT = 10
ALPHA = 0.05

P = load_json(WORK / "panel.json")
S = P["province_series"]
DISTRICTS = P["districts"]
EXPO = {r["province"]: {k: (float(v) if k not in ("province", "label") else v) for k, v in r.items()}
        for r in read_csv(DATA / "province_exposure.csv")}
PROVS = sorted(EXPO)
NOTES = read_csv(DATA / "cgpj_notes.csv")
DQ = load_json(DATA / "dq_summary.json")
EXCLUSIONS = []


def qs(t: str, d: int) -> str:
    return q_label(q_index(t) + d)


# ----------------------------------------------------------------------------- outcomes
def Y(sid, p, t, override=None):
    if override and (sid, p, t) in override:
        return override[(sid, p, t)]
    return S[sid][p].get(t)


def dg(sid, p, t, eps=0.0, override=None):
    """Δg_p(t) = [ln Y_t − ln Y_{t−4}] − [ln Y_{t−1} − ln Y_{t−5}]."""
    vals = [Y(sid, p, qs(t, d), override) for d in (0, -4, -1, -5)]
    if any(v is None for v in vals) or any(v + eps <= 0 for v in vals):
        return None
    a, b, c, d = (math.log(v + eps) for v in vals)
    return (a - b) - (c - d)


def counts_ok(sid, p, t, override=None):
    vals = [Y(sid, p, qs(t, d), override) for d in (0, -4, -1, -5)]
    return all(v is not None and v >= MIN_COUNT for v in vals)


def sc_covered(p):
    return all((S["SC-REC"][p].get(q) or 0) > 0 for q in [q_label(i) for i in range(q_index("2024Q1"), q_index("2026Q1") + 1)])


# ----------------------------------------------------------------------------- regression
def xtest(name, sid, t, cols, direction, *, weights="B", eps=0.0, drop=(), extra_filter=None, override=None,
          wvar="", outcome=None, permute=True, min_count=True, tag="primary"):
    """Cross-province test: Δg_p(t) = a + Σ b_c W_c,p + u_p; coefficient of interest = cols[0]."""
    rows, excl = [], []
    for p in PROVS:
        if p in drop:
            continue
        if extra_filter and not extra_filter(p):
            excl.append((p, "filter"))
            continue
        if outcome is None:
            if min_count and not counts_ok(sid, p, t, override):
                excl.append((p, "count<10"))
                continue
            v = dg(sid, p, t, eps, override)
        else:
            v = outcome(p)
            if v is None:
                excl.append((p, "count<10 in either series, or undefined"))
                continue
        if v is None:
            excl.append((p, "undefined"))
            continue
        rows.append((p, v))
    for p, why in excl:
        EXCLUSIONS.append({"test": name, "tag": tag, "province": p, "reason": why})
    n = len(rows)
    y = np.array([v for _, v in rows])
    X = np.column_stack([np.ones(n)] + [[EXPO[p][f"{c}{wvar}"] for p, _ in rows] for c in cols])
    w = np.array([EXPO[p]["B_2024"] if weights == "B" else 1.0 for p, _ in rows])
    beta, se, df = wls(y, X, w)
    b, s = beta[1], se[1]
    tval = b / s if s > 0 else float("nan")
    p_one = stats.t.cdf(tval, df) if direction < 0 else stats.t.sf(tval, df)
    p_two = 2 * stats.t.sf(abs(tval), df)
    tcrit = stats.t.ppf(0.95, df)
    out = {"test": name, "tag": tag, "series": sid if outcome is None else "derived", "quarter": t,
           "coef": cols[0], "direction": "-" if direction < 0 else "+", "b": b, "se_hc3": s, "df": df, "n": n,
           "p_one_sided": p_one, "p_two_sided": p_two,
           "lower_one_sided_95": b - tcrit * s, "upper_one_sided_95": b + tcrit * s,
           "ci95_low": b - stats.t.ppf(0.975, df) * s, "ci95_high": b + stats.t.ppf(0.975, df) * s,
           "rho": math.exp(b) - 1, "weights": weights, "intercept": beta[0]}
    if permute:
        rng = np.random.default_rng(SEED)
        Wm = X[:, 1:].copy()
        sw = np.sqrt(w)
        hits = 0
        for _ in range(N_PERM):
            idx = rng.permutation(n)
            Xp = np.column_stack([np.ones(n), Wm[idx]])
            Xs = Xp * sw[:, None]
            bp = np.linalg.lstsq(Xs, y * sw, rcond=None)[0][1]
            hits += (bp <= b) if direction < 0 else (bp >= b)
        out["p_perm"] = (1 + hits) / (1 + N_PERM)
    return out


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


# ----------------------------------------------------------------------------- exposures by event time
def district_weights(var="w"):
    out = defaultdict(list)
    for r in DISTRICTS:
        out[r["series_province"]].append((r["phase"], r[var]))
    return out


DW = district_weights()
KBINS_LEADS = (-2, -1, 0, 1, 2)
KBINS = (0, 1, 2)


def exposure(p, t, kbins, dw=None):
    """S^(k)_pt for k in kbins; the last bin collects k >= its value; e < min(kbins) is reference."""
    dw = dw or DW
    out = np.zeros(len(kbins))
    for phase, w in dw[p]:
        e = q_index(t) - q_index(PHASE_QUARTER[phase])
        if e < kbins[0]:
            continue
        j = min(e - kbins[0], len(kbins) - 1)
        if kbins[j] != e and j != len(kbins) - 1:
            continue
        out[j] += w
    return out


# ----------------------------------------------------------------------------- pooled model (§6.2)
WINDOW = [q_label(i) for i in range(q_index("2022Q1"), q_index("2026Q1") + 1)]


def pooled_data(kbins, provs=None, sid="P-TOT"):
    provs = provs or PROVS
    rows = []
    for p in provs:
        for t in WINDOW:
            a, b = Y(sid, p, t), Y(sid, p, qs(t, -4))
            if a is None or b is None or a <= 0 or b <= 0:
                continue
            rows.append((p, t, math.log(a) - math.log(b), exposure(p, t, kbins), exposure(p, qs(t, -4), kbins),
                         EXPO[p]["B_2024"]))
    return rows


def fit_pooled(rows, kbins):
    T = sorted({r[1] for r in rows})
    ti = {t: i for i, t in enumerate(T)}
    y = np.array([r[2] for r in rows])
    S1 = np.array([r[3] for r in rows])
    S0 = np.array([r[4] for r in rows])
    w = np.array([r[5] for r in rows])
    tix = np.array([ti[r[1]] for r in rows])
    sw = np.sqrt(w)
    wsum = np.bincount(tix, weights=w, minlength=len(T))

    def resid(rho):
        f = np.log1p(S1 @ rho) - np.log1p(S0 @ rho)
        r = y - f
        gamma = np.bincount(tix, weights=w * r, minlength=len(T)) / wsum
        return sw * (r - gamma[tix])

    sol = optimize.least_squares(resid, np.zeros(len(kbins)), bounds=(-0.95, 3.0), method="trf")
    return sol.x, float(np.sum(sol.fun ** 2))


def bootstrap_pooled(kbins, n_boot=N_BOOT):
    rng = np.random.default_rng(SEED)
    by_p = defaultdict(list)
    for r in pooled_data(kbins):
        by_p[r[0]].append(r)
    provs = sorted(by_p)
    draws = []
    for _ in range(n_boot):
        pick = rng.choice(len(provs), size=len(provs), replace=True)
        rows = [r for i in pick for r in by_p[provs[i]]]
        draws.append(fit_pooled(rows, kbins)[0])
    return np.array(draws)


# ----------------------------------------------------------------------------- S7: Poisson in levels
def fit_poisson_levels(kbins):
    window = [q_label(i) for i in range(q_index("2021Q1"), q_index("2026Q1") + 1)]
    cells = [(p, t, Y("P-TOT", p, t), exposure(p, t, kbins)) for p in PROVS for t in window
             if Y("P-TOT", p, t) is not None]
    p_idx = {p: i for i, p in enumerate(PROVS)}
    t_idx = {t: i for i, t in enumerate(window)}
    yv = np.array([c[2] for c in cells])
    Sx = np.array([c[3] for c in cells])
    pq = np.array([p_idx[c[0]] * 4 + (int(c[1][-1]) - 1) for c in cells])
    tt = np.array([t_idx[c[1]] for c in cells])

    def profile(rho):
        h = np.clip(1 + Sx @ rho, 1e-9, None)
        a = np.zeros(len(PROVS) * 4)
        g = np.zeros(len(window))
        for _ in range(200):
            mu0 = np.exp(g[tt]) * h
            a_new = np.log(np.clip(np.bincount(pq, weights=yv, minlength=len(a)), 1e-12, None)
                           / np.clip(np.bincount(pq, weights=mu0, minlength=len(a)), 1e-12, None))
            mu1 = np.exp(a_new[pq]) * h
            g_new = np.log(np.bincount(tt, weights=yv, minlength=len(g)) / np.bincount(tt, weights=mu1, minlength=len(g)))
            g_new -= g_new[0]
            if np.max(np.abs(a_new - a)) < 1e-10 and np.max(np.abs(g_new - g)) < 1e-10:
                a, g = a_new, g_new
                break
            a, g = a_new, g_new
        mu = np.exp(a[pq] + g[tt]) * h
        return -np.sum(yv * np.log(np.clip(mu, 1e-12, None)) - mu)

    sol = optimize.minimize(profile, np.zeros(len(kbins)), method="L-BFGS-B", bounds=[(-0.95, 3.0)] * len(kbins))
    return dict(zip([str(k) for k in kbins], sol.x.tolist()))


# ----------------------------------------------------------------------------- H5 (district, annual)
def h5(year, exclude_flagged_notes=False):
    flagged = {(f["district"], f["year"]) for f in P["dq1_outliers"]}
    note_d = {n["district"] for n in NOTES if n["release"] in ("2025Q3", "2025Q4")}
    rows = []
    for r in DISTRICTS:
        yrs = (year - 2, year - 1, year)
        if any((r["district"], y) in flagged for y in yrs):
            continue
        if exclude_flagged_notes and r["district"] in note_d:
            continue
        v = [r.get(f"tot_{y}") for y in yrs]
        if any(x is None for x in v):
            continue
        wt = v[0] + v[1]
        if wt <= 0:
            continue
        rows.append((r["province"], r["phase"], math.log(v[2] + 1) - math.log(v[1] + 1), wt))
    provs = sorted({r[0] for r in rows})
    pi = {p: i for i, p in enumerate(provs)}
    n = len(rows)
    X = np.zeros((n, 2 + len(provs)))
    for i, (p, ph, _, _) in enumerate(rows):
        X[i, 0] = ph == 1
        X[i, 1] = ph == 2
        X[i, 2 + pi[p]] = 1
    y = np.array([r[2] for r in rows])
    w = np.array([r[3] for r in rows])
    keep = np.any(X != 0, axis=0)
    X = X[:, keep]
    sw = np.sqrt(w)
    Xs, ys = X * sw[:, None], y * sw
    XtX_inv = np.linalg.pinv(Xs.T @ Xs)
    beta = XtX_inv @ Xs.T @ ys
    e = ys - Xs @ beta
    G = len(provs)
    cl = np.array([pi[r[0]] for r in rows])
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in range(G):
        sg = Xs[cl == g].T @ e[cl == g]
        meat += np.outer(sg, sg)
    k = np.linalg.matrix_rank(Xs)
    V = XtX_inv @ meat @ XtX_inv * (G / (G - 1)) * ((n - 1) / (n - k))
    se = np.sqrt(np.diag(V))
    d1, s1 = beta[0], se[0]
    df = G - 1
    return {"year": year, "delta1": d1, "se": s1, "delta2": beta[1], "se2": se[1], "n_districts": n,
            "n_provinces": G, "df": df, "p_one_sided": stats.t.cdf(d1 / s1, df),
            "lower_one_sided_95": d1 - stats.t.ppf(0.95, df) * s1, "rho1": math.exp(d1) - 1,
            "excluded_note_districts": exclude_flagged_notes}


# ----------------------------------------------------------------------------- main
def main():
    if not DQ["gate"]["confirmatory_tests_allowed"]:
        raise SystemExit("PROTOCOL.md §10 early stop: data-quality gate failed; confirmatory tests not run")
    tests, sens = [], []
    ln90, ln95 = math.log(0.90), math.log(0.95)

    # Primary and sibling tests ----------------------------------------------------------
    H1a = xtest("H1a", "P-TOT", "2026Q1", ("W3", "W2"), -1)
    H1b = xtest("H1b", "P-TOT", "2025Q3", ("W1",), -1)
    sc_filter = sc_covered
    H2 = xtest("H2", "SC-POS", "2026Q1", ("W3", "W2"), +1, extra_filter=sc_filter)
    H2_rec = xtest("H2-SC-REC (exploratory)", "SC-REC", "2026Q1", ("W3", "W2"), +1, extra_filter=sc_filter,
                   tag="exploratory")
    H2_p1_pos = xtest("SC-POS phase 1 (exploratory)", "SC-POS", "2025Q3", ("W1",), +1, extra_filter=sc_filter,
                      tag="exploratory")
    H2_p1_rec = xtest("SC-REC phase 1 (exploratory)", "SC-REC", "2025Q3", ("W1",), +1, extra_filter=sc_filter,
                      tag="exploratory")

    def ratio(p):
        if not (counts_ok("P-TOT", p, "2026Q1") and counts_ok("SC-POS", p, "2026Q1")):
            return None
        a, b = dg("P-TOT", p, "2026Q1"), dg("SC-POS", p, "2026Q1")
        return None if a is None or b is None else a - b
    H3 = xtest("H3", "P-TOT/SC-POS", "2026Q1", ("W3", "W2"), -1, extra_filter=sc_filter, outcome=ratio)
    H4_hip = xtest("H4", "P-HIP", "2026Q1", ("W3", "W2"), -1)
    H4_lau = xtest("H4-LAU (reference)", "P-LAU", "2026Q1", ("W3", "W2"), -1, tag="secondary-ref")

    def diff_lau_hip(p):
        if not (counts_ok("P-LAU", p, "2026Q1") and counts_ok("P-HIP", p, "2026Q1")):
            return None
        a, b = dg("P-LAU", p, "2026Q1"), dg("P-HIP", p, "2026Q1")
        return None if a is None or b is None else a - b
    H4_diff = xtest("H4-difference LAU-HIP", "P-LAU-P-HIP", "2026Q1", ("W3", "W2"), -1, outcome=diff_lau_hip,
                    tag="secondary-ref")
    tests += [H1a, H1b, H2, H2_rec, H2_p1_pos, H2_p1_rec, H3, H4_hip, H4_lau, H4_diff]

    # Time placebos ------------------------------------------------------------------------
    plac = [xtest(f"placebo H1a {t}", "P-TOT", t, ("W3", "W2"), -1, tag="placebo") for t in ("2025Q1", "2024Q1")]
    plac += [xtest(f"placebo H1b {t}", "P-TOT", t, ("W1",), -1, tag="placebo") for t in ("2024Q3", "2023Q3")]
    tests += plac

    def clean(real, placebos):
        bad = [pl["test"] for pl in placebos if pl["p_two_sided"] <= ALPHA and abs(pl["b"]) >= abs(real["b"]) / 2]
        return not bad, bad
    clean_a, bad_a = clean(H1a, plac[:2])
    clean_b, bad_b = clean(H1b, plac[2:])

    # Negative and positive controls --------------------------------------------------------
    ctrl = []
    for sid in ("NC-EH", "NC-DES", "PC-MON"):
        ctrl.append(xtest(f"{sid} on H1a model", sid, "2026Q1", ("W3", "W2"), -1, tag="control"))
        ctrl.append(xtest(f"{sid} on H1b model", sid, "2025Q3", ("W1",), -1, tag="control"))
    for c in ctrl:
        real = H1a if "H1a" in c["test"] else H1b
        c["wider_disruption_flag"] = int(c["test"].startswith("NC") and c["p_two_sided"] <= ALPHA
                                         and np.sign(c["b"]) == np.sign(real["b"]) and abs(c["b"]) >= abs(real["b"]) / 2)
    tests += ctrl
    national = {sid: {t: S[sid]["TOTAL"][t] / S[sid]["TOTAL"][qs(t, -4)] - 1
                      for t in [q_label(i) for i in range(q_index("2025Q1"), q_index("2026Q1") + 1)]}
                for sid in ("P-TOT", "P-HIP", "P-LAU", "P-OTR", "SC-REC", "SC-POS", "NC-EH", "NC-DES", "PC-MON")}

    # H5 -------------------------------------------------------------------------------------
    h5_rows = [h5(y) for y in range(2015, 2026)]
    H5 = h5_rows[-1]
    placebo_years = h5_rows[:-1]
    write_csv(DATA / "h5_years.csv", h5_rows)

    # Holm --------------------------------------------------------------------------------------
    prim = holm({"H1a": H1a["p_one_sided"], "H1b": H1b["p_one_sided"]})
    sec = holm({"H2": H2["p_one_sided"], "H3": H3["p_one_sided"], "H4": H4_hip["p_one_sided"],
                "H5": H5["p_one_sided"]})
    for t in (H1a, H1b):
        t["p_holm"] = prim[t["test"]]
    for t, k in ((H2, "H2"), (H3, "H3"), (H4_hip, "H4")):
        t["p_holm"] = sec[k]
    H5["p_holm"] = sec["H5"]

    # Verdicts (§8) --------------------------------------------------------------------------
    def v_h1(t, clean_ok):
        if t["b"] >= 0 or t["lower_one_sided_95"] > ln90:
            return "falsified"
        if t["p_holm"] <= ALPHA and t["p_perm"] <= ALPHA and clean_ok:
            return "supported"
        if t["p_holm"] <= ALPHA and t["p_perm"] <= ALPHA and not clean_ok:
            return "not supported (confounded: time placebo)"
        return "inconclusive"
    verdict = {"H1a": v_h1(H1a, clean_a), "H1b": v_h1(H1b, clean_b)}
    if H2["b"] > 0 and H2["p_holm"] <= ALPHA and H2["p_perm"] <= ALPHA:
        verdict["H2"] = "supported"
    elif H2["b"] < 0 and stats.t.cdf(H2["b"] / H2["se_hc3"], H2["df"]) <= ALPHA:
        verdict["H2"] = "falsified"
    else:
        verdict["H2"] = "inconclusive"
    verdict["H3"] = ("falsified" if H3["b"] >= 0 else
                     "supported" if H3["p_holm"] <= ALPHA and H3["p_perm"] <= ALPHA else "inconclusive")
    diff_includes_0 = H4_diff["ci95_low"] <= 0 <= H4_diff["ci95_high"]
    if H4_hip["b"] < 0 and H4_hip["p_holm"] <= ALPHA and H4_hip["p_perm"] <= ALPHA and diff_includes_0:
        verdict["H4"] = "supported"
    elif H4_hip["b"] >= 0 and H4_diff["b"] < 0 and H4_diff["p_one_sided"] <= ALPHA:
        verdict["H4"] = "falsified"
    else:
        verdict["H4"] = "inconclusive"
    more_negative_than_placebos = all(H5["delta1"] < r["delta1"] for r in placebo_years)
    if H5["delta1"] >= 0 or H5["lower_one_sided_95"] > ln95:
        verdict["H5"] = "falsified"
    elif H5["p_holm"] <= ALPHA and more_negative_than_placebos:
        verdict["H5"] = "supported"
    else:
        verdict["H5"] = "inconclusive"

    # Sensitivity (§6.5) --------------------------------------------------------------------------
    flag_prov = defaultdict(set)
    for n in NOTES:
        flag_prov[n["release"]].add(n["series_province"])
    no_data = defaultdict(float)
    partial = defaultdict(float)
    wmap = {r["district"]: r["w"] for r in DISTRICTS}
    for n in NOTES:
        if n["release"] == "2026Q1":
            no_data[n["series_province"]] += wmap[n["district"]]
        if n["release"] == "2025Q4":
            partial[n["series_province"]] += wmap[n["district"]]

    def scaled(quarters_and_shares):
        ov = {}
        for t, shares in quarters_and_shares:
            for p, s in shares.items():
                for sid in ("P-TOT", "P-HIP", "P-LAU", "P-OTR"):
                    v = S[sid][p].get(t)
                    if v is not None:
                        ov[(sid, p, t)] = v / (1 - s)
        return ov
    ov_a = scaled([("2026Q1", no_data)])
    ov_b = scaled([("2026Q1", no_data), ("2025Q4", partial)])
    variants = [
        ("S1 unweighted", dict(weights="1")),
        ("S2 without Barcelona and Madrid", dict(drop=("BARCELONA", "MADRID"))),
        ("S3 without provinces with CGPJ-flagged districts", None),
        ("S4a impute Q1-2026 no-data districts", dict(override=ov_a)),
        ("S4b also treat Q4-2025 partial districts as missing", dict(override=ov_b)),
        ("S5 weights from 2024 only", dict(wvar="_2024")),
        ("S6 small provinces included, ln(Y+0.5)", dict(eps=0.5, min_count=False)),
        ("S9 rent (P-LAU) as outcome", "LAU"),
        ("S10 without Murcia (San Javier pilot)", dict(drop=("MURCIA",))),
    ]
    for label, kw in variants:
        for hname, t, cols in (("H1a", "2026Q1", ("W3", "W2")), ("H1b", "2025Q3", ("W1",))):
            if kw is None:
                involved = {"H1a": ("2025Q4", "2026Q1"), "H1b": ("2025Q3",)}[hname]
                drop = set().union(*[flag_prov[q] for q in involved])
                r = xtest(f"{hname} {label}", "P-TOT", t, cols, -1, drop=tuple(drop), permute=False, tag="sensitivity")
            elif kw == "LAU":
                r = xtest(f"{hname} {label}", "P-LAU", t, cols, -1, permute=False, tag="sensitivity")
            else:
                r = xtest(f"{hname} {label}", "P-TOT", t, cols, -1, permute=False, tag="sensitivity", **kw)
            sens.append(r)
    # S8: TSJ-level replication
    sens += tsj_replication()
    # S11: H5 without the 64 + 4 districts flagged in Q3/Q4-2025
    s11 = h5(2025, exclude_flagged_notes=True)
    sens.append({"test": "H5 S11 without Q3/Q4-2025 flagged districts", "tag": "sensitivity", "b": s11["delta1"],
                 "se_hc3": s11["se"], "n": s11["n_districts"], "p_one_sided": s11["p_one_sided"],
                 "p_two_sided": 2 * stats.t.sf(abs(s11["delta1"] / s11["se"]), s11["df"]),
                 "lower_one_sided_95": s11["lower_one_sided_95"], "rho": s11["rho1"]})

    # Pooled model (§6.2) ---------------------------------------------------------------------------
    rows_l = pooled_data(KBINS_LEADS)
    rho_l, _ = fit_pooled(rows_l, KBINS_LEADS)
    boot_l = bootstrap_pooled(KBINS_LEADS)
    theta = rho_l[:2]
    V = np.cov(boot_l[:, :2].T)
    wald = float(theta @ np.linalg.pinv(V) @ theta)
    p_antic = float(stats.chi2.sf(wald, 2))
    antic_pass = p_antic > ALPHA
    if antic_pass:
        kb, rho_use = KBINS, fit_pooled(pooled_data(KBINS), KBINS)[0]
        boot_use = bootstrap_pooled(KBINS)
    else:
        kb, rho_use, boot_use = KBINS_LEADS, rho_l, boot_l
    at_bound = {"with_leads": [k for k, r in zip(KBINS_LEADS, rho_l) if r <= -0.949 or r >= 2.999],
                "used": [k for k, r in zip(kb, rho_use) if r <= -0.949 or r >= 2.999]}
    pooled = {
        "window": [WINDOW[0], WINDOW[-1]], "weights": "B_2024", "n_obs": len(rows_l), "bootstrap": N_BOOT,
        "search_bounds_rho": [-0.95, 3.0],
        "parameters_at_search_bound": at_bound,
        "degenerate": bool(at_bound["with_leads"] or at_bound["used"]),
        "with_leads": {"k": list(KBINS_LEADS), "rho": rho_l.tolist(),
                       "ci95": np.percentile(boot_l, [2.5, 97.5], axis=0).T.tolist()},
        "anticipation_test": {"wald": wald, "p": p_antic, "passes": antic_pass},
        "used_for_decomposition": {"k": list(kb), "rho": rho_use.tolist(),
                                   "ci95": np.percentile(boot_use, [2.5, 97.5], axis=0).T.tolist()},
        "phase_specific_rho0": {"phase1_from_H1b": H1b["rho"], "phase3_from_H1a": H1a["rho"]},
        "S7_poisson_levels_rho": fit_poisson_levels(KBINS_LEADS),
    }
    write_json(DATA / "pooled_model.json", pooled)

    # Decomposition and record low (§6.4) -------------------------------------------------------------
    t1, t0 = "2026Q1", "2025Q1"
    y_obs = {p: S["P-TOT"][p][t1] for p in PROVS}
    y_imp = {p: y_obs[p] / (1 - no_data.get(p, 0.0)) for p in PROVS}
    def counterfactual(rho):
        return sum(y_imp[p] / (1 + exposure(p, t1, kb) @ rho) for p in PROVS)
    Yobs, Yimp, Y0 = sum(y_obs.values()), sum(y_imp.values()), S["P-TOT"]["TOTAL"][t0]
    Ystar = counterfactual(rho_use)
    Ystar_boot = np.array([counterfactual(r) for r in boot_use])
    lo, hi = np.percentile(Ystar_boot, [2.5, 97.5])
    L = math.log(Yobs / Y0)
    comp = {"a_reported_missing": math.log(Yobs) - math.log(Yimp),
            "b_phase_counting": math.log(Yimp) - math.log(Ystar),
            "c_national_residual": math.log(Ystar) - math.log(Y0)}
    b_boot = math.log(Yimp) - np.log(Ystar_boot)
    share_ab = (comp["a_reported_missing"] + comp["b_phase_counting"]) / L
    hist = {q: v for q, v in S["P-TOT"]["TOTAL"].items() if "2013Q1" <= q <= "2025Q4"}
    prev_min = min(hist.values())
    prev_min_q1 = min(v for q, v in hist.items() if q.endswith("Q1"))

    def record(lo_, hi_, ref):
        return "not supported" if lo_ > ref else "robust" if hi_ < ref else "undetermined"
    decomposition = {
        "national_Q1_2025": Y0, "national_Q1_2026_observed": Yobs, "log_change": L, "pct_change": Yobs / Y0 - 1,
        "imputed_Q1_2026": Yimp, "imputed_provinces": {p: s for p, s in no_data.items()},
        "counterfactual_Q1_2026": Ystar, "counterfactual_ci95": [lo, hi],
        "counterfactual_pct_change": Ystar / Y0 - 1,
        "components_log": comp, "b_ci95": np.percentile(b_boot, [2.5, 97.5]).tolist(),
        "share_of_log_fall_a_plus_b": share_ab,
        "previous_minimum_all_quarters": {"value": prev_min, "quarter": min(hist, key=hist.get)},
        "previous_minimum_first_quarters": {"value": prev_min_q1,
                                             "quarter": min((q for q in hist if q.endswith("Q1")), key=hist.get)},
        "record_low_all_quarters": record(lo, hi, prev_min),
        "record_low_first_quarters": record(lo, hi, prev_min_q1),
        "rho_used": dict(zip([str(k) for k in kb], rho_use.tolist())),
    }
    # Exploratory (not registered): phase-3-only transient reading with H1a's own estimate and 95% CI.
    def cf_h1a(b):
        rho = math.exp(b) - 1
        den = {p: 1 + rho * EXPO[p]["W3"] for p in PROVS}
        return None if min(den.values()) <= 0 else sum(y_imp[p] / den[p] for p in PROVS)
    decomposition["exploratory_h1a_transient"] = {
        "note": "EXPLORATORY, not registered: Y*_p = Y_imp,p / (1 + rho·W3_p), rho = exp(b3_H1a) − 1, "
                "phase 1 and 2 effects set to 0 in Q1-2026",
        "rho": H1a["rho"], "counterfactual": cf_h1a(H1a["b"]),
        "counterfactual_at_ci95_bounds_of_b3": [cf_h1a(H1a["ci95_low"]), cf_h1a(H1a["ci95_high"])],
    }
    write_json(DATA / "decomposition.json", decomposition)

    # Overall reading (§8) ------------------------------------------------------------------------------
    if (verdict["H1a"] == "supported" and (verdict["H2"] == "supported" or verdict["H3"] == "supported")
            and clean_a and share_ab >= 0.5):
        overall = "to a large extent an artefact of counting"
    elif verdict["H1a"] == "falsified" and verdict["H1b"] == "falsified":
        overall = "not explained by the phased reform"
    else:
        overall = "partial"

    # Predictions for Q2-2026 (§7) -------------------------------------------------------------------------
    rho0_pooled = float(rho_use[list(kb).index(0)])
    rho0_h1a = H1a["rho"]
    preds = []
    for p in PROVS:
        W3 = EXPO[p]["W3"]
        preds.append({"province": p, "label": EXPO[p]["label"], "B_2024": EXPO[p]["B_2024"],
                      "W1": EXPO[p]["W1"], "W2": EXPO[p]["W2"], "W3": W3,
                      "transient_raw": -math.log1p(rho0_pooled * W3),
                      "transient_h1a_raw": -math.log1p(rho0_h1a * W3)})
    Bsum = sum(r["B_2024"] for r in preds)
    for key in ("transient", "transient_h1a"):
        mean = sum(r["B_2024"] * r[f"{key}_raw"] for r in preds) / Bsum
        for r in preds:
            r[f"pred_dev_{key}"] = r[f"{key}_raw"] - mean
    for r in preds:
        r["pred_dev_persistent"] = 0.0
    write_csv(DATA / "predictions_q2_2026.csv", preds,
              ["province", "label", "B_2024", "W1", "W2", "W3", "pred_dev_transient", "pred_dev_persistent",
               "pred_dev_transient_h1a"])
    spec = {
        "registered_in": "PROTOCOL.md §7",
        "quantity": "Δg_p(2026Q2) = [ln Y(2026Q2) − ln Y(2025Q2)] − [ln Y(2026Q1) − ln Y(2025Q1)], P-TOT, "
                    "province series file of the Q2-2026 release",
        "deviation": "Δg_p minus its B_2024-weighted mean over the provinces that pass the count rule",
        "count_rule": "Y >= 10 in 2026Q2, 2026Q1, 2025Q2 and 2025Q1",
        "readings": {
            "pred_dev_transient": f"rho_0 = {rho0_pooled:.6f} (pooled model, §6.2), rho_k = 0 for k >= 1 (primary)",
            "pred_dev_persistent": "rho_k = rho_0 for all k >= 0: no cross-province deviation (primary)",
            "pred_dev_transient_h1a": f"as transient, with rho_0 = exp(b3_H1a) − 1 = {rho0_h1a:.6f} (descriptive)",
        },
        "test": "Δg_p(2026Q2) = a + b3'·W3 + b2'·W2 + u, weights B_2024, HC3, as H1a",
        "b3_H1a": H1a["b"],
        "classification": {"transient": "b3' > 0 with one-sided p <= 0.05",
                           "persistent": f"upper bound of the 95% CI of b3' < −b3_H1a/2 = {-H1a['b'] / 2:.6f}",
                           "otherwise": "undetermined", "read_only_if": f"H1a supported (now: {verdict['H1a']})"},
        "scoring": "B_2024-weighted RMSE of predicted vs observed deviations, provinces passing the count rule",
        "revision_check": "Q1-2026 in the Q2 release vs the locked vintage: national P-TOT ±5%; province ±10% and ±10",
    }
    write_json(DATA / "predictions_q2_2026_spec.json", spec)

    write_csv(DATA / "tests.csv", tests)
    write_csv(DATA / "sensitivity.csv", sens)
    write_csv(DATA / "exclusions.csv", EXCLUSIONS, ["test", "tag", "province", "reason"])
    summary = {
        "verdicts": verdict, "overall_reading": overall,
        "time_placebos_clean": {"H1a": clean_a, "H1a_failing": bad_a, "H1b": clean_b, "H1b_failing": bad_b},
        "H5_more_negative_than_all_placebo_years": more_negative_than_placebos,
        "H1a": H1a, "H1b": H1b, "H2": H2, "H3": H3, "H4": H4_hip, "H4_difference": H4_diff, "H5": H5,
        "national_yoy": national,
        "decomposition": {k: decomposition[k] for k in ("components_log", "share_of_log_fall_a_plus_b",
                                                        "counterfactual_Q1_2026", "counterfactual_ci95",
                                                        "record_low_all_quarters", "record_low_first_quarters")},
        "anticipation_test": pooled["anticipation_test"],
        "pooled_model_degenerate": pooled["degenerate"],
        "pooled_parameters_at_bound": pooled["parameters_at_search_bound"],
    }
    write_json(DATA / "summary.json", summary)
    print(json.dumps({"verdicts": verdict, "overall": overall,
                      "H1a": {k: round(H1a[k], 4) for k in ("b", "se_hc3", "p_one_sided", "p_perm", "n")},
                      "H1b": {k: round(H1b[k], 4) for k in ("b", "se_hc3", "p_one_sided", "p_perm", "n")},
                      "share_ab": round(share_ab, 3)}, indent=1))


def tsj_replication():
    """S8: H1a and H1b on the 17 TSJ series."""
    from s12lib import TSJ_OF_PROVINCE
    T = P["tsj_series"]["P-TOT"]
    base = defaultdict(float)
    by_tsj = defaultdict(lambda: defaultdict(float))
    for r in DISTRICTS:
        tsj = TSJ_OF_PROVINCE[r["province"]]
        b = (r.get("tot_2023") or 0) + (r.get("tot_2024") or 0)
        base[tsj] += b
        by_tsj[tsj][r["phase"]] += b
    out = []
    for name, t, phases in (("H1a S8 TSJ level", "2026Q1", (3, 2)), ("H1b S8 TSJ level", "2025Q3", (1,))):
        rows = []
        for tsj, vals in T.items():
            if tsj.upper() == "TOTAL":
                continue
            v = [vals.get(qs(t, d)) for d in (0, -4, -1, -5)]
            if any(x is None or x < MIN_COUNT for x in v):
                continue
            g = (math.log(v[0]) - math.log(v[1])) - (math.log(v[2]) - math.log(v[3]))
            W = [by_tsj[tsj][ph] / base[tsj] for ph in phases]
            B = sum(vals[f"2024Q{k}"] for k in range(1, 5))
            rows.append((g, W, B))
        y = [r[0] for r in rows]
        X = np.column_stack([np.ones(len(rows))] + [[r[1][i] for r in rows] for i in range(len(phases))])
        beta, se, df = wls(y, X, [r[2] for r in rows])
        tval = beta[1] / se[1]
        out.append({"test": name, "tag": "sensitivity", "series": "P-TOT", "quarter": t, "b": beta[1], "se_hc3": se[1],
                    "df": df, "n": len(rows), "p_one_sided": stats.t.cdf(tval, df),
                    "p_two_sided": 2 * stats.t.sf(abs(tval), df), "rho": math.exp(beta[1]) - 1})
    return out


if __name__ == "__main__":
    main()
