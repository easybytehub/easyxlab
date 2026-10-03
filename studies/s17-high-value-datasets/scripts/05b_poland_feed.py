# SPDX-License-Identifier: Apache-2.0
"""Poland, second pass (review M3): read the pages of the dane.gov.pl DCAT-AP feed that contain
EU-list HVD datasets and report their properties; test the paging hypothesis (advertised last page vs
total items). Network step; pages kept in data/raw/ (not published). Updates data/poland_case.json."""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
FEED = "https://api.dane.gov.pl/1.4/catalog.rdf?sort=id&page={}"
DS = re.compile(r'<dcat:dataset rdf:resource="https://dane\.gov\.pl/pl/dataset/(\d+)[,"]')


def page(n):
    path = os.path.join(RAW, f"dane_feed_p{n}.rdf")
    if not os.path.exists(path):
        r = fetch.get(FEED.format(n), headers={"Accept": "application/rdf+xml"}, max_bytes=8_000_000, timeout=120)
        if r.status != 200:
            return {"page": n, "status": r.status, "ids": []}
        open(path, "wb").write(r.body)
    t = open(path, "rb").read().decode("utf-8", "replace")
    ids = sorted({int(x) for x in DS.findall(t)})
    return {"page": n, "status": 200, "ids": ids, "datasets": len(re.findall(r"<dcat:dataset\b", t)),
            "applicableLegislation": t.count("applicableLegislation"), "hvdCategory": t.count("hvdCategory"),
            "eli_2023_138": t.count("2023/138"), "r5r_namespace": t.count("data.europa.eu/r5r"),
            "dcat_license": len(re.findall(r"<dcat:license\b", t)),
            "dct_license": len(re.findall(r"<dct:license\b|<dcterms:license\b", t)),
            "hvd_words": len(re.findall(r"(?i)high[- ]value|wysokiej warto", t)),
            "last_page": (re.findall(r"<hydra:lastPage>([^<]+)", t) or [""])[0].replace("&amp;", "&"),
            "total_items": int((re.findall(r"<hydra:totalItems[^>]*>(\d+)", t) or [0])[0])}


def main():
    pc = json.load(open(os.path.join(ROOT, "data", "poland_case.json")))
    ec = sorted(int(x) for x in pc["source_ec_list_ids"])
    found = sorted(int(m.group(1)) for i in pc["ec_list_found_edp_ids"]
                   for m in [re.match(r"https-dane-gov-pl-pl-dataset-(\d+)-", i)] if m)
    missing = sorted(set(ec) - set(found))
    pages = {n: page(n) for n in (4, 9)}
    # target more pages: interpolate page from known (page, first id) points, up to 8 extra pages
    for target in [i for i in ec if i <= 12585][::12][:8]:
        if any(p["ids"] and p["ids"][0] <= target <= p["ids"][-1] for p in pages.values()):
            continue
        pts = sorted((n, p["ids"][0]) for n, p in pages.items() if p["ids"])
        (n0, i0), (n1, i1) = pts[0], pts[-1]
        guess = max(1, min(500, round(n0 + (target - i0) * (n1 - n0) / max(1, i1 - i0))))
        if guess not in pages:
            pages[guess] = page(guess)
    for n in (500, 501):
        pages[n] = page(n)
    hvd_pages = {}
    for n, p in sorted(pages.items()):
        present = [i for i in ec if i in set(p["ids"])]
        hvd_pages[str(n)] = {k: v for k, v in p.items() if k != "ids"} | {
            "first_id": p["ids"][0] if p["ids"] else None, "last_id": p["ids"][-1] if p["ids"] else None,
            "ec_list_ids_on_page": present}
    pc["feed_pages"] = hvd_pages
    pc["feed_pages_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    pc["ec_list_ids_found_numeric"] = found
    pc["ec_list_ids_missing_numeric"] = missing
    pc["harvest_hypothesis"] = {
        "found_max_id": max(found), "missing_min_id": min(missing),
        "advertised_last_page": hvd_pages["500"]["last_page"], "items_per_page": 20,
        "advertised_pages_x_per_page": 500 * 20, "total_items": hvd_pages["500"]["total_items"],
        "page_500_last_id": hvd_pages["500"]["last_id"], "page_501_serves_datasets": hvd_pages["501"]["datasets"],
        "page_501_first_id": hvd_pages["501"]["first_id"],
        "edp_dane_gov_pl_records": pc["edp_catalogue_dane_gov_pl"]["records"]}
    json.dump(pc, open(os.path.join(ROOT, "data", "poland_case.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps({"pages": {k: {x: v[x] for x in ("first_id", "last_id", "ec_list_ids_on_page", "applicableLegislation",
                                                      "hvdCategory", "eli_2023_138", "dcat_license", "dct_license", "datasets")}
                                for k, v in hvd_pages.items()}, "hyp": pc["harvest_hypothesis"]}, indent=0))


if __name__ == "__main__":
    main()
