# S7 — Method

*EasyxLab · study S7 · readings of 2026-10-02 · status: working draft, not peer-reviewed*

## 1. Question and unit

The unit is one **answer**: the text Google's AI Overview (AIO) or AI Mode returned for one Spanish query, issued
for Spain, at one reading. Each query targets one **fact**, a Spanish rule. Answers are judged against the
**consolidated law in the BOE as in force at the moment of the reading**, not against the pages they cite.

## 2. Facts

- **28 facts.** Labour 5, Social Security 8, self-employed 1, housing 3, justice 2, consumer 3, traffic 2,
  mobility 1, invoicing 3. They were chosen from the BOE open-data listing of 2025–2026 state norms, keeping rules
  with a crisp value that a person or small business would search for. Regional rules were excluded.
- **Control.** F05 is the 40-hour week: the 37.5-hour bill did not pass.
- **Conflict-of-interest cap.** At most 5 facts on Verifactu or invoicing; 3 are used (F26–F28).
- **Quotations.** `scripts/fetch_boe.py --from-facts` downloads every BOE text a fact cites (Diario text or
  consolidated text). `scripts/build_facts.py` matches each quotation by regular expression: **55/55 verified**
  (`data/facts.csv`).
- **Status in force (version 2).** `scripts/status_check.py` reads, for each fact's source norms, the BOE document
  page and keeps every later reference from 2025–2026 that the BOE lists: amendments, repeals, annulments by court
  rulings, validations of decree-laws, pending appeals, implementing orders. It also lists every item of the BOE
  issues of 2 October 2026, with the Last-Modified time of each issue's PDF, and tries the issue of 3 October
  (`data/fact_status.json`). `scripts/facts_in_force.py` writes `data/facts_in_force.csv`: one row per fact with
  the rule in force at each reading, the BOE ids, the later references checked, and what changed from version 1.
- **Reading-day timeline (UTC).**
  - BOE no. 244 (ordinary, 2 October): PDF last modified 1 October, 17:42.
  - BOE no. 245 (extraordinary, 2 October): repeals of RDL 26/2026 and RDL 27/2026, PDF last modified 14:59:41.
  - Readings: 19:32–19:38, 23:05–23:11 and 23:42–23:47.
  - BOE of 3 October: not online at 04:17 on 3 October.

  The law was therefore the same at all three readings.
- **What version 1 got wrong.** Version 1 checked only that quotations exist in the original texts:
  - F15 (register annulled by the Supreme Court) and F25 (deadline cut by RDL 7/2026) were wrong;
  - F20–F22 omitted the 12-month adaptation period, and F21 omitted the rewrite of TRLGDCU art. 21.3;
  - F16 was excluded on a false premise: the repeal of RDL 26/2026 was in a file downloaded before reading 1 and was
    missed;
  - F04 (date), F14 (wording) and F28 (detail) needed smaller corrections.

  Details are in `data/facts_in_force.csv`, column `v1_to_v2`.

## 3. Queries

101 Spanish queries, 3–4 per fact, written by the AI agent with and without the year, as questions or keywords
(`data/queries.csv`). None contains the answer. They were fixed before reading 1 and not changed.

## 4. Collection (`scripts/probe.py`)

- **Provider.** Readings were obtained through DataForSEO's commercial SERP API, which queries Google; we did not
  query Google directly. DataForSEO's terms make the customer responsible for the use of SERP data, including "any
  use of SERP data that violates the terms of service or legal rights of the search engine providers" (7.2,
  dataforseo.com/terms-of-service, read on 2026-10-03). We publish only aggregates and extracts of at most 282
  characters.
- **Access.** Authenticated calls with our paid account and the HTTP library's default User-Agent, up to six in
  parallel: 202 per reading, each reading in about six minutes. None was refused.
- **AIO.** `POST /v3/serp/google/organic/live/advanced` with `location_name: Spain` (echoed as location code 2724),
  `language_code: es`, `device: desktop` (echoed `os: windows`, `se_domain: google.com`), `depth: 10` and
  `load_async_ai_overview: true`.
- **AI Mode.** `POST /v3/serp/google/ai_mode/live/advanced` with the same location and language.
- **Readings.** Three on 2 October 2026, 202 requests each, no API errors.
- **Prices.** The price table (`/v3/appendix/user_data`) lists USD 0.002 per SERP request. The observed AIO
  requests cost USD 0.00285–0.00301 because of the asynchronous AI Overview; AI Mode cost USD 0.004 (measured on a
  2-query pilot).
