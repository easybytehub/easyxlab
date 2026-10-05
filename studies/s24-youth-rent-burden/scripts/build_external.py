#!/usr/bin/env python3
"""S24: published figures used beside the microdata, from the locked files in data/raw/.

  eurostat_series.csv   Eurostat ilc_lvho07c (tenure), ilc_lvho07a (age), ilc_lvps08 (living with
                        parents), yth_demo_030 (age at leaving home): Spain and EU-27
  ipva.csv              INE IPVA (rents declared to the tax agency): index by contract age (new vs
                        existing contracts) and national weights by contract age and dwelling size
  quotes.csv            literal sentences this study relies on (CJE, INE, Eurostat), with their source,
                        checked here against the locked files so a changed source is noticed
"""
from __future__ import annotations

import csv
import html
import json
import re
import subprocess
import sys

from jsonstat import rows as jrows
from s24lib import D, RAW


def norm(s: str) -> str:
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"(\w)- (\w)", r"\1\2", s)          # words hyphenated across PDF lines


def pdf_text(path) -> str:
    """Text of a PDF in layout order and in reading order (sidebars interleave with the body in layout
    mode), joined, so a quotation is found in either."""
    parts = []
    for mode in (["-layout"], []):
        try:
            out = subprocess.run(["pdftotext", *mode, str(path), "-"], capture_output=True, check=True).stdout
            parts.append(norm(out.decode("utf-8", "replace")))
        except Exception:
            pass
    return " ||| ".join(parts)


