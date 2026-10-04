# S13 — Method

*EasyxLab · study S13 · working draft*

The analysis plan below was written on 2026-10-04 after the scouting pilot (287 registrations
on 2 April 2025; a lower pace after May 2025) and after we had looked at the monthly counts by
province and by kind of dwelling. It was frozen before any of the measures in §1.3–§1.7 was
computed. The freeze guards the windows, baselines and contrasts, not ignorance of the likely
result. Its SHA-256 is recorded in `STATUS.md`. Later changes are listed in §9.

<!-- FROZEN-PLAN-START -->
## 1. Analysis plan (frozen)

### 1.1 Data, unit and date

- **Primary file:** the copy of the Comunitat Valenciana tourist-dwelling registry
  (`tur-gestur-vt`) downloaded on 2026-10-04. One row is one registered dwelling, identified by
  its `signatura` (`CV-VUT<7 digits>-<A|CS|V>`).
- **Date:** `fecha_alta` ("Fecha de alta en el registro"). §1.4 tests what it records.
- **Series:** daily and monthly counts of dwellings by `fecha_alta`, for the Comunitat as a
  whole, by province (03 Alicante, 12 Castellón, 46 Valencia) and by municipality (INE code =
  `cod_provincia` + `cod_municipio`).
- **Analysis end:** 2026-08-31, so that the last month has had at least a month to be filled
  in. September 2026 is reported as provisional and is not used in any measure.
- **Working day:** Monday to Friday, except national and Comunitat Valenciana holidays
  (`data/holidays.csv`, from the BOE resolutions). All other days are non-working days. Local
  holidays are ignored.

### 1.2 Who the rule reaches: kind of dwelling

LPH art. 7.3 reaches dwellings in a building under horizontal property. The registry does not
say this directly, but the address carries the cadastral unit part `ES:<stair> PL:<floor>
PT:<door>`. At ingest, before the address is dropped:

- `whole_parcel`: `PL:OD PT:OS`. This is the cadastral notation for a property that is not
  divided into units, typically a detached house. **Not reached by art. 7.3: the control
  group.**
- `in_building`: any other floor or door value. This is a unit in a divided building or
  complex. **Reached by art. 7.3: the exposed group.**
- `unknown`: no floor or door at all.

Validation, reported but not used as a rule:
- the share with cadastral unit number `0001`;
- the share sharing a cadastral parcel with another registered dwelling.

Sensitivity: `unknown` is added to `in_building`.

### 1.3 Q1: was there a rush? (D = 2025-04-02, the last day before the rule took effect)

- **R1 peak.**
  - The count on D.
  - The median and maximum of working days from 2025-01-07 to 2025-02-28.
  - The ratio of the count on D to that median.
  - The rank of D among all days from 2016-01-01 to 2026-08-31.
- **R2 run-up excess.**
  - Window W = D−13…D (2025-03-20 to 2025-04-02).
  - Baseline B = D−87…D−34 (2025-01-05 to 2025-02-27).
  - Expected E = Σ over the days of W of the baseline mean count for that day type (working
    or non-working).
  - Reported: observed O, E, O − E and O/E.
  - Computed for all dwellings, for each kind and for each province.
- **R3 placebo.**
  - The R2 ratio is computed for every working day e from 2023-04-03 to 2026-08-31 taken as
    the window end, with the same offsets.
  - Ends from 2025-03-01 to 2025-05-31 are excluded.
  - Reported: the share of placebo windows with a ratio at least as large as D's, the
    largest placebo ratio, and every placebo window with O/E ≥ 1.5. This is computed for all
    dwellings and for each kind.
- **R4 contrast between kinds.**
  - The contrast is log(O/E) for `in_building` minus log(O/E) for `whole_parcel`.
  - Its empirical p-value is the share of placebo windows with a contrast at least as large.
  - The Poisson approximate 95% CI of the ratio of ratios is also reported. Its variance is
    1/O + 1/B for each kind, where B is the baseline count scaled to W.
- **R5 after the deadline.**
  - O/E for D+1…D+28 (2025-04-03 to 2025-04-30), with the same baseline B.
  - This shows whether registrations were brought forward from the following weeks.

### 1.4 What the date records

- **E1.** The share of registrations dated on non-working days, 2023–2026 (counted up to
  2026-08-31), overall and by kind. A date set when a civil servant processes a file would
  almost never fall on a Sunday.
