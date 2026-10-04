#!/usr/bin/env python3
"""Base rate for the wording changes: how much text every measure and every milestone/target
lost in the December 2025 amendment (COM(2025) 794 against COM(2025) 556) and in the August
2026 amendment (COM(2026) 435 against COM(2026) 257), so that the housing items can be set
against the whole annex.

Length is counted in words of the description, footnote call-outs removed (cidparse). A
measure description that runs into a table (the parser stops at the next heading, and a few
loan measures are followed by long tables) is excluded when it exceeds 3,000 words in either
version; the number excluded is reported.

Outputs: data/baseline_measures.csv, data/baseline_rows.csv, data/baseline_summary.json
"""
import csv, json, statistics
from s20lib import DATA, VERSIONS, version_docs
from cidparse import descriptions, mt_rows

PAIRS = [("v6-2025c", "v7-2025d"), ("v8-2026a", "v9-2026b")]
HOUSING = ("C2.I2", "C2.I7", "C2.R3", "C2.R7")
CAP = 3000


def annex(label):
    celex = {v[0]: v[1] for v in VERSIONS}[label]
    return max(version_docs(celex), key=lambda d: len(d[1]))[1]


def words(s):
    return len((s or "").split())


def summarise(ratios):
    n = len(ratios)
    return {"n": n,
            "changed": sum(1 for r in ratios if r != 1.0),
            "lost_more_than_30pct": sum(1 for r in ratios if r < 0.7),
            "share_lost_more_than_30pct": round(sum(1 for r in ratios if r < 0.7) / n, 3),
            "median_ratio": round(statistics.median(ratios), 3)}


def main():
    mout, rout, summ = [], [], {}
    for a, b in PAIRS:
        A, B = annex(a), annex(b)
        da, db = descriptions(A), descriptions(B)
        ratios, excluded, hous = [], 0, {}
        for m in sorted(set(da) & set(db)):
            wa, wb = words(da[m][1]), words(db[m][1])
            if wa == 0:
                continue
            if wa > CAP or wb > CAP:
                excluded += 1
                continue
            r = wb / wa
            ratios.append(r)
            mout.append({"from": a, "to": b, "measure": m, "housing": m in HOUSING,
                         "words_from": wa, "words_to": wb, "ratio": round(r, 3)})
            if m in HOUSING:
                hous[m] = round(r, 3)
        s = summarise(ratios)
        s["excluded_over_cap"] = excluded
        s["housing_ratios"] = hous
        s["housing_rank_from_most_cut"] = {m: 1 + sum(1 for x in ratios if x < hous[m]) for m in hous}
        # milestones and targets present in both versions
        ra = {(r["measure"], r["number"]): r for r in mt_rows(A)}
        rb = {(r["measure"], r["number"]): r for r in mt_rows(B)}
        rr, rh = [], {}
        for k in sorted(set(ra) & set(rb)):
            wa, wb = words(ra[k]["cells"][-1]), words(rb[k]["cells"][-1])
            if wa == 0:
                continue
            r = wb / wa
            rr.append(r)
            rout.append({"from": a, "to": b, "measure": k[0], "number": k[1], "housing": k[0] in HOUSING,
                         "words_from": wa, "words_to": wb, "ratio": round(r, 3)})
            if k[0] in HOUSING:
                rh[f"{k[0]} {k[1]}"] = round(r, 3)
        rs = summarise(rr)
        rs["housing_ratios"] = rh
        rs["housing_rank_from_most_cut"] = {k: 1 + sum(1 for x in rr if x < v) for k, v in rh.items()}
        rs["housing_rows_removed"] = sorted(f"{k[0]} {k[1]}" for k in set(ra) - set(rb) if k[0] in HOUSING)
        rs["housing_rows_from"] = sum(1 for k in ra if k[0] in HOUSING)
        rs["removed_rows"] = len(set(ra) - set(rb))
        rs["rows_from"] = len(ra)
        summ[f"{a}->{b}"] = {"measures": s, "milestones_targets": rs}
        print(a, "->", b, "measures", s, "\n   rows", rs, flush=True)
    for name, rows in (("baseline_measures.csv", mout), ("baseline_rows.csv", rout)):
        with open(DATA / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    json.dump(summ, open(DATA / "baseline_summary.json", "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
