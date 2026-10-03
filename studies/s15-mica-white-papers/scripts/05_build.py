"""Build the publishable per-row and per-document tables from the raw collection (work/) and the register (data/raw/).
Needs the raw inputs; run once after 02-04. Outputs (published):
  data/rows.csv        one line per register row (cohort and context), no personal data
  data/documents.csv   one line per distinct ESMA-format iXBRL file reached
  data/sources.csv     pinned inputs (URL, sha256, date)
  data/cohort_check.json  Wayback cross-check of the cohort rule
The figures are then computed offline from these files by 06_analyse.py."""
from __future__ import annotations

import csv
import hashlib
import importlib
import json
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
collect = importlib.import_module("02_collect")
from mica_wp_check import lei_checksum_ok  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/sources"
WORK = ROOT / "work"
DATA = ROOT / "data"
ORDER = ["ixbrl-esma", "ixbrl-esma-unattributed", "ixbrl-1.0", "ixbrl-other", "xhtml-no-ixbrl", "pdf", "zip-other", "html", "other", "empty",
         "anti-bot", "robots", "http-error", "net-error"]
# Generic hosting services: the registrable domain names the platform, not the producer of the file.
HOSTING_PLATFORMS = {"googleapis.com", "github.io", "r2.dev", "amazonaws.com", "website-files.com", "gitbook.io",
                     "digitaloceanspaces.com", "framerusercontent.com", "hubspotusercontent-na1.net", "windows.net"}
SECOND_LEVEL = {"org.ht", "co.uk", "com.au", "co.jp", "com.mt", "com.cy", "co.at", "com.br", "co.za", "org.uk"}


def regdomain(host: str) -> str:
    h = (host or "").lower().split(":")[0]
    parts = h.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def nu(u: str) -> str:
    u = (u or "").strip().lower()
    for p in ("https://", "http://"):
        if u.startswith(p):
            u = u[len(p):]
    if u.startswith("www."):
        u = u[4:]
    return u.rstrip("/")


def key(r):
    return (r.get("ae_lei", "").strip().upper(), r.get("ae_lei_casp", "").strip().upper(), nu(r.get("wp_url")))


def codes(s: str) -> set[str]:
    return {c.strip().upper() for c in re.split(r"[|,;\s]+", s or "") if c.strip()}


NS = {}          # sha256 -> namespace re-check (D10), filled in main()
DISALLOWED = set()  # result URLs disallowed under the RFC 9309 re-check (D8), filled in main()


def effective(res):
    """Outcome of one fetched result after the review corrections D8 (robots) and D10 (Inline XBRL version)."""
    oc = res.get("outcome")
    if res.get("url") in DISALLOWED or (res.get("final_url") or "") in DISALLOWED:
        return "robots"
    if oc == "robots" and (res.get("reason") or "").endswith(":error"):
        return "net-error"  # robots.txt unreachable (5xx/network): the host could not be read at all (D2)
    if oc in ("ixbrl-esma", "ixbrl-other"):
        ver = (res.get("doc") or {}).get("ix_version") or (NS.get(res.get("sha256")) or {}).get("ix_version")
        if ver == "1.0":
            return "ixbrl-1.0"
    return oc


def resolve(r, urls, val, reg_leis, rec_codes, frozen=False):
    """Row outcome = best document reached from the registered URL(s), directly or in one hop (METHOD.md §5).
    frozen=True recomputes it with the records collected under the frozen robots rule (before deviation D1)."""
    best, best_doc, via = None, None, ""
    hops_blocked = Counter()
    if not r["_urls"]:
        return "invalid-url", None, "", hops_blocked
    for u in r["_urls"]:
        d = urls.get(u)
        if not d:
            continue
        if frozen:
            d = {**d, **d["pre_review"]} if "pre_review" in d else d   # before following client redirects (D9)
            d = {**d, **d["frozen"]} if "frozen" in d else d           # before D1 (robots 4xx)
        cands = [("direct", d["main"])] + [("hop", h) for h in d.get("hops", [])]
        esma_hops = [h for h in d.get("hops", []) if effective(h) == "ixbrl-esma"]
        for how, res in cands:
            oc = effective(res)
            if oc == "ixbrl-esma" and how == "hop" and len(esma_hops) > 1:
                ids = (val.get(res.get("sha256"), {}) or {}).get("identifiers") or {}
                if not (set(ids.get("leis", [])) & reg_leis or set(ids.get("dtis", [])) & rec_codes):
                    oc = "ixbrl-esma-unattributed"
            if oc not in ORDER:
                oc = "net-error"
            if best is None or ORDER.index(oc) < ORDER.index(best):
                best, best_doc, via = oc, res, how
        for h in d.get("hops", []):
            if effective(h) in ("robots", "anti-bot", "http-error", "net-error"):
                hops_blocked[effective(h)] += 1
        if not frozen and d.get("client_redirects"):
            via = "client-redirect+" + via if via and not via.startswith("client-redirect") else via
    return best or "not-collected", best_doc, via, hops_blocked


