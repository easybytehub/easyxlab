#!/usr/bin/env python3
"""Assert the headline numbers of README.md (and paper.md, when present) against data/.

The numbers are recomputed from the per-lot table data/lots.csv and the per-notice table
data/notices.csv where possible; the frozen-parser comparison is read from
data/d1_comparison.csv. summary.json and the other CSVs are cross-checked. Each expected string
must appear in the documents with number boundaries (so "4 of 30" cannot match "14 of 306");
whitespace, including line breaks, is collapsed before comparing. Exit 1 on any mismatch.

paper.md is not in the public package: when it is absent, only README.md is checked.
"""
import csv
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

R = Path(__file__).resolve().parent.parent
D = R / "data"
PAPER_URL = "https://easybyte.es/lab/studies/s14/paper/"
RULES = ("primary", "two_letters", "lenient", "faq_3_2_e", "strict_exempt")


def wilson(k, n, z=1.96):
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return f"{100 * max(0, c - h):.1f}–{100 * min(1, c + h):.1f}"


def f(n):
    return f"{n:,}"


def pc(k, n):
    return f"{100 * k / n:.1f}%"


def rows(name):
    return list(csv.DictReader(open(D / name, encoding="utf-8")))


def flat(s):
    return re.sub(r"\s+", " ", s)


docs = {"README.md": flat((R / "README.md").read_text(encoding="utf-8"))}
if (R / "paper.md").exists():
    docs["paper.md"] = flat((R / "paper.md").read_text(encoding="utf-8"))
else:
    print(f"paper.md is not in the public package: the paper is at {PAPER_URL}")
bad = []
BOTH = ("README.md", "paper.md")


def need(label, text, where=BOTH):
    print(f"{label}: {text}")
    rx = re.compile(r"(?<![\d.,])" + re.escape(text) + r"(?![\d])")
    for w in where:
        if w in docs and not rx.search(docs[w]):
            bad.append(f"{w} does not contain «{text}» ({label})")


lots = rows("lots.csv")
kept = [x for x in lots if x["scope"] != "drop"]
cov = [x for x in kept if x["scope"] == "covered"]
S = json.load(open(D / "summary.json", encoding="utf-8"))
P = "rating_stated_primary"

# 1. headline (primary rule)
no = sum(x[P] == "no" for x in cov)
n = len(cov)
need("headline", f"{no} of {n} covered lots")
need("headline share and CI", f"{pc(no, n)}, 95% CI {wilson(no, n)}%")
if (S["headline"]["without_label"], S["headline"]["covered"]) != (no, n):
    bad.append("summary.json headline disagrees with lots.csv")
for x in cov:
    if (x[P] == "yes") != (x["energy_status"] == "rating") or x["label_included"] != x[P]:
        bad.append(f"lots.csv: inconsistent primary rule for {x['lot_key']}")

# 2. population
off_kept = sorted({x["boe_id"] for x in kept})
need("candidate notices", f"{len(rows('notices.csv'))} candidate notices")
need("sale notices kept (README)", f"{len(off_kept)} sale notices", ("README.md",))
need("sale notices kept (paper)", f"{len(off_kept)} notices", ("paper.md",))
need("lots kept", f"{f(len(kept))} lots")
need("lots not covered", f"{f(len(kept) - n)} lots", ("README.md",))
removed = S["offer_notices"] - len(off_kept)
need("offer notices removed in the review", f"review removed {removed}", ("paper.md",))
if S["lots_kept"] != len(kept) or S["offer_notices_kept"] != len(off_kept):
    bad.append("summary.json population disagrees")
sc = Counter(x["scope"] for x in kept)
reason = Counter(x["scope_reason"] for x in kept)
need("land lots", f"{f(reason['land: not a building (art. 2.h)'])} are land", ("paper.md",))
need("garages", f"{reason['garage or storage room (MITECO FAQ v6.0 no. 14)']} are garages", ("paper.md",))
need("declared exempt", f"{reason['declared exempt by the seller']} were declared exempt", ("paper.md",))
ind = reason["industrial/agricultural non-residential (art. 3.2.c)"] + reason["defence non-residential (art. 3.2.c)"]
need("industrial", f"{ind} are industrial", ("paper.md",))
need("undeterminable", f"{sc['undeterminable']} are undeterminable", ("paper.md",))
need("covered", f"{n} are covered", ("paper.md",))

# 3. by seller group
by = {}
for x in cov:
    by.setdefault(x["seller_group"], Counter())[x[P]] += 1
