<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/readme-banner-dark.png">
  <img alt="EasyxLab · a research lab by EasyByte" src=".github/readme-banner.png" width="100%">
</picture>

# EasyxLab — studies

<img alt="EasyxLab study" src=".github/badge-study.svg">

Original research by EasyxLab, the research lab of [EasyByte Hub S. Coop. Mad.](https://easybyte.es), a worker cooperative of software developers in Spain. Each study measures something practitioners usually take on faith, publishes its method and reproducible scripts, and releases its aggregated data.

| study | question | headline |
|---|---|---|
| [S1](studies/s1-verifactu-conformance/) | Do the XML records that open-source Verifactu implementations publish comply with Spain's rules? | Of 35 files presented as valid records, 10 (28.6%) contain at least one error; the most frequent defect is a declared hash that does not match the record. |
| [S2](studies/s2-spoofed-ai-crawlers/) | How much traffic that claims to be an AI or search crawler is real? | 39.3% of 16,548 claims on three small sites were spoofed; for user-initiated fetchers (ChatGPT-User, Claude-User, Perplexity-User…) 67.8%. |
| [S3](studies/s3-ai-marks-survival/) | Do AI provenance marks (C2PA, IPTC, China's AIGC label) survive common image, video and audio pipelines? | Every pixel or container rewrite removed the embedded C2PA manifest (124/124); editing one metadata field after signing left it present but invalid (6/6). |
| [S4](studies/s4-wikidata-drug-labels/) | How accurate are Wikidata's multilingual drug names? | About 0.9% of 34,207 labels are wrong (a lower bound), concentrated in Urdu, Persian, Russian and Hindi; 135 proposed corrections, not applied. |
| [S5](studies/s5-pypi-attestations/) | Who publishes PEP 740 attestations on PyPI and npm, and who stopped? | The latest version is attested for 3,479 of 14,995 top PyPI projects (23.2%); 138 projects that once attested no longer do in the line `pip` installs, 96 of them after a change of publishing tool or workflow. |
| [S6](studies/s6-commons-ai-marks/) | Do AI-generated images on Wikimedia Commons carry provenance marks? | Files with a machine-readable AI mark rose from 25.8% of January–May 2026 uploads to 50.2% of June–July uploads; our own validator, ai-mark-lint 0.1.0, wrongly rejected 187 valid C2PA manifests (fixed in 0.1.1). |
| [S7](studies/s7-aio-spanish-regulation/) | Do Google's AI Overviews and AI Mode keep up with Spanish rule changes? | Judged against the consolidated law in force on 2 October 2026, 12 of 240 AI Overview answers (5.0%) and 13 of 291 AI Mode answers (4.5%) on 27 recently changed rules were outdated or wrong. |
| [S8](studies/s8-spanish-public-sector-web/) | What can a machine verify on Spain's public-sector websites? | Of 5,130 public-sector home pages served over HTTPS, 1,688 (32.9%) send HSTS; of 5,570 entities, 4 serve a `security.txt` that is strictly valid under RFC 9116. |
| [S10](studies/s10-netex-naps/) | Are the public-transport NeTEx timetables on Europe's national access points valid against the open schemas? | 8 of 34 timetable datasets from five national access points are fully valid against the NeTEx XSD, all of them French; the static MMTIS deadlines passed in 2019–2025, and the 1 December 2026 date covers parking and vehicle sharing, not timetables. |
| [S11](studies/s11-str-registration-numbers/) | Do the registration numbers on Airbnb listings exist in the official registries? | In June 2026, in five Spanish areas with an open registry, 2,066 of 31,222 listings showing a well-formed tourist-dwelling number (6.6%) showed one we could not trace to any registered dwelling; a further 557 (1.8%) showed a registered dwelling written in a recognisable wrong form. |
| [S12](studies/s12-eviction-statistics/) | Is Spain's record low of evictions in early 2026 real, or an effect of the court reform? | The CGPJ's 4,005 practised evictions in Q1-2026 (−45.4%) coincide with a change in how evictions are counted under Organic Law 1/2025, documented in the CGPJ's own forms; a pre-registered test is inconclusive on the overall effect, and an out-of-sample check follows the Q2-2026 release. |
| [S13](studies/s13-tourist-registration-rush/) | Was there a rush to register tourist dwellings before Spain's community-approval rule of 3 April 2025? | In the 14 days before the rule, the Comunitat Valenciana's open registry received 1,093 tourist-dwelling registrations against 456 expected; 55% of the excess was in València city and Torrevieja, and the rush cannot be attributed to the rule alone. |
| [S14](studies/s14-state-sales-energy-label/) | Do public sellers show the energy label when they announce property sales in Spain's Official Gazette? | Of 306 lots covered by RD 390/2021 announced in the BOE between January 2025 and September 2026, 144 (47.1%) did not state an energy rating; whether a BOE sale notice counts as «publicidad» under art. 15.2 is an open legal question. |
| [S19](studies/s19-dana-flood-mapped-vs-observed/) | How many dwellings inside the observed extent of the October 2024 DANA in Valencia lay outside the official flood maps? | About 39–66% of the dwellings inside the observed extent were outside every official flood zone, depending on the extent and the rule: 43,359 of 84,789 (51.1%) in the Copernicus extent and 53,801 of 138,217 (38.9%) in the Generalitat's footprint under the reference rule; 1,776 were in buildings dated 2017–2024. Counts of exposure, not of illegality. |
| [S20](studies/s20-recovery-plan-housing-commitments/) | What did Spain commit to the EU on social housing in its recovery plan, and how did it change? | The ICO social-housing loan line fell from €4,000 million to €567,854,983 (−85.8%) and the dwellings target from 20,000 «new» to 15,718 «constructed or rehabilitated», across ten versions of the Council decision (2021–2026). |
| [S21](studies/s21-golden-visa-end/) | Did purchases by foreign non-residents fall after Spain ended its golden visa? | The end of the golden visa (3 April 2025) coincided with a fall in foreign non-resident purchases in Madrid and Barcelona (−35.9%, against −8.5% elsewhere), but the tests fixed in advance do not support attributing it to the repeal; an out-of-sample test follows MIVAU's release of 16 December 2026. |
| [S22](studies/s22-homeless-shelter-record/) | What does the +57.5% record in Spain's 2024 survey of centres for homeless people measure? | 81.3% of the 2022–2024 increase in adults accommodated per day (21,684 → 34,145) is in centres specialised in immigrants, whose definition INE changed in the record year; outside them the rise per centre was +4.7%. |
| [S23](studies/s23-public-housing-stock/) | How large is Spain's public housing stock, and where do the EU averages it is compared with come from? | Every count of Spain's public stock (290,000 in 2019, 318,000 in 2023) comes from two Ministry surveys of regional and municipal housing; 2.5%, 3.3%, 3.4% and 3.5% equal INE's share of households paying a below-market rent; no annual report on the State's own stock under art. 32 of the 2023 housing law was found by any route open to us. |
| [S15](studies/s15-mica-white-papers/) | Are MiCA crypto-asset white papers published in the machine-readable format required since 23 December 2025? | Of 440 white papers notified or updated in ESMA's interim MiCA register since 23 December 2025, 143 (32.5%) lead from the registered URL to the Inline XBRL file the rules require, and 110 of those validate against ESMA's taxonomy; one producer serves 77 of the 110. |
| [S16](studies/s16-eu-press-tdm-reservations/) | Do EU news publishers state text-and-data-mining reservations that an AI crawler can read, whatever its name? | Of 1,356 EU-27 press sites read in full on 2026-10-03, 99 (7.3%) state a text-and-data-mining reservation that binds any crawler; 480 of the 558 that block named AI crawlers (86.0%) state nothing a crawler with a new name would read. |
| [S17](studies/s17-high-value-datasets/) | What does a machine see about the EU's high-value datasets on data.europa.eu, and does it match what Member States report? | On 2026-10-03, 28 months after the rules became applicable, the European data portal identified no high-value dataset for 7 of the 27 Member States, 3 of which had told the 2025 Open Data Maturity survey that their portal uses the DCAT-AP HVD tag; another 13,948 records (12,062 distinct datasets) carried an HVD category without the legal reference the portal needs to count them. |
| [S18](studies/s18-actions-immutable-releases/) | What do GitHub's immutable releases protect in the Actions workflows of popular repositories? | Where the action's author already publishes immutable releases, only 312 of 6,898 (4.5%) tag references in the workflows of GitHub's top 1,000 repositories point to a protected tag; most use the movable major tag that GitHub's documentation recommends, and for 3,238 of 6,586 (49.2%) unprotected references an immutable tag already points to the same commit. |

**The full papers are published at [easybyte.es/lab](https://easybyte.es/lab/studies/)**, in HTML and PDF. This repository holds what is needed to check and reproduce each study: its abstract, method, verification, scripts and aggregated data.

## How these studies were made

The studies were run by AI agents supervised by EasyByte: collection, classification, analysis and drafting. Every paper was then checked by an independent AI reviewer, which recomputed the figures from the data, verified each quotation against its source and re-ran the scripts where feasible. Each paper has an "Automation and review" section stating exactly what was automated. The point of publishing the scripts and data is that anyone can check the results.

## Competing interests

EasyByte develops [verifactu-lint](https://github.com/easybytehub/verifactu-lint), the instrument of S1, and offers commercial Verifactu services. EasyByte also develops [ai-mark-lint](https://github.com/easybytehub/ai-mark-lint), which automates the before/after comparison in S3 and is the validator whose defects S6 found and reported. It develops [attest-lint](https://github.com/easybytehub/attest-lint), which flags in a lockfile the attestation regressions S5 measures. The sites in S2 are EasyByte's own and are anonymised as Site A, B and C.

## What is not here

- **Third-party files** (S1) and **raw access logs** (S2) are not redistributed. S1 publishes anonymised repository IDs; S2 publishes aggregates only, with no IP addresses.
- **Nothing was submitted, uploaded or edited elsewhere.** S4's Wikidata corrections are proposals for a Wikidata editor to review.

## Licences

- **Code** (`scripts/`, `tests/`): Apache-2.0, see [LICENSE](LICENSE).
- **Data, fixtures and text:** CC BY 4.0, see [LICENSE-DATA](LICENSE-DATA).
- **Exception, S4:** its data and corrections derive from Wikidata (CC0) and are meant to go back there, so they are released under CC0 1.0 ([studies/s4-wikidata-drug-labels/LICENSE-DATA](studies/s4-wikidata-drug-labels/LICENSE-DATA)).

Cite a study as: *EasyxLab (2026). [title of the study]. Study Sn. EasyByte Hub S. Coop. Mad. https://github.com/easybytehub/easyxlab*.

---

EasyxLab · a research lab by [EasyByte](https://easybyte.es)
