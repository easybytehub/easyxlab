# METHOD — S1: Conformance of open-source Verifactu implementations

Study date: 2026-10-02. Instrument: `verifactu-lint` 0.4.0 (EasyByte, Apache-2.0).
Everything below is reproducible with `./run.sh`; each phase is idempotent.

## 1. Research question

Do the Verifactu invoicing-record XML files that open-source implementations publish
on GitHub conform to the regulation (RD 1007/2023, Orden HAC/1177/2024 and the AEAT
validation rules)? Which rules are broken most often?

## 2. Population and sampling frame

**Target population:** XML files containing Verifactu invoicing records
(`RegistroAlta`, `RegistroAnulacion`) or event records (`RegistroEvento`) published in
public GitHub repositories, as of 2026-10-02.

**Sampling frame:** the union of two GitHub API routes, because each one sees what the
other misses (`scripts/01_collect.py`):

1. **Code search** (`GET /search/code`), nine queries restricted to `extension:xml`:
   `RegistroAlta`, `RegistroAnulacion`, `RegFactuSistemaFacturacion`, `sum1`,
   `Huella TipoHuella`, `RegistroEvento`, `IDEmisorFactura`,
   `NumeroInstalacion IdSistemaInformatico`, `huella RegistroAnterior`. Code search only
   indexes default branches, files under 384 KB, and (generally) not forks. Rate limit:
   10 requests/min, respected with a fixed 7 s pause between requests.
2. **Repository search** (`GET /search/repositories`) for `verifactu`, `veri-factu`
   and `verifactu in:readme`, followed by a full recursive walk of each repository's
   git tree at the head of its default branch. Every `.xml` blob up to 1.5 MB is
   downloaded, except obvious noise (Odoo `views/`, `security/`, `report/`, `i18n/`
   directories; `pom.xml`, `AndroidManifest.xml`, `*.csproj`, `phpunit.xml`, `*.wsdl`…);
   at most 200 XML per repository.

A downloaded file enters the corpus only if it contains one of the byte markers
`RegistroAlta | RegistroAnulacion | RegistroEvento | RegFactuSistemaFacturacion`.
Files are downloaded from `raw.githubusercontent.com` **pinned to a commit SHA**, so
every reference in `private/references.csv` is immutable.

Third-party files are kept in `data/raw/` (git-ignored) and are **not redistributed**.

## 3. Classification (before linting)

Each *occurrence* (repository + path) is classified, not each content: the same file
can be an example in one repository and a negative test in another. Occurrences in the
instrument's own repository (`easybytehub/*`, class **x**) are removed first: its
examples are written to trigger or not trigger its own rules. The remaining
occurrences are classified in priority order c > d > e > b > a
(`scripts/02_classify.py`):

| Class | Meaning | Deterministic rule |
|---|---|---|
| **c** | AEAT response or other non-record artefact | contains an element whose local name starts with `Respuesta…`, or `EstadoEnvio`, `EstadoRegistro`, `CodigoErrorRegistro`, `Fault` |
| **d** | Template or schema | placeholder values in key fields (`Huella`/`huella…`, a letter repeated ≥ 3 times such as `AAAA`/`NNNN`, `XXX`, `...`, `?`, dummy hashes: 64 × one hex digit, `0123456789ABCDEF`×4) in `Huella`, `IDEmisorFactura(Anulada)`, `NIF`, `NumSerieFactura(Anulada)` — this is how the AEAT's web-service description writes its examples; or template markers (`{{`, `{%`, `${`, `<?php`, `<%`, `#{`, `th:`, `<xsl:`, `<xs:schema`, `<wsdl:`, `%s`, `{0}`, `{name}` as a text node…) or ≥ 3 SoapUI-style `?` placeholders |
| **e** | Contains the marker but no record to lint | no `RegistroAlta` / `RegistroAnulacion` / `RegistroEvento` element (e.g. a query request, a header-only envelope) |
| **b** | Deliberately invalid negative test | (i) **path**: a negative token in the path or file name (`invalid`, `error`, `bad`, `fail`, `wrong`, `broken`, `corrupt`, `malformed`, `negative`, `incorrect`, `tamper`, `defect`, `ko`, `roto/rota`, `missing`, `duplicate`, `mismatch`, `descuadr…`, `nok`…); (ii) **comment**: an XML comment announcing the defect; (iii) **testcode**: the repository's test source code references the file within ±12 lines of an error assertion |
| **a** | Example that purports to be valid | everything else |

### 3.3 Test-code check (`scripts/02b_testcode.py`)

