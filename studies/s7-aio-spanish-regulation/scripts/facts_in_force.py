#!/usr/bin/env python3
"""One row per fact: the rule in force at each reading (2026-10-02, 19:32 / 23:05 / 23:42 UTC), its BOE ids, the later
references the BOE lists for its sources (data/fact_status.json, scripts/status_check.py) and what changed between the
first fact sheet (v1) and the re-verified one (v2). Writes data/facts_in_force.csv."""
import csv, json
from pathlib import Path
R = Path(__file__).resolve().parent.parent
facts = json.load(open(R / "data/facts.json", encoding="utf-8"))
st = json.load(open(R / "data/fact_status.json", encoding="utf-8"))["sources"]
CHANGED = {
 "F04": "date only: in force 2025-05-01 (v1 gave the publication date)",
 "F14": "wording: the general maximum base rises to 5,101.20 and fees rise slightly via the MEI; brackets and minimum bases unchanged",
 "F15": "WRONG in v1: the Supreme Court annulled the state register (judgments 19-May, 21-May, 1-Jun-2026; BOE 8-Jun, 26-Jun, 18-Jul)",
 "F16": "truth unchanged (no cap at any reading); v1 excluded it on a false premise: RDL 26/2026 was repealed (BOE 245, 14:59:41 UTC 2-Oct) before reading 1",
 "F20": "INCOMPLETE in v1: 12-month adaptation period (to 28-Dec-2026, transitional provision) and pending constitutional appeal 2331/2026",
 "F21": "INCOMPLETE in v1: Ley 10/2025 also rewrote TRLGDCU art. 21.3 for all businesses (one month -> fifteen days)",
 "F22": "INCOMPLETE in v1: 12-month adaptation period",
 "F25": "WRONG in v1: RDL 7/2026 (in force 22-Mar-2026, validated 26-Mar) cut the deadline from 24 to 12 months (obligation from 5-Dec-2026)",
 "F28": "detail: fixed calendar dates are not in the rule (the deadlines run from an order not published by 2-Oct-2026)",
}
rows = []
for f in facts:
    src = [i for i, v in st.items() if f["id"] in v["facts"]]
    later = sorted({ref.split("(Ref. ")[1].rstrip(" )") for i in src for ref in st[i]["later_refs_2025_2026"] if "(Ref. " in ref})
    rule = f["current"]
    rows.append({"fact_id": f["id"], "topic": f["topic"], "rule_in_force_reading1_19:32UTC": rule,
                 "same_at_readings_2_and_3": "yes (no BOE issue between 19:32 and 23:47 UTC; the 3-Oct issue was not online at 04:17 UTC)",
                 "boe_ids_rule": " ".join(r["boe_id"] for r in f["boe"]), "boe_ids_superseded": " ".join(r["boe_id"] for r in f["boe_old"]),
                 "sources_checked": " ".join(src), "later_refs_listed_by_boe_2025_2026": " ".join(later),
                 "v1_to_v2": CHANGED.get(f["id"], "unchanged")})
with open(R / "data/facts_in_force.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), sum(r["v1_to_v2"] != "unchanged" for r in rows))
