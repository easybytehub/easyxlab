#!/usr/bin/env python3
"""Check the headline numbers of README.md (abstract) and paper.md against data/.

Each claim is a phrase built from data/ (counts, denominators, percentages, Wilson intervals,
channel splits, band figures, deviation counts). It must occur in the text with number
boundaries: a claim starting or ending with a digit cannot match inside a longer number, so
"0 contradictions" does not match "10 contradictions". Exit 1 if any claim is missing.
What this does NOT check: numbers in the text that are not listed as claims here, and whether the
wording around a number is right (see VERIFICATION.md). paper.md is not in the public package;
when it is absent only README.md is checked.
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
J = lambda n: json.load(open(os.path.join(D, n)))  # noqa: E731
S = J("summary.json")
IND = J("independent_audit_v2.json")
D2, D4, D5 = J("deviation_d2.json"), J("deviation_d4.json"), J("deviation_d5.json")
panel = list(csv.DictReader(open(os.path.join(D, "providers_panel.csv"))))
read = [p for p in panel if p["crawler_doc_read"] == "yes"]


def kn(x):
    return f"{x['k']:,} of {x['n']:,} ({x['pct']}%)"


def ci(x):
    return f"{x['ci95'][0]}–{x['ci95'][1]}%"


F, A, T, B = S["full"], S["all"], S["tdmrep"], S["bands"]
FZ = S["frozen_rule"]
D7 = J("deviation_d7.json")
IND3 = J("independent_audit_v3.json")
AUD = J("comment_audit_summary.json")
RA = J("request_audit.json")
band = lambda k: B[k]["agnostic_full"]  # noqa: E731
bci = lambda x: f"{x['k']} of {x['n']} ({x['pct']}%, CI {x['ci95'][0]}–{x['ci95'][1]})"  # noqa: E731
LB, MB, SB = band("large (n>=100)"), band("medium (30-99)"), band("small (n<30)")
fr, pl = S["country_full"]["FR"], S["country_full"]["PL"]
agf = F["classes"]["agnostic_reservation"]
# Named blockers with no agnostic reservation that state one only in a form not counted as one:
# robots.txt comments, Content-Usage ai=n (vocab-01 label) or noai. Counted from data/records.csv.
rec = list(csv.DictReader(open(os.path.join(D, "records.csv"))))
nbo = [r for r in rec if r["class"] == "named_bots_only"]
sig = {"comments": [r for r in nbo if r["nl_reservation"] == "1"],
       "ai_n": [r for r in nbo if r["content_usage_values"] == "ai=n"],
       "noai": [r for r in nbo if r["noai"] == "1"]}
sig_any = {r["host"] for v in sig.values() for r in v}
sig_ok = len(sig_any) == sum(len(v) for v in sig.values()) and len(nbo) == F["named_no_agnostic"]["k"]
# Agnostic sites whose only agnostic channel is a `*` group disallowing `/` (a total block, not a TDM-specific reservation).
# Fully read sites only (the 154 read on robots.txt alone include 11 more agnostic hosts).
star_only = sum(r["partial"] == "0" and r["class"] == "agnostic_reservation"
                and r["agnostic_channels"] == "robots_star_disallow_root" for r in rec)
NOT_COUNTED = "state no reservation in a form we count as addressed to any crawler"
d1 = RA["breach_requests_by_deviation"]["D1 (before that host's robots.txt)"]
claims = {
    "frame": f"{S['frame_hosts']:,} news websites",
    "countries": f"{S['countries_with_frame']} Member States",
    "fully_read": f"{S['fully_read']:,} sites we could read in full",
    "agnostic_full": kn(agf),
    "agnostic_full_ci": ci(agf),
    "named_full": kn(F["named_any"]),
    "named_no_agn_full": kn(F["named_no_agnostic"]),
    "named_no_agn_full_ci": ci(F["named_no_agnostic"]),
    "none_full": kn(F["classes"]["none_stated"]),
    "named_no_agn_signal": f"{len(sig_any)} of the {len(nbo)} state one only" if sig_ok else "MISMATCH",
    "named_no_agn_wording": f"{kn(F['named_no_agnostic'])}, CI {ci(F['named_no_agnostic'])}, {NOT_COUNTED}",
    "agnostic_star_only": f"{star_only} of them through a `robots.txt` that disallows the whole site",
    "named_no_agn_signal_split": f"`robots.txt` comments ({len(sig['comments'])}), which an RFC 9309 parser discards, as `Content-Usage: ai=n`, a label the current IETF draft dropped ({len(sig['ai_n'])}), or as the non-standard `noai` ({len(sig['noai'])})"
    if sig_ok else "MISMATCH",
    "agnostic_all_min": "at least " + kn(A["agnostic_min"]),
    "named_no_agn_all_max": f"at most {A['named_no_agnostic_max']['k']:,} of {A['named_no_agnostic_max']['n']:,} ({A['named_no_agnostic_max']['pct']}%)",
    "band_large": f"large countries {LB['k']} of {LB['n']} ({LB['pct']}%)",
    "band_medium": f"medium {MB['k']} of {MB['n']} ({MB['pct']}%)",
    "band_small": f"small {SB['k']} of {SB['n']} ({SB['pct']}%)",
    "frozen": f"{kn(FZ['agnostic'])}, CI {ci(FZ['agnostic'])}",
    "frozen_contr": f"and {FZ['contradictions']} contradictions",
    "tdmrep_full": kn(F["tdmrep"]),
    "tdmrep_full_ci": ci(F["tdmrep"]),
    "tdmrep_not_file": f"{T['not_in_file']} of the {T['any']}",
    "tdmrep_split": f"meta {T['meta']}, header {T['header']}, file {T['file']}",
    "tdmrep_fr": f"{T['france_full']['k']} of {T['france_full']['n']} fully read French sites ({T['france_full']['pct']}%)",
    "cs_no": f"`ai-train=no` appears on {S['content_signal']['ai_train_no']} sites",
    "cu_n": f"`train-ai=n` appears on {S['content_usage']['train_ai_n_unnamed']}",
    "cu_ai": f"{S['content_usage']['ai_n_vocab01']} sites send `Content-Usage: ai=n`",
    "sens_ai_n": kn(S["sensitivity"]["ai_n_as_training_full"]),
    "contradictions": f"{F['contradictions']['k']} contradictions among the {F['contradictions']['n']:,} under the current rule, {S['contradictions_by_rule']['frozen_rule']} under the frozen rule",
    "comments": kn(S["comments"]["statement_any"]),
    "robots_only": f"For {S['robots_only']} sites we read `robots.txt` only",
    "d1": f"D1: {d1} requests",
    "d2": f"D2: {D2['requests_beyond_robots_to_them']} requests to {D2['n_hosts']} sites",
    "d4": f"D4: {D4['requests_beyond_robots']} requests to one site",
    "d7": f"D7: {D7['requests_beyond_robots']} requests to {D7['n_hosts']} sites",
    "aud_res": f"right on {AUD['v1_reservation']['tp']} of {AUD['v1_reservation']['flagged']} flags",
    "aud_v2": f"right on {AUD['v2_prohibition']['tp']} of {AUD['v2_prohibition']['flagged']}",
    "ind_pro": f"right on {IND['prohibition']['precision_k']} of {IND['prohibition']['precision_n']} flags and found {IND['prohibition']['recall_k']} of {IND['prohibition']['recall_n']}",
    "ind_res": f"right on {IND['reservation']['precision_k']} of {IND['reservation']['precision_n']} flags and found {IND['reservation']['recall_k']} of {IND['reservation']['recall_n']}",
    "ind3_pro": f"prohibition {IND3['prohibition']['precision_k']} of {IND3['prohibition']['precision_n']} in the sample",
    "ind3_recall": f"({IND3['prohibition']['recall_overall_k']} of {IND3['prohibition']['recall_overall_n']}) once the {D7['n_hosts']} D7 misses",
    "ind3_res": f"reservation {IND3['reservation']['precision_k']} of {IND3['reservation']['precision_n']}",
    "providers": f"{len(read)} of {len(panel)} providers",
    "providers_robots": f"all {sum(p['robots_txt'] == '1' for p in read)} name robots.txt",
    "providers_other": f"None of the {len(read)} names TDMRep, Content-Signal, Content-Usage or `noai`"
    if all(p[k] == "0" for p in read for k in ("tdmrep", "content_signal", "content_usage_aipref", "noai_meta")) else "MISMATCH",
}
PAPER = ["frame", "agnostic_full", "agnostic_full_ci", "named_full", "named_no_agn_full", "named_no_agn_signal", "none_full", "tdmrep_full",
         "tdmrep_full_ci", "tdmrep_split", "tdmrep_not_file", "sens_ai_n", "comments", "providers"]
named_all = A["named_any"]
PAPER_EXTRA = {
    "p_table": f"| agnostic reservation | {agf['k']} | {agf['pct']}% | {agf['ci95'][0]}–{agf['ci95'][1]} |",
    "p_table_named": "| named bots only | {k} | {pct}% |".format(**F["classes"]["named_bots_only"]),
    "p_table_none": "| none stated | {k} | {pct}% |".format(**F["classes"]["none_stated"]),
    "p_named_all": f"{named_all['k']} of {named_all['n']:,} ({named_all['pct']}%)",
    "p_named_all_max": f"{A['named_no_agnostic_max']['k']:,} of {A['named_no_agnostic_max']['n']:,} ({A['named_no_agnostic_max']['pct']}%)",
    "p_agn_all_min": kn(A["agnostic_min"]),
    "p_frozen": kn(FZ["agnostic"]),
    "p_frozen_named": kn(FZ["named_any"]),
    "p_frozen_noagn": kn(FZ["named_no_agnostic"]),
    "p_frozen_fr": f"{FZ['france_tdmrep']['k']} of {FZ['france_tdmrep']['n']} under the frozen rule",
    "p_fr_tdm": f"{T['france_full']['k']} of {T['france_full']['n']} ({T['france_full']['pct']}%, CI {T['france_full']['ci95'][0]}–{T['france_full']['ci95'][1]}%)",
    "p_fr_agn": f"France {bci(fr)}",
    "p_pl": f"Poland {bci(pl)}",
    "p_band_large": bci(LB), "p_band_medium": bci(MB), "p_band_small": bci(SB),
    "p_contr": f"{F['contradictions']['k']} of {F['contradictions']['n']:,} under the current rule, {FZ['contradictions']} under the frozen rule",
    "p_all_four": f"{S['headline4_all_four']} sites block all four",
    "p_llms": f"{S['llms_txt']['k']} of {S['llms_txt']['n']:,} ({S['llms_txt']['pct']}%)",
    "p_noai": kn(S["sensitivity"]["noai_full"]),
    "p_bucket": "{k} ({pct}%) of the {n} sites in the top-1,000".format(**S["by_crux_bucket"]["1000"]["named_ai_any"]),
    "p_bucket_low": kn(S["by_crux_bucket"]["100000"]["named_ai_any"]),
    "p_comm_full": f"Among fully read sites, {S['comments']['full_statement']['k']} do. {S['comments']['full_statement_without_agnostic']} of those",
    "p_d5": f"It freed {D5['n_hosts']} sites",
    "p_d7": f"{D7['requests_in_rescan']} requests ({D7['requests_beyond_robots']} beyond `robots.txt`) went to {D7['n_hosts']} sites",
    "p_d2": f"{D2['requests_beyond_robots_to_them']} requests went to {D2['n_hosts']} sites",
    "p_robots_only": f"{S['robots_only']} sites were read on `robots.txt` alone, and {S['fully_read']:,} in full",
    "p_abs_named_no_agn": f"{kn(F['named_no_agnostic'])} of those {NOT_COUNTED}",
    "p_abs_star_only": f"({star_only} of them through a `robots.txt` that disallows the whole site",
    "p_61_split": f"{len(sig['comments'])} of them state a reservation only in comments, and {len(sig['ai_n']) + len(sig['noai'])} only in a label the headline does not count (`Content-Usage: ai=n`, {len(sig['ai_n'])}; `noai`, {len(sig['noai'])})"
    if sig_ok else "MISMATCH",
    "p_d8": f"at least {kn(A['agnostic_min'])}",
}
# Wording the third review (2026-10-05) found false for 23 of the 480 (6 `noai`, 17 `Content-Usage: ai=n`): it must not return.
BANNED = ["would meet no machine-readable reservation", "a crawler with a new name would meet no",
          "text-and-data-mining reservation addressed to any crawler"]


def norm(s):
    return re.sub(r"\s+", " ", s)


def present(claim, text):
    c = norm(claim)
    rx = re.escape(c)
    if c[:1].isdigit():
        rx = r"(?<![\d.,])" + rx
    if c[-1:].isdigit():
        rx = rx + r"(?![\d])"
    return re.search(rx, norm(text)) is not None


fail = 0
readme = open(os.path.join(ROOT, "README.md")).read()
abstract = readme.split("## Abstract", 1)[1].split("\n## ", 1)[0]
for k, s in claims.items():
    ok = present(s, abstract)
    fail += not ok
    print(("ok   " if ok else "FAIL ") + f"README {k}: {norm(s)}")
pp = os.path.join(ROOT, "paper.md")
if os.path.exists(pp):
    paper = open(pp).read()
    for k in PAPER:
        ok = present(claims[k], paper)
        fail += not ok
        print(("ok   " if ok else "FAIL ") + f"paper  {k}: {norm(claims[k])}")
    for k, s in PAPER_EXTRA.items():
        ok = present(s, paper)
        fail += not ok
        print(("ok   " if ok else "FAIL ") + f"paper  {k}: {s}")
else:
    print("paper.md is not in the public package: the paper is at https://easybyte.es/lab/studies/s16/paper/")
# The study's row in the repository's README (the headline the site shows), when the study sits in it.
rp = os.path.join(os.path.dirname(os.path.dirname(ROOT)), "README.md")
if os.path.exists(rp):
    rows_ = [ln for ln in open(rp, encoding="utf-8").read().splitlines() if ln.startswith("| [S16](")]
    nm, nn = F["named_any"], F["named_no_agnostic"]
    ROW = {
        "row_frame": f"Of {S['fully_read']:,} EU news sites read in full",
        "row_named": f"{nm['k']} block at least one AI crawler by name",
        "row_named_no_agn": f"but {nn['k']} of those ({nn['pct']}%) {NOT_COUNTED}",
        "row_named_no_agn_signal": f"{len(sig_any)} of the {nn['k']} state one only in `robots.txt` comments, in a label the current IETF draft dropped or in the non-standard `noai`" if sig_ok else "MISMATCH",
        "row_agnostic": f"Only {agf['k']} ({agf['pct']}%) state a reservation addressed to any crawler, whatever its name, {star_only} of them by closing the whole site to unnamed crawlers",
    }
    if len(rows_) != 1 or nm["n"] != S["fully_read"] or nn["n"] != nm["k"]:
        fail += 1
        print(f"FAIL root row: {len(rows_)} rows for S16, or the denominators of the row do not chain")
    else:
        for k, s in ROW.items():
            ok = present(s, rows_[0])
            fail += not ok
            print(("ok   " if ok else "FAIL ") + f"root   {k}: {s}")
else:
    print("not inside the studies repository: the root-table row is not checked")
texts = {"README.md": readme}
if os.path.exists(pp):
    texts["paper.md"] = open(pp).read()
if os.path.exists(rp):
    texts["root row"] = "\n".join(ln for ln in open(rp, encoding="utf-8").read().splitlines() if ln.startswith("| [S16]("))
for name, text in texts.items():
    for b in BANNED:
        if b in norm(text):
            fail += 1
            print(f"FAIL banned wording in {name}: {b}")
print("MISMATCHES:", fail)
sys.exit(1 if fail else 0)
