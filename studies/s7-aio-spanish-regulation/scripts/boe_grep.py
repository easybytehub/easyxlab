#!/usr/bin/env python3
"""Print literal context around regex matches in a downloaded BOE text. Usage: boe_grep.py FILE [-n N] PATTERN..."""
import re, sys
from pathlib import Path
a = sys.argv[1:]; f = a.pop(0); n = 2; w = 200
if a and a[0] == "-n": a.pop(0); n = int(a.pop(0))
p = Path(f) if Path(f).exists() else Path(__file__).resolve().parent.parent / "data/raw/boe" / f
t = re.sub(r"\s+", " ", p.read_text(encoding="utf-8"))
for pat in a:
    ms = list(re.finditer(pat, t, re.I))
    print(f"[{p.name}] /{pat}/ x{len(ms)}")
    for m in ms[:n]:
        print("   …" + t[max(0, m.start() - w):m.end() + w] + "…")
