#!/usr/bin/env python3
"""Step 1 - freeze a snapshot of Wikidata drug and disease labels.

Drugs    = every item with at least one ATC code statement (P267, any rank).
Diseases = every item with an ICD-10 (P494) or ICD-11 MMS (P7329) statement.
Chronic  = 34 chronic diseases named in the earlier review (legacy/diseases.py),
           resolved by English label, highest sitelink count wins.

For each item we store lastrevid (schema:version) and dateModified, so the dataset is
pinned to exact revisions. Output (CC0, derived from Wikidata):
  data/frozen/drugs.jsonl, data/frozen/diseases.jsonl, data/frozen/extract_meta.json
"""
import json, os, sys, time, collections
sys.path.insert(0, os.path.dirname(__file__))
from wd import q, qid, chunks, LANGS, LF, UA, ENDPOINT

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "frozen")
os.makedirs(OUT, exist_ok=True)
LANGS_X = LANGS + ["mul"]          # "mul" = default-for-all-languages label (context only)
LFX = ",".join(f'"{l}"' for l in LANGS_X)
WIKIS = ",".join(f"<https://{l}.wikipedia.org/>" for l in LANGS)
CHRONIC = ["type 1 diabetes", "type 2 diabetes", "hypertension", "asthma",
           "chronic obstructive pulmonary disease", "epilepsy", "HIV/AIDS", "heart failure",
           "chronic kidney disease", "hypothyroidism", "major depressive disorder", "schizophrenia",
           "sickle cell disease", "thalassemia", "coronary artery disease", "atrial fibrillation",
           "rheumatoid arthritis", "Crohn's disease", "ulcerative colitis", "multiple sclerosis",
           "Parkinson's disease", "Alzheimer's disease", "cystic fibrosis", "haemophilia A", "obesity",
           "osteoporosis", "psoriasis", "gout", "bipolar disorder", "hepatitis B", "hyperthyroidism",
           "migraine", "coeliac disease", "glaucoma"]
RANK = lambda u: u.rsplit("#", 1)[-1].replace("Rank", "").lower()
N_QUERIES = [0]


def Q(s):
    N_QUERIES[0] += 1
    return q(s)


def labels_aliases(items, rec):
    for ch in chunks(items, 400):
        vals = " ".join(f"wd:{i}" for i in ch)
        for b in Q(f"SELECT ?item ?l WHERE {{ VALUES ?item {{ {vals} }} ?item rdfs:label ?l. "
                   f"FILTER(LANG(?l) IN ({LFX})) }}"):
            rec[qid(b["item"]["value"])]["labels"][b["l"]["xml:lang"]] = b["l"]["value"]
        for b in Q(f"SELECT ?item ?l WHERE {{ VALUES ?item {{ {vals} }} ?item skos:altLabel ?l. "
                   f"FILTER(LANG(?l) IN ({LFX})) }}"):
            rec[qid(b["item"]["value"])]["aliases"].setdefault(b["l"]["xml:lang"], []).append(b["l"]["value"])
        print(f"  labels/aliases {len(ch)} items", file=sys.stderr)


