#!/usr/bin/env python3
"""Assert the headline numbers of README.md (and paper.md, when present) against data/, and the
two freeze hashes (data/freeze.json).

Recomputed from the published tables, not read from summary.json, wherever they allow it:
- window sums and changes, the six provinces and the buyer groups, from data/province_quarter.csv;
- placebo-date p-values (planned, spaced, non-overlapping, post hoc), from data/placebo_dates.csv;
- shares by period, the baseline-year numbers and the one-quarter break, from province_quarter.csv;
- the euro's quarterly moves, from data/fx_quarter.csv;
- Portugal, from data/portugal_quarter.csv;
- the exposure slopes, from data/did_windows.csv;
- the predictions, from data/predictions_2026Q3_frozen.csv.
Read from summary.json: the Durbin-Watson statistic and the differenced currency elasticities.
Each expected string must appear in the documents; whitespace, line breaks included, is collapsed
before comparing.

The published numbers belong to MIVAU's release of 1 October 2026 (SHA-256 of table 1.6 below).
If data/ was built from another release, mismatches are listed and the exit code is 0. Otherwise
exit 1 on any mismatch. A freeze-hash mismatch always fails.
"""
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
D = R / "data"
sys.path.insert(0, str(R / "scripts"))
from s21lib import qrange, rank_p, qshift  # noqa: E402

PAPER_URL = "https://easybyte.es/lab/studies/s21/paper/"
PUBLISHED_SHA_1_6 = "1efd447a9ac38e8c252f48c7e6d65f344b85a7677a5986f6b85df9c15851c2cd"
B, A, P = qrange("2023Q2", "2024Q1"), qrange("2024Q2", "2025Q1"), qrange("2025Q2", "2026Q1")
CORE = ["28", "08"]
SIX = ["08", "28", "29", "03", "07", "46"]
BOTH = ("README.md", "paper.md")
RD, PA = ("README.md",), ("paper.md",)


def flat(s):
    return re.sub(r"\s+", " ", s)


def f(n):
    return f"{n:,}"


def sp(x, nd=1):
    """Signed percentage as written in the documents: +24.8% / −35.9%."""
    s = f"{abs(x):.{nd}f}%"
    return ("+" if x > 0 else "−") + s if round(abs(x), nd) != 0 else s


def pc(a, b):
    return 100.0 * (a / b - 1.0)


def rel(ta, tb, ca, cb):
    return 100.0 * ((ta / tb) / (ca / cb) - 1.0)


docs = {"README.md": flat((R / "README.md").read_text(encoding="utf-8"))}
if (R / "paper.md").exists():
    docs["paper.md"] = flat((R / "paper.md").read_text(encoding="utf-8"))
else:
    print(f"paper.md is not in the public package: the paper is at {PAPER_URL}")
bad, hard = [], []


def need(label, text, where=BOTH):
    print(f"{label}: {text}")
    for w in where:
        if w in docs and text not in docs[w]:
            bad.append(f"{w} does not contain «{text}» ({label})")


# ---------------------------------------------------------------- MIVAU table 1.6
pq = {}
for r in csv.DictReader(open(D / "province_quarter.csv", encoding="utf-8")):
    pq[(r["quarter"], r["code"])] = r
provs = sorted({c for _, c in pq if c != "00"})


def tot(codes, qs, g="nres_fx"):
    return sum(int(pq[(q, c)][g]) for q in qs for c in codes)


REST = [c for c in provs if c not in CORE]
OTHER46 = [c for c in provs if c not in SIX]
terr = {"official six provinces": SIX, "the other 46 provinces": OTHER46,
        "Madrid + Barcelona": CORE, "Madrid": ["28"], "Barcelona": ["08"], "Valencia": ["46"],
        "Málaga": ["29"], "Alicante": ["03"], "Spain without Madrid and Barcelona": REST, "Spain": ["00"]}
for name, codes in terr.items():
    b, a, p = tot(codes, B), tot(codes, A), tot(codes, P)
    need(f"window row {name}", f"| {name} | {f(b)} | {f(a)} | {f(p)} | {sp(pc(a, b))} | {sp(pc(p, b))} | {sp(pc(p, a))} |")

