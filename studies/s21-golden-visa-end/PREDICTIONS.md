# S21 — Pre-registered predictions for 2026Q3

*EasyxLab · study S21 · written 2026-10-04, before MIVAU publishes 2026Q3 (scheduled for 2026-12-16 in the PEN 2026 calendar) · status: pre-registration, not to be edited after its first commit*

## What is predicted

Purchases of dwellings by **foreign non-residents** (MIVAU table 1.6, «Extranjeros» among «No residentes») in the third quarter of 2026, for each of 19 units: the 18 provinces with at least 100 such purchases in 2023Q2–2024Q1, and the other 34 provinces pooled. Model and tests are those of METHOD.md §1.9, frozen on 2026-10-04 (sha256 of the plan in STATUS.md).

The quantity predicted is the unit's relative level, r = log(unit) − log(Spain without the unit), equivalently its share of Spain's foreign non-resident purchases. A national total is not predicted; counts follow from the realised national total N as N × share.

## Model

- Fitted per unit over 2019Q1–2026Q1 (definitive data): quarter-of-year effects, one shift for the anticipation year (2024Q2–2025Q1) and one for the post year (2025Q2–2026Q1).
- Prediction: third-quarter effect + post shift, that is, the post-repeal level persists.
- 90% interval: 5th and 95th percentiles of the unit's 2019Q1–2024Q1 residuals, added to the prediction. They include the 2020 pandemic quarters, and ignore the uncertainty of the post shift itself (estimated from four quarters).

## Predictions

| unit | fitted pre-announcement Q3 share, 2019–2023 (%) | share in 2023Q3 (%) | predicted share (%) | 90% interval (%) | 2025Q3 count | count if N equals 2025Q3's 11,531 |
|---|---|---|---|---|---|---|
| Alicante | 33.89 | 35.03 | 37.35 | 33.16–39.99 | 4,340 | 4,307 |
| Almería | 2.56 | 2.63 | 2.55 | 2.23–2.91 | 309 | 294 |
| Illes Balears | 8.87 | 7.42 | 7.46 | 6.22–9.98 | 850 | 860 |
| Barcelona | 2.52 | 3.09 | 2.13 | 1.51–2.92 | 247 | 246 |
| Cádiz | 1.14 | 1.32 | 1.24 | 1.04–1.61 | 175 | 142 |
| Castellón | 1.46 | 1.67 | 1.66 | 1.46–2.04 | 185 | 192 |
| A Coruña | 0.18 | 0.24 | 0.20 | 0.13–0.33 | 17 | 24 |
| Girona | 5.51 | 4.91 | 4.62 | 3.76–5.53 | 508 | 533 |
| Granada | 1.14 | 0.96 | 1.01 | 0.84–1.25 | 112 | 116 |
| Huelva | 0.37 | 0.54 | 0.46 | 0.31–0.64 | 53 | 53 |
| Madrid | 1.35 | 2.00 | 1.25 | 0.98–1.65 | 149 | 144 |
| Málaga | 18.67 | 17.52 | 17.94 | 15.58–20.47 | 2,013 | 2,068 |
| Murcia | 6.20 | 7.52 | 7.75 | 6.31–9.32 | 906 | 894 |
| Asturias | 0.29 | 0.37 | 0.40 | 0.27–0.56 | 63 | 46 |
| Las Palmas | 4.22 | 3.67 | 3.44 | 3.00–3.75 | 413 | 397 |
| Santa Cruz de Tenerife | 4.70 | 4.22 | 3.99 | 3.58–4.69 | 446 | 460 |
| Tarragona | 1.67 | 1.42 | 1.59 | 1.32–1.91 | 169 | 184 |
| Valencia | 3.05 | 3.55 | 2.96 | 2.37–3.67 | 340 | 341 |
| other 34 provinces, pooled | 1.67 | 1.91 | 2.06 | 1.76–2.47 | 236 | 238 |

