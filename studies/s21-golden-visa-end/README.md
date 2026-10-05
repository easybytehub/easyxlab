# S21 — Did purchases by foreign non-residents fall after Spain ended its golden visa? Evidence from MIVAU's quarterly transactions, 2007–2026
*EasyxLab · study S21 · MIVAU release of 1 October 2026 (data to 2026Q2) · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s21/paper/](https://easybyte.es/lab/studies/s21/paper/) · [PDF](https://easybyte.es/lab/studies/s21/paper.pdf)

## Abstract

**The rule.** Spain's residence permits for investors (the "golden visa", arts. 63–67 of Ley
14/2013) ended on 3 April 2025. Ley Orgánica 1/2025, final provision 21: «Se dejan sin contenido
los artículos 63, 64, 65, 66 y 67».
- Applications filed before that date are decided under the old rules.
- Permits already granted keep their validity.
- One of its routes, the one the Government named when it announced the end, was buying
  property worth €500,000 or more.
- The Prime Minister announced the end on 8 April 2024.

**The data.** The Ministry of Housing's (MIVAU) open quarterly count of home purchases by the
buyer's residence and nationality, for 52 provinces, 2007Q1–2026Q2, built from notarial deeds.
The outcome is purchases by foreign non-residents. The windows are four quarters each:
- B, the year before the announcement (2023Q2–2024Q1);
- A, the year from announcement to repeal (2024Q2–2025Q1);
- P, the year after the repeal (2025Q2–2026Q1).

**The end of the golden visa coincided with a fall in foreign non-resident purchases in Madrid
and Barcelona. The tests fixed in advance do not support attributing it to the repeal.**

**What the tests fixed in advance show.**
- **Spain.** Foreign non-resident purchases fell 9.8% from B to P.
- **The Government's six provinces.** The Council of Ministers placed 90% of the permits in
  Barcelona, Madrid, Málaga, Alicante, Baleares and Valencia. Together they fell 9.3%, against
  11.0% in the other 46 provinces. Across 19 units, the six-province contrast is null: +0.02 log
  points, permutation p = 0.84.
- **Exposure.** The planned exposure was a province's share of foreign non-resident buyers in
  2019–2023. It has the wrong sign: provinces with a larger share fell less, +0.05 log points per
  10 percentage points of share, permutation p = 0.13. Their share of homes sold for €600,000 or
  more does not predict the fall either.

**What the data show for Madrid and Barcelona (the provinces, called "the two cities" below for
short; exploratory: chosen after a pilot showed they fell most).**
- **Size.** Foreign non-resident purchases went from 2,651 in B to 1,699 in P, −35.9%, against
  −8.5% in the rest of Spain: −30.0% relative to the rest. Madrid fell 36.3% and Barcelona 35.7%.
  Valencia, also one of the six, fell 26.9%. Málaga fell 5.5% and Alicante 5.2%.
- **Only these buyers.** In the same two provinces, against the rest of Spain, no other buyer
  group fell by more than 3.7%: foreign residents +4.6%, Spanish non-residents +13.0%, Spanish
  residents −3.7%, all purchases −1.3%.
- **Against history.** Over the 58 planned placebo dates the relative fall has p = 0.051, and over
  a spaced subset of 15 dates p = 0.125. Placebo windows overlap. With fully non-overlapping
  windows there are only five dates, so no p below about 0.17 is attainable; the real fall is the
  most extreme of those five. Excluding pandemic windows, a choice made after seeing the data,
  gives p = 0.024.
- **The baseline year was high.** Madrid's 614 purchases in P are about its 2019 count (609).
  - Against 2018–2019, the two cities' share of Spain's foreign non-resident purchases is 22%
    lower (Madrid −13%, Barcelona −26%); against B it is 29% lower.
  - In the event study, their deviations in 2020Q3–2022Q4 (−0.28 to −0.53 log points) are as large as
    the post-repeal ones (−0.22 to −0.45).
- **Timing.** The two cities' level relative to the rest fell 42.7% from 2025Q1 to 2025Q2, the
  largest such fall since 2007. Two other readings fit that quarter:
  - it is also the quarter of the euro's largest quarterly rise of 2007–2026 against the dollar
    (+7.7%) and the yuan (+7.1%);
  - a deadline makes buyers bring purchases forward, so a sharp drop just after it cannot tell
    "the rush ended" from "demand fell". Portugal shows the pattern: when it closed homes in Lisbon, Porto and the coast to its real-estate route on 1 January 2022, purchases by buyers domiciled
    outside the EU spiked in 2021Q4, fell 0.49 log points against EU buyers in 2022Q1, and grew
    again in 2022 and 2023 (in 2022 less than purchases by EU buyers: −11.8% relative).
- **The rush.** Madrid rose 38.7% in A and the two cities 24.8%, against 6.1% in the rest. The
  relative rise (+17.7%) is unremarkable against history (p = 0.34).

