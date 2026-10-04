#!/usr/bin/env bash
# S22: regenerate data/ from the locked INE, Ministry and Eurostat files in data/raw/ (git-ignored).
#
#   bash scripts/run.sh          tests + build + analysis + headline check (offline, a few seconds)
#   bash scripts/run.sh fetch    download the locked files again and check their SHA-256
#   bash scripts/run.sh check    only check the headline numbers of README.md and paper.md against data/
#   bash scripts/run.sh prior    rebuild data/prior_work_search.csv from the search logs in work/
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
  prior)
    "$PY" scripts/prior_work_search.py
    ;;
  all)
    "$PY" scripts/build.py          # -> data/national_series.csv, specialisation.csv, regions.csv, …
    "$PY" scripts/analyse.py        # -> data/decomposition.csv, sensitivity.csv, summary.json, predictions_2026_spec.json …
    "$PY" scripts/score_2026.py --dry-run   # -> data/score_dryrun.json (the D1 rules on 2022 -> 2024, in sample)
    "$PY" -m unittest discover -s tests
    "$PY" scripts/check_headlines.py
    ;;
  *) echo "usage: scripts/run.sh [all|fetch|check|prior]" >&2; exit 2 ;;
esac
