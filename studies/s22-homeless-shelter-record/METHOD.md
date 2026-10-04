# S22 — Method

*EasyxLab · study S22 · working draft*

## 1. Design

- **In sample (2012–2024): descriptive.** All editions had been seen before any analysis.
- **Out of sample.** `PROTOCOL.md` registers predictions for the 2026 edition (expected around
  September 2027, by inference). It was registered by commit `844d5a3` on 2026-10-04. Its §12 dates
  the later clarifications D1–D5 and lists what the freeze commit must contain (code and frozen
  values).
- **The scoring rules are code**: `scripts/score_2026.py`.
- **An independent adversarial review** followed (`private/REVIEW.md`). Its corrections are applied
  here, in the paper, and in PROTOCOL §12.
- **Scout figures.** The figures of the scout report that proposed the study were recomputed, not
  reused.

## 2. Sources

All requests used the User-Agent `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`,
one at a time, with at least 1.2 s between requests to the same host. `robots.txt` was read first.

**Hosts not used:**

| host | reason |
|---|---|
| `www.inclusion.gob.es`, `extranjeros.inclusion.gob.es` | 403 on `robots.txt` |
| `www.interior.gob.es` | 403 and a bot challenge on `robots.txt` |
| `www.congreso.es` | 403 on `robots.txt`, as reported by the reviewer |
| `efe.com`, `provivienda.org` | `robots.txt` disallows our User-Agent |
| `www.elperiodico.com` | 406 |

No access control was bypassed. Data were downloaded on 4 October 2026.

| source | access | what we took |
|---|---|---|
| INE, ECAPSH, editions 2012–2024 | `www.ine.es/jaxi/files/tpx/es/csv_bdsc/<id>.csv`, 50 tables; ids and SHA-256 in `scripts/locked_inputs.json` | centres, centres with accommodation, mean places and occupied places by specialisation, ownership, reference date, type of centre and region; regions by reference date (2022, 2024); centres oriented to specific situations |
| INE, 2024 release (live, «Actualizada el 22 de octubre de 2025») and results page («Datos revisados y modificados con fecha 17/10/2025») | `www.ine.es/dyngs/Prensa/es/ECAPSH2024.htm`; results page | headline wording; the 2006–2024 chart; the regional table with its red cells |
| The same release as first published | Internet Archive, capture 2025-09-26 13:25:24 UTC | first-published figures |
| INE releases 2018, 2020, 2022; methodologies 2012–2024; questionnaires 2020–2024; IME and inventory entry 30469; calendars 2026 and 2027 | `www.ine.es/prensa/`, `/daco/daco42/epsh/`, `/dynt3/metadatos/`, `/dyngs/IOE/`, `/dynt3/Calendario/` | frame, definitions (including the 2024 change to ETHOS), response rates, revision policy, release dates |
| INE, EPSH 2022: methodology and release | `/daco/daco42/epsh/epshper_22.pdf`, `/prensa/epsh_2022.pdf` | definitions; the 28,552 estimate; «el 0,4% en centros de ayuda al refugiado» |
| Ministerio de Inclusión, «Informe Sistema de Protección Internacional español», 20-Jun-2025 (and 20-Jun-2024) | as published on `www.lamoncloa.gob.es` (locked) | SAPI and PAH places 2015–2025, read from Gráficos 1 and 2 |
| Eurostat `migr_asyappctza`, Spain | dissemination API 1.0 (locked) | asylum applicants, total and first-time |
| AIDA (ECRE), country reports on Spain, updates 2015–2025 | `asylumineurope.org` | arrivals, as cited from the Ministry of the Interior. Typed from the reports, not locked |
| Estrategia Nacional para la lucha contra el Sinhogarismo en España 2023-2030; operational plan 2023-2024; progress reports 2023 and 2024 | `www.dsca.gob.es` | ETHOS table, indicators and targets, the Ministry's readings |
| European Observatory on Homelessness, *Non-EU Migrant Homelessness*, Comparative Studies 14 (December 2025) | `www.feantsa.org` | its view of ETHOS and ETHOS Light on reception; its Spain section |
| Press and civil society (Europa Press, RTVE, La Razón, Diario de Sevilla, El Imparcial, Tribuna Madrid, Albergue Covadonga, HOGAR SÍ, FACIAM, fuentesinformadas.com, Europa Press/Accem, FEANTSA–Fondation pour le Logement 2026) | public pages | how the record was read; prior statements |
| Crossref, OpenAlex, GitHub, DuckDuckGo HTML | APIs and HTML search | prior work (`data/prior_work_search.csv`) |

