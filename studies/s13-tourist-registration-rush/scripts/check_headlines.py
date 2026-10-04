#!/usr/bin/env python3
"""Assert every headline number of README.md (and paper.md, when present) against data/.

Recomputed from the published tables where they allow it:
- the run-up, the seasonal comparison and the spaced placebo p, from daily_kind.csv,
  holidays.csv and placebo.csv;
- the fall, the paired monthly comparison and the Generalitat's year, from daily_kind.csv.

The within-municipality contrast, the excess by municipality, the València cohort and
survivorship need row-level data that are not published. They are checked against summary.json
and rush_by_municipality.csv. Each expected string must appear in the documents; whitespace,
line breaks included, is collapsed before comparing.

The published numbers belong to the registry copy of 2026-10-04 (SHA-256 below). If data/ was
built from any other copy, for instance after a new fetch, mismatches are listed but the exit
code is 0. Otherwise exit 1 on any mismatch.
"""
import collections
import csv
import datetime as dt
import json
import math
import re
import statistics
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
D = R / "data"
sys.path.insert(0, str(R / "scripts"))
from s13lib import excess, ratio_of_means, days, nonworking  # noqa: E402

PAPER_URL = "https://easybyte.es/lab/studies/s13/paper/"
PUBLISHED = "2026-10-04"
# SHA-256 of the minimal copy the published numbers come from (data/sources.json)
PUBLISHED_SHA = "3343f6f6d5c71bc61f8b2d269210f5b7bc2e165e54ad28554256ea55b1b2e536"
D0 = dt.date(2025, 4, 2)
END = dt.date(2026, 8, 31)


def flat(s):
    return re.sub(r"\s+", " ", s)


def f(n):
    return f"{n:,}"


def r2(x):
    return f"{x:.2f}"


def rows(name):
    return list(csv.DictReader(open(D / name, encoding="utf-8")))


docs = {"README.md": flat((R / "README.md").read_text(encoding="utf-8"))}
if (R / "paper.md").exists():
    docs["paper.md"] = flat((R / "paper.md").read_text(encoding="utf-8"))
else:
    print(f"paper.md is not in the public package: the paper is at {PAPER_URL}")
bad = []


def need(label, text, where=("README.md", "paper.md")):
    print(f"{label}: {text}")
    for w in where:
        if w in docs and text not in docs[w]:
            bad.append(f"{w} does not contain «{text}» ({label})")


def close(label, a, b, tol=1e-6):
    if abs(a - b) > tol * max(1, abs(a)):
        bad.append(f"{label}: recomputed {a} != published {b}")


S = json.load(open(D / "summary.json", encoding="utf-8"))
PR, CO = S["post_review"], S["coordinator_review"]
sem = json.load(open(D / "date_semantics.json", encoding="utf-8"))
hol = {dt.date.fromisoformat(r["date"]) for r in rows("holidays.csv") if r["region"] in ("ES", "CV")}

# ---------------------------------------------------------------- series from daily_kind.csv
ser = collections.defaultdict(collections.Counter)
for r in rows("daily_kind.csv"):
    x, n = dt.date.fromisoformat(r["date"]), int(r["n"])
    ser["all"][x] += n
    ser[r["unit_kind"]][x] += n
need("dwellings in the main copy", f(S["rows_main"]))
tot = sum(n for x, n in ser["all"].items() if dt.date(2023, 1, 1) <= x <= END)
need("dwellings in the analysis window", f(tot), ("README.md",))
if tot != sem["E1_all"]["total"]:
    bad.append("E1 total disagrees with daily_kind.csv")

# ---------------------------------------------------------------- the run-up
rush = {r["series"]: r for r in rows("rush.csv")}
base_days = [x for x in days(dt.date(2025, 1, 7), dt.date(2025, 2, 28)) if not nonworking(x, hol)]
plac = collections.defaultdict(dict)
for r in rows("placebo.csv"):
    plac[r["series"]][r["window_end"]] = float(r["ratio"])
