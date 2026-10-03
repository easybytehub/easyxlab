#!/usr/bin/env bash
# S16 — rebuild every figure from data/ and check the headline numbers.
#
#   ./run.sh                    offline. With EasyxLab's raw scan in data/raw/ it re-applies the current comment detector (v4)
#                               and rebuilds data/records.csv; otherwise it starts from the published
#                               data/records.csv. Then aggregates, runs the tests and check_headline.py.
#   ./run.sh --new-measurement  a NEW measurement (network): population, sources, scan. Its figures will
#                               not match README.md.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3}
if [ "${1:-}" = "--new-measurement" ]; then
  "$PY" scripts/build_population.py fetch
  "$PY" scripts/build_population.py build
  "$PY" scripts/fetch_sources.py
  "$PY" scripts/fetch_sources.py --providers
  "$PY" scripts/scan.py --workers 16
  "$PY" scripts/aggregate.py build
  "$PY" scripts/aggregate.py summary
  echo "new measurement written to data/; README.md describes the 2026-10-03 one" >&2
  exit 0
fi
if [ -f data/raw/scan.jsonl ]; then
  "$PY" scripts/apply_detectors.py
  "$PY" scripts/aggregate.py build
  [ -f work/audit_sample.json ] && "$PY" scripts/comment_audit.py >/dev/null
fi
[ -d data/raw/sources ] && "$PY" scripts/providers_panel.py >/dev/null
"$PY" scripts/aggregate.py summary >/dev/null
"$PY" -m unittest discover -s tests
"$PY" scripts/check_headline.py
