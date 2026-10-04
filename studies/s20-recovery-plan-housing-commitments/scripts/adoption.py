#!/usr/bin/env python3
"""Adoption of each version: Council document, adoption date and its source, and whether the
Council's text of the housing items is the Commission's text. Output: data/adoption.csv.

Sources, in order of preference:
  1. the Commission's own later proposals, which list the adoption dates of all earlier
     decisions in recital 1 (COM(2026) 435 lists every adoption up to 12 June 2026);
  2. for the last version, which no later Commission text can list yet: the Council's
     document prepared for adoption (date and "of …") and the Spanish Government's statement
     on planderecuperacion.gob.es.
"""
import csv, re
from s20lib import DATA, RAW, VERSIONS
from extract import annex_and_decision, recitals
from council_compare import ANNEX
from fetch import COUNCIL_DOCS
import htmltext

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def iso(d):
    import datetime
    return datetime.datetime.strptime(d, "%d %B %Y").date().isoformat()


def main():
    # 1. dates listed by the latest proposal
    _, dec = annex_and_decision(VERSIONS[-1][1])
    r1 = recitals(dec)[0][1]
    first = re.search(r"On (\d{1,2} (?:%s) \d{4}), the Council approved" % MONTHS, r1).group(1)
    amend = re.search(r"was amended by the Council Implementing Decisions of (.*?)\.$", r1).group(1)
    dates = re.findall(r"\d{1,2} (?:%s) \d{4}" % MONTHS, amend)
    listed = [first] + dates
    assert len(listed) == len(VERSIONS) - 1, (listed, len(VERSIONS))
    # 2. Council documents and their dates
    cdocs = {r["id"].split(":", 1)[1]: r for r in csv.DictReader(open(RAW / "sparql_council_spain_all.csv", encoding="utf-8"))}
    reqs = {r["version"]: r for r in csv.DictReader(open(DATA / "requests.csv", encoding="utf-8"))}
    comp = list(csv.DictReader(open(DATA / "council_vs_proposal.csv", encoding="utf-8")))
    # 3. the Spanish Government's statement on the last version
    gov = htmltext.text(str(RAW / "prtr" / "carlos-cuerpo-comparece-comision-mixta-UE-congreso-informar-cierre-plan-de-recuperacion-prtr.html"))
    gov = re.sub(r"\s+", " ", gov)
    m = re.search(r"El 27 de agosto el Consejo adoptó la adenda técnica de cierre[^.]*\.", gov)
    gov_sentence = m.group(0) if m else ""
    gov7 = htmltext.text(str(RAW / "prtr" / "gobierno-pone-marcha-inyeccion-13300-millones-ico-activar-fondo-espana-crece-prtr.html"))
    gov7 = re.sub(r"\s+", " ", gov7)
    m7 = re.search(r"Decisión de Ejecución del Consejo de 13 de enero de 2026", gov7)
    out = []
    for i, (label, celex, com, date) in enumerate(VERSIONS):
        docs = COUNCIL_DOCS.get(label, [])
        cd = "; ".join(f"ST {d.split('_')[1]}/{d.split('_')[2][2:]}{' ' + ' '.join(d.split('_')[3:]) if len(d.split('_')) > 3 else ''} ({cdocs[d]['date']})" for d in docs if d in cdocs)
        core = [c for c in comp if c["version"] == label and c["item"].split(" ")[0] in ("C2.I2", "C2.I7", "C2.R3", "C2.R7", "C2.summary")]
        same = sum(1 for c in core if c["identical"] in ("yes", "insertions-only"))
        if i < len(listed):
            adopted, status = iso(listed[i]), "adopted"
            src = f"{VERSIONS[-1][2]}, recital 1 (Commission)"
            lit = (f"On {first}, the Council approved the positive assessment" if i == 0
                   else f"…was amended by the Council Implementing Decisions of … {listed[i]} …")
            note = ""
            if label == "v7-2025d" and m7:
                note = ("The Spanish Government cites this decision as «Decisión de Ejecución del Consejo de 13 de enero de 2026» "
                        "(planderecuperacion.gob.es, 20-05-2026); the Commission's recitals give 20 January 2026. "
                        "No Council text of this version is in Cellar.")
        else:
            adopted, status = "2026-08-27", "reported adopted (Spanish Government); no EU record retrieved"
            src = "planderecuperacion.gob.es, 01-10-2026 (Government statement); Council ST 12355/26 INIT of 25-08-2026 is the text prepared for adoption («of …»)"
            lit = gov_sentence
            note = ("consilium.europa.eu disallows our client in robots.txt and returned HTTP 403 to a browser-like fetch; "
                    "Cellar records no Council adoption event for Spain's CID amendments; no later Commission text lists this decision yet.")
        out.append({
            "version": label, "com": com, "celex": celex, "proposed": date,
            "spain_request": reqs[label]["request_date"], "council_docs": cd,
            "adopted": adopted, "status": status, "source": src, "literal": lit,
            "core_housing_items_compared": len(core) if core else "",
            "core_items_identical_in_council_text": same if core else "",
            "note": note,
        })
    with open(DATA / "adoption.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    for o in out:
        print(o["version"], o["proposed"], o["spain_request"], o["adopted"], o["core_items_identical_in_council_text"], "/", o["core_housing_items_compared"])


if __name__ == "__main__":
    main()
