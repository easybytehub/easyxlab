#!/usr/bin/env python3
"""Build the published tables from data/population.csv + data/records.jsonl.gz.

Outputs (all in data/):
  entities.csv          one row per entity (all 8,275 entities, scanned or not)
  exclusions.csv        every scanned URL judged not to be the entity's own website, with the rule
  summary_by_type.csv   indicators by entity type
  summary_by_region.csv municipalities by autonomous community
  summary_by_size.csv   municipalities by population band
  coverage.csv          URL coverage of municipalities by region and band
  summary.json          headline numbers with 95% Wilson intervals (checked by check_numbers.py)
Reads, never writes: data/date_audit_v2.csv (the agent's audit of the date extractor).
Only booleans, statuses, public URLs and dates are written; no response bodies, no contact data.
"""
import csv, gzip, json, math, os, re, sys
from collections import Counter, defaultdict
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan as S  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
HEAD4 = ["gptbot", "claudebot", "google_extended", "ccbot"]
ALL_AI = [S.ai_key(t)[3:] for t in S.AI_TOKENS]
DATE_OK = {"v2", "v1_ctx_ok", "v1_nodate", "v2_recheck"}
SAME_AS_REGIONAL = {"INE51001": "CCAA18", "INE52001": "CCAA19"}    # Ceuta, Melilla
REDIRECTS = (301, 302, 303, 307, 308)
MIN_N = 10          # in the CSV tables a percentage is left blank when its denominator is under 10

# ---------------------------------------------------------------- is the URL the entity's site?
PLATFORMS = {"youtube.com", "youtu.be", "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
             "tiktok.com", "linkedin.com", "wikipedia.org", "wikimedia.org", "yahoo.com", "google.com"}
MARKETPLACES = {"hugedomains.com", "dropcatch.com", "nicsell.com", "sedo.com", "dan.com", "afternic.com",
                "godaddy.com", "buydomains.com", "undeveloped.com", "atom.com", "squadhelp.com", "sav.com",
                "domainmarket.com", "parkingcrew.net", "bodis.com", "above.com", "epik.com", "efty.com",
                "brandbucket.com", "uniregistry.com"}
DIRECTORIES = {"codigopostales.com", "codigo-postal.info", "codigospostales.com", "pueblos-espana.org",
               "lugares.com", "paginasamarillas.es"}
PANEL_PATH = re.compile(r"/login_up\.php|/cgi-sys/defaultwebpage\.cgi|:(2082|2083|2086|2087|8443|8880)(/|$)", re.I)
RULES = {
    "third_party_platform": "the URL or the page it redirects to is on a video, social-network or portal platform",
    "domain_for_sale": "the page is a domain marketplace or a parked/for-sale page",
    "directory_site": "the page belongs to a postcode or place directory",
    "hosting_panel_or_default_page": "the page is a hosting-panel login (e.g. Plesk /login_up.php) or a server's default page",
    "other_site_after_redirect": "redirected to another registrable domain whose page and URL carry no form of the municipality's name",
    "other_body_page": "the page's title names another municipality's council, or the page names a council or public body but neither it nor its URL names this municipality",
    "no_sign_of_council": "a page with text and a title, but neither the municipality's name nor any council wording",
}


def host(u):
    return (urlsplit(u or "").hostname or "").lower()


def reg(h):
    parts = (h or "").split(".")
    k = 3 if len(parts) >= 3 and parts[-2] in ("gob", "com", "org", "edu", "nom", "net") else 2
    return ".".join(parts[-k:])