cb, ca, cp = tot(CORE, B), tot(CORE, A), tot(CORE, P)
rb, ra, rp = tot(REST, B), tot(REST, A), tot(REST, P)
need("Spain fall", f"{abs(pc(tot(['00'], P), tot(['00'], B))):.1f}%")
need("six against the other 46", f"{abs(pc(tot(SIX, P), tot(SIX, B))):.1f}%, against {abs(pc(tot(OTHER46, P), tot(OTHER46, B))):.1f}%")
need("core two counts", f"{f(cb)} in B to {f(cp)} in P", RD)
need("core two counts (paper)", f"({f(cb)} to {f(cp)})", PA)
need("core two fall", sp(pc(cp, cb)))
need("rest fall", sp(pc(rp, rb)))
need("relative fall", sp(rel(cp, cb, rp, rb)))
need("relative rush", f"({sp(rel(ca, cb, ra, rb))})", RD)
need("Madrid and Barcelona falls", f"Madrid fell {abs(pc(tot(['28'], P), tot(['28'], B))):.1f}% and Barcelona "
     f"{abs(pc(tot(['08'], P), tot(['08'], B))):.1f}%", RD)
need("Valencia fall", f"fell {abs(pc(tot(['46'], P), tot(['46'], B))):.1f}%")
need("Madrid rush", f"Madrid rose {pc(tot(['28'], A), tot(['28'], B)):.1f}%", RD)

labels = {"nres_fx": "foreign non-residents", "res_fx": "foreign residents",
          "nres_es": "Spanish non-residents", "res_es": "Spanish residents", "total": "all buyers"}
for g, where in (("nres_fx", BOTH), ("res_fx", BOTH), ("nres_es", BOTH), ("res_es", BOTH), ("total", PA)):
    t = [tot(CORE, x, g) for x in (B, A, P)]
    c = [tot(REST, x, g) for x in (B, A, P)]
    need(f"group row {g}", f"| {labels[g]} | {sp(rel(t[1], t[0], c[1], c[0]))} | "
         f"{sp(rel(t[2], t[0], c[2], c[0]))} | {sp(rel(t[2], t[1], c[2], c[1]))} |", where)
t = [tot(CORE, x, "total") for x in (B, A, P)]
c = [tot(REST, x, "total") for x in (B, A, P)]
need("all buyers", f"all purchases {sp(rel(t[2], t[0], c[2], c[0]))}", RD)

# ---------------------------------------------------------------- tests fixed in advance
did = {(r["contrast"], r["outcome"], r["exposure"], r["weighted"]): r
       for r in csv.DictReader(open(D / "did_windows.csv", encoding="utf-8"))}
six = did[("P_vs_B", "nres_fx", "six", "1")]
sh = did[("P_vs_B", "nres_fx", "share", "1")]
need("six slope", f"{float(six['slope_log_points']):+.2f} log points")
need("six p", f"p = {float(six['perm_p_two_sided']):.2f}")
need("share slope per 10 pp", f"+{float(sh['slope_log_points']) / 10:.2f} log points per 10 percentage points", RD)
need("share p", f"p = {float(sh['perm_p_two_sided']):.2f}")

# ---------------------------------------------------------------- placebo dates
pl = list(csv.DictReader(open(D / "placebo_dates.csv", encoding="utf-8")))
real = {"rel_rush_pct": rel(ca, cb, ra, rb), "rel_net_pct": rel(cp, cb, rp, rb), "rel_from_rush_pct": rel(cp, ca, rp, ra)}
covid = set(qrange("2020Q1", "2021Q4"))
pv, ps, pc_ = {}, {}, {}
for k, side in (("rel_rush_pct", "upper"), ("rel_net_pct", "lower"), ("rel_from_rush_pct", "lower")):
    pv[k] = rank_p(real[k], [float(r[k]) for r in pl], side)
    ps[k] = rank_p(real[k], [float(r[k]) for r in pl if r["spaced"] == "1"], side)
    clean = [float(r[k]) for r in pl if not set(qrange(qshift(r["announce_q"], -4), qshift(r["announce_q"], 7))) & covid]
    pc_[k] = rank_p(real[k], clean, side)