The WebSearch tool was not available: its quota had run out.

## 3. Units and definitions

**Edition.** The reference year. Results come out in September of the following year.

**Occupied places.** INE's «número medio de plazas ocupadas», the mean of two reference dates
(mid-June and mid-December; 30 April and 15 December in 2020).
- From 2022 these count adults only: «A partir del año 2022 se contabilizan las plazas ocupadas por
  personas de 18 y más años». Places count all beds.
- So the occupancy ratio (occupied ÷ places) also moves with the share of children.

**Centres.** Centres in INE's tables.
- The survey is a census of a directory supplied by the regions through the Ministry of Social Rights.
  The Basque Country's fieldwork is done by EUSTAT.
- It does not impute or calibrate («La tasa de imputación es A7 = 0%», «no se calibra»), so the
  tables cover responding centres.

**Centres with accommodation.** INE gives two counts:
- 1,120 «ofrecieron servicios de alojamiento»;
- 1,099 offer the service «Alojamiento».

Only the second is split by specialisation, so the decomposition uses it. The national series uses
the first.

**Segments** («Especialización del centro», from 2020):
- **IMM**: «Especializado en inmigrantes»; we call these *immigrant-specialised*.
- **GBV**: «Especializado en mujeres víctimas de violencia de género».
- **OTH**: «Sin especialización/Otra especialización».
- **Core**: GBV + OTH.

**How the segments are defined and assigned.**
- INE's definition, the same in 2020–2024: «Distintas situaciones que el centro atiende específica y
  exclusivamente».
- The 2024 questionnaire asks the centre to tick «Centro especializado en la atención a migrantes»,
  without "exclusively". The published 2020 and 2022 questionnaires have no such item.
- INE does not break IMM down into asylum, humanitarian or seasonal-worker accommodation.

**The 2024 definition change.** §5 of INE's methodology moved from the 2020/2022 definition, which
added immigrant centres «para asegurar la continuidad de la serie histórica», to ETHOS. In ETHOS,
«Personas en centros de alojamiento para solicitantes de asilo e inmigrantes: Personas inmigrantes
que viven en alojamientos temporales por su estatus de extranjeros o trabajadores temporeros» is a
homelessness category.

**Centres oriented to immigration** (from 2014): «Inmigración/Solicitud de protección
internacional» among the situations a centre declares. This is not IMM. In 2024 it is 437 of 841
oriented centres (52.0%), against 360 IMM centres.

**EPSH 2022.** A sample survey of people using accommodation or meal services in municipalities of
more than 20,000 inhabitants. Its 28,552 is an estimate.

**Number parsing.** INE writes «1.376» and «26,2».
- Table 75683 writes «1,092» with a comma for thousands; it is read as 1,092 and flagged.
- «.» in region-by-specialisation tables marks a zero, checked against the other segments.

## 4. Decomposition

For segment `s`, `O_s = C_s · o_s`, where `C_s` is the number of centres offering accommodation and
`o_s` is occupied places per such centre.

**Headline: the symmetric split**, the Shapley value for two factors:

    ΔO_s = ΔC_s · (o_s,0 + o_s,1) / 2  +  Δo_s · (C_s,0 + C_s,1) / 2

**Range: the two one-at-a-time orderings**, centres first (`ΔC · o₀`, `Δo · C₁`) and per centre
first (`ΔC · o₁`, `Δo · C₀`).

**The core** is split once as an aggregate and once segment by segment (GBV and OTH separately, then
summed), to show the mix effect.

**What the terms mean.** "Centres" are centres in the tables. The split books an entering or leaving
centre at the average size of its segment, so frame changes can sit in either term.
- The centres term is not an upper bound on the frame effect.
- The per-centre term is not "existing centres filling up".
- Worked example: the 2025 correction added one IMM centre with 387 occupied places, and the split
  books 100 of them as centres and 287 as per centre (`data/summary.json`, `revision_split`).

