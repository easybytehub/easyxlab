#!/usr/bin/env python3
"""Fase 5 — muestra estratificada de hallazgos para verificación manual.

Estratos: (regla, severidad) de los hallazgos ERROR y AVISO sobre ficheros de clase
(a). Hasta 2 hallazgos por estrato, con semilla fija, de ficheros distintos. La
muestra (con rutas reales) va a private/verification_sample.json; el veredicto de
cada uno se registra a mano en VERIFICATION.md, anonimizado.

Incluye una comprobación independiente de RRSIF001: la huella se recalcula con una
implementación escrita aquí desde el texto de la Orden HAC/1177/2024 art. 13 y la
especificación de la AEAT (concatenación «campo=valor&…», SHA-256, hex mayúsculas),
sin importar nada de verifactu-lint.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PRIV = BASE / "private"
RAW = BASE / "data" / "raw"


def _v(xml: str, tag: str) -> str:
    m = re.search(rf"<(?:\w+:)?{tag}>([^<]*)</(?:\w+:)?{tag}>", xml)
    return m.group(1).strip() if m else ""


def huella_independiente(bloque: str) -> tuple[str, str]:
    """Huella de un RegistroAlta/Anulacion según el texto de la norma (sin verifactu-lint)."""
    enc = re.search(r"<(?:\w+:)?Encadenamiento>(.*?)</(?:\w+:)?Encadenamiento>", bloque, re.S)
    ant = _v(enc.group(1), "Huella") if enc else ""
    idf = re.search(r"<(?:\w+:)?IDFactura>(.*?)</(?:\w+:)?IDFactura>", bloque, re.S)
    idf = idf.group(1) if idf else ""
    if "IDEmisorFacturaAnulada" in idf:
        campos = [
            ("IDEmisorFacturaAnulada", _v(idf, "IDEmisorFacturaAnulada")),
            ("NumSerieFacturaAnulada", _v(idf, "NumSerieFacturaAnulada")),
            ("FechaExpedicionFacturaAnulada", _v(idf, "FechaExpedicionFacturaAnulada")),
            ("Huella", ant),
            ("FechaHoraHusoGenRegistro", _v(bloque, "FechaHoraHusoGenRegistro")),
        ]
        cadena = "&".join(f"{k}={v}" for k, v in campos)
        return hashlib.sha256(cadena.encode("utf-8")).hexdigest().upper(), cadena
    campos = [
        ("IDEmisorFactura", _v(idf, "IDEmisorFactura")),
        ("NumSerieFactura", _v(idf, "NumSerieFactura")),
        ("FechaExpedicionFactura", _v(idf, "FechaExpedicionFactura")),
        ("TipoFactura", _v(bloque, "TipoFactura")),
        ("CuotaTotal", _v(bloque, "CuotaTotal")),
        ("ImporteTotal", _v(bloque, "ImporteTotal")),
        ("Huella", ant),
        ("FechaHoraHusoGenRegistro", _v(bloque, "FechaHoraHusoGenRegistro")),
    ]
    cadena = "&".join(f"{k}={v}" for k, v in campos)
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest().upper(), cadena


def main() -> None:
    filas = list(csv.DictReader((PRIV / "classified.csv").open()))
    estado = json.loads((PRIV / "collect_state.json").read_text())
    fork = {r for r, m in estado["repos"].items() if m.get("fork")}
    a = {}
    for f in filas:
        if f["clase"] == "a" and f["repo"] not in fork:
            a.setdefault(f["sha256"], f)
    estratos: dict[str, list[tuple[str, dict]]] = {}
    for h, occ in a.items():
        p = RAW / "lint" / f"{h}.json"
        if not p.exists():
            continue
        for x in json.loads(p.read_text()).get("hallazgos", []):
            if x["severidad"] in ("error", "aviso"):
                estratos.setdefault(f'{x["regla"]}:{x["severidad"]}', []).append((h, x))
    rnd = random.Random(20261002)
    muestra = []
    for k in sorted(estratos):
        vistos = set()
        cands = estratos[k][:]
        rnd.shuffle(cands)
        for h, x in cands:
            if h in vistos:
                continue
            vistos.add(h)
            occ = a[h]
            item = {"estrato": k, "sha256": h, "repo": occ["repo"], "commit": occ["commit"],
                    "path": occ["path"], "hallazgo": x}
            muestra.append(item)
            if len(vistos) >= 2:
                break
    # Comprobación independiente de TODOS los RRSIF001 «no coincide» de clase (a).
    indep = []
    for h, occ in a.items():
        p = RAW / "lint" / f"{h}.json"
        if not p.exists():
            continue
        xml = (RAW / "files" / f"{h}.xml").read_bytes().decode("utf-8", "ignore")
        bloques = re.findall(
            r"<(?:\w+:)?(?:RegistroAlta|RegistroAnulacion)(?:\s[^>]*)?>.*?"
            r"</(?:\w+:)?(?:RegistroAlta|RegistroAnulacion)>", xml, re.S)
        for x in json.loads(p.read_text()).get("hallazgos", []):
            if x["regla"] != "RRSIF001" or "no coincide" not in x["titulo"]:
                continue
            n = int(re.match(r"#(\d+)", x["referencia"]).group(1)) - 1
            if n >= len(bloques):
                continue
            calc, cad = huella_independiente(bloques[n])
            decl = _v(re.split(r"</(?:\w+:)?Encadenamiento>", bloques[n])[-1], "Huella")
            indep.append({"sha256": h, "path": occ["path"], "repo": occ["repo"],
                          "referencia": x["referencia"], "declarada": decl.upper(),
                          "independiente": calc, "coincide_con_independiente":
                          calc == decl.strip().upper(), "cadena": cad})
    (PRIV / "rrsif001_independiente.json").write_text(
        json.dumps(indep, indent=1, ensure_ascii=False))
    print(f"RRSIF001: {len(indep)} hallazgos recalculados de forma independiente; "
          f"{sum(i['coincide_con_independiente'] for i in indep)} coinciden con la "
          "huella declarada (serían falsos positivos)")
    (PRIV / "verification_sample.json").write_text(
        json.dumps(muestra, indent=1, ensure_ascii=False))
    print(f"{len(muestra)} hallazgos en la muestra de {len(estratos)} estratos")


if __name__ == "__main__":
    main()
