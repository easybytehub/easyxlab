"""S12: prior-work searches (Crossref, arXiv API, GitHub) and their summary in data/prior_work_search.csv.

  python scripts/prior_work_search.py          rebuild the CSV from work/prior/search.json
  python scripts/prior_work_search.py --run    run the searches again first (results will differ by date)

Crossref ≥ 1.1 s between requests, arXiv 3.1 s (its API terms ask for 3 s), GitHub via `gh`.
GitHub owners are withheld in the CSV; only counts and the relevant hits we cite are kept.
"""
import csv
import json, time, urllib.parse, urllib.request, datetime, subprocess, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAWJ = ROOT / "work" / "prior" / "search.json"
CITED = {"10.1016/j.cities.2019.102466", "10.4337/9781788116992.00017", "10.4337/9781788116992.00016",
         "10.3390/su13137485", "10.1145/3656156.3665128", "10.62659/cf2503101",
         "10.69592/979-13-7011-288-2-cap-1", "10.62659/cf2502901", "http://arxiv.org/abs/2604.21212v3",
         "http://arxiv.org/abs/2605.24849v1"}


def run():
    UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
    out = []
    def get(url):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    def now(): return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    crossref = ["desahucios estadística judicial", "lanzamientos practicados desahucios", "evictions Spain court statistics",
                "Ley Orgánica 1/2025 tribunales de instancia", "eviction statistics data quality",
                "court reorganization statistics structural break", "eviction moratorium Spain",
                "desahucios moratoria vulnerabilidad", "evictions Spain judicial data CGPJ",
                "administrative data eviction counts measurement error", "tribunales de instancia estadística",
                "medios adecuados de solución de controversias desahucio"]
    for q in crossref:
        url = "https://api.crossref.org/works?rows=20&select=DOI,title,issued,container-title&query=" + urllib.parse.quote(q)
        try:
            d = json.loads(get(url)); items = d["message"]["items"]
            hits = [{"doi": i.get("DOI"), "title": (i.get("title") or [""])[0], "year": (i.get("issued", {}).get("date-parts") or [[None]])[0][0]} for i in items]
            out.append({"source": "crossref", "query": q, "time": now(), "n": d["message"]["total-results"], "top": hits})
        except Exception as e:
            out.append({"source": "crossref", "query": q, "time": now(), "error": str(e)})
        time.sleep(1.1)
    arxiv = ['all:"eviction" AND all:"Spain"', 'all:evictions AND all:statistics', 'all:"court reform" AND all:statistics',
             'all:"judicial statistics"', 'all:"eviction moratorium"', 'all:"structural break" AND all:"administrative data" AND all:court']
    for q in arxiv:
        url = "http://export.arxiv.org/api/query?max_results=25&search_query=" + urllib.parse.quote(q)
        try:
            x = get(url).decode()
            n = int(re.search(r"<opensearch:totalResults[^>]*>(\d+)<", x).group(1))
            titles = re.findall(r"<entry>.*?<id>(.*?)</id>.*?<title>(.*?)</title>", x, re.S)
            out.append({"source": "arxiv", "query": q, "time": now(), "n": n,
                        "top": [{"id": i.strip(), "title": re.sub(r"\s+", " ", t).strip()} for i, t in titles]})
        except Exception as e:
            out.append({"source": "arxiv", "query": q, "time": now(), "error": str(e)})
        time.sleep(3.1)
    for q in ["lanzamientos CGPJ", "desahucios CGPJ", "desahucios", "evictions Spain", "poderjudicial estadistica",
              "tribunales de instancia", "estadistica judicial", "CGPJ"]:
        r = subprocess.run(["gh", "search", "repos", q, "--limit", "30", "--json", "fullName,description,updatedAt"], capture_output=True, text=True)
        try:
            items = json.loads(r.stdout or "[]")
            out.append({"source": "github-repos", "query": q, "time": now(), "n": len(items),
                        "top": [{"repo": i["fullName"], "description": (i.get("description") or "")[:200]} for i in items]})
        except Exception as e:
            out.append({"source": "github-repos", "query": q, "time": now(), "error": r.stderr[:300]})
        time.sleep(2)
    for q in ['"Lanzamientos por PJs"', '"lanzamientos practicados"', '"Efecto de la crisis en los organos judiciales"']:
        r = subprocess.run(["gh", "search", "code", q, "--limit", "30", "--json", "repository,path"], capture_output=True, text=True)
        try:
            items = json.loads(r.stdout or "[]")
            out.append({"source": "github-code", "query": q, "time": now(), "n": len(items),
                        "top": [{"repo": i["repository"]["nameWithOwner"], "path": i["path"]} for i in items]})
        except Exception as e:
            out.append({"source": "github-code", "query": q, "time": now(), "error": r.stderr[:300]})
        time.sleep(6)

    RAWJ.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(RAWJ, "w"), ensure_ascii=False, indent=1)


def to_csv():
    import json
    data = json.load(open(RAWJ, encoding="utf-8"))
    rows = []
    for x in data:
        top = x.get("top") or []
        cited = [t.get("doi") or t.get("id") for t in top if (t.get("doi") or t.get("id")) in CITED]
        rows.append({"source": x["source"], "query": x["query"], "time_utc": x["time"],
                     "results_reported": x.get("n", ""), "screened": len(top),
                     "relevant_cited": " ".join(cited), "error": x.get("error", "")})
    det = RAWJ.parent / "details.json"  # title lookups on Crossref for works we cite by name
    if det.exists():
        for q, v in json.load(open(det, encoding="utf-8")).items():
            if isinstance(v, list):
                rows.append({"source": "crossref-title-lookup", "query": q, "time_utc": "2026-10-04",
                             "results_reported": len(v), "screened": len(v), "relevant_cited": v[0]["doi"], "error": ""})
    with open(ROOT / "data" / "prior_work_search.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} searches -> data/prior_work_search.csv")


if __name__ == "__main__":
    import sys
    if "--run" in sys.argv:
        run()
    to_csv()