need("placebo row", f"| placebo p, {len(pl)} planned dates (15 spaced) | {pv['rel_rush_pct']:.2f} ({ps['rel_rush_pct']:.2f}) | "
     f"{pv['rel_net_pct']:.3f} ({ps['rel_net_pct']:.3f}) | {pv['rel_from_rush_pct']:.3f} ({ps['rel_from_rush_pct']:.3f}) |", RD)
need("planned p", f"p = {pv['rel_net_pct']:.3f}")
need("spaced p", f"{ps['rel_net_pct']:.3f}")
need("post hoc p", f"{pc_['rel_net_pct']:.3f}")
need("rush p", f"p = {pv['rel_rush_pct']:.2f}")
nono = ["2010Q2", "2013Q2", "2016Q2", "2019Q2", "2022Q2"]
vals = {r["announce_q"]: float(r["rel_net_pct"]) for r in pl if r["announce_q"] in nono}
p_no = rank_p(real["rel_net_pct"], list(vals.values()), "lower")
need("non-overlapping floor", f"{p_no:.2f}")
need("non-overlapping values", ", ".join(sp(vals[q]) for q in nono[:4]) + f" and {sp(vals[nono[4]])}", PA)
need("paper placebo table, planned", f"| planned: every quarter 2008Q1–2022Q2 (overlapping) | {len(pl)} | {pv['rel_net_pct']:.3f} | {1 / (len(pl) + 1):.3f} |", PA)

# ---------------------------------------------------------------- shares, baseline, break
spain = {q: int(pq[(q, "00")]["nres_fx"]) for q in qrange("2007Q1", "2026Q2")}


def share(codes, a, b):
    qs = qrange(a, b)
    return 100.0 * tot(codes, qs) / sum(spain[q] for q in qs)


per = [("2014Q1", "2017Q4"), ("2018Q1", "2019Q4"), ("2020Q2", "2022Q1"), (B[0], B[-1]), (A[0], A[-1]), (P[0], P[-1])]
for name, codes in (("Madrid", ["28"]), ("Barcelona", ["08"])):
    need(f"share row {name}", "| " + name + " | " + " | ".join(f"{share(codes, a, b):.2f}%" for a, b in per) + " |", RD)
mP, m19 = tot(["28"], P), tot(["28"], qrange("2019Q1", "2019Q4"))
need("Madrid P against 2019", f"{mP} purchases in P")
need("Madrid 2019", f"2019 count ({m19})")
v1819 = pc(share(CORE, P[0], P[-1]), share(CORE, "2018Q1", "2019Q4"))
need("against 2018-2019", f"{abs(v1819):.0f}% lower")
need("against 2018-2019 by city", f"(Madrid {sp(pc(share(['28'], P[0], P[-1]), share(['28'], '2018Q1', '2019Q4')), 0)}, "
     f"Barcelona {sp(pc(share(['08'], P[0], P[-1]), share(['08'], '2018Q1', '2019Q4')), 0)})")
need("against B", f"{abs(pc(share(CORE, P[0], P[-1]), share(CORE, B[0], B[-1]))):.0f}% lower")
lv = {q: math.log(tot(CORE, [q])) - math.log(tot(REST, [q])) for q in ("2025Q1", "2025Q2")}
need("break", f"{abs(100 * (math.exp(lv['2025Q2'] - lv['2025Q1']) - 1)):.1f}%")

# ---------------------------------------------------------------- currency
fx = {}
for r in csv.DictReader(open(D / "fx_quarter.csv", encoding="utf-8")):
    fx.setdefault(r["currency"], {})[r["quarter"]] = float(r["eur_rate"])
for cur in ("USD", "CNY"):
    need(f"euro 2025Q2 against {cur}", f"(+{pc(fx[cur]['2025Q2'], fx[cur]['2025Q1']):.1f}%)" if cur == "USD" else
         f"the yuan (+{pc(fx[cur]['2025Q2'], fx[cur]['2025Q1']):.1f}%)", RD)
    need(f"currency {cur} B to P", f"{pc(sum(fx[cur][q] for q in P), sum(fx[cur][q] for q in B)):.1f}%", PA)
