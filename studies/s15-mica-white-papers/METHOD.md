# S15 — Method

*EasyxLab · study S15 · rules frozen 2026-10-03 before the main collection (sha256 and time in the study's private status file); later changes are listed under "Deviations" at the end.*

## 1. Question

Of the crypto-asset white papers in ESMA's interim MiCA register that were notified or updated since
23 December 2025 (the date from which Commission Implementing Regulation (EU) 2024/2984 applies), how many are
available, at the URL the register lists, as an Inline XBRL XHTML file using ESMA's MiCA taxonomy? How many of those
validate against the taxonomy, and do their LEI and DTI match the register and GLEIF?

The study measures **availability of the machine-readable version at the registered URL**. It does not measure what
was notified to the national competent authority (NCA), which is not public, and it does not claim that a missing
file is a breach: see [the paper](https://easybyte.es/lab/studies/s15/paper/) §3 for what the law and ESMA's Q&As say.

## 2. Population and inputs (pinned)

| input | source | pin |
|---|---|---|
| Register, Title II (`OTHER.csv`) | `https://www.esma.europa.eu/sites/default/files/2024-12/OTHER.csv`, page states "Last update: 30 September 2026", downloaded 2026-10-03 | sha256 in `data/sources.csv` |
| Register, Title IV (`EMTWP.csv`), Title III (`ARTZZ.csv`) | same folder, same date | idem |
| Register at 23-12-2025 | Wayback Machine capture `20251223101326` of `OTHER.csv` (raw `id_` capture) | idem |
| ESMA MiCA taxonomy 2025 | `https://www.esma.europa.eu/sites/default/files/2025-08/mica_taxonomy_2025.zip` | sha256 `19921398b16cb2521f808965e5d058be8f68591c8f9d77d24eb9df2c14aae033` |
| Validator | Arelle (`arelle-release` 2.46.0, PyPI) in the study virtualenv, offline, with the package above | |
| LEI reference data | GLEIF API `https://api.gleif.org/api/v1/lei-records/<LEI>` (CC0) | queried on the collection date |

Raw register files, snapshots, the taxonomy package and every downloaded document stay in `data/raw/` or `work/`
(never published). ESMA's notice allows reproduction with acknowledgement; we nevertheless publish only derived,
per-row classifications, not the register.

## 3. Cohort (frozen rule)

1. **Rows.** Every row of `OTHER.csv` and `EMTWP.csv` as downloaded on 2026-10-03 (`ARTZZ.csv` has no rows). EMT rows
   whose `wp_url` is a placeholder (`EMT_NO_WP`, `EMT_CRIN`) or empty have no white paper and are excluded.
2. **Cohort ("notified or updated since 23-12-2025").** Rows whose `wp_lastupdate` ("Last update of the record",
   `dd/mm/yyyy`) is on or after **23/12/2025**.
3. **Cross-check with the Wayback snapshot** (Title II only; there is no December capture of `EMTWP.csv`). A row's key
   is (`ae_lei`, `ae_lei_casp`, normalised `wp_url`), where normalisation lower-cases, strips the scheme, a leading
   `www.` and a trailing `/`. Each cohort row is labelled `new` (key absent from the 2025-12-23 capture) or `changed`
   (key present, `wp_lastupdate` different). Rows whose key is absent from the capture but whose `wp_lastupdate` is
   earlier than 23/12/2025 are **not** in the cohort (they are re-keyed older entries, typically URL edits); they are
   counted and reported.
4. **Cross-check with the document.** For files reached in the ESMA format, the tagged date of notification
   (`DateOfNotificationFor…WhitePaper`) is compared with 23-12-2025 and reported; it does not change membership.
5. **Context population.** All other rows of the register (any date) are processed with the same rules and reported
   separately, never mixed into the headline.
6. **Unit.** The register row. Several rows can share a URL; each URL is fetched once and its result applies to every
   row that lists it. Results are also reported per distinct URL.

## 4. Access rules (enforced in `scripts/fetch.py`)

- `robots.txt` of every host is read **before** the first other request to that host and honoured for the
  User-Agent `EasyxLab-research/0.1 (+https://easybyte.es/lab/; contact@easybyte.es)`. A 401/403 or 5xx on
  `robots.txt`, or a network error, makes the host not retrievable. Comments in `robots.txt` that forbid robots,
  scraping or text-and-data mining count as a reservation: the host is skipped. An HTML page served at `/robots.txt`
  is read for such a reservation and otherwise treated as no rules.
- At most 1 request per second per host; redirects are followed manually (≤ 5) and `robots.txt` is checked on every
  host of the chain.
- **Anti-bot walls** (Incapsula, Cloudflare challenge, DataDome, PerimeterX, Akamai denial page; detected by markers
  in the body) are a class of their own, *not retrievable*, and are never circumvented (no browser, no cookies, no
  retries with other headers).
- **At most one hop**: if the registered URL returns an HTML page, links from it (`<a href>`, `<iframe src>`,
  `<embed src>`, `<object data>`) are candidates when their path ends in `.xhtml`, `.xhtm`, `.pdf` or `.zip`, or the
  URL or anchor text contains `xbrl` or `xhtml`. Candidates are ranked: (1) the URL contains one of the row's DTI or
  DTI-FFG codes; (2) XHTML/XBRL-looking before PDF before ZIP; (3) document order. At most 3 XHTML-looking candidates
  and 1 PDF are fetched per registered URL. Links found inside those documents are not followed.
- Documents are streamed (cap 60 MB), hashed, classified and deleted. Only Inline XBRL files are kept on disk until
  validated, then deleted. No document is redistributed.

## 5. Classification (implemented in `scripts/mica_wp_check.py`)

**Document class** (from the bytes, not the file name):

| class | rule |
|---|---|
| `ixbrl-esma` | contains the Inline XBRL namespace (`http://www.xbrl.org/2013/inlineXBRL`) and an `ix:references`/`link:schemaRef` to an ESMA MiCA entry point `https://www.esma.europa.eu/taxonomy/mica/2025-03-31/mica_entry_table_{2,3,4}.xsd` |
| `ixbrl-other` | Inline XBRL namespace and a `schemaRef` to anything else |
| `xhtml-no-ixbrl` | no Inline XBRL; the file name ends in `.xhtml`/`.xhtm`, or it is served as `application/xhtml+xml`, or it is well-formed XML with an XHTML root and an XML declaration |
| `pdf` | starts with `%PDF-` |
| `zip-other` | a ZIP archive |
| `html` | any other HTML page (a landing page, a web rendering of the white paper, a home page) |
| `other` / `empty` | anything else / no body |

**Row outcome** = the best document reached from the registered URL directly or in one hop, in this order:
`ixbrl-esma` > `ixbrl-other` > `xhtml-no-ixbrl` > `pdf` > `zip-other` > `html` > `other`/`empty`; or, when nothing
could be read: `anti-bot`, `robots` (disallowed or reserved), `http-error` (status ≥ 400), `net-error` (DNS, TLS,
timeout), `invalid-url` (the register field is not a URL).

**Attribution.** An `ixbrl-esma` file reached in one hop from a page that offers **more than one** `ixbrl-esma`
file counts for the row only if one of its LEI or DTI values equals the row's `ae_lei`, `ae_lei_casp`, `ae_DTI` or
`ae_DTI_FFG`; otherwise the row is `ixbrl-esma-unattributed` and does not count as available. A file at the
registered URL itself, or the only `ixbrl-esma` file one hop away, always counts.

**Headline "available"** = row outcome `ixbrl-esma` (after attribution).

**Valid** = Arelle loads the file with the pinned ESMA package, offline, with formula processing on
(`formulaAction=run`), and logs **zero** messages at level ERROR or above — XBRL 2.1, Inline XBRL 1.1, dimensions
and every unsatisfied ESMA assertion of error severity. Warnings are reported, not counted as invalid. The number of
assertions evaluated and the identifiers of failed assertions are recorded.

**Single XHTML file** (ITS Art. 2(1)(a)): the file is well-formed XML with an XHTML `html` root; recorded for every
`ixbrl-*` file.

**Identifiers.**
- *Document LEIs*: values of `OfferorsLegalEntityIdentifier`, `IssuersLegalEntityIdentifier`,
  `OperatorsLegalEntityIdentifier`, `EmoneyTokenIssuersLegalEntityIdentifier`,
  `AssetreferencedTokenIssuersLegalEntityIdentifier`, `OtherTokenServiceProviderIdentifier…`, plus context entity
  identifiers with the ISO 17442 scheme. *Document DTIs*: the `…DigitalTokenIdentifierCode` and
  `…FunctionallyFungibleGroupDigitalTokenIdentifier` facts, split on `|`, `,`, `;` and spaces.
- *LEI match*: the row's `ae_lei` is among the document LEIs. *DTI match*: the row's `ae_DTI` codes (split on `|`)
  intersect the document DTIs; *FFG match* likewise for `ae_DTI_FFG`. Rows without a DTI in the register are
  reported as "no DTI in register", not as mismatches.
- *GLEIF*: for the row's `ae_lei` and the document's offeror LEI, the GLEIF record's existence, `registration.status`
  and `entity.status`. A LEI that GLEIF does not know is reported as such.

**Producing host** = the host that served the `ixbrl-esma` file (after redirects), grouped by registrable domain
(last two labels; last three for `co.uk`-style second levels). It identifies who hosts the files, which may be a
service provider rather than the offeror.

## 6. Privacy and fairness

White papers name members of management bodies (Annex I). No personal name, e-mail or address is extracted,
stored or published. Results are reported per legal entity (offeror, CASP, producing host), worded neutrally and
dated: they describe what a request on 2026-10-03 returned, not a firm's compliance.

## 7. What is excluded and why

- What the NCA received (not public).
- Content checks of the white paper against Annex I beyond what ESMA's own assertions encode.
- Documents behind log-ins, anti-bot walls, `robots.txt` disallows or reservations, or more than one hop away.
- Title III (ART): the register lists none.

## Deviations

**D1 (2026-10-03T11:19:40Z, during the cohort collection, before any affected URL was re-fetched).** The frozen rule treated a
401/403 answer to `/robots.txt` as "not retrievable". After about 120 cohort URLs, 24 requests had been skipped this
way, and the bodies show why: most come from object stores and CDNs (Amazon S3, DigitalOcean Spaces, Webflow and
Framer asset hosts, GitBook file hosts) that answer `AccessDenied` for any absent object, `/robots.txt` included. They
publish no robots policy at all. RFC 9309 §2.3.1.3 says that when `robots.txt` is "unavailable" (any 4xx status),
"the crawler MAY access any resources on the server". From D1 on, a 4xx (including 401/403) on `/robots.txt` means no
rules, as in RFC 9309; a 5xx or a network error still means "do not crawl", and every other rule (anti-bot walls,
reservations in comments, one hop, 1 request/second) is unchanged. URLs skipped under the old rule are re-fetched
once under D1 (`scripts/02b_refetch_4xx.py`). The headline uses D1; the figures under the frozen rule are kept and
reported next to it (`outcome_frozen_rule` in `data/rows.csv`).

**D2 (2026-10-03T11:30:07Z, labelling only).** When `/robots.txt` itself cannot be fetched (network error, TLS error, timeout or
5xx), the host was never read; such URLs are reported as `net-error` rather than `robots`, so that `robots`
means only "disallowed for our User-Agent, or reserved in a comment". No request or rule changes.

**D3 (2026-10-03T11:30:07Z, robustness).** A total time limit of 180 s per response body was added to the fetcher after one server
kept a connection open for more than a minute; such responses are `net-error`. It applies to the D1 re-fetch and to
the context collection; no cohort URL hit it before.

**D4 (2026-10-03T11:42:54Z, bug fix, no rule change).** The first validation batch (151 cohort files) ran with the Arelle model closed
before the facts were read, so the XBRL/assertion results were recorded but the identifiers (LEI, DTI, dates) were
not, and the files had already been deleted. Those files are downloaded again once, under the same access rules
(`scripts/03b_refetch_facts.py`); their sha256 is compared with the first download, and the identifiers are read
with Arelle (load only, same package). Files whose hash changed are flagged. "Valid" is computed as zero
ERROR-level messages with the ESMA assertions evaluated (assertions evaluated > 0), which is equivalent to "loaded"
for these files.

**D5 (2026-10-03T11:52:23Z, clarification, no change).** Redirects on `/robots.txt` (3xx) were followed from the start by the HTTP
client (up to 30 hops, more than the 5 of RFC 9309 §2.3.1.2), and the final response is the one parsed; a redirect
to an HTML page is read as described in §4. The log records the final status only.

**D6 (2026-10-03T11:52:23Z, reporting).** For 2 cohort rows the identifiers of the file could not be read (the D4 re-download
failed for one file); their LEI/DTI matches are reported as "not checked", not as mismatches, and they are left out
of the match denominators. For 9 rows the re-downloaded file had changed since the first download; their validation
result is from the first download and their identifiers from the second (column `identifiers_source` in
`data/documents.csv`).

## Frozen text

The text frozen at 2026-10-03 before the collection is everything above "Deviations" plus "(None at freeze time.)";
its sha256 (`33240471…330a`) is recorded with the time in the study's status file, and the byte-identical copy is
kept privately. The four scripts hashed at the freeze were changed afterwards only as described in D1–D6 and in
the refactoring of `02_collect.py` into `process_url()` (no behaviour change); their frozen hashes are therefore
self-attested.

## Deviations after the independent review (2026-10-03, afternoon)

The independent AI review (4 blockers) led to the following changes. The frozen sections above are unchanged.

**Access, as applied from this point (operator rule of 2026-10-03).** Hosts: `www.esma.europa.eu` (register CSVs,
taxonomy, Q&As; reuse authorised by ESMA with acknowledgement of the source), `publications.europa.eu` (legal texts),
`web.archive.org` (one capture of `OTHER.csv`), `api.gleif.org` (CC0), the 668 hosts serving white papers, and
search APIs for prior work. Access: HTTPS GET, User-Agent `EasyxLab-research/0.1 (+https://easybyte.es/lab/;
contact@easybyte.es)`, at most 1 request per second per host (or the host's `Crawl-delay`), no log-ins, no
circumvention of any access control, no personal data. On the hosts whose white papers we analyse, `robots.txt` is
honoured as RFC 9309 specifies. The six arXiv API queries of the prior-work search (whose `robots.txt` disallows
everything and is served as `text/html`) would have been excluded by our original, stricter protocol; they returned
nothing and are not redone.

**D7 (cohort parsing; review B1).** `wp_lastupdate` uses three forms: `dd/mm/yyyy` (1,057 rows), `dd.mm.yyyy` (13
Latvian rows) and empty (6). The first build parsed only the first form, so five rows dated after the cut-off
(OTHER lines 771–773, 775, 776) fell outside the cohort; all formats are now parsed. `OTHER.csv` repeats its header
line inside the file (lines 763 and 1027); these two lines are parsing artefacts and are dropped (Title II has
1,026 rows, not 1,028). The cohort is **440 rows (414 Title II, 26 e-money token)**. The five added rows had already
been fetched and classified in the context collection under the same rules, so no new request was needed. Of the
Title II rows absent from the 2025-12-23 capture and outside the cohort, 58 have an earlier date and 3 have none
(OTHER 1024–1026); EMTWP lines 7, 11 and 27 are undated as well. OTHER line 190 is dated 02/12/2026, after the
register's own last update (30-09-2026); it stays in the cohort and is flagged.

**D8 (robots.txt as RFC 9309 on document hosts; review B3).** The first fetcher parsed `robots.txt` with Python's
`urllib.robotparser` (no `*`/`$` wildcards, no longest match) and treated a `robots.txt` served as `text/html` as "no
rules". `fetch.py` now parses the body by syntax, whatever its Content-Type, with an RFC 9309 matcher
(`scripts/robots9309.py`), and honours `Crawl-delay`. We fetched `robots.txt` again for the 667 hosts of the
collection's 1,816 document requests and re-evaluated every request, including each step of redirect chains
(`scripts/02c_review_recheck.py`, phase A). 16 URLs are disallowed for our User-Agent; 10 of them had been requested
(the other 6 had been skipped at the time). They are now classified `robots`, links read from a disallowed page are
dropped, and any record kept from them was deleted: four GitHub `/commits/` pages reached one hop from GitHub file
pages, one iXBRL file (a context row), and five PDF or HTML documents. Effect: in the cohort, one row goes from PDF
to "HTML page, no document link" (OTHER 510); in the context, four rows become `robots` and one goes from PDF to
HTML (OTHER 454). The `robots.txt` files were
read in the afternoon of the collection day and may differ from those of the morning.

**D9 (instant client-side redirects; review B4).** A landing page that is only an instant redirect —
`<meta http-equiv="refresh">` with a delay of at most 1 s, or a trivial JavaScript `location` redirect on a page with
no visible text — is now followed like an HTTP 3xx (at most five), not counted as a page without a document. All 510
landing pages classified `html` were fetched again (phase B); 7 are such redirects. Two are cohort rows of the main
producer (OTHER 132, 144), which now reach a valid iXBRL file one hop after the redirect; of the five context rows,
two now reach a PDF. The nine other cohort rows of the same producer that end on an `html` page were read again
the same afternoon: they are not redirects and carry no link to a document. The frozen-rule figure (without D1 and
D9) is reported beside the headline.

**D10 (Inline XBRL version; review B2).** ITS Art. 2(1) requires Inline XBRL 1.1 (namespace
`http://www.xbrl.org/2013/inlineXBRL`); the first classifier also accepted the 1.0 namespace (2008). Every Inline XBRL
file reached (168) was downloaded once more and its namespace recorded (phase C): 151 unchanged and 1.1, 12 changed
since and 1.1, **1 in Inline XBRL 1.0** (OTHER 519), now its own class `ixbrl-1.0` ("Inline XBRL 1.0, not the required
version"), never available or valid; 4 could not be read again (2 now answer 404, 2 hosts' `robots.txt` unreachable),
and keep their first classification (`ix_version_rechecked = 0` in `data/rows.csv`).

**D11 (reporting).** Rows and distinct files are reported separately. Failed assertions are listed at error severity.
`data/rows.csv` now carries the registered `wp_url` and the URL of the document classified (public register data,
reused with acknowledgement of ESMA). The Q&A count is 51 (the listing loop stopped at 50; the missing Q&A, 765, on
DLT market infrastructures, is unanswered). Before the freeze, the checker was tried on one cohort URL of the main
producer and its file (8 requests, 11:11:50–11:12:12 UTC); the cohort collection started at 11:14:46 UTC. The D4
counts reconcile as follows: the first validation batch had 151 files (148 `ixbrl-esma`, 3 `ixbrl-other`); the 148
were re-read (137 same hash, 10 changed, 1 failed), and 140 of them are the files of available cohort rows before D7–D10.
From D8 on, the log records the monotonic start time of each request.