ends = sorted(plac["all"])
thin = [e for e in ends[::10] if not ("2025-06-01" <= e <= "2025-06-28")]
sw = PR["same_window_other_years"]
for name in ("all", "in_building", "whole_parcel"):
    s = ser[name]
    med = statistics.median([s.get(x, 0) for x in base_days])
    x = excess(s, D0, hol)
    close(f"{name} R2_O", x["O"], float(rush[name]["R2_O"]))
    close(f"{name} R2_E", x["E"], float(rush[name]["R2_E"]), 1e-4)
    ge = sum(v >= x["ratio"] for v in plac[name].values())
    row = f"| {f(s.get(D0, 0))} | {int(med)} | {f(x['O'])} | {f(round(x['E']))} | {r2(x['ratio'])} | {ge} of {len(plac[name])}"
    need(f"{name} run-up row (paper)", row, ("paper.md",))
    if name == "all":
        if max(s.get(y, 0) for y in days(dt.date(2016, 1, 1), END)) != s.get(D0, 0):
            bad.append("2 April 2025 is not the busiest day since 2016")
        need("14-day observed vs expected", f"{f(x['O'])} registrations against {f(round(x['E']))} expected")
        need("README all row", f"| all dwellings | {f(x['O'])} | {f(round(x['E']))} | {r2(x['ratio'])} | "
             f"{r2(sw['2023']['all']['ratio'])} / {r2(sw['2024']['all']['ratio'])} | {float(rush['all']['R5_ratio']):.2f} |", ("README.md",))
        need("seasonal ratios", f"{r2(sw['2023']['all']['ratio'])} and {r2(sw['2024']['all']['ratio'])} times their baseline in 2023 and 2024", ("README.md",))
        adj = x["O"] - x["E"] * (sw["2023"]["all"]["ratio"] + sw["2024"]["all"]["ratio"]) / 2
        close("seasonal excess", adj, PR["excess_seasonally_adjusted"])
        need("seasonally adjusted excess", f"about {int(round(adj, -1))}")
        va = [plac["all"][e] for e in thin]
        p_all = (1 + sum(v >= x["ratio"] for v in va)) / (1 + len(va))
        close("thinned p (all)", p_all, CO["all_thinned"]["p"])
        need("spaced placebo windows and p", f"{len(va)} spaced placebo windows")
        need("spaced placebo p", f"p = {p_all:.3f}")
        need("single day (README)", f"Of the 287 registrations in the region on 2 April, {int(rush['valencia_city']['R1_count_on_D'])} were in València city", ("README.md",))
        need("single day (paper)", f"with {s.get(D0, 0)} registrations, is the busiest day in the file since 2016", ("paper.md",))
        need("rank without the cities", f"{PR['rank_D_without_cities']}th busiest", ("paper.md",))

# where the excess is
bym = {r["ine_code"]: r for r in rows("rush_by_municipality.csv")}
ex_v, ex_t = float(bym["46250"]["excess"]), float(bym["03133"]["excess"])
tot_ex = float(rush["all"]["R2_O"]) - float(rush["all"]["R2_E"])
close("excess València", ex_v, CO["excess_vlc"])
need("share of the excess", f"55% of the excess (352 of 637)" if round(100 * (ex_v + ex_t) / tot_ex) == 55 and round(ex_v + ex_t) == 352 else "MISMATCH", ("README.md",))
need("València and Torrevieja excess", f"(+{round(ex_v)}) and Torrevieja (+{round(ex_t)})", ("README.md",))
need("València and Torrevieja excess (paper)", f"València city (+{round(ex_v)})", ("paper.md",))
G = CO["groups"]
for g, lab in (("valencia_city", "city of València"), ("torrevieja", "Torrevieja")):
    v = G[g]
    close(f"{g} O", v["R2_O"], float(bym["46250" if g == "valencia_city" else "03133"]["O"]))
    need(f"{g} README row", f"| {lab} | {f(v['R2_O'])} | {f(round(v['R2_E']))} | {r2(v['R2'])} | {r2(v['same_window']['2023'])} / {r2(v['same_window']['2024'])} | {r2(v['R5'])} |", ("README.md",))
