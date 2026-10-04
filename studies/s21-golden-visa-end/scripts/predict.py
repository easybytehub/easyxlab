#!/usr/bin/env python3
"""Pre-registered prediction for 2026Q3 (METHOD.md §1.9), and its later evaluation.

    python3 scripts/predict.py            write data/predictions_2026Q3_frozen.csv and PREDICTIONS.md
                                          only if they do not exist; otherwise refit and report whether
                                          the refit matches the frozen file, without writing anything
    python3 scripts/predict.py evaluate   once MIVAU has published 2026Q3 and build.py has run:
                                          score data/predictions_2026Q3_frozen.csv (SHA-256 checked
                                          against data/freeze.json) with the tests as revised on
                                          2026-10-04 (PREDICTIONS.md, «Deviations»)

Model, per unit u (the 18 provinces with >= 100 foreign non-resident purchases in B, and the
other 34 pooled): r(u, t) = log y(u, t) - log(Y(t) - y(u, t)), y = foreign non-resident purchases,
Y = Spain. Fitted over 2019Q1-2026Q1 (definitive data) with quarter-of-year effects and one shift
each for the anticipation year A and the post year P. Prediction for 2026Q3 = third-quarter effect
+ post shift. 90% interval from the 5th and 95th percentiles of the pre-period residuals.
"""
import csv
import math
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, "scripts"))
from s21lib import CODE_LABEL, qrange, window_sum, wls_fe, quantile  # noqa: E402
from analyse import load, series, B, A, P, MIN_B, POOLED  # noqa: E402

D = os.path.join(R, "data")
FIT = qrange("2019Q1", "2026Q1")
TARGET = "2026Q3"
RELEASE = "2026-12-16"
OUT = os.path.join(D, "predictions_2026Q3_frozen.csv")
FREEZE = os.path.join(D, "freeze.json")
PRED_MD = os.path.join(R, "PREDICTIONS.md")


def units(d):
    provs = sorted(CODE_LABEL)
    bc = {c: window_sum(series(d, [c], "nres_fx"), B) for c in provs}
    single = sorted(c for c in provs if bc[c] >= MIN_B)
    u = {c: [c] for c in single}
    u[POOLED] = [c for c in provs if c not in single]
    lab = {c: CODE_LABEL[c] for c in single}
    lab[POOLED] = f"other {len(u[POOLED])} provinces, pooled"
    return u, lab


def fit(d):
    U, lab = units(d)
    spain = series(d, ["00"], "nres_fx")
    rows = []
    for u, codes in sorted(U.items()):
        y = series(d, codes, "nres_fx")
        r = {q: math.log(y[q]) - math.log(spain[q] - y[q]) for q in FIT}
        X = [[1.0 if q in A else 0.0, 1.0 if q in P else 0.0] for q in FIT]
        season = [q[-1] for q in FIT]
        beta, se = wls_fe([r[q] for q in FIT], X, [season], [1.0] * len(FIT))
        dA, dP = beta
        resid_all = {q: r[q] - dA * X[i][0] - dP * X[i][1] for i, q in enumerate(FIT)}
        a = {s: sum(v for q, v in resid_all.items() if q[-1] == s) / sum(1 for q in resid_all if q[-1] == s)
             for s in "1234"}
        pre = [r[q] - a[q[-1]] for q in FIT if q not in A and q not in P]
        pred = a["3"] + dP
        lo, hi = pred + quantile(pre, 0.05), pred + quantile(pre, 0.95)
        share = math.exp(pred) / (1 + math.exp(pred))
        rows.append({"unit": u, "label": lab[u], "n_provinces": len(codes),
                     "pre_q3_level_r": round(a["3"], 4), "shift_A": round(dA, 4), "shift_P": round(dP, 4),
                     "pred_r": round(pred, 4), "lo90_r": round(lo, 4), "hi90_r": round(hi, 4),
                     "pred_share_pct": round(100 * share, 3),
                     "lo90_share_pct": round(100 * math.exp(lo) / (1 + math.exp(lo)), 3),
                     "hi90_share_pct": round(100 * math.exp(hi) / (1 + math.exp(hi)), 3),
                     "b_q3_share_pct": round(100 * y["2023Q3"] / spain["2023Q3"], 3),
                     "obs_2025Q3": y["2025Q3"], "obs_2026Q2_provisional": y.get("2026Q2", "")})
    return rows, spain


