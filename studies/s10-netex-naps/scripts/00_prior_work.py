#!/usr/bin/env python3
"""S10 step 0b — prior-work searches (2026-10-02/03). Parses the raw API responses saved in
work/docs/prior/ (arXiv, Crossref, Semantic Scholar, GitHub code search) into data/prior_work.csv.
`--fetch` re-runs the queries (curl, polite pauses)."""
import csv, json, os, re, subprocess, sys, time
S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(S, "work", "docs", "prior"); os.makedirs(P, exist_ok=True)
UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
Q = [("arXiv", "all:NeTEx", "arxiv_netex.xml", "http://export.arxiv.org/api/query?search_query=all:NeTEx&max_results=50"),
     ("arXiv", 'all:"national access point" AND all:transport', "arxiv_nap.xml",
      "http://export.arxiv.org/api/query?search_query=all:%22national%20access%20point%22%20AND%20all:transport&max_results=50"),
     ("arXiv", "all:MMTIS", "arxiv_mmtis.xml", "http://export.arxiv.org/api/query?search_query=all:MMTIS&max_results=50"),
     ("Crossref", "NeTEx public transport data validation", "cr_netex.json",
      "https://api.crossref.org/works?query.bibliographic=NeTEx+public+transport+data+validation&rows=15&select=title,DOI,issued,container-title"),
     ("Crossref", "national access point multimodal travel information services regulation 2017/1926", "cr_nap.json",
      "https://api.crossref.org/works?query.bibliographic=national+access+point+multimodal+travel+information+services+regulation+2017%2F1926&rows=15&select=title,DOI,issued,container-title"),
     ("Semantic Scholar", "NeTEx public transport", "ss_netex.json",
      "https://api.semanticscholar.org/graph/v1/paper/search?query=NeTEx+public+transport&fields=title,year,venue,externalIds&limit=20"),
     ("Semantic Scholar", "national access points multimodal travel information services", "ss_nap.json",
      "https://api.semanticscholar.org/graph/v1/paper/search?query=national+access+points+multimodal+travel+information+services&fields=title,year,venue,externalIds&limit=20")]
if "--fetch" in sys.argv:
    for _, _, fn, url in Q:
        subprocess.run(["curl", "-sL", "-A", UA, "--max-time", "60", "-o", os.path.join(P, fn), url]); time.sleep(3)
rows = []
for api, query, fn, url in Q:
    t = open(os.path.join(P, fn), errors="ignore").read()
    if api == "arXiv":
        tot = re.search(r"<opensearch:totalResults[^>]*>(\d+)", t).group(1)
        items = [(re.search(r"<id>(.*?)</id>", e).group(1).split("/")[-1], re.sub(r"\s+", " ", re.search(r"<title>(.*?)</title>", e, re.S).group(1)))
                 for e in re.findall(r"<entry>(.*?)</entry>", t, re.S)]
    elif api == "Crossref":
        d = json.loads(t)["message"]; tot = d["total-results"]
        items = [(it["DOI"], (it.get("title") or [""])[0]) for it in d["items"][:15]]
    else:
        try:
            d = json.loads(t); tot = d.get("total", "no data"); items = [((x.get("externalIds") or {}).get("DOI", ""), x["title"]) for x in d.get("data", [])]
        except Exception:
            tot, items = "no data (rate-limited without key)", []
    rows.append(dict(api=api, query=query, total=tot, top=" | ".join(f"{i} {ti[:90]}" for i, ti in items[:5])))
gh = open(os.path.join(P, "gh_transport_site.txt")).read().split("\n")
rows.append(dict(api="GitHub code search", query="netex repo:etalab/transport-site validator", total=gh[0], top=" | ".join(gh[1:6])))
with open(os.path.join(S, "data", "prior_work.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["api", "query", "total", "top"]); w.writeheader(); w.writerows(rows)
for r in rows:
    print(r["api"], "|", r["query"], "|", r["total"])
