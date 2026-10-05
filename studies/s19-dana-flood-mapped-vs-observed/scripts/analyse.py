#!/usr/bin/env python3
"""Aggregate the flagged buildings into the published tables (data/, aggregates only).

    .venv/bin/python scripts/analyse.py

Primary scenario (after review, METHOD.md section 9): extent 'all' (every Copernicus EMSR773
product for the province of Valencia), a building is inside the extent when its footprint
intersects it, and inside a zone when its footprint touches the zone envelope (the SNCZI/ARPSI
depth grid with enclosed holes of up to 2 ha closed; PATRICOVA polygons as published). The same
rule is reported for the Generalitat's footprint. Unit: dwellings (Catastro numberOfDwellings).

Disclosure control (scripts/disclosure.py): no published cell represents 1-4 buildings, and
complementary suppression makes sure no suppressed value can be recovered from the published
totals. Shares are given only where both counts are published, and the leave-one-out shares are
rounded to 0.1 percentage points. scripts/check_disclosure.py tests the files as written."""
import collections
import csv
import glob
import json
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s19lib as L
from disclosure import Registry

R = L.R
D = os.path.join(R, "data")
VARIANTS = ["all", "first", "aoi01_first", "flooded_only", "earlier_versions", "gva_footprint",
            "all_or_gva", "all_plus10m", "all_minus10m", "all_plus25m", "all_minus25m"]
COP = ["all", "first", "aoi01_first", "earlier_versions", "all_plus10m", "all_minus10m", "all_plus25m", "all_minus25m"]
# 'all_or_gva' (added after the plan was frozen): the union of the Copernicus extent and the
# Generalitat's footprint. A footprint meets a union iff it meets either part, and a centroid lies
# in it iff it lies in either, so the flag is derived without re-reading the buildings.
DERIVED = {"all_or_gva": ("all", "gva_footprint")}
# zone rules -> flag suffix (classify.py). env = depth grid with enclosed holes closed (2 ha unless
# stated), fp = any footprint pixel, ct = the centroid. 'fp'/'ct' alone = the depth grid as drawn.
ZR = {"envfp": "env2fp", "envct": "env2ct", "fp": "fp", "ct": "ct",
      "env05fp": "env05fp", "env5fp": "env5fp", "env05ct": "env05ct", "env5ct": "env5ct"}
FROZEN_ZR = ("fp", "ct")
PRIMARY = {"variant": "all", "extent_rule": "fp", "zone_rule": "envfp"}
KEYS = ("t10", "t100", "t500", "pat16", "patgeo")
BANDS = [b[0] for b in L.YEAR_BANDS] + ["unknown"]
# the municipal table is coarser (fewer small cells): T10 merged into T100, three year bands
S5 = ["SNCZI T100 or T10", "SNCZI T500 (not T100)", "PATRICOVA levels 1-6 only",
      "PATRICOVA geomorphological only", "outside every official zone"]
B3 = ["2016 or earlier, or unknown", "2017-2024", "2025 or later"]


def s5(s):
    return S5[0] if s in L.STATUS_ORDER[:2] else s


B5 = ["1985 or earlier, or unknown", "1986-2007", "2008-2016", "2017-2024", "2025 or later"]


def b5(band):
    return B5[0] if band in ("1985 or earlier", "unknown") else band


def b3(band):
    return band if band in ("2017-2024", "2025 or later") else B3[0]
POST = ("2017-2024", "2025 or later")
ST = L.STATUS_ORDER
OUTSIDE = ST[-1]
SNCZI = ST[:3]


def load():
    totals = json.load(open(os.path.join(R, "work", "buildings", "totals.json")))
    data = {}
    for f in sorted(glob.glob(os.path.join(R, "work", "buildings", "*.pkl"))):
        ine = os.path.basename(f)[:-4]
        ff = os.path.join(R, "work", "flags", f"{ine}.pkl")
        if not os.path.exists(ff):
            raise SystemExit(f"no flags for {ine}: run scripts/classify.py")
        rows, flags = pickle.load(open(f, "rb")), pickle.load(open(ff, "rb"))
        for r, fl in zip(rows, flags):
            r.pop("wkb", None)
            r["flags"] = fl
        data[ine] = rows
    return totals, data