The first-vintage IMM count of centres with accommodation (345) is inferred: the correction raised
centres with accommodation from 1,119 to 1,120 and the IMM share of centres from 26.1% to 26.2%.

## 5. Sensitivity (`data/sensitivity.csv`)

| id | variant | can move the IMM share? |
|---|---|---|
| S0 | headline: occupied places, centres offering accommodation, core = GBV + OTH, 2022 → 2024, revised 2024 | — |
| S1 | 2024 figures as first published | yes |
| S2 | places instead of occupied places | yes |
| S3 | all centres instead of centres offering accommodation | no, by construction |
| S4, S4b, S4c | core = OTH only (occupied; places; all centres) | no, by construction |
| S5 | base 2020 (crosses the adults-only rule of 2022) | yes |
| S6 | June and December snapshots (national totals only) | — |
| S7 | Spain without the Canary Islands (regional totals) | — |
| S9 | the previous edition, 2020 → 2022 (crosses the adults-only rule) | — |

The classification of centres into IMM, the variant that matters most, cannot be varied with
published tables.

## 6. Other analyses

- **Long series.** Occupied places per centre with accommodation, 2012–2024. `data/summary.json`
  also holds a through-origin elasticity over 2012–2022 (1.27). The five interval ratios range from
  −1.02 to +1.69 and one interval crosses the 2022 rule, so the paper does not use it.
- **Canary Islands by date.** Regional occupied places at each reference date, 2022 and 2024
  (`data/region_dates.csv`).
- **Reception arithmetic.** INE IMM places against SAPI + PAH places (one value a year; dated
  31 December only for 2024), first-time asylum applicants and arrivals. Growth is computed for both
  intervals, 2020–2022 and 2022–2024. The ratio is not a coverage rate: we cannot show that IMM is a
  subset of SAPI and PAH. The Ministry's figures are stocks on one day; INE's are a mean of two.
- **Strategy indicator.** «Tasa de cobertura de la red de plazas de alojamiento» = places / 28,552
  (EPSH 2022).
  - The strategy's baseline uses December 2020 places (20,191). We compute December and mean bases,
    and the mean without IMM.
  - EPSH's «el 0,4% en centros de ayuda al refugiado» is used to show that the two sides cover
    different populations.
  - The Ministry's progress reports do not publish the indicator; the values are ours.
- **Regions (exploratory).** Change in occupied places, 2022 → 2024, against the change in IMM
  centres and in other centres, across 19 regions (OLS slope, Pearson and Spearman correlation).

## 7. Data-quality notes

1. **The published 2024 figures changed after release.**
   - The results page: «Datos revisados y modificados con fecha 17/10/2025»; the release: «Actualizada
     el 22 de octubre de 2025».
   - Between vintages: one centre; 387 places and 387 occupied places at both dates, all IMM; meals;
     staff; the women's share.
   - In the regional table only Navarre changed (403 → 790 mean places), and INE shows the changed
     cells in red. No note says what changed or why.
   - The IME's revision section names «revisiones extraordinarias (por ejemplo, las debidas a un error
     en estadísticas ya publicadas)» among the revisions its policy covers. It also states «No existe
     revisión de datos» and «Los datos se publican cuando son definitivos, no están sujetos a
     revisión». The release says «Los datos publicados hoy son definitivos».
2. **INE's chart disagrees with INE's tables** for 2012 (chart 16,334 / 14,038; table 9743 15,638 /
   13,991) and 2016 places (19,224 against 19,124).
3. **The IME gives the 2024 response rate as 79.9%**, unit non-response as 20.4% and non-response as
   18.2%. The release says 80.0%.
4. **The IME says** «Posteriormente la información se somete a procesos de depuración e imputación»
   and «La tasa de imputación es A7 = 0%».
5. **In 2020, public IMM centres had more occupants than places** (2,182 occupied, 1,399 places).
   INE's 2020 release lists Melilla at 196.1%.

## 8. Not done

- No unit-level data: INE does not publish them, and we did not request them.
- No figures from `inclusion.gob.es`, `interior.gob.es` or `congreso.es` (§2).
- No breakdown of the immigrant category: not published.
- No reception places by region at INE's reference dates: not found in an accessible official report.
- No contact with INE, the Ministries or any organisation.
