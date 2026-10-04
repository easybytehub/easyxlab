#!/usr/bin/env python3
"""S13 comparators (METHOD.md §1.7): the same run-up, placebo and fall measures for every other
regional registry with a usable registration date. Reads data/raw/comparators/<region>_daily.csv
(built by scripts/comparators/*.py) and writes aggregates to data/.

    python3 scripts/analyse_comparators.py
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
from s13lib import d, days, nonworking, excess, ratio_of_means, rank_desc

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(R, "data")
D0 = dt.date(2025, 4, 2)
END = dt.date(2026, 8, 31)
# region -> (holiday code, label, LPH governs horizontal property there?)
REGIONS = {"andalucia": ("AND", "Andalucía", True), "euskadi": ("PV", "País Vasco", True),
           "mallorca": ("IB", "Mallorca", True)}


def months(a, b):
    y, m, out = a.year, a.month, []
    while (y, m) <= (b.year, b.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def load_gva():
    s = collections.Counter()
    for r in csv.DictReader(open(os.path.join(DATA, "daily_kind.csv"), encoding="utf-8")):
        s[d(r["date"])] += int(r["n"])
    return s


def main():
    hol = collections.defaultdict(set)
    for r in csv.DictReader(open(os.path.join(DATA, "holidays.csv"), encoding="utf-8")):
        hol[r["region"]].add(d(r["date"]))
    series = {}
    for reg in REGIONS:
        s = collections.Counter()
        for r in csv.DictReader(open(os.path.join(DATA, "raw", "comparators", f"{reg}_daily.csv"), encoding="utf-8")):
            if r["date"]:
                s[d(r["date"])] += int(r["n"])
        series[reg] = s
    series["comunitat_valenciana"] = load_gva()
    labels = dict((k, v[1]) for k, v in REGIONS.items())
    labels["comunitat_valenciana"] = "Comunitat Valenciana"
    hcode = {k: v[0] for k, v in REGIONS.items()}
    hcode["comunitat_valenciana"] = "CV"

    rows, out, daily_rows, monthly_rows = [], {}, [], []
    base_days_all = days(dt.date(2025, 1, 7), dt.date(2025, 2, 28))
    for reg, s in series.items():
        H = hol["ES"] | hol[hcode[reg]]
        bdays = [x for x in base_days_all if not nonworking(x, H)]
        bv = [s.get(x, 0) for x in bdays]
        rng = days(dt.date(2023, 1, 1), END)
        tot = sum(s.get(x, 0) for x in rng)
        nw = sum(s.get(x, 0) for x in rng if nonworking(x, H))
        n_wd = sum(1 for x in rng if not nonworking(x, H))
        n_sun = sum(1 for x in rng if x.weekday() == 6)
        r2 = excess(s, D0, H)
        ends = [x for x in days(dt.date(2023, 4, 3), END)
                if not nonworking(x, H) and not (dt.date(2025, 3, 1) <= x <= dt.date(2025, 5, 31))]
        pv = [excess(s, e, H)["ratio"] for e in ends]
        pv = [v for v in pv if not math.isnan(v)]
        base = days(D0 - dt.timedelta(days=87), D0 - dt.timedelta(days=34))
        tb, cb = {True: 0, False: 0}, {True: 0, False: 0}
        for x in base:
            k = nonworking(x, H)
            tb[k] += s.get(x, 0)
            cb[k] += 1
        mean = {k: tb[k] / cb[k] for k in tb}
        w5 = days(D0 + dt.timedelta(days=1), D0 + dt.timedelta(days=28))
        o5 = sum(s.get(x, 0) for x in w5)
        e5 = sum(mean[nonworking(x, H)] for x in w5)
        mc = collections.Counter(x.strftime("%Y-%m") for x in s.elements())
        pre12 = months(dt.date(2023, 9, 1), dt.date(2024, 8, 1))
        post12 = months(dt.date(2025, 9, 1), dt.date(2026, 8, 1))
        f2 = ratio_of_means([mc.get(m, 0) for m in post12], [mc.get(m, 0) for m in pre12])
        run = days(dt.date(2025, 3, 24), dt.date(2025, 4, 4))
        peak_day = max(run, key=lambda x: s.get(x, 0))
        o = {"label": labels[reg], "total_2023_to_end": tot, "nonworking_share": nw / tot if tot else None,
             "mean_per_working_day": (tot - nw) / n_wd, "mean_per_sunday": sum(s.get(x, 0) for x in rng if x.weekday() == 6) / n_sun,
             "count_on_D": s.get(D0, 0), "base_median": statistics.median(bv), "base_max": max(bv),
             "rank_D_since_2016": rank_desc([s.get(x, 0) for x in days(dt.date(2016, 1, 1), END)], s.get(D0, 0)),
             "peak_day_24mar_4apr": str(peak_day), "peak_count": s.get(peak_day, 0),
             "rank_peak_since_2016": rank_desc([s.get(x, 0) for x in days(dt.date(2016, 1, 1), END)], s.get(peak_day, 0)),
             "R2": r2, "R3_share_ge": (sum(v >= r2["ratio"] for v in pv) / len(pv)) if pv else None,
             "R3_max": max(pv) if pv else None, "R5": {"O": o5, "E": e5, "ratio": o5 / e5 if e5 else None},
             "F2": f2, "pre12": sum(mc.get(m, 0) for m in pre12), "post12": sum(mc.get(m, 0) for m in post12)}
        out[reg] = o
        rows.append((reg, labels[reg], o["count_on_D"], o["base_median"], o["rank_D_since_2016"], o["peak_day_24mar_4apr"],
                     o["peak_count"], o["rank_peak_since_2016"], r2["O"], r2["E"], r2["ratio"], o["R3_share_ge"], o["R3_max"],
                     o5, e5, o["R5"]["ratio"], o["pre12"], o["post12"], f2["ratio"], f2["lo"], f2["hi"],
                     o["nonworking_share"], o["mean_per_working_day"], o["mean_per_sunday"]))
        for x in days(dt.date(2024, 1, 1), dt.date(2026, 9, 30)):
            daily_rows.append((x.isoformat(), reg, s.get(x, 0)))
        for m in months(dt.date(2023, 1, 1), dt.date(2026, 9, 1)):
            monthly_rows.append((m, reg, mc.get(m, 0)))

    def w(name, header, rr):
        with open(os.path.join(DATA, name), "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow(header)
            for r in rr:
                wr.writerow([(f"{x:.6g}" if isinstance(x, float) else x) for x in r])
    w("comparators.csv", ["region", "label", "count_on_D", "base_median_working_day", "rank_D_since_2016",
                          "peak_day_24mar_4apr", "peak_count", "rank_peak_since_2016", "R2_O", "R2_E", "R2_ratio",
                          "R3_share_placebo_ge", "R3_max_placebo", "R5_O", "R5_E", "R5_ratio", "pre12", "post12",
                          "F2_ratio", "F2_lo", "F2_hi", "nonworking_day_share", "mean_per_working_day", "mean_per_sunday"], rows)
    w("comparators_daily.csv", ["date", "region", "n"], daily_rows)
    w("comparators_monthly.csv", ["month", "region", "n"], monthly_rows)
    json.dump(out, open(os.path.join(DATA, "comparators_summary.json"), "w"), indent=1, ensure_ascii=False, default=str)
    for reg, o in out.items():
        print(reg, o["count_on_D"], o["peak_day_24mar_4apr"], o["peak_count"], "R2", round(o["R2"]["ratio"], 2),
              "share_ge", o["R3_share_ge"], "F2", round(o["F2"]["ratio"], 3), "nonwork", round(o["nonworking_share"] or 0, 3))


if __name__ == "__main__":
    main()
