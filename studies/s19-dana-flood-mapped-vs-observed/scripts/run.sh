#!/usr/bin/env bash
# S19: download the public sources and rebuild data/.
#
#   bash scripts/run.sh            build: tests, extent, buildings, map flags, aggregates, headline
#                                  check. If the raw inputs are missing (a fresh clone), it runs
#                                  `fetch` first.
#   bash scripts/run.sh fetch      download every public source (Copernicus EMS ~620 MB, Catastro
#                                  ~230 MB, PATRICOVA, IGN, GVA, 1,153 hazard-map tiles).
#                                  At one request per second this takes about an hour.
#   bash scripts/run.sh check      only check the headline numbers and the disclosure control
#
# Heavy steps (the Catastro download and parse, the extent unions: >1 GB of RAM) go through the
# lab's shared lock when it exists (EASYXLAB_HEAVY points to heavy.sh); otherwise they run directly.
# Python >= 3.10 with shapely 2, pyproj, pyogrio (GDAL), lxml, numpy and Pillow:
#   python3 -m venv .venv && .venv/bin/pip install shapely pyproj pyogrio lxml numpy pillow scipy
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
HEAVY="${EASYXLAB_HEAVY:-}"
heavy() { if [ -n "$HEAVY" ]; then bash "$HEAVY" "s19-$1" "${@:2}"; else "${@:2}"; fi; }

fetch() {
  "$PY" scripts/fetch_ems.py                    # Copernicus EMS EMSR773 (latest versions)
  mkdir -p data/raw/ems_prev                    # earlier versions used in the sensitivity
  for a in AOI03/GRA_PRODUCT/EMSR773_AOI03_GRA_PRODUCT_v1.zip AOI02/DEL_PRODUCT/EMSR773_AOI02_DEL_PRODUCT_v1.zip; do
    f="data/raw/ems_prev/$(basename "$a")"
    [ -f "$f" ] || "$PY" scripts/polite.py "https://rapidmapping.emergency.copernicus.eu/backend/EMSR773/$a" "$f"
  done
  "$PY" scripts/fetch_patricova.py              # PATRICOVA hazard (ICV geoprocessing service)
  "$PY" scripts/fetch_municipalities.py         # IGN municipal boundaries, province 46
  "$PY" scripts/fetch_gva_dana.py               # Generalitat DANA layers (footprint, municipalities)
  heavy extent "$PY" scripts/build_extent.py    # needed to know which municipalities to fetch
  heavy catastro "$PY" scripts/fetch_catastro.py
  heavy parse "$PY" scripts/parse_buildings.py
  "$PY" scripts/fetch_snczi.py                  # SNCZI tiles around the kept buildings
  "$PY" scripts/make_sources.py
}

build() {
  "$PY" -m unittest discover -s tests
  [ -f work/extent/extent_summary.json ] || heavy extent "$PY" scripts/build_extent.py
  heavy parse "$PY" scripts/parse_buildings.py  # resumable: skips municipalities already parsed
  heavy classify "$PY" scripts/classify.py      # recomputes when buildings or classify.py changed
  "$PY" scripts/check_nesting.py
  "$PY" scripts/qa_holes.py
  "$PY" scripts/analyse.py
  "$PY" scripts/make_sources.py
  "$PY" scripts/check_headlines.py
  "$PY" scripts/check_disclosure.py
}

case "${1:-all}" in
  fetch) fetch ;;
  check) "$PY" scripts/check_headlines.py && "$PY" scripts/check_disclosure.py ;;
  all)
    if ! ls data/raw/ems/EMSR773_AOI01_DEL_PRODUCT_v1.zip >/dev/null 2>&1 \
       || ! ls data/raw/catastro/A.ES.SDGC.BU.*.zip >/dev/null 2>&1 \
       || [ ! -d work/snczi/tiles ]; then
      echo "local copies missing: fetching the public sources first"
      fetch
    fi
    build
    ;;
  *) echo "usage: scripts/run.sh [all|fetch|check]" >&2; exit 2 ;;
esac
