# S21 — Method

*EasyxLab · study S21 · status: working draft, not peer-reviewed*

This file holds the analysis plan, frozen before any of its measures were computed (§1), the
sources (§2), access (§3) and every later deviation (§9). The plan was written after the scout's
pilot (report K1) was known: the four-quarter sums for Madrid, Barcelona, Valencia, Málaga,
Alicante, Baleares and Spain, and the Madrid and Barcelona quarterly counts for 2023–2026. We
recomputed those and they match (STATUS.md, phase 1). Nothing else in §1.3–§1.9 had been
computed. The in-sample tests are therefore not blind. The only blind test is the
pre-registered prediction for the third quarter of 2026 (§1.9, `PREDICTIONS.md`).

<!-- FROZEN-PLAN:BEGIN -->
## 1. Analysis plan (frozen)

### 1.1 Data and unit

- MIVAU table 1.6, «Número de transacciones inmobiliarias según residencia del comprador», one
  sheet per quarter from 2007Q1 to 2026Q2 (2026Q2 provisional), 52 provinces. Groups: Spanish
  residents (`res_es`), foreign residents (`res_fx`), Spanish non-residents (`nres_es`), foreign
  non-residents (`nres_fx`), all buyers (`total`). Outcome: `nres_fx`.
- Unit: province × quarter. The 18 provinces with at least 100 foreign non-resident purchases
  in the baseline window B are analysed one by one. The other 34 are pooled into one unit,
  «rest pooled», so that the 19 units cover all of Spain.
- Definitive data only (to 2026Q1) for estimation. 2026Q2 is provisional and is reported apart.

### 1.2 Dates and windows

- Announcement: 8 April 2024 (La Moncloa). First quarter after it: 2024Q2.
- Announcement of the tax of «hasta el 100 %» on non-EU non-resident buyers: 13 January 2025,
  inside 2025Q1. It has no legal text.
- Repeal in force: 3 April 2025 (LO 1/2025, DF 21.ª and DF 38.ª.1). First quarter after it: 2025Q2.
- Windows of four quarters, so that seasonality cancels:
  - B, baseline: 2023Q2–2024Q1;
  - A, anticipation: 2024Q2–2025Q1;
  - P, post: 2025Q2–2026Q1.

### 1.3 Measures for the two cities

- Treated: Madrid and Barcelona pooled («core two»), and each one. Comparison: Spain without
  Madrid and Barcelona («rest»).
