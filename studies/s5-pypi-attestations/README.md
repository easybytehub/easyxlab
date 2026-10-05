# S5 — Who publishes attestations on PyPI and npm — and who stopped?

*EasyxLab · study S5 · snapshot of 2026-10-02 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s5/paper/](https://easybyte.es/lab/studies/s5/paper/) · [PDF](https://easybyte.es/lab/studies/s5/paper.pdf)

## Abstract

PEP 740 attestations let anyone check that a PyPI file was published by a named repository and
workflow (its Trusted Publisher). Not attesting is the norm. We measured, on 2026-10-02:

- the full upload history of the 15,000 most-downloaded PyPI projects (hugovk's list of 2026-10-01);
- the publisher identity of every attested project (PyPI Integrity API);
- a 1,500-package npm sample.

Of the 14,995 projects we could analyse, 11,336 (75.6%) have never uploaded an attested file.

**Adoption.** The latest version is attested for 3,479 of 14,995 projects (23.2%), and for 31.1% of
those whose latest version was first uploaded on or after 2024-10-01. By rank band:

| ranks | latest version attested |
|---|---|
| 1–100 | 59.0% |
| 10,001–15,000 | 20.3% |

Projects whose latest version is attested went from 4.0% (end of November 2024) to 23.2% (end of
September 2026). We agree with Trail of Bits' *Are we PEP 740 yet?* on 359 of its 360 packages.

**Projects that stopped.** 148 projects uploaded an attested file and later released without one.
For 138, the line `pip` installs had attestations and its latest version has none: 3.8% of the
3,659 projects that ever attested. By probable cause:

| cause | projects |
|---|---|
| tool or workflow change | 96 |
| one isolated release | 15 |
| restored after the latest release | 1 |
| unknown | 26 |

In 53 of the tool or workflow changes, the publishing workflow now runs `uv publish` with no
attestation step. Examples, each backed by a commit in [the paper](https://easybyte.es/lab/studies/s5/paper/) §5.3: fastapi, typer, fastmcp and
supabase. A stop removes a guarantee; it does not show that one was broken.

**Publisher changes.** At least 307 attested projects changed publisher. Of the 188 changes that
cross repositories or publisher kinds:

- 160 are confirmed by public data;
- 16 are consistent with the project's own metadata;
- 12, in 5 projects, are not confirmed.

**npm.** 30.8% of the top 1,000 publish provenance; of the 459 packages in the 1,500-package sample that ever did, 4 (0.9%) stopped.

**Prior work.** The closest existing measurement is Trail of Bits' tracker, which covers the top
360 PyPI packages by latest release. This study adds the distribution beyond those 360, the history,
the stops and their probable causes, and the publisher audit ([the paper](https://easybyte.es/lab/studies/s5/paper/) §2).

**Automation and review.** AI agents ran the study and wrote the text. An independent AI reviewer
checked it ([the paper](https://easybyte.es/lab/studies/s5/paper/) §4.1).

**Competing interests:** EasyByte develops attest-lint, an open-source tool that flags the
attestation regressions this study measures; it produced no figure here.

## Contents

| path | what |
|---|---|
| [paper](https://easybyte.es/lab/studies/s5/paper/) (web) | paper-style draft (EN) |
| `METHOD.md` | definitions, literal source text, rules, pinned inputs, reproduction |
| `scripts/` | `run.sh` + numbered Python steps (stdlib + `packaging`); `10_check_headlines.py` asserts every headline number |
| `data/pypi_packages.csv` | one row per PyPI project (rank, latest version, attestation flags, stop flags; no download counts) |
| `data/pypi_monthly.csv`, `data/pypi_aggregates.json` | monthly counts and rank-band counts |
| `data/pypi_regressions.csv`, `data/pypi_regressions_reviewed.csv`, `data/pypi_review_sample.csv` | stops with evidence (workflow markers, commit ids), rule class, agent review with evidence URLs, the reviewed sample |
| `data/pypi_publishers.csv`, `data/pypi_publisher_changes.csv`, `data/pypi_publisher_changes_reviewed.csv` | Integrity API publishers and their changes |
| `data/npm_packages.csv`, `data/npm_aggregates.json`, `data/npm_*_reviewed.csv` | npm sample |
| `data/compact/` | per-file PyPI data since 2024-09-01, older versions aggregated, npm per-version data, reduced evidence |
| `data/metrics.json`, `data/tables.md` | headline figures and tables |
| `data/sources/` | literal excerpts of the PEPs and documentation; prior-work search log |

The request cache (`data/raw/`), the hugovk list, the npm-high-impact list and the Trail of Bits
snapshot are not redistributed. `scripts/01_fetch_inputs.py` fetches the lists at pinned versions.

## Reproduce

```bash
pip install packaging
scripts/run.sh            # offline: recomputes everything from data/compact/, never touches the network
FETCH=1 scripts/run.sh    # rebuilds data/raw/ and data/compact/ from the network (pinned inputs; registries move)
```

## Licences

- Code: Apache-2.0. Data and text: CC BY 4.0 (repository `LICENSE` and `LICENSE-DATA`).
- `data/` holds factual PyPI and npm metadata and our derived results. It contains no copy of
  hugovk/top-pypi-packages (no licence declared), npm-high-impact (MIT) or Trail of Bits' results
  (BSD-2-Clause).

---

EasyxLab · a research lab by EasyByte

Cite as: EasyxLab (2026). Who publishes attestations on PyPI and npm — and who stopped? Study S5.
EasyByte Hub S. Coop. Mad. https://github.com/easybytehub/easyxlab