- **Spend.** USD 2.120 in total (`data/spend.json`), within a budget of USD 4.50. No calls were made after reading 3.
- **Storage.** Raw responses and full answer texts stay in `data/raw/`, git-ignored and not redistributed.
- **Client.** `probe.py` uses EasyByte's private client if present, otherwise a minimal stdlib client with
  credentials from the environment.

## 5. Classification

**Rule verdict (script).** `scripts/classify.py` normalises the text: it removes links and citation markers and
thousands separators, and lowercases. It then applies, for each fact, `cur_patterns` (rule in force) and
`old_patterns` (superseded rule) from `data/facts.json`. An old-rule hit counts as history when a past, negation or
hedge marker (`PAST` in the script) sits within 90 characters before it or 40 after it, or inside the hit.
- `current`: the current rule, and no old-rule hit counted as live;
- `mixed`: both, the old rule as if in force;
- `outdated`: only the old rule;
- `not_stated`: an answer, but neither rule;
- `no_answer`: no AI answer for the query.

**Final verdict (AI agent).** An AI agent re-read two sets (`data/review_agent.csv`, with a reason and, for errors,
an extract of at most 300 characters):
- **every** answer the script flagged `outdated` or `mixed` (39);
- **every** answered response of the six facts whose ground truth changed in version 2 or needs judgment (F14, F15,
  F16, F21, F25, F28; 81 more).

The agent added `incorrect`: a fixed date or value that neither the current nor the superseded text contains. For
F28, firm calendar dates for a deadline that runs from an unpublished order are `incorrect`; with the dependency
stated they are `mixed`; labelled as estimates they are `current`.

**False-negative check.** The agent re-read 40 random unflagged answers (seed 20261003) from the facts not fully
re-read (`data/fn_check.csv`).

**Rule freeze: not verifiable.** The folder has no version history. The timestamps (UTC) are:
- reading 1 ended at 19:38:46;
- the first-version second-reader input, already built on revised verdicts, was written at 19:40:22;
- the rule files were modified at 23:48:57–58, after reading 3 ended at 23:47:27;
- they were rewritten again on 3 October (version 2) to encode the corrected facts.

From now on, the rule files below are the ones used for every published figure:

| file | SHA-256 |
|---|---|
| `scripts/classify.py` | `e557d8861d351f2cd6ea408db83950eff9598943ed4c66681b6ff551c9db3f21` |
| `scripts/build_facts.py` | `8e17ec671d226cdd32dffa8b1f4ced771926bc6a970273e546b9ce623e9c0d88` |
| `data/facts.json` | `d6f6e3ef33a08f04eb6a2c0cb6e2ca8a66424a87d037ab370d7f8e631f4f8c29` |
| `data/review_agent.csv` | `707600f5520ed634f264c5e517f0fcaaaf60e61ed3ab3b465a8900422c47d614` |
| `data/domain_types_agent.csv` | `5676e0128ac8f4ddc2c904d789fb7fa596baf4c950f4dff4c316c50e6bd367a4` |
| `scripts/aggregate.py` | `c251e7023097420bfb5c36d4c1006f26a540f765822d29f861f030ba6b2bb9fa` |

## 6. Cited domains

`domain_type()` in `classify.py` matches domain **labels**, not substrings; version 1's substring matching typed
taxfix.com as `x.com` and cuatrecasas.com as `as.com`. The order of checks is: BOE, AEAT, Social Security, other
public bodies (`*.gob.es` and a list), forums and social networks, press, software, other (banks, insurers,
associations, businesses), and advisory (keyword heuristics). 309 domains, those no rule covered plus a few
overrides, were typed by the AI agent from the domain name alone, without visiting them (`data/domain_types_agent.csv`). Shares are computed on the
27 scored facts; F16 references are excluded from the denominators. Social-network URLs are published as domains
only.

## 7. Second reader (version 2)

`scripts/sample_second_reader.py` draws 60 answers in three strata:
- A: 20 of the 30 confirmed errors (seed 31);
- B: all 17 answers flagged by the script and rejected by the agent (seed 32);
- C: 23 of the 502 answers that are unflagged and unchanged (seed 33);
- the item order is shuffled with seed 34.

