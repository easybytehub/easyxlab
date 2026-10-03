#!/usr/bin/env python3
"""Prior-work search for S4 (paper.md §2), run 2026-10-03.

  scripts/prior_work.py            # query the APIs; raw responses go to work/prior/ (git-ignored)
  scripts/prior_work.py --offline  # rebuild data/prior_work_search.csv and the digest from work/prior/
  scripts/prior_work.py --retry    # re-query only what failed (HTTP 503/429) on the previous run

One CSV row per query: query, source, date_utc, hits, screened, used, used_ids, notes.
`hits` is the total the API reports (Crossref's relevance search matches very loosely);
`screened` is how many top results were read by title; `used` says whether paper.md §2 cites one.
"""
import csv, json, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "work" / "prior"
OUT = ROOT / "data" / "prior_work_search.csv"
UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
MAILTO = "contact@easybyte.es"          # Crossref etiquette
PAUSE = {"export.arxiv.org": 3.1}       # arXiv API terms: at most one request every 3 s; 1 s per host elsewhere
SCREEN = 10

QUERIES = [
    ("arxiv", 'all:Wikidata AND all:quality AND all:labels'),
    ("arxiv", 'all:Wikidata AND all:multilingual AND all:labels'),
    ("arxiv", 'all:Wikidata AND all:medical'),
    ("arxiv", 'all:Wikidata AND all:drugs'),
    ("arxiv", 'all:Wikidata AND all:"constraint violations"'),
    ("arxiv", 'all:"knowledge graph" AND all:multilingual AND all:"label errors"'),
    ("crossref", "Wikidata data quality labels multilingual"),
    ("crossref", "Wikidata medical knowledge quality"),
    ("crossref", "Wikidata drug data quality"),
    ("crossref", "multilingual drug names translation errors international nonproprietary names"),
    ("crossref", "Wikidata RxNorm ATC mapping"),
    ("crossref", "accuracy of drug information in Wikipedia across languages"),
    ("s2", "Wikidata label quality multilingual"),
    ("s2", "Wikidata medical data quality"),
    ("s2", "Wikidata drugs ATC RxNorm"),
    ("europepmc", "Wikidata AND (drug OR medication OR pharmaceutical) AND (quality OR accuracy OR error)"),
    ("europepmc", "Wikidata AND (label OR labels) AND multilingual"),
    ("europepmc", "\"international nonproprietary names\" AND translation AND error"),
    ("gh-repos", "wikidata drug labels"),
    ("gh-repos", "wikidata medical quality"),
    ("gh-repos", "wikidata ATC code"),
    ("wikidata", "WikiProject Medicine label"),
    ("wikidata", "ATC code label error"),
    # second batch, same day, after reading the first results and web searches
    ("arxiv", 'all:Wikidata AND all:multilinguality'),
    ("arxiv", 'all:Wikidata AND all:biomedical'),
    ("crossref", "A glimpse into Babel multilingualism in Wikidata"),
    ("crossref", "Wikidata large-scale collaborative ontological medical database"),
    ("crossref", "logical constraints validate collaborative knowledge graphs COVID-19 Wikidata"),
    ("europepmc", "Wikidata AND (ICD OR \"ATC\" OR \"anatomical therapeutic chemical\")"),
    ("wikidata", "drug label wrong language"),
]

# Filled after reading the results: (source, query) -> ids cited in paper.md §2.
USED = {
    ("arxiv", 'all:Wikidata AND all:quality AND all:labels'): ["arXiv:2206.08709"],
    ("arxiv", 'all:Wikidata AND all:"constraint violations"'): ["arXiv:2107.00156"],
    ("arxiv", 'all:Wikidata AND all:biomedical'): ["arXiv:2004.03181"],
    ("crossref", "A glimpse into Babel multilingualism in Wikidata"): ["doi:10.1145/3125433.3125465"],
    ("crossref", "logical constraints validate collaborative knowledge graphs COVID-19 Wikidata"): ["doi:10.7717/peerj-cs.1085"],
    ("europepmc", "Wikidata AND (drug OR medication OR pharmaceutical) AND (quality OR accuracy OR error)"): ["doi:10.1016/j.heliyon.2024.e38448"],
}

