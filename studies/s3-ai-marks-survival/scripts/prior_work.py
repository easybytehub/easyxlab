#!/usr/bin/env python3
"""Prior-work search for S3 (paper.md §3), run 2026-10-03.

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
    ("arxiv", 'all:C2PA'),
    ("arxiv", 'all:"content credentials"'),
    ("arxiv", 'all:C2PA AND all:metadata AND all:stripping'),
    ("arxiv", 'all:"soft binding" AND all:provenance'),
    ("arxiv", 'all:metadata AND all:"social media" AND all:stripping'),
    ("arxiv", 'all:EXIF AND all:"social media" AND all:images AND all:removal'),
    ("arxiv", 'all:IPTC AND all:metadata'),
    ("arxiv", 'all:provenance AND all:"AI-generated" AND all:metadata AND all:platforms'),
    ("crossref", "C2PA content credentials durability metadata stripping"),
    ("crossref", "social media metadata removal EXIF IPTC images"),
    ("crossref", "image metadata preservation social networks test"),
    ("crossref", "provenance metadata AI-generated images survival"),
    ("crossref", "IPTC digital source type AI generated"),
    ("s2", "C2PA manifest robustness image processing"),
    ("s2", "metadata stripping social media platforms images"),
    ("s2", "content credentials survival transcoding"),
    ("gh-repos", "c2pa survival"),
    ("gh-repos", "c2pa metadata stripping test"),
    ("gh-repos", "content credentials preservation"),
    ("gh-code", '"c2pa" "keepMetadata"'),
    # second batch, same day, after reading the first results and the web search that found Creative AI News
    ("arxiv", 'all:"AI provenance"'),
    ("arxiv", 'all:"digital source type"'),
    ("arxiv", 'all:"Content Credentials" AND all:survive'),
    ("crossref", "content credentials export survival test"),
    ("crossref", "C2PA soft binding perceptual hash social media transcoding"),
    ("gh-repos", "content credentials survival test"),
    ("gh-repos", "iptc digitalsourcetype survival"),
]

# Filled after reading the results: (source, query) -> ids cited in paper.md §3.
USED = {
    ("arxiv", 'all:C2PA'): ["arXiv:2604.25370", "arXiv:2603.02378"],
    ("arxiv", 'all:"AI provenance"'): ["arXiv:2609.38571"],
    ("crossref", "C2PA content credentials durability metadata stripping"): ["doi:10.1109/paee71887.2026.11660698"],
    ("crossref", "C2PA soft binding perceptual hash social media transcoding"): ["doi:10.1109/paee71887.2026.11660698"],
    ("gh-repos", "c2pa survival"): ["AitchEm-bot/research"],
    ("gh-repos", "content credentials survival test"): ["AitchEm-bot/research"],
}

# Searches and documents that did not go through this script (web search, specification and vendor pages fetched with curl).
MANUAL = [
    {"query": 'IPTC embedded metadata social media test results which sites preserve photo metadata', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 10, "screened": "",
     "used": 'yes', "used_ids": 'iptc.org social media tests 2016 and 2019', "notes": ''},
    {"query": 'C2PA durable content credentials soft binding manifest stripped metadata removed when re-encoded', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 9, "screened": "",
     "used": 'yes', "used_ids": 'c2pa.org/faq', "notes": ''},
    {"query": '"Recovering Content Provenance After Social Media Transcoding" perceptual hash soft-bindings C2PA', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 9, "screened": "",
     "used": 'no', "used_ids": '', "notes": 'paper not among results; abstract taken from Semantic Scholar by DOI'},
    {"query": 'Ossowski Chaber "Recovering Content Provenance After Social Media Transcoding" PAEE 2026', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 9, "screened": "",
     "used": 'no', "used_ids": '', "notes": 'paper not among results'},
    {"query": 'Bushey Rivard Barbeau "Cryptographic Provenance and AI-Generated Images" BigData 2025 C2PA', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 9, "screened": "",
     "used": 'no', "used_ids": '', "notes": 'paper not among results; abstract from Semantic Scholar: archival framework, no survival test'},
    {"query": 'exiftool editing XMP invalidates C2PA manifest "data hash" mismatch content credentials metadata edit after signing', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 9, "screened": "",
     "used": 'yes', "used_ids": 'creativeainews.com/articles/content-credentials-export-survival-test-2026/', "notes": 'found the closest prior result'},
    {"query": 'test C2PA content credentials survive sharp keepMetadata Pillow ffmpeg remux stripped IPTC DigitalSourceType XMP survive', "source": 'WebSearch', "date_utc": '2026-10-03', "hits": 9, "screened": "",
     "used": 'no', "used_ids": '', "notes": 'no further per-library test found'},
    {"query": 'https://www.creativeainews.com/articles/content-credentials-export-survival-test-2026/', "source": 'web page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'Creative AI News 2026-09-25', "notes": 'HTTP 200; robots.txt allows; no harness published'},
    {"query": 'https://c2pa.org/faq/', "source": 'specification page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'C2PA FAQ', "notes": 'HTTP 200'},
    {"query": 'https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html', "source": 'specification page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'C2PA 2.2 specification', "notes": 'HTTP 200'},
    {"query": 'https://spec.c2pa.org/specifications/specifications/2.2/guidance/Guidance.html', "source": 'specification page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'C2PA 2.2 implementation guidance', "notes": 'HTTP 200'},
    {"query": 'https://spec.c2pa.org/specifications/specifications/2.2/security/Security_Considerations.html', "source": 'specification page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'C2PA 2.2 security considerations', "notes": 'HTTP 200'},
    {"query": 'https://iptc.org/news/social-media-sites-photo-metadata-test-results/', "source": 'standards body page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'IPTC 2019 test', "notes": 'HTTP 200'},
    {"query": 'https://iptc.org/news/many-social-media-sites-still-remove-image-rights-information-from-photos/', "source": 'standards body page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'IPTC 2016 test', "notes": 'HTTP 200'},
    {"query": 'https://iptc.org/standards/photo-metadata/research/', "source": 'standards body page', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'HTTP 200; index page'},
    {"query": 'https://arxiv.org/html/2603.02378v2', "source": 'arXiv full text', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'arXiv:2603.02378', "notes": 'robots.txt allows /html (Crawl-delay 15 respected)'},
    {"query": 'https://arxiv.org/html/2609.38571v1', "source": 'arXiv full text', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'arXiv:2609.38571', "notes": ''},
    {"query": 'DOI:10.1109/paee71887.2026.11660698', "source": 'Semantic Scholar paper lookup', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'doi:10.1109/paee71887.2026.11660698', "notes": 'HTTP 200, abstract; Crossref has no abstract'},
    {"query": 'DOI:10.1109/bigdata66926.2025.11402054', "source": 'Semantic Scholar paper lookup', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'HTTP 200, abstract; archival framework'},
    {"query": 'DOI:10.36244/icj.2026.1.7', "source": 'Crossref work lookup', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'overview paper'},
    {"query": 'repos/AitchEm-bot/research (README, tree, compress_images.py)', "source": 'GitHub API', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'yes', "used_ids": 'AitchEm-bot/research', "notes": 'no results files in the repository'},
    {"query": 'repos/easybytehub/easyxlab commits for studies/s3-ai-marks-survival', "source": 'GitHub API', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'S3 first public on 2026-10-02, after the Creative AI News test'},
    {"query": 'https://huggingface.co/api/datasets/csoai/gspc-prv', "source": 'Hugging Face API', "date_utc": '2026-10-03', "hits": '', "screened": "",
     "used": 'no', "used_ids": '', "notes": 'LLM evaluation bank, not a survival test'},
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
