# S18 — Method

*EasyxLab · study S18 · data collected 2026-10-03 · status: working draft, not peer-reviewed*

This file defines the population, the unit of analysis, every classification rule and every
headline quantity. Sections 1–5 were written and frozen (sha256 and time in the private status file)
before the main collection; anything changed afterwards is listed in section 9 as a deviation, with
its reason.

## 1. Question

GitHub made *immutable releases* generally available on 2025-10-28: the Git tag of an immutable
release cannot be moved or deleted. GitHub's documentation for action authors also says that a tag
that should stay updatable (a major version tag such as `v1`) must **not** be tied to a release.
So in a workflow, `uses: owner/action@v1.2.3` is protected when `v1.2.3` is an immutable release,
and `uses: owner/action@v1` is not, by design. We measure what the mechanism protects in the
workflows of popular public repositories on the collection date.

## 2. Population

Two populations, both drawn with the GitHub REST search API (`GET /search/repositories`) on
2026-10-03, with the qualifiers

    pushed:>=2026-07-05 archived:false fork:false is:public

(2026-07-05 is 90 days before the collection date). The search API returns at most 1,000 results per
query, so each frame is enumerated in star-range slices that each return fewer than 1,000 results
(`sort=stars&order=desc&per_page=100`); every query, page and `total_count` is logged in
`data/frame_queries.csv`.

- **A, top 1,000.** Frame: all repositories with `stars:>=20000` and the qualifiers. Population: the
  first 1,000 by star count, ties broken by ascending repository id.
- **B, random 1k–5k.** Frame: all repositories with `stars:1000..5000` and the qualifiers. Population:
  500 repositories drawn without replacement with Python's `random.Random(20261003).sample()` from
  the frame sorted by repository id.

Forks and archived repositories are excluded by the qualifiers; a repository that is a fork, is
archived or no longer resolves when its workflows are read is excluded and counted.

## 3. Unit and collection

- **Workflow files**: every blob directly in `.github/workflows/` whose name ends in `.yml` or `.yaml`,
  at the default branch (`HEAD`), read with one GraphQL query per batch of repositories
  (`object(expression: "HEAD:.github/workflows")`). Subdirectories are not read (Actions does not run
  workflows from them). Composite actions defined inside the repository are out of scope.
- **References**: every `uses:` value in those files, extracted by `scripts/uses_check.py`
  (`extract_uses`: YAML-aware line scanner that skips comments and block scalars such as `run: |`).
  The extractor is cross-checked against a full YAML parse (PyYAML) of every file; disagreements are
  reported.
- **Remote reference**: a value of the form `owner/repo[/path]@ref`. A remote reference whose path
  ends in `.github/workflows/<file>.yml|yaml` is a *reusable workflow*; any other is an *action*.
  Not remote (excluded from all shares, counted): local (`./…`), `docker://…`, values containing an
  expression (`${{`), and values without `@`.
- **Action repository**: `owner/repo` of a remote reference, case-insensitive. For each one, one
  GraphQL query (batched) reads: `latestRelease { tagName immutable }`; the 100 most recent releases
  (`tagName immutable isDraft tagCommit`); and, for every distinct non-SHA ref used against it,
  `ref(refs/tags/<ref>)` (peeled to the commit), `ref(refs/heads/<ref>)` and `release(tagName: <ref>)`.
  The query text is `build_repo_query()` in `scripts/uses_check.py`.
- **Population repositories**: the same queries also read the repository's own latest release
  (`immutable` and asset names) for the secondary metrics.

All requests go to `api.github.com` (REST and GraphQL) with an authenticated token, at most one
request per second (search: one per 2.2 s), User-Agent
`EasyxLab-research/0.1 (+https://easybyte.es/lab/; contact@easybyte.es)`, after reading
`https://api.github.com/robots.txt` (404, no restrictions). No github.com HTML page is fetched.

## 4. Classification of a remote reference (frozen rules)

Implemented by `classify()` in `scripts/uses_check.py`; tests in `tests/`.

1. **sha**: the ref is 40 hexadecimal characters (case-insensitive). Not checked against the
   repository.
2. If the action repository does not resolve: **unresolved**.
3. If the ref exists as a tag (`refs/tags/<ref>`):
   - **immutable-tag** (protected) if `release(tagName: <ref>)` exists, is not a draft and has
     `immutable: true`;
   - otherwise **mutable-tag**, with its *form*: `major` (`v?N`), `minor` (`v?N.N`), `full`
     (`v?N.N.N` with optional `-`/`+` suffix) or `other`.
   - For a mutable tag, the *immutable alternative* is the immutable release (among the 100 most
     recent releases and the release of the ref itself) whose tag points to the same commit as the
     ref; if several, the highest version.
4. Else, if the ref exists as a branch: **branch**.
5. Else: **unresolved** (includes short SHAs, which Actions does not resolve).

