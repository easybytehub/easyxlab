# METHOD — S4 Multilingual quality of drug names in Wikidata

## 1. Population and snapshot

| set | definition | n |
|---|---|---:|
| Drugs | items with ≥1 ATC statement (P267), any rank | 3,768 (4,459 ATC statements; 363 items hold only class-level codes) |
| ICD items | items with ICD-10 (P494) or ICD-11 MMS (P7329), any rank | 10,823 (5,536 ICD-10 and 8,193 ICD-11 values) |
| Diseases (for label analysis) | ICD items whose P31 is a disease-like class (type of disease, rare disease, symptom, syndrome…) | 5,212 |
| Chronic subset | 34 chronic diseases named in the earlier review, resolved by English label (highest sitelink count) | 29 resolved (5 names no longer match any English label exactly) |

We excluded 799 taxa (Latin binomials are correct in every language), 161 Wikimedia templates and
categories, and 4,651 other items from the disease-label analysis. The other items are mostly
anatomy carrying ICD-11 extension codes. All ICD items are kept for the code-format detector (f).

Languages: en es fr de it pt pl ru uk tr ar fa ur hi bn zh ja ko sw am (+ `mul` stored for context).

- **Extraction** used the Wikidata Query Service, `https://query.wikidata.org/sparql`. Each request
  sent the User-Agent `EasyByteLab-research/0.1 (contact: contact@easybyte.es)` and was a POST. There
  was a 1 s pause between queries. On HTTP 429/503 the client waits for `Retry-After` and tries at most 5 times.
- **Load**: 101 queries in total, run on 2026-10-02 between 15:24 and 15:29 UTC. The service returned no 429 responses.
- **Terms**: `query.wikidata.org/robots.txt` disallows `/sparql` for crawlers (`User-agent: *`, `Disallow: /sparql`). The Wikidata Query Service is an API meant for programs, and its terms are Wikimedia's User-Agent policy ("Scripts should use an informative User-Agent string with contact information, or they may be blocked without notice") and the service limits ("One client (user agent + IP) is allowed 60 seconds of processing time each 60 seconds"; "access to the service is limited to 5 parallel queries per IP"). Policies quoted on 2026-10-03. Our queries were serial, one at a time with a 1 s pause, under that User-Agent with a contact address.
- **Fields stored per item**: `lastrevid` (schema:version), `dateModified`, sitelink count, ATC codes
  with rank and end date, labels, aliases, P2275 (WHO INN, non-deprecated), P31/P279, and the titles
  of the item's Wikipedia sitelinks in the 20 languages. The dataset is therefore pinned to exact
  revisions. Maximum lastrevid: 2552201749.

## 2. Reference sources (`scripts/02_reference_sources.py`)

- **RxNorm Prescribable subset**, from the RxNav `REST/Prescribe/allconcepts.json` endpoint with
  `tty` = BN, IN, PIN and MIN. Brand names (BN) that also appear as an ingredient name (IN/PIN/MIN)
  or are shorter than 4 characters are removed, leaving 4,125 brand terms.
- **DrugBank Open Data Vocabulary**: the download URL returned HTTP 403 without an account, so this
  source was not used.
- **WHO ATC alterations list (cumulative)**, from `atcddd.fhi.no/atc_ddd_alterations__cumulative/atc_alterations/`:
  355 rows of (previous code, substance, new code, year, note). Only these facts are stored.

## 3. Detectors (`scripts/03_detect.py`) — one explicit rule each

| id | subtype | rule |
|---|---|---|
| a | `a_latin` / `a_other` | label in ru/uk/ar/fa/ur/hi/bn/zh/ja/ko/am has **no letter of the expected script** (Unicode blocks: Cyrillic; Arabic incl. presentation forms; Devanagari; Bengali; Han; Han+Kana for ja; Hangul+Han for ko; Ethiopic) and only Latin letters (`a_latin`) or another script (`a_other`) |
| a | `a_nonlatin` | label in en/es/fr/de/it/pt/pl/tr/sw contains Cyrillic, Arabic, CJK, Indic or Ethiopic letters (Greek allowed: α, β) |
| a | `a_devcode` (excluded) | label matches `^[A-Z]{1,6}[- ]?\d{2,}` (development code, language-neutral) |
| a | `a_mixed` (informational) | expected script present **and** a Latin run of ≥3 letters |
| b | `b_rxnorm_bn` | normalised label (NFKC, casefold, collapsed spaces) equals an RxNorm Prescribable brand name that is not an ingredient name and not the item's own English label or INN |
| c | `c_salt_on_parent` | English label has no salt/ester term (substring match over a Latin lexicon plus parent acids: hydrochloric, phosphoric…), but the target label has one. Terms are matched as whole words in Latin-script languages, as substrings in German and in the per-language lexicons for ru, uk, ar, fa, ur, hi, bn, zh, ja, ko and am |
| c | `c_parent_on_salt` | English label has a whole-word salt/ester term, and the target label has none, even under loose substring matching |
| c | exclusion | items whose English label consists only of inorganic tokens (element, inorganic anion, roman numeral), e.g. zinc sulfate, potassium, borax |
| d | `d_diff_en` / `d_same_en` | the same normalised label, in the same language, on ≥2 drug items |
| e | `e_typographic` / `e_contains` / `e_different` | en/fr/es (plus ru/ar/zh) label ≠ every same-language P2275 value after normalisation. Subtypes, in order: equal after removing accents, hyphens and spaces (`e_typographic`); one contains the other (`e_contains`); otherwise `e_different` |
| f | `f_doubled` | ICD-10 value with a repeated code part: `[A-Z](\d{2}(\.\d{1,2})?)\1\.?` (e.g. `B2424.`, `J09.009.0`) |
| f | `f_range` (informational) | value fails Wikidata's own P494 regex `[A-Z]\d{2}(\.\d{1,2})?` but is a clean block range (`I10-I15`) |
| f | `f_cm` / `f_corrupt` | fails the P494 regex and looks like an extended code (`[A-Z]\d{2}\.?[0-9A-Z]{1,4}`), or anything else |
| f | `f_icd11` | P7329 value fails Wikidata's ICD-11 regex (from the property's P1793 constraint) |
| g | `g_format` | P267 value fails Wikidata's ATC regex `[ABCDGHJLMNPRSV]([0-9][0-9]([A-Z]([A-Z]([0-9][0-9])?)?)?)?` |
| g | `g_obsolete` / `g_obsolete_split` | non-deprecated code without an end date appears as a "previous" code in the WHO alterations list and never as a "new" code. `_split` is used when the WHO note says the change was partial ("split", "only") |
| g | `g_dup` | the same 7-character ATC code, non-deprecated, appears on ≥2 items |