**Other changes at the same time.**
- **The tax announcement.** On 13 January 2025 the Government announced a tax of «hasta el 100%»
  on non-EU non-resident buyers. It had not become law by 4 October 2026 (no rule in the
  BOE, and none in the housing decree-law of 29 September 2026). It reached the same buyers one quarter
  before the repeal and **cannot be separated** from it.
- **Currency.** A regression in levels gives a −10% relative change from the euro's rise, but it is
  close to spurious (Durbin–Watson 0.49). Regressions in differences give about zero. **The
  currency effect cannot be bounded with these data.**
- **The general market** fell little: against the rest of Spain, Spanish residents in the two
  cities fell 3.7% and all buyers 1.3%.
- **Regional tax.** Madrid's transfer tax has been 6% since 2014. Catalonia raised it on
  second-hand homes over €600,000, for all buyers, from 27 June 2025 (decree-law published 26
  March 2025). A Catalan law of 9 July 2026 (Ley 11/2026), in force after window P, changed who
  counts as a large holder and the rules for whole buildings in the article that sets the scale,
  not the scale itself.
- **EU and non-EU buyers.** MIVAU does not separate them. The Notariado and the Registradores
  publish national EU/non-EU figures in press releases, but their sites restrict reuse, and we did
  not use them.

**Prior work.** The press has already reported the rush and the fall from notarial and registry
data, in April and May 2026, including EU/non-EU splits. Academic work measured the introduction
of the schemes, not their end. What this study adds is narrow:
- an open, reproducible, province-level analysis from open data, with placebo buyer groups and
  placebo dates;
- an out-of-sample test pre-registered before MIVAU publishes 2026Q3 on 16 December 2026
  (`PREDICTIONS.md`).

## Headline tables (foreign non-resident purchases; B = 2023Q2–2024Q1, A = 2024Q2–2025Q1, P = 2025Q2–2026Q1)

| tests fixed in advance | estimate | permutation p |
|---|---|---|
| the Government's six provinces against the other 46 (19 units, weighted) | +0.02 log points | 0.84 |
| share of foreign non-resident buyers, 2019–2023 (per 10 percentage points, weighted) | +0.05 log points | 0.13 |
| share of homes over €600,000 (weighted) | −0.38 log points per unit of share | 0.76 |

| territory | B | A | P | A vs B | P vs B | P vs A |
|---|---|---|---|---|---|---|
| official six provinces | 36,812 | 40,399 | 33,389 | +9.7% | −9.3% | −17.4% |
| the other 46 provinces | 17,270 | 17,468 | 15,371 | +1.1% | −11.0% | −12.0% |
| Madrid + Barcelona | 2,651 | 3,309 | 1,699 | +24.8% | −35.9% | −48.7% |
| Madrid | 964 | 1,337 | 614 | +38.7% | −36.3% | −54.1% |
| Barcelona | 1,687 | 1,972 | 1,085 | +16.9% | −35.7% | −45.0% |
| Valencia | 1,883 | 1,873 | 1,376 | −0.5% | −26.9% | −26.5% |
| Málaga | 9,587 | 11,006 | 9,064 | +14.8% | −5.5% | −17.6% |
| Alicante | 18,894 | 20,258 | 17,915 | +7.2% | −5.2% | −11.6% |
| Spain without Madrid and Barcelona | 51,431 | 54,558 | 47,061 | +6.1% | −8.5% | −13.7% |
| Spain | 54,082 | 57,867 | 48,760 | +7.0% | −9.8% | −15.7% |

| Madrid + Barcelona against the rest of Spain (exploratory) | rush (A vs B) | fall (P vs B) | fall from the rush (P vs A) |
|---|---|---|---|
| foreign non-residents | +17.7% | −30.0% | −40.5% |
| foreign residents | +10.6% | +4.6% | −5.4% |
| Spanish non-residents | +3.3% | +13.0% | +9.3% |
| Spanish residents | +2.2% | −3.7% | −5.9% |
| placebo p, 58 planned dates (15 spaced) | 0.34 (0.31) | 0.051 (0.125) | 0.017 (0.062) |

| share of Spain's foreign non-resident purchases | 2014–2017 | 2018–2019 | 2020Q2–2022Q1 | B | A | P |
|---|---|---|---|---|---|---|
| Madrid | 1.22% | 1.45% | 1.12% | 1.78% | 2.31% | 1.26% |
| Barcelona | 4.15% | 3.01% | 2.21% | 3.12% | 3.41% | 2.23% |

## Layout