def is_valid(v: dict) -> bool:
    """Zero ERROR-level messages with the ESMA assertions evaluated (METHOD.md §5, D4)."""
    vv = v.get("validation") or {}
    return vv.get("errors") == 0 and (vv.get("assertions_evaluated") or 0) > 0


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    rows = collect.load_rows()
    urls = {}
    for line in (WORK / "collect/urls.jsonl").open():
        d = json.loads(line)
        urls[d["url"]] = d
    val = {p.stem: json.loads(p.read_text()) for p in (WORK / "validate").glob("*.json")}
    gleif = json.loads((WORK / "gleif.json").read_text()) if (WORK / "gleif.json").exists() else {}
    if (WORK / "namespaces.json").exists():
        NS.update(json.loads((WORK / "namespaces.json").read_text()))
    if (WORK / "review_recheck.json").exists():
        st = json.loads((WORK / "review_recheck.json").read_text())
        DISALLOWED.update((st.get("A") or {}).get("disallowed", []))
        DISALLOWED.update(c["url"] for c in (st.get("A") or {}).get("results_changed", []))

    # ---- Wayback cross-check (Title II) ----
    with open(RAW / "wayback/20251223101326_OTHER.csv", encoding="utf-8-sig", newline="") as f:
        snap = [{k: (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(f)]
    smap = {}
    for r in snap:
        smap.setdefault(key(r), r)
    snap_pairs = Counter((r.get("ae_lei", "").upper(), r.get("ae_lei_casp", "").upper()) for r in snap)
    cur_keys = {key(r) for r in rows if r["_register"] == "OTHER"}
    vanished_pairs = Counter((k[0], k[1]) for k in smap if k not in cur_keys)

    out_rows, docs = [], {}
    for r in rows:
        has_wp = bool(r["_urls"]) or (r["_register"] == "OTHER")
        placeholder = r["_register"] == "EMTWP" and r.get("wp_url", "").strip().upper() in ("EMT_NO_WP", "EMT_CRIN", "")
        label = ""
        if r["_register"] == "OTHER":
            k = key(r)
            if k in smap:
                label = "changed" if smap[k].get("wp_lastupdate") != r.get("wp_lastupdate") else "unchanged"
            else:
                label = "new"
                if not r["_cohort"]:
                    label = "rekeyed" if vanished_pairs[(k[0], k[1])] else "new-before-cutoff"
        rec_codes = codes(r.get("ae_DTI")) | codes(r.get("ae_DTI_FFG"))
        reg_leis = {x for x in (r.get("ae_lei", "").upper(), r.get("ae_lei_casp", "").upper()) if x}
        best, best_doc, via, hops_blocked = resolve(r, urls, val, reg_leis, rec_codes, frozen=False)
        best_frozen = resolve(r, urls, val, reg_leis, rec_codes, frozen=True)[0]
        rec = {
            "register": r["_register"], "csv_line": r["_row"], "cohort": int(r["_cohort"]), "wayback_label": label,
            "excluded_placeholder": int(placeholder), "home_ms": r.get("ae_homeMemberState", ""),
            "wp_lastupdate": r.get("wp_lastupdate", ""), "wp_lastupdate_iso": r.get("_date", ""),
            "wp_url": r.get("wp_url", "").replace("\n", " ").replace("\r", " "),
            "lei": r.get("ae_lei", "").upper() if lei_checksum_ok(r.get("ae_lei", "")) else "",
            "lei_casp": r.get("ae_lei_casp", "").upper() if lei_checksum_ok(r.get("ae_lei_casp", "")) else "",
            "casp_named": int(bool(r.get("ae_lei_casp") or r.get("ae_lei_name_casp"))),
            "register_dti": "|".join(sorted(codes(r.get("ae_DTI")))), "register_dti_ffg": "|".join(sorted(codes(r.get("ae_DTI_FFG")))),
            "url_host": urllib.parse.urlsplit(r["_urls"][0]).netloc.lower() if r["_urls"] else "",
            "n_urls": len(r["_urls"]),
            "url_id": hashlib.sha256(r["_urls"][0].encode()).hexdigest()[:12] if r["_urls"] else "",
            "outcome": best, "via": via, "outcome_frozen_rule": best_frozen,
            "doc_sha256": (best_doc or {}).get("sha256") or "",
            "doc_host": urllib.parse.urlsplit((best_doc or {}).get("final_url") or "").netloc.lower() if best_doc else "",
            # download tokens in signed storage links (e.g. GitBook/Firebase "token=") are redacted
            "doc_url": re.sub(r"(?i)(token=)[^&#]+", r"\1REDACTED", ((best_doc or {}).get("final_url") or (best_doc or {}).get("url") or "")) if best not in ("robots",) else "",
            "ix_version": ((best_doc or {}).get("doc") or {}).get("ix_version") or (NS.get((best_doc or {}).get("sha256")) or {}).get("ix_version") or "",
            "ix_version_rechecked": int(bool(NS.get((best_doc or {}).get("sha256"), {}).get("ix_version") or ((best_doc or {}).get("doc") or {}).get("ix_version"))) if best in ("ixbrl-esma", "ixbrl-1.0", "ixbrl-other") else "",
            "robots_reason": (best_doc or {}).get("reason") or "",
            "hops_not_retrieved": "|".join(f"{k}:{v}" for k, v in sorted(hops_blocked.items())),
        }
        rec["producer_domain"] = regdomain(rec["doc_host"]) if best in ("ixbrl-esma", "ixbrl-1.0", "ixbrl-other") else ""
        rec["producer_is_hosting_platform"] = int(rec["producer_domain"] in HOSTING_PLATFORMS) if rec["producer_domain"] else ""
        if best == "robots":
            rec["doc_sha256"] = ""
        v = val.get(rec["doc_sha256"]) if best == "ixbrl-esma" else None
        if v:
            ids = v.get("identifiers") or {}
            vv = v.get("validation") or {}
            rec["valid"] = int(is_valid(v))
            # identifiers could not be read (D4 re-download failed): matches are "not checked", not mismatches
            checked = bool(ids.get("leis") or ids.get("dtis") or vv.get("fact_count"))
            rec["ids_checked"] = int(checked)
            rec["lei_match"] = (int(rec["lei"] in set(ids.get("leis", []))) if rec["lei"] else "") if checked else ""
            rec["dti_match"] = (int(bool(codes(r.get("ae_DTI")) & set(ids.get("dtis", [])))) if codes(r.get("ae_DTI")) else "") if checked else ""
            rec["ffg_match"] = (int(bool(codes(r.get("ae_DTI_FFG")) & set(ids.get("dtis", [])))) if codes(r.get("ae_DTI_FFG")) else "") if checked else ""
            nd = [x for k_, xs in (ids.get("dates") or {}).items() if k_.startswith("DateOfNotification") for x in xs]
            rec["doc_notification_date"] = min(nd) if nd else ""
            offl = [x for x in (vv.get("lei_facts") or {}).get("OfferorsLegalEntityIdentifier", []) if x]
            rec["doc_offeror_lei"] = offl[0] if offl else ""
            docs.setdefault(rec["doc_sha256"], (v, rec["doc_host"]))
        else:
            rec.update({"valid": "", "ids_checked": "", "lei_match": "", "dti_match": "", "ffg_match": "", "doc_notification_date": "", "doc_offeror_lei": ""})
        g = gleif.get(rec["lei"]) if rec["lei"] else None
        rec["gleif_register_lei"] = ("not-found" if g and not g["found"] else
                                     f"{g['registration_status']}/{g['entity_status']}" if g else "")
        g2 = gleif.get(rec["doc_offeror_lei"]) if rec["doc_offeror_lei"] else None
        rec["gleif_doc_offeror_lei"] = ("not-found" if g2 and not g2["found"] else
                                        f"{g2['registration_status']}/{g2['entity_status']}" if g2 else "")
        rec["register_lei_malformed"] = int(bool(r.get("ae_lei")) and not lei_checksum_ok(r.get("ae_lei", "")))
        out_rows.append(rec)

    fields = list(out_rows[0].keys())
    with open(DATA / "rows.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)

    with open(DATA / "documents.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["sha256", "size", "producer_domain", "esma_table", "single_xhtml", "facts", "valid", "errors",
                    "warnings", "assertions_evaluated", "assertions_failed", "assertions_failed_error_severity", "error_families",
                    "identifiers_source", "ix_version", "seconds"])
        for s, (v, host) in sorted(docs.items()):
            vv = v.get("validation") or {}
            doc = v.get("doc") or {}
            w.writerow([s, v.get("size"), regdomain(host), doc.get("esma_table"),
                        int(bool(doc.get("is_xml_wellformed") and doc.get("root") == "{http://www.w3.org/1999/xhtml}html")),
                        vv.get("fact_count"), int(is_valid(v)), vv.get("errors"), vv.get("warnings"),
                        vv.get("assertions_evaluated"), "|".join(vv.get("assertions_failed") or []),
                        "|".join(sorted(k[len("message:"):] for k in (vv.get("error_codes") or {}) if k.startswith("message:"))),
                        json.dumps(vv.get("error_families") or {}, sort_keys=True),
                        ("same-file" if not v.get("refetch") else "refetch-same-hash" if v["refetch"].get("same_hash")
                         else "refetch-changed" if v["refetch"].get("status") == 200 else "none"),
                        (v.get("doc") or {}).get("ix_version") or (NS.get(s) or {}).get("ix_version") or "",
                        v.get("seconds")])

    # Legal entities (GLEIF legal names) for the LEIs used in rows.csv: lets results be read per legal entity.
    used = sorted({x for r in out_rows for x in (r["lei"], r["lei_casp"], r["doc_offeror_lei"]) if x})
    with open(DATA / "entities.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["lei", "gleif_found", "gleif_legal_name", "gleif_country", "gleif_registration_status", "gleif_entity_status"])
        for l in used:
            g = gleif.get(l) or {}
            w.writerow([l, int(bool(g.get("found"))), g.get("legal_name", ""), g.get("country", ""),
                        g.get("registration_status", ""), g.get("entity_status", "")])

    # Wayback cross-check summary
    cohort_other = [x for x in out_rows if x["register"] == "OTHER" and x["cohort"]]
    other_all = [x for x in out_rows if x["register"] == "OTHER"]
    with open(RAW / "OTHER.csv", encoding="utf-8-sig", newline="") as f:
        raw_other = list(csv.DictReader(f))
    header_rows = [i + 2 for i, x in enumerate(raw_other) if collect.is_header_row({k: (v or "") for k, v in x.items() if k})]
    absent_nc = [x for x in other_all if not x["cohort"] and x["wayback_label"] in ("rekeyed", "new-before-cutoff")]
    chk = {
        "snapshot": "web.archive.org 20251223101326 OTHER.csv", "snapshot_rows": len(snap),
        "snapshot_max_wp_lastupdate": max((collect.parse_date(r.get("wp_lastupdate", "")) for r in snap if collect.parse_date(r.get("wp_lastupdate", ""))), default=None),
        "date_formats_in_register": dict(Counter(("dd/mm/yyyy" if "/" in x["wp_lastupdate"] else "dd.mm.yyyy" if "." in x["wp_lastupdate"]
                                                  else "empty" if not x["wp_lastupdate"] else "other") for x in out_rows)),
        "header_rows_inside_other_csv_dropped": header_rows,
        "current_rows_other": len(other_all),
        "cohort_other_rows": len(cohort_other),
        "cohort_other_by_label": dict(Counter(x["wayback_label"] for x in cohort_other)),
        "noncohort_absent_from_snapshot": {"earlier_date": sum(1 for x in absent_nc if x["wp_lastupdate_iso"]),
                                           "no_date": sum(1 for x in absent_nc if not x["wp_lastupdate_iso"])},
        "undated_rows": [(x["register"], x["csv_line"]) for x in out_rows if not x["wp_lastupdate_iso"]],
        "dated_after_register_update": [(x["register"], x["csv_line"], x["wp_lastupdate"]) for x in out_rows if x["wp_lastupdate_iso"] > "2026-09-30"],
        "snapshot_rows_gone": sum(1 for k in smap if k not in cur_keys),
    }
    (DATA / "cohort_check.json").write_text(json.dumps(chk, indent=1, default=str))

    srcs = [("ESMA interim MiCA register, OTHER.csv", "https://www.esma.europa.eu/sites/default/files/2024-12/OTHER.csv", RAW / "OTHER.csv"),
            ("ESMA interim MiCA register, EMTWP.csv", "https://www.esma.europa.eu/sites/default/files/2024-12/EMTWP.csv", RAW / "EMTWP.csv"),
            ("ESMA interim MiCA register, ARTZZ.csv", "https://www.esma.europa.eu/sites/default/files/2024-12/ARTZZ.csv", RAW / "ARTZZ.csv"),
            ("ESMA register field descriptions", "https://www.esma.europa.eu/sites/default/files/2024-12/Description_of_the_fields_in_the_interim_MiCA_register.csv", RAW / "Description_of_the_fields_in_the_interim_MiCA_register.csv"),
            ("Wayback capture of OTHER.csv, 2025-12-23", "https://web.archive.org/web/20251223101326id_/https://www.esma.europa.eu/sites/default/files/2024-12/OTHER.csv", RAW / "wayback/20251223101326_OTHER.csv"),
            ("ESMA MiCA taxonomy 2025", "https://www.esma.europa.eu/sites/default/files/2025-08/mica_taxonomy_2025.zip", ROOT / "data/raw/taxonomy/mica_taxonomy_2025.zip"),
            ("ESMA MiCA taxonomy formulas (xlsx)", "https://www.esma.europa.eu/sites/default/files/2025-08/mica_taxonomy_formulas_202507.xlsx", ROOT / "data/raw/taxonomy/mica_taxonomy_formulas_202507.xlsx"),
            ("ESMA statement ESMA75-1303207761-6284 (28-11-2025)", "https://www.esma.europa.eu/sites/default/files/2025-11/ESMA75-1303207761-6284_Statement_to_support_the_smooth_implementation_of_MiCA_standards_and_format.pdf", RAW / "statement_2025-11.pdf"),
            ("ESMA MiCA white paper reporting manual v1.0", "https://www.esma.europa.eu/sites/default/files/2025-08/mica_taxonomy_reporting_manual_v1.0.pdf", RAW / "reporting_manual_v1.0.pdf"),
            ("MiCA consolidated text (CELEX 02023R1114-20240109)", "https://publications.europa.eu/resource/celex/02023R1114-20240109", RAW / "legal/02023R1114-20240109.txt"),
            ("Implementing Regulation (EU) 2024/2984 (CELEX 32024R2984)", "https://publications.europa.eu/resource/celex/32024R2984", RAW / "legal/32024R2984.txt"),
            ("ESMA Q&A 2845", "https://www.esma.europa.eu/publications-data/questions-answers/2845", RAW / "qa/2845.txt")]
    with open(DATA / "sources.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["source", "url", "retrieved", "sha256_of_local_copy"])
        for name, url, p in srcs:
            w.writerow([name, url, "2026-10-03", sha(p) if p.exists() else ""])
    print("rows", len(out_rows), "documents", len(docs))


if __name__ == "__main__":
    main()