Before the sample was drawn, the detectors were changed once, after looking at unsampled
examples. The changes were case-insensitive matching in the salt lexicons, German compounds, the
inorganic exclusion, separating taxa and templates from diseases, and requiring ≥2 digits in the
doubled-code regex. They were not changed after the validation sample was drawn. Known failure
modes found during review, such as «استات» inside «سیمواستاتین» or «戊酸» inside «丙戊酸», remain
in the measured precision.

## 4. Validation (`scripts/04_sample.py`, `data/validation_*.csv`)

- **Stratified random sample**, one RNG per stratum seeded `"20261002-<subtype>"`, giving 103 flags
  for detectors a–g. In addition, 15 disease-label script flags were drawn with the seed
  `"20261002-disease_a"`. Informational subtypes (`a_mixed`, `a_devcode`, `f_range`) were not sampled.
- **Verdicts.** One automated reviewer — the LLM-based study agent that also wrote the detectors, without blinding — gave each flag a verdict, using the item's other
  labels, its sitelink titles and its INNs:
  - **TP** — the flag points at a real error. For d, the group contains at least one wrong label or the items are duplicates. Flags that reveal a real error of a different type count as TP and are noted.
  - **FP** — the value is correct or an accepted variant (USAN/BAN, stereodescriptor, common name, international acronym or code name).
  - **DOUBT** — cannot be settled from the available sources.
- **Rule for c**: when the salt item is the only item carrying the drug's ATC code, so that it is
  in practice the drug item, a label naming the parent is acceptable (FP).
- **Precision** = TP/(TP+FP), with a Wilson 95% CI. A conservative variant counts DOUBT as FP.
- **Error estimates.** The per-language estimate is Σ over detectors a, b, c and e of (flags ×
  precision). d (ambiguity) is reported separately. These are **lower bounds on the error count**:
  recall was not measured.

## 5. Corrections (`data/corrections_reviewed.csv` → `scripts/06_corrections.py`)

- **Selection.** Only corrections reviewed one by one by the study agent and backed by a verifiable source are included. Each new
  label comes either from the title of the same item's Wikipedia sitelink in that language or from
  the item's own P2275 INN. ICD repairs are deterministic undoings of the code doubling, each checked
  against the item. New ATC codes come from the WHO alterations list.
- **Output.** The script checks every old value against the frozen snapshot and records the
  `lastrevid` it was reviewed against. It writes QuickStatements V1: `Lxx` for labels, a `-` removal
  followed by an addition for ICD values (packed lists become separate statements), and an addition
  with S854 for ATC codes. The removal drops the original statement's references and qualifiers,
  and the `.qs` header says so. Repairs whose result is a block range (still invalid under P494's
  constraint), the warfarin fr label (no sitelink or P2275 support), rank changes, merges and the
  ATCvet clean-up are listed as manual actions for a Wikidata editor.
- Nothing was sent to Wikidata.

## 6. Limitations (summary; see paper.md §6)

- **Precision only; recall is unknown.** For example, brands written in non-Latin scripts and
  non-US brands (Arcoxia, Selexid) are invisible to detector b, though several were caught by a.
- **A single automated reviewer**: all verdicts and corrections come from the LLM-based agent that also wrote the detectors, without blinding.
- **Small strata**: the confidence intervals are wide.
- **Spot checks only**: Urdu, Hindi, Bengali, Korean and Persian labels were judged against the
  sitelink titles and general knowledge, without a native-speaker review.
- **Narrow INN coverage**: P2275 exists on 1,271 items in English and on ≤35 items in fr/es/ru/ar/zh, so detector e mostly measures English.
- **ICD-10 means WHO ICD-10**: extended codes such as ICD-10-CM or ICD-10-NA count as invalid in P494 by design.
