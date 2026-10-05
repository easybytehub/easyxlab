#!/usr/bin/env python3
"""S22: decomposition of the 2024 record, sensitivity, links to the reception system, Strategy indicator.

Reads only data/*.csv written by build.py. Writes:
  data/decomposition.csv   2022->2024 (headline) and 2020->2022: change by segment, centres x per-centre split
  data/sensitivity.csv     the headline under each definitional choice
  data/long_series.csv     2012-2024: occupied per accommodation centre, growth of each
  data/reception_link.csv  INE immigrant-only component against reception places, applications, arrivals
  data/strategy_indicator.csv  the Strategy's «tasa de cobertura» with and without immigrant-only places
  data/regional_link.csv   2022->2024 by region, and the slope of the change in occupied on immigrant-only centres
  data/summary.json        headline numbers used in README.md and paper.md
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import re

from s22lib import DATA



# Dates, editions, quotations and prior-work figures that the abstracts quote (paper §2-§3,
# PROTOCOL.md), so that every number the text shows has a key in summary.json.
TEXT = {
    "editions_compared": "2022–2024", "edition_first": 2022, "edition_last": 2024, "edition_base_variant": 2020,
    "edition_adults_only_from": 2022, "editions_imm_in_methodology": "2020 and 2022",
    "sapi_years": "From 2020 to 2022",
    "revision_year": 2025, "revision_date_quoted": "17/10/2025",           # INE results page
    "first_published_date": "26 September 2025", "revision_date": "17 October 2025",
    "strategy_period": "2023–2030", "strategy_goal_year": 2030, "epsh_refugee_share": 0.004,
    "epsh_refugee_share_quoted": "0,4%",                                    # INE, EPSH 2022 release
    "progress_report_quoted": "34.145",                                     # Ministry, progress report 2024
    "mww_year": 2026, "mww_migrant_share": "59–62%", "mww_rise": 0.43,      # Meyer, Wyse and Williams (2026)
    "next_edition": 2026, "protocol_registered": "4 October 2026", "protocol_clarifications_section": 12,
    "next_edition_expected": "September 2027",
}

def region_places(html, label="Navarra, Comunidad Foral de"):
    """Mean daily places of a region in the regional table embedded in an INE press release:
    a JSON block with the row labels, then 'ids', 'col', 'row' and 'data' (three values per row)."""
    i = html.index('"table_1_' + re.sub(r"[^A-Za-z]+", "_", label.replace("í", "i")).strip("_") + '"')
    k = html.rfind('"ids"', 0, i)
    end = html.rfind(']', 0, k)
    start = html.rfind('[', 0, end)
    labels = json.loads(html[start:end + 1])
    d = html.index('"data"', i)
    data = json.loads(html[html.index('[', d):html.index(']', d) + 1])
    rows = labels[len(labels) - len(data) // 3:]  # the labels start with the three column headers
    assert len(data) == 3 * len(rows) and rows[0].upper() == "TOTAL", (len(data), rows[:2])
    return float(re.sub(r"<[^>]+>", "", data[3 * rows.index(label)]).replace(".", "").replace(",", "."))

def region_table(html):
    """Every row of the regional table embedded in an INE press release, as label -> its three cells
    (the same JSON block that region_places reads); used to count the regions a revision changed."""
    k = html.index('"ids"')
    end = html.rfind(']', 0, k)
    start = html.rfind('[', 0, end)
    labels = json.loads(html[start:end + 1])
    d = html.index('"data"', k)
    data = json.loads(html[html.index('[', d):html.index(']', d) + 1])
    rows = labels[len(labels) - len(data) // 3:]
    assert len(data) == 3 * len(rows) and rows[0].upper() == "TOTAL", (len(data), rows[:2])
    return {r: [re.sub(r"<[^>]+>", "", str(x)) for x in data[3 * j:3 * j + 3]] for j, r in enumerate(rows)}


def load(name):
    with open(DATA / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields=None):
    fields = fields or list(rows[0].keys())
    with open(DATA / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else (round(r[k], 4) if isinstance(r[k], float) else r[k]))
                        for k in fields})
    print(f"wrote data/{name} ({len(rows)} rows)")


F = lambda x: float(x) if x not in ("", None) else None

SPEC = {(int(r["edition"]), r["segment"]): {k: F(v) for k, v in r.items() if k not in ("segment", "occupied_scope")}
        for r in load("specialisation.csv")}
NAT = {int(r["edition"]): {k: F(v) if k not in ("occupied_scope", "response_rate_source") else v for k, v in r.items()}
       for r in load("national_series.csv")}
EPSH_2022 = 28552  # INE, Encuesta sobre las personas sin hogar 2022: «Un total de 28.552 personas sin hogar»


def shapley(c0, c1, o0, o1):
    """Split ΔO = Δ(C·o) into a centres term and a per-centre term (symmetric, exact).

    For two factors this midpoint split is the Shapley value: the mean of the two orderings."""
    return (c1 - c0) * (o0 + o1) / 2, (o1 - o0) * (c0 + c1) / 2


def orderings(c0, c1, o0, o1):
    """The two one-at-a-time splits. Returns (centres term, per-centre term) for
    'centres first' (ΔC·o0, Δo·C1) and 'per centre first' (ΔC·o1, Δo·C0)."""
    return ((c1 - c0) * o0, (o1 - o0) * c1), ((c1 - c0) * o1, (o1 - o0) * c0)


def decompose(e0, e1, value="occupied_mean", count="accommodation_centres", core=("GBV", "OTH")):
    """Return dict with the change by segment and the centres/per-centre split.

    IMM = centres INE classes as «Especializado en inmigrantes»; the rest ('non-IMM') = core."""
    t0, t1 = SPEC[(e0, "ALL")][value], SPEC[(e1, "ALL")][value]
    d = {"from": e0, "to": e1, "value": value, "count": count, "total_0": t0, "total_1": t1,
         "total_change": t1 - t0, "total_growth_pct": 100 * (t1 / t0 - 1)}
    for seg in ("IMM", "GBV", "OTH"):
        v0, v1 = SPEC[(e0, seg)][value], SPEC[(e1, seg)][value]
        c0, c1 = SPEC[(e0, seg)][count], SPEC[(e1, seg)][count]
        a, b = shapley(c0, c1, v0 / c0, v1 / c1)
        (cf_a, cf_b), (pf_a, pf_b) = orderings(c0, c1, v0 / c0, v1 / c1)
        d.update({f"{seg}_centres_term_min": min(cf_a, pf_a), f"{seg}_centres_term_max": max(cf_a, pf_a),
                  f"{seg}_per_centre_term_min": min(cf_b, pf_b), f"{seg}_per_centre_term_max": max(cf_b, pf_b)})
        d.update({f"{seg}_0": v0, f"{seg}_1": v1, f"{seg}_change": v1 - v0,
                  f"{seg}_share_of_change_pct": 100 * (v1 - v0) / (t1 - t0),
                  f"{seg}_centres_0": c0, f"{seg}_centres_1": c1,
                  f"{seg}_centres_term": a, f"{seg}_per_centre_term": b,
                  f"{seg}_per_centre_0": v0 / c0, f"{seg}_per_centre_1": v1 / c1})
    n0 = sum(SPEC[(e0, s)][value] for s in core)
    n1 = sum(SPEC[(e1, s)][value] for s in core)
    nc0 = sum(SPEC[(e0, s)][count] for s in core)
    nc1 = sum(SPEC[(e1, s)][count] for s in core)
    a, b = shapley(nc0, nc1, n0 / nc0, n1 / nc1)
    (cf_a, cf_b), (pf_a, pf_b) = orderings(nc0, nc1, n0 / nc0, n1 / nc1)
    d.update({"core_centres_term_min": min(cf_a, pf_a), "core_centres_term_max": max(cf_a, pf_a),
              "core_per_centre_term_min": min(cf_b, pf_b), "core_per_centre_term_max": max(cf_b, pf_b),
              # the core split segment by segment (GBV and OTH separately, then summed): a mix check
              "core_centres_term_by_segment": sum(d[f"{x}_centres_term"] for x in core),
              "core_per_centre_term_by_segment": sum(d[f"{x}_per_centre_term"] for x in core)})
    d.update({"core": "+".join(core), "core_0": n0, "core_1": n1, "core_growth_pct": 100 * (n1 / n0 - 1),
              "core_centres_growth_pct": 100 * (nc1 / nc0 - 1),
              "core_per_centre_growth_pct": 100 * ((n1 / nc1) / (n0 / nc0) - 1),
              "core_centres_term": a, "core_per_centre_term": b,
              "all_centres_growth_pct": 100 * (SPEC[(e1, "ALL")]["centres"] / SPEC[(e0, "ALL")]["centres"] - 1),
              "all_accommodation_centres_growth_pct": 100 * (SPEC[(e1, "ALL")]["accommodation_centres"]
                                                             / SPEC[(e0, "ALL")]["accommodation_centres"] - 1)})
    # four-way split of the total change: IMM centres, IMM per centre, core centres, core per centre
    d["split_IMM_centres"] = d["IMM_centres_term"]
    d["split_IMM_per_centre"] = d["IMM_per_centre_term"]
    d["split_core_centres"] = a
    d["split_core_per_centre"] = b
    # the core is GBV+OTH by default; when core = OTH only, GBV is left as its own residual
    d["split_residual"] = d["total_change"] - (d["split_IMM_centres"] + d["split_IMM_per_centre"] + a + b)
    return d


def main():
    summary = {}
    # ---------------------------------------------------------------- headline decomposition
    head = decompose(2022, 2024)
    prev = decompose(2020, 2022)
    fields = list(head.keys())
    write("decomposition.csv", [head, prev], fields)
    summary["headline"] = head
    summary["previous"] = prev

    # ---------------------------------------------------------------- sensitivity
    sens = []

    def add(label, d, note=""):
        sens.append({"variant": label, "from": d["from"], "to": d["to"], "value": d["value"], "count": d["count"],
                     "core": d["core"], "total_growth_pct": d["total_growth_pct"],
                     "IMM_share_of_change_pct": d["IMM_share_of_change_pct"],
                     "core_growth_pct": d["core_growth_pct"], "core_centres_growth_pct": d["core_centres_growth_pct"],
                     "core_per_centre_growth_pct": d["core_per_centre_growth_pct"],
                     "all_centres_growth_pct": d["all_centres_growth_pct"], "note": note})

    add("S0 headline: occupied, accommodation centres, core = GBV+OTH", head)
    add("S2 places instead of occupied places", decompose(2022, 2024, value="places_mean"))
    add("S3 all centres instead of centres offering accommodation", decompose(2022, 2024, count="centres"))
    add("S4 core = OTH only (gender-violence shelters set aside)", decompose(2022, 2024, core=("OTH",)))
    add("S4b core = OTH only, places", decompose(2022, 2024, value="places_mean", core=("OTH",)))
    add("S4c core = OTH only, all centres as denominator", decompose(2022, 2024, count="centres", core=("OTH",)))
    add("S5 base 2020 (occupied of all ages in 2020; adults only from 2022)", decompose(2020, 2024),
        "scope break: INE counts occupied places of adults only from 2022")
    add("S9 previous edition 2020->2022", prev, "same scope break")
    # S1: the first-published vintage (26-Sep-2025). Only the total and the immigrant-only figures differ.
    rev = {r["indicator"]: r for r in load("revision_2024.csv")}
    o1 = float(rev["occupied_mean"]["original_2025_09_26"])
    i1 = float(rev["imm_occupied_mean"]["original_2025_09_26"])
    o0, i0 = SPEC[(2022, "ALL")]["occupied_mean"], SPEC[(2022, "IMM")]["occupied_mean"]
    sens.append({"variant": "S1 first-published 2024 figures (26-Sep-2025, before INE's revision)", "from": 2022,
                 "to": 2024, "value": "occupied_mean", "count": "", "core": "GBV+OTH",
                 "total_growth_pct": 100 * (o1 / o0 - 1), "IMM_share_of_change_pct": 100 * (i1 - i0) / (o1 - o0),
                 "core_growth_pct": 100 * ((o1 - i1) / (o0 - i0) - 1), "core_centres_growth_pct": None,
                 "core_per_centre_growth_pct": None,
                 "all_centres_growth_pct": 100 * (float(rev["centres"]["original_2025_09_26"]) / SPEC[(2022, "ALL")]["centres"] - 1),
                 "note": "segment centre counts of the first vintage were not published in the release"})
    # S6: reference dates (national totals only; INE does not split them by specialisation)
    rd = {(int(r["edition"]), r["date"], r["type"]): r for r in load("reference_dates.csv")}
    j22, j24 = float(rd[(2022, "15 de junio", "total")]["occupied"]), float(rd[(2024, "14 de junio", "total")]["occupied"])
    d22, d24 = float(rd[(2022, "15 de diciembre", "total")]["occupied"]), float(rd[(2024, "16 de diciembre", "total")]["occupied"])
    for lab, a, b in (("S6a June only (15-Jun-2022 -> 14-Jun-2024), national total", j22, j24),
                      ("S6b December only (15-Dec-2022 -> 16-Dec-2024), national total", d22, d24)):
        sens.append({"variant": lab, "from": 2022, "to": 2024, "value": "occupied (snapshot)", "count": "", "core": "",
                     "total_growth_pct": 100 * (b / a - 1), "IMM_share_of_change_pct": None, "core_growth_pct": None,
                     "core_centres_growth_pct": None, "core_per_centre_growth_pct": None,
                     "all_centres_growth_pct": None, "note": "INE does not split the snapshots by specialisation"})
    # S7: without the Canary Islands (regional totals; no split by specialisation within regions)
    reg = {(int(r["edition"]), r["region"]): r for r in load("regions.csv")}
    c22 = float(reg[(2022, "Canary Islands")]["occupied_mean"]); c24 = float(reg[(2024, "Canary Islands")]["occupied_mean"])
    t22, t24 = SPEC[(2022, "ALL")]["occupied_mean"], SPEC[(2024, "ALL")]["occupied_mean"]
    sens.append({"variant": "S7 Spain without the Canary Islands, national total", "from": 2022, "to": 2024,
                 "value": "occupied_mean", "count": "", "core": "", "total_growth_pct": 100 * ((t24 - c24) / (t22 - c22) - 1),
                 "IMM_share_of_change_pct": None, "core_growth_pct": None, "core_centres_growth_pct": None,
                 "core_per_centre_growth_pct": None, "all_centres_growth_pct": None,
                 "note": f"Canary Islands {c22:.0f} -> {c24:.0f}, {100 * (c24 - c22) / (t24 - t22):.1f}% of the national change"})
    write("sensitivity.csv", sens)
    summary["sensitivity"] = sens
    summary["canary"] = {"occ_2022": c22, "occ_2024": c24, "share_of_change_pct": 100 * (c24 - c22) / (t24 - t22)}
    rdt = {(int(r["edition"]), r["region"], r["date"], r["indicator"]): float(r["value"])
           for r in load("region_dates.csv") if r["value"] != ""}
    cj, cd = rdt[(2024, "Canary Islands", "14 de junio", "occupied")], rdt[(2024, "Canary Islands", "16 de diciembre", "occupied")]
    nj, nd = rdt[(2024, "Spain", "14 de junio", "occupied")], rdt[(2024, "Spain", "16 de diciembre", "occupied")]
    summary["canary"].update({"jun_2024": cj, "dec_2024": cd, "national_jun_2024": nj, "national_dec_2024": nd,
                              "share_of_jun_dec_gap_pct": 100 * (cd - cj) / (nd - nj),
                              "jun_2022": rdt[(2022, "Canary Islands", "15 de junio", "occupied")],
                              "dec_2022": rdt[(2022, "Canary Islands", "15 de diciembre", "occupied")]})
    # The revision of 17-Oct-2025 as a worked case: a known frame change (one more immigrant-specialised
    # centre with accommodation, +387 occupied places) and where the midpoint split books it.
    # First vintage: IMM occupied 17,786 (release), IMM centres with accommodation 345 (inferred: the
    # revision added one centre with accommodation, 1,119 -> 1,120, and one IMM centre, 26.1% -> 26.2%).
    i0c, i0o = SPEC[(2022, "IMM")]["accommodation_centres"], SPEC[(2022, "IMM")]["occupied_mean"]
    i1c, i1o = SPEC[(2024, "IMM")]["accommodation_centres"], SPEC[(2024, "IMM")]["occupied_mean"]
    f_a, f_b = shapley(i0c, i1c - 1, i0o / i0c, (i1o - 387) / (i1c - 1))
    r_a, r_b = shapley(i0c, i1c, i0o / i0c, i1o / i1c)
    summary["revision_split"] = {"first_centres_term": f_a, "first_per_centre_term": f_b,
                                 "revised_centres_term": r_a, "revised_per_centre_term": r_b,
                                 "added_to_centres_term": r_a - f_a, "added_to_per_centre_term": r_b - f_b,
                                 "share_booked_per_centre_pct": 100 * (r_b - f_b) / 387}
    summary["snapshots"] = {"jun22": j22, "jun24": j24, "dec22": d22, "dec24": d24}

    # ---------------------------------------------------------------- long series
    longs = []
    prevr = None
    for ed in sorted(NAT):
        n = NAT[ed]
        r = {"edition": ed, "centres": n["centres"], "accommodation_centres": n["accommodation_centres"],
             "occupied_mean": n["occupied_mean"], "places_mean": n["places_mean"],
             "occupied_per_accommodation_centre": n["occupied_mean"] / n["accommodation_centres"],
             "occupied_scope": n["occupied_scope"]}
        if prevr:
            r["occupied_growth_pct"] = 100 * (r["occupied_mean"] / prevr["occupied_mean"] - 1)
            r["accommodation_centres_growth_pct"] = 100 * (r["accommodation_centres"] / prevr["accommodation_centres"] - 1)
            r["centres_growth_pct"] = 100 * (r["centres"] / prevr["centres"] - 1)
        if (ed, "IMM") in SPEC:
            core_o = sum(SPEC[(ed, s)]["occupied_mean"] for s in ("GBV", "OTH"))
            core_c = sum(SPEC[(ed, s)]["accommodation_centres"] for s in ("GBV", "OTH"))
            r["core_occupied_per_accommodation_centre"] = core_o / core_c
            r["imm_occupied_per_accommodation_centre"] = SPEC[(ed, "IMM")]["occupied_mean"] / SPEC[(ed, "IMM")]["accommodation_centres"]
            r["imm_share_of_occupied_pct"] = 100 * SPEC[(ed, "IMM")]["occupied_mean"] / SPEC[(ed, "ALL")]["occupied_mean"]
        longs.append(r)
        prevr = r
    write("long_series.csv", longs, ["edition", "centres", "accommodation_centres", "places_mean", "occupied_mean",
                                     "occupied_scope", "occupied_per_accommodation_centre",
                                     "core_occupied_per_accommodation_centre", "imm_occupied_per_accommodation_centre",
                                     "imm_share_of_occupied_pct", "occupied_growth_pct",
                                     "accommodation_centres_growth_pct", "centres_growth_pct"])
    # elasticity of occupied to accommodation centres across the 2012-2022 intervals (log growth, OLS through origin)
    xs = [math.log(longs[i]["accommodation_centres"] / longs[i - 1]["accommodation_centres"]) for i in range(1, len(longs) - 1)]
    ys = [math.log(longs[i]["occupied_mean"] / longs[i - 1]["occupied_mean"]) for i in range(1, len(longs) - 1)]
    beta = sum(x * y for x, y in zip(xs, ys)) / sum(x * x for x in xs)
    ratios = [y / x for x, y in zip(xs, ys)]
    per = [r["occupied_per_accommodation_centre"] for r in longs if r["edition"] <= 2022]
    summary["long"] = {"per_centre_2012_2022_min": min(per), "per_centre_2012_2022_max": max(per),
                       "per_centre_2024": longs[-1]["occupied_per_accommodation_centre"],
                       "elasticity_2012_2022": beta, "interval_ratios": ratios, "n_intervals": len(xs), "rows": longs}

    # ---------------------------------------------------------------- reception system link
    ex = {int(r["year"]): {k: F(v) for k, v in r.items()} for r in load("explanatory.csv")}
    sit = {int(r["edition"]): r for r in load("situations.csv")}
    link = []
    for ed in (2014, 2016, 2018, 2020, 2022, 2024):
        e = ex.get(ed, {})
        row = {"edition": ed, "centres_oriented_immigration_ip": int(sit[ed]["centres_oriented_immigration_ip"]),
               "imm_only_centres": SPEC.get((ed, "IMM"), {}).get("centres"),
               "imm_places_mean": SPEC.get((ed, "IMM"), {}).get("places_mean"),
               "imm_occupied_mean": SPEC.get((ed, "IMM"), {}).get("occupied_mean"),
               "sapi_places_yearend": e.get("sapi_places"), "humanitarian_places_yearend": e.get("humanitarian_places"),
               "reception_places_yearend": e.get("reception_places_total"),
               "asylum_applicants_first": e.get("asylum_applicants_first"), "arrivals_land_sea": e.get("arrivals_land_sea")}
        if row["imm_places_mean"] and row["reception_places_yearend"]:
            row["imm_places_as_pct_of_reception_places"] = 100 * row["imm_places_mean"] / row["reception_places_yearend"]
        link.append(row)
    write("reception_link.csv", link, list(link[-1].keys()))
    g = lambda a, b: 100 * (b / a - 1)
    L = {r["edition"]: r for r in link}
    summary["reception"] = {
        "imm_places_growth_22_24": g(L[2022]["imm_places_mean"], L[2024]["imm_places_mean"]),
        "imm_occupied_growth_22_24": g(L[2022]["imm_occupied_mean"], L[2024]["imm_occupied_mean"]),
        "reception_growth_22_24": g(L[2022]["reception_places_yearend"], L[2024]["reception_places_yearend"]),
        "sapi_growth_22_24": g(L[2022]["sapi_places_yearend"], L[2024]["sapi_places_yearend"]),
        "humanitarian_growth_22_24": g(L[2022]["humanitarian_places_yearend"], L[2024]["humanitarian_places_yearend"]),
        "asylum_first_growth_22_24": g(L[2022]["asylum_applicants_first"], L[2024]["asylum_applicants_first"]),
        "arrivals_growth_22_24": g(L[2022]["arrivals_land_sea"], L[2024]["arrivals_land_sea"]),
        "imm_places_growth_20_22": g(L[2020]["imm_places_mean"], L[2022]["imm_places_mean"]),
        "reception_growth_20_22": g(L[2020]["reception_places_yearend"], L[2022]["reception_places_yearend"]),
        "sapi_growth_20_22": g(L[2020]["sapi_places_yearend"], L[2022]["sapi_places_yearend"]),
        "humanitarian_growth_20_22": g(L[2020]["humanitarian_places_yearend"], L[2022]["humanitarian_places_yearend"]),
        "asylum_first_growth_20_22": g(L[2020]["asylum_applicants_first"], L[2022]["asylum_applicants_first"]),
        "arrivals_growth_20_22": g(L[2020]["arrivals_land_sea"], L[2022]["arrivals_land_sea"]),
        "coverage_pct": {ed: L[ed].get("imm_places_as_pct_of_reception_places") for ed in (2020, 2022, 2024)},
        "canary_arrivals_2024": ex[2024]["arrivals_canary_sea"], "canary_arrivals_2025": ex[2025]["arrivals_canary_sea"],
        "arrivals_2025_vs_2024_pct": g(ex[2024]["arrivals_land_sea"], ex[2025]["arrivals_land_sea"]),
        "sapi_jun2025": ex[2025]["sapi_places"], "humanitarian_jun2025": ex[2025]["humanitarian_places"],
        "rows": link}

    # ---------------------------------------------------------------- Strategy indicator
    rdd = {(int(r["edition"]), r["type"], r["date"]): float(r["places"]) for r in load("reference_dates.csv")}
    strat = []
    for ed in (2020, 2022, 2024):
        dec = [v for (e, t, d), v in rdd.items() if e == ed and t == "total" and "diciembre" in d][0]
        allp = SPEC[(ed, "ALL")]["places_mean"]
        imm = SPEC[(ed, "IMM")]["places_mean"]
        strat.append({"edition": ed, "places_december": dec, "places_mean": allp, "imm_places_mean": imm,
                      "coverage_december_pct": 100 * dec / EPSH_2022, "coverage_mean_pct": 100 * allp / EPSH_2022,
                      "coverage_mean_without_imm_pct": 100 * (allp - imm) / EPSH_2022})
    write("strategy_indicator.csv", strat)
    summary["strategy"] = {"rows": strat, "baseline_pct": 70.7, "target_2028_pct": 85, "target_2030_pct": 90,
                           "epsh_2022_persons": EPSH_2022}

    # ---------------------------------------------------------------- regions (exploratory)
    regs = sorted({r["region"] for r in load("regions.csv")} - {"Spain"})
    rl = []
    for rg in regs:
        a, b = reg[(2022, rg)], reg[(2024, rg)]
        rl.append({"region": rg, "occupied_2022": int(a["occupied_mean"]), "occupied_2024": int(b["occupied_mean"]),
                   "occupied_change": int(b["occupied_mean"]) - int(a["occupied_mean"]),
                   "centres_2022": int(a["centres"]), "centres_2024": int(b["centres"]),
                   "imm_centres_2022": int(a["centres_imm"]), "imm_centres_2024": int(b["centres_imm"]),
                   "imm_centres_change": int(b["centres_imm"]) - int(a["centres_imm"]),
                   "other_centres_change": (int(b["centres"]) - int(b["centres_imm"])) - (int(a["centres"]) - int(a["centres_imm"]))})
    write("regional_link.csv", rl)

    def ols(x, y):
        mx, my = sum(x) / len(x), sum(y) / len(y)
        sxx = sum((a - mx) ** 2 for a in x); sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
        syy = sum((b - my) ** 2 for b in y)
        return sxy / sxx, sxy / math.sqrt(sxx * syy)

    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r

    y = [r["occupied_change"] for r in rl]
    xi = [r["imm_centres_change"] for r in rl]
    xo = [r["other_centres_change"] for r in rl]
    bi, ri = ols(xi, y); bo, ro = ols(xo, y)
    _, rhoi = ols(rank(xi), rank(y)); _, rhoo = ols(rank(xo), rank(y))
    summary["regions"] = {"n": len(rl), "slope_imm": bi, "r_imm": ri, "spearman_imm": rhoi,
                          "slope_other": bo, "r_other": ro, "spearman_other": rhoo}
    # ---------------------------------------------------------------- predictions for ECAPSH 2026 (PROTOCOL.md §5)
    core = ("GBV", "OTH")
    co = sum(SPEC[(2024, s)]["occupied_mean"] for s in core)
    cc = sum(SPEC[(2024, s)]["accommodation_centres"] for s in core)
    cp = sum(SPEC[(2024, s)]["places_mean"] for s in core)
    co22 = sum(SPEC[(2022, s)]["occupied_mean"] for s in core)
    cc22 = sum(SPEC[(2022, s)]["accommodation_centres"] for s in core)
    o24 = co / cc
    oth_o, oth_c, oth_p = (SPEC[(2024, "OTH")][k] for k in ("occupied_mean", "accommodation_centres", "places_mean"))
    spec = {
        "registered_in": "PROTOCOL.md §5, before INE publishes ECAPSH 2026 (expected September 2027)",
        "baseline_2024": {"core_segments": list(core), "core_occupied_mean": co, "core_accommodation_centres": cc,
                          "core_places_mean": cp, "core_occupied_per_centre": o24,
                          "core_occupancy_pct": 100 * co / cp,
                          "imm_occupied_mean": SPEC[(2024, "IMM")]["occupied_mean"],
                          "imm_places_mean": SPEC[(2024, "IMM")]["places_mean"],
                          "total_occupied_mean": SPEC[(2024, "ALL")]["occupied_mean"],
                          "reception_places_dec2024": ex[2024]["reception_places_total"]},
        "in_sample_2022_2024": {"core_per_centre_log_change": math.log(o24 / (co22 / cc22)),
                                "core_occupancy_pp_change": 100 * co / cp - 100 * co22 / sum(SPEC[(2022, s)]["places_mean"] for s in core),
                                "abs_imm_change": SPEC[(2024, "IMM")]["occupied_mean"] - SPEC[(2022, "IMM")]["occupied_mean"],
                                "abs_core_change": co - co22},
        "P1_core_per_centre_log_change": {"A": [-0.10, 0.10], "B": [">", 0.10],
                                          "A_bounds_occupied_per_centre": [round(o24 * math.exp(-0.10), 2), round(o24 * math.exp(0.10), 2)]},
        "P2_core_occupancy_pp_change": {"A": [-4.0, 4.0], "B": [">", 4.0],
                                        "A_bounds_pct": [round(100 * co / cp - 4, 1), round(100 * co / cp + 4, 1)]},
        "P3_driver": {"A": "|ΔIMM occupied| > |Δcore occupied|", "B": "|Δcore occupied| >= |ΔIMM occupied|"},
        "P4_imm_vs_reception": {"A": "sign(ΔIMM occupied) = sign(Δ reception places, Dec-2024 -> Dec-2026), scored only if |Δ reception| >= 10%",
                                "B": "no prediction"},
        "deviation_D1_2026_10_04": {
            "note": "PROTOCOL.md §12, D1. Clarifies scoring; the registered intervals above are unchanged.",
            "oth_baseline_2024": {"occupied_mean": oth_o, "accommodation_centres": oth_c, "places_mean": oth_p,
                                  "occupied_per_centre": oth_o / oth_c, "occupancy_pct": 100 * oth_o / oth_p},
            "P1_oth_only_bounds_occupied_per_centre": [round(oth_o / oth_c * math.exp(-0.10), 2),
                                                       round(oth_o / oth_c * math.exp(0.10), 2)],
            "q1": "ln(o_core,2026 / o_core,2024), o = occupied per centre offering accommodation, core = GBV+OTH",
            "q1_oth": "the same with core = OTH only",
            "q2": "core occupancy 2026 minus 2024, percentage points (occupied adults / all places)",
            "per_centre_pressure": "q1 > +0.10 AND q1_oth > +0.10 AND q2 > +4",
            "no_per_centre_pressure": "|q1| <= 0.10 AND |q1_oth| <= 0.10 AND |q2| <= 4",
            "reading_B_falsified_iff": "no_per_centre_pressure",
            "reading_A_falsified_iff": "per_centre_pressure OR (P4 scored AND P4 sign mismatch, on occupied and on places)",
            "verdicts": {
                "B supported (per-centre pressure in the core)": "per_centre_pressure (P4 reported alongside)",
                "A supported": "no_per_centre_pressure AND P4 scored AND P4 = A on both occupied and places",
                "no per-centre pressure; A and growth through new centres not separable": "no_per_centre_pressure AND (P4 not scored OR P4 mixed)",
                "A rejected on P4; no per-centre pressure": "no_per_centre_pressure AND P4 = mismatch on both",
                "undetermined": "any other combination (stated, with the values)"},
            "P3": "reported, not used in the verdict",
            "P4_places_variant": "sign(ΔIMM places) against the same reception change; reported with P4",
            "classification_break": "if INE changes the specialisation item, the ETHOS-based scope, the adults-only rule or the reference dates, all values are reported and the verdict is 'not scored (classification break)'",
            "reception_places_dec2024": ex[2024]["reception_places_total"]},
    }
    with open(DATA / "predictions_2026_spec.json", "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print("wrote data/predictions_2026_spec.json")
    summary["predictions"] = spec

    # keys the abstracts quote: the INE chart, the per-centre changes, the 2025 revision
    chart = {int(r["edition"]): float(r["occupied_chart"]) for r in csv.DictReader(open(DATA / "ine_chart_2006_2024.csv", encoding="utf-8"))}
    eds = sorted(chart)
    rises = {b: chart[b] / chart[a] - 1 for a, b in zip(eds, eds[1:])}
    summary["ine_chart"] = {"first_edition": eds[0], "last_edition": eds[-1], "occupied_last": chart[eds[-1]],
                            "max_occupied_before_last": max(chart[e] for e in eds[:-1]),
                            "rise_last": rises[eds[-1]], "max_rise_before_last": max(v for e, v in rises.items() if e != eds[-1])}
    hh = summary["headline"]
    summary["per_centre_change_pct"] = {
        g: 100 * ((hh[f"{g}_1"] / hh[f"{g}_centres_1"]) / (hh[f"{g}_0"] / hh[f"{g}_centres_0"]) - 1) for g in ("GBV", "OTH")}
    rv = {r["indicator"]: r for r in csv.DictReader(open(DATA / "revision_2024.csv", encoding="utf-8"))}
    raw = DATA / "raw"
    orig = gzip.decompress((raw / "wayback" / "ECAPSH2024_20250926132524.htm").read_bytes()).decode("utf-8", "replace")
    revd = (raw / "ine_press" / "ECAPSH2024.htm").read_text(encoding="utf-8")
    summary["revision"] = {"first_published_occupied": float(rv["occupied_mean"]["original_2025_09_26"]),
                           "added_occupied": float(rv["occupied_mean"]["revised_2025_10_17"]) - float(rv["occupied_mean"]["original_2025_09_26"]),
                           "added_booked_per_centre": summary["revision_split"]["added_to_per_centre_term"],
                           "navarre_places_first": region_places(orig), "navarre_places_revised": region_places(revd)}
    t_orig, t_revd = region_table(orig), region_table(revd)
    assert list(t_orig) == list(t_revd), "the two vintages list different regions"
    changed = [r for r in t_orig if r.upper() != "TOTAL" and t_orig[r] != t_revd[r]]
    summary["revision"].update({"regions_in_table": sum(1 for r in t_orig if r.upper() != "TOTAL"),
                                "regions_changed": len(changed), "regions_changed_labels": changed})
    # all centres (with or without accommodation), by specialisation: the homogeneous base for
    # «most of the new centres» against the change in all centres (long.rows.*.centres)
    summary["centres_all"] = {f"{seg}_{i}": SPEC[(ed, seg)]["centres"]
                              for seg in ("IMM", "ALL") for i, ed in ((0, 2022), (1, 2024))}
    summary["text"] = dict(TEXT)

    with open(DATA / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=float)
    print("wrote data/summary.json")
    h = head
    print(f"2022->2024: total {h['total_0']:.0f} -> {h['total_1']:.0f} ({h['total_growth_pct']:+.1f}%); "
          f"IMM {h['IMM_change']:+.0f} = {h['IMM_share_of_change_pct']:.1f}% of change; "
          f"core {h['core_growth_pct']:+.1f}% vs core accommodation centres {h['core_centres_growth_pct']:+.1f}% "
          f"(per centre {h['core_per_centre_growth_pct']:+.1f}%); all centres {h['all_centres_growth_pct']:+.1f}%")


if __name__ == "__main__":
    main()
