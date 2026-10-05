#!/usr/bin/env python3
"""Assert every headline number of README.md (and paper.md, when present) against data/.

The numbers are recomputed from the published tables: sensitivity.csv (every extent x rule x unit,
unsuppressed province totals), by_year.csv (province, year band x map status), municipalities.csv,
leave_one_out.csv and summary.json; the tables are also checked against each other. Each expected
string must appear in the documents (whitespace collapsed). Exit 1 on any mismatch. paper.md may be
absent from the public package: the check then covers README.md only."""
import csv
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
D = R / "data"
PAPER_URL = "https://easybyte.es/lab/studies/s19/paper/"
COP = ["all", "first", "aoi01_first", "earlier_versions", "all_plus10m", "all_minus10m", "all_plus25m", "all_minus25m"]


def flat(s):
    return re.sub(r"\s+", " ", s)


def f(n):
    return f"{int(n):,}"


def pct(x, d=1):
    return f"{100 * float(x):.{d}f}%"


def rows(name):
    return list(csv.DictReader(open(D / name, encoding="utf-8")))


docs = {"README.md": flat((R / "README.md").read_text(encoding="utf-8"))}
if (R / "paper.md").exists():
    docs["paper.md"] = flat((R / "paper.md").read_text(encoding="utf-8"))
else:
    print(f"paper.md is not in the public package: the paper is at {PAPER_URL}")
bad = []
BOTH, PAPER, ROW = ("README.md", "paper.md"), ("paper.md",), ("root row",)
# The study's row in the repository's README (the headline the site shows), when the study sits in it.
ROOT = R.parent.parent / "README.md"
if ROOT.exists():
    row = [ln for ln in ROOT.read_text(encoding="utf-8").splitlines() if ln.startswith("| [S19](")]
    if len(row) != 1:
        bad.append(f"repository README: {len(row)} rows for S19")
    else:
        docs["root row"] = flat(row[0])
else:
    print("not inside the studies repository: the root-table row is not checked")


def need(label, text, where=BOTH):
    print(f"{label}: {text}")
    for w in where:
        if w in docs and text not in docs[w]:
            bad.append(f"{w} does not contain «{text}» ({label})")


def same(label, a, b):
    if a != b:
        bad.append(f"{label}: {a} != {b}")


S = json.load(open(D / "summary.json", encoding="utf-8"))
P = S["primary"]
sens = {(r["extent_variant"], r["extent_rule"], r["zone_rule"], r["unit"]): r for r in rows("sensitivity.csv")}


def sc(v="all", er="fp", zr="envfp", unit="dwellings"):
    return sens[(v, er, zr, unit)]


def share(v="all", er="fp", zr="envfp", unit="dwellings"):
    return float(sc(v, er, zr, unit)["share_outside_all_zones"])


def rng(keys, d=1):
    vals = [share(*k) for k in keys]
    return f"{100 * min(vals):.{d}f}–{100 * max(vals):.{d}f}%"


# ---------------------------------------------------------------- primary, both extents
p = sc()
n, out = int(p["n_in_extent"]), int(p["n_outside_all_zones"])
same("dwellings in extent (summary)", n, P["dwellings_in_extent"])
same("outside (summary)", out, P["dwellings_by_status"]["outside every official zone"])
need("dwellings in the Copernicus extent", f"{f(n)} dwellings")
need("outside every zone", f"{f(out)} ({pct(out / n)})")
need("SNCZI alone", pct(float(p["share_outside_snczi"])))
need("SNCZI 100-year zone", f(P["dwellings_by_status"]["SNCZI T100 or T10"]))
g = sc("gva_footprint")
need("Generalitat footprint dwellings", f(g["n_in_extent"]))
need("Generalitat footprint share", f"{f(g['n_outside_all_zones'])} ({pct(share('gva_footprint'))})")
need("union", pct(share("all_or_gva")))
need("buildings with dwellings / all buildings", f"{pct(share(unit='buildings with dwellings'))} / {pct(share(unit='all buildings'))}", PAPER)

# ---------------------------------------------------------------- matched comparison
M = S["matched_comparison"]
need("matched municipalities", f"{M['municipalities']} municipalities")
need("matched, depth-grid footprint rule", f"{pct(M['fp']['copernicus_share_outside'])} with the Copernicus extent and {pct(M['fp']['gva_share_outside'])} with the Generalitat's footprint")
need("matched, envelope footprint rule (abstracts)", f"{pct(M['envfp']['copernicus_share_outside'])} and {pct(M['envfp']['gva_share_outside'])} under the reference rule")
need("matched, envelope footprint rule", f"{pct(M['envfp']['copernicus_share_outside'])} against {pct(M['envfp']['gva_share_outside'])}", PAPER)
same("matched gva = all gva", M["envfp"]["gva_dwellings"], int(g["n_in_extent"]))

