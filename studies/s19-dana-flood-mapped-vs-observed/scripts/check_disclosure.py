#!/usr/bin/env python3
"""Test the published files in data/ for disclosure, independently of analyse.py.

    python3 scripts/check_disclosure.py        # exit 1 on any failure

Checks:
1. No published table cell represents 1-4 buildings (buildings with dwellings, or all buildings).
2. summary.json holds no count of 1-4 (its 'text' block of dates, citations and parameters is not
   counts and is skipped).
3. No suppressed value ('<5') can be recovered exactly from the published files. The test builds
   every linear relation the files imply, from their meaning (a municipal total is the sum of its
   cells; a province cell is the sum over municipalities; summary totals are sums of by_year
   cells; 'either' = 'copernicus' + 'gva' - 'both'; ...) and checks with the null space of those
   relations that no suppressed value is fixed by the published ones.
4. Shares are published only where both counts are, and leave-one-out shares are rounded to
   0.1 percentage points with no counts.
Standard library plus numpy."""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

D = Path(__file__).resolve().parent.parent / "data"
ST = ["SNCZI T10", "SNCZI T100 (not T10)", "SNCZI T500 (not T100)", "PATRICOVA levels 1-6 only",
      "PATRICOVA geomorphological only", "outside every official zone"]
OUT = ST[-1]
BANDS = ["1985 or earlier", "1986-2007", "2008-2016", "2017-2024", "2025 or later", "unknown"]
POST = ("2017-2024", "2025 or later")
S5 = ["SNCZI T100 or T10", "SNCZI T500 (not T100)", "PATRICOVA levels 1-6 only",
      "PATRICOVA geomorphological only", "outside every official zone"]
B3 = ["2016 or earlier, or unknown", "2017-2024", "2025 or later"]


def s5(s):
    return S5[0] if s in ST[:2] else s


B5 = ["1985 or earlier, or unknown", "1986-2007", "2008-2016", "2017-2024", "2025 or later"]


def b3(band):
    return band if band in POST else B3[0]
bad = []


def rows(name):
    return list(csv.DictReader(open(D / name, encoding="utf-8")))


class System:
    def __init__(self):
        self.known = {}          # (var, key) -> value
        self.unknown = set()
        self.eqs = defaultdict(list)   # var -> list of [(key, coef)]

    def put(self, var, key, val):
        if val in ("", None):
            return
        if val == "<5":
            self.unknown.add((var, key))
        else:
            self.known[(var, key)] = float(val)

    def eq(self, var, total, parts, signs=None):
        signs = signs or [1] * len(parts)
        self.eqs[var].append([(total, -1)] + list(zip(parts, signs)))

    def determined(self):
        out = []
        for var, eqs in self.eqs.items():
            unk = sorted({k for e in eqs for k, _ in e if (var, k) in self.unknown}, key=str)
            if not unk:
                continue
            col = {k: j for j, k in enumerate(unk)}
            A = []
            for e in eqs:
                keys = [k for k, _ in e]
                # an equation is usable only if each of its terms is published, suppressed, or an
                # absent cell (zero); a term that is not published anywhere makes it unusable
                if any((var, k) not in self.known and (var, k) not in self.unknown and k[0] not in ZERO_OK for k in keys):
                    continue
                r = np.zeros(len(unk))
                for k, c in e:
                    if k in col:
                        r[col[k]] += c
                if r.any():
                    A.append(r)
            if not A:
                continue
            A = np.array(A)
            _, s, vt = np.linalg.svd(A, full_matrices=True)
            rank = int((s > 1e-9 * max(1.0, s.max())).sum())
            ns = vt[rank:]
            for k, j in col.items():
                if ns.shape[0] == 0 or np.abs(ns[:, j]).max() < 1e-9:
                    out.append((var, k))
        return out


ZERO_OK = {"c"}     # absent rows of dwellings_in_extent.csv are true zeros


def small(v):
    return v not in ("", "<5", None) and 0 < float(v) < 5