def site_check(p, s):
    """('ok', how) or ('excluded', rule). Applied to every reachable home page; the name rules
    only to municipalities (curated URLs of other bodies were chosen, not looked up)."""
    url, fin, rfin = p["url"], s.get("home_final", ""), s.get("rc_final_url") or ""
    regs = {reg(host(u)) for u in (url, fin, rfin) if u}
    if regs & PLATFORMS:
        return "excluded", "third_party_platform"
    if regs & MARKETPLACES or s.get("rc_parking") or s.get("home_parking"):
        return "excluded", "domain_for_sale"
    if regs & DIRECTORIES:
        return "excluded", "directory_site"
    if PANEL_PATH.search(fin) or PANEL_PATH.search(rfin) or s.get("rc_panel") or s.get("rc_default_page") \
            or s.get("home_panel") or s.get("home_default_page"):
        return "excluded", "hosting_panel_or_default_page"
    if p["entity_type"] != "municipality":
        return "ok", "curated"
    if s.get("home_name_match") or s.get("rc_name_match") or s.get("rc_name_in_text") or s.get("rc_name_in_title"):
        return "ok", "name_on_page"
    if s.get("rc_title_other_council"):
        return "excluded", "other_body_page"
    runs = S.name_runs(p["name"])
    in_url = S.name_in_url(fin, runs) or bool(rfin and S.name_in_url(rfin, runs))
    if reg(host(fin)) != reg(host(url)) and not in_url:
        return "excluded", "other_site_after_redirect"
    rechecked = s.get("rc_status") == 200
    shell = s.get("rc_js_shell") if rechecked else s.get("home_js_shell")
    if rechecked and not shell:
        if s.get("rc_council_word"):
            return ("ok", "council_words_and_url") if in_url else ("excluded", "other_body_page")
        if s.get("rc_title_present"):
            return "excluded", "no_sign_of_council"
    return "ok", "unverified"


# ---------------------------------------------------------------- per-entity row
def band(p):
    if p == "" or p is None:
        return ""
    p = int(p)
    return ("a <1k" if p < 1000 else "b 1k-5k" if p < 5000 else "c 5k-20k" if p < 20000
            else "d 20k-100k" if p < 100000 else "e 100k+")


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(100 * (c - h), 1), round(100 * (c + h), 1))


def B(v):
    return "" if v is None else ("1" if v is True else "0" if v is False else v)


def outcome(s):
    """Why the home page was or was not analysed (one label per scanned entity)."""
    hs = s.get("home_status")
    if hs == "robots_discarded":
        return "robots_disallow" if s["robots_audit"].get("home") == "disallowed" else "robots_unverifiable"
    if hs == 200:
        return "ok" if s.get("home_html") else "200_not_html"
    if hs == "robots_disallowed":
        if s.get("scanner_version") == "2":
            if s.get("robots_state") == "ok":
                return "robots_disallow"
            st = s.get("robots_status")
            if s.get("robots_error") == "gaierror":
                return "dns_failure"
            if s.get("robots_error") == "host_budget":
                return "not_measured_budget"
            if s.get("robots_error"):
                return "connection_failure"
            return "robots_5xx" if isinstance(st, int) and st >= 500 else "robots_unreachable"
        err, st = s.get("robots_error_scan"), s.get("robots_status_scan")
        if err == "gaierror":
            return "dns_failure"
        if err == "redirect_target_budget":
            return "not_measured_budget"
        if err:
            return "connection_failure"       # the server did not answer the robots.txt request
        if isinstance(st, int) and 200 <= st < 300:
            return "robots_disallow"
        if isinstance(st, int) and st >= 500:
            return "robots_5xx"
        return "robots_unreachable"           # e.g. an unresolved 3xx
    if hs == "host_budget":
        return "not_measured_budget"
    if hs == 202:
        return "http_202"
    if hs in (401, 403, 429):
        return "forbidden"
    if hs in REDIRECTS:
        return "too_many_redirects" if (s.get("home_hops") or 0) >= 5 else "not_measured_budget"
    if isinstance(hs, int):
        return "http_error"
    if hs == "gaierror":
        return "dns_failure"
    return "connection_failure"


