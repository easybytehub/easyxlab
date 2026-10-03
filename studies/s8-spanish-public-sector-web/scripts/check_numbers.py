#!/usr/bin/env python3
"""Assert that the figures quoted in README.md and paper.md are the ones in data/.

Each claim is a phrase built from data/summary.json (or the summary CSVs) and must appear
verbatim in the document (whitespace normalised, so line breaks do not matter). If a document
is edited, or the data change, the check fails and says which phrase is missing.
Exit status 0 = every claim found.
"""
import csv, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open(os.path.join(ROOT, "data", "summary.json"), encoding="utf-8"))
REG = {r["group"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "summary_by_region.csv"), encoding="utf-8"))}
SIZE = {r["group"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "summary_by_size.csv"), encoding="utf-8"))}
DOCS = {f: re.sub(r"\s+", " ", open(os.path.join(ROOT, f), encoding="utf-8").read())
        for f in ("README.md", "paper.md") if os.path.exists(os.path.join(ROOT, f))}
if "paper.md" not in DOCS:  # the public package on GitHub ships without the paper
    print("paper.md is not in the public package: the paper is at https://easybyte.es/lab/studies/s8/paper/")


def n(x):
    return f"{int(x):,}"


def p(x):
    return "100" if float(x) == 100 else f"{float(x):.1f}"


def P(k, m):
    return p(100 * int(k) / int(m))


A, T, H = S["all"], S["by_type"], S["home_outcome_counts"]["municipality"]
M = T["municipality"]
claims = []


def claim(doc, text):
    claims.append((doc, text))


def both(text):
    claim("README.md", text)
    claim("paper.md", text)


# --- population and coverage
both(f"{n(S['municipalities_with_url'])} of Spain's {n(S['municipalities'])} municipalities")
both(f"({p(100 * S['municipalities_with_url'] / S['municipalities'])}% of municipalities, {p(S['population_with_url_pct'])}% of the population)")
cb = S["coverage_by_band"]
claim("README.md", f"{n(cb['a <1k']['with_url'])} of {n(cb['a <1k']['n'])} under 1,000 inhabitants, {p(cb['a <1k']['pct'])}%")
for band, label in (("a <1k", "< 1,000 inhabitants"), ("b 1k-5k", "1,000–5,000"), ("c 5k-20k", "5,000–20,000"),
                    ("d 20k-100k", "20,000–100,000"), ("e 100k+", "≥ 100,000")):
    c = cb[band]
    claim("paper.md", f"| {label} | {n(c['n'])} | {n(c['with_url'])} | {p(c['pct'])} | {p(c['pop_pct'])} |")
claim("paper.md", f"| **all** | **{n(S['municipalities'])}** | **{n(S['municipalities_with_url'])}** | "
                  f"**{p(100 * S['municipalities_with_url'] / S['municipalities'])}** | **{p(S['population_with_url_pct'])}** |")
claim("paper.md", f"The {n(S['municipalities'] - S['municipalities_with_url'])} municipalities without a URL")

# --- reachability
r = A["reachable"]
both(f"Of {n(r['n'])} entities whose home page we could measure, {n(r['k'])} ({p(r['pct'])}%) returned their own home page")
claim("README.md", f"{H['not_entity_site']} municipal URLs led to something that is not the council's site")
claim("paper.md", f"to something that is not the entity's site ({H['not_entity_site']} URLs")
claim("paper.md", f"Of {n(S['entities_with_url'])} entities with a URL, {S['entities_with_url'] - S['measured']} could not be measured")
claim("paper.md", f"Of the remaining {n(r['n'])}, {n(r['k'])} ({p(r['pct'])}%) returned their own home page")
mr = M["reachable"]
claim("paper.md", f"The {n(mr['n'] - mr['k'])} municipalities that did not (of {n(mr['n'])} measured)")
for key, phrase in (("dns_failure", "the domain no longer resolves ({})"), ("http_error", "the server returned an HTTP error ({})"),
                    ("robots_disallow", "*not measurable: robots.txt disallows* ({},"),
                    ("robots_5xx", "`robots.txt` answered 5xx so we did not crawl ({})"),
                    ("not_entity_site", "the URL does not lead to the municipality's site ({},"),
                    ("connection_failure", "the server did not answer ({})"), ("http_202", "typically a bot challenge ({};"),
                    ("forbidden", "the server refused our client ({};"), ("too_many_redirects", "could not leave ({},"),
                    ("robots_unverifiable", "*not verifiable* ({},"), ("200_not_html", "a 200 response that is not HTML ({})")):
    claim("paper.md", phrase.format(n(H[key])))