need("Torrevieja before and after", f"{r2(G['torrevieja']['R2'])} times before the deadline and {r2(G['torrevieja']['R5'])} times after it", ("README.md",))
need("València before and after", f"{r2(G['valencia_city']['R2'])} times its expected count before the deadline and at {r2(G['valencia_city']['R5'])}", ("README.md",))
rest = G["all_excl_vlc_torre"]
need("rest of the region", f"{r2(rest['R2'])} times, or about {rest['R2_seasonally_adjusted']:.2f} times after the seasonal allowance (+{round(rest['excess_seasonally_adjusted'])})", ("README.md",))
# within municipalities
W = CO["within_municipality"]
need("within-municipality contrast", f"{r2(W['contrast'])}")
need("within-municipality n", f"{W['municipalities']} municipalities with both kinds ({W['flats_in_window']} flats and {W['houses_in_window']} houses in the window)", ("README.md",))
need("within-municipality p", f"{W['ge']} of {W['placebo_windows']} placebo windows were as large (p = {W['p']:.3f}", ("README.md",))
need("within-municipality p (paper)", f"| {r2(W['contrast'])} | {W['ge']} of {W['placebo_windows']} (p = {W['p']:.3f}) | {r2(W['ci_placebo_calibrated'][0])}–{r2(W['ci_placebo_calibrated'][1])}", ("paper.md",))
need("within-municipality interval", f"{r2(W['ci_placebo_calibrated'][0])}–{r2(W['ci_placebo_calibrated'][1])}")
r4 = S["R4"]["in_building"]
need("pooled contrast", f"{r2(r4['ratio_of_ratios'])}")
# the València deadline cohort
vc = CO["valencia_deadline_cohort"]
need("València cohort", f"{vc['buildings_street_and_number']} buildings (by street and number), {vc['in_buildings_with_5_or_more']} of them in buildings with five or more. {vc['without_cadastral_reference']} have no cadastral reference, against {100 * vc['share_without_reference_jan_feb_2025_all']:.1f}%", ("README.md",))

# ---------------------------------------------------------------- the fall, from daily_kind.csv
def mcount(name):
    c = collections.Counter()
    for x, n in ser[name].items():
        c[x.strftime("%Y-%m")] += n
    return c


def mrange(a, b):
    out, (y, m) = [], a
    while (y, m) <= b:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


pre12, post12 = mrange((2023, 9), (2024, 8)), mrange((2025, 9), (2026, 8))
F = {}
for name in ("all", "in_building", "whole_parcel"):
    c = mcount(name)
    F[name] = ratio_of_means([c.get(m, 0) for m in post12], [c.get(m, 0) for m in pre12])
    pre, post = sum(c.get(m, 0) for m in pre12), sum(c.get(m, 0) for m in post12)
    need(f"F2 table {name}", f"| {f(pre)} | {f(post)} | {r2(F[name]['ratio'])} ({r2(F[name]['lo'])}–{r2(F[name]['hi'])}) |")
ca, cf, ch = mcount("all"), mcount("in_building"), mcount("whole_parcel")
need("F2 all, abstract", f"{f(sum(ca.get(m, 0) for m in post12))} dwellings were registered, against {f(sum(ca.get(m, 0) for m in pre12))}", ("README.md",))


def paired(ref):
    dd = [math.log(cf[p] / ch[p]) - math.log(cf[q] / ch[q]) for p, q in zip(post12, ref)]
    mu, se = statistics.mean(dd), statistics.stdev(dd) / math.sqrt(len(dd))
    return math.exp(mu), math.exp(mu - 1.96 * se), math.exp(mu + 1.96 * se)


for lab, ref, key in (("against Sep 2022–Aug 2023", mrange((2022, 9), (2023, 8)), "2022-09..2023-08"),
                      ("against Sep 2023–Aug 2024", pre12, "pre12")):
    pr, lo, hi = paired(ref)
    close(f"paired {key}", pr, CO["paired_did"][key]["ratio"])
    need(f"paired DiD {lab}", f"{r2(pr)} ({r2(lo)}–{r2(hi)})" if key == "pre12" else f"{r2(pr)} (95% CI {r2(lo)}–{r2(hi)})")
