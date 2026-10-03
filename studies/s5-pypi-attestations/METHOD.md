# S5 — Method

EasyxLab · study S5 · snapshot of 2026-10-02

This file defines every quantity in [the paper](https://easybyte.es/lab/studies/s5/paper/), lists the sources with the literal text we rely on,
and gives the rules used to classify regressions and publisher changes. Everything here is computed
by the scripts in `scripts/` (Python 3 standard library plus `packaging`).

## 1. Sources and the literal text we rely on

Every source was downloaded on 2026-10-02 by `scripts/00_sources.py`. The matched sentences are
stored in `data/sources/excerpts.json`; the pages themselves are kept in `data/raw/src/`, which is
not published. Quotes below are copied from those files.

| source | what we take from it | literal text |
|---|---|---|
| PEP 740 (Status: Final) | the `provenance` key of the JSON simple API | "When an uploaded file has one or more attestations, the index MAY include a provenance key in the file dictionary for that file." / "The value of the provenance key SHALL be either a JSON string or null." |
| PEP 691 | the JSON form of the simple API | content type `application/vnd.pypi.simple.v1+json` |
| PEP 700 | upload times in the simple API | "Two new "file information" keys, size and upload-time, are added to the files data." |
| docs.pypi.org, *Producing attestations* | when attestations appear | "If you publish to PyPI with pypa/gh-action-pypi-publish (the official PyPA action), attestations are generated and uploaded automatically by default, with no additional configuration necessary." / "PyPI will reject non-Trusted Publisher attestations at upload time." |
| docs.pypi.org, *Integrity API* | publisher identity per file | "Route: GET /integrity/<project>/<version>/<filename>/provenance" / "Provenance objects encapsulate one or more attestations for a given file, bundling them with the identity that produced them." |
| pypa/gh-action-pypi-publish README | default and opt-out | "Generating signed [digital attestations] for all the distribution files and uploading them all together is now on by default for all projects using Trusted Publishing." / "To disable it, set `attestations` as follows: … `attestations: false`" / "Generating and uploading digital attestations currently requires authentication with a [trusted publisher]." Release v1.11.0 (the first with attestations on by default) was published 2024-10-30 (GitHub release API). |
| uv documentation, *Building and publishing a package* | a common uploader | "uv publish does not currently generate attestations; attestations must be created separately before publishing." uv uploads attestations found next to the distributions since 0.9.12 (2025-11-25, changelog: "Collect and upload PEP 740 attestations during `uv publish`"); its GitHub guide shows a separate `astral-sh/attest-action` step since 0.12.3 (2026-08-07). Dates from the uv release notes, checked by the review agent. |
| docs.npmjs.com, *Trusted publishing* | npm provenance by default | "When you publish using trusted publishing from GitHub Actions or GitLab CI/CD, npm automatically generates and publishes provenance attestations for your package." / "This happens by default—you don't need to add the --provenance flag to your publish command." |
| docs.npmjs.com, *Generating provenance statements* | scope and limits | "To publish a package with provenance, you must build your package with a supported cloud CI/CD provider using a cloud-hosted runner." / "When a package in the npm registry has established provenance, it does not guarantee the package has no malicious code." |
| Trail of Bits, *Are we PEP 740 yet?* | comparison | "This site shows the top 360 most-downloaded packages on PyPI showing which have been uploaded with attestations." Snapshot of its `results.json`, last updated "Friday, 02 October 2026, 16:12:11 UTC", is in `data/sources/`. |

## 2. Population and pinned inputs

- **PyPI.** hugovk's *top-pypi-packages*, `top-pypi-packages.min.json`, `last_update` 2026-10-01 12:40:51,
  15,000 rows ranked by 30-day downloads. Fetched by `scripts/01_fetch_inputs.py` from
  `raw.githubusercontent.com/hugovk/top-pypi-packages/e6b5b398c1fc/…` and checked against SHA-256
  `55fee05ed02b628f05350a51780ec436efae39ea0810df5d5419e15b850c7041`. The repository declares no licence,
  so the list is **not** redistributed; `data/compact/projects.csv` keeps only rank and name of each
  project analysed. Files uploaded after 2026-10-01 12:40:51 UTC are ignored, file by file.
- **npm.** `lib/top-download.js` of `npm-high-impact` 1.13.0 (MIT, 2026-06-08; 15,916 packages with at
  least one million weekly downloads, sorted by downloads), fetched from the registry tarball and checked
  against its sha512 integrity; not redistributed. Sample: ranks 1–1,000 plus 500 ranks drawn from
  1,001–15,916 with seed 20261002 (`data/compact/npm_sample.csv`).
- **Trail of Bits** `results.json` (BSD-2-Clause) is regenerated daily and cannot be pinned. The copy
  compared here has `last_update` "Friday, 02 October 2026, 16:12:11 UTC" and SHA-256
  `8ac4020a8873b6c90ce0524e568b5af1e24daa98fe1d4db7e58bc939b13c8347`. It is not redistributed; only
  the agreement counts are published.

## 3. Collection

| step | endpoint | volume |
|---|---|---|
| PyPI file history | `https://pypi.org/simple/<project>/`, `Accept: application/vnd.pypi.simple.v1+json` | 15,000 |
| PyPI publisher | `https://pypi.org/integrity/<project>/<version>/<filename>/provenance` | 8,384 |
| PyPI project URLs | `https://pypi.org/pypi/<project>/<version>/json` (publisher changes only) | small |
| npm versions | `https://registry.npmjs.org/<pkg>`, abbreviated metadata | 1,500 |
| npm provenance | `https://registry.npmjs.org/-/npm/v1/attestations/<pkg>@<version>` | 939 + 1 |
| GitHub | `raw.githubusercontent.com/<repo>/HEAD/<path>`; `github.com/<repo>/commits/HEAD/<path>.atom`; `HEAD https://github.com/<repo>` (redirects) | stops and publisher changes only |

**Rate and identification.** At most 7 requests per second per host to PyPI and npm, and 2–4 per
second to GitHub. Every request in this snapshot (2026-10-02, including the list downloads, source
pages and GitHub reads) carried the User-Agent
`EasyByteLab-research/0.1 (contact: contact@easybyte.es)`, the lab's name at the time. The scripts now
send `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`, and data already collected
was not re-fetched. Some follow-up GitHub reads on 2026-10-03 (Atom feeds with commit ids, Makefiles,
called scripts, redirects of new repositories) were sent with the new User-Agent.

**Terms and robots.txt.** We used only public, unauthenticated, documented API endpoints. PyPI's
`robots.txt` disallows them for crawlers (`Disallow: /simple/`, `Disallow: /pypi/*/json`,
`Disallow: /pypi/*/*/json`, `Disallow: /integrity/`). PyPI's Acceptable Use Policy separates the two:
"Scraping refers to extracting information from PyPI via an automated process, such as a bot or
webcrawler. Scraping does not refer to the collection of information through our API." For API
consumers, docs.pypi.org/api asks: "Set your consumer's User-Agent header to uniquely identify your
requests", and "Try not to make a lot of requests (thousands) in a short amount of time (minutes).
Generally PyPI can handle it, but it's preferred to make requests in serial over a longer amount of
time if possible." Our requests were identified, but at up to 7 per second this snapshot made
thousands of requests within minutes, more than that guidance prefers. The scripts now default to
1 request per second per host. (Policies quoted on 2026-10-03.)

**What is stored.**

- **Raw cache** (`data/raw/`, not published): reduced copies of the responses.
- **Published compact data** (`data/compact/`):
  - `pypi_files.csv.gz`: every file uploaded since 2024-09-01, with project, version, filename,
    upload time, provenance, yanked flag and the Integrity API publisher where queried. No earlier
    file carries provenance; the first attested file is from 2024-10-03.
  - `pypi_old_versions.csv.gz`: for older files, one aggregate row per version where the analysis
    needs it (versions that also have newer files, plus each project's highest stable, highest overall
    and latest-uploaded older version).
  - `projects.csv`, `npm_sample.csv` and `npm_versions.csv.gz`.
  - `evidence.jsonl.gz`: reduced publisher records, npm provenance repository and workflow, commit
    lists (date, commit id, title), GitHub redirect targets and declared project URLs.
- **Self-check.** `01b_export_compact.py` asserts that the analysis reads the same versions from the
  compact data as from the raw cache: 0 mismatches over 15,000 projects.
- **Never stored:** who uploaded a file; npm maintainer fields; commit authors; workflow file
  contents.

## 4. Definitions

- **Version.** Files are grouped by the PEP 440 version parsed from the file name. Versions whose
  files are all yanked are ignored, and versions are ordered by their first upload time.
- **Attested version.** At least one non-yanked file has provenance.
  - **Fully attested:** every non-yanked file has provenance.
  - **`t_att`:** the earliest upload time of an attested file. Attestation is dated by the file, not
    the version: an attested wheel added in 2024-12 to a version first released in 2023 dates from
    2024-12.
- **Latest version.** The highest stable PEP 440 version, or the highest pre-release if a project has
  no stable version. This is the version `pip` selects by default, ignoring Requires-Python and wheel
  availability.
- **Eligible.** The latest version was first uploaded on or after the fixed date **2024-10-01**.
- **Mainline release.** A stable version that was the highest stable version at its `t_att`, so not
  a backport.
- **Stopped (newest).** The newest version by first upload is not attested, and some attested file
  was uploaded before that version: **148**.
- **Stopped (pip-default).** The latest version is not attested, and some *mainline* stable version
  was attested before it: **138**. Projects that only ever attested pre-releases or backports are
  excluded, because the line `pip` installs never had attestations. The variant that includes
  backports gives 140; the old definition, version-dated and with backports, gave 145.
- **Monthly series** (2024-10 to 2026-09), over today's list:
  - versions first uploaded in the month, and how many were attested by month end;
  - projects releasing in the month, and how many released an attested version;
  - projects whose highest stable version at month end was attested by then.
- **Rounding.** Counts are stored as integers. Percentages are computed once, from the counts,
  rounded half-up to one decimal (`09_tables.py`).
- **npm.** A version is attested when `dist.attestations.provenance` is present. Candidates are
  `latest` versions without provenance above an attested version in SemVer order, confirmed when an
  attested version was published before `latest`.

## 5. Publisher changes (PyPI)

- **Identity.** Publisher = (`kind`, `repository`/`project`, `workflow`). Changes in `environment`
  alone are recorded but not counted.
- **Bisection.** For each attested project we read the publisher of the first and last attested
  versions, ordered by `t_att`, using one file per version. Where they differ we bisect. The method
  misses any A→B→A sequence inside an interval, so counts are **lower bounds**.
- **Rules**, first match wins:
  1. same repository → `confirmed: same repository`;
  2. same owner → `confirmed: same owner`;
  3. old and new repositories resolve to the same GitHub repository today, chained moves included →
     `confirmed: same repository after GitHub redirects`;
  4. the new repository, directly or after redirects, equals a GitHub repository declared in the
     `project_urls`/`home_page` of the last attested version (exact slug match) → `consistent with the
     project's own metadata`. This is self-declared, so it is not independent confirmation;
  5. otherwise → `not confirmed by public data`. That is not evidence of anything wrong.

## 6. Causes of stopping (PyPI)

**Evidence.** For each project that stopped, we read the workflow named by the last attestation at
the repository's `HEAD`. One level down, we follow:

- local and remote reusable workflows;
- local composite actions;
- the `Makefile` when a step runs `make <target>`;
- Python scripts run by `python` or `uv run`.

**Markers recorded:**

- `pypa/gh-action-pypi-publish@<ref>`;
- `attestations: false`;
- an API-token `password:` on every PyPA step;
- the action pinned below v1.11;
- other uploaders: `uv publish`, `twine upload`, `poetry`/`hatch`/`flit`/`pdm`/`rye publish`,
  `maturin upload`;
- separate attestation generators: `astral-sh/attest-action`, `actions/attest`,
  `pypi-attestations sign`;
- comments that mention attestations.

If the workflow returns 404, we check whether the repository itself is publicly readable. Commits
touching the workflow since the last attested release come from the GitHub Atom feed (most recent
page).

**Rules**, first match wins:

| class | rule |
|---|---|
| pre-release or secondary pipeline | not a pip-default stop (the latest version is attested, or only pre-releases were attested), or only backport releases were ever attested |
| restored at HEAD | the workflow attests at `HEAD` and a commit about attestations (not `attest-build-provenance`) is dated after the latest release |
| tool or workflow change | the workflow file is gone while its repository is readable; or it uploads with a non-attesting tool and no generator, sets `attestations: false`, uses an API token on every PyPA step, or pins the action below v1.11 |
| isolated release | exactly one unattested release since the last attested one, and the workflow at `HEAD` attests |
| unknown (indeterminate) | everything else: an unreadable repository, an unrecognised upload step, a non-GitHub publisher, or several unattested releases while the workflow still attests |

## 7. Review by the study agent

On 2026-10-02 the study agent, an LLM-based agent, reviewed 57 projects one by one. The draw was not
scripted. The composition, recorded in `data/pypi_review_sample.csv`:

- all 24 projects then in the top 1,000;
- from the rest, by the rule class of the time: 11 tool or workflow changes, 5 indeterminate,
  8 isolated, 8 pre-release and 1 artefact.

An independent AI review agent re-checked the work and showed that one overrule, fastmcp, was wrong.
On 2026-10-03, with the corrected rules, the study agent re-examined the 55 sampled projects still in
the set. It keeps a class different from the rule only where a commit supports it, cited in
`data/pypi_regressions_reviewed.csv` (`evidence_url`). Dates alone do not count as evidence.

## 8. Reproducibility

- **`scripts/run.sh` (default, `OFFLINE=1`).** It recomputes every table and figure from
  `data/compact/` and the published review files. With `OFFLINE=1`, any attempted network request
  raises an error instead of being sent. `00_sources.py` re-extracts the excerpts only from saved
  pages and never overwrites `data/sources/excerpts.json` otherwise. The Trail of Bits comparison is
  recomputed only if the local snapshot exists; otherwise the published counts are kept.
- **`FETCH=1 scripts/run.sh`.** It fetches the pinned inputs (§2), rebuilds `data/raw/` from the
  registries and GitHub (several hours at the default of 1 request per second), then regenerates `data/compact/`. The
  registries and repositories change daily, so a fresh fetch is a new snapshot. The published
  compact data is the reference for this paper.
- **`scripts/10_check_headlines.py`.** It recomputes every headline number from `data/` and asserts
  that README.md and paper.md state it.
