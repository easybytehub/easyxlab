#!/usr/bin/env python3
"""Step 1b - instance-of (P31) classes of the ICD-coded items, to separate real diseases from
taxa (Latin binomials are correct in every language), Wikimedia templates/categories and
other non-disease items that carry ICD statements. Output: data/frozen/disease_p31.json"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from wd import q, qid
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "frozen", "disease_p31.json")
res = {}
for prop in ("P494", "P7329"):
    for b in q(f"SELECT DISTINCT ?item ?c WHERE {{ ?item p:{prop} ?st. ?item wdt:P31 ?c }}"):
        res.setdefault(qid(b["item"]["value"]), set()).add(qid(b["c"]["value"]))
json.dump({k: sorted(v) for k, v in sorted(res.items())}, open(OUT, "w"))
print(len(res), "items with P31")
