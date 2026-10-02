#!/usr/bin/env python3
"""Build data/records.jsonl.gz, the published per-entity scan records, from data/raw/.

Inputs (data/raw/, git-ignored): scan.jsonl and scan_sec_pass2.jsonl (first scan, scanner
version 1), robots_snapshot.jsonl and recheck_*.jsonl (re-checks of 2026-10-02, recheck.py).
For records of scanner version 2 (a new measurement) no robots audit is needed.

What it does to version-1 records:
  1. keeps one record per entity (the REL export listed two municipalities twice);
  2. robots audit (audit_robots.py): a request the robots.txt in force did not allow is
     discarded together with everything derived from it; if the home page itself was not
     allowed, the whole record except robots.txt-derived fields is discarded;
  3. replaces the robots.txt indicators with an RFC 9309 reading of the re-read robots.txt
     (the first scan used urllib.robotparser and ignored files served as text/html);
  4. merges the security.txt second pass (where allowed) and the re-checks;
  5. labels where each statement date comes from (date_method).

--purge-raw rewrites data/raw/scan.jsonl and scan_sec_pass2.jsonl without the discarded data,
deletes data/raw/scan_test.jsonl and removes from pilot/muni_res.json what the pilot fetched
against robots.txt. Running the build again afterwards gives the same records.

Published records keep no response body, no security.txt Contact value and no page title; in
the stored statement sentences e-mail addresses and phone numbers are masked.
"""
import argparse, csv, gzip, json, os, re, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan as S  # noqa: E402
import audit_robots as A  # noqa: E402
import robots9309 as R  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "records.jsonl.gz")
SCAN_DATE = date(2026, 10, 2)
RUN1, RUN2 = 586, 3299          # line counts at the two scanner restarts (private/scan*.log)
DERIVED = ("home_", "hsts", "https_", "acc_", "sectxt_", "stmt_", "llms_")
PILOT_TOKEN = "easybyte-lab-pilot"


COUNCIL_TITLE = re.compile(r"\b(ayuntamiento|ajuntament|concello|udala|ayto)\.?\s+(de\s+la\s+|de\s+los\s+|de\s+las\s+|del\s+|de\s+|d'|d\u2019)?([^|()\-\u2013:.,]+)", re.I)
MUNI_NAMES = set()


def other_council(title, name):
    """True if the page title names the council of ANOTHER municipality of the list
    ('Ayuntamiento de Alba de Tormes' on fresnedoso.es)."""
    own = S.name_runs(name)
    if S.name_in_text(S.norm(title), own):
        return False
    for m in COUNCIL_TITLE.finditer(title or ""):
        rest = re.sub(r"\s+", " ", S.norm(m.group(3))).strip()
        if rest in MUNI_NAMES:
            return True
    return False


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def mask(s):
    s = re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", "[e-mail]", s or "")
    return re.sub(r"(\+34[\s.-]?)?\b\d{3}[\s.-]?\d{2,3}[\s.-]?\d{2,3}[\s.-]?\d{0,3}\b",
                  lambda m: "[phone]" if len(re.sub(r"\D", "", m.group(0))) >= 9 else m.group(0), s)


def drop(rec, prefixes):
    for k in [k for k in rec if k.startswith(prefixes)]:
        del rec[k]


def load():
    lines = jl(os.path.join(RAW, "scan.jsonl"))
    main, order = {}, []
    for i, r in enumerate(lines):
        if r["entity_id"] in main:
            continue
        r.setdefault("scan_run", 1 if i < RUN1 else 2 if i < RUN2 else 3)
        main[r["entity_id"]] = r
        order.append(r["entity_id"])
    p2 = {r["entity_id"]: r for r in jl(os.path.join(RAW, "scan_sec_pass2.jsonl"))}
    snap = {d["host"]: d for d in jl(os.path.join(RAW, "robots_snapshot.jsonl"))}
    rh = {d["entity_id"]: d for d in jl(os.path.join(RAW, "recheck_home.jsonl"))}
    rs = {d["entity_id"]: d for d in jl(os.path.join(RAW, "recheck_statement.jsonl"))}
    rt = {d["host"]: d for d in jl(os.path.join(RAW, "recheck_sectxt.jsonl"))}
    return main, order, p2, snap, rh, rs, rt


