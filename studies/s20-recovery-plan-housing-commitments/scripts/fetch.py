#!/usr/bin/env python3
"""Download every source S20 uses into data/raw/ (git-ignored). Polite: robots.txt checked, at
most one request per second per host, fixed User-Agent, every request logged in
work/fetch_log.jsonl, 120 s timeout per request. Resumable: files that exist are kept (pass
--refetch to download again).

  python3 scripts/fetch.py proposals   Commission proposals (CID versions), XHTML from Cellar
  python3 scripts/fetch.py council     Council texts of each version (ST documents, PDF)
  python3 scripts/fetch.py frame       EU housing plan, RRF Regulation, Council recommendations to Spain
  python3 scripts/fetch.py prtr        Spanish Government pages on planderecuperacion.gob.es
  python3 scripts/fetch.py others      August 2026 amending decisions of other member states
  python3 scripts/fetch.py all         everything above

Run it in the background (`nohup python3 scripts/fetch.py all > work/fetch.log 2>&1 &`).
"""
import csv, os, re, sys
from s20lib import RAW, VERSIONS, CELLAR, fetch, sparql, manifestations

REFETCH = "--refetch" in sys.argv
XSD = "<http://www.w3.org/2001/XMLSchema#string>"
CDM = "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
ENG = "<http://publications.europa.eu/resource/authority/language/ENG>"

Q_PROPOSALS = CDM + """SELECT DISTINCT ?celex ?date ?title WHERE {
  ?w cdm:resource_legal_id_celex ?celex .
  ?w cdm:work_date_document ?date .
  ?e cdm:expression_belongs_to_work ?w ;
     cdm:expression_title ?title ;
     cdm:expression_uses_language %s .
  FILTER(CONTAINS(LCASE(STR(?title)), "recovery and resilience plan for spain"))
} ORDER BY ?date""" % ENG

Q_COUNCIL = CDM + """SELECT DISTINCT ?celex ?dossier ?council_doc ?date ?type WHERE {
  ?w cdm:resource_legal_id_celex ?celex ; cdm:act_preparatory_initiates_dossier ?dossier .
  FILTER(STR(?celex) IN (%s))
  ?w2 cdm:work_part_of_dossier ?dossier ; cdm:work_id_document ?council_doc .
  FILTER(STRSTARTS(STR(?council_doc), "consil:"))
  OPTIONAL { ?w2 cdm:work_date_document ?date }
  OPTIONAL { ?w2 cdm:work_has_resource-type ?type }
} ORDER BY ?celex ?date ?council_doc"""

Q_EVENTS = CDM + """SELECT DISTINCT ?celex ?procedure ?event_type ?event_date WHERE {
  ?w cdm:resource_legal_id_celex ?celex ; cdm:act_preparatory_initiates_dossier ?dossier .
  FILTER(STR(?celex) IN (%s))
  OPTIONAL { ?dossier cdm:procedure_code_interinstitutional_reference_procedure ?procedure }
  OPTIONAL { ?ev cdm:event_legal_part_of_dossier ?dossier ;
                 cdm:event_legal_has_type_concept_type_event_legal ?event_type ;
                 cdm:event_legal_date ?event_date }
} ORDER BY ?celex ?event_date"""

# Every Council document holding the text of a version as prepared for, or recorded after,
# adoption (the decision "INIT"/"REV" and its annex "ADD 1"), as listed by Cellar on 2026-10-04
# (data/raw/sparql_council_spain_all.csv). COM(2025) 794 has no such document in Cellar.
COUNCIL_DOCS = {
    "v0-2021": ["ST_10150_2021_INIT", "ST_10150_2021_ADD_1_REV_2"],
    "v1-2023": ["ST_13695_2023_REV_1", "ST_13695_2023_ADD_1_REV_1"],
    "v2-2024a": ["ST_9303_2024_INIT", "ST_9303_2024_ADD_1"],
    "v3-2024b": ["ST_17099_2024_INIT", "ST_17099_2024_ADD_1"],
    "v4-2025a": ["ST_8053_2025_INIT", "ST_8053_2025_ADD_1"],
    "v5-2025b": ["ST_9583_2025_INIT", "ST_9583_2025_ADD_1", "ST_9583_2025_ADD_1_COR_1"],
    "v6-2025c": ["ST_13075_2025_INIT", "ST_13075_2025_ADD_1"],
    "v7-2025d": [],
    "v8-2026a": ["ST_9518_2026_ADD_1"],
    "v9-2026b": ["ST_12355_2026_INIT", "ST_12355_2026_ADD_1"],
}