names = {"TGSS": "TGSS", "Patrimonio del Estado (DEH)": "Hacienda", "INVIED (Defensa)": "INVIED",
         "GIESE (Interior)": "GIESE", "FOGASA": "FOGASA", "Port authorities": "port authority"}
for g, label in names.items():
    c = by[g]
    k, m = c["no"], c["no"] + c["yes"]
    txt = f"{k} of {m} ({pc(k, m)})" if m >= 10 else f"{k} of {m}"
    need(f"{label} lots without the rating", txt)
    sb = S["by_seller"][g]
    if (sb["without_label"], sb["covered"]) != (k, m):
        bad.append(f"summary.json by_seller {g} disagrees")
csv_by = {r["seller_group"]: r for r in rows("by_seller.csv")}
if int(csv_by["ALL"]["without_label"]) != no or int(csv_by["ALL"]["covered"]) != n:
    bad.append("by_seller.csv ALL disagrees")
for g, r in csv_by.items():
    if g != "ALL" and g in names and int(r["covered"]) >= 10:
        k, m = int(r["without_label"]), int(r["covered"])
        need(f"{names[g]} table row", f"| {m} | {k} | {100 * k / m:.1f} | {wilson(k, m)} |", ("README.md",))

# 4. notice level
nl = [x for x in rows("notices.csv") if x["notice_label"]]
c = Counter(x["notice_label"] for x in nl)
need("notices with covered lots", f"{len(nl)} notices with at least one covered lot")
need("notices with the rating in none of their covered lots", f"{c['none']} of them")
for g, label in (("TGSS", "TGSS"), ("Patrimonio del Estado (DEH)", "Hacienda")):
    gg = [x for x in nl if x["seller_group"] == g]
    cg = Counter(x["notice_label"] for x in gg)
    need(f"{label} notices with the rating in all covered lots", f"{cg['all']} of its {len(gg)} notices")

# 5. rules (recomputed from lots.csv)
sens = {r["measure"]: r for r in rows("sensitivity.csv")}
for rule in RULES:
    col = f"rating_stated_{rule}"
    pop = [x for x in kept if x["scope"] == "covered" or x[col] == "no"]
    k = sum(x[col] == "no" for x in pop)
    if (int(sens[rule]["without_label"]), int(sens[rule]["covered"])) != (k, len(pop)):
        bad.append(f"sensitivity.csv {rule} disagrees with lots.csv")
    if rule != "primary":
        need(f"rule {rule}", f"{k} of {len(pop)}")
d = sens["distinct_properties"]
need("distinct properties", f"{d['without_label']} of {d['covered']}")

# 6. the frozen parser (deviation D1)
d1 = {r["parser"]: r for r in rows("d1_comparison.csv")}
fz = d1["frozen parser (without D1)"]
k, m = int(fz["without_label"]), int(fz["covered"])
need("frozen parser headline", f"{k} of {m} ({pc(k, m)})")
added = no - k
inv_d1 = int(d1["frozen parser: INVIED (Defensa)"]["without_label"])
need("lots without the rating added by D1", f"{by['INVIED (Defensa)']['no'] - inv_d1} lots without the rating")
if added != by["INVIED (Defensa)"]["no"] - inv_d1:
    bad.append("D1: the added lots are not all INVIED; the documents say they are")
need("INVIED with the frozen parser", f"{inv_d1} lots without the rating", ("paper.md",))
if (S["d1"]["frozen_without"], S["d1"]["frozen_covered"]) != (k, m):
    bad.append("summary.json d1 disagrees with d1_comparison.csv")

# 7. declared exemptions and the review
ex = [x for x in kept if x["energy_status"] == "exempt_declared"]
need("declared exemptions", f"{len(ex)} lots")
part = sum(1 for x in ex if x["exempt_ground"] == "3.2.e_part")
need("3.2.e claimed for parts of buildings", f"{part} of them")
r1 = [x for x in lots if x["reviewed"] == "yes" and x["review_set"] == "R1" and x["auto_scope"] == "covered"]
conf = sum(1 for x in r1 if x["scope"] == "covered" and x[P] == "no")
need("R1 confirmed", f"{conf} of the {len(r1)}", ("paper.md",))
need("independent re-reading", "40 of 40")

if bad:
    print("\nFAIL:\n  " + "\n  ".join(bad))
    sys.exit(1)
print("\nOK: every headline number matches data/ and appears in " + " and ".join(docs))
