#!/usr/bin/env python3
"""Build the published per-host table and all aggregates from the scan records.

    python3 scripts/aggregate.py build     # data/raw/scan.jsonl -> data/records.csv (needs the raw scan)
    python3 scripts/aggregate.py summary   # data/records.csv (+ data/comment_audit.csv) -> data/summary.json, tables

`summary` works offline from the published data/records.csv alone.
"""
import csv
import json
import re
import math
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
CLASSES = ["agnostic_reservation", "named_bots_only", "comment_only", "none_stated"]
PARTIAL = ["named_bots_robots_only_partial", "comment_only_robots_only_partial", "none_stated_robots_only_partial"]
FIELDS = ["host", "country", "wikidata", "crux_rank_bucket", "robots_state", "robots_status", "read_reason",
          "class", "partial", "contradiction", "agnostic_channels", "unnamed_blocked_root", "ai_blocked_root_n",
          "ai_blocked_root", "headline4_blocked_root", "content_signal_ai_train", "content_signal_lines",
          "content_usage_lines", "content_usage_unnamed_root", "content_usage_header", "tdmrep_file_state",
          "tdmrep_file_any_reservation", "tdmrep_file_root", "tdmrep_header", "tdmrep_meta", "tdmrep_policy_any",
          "nl_reservation", "nl_prohibition", "noai", "llms_txt", "home_status", "home_final_host", "checked_utc",
          "content_usage_values", "rescan_d5", "deleted_after_collection"]


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def share(k, n):
    return dict(k=k, n=n, pct=round(100 * k / n, 1) if n else None, ci95=wilson(k, n))