A ref that names both a tag and a branch is classified as a tag and counted as *ambiguous*.

**Action author publishes immutable releases** (*immutable publisher*): the action repository's
`latestRelease` has `immutable: true` on the collection date. Sensitivity variant: any of its 100
most recent releases, or the release of any ref used against it, is immutable.

**First party**: the action repository owner is `actions` or `github`.

## 5. Headline quantities (frozen)

Computed separately for A and for B (the two populations are never pooled).

- **H1, protection where it is available.** Among references with verdict immutable-tag or
  mutable-tag whose action repository is an immutable publisher: the number with verdict
  immutable-tag, as "X of N (p%)".
- **H1b.** Among the mutable-tag references of H1: the number that have an immutable alternative at
  the same commit.
- **H2, most-used actions.** The 50 action repositories referenced by the most population-A
  repositories (ties: more references, then name): how many are immutable publishers. Also for every
  first-party action repository referenced in A, and separately for `actions/*` and `github/*`.
- **H3, pin everything.** Among repositories with at least one remote reference: the number whose
  remote references are all `sha`. Variant: all remote references to non-first-party repositories
  are `sha` (among repositories with at least one such reference).
- **Distribution** of all remote references by verdict and form.
- **Secondary**: population repositories whose own latest release is immutable; whose latest release
  has an SBOM-like asset (asset name matching, case-insensitive,
  `sbom|\.spdx|spdx\.json|\.cdx\.|cyclonedx|bom\.json|bom\.xml`); SHA pins that carry a version
  comment; reusable-workflow references.

Intervals: for B (a simple random sample of repositories) and for reference-level shares in both
populations, 95 % intervals from a percentile bootstrap that resamples repositories (2,000
replicates, seed 20261003), because references are clustered within repositories. A is a census of
its defined frame; its intervals describe variation across repositories, not sampling error.

## 6. Anonymisation and publication

- Published per-repository and per-reference data name a repository only if its owner is an
  organisation. Repositories owned by individual users — population repositories and action
  repositories alike — are replaced by stable pseudonyms (`user-repo-A0001`, `user-action-0001`, …).
  Workflow file names are replaced by an index.
- Aggregate tables name organisations' action repositories (for example, which popular actions
  publish immutable releases).
- Raw API responses (workflow texts, search results) stay in `data/raw/`, which is not published.

## 7. Fairness

GitHub's documentation tells action authors to keep major version tags movable and not to tie them to
a release. A workflow that uses `@v4` follows the documented, intended usage. The study measures what
the mechanism protects; it does not grade projects, and it does not call any project negligent.

## 8. Instruments and versions

Python 3.14 standard library for collection and analysis; `pyyaml` 6.0.2 only for the extractor
cross-check; `pypdf` 5.1.0 only to read prior-work PDFs. GitHub REST API version `2022-11-28` and the
GraphQL API as served on 2026-10-03.

## 9. Deviations after the freeze

(none yet)

## Deviations (appended after the freeze)

Everything above this heading is the text frozen at 2026-10-03T11:30:00Z, byte for byte (sha256
`0fceab6cd6fc074a053ba7357ee3fb75d1216860cd250899c1d3109fa31b8165`); section 9 is kept as it was frozen.
The deviations below were made afterwards, all on 2026-10-03.

1. **Extractor, three fixes** (classification rules unchanged). The cross-check with PyYAML
   (section 3) disagreed on 42 files. We fixed three causes in `extract_uses()`/`parse_uses()`:
   (a) YAML anchors on a `uses:` value (`uses: &co actions/checkout@v4`) and aliases to a scalar
   anchored in the same file (`uses: *co`) are resolved;
   (b) a value written on the line after `uses:` is read;
   (c) values starting with `$/`, GitHub's *self-repository* syntax (changelog of 2026-07-30: "A
   uses: value that starts with $/ resolves to your workflow's own repository at the exact commit
   that is running"), are a separate not-remote kind (`self`) instead of `invalid`.
   Effect: remote references 58,678 → 58,690 in A and 10,460 → 10,472 in B; SHA-pinned 32,966 →
   32,978 in A; H3 in A 262 of 890 → 263 of 891. H1, H1b and H2 did not change.
2. **Cross-check walker.** The PyYAML side of the cross-check now counts each written mapping once
   (an aliased step list is not counted twice) and descends into nested step lists such as
   `parallel:` (steps run in parallel, changelog of 2026-06-25). After both changes, 12,760 of the
   12,761 parsable files agree; 3 files are not parsable by PyYAML; the one remaining file has 2
   `uses:` values written as folded block scalars, which the extractor skips (`data/extractor_check.json`).
3. **Collection procedure.** To shorten the collection, steps 3 and 4 ran with three worker threads;
   request *starts* to `api.github.com` stayed at most one per second (a shared, locked pacer in
   `scripts/common.py`). The on-disk response cache was switched off after it duplicated the search
   pages (it held no data the study uses).
