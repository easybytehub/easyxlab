# S8 — Method

*EasyxLab · study S8 · data collected 2026-10-02 · status: working draft, not peer-reviewed*

This file says exactly what was measured, how, what went wrong, and what the scanner refuses
to do. The numbers are in [the paper](https://easybyte.es/lab/studies/s8/paper/) and `data/`.

## 1. Population and where the URLs come from

| entity type | n | list of entities | website URL |
|---|---|---|---|
| municipality (*ayuntamiento*) | 8,132 | Registro de Entidades Locales (REL), Ministerio de Política Territorial, Excel export of all municipalities, downloaded 2026-10-02 | see below |
| regional government (17 autonomous communities + Ceuta + Melilla) | 19 | curated | curated |
| provincial council (38 *diputaciones*, 3 *diputaciones forales*, 7 *cabildos*, 4 *consells insulars*) | 52 | curated | curated |
| public university | 50 | curated | curated |
| ministry (Government of Spain) | 22 | curated | curated |

**REL de-duplication.** The REL export has 8,134 municipal rows but two municipalities appear
twice (Alhama de Granada, INE 18013, and Soba, INE 39083: same inscription number, rows that
differ only in the ANOTACION text). `build_population.py` keeps the first row of each INE code.
The 8,132 codes that remain are exactly those of INE's *Relación de municipios y códigos por
comunidades autónomas y provincias a 1 de enero de 2026*
(https://www.ine.es/daco/daco42/codmun/diccionario26.xlsx; 8,132 code rows), which
`build_population.py` checks when the file has been downloaded.

**Municipal URLs.** There is no official national file that lists the website of each
municipality. We looked for one and document what we found:

- **REL**: complete list with population, province and region; no website field. Its
  inscription number embeds the INE code (digits 3–7), which is what we join on.
- **DIR3** (Directorio Común): the download page `administracionelectronica.gob.es/ctt/dir3/descargas`
  rejected our requests (WAF, "The requested URL was rejected"); the DIR3 dataset record on
  datos.gob.es lists no file distribution.
- **BDGEL** (Ministerio de Hacienda): the entity listing is available as JSON per province, but
  the entity page we inspected shows no website.
- **Castilla y León** open data (`registro-de-municipios-de-castilla-y-leon`): no website field.
- **Castilla-La Mancha** open data, *Directorio de Entidades Locales* (June 2025 CSV, CC BY 4.0,
  "Fuente de datos: Junta de Comunidades de Castilla-La Mancha"): has a `WEB` field. Used. The
  file also carries mayors' names, phones and e-mails. `csv.DictReader` reads every column into
  memory, but only the municipality, province, EATIM flag and `WEB` columns are used; nothing
  else is written or published, and the raw file stays in the git-ignored `data/raw/`.
- **Wikidata**: every item with an INE municipality code (P772), with all non-deprecated
  official-website (P856) statements and without a dissolution date (P576). Querying by the
  code rather than by class avoids the class problem that hides some cities (e.g. Barcelona).

Precedence: URL override (1 case, written by the agent: Bilbao, whose only P856 value was the
tourism site) > Castilla-La Mancha directory > Wikidata. Among several Wikidata values we prefer
the preferred-rank one, then one that does not look like a tourism site, then a host that looks
like a council (`ayto`, `ajuntament`, `concello`, `udala`, …). If every value looks like a
tourism site the URL is dropped (3 municipalities).

**Curated lists.** Regional governments, provincial councils, public universities and
ministries are small, well-known sets; their main websites were written by the agent from
general knowledge and are checked by the scan itself (a dead or wrong URL shows up as not
reachable). They are in `data/other_entities.csv`. The November 2023 ministerial structure is
used.

**Ceuta and Melilla** are in the REL as municipalities (INE 51001, 52001) and in the curated
list as autonomous cities (CCAA18, CCAA19), with one website each. They are counted once, as
regional governments; the municipal rows are labelled `same_as_regional_entry` and left out of
every scan figure (they remain in the coverage figures).

**What is not covered.** Municipalities with no URL in any source (most of them tiny, see
`data/coverage.csv`); municipal companies and autonomous bodies; *sedes electrónicas* as such
(we test the council's main website, and only reach the *sede* when the accessibility link
goes there); regional ministries and agencies; EATIMs, *mancomunidades* and *comarcas*.

## 2. The scan of 2026-10-02 (scanner version 1)

The published measurement was taken by the first version of `scripts/scan.py`, between
19:08:05 and 19:18:35 UTC (main pass) and 19:18:51–19:19:51 UTC (second pass, see below), from
one Spanish residential IP, with Python 3.14.4 and OpenSSL 3.6.2.
User-Agent: `EasyByteLab-research/0.1 (contact: contact@easybyte.es)`; product token for
`robots.txt`: `EasyByteLab-research`. Timeout 15 s. Redirects (up to 5) followed by the scanner
itself, not by `urllib`. 48 hosts in parallel for the first 586 entities, 96 afterwards.

Per entity, in this order:

1. `http://<host>/robots.txt` (plain HTTP on purpose: whether the server upgrades to HTTPS is
   read from this redirect). If the plain-HTTP connection failed, `https://` was tried.
2. The home page, `https://<host><path>`; plain HTTP only if HTTPS failed. Not fetched if the
   `robots.txt` read in step 1 forbade it for our token, or answered 5xx or did not answer.
3. `https://<final host>/.well-known/security.txt`, where *final host* is the host the home
   page redirected to.
4. Either the accessibility statement (the page the home page links to) or `/llms.txt`. A
   deterministic 1-in-5 split by host (SHA-256 of the host name) put hosts in **arm L**, which
   always spent this fetch on `/llms.txt`; the rest (**arm S**) fetched the statement when there
   was an on-host link and `/llms.txt` otherwise. A statement on another host (often the *sede
   electrónica*) cost that other host two fetches (its `robots.txt` and the page) and was
   fetched in both arms. `llms.txt` prevalence is reported on arm L only, where the choice did
   not depend on the site.

A second pass (`--sec-only`, 674 entities, 672 of them fetched) requested only `security.txt`
for entities whose home page had not been fetched (`robots.txt` forbade it, or the host budget
was spent).

**Fetch budget, as designed:** at most four resource fetches per host over the whole run (a
global counter; the first redirect hop into another host consumes one of that host's fetches),
and at most one request per second per host, redirect hops included. **Exceptions found
afterwards:**

- The home-page fallback from HTTPS to HTTP after a non-timeout error, and the `robots.txt`
  fallback from HTTP to HTTPS after a timeout, were not counted against the budget.
- After a certificate error the request was repeated without verification; the TLS handshake
  had failed before any HTTP request was sent, but the repeat was not paced.
- The counter lives in memory and restarted with the two scanner restarts (after 586 and 3,299
  entities); a host shared by finished and unfinished entities could receive more than four
  fetches over the whole run. The busiest host of the third run received 16 HTTP requests
  including redirect hops (`private/scan3.log`); the first two runs were stopped before printing
  their counters.
- Before the run the scanner was tested on 21 entities (Madrid, Málaga, Barcelona, Bilbao, a
  few small municipalities, two regional governments, two universities, two ministries, two
  provincial councils), so those hosts received up to four more fetches that day. The test
  records were deleted.
- The earlier pilot (`pilot/`) made up to five requests to each of its 25 hosts, with the
  User-Agent `Mozilla/5.0 (compatible; easybyte-lab-pilot/0.1; +https://github.com/easybytehub/easybyte-lab)`,
  and did not read `robots.txt` before fetching the home page, `security.txt` and `llms.txt`.

**robots.txt, as designed and as it was.** The scanner was meant to honour `robots.txt` for
every page. It did not: (a) a `robots.txt` that answered 200 with an HTML Content-Type was
treated as absent ("soft 404"), so its rules were ignored; (b) `/.well-known/security.txt` was
never checked against `robots.txt` — the code and an earlier draft justified this by saying RFC
9116 exempts the file, which it does not (RFC 9116 does not mention `robots.txt`; RFC 9309
§2.2.2 exempts only "/robots.txt" itself); (c) the `robots.txt` of hosts reached by a redirect
was never read, and `llms.txt` on such a host was fetched unchecked; (d) Python's
`urllib.robotparser` matches rules in file order rather than by the longest match, does not
expand `*` or `$`, and uses only the first of several `User-agent: *` groups; (e) a 2xx answer
other than 200 (e.g. a 202 bot challenge) to `robots.txt` was treated as "no restrictions".
Section 6 describes how every record obtained against `robots.txt` was found and deleted.

TLS certificate errors happen in the handshake; the scanner recorded `https_cert_ok = false`
and repeated the request without verification so that the other checks could still run.
Verification uses Python's `ssl` default context (OpenSSL with the Mozilla root store, no AIA
fetching): a server that does not send its intermediate certificate fails here even if a
browser would repair the chain.

## 3. Checks

### 3.1 HTTPS and HSTS
- `https`: the home page was finally served over HTTPS. The scanner asks for `https://` first,
  so this says the site answers over HTTPS when asked, not that visitors are redirected to it.
- `https_cert_ok`: and the certificate chain verified (see caveat above).
- `http_upgrades`: `http://<host>/robots.txt` ended on an `https://` URL (a proxy for an
  HTTP-to-HTTPS redirect, measured on that one request).
- `hsts`: the HTTPS home-page response carries `Strict-Transport-Security` with `max-age > 0`;
  `hsts_1y`: `max-age >= 31536000`; `hsts_valid_chain`: `hsts` on a connection whose certificate
  verified (RFC 6797 §8.1: a browser notes an HSTS host only if "there are no underlying secure
  transport errors or warnings").

### 3.2 security.txt (RFC 9116)
A response counts as a **file** if `/.well-known/security.txt` returns 200 and has at least one
`Contact:` or `Expires:` line; a 200 without either (an HTML page, or a text without any field)
is a **soft 404**. For files we report two levels:

- **`sectxt_required_ok` — has the required fields.** Served over HTTPS; at least one `Contact`
  field; exactly one `Expires` field; its value parses as a date-time (`YYYY-MM-DDThh:mm[:ss]`
  with an offset or `Z`, `T` and `Z` in either case) that is not in the past. RFC 9116: "This
  field MUST always be present in a "security.txt" file" (§2.5.3, Contact); "This field MUST
  always be present and MUST NOT appear more than once" (§2.5.5, Expires), whose value marks
  the date "after which the data contained in the "security.txt" file is considered stale and
  should not be used"; "the file access MUST use the "https" scheme" (§3).
- **`sectxt_strict_ok` — strictly valid.** The above, plus every RFC 9116 requirement the
  scanner can test: "It MUST have a Content-Type of "text/plain" with the default charset
  parameter set to "utf-8"" (§3) — media type `text/plain` and a `charset=utf-8` parameter;
  every `Contact` value is a URI ("The value MUST follow the URI syntax described in Section 3
  of [RFC3986]. This means that "mailto" and "tel" URI schemes must be used when specifying
  email addresses and telephone numbers", §2.5.3) — tested as `scheme:rest` with no spaces;
  no `Contact`, `Encryption`, `Acknowledgments`, `Canonical`, `Policy` or `Hiring` value starts
  with `http:` ("If this field indicates a web URI, then it MUST begin with "https://"");
  `Expires` is an RFC 3339 date-time (seconds required, offset with a colon); `Preferred-Languages`
  appears at most once (§2.5.8); every non-empty line outside an OpenPGP armour is a comment or a
  `name: value` field (§4); the body decodes as UTF-8 (§4). **Not tested:** OpenPGP signatures,
  `Canonical` consistency (a SHOULD), the full ABNF of each value.

Both levels were applied to the re-fetch of each file on the evening of 2026-10-02 (§6), since
the first scan did not store whether every `Contact` was a URI. **The Contact values are never
stored**: only booleans.

### 3.3 Accessibility statement (RD 1112/2018, art. 15)
- `acc_link`: the static HTML of the home page has an `<a href>` whose short text (≤ 60 chars,
  including `title` and image `alt`) mentions *accesibilidad* / *accessibilitat* /
  *accesibilidade* / *irisgarritasun* / *accessibility*, or whose `href` does. Ignored: links to
  W3C, TAW or WebAIM badges; links to accessibility widget or plug-in vendors
  (accessibility-helper.co.il, dj-extensions.com, pluginsmarket.com, inclusite.com, userway.org,
  accessibe.com, equalweb.com, …); links whose label is a credit ("Accessibility by …",
  "powered by", "plugin"). The first version did not ignore vendors and credits; the 67 home
  pages where it had picked such a link were re-fetched and the link re-detected (§6). Links
  injected by JavaScript are not seen. This is neither a lower nor an upper bound.
- `stmt_ok`: the linked page returns 200. PDFs and other non-HTML documents count for existence
  only. `stmt_about_accessibility`: the HTML page mentions accessibility and statement wording
  ("declaración", "declaració d'accessibilitat", "irisgarritasun-adierazpen", "1112/2018", …).
- `stmt_has_date` (extractor v2): the page contains a date within 160 characters after one of
  these words (regular expression `DATE_CONTEXT` in `scan.py`): *preparada/o*, *preparat*,
  *preparación*, *preparació*, *preparou*, *revisada/o*, *revisió*, *revisión*, *revisou*,
  *elaborada/o*, *elaboració*, *elaboración*, *actualizada/o*, *actualitzada*, *berrikus…*,
  *eguneratu*, *prestatu*, *egin zen*, *prepared*, *reviewed*, *updated on* — unless the 80
  characters around the word match "darrera actualització:", "data i hora oficials" or "última
  actualización: <digit>" (page-edit footers and clocks). Dates before 2018-09-01 or after the
  scan date are ignored. Numeric (`dd/mm/yyyy`, `yyyy-mm-dd`) and written (`15 de octubre de
  2025`, Basque `2025eko urriaren 15`) forms are read. The latest such date is kept, with the
  sentence it came from.
- `stmt_fresh_1y`: that date is no more than 365 days before 2026-10-02. Article 15.1 says the
  statement "será actualizada periódicamente, como mínimo una vez al año"; it does not require
  the date to be shown, so a missing or old date is not proof of non-compliance.
- **Date figures** (`stmt_dates_statements`) use HTML statement pages (200, statement wording)
  read by the audited extractor: v2 itself, or a v1 reading that v2 confirmed on its stored
  sentence, or a v1 page with no date (v1's keywords include all of v2's, so no v1 date means no
  v2 date), or a v1 date rejected by v2 and then re-read in full with v2 (§6). Excluded: every
  statement of the first 586 entities scanned (`date_method = v1_first_run`, dated or not), PDFs,
  and pages without statement wording (reported separately as `*_all_pages`).
- Not judged: whether the statement is truthful, complete, or follows the model; whether the
  site is accessible.

### 3.4 AI crawlers and llms.txt
From the re-read of `robots.txt` of 2026-10-02 evening (§6), parsed with `scripts/robots9309.py`
(RFC 9309: groups for a token merged, most specific match wins, allow wins ties, `*` and `$`
supported, rules outside groups ignored, the body parsed whatever its Content-Type). For 14
tokens (headline four: GPTBot, ClaudeBot, Google-Extended, CCBot; plus anthropic-ai,
Applebot-Extended, Bytespider, meta-externalagent, cohere-ai, OAI-SearchBot, ChatGPT-User,
PerplexityBot, Claude-SearchBot, Claude-User) we record whether `/` is disallowed (`blocked`)
and whether the token is named in a `User-agent` line (`named`). `robots_star_disallows_root`:
the `User-agent: *` group disallows `/`, which affects every crawler not named in the file;
named crawlers (often Googlebot and Bingbot) may still be allowed. A 4xx `robots.txt` means no
restrictions (RFC 9309 §2.3.1.3). `llms.txt` is present if `/llms.txt` returns 200, is not
HTML, is non-empty and starts with a Markdown H1 (`# `).

### 3.5 Is the URL the entity's website? (`site_check`, `data/exclusions.csv`)
Applied to every home page that answered 200 with HTML, in this order; the first rule that
matches excludes the URL (`home_outcome = not_entity_site`, not reachable, no indicators except
coverage):

1. **third_party_platform** — the registrable domain of the URL, of the scan's final URL or of
   the re-fetch's final URL is youtube.com, youtu.be, facebook.com, fb.com, instagram.com,
   twitter.com, x.com, tiktok.com, linkedin.com, wikipedia.org, wikimedia.org, yahoo.com or
   google.com.
2. **domain_for_sale** — that domain is a marketplace (hugedomains.com, dropcatch.com,
   nicsell.com, sedo.com, dan.com, afternic.com, godaddy.com, atom.com, brandbucket.com, …), or
   the page or its title matches a parking pattern ("domain is for sale", "dominio en venta",
   "dominio en reserva", "domain expired", "parked domain", …; `PARKING` in `scan.py`).
3. **directory_site** — codigopostales.com and similar postcode or place directories.
4. **hosting_panel_or_default_page** — the final URL's path is `/login_up.php` (Plesk) or a
   cPanel default path, or a control-panel port; or the title or first lines match a panel or
   server default page ("Plesk", "cPanel", "Index of /", "Domain Default page", "Web Server's
   Default Page", "IIS Windows Server", "Welcome to nginx", "sitio en construcción", …) or the
   title is a placeholder ("Coming Soon", "Site is created successfully", "Próximamente", …).
   Ports are ignored when comparing hosts (`https://vigo.gal:443/` is `vigo.gal`).
5. **other_site_after_redirect** (municipalities) — no form of the municipality's name on the
   page (§3.6), and the final registrable domain differs from the URL's and carries no form of
   the name either.
6. **other_body_page** (municipalities) — the re-fetched page's title names the council of
   another municipality in the REL ("Ayuntamiento de Alba de Tormes" on `fresnedoso.es`); or the
   page has council wording but neither it nor its URL names this municipality.
7. **no_sign_of_council** (municipalities) — the re-fetched page has visible text (it is not a
   near-empty JavaScript page) and a title, but neither any form of the name nor any council
   wording (*ayuntamiento, ajuntament, concello, udala, alcalde, sede electrónica, municipio,
   council, …*; `COUNCIL` in `scan.py`).

Pages with no form of the name that none of these rules excludes (mostly near-empty JavaScript
pages, or pages the re-fetch could not reach) are kept and labelled `unverified`.

### 3.6 The municipality's name on a page
`home_name_match` (scan): the normalised name (accents removed; "Solana, La" → "la solana";
bilingual names split on "/") appears in the page text. The first version did not decode HTML
entities (`&Aacute;vila`), which made it miss accented names; the re-fetch decodes them. For the
rules above we also accept a **name run**: any sequence of consecutive words of the name, at
least 5 letters long once spaces are removed, that does not start or end with an article or
preposition and is not made only of generic place words (*villa, santa, torre, fuente, …*) or
region and province names; the whole name always counts. A run counts in the page text, the
title or the URL (host and path, letters only).

## 4. Outcome of the home page (`home_outcome`)
`ok` · `dns_failure` (the domain does not resolve) · `connection_failure` (no answer) ·
`forbidden` (401, 403, 429) · `http_202` (202 with no usable content, typically a bot
challenge; the body was not inspected) · `http_error` (other status) · `robots_5xx`
(`robots.txt` answered 5xx, so we did not crawl) · `robots_disallow` (*not measurable:
robots.txt disallows*: the scan did not fetch the home page because `robots.txt` forbade it,
or fetched it against `robots.txt` and the record was deleted, §6; `ra_home = disallowed`
tells them apart) · `robots_unverifiable` (the home page was fetched, the `robots.txt` could not
be re-read to verify that it allowed it, and the record was deleted) · `robots_unreachable`
(e.g. an unresolved 3xx to `robots.txt`) · `too_many_redirects` (a redirect loop; all 86 cases
are on one *sede electrónica* platform that loops without cookies) · `not_entity_site` (§3.5)
· `200_not_html` · `not_measured_budget` (the scanner's own budget prevented the fetch: a
redirect into a host with no fetches left) · `same_as_regional_entry` (Ceuta, Melilla).

## 5. Denominators
- reachability: scanned entities, minus `not_measured_budget` and `same_as_regional_entry`;
- served over HTTPS, accessibility link: entities whose home page returned 200 HTML and is the
  entity's site (*reachable*); `acc_link` also minus pages where it could not be re-detected;
- certificate, HSTS: reachable entities served over HTTPS;
- HTTP → HTTPS: reachable entities whose plain-HTTP `robots.txt` request got an answer;
- AI crawler indicators: entities whose re-read `robots.txt` answered (a file, or a 4xx), minus
  `not_entity_site` and `same_as_regional_entry`;
- security.txt: entities for which `/.well-known/security.txt` was requested, the request was
  allowed by `robots.txt`, and the server answered with a status code, minus `not_entity_site`;
- statement dates: see §3.3;
- `llms.txt`: reachable entities in arm L whose `/llms.txt` request got a status code.

Entities that share a host (some small municipalities on a provincial platform) share the
host-level results (`robots.txt`, `security.txt`, `llms.txt`). In the CSV tables a percentage is
left blank when its denominator is under 10.

## 6. The correction of 2026-10-02 (evening)

An adversarial review by a second AI agent ([the paper](https://easybyte.es/lab/studies/s8/paper/) §11) found the `robots.txt` failures of
§2 and other errors. The corrections were made the same evening with
`scripts/recheck.py`, which uses the Session of scanner version 2 (§7): `robots.txt` read before
any request to a host and honoured for every request and every redirect hop; at most four
resource fetches per host over all the correction's requests together, `robots.txt` included
(counters kept in `data/raw/recheck_budget.json` across the phases); at most one request per
second per host. User-Agent: `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`.

1. **robots.txt re-read** (21:45–21:58 UTC): every host the first scan or the pilot had sent a
   request to — 8,055 hosts. 131 hosts that had answered 202 were read again once the parser
   accepted any 2xx, and 66 that had failed (timeouts, refused connections, 5xx) were tried
   once more. The re-read can count as a
   statement of the rules in force at 19:08–19:20 UTC only approximately; RFC 9309 §2.4 lets a
   crawler use a cached copy for up to 24 hours.
2. **Audit of every recorded request** (`scripts/audit_robots.py`), for the token the first scan
   sent (`EasyByteLab-research`). For the entity's own host: if the first scan had seen a 5xx, a
   network error or an unresolved redirect, any request other than `robots.txt` was disallowed
   (RFC 9309 §2.3.1.4: "the crawler MUST assume complete disallow"); if it had seen a 4xx, all
   were allowed; if it had seen a 2xx, the re-read file decides. For any other host (redirect
   targets, statements on another host, `security.txt` and `llms.txt` on the final host) the
   re-read decides. Requests checked: the home page (requested URL and final URL), `security.txt`
   (both passes), the statement, `llms.txt`. Intermediate redirect hops were not recorded and
   could not be checked. Decision `allowed`, `disallowed` or `unverifiable` (the re-read failed,
   or gave a 4xx where the scan had seen a file); anything not `allowed` was discarded.
3. **Deletion** (`build_records.py --purge-raw`): a discarded home page takes with it every
   field derived from it (HTTPS, HSTS, link, statement, `security.txt`, `llms.txt`); a discarded
   single request takes its own fields. The raw scan files were rewritten without them, the
   21-entity test records were deleted, and `pilot/muni_res.json` lost what the pilot had
   fetched against `robots.txt` (home page, `security.txt` and `llms.txt` of www.murcia.es;
   `security.txt` and `llms.txt` of www.laspalmasgc.es). Result: 168 entities without any
   measurement except `robots.txt` (123 disallowed, of which 100 in the province of
   Castelló/Castellón behind a `robots.txt` served as `text/html`; 45 unverifiable); 845
   entities had at least one request disallowed. Counts in `data/summary.json`
   (`robots_*`).
4. **Re-checks**, each only where `robots.txt` allowed it and never for a discarded entity:
   home pages of 758 entities (`recheck_home.jsonl`: page markers, a short title kept privately,
   name evidence, the accessibility link) where the name was not found, the page was near-empty,
   the domain had changed, the path was a panel's, or the first detector had picked a widget
   link — 55 of them were looked at a second time with compressed bodies decoded; the 116
   statements whose v1 date v2 rejected on its sentence, read in full with v2; `security.txt` on
   the 360 hosts where the scan had found a file or a soft 404.
5. **Budget exception.** One host (calanda.es) received a fifth request in the correction: the
   agent fetched it with an ad hoc command, outside the budgeted session, to diagnose a
   compressed body after the budget counter had reached four. No other host received more than four resource fetches in
   the correction; the busiest host received 22 HTTP requests including redirect hops in the
   `robots.txt` phase (several municipal domains whose `robots.txt` redirects into one provincial
   platform).
6. **One fetch against robots.txt outside the scan.** While searching for prior work
   ([the paper](https://easybyte.es/lab/studies/s8/paper/) §2), the agent followed a link from the European Commission's site to a news page
   of administracionelectronica.gob.es whose URL carried `?idioma=es`, a pattern that site's
   `robots.txt` disallows (`Disallow: /*?idioma=`). The page was deleted and not used; every later
   fetch for the prior-work search was checked against the site's `robots.txt` first.

## 7. Scanner version 2 (`scripts/scan.py` as published)

Not used for the published measurement; used for the re-checks. Differences from version 1:
`robots.txt` checked before every request, redirect hops included, on the host each request
goes to, parsed with `robots9309.py` whatever the Content-Type; any 2xx to `robots.txt` is a
successful download; a 5xx, network error, unresolved redirect or spent budget means complete
disallow; `security.txt` is subject to `robots.txt` like everything else and is tried on the
entity's host when the home page is not allowed (there is no separate second pass); fallbacks
are reserved against the budget and certificate retries are paced; budget, pacing and
`robots.txt` are per host and port, with default ports removed; gzip or deflate bodies sent
without being asked are decoded; the accessibility-link detector ignores widget vendors and
credit links; the security.txt check records the strict fields of §3.2; the home page records
title-based markers for §3.5 and decodes HTML entities in the name check; the near-empty test
uses visible text (under 400 characters) instead of HTML size; the User-Agent must be given
(`--user-agent` or `S8_USER_AGENT`) and should identify whoever runs it. The date extractor is
unchanged (v2).

## 8. Privacy and ethics
- No response body is published. Published: status codes, booleans, public URLs, the extracted
  statement date and the short public sentence it came from (e-mail addresses and phone numbers
  masked). Page titles from the re-checks are kept only in the git-ignored `data/raw/`.
- From `security.txt`, no Contact value (e-mail, phone or URL) is kept.
- `robots.txt` re-reads are stored as parsed rules (user agents and paths), without comments.
- Naming entities: all are public bodies, all tested pages are public, and every indicator is a
  machine-checkable fact about a legal or technical standard. The tables carry no ranking.
- Data obtained against a site's `robots.txt` were deleted (§6), not used.
- No administration was contacted. Nothing was submitted to any form.

## 9. Reproducing

```bash
./run.sh                                     # rebuild data/ from the records, check the figures
S8_USER_AGENT="Name/1.0 (+URL)" ./run.sh --new-measurement   # a new scan with scanner v2
```

Without arguments, `run.sh` builds `data/records.jsonl.gz` from `data/raw/` when the raw files
are present (EasyxLab's working copy), runs `aggregate.py` and `check_numbers.py`. Anyone else
starts from the published `data/records.jsonl.gz`. `--new-measurement` downloads the sources
again, rebuilds the population and scans with version 2; it is a new measurement (websites
change, Wikidata changes daily), and its figures will not match [the paper](https://easybyte.es/lab/studies/s8/paper/). Python ≥ 3.10;
`xlrd` and `openpyxl` only to read the REL and INE spreadsheets. The published run used
Python 3.14.4 and OpenSSL 3.6.2; `ssl` defaults differ across versions.