def status(r, zr):
    f = r["flags"]
    return L.map_status({k: f[f"{k}_{ZR[zr]}"] for k in KEYS})


def flooded(r, variant, er):
    if variant in DERIVED:
        return any(bool(r[er].get(v)) for v in DERIVED[variant])
    return bool(r[er].get(variant))


def scenario(data, variant, er, zr, munis=None):
    """dwellings, buildings with dwellings and all buildings, by status, and dwellings by band x status."""
    c = {u: collections.Counter() for u in ("d", "b", "a")}
    y = collections.Counter()
    for ine, rows in data.items():
        if munis is not None and ine not in munis:
            continue
        for r in rows:
            if not flooded(r, variant, er):
                continue
            s = status(r, zr)
            c["a"][s] += 1
            if r["dwellings"] > 0:
                c["d"][s] += r["dwellings"]
                c["b"][s] += 1
                y[(L.year_band(r["year"]), s)] += r["dwellings"]
    return c, y


def shares(counter):
    n = sum(counter.values())
    out = counter[OUTSIDE]
    sn = sum(counter[s] for s in SNCZI)
    rp = sn + counter[ST[3]]
    return {"n": n, "outside": out, "share_outside": out / n if n else None,
            "share_outside_snczi": (n - sn) / n if n else None,
            "share_outside_return_period": (n - rp) / n if n else None}


