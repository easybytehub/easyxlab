# SPDX-License-Identifier: Apache-2.0
"""Review items M2 and M4 (network, SPARQL): (1) how the portal describes the licence value
dcat-ap.de/def/licenses/other-closed; (2) the IDs of the datasets with an HVD category but without the ELI
(to measure duplicates). Writes data/half_tagged_ids.csv and data/other_closed_description.json."""
import csv
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sp = __import__("02_sparql")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DS = "http://data.europa.eu/88u/dataset/"
CAT = "http://data.europa.eu/88u/catalogue/"

q = "SELECT DISTINCT ?p ?o WHERE { <http://dcat-ap.de/def/licenses/other-closed> ?p ?o } LIMIT 200"
rows = sp.sparql(q)
json.dump({"triples": rows}, open(os.path.join(ROOT, "data", "other_closed_description.json"), "w"), indent=1)
sp.log_query("other-closed-description", q, len(rows))

NOELI = ("FILTER NOT EXISTS { ?d dcatap:applicableLegislation "
         "<http://data.europa.eu/eli/reg_impl/2023/138/oj> }")
h1 = json.load(open(os.path.join(ROOT, "data", "raw", "sparql_main.json")))["h1_by_catalogue"]
seen = {}
body = ""
for cat in sorted(h1):  # one query per catalogue: Virtuoso sorts at most 10,000 rows
    if cat == "none":
        body = sp.P + ("SELECT DISTINCT ?d WHERE { ?d a dcat:Dataset ; dcatap:hvdCategory ?c . " + NOELI +
                       " FILTER NOT EXISTS { ?k dcat:dataset ?d } } LIMIT 10000")
    else:
        body = sp.P + ("SELECT DISTINCT ?d WHERE { <" + CAT + cat + "> dcat:dataset ?d . ?d a dcat:Dataset ; "
                       "dcatap:hvdCategory ?c . " + NOELI + " } LIMIT 10000")
    for r in sp.sparql(body):
        d = r["d"]
        i = urllib.parse.unquote(d[len(DS):]) if d.startswith(DS) else d
        seen.setdefault(i, set()).add(cat)
with open(os.path.join(ROOT, "data", "half_tagged_ids.csv"), "w", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["dataset_id", "catalogue"])
    for i in sorted(seen):
        w.writerow([i, ";".join(sorted(seen[i]))])
sp.log_query("half-tagged-ids", "per catalogue: " + body, len(seen))
print("other-closed triples:", [(r["p"].rsplit("/", 1)[-1], r["o"][:80]) for r in rows])
print("half-tagged ids:", len(seen))
