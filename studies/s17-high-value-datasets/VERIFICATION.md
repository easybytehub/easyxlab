# S17 — Verification

Every headline figure is computed by `scripts/06_tables.py` from the files in `data/` and written to `data/summary.json`. `scripts/check_headline.py` does four things. It recounts 19 key figures directly from the CSVs and compares them with `summary.json`. It asserts that every number in the README abstract matches. When [the paper](https://easybyte.es/lab/studies/s17/paper/) is present, it also checks 32 headline sentences of the paper (not every table cell). And it checks the figures typed by hand in `METHOD.md` and in this file: the D5 sensitivity and the split of the 188 `skipped_robots` URLs. It exits with status 1 on any mismatch. `06_tables.py` also checks that the licence verdicts in `census_records.csv` match a recomputation from `licences_by_dataset.csv`. The independent review recomputed every figure, including Table 1 of the paper, with its own code.

```bash
bash scripts/run.sh             # regenerate tables offline, run tests, check headlines
python3 scripts/check_headline.py
```

## 1. Recompute from the published data (offline)

| figure | file | how |
|---|---|---|
| 27,972 HVD datasets; 19,162 in DE (68.5%) | `data/census_records.csv` | count rows; count `country == DE` |
| 7 Member States with 0 (BG, CY, HU, PL, RO, SI, SK) | `data/by_member_state.csv` | `hvd_datasets == 0` |
| 25 "yes" to ODM P12; 6 of them with 0 on the portal | `data/odm2025_answers.csv`, `data/by_member_state.csv` | `odm_P12_denoted_in_metadata == yes` and `gap_class == self-yes-portal-zero` |
| 13,948 with category but no ELI; 12,343 in five catalogues | `data/sparql_summary.json` (`h1_category_without_eli_total`), `data/half_tagged_ids.csv` | records whose catalogue list includes one of the five largest catalogues (the five rows of `data/category_without_eli_by_catalogue.csv` sum to 12,345 because 2 records are in both bev-at and bmlfuw-at) |
| 1,033 with ELI but no category (3.7%) | `data/census_records.csv` | `n_categories == 0` |
| licence: 17,104 pass, 7,483 fail, 1,577 unclear, 1,808 none in index | `data/census_records.csv` | column `licence_verdict` |
| 1,456 confirmed with no licence and no rights in RDF | `data/census_records.csv` | `rdf_licence_check == confirmed_none` |
| API modelled 5,146 (18.4%); inferable only 18,145 | `data/census_records.csv` | `api_index_access_service == 1 or api_rdf_served == 1`; else `api_inferable == 1` |
| 188 `skipped_robots` (176 not requested; 12 requested once, redirect not followed); 1,387 of the other 1,510 URLs 2xx (91.9%) | `data/reach_sample.csv` | `outcome == skipped_robots`, split by `hops` (0, or 1 after a 3xx); `outcome == ok` over rows whose outcome is not `skipped_robots`/`bad_url` |
| Poland: 120 flagged, 96 found, 0 with HVD properties or licence | `data/poland_case.json` | fields `source_flag_ec_list`, `ec_list_found_*` |
| Poland: 7 EU-list HVDs on 6 feed pages, 0 HVD properties, licences only as `dcat:license`; IDs found ≤ 9,156, missing ≥ 18,216; last page 500 × 20 vs 28,132 items | `data/poland_case.json` | `feed_pages`, `harvest_hypothesis` |
| 27,526 distinct base IDs; 446 surplus records (ES 421, LV 17, IT 6, DE 2) | `data/census_records.csv` | strip `~~n` from `dataset_id` and count distinct |
| 10,032 records from one Rhineland-Palatinate geoportal; at least 12,798 from the Land's geoportals | `data/census_records.csv`, `data/source_concentration.csv` | host embedded in `dataset_id`; host list in `scripts/06_tables.py` (`RLP_EXTRA`) |
| other-closed sensitivity: 5,855 fail only on it; as class E, fail 1,628 (5.8%) | `data/licences_by_dataset.csv` | reclassify the value `http://dcat-ap.de/def/licenses/other-closed` and recompute (see `verdict()` in `06_tables.py`) |
| half-tagged: 13,948 records, 13,054 distinct base IDs, 992 twins of HVD records, 12,062 distinct not counted | `data/half_tagged_ids.csv`, `data/census_records.csv` | base IDs and set difference |
| of the 992 twins, 990 of govdata records (758 in gdi-de, 232 not linked to a catalogue) and 2 codsi twins of datos-gob-es records | `data/half_tagged_ids.csv`, `data/census_records.csv` | catalogue of the census records sharing each half-tagged record's base ID, in either direction of the `~~n` suffix, one count per half-tagged record (`half_tagged_twins_by_census_catalogue`) |
| ODM Q5: zero states CY, SI, SK said yes; HU, PL, RO, BG no; EE and GR no with HVDs | `data/by_member_state.csv` | columns `odm_Q5_dcatap_hvd_tag`, `gap_class_q5` |
| D5: 2 requests would have been disallowed (two Danish hosts, whose sampled URLs are all `skipped_robots`); 8 keys on 7 hosts with robots.txt unreadable after redirects; reachability without those 7 hosts 1,359 of 1,482 (91.7%) | `data/robots_redirect_audit.json`, `data/reach_sample.csv` | hosts whose `robots_after_redirects` is `server-error` or starts with `error`; drop their rows and recount `ok` over rows whose outcome is not `skipped_robots`/`bad_url` |

Quick checks with standard tools:

```bash
awk -F, 'NR>1' data/census_records.csv | wc -l                                  # 27972
awk -F, 'NR>1 && $2=="DE"' data/census_records.csv | wc -l                      # 19162
awk -F, 'NR>1 {print $14}' data/census_records.csv | sort | uniq -c             # licence_verdict
awk -F, 'NR>1 && $16=="confirmed_none"' data/census_records.csv | wc -l         # 1456
awk -F, 'NR>1 {print $7}' data/reach_sample.csv | sort | uniq -c                # reachability outcomes
```

## 2. Re-measure on the live portal

The portal re-harvests every day, so counts will drift. The exact queries and their UTC timestamps are in `data/queries.json`.

- Census count: `https://data.europa.eu/api/hub/search/search?filter=dataset&facets={"is_hvd":["true"]}&limit=0` → `result.count` (27,972 at 2026-10-03T11:12:44Z), and the `country` facet for the per-country counts.
- Half-tagged count (SPARQL, `https://data.europa.eu/sparql`):

```sparql
PREFIX dcat:<http://www.w3.org/ns/dcat#> PREFIX dcatap:<http://data.europa.eu/r5r/>
SELECT (COUNT(DISTINCT ?d) AS ?n) WHERE { ?d a dcat:Dataset ; dcatap:hvdCategory ?c .
  FILTER NOT EXISTS { ?d dcatap:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj> } }
```

- One record: `python3 scripts/hvd_check.py <dataset-id>` reads `https://data.europa.eu/api/hub/repo/datasets/<id>.ttl` and applies the same rules. For example, `2c2b8ea6-2489-49bf-b6cc-795f4c05d2ba` passes all three checks.
- Poland: `https://api.dane.gov.pl/1.4/datasets?has_high_value_data_from_ec_list=true&per_page=1` → `meta.count` (120), and `https://api.dane.gov.pl/1.4/catalog.rdf`, where you can count `<dcat:license` against `<dct:license`.

## 3. Law and self-report quoted

- Regulation text: Cellar, CELEX 32023R0138 (`http://publications.europa.eu/resource/celex/32023R0138`, `Accept-Language: eng`). Amendments, corrigenda and consolidations were looked up in the Cellar SPARQL endpoint (`https://publications.europa.eu/webapi/rdf/sparql`, properties `cdm:resource_legal_amends_resource_legal`, `cdm:resource_legal_corrects_resource_legal`, `cdm:act_consolidated_consolidates_resource_legal`) on 2026-10-03; see [the paper](https://easybyte.es/lab/studies/s17/paper/) §3.
- ODM 2025: `2025_odm_report_6.pdf` (byte-identical to `2025_odm_report_7.pdf`), Table 8 p. 36, p. 11, Table 41 p. 91, p. 37. Per-country answers: `2025_odm_questionnaire_data.xlsx`, sheet `merged_responses`. URLs and sha256 of these and of the other source documents are in `data/sources.json`.
- DCAT-AP HVD 3.0.0: https://semiceu.github.io/DCAT-AP/releases/3.0.0-hvd/

## 4. Privacy check

The published files hold dataset IDs, distribution IDs, host names, licence IRIs and counts. They hold no contact points, e-mail addresses or person names. IP-literal hosts would be written as `ip-literal`; there were none. The only e-mail address in the package is EasyxLab's own, `contact@easybyte.es`, which is in our crawler's User-Agent on purpose so that site operators can identify and contact us. The privacy grep run before release is recorded in the private status file.
