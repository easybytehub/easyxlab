#!/usr/bin/env python3
"""S23: does the annual report ('memoria') of art. 32 of Ley 12/2023 exist?

Collects the evidence of every route we were allowed to use into data/art32_search.csv:
the law in force (consolidated text and its amendment record), every BOE daily summary from
26 May 2023 to 3 October 2026, the national open-data catalogue, the Ministry's publications
catalogue, the Transparency Portal, the Ministry's websites, the press, and the Ministry's own
social-housing bulletin. Also writes data/art32_text.csv with the article, quoted literally.
"""
import csv, glob, gzip, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s23lib import RAW, DATA, boe_blocks, quote_found, html_text, source_text

LEY = os.path.join(RAW, "boe", "ley12_2023_texto.xml")


def main():
    # ---- the article, literally, with its versions
    bl = boe_blocks(LEY)
    vs = bl["a3-4"]
    text = [{"block": "a3-4", "title": v[2], "id_norma": v[0], "in_force_from": v[1], "text": v[3]} for v in vs]
    df7 = bl["df-7"][-1][3]
    text.append({"block": "df-7", "title": "Disposición final séptima (extract)", "id_norma": bl["df-7"][-1][0],
                 "in_force_from": bl["df-7"][-1][1],
                 "text": [p for p in df7.split("\n") if p.startswith("a) Los artículos 10, 11, 32")][0]})
    df9 = bl["df-9"][-1]
    text.append({"block": "df-9", "title": "Disposición final novena", "id_norma": df9[0], "in_force_from": df9[1], "text": df9[3]})
    with open(os.path.join(DATA, "art32_text.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(text[0])); w.writeheader(); w.writerows(text)
    analisis = open(os.path.join(RAW, "boe", "ley12_2023_analisis.xml"), encoding="utf-8").read()
    touches_32 = [m for m in re.findall(r"<texto>([^<]*)</texto>", analisis) if re.search(r"\b32\b", m)]
    meta = open(os.path.join(RAW, "boe", "ley12_2023_metadatos.xml"), encoding="utf-8").read()
    upd = re.search(r"<fecha_actualizacion>(\d{8})", meta).group(1)

    rows = []

    def add(route, what, n_checked, result, url, note=""):
        rows.append({"route": route, "what_was_checked": what, "n_checked": n_checked, "result": result, "url": url, "note": note})

    add("Law in force", "Consolidated text of Ley 12/2023 (BOE open-data API), versions of art. 32", len(vs),
        f"one version, in force since {vs[0][1]}; none of the {len(re.findall(r'<texto>', analisis))} entries of the BOE's amendment record amends art. 32",
        "https://www.boe.es/buscar/act.php?id=BOE-A-2023-12203#a3-4", f"consolidated text updated {upd}")
    # ---- the Constitutional Court on art. 32 (rulings read from /buscar/doc.php, allowed by robots.txt)
    stc = [("STC 79/2024", "boe/stc_79_2024.html", "Por ello, los arts. 32 a 36 de la Ley 12/2023 quedan fuera del objeto de análisis de esta sentencia",
            "https://www.boe.es/buscar/doc.php?id=BOE-A-2024-12808"),
           ("STC 79/2024 (Abogacía del Estado, as recorded)", "boe/stc_79_2024.html", "Se alega además que el art. 32 de la Ley 12/2023 se refiere a patrimonio público estatal",
            "https://www.boe.es/buscar/doc.php?id=BOE-A-2024-12808"),
           ("STC 190/2025", "boe/stc_190_2025.html", "a proporcionar información periódica sobre cuestiones tales como el parque público de vivienda de titularidad estatal (art. 32)",
            "https://www.boe.es/buscar/doc.php?id=BOE-A-2026-1756")]
    for name, raw, q, url in stc:
        assert quote_found(q, raw), name
        add("Constitutional Court", name, 1, f"«{q}»", url,
            "Andalusia's challenge to arts. 32-36 was left out of the ruling for lack of argument" if name == "STC 79/2024" else
            ("the State's pleading on the scope of art. 32" if "Abogacía" in name else "the Court's description of art. 32: State-owned stock"))

    # ---- BOE daily summaries
    p = os.path.join(RAW, "boe", "sumarios.jsonl.gz")
    days = items = issues = 0
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line); days += 1; items += len(r["items"]); issues += r["status"] == 200
    hits = list(csv.DictReader(open(os.path.join(DATA, "boe_title_hits.csv"), encoding="utf-8")))
    memoria = [h for h in hits if re.search(r"memoria(?! Democr)|inventario|mapa de la vivienda|artículo 32", h["titulo"], re.I)]
    add("BOE", "Titles of every item in every BOE daily summary, 26 May 2023 to 3 October 2026 (open-data API)",
        f"{issues} issues over {days} days, {items} items", f"{len(hits)} titles mention public/social housing stock; {len(memoria)} mention an inventory, report, map or art. 32 of the housing law",
        "https://www.boe.es/datosabiertos/api/boe/sumario/{YYYYMMDD}", "titles in data/boe_title_hits.csv. A ministerial report would normally not be published in the BOE; this route can only find an order or resolution about it.")

    # ---- national open-data catalogue
    cat = list(csv.DictReader(open(os.path.join(DATA, "catalogue_search.csv"), encoding="utf-8")))
    q = sorted({r["query"] for r in cat})
    mivau = json.load(open(os.path.join(RAW, "catalogues", "datosgob_publisher_E05233601.json"), encoding="utf-8"))["result"]["items"]

    def title(it):
        t = it.get("title")
        if isinstance(t, list):
            t = [x for x in t if isinstance(x, dict) and x.get("_lang") == "es"] or t
            t = t[0]
        return t.get("_value", "") if isinstance(t, dict) else t
    add("datos.gob.es", "Title search, 20 terms (Spanish, Catalan, Basque); all datasets of the housing ministry's publisher code E05233601",
        f"{len(q)} queries; {len(mivau)} ministry datasets",
        "no dataset is an inventory or annual report of the State's public housing stock; the ministry's 8 datasets are: " + "; ".join(title(i) for i in mivau),
        "https://datos.gob.es/apidata/catalog/dataset/publisher/E05233601", "queries and hits in data/catalogue_search.csv")

    # ---- the ministry's publications catalogue
    seen = {}
    for f in glob.glob(os.path.join(RAW, "ovs", "cat_*.html")):
        s = open(f, encoding="utf-8", errors="replace").read()
        for h, t in re.findall(r'<a href=([^ >]+) title="Mostrar detalles de ([^"]+)"', s):
            seen[h] = re.sub(r"\s+", " ", t)
    mem = [t for t in seen.values() if re.search(r"memoria|inventario|parque p[uú]blico", t, re.I)]
    add("Centro de Publicaciones (publicaciones.transportes.gob.es)",
        "Every title in the categories 'Arquitectura, vivienda y suelo' and its MIVAU sub-category (the ministry's publications since 2023)",
        f"{len(seen)} titles", f"{len(mem)} titles mention a report (memoria), an inventory or the public housing stock",
        "https://publicaciones.transportes.gob.es/arquitectura-vivienda-y-suelo-mivau",
        "Two bulletins on social housing exist: Boletín Especial Vivienda Social 2020 and 2024 (the sources of 290,000 and 318,000). They cover regional and municipal stock, not the State's own, and do not mention art. 32.")

    # ---- transparency portal
    sm = open(os.path.join(RAW, "transparencia", "sitemap.xml"), encoding="utf-8").read()
    locs = re.findall(r"<loc>([^<]+)</loc>", sm)
    viv = [u for u in locs if re.search(r"vivienda|parque|alquiler", u, re.I)]
    add("Portal de la Transparencia (transparencia.gob.es)", "Sitemap (all URLs), filtered for housing", f"{len(locs)} URLs; {len(viv)} on housing",
        "no page for an art. 32 report; the housing pages are Observatory bulletins, a tenants' guide, the rent-index system, the 2021 census and the urban information system",
        "https://transparencia.gob.es/sitemap.xml",
        "The page for the Boletín Especial Vivienda Social 2024 (published there 17 Feb 2025) links to a different publication (bulletin no. 39, 2021).")

    # ---- ministry websites
    # ---- the electronic office that art. 32.2 names
    st_ = source_text("sede/sitemap.html")[0]
    srch = {}
    for term in ("memoria", "inventario", "parque", "vivienda_social"):
        t = source_text(f"sede/search_{term}.html")[0]
        srch[term.replace("_", " ")] = ("none" if "No existen procedimientos disponibles" in t else
                                        "; ".join(x for x in ("Programas de ayuda en materia de rehabilitación residencial y para el incremento del parque de vivienda en alquiler social",
                                                              "Convocatoria pública de alquiler asequible del parque de viviendas de CASA 47") if x in t))
    add("Ministry electronic office (mivau.sede.gob.es)", "home page, site map, procedure search for «memoria», «inventario», «parque», «vivienda social»",
        1 + 1 + len(srch),
        "the site map lists procedures, services, «Sobre la sede», help and the private area; no publications section. Search results: "
        + "; ".join(f"«{k}»: {v}" for k, v in srch.items()),
        "https://mivau.sede.gob.es/sitemap",
        "art. 32.2 requires publication «en la sede electrónica prevista en el artículo 38 de la Ley 40/2015»; robots.txt answers 404 (no restrictions)" + ("" if "Mapa del sitio" in st_ else " [site map text not recognised]"))
    add("Ministry website (www.mivau.gob.es)", "home page and robots.txt", 2, "HTTP 403, «Página web bloqueada» (web application firewall); not retried, not bypassed",
        "https://www.mivau.gob.es/", "Not checked by hand; a report published only there cannot be excluded.")
    # ---- CASA 47, the State housing entity (an «ente adscrito» in the sense of art. 32.1)
    plan = source_text("casa47/plan_anual_2026.pdf")[0]
    add("CASA 47 (www.casa47.es)", "transparency page «Planificación, actuaciones y resultados»: Plan Anual de Actuación 2026, Informe de gestión 2024, evaluation of the annual plan; pages on the Sareb transfer and the rental portal",
        5, "no inventory or annual report of the State's housing stock; the 2026 plan refers to the «parque estatal de vivienda» but gives no count; partial figures: 40,000 dwellings identified for transfer from Sareb (2025), 816 dwellings offered for affordable rent (September 2026)",
        "https://www.casa47.es/planificacion-actuaciones-y-resultados", "figures ES-30 to ES-32 in data/figures.csv")
    add("La Moncloa (lamoncloa.gob.es)", "site search", 1, "the search URL we tried returns the site's not-found page; no other search route found",
        "https://www.lamoncloa.gob.es/", "")

    # ---- press
    pw = list(csv.DictReader(open(os.path.join(DATA, "prior_work_search.csv"), encoding="utf-8")))
    pq = [r for r in pw if r["source"] == "Bing News RSS" and re.search(r"memoria|inventario|artículo 32", r["query"])]
    add("Press (Bing News RSS)", "; ".join(r["query"] for r in pq), len(pq),
        "; ".join(f"{r['query']}: {r['hits']} items" for r in pq) + ". None of the items listed is about an art. 32 report.",
        "https://www.bing.com/news/search?format=rss", "screened titles in data/prior_work_search.csv")

    # ---- the ministry's own bulletin
    b24 = "ovs/OVS_boletin_especial_vivienda_social_2024.pdf"
    t = source_text(b24)[0]
    n32 = len(re.findall(r"art[íi]culo 32|art\. 32", t, re.I))
    nmem = len(re.findall(r"\bmemoria\b", t, re.I))
    ninv = len(re.findall(r"inventario", t, re.I))
    add("OVS Boletín Especial Vivienda Social 2024", "full text", 1,
        f"mentions of «artículo 32»: {n32}; «memoria»: {nmem}; «inventario»: {ninv}; no table of State-owned dwellings",
        "https://publicaciones.transportes.gob.es/observatorio-de-vivienda-y-suelo-boletin-especial-alquiler-residencial-2024", "")
    order = ["Law in force", "Constitutional Court", "Ministry electronic office", "Ministry website", "CASA 47", "BOE",
             "datos.gob.es", "Centro de Publicaciones", "Portal de la Transparencia", "La Moncloa", "Press", "OVS Boletín"]
    rows.sort(key=lambda r: next(i for i, o in enumerate(order) if r["route"].startswith(o)))
    with open(os.path.join(DATA, "art32_search.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    S = json.load(open(os.path.join(DATA, "summary.json"), encoding="utf-8"))
    S.update({"art32_routes": len(rows), "art32_routes_blocked": sum(r["result"].startswith("HTTP 403") for r in rows), "boe_days": days, "boe_issues": issues, "boe_items": items, "boe_title_hits": len(hits),
              "boe_memoria_hits": len(memoria), "pub_titles": len(seen), "pub_memoria_titles": len(mem),
              "transparency_urls": len(locs), "art32_in_force_from": vs[0][1], "art32_versions": len(vs)})
    json.dump(S, open(os.path.join(DATA, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    for r in rows:
        print(r["route"], "|", r["n_checked"], "|", r["result"][:160])


if __name__ == "__main__":
    main()
