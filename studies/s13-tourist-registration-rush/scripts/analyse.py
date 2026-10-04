#!/usr/bin/env python3
"""S13 analysis of the Comunitat Valenciana tourist-dwelling registry (METHOD.md §1, frozen
plan, plus the additions listed in METHOD.md §9). Reads the minimal, git-ignored copies in
data/raw/ and writes aggregates only to data/.

    python3 scripts/analyse.py

Which copies are read: the main copy is $S13_SNAPSHOT if set, else 2026-10-04 (the copy the
published numbers come from) if present, else the latest gva_min_<date>.csv; the comparison copy
is the latest Internet Archive capture older than the main copy (data/sources.json). An outsider
who runs `bash scripts/run.sh fetch` gets today's file and therefore slightly different numbers.
"""
import collections
import csv
import datetime as dt
import json
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s13lib import (parse_signatura, parse_hist_signatura, counter_of, d, days, nonworking, excess,
                    contrast_ci, ratio_of_means, ratio_of_ratios, gaps, order_lags, rank_desc)

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(R, "data")
RAW = os.path.join(DATA, "raw", "registries")
PUBLISHED = "2026-10-04"


def pick_copies():
    import glob
    days_ = sorted(os.path.basename(f)[8:18] for f in glob.glob(os.path.join(RAW, "gva_min_????-??-??.csv")))
    if not days_:
        raise SystemExit("no copy of the GVA registry in data/raw/registries: run `bash scripts/run.sh fetch`")
    main = os.environ.get("S13_SNAPSHOT") or (PUBLISHED if PUBLISHED in days_ else days_[-1])
    try:
        meta = json.load(open(os.path.join(DATA, "sources.json"), encoding="utf-8"))["gva_snapshots"]
    except Exception:
        meta = {}
    arch = sorted(k for k, v in meta.items() if str(v.get("source", "")).startswith("Internet Archive")
                  and k < main and k in days_)
    if not arch:
        raise SystemExit("no Internet Archive copy older than the main copy: run `python3 scripts/fetch_gva.py wayback`")
    return main, arch[-1]


MAIN, WB = pick_copies()
D0 = dt.date(2025, 4, 2)                    # last day before LPH art. 7.3 took effect
END = dt.date(2026, 8, 31)                  # analysis end (frozen)
PROV = {"03": "Alicante", "12": "Castellón", "46": "Valencia"}
SUFFIX_PROV = {"A": "03", "CS": "12", "V": "46"}
KINDS = ("in_building", "whole_parcel", "unknown")
SUSPENSION_CITIES = {"46250": "València", "03014": "Alacant/Alicante"}


def P(*a):
    return os.path.join(DATA, *a)


