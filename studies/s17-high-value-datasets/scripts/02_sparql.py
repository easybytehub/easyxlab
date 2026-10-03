# SPDX-License-Identifier: Apache-2.0
"""SPARQL measurements on data.europa.eu (METHOD.md §2-§6). Writes data/raw/sparql_*.json."""
import gzip
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch  # noqa: E402
import hvd_rules as R  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
EP = "https://data.europa.eu/sparql"
P = ("PREFIX dcat:<http://www.w3.org/ns/dcat#> PREFIX dcatap:<http://data.europa.eu/r5r/> "
     "PREFIX dct:<http://purl.org/dc/terms/> ")
ELI = "<" + R.ELI + ">"
DS = "http://data.europa.eu/88u/dataset/"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log_query(kind, q, result):
    p = os.path.join(ROOT, "data", "queries.json")
    qs = json.load(open(p)) if os.path.exists(p) else []
    qs.append({"kind": kind, "endpoint": EP, "query": q, "utc": now(), "result": result})
    json.dump(qs, open(p, "w"), indent=1, ensure_ascii=False)


def sparql(q, timeout=300):
    data = urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"}).encode()
    r = fetch.get(EP, method="POST", data=data, max_bytes=200_000_000, timeout=timeout,
                  headers={"Accept": "application/sparql-results+json",
                           "Content-Type": "application/x-www-form-urlencoded"})
    if r.status != 200:
        raise RuntimeError(f"SPARQL {r.status} {r.error} {r.body[:300]!r}")
    return [{k: v["value"] for k, v in b.items()} for b in json.loads(r.body)["results"]["bindings"]]


def paged(q_body, var, page=10000):
    out, off = [], 0
    while True:
        rows = sparql(f"{q_body} ORDER BY ?{var} LIMIT {page} OFFSET {off}")
        out += rows
        if len(rows) < page:
            return out
        off += page