For every provisional class-(a) file that lives under a test/fixture directory, the
repository's test sources (`.py .js .ts .php .java .cs .go .rb .kt .rs …` under test
directories, same commit, ≤ 300 files per repository) are downloaded and searched for
the file name (the stem if it has ≥ 8 characters, the full name otherwise). If it
appears inside a test case (from the enclosing `it(`/`test(`/`def test`/`@Test`… to
the next one) that contains an error assertion (`assertRaises`, `pytest.raises`,
`toThrow`, `expectException`, `assertThrows`, `assertFalse`, `invalid`, `should fail`,
`debe fallar`…) and no positive signal (`golden`, `assertValid`, `toMatchSnapshot`…),
the occurrence becomes (b).

**Revisions after review by the study agent (documented, not hidden).** The first version used a
±12-line window and counted `reject`/`rechazo` as negative path tokens. The review by the
LLM-based study agent found all 4 resulting (b) occurrences wrong: three were golden files, and one
was a valid `RechazoPrevio` resubmission fixture (in Verifactu, «rechazo» names a valid
scenario). The placeholder rule was also made case-insensitive after an AEAT example
variant with the literal previous hash `huella` slipped into (a). See `VERIFICATION.md`.

**Direction of the bias.** Every heuristic in this section errs towards (b). A file
moved from (a) to (b) leaves the numerator of non-conformance, so the reported
non-conformance rates are, by construction, **lower bounds** with respect to
classification error. §3.4 says which classes were reviewed (by the study agent, not by a person) and
which were not.

### 3.4 Review of the classification

The LLM-based study agent reviewed one by one all (b) and (a) occurrences and
tabulated the matching value of every (d)-placeholder occurrence. The random
per-class sample originally planned here was **not carried out**; classes (c),
(d)-template and (e) were not reviewed. No human reviewed the classification. Results
in `VERIFICATION.md`.

## 4. Deduplication

- **Forks** are excluded from all analyses (repository flag `fork: true`). They are
  counted in the funnel.
- **Identical content** (same SHA-256 of the bytes) is linted once. A content's class
  is the most conservative class among its non-fork, third-party occurrences (priority
  c > d > e > b > a; occurrences in the instrument's repository were already removed,
  so a file present there and in third-party repositories keeps its third-party class).
- **Copies across unrelated repositories** (vendored examples, copied AEAT samples)
  are kept at repository level — a repository that publishes a defective example
  publishes it regardless of who wrote it — but each content is assigned an *origin*
  (the oldest repository, by `created_at`, that contains it), and the repository-level
  rate is also reported restricted to the repository's *own* files.

## 5. Linting and statistics

Each unique content is linted with `verifactu-lint` 0.4.0 used as a library
(`lee`, `lee_eventos`, `audita`, `audita_eventos`), exactly as its CLI does: each file
is its own chain, invoicing and event chains audited separately, invoicing chains split
by issuer (`IDEmisorFactura`). No `--historico`. Severities are kept separate:
**ERROR** (contradicts the cited norm), **AVISO** (very likely non-conformant),
**INCOMPLETO** (cannot be determined from the file).

Two units of analysis (`scripts/04_stats.py`):

- **File**: unique class-(a) content that the instrument could read and that contains
  at least one record.
- **Repository** (headline unit): non-fork repository with at least one such class-(a)
  occurrence. Files within a repository are not independent (same generator, same
  author), so repository-level proportions are the ones for which a binomial model is
  defensible.

Proportions carry **Wilson 95% confidence intervals**. The repositories are not a
random sample of all Verifactu implementations — they are (close to) a census of what
GitHub search exposes — so the intervals describe sampling variability under the
hypothetical "repositories like these", not a margin of error against the population
of private implementations.

## 6. Verification of findings (instrument false-positive rate)

`scripts/05_sample.py` draws a stratified sample (up to two findings per
(rule, severity) stratum, seed 20261002), but since the corpus turned out small the
sample was **not used**: every ERROR (22) and AVISO (4) on class-(a) files was
reviewed one by one by the LLM-based study agent; no human expert reviewed them. Each
finding is checked against the literal text of the norm (BOE texts
downloaded to `data/raw/norma/`) and, for hash rule `RRSIF001`, against an
**independent re-implementation** of the hash written in `05_sample.py` from the text
of Orden HAC/1177/2024 art. 13 and the AEAT hash specification, which imports nothing
from `verifactu-lint` (it was written by the same team, so it rules out coding bugs,
not a shared misreading of the specification). Verdicts: *true positive*, *false positive* (instrument bug, also
logged in `instrument-issues.md`), or *true positive but out of scope* (the file is
conformant to a different, legitimate reading — e.g. a fragment never meant to be a
chain).

## 7. Ethics

- No issues, pull requests or messages to maintainers. The operator decides whether
  and how to notify before publication.
- Repositories are anonymised (`R01…`, random order derived from a private salt).
  The mapping and the real references (repo, commit, path, licence) live in
  `private/` (git-ignored).
- Third-party files are not redistributed; `data/` only holds aggregates.
- A file in a public repository is not a production record: findings describe
  published examples, not the conformance of anyone's invoicing.
