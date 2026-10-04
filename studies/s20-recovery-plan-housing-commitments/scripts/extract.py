#!/usr/bin/env python3
"""Extract the housing commitments from every version of Spain's CID (Commission proposals,
XHTML from Cellar) into data/:

  data/housing_rows.csv      one row per version x housing milestone/target, literal cells
  data/housing_measures.csv  one row per version x housing measure: name, euro amounts, literal
                             description; plus the component-2 summary sentence
  data/reasons.csv           the recital of each proposal that names a housing measure, with
                             the stated reason (literal first sentence) and a reason label
  data/requests.csv          date of Spain's reasoned request quoted in each proposal
  data/texts/<version>/<measure>.txt   the literal texts (description + rows), one file each

Scope (fixed before the diff was run, see METHOD.md section 2): measures whose name,
description or milestones/targets mention social or affordable housing, social or affordable
rent, rental housing or the Housing Law. Four are housing measures (CORE); one is a
multi-sector fund that lists social and affordable housing among its priority areas (CONTEXT).
Measures matched only through the generic definition of a renovated dwelling ("may include,
where appropriate, social or public housing": C2.I1, C2.I3, C28.I1) are out of scope.
"""
import csv, json, re, sys
from s20lib import DATA, VERSIONS, version_docs
from cidparse import mt_rows, descriptions, plain_text
import differ

CORE = ["C2.I2", "C2.I7", "C2.R3", "C2.R7"]
CONTEXT = ["C13.I13"]
SCOPE = CORE + CONTEXT
SUMMARY_ID = "C2.summary"
KW = re.compile(r"social hous|social rent|affordable hous|affordable rent|affordable price|housing law|rental housing|public housing|right to housing", re.I)
# Short names used for the housing measures in recitals that do not give the measure id.
ALIASES = {"C2.I7": "Facility for the Promotion of Social Housing",
           "C2.R7": "programme of measures to promote the supply of rental housing",
           "C2.I2": "construction of social rented housing"}
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def annex_and_decision(celex):
    docs = version_docs(celex)
    annex = max(docs, key=lambda d: len(d[1]))[1]
    dec = [d for d in docs if d[0] == "DOC_1"][0][1]
    return annex, dec


def squash_date(day, month, year):
    return f"{int(day.replace(' ', ''))} {month} {year.replace(' ', '')}"


def iso(d):
    import datetime
    return datetime.datetime.strptime(d, "%d %B %Y").date().isoformat()


def request_date(dec_text):
    t = re.sub(r"\s+", " ", plain_text(dec_text))
    m = re.search(r"On ([\d ]{1,4}) (%s) ((?:\d ?){4}) ?, Spain (?:made a reasoned request|submitted)" % MONTHS, t)
    if not m:
        return "", ""
    d = squash_date(*m.groups())
    s = t[m.start(): t.find(".", m.end()) + 1]
    return iso(d), s


def recitals(dec_text):
    """[(number, text)] of the recitals: blocks that start with '(n)' before 'HAS ADOPTED'."""
    t = plain_text(dec_text)
    t = t.split("HAS ADOPTED THIS DECISION")[0]
    blocks, cur = [], None
    for line in t.split("\n"):
        m = re.match(r"^\((\d+)\)\s*(.*)$", line)
        if m:
            if cur:
                blocks.append(cur)
            cur = [int(m.group(1)), m.group(2)]
        elif cur:
            cur[1] += " " + line
    if cur:
        blocks.append(cur)
    return [(n, re.sub(r"\s+", " ", x).strip()) for n, x in blocks if x.strip()]


def id_pattern(mid):
    c, rest = mid.split(".")
    k, n = rest[0], rest[1:]
    comp = c[1:]
    return re.compile(r"C\s?%s\s?\.\s?%s\s?%s\b" % (comp, k, n))


REASONS = [
    ("inflation", r"because of inflation"),
    ("lack of demand", r"lack of demand"),
    ("supply chain / technical", r"supply chain constraints|unexpected technical difficulties|unforeseen technical difficulties"),
    ("insufficient applications", r"insufficient number of eligible applications"),
    ("better alternative", r"better alternative"),
    ("verification", r"unequivocal primary evidence|verification"),
    ("clerical error", r"clerical error"),
    ("resources freed up / reallocation", r"freed up|decrease in the level of implementation|increase the level of implementation"),
    ("loan support", r"loan support"),
    ("REPowerEU / new measures", r"REPowerEU|new measure|new reform"),
    ("country-specific recommendations", r"recommend"),
]


