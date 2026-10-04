# S22 — Protocol: what will ECAPSH 2026 show about the 2024 record in centres for homeless people?

EasyxLab · study S22 · **protocol written on 2026-10-04, to be registered by its first commit, before INE
publishes the 2026 edition of its survey of centres for homeless people (expected late September
2027, §2.4).** Later changes are listed, dated, in §12 ("Deviations"); nothing above §12 is edited
after registration except to fix typos.

**What is and is not blind.** Every figure of the 2012–2024 editions had been seen, and the
decomposition of §4 had been computed, before this protocol was written. The in-sample results
(2022→2024) are therefore descriptive, not tests. The only blind test is the out-of-sample use of
ECAPSH 2026 (§5–§7). The scout report that proposed this study gave unaudited figures; none is
reused: everything is recomputed from the files locked in §3.

## 1. Research questions

- **RQ1 (composition).** How much of the change in the mean daily number of occupied places
  between two editions comes from centres INE classes as «Especializado en inmigrantes»
  (immigrant-only centres, IMM), and how much from the other centres (the *core*: centres for women
  victims of gender violence, GBV, plus centres without specialisation or with another, OTH)?
- **RQ2 (frame).** Within each group, how much comes from more centres offering accommodation (the
  number of responding centres in the published tables) and how much from more people per centre?
- **RQ3 (out of sample).** In ECAPSH 2026, does the core behave as a stable network whose total moves
  with its number of centres (reading A, "frame and composition"), or as a network under rising
  pressure (reading B, "real growth")? Does the immigrant-only component move with the capacity of
  the state reception system?

## 2. Facts verified before registration (literal text, retrieved on 2026-10-04)

### 2.1 What INE published for 2024, and when it changed

| item | literal text | source |
|---|---|---|
| Headline, current release | «Una media de 34.145 personas mayores de 18 años se alojó diariamente en el año 2024 en centros de atención a personas sin hogar (un 57,5 % más que en 2022).» Header: «26 de septiembre de 2025 · Actualizada el 22 de octubre de 2025» | https://www.ine.es/dyngs/Prensa/es/ECAPSH2024.htm |
| Immigrant-only centres | «Los centros que atendieron exclusivamente a personas inmigrantes ofrecieron una media diaria de 21.298 plazas de alojamiento (un 100,9 % más que en 2022), con una media de 18.173 plazas ocupadas (un 125,9 % más que en 2022).» | same |
| INE's own explanation | «Cabe destacar que las llegadas masivas de inmigrantes a Canarias y el reparto de inmigrantes provocaron el aumento del número de plazas de alojamiento disponibles, especialmente en el periodo invernal.» | same |
| Scope change in 2022 | «Nota: A partir del año 2022 se contabilizan las plazas ocupadas por personas de 18 y más años, mientras que la capacidad se refiere al número total de plazas disponibles en el centro.» | same |
| Revision | Results page: «Aviso a usuarios Datos revisados y modificados con fecha 17/10/2025.» | https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736176925&menu=resultados&idp=1254735976608 |
| First-published figures | «Una media de 33.758 personas mayores de 18 años se alojó diariamente en el año 2024 en centros de atención a personas sin hogar (un 55,7% más que en 2022).» «… una media diaria de 20.911 plazas de alojamiento (un 97,2% más que en 2022), con una media de 17.786 plazas ocupadas (un 121,1% más que en 2022).» «De los 1.375 centros …» | Internet Archive capture 2025-09-26 13:25:24 UTC of https://www.ine.es/dyngs/Prensa/ECAPSH2024.htm |
| Revision policy (metadata of 19-Sep-2025) | «No existe revisión de datos.» | Informe metodológico estandarizado, https://www.ine.es/dynt3/metadatos/es/RespuestaDatos.html?oe=30469 |

The revision added one centre (1,375 → 1,376), one centre with accommodation (1,119 → 1,120), 387
places and 387 occupied places, all of them in immigrant-only centres (`data/revision_2024.csv`).

### 2.2 How the survey is built