4. **Re-query of new refs.** `04_actions.py` re-queries an action repository when fix 1 produced refs
   for it that had not been resolved; no new refs appeared.
5. **Redirected action repositories and first party.** 37 written names reach their repository through
   a rename or transfer redirect, and the name as written can carry a former personal owner. *First
   party* is read from the current owner everywhere: `github/issue-metrics`, now
   `github-community-projects/issue-metrics`, is no longer first party (`github/*` 4 of 7 → 3 of 6; all
   first party 16 of 35 → 15 of 34). Redirected names are now merged into one repository (item 8).
6. **The CLI** (`uses_check.py` run on its own) sends its own User-Agent,
   `EasyxLab-uses-check/0.1 (+https://easybyte.es/lab/)`; it was run once on a five-line demo
   workflow and produced no data for the study.

## Deviations made after the independent review (2026-10-03)

7. **Pseudonymisation (review B1).** The first version leaked identities of individuals' repositories
   (star rank next to the pseudonym, pseudonyms numbered in rank order or by an unsalted hash, full SHAs
   and file/line locations of references to individuals' actions). Now: pseudonyms are drawn with a
   system random generator and the key stays in `data/raw/` (not published); user-owned population
   repositories have no rank and no star band, and `data/references.csv` lists only references from
   organisation repositories to organisation actions; everything else is published as counts per
   repository (`data/repos.csv`) or per pseudonymised action (`data/actions.csv`, without release tag or
   release count). Re-identification attempts on 10 cases (rank lookup, SHA lookup, location in a named
   repository) all fail. Figures unchanged.
8. **Redirects merged (review m3).** Names that redirect to the same repository are one action
   repository (1,453 written names → 1,435 repositories, 1,427 resolved). A: 1,236 → 1,221 resolved
   action repositories, 159 → 154 immutable publishers; third party 144 of 1,202 → 139 of 1,187. H1, H2
   and the top-50 list unchanged.
9. **SHA pins resolved (review m5).** New step `04b_shas.py` asks GitHub whether each of the 1,881
   distinct (action repository, SHA) pins is a commit; a new verdict `sha-unresolvable` (deleted commit,
   annotated-tag object id, vanished repository) counts as SHA-pinned in every share. 110 references in
   A and 6 in B. No headline changed.
10. **H3 is an upper bound (review M3).** Local references to anything other than a workflow file in
    `.github/workflows/` are counted (`local_actions_unread`); their own `uses:` were not read. H3 is
    reported as "at most", with the bound that excludes repositories calling such actions: 174 of 891
    in A (89 excluded), 55 of 398 in B (10 excluded). Nothing new was collected.
11. **Added measures (review M1, M2, M4, m8, m9).** Pooled SHA shares without the largest repositories;
    per-repository median and mean SHA share; H1 concentration (largest contributor, top five,
    leave-one-repository-out range); bootstrap interval for H1b; §6.3 shares with and without action
    repositories that have no release.
12. **Intervals (review m1).** Section 5 froze a bootstrap for B's repository-level shares; we report
    Wilson intervals for them instead (B is a simple random sample) and no interval for A's
    repository-level shares (a census). Reference-level intervals are the frozen cluster bootstrap; its
    values moved by up to 0.3 points because the repository order changed with the new export.
13. **Timing (review m2).** The frames were enumerated and the B sample drawn by 11:21:00Z, 9 minutes
    before this file was frozen (11:30:00Z); the workflows were collected after the freeze. The rules
    do not depend on the sample. `data/population.json` notes that B is stored sorted by id, not in
    `random.sample()` order.
14. **Headline check (review M5).** `check_headline.py` now matches with number boundaries and accounts
    for every number of the checked sections (`VERIFICATION.md` §1).

## Sources and access (brief)

| host | access | used for |
|---|---|---|
| `api.github.com` | REST and GraphQL API, authenticated token | search frames, workflow files, releases, refs, commits, github/docs and github/roadmap contents |
| `github.blog` | WordPress REST API, unauthenticated | changelog and blog entries |
| `api.openalex.org`, `api.crossref.org` | public APIs | prior-work search and metadata |
| USENIX, NDSS, Radboud and UMONS repositories, wiz.io | one GET per document | prior-work PDFs and pages |

User-Agent `EasyxLab-research/0.1 (+https://easybyte.es/lab/; contact@easybyte.es)`; at most one request
start per second per host (search API: one per 2.2 s); about 900 requests in total, none rate-limited.
robots.txt was read before the first request to each host; arXiv and DBLP search were not queried
because it disallows them. Data published under CC BY 4.0; GitHub Docs quotations under their CC BY 4.0
licence; datosh/pinned-actions figures recomputed from its MIT-licensed archive.
