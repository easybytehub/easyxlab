#!/usr/bin/env python3
"""Prior-work search (run once, 2026-10-03): OpenAlex, arXiv API, GitHub and Zenodo, through
politefetch (robots.txt first). Writes data/prior_work_search.json with the exact queries, the date
and the top hits (title, year, id). Results are read and summarised in the paper."""
import json
import os
import urllib.parse
from datetime import datetime, timezone

import politefetch as P

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

QUERIES = [
    "TDMRep text and data mining reservation protocol",
    "robots.txt AI crawlers news publishers",
    "text and data mining opt-out machine-readable Article 4(3)",
    "AI training opt-out robots.txt consent",
    "Content Signals robots.txt ai-train",
    "news publishers block GPTBot",
]


def main():
    s = P.Session(per_host=40)
    out = dict(run_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), sources={})
    oa = {}
    for q in QUERIES:
        u = "https://api.openalex.org/works?per_page=8&search=" + urllib.parse.quote(q)
        r = s.get(u)
        hits = []
        if r["status"] == 200:
            j = json.loads(r["body"])
            hits = [dict(title=w.get("title"), year=w.get("publication_year"), id=w.get("doi") or w.get("id"),
                         cited_by=w.get("cited_by_count")) for w in j.get("results", [])]
        oa[q] = dict(url=u, status=r["status"], error=r["error"], hits=hits)
    out["sources"]["openalex"] = oa
    ax = {}
    for q in QUERIES[:4]:
        u = "https://export.arxiv.org/api/query?max_results=8&search_query=" + urllib.parse.quote("all:" + q)
        r = s.get(u)
        titles = []
        if r["status"] == 200:
            import re
            body = r["body"].decode("utf-8", "replace")
            for e in re.findall(r"<entry>(.*?)</entry>", body, re.S):
                t = re.search(r"<title>(.*?)</title>", e, re.S)
                i = re.search(r"<id>(.*?)</id>", e, re.S)
                titles.append(dict(title=re.sub(r"\s+", " ", t.group(1)).strip() if t else "", id=i.group(1) if i else ""))
        ax[q] = dict(url=u, status=r["status"], error=r["error"], hits=titles)
    out["sources"]["arxiv"] = ax
    for name, u in [("arxiv_2407.14933", "https://export.arxiv.org/api/query?id_list=2407.14933"),
                    ("arxiv_2510.10315", "https://export.arxiv.org/api/query?id_list=2510.10315"),
                    ("github_tdmrep", "https://api.github.com/search/repositories?q=tdmrep&per_page=10"),
                    ("github_aicrawl", "https://api.github.com/search/repositories?q=ai+crawler+robots.txt+census&per_page=10"),
                    ("github_aicrawl_census", "https://api.github.com/repos/mxdangelo/aicrawl-census"),
                    ("zenodo_radar", "https://zenodo.org/api/records/22178283"),
                    ("zenodo_search", "https://zenodo.org/api/records?q=" + urllib.parse.quote('"tdmrep" OR "TDM reservation"') + "&size=10")]:
        r = s.get(u, headers={"Accept": "application/json, application/atom+xml;q=0.9"})
        body = (r["body"] or b"").decode("utf-8", "replace")
        out["sources"][name] = dict(url=u, status=r["status"], error=r["error"], body=body[:20000])
    json.dump(out, open(os.path.join(ROOT, "data", "raw", "prior_work_search_raw.json"), "w"), indent=1)
    slim = dict(run_utc=out["run_utc"], openalex={q: [h["title"] for h in v["hits"]] for q, v in oa.items()},
                arxiv={q: v["hits"] for q, v in ax.items()},
                other={k: dict(url=v["url"], status=v["status"], error=v["error"]) for k, v in out["sources"].items()
                       if k not in ("openalex", "arxiv")})
    json.dump(slim, open(os.path.join(ROOT, "data", "prior_work_search.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(slim, indent=1, ensure_ascii=False)[:9000])


if __name__ == "__main__":
    main()