# Searches and documents that did not go through this script (web search, Wikidata report pages fetched with the API).
MANUAL = [
    {"query": '"A glimpse into Babel" multilinguality Wikidata labels Kaffee OpenSym 2017', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 10, "screened": "",
     "used": 'yes', "used_ids": 'eprints.soton.ac.uk/413433', "notes": 'full text read (pdftotext)'},
    {"query": 'Turki "Wikidata: A large-scale collaborative ontological medical database" Journal of Biomedical Informatics 2019 data quality', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 10, "screened": "",
     "used": 'no', "used_ids": '', "notes": 'abstract taken from Europe PMC; describes medical content, no label audit'},
    {"query": 'Wikidata drug labels translation errors multilingual pharmaceutical names study OR WikiProject Medicine ATC INN quality', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 10, "screened": "",
     "used": 'no', "used_ids": '', "notes": 'results concern translated prescription labels, not Wikidata'},
    {"query": 'Wikidata:Database reports/Constraint violations/P494', "source": 'Wikidata API (page content)', "date_utc": '2026-10-03', "hits": '306', "screened": "",
     "used": 'yes', "used_ids": 'report generated 2026-09-23', "notes": 'hits = Format violations; also 543 single-value and 946 unique-value violations'},
    {"query": 'Wikidata:Database reports/Constraint violations/P267', "source": 'Wikidata API (page content)', "date_utc": '2026-10-03', "hits": '82', "screened": "",
     "used": 'yes', "used_ids": 'report generated 2026-09-17', "notes": 'hits = Unique value violations; 2 Format violations'},
    {"query": 'DOI:10.1016/j.jbi.2019.103292', "source": 'Europe PMC (core)', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'abstract; overview of medical content'},
    {"query": 'DOI:10.7717/peerj-cs.1085', "source": 'Europe PMC (core)', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'doi:10.7717/peerj-cs.1085', "notes": 'abstract'},
    {"query": 'DOI:10.1016/j.heliyon.2024.e38448', "source": 'Europe PMC (core)', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'doi:10.1016/j.heliyon.2024.e38448', "notes": 'abstract'},
    {"query": 'DOI:10.1371/journal.pone.0106930', "source": 'Europe PMC (core)', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'doi:10.1371/journal.pone.0106930', "notes": 'abstract; looked up by DOI as a known study (the Crossref query returned two earlier studies of drug information in Wikipedia)'},
    {"query": 'DOI:10.3163/1536-5050.99.4.010', "source": 'Europe PMC (core)', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'no abstract'},
    {"query": 'https://arxiv.org/pdf/2004.03181v1', "source": 'arXiv full text', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'arXiv:2004.03181', "notes": 'robots.txt allows /pdf (Crawl-delay 15 respected)'},
    {"query": 'https://eprints.soton.ac.uk/id/eprint/413433/1/Open_Sym_Short_Paper_Wikidata_Multilingual.pdf', "source": 'repository full text', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'doi:10.1145/3125433.3125465', "notes": 'HTTP 200'},
    {"query": 'arXiv id_list 2107.00156,2109.09405,2206.08709,2609.20057,2004.03181,2505.18136', "source": 'arXiv API', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'arXiv:2107.00156 arXiv:2206.08709 arXiv:2004.03181 arXiv:2609.20057', "notes": 'abstracts'},
]

_last = {}


def get(url):
    host = urllib.parse.urlsplit(url).netloc
    wait = PAUSE.get(host, 1.05) - (time.monotonic() - _last.get(host, -99))
    if wait > 0:
        time.sleep(wait)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # network error
        return None, str(e).encode()
    finally:
        _last[host] = time.monotonic()


def fetch(source, q):
    """Returns (status, body bytes, extension, retry note)."""
    if source == "arxiv":
        return (*get("https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"search_query": q, "max_results": 25, "sortBy": "relevance"})), "xml", "")
    if source == "crossref":
        return (*get("https://api.crossref.org/works?" + urllib.parse.urlencode(
            {"query.bibliographic": q, "rows": 20, "select": "DOI,title,issued,container-title,type", "mailto": MAILTO})), "json", "")
    if source == "s2":
        url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(
            {"query": q, "limit": 20, "fields": "title,year,externalIds,venue"})
        notes = []
        for back in (0, 10, 30, 60):
            time.sleep(back)
            st, body = get(url)
            if st != 429:
                break
            notes.append(f"429 (then waited {back}s)" if back else "429")
        return st, body, "json", "; ".join(notes)
    if source == "europepmc":
        return (*get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
            {"query": q, "format": "json", "pageSize": 20, "resultType": "lite"})), "json", "")
    if source == "wikidata":   # Wikidata project and project-talk namespaces
        return (*get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "query", "list": "search", "srsearch": q, "srnamespace": "4|5", "srlimit": 20,
             "srprop": "timestamp", "format": "json", "formatversion": 2, "maxlag": 5})), "json", "")
    if source in ("gh-repos", "gh-code"):
        kind = "repositories" if source == "gh-repos" else "code"
        time.sleep(7 if kind == "code" else 2)   # GitHub search rate limits (code: 10/min)
        r = subprocess.run(["gh", "api", "-X", "GET", f"search/{kind}", "-f", f"q={q}", "-f", "per_page=20"],
                           capture_output=True, text=True)
        return (200 if r.returncode == 0 else None), (r.stdout or r.stderr).encode(), "json", ""
    raise ValueError(source)


