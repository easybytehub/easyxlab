#!/usr/bin/env python3
"""Literature search for the Prior work section: arXiv, Crossref and Semantic Scholar APIs (no web search).
Writes data/prior_work_search.csv (source, query, rank, title, year, id) and keeps raw responses in private/prior_work/."""
import csv, json, re, time, urllib.parse, urllib.request
from pathlib import Path
R = Path(__file__).resolve().parent.parent
RAW = R / "private/prior_work"; RAW.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "EasyxLab-S7/0.1 (research; https://github.com/easybytehub/easyxlab)"}
Q = ["AI Overviews accuracy", "Google AI Overviews audit", "AI Overviews legal questions",
     "generative search engine legal answers", "LLM tax questions accuracy", "generative search outdated information",
     "temporal staleness retrieval-augmented generation", "search engine generative answers regulatory compliance questions"]
def get(url):
    for i in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode("utf-8", "replace")
        except Exception as e:
            err = e; time.sleep(4 * (i + 1))
    return f"ERROR {err}"
rows = []
for qi, q in enumerate(Q):
    # arXiv
    x = get("https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": f'all:"{q}"' if len(q.split()) <= 3 else "all:" + " AND all:".join(q.split()), "max_results": 10, "sortBy": "relevance"}))
    (RAW / f"arxiv_{qi}.xml").write_text(x)
    for k, e in enumerate(x.split("<entry>")[1:], 1):
        t = re.sub(r"\s+", " ", re.search(r"<title>(.*?)</title>", e, re.S).group(1)).strip()
        rows.append({"source": "arXiv", "query": q, "rank": k, "title": t, "year": re.search(r"<published>(\d{4})", e).group(1),
                     "id": re.search(r"<id>(.*?)</id>", e).group(1)})
    time.sleep(3)
    # Crossref
    c = get("https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": q, "rows": 8, "filter": "from-pub-date:2024-05-01", "select": "DOI,title,issued,container-title"}))
    (RAW / f"crossref_{qi}.json").write_text(c)
    try:
        for k, it in enumerate(json.loads(c)["message"]["items"], 1):
            rows.append({"source": "Crossref", "query": q, "rank": k, "title": (it.get("title") or [""])[0], "year": (it.get("issued", {}).get("date-parts") or [[None]])[0][0], "id": "doi:" + it["DOI"]})
    except Exception:
        pass
    # Semantic Scholar
    s = get("https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode({"query": q, "limit": 8, "fields": "title,year,externalIds,citationCount", "year": "2024-"}))
    (RAW / f"s2_{qi}.json").write_text(s)
    try:
        for k, it in enumerate(json.loads(s).get("data", []), 1):
            ex = it.get("externalIds") or {}
            rows.append({"source": "Semantic Scholar", "query": q, "rank": k, "title": it["title"], "year": it.get("year"),
                         "id": ("arXiv:" + ex["ArXiv"]) if "ArXiv" in ex else ("doi:" + ex["DOI"]) if "DOI" in ex else it.get("paperId")})
    except Exception:
        pass
    time.sleep(3)
with open(R / "data/prior_work_search.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["source", "query", "rank", "title", "year", "id"]); w.writeheader(); w.writerows(rows)
from collections import Counter
print("searched", time.strftime("%Y-%m-%d"), Counter(r["source"] for r in rows))
seen = set()
for r in rows:
    k = r["title"].lower()[:80]
    if k in seen: continue
    seen.add(k)
    if re.search(r"overview|generative (search|engine)|answer engine|legal|tax|law|outdated|stale|temporal|fresh|time-sensitive|regulat", r["title"], re.I):
        print(f"[{r['source'][:5]}|{r['query'][:22]}] {r['year']} {r['id']} :: {r['title'][:130]}")
