#!/usr/bin/env python3
"""Estimated cost of each housing measure, by version, from the Commission staff working
documents that accompany the proposals (the CID annex states measure costs only for some
financial instruments). The SWDs carry a climate-tagging table with one row per measure or
sub-measure: id, name, budget (EUR million), intervention field, coefficient.

Output: data/measure_costs.csv (version, SWD, measure id as printed, name, EUR million).
"""
import csv, glob, re
from s20lib import DATA, RAW
from cidparse import tables

SWD = {  # SWD CELEX -> version it accompanies
    "52021SC0147": "v0-2021", "52023SC0326": "v1-2023", "52025SC0276": "v6-2025c",
    "52025SC0432": "v7-2025d", "52026SC0135": "v8-2026a", "52026SC0267": "v9-2026b",
}
IDS = re.compile(r"^C\s?(2|13)\s?\.\s?([RI])\s?(\d{1,2})\s?([a-z]?)$")
WANT = {("2", "I", "2"), ("2", "I", "7"), ("2", "R", "7"), ("13", "I", "13")}


def num(s):
    s = re.sub(r"\s", "", s)
    if not re.fullmatch(r"\d+(?:[.,]\d+)*", s):
        return None
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):      # 1.000 = one thousand (EUR million)
        return float(s.replace(".", ""))
    return float(s.replace(",", "."))


def main():
    out = []
    for celex, version in SWD.items():
        files = sorted(glob.glob(str(RAW / "frame" / celex / "DOC_*.xhtml")))
        if not files:
            print(celex, "not downloaded")
            continue
        seen = set()
        for f in files:
            b = open(f, "rb").read()
            if not b.lstrip().startswith(b"<"):
                continue
            for ti, t in enumerate(tables(b.decode("utf-8"))):
                for r in t:
                    if len(r) < 3:
                        continue
                    m = IDS.match(re.sub(r"\s+", " ", r[0]).strip())
                    if not m or (m.group(1), m.group(2), m.group(3)) not in WANT:
                        continue
                    val = next((num(c) for c in r[2:4] if num(c) is not None), None)
                    key = (r[0], r[1][:80], val)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({"version": version, "swd_celex": celex, "doc": f.rsplit("/", 1)[1], "table": ti,
                                "measure_printed": r[0], "measure": f"C{m.group(1)}.{m.group(2)}{m.group(3)}",
                                "name": r[1], "eur_million": val, "cells": " | ".join(r)[:400]})
        print(celex, version, sum(1 for o in out if o["swd_celex"] == celex), flush=True)
    with open(DATA / "measure_costs.csv", "w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    for o in out:
        print(o["version"], o["measure_printed"], o["eur_million"], "|", o["name"][:80])


if __name__ == "__main__":
    main()
