#!/usr/bin/env python3
"""Assert every number of the README abstract (and the headline figures of paper.md, if present) against data/.

1. Re-derive the cohort from the raw `wp_lastupdate` strings in data/rows.csv with an independent date parser, and
   the classes from row- and file-level data: "available" = outcome ixbrl-esma AND Inline XBRL 1.1 AND an ESMA
   entry point in data/documents.csv; "valid" = zero errors with the ESMA assertions evaluated, read from
   data/documents.csv (not from the row flag). Recompute the Wilson intervals. Compare with data/metrics.json.
2. Build the headline phrases from these recomputed figures and require each one in the README abstract, matched
   on number boundaries.
3. Every number in the README abstract must lie inside a required phrase or a fixed legal/date constant, so that
   changing any number makes the check fail. In paper.md, the headline phrases are required and every "X of N"
   pair must be a known one.
Exit 1 on any mismatch."""
import csv
import datetime as dt
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUTOFF = dt.date(2025, 12, 23)
BITSTAMP = "549300XIBGTJ0PLIEO72"
fail = []


def pdate(s):
    s = (s or "").strip()
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
    if m:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    return dt.date(*map(int, m.groups())) if m else None


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - h), 1), round(100 * (c + h), 1)


def pct(k, n):
    return round(100 * k / n, 1)


rows = list(csv.DictReader(open(ROOT / "data/rows.csv", encoding="utf-8")))
docs = {d["sha256"]: d for d in csv.DictReader(open(ROOT / "data/documents.csv", encoding="utf-8"))}
m = json.loads((ROOT / "data/metrics.json").read_text())

# ---- 1. independent recomputation ----
elig = [r for r in rows if r["excluded_placeholder"] == "0"]
for r in elig:
    d = pdate(r["wp_lastupdate"])
    if int(bool(d and d >= CUTOFF)) != int(r["cohort"]):
        fail.append(f"cohort flag wrong for {r['register']} line {r['csv_line']} ({r['wp_lastupdate']!r})")
coh = [r for r in elig if (pdate(r["wp_lastupdate"]) or dt.date(1, 1, 1)) >= CUTOFF]
ctx = [r for r in elig if r not in coh]


def available(r):
    d = docs.get(r["doc_sha256"])
    # Inline XBRL 1.1; files that could not be re-read for the version check keep their first class (D10)
    ver_ok = r["ix_version"] == "1.1" or (r["ix_version"] == "" and r["ix_version_rechecked"] == "0")
    ok = r["outcome"] == "ixbrl-esma" and ver_ok and d is not None and d["esma_table"] in ("2", "3", "4")
    if (r["outcome"] == "ixbrl-esma") != ok:
        fail.append(f"row {r['register']} {r['csv_line']}: outcome ixbrl-esma not supported by file-level data")
    return ok


def valid(r):
    d = docs[r["doc_sha256"]]
    return d["errors"] == "0" and int(d["assertions_evaluated"] or 0) > 0


N = len(coh)
av = [r for r in coh if available(r)]
va = [r for r in av if valid(r)]
oc = Counter(r["outcome"] for r in coh)
fav = sum(1 for r in coh if r["outcome_frozen_rule"] == "ixbrl-esma")
files, vfiles = len({r["doc_sha256"] for r in av}), len({r["doc_sha256"] for r in va})
ck = [r for r in av if r["ids_checked"] == "1"]
lei_n, lei_k = sum(1 for r in ck if r["lei"]), sum(1 for r in ck if r["lei"] and r["lei_match"] == "1")
dti_n, dti_k = sum(1 for r in ck if r["register_dti"]), sum(1 for r in ck if r["register_dti"] and r["dti_match"] == "1")
prod = Counter(r["producer_domain"] for r in va).most_common(1)[0]
inv = Counter()
for r in av:
    if not valid(r):
        ks = set(json.loads(docs[r["doc_sha256"]]["error_families"] or "{}"))
        inv["assertion-only" if ks == {"assertion"} else "xbrl"] += 1
bs = Counter(r["outcome"] for r in coh if r["lei_casp"] == BITSTAMP)
not_retr = sum(oc[k] for k in ("anti-bot", "robots", "http-error", "net-error"))
ctx_av = sum(1 for r in ctx if r["outcome"] == "ixbrl-esma")

c = m["cohort"]
for name, mine, theirs in [("rows", N, c["rows"]), ("available", len(av), c["available"]), ("valid", len(va), c["valid"]),
                           ("ci", list(wilson(len(av), N)), list(c["available_ci95"])),
                           ("frozen", fav, c["available_frozen_rule"]),
                           ("frozen ci", list(wilson(fav, N)), list(c["available_frozen_rule_ci95"])),
                           ("files", files, c["available_distinct_files"]), ("valid files", vfiles, c["valid_distinct_files"]),
                           ("lei", (lei_k, lei_n), (c["lei_match"], c["lei_rows_with_register_lei"])),
                           ("dti", (dti_k, dti_n), (c["dti_match"], c["dti_rows_with_register_dti"])),
                           ("context", (ctx_av, len(ctx)), (m["context_all_other_rows"]["available"], m["context_all_other_rows"]["rows"]))]:
    if mine != theirs and list(mine) != list(theirs) if isinstance(mine, (list, tuple)) else mine != theirs:
        fail.append(f"metrics.json {name}: {theirs} but data gives {mine}")

