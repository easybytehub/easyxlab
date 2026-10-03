# S11 — Method

*EasyxLab · study S11 · working draft*

Before the freeze below, the rates were not unknown. The preliminary scouting that proposed
this study had estimated two of them on the June snapshots: 13.6% of Barcelona's HUT numbers
missing from both registries, and 77% of Madrid's "non-tourist" listings accepting 1–4
nights. The freeze guarded the rules, not ignorance of the likely result.

<!-- FROZEN-RULES-START -->
## 1. Classification rules (frozen before matching)

These rules were written, and their SHA-256 recorded in `STATUS.md`, before any listing was
matched against a registry. Parser code: `scripts/strnum.py`; extraction:
`scripts/extract_listings.py`; matching: `scripts/analyse.py`. Any later change is listed in
§9 "Deviations from the frozen rules", with the reason.

### 1.1 Population and denominators

- **Listing**: one row of an Inside Airbnb `listings.csv.gz` snapshot.
- **Active listing**: `number_of_reviews_ltm ≥ 1` (at least one review in the twelve months
  before the scrape). All headline shares use active listings. Shares over all listings are
  published too.
- **Short stay** (NYC only, where the law applies to stays of fewer than 30 days):
  `minimum_nights < 30`.
- Areas and snapshots: Barcelona (city), Girona (Inside Airbnb's "girona" area, which covers
  municipalities of the Costa Brava and inland Girona), València (city), Málaga (city), Sevilla
  (city), Madrid (city) and New York City; the last scrape before 20 May 2026 (March 2026) and
  the first after (June 2026).

### 1.2 Reading the licence field

`split_license` splits Airbnb's labelled blocks ("Spain - National registration number",
"<Region> - Regional registration number"). An unlabelled value that starts like a national
number (`ES` + four letters + a digit) is read as national; any other unlabelled value as the
regional (in NYC, the only) number. A national number typed into the regional field is moved
to the national slot.

### 1.3 Regional formats (`parse_regional`)

Text is upper-cased, accents removed, dashes unified; decorations such as "Nº", "Licencia:"
are dropped. If several numbers are given, the first is used.

| region | accepted form → matching key | other series recognised (no open registry used) |
|---|---|---|
| Catalonia | `PREFIX[-]digits[-NN]`, prefix in the RTC prefix list (HUTB/G/T/L/CC/TE/VA, HB…, PB…, LLB…, ATB…, KB…, AA…); key `PREFIX-` + 6 digits; `-NN` (or two extra digits written together with a 6-digit number) = control digit | AJ (youth hostels) |
| Comunitat Valenciana | `CV-VUT` + digits + `-V/A/CS`; old `VT-digits-V/A/CS` and the variants `VUT…-X`, `CV-VT…-X` mapped to `CV-VUT` + 7 zero-padded digits + province | HV/H, AT/AP/AV, CR/ARU |
| Andalucía | `TYPE/PP/digits` with `/`, `-`, `.`, space or nothing as separators, PP an Andalusian province code; VFT, VUT and the transposition VTF are one series (VUT); key `SERIES/PP/integer` | CTC codes |
| Comunidad de Madrid | `VT[-]digits` (also AM, HM, TR…); key `VT-integer` | all (no downloadable registry) |
| New York City | `OSE-STRREG-` + 7 digits | — |

- **placeholder**: the number part is zero (`HUTB-000000`, `VT-0`, `CV-VUT0000000-V`).
- **malformed or unrecognised**: a value is present but fits no form above (free text such as
  "En proceso", a tax id, a file number, a province code that is not Andalusian…).
- **exempt**: the value starts with "Exempt" (Airbnb's wording, e.g. "Exempt - seasonal rental").

National number (`parse_national`): 53 characters `ES` + `FC|HF` + `TU|NT` (TU tourist, NT
non-tourist, as designated by the host); any other `ES…` value of 20+ characters is "national,
other prefix". National numbers are not matched against any registry (there is none to match:
the procedure was annulled and the Colegio de Registradores publishes no list).

