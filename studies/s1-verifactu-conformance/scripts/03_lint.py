#!/usr/bin/env python3
"""Fase 3 — lint de cada contenido único con verifactu-lint (como librería).

Se lintea por **contenido** (sha256), no por ocurrencia: un fichero idéntico en cinco
repos se audita una vez. Cada fichero es su propia cadena, igual que hace la CLI.

Salida: data/raw/lint/<sha256>.json (detalle completo, con fragmentos de los datos del
fichero: no se publica) y private/lint_summary.json (hallazgos por regla y severidad).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from verifactu_lint import __version__
from verifactu_lint.registros import ErrorDeLectura, lee, lee_eventos
from verifactu_lint.reglas import audita, audita_eventos

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw" / "files"
OUT = BASE / "data" / "raw" / "lint"
PRIV = BASE / "private"
OUT.mkdir(parents=True, exist_ok=True)


def lintea(ruta: Path) -> dict:
    try:
        registros = lee(ruta)
        eventos = lee_eventos(ruta)
    except ErrorDeLectura as exc:
        return {"estado": "ilegible", "motivo": str(exc).split(": ", 1)[-1][:300]}
    hallazgos = []
    for inf in (audita(registros, fichero=ruta.name) if registros else None,
                audita_eventos(eventos, fichero=ruta.name) if eventos else None):
        if inf is None:
            continue
        for h in inf.hallazgos:
            hallazgos.append({"regla": h.regla, "severidad": h.severidad.value,
                              "titulo": h.titulo, "referencia": h.referencia,
                              "detalle": h.detalle, "norma": h.norma})
    return {
        "estado": "ok" if (registros or eventos) else "sin_registros",
        "n_alta": sum(r.tipo == "alta" for r in registros),
        "n_anulacion": sum(r.tipo == "anulacion" for r in registros),
        "n_evento": len(eventos),
        "n_emisores": len({(r.id_emisor or "").strip() for r in registros}),
        "hallazgos": hallazgos,
    }


def main() -> None:
    filas = list(csv.DictReader((PRIV / "classified.csv").open()))
    unicos = sorted({f["sha256"] for f in filas})
    resumen = {}
    for h in unicos:
        res = lintea(RAW / f"{h}.xml")
        res["version_lint"] = __version__
        (OUT / f"{h}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        resumen[h] = {k: v for k, v in res.items() if k != "hallazgos"}
        resumen[h]["por_regla"] = {}
        for x in res.get("hallazgos", []):
            k = f'{x["regla"]}:{x["severidad"]}'
            resumen[h]["por_regla"][k] = resumen[h]["por_regla"].get(k, 0) + 1
    (PRIV / "lint_summary.json").write_text(json.dumps(resumen, indent=1))
    print(f"{len(unicos)} contenidos únicos linteados con verifactu-lint {__version__}")


if __name__ == "__main__":
    main()