def reason_label(text):
    first = re.split(r"(?<=\.)\s", text, maxsplit=1)[0]
    for lab, pat in REASONS:
        if re.search(pat, first, re.I):
            return lab
    for lab, pat in REASONS:
        if re.search(pat, text, re.I):
            return lab
    return "other"


def summary_sentence(annex_text):
    t = re.sub(r"\s+", " ", plain_text(annex_text))
    m = re.search(r"c\)\s?construct at least ([\d ]+?) new dwellings[^;]*;", t)
    return (m.group(0), m.group(1).strip()) if m else ("", "")


def main():
    rows_out, meas_out, reas_out, req_out = [], [], [], []
    names_by_version = {}
    tdir = DATA / "texts"
    for label, celex, com, date in VERSIONS:
        annex, dec = annex_and_decision(celex)
        desc = descriptions(annex)
        names_by_version[label] = {m: desc[m][0] for m in SCOPE if m in desc}
        rows = [r for r in mt_rows(annex) if r["measure"] in SCOPE]
        # literal texts
        vdir = tdir / label
        vdir.mkdir(parents=True, exist_ok=True)
        for mid in SCOPE:
            parts = []
            if mid in desc:
                parts.append(f"## {mid} — {desc[mid][0]}\n\n{desc[mid][1]}\n")
            for r in rows:
                if r["measure"] == mid:
                    parts.append(f"### {r['number']} ({r.get('type','')}) {r.get('name','')}\n\n" + " | ".join(r["cells"]) + "\n")
            if parts:
                (vdir / f"{mid}.txt").write_text(
                    f"# {label} · {com} · proposed {date} · CELEX {celex}\n\n" + "\n".join(parts), encoding="utf-8")
        sent, n = summary_sentence(annex)
        if sent:
            (vdir / f"{SUMMARY_ID}.txt").write_text(f"# {label} · {com}\n\n{sent}\n", encoding="utf-8")
        for r in rows:
            rows_out.append({
                "version": label, "com": com, "proposed": date, "measure": r["measure"],
                "scope": "core" if r["measure"] in CORE else "context",
                "number": r["number"], "type": r.get("type", ""), "name": r.get("name", ""),
                "qual_indicator": r.get("qual_indicator", ""), "unit": r.get("unit", ""),
                "baseline": r.get("baseline", ""), "goal": r.get("goal", ""),
                "quarter": r.get("quarter", ""), "year": r.get("year", ""),
                "eur_amounts": ";".join(str(x) for x in differ.eur_amounts(r.get("description", ""))),
                "description": r.get("description", ""),
            })
        for mid in SCOPE:
            if mid not in desc:
                continue
            name, text = desc[mid]
            amts = differ.eur_amounts(text)
            meas_out.append({
                "version": label, "com": com, "proposed": date, "measure": mid,
                "scope": "core" if mid in CORE else "context", "name": name,
                "eur_amounts": ";".join(str(x) for x in amts),
                "n_words": len(text.split()), "description": text,
            })
        if sent:
            meas_out.append({"version": label, "com": com, "proposed": date, "measure": SUMMARY_ID,
                             "scope": "core", "name": "Component 2 summary, item c)",
                             "eur_amounts": "", "n_words": len(sent.split()), "description": sent})
        rd, rs = request_date(dec)
        req_out.append({"version": label, "com": com, "proposed": date, "request_date": rd, "literal": rs})
        for num, text in recitals(dec):
            for mid in SCOPE:
                pats = [id_pattern(mid)]
                nm = names_by_version[label].get(mid)
                alias = ALIASES.get(mid)
                hit = (any(p.search(text) for p in pats) or (nm and len(nm) > 15 and nm in text)
                       or (alias and alias.lower() in text.lower()))
                if not nm or nm not in text:
                    nm = alias if alias and alias.lower() in text.lower() else nm
                if not hit:
                    continue
                m = pats[0].search(text)
                pos = m.start() if m else text.lower().find((nm or "").lower())
                first = re.split(r"(?<=\.)\s", text, maxsplit=1)[0]
                reas_out.append({
                    "version": label, "com": com, "proposed": date, "measure": mid, "recital": num,
                    "reason_label": reason_label(text), "first_sentence": first[:600],
                    "context": text[max(0, pos - 200): pos + 250],
                })
        print(label, len(rows), "rows", sum(1 for m in SCOPE if m in desc), "measures", flush=True)

    def write(name, rows):
        with open(DATA / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    write("housing_rows.csv", rows_out)
    write("housing_measures.csv", meas_out)
    write("reasons.csv", reas_out)
    write("requests.csv", req_out)


if __name__ == "__main__":
    main()
