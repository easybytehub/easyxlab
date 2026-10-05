# S24 — Method

*EasyxLab · study S24 · working draft*

## 1. Design

- **Descriptive and decomposition-based.** No outcome was registered in advance. Every figure in the
  scout report that proposed the study was recomputed from the sources, not reused.
- **Three questions.**
  1. What do young tenants pay relative to their income? ECV microdata 2008–2025.
  2. Is the falling overburden a selection effect? Five tests: a shift-share split, an age
     comparison, a one-channel bound, the panel of continuing tenants and the panel of leavers.
  3. How do the CJE's 98.7% and 33.6% relate to the measured burden? A step-by-step comparison under
     two income benchmarks, and a check of the CJE's own ECV-based figures.
- **The cross-section is the main tool.** The ECV's cross-sectional files cannot follow anyone. Its
  longitudinal files follow households for up to four years and are used for the two panel tests,
  with the limits stated in §5 and §8.
- **Revision.** An independent adversarial review (5 October 2026) led to the changes listed in
  [the paper](https://easybyte.es/lab/studies/s24/paper/) §9. The main one: temporarily absent household members are now kept (§3).

## 2. Sources

All requests used the User-Agent `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`,
one at a time, at least 1.2 s apart per host, `robots.txt` read first. `curl` ran with
`--max-time 120` and resumed across attempts. The 54 inputs are listed with URL and SHA-256 in
`scripts/locked_inputs.json`.
- `scripts/fetch.py` never lets a different file take a locked file's place: a new vintage is kept
  as `<name>.new` and the script fails.
- `run.sh` runs `fetch.py --verify` before any analysis.

| source | what | used for |
|---|---|---|
| INE, ECV, cross-sectional microdata, base 2013, 2008–2025 (`/ftp/microdatos/ecv/ecv_b2013/datos_<year>.zip`) | files D, R, H, P per year | burden, living arrangements, selection, CJE comparison |
| INE, ECV, cross-sectional microdata, base 2004, 2004–2007 | same | living arrangements only (income not comparable with base 2013) |
| INE, ECV, longitudinal microdata 2013–2016, 2016–2019, 2019–2022, 2022–2025 | four-year panels | leaving home by prior income; continuing tenants |
| INE, EPA microdata, 3rd and 4th quarters 2023–2025, and INE's base-2021 weights annex for 2023 | quarterly LFS files | the emancipation splice check |
| Eurostat API: `ilc_lvho07c`, `ilc_lvho07a`, `ilc_lvps08`, `yth_demo_030` (Spain, EU-27) | overburden by tenure and age; young adults living with parents; age at leaving home | replication and context |
| INE, IPVA (Tempus API tables 59004, 59008, 59063) | rent index by contract age; weights by contract age and dwelling size | asking vs paid rents |
| INE press releases ECV 2017, 2019, 2021–2025 and the 2025 module on access to housing | fieldwork period and collection mode, quoted | data-quality notes |
| CJE, Observatorio de Emancipación: 2025 balance; 2nd semester 2024 (state report, methodological note); 2nd semester 2023 (state report) | the 98.7% and 33.6%, their method, the chart note, EPA-era rates | question 3 |
| FEDEA, eee2026-28 (Conde-Ruiz and Pinto) | quoted in prior work | prior work |
| BOE, consolidated texts: Ley 29/1994 (LAU), RDL 6/2022 art. 46; RDL 26/2026, RDL 27/2026 and the Congress resolutions of 2 October 2026 | rent-update limits; law in force | context |

**Vintage.** INE microdata as downloaded on 4 October 2026.
- The ECV 2025 archive was last modified on 10 June 2026, and the 2022–2025 longitudinal archive on
  28 May 2026.
- INE updated `HS200` in the 2022 household file in March 2026. We do not use that variable.

**Terms of use.**
- INE's microdata page (https://www.ine.es/dyngs/SER/index.htm?cid=1388, the redirect target of
  `/prodyser/microdatos.htm`) says: «El Instituto Nacional de Estadística (INE) no se responsabiliza
  de los resultados que los usuarios obtengan a partir de estos ficheros basados en sus propios
  cálculos. Además, toda persona que utilice ficheros de microdatos se compromete a citar, en
  cualquier publicación obtenida a partir de ellos, al INE como fuente del dato primario (fuente:
  INE, www.ine.es), así como a que el grado de exactitud o fiabilidad de la información derivada por
  elaboración propia de los autores es de la exclusiva responsabilidad de estos.» The ECV and EPA
  results pages carry the same clause.
