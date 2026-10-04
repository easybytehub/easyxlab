#!/usr/bin/env bash
# S12: regenerate data/ from the locked CGPJ and Ministry files in data/raw/ (git-ignored).
#
#   bash scripts/run.sh          tests + build + data-quality checks + analysis + headline check (offline)
#   bash scripts/run.sh fetch    download the locked files again and check their SHA-256 (PROTOCOL.md §3.3)
#   bash scripts/run.sh check    only check the headline numbers of paper.md against data/
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
PY=.venv/bin/python
case "${1:-all}" in
  fetch)
    "$PY" scripts/fetch.py
    ;;
  check)
    "$PY" scripts/check_headlines.py
    ;;
  all)
    "$PY" -m unittest discover -s tests
    "$PY" scripts/build.py        # -> data/districts.csv, province_*.csv, cgpj_notes.csv; work/panel.json
    "$PY" scripts/dq.py           # -> data/dq_*.csv, data/dq_summary.json
    "$PY" scripts/analyse.py      # -> data/tests.csv, sensitivity.csv, summary.json, predictions_q2_2026.csv …
    "$PY" scripts/post_review.py  # -> data/review_checks.json, review_slopes.csv (post-review, exploratory)
    "$PY" scripts/check_headlines.py
    ;;
  *) echo "usage: scripts/run.sh [all|fetch|check]" >&2; exit 2 ;;
esac