| item | literal text | source |
|---|---|---|
| Frame | «Se investigan exhaustivamente todos los centros del directorio facilitado al INE por el Ministerio de Derechos Sociales y Agenda 2030 a través de las correspondientes consejerías de todas las comunidades autónomas, excepto el País Vasco, con referencia a 30 de junio de 2024.» | INE, metodología ECAPSH 2024, https://www.ine.es/daco/daco42/epsh/ecapsh_meto_24.pdf |
| Specialisation | «Especialización del centro: Distintas situaciones que el centro atiende específica y exclusivamente. Se consideran las siguientes: mujeres víctimas de violencia de género, inmigrantes y sin especialización o con otra distinta de las anteriores.» (same wording in 2020 and 2022) | same; ecapsh_meto_20.pdf, ecapsh_meto_22.pdf |
| How it is asked | 2024 questionnaire, cover: «Especialización del centro: Centro sin especialización / otra especialización · Centro especializado en la atención a mujeres víctimas de violencia de género · Centro especializado en la atención a migrantes». The published 2020 and 2022 questionnaires have no such item | ecapsh_cues_24.pdf, ecapsh_cues_22.pdf, ecapsh_cues_20.pdf |
| Non-response | «la tasa de respuesta fue el 79,9%» · «La tasa de sobrecobertura es A2= 10,8%» · «La tasa de no respuesta por unidad es A4= 20,4%» · «La tasa de imputación es A7 = 0%.» · «Señalar que no se calibra en esta operación estadística.» | IME (above) |
| Response rates of earlier editions | 2018: «nivel de respuesta del 77,8%»; 2020: «79,5%» | INE press releases 2018 and 2020 |

With no imputation and no calibration, the published totals are sums over responding centres. A
change in the number of centres in the tables combines changes in the directory, in response and in
the real number of centres.

### 2.3 What the national strategy measures with this survey

- ETHOS, as reproduced in the Estrategia Nacional para la lucha contra el Sinhogarismo en España
  2023-2030 (Cuadro 1), places category 5, «Personas en centros de alojamiento para solicitantes de
  asilo e inmigrantes», under «Sin vivienda». **People in reception centres are houseless under the
  Strategy's own definition.**
- Indicator «Tasa de cobertura de la red de plazas de alojamiento»: baseline «70,7%» (ECPSH 2020),
  expected result «alcanza el 85%» in 2028 and «alcanza el 90% o más» in 2030. Footnote 35:
  «Estimación realizada a partir del número total de plazas existentes a 31 de diciembre de 2021
  (disponibles en la ECPSH, 2020), sobre el total de personas en situación de sinhogarismo
  identificadas en la ENPSH 2022.» (20,191 places / 28,552 people = 70.7%.)
- The Strategy's own caveat: «una parte del incremento de las plazas contabilizadas por esa encuesta
  podría también deberse a la mejora en cuanto a la capacidad de detección e identificación por parte
  del INE de los centros que prestan este tipo de servicios».
- Source: https://www.dsca.gob.es/sites/default/files/derechos-sociales/servicios-sociales/docs/Estrategia.2_PSH20232030.pdf

### 2.4 Release calendar

- Past releases: 2018 edition on 26-Sep-2019; 2020 on 29-Sep-2021; 2022 on 26-Sep-2023; 2024 on
  26-Sep-2025 (dates printed on the releases).
- INE's 2027 calendar («Última actualización: 25 Septiembre 2026»,
  https://www.ine.es/dynt3/Calendario/calenHTML.htm?q=2027) lists no ECAPSH release yet. INE announces
  structural releases two months ahead (IME: «el último viernes de cada mes (t) se anuncia el día
  exacto de publicación de las estadísticas estructurales programadas para el mes (t+2)»).
- **Expected: late September 2027, unverified.** The operation is in the Programa anual 2026 (IOE
  30469: «Figura en el Programa anual 2026: Sí»).

## 3. Data and vintage lock

- **INE tables** (`csv_bdsc` files of INEbase), editions 2012–2024: 48 files, listed with URL and
  SHA-256 in `scripts/locked_inputs.json`, downloaded on 2026-10-04. INE replaces tables in place
  when it revises them; `scripts/fetch.py` reports any file whose hash has changed.
- **The 2024 release page** (live) and its **Internet Archive capture** of 2025-09-26 13:25:24 UTC.
- **Reception system**: Ministerio de Inclusión, Seguridad Social y Migraciones, «Informe Sistema de
  Protección Internacional español», 20 June 2025, Gráficos 1 and 2 (places of the Sistema de
  Acogida de Protección Internacional, SAPI, and of the Programa de Atención Humanitaria, PAH),
  published on La Moncloa. `www.inclusion.gob.es` and `www.interior.gob.es` answered our User-Agent
  with 403 or a bot challenge at `robots.txt` and were not used.
- **Asylum applicants**: Eurostat `migr_asyappctza` (geo ES), updated 2026-09-03.
- **Arrivals**: AIDA (ECRE) country reports on Spain, which cite the Ministry of the Interior.

