# S1 — Conformance of open-source Verifactu implementations

*EasyxLab · study S1 · snapshot 2026-10-02 · status: working draft, not peer-reviewed*

## Abstract

Spain's Verifactu regime (RD 1007/2023, Orden HAC/1177/2024) requires invoicing
software to emit hash-chained XML records. We searched GitHub systematically through its
code and repository search APIs (1,008 repositories, 29,491 XML files), classified
every file containing a Verifactu record marker *before* linting it, and audited the
corpus with `verifactu-lint` 0.4.0, maintained by the authors. Only 63 third-party
repositories publish such XML, and most of it does not claim to be a valid record: 81
of 191 unique files are templates, mostly copies of the AEAT's own documentation
samples, whose hash fields literally read `Huella` or `AAAA`. Of the 35 files that do
purport to be valid records, 10 (28.6%, 95% CI 16.3–45.1) contain at least one ERROR;
6 of 19 repositories (31.6%, 95% CI 15.4–54.0) publish at least one. The most frequent
defect, in 5 of the 19 repositories, is a declared hash that does not match the one
computed from the record's fields. All 22 ERROR findings were reviewed one by one by
the LLM-based study agent, with hashes recomputed by an independent implementation:
no false positive was found (0/22; the findings are not independent, and over the 12
distinct repository–rule situations the upper 95% bound is 24.3%). No human expert
reviewed the findings. 34 of the 35 files hold a single record, so public XML examples
cannot serve as a reference for the hash chain, and outside the instrument's own
repository nobody publishes a deliberately invalid record.

**Competing interests:** the authors' organisation develops verifactu-lint and offers
commercial Verifactu services.

## Contents

| File | What |
|---|---|
| `paper.md` | Paper-style draft (EN). |
| `METHOD.md` | Sampling frame, classification rules, deduplication, statistics, ethics. |
| `VERIFICATION.md` | One-by-one review (by the LLM-based study agent) of every ERROR and of the classification. |
| `instrument-issues.md` | Issues found in verifactu-lint 0.4.0 (none filed). |
| `blog-es.md` | Divulgative version in Spanish for easybyte.es/papers. |
| `run.sh`, `scripts/` | Reproducible pipeline (collect → classify → lint → stats → sample). |
| `data/summary.json`, `data/rules.csv`, `data/repos_anon.csv`, `data/files_anon.csv` | Aggregates and anonymised references only. |

Not in version control: `data/raw/` (third-party files, normative PDFs, lint
details) and `private/` (repository mapping, real references with commit SHAs,
collection state).

## Reproduce

```bash
./run.sh     # needs gh (authenticated), Python ≥ 3.11; ~40 min, rate-limited by GitHub search
```

GitHub search results change over time. The exact corpus is pinned by commit SHAs, but
those live in `private/references.csv`, which is not published (it would de-anonymise
the repositories): **a third party cannot reproduce the exact corpus**, only re-run the
pipeline on today's GitHub. Repositories are published anonymised (R01–R19) and
maintainers have not been contacted.

---

EasyxLab · a research lab by [EasyByte](https://easybyte.es)
