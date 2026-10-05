# S12 — Method

*EasyxLab · study S12 · working draft*

## 1. Pre-registration

The design is in `PROTOCOL.md`, registered by commit `ee3ef6c` on 2026-10-04 at 12:38 UTC, before the
CGPJ's Q2-2026 release (scheduled for 2026-10-16). The code, the in-sample results and the
predictions for Q2-2026 were frozen by commit `321bce1` at 12:56 UTC the same day. Every later event,
and every implementation choice the protocol left open, is dated in `PROTOCOL.md` §14. The protocol
states what had been seen before it was written; the in-sample tests are therefore not blind, and the
Q2-2026 test is. No commit separates the implementation choices from the first estimates; their order
rests on the session's command log.

An independent review followed the freeze (`private/REVIEW.md`). Its corrections are recorded in
§14, and its additional checks are in `scripts/post_review.py` (§12 below). No frozen file was
changed.

## 2. Sources

All requests used the User-Agent `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`,
one at a time, with at least 1 s between requests to the same host and 5 s to www.poderjudicial.es,
whose `robots.txt` asks for `Crawl-delay: 5`. Paths that a site's `robots.txt` disallows were not
fetched; on poderjudicial.es that excludes the press files under `/stfls/…/NOTAS*DE*PRENSA/`. No
access control was bypassed. Data were downloaded on 2026-10-04.

