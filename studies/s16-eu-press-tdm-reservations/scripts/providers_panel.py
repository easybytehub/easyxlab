#!/usr/bin/env python3
"""Secondary panel: which reservation protocols do GPAI providers say their crawlers honour?

Reads the provider documents archived by `fetch_sources.py --providers` (data/raw/sources/, with
URL, date and sha256 in data/sources_manifest.csv) and writes data/providers_panel.csv: for each
document, whether it mentions each protocol, with a short evidence snippet. A mention is not
proof of behaviour: it is what the provider states on that date.
"""
import csv
import html
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "raw", "sources")

PROVIDER = {
    "openai_bots": "OpenAI", "anthropic_crawler": "Anthropic", "google_crawlers_common": "Google",
    "mistral_crawlers": "Mistral AI", "apple_applebot": "Apple", "amazon_amazonbot": "Amazon",
    "perplexity_bots": "Perplexity", "commoncrawl_ccbot": "Common Crawl", "microsoft_bingbot_ai": "Microsoft",
    "cohere_crawler": "Cohere", "aleph_alpha": "Aleph Alpha", "deepseek_crawler": "DeepSeek",
    "meta_crawlers": "Meta", "bytedance_bytespider": "ByteDance",
}
NOTE = {  # what the archived document is, when it is not a crawler page we could read
    "microsoft_bingbot_ai": "page text is rendered by script: 0 words in the served HTML",
    "aleph_alpha": "home page; no crawler documentation located",
    "deepseek_crawler": "home page; no crawler documentation located",
    "cohere_crawler": "documented URL answers 404",
    "meta_crawlers": "robots.txt of developers.facebook.com disallows the page for our user agent",
    "bytedance_bytespider": "robots.txt of bytespider.bytedance.com disallows the page for our user agent",
}
PROTOCOLS = {
    "robots_txt": r"robots\.txt",
    "rfc9309": r"RFC\s*9309|Robots Exclusion Protocol",
    "tdmrep": r"TDMRep|tdm-?reservation|TDM Reservation Protocol|tdmrep\.json",
    "content_signal": r"Content[- ]Signals?\b",
    "content_usage_aipref": r"Content-Usage|aipref|AI Preferences",
    "noai_meta": r"\bnoai\b|noimageai",
    "x_robots_tag_or_meta": r"X-Robots-Tag|meta\s+(?:name|tag)|robots meta",
    "dsm_art4": r"2019/790|Article\s+4\b|Art\.\s*4\(3\)",
}


def text_of(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    t = re.sub(r"(?s)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t))


def main():
    man = {r["name"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "sources_manifest.csv")))}
    rows = []
    for name, prov in PROVIDER.items():
        m = man.get(name)
        if not m:
            continue
        row = dict(provider=prov, document=name, url=m["final_url"] or m["url"], fetched_utc=m["fetched_utc"],
                   http_status=m["status"], sha256=m["sha256"],
                   crawler_doc_read="no" if name in NOTE else "yes", note=NOTE.get(name, ""))
        fn = next((f for f in os.listdir(SRC) if f.startswith(name + ".")), None)
        t = text_of(os.path.join(SRC, fn)) if (fn and m["status"] == "200") else ""
        for k, rx in PROTOCOLS.items():
            mm = re.search(rx, t, re.I)
            row[k] = int(bool(mm))
            row[k + "_evidence"] = (t[max(0, mm.start() - 90):mm.end() + 110].strip() if mm else "")[:220]
        rows.append(row)
    keys = list(rows[0])
    with open(os.path.join(ROOT, "data", "providers_panel.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['provider']:<13} {r['crawler_doc_read']:<4}", " ".join(f"{k}={r[k]}" for k in PROTOCOLS))


if __name__ == "__main__":
    main()
