# S4 — Multilingual quality of drug names in Wikidata

EasyxLab · study S4 · snapshot of 2026-10-02 · status: working draft, not peer-reviewed

## Abstract

Wikidata is a CC0 knowledge graph whose multilingual labels are reused by Wikipedia
infoboxes, identifier-translation services and multilingual term search. We froze the
labels of all 3,768 Wikidata items that carry an ATC code (P267) in 20 languages
(34,207 labels), plus 10,823 items with ICD-10/ICD-11 codes. Seven rule-based detectors
flag labels in the wrong script, brand names, salt/parent mismatches, shared labels,
departures from the WHO INN, malformed ICD codes and obsolete ATC codes. A stratified random
sample of 118 flags was reviewed one by one by the study agent, an LLM-based agent (see
`paper.md` §3.1).

Script (0.71 drugs, 0.93 diseases), brand (0.83), shared-label (1.00), ICD-10 format
(13/13) and obsolete-ATC (5/5) flags were mostly correct. INN (0.19), salt/parent (0.26) and
duplicate-ATC (0/4) flags were not, and ICD-11 is undetermined (1/2).

About 0.9% of drug labels are wrong (≈312 of 34,207; 0.5% at the lower 95% CI bounds of
precision). This is a lower bound with respect to recall. Errors concentrate in Urdu (39 per
1,000 labels), Persian (35), Russian (28) and Hindi (25), against 2–4 per 1,000 in the major
Latin-script languages (excluding English). They include:

- brand names (Seroquel, Lyrica, Arcoxia);
- English text and misspellings;
- an unrelated personal name: fa «mohamad» on belimumab;
- labels that name a different substance («pregabalin» on flumequine, «omeprazole» on esomeprazole).

In ICD-10 (P494), 2.5% of values are invalid, ranges excluded; 44 show the same repeated-code
corruption («B2424.» for HIV/AIDS, «I10-I1515.» for hypertension). In ATC, 3.3% of statements
are codes replaced (WHO alterations list) but still ranked normal.

Six of the seven errors from our earlier review (an exploratory check of 59 chronic-treatment
drugs and 34 chronic diseases) were still present; the seventh was only partly fixed.

We propose 135 corrections, reviewed one by one by the study agent, as a QuickStatements
proposal (`corrections.qs`). The proposal **has not been applied**: re-check each `lastrevid`
and discuss at WikiProject Medicine first. **We have not edited Wikidata.**

## Contents

| path | what |
|---|---|
| `paper.md` | paper-style draft (EN) |
| `METHOD.md` | detectors, sampling, precision, reproducibility |
| `scripts/` | `run.sh` + numbered stdlib-only Python steps; `legacy/` = earlier exploratory scripts |
| `data/frozen/` | frozen snapshot: `drugs.jsonl`, `diseases.jsonl`, `disease_p31.json`, `extract_meta.json` (each item with `lastrevid`) |
| `data/reference/` | RxNorm Prescribable name lists, WHO ATC alteration facts, Europe PMC search used for the impact section |
| `data/flags.csv` | every detector flag (1,911) |
| `data/validation_sample.csv`, `data/validation_verdicts.csv`, `data/validation_disease_script.csv` | sample and the study agent's verdicts |
| `data/metrics.json`, `data/tables.md` | rates and precision |
| `corrections.qs`, `corrections.csv` | proposed edits (not applied; for a Wikidata editor to decide) and their justification |

## Reproduce

```bash
scripts/run.sh            # from the frozen snapshot
FREEZE=1 scripts/run.sh   # fresh extraction (new snapshot; recorded verdicts no longer apply)
```

## Licences

- Data derived from Wikidata (`data/frozen/`, `data/flags.csv`, the validation files): **CC0 1.0**.
- RxNorm Prescribable names: US public domain (NLM).
- `data/reference/atc_alterations_codes.json` holds only the code-change facts used for checking. The ATC/DDD
  index itself may not be redistributed, and it is not included.
- Code: to be decided at publication (Apache-2.0 or MIT proposed).

---

EasyxLab · a research lab by [EasyByte](https://easybyte.es)