claim("paper.md", f"{S['http_202_by_province']['Málaga']} of them in the province of Málaga")
claim("paper.md", f"Four of the 22 ministries' home pages answered 403")
assert S["home_outcome_counts"]["ministry"].get("forbidden") == 4

# --- HTTPS / HSTS
h, hv, h1, hu, hc = A["https"], A["hsts"], A["hsts_1y"], A["http_upgrades"], A["https_cert_ok"]
both(f"{n(h['k'])} ({p(h['pct'])}%) served the home page over HTTPS when asked")
claim("README.md", f"**{n(hv['k'])} of those {n(hv['n'])} ({p(hv['pct'])}%) send HSTS**")
claim("paper.md", f"and {n(hv['k'])} of those {n(hv['n'])} ({p(hv['pct'])}%) sent HSTS")
claim("paper.md", f"HTTPS is nearly universal: {n(h['k'])} of {n(h['n'])} reachable home pages ({p(h['pct'])}%)")
claim("paper.md", f"{n(hv['k'])} of the {n(hv['n'])} ({p(hv['pct'])}%) send it. {S['hsts_with_cert_error']} of those")
claim("paper.md", f"is {n(A['hsts_valid_chain']['k'])} of {n(A['hsts_valid_chain']['n'])} ({p(A['hsts_valid_chain']['pct'])}%)")
claim("paper.md", f"(5,130 in all); HTTP → HTTPS over reachable entities whose plain-HTTP `robots.txt` request got an answer ({n(hu['n'])})")
claim("paper.md", f"| **all** | **{n(r['k'])}** | **{p(h['pct'])}%** | **{p(hc['pct'])}%** | **{p(hu['pct'])}%** | **{p(hv['pct'])}%** | **{p(h1['pct'])}%** |")
for t, label in (("municipality", "municipalities"), ("provincial_council", "provincial councils"),
                 ("public_university", "universities"), ("regional_government", "regional governments"), ("ministry", "ministries")):
    b = T[t]
    cells = [b[k]["pct"] for k in ("https", "https_cert_ok", "http_upgrades", "hsts", "hsts_1y")]
    claim("paper.md", f"| {label} | {n(b['reachable']['k'])} | " + " | ".join(p(c) + "%" for c in cells) + " |")
for reg_, label in (("Comunitat Valenciana", "in the Valencian Community"), ("Balears, Illes", "in the Balearic Islands"),
                    ("Asturias, Principado de", "in Asturias"), ("Navarra, Comunidad Foral de", "in Navarra"), ("Aragón", "in Aragón")):
    g = REG[reg_]
    claim("paper.md", f"{g['hsts_k']} of {g['hsts_n']} {label} ({p(g['hsts_pct'])}%)" if label != "in the Valencian Community"
          else f"{g['hsts_k']} of {g['hsts_n']} municipal home pages served over HTTPS {label} ({p(g['hsts_pct'])}%)")