def wcsv(name, header, rows):
    with open(P(name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow([(f"{x:.6g}" if isinstance(x, float) else x) for x in r])


def months(a, b):
    """'YYYY-MM' from month of a to month of b inclusive."""
    y, m = a.year, a.month
    out = []
    while (y, m) <= (b.year, b.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def load(day):
    rows = []
    side = {}
    sp = os.path.join(RAW, f"gva_bkey_{day}.csv")
    if os.path.exists(sp):
        side = {r["signatura"]: r for r in csv.DictReader(open(sp, encoding="utf-8"))}
    for r in csv.DictReader(open(os.path.join(RAW, f"gva_min_{day}.csv"), encoding="utf-8")):
        if "bkey" not in r and r["signatura"] in side:
            r.update(side[r["signatura"]])
        k = parse_signatura(r["signatura"])
        if not k:
            raise SystemExit(f"unrecognised signatura form in {day}")
        rows.append({"sig": r["signatura"], "num": k[0], "suf": k[1], "counter": counter_of(*k),
                     "prov": r["cod_provincia"] or SUFFIX_PROV[k[1]],
                     "ine": (r["cod_provincia"] or SUFFIX_PROV[k[1]]) + r["cod_municipio"],
                     "muni": r["municipio"], "date": d(r["fecha_alta"]),
                     "kind": r.get("unit_kind") or "", "cargo0001": r.get("cargo0001", ""),
                     "parcel_n": int(r["parcel_n"]) if r.get("parcel_n") else None,
                     "bkey": r.get("bkey") or None, "has_ref": r.get("has_ref", "")})
    return rows


def main():
    hol_cv = {d(r["date"]) for r in csv.DictReader(open(P("holidays.csv"), encoding="utf-8"))
              if r["region"] in ("ES", "CV")}
    cur = load(MAIN)
    wb = load(WB)
    summ = {"snapshot_main": MAIN, "snapshot_archive": WB, "rows_main": len(cur), "D": str(D0), "analysis_end": str(END)}

    # ---------------------------------------------------------------- daily / monthly series
    # Publication rule (METHOD §8): no table below province level has a cell under SMALL.
    SMALL = 5
    span = (dt.date(2016, 1, 1), dt.date(2026, 9, 30))
    dk = collections.Counter((r["date"], r["kind"]) for r in cur if span[0] <= r["date"] <= span[1])
    wcsv("daily_kind.csv", ["date", "unit_kind", "n"], sorted((x.isoformat(), k, n) for (x, k), n in dk.items()))
    dp = collections.Counter((r["date"], r["prov"]) for r in cur if span[0] <= r["date"] <= span[1])
    wcsv("daily_province.csv", ["date", "province", "n"], sorted((x.isoformat(), p, n) for (x, p), n in dp.items()))
    mpk = collections.Counter((r["date"].strftime("%Y-%m"), r["prov"], r["kind"]) for r in cur
                              if dt.date(2022, 1, 1) <= r["date"] <= span[1])
    wcsv("monthly_province_kind.csv", ["month", "province", "unit_kind", "n"],
         sorted((m, p, k, n if n >= SMALL else f"<{SMALL}") for (m, p, k), n in mpk.items()))
    mm = collections.Counter((r["date"].strftime("%Y-%m"), r["ine"], r["muni"]) for r in cur
                             if dt.date(2022, 1, 1) <= r["date"] <= span[1])
    mrows, rest = [], collections.Counter()
    for (m, i, nm), n in mm.items():
        if n >= SMALL:
            mrows.append((m, i, nm, n))
        else:
            rest[(m, i[:2])] += n
    for (m, p), n in rest.items():
        mrows.append((m, p + "000", f"other municipalities of {PROV[p]} (each under {SMALL})", n if n >= SMALL else f"<{SMALL}"))
    wcsv("monthly_municipality.csv", ["month", "ine_code", "municipality", "n"], sorted(mrows, key=lambda r: (r[0], r[1])))
    summ["publication_rule"] = {"threshold": SMALL, "municipality_month_cells_published": sum(1 for r in mrows if r[1][2:] != "000"),
                                "merged_cells": sum(1 for (m, i, nm), n in mm.items() if n < SMALL)}

    def series(pred):
        s = collections.Counter()
        for r in cur:
            if pred(r):
                s[r["date"]] += 1
        return s

    SER = {"all": series(lambda r: True)}
    for k in KINDS:
        SER[k] = series(lambda r, k=k: r["kind"] == k)
    SER["in_building+unknown"] = series(lambda r: r["kind"] in ("in_building", "unknown"))
    for p in PROV:
        SER[f"prov{p}"] = series(lambda r, p=p: r["prov"] == p)
    # sensitivity added after the freeze (METHOD §9): without the two cities with municipal suspensions
    SER["all_excl_cities"] = series(lambda r: r["ine"] not in SUSPENSION_CITIES)
    SER["in_building_excl_cities"] = series(lambda r: r["ine"] not in SUSPENSION_CITIES and r["kind"] == "in_building")
    SER["whole_parcel_excl_cities"] = series(lambda r: r["ine"] not in SUSPENSION_CITIES and r["kind"] == "whole_parcel")
    SER["valencia_city"] = series(lambda r: r["ine"] == "46250")

    # ---------------------------------------------------------------- 1.2 kind validation
    kv = {}
    for k in KINDS:
        g = [r for r in cur if r["kind"] == k]
        kv[k] = {"n": len(g), "cargo0001_share": sum(r["cargo0001"] == "1" for r in g) / len(g),
                 "parcel_shared_share": sum((r["parcel_n"] or 0) > 1 for r in g) / len(g)}
    summ["kind_validation"] = kv

    # ---------------------------------------------------------------- R1 peak
    base_days = [x for x in days(dt.date(2025, 1, 7), dt.date(2025, 2, 28)) if not nonworking(x, hol_cv)]
    alldays = days(dt.date(2016, 1, 1), END)
    rush_rows = []
    rush = {}
    for name, s in SER.items():
        bv = [s.get(x, 0) for x in base_days]
        peak = s.get(D0, 0)
        r1 = {"peak": peak, "base_median": statistics.median(bv), "base_max": max(bv),
              "base_days": len(bv),
              "peak_ratio": peak / statistics.median(bv) if statistics.median(bv) else float("nan"),
              "rank_since_2016": rank_desc([s.get(x, 0) for x in alldays], peak)}
        r2 = excess(s, D0, hol_cv)
        r5 = excess(s, D0 + dt.timedelta(days=28), hol_cv, w_len=28, b_from=87 + 28, b_to=34 + 28)
        rush[name] = {"R1": r1, "R2": r2, "R5": r5}
    # R5 must use the same baseline B as R2: recompute explicitly
    for name, s in SER.items():
        base = days(D0 - dt.timedelta(days=87), D0 - dt.timedelta(days=34))
        tot, cnt = {True: 0, False: 0}, {True: 0, False: 0}
        for x in base:
            k = nonworking(x, hol_cv)
            tot[k] += s.get(x, 0)
            cnt[k] += 1
        mean = {k: tot[k] / cnt[k] for k in tot}
        win = days(D0 + dt.timedelta(days=1), D0 + dt.timedelta(days=28))
        O = sum(s.get(x, 0) for x in win)
        E = sum(mean[nonworking(x, hol_cv)] for x in win)
        rush[name]["R5"] = {"O": O, "E": E, "ratio": O / E if E else float("nan")}

    # ---------------------------------------------------------------- R3 placebo, R4 contrast
    ends = [x for x in days(dt.date(2023, 4, 3), END)
            if not nonworking(x, hol_cv) and not (dt.date(2025, 3, 1) <= x <= dt.date(2025, 5, 31))]
    plac_rows = []
    plac = collections.defaultdict(dict)
    for name in ("all", "in_building", "whole_parcel", "unknown", "in_building+unknown", "prov03", "prov12", "prov46",
                 "all_excl_cities", "in_building_excl_cities", "whole_parcel_excl_cities"):
        for e in ends:
            x = excess(SER[name], e, hol_cv)
            plac[name][e] = x
            plac_rows.append((e.isoformat(), name, x["O"], x["E"], x["ratio"]))
    wcsv("placebo.csv", ["window_end", "series", "O", "E", "ratio"], plac_rows)
    for name in plac:
        rv = [x["ratio"] for x in plac[name].values() if not math.isnan(x["ratio"])]
        r = rush[name]["R2"]["ratio"]
        rush[name]["R3"] = {"n_windows": len(rv), "share_ge": sum(v >= r for v in rv) / len(rv),
                            "max_placebo_ratio": max(rv),
                            "max_placebo_end": str(max(plac[name], key=lambda e: plac[name][e]["ratio"])),
                            "windows_ge_1_5": [str(e) for e, x in sorted(plac[name].items()) if x["ratio"] >= 1.5]}

    def contrast(a, b):
        return math.log(a["ratio"]) - math.log(b["ratio"])
    r4 = {}
    for exp_name, ctl in (("in_building", "whole_parcel"), ("in_building+unknown", "whole_parcel"),
                          ("in_building_excl_cities", "whole_parcel_excl_cities")):
        c0 = contrast(rush[exp_name]["R2"], rush[ctl]["R2"])
        cp = [contrast(plac[exp_name][e], plac[ctl][e]) for e in ends
              if plac[exp_name][e]["O"] > 0 and plac[ctl][e]["O"] > 0]
        rr, lo, hi = contrast_ci(rush[exp_name]["R2"], rush[ctl]["R2"], scaled=True)
        rr2, lo2, hi2 = contrast_ci(rush[exp_name]["R2"], rush[ctl]["R2"], scaled=False)
        r4[exp_name] = {"ratio_of_ratios": rr, "ci_frozen": [lo, hi], "ci_delta": [lo2, hi2],
                        "empirical_p": (1 + sum(c >= c0 for c in cp)) / (1 + len(cp)), "placebo_windows": len(cp),
                        "max_placebo_ratio_of_ratios": math.exp(max(cp))}
    summ["R4"] = r4
    for name, x in rush.items():
        r1, r2, r5 = x["R1"], x["R2"], x["R5"]
        r3 = x.get("R3", {})
        rush_rows.append((name, r1["peak"], r1["base_median"], r1["base_max"], r1["base_days"], r1["peak_ratio"],
                          r1["rank_since_2016"], r2["O"], r2["E"], r2["O"] - r2["E"], r2["ratio"], r2["B"],
                          r3.get("share_ge", ""), r3.get("max_placebo_ratio", ""), r3.get("max_placebo_end", ""),
                          r5["O"], r5["E"], r5["ratio"]))
    wcsv("rush.csv", ["series", "R1_count_on_D", "R1_base_median", "R1_base_max", "R1_base_days", "R1_ratio",
                      "R1_rank_since_2016", "R2_O", "R2_E", "R2_excess", "R2_ratio", "R2_baseline_count",
                      "R3_share_placebo_ge", "R3_max_placebo_ratio", "R3_max_placebo_end",
                      "R5_O", "R5_E", "R5_ratio"], rush_rows)
    summ["rush"] = rush
    # top days since 2016
    tops = sorted(((SER["all"].get(x, 0), x) for x in alldays), reverse=True)[:10]
    summ["top_days_since_2016"] = [(str(x), n) for n, x in tops]
    # week of 31 Mar - 6 Apr 2025 vs February 2025 (the scout's measure, recomputed)
    wk = sum(SER["all"].get(x, 0) for x in days(dt.date(2025, 3, 31), dt.date(2025, 4, 6)))
    feb = sum(SER["all"].get(x, 0) for x in days(dt.date(2025, 2, 1), dt.date(2025, 2, 28)))
    summ["scout_week"] = {"week_31mar_6apr": wk, "feb_total": feb, "feb_weekly_mean": feb / 4, "ratio": wk / (feb / 4)}

    # ---------------------------------------------------------------- E1-E4 date semantics
    sem = {}
    rng = [x for x in days(dt.date(2023, 1, 1), END)]
    for name in ("all", "in_building", "whole_parcel"):
        s = SER[name]
        nw = sum(s.get(x, 0) for x in rng if nonworking(x, hol_cv))
        tot = sum(s.get(x, 0) for x in rng)
        n_nw_days = sum(1 for x in rng if nonworking(x, hol_cv))
        sat = sum(s.get(x, 0) for x in rng if x.weekday() == 5)
        sun = sum(s.get(x, 0) for x in rng if x.weekday() == 6)
        hol_wd = sum(s.get(x, 0) for x in rng if x in hol_cv and x.weekday() < 5)
        n_hol_wd = sum(1 for x in rng if x in hol_cv and x.weekday() < 5)
        n_wd = len(rng) - n_nw_days
        sem[f"E1_{name}"] = {"total": tot, "on_nonworking_days": nw, "share": nw / tot,
                             "saturday": sat, "sunday": sun, "weekday_holidays": hol_wd, "n_weekday_holidays": n_hol_wd,
                             "mean_per_working_day": (tot - nw) / n_wd, "mean_per_sunday": sun / sum(1 for x in rng if x.weekday() == 6),
                             "mean_per_weekday_holiday": hol_wd / n_hol_wd if n_hol_wd else None}
    # E2 processing order
    byc = collections.defaultdict(list)
    for r in cur:
        if r["counter"] != "A-old":
            byc[r["counter"]].append((r["num"], r["date"]))
    e2 = {}
    lag_all = []
    for c, ent in byc.items():
        lags = order_lags(ent, dt.date(2023, 1, 1))
        lags = [x for x in lags if x[1] <= END]
        lag_all += lags
        dl = [x for x in lags if x[1] == D0]
        last_num = max(n for n, _, _ in dl) if dl else None
        before = [day for n, day in ent if last_num and n < last_num]
        e2[c] = {"n": len(lags), "lag0": sum(l == 0 for _, _, l in lags) / len(lags),
                 "le3": sum(l <= 3 for _, _, l in lags) / len(lags),
                 "gt7": sum(l > 7 for _, _, l in lags) / len(lags),
                 "gt30": sum(l > 30 for _, _, l in lags) / len(lags),
                 "D_n": len(dl), "D_lag_median": statistics.median([l for _, _, l in dl]) if dl else None,
                 "D_lag_max": max([l for _, _, l in dl]) if dl else None,
                 "D_lag_gt7": sum(l > 7 for _, _, l in dl),
                 "latest_date_numbered_before_last_D": str(max(before)) if before else None}
    e2["all"] = {"n": len(lag_all), "lag0": sum(l == 0 for _, _, l in lag_all) / len(lag_all),
                 "le3": sum(l <= 3 for _, _, l in lag_all) / len(lag_all),
                 "gt7": sum(l > 7 for _, _, l in lag_all) / len(lag_all),
                 "gt30": sum(l > 30 for _, _, l in lag_all) / len(lag_all)}
    sem["E2"] = e2
    # E3 publication lag across copies
    sw = {r["sig"]: r for r in wb}
    sc = {r["sig"]: r for r in cur}
    wb_max = max(r["date"] for r in wb)
    late = [sc[s]["date"] for s in sc if s not in sw and sc[s]["date"] <= wb_max]
    recent = [s for s in sc if dt.date(2026, 9, 1) <= sc[s]["date"] <= wb_max]
    sem["E3"] = {"wayback_capture": WB, "latest_date_in_wayback_copy": str(wb_max),
                 "late_appearing_n": len(late),
                 "late_appearing_by_month": dict(sorted(collections.Counter(x.strftime("%Y-%m") for x in late).items())),
                 "late_appearing_oldest": str(min(late)) if late else None,
                 "dated_sep1_to_wbmax_in_main": len(recent),
                 "of_which_already_in_wayback": sum(1 for s in recent if s in sw),
                 "wayback_weekend_dates_present": sum(1 for r in wb if r["date"] >= dt.date(2026, 9, 1) and r["date"].weekday() >= 5)}
    # E4 changed dates
    ch = [(sw[s]["date"], sc[s]["date"]) for s in sw if s in sc and sw[s]["date"] != sc[s]["date"]]
    sem["E4"] = {"changed": len(ch), "moved_earlier": sum(b < a for a, b in ch), "moved_later": sum(b > a for a, b in ch),
                 "median_shift_days": statistics.median([(b - a).days for a, b in ch]) if ch else None,
                 "changed_dates_years": dict(collections.Counter(a.year for a, _ in ch))}

    # ---------------------------------------------------------------- historical list (added, §9)
    hist = [r for r in csv.DictReader(open(os.path.join(RAW, "gvahist_historico.csv"), encoding="utf-8"))
            if r["cod_tipo"] == "U"]
    ult = [r for r in csv.DictReader(open(os.path.join(RAW, "gvahist_ultimo.csv"), encoding="utf-8"))
           if r["cod_tipo"] == "U"]
    curk = {(r["num"], r["suf"]): r for r in cur}
    hk = {}
    bm = 0
    for r in hist:
        k = parse_hist_signatura(r["signatura"])
        if not k:
            continue
        if k[1] == "BM":
            bm += 1
            continue
        hk[k] = r
    hist_max = max(r["fecha_alta"] for r in hist)
    same = sum(1 for k, r in hk.items() if k in curk and curk[k]["date"] == d(r["fecha_alta"]))
    matched = sum(1 for k in hk if k in curk)
    sem["E4_hist"] = {"historical_extract_latest_date": hist_max, "matched_in_main": matched,
                      "same_fecha_alta": same, "share_same": same / matched}
    # E3b: entries dated <= 2025-01-10 that appear only in later copies
    uk = {parse_hist_signatura(r["signatura"]) for r in ult}
    hkeys = set(hk)
    late_ult = [d(r["fecha_alta"]) for r in ult if parse_hist_signatura(r["signatura"]) not in hkeys
                and parse_hist_signatura(r["signatura"]) and parse_hist_signatura(r["signatura"])[1] != "BM"
                and r["fecha_alta"] and r["fecha_alta"] <= hist_max]
    late_cur = collections.Counter(r["date"].strftime("%Y-%m") for k, r in curk.items()
                                   if k not in hkeys and r["date"] <= d(hist_max) and r["counter"] != "A-old")
    sem["E3_hist"] = {"historical_extract": hist_max, "last_period_extract": max(r["fecha_alta"] for r in ult),
                      "in_last_period_not_in_historical_dated_on_or_before_historical_extract": len(late_ult),
                      "in_main_not_in_historical_dated_on_or_before_extract_by_month":
                          {m: n for m, n in sorted(late_cur.items()) if m >= "2024-01"}}
    # E5 kind vs Situación (validation)
    sit = collections.Counter()
    for k, r in hk.items():
        if k in curk:
            sit[(r["cod_situacion"] or "-", curk[k]["kind"])] += 1
    sem["E5_kind_vs_situacion"] = {s: {k: sit[(s, k)] for k in KINDS} for s in ("A", "B", "C", "-")}
    # E6 reconciliation with the GVA's own counts (press, 2025-08-08)
    jj = collections.Counter(r["prov"] for r in cur if dt.date(2025, 1, 1) <= r["date"] <= dt.date(2025, 7, 31))
    yr = collections.Counter(r["prov"] for r in cur if dt.date(2024, 8, 8) <= r["date"] <= dt.date(2025, 8, 8))
    # numbered by 8 Aug 2025: number below the first number given to a dwelling dated >= 2025-08-08
    first_after = {}
    for r in cur:
        if r["counter"] != "A-old" and r["date"] >= dt.date(2025, 8, 8):
            first_after[r["counter"]] = min(first_after.get(r["counter"], 10**9), r["num"])
    jj_num = collections.Counter(r["prov"] for r in cur if dt.date(2025, 1, 1) <= r["date"] <= dt.date(2025, 7, 31)
                                 and r["counter"] in first_after and r["num"] < first_after[r["counter"]])
    sem["E6_gva_press"] = {"press_jan_jul_2025": {"03": 3391, "46": 1506, "12": 791, "stated_total": 4688},
                           "ours_jan_jul_2025": dict(jj), "ours_jan_jul_2025_total": sum(jj.values()),
                           "ours_jan_jul_2025_numbered_before_8aug": dict(jj_num),
                           "press_8aug2024_8aug2025": 8579, "ours_8aug2024_8aug2025": sum(yr.values())}
    json.dump(sem, open(P("date_semantics.json"), "w"), indent=1, ensure_ascii=False, default=str)
    summ["date_semantics"] = sem

    # ---------------------------------------------------------------- S1 churn, S2 gaps, S4 historical
    sw_set, sc_set = set(sw), set(sc)
    rem = [sw[s] for s in sw_set - sc_set]
    ch_rows = []
    pres_y = collections.Counter(r["date"].year for r in wb)
    rem_y = collections.Counter(r["date"].year for r in rem)
    for y in sorted(pres_y):
        if y >= 2015:
            ch_rows.append((y, pres_y[y], rem_y.get(y, 0), rem_y.get(y, 0) / pres_y[y] * 365 / 20))
    wcsv("churn.csv", ["fecha_alta_year", "present_2026_09_14", "removed_by_2026_10_04", "annualised_removal_rate"], ch_rows)
    summ["S1"] = {"removed": len(rem), "added": len(sc_set - sw_set), "present_wb": len(wb),
                  "annualised_overall": len(rem) / len(wb) * 365 / 20,
                  "removed_2025_2026_cohorts": sum(1 for r in rem if r["date"] >= dt.date(2025, 1, 1)),
                  "present_wb_2025_2026_cohorts": sum(1 for r in wb if r["date"] >= dt.date(2025, 1, 1))}
    # S2 gaps
    start = {}
    for c, ent in byc.items():
        jan23 = [n for n, day in ent if day.strftime("%Y-%m") == "2023-01"]
        start[c] = min(jan23)
    gap_m = collections.defaultdict(collections.Counter)
    pres_m = collections.defaultdict(collections.Counter)
    gap_w = collections.Counter()
    largest = []
    for c, ent in byc.items():
        for day, g in gaps(ent, start[c]):
            gap_m[c][day.strftime("%Y-%m")] += g
            largest.append((g, c, str(day)))
            if D0 - dt.timedelta(days=13) <= day <= D0:
                gap_w["W"] += g
            if D0 - dt.timedelta(days=87) <= day <= D0 - dt.timedelta(days=34):
                gap_w["B"] += g
        for n, day in ent:
            if n >= start[c]:
                pres_m[c][day.strftime("%Y-%m")] += 1
                if D0 - dt.timedelta(days=13) <= day <= D0:
                    gap_w["W_present"] += 1
                if D0 - dt.timedelta(days=87) <= day <= D0 - dt.timedelta(days=34):
                    gap_w["B_present"] += 1
    summ["S2_largest_gaps"] = sorted(largest, reverse=True)[:8]
    summ["S2_window"] = {"W_gaps": gap_w["W"], "W_present": gap_w["W_present"],
                         "W_gap_share": gap_w["W"] / (gap_w["W"] + gap_w["W_present"]),
                         "B_gaps": gap_w["B"], "B_present": gap_w["B_present"],
                         "B_gap_share": gap_w["B"] / (gap_w["B"] + gap_w["B_present"])}
    # S4 survival of pre-2025 cohorts from the historical list
    s4 = collections.defaultdict(collections.Counter)
    for k, r in hk.items():
        m = r["fecha_alta"][:7]
        s4[m]["hist_all"] += 1
        s4[m]["cancelled_by_extract"] += r["estado"] == "BAJA"
        s4[m]["in_main"] += k in curk
    for k, r in curk.items():
        if k not in hk and r["counter"] != "A-old":
            s4[r["date"].strftime("%Y-%m")]["main_not_in_hist"] += 1
    surv_rows = []
    for m in months(dt.date(2023, 1, 1), END):
        tg = sum(gap_m[c].get(m, 0) for c in gap_m)
        tp = sum(pres_m[c].get(m, 0) for c in pres_m)
        h = s4.get(m, collections.Counter())
        surv_rows.append((m, tp, tg, tg / (tp + tg) if tp + tg else "", h["hist_all"], h["cancelled_by_extract"],
                          h["in_main"], h["main_not_in_hist"],
                          (h["in_main"] / h["hist_all"]) if h["hist_all"] and m <= "2024-12" else ""))
    wcsv("survivorship.csv", ["month", "present_numbered", "number_gaps", "gap_share", "hist_registrations",
                              "hist_cancelled_by_2025_01_10", "hist_still_in_2026_10_04", "main_dated_month_not_in_hist",
                              "hist_survival_to_2026_10_04"], surv_rows)
    wcsv("survivorship_by_province.csv", ["month", "counter", "present_numbered", "number_gaps"],
         [(m, c, pres_m[c].get(m, 0), gap_m[c].get(m, 0)) for m in months(dt.date(2023, 1, 1), END) for c in sorted(byc)])
    summ["S4_bm_entries_excluded"] = bm

    # ---------------------------------------------------------------- F1-F4 the fall
    def mcount(pred):
        c = collections.Counter(r["date"].strftime("%Y-%m") for r in cur if pred(r))
        return c
    MC = {"all": mcount(lambda r: True)}
    for k in KINDS:
        MC[k] = mcount(lambda r, k=k: r["kind"] == k)
    MC["in_building+unknown"] = mcount(lambda r: r["kind"] in ("in_building", "unknown"))
    for p in PROV:
        MC[f"prov{p}"] = mcount(lambda r, p=p: r["prov"] == p)
    ex = lambda r: r["ine"] not in SUSPENSION_CITIES
    MC["all_excl_cities"] = mcount(ex)
    MC["in_building_excl_cities"] = mcount(lambda r: ex(r) and r["kind"] == "in_building")
    MC["whole_parcel_excl_cities"] = mcount(lambda r: ex(r) and r["kind"] == "whole_parcel")
    pre12 = months(dt.date(2023, 9, 1), dt.date(2024, 8, 1))
    post12 = months(dt.date(2025, 9, 1), dt.date(2026, 8, 1))
    y2024 = months(dt.date(2024, 1, 1), dt.date(2024, 12, 1))
    f1post = months(dt.date(2025, 5, 1), dt.date(2026, 8, 1))
    fall_rows = []
    fall = {}
    for name, c in MC.items():
        f1 = ratio_of_means([c.get(m, 0) for m in f1post], [c.get(m, 0) for m in y2024])
        f2 = ratio_of_means([c.get(m, 0) for m in post12], [c.get(m, 0) for m in pre12])
        fall[name] = {"F1": f1, "F2": f2, "pre12": sum(c.get(m, 0) for m in pre12), "post12": sum(c.get(m, 0) for m in post12),
                      "f1_post_mean": statistics.mean([c.get(m, 0) for m in f1post]),
                      "f1_pre_mean": statistics.mean([c.get(m, 0) for m in y2024])}
        fall_rows.append((name, "F1", "2025-05..2026-08 vs 2024", fall[name]["f1_post_mean"], fall[name]["f1_pre_mean"],
                          f1["ratio"], f1["lo"], f1["hi"]))
        fall_rows.append((name, "F2", "2025-09..2026-08 vs 2023-09..2024-08", fall[name]["post12"] / 12,
                          fall[name]["pre12"] / 12, f2["ratio"], f2["lo"], f2["hi"]))
    did = ratio_of_ratios(fall["in_building"]["F2"], fall["whole_parcel"]["F2"])
    did_u = ratio_of_ratios(fall["in_building+unknown"]["F2"], fall["whole_parcel"]["F2"])
    did_x = ratio_of_ratios(fall["in_building_excl_cities"]["F2"], fall["whole_parcel_excl_cities"]["F2"])
    fall_rows.append(("in_building / whole_parcel", "F2-DiD", "ratio of F2 ratios", "", "", did["ratio"], did["lo"], did["hi"]))
    fall_rows.append(("in_building+unknown / whole_parcel", "F2-DiD", "sensitivity", "", "", did_u["ratio"], did_u["lo"], did_u["hi"]))
    fall_rows.append(("excl. València and Alicante cities", "F4-DiD", "ratio of F2 ratios", "", "", did_x["ratio"], did_x["lo"], did_x["hi"]))
    # S3 worst-case bounds with number gaps
    gpre = sum(gap_m[c].get(m, 0) for c in gap_m for m in pre12)
    gpost = sum(gap_m[c].get(m, 0) for c in gap_m for m in post12)
    pre_all, post_all = fall["all"]["pre12"], fall["all"]["post12"]
    s3_all = (post_all + gpost) / pre_all
    ib_pre, ib_post = fall["in_building"]["pre12"], fall["in_building"]["post12"]
    wp_pre, wp_post = fall["whole_parcel"]["pre12"], fall["whole_parcel"]["post12"]
    s3_did = ((ib_post + gpost) / ib_pre) / (wp_post / (wp_pre + gpre))
    fall_rows.append(("all", "S3", "Post12 + all Post12 number gaps", (post_all + gpost) / 12, pre_all / 12, s3_all, "", ""))
    fall_rows.append(("in_building / whole_parcel", "S3-DiD", "all Post12 gaps to exposed, all Pre12 gaps to control Pre12", "", "", s3_did, "", ""))
    # S4: Pre12 registrations reconstructed from the historical list (incl. those cancelled since)
    pre_true = sum(s4[m]["hist_all"] + s4[m]["main_not_in_hist"] for m in pre12)
    pre_in_main = sum(s4[m]["in_main"] + s4[m]["main_not_in_hist"] for m in pre12)
    s4_all = post_all / pre_true
    fall_rows.append(("all", "S4", "Pre12 rebuilt from the historical list", post_all / 12, pre_true / 12, s4_all, "", ""))
    # S4 by building type (added, METHOD §9): survival of Pre12 cohorts by the registry's own
    # "Situación" (A block/building + B bungalow/terraced vs C chalet/villa)
    sv = collections.defaultdict(collections.Counter)
    for k, r in hk.items():
        if r["fecha_alta"][:7] in pre12:
            g = "C" if r["cod_situacion"] == "C" else ("AB" if r["cod_situacion"] in ("A", "B") else "other")
            sv[g]["all"] += 1
            sv[g]["in_main"] += k in curk
    surv_ab, surv_c = sv["AB"]["in_main"] / sv["AB"]["all"], sv["C"]["in_main"] / sv["C"]["all"]
    s4_did = did["ratio"] * surv_ab / surv_c
    fall_rows.append(("in_building / whole_parcel", "S4-DiD", "Pre12 divided by survival of Situación A+B vs C", "", "", s4_did, "", ""))
    summ["S4_by_situacion"] = {"AB": dict(sv["AB"]), "C": dict(sv["C"]), "survival_AB": surv_ab, "survival_C": surv_c,
                               "did_adjusted": s4_did}
    # F5 (added, METHOD §9): after Decreto-ley 9/2024 and before the run-up, against a year earlier
    p5 = months(dt.date(2024, 9, 1), dt.date(2025, 2, 1))
    p5ref = months(dt.date(2023, 9, 1), dt.date(2024, 2, 1))
    f5 = {name: ratio_of_means([MC[name].get(m, 0) for m in p5], [MC[name].get(m, 0) for m in p5ref])
          for name in ("all", "in_building", "whole_parcel")}
    f5_did = ratio_of_ratios(f5["in_building"], f5["whole_parcel"])
    for name, v in f5.items():
        fall_rows.append((name, "F5", "2024-09..2025-02 vs 2023-09..2024-02", statistics.mean([MC[name].get(m, 0) for m in p5]),
                          statistics.mean([MC[name].get(m, 0) for m in p5ref]), v["ratio"], v["lo"], v["hi"]))
    fall_rows.append(("in_building / whole_parcel", "F5-DiD", "after DL 9/2024, before the run-up", "", "", f5_did["ratio"], f5_did["lo"], f5_did["hi"]))
    summ["F5"] = {k: v for k, v in f5.items()}
    summ["F5_DiD"] = f5_did
    wcsv("fall.csv", ["series", "measure", "definition", "post_monthly_mean", "pre_monthly_mean", "ratio", "ci_lo", "ci_hi"], fall_rows)
    summ["fall"] = {k: {"F1": v["F1"], "F2": v["F2"], "pre12": v["pre12"], "post12": v["post12"],
                        "f1_post_mean": v["f1_post_mean"], "f1_pre_mean": v["f1_pre_mean"]} for k, v in fall.items()}
    summ["F2_DiD"] = did
    summ["F2_DiD_unknown_as_exposed"] = did_u
    summ["F4_DiD_excl_cities"] = did_x
    summ["S3"] = {"gaps_pre12": gpre, "gaps_post12": gpost, "ratio_all": s3_all, "did": s3_did}
    summ["S4"] = {"pre12_registrations_rebuilt": pre_true, "pre12_in_main": pre_in_main, "pre12_main_count": pre_all,
                  "pre12_survival": pre_in_main / pre_true, "ratio_all": s4_all}

    # F3 timing
    tim = []
    for m in months(dt.date(2025, 1, 1), END):
        ref = ("2023" if m[5:] in ("09", "10", "11", "12") else "2024") + m[4:]
        row = [m, ref]
        for name in ("all", "in_building", "whole_parcel", "unknown"):
            row += [MC[name].get(m, 0), MC[name].get(ref, 0),
                    MC[name].get(m, 0) / MC[name][ref] if MC[name].get(ref) else ""]
        ib, wp = MC["in_building"].get(m, 0), MC["whole_parcel"].get(m, 0)
        row.append(wp / (ib + wp) if ib + wp else "")
        tim.append(row)
    wcsv("monthly_timing.csv", ["month", "reference_month"] + [f"{n}_{x}" for n in ("all", "in_building", "whole_parcel", "unknown")
                                                              for x in ("n", "ref_n", "ratio")] + ["whole_parcel_share"], tim)
    # F3 summary: the four months after the deadline month, against the same months of 2024
    ma25, ma24 = months(dt.date(2025, 5, 1), dt.date(2025, 8, 1)), months(dt.date(2024, 5, 1), dt.date(2024, 8, 1))
    f3 = {name: {"n": sum(MC[name].get(m, 0) for m in ma25), "ref": sum(MC[name].get(m, 0) for m in ma24)}
          for name in ("all", "in_building", "whole_parcel")}
    for v in f3.values():
        v["ratio"] = v["n"] / v["ref"]
    f3["did"] = f3["in_building"]["ratio"] / f3["whole_parcel"]["ratio"]
    summ["F3_may_aug_2025"] = f3
    share = lambda ms: (sum(MC["whole_parcel"].get(m, 0) for m in ms) /
                        sum(MC["whole_parcel"].get(m, 0) + MC["in_building"].get(m, 0) for m in ms))
    summ["whole_parcel_share"] = {"pre12": share(pre12), "2025-03..04": share(["2025-03", "2025-04"]),
                                  "2025-05..08": share(months(dt.date(2025, 5, 1), dt.date(2025, 8, 1))), "post12": share(post12)}

    # ---------------------------------------------------------------- INE VTE check
    want = {"Total Nacional": "Spain", "09 Cataluña": "Catalonia", "10 Comunitat Valenciana": "Comunitat Valenciana",
            "03 Alicante/Alacant": "Alicante", "12 Castellón/Castelló": "Castellón", "46 Valencia/València": "Valencia"}
    per = ["2024M08", "2024M11", "2025M05", "2025M11", "2026M05"]
    vte = {}
    rd = csv.reader(open(os.path.join(DATA, "raw", "ine", "39363.csv"), encoding="utf-8-sig"), delimiter=";")
    next(rd)
    for r in rd:
        if r[3] or r[4] != "Viviendas turísticas" or r[5] not in per:
            continue
        key = r[2] or r[1] or r[0]
        if key in want:
            vte[(want[key], r[5])] = int(r[6].replace(".", ""))
    reg_flow = {}
    bounds = [dt.date(2024, 8, 1), dt.date(2024, 11, 1), dt.date(2025, 5, 1), dt.date(2025, 11, 1), dt.date(2026, 5, 1)]
    ine_rows = []
    for area in want.values():
        for i, p in enumerate(per):
            flow = ""
            if area in ("Comunitat Valenciana", "Alicante", "Castellón", "Valencia") and i > 0:
                pc = {"Alicante": "03", "Castellón": "12", "Valencia": "46"}.get(area)
                flow = sum(1 for r in cur if bounds[i - 1] <= r["date"] < bounds[i] and (pc is None or r["prov"] == pc))
            ine_rows.append((area, p, vte.get((area, p), ""), flow))
    wcsv("ine_vte.csv", ["area", "period", "ine_vte_listings", "registry_new_since_previous_period_start"], ine_rows)
    summ["ine_vte"] = {f"{a} {p}": v for (a, p), v in vte.items()}

    # ---------------------------------------------------------------- after the review (METHOD §9.9)
    rv = {}
    # (a) placebo inference with less overlap: every tenth working-day window end
    thin = ends[::10]
    for exp_name, ctl in (("in_building", "whole_parcel"), ("in_building_excl_cities", "whole_parcel_excl_cities")):
        c0 = contrast(rush[exp_name]["R2"], rush[ctl]["R2"])
        cp_all = [contrast(plac[exp_name][e], plac[ctl][e]) for e in ends
                  if plac[exp_name][e]["O"] > 0 and plac[ctl][e]["O"] > 0]
        cp = [contrast(plac[exp_name][e], plac[ctl][e]) for e in thin
              if plac[exp_name][e]["O"] > 0 and plac[ctl][e]["O"] > 0]
        sd = statistics.stdev(cp_all)
        mu = statistics.mean(cp_all)
        ac1 = (sum((a - mu) * (b - mu) for a, b in zip(cp_all, cp_all[1:])) /
               sum((a - mu) ** 2 for a in cp_all))
        rv[f"thinned_contrast_{exp_name}"] = {
            "windows": len(cp), "ge": sum(c >= c0 for c in cp), "p": (1 + sum(c >= c0 for c in cp)) / (1 + len(cp)),
            "placebo_sd_log": sd, "z": (c0 - mu) / sd, "lag1_autocorrelation": ac1,
            "ci_placebo_calibrated": [math.exp(c0 - 1.96 * sd), math.exp(c0 + 1.96 * sd)]}
    for name in ("all", "all_excl_cities"):
        r = rush[name]["R2"]["ratio"]
        tv = [plac[name][e]["ratio"] for e in thin]
        rv[f"thinned_R2_{name}"] = {"windows": len(tv), "ge": sum(v >= r for v in tv), "p": (1 + sum(v >= r for v in tv)) / (1 + len(tv))}
    # exclusion extended to D+87 (baselines containing the run-up)
    ends2 = [e for e in ends if not (dt.date(2025, 6, 1) <= e <= D0 + dt.timedelta(days=87))]
    rv["R3_exclusion_to_D_plus_87"] = {"windows": len(ends2),
                                       "max_all": max(plac["all"][e]["ratio"] for e in ends2),
                                       "ge_all": sum(plac["all"][e]["ratio"] >= rush["all"]["R2"]["ratio"] for e in ends2)}
    # (b) the same calendar window in other years (seasonality)
    seas = {}
    for y in (2023, 2024, 2026):
        e = dt.date(y, 4, 2)
        seas[y] = {k: excess(SER[k], e, hol_cv) for k in ("all", "in_building", "whole_parcel")}
    sf = statistics.mean([seas[y]["all"]["ratio"] for y in (2023, 2024)])
    o, e_ = rush["all"]["R2"]["O"], rush["all"]["R2"]["E"]
    rv["same_window_other_years"] = {str(y): {k: {"O": v["O"], "E": v["E"], "ratio": v["ratio"]} for k, v in seas[y].items()} for y in seas}
    rv["seasonal_factor_2023_2024"] = sf
    rv["excess_seasonally_adjusted"] = o - e_ * sf
    rv["ratio_seasonally_adjusted"] = o / (e_ * sf)
    rv["same_window_contrast"] = {str(y): seas[y]["in_building"]["ratio"] / seas[y]["whole_parcel"]["ratio"] for y in seas}
    # (c) rank of D without the two cities
    rv["rank_D_without_cities"] = int(rush["all_excl_cities"]["R1"]["rank_since_2016"])
    # (d) reference-period sensitivity of F2-DiD
    for lab, (a, b) in {"2022-09..2023-08": ((2022, 9), (2023, 8)), "2022": ((2022, 1), (2022, 12))}.items():
        ref = months(dt.date(*a, 1), dt.date(*b, 1))
        fi = ratio_of_means([MC["in_building"].get(m, 0) for m in post12], [MC["in_building"].get(m, 0) for m in ref])
        fw = ratio_of_means([MC["whole_parcel"].get(m, 0) for m in post12], [MC["whole_parcel"].get(m, 0) for m in ref])
        fa = ratio_of_means([MC["all"].get(m, 0) for m in post12], [MC["all"].get(m, 0) for m in ref])
        rv[f"F2_ref_{lab}"] = {"all": fa, "in_building": fi, "whole_parcel": fw, "did": ratio_of_ratios(fi, fw)}
    half = collections.defaultdict(lambda: [0, 0])
    for m in months(dt.date(2022, 1, 1), dt.date(2026, 6, 1)):
        h = m[:4] + ("H1" if int(m[5:]) <= 6 else "H2")
        half[h][0] += MC["whole_parcel"].get(m, 0)
        half[h][1] += MC["whole_parcel"].get(m, 0) + MC["in_building"].get(m, 0)
    rv["whole_parcel_share_by_half_year"] = {h: v[0] / v[1] for h, v in sorted(half.items())}
    # survival of the 2022-09..2023-08 cohorts by building type (is the older reference lower because of attrition?)
    ref22 = months(dt.date(2022, 9, 1), dt.date(2023, 8, 1))
    sv22 = collections.defaultdict(collections.Counter)
    for k, r in hk.items():
        if r["fecha_alta"][:7] in ref22:
            g = "C" if r["cod_situacion"] == "C" else ("AB" if r["cod_situacion"] in ("A", "B") else "other")
            sv22[g]["all"] += 1
            sv22[g]["in_main"] += k in curk
    rv["survival_2022_09_2023_08"] = {g: v["in_main"] / v["all"] for g, v in sv22.items() if v["all"]}
    # survival-corrected references: registrations rebuilt from the historical list, as in S4
    for lab, (a, b) in {"2022-09..2023-08": ((2022, 9), (2023, 8)), "2022": ((2022, 1), (2022, 12))}.items():
        ref = months(dt.date(*a, 1), dt.date(*b, 1))
        rebuilt = sum(s4[m]["hist_all"] + s4[m]["main_not_in_hist"] for m in ref)
        inmain = sum(s4[m]["in_main"] + s4[m]["main_not_in_hist"] for m in ref)
        obs = sum(MC["all"].get(m, 0) for m in ref)
        rv[f"F2_ref_{lab}"]["rebuilt"] = {"observed": obs, "rebuilt": rebuilt, "survival": inmain / rebuilt,
                                          "ratio_all_corrected": post_all / (obs / (inmain / rebuilt)),
                                          "post_monthly": post_all / 12, "ref_monthly_observed": obs / len(ref)}
    # (e) weekend/holiday share by year
    rv["nonworking_share_by_year"] = {}
    for y in (2023, 2024, 2025, 2026):
        rr = [x for x in days(dt.date(y, 1, 1), min(END, dt.date(y, 12, 31)))]
        tt = sum(SER["all"].get(x, 0) for x in rr)
        rv["nonworking_share_by_year"][y] = sum(SER["all"].get(x, 0) for x in rr if nonworking(x, hol_cv)) / tt
    # (f) late-appearing entries numbered above every number already published on 14 September
    wbmax = collections.defaultdict(int)
    for r in wb:
        if r["counter"] != "A-old":
            wbmax[r["counter"]] = max(wbmax[r["counter"]], r["num"])
    lateents = [sc[s_] for s_ in sc if s_ not in sw and sc[s_]["date"] <= wb_max and sc[s_]["counter"] != "A-old"]
    late26 = [r for r in lateents if r["date"].year == 2026]
    rv["E3c_late_2026_entries"] = {"n": len(late26), "numbered_above_all_published": sum(r["num"] > wbmax[r["counter"]] for r in late26)}
    # (g) the unknown kind in the window, and unknown as control
    wd = set(days(D0 - dt.timedelta(days=13), D0))
    unk = [r for r in cur if r["kind"] == "unknown" and r["date"] in wd]
    rv["unknown_in_window"] = {"n": len(unk), "valencia_city": sum(r["ine"] == "46250" for r in unk),
                               "cargo_not_0001": sum(r["cargo0001"] == "0" for r in unk),
                               "on_D": sum(r["date"] == D0 for r in unk),
                               "on_D_valencia_city": sum(r["date"] == D0 and r["ine"] == "46250" for r in unk)}
    SER["whole_parcel+unknown"] = series(lambda r: r["kind"] in ("whole_parcel", "unknown"))
    rv["contrast_unknown_as_control"] = rush["in_building"]["R2"]["ratio"] / excess(SER["whole_parcel+unknown"], D0, hol_cv)["ratio"]
    ua = collections.Counter(r["ine"] == "46250" for r in cur if r["kind"] == "unknown" and dt.date(2025, 1, 1) <= r["date"] <= dt.date(2025, 4, 30))
    rv["unknown_jan_apr_2025"] = {"total": sum(ua.values()), "valencia_city": ua[True]}
    # (h) S4 including the older Benidorm series on both sides
    bm_pre = sum(1 for r in hist if (parse_hist_signatura(r["signatura"]) or (0, ""))[1] == "BM" and r["fecha_alta"][:7] in pre12)
    aold_pre = sum(1 for r in cur if r["counter"] == "A-old" and r["date"].strftime("%Y-%m") in pre12)
    pre_true_bm = pre_true + bm_pre
    rv["S4_with_BM"] = {"bm_hist_pre12": bm_pre, "a_old_main_pre12": aold_pre, "pre12_rebuilt": pre_true_bm,
                        "survival": (pre_in_main + aold_pre) / pre_true_bm, "ratio_all": post_all / pre_true_bm}
    rv["pre12_cancelled_by_2025_01_10"] = sum(s4[m]["cancelled_by_extract"] for m in pre12)
    # (i) the kind classification by registration year
    kv_y = {}
    for y in range(2016, 2027):
        for k in ("in_building", "whole_parcel"):
            g = [r for r in cur if r["kind"] == k and r["date"].year == y]
            if g:
                kv_y[f"{y} {k}"] = {"n": len(g), "cargo0001": sum(r["cargo0001"] == "1" for r in g) / len(g),
                                    "parcel_shared": sum((r["parcel_n"] or 0) > 1 for r in g) / len(g)}
    rv["kind_validation_by_year"] = kv_y
    # (j) the lag of the Alicante deadline cohort
    summ["post_review"] = rv

    # ---------------------------------------------------------------- coordinator review (METHOD §9.10)
    co = {}
    TORRE, VLC, ALC = "03133", "46250", "03014"
    thin2 = [e for e in ends[::10] if not (dt.date(2025, 6, 1) <= e <= D0 + dt.timedelta(days=87))]
    co["thinned_windows"] = len(thin2)
    # day index and prefix sums per (municipality, kind) and per municipality, by day type
    f0, f1 = dt.date(2016, 1, 1), dt.date(2026, 9, 30)
    alld = days(f0, f1)
    ix = {x: i for i, x in enumerate(alld)}
    nwk = [nonworking(x, hol_cv) for x in alld]
    pcw, pcn = [0], [0]
    for i in range(len(alld)):
        pcw.append(pcw[-1] + (0 if nwk[i] else 1))
        pcn.append(pcn[-1] + (1 if nwk[i] else 0))
    raw = collections.defaultdict(collections.Counter)
    for r in cur:
        if f0 <= r["date"] <= f1:
            raw[(r["ine"], r["kind"])][ix[r["date"]]] += 1
            raw[(r["ine"], "*")][ix[r["date"]]] += 1
    pref = {}
    for key, c in raw.items():
        pw, pn = [0], [0]
        for i in range(len(alld)):
            v = c.get(i, 0)
            pw.append(pw[-1] + (0 if nwk[i] else v))
            pn.append(pn[-1] + (v if nwk[i] else 0))
        pref[key] = (pw, pn)
    munis = sorted({k[0] for k in raw})

    def win(key, e):
        """O, E, B of one (municipality, kind) series for the window ending e (same rule as excess())."""
        if key not in pref:
            return 0, 0.0, 0
        pw, pn = pref[key]
        w0, w1 = ix[e - dt.timedelta(days=13)], ix[e] + 1
        b0, b1 = ix[e - dt.timedelta(days=87)], ix[e - dt.timedelta(days=34)] + 1
        bw, bn = pw[b1] - pw[b0], pn[b1] - pn[b0]
        dw, dn = pcw[b1] - pcw[b0], pcn[b1] - pcn[b0]
        o = (pw[w1] - pw[w0]) + (pn[w1] - pn[w0])
        ewin = (bw / dw if dw else 0) * (pcw[w1] - pcw[w0]) + (bn / dn if dn else 0) * (pcn[w1] - pcn[w0])
        return o, ewin, bw + bn

    def fe_contrast(e, excl=()):
        """Flats-to-houses contrast within municipalities: Poisson O_mk ~ E_mk a_m b_k, b_house = 1,
        over municipalities with both kinds present in the baseline. Returns (b, n_munis, O_f, O_h)."""
        rows_ = []
        for m in munis:
            if m in excl:
                continue
            of, ef, bf = win((m, "in_building"), e)
            oh, eh, bh = win((m, "whole_parcel"), e)
            if bf > 0 and bh > 0:
                rows_.append((of, ef, oh, eh))
        if not rows_ or sum(r[0] for r in rows_) == 0 or sum(r[2] for r in rows_) == 0:
            return None
        b = 1.0
        for _ in range(500):
            a = [(of + oh) / (ef * b + eh) for of, ef, oh, eh in rows_]
            nb = sum(r[0] for r in rows_) / sum(r[1] * ai for r, ai in zip(rows_, a))
            if abs(nb - b) < 1e-12:
                b = nb
                break
            b = nb
        return b, len(rows_), sum(r[0] for r in rows_), sum(r[2] for r in rows_)

    def fe_test(excl=()):
        c0 = fe_contrast(D0, excl)
        pl = [fe_contrast(e, excl) for e in thin2]
        lp = [math.log(x[0]) for x in pl if x and x[0] > 0]
        sd = statistics.stdev(lp)
        lc = math.log(c0[0])
        return {"contrast": c0[0], "municipalities": c0[1], "flats_in_window": c0[2], "houses_in_window": c0[3],
                "placebo_windows": len(lp), "ge": sum(v >= lc for v in lp), "p": (1 + sum(v >= lc for v in lp)) / (1 + len(lp)),
                "placebo_sd_log": sd, "ci_placebo_calibrated": [math.exp(lc - 1.96 * sd), math.exp(lc + 1.96 * sd)],
                "same_window": {str(y): (fe_contrast(dt.date(y, 4, 2), excl) or [None])[0] for y in (2023, 2024, 2026)}}
    co["within_municipality"] = fe_test()
    co["within_municipality_excl_vlc_alc_torre"] = fe_test((VLC, ALC, TORRE))
    co["within_municipality_excl_torre"] = fe_test((TORRE,))
    # the pooled contrast and the all-dwellings ratio on the same 78 thinned windows
    c0p = contrast(rush["in_building"]["R2"], rush["whole_parcel"]["R2"])
    cpp = [contrast(plac["in_building"][e], plac["whole_parcel"][e]) for e in thin2
           if plac["in_building"][e]["O"] > 0 and plac["whole_parcel"][e]["O"] > 0]
    co["pooled_contrast_thinned"] = {"windows": len(cpp), "ge": sum(c >= c0p for c in cpp), "p": (1 + sum(c >= c0p for c in cpp)) / (1 + len(cpp))}
    ra = rush["all"]["R2"]["ratio"]
    va = [plac["all"][e]["ratio"] for e in thin2]
    co["all_thinned"] = {"windows": len(va), "ge": sum(v >= ra for v in va), "p": (1 + sum(v >= ra for v in va)) / (1 + len(va)),
                         "max": max(va)}
    # where the excess is: decomposition by municipality
    dec = []
    for m in munis:
        o, e_, _ = win((m, "*"), D0)
        if o or e_:
            dec.append((m, o, e_, o - e_))
    dec.sort(key=lambda x: -x[3])
    tot_ex = rush["all"]["R2"]["O"] - rush["all"]["R2"]["E"]
    names = {r["ine"]: r["muni"] for r in cur}
    top = dec[:10]
    wcsv("rush_by_municipality.csv", ["ine_code", "municipality", "O", "E", "excess", "share_of_excess"],
         [(m, names[m], o, e_, x, x / tot_ex) for m, o, e_, x in top] +
         [("other", f"{len(dec) - len(top)} other municipalities", sum(r[1] for r in dec[10:]), sum(r[2] for r in dec[10:]),
           sum(r[3] for r in dec[10:]), sum(r[3] for r in dec[10:]) / tot_ex)])
    exd = {m: x for m, _, _, x in dec}
    co["excess_total"] = tot_ex
    co["excess_vlc"], co["excess_torre"] = exd.get(VLC, 0), exd.get(TORRE, 0)
    co["share_vlc_torre"] = (exd.get(VLC, 0) + exd.get(TORRE, 0)) / tot_ex
    kinds_w = collections.Counter((r["ine"], r["kind"]) for r in cur if D0 - dt.timedelta(days=13) <= r["date"] <= D0)
    co["window_kinds"] = {m: {k: kinds_w.get((m, k), 0) for k in KINDS} for m in (VLC, TORRE)}

    def r25(s):
        """R2 and R5 (D+1..D+28 against the same baseline) for one daily series."""
        x2 = excess(s, D0, hol_cv)
        base = days(D0 - dt.timedelta(days=87), D0 - dt.timedelta(days=34))
        tb, cb = {True: 0, False: 0}, {True: 0, False: 0}
        for x in base:
            k = nonworking(x, hol_cv)
            tb[k] += s.get(x, 0)
            cb[k] += 1
        mean = {k: tb[k] / cb[k] for k in tb}
        w5 = days(D0 + dt.timedelta(days=1), D0 + dt.timedelta(days=28))
        o5, e5 = sum(s.get(x, 0) for x in w5), sum(mean[nonworking(x, hol_cv)] for x in w5)
        sw_ = {y: excess(s, dt.date(y, 4, 2), hol_cv)["ratio"] for y in (2023, 2024, 2026)}
        sf_ = (sw_[2023] + sw_[2024]) / 2
        return {"R2_O": x2["O"], "R2_E": x2["E"], "R2": x2["ratio"], "R5_O": o5, "R5_E": e5, "R5": o5 / e5 if e5 else None,
                "same_window": sw_, "R2_seasonally_adjusted": x2["O"] / (x2["E"] * sf_), "excess_seasonally_adjusted": x2["O"] - x2["E"] * sf_}
    groups = {
        "valencia_city": lambda r: r["ine"] == VLC,
        "torrevieja": lambda r: r["ine"] == TORRE,
        "all_excl_vlc_torre": lambda r: r["ine"] not in (VLC, TORRE),
        "all_excl_vlc_alc_torre": lambda r: r["ine"] not in (VLC, ALC, TORRE),
        "in_building_excl_vlc_alc_torre": lambda r: r["ine"] not in (VLC, ALC, TORRE) and r["kind"] == "in_building",
        "whole_parcel_excl_vlc_alc_torre": lambda r: r["ine"] not in (VLC, ALC, TORRE) and r["kind"] == "whole_parcel",
        "in_building_rest": lambda r: r["ine"] not in (VLC, TORRE) and r["kind"] == "in_building",
        "whole_parcel_rest": lambda r: r["ine"] not in (VLC, TORRE) and r["kind"] == "whole_parcel",
        "in_building_excl_torre": lambda r: r["ine"] != TORRE and r["kind"] == "in_building",
        "all_excl_torre": lambda r: r["ine"] != TORRE,
    }
    co["groups"] = {g: r25(series(f)) for g, f in groups.items()}
    co["groups"]["in_building_vlc"] = r25(series(lambda r: r["ine"] == VLC and r["kind"] in ("in_building", "unknown")))
    co["groups"]["in_building_torre"] = r25(series(lambda r: r["ine"] == TORRE and r["kind"] == "in_building"))
    # the deadline cohort of València city: buildings and cadastral references
    if all(r["bkey"] for r in cur):
        coh = [r for r in cur if r["ine"] == VLC and r["date"] == D0]
        bc = collections.Counter(r["bkey"] for r in coh)
        jf = [r for r in cur if dt.date(2025, 1, 1) <= r["date"] <= dt.date(2025, 2, 28)]
        co["valencia_deadline_cohort"] = {
            "dwellings": len(coh), "kinds": dict(collections.Counter(r["kind"] for r in coh)),
            "buildings_street_and_number": len(bc), "in_buildings_with_5_or_more": sum(v for v in bc.values() if v >= 5),
            "largest_buildings": sorted(bc.values(), reverse=True)[:4],
            "without_cadastral_reference": sum(r["has_ref"] == "0" for r in coh),
            "share_without_reference_jan_feb_2025_all": sum(r["has_ref"] == "0" for r in jf) / len(jf)}
        # filing events: one per building and day and kind
        ev = {}
        for k in ("in_building", "whole_parcel"):
            sset = collections.defaultdict(set)
            for r in cur:
                if r["kind"] == k:
                    sset[r["date"]].add(r["bkey"])
            ev[k] = collections.Counter({x: len(v) for x, v in sset.items()})
        ef_, eh_ = excess(ev["in_building"], D0, hol_cv), excess(ev["whole_parcel"], D0, hol_cv)
        c0e = math.log(ef_["ratio"]) - math.log(eh_["ratio"])
        cpe = [math.log(excess(ev["in_building"], e, hol_cv)["ratio"]) - math.log(excess(ev["whole_parcel"], e, hol_cv)["ratio"])
               for e in thin2]
        sde = statistics.stdev(cpe)
        co["filing_events"] = {"flats_R2": ef_["ratio"], "houses_R2": eh_["ratio"], "contrast": math.exp(c0e),
                               "p": (1 + sum(c >= c0e for c in cpe)) / (1 + len(cpe)),
                               "ci_placebo_calibrated": [math.exp(c0e - 1.96 * sde), math.exp(c0e + 1.96 * sde)]}
    # the fall: paired monthly log-odds of flats to houses, by calendar month
    def paired(ref_months):
        dd = []
        for pm, rm in zip(post12, ref_months):
            dd.append(math.log(MC["in_building"][pm] / MC["whole_parcel"][pm]) - math.log(MC["in_building"][rm] / MC["whole_parcel"][rm]))
        mu, se = statistics.mean(dd), statistics.stdev(dd) / math.sqrt(len(dd))
        return {"ratio": math.exp(mu), "lo": math.exp(mu - 1.96 * se), "hi": math.exp(mu + 1.96 * se),
                "lo_t11": math.exp(mu - 2.201 * se), "hi_t11": math.exp(mu + 2.201 * se)}
    co["paired_did"] = {"pre12": paired(pre12), "2022-09..2023-08": paired(months(dt.date(2022, 9, 1), dt.date(2023, 8, 1))),
                        "2022": paired([f"2022-{m[5:]}" for m in post12])}
    # the GVA's «casi el doble»: registrations dated in the year before and the year after 8 Aug 2024
    def year_count(a, b):
        surv = sum(1 for r in cur if a <= r["date"] <= b)
        reb = (sum(1 for k, r in hk.items() if a <= d(r["fecha_alta"]) <= b) +
               sum(1 for k, r in curk.items() if k not in hk and r["counter"] != "A-old" and a <= r["date"] <= b))
        return {"surviving": surv, "rebuilt": reb}
    y1 = year_count(dt.date(2023, 8, 8), dt.date(2024, 8, 7))
    y2 = year_count(dt.date(2024, 8, 8), dt.date(2025, 8, 8))
    co["gva_year"] = {"2023-08-08..2024-08-07": y1, "2024-08-08..2025-08-08": y2,
                      "ratio_surviving": y2["surviving"] / y1["surviving"], "ratio_rebuilt_first_year": y2["surviving"] / y1["rebuilt"]}
    summ["coordinator_review"] = co

    import hashlib
    summ["inputs_sha256"] = {os.path.relpath(f, R): hashlib.sha256(open(f, "rb").read()).hexdigest()
                             for f in [os.path.join(RAW, f"gva_min_{x}.csv") for x in (MAIN, WB)] +
                             [os.path.join(RAW, f"gvahist_{x}.csv") for x in ("historico", "ultimo")] +
                             [os.path.join(DATA, "raw", "ine", "39363.csv"), P("holidays.csv")]}
    json.dump(summ, open(P("summary.json"), "w"), indent=1, ensure_ascii=False, default=str)
    print("rush all:", rush["all"]["R1"], rush["all"]["R2"])
    print("fall F2 all:", fall["all"]["F2"], "DiD:", did)


if __name__ == "__main__":
    main()
