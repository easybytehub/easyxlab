#!/usr/bin/env bash
# S11: regenerate data/ from the raw snapshots and registries in data/raw/ (git-ignored).
#
#   bash scripts/run.sh            tests + extract + analyse + headline check (offline)
#   bash scripts/run.sh fetch      download Inside Airbnb snapshots and registries again
#                                  (registries change daily: a new fetch gives new numbers)
#   bash scripts/run.sh check      only check the headline numbers against data/
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-all}" in
  fetch)
    python3 scripts/download_listings.py
    python3 scripts/fetch_registries.py
    ;;
  check)
    python3 scripts/check_headlines.py
    ;;
  all)
    python3 -m unittest discover -s tests
    python3 scripts/extract_listings.py      # -> work/extract/ (row level, private)
    python3 scripts/analyse.py               # -> data/*.csv, data/*.json (aggregates only)
    python3 scripts/check_headlines.py
    ;;
  *) echo "usage: scripts/run.sh [all|fetch|check]" >&2; exit 2 ;;
esac
