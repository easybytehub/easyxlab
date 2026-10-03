# S10 — Method

Snapshot date: **2026-10-02** (validation runs continued into 2026-10-03; access re-checks on 2026-10-03).

**User-Agent.** Catalogues, schemas, legal and profile texts, and all dataset downloads up to the
review used `EasyByteLab-research/0.1 (contact: contact@easybyte.es)`. This covers the census, the
first run, the resumed run and the re-check pass. After the lab was renamed EasyxLab, every later
request sent `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`: the prior-work
searches, the Swiss access check, the Greenlight Docker query and the post-review re-scans. Requests
were sequential per worker, with pauses of 0.3–3 s. No NAP, operator or standards body was
contacted. No dataset is redistributed.

## 1. Research questions

1. What do five national access points (NAPs) with anonymous catalogues publish in NeTEx: how many
   feeds, how large, under which licence, updated when?
2. On a justified sample, do the datasets validate against the open NeTEx XSD (releases 1.3.2 and
   2.0.0) and against the archived EPIP XSD? Which errors are most frequent?
3. Which consistency problems can be detected with rules taken only from open texts?

## 2. Legal basis, checked against the literal text

EUR-Lex returned HTTP 202 with an empty body to `curl`, so the texts were fetched from the
Publications Office Cellar (XHTML, English) and searched with `grep`:
- `http://publications.europa.eu/resource/celex/32024R0490` → `work/docs/reg2024_490.txt`;
- `…/celex/32026R0253` → `work/docs/reg2026_253.txt`.

**Delegated Regulation (EU) 2024/490**, replacing Articles 4–6 and the Annex of 2017/1926:

- Art. 4(1)(b): "one of the following standards and technical specifications, or any digital
  machine-readable format that can be proven fully compatible and interoperable with those
  standards … (i) NeTEx CEN/TS 16614 and subsequent versions; (ii) the technical specifications set
  out in Regulation (EU) No 454/2011; (iii) … IATA …; (iv) Transmodel EN 12896 where there is no
  reference exchange protocol".
- Art. 4(2) and 5(2): "minimum EU profiles or national profiles". "EPIP" does not occur in 2024/490.
- Art. 4(3), static data: 1 December 2019 (point 1.1, comprehensive TEN-T), 2020 (1.2), 2021 (1.3),
  1 December 2023 (other parts of the network), 2024 (new items such as transport on demand) and
  "(f) for the travel and traffic data set out in point 1.4 of the Annex, for the entire transport
  network of the Union, by 1 December 2025". **All have passed.**
- Art. 4(4): APIs "shall be publicly accessible to data users, where relevant subject to
  registration". Registration walls are lawful.
- Art. 5(3), dynamic data:
  - "(a) for the travel and traffic data set out in point 2.1 of the Annex, for the comprehensive
    TEN-T network, by 1 December 2025";
  - "(b) … point 2.2 …, for the comprehensive TEN-T network, by 1 December 2026";
  - "(c) … points 2.1 and 2.2 … for the other parts of the Union transport network, by 1 December
    2028".
- Annex 2.1 (the SIRI-relevant one): "Passing times, trip plans and auxiliary information:
  (i) disruptions … (ii) real-time status information, such as estimated departure and arrival
  times of services, delays, cancellations, guaranteed connections monitoring; (iii) status of
  access node features … – for scheduled transport."
- Annex 2.2: "(a) information service on parking tariffs – for transport on demand and personal
  transport; (b) availability check and location … (i) car-sharing availability and location,
  bike-sharing availability and location, scooter-sharing availability and location, and other
  vehicle-sharing availability and location; (ii) car parking spaces available (on and
  off-street)."

So the 1 December 2026 date is about parking and vehicle sharing, not public-transport real time.
The public-transport real-time deadline on the comprehensive TEN-T was 1 December 2025.

**Implementing Regulation (EU) 2026/253 (TEL TSI, 6 February 2026):**

