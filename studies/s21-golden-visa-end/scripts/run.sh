#!/usr/bin/env bash
# S21: download the public sources and rebuild data/.
#
#   bash scripts/run.sh            build: tests + tables + analysis + prediction CSV + headline check.
#                                  In a fresh clone (no data/raw/), it runs `fetch` first.
#   bash scripts/run.sh fetch      download every public source again (MIVAU, Internet Archive, ECB,
#                                  BOE / La Moncloa / INE / portugal.gov.pt pages, Statistics Portugal)
#   bash scripts/run.sh check      only check the headline numbers against data/
#   bash scripts/run.sh evaluate   score PREDICTIONS.md once MIVAU has published 2026Q3 (16 Dec 2026)
#
# The published numbers come from MIVAU's release of 1 October 2026 (2026Q2 provisional). A later
# fetch brings a later release; check_headlines.py then lists the differences without failing.
# PREDICTIONS.md is never rewritten: scripts/predict.py only refreshes data/predictions_2026Q3.csv.
set -euo pipefail
cd "$(dirname "$0")/.."

fetch() {
  python3 scripts/fetch.py all
}

build() {
  python3 -m unittest discover -s tests
  python3 scripts/build.py                     # data/raw -> data/province_quarter.csv, value_*.csv, fx_quarter.csv
  python3 scripts/fetch_portugal.py build      # data/raw/portugal -> data/portugal_quarter.csv
  python3 scripts/analyse.py                   # -> data/*.csv, data/summary.json (aggregates only), ~2 min
  python3 scripts/predict.py                   # -> data/predictions_2026Q3.csv
  python3 scripts/check_headlines.py
}

case "${1:-all}" in
  fetch) fetch ;;
  check) python3 scripts/check_headlines.py ;;
  evaluate) python3 scripts/build.py && python3 scripts/predict.py evaluate ;;
  all)
    if [ ! -f data/raw/mivau/340101d0.XLS ] || [ ! -f data/raw/mivau/340101l0.XLS ] \
       || [ ! -f data/raw/fx/ecb_EXR_Q.USD.EUR.SP00.A.csv ] || [ ! -f data/raw/fx/ecb_EXR_Q.GBP.EUR.SP00.A.csv ] \
       || [ ! -f data/raw/fx/ecb_EXR_Q.CNY.EUR.SP00.A.csv ] \
       || ! ls data/raw/portugal/0012785_05.json >/dev/null 2>&1; then
      echo "local copies missing: fetching the public sources first"
      fetch
    fi
    build
    ;;
  *) echo "usage: scripts/run.sh [all|fetch|check|evaluate]" >&2; exit 2 ;;
esac