- INE's legal notice authorises reuse of INE-sourced information on these conditions: «Se prohíbe
  expresamente desnaturalizar el sentido de la información»; the source must be cited; and «Debe
  mencionarse la fecha de la última actualización de la información objeto de reutilización».
- Neither text says that microdata files may be redistributed. We therefore do not re-host them:
  `scripts/fetch.py` downloads them. The unit-level files we derive stay in `data/raw/derived/`,
  which is git-ignored.
- `data/` holds aggregates only. A test checks that no CSV there carries a person or household
  identifier, and that cells of fewer than 10 households publish no median or rate.
- Eurostat's copyright notice: «Reuse of statistical data, metadata, publications, and other
  dissemination tools published on this website for commercial or non-commercial purposes is
  authorised provided the source is acknowledged». CJE material is quoted briefly for comment.

**Hosts not used.**

| host | reason |
|---|---|
| `www.mivau.gob.es` (SERPAVI), `assets.eurofound.europa.eu` | 403 on `robots.txt` |
| `www.eurofound.europa.eu` | 429 (rate limit) on `robots.txt`; the 2025 youth report was read as an abstract from the TU Delft research portal |
| `provivienda.org` | not tried: the scout report found it refuses our User-Agent |

**El Mundo** reserves text and data mining (art. 67.3 RDL 24/2021). We read one article for the
prior-work review, quote nothing from it and deleted the local copy.

**Searches.** A general web-search tool was unavailable (session quota used up). Prior work was
searched on DuckDuckGo's HTML endpoint (`robots.txt` allows it), Crossref and OpenAlex. All searches
are in `data/prior_work_search.csv`, and the documents read in `data/prior_work.csv`.

## 3. Population and variables, year by year

**Population.** All members of private households: `RB200` = 1 («Vive actualmente en el hogar») or
2 («Ausente temporalmente»), as in Eurostat's household population. The first draft kept only
`RB200` = 1. That dropped 1,205 people in 2025, 731 of them aged 18–34, and was the whole of the
residual against Eurostat.

| concept | variable | years | note |
|---|---|---|---|
| tenure | `HH021` (1 owner outright, 2 owner with mortgage, 3 market rent «En alquiler o realquiler a precio de mercado», 4 below-market rent, 5 free) | 2011–2025 | 2004–2010 files carry `HH020` (owner, market rent, reduced rent, free). The owner split is missing, so owner rows start in 2011 |
| current rent, monthly | `HH060` | all | missing for ≈ 2% of market-rent households: they are excluded from every rent statistic and from their burden |
| total housing cost, monthly | `HH070` | all | «Alquiler …, intereses de la hipoteca … y otros gastos asociados (comunidad, agua, electricidad, gas, etc.)» |
| disposable income, annual | `HY020` | all | calendar year before the survey. It excludes imputed rent (which the files carry as `HY030N`), as Eurostat's indicator does |
| housing allowances, annual | `HY070G` | 2006–2025 | netted out of costs and income |
| consumption units | `HX240` (modified OECD scale) | all | for national quintiles of equivalised income |
| household size | `HX040` | all | "living alone" = `HX040` = 1 |
| age | `RB082` (age at interview), `RB081` (age on 31 December of the income year) | 2021–2025 | before 2021: interview age from birth year `RB080`, birth month `RB070` and interview month `HB050`; end-of-year age = year − 1 − `RB080` |
| living with a parent | `RB220` or `RB230` present (father or mother in the household) | all | "emancipated" = neither |
| partner in household | `RB240` | all | for the household types |
| first responsible person | `HB080` | all | for the "young reference person" household definition |
| personal net income | sum of `PY010N`, `PY020N`, `PY050N`, `PY080N`, `PY090N`–`PY140N` | 2008–2025 | the CJE's «ingresos ordinarios»; previous calendar year |
| weights | `RB050` (persons), `DB090` (households); longitudinal `RB060`, `DB095` | | |
| 2025 module | `PMG8` (main reason for living with a parent, 17–34), `PMG4` (same dwelling 12 months ago) | 2025 | |

## 4. Burden and the replication of Eurostat