def main():
    t0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # ---------------- drugs ----------------
    rec = {}
    for b in Q("""SELECT ?item ?atc ?rank ?end ?rev ?mod ?sl WHERE {
        ?item p:P267 ?st. ?st ps:P267 ?atc; wikibase:rank ?rank. OPTIONAL { ?st pq:P582 ?end }
        ?item schema:version ?rev; schema:dateModified ?mod; wikibase:sitelinks ?sl }"""):
        i = qid(b["item"]["value"])
        r = rec.setdefault(i, {"qid": i, "lastrevid": int(b["rev"]["value"]), "modified": b["mod"]["value"],
                               "sitelinks": int(b["sl"]["value"]), "atc": [], "labels": {}, "aliases": {},
                               "inn": {}, "p31": [], "p279": [], "wiki": {}})
        a = {"code": b["atc"]["value"], "rank": RANK(b["rank"]["value"])}
        if "end" in b:
            a["end"] = b["end"]["value"][:10]
        if a not in r["atc"]:
            r["atc"].append(a)
    items = sorted(rec)
    print(f"drugs: {len(items)} items", file=sys.stderr)
    labels_aliases(items, rec)
    for ch in chunks(items, 400):
        vals = " ".join(f"wd:{i}" for i in ch)
        for b in Q(f"""SELECT ?item ?p ?v WHERE {{ VALUES ?item {{ {vals} }}
            {{ ?item p:P2275 ?s. ?s ps:P2275 ?v. ?s wikibase:rank ?r FILTER(?r != wikibase:DeprecatedRank) BIND("inn" AS ?p) }}
            UNION {{ ?item wdt:P31 ?v BIND("p31" AS ?p) }} UNION {{ ?item wdt:P279 ?v BIND("p279" AS ?p) }} }}"""):
            r = rec[qid(b["item"]["value"])]
            if b["p"]["value"] == "inn":
                r["inn"].setdefault(b["v"].get("xml:lang", "?"), []).append(b["v"]["value"])
            else:
                r[b["p"]["value"]].append(qid(b["v"]["value"]))
        for b in Q(f"""SELECT ?item ?w ?t WHERE {{ VALUES ?item {{ {vals} }}
            ?a schema:about ?item; schema:isPartOf ?w; schema:name ?t. FILTER(?w IN ({WIKIS})) }}"""):
            lang = b["w"]["value"].split("//")[1].split(".")[0]
            rec[qid(b["item"]["value"])]["wiki"][lang] = b["t"]["value"]
        print(f"  inn/p31/wiki {len(ch)} items", file=sys.stderr)
    with open(os.path.join(OUT, "drugs.jsonl"), "w") as f:
        for i in items:
            f.write(json.dumps(rec[i], ensure_ascii=False, sort_keys=True) + "\n")

    # ---------------- diseases ----------------
    dis = {}
    for prop, key in (("P494", "icd10"), ("P7329", "icd11")):
        for b in Q(f"""SELECT ?item ?v ?rank ?rev ?mod WHERE {{ ?item p:{prop} ?st. ?st ps:{prop} ?v;
            wikibase:rank ?rank. ?item schema:version ?rev; schema:dateModified ?mod }}"""):
            i = qid(b["item"]["value"])
            r = dis.setdefault(i, {"qid": i, "lastrevid": int(b["rev"]["value"]), "modified": b["mod"]["value"],
                                   "icd10": [], "icd11": [], "labels": {}, "aliases": {}, "chronic": None})
            v = {"v": b["v"]["value"], "rank": RANK(b["rank"]["value"])}
            if v not in r[key]:
                r[key].append(v)
    vals = " ".join(f'"{n}"@en' for n in CHRONIC)
    best = {}
    for b in Q(f"""SELECT ?name ?item ?sl ?rev ?mod WHERE {{ VALUES ?name {{ {vals} }} ?item rdfs:label ?name;
        wikibase:sitelinks ?sl; schema:version ?rev; schema:dateModified ?mod }}"""):
        n, sl = b["name"]["value"], int(b["sl"]["value"])
        if n not in best or sl > best[n][1]:
            best[n] = (qid(b["item"]["value"]), sl, int(b["rev"]["value"]), b["mod"]["value"])
    for n, (i, sl, rev, mod) in best.items():
        dis.setdefault(i, {"qid": i, "lastrevid": rev, "modified": mod, "icd10": [], "icd11": [],
                           "labels": {}, "aliases": {}, "chronic": None})["chronic"] = n
    ditems = sorted(dis)
    print(f"diseases: {len(ditems)} items; chronic resolved {len(best)}/{len(CHRONIC)}", file=sys.stderr)
    labels_aliases(ditems, dis)
    with open(os.path.join(OUT, "diseases.jsonl"), "w") as f:
        for i in ditems:
            f.write(json.dumps(dis[i], ensure_ascii=False, sort_keys=True) + "\n")

    meta = {"extracted_at_utc_start": t0,
            "extracted_at_utc_end": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "endpoint": ENDPOINT, "user_agent": UA, "languages": LANGS_X, "n_queries": N_QUERIES[0],
            "n_drug_items": len(items), "n_disease_items": len(ditems),
            "chronic_unresolved": [n for n in CHRONIC if n not in best],
            "max_lastrevid_drugs": max(rec[i]["lastrevid"] for i in items),
            "license": "CC0 1.0 (data derived from Wikidata)"}
    json.dump(meta, open(os.path.join(OUT, "extract_meta.json"), "w"), indent=2)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