def write_md(rows, spain):
    n25 = spain["2025Q3"]
    t = []
    t.append("# S21 — Pre-registered predictions for 2026Q3\n")
    t.append("*EasyxLab · study S21 · written 2026-10-04, before MIVAU publishes 2026Q3 (scheduled for "
             f"{RELEASE} in the PEN 2026 calendar) · status: pre-registration, not to be edited after its first commit*\n")
    t.append("## What is predicted\n")
    t.append("Purchases of dwellings by **foreign non-residents** (MIVAU table 1.6, «Extranjeros» among "
             "«No residentes») in the third quarter of 2026, for each of 19 units: the 18 provinces with at "
             "least 100 such purchases in 2023Q2–2024Q1, and the other 34 provinces pooled. Model and tests "
             "are those of METHOD.md §1.9, frozen on 2026-10-04 (sha256 of the plan in STATUS.md).\n")
    t.append("The quantity predicted is the unit's relative level, r = log(unit) − log(Spain without the unit), "
             "equivalently its share of Spain's foreign non-resident purchases. A national total is not "
             "predicted; counts follow from the realised national total N as N × share.\n")
    t.append("## Model\n")
    t.append("- Fitted per unit over 2019Q1–2026Q1 (definitive data): quarter-of-year effects, one shift for "
             "the anticipation year (2024Q2–2025Q1) and one for the post year (2025Q2–2026Q1).\n"
             "- Prediction: third-quarter effect + post shift, that is, the post-repeal level persists.\n"
             "- 90% interval: 5th and 95th percentiles of the unit's 2019Q1–2024Q1 residuals, added to the "
             "prediction. They include the 2020 pandemic quarters, and ignore the uncertainty of the post "
             "shift itself (estimated from four quarters).\n")
    t.append("## Predictions\n")
    t.append("| unit | fitted pre-announcement Q3 share, 2019–2023 (%) | share in 2023Q3 (%) | predicted share (%) | 90% interval (%) | 2025Q3 count | count if N equals 2025Q3's " + f"{n25:,}" + " |")
    t.append("|---|---|---|---|---|---|---|")
    for r in rows:
        pre_share = 100 * math.exp(r["pre_q3_level_r"]) / (1 + math.exp(r["pre_q3_level_r"]))
        t.append(f"| {r['label']} | {pre_share:.2f} | {r['b_q3_share_pct']:.2f} | {r['pred_share_pct']:.2f} | "
                 f"{r['lo90_share_pct']:.2f}–{r['hi90_share_pct']:.2f} | {r['obs_2025Q3']:,} | "
                 f"{round(n25 * r['pred_share_pct'] / 100):,} |")
    t.append("")
    t.append("Machine-readable copy: `data/predictions_2026Q3.csv` (log scale, with the fitted effects).\n")
    t.append("## Tests, decided now\n")
    t.append("1. **Calibration.** Count the units whose realised share falls inside its 90% interval. About 17 "
             "of 19 are expected; fewer than 15 means the model or the intervals are wrong.\n"
             "2. **No rebound in the two cities.** For Madrid and for Barcelona, the realised 2026Q3 share stays "
             "below the fitted pre-announcement third-quarter share (first share column). If either is above "
             "it, the post-repeal fall did not persist there. This benchmark averages 2019–2023, including "
             "the 2020–2022 trough, so it is a weak test.\n"
             "2b. **Added on 2026-10-04, before this file's first commit (METHOD.md §9).** The same, against "
             "the share in 2023Q3, the third quarter of the year before the announcement (second share "
             "column). This is the comparison behind the study's headline.\n"
             "3. **Counts.** Given the realised national total N, each unit's count is N × predicted share; "
             "the interval scales the same way.\n")
    t.append("## What is already known and is not a test\n")
    t.append("- 2026Q2 is published but provisional; it was seen before writing this file and is not used to fit.\n"
             "- If MIVAU revises earlier quarters in the December release, the evaluation uses the revised "
             "figures for 2026Q3 only; the fitted effects stay as frozen in the CSV.\n")
    t.append("## How it will be scored\n")
    t.append("`python3 scripts/build.py && python3 scripts/predict.py evaluate`, after downloading the "
             "December release with `bash scripts/run.sh fetch`.\n")
    t.append("---\nEasyxLab · a research lab by [EasyByte](https://easybyte.es)\n")
    open(PRED_MD, "w", encoding="utf-8").write("\n".join(t))


def evaluate():
    import hashlib
    import json
    d = load()
    spain = series(d, ["00"], "nres_fx")
    if TARGET not in spain:
        print(f"{TARGET} is not in data/province_quarter.csv yet (release scheduled for {RELEASE})")
        return
    fz = json.load(open(FREEZE, encoding="utf-8"))
    sha = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
    if sha != fz["frozen_csv_sha256"]:
        sys.exit(f"{os.path.relpath(OUT, R)} does not match the SHA-256 in data/freeze.json: not scoring")
    U, _ = units(d)
    rows = list(csv.DictReader(open(OUT, encoding="utf-8")))
    inside = 0
    for r in rows:
        y = sum(d[(TARGET, c)]["nres_fx"] for c in U[r["unit"]])
        rr = math.log(y) - math.log(spain[TARGET] - y)
        sh = 100 * y / spain[TARGET]
        ok = float(r["lo90_r"]) <= rr <= float(r["hi90_r"])
        inside += ok
        print(f"{r['label']}: realised share {sh:.2f}% (r {rr:.3f}); predicted {float(r['pred_share_pct']):.2f}% "
              f"[{float(r['lo90_share_pct']):.2f}, {float(r['hi90_share_pct']):.2f}] inside={ok}")
        if r["unit"] in ("28", "08"):
            print(f"   test 2 (revised): rebound = above the upper 90% bound: {rr > float(r['hi90_r'])}")
            print(f"   test 2b (revised): further fall = below the lower 90% bound: {rr < float(r['lo90_r'])}")
            print(f"   superseded, for the record: below fitted 2019-2023 Q3 level: {rr < float(r['pre_q3_level_r'])}; "
                  f"below 2023Q3 share: {sh < float(r['b_q3_share_pct'])}")
    print(f"test 1: inside the 90% interval: {inside} of {len(rows)} (fewer than 15 = model or intervals wrong)")


def main():
    if sys.argv[1:] == ["evaluate"]:
        evaluate()
        return
    d = load()
    rows, spain = fit(d)
    if os.path.exists(OUT):
        frozen = list(csv.DictReader(open(OUT, encoding="utf-8")))
        same = [{k: str(v) for k, v in r.items()} for r in rows] == frozen
        print(f"{os.path.relpath(OUT, R)} is frozen and not rewritten; today's refit "
              f"{'matches it' if same else 'DIFFERS from it (data revised?)'}")
    else:
        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"{os.path.relpath(OUT, R)} written (frozen from now on)")
    if os.path.exists(PRED_MD):
        print("PREDICTIONS.md exists and is frozen; not rewritten")
    else:
        write_md(rows, spain)
        print("PREDICTIONS.md written")


if __name__ == "__main__":
    main()
