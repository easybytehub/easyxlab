#!/usr/bin/env bash
# S8 — rebuild data/ from the scan records, and check the figures quoted in README.md and paper.md.
#
#   ./run.sh                    build data/records.jsonl.gz from data/raw/ when the raw scan files
#                               are present (EasyxLab's working copy); otherwise use the published
#                               data/records.jsonl.gz. Then aggregate and check the figures.
#   ./run.sh --new-measurement  a NEW measurement: download the sources, rebuild the population and
#                               scan with scanner version 2. Needs S8_USER_AGENT set to a
#                               User-Agent that identifies you. Its figures will not match paper.md.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3}

if [ "${1:-}" = "--new-measurement" ]; then
  : "${S8_USER_AGENT:?set S8_USER_AGENT, e.g. 'MyLab-research/1.0 (+https://example.org/about-this-scan)'}"
  if ! "$PY" -c "import xlrd, openpyxl" 2>/dev/null; then
    python3 -m venv .venv && .venv/bin/pip -q install xlrd openpyxl && PY=.venv/bin/python
  fi
  scripts/fetch_sources.sh
  "$PY" scripts/build_population.py
  # keep the previous raw records apart: the new scan must not be mixed with them
  if ls data/raw/scan*.jsonl data/raw/recheck_*.jsonl data/raw/robots_snapshot.jsonl >/dev/null 2>&1; then
    old="data/raw/previous-$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p "$old"
    mv data/raw/scan*.jsonl data/raw/recheck_* data/raw/robots_snapshot.jsonl "$old"/ 2>/dev/null || true
  fi
  "$PY" scripts/scan.py --workers 48 --out data/raw/scan.jsonl      # ~30 min, resumable
  "$PY" scripts/build_records.py
  "$PY" scripts/aggregate.py
  echo "new measurement written to data/; README.md and paper.md describe the 2026-10-02 one" >&2
  exit 0
fi

if [ -f data/raw/scan.jsonl ]; then
  "$PY" scripts/build_records.py
fi
"$PY" scripts/aggregate.py
"$PY" scripts/check_numbers.py
