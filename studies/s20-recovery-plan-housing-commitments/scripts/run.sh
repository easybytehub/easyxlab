#!/usr/bin/env bash
# S20: regenerate data/ from the raw texts in data/raw/ (git-ignored).
#
#   bash scripts/run.sh            tests + extract + diff + adoption + analysis + headline check (offline)
#   bash scripts/run.sh fetch      download the sources again (Cellar, Council, EU frame, PRTR site),
#                                  the scoreboard and the prior-work searches; run it in the background:
#                                  nohup bash scripts/run.sh fetch > work/fetch.log 2>&1 &
#   bash scripts/run.sh check      only check the headline numbers against data/
#
# Python >= 3.10, standard library only, plus websocket-client (scoreboard) and poppler's
# pdftotext (Council PDFs).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && PY=.venv/bin/python
case "${1:-all}" in
  fetch)
    "$PY" scripts/fetch.py all          # -> data/raw/{cellar,council,frame,others,prtr}
    "$PY" scripts/scoreboard.py         # -> data/raw/scoreboard/, data/scoreboard.csv
    "$PY" scripts/prior_work.py         # -> data/prior_work_search.csv (raw in work/prior/)
    ;;
  check)
    "$PY" scripts/check_headlines.py
    ;;
  all)
    "$PY" -m unittest discover -s tests
    "$PY" scripts/extract.py            # -> housing_rows, housing_measures, reasons, requests, texts/
    "$PY" scripts/diffs.py              # -> diffs.csv
    "$PY" scripts/baseline.py           # -> baseline_*.csv, baseline_summary.json (annex-wide base rate)
    "$PY" scripts/council_compare.py    # -> council_vs_proposal.csv
    "$PY" scripts/adoption.py           # -> adoption.csv
    "$PY" scripts/scoreboard.py --match # -> scoreboard.csv, scoreboard_versions.csv (from the saved raw)
    "$PY" scripts/costs.py              # -> measure_costs.csv (from the SWDs)
    "$PY" scripts/frame.py              # -> frame.csv, timeline.csv
    "$PY" scripts/others.py             # -> other_states_aug2026.csv
    "$PY" scripts/analyse.py            # -> version_table.csv, summary.json
    "$PY" scripts/check_headlines.py
    "$PY" scripts/check_quotes.py       # every «quotation» in README and paper is in a source text
    ;;
  *) echo "usage: scripts/run.sh [all|fetch|check]" >&2; exit 2 ;;
esac