def audit_and_discard(rec, p2rec, snap):
    """Apply the robots audit to one version-1 record (in place). Returns the pass-2 record
    that may still be used, or None."""
    a = rec.get("robots_audit")
    if a is None:
        a = A.audit(rec, p2rec, snap)
        if rec.get("home_status") == "robots_disallowed" and A.scan_time_state(rec) == "ok":
            s = snap.get(rec["host"])
            if s and s["state"] == "ok" and R.allowed(s["groups"], A.OLD_TOKEN, A.path_of(rec["url"])):
                a["home_not_fetched_but_allowed"] = True
        rec["robots_audit"] = a
    if a.get("home", "allowed") != "allowed":
        drop(rec, DERIVED)
        rec["home_status"] = "robots_discarded"
        return None
    for kind, pre in (("sectxt", "sectxt_"), ("stmt", "stmt_"), ("llms", "llms_")):
        if a.get(kind, "allowed") != "allowed":
            drop(rec, (pre,))
            rec[kind + "_status"] = "robots_discarded"
    if p2rec and a.get("sectxt_pass2", "allowed") != "allowed":
        return None
    return p2rec


def build_v1(rec, p2rec, snap, rh, rs, rt, name=""):
    p2rec = audit_and_discard(rec, p2rec, snap)
    # robots.txt indicators from the RFC 9309 reading of the re-read file
    rec["robots_status_scan"] = rec.pop("robots_status", None)
    rec["robots_error_scan"] = rec.pop("robots_error", None)
    for k in [k for k in rec if k.startswith(("ai_", "robots_valid", "robots_soft404", "robots_star"))]:
        del rec[k]
    s = snap.get(rec["host"])
    if s:
        f = S.robots_fields(s)
        f.pop("http_upgrades_to_https", None)       # keep the first scan's reading
        rec.update(f)
    else:
        rec["robots_state"] = None
    # security.txt: second pass where the home page was not fetched
    if p2rec and "sectxt_present" not in rec and "sectxt_status" in p2rec:
        rec.update({k: v for k, v in p2rec.items() if k.startswith("sectxt")})
        rec["sectxt_pass2"] = True
    if rec.get("sectxt_present") is not None and "sectxt_required_ok" not in rec:
        rec["sectxt_required_ok"] = rec.get("sectxt_valid")     # version-1 definition
        rec["sectxt_strict_ok"] = None
        rec["sectxt_source"] = "scan"
    t = rt.get(rec.get("sectxt_host") or rec["host"])
    if t and (rec.get("sectxt_present") or rec.get("sectxt_soft404")) and t.get("http_status") == 200 \
            and t.get("error") is None:
        drop(rec, ("sectxt_",))
        rec.update({k: v for k, v in t.items() if k.startswith("sectxt_")})
        rec["sectxt_status"] = 200
        rec["sectxt_host"] = t["host"]
        rec["sectxt_source"] = "recheck"
    # home-page re-check (identity markers; accessibility link without widget credits)
    h = rh.get(rec["entity_id"])
    if h:
        rec["rc_status"] = h.get("status") or h.get("error")
        for k in ("home_panel", "home_default_page", "home_parking", "home_council_word",
                  "name_match", "name_in_text", "name_in_url", "acc_link", "acc_url", "decompressed"):
            if k in h:
                rec["rc_" + k.replace("home_", "")] = h[k]
        if h.get("status") == 200:
            rec["rc_final_url"] = h.get("final_url")
            title = h.get("home_title") or ""
            rec["rc_title_present"] = bool(title.strip())
            rec["rc_name_in_title"] = S.name_in_text(S.norm(title), S.name_runs(name))
            # title-only markers with the final regular expressions (the title is not published)
            rec["rc_parking"] = bool(h.get("home_parking") or S.PARKING.search(title))
            rec["rc_panel"] = bool(h.get("home_panel") or S.PANEL.search(title))
            rec["rc_default_page"] = bool(h.get("home_default_page") or S.DEFAULT_PAGE.search(title)
                                          or S.PLACEHOLDER_TITLE.search(title))
            rec["rc_title_other_council"] = other_council(title, name)
            # shell test on visible text where the re-check measured it (second look), else
            # the first scan's measure (HTML without <script> under 3,000 characters)
            rec["rc_js_shell"] = h["text_len"] < 400 if "text_len" in h else h.get("js_shell")
        if h.get("decompressed") and h.get("status") == 200 and "acc_link" in h:
            # the first scan read this server's unrequested gzip body as binary
            rec.update(acc_link=h["acc_link"], acc_url=h["acc_url"], acc_source="recheck")
    if rec.get("acc_url") and S.ACC_VENDOR.search(A.host_of(rec["acc_url"])):
        rec["acc_vendor_link_v1"] = rec["acc_url"]
        drop(rec, ("stmt_",))
        if h and h.get("status") == 200 and "acc_link" in h:
            rec.update(acc_link=h["acc_link"], acc_url=h["acc_url"], acc_source="recheck")
        else:
            rec.update(acc_link=None, acc_url="", acc_source="unknown")
    # statement dates: where each one comes from
    if "stmt_has_date" in rec:
        rec["stmt_html"] = bool(rec.get("stmt_ok") and not rec.get("stmt_format"))
        if rec["scan_run"] == 1:
            rec["date_method"] = "v1_first_run"
        elif rec.get("stmt_extractor") == "v2":
            rec["date_method"] = "v2"
        elif not rec.get("stmt_has_date"):
            rec["date_method"] = "v1_nodate"       # v1 keywords were a superset of v2's
        elif S.statement_dates(rec.get("stmt_date_context") or "", SCAN_DATE):
            rec["date_method"] = "v1_ctx_ok"
        else:
            x = rs.get(rec["entity_id"])
            if x and x.get("stmt_status") == 200 and x.get("stmt_html"):
                drop(rec, ("stmt_",))
                rec.update({k: v for k, v in x.items() if k.startswith("stmt_")})
                rec["stmt_off_host"] = bool(x.get("stmt_off_host"))
                rec["date_method"] = "v2_recheck"
            else:
                rec["date_method"] = "v1_rejected_unchecked"
    if rec.get("stmt_date_context"):
        rec["stmt_date_context"] = mask(rec["stmt_date_context"])
    rec.pop("home_title", None)
    return rec