cur = json.load(open(D / "summary.json", encoding="utf-8"))["post_review"]["currency"]
need("Durbin-Watson", f"Durbin–Watson {cur['levels_durbin_watson']:.2f}")
need("differenced elasticities", f"{cur['diff4_elasticity']:+.2f} (SE {cur['diff4_se_hc1']:.2f})", PA)

# ---------------------------------------------------------------- Portugal
pt = {}
for r in csv.DictReader(open(D / "portugal_quarter.csv", encoding="utf-8")):
    if r["region_code"] == "PT" and r["n_transactions"]:
        pt[(r["quarter"], r["domicile_group"])] = int(r["n_transactions"])
lr = {q: math.log(pt[(q, "nonEU")]) - math.log(pt[(q, "EU")]) for q in ("2021Q4", "2022Q1")}
need("Portugal break", f"{abs(lr['2022Q1'] - lr['2021Q4']):.2f} log points")
need("Portugal quarters", "| domiciled outside the EU | " + " | ".join(f(pt[(q, 'nonEU')]) for q in qrange("2021Q2", "2022Q3")) + " |", PA)
PB, PP = qrange("2022Q1", "2022Q4"), qrange("2023Q4", "2024Q3")
need("Portugal 2023 non-EU", f"{pc(sum(pt[(q, 'nonEU')] for q in PP), sum(pt[(q, 'nonEU')] for q in PB)):.1f}% above 2022", PA)
need("Portugal 2023 EU", f"{abs(pc(sum(pt[(q, 'EU')] for q in PP), sum(pt[(q, 'EU')] for q in PB))):.1f}% below", PA)

# ---------------------------------------------------------------- predictions and the freeze
FROZEN = D / "predictions_2026Q3_frozen.csv"
pred = {r["unit"]: r for r in csv.DictReader(open(FROZEN, encoding="utf-8"))}
for u, name in (("28", "Madrid"), ("08", "Barcelona")):
    r = pred[u]
    need(f"prediction {name}", f"{float(r['pred_share_pct']):.2f}% ({float(r['lo90_share_pct']):.2f}–{float(r['hi90_share_pct']):.2f}%", PA)
pm = flat((R / "PREDICTIONS.md").read_text(encoding="utf-8"))
for u, r in pred.items():
    row = f"{float(r['pred_share_pct']):.2f} | {float(r['lo90_share_pct']):.2f}–{float(r['hi90_share_pct']):.2f}"
    if row not in pm:
        bad.append(f"PREDICTIONS.md does not contain «{row}» (unit {u})")
fz = json.load(open(D / "freeze.json", encoding="utf-8"))
blk = re.search(r"<!-- FROZEN-PLAN:BEGIN -->(.*)<!-- FROZEN-PLAN:END -->",
                (R / "METHOD.md").read_text(encoding="utf-8"), re.S).group(1)
plan_sha = hashlib.sha256(blk.encode("utf-8")).hexdigest()
csv_sha = hashlib.sha256(FROZEN.read_bytes()).hexdigest()
print(f"plan sha256 {plan_sha}\nfrozen csv sha256 {csv_sha}")
if plan_sha != fz["plan_sha256"]:
    hard.append("the frozen plan in METHOD.md does not match data/freeze.json")
if csv_sha != fz["frozen_csv_sha256"]:
    hard.append("data/predictions_2026Q3_frozen.csv does not match data/freeze.json")
for h in (plan_sha, csv_sha):
    if h not in pm:
        hard.append(f"PREDICTIONS.md does not record {h}")
need("release date", "16 December 2026")

# ---------------------------------------------------------------- verdict
src = json.load(open(D / "sources.json", encoding="utf-8"))
published = src["mivau"]["files"].get("data/raw/mivau/340101d0.XLS") == PUBLISHED_SHA_1_6
if hard:
    print("\nFREEZE BROKEN:")
    for h in hard:
        print(" -", h)
if bad:
    print("\nMISMATCHES:")
    for b_ in bad:
        print(" -", b_)
if hard or (bad and published):
    sys.exit(1)
if bad:
    print("data/ was built from a release other than 1 October 2026: differences listed, not failing")
else:
    print("\nall headline numbers match data/; freeze hashes verified")
