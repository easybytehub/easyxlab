# SPDX-License-Identifier: Apache-2.0
"""National case: Poland (METHOD.md §8). Network step.
(1) dane.gov.pl API: datasets flagged has_high_value_data_from_ec_list (EU list) and has_high_value_data;
(2) the same datasets on data.europa.eu (catalogue dane-gov-pl), matched by the numeric dataset ID in the
    landing page / identifier, with their HVD properties;
(3) the first page of the source's DCAT-AP catalogue endpoint: which HVD and licence properties it carries.
Writes data/poland_case.json (aggregates + dataset IDs only)."""
import json
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch  # noqa: E402
import hvd_rules as R  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.dane.gov.pl/1.4/datasets?"
NUM = re.compile(r"/dataset/(\d+)")


FEED = os.path.join(ROOT, "data", "raw", "dane_gov_pl_catalog_page1.rdf")


def feed_stats(status=200):
    t = open(FEED, "rb").read().decode("utf-8", "replace")
    return {
        "status": status, "bytes": len(t.encode()),
        "datasets": len(re.findall(r"<dcat:dataset\b", t)),
        "distributions": len(re.findall(r"<dcat:distribution\b", t)),
        "applicableLegislation": len(re.findall(r"applicableLegislation", t)),
        "hvdCategory": len(re.findall(r"hvdCategory", t)),
        "eli_2023_138": len(re.findall(r"2023/138", t)),
        "dct_license": len(re.findall(r"<dct:license\b|<dcterms:license\b", t)),
        "dcat_license": len(re.findall(r"<dcat:license\b", t)),
        "hydra_next_page": bool(re.search(r"<hydra:nextPage", t)),
        "ns": sorted(set(re.findall(r'xmlns:(dcat|dct|dcterms|dcatap)="([^"]+)"', t))),
    }


def count(flag):
    d = fetch.get_json(API + urllib.parse.urlencode({flag: "true", "per_page": 1}))
    return d["meta"]["count"]


def main():
    out = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    out["source_flag_ec_list"] = count("has_high_value_data_from_ec_list")
    out["source_flag_national"] = count("has_high_value_data")
    ids, page = {}, 1
    while True:
        d = fetch.get_json(API + urllib.parse.urlencode(
            {"has_high_value_data_from_ec_list": "true", "per_page": 100, "page": page}))
        for x in d["data"]:
            a = x["attributes"]
            ids[str(x["id"])] = {"license": a.get("license_name"), "national_flag": a.get("has_high_value_data")}
        if len(d["data"]) < 100:
            break
        page += 1
    out["source_ec_list_ids"] = sorted(ids, key=int)
    out["source_ec_list_licences"] = {k: sum(1 for v in ids.values() if v["license"] == k)
                                      for k in sorted({str(v["license"]) for v in ids.values()})}

    # the Polish national catalogue on data.europa.eu
    inc = "id,identifier,landing_page.resource,hvd_category.id,applicable_legislation,keywords.id,distributions.license.id"
    first = "https://data.europa.eu/api/hub/search/search?" + urllib.parse.urlencode(
        {"filter": "dataset", "facets": json.dumps({"catalog": ["dane-gov-pl"]}), "limit": 500, "scroll": "true",
         "includes": inc})
    d = fetch.get_json(first, timeout=180)
    edp, n_total = {}, d["result"]["count"]
    stats = {"records": 0, "with_eli": 0, "with_category": 0, "with_hvd_keyword": 0, "with_dist_licence": 0}
    while d["result"].get("results"):
        for r in d["result"]["results"]:
            stats["records"] += 1
            refs = [str(x) for x in (r.get("identifier") or [])] + [
                (x or {}).get("resource", "") for x in (r.get("landing_page") or [])]
            nums = {m.group(1) for s in refs for m in [NUM.search(s)] if m}
            eli = R.eli_status(r.get("applicable_legislation"))[0] == "exact"
            cat = bool(r.get("hvd_category"))
            kw = any(re.search(r"hvd|high-value|wysokiej-wartosci|wysokiej-wartości", (k or {}).get("id", ""))
                     for k in (r.get("keywords") or []))
            lic = any((x.get("license") or {}).get("id") for x in (r.get("distributions") or []))
            stats["with_eli"] += eli
            stats["with_category"] += cat
            stats["with_hvd_keyword"] += kw
            stats["with_dist_licence"] += lic
            for n in nums:
                edp[n] = {"edp_id": r["id"], "eli": eli, "category": cat, "hvd_keyword": kw, "dist_licence": lic}
        if stats["records"] >= n_total or not d["result"].get("scrollId"):
            break
        d = fetch.get_json("https://data.europa.eu/api/hub/search/scroll?" + urllib.parse.urlencode(
            {"scrollId": d["result"]["scrollId"]}), timeout=180)
    out["edp_catalogue_dane_gov_pl"] = {"count_reported": n_total, **stats}
    found = {i: edp[i] for i in ids if i in edp}
    out["ec_list_found_on_edp"] = len(found)
    out["ec_list_found_with_eli"] = sum(v["eli"] for v in found.values())
    out["ec_list_found_with_category"] = sum(v["category"] for v in found.values())
    out["ec_list_found_with_hvd_keyword"] = sum(v["hvd_keyword"] for v in found.values())
    out["ec_list_found_with_dist_licence"] = sum(v["dist_licence"] for v in found.values())
    out["ec_list_found_edp_ids"] = sorted(v["edp_id"] for v in found.values())

    # the source's DCAT-AP endpoint (first page only), kept in data/raw/
    r = fetch.get("https://api.dane.gov.pl/1.4/catalog.rdf", headers={"Accept": "application/rdf+xml"},
                  max_bytes=5_000_000, timeout=120)
    open(FEED, "wb").write(r.body)
    out["source_feed_page1"] = feed_stats(r.status)
    json.dump(out, open(os.path.join(ROOT, "data", "poland_case.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if not k.endswith("_ids")}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1:] == ["--feed-only"]:  # recompute the feed figures from the saved page
        p = os.path.join(ROOT, "data", "poland_case.json")
        o = json.load(open(p))
        o["source_feed_page1"] = feed_stats(o["source_feed_page1"]["status"])
        json.dump(o, open(p, "w"), indent=1, ensure_ascii=False)
        print(o["source_feed_page1"])
    else:
        main()
