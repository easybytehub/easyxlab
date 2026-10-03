#!/usr/bin/env python3
"""Prior-work search (run 2026-10-03). Saves raw responses in work/docs/prior/ and prints a digest."""
import json, re, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path
OUT = Path(__file__).resolve().parent.parent / "work" / "docs" / "prior"
UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
def get(url, name):
    time.sleep(1.1)
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
    except Exception as e:
        print(f"[{name}] ERROR {e}"); return None
    (OUT / name).write_bytes(raw); return raw
q = urllib.parse.quote
def base():
    for i, s in enumerate(['all:C2PA', 'all:"content credentials"', 'all:"Wikimedia Commons" AND all:"AI-generated"',
                           'abs:provenance AND abs:"AI-generated images" AND abs:metadata']):
        raw = get(f"https://export.arxiv.org/api/query?search_query={q(s)}&max_results=25&sortBy=relevance", f"arxiv{i}.xml")
        if raw:
            t = raw.decode()
            n = re.search(r"<opensearch:totalResults[^>]*>(\d+)", t)
            print(f"\n## arXiv {s!r}: total {n.group(1) if n else '?'}")
            for e in re.findall(r"<entry>(.*?)</entry>", t, re.S):
                ti = " ".join(re.search(r"<title>(.*?)</title>", e, re.S).group(1).split())
                pid = re.search(r"<id>http://arxiv.org/abs/(.*?)</id>", e).group(1)
                ab = " ".join(re.search(r"<summary>(.*?)</summary>", e, re.S).group(1).split())
                hit = [m for m in re.split(r"(?<=\.)\s", ab) if re.search(r"C2PA|Content Credential|wild|adoption|stripp|metadata|Commons|platform", m)]
                print(f"- {pid} | {ti[:110]} || {' '.join(hit)[:260]}")
    for i, s in enumerate(["C2PA content credentials adoption measurement", "Wikimedia Commons AI-generated images provenance"]):
        raw = get(f"https://api.crossref.org/works?query={q(s)}&rows=8&select=title,DOI,issued,container-title", f"crossref{i}.json")
        if raw:
            d = json.loads(raw)["message"]; print(f"\n## Crossref {s!r}: total {d['total-results']}")
            for it in d["items"]:
                print(f"- {it.get('DOI')} | {(it.get('title') or [''])[0][:110]} | {it.get('issued',{}).get('date-parts',[[None]])[0][0]}")
    for i, s in enumerate(["C2PA content credentials in the wild", "AI-generated images Wikimedia Commons", "provenance metadata AI-generated images survival platforms"]):
        raw = get(f"https://api.semanticscholar.org/graph/v1/paper/search?query={q(s)}&limit=10&fields=title,year,externalIds,abstract", f"s2_{i}.json")
        if raw:
            d = json.loads(raw); print(f"\n## Semantic Scholar {s!r}: total {d.get('total')}")
            for p in d.get("data", []):
                ab = p.get("abstract") or ""
                hit = [m for m in re.split(r"(?<=\.)\s", ab) if re.search(r"C2PA|Content Credential|wild|adoption|stripp|Commons|%", m)]
                print(f"- {p.get('year')} | {p['title'][:110]} | {(p.get('externalIds') or {}).get('ArXiv') or (p.get('externalIds') or {}).get('DOI')} || {' '.join(hit)[:240]}")
    for s in ["c2pa wikimedia", "c2pa commons", "content credentials crawler", "c2pa survey dataset"]:
        r = subprocess.run(["gh", "search", "repos", s, "--limit", "8", "--json", "fullName,description,updatedAt,stargazersCount"], capture_output=True, text=True)
        (OUT / f"gh_{s.replace(' ', '_')}.json").write_text(r.stdout or r.stderr)
        print(f"\n## gh search repos {s!r}")
        try:
            for x in json.loads(r.stdout): print(f"- {x['fullName']} ★{x['stargazersCount']} | {(x['description'] or '')[:120]}")
        except Exception: print("  ", (r.stderr or r.stdout)[:200])
    W = "https://commons.wikimedia.org/w/api.php?format=json&formatversion=2&maxlag=5&"
    for s in ["C2PA", "\"Content Credentials\"", "\"DigitalSourceType\"", "\"trainedAlgorithmicMedia\""]:
        raw = get(W + f"action=query&list=search&srsearch={q(s)}&srnamespace=4|5|10|11|12|13&srlimit=15&srprop=snippet|timestamp", f"commons_search_{re.sub(r'[^A-Za-z]', '', s)}.json")
        if raw:
            d = json.loads(raw)["query"]; print(f"\n## Commons project/help/template search {s}: total {d['searchinfo']['totalhits']}")
            for h in d["search"]: print(f"- {h['title']} ({h['timestamp'][:10]}) | {re.sub('<.*?>', '', h['snippet'])[:150]}")
    raw = get(W + "action=parse&page=Commons:AI-generated_media&prop=wikitext&redirects=1", "commons_ai_policy.json")
    if raw:
        t = json.loads(raw)["parse"]["wikitext"]
        print(f"\n## Commons:AI-generated media ({len(t)} chars); sentences on metadata/prompt/C2PA:")
        for m in re.split(r"(?<=[.!?])\s+|\n", t):
            if re.search(r"metadata|C2PA|Content Credentials|EXIF|prompt|PD-algorithm", m, re.I): print("  >", m.strip()[:300])
    raw = get("https://phabricator.wikimedia.org/api/maniphest.search?constraints[query]=C2PA&limit=20", "phab_c2pa.json")
    if raw:
        d = json.loads(raw); print(f"\n## Phabricator maniphest.search C2PA: error={d.get('error_info')}")
        for x in ((d.get("result") or {}).get("data") or []): print(f"- T{x['id']} | {x['fields']['name'][:120]} | {x['fields']['status']['value']}")