- Art. 25: "1. Regulations (EU) No 454/2011 and (EU) No 1305/2014 are repealed. 2. References to the
  repealed Regulations shall be construed as references to this Regulation." The MMTIS reference to
  454/2011 therefore now reads as a reference to the TEL TSI.
- Appendix C.4.A: "[P.4] CEN/TS 16614-4:2025 Public transport - Network and Timetable Exchange
  (NeTEx) – Part 4: Passenger Information European Profile | Passenger timetable data for passenger
  rail transport services 4.2.1 all | Passenger timetable data of connection times 4.2.2 | Passenger
  timetable data sharing with other modes of transport 4.9 | Passenger travel information within the
  station 4.7.1". Also [P.1]–[P.3] (CEN/TS 16614-1, -2, -3:2025).
- Annex 4.2.1(1): "Passenger timetable data shared pursuant to Article 6(1) shall comply with the
  specifications referenced in Appendix C, indexes [P.2] and [P.4]."
- Art. 16(2): existing applications follow "the milestones set out in Appendix G of the Annex".
  Appendix G: "4.2.1 – Passenger timetable data 14.12.2025 | 4.2.2 – Passenger timetable data of
  connection times 12.12.2027 | 4.3 – Tariff data 10.12.2028 | … 4.7 – Passenger travel information
  during the train journey 12.12.2027". Art. 27 applies certain articles from 15 March 2026,
  2 September 2026 and 2 March 2027.

EPIP is therefore named in EU law as the 2025 CEN/TS edition, mandatory for rail passenger
timetables. Its text is sold by standards bodies and was not read. The only open EPIP schema is the
archived 2021 Data4PT XSD (§5).

## 3. Catalogue census (`scripts/01_catalogues.py`, `scripts/01b_access.py`)

| Country | NAP / source | Endpoint | Access found |
|---|---|---|---|
| FR | transport.data.gouv.fr | `/api/datasets`, resources with `format == NeTEx` | anonymous |
| NO (EEA) | Entur | public bucket listing `marduk-production/outbound/netex/` | anonymous |
| NL | NDOV Loket | directory listing `data.ndovloket.nl/netex/<operator>/` | anonymous |
| BE | transportdata.be | CKAN `package_search?q=netex` | anonymous |
| LU | data.public.lu | udata `datasets/?q=netex` | anonymous |
| DE | Mobilithek | `offers/search` (free text "NeTEx") | metadata anonymous; files need an account |

`data/nap_access.csv` records what the other probes showed and how to read them:
- ES: the file API answers 401 (registration).
- SE: the national file answers 403 without a key.
- FI: an internal API answered 401 "Invalid cookie" (not assessed).
- AT and CH: our guessed CKAN paths hit HTML "not found" pages (wrong endpoint, not a refusal).
- CH, rechecked with two requests on 2026-10-03: the CKAN API answers 403. A 1 kB `Range` GET on
  the `timetablenetex_2026` permalink returned HTTP 206, so the 663,744,713-byte national NeTEx
  timetable is anonymously downloadable. It exceeds this study's 300 MB limit and would not have
  been sampled.

Italy and Portugal were not probed.

Definitions:
- **resource**: one listed file.
- **feed**: the logical dataset. For NL, one operator directory; for LU, the 311 weekly snapshots
  are one feed; elsewhere, one resource. Feeds are the unit of the census.
- **size**: from the catalogue, or from the `Content-Length` of a HEAD request (or of a GET whose
  body is not read). A HEAD size can be wrong: Voi's server reported 137 bytes for a file that
  downloaded as 474 kB.
- **updated**: the catalogue's resource date. For DE it is the offer's `created` date.
- **licence**: counted only when it is machine-readable and not "not specified".

Raw catalogue responses contain third-party contact details, including personal e-mail addresses.
They are kept in `work/raw_catalogs/` and are **not published**. Only derived CSVs without contact
fields are in `data/`.

## 4. Sample (`scripts/02_sample.py`, `data/sample.csv`, 44 datasets)

