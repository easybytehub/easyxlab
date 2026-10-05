#!/usr/bin/env bash
# S23: regenerate data/ from the raw sources in data/raw/ (git-ignored).
#
#   bash scripts/run.sh            tests + tables + figures + reconciliation + art. 32 + headline and quotation checks (offline)
#   bash scripts/run.sh fetch      download every source again; run it in the background:
#                                  nohup bash scripts/run.sh fetch > work/fetch.log 2>&1 &
#   bash scripts/run.sh check      only check the headline numbers against data/
#
# Python >= 3.10 (standard library + openpyxl for the OECD workbook), poppler's pdftotext,
# and curl (used only when Python cannot verify a server's TLS chain; TLS is still verified).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && PY=.venv/bin/python
case "${1:-all}" in
  fetch)
    "$PY" scripts/fetch.py all          # BOE consolidated texts, EU texts (Cellar)
    "$PY" scripts/fetch_others.py       # OVS bulletins, OECD, Housing Europe, BdE, INE, Eurostat, MIVAU, catalogue pages
    "$PY" scripts/catalogues.py         # datos.gob.es title searches -> data/catalogue_search.csv
    "$PY" scripts/boe_sumarios.py       # BOE daily summaries 26-5-2023..3-10-2026 -> data/boe_title_hits.csv (~25 min)
    "$PY" scripts/prior_work.py         # Crossref, OpenAlex, Bing News RSS, press pages -> data/prior_work_search.csv
    ;;
  check)
    "$PY" scripts/check_headlines.py
    ;;
  all)
    "$PY" -m unittest discover -s tests
    "$PY" scripts/ovs_tables.py         # -> ovs_eu_table, ovs_regions, ovs_regions_t23, ovs_municipal_2023, ovs_checks
    "$PY" scripts/figures.py            # -> figures.csv, eu_averages.csv (every quotation checked against the raw text)
    "$PY" scripts/boe_sumarios.py --hits-only   # -> boe_title_hits.csv (from the saved summaries)
    "$PY" scripts/analysis.py           # -> denominators, shares_recomputed, oecd_average_check, reconciliation, summary.json
    "$PY" scripts/art32.py              # -> art32_text.csv, art32_search.csv; adds to summary.json
    "$PY" scripts/check_headlines.py
    "$PY" scripts/check_quotes.py       # every «quotation» in README and paper is in a source text
    ;;
  *) echo "usage: scripts/run.sh [all|fetch|check]" >&2; exit 2 ;;
esac