def derive(p, s):
    r = dict(entity_id=p["entity_id"], entity_type=p["entity_type"], name=p["name"], region=p["region"],
             province=p["province"], ine=p["ine"], population=p["population"], pop_band=band(p["population"]),
             url=p["url"], url_source=p["url_source"])
    scanned = bool(s)
    r.update(scanned=scanned, scan_run=s.get("scan_run", ""), home_status=s.get("home_status", "") if scanned else "",
             final_url=s.get("home_final", ""), home_outcome=outcome(s) if scanned else "not_scanned")
    if p["entity_id"] in SAME_AS_REGIONAL:
        r["home_outcome"] = "same_as_regional_entry"
        r["note"] = f"same body and website as {SAME_AS_REGIONAL[p['entity_id']]}; counted there"
    r["reachable"] = r["home_outcome"] == "ok"
    r["site_check"] = ""
    if r["reachable"]:
        verdict, how = site_check(p, s)
        r["site_check"] = how
        if verdict == "excluded":
            r.update(reachable=False, home_outcome="not_entity_site")
    a = s.get("robots_audit") or {}
    r.update(ra_home=a.get("home", ""), ra_sectxt=a.get("sectxt", a.get("sectxt_pass2", "")),
             ra_stmt=a.get("stmt", ""), ra_llms=a.get("llms", ""),
             robots_discarded=s.get("home_status") == "robots_discarded" or any(
                 s.get(k + "_status") == "robots_discarded" for k in ("sectxt", "stmt", "llms")))
    if not scanned or r["home_outcome"] == "same_as_regional_entry":
        return r
    excluded = r["home_outcome"] == "not_entity_site"
    reach = r["reachable"]
    https = bool(s.get("home_https")) if reach else None
    cert = (not s.get("https_cert_invalid")) if reach and https else None
    r.update(https=https, https_cert_ok=cert,
             http_upgrades=s.get("http_upgrades_to_https") if not excluded else None,
             hsts=bool(s.get("hsts")) if reach and https else None,
             hsts_1y=bool(s.get("hsts_1y")) if reach and https else None,
             hsts_valid_chain=bool(s.get("hsts") and cert) if reach and https else None)
    # robots.txt (RFC 9309 reading); not the entity's policy when the URL is not its site
    st = s.get("robots_state") if not excluded else None
    r.update(robots_state=st or "", robots_html_typed=s.get("robots_html_typed") if st else None,
             robots_has_groups=s.get("robots_has_groups") if st else None,
             robots_star_disallows_root=s.get("robots_star_blocks_root") if st in ("ok", "unavailable") else None,
             robots_known=st in ("ok", "unavailable"))
    if r["robots_known"]:
        for t in ALL_AI:
            r["ai_block_" + t] = bool(s.get(f"ai_{t}_blocked"))
        for t in HEAD4:
            r["ai_named_" + t] = bool(s.get(f"ai_{t}_named"))
        r["ai_block_any4"] = any(s.get(f"ai_{t}_blocked") for t in HEAD4)
        r["ai_named_block_any4"] = any(s.get(f"ai_{t}_blocked") and s.get(f"ai_{t}_named") for t in HEAD4)
        r["ai_block_all4"] = all(s.get(f"ai_{t}_blocked") for t in HEAD4)
    # security.txt
    sst = s.get("sectxt_status") if not excluded else None
    r["sectxt_answered"] = isinstance(sst, int)
    r.update(sectxt_status=sst if sst is not None else "", sectxt_source=s.get("sectxt_source", ""),
             sectxt_host=s.get("sectxt_host", "") if not excluded else "")
    for k in ("present", "soft404", "required_ok", "strict_ok", "expired", "expires", "expires_once",
              "expires_rfc3339", "text_plain", "utf8", "contact_all_uri", "web_uris_https", "signed",
              "policy", "canonical"):
        r["sectxt_" + k] = s.get("sectxt_" + k) if r["sectxt_answered"] else None
    # accessibility link and statement
    r.update(acc_link=s.get("acc_link") if reach else None, acc_url=s.get("acc_url", "") if reach else "",
             acc_source=s.get("acc_source", "scan") if reach else "", acc_vendor_link_v1=s.get("acc_vendor_link_v1", ""),
             home_js_shell=s.get("home_js_shell"), home_name_match=s.get("home_name_match"), arm=s.get("arm"))
    stst = s.get("stmt_status") if reach else None
    r.update(stmt_checked=isinstance(stst, int), stmt_status=stst if stst is not None else "",
             stmt_off_host=s.get("stmt_off_host") if reach else None, stmt_ok=s.get("stmt_ok") if reach else None,
             stmt_html=s.get("stmt_html") if reach else None,
             stmt_about_accessibility=s.get("stmt_about_accessibility") if reach else None,
             date_method=s.get("date_method", "") if reach else "",
             stmt_has_date=s.get("stmt_has_date") if reach else None,
             stmt_latest_date=(s.get("stmt_latest_date") or "") if reach else "",
             stmt_age_days=s.get("stmt_age_days") if reach else None,
             stmt_fresh_1y=s.get("stmt_fresh_1y") if reach else None)
    if r["date_method"] == "v1_rejected_unchecked":
        r.update(stmt_has_date=None, stmt_latest_date="", stmt_age_days=None, stmt_fresh_1y=None)
    base = r["stmt_checked"] and r["stmt_status"] == 200 and r["stmt_html"] and r["date_method"] in DATE_OK
    r["stmt_dates_all_pages"] = bool(base)
    r["stmt_dates_statements"] = bool(base and r["stmt_about_accessibility"])
    ls = s.get("llms_status") if reach else None
    r.update(llms_checked=isinstance(ls, int),
             llms_present=bool(s.get("llms_present") and s.get("llms_h1")) if isinstance(ls, int) else None,
             llms_200_text_no_h1=bool(s.get("llms_present") and not s.get("llms_h1")) if isinstance(ls, int) else None,
             llms_soft404=s.get("llms_soft404") if isinstance(ls, int) else None)
    return r