Q_ITEMS = CDM + """SELECT DISTINCT ?mtype ?item WHERE {
  ?w cdm:work_id_document "consil:%s"^^""" + XSD + """ .
  ?e cdm:expression_belongs_to_work ?w ; cdm:expression_uses_language """ + ENG + """ .
  ?m cdm:manifestation_manifests_expression ?e ; cdm:manifestation_type ?mtype .
  ?item cdm:item_belongs_to_manifestation ?m .
}"""

# Frame documents (CELEX numbers found by title search in Cellar, see METHOD.md):
FRAME = {
    "52025DC1025": "European Affordable Housing Plan, COM(2025) 1025",
    "32021R0241": "Regulation (EU) 2021/241 establishing the Recovery and Resilience Facility",
    "52025DC0310": "NextGenerationEU - The road to 2026, COM(2025) 310",
    # Commission staff working documents with the climate tracking of every measure, which
    # give each measure's estimated cost (the CID annex does not), one per later version:
    "52025SC0276": "SWD(2025) 276, climate tracking, with COM(2025) 556",
    "52025SC0432": "SWD(2025) 432, climate tracking, with COM(2025) 794",
    "52026SC0135": "SWD(2026) 135, climate tracking, with COM(2026) 257",
    "52026SC0267": "SWD(2026) 267, climate tracking, with COM(2026) 435",
    "52021SC0147": "SWD(2021) 147, analysis of the plan, with COM(2021) 322",
    "52023SC0326": "SWD(2023) 326, analysis of the amended plan, with COM(2023) 576",
}

# Spain's recovery-plan site: the Government's own statements used in the paper (dated pages).
PRTR = "https://planderecuperacion.gob.es/noticias/"
PRTR_PAGES = [
    "gobierno-aprueba-adenda-simplificacion-plan-recuperacion-prtr",
    "gobierno-aprueba-adenda-cierre-plan-recuperacion-culminar-ejecucion-prtr",
    "gobierno-pone-marcha-inyeccion-13300-millones-ico-activar-fondo-espana-crece-prtr",
    "pedro-sanchez-anuncia-fondo-espana-crece-movilizara-hasta-23000-millones-vivienda-prtr",
    "ico-pone-marcha-instrumentos-financiar-vivienda-asequible-fondo-espana-crece-prtr",
    "ico-destina-32-millones-financiar-construccion-316-viviendas-alquiler-asequible-toledo-prtr",
    "espana-solicita-septimo-ultimo-pago-plan-de-recuperacion-25861-millones-prtr",
    "carlos-cuerpo-comparece-comision-mixta-UE-congreso-informar-cierre-plan-de-recuperacion-prtr",
    "espana-solicita-sexto-pago-plan-de-recuperacion-7256-millones-prtr",
    "Espana-solicita-quinto-pago-plan-de-recuperacion-cifra-record-25000-millones-euros-prtr",
    "gobierno-Espana-solicita-cuarto-desembolso-plan-recuperacion-valor-10021-millones-euros-prtr",
    "gobierno-aprueba-linea-prestamos-4000-millones-promover-viviendas-alquiler-asequible-prtr",
    "consejo-ministros-aprueba-adenda-ampliaci%C3%B3n-Plan-Recuperacion-Transformacion-Resiliencia-prtr",
]


# La Moncloa: the Government's official summaries of the Council of Ministers ("Referencia")
MONCLOA = [
    "https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/2025/20251209-referencia-rueda-de-prensa-ministros.aspx",
    "https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/2026/20260728-referencia-rueda-de-prensa-ministros.aspx",
]


def fetch_prtr():
    for u in MONCLOA:
        try:
            fetch(u, RAW / "prtr" / ("moncloa_" + u.rsplit("/", 1)[1].replace(".aspx", ".html")), refetch=REFETCH)
            print("moncloa", u, flush=True)
        except Exception as e:
            print("moncloa", u, "failed:", e, flush=True)
    for slug in PRTR_PAGES:
        name = slug.replace("%C3%B3", "o") + ".html"
        fetch(PRTR + slug, RAW / "prtr" / name, refetch=REFETCH)
        print("prtr", slug, flush=True)


def fetch_proposals():
    rows = sparql(Q_PROPOSALS, RAW / "sparql_spain_rrp_documents.csv", REFETCH)
    found = {r["celex"] for r in rows if "PC" in r["celex"]}
    ours = {v[1] for v in VERSIONS}
    if found != ours:
        print("WARNING: Cellar lists proposals not in VERSIONS or vice versa:", sorted(found ^ ours))
    ids = ",".join(f'"{v[1]}"' for v in VERSIONS)
    sparql(Q_COUNCIL % ids, RAW / "sparql_council_docs.csv", REFETCH)
    sparql(Q_EVENTS % ids, RAW / "sparql_procedure_events.csv", REFETCH)
    for label, celex, com, date in VERSIONS:
        get_celex(celex)
        print(label, celex, "ok", flush=True)