For ECAPSH 2026, the scoring uses the INE tables whose titles match the 2024 roles:
- «Centros según especialización por titularidad del centro y tamaño del municipio de ubicación del centro» (2024: 75637);
- «Centros según servicios y/o prestaciones ofrecidas por especialización» (2024: 75639, row «Alojamiento»);
- «Número medio de plazas de alojamiento existentes y ocupadas por mayores de 18 años según especialización y titularidad del centro» (2024: 75652);
- «Número de plazas de alojamiento existentes y número de plazas ocupadas por mayores de 18 años a … según tipo de centro por titularidad del centro» (2024: 75651).

The 2024 tables are re-downloaded on the day of the 2026 release. If INE has revised them, both
vintages are reported and the predictions are scored against the 2024 vintage locked here and,
separately, against the revised one.

## 4. Notation and in-sample results (2022 → 2024, not blind)

- `O_s`: mean daily occupied places (adults from 2022) in segment `s` ∈ {IMM, GBV, OTH}; core = GBV + OTH.
- `C_s`: centres offering accommodation in segment `s` (row «Alojamiento» of the services table).
- `o_s = O_s / C_s`: occupied places per centre offering accommodation.
- `ΔO_s = ΔC_s · (o_s,0 + o_s,1)/2 + Δo_s · (C_s,0 + C_s,1)/2` (exact, symmetric).

| quantity | 2022 | 2024 | change |
|---|---|---|---|
| total occupied | 21,684 | 34,145 | +12,461 (+57.5%) |
| IMM occupied | 8,045 | 18,173 | +10,128 (81.3% of the change) |
| core occupied | 13,639 | 15,973 | +2,334 (+17.1%) |
| core centres offering accommodation | 673 | 753 | +11.9% |
| core occupied per centre | 20.27 | 21.21 | +4.7% (log +0.046) |
| core occupancy (occupied / places) | 84.8% | 85.9% | +1.1 points |

Four-way split of +12,461: IMM centres +5,128; IMM per centre +5,000; core centres +1,659; core per
centre +675 (`data/decomposition.csv`).

## 5. Readings and predictions for ECAPSH 2026 (2024 → 2026)

**Reading A, "frame and composition".** The ECAPSH total moves with the number of centres in the
published tables and with the capacity of the immigrant reception network that the directory
covers. Outside immigrant-only centres the network is stable per centre.

**Reading B, "real growth".** The ECAPSH total moves with the number of people who need shelter.
Existing centres outside the immigrant-only group fill up: they hold more people per centre and run
fuller, and the core grows faster than its number of centres.

| # | quantity (2024 value) | reading A predicts | reading B predicts |
|---|---|---|---|
| P1 | log change of core occupied per centre offering accommodation, ln(o_core,2026 / o_core,2024) (2024: 21.21) | within [−0.10, +0.10] (19.19 to 23.44 per centre) | above +0.10 |
| P2 | change in core occupancy, occupied / places, in percentage points (2024: 85.9%) | within [−4, +4] (81.9% to 89.9%) | above +4 |
| P3 | which group drives the total change | \|ΔO_IMM\| > \|ΔO_core\| | \|ΔO_core\| ≥ \|ΔO_IMM\| |
| P4 | direction of ΔO_IMM against the change in SAPI + PAH places between 31-Dec-2024 (56,963) and 31-Dec-2026 | same sign, scored only if the reception change is at least ±10% | no prediction |

The frozen values are in `data/predictions_2026_spec.json`.

**Context, not a prediction.** Arrivals by land and sea fell from 63,970 in 2024 to 36,775 in 2025
(AIDA, from the Ministry of the Interior), and to the Canary Islands by sea from 46,843 to 17,788.
SAPI places rose from 29,444 (31-Dec-2024) to 34,062 (15-Jun-2025), and PAH places fell from 27,519
to 24,532. Neither reading fixes the total for 2026.

## 6. Scoring

- **Verdict per prediction**: "A" if the value falls in A's region, "B" if in B's region, "neither"
  otherwise (for P1 and P2, a value below the A interval).
- **Overall**:
  - *A supported*: P1, P2 and P3 all "A", and P4 "A" or not scored.
  - *B supported*: P1 and P2 both "B" (P3 is reported but not required, because a large IMM change
    of either sign can dominate P3 under either reading).
  - *Mixed*: anything else.
- **P4** uses the Ministry's published end-2026 figure for SAPI and PAH places. If it is not published
  in a report we can access under the rules of §3 by the day of scoring, P4 is not scored and that is
  stated.
