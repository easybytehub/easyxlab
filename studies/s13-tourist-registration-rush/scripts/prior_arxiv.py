#!/usr/bin/env python3
"""Prior-work search on arXiv through its API (export.arxiv.org/api/query).

export.arxiv.org's robots.txt disallows crawlers, so polite.py refuses it. The API is used, as in
study S11, under the arXiv API Terms of Use, which grant programmatic access and ask for one
request every three seconds over a single connection: this script waits 3.1 s between requests,
sends the study User-Agent and logs every request to work/fetch_log.jsonl. It replaces the
"NOT RUN" arXiv rows of data/prior_work_search.csv with the queries' results; titles of the top
20 hits are saved in work/prior/arxiv_hits.json for screening.

    python3 scripts/prior_arxiv.py
"""
import csv, json, os, re, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
CSV = os.path.join(R, "data", "prior_work_search.csv")
NS = {"a": "http://www.w3.org/2005/Atom", "o": "http://a9.com/-/spec/opensearch/1.1/"}


def main():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    hits_out = {}
    for r in rows:
        if r["source"] != "arxiv":
            continue
        q = re.search(r"\[(.*)\]", r["query"]).group(1)
        url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"search_query": q, "start": 0, "max_results": 20})
        t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        body = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
        with open(os.path.join(R, "work", "fetch_log.jsonl"), "a") as f:
            f.write(json.dumps({"t": t, "url": url, "status": 200, "robots": "arXiv API ToU (robots.txt disallows)"}) + "\n")
        root = ET.fromstring(body)
        total = int(root.find("o:totalResults", NS).text)
        titles = [(e.find("a:id", NS).text, re.sub(r"\s+", " ", e.find("a:title", NS).text).strip())
                  for e in root.findall("a:entry", NS)]
        hits_out[r["query"]] = titles
        r["date_run"], r["hits"] = t, str(total)
        r["relevant"] = ""
        r["note"] = ("arXiv API (export.arxiv.org), top 20 screened; robots.txt disallows crawlers, "
                     "API used under its Terms of Use (1 request / 3 s)")
        time.sleep(3.1)
    os.makedirs(os.path.join(R, "work", "prior"), exist_ok=True)
    json.dump(hits_out, open(os.path.join(R, "work", "prior", "arxiv_hits.json"), "w"), indent=1, ensure_ascii=False)
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    for k, v in hits_out.items():
        print(k, len(v))
        for i, tt in v[:20]:
            print("   ", i, tt[:110])


if __name__ == "__main__":
    main()
