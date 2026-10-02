#!/usr/bin/env bash
# Download the population and URL sources into data/raw/ (git-ignored).
# Identify yourself: S8_USER_AGENT="Name/1.0 (+URL describing your work)".
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw
: "${S8_USER_AGENT:?set S8_USER_AGENT to a User-Agent that identifies you (EasyxLab uses 'EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)')}"
UA="$S8_USER_AGENT"
# 1. Registro de Entidades Locales (Ministerio de Politica Territorial): all municipalities (Excel)
curl -sS -f -A "$UA" -L -m 300 -o data/raw/rel_municipios.xls \
  "https://registroentidadeslocales.mpt.es/REL/frontend/export_data/file_export/export_excel/municipios/all/all"
# 2. INE, Relacion de municipios y codigos a 1 de enero de 2026 (used only as a check of the REL list)
curl -sS -f -A "$UA" -L -m 300 -o data/raw/ine_diccionario26.xlsx \
  "https://www.ine.es/daco/daco42/codmun/diccionario26.xlsx"
# 3. Wikidata: INE municipality code (P772) + official website (P856) with rank, dissolution (P576)
Q='SELECT ?item ?ine ?web ?rank ?dis WHERE { ?item wdt:P772 ?ine . OPTIONAL { ?item p:P856 ?st . ?st ps:P856 ?web ; wikibase:rank ?rank . } OPTIONAL { ?item wdt:P576 ?dis } }'
curl -sS -f -A "$UA" -m 300 -G "https://query.wikidata.org/sparql" --data-urlencode "query=$Q" \
  -H "Accept: text/csv" -o data/raw/wd_ine_web.csv
# 4. Junta de Comunidades de Castilla-La Mancha, Directorio de Entidades Locales (edition of June 2025).
#    The portal replaces the file when a new edition is published; if this URL fails, find the
#    current CSV on https://datosabiertos.castillalamancha.es/ and pass it as CLM_URL=...
CLM_URL="${CLM_URL:-https://datosabiertos.castillalamancha.es/sites/datosabiertos.castillalamancha.es/files/Entidades_Locales_CLM%20%28Junio_2025%29.csv}"
if ! curl -sS -f -A "$UA" -m 300 -o data/raw/clm_entidades.csv "$CLM_URL"; then
  echo "Castilla-La Mancha directory not found at $CLM_URL; set CLM_URL (see comment above)" >&2
  exit 1
fi
ls -l data/raw/rel_municipios.xls data/raw/ine_diccionario26.xlsx data/raw/wd_ine_web.csv data/raw/clm_entidades.csv