- Scoring is done within 14 days of the release, with the same code (`scripts/build.py`,
  `scripts/analyse.py`) pointed at the 2026 tables. The result is published whatever it is.

## 7. What would falsify each reading

- **Reading A** is falsified by P1 or P2 in B's region, or by a P4 sign mismatch with a reception
  change of at least ±10%.
- **Reading B** is falsified by P1 and P2 both inside A's intervals while the core's number of
  accommodation centres changes by less than its occupied places would require. In other words,
  core occupancy moves in step with core centres.
- **The design cannot separate** a new centre that opened from one that was already open and entered
  the directory or answered for the first time: INE publishes neither the directory nor the panel of
  respondents. "Frame" in this protocol therefore means *centres in the tables*, an upper bound on
  the pure directory-and-response effect.

## 8. Checks to run on the 2026 release

1. Segment sums equal the published totals (±2, INE rounds means).
2. INE's wording: does the release separate immigrant-only centres in its headline? Does it give
   an explanation as in 2022 (Ukraine, COVID-19 capacity) and 2024 (Canary Islands)?
3. Response rate and over-coverage in the IME, compared with 2024 (79.9%, 10.8%).
4. Any change in the specialisation item, in the adults-only rule, or in the reference dates.
5. Any revision of the 2024 tables (hash check, §3).

## 9. Stopping rule and timeline

- 2026-10-04: protocol written. The coordinator registers it by commit before publication of the
  study.
- ECAPSH 2026 release (expected late September 2027): scoring within 14 days (§6).
- If INE has not published ECAPSH 2026 by 31-Dec-2027, or publishes it without the specialisation
  breakdown, the out-of-sample test is reported as not possible and the protocol is closed.

## 10. Threats to validity

- **Classification by self-declaration.** In 2024 the centre ticks its own specialisation on the
  questionnaire cover. A centre serving mostly, but not exclusively, asylum seekers may tick "other",
  and a change in how centres answer moves places between IMM and core without any change on the
  ground. P1–P3 are reported with core = OTH only as a sensitivity check.
- **Two snapshots a year.** Occupancy is the mean of two dates (mid-June and mid-December). Reception
  capacity in the Canary Islands peaks in winter, so the December date weighs heavily.
- **Rounding.** INE rounds means; segment sums differ from totals by up to 1.
- **Non-response.** 20% of directory units do not answer and are not imputed. A change in response
  moves the total.
- **Reception data are not ECAPSH data.** The Ministry's SAPI and PAH places include flats,
  hotel places and units that may not be in the ECAPSH directory. P4 tests direction only.

## 11. Ethics

Aggregates only: national and regional figures published by INE and the Ministry. No unit-level data,
no centre names, no data on individuals. The study examines what the statistic measures. People in
asylum and humanitarian reception centres are houseless under ETHOS and under the Strategy's own
definition, and a record driven by reception capacity is still a record of people needing shelter.
Nothing in this protocol attributes homelessness to asylum seekers.

## 12. Deviations and dated events

- 2026-10-04: protocol written; awaiting registration by commit.
- 2026-10-04 21:27 +0200: registered by commit `844d5a3` (this file only). The commit was local when
  this entry was written. It becomes a public timestamp when pushed. The text above this section is
  unchanged since that commit.
- 2026-10-04, after an independent adversarial review (`private/REVIEW.md`), before any 2026 data
  exist. **D1–D5 below clarify or correct; none changes a registered interval.**

**D1. Scoring made computable and symmetric.** This replaces §6 "Overall" and §7 where they differ.
The intervals of §5 stand.

- **Quantities.** All are measured from the 2024 tables locked in §3:
  - `q1 = ln(o_core,2026 / o_core,2024)`, where `o` is occupied places per centre offering
    accommodation and core = GBV + OTH. 2024 baseline: 21.21.
  - `q1_oth`: the same, with core = OTH only. 2024 baseline: 22.87; band 20.69 to 25.27. It is made
    co-primary because a change in the GBV/OTH mix can move `q1` on its own: from 2022 to 2024 GBV
    per centre fell −24.6% and OTH rose +7.9%.
  - `q2`: core occupancy in 2026 minus 2024, in percentage points. 2024 baseline: 85.9%.
- **Per-centre pressure** = `q1 > +0.10` AND `q1_oth > +0.10` AND `q2 > +4`.
- **No per-centre pressure** = `|q1| ≤ 0.10` AND `|q1_oth| ≤ 0.10` AND `|q2| ≤ 4`.
- **Reading B is falsified** if and only if there is no per-centre pressure. This replaces the
  sentence in §7 that could not be computed («changes by less than its occupied places would
  require»).
