# S20 — What Spain committed to the EU on social housing in its recovery plan, version by version (2021–2026)
*EasyxLab · study S20 · ten versions of the Council Implementing Decision, June 2021 to August 2026, read on 4 October 2026 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s20/paper/](https://easybyte.es/lab/studies/s20/paper/) · [PDF](https://easybyte.es/lab/studies/s20/paper.pdf)

## Abstract

A Council Implementing Decision (CID) fixes what Spain committed to deliver in exchange for
EU recovery funds. The Commission proposed 10 versions of Spain's CID between June 2021 and
August 2026. We extracted every measure, milestone and target dedicated to social and
affordable housing from each version and diffed the literal texts. That covers four housing
measures, ten milestones and targets, and the sentence that restates the number of dwellings;
the Regional Resilience Fund, which lists housing among seven priority areas, is tracked as
context.

**The dwelling target (target 31).** It went from 20,000 to 17,365, then to 15,718: −21.4%,
"because of inflation". Its wording changed in three steps:
- "New dwellings built", whose "construction shall be completed", "as attested by a
  certificate or proof of completion and use of the dwellings by the competent authority";
- "Provision of dwellings", with no completion requirement stated;
- "Construction or rehabilitation of dwellings", still with no completion requirement stated.

**The ICO loan line for social housing.** It went from €4,000 million (2023) to €750 million
(proposal of 17 December 2025), then to €567,854,983 (proposal of 7 August 2026): −85.8%.
Both times the stated reason was "lack of demand".

**Context.** The December 2025 amendment rewrote the whole annex: in 109 of 234 measure
descriptions (46.6%), the text lost more than 30% of its words. The Spanish Government
described it as about 160 measures modified. Within that rewrite, the housing measures lost
wording about as often as the rest: 2 of 4. Two of their deletions:
- the clause "in particular in areas in which social housing is currently insufficient and
  on publicly owned land";
- the Land Law amendment for social housing, replaced by an update of the statute of the
  public land agency (SEPES).

In August 2026 few items lost text, and housing items were among them: the dwelling target
and the ICO milestone are 2 of the 5, out of 480 milestones and targets, that lost more than
30%. That version also dropped the ICO line's climate requirement ("At least 53%").

**Cost estimates.** The Commission's estimate of the dwelling programme's cost went from
€1,000 million to €1,920 million, then to €1,885 million. No Commission text we read explains
the change; in those two amendments, inflation is the only reason stated for the measure. The ECA found the same
pattern, target down and estimated cost up, for a Lithuanian renovation measure.

Between consecutive versions we count 19 item-level changes, 2 of them spacing only, in four
of the nine amendments.

**Adoption.** The Commission's own recitals give the adoption date of 9 of the 10 versions;
the December 2025 version was adopted on 20 January 2026. For the August 2026 proposal:
- the Council's text prepared for adoption is dated 25 August 2026, and its housing text is
  identical to the Commission's;
- the Spanish Government states (1 October 2026) that the Council adopted it on 27 August
  2026;
- the Commission's scoreboard (refreshed 4 October 2026) already shows the August wording,
  with target 31 "Not Assessed".

We found no EU record of that adoption. Where we could compare them, the Council's texts
match the Commission's on every core housing item: 206 of 206 field comparisons.

**Dates** (no inference drawn from their order):
- 4 June 2025: the Commission "urges Member States to undertake such plan revisions as soon as
  possible and, in any event, by the end of 2025".
- 29 November 2025: Spain's request.
- 9 December 2025: its Council of Ministers' approval.
- 16 December 2025: the EU's Affordable Housing Plan.
- 17 December 2025: the Commission's proposal.
- 11 July 2026: Spain's request for the last amendment.
- 7 August 2026: the proposal.
- Target 31 was due in Q2 2026; the cut-off for all milestones was 31 August 2026.

The Commission has not yet assessed target 31, which is part of Spain's last payment request
(1 October 2026).

**What is new.** The Spanish press reported the headline figures from 6 September 2026 (El
Confidencial), including AIReF's €1,301 million against the €1,000 million initially
planned. What we add is narrow:
- the complete literal record of every housing item in all ten versions, classified;
- the stated reasons, recital by recital;
- the adoption trail with the Council's texts;
- a reusable differ.

## Version table (housing items that changed)

| version (proposal) | Spain's request (2021: submission of the plan) | adopted | ICO line (C2.I7) | target 31 (C2.I2) | target 31 wording (name) | C2.I2 cost estimate (SWD) |
|---|---|---|---|---|---|---|
| COM(2021) 322, 16 June 2021 | 30 April 2021 | 13 July 2021 | — | 20,000, Q2 2026 | New dwellings built for social rental or at affordable prices… | €1,000 million |
| COM(2023) 576, 2 October 2023 | 6 June 2023 | 17 October 2023 | €4,000 million | 20,000 | unchanged | €1,000 million |
| COM(2024) 592, 18 December 2024 | 3 December 2024 | 21 January 2025 | €4,000 million | 20,000; "at least EUR 950 000 000 of grants awarded" added | unchanged | — |
| COM(2025) 794, 17 December 2025 | 29 November 2025 | 20 January 2026 | €750 million | 17,365 | Provision of dwellings | €1,920 million |
| COM(2026) 435, 7 August 2026 | 11 July 2026 | 27 August 2026 (Spanish Government; no EU record retrieved) | €567,854,983 | 15,718 | Construction or rehabilitation of dwellings | €1,885 million |

The other five versions (April 2024, April 2025, May 2025, September 2025, May 2026) did not
change these items, except for one spacing fix in May 2025. The August 2026 version also
changed milestone 30 by one space («80 %» became «80%»). The full table, with literal
wording, deadlines, indicators, scoreboard status and stated reasons for every item and
version, is in `data/version_table.csv`.

## Layout

| path | |
|---|---|
| `METHOD.md` | sources, scope rule, extraction, change categories, adoption evidence, what could not be done |
| `scripts/cidparse.py` | parser of CID annexes (Commission XHTML): milestone/target rows and measure descriptions |
| `scripts/differ.py` | word-level differ and change classifier (amount, quantity, deadline, definition, editorial, added/removed) |
| `tests/test_differ.py` | unit tests for the differ (`python3 -m unittest discover -s tests`) |
| `scripts/fetch.py` | downloads every source (Cellar SPARQL and items, Council PDFs, EU frame texts, Spanish Government pages) |
| `scripts/polite.py`, `scripts/robots9309.py` | fetcher: fixed User-Agent, ≤ 1 request/s per host, robots.txt read (RFC 9309), every request logged |
| `scripts/extract.py`, `scripts/diffs.py` | housing items of every version; diffs between consecutive versions and first-to-last |
| `scripts/council_compare.py`, `scripts/adoption.py` | Council text vs Commission text; adoption dates and their sources |
| `scripts/scoreboard.py` | status of the housing milestones on the Commission's scoreboard (public Qlik app) |
| `scripts/baseline.py` | base rate: how much text every measure and milestone lost in the December 2025 and August 2026 amendments |
| `scripts/costs.py`, `scripts/frame.py`, `scripts/others.py` | measure costs from the SWDs; dated EU and Spanish quotations and timeline; other member states' August 2026 amendments |
| `scripts/prior_work.py` | prior-work searches, logged |
| `scripts/analyse.py`, `scripts/check_headlines.py`, `scripts/run.sh` | version table and summary; check of every headline number against `data/`; runner |
| `scripts/check_quotes.py` | checks that every quotation in the README and the paper («…», and "…" in the README) occurs in a downloaded source text (`data/raw/`) |
| `data/version_table.csv` | the version table: one row per version × housing item |
| `data/housing_rows.csv`, `data/housing_measures.csv`, `data/texts/` | literal milestones/targets and measure descriptions, per version |
| `data/diffs.csv` | every change, classified, with old and new literal text |
| `data/reasons.csv`, `data/requests.csv` | stated reasons (recitals) and dates of Spain's requests |
| `data/adoption.csv`, `data/council_vs_proposal.csv` | adoption evidence per version; field-by-field comparison with the Council's texts |
| `data/scoreboard.csv`, `data/scoreboard_versions.csv` | scoreboard rows for the housing measures, and which CID version their wording matches |
| `data/baseline_measures.csv`, `data/baseline_rows.csv`, `data/baseline_summary.json` | words kept by every measure and milestone/target in the last two amendments, and the summary |
| `data/measure_costs.csv` | estimated cost of the housing measures in the Commission's SWDs |
| `data/frame.csv`, `data/timeline.csv` | dated literal quotations (EU housing plan, RRF Regulation, Council recommendations, Spanish Government) and the timeline |
| `data/other_states_aug2026.csv` | recitals of the other member states' August 2026 decisions that name a housing measure |
| `data/prior_work_search.csv` | every prior-work query, with date, status and screened titles |
| `data/summary.json` | headline numbers |
| [paper](https://easybyte.es/lab/studies/s20/paper/) (web) | the paper |
| `data/raw/`, `work/`, `private/` | git-ignored: downloads (including prior-work documents in `data/raw/prior/`), logs, scratch. Never published. |

## How to run

Python ≥ 3.10; standard library, plus `websocket-client` (scoreboard only) and poppler's
`pdftotext` (Council PDFs).

```bash
nohup bash scripts/run.sh fetch > work/fetch.log 2>&1 &   # downloads the sources (~115 MB); resumable
bash scripts/run.sh                                        # tests, extraction, diffs, analysis, headline and quotation checks; offline
bash scripts/run.sh check                                  # only the headline check
```

A new `fetch` reads today's scoreboard and today's search results; the CID texts do not
change.

## Licences

- Code (`scripts/`, `tests/`): Apache-2.0, see [`../../LICENSE`](../../LICENSE).
- Our data and text: CC BY 4.0, see [`../../LICENSE-DATA`](../../LICENSE-DATA).
- Quoted EU texts (Commission proposals and staff working documents, Council documents, the
  RRF Regulation, Council recommendations, the scoreboard): © European Union. Reused under the
  Commission's reuse policy (Decision 2011/833/EU) and the Council's notice on reproduction
  with acknowledgement of the source. Source: EUR-Lex/Cellar and the Council register, as
  cited row by row.
- Quoted Spanish Government statements: planderecuperacion.gob.es, cited with URL and date.
- None of these sources endorses this study.

Cite as: EasyxLab (2026). What Spain committed to the EU on social housing in its recovery
plan, version by version (2021–2026). Study S20. EasyByte Hub S. Coop. Mad.
https://github.com/easybytehub/easyxlab

---
EasyxLab · a research lab by [EasyByte](https://easybyte.es)