- **E2 processing order.** Each province uses its own number counter: Alicante from 490000 in
  May 2022; Castellón and Valencia each have a separate low counter.
  - For each dwelling dated from 2023-01-01, lag = (the latest `fecha_alta` among dwellings
    with a lower number in the same counter) − (its own `fecha_alta`).
  - Reported: the distribution of the lag (0, ≤3, >7 and >30 days), for 2023–2026 and for
    the dwellings dated D.
  - Also reported: the latest `fecha_alta` among the dwellings numbered just before the last
    D-dated dwelling.
- **E3 publication lag.** Using three copies of the file (2026-09-14 from the Internet
  Archive, 2026-10-03 from study S11, and 2026-10-04):
  - the dwellings that appear after 2026-09-14 with a `fecha_alta` on or before the latest
    date in the 2026-09-14 copy;
  - for the dwellings dated 2026-09-01…the latest date in that copy, the share already
    present on 2026-09-14.
- **E4.** Dates that changed between copies: how many, and in which direction.

### 1.5 Q2: did the pace fall afterwards?

- **F1 (the scout's measure, recomputed):** mean monthly count from May 2025 to August 2026,
  against the mean monthly count of 2024.
- **F2 (main):**
  - Post12 = 2025-09-01…2026-08-31, against Pre12 = 2023-09-01…2024-08-31. Both are twelve
    full months; Pre12 ends before Decreto-ley 9/2024 and before LO 1/2025 was published.
  - Ratio Post12/Pre12 for all dwellings, for each kind and for each province.
  - CI from the month-to-month variance (delta method on the log of the ratio of means).
- **F2-DiD:** the F2 ratio for `in_building` divided by the F2 ratio for `whole_parcel`, with
  a delta-method CI.
- **F3 timing:**
  - Monthly ratio against the same calendar month of Pre12 (Sep–Dec against 2023,
    Jan–Aug against 2024), for every month from 2025-01 to 2026-08, overall and by kind.
  - The share of `whole_parcel` among new registrations, by month.
- **F4 without the two cities with municipal suspensions:** F2 and F2-DiD excluding València
  (46250) and Alacant/Alicante (03014).

### 1.6 Survivorship

- **S1 churn.**
  - Dwellings present on 2026-09-14 and absent on 2026-10-04, by `fecha_alta` year.
  - Annualised removal rate = removed ÷ present on 2026-09-14 × 365 ÷ 20.
- **S2 number gaps.**
  - In each province counter, every integer between two consecutive numbers that are
    present and absent from the 2026-10-04 copy is a gap.
  - Each gap is assigned the `fecha_alta` month of the lower neighbour.
  - A gap is a cancelled dwelling, a refused or withdrawn file, or a number never used. Gaps
    are therefore an **upper bound** on cancellations of numbered dwellings.
  - Reported: gap share = gaps ÷ (present + gaps), by month from 2023-01 to 2026-08.
- **S3 bounds.**
  - F2 and F2-DiD are recomputed with every Post12 gap added to the exposed series (and, for
    the ratio over all dwellings, to Post12).
  - For the DiD, every Pre12 gap is added to the control series' Pre12.
  - This is the worst case for "it fell, and it fell more for flats".
  - For R2, the gap share of the numbers issued for dwellings dated in W is reported against
    that of B.

### 1.7 Comparators and the INE check

- **Other regions.** Every other regional registry found with a usable registration date for
  tourist dwellings goes through R1–R3 and F2 on its own daily series. Its working days use
  the national holidays and that region's holidays where available. Catalonia, where the LPH
  does not govern horizontal property, is the region the rule does not reach. Descriptive
  only: no pooled test.
- **INE experimental statistic "Viviendas turísticas en España"** (table 39363): listings in
  2024M08, 2024M11, 2025M05, 2025M11 and 2026M05, for the Comunitat Valenciana and its
  provinces, Catalonia and Spain. These are set beside the registry's new registrations in
  the same intervals. They are a consistency check, not an outcome.

### 1.8 Publication

`data/` holds aggregates only:
- counts per day × province × kind;
- counts per month × municipality × kind;
- measures, gaps and churn per month or year.

No registration number, name, address or cadastral reference is published.
<!-- FROZEN-PLAN-END -->

## 2. Sources

All downloads were made on 2026-10-04 unless stated. `data/sources.json` gives each URL, the
fetch time and the SHA-256 of the minimal copy we kept.

| source | host | what we kept | rows | licence as stated |
|---|---|---|---|---|
| GVA, viviendas de uso turístico (`tur-gestur-vt`), daily | dadesobertes.gva.es | number, province, municipality, `fecha_alta`, places, rural flag; derived kind (§1.2) | 90,091 | "Creative Commons Attribution" (dataset page) |
| same file, Internet Archive capture 2026-09-14 16:40 UTC | web.archive.org (`id_` raw URL, found with the CDX API) | same columns | 90,043 | as above |
| same file, study S11's copy of 2026-10-03 10:57 UTC (optional; not used by the analysis since the coordinator review) | local, SHA-256 checked against S11's record | number, municipality, province, date | 90,097 | as above |
| same file, read again on 2026-10-04 for the building key only (`gva_bkey_2026-10-04.csv`; all 90,091 dwellings matched by number) | dadesobertes.gva.es | number; salted building key; whether a cadastral reference is filled in | 90,091 | as above |
| Ajuntament de València, news notes of 31 January 2025 and 20 March 2026 | www.valencia.es (`/cas/actualidad/-/content/…`, allowed; the short `/-/` paths are disallowed and were not used) | full text, quoted | — | — |
| NBER abstracts of w35794 and w32537 | www.nber.org | abstract and citation | — | — |
| GVA, historical list and last-period list (`dades-turisme-habitatges-comunitat-valenciana-2025`) | dadesobertes.gva.es | number, status, type, province, municipality, "Situación" (A building, B bungalow or terraced, C chalet or villa), places, dates of registration and cancellation; floor and door as two yes/no flags | 182,893 (extract of 2025-01-10); 101,408 (2025-01-24) | "Creative Commons Attribution" (dataset page) |
| OpenRTA, Registro de Turismo de Andalucía | datos.juntadeandalucia.es | code, type, province, municipality (INE code), `registration_date`, `activity_start_date` | 173,965 rows read, 153,496 tourist dwellings | "Reconocimiento 4.0 Internacional (CC BY 4.0)" |
| REATE, viviendas para uso turístico en Euskadi | opendata.euskadi.eus | number, type, province, municipality, `FechainscripcionREATE` | 4,754 dwellings (+ 749 rooms, excluded) | "Licencia: Información legal" (not read) |
| Habitatges turístics de Mallorca | intranet.caib.es (CAIB CKAN) | number, type, municipality, "Inici d'activitat" | 16,781 dwellings | "Creative Commons Attribution" |
| INE, Viviendas turísticas en España (experimental), table 39363 | www.ine.es | whole table | — | INE legal notice: reuse with attribution |
| INE municipality dictionary 2026 | www.ine.es | code and name | 8,132 | as above |
| BOE: holidays for 2023–2026; LO 1/2025; LPH; RD 1312/2024; Ley 15/2018; Ley 39/2015; Ley 3/2026; CCCat | www.boe.es (open-data API and `txt.php`) | full texts, grepped literally | — | BOE legal notice |
| DOGV: Decreto 10/2021 (consolidated), Decreto-ley 9/2024 | dogv.gva.es | full texts | — | — |

**Repairing the Andalusian export.** OpenRTA's header has 72 names, but most rows of tourist
dwellings carry 92 fields: 20 unnamed fields sit before `municipalities`. Every named column from
`municipalities` onward is therefore read from the right end of the row (index = row length −
(72 − header index)). Rows with extra `|` inside quoted text are anchored on the field that
matches the code pattern (`XXX/PP/digits`) followed by an eight-digit date. Each row is accepted
only if both match. This recovered all 153,496 tourist dwellings, every one with an INE
municipality code. The 1,467 rows left unrecovered are guides, agencies and activities. Code:
`scripts/comparators/andalucia.py`.

Personal data. The GVA file carries the dwelling's name (sometimes a person's name), the street
address with floor and door, the cadastral reference and a website. OpenRTA carries holders'
names, e-mails and phones. These columns were dropped while streaming and never written to disk.
The only things derived from them before they were dropped are:
- the dwelling kind;
- whether the cadastral unit number is 0001;
- how many registered dwellings share the cadastral parcel;
- floor and door as yes/no flags.