- **Burden.** Housing cost burden = (12 × `HH070` − `HY070G`) / (`HY020` − `HY070G`). A person is
  overburdened when it exceeds 40%. A household whose net income is zero or negative counts as
  overburdened. That rule reproduces Eurostat; counting such households as not overburdened lowers
  the 2025 market-rent rate by about 0.4 points.
- **Rent ratio.** Rent-to-income = 12 × `HH060` / `HY020`.
- **Statistics.** All rates are person-weighted (`RB050`) unless the unit is a household (`DB090`).
  Medians are weighted, with the mean of the two middle values at an exact half.
- **Replication** (`data/eurostat_replication.csv`).
  - By tenure (`ilc_lvho07c`; 84 cells for 2008–2025, including the all-tenure total): exact in 76,
    and never more than 0.3 points off.
  - By age (`ilc_lvho07a`; 15–29, 18–24, 25–29), using age at the end of the income year: 52 of 54
    cells exact, largest gap 0.1. With age at interview, gaps reach 1.5 points.
  - Living with parents, ages 18–34 (`ilc_lvps08`), with age at interview: within 0.7 points in
    2008–2025, and exact in six of those 18 years, including 2019, 2021, 2023 and 2025. The base-2004
    files (2004–2007) differ by up to 7 points and are not compared.
  - Our main age variable is age at interview, the moment at which living arrangements and rents are
    measured.
- **Units for the young** (`data/young_burden.csv`; age bands 16–29, 18–29, 18–34):
  - emancipated persons (`RB050`);
  - households with at least one emancipated person in the band. This is the CJE's «hogar joven»;
  - households whose first responsible person is in the band.
- **Tenure groups**: market rent; reduced or free; owner with mortgage; owner outright.
- **Breakdowns of young market tenants** (`data/young_tenants_breakdown.csv`):
  - national quintile of equivalised disposable income over all persons;
  - household type. "Alone" is a household of one. "Couple" is two people, partners. "Shared or
    other" means no partner, no parent and no own child in the household: flatmates, siblings or
    other relatives, which the ECV does not distinguish.
- **Small cells.** For any group of fewer than 10 households we publish counts only, never medians or
  rates (column `suppressed`).

## 5. Selection

1. **Cells** (`data/selection_cells.csv`). Each year, all people in the age band are grouped by
   personal net income: none (G0), then quartiles of positive income within the year (G1–G4). The
   groups are relative to the young population of that year. For each group we report:
   - the share emancipated;
   - the share renting at market price;
   - the group's share of young tenants and their overburden.
2. **Shift-share split** (`data/decomposition.csv`). The overburden of young market tenants is
   O = Σ s_c o_c, summed over cells c. The change splits exactly into composition, Σ Δs·ō, and
   within-cell change, Σ s̄·Δo, using averages of the two years (Shapley).
   - Cells are income groups, then income groups × age subgroup (18–24, 25–29, 30–34).
   - The composition term is selection on observed relative income. It is a floor on selection, not
     an estimate of it. Selection on what personal income does not capture (a partner's or family's
     resources) appears in the within-cell term.
   - The largest within-cell falls are in the groups whose emancipation fell most. That is the
     pattern such selection would produce.
   - The same split is applied to all market tenants, over age groups and over national income
     quintiles.
3. **One-channel bound** (`data/selection_bound.csv`). It caps one channel only: fewer young people
   leaving home, which changes who is a tenant.
   - **Extra stayers.** E = (p₁ − p₀) × N₁, where p is the share of the age band living with a parent
     and N₁ the band's population in the final year. This is a net figure: migration and cohort
     change make it differ from the gross number of stayers.
   - **The bound.** We add X of them to the tenants as overburdened tenants and recompute the young
     and the all-age rates, with X = E × the final year's tenancy rate among the emancipated, or
     X = E (all rent).
   - **Variants.** The added tenants are overburdened only as often as the two lowest income groups
     of young tenants, in the final year or in the base year. Those groups' rates themselves fell,
     plausibly by selection, so neither variant is a central estimate.
   - **What it leaves out.** It does not bound who leaves when the number leaving is unchanged,
     selection into renting at older ages, or within-cell selection. It assumes no effect on prices.
   - **What it shows.** For all tenants the result is small partly because young emancipated tenants
     are about 15% of market tenants. For young tenants it exceeds 100% of their fall and rules
     nothing out.