| source | host and access | what we took | licence or terms |
|---|---|---|---|
| CGPJ, «Efecto de la crisis en los órganos judiciales»: province and TSJ series (Q1-2026, «revisado») and the quarterly releases Q1-2025 … Q1-2026 and annual 2025 | `www.poderjudicial.es/stfls/ESTADISTICA/FICHEROS/Crisis/`, nine xlsx files linked from the statistics page | practised evictions by type; evictions received and completed by common services; mortgage enforcement, dismissal and payment-order filings; the notes on missing and estimated data | **not verified**: the live legal notice reads only «No hay información disponible»; its last archived text (Internet Archive, 14-Nov-2025) concerns the case-law database («Las resoluciones judiciales que integran la base de datos “Jurisprudencia”…»), not the statistics. Not re-hosted; derived figures published with attribution |
| CGPJ, «Boletines trimestrales de recogida de datos»: BOLETIN 04 Juzgado de Primera Instancia e Instrucción (2024; Last-Modified 2024-06-12, SHA-256 `a99a77ab…`), BOLETIN 04 Sección Civil y de Instrucción TI (2026; 2026-04-17, `7de3e53f…`), BOLETIN 56 Servicios comunes TI (2026; 2026-04-17, `beb85dff…`) | `www.poderjudicial.es/stfls/ESTADISTICA/DOCUMENTOSCGPJ/`, linked from the bulletins page (the 2024 court form is no longer linked; its URL follows the CGPJ's naming of earlier years) | the items that define practised evictions before and after the transformation (§13) | same; full hashes in `PROTOCOL.md` §14 |
| CGPJ, «Lanzamientos por PJs 2013-2025» | same folder, one xlsx | practised evictions by judicial district and year, by type | same |
| CGPJ, «Población por Partido Judicial - Año 2025» | `www.poderjudicial.es/stfls/ESTADISTICA/FICHEROS/Poblacion/`, one xlsx | the district-to-province table | same |
| Ministry of the Presidency, Justice and Relations with the Cortes, LexNET name changes, phases 1–3 | `www.administraciondejusticia.gob.es/documents/d/asset-library-5650231/cambios-lexnet-numo-fase-1-2-y-3-v1-0-1-xls`, linked from the Directorate-General's letter of 19-Dec-2025 | former and new court names per seat, by phase | none stated; `robots.txt` allows all |
| BOE consolidated texts: LO 1/2025, LEC, RDL 11/2020; analysis pages; the Congress resolutions repealing RDL 16/2025 and RDL 2/2026 | `www.boe.es/buscar/act.php`, `/buscar/doc.php`, `/diario_boe/txt.php` | the provisions quoted in the paper | official journal; `robots.txt` disallows only other-language variants and some services |
| Ministry press release of 30-Jun-2025; Madrid Bar and Spanish Bar notes of 1-Oct-2025; the Directorate-General's letter (copy on cograsova.es) | `www.mjusticia.gob.es`, `web.icam.es`, `www.abogacia.es`, `www.cograsova.es` | phase totals (315 / 16 / 100) and the phase-2 list | quoted only |
| CGPJ web pages: methodology, publication calendar, PC-Axis page, Q1-2026 activity press note, TSJ Galicia and TSJ Cantabria notes of 22-Jun-2026 | `www.poderjudicial.es/cgpj/es/…` | definitions, release dates, how the figures were presented | quoted only |
| Instituto de Estadística de Extremadura, divulgative note on Q1-2026 | `www.juntaex.es` | the CGPJ's national figures as relayed | quoted only |
| Press and civil society: que.es (22-Jun-2026), brainsre.news, PAH Barcelona (22-Jun-2026), Electomanía (24-Sep-2026) | public pages; `robots.txt` read before fetching (Electomanía groups AI agents with `*` and disallows only admin and search paths) | how the figure was read; the prior statement of the hypothesis | quoted only |
| Internet Archive | `web.archive.org`, the CGPJ legal notice as captured on 2025-11-14 and 2026-07-01; CDX index of CGPJ form files | the archived reuse text | quoted only |
| Crossref REST API, arXiv API, GitHub (`gh search repos`, `gh search code`) | APIs | prior work | Crossref ≥ 1.1 s, arXiv 3.1 s between requests |

The SHA-256 of every input file is in `scripts/s12lib.py` (`LOCKED`, `SUPPORT`) and in `PROTOCOL.md`
§3.3 and §14.

## 3. Units

- **Quarter**: calendar quarter as labelled by the CGPJ (`26-T1` = 2026-Q1). Footnote marks (`13-T3(1)`)
  and stars (`25-T3*`, estimated) are read as the quarter they label.
- **Province**: the 50 rows of the province series. Ceuta and Melilla are counted inside Cádiz and
  Málaga in that series. Comparing the district file with the province series over 2013–2024, the
  absolute differences add up to 3 (Cádiz) and 0 (Málaga) with them included, and to 490 and 1,086
  without.
- **District** (*partido judicial*): the 431 rows of the district file, one per *tribunal de
  instancia*.
- **Series**: practised evictions recorded by the courts (total, mortgage, rent/LAU, other); evictions
  received by the common services and those they completed («cumplimiento positivo»); mortgage
  enforcement filings, dismissal claims and payment-order filings as controls.

## 4. Phase of each district

Phase 1 = the 315 seats of the xls sheet «Cambios NUMO fase 1»; phase 2 = the 16 of «Cambios NUMO
fase 2», identical to the Madrid Bar's list; phase 3 = the other 100 of the 431, which must include
the 30 seats of the sheet «Cambios NUMO (MJU) fase 3» (they do). A seat is the municipality of the
former first-instance courts; it is matched to its district by normalised name, with five aliases
(Cangas del Narcea, Mahón, Palma de Mallorca, Villarrobledo, Vila-real). Event quarters: phase 1 →
2025-Q3, phase 2 → 2025-Q4, phase 3 → 2026-Q1 (the change took effect on the last day of 2025).

## 5. Weights and exposure

`w_d` is the district's share of its province's practised evictions in 2023 + 2024 (district file).
A district-year flagged by the outlier rule of §9 is left out: the district takes the mean of its
other weight years. `W1`, `W2`, `W3` are the shares of a province in phase-1, phase-2 and phase-3
districts. `B` is the province's practised evictions in 2024, the regression weight.

## 6. Tests

For province `p` and quarter `t`, `g = ln Y_t − ln Y_{t−4}` (year on year, which removes the August
judicial holiday) and `Δg(t) = g_t − g_{t−1}`. Between 2025-Q4 and 2026-Q1 only the phase-3 districts
change status for the first time, and the base quarters of both year-on-year changes precede every
transformation. So the slope of `Δg(2026-Q1)` on `W3`, controlling for `W2`, measures how much more
the phase-3 districts' count fell when they were transformed. National events (the end of the
suspensions, the pre-filing negotiation, the market) are common to all provinces and go into the
intercept. H1b uses `Δg(2025-Q3)` on `W1`.