def build_v2(rec, name=""):
    """Scanner version 2 already honours robots.txt and records the page markers; map them onto
    the fields the site rules read (rc_* = what the re-checks give for version-1 records)."""
    if rec.get("home_status") == 200 and rec.get("home_html"):
        title = rec.get("home_title") or ""
        rec.update(rc_status=200, rc_final_url=rec.get("home_final"), rc_name_match=rec.get("home_name_match"),
                   rc_council_word=rec.get("home_council_word"), rc_js_shell=rec.get("home_js_shell"),
                   rc_panel=rec.get("home_panel"), rc_default_page=rec.get("home_default_page"),
                   rc_parking=rec.get("home_parking"), rc_title_present=bool(title.strip()),
                   rc_name_in_title=S.name_in_text(S.norm(title), S.name_runs(name)),
                   rc_title_other_council=other_council(title, name))
    if "stmt_has_date" in rec:
        rec["date_method"] = "v2"
    if rec.get("stmt_date_context"):
        rec["stmt_date_context"] = mask(rec["stmt_date_context"])
    rec.pop("home_title", None)
    rec["sectxt_source"] = "scan"
    return rec


def purge_raw(main, order, p2, snap):
    """Rewrite the raw scan files without the data obtained against robots.txt."""
    with open(os.path.join(RAW, "scan.jsonl.tmp"), "w", encoding="utf-8") as f:
        for eid in order:
            r = dict(main[eid])
            if r.get("scanner_version") != "2":
                audit_and_discard(r, p2.get(eid), snap)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(os.path.join(RAW, "scan.jsonl.tmp"), os.path.join(RAW, "scan.jsonl"))
    kept = []
    for eid, r in p2.items():
        a = main[eid].get("robots_audit") or A.audit(main[eid], r, snap)
        if a.get("sectxt_pass2", "allowed") != "allowed" or a.get("home", "allowed") != "allowed":
            r = {k: v for k, v in r.items() if not k.startswith("sectxt_") or k == "sectxt_host"}
            r["sectxt_status"] = "robots_discarded"
        kept.append(r)
    with open(os.path.join(RAW, "scan_sec_pass2.jsonl"), "w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    t = os.path.join(RAW, "scan_test.jsonl")
    if os.path.exists(t):
        os.remove(t)
    # pilot: drop what it fetched against robots.txt (it did not read robots.txt first)
    pr = os.path.join(ROOT, "pilot", "muni_res.json")
    if os.path.exists(pr):
        res, notes = json.load(open(pr)), []
        for x in res:
            s = snap.get(x["host"].lower())
            for field, path in (("home", "/"), ("sectxt", "/.well-known/security.txt"),
                                ("llms", "/llms.txt")):
                ok = s is not None and (s["state"] == "unavailable" or
                                        (s["state"] == "ok" and R.allowed(s["groups"], PILOT_TOKEN, path)))
                if not ok and x.get(field) is not None:
                    keys = {"home": ("home", "acc_link"), "sectxt": ("sectxt", "sec_expires", "sec_soft404"),
                            "llms": ("llms",)}[field]
                    for k in keys:
                        x[k] = None
                    x.setdefault("removed", []).append(field + (" (robots.txt disallows)" if s and s["state"] == "ok"
                                                                 else " (robots.txt not verifiable)"))
                    notes.append((x["host"], field))
        json.dump(res, open(pr, "w"))
        print(f"pilot: removed {notes}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--purge-raw", action="store_true")
    a = ap.parse_args()
    main_, order, p2, snap, rh, rs, rt = load()
    if not main_:
        sys.exit("no data/raw/scan.jsonl: nothing to build (data/records.jsonl.gz is the published input)")
    if a.purge_raw:
        purge_raw(main_, order, p2, snap)
        main_, order, p2, snap, rh, rs, rt = load()
    popl = list(csv.DictReader(open(os.path.join(ROOT, "data", "population.csv"), encoding="utf-8")))
    pop = {p["entity_id"]: p["name"] for p in popl}
    for p in popl:
        if p["entity_type"] == "municipality":
            MUNI_NAMES.update(re.sub(r"\s+", " ", t).strip() for t in S.name_tokens(p["name"]))
    n = 0
    with gzip.open(OUT, "wt", encoding="utf-8", compresslevel=9) as f:
        for eid in order:
            if eid not in pop:
                continue
            r = dict(main_[eid])
            r = build_v2(r, pop[eid]) if r.get("scanner_version") == "2" else build_v1(r, p2.get(eid), snap, rh, rs, rt, pop[eid])
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
            n += 1
    print(f"{n} records -> {os.path.relpath(OUT, ROOT)}", file=sys.stderr)
    write_meta(main_, snap, rh, rs, rt, popl)


def write_meta(main_, snap, rh, rs, rt, popl):
    """Counts about the robots.txt re-read and the re-checks, which live in data/raw/ and are
    therefore not in the published records: written to data/build_meta.json for the paper."""
    if not snap:
        return
    types = {p["entity_id"]: p["entity_type"] for p in popl}
    agree = total = 0
    for r in main_.values():
        if r.get("scanner_version") == "2" or not r.get("robots_valid"):
            continue
        s = snap.get(r["host"])
        if not s or s["state"] != "ok":
            continue
        f = S.robots_fields(s)
        total += 1
        agree += all(bool(r.get(f"ai_{t}_blocked")) == bool(f.get(f"ai_{t}_blocked"))
                     for t in ("gptbot", "claudebot", "google_extended", "ccbot"))
    mh = [d for d in rh.values() if types.get(d["entity_id"]) == "municipality"]
    meta = dict(
        robots_hosts_reread=len(snap),
        robots_reread_2xx_retried=sum(1 for d in snap.values() if isinstance(d.get("status"), int) and 200 < d["status"] < 300),
        robots_reread_failures_retried=sum(1 for d in snap.values() if d.get("retry")),
        robots_html_typed_hosts_with_rules=sum(1 for d in snap.values() if d["state"] == "ok" and d.get("html_typed") and d.get("has_groups")),
        robotparser_vs_rfc9309=dict(entities=total, agree_on_4_tokens=agree),
        recheck_home=len(rh), recheck_home_municipal=len(mh),
        recheck_home_municipal_answered=sum(1 for d in mh if d.get("status") == 200),
        recheck_home_second_look=sum(1 for d in rh.values() if d.get("second_look")),
        recheck_statements=len(rs), recheck_sectxt_hosts=len(rt),
        robots_reread_utc=[min(d["fetched_at"] for d in snap.values() if d.get("fetched_at")),
                           max(d["fetched_at"] for d in snap.values() if d.get("fetched_at"))])
    json.dump(meta, open(os.path.join(ROOT, "data", "build_meta.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
