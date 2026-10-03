# S18 — What immutable releases protect in GitHub Actions workflows

*EasyxLab · study S18 · data collected 2026-10-03 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s18/paper/](https://easybyte.es/lab/studies/s18/paper/) · [PDF](https://easybyte.es/lab/studies/s18/paper.pdf)

## Abstract

Since 2025-10-28 a GitHub release can be published as *immutable*: its Git tag can no longer be moved
or deleted. GitHub's documentation also tells action authors that a tag they want to keep updating,
such as the major version tag `v1`, must **not** be tied to a release, and suggests they "recommend
that your users specify a major version". A workflow that writes `uses: owner/action@v1` follows that
documented, intended usage, and immutable releases do not protect it. We measured what the mechanism
protects in practice, on 2026-10-03, through the GitHub API only:

- **A**: the top 1,000 repositories by stars among public, non-fork, non-archived repositories
  pushed in the last 90 days (cut-off 29,565 stars);
- **B**: 500 repositories drawn at random (seed 20261003) from the 20,553 such repositories with
  1,000–5,000 stars.

Their default-branch workflows hold 58,690 remote `uses:` references in A and 10,472 in B. Each one
was classified as pinned by commit SHA, by the tag of an immutable release, by a mutable tag, or by a
branch.

**Where the author already publishes immutable releases, almost no reference is protected.** Of the
tag references to actions whose latest release is immutable, 312 of 6,898 (4.5%) point to a protected
tag in A (95% interval 2.8–7.1%, bootstrap over repositories), and 76 of 1,564 (4.9%) in B. The
protected ones are concentrated: one repository holds 68 of the 312, and leaving out any single
repository gives 3.6–4.6%. Almost all the rest are major tags such as `@v7`. For 3,238 of 6,586
(49.2%) of the unprotected references in A (interval 43.2–56.0%), an immutable release tag already
points to the same commit, so switching to it would not change the code that runs.

**Most-used actions.** 28 of 50 (56.0%) of the action repositories used by the most repositories in A
publish their latest release as immutable. First party: 12 of 28 (42.9%) for `actions/*` (yes:
`setup-node`, `setup-python`, `setup-go`, `setup-java`; no: `checkout`, `cache`, `upload-artifact`,
`download-artifact`, `github-script`) and 3 of 6 (50.0%) for `github/*`.

**SHA pinning carries the protection, in a minority of repositories.** Pooled, 32,978 of 58,690 (56.2%)
remote references in A are SHA-pinned (interval 50.7–61.7%) and 4,812 of 10,472 (46.0%) in B
(interval 29.0–60.1%; 37.7% without its largest repository, open-telemetry/opentelemetry-python, which
holds 1,392 references). The typical repository pins few: the median per-repository SHA share is 5.0%
in A and 0.0% in B. Every remote reference written in the workflow files is SHA-pinned in at most 263
of 891 (29.5%) repositories in A, and in 174 of 891 (19.5%) if the 89 that also call local actions we
did not read are left out; in B, at most 65 of 398 (16.3%), or 55 of 398 (13.8%). Immutable tags: 0.6%
of references in A, 0.8% in B.

**Workflow-level dependency locking**, announced on 2026-03-26 with "Public preview 3-6 months", had
not shipped on 2026-10-03: its roadmap items are open, and no changelog entry or workflow-syntax
reference documents it. These figures describe the state before it ships.

**Prior work.** datosh/pinned-actions tracks SHA pinning in the top 10,000 repositories by stars
("only 7%" pin fully, April 2026; 506 of 6,290 repositories using Actions, 8.0%, in its archive) and
added a latest-release immutability check in April 2026; joshjohanning/ensure-immutable-actions
(since 2025-11) checks whether workflow references use immutable releases. Papers measured SHA pinning
at 1–2% of references in 2022; NDSS 2026 found 16.2% of repositories referencing every third-party
action by SHA or by a tag of a verified creator. Our 29.5% differs from datosh's 8.0% mainly by
population (top 1,000 with recent activity, not top 10,000) and date; datosh's own first 1,000 entries
give 100 of 781 (12.8%). As far as we can find, H1 (how many tag references immutable releases protect)
and the 49.2% with an immutable tag at the same commit had not been measured. Paper and sources:
https://easybyte.es/lab/studies/s18/paper/.

**Automation and review.** AI agents ran the study and wrote the text. An independent AI reviewer
checked the work; its findings were applied (`METHOD.md`, Deviations).

**Competing interests.** EasyByte develops attest-lint and may release `scripts/uses_check.py`, the
classifier used here, as a free tool. Unlike ensure-immutable-actions, which suggests SHA pins, it
reports for each movable tag the immutable release tag at the same commit.

## Contents

| path | what |
|---|---|
| `METHOD.md` | population, unit, frozen classification rules, deviations |
| `VERIFICATION.md` | how to recompute and check every headline figure, and what the checks cover |
| `scripts/uses_check.py` | the classifier as a reusable module and CLI: `python3 scripts/uses_check.py .github/workflows` |
| `scripts/00…06_*.py`, `scripts/run.sh` | collection (network) and analysis (offline) |
| `scripts/check_headline.py` | checks the numbers of this abstract (and of the paper, when present) against `data/` |
| `tests/` | tests of the extractor, the ref parser and the classifier |
| `data/repos.csv` | one row per population repository: counts by class, all-SHA, own latest release |
| `data/references.csv` | one row per remote reference from an organisation repository to an organisation action |
| `data/actions.csv` | one row per action repository: latest release, immutable or not, usage in A and B |
| `data/ref_resolution.csv` | for every (organisation action repository, ref): tag, branch, release immutability, immutable tag at the same commit, SHA is a commit |
| `data/metrics.json`, `data/tables.md` | every figure and table |
| `data/frame_queries.csv`, `data/population.json` | every search query with its `total_count`; frame sizes, seed, frame hashes |
| `data/extractor_check.json` | extractor against a full YAML parse of all 12,764 workflow files |
| `data/sources/` | literal excerpts of GitHub's documentation, changelog and roadmap with dates; prior-work search log and figures |

**Personal data.** Repositories and actions owned by individual users carry random pseudonyms whose
key is not published. For their repositories we publish only per-repository counts (no rank, stars,
file, line or SHA); references to their actions are counted, never listed with a repository, ref or
location. Raw API responses (`data/raw/`) are not published.

## Reproduce

```bash
scripts/run.sh            # offline: tests, every figure from data/, headline check (Python >= 3.10, stdlib)
FETCH=1 scripts/run.sh    # new snapshot from the GitHub API (token via `gh auth token`); repositories change daily
```

## Licences

- Code: Apache-2.0. Data and text: CC BY 4.0.
- `data/` holds facts derived from public GitHub repositories through the GitHub API; this study is
  open access. `data/sources/` holds short quotations of GitHub Docs (github/docs, CC BY 4.0), GitHub's
  changelog and blog, zizmor and pinact, and figures recomputed from datosh/pinned-actions (MIT).

---

EasyxLab · a research lab by EasyByte

Cite as: EasyxLab (2026). What immutable releases protect in GitHub Actions workflows. Study S18.
EasyByte Hub S. Coop. Mad. https://github.com/easybytehub/easyxlab
