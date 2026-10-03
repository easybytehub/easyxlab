#!/usr/bin/env bash
# Reproduce study S18.
#   scripts/run.sh          offline (default): tests, then every figure from data/; never touches the network
#   FETCH=1 scripts/run.sh  re-collect from the GitHub API (needs a token via `gh auth token`), then recompute.
#                           The search frames and the repositories change every day: a re-run is a new snapshot.
# Requirements: python3 >= 3.10, standard library only (pyyaml optional: extractor cross-check in 05_export.py).
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
if [ "${FETCH:-0}" = 1 ]; then
  export OFFLINE=0
  $PY 00_sources.py        # GitHub Docs (github/docs), changelog and roadmap (github.blog REST API) -> data/sources/
  $PY 02_prior_work.py     # prior-work search log -> data/sources/prior_work_search.json
  $PY 02c_prior_numbers.py # prior-work figures (papers; datosh/pinned-actions archive) -> data/sources/prior_work_numbers.json
  $PY 01_frame.py          # search frames A and B, seeded sample -> data/raw/, data/frame_queries.csv
  $PY 03_collect.py        # workflow files and latest releases (GraphQL) -> data/raw/repos.jsonl
  $PY 04_actions.py        # action repositories, refs, releases (GraphQL) -> data/raw/actions.jsonl
  $PY 04b_shas.py          # is every pinned SHA a commit of its action repository? -> data/raw/shas.jsonl
  $PY 05_export.py         # -> data/*.csv (personal repositories: random pseudonyms, counts only), data/population.json
else
  export OFFLINE=1
  $PY 00_sources.py        # re-checks the literal excerpts if the saved pages exist; otherwise keeps them
fi
$PY -m unittest discover -s ../tests -q
$PY 06_analyse.py          # -> data/metrics.json, data/tables.md (asserts the verdicts are reproduced)
$PY check_headline.py      # asserts every headline number in README.md (and paper.md if present)
