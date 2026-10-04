#!/usr/bin/env python3
"""Dated frame of the version history: EU texts (housing plan, RRF Regulation, the
Commission's June 2025 guidance, Council recommendations to Spain) and the Spanish
Government's statements. Every quotation is cut from the downloaded file by a pattern; the
script fails if a pattern does not match, so the quotations in data/ are literal.

Outputs: data/frame.csv (quotations) and data/timeline.csv (every dated event of the study,
with its source).
"""
import csv, glob, re
from s20lib import DATA, RAW, VERSIONS
from cidparse import plain_text

PRTR_URL = "https://planderecuperacion.gob.es/noticias/"
CELEX_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"


def cellar_text(celex):
    for f in sorted(glob.glob(str(RAW / "frame" / celex / "DOC_*.xhtml"))):
        b = open(f, "rb").read()
        if b.lstrip().startswith(b"<"):
            return re.sub(r"\s+", " ", plain_text(b.decode("utf-8")))
    raise FileNotFoundError(celex)


def prtr(slug):
    p = RAW / "prtr" / (slug + ".html")
    raw = open(p, encoding="utf-8").read()
    d = re.search(r'c-article-detail__date">\s*(\d\d)\.(\d\d)\.(\d{4})', raw)
    date = f"{d.group(3)}-{d.group(2)}-{d.group(1)}" if d else ""
    return date, re.sub(r"\s+", " ", plain_text(raw))


SENT = r"(?:[^.]|\.(?=\d))*\."   # up to the end of the sentence; "15.000" is not an end


def cut(text, pattern, src):
    m = re.search(pattern.replace(r"[^.]*\.", SENT), text)
    if not m:
        raise SystemExit(f"pattern not found in {src}: {pattern}")
    return m.group(0).strip()


EU = [  # id, celex, date, label, pattern
    ("eahp-spain", "52025DC1025", "2025-12-16", "European Affordable Housing Plan, COM(2025) 1025 (Strasbourg, 16.12.2025): its only mention of Spain",
     r"Spain’s Strategic Project for Economic Recovery and Transformation on industrialised construction aims to provide 15,000 affordable[^.]*\."),
    ("eahp-semester", "52025DC1025", "2025-12-16", "European Affordable Housing Plan: housing in the European Semester",
     r"help Member States design effective reforms for affordable and social housing through stronger monitoring and targeted recommendations under the European Semester"),
    ("eahp-rrf", "52025DC1025", "2025-12-16", "European Affordable Housing Plan: its only mention of the RRF",
     r"Out of its allocated EUR 2\.7 billion RRF budget for the provision of social and affordable housing, Portugal[^.]*\."),
    ("rrf-art18", "32021R0241", "2021-02-12", "Regulation (EU) 2021/241, Article 18(4)(i)",
     r"envisaged milestones, targets and an indicative timetable for the implementation of the reforms, and investments to be completed by 31 August 2026"),
    ("rrf-art24", "32021R0241", "2021-02-12", "Regulation (EU) 2021/241, Article 24(1)",
     r"Payments of financial contributions and, where applicable, of the loan to the Member State concerned under this Article shall be made by 31 December 2026"),
    ("road2026-revise", "52025DC0310", "2025-06-04", "Commission, NextGenerationEU – The road to 2026, COM(2025) 310",
     r"the Commission urges Member States to undertake such plan revisions as soon as possible and, in any event, by the end of 2025"),
    ("road2026-noamend", "52025DC0310", "2025-06-04", "Commission, NextGenerationEU – The road to 2026, COM(2025) 310",
     r"there is no scope for adopting amendments of RRPs after 31 August 2026"),
    ("road2026-requests", "52025DC0310", "2025-06-04", "Commission, NextGenerationEU – The road to 2026, COM(2025) 310",
     r"All payment requests, including the management declarations,[^.]*?must be submitted by 30 September 2026"),
]

