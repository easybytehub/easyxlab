#!/usr/bin/env python3
"""Step 6 - turn the list reviewed one by one by the study agent (data/corrections_reviewed.csv) into
corrections.qs (QuickStatements V1, tab-separated) and corrections.csv (justification).

Every row is checked against the frozen snapshot: the old value must still be what the
snapshot holds, otherwise the row is dropped and reported. Nothing is sent to Wikidata.
Rows whose repaired ICD value is a block range (still violating the P494 format constraint)
are NOT put in the .qs: they are listed as manual actions. Lines that remove a P494/P7329
value and re-add the repaired one DROP the references and qualifiers of the original
statement. Before running anything, a Wikidata editor must re-check each item: rows carry the lastrevid
they were reviewed against; if the item changed since, review it again.
"""
import csv, json, os
B = os.path.join(os.path.dirname(__file__), "..")
D = {d["qid"]: d for d in map(json.loads, open(os.path.join(B, "data/frozen/drugs.jsonl")))}
S = {d["qid"]: d for d in map(json.loads, open(os.path.join(B, "data/frozen/diseases.jsonl")))}
REF = 'S854\t"https://atcddd.fhi.no/atc_ddd_alterations__cumulative/atc_alterations/"'
import re
RANGE = re.compile(r"[A-Z]\d{2}(\.\d{1,2})?[-–][A-Z]\d{2}")
qs, out, dropped, manual_rows = [], [], [], []
for r in csv.DictReader(open(os.path.join(B, "data/corrections_reviewed.csv"))):
    it = D.get(r["qid"]) or S.get(r["qid"])
    ok = False
    if it and r["kind"] == "label":
        ok = it["labels"].get(r["lang"]) == r["old_value"]
        if ok:
            qs.append(f'{r["qid"]}\tL{r["lang"]}\t"{r["new_value"]}"')
    elif it and r["kind"] in ("P494", "P7329") and RANGE.search(r["new_value"]):
        ok = r["old_value"] in [v["v"] for v in it["icd10"]]
        if ok:
            manual_rows.append({**r, "action": "manual: repaired value is a block range that still violates the P494 "
                                "format constraint; decide modelling (range vs individual codes)",
                                "lastrevid_reviewed": it["lastrevid"], "in_qs": "no"})
            continue
    elif it and r["kind"] in ("P494", "P7329"):
        key = "icd10" if r["kind"] == "P494" else "icd11"
        ok = r["old_value"] in [v["v"] for v in it[key]]
        if ok:
            qs.append(f'-{r["qid"]}\t{r["kind"]}\t"{r["old_value"]}"')
            for v in r["new_value"].split(","):
                qs.append(f'{r["qid"]}\t{r["kind"]}\t"{v.strip()}"')
    elif it and r["kind"] == "P267":
        codes = [a["code"] for a in it["atc"]]
        ok = r["old_value"] in codes and r["new_value"] not in codes
        if ok:
            qs.append(f'{r["qid"]}\tP267\t"{r["new_value"]}"\t{REF}')
    if not ok:
        dropped.append(r)
        continue
    action = {"label": f'set {r["lang"]} label', "P494": "replace ICD-10 value", "P7329": "replace ICD-11 value",
              "P267": "add current ATC code (then deprecate the old one by hand)"}[r["kind"]]
    if "," in r["new_value"]:
        r = {**r, "new_value": " ; ".join(v.strip() for v in r["new_value"].split(",")) + " (separate statements)"}
        action += " (split into separate statements)"
    if r["kind"] in ("P494", "P7329"):
        action += "; WARNING: removal drops the original statement's references and qualifiers"
    out.append({**r, "action": action, "lastrevid_reviewed": it["lastrevid"], "in_qs": "yes"})

MANUAL = [
    ("Q113368879", "label fr (manual)", "fr label 'Coumaphène' is a pesticide name; the French INN form is 'warfarine', but neither the "
     "frwiki sitelink ('Coumaphène') nor P2275 (empty) supports it, and the item may be merged with Q407431: decide together with the merge"),
    ("Q113368879", "merge?", "rac-warfarin (this item, with ATC B01AA03) and Q407431 '(RS)-warfarin' describe the same racemate; frwiki page linked here is titled 'Coumaphène'"),
    ("Q1326389", "merge?", "two items for aloxiprin (Q1326389 'aspirin aluminum', N02BA02; Q27888708 'aloxiprin', B01AC15)"),
    ("Q135197125", "remove", "ATCvet codes QB03AC91 / QB03AC stored in the human ATC property P267"),
    ("Q16868421|Q2070286|Q5186964|Q411787", "deprecate", "set deprecated rank (reason: withdrawn identifier value) on the obsolete ATC codes once the new codes are added"),
    ("ATC class items (pl, zh)", "relabel", "dozens of ATC class items share the pl label 'ATC' and the zh label 'ATC代码'; the code should be part of each label"),
]
out += manual_rows
for q, a, why in MANUAL:
    out.append({"qid": q, "kind": "manual", "lang": "", "old_value": "", "new_value": "", "error_type": a, "source": why,
                "action": "Wikidata editor decision (not in .qs)", "lastrevid_reviewed": "", "in_qs": "no"})
HEADER = [
    "# S4 proposed corrections - QuickStatements V1 (tab-separated). PROPOSAL ONLY: NOT APPLIED.",
    "# Delete these '#' lines before pasting. Re-check every item's current revision against",
    "# lastrevid_reviewed in corrections.csv, and discuss at Wikidata:WikiProject Medicine first.",
    "# WARNING: '-Qxx<TAB>P494<TAB>\"old\"' lines remove the whole statement, including its references",
    "# and qualifiers; the re-added value carries none. Restore them by hand if they exist.",
]
open(os.path.join(B, "corrections.qs"), "w").write("\n".join(HEADER + qs) + "\n")
with open(os.path.join(B, "corrections.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["qid", "kind", "lang", "old_value", "new_value", "error_type", "action", "source",
                                       "lastrevid_reviewed", "in_qs"])
    w.writeheader()
    w.writerows(out)
print(f"{sum(1 for o in out if o['in_qs'] == 'yes')} corrections -> {len(qs)} QuickStatements command lines; "
      f"{len(MANUAL) + len(manual_rows)} manual actions; dropped {len(dropped)}: {[(d['qid'], d['lang'], d['old_value']) for d in dropped]}")