# --- security.txt
st = A["sectxt_present"]
both(f"{n(st['n'])} entities whose server answered")
claim("README.md", f"12 serve a file, 8 have its required fields and 4 are strictly valid under RFC 9116")
claim("paper.md", f"{st['k']} (0.2%) serve a file, {A['sectxt_required_ok']['k']} have its two required fields")
claim("paper.md", f"and {A['sectxt_strict_ok']['k']} meet every requirement of RFC 9116 we can test")
assert (st["k"], A["sectxt_required_ok"]["k"], A["sectxt_strict_ok"]["k"]) == (12, 8, 4)
claim("paper.md", f"for the {st['k']} entities ({S['sectxt_present_files']} files)")
claim("paper.md", f"**{A['sectxt_required_ok']['k']} of {n(st['n'])} entities ({S['sectxt_required_ok_files']} files)**")
claim("paper.md", f"**{A['sectxt_strict_ok']['k']} of {n(st['n'])} entities**: Madrid, Málaga, Adeje and Fuenllana")
strict = sorted(e["name"] for e in S["sectxt_present_entities"] if e["strict_ok"])
assert strict == ["Adeje", "Fuenllana", "Madrid", "Málaga"], strict
req = sorted(e["name"] for e in S["sectxt_present_entities"] if e["required_ok"])
assert req == sorted(["Madrid", "Málaga", "Adeje", "Fuenllana", "Bargas", "Pobladura del Valle", "Deputación da Coruña", "Vilasantar"]), req
sf = A["sectxt_soft404"]
claim("README.md", f"while {n(sf['k'])} ({p(sf['pct'])}%) answer that path with HTTP 200 and something else")
claim("paper.md", f"while {n(sf['k'])} ({p(sf['pct'])}%) answer that path with HTTP 200 and something else")
claim("paper.md", f"**{n(sf['k'])} of the {n(sf['n'])} ({p(sf['pct'])}%) answer the path with HTTP 200")
claim("paper.md", f"would report {round(sf['k'] / st['k'])} times more")

# --- accessibility link and statements
a = A["acc_link"]
claim("README.md", f"**{n(a['k'])} of {n(a['n'])} home pages ({p(a['pct'])}%)**")
claim("paper.md", f"{n(a['k'])} of the {n(a['n'])} home pages ({p(a['pct'])}%) carry a link")
claim("paper.md", f"**{n(a['k'])} of {n(a['n'])} reachable home pages ({p(a['pct'])}%)**")
for t, lab in (("ministry", "ministries"), ("provincial_council", "provincial councils"), ("public_university", "universities"),
               ("regional_government", "regional governments"), ("municipality", "municipalities")):
    b = T[t]["acc_link"]
    claim("paper.md", f"{n(b['k'])} of {n(b['n'])} {lab} ({p(b['pct'])}%)")
for band, lab in (("a <1k", "under 1,000 inhabitants"), ("d 20k-100k", "at 20,000–100,000"), ("e 100k+", "above 100,000")):
    g = SIZE[band]
    claim("paper.md", f"{n(g['acc_link_k'])} of {n(g['acc_link_n'])} {lab}, {p(g['acc_link_pct'])}%")
for reg_, lab in (("Asturias, Principado de", "in Asturias"), ("Extremadura", "in Extremadura"), ("Cataluña", "in Catalonia"),
                  ("Rioja, La", "in La Rioja"), ("País Vasco", "in the Basque Country"), ("Madrid, Comunidad de", "in the Community of Madrid")):
    g = REG[reg_]
    claim("paper.md", f"{g['acc_link_k']} of {g['acc_link_n']} {lab}, {p(g['acc_link_pct'])}%")
