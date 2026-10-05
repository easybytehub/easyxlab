#!/usr/bin/env python3
"""S24: what the ECV's rotating panel says about selection, from INE's longitudinal microdata files.

The ECV interviews each household for four consecutive years and INE publishes longitudinal files
(periodo_<t>-<t+3>.zip). Two uses here:

L1  Leaving home. Young people (18-34 at the end of the income year) who live with a parent in wave t
    and are seen again, or recorded as having moved to a private household in Spain (RB110 = 5,
    RB120 = 1), in wave t+1. "Left" = no longer with a parent in t+1 (moved out, or present without a
    parent). Their personal net income in wave t (the year before leaving) is compared with that of
    young people who stayed. Most young people who move out are recorded as moved and "lost" (RB120 =
    4: INE did not trace them); they count as leavers, as do those recorded in a private household in
    Spain (RB120 = 1). People who died, emigrated (RB120 = 3) or entered an institution (RB120 = 2) are
    left out. Transitions are taken from one file each: 13->14 ... 15->16 from 2013-2016, 16->17 ... 18->19
    from 2016-2019, and so on, so no transition is counted twice.

L2  Continuing tenants. Households that pay market rent in two consecutive waves (same household id).
    Their overburden in t and t+1 measures how much the burden of the same tenants changed, which
    selection into leaving home cannot produce.

Weights: L1 uses the person base weight in wave t (RB060); L2 the household longitudinal weight in
wave t+1 (DB095); unweighted counts are reported too. Output: data/leavers.csv, data/continuing_tenants.csv.
"""
from __future__ import annotations

import csv
import io
import re
import sys
import zipfile
from collections import defaultdict

from s24lib import D, RAW, wmedian, wquantile

PERIODS = {"2013-2016": (2013, 2016), "2016-2019": (2016, 2019), "2019-2022": (2019, 2022), "2022-2025": (2022, 2025)}
INC = ["PY010N", "PY020N", "PY050N", "PY080N", "PY090N", "PY100N", "PY110N", "PY120N", "PY130N", "PY140N"]


def _walk(z, depth=0):
    for n in z.namelist():
        if n.lower().endswith(".zip") and depth < 3:
            yield from _walk(zipfile.ZipFile(io.BytesIO(z.read(n))), depth + 1)
        elif re.search(r"\.(csv|tab)$", n, re.I):
            yield n, z


def files(period):
    z = zipfile.ZipFile(RAW / "ecv" / f"periodo_{period}.zip")
    t1 = PERIODS[period][1] % 100
    found = {}
    for n, zz in _walk(z):
        base = n.rsplit("/", 1)[-1].lower()
        for kind in "drhp":
            if re.fullmatch(rf"ecv_l{kind}_\d\da\d\d\.(csv|tab)", base):
                rank = 0
            elif re.fullmatch(rf"es{t1:02d}{kind}\.csv", base):
                rank = 1
            else:
                continue
            if kind not in found or rank < found[kind][0]:
                found[kind] = (rank, zz, n)
    return {k: v[1].read(v[2]) for k, v in found.items()}


def rows(b):
    text = b.decode("latin-1")
    delim = "\t" if "\t" in text.split("\n", 1)[0] else ","
    rd = csv.reader(io.StringIO(text), delimiter=delim)
    head = [h.strip().strip('"').upper() for h in next(rd)]
    for r in rd:
        if r:
            yield dict(zip(head, (x.strip().strip('"') for x in r)))


def f(x):
    try:
        return float(x) if x not in ("", None) else None
    except ValueError:
        return None


def wilson(k, n, z=1.96):
    """Wilson 95% interval for k of n (unweighted), in percent."""
    if not n:
        return "", ""
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return round(100 * (c - h), 1), round(100 * (c + h), 1)


def med(pairs):
    pairs = [(v, w) for v, w in pairs if w > 0]
    return round(wmedian(*zip(*pairs))) if pairs else ""


def burden(h):
    hc, inc, al = f(h.get("HH070")), f(h.get("HY020")), f(h.get("HY070G")) or 0.0
    if hc is None or inc is None:
        return None
    den = inc - al
    return 9.99 if den <= 0 else max(12 * hc - al, 0) / den