- **FR (15):** public-transit resources with HTTP 200 and a known size ≤ 300 MB. That is 131 of the
  164 public-transit resources; 32 had no size and 1 failed. 5 were drawn per size tercile with
  `random.Random(20261002)`. Terciles are equally weighted, so FR results are not population
  estimates.
- **NO (6):** the three largest regional authorities (RUT, SKY, INN) and three rail operators (VYG,
  SJN, GOA). Rail was chosen as a part of the network that is clearly in TEN-T scope; the
  comprehensive TEN-T also covers urban nodes, so this is a simplification.
- **NL (16):** the newest file of every NDOV Loket directory except `test`. This brings in a 2018
  directory (AVV), a codespace list (ENUM) and a stop file (EPIAP).
- **BE (6):** every transportdata.be NeTEx resource with a direct download. This brings in two
  car-park files and one scooter-operator file.
- **LU (1):** the newest snapshot.

Every result is reported with a **content class** derived from the data (`04_aggregate.py`):
- `timetable` (ServiceJourney present);
- `stops` (StopPlace/Quay, no journeys);
- `parking` (a `…NETEX_PARKING` frame);
- `scooter-sharing` (the Voi feed);
- `codespace-list`.

## 5. XSD validation (`scripts/03_validate.py`)

Each sampled file was downloaded to `work/dl/`, processed and deleted. Up to five worker processes
ran in parallel, so `work/` held up to five datasets at once; the recorded peak was 302 MB.
Documents were parsed with lxml 6.1.3 / libxml2 2.14.6 (`huge_tree`, no network, no entities) and
validated against:

| Key | Schema | Pin |
|---|---|---|
| `netex_1_3_2` | `xsd/NeTEx_publication.xsd` | TransmodelEcosystem/NeTEx tag v1.3.2 = `4f42794047ec9944fd38e4497f3af142a33462c8` |
| `netex_2_0_0` | same file | tag v2.0.0 = `a94e5e1752bcc13aabb8a1f3d018dc08e6978f42` |
| `epip` | `NeTEx_publication_EPIP.xsd` | TransmodelEcosystem/NeTEx-Profile-EPIP `e5eaf83f15f7fd8db7991a4a8323b6ff7905c13a` (archived; "created in 2021 in the context of the Data4PT project, based on the NeTEx XSD v1.3.1. This XSD is no longer maintained by the NeTEx subgroup.") |

`run.sh` downloads the schemas by these SHAs.

**What the XSD checks.** Validation is per document. Keyrefs on (`@ref`, `@version`), such as
`StopPlace_KeyRef`, skip references without `version`. `*_AnyKeyRef` constraints keyed on `@ref`
alone, such as `Codespace_AnyKeyRef`, check unversioned references too. A reference to an object in
another file, a stop registry or the profile therefore fails the XSD exactly like a broken one.

**Budgets and caps.** Not every byte was XSD-validated.

- **Budgets.** Per dataset and schema, documents are validated in file-name order. A document is
  skipped when it is larger than `MAX_XSD_BYTES` or would exceed the remaining `XSD_BUDGET`, and
  later smaller documents are still validated (greedy, not a prefix).
- **Caps changed mid-run.** The 16 datasets finished before the interruption of 2026-10-02 (~22:06)
  used 300 MB / 400 MB. The rest used 150 MB / 150 MB. This was lowered to finish in time, which
  made four Dutch single-document files "not checked". After the review, those four were
  re-processed with the original 400 MB cap, but with the memory guard below active. Only AVV
  (220 MB) was checked, and only against 1.3.2. ARR, GVB and Keolis (185–358 MB) were skipped
  because free memory was below the guard on this 8 GB machine, so they remain "not checked". The
  631 MB SNCF file exceeds every cap used.
  Parameters are stored per record (`xsd_params`).
- **Error lists are truncated.** Only the first 20,000 errors per document are categorised. Totals
  are counted in full; per-category counts are lower bounds. We therefore report **datasets**, not
  error counts, and give both totals in `summary.json` (`xsd_error_totals`).
