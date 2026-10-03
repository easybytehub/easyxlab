"""Step 2: prior-work search (arXiv API and OpenAlex API), logged with the exact queries and date.

Writes data/sources/prior_work_search.json (query, endpoint, date, hit count, top titles).
Raw responses go to data/raw/prior/ (not published). Offline: keeps the published log.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse

from common import DATA, OFFLINE, RAW, RobotsRefused, fetch, robots_check

OUT = DATA / "sources" / "prior_work_search.json"
ARXIV = [
    'all:"immutable releases"',
    'all:"GitHub Actions" AND all:immutable',
    'all:"GitHub Actions" AND all:pinning',
    'all:"GitHub Actions" AND all:SHA',
    'all:"GitHub Actions" AND all:"supply chain"',
    'all:"GitHub Actions" AND all:security AND all:workflows',
    'ti:"Time for Actions"',
    'ti:"Revisiting Security Practices for GitHub Actions"',
]
DBLP = ["GitHub Actions", "GitHub workflows security", "immutable releases", "GitHub CI workflows"]
OPENALEX = [
    '"immutable releases"',
    '"GitHub Actions" pinning',
    '"GitHub Actions" "commit SHA"',
    '"GitHub Actions" security workflows',
    '"Time for Actions"',
    '"Revisiting Security Practices for GitHub Actions Workflows"',
    '"Characterizing the Security of GitHub CI Workflows"',
]


def sanitize(log: list) -> list:
    """Published log: queries, dates, counts and work ids only. Titles of arbitrary search hits
    (for example Zenodo snapshots of personal repositories) can carry user names, so they stay in
    data/raw/prior/; the works we cite are listed with full references in paper.md."""
    return [{k: e.get(k) for k in ("endpoint", "query", "status", "utc", "total", "note") if e.get(k) is not None}
            | {"top_ids": [x.get("id") for x in e.get("top", [])]} for e in log]


def main() -> None:
    if OFFLINE:
        print("02_prior_work: offline; keeping", OUT.relative_to(DATA.parent))
        return
    (RAW / "prior").mkdir(parents=True, exist_ok=True)
    log = []
    for q in ARXIV:
        try:
            robots_check("https://export.arxiv.org/api/query")
        except RobotsRefused as e:
            log.append({"endpoint": "export.arxiv.org/api/query", "query": q, "status": None,
                        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "total": None, "note": "not queried: robots.txt disallows all user agents", "top": []})
            continue
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"search_query": q, "start": 0, "max_results": 25, "sortBy": "relevance"})
        s, _, b = fetch(url)
        t = b.decode("utf-8", "replace")
        total = re.search(r"<opensearch:totalResults[^>]*>(\d+)<", t)
        entries = re.findall(r"<entry>.*?<id>(.*?)</id>.*?<published>(.*?)</published>.*?<title>(.*?)</title>", t, re.S)
        log.append({"endpoint": "export.arxiv.org/api/query", "query": q, "status": s,
                    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "total": int(total.group(1)) if total else None,
                    "top": [{"id": i.rsplit("/", 1)[-1], "published": p[:10], "title": re.sub(r"\s+", " ", ti).strip()}
                            for i, p, ti in entries[:25]]})
        time.sleep(3)  # arXiv API asks for 3 s between calls
    for q in OPENALEX:
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(
            {"search": q, "per-page": 25, "mailto": "contact@easybyte.es"})
        s, _, b = fetch(url)
        js = json.loads(b) if s == 200 else {}
        log.append({"endpoint": "api.openalex.org/works?search=", "query": q, "status": s,
                    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "total": (js.get("meta") or {}).get("count"),
                    "top": [{"id": w["id"].rsplit("/", 1)[-1], "doi": w.get("doi"), "year": w.get("publication_year"),
                             "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
                             "title": w.get("display_name")} for w in js.get("results", [])]})
    for q in DBLP:
        url = "https://dblp.org/search/publ/api?" + urllib.parse.urlencode({"q": q, "format": "json", "h": 100})
        try:
            s, _, b = fetch(url)
        except RobotsRefused as e:
            log.append({"endpoint": "dblp.org/search/publ/api", "query": q, "status": None, "total": None,
                        "note": str(e), "top": []})
            continue
        hits = ((json.loads(b) if s == 200 else {}).get("result") or {}).get("hits") or {}
        log.append({"endpoint": "dblp.org/search/publ/api", "query": q, "status": s,
                    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "total": int(hits.get("@total", 0)),
                    "top": [{"id": h["info"].get("key"), "year": h["info"].get("year"), "venue": h["info"].get("venue"),
                             "doi": h["info"].get("doi"), "title": h["info"].get("title")} for h in hits.get("hit", [])]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    (RAW / "prior" / "search_log_full.json").write_text(json.dumps(log, indent=1, ensure_ascii=False))
    OUT.write_text(json.dumps(sanitize(log), indent=1, ensure_ascii=False) + "\n")
    for e in log:
        print(f"{e['endpoint']} | {e['query']} | {e['total']}")
        for x in e["top"][:8]:
            print("    ", x.get("published") or x.get("year"), x["id"], (x.get("venue") or "")[:30], "|", x["title"][:110])


if __name__ == "__main__":
    main()