- Weighted least squares, weights `B`, HC3 standard errors, one-sided p-values in the registered
  direction, from Student's t with n − k degrees of freedom (slightly more conservative than the
  normal).
- A permutation p-value from 10,000 reassignments of the vectors `(W1, W2, W3)` across provinces
  (seed 20261004).
- Holm correction within {H1a, H1b} and within {H2, H3, H4, H5}. "Supported" needs the Holm-adjusted
  HC3 p and the permutation p both ≤ 0.05, and clean time placebos for H1.
- Provinces with fewer than 10 evictions in any of the four quarters entering `Δg` are left out
  (`data/exclusions.csv`).
- H2 and H3 use only provinces whose common services received evictions in every quarter of
  2024–2026-Q1. H3's outcome is `Δg` of practised minus `Δg` of completed by the services. H4 compares
  mortgage and rent evictions on the same provinces.
- H5 uses the district file: `ln(Y_2025 + 1) − ln(Y_2024 + 1)` on phase dummies with province fixed
  effects, weights `Y_2023 + Y_2024`, and standard errors clustered by province. There are 52
  clusters, because here Ceuta and Melilla are their own provinces; a singleton cluster adds nothing
  to δ1. The same regression is run for every pair of years from 2015/2014 to 2024/2023 as placebos.
- Time placebos repeat H1a on 2025-Q1 and 2024-Q1, and H1b on 2024-Q3 and 2023-Q3. Negative controls
  apply the H1 models to mortgage-enforcement filings and dismissal claims; payment-order filings,
  which the pre-filing negotiation hit nationally, are a positive control for national shocks.

Falsification rules are in `PROTOCOL.md` §8 and are applied mechanically by `scripts/analyse.py`.

## 7. Pooled model, decomposition and the "record low"

The registered pooled model fits every province-quarter from 2022-Q1 to 2026-Q1 with a free effect
for each quarter and a proportional effect `ρ_k` for each event time `k` (−2, −1, 0, 1, 2 or more),
mixed by the districts' shares. It is estimated by weighted nonlinear least squares with `ρ` searched
in [−0.95, 3.0], and 2,000 province-cluster bootstrap resamples. The parameter for `k ≥ 2` ends at the
upper bound of the search, +3.0, in both the version with and without leads. The fit is degenerate:
in 2026-Q1 every district is past its transformation, and the model reproduces the strong
relative growth of phase-1-heavy provinces only by pushing that parameter to the bound. The
phase-specific slopes disagree (phase 1, H1b: −0.13; phase 3, H1a: −1.23, with a 95% interval
from −3.05 to +0.59), so the assumption of a common effect across phases fails. Read as proportional
effects, these slopes give no usable size: H1a's interval spans −95% to +80%. The registered decomposition and record-low
verdict rest on this fit. They are reported in `data/decomposition.json` and the paper, flagged as
unreliable. An exploratory, unregistered counterfactual using H1a alone is reported next to them.

## 8. Out-of-sample test, due after the CGPJ's Q2-2026 release (scheduled for 16 October 2026)

`data/predictions_q2_2026.csv` holds, for each province, the predicted deviation of `Δg(2026-Q2)`
from the weighted national mean under a transient reading (the effect lasts one quarter) and a
persistent reading (no deviation). `data/predictions_q2_2026_spec.json` states the test and the
classification rule. The transient reading uses the first-quarter parameter of the degenerate pooled
model (§7), and the persistent reading is zero for every province; scoring therefore compares an
uncertain prediction with a constant. H1a was not supported, so by the registered rule the Q2 slope
is read as a replication check. The Q2-2026 release is due on 2026-10-16; the test will be run and
reported after it, without changing any rule.

## 9. Data-quality checks