## 3. Access: User-Agent, rate, robots.txt

- User-Agent `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)` on every
  request.
- At most one request per second per host, or the host's Crawl-delay if larger
  (dadesobertes.gva.es declares 10 s). The clock is shared by all processes. Three requests
  broke the rule: on datadista.com, catalegdades.caib.cat and www.turgalicia.gal, the first
  request followed the host's robots.txt request after 0.66–0.88 s.
- robots.txt is read under RFC 9309 before every request (`scripts/polite.py`), and every
  request is logged in `work/fetch_log.jsonl`.
- 252 requests were sent to 47 hosts, and robots.txt stopped 16 more before they were sent.
  - Most went to api.crossref.org (31), www.boe.es (27), dadesobertes.gva.es (17),
    web.archive.org (16), datos.gob.es (15), intranet.caib.es (12) and export.arxiv.org (9).
  - The 11 GitHub searches went through the `gh` client.

robots.txt was respected to the legal minimum: wherever it can work as a reservation of text and
data mining on content we analyse (Directive 2019/790 art. 4(3); TRLPI art. 67), or where terms
we accepted require it. In practice we followed it everywhere, with one exception:

- **dadesobertes.gva.es** disallows `/api/`, `/dataset/*/history` and `/revision/`. We used
  neither the CKAN API nor the revision history. Metadata came from the dataset pages, which are
  allowed.
