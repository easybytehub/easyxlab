#!/usr/bin/env python3
"""Assert every headline number of README.md (and paper.md, when present) against data/.

The numbers are recomputed from the published CSVs (categories.csv, h1_tourist_numbers.csv,
national_numbers.csv, signals.csv, nyc.csv) and diagnostics.json, not copied from
summary.json; summary.json is cross-checked. Each expected string must appear in the
documents (whitespace, including line breaks, is collapsed before comparing).
Exit 1 on any mismatch."""
import csv, json, math, re, sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
D = R / "data"
PAPER_URL = "https://easybyte.es/lab/studies/s11/paper/"
SPAIN6 = ("barcelona", "girona", "valencia", "malaga", "sevilla", "madrid")


def wilson(k, n, z=1.96):
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return f"{100 * max(0, c - h):.1f}–{100 * (c + h):.1f}"


def rnd(x):
    """round half up (Python's round() rounds 44.5 to 44)"""
    return int(math.floor(x + 0.5))


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


def need(label, text, where=("README.md", "paper.md")):
    print(f"{label}: {text}")
    for w in where:
        if w in docs and text not in docs[w]:
            bad.append(f"{w} does not contain «{text}» ({label})")


cat = rows("categories.csv")


def c(area, snap, pop, category):
    r = [x for x in cat if x["area"] == area and x["snapshot"] == snap and x["population"] == pop and x["category"] == category]
    return int(r[0]["n"]), int(r[0]["denominator"])


snaps = {}
for x in cat:
    snaps.setdefault(x["area"], set()).add(x["snapshot"])
before = {a: min(s) for a, s in snaps.items()}
after = {a: max(s) for a, s in snaps.items()}
S = json.load(open(D / "summary.json", encoding="utf-8"))
diag = json.load(open(D / "diagnostics.json", encoding="utf-8"))

# 1. listings parsed
tot = sum(c(a, s, "all", "empty")[1] for a in snaps for s in snaps[a])
need("listings parsed", f(tot), ("README.md",))
if tot != S["listings_total"]:
    bad.append("summary.json listings_total disagrees")

# 2. H1: tourist-dwelling numbers against the registries, per area (June) and pooled.
#    Categories: in registry / other municipality / registered dwelling in a wrong form
#    (post-review rules) / not found (residual). The frozen rule's "not found" = last two.
h1 = rows("h1_tourist_numbers.csv")
for period, snapmap in (("after", after), ("before", before)):
    sh = nf = oth = wf = 0
    for r in h1:
        if r["snapshot"] != snapmap[r["area"]]:
            continue
        n, k = int(r["shown"]), int(r["not_found"])
        o, i, w = int(r["in_registry_other_municipality"]), int(r["in_registry"]), int(r["registered_wrong_form"])
        if i + o + w + k != n:
            bad.append(f"h1 {r['area']} {r['snapshot']}: the four categories do not add up to 'shown'")
        if int(r["not_found_frozen_rule"]) != w + k:
            bad.append(f"h1 {r['area']} {r['snapshot']}: frozen-rule not-found != wrong form + not found")
        sh, nf, oth, wf = sh + n, nf + k, oth + o, wf + w
        if period == "after":
            need(f"{r['area']} table row", f"| {f(n)} | {f(i)} ({pc(i, n)}) | {f(o)} ({pc(o, n)}) | {f(w)} ({pc(w, n)}) | {f(k)} ({pc(k, n)}, {wilson(k, n)}) |", ("README.md",))
    p = S[f"h1_pooled_{period}"]
    if (p["shown"], p["not_found"], p["in_registry_other_municipality"], p["registered_wrong_form"]) != (sh, nf, oth, wf):
        bad.append(f"summary.json h1_pooled_{period} disagrees with h1_tourist_numbers.csv")
    if period == "after":
        need("pooled not found (residual), June", f"{f(nf)} of {f(sh)}")
        need("pooled share and CI, June", f"{pc(nf, sh)}, 95% CI {wilson(nf, sh)}%")
        need("pooled wrong form, June", f"{f(wf)} ({100 * wf / sh:.1f}%, CI {wilson(wf, sh)}%)")
        need("pooled other municipality, June", f"{f(oth)} ({100 * oth / sh:.1f}%)", ("README.md",))
        need("pooled not found under the frozen rules, June", f"{f(nf + wf)} of {f(sh)} ({pc(nf + wf, sh)})")
        need("wrong form expected by chance", f"About {rnd(p['wrong_form_expected_by_chance'])}", ("README.md",))
    else:
        need("pooled not found, March", f"{f(nf)} of {f(sh)}, {100 * nf / sh:.1f}%", ("README.md",))
        need("pooled not found under the frozen rules, March", f"{f(nf + wf)}, {100 * (nf + wf) / sh:.1f}%", ("README.md",))

