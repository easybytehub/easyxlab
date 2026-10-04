# S20 — Method

*EasyxLab · study S20 · working draft*

## 1. Sources

All sources were downloaded on 4 October 2026. Third-party texts stay in `data/raw/` (not
published); `data/` holds the extracted literal passages and counts.

| source | what we took | access |
|---|---|---|
| Commission proposals for a Council Implementing Decision (CID) approving or amending the assessment of Spain's recovery and resilience plan, COM(2021) 322 to COM(2026) 435 | the full text of each version: decision (recitals) and annex (measures, milestones, targets) | Cellar (Publications Office), SPARQL to list them, then the English XHTML items; CELEX numbers in `scripts/s20lib.py` |
| Council documents (ST) with the text of each version as prepared for adoption | decision and annex, English PDF | Cellar, by Council document number (`scripts/fetch.py`, `COUNCIL_DOCS`) |
| Commission staff working documents (SWD) accompanying the proposals | the estimated cost of each measure ("Estimated costs (EUR m)" in the climate-tracking table) | Cellar, XHTML |
| Recovery and Resilience Scoreboard (Commission) | status, instalment and disbursement date of Spain's milestones and targets; date of the last data refresh | the public, anonymous Qlik Sense app that the scoreboard page reads; same queries as the page's own scripts |
| European Affordable Housing Plan, COM(2025) 1025; Regulation (EU) 2021/241; COM(2025) 310 "NextGenerationEU – The road to 2026" | literal passages, dates | Cellar, XHTML |
| Council recommendations to Spain under the European Semester, 2019–2026 (9 texts) | the operative recommendations on housing | Cellar, found by title search |
| Council documents of 20–25 August 2026 amending the plans of 10 other member states | recitals that name a housing measure | Cellar, PDF |
| planderecuperacion.gob.es (Spanish Government) | 13 dated news pages: the Government's own account of each addendum, of the ICO line and of the payment requests | direct; robots.txt has groups only for Googlebot and Bingbot, so no rule applies to our client |
| lamoncloa.gob.es (Spanish Government) | the official summaries ("Referencia") of the Councils of Ministers of 9 December 2025 and 28 July 2026 | direct; robots.txt allows |
| Prior work | Crossref, OpenAlex, GDELT DOC 2.0 (news), Bing News RSS, ECA special reports, institutional pages | see §6 |

Every scripted request used the User-Agent `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`,
at most one request per second per host (shared clock across processes), robots.txt read
first (RFC 9309), 120-second timeout, and was logged in `work/fetch_log.jsonl`.

Not used, and why:
- **consilium.europa.eu** (Council press releases, register search). Our script read its
  robots.txt first; it disallows every agent not on its list, so no scripted request followed.
  Afterwards, one manual check of the press-release listing with a browser-like client (not
  our User-Agent) returned HTTP 403. We did not try again or try to get round either.
- **EUR-Lex web pages**: they block scripted clients; Cellar serves the same documents.
- **The scoreboard's own CSV export**: there is no plain download; the page builds its export in
  the browser from the same Qlik engine we query.

## 2. Versions and scope (fixed before the diff was run)

**Versions.** A "version" is one Commission proposal for a CID on Spain's plan. Cellar lists
ten, from 16 June 2021 to 7 August 2026 (`data/raw/sparql_spain_rrp_documents.csv`). The
SPARQL query in `scripts/fetch.py` checks that no other proposal exists. Each amending
decision replaces the whole annex, so every version's annex is the full text of the plan's
commitments at that date.

**Scope.** A measure is in scope if its name, description or any of its milestones and
targets mentions social or affordable housing, social or affordable rent, rental housing, public
housing or the Housing Law (regular expression in `scripts/extract.py`, applied to all ten
versions). That gives seven measures. Four are housing measures (**core**):

- C2.I2 construction of social rental housing (grants);
- C2.I7 ICO loan facility for social housing (loans, from 2023);
- C2.R3 Housing Law;
- C2.R7 rental-housing supply reform (loans, from 2023; renamed "Accessibility of housing" in
  December 2025).

C13.I13, the Regional Resilience Fund, lists "social and affordable housing and urban
regeneration" among seven priority areas. We report it as **context**, not in the headline.
C2.I1, C2.I3 and C28.I1 match only through the generic definition of a dwelling ("may include,
where appropriate, social or public housing") and are out of scope. The component-2 summary
sentence that restates the number of dwellings ("construct at least … new dwellings") is
tracked as its own item.

The two equity injections into ICO (C13.I14 and C13.I15, December 2025), which fund the
"España Crece" fund that the Government presents as mainly for housing, are out of scope
under this rule: their CID text names no housing purpose. In December 2025 it cited
"energy efficiency renovation of existing housing stock" as one possible green investment;
in August 2026 the CID text no longer mentions housing. The paper reports this as a fact.

## 3. Extraction

`scripts/cidparse.py` reads the Commission's XHTML: every table row whose first cell is a
milestone/target number and whose second cell is a measure id; and every measure description
from its heading ("Investment 2 (C2.I2) – …") to the next heading. Text is normalised only for
whitespace, soft hyphens and footnote call-outs. Inline tags are removed without adding
spaces, because the Commission's XHTML splits words across `<span>` elements. Quotations
therefore stay literal.

`scripts/extract.py` writes:
- one row per version × in-scope milestone/target (`data/housing_rows.csv`);
- one per version × measure (`data/housing_measures.csv`);
- the literal texts (`data/texts/<version>/<measure>.txt`);
- the recitals that name a housing measure, with the stated reason (`data/reasons.csv`);
- the date of Spain's reasoned request quoted in each proposal (`data/requests.csv`).

Coverage check: the parser finds 415 milestone/target rows in the 2021 annex, whose recitals
announce 416. The missing number is 416, which appears in no table of the 2021 annex.

## 4. The differ and the change categories

`scripts/differ.py` compares two versions of an item word by word and classifies the change.
`tests/test_differ.py` holds 12 tests on literal fragments of target 31, milestone 30 and C2.I7.

| category | rule |
|---|---|
| amount | the multiset of euro amounts in the item changed |
| quantity | the goal or baseline cell changed, or the set of other numbers in the text (dwellings, percentages) changed |
| deadline | the quarter or year cell changed, or a calendar date in the text changed |
| definition | words changed once every number is removed, beyond case, punctuation and one-letter spelling fixes |
| editorial | any other textual change, spacing included («80 %» → «80%», «1.Description» → «1. Description»); every textual change is recorded |
| removed / added | the item exists in only one of the two versions |

An item can carry several categories. `scripts/diffs.py` compares every pair of consecutive
versions and each item's first and last version (`data/diffs.csv`, with the rendered word diff
and both literal texts).

