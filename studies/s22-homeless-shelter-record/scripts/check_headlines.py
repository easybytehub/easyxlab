#!/usr/bin/env python3
"""S22: assert every headline number of README.md (and paper.md, when present) against data/.

Each number is recomputed from the published files in data/ (specialisation.csv, decomposition.csv,
sensitivity.csv, revision_2024.csv, long_series.csv, reception_link.csv, strategy_indicator.csv,
predictions_2026_spec.json), formatted the way the text writes it, and searched for in each document
with whitespace (including line breaks) collapsed. A missing paper.md is not an error: only README.md
is checked then. Exit 1 on any mismatch.
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
D = R / "data"


def load(name):
    with open(D / name, encoding="utf-8") as f:
        return json.load(f) if name.endswith(".json") else list(csv.DictReader(f))


def flat(s):
    return re.sub(r"\s+", " ", s)


def num(x):
    return f"{int(round(float(x))):,}"


def pct(x, sign=True):
    s = f"{float(x):+.1f}%" if sign else f"{float(x):.1f}%"
    return s.replace("-", "−")


docs = {"README.md": flat((R / "README.md").read_text(encoding="utf-8"))}
if (R / "paper.md").exists():
    docs["paper.md"] = flat((R / "paper.md").read_text(encoding="utf-8"))
else:
    print("paper.md not present: checking README.md only")
bad = []


def need(label, text, where=("README.md", "paper.md")):
    print(f"{label}: {text}")
    for w in where:
        if w in docs and text not in docs[w]:
            bad.append(f"{w} does not contain «{text}» ({label})")


spec = {(r["edition"], r["segment"]): r for r in load("specialisation.csv")}
S = lambda e, s, k: float(spec[(str(e), s)][k])

# 1. The record and its composition -----------------------------------------------------------
t0, t1 = S(2022, "ALL", "occupied_mean"), S(2024, "ALL", "occupied_mean")
i0, i1 = S(2022, "IMM", "occupied_mean"), S(2024, "IMM", "occupied_mean")
need("total 2022", num(t0)); need("total 2024", num(t1)); need("total growth", pct(100 * (t1 / t0 - 1)))
need("total change", num(t1 - t0))
need("IMM 2022", num(i0)); need("IMM 2024", num(i1)); need("IMM change", num(i1 - i0))
need("IMM share of change", pct(100 * (i1 - i0) / (t1 - t0), sign=False))
c0 = S(2022, "GBV", "occupied_mean") + S(2022, "OTH", "occupied_mean")  # INE rounds means: the segments,
c1 = S(2024, "GBV", "occupied_mean") + S(2024, "OTH", "occupied_mean")  # not total − IMM, define the core
need("core 2022", num(c0), where=("paper.md",)); need("core 2024", num(c1), where=("paper.md",)); need("core growth", pct(100 * (c1 / c0 - 1)))
cc0 = S(2022, "GBV", "accommodation_centres") + S(2022, "OTH", "accommodation_centres")
cc1 = S(2024, "GBV", "accommodation_centres") + S(2024, "OTH", "accommodation_centres")
need("core accommodation centres growth", pct(100 * (cc1 / cc0 - 1)))
need("core per-centre growth", pct(100 * ((c1 / cc1) / (c0 / cc0) - 1)))
need("all centres 2022", num(S(2022, "ALL", "centres"))); need("all centres 2024", num(S(2024, "ALL", "centres")))
need("all centres growth", pct(100 * (S(2024, "ALL", "centres") / S(2022, "ALL", "centres") - 1)))

# 2. Four-way split -----------------------------------------------------------------------------
dec = [r for r in load("decomposition.csv") if r["from"] == "2022"][0]
for k in ("split_IMM_centres", "split_IMM_per_centre", "split_core_centres", "split_core_per_centre"):
    need(k, num(dec[k]))

# 3. Revision of the 2024 release ---------------------------------------------------------------
rev = {r["indicator"]: r for r in load("revision_2024.csv")}
need("first-published total", num(rev["occupied_mean"]["original_2025_09_26"]))
need("first-published growth", pct(float(rev["occupied_change_pct"]["original_2025_09_26"])))
need("revision size", num(rev["occupied_mean"]["difference"]))
assert rev["occupied_mean"]["difference"] == rev["imm_occupied_mean"]["difference"], "revision not all IMM"

# 4. Sensitivity --------------------------------------------------------------------------------
sens = {r["variant"].split(" ")[0]: r for r in load("sensitivity.csv")}
need("S1 first vintage IMM share", pct(sens["S1"]["IMM_share_of_change_pct"], sign=False))
need("S2 places IMM share", pct(sens["S2"]["IMM_share_of_change_pct"], sign=False))
need("S5 base 2020 IMM share", pct(sens["S5"]["IMM_share_of_change_pct"], sign=False))
need("S9 2020-2022 IMM share", pct(sens["S9"]["IMM_share_of_change_pct"], sign=False), where=("paper.md",))
need("S4 OTH-only per centre", pct(sens["S4"]["core_per_centre_growth_pct"]), where=("paper.md",))
need("S6a June", pct(sens["S6a"]["total_growth_pct"])); need("S6b December", pct(sens["S6b"]["total_growth_pct"]))
need("S7 without Canary Islands", pct(sens["S7"]["total_growth_pct"]), where=("paper.md",))

# 5. Long series --------------------------------------------------------------------------------
ls = [r for r in load("long_series.csv")]
per = [float(r["occupied_per_accommodation_centre"]) for r in ls if int(r["edition"]) <= 2022]
need("per centre min 2012-2022", f"{min(per):.1f}", where=("paper.md",)); need("per centre max 2012-2022", f"{max(per):.1f}", where=("paper.md",))
need("per centre 2024", f"{float(ls[-1]['occupied_per_accommodation_centre']):.1f}", where=("paper.md",))

# 6. Reception system ---------------------------------------------------------------------------
rl = {r["edition"]: r for r in load("reception_link.csv")}
for e in ("2020", "2022", "2024"):
    need(f"IMM places as % of reception {e}", pct(rl[e]["imm_places_as_pct_of_reception_places"], sign=False))
g = lambda a, b: 100 * (float(b) / float(a) - 1)
need("reception growth", pct(g(rl["2022"]["reception_places_yearend"], rl["2024"]["reception_places_yearend"])), where=("paper.md",))
need("arrivals growth", pct(g(rl["2022"]["arrivals_land_sea"], rl["2024"]["arrivals_land_sea"])))
need("asylum first-time growth", pct(g(rl["2022"]["asylum_applicants_first"], rl["2024"]["asylum_applicants_first"])), where=("paper.md",))
need("IMM places growth", pct(g(rl["2022"]["imm_places_mean"], rl["2024"]["imm_places_mean"])), where=("paper.md",))

# 7. Strategy indicator -------------------------------------------------------------------------
st = {r["edition"]: r for r in load("strategy_indicator.csv")}
need("coverage baseline (Dec 2020)", pct(st["2020"]["coverage_december_pct"], sign=False))
need("coverage 2022 mean", pct(st["2022"]["coverage_mean_pct"], sign=False), where=("paper.md",))
need("coverage 2024 mean", pct(st["2024"]["coverage_mean_pct"], sign=False), where=("paper.md",))
need("coverage 2024 without IMM", pct(st["2024"]["coverage_mean_without_imm_pct"], sign=False))

# 8. Predictions --------------------------------------------------------------------------------
sp = load("predictions_2026_spec.json")
lo, hi = sp["P1_core_per_centre_log_change"]["A_bounds_occupied_per_centre"]
need("P1 bounds", f"{lo:.2f} to {hi:.2f}", where=("paper.md",))
need("core per centre 2024", f"{sp['baseline_2024']['core_occupied_per_centre']:.2f}", where=("paper.md",))
need("core occupancy 2024", pct(sp["baseline_2024"]["core_occupancy_pct"], sign=False), where=("paper.md",))
assert math.isclose(sp["in_sample_2022_2024"]["abs_imm_change"], i1 - i0)

# 9. Added after the review -------------------------------------------------------------------
sm = load("summary.json")
h = sm["headline"]
need("IMM centres term range", f"{num(h['IMM_centres_term_min'])}–{num(h['IMM_centres_term_max'])}")
need("IMM per-centre term range", f"{num(h['IMM_per_centre_term_min'])}–{num(h['IMM_per_centre_term_max'])}")
need("core centres term range", f"{num(h['core_centres_term_min'])}–{num(h['core_centres_term_max'])}", where=("paper.md",))
need("core per-centre term range", f"{num(h['core_per_centre_term_min'])}–{num(h['core_per_centre_term_max'])}", where=("paper.md",))
need("GBV per centre change", pct(100 * (h["GBV_per_centre_1"] / h["GBV_per_centre_0"] - 1)))
need("OTH per centre change", pct(100 * (h["OTH_per_centre_1"] / h["OTH_per_centre_0"] - 1)))
need("core by segment, centres", num(h["core_centres_term_by_segment"]), where=("paper.md",))
need("core by segment, per centre", num(h["core_per_centre_term_by_segment"]), where=("paper.md",))
need("per-centre span low", pct(sens["S2"]["core_per_centre_growth_pct"]))
need("per-centre span high", pct(sens["S4c"]["core_per_centre_growth_pct"]))
rs = sm["revision_split"]
need("revision booked per centre", num(rs["added_to_per_centre_term"]))
need("revision booked as centres", num(rs["added_to_centres_term"]), where=("paper.md",))
cn = sm["canary"]
need("Canary June 2024", num(cn["jun_2024"])); need("Canary December 2024", num(cn["dec_2024"]))
need("Canary share of June-December gap", pct(cn["share_of_jun_dec_gap_pct"], sign=False))
r = sm["reception"]
for k in ("imm_places_growth_20_22", "sapi_growth_20_22", "humanitarian_growth_20_22", "reception_growth_20_22",
          "asylum_first_growth_20_22", "arrivals_growth_20_22", "sapi_growth_22_24", "humanitarian_growth_22_24"):
    need(k, pct(r[k]), where=("paper.md",))
need("coverage 2022 December", pct(st["2022"]["coverage_december_pct"], sign=False))
need("coverage 2024 December", pct(st["2024"]["coverage_december_pct"], sign=False))
d1 = sp["deviation_D1_2026_10_04"]
need("OTH P1 baseline", f"{d1['oth_baseline_2024']['occupied_per_centre']:.2f}", where=("paper.md",))
dry = load("score_dryrun.json")
need("dry-run q1", f"{dry['q1']:+.3f}", where=("paper.md",)); need("dry-run q1_oth", f"{dry['q1_oth']:+.3f}", where=("paper.md",))
reg = {(r["edition"], r["region"]): r for r in load("regions.csv")}
need("Navarre 2024 places (revised)", num(reg[("2024", "Navarre")]["places_mean"]))

if bad:
    print("\nMISMATCHES:")
    for b in bad:
        print("  " + b)
    sys.exit(1)
print("\nall headline numbers found")