lo, hi = wilson(len(av), N)
flo, fhi = wilson(fav, N)
P = {  # required phrases (numbers exactly as they must appear)
    "headline": f"{len(av)} of {N} register rows ({pct(len(av), N)}%; 95% CI {lo}–{hi}%)",
    "distinct files": f"{files} distinct files",
    "frozen rule": f"{fav} of {N} ({pct(fav, N)}%; 95% CI {flo}–{fhi}%)",
    "valid rows": f"{len(va)} of {len(av)} rows",
    "valid files": f"{vfiles} of {files} distinct files",
    "invalid": f"the {len(av) - len(va)} others",
    "assertion-only": f"{inv['assertion-only']} fail only ESMA assertions",
    "xbrl errors": f"{inv['xbrl']} have XBRL or Inline XBRL errors",
    "html": f"no document link ({oc['html']} rows)",
    "pdf": f"a PDF only ({oc['pdf']})",
    "xhtml": f"without any Inline XBRL ({oc['xhtml-no-ixbrl']})",
    "ixbrl 1.0": f"Inline XBRL 1.0 ({oc['ixbrl-1.0']})",
    "not retrievable": f"{not_retr} of {N} rows ended",
    "bitstamp wall": f"an Incapsula wall on {bs['anti-bot']} rows",
    "bitstamp xhtml": f"no XBRL facts on {bs['xhtml-no-ixbrl']} rows",
    "lei": f"{lei_k} of {lei_n}",
    "dti": f"{dti_k} of {dti_n}",
    "producer": f"{prod[1]} of {len(va)} valid rows",
    "context": f"{ctx_av} of {len(ctx)} rows",
}
CONSTANTS = ["23 December 2025", "5 August 2025", "30 September 2026", "2026-10-03", "(EU) 2024/2984", "(EU) 2023/1114",
             "Inline XBRL 1.1", "51 MiCA Q&As", "Q&A 2845",
             "MiCA Art. 6(11), which ties the format standards to the duty of Art. 6(10)",
             "`paper.md` §2", "(D1–D11)"]


def bounded(ph):
    return re.compile(r"(?<![\d.])" + re.escape(ph) + r"(?![\d])")


readme = (ROOT / "README.md").read_text()
abstract = readme.split("## Abstract", 1)[1].split("\n## ", 1)[0] if "## Abstract" in readme else ""
abstract = re.sub(r"\s+", " ", abstract)
if not abstract:
    fail.append("README.md has no '## Abstract' section")
covered = []
for name, ph in P.items():
    hits = list(bounded(ph).finditer(abstract))
    if not hits:
        fail.append(f"README abstract lacks {name}: '{ph}'")
    covered += [h.span() for h in hits]
for ph in CONSTANTS:
    covered += [h.span() for h in bounded(ph).finditer(abstract)]
for mt in re.finditer(r"\d+(?:[.,]\d+)*", abstract):
    if not any(a <= mt.start() and mt.end() <= b for a, b in covered):
        ctx_txt = abstract[max(0, mt.start() - 30):mt.end() + 10].replace("\n", " ")
        fail.append(f"README abstract number '{mt.group()}' is not covered by a checked phrase: …{ctx_txt}…")

paper = ROOT / "paper.md"
if paper.exists():
    t = re.sub(r"\s+", " ", paper.read_text())
    for name in ("headline", "frozen rule", "valid rows", "valid files", "lei", "dti", "producer", "context", "distinct files"):
        if not bounded(P[name]).search(t):
            fail.append(f"paper.md lacks {name}: '{P[name]}'")
    known = set()
    for ph in P.values():
        for a, b in re.findall(r"(\d+) of (\d+)", ph):
            known.add((int(a), int(b)))
    known |= {(int(a), int(b)) for a, b in re.findall(r"(\d+) of (\d+)", json.dumps(m.get("paper_pairs", [])))}
    for a, b in re.findall(r"(?<![\d.])(\d[\d,]*) of (\d[\d,]*)(?![\d])", t):
        pair = (int(a.replace(",", "")), int(b.replace(",", "")))
        if pair not in known:
            fail.append(f"paper.md has an unchecked pair '{a} of {b}'")
else:
    print("paper.md is not in the public package: the paper is at https://easybyte.es/lab/studies/s15/paper/")

for f in fail:
    print("FAIL:", f)
print("OK" if not fail else f"{len(fail)} problem(s)")
sys.exit(1 if fail else 0)
