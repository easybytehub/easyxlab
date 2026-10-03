# SPDX-License-Identifier: Apache-2.0
"""RDF checks added after freezing (METHOD.md §9, deviations D2 and the rule-5 sample):
(1) what the Czech per-distribution terms-of-use nodes say (SPARQL);
(2) 50 random 'no licence in the RDF' datasets re-read from the portal's repository API (.ttl).
Writes data/raw/rdf_checks.json."""
import json
import os
import random
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch  # noqa: E402

sp = __import__("02_sparql")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
ELI = "<http://data.europa.eu/eli/reg_impl/2023/138/oj>"

q = sp.P + ("SELECT ?p ?o (COUNT(DISTINCT ?x) AS ?n) WHERE { ?cat dcat:dataset ?d . "
            "FILTER(?cat = <http://data.europa.eu/88u/catalogue/nkod-opendata-cz>) "
            f"?d dcatap:applicableLegislation {ELI} ; dcat:distribution ?x . ?x dct:license ?t . ?t ?p ?o . "
            "FILTER(isIRI(?o)) } GROUP BY ?p ?o ORDER BY DESC(?n) LIMIT 60")
cz = [{"p": r["p"], "o": r["o"], "n": int(r["n"])} for r in sp.sparql(q)]
qn = sp.P + ("SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE { ?cat dcat:dataset ?d . "
             "FILTER(?cat = <http://data.europa.eu/88u/catalogue/nkod-opendata-cz>) "
             f"?d dcatap:applicableLegislation {ELI} ; dcat:distribution ?x . }}")
cz_n = int(sp.sparql(qn)[0]["n"])

conf = json.load(open(os.path.join(RAW, "sparql_licence_confirm.json")))["confirmation"]
confirmed = sorted(k for k, v in conf.items() if not (v["distLic"] or v["dsLic"] or v["rights"]))
sample = random.Random(17).sample(confirmed, 50)
rows = []
for i in sample:
    u = "https://data.europa.eu/api/hub/repo/datasets/" + urllib.parse.quote(i, safe="~-._") + ".ttl"
    r = fetch.get(u, headers={"Accept": "text/turtle"}, max_bytes=20_000_000, timeout=60)
    t = r.body.decode("utf-8", "replace") if r.status == 200 else ""
    rows.append({"id": i, "status": r.status,
                 "license": len(re.findall(r"\bdct:license\b|purl.org/dc/terms/license", t)),
                 "rights": len(re.findall(r"\bdct:rights\b|purl.org/dc/terms/rights", t)),
                 "accessRights": len(re.findall(r"\bdct:accessRights\b", t))})
json.dump({"cz_terms_of_use": cz, "cz_eli_distributions": cz_n, "ttl_sample": rows,
           "ttl_sample_population": len(confirmed)}, open(os.path.join(RAW, "rdf_checks.json"), "w"), indent=1)
sp.log_query("cz-terms-of-use", q, len(cz))
sp.log_query("ttl-sample-50", "https://data.europa.eu/api/hub/repo/datasets/{id}.ttl for 50 ids (seed 17)",
             {"with_license": sum(1 for r in rows if r["license"]), "with_rights": sum(1 for r in rows if r["rights"]),
              "ok": sum(1 for r in rows if r["status"] == 200)})
for x in cz[:25]:
    print(x)
print("cz dists", cz_n)
print("ttl: ok", sum(1 for r in rows if r["status"] == 200), "license", sum(1 for r in rows if r["license"]),
      "rights", sum(1 for r in rows if r["rights"]), "accessRights", sum(1 for r in rows if r["accessRights"]))