def extra():
    """Second pass (2026-10-03, after review): queries beyond C2PA wording, the paper the
    review found (Rijsbosch et al.), and the Semantic Scholar retry."""
    for i, s in enumerate(['abs:"AI Act" AND abs:watermarking', 'abs:"machine-readable" AND abs:"AI-generated"',
                           'abs:"AI Act" AND abs:labelling', 'abs:watermarking AND abs:adoption AND abs:generators']):
        raw = get(f"https://export.arxiv.org/api/query?search_query={q(s)}&max_results=15", f"arxiv_extra{i}.xml")
        if raw:
            t = raw.decode(); n = re.search(r"<opensearch:totalResults[^>]*>(\d+)", t)
            print(f"\n## arXiv {s!r}: total {n.group(1) if n else '?'}")
            for e in re.findall(r"<entry>(.*?)</entry>", t, re.S):
                ti = " ".join(re.search(r"<title>(.*?)</title>", e, re.S).group(1).split())
                print(f"- {re.search(r'<id>http://arxiv.org/abs/(.*?)</id>', e).group(1)} | {ti[:120]}")
    raw = get("https://export.arxiv.org/api/query?id_list=2503.18156", "arxiv_2503.18156.xml")
    if raw:
        t = raw.decode(); e = re.search(r"<entry>(.*?)</entry>", t, re.S).group(1)
        print("\n## arXiv:2503.18156", " ".join(re.search(r"<title>(.*?)</title>", e, re.S).group(1).split()))
        print("   authors:", re.findall(r"<name>(.*?)</name>", e)[:6], "published:", re.search(r"<published>(.*?)</published>", e).group(1))
        print("   abstract:", " ".join(re.search(r"<summary>(.*?)</summary>", e, re.S).group(1).split()))
    for k, s in enumerate(["C2PA content credentials in the wild", "AI-generated images Wikimedia Commons"]):
        time.sleep(3)
        raw = get(f"https://api.semanticscholar.org/graph/v1/paper/search?query={q(s)}&limit=8&fields=title,year,externalIds", f"s2_retry_{k}.json")
        if raw:
            d = json.loads(raw); print(f"\n## Semantic Scholar (retry) {s!r}: total {d.get('total')}")


if __name__ == "__main__":
    extra() if "--extra" in sys.argv else base()