- **export.arxiv.org** disallows all crawlers. It is the one exception. As in study S11, its API
  was queried under the arXiv API Terms of Use, which grant programmatic access, at one request
  every 3.1 s (8 queries, `scripts/prior_arxiv.py`).
- **Not used because robots.txt disallows them:**
  - datos.comunidad.madrid: `User-agent: *` / `Disallow: /`. Its licence page sits behind the
    same rule, so we could not verify a licence.
  - opendata.aragon.es: `Disallow: /GA_OD_Core/download*`.
  - datosabiertos.navarra.es: `Disallow: /datastore/`; the dataset has no tourist dwellings in
    any case.
  - sforms.gva.es: unreachable robots.txt, which counts as disallow-all.

  The Madrid dataset, owners' declarations with a historical file, was the most promising
  comparator. We did not bypass the rule, and we did not use an archived copy instead.
- **Rule broken once, in the prior-work search:** one public GitHub notebook was downloaded with
  `curl` and the study User-Agent instead of `polite.py`. Its content was used only to confirm
  that it holds annual counts.

## 4. Definitions used in the measures

- **Registration:** one row of the GVA file, dated by `fecha_alta`.
- **Counters:** each province numbers its dwellings separately: Alicante (`-A`, from 490000 since
  May 2022), Castellón (`-CS`) and Valencia (`-V`).
- **Expected count (R2, R5):** the baseline mean per day type, summed over the window.
  - Day types: working day and non-working day (weekend, national or Comunitat Valenciana
    holiday).
  - Baseline: from 87 to 34 days before the window's last day.
  - The comparators use their own regional holidays (Andalucía, País Vasco, Illes Balears).
- **Placebo windows (R3):** the same statistic for every working day from 2023-04-03 to
  2026-08-31 taken as the window end, leaving out ends from 2025-03-01 to 2025-05-31. That gives
  791 windows in the Comunitat Valenciana.
- **Periods (F2):** Pre12 = September 2023–August 2024; Post12 = September 2025–August 2026.
  Both are full calendar months.

## 5. Checks of the kind classification (`data/summary.json`, `data/date_semantics.json` E5)

| kind | dwellings (4 Oct 2026) | cadastral unit 0001 | parcel shared with another registered dwelling |
|---|---|---|---|
| in_building | 74,888 | 3.7% | 84.8% |
| whole_parcel | 13,992 | 98.5% | 4.6% |
| unknown | 1,211 | 65.3% | 4.5% |

The GVA's own "Situación" in the historical list (dwellings in both lists):

| Situación | in_building | whole_parcel | unknown |
|---|---|---|---|
| A, in a block or building | 49,182 | 1,418 | 87 |
| B, bungalow or terraced | 6,588 | 1,628 | 88 |
| C, chalet or villa | 1,893 | 7,960 | 387 |

Our classification follows the legal division of the property, not the building's shape.
Bungalows and terraced houses in complexes are mostly divided into cadastral units, and complexes
fall under the LPH too (art. 24). The kind `unknown` is almost absent before 2025: about 6 a
month in 2023–2024 and 13–51 a month in 2025–2026. It is not a general change of address format:
- 138 of the 176 unknowns of January–April 2025 are in the city of València, and 194 of the 570
  since 2025;
