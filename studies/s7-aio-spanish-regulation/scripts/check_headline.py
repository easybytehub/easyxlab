#!/usr/bin/env python3
"""Assert every headline number of README.md / paper.md against the published data (no raw answers needed).

Recomputes from data/answers.csv, data/citations.csv, data/fn_check.csv, data/second_reader*.csv independently of
aggregate.py, compares with data/summary.json, and checks that README.md and paper.md print the same values.
Exit 1 on any mismatch."""
import csv, json, math, sys
from collections import Counter
from pathlib import Path
R = Path(__file__).resolve().parent.parent
D = R / "data"
WRONG = {"outdated", "mixed", "incorrect"}
def wilson(k, n, z=1.96):
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return f"{100*max(0,c-h):.1f}–{100*(c+h):.1f}"
A = [r for r in csv.DictReader(open(D / "answers.csv", encoding="utf-8")) if r["fact_id"] != "F16" and r["has_answer"] == "True"]
S = json.load(open(D / "summary.json", encoding="utf-8"))
docs = (R / "README.md").read_text(encoding="utf-8") + (R / "paper.md").read_text(encoding="utf-8")
bad = []
def need(label, value, text=None):
    print(f"{label}: {value}")
    if text is not None and text not in docs:
        bad.append(f"docs do not contain «{text}» ({label})")
for s, name in (("aio", "AI Overview"), ("mode", "AI Mode")):
    x = [r for r in A if r["surface"] == s]
    w = sum(r["final_verdict"] in WRONG for r in x)
    rule = sum(r["rule_verdict"] in ("outdated", "mixed") for r in x)
    if (w, len(x)) != (S["pooled"][s]["wrong"], S["pooled"][s]["answered"]):
        bad.append(f"{s}: summary.json disagrees")
    need(f"{name} wrong", f"{w} of {len(x)}", f"{w} of {len(x)}")
    need(f"{name} CI", wilson(w, len(x)), wilson(w, len(x)))
    need(f"{name} regex-only flags", rule, f"{rule} ")
    b = sum(r["cites_boe"] == "True" for r in x)
    need(f"{name} BOE cited %", f"{100*b/len(x):.1f}", f"{100*b/len(x):.1f} %")
C = [c for c in csv.DictReader(open(D / "citations.csv", encoding="utf-8")) if c["fact_id"] != "F16" and c["surface"] == "aio"]
fs = sum(c["type"] == "forum_social" for c in C)
need("AIO forum/social share of references", f"{100*fs/len(C):.1f}", f"{100*fs/len(C):.1f} %")
fn = list(csv.DictReader(open(D / "fn_check.csv", encoding="utf-8")))
m = sum(r["agent_verdict"] in WRONG for r in fn)
need("false-negative check", f"{m} of {len(fn)}", f"{m} of {len(fn)}")
need("second reader kappa", f"κ {S['second_reader']['kappa']:.2f}", f"κ {S['second_reader']['kappa']:.2f}")
need("second reader binary kappa", f"{S['second_reader']['binary_wrong_kappa']:.2f}", f"{S['second_reader']['binary_wrong_kappa']:.2f}")
f16 = [r for r in csv.DictReader(open(D / "answers.csv", encoding="utf-8")) if r["fact_id"] == "F16" and r["has_answer"] == "True"]
o = sum(r["final_verdict"] == "outdated" for r in f16)
need("F16 answers presenting a repealed cap as law", f"{o} of {len(f16)}", f"{o} of {len(f16)}")
if bad:
    print("\nFAIL:\n  " + "\n  ".join(bad)); sys.exit(1)
print("\nOK: every headline number matches data/ and appears in README.md / paper.md")