claim("paper.md", f"counted {S['acc_vendor_links_v1']} credit links")
assert S["acc_link_widget_rechecked"] == S["acc_vendor_links_v1"] and S["acc_link_unknown_widget"] == 0
so = S["stmt_200_html"]
claim("paper.md", f"Of {n(so[1])} linked pages requested, {n(so[0])} ({P(so[0], so[1])}%) answered 200; {S['stmt_200_without_statement_wording']} of the HTML pages")
d, f_ = A["stmt_has_date"], A["stmt_fresh_1y"]
both(f"of {n(d['n'])} statements read with an audited date extractor, {n(d['k'])} ({p(d['pct'])}%) show a preparation or review date")
claim("README.md", f"**{f_['k']} ({p(f_['pct'])}%) show one from the last 365 days**")
claim("paper.md", f"{f_['k']} ({p(f_['pct'])}%; 95% CI {p(f_['ci95'][0])}–{p(f_['ci95'][1])}) show one from the last 365 days")
claim("paper.md", f"Of **{n(d['n'])} statement pages** read with the audited extractor (§7), **{n(d['k'])} ({p(d['pct'])}%) show a preparation or review date, and {f_['k']} ({p(f_['pct'])}%; 95% CI {p(f_['ci95'][0])}–{p(f_['ci95'][1])})")
da, fa = A["stmt_has_date_all_pages"], A["stmt_fresh_1y_all_pages"]
claim("paper.md", f"the figures are {da['k']} and {fa['k']} of {n(da['n'])} ({p(da['pct'])}% and {p(fa['pct'])}%)")
y = S["dated_by_year"]
claim("paper.md", f"of the {S['dated_statements']}, {S['dated_2018_2021']} are from 2018–2021, {y['2022']} from 2022, {y['2023']} from 2023, {y['2024']} from 2024, {y['2025']} from 2025 and {y['2026']} from 2026")
t6 = S["top6_dates"]
assert t6["single_province"]
both(f"{t6['k']} of the {t6['n']} dated statements ({p(t6['pct'])}%)")
td = S["top_dates"]
claim("paper.md", f"28 June 2022 on {td[0]['n']} statements in Burgos, 27 March 2024 on {td[1]['n']} in Valencia, 6 September 2023 on {td[2]['n']} in Granada, 18 February 2026 on {td[3]['n']} in Badajoz, 26 April 2024 on {td[4]['n']} in Albacete and 11 December 2023 on {td[5]['n']} in Jaén")
assert [t["date"] for t in td[:6]] == ["2022-06-28", "2024-03-27", "2023-09-06", "2026-02-18", "2024-04-26", "2023-12-11"]
for reg_, lab in (("Extremadura", "in Extremadura"), ("Cataluña", "in Catalonia"), ("Andalucía", "in Andalusia"),
                  ("Castilla y León", "in Castilla y León"), ("Comunitat Valenciana", "in the Valencian Community")):
    g = REG[reg_]
    claim("paper.md", f"{g['stmt_fresh_1y_k']} of {g['stmt_fresh_1y_n']} {lab}")
claim("paper.md", f"all {S['first_run_statements']['fetched']} statements fetched for them")

# --- AI crawlers and llms.txt
ai = A["ai_block_any4"]
both(f"{ai['k']} of {n(ai['n'])} entities ({p(ai['pct'])}%) block at least one of GPTBot, ClaudeBot")
claim("paper.md", f"over the {n(ai['n'])} entities whose `robots.txt` answered")
claim("paper.md", f"**{ai['k']} of the {n(ai['n'])} ({p(ai['pct'])}%) disallow `/` to at least one of GPTBot")
claim("paper.md", f"{A['ai_named_block_any4']['k']} ({p(A['ai_named_block_any4']['pct'])}%) do so by naming the crawler, {A['ai_block_all4']['k']} ({p(A['ai_block_all4']['pct'])}%) block all four, and {A['robots_star_disallows_root']['k']} ({p(A['robots_star_disallows_root']['pct'])}%)")
for tok, lab in (("bytespider", "Bytespider"), ("gptbot", "GPTBot"), ("meta_externalagent", "meta-externalagent"),
                 ("chatgpt_user", "ChatGPT-User"), ("ccbot", "CCBot"), ("claudebot", "ClaudeBot"), ("oai_searchbot", "OAI-SearchBot"),
                 ("google_extended", "Google-Extended"), ("perplexitybot", "PerplexityBot")):
    b = A["ai_block_" + tok]
    claim("paper.md", f"{lab} {b['k']} ({p(b['pct'])}%)")
for reg_, lab in (("Asturias, Principado de", "municipalities in Asturias"), ("País Vasco", "in the Basque Country"),
                  ("Comunitat Valenciana", "in the Valencian Community"), ("Canarias", "in the Canary Islands"),
                  ("Balears, Illes", "in the Balearic Islands")):
    g = REG[reg_]
    claim("paper.md", f"{g['ai_block_any4_k']} of {g['ai_block_any4_n']} {lab} ({p(g['ai_block_any4_pct'])}%")
claim("paper.md", f"({p(REG['Asturias, Principado de']['ai_block_any4_pct'])}%, all by naming the crawlers)")
assert REG["Asturias, Principado de"]["ai_named_block_any4_k"] == REG["Asturias, Principado de"]["ai_block_any4_k"]
claim("paper.md", f"({p(REG['País Vasco']['ai_block_any4_pct'])}%; {REG['País Vasco']['ai_named_block_any4_k']} by naming)")
claim("paper.md", f"({p(REG['Comunitat Valenciana']['ai_block_any4_pct'])}%; {REG['Comunitat Valenciana']['robots_star_disallows_root_k']} through `User-agent: *`")
others = [float(g["ai_block_any4_pct"]) for k, g in REG.items() if g["ai_block_any4_pct"] and k not in
          ("Asturias, Principado de", "País Vasco", "Comunitat Valenciana", "Canarias", "Balears, Illes")]