ES = [  # id, slug, label, pattern
    ("es-ico-2023", "gobierno-aprueba-linea-prestamos-4000-millones-promover-viviendas-alquiler-asequible-prtr",
     "Government: launch of the ICO social-housing line", r"El Gobierno aprueba una línea de préstamos de 4\.000 M€ para promover hasta 43\.000 viviendas en alquiler asequible"),
    ("es-adenda-2023", "consejo-ministros-aprueba-adenda-ampliacion-Plan-Recuperacion-Transformacion-Resiliencia-prtr",
     "Government: approval of the 2023 addendum (loans and REPowerEU)", r"El Consejo de Ministros ha aprobado[^.]*\."),
    ("es-adenda-simplificacion", "gobierno-aprueba-adenda-simplificacion-plan-recuperacion-prtr",
     "Government: approval of the «Adenda de Simplificación»", r"El Consejo de Ministros ha aprobado la Adenda de Simplificación[^.]*\."),
    ("es-espana-crece", "pedro-sanchez-anuncia-fondo-espana-crece-movilizara-hasta-23000-millones-vivienda-prtr",
     "Government: España Crece fund announced", r"el nuevo fondo España Crece movilizará hasta 23\.000 millones de euros[^.]*\."),
    ("es-cid-jan2026", "gobierno-pone-marcha-inyeccion-13300-millones-ico-activar-fondo-espana-crece-prtr",
     "Government: España Crece capital transfer; cites the December amendment's adoption date", r"conforme a los términos exigidos en el Anexo a la Decisión de Ejecución del Consejo de 13 de enero de 2026"),
    ("es-adenda-cierre", "gobierno-aprueba-adenda-cierre-plan-recuperacion-culminar-ejecucion-prtr",
     "Government: approval of the «Adenda de Cierre»; its stated scope", r"La Adenda de cierre mejora la redacción de 121 hitos y objetivos y 101 medidas[^.]*\."),
    ("es-adenda-cierre-loans", "gobierno-aprueba-adenda-cierre-plan-recuperacion-culminar-ejecucion-prtr",
     "Government: the closing addendum's loan adjustment", r"los recursos se adaptan a la demanda demostrada por las empresas[^.]*\."),
    ("es-ico-toledo", "ico-destina-32-millones-financiar-construccion-316-viviendas-alquiler-asequible-toledo-prtr",
     "Government site, ICO loan in Toledo: how the line is described after the August cut", r"El préstamo se enmarca en la Línea ICO Vivienda ?, dotada con 4\.000 millones de euros[^.]*\."),
    ("es-pr6", "espana-solicita-sexto-pago-plan-de-recuperacion-7256-millones-prtr",
     "Government: sixth payment request", r"España ha dado un paso decisivo[^.]*\."),
    ("es-pr7-housing", "espana-solicita-septimo-ultimo-pago-plan-de-recuperacion-25861-millones-prtr",
     "Government: seventh and last payment request, housing", r"Vivienda y rehabilitación ?: Se ha iniciado la construcción de 23\.000 viviendas[^.]*\.[^.]*\."),
    ("es-pr7", "espana-solicita-septimo-ultimo-pago-plan-de-recuperacion-25861-millones-prtr",
     "Government: seventh payment request, size", r"La solicitud está referida a 148 hitos y objetivos[^.]*\."),
    ("es-adoption-aug2026", "carlos-cuerpo-comparece-comision-mixta-UE-congreso-informar-cierre-plan-de-recuperacion-prtr",
     "Government (Minister of Economy before the Joint Committee for the EU): adoption of the closing addendum", r"El 27 de agosto el Consejo adoptó la adenda técnica de cierre[^.]*\."),
]