Row L2 of C2.R7 (amendment of the Land Law) was replaced in December 2025 by row L2a (statute of
the public land agency SEPES). We follow the CID's numbering and treat them as two items, one
removed and one added. New items are not counted as changes.

**Base rate** (`scripts/baseline.py`). For the December 2025 amendment (COM(2025) 556 →
COM(2025) 794) and the August 2026 amendment (COM(2026) 257 → COM(2026) 435) we count the words of
every measure description and every milestone/target description present in both versions. A
description that loses more than 30% of its words (kept < 70%) is counted as heavily cut; we
report the share, the median and the rank of each housing item. Word counts measure length,
not meaning. A description longer than 3,000 words in either version (a parser run into a
table) would be excluded; none was.

## 5. Adoption

- **Adoption dates.** For the first nine versions, the date comes from the Commission's own
  later text. Recital 1 of COM(2026) 435 lists the date of every earlier decision. The recitals
  are not error-free, so we cross-checked them: COM(2023) 576, COM(2024) 185 and COM(2024) 592
  call the original decision one «of 6 July 2021» (it is of 13 July 2021), and COM(2025) 794,
  COM(2026) 257 and COM(2026) 435 date Spain's submission of the plan «3 April 2021» (the 2021
  proposal says 30 April 2021). The adoption dates listed in recital 1 agree across all
  successive proposals. For the 2021 version, "Spain's request" is the submission of the plan.
- **Council texts.** For nine of the ten versions, the Council's text prepared for adoption is
  in Cellar. `scripts/council_compare.py` compares it field by field with the Commission's
  text, using pdftotext and a token alignment that tolerates the PDF's column order
  (`data/council_vs_proposal.csv`). Only COM(2025) 794 has no Council text in Cellar.
- **The last version.** No later Commission text exists yet for COM(2026) 435. We record:
  - the Council's ST 12355/26 INIT of 25 August 2026 («of …», i.e. not yet dated);
  - the Spanish Government's statement of 1 October 2026 that the Council adopted it on
    27 August;
  - which version's wording the Commission's scoreboard shows.
  The Commission's Spain page (reforms-investments.ec.europa.eu) lists no adopted decision for
  August 2026, but it lists none for January 2026 either, so its silence is not evidence.

## 6. Prior work

`scripts/prior_work.py` logs each query with its date, URL, HTTP status, number of hits and
the screened titles (`data/prior_work_search.csv`):

- 8 scholarly queries in English and Spanish on Crossref (top 20) and OpenAlex (top 25);
- 12 press queries on GDELT and on Bing News RSS (literal figures such as "15.718 viviendas",
  "17.365 viviendas", "línea ICO", "adenda de cierre");
- greps of institutional pages: ECA, AIReF, Bruegel, Fundación Alternativas, EPRS and the
  Commission;
- the five press articles that Bing returned, fetched and grepped. **Their dates are the
  articles' own datelines** (`datePublished` / `article:published_time`, recorded in the CSV),
  not the feed's `pubDate`, which is in UTC and was a day early for two of them. Two further
  items (elEconomista and El Mundo, syndicated on MSN) could not be read and are cited as
  headlines only.

ECA special reports were located through Cellar (author = ECA, titles mentioning recovery or
housing) and downloaded from eca.europa.eu: 13/2024, 26/2023 and 20/2026. All prior-work
documents are kept in `data/raw/prior/` (git-ignored), so the quotation check runs offline.

## 7. Timing

`data/timeline.csv` lists every dated event used, with its source. The paper presents the dates
in a plain table, with the procedurally relevant deadline (COM(2025) 310: revisions «by the end
of 2025») alongside. We report dates and the order of events and make no claim about intent.

## 8. What could not be done

- **Council adoption of COM(2026) 435.** It could not be confirmed from an EU source. The
  Council's site is closed to our client. Cellar records no adoption event for any of Spain's
  CIDs. No later Commission text yet lists the decision.
- **The adopted text of COM(2025) 794** (adopted 20 January 2026 according to the Commission)
  is not in Cellar. Its wording is the Commission's proposal. The next version, whose Council
  text we do have, repeats it unchanged for every housing item.
- **The Commission's assessment of target 31 and milestone L6** has not been published. Both
  belong to Spain's last payment request (1 October 2026), and the Commission has until
  31 December 2026 to pay.
- **The press search is limited to Bing News RSS.** WebSearch was exhausted, GDELT answered
  HTTP 429 to most queries, and Google News's robots.txt disallows our client. Bing found the
  coverage listed in the paper, §4. Older or paywalled coverage may be missing.
- **AIReF's site disallows our client in robots.txt.** We could not grep its pages.
