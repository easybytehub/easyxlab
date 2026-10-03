# netex-lint (prototype)

A small, dependency-light linter for NeTEx datasets, written for EasyxLab, study S10.
**It is a prototype, not a product**: no packaging, no stability promise, rules may change.

What it does that a plain XSD validator does not:

- treats all documents of a ZIP as **one dataset**, so references across files are resolved
  (XSD identity constraints only work inside one document);
- flags versioned references that resolve nowhere, version mismatches and duplicate definitions;
- flags datasets whose validity window or calendar is already in the past;
- flags non-UTF-8 declarations, BOMs and double-encoded text ("GÃ¤vle");
- applies the identifier and reference rules that the **open** Nordic and French national profile
  texts state literally (see `RULES.md` for every quote and source).

It never uses the paid CEN text of EPIP. Optional XSD validation uses the open NeTEx XSD
(GPL-3.0) or the archived EPIP XSD, which you download yourself.

## Use

```bash
python3 -m venv .venv && .venv/bin/pip install lxml
cd prototype
../.venv/bin/python -m netex_lint path/to/dataset.zip                  # consistency rules only
../.venv/bin/python -m netex_lint data.zip --xsd NeTEx/xsd/NeTEx_publication.xsd
../.venv/bin/python -m netex_lint data.zip --profile nordic --today 2026-10-02 --json
```

Input: a `.zip` of NeTEx XML documents, a `.xml.gz` or a `.xml`. The consistency pass **parses** in
streaming mode, but it keeps every id, definition and reference of the dataset in memory, so memory
grows with the dataset: O(ids + refs). The Belgian TEC feed has about 6.9 M references and needs
several GB. XSD validation loads one whole document at a time (roughly 5–6 times its size in RAM).
A disk-backed index would be needed for national-scale feeds.

Exit status: `0` no error-level finding, `1` at least one error, `2` usage problem.

## Tests

```bash
cd prototype && ../.venv/bin/python -m unittest discover -s tests
```

Sixteen synthetic fixtures (no real dataset is redistributed). They include the two false positives found by the S10 review: open-ended validity and a missing XML declaration.

## What it would take to be useful

- SIRI: validate SIRI deliveries and resolve their references against the NeTEx ids of the same NAP.
- EPIP as now mandated for rail by the TEL TSI (CEN/TS 16614-4:2025, milestones 12.12.2027 and
  10.12.2028): this needs an open schema or open rules for the 2025 edition; the only open EPIP XSD
  is the archived 2021 one.
- A disk-backed index (memory, see above) and tests on real national feeds.

## Limits

- No semantic checks (stop sequences, times, geometry, fares).
- Profile detection is heuristic (declared version string and `TypeOfFrameRef`); force it with `--profile`.
- Unversioned references to objects outside the dataset (national stop registries) are counted, not flagged.
- Licence: Apache-2.0 (code), like the rest of EasyxLab.
