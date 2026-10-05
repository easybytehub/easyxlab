#!/usr/bin/env bash
# Reproduce el estudio S1 de principio a fin. Cada fase es idempotente.
# Requisitos: gh autenticado, Python ≥ 3.11, red. ~25-40 min la primera vez
# (la búsqueda de código está limitada a 10 peticiones/minuto).
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  # Instrumento: verifactu-lint 0.4.0, siempre desde PyPI con la versión fijada
  # (0.4.1 cambia el resultado de 9 ficheros del corpus).
  .venv/bin/pip install -q "verifactu-lint==0.4.0"
fi
PY=.venv/bin/python
$PY scripts/01_collect.py          # GitHub → data/raw/files, private/occurrences.jsonl
$PY scripts/02_classify.py         # clasificación provisional (sin testcode)
$PY scripts/02b_testcode.py        # ¿el código de test espera un fallo?
$PY scripts/02_classify.py         # clasificación final
$PY scripts/03_lint.py             # verifactu-lint por contenido único
$PY scripts/04_stats.py            # agregados anonimizados → data/
$PY scripts/05_sample.py           # muestra para verificación manual → private/
