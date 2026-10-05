# S12 — Protocol: is the record low of practised evictions in Q1-2026 an artefact of the court reform?

EasyxLab · study S12 · **protocol written on 2026-10-04 and registered by its first commit, before the
CGPJ publishes its Q2-2026 data (scheduled for 2026-10-16, §2.5).** Later changes are listed, dated,
in §14 ("Deviations"); nothing above §14 is edited after registration except to fix typos.

**What is and is not blind.** Before this protocol was written, the following had been seen: the
national Q1-2026 figures (CGPJ, 22 June 2026); a scout's unaudited pilot of 2026-10-03 (per-province
medians, Barcelona, Ribadavia); and, while the CGPJ files were searched for methodology notes on
2026-10-04, the quarterly TSJ-level figures of practised rent (LAU) evictions. No relationship between
any outcome and the phase of the reform was computed. The in-sample tests (§5, H1a–H5) are therefore
designed after seeing national and some regional aggregates, and are **not blind**. The only fully
blind test is the out-of-sample use of the Q2-2026 release (§7). The pilot figures are not reused:
everything is recomputed from the files locked in §3.3.

## 1. Research questions

- **RQ1 (timing).** Does the fall in practised evictions recorded by the courts concentrate in the
  judicial districts, and in the quarters, in which those districts' courts were turned into
  *tribunales de instancia* (LO 1/2025: 1 July 2025, 1 October 2025, 31 December 2025)?
- **RQ2 (mechanism).** At the same time and place, do evictions received and completed by the common
  services (*servicios comunes*) rise, as they would if the work moved from the count kept by the
  court to the count kept by the common service?
- **RQ3 (size).** How much of the national fall from Q1-2025 to Q1-2026 (7,334 → 4,005, −45.4%) is
  (a) data the CGPJ itself reports as missing or estimated, (b) a change in counting tied to the
  phased reform, and (c) a national residual (real changes and anything uniform across districts)?
  Does Q1-2026 remain the lowest quarter of the series once (a) and (b) are removed?
- **RQ4 (persistence, out-of-sample).** Is any phase-related effect transient (the first quarter of
  the new organisation) or persistent (a lasting change in what is counted)?
- **RQ5 (data quality).** Do the CGPJ's district, province and TSJ files agree with each other and
  across successive releases?

## 2. Facts verified before registration (literal text, retrieved with `curl` on 2026-10-04)

### 2.1 The law in force: LO 1/2025

| item | literal text | source |
|---|---|---|
| Entry into force; consolidation | «Entrada en vigor: 03/04/2025» · «Última actualización publicada el 04/06/2025» | https://www.boe.es/buscar/act.php?id=BOE-A-2025-76 |
| Rollout of the *tribunales de instancia* (transitional provision 1) | «La constitución de los Tribunales de Instancia se realizará de manera escalonada conforme al siguiente orden: 1.º El día 1 de julio de 2025 los Juzgados de Primera Instancia e Instrucción y los Juzgados de Violencia sobre la Mujer, en aquellos partidos judiciales donde no exista otro tipo de Juzgados, se transformarán, respectivamente, en Secciones Civiles y de Instrucción Únicas y Secciones de Violencia sobre la Mujer. 2.º El día 1 de octubre de 2025, los Juzgados de Primera Instancia, los Juzgados de Instrucción y los Juzgados de Violencia sobre la Mujer, en los partidos judiciales donde no exista otro tipo de Juzgados, se transformarán, respectivamente, en Secciones Civiles, Secciones de Instrucción y Secciones de Violencia sobre la Mujer. 3.º El día 31 de diciembre de 2025, los restantes Juzgados, no comprendidos en los supuestos anteriores, se transformarán en las respectivas Secciones conforme a lo previsto en la presente ley.» | same, DT 1.ª |
| Court office (transitional provision 5) | «La implantación de la Oficina judicial será simultánea a la de los Tribunales de Instancia» — but the Conferencia Sectorial «podrá también aprobar … una fecha diferente para el establecimiento de alguna de las oficinas judiciales» when «concurren circunstancias excepcionales», and where staff lists are not approved «se mantendrá el régimen de organización de las oficinas y de su personal anterior … dentro de los seis meses siguientes» | same, DT 5.ª |
| Mandatory prior negotiation (MASC) | Required «en todos los procesos declarativos del libro II y en los procesos especiales del libro IV» of the LEC, with listed exceptions (art. 5.2); «No será preciso acudir a un medio adecuado de solución de controversias para la interposición de una demanda ejecutiva» (art. 5.3); only for «procedimientos incoados con posterioridad a su entrada en vigor» (DT 9.ª.1) | same |
| Eviction for unpaid rent is a Book II proceeding | LEC art. 250.1.1.º («Las que versen sobre reclamación de cantidades por impago de rentas … pretendan … recuperen la posesión de dicha finca») sits inside «LIBRO II De los procesos declarativos»; not among the art. 5.2 exceptions. LEC consolidated: «Última actualización publicada el 30/09/2026» | https://www.boe.es/buscar/act.php?id=BOE-A-2000-323 |

