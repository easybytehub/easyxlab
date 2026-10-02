#!/usr/bin/env python3
"""Step 4 - stratified random sample of flags for manual review (fixed seed).

Quotas per (detector, subtype); if a stratum has fewer flags than its quota, all are taken.
Writes data/validation_sample.csv (machine part) and prints a review sheet with context.
The human verdicts live in data/validation_verdicts.csv (sample_id, verdict, note), written
by hand: TP = the flag points at a real error; FP = the flagged value is correct/acceptable;
DOUBT = cannot be settled from verifiable sources during review.
"""
import csv, json, os, random, collections

SEED = 20261002
QUOTA = {("a", "a_latin"): 12, ("a", "a_other"): 2, ("a", "a_nonlatin"): 2,
         ("b", "b_rxnorm_bn"): 12,
         ("c", "c_salt_on_parent"): 10, ("c", "c_parent_on_salt"): 10,
         ("d", "d_diff_en"): 14,
         ("e", "e_different"): 9, ("e", "e_contains"): 4, ("e", "e_typographic"): 3,
         ("f", "f_doubled"): 5, ("f", "f_corrupt"): 5, ("f", "f_cm"): 3, ("f", "f_icd11"): 2,
         ("g", "g_obsolete"): 5, ("g", "g_obsolete_split"): 1, ("g", "g_dup"): 4, ("g", "g_format"): 2}
# Not sampled (informational, not error claims): a_mixed (script mixing), a_devcode,
# f_range (ICD-10 block ranges: valid ICD notation that only violates Wikidata's regex).
BASE = os.path.join(os.path.dirname(__file__), "..", "data")
flags = list(csv.DictReader(open(os.path.join(BASE, "flags.csv"))))
drugs = {d["qid"]: d for d in map(json.loads, open(os.path.join(BASE, "frozen", "drugs.jsonl")))}
dis = {d["qid"]: d for d in map(json.loads, open(os.path.join(BASE, "frozen", "diseases.jsonl")))}

strata = collections.defaultdict(list)
for f in flags:
    if f["detector"] in ("a",) and f["domain"] != "drug":
        continue  # disease-label script flags are reported, not sampled (same rule as drugs)
    strata[(f["detector"], f["subtype"])].append(f)
sample = []
for key in sorted(QUOTA):
    pool = sorted(strata.get(key, []), key=lambda f: f["flag_id"])
    rng = random.Random(f"{SEED}-{key[1]}")   # one RNG per stratum: strata are independent
    sample += rng.sample(pool, min(QUOTA[key], len(pool)))
for i, f in enumerate(sample, 1):
    f["sample_id"] = f"S{i:03d}"
cols = ["sample_id"] + list(flags[0].keys())
with open(os.path.join(BASE, "validation_sample.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(sample)

for f in sample:
    it = drugs.get(f["qid"]) or dis.get(f["qid"]) or {}
    lab = it.get("labels", {})
    ctx = {k: lab.get(k)[:30] for k in ("en", "es", "fr", "ru", "zh") if lab.get(k) and k != f["lang"]}
    wiki = it.get("wiki", {}).get(f["lang"], "")
    inn = {k: v for k, v in it.get("inn", {}).items() if k in ("en", "fr", "es", f["lang"])}
    print(f"{f['sample_id']} {f['subtype']:<16} {f['qid']:<11} [{f['lang']}] «{f['value']}» ref={f['reference'][:60]!r} "
          f"x={f['extra'][:60]!r} wiki={wiki!r} inn={inn} ctx={ctx}")
print(len(sample), "sampled; strata sizes:", {f"{k[1]}": len(v) for k, v in sorted(strata.items())})