- in the run-up window, 50 of 59 are in the city and 52 have a cadastral unit other than 0001,
  so they are flat-like.

Counting `unknown` as exposed gives a run-up contrast of 2.04; counting it as control gives
1.50. The validation shares are stable across registration years: cadastral unit 0001 at 3–5%
for in_building and 98–100% for whole_parcel, every year from 2016 to 2026
(`summary.json` → `post_review.kind_validation_by_year`).

## 6. Statistics

- **Run-up CIs (R4):** three versions.
  - The frozen-plan Poisson approximation scales the baseline count to the window length. It is
    wider than the delta-method version, which uses 1/B for the baseline.
  - Both ignore overdispersion.
  - The placebo-calibrated interval uses the standard deviation of the placebo log contrasts
    (0.26). It is the widest, and the one to read.
- **Empirical p:** (1 + placebo contrasts ≥ observed) ÷ (1 + placebo windows).
  - Consecutive windows overlap (lag-1 autocorrelation of the contrast 0.93), so the 791 windows
    are worth roughly 65 independent ones.
  - We therefore also report p over every tenth window (80 windows). The smallest attainable p
    is then 1/81 = 0.012.
- **Ratios of twelve-month means (F1, F2, F5):** delta-method CI on the log scale, with the
  month-to-month sample variance of each period. Seasonality is left in that variance, so these
  intervals are wide.
- **Ratios of ratios:** the log variances are added.
- No multiple-testing correction. The headline tests are R2 against its placebo distribution
  and F2-DiD; the rest is description.

## 7. Survivorship, in three layers

1. **Removals between copies (S1).** 248 dwellings removed between 14 September and 4 October
   2026: 5.0% a year. For dwellings registered in 2025–2026: 19 of 14,228.
2. **Number gaps (S2).** Each gap is an upper bound on cancelled numbered dwellings.
   - Pre12 has 1,688 gaps; Post12 has 106.
   - In the run-up window, the gap share is 3.4%, against 6.3% in its baseline, so the window
     did not lose more than its baseline.
3. **Historical list (S4).**
   - 14,177 dwellings were registered in Pre12: those in the GVA list of 10 January 2025,
     including those cancelled before then, plus those that reached the registry after that
     date.
   - 12,941 of them are in today's file: a survival of 91.3%.
   - Buildings (Situación A+B) survived at 91.1% and chalets (C) at 92.3%.
   - The number gaps (1,688) are more than the 1,236 Pre12 registrations missing from today's
     file, as an upper bound should be. 425 of those 1,236 had already been cancelled by 10
     January 2025.
   - An older Benidorm series (suffix `BM`, 255 Pre12 registrations in the list) does not map
     onto today's numbers and is left out of S4. Today's file has 212 dwellings dated in Pre12
     on Alicante's old counter, which are probably the same dwellings. Adding both sides gives
     14,432 registrations, a survival of 91.1% and a corrected ratio of 0.43, against 0.44.

## 8. Privacy and publication

- `data/` holds counts and summary statistics:
  - per day, by kind (whole region) and by province;
  - per month, by province and kind, and by municipality;
  - the run-up excess for the ten municipalities with the largest excess, and the rest together.
- **Small cells.** No table below province level has a cell under 5.
  - In `monthly_municipality.csv`, a municipality with fewer than 5 registrations in a month is
    merged into a row «other municipalities of <province> (each under 5)». If that row is itself
    under 5, it is published as «<5». This covers 3,066 municipality-months.
  - `monthly_province_kind.csv` shows province-level cells under 5 as «<5».
  - Daily counts are published only for the whole region (by kind) and by province.
  - Until the coordinator's review, the municipal table had 3,030 cells equal to 1. It was
    replaced.
- No registration number, name, address, cadastral reference or row is published. The examples in
  the code and tests use synthetic numbers that do not exist in any copy of the registry.
- Row-level minimal copies stay in `data/raw/` (git-ignored). They include a salted hash of each
  dwelling's building: street and first street number, within the municipality. The salt is
  random for every run and never stored, so the key cannot be reversed or linked to another
  copy.

## 9. Deviations from the frozen plan, and additions

