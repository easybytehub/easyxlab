# S17 — Method

*EasyxLab · study S17 · method written and hashed 2026-10-03 before the main collection. The sha256 of the frozen text was recorded in the private status file, but the frozen text itself was not preserved, so the freeze is self-attested and cannot be audited by a third party. §1-§8 below are the frozen text except for the dated correction notes marked as such; all later changes are listed in §9.*

## 1. Question and legal yardstick

What does a machine see on data.europa.eu, sixteen months after Commission Implementing Regulation (EU) 2023/138 on high-value datasets (HVD) became applicable (9 June 2024), and how does it compare with what Member States self-reported in the Open Data Maturity (ODM) 2025 questionnaire?

> **Correction 2026-10-03:** "16 months" was an arithmetic error in the study brief; it is 28 months (9 June 2024 → 3 October 2026). Sixteen months is the gap between entry into force and application (Art. 6). No rule or measurement depends on it.

The yardstick is the regulation's text in force on the measurement date (Cellar, CELEX 32023R0138; no amending act; the three corrigenda of 2024 concern only the Greek, Spanish and Slovenian versions) and the SEMIC recommendation **DCAT-AP HVD 3.0.0** (published 2024-10-25), which says how Art. 3(5) is expressed in metadata. We test four things:

| test | article | what a machine can check on the European portal |
|---|---|---|
| T1 tagging | Art. 3(5) | the dataset carries `dcatap:applicableLegislation` = `http://data.europa.eu/eli/reg_impl/2023/138/oj` **and** at least one `dcatap:hvdCategory` (both 1..* in DCAT-AP HVD 3.0.0) |
| T2 licence | Art. 4(3) | every distribution carries a licence in the classes A or B of the table in §5 |
| T3 API | Art. 3(1) | the dataset is served by an API, modelled as DCAT-AP HVD says (`dcat:accessService` on a distribution, or a `dcat:DataService` whose `dcat:servesDataset` is the dataset) |
| T4 reachability | Art. 3(1) (availability) | the distribution URL answers |

Nothing here measures whether a Member State *publishes* its HVDs. The portal shows what national catalogues deliver and what its harvester maps. "0 on the European portal" means "the European portal does not identify any dataset of that country as HVD", not "the country does not publish". All counts are of the snapshot taken on 2026-10-03; the portal re-harvests daily.

## 2. Population

- **Census (C).** All records returned by the data.europa.eu search API with `filter=dataset` and facet `is_hvd=true`, collected with the API's scroll mechanism on 2026-10-03. Fields kept: `id`, `country.id`, `catalog.id`, `is_hvd`, `hvd_category.id`, `applicable_legislation`, `keywords.id`, `access_right.resource`, and per distribution `id`, `license.id`, `license.resource`, `access_url`, `download_url`, `format.id`, `access_service`, `applicable_legislation`, `rights`. Contact points, publisher e-mails and any person names are never requested.
- **Half-tagged (H).** From the portal's SPARQL endpoint (`https://data.europa.eu/sparql`), the `dcat:Dataset` resources that have `dcatap:hvdCategory` but not the exact ELI as `dcatap:applicableLegislation` (H1), grouped by catalogue; and resources whose `applicableLegislation` value contains `2023/138`, `32023R0138` or `2023_138` but is not the exact ELI (H2, malformed). "ELI without category" (H3) is computed inside C (`hvd_category` empty).
- **Denominators.** For each country, the total number of datasets on the portal (search facet `country`, no HVD filter), and the catalogue → country mapping from the search API (`filter=catalogue`).
- **Member States.** The 27 EU Member States. Records whose country is `EUROPE` (EU institutions), Norway, Iceland or Serbia are counted in the census total but excluded from per-Member-State results and from the ODM comparison (the regulation and the ODM HVD questions apply only to Member States).

## 3. Tagging rules (T1, H)

- Exact ELI: the IRI `http://data.europa.eu/eli/reg_impl/2023/138/oj` (string equality, http scheme, no trailing slash). Any other IRI mentioning the regulation is **malformed**, and we list each variant with its count.
- A record of C passes T1 if it has ≥ 1 HVD category. A record of C without category is "ELI without category".
- The SPARQL counts are taken in the same session as the census and stored with the query text and timestamp (`data/queries.json`).

## 4. Distribution-level ELI