def build():
    rows = []
    frame = {r["host"] for r in csv.DictReader(open(os.path.join(DATA, "frame.csv")))}
    for line in open(os.path.join(DATA, "raw", "scan.jsonl")):
        r = json.loads(line)
        if r["host"] not in frame:          # D6: hosts excluded from the frame after the scan
            continue
        if "crash" in r:
            rows.append(dict(host=r["host"], country=r["country"], wikidata=r["wikidata"],
                             crux_rank_bucket=r["crux_rank_bucket"], robots_state="crash", class_=""))
            continue
        rb, tdm, home, v = r["robots"], r["tdmrep_file"], r["home"], r["verdict"]
        b = lambda x: int(bool(x))  # noqa: E731
        rows.append(dict(
            host=r["host"], country=r["country"], wikidata=r["wikidata"], crux_rank_bucket=r["crux_rank_bucket"],
            robots_state=rb["state"], robots_status=rb["status"] or "", read_reason=r["read"]["reason"],
            **{"class": v["class_"]},
            partial=b(v.get("partial")), contradiction=b(v.get("contradiction")),
            agnostic_channels=";".join(v.get("agnostic_channels") or []),
            unnamed_blocked_root=b(rb.get("unnamed_blocked_root")),
            ai_blocked_root_n=len(rb.get("ai_blocked_root") or []),
            ai_blocked_root=";".join(rb.get("ai_blocked_root") or []),
            headline4_blocked_root=";".join(rb.get("headline4_blocked_root") or []),
            content_signal_ai_train=";".join(rb.get("content_signal_ai_train") or []),
            content_signal_lines=len(rb.get("content_signal") or []),
            content_usage_lines=len(rb.get("content_usage") or []),
            content_usage_unnamed_root=rb.get("content_usage_unnamed_root") or "",
            content_usage_header=(home.get("hdr_content_usage") or "")[:80],
            tdmrep_file_state=tdm.get("state", ""), tdmrep_file_any_reservation=b(tdm.get("any_reservation")),
            tdmrep_file_root="" if tdm.get("root") is None else tdm["root"],
            tdmrep_header=(home.get("hdr_tdm_reservation") or "")[:20], tdmrep_meta=(home.get("meta_tdm_reservation") or "")[:20],
            tdmrep_policy_any=b(tdm.get("has_policy") or home.get("hdr_tdm_policy") or home.get("meta_tdm_policy")),
            nl_reservation=b(rb.get("nl_reservation")), nl_prohibition=b(rb.get("nl_prohibition")),
            noai=b(v.get("noai")), llms_txt=r["llms_txt"].get("state", ""),
            home_status=home.get("status") or "", home_final_host=home.get("final_host") or "",
            checked_utc=r["checked_utc"],
            content_usage_values=";".join(rb.get("content_usage") or [])[:120],
            rescan_d5=int(bool(r.get("rescan_d5"))),
            deleted_after_collection={True: "d2"}.get(r["read"].get("deleted_after_collection"),
                                                      r["read"].get("deleted_after_collection") or "")))
    rows.sort(key=lambda d: (d["country"], d["host"]))
    with open(os.path.join(DATA, "records.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "records", file=sys.stderr)


def band(n):
    return "large (n>=100)" if n >= 100 else ("medium (30-99)" if n >= 30 else "small (n<30)")


def summary():
    recs = list(csv.DictReader(open(os.path.join(DATA, "records.csv"))))
    I = lambda r, k: r[k] not in ("", "0")  # noqa: E731
    ok = [r for r in recs if r["robots_state"] in ("ok", "unavailable", "nl_prohibition")]
    full = [r for r in ok if not r["read_reason"]]
    part = [r for r in ok if r["read_reason"]]
    n, nf = len(ok), len(full)
    cf = Counter(r["class"] for r in full)
    ca = Counter(r["class"] for r in ok)
    agn = lambda L: sum(r["class"] == "agnostic_reservation" for r in L)  # noqa: E731
    named = lambda L: [r for r in L if int(r["ai_blocked_root_n"]) > 0]  # noqa: E731
    tdm = lambda L: [r for r in L if "tdmrep" in r["agnostic_channels"]]  # noqa: E731
    S = dict(frame_hosts=len(recs), robots_obtained=n, robots_unreachable=len(recs) - n,
             robots_states=dict(Counter(r["robots_state"] for r in recs)), fully_read=nf, robots_only=len(part),
             robots_only_deleted=dict(Counter(r["deleted_after_collection"] for r in part if r["deleted_after_collection"])),
             rescanned_d5=sum(I(r, "rescan_d5") for r in recs))
    # --- headline: fully read sites (exact for that subset)
    S["full"] = dict(classes={c: share(cf[c], nf) for c in CLASSES},
                     named_any=share(len(named(full)), nf),
                     named_no_agnostic=share(sum(r["class"] != "agnostic_reservation" for r in named(full)), len(named(full))),
                     tdmrep=share(len(tdm(full)), nf),
                     contradictions=share(sum(I(r, "contradiction") for r in full), nf),
                     contradiction_hosts=[r["host"] for r in full if I(r, "contradiction")])
    # --- all sites with robots.txt: agnostic & TDMRep are minima, the named-only class a maximum
    S["all"] = dict(classes={c: share(ca[c], n) for c in CLASSES + PARTIAL},
                    agnostic_min=share(agn(ok), n),
                    named_any=share(len(named(ok)), n),           # exact: robots.txt was read everywhere
                    named_no_agnostic_max=share(sum(r["class"] != "agnostic_reservation" for r in named(ok)), len(named(ok))),
                    named_only_max=share(ca["named_bots_only"] + ca["named_bots_robots_only_partial"], n),
                    none_max=share(ca["none_stated"] + ca["none_stated_robots_only_partial"], n),
                    tdmrep_min=share(len(tdm(ok)), n))
    # --- sensitivity: the frozen access rule (no D5 re-scan: hosts re-read in D5 count as robots-only)
    fz = [r for r in full if not I(r, "rescan_d5")]
    fz_fr = [r for r in fz if r["country"] == "FR"]
    S["frozen_rule"] = dict(fully_read=len(fz), agnostic=share(agn(fz), len(fz)), named_any=share(len(named(fz)), len(fz)),
                            named_no_agnostic=share(sum(r["class"] != "agnostic_reservation" for r in named(fz)), len(named(fz))),
                            tdmrep=share(len(tdm(fz)), len(fz)), france_tdmrep=share(len(tdm(fz_fr)), len(fz_fr)),
                            contradictions=sum(I(r, "contradiction") for r in fz))
    S["contradictions_by_rule"] = dict(current_rule=sum(I(r, "contradiction") for r in full), frozen_rule=S["frozen_rule"]["contradictions"])
    S["full_home_not_observed"] = [r["host"] for r in full if not r["home_status"] or not r["home_status"].isdigit()]
    S["agnostic_by_channel_full"] = {
        "robots_star_disallow_root": share(sum(I(r, "unnamed_blocked_root") for r in full), nf),
        "tdmrep_any_channel": share(len(tdm(full)), nf),
        "content_signal_ai_train_no": share(sum("no" in r["content_signal_ai_train"].split(";") for r in full), nf),
        "content_usage_train_ai_n": share(sum(r["content_usage_unnamed_root"] == "n" or "content_usage_header" in r["agnostic_channels"] for r in full), nf)}
    T = tdm(full)
    S["tdmrep"] = dict(any=len(T), file=sum("tdmrep_file" in r["agnostic_channels"] for r in T),
                       header=sum("tdmrep_header" in r["agnostic_channels"] for r in T),
                       meta=sum("tdmrep_meta" in r["agnostic_channels"] for r in T),
                       not_in_file=sum("tdmrep_file" not in r["agnostic_channels"] for r in T),
                       with_policy=sum(I(r, "tdmrep_policy_any") for r in T),
                       file_states=dict(Counter(r["tdmrep_file_state"] for r in full)),
                       by_country=dict(Counter(r["country"] for r in T)))
    fr_full = [r for r in full if r["country"] == "FR"]
    S["tdmrep"]["france_full"] = share(len(tdm(fr_full)), len(fr_full))
    S["content_signal"] = dict(any_line=sum(int(r["content_signal_lines"]) > 0 for r in ok),
                               ai_train_no=sum("no" in r["content_signal_ai_train"].split(";") for r in ok),
                               ai_train_yes=sum("yes" in r["content_signal_ai_train"].split(";") for r in ok))
    ai_n = [r for r in ok if "ai=n" in r["content_usage_values"].replace(" ", "").lower()]
    S["content_usage"] = dict(any_line=sum(int(r["content_usage_lines"]) > 0 for r in ok),
                              train_ai_n_unnamed=sum(r["content_usage_unnamed_root"] == "n" for r in ok),
                              ai_n_vocab01=len(ai_n), header_any=sum(bool(r["content_usage_header"]) for r in ok))
    S["sensitivity"] = dict(
        ai_n_as_training_full=share(sum(r["class"] == "agnostic_reservation" or r in ai_n for r in full), nf),
        ai_n_as_training_all=share(sum(r["class"] == "agnostic_reservation" or r in ai_n for r in ok), n),
        noai_full=share(sum(r["class"] == "agnostic_reservation" or I(r, "noai") for r in full), nf),
        noai_hosts=sum(I(r, "noai") for r in ok))
    comm = [r for r in ok if I(r, "nl_reservation") or I(r, "nl_prohibition")]
    commf = [r for r in full if I(r, "nl_reservation") or I(r, "nl_prohibition")]
    S["comments"] = dict(statement_any=share(len(comm), n), reservation=sum(I(r, "nl_reservation") for r in ok),
                         general_prohibition_flag=sum(I(r, "nl_prohibition") for r in ok),
                         full_statement=share(len(commf), nf),
                         full_statement_without_agnostic=sum(r["class"] != "agnostic_reservation" for r in commf),
                         full_statement_and_named_only=sum(r["class"] == "named_bots_only" for r in commf),
                         comment_only_class_full=cf["comment_only"])
    llms_req = [r for r in full if r["llms_txt"] in ("present", "absent")]
    S["llms_txt"] = share(sum(r["llms_txt"] == "present" for r in llms_req), len(llms_req))
    S["most_blocked_named"] = Counter(t for r in ok for t in r["ai_blocked_root"].split(";") if t).most_common(8)
    S["headline4_all_four"] = sum(len(r["headline4_blocked_root"].split(";")) == 4 for r in ok if r["headline4_blocked_root"])
    # --- per country and per band (fully read sites)
    by = defaultdict(list)
    for r in recs:
        by[r["country"]].append(r)
    countries = []
    for cc, lst in sorted(by.items()):
        okc = [r for r in lst if r in ok]
        fc = [r for r in okc if not r["read_reason"]]
        c = Counter(r["class"] for r in fc)
        row = dict(country=cc, frame=len(lst), band=band(len(lst)), robots_obtained=len(okc), fully_read=len(fc),
                   **{k: c[k] for k in CLASSES}, robots_only=len(okc) - len(fc),
                   named_ai_any=len(named(okc)), tdmrep=len(tdm(fc)),
                   comment_statement=sum(I(r, "nl_reservation") or I(r, "nl_prohibition") for r in okc),
                   contradiction=sum(I(r, "contradiction") for r in fc))
        a = c["agnostic_reservation"]
        row["agnostic_pct_full"] = round(100 * a / len(fc), 1) if len(fc) >= 30 else ""
        row["agnostic_ci95_full"] = "-".join(str(x) for x in wilson(a, len(fc))) if len(fc) >= 30 else ""
        countries.append(row)
    with open(os.path.join(DATA, "by_country.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(countries[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(countries)
    S["countries_with_frame"] = len(countries)
    S["country_full"] = {r["country"]: share(r["agnostic_reservation"], r["fully_read"]) for r in countries}
    bands = defaultdict(Counter)
    for row in countries:
        b = bands[row["band"]]
        b["countries"] += 1
        for k in ["frame", "robots_obtained", "fully_read", "named_ai_any", "tdmrep"] + CLASSES:
            b[k] += row[k]
    S["bands"] = {k: dict(v, agnostic_full=share(v["agnostic_reservation"], v["fully_read"])) for k, v in sorted(bands.items())}
    bk = defaultdict(list)
    for r in ok:
        bk[int(r["crux_rank_bucket"])].append(r)
    S["by_crux_bucket"] = {str(k): dict(n=len(v), named_ai_any=share(len(named(v)), len(v)),
                                        agnostic_full=share(agn([r for r in v if not r["read_reason"]]),
                                                            sum(not r["read_reason"] for r in v)))
                           for k, v in sorted(bk.items())}
    for name in ("comment_audit_summary.json", "deviation_d2.json", "deviation_d4.json", "deviation_d5.json"):
        p = os.path.join(DATA, name)
        if os.path.exists(p):
            S[name.split(".")[0]] = {k: v for k, v in json.load(open(p)).items() if k not in ("hosts_data_deleted", "request_times_utc")}
    # --- added 2026-10-05 [after the freeze] for claims.csv: figures the abstract quotes that had no key
    named480 = [r for r in named(full) if r["class"] != "agnostic_reservation"]
    nb_comments = {r["host"] for r in named480 if I(r, "nl_reservation") or I(r, "nl_prohibition")}
    nb_ai_n = {r["host"] for r in named480 if r in ai_n}
    nb_noai = {r["host"] for r in named480 if I(r, "noai")}
    S["named_only_breakdown"] = dict(of=len(named480), comments=len(nb_comments), ai_n=len(nb_ai_n), noai=len(nb_noai),
                                     total=len(nb_comments | nb_ai_n | nb_noai),
                                     overlaps=len(nb_comments & nb_ai_n) + len(nb_comments & nb_noai) + len(nb_ai_n & nb_noai))
    S["crux_rank_max"] = json.load(open(os.path.join(DATA, "frame_meta.json")))["rank_max"]
    S["dates"] = dict(ai_act_gpai_obligations="2 August 2025", ai_act_legacy_models="2 August 2027",
                      ai_act_fines="2 August 2026", lab_robots_rule="3 October 2026")  # AI Act Arts. 111(3), 113
    prov = list(csv.DictReader(open(os.path.join(DATA, "providers_panel.csv"))))
    read = {r["provider"] for r in prov if r["crawler_doc_read"] == "yes"}
    names = lambda col: len({r["provider"] for r in prov if r["provider"] in read and r[col] == "1"})  # noqa: E731
    S["providers"] = dict(n=len({r["provider"] for r in prov}), doc_read=len(read),
                          read_on=sorted({r["fetched_utc"][:10] for r in prov if r["provider"] in read}),
                          robots_txt=names("robots_txt"), tdmrep=names("tdmrep"), content_signal=names("content_signal"),
                          content_usage=names("content_usage_aipref"), noai=names("noai_meta"))
    S["providers"]["read_on"] = S["providers"]["read_on"][0] if len(S["providers"]["read_on"]) == 1 else S["providers"]["read_on"]
    for name in ("independent_audit_v2.json", "independent_audit_v3.json", "request_audit.json", "deviation_d7.json"):
        S[name.split(".")[0]] = {k: v for k, v in json.load(open(os.path.join(DATA, name))).items()
                                 if k not in ("hosts", "evidence", "first_request_not_robots_hosts")}
    v2s, v3s = S["independent_audit_v2"]["sample"], S["independent_audit_v3"]["sample"]
    v3p = S["independent_audit_v3"]["prohibition"]
    S["audit_figures"] = dict(v2_sample_sites=int(re.match(r"(\d+) hosts", v2s).group(1)),
                              v3_sample_sites=int(re.search(r"(\d+) hosts$", v3s).group(1)),
                              v3_prohibition_recall_overall=v3p["recall_overall_k"] / v3p["recall_overall_n"])
    ra, d7 = S["request_audit"], json.load(open(os.path.join(DATA, "deviation_d7.json")))
    by_dev = {k.split()[0]: v for k, v in ra["breach_requests_by_deviation"].items()}
    S["access"] = dict(d1_requests=by_dev["D1"], d2_requests=by_dev["D2"], d2_sites=S["deviation_d2"]["n_hosts"],
                       d4_requests=by_dev["D4"], d4_sites=len(json.load(open(os.path.join(DATA, "deviation_d4.json")))["hosts"]),
                       d7_requests=by_dev["D7"], d7_sites=d7["n_hosts"],
                       d7_sites_mediahuis_notice=sum(v.startswith("is not to be used for the purposes of text and data mining")
                                                     for v in d7["evidence"].values()),
                       breaches_declared=1 + len(by_dev),  # D0 (the scouting pilot, not in the request log) + the logged ones
                       logged_beyond_robots=ra["requests_beyond_robots_to_nl_hosts"],
                       logged_beyond_robots_attributed=sum(ra["requests_beyond_robots_to_nl_hosts_by_deviation"].values()),
                       logged_before_robots=ra["requests_to_those_hosts"])
    json.dump(S, open(os.path.join(DATA, "summary.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: S[k] for k in ["frame_hosts", "robots_obtained", "fully_read", "robots_only", "full", "all",
                                        "tdmrep", "sensitivity", "comments", "llms_txt", "bands"]}, indent=None)[:6000])


if __name__ == "__main__":
    {"build": build, "summary": summary}[sys.argv[1]]()
