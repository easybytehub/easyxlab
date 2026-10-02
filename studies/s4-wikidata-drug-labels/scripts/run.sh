#!/usr/bin/env bash
# Reproduce study S4 from the frozen snapshot (default) or from a fresh extraction.
#   scripts/run.sh            -> detectors, sample, metrics, corrections on data/frozen (2026-10-02)
#   FREEZE=1 scripts/run.sh   -> re-extract from Wikidata first (new snapshot: the hand
#                                verdicts in data/validation_*.csv then no longer apply)
# Requirements: python3 (stdlib only), network only when FREEZE=1.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "${FREEZE:-0}" = 1 ] || [ ! -f data/frozen/drugs.jsonl ]; then
  python3 scripts/01_extract_wikidata.py
  python3 scripts/01b_disease_classes.py
  python3 scripts/02_reference_sources.py
fi
python3 scripts/03_detect.py
python3 scripts/04_sample.py > data/review_sheet.txt
python3 scripts/05_metrics.py > /dev/null
python3 scripts/06_corrections.py
echo "done: data/flags.csv data/metrics.json data/tables.md corrections.qs corrections.csv"