def get_celex(celex, sub="cellar"):
    """Branch notice of a CELEX work, then every XHTML item (or PDF if no XHTML)."""
    d = RAW / sub / celex
    d.mkdir(parents=True, exist_ok=True)
    br = d / "branch.xml"
    import urllib.parse
    fetch(f"{CELLAR}/celex/{urllib.parse.quote(celex)}", br, accept="application/xml;notice=branch",
          extra={"Accept-Language": "eng"}, refetch=REFETCH)
    if not br.exists():
        print(celex, "no branch notice")
        return []
    man = manifestations(br)
    kind = "xhtml" if "xhtml" in man else ("pdf" if "pdf" in man else None)
    if not kind:
        print(celex, "no xhtml/pdf manifestation:", list(man))
        return []
    out = []
    for item in man[kind]:
        name = item.rsplit("/", 1)[1] + "." + kind
        fetch(item, d / name, refetch=REFETCH)
        out.append(d / name)
    return out


def get_consil(doc_id, sub="council"):
    """One Council document (English PDF) from Cellar, by its Council number."""
    d = RAW / sub / doc_id
    d.mkdir(parents=True, exist_ok=True)
    items = sparql(Q_ITEMS % doc_id, d / "items.csv", REFETCH)
    pdfs = sorted({r["item"] for r in items if r["mtype"] in ("pdf", "pdfa1a", "pdfa2a")})
    for i, item in enumerate(pdfs, 1):
        fetch(item, d / f"DOC_{i}.pdf", refetch=REFETCH)
    return pdfs


def fetch_council():
    for label, ids in COUNCIL_DOCS.items():
        for doc_id in ids:
            got = get_consil(doc_id)
            print(label, doc_id, len(got), "pdf", flush=True)


def fetch_frame():
    for celex in FRAME:
        get_celex(celex, sub="frame")
        print("frame", celex, flush=True)
    # Council recommendations to Spain (European Semester), 2019-2026: found by title.
    q = CDM + """SELECT DISTINCT ?celex ?date ?title WHERE {
  ?w cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?date .
  FILTER(?date >= "2019-01-01"^^<http://www.w3.org/2001/XMLSchema#date>)
  ?e cdm:expression_belongs_to_work ?w ; cdm:expression_title ?title ;
     cdm:expression_uses_language %s .
  FILTER(STRSTARTS(STR(?celex), "3") && CONTAINS(LCASE(STR(?title)), "council recommendation") && CONTAINS(STR(?title), "of Spain"))
} ORDER BY ?date""" % ENG
    rows = sparql(q, RAW / "frame" / "sparql_csr_spain.csv", True)
    for r in rows:
        get_celex(r["celex"], sub="frame")
        print("csr", r["celex"], r["date"], flush=True)


def fetch_others():
    """The decisions (recitals) of the other member states amended in the same August 2026
    round, to see whether housing measures were cut elsewhere and with what stated reasons."""
    rows = list(csv.DictReader(open(RAW / "sparql_council_aug2026.csv", encoding="utf-8")))
    for r in rows:
        doc = r["id"].split(":", 1)[1]
        if doc.endswith("_INIT"):
            get_consil(doc, sub="others")
            print("other", doc, flush=True)


def council_aug2026_list():
    q = CDM + """SELECT DISTINCT ?id ?date ?title WHERE {
  ?w cdm:work_id_document ?id ; cdm:work_date_document ?date .
  FILTER(?date >= "2026-08-20"^^<http://www.w3.org/2001/XMLSchema#date> && ?date <= "2026-08-31"^^<http://www.w3.org/2001/XMLSchema#date>)
  FILTER(STRSTARTS(STR(?id), "consil:ST_"))
  ?e cdm:expression_belongs_to_work ?w ; cdm:expression_title ?title ;
     cdm:expression_uses_language %s .
  FILTER(CONTAINS(STR(?title), "recovery and resilience plan for"))
} ORDER BY ?id""" % ENG
    return sparql(q, RAW / "sparql_council_aug2026.csv", REFETCH)


if __name__ == "__main__":
    what = [a for a in sys.argv[1:] if not a.startswith("--")] or ["all"]
    if "proposals" in what or "all" in what:
        fetch_proposals()
    if "council" in what or "all" in what:
        fetch_council()
    if "frame" in what or "all" in what:
        fetch_frame()
    if "prtr" in what or "all" in what:
        fetch_prtr()
    if "others" in what or "all" in what:
        council_aug2026_list()
        fetch_others()
    print("done", flush=True)
