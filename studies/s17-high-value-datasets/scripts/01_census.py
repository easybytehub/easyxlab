# SPDX-License-Identifier: Apache-2.0
"""Census of is_hvd=true datasets on data.europa.eu (METHOD.md §2), streamed page by page.

Writes data/raw/census.jsonl.gz (one trimmed record per line, never published),
data/raw/country_totals.json, data/raw/catalogues.json, and appends to data/queries.json.
"""
import gzip
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
os.makedirs(RAW, exist_ok=True)
API = "https://data.europa.eu/api/hub/search/"
INCLUDES = ",".join([
    "id", "country.id", "catalog.id", "is_hvd", "hvd_category.id", "applicable_legislation", "keywords.id",
    "access_right.resource", "distributions.id", "distributions.license.id", "distributions.license.resource",
    "distributions.access_url", "distributions.download_url", "distributions.format.id",
    "distributions.access_service", "distributions.applicable_legislation", "distributions.rights",
])


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log_query(kind, url, result):
    p = os.path.join(ROOT, "data", "queries.json")
    q = json.load(open(p)) if os.path.exists(p) else []
    q.append({"kind": kind, "url": url, "utc": now(), "result": result})
    json.dump(q, open(p, "w"), indent=1, ensure_ascii=False)


def main():
    facets = json.dumps({"is_hvd": ["true"]})
    first = API + "search?" + urllib.parse.urlencode(
        {"filter": "dataset", "facets": facets, "limit": 500, "scroll": "true", "includes": INCLUDES})
    started = now()
    d = fetch.get_json(first, timeout=180)
    total = d["result"]["count"]
    n = 0
    out = gzip.open(os.path.join(RAW, "census.jsonl.gz"), "wt", encoding="utf-8")
    while True:
        res = d["result"].get("results") or []
        if not res:
            break
        for r in res:
            r.pop("index", None)
            out.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
        n += len(res)
        sid = d["result"].get("scrollId")
        print(f"{n}/{total}", flush=True)
        if not sid or n >= total:
            break
        d = fetch.get_json(API + "scroll?" + urllib.parse.urlencode({"scrollId": sid}), timeout=180)
    out.close()
    log_query("census-scroll", first, {"count_reported": total, "records_written": n, "started": started,
                                       "finished": now()})

    # national totals on the portal (no HVD filter) and HVD facet counts per country/catalogue
    for name, fac in (("country_totals", None), ("hvd_facets", {"is_hvd": ["true"]})):
        params = {"filter": "dataset", "limit": 0, "facetGroupOperator": "AND"}
        if fac:
            params["facets"] = json.dumps(fac)
        u = API + "search?" + urllib.parse.urlencode(params)
        dd = fetch.get_json(u)
        facets_out = {f["id"]: {i["id"]: i["count"] for i in f["items"]} for f in dd["result"]["facets"]
                      if f["id"] in ("country", "catalog", "hvdCategory", "is_hvd")}
        json.dump({"utc": now(), "count": dd["result"]["count"], "facets": facets_out},
                  open(os.path.join(RAW, name + ".json"), "w"), indent=1)
        log_query(name, u, {"count": dd["result"]["count"]})

    # catalogue -> country mapping
    cats = []
    page = 0
    while True:
        u = API + "search?" + urllib.parse.urlencode(
            {"filter": "catalogue", "limit": 100, "page": page, "includes": "id,country.id,count"})
        dd = fetch.get_json(u)
        res = dd["result"]["results"]
        cats += [{"id": c["id"], "country": (c.get("country") or {}).get("id"), "count": c.get("count")} for c in res]
        if len(res) < 100:
            break
        page += 1
    json.dump(cats, open(os.path.join(RAW, "catalogues.json"), "w"), indent=1)
    log_query("catalogues", API + "search?filter=catalogue", {"catalogues": len(cats)})


if __name__ == "__main__":
    main()