MONCLOA = [  # id, file stem, date, label, pattern
    ("moncloa-2025-12-09-160", "moncloa_20251209-referencia-rueda-de-prensa-ministros", "2025-12-09",
     "La Moncloa, Referencia del Consejo de Ministros: the simplification addendum's scope",
     r"Se han modificado alrededor de 160 medidas\. Ejemplos de ello son la eliminación de: \(i\) lenguaje ambiguo o confuso, \(ii\) cualquier especificación innecesaria para demostrar el cumplimiento de las medidas de los planes de recuperación, \(iii\) hitos y objetivos intermedios\."),
    ("moncloa-2025-12-09-acuerdo", "moncloa_20251209-referencia-rueda-de-prensa-ministros", "2025-12-09",
     "La Moncloa, Referencia del Consejo de Ministros: approval of the simplification addendum",
     r"ACUERDO por el que se aprueba la Adenda de Simplificación al Plan de Recuperación, Transformación y Resiliencia\."),
    ("moncloa-2026-07-28-acuerdo", "moncloa_20260728-referencia-rueda-de-prensa-ministros", "2026-07-28",
     "La Moncloa, Referencia del Consejo de Ministros: approval of the closing addendum",
     r"ACUERDO por el que se aprueba la adenda de cierre del Plan de Recuperación, Transformación y Resiliencia\."),
]
MONCLOA_URL = "https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/"


def main():
    out = []
    for i, stem, date, label, pat in MONCLOA:
        t = re.sub(r"\s+", " ", plain_text(open(RAW / "prtr" / (stem + ".html"), encoding="utf-8", errors="replace").read()))
        url = MONCLOA_URL + date[:4] + "/" + stem.replace("moncloa_", "") + ".aspx"
        out.append({"id": i, "date": date, "source": label, "url": url, "literal": cut(t, pat, stem)})
    for i, celex, date, label, pat in EU:
        out.append({"id": i, "date": date, "source": label, "url": CELEX_URL + celex, "literal": cut(cellar_text(celex), pat, celex)})
    for i, slug, label, pat in ES:
        date, t = prtr(slug)
        out.append({"id": i, "date": date, "source": label, "url": PRTR_URL + slug, "literal": cut(t, pat, slug)})
    # Council recommendations to Spain: the operative housing sentences
    for r in csv.DictReader(open(RAW / "frame" / "sparql_csr_spain.csv", encoding="utf-8")):
        t = cellar_text(r["celex"])
        parts = t.split("HEREBY RECOMMENDS")
        op = parts[1] if len(parts) > 1 else ""
        op = re.sub(r"Done at [^.]*\.", " ", op)
        sents = [s.strip() for s in re.split(r"(?<=\.)\s|(?=\s\d\.\s)", op) if re.search(r"housing", s, re.I)]
        out.append({"id": "csr-" + r["date"][:4] + ("b" if r["celex"] == "32025H00643" else ""), "date": r["date"],
                    "source": r["title"][:200], "url": CELEX_URL + r["celex"],
                    "literal": " … ".join(sents) if sents else "(no operative recommendation on housing)"})
    with open(DATA / "frame.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    # timeline
    tl = []
    adopt = {r["version"]: r for r in csv.DictReader(open(DATA / "adoption.csv", encoding="utf-8"))}
    for label, celex, com, date in VERSIONS:
        a = adopt[label]
        tl.append({"date": a["spain_request"], "event": f"Spain's request behind {com} ({label})", "source": f"{com}, recital 2"})
        tl.append({"date": date, "event": f"Commission proposal {com} ({label})", "source": f"Cellar, CELEX {celex}"})
        tl.append({"date": a["adopted"], "event": f"Council adoption of {com} ({label}); {a['status']}", "source": a["source"]})
    for o in out:
        tl.append({"date": o["date"], "event": o["source"], "source": o["url"]})
    for r in csv.DictReader(open(DATA / "scoreboard_versions.csv", encoding="utf-8")):
        for d in filter(None, r["disbursement_dates"].split(";")):
            dd, mm, yy = d.split("/")
            tl.append({"date": f"{yy}-{mm}-{dd}", "event": f"Disbursement covering {r['measure']} {r['number']} ({r['loans_grants']}, instalment {r['instalment']})",
                       "source": "Recovery and Resilience Scoreboard"})
    tl.sort(key=lambda x: (x["date"], x["event"]))
    with open(DATA / "timeline.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "event", "source"])
        w.writeheader()
        w.writerows(tl)
    for o in out:
        print(o["id"], o["date"], o["literal"][:110])


if __name__ == "__main__":
    main()