4. **Age comparison** (`data/tenants_by_age.csv`). This is not a placebo test.
   - **What it tests.** It addresses whether selection into leaving home drives the national fall. As
     evidence on young tenants' own fall it would need parallel trends, and it lacks them: their
     median housing cost rose 27.1% from 2021 to 2025, against 14.7% for tenants aged 35–64.
   - **Other selection.** Selection into renting also operates at older ages, through postponed
     purchases and new tenant households.
   - **Power.** The comparison has little: the bootstrap SE of the young-minus-35–49 difference in
     the change is 5.5 points.
5. **Panels** (`scripts/longitudinal.py`).
   - **Leavers** (`data/leavers.csv`). Persons aged 18–34 (end-of-income-year age) living with a
     parent in wave t and seen in t+1. "Left" means either:
     - recorded as moved out (`RB110` = 5) to a private household (`RB120` = 1), or moved out and
       «Perdido», lost to tracing (`RB120` = 4). The destination of the lost is unknown;
     - or present in t+1 with no parent in the household.

     Moves abroad (3) or into institutions (2), deaths, and people absent from t+1 are left out.
     Prior income is personal net income in wave t, grouped as in §5.1 within each transition. Each
     transition t→t+1 comes from one file only. Levels are not comparable across panels, because
     movers are coded differently; we compare ratios between income groups, overall and within ages
     18–24 and 25–34, with Wilson intervals on unweighted counts.
   - **Continuing tenants** (`data/continuing_tenants.csv`). Households paying market rent in two
     consecutive waves under the same household id. We report:
     - their overburden in both years (weight `DB095` of t+1, and unweighted);
     - the same for households with the same members in both waves;
     - the median income and rent changes.

     Every transition from 2013→2014 to 2024→2025 is reported. Households that move untraced, or
     stop renting at market price, drop out. If leaving correlates with a worsening burden, the
     measured fall within households is biased downward; earlier transitions show rises as well as
     falls.

## 6. Counterfactuals, sensitivity, uncertainty

- **Income growth** (`data/income_counterfactual.csv`). Every final-year market-tenant income is
  scaled by g_cost / g_inc, and overburden is recomputed. g_cost is the growth of median housing cost
  of market-rent households between the two surveys. g_inc is one of:
  - the chained median income growth of continuing tenant households over the same transitions (the
    "within-household" version);
  - the cross-section's median income growth, which also reflects who rents.
- **The windows differ.** Incomes refer to calendar years (2020 to 2024: 48 months). Costs are
  measured at interview (about September 2021 to April 2025).
- **Fieldwork lag.** The gap between the middle of the income year and the interview fell from 14.1
  months (2021) to 9.4 months (2025) (`data/fieldwork.csv`). We grew 2025 housing costs over the
  4.7 extra months at 2.8% a year (IPVA, existing contracts, 2024) and at 5% a year.
- **Age definition.** Young tenants' overburden is recomputed with end-of-income-year age (`unit` =
  `persons_emancipated_age_end_of_income_year`).
- **Uncertainty** (`data/bootstrap.csv`).
  - Households are resampled with replacement within regions: 200 replicates, fixed seed, no
    re-calibration.
  - Intervals are normal (point ± 1.96 bootstrap SE); percentile limits are kept for comparison.
  - The 2021–2025 files carry no primary sampling units. For 2019, which does, the independent
    reviewer found PSU-clustered and household-clustered SEs for young tenants' overburden within 0.2
    points (3.29 and 3.40).
  - The 2021 and 2025 samples share no households (four-year rotation), so the interval of their
    difference uses the two standard errors. The 2021 SE is larger (4.3 against 2.4) with a similar
    number of young tenants.

## 7. The CJE

- **The 98.7%** = 1,176 / (14,292.22 / 12).
  - Rent: «Precio de oferta … Idealista.com, aplicando una superficie media de 80 metros cuadrados
    construidos».
  - Salary: the median net salary of a wage earner aged 16–29, built from INE's quarterly labour
    cost survey (ETCL), the age and sex wage structure and the ECV's gross-to-net model.
  - **The 33.6%** = a median room asking rent of 400 € («Renta mediana alquiler habitación») over the
    same salary.
  - All are quoted literally in `data/quotes.csv`, including the full sentence of p. 5 with both
    figures. The 2025 report does not define «coste de acceso al alquiler»; the 2nd-semester 2024
    note does, and is quoted.
