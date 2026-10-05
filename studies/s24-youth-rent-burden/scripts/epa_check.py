#!/usr/bin/env python3
"""S24: the CJE's emancipation chart joins two surveys. What does each survey say about 2024-2025?

Until its 2024 editions the CJE's Observatorio de Emancipación computed the emancipation rate from the
EPA (Labour Force Survey); its 2025 report uses the ECV. Its chart 2006-2025 shows the EPA rate of the
second semester of each edition up to 2024 and the ECV rate for 2025 («Se muestra la tasa de
emancipación del segundo semestre de cada edición del Observatorio de Emancipación hasta 2024. En
2025, se muestra la tasa de emancipación calculada con la nueva metodología»).

This script computes, from INE's public EPA microdata, the share of people aged 16-29 (EDAD1 groups 16,
20 and 25) with neither father nor mother in the dwelling (NPADRE and NMADRE = 00), weighted by
FACTOREL, for the third and fourth quarters of 2023, 2024 and 2025. For 2023 it also applies the
base-2021 weights INE published in an annex (FACB2021), which the 2024 and 2025 files already use. The public files carry age in
five-year groups and no other definition of the «hogar de origen», so these levels do not reproduce the
CJE's (17,0 % in 2023 and 15,2 % in 2024, EPA); we use them only for the year-on-year direction.
The ECV series comes from data/living_with_parents.csv (analyse.py). Writes data/epa_emancipation.csv.
"""
from __future__ import annotations

import csv
import io
import sys
import zipfile

from s24lib import D, RAW

QUARTERS = ("3t23", "4t23", "3t24", "4t24", "3t25", "4t25")


def epa(q):
    z = zipfile.ZipFile(RAW / "epa" / f"datos_{q}.zip")
    name = [n for n in z.namelist() if n.startswith("CSV/") and n.lower().endswith(".tab")][0]
    rd = csv.reader(io.StringIO(z.read(name).decode("latin-1")), delimiter="\t")
    head = [h.strip('"') for h in next(rd)]
    for r in rd:
        if r:
            yield dict(zip(head, r))


def annex(q):
    """Base-2021 weights INE published for 2021-2023 («Anexo trimestre … con factor base 2021»)."""
    p = RAW / "epa" / f"datos_{q}_a.zip"
    if not p.exists():
        return None
    z = zipfile.ZipFile(p)
    name = [n for n in z.namelist() if n.startswith("CSV/") and n.lower().endswith(".tab")][0]
    rd = csv.reader(io.StringIO(z.read(name).decode("latin-1")), delimiter="\t")
    head = [h.strip('"') for h in next(rd)]
    out = {}
    for r in rd:
        if r:
            d = dict(zip(head, r))
            out[(d["CICLO"], d["CCAA"], d["NVIVI"], d["NIVEL"], d["NPERS"])] = float(d["FACB2021"] or 0)
    return out


def main():
    out = []
    for q in QUARTERS:
        ax = annex(q)
        for wname in (("FACTOREL", "FACB2021") if ax else ("FACTOREL",)):
            tot = em = 0.0
            n = 0
            for r in epa(q):
                if r["EDAD1"].strip() not in ("16", "20", "25"):
                    continue
                if wname == "FACTOREL":
                    w = float(r["FACTOREL"] or 0)
                else:
                    w = ax.get((r["CICLO"], r["CCAA"], r["NVIVI"], r["NIVEL"], r["NPERS"]), 0.0)
                nopar = r["NPADRE"].strip() in ("00", "") and r["NMADRE"].strip() in ("00", "")
                tot += w; em += w * nopar; n += 1
            src = "EPA" if wname == "FACTOREL" else "EPA, base-2021 weights (INE annex)"
            out.append({"source": src, "period": f"20{q[2:]}Q{q[0]}", "age_band": "16-29", "n": n,
                        "population": round(tot), "emancipated": round(em), "emancipated_pct": round(100 * em / tot, 2)})
    for y, src in (("23", "EPA"), ("23", "EPA, base-2021 weights (INE annex)"), ("24", "EPA"), ("25", "EPA")):
        a, b = [r for r in out if r["period"] in (f"20{y}Q3", f"20{y}Q4") and r["source"] == src]
        out.append({"source": src, "period": f"20{y}H2", "age_band": "16-29", "n": a["n"] + b["n"],
                    "population": round((a["population"] + b["population"]) / 2),
                    "emancipated": round((a["emancipated"] + b["emancipated"]) / 2),
                    "emancipated_pct": round((a["emancipated_pct"] + b["emancipated_pct"]) / 2, 2)})
    with open(D / "living_with_parents.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["age_band"] == "16-29" and r["year"] in ("2023", "2024", "2025"):
                out.append({"source": f"ECV (age at {r['age_definition'].replace('_', ' ')})", "period": r["year"],
                            "age_band": "16-29", "n": r["n"], "population": r["pop"], "emancipated": "",
                            "emancipated_pct": r["emancipated_pct"]})
    cje = [("CJE 2S-2023 (EPA)", "2023H2", 17.0), ("CJE 2S-2024 (EPA)", "2024H2", 15.2), ("CJE 2025 (ECV)", "2025", 14.5),
           ("CJE 2025 (ECV), implied 2024: 14,5 + 1,13", "2024", 15.63)]
    for s, p, v in cje:
        out.append({"source": s, "period": p, "age_band": "16-29", "n": "", "population": "", "emancipated": "", "emancipated_pct": v})
    with open(D / "epa_emancipation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    for r in out:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