assert max(others) == float(REG["Murcia, Región de"]["ai_block_any4_pct"]) == 7.1
claim("paper.md", f"no more than 7.1% ({REG['Murcia, Región de']['ai_block_any4_k']} of {REG['Murcia, Región de']['ai_block_any4_n']}, Murcia)")
for t, lab in (("provincial_council", "provincial councils"), ("public_university", "universities"), ("regional_government", "regional governments")):
    b = T[t]["ai_block_any4"]
    claim("paper.md", f"{b['k']} of {b['n']} {lab} ({p(b['pct'])}%)")
claim("paper.md", f"but {T['ministry']['ai_block_any4']['k']} of {T['ministry']['ai_block_any4']['n']} ministries")
l = A["llms_present"]
claim("README.md", f"appears on {l['k']} of {n(l['n'])} sites in a random subsample ({p(l['pct'])}%)")
claim("paper.md", f"appears on {l['k']} of {n(l['n'])} sites in a random subsample ({p(l['pct'])}%)")
claim("paper.md", f"**{l['k']} of {n(l['n'])} reachable sites in the random arm ({p(l['pct'])}%; 95% CI {p(l['ci95'][0])}–{p(l['ci95'][1])})**, and on {S['llms_present_any_arm']} sites across both arms")
claim("paper.md", f"Another {S['llms_200_text_no_h1_any_arm']} sites answer `/llms.txt`")

# --- site identity (exclusions)
ex = S["exclusions_by_rule"]
for rule, phrase in (("third_party_platform", "Yahoo, …) — {} municipalities"), ("domain_for_sale", "reserva\", …) — {};"),
                     ("directory_site", "postcode or place directory — {};"), ("hosting_panel_or_default_page", "\"Coming Soon\", …) — {};"),
                     ("other_site_after_redirect", "a provincial portal's home page) — {};"), ("other_body_page", "names this municipality — {} ("),
                     ("no_sign_of_council", "(mostly hijacked domains) — {}.")):
    claim("paper.md", phrase.format(ex[rule]))
assert sum(ex.values()) == H["not_entity_site"]
src = S["exclusions_by_rule_and_source"]
wd = sum(v for k, v in src.items() if k.endswith("|wikidata_P856"))
clm = sum(v for k, v in src.items() if k.endswith("|clm_directorio_entidades_locales"))
claim("paper.md", f"{H['not_entity_site']} municipal URLs were excluded ({wd} from Wikidata, {clm} from the Castilla-La Mancha directory)")
sc = S["site_check_reachable_municipal"]
claim("paper.md", f"Of the {n(mr['k'])} municipal home pages kept, {n(sc['name_on_page'])} show the municipality's name, {sc['council_words_and_url']} show council wording and carry the name in their URL, and {sc['unverified']} could not be confirmed")
claim("paper.md", f"{wd} of its {n(S['municipal_urls_by_source']['wikidata_P856'])} municipal URLs (and {clm} of the {S['municipal_urls_by_source']['clm_directorio_entidades_locales']} from the Castilla-La Mancha directory)")
claim("paper.md", f"and {S['dns_failure_by_source']['wikidata_P856']} (and {S['dns_failure_by_source']['clm_directorio_entidades_locales']} of the directory's) to domains")
claim("paper.md", f"{sc['unverified']} reachable municipal home pages could not be confirmed")