Machine-readable copy: `data/predictions_2026Q3.csv` (log scale, with the fitted effects).

## Tests, decided now

1. **Calibration.** Count the units whose realised share falls inside its 90% interval. About 17 of 19 are expected; fewer than 15 means the model or the intervals are wrong.
2. **No rebound in the two cities.** For Madrid and for Barcelona, the realised 2026Q3 share stays below the fitted pre-announcement third-quarter share (first share column). If either is above it, the post-repeal fall did not persist there. This benchmark averages 2019–2023, including the 2020–2022 trough, so it is a weak test.
2b. **Added on 2026-10-04, before this file's first commit (METHOD.md §9).** The same, against the share in 2023Q3, the third quarter of the year before the announcement (second share column). This is the comparison behind the study's headline.
3. **Counts.** Given the realised national total N, each unit's count is N × predicted share; the interval scales the same way.

## What is already known and is not a test

- 2026Q2 is published but provisional; it was seen before writing this file and is not used to fit.
- If MIVAU revises earlier quarters in the December release, the evaluation uses the revised figures for 2026Q3 only; the fitted effects stay as frozen in the CSV.

## How it will be scored

`python3 scripts/build.py && python3 scripts/predict.py evaluate`, after downloading the December release with `bash scripts/run.sh fetch`.

## Deviations (dated 2026-10-04, after the first commit 204bcf6 and before the release of 2026-12-16)

An independent review of the study, made on 2026-10-04, found three faults in the tests above.
The predictions are unchanged. The tests are revised as follows; the original wording above is
kept for the record.

**Freeze record.**
- The plan: METHOD.md, between the FROZEN-PLAN markers, sha256
  `3f0e6b4c7f756155bf2e42f93929fc02e7845334a59e9e2a5b6e34dae7d15914`, frozen 2026-10-04T19:09:48Z.
- The scored values: `data/predictions_2026Q3_frozen.csv`, sha256
  `9f9d6afad07e7dce0dba31f0ff7eb34bac9942b1dd83eb1589acc922b5d6e68a`. This is the file called
  `data/predictions_2026Q3.csv` above, renamed, with its content unchanged.
- `data/freeze.json` holds both hashes. `scripts/predict.py` no longer writes the CSV once it
  exists, and `evaluate` refuses to score a file whose hash differs.

**Test 1 (calibration)** is unchanged.

**Test 2, respecified.** The original benchmark, the fitted 2019–2023 third-quarter share, lies
inside Madrid's own 90% interval: 1.35% against 0.98–1.65%. Madrid's provisional 2026Q2 share,
1.32% (152 of 11,510), was already at it when this file was written. The model could therefore
«fail» the test with no rebound at all.
- New rule: a city has **rebounded** if its realised 2026Q3 share is above the upper end of its
  90% interval: Madrid 1.65%, Barcelona 2.92%.
- By construction (95th percentile of the pre-period residuals), a persistent level crosses this
  line about 5% of the time. The intervals ignore the uncertainty of the post shift, so the true
  rate is somewhat higher.

**Test 2b, replaced.** The original 2b (below the 2023Q3 share, Madrid 2.00% and Barcelona
3.09%) could fail only with a rebound of about 60% (Madrid) or 45% (Barcelona) above the
predicted share. It was near-certain to pass and could not falsify anything.
- New rule: a city has **fallen further** if its realised 2026Q3 share is below the lower end of
  its 90% interval: Madrid 0.98%, Barcelona 1.51%. About 5% of the time under persistence.
- Tests 2 and 2b together are the two directional readings of test 1 for the two cities. Each
  has a stated false-alarm rate.

**Test 3, removed.** Counts are the realised national total times the share, so «counts» restates
test 1 and has no criterion of its own.

**Scoring.** `bash scripts/run.sh fetch && bash scripts/run.sh evaluate` after the release. It
prints the revised tests and, for the record, the superseded ones.

---
EasyxLab · a research lab by [EasyByte](https://easybyte.es)
