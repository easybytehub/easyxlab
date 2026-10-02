#!/usr/bin/env python3
"""Fase 2 — clasificación de cada XML ANTES de lintarlo.

Clases (ver METHOD.md §3):
  a  ejemplo que pretende ser un registro válido
  b  test negativo deliberadamente inválido (no cuenta como incumplimiento)
  c  respuesta de la AEAT u otro artefacto que no es un registro
  d  plantilla o esquema (marcadores de plantilla, placeholders, XSLT/XSD/WSDL)
  e  XML con el marcador pero sin RegistroAlta/RegistroAnulacion/RegistroEvento
     (p. ej. consulta, cabecera sola): no hay nada que lintar

La clasificación es determinista y se aplica a la *ocurrencia* (repo + ruta), no al
contenido: el mismo fichero puede ser un ejemplo en un repo y un test negativo en
otro. La regla de prioridad es c > d > e > b > a.

La señal de test negativo sale de tres fuentes, y se registra cuál disparó:
  path     tokens negativos en la ruta o el nombre. «reject»/«rechazo» NO cuentan: en
           Verifactu `RechazoPrevio` es un escenario VÁLIDO (subsanar tras rechazo), y la
           revisión manual encontró un fixture positivo «…-rejection-correction.xml»
           clasificado como negativo por ese token.
  comment  comentarios XML que anuncian el defecto («inválido», «debe fallar»…)
  testcode el código de test del repo referencia el fichero junto a una aserción de
           error (lo rellena 02b_testcode.py; aquí solo se lee su salida)
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw" / "files"
PRIV = BASE / "private"

NEG_PATH = re.compile(
    r"(invalid|inv[aá]lid|error|defect|err[oó]ne|\bbad|bad[_\-.]|fail|wrong|broken|corrupt|"
    r"malformed|negative|incorrect|tamper|manipul|(^|[_\-./])ko([_\-./]|$)|"
    r"(^|[_\-./])mal[_\-]|(^|[_\-./])rot[oa]([_\-./]|$)|missing|duplicat|duplicad|"
    r"mismatch|descuadr|no[_\-]?valid|nok([_\-./]|$))",
    re.I,
)
NEG_COMMENT = re.compile(
    r"<!--[^>]*?(inv[aá]lid|incorrect|err[oó]ne|debe fallar|should fail|must fail|"
    r"rechaz|reject|wrong|bad hash|huella (mal|incorrecta)|negative test|caso de error)"
    r"[^>]*?-->",
    re.I | re.S,
)
RESPUESTA = re.compile(
    rb"<(?:[\w.\-]+:)?(Respuesta\w*|RespuestaLinea|EstadoEnvio|EstadoRegistro|"
    rb"CodigoErrorRegistro|Fault)[\s>/]"
)
PLANTILLA = re.compile(
    rb"(\{\{|\{%|\$\{|<\?php|<%|#\{|@\{|\bth:|<xsl:|<xs:schema|<xsd:schema|<wsdl:|"
    rb"\{\$|\[\[|%\(\w+\)s|\{[A-Za-z_][\w.]*\}(?=<)|>\s*%s\s*<|>\s*\{\d+\}\s*<)"
)
SOAPUI_PH = re.compile(rb">\s*\?\s*<")
# Valores de relleno en campos clave: los ejemplos del documento de la AEAT
# «Descripción del servicio web» (ap. 9) usan literalmente <Huella>Huella</Huella>,
# <Huella>HuellaRegistroAnterior</Huella>, <IDEmisorFactura>AAAA</IDEmisorFactura>,
# <NIF>NNNN</NIF>. Un fichero con esos valores es una plantilla ilustrativa, no un
# registro que pretenda ser válido. También hashes ficticios (64 ceros, un solo
# carácter repetido) y marcadores tipo «XXXX».
RELLENO = re.compile(
    rb"<(?:[\w.\-]+:)?(Huella|IDEmisorFactura|IDEmisorFacturaAnulada|NIF|NumSerieFactura|NumSerieFacturaAnulada)>\s*("
    rb"[Hh]uella\w*|([A-Za-z])\3{2,}|X{3,}|x{3,}|\.\.\.|string|\?|"
    rb"([0-9A-Fa-f])\4{63}|(0123456789ABCDEF){4}|(ABCDEF0123456789){4})\s*<"
)
REGISTRO = re.compile(rb"<(?:[\w.\-]+:)?(RegistroAlta|RegistroAnulacion|RegistroEvento)[\s>]")


# El repositorio del propio instrumento queda fuera: sus ejemplos están escritos para
# disparar (o no) sus reglas, y contarlos sería medir el instrumento contra sí mismo.
EXCLUIDOS = re.compile(r"^easybytehub/", re.I)


def clasifica(occ: dict, contenido: bytes, testcode: dict) -> tuple[str, str]:
    if EXCLUIDOS.search(occ["repo"]):
        return "x", "repo_del_instrumento"
    if RESPUESTA.search(contenido) and not REGISTRO.search(contenido):
        return "c", "respuesta"
    if RESPUESTA.search(contenido):
        # Respuestas de consulta que reproducen registros: siguen siendo respuestas.
        return "c", "respuesta_con_registro"
    if PLANTILLA.search(contenido):
        return "d", "marcador_plantilla"
    if len(SOAPUI_PH.findall(contenido)) >= 3:
        return "d", "placeholder_soapui"
    if REGISTRO.search(contenido) and RELLENO.search(contenido):
        return "d", "valores_de_relleno"
    if not REGISTRO.search(contenido):
        return "e", "sin_registros"
    if NEG_PATH.search(occ["path"]):
        return "b", "path"
    if NEG_COMMENT.search(contenido.decode("utf-8", "ignore")):
        return "b", "comment"
    key = f'{occ["repo"]}|{occ["path"]}'
    if testcode.get(key, {}).get("negativo"):
        return "b", "testcode"
    return "a", "por_defecto"


def main() -> None:
    occs = [json.loads(x) for x in (PRIV / "occurrences.jsonl").read_text().splitlines()]
    occs = [o for o in occs if o.get("status") == "ok"]
    tc_f = PRIV / "testcode.json"
    testcode = json.loads(tc_f.read_text()) if tc_f.exists() else {}
    filas = []
    for o in occs:
        contenido = (RAW / f'{o["sha256"]}.xml').read_bytes()
        clase, motivo = clasifica(o, contenido, testcode)
        filas.append({**{k: o[k] for k in ("repo", "commit", "path", "sha256")},
                      "via": "+".join(o["via"]), "clase": clase, "motivo": motivo})
    with (PRIV / "classified.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    from collections import Counter
    print(Counter((r["clase"], r["motivo"]) for r in filas), file=sys.stderr)


if __name__ == "__main__":
    main()
