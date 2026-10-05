#!/usr/bin/env bash
# S24: rebuild data/ from INE's ECV microdata (downloaded into data/raw/, git-ignored).
#
#   bash scripts/run.sh fetch    download the 53 locked inputs (≈ 0.7 GB, mostly INE microdata) and check SHA-256
#   bash scripts/run.sh          extract, analyse, tests, headline check (offline; a few minutes)
#   bash scripts/run.sh check    only check the headline numbers of README.md and paper.md against data/
#
# INE's terms for its microdata do not expressly allow redistributing the files, so they are not in
# this repository: `fetch` downloads them from ine.es. Heavy steps can be wrapped by the caller.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
"$PY" -c 'import sys; assert sys.version_info >= (3, 10), "Python >= 3.10 needed"'
export PYTHONPATH="scripts${PYTHONPATH:+:$PYTHONPATH}"
case "${1:-all}" in
  fetch)
    "$PY" scripts/fetch.py
    ;;
  check)
    "$PY" scripts/check_headlines.py
    ;;
  all)
    "$PY" scripts/fetch.py --verify     # stop if any locked input is missing or is not the locked vintage
    "$PY" scripts/extract_ecv.py        # data/raw/ecv/*.zip -> data/raw/derived/ecv_persons_<year>.csv (unit level, git-ignored)
    "$PY" scripts/longitudinal.py       # -> data/leavers.csv, continuing_tenants.csv (INE longitudinal files)
    "$PY" scripts/analyse.py            # -> data/young_burden.csv, decomposition.csv, selection_bound.csv, bootstrap.csv …
    "$PY" scripts/cje.py                # -> data/cje_reconciliation.csv, cje_own_ecv_figures.csv
    "$PY" scripts/epa_check.py          # -> data/epa_emancipation.csv
    "$PY" scripts/build_external.py     # -> data/eurostat_series.csv, ipva.csv, quotes.csv
    "$PY" scripts/summarize.py          # -> data/summary.json
    "$PY" -m unittest discover -s tests
    "$PY" scripts/check_headlines.py
    ;;
  *) echo "usage: scripts/run.sh [all|fetch|check]" >&2; exit 2 ;;
esac
