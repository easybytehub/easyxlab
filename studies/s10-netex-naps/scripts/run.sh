#!/usr/bin/env bash
# S10 — Are Europe's public-transport NeTEx datasets ready for the MMTIS deadlines?
# Regenerates the catalogue census, the sample, the validation results and the aggregates.
#   scripts/run.sh                   # full run: hours; ~0.6 GB of downloads, one dataset at a time (one worker)
#   SKIP_DOWNLOAD=1 scripts/run.sh   # re-aggregate existing data/per_dataset/*.json and check headlines
# A full run uses XSD_BUDGET = MAX_XSD_BYTES = 150 MB. The published records mix 300/400 MB (16 early
# datasets) and 150/150 MB; each record stores its own parameters in `xsd_params` (see METHOD.md §5).
# Requirements: python3 (3.11+), curl, tar. Disk: < 0.8 GB at any time (one dataset + XSDs).
set -euo pipefail
S="$(cd "$(dirname "$0")/.." && pwd)"; cd "$S"
UA="EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q "lxml==6.1.3" "requests==2.34.2"; }
mkdir -p work/xsd work/docs work/dl work/raw_catalogs data/per_dataset

# ---------- open schemas (pinned by commit SHA, not by tag) ----------
for TAG in 1.3.2 2.0.0; do
  case $TAG in 1.3.2) SHA=4f42794047ec9944fd38e4497f3af142a33462c8 ;; 2.0.0) SHA=a94e5e1752bcc13aabb8a1f3d018dc08e6978f42 ;; esac
  if [ ! -f "work/xsd/NeTEx-$TAG/xsd/NeTEx_publication.xsd" ]; then
    curl -sfL -A "$UA" "https://codeload.github.com/TransmodelEcosystem/NeTEx/tar.gz/$SHA" | tar -xzf - -C work/xsd "NeTEx-$SHA/xsd"
    mv "work/xsd/NeTEx-$SHA" "work/xsd/NeTEx-$TAG"
  fi
done
EPIP_REF=e5eaf83f15f7fd8db7991a4a8323b6ff7905c13a   # last commit; repository archived, "no longer maintained"
mkdir -p work/xsd/epip
for f in NeTEx_publication_EPIP.xsd NeTEx_publication_EPIP-NoConstraint.xsd _content_NeTEx_EPIP.xsd gml_combo_v3_2_1_simplified.xsd; do
  [ -f "work/xsd/epip/$f" ] || curl -sfL -o "work/xsd/epip/$f" "https://raw.githubusercontent.com/TransmodelEcosystem/NeTEx-Profile-EPIP/$EPIP_REF/$f"
done

# ---------- legal and profile texts (for the literal quotes; EUR-Lex blocks curl, use the Cellar) ----------
[ -f work/docs/cellar.html ] || curl -sfL -A "$UA" -H "Accept: application/xhtml+xml" -H "Accept-Language: eng" \
  -o work/docs/cellar.html "http://publications.europa.eu/resource/celex/32024R0490"
[ -f work/docs/fr_elements_communs.html ] || curl -sfL -A "$UA" -o work/docs/fr_elements_communs.html \
  "https://normes.transport.data.gouv.fr/normes/netex/elements_communs/"
for pair in general:728563782 framework:728727624; do
  name=${pair%%:*}; id=${pair##*:}
  [ -f "work/docs/nordic_$name.json" ] || curl -sfL -A "$UA" -o "work/docs/nordic_$name.json" \
    "https://enturas.atlassian.net/wiki/rest/api/content/$id?expand=body.storage,version"
done

# ---------- pipeline ----------
if [ -z "${SKIP_DOWNLOAD:-}" ]; then
  .venv/bin/python scripts/00_prior_work.py --fetch   # -> data/prior_work.csv
  .venv/bin/python scripts/00_landscape.py            # -> data/validator_landscape.csv (needs gh)
  .venv/bin/python scripts/01_catalogues.py     # census -> data/catalogue_netex.csv, data/nap_access_probes.csv
  .venv/bin/python scripts/01b_access.py --fetch       # -> data/nap_access.csv (2 Swiss requests, 1 kB)
  .venv/bin/python scripts/02_sample.py         # -> data/sample.csv
  .venv/bin/python scripts/03_validate.py       # -> data/per_dataset/*.json (download, validate, delete)
fi
.venv/bin/python scripts/03b_upgrade_records.py   # idempotent bookkeeping (xsd_params, rules v3 upgrades)
.venv/bin/python scripts/04_aggregate.py        # -> data/*.csv, data/summary.json, data/tables.md
.venv/bin/python scripts/05_check_headlines.py   # asserts every headline number against data/
( cd prototype && ../.venv/bin/python -W ignore -m unittest discover -s tests )
