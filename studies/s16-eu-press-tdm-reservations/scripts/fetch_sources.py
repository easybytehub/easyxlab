#!/usr/bin/env python3
"""Download the legal and technical baseline (and, with --providers, the GPAI providers' crawler
documentation) through politefetch, store each document in data/raw/sources/ (not published:
third-party text) and write data/sources_manifest.csv (published: URL, date, status, sha256).

  python3 scripts/fetch_sources.py [--providers] [--only name1,name2]
"""
import csv
import hashlib
import os
import sys
from datetime import datetime, timezone

import politefetch as P

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "raw", "sources")
MANIFEST = os.path.join(ROOT, "data", "sources_manifest.csv")

CELLAR = {"Accept": "text/html, application/xhtml+xml", "Accept-Language": "en"}
BASELINE = [
    # name, url, headers
    ("dsm_2019_790", "https://publications.europa.eu/resource/celex/32019L0790", CELLAR),
    ("ai_act_2024_1689", "https://publications.europa.eu/resource/celex/32024R1689", CELLAR),
    ("omnibus_2026_1744", "https://publications.europa.eu/resource/celex/32026R1744", CELLAR),
    ("tdmrep_cg_final", "https://www.w3.org/community/reports/tdmrep/CG-FINAL-tdmrep-20240510/", None),
    ("aipref_vocab_08", "https://www.ietf.org/archive/id/draft-ietf-aipref-vocab-08.txt", None),
    ("aipref_attach_05", "https://www.ietf.org/archive/id/draft-ietf-aipref-attach-05.txt", None),
    ("aipref_wg_docs", "https://datatracker.ietf.org/wg/aipref/documents/", None),
    ("crux_methodology", "https://developer.chrome.com/docs/crux/methodology", None),
    ("crux_about", "https://developer.chrome.com/docs/crux/about", None),
    ("cop_gpai_page", "https://digital-strategy.ec.europa.eu/en/policies/contents-code-gpai", None),
    ("cf_content_signals_docs", "https://developers.cloudflare.com/bots/additional-configurations/managed-robots-txt/", None),
    ("qlever_home", "https://qlever.cs.uni-freiburg.de/", None),
]
PROVIDERS = [
    ("openai_bots", "https://platform.openai.com/docs/bots"),
    ("openai_bots_dev", "https://developers.openai.com/api/docs/bots"),
    ("anthropic_crawler", "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler"),
    ("google_crawlers_common", "https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers"),
    ("google_extended", "https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers"),
    ("meta_crawlers", "https://developers.facebook.com/docs/sharing/webmasters/web-crawlers/"),
    ("mistral_crawlers", "https://docs.mistral.ai/robots"),
    ("apple_applebot", "https://support.apple.com/en-us/119829"),
    ("amazon_amazonbot", "https://developer.amazon.com/amazonbot"),
    ("perplexity_bots", "https://docs.perplexity.ai/guides/bots"),
    ("commoncrawl_ccbot", "https://commoncrawl.org/ccbot"),
    ("microsoft_bingbot_ai", "https://www.bing.com/webmasters/help/which-crawlers-does-bing-use-8c184ec0"),
    ("cohere_crawler", "https://docs.cohere.com/docs/cohere-crawler"),
    ("bytedance_bytespider", "https://bytespider.bytedance.com/"),
    ("aleph_alpha", "https://aleph-alpha.com/"),
    ("deepseek_crawler", "https://www.deepseek.com/"),
]


def main():
    args = sys.argv[1:]
    items = list(BASELINE)
    if "--providers" in args:
        items = [(n, u, None) for n, u in PROVIDERS]
    if "--only" in args:
        only = set(args[args.index("--only") + 1].split(","))
        items = [x for x in items if x[0] in only]
    os.makedirs(OUT, exist_ok=True)
    s = P.Session(per_host=20)
    rows = []
    if os.path.exists(MANIFEST):
        rows = list(csv.DictReader(open(MANIFEST)))
    done = {r["name"] for r in rows}
    for name, url, hd in items:
        res = s.get(url, limit=30_000_000, headers=hd)
        when = datetime.now(timezone.utc).isoformat(timespec="seconds")
        body = res["body"] or b""
        sha = hashlib.sha256(body).hexdigest() if body else ""
        ext = ".pdf" if body[:4] == b"%PDF" else (".txt" if url.endswith(".txt") else ".html")
        if body:
            with open(os.path.join(OUT, name + ext), "wb") as f:
                f.write(body)
        row = dict(name=name, url=url, final_url=res["final_url"], fetched_utc=when, status=res["status"] or "",
                   error=res["error"] or "", bytes=len(body), sha256=sha)
        rows = [r for r in rows if r["name"] != name] + [row]
        print(name, res["status"], res["error"], len(body), res["final_url"][:100], file=sys.stderr)
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "url", "final_url", "fetched_utc", "status", "error", "bytes", "sha256"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["name"]))


if __name__ == "__main__":
    main()
