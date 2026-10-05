<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/readme-banner-dark.png">
  <img alt="EasyxLab · a research lab by EasyByte" src=".github/readme-banner.png" width="100%">
</picture>

# EasyxLab — studies

<img alt="EasyxLab study" src=".github/badge-study.svg">

Original research by EasyxLab, the research lab of [EasyByte Hub S. Coop. Mad.](https://easybyte.es), a worker cooperative of software developers in Spain. Each study measures something practitioners usually take on faith, publishes its method and reproducible scripts, and releases its aggregated data.

| study | question | headline |
|---|---|---|
| [S2](studies/s2-spoofed-ai-crawlers/) | How much traffic that claims to be an AI or search crawler is real? | 39.3% of 16,548 claims on three small sites were spoofed; for user-initiated fetchers (ChatGPT-User, Claude-User, Perplexity-User…) 67.8%. |
| [S3](studies/s3-ai-marks-survival/) | Do the machine-readable labels used to meet EU, Californian and Chinese rules on AI-generated images, video and audio survive ordinary re-saving, resizing or conversion? | All 124 times we re-saved, resized or converted a signed image, video or audio file with common open-source tools (124/124), they removed its embedded content credential, the signed record that can label it AI-made, even with the "keep metadata" options we tried. Online platforms were not tested. |
| [S4](studies/s4-wikidata-drug-labels/) | How accurate are Wikidata's multilingual drug names? | About 0.9% of 34,207 labels are wrong (0.5% at the lower bounds of precision; recall unknown), concentrated in Urdu, Persian, Russian and Hindi; 135 proposed corrections, not applied. |
| [S5](studies/s5-pypi-attestations/) | Who publishes PEP 740 attestations on PyPI and npm, and who stopped? | The latest version is attested for 3,479 of 14,995 top PyPI projects (23.2%); 138 projects that once attested no longer do in the line `pip` installs, 96 of them after a change of publishing tool or workflow. |
| [S7](studies/s7-aio-spanish-regulation/) | Do Google's AI Overviews and AI Mode keep up with Spanish rule changes? | Judged against the consolidated law in force on 2 October 2026, 12 of 240 AI Overview answers (5.0%) and 13 of 291 AI Mode answers (4.5%) on 27 rules (26 recently changed, one control) were outdated or wrong. |
| [S8](studies/s8-spanish-public-sector-web/) | What can a machine verify on Spain's public-sector websites? | Of 5,130 public-sector home pages served over HTTPS, 1,688 (32.9%) send HSTS; of 5,570 entities, 4 serve a `security.txt` that is strictly valid under RFC 9116. |
| [S10](studies/s10-netex-naps/) | Are the public-transport NeTEx timetables on Europe's national access points valid against the open schemas? | 8 of 34 timetable datasets from five national access points are fully valid against at least one of the two public NeTEx XSD releases we tested (1.3.2 and 2.0.0; 7 only against 1.3.2), all of them French; the static MMTIS deadlines passed in 2019–2025, and the 1 December 2026 date covers parking and vehicle sharing, not timetables. |
| [S11](studies/s11-str-registration-numbers/) | Do the registration numbers on Airbnb listings exist in the official registries? | In June 2026, in five Spanish areas with an open registry, 2,066 of 31,222 active listings showing a well-formed tourist-dwelling number (6.6%) showed one we could not trace to any registered dwelling; a further 557 (1.8%) showed a registered dwelling written in a recognisable wrong form. |
| [S12](studies/s12-eviction-statistics/) | Did evictions in Spain really fall by almost half in early 2026, or did the court reform change how they are counted? | Spain's judiciary reported 4,005 evictions carried out in January–March 2026, 45.4% fewer than a year earlier. The fall coincides with a change in who counts them, documented in its own forms; a test registered before it was run is inconclusive on whether that change explains it. |
| [S14](studies/s14-state-sales-energy-label/) | Do public sellers show the energy label when they announce property sales in Spain's Official Gazette? | Of 306 lots covered by RD 390/2021 announced in the BOE between January 2025 and September 2026, 144 (47.1%) did not state an energy rating; whether a BOE sale notice counts as «publicidad» under art. 15.2 is an open legal question. |
| [S19](studies/s19-dana-flood-mapped-vs-observed/) | How many dwellings inside the mapped outline of the October 2024 flood in Valencia (the DANA) lay outside the official flood maps? | Of 84,789 dwellings inside the EU's Copernicus outline of the October 2024 Valencia flood, 43,359 (51.1%) lay outside every official river-flood zone, and 1,776 were in buildings dated 2017–2024. Across two flood outlines and three counting rules, the share outside is 39–62%. Counts of exposure, not of illegality. |
| [S20](studies/s20-recovery-plan-housing-commitments/) | What did Spain commit to the EU on social housing in exchange for recovery funds, and how did that change? | Spain first committed to the EU to complete 20,000 new dwellings for social rental or at affordable prices; the August 2026 proposal asks for 15,718 under «Construction or rehabilitation», with no completion requirement stated, as since December 2025. In the same proposal Spain's social-housing loan line at the state bank ICO is 85.8% below its 2023 commitment (81.3% below in the version adopted in January 2026). |
| [S21](studies/s21-golden-visa-end/) | Did purchases by foreign non-residents fall after Spain ended its golden visa? | The end of the golden visa (3 April 2025) coincided with a fall in foreign non-resident purchases in Madrid and Barcelona (−35.9%, against −8.5% elsewhere), but the tests fixed in advance do not support attributing it to the repeal; an out-of-sample test follows MIVAU's release of 16 December 2026. |
| [S22](studies/s22-homeless-shelter-record/) | What does the +57.5% record in Spain's 2024 survey of centres for homeless people measure? | 81.3% of the 2022–2024 increase in occupied places held by adults (mean of two days; 21,684 → 34,145) is in centres INE classes as specialised in immigrants; outside them the rise per centre was +4.7%. In the record year INE moved its definition of homelessness to the ETHOS typology and for the first time asked each centre to declare its specialisation. |
| [S23](studies/s23-public-housing-stock/) | How much public housing does Spain have, and where do the shares quoted for it come from? | Spain's regions and municipalities let 318,000 dwellings in the Ministry's 2023 survey, 1.7% of households; about a fifth of the count is extrapolated by population. Official texts' 2.5–3.5% shares equal the share of households renting below market price, whoever the landlord, and no legally required inventory of the State's own stock was found by any route open to us. |
| [S24](studies/s24-youth-rent-burden/) | What do young tenants in Spain pay, and why did a smaller share of them live in households spending over 40% of their income on housing? | In 2025, 31.5% of people aged 18–34 in Spain who had left home and rented at market price lived in households that spent over 40% of their disposable income on housing, against 42.7% in 2021; their median rent was €630 a month. Older tenants' overburden fell about as much; for the young, that the fall reflects who leaves home cannot be ruled out. |
| [S15](studies/s15-mica-white-papers/) | Are MiCA crypto-asset white papers published in the machine-readable format required since 23 December 2025? | Of 440 rows of ESMA's interim MiCA register whose record was created or updated since 23 December 2025, 143 (32.5%) lead from the registered URL to an Inline XBRL file in the format the rules prescribe for drawing up white papers, and 110 of those validate against ESMA's taxonomy; one producer serves 77 of the 110. |
| [S16](studies/s16-eu-press-tdm-reservations/) | Do European news sites reserve their content from text and data mining in a way that an AI crawler can read, whatever its name? | Of 1,356 EU news sites read in full, 558 block at least one AI crawler by name, but 480 of those (86.0%) state no reservation in a form we count as addressed to any crawler; 83 of the 480 state one only in `robots.txt` comments, in a label the current IETF draft dropped or in the non-standard `noai`. Only 99 (7.3%) state a reservation addressed to any crawler, whatever its name, 11 of them by closing the whole site to unnamed crawlers. |
| [S17](studies/s17-high-value-datasets/) | What does a machine see about the EU's high-value datasets on data.europa.eu, and does it match what Member States report? | On 2026-10-03, almost 28 months after the rules became applicable, the European data portal identified no high-value dataset for 7 of the 27 Member States, 3 of which had told the 2025 Open Data Maturity survey that their portal uses the DCAT-AP HVD tag; another 13,948 records, 12,062 of them distinct datasets not otherwise counted, carried an HVD category without the legal reference the portal needs to count them. |
| [S18](studies/s18-actions-immutable-releases/) | What do GitHub's immutable releases protect in the Actions workflows of popular repositories? | Where the action's author already publishes immutable releases, only 312 of 6,898 (4.5%) tag references in the workflows of GitHub's 1,000 most-starred active repositories point to a protected tag; most use the movable major tag that GitHub's documentation lets action authors recommend, and for 3,238 of 6,586 (49.2%) unprotected references an immutable tag already points to the same commit. |

**The full papers are published at [easybyte.es/lab](https://easybyte.es/lab/studies/)**, in HTML and PDF. This repository holds what is needed to check and reproduce each study: its abstract, method, verification, scripts and aggregated data.

## Withdrawn studies

S1 (conformance of open-source Verifactu implementations) and S6 (provenance marks on AI-generated images in Wikimedia Commons) were withdrawn on 5 October 2026. A review of every study found errors in how several of their figures were counted: mixed units and denominators. S13 (the rush to register tourist dwellings before 3 April 2025) was withdrawn the same day, because several of its readings of the data went further than the data allow. None of them is published any longer, and they should not be cited.

## How these studies were made

The studies were run by AI agents supervised by EasyByte: collection, classification, analysis and drafting. Every paper was then checked by an independent AI reviewer, which recomputed the figures from the data, verified each quotation against its source and re-ran the scripts where feasible. Each paper has an "Automation and review" section stating exactly what was automated. The point of publishing the scripts and data is that anyone can check the results.

## Competing interests

EasyByte develops [verifactu-lint](https://github.com/easybytehub/verifactu-lint) and offers commercial Verifactu services. EasyByte also develops [ai-mark-lint](https://github.com/easybytehub/ai-mark-lint), which automates the before/after comparison in S3. It develops [attest-lint](https://github.com/easybytehub/attest-lint), which flags in a lockfile the attestation regressions S5 measures. The sites in S2 are EasyByte's own and are anonymised as Site A, B and C.

## What is not here

- **Raw access logs** (S2) are not redistributed; S2 publishes aggregates only, with no IP addresses.
- **Nothing was submitted, uploaded or edited elsewhere.** S4's Wikidata corrections are proposals for a Wikidata editor to review.

## Licences

- **Code** (`scripts/`, `tests/`): Apache-2.0, see [LICENSE](LICENSE).
- **Data, fixtures and text:** CC BY 4.0, see [LICENSE-DATA](LICENSE-DATA).
- **Exception, S4:** its data and corrections derive from Wikidata (CC0) and are meant to go back there, so they are released under CC0 1.0 ([studies/s4-wikidata-drug-labels/LICENSE-DATA](studies/s4-wikidata-drug-labels/LICENSE-DATA)).

Cite a study as: *EasyxLab (2026). [title of the study]. Study Sn. EasyByte Hub S. Coop. Mad. https://github.com/easybytehub/easyxlab*.

---

EasyxLab · a research lab by [EasyByte](https://easybyte.es)