# 3. Barcelona
r = [x for x in h1 if x["area"] == "barcelona" and x["snapshot"] == after["barcelona"]][0]
k, n, w = int(r["not_found"]), int(r["shown"]), int(r["registered_wrong_form"])
need("Barcelona not found (residual)", f"{f(k)} of {f(n)} ({pc(k, n)}, CI {wilson(k, n)}%)")
need("Barcelona wrong form", f"{f(w)} ({pc(w, n)}) in a wrong form")
need("Barcelona under the frozen rules", f"{f(k + w)} of {f(n)} ({pc(k + w, n)})")
rt = diag["room_type_by_h1_category"][f"barcelona {after['barcelona']}"]
rooms = rt.get("not_found | Private room", 0)
need("Barcelona private rooms among residual not found", f"{f(rooms)} of the {f(k)}")
# rule-by-rule table (June)
for rule, label in (("R1", "Catalan control digit"), ("R2", "province code"), ("R3", "Málaga extra digit")):
    m = sum(int(x[f"wrong_form_{rule}"]) for x in h1 if x["snapshot"] == after[x["area"]])
    e = sum(float(x[f"wrong_form_{rule}_expected_by_chance"]) for x in h1 if x["snapshot"] == after[x["area"]])
    need(f"rule {rule}", f"| {label} | {m} | ≈ {rnd(e)} |", ("README.md",))

# 4. in-range chance-match statements
cm = diag["chance_match"]
g = lambda a, k="in_range_chance_match_pct": cm[f"{a} {after[a]}"][k]
need("Sevilla in-range chance match", f"{rnd(g('sevilla'))}%")
need("Barcelona/Málaga in-range chance match", f"{math.floor(min(g('barcelona'), g('malaga')))}–{math.floor(max(g('barcelona'), g('malaga')))}%", ("README.md",))
need("València/Girona in-range chance match", f"{math.floor(min(g('valencia'), g('girona')))}–{math.ceil(max(g('valencia'), g('girona')))}%", ("README.md",))
need("full-format chance match", f"Sevilla {g('sevilla', 'full_format_chance_match_pct')}%, Barcelona {g('barcelona', 'full_format_chance_match_pct')}%", ("README.md",))

# 5. annulled national number only, and Exempt statements, six Spanish areas
nat_rows = rows("national_numbers.csv")
for period, snapmap in (("before", before), ("after", after)):
    k = sum(c(a, snapmap[a], "active", "national_tu_only")[0] for a in SPAIN6)
    n = sum(c(a, snapmap[a], "active", "national_tu_only")[1] for a in SPAIN6)
    need(f"national TU only, {period}", f"{f(k)} of {f(n)} ({pc(k, n)})", ("README.md",))
    ex = sum(int(x["regional_exempt_statement"]) for x in nat_rows if x["snapshot"] == snapmap[x["area"]])
    need(f"regional Exempt statements, {period}", f"{f(ex)} ({pc(ex, n)})", ("README.md",))
    sp = S[f"spain_{period}"]
    if (sp["active"], sp["national_tu_only"]["n"], sp["regional_exempt_statement"]["n"]) != (n, k, ex):
        bad.append(f"summary.json spain_{period} disagrees")

# 6. Madrid (frozen H3): national NT number and no regional number
k, n = c("madrid", after["madrid"], "active", "non_tourist")
need("Madrid non-tourist", f"{f(k)} of {f(n)} active listings ({pc(k, n)})")
sig = [x for x in rows("signals.csv") if x["area"] == "madrid" and x["snapshot"] == after["madrid"] and x["category"] == "non_tourist"][0]
if int(sig["n"]) != k:
    bad.append("signals.csv non_tourist differs from categories.csv")
s4 = int(sig["min_nights_le4"])
need("Madrid non-tourist accepting 1-4 nights", f"{f(s4)} of them ({pc(s4, k)})", ("README.md",))
need("Madrid non-tourist accepting 1-4 nights (paper)", f"{f(s4)} ({pc(s4, k)}", ("paper.md",))
# secondary, post-freeze row: every listing showing an NT number
nat = [x for x in nat_rows if x["area"] == "madrid" and x["snapshot"] == after["madrid"]][0]
sec = [x for x in rows("signals.csv") if x["area"] == "madrid" and x["snapshot"] == after["madrid"] and x["category"] == "shows_NT_number"][0]
if int(sec["n"]) != int(nat["national_NT"]):
    bad.append("signals.csv shows_NT_number differs from national_numbers.csv")
need("Madrid secondary (any NT number)", f"{f(int(sec['n']))} of {f(int(nat['active']))}", ("paper.md",))

# 7. New York
ex, n = c("nyc", after["nyc"], "active_short_stay", "exempt")
need("NYC Exempt", f"{f(ex)} of {f(n)} active short-stay listings ({pc(ex, n)})")
ny = [x for x in rows("nyc.csv") if x["snapshot"] == after["nyc"]][0]
need("NYC listings linked by OSE showing the same number", f"{f(int(ny['linked_same_number']))} of {f(int(ny['listings_linked_by_ose']))}")

if bad:
    print("\nFAIL:\n  " + "\n  ".join(bad))
    sys.exit(1)
print("\nOK: every headline number matches data/ and appears in " + " and ".join(docs))