def rate(rows, num, den):
    d = [r for r in rows if den(r)]
    return sum(1 for r in d if num(r)), len(d)


def measured(r):
    return r["scanned"] and r["home_outcome"] not in ("not_measured_budget", "same_as_regional_entry")


INDICATORS = [
    # name, numerator, denominator
    ("reachable", lambda r: r["reachable"], measured),
    ("https", lambda r: r.get("https"), lambda r: r["reachable"]),
    ("https_cert_ok", lambda r: r.get("https_cert_ok"), lambda r: r["reachable"] and r.get("https")),
    ("http_upgrades", lambda r: r.get("http_upgrades"), lambda r: r["reachable"] and r.get("http_upgrades") is not None),
    ("hsts", lambda r: r.get("hsts"), lambda r: r["reachable"] and r.get("https")),
    ("hsts_valid_chain", lambda r: r.get("hsts_valid_chain"), lambda r: r["reachable"] and r.get("https")),
    ("hsts_1y", lambda r: r.get("hsts_1y"), lambda r: r["reachable"] and r.get("https")),
    ("ai_block_any4", lambda r: r.get("ai_block_any4"), lambda r: r.get("robots_known")),
    ("ai_named_block_any4", lambda r: r.get("ai_named_block_any4"), lambda r: r.get("robots_known")),
    ("ai_block_all4", lambda r: r.get("ai_block_all4"), lambda r: r.get("robots_known")),
    ("robots_star_disallows_root", lambda r: r.get("robots_star_disallows_root"), lambda r: r.get("robots_known")),
    ("sectxt_present", lambda r: r.get("sectxt_present"), lambda r: r.get("sectxt_answered")),
    ("sectxt_required_ok", lambda r: r.get("sectxt_required_ok"), lambda r: r.get("sectxt_answered")),
    ("sectxt_strict_ok", lambda r: r.get("sectxt_strict_ok"), lambda r: r.get("sectxt_answered")),
    ("sectxt_soft404", lambda r: r.get("sectxt_soft404"), lambda r: r.get("sectxt_answered")),
    ("acc_link", lambda r: r.get("acc_link"), lambda r: r["reachable"] and r.get("acc_link") is not None),
    ("stmt_ok", lambda r: r.get("stmt_ok"), lambda r: r.get("stmt_checked")),
    ("stmt_has_date", lambda r: r.get("stmt_has_date"), lambda r: r.get("stmt_dates_statements")),
    ("stmt_fresh_1y", lambda r: r.get("stmt_fresh_1y"), lambda r: r.get("stmt_dates_statements")),
    ("stmt_has_date_all_pages", lambda r: r.get("stmt_has_date"), lambda r: r.get("stmt_dates_all_pages")),
    ("stmt_fresh_1y_all_pages", lambda r: r.get("stmt_fresh_1y"), lambda r: r.get("stmt_dates_all_pages")),
    ("llms_present", lambda r: r.get("llms_present"), lambda r: r["reachable"] and r.get("llms_checked") and r.get("arm") == "L"),
]
for _t in ALL_AI:
    INDICATORS.append(("ai_block_" + _t, (lambda t: lambda r: r.get("ai_block_" + t))(_t), lambda r: r.get("robots_known")))


def ind(rows, n, num, den):
    k, m = rate(rows, num, den)
    return dict(k=k, n=m, pct=round(100 * k / m, 1) if m else None, ci95=wilson(k, m))


