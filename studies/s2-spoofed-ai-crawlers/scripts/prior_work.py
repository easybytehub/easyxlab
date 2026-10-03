#!/usr/bin/env python3
"""Prior-work search for S2 (paper.md §2), run 2026-10-03.

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
    ("arxiv", 'all:"user agent" AND all:spoofing'),
    ("arxiv", 'all:"user-agent" AND all:crawler AND all:verification'),
    ("arxiv", 'all:"AI crawlers"'),
    ("arxiv", 'all:"robots.txt" AND all:AI AND all:crawlers'),
    ("arxiv", 'all:impersonation AND all:crawlers'),
    ("arxiv", 'all:"bot detection" AND all:"reverse DNS"'),
    ("arxiv", 'all:"web bots" AND all:honeysites'),
    ("arxiv", 'all:"search engine" AND all:bots AND all:fake'),
    ("crossref", "fake Googlebot crawler impersonation"),
    ("crossref", "AI crawler user agent verification"),
    ("crossref", "web bot detection user agent spoofing reverse DNS"),
    ("crossref", "good bot bad bot characterizing automated browsing activity"),
    ("crossref", "AI crawlers robots.txt compliance measurement"),
    ("crossref", "LLM crawlers web server access logs"),
    ("s2", "AI crawler user agent spoofing"),
    ("s2", "fake search engine crawlers reverse DNS verification"),
    ("s2", "AI crawlers web server logs measurement"),
    ("s2", "characterizing automated browsing activity honeysites"),
    ("gh-repos", "verify googlebot"),
    ("gh-repos", "ai crawler verification ip ranges"),
    ("gh-repos", "fake bot detection user agent ip"),
    ("gh-repos", "gptbot.json"),
    ("gh-code", '"openai.com/gptbot.json"'),
    ("gh-code", '"perplexity.com/perplexity-user.json"'),
    # second batch, same day, after reading the first digest
    ("arxiv", 'all:GPTBot'),
    ("arxiv", 'all:Googlebot'),
    ("arxiv", 'all:"verified bots"'),
    ("arxiv", 'all:"user-initiated" AND all:fetch AND all:LLM'),
    ("crossref", "are LLM web search engines sustainable real-time fetching"),
]

# Filled after reading the results: (source, query) -> ids cited in paper.md §2.
USED = {
    ("arxiv", 'all:"robots.txt" AND all:AI AND all:crawlers'): ["arXiv:2505.21733"],
    ("crossref", "good bot bad bot characterizing automated browsing activity"): ["doi:10.1109/sp40001.2021.00079"],
    ("s2", "AI crawlers web server logs measurement"): ["arXiv:2607.14447", "doi:10.1145/3774904.3792278"],
    ("crossref", "are LLM web search engines sustainable real-time fetching"): ["doi:10.1145/3774904.3792278"],
    ("gh-repos", "verify googlebot"): ["(count only)"],
    ("gh-repos", "ai crawler verification ip ranges"): ["CyberKendra/ai-crawler-verify", "ayronjins/ai-crawler-verify",
                                                        "asxpi/traefik-crawlers-statistics"],
    ("gh-code", '"openai.com/gptbot.json"'): ["(count only)"],
}

# Searches and documents that did not go through this script (web search, vendor pages fetched with curl).
MANUAL = [
    {"query": '"Good Bot, Bad Bot: Characterizing Automated Browsing Activity" Aristaeus pdf', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 9, "screened": "",
     "used": 'yes', "used_ids": 'securitee.org/files/goodbotbadbot_oakland2021.pdf', "notes": 'full text read (pdftotext)'},
    {"query": '"Are LLM Web Search Engines Sustainable" real-time fetching web measurement', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 9, "screened": "",
     "used": 'no', "used_ids": '', "notes": 'paper not among results; abstract taken from Semantic Scholar by DOI'},
    {"query": 'Cloudflare blog AI crawlers spoofed user agent verified bots impersonating GPTBot', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 9, "screened": "",
     "used": 'no', "used_ids": '', "notes": 'no Cloudflare page with a spoof rate'},
    {"query": 'Akamai report AI bots impersonating crawlers fake GPTBot ClaudeBot percentage 2025 2026', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 10, "screened": "",
     "used": 'yes', "used_ids": 'greynoise.io/blog/threat-actors-posing-as-ai-crawlers', "notes": 'led to GreyNoise; no Akamai spoof figure found'},
    {"query": 'DataDome fake AI crawlers spoofed ChatGPT-User user agent report', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 10, "screened": "",
     "used": 'no', "used_ids": '', "notes": 'datadome.co answered HTTP 403; secondary summaries not cited'},
    {"query": 'Imperva Bad Bot Report 2025 bots impersonating search engine crawlers AI crawlers percentage', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 10, "screened": "",
     "used": 'no', "used_ids": '', "notes": 'no spoof rate for crawler names in the Thales/Imperva page'},
    {"query": 'blog.cloudflare.com 2026 GPTBot impersonation verified "13%" OR "signed" AI crawler verification web bot auth', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 9, "screened": "",
     "used": 'no', "used_ids": '', "notes": "a '13% of GPTBot verified' figure circulates in secondary pages; no primary source found"},
    {"query": 'Cloudflare blog August 28 2026 bot verification automatic "We fetch your IP list, confirm your reverse DNS"', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 10, "screened": "",
     "used": 'yes', "used_ids": 'blog.cloudflare.com/friendly-bots/', "notes": ''},
    {"query": 'https://www.humansecurity.com/learn/blog/ai-crawler-spoofing-chatgpt-mistral-perplexity/', "source": 'vendor page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'HUMAN Satori 2025-09-09', "notes": 'HTTP 200'},
    {"query": 'https://www.humansecurity.com/learn/blog/controlling-ai-driven-content-scraping-with-human/', "source": 'vendor page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'HUMAN 2026-02-28 (already cited in §1)', "notes": 'HTTP 200; links to the Satori post'},
    {"query": 'https://www.greynoise.io/blog/threat-actors-posing-as-ai-crawlers', "source": 'vendor page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'GreyNoise 2026-08-28', "notes": 'HTTP 200'},
    {"query": 'https://blog.cloudflare.com/friendly-bots/', "source": 'vendor page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'Cloudflare 2022-03-16', "notes": 'HTTP 200'},
    {"query": 'https://datadome.co/threat-research/ai-traffic-report/', "source": 'vendor page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'HTTP 403'},
    {"query": 'https://datadome.co/press/datadome-report-finds-most-organizations-flying-blind-as-agentic-traffic-surges/', "source": 'vendor page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'HTTP 403'},
    {"query": 'https://cpl.thalesgroup.com/blog/access-management/ai-bots-internet-traffic-imperva-2025-report', "source": 'vendor page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'HTTP 200; no spoof rate for crawler names'},
    {"query": 'https://www.akamai.com/newsroom/press-release/akamai-research-ai-bots-threaten-foundation-of-web-based-business-models', "source": 'vendor page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'HTTP 403'},
    {"query": 'https://nohacks.co/blog/ai-crawlers-cannot-prove-identity', "source": 'web page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'HTTP 200; secondary, no spoof rate'},
    {"query": 'https://arxiv.org/html/2505.21733v2', "source": 'arXiv full text', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'arXiv:2505.21733', "notes": 'robots.txt allows /html (Crawl-delay 15 respected)'},
    {"query": 'https://arxiv.org/html/2607.14447v2', "source": 'arXiv full text', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'arXiv:2607.14447', "notes": ''},
    {"query": 'https://arxiv.org/html/2411.15091v2', "source": 'arXiv full text', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'Cloudflare reverse-proxy blocking study; no spoof rate'},
    {"query": 'DOI:10.1145/3774904.3792278', "source": 'Semantic Scholar paper lookup', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'doi:10.1145/3774904.3792278', "notes": 'HTTP 200, abstract'},
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