| path | |
|---|---|
| `METHOD.md` | frozen analysis plan (§1), sources (§2), access (§3), deviations and additions (§9), what was not possible (§10) |
| `PREDICTIONS.md` | pre-registered predictions for 2026Q3 (MIVAU release of 16 December 2026), with the dated deviations of 4 October 2026 |
| `scripts/s21lib.py` | provinces, quarters, window sums, relative changes, rank p-values, WLS with absorbed fixed effects and clustered errors, permutations |
| `tests/test_s21lib.py` | unit tests on synthetic numbers (`python3 -m unittest discover -s tests`) |
| `scripts/fetch.py`, `scripts/fetch_portugal.py` | every public source (MIVAU, Internet Archive, ECB, BOE, La Moncloa, INE, portugal.gov.pt, Statistics Portugal) |
| `scripts/polite.py`, `scripts/robots9309.py`, `scripts/htmltext.py` | fetcher shared with other EasyxLab studies: fixed User-Agent, ≤ 1 request/s per host, robots.txt (RFC 9309), every request logged |
| `scripts/build.py` | MIVAU workbooks and ECB files → `data/province_quarter.csv`, `vintages.csv`, `value_bands.csv`, `value_quarter.csv`, `fx_quarter.csv` |
| `scripts/analyse.py` | every published table (§1 of METHOD and the additions of §9) |
| `scripts/predict.py` | the 2026Q3 model; writes the frozen CSV once and never again; `evaluate` scores it after the release |
| `scripts/check_headlines.py` | recomputes the headline numbers from `data/`, checks they appear in this README (and in [the paper](https://easybyte.es/lab/studies/s21/paper/), when present), and checks both freeze hashes |
| `scripts/run.sh` | `run.sh` (fetches first in a fresh clone, then tests, tables, analysis, check), `run.sh fetch`, `run.sh check`, `run.sh evaluate` |
| `data/province_quarter.csv` | MIVAU table 1.6: purchases by buyer group, 52 provinces + Spain, 2007Q1–2026Q2 |
| `data/windows.csv`, `data/core_quarterly.csv`, `data/history_shares.csv` | four-quarter sums and changes per territory and buyer group; the two cities quarter by quarter; their share by period |
| `data/placebo_dates.csv`, `data/event_study.csv`, `data/did_windows.csv`, `data/units.csv` | placebo dates; event-study coefficients; window differences-in-differences; the 19 units and their exposures |
| `data/value_bands.csv`, `data/price_segment.csv`, `data/value_quarter.csv` | free-market transactions by value band (first quarters of 2021, 2022, 2025, 2026) and by value |
| `data/fx_quarter.csv`, `data/portugal_quarter.csv`, `data/portugal_windows.csv` | ECB rates; Portuguese transactions by buyer's tax domicile |
| `data/vintages.csv` | the same counts in archived releases of 2023 and 2025 (revision check) |
| `data/predictions_2026Q3_frozen.csv`, `data/freeze.json` | the frozen predictions that `evaluate` scores; the SHA-256 of the frozen plan and of that file |
| `data/summary.json`, `data/sources.json`, `data/prior_work_search.csv` | headline numbers; source URLs and SHA-256; every prior-work query |
| [paper](https://easybyte.es/lab/studies/s21/paper/) (web) | the paper (not in the public package; read it at https://easybyte.es/lab/studies/s21/paper/) |
| `data/raw/`, `work/`, `private/` | git-ignored: downloads, logs, drafts. Never published. |

## How to run

Python ≥ 3.10 and `xlrd` 2.0 (`pip install -r requirements.txt`, to read the MIVAU `.XLS`
workbooks); everything else is the standard library.

```bash
bash scripts/run.sh            # in a fresh clone: fetches the public sources, then builds and checks
bash scripts/run.sh fetch      # MIVAU workbooks, Internet Archive copies, ECB, legal pages, Statistics Portugal
bash scripts/run.sh check      # only the headline check
bash scripts/run.sh evaluate   # after 16 December 2026: score PREDICTIONS.md
```

MIVAU replaces its workbooks at each release. The published numbers come from the release of 1
October 2026; the SHA-256 of every workbook is in `data/sources.json`. On a later release,
`check_headlines.py` lists the differences from the published numbers but does not fail.

## Licences

- Code (`scripts/`, `tests/`): Apache-2.0, see [`../../LICENSE`](../../LICENSE).
- Our data and text: CC BY 4.0, see [`../../LICENSE-DATA`](../../LICENSE-DATA).
- Third-party data are not redistributed. `data/` holds only aggregates derived from them.
  - Ministerio de Vivienda y Agenda Urbana, «Transacciones inmobiliarias» (tables 1, 1.1, 1.5, 1.6,
    1.7, 3.1, 3.2, 3.3), CC BY 4.0 according to datos.gob.es. Earlier releases were read from the
    Internet Archive.
  - European Central Bank, euro foreign exchange reference rates (ECB Data Portal). Source: ECB.
  - Instituto Nacional de Estatística (Statistics Portugal), indicators 0012785 and 0012786.
    Source: INE, Portugal.
  - Legal texts: Boletín Oficial del Estado; La Moncloa; INE (calendar of the Plan Estadístico
    Nacional 2026); Government of Portugal; Procuradoria-Geral Distrital de Lisboa (consolidated
    Portuguese laws).
- None of these sources endorses this study.

Cite as: EasyxLab (2026). Did purchases by foreign non-residents fall after Spain ended its golden
visa? Evidence from MIVAU's quarterly transactions, 2007–2026. Study S21. EasyByte Hub S. Coop.
Mad. https://github.com/easybytehub/easyxlab

---
EasyxLab · a research lab by [EasyByte](https://easybyte.es)