v22 = PR["F2_ref_2022"]
need("ratio against 2022", f"{r2(v22['all']['ratio'])}, or {r2(v22['rebuilt']['ratio_all_corrected'])} corrected", ("README.md",))
ma25, ma24 = mrange((2025, 5), (2025, 8)), mrange((2024, 5), (2024, 8))
rf = sum(cf[m] for m in ma25) / sum(cf[m] for m in ma24)
rh = sum(ch[m] for m in ma25) / sum(ch[m] for m in ma24)
need("May-Aug 2025", f"{r2(rf)} and {r2(rh)} of a year earlier", ("README.md",))
need("May-Aug 2025 (paper)", f"flats {r2(rf)} ({f(sum(cf[m] for m in ma25))} against {f(sum(cf[m] for m in ma24))}), "
     f"houses {r2(rh)} ({f(sum(ch[m] for m in ma25))} against {f(sum(ch[m] for m in ma24))})", ("paper.md",))
tim = rows("monthly_timing.csv")
first = next((r["month"] for i_, r in enumerate(tim)
              if all(float(t["in_building_ratio"]) < float(t["whole_parcel_ratio"]) for t in tim[i_:])), None)
if first != "2025-10":
    bad.append(f"the flats-below-houses run does not start in October 2025 ({first})")
need("from October 2025", "From October 2025 flats ran below houses every month", ("README.md",))
# the Generalitat's year
y1 = sum(n for x, n in ser["all"].items() if dt.date(2023, 8, 8) <= x <= dt.date(2024, 8, 7))
y2 = sum(n for x, n in ser["all"].items() if dt.date(2024, 8, 8) <= x <= dt.date(2025, 8, 8))
close("GVA year 1", y1, CO["gva_year"]["2023-08-08..2024-08-07"]["surviving"])
need("GVA year", f"{f(y2)} dwellings dated in that year against {f(y1)} in the year before ({y2 / y1:.2f})", ("README.md",))
need("GVA quote", "casi el doble que en el periodo anterior")

# ---------------------------------------------------------------- date, survivorship, comparators
e3c = PR["E3c_late_2026_entries"]
if e3c["n"] != e3c["numbered_above_all_published"]:
    bad.append("E3c: not every late 2026 entry is numbered above the published numbers")
need("E3c", f"The {e3c['n']} dwellings dated in 2026", ("README.md",))
need("E3c (paper)", f"The {e3c['n']} of them dated in 2026", ("paper.md",))
need("non-working-day share", f"{100 * sem['E1_all']['share']:.1f}% of", ("paper.md",))
need("S4 survival", f"{100 * S['S4']['pre12_survival']:.1f}%")
need("S4 by building type", f"{100 * S['S4_by_situacion']['survival_AB']:.1f}%")
need("S4 chalets", f"{100 * S['S4_by_situacion']['survival_C']:.1f}%")
need("S4 corrected fall", f"{S['S4']['ratio_all']:.2f} once", ("README.md",))
comp = {r["region"]: r for r in rows("comparators.csv")}
a = comp["andalucia"]
need("Andalucía peak", f"{int(a['peak_count'])} registrations on 31 March 2025", ("README.md",))
need("Andalucía run-up", f"{f(int(a['R2_O']))} in the last two weeks against {f(round(float(a['R2_E'])))} expected", ("README.md",))
need("Andalucía run-up (paper)", f"{f(int(a['R2_O']))} against {f(round(float(a['R2_E'])))} expected", ("paper.md",))
ad = {r["date"]: int(r["n"]) for r in rows("comparators_daily.csv") if r["region"] == "andalucia"}
need("Andalucía after the deadline", f"{ad['2025-04-03'] + ad['2025-04-04']} in Andalucía on 3–4 April", ("README.md",))

if bad:
    print("\nFAIL:\n  " + "\n  ".join(bad))
    main_sha = S.get("inputs_sha256", {}).get(f"data/raw/registries/gva_min_{S.get('snapshot_main')}.csv")
    if main_sha != PUBLISHED_SHA:
        print(f"\ndata/ was built from another copy of the registry ({S.get('snapshot_main')}, SHA-256 "
              f"{str(main_sha)[:12]}…), not the published copy of {PUBLISHED}: differences are expected. Not failing.")
        sys.exit(0)
    sys.exit(1)
print("\nOK: every headline number matches data/ and appears in " + " and ".join(docs))