- **Rush:** A/B. **Fall net of the rush:** P/B (primary). **Fall from the rush:** P/A (the
  scout's measure, reported for comparison).
- Relative change: (treated ratio) / (rest ratio) − 1, on the same windows.
- Within-province placebo groups: the same measures for foreign residents, Spanish
  non-residents and Spanish residents. The repeal applied only to buyers who wanted a residence
  permit, so these groups should not show the same pattern.
- Excess and deficit, in purchases: rush excess = A − B × (rest A/B); deficit = B × (rest P/B) − P.

### 1.4 Placebo dates

- The same windows are moved to every earlier announcement quarter a from 2008Q1 to 2022Q2 (B =
  a−4…a−1, A = a…a+3, P = a+4…a+7), so that every placebo window ends before 2024Q2: 58 dates.
- For each date: the core two's relative rush (A/B), relative fall net of rush (P/B) and
  relative fall from the rush (P/A), against the rest.
- p-value: the share of placebo values at least as extreme as the real one, counting the real
  one (smallest attainable p = 1/59). Also over a spaced subset, one date every four quarters
  (15 dates, smallest p = 1/16), because consecutive windows overlap.
- One-sided: upper for the rush, lower for the falls.

### 1.5 Event study and difference-in-differences across provinces

- **Exposure, primary (as required by the brief):** the foreign non-resident share of all
  purchases in the province, 2019Q1–2023Q4.
- **Exposure, secondary:**
  - core two (Madrid and Barcelona = 1);
  - the official six provinces that concentrated 90% of the authorisations (Council of
    Ministers, 9 April 2024);
  - high-value share: transactions of €600,000 or more over all free-market transactions in table
    1.7, first quarters of 2021 and 2022 pooled. That is the closest pre-period measure of the
    segment above the €500,000 threshold.
- **Event study:** log `nres_fx` by unit and quarter, 2019Q1–2026Q1. Fixed effects for unit ×
  quarter-of-year and for quarter. Interactions of the exposure with each quarter, the four
  quarters of B being the reference. WLS weighted by the unit's B count, with standard errors
  clustered by unit (CR1). Unweighted as robustness.
- **Window DiD:** for each unit, Δ = log(P) − log(B) (and log(A) − log(B), log(P) − log(A)),
  regressed on the exposure, weighted by B. Inference by permuting the exposure across the 19
  units (9,999 draws) and by HC1 standard errors.
- **Triple difference:** the same with Δ(`nres_fx`) − Δ(`res_fx`) in each unit.

### 1.6 Price segment

- Table 1.7 gives free-market transactions by value band, for all buyers, one first quarter per
  file. We have the first quarters of 2021, 2022, 2025 and 2026.
- Measure: change from 2025Q1 (anticipation) to 2026Q1 (post) in transactions of €600,000 or
  more, against transactions under €450,000, by province. Then the same for Madrid and Barcelona
  against the rest.
- The test is a bound: the purchases lost by foreign non-residents in Madrid in one quarter are
  compared with the change in that quarter's high-value count. Table 1.7 does not separate
  buyers, so this is descriptive.

### 1.7 Currency

- ECB reference rates, quarterly averages, of USD, GBP and CNY per euro (the currencies of three
  of the four main golden-visa nationalities). Change between B and P.
- The pre-period elasticity of the core two's relative non-resident purchases, log(core two) −
  log(rest), to an equal-weighted log index of the three rates, estimated over 2010Q1–2024Q1 with
  quarter-of-year dummies. The implied currency-driven change from B to P is compared with the
  observed change.

### 1.8 What cannot be separated, stated in advance

- The repeal and the 13 January 2025 tax announcement hit the same buyers within one quarter of
  each other. The geography (§1.5) and the price segment (§1.6) can show where the fall sits, but
  not apportion it between the two.
- MIVAU does not separate buyers from inside and outside the EU. If no open source does, the
  outcome mixes EU buyers, who were never affected, into the denominator of every ratio.

### 1.9 Out-of-sample prediction (`PREDICTIONS.md`)

- MIVAU publishes 2026Q3 on 16 December 2026 (PEN 2026 calendar). Before then, `PREDICTIONS.md`
  is committed with predictions for each of the 19 units.
- Model: relative level r(u, t) = log `nres_fx`(u, t) − log `nres_fx`(Spain without u, t), fitted
  over 2019Q1–2026Q1 with unit × quarter-of-year effects, one shift for A and one for P.
  - Prediction for 2026Q3: the unit's third-quarter effect plus its post shift.
  - 90% interval from the empirical 5th and 95th percentiles of the unit's pre-period residuals.
- Pre-registered tests:
  - the number of the 19 units whose realised r falls inside its interval (about 17 expected);
  - for Madrid and Barcelona, that r stays below the pre-announcement third-quarter level (no
    rebound);
  - counts, conditional on the realised national total.
<!-- FROZEN-PLAN:END -->

## 2. Sources

All downloads were made on 2026-10-04 with `scripts/fetch.py` and `scripts/fetch_portugal.py`.
`data/sources.json` gives each URL and the SHA-256 of every file kept in `data/raw/`.

| source | host | what we used | licence or terms as stated |
|---|---|---|---|
| MIVAU, «Transacciones inmobiliarias», tables 1, 1.1, 1.5, 1.6, 1.7, 3.1, 3.2, 3.3 (release of 1 Oct 2026; workbooks saved 25–29 Sep 2026) | apps.fomento.gob.es (`/BoletinOnline2/sedal/*.XLS`) | table 1.6, purchases by buyer residence and nationality, 78 quarterly sheets, 2007Q1–2026Q2; table 1.7, free-market purchases by value band (one first quarter per file); tables 1.1 and 3.1, counts and values of free-market purchases | CC BY 4.0 (datos.gob.es catalogue entry «Transacciones inmobiliarias de vivienda», «Condiciones de uso: …CC_BY_4_0») |
| Same workbooks, earlier releases | web.archive.org (`id_` raw captures found with the CDX API) | table 1.6 of 30 May 2023 (to 2022Q4) and 6 Oct 2025 (to 2025Q2); table 1.7 for 2021Q1, 2022Q1 and 2025Q1 | as above |
| INE, Inventario de Operaciones Estadísticas, operation 25003 | www.ine.es | source: «Documentación administrativa del Colegio General del Notariado»; unit: «Transacciones de viviendas recogidas ante notario a través de escritura pública» | INE legal notice |
| Calendar of the Programa anual 2026 of the Plan Estadístico Nacional (PDF, image-based; read on screen and by OCR) | www.ine.es | p. 24: «Estadística de Transacciones Inmobiliarias», PEN 9198: 11 March (T4/25), 11 June (T1/26), 1 October (T2/26), 16 December (T3/26) | — |
| INE, ETDP results page | www.ine.es | the six table families; none by buyer nationality or residence | — |
| ECB Data Portal, EXR.Q.{USD,GBP,CNY}.EUR.SP00.A | data-api.ecb.europa.eu | quarterly averages of the reference rates | ECB reuse with source |
| Statistics Portugal (INE), indicators 0012785 and 0012786 | www.ine.pt (JSON API) | transactions of family dwellings, number and value, by buyer's tax domicile (national territory, EU, other countries), 2009Q1–2026Q2. The split by domicile exists only at national level; regional cells are «x», «Dado não disponível» | INE (Portugal) terms: reuse with source |
| BOE: LO 1/2025 (original and consolidated, and its «Referencias posteriores»); Ley 14/2013 (consolidated, and the 2015 wording of arts. 63–64); TRLITPAJD (consolidated to 21 Mar 2026); RDL 26/2026; Catalan DLeg 1/2024 (consolidated and 2024 wording of art. 641-1); Madrid DLeg 1/2010 | www.boe.es (and its open-data API for searches) | literal texts, grepped | BOE legal notice |
| La Moncloa: 8 Apr 2024 (announcement), 9 Apr 2024 (Council of Ministers reference), 13 Jan 2025 (tax announcement), 29 Sep 2026 (Council of Ministers reference) | www.lamoncloa.gob.es | literal quotes | — |
| Government of Portugal, Council of Ministers communiqué of 16 Feb 2023 | portugal.gov.pt | literal quote | — |
| idealista/news, golden-visa topic page and two articles | www.idealista.com | the legislative timeline; permits January–October 2024 from a parliamentary answer as quoted by Europa Press | quoted only |
| Prior work: OpenAlex, Crossref, Banco de España (sitemaps and two PDFs), EUR-Lex | api.openalex.org, api.crossref.org, www.bde.es, eur-lex.europa.eu | metadata, abstracts, two BdE documents read | — |

**Reading table 1.6.** Each sheet has the columns TOTAL · Residentes (Total, Españoles, Extranjeros,
No consta) · No residentes (Total, Españoles, Extranjeros, No consta) · No consta. The parser
checks the header and the identities (groups add up to totals, provinces add up to Spain). In
the current release they hold everywhere except two cells of 2009Q4: the national total and
Toledo's total. Neither is used. Sheets marked «(**)» are provisional; only 2026Q2 is.

**Revisions.** The release of 30 May 2023 and that of 6 October 2025 differ from the current one
only in a few cells, mostly in their last, provisional quarter. For example, 2025Q2's national
count of foreign non-resident purchases went from 13,545 to 13,536. Over 2021Q1–2025Q2, Madrid's
and Barcelona's sums differ by at most 4 purchases (`data/vintages.csv`).

## 3. Access: User-Agent, rate, robots.txt

- User-Agent `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)` on every request.
- At most one request per second per host, on a clock shared by all processes. Every request is
  logged in `work/fetch_log.jsonl`.
- robots.txt is read under RFC 9309 before every request. 2xx: parsed. 4xx: no restriction.
  5xx or network error: complete disallow.
- 214 requests went to 38 hosts. Most went to api.openalex.org (32), www.ine.pt (21),
  web.archive.org (20), www.boe.es (16), www.ine.es (13) and apps.fomento.gob.es (11).
- A reproduction from a clean copy (§9.7) sent about 60 more, logged in that copy.
- www.pgdlisboa.pt has no robots.txt (404, no restriction under RFC 9309).
- The reviewer's own requests, sent with User-Agent `EasyxLab-review/1.0`, are not in this log.
- robots.txt stopped three more before they were sent. Two went to repositorio.bde.es and one to
  servicios.ine.es; both robots.txt files were unreachable, which counts as disallow-all.
- **The rate rule was broken four times.** In each case a robots.txt request followed a redirect
  0.58–0.72 s after the previous request to the same host (consejodetransparencia.es,
  extranjeros.inclusion.gob.es, data-api.ecb.europa.eu, www.portugal.gov.pt).
- **Blocked, not bypassed.** These hosts answered 403 to our User-Agent: www.mivau.gob.es,
  www.inclusion.gob.es and extranjeros.inclusion.gob.es (the investor-permit statistics),
  elpais.com, www.eleconomista.es and www.transparency.org. html.duckduckgo.com answered with a
  challenge page. We used neither archived copies of these hosts nor any other route around them.
- **www.ine.pt** answers 403 to robots.txt itself. RFC 9309 treats a 4xx as "no restrictions", and
  the JSON API answered normally.
- **Rate-limited or failing.** api.gdeltproject.org (429) and api.crossref.org (429, once). The ECB
  Data Portal answered 504 now and then. `fetch.py` retries server errors three times, 30 s apart.
- **robots.txt and the law.** We respected robots.txt to the legal minimum: wherever it can work as
  a reservation of text and data mining on content we analyse (Directive 2019/790 art. 4(3);
  TRLPI art. 67). In practice we followed it everywhere.
- **Notariado and Registradores.** The Notariado's statistics portal forbids reproduction, and
  Registradores' site blocks us with a firewall. We used neither.
- **WebSearch.** The session's budget was exhausted (200 of 200), so no open web search was made.
  Discovery went through OpenAlex, Crossref, sitemaps and one outlet's topic page.

## 4. Definitions

- **Foreign non-resident purchase:** a notarial purchase deed of a dwelling whose buyer is not
  resident in Spain and is not Spanish (table 1.6, «No residentes · Extranjeros»). The table
  counts transactions, not buyers. It does not give the buyer's country or the price.
- **Province:** the dwelling's province. Ceuta and Melilla are separate provinces.
- **Unit:** each of the 18 provinces with at least 100 foreign non-resident purchases in B, plus
  the other 34 pooled into one unit («RP»).
- **Relative change:** (treated P/B) / (comparison P/B) − 1, in percent. The comparison is Spain
  without Madrid and Barcelona unless stated.

## 5. Statistics

- Placebo dates: one-sided rank p-values counting the real value, with smallest attainable p
  1/(n + 1) (`s21lib.rank_p`).
- Event study and window DiD: weighted least squares with fixed effects absorbed by alternating
  projections. Standard errors are clustered by unit (CR1), or HC1 for the cross-section
  (`s21lib.wls_fe`). With 19 units the clustered errors are unreliable, so inference on exposures
  uses permutations of the exposure across units (9,999 draws, seed 21). With two treated units
  out of 19, the smallest attainable two-sided p for the core-two indicator is 1/171 ≈ 0.0058.
- Poisson intervals for count ratios capture sampling noise only.

## 9. Deviations from the frozen plan, and additions

All were made on 2026-10-04, after the frozen plan's measures had been computed.

### 9.1 History of the two cities' share (added)

The event study showed that the core two's level relative to other units was 0.3–0.5 log points
below B throughout 2020Q3–2022Q4 (`data/event_study.csv`). The plan's baseline year B was
therefore not typical. We added the two cities' share of Spain's foreign non-resident purchases
by period, 2014–2026 (`data/history_shares.csv`).

### 9.2 Placebo dates without pandemic windows (added)

The most negative placebo values come from dates whose windows cover 2020–2021. We recomputed
the p-values over the 41 dates whose windows do not touch 2020Q1–2021Q4.

### 9.3 Sharpness of the break (added)

We measured the change in log(core two) − log(rest) from 2025Q1 to 2025Q2. It is compared with
the same change in every year since 2007 (19 values) and with all quarter-to-quarter changes (76).

### 9.4 Portugal (added)

The plan did not specify the Portuguese comparator. We found the INE (Portugal) indicators after
freezing and added:
- windows B = 2022, A = 2023Q1–Q3 (against 2022Q1–Q3), P = 2023Q4–2024Q3;
- the contrast of non-EU-domiciled against EU-domiciled buyers;
- placebo end dates, of which only five fit in the series, so no p-value is interpreted.

The dates first came from the government's communiqué of 16 February 2023 and from Lei 56/2023.
The review found that the communiqué does not mention the permits, and that the right Portuguese
event is the one of 1 January 2022 (§9.7). Both laws were then read in the consolidated texts of
the Procuradoria-Geral Distrital de Lisboa. The October 2023 contrast is kept as secondary,
without its A window.

### 9.5 Pre-registration test 2b (added before the first commit of PREDICTIONS.md)

The plan's «pre-announcement third-quarter level» was implemented as the fitted average of the
2019–2023 third quarters. That average includes the 2020–2022 trough, which makes the no-rebound
test weak: Madrid's predicted share, 1.25%, is barely below it (1.35%). We added a second
benchmark, each city's share in 2023Q3 (2.00% and 3.09%). The plan's version is kept.

### 9.6 Sources not in the plan

- Regional purchase taxes for Madrid and Catalonia (BOE consolidated texts).
- The Government's housing decree-law of 29 September 2026.
- Secondary permit counts (a parliamentary answer quoted by Europa Press).

They are context and enter no estimate.

### 9.7 Changes after the independent review (2026-10-04)

An independent agent reviewed the study (internal file `private/REVIEW.md`). Every major item was
applied:

1. **Selection.**
   - Madrid and Barcelona were chosen after the pilot, so their contrasts are now labelled
     exploratory.
   - The abstract leads with the tests fixed independently of the pilot: the six provinces, the
     share exposure and the high-value exposure.
   - The binary-exposure p (0.0058) and the triple-difference p (0.021) are reported as
     descriptions.
2. **Placebo dates.**
   - The planned p (0.051) and the spaced p (0.125) lead.
   - Added: the five fully non-overlapping dates (2010Q2, 2013Q2, 2016Q2, 2019Q2, 2022Q2). The
     smallest attainable p is 1/6 ≈ 0.17, and the real value reaches it.
   - The pandemic-free p (0.024) is labelled post hoc.
3. **The 2025Q2 break.**
   - Added: the euro's quarterly moves against the dollar and the yuan, from `data/fx_quarter.csv`.
     In 2025Q2 they were the largest of the 2007–2026 sample, +7.7% and +7.1%.
   - Added: the statement that a break after a deadline cannot tell the end of a rush from a fall
     in demand.
4. **Currency.**
   - Added: the Durbin–Watson statistic of the levels regression (0.49), and regressions in
     four-quarter and one-quarter differences (+0.07 and +0.33, both about zero).
   - Removed: the «upper bound».
5. **Portugal.**
   - Added: the 1 January 2022 event (DL 14/2021, read literally), with its quarter-to-quarter
     changes and annual sums.
   - The October 2023 contrast is now secondary.
6. **Prior work.** The press items found by the reviewer are cited, the false sentence «has not
   been measured» is removed, and the novelty claim is narrowed.
7. **Pre-registration.** See §9.8.
8. **Abstract.**
   - The baseline-year numbers (Madrid's 614 against 609 in 2019; −22% against 2018–2019) are in
     the abstract.
   - «only there was the fall large» is removed.

Minor items applied:
- Catalonia's tax applies to second-hand homes only, and the decree was published on 26 March
  2025.
- «Including family members» is marked as our inference.
- Madrid's within-territory price contrast is about 3 points (about 90 purchases), not 7.
- Madrid's foreign residents had their own smaller rise and fall.
- Ley 20/2022 as a caveat on the Spanish non-resident placebo.
- The quote «hasta el 100%» now matches the source.
- The check's coverage is described accurately.

The computations of items 2–5 are in `scripts/analyse.py` (`post_review`, `portugal_2022`) and
`data/summary.json` → `post_review`.

**Reproduction from a clean copy.** Before the review, a copy without `data/raw/` or derived CSVs
was rebuilt from public sources:
- the first attempt failed on an ECB 504;
- `fetch.py` now retries;
- the second attempt gave `data/` byte for byte.

### 9.8 Pre-registration, after the review

`PREDICTIONS.md` was committed (204bcf6) before the review. A dated «Deviations» section was
appended to it, before the release of 16 December 2026:
- **Test 2** is respecified. A rebound now means a realised share above the upper end of the 90%
  interval. The old benchmark lay inside Madrid's interval.
- **Test 2b** is replaced by a further-fall test (below the lower end). The old 2b could fail only
  with a 45–60% rebound.
- **Test 3**, which had no criterion, is removed.

The scored values are frozen in `data/predictions_2026Q3_frozen.csv`. `scripts/predict.py` writes
it only if it is missing, and `evaluate` refuses to score it if its SHA-256 differs from
`data/freeze.json`. That file also holds the SHA-256 of the plan block above.

## 10. What was not possible

- **EU and non-EU buyers in Spain.** MIVAU table 1.6 does not separate them, and neither does
  the INE's ETDP (its tables classify transactions by nature, title, regime, new or used, and
  whether the buyer is a person or a company). The Notariado and Registradores publish national
  EU/non-EU aggregates in press releases (paper §3). Registradores' site blocks us, the Notariado's
  portal forbids reproduction and its site reserves against AI input. The Portuguese split is
  national only.
- **Investor-permit statistics by province and year.** Inclusión's statistics answered 403 (not
  bypassed). The only official figures read are national ones from the Council of Ministers of 9
  April 2024. The secondary figures from a 2024 parliamentary answer cannot be reconciled with
  them: visas issued by consulates and authorisations granted in Spain are different counts.
  - The PEN 2026 calendar lists Inclusión's «Flujo de Documentos de Residencia Concedidos a
    Personas Extranjeras» (PEN 9870) for release by 31 December 2026, with 2025 data. It may give
    the post-repeal count of investor authorisations, if Inclusión opens it to us.
- **Price segment by residence.** Table 1.7 gives value bands for all buyers, one first quarter
  per file. The Internet Archive holds 2021Q1, 2022Q1 and 2025Q1 (and the live file 2026Q1), but
  not 2023Q1 or 2024Q1.
- **The tax announcement.** It cannot be separated from the repeal with quarterly data. Its legal
  status was checked: no rule in the BOE.
- **Press data journalism.** WebSearch was exhausted, and El País and elEconomista block us. The
  press items in paper §3 come from search snippets found by the reviewer:
  - El Periódico answers 406;
  - La Razón's robots.txt reserves its content against AI crawlers;
  - the Notariado's site carries «Content-Signal: ai-train=no, search=yes, ai-input=no».

  We cite them and did not read them.
- **Other local measures** in Madrid and Barcelona (tourist-flat plans, seasonal-let rules, the
  national short-let register) were listed but not verified against official texts.
