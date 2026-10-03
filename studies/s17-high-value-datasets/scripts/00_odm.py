# SPDX-License-Identifier: Apache-2.0
"""ODM 2025 per-country answers to P11, P12, Q5, Q6 (METHOD.md §8) -> data/odm2025_answers.csv.
Source: data.europa.eu, 2025_odm_questionnaire_data.xlsx (sheet merged_responses), kept in data/raw/."""
import csv
import os

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
wb = openpyxl.load_workbook(os.path.join(ROOT, "data/raw/odm2025_questionnaire_data.xlsx"), read_only=True)
ws = wb["merged_responses"]
it = ws.iter_rows(values_only=True)
hdr = next(it)
rows = {}
for r in it:
    d = dict(zip(hdr, r))
    if d["question_id"] in ("P11", "P12", "Q5", "Q6") and d["country_group"] == "eu27":
        rows.setdefault(d["country_code"], {"country_code": d["country_code"], "country_name": d["country_name"]})
        rows[d["country_code"]][d["question_id"]] = d["response"]
with open(os.path.join(ROOT, "data/odm2025_answers.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, ["country_code", "country_name", "P11", "P12", "Q5", "Q6"], lineterminator="\n")
    w.writeheader()
    for k in sorted(rows):
        w.writerow(rows[k])
print(len(rows), "Member States")