DCAT-AP HVD 3.0.0 also makes `applicableLegislation` 1..* on the Distribution and the Data Service. We report the share of distributions of C that carry the exact ELI. This is reported, not used to fail a dataset (Art. 3(5) speaks of the dataset's metadata description).

## 5. Licence classes (T2) — written criterion, frozen before measuring

Art. 4(3) names CC0 and CC BY 4.0 and admits "any equivalent or less restrictive open licence … allowing for unrestricted re-use", with attribution allowed. Each distribution's licence value (IRI or ID, lower-cased, `https`→`http`, trailing `/` and `.html`/`legalcode` removed) is put into one class by the first matching rule:

| class | meaning | rule (patterns on the normalised IRI/ID) |
|---|---|---|
| **A** named | CC0 1.0 or CC BY 4.0 | `cc0`, `cc-zero`, `publicdomain/zero`, `cc_zero`; `cc-by-4.0`, `cc_by_4_0`, `cc-by/4.0`, `licenses/by/4.0`, `cc-by_4.0` (and no `-sa`, `-nc`, `-nd`) |
| **B** equivalent or less restrictive | open, at most attribution required, no share-alike, no use restriction | public domain mark (`publicdomain/mark`), ODC-PDDL (`pddl`), ODC-BY (`odc-by`, `odc_by`), Datenlizenz Deutschland Zero 2.0 (`dl-de-zero`, `dl-zero-de`, `dl_de_zero`), Datenlizenz Deutschland Namensnennung 2.0 (`dl-de-by-2.0`, `dl-by-de/2.0`, `dl_de_by_2_0`), Etalab Licence Ouverte 1.0/2.0 (`etalab`, `licence-ouverte`, `lo_ol`, `lo-2.0`, `lov2`, `licence_ouverte`), Italian Open Data Licence 2.0 (`iodl/2.0`, `iodl_2_0`, `iodl-2.0`), Flemish free re-use model licence (`modellicentie-gratis-hergebruik`, `gratis-hergebruik`), Croatian Open Licence (`otvorena-dozvola`, `otvorena_dozvola`), Czech terms of use with CC BY 4.0 for the work (`ofn/podminky-uziti` only when the record also references CC BY 4.0 — otherwise class E), older CC BY versions and their national ports (`cc-by/3.0`, `cc-by-3.0`, `licenses/by/3.0`, `licenses/by/2.5`, `licenses/by/2.0`, `cc_by_3_0`, `cc-by_3.0`, ports such as `licenses/by/3.0/at`), Commission reuse decision 2011/833 (`com_reuse`, `2011/833`) |
| **C** share-alike | open but more restrictive than CC BY 4.0 | `-sa`, `_sa`, `bysa`, `by-sa`, `odbl`, `iodl/1.0`, `dl-de/by-nc` excluded from here (→ D) |
| **D** not open | non-commercial, no-derivatives, closed or restricted | `-nc`, `_nc`, `bync`, `-nd`, `_nd`, `bynd`, `other-closed`, `closed`, `restricted`, `dl-de-by-nc` |
| **E** unspecific | a value exists but names no specific terms | `other-open`, `other-at`, `other-pd`, `other-nc`, `notspecified`, `not-specified`, `unknown`, `other`, a bare home page of a portal, and anything that matches no rule above |
| **N** none | the distribution carries no licence value in the search index | — |

Rules are checked in the order D, C, A, B, E (so that `cc-by-nc-4.0` is D, not A). Class E is never counted as conforming or non-conforming: it is reported, with each value and its count, in `data/licence_values.csv`, so a reader can reclassify. A **dataset** passes T2 if all its distributions are A or B; it is "no licence visible" if **all** its distributions are N (or it has none).

**Confirmation of "no licence" (coordinator rule 5).** Every dataset of C counted as "no licence visible" in the index is re-checked in the portal's RDF through SPARQL: `dct:license` on any of its distributions, `dct:license` on the dataset itself, and `dct:rights` on the dataset or its distributions. Only datasets with none of these are counted as "no licence in the RDF"; those with only `dct:rights` are counted separately. A random 50 of the confirmed ones (seed 17) are also checked against the full record from the portal's repository API (`/api/hub/repo/datasets/{id}.ttl`), to bound the disagreement between the SPARQL store and the record.

## 6. API signal (T3)

A dataset of C has:

- **modelled API** if any distribution has a non-empty `access_service` in the index, **or** a `dcat:DataService` in the SPARQL store has `dcat:servesDataset` = the dataset, **or** a distribution has `dcat:accessService` in the SPARQL store;
- **inferable API** (looser, reported separately) if it has no modelled API but a distribution's format or URL indicates a service interface: format ID in {WMS, WFS, WCS, WMTS, WMS_SRVC, WFS_SRVC, CSW, SOS, OGC API, API, REST, SPARQL, JSON_LD API} or URL matching (case-insensitive) `service=(wms|wfs|wcs|wmts|csw|sos)`, `getcapabilities`, `/wms`, `/wfs`, `/wcs`, `/wmts`, `/ogc/`, `/ogcapi`, `/collections`, `/api/`, `/api?`, `/sparql`, `/rest/`, `/services/`, `arcgis/rest`, `mapserver`, `/odata`.

Only "modelled API" is how DCAT-AP HVD 3.0.0 expresses Art. 3(1) ("A Dataset MUST have an associated Data Service, besides the exceptions listed in the HVD IR"). Art. 3(1) allows bulk-only only "where indicated in the Annex", and some Annex datasets have API exceptions; the metadata does not say which Annex item a dataset is, so T3 is reported as a signal, not as a breach.

## 7. Reachability sample (T4)

- **Frame.** Every distinct URL of C's distributions (download URL if present, else access URL), Member States only.
- **Sample.** Stratified by Member State: 100 URLs per Member State drawn uniformly at random (Python `random.Random(17)` over the URLs sorted lexicographically), or all URLs when a Member State has fewer than 100. At most 10 URLs per host within a stratum (redraws replace excess), so that one server does not dominate a country.
- **Request.** Every request goes through one helper (`scripts/fetch.py`) that reads the host's robots.txt before the first request to that host and honours it for our User-Agent and `*`; robots.txt answered with 5xx or not reachable → host skipped; robots.txt with a natural-language prohibition in comments → host skipped; 4xx → allowed (RFC 9309 §2.3.1.3). At most 1 request per second per host. Redirects are followed by the helper hop by hop (≤ 5), each hop checked against its own host's robots.txt. URLs that look like OGC services (`service=wms|wfs|wcs|wmts` or `/wms`, `/wfs` in the path) are requested as `GetCapabilities` (adding `SERVICE=…&REQUEST=GetCapabilities` if absent). Every other URL: `GET` with `Range: bytes=0-2047`, reading at most 2,048 bytes. Timeout 20 s. No retries.
- **Outcome classes.** `ok` (final status 200–299); `client_error` (400–499, with 401/403 and 404/410 kept apart); `server_error` (≥ 500); `network` (DNS, TLS, connection, timeout); `skipped_robots` (not requested: robots disallow, robots unreachable or natural-language reservation); `bad_url` (not an http(s) URL, or not parseable). Reachability = ok / (requested), with Wilson 95 % intervals per Member State; the EU figure is weighted by each Member State's share of frame URLs.
- An `ok` response is not a check of content: an HTML landing page or a login page with 200 counts as `ok`. We record the content type to report how many "download" URLs return HTML.

## 8. Self-report comparison (ODM 2025) and national cases

- **ODM 2025.** Per-country answers from `2025_odm_questionnaire_data.xlsx` (sheet `merged_responses`), questions P11 (applying the regulation), P12 ("Have the public bodies in your country denoted relevant datasets as high-value datasets in their metadata…?") and Q5 ("Have you implemented the DCAT-AP High Value Datasets tag…?"), against the census count, the half-tagged count and the national total on the portal. The report's own sentences are quoted with page and table (`2025_odm_report_6.pdf`). The questionnaire refers to the situation in 2025; the census is of 2026-10-03, so a "yes" in 2025 with 0 today is a gap between two dates, not a contradiction proven at one date.
- **Classification of the gap**, per Member State: `consistent-yes` (ODM yes and census ≥ 1), `self-yes-portal-zero` (ODM yes, census 0), `self-no-portal-some` (ODM no, census ≥ 1), `consistent-no`.
- **National cases.** Poland (dane.gov.pl, API `api.dane.gov.pl`, flag `has_high_value_data_from_ec_list`): count the datasets flagged at source, find the same datasets on data.europa.eu (catalogue of Poland, matching by the source landing page or identifier), and show which HVD properties survive harvesting. Where possible, a second case among the half-tagged catalogues (e.g. Ireland), using the portal's own records only.

## 9. Deviations after freezing

The text of §1-§8 above is the frozen text (its sha256 was recorded before the collection, but the text was not preserved separately, so this cannot be verified by a third party), apart from the dated correction note in §1. Everything below was added afterwards.

- **D1 (2026-10-03, licence spellings).** The frozen patterns missed some spellings of class A/B licences that appeared in the data (for example `dcat-ap.de/def/licenses/cc-by-de/3.0`, `govdata.de/dl-de/zero-2-0`, a CC BY 4.0 written as a keyword slug, the German GeoNutzV and the INSPIRE value "no conditions apply"). All results are reported **with the frozen rules**; a second count with these additions (`strict=False` in `scripts/hvd_rules.py`, column `class_D1` in `data/licence_values.csv`) is reported as a sensitivity analysis. It moves 709 datasets from "unclear" to "pass" and changes nothing else. The checker `hvd_check.py` uses the D1 rules by default and the frozen ones with `--strict`.
- **D2 (2026-10-03, Czech terms of use).** The frozen Czech rule expected the unaccented path `podminky-uziti` and a CC BY 4.0 reference in the same record; the index carries the accented IRI of a per-distribution terms-of-use node and no reference, so all 282 Czech HVD datasets are "unclear" under the frozen rules. We read what those nodes say from the SPARQL store (`scripts/02b_rdf_checks.py`) and report it in the text; the headline counts keep the frozen classification.
- **D3 (2026-10-03, GetCapabilities URL).** The URL builder left an empty parameter (`&&`) when it removed a `request=` parameter from an OGC URL. 68 sampled URLs were affected: 14 were not requested (robots.txt), and the other 54 all answered 2xx, so no outcome changed. Fixed and covered by a test.
- **D4 (2026-10-03, sample size).** The per-host cap of 10 and Member States with small frames gave 1,699 sampled URLs, not ~2,000; we did not raise the cap.
- **Note on 416.** 19 sampled URLs answered `416 Range Not Satisfiable`, which the frozen classes count as `client_error_other`. A 416 can mean an empty file or a server that refuses ranges; we report the number and do not reclassify.

- **D5 (2026-10-03, robots.txt redirects; found by the independent review).** `fetch.py` did not follow redirects when it fetched robots.txt, and parsed a 3xx answer as "allow all". RFC 9309 §2.3.1.2 asks crawlers to follow at least five. 51 scheme+host keys answered robots.txt with a 3xx; we made 162 requests to them. Re-read on 2026-10-03 with redirects followed (`scripts/08_robots_redirect_audit.py`, `data/robots_redirect_audit.json`): 2 of those requests (one on each of two Danish hosts) would have been disallowed, and on 8 keys (7 hosts) robots.txt still cannot be read after redirects (timeouts, redirect loops), so under our rules they would have been skipped. Without those 7 hosts the reachability figure is 1,361 of 1,484 (91.7 %) instead of 1,387 of 1,510 (91.9 %). `fetch.py` now follows up to five redirects.
- **D6 (2026-10-03, analyses added after the independent review).** (a) Sensitivity with the DCAT-AP.de value `other-closed` as class E (it is a catch-all "other closed licence" value that the portal types `adms:licencetype/UnknownIPR`; the frozen §5 is inconsistent in putting `other-open` in E and `other-closed` in D); (b) duplicates by base ID (the portal's `~~n` suffix) and the source host embedded in dataset IDs (`scripts/06_tables.py`); (c) the ODM Q5 comparison beside P12; (d) Polish feed pages that contain EU-list HVD datasets and the paging hypothesis (`scripts/05b_poland_feed.py`); (e) the IDs of the half-tagged datasets (`scripts/02c_review_sparql.py`, `data/half_tagged_ids.csv`). None changes a frozen rule; all are reported beside the frozen results.
- **Dead text in §5.** `other-nc` is listed in class E, but the rule order (D first) and the D pattern `-nc` make it class D.
- **Correction to §6 (Annex and APIs).** The Annex requires APIs in all six categories. The only relaxations are for earth observation and environment, "(for historical versions of datasets: APIs or bulk download, as feasible and appropriate)", and for meteorological "NWP model data", "which shall be made available through APIs only" (which relaxes bulk download, not the API). One Annex dataset may also be split over many portal records, so T3 is reported per record, not per Annex dataset.
- **Per-host cap.** The published `data/reach_sample.csv` shows 11 rows for `service.pdok.nl` in the Dutch stratum: the eleventh is the one `bad_url` row (not an http(s) URL, not requested), whose host is parsed only for publication. The cap held for every requested URL.
- Published reachability rows carry the host name only (`urllib.parse.urlsplit(url).hostname`): one sampled URL had an e-mail-like user-info part, which is dropped; IP-literal hosts would be written as `ip-literal` (there were none).

## 10. Privacy and access

- data.europa.eu legal notice: "To the extent possible under law, the European Union has waived all copyright and related or neighbouring rights to metadata of the open data portal via Creative Commons CC0 1.0 Universal". robots.txt of data.europa.eu (read 2026-10-03) disallows `/core/`, `/profiles/`, `/search/`, `/admin/`, user paths and similar; it does not disallow `/api/` or `/sparql`.
- Only aggregates per Member State and catalogue, dataset IDs and public URLs of distributions are published. No contact points, e-mails or personal names. Raw API pages stay in `data/raw/` (not published).
- User-Agent `EasyxLab-research/0.1 (+https://easybyte.es/lab/; contact@easybyte.es)`. The e-mail address in it is EasyxLab's own, there on purpose so that site operators can identify and contact the crawler (polite-crawling practice); it is not a third-party contact point.
