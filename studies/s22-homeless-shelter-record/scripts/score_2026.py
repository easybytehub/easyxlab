#!/usr/bin/env python3
"""S22: score ECAPSH 2026 against PROTOCOL.md §5–§6 as clarified by deviation D1 (§12).

  python scripts/score_2026.py --reception-dec2026 N [--classification-break]
        reads the 2026 rows of data/specialisation.csv (added by build.py once INE publishes the
        2026 tables; the only code change allowed is adding the 2026 table ids) and the frozen
        2024 baselines in data/predictions_2026_spec.json
  python scripts/score_2026.py --dry-run
        runs the same rules on 2022 -> 2024 (in sample, not a test) to show the code works

Frozen with the protocol's freeze commit. Writes data/score_2026.json (or data/score_dryrun.json).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys

from s22lib import DATA


def seg(rows, ed):
    return {r["segment"]: {k: float(v) for k, v in r.items() if k not in ("edition", "segment", "occupied_scope")}
            for r in rows if int(r["edition"]) == ed}


def score(base, new, rec_base, rec_new, classification_break=False):
    core = ("GBV", "OTH")
    o = lambda d, ss: sum(d[x]["occupied_mean"] for x in ss)
    c = lambda d, ss: sum(d[x]["accommodation_centres"] for x in ss)
    p = lambda d, ss: sum(d[x]["places_mean"] for x in ss)
    q1 = math.log((o(new, core) / c(new, core)) / (o(base, core) / c(base, core)))
    q1_oth = math.log((o(new, ("OTH",)) / c(new, ("OTH",))) / (o(base, ("OTH",)) / c(base, ("OTH",))))
    q2 = 100 * o(new, core) / p(new, core) - 100 * o(base, core) / p(base, core)
    d_imm_occ = new["IMM"]["occupied_mean"] - base["IMM"]["occupied_mean"]
    d_imm_pl = new["IMM"]["places_mean"] - base["IMM"]["places_mean"]
    d_core = o(new, core) - o(base, core)
    p3 = "A" if abs(d_imm_occ) > abs(d_core) else "B"
    p4 = "not scored"
    p4_detail = {}
    if rec_base and rec_new:
        dr = rec_new / rec_base - 1
        p4_detail = {"reception_change_pct": 100 * dr}
        if abs(dr) >= 0.10:
            m_occ = (d_imm_occ > 0) == (dr > 0)
            m_pl = (d_imm_pl > 0) == (dr > 0)
            p4 = "A on both" if (m_occ and m_pl) else ("mismatch on both" if not (m_occ or m_pl) else "mixed")
    pressure = q1 > 0.10 and q1_oth > 0.10 and q2 > 4
    none_ = abs(q1) <= 0.10 and abs(q1_oth) <= 0.10 and abs(q2) <= 4
    if classification_break:
        verdict = "not scored (classification break)"
    elif pressure:
        verdict = "B supported (per-centre pressure in the core)"
    elif none_ and p4 == "A on both":
        verdict = "A supported"
    elif none_ and p4 == "mismatch on both":
        verdict = "A rejected on P4; no per-centre pressure"
    elif none_:
        verdict = "no per-centre pressure; A and growth through new centres not separable"
    else:
        verdict = "undetermined"
    return {"q1": q1, "q1_oth": q1_oth, "q2_pp": q2, "P3": p3, "delta_imm_occupied": d_imm_occ,
            "delta_imm_places": d_imm_pl, "delta_core_occupied": d_core, "P4": p4, **p4_detail,
            "reading_B_falsified": none_, "reading_A_falsified": pressure or p4 == "mismatch on both",
            "verdict": verdict}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reception-dec2026", type=float)
    ap.add_argument("--classification-break", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(DATA / "specialisation.csv", encoding="utf-8")))
    spec = json.loads((DATA / "predictions_2026_spec.json").read_text(encoding="utf-8"))
    if a.dry_run:
        ex = {int(r["year"]): r for r in csv.DictReader(open(DATA / "explanatory.csv", encoding="utf-8"))}
        res = score(seg(rows, 2022), seg(rows, 2024), float(ex[2022]["reception_places_total"]),
                    float(ex[2024]["reception_places_total"]))
        out = DATA / "score_dryrun.json"
    else:
        if not seg(rows, 2026):
            print("no 2026 rows in data/specialisation.csv: INE has not published ECAPSH 2026 or build.py lacks its ids")
            return 1
        res = score(seg(rows, 2024), seg(rows, 2026), spec["baseline_2024"]["reception_places_dec2024"],
                    a.reception_dec2026, a.classification_break)
        out = DATA / "score_2026.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in res.items():
        print(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