The reader is a separate AI agent (a Claude Sonnet model; the exact version string is not exposed). It was told to
read one file, holding the corrected fact sheet, the query and the full answer, and to output a verdict and a
20-word note (`data/second_reader_prompt.md`, `data/second_reader.csv`). Blinding rests on that instruction; the
reader ran in the same file tree, and its tool log was not kept. Agreement and Cohen's κ are reported overall, per
stratum and for the binary "wrong or not" (`data/summary.json`). The version-1 subsample (one wrong answer in 54) is
superseded and kept in `private/v1/`.

## 8. Cited pages (`scripts/check_pages.py`)

For each confirmed error (scored facts, 25 answers), and for 40 random correct answers from reading 1 (seed 7), the
script fetches up to 6 cited URLs and applies the same regular expressions. Each page is classed `page_old`,
`page_current`, `page_mixed`, `page_silent` or `fetch_failed`. No person or agent read the pages. They were fetched
on 3 October, not when Google read them.

**Access.** User-Agent `Mozilla/5.0 (compatible; EasyxLab-S7/0.1; research; +https://github.com/easybytehub/easyxlab)`,
one request per distinct URL (163, 44 and 30 in readings 1–3; 206 distinct URLs on 135 hosts), up to 8 in parallel.
Because the analysis mines the text of these pages, a `robots.txt` that disallows them is treated as a
machine-readable reservation against text and data mining (Directive (EU) 2019/790, art. 4(3); Spanish TRLPI,
art. 67). The run of 3 October did not read `robots.txt`. A check on 2026-10-03 found six fetched URLs whose
`robots.txt` disallows all agents (`User-agent: *` / `Disallow: /`): five `www.facebook.com` posts and videos and
one `legatiq.ai` page, in seven rows of `data/page_checks_r*.csv`. Those rows were removed and
`data/error_attribution_r*.csv` was rebuilt from the rest (`check_pages.py --reattribute`, which reproduces the
earlier files byte for byte when nothing is removed). Page text was never stored, so there was no copy to delete.
The published files now hold 268 page rows (186, 51, 31) and 200 distinct URLs on 133 hosts. No answer changed
attribution and no figure changed: of the 25 errors, 14 cite a page stating only the superseded rule, 8 a page
stating both and 3 nothing readable on the rule; 2 of the 40 controls are `in_source` (strict), 23 (loose).
`check_pages.py` now reads each host's `robots.txt` (RFC 9309 matching) and skips the URLs it disallows.

## 9. Headline definitions

- **Scored set:** 27 facts (all except F16), 531 answered responses.
- **F16:** reported separately (`data/f16_case.csv`).
- **Wrong:** outdated, mixed or incorrect, by final verdict. 95 % intervals are Wilson intervals over answers;
  repeated identical answers make them too narrow.

`scripts/check_headline.py` recomputes the headline numbers from the published files and checks that README.md and
paper.md print them.

## 10. Ethics and licences

The queries contain no personal data. Cited pages were fetched with an identifying User-Agent, and their text was
not stored; six pages reserved by `robots.txt` were removed from the analysis (§8).

**Other sources.** BOE texts and issue summaries: `www.boe.es` (open-data API, `/diario_boe/txt.php`,
`/buscar/doc.php`), User-Agent `EasyxLab-S7/0.1` or `/0.2` with the lab's GitHub URL, one-second pauses between
documents; reuse under the BOE's reuse conditions (www.boe.es/informacion/aviso_legal). Prior work: arXiv,
Crossref and Semantic Scholar APIs, User-Agent `EasyxLab-S7/0.1 (research; https://github.com/easybytehub/easyxlab)`,
eight queries each, serial, at least 3 s between arXiv requests as arXiv's API terms ask.

Licences:
- code: Apache-2.0;
- our data and text: CC BY 4.0;
- third-party content (Google's answers, DataForSEO responses): not redistributed. `data/answers.csv` keeps only
  extracts of at most 300 characters for flagged or wrong answers.

## 11. Reproduce

```bash
scripts/run.sh boe        # BOE texts + 55 quotations
scripts/run.sh status     # later references, reading-day issues
scripts/run.sh reading 1  # paid (DataForSEO credentials); ~USD 0.70
scripts/run.sh classify   # needs data/raw/responses/ (not redistributed)
scripts/run.sh pages      # online; skips URLs disallowed by robots.txt (§8)
scripts/run.sh analyse    # tables from published files + headline check
```