def summarise(rows, key, path):
    groups = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    cols = ["group", "entities", "with_url", "scanned"] + [f"{n}_{x}" for n, _, _ in INDICATORS for x in ("k", "n", "pct")]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for g in sorted(groups):
            rs = groups[g]
            line = [g, len(rs), sum(1 for r in rs if r["url"]), sum(1 for r in rs if r["scanned"])]
            for n, num, den in INDICATORS:
                k, m = rate(rs, num, den)
                line += [k, m, round(100 * k / m, 1) if m >= MIN_N else ""]
            w.writerow(line)


def load_records():
    p = os.path.join(D, "records.jsonl.gz")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return {s["entity_id"]: s for s in map(json.loads, f)}


def main():
    pop = list(csv.DictReader(open(os.path.join(D, "population.csv"), encoding="utf-8")))
    recs = load_records()
    rows = [derive(p, recs.get(p["entity_id"], {})) for p in pop]
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(os.path.join(D, "entities.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: B(r.get(k)) for k in cols})
    # exclusions: every scanned URL judged not to be the entity's website
    with open(os.path.join(D, "exclusions.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["entity_id", "entity_type", "name", "region", "url", "final_url", "rule", "rule_text"])
        for p, r in zip(pop, rows):
            if r["home_outcome"] == "not_entity_site":
                rule = site_check(p, recs[p["entity_id"]])[1]
                w.writerow([r["entity_id"], r["entity_type"], r["name"], r["region"], r["url"], r["final_url"],
                            rule, RULES[rule]])
    summarise(rows, lambda r: r["entity_type"], os.path.join(D, "summary_by_type.csv"))
    mun = [r for r in rows if r["entity_type"] == "municipality"]
    summarise(mun, lambda r: r["region"], os.path.join(D, "summary_by_region.csv"))
    summarise(mun, lambda r: r["pop_band"], os.path.join(D, "summary_by_size.csv"))
    # coverage
    with open(os.path.join(D, "coverage.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dimension", "group", "municipalities", "population", "with_url", "pct_with_url",
                    "population_with_url_pct", "from_wikidata", "from_clm_directory", "override", "reachable"])
        for dim, key in (("region", lambda r: r["region"]), ("size", lambda r: r["pop_band"]), ("all", lambda r: "Spain")):
            g = defaultdict(list)
            for r in mun:
                g[key(r)].append(r)
            for k in sorted(g):
                rs = g[k]
                popt = sum(int(r["population"] or 0) for r in rs)
                popu = sum(int(r["population"] or 0) for r in rs if r["url"])
                wu = sum(1 for r in rs if r["url"])
                w.writerow([dim, k, len(rs), popt, wu, round(100 * wu / len(rs), 1),
                            round(100 * popu / popt, 1) if popt else "",
                            sum(1 for r in rs if r["url_source"] == "wikidata_P856"),
                            sum(1 for r in rs if r["url_source"] == "clm_directorio_entidades_locales"),
                            sum(1 for r in rs if r["url_source"] == "override"),
                            sum(1 for r in rs if r["reachable"])])
    # ---------------------------------------------------------------- summary.json
    out = {"entities": len(rows), "municipalities": len(mun),
           "municipalities_with_url": sum(1 for r in mun if r["url"]),
           "population_total": sum(int(r["population"] or 0) for r in mun),
           "population_with_url_pct": round(100 * sum(int(r["population"] or 0) for r in mun if r["url"]) /
                                            sum(int(r["population"] or 0) for r in mun), 1),
           "entities_with_url": sum(1 for r in rows if r["url"]),
           "scanned": sum(1 for r in rows if r["scanned"]),
           "measured": sum(1 for r in rows if measured(r)),
           "by_type": {}, "all": {}}
    for t in sorted({r["entity_type"] for r in rows}):
        rs = [r for r in rows if r["entity_type"] == t]
        out["by_type"][t] = {n: ind(rs, n, num, den) for n, num, den in INDICATORS}
        out["by_type"][t]["entities"] = len(rs)
    out["all"] = {n: ind(rows, n, num, den) for n, num, den in INDICATORS}
    out["home_outcome_counts"] = {t: dict(Counter(r["home_outcome"] for r in rows if r["entity_type"] == t and r["scanned"]))
                                  for t in sorted({r["entity_type"] for r in rows})}
    out["home_outcome_counts_all"] = dict(Counter(r["home_outcome"] for r in rows if r["scanned"]))
    out["exclusions_by_rule"] = dict(Counter(r["site_check"] for r in rows if r["home_outcome"] == "not_entity_site"))
    out["exclusions_by_rule_and_source"] = dict(Counter(f'{r["site_check"]}|{r["url_source"]}' for r in rows
                                                        if r["home_outcome"] == "not_entity_site"))
    out["site_check_reachable_municipal"] = dict(Counter(r["site_check"] for r in mun if r["reachable"]))
    out["dns_failure_by_source"] = dict(Counter(r["url_source"] for r in mun if r["home_outcome"] == "dns_failure"))
    with_src = Counter(r["url_source"] for r in mun if r["url"])
    out["municipal_urls_by_source"] = dict(with_src)
    # robots audit of the first scan
    ra = Counter()
    for s in recs.values():
        for k, v in (s.get("robots_audit") or {}).items():
            ra[f"{k}:{v}"] += 1
    out["robots_audit_counts"] = dict(ra)
    out["robots_discarded_entities"] = {
        "home_and_all": sum(1 for s in recs.values() if s.get("home_status") == "robots_discarded"),
        "home_disallowed": sum(1 for s in recs.values() if s.get("home_status") == "robots_discarded"
                               and s["robots_audit"].get("home") == "disallowed"),
        "home_unverifiable": sum(1 for s in recs.values() if s.get("home_status") == "robots_discarded"
                                 and s["robots_audit"].get("home") == "unverifiable"),
        "sectxt_only": sum(1 for s in recs.values() if s.get("home_status") != "robots_discarded"
                           and s.get("sectxt_status") == "robots_discarded"),
        "stmt_only": sum(1 for s in recs.values() if s.get("home_status") != "robots_discarded"
                         and s.get("stmt_status") == "robots_discarded"),
        "llms_only": sum(1 for s in recs.values() if s.get("home_status") != "robots_discarded"
                         and s.get("llms_status") == "robots_discarded"),
        "sectxt_pass2": sum(1 for s in recs.values() if (s.get("robots_audit") or {}).get("sectxt_pass2", "allowed") != "allowed"),
        "home_not_fetched_but_allowed": sum(1 for s in recs.values() if (s.get("robots_audit") or {}).get("home_not_fetched_but_allowed")),
    }
    aud = [s.get("robots_audit") or {} for s in recs.values()]
    out["robots_entities_any_request_disallowed"] = sum(1 for a in aud if "disallowed" in a.values())
    out["robots_entities_home_allowed_other_disallowed"] = sum(1 for a in aud if a.get("home", "allowed") == "allowed"
                                                            and "disallowed" in a.values())
    out["robots_entities_any_request_discarded"] = sum(1 for a in aud if any(
        v != "allowed" for k, v in a.items() if k != "home_not_fetched_but_allowed"))
    disc = [r for r in rows if r["home_outcome"] in ("robots_disallow", "robots_unverifiable") and r["ra_home"]]
    out["robots_discarded_by_region"] = dict(Counter(r["region"] for r in disc))
    out["robots_html_typed_with_rules"] = {
        "entities": sum(1 for r in rows if r.get("robots_html_typed") and r.get("robots_has_groups")),
        "hosts": len({host(r["url"]) for r in rows if r.get("robots_html_typed") and r.get("robots_has_groups")})}
    # extra breakdowns used in the paper
    known = [r for r in rows if r.get("robots_known")]
    out["ai_named_any4"] = rate(rows, lambda r: any(r.get("ai_named_" + t) for t in HEAD4), lambda r: r.get("robots_known"))
    out["robots_state_counts"] = dict(Counter(r.get("robots_state") or "none" for r in rows if r["scanned"]))
    out["llms_present_any_arm"] = sum(1 for r in rows if r.get("llms_present"))
    out["llms_checked_any_arm"] = sum(1 for r in rows if r.get("llms_checked") and r["reachable"])
    out["llms_200_text_no_h1_any_arm"] = sum(1 for r in rows if r.get("llms_200_text_no_h1"))
    out["llms_present_entities"] = sorted(r["name"] for r in rows if r.get("llms_present"))
    pres = [r for r in rows if r.get("sectxt_present")]
    out["sectxt_present_entities"] = sorted(
        (dict(entity_id=r["entity_id"], name=r["name"], host=r["sectxt_host"], required_ok=r["sectxt_required_ok"],
              strict_ok=r["sectxt_strict_ok"], expired=r["sectxt_expired"], has_expires=r["sectxt_expires"],
              text_plain=r["sectxt_text_plain"], charset_utf8=r["sectxt_utf8"], contact_all_uri=r["sectxt_contact_all_uri"],
              expires_rfc3339=r["sectxt_expires_rfc3339"], source=r["sectxt_source"]) for r in pres),
        key=lambda x: x["entity_id"])
    out["sectxt_present_files"] = len({r["sectxt_host"] for r in pres})
    out["sectxt_required_ok_files"] = len({r["sectxt_host"] for r in pres if r["sectxt_required_ok"]})
    out["sectxt_strict_ok_files"] = len({r["sectxt_host"] for r in pres if r["sectxt_strict_ok"]})
    out["sectxt_soft404_html_or_text"] = rate(rows, lambda r: r.get("sectxt_soft404"), lambda r: r.get("sectxt_answered"))
    out["name_match_municipal_reachable"] = rate(mun, lambda r: r.get("home_name_match"), lambda r: r["reachable"])
    out["stmt_off_host_share"] = rate(rows, lambda r: r.get("stmt_off_host"), lambda r: r.get("stmt_checked"))
    out["js_shell_reachable"] = rate(rows, lambda r: r.get("home_js_shell"), lambda r: r["reachable"])
    out["acc_link_unknown_widget"] = sum(1 for r in rows if r["reachable"] and r.get("acc_link") is None)
    out["acc_link_widget_rechecked"] = sum(1 for r in rows if r.get("acc_vendor_link_v1") and r.get("acc_source") == "recheck")
    out["acc_vendor_links_v1"] = sum(1 for r in rows if r.get("acc_vendor_link_v1"))
    out["stmt_200_html"] = rate(rows, lambda r: r.get("stmt_status") == 200, lambda r: r.get("stmt_checked"))
    out["stmt_200_without_statement_wording"] = sum(1 for r in rows if r.get("stmt_ok") and r.get("stmt_html")
                                                     and not r.get("stmt_about_accessibility"))
    out["date_method_counts"] = dict(Counter(r["date_method"] for r in rows if r.get("date_method")))
    out["date_method_counts_statements"] = dict(Counter(r["date_method"] for r in rows if r.get("date_method")
                                                        and r.get("stmt_status") == 200 and r.get("stmt_html")
                                                        and r.get("stmt_about_accessibility")))
    v1 = [s for s in recs.values() if s.get("scan_run") == 2 and s.get("date_method") in ("v1_ctx_ok", "v2_recheck", "v1_rejected_unchecked")]
    out["v1_recheck"] = dict(v1_dated_with_sentence=len(v1),
                             confirmed=sum(1 for s in v1 if s["date_method"] == "v1_ctx_ok"),
                             rejected=sum(1 for s in v1 if s["date_method"] != "v1_ctx_ok"),
                             rejected_reread=sum(1 for s in v1 if s["date_method"] == "v2_recheck"),
                             rejected_reread_dated=sum(1 for s in v1 if s["date_method"] == "v2_recheck" and s.get("stmt_has_date")))
    dated = [r for r in rows if r.get("stmt_dates_statements") and r.get("stmt_has_date")]
    out["dated_statements"] = len(dated)
    out["dated_by_year"] = dict(sorted(Counter(r["stmt_latest_date"][:4] for r in dated).items()))
    top = Counter(r["stmt_latest_date"] for r in dated).most_common(10)
    out["top_dates"] = [dict(date=d, n=n, regions=dict(Counter(r["region"] for r in dated if r["stmt_latest_date"] == d)),
                             provinces=dict(Counter(r["province"] for r in dated if r["stmt_latest_date"] == d)))
                        for d, n in top]
    top6 = sum(t["n"] for t in out["top_dates"][:6])
    out["top6_dates"] = dict(k=top6, n=len(dated), pct=round(100 * top6 / len(dated), 1),
                             single_province=all(len(t["provinces"]) == 1 for t in out["top_dates"][:6]))
    out["dated_2018_2021"] = sum(v for y, v in out["dated_by_year"].items() if y <= "2021")
    out["http_202_by_province"] = dict(Counter(r["province"] for r in rows if r["home_outcome"] == "http_202").most_common(5))
    disc_html = [r for r, s in ((r, recs.get(r["entity_id"], {})) for r in rows)
                 if s.get("home_status") == "robots_discarded" and s["robots_audit"].get("home") == "disallowed"
                 and s.get("robots_html_typed") and s.get("robots_has_groups")]
    out["robots_discarded_html_typed"] = dict(n=len(disc_html), by_province=dict(Counter(r["province"] for r in disc_html)))
    out["hsts_with_cert_error"] = sum(1 for r in rows if r.get("hsts") and r.get("https_cert_ok") is False)
    out["municipal_reachable_rechecked"] = sum(1 for r in mun if r["reachable"] and recs[r["entity_id"]].get("rc_status") is not None)
    out["first_run_statements"] = dict(
        fetched=sum(1 for r in rows if r.get("date_method") == "v1_first_run"),
        by_type=dict(Counter(r["entity_type"] for r in rows if r.get("date_method") == "v1_first_run")))
    # municipal coverage by size band (paper table)
    out["coverage_by_band"] = {}
    for b in sorted({r["pop_band"] for r in mun}):
        rs = [r for r in mun if r["pop_band"] == b]
        pt = sum(int(r["population"] or 0) for r in rs)
        out["coverage_by_band"][b] = dict(n=len(rs), with_url=sum(1 for r in rs if r["url"]),
                                          pct=round(100 * sum(1 for r in rs if r["url"]) / len(rs), 1),
                                          pop_pct=round(100 * sum(int(r["population"] or 0) for r in rs if r["url"]) / pt, 1))
    # date audit (written by the agent, never regenerated here)
    ap = os.path.join(D, "date_audit_v2.csv")
    if os.path.exists(ap):
        au = list(csv.DictReader(open(ap, encoding="utf-8")))
        k = sum(1 for a in au if a["verdict"] == "correct")
        n = sum(1 for a in au if a["verdict"] in ("correct", "wrong"))
        out["date_audit_v2"] = dict(k=k, n=n, ci95=wilson(k, n), unjudged=len(au) - n)
    out["other_body_page_by_province"] = dict(Counter(r["province"] for r in rows if r["site_check"] == "other_body_page"))
    # derived figures the abstract quotes (added 2026-10-05, full precision)
    hc = out["home_outcome_counts_all"]
    out["municipalities_with_url_share"] = out["municipalities_with_url"] / out["municipalities"]
    out["home_measurable"] = (out["measured"] - hc.get("robots_5xx", 0) - hc.get("robots_disallow", 0)
                              - hc.get("robots_unverifiable", 0))
    out["home_ok_share_of_measurable"] = hc.get("ok", 0) / out["home_measurable"]
    # added 2026-10-05 (closing review): «concentrated in a few regions» and «every requirement
    # of RFC 9116 we can test», each checked against data rather than read off the prose
    top3 = Counter(r["region"] for r in rows if r.get("ai_block_any4")).most_common(3)
    out["ai_block_any4_top3_regions"] = sum(k for _, k in top3)
    # base rate for «concentrated»: the share of entities with a robots.txt read (the indicator's
    # denominator) that lie in those same three regions
    out["ai_block_top3_regions_entity_share"] = (
        sum(1 for r in rows if r.get("robots_known") and r["region"] in {g for g, _ in top3})
        / sum(1 for r in rows if r.get("robots_known")))
    musts = ("present", "https", "contact", "contact_all_uri", "web_uris_https", "expires_once",
             "expires_parse", "expires_rfc3339", "text_plain", "utf8", "body_utf8", "pref_lang_once",
             "lines_ok")
    out["sectxt_pass_each_tested_must"] = sum(
        1 for r in rows if r.get("sectxt_answered")
        and all(recs.get(r["entity_id"], {}).get("sectxt_" + m) for m in musts)
        and recs.get(r["entity_id"], {}).get("sectxt_expired") is False)
    # external: websites in the OAW's in-depth monitoring by year (paper §2; the OAW's reports)
    out["oaw_in_depth_sites"] = {"2022": 64, "2023": 62, "2024": 63, "2025": 63}
    mp = os.path.join(D, "build_meta.json")
    if os.path.exists(mp):
        out["build_meta"] = json.load(open(mp))
    json.dump(out, open(os.path.join(D, "summary.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: out[k] for k in ("entities", "municipalities", "municipalities_with_url", "measured")}))


if __name__ == "__main__":
    main()