### 1.4 Registry match (`analyse.py`)

Registries, all read once on 2026-10-03: Registre de Turisme de Catalunya (RTC, all types,
only establishments "Alta"), viviendas turísticas of the Comunitat Valenciana (GVA), OpenRTA
(Andalucía, all types), NYC OSE registration dataset as of 2025-06-25. A key is **found** if
the registry has the same canonical key. It is found **in the same municipality** if the
registry's municipality (accents, case, punctuation and articles ignored) equals the
listing's municipality: Barcelona, València, Málaga, Sevilla; for Girona the listing's Inside
Airbnb neighbourhood, which is a municipality; for NYC the borough.

### 1.5 Primary category (one per listing; first rule that applies)

1. `in_registry` — regional number well-formed, of a series with an open registry, found, same
   municipality.
2. `in_registry_other_municipality` — found, different municipality.
3. `not_found` — well-formed, open registry, not found. In NYC, only numbers up to the highest
   number in the registry file; higher numbers are `after_registry_date`.
4. `no_open_registry` — well-formed, but the series has no open registry we could use.
5. `placeholder`.
6. `malformed` (malformed or unrecognised).
7. `national_tu_only` — no regional value; a national TU number.
8. `non_tourist` — no regional number; a national NT number (with or without an "Exempt"
   regional statement).
9. `national_other_only` — no regional number; a national number with another prefix.
10. `exempt` — no number at all, an "Exempt" statement in the regional or national field.
11. `empty` — nothing.

### 1.6 Headline measures

- **H1 (Spain)**: among active listings whose regional field shows a well-formed number of the
  tourist-dwelling series with an open registry (HUT*, CV-VUT, VFT/VUT), the share
  `in_registry`, `in_registry_other_municipality` and `not_found`, per area and snapshot, with
  95 % Wilson intervals.
- **H2 (Spain)**: share of active listings by primary category, per area and snapshot.
- **H3 (non-tourist numbers)**: among active `non_tourist` listings, the share with
  `minimum_nights ≤ 4`, `≤ 31`, and with 12 or more reviews in the last twelve months, and the
  median of reviews in the last twelve months. These are signals of tourist use, not proof.
  Same signals for `exempt` listings.
- **H4 (NYC)**: among active short-stay listings, the share by category; among those showing
  an `OSE-STRREG` number up to the registry's highest number, the share found, by status.
- **Before/after**: H1–H4 in March and June 2026; and, for listings present in both
  snapshots, the transition table between categories.

### 1.7 Diagnostics (reported, not headline)