- **Memory guard.** After the review, a document is also skipped when free memory is below six times
  its size plus 1 GB (`skipped_memory_guard`).

**Verdicts:**
- **valid**: every document checked and valid;
- **valid-partial**: all checked documents valid but some skipped (coverage in bytes is reported per
  dataset);
- **invalid**: at least one checked document failed;
- **not-checked**: nothing checked.

The best of the two NeTEx releases is kept, because publishers' declared versions (1.09, 1.15,
`ntx:1.1`…) do not map to release tags.

## 6. Consistency checks (`prototype/netex_lint/core.py`, rules in `prototype/RULES.md`)

- **The pass.** A streaming parse (`iterparse`, elements cleared) over all documents of a dataset.
  The parse is streaming, but ids, definitions and references are **held in memory**, which is
  O(ids + refs): TEC alone has about 6.9 M references and 6.6 M ids. That, with up to five workers
  in parallel on an 8 GB machine shared with other jobs, is the likely reason the Ruter, Skyss and
  SNCB runs stalled under swap.
- **Rule versions.** Rules changed twice:
  - **v2 (during the run):** in-file duplicates are split from cross-file redundancy, and French
    stop ids are accepted.
  - **v3 and v4 (after the review).** v4 only adds that, when frames carry validity conditions,
    frame-level validity decides expiry; it was applied to the two datasets earlier rules flagged.
    v3:
    - open-ended validity (no `ToDate`) is never "expired";
    - a missing XML declaration is not "non-UTF-8";
    - U+FFFD is reported apart from double encoding;
    - the French id codification is reported as a recommendation (info), with shares;
    - every finding carries a `source`.
- **Applying v3.** Records whose v3 result needs the raw data were re-scanned with
  `CHECKS_ONLY=1 03_validate.py <slugs>`: every French-profile dataset, Voi, and the four re-processed
  Dutch files. The others were upgraded from their stored summaries by `03b_upgrade_records.py`.
  Each record states its `rules_version`.
- **Calendars.** `DayTypeAssignment` patterns are not expanded, so only some datasets yield a
  calendar end date (denominator in `summary.json`, `calendar_extracted`).

## 7. Prior work and validator landscape (`scripts/00_prior_work.py`, `scripts/00_landscape.py`)

- **Literature** (2026-10-02/03): arXiv API (`all:NeTEx`; `all:"national access point" AND
  all:transport`; `all:MMTIS`); Crossref (`query.bibliographic`, NeTEx validation and NAP/MMTIS
  terms); Semantic Scholar (keyword search returned no data without a key, so the DOIs of the closest
  papers were looked up directly). Counts are in `data/prior_work.csv`.
- **Code:** GitHub code search `netex repo:etalab/transport-site validator`, and `gh api` metadata of
  14 repositories plus the Greenlight Docker image (`data/validator_landscape.csv`).
- **NAPCORE:** the deliverables page.

## 8. Threats to validity

- **Coverage.**
  - Five NAPs (four EU Member States plus Norway). Germany (DELFI), Spain, Sweden, Italy, Austria,
    Finland and Switzerland are not validated: some need registration (lawful under Art. 4(4)), some
    were not assessed, and the Swiss file exceeds the size limit.
  - Ruter, Skyss and SNCB were not completed.
- **Content mix.** The sample includes stop, parking, scooter and codespace files. Results are given
  per content class.
- **Schemas.** We validate against public releases, not against the snapshot each publisher used.
  The EPIP XSD is a 2021 schema that predates CEN/TS 16614-4:2025: failing it says little about
  conformance to the current EPIP.
- **Partial coverage.** "Valid-partial" can rest on as little as 2.4 % of a dataset's bytes.
- **Re-runs.** A full re-run with today's defaults (150 MB caps) would not reproduce the 16 early
  records (300/400 MB). The per-record parameters make the difference explicit.
- **Rules.** The profile quotes were selected by the agent and have not been checked by a French- or
  Nordic-profile expert.
