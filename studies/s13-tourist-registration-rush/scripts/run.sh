#!/usr/bin/env bash
# S13: download the public sources and rebuild data/.
#
#   bash scripts/run.sh            build: tests + analysis + comparators + headline check.
#                                  If no copy of the registry is present in data/raw/ (a fresh
#                                  clone), it runs `fetch` first.
#   bash scripts/run.sh fetch      download every public source again (registries, Internet
#                                  Archive copies, the GVA historical list, INE, BOE holidays)
#   bash scripts/run.sh check      only check the headline numbers against data/
#
# The registry changes daily. The published numbers come from the copy of 2026-10-04; a new
# fetch gives today's copy, the analysis then reads it (scripts/analyse.py, pick_copies), and
# check_headlines.py reports the differences without failing (see README, "How to run").
set -euo pipefail
cd "$(dirname "$0")/.."

fetch() {
  python3 scripts/fetch_gva.py                 # today's GVA registry (tur-gestur-vt)
  python3 scripts/fetch_gva.py wayback         # Internet Archive copies of the same CSV
  python3 scripts/fetch_gva_hist.py            # GVA historical list (to 2025-01-10) and last period
  mkdir -p data/raw/ine data/raw/legal
  python3 scripts/polite.py "https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/39363.csv" data/raw/ine/39363.csv
  for id in BOE-A-2022-16755:2023 BOE-A-2023-22014:2024 BOE-A-2024-21316:2025 BOE-A-2025-21667:2026; do
    python3 scripts/polite.py "https://www.boe.es/diario_boe/txt.php?id=${id%%:*}" "data/raw/legal/${id%%:*}_fiestas${id##*:}.html"
  done
  python3 scripts/build_holidays.py
  (cd scripts/comparators && python3 fetch_ine_dictionary.py && python3 andalucia.py && python3 euskadi.py && python3 mallorca.py)
}

build() {
  python3 -m unittest discover -s tests
  python3 scripts/analyse.py                   # -> data/*.csv, data/*.json (aggregates only)
  python3 scripts/analyse_comparators.py       # -> data/comparators*.csv
  python3 scripts/check_headlines.py
}

case "${1:-all}" in
  fetch) fetch ;;
  check) python3 scripts/check_headlines.py ;;
  all)
    if ! ls data/raw/registries/gva_min_????-??-??.csv >/dev/null 2>&1 \
       || [ ! -f data/raw/registries/gvahist_historico.csv ] || [ ! -f data/raw/ine/39363.csv ] \
       || [ ! -f data/raw/comparators/andalucia_daily.csv ]; then
      echo "local copies missing: fetching the public sources first"
      fetch
    fi
    build
    ;;
  *) echo "usage: scripts/run.sh [all|fetch|check]" >&2; exit 2 ;;
esac
