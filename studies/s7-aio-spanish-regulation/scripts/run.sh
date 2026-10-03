#!/usr/bin/env bash
# S7 — run the study (Python 3.10+, stdlib only).
#   run.sh boe              download every BOE text used in data/facts.json and verify each quotation (free)
#   run.sh status           later amendments, repeals, annulments and the BOE issues of the reading day (free)
#   run.sh reading N        one reading of all queries on AIO + AI Mode (paid, DataForSEO; budget-guarded)
#   run.sh classify         regex rules + the agent's review file -> data/answers.csv, data/citations.csv
#                           (needs data/raw/responses/, the full answers, which are NOT redistributed)
#   run.sh pages            fetch the cited pages of confirmed errors (+40 controls in reading 1) (online)
#   run.sh analyse          tables and summary from the published files only, then the headline check
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
  boe)      python3 scripts/fetch_boe.py --from-facts && python3 scripts/build_facts.py ;;
  status)   python3 scripts/status_check.py ;;
  reading)  shift; n="$1"; shift; python3 scripts/probe.py --reading "$n" "$@" ;;
  classify) python3 scripts/classify.py && python3 scripts/sample_second_reader.py ;;
  pages)    python3 scripts/check_pages.py --reading 1 --control 40
            python3 scripts/check_pages.py --reading 2 --control 0
            python3 scripts/check_pages.py --reading 3 --control 0 ;;
  analyse)  python3 scripts/aggregate.py > /dev/null && python3 scripts/check_headline.py ;;
  *) sed -n '2,10p' "$0"; exit 1 ;;
esac
