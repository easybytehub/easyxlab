# SPDX-License-Identifier: Apache-2.0
"""Step 3 (offline, needs data/raw/): reduce the raw census and SPARQL results to publishable,
per-dataset and aggregated files in data/ (dataset IDs, flags and counts only; no contact data).

Outputs: data/census_records.csv, data/sparql_summary.json, data/licence_values.csv,
data/hvd_categories.csv, data/category_without_eli_by_catalogue.csv, data/portal_totals.csv."""
import collections
import csv
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hvd_rules as R  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data")
FIELDS = ["dataset_id", "country", "catalogue", "n_dist", "eli_dataset", "n_categories", "n_dist_eli",
          "lic_A", "lic_B", "lic_C", "lic_D", "lic_E", "lic_N", "licence_verdict", "licence_verdict_D1",
          "rdf_licence_check", "api_index_access_service", "api_rdf_served", "api_inferable"]


def lic_value(d):
    lic = d.get("license") or {}
    return lic.get("resource") or lic.get("id")


def wcsv(name, rows, fields):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.DictWriter(f, fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    sp = json.load(open(os.path.join(RAW, "sparql_main.json")))
    conf = json.load(open(os.path.join(RAW, "sparql_licence_confirm.json")))["confirmation"]
    rdf = json.load(open(os.path.join(RAW, "rdf_checks.json")))
    served = set(sp["api_served_datasets"])
    lic_values = collections.Counter()
    cat_counter = collections.Counter()
    rows, lbd = [], []
    for line in gzip.open(os.path.join(RAW, "census.jsonl.gz"), "rt"):
        r = json.loads(line)
        dists = r.get("distributions") or []
        cats = R.hvd_categories([x.get("id") for x in (r.get("hvd_category") or [])])
        for h in cats:
            cat_counter[h.rsplit("/", 1)[-1]] += 1
        classes = []
        for d in dists:
            v = lic_value(d)
            cl = R.licence_class(v)
            classes.append(cl)
            if v:
                lic_values[(R.normalise_licence(v), cl, R.licence_class(v, strict=False))] += 1
        verdict = R.dataset_licence_verdict(classes)
        check = ""
        if verdict == "none":
            cf = conf.get(r["id"], {})
            check = ("licence_in_rdf" if cf.get("distLic") or cf.get("dsLic") else
                     "rights_only" if cf.get("rights") else "confirmed_none")
        cc = collections.Counter(classes)
        vals = sorted({R.normalise_licence(lic_value(d)) for d in dists if lic_value(d)})
        lbd.append({"dataset_id": r["id"], "n_dist": len(dists), "n_dist_no_licence": cc.get("N", 0),
                    "licence_values": " ".join(vals)})
        rows.append({
            "dataset_id": r["id"], "country": ((r.get("country") or {}).get("id") or "").upper(),
            "catalogue": (r.get("catalog") or {}).get("id") or "", "n_dist": len(dists),
            "eli_dataset": R.eli_status(r.get("applicable_legislation"))[0], "n_categories": len(cats),
            "n_dist_eli": sum(R.eli_status(d.get("applicable_legislation"))[0] == "exact" for d in dists),
            **{f"lic_{k}": cc.get(k, 0) for k in "ABCDEN"},
            "licence_verdict": verdict,
            "licence_verdict_D1": R.dataset_licence_verdict([R.licence_class(lic_value(d), strict=False) for d in dists]),
            "rdf_licence_check": check,
            "api_index_access_service": int(any(d.get("access_service") for d in dists)),
            "api_rdf_served": int(r["id"] in served),
            "api_inferable": int(any(R.inferable_api((d.get("format") or {}).get("id"),
                                                      (d.get("access_url") or []) + (d.get("download_url") or []))
                                     for d in dists)),
        })
    rows.sort(key=lambda x: (x["country"], x["catalogue"], x["dataset_id"]))
    wcsv("census_records.csv", rows, FIELDS)
    lbd.sort(key=lambda x: x["dataset_id"])
    wcsv("licences_by_dataset.csv", lbd, ["dataset_id", "n_dist", "n_dist_no_licence", "licence_values"])
    wcsv("licence_values.csv", [{"licence_value": v, "class": cl, "class_D1": c2, "distributions": n}
                                for (v, cl, c2), n in sorted(lic_values.items(), key=lambda x: (-x[1], x[0]))],
         ["licence_value", "class", "class_D1", "distributions"])
    wcsv("hvd_categories.csv", [{"category": k, "datasets": n} for k, n in cat_counter.most_common()],
         ["category", "datasets"])
    cats = {c["id"]: c["country"] for c in json.load(open(os.path.join(RAW, "catalogues.json")))}
    wcsv("category_without_eli_by_catalogue.csv",
         [{"catalogue": k, "country": (cats.get(k) or "").upper(), "datasets": n}
          for k, n in sorted(sp["h1_by_catalogue"].items(), key=lambda x: (-x[1], x[0]))],
         ["catalogue", "country", "datasets"])
    tot = json.load(open(os.path.join(RAW, "country_totals.json")))
    hv = json.load(open(os.path.join(RAW, "hvd_facets.json")))
    wcsv("portal_totals.csv", [{"country": k.upper(), "portal_datasets": v,
                                "hvd_facet": hv["facets"]["country"].get(k, 0)}
                               for k, v in sorted(tot["facets"]["country"].items())],
         ["country", "portal_datasets", "hvd_facet"])
    json.dump({
        "census_snapshot_utc": hv["utc"], "portal_total_datasets": tot["count"], "hvd_facet_total": hv["count"],
        "h1_category_without_eli_total": sp["h1_total"], "eli_datasets_by_category": sp["eli_datasets_by_category"],
        "malformed_eli": sp["h2_variants"], "datasets_only_malformed_eli": sp["h2_datasets_only_malformed"],
        "eli_subjects_by_type": sp["eli_subjects_by_type"], "api_rdf_served_datasets": len(served),
        "licence_confirmation_population": len(conf),
        "cz_terms_of_use": rdf["cz_terms_of_use"], "cz_eli_distributions": rdf["cz_eli_distributions"],
        "ttl_sample": rdf["ttl_sample"], "ttl_sample_population": rdf["ttl_sample_population"],
    }, open(os.path.join(OUT, "sparql_summary.json"), "w"), indent=1)
    print(len(rows), "records")


if __name__ == "__main__":
    main()
