"""Compute every figure from the published tables (offline): data/rows.csv, data/documents.csv, data/cohort_check.json.
Writes data/metrics.json and data/tables.md."""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
NOT_RETRIEVABLE = ("anti-bot", "robots", "http-error", "net-error")


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 1), round(100 * (c + h), 1))


def pct(k, n):
    return round(100 * k / n, 1) if n else None


def block(rows):
    n = len(rows)
    oc = Counter(r["outcome"] for r in rows)
    av = [r for r in rows if r["outcome"] == "ixbrl-esma"]
    va = [r for r in av if r["valid"] == "1"]
    out = {
        "rows": n, "distinct_urls": len({r["url_id"] for r in rows if r["url_id"]}),
        "outcomes": dict(oc.most_common()),
        "available": len(av), "available_pct": pct(len(av), n), "available_ci95": wilson(len(av), n),
        "available_direct": sum(1 for r in av if r["via"].endswith("direct")), "available_one_hop": sum(1 for r in av if r["via"].endswith("hop")),
        "valid_direct": sum(1 for r in va if r["via"].endswith("direct")), "valid_one_hop": sum(1 for r in va if r["via"].endswith("hop")),
        "available_distinct_files": len({r["doc_sha256"] for r in av}),
        "valid": len(va), "valid_pct_of_available": pct(len(va), len(av)), "valid_pct_of_rows": pct(len(va), n),
        "valid_distinct_files": len({r["doc_sha256"] for r in va}),
        "not_retrievable": sum(oc[k] for k in NOT_RETRIEVABLE),
        "available_frozen_rule": sum(1 for r in rows if r["outcome_frozen_rule"] == "ixbrl-esma"),
        "available_frozen_rule_pct": pct(sum(1 for r in rows if r["outcome_frozen_rule"] == "ixbrl-esma"), n),
        "available_frozen_rule_ci95": wilson(sum(1 for r in rows if r["outcome_frozen_rule"] == "ixbrl-esma"), n),
        "available_via_client_redirect": sum(1 for r in av if r["via"].startswith("client-redirect")),
        "ixbrl_1_0_rows": oc.get("ixbrl-1.0", 0),
        "ixbrl_1_0_distinct_files": len({r["doc_sha256"] for r in rows if r["outcome"] == "ixbrl-1.0"}),
        "ix_version_not_rechecked_available": sum(1 for r in av if r["ix_version_rechecked"] != "1"),
        "failed_assertions_error_severity_rows": dict(Counter(a for r in av if r["valid"] != "1"
                                                              for a in DOCS.get(r["doc_sha256"], {}).get("assertions_failed_error_severity", "").split("|") if a).most_common(10)),
        "outcomes_frozen_rule": dict(Counter(r["outcome_frozen_rule"] for r in rows).most_common()),
        "ids_not_checked": sum(1 for r in av if r["ids_checked"] != "1"),
        "lei_rows_with_register_lei": sum(1 for r in av if r["lei"] and r["ids_checked"] == "1"),
        "lei_match": sum(1 for r in av if r["lei_match"] == "1"),
        "dti_rows_with_register_dti": sum(1 for r in av if r["register_dti"] and r["ids_checked"] == "1"),
        "dti_match": sum(1 for r in av if r["dti_match"] == "1"),
        "ffg_rows_with_register_ffg": sum(1 for r in av if r["register_dti_ffg"] and r["ids_checked"] == "1"),
        "ffg_match": sum(1 for r in av if r["ffg_match"] == "1"),
        "gleif_register_lei_available": dict(Counter(r["gleif_register_lei"] or "no-lei" for r in av).most_common()),
        "gleif_doc_offeror_lei_available": dict(Counter(r["gleif_doc_offeror_lei"] or "none-tagged" for r in av).most_common()),
        "doc_notification_before_cutoff": sum(1 for r in av if r["doc_notification_date"] and r["doc_notification_date"] < "2025-12-23"),
        "register_without_lei": sum(1 for r in av if not r["lei"]),
        "doc_notification_tagged": sum(1 for r in av if r["doc_notification_date"]),
        "producer_rows_available": dict(Counter(r["producer_domain"] for r in av).most_common()),
        "producer_rows_valid": dict(Counter(r["producer_domain"] for r in va).most_common()),
        "xhtml_no_ixbrl_hosts": dict(Counter(r["doc_host"] for r in rows if r["outcome"] == "xhtml-no-ixbrl").most_common()),
        "by_home_ms": {ms: {"rows": c, "available": sum(1 for r in av if r["home_ms"] == ms)}
                       for ms, c in Counter(r["home_ms"] for r in rows).most_common()},
        "html_with_blocked_document_link": sum(1 for r in rows if r["outcome"] == "html" and r["hops_not_retrieved"]),
    }
    def month(r):
        return r["wp_lastupdate_iso"][:7] if r["wp_lastupdate_iso"] else "?"
    out["by_quarter"] = {}
    for r in rows:
        mo = month(r)
        q = mo[:4] + "-Q" + str((int(mo[5:7]) - 1) // 3 + 1) if mo != "?" else "?"
        b = out["by_quarter"].setdefault(q, {"rows": 0, "available": 0, "valid": 0})
        b["rows"] += 1
        b["available"] += r["outcome"] == "ixbrl-esma"
        b["valid"] += r["outcome"] == "ixbrl-esma" and r["valid"] == "1"
    out["by_quarter"] = dict(sorted(out["by_quarter"].items()))
    inv = [r for r in av if r["valid"] != "1"]
    fam = Counter()
    for r in inv:
        f = DOCS.get(r["doc_sha256"], {}).get("error_families", "{}")
        ks = set(json.loads(f or "{}"))
        fam["assertion-only" if ks == {"assertion"} else "xbrl-or-ixbrl-errors" if ks else "no-error-but-no-assertions"] += 1
    out["invalid_rows_by_kind"] = dict(fam)
    casp = Counter(r["lei_casp"] for r in rows if r["lei_casp"])
    out["by_casp"] = {l: {"rows": n, "available": sum(1 for r in av if r["lei_casp"] == l),
                          "valid": sum(1 for r in va if r["lei_casp"] == l),
                          "outcomes": dict(Counter(r["outcome"] for r in rows if r["lei_casp"] == l).most_common(3))}
                      for l, n in casp.most_common() if n >= 3}
    if va:
        top, k = Counter(r["producer_domain"] for r in va).most_common(1)[0]
        out["top_producer_available"] = {"domain": top, "rows": sum(1 for r in av if r["producer_domain"] == top),
                                         "distinct_files": len({r["doc_sha256"] for r in av if r["producer_domain"] == top}),
                                         "valid_rows": k, "valid_distinct_files": len({r["doc_sha256"] for r in va if r["producer_domain"] == top}),
                                         "register_lei_most_common": Counter(r["lei"] for r in av if r["producer_domain"] == top).most_common(1)[0],
                                         "rows_register_lei_equals_tagged_offeror_lei": sum(1 for r in av if r["producer_domain"] == top and r["lei"] and r["lei"] == r["doc_offeror_lei"])}
        rest = [r for r in av if r["producer_domain"] != top]
        out["other_producers"] = {"rows": len(rest), "valid_rows": sum(1 for r in rest if r["valid"] == "1"),
                                  "domains": len({r["producer_domain"] for r in rest}),
                                  "hosting_platform_rows": sum(1 for r in rest if r["producer_is_hosting_platform"] == "1")}
        out["top_producer_valid"] = {"domain": top, "rows": k, "pct": pct(k, len(va))}
    return out


DOCS = {}


def main():
    rows = list(csv.DictReader(open(DATA / "rows.csv", encoding="utf-8")))
    docs = list(csv.DictReader(open(DATA / "documents.csv", encoding="utf-8")))
    DOCS.update({d["sha256"]: d for d in docs})
    chk = json.loads((DATA / "cohort_check.json").read_text())
    elig = [r for r in rows if r["excluded_placeholder"] == "0"]
    cohort = [r for r in elig if r["cohort"] == "1"]
    context = [r for r in elig if r["cohort"] == "0"]
    m = {
        "collection_date": "2026-10-03", "register_last_update": "2026-09-30",
        "register_rows": {"OTHER": sum(1 for r in rows if r["register"] == "OTHER"), "EMTWP": sum(1 for r in rows if r["register"] == "EMTWP"),
                          "excluded_placeholders": sum(1 for r in rows if r["excluded_placeholder"] == "1")},
        "cohort_rule": "wp_lastupdate >= 23/12/2025",
        "cohort": block(cohort),
        "cohort_by_register": {reg: len([r for r in cohort if r["register"] == reg]) for reg in ("OTHER", "EMTWP")},
        "cohort_title_ii_by_wayback_label": chk["cohort_other_by_label"],
        "cohort_new_only": block([r for r in cohort if r["wayback_label"] == "new"]),
        "context_all_other_rows": block(context),
        "whole_register": block(elig),
        "documents": {
            "distinct_files_validated": len(docs),
            "valid": sum(1 for d in docs if d["valid"] == "1"),
            "single_xhtml": sum(1 for d in docs if d["single_xhtml"] == "1"),
            "failed_assertions": dict(Counter(a for d in docs for a in d["assertions_failed"].split("|") if a).most_common(20)),
            "files_with_failed_assertions": sum(1 for d in docs if d["assertions_failed"]),
            "esma_table": dict(Counter(d["esma_table"] for d in docs)),
            "median_size_kb": sorted(int(d["size"]) for d in docs)[len(docs) // 2] // 1024 if docs else None,
        },
        "cohort_check": chk,
    }
    # every "X of N" pair the paper may cite, derived from the data (check_headline.py rejects any other pair)
    pairs = set()
    for b in (m["cohort"], m["cohort_new_only"], m["context_all_other_rows"], m["whole_register"]):
        pairs |= {(b["available"], b["rows"]), (b["valid"], b["available"]), (b["available_frozen_rule"], b["rows"]),
                  (b["valid_direct"], b["available_direct"]), (b["valid_one_hop"], b["available_one_hop"]),
                  (b["not_retrievable"], b["rows"]), (b["lei_match"], b["lei_rows_with_register_lei"]),
                  (b["dti_match"], b["dti_rows_with_register_dti"]), (b["ffg_match"], b["ffg_rows_with_register_ffg"]),
                  (b["valid_distinct_files"], b["available_distinct_files"]), (b["ixbrl_1_0_rows"], b["rows"])}
        pairs |= {(v["available"], v["rows"]) for v in b["by_quarter"].values()} | {(v["valid"], v["available"]) for v in b["by_quarter"].values()}
        pairs |= {(v["available"], v["rows"]) for v in b["by_home_ms"].values()}
        pairs |= {(v["available"], v["rows"]) for v in b["by_casp"].values()} | {(v["valid"], v["available"]) for v in b["by_casp"].values()}
        if b.get("top_producer_available"):
            t = b["top_producer_available"]
            pairs |= {(t["valid_rows"], b["valid"]), (t["valid_rows"], t["rows"]), (t["valid_distinct_files"], b["valid_distinct_files"]),
                      (t["rows_register_lei_equals_tagged_offeror_lei"], t["rows"]),
                      (b["other_producers"]["valid_rows"], b["other_producers"]["rows"])}
    emt = [r for r in cohort if r["register"] == "EMTWP"]
    pairs.add((sum(1 for r in emt if r["outcome"] == "ixbrl-esma"), len(emt)))
    d = m["documents"]
    pairs |= {(d["valid"], d["distinct_files_validated"]), (d["single_xhtml"], d["distinct_files_validated"])}
    m["paper_pairs"] = sorted(f"{a} of {b}" for a, b in pairs)
    (DATA / "metrics.json").write_text(json.dumps(m, indent=1, ensure_ascii=False))
    c = m["cohort"]
    lines = ["# S15 tables (generated by scripts/06_analyse.py)", "",
             f"Cohort: {c['rows']} register rows ({c['distinct_urls']} distinct URLs).", "",
             "| outcome | cohort rows | context rows |", "|---|---:|---:|"]
    ctx = m["context_all_other_rows"]["outcomes"]
    for k in sorted(set(c["outcomes"]) | set(ctx), key=lambda k: -c["outcomes"].get(k, 0)):
        lines.append(f"| {k} | {c['outcomes'].get(k, 0)} | {ctx.get(k, 0)} |")
    lines += ["", "| producing domain | available rows | valid rows |", "|---|---:|---:|"]
    for k, v in c["producer_rows_available"].items():
        lines.append(f"| {k} | {v} | {c['producer_rows_valid'].get(k, 0)} |")
    lines += ["", "| home Member State | cohort rows | available |", "|---|---:|---:|"]
    for k, v in c["by_home_ms"].items():
        lines.append(f"| {k} | {v['rows']} | {v['available']} |")
    (DATA / "tables.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: c[k] for k in ("rows", "available", "available_pct", "available_ci95", "valid", "lei_match", "dti_match")}))


if __name__ == "__main__":
    main()
