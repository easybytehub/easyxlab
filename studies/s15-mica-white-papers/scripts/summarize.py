#!/usr/bin/env python3
"""Write data/summary.json: every number of the study's claims.csv, at full precision, from the published data/.

Offline, standard library only. Reads data/rows.csv, data/documents.csv and data/metrics.json (for the two
collection dates only). Uses the definitions of scripts/06_analyse.py and scripts/check_headline.py:
"available" = outcome ixbrl-esma; "valid" = the row's file validates with zero errors; cohort = eligible rows
(placeholders excluded) whose wp_lastupdate is on or after 2025-12-23; "older" = the other eligible rows.

`dates` and `constants` hold the three facts that do not come from the register or the files: the date of
application of Implementing Regulation (EU) 2024/2984 (Art. 4), the publication date of ESMA's taxonomy package
(ESMA's taxonomy page and reporting manual, data/sources.csv) and the number of MiCA Q&As read in ESMA's Q&A tool.

    python3 scripts/summarize.py
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CUTOFF = dt.date(2025, 12, 23)
BITSTAMP = "549300XIBGTJ0PLIEO72"
NOT_RETRIEVABLE = ("anti-bot", "robots", "http-error", "net-error")
WITHIN_ONE_HOP = ("direct", "hop", "client-redirect+direct", "client-redirect+hop", "")
MICA_QAS = 51  # MiCA Q&As in ESMA's Q&A tool, read for paper.md §3 (one unanswered)


def pdate(s: str) -> dt.date | None:
    s = (s or "").strip()
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
    if m:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    return dt.date(*map(int, m.groups())) if m else None


def long_date(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def wilson_pct(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (c - h), 100 * (c + h)


def main() -> None:
    rows = list(csv.DictReader(open(DATA / "rows.csv", encoding="utf-8")))
    docs = {d["sha256"]: d for d in csv.DictReader(open(DATA / "documents.csv", encoding="utf-8"))}
    metrics = json.loads((DATA / "metrics.json").read_text(encoding="utf-8"))

    elig = [r for r in rows if r["excluded_placeholder"] == "0"]
    coh = [r for r in elig if r["cohort"] == "1"]
    older = [r for r in elig if r["cohort"] == "0"]
    for r in elig:  # the cohort flag is the date rule, nothing else
        d = pdate(r["wp_lastupdate"])
        assert (r["cohort"] == "1") == bool(d and d >= CUTOFF), (r["register"], r["csv_line"])

    n = len(coh)
    oc = Counter(r["outcome"] for r in coh)
    av = [r for r in coh if r["outcome"] == "ixbrl-esma"]
    va = [r for r in av if r["valid"] == "1"]
    inv = [r for r in av if r["valid"] != "1"]
    av_files = {r["doc_sha256"] for r in av}
    kinds = Counter()
    for r in inv:
        fam = set(json.loads(docs[r["doc_sha256"]]["error_families"] or "{}"))
        kinds["assertion_only" if fam == {"assertion"} else "xbrl"] += 1
    frozen = sum(1 for r in coh if r["outcome_frozen_rule"] == "ixbrl-esma")
    ck = [r for r in av if r["ids_checked"] == "1"]
    top_domain, top_rows = Counter(r["producer_domain"] for r in va).most_common(1)[0]
    top_av = [r for r in av if r["producer_domain"] == top_domain]
    # closing review 2026-10-05: who the register names on the top producer's rows (GLEIF name from entities.csv)
    gleif_name = {e["lei"]: e["gleif_legal_name"] for e in csv.DictReader(open(DATA / "entities.csv", encoding="utf-8"))}
    top_leis = sorted({r["lei"] for r in top_av if r["lei"]})
    top_lei_name = gleif_name.get(top_leis[0], "") if len(top_leis) == 1 else ""
    casp = Counter(r["outcome"] for r in coh if r["lei_casp"] == BITSTAMP)
    lo, hi = wilson_pct(len(av), n)
    flo, fhi = wilson_pct(frozen, n)

    summary = {
        "_about": "S15 figures from data/rows.csv and data/documents.csv (scripts/summarize.py); full precision",
        "dates": {
            "cutoff": long_date(CUTOFF.isoformat()),
            "taxonomy_published": "5 August 2025",
            "register_last_update": long_date(metrics["register_last_update"]),
            "collection": metrics["collection_date"],
        },
        "constants": {"mica_qas": MICA_QAS},
        "register_rows": {
            "OTHER": sum(1 for r in rows if r["register"] == "OTHER"),
            "EMTWP": sum(1 for r in rows if r["register"] == "EMTWP"),
            "excluded_placeholders": len(rows) - len(elig),
            "eligible": len(elig),
        },
        "cohort": {
            "rows": n,
            "outcomes": {k.replace("-", "_").replace(".", "_"): v for k, v in oc.most_common()},
            "available": len(av),
            "available_share": len(av) / n,
            "available_ci95_lo_pct": lo,
            "available_ci95_hi_pct": hi,
            "available_distinct_files": len(av_files),
            "available_files_validated": sum(1 for h in av_files if h in docs and docs[h]["valid"] in ("0", "1")),
            "not_retrievable": sum(oc[k] for k in NOT_RETRIEVABLE),
            "rows_beyond_one_hop": sum(1 for r in coh if r["via"] not in WITHIN_ONE_HOP),
            "valid": len(va),
            "valid_distinct_files": len({r["doc_sha256"] for r in va}),
            "invalid": len(inv),
            "invalid_assertion_only": kinds["assertion_only"],
            "invalid_xbrl": kinds["xbrl"],
            "frozen_available": frozen,
            "frozen_share": frozen / n,
            "frozen_ci95_lo_pct": flo,
            "frozen_ci95_hi_pct": fhi,
            "lei_checkable": sum(1 for r in ck if r["lei"]),
            "lei_match": sum(1 for r in ck if r["lei"] and r["lei_match"] == "1"),
            "dti_checkable": sum(1 for r in ck if r["register_dti"]),
            "dti_match": sum(1 for r in ck if r["register_dti"] and r["dti_match"] == "1"),
            "top_producer": {
                "domain": top_domain,
                "valid_rows": top_rows,
                "available_rows": len(top_av),
                "register_lei_is_tagged_offeror": sum(1 for r in top_av if r["lei"] and r["lei"] == r["doc_offeror_lei"]),
                "register_leis": len(top_leis),
                "register_lei_name": top_lei_name,
                # 1 if the GLEIF legal name, letters only, contains the domain's first label, letters only
                "register_lei_name_matches_domain": int(bool(top_lei_name) and re.sub(r"[^a-z]", "", top_domain.split(".")[0])
                                                        in re.sub(r"[^a-z]", "", top_lei_name.lower())),
            },
            "casp_bitstamp": {"anti_bot": casp["anti-bot"], "xhtml_no_ixbrl": casp["xhtml-no-ixbrl"]},
        },
        "older": {
            "rows": len(older),
            "available": sum(1 for r in older if r["outcome"] == "ixbrl-esma"),
            # closing review 2026-10-05: «older» includes rows with no wp_lastupdate, which are not known to be older
            "undated": sum(1 for r in older if pdate(r["wp_lastupdate"]) is None),
            "dated_before_cutoff": sum(1 for r in older if pdate(r["wp_lastupdate"]) is not None),
            "undated_available": sum(1 for r in older if pdate(r["wp_lastupdate"]) is None and r["outcome"] == "ixbrl-esma"),
        },
    }
    (DATA / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"data/summary.json: {n} cohort rows, {len(av)} available, {len(va)} valid")


if __name__ == "__main__":
    main()