DQ1 district file against province series, with the outlier rule (a district-year ≥ 10 times its
earlier maximum and ≥ 100 more, or 0 after ≥ 50); DQ2 first against latest vintage of each quarter;
DQ3 the CGPJ's notes by phase; DQ4 identities (total = mortgage + rent + other; provinces add up to
TSJ and national totals; national totals equal the published figures); DQ5 column labels; DQ6 and
DQ7 phase matching; DQ8 seasonality; DQ9 exclusions; DQ10 common-service coverage; DQ11 the record
claim taken literally. Results: `data/dq_summary.json` and `data/dq_*.csv`.

## 10. Deviations and choices left open by the protocol

Listed and dated in `PROTOCOL.md` §14:
- the district-to-province table;
- Ceuta and Melilla;
- the handling of flagged district-years in weights;
- the reading of "half the size" in absolute value;
- the two versions of S4;
- S10 dropping Murcia for San Javier's pre-reform pilot;
- zero counts in the pooled model;
- the anticipation test at α = 0.05;
- the permutation test for H2–H4;
- the weighting of predictions;
- the descriptive "as fitted" prediction column, dropped before the freeze;
- after the review: the correction of the documented counting change (protocol §2.3), of the
  suspension dates and scope (§2.4, §5, §12), and S3 run as registered (with Madrid dropped).

## 11. What was not possible

- **No district-by-quarter data.** The CGPJ publishes districts only by year (the district file, and
  the PC-Axis database, which is annual by court). The quarterly test therefore runs on provinces.
- **No district data for the common services.** The SC tests use the practised-eviction weights.
- **No actual start dates for court offices.** Transitional provision 5 allows them to differ from
  the *tribunal* date; we found no official list of such cases. One pre-reform pilot (San Javier) is
  handled in S10.
- **Reuse terms not verified.** The live legal notice is empty, and the archived one covers only the
  case-law database (§2).
- **The 2025 forms.** The 2025 versions of the court form and of form 56 are no longer linked from
  the CGPJ's page and are not in the Internet Archive's index under the CGPJ's naming. We read the
  2024 court form and the 2026 section and common-service forms. The reviewer read the 2025 ones.
- **Web search.** The session's web-search quota ran out during the write-up. Two prior statements
  of the hypothesis (PAH Barcelona, Electomanía) were found by the independent review and then read
  by us.

## 12. Post-review checks (`scripts/post_review.py`, not registered except S3)

- **S3 as registered.** Drops the provinces with CGPJ-flagged districts in Q4-2025 or Q1-2026 and
  Madrid, whose Q1-2026 split is estimated.
- **The slope split.** Each H1a, H2, H3 and SC-receipts slope is split into the slope of
  `g(2026-Q1)` and the slope of `g(2025-Q4)`, on the same provinces and weights as the frozen test.
- **In-window placebo.** `Δg(2025-Q4)` on (W3, W2), for practised evictions and for the two
  common-service series, with the frozen estimator and permutation test.
- **Las Palmas.** H1a without it.
- **H5 by consistency.** H5 restricted to districts in provinces where the 2025 district file is
  within 5% of the province series, more than 5% below it, or more than 5% above it.
- Output: `data/review_checks.json`, `data/review_slopes.csv`.

## 13. The data-collection forms

The CGPJ's quarterly bulletins define what each court or service reports.
- **Item 1.13 of the 2024 court form** (BOLETIN 04) counted practised evictions «bien directamente
  por el juzgado o bien por un servicio común».
- **The 2026 section form** has no such item.
- **The 2026 common-services form** (BOLETIN 56, «II. SERVICIO COMUN DE EJECUCION») has items
  1.4.1 (evictions ordered by the service's decree), 1.4.2 «LANZAMIENTOS PRACTICADOS EN EL
  TRIMESTRE», with the instruction to gather missing information «del resto de Servicios comunes del
  Tribunal de Instancia», and 1.4.3 «Entregas posesorias mediatas producidas en el trimestre».

We read these items with `pdftotext` from the downloaded PDFs.
