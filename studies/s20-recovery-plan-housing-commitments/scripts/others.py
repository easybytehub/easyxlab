#!/usr/bin/env python3
"""Context: the other member states whose plans were amended in the same closing round as
Spain's (Council documents of 20-25 August 2026). For each decision (ST ... INIT, the text
prepared for adoption), the recitals that name a housing measure, with the stated reason.
Output: data/other_states_aug2026.csv. Only recitals are read: this is a pointer to where
housing measures were also amended, not a measurement of how much.
"""
import csv, re, subprocess
from s20lib import DATA, RAW, WORK
from extract import reason_label

HOUSING = re.compile(r"housing|dwelling", re.I)


def text(doc):
    out = WORK / "council_txt" / f"{doc}.txt"
    if not out.exists():
        subprocess.run(["pdftotext", "-enc", "UTF-8", str(RAW / "others" / doc / "DOC_1.pdf"), str(out)], check=True, timeout=240)
    return re.sub(r"\s+", " ", out.read_text(encoding="utf-8"))


def main():
    docs = [r["id"].split(":", 1)[1] for r in csv.DictReader(open(RAW / "sparql_council_aug2026.csv", encoding="utf-8"))
            if r["id"].endswith("_INIT")]
    dates = {r["id"].split(":", 1)[1]: r["date"] for r in csv.DictReader(open(RAW / "sparql_council_aug2026.csv", encoding="utf-8"))}
    out = []
    for doc in sorted(docs):
        t = text(doc)
        country = re.search(r"recovery and resilience plan for ([A-Z][a-z]+)", t).group(1)
        pre = t.split("HAS ADOPTED THIS DECISION")[0]
        parts = re.split(r"\s\((\d{1,2})\)\s", pre)
        n_hits = 0
        for i in range(1, len(parts) - 1, 2):
            num, body = int(parts[i]), parts[i + 1]
            if not HOUSING.search(body):
                continue
            # the housing measure names quoted in the recital
            names = sorted({m.group(1).strip() for m in re.finditer(r"\(([^()]*?(?:[Hh]ousing|[Dd]welling)[^()]*?)\)", body)}
                           | {m.group(1).strip() for m in re.finditer(r"‘([^‘’]*?(?:[Hh]ousing|[Dd]welling)[^‘’]*?)’", body)})
            first = re.split(r"(?<=\.)\s", body, maxsplit=1)[0]
            out.append({"council_doc": doc, "doc_date": dates.get(doc, ""), "country": country, "recital": num,
                        "reason_label": reason_label(first), "housing_measures_named": " | ".join(names),
                        "first_sentence": first[:500]})
            n_hits += 1
        if not n_hits:
            out.append({"council_doc": doc, "doc_date": dates.get(doc, ""), "country": country, "recital": "",
                        "reason_label": "", "housing_measures_named": "", "first_sentence": "(no recital names a housing measure)"})
        print(doc, country, n_hits, flush=True)
    with open(DATA / "other_states_aug2026.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)


if __name__ == "__main__":
    main()
