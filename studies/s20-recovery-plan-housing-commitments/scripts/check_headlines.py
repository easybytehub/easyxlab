#!/usr/bin/env python3
"""Assert every headline number of README.md (and paper.md, when present) against data/.

The numbers are recomputed here from the published CSVs (housing_rows.csv,
housing_measures.csv, diffs.csv, adoption.csv, requests.csv, council_vs_proposal.csv,
scoreboard_versions.csv, frame.csv) and cross-checked with summary.json. Each expected
string must appear in the documents (whitespace, including line breaks, is collapsed before
comparing). paper.md is optional: when it is absent only README.md is checked.
Exit 1 on any mismatch."""
import csv, datetime, json, re, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

R = Path(__file__).resolve().parent.parent
D = R / "data"
PAPER_URL = "https://easybyte.es/lab/studies/s20/paper/"


def rows(name):
    return list(csv.DictReader(open(D / name, encoding="utf-8")))


def flat(s):
    return re.sub(r"\s+", " ", s)


def pct(a, b):
    v = (Decimal(100) * (Decimal(b) - Decimal(a)) / Decimal(a)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return ("−" if v < 0 else "+") + f"{abs(v)}%"


def day(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def n(x):
    return f"{x:,}"


docs = {"README.md": flat((R / "README.md").read_text(encoding="utf-8"))}
if (R / "paper.md").exists():
    docs["paper.md"] = flat((R / "paper.md").read_text(encoding="utf-8"))
else:
    print(f"paper.md is not in the public package: the paper is at {PAPER_URL}")
bad = []
# The study's row in the repository's README (the headline the site shows), when the study sits in it.
ROOT = R.parent.parent / "README.md"
if ROOT.exists():
    row = [ln for ln in ROOT.read_text(encoding="utf-8").splitlines() if ln.startswith("| [S20](")]
    if len(row) != 1:
        bad.append(f"repository README: {len(row)} rows for S20")
    else:
        docs["root row"] = flat(row[0])
else:
    print("not inside the studies repository: the root-table row is not checked")
ROW = ("root row",)


def need(label, text, where=("README.md", "paper.md")):
    print(f"{label}: {text}")
    for w in where:
        if w in docs and text not in docs[w]:
            bad.append(f"{w} does not contain «{text}» ({label})")


S = json.load(open(D / "summary.json", encoding="utf-8"))
hr, hm, df = rows("housing_rows.csv"), rows("housing_measures.csv"), rows("diffs.csv")
ad = {r["version"]: r for r in rows("adoption.csv")}
labels = list(ad)


def goal(v):
    x = [r for r in hr if r["version"] == v and r["measure"] == "C2.I2" and r["number"] == "31"]
    return int(x[0]["goal"].replace(" ", ""))


def ico(v):
    x = [m for m in hm if m["version"] == v and m["measure"] == "C2.I7"]
    if not x:
        return None
    m = re.search(r"aims at initially providing at least EUR ([\d  ]+)", x[0]["description"])
    return int(re.sub(r"\D", "", m.group(1)))


# 1. versions
need("versions", f"{len(labels)} versions")
assert len(labels) == S["n_versions"]

# 2. target 31
t = {v: goal(v) for v in labels}
assert t[labels[0]] == S["target31_first"] and t[labels[-1]] == S["target31_last"]
need("target 31 first", n(t[labels[0]]))
need("target 31 Dec-2025", n(t["v7-2025d"]))
need("target 31 last", n(t[labels[-1]]))
need("target 31 change", pct(t[labels[0]], t[labels[-1]]))
need("target 31 change Dec-2025", pct(t["v6-2025c"], t["v7-2025d"]), ("paper.md",))
need("target 31 change Aug-2026", pct(t["v8-2026a"], t["v9-2026b"]), ("paper.md",))
assert pct(t[labels[0]], t[labels[-1]]) == "−" + str(abs(Decimal(repr(S["target31_change_pct"]))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) + "%"

# 3. ICO line
i = {v: ico(v) for v in labels}
first = next(v for v in labels if i[v])
need("ICO first (EUR million)", f"€{n(i[first] // 10**6)} million")
need("ICO Dec-2025 (EUR million)", f"€{n(i['v7-2025d'] // 10**6)} million")
need("ICO last (EUR)", f"€{n(i[labels[-1]])}")
need("ICO change", pct(i[first], i[labels[-1]]))
need("ICO change Dec-2025", pct(i["v6-2025c"], i["v7-2025d"]), ("paper.md",))
need("ICO change Aug-2026", pct(i["v8-2026a"], i["v9-2026b"]), ("paper.md",))
assert i[labels[-1]] == S["ico_last"]

# 3b. the root-table row: first and last wording of target 31, and the ICO line
t31 = {v: [r for r in hr if r["version"] == v and r["measure"] == "C2.I2" and r["number"] == "31"][0] for v in labels}
w0, w9 = t31[labels[0]], t31[labels[-1]]
if not (w0["name"].startswith("New dwellings built for social rental or at affordable prices")
        and "construction shall be completed" in w0["description"]):
    bad.append("target 31, first version: not «New dwellings built … construction shall be completed»")
if not w9["description"].startswith("Construction or rehabilitation") or "complet" in w9["description"]:
    bad.append("target 31, last version: not «Construction or rehabilitation» without a completion requirement")
if not ad[labels[-1]]["proposed"].startswith("2026-08"):
    bad.append("the last version is not the proposal of August 2026")
need("root row: first target", f"Spain first committed to the EU to complete {n(t[labels[0]])} new dwellings for social rental or at affordable prices", ROW)
need("root row: last target", f"the August 2026 proposal asks for {n(t[labels[-1]])} under «Construction or rehabilitation», with no completion requirement stated", ROW)
# the base is the first version with an ICO amount (v1-2023, adopted on 17 Oct 2023), and the
# comparison is the version proposed in Dec 2025 and adopted in Jan 2026 (v7); both dates from adoption.csv
if not (ad[first]["status"] == "adopted" and ad[first]["adopted"].startswith("2023-")):
    bad.append(f"ICO base {first}: not a version adopted in 2023")
if not (ad["v7-2025d"]["status"] == "adopted" and ad["v7-2025d"]["adopted"].startswith("2026-01")):
    bad.append("v7-2025d: not adopted in January 2026")
need("root row: ICO line", f"social-housing loan line at the state bank ICO is {pct(i[first], i[labels[-1]]).lstrip('−')} below its {ad[first]['adopted'][:4]} commitment", ROW)
need("root row: ICO line, version adopted in January 2026",
     f"({pct(i[first], i['v7-2025d']).lstrip('−')} below in the version adopted in January 2026)", ROW)

# 4. dates of the two cutting proposals, the requests behind them, adoption
for v in ("v7-2025d", "v9-2026b"):
    need(f"{v} proposed", day(ad[v]["proposed"]))
    need(f"{v} Spain's request", day(ad[v]["spain_request"]))
need("v7 adopted", day(ad["v7-2025d"]["adopted"]))
need("v9 reported adopted", day(ad["v9-2026b"]["adopted"]))
fr = {r["id"]: r for r in rows("frame.csv")}
need("EU housing plan", day(fr["eahp-spain"]["date"]))
n_adopted = sum(1 for v in labels if ad[v]["status"] == "adopted")
need("versions adopted per the Commission's recitals", f"{n_adopted} of the {len(labels)}")

need("Spanish Council of Ministers, simplification addendum", day(fr["es-adenda-simplificacion"]["date"]))
need("last payment request", day(fr["es-pr7"]["date"]))

# 4b. estimated cost of C2.I2 in the Commission's SWDs
mc = {}
for c in rows("measure_costs.csv"):
    if c["measure"] == "C2.I2" and c["eur_million"]:
        mc[c["version"]] = int(float(c["eur_million"]))
for v in ("v6-2025c", "v7-2025d", "v9-2026b"):
    need(f"C2.I2 cost {v}", f"€{n(mc[v])} million")
assert S["swd_cost_eur_m"]["C2.I2"]["v7-2025d"] == mc["v7-2025d"]

# 5. change counts
cons = [d for d in df if d["comparison"] == "consecutive" and d["measure"] in ("C2.I2", "C2.I7", "C2.R3", "C2.R7", "C2.summary")]
need("item-level changes", f"{len(cons)} item-level changes")
assert len(cons) == S["core_changes_consecutive"]
cats = {}
for d in cons:
    for c in d["categories"].split(";"):
        cats[c] = cats.get(c, 0) + 1
need("spacing-only changes", f"{cats['editorial']} of them spacing only")
need("definition changes", f"{cats['definition']} changed the definition", ("paper.md",))
need("quantity changes", f"{cats['quantity']} changed a quantity", ("paper.md",))
need("amount changes", f"{cats['amount']} changed an amount", ("paper.md",))
need("deadline changes", f"{cats['deadline']} changed a deadline", ("paper.md",))
need("removed items", f"{cats['removed']} removed an item", ("paper.md",))

# 5b. base rate of the December 2025 and August 2026 rewrites
B = json.load(open(D / "baseline_summary.json", encoding="utf-8"))
dec, aug = B["v6-2025c->v7-2025d"], B["v8-2026a->v9-2026b"]
bm = rows("baseline_measures.csv")
dm = [r for r in bm if r["from"] == "v6-2025c"]
lost = sum(1 for r in dm if float(r["ratio"]) < 0.7)
assert lost == dec["measures"]["lost_more_than_30pct"] and len(dm) == dec["measures"]["n"]
share = (Decimal(100 * lost) / Decimal(len(dm))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
need("Dec-2025 measures losing >30% (README)", f"{lost} of {len(dm)}", ("README.md",))
need("Dec-2025 measures losing >30% (paper)", f"{lost} ({share}%)", ("paper.md",))
need("Dec-2025 share", f"{share}%")
hous_lost = sum(1 for r in dm if r["housing"] == "True" and float(r["ratio"]) < 0.7)
need("Dec-2025 housing measures losing >30%", f"{hous_lost} of 4", ("README.md",))
br = rows("baseline_rows.csv")
ar = [r for r in br if r["from"] == "v8-2026a"]
alost = sum(1 for r in ar if float(r["ratio"]) < 0.7)
need("Aug-2026 rows losing >30%", f"{alost}, out of {len(ar)}", ("README.md",))
need("Aug-2026 rows losing >30% (paper)", f"{alost} milestones and targets, out of {len(ar)}", ("paper.md",))
assert sorted(r["measure"] + " " + r["number"] for r in ar if float(r["ratio"]) < 0.7 and r["housing"] == "True") == ["C2.I2 31", "C2.I7 L6"]

# 5c. press datelines (from the articles, recorded in prior_work_search.csv)
pw = {r["source"]: r for r in rows("prior_work_search.csv")}
for src, label in (("press: Okdiario 2026-08-09", "9 August 2026"), ("press: El Confidencial 2026-09-06", "6 September 2026")):
    assert src in pw and pw[src]["screened_titles"].startswith("datePublished " + src[-10:]), src
need("Okdiario dateline", "9 August 2026", ("paper.md",))
need("El Confidencial dateline", "6 September 2026")
need("COM(2025) 310 deadline", "by the end of 2025")

# 6. Council texts
cv = rows("council_vs_proposal.csv")
core = [c for c in cv if c["item"].split(" ")[0] in ("C2.I2", "C2.I7", "C2.R3", "C2.R7", "C2.summary")]
same = sum(1 for c in core if c["identical"] in ("yes", "insertions-only"))
need("Council field comparisons", f"{same} of {len(core)}")
assert same == S["council_core_items_identical"] and len(core) == S["council_core_items_compared"]

# 7. scoreboard
sb = {(r["measure"], r["number"]): r for r in rows("scoreboard_versions.csv")}
s31 = sb[("C2.I2", "31")]
assert s31["cid_versions_with_same_text"] == "v9-2026b"
need("scoreboard refresh", s31["scoreboard_last_refresh"].replace("/", "/"), ("paper.md",))
need("scoreboard status of target 31", s31["status"])

if bad:
    print("\nMISMATCHES:")
    for b in bad:
        print(" -", b)
    sys.exit(1)
print("\nall headline numbers found")
