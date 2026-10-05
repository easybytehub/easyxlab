# S15 — Are MiCA crypto-asset white papers published in the machine-readable format required since 23 December 2025?

*EasyxLab · study S15 · data collected 2026-10-03 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s15/paper/](https://easybyte.es/lab/studies/s15/paper/) · [PDF](https://easybyte.es/lab/studies/s15/paper.pdf)

## Abstract

Since 23 December 2025, Commission Implementing Regulation (EU) 2024/2984 requires crypto-asset white papers under
MiCA, Regulation (EU) 2023/1114, to be drawn up in XHTML with the fields of its Annex marked in Inline XBRL 1.1, as a
single XHTML file; ESMA published the XBRL taxonomy files on 5 August 2025. We took every white paper in ESMA's
interim MiCA register (CSV files, last updated 30 September 2026) whose record was created or updated on or after
23 December 2025, fetched the URL the register gives for it on 2026-10-03, followed redirects and at most one link
to a document, and validated every Inline XBRL file with Arelle and ESMA's taxonomy package, formula assertions
included.

**143 of 440 register rows (32.5%; 95% CI 28.3–37.0%) lead to an Inline XBRL 1.1 file in ESMA's MiCA taxonomy at
the registered URL or one link away; they correspond to 141 distinct files.** The rest lead to a web page with
no document link (129 rows), a PDF only (69), an XHTML file without any Inline XBRL (20), an Inline XBRL file with another or wrong taxonomy reference (3), a ZIP archive (2), a file in Inline XBRL 1.0 (1), or nothing we could read: 73 of 440 rows ended in an
anti-bot wall, a `robots.txt` exclusion, an HTTP error or a network failure. For one crypto-asset service provider
we observed an Incapsula wall on 20 rows and, on its asset host, XHTML files titled "MiCA Whitepaper Inline XBRL"
with no XBRL facts on 18 rows; the same title also appears on Inline XBRL files from other hosts.

Of the rows that reach the format, **110 of 143 rows** point to a file that validates with zero errors (108 of 141 distinct
files); of the 33 others, 16 fail only ESMA assertions and 17 have XBRL or Inline XBRL errors. Identifiers agree
with the register: the register's LEI is in the file in 103 of 103 checkable rows, and a register DTI in 134 of
136. Production is concentrated: one data provider, which the register names as offeror or person seeking
admission on those rows, serves 77 of 110 valid rows from its own white-paper site.

Under the access and redirect rules frozen before collection (`METHOD.md`), the headline would be 139 of 440 (31.6%;
95% CI 27.4–36.1%). The rest of the register (634 rows dated before 23 December 2025 or undated)
reaches the format in 20 of 634 rows.

ESMA's 51 MiCA Q&As do not say whether the copy published on the website must itself be the Inline XBRL file, and
the closest legal link (MiCA Art. 6(11), which ties the format standards to the duty of Art. 6(10)) does not say so
either. This study therefore measures **availability of the machine-readable version at the registered URL**, not
compliance; it cannot see what was notified to national authorities.

**Prior work.** A public dashboard classifies the register's links by URL shape only, and a linter checks Annex I
content on a small convenience sample; neither fetches and validates the published Inline XBRL files. We found no census of
the format at the registered URLs (CCRI's MiCA-Monitor, a JavaScript application, could not be inspected)
([the paper](https://easybyte.es/lab/studies/s15/paper/) §2).

## Contents

- `METHOD.md` — population, cohort rule, access rules, classification, deviations (D1–D11).
- `VERIFICATION.md` — how to recompute and re-check each headline figure.
- `data/rows.csv` (one line per register row: registered URL, URL of the document classified, outcome under the
  current and the frozen rules, validity, identifier matches; no personal data), `data/documents.csv` (one line per
  distinct Inline XBRL file validated), `data/entities.csv` (GLEIF legal names of the LEIs used),
  `data/metrics.json`, `data/summary.json` (the figures of `claims.csv`, written by `scripts/summarize.py`), `data/tables.md`, `data/cohort_check.json`, `data/sources.csv`.
- `scripts/` — the fetcher (RFC 9309 `robots.txt`), the collector, the checker (`mica_wp_check.py`, usable on its own:
  `python scripts/mica_wp_check.py <file-or-url>` prints a JSON verdict that cites the rule), `run.sh` and
  `check_headline.py`. `tests/` covers the classification logic. `requirements.txt` pins Arelle.

## Licences

Code: Apache-2.0. Data and text: CC BY 4.0. The register-derived fields (including `wp_url`) come from ESMA's interim
MiCA register; ESMA authorises reproduction with acknowledgement of the source. `data/entities.csv` uses GLEIF data
(CC0). No white paper is redistributed; only hashes, sizes, classifications and validation results are published.
