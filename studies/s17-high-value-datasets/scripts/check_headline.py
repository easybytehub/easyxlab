#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Assert every number in the README abstract (and the paper's headline sentences, when paper.md is
present) against data/. Exit 1 on any mismatch."""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open(os.path.join(ROOT, "data", "summary.json")))
PAPER_URL = "https://easybyte.es/lab/studies/s17/paper/"


def f(n):
    return f"{n:,}"


def p(a, b):
    return f"{100 * a / b:.1f}%"


N = S["census_total"]
h1 = list(csv.DictReader(open(os.path.join(ROOT, "data", "category_without_eli_by_catalogue.csv"))))
top5 = [r for r in h1 if r["catalogue"] != "none"][:5]
lic, api_m = S["datasets_licence"], S["api_modelled"]
pol = S["poland"]
pol["source_flag_national"] = S["poland"]["source_flag_national"]
zero_names = {"BG": "Bulgaria", "CY": "Cyprus", "HU": "Hungary", "PL": "Poland", "RO": "Romania",
              "SI": "Slovenia", "SK": "Slovakia"}
assert S["member_states_zero"] == list(zero_names), S["member_states_zero"]

# --- 1. summary.json against an independent recount from the published CSVs (review minor #7)
rec = list(csv.DictReader(open(os.path.join(ROOT, "data", "census_records.csv"))))
reach = list(csv.DictReader(open(os.path.join(ROOT, "data", "reach_sample.csv"))))
req = [r for r in reach if r["outcome"] not in ("skipped_robots", "bad_url")]
recount = {
    "census_total": len(rec),
    "de_hvd": sum(r["country"] == "DE" for r in rec),
    "census_distinct_base_ids": len({r["dataset_id"].split("~~")[0] for r in rec}),
    "eli_without_category_census": sum(r["n_categories"] == "0" for r in rec),
    "licence_none_confirmed_rdf": sum(r["rdf_licence_check"] == "confirmed_none" for r in rec),
    "api_modelled": sum(r["api_index_access_service"] == "1" or r["api_rdf_served"] == "1" for r in rec),
    "reach_requested": len(req), "reach_ok": sum(r["outcome"] == "ok" for r in req),
    # skipped_robots split by whether the sampled URL itself was requested (closing review 4, 2026-10-05)
    "reach_skipped_robots_before_request": sum(r["outcome"] == "skipped_robots" and r["hops"] == "0" for r in reach),
    "reach_skipped_robots_after_redirect": sum(r["outcome"] == "skipped_robots" and r["hops"] != "0" for r in reach),
    "half_tagged_records": sum(1 for _ in open(os.path.join(ROOT, "data", "half_tagged_ids.csv"))) - 1,
    # distinct records, not catalogue rows: 2 records are in both bev-at and bmlfuw-at (closing review 2026-10-05)
    "half_tagged_top5_catalogues": sum(
        1 for r in csv.DictReader(open(os.path.join(ROOT, "data", "half_tagged_ids.csv")))
        if set(r["catalogue"].split(";")) & {t["catalogue"] for t in top5}),
}
for v in ("pass", "fail", "unclear", "none"):
    recount["lic_" + v] = sum(r["licence_verdict"] == v for r in rec)
# the text says the 12 were "requested once": every one of them must have exactly one hop
assert all(r["hops"] == "1" for r in reach if r["outcome"] == "skipped_robots" and r["hops"] != "0")
# D5 sensitivity with its own rule (closing review 3, 2026-10-05): drop the hosts whose robots.txt is still
# unreadable after redirects (anything but a parsed file, an absent one or an HTML page) and recount.
audit = json.load(open(os.path.join(ROOT, "data", "robots_redirect_audit.json")))
d5 = {h["host"] for h in audit["hosts"] if h["robots_after_redirects"] not in ("ok", "absent", "html", "nl-reservation")}
req_d5 = [r for r in req if r["host"] not in d5]
for k, v in {"hosts_excluded": len(d5), "requested": len(req_d5),
             "ok": sum(r["outcome"] == "ok" for r in req_d5)}.items():
    recount["reach_d5_sensitivity." + k] = v
bad_recount = [k for k, v in recount.items()
               if v != (S["datasets_licence"][k[4:]] if k.startswith("lic_")
                        else S["reach_d5_sensitivity"][k.split(".")[1]] if k.startswith("reach_d5_sensitivity.")
                        else S[k])]
for k in bad_recount:
    print(f"MISMATCH summary.json vs CSV recount: {k}")
print(f"summary.json vs CSV recount: {len(recount) - len(bad_recount)}/{len(recount)} match")

# --- 2. README abstract
q5z = S["zero_states_q5"]
oc = S["licence_other_closed_as_E"]
ph = S["poland_id_ranges"]
README_CLAIMS = [
    f"For {len(S['member_states_zero'])} of the 27 Member States (Bulgaria, Cyprus, Hungary, Poland, Romania, Slovenia and Slovakia), the European portal does not identify any dataset as HVD",
    f"{S['member_states_with_hvd']} of 27 have at least one",
    f"The portal flags {f(N)} records in all, which are {f(S['census_distinct_base_ids'])} distinct datasets",
    f"{f(S['de_komserv4gdi_rlp'])} of the {f(N)} records come from one Rhineland-Palatinate municipal geoportal",
    "| Cyprus, Slovenia, Slovakia | yes | yes | 0 |" if all(q5z[k] == "yes" for k in ("CY", "SI", "SK")) else "__q5_yes__",
    "| Hungary, Poland, Romania | yes | no | 0 |" if all(q5z[k] == "no" for k in ("HU", "PL", "RO")) else "__q5_no__",
    "| Bulgaria | no | no | 0 |" if q5z["BG"] == "no" else "__bg__",
    f"| Estonia | yes | no | {f(S['q5_no_with_hvd']['EE'])} |",
    f"| Greece | no | no | {f(S['q5_no_with_hvd']['GR'])} |",
    f"flags {pol['source_flag_ec_list']} datasets as HVD from the EU list",
    f"We found {pol['ec_list_found_on_edp']} of them",
    f"hold {sum(len(v['ec_list_ids_on_page']) for v in S['poland_feed_hvd_pages'].values())} of these datasets",
    f"The {pol['source_flag_ec_list'] - pol['ec_list_found_on_edp']} not found all have IDs of {f(ph['missing_min_id'])} or more, while all {pol['ec_list_found_on_edp']} found have IDs of {f(ph['found_max_id'])} or less",
    f"500 × 20 = {f(ph['advertised_pages_x_per_page'])} items out of {f(ph['total_items'])}",
    f"{f(S['category_without_eli_total'])} records carry an HVD category but not the regulation's ELI",
    f"They are {f(S['half_tagged_distinct_not_in_census'])} distinct datasets not already counted",
    f"{f(S['half_tagged_top5_catalogues'])} of the {f(S['category_without_eli_total'])} come from five catalogues",
    f"{f(S['eli_without_category_census'])} of {f(N)} ({p(S['eli_without_category_census'], N)}) carry the ELI without a category",
    f"in {f(lic['pass'])} of {f(N)} records ({p(lic['pass'], N)})",
    f"{f(lic['fail'])} ({p(lic['fail'], N)}) have at least one distribution",
    f"{f(S['licence_fail_only_other_closed'])} of those {f(lic['fail'])} fail only because",
    f"{f(oc['fail'])} ({p(oc['fail'], N)}) fail",
    f"{f(S['licence_none_confirmed_rdf'])} ({p(S['licence_none_confirmed_rdf'], N)}) have no licence and no rights statement",
    f"{f(api_m)} of {f(N)} records ({p(api_m, N)}) have a Data Service",
    f"Another {f(S['api_inferable_only'])} have a distribution",
    f"{f(S['reach_ok'])} of {f(S['reach_requested'])} sampled distribution URLs ({p(S['reach_ok'], S['reach_requested'])})",
    f"Another {S['reach_outcomes']['skipped_robots']} were stopped by robots.txt, because it disallowed them or could "
    f"not be read: {S['reach_skipped_robots_before_request']} before any request, and "
    f"{S['reach_skipped_robots_after_redirect']} after one request, at the address they redirected to",
    PAPER_URL,
]
rows = {r["member_state"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "by_member_state.csv")))}
others = [r for k, r in rows.items() if r["gap_class_q5"] == "consistent-yes"]
assert all(r["odm_P12_denoted_in_metadata"] == "yes" for r in others)
README_CLAIMS.append(f"| {len(others)} others | yes | yes | {min(int(r['hvd_datasets']) for r in others)} to "
                     f"{f(max(int(r['hvd_datasets']) for r in others))} each |")

# --- 3. paper headline sentences
PAPER_CLAIMS = [
    f"For {len(S['member_states_zero'])} of the 27 Member States the portal does not identify any dataset as HVD",
    f"The portal flags {f(N)} records, {f(S['census_distinct_base_ids'])} distinct datasets",
    f"{f(S['de_komserv4gdi_rlp'])} come from one German municipal geoportal",
    f"Another {f(S['category_without_eli_total'])} records carry an HVD category without the regulation's ELI",
    f"Art. 4(3) in {f(lic['pass'])} of {f(N)} records ({p(lic['pass'], N)})",
    f"{f(api_m)} of {f(N)} ({p(api_m, N)}) have the Data Service",
    f"{f(S['reach_ok'])} of {f(S['reach_requested'])} distribution URLs ({p(S['reach_ok'], S['reach_requested'])}) "
    f"answered with a 2xx status; robots.txt stopped another {S['reach_outcomes']['skipped_robots']}",
    f"Of {f(S['reach_sampled'])} sampled URLs, {S['reach_outcomes']['skipped_robots']} were stopped by robots.txt: "
    f"it disallowed {S['reach_skipped_robots_by_reason']['robots']}, and for "
    f"{S['reach_skipped_robots_by_reason']['robots-unavailable']} it could not be read. "
    f"{S['reach_skipped_robots_before_request']} of the {S['reach_outcomes']['skipped_robots']} were not requested. "
    f"The other {S['reach_skipped_robots_after_redirect']} were requested once and answered with a redirect, which we "
    f"did not follow because the robots.txt at its target disallowed it "
    f"({S['reach_skipped_robots_after_redirect_by_reason']['robots']}) or could not be read "
    f"({S['reach_skipped_robots_after_redirect_by_reason']['robots-unavailable']}). One URL was malformed. "
    f"Of the other {f(S['reach_requested'])}, **{f(S['reach_ok'])} ({S['reach_ok_pct']}%)** answered 2xx",
    f"The {f(S['census_surplus_records_same_base_id'])} surplus records are almost all Spanish ({S['surplus_records_by_ms']['ES']} of Spain's {f(rows['ES']['hvd_datasets'] and int(rows['ES']['hvd_datasets']))}",
    f"10,032 of them come from one Rhineland-Palatinate municipal geoportal ({S['de_komserv4gdi_rlp_pct_of_de']}% of Germany, {p(S['de_komserv4gdi_rlp'], N)} of the whole census)",
    f"At least {f(S['de_rlp_sources'])} ({S['de_rlp_pct_of_de']}% of Germany)",
    f"They are {f(S['half_tagged_distinct_base_ids'])} distinct base IDs, and {S['half_tagged_twins_of_census']} of the records",
    f"Among those {S['half_tagged_twins_of_census']}, {S['half_tagged_twins_of_govdata']} are twins of German govdata records",
    f"({f(S['half_tagged_twins_of_govdata_by_catalogue']['gdi-de'])} of them in the geodata catalogue gdi-de, "
    f"{S['half_tagged_twins_of_govdata_by_catalogue']['none']} not linked to a catalogue), and "
    f"{S['half_tagged_twins_by_census_catalogue']['datos-gob-es']['codsi']} are codsi twins of datos-gob-es records",
    f"{f(S['category_without_eli_no_catalogue'])} more are not linked to a catalogue, and "
    f"{S['category_without_eli_european_level']} are in European-level catalogues",
    f"The rest are {f(S['half_tagged_distinct_not_in_census'])} distinct datasets",
    f"{f(S['half_tagged_top5_catalogues'])} of the {f(S['category_without_eli_total'])} records come from five catalogues",
    f"{S['half_tagged_top5_in_two_catalogues']} records are in both Austrian catalogues",
    f"{f(S['licence_fail_only_other_closed'])} of the {f(lic['fail'])} fail only because",
    f"With `other-closed` in E, {f(oc['fail'])} records ({p(oc['fail'], N)}) fail and {f(oc['unclear'])} are unclear",
    f"6,963 records fail under the frozen rule" if S["de_rlp_fail"] == 6963 else "__rlp_fail__",
    f"**{f(S['licence_none_confirmed_rdf'])} ({p(S['licence_none_confirmed_rdf'], N)} of the census) have neither",
    f"{f(S['distributions_with_eli'])} of {f(S['distributions'])} distributions ({S['distributions_with_eli_pct']}%)",
    f"the rate is {S['reach_ok_weighted_pct']}%",
    f"the rate is {f(S['reach_d5_sensitivity']['ok'])} of {f(S['reach_d5_sensitivity']['requested'])} ({S['reach_d5_sensitivity']['ok_pct']}%)",
    f"{S['reach_ok_html_of_range_get'][0]} of the {S['reach_ok_html_of_range_get'][1]} successful ranged GETs",
    f"| P12 \"denoted in metadata\": yes ({S['odm_p12_yes']}) | {S['gap_classes']['consistent-yes']} | {len(S['self_yes_portal_zero'])} (CY, HU, PL, RO, SI, SK) |",
    f"| Q5 \"DCAT-AP HVD tag\": yes ({S['odm_q5_yes']}) | {S['gap_classes_q5']['consistent-yes']} | {S['gap_classes_q5']['self-yes-portal-zero']} (CY, SI, SK) |",
    f"| Q5: no (6) | 2 (EE 87, GR 1,281) | 4 (BG, HU, PL, RO) |",
    f"and {f(pol['source_flag_national'])} with its national flag",
    f"({f(S['poland_edp_catalogue']['records'])} records)",
    f"while `hydra:totalItems` is {f(ph['total_items'])}",
]


def section(text, head="## Abstract"):
    i = text.find(head)
    j = text.find("\n## ", i + 5)
    return text[i:j if j > 0 else None]


def check(path, claims, whole=False):
    t = open(path).read()
    t = t if whole else section(t)
    bad = [c for c in claims if c not in t]
    if not re.search(r"\d[\d,]* of [\d,]+ \(\d+(\.\d+)?%\)", t):
        bad.append("<no 'X of N (p%)' pattern>")
    for c in bad:
        print(f"MISMATCH in {os.path.basename(path)}: {c}")
    print(f"{os.path.basename(path)}: {len(claims) - len(bad)}/{len(claims)} claims match")
    return not bad


ok = not bad_recount
ok = check(os.path.join(ROOT, "README.md"), README_CLAIMS) and ok
pp = os.path.join(ROOT, "paper.md")
if os.path.exists(pp):
    ok = check(pp, PAPER_CLAIMS, whole=True) and ok
else:
    print(f"paper.md is not in the public package: the paper is at {PAPER_URL}")

# --- 3. hand-typed twins of the D5 sensitivity (closing review 3, 2026-10-05)
d5s = S["reach_d5_sensitivity"]
TWINS = {
    "METHOD.md": [f"Without those {d5s['hosts_excluded']} hosts the reachability figure is {f(d5s['ok'])} of "
                  f"{f(d5s['requested'])} ({d5s['ok_pct']} %) instead of {f(S['reach_ok'])} of "
                  f"{f(S['reach_requested'])} ({S['reach_ok_pct']} %)"],
    "VERIFICATION.md": [f"reachability without those {d5s['hosts_excluded']} hosts {f(d5s['ok'])} of "
                        f"{f(d5s['requested'])} ({d5s['ok_pct']}%)",
                        f"{S['reach_outcomes']['skipped_robots']} `skipped_robots` "
                        f"({S['reach_skipped_robots_before_request']} not requested; "
                        f"{S['reach_skipped_robots_after_redirect']} requested once, redirect not followed); "
                        f"{f(S['reach_ok'])} of the other {f(S['reach_requested'])} URLs 2xx ({S['reach_ok_pct']}%)"],
}
# hand-typed twin of the skipped_robots split (closing review 4, 2026-10-05)
sa = S["reach_skipped_robots_after_redirect_by_reason"]
TWINS["METHOD.md"].append(
    f"That holds for {S['reach_skipped_robots_before_request']} of the {S['reach_outcomes']['skipped_robots']} sampled "
    f"URLs in it (`hops == 0` in `data/reach_sample.csv`). The other {S['reach_skipped_robots_after_redirect']} "
    f"(`hops == 1`) were requested once, answered with a redirect, and the redirect was not followed because the "
    f"robots.txt at its target disallowed it ({sa['robots']}, sampled on `kort.plandata.dk` and `miljoegis.mim.dk`) "
    f"or could not be read ({sa['robots-unavailable']})")
TWINS["METHOD.md"].append(f"excluding `bad_url` ({f(S['reach_requested'])})")
for name, claims in TWINS.items():
    tp = os.path.join(ROOT, name)
    if not os.path.exists(tp):
        continue
    t = open(tp).read()
    bad = [c for c in claims if c not in t]
    for c in bad:
        print(f"MISMATCH in {name}: {c}")
    print(f"{name}: {len(claims) - len(bad)}/{len(claims)} claims match")
    ok = not bad and ok
sys.exit(0 if ok else 1)