# --- robots.txt audit and deletions
rd = S["robots_discarded_entities"]
both(f"fetched the home page of {rd['home_disallowed']} entities")
both(f"or the statement of another {S['robots_entities_home_allowed_other_disallowed']}")
claim("paper.md", f"**{rd['home_and_all']} entities lost their whole record**")
claim("paper.md", f"{rd['home_disallowed']} whose `robots.txt` did not allow the home page or a redirect hop of it — {S['robots_discarded_html_typed']['n']} of them")
assert S["robots_discarded_html_typed"]["by_province"] == {"Castelló/Castellón": S["robots_discarded_html_typed"]["n"]}
claim("paper.md", f"and {rd['home_unverifiable']} whose `robots.txt` could not be re-read to verify")
claim("paper.md", f"`security.txt` ({rd['sectxt_only']}), `llms.txt` ({rd['llms_only']}), the statement ({rd['stmt_only']})")
claim("paper.md", f"In all, {S['robots_entities_any_request_disallowed']} entities had at least one request that their `robots.txt` did not allow, and {S['robots_entities_any_request_discarded']} had at least one record discarded")
claim("paper.md", f"{rd['sectxt_pass2']} of those fetches were not allowed")
assert H["robots_disallow"] - rd["home_disallowed"] >= 0
claim("paper.md", f"({n(H['robots_disallow'])}, of which {rd['home_disallowed']} are the records deleted")

# --- robots.txt re-read and re-checks (data/build_meta.json, written by build_records.py)
B = S["build_meta"]
claim("paper.md", f"we re-read the `robots.txt` of all {n(B['robots_hosts_reread'])} hosts the scan or the pilot had sent a request to")
claim("paper.md", f"For the {n(B['robotparser_vs_rfc9309']['entities'])} entities whose `robots.txt` the scan had read as plain text")
claim("paper.md", f"agree on all four headline tokens for {n(B['robotparser_vs_rfc9309']['agree_on_4_tokens'])}")
claim("paper.md", f"{n(B['recheck_home'])} home pages were fetched again")
claim("paper.md", f"{B['recheck_statements']} statements whose first-version date")
claim("paper.md", f"fetched again on the {B['recheck_sectxt_hosts']} hosts where the scan had found a file")
claim("paper.md", f"for the {n(B['recheck_home_municipal'])} municipal home pages whose identity")
claim("paper.md", f"({'§'}5.4; {B['recheck_home_municipal_answered']} of them answered)")
claim("paper.md", f"{S['other_body_page_by_province']['Salamanca']} of them domains of small municipalities in Salamanca")
claim("README.md", "")

# --- date extractor
v = S["v1_recheck"]
claim("paper.md", f"{v['confirmed']} of {v['v1_dated_with_sentence']} v1 dates were confirmed and {v['rejected']} rejected ({P(v['rejected'], v['v1_dated_with_sentence'])}%)")
claim("paper.md", f"Those {v['rejected_reread']} statements were then read again in full with v2 the same evening: {v['rejected_reread_dated']} do show a v2 date")
au = S["date_audit_v2"]
assert au["k"] == au["n"] == 40 and au["unjudged"] == 0
claim("paper.md", f"All {au['n']} dates are a preparation, review or update date")
claim("paper.md", f"(95% CI for precision {p(au['ci95'][0])}–{p(au['ci95'][1])})")

# --- README headline table
rows = {"reachable": "home page reachable (of measured)", "https": "served over HTTPS (of reachable)",
        "hsts": "HSTS (of served over HTTPS)", "acc_link": "link to accessibility statement (of reachable)",
        "ai_block_any4": "blocks ≥ 1 of 4 AI crawlers (of robots.txt read)"}
order = ("municipality", "provincial_council", "public_university", "regional_government", "ministry")
for k, lab in rows.items():
    cells = [f"{p(T[t][k]['pct'])}% of {n(T[t][k]['n'])}" for t in order]
    claim("README.md", f"| {lab} | " + " | ".join(cells) + " |")
claim("README.md", "| security.txt with the required fields (entities) | " +
      " | ".join(str(T[t]["sectxt_required_ok"]["k"]) for t in order) + " |")
claim("README.md", "| security.txt strictly valid (entities) | " +
      " | ".join(str(T[t]["sectxt_strict_ok"]["k"]) for t in order) + " |")

# --- run
claims = [(d, t) for d, t in claims if d in DOCS]
missing = [(d, t) for d, t in claims if t and re.sub(r"\s+", " ", t) not in DOCS[d]]
for d, t in missing:
    print(f"MISSING in {d}: {t}")
checked = sum(1 for _, t in claims if t)
print(f"{checked - len(missing)} of {checked} quoted figures match data/summary.json")
sys.exit(1 if missing else 0)