- **Reading A is falsified** if there is per-centre pressure, or if P4 is scored and both measures
  below mismatch.
- **P4 is computed twice**: on IMM occupied places, as registered, and on IMM places, which is
  like-for-like with the Ministry's places. Each gives a sign against the change in SAPI + PAH places
  from 31-Dec-2024 (56,963) to 31-Dec-2026, and is scored only if that change is at least ±10%. The
  result is "A on both", "mismatch on both" or "mixed".
- **Verdicts.** Reading A no longer wins by default:

  | verdict | condition |
  |---|---|
  | B supported (per-centre pressure in the core) | per-centre pressure; P4 reported alongside |
  | A supported | no per-centre pressure AND P4 scored AND "A on both" |
  | no per-centre pressure; A and growth through new centres not separable | no per-centre pressure AND (P4 not scored OR "mixed") |
  | A rejected on P4; no per-centre pressure | no per-centre pressure AND P4 "mismatch on both" |
  | undetermined | any other combination, e.g. pressure on one core definition only, `q2` outside ±4 with `q1` inside, or `q1` below −0.10; reported with the values |

- **P3** is reported but not used in any verdict: a large immigrant-only swing of either sign says
  nothing about the core.
- **Classification break.** If INE changes the specialisation item, the ETHOS-based scope of §5 of
  its 2024 methodology, the adults-only rule or the reference dates, all values are reported and the
  verdict is "not scored (classification break)".
- **The rules are code.** They are implemented in `scripts/score_2026.py` (`--dry-run` applies them
  to 2022 → 2024, in sample).

**D2. What the freeze commit must contain.** Code and frozen values, committed before publication
and before INE publishes the 2026 edition:
- `scripts/s22lib.py`, `scripts/build.py`, `scripts/analyse.py`, `scripts/score_2026.py`,
  `scripts/fetch.py`, `scripts/locked_inputs.json`, `scripts/run.sh`, `tests/test_s22.py`;
- `data/predictions_2026_spec.json`, the frozen 2024 baselines, intervals and D1 rules;
- the in-sample outputs `data/*.csv`, `data/summary.json` and `data/score_dryrun.json`.

At scoring, the only code change allowed is adding the 2026 table ids, found by the titles of §3,
to the id maps in `build.py`. Any other change is a new deviation.

**D3. Corrections to facts stated in §2** (the predictions do not depend on them):
- **The 2024 definition changed.** §2.2 says the specialisation wording is the same in 2020–2024,
  which holds for that item only. §5 of INE's 2024 methodology replaces the 2020/2022 definition with
  ETHOS: «En esta encuesta se toma como referencia la Tipología europea de sinhogarismo y exclusión
  residencial (ETHOS …) contemplada en la Estrategia Nacional …». It lists «Personas en centros de
  alojamiento para solicitantes de asilo e inmigrantes: Personas inmigrantes que viven en
  alojamientos temporales por su estatus de extranjeros o trabajadores temporeros».
- **What the 2020 and 2022 methodologies said instead.** They added immigrant centres «para
  asegurar la continuidad de la serie histórica y la comparabilidad internacional» (CETI, CAR, and
  separately «Centros destinados al alojamiento de trabajadores temporeros …»). **The frame
  definition changed in the record year.**
- **The full revision paragraph of the IME.** §2.1 quoted «No existe revisión de datos» alone. The
  paragraph reads: «Esta política general fija los criterios que se deben seguir para los diferentes
  tipos de revisiones: rutinarias …; revisiones mayores, por cambios metodológicos o de fuentes
  básicas de referencia de la estadística; y revisiones extraordinarias (por ejemplo, las debidas a
  un error en estadísticas ya publicadas). No existe revisión de datos.» §17.2: «Los datos se publican
  cuando son definitivos, no están sujetos a revisión.»
- **What changed in the release.** It changed after publication. Its regional table changed only in
  Navarre (403 → 790 mean places) and the national total, and those six cells are shown in red. No
  note says what changed or why.

**D4. §7, "the design cannot separate".** The centres term is not an upper bound on the frame
effect. A midpoint split books a new centre at average size, so a frame change can sit in either
term. The October 2025 revision added one immigrant-specialised centre with 387 occupied places: of
those, 100 went to the centres term and 287 to the per-centre term. This is a further reason for D1:
`q1` alone is not evidence for either reading.

**D5. §2.4.** INE's 2027 calendar («Última actualización: 25 Septiembre 2026») lists a single
release (FRONTUR-EGATUR). The expected ECAPSH date remains an inference from past release dates.