def main():
    S = System()
    # 1. cells
    fd = rows("dwellings_in_extent.csv")
    munis = sorted({r["ine_code"] for r in fd} | {r["ine_code"] for r in rows("municipalities.csv")})
    for r in fd:
        k = ("c", r["ine_code"], r["map_status"], r["year_band"])
        if small(r["buildings_with_dwellings"]):
            bad.append(f"dwellings_in_extent.csv: {k} has {r['buildings_with_dwellings']} buildings")
        S.put("b", k, r["buildings_with_dwellings"])
        S.put("d", k, r["dwellings"])
    for i in munis:          # absent cells are zeros
        for s in S5:
            for bd in B3:
                for v in ("b", "d"):
                    S.known.setdefault((v, ("c", i, s, bd)), 0.0) if (v, ("c", i, s, bd)) not in S.unknown else None
    # 2. municipalities
    mrows = rows("municipalities.csv")
    for r in mrows:
        i = r["ine_code"]
        for col in ("buildings_with_dwellings_in_extent", "buildings_outside_all_zones", "buildings_built_2017_2024",
                    "gva_buildings_with_dwellings_in_footprint"):
            if small(r[col]):
                bad.append(f"municipalities.csv: {i} {col} = {r[col]}")
        S.put("b", ("m", i, "in"), r["buildings_with_dwellings_in_extent"]); S.put("d", ("m", i, "in"), r["dwellings_in_extent"])
        S.put("b", ("m", i, "out"), r["buildings_outside_all_zones"]); S.put("d", ("m", i, "out"), r["dwellings_outside_all_zones"])
        S.put("b", ("m", i, "b1724"), r["buildings_built_2017_2024"]); S.put("d", ("m", i, "b1724"), r["dwellings_built_2017_2024"])
        S.put("d", ("m", i, "b1724out"), r["dwellings_built_2017_2024_outside_all_zones"])
        S.put("d", ("mct", i), r["dwellings_outside_all_zones_centroid_in_envelope"])
        S.put("b", ("g", i, "in"), r["gva_buildings_with_dwellings_in_footprint"]); S.put("d", ("g", i, "in"), r["gva_dwellings_in_footprint"])
        S.put("d", ("g", i, "out"), r["gva_dwellings_outside_all_zones"])
        for v in ("b", "d"):
            S.eq(v, ("m", i, "in"), [("c", i, s, bd) for s in S5 for bd in B3])
            S.eq(v, ("m", i, "out"), [("c", i, OUT, bd) for bd in B3])
            S.eq(v, ("m", i, "b1724"), [("c", i, s, "2017-2024") for s in S5])
        S.eq("d", ("m", i, "b1724out"), [("c", i, OUT, "2017-2024")])
        for num, den in (("dwellings_outside_all_zones", "dwellings_in_extent"),
                         ("dwellings_outside_all_zones_centroid_in_envelope", "dwellings_in_extent"),
                         ("gva_dwellings_outside_all_zones", "gva_dwellings_in_footprint")):
            sh = {"dwellings_outside_all_zones": "share_outside_all_zones",
                  "dwellings_outside_all_zones_centroid_in_envelope": "share_outside_centroid_in_envelope",
                  "gva_dwellings_outside_all_zones": "gva_share_outside_all_zones"}[num]
            if r[sh] != "" and ("<5" in (r[num], r[den]) or r[num] == "" or r[den] == ""):
                bad.append(f"municipalities.csv: {i} {sh} published although a count is suppressed")
    # 3. extent comparison
    for r in rows("extent_comparison.csv"):
        i = r["ine_code"]
        S.put("d", ("m", i, "in"), r["dwellings_copernicus"])
        S.put("d", ("g", i, "in"), r["dwellings_gva_footprint"])
        S.put("d", ("g", i, "both"), r["dwellings_both"])
        S.put("d", ("g", i, "either"), r["dwellings_either"])
        S.eq("d", ("g", i, "either"), [("m", i, "in"), ("g", i, "in"), ("g", i, "both")], [1, 1, -1])
    listed = {r["ine_code"] for r in rows("extent_comparison.csv")}
    for i in munis:          # municipalities absent from the comparison have zero in both extents
        if i not in listed:
            for key in ("both", "either"):
                S.known[("d", ("g", i, key))] = 0.0
    # 4. province by year
    for r in rows("by_year.csv"):
        k = ("p", r["year_band"], r["map_status"])
        if small(r["buildings_with_dwellings"]):
            bad.append(f"by_year.csv: {k} has {r['buildings_with_dwellings']} buildings")
        S.put("b", k, r["buildings_with_dwellings"]); S.put("d", k, r["dwellings"])
    for bd in B5:
        for s in S5:
            for v in ("b", "d"):
                if (v, ("p", bd, s)) not in S.unknown:
                    S.known.setdefault((v, ("p", bd, s)), 0.0)
    # municipal cells (three bands) add up to sums of province cells (five bands)
    for s in S5:
        for bd in B3:
            for v in ("b", "d"):
                S.eqs[v].append([(("c", i, s, bd), 1) for i in munis] +
                                [(("p", band, s), -1) for band in B5 if b3(band) == bd])
    # 5. uses
    for r in rows("by_use.csv"):
        k = ("u", r["use"], r["map_status"]) if r["map_status"] != "all" else ("ut", r["use"])
        if small(r["buildings"]) or small(r["buildings_with_dwellings"]):
            bad.append(f"by_use.csv: {k} has a cell of 1-4 buildings")
        S.put("a", k, r["buildings"]); S.put("b", k, r["buildings_with_dwellings"]); S.put("d", k, r["dwellings"])
    uses = sorted({r["use"] for r in rows("by_use.csv")})
    for u in uses:
        for s in S5:
            for v in ("a", "b", "d"):
                if (v, ("u", u, s)) not in S.unknown:
                    S.known.setdefault((v, ("u", u, s)), 0.0)
        for v in ("a", "b", "d"):
            S.eq(v, ("ut", u), [("u", u, s) for s in S5])
    # 6. zone overlap
    zo = rows("zone_overlap.csv")
    for r in zo:
        k = ("zo", r["snczi_t10_t100_t500"], r["patricova_levels_1_6"], r["patricova_geomorphological"])
        if small(r["buildings_with_dwellings"]):
            bad.append(f"zone_overlap.csv: {k} has 1-4 buildings")
        S.put("b", k, r["buildings_with_dwellings"]); S.put("d", k, r["dwellings"])
    # 7. summary.json
    J = json.load(open(D / "summary.json", encoding="utf-8"))

    def scan(o, path=""):
        if path == ".text":  # dates, legal citations and method parameters the text quotes: not counts
            return
        if isinstance(o, dict):
            for k, v in o.items():
                scan(v, f"{path}.{k}")
        elif isinstance(o, list):
            for j, v in enumerate(o):
                scan(v, f"{path}[{j}]")
        elif isinstance(o, int) and not isinstance(o, bool) and 0 < o < 5:
            bad.append(f"summary.json{path} = {o}")
    scan(J)
    P = J["primary"]
    for s in S5:
        S.put("d", ("ps", s), P["dwellings_by_status"][s]); S.put("b", ("ps", s), P["buildings_with_dwellings_by_status"][s])
        for v in ("b", "d"):
            S.eq(v, ("ps", s), [("p", bd, s) for bd in B5])
            S.eq(v, ("ps", s), [("u", u, s) for u in uses])
    S.put("d", ("pT10",), P["snczi_t10_dwellings"]); S.put("d", ("pT100",), P["snczi_t100_not_t10_dwellings"])
    S.eq("d", ("ps", S5[0]), [("pT10",), ("pT100",)])
    S.put("d", ("pt",), P["dwellings_in_extent"]); S.put("b", ("pt",), P["buildings_with_dwellings_in_extent"])
    for v in ("b", "d"):
        S.eq(v, ("pt",), [("ps", s) for s in S5])
        S.eq(v, ("pt",), [("m", i, "in") for i in munis])
        S.eq(v, ("pt",), [("zo",) + (r["snczi_t10_t100_t500"], r["patricova_levels_1_6"], r["patricova_geomorphological"]) for r in zo])
    for bd in B5:
        S.put("d", ("pb", bd), P["dwellings_by_band"][bd])
        S.eq("d", ("pb", bd), [("p", bd, s) for s in S5])
    G = J["gva_footprint"]
    for k, key in (("dwellings", "in"), ("outside_all", "out"), ("both", "both"), ("either", "either")):
        S.put("d", ("gt", key), G[k])
        S.eq("d", ("gt", key), [("g", i, key) for i in munis])
    # 8. sensitivity: province totals of the primary scenario and of the centroid-in-envelope rule
    sens = {(r["extent_variant"], r["extent_rule"], r["zone_rule"], r["unit"]): r for r in rows("sensitivity.csv")}
    for r in sens.values():
        for col in ("n_in_extent", "n_outside_all_zones"):
            if small(r[col]):
                bad.append(f"sensitivity.csv: {tuple(r.values())[:4]} {col} = {r[col]}")
    pc = sens[("all", "fp", "envct", "dwellings")]
    S.put("d", ("mctt",), pc["n_outside_all_zones"])
    S.eq("d", ("mctt",), [("mct", i) for i in munis])
    pa = sens[("all", "fp", "envfp", "all buildings")]
    S.put("a", ("pat",), pa["n_in_extent"])
    S.eq("a", ("pat",), [("ut", u) for u in uses])
    # 9. leave one out
    for r in rows("leave_one_out.csv"):
        if set(r) - {"dropped_ine_code", "dropped_municipality", "share_outside_all_zones_rounded"}:
            bad.append("leave_one_out.csv has extra columns")
        if len(r["share_outside_all_zones_rounded"].split(".")[-1]) > 3:
            bad.append(f"leave_one_out.csv: share not rounded for {r['dropped_ine_code']}")

    det = S.determined()
    for v, k in det:
        bad.append(f"recoverable suppressed value: {v} {k}")
    print(f"{len(S.unknown)} suppressed values, {sum(len(e) for e in S.eqs.values())} relations tested")
    if bad:
        print("DISCLOSURE PROBLEMS:")
        for b in bad[:60]:
            print(" -", b)
        print(f"({len(bad)} in all)")
        sys.exit(1)
    print("disclosure check passed")


if __name__ == "__main__":
    main()
