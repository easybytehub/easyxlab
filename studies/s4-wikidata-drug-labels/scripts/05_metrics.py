#!/usr/bin/env python3
"""Step 5 - rates per language / error type, detector precision (Wilson 95% CI).

Inputs: data/flags.csv, data/label_counts.json, data/validation_sample.csv,
        data/validation_verdicts.csv (hand-written). Outputs: data/metrics.json, data/tables.md
Precision = TP / (TP + FP); DOUBT is excluded from that ratio and reported separately, and a
conservative bound counts DOUBT as FP. Estimated errors = flags x precision (point estimate).
"""
import csv, json, math, os, collections

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
LANGS = ["en", "es", "fr", "de", "it", "pt", "pl", "ru", "uk", "tr", "ar", "fa", "ur", "hi", "bn",
         "zh", "ja", "ko", "sw", "am"]
flags = list(csv.DictReader(open(os.path.join(BASE, "flags.csv"))))
counts = json.load(open(os.path.join(BASE, "label_counts.json")))
sample = {r["sample_id"]: r for r in csv.DictReader(open(os.path.join(BASE, "validation_sample.csv")))}
verd = {r["sample_id"]: r for r in csv.DictReader(open(os.path.join(BASE, "validation_verdicts.csv")))}


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(p, 3), round(max(0, c - h), 3), round(min(1, c + h), 3))


# ---- precision per detector and per subtype ----
prec = {}
for level in ("detector", "subtype"):
    agg = collections.defaultdict(collections.Counter)
    for sid, s in sample.items():
        v = verd.get(sid, {}).get("verdict", "UNREVIEWED")
        agg[s[level]][v] += 1
    for k, c in agg.items():
        tp, fp, db = c["TP"], c["FP"], c["DOUBT"]
        p, lo, hi = wilson(tp, tp + fp)
        prec[k] = {"n": sum(c.values()), "TP": tp, "FP": fp, "DOUBT": db, "unreviewed": c["UNREVIEWED"],
                   "precision": p, "ci95": [lo, hi], "precision_conservative": wilson(tp, tp + fp + db)[0]}

# ---- flag counts ----
drug_flags = [f for f in flags if f["domain"] == "drug"]
ERR_A = {"a_latin", "a_other", "a_nonlatin"}
by_lang = {}
for l in LANGS:
    n = counts["drug"].get(l, 0)
    row = {"labels": n, "coverage": round(n / counts["drug_items"], 3)}
    for det in "abcde":
        fl = {(f["qid"]) for f in drug_flags if f["lang"] == l and f["detector"] == det
              and (det != "a" or f["subtype"] in ERR_A)}
        row[det] = len(fl)
    row["any"] = len({f["qid"] for f in drug_flags if f["lang"] == l and f["detector"] in "abce"
                      and (f["detector"] != "a" or f["subtype"] in ERR_A)})
    est = 0.0
    for det in "abce":
        p = prec.get(det, {}).get("precision") or 0
        est += row[det] * p
    row["est_errors"] = round(est, 1)
    row["est_rate_per_1000"] = round(1000 * est / n, 2) if n else None
    by_lang[l] = row

sub_counts = collections.Counter((f["domain"], f["detector"], f["subtype"]) for f in flags)
dis_a = {l: {"labels": counts["disease"].get(l, 0),
             "a_err": len({f["qid"] for f in flags if f["domain"] in ("disease", "chronic") and f["lang"] == l
                           and f["subtype"] in ERR_A})} for l in LANGS}
chronic_flags = [f for f in flags if f["domain"] == "chronic"]

out = {"precision": prec, "by_lang_drugs": by_lang,
       "subtype_counts": {"|".join(k): v for k, v in sorted(sub_counts.items())},
       "disease_script": dis_a, "chronic_flags": chronic_flags, "counts": counts}
json.dump(out, open(os.path.join(BASE, "metrics.json"), "w"), indent=1, ensure_ascii=False)

# ---- markdown tables ----
L = ["| lang | labels | coverage | a script | b brand | c salt | d dup | e INN | flagged (a,b,c,e) | est. errors | est. per 1,000 |",
     "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
for l, r in by_lang.items():
    L.append(f"| {l} | {r['labels']} | {r['coverage']:.0%} | {r['a']} | {r['b']} | {r['c']} | {r['d']} | {r['e']} | "
             f"{r['any']} | {r['est_errors']} | {r['est_rate_per_1000']} |")
L += ["", "| detector / subtype | flags (all domains) |", "|---|---:|"]
for k, v in sorted(sub_counts.items()):
    L.append(f"| {k[0]} · {k[1]} · {k[2]} | {v} |")
L += ["", "| detector | reviewed | TP | FP | doubtful | precision | 95% CI | conservative |", "|---|---:|---:|---:|---:|---:|---|---:|"]
for k in sorted(prec):
    p = prec[k]
    L.append(f"| {k} | {p['n']} | {p['TP']} | {p['FP']} | {p['DOUBT']} | {p['precision']} | {p['ci95']} | "
             f"{p['precision_conservative']} |")
L += ["", "| lang | disease labels | script errors (a) |", "|---|---:|---:|"]
for l, r in dis_a.items():
    L.append(f"| {l} | {r['labels']} | {r['a_err']} |")
open(os.path.join(BASE, "tables.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