1. **The GVA's historical list (added after the freeze).** We found it after freezing the plan
   (fetched 2026-10-04 12:38 UTC). It is used for:
   - survival measured directly (S4, and the S4-DiD that divides Pre12 by the survival of each
     building type);
   - checking the kind classification against "Situación" (E5);
   - the publication lag in January 2025 (E3b): 103 dwellings in the list of 24 January are
     dated on or before 10 January but are missing from the list of that day.
2. **F5 (added).** September 2024–February 2025 against a year earlier. This separates
   Decreto-ley 9/2024, in force 2024-08-08, from the LPH.
3. **Run-up without the two cities (added).** The plan had this sensitivity only for the fall
   (F4). We also computed R2 and R4 without València (46250) and Alicante (03014), and R2 for
   the city of València alone.
4. **The CI of R4.** The frozen text defines B as "the baseline count scaled to W". That is not
   the delta-method variance of log E. We report it as frozen, which is wider than the
   delta-method CI, and add the delta-method CI. Both ignore overdispersion; the
   placebo-calibrated interval of item 9 does not.
5. **S3, worst case:** every Pre12 gap goes to the whole-parcel control. The DiD then turns to
   1.34, so S3 is uninformative for the DiD: gaps cannot be split by kind, and putting all 1,688
   on houses (pre-period count 1,870) is not plausible. S4 measures survival by building type
   and replaces it.
6. **E6 (added).** We set our counts beside the GVA's published totals; they do not match
   (paper §5.6).
7. **Holidays.** Holidays for Andalucía, País Vasco and Illes Balears were parsed from the same
   BOE resolutions (`scripts/build_holidays.py`). For the Comunitat Valenciana and Catalonia the
   output equals the legal baseline's list.
8. **Comparators.** Catalonia has no date in its open registry, so the region the LPH does not
   reach could not be measured (§10). Mallorca had no registrations in 2025 (capped places) and
   gives no information.

9. **After the independent review (`private/REVIEW.md`).** All of the following are reported
   in `summary.json` → `post_review`.
   - **Placebo inference on spaced windows** (every tenth working day; 80 windows) and
     **placebo-calibrated intervals**:
     - all dwellings: 0 of 80 as high, p = 0.012;
     - flat-house contrast: 0 of 80, p = 0.012, interval 1.21–3.37;
     - without the two cities: 2 of 80, p = 0.037, interval 1.06–2.93.
   - **The same calendar window in 2023, 2024 and 2026.** The ratios were 1.59, 1.27 and 1.19.
     The flat-house contrasts were 0.86, 1.00 and 1.57. The seasonally adjusted 2025 excess is
     441 (ratio 1.68).
   - **Older reference periods for the fall.** Against September 2022–August 2023, the overall
     ratio is 0.59 and the flat-house contrast 0.80 (CI 0.57–1.13). Against 2022, they are 0.88
     and 0.90. Survival of those cohorts is 84.9% and 81.5%, and it does not differ by building
     type.
   - **Houses' share of new registrations by half-year,** and the share of registrations on
     non-working days by year: 2.7%, 5.7%, 8.5% and 8.1% for 2023–2026.
   - **E3c.** All 23 dwellings dated in 2026 that appeared after the 14 September copy carry
     numbers above every number published on that date.
   - **The split of the unknown kind** (§5), **S4 with the Benidorm series** (§7), and **the
     kind validation by registration year**.
   - **The placebo exclusion extended to D+87** (2025-06-28). Windows ending in June 2025 have
     baselines that contain the run-up; the frozen plan should have excluded them. With them
     excluded there are 772 windows, and still none as high (maximum 1.64).
   - **Wording.** The claims of README and paper were rewritten: the flat-specific gap is dated
     October 2025 and is not attributed to the rule, and the comparators are described as
     processing-like dates.