Chance-match rate (share of the numeric range of a series occupied by registry numbers of the
listing's municipality, i.e. how often a random well-formed number would be "found"); Catalan
control digit agreement; Valencian old-format mapping (match rate of old vs current form);
Andalusian VFT vs VUT match rates; numbers shown on more than one listing and by more than one
host; regional numbers embedded in national TU numbers.

### 1.8 Publication rules

Only aggregates per area × snapshot × category, with n. No listing or host id, URL, name,
coordinates, address, or individual licence number is published. Cells with n < 10 are
published as counts but their percentages are left blank.
<!-- FROZEN-RULES-END -->

## 2. Sources, licences and snapshot dates

### 2.1 Listings: Inside Airbnb

Inside Airbnb publishes scrapes of Airbnb listings. Its download page licenses them under the
"Creative Commons Attribution 4.0 International License"; its data policy says "Inside Airbnb
data should be attributed and cited appropriately" and offers "a reasonable amount of free data
(the last 12 months)". We used only free snapshots, downloaded on 2026-10-03 from
`data.insideairbnb.com` (robots.txt allows our client), and never accessed Airbnb.

| area | Inside Airbnb path | before 20 May 2026 | after | listings (before / after) | active |
|---|---|---|---|---|---|
| Barcelona | spain/catalonia/barcelona | 2026-03-21 | 2026-06-24 | 16,107 / 15,293 | 9,575 / 9,666 |
| Girona area | spain/catalonia/girona | 2026-03-31 | 2026-06-30 | 16,834 / 21,257 | 11,505 / 13,481 |
| València | spain/vc/valencia | 2026-03-28 | 2026-06-26 | 4,930 / 7,851 | 4,123 / 6,219 |
| Málaga | spain/andalucía/malaga | 2026-03-31 | 2026-06-30 | 8,098 / 9,568 | 6,525 / 7,541 |
| Sevilla | spain/andalucía/sevilla | 2026-03-31 | 2026-06-30 | 7,093 / 8,245 | 5,972 / 6,706 |
| Madrid | spain/comunidad-de-madrid/madrid | 2026-03-24 | 2026-06-20 | 23,002 / 22,708 | 15,238 / 15,782 |
| New York City | united-states/ny/new-york-city | 2026-03-16 | 2026-06-14 | 35,979 / 30,259 | 10,696 / 10,476 |

The dates are Inside Airbnb's publication dates; the March and June scrapes are the last before
and the first after 20 May 2026 in Inside Airbnb's list. URLs and SHA-256 of each file are in
`data/sources.json`. Inside Airbnb also covers Mallorca, Menorca and Euskadi, which have no
registry we could download, so they are not in the study.

The licence field (`license`) holds what Airbnb displays. Since at least March 2026 it is a set
of labelled blocks, e.g. `Spain - National registration number<br />…<br /><br />Barcelona -
Regional registration number<br />…`; in New York it is a single unlabelled value.

### 2.2 Registries (all downloaded 2026-10-03)

| registry | publisher, portal | licence or terms as stated | state of the copy | rows | used for |
|---|---|---|---|---|---|
| Registre de Turisme de Catalunya (RTC), "Establiments d'allotjament turístic inscrits al Registre de Turisme de Catalunya" (Socrata `t2h3-cgys`) | Generalitat de Catalunya, Departament d'Empresa i Treball; analisi.transparenciacatalunya.cat | dataset metadata: "See Terms of Use", with a link to the Generalitat's open-data licence page (that page's robots.txt does not allow our client): **licence not verified**; we redistribute only counts | rows updated 2026-07-31; the publisher lists only establishments "Alta" (all 112,714 rows), we applied no filter | 112,714 | Barcelona, Girona |
| Viviendas turísticas de la Comunitat Valenciana (`tur-gestur-vt`) | Generalitat Valenciana; dadesobertes.gva.es | CKAN `license_id` "cc-by" ("Creative Commons Attribution") | daily file of 2026-10-03; current registrations only | 90,097 | València |
| OpenRTA, Registro de Turismo de Andalucía | Junta de Andalucía; datos.juntadeandalucia.es | "Reconocimiento 4.0 Internacional (CC BY 4.0)" | API `lastUpdateData` 2026-10-03T04:07Z | 175,432 | Málaga, Sevilla |
| NYC Office of Special Enforcement, "Short-Term Rental Registration Data, as of June 25, 2025" | City of New York; read from the Internet Archive's capture of 2025-11-08 | the OSE data page says the data "is being published consistent with the requirements of Local Law 18, and as such, does not include the name of the applicant" | 2025-06-25 | 3,136 registrations; 2,910 links to Airbnb listing numbers | New York |

Columns kept: number, type, municipality and its code, province, date of registration (GVA),
status (OSE), control digit (RTC), Airbnb listing number linked to a registration (OSE).
Holders' names, tax ids, e-mails, phones (OpenRTA and RTC publish them), street addresses,
units and cadastral references were not kept.

- **Spanish registries.** `scripts/fetch_registries.py` filters while streaming, so no other
  column is written to disk. During exploration, before that script existed, the full GVA
  CSV was saved in `work/` for about 13 minutes. So was a probe extract of OpenRTA which,
  because of the file's misaligned rows, contained holders' names in one column. Both were
  deleted the same hour.
- **New York.** The xlsx (street address, unit, BIN; no names) is written to a temporary file
  in `work/` and deleted after filtering. Two OSE annual-report spreadsheets saved during the
  prior-work search contained building addresses; they were deleted after the review.
  Nothing with addresses remains.

### 2.3 Registries we could not use

- **Barcelona City Council's list of tourist dwellings** (opendata-ajuntament.barcelona.cat,
  CC BY 4.0, quarterly since 2024): its robots.txt disallows `/data/api*`,
  `/data/dataset/*/download` and `/resources/*`, which covers every way to download it. We
  did not download it. Its quarterly archive would have separated "recently de-registered"
  from "never registered".
- **Comunidad de Madrid** (datos.comunidad.madrid): robots.txt `User-agent: * Disallow: /`. No
  Madrid registry was used; Madrid numbers are checked for format only.
- **NYC OSE dataset of 7 January 2026**, the copy current on the snapshot dates (OSE's page
  captured on 9 May 2026 offered it). www.nyc.gov answers HTTP 403 to our User-Agent, for
  robots.txt and for content. We did not try another User-Agent. The Internet Archive has
  no capture of that file, so we used the 25 June 2025 dataset, the latest captured. Using
  the archive copy goes round an origin refusal. We consider it acceptable here: the dataset
  is a public record published under Local Law 18, it has no names, and we publish only
  counts.
- **Spain's national number**: there is no public list. The Colegio de Registradores issued the
  numbers; the procedure was annulled (§3 of the paper).

## 3. Sources: access, User-Agent and rate

All requests to websites went through `scripts/polite.py`. It sends the User-Agent
`EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`, keeps at least 1.05 s
between requests to the same host, honours a declared `Crawl-delay`, reads robots.txt, and
logs every request in `work/fetch_log.jsonl`. Requests that robots.txt refused were not made
by other means: Barcelona's CKAN API and downloads, Madrid's open-data portal, the
Generalitat's licence and legal portals, three CBC articles, *Scripta Nova* article 18573,
and insidemenorca.com. The log of the main run shows 17 pairs of consecutive requests to the
same host within the same second and 4 pairs to www.bocm.es closer than its declared
`Crawl-delay: 10`; the OpenRTA file was downloaded 7 times while its layout was worked out.

| source | host and access method | rate | licence or term that applied |
|---|---|---|---|
| Inside Airbnb listings | `data.insideairbnb.com`, 14 `listings.csv.gz` files, each downloaded once; `insideairbnb.com` pages to locate them | ≤ 1 request/s | "Creative Commons Attribution 4.0 International License"; "Inside Airbnb data should be attributed and cited appropriately"; "Do not republish the data" (https://insideairbnb.com/data-policies/). We attribute the data and publish only counts. |
| Registre de Turisme de Catalunya | `analisi.transparenciacatalunya.cat`, Socrata API (`/resource/t2h3-cgys.csv` with `$select`) | ≤ 1 request/s | metadata "See Terms of Use"; licence not verified (§2.2) |
| Viviendas turísticas, Generalitat Valenciana | `dadesobertes.gva.es`, CKAN resource download (CSV) | ≥ 10 s (declared Crawl-delay) | CKAN licence "cc-by" |
| OpenRTA, Junta de Andalucía | `datos.juntadeandalucia.es/api/v0/openrta/all?format=csv`, redirecting to `www.juntadeandalucia.es/ssdigitales/…` | ≤ 1 request/s | "Reconocimiento 4.0 Internacional (CC BY 4.0)" |
| NYC OSE registration dataset | `web.archive.org` capture of 2025-11-08 (`www.nyc.gov` answers HTTP 403 to our client) | ≤ 1 request/s | none stated; the file has no names (§2.2) |
| Regulation (EU) 2024/1028 and corrigendum | `publications.europa.eu` (Cellar, `Accept: application/xhtml+xml`, `Accept-Language: eng`) and its SPARQL endpoint | ≤ 1 request/s | EU content, reuse with acknowledgement of the source |
| Spanish law and judgments | `www.boe.es` (`txt.php`, `act.php`, open-data API) | ≤ 1 request/s | BOE reuse conditions: the source must be cited with a link to https://www.boe.es; the paper does so |
| Regional bulletins | DOGV portal JSON endpoints (`dogv.gva.es`), BOJA pages (`www.juntadeandalucia.es/boja`), BOCM PDFs (`www.bocm.es`), Comunidad de Madrid legislation portal (`gestiona.comunidad.madrid`) | ≤ 1 request/s; BOCM 10 s declared | official bulletins |
| NYC rules | `rules.cityofnewyork.us` (adopted rule PDF); `codelibrary.amlegal.com` answered HTTP 403 | ≤ 1 request/s | — |
| arXiv | `export.arxiv.org/api/query`, 39 requests: the 16 queries twice (the first run's syntax returned nothing), 5 broader ones and 2 tests | one request every ≥ 3 s, one connection, as the arXiv API terms ask | API terms of use |
| Crossref | `api.crossref.org` REST API, public pool, 26 searches and 8 DOI lookups | ≤ 1 request/s, one connection | — |
| Semantic Scholar | `api.semanticscholar.org` Graph API, 20 attempts (17 answered 429) | ≤ 1 request/s, retries after 8 and 16 s | — |
| OpenAlex | `api.openalex.org`, 27 requests, no key | ≤ 1 request/s | — |
| GitHub | `gh search repos` / `gh search code` (authenticated CLI), 18 + 9 searches | about 3 s and 7.5 s apart, within GitHub's search limits | — |
| Press, official and NGO pages | 38 pages on about 20 hosts | ≤ 1 request/s per host | quoted only, with source |

## 4. Matching rules per region

See §1.3–1.5 (frozen). In more detail:

- **Catalonia.** Key `PREFIX-NNNNNN`.
  - The RTC lists 45 prefixes: HUT + province code (B, G, T, L, CC, TE, VA) for tourist
    dwellings, plus hotels, rural tourism, shared homes (llars compartides), apartments,
    campsites and motorhome areas.
  - Youth hostels (AJ) are in another register and count as `no_open_registry`.
  - A two-digit suffix is compared with the RTC's control digit, as a check of the parser.
  - The listing's municipality:
    - Barcelona snapshot: Barcelona;
    - Girona snapshot: Inside Airbnb's `neighbourhood_cleansed`, which is a municipality
      name (aliases in §9).
- **Comunitat Valenciana.** Key `CV-VUT` + 7 digits + province letter.
  - Old `VT-NNNNN-X` numbers are mapped by zero-padding. This rule is not stated in any norm
    we could fetch; the evidence is empirical (§6).
  - The open file covers tourist dwellings only. Hotels (HV, CV-H), apartments (AT/AP/AV)
    and rural accommodation (CR/ARU) are `no_open_registry`.
- **Andalucía.** Key `SERIES/PP/integer`.
  - VFT ("viviendas con fines turísticos", the term of Decreto 28/2016) and VUT are one
    series. OpenRTA now labels all 153,506 tourist dwellings "Vivienda de uso turístico",
    with VUT codes. We could not locate the amending decree that changed the name or the
    code (§10), so the equivalence rests on the data (§6).
  - OpenRTA keys come from its `registration_code`.
  - The OpenRTA CSV mixes two row layouts: 30,000 rows with the 72 fields of the header and
    145,432 rows with 92 fields that do not follow it. In the 92-field rows the code,
    type, municipality and province were located by their values (positions 69, 60, 51
    and 67); `scripts/fetch_registries.py` documents this.
  - "CTC-" codes, which look like procedure codes rather than registry numbers, are
    `no_open_registry`.
- **New York.** Key `OSE-STRREG-NNNNNNN`.
  - Numbers above 3,137, the highest in the 25 June 2025 file, are `after_registry_date`:
    they were issued later and cannot be tested.
  - The municipality check uses the borough.
  - OSE's file also lists the Airbnb listing numbers it associates with each registration.
    For listings in that list we compare the number shown with the one OSE associates.

- **Wrong-form rules (post-review, §9 deviation 5).** A number not in the registry as written
  is `registered_wrong_form` if it matches one of three rules, applied in this order:
  - **R1** (Barcelona, Girona area). The six digits shown are `abcdef`; `PREFIX-00abcd` is
    registered in the listing's municipality and its RTC control digit equals `ef`. The
    probability of a chance match is the RTC's control-digit coincidence rate for the
    prefix, Σp² over the control-digit distribution (about 1.03% for HUT series). It counts
    for every number whose first four digits are a registered entry in the municipality.
  - **R2** (Barcelona, Girona area). A HUT number with one province code, `HUTx-n`, where
    `HUTy-n` with another code is registered in the listing's municipality. The chance
    probability is the sum, over the other codes, of the number of entries of that series in
    the municipality divided by the series' highest number.
  - **R3** (Málaga only). A `VUT/MA` number of six digits, above the series maximum, whose
    first five digits are a registered number in the listing's municipality. The chance
    probability is the share of five-digit numbers (10,000–99,999) registered in the
    municipality, 12.9% for Málaga.
  - R3 is not applied in Sevilla, following the reviewer, who judged it uninformative there.
    In June, 21 of Sevilla's 28 six-digit numbers above the series maximum (15,585) would
    match. How many would match by chance depends on the null:
    - about 1, if the first five digits were a random five-digit number (the null used for
      Málaga, where both nulls coincide because the series maximum is above 99,999);
    - about 14, if they are drawn from below the series maximum, where 61% of numbers are
      registered in the city. 23 of the 28 have first five digits in that range.

    Applying R3 would move 21 Sevilla listings (0.4 points) from "not found" to "wrong form".
    We leave them in "not found".
  - Expected counts by chance are in `data/h1_tourist_numbers.csv`
    (`wrong_form_R*_expected_by_chance`, next to `wrong_form_R*` and `_eligible`).

## 5. Denominators

- **Active** listings (≥ 1 review in the last twelve months): every headline share.
- **H1 denominator**: active listings whose regional field shows a well-formed number of the
  tourist-dwelling series with an open registry.
- **NYC**: active listings with `minimum_nights < 30`.
- `data/categories.csv` also gives shares over all listings.
- Cells with a denominator under 10 have counts but no percentage.
- Wilson intervals treat listings as independent; they are not (same host, shared numbers),
  so the intervals are too narrow. `data/h1_tourist_numbers.csv` gives the share of distinct
  numbers not found as a sensitivity check (Barcelona, June: 571 of 5,670 distinct numbers,
  10.1%, against 10.6% of listings).

## 6. Checks of the parser and of the format mappings (from `data/diagnostics.json`)

- **Catalan control digit.** In the Girona area in June, 853 of 865 numbers written with a
  two-digit suffix and found in the RTC carry the RTC's own control digit. So the suffix is
  read correctly, and those matches are not chance.
- **Valencian old format** (June). Old-format numbers mapped to `CV-VUT`: 2,132 of 2,405
  found (88.6%). Current-format numbers: 531 of 545 (97.4%). A random number of the right
  format would be found in València 1.1% of the time. The mapping is therefore right for
  most old numbers. The higher not-found share of old numbers may include de-registrations
  and some numbers the mapping does not cover; we report it, not adjust it.
- **Andalusian VFT/VUT** (June). Málaga: VFT 3,164 of 3,433 found (92.2%), VUT 2,043 of
  2,218 (92.1%). Sevilla: VFT 2,239 of 2,445 (91.6%), VUT 2,183 of 2,332 (93.6%). Old and new
  names behave alike.
- **In-range chance match** (renamed after the review; the first draft described it wrongly
  as the chance for "a random number of the right format"). For each listing showing a
  tourist-series number, this is the share of the numbers below the highest number the
  registry has issued in the series that are registered in the listing's municipality,
  averaged over listings. It is the probability that a random number *below the registry's
  highest number* would be found. June values:
  - Barcelona 13.3%;
  - Girona area 2.7%;
  - València 1.1%;
  - Málaga 12.3%;
  - Sevilla 61.2%;
  - NYC (same-borough test) 35.9%.

  Over the whole range the format allows (six-digit HUT, seven-digit CV-VUT and OSE,
  five-digit VUT or the series maximum if higher), the shares are: Barcelona 1.1%, Girona
  area 0.2%, València 0.1%, Málaga 12.3%, Sevilla 9.5%, NYC 0.0%
  (`full_format_chance_match_pct`). The HUT numbering is block-structured: HUTB has no
  entries between 20,000 and 29,999, and all four HUT province series stop just below
  80,000.

  A "found" result is weak evidence where the in-range rate is high. A "not found" result is
  a sure absence from the registry copy, as written.
- **Numbers embedded in national TU numbers** (replaces the dropped diagnostic of §9.4). Many
  national TU numbers end with a Catalan number: `HUTx-` plus seven digits (the first six
  read as the number) or plus six digits and a suffix. For listings with such an ending we
  compare it with the regional number shown (`catalan_number_embedded_in_national_TU`). In
  Barcelona in June, among the 205 residual not-found listings with such an ending:
  - 64 embed the number shown;
  - 123 embed a different number registered in Barcelona;
  - 18 embed a different, unregistered one.

  Among found listings the second group is 251 of 4,176. The residual "not found" is
  therefore an upper bound on numbers that belong to no registered dwelling.
- **Málaga extra digit.** In 183 of the 205 R3 matches of June, the national number ends with
  the same six digits (`malaga_extra_digit_in_national_number`).

## 7. Statistics

- Proportions get Wilson 95% intervals.
- No weighting: a listing counts once even if the same number appears on several listings
  (`data/duplicates.csv` reports how often that happens).
- Pooled figures add counts across areas.
- "Before/after" compares two cross-sections, plus a paired table for listings present in
  both snapshots (`data/transitions.csv`). There is no causal model.

## 8. Privacy and publication

- Inside Airbnb files contain host names, profile URLs and listing URLs. The registries
  contain holders' names and contacts. None of this is copied into `data/`, `README.md`,
  `METHOD.md` or the paper.
- Row-level extracts live in `work/extract/` (git-ignored). They hold the listing id, host
  id and licence text, which matching and de-duplication need.
- We publish counts per area × snapshot × category. We never publish listing or host ids,
  URLs, licence numbers or addresses, nor lists of non-matching listings.

## 9. Deviations from the frozen rules

1. **Municipality aliases** (found after the first match run; the rules' wording was
   "accents, case, punctuation and articles ignored").
   - The RTC uses current official names. Inside Airbnb's neighbourhood polygons carry older
     ones:
     - Castell-Platja d'Aro → Castell d'Aro, Platja d'Aro i s'Agaró;
     - Calonge → Calonge i Sant Antoni;
     - Boadella d'Empordà → Boadella i les Escaules;
     - Masarac → Masarac i Vilarnadal;
     - Brunyola → Brunyola i Sant Martí Sapresa;
     - Saus → Saus, Camallera i Llampaies.
   - Without the aliases, 1,231 of 11,597 Girona-area numbers (10.6%) appeared as "other
     municipality" in June; with them, 313 (2.7%). Barcelona and the cities are unaffected.
     Both figures are recomputed in `data/diagnostics.json` (`deviations_evidence`).
2. **Andalusian apartments and rural houses.**
   - OpenRTA lists only 178 tourist-apartment establishments ("A/") and 51 rural houses for
     all of Andalucía.
   - Only 30 of the 853 apartment and rural-house numbers shown by active listings in
     Málaga in June, and 75 of 1,082 in Sevilla, are in OpenRTA. This is a gap in the open
     file, not evidence about the listings (`deviations_evidence`).
   - These series (A, CR, CTR) were moved to `no_open_registry`. The tourist-dwelling
     headline (H1) is unaffected.
3. **Added signal rows.** `data/signals.csv` also reports `shows_NT_number`: every active
   listing showing a national NT number, whatever its regional field. The frozen H3 covered
   only the `non_tourist` category, which excludes the NT listings that also show a regional
   number. In the first draft this post-freeze row became the Madrid headline (7,659 of
   15,782, 48.5%; 5,872, 76.7%, accepting 1–4 nights) without saying so. After the review,
   the headline is the frozen measure again: 6,634 of 15,782 (42.0%); 4,916 (74.1%, 95% CI
   73.0–75.1%) accept 1–4 nights. The secondary row stays, labelled as post-freeze. It was
   added because about a thousand Madrid listings show an NT number together with a regional
   one. It is not the headline because a listing that also displays a tourist registration
   has a better claim to be a tourist let.
4. **Dropped, then restored, diagnostic.** We had planned to read the regional number
   embedded at the end of national TU numbers, and dropped it because our first reading gave
   spurious disagreements. The reviewer showed that a clean subset reads unambiguously and
   reveals the wrong forms of deviation 5. It is now reported for that subset (§6).
5. **Wrong-form category (added after the adversarial review, i.e. after the freeze).**
   - The review found that about one in five "not found" numbers is a registered dwelling of
     the listing's own municipality written in a recognisable wrong form. We added the
     category `registered_wrong_form` with the three rules R1–R3 of §4 and their chance
     baselines.
   - Under the frozen rules, "not found" is the sum of `registered_wrong_form` and
     `not_found`. `data/h1_tourist_numbers.csv` keeps it as `not_found_frozen_rule`.
   - **Frozen versus current, pooled June:**
     - frozen rules: 2,623 of 31,222 not found (8.4%, CI 8.1–8.7%);
     - now: 557 in a wrong form (1.8%, about 45 expected by chance) and 2,066 not found
       (6.6%, CI 6.3–6.9%).
   - **Pooled March:** 2,211 (8.1%) under the frozen rules, now 475 and 1,736 (6.4%).
   - **Barcelona, June:** 810 (13.3%) under the frozen rules, now 168 and 642 (10.6%).
   - **Girona area, June:** 720 (6.2%), now 184 and 536 (4.6%).
   - **Málaga, June:** 444 (7.9%), now 205 and 239 (4.2%).
   - Our counts differ slightly from the reviewer's. The reviewer reported 46 Girona-area R1
     matches and 152 R2 matches; we find 29 and 155, because our R1 also requires the entry
     to be in the listing's municipality.

Process note: the first matching run used row-level extracts produced before the last
pre-freeze parser change (Valencian hotel numbers written `CV-H…`). Every published figure
comes from extracts regenerated with the frozen parser (`scripts/run.sh` always re-extracts);
the change moved 22 active València listings in June from "malformed" to "no open registry"
and left every headline unchanged.

## 10. What was not possible

- Separating "cancelled between the scrape and our registry copy" from "never registered".
  Barcelona's quarterly archive is behind robots.txt, and the RTC and GVA files list only
  current registrations. The copies were taken after both snapshots (RTC 31 July, GVA and
  OpenRTA 3 October 2026), so "not yet registered" is unlikely. One copy serves both
  snapshots, which biases March towards "not found".
- Verifying the RTC licence (its licence page refused our client).
- Publishing the registry extracts, as the reviewer suggested, to make the figures exactly
  reproducible after the sources change. The study publishes aggregates only, and the New
  York extract links registrations to Airbnb listing numbers, a row-level join. The SHA-256
  of every extract is in `data/sources.json`.
- Any registry check in Madrid.
- Testing New York numbers above 3,137 (issued after 25 June 2025).
- Checking national numbers, for lack of a public list.
- Checking that a number belongs to the specific dwelling advertised. We match numbers and
  municipalities, not addresses: Inside Airbnb's coordinates are approximate and we did not
  use addresses.
- Regions outside the study (Baleares, Euskadi, Canarias…).
- Reading some legal texts: Decret 75/2020 de turisme de Catalunya and the Catalan originals
  (robots.txt of the Generalitat's legal portals); the Andalusian decree that renamed VFT as
  VUT (not found in the BOJA issues searched); the NYC Administrative Code (HTTP 403). None
  of the regional texts we read defines the format of the number.
