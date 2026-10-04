#!/usr/bin/env python3
"""Record review verdicts (METHOD.md §1.7) into data/review_verdicts.csv.

    python3 scripts/review_record.py work/auto < verdict_lines.txt

One verdict per input line, fields separated by ' ; ':
    lot_key ; review_set ; scope ; energy ; note [; key=value …]
'=' keeps the classifier's value (for review_set: the lot's set in the queue, or 'extra'). Optional key=value fields: reason=…, letters=…, both=0|1,
type=…, ground=… (for declared exemptions: land, 3.2.a … 3.2.e, guidance_garage_storage,
guidance_shell, none_stated, other), split_from=<lot_key> (a lot the review split out of an
'unsplit' or 'not_described' record; its lot_key is <BOE id>#r<N>). scope 'drop' removes a lot
(not an offer by a public body to the public, or a parsing artefact). A later line for the same
lot_key replaces the earlier one. Notes must not name persons.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data", "review_verdicts.csv")
FIELDS = ["lot_key", "review_set", "scope_final", "scope_reason_final", "energy_final", "letters_final",
          "both_final", "lot_type_final", "exempt_ground", "split_from", "change", "note"]
SCOPES = {"covered", "excluded", "undeterminable", "drop"}
ENERGY = {"rating", "exempt_declared", "pending", "no_certificate_stated", "certificate_reference", "none"}


def main(auto):
    lots = {r["lot_key"]: r for r in csv.DictReader(open(os.path.join(auto, "lots_auto.csv"), encoding="utf-8"))}
    queue = {r["lot_key"]: r["review_set"] for r in csv.DictReader(open(os.path.join(auto, "review_queue.csv"), encoding="utf-8"))}
    have = {}
    if os.path.exists(OUT):
        for r in csv.DictReader(open(OUT, encoding="utf-8")):
            have[r["lot_key"]] = r
    n = 0
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(" ; ")]
        key, rset, scope, energy, note = parts[:5]
        opts = dict(p.split("=", 1) for p in parts[5:])
        base = lots.get(opts.get("split_from", key)) or lots.get(key)
        if rset == "=":
            rset = queue.get(opts.get("split_from", key), "extra")
        if base is None:
            raise SystemExit(f"unknown lot {key}")
        scope = base["scope"] if scope == "=" else scope
        energy = base["energy_status"] if energy == "=" else energy
        if scope not in SCOPES or energy not in ENERGY:
            raise SystemExit(f"bad value in: {line}")
        reason = opts.get("reason", base["scope_reason"] if scope == base["scope"] else "")
        ch = []
        if "split_from" in opts:
            ch.append("split")
        if scope != base["scope"]:
            ch.append(f"scope {base['scope']}>{scope}")
        if energy != base["energy_status"]:
            ch.append(f"energy {base['energy_status']}>{energy}")
        if "type" in opts and opts["type"] != base["lot_type"]:
            ch.append(f"type {base['lot_type']}>{opts['type']}")
        have[key] = dict(lot_key=key, review_set=rset, scope_final=scope, scope_reason_final=reason,
                         energy_final=energy, letters_final=opts.get("letters", base["letters"] if energy == "rating" else ""),
                         both_final=opts.get("both", base["both_indicators"] if energy == "rating" else "0"),
                         lot_type_final=opts.get("type", ""), exempt_ground=opts.get("ground", ""),
                         split_from=opts.get("split_from", ""), change="; ".join(ch) or "none", note=note)
        n += 1
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(have.values(), key=lambda r: r["lot_key"]))
    print(f"recorded {n}; total verdicts {len(have)}")


if __name__ == "__main__":
    main(sys.argv[1])
