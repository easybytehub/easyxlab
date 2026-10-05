# SPDX-License-Identifier: Apache-2.0
"""Step 6 (offline, data/ only): every published figure. Writes data/by_member_state.csv,
data/by_catalogue.csv, data/reach_by_member_state.csv and data/summary.json."""
import collections
import csv
import datetime
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hvd_rules as R  # noqa: E402

OTHER_CLOSED = "http://dcat-ap.de/def/licenses/other-closed"
# Rhineland-Palatinate sources, by the host embedded in the portal's dataset ID (review M1); explicit list
RLP_EXTRA = ("geoportal-koblenz-de", "gis-schweich-de", "gis-saarburg-kell-de", "gis-wittlich-land-de",
             "geoportal-trier-de", "gis-suedeifel-de", "gis-ruwer-de", "gis-bitburgerland-de", "gis-hermeskeil-de",
             "gis-vg-arzfeld-de", "adenau-de")


def source_of(dataset_id):
    """Source host as encoded in the portal's dataset ID (e.g. https-komserv4gdi-service24-rlp-de-...)."""
    i = dataset_id.replace("https:-", "https-").replace(".", "-")
    m = re.match(r"(?:https?-)?(?:www-)?([a-z0-9-]*?-(?:de|es|gr|fr|be|lv|lt|nl|lu|se|ie|pt|cz|it|mt|dk|ee|hr|fi|at|"
                 r"eu|com|org|net|info|gov))-", i)
    return m.group(1) if m else "(no host in ID)"


def is_rlp(src):
    return "rlp-de" in src or src in RLP_EXTRA or any(src.endswith(x) for x in RLP_EXTRA)


def base_id(i):
    return i.split("~~")[0]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
MS = ["AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "GR", "ES", "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU",
      "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"]


def rd(name):
    return list(csv.DictReader(open(os.path.join(D, name), newline="")))


def wcsv(name, rows):
    with open(os.path.join(D, name), "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def wilson(k, n, z=1.96):
    if n == 0:
        return ("", "")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(100 * (c - h), 1), round(100 * (c + h), 1))


def pct(a, b, nd=1):
    return round(100 * a / b, nd) if b else 0.0


