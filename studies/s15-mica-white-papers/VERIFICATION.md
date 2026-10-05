# S15 — Verification

Every figure in `README.md` and the paper is computed by `scripts/06_analyse.py` from three published files:
`data/rows.csv`, `data/documents.csv` and `data/cohort_check.json`. `scripts/check_headline.py` recomputes them and
asserts each headline phrase in the README abstract (and in the paper, when present).

## Offline (no network, a few seconds)

```bash
cd studies/s15-mica-white-papers
bash scripts/run.sh            # = python3 scripts/06_analyse.py && python3 scripts/check_headline.py
python3 -m pytest -q tests     # classification logic (needs lxml)
```

## Each headline figure by hand

```python
import csv, re, datetime as dt
def d(x):
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", x.strip())
    return dt.date(int(m[3]), int(m[2]), int(m[1])) if m else None
rows = [r for r in csv.DictReader(open("data/rows.csv")) if r["excluded_placeholder"] == "0"]
c = [r for r in rows if (d(r["wp_lastupdate"]) or dt.date(1, 1, 1)) >= dt.date(2025, 12, 23)]   # 440 (414 + 26)
av = [r for r in c if r["outcome"] == "ixbrl-esma"]                   # 143 -> 143 of 440 (32.5%)
len({r["doc_sha256"] for r in av})                                    # 141 distinct files
va = [r for r in av if r["valid"] == "1"]                             # 110 of 143 rows (108 of 141 files)
ck = [r for r in av if r["ids_checked"] == "1"]
sum(r["lei_match"] == "1" for r in ck if r["lei"]), sum(1 for r in ck if r["lei"])                   # 103, 103
sum(r["dti_match"] == "1" for r in ck if r["register_dti"]), sum(1 for r in ck if r["register_dti"])  # 134, 136
sum(r["producer_domain"] == "crypto-risk-metrics.com" for r in va)                                    # 77 of 110
sum(r["outcome_frozen_rule"] == "ixbrl-esma" for r in c)                                              # 139 of 440
x = [r for r in rows if r not in c]; sum(r["outcome"] == "ixbrl-esma" for r in x), len(x)            # 20 of 634
```

The intervals are Wilson score intervals (`wilson()` in `scripts/06_analyse.py` and `scripts/check_headline.py`).
`check_headline.py` re-derives the cohort from the raw dates and the classes from `data/documents.csv`, recomputes
the intervals, and requires every number of the README abstract to sit inside a checked phrase: changing any of the
60 numbers of the abstract, or any headline pair in the paper, makes it fail (tested on a scratch copy).

## Re-checking against the sources (network)

1. **Cohort.** Download `https://www.esma.europa.eu/sites/default/files/2024-12/OTHER.csv` and `EMTWP.csv`. If ESMA
   has updated them since 30 September 2026, use the Wayback Machine capture of that date. Count rows with
   `wp_lastupdate` on or after 23/12/2025, in any of its formats (`dd/mm/yyyy`, `dd.mm.yyyy`), dropping the two
   copies of the header line inside `OTHER.csv` and the `EMT_NO_WP`/`EMT_CRIN` placeholders: 414 + 26. `csv_line` in
   `data/rows.csv` is the line in the CSV (header = 1); `wp_url` is the registered URL, so rows can be re-checked after
   ESMA overwrites the file; download tokens in signed storage links (`token=…`) are redacted, in `wp_url` (4 rows)
   as in `doc_url` (23 rows). The capture of 2025-12-23 is
   `https://web.archive.org/web/20251223101326id_/https://www.esma.europa.eu/sites/default/files/2024-12/OTHER.csv`.
2. **A row's outcome.** Open `wp_url` (or `doc_url`, the document we classified); if it is a landing page, look for a
   linked `.xhtml` file. `doc_sha256` is the sha256 of the file we classified (it changes if the publisher updates it).
3. **A file's validity.** Download ESMA's package
   (`https://www.esma.europa.eu/sites/default/files/2025-08/mica_taxonomy_2025.zip`, sha256
   `19921398b16cb2521f808965e5d058be8f68591c8f9d77d24eb9df2c14aae033`) and run, in a virtualenv with
   `arelle-release==2.46.0`:

   ```bash
   python scripts/mica_wp_check.py <file.xhtml> --package mica_taxonomy_2025.zip --lei <LEI> --dti <DTI>
   # or Arelle directly:
   arelleCmdLine --file <file.xhtml> --packages mica_taxonomy_2025.zip --validate --formula run --internetConnectivity offline
   ```

   A file is valid when no message has level ERROR or above. `data/documents.csv` lists, per file hash, the number
   of errors, the assertions evaluated (216 for Table 2) and the identifiers of failed assertions.
4. **GLEIF.** `https://api.gleif.org/api/v1/lei-records/<LEI>`; compare with `data/entities.csv`.
5. **Legal quotations.** `https://publications.europa.eu/resource/celex/02023R1114-20240109` and
   `…/celex/32024R2984` with `Accept: application/xhtml+xml`; ESMA Q&A 2845 at
   `https://www.esma.europa.eu/publications-data/questions-answers/2845`. Search the text for the quoted words.

## Known differences you may see

- Sites change: a URL that served a file on 2026-10-03 may now serve another one, or none.
- Files change: 12 of the 168 Inline XBRL files had changed when downloaded again for the version check (D10).
- `outcome_frozen_rule` differs from `outcome` on 47 cohort rows, because of deviations D1 and D9 (`METHOD.md`).
- `robots.txt` is applied as RFC 9309 (`scripts/robots9309.py`); it was re-read on the afternoon of 2026-10-03 (D8).
