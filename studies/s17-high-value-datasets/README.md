# S17 — High-value datasets on data.europa.eu: what a machine sees, and what Member States say

*EasyxLab · study S17 · data collected 2026-10-03 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s17/paper/](https://easybyte.es/lab/studies/s17/paper/) · [PDF](https://easybyte.es/lab/studies/s17/paper.pdf)

## Abstract

Commission Implementing Regulation (EU) 2023/138 has applied since 9 June 2024. It requires the listed high-value datasets (HVD) to be denoted as HVD in their metadata (Art. 3(5)), offered via APIs (Art. 3(1)) and licensed under CC0, CC BY 4.0 or an equivalent or less restrictive open licence (Art. 4(3)). Almost twenty-eight months later, on 2026-10-03, we read every record the European portal flags as HVD (snapshot 11:12 UTC). We then compared the result with each Member State's answers to the Open Data Maturity (ODM) 2025 questionnaire.

**Member States with none identified.** For 7 of the 27 Member States (Bulgaria, Cyprus, Hungary, Poland, Romania, Slovenia and Slovakia), the European portal does not identify any dataset as HVD. 20 of 27 have at least one. The portal flags 27,972 records in all, which are 27,526 distinct datasets once the portal's `~~n` duplicates are merged. Record counts depend heavily on how finely a country catalogues, so they do not tell how many HVDs it holds. 10,032 of the 27,972 records come from one Rhineland-Palatinate municipal geoportal.

**Self-report against census.** ODM 2025 asked two questions. P12 asks whether public bodies denote HVDs in their metadata; Q5 asks whether a portal implements the DCAT-AP HVD tag, which is what the European portal reads.

| Member States | ODM P12 | ODM Q5 | HVD records on the portal |
|---|---|---|---|
| Cyprus, Slovenia, Slovakia | yes | yes | 0 |
| Hungary, Poland, Romania | yes | no | 0 |
| Bulgaria | no | no | 0 |
| Estonia | yes | no | 87 |
| Greece | no | no | 1,281 |
| 18 others | yes | yes | 32 to 19,162 each |

The questionnaire describes 2025 and the census 2026-10-03, so the gaps lie between two dates.

**Where Polish records are lost.** dane.gov.pl flags 120 datasets as HVD from the EU list. We found 96 of them on the European portal, and none carries an HVD property or a licence. We read the national DCAT-AP feed pages that hold 7 of these datasets: they carry no HVD property, and they put licences under `dcat:license`, which DCAT does not define. The 24 not found all have IDs of 18,216 or more, while all 96 found have IDs of 9,156 or less. The feed advertises a last page of 500 × 20 = 10,000 items out of 28,132. This is consistent with the harvest stopping at the feed's advertised last page; we have not confirmed it with the operators (we contacted no one).

**Half-tagged.** 13,948 records carry an HVD category but not the regulation's ELI, so the portal does not count them. They are 12,062 distinct datasets not already counted as HVD under another record. 12,343 of the 13,948 come from five catalogues in Germany, Ireland, Austria and Sweden. In the other direction, 1,033 of 27,972 (3.7%) carry the ELI without a category.

**Licence (Art. 4(3)).** All distributions are under CC0, CC BY 4.0 or an equivalent open licence in 17,104 of 27,972 records (61.1%). Under our frozen rule, 7,483 (26.8%) have at least one distribution with a share-alike, non-commercial, or closed/catch-all licence value. 5,855 of those 7,483 fail only because of the German value `other-closed`, a catch-all that the portal itself types as "unknown IPR". With that value counted as unclear, 1,628 (5.8%) fail. 1,456 (5.2%) have no licence and no rights statement anywhere in their RDF.

**API (Art. 3(1)).** 5,146 of 27,972 records (18.4%) have a Data Service modelled as DCAT-AP HVD requires. Another 18,145 have a distribution whose URL or format looks like an API. The count is per portal record, not per dataset listed in the Annex.

**Reachability.** 1,387 of 1,510 sampled distribution URLs (91.9%) answered with a 2xx status. Another 188 were stopped by robots.txt, because it disallowed them or could not be read: 176 before any request, and 12 after one request, at the address they redirected to.

**Prior work.** The European portal shows HVD counts. ODM publishes what countries self-report. An ETC DI report analyses environmental HVDs in three subdomains. In the indexes we could reach, we found no work that checks every HVD record against Arts. 3 and 4, or compares the census with each country's ODM answer.

**Automation and review.** AI agents collected the data, ran the analysis and wrote the text. An independent AI reviewer then recomputed every figure from the data, checked the legal and ODM quotes against their sources, and audited 48 records against their RDF. Its corrections have been applied and are listed in `METHOD.md` §9.

The paper is at https://easybyte.es/lab/studies/s17/paper/.

## Contents

| path | what |
|---|---|
| `METHOD.md` | population, rules, licence classes, sample, corrections and deviations |
| `VERIFICATION.md` | how to recompute and check each headline figure |
| `data/` | per-record flags (`census_records.csv`) and licence values (`licences_by_dataset.csv`), IDs only; tables by Member State, catalogue and source; reachability sample without URLs; ODM answers; queries with timestamps; source files with sha256 |
| `scripts/` | collection (network) and analysis (offline) scripts; `hvd_check.py`, the per-record checker |
| `tests/` | tests of the rules and the checker |

To re-run the offline analysis: `bash scripts/run.sh`. To check the abstract: `python3 scripts/check_headline.py`. To check one record: `python3 scripts/hvd_check.py <dataset-id-or-DCAT-AP-file>` (needs `rdflib`).

## Licences

Code: Apache-2.0. Data and text: CC BY 4.0. The portal's metadata are CC0 ("the European Union has waived all copyright and related or neighbouring rights to metadata of the open data portal via Creative Commons CC0 1.0 Universal"). The ODM 2025 answers are re-published from data.europa.eu under the Commission's reuse policy (Decision 2011/833/EU). We publish no contact points, no third-party e-mail addresses and no personal names. The only address in the package is EasyxLab's own, in our crawler's User-Agent.