def main():
    p = os.path.join(ROOT, "data", "queries.json")
    if os.path.exists(p):  # re-runs replace this script's earlier entries
        qs = [x for x in json.load(open(p)) if x.get("endpoint") != EP]
        json.dump(qs, open(p, "w"), indent=1, ensure_ascii=False)
    res = {"utc_start": now()}
    # H1: HVD category without the exact ELI, by catalogue
    q = P + ("SELECT ?cat (COUNT(DISTINCT ?d) AS ?n) WHERE { ?d a dcat:Dataset ; dcatap:hvdCategory ?c . "
             f"FILTER NOT EXISTS {{ ?d dcatap:applicableLegislation {ELI} }} OPTIONAL {{ ?cat dcat:dataset ?d }} }} "
             "GROUP BY ?cat")
    rows = sparql(q)
    res["h1_by_catalogue"] = {(r.get("cat") or "none").rsplit("/", 1)[-1]: int(r["n"]) for r in rows}
    q2 = P + ("SELECT (COUNT(DISTINCT ?d) AS ?n) WHERE { ?d a dcat:Dataset ; dcatap:hvdCategory ?c . "
              f"FILTER NOT EXISTS {{ ?d dcatap:applicableLegislation {ELI} }} }}")
    res["h1_total"] = int(sparql(q2)[0]["n"])
    log_query("h1-category-without-eli", q2, res["h1_total"])
    log_query("h1-by-catalogue", q, len(rows))
    # exact ELI on datasets, with / without category
    q = P + ("SELECT ?hasCat (COUNT(DISTINCT ?d) AS ?n) WHERE { ?d a dcat:Dataset ; dcatap:applicableLegislation "
             f"{ELI} . BIND(EXISTS {{ ?d dcatap:hvdCategory ?c }} AS ?hasCat) }} GROUP BY ?hasCat")
    res["eli_datasets_by_category"] = {r["hasCat"]: int(r["n"]) for r in sparql(q)}
    log_query("eli-datasets-by-category", q, res["eli_datasets_by_category"])
    # H2: malformed ELI variants, by subject type
    q = P + ("SELECT ?l ?t (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s dcatap:applicableLegislation ?l . "
             "FILTER(?l != " + ELI + " && (CONTAINS(STR(?l),'2023/138') || CONTAINS(STR(?l),'32023R0138') || "
             "CONTAINS(LCASE(STR(?l)),'2023_138'))) OPTIONAL { ?s a ?t } } GROUP BY ?l ?t")
    res["h2_variants"] = [{"value": r["l"], "type": r.get("t"), "n": int(r["n"])} for r in sparql(q)]
    log_query("h2-malformed-eli", q, len(res["h2_variants"]))
    q = P + ("SELECT ?l ?cat (COUNT(DISTINCT ?d) AS ?n) WHERE { ?d a dcat:Dataset ; dcatap:applicableLegislation ?l . "
             "FILTER(?l != " + ELI + " && (CONTAINS(STR(?l),'2023/138') || CONTAINS(STR(?l),'32023R0138') || "
             "CONTAINS(LCASE(STR(?l)),'2023_138'))) FILTER NOT EXISTS { ?d dcatap:applicableLegislation " + ELI +
             " } OPTIONAL { ?cat dcat:dataset ?d } } GROUP BY ?l ?cat")
    res["h2_datasets_only_malformed"] = [{"value": r["l"], "catalogue": (r.get("cat") or "none").rsplit("/", 1)[-1],
                                          "n": int(r["n"])} for r in sparql(q)]
    log_query("h2-datasets-only-malformed", q, len(res["h2_datasets_only_malformed"]))
    # subjects carrying the exact ELI, by type (datasets, distributions, data services, series)
    q = P + f"SELECT ?t (COUNT(DISTINCT ?s) AS ?n) WHERE {{ ?s dcatap:applicableLegislation {ELI} . ?s a ?t }} GROUP BY ?t"
    res["eli_subjects_by_type"] = {r["t"]: int(r["n"]) for r in sparql(q)}
    log_query("eli-subjects-by-type", q, res["eli_subjects_by_type"])
    # API modelled in RDF: datasets with the ELI that are served by a DataService (direct or via distribution)
    body = P + ("SELECT DISTINCT ?d WHERE { ?d a dcat:Dataset ; dcatap:applicableLegislation " + ELI + " . "
                "{ ?s dcat:servesDataset ?d } UNION { ?d dcat:distribution ?x . ?x dcat:accessService ?s } }")
    served = paged(body, "d")
    res["api_served_datasets"] = sorted({r["d"][len(DS):] if r["d"].startswith(DS) else r["d"] for r in served})
    log_query("api-served-eli-datasets", body, len(res["api_served_datasets"]))
    json.dump(res, open(os.path.join(RAW, "sparql_main.json"), "w"), indent=1)

    # "No licence" confirmation (coordinator rule 5): datasets with no licence in any distribution of the index
    none_ids = []
    for line in gzip.open(os.path.join(RAW, "census.jsonl.gz"), "rt"):
        r = json.loads(line)
        cls = [R.licence_class((d.get("license") or {}).get("resource") or (d.get("license") or {}).get("id"))
               for d in (r.get("distributions") or [])]
        if R.dataset_licence_verdict(cls) == "none":
            none_ids.append(r["id"])
    conf = {}
    for i in range(0, len(none_ids), 150):
        chunk = none_ids[i:i + 150]
        vals = " ".join("<" + DS + urllib.parse.quote(x, safe="~-._") + ">" for x in chunk)
        q = P + ("SELECT ?d (BOUND(?dl) AS ?distLic) (BOUND(?sl) AS ?dsLic) (BOUND(?rr) AS ?rights) "
                 "(SAMPLE(?dl) AS ?dlv) (SAMPLE(?sl) AS ?slv) WHERE { VALUES ?d { " + vals + " } "
                 "OPTIONAL { ?d dcat:distribution ?x . ?x dct:license ?dl } OPTIONAL { ?d dct:license ?sl } "
                 "OPTIONAL { { ?d dct:rights ?rr } UNION { ?d dcat:distribution ?y . ?y dct:rights ?rr } } } "
                 "GROUP BY ?d ?dl ?sl ?rr")
        for r in sparql(q):
            k = r["d"][len(DS):]
            k = urllib.parse.unquote(k)
            c = conf.setdefault(k, {"distLic": False, "dsLic": False, "rights": False, "dl": None, "sl": None})
            c["distLic"] |= r.get("distLic") in ("1", "true")
            c["dsLic"] |= r.get("dsLic") in ("1", "true")
            c["rights"] |= r.get("rights") in ("1", "true")
            c["dl"] = c["dl"] or r.get("dlv")
            c["sl"] = c["sl"] or r.get("slv")
    missing = [x for x in none_ids if x not in conf]
    json.dump({"utc": now(), "none_in_index": len(none_ids), "confirmation": conf, "not_found_in_sparql": missing},
              open(os.path.join(RAW, "sparql_licence_confirm.json"), "w"), indent=1)
    log_query("licence-confirmation", "VALUES batches of 150 over the 'no licence in index' datasets "
              "(see scripts/02_sparql.py)", {"datasets": len(none_ids), "not_found": len(missing)})
    print(json.dumps({k: v for k, v in res.items() if k not in ("api_served_datasets", "h1_by_catalogue")}, indent=1)[:4000])
    print("served", len(res["api_served_datasets"]), "none_in_index", len(none_ids), "not found", len(missing))


if __name__ == "__main__":
    main()