10. **After the coordinator's review (`private/REVIEW-coordinator.md`).** All of the following
    are in `summary.json` → `coordinator_review`.
    - **Within-municipality contrast** (primary flats-against-houses test). Poisson model
      O_mk ~ E_mk · a_m · b_k, with municipality and kind effects, fitted on the municipalities
      with both kinds in the baseline (35 municipalities; 826 flats and 54 houses in the
      window).
      - 1.73, with 6 of 78 spaced placebo windows as large: p = 0.089.
      - Placebo-calibrated interval 0.92–3.22, from a placebo SD of the log contrast of 0.32.
        The reviewer had 0.94–3.16, from an SD of 0.31.
      - Without Torrevieja: 1.79 (p = 0.101). Without València, Alicante and Torrevieja: 1.73
        (p = 0.101; the reviewer had 8 of 78).
    - **The excess by municipality** (`rush_by_municipality.csv`). València city +200 and
      Torrevieja +151 of 637 (55%).
    - **R2 and R5 for València city, Torrevieja and the rest**, with the same calendar window in
      2023, 2024 and 2026 for each.
    - **The spaced placebo set** now leaves out the June-2025 ends whose baselines contain the
      run-up: 78 windows, so p = 0.013 where it was 0.012.
    - **The deadline cohort of València city**, using the salted building key (§8):
      - 172 dwellings in 55 buildings by street and number (the reviewer's stricter key: 76);
      - 89 in buildings with 5 or more;
      - 73 without a cadastral reference.
    - **Filing events.** One per building, day and kind: pooled contrast 1.81.
    - **Paired monthly log-odds of flats to houses.** Against Sep 2023–Aug 2024: 0.70
      (0.62–0.80). Against Sep 2022–Aug 2023: 0.83 (0.71–0.97; t(11) 0.69–0.99). Against 2022:
      0.92. The reviewer's interval against 2022–23 was 0.73–0.94; our pairing (the same calendar
      month) and SE (the SD of the 12 differences ÷ √12) give a wider one.
    - **The Generalitat's year.** Surviving dwellings dated 8 Aug 2023–7 Aug 2024 against 8 Aug
      2024–8 Aug 2025: 13,451 and 11,237 (0.84). With the earlier year rebuilt from the
      historical list (14,528): 0.77.
    - **Publication.** Small cells (§8), synthetic numbers in tests and docstrings.
    - **Reproducibility.** The analysis no longer depends on the S11 copy. It picks the copies
      itself (`pick_copies`). `run.sh` fetches the public sources when no local copy exists.
      `import_s11_copy.py` exits 0 when the copy is absent.
    - **Text.** New central claim. València's dates of 31 January and 30 April 2025 are quoted
      from the city's site. Other corrections:
      - the w32537 authors;
      - "strong", not "decisive", for the date test;
      - Terra Meridiana's context;
      - the two limbs of the LPH's second additional provision;
      - the publication dates of the annulments;
      - the historical list's extraction date, which is inferred;
      - the pacing breaches (§3).

## 10. What was not possible

- **An outside control region.** Catalonia's open registry (`t2h3-cgys`) has no registration
  date. Its numbers are sequential, but the Internet Archive holds no copy from before June
  2025.
- **Madrid, Aragón and Navarra:** blocked by robots.txt (§3).
- **Canarias, Castilla y León, Castilla-La Mancha and Galicia:** no per-dwelling registration
  date. Galicia publishes only a monthly net stock.
- **Cancellations after January 2025 by kind.** The open file has no history. The historical
  list stops on 10 January 2025, and the Internet Archive has a single capture (14 September
  2026). The March and June 2025 mass cancellations reported in the press (886 and 10,601) can
  be bounded only through the number gaps.
- **Whether an entry is a new dwelling.** Neither file says whether a registration is a first
  registration, a new declaration after a change of owner (required since Decreto-ley 9/2024),
  or a re-registration after a cancellation.
- **The Supreme Court's plenary rulings of October 2024 on art. 17.12.** They were suggested by a
  reviewer, but we could not read them in CENDOJ, so we do not cite them.
- **The cause of Torrevieja's rise.** No municipal act was found.
- **A municipal date in València city on 2 or 3 April 2025.**
  - The city's notes give the suspension of 28 May 2024, extended on 28 January and 30 April
    2025, and the draft ban of 31 January 2025.
  - We found no act of 2 or 3 April. The provincial bulletin was not searched: our web-search
    budget ran out.
- **The meaning of the Andalusian and Basque dates.** Neither registry describes its date field,
  and both behave like office-processing dates.
  - Andalucía had no registrations on the weekend of 29–30 March 2025 (60 and 50 a week
    earlier), and 220 and 409 on 3–4 April, after the deadline. 9.4% of its 2023–2026
    registrations fall on non-working days.
  - País Vasco has 0.6% on non-working days.

  Their pre-deadline peaks show bulk processing around the deadline, not filing behaviour.