- **Comparison** (`data/cje_reconciliation.csv`).
  - **Inputs.** For emancipated market tenants aged 16–29 and 18–34 in ECV 2025 with a recorded rent
    and income, we replace one CJE input at a time with the measured value: rent paid, the tenants'
    own net income, their household's disposable income.
  - **Accounting.** The log gap between the CJE-type ratio and rent paid / household income splits
    into three terms: asking against paid rent, own income against the benchmark, and household
    against own income.
  - **Two benchmarks.**
    - The CJE's salary (an ETCL-based figure, 1,191 €).
    - The median net employee income of young earners in the same ECV (`PY010N` > 0; 749 € at 16–29),
      which counts part-year work. The split depends on the choice, and both are reported. These are
      ratios of medians: an accounting device, not a model.
  - **Also reported:** household types; those living alone; sharers' rent per adult (household rent
    divided by members aged 16+); movers in the last 12 months (`PMG4`); and the share of all young
    people, and of young wage earners, whose own net income would keep the asking rent within 30% or
    40% of it.
- **The CJE's own ECV figures** (`data/cje_own_ecv_figures.csv`). Renter households with a young
  member, under eight definitions: an emancipated member or a responsible person aged 16–29; age at
  interview or at the end of the income year; tenure 3 or 4, or 3 only.
  - **The 780 €.** With the CJE's household definition our mean `HH070` is 770–785 € (CJE: «780 €»).
  - **The 30%.** It is 780 × 12 / 31,167.83 (the CJE's own income figure): arithmetic, not a test.
  - **The 48.9%.** Not reproduced: 35.4–40.1% with the CJE's household definition. Definitions with a
    young responsible person give 47.0–51.0% but a mean cost of 722–748 €.
- **Size.** The ECV does not record floor area, so the 80 m² cannot be tested on young tenants. INE's
  IPVA weights by dwelling-size band put the middle of rent expenditure in the 75–90 m² band
  (`data/ipva.csv`). DatosRTVE reports a SERPAVI mean of 78.6 m² built for rented dwellings; we could
  not open SERPAVI (§2).
- **Emancipation series** (`data/epa_emancipation.csv`).
  - The CJE's chart note is quoted literally.
  - ECV: share of 16–29s with no parent in the household, by both age definitions.
  - EPA: share of 16–29s (age groups 16, 20, 25) with `NPADRE` and `NMADRE` = 00, weighted by
    `FACTOREL`. INE's base-2021 annex weights for 2023 give the same figures as the files now online.
  - This EPA definition does not reproduce the CJE's EPA rates (17.0% in 2023, 15.2% in 2024), nor
    their 2023–2024 change (ours −0.36 points, the CJE's −1.8). It therefore cannot say whether the
    2025 fall would show in the EPA; we report it as a failed attempt.

## 8. Data-quality notes

- **Fieldwork moved**, quoted from INE's releases: «tercer cuatrimestre» in 2017, 2019 and 2021;
  «Segundo cuatrimestre de 2022»; «de febrero a mayo» in 2023, 2024 and 2025. The interview months
  in the files agree. Before 2017 interviews ran between February and July.
- **Collection mode changed.** Face-to-face until 2019, telephone in 2020, and from 2021 «el método
  multicanal» (40% web, 53% telephone, 7% face-to-face in 2021).
- **Income and rent refer to different moments.** Income is the previous calendar year; rent and
  costs are current. This is Eurostat's convention for these indicators. In 2021 the income year was
  2020.
- **Movers in the panel.** Most young people who leave are coded as moved and lost (`RB120` = 4).
  The 2019–2022 file gives a flatter income gradient than the other three panels, and its mover
  records carry a parent identifier (`RB220`) that the others leave empty. We report it but do not
  lean on it.
- **Rent changes in the panel are noisy.** The median change for continuing tenants is 0–1.2% a
  year, 20–31% report exactly the same rent, and the mean (ratios capped at 3) ranges from 0.1% to
  6.3% a year.
- **Small samples.** Young tenants living alone (n = 227 at 18–34, 100 at 16–29) and recent movers
  (n = 129 and 62) are small samples. No regional figures are reported.

## 9. Not done

- **No floor area for young tenants**, and SERPAVI was not accessible.
- **No causal estimate of selection.** The panel shows who leaves, not who would have left at other
  rents. The bound covers one channel.
- **No regional breakdown.** The samples are too small for young tenants.
- **Not reproduced exactly:** the CJE's EPA emancipation rate and its 48.9% overburden.
- **No CPI deflation.** All comparisons are within a year, or growth of income against growth of
  costs.
