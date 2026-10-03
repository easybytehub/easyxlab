# S18 — Verification

*EasyxLab · study S18 · data collected 2026-10-03 · status: working draft, not peer-reviewed*

How to recompute and check the figures. Everything below runs offline from `data/` with Python ≥ 3.10
and the standard library.

## 1. One command

```bash
scripts/run.sh
```

It runs the tests (`tests/`), recomputes every figure (`scripts/06_analyse.py` → `data/metrics.json`,
`data/tables.md`) and runs `scripts/check_headline.py`.

**What `06_analyse.py` asserts.** (a) Every published reference row (`data/references.csv`: organisation
repositories → organisation actions, 53,694 rows) is re-classified with `uses_check.classify()` from
`data/ref_resolution.csv` and `data/actions.csv`; one differing verdict or immutable alternative stops
the run. (b) For each organisation repository, its rows add up to its counts in `data/repos.csv`.
References from user-owned repositories, and references to user-owned actions, are published only as
counts, so they are not re-classified offline.

**What `check_headline.py` asserts**, on whitespace-normalised text:

1. *Fragments.* 99 sentence fragments (31 for the README abstract, 68 for the paper), recomputed from
   `data/` through `06_analyse.compute()`, must appear with number boundaries: "312 of 6,898" does not
   match inside "1312 of 6,898". They cover every headline number, the verdict table of paper §6.1 row
   by row, and the figures of paper §4, §6 and §7.
2. *Number accounting.* Every number in the README abstract and in the paper's Abstract, §4, §6 and §7
   (code spans, dates, versions, URLs and section numbers excluded) must be a figure the data produce,
   a prior-work figure in `data/sources/prior_work_numbers.json`, or a design constant listed in the
   script (sizes such as 1,000 or 20,000, the seed, small integers up to 12). A changed number outside
   that set fails even when no fragment covers it.
3. The README's yes/no list of `actions/*` must match the data.

Not covered: numbers in the paper's §2 (quotations of other work; listed with sources in
`prior_work_numbers.json`), §3, §8 and the references; small integers and design constants that also
appear elsewhere. The check shares `compute()` with the analysis, so it checks that the texts match the
published data; it is not an independent re-analysis. Without [the paper](https://easybyte.es/lab/studies/s18/paper/) (the public package) it checks
the README only and prints where the paper is.

Mutation test (`work/mutation_test.sh`, scratch copy): changing "312 of 6,898" to "1312 of 6,898", an
interval bound, the seed, NDSS's "16.2%", a table cell, B's H1 interval, "490 repositories" or "95% of
the time" each makes the check exit 1.

## 2. Each headline, by hand

```python
import csv
repos = [r for r in csv.DictReader(open("data/repos.csv")) if r["status"] == "ok"]
acts = list(csv.DictReader(open("data/actions.csv")))
I = lambda r, k: int(r[k])
```

| figure | computation |
|---|---|
| remote references, A / B | sum of `remote` over rows of A → 58,690; B → 10,472 |
| SHA-pinned share, A | sum of `sha` + `sha_unresolvable` over sum of `remote` → 32,978 of 58,690 (56.2%) |
| per-repository median, A | median of (`sha` + `sha_unresolvable`) / `remote` over rows with `remote` > 0 → 5.0% |
| H1, A | sum of `h1_protected` over sum of `h1_n` → 312 of 6,898 (4.5%); B → 76 of 1,564 (4.9%) |
| H1 concentration, A | the largest `h1_protected` → 68; leave-one-row-out range of the ratio → 3.6–4.6% |
| H1b, A | sum of `h1_alt` over sum of (`h1_n` − `h1_protected`) → 3,238 of 6,586 (49.2%) |
| H2 | sort `actions.csv` by `repos_A` (desc), `refs_A` (desc), name; first 50; count `latest_release_immutable == "True"` → 28 of 50; names starting `actions/` with `repos_A > 0` and `exists` → 12 of 28; `github/` → 3 of 6 |
| H3, A (upper bound) | rows with `remote > 0` and `sha + sha_unresolvable == remote` → 263 of 891 (29.5%); of those with `local_actions_unread == 0` → 174 of 891 (19.5%) |
| H3, B | same → 65 of 398 (16.3%); 55 of 398 (13.8%) |
| intervals | reference-level: percentile bootstrap over repositories, 2,000 replicates, seed 20261003 (`cluster_boot()`); repository-level in B: Wilson |

## 3. Checking against GitHub (needs the network and a token)

Rows of organisation repositories and actions can be checked against the live API (releases and tags
change after 2026-10-03):

```bash
gh api repos/actions/setup-node/releases/tags/v7.0.0 --jq .immutable          # true on 2026-10-03
gh api repos/actions/checkout/releases/latest --jq '.tag_name, .immutable'     # v7.0.1, false
python3 scripts/uses_check.py path/to/.github/workflows                        # the classifier itself
gh api repos/github/roadmap/issues/1253 --jq '.title, .state, [.labels[].name]' # lock: open, no "Shipped"
```

Pseudonymised rows cannot be checked against GitHub from the published data; that is their purpose.

## 4. Sources and dates

`data/sources/excerpts.json` lists every quotation in `METHOD.md` and the paper, with its source and
date, and whether it was found verbatim in the saved copy (22 of 22). `scripts/00_sources.py`
re-checks them when the saved pages exist (`data/raw/src/`, not published).
`data/sources/prior_work_numbers.json` holds the prior-work figures; those of datosh/pinned-actions are
recomputed by `scripts/02c_prior_numbers.py` from its published April 2026 archive.

## 5. Population

`data/frame_queries.csv` has every search query, page and `total_count` (242 queries);
`data/population.json` the frame sizes (1,686 and 20,553), the A cut-off (29,565 stars), the seed and
the sha256 of both frame files. The frames list individuals' repositories and are not published, so the
cut-off and the B draw can be re-derived only by re-running the published queries, and the frames
drift daily.