# ---------------------------------------------------------------- rules and ranges
two = [(v, "fp", zr) for v in ("all", "gva_footprint") for zr in ("envfp", "envct", "fp")]
vals = [share(*k) for k in two]
same("headline range = summary.json", [round(min(vals), 6), round(max(vals), 6)], S["ranges"]["headline_dwellings"])
need("headline range, two extents and three rules, whole percent", f"{100 * min(vals):.0f}–{100 * max(vals):.0f}%")
need("root row: reference figure first", f"Of {f(n)} dwellings inside the EU's Copernicus outline", ROW)
need("root row: outside every zone", f"{f(out)} ({pct(out / n)}) lay outside every official flood zone", ROW)
need("root row: range over two extents and three rules",
     f"Across two flood outlines and three counting rules, the share outside is {100 * min(vals):.0f}–{100 * max(vals):.0f}%", ROW)
need("root row: caveat", "Counts of exposure, not of illegality.", ROW)
need("abstract lead: reference figure first", f"Of the {f(n)} dwellings inside the flood extent mapped by Copernicus EMS")
need("abstract lead: outside every zone", f"{f(out)} ({pct(out / n)}) lay outside every official flood zone under the reference rule")
main2 = [(v, er, zr) for v in COP + ["gva_footprint", "all_or_gva"] for er in ("fp", "ct") for zr in ("envfp", "envct", "fp")]
vals2 = [share(*k) for k in main2]
same("range with variants = summary.json", [round(min(vals2), 6), round(max(vals2), 6)], S["ranges"]["with_variants_dwellings"])
same("variants do not lower the bottom of the headline range", f"{100 * min(vals2):.0f}", f"{100 * min(vals):.0f}")
need("top with product versions, edge buffers and centroid at the extent, whole percent", f"up to {100 * max(vals2):.0f}%")
allthr = [(v, er, zr) for v in COP + ["gva_footprint", "all_or_gva"] for er in ("fp", "ct")
          for zr in ("envfp", "envct", "fp", "env05fp", "env5fp", "env05ct", "env5ct")]
vals = [share(*k) for k in allthr]
need("range with envelope thresholds 0.5-5 ha", f"{100 * min(vals):.0f}–{100 * max(vals):.0f}%", PAPER)
for zr, label in (("envfp", "footprint in envelope"), ("envct", "centroid in envelope"), ("fp", "depth-grid footprint"), ("ct", "depth-grid centroid")):
    need(f"Copernicus primary, {label}", pct(share(zr=zr)), PAPER)
    need(f"Copernicus range, {label}", rng([(v, er, zr) for v in COP for er in ("fp", "ct")]), PAPER)
for zr in ("env05fp", "env05ct", "env5ct"):
    need(f"threshold {zr}", pct(share(zr=zr)), PAPER)
frozen = [(v, er, zr) for v in ["all", "first", "aoi01_first", "flooded_only", "earlier_versions", "gva_footprint",
                                "all_plus10m", "all_minus10m", "all_plus25m", "all_minus25m"] for er in ("fp", "ct") for zr in ("fp", "ct")]
need("frozen-plan range", rng(frozen), PAPER)
loo = rows("leave_one_out.csv")
lv = [float(r["share_outside_all_zones_rounded"]) for r in loo]
need("leave-one-out range", f"{100 * min(lv):.1f}–{100 * max(lv):.1f}%")

# ---------------------------------------------------------------- construction year (by_year.csv)
by = {(r["year_band"], r["map_status"]): r for r in rows("by_year.csv")}
if any(r["dwellings"] == "<5" for r in by.values()):
    bad.append("by_year.csv has suppressed cells: the year figures below cannot be checked")
else:
    tot = sum(int(r["dwellings"]) for r in by.values())
    same("by_year total", tot, n)

    def band(b, statuses=None):
        return sum(int(r["dwellings"]) for (bd, s), r in by.items() if bd == b and (statuses is None or s in statuses))
    sn = ("SNCZI T100 or T10", "SNCZI T500 (not T100)")
    b17, b25 = band("2017-2024"), band("2025 or later")
    need("built 2017-2024", f"{f(b17)} dwellings")
    need("root row: built 2017-2024", f"and {f(b17)} were in buildings dated 2017–2024", ROW)
    need("built 2025 or later", f(b25))
    need("2017-2024 outside every zone", f(band("2017-2024", ("outside every official zone",))))
    need("2017-2024 in an SNCZI zone", f(band("2017-2024", sn)))
    need("2017-2024 in the 100-year zone", f(band("2017-2024", sn[:1])))
    need("2017 or later in all", f(b17 + b25), PAPER)
    need("2017-2024 share in SNCZI", f"{100 * band('2017-2024', sn) / b17:.0f}%", PAPER)

# ---------------------------------------------------------------- places and the pilot
mun = {r["municipality"]: r for r in rows("municipalities.csv")}
for nm in ("Paiporta", "Picanya", "Sedaví"):
    need(f"{nm} share outside", pct(mun[nm]["share_outside_all_zones"]))
need("municipalities touched", f"{P['municipalities_touched']} municipalities")
pil = S["paiporta_pilot_recomputed"]
need("Paiporta pilot dwellings", f"{f(pil['aoi01_first']['dwellings_in_extent'])} of {f(pil['dwellings_total'])}")
need("Paiporta pilot post-2016", f"{pil['aoi01_first']['dwellings_2017_or_later']} dwellings in {pil['aoi01_first']['buildings_2017_or_later']} buildings")

if bad:
    print("\nMISMATCHES:")
    for b in bad:
        print(" -", b)
    sys.exit(1)
print("\nall headline numbers check out")
