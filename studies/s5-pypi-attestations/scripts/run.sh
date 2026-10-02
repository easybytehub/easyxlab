#!/usr/bin/env bash
# Reproduce study S5.
#   scripts/run.sh          offline (default): recompute everything from data/compact/; never touches the network
#   FETCH=1 scripts/run.sh  rebuild data/raw/ and data/compact/ from the network with pinned inputs, then recompute
# Requirements: python3 >= 3.10 and `packaging` (pip install packaging).
set -euo pipefail
cd "$(dirname "$0")"
if [ "${FETCH:-0}" = 1 ]; then
  export OFFLINE=0
  python3 01_fetch_inputs.py         # hugovk list at pinned commit (SHA-256), npm-high-impact 1.13.0 (sha512)
  python3 00_sources.py              # literal excerpts from the saved pages (REFRESH_SOURCES=1 to re-download)
  python3 02_fetch_simple.py         # PEP 691 simple index, 15,000 projects -> data/raw/simple/
  python3 01b_export_compact.py      # -> data/compact/ (self-check against the cache)
  python3 03_analyse_pypi.py
  python3 04_integrity.py            # Integrity API publishers
  python3 05_regressions.py          # workflow evidence + rule classes
  python3 06_publisher_changes.py
  python3 07_npm.py                  # npm sample
  python3 08_npm_analyse.py
  python3 01b_export_compact.py      # include the new evidence in data/compact/
else
  export OFFLINE=1
  python3 00_sources.py              # uses saved pages if present; never overwrites excerpts.json otherwise
  python3 03_analyse_pypi.py
  python3 04_integrity.py
  python3 05_regressions.py          # reuses published evidence where the raw cache is absent
  python3 06_publisher_changes.py
  python3 08_npm_analyse.py
fi
python3 09_tables.py > /dev/null
python3 10_check_headlines.py