def main():
    rec = rd("census_records.csv")
    totals = {r["country"]: int(r["portal_datasets"]) for r in rd("portal_totals.csv")}
    h1 = rd("category_without_eli_by_catalogue.csv")
    odm = {("GR" if r["country_code"] == "EL" else r["country_code"]): r for r in rd("odm2025_answers.csv")}
    sps = json.load(open(os.path.join(D, "sparql_summary.json")))
    pol = json.load(open(os.path.join(D, "poland_case.json")))
    reach = rd("reach_sample.csv")
    lbd = {r["dataset_id"]: r for r in rd("licences_by_dataset.csv")}
    half = rd("half_tagged_ids.csv")
    audit = json.load(open(os.path.join(D, "robots_redirect_audit.json")))

    # --- licence verdicts recomputed from the published dataset-level values (frozen rules), and the
    # sensitivity with the catch-all value other-closed treated as class E (review M2)
    def verdict(r, other_closed_as_e=False):
        vals = r["licence_values"].split()
        cl = ["E" if (other_closed_as_e and (v == OTHER_CLOSED or v == "other-closed")) else R.licence_class(v)
              for v in vals]
        if int(r["n_dist_no_licence"]) or int(r["n_dist"]) == 0:
            cl.append("N")
        return R.dataset_licence_verdict(cl)
    v_frozen = {i: verdict(r) for i, r in lbd.items()}
    v_oc = {i: verdict(r, True) for i, r in lbd.items()}
    mism = sum(1 for r in rec if v_frozen[r["dataset_id"]] != r["licence_verdict"])
    assert mism == 0, f"{mism} licence verdicts differ when recomputed from licences_by_dataset.csv"
    oc_counts = collections.Counter(v_oc.values())
    fail_only_oc = sum(1 for i in v_frozen if v_frozen[i] == "fail" and v_oc[i] != "fail")

    # --- concentration by source (review M1)
    src = collections.Counter((r["country"], source_of(r["dataset_id"])) for r in rec)
    per_ms = collections.Counter(r["country"] for r in rec)
    conc = []
    for m in sorted(per_ms):
        top = sorted(((k[1], v) for k, v in src.items() if k[0] == m), key=lambda x: (-x[1], x[0]))[:3]
        for rank, (sname, v) in enumerate(top, 1):
            conc.append({"member_state": m, "rank": rank, "source_in_dataset_id": sname, "records": v,
                         "share_of_member_state_pct": pct(v, per_ms[m])})
    wcsv("source_concentration.csv", conc)
    de = [r for r in rec if r["country"] == "DE"]
    de_komserv = sum(1 for r in de if source_of(r["dataset_id"]) == "komserv4gdi-service24-rlp-de")
    de_rlp = sum(1 for r in de if is_rlp(source_of(r["dataset_id"])))
    de_rlp_fail = sum(1 for r in de if is_rlp(source_of(r["dataset_id"])) and r["licence_verdict"] == "fail")

    # --- duplicates by base ID (portal suffix ~~n) (review M4)
    groups = collections.defaultdict(list)
    for r in rec:
        groups[base_id(r["dataset_id"])].append(r["country"])
    distinct_ms = collections.Counter()
    for b, cs in groups.items():
        distinct_ms[cs[0]] += 1
    # surplus records = records minus distinct base IDs (all twins found are within one Member State)
    assert all(len(set(cs)) == 1 for cs in groups.values())
    dup_rec = collections.Counter({m: per_ms[m] - distinct_ms[m] for m in per_ms if per_ms[m] - distinct_ms[m]})
    census_bases = set(groups)
    half_bases = collections.Counter(base_id(r["dataset_id"]) for r in half)
    half_twins = sum(1 for r in half if base_id(r["dataset_id"]) in census_bases)
    half_distinct = len(half_bases)
    half_distinct_new = len([b for b in half_bases if b not in census_bases])
    govdata_tilde = [r for r in rec if r["catalogue"] == "govdata" and "~~" in r["dataset_id"]]
    # Twins of HVD records, by the census catalogue of the twin, one count per half-tagged record and in both
    # directions of the ~~n suffix (closing review 2, 2026-10-05). The earlier count matched only half-tagged IDs
    # without a suffix against govdata IDs with one, which gave 255 of the 990 govdata twins.
    census_cats = collections.defaultdict(set)
    for r in rec:
        census_cats[base_id(r["dataset_id"])].add(r["catalogue"])
    twins_by_census_cat = collections.defaultdict(collections.Counter)
    for r in half:
        cs = census_cats.get(base_id(r["dataset_id"]))
        if cs:
            twins_by_census_cat[";".join(sorted(cs))][r["catalogue"]] += 1
    assert sum(sum(c.values()) for c in twins_by_census_cat.values()) == half_twins
    govdata_twins_in_half = twins_by_census_cat.get("govdata", collections.Counter())

    # --- reachability without the hosts affected by deviation D5 (robots.txt redirects)
    # The hosts whose robots.txt still cannot be read once redirects are followed (no answer, more than five
    # redirects, or a 5xx, which METHOD §7 skips): the same rule as robots_unreadable_after_redirects in
    # 08_robots_redirect_audit.py, 8 keys on 7 hosts. Cut by host name, the only key published in
    # reach_sample.csv. Closing review 3 (2026-10-05): the earlier set took the 2 Danish hosts and left out
    # the two 5xx hosts. The Danish hosts' sampled URLs are all outside the denominator already (asserted).
    def robots_unreadable(h):
        note = str(h["robots_after_redirects"])
        return h["status"] is None or note == "server-error" or note.startswith("error")

    assert sum(map(robots_unreadable, audit["hosts"])) == audit["robots_unreadable_after_redirects"]
    d5_hosts = {h["host"] for h in audit["hosts"] if robots_unreadable(h)}
    d5_disallowed_hosts = {h["host"] for h in audit["hosts"] if h["would_be_disallowed"]}
    assert not [r for r in reach if r["host"] in d5_disallowed_hosts and r["outcome"] not in ("skipped_robots", "bad_url")]
    req_d5 = [r for r in reach if r["outcome"] not in ("skipped_robots", "bad_url") and r["host"] not in d5_hosts]
    ok_d5 = sum(1 for r in req_d5 if r["outcome"] == "ok")

    def api(r):
        m = r["api_index_access_service"] == "1" or r["api_rdf_served"] == "1"
        return "modelled" if m else ("inferable" if r["api_inferable"] == "1" else "none")

    by = collections.defaultdict(collections.Counter)
    for r in rec:
        k = by[r["country"]]
        k["hvd"] += 1
        k["no_category"] += int(r["n_categories"] == "0")
        k["dist"] += int(r["n_dist"])
        k["dist_eli"] += int(r["n_dist_eli"])
        k["lic_" + r["licence_verdict"]] += 1
        k["licD1_" + r["licence_verdict_D1"]] += 1
        k["rdf_" + (r["rdf_licence_check"] or "na")] += 1
        k["api_" + api(r)] += 1
        k["has_D"] += int(int(r["lic_D"]) > 0)
        k["has_C"] += int(int(r["lic_C"]) > 0)
        for c in "ABCDEN":
            k["d" + c] += int(r["lic_" + c])
    # Half-tagged records counted once each (closing review, 2026-10-05). A record can sit in two catalogues
    # (gdi-de and govdata, bev-at and bmlfuw-at), so summing the rows of category_without_eli_by_catalogue.csv
    # counts it twice. Per catalogue that file is right; per Member State or over several catalogues, count
    # the distinct records of half_tagged_ids.csv.
    cat_country = {r["catalogue"]: r["country"] for r in h1}
    half_cats = [set(r["catalogue"].split(";")) for r in half]
    membership = collections.Counter(c for cs in half_cats for c in cs)
    assert membership == {r["catalogue"]: int(r["datasets"]) for r in h1}, \
        "half_tagged_ids.csv and category_without_eli_by_catalogue.csv disagree"
    h1c = collections.Counter(m for cs in half_cats for m in {cat_country[c] for c in cs})
    top5_catalogues = {r["catalogue"] for r in sorted((r for r in h1 if r["catalogue"] != "none"),
                                                       key=lambda r: -int(r["datasets"]))[:5]}

    rows = []
    for m in MS:
        k = by.get(m, collections.Counter())
        o = odm.get(m, {})
        n = k["hvd"]
        p12 = o.get("P12", "")
        gap = ("consistent-yes" if p12 == "yes" and n > 0 else "self-yes-portal-zero" if p12 == "yes"
               else "self-no-portal-some" if n > 0 else "consistent-no")
        q5 = o.get("Q5", "")
        gap_q5 = ("consistent-yes" if q5 == "yes" and n > 0 else "self-yes-portal-zero" if q5 == "yes"
                  else "self-no-portal-some" if n > 0 else "consistent-no")
        rows.append({
            "member_state": m, "portal_datasets": totals.get(m, 0), "hvd_datasets": n,
            "hvd_distinct_base_ids": distinct_ms.get(m, 0), "hvd_surplus_records_same_base_id": dup_rec.get(m, 0),
            "top_source_in_ids": next((c["source_in_dataset_id"] for c in conc if c["member_state"] == m), ""),
            "top_source_share_pct": next((c["share_of_member_state_pct"] for c in conc if c["member_state"] == m), ""),
            "hvd_share_of_portal_pct": pct(n, totals.get(m, 0), 2),
            "category_without_eli": h1c.get(m, 0), "eli_without_category": k["no_category"],
            "distributions": k["dist"], "distributions_with_eli": k["dist_eli"],
            "licence_pass": k["lic_pass"], "licence_fail": k["lic_fail"], "licence_unclear": k["lic_unclear"],
            "licence_none_index": k["lic_none"], "licence_none_confirmed_rdf": k["rdf_confirmed_none"],
            "licence_none_rights_only": k["rdf_rights_only"], "licence_none_but_in_rdf": k["rdf_licence_in_rdf"],
            "api_modelled": k["api_modelled"], "api_inferable_only": k["api_inferable"], "api_none": k["api_none"],
            "odm_P11_applying": o.get("P11", ""), "odm_P12_denoted_in_metadata": p12,
            "odm_Q5_dcatap_hvd_tag": q5, "gap_class": gap, "gap_class_q5": gap_q5,
        })
    wcsv("by_member_state.csv", rows)

    bc = collections.defaultdict(collections.Counter)
    ccountry = {}
    for r in rec:
        k = bc[r["catalogue"]]
        ccountry[r["catalogue"]] = r["country"]
        k["hvd"] += 1
        k["no_category"] += int(r["n_categories"] == "0")
        k["lic_" + r["licence_verdict"]] += 1
        k["rdf_" + (r["rdf_licence_check"] or "na")] += 1
        k["api_" + api(r)] += 1
    for r in h1:
        bc[r["catalogue"]]["h1"] += int(r["datasets"])
        ccountry.setdefault(r["catalogue"], r["country"])
    crow = [{"catalogue": c, "country": ccountry.get(c, ""), "hvd_datasets": k["hvd"],
             "category_without_eli": k["h1"], "eli_without_category": k["no_category"],
             "licence_pass": k["lic_pass"], "licence_fail": k["lic_fail"], "licence_none_index": k["lic_none"],
             "licence_none_confirmed_rdf": k["rdf_confirmed_none"], "api_modelled": k["api_modelled"]}
            for c, k in sorted(bc.items(), key=lambda x: (-x[1]["hvd"], -x[1]["h1"], x[0]))]
    wcsv("by_catalogue.csv", crow)

    # reachability
    frame = collections.Counter()
    rr = collections.defaultdict(collections.Counter)
    for r in reach:
        rr[r["country"].upper()][r["outcome"]] += 1
        frame[r["country"].upper()] = int(r["frame_size"])
    reach_rows, wsum, wtot = [], 0.0, 0
    for m in sorted(rr):
        k = rr[m]
        requested = sum(v for o, v in k.items() if o not in ("skipped_robots", "bad_url"))
        lo, hi = wilson(k["ok"], requested)
        reach_rows.append({"member_state": m, "frame_urls": frame[m], "sampled": sum(k.values()),
                           "requested": requested, "ok": k["ok"], "ok_pct": pct(k["ok"], requested),
                           "ci95_low": lo, "ci95_high": hi, "client_error_notfound": k["client_error_notfound"],
                           "client_error_auth": k["client_error_auth"], "client_error_other": k["client_error_other"],
                           "server_error": k["server_error"], "network": k["network"],
                           "too_many_redirects": k["too_many_redirects"], "skipped_robots": k["skipped_robots"],
                           "bad_url": k["bad_url"]})
        if requested:
            wsum += frame[m] * k["ok"] / requested
            wtot += frame[m]
    wcsv("reach_by_member_state.csv", reach_rows)
    rt = collections.Counter()
    for k in rr.values():
        rt += k
    requested = sum(v for o, v in rt.items() if o not in ("skipped_robots", "bad_url"))
    html_dl = sum(1 for r in reach if r["outcome"] == "ok" and r["method"] == "range-get" and "html" in r["ctype"])
    ok_get = sum(1 for r in reach if r["outcome"] == "ok" and r["method"] == "range-get")
    # `skipped_robots` is not always "not requested" (closing review 4, 2026-10-05): with hops == 0 the sampled
    # URL was never requested; with hops >= 1 it was requested, answered 3xx, and robots.txt stopped a later hop.
    skipped = [r for r in reach if r["outcome"] == "skipped_robots"]
    skipped_after = [r for r in skipped if int(r["hops"] or 0) > 0]

    T = collections.Counter()
    for m in MS:
        T += by.get(m, collections.Counter())
    ALL = collections.Counter()
    for k in by.values():
        ALL += k
    n_ms = sum(by[m]["hvd"] for m in MS)
    zero = [m for m in MS if by[m]["hvd"] == 0]
    s = {
        "snapshot_utc": sps["census_snapshot_utc"],
        "census_total": len(rec), "census_member_states": n_ms, "census_non_ms": len(rec) - n_ms,
        "member_states_with_hvd": 27 - len(zero), "member_states_zero": zero,
        "de_hvd": by["DE"]["hvd"], "de_share_pct": pct(by["DE"]["hvd"], len(rec)),
        "portal_total_datasets": sps["portal_total_datasets"],
        "category_without_eli_total": sps["h1_category_without_eli_total"],
        "category_without_eli_member_states": sum(h1c[m] for m in MS),
        # the rest of the 13,948, so that table 1 adds up (closing review 2, 2026-10-05)
        "category_without_eli_no_catalogue": h1c.get("", 0),
        "category_without_eli_european_level": h1c.get("EUROPE", 0),
        "eli_without_category_census": ALL["no_category"],
        "eli_datasets_rdf": sps["eli_datasets_by_category"],
        "malformed_eli_triples": sum(v["n"] for v in sps["malformed_eli"]),
        "datasets_only_malformed_eli": len(sps["datasets_only_malformed_eli"]),
        "distributions": ALL["dist"], "distributions_with_eli": ALL["dist_eli"],
        "distributions_with_eli_pct": pct(ALL["dist_eli"], ALL["dist"]),
        "distribution_licence_classes": {c: ALL["d" + c] for c in "ABCDEN"},
        "datasets_licence": {v: ALL["lic_" + v] for v in ("pass", "fail", "unclear", "none")},
        "datasets_licence_pct": {v: pct(ALL["lic_" + v], len(rec)) for v in ("pass", "fail", "unclear", "none")},
        "datasets_licence_D1": {v: ALL["licD1_" + v] for v in ("pass", "fail", "unclear", "none")},
        "datasets_with_closed_or_nc": ALL["has_D"], "datasets_with_share_alike": ALL["has_C"],
        "licence_none_confirmed_rdf": ALL["rdf_confirmed_none"], "licence_none_rights_only": ALL["rdf_rights_only"],
        "licence_none_but_in_rdf": ALL["rdf_licence_in_rdf"],
        "licence_none_confirmed_pct": pct(ALL["rdf_confirmed_none"], len(rec)),
        "ttl_sample_n": len(sps["ttl_sample"]),
        "ttl_sample_without_licence_or_rights": sum(1 for r in sps["ttl_sample"] if r["license"] == 0 and r["rights"] == 0),
        "api_modelled": ALL["api_modelled"], "api_modelled_pct": pct(ALL["api_modelled"], len(rec)),
        "api_inferable_only": ALL["api_inferable"], "api_none": ALL["api_none"],
        "odm_p12_yes": sum(1 for r in rows if r["odm_P12_denoted_in_metadata"] == "yes"),
        "odm_q5_yes": sum(1 for r in rows if r["odm_Q5_dcatap_hvd_tag"] == "yes"),
        "gap_classes": dict(collections.Counter(r["gap_class"] for r in rows)),
        "self_yes_portal_zero": [r["member_state"] for r in rows if r["gap_class"] == "self-yes-portal-zero"],
        "self_no_portal_some": [r["member_state"] for r in rows if r["gap_class"] == "self-no-portal-some"],
        "reach_sampled": len(reach), "reach_requested": requested, "reach_ok": rt["ok"],
        "reach_ok_pct": pct(rt["ok"], requested), "reach_ok_weighted_pct": round(100 * wsum / wtot, 1) if wtot else 0,
        "reach_outcomes": dict(rt), "reach_ok_html_of_range_get": [html_dl, ok_get],
        "reach_skipped_robots_by_reason": dict(collections.Counter(r["skip_reason"] for r in skipped)),
        "reach_skipped_robots_before_request": len(skipped) - len(skipped_after),
        "reach_skipped_robots_after_redirect": len(skipped_after),
        "reach_skipped_robots_after_redirect_hops": dict(collections.Counter(int(r["hops"]) for r in skipped_after)),
        "reach_skipped_robots_after_redirect_by_reason": dict(collections.Counter(r["skip_reason"]
                                                                                for r in skipped_after)),
        "reach_member_states": len(rr), "reach_hosts": len({r["host"] for r in reach}),
        "gap_classes_q5": dict(collections.Counter(r["gap_class_q5"] for r in rows)),
        "zero_states_q5": {r["member_state"]: r["odm_Q5_dcatap_hvd_tag"] for r in rows if r["hvd_datasets"] == 0},
        "q5_no_with_hvd": {r["member_state"]: r["hvd_datasets"] for r in rows
                           if r["odm_Q5_dcatap_hvd_tag"] == "no" and r["hvd_datasets"] > 0},
        "licence_other_closed_as_E": {v: oc_counts[v] for v in ("pass", "fail", "unclear", "none")},
        "licence_other_closed_as_E_fail_pct": pct(oc_counts["fail"], len(rec)),
        "licence_fail_only_other_closed": fail_only_oc,
        "licence_verdicts_recomputed_from_values_mismatch": mism,
        "de_komserv4gdi_rlp": de_komserv, "de_komserv4gdi_rlp_pct_of_de": pct(de_komserv, by["DE"]["hvd"]),
        "de_rlp_sources": de_rlp, "de_rlp_pct_of_de": pct(de_rlp, by["DE"]["hvd"]),
        "de_rlp_pct_of_census": pct(de_rlp, len(rec)), "de_rlp_fail": de_rlp_fail,
        "census_surplus_records_same_base_id": sum(dup_rec.values()), "surplus_records_by_ms": dict(dup_rec),
        "census_distinct_base_ids": len(groups),
        "half_tagged_records": len(half), "half_tagged_distinct_base_ids": half_distinct,
        "half_tagged_twins_of_census": half_twins, "half_tagged_distinct_not_in_census": half_distinct_new,
        "govdata_tilde_records": len(govdata_tilde), "half_tagged_twins_of_govdata": sum(govdata_twins_in_half.values()),
        "half_tagged_twins_of_govdata_by_catalogue": dict(govdata_twins_in_half.most_common()),
        "half_tagged_twins_by_census_catalogue": {k: dict(v.most_common()) for k, v in
                                                  sorted(twins_by_census_cat.items(), key=lambda x: -sum(x[1].values()))},
        "robots_redirect_audit": {k: audit[k] for k in audit if k != "hosts"},
        "reach_d5_sensitivity": {"hosts_excluded": len(d5_hosts), "requested": len(req_d5), "ok": ok_d5,
                                 "ok_pct": pct(ok_d5, len(req_d5))},
        "poland_id_ranges": pol.get("harvest_hypothesis", {}),
        "poland_feed_hvd_pages": {k: {x: v[x] for x in ("ec_list_ids_on_page", "applicableLegislation", "hvdCategory",
                                                        "eli_2023_138", "dcat_license", "dct_license")}
                                  for k, v in pol.get("feed_pages", {}).items() if v["ec_list_ids_on_page"]},
        "poland": {k: pol[k] for k in ("source_flag_ec_list", "source_flag_national", "ec_list_found_on_edp",
                                       "ec_list_found_with_eli", "ec_list_found_with_category",
                                       "ec_list_found_with_dist_licence")},
        "poland_edp_catalogue": pol["edp_catalogue_dane_gov_pl"], "poland_feed_page1": pol["source_feed_page1"],
    }
    # dates, completeness and the remaining abstract figures (added 2026-10-05 for claims.csv)
    applicable = datetime.date(2024, 6, 9)  # Art. 6: 16 months after entry into force (9 February 2023)
    census_day = datetime.date.fromisoformat(s["snapshot_utc"][:10])
    days = (census_day - applicable).days
    whole = (census_day.year - applicable.year) * 12 + census_day.month - applicable.month - (census_day.day < applicable.day)
    others = [int(r["hvd_datasets"]) for r in rows if int(r["hvd_datasets"]) > 0
              and r["odm_P12_denoted_in_metadata"] == "yes" and r["odm_Q5_dcatap_hvd_tag"] == "yes"]
    assert set(h1c) <= set(MS) | {"", "EUROPE"} and sum(h1c.values()) == len(half) == s["category_without_eli_total"]
    s.update({
        "applicable_date": f"{applicable.day} {applicable.strftime('%B')} {applicable.year}",
        "census_date": census_day.isoformat(),
        "snapshot_hhmm_utc": s["snapshot_utc"][11:16],
        "days_since_applicable": days,
        "months_since_applicable": days / (365.2425 / 12),  # mean Gregorian month
        "whole_months_since_applicable": whole,
        "member_states_eu": 27,
        "member_states_without_hvd": 27 - s["member_states_with_hvd"],
        "odm_edition": 2025,
        "hvd_facet_total": sps["hvd_facet_total"],
        # distinct records in any of the five largest catalogues (records with no catalogue excluded)
        "half_tagged_top5_catalogues": sum(1 for cs in half_cats if cs & top5_catalogues),
        "half_tagged_top5_in_two_catalogues": sum(1 for cs in half_cats if len(cs & top5_catalogues) > 1),
        "hvd_ms_p12_q5_yes": {"n": len(others), "min": min(others), "max": max(others)},
        "poland_feed_pages_ec_ids": len({i for v in s["poland_feed_hvd_pages"].values() for i in v["ec_list_ids_on_page"]}),
        # a process figure reported by the independent review (README «Automation and review»), not in data/
        "review_records_audited": 48,
    })
    json.dump(s, open(os.path.join(D, "summary.json"), "w"), indent=1)
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
