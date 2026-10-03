#!/usr/bin/env python3
"""Draw the stratified blind subsample for the second reader (v2).

Strata, from data/answers.csv (rule verdict = regex script; final verdict = after the AI agent's re-reading):
  A  confirmed errors      final in {outdated, mixed, incorrect}                      20 drawn (seed 31)
  B  flagged, rejected     rule in {outdated, mixed}, final in {current, not_stated}  all (seed 32 for order)
  C  unflagged             rule == final, final in {current, not_stated}             23 drawn (seed 33)
The reader sees only the corrected fact sheet (rule in force on 2026-10-02 and the superseded rule), the query and
the answer text. The input file holds full Google answers, so it is written to data/raw/second_reader_v2/
(not redistributed); data/second_reader_sample.csv (published) lists the drawn ids and strata.
Usage: sample_second_reader.py
"""
import csv, json, random
from pathlib import Path
R = Path(__file__).resolve().parent.parent
facts = {f["id"]: f for f in json.load(open(R / "data/facts.json", encoding="utf-8"))}
A = [r for r in csv.DictReader(open(R / "data/answers.csv", encoding="utf-8")) if r["has_answer"] == "True"]
ERR = {"outdated", "mixed", "incorrect"}
sA = [r for r in A if r["final_verdict"] in ERR]
sB = [r for r in A if r["rule_verdict"] in ("outdated", "mixed") and r["final_verdict"] in ("current", "not_stated")]
sC = [r for r in A if r["rule_verdict"] == r["final_verdict"] and r["final_verdict"] in ("current", "not_stated")]
take = [("A", r) for r in random.Random(31).sample(sA, min(20, len(sA)))]
take += [("B", r) for r in random.Random(32).sample(sB, len(sB))]
take += [("C", r) for r in random.Random(33).sample(sC, 23)]
random.Random(34).shuffle(take)
resp = {}
for n in (1, 2, 3):
    for l in open(R / f"data/raw/responses/reading{n}.jsonl", encoding="utf-8"):
        x = json.loads(l); resp[(str(n), x["qid"], x["surface"])] = x
out = R / "data/raw/second_reader_v2"; out.mkdir(parents=True, exist_ok=True)
with open(out / "input.jsonl", "w", encoding="utf-8") as fh, open(R / "data/second_reader_sample.csv", "w", newline="") as fs:
    w = csv.writer(fs); w.writerow(["item", "reading", "qid", "surface", "stratum", "population_size"])
    for i, (st, r) in enumerate(take, 1):
        f = facts[r["fact_id"]]
        x = resp[(r["reading"], r["qid"], r["surface"])]
        fh.write(json.dumps({"item": i, "fact": {"topic": f["topic"], "rule_in_force_2026_10_02": f["current"],
                                                 "superseded_rule": f["old"]},
                             "query": x["query"], "answer_text": x["text"]}, ensure_ascii=False) + "\n")
        w.writerow([i, r["reading"], r["qid"], r["surface"], st, {"A": len(sA), "B": len(sB), "C": len(sC)}[st]])
print(f"A {len(sA)} -> {sum(1 for s,_ in take if s=='A')}, B {len(sB)} -> {sum(1 for s,_ in take if s=='B')}, C {len(sC)} -> 23; total {len(take)}")