def main():
    rows = []
    for t in ("ilc_lvho07c", "ilc_lvho07a", "ilc_lvps08", "yth_demo_030"):
        meta, data = jrows(RAW / "eurostat" / f"{t}.json")
        for r in data:
            if t == "ilc_lvho07a" and (r["sex"] != "T" or r["rskpovth"] != "TOTAL"):
                continue
            if t in ("ilc_lvps08", "yth_demo_030") and r["sex"] != "T":
                continue
            group = r.get("tenure") or r.get("age") or "T"
            rows.append({"table": t, "geo": r["geo"], "group": group, "year": r["time"], "value": r["value"],
                         "flag": r["flag"], "updated": meta.get("updated", "")})
    with open(D / "eurostat_series.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    ipva = []
    for tid in ("59004", "59008", "59063"):
        for s in json.load(open(RAW / "ine" / f"ipva_{tid}.json", encoding="utf-8")):
            name = s["Nombre"]
            if not name.startswith("Total Nacional"):
                continue
            for x in s["Data"]:
                ipva.append({"table": tid, "series": name.strip(), "year": x["Anyo"], "value": x["Valor"]})
    with open(D / "ipva.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["table", "series", "year", "value"])
        w.writeheader()
        w.writerows(ipva)

    # literal quotes, verified against the locked sources
    cje25 = pdf_text(RAW / "cje" / "2025-balance-general.pdf")
    cje24 = pdf_text(RAW / "cje" / "2024-2sem_informe-estatal-1.pdf")
    cje24n = pdf_text(RAW / "cje" / "2024-2sem_nota-metodologica-1.pdf")
    src = {
        "cje25": cje25, "cje24": cje24, "cje24n": cje24n,
        "ecv2017": pdf_text(RAW / "ine" / "ecv_2017.pdf"), "ecv2019": pdf_text(RAW / "ine" / "ecv_2019.pdf"),
        "ecv2021": pdf_text(RAW / "ine" / "ecv_2021.pdf"), "ecv2022": pdf_text(RAW / "ine" / "ecv_2022.pdf"),
        "ecv2023": norm(open(RAW / "ine" / "ECV2023.htm", encoding="utf-8", errors="replace").read()),
        "ecv2024": norm(open(RAW / "ine" / "ECV2024.htm", encoding="utf-8", errors="replace").read()),
        "ecv2025": norm(open(RAW / "ine" / "ECV2025.htm", encoding="utf-8", errors="replace").read()),
        "m3": norm(open(RAW / "ine" / "m3ECV2025.htm", encoding="utf-8", errors="replace").read()),
        "fedea": pdf_text(RAW / "prior" / "fedea_eee2026-28.pdf"),
    }
    quotes = [
        ("cje25", "CJE 2025, p. 5", "Una persona joven asalariada tiene que destinar el 98,7 % de su salario para pagar un alquiler en solitario, incluso compartir piso (opción que ya no es una elección sino una necesidad) requiere el 33,6 % de nuestro salario superando el umbral de cualquier límite de asequibilidad que fijan los organismos internacionales (que por cierto fijan para el acceso a una vivienda, no a una habitación en un piso compartido)."),
        ("cje25", "CJE 2025, p. 5 (margin)", "Alquilar en solitario supone el 98,7 % del salario de una persona joven. Compartir piso, el 33,6 %."),
        ("cje25", "CJE 2025, p. 23 (table)", "Renta mediana alquiler habitación (euros/mes) 400,00"),
        ("fedea", "FEDEA eee2026-28 (Conde-Ruiz and Pinto), section on burden by tenure", "Parte de esta mejora coincide con el fuerte crecimiento en número de hogares y personas de este régimen, que introduce mayor heterogeneidad interna"),
        ("cje25", "CJE 2025, p. 8", "alquilar una vivienda libre costaba de media 1.176 euros mensuales"),
        ("cje25", "CJE 2025, p. 8", "situándose en 14.292,22 euros anuales"),
        ("cje25", "CJE 2025, p. 9", "el 98,7 % de su salario neto mensual para poder alquilar una vivienda en solitario"),
        ("cje25", "CJE 2025, nota metodológica (renta de alquiler)", "Precio de oferta de las viviendas libres en alquiler que recogen los informes que publica el portal Idealista.com, aplicando una superficie media de 80 metros cuadrados construidos"),
        ("cje25", "CJE 2025, nota metodológica (salario)", "Cálculo propio del salario neto mediano de una persona joven que trabaja por cuenta ajena, obtenido de aplicar al último dato disponible de la Encuesta Trimestral de Coste Laboral (ETCL-INE), previa desestacionalización, la estructura salarial por tramos de edad y sexo y el modelo de conversión de salarios brutos a netos de la ECV, simplificado en deciles"),
        ("cje25", "CJE 2025, nota metodológica (cambio de fuente)", "no son directamente comparables con las publicadas en ediciones anteriores del Observatorio, que se basaban en la Encuesta de Población Activa"),
        ("cje25", "CJE 2025, p. 22 (coste de la vivienda actual)", "el gasto medio en alquiler de los hogares jóvenes se situó en 780 € mensuales para la población de 16 a 29 años que representaba el 30 % de los ingresos netos del hogar joven"),
        ("cje25", "CJE 2025, p. 22", "el 48,9 % de los hogares jóvenes de 16 a 29 años en alquiler destinaban más del 40 % de sus ingresos al pago de la vivienda"),
        ("cje25", "CJE 2025, nota metodológica (coste de la vivienda)", "El gasto mensual en vivienda recoge el importe total que el hogar destina mensualmente a la vivienda principal, incluyendo el alquiler (en hogares arrendatarios) o los pagos asociados a la propiedad, incluyendo la cuota hipotecaria, comunidad, suministros y otros gastos corrientes vinculados al inmueble"),
        ("cje25", "CJE 2025, nota metodológica (hogares jóvenes)", "Se han considerado como “hogares jóvenes” aquellos en los que hay personas jóvenes emancipadas, independientemente de la edad de la persona que figura como “persona de referencia”"),
        ("cje24n", "CJE 2S-2024, nota metodológica", "Cálculo propio de la relación entre la capacidad adquisitiva de una persona joven (o de un hogar joven ya existente) y el importe mensual de un alquiler de mercado"),
        ("cje24", "CJE 2S-2024, informe estatal", "En el segundo semestre de 2024, solo el 15,2 % de la población joven estaba emancipada"),
        ("ecv2017", "INE, ECV 2017", "La muestra del INE fue recogida en el tercer cuatrimestre de 2017"),
        ("ecv2019", "INE, ECV 2019", "Periodo de recogida: Tercer cuatrimestre de 2019"),
        ("ecv2021", "INE, ECV 2021", "Periodo de recogida: Tercer cuatrimestre de 2021"),
        ("ecv2021", "INE, ECV 2021", "A partir de la encuesta de 2021 se ha introducido el método multicanal"),
        ("ecv2022", "INE, ECV 2022", "Periodo de recogida: Segundo cuatrimestre de 2022"),
        ("ecv2023", "INE, ECV 2023", "de febrero a mayo de 2023"),
        ("ecv2024", "INE, ECV 2024", "De febrero a mayo de 2024"),
        ("ecv2025", "INE, ECV 2025", "De febrero a mayo de 2025"),
        ("m3", "INE, ECV 2025 module", "El 67,1% de las personas de 18 a 34 años convivía con alguno de sus progenitores en 2025"),
        ("m3", "INE, ECV 2025 module", "Un 47,3% de los jóvenes de 26 a 34 años que convivían con sus padres indicó como razón principal de convivencia que no se podía permitir comprar o alquilar una vivienda"),
    ]
    out, missing = [], 0
    for key, where, q in quotes:
        found = norm(q) in src[key]
        missing += not found
        out.append({"source": where, "quote": q, "found_in_locked_file": found})
    # the chart note of the CJE 2025 report is printed letter-spaced in the PDF; compare without spaces
    chart = "Se muestra la tasa de emancipación del segundo semestre de cada edición del Observatorio de Emancipación hasta 2024. En 2025, se muestra a la tasa de emancipación calculada con la nueva metodología."
    found = chart.replace(" ", "") in cje25.replace(" ", "")
    missing += not found
    out.append({"source": "CJE 2025, p. 7, note under «Tasa de Emancipación Joven en España (2006-2025)»", "quote": chart,
                "found_in_locked_file": found})
    with open(D / "quotes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source", "quote", "found_in_locked_file"])
        w.writeheader()
        w.writerows(out)
    print(f"eurostat rows {len(rows)}, ipva rows {len(ipva)}, quotes {len(out)} ({missing} not found)")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
