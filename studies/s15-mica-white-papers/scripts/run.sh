#!/usr/bin/env bash
# Regenerate every figure of S15 offline from the published tables in data/ (no network, no raw data needed).
# Full pipeline from scratch (network, ~2 h; needs data/raw/ and work/, never published):
#   python scripts/00_sources.py; python scripts/00_legal.py; python scripts/00_qas.py; python scripts/01_snapshots.py
#   python scripts/00_prior_work.py   # prior-work search, as run on 2026-10-03
#   python scripts/02_collect.py --cohort-only; python scripts/02b_refetch_4xx.py; python scripts/02_collect.py
#   python scripts/03_validate.py; python scripts/03b_refetch_facts.py   # D4 (only after the keepOpen bug)
#   python scripts/02c_review_recheck.py   # D8-D10, corrections after the review (then 03_validate.py and 04_gleif.py again)
#   python scripts/04_gleif.py; python scripts/05_build.py
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
"$PY" scripts/06_analyse.py
"$PY" scripts/summarize.py   # data/summary.json, the figures of claims.csv
"$PY" scripts/check_headline.py
