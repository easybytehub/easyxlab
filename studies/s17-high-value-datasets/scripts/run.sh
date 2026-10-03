#!/usr/bin/env bash
# S17: regenerate every published figure offline from data/ and check the headline numbers.
# Network steps (not run here; they re-collect a new snapshot):
#   01_census.py  02_sparql.py  02b_rdf_checks.py  04_reach.py  05_poland.py
# Steps that need the raw snapshot in data/raw/ (not published) run only if it is present:
#   00_odm.py (ODM xlsx -> data/odm2025_answers.csv), 03_analyse.py (raw -> data/census_records.csv etc.)
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
if [ -f data/raw/census.jsonl.gz ]; then
  "$PY" scripts/03_analyse.py
fi
if [ -f data/raw/odm2025_questionnaire_data.xlsx ] && "$PY" -c "import openpyxl" 2>/dev/null; then
  "$PY" scripts/00_odm.py
fi
"$PY" scripts/06_tables.py > /dev/null
echo "tables regenerated in data/"
if "$PY" -c "import pytest, rdflib" 2>/dev/null; then
  "$PY" -m pytest -q tests
else
  echo "pytest/rdflib not installed: tests skipped (pip install pytest rdflib)"
fi
"$PY" scripts/check_headline.py
