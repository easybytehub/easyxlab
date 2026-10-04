# S12 — Spain's record low of evictions in early 2026 and the court reform: a pre-registered test
*EasyxLab · study S12 · CGPJ data to Q1-2026, protocol registered 4 October 2026 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s12/paper/](https://easybyte.es/lab/studies/s12/paper/) · [PDF](https://easybyte.es/lab/studies/s12/paper.pdf)

## Abstract

Spain's General Council of the Judiciary (CGPJ) reported 4,005 evictions practised in the first
quarter of 2026, −45.4% on the 7,334 of a year earlier. That is the lowest quarter since its series
began in 2013, except Q2-2020 under the lockdown (1,383); the next lowest is Q3-2025 (4,839).

Readings differed:
- **que.es** took it as a sign that tenant protection was working.
- **PAH Barcelona** disputed it on the day of release. It asked why court-practised evictions fell
  while those received and completed by the common services rose (16,167, +19.2%; 7,696, +16.6%),
  and pointed to the court reform.
- **Electomanía**, in September, attributed part of the fall to changes in court procedure.

Under Organic Law 1/2025 the first-instance courts became *tribunales de instancia*, district by
district: 315 districts on 1 July 2025, 16 on 1 October and 100 on 31 December, 431 in all.

**The counting changed with the reform, and the CGPJ's own data-collection forms document it.**
- **Before.** Each court reported the evictions practised «bien directamente por el juzgado o bien
  por un servicio común» (item 1.13 of the court form).
- **After.** The 2026 form of the new civil section has no such item. Practised evictions are now
  item 1.4.2 of the common-services form, filled in by the common execution service, which «deberá
  recabarla del resto de Servicios comunes del Tribunal de Instancia» when it lacks information. A
  new item counts voluntary handovers.
- **Not in the published statistics.** The CGPJ's methodology page and release notes do not mention
  the change.

We registered a protocol on 4 October 2026, before the CGPJ's next release. It tests whether the fall
follows this change district phase by phase. The study measures the effect of a documented change in
who reports the series.

**The data neither establish that the record low is an artefact of that change nor rule it out.**

- **The main test is inconclusive (H1).** Provinces with more of their evictions in phase-3
  districts fell more in Q1-2026 than in the quarter before: b3 = −1.23, Holm-adjusted p = 0.18,
  permutation p = 0.047. The registered sensitivity analysis S3, run after the review, gives −1.18
  (p 0.088). Phase 1 left no detectable mark in Q3-2025 (b1 = −0.13, p = 0.34). One quarter earlier,
  before phase 3, the same regression already gives −0.755 (two-sided p 0.024). That pre-reform
  slope is an exploratory check, and it weakens H1a.
- **The service-side tests rest on Q4-2025 (H2 inconclusive, H3 supported).** The ratio of
  court-recorded to service-completed evictions fell more where phase 3 weighed more (b3 = −2.28,
  Holm-adjusted p = 0.026). The signal comes from the quarter *before* phase 3: in phase-3-heavy
  provinces the common services' figures collapsed in Q4-2025 and recovered in Q1-2026. Madrid's
  completed evictions went 955 → 193 → 867 (Q4-2024, Q4-2025, Q1-2026). In Q1-2026 alone, year on
  year, the slopes are −0.30 and −0.83 and not significant. Nationally, receipts were −29.6% in
  Q4-2025 and +19.2% in Q1-2026, and −4.2% over the two quarters together. The +19.2% is mostly a
  rebound.
- **The concentration is in rent evictions (H4, falsified).** Rent minus mortgage is −2.11
  (p = 0.011). The mortgage estimate is near zero but very imprecise: only 18 provinces have enough
  cases.
- **The district-level test passes, on doubtful data (H5).** Within provinces, phase-1 districts
  recorded −33% relative to phase-3 districts in 2025, but the gap was already −17% in 2024. The
  district file's 2025 column disagrees with the CGPJ's province figures in all 50 provinces.
- **No size can be given.** The pooled model registered to size the effect is degenerate: one
  parameter sits at its search bound.

**Explanations the design cannot separate:**
- the change in who counts;
- a real slowdown of the reorganised courts (the CGPJ reports resolved cases −13.7% overall and civil
  −22.3% in Q1-2026);
- rent-specific channels. One is the suspension of evictions for vulnerable households, in force for
  most of Q1-2026 but lapsed from 28 January to 4 February and finally from 28 February. Another is
  the pre-filing negotiation required since April 2025.

**Missing and estimated data, in the CGPJ's own words.**
- **Q3-2025.** «En este trimestre los datos de lanzamientos han sido estimados debido a la falta de
  información completa en algunos partidos judiciales». It lists 64 districts, 63 of them in phase
  1, transformed that quarter; the common-service series carry the same note. The first estimate,
  5,053, was later revised to 4,839.
- **Q1-2026.** The CGPJ lists three phase-3 districts without data at the close of the report:
  Donostia/San Sebastián, Gijón, Vinarós. It marks Madrid's rent figure «*Dato estimado». The
  release's own province sheet gives 2,249 rent evictions nationally, the series 2,600; the
  difference is how Madrid's 475 non-mortgage evictions are split.
- **The district file.** It places 2,944 evictions of 2025 in Ribadavia (Ourense), which had at
  most 11 in any earlier year.

The CGPJ has met this problem before. It stopped publishing its seizures series because, it says,
«muchos juzgados practican directamente el embargo sin que sea necesaria la intervención de los
servicios comunes». It explains: «Las bajadas que se venían observando se deben más a esta causa que
a una verdadera reducción del número de embargos practicados».

**Still to come.** The CGPJ publishes Q2-2026 on 16 October 2026. Predictions were frozen before
(commit `321bce1`); the out-of-sample test of PROTOCOL.md §7 will be added after that date.

An artefact of counting would be nobody's wrongdoing. The reform's timetable is set by law, and the
CGPJ itself disclosed the missing and estimated data.

## Results

| test | prediction | estimate | verdict |
|---|---|---|---|
| H1a | phase-3 share → larger fall in Q1-2026 | b3 = −1.23 (HC3 SE 0.90, 41 provinces); one-sided p 0.090, Holm-adjusted p = 0.18, permutation p = 0.047. Same regression one quarter earlier: −0.755 (exploratory) | inconclusive |
| H1b | phase-1 share → larger fall in Q3-2025 | b1 = −0.13 (SE 0.32, 44 provinces), p = 0.34 | inconclusive |
| H2 | phase-3 share → more evictions completed by common services | b3 = +1.33 (SE 0.95, 32 provinces), Holm-adjusted 0.17, permutation 0.051; driven by a Q4-2025 dip | inconclusive |
| H3 | phase-3 share → lower court-to-service ratio | b3 = −2.28 (SE 0.90, 31 provinces), Holm-adjusted p = 0.026, permutation 0.006; driven by Q4-2025, Q1-2026 alone −0.83 (n.s.) | supported, read as a Q4-2025 effect |
| H4 | the change is the same for mortgage and rent evictions | mortgage b3 = +0.14 (SE 1.58, 18 provinces); rent − mortgage −2.11, p = 0.011 | falsified |
| H5 | phase-1 districts fall more in 2025, within province | −33% (422 districts); placebo years 2015–2024 all smaller, 2024 already −17% | supported, on data that fail a consistency check |

Coefficients are slopes of the change in year-on-year log growth on the share of a province's
2023–24 evictions in districts of the phase. The registered time placebos (2024 and 2025 first
quarters, 2023 and 2024 third quarters) and negative controls show no comparable pattern; the
exploratory in-window placebo does.

Full tables are in:
- `data/tests.csv`, `data/sensitivity.csv` and `data/h5_years.csv` (frozen);
- `data/review_checks.json` (after the review).

## Layout

| path | |
|---|---|
| `PROTOCOL.md` | the pre-registration (commit `ee3ef6c`), with every later event dated in §14 |
| `METHOD.md` | sources, access, licences; how phases, weights and outcomes are built; deviations |
| [paper](https://easybyte.es/lab/studies/s12/paper/) (web) | the paper |
| `scripts/s12lib.py` | locked inputs and their SHA-256, readers for the CGPJ and Ministry files, name matching, WLS with HC3 |
| `scripts/fetch.py` | downloads the locked files again and checks them against the registered hashes |
| `scripts/build.py` | districts, phases, weights, province series and the CGPJ's notes → `data/` |
| `scripts/dq.py` | data-quality checks DQ1–DQ11 → `data/dq_*.csv`, `data/dq_summary.json` |
| `scripts/analyse.py` | registered tests, placebos, controls, sensitivity, pooled model, decomposition, frozen predictions |
| `scripts/post_review.py` | checks added after the independent review: S3 as registered, the Q4-2025/Q1-2026 split, the in-window placebo, H5 by consistency (exploratory) |
| `scripts/prior_work_search.py` | the prior-work searches and `data/prior_work_search.csv` |
| `scripts/check_headlines.py` | recomputes the main headline numbers from `data/` and checks that each appears in this README and in [the paper](https://easybyte.es/lab/studies/s12/paper/) |
| `scripts/run.sh` | `run.sh` (offline: tests, build, checks, analysis, post-review checks, headline check), `run.sh fetch`, `run.sh check` |
| `tests/test_s12.py` | unit tests (labels, name matching, WLS/HC3, phase counts) |
| `data/districts.csv` | 431 districts: province, phase, weight, practised evictions 2023–2025, CGPJ flags |
| `data/province_exposure.csv`, `data/province_quarter.csv` | phase shares by province; the province series used, 2021-Q1 to 2026-Q1 |
| `data/cgpj_notes.csv` | the CGPJ's missing/estimated-data notes, literal, matched to districts and phases |
| `data/tests.csv`, `data/sensitivity.csv`, `data/h5_years.csv`, `data/exclusions.csv` | every regression; provinces excluded by the small-count rule |
| `data/pooled_model.json`, `data/decomposition.json`, `data/summary.json` | pooled model, decomposition, verdicts |
| `data/dq_*.csv`, `data/dq_summary.json` | data-quality checks |
| `data/predictions_q2_2026.csv`, `data/predictions_q2_2026_spec.json` | the frozen predictions and the rules for scoring them |
| `data/review_checks.json`, `data/review_slopes.csv` | post-review checks (not registered, except S3 as written) |
| `data/prior_work_search.csv` | every prior-work search, with time and number of results (GitHub owners withheld) |
| `data/raw/`, `work/`, `private/` | git-ignored: downloaded files, intermediate panel, scratch, the review. Never published |

## How to run

Python ≥ 3.10 with `numpy`, `scipy`, `openpyxl` and `xlrd` (pinned in `requirements.txt`; `run.sh`
creates `.venv/` if it is missing).

```bash
bash scripts/run.sh fetch   # ~7 MB from poderjudicial.es and administraciondejusticia.gob.es, 5 s between CGPJ requests
bash scripts/run.sh         # tests, build, data-quality checks, analysis, headline check; offline, ~30 s
```

`fetch` refuses a file whose SHA-256 differs from the vintage registered in PROTOCOL.md §3.3: the
CGPJ replaces its files in place, and a changed file is a different vintage. After the Q2-2026
release the CGPJ may replace the «1T-2026_revisado» series in place, as it did with 3T-2024 «V2». In
that case `fetch` reports the file as changed and the locked vintage can no longer be downloaded
from the CGPJ. Outputs are deterministic (fixed seeds).

## Licences

- Code (`scripts/`, `tests/`): Apache-2.0, see [`../../LICENSE`](../../LICENSE).
- Our data and text: CC BY 4.0, see [`../../LICENSE-DATA`](../../LICENSE-DATA).
- Source data are official statistics of the Consejo General del Poder Judicial
  (poderjudicial.es, «Efecto de la crisis en los órganos judiciales», «Lanzamientos por partidos
  judiciales», «Población por partido judicial») and a list of court name changes published by
  the Ministry of the Presidency, Justice and Relations with the Cortes
  (administraciondejusticia.gob.es).
- **Reuse terms are not verified.** On 4 October 2026 the CGPJ's legal-notice page contained only
  «No hay información disponible». Its last archived text (Internet Archive, 14 November 2025) is
  about the case-law database only: «Las resoluciones judiciales que integran la base de datos
  “Jurisprudencia” se difunden a través de este portal …». We found no terms covering the
  statistics files.
- We do not re-host the source files; `data/` holds the figures we derived from them, attributed to
  their publishers.
- None of these bodies endorses this study.

Cite as: EasyxLab (2026). Spain's record low of evictions in early 2026 and the court reform: a
pre-registered test. Study S12. EasyByte Hub S. Coop. Mad. https://github.com/easybytehub/easyxlab

---
EasyxLab · a research lab by [EasyByte](https://easybyte.es)
