#!/usr/bin/env python3
"""S12: assert every headline number of README.md (and paper.md, when present) against data/.

Each number is recomputed from the published files in data/ (province_quarter.csv, districts.csv,
cgpj_notes.csv, tests.csv, h5_years.csv, dq_summary.json, pooled_model.json, summary.json), formatted
the way the text writes it, and searched for in each document (whitespace, including line breaks,
collapsed). The verdict of each hypothesis must appear in its row of the results table. A missing
paper.md is not an error: only README.md is checked then. Exit 1 on any mismatch.
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


def minus(s):
    return s.replace("-", "−")


def num(x):
    return f"{int(round(x)):,}"


def pct(x, d=1, sign=True):
    s = f"{100 * x:+.{d}f}%" if sign else f"{100 * x:.{d}f}%"
    return minus(s)


def coef(b):
    return minus(f"{b:+.2f}")


def pv(p, d=2):
    return f"{p:.{d}f}"


docs = {"README.md": flat((R / "README.md").read_text(encoding="utf-8"))}
if (R / "paper.md").exists():
    docs["paper.md"] = flat((R / "paper.md").read_text(encoding="utf-8"))
else:
    print("paper.md not present: checking README.md only")
raw_docs = {k: (R / k).read_text(encoding="utf-8") for k in docs}
bad = []


def need(label, text, where=("README.md", "paper.md")):
    print(f"{label}: {text}")
    for w in where:
        if w in docs and text not in docs[w]:
            bad.append(f"{w} does not contain «{text}» ({label})")


# 1. National figures, Q1-2026 vs Q1-2025 (province series file, TOTAL row) ----------------------
pq = load("province_quarter.csv")
V = {(r["series"], r["province"], r["quarter"]): float(r["value"]) for r in pq if r["value"] != ""}
t1, t0 = "2026Q1", "2025Q1"
for sid, label in (("P-TOT", "practised"), ("SC-REC", "received by common services"),
                   ("SC-POS", "completed by common services")):
    a, b = V[(sid, "TOTAL", t1)], V[(sid, "TOTAL", t0)]
    need(f"{label} Q1-2026", num(a))
    need(f"{label} change", pct(a / b - 1))
need("practised Q1-2025", num(V[("P-TOT", "TOTAL", t0)]))

# 2. Phases --------------------------------------------------------------------------------------
dist = load("districts.csv")
counts = {ph: sum(1 for r in dist if r["phase"] == str(ph)) for ph in (1, 2, 3)}
need("phase 1 districts", f"{counts[1]} districts")
need("phase 2 districts", f"{counts[2]} on 1 October")
need("phase 3 districts", f"{counts[3]} on 31 December")
need("all districts", f"{len(dist)}")

# 3. Registered tests ----------------------------------------------------------------------------
S = load("summary.json")
H1a, H1b, H2, H3, H4, H4d, H5 = (S[k] for k in ("H1a", "H1b", "H2", "H3", "H4", "H4_difference", "H5"))
need("H1a coefficient", f"b3 = {coef(H1a['b'])}")
need("H1a Holm", f"Holm-adjusted p = {pv(H1a['p_holm'])}")
need("H1a permutation", f"permutation p = {pv(H1a['p_perm'], 3)}")
need("H1b coefficient", f"b1 = {coef(H1b['b'])}")
need("H1b p", f"p = {pv(H1b['p_one_sided'])}")
need("H3 coefficient", f"b3 = {coef(H3['b'])}")
need("H3 Holm", f"Holm-adjusted p = {pv(H3['p_holm'], 3)}")
need("H4 difference", coef(H4d["b"]))
need("H4 difference p", f"p = {pv(H4d['p_one_sided'], 3)}")
need("H4 mortgage provinces", f"{H4['n']} provinces")
need("H5 effect", pct(math.exp(H5["delta1"]) - 1, 0))
h5 = {r["year"]: float(r["delta1"]) for r in load("h5_years.csv")}
need("H5 placebo 2024", pct(math.exp(h5["2024"]) - 1, 0))
verdicts = S["verdicts"]
for doc, text in raw_docs.items():
    for h, v in verdicts.items():
        rows = [ln for ln in text.splitlines() if ln.startswith(f"| {h} |")]
        print(f"verdict {h} in {doc}: {v}")
        if not rows or not any(v in ln for ln in rows):
            bad.append(f"{doc}: results-table row for {h} missing or not «{v}»")

# 4. The CGPJ's own notes and the data-quality findings ------------------------------------------
notes = load("cgpj_notes.csv")
q3 = [n for n in notes if n["release"] == "2025Q3"]
need("Q3-2025 estimated districts", f"{len(q3)} districts")
need("of which phase 1", f"{sum(1 for n in q3 if n['phase'] == '1')} of them")
q1 = [n["name_in_note"] for n in notes if n["release"] == "2026Q1"]
need("Q1-2026 districts without data", ", ".join(q1))
dq = load("dq_summary.json")
rev = {(r["quarter"], r["series"]): r for r in dq["DQ2"]["national_revisions"]}
need("Q3-2025 first vintage", num(rev[("2025Q3", "P-TOT")]["first_vintage"]))
need("Q3-2025 latest vintage", num(rev[("2025Q3", "P-TOT")]["latest_vintage"]))
split = dq["DQ4"]["q1_2026_type_split"]["P-LAU"]
need("LAU Q1-2026, release province sheet", num(split["release_provincias_sheet"]))
need("LAU Q1-2026, series", num(split["series_file"]))
rib = [o for o in dq["DQ1"]["outliers"] if o["district"] == "RIBADAVIA"][0]
need("Ribadavia 2025", num(rib["value"]))
dq1 = load("dq1_district_vs_province.csv")
n2025 = len({r["province"] for r in dq1 if r["year"] == "2025" and r["series"] == "P-TOT"})
need("provinces where the district file disagrees in 2025", f"all {n2025} provinces")
need("lowest earlier quarter", num(dq["DQ11"]["previous_minimum"]))
need("lowest earlier first quarter", num(dq["DQ11"]["previous_minimum_first_quarter_value"]), ("paper.md",))

# 5. Pooled model and the out-of-sample test -----------------------------------------------------
pooled = load("pooled_model.json")
if pooled["degenerate"]:
    need("pooled model degenerate", "search bound")
need("Q2-2026 test date", "16 October 2026")

# 6. Checks added after the independent review (data/review_checks.json) -----------------------
rc = load("review_checks.json")
need("next lowest earlier quarter", num(rc["lowest_earlier_quarters"][1]["value"]))
need("S3 as registered", coef(rc["S3_registered"]["b"]))
need("S3 as registered, p", pv(rc["S3_registered"]["p_one_sided"], 3))
pre = rc["placebo_2025Q4_exploratory"]["P-TOT"]
need("in-window placebo Δg(2025Q4)", minus(f"{pre['b']:.3f}"))
need("in-window placebo p", f"p {pv(pre['p_two_sided'], 3)}")
split = rc["delta_g_split"]
need("H2, Q1-2026 part", coef(split["H2"]["g_2026Q1"]["b"]))
need("H3, Q1-2026 part", coef(split["H3"]["g_2026Q1"]["b"]))
m = rc["province_detail"]["MADRID"]["SC-POS"]
need("Madrid completed by services", " → ".join(num(m[q]) for q in ("2024Q4", "2025Q4", "2026Q1")),
     ("README.md",))
need("SC receipts, Q4-2025 year on year", pct(rc["national_yoy"]["SC-REC"]["2025Q4"]))
need("SC receipts, Q4+Q1 pooled", pct(rc["national_yoy_pooled_Q4_Q1"]["SC-REC"]))

# 7. Internal consistency of summary.json with tests.csv -----------------------------------------
tests = {r["test"]: r for r in load("tests.csv")}
for k in ("H1a", "H1b", "H2", "H3", "H4"):
    if abs(float(tests[k]["b"]) - S[k]["b"]) > 1e-5 * max(1.0, abs(S[k]["b"])):  # CSV keeps 6 significant digits
        bad.append(f"summary.json and tests.csv disagree on {k}")

if bad:
    print("\nFAILED:")
    for b in bad:
        print("  " + b)
    sys.exit(1)
print(f"\nall headline numbers found in {', '.join(docs)}")