def parse(source, status, body):
    """Returns (hits or None, list of (id, title, year), note)."""
    t = body.decode("utf-8", "replace")
    if status != 200:
        return None, [], f"HTTP {status}" if status else "network error"
    if source == "arxiv":
        n = re.search(r"<opensearch:totalResults[^>]*>(\d+)", t)
        out = []
        for e in re.findall(r"<entry>(.*?)</entry>", t, re.S):
            out.append(("arXiv:" + re.search(r"<id>https?://arxiv.org/abs/(.*?)</id>", e).group(1),
                        " ".join(re.search(r"<title>(.*?)</title>", e, re.S).group(1).split()),
                        re.search(r"<published>(\d{4})", e).group(1)))
        return int(n.group(1)) if n else None, out, ""
    if source == "crossref":
        m = json.loads(t)["message"]
        return m["total-results"], [("doi:" + i["DOI"], (i.get("title") or [""])[0],
                                     (i.get("issued", {}).get("date-parts") or [[None]])[0][0]) for i in m["items"]], ""
    if source == "s2":
        d = json.loads(t)
        out = []
        for p in d.get("data", []):
            ex = p.get("externalIds") or {}
            pid = ("arXiv:" + ex["ArXiv"]) if "ArXiv" in ex else ("doi:" + ex["DOI"]) if "DOI" in ex else "s2:" + p["paperId"]
            out.append((pid, p.get("title") or "", p.get("year")))
        return d.get("total"), out, ""
    if source == "europepmc":
        d = json.loads(t)
        return d.get("hitCount"), [("doi:" + r["doi"] if r.get("doi") else f"{r.get('source')}:{r.get('id')}",
                                    r.get("title", ""), r.get("pubYear")) for r in d["resultList"]["result"]], ""
    if source == "wikidata":
        d = json.loads(t)["query"]
        return d["searchinfo"]["totalhits"], [(h["title"], "", h["timestamp"][:4]) for h in d["search"]], ""
    if source in ("gh-repos", "gh-code"):
        d = json.loads(t)
        if source == "gh-repos":
            out = [(i["full_name"], (i.get("description") or "")[:150], (i.get("pushed_at") or "")[:4]) for i in d["items"]]
        else:
            out = [(i["repository"]["full_name"] + "/" + i["path"], "", "") for i in d["items"]]
        return d.get("total_count"), out, ""
    raise ValueError(source)


def main(offline, retry=False):
    RAW.mkdir(parents=True, exist_ok=True)
    index_path = RAW / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    rows = []
    for i, (source, q) in enumerate(QUERIES):
        key = f"{source}_{i:02d}"
        prev = index.get(key, {})
        if not offline and not (retry and prev.get("status") == 200 and prev.get("query") == q):
            st, body, ext, again = fetch(source, q)
            if prev.get("status") not in (None, 200):
                again = "; ".join(x for x in (f"first attempt {prev['date_utc']} HTTP {prev['status']}", prev.get("retry", ""), again) if x)
            (RAW / f"{key}.{ext}").write_bytes(body)
            index[key] = {"source": source, "query": q, "status": st, "file": f"{key}.{ext}", "retry": again,
                          "date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            index_path.write_text(json.dumps(index, indent=1))
        meta = index[key]
        hits, items, note = parse(source, meta["status"], (RAW / meta["file"]).read_bytes())
        note = "; ".join(x for x in (meta.get("retry", ""), note) if x)
        used = USED.get((source, q), [])
        rows.append({"query": q, "source": source, "date_utc": meta["date_utc"], "hits": "" if hits is None else hits,
                     "screened": min(SCREEN, len(items)), "used": "yes" if used else "no", "used_ids": " ".join(used),
                     "notes": note})
        print(f"\n## {source} {q!r}: hits {hits} {note}")
        for pid, title, year in items[:SCREEN]:
            print(f"- {year} {pid} | {title[:120]}")
    rows += MANUAL
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["query", "source", "date_utc", "hits", "screened", "used", "used_ids", "notes"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT.relative_to(ROOT)} ({len(rows)} rows)")


if __name__ == "__main__":
    main("--offline" in sys.argv, "--retry" in sys.argv)
