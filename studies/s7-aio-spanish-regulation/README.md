# S7 — Do Google's AI Overviews and AI Mode keep up with Spanish rule changes? About one answer in twenty did not
*EasyxLab · study S7 · readings of 2026-10-02 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s7/paper/](https://easybyte.es/lab/studies/s7/paper/) · [PDF](https://easybyte.es/lab/studies/s7/paper.pdf)

## Abstract

We asked Google, from Spain and in Spanish, 101 questions about 28 Spanish rules: 27 that changed in 2025–2026
(minimum wage, contributions, pensions, birth leave, consumer, traffic, housing and invoicing rules) and one
announced change that never happened. Each AI Overview (AIO) and AI Mode answer was judged against the
consolidated law in the Boletín Oficial del Estado as in force on 2 October 2026, not against the pages it cites.
There were three readings that evening (606 responses), collected through a commercial SERP API. One rule, the 2 %
cap on rent updates, was re-imposed on 1 October and repealed on 2 October; we report it apart as a case study.
On the other 27, an AIO appeared for 77–86 % of the queries and AI Mode always answered.

**12 of 240 AIO answers (5.0 %, 95 % CI 2.9–8.5 %) and 13 of 291 AI Mode answers (4.5 %, CI 2.6–7.5 %) gave a
superseded rule as current, mixed it with the current one, or stated a fixed date the law does not contain.** Twenty
of the 25 errors concern three rules that moved in 2026: the state register for short-term lets, which the Supreme
Court annulled in May–June, still presented as mandatory; the workplace mobility-plan deadline, which a decree-law
cut from 24 to 12 months, given as December 2027; and B2B e-invoicing, given calendar dates although its deadlines
run from an order not yet published. In the rent-cap case study, 5 of 23 answers, 4 of them AI Mode, presented the repealed
2 % cap as law.

The BOE was cited in 5.4 % of AIO answers and 15.8 % of AI Mode answers. Forums and social networks made up 13.2 %
of AIO references. A regex script flagged 31 answers (16 AIO, 15 AI Mode); an AI agent re-read every flag and every answer of the six
facts whose ground truth we corrected. A blind second AI reader agreed on whether an answer was wrong with κ 0.86
(κ 0.76 over all categories). In a random sample of unflagged answers, the agent found 0 of 40 missed errors.

Our own first fact sheet had the same failure. Checking quotations in the original BOE texts missed a Supreme
Court annulment and a decree-law amendment published months earlier, plus a transitional period.

## Headline table (27 scored facts, three readings pooled)

| surface | answered | current | mixed | outdated | incorrect (fixed date) | not stated | wrong (95 % CI) |
|---|---|---|---|---|---|---|---|
| AI Overview | 240 | 213 | 4 | 5 | 3 | 15 | 12 (5.0 %, 2.9–8.5 %) |
| AI Mode | 291 | 267 | 4 | 7 | 2 | 11 | 13 (4.5 %, 2.6–7.5 %) |

An earlier draft reported 4 of 240 and 0 of 291. It was wrong because three fact sheets missed later changes in the
law and one exclusion rested on a misread repeal ([the paper](https://easybyte.es/lab/studies/s7/paper/) §3 and §5.2; `private/REVIEW.md` is the adversarial
review that found it).

## Contents

| file | |
|---|---|
| [paper](https://easybyte.es/lab/studies/s7/paper/) (web) | paper-style draft (EN) |
| `METHOD.md` | facts, status checks, queries, collection, rules (with SHA-256), review, second reader, ethics |
| `data/facts.json`, `data/facts.csv`, `data/facts_in_force.csv`, `data/fact_status.json` | facts, BOE quotations (55/55 verified), rule in force at each reading, later amendments/annulments listed by the BOE |
| `data/queries.csv` | the 101 queries |
| `data/answers.csv` | one row per response: ids, query, surface, reading, presence, regex verdict, final verdict, short extract (≤ 300 characters) for flagged or wrong answers |
| `data/citations.csv` | cited domain, type and URL (social-network paths withheld) |
| `data/review_agent.csv`, `data/fn_check.csv` | the AI agent's re-reading of 120 answers; the 40-answer false-negative check |
| `data/second_reader_sample.csv`, `data/second_reader.csv`, `data/second_reader_prompt.md` | blind second reader: strata, verdicts, prompt |
| `data/page_checks_r*.csv`, `data/error_attribution_r*.csv` | cited pages of wrong answers and controls, checked by script; six pages reserved by `robots.txt` removed (`METHOD.md` §8) |
| `data/summary.json` and `by_*.csv`, `citation_types.csv`, `stability.csv`, `f16_case.csv` | all tables |
| `data/spend.json` | DataForSEO ledger (USD 2.120) |
| `scripts/run.sh` | `boe`, `status`, `reading N`, `classify`, `pages`, `analyse`; `scripts/check_headline.py` asserts every headline number |
| `data/raw/`, `private/` | git-ignored: full answer texts, raw API responses, BOE downloads, logs. Not redistributed. |

## Automation and review

The study was run by AI agents: choosing and verifying the facts, writing the queries, collecting, writing the
regex rules, re-reading flagged answers, typing cited domains and drafting. The second reader was a separate AI agent
(a Claude Sonnet model), blind to all labels. An independent AI agent reviewed the first draft adversarially
(`private/REVIEW.md`); its findings were applied in this version ([the paper](https://easybyte.es/lab/studies/s7/paper/) §9).

## Competing interests

None related to Google or DataForSEO. EasyByte Hub S. Coop. Mad. sells Verifactu-related software and services, and
publishes Spanish legal and tax content on its own website, which competes for some of the same searches. Invoicing
facts were therefore capped at 5 (3 used), and results are also given without them: 8 of 210 AIO and 7 of 258 AI
Mode answers wrong. EasyByte's domains were never cited.

## Licences

- Code (`scripts/`): Apache-2.0.
- Our data and text (`data/` except as below, `*.md`): CC BY 4.0.
- Third-party content is not redistributed: Google's answer texts and DataForSEO responses stay in `data/raw/`
  (git-ignored). `data/answers.csv` carries only short extracts of flagged or wrong answers, quoted as evidence for
  the finding. BOE texts are public and can be re-downloaded with `scripts/run.sh boe`.

Cite as: EasyxLab (2026). Do Google's AI Overviews and AI Mode keep up with Spanish rule changes? Study S7.
EasyByte Hub S. Coop. Mad. https://github.com/easybytehub/easyxlab

---
EasyxLab · a research lab by [EasyByte](https://easybyte.es)