def tenure(h):
    t = h.get("HH021", "")
    if t:
        return int(float(t))
    t = h.get("HH020", "")
    return {1: 0, 2: 3, 3: 4, 4: 5}.get(int(float(t))) if t else None


def main():
    leavers, cont = [], []
    pooled = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0, 0]))
    moved_out = defaultdict(int)   # period -> group -> [w_risk, w_left, n_risk, n_left]
    for period, (t0, t1) in PERIODS.items():
        fl_ = files(period)
        R = {(int(r["RB010"]), r["RB030"]): r for r in rows(fl_["r"])}
        members = defaultdict(set)          # (year, household id) -> current members (RB110 1-4)
        for (yr, pid), r in R.items():
            if r.get("RB110", "1") in ("1", "2", "3", "4") and r.get("RB040", ""):
                members[(yr, r["RB040"])].add(pid)
        P = {(int(r["PB010"]), r["PB030"]): r for r in rows(fl_["p"])}
        H = {(int(r["HB010"]), r["HB030"]): r for r in rows(fl_["h"])}
        Dd = {(int(r["DB010"]), r["DB030"]): r for r in rows(fl_["d"])}
        for t in range(t0, t1):
            # ---- L1 leaving home --------------------------------------------------------------
            risk = []
            for (yr, pid), r in R.items():
                if yr != t or r.get("RB110", "1") not in ("1", "2", "3", "4"):
                    continue
                by = f(r.get("RB080"))
                if by is None:
                    continue
                age = t - 1 - int(by)
                if not 18 <= age <= 34:
                    continue
                if r.get("RB220", "") == "" and r.get("RB230", "") == "":
                    continue                                    # not living with a parent in t
                nxt = R.get((t + 1, pid))
                if nxt is None:
                    continue
                st = nxt.get("RB110", "")
                if st in ("1", "2", "3", "4"):
                    left = nxt.get("RB220", "") == "" and nxt.get("RB230", "") == ""
                elif st == "5" and nxt.get("RB120", "") in ("1", "4"):
                    left = True                                  # moved to a private household, or moved and lost
                else:
                    continue
                p = P.get((t, pid))
                if p is None:
                    continue
                vals = [f(p.get(k, "")) for k in INC]
                pinc = sum(v for v in vals if v is not None)
                w = f(r.get("RB060")) or 0.0
                risk.append((pinc, w, left, age))
            moved_out[period] += sum(1 for (yr, _), r in R.items() if yr == t + 1 and r.get("RB110", "") == "5")
            if not risk:
                continue
            pos = [(v, w) for v, w, _, _ in risk if v > 0]
            cuts = [wquantile([v for v, _ in pos], [w for _, w in pos], q) for q in (0.25, 0.5, 0.75)]
            tr = f"{t}->{t + 1}"
            per = f"{period}"
            def grp(v):
                return "G0_none" if v <= 0 else ("G1", "G2", "G3", "G4")[sum(v > c for c in cuts)]
            agg = defaultdict(lambda: [0.0, 0.0, 0, 0])
            for v, w, left, age in risk:
                for g in ("all", grp(v)):
                    a = agg[g]; a[0] += w; a[1] += w * left; a[2] += 1; a[3] += left
                    b = pooled[per][g]; b[0] += w; b[1] += w * left; b[2] += 1; b[3] += left
                    sub = "18-24" if age <= 24 else "25-34"
                    b = pooled[per][f"{g}|{sub}"]; b[0] += w; b[1] += w * left; b[2] += 1; b[3] += left
            lv = [(v, w) for v, w, left, _ in risk if left]
            sy = [(v, w) for v, w, left, _ in risk if not left]
            for g, a in agg.items():
                leavers.append({"period_file": period, "transition": tr, "personal_income_group": g,
                                "at_risk_n": a[2], "left_n": a[3], "leaving_rate_pct": round(100 * a[1] / a[0], 1) if a[0] else "",
                                "median_prior_income_leavers": med(lv) if g == "all" else "",
                                "median_prior_income_stayers": med(sy) if g == "all" else ""})
            # ---- L2 continuing market tenants ----------------------------------------------------
            n = 0; w_ = ob0 = ob1 = 0.0; nb0 = nb1 = 0
            ns = 0; ws_ = os0 = os1 = 0.0             # same members in both waves
            g_inc, g_rent = [], []
            for (yr, hid), h in H.items():
                if yr != t or tenure(h) != 3:
                    continue
                h1 = H.get((t + 1, hid))
                if h1 is None or tenure(h1) != 3:
                    continue
                b0, b1 = burden(h), burden(h1)
                if b0 is None or b1 is None:
                    continue
                d1 = Dd.get((t + 1, hid), {})
                w = f(d1.get("DB095")) or 0.0
                n += 1; w_ += w; ob0 += w * (b0 > 0.4); ob1 += w * (b1 > 0.4); nb0 += b0 > 0.4; nb1 += b1 > 0.4
                m0, m1 = members.get((t, hid)), members.get((t + 1, hid))
                if m0 and m0 == m1:
                    ns += 1; ws_ += w; os0 += w * (b0 > 0.4); os1 += w * (b1 > 0.4)
                i0, i1 = f(h.get("HY020")), f(h1.get("HY020"))
                r0, r1 = f(h.get("HH060")), f(h1.get("HH060"))
                if i0 and i1 and i0 > 0:
                    g_inc.append((i1 / i0, w))
                if r0 and r1 and r0 > 0:
                    g_rent.append((r1 / r0, w))
            if n:
                cont.append({"period_file": period, "transition": tr, "households_n": n,
                             "overburden_t_pct": round(100 * ob0 / w_, 1) if w_ else "",
                             "overburden_t1_pct": round(100 * ob1 / w_, 1) if w_ else "",
                             "overburden_t_unweighted_pct": round(100 * nb0 / n, 1),
                             "overburden_t1_unweighted_pct": round(100 * nb1 / n, 1),
                             "same_members_n": ns,
                             "same_members_overburden_t_pct": round(100 * os0 / ws_, 1) if ws_ else "",
                             "same_members_overburden_t1_pct": round(100 * os1 / ws_, 1) if ws_ else "",
                             "median_income_growth_pct": round(100 * (wmedian(*zip(*g_inc)) - 1), 1) if g_inc else "",
                             "median_rent_growth_pct": round(100 * (wmedian(*zip(*g_rent)) - 1), 1) if g_rent else "",
                             "mean_rent_growth_pct": round(100 * (sum(min(x, 3.0) * w for x, w in g_rent) / sum(w for _, w in g_rent) - 1), 1) if g_rent else "",
                             "share_rent_unchanged_pct": round(100 * sum(w for x, w in g_rent if abs(x - 1) < 1e-9) / sum(w for _, w in g_rent), 1) if g_rent else ""})
        print(f"{period} done; records of persons who moved out (RB110 = 5): {moved_out[period]}", flush=True)
    for per, gs in pooled.items():
        for g, a in gs.items():
            lo, hi = wilson(a[3], a[2])
            leavers.append({"period_file": per, "transition": "pooled", "personal_income_group": g, "at_risk_n": a[2],
                            "moved_out_records_in_file": moved_out[per],
                            "left_n": a[3], "leaving_rate_pct": round(100 * a[1] / a[0], 1) if a[0] else "",
                            "unweighted_rate_pct": round(100 * a[3] / a[2], 1) if a[2] else "",
                            "unweighted_ci95_low": lo, "unweighted_ci95_high": hi})
    for name, rows_ in (("leavers.csv", leavers), ("continuing_tenants.csv", cont)):
        keys = list(rows_[0].keys()) if name != "leavers.csv" else ["period_file", "transition", "personal_income_group",
                                                                    "at_risk_n", "left_n", "leaving_rate_pct",
                                                                    "median_prior_income_leavers", "median_prior_income_stayers",
                                                                    "moved_out_records_in_file", "unweighted_rate_pct",
                                                                    "unweighted_ci95_low", "unweighted_ci95_high"]
        with open(D / name, "w", newline="", encoding="utf-8") as fo:
            w = csv.DictWriter(fo, fieldnames=keys)
            w.writeheader()
            for r in rows_:
                w.writerow({k: r.get(k, "") for k in keys})
    return 0


if __name__ == "__main__":
    sys.exit(main())
