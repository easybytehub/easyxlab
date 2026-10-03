# S10 — Past the static deadlines: NeTEx on five European access points, checked against open schemas
*EasyxLab · study S10 · snapshot of 2026-10-02 · status: working draft, not peer-reviewed*

*EasyxLab · a research lab by EasyByte*

## Abstract

**The deadlines.** Under the MMTIS regulation (2017/1926 as amended by 2024/490):
- every static-data deadline, where NeTEx applies, has passed (2019–2025);
- the public-transport real-time deadline on the comprehensive TEN-T passed on 1 December 2025;
- the 1 December 2026 date covers parking and vehicle sharing.

The TEL TSI, Regulation (EU) 2026/253, makes CEN/TS 16614-4:2025 (EPIP) mandatory for rail passenger
timetables, with NeTEx milestones in 2027 and 2028.

**What we measured.** On 2026-10-02 we censused 284 NeTEx feeds (639 files) on five national access
points (France, Norway, the Netherlands, Belgium, Luxembourg) and validated 41 of 44 sampled datasets.

**XSD results for the 34 timetable datasets:**
- 8 are fully valid, all French;
- 6 are valid on the part checked, which ranges from 2.4 % to 66 % of their bytes;
- 16 are invalid and 4 were not checked.

Two schema details explain much of this:
- NeTEx 2.0.0 rejects 11 French timetables, 9 of which pass 1.3.2. The reason is that passing times
  now need an `id` and a stop-point reference.
- Ten of eleven Dutch datasets fail 2.0.0 only on references to objects outside the document.

**EPIP.** No dataset passes the archived 2021 EPIP XSD (0 of 36). That XSD predates the 2025
standard, so this says little about conformance to it.

**Consistency checks.**
- One feed is stale (Dutch AVV, 2018).
- Six strings are double-encoded and one character was lost.
- In 11 of 14 French datasets, at least 99 % of ids follow the codification the French profile
  proposes.
- 248,286 internal references lack the `version` the French profile requires, 81 % of them in one
  dataset.

**Our own instrument.** Our linter produced two false positives, now fixed.

We release `netex-lint` as a prototype.

## Layout

| Path | Content |
|---|---|
| `paper.md` | The study (English) |
| `METHOD.md` | Legal quotes, sources, sample rules, schema pins, budgets, threats to validity |
| `RD-MEMO.md` | R&D memo (Spanish) |
| `STATUS.md` | Phases, open items, disk use |
| `scripts/00_prior_work.py`, `00_landscape.py` | Prior-work searches and validator metadata → `data/prior_work.csv`, `data/validator_landscape.csv` |
| `scripts/01_catalogues.py`, `01b_access.py` | Census → `data/catalogue_netex.csv`; access findings → `data/nap_access.csv` |
| `scripts/02_sample.py` | Deterministic sample → `data/sample.csv` |
| `scripts/03_validate.py`, `03b_upgrade_records.py` | Download → XSD + consistency → delete → `data/per_dataset/*.json`; record bookkeeping |
| `scripts/04_aggregate.py` | Aggregates, `data/summary.json`, `data/tables.md` |
| `scripts/05_check_headlines.py` | Recomputes every headline number in README and paper from `data/` and asserts it |
| `scripts/run.sh` | Everything above, plus schema and source retrieval and the prototype tests |
| `prototype/` | `netex-lint`, prototype linter (`RULES.md` cites every rule; 16 tests) |

`work/` (schemas, source texts, raw catalogue responses, temporary downloads) and `.venv/` are not
published. The raw catalogue responses contain third-party contact details.

## Run

```bash
scripts/run.sh                    # hours; ~0.6 GB of downloads, one dataset at a time
SKIP_DOWNLOAD=1 scripts/run.sh    # re-aggregate the published records and assert the headlines
```

The published records were produced over two sessions with up to five parallel workers. The
16 earliest records used 300/400 MB XSD budgets, the rest 150/150 MB; each record stores its
parameters. Catalogues change daily: a fresh run gives a different census and sample.

## How to cite

EasyxLab (2026). *Past the static deadlines: NeTEx on five European access points, checked against
open schemas.* Study S10. EasyByte Hub S. Coop. Mad. https://github.com/easybytehub/easyxlab

## Licence of third-party material

No NeTEx dataset is redistributed. `data/` holds derived results and catalogue metadata without
contact fields. The CC BY 4.0 grant does not cover third-party catalogue metadata (titles,
publisher names) quoted in `data/catalogue_netex.csv`. Source licences, as the catalogues state them:
- FR: Licence Ouverte 2.0, ODbL, or other/unspecified for 11 resources;
- LU: CC0;
- DE (DELFI): CC BY 4.0;
- NO, NL and part of BE: not machine-readable.

NeTEx XSD: GPL-3.0. Profile quotes are short citations of Entur's Nordic NeTEx Profile and the
Profil NeTEx France.

Code: Apache-2.0. Data and text: CC BY 4.0.
