#!/usr/bin/env bash
# S14: regenerate data/ from the BOE downloads in data/raw/ (git-ignored) and the review verdicts.
#
#   bash scripts/run.sh            tests + lots + review queue + analysis + headline check (offline)
#   bash scripts/run.sh fetch      download the BOE daily summaries and the candidate notices again
#   bash scripts/run.sh check      only check the headline numbers against data/
#
# The review verdicts (data/review_verdicts.csv) were written by the study agent (an AI agent); they
# are an input here, not an output.
set -euo pipefail
cd "$(dirname "$0")/.."
START=2025-01-01
END=2026-09-30
case "${1:-all}" in
  fetch)
    python3 scripts/fetch_sumarios.py "$START" "$END"
    python3 scripts/select_notices.py "$START" "$END" work/candidates_study.csv
    python3 scripts/fetch_notices.py work/candidates_study.csv
    ;;
  check)
    python3 scripts/check_headlines.py
    ;;
  all)
    python3 -m unittest discover -s tests
    python3 scripts/select_notices.py "$START" "$END" work/candidates_study.csv
    python3 scripts/build_lots.py work/candidates_study.csv work/auto      # row level, private
    python3 scripts/build_lots.py work/candidates_study.csv work/auto_frozen --frozen-parser   # for the D1 comparison
    python3 scripts/review_queue.py build work/auto                        # review sets R1-R4
    python3 scripts/analyse.py work/auto data/review_verdicts.csv work/auto_frozen   # -> data/*.csv, data/summary.json
    python3 scripts/check_headlines.py
    ;;
  *) echo "usage: scripts/run.sh [all|fetch|check]" >&2; exit 2 ;;
esac