def write_csv(name, header, rows):
    with open(os.path.join(D, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def r6(x):
    return "" if x is None else round(x, 6)


def main():
    os.makedirs(D, exist_ok=True)
    totals, data = load()
    ext = json.load(open(os.path.join(R, "work", "extent", "extent_summary.json")))
    names = {k: v["name"] for k, v in totals.items()}
    munis = sorted(data)
    reg = Registry(k=5)
    V, ER, ZP = PRIMARY["variant"], PRIMARY["extent_rule"], PRIMARY["zone_rule"]

    # ------------------------------------------------------------------ cells: municipality x status x band
    cell = collections.defaultdict(lambda: [0, 0])            # (ine, s5, b3) -> [b, d]
    prov = collections.defaultdict(lambda: [0, 0])            # (band, status) -> [b, d]
    use = collections.defaultdict(lambda: [0, 0, 0])          # (use, s) -> [a, b, d]
    gva = collections.defaultdict(lambda: [0, 0])             # (ine, 'in'|'out'|'both'|'either') -> [b, d]
    mct = collections.defaultdict(lambda: [0, 0])             # ine -> outside under centroid-in-envelope
    overlap = collections.defaultdict(lambda: [0, 0])
    for ine in munis:
        for r in data[ine]:
            a_in = flooded(r, V, ER)
            g_in = flooded(r, "gva_footprint", ER)
            if a_in:
                s = status(r, ZP)
                u = use[(r["use"], s5(s))]
                u[0] += 1
                if r["dwellings"] > 0:
                    u[1] += 1
                    u[2] += r["dwellings"]
            if r["dwellings"] <= 0:
                continue
            dw = r["dwellings"]
            if a_in:
                band = L.year_band(r["year"])
                for c in (cell[(ine, s5(s), b3(band))], prov[(b5(band), s5(s))]):
                    c[0] += 1
                    c[1] += dw
                if status(r, "envct") == OUTSIDE:
                    mct[ine][0] += 1
                    mct[ine][1] += dw
                f = r["flags"]
                sn = any(f[f"{k}_{ZR[ZP]}"] for k in ("t10", "t100", "t500"))
                key = ("SNCZI" if sn else "-", "PATRICOVA 1-6" if f[f"pat16_{ZR[ZP]}"] else "-",
                       "PATRICOVA geomorph." if f[f"patgeo_{ZR[ZP]}"] else "-")
                overlap[key][0] += 1
                overlap[key][1] += dw
            if g_in:
                for k in ("in",) + (("out",) if status(r, ZP) == OUTSIDE else ()):
                    gva[(ine, k)][0] += 1
                    gva[(ine, k)][1] += dw
            if a_in and g_in:
                gva[(ine, "both")][0] += 1
                gva[(ine, "both")][1] += dw
            if a_in or g_in:
                gva[(ine, "either")][0] += 1
                gva[(ine, "either")][1] += dw

    # register groups and equations
    for ine in munis:
        for s in S5:
            for band in B3:
                b, d = cell[(ine, s, band)]
                reg.add(("c", ine, s, band), b=b, d=d)
        m_in = reg.add(("m", ine, "in"), b=sum(cell[(ine, s, bd)][0] for s in S5 for bd in B3),
                       d=sum(cell[(ine, s, bd)][1] for s in S5 for bd in B3))
        reg.total(m_in, [("c", ine, s, bd) for s in S5 for bd in B3])
        m_out = reg.add(("m", ine, "out"), b=sum(cell[(ine, OUTSIDE, bd)][0] for bd in B3),
                        d=sum(cell[(ine, OUTSIDE, bd)][1] for bd in B3))
        reg.total(m_out, [("c", ine, OUTSIDE, bd) for bd in B3])
        m_17 = reg.add(("m", ine, "b1724"), b=sum(cell[(ine, s, "2017-2024")][0] for s in S5),
                       d=sum(cell[(ine, s, "2017-2024")][1] for s in S5))
        reg.total(m_17, [("c", ine, s, "2017-2024") for s in S5])
        reg.add(("mct", ine), b=mct[ine][0], d=mct[ine][1])
        for k in ("in", "out", "both", "either"):
            reg.add(("g", ine, k), b=gva[(ine, k)][0], d=gva[(ine, k)][1])
        # either = copernicus + gva - both
        reg.total(("g", ine, "either"), [m_in, ("g", ine, "in"), ("g", ine, "both")], signs=[1, 1, -1])
    for band in B5:
        for s in S5:
            reg.add(("p", band, s), b=prov[(band, s)][0], d=prov[(band, s)][1])
        reg.add(("pb", band), b=sum(prov[(band, s)][0] for s in S5), d=sum(prov[(band, s)][1] for s in S5))
        reg.total(("pb", band), [("p", band, s) for s in S5])
    # the municipal cells add up to sums of province cells
    for s in S5:
        for bd in B3:
            parts = [("p", band, s) for band in B5 if b3(band) == bd]
            reg.eqs.append(("b", [(("c", i, s, bd), 1) for i in munis] + [(g, -1) for g in parts]))
            reg.eqs.append(("d", [(("c", i, s, bd), 1) for i in munis] + [(g, -1) for g in parts]))
    for s in S5:
        reg.add(("ps", s), b=sum(prov[(bd, s)][0] for bd in B5), d=sum(prov[(bd, s)][1] for bd in B5))
        reg.total(("ps", s), [("p", bd, s) for bd in B5])
    # the SNCZI T10 / T100 split, published only as province totals
    t10 = [sum(1 for i in munis for r in data[i] if r["dwellings"] > 0 and flooded(r, V, ER) and status(r, ZP) == ST[0]),
           sum(r["dwellings"] for i in munis for r in data[i] if r["dwellings"] > 0 and flooded(r, V, ER) and status(r, ZP) == ST[0])]
    reg.add(("pT10",), b=t10[0], d=t10[1])
    reg.add(("pT100",), b=reg.value(("ps", S5[0]), "b") - t10[0], d=reg.value(("ps", S5[0]), "d") - t10[1])
    reg.total(("ps", S5[0]), [("pT10",), ("pT100",)])
    reg.add(("pt",), b=sum(reg.value(("ps", s), "b") for s in S5), d=sum(reg.value(("ps", s), "d") for s in S5))
    reg.total(("pt",), [("ps", s) for s in S5])
    reg.total(("pt",), [("m", i, "in") for i in munis])
    reg.total(("pt",), [("pb", bd) for bd in B5])
    for k in ("in", "out", "both", "either"):
        reg.add(("gt", k), b=sum(reg.value(("g", i, k), "b") for i in munis), d=sum(reg.value(("g", i, k), "d") for i in munis))
        reg.total(("gt", k), [("g", i, k) for i in munis])
    reg.add(("mctt",), b=sum(mct[i][0] for i in munis), d=sum(mct[i][1] for i in munis))
    reg.total(("mctt",), [("mct", i) for i in munis])
    # uses (all buildings 'a', and dwellings)
    uses = sorted({u for u, _ in use})
    for u in uses:
        for s in S5:
            a, b, d = use[(u, s)]
            reg.add(("u", u, s), a=a, b=b, d=d)
        reg.add(("ut", u), a=sum(use[(u, s)][0] for s in S5), b=sum(use[(u, s)][1] for s in S5), d=sum(use[(u, s)][2] for s in S5))
        reg.total(("ut", u), [("u", u, s) for s in S5], vars=("a", "b", "d"))
    for s in S5:
        reg.add(("pa", s), a=sum(use[(u, s)][0] for u in uses))
        reg.total(("pa", s), [("u", u, s) for u in uses], vars=("a",))
        reg.total(("ps", s), [("u", u, s) for u in uses], vars=("b", "d"))
    reg.add(("pat",), a=sum(reg.value(("pa", s), "a") for s in S5))
    reg.total(("pat",), [("pa", s) for s in S5], vars=("a",))
    reg.total(("pat",), [("ut", u) for u in uses], vars=("a",))
    combos = sorted(overlap)
    for k in combos:
        reg.add(("zo",) + k, b=overlap[k][0], d=overlap[k][1])
    reg.total(("pt",), [("zo",) + k for k in combos])

    n1, n2 = reg.run()
    print(f"suppression: {n1} primary, {n2} complementary groups", flush=True)
    F = reg.fmt

    # ------------------------------------------------------------------ files
    rows = []
    for ine in munis:
        for s in S5:
            for band in B3:
                g = ("c", ine, s, band)
                if reg.value(g, "b") or reg.groups[g]["supp"]:
                    rows.append([ine, names[ine], s, band, F(g, "b"), F(g, "d")])
    write_csv("dwellings_in_extent.csv", ["ine_code", "municipality", "map_status", "year_band",
                                          "buildings_with_dwellings", "dwellings"], rows)

    def share(num, den, var="d"):
        if not (reg.published(num) and reg.published(den)) or not reg.value(den, var):
            return ""
        return round(reg.value(num, var) / reg.value(den, var), 3)

    rows = []
    for ine in munis:
        t = totals[ine]
        fl = ext["variants"][V]["municipalities"].get(ine, {}).get("flooded_ha", 0)
        mi, mo, m17, mg, mgo, mc = ("m", ine, "in"), ("m", ine, "out"), ("m", ine, "b1724"), ("g", ine, "in"), ("g", ine, "out"), ("mct", ine)
        rows.append([ine, names[ine], round(fl, 1), t["dwellings"],
                     F(mi, "b"), F(mi, "d"), F(mo, "b"), F(mo, "d"), share(mo, mi),
                     F(mc, "d"), share(mc, mi),
                     F(m17, "b"), F(m17, "d"), F(("c", ine, OUTSIDE, "2017-2024"), "d"),
                     F(mg, "b"), F(mg, "d"), F(mgo, "d"), share(mgo, mg)])
    write_csv("municipalities.csv", ["ine_code", "municipality", "flooded_area_ha", "dwellings_in_municipality",
                                     "buildings_with_dwellings_in_extent", "dwellings_in_extent",
                                     "buildings_outside_all_zones", "dwellings_outside_all_zones", "share_outside_all_zones",
                                     "dwellings_outside_all_zones_centroid_in_envelope", "share_outside_centroid_in_envelope",
                                     "buildings_built_2017_2024", "dwellings_built_2017_2024",
                                     "dwellings_built_2017_2024_outside_all_zones",
                                     "gva_buildings_with_dwellings_in_footprint", "gva_dwellings_in_footprint",
                                     "gva_dwellings_outside_all_zones", "gva_share_outside_all_zones"], rows)
    write_csv("by_year.csv", ["year_band", "map_status", "buildings_with_dwellings", "dwellings"],
              [[bd, s, F(("p", bd, s), "b"), F(("p", bd, s), "d")] for bd in B5 for s in S5])
    write_csv("by_use.csv", ["use", "map_status", "buildings", "buildings_with_dwellings", "dwellings"],
              [[u, s, F(("u", u, s), "a"), F(("u", u, s), "b"), F(("u", u, s), "d")] for u in uses for s in S5
               if reg.value(("u", u, s), "a") or reg.groups[("u", u, s)]["supp"]]
              + [[u, "all", F(("ut", u), "a"), F(("ut", u), "b"), F(("ut", u), "d")] for u in uses])
    write_csv("zone_overlap.csv", ["snczi_t10_t100_t500", "patricova_levels_1_6", "patricova_geomorphological",
                                   "buildings_with_dwellings", "dwellings"],
              [list(k) + [F(("zo",) + k, "b"), F(("zo",) + k, "d")] for k in combos])
    write_csv("extent_comparison.csv", ["ine_code", "municipality", "dwellings_copernicus", "dwellings_gva_footprint",
                                        "dwellings_both", "dwellings_either"],
              [[i, names[i], F(("m", i, "in"), "d"), F(("g", i, "in"), "d"), F(("g", i, "both"), "d"), F(("g", i, "either"), "d")]
               for i in munis if reg.value(("g", i, "either"), "b") or reg.groups[("g", i, "either")]["supp"]])
    write_csv("extent_variants.csv", ["extent_variant", "area_ha", "area_in_province_ha", "municipalities_touched"],
              [[v, ext["variants"][v]["area_ha"], ext["variants"][v]["area_in_province_ha"],
                ext["variants"][v]["municipalities_touched"]] for v in VARIANTS if v in ext["variants"]])

    # ------------------------------------------------------------------ sensitivity
    sens = []
    for v in VARIANTS:
        for er in ("fp", "ct"):
            for zr in ZR:
                c, y = scenario(data, v, er, zr)
                for unit, key in (("dwellings", "d"), ("buildings with dwellings", "b"), ("all buildings", "a")):
                    sh = shares(c[key])
                    p17 = sum(y[(bd, s)] for bd in POST for s in ST) if key == "d" else ""
                    sens.append([v, er, zr, unit, sh["n"], sh["outside"], r6(sh["share_outside"]),
                                 r6(sh["share_outside_snczi"]), r6(sh["share_outside_return_period"]), p17])
    write_csv("sensitivity.csv", ["extent_variant", "extent_rule", "zone_rule", "unit", "n_in_extent", "n_outside_all_zones",
                                  "share_outside_all_zones", "share_outside_snczi", "share_outside_return_period_zones",
                                  "dwellings_built_2017_or_later"], sens)
    dw = {(r[0], r[1], r[2]): r for r in sens if r[3] == "dwellings"}

    def rng(keys):
        vals = [dw[k][6] for k in keys]
        return [min(vals), max(vals)]
    main_keys = [(v, er, zr) for v in COP + ["gva_footprint", "all_or_gva"] for er in ("fp", "ct")
                 for zr in ZR if zr != "ct"]
    # the headline: the two extents (footprint meets the extent) and the three rules
    headline_keys = [(v, "fp", zr) for v in ("all", "gva_footprint") for zr in ("envfp", "envct", "fp")]
    # plus the Copernicus product versions, edge buffers, the union and the centroid tested against the extent
    variant_keys = [(v, er, zr) for v in COP + ["gva_footprint", "all_or_gva"] for er in ("fp", "ct")
                    for zr in ("envfp", "envct", "fp")]
    frozen_keys = [(v, er, zr) for v in VARIANTS if v not in DERIVED for er in ("fp", "ct") for zr in FROZEN_ZR]

    # ------------------------------------------------------------------ leave one out (rounded)
    loo = []
    allv = []
    for ine in munis:
        c, _ = scenario(data, V, ER, ZP, munis=set(munis) - {ine})
        sh = shares(c["d"])
        allv.append((sh["share_outside"], names[ine]))
        if reg.published(("m", ine, "in")) and reg.value(("m", ine, "in"), "b") >= 5:
            loo.append([ine, names[ine], round(sh["share_outside"], 3)])
    write_csv("leave_one_out.csv", ["dropped_ine_code", "dropped_municipality", "share_outside_all_zones_rounded"], loo)

    # ------------------------------------------------------------------ matched comparison with the Generalitat footprint
    M = {i for i in munis if reg.value(("g", i, "in"), "d") > 0}
    matched = {"municipalities": len(M)}
    for zr in ("envfp", "fp", "envct"):
        ca, _ = scenario(data, V, ER, zr, munis=M)
        cg, _ = scenario(data, "gva_footprint", ER, zr, munis=M)
        sa, sg = shares(ca["d"]), shares(cg["d"])
        matched[zr] = {"copernicus_dwellings": sa["n"], "copernicus_share_outside": sa["share_outside"],
                       "gva_dwellings": sg["n"], "gva_share_outside": sg["share_outside"]}

    # ------------------------------------------------------------------ summary.json (published values only)
    S = {"primary": dict(PRIMARY), "disclosure": {"primary_suppressed_groups": n1, "complementary_suppressed_groups": n2}}
    P = S["primary"]
    P["municipalities_touched"] = ext["variants"][V]["municipalities_touched"]
    P["municipalities_with_dwellings_in_extent"] = sum(1 for i in munis if reg.value(("m", i, "in"), "d") > 0)
    P["extent_area_in_province_ha"] = ext["variants"][V]["area_in_province_ha"]
    P["dwellings_in_extent"] = F(("pt",), "d")
    P["buildings_with_dwellings_in_extent"] = F(("pt",), "b")
    P["buildings_in_extent"] = F(("pat",), "a")
    P["dwellings_by_status"] = {s: F(("ps", s), "d") for s in S5}
    P["buildings_with_dwellings_by_status"] = {s: F(("ps", s), "b") for s in S5}
    P["snczi_t10_dwellings"] = F(("pT10",), "d")
    P["snczi_t100_not_t10_dwellings"] = F(("pT100",), "d")
    pr = shares(collections.Counter({(ST[1] if s == S5[0] else s): reg.value(("ps", s), "d") for s in S5}))
    P["share_outside_all_zones"] = pr["share_outside"]
    P["share_outside_snczi"] = pr["share_outside_snczi"]
    P["share_outside_return_period_zones"] = pr["share_outside_return_period"]
    P["dwellings_by_band"] = {bd: F(("pb", bd), "d") for bd in B5}
    P["province_dwellings_in_touched_municipalities"] = sum(totals[i]["dwellings"] for i in munis)
    S["gva_footprint"] = {"dwellings": F(("gt", "in"), "d"), "outside_all": F(("gt", "out"), "d"),
                          "share_outside_all_zones": dw[("gva_footprint", "fp", "envfp")][6],
                          "both": F(("gt", "both"), "d"), "either": F(("gt", "either"), "d")}
    S["matched_comparison"] = matched
    S["ranges"] = {"headline_dwellings": rng(headline_keys), "with_variants_dwellings": rng(variant_keys),
                   "all_envelope_thresholds_dwellings": rng(main_keys), "frozen_plan_dwellings": rng(frozen_keys),
                   "copernicus_envfp": rng([(v, er, "envfp") for v in COP for er in ("fp", "ct")]),
                   "copernicus_envct": rng([(v, er, "envct") for v in COP for er in ("fp", "ct")]),
                   "copernicus_grid_fp": rng([(v, er, "fp") for v in COP for er in ("fp", "ct")]),
                   "copernicus_grid_ct": rng([(v, er, "ct") for v in COP for er in ("fp", "ct")]),
                   "leave_one_out": [min(allv)[0], max(allv)[0]],
                   "leave_one_out_extremes": [min(allv)[1], max(allv)[1]]}
    pil = {}
    pa = data.get("46186", [])
    for v in ("aoi01_first", "all"):
        s_in = [r for r in pa if r["dwellings"] > 0 and flooded(r, v, "fp")]
        pil[v] = {"dwellings_in_extent": sum(r["dwellings"] for r in s_in), "buildings_with_dwellings_in_extent": len(s_in),
                  "dwellings_2017_or_later": sum(r["dwellings"] for r in s_in if r["year"] and r["year"] >= 2017),
                  "buildings_2017_or_later": sum(1 for r in s_in if r["year"] and r["year"] >= 2017),
                  "buildings_2025_or_later": sum(1 for r in s_in if r["year"] and r["year"] >= 2025)}
    pil["dwellings_total"] = totals["46186"]["dwellings"]
    pil["buildings_with_dwellings_total"] = totals["46186"]["buildings_with_dwellings"]
    S["paiporta_pilot_recomputed"] = pil
    json.dump(S, open(os.path.join(D, "summary.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: P[k] for k in ("dwellings_in_extent", "share_outside_all_zones", "share_outside_snczi")}, ensure_ascii=False))
    print(json.dumps(S["ranges"], ensure_ascii=False))
    print(json.dumps(matched, ensure_ascii=False))
    print("gva", S["gva_footprint"])


if __name__ == "__main__":
    main()