**Later amendments and annulments.** The BOE analysis page lists, as later references: modifications
of final provision 8.18 by Real Decreto 388/2025 (BOE-A-2025-9384) and Real Decreto 422/2025
(BOE-A-2025-11069); a correction of errors (BOE-A-2025-461) that replaces annex II.2 of Ley 15/2003
inside final provision 13; constitutional questions 5810/2025 and 6723/2025 (DT 14 and DF 7.2) and
8318/2025 (art. 5.2); conflict 2764/2025 (DF 13); appeal 2440-2025 (DF 7.2). **None amends or annuls
transitional provision 1 or 5**; the rollout dates above are the law in force
(https://www.boe.es/buscar/doc.php?id=BOE-A-2025-76, «Referencias posteriores»). A pending question
on art. 5.2 (MASC) does not change the rollout.

### 2.2 Districts per phase

| item | literal text / count | source |
|---|---|---|
| Totals per phase (Ministry of Justice, 30 June 2025) | «El próximo 1 de julio entrarán en funcionamiento 315 Tribunales de Instancia (TI)» · «16 nuevos tribunales el 1 de octubre y 100 adicionales el 31 de diciembre, hasta alcanzar los 431 Tribunales de Instancia en todo el territorio nacional» · «Cada Tribunal de Instancia contará además con un nuevo modelo de Oficina Judicial, que centralizará los servicios comunes» | https://www.mjusticia.gob.es/es/institucional/gabinete-comunicacion/noticias-ministerio/300625-primeros-315-tribunales-instancia |
| Court-by-court name changes, all three phases (Ministry, DG for the Digital Transformation of Justice; xls, Last-Modified 2025-12-17) | Sheet «Cambios NUMO fase 1»: former courts in **315** seat municipalities, all regions. Sheet «Cambios NUMO fase 2»: **16**. Sheet «Cambios NUMO (MJU) fase 3»: **30**, Ministry-managed territory only | https://www.administraciondejusticia.gob.es/documents/d/asset-library-5650231/cambios-lexnet-numo-fase-1-2-y-3-v1-0-1-xls (linked from the DG's letter of 19-Dec-2025: https://www.cograsova.es/adjuntosmail/2025/20251229/ComunicadoLexNetColegiosProfGS.pdf) |
| Phase 3 total (same letter) | «se actualizarán con las nuevas denominaciones en los 100 partidos judiciales de todo el territorio español incluidos en esta tercera fase» · «Los Juzgados Decanos … dejarán de estar operativos, para pasar a remitirse los escritos a los servicios comunes de registro y reparto del partido judicial» | same PDF |
| Phase 2 list (Madrid Bar, 1-Oct-2025) | «Fuengirola, Marbella y Torremolinos (Málaga); San Bartolomé de Tirajana y Telde (Las Palmas); Arona y San Cristóbal de La Laguna (Santa Cruz de Tenerife); Badalona y L'Hospitalet de Llobregat (Barcelona); Alcobendas, Fuenlabrada y Torrejón de Ardoz (Madrid); Denia y Torrent (Valencia); Inca y Manacor (Illes Balears)» — identical to the xls sheet; the xls places Dénia in Alicante | https://web.icam.es/comienza-la-segunda-fase-de-transformacion-de-los-organos-judiciales/ |
| Districts in the CGPJ district file | 431 rows, one per judicial district, matching the 431 TI | D1 (§3.1) |

**Phase list used.** Phase 1 = the 315 districts of sheet «fase 1»; phase 2 = the 16 of sheet «fase 2»;
phase 3 = the other 100 of the 431. The 30 districts of sheet «(MJU) fase 3» must all fall in that
remainder (check DQ6). No single official list names the 70 phase-3 districts outside the
Ministry-managed territory; they are obtained by complement, which the three official totals
(315 + 16 + 100 = 431) make exact.

### 2.3 What the CGPJ says about counting evictions

**Methodology page** (https://www.poderjudicial.es/cgpj/es/Temas/Estadistica-Judicial/Estudios-e-Informes/Efecto-de-la-Crisis-en-los-organos-judiciales/):
- «Lanzamientos con cumplimiento positivo: Aquellos lanzamientos en los que el Servicio Común ha
  podido practicar el lanzamiento acordado por el juzgado.»
- «En las localidades donde existen servicios comunes con funciones de actos de comunicación y
  ejecución, estos reciben de los Juzgados de Primera Instancia y Juzgados de Primera Instancia e
  Instrucción el encargo de practicar los lanzamientos. Al no existir este tipo de servicios en todos
  los partidos judiciales, el dato que se obtiene de los mismos tiene interés para seguir la
  evolución histórica pero no para conocer el volumen total de lanzamientos. El dato recogido en los
  juzgados de primera instancia y de primera instancia e instrucción (disponible desde el 1T de 2013)
  si debe ser exhaustivo»
- «EN NINGUN CASO DEBE SUMARSE EL NUMERO DE LOS PRACTICADOS POR LOS JUZGADOS DE PRIMERA INSTANCIA CON
  EL DE LOS PRACTICADOS EN LOS SERVICIOS COMUNES.»
- The page does not mention LO 1/2025, the *tribunales de instancia* or the *secciones*; the
  definitions still refer to *juzgados*.

**Notes inside each quarterly release** (files of §3.3):

| release (Last-Modified) | note on evictions, literal |
|---|---|
| Q1-2025 (2025-06-16) | none |
| Q2-2025 (2025-10-13) | none |
| Q3-2025 (2025-12-12) | «En este trimestre los datos de lanzamientos han sido estimados debido a la falta de información completa en algunos partidos judiciales.» TSJ sheets: «* Datos estimados debido a la falta de información completa en 64 partidos judiciales»; province sheet: «… en 66 partidos judiciales». Sheet «Nota falta datos lanzamientos» lists 64 districts, «a fecha de cierre del informe ( 9/12/2025)» |
| Q4-2025 (2026-03-20) | «Partidos judiciales con falta de información parcial sobre lanzamientos a fecha de cierre del informe ( 18/12/2025)»: Estella-Lizarra, Guimar, La Línea de la Concepción, Ubrique. On the new annex of suspensions: «Estos datos se han incorporado recientemente al proceso estadístico y continúan sujetos a la implantación progresiva de controles adicionales de consistencia, completitud y calidad.» |
| Q1-2026 (2026-06-22, «_revisado») | «Se acompaña la lista de partidos judiciales para los que no ha sido posible disponer de la información en la fecha de cierre de este informe.» Sheet «Nota falta datos», «( 18/06/2026)»: **Donostia/San Sebastián, Gijón, Vinarós**. Practised LAU and «otros» evictions of MADRID, COMUNIDAD marked «*Dato estimado». Suspensions annex: «No ha sido posible disponer de la información correspondiente a los siguientes Tribunales de Instancia: Donostia-San Sebastián, Gijón, Madrid.» |

The provincial and TSJ series files («Series … 1T-2026_revisado»), which most reusers download, carry
none of these flags. In the Q1-2026 release file, the sheet of practised LAU evictions by TSJ heads its
Q1-2026 column «25-T1» (a label slip; position and totals identify it as 26-T1).

**Conclusion of the check.** The CGPJ **does not explain any change in how practised evictions are
counted after the reform.** It does disclose, in each of the three quarters after the reform began,
missing or estimated eviction data in specific districts: estimates for 64 districts in Q3-2025 (the
quarter of phase 1), partial gaps in 4 in Q4-2025, and no data for 3 districts plus estimated Madrid
LAU and «otros» figures in Q1-2026. **This changes the study in one respect:** part of the Q1-2026 fall
may be data the CGPJ already reports as missing, so that component is measured separately (§6.4,
component a) from any undisclosed change in counting (component b). The question itself stands.

**Who called it a record.** The −45.4% is the CGPJ's; the phrase «la cifra más baja desde que hay
registros comparables» is the press's reading of it (https://www.que.es/2026/06/22/desahucios-2026-caida-45-cgpj/,
22-Jun-2026), which also wrote «la protección a los inquilinos parece estar frenando la sangría».

### 2.4 National events in the window (confounders handled by quarter effects)

- Suspension of evictions of vulnerable households, RDL 11/2020 art. 1: «hasta el 31 de diciembre de
  2025» (consolidated text, «Última actualización publicada el 28/02/2026»,
  https://www.boe.es/buscar/act.php?id=BOE-A-2020-4208). Two extensions were in force briefly in
  Q1-2026 and repealed by Congress: RDL 16/2025 (amendment published 24/12/2025; repeal by Resolución
  de 27 de enero de 2026, BOE-A-2026-2024) and RDL 2/2026 (amendment published 04/02/2026; repeal by
  Resolución de 26 de febrero de 2026, BOE-A-2026-4667). The Q1-2025 baseline also contains a lapse:
  RDL 9/2024 was repealed by Resolución de 22 de enero de 2025.
- MASC requirement for new civil claims from 3 April 2025 (§2.1).
- These events are national. They differ across districts only through who is affected (§12).

### 2.5 Release calendar and the Q2-2026 release

- CGPJ calendar (https://www.poderjudicial.es/cgpj/es/Temas/Estadistica-Judicial/Calendario-de-Publicaciones/):
  «Efectos de la crisis económica en los órganos judiciales 22/06/2026 16/10/2026 14/12/2026
  22/03/2027». **Q2-2026 is due on 2026-10-16.**
- Past releases (HTTP Last-Modified of the files): Q1-2025 2025-06-16; Q2-2025 2025-10-13; Q3-2025
  2025-12-12; Q4-2025 and annual 2025 2026-03-20; Q1-2026 2026-06-22.
- On 2026-10-04 at 11:56 UTC the CGPJ page listed Q1-2026 as the latest release. No Q2-2026 file has
  been accessed.

## 3. Data

### 3.1 Series

All from the CGPJ's quarterly «Efecto de la crisis en los órganos judiciales», province and TSJ series
(«Series … por provincias / por TSJ»), and its district file «Lanzamientos por PJs 2013-2025» (D1).

| id | CGPJ series | level and period | role |
|---|---|---|---|
| P-TOT | Lanzamientos practicados, total (courts) | province and TSJ, quarterly 2013-T1 to 2026-T1; district, annual 2013–2025 | primary outcome |
| P-HIP / P-LAU / P-OTR | practised, from mortgage enforcement / urban leases (LAU) / other | same | H4 |
| SC-REC | Lanzamientos recibidos en los servicios comunes | province and TSJ, quarterly | H2 (exploratory) |
| SC-POS | Lanzamientos con cumplimiento positivo (common services) | province and TSJ, quarterly | H2, H3 |
| NC-EH | Ejecuciones hipotecarias presentadas (intake; MASC-exempt, art. 5.3) | province, quarterly | negative control |
| NC-DES | Despidos presentados (social courts) | province, quarterly | negative control |
| PC-MON | Monitorios presentados (intake; MASC applies) | province, quarterly | positive control for national shocks |

Population, rental-market or suspension data are not used in confirmatory tests.

### 3.2 Phase and timing

Each district `d` gets its phase `c(d)` from §2.2 and an event quarter `T_c`: phase 1 → 2025-Q3,
phase 2 → 2025-Q4, phase 3 → 2026-Q1 (the transformation took effect on the last day of 2025-Q4; Q1-2026
is its first quarter of operation). Event time `e(d,t) = t − T_c(d)` in quarters. Districts are
matched to D1 by normalised name (accents, articles, bilingual forms); the province of each district
comes from a district-to-province table built from official sources (the xls province column and the
CGPJ's table of judicial districts and municipalities); every unmatched or ambiguous name is listed
(DQ6). The transformation date of DT 1.ª is the treatment
date (intention to treat); any district whose court office (DT 5.ª) is found to have started on a
different date is listed and handled in a sensitivity analysis (S10), not in the primary analysis.

### 3.3 Vintage lock

The confirmatory in-sample analysis uses exactly these files (downloaded 2026-10-04, 5 s between
requests to poderjudicial.es; raw files are not redistributed):

| file (under `https://www.poderjudicial.es/stfls/ESTADISTICA/FICHEROS/Crisis/`) | Last-Modified (GMT) | SHA-256 |
|---|---|---|
| `Series - Efecto de la crisis en los organos judiciales por provincias 1T-2026_revisado.xlsx` | 2026-06-22 06:37:54 | `065ba5674539dad999dda6e15e93ba0b41884162115c7cfe20e23672c2f8c5a7` |
| `Series - Efecto de la crisis en los organos judiciales por TSJ 1T-2026_revisado.xlsx` | 2026-06-22 06:37:55 | `6c72240817fc88e2fdef7543c7c708aee57a23707700d175c419d5b4c65a8f05` |
| `Lanzamientos por PJs_2013_ 2025.xlsx` (D1) | 2026-03-20 11:01:06 | `6d6023a2b5c738ae0ff4360722209e50ac8ea7be971033d480869bca741c7218` |
| `Datos sobre el efecto de la crisis en los organos judiciales 1T-2026- con Microempresas_revisado.xlsx` | 2026-06-22 06:31:36 | `50be1668f168c950a91ce0f41af77b3f69ae97697571797e7fd7dfdc6465658c` |
| `Datos sobre el efecto de la crisis en los organos judiciales - Anual 2025.xlsx` | 2026-03-20 11:01:06 | `c96015b93e36fde0c618c467f5938e3830cbbd8b1c9e03d49c79b012a61a8873` |
| `Datos sobre el efecto de la crisis en los organos judiciales 4T-2025- con Microempresas.xlsx` | 2026-03-20 11:01:06 | `8a6e0fe34ab7fca4e549e546edeb8f91c6f97ff4f7fe30ecc8cf95056bbf1470` |
| `Datos sobre el efecto de la crisis en los organos judiciales 3T-2025- con Microempresas.xlsx` | 2025-12-12 09:24:36 | `fe520fd7b028b690739ce90c5ceff74c74f11e95ce1d63532b6bdcf44f1ce1fd` |
| `Datos sobre el efecto de la crisis en los organos judiciales 2T-2025- con Microempresas.xlsx` | 2025-10-13 07:53:39 | `2d2450efb4119ab4424ed77ba3d22bff0222f4efb9cb8f08c96cd1ca0f96cbfb` |
| `Datos sobre el efecto de la crisis en los organos judiciales 1T 2025- con Microempresas.xlsx` | 2025-06-16 06:57:20 | `0c98a475284d988fdcab69abb69750f49394bcf59265e9ef4bf10e9cc6e409eb` |
| phase list, `cambios-lexnet-numo-fase-1-2-y-3-v1-0-1-xls` (administraciondejusticia.gob.es) | 2025-12-17 07:39:23 | `12925b64224211b58c343d9e8f79baf7c15f9e4dcda06623df50591a74e76e2b` |

The province series file is the primary source for province × quarter values (latest vintage). The
quarterly release files are used for the flags of §2.3 and for the vintage comparison (DQ2).

## 4. Notation

- `p` province (every province row of the series file, including Ceuta and Melilla if listed);
  `t` quarter; `Y_pt` a count.
- `g_pt = ln Y_pt − ln Y_p,t−4`: year-on-year log change (removes seasonality, including August).
- `Δg_p(t) = g_pt − g_p,t−1`: change in year-on-year growth from one quarter to the next.
- `w_d`: district `d`'s share of its province's practised evictions (P-TOT) over 2023 + 2024 (D1).
  `W_c,p = Σ w_d` over the districts of phase `c` in `p`. `W1 + W2 + W3 = 1`.
- `B_p`: province's P-TOT in 2024 (sum of four quarters); the regression weight.
- `S^(k)_pt = Σ_d w_d · 1[e(d,t) = k]`: share of the province's baseline in districts at event time `k`.
- `ρ_k`: proportional change in the count a district records at event time `k`, relative to what it
  would record without the transformation. Artefact means `ρ_0 < 0`.

Why the cross-section works. Between 2025-Q4 and 2026-Q1, phase-3 districts move from event time −1
to 0, phase-2 from 0 to 1 and phase-1 from 1 to 2, while the year-on-year base quarters (2024-Q4,
2025-Q1) are before every transformation. To first order,
`Δg_p(2026-Q1) ≈ const + (ρ_0 + ρ_1 − ρ_2)·W3_p + (2ρ_1 − ρ_0 − ρ_2)·W2_p`, so the slope on `W3`
equals `ρ_0` whenever the phase-1 effect is stable between its second and third quarter (`ρ_1 = ρ_2`),
whether the effect is transient (`ρ_1 = ρ_2 = 0`) or persistent (`ρ_1 = ρ_2 = ρ_0`). National events
(moratorium windows, MASC, the market) enter the constant. Between 2025-Q2 and 2025-Q3 only phase 1
moves (−1 → 0), so `Δg_p(2025-Q3) ≈ const + ρ_0·W1_p`.

## 5. Hypotheses (fixed 2026-10-04)

**H1a — Phase 3 (primary).** In Q1-2026, practised evictions (P-TOT) fall more in provinces with a
larger share of phase-3 districts: in `Δg_p(2026-Q1) = a + b3·W3_p + b2·W2_p + u_p`, **b3 < 0**.

**H1b — Phase 1 (primary).** In Q3-2025, P-TOT falls more in provinces with a larger share of phase-1
districts: in `Δg_p(2025-Q3) = a + b1·W1_p + u_p`, **b1 < 0**.

**H2 — Work moves to the common services.** In Q1-2026, evictions completed by the common services
(SC-POS) rise with the phase-3 share: H1a's model for SC-POS gives **b3 > 0**. (SC-REC is reported
with the same model, two-sided, exploratory; phase-1 SC results are exploratory, because before the
reform common services existed mostly in the larger, phase-3 districts.)

**H3 — The court-to-service ratio breaks.** In Q1-2026, `ln(P-TOT / SC-POS)` falls with the phase-3
share: **b3 < 0**.

**H4 — The change does not depend on the type of eviction.** A counting change affects every type;
the MASC requirement and the suspension windows affect rent evictions only. H1a's model for P-HIP
gives **b3 < 0**, and the difference `b3(LAU) − b3(HIP)` has a 95% interval that includes 0.

**H5 — Within-province, district-level, annual (D1).** In 2025, practised evictions fall more in phase-1
districts (two quarters as *tribunal de instancia* in 2025) than in phase-3 districts of the same
province (none): in `ln(Y_d,2025 + 1) − ln(Y_d,2024 + 1) = α_province + δ1·phase1_d + δ2·phase2_d + e_d`,
weighted by `Y_d,2023 + Y_d,2024`, **δ1 < 0**.

**H6 — Persistence (out-of-sample, Q2-2026).** Stated and tested in §7; two-sided, because "transient"
and "persistent" are both readings of a confirmed artefact.

**Rival explanations and their signatures** (used to read the pattern of H1–H5 jointly):

| explanation | P-TOT slope on W3 (Q1-26) | SC-POS slope | ratio slope | rent vs mortgage | Q2-2026 |
|---|---|---|---|---|---|
| counting change at transformation (artefact) | − | + or 0 | − | both − | transient: recovery; persistent: no change |
| data the CGPJ reports missing | concentrated in Gipuzkoa, Asturias, Castellón | 0 | − there | both | upward revision of Q1-2026 |
| real national fall (suspension windows, MASC, market) | 0 | 0 | 0 | rent falls more, nationally | — |
| MASC, felt later in slower large-city courts (real) | − | − | ≈ 0 | rent only | fall continues |
| suspension windows used more in large cities (real) | − | − or 0 | ≈ 0 | rent only | recovery (windows ended 26-Feb-2026) |

## 6. Identification and estimation

### 6.1 Primary tests (H1a, H1b) and their siblings (H2–H4)

Weighted least squares across provinces, weights `B_p`. Provinces with a count below 10 in any of the
four quarters entering `Δg_p` are excluded from that test and listed (included in sensitivity S6).
Inference: HC3 standard errors, one-sided p-values in the predicted direction; and a permutation
p-value from 10,000 random reassignments of the phase-share vectors `(W1, W2, W3)` across provinces.
**Supported** requires the HC3 p-value, after Holm (§6.5), and the permutation p-value both to be ≤ 0.05. For SC series, only provinces with common-service
receipts in every quarter of 2024–2026-Q1 enter.

### 6.2 Pooled staggered model (secondary, used for the decomposition)

`g_pt = γ_t + ln(1 + Σ_k ρ_k S^(k)_pt) − ln(1 + Σ_k ρ_k S^(k)_p,t−4) + ε_pt`, for `t` in 2022-Q1 … 2026-Q1,
with `γ_t` free for every quarter (all national events), `k ∈ {−2, −1, 0, 1, 2+}`. Weighted nonlinear
least squares (weights `B_p`); 95% intervals from a province-cluster pairs bootstrap (2,000
resamples). Anticipation test: `ρ_−2 = ρ_−1 = 0` (bootstrap Wald). The model assumes the effect at a
given event time is the same in every phase; with `γ_t` free, Q1-2026 alone identifies only differences
between `ρ_k`, and levels come from the staggering (Q3 and Q4 2025). The phase-specific
`ρ_0` of phase 1 (from Q3-2025) and of phase 3 (from H1a) are reported side by side as a check of that
assumption. The years 2020–2021 are outside the window (pandemic disruptions).

### 6.3 Placebos and controls

- **Time placebos.** H1a's model on `Δg_p(2025-Q1)` and `Δg_p(2024-Q1)`; H1b's on `Δg_p(2024-Q3)` and
  `Δg_p(2023-Q3)`. Expected: slopes near 0. If any placebo slope has two-sided p ≤ 0.05 and at least half
  the size of the real one, the real result is marked **confounded** and its hypothesis not supported.
- **Leads** in the pooled model (§6.2).
- **Negative-control outcomes** NC-EH and NC-DES with H1a's and H1b's models. A significant slope of the
  same sign and at least half the size does not by itself reject H1, but the finding is then described
  as a wider disruption of court statistics at the transformation, not one specific to evictions.
- **Positive control** PC-MON: the MASC shock should appear in the national quarter effects, not in
  the phase slopes; reported descriptively.

### 6.4 Decomposition and the "record low" verdict

National change `ln(Y_2026-Q1 / Y_2025-Q1)` for P-TOT is split into:
- **(a) reported missing data.** For each district listed by the CGPJ as without data at the close of
  Q1-2026 (Donostia/San Sebastián, Gijón, Vinarós), the province value is scaled to
  `observed / (1 − w_d)`, i.e. the missing district is assumed to have moved like the rest of its
  province, and the released total is assumed to contain nothing for it (checked against the
  revisions in the Q2 release, §7). Madrid's estimated figures are kept (sensitivity S3 drops Madrid).
- **(b) phase-related counting.** The counterfactual province value `Y*_p = Y_p / (1 + Σ_k ρ̂_k S^(k)_p,2026-Q1)`
  from §6.2 (leads set to 0 if the anticipation test passes; otherwise the model with leads), summed
  over provinces, with bootstrap 95% interval.
- **(c) national residual**: the rest. It contains real changes and any change in counting that hit
  every district at the same time, which this design cannot see.

**Record-low verdict.** The comparison is with the minimum of national P-TOT over all quarters
2013-Q1 … 2025-Q4 and, separately, over first quarters only. "Record low **not supported**" if the lower
bound of the 95% interval of the adjusted Q1-2026 total (a + b removed) is above the previous minimum;
"record low **robust**" if its upper bound is below; otherwise "**undetermined**". The literal check of
the unadjusted 4,005 against every earlier quarter is reported too (DQ11).

### 6.5 Multiplicity and sensitivity

- Holm correction within the primary family {H1a, H1b} and within the secondary family {H2, H3, H4, H5}.
  Placebos, controls and H6 are not corrected. Everything else is exploratory and labelled so.
- Sensitivity analyses, all reported whatever their result: S1 unweighted; S2 without Barcelona and
  Madrid; S3 without provinces containing a district flagged by the CGPJ in the quarters involved;
  S4 imputation of flagged districts as in §6.4(a) for every quarter; S5 weights from 2024 only;
  S6 small provinces included, `ln(Y + 0.5)`; S7 Poisson pseudo-likelihood in levels with
  province × quarter-of-year effects; S8 TSJ-level replication; S9 rent (P-LAU) as outcome; S10 court
  offices with a different start date (DT 5.ª) coded at their actual date; S11 H5 without the 64 + 4
  districts flagged in Q3/Q4-2025.

## 7. Out-of-sample use of Q2-2026

**Freeze before release.** Before anyone on the study opens a Q2-2026 file, the coordinator commits:
the analysis code; the in-sample results for H1a–H5; and `data/predictions_q2_2026.csv`, which gives
for every province the predicted `Δg_p(2026-Q2)` relative to the national mean under two readings
fitted on the locked data: **transient** (`ρ_k = 0` for `k ≥ 1`) and **persistent** (`ρ_k = ρ̂_0` for
all `k ≥ 0`). The commit hash and time are recorded in §14. If the freeze is committed after the
release appears, the Q2-2026 analysis is labelled **not out-of-sample** and is exploratory.

**Test.** Between 2026-Q1 and 2026-Q2, phase 3 moves from event time 0 to 1, phase 2 from 1 to 2 and
phase 1 from 2 to 3; the base quarters (2025-Q1, 2025-Q2) are before every transformation.
In `Δg_p(2026-Q2) = a + b3'·W3_p + b2'·W2_p + u_p` (same weights and inference as §6.1):
- **transient** if `b3' > 0` with one-sided p ≤ 0.05 (phase-3 provinces recover);
- **persistent** if the upper bound of the 95% interval of `b3'` is below `−b̂3/2`, where `b̂3` is
  H1a's estimate (recovery of half the Q1 effect is ruled out);
- otherwise **undetermined**.

This test is read only if H1a is supported. If H1a is not supported, `b3'` is expected near 0 and is
reported as a replication of that null. The two prediction sets are also scored by root mean squared
error against the observed province deviations (descriptive).

**Other uses of the Q2 release.** (i) Revisions: Q1-2026 values in the Q2 release are compared with
the locked vintage; a revision of national Q1-2026 P-TOT by 5% or more, or of any province by 10% and
10 evictions, is reported; the expectation is an upward revision in Gipuzkoa, Asturias and Castellón if
the missing districts' data arrive. H1a is re-run on the revised vintage as a robustness check, never
replacing the locked result. (ii) Any note in the Q2 release about LO 1/2025, the *tribunales de
instancia* or a change in counting is quoted in §14 and in the paper. (iii) The Q2 files are hashed
on download, as in §3.3.

## 8. What would falsify each hypothesis

| hypothesis | supported | falsified | otherwise |
|---|---|---|---|
| H1a | b3 < 0, both p ≤ 0.05 (Holm), time placebos clean | b3 ≥ 0, or the one-sided 95% lower confidence bound of b3 is above ln(0.90) (a phase-3 drop of 10% or more is ruled out) | inconclusive |
| H1b | b1 < 0, same rules | b1 ≥ 0, or its bound above ln(0.90) | inconclusive |
| H2 | b3(SC-POS) > 0, one-sided p ≤ 0.05 | b3(SC-POS) < 0 with one-sided p ≤ 0.05 (work did not move; the fall is upstream) | inconclusive |
| H3 | b3(ratio) < 0, one-sided p ≤ 0.05 | b3(ratio) ≥ 0 | inconclusive |
| H4 | b3(HIP) < 0, p ≤ 0.05, and the LAU − HIP interval includes 0 | b3(HIP) ≥ 0 while b3(LAU) − b3(HIP) < 0 with p ≤ 0.05 (the concentration is rent-specific, pointing to a real policy channel) | inconclusive |
| H5 | δ1 < 0, one-sided p ≤ 0.05 (province-clustered), and the 2025 δ1 more negative than every placebo-year δ1 for 2015/2014 … 2024/2023 | δ1 ≥ 0, or its one-sided 95% lower confidence bound above ln(0.95) (an annual drop of 5% or more, about 10% in each of the two transformed quarters, is ruled out) | inconclusive (including a significant δ1 inside the range of placebo years) |
| H6 | see §7 | — | undetermined |

**Overall reading.** "The Q1-2026 low is to a large extent an artefact of counting" if H1a is
supported, H2 or H3 is supported, the placebos are clean, and components (a) + (b) are at least half of
the national log fall. "Not explained by the phased reform" if H1a and H1b are both falsified. Anything
else is reported as partial, with the decomposition and the record-low verdict of §6.4. An artefact of
counting is described as such: it says nothing about anyone's conduct.

## 9. Data-quality checks

| id | check | rule and consequence |
|---|---|---|
| DQ1 | D1 (district) vs province series, by province × year × type, 2013–2025 | every difference listed. District-year outlier: `Y_d,y ≥ 10 × max(1, max earlier Y_d)` and an increase of at least 100 (or a fall to 0 from at least 50) → flagged, excluded from H5 and from `w_d`. The Ribadavia (Ourense) 2025 value is checked under this rule, not assumed |
| DQ2 | same quarter across releases (Q1-2025 … Q1-2026 files vs the series file) | revisions of 5% or more and 10 evictions listed by province and quarter |
| DQ3 | CGPJ missing/estimate flags (§2.3) | drive S3 and S4; Q3-2025 values are taken from the latest vintage, and how far they moved from the first (estimated) vintage is reported |
| DQ4 | identities: total = mortgage + LAU + other; Σ provinces = TSJ; Σ TSJ = Spain; Spain = press figures (4,005; 16,167; 7,696; −45.4%; +19.2%; +16.6%) | failures listed; if more than 10% of province-quarters fail, confirmatory tests are not run (§10) |
| DQ5 | column labels | columns parsed by position and validated against totals (e.g. the «25-T1» header on the Q1-2026 column) |
| DQ6 | phase matching | all 431 D1 districts matched to exactly one phase; counts must be 315 / 16 / 100; the 30 MJU phase-3 districts must fall in the remainder; for phases 1 and 2, the former courts in the xls must be only those named in DT 1.ª (mixed first-instance-and-investigation, or separate first-instance, investigation and violence-against-women courts) |
| DQ7 | phase-2 list | xls sheet = Madrid Bar list (§2.2) |
| DQ8 | seasonality | Q3/Q2 and Q1/Q4 ratios of 2025-26 compared with 2022–2024 |
| DQ9 | small counts | the exclusion rule of §6.1, with the list of excluded provinces per test |
| DQ10 | common-service coverage | provinces with zero receipts in any quarter 2024–2026-Q1 listed and excluded from SC tests |
| DQ11 | "record low" literal check | 4,005 against every quarter 2013-Q1 … 2025-Q4 and against first quarters only |

## 10. Stopping rule

- **Fixed data.** The confirmatory in-sample analysis uses only the files of §3.3; the out-of-sample
  analysis adds only the Q2-2026 release. Later quarters (Q3-2026, due 2026-12-14) are not added to
  any confirmatory test.
- **End.** The study ends when the Q2-2026 analysis of §7 is done. If Q2-2026 has not been published by
  2027-01-31, the study is reported with the out-of-sample test marked "not run".
- **No re-specification.** After the freeze (§7) no model, threshold, weight or exclusion is changed;
  any new analysis is labelled exploratory.
- **Early stop for data quality.** If DQ6 leaves more than 5% of districts (22) unmatched, or DQ4 fails
  in more than 10% of province-quarters, the confirmatory tests are not run and the study is reported as
  a data-quality note.
- **If the CGPJ explains a counting change** before the freeze, the note is quoted in §14, the tests
  are still run as registered (they measure the size of the change), and the paper presents the CGPJ's
  explanation as prior work. If the CGPJ revises the Q1-2026 series before the freeze, the locked vintage
  stays primary and the revision is a sensitivity analysis.

## 11. Timeline

- 2026-10-04: protocol registered (this commit).
- Before 2026-10-16: in-sample analysis and frozen predictions committed (§7).
- 2026-10-16: CGPJ Q2-2026 release (scheduled). Out-of-sample analysis within 7 days of the release.

## 12. Threats to validity

- **Phases are not random.** Phase 3 is, by law, the districts with more kinds of courts: provincial
  capitals and large cities, with different rental markets, tenants and court backlogs. Mitigations:
  H5 compares districts inside the same province; time placebos test whether phase-3 provinces always
  behave differently in first quarters; H4 and the signature table (§5) separate a counting change from
  rent-specific real channels. One plausible real channel, the end of the suspensions on 31-Dec-2025,
  would *raise* evictions in large cities in Q1-2026, which works against H1a.
- **MASC lag.** Fewer rent claims since April 2025 reach the eviction stage months later, possibly
  later in slower large-city courts. Its signature (rent only; common-service receipts fall, not rise)
  is in §5.
- **Timing within phases.** DT 5.ª allows court offices and staff lists to start later than the
  *tribunal*; the primary analysis uses the legal date (S10 uses actual dates where found).
- **Weights.** District weights come from practised evictions; there are no district data for common
  services, so the SC tests use the same weights.
- **Estimated and missing data**, disclosed by the CGPJ (§2.3), and possible undisclosed ones.
- **Homogeneity.** The pooled model assumes the same effect at a given event time in every phase.
- **Few units.** About 50 provinces; phase 2 has only 16 districts and is not tested on its own.
- **Revisions.** The CGPJ revises earlier quarters; the vintage is locked and revisions are reported.
- **Not blind in-sample** (preamble); hence the weight given to §7.
- **Invisible uniform changes.** A change in counting that hit every district on the same day would sit
  in the national residual (c) and cannot be told apart from a real change by this design.

## 13. Ethics

- **Aggregates only.** Court statistics by province, TSJ and district. No personal data, no case
  files, no names of judges, court staff or parties. The suspension annex is used, if at all, only as
  regional aggregates.
- **Neutral wording.** An artefact of counting is not wrongdoing by anyone. The CGPJ itself disclosed
  missing and estimated data; the reform's timing is set by law. Results speak of statistics and
  counting, not of the conduct of courts, officials or the CGPJ.
- **People behind the numbers.** Each eviction is a household losing its home. The study measures how
  evictions are counted; it does not claim that evictions did not happen, and it makes no claim about
  the welfare effects of tenant protection.
- **Access.** Public files only, User-Agent `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`,
  at most one request per second per host, and 5 s between requests to poderjudicial.es as its
  `robots.txt` asks (`Crawl-delay: 5`). Paths disallowed in `robots.txt` (for example the CGPJ's press
  files under `/stfls/…/NOTAS*DE*PRENSA/`) are not fetched. No access control is bypassed.
- **Reuse.** Only derived aggregates are published, with attribution to the CGPJ and the Ministry; the
  raw files are not re-hosted. On 2026-10-04 the CGPJ legal-notice page
  (https://www.poderjudicial.es/cgpj/es/Poder-Judicial/Aviso-Legal/) served «No hay información
  disponible» to a plain HTTP client; METHOD.md will state the reuse terms found before publication.
- **Right of reply.** Whether to send the findings to the CGPJ's Statistics Service before publication,
  and with how much time to reply, is the study coordinator's decision.

## 14. Deviations and dated events

| date (UTC) | event |
|---|---|
| 2026-10-04 | Protocol drafted. Verified with `curl`: LO 1/2025 consolidated text and its later references (DT 1.ª unamended); Ministry totals 315 / 16 / 100; the Ministry's court-by-court phase xls (315 / 16 / 30 MJU); the CGPJ methodology page and the notes inside the five releases Q1-2025 … Q1-2026 (no counting-change note; missing/estimated data disclosed in Q3-2025, Q4-2025 and Q1-2026). Files of §3.3 downloaded and hashed. At 11:56 UTC, and again at 12:38 UTC, the CGPJ page listed Q1-2026 as the latest release; Q2-2026 scheduled for 2026-10-16. No Q2-2026 data accessed. |
| 2026-10-04 | **Registration**: protocol committed as `ee3ef6c`, 2026-10-04T14:38:42+02:00 (12:38:42 UTC). |
| 2026-10-04 | **Implementation choices, fixed in code before any H1–H5 estimate was computed** (the data-quality checks of §9 had been run; their results are listed in the next row). (1) District-to-province table (§3.2): the CGPJ's «Población por Partido Judicial - Año 2025» (`…/FICHEROS/Poblacion/`, Last-Modified 2026-01-14, SHA-256 `665bb817a8c197ab60e20589361555c376180470ccbb8499b371b74aa2101b94`); four spelling aliases (Cangas del Narcea, Mahón, Palma de Mallorca, Villarrobledo) and Vila-real = Villarreal. (2) Ceuta and Melilla are counted inside Cádiz and Málaga in the province series (DQ1: absolute difference 2013–2024 of 3 and 0 with them, 490 and 1,086 without), so their districts take those provinces' weights. (3) A DQ1-flagged district-year is left out of `w_d` by giving the district the mean of its unflagged weight years; H5 drops districts with a flagged year among the three years it uses. (4) "At least half the size" (§6.3) is read in absolute value, whatever the sign. (5) S4 is run twice: S4a imputes only the districts the CGPJ lists as without data (Q1-2026); S4b also treats the four Q4-2025 «información parcial» districts as missing (an upper bound). The 64 Q3-2025 districts are not imputed, because the CGPJ says it already estimated them. (6) S10: no court office with a start date different from DT 1.ª was found in the sources consulted; DQ6 found that San Javier (Murcia, phase 1) had pilot *tribunal de instancia* sections before the reform, so S10 drops Murcia. (7) The pooled model drops province-quarters with a zero count (log undefined); the anticipation test uses α = 0.05; S7 is unweighted Poisson on 2021-Q1…2026-Q1. (8) The permutation p-value of §6.1 is applied to H2–H4 as well as H1. (9) Predictions (§7) are deviations from the B_2024-weighted mean; scoring is the B_2024-weighted RMSE over provinces passing the count rule. |
| 2026-10-04 | **Data-quality results seen before the in-sample tests** (full tables in `data/dq_*.csv`): DQ1 — the 2025 column of the district file disagrees with the province series in all 50 provinces; the national excess is 2,943, the size of Ribadavia's anomaly (2,944 in 2025, 11 at most before), and outside Ourense the provincial differences net to +4; the annual 2025 release agrees with the province series in all 50. 2013–2024 agree except small differences up to 2022. DQ2 — Q3-2025 national practised evictions revised from 5,053 (first vintage, «estimated») to 4,839; Q1-2026 LAU/«otros» split differs between the release's province sheet (2,249 / 785) and the series (2,600 / 434), the difference being Madrid (103 / 372 vs 454 / 21, the latter marked «*Dato estimado»). DQ3 — 63 of the 64 Q3-2025 estimated districts are phase 1 (the other is Cuenca, phase 3); the 4 Q4-2025 districts are phase 1; the 3 Q1-2026 districts are phase 3. DQ6 — 315/16/100 matched; San Javier pilot. DQ11 — 2020-Q2 (1,383) is below 4,005; the lowest earlier first quarter is 2023-Q1 (6,579). Gate of §10 passed. |
| 2026-10-04 | **In-sample results on the locked data** (computed ~12:50 UTC; `data/tests.csv`, `data/summary.json`). H1a: b3 = −1.229 (HC3 SE 0.899, n = 41, one-sided p 0.090, Holm 0.180, permutation 0.047) → inconclusive. H1b: b1 = −0.133 (SE 0.321, n = 44, p 0.341) → inconclusive. H2: b3 = +1.326 (SE 0.946, n = 32, p 0.086, Holm 0.172, permutation 0.051) → inconclusive. H3: b3 = −2.275 (SE 0.898, n = 31, p 0.009, Holm 0.026, permutation 0.006) → supported. H4: b3(HIP) = +0.144 (SE 1.579, n = 18) and LAU − HIP = −2.109 (one-sided p 0.011, n = 17) → falsified by the registered rule (the HIP test has little power). H5: δ1 = −0.400 (province-clustered SE 0.051, 422 districts, p < 0.001), more negative than every placebo year (the 2024/2023 placebo is −0.189, p < 0.001) → supported, with the DQ1 caveat on the 2025 district column. Time placebos clean; no negative control flags a wider disruption. Pooled model (§6.2): the k ≥ 2 parameter sits at the search bound (+3.0), so the fit is degenerate; anticipation test p = 0.30. Registered decomposition: a = −0.007, b = +0.521 (bootstrap 95% −0.26 to 0.66), c = −1.118; record low over all quarters "not supported" (2020-Q2, 1,383), over first quarters "robust" (counterfactual 95% 2,079–5,235 < 6,579), both resting on the degenerate fit. Overall reading (§8): partial. Frozen predictions: `data/predictions_q2_2026.csv` (SHA-256 `2c8d663d64f1e186911ce943d4ee7cc129090269657fe8b4f5de5618eaa9f646`) and `data/predictions_q2_2026_spec.json` (`722a2731ea23acdaee51760339c8f6c13c09025b4ac0ebf49ed0a176962b32fb`); the descriptive "as fitted" column first drafted was dropped before the freeze because it rests on the degenerate parameter. At 12:55 UTC the CGPJ page still listed Q1-2026 as the latest release; no Q2-2026 file has been accessed. |
| 2026-10-04 | **§7 freeze committed**: `321bce1`, 2026-10-04T14:56:50+02:00 (12:56:50 UTC), before the Q2-2026 release scheduled for 2026-10-16. |
| 2026-10-04 | **Write-up after the freeze** (13:00–13:10 UTC): prior-work searches run (Crossref, arXiv API, GitHub; `data/prior_work_search.csv`, `scripts/prior_work_search.py`); README, METHOD, paper, and a full `scripts/check_headlines.py` written. `build.py`, `dq.py`, `analyse.py` and `s12lib.py` were not changed after the freeze, and a full rerun of `scripts/run.sh` reproduces every frozen file in `data/` byte for byte. At 13:09 UTC the CGPJ page still listed Q1-2026 as the latest release; no Q2-2026 file has been accessed. The out-of-sample test of §7 will be run and reported after the release of 2026-10-16. |
| 2026-10-04 | **Independent review received** (`private/REVIEW.md`, started 13:12 UTC). Its BLOCKER and MAJOR items are applied in the rows below, in new files and in the text; no frozen file (`build.py`, `dq.py`, `analyse.py`, `s12lib.py`, their outputs in `data/`, or anything above this table) is changed. |
| 2026-10-04 | **Correction to §2.3 (the counting change is documented).** §2.3 concludes that the CGPJ «does not explain any change in how practised evictions are counted after the reform». Its methodology page and release notes indeed say nothing, but its data-collection forms document one. The court form («BOLETIN 04. JUZGADO DE PRIMERA INSTANCIA E INSTRUCCIÓN», version 2024, `…/DOCUMENTOSCGPJ/04_Jdo Primera Instancia e Instruccion 2024.pdf`, Last-Modified 2024-06-12, SHA-256 `a99a77abeca276eb363196287410782c97a85f9fa5d1f165cd8060a4c8f390a7`) has «1.13. LANZAMIENTOS PRACTICADOS EN EL TRIMESTRE (*)», «(*) Se contabilizará un lanzamiento por cada bien inmueble cuyo lanzamiento o entrega posesoria se practique, bien directamente por el juzgado o bien por un servicio común». The 2026 form of the new section («BOLETIN 04 SECCIÓN CIVIL Y DE INSTRUCCIÓN. TRIBUNAL DE INSTANCIA», Last-Modified 2026-04-17, SHA-256 `7de3e53fc6ffb614a43bae7938b033f7eefce2cf0158905cd317e880b6bcf1fa`) has no practised-evictions item. The 2026 common-services form («BOLETIN 56. SERVICIOS COMUNES. TRIBUNAL DE INSTANCIA», «Versión 1er TRIMESTRE 2026», Last-Modified 2026-04-17, SHA-256 `beb85dff2aecbb05aec09ce068910ca0fa1288adad87519a936e3640d48be9fb`), under «II. SERVICIO COMUN DE EJECUCION», has «1.4.1. LANZAMIENTOS ACORDADOS POR EL SERVICIO COMÚN DE EJECUCIÓN (decreto)», «1.4.2. LANZAMIENTOS PRACTICADOS EN EL TRIMESTRE (*)» with «En el caso de que este Servicio Común o disponga de la totalidad de la información deberá recabarla del resto de Servicios comunes del Tribunal de Instancia», and a new «1.4.3 Entregas posesorias mediatas producidas en el trimestre». From each district's transformation on, the series is therefore reported by a different respondent on a different form. The study's tests are unchanged; what they measure is now the effect of this documented change in who reports. (The reviewer read the same item 1.13 in the 2025 court form and the «Versión 4º TRIMESTRE 2025» of form 56; those 2025 files are no longer linked from the CGPJ page, so they were not re-fetched.) |
| 2026-10-04 | **Correction to §2.4, §5 and §12 (suspension of evictions).** The protocol says the suspension ended on 31-Dec-2025 and that «the suspension windows affect rent evictions only». Both are wrong. The BOE version history of RDL 11/2020 art. 1 (https://www.boe.es/buscar/act.php?id=BOE-A-2020-4208) reads «Modificación publicada el 24/12/2025, en vigor a partir del 25/12/2025», and the version of that date (https://www.boe.es/eli/es/rdl/2020/03/31/11/con/20251224) reads «hasta el 31 de diciembre de 2026». RDL 16/2025 thus extended the suspension before it expired. It lapsed when the repeal took effect («Modificación publicada el 28/01/2026, en vigor a partir del 28/01/2026»). RDL 2/2026 restored it («Modificación publicada el 04/02/2026, en vigor a partir del 05/02/2026»), and it lapsed finally on 28-Feb-2026 (repeal published that day, BOE-A-2026-4667). In Q1-2026 it was in force on 1–27 January and 5–27 February. Article 1 bis («Suspensión hasta el 31 de diciembre de 2026 del procedimiento de desahucio y de los lanzamientos para personas económicamente vulnerables sin alternativa habitacional en los supuestos de los apartados 2.º, 4.º y 7.º del artículo 250.1 de la Ley 1/2000 … y en aquellos otros en los que el desahucio traiga causa de un procedimiento penal») covers non-rent evictions too, which fall in the «otros» category. The mortgage-versus-rent contrast of H4 is unaffected: neither article covers mortgage enforcement. |
| 2026-10-04 | **Deviation found by the review: S3 omitted Madrid.** §6.4(a) says «sensitivity S3 drops Madrid»; the frozen code dropped only the provinces in `cgpj_notes.csv`. The frozen `data/sensitivity.csv` is left as it is. S3 as registered (also dropping Madrid) is run in the new `scripts/post_review.py`: b3 = −1.18 (HC3 SE 0.85, 34 provinces, one-sided p 0.088, permutation 0.051), not supported. Output: `data/review_checks.json`. |
| 2026-10-04 | **Post-review exploratory analyses** (not registered; `scripts/post_review.py`, `data/review_checks.json`, `data/review_slopes.csv`). (1) The slopes behind H1a, H2, H3 split into their Q1-2026 and Q4-2025 parts; H2 and H3 come from Q4-2025. (2) The same regression one quarter earlier, Δg(2025-Q4), as an in-window placebo: P-TOT −0.755 (SE 0.322, n 42, two-sided p 0.024, permutation 0.004). Had it been registered, §6.3 would mark H1a «confounded». (3) H1a without Las Palmas. (4) H5 restricted to provinces where the 2025 district file is within 5% of the province series. (5) The registered but unreported S7 values, the PC-MON phase-1 slope and DQ8, collected for the text. Registered verdicts are unchanged; the paper scopes their reading. |
| 2026-10-04 | **On the order of events between registration and freeze.** No commit separates the implementation choices from the first estimates. Their order (data-quality checks, then the §14 row of choices, then `analyse.py`) rests on the session's command log, not on git. |
| 2026-10-05 | **Descriptive block appended to `data/summary.json`, a frozen output of `analyse.py`.** The new `scripts/summarize.py`, which `scripts/run.sh` now runs after `analyse.py`, appends one key, `descriptive`: the series levels and other descriptive figures the text quotes. Why: so that the claims register (`claims.csv`) can check those figures against data instead of against typed numbers. The earlier content is byte-identical: the 16 keys `analyse.py` wrote are unchanged, the first 7,252 of the 7,255 bytes of the file frozen in `321bce1` are unchanged, and only its closing `}` now follows the new block. `build.py`, `dq.py`, `analyse.py` and `s12lib.py` are unchanged; no registered result changes. Appended in commits `971641f` and `c9dd69d`; this row was added the same day, after a closing review found the deviation missing from this table. |
