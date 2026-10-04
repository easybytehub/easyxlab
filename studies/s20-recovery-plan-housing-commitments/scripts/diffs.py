#!/usr/bin/env python3
"""Literal diff of every housing item between consecutive versions of Spain's CID, and between
each item's first and last version. Uses scripts/differ.py. Output: data/diffs.csv.

An item is a milestone/target row (measure + number), a measure (name + description) or the
component-2 summary sentence. Row L2 of C2.R7 was replaced by row L2a in December 2025: they
are different items (one removed, one added), as the CID numbers them.
"""
import csv
from s20lib import DATA, VERSIONS
import differ

ROWF = ("type", "name", "qual_indicator", "unit", "baseline", "goal", "quarter", "year", "description")


def load():
    rows = list(csv.DictReader(open(DATA / "housing_rows.csv", encoding="utf-8")))
    meas = list(csv.DictReader(open(DATA / "housing_measures.csv", encoding="utf-8")))
    items = {}   # key -> {version: dict}
    for r in rows:
        items.setdefault(("row", r["measure"], r["number"]), {})[r["version"]] = {k: r[k] for k in ROWF}
    for m in meas:
        items.setdefault(("measure", m["measure"], ""), {})[m["version"]] = {"name": m["name"], "description": m["description"]}
    return items, {m["measure"]: m["scope"] for m in meas}


def compare(old, new):
    cats = differ.classify(old, new)
    if old and new and old.get("type") != new.get("type") and "definition" not in cats:
        cats = sorted(set(cats) | {"definition"})
    return cats


def text(d):
    if d is None:
        return ""
    if "goal" in d:
        return (f"[{d['type']}] {d['name']} | indicator: {d['qual_indicator']} | unit: {d['unit']} | "
                f"baseline: {d['baseline']} | goal: {d['goal']} | due: {d['quarter']} {d['year']} | {d['description']}")
    return f"{d['name']} | {d['description']}"


def main():
    items, scope = load()
    labels = [v[0] for v in VERSIONS]
    meta = {v[0]: v for v in VERSIONS}
    out = []
    for key, byv in sorted(items.items()):
        kind, measure, number = key
        present = [l for l in labels if l in byv]
        # consecutive versions, from the first in which the item (or its measure) exists
        first_idx = labels.index(present[0])
        for a, b in zip(labels[first_idx:], labels[first_idx + 1:]):
            old, new = byv.get(a), byv.get(b)
            if old is None and new is None:
                continue
            cats = compare(old, new)
            if not cats:
                continue
            ops = differ.word_diff(text(old), text(new))
            out.append({
                "comparison": "consecutive", "kind": kind, "measure": measure, "number": number,
                "scope": scope.get(measure, "core"), "from_version": a, "to_version": b,
                "to_com": meta[b][2], "to_proposed": meta[b][3], "categories": ";".join(cats),
                "goal_from": (old or {}).get("goal", ""), "goal_to": (new or {}).get("goal", ""),
                "due_from": f"{(old or {}).get('quarter', '')} {(old or {}).get('year', '')}".strip(),
                "due_to": f"{(new or {}).get('quarter', '')} {(new or {}).get('year', '')}".strip(),
                "eur_from": ";".join(map(str, differ.eur_amounts(text(old)))),
                "eur_to": ";".join(map(str, differ.eur_amounts(text(new)))),
                "word_diff": differ.render(ops), "old_text": text(old), "new_text": text(new),
            })
        a, b = present[0], present[-1]
        last = labels[-1]
        old, new = byv[a], byv.get(last)
        cats = compare(old, new)
        ops = differ.word_diff(text(old), text(new))
        out.append({
            "comparison": "first-to-last", "kind": kind, "measure": measure, "number": number,
            "scope": scope.get(measure, "core"), "from_version": a, "to_version": last,
            "to_com": meta[last][2], "to_proposed": meta[last][3], "categories": ";".join(cats) or "unchanged",
            "goal_from": old.get("goal", ""), "goal_to": (new or {}).get("goal", ""),
            "due_from": f"{old.get('quarter', '')} {old.get('year', '')}".strip(),
            "due_to": f"{(new or {}).get('quarter', '')} {(new or {}).get('year', '')}".strip(),
            "eur_from": ";".join(map(str, differ.eur_amounts(text(old)))),
            "eur_to": ";".join(map(str, differ.eur_amounts(text(new)))),
            "word_diff": differ.render(ops), "old_text": text(old), "new_text": text(new),
        })
    with open(DATA / "diffs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    for o in out:
        if o["scope"] == "core":
            print(o["comparison"][:5], o["measure"], o["number"], o["from_version"], "->", o["to_version"], o["categories"],
                  o["goal_from"], "->", o["goal_to"], o["eur_from"], "->", o["eur_to"])


if __name__ == "__main__":
    main()
