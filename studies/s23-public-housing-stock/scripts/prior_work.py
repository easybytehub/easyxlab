#!/usr/bin/env python3
"""S23: prior-work search, logged query by query in data/prior_work_search.csv (date, source,
query, URL, status, hits, screened titles). Raw responses go to data/raw/prior/ (git-ignored).

Sources: Crossref and OpenAlex (scholarly works), Bing News RSS (press; Bing's robots.txt
disallows /search but not /news/search), and a short list of institutional pages that are
fetched and grepped. robots.txt is read for every host; a disallowed URL is logged, not
fetched. Resumable: an existing response file is reused.  Run: python3 scripts/prior_work.py
"""
import csv, html as H, json, os, re, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite
from s23lib import RAW, DATA, html_text

OUT = os.path.join(RAW, "prior")
os.makedirs(OUT, exist_ok=True)
SCHOLAR_Q = [
    "social housing stock Spain", "public rental housing Spain size", "vivienda social España parque",
    "parque público de vivienda España", "alquiler social España porcentaje", "social housing definition comparison Europe",
    "social rental housing stock OECD countries", "measuring social housing Europe comparability",
    "vivienda protegida descalificación España", "Ley 12/2023 derecho a la vivienda",
]
NEWS_Q = [
    '"318.000 viviendas"', '"290.000 viviendas" vivienda social', '"vivienda social" "1,6%"', '"vivienda social" "1,7%"',
    '"vivienda social" "2,5%" Europa', '"parque público de vivienda" media europea', '"media europea" "vivienda social" 9%',
    '"parque de vivienda social" España datos', '"vivienda social" España "OCDE"', '"memoria" "parque público de vivienda"',
    '"inventario del parque público de vivienda"', '"artículo 32" "Ley de Vivienda" parque público',
    'Newtral vivienda social España porcentaje', 'Maldita vivienda social España porcentaje',
    'vivienda social España 318.000 viviendas', 'vivienda social España 290.000 viviendas', 'vivienda pública España 1,6% hogares',
    'media europea vivienda social 9%', 'media europea vivienda social 8%', 'parque público vivienda España cifras',
    'memoria anual parque público de vivienda Ministerio', 'inventario parque público vivienda Estado ley',
    'Observatorio de Vivienda y Suelo boletín vivienda social', 'Housing Europe España vivienda social',
]
PAGES = [  # (source, url, grep pattern)
    ("OECD policy brief 2020", "https://www.oecd.org/content/dam/oecd/en/publications/reports/2020/11/social-housing-a-key-part-of-past-and-future-housing-policy_0d7d4fd3/a3f5b8a6-en.pdf", r"Spain|social rental"),
    ("Fundación Alternativas", "https://fundacionalternativas.org/?s=vivienda+social", r"vivienda social|parque"),
    ("AIReF", "https://www.airef.es/es/politicas/acceso-a-la-vivienda-y-fomento-de-la-edificacion/", r"vivienda social|parque"),
    # press articles found through Bing News RSS (URLs decoded from the feed), fetched and grepped
    ("press: El Periódico 2026-07-28", "https://www.elperiodico.com/es/economia/vivienda-social-alquiler-publico-europa-espana-132698286-rm/index.html", r"1,72|8 ?%|9 ?%|318|Observatorio|Housing Europe|artículo 32|memoria"),
    ("press: EFE Verifica 2026-09-30", "https://verifica.efe.com/claves-vivienda-espana-alquilar-comprar/", r"vivienda (pública|social)|318|290|1,[67]|parque"),
    ("press: El País 2026-05-07", "https://elpais.com/economia/vivienda/2026-05-07/las-entidades-sociales-ya-gestionan-la-mayoria-de-vivienda-publica-pero-siguen-lejos-de-los-niveles-europeos.html", r"318|290|1,[67]|3,[35]|9 ?%|8 ?%|7 ?%|media"),
    ("press: El País 2026-09-29", "https://elpais.com/economia/2026-09-29/la-vivienda-en-graficos-mas-poblacion-mas-turismo-y-poca-construccion.html", r"vivienda (pública|social)|318|290|1,[67]|parque"),
    ("press: La Marea 2025-01-08", "https://www.lamarea.com/2025/01/08/vivienda-social-europa/", r"2,5|1,[67]|9 ?%|8 ?%|media|Housing Europe|OCDE"),
    ("press: La Gaceta 2026-10-04", "https://lagacetadecanarias.com/en-ocho-anos-de-sanchez-espana-ha-acabado-78-977-viviendas-protegidas-y-es-cuarta-por-la-cola-en-vivienda-social-entre-los-paises-europeos-analizados/", r"cuarta|%|Observatorio|OCDE"),
    ("press: Europa Press 2025-11-26 (OECD survey)", "https://www.europapress.es/economia/construccion-y-vivienda-00342/noticia-ocde-urge-espana-ampliar-parque-vivienda-social-alquiler-mejor-enfoque-ayudas-20251126120251.html", r"%|parque|social"),
    # institutional searches for an existing reconciliation (added after review)
    ("Funcas site search", "https://www.funcas.es/?s=vivienda+social", r"vivienda social|parque (público|social)|alquiler social"),
    ("Housing Europe site search", "https://www.housingeurope.eu/?s=Spain+social+housing", r"Spain|Spanish|social housing"),
    ("Newtral site search", "https://www.newtral.es/?s=vivienda+social", r"vivienda (social|pública)|parque"),
    ("Newtral fact check 2018-11-22", "https://www.newtral.es/jose-luis-abalos-la-vivienda-social-representa-apenas-un-25-del-parque-en-nuestro-pais/20181122/", r"2,5|Encuesta|ECV|INE|Housing Europe|Eurostat|parque"),
    ("Newtral 2023-01-17", "https://www.newtral.es/vivienda-social-espana-europa-datos/20230117/", r"\d+[.,]?\d* ?%|290|Housing Europe|OCDE|Observatorio"),
    ("Funcas article (la vivienda social)", "https://www.funcas.es/articulos/la-vivienda-social/", r"\d+[.,]?\d* ?%|290|318|parque"),
    ("press: La Vanguardia 2025-09-28", "https://www.lavanguardia.com/dinero/20250928/11099769/busca-parque-publico-vivienda.html", r"\d+[.,]?\d* ?%|290|318|parque público"),
    ("press: Cadena SER 2026-10-03", "https://cadenaser.com/nacional/2026/10/03/radiografia-de-la-vivienda-publica-a-la-cola-de-europa-y-presencia-muy-limitada-del-alquiler-asequible-cadena-ser/", r"\d+[.,]?\d* ?%|290|318|parque"),
    ("press: Heraldo 2025-07-01", "https://www.heraldo.es/noticias/nacional/2025/07/01/gobierno-incorporara-viviendas-suelos-sareb-parque-publico-1836215.html", r"40\.000|2\.400|parque público"),
    ("press: elDiario.es 2026-09-09", "https://www.eldiario.es/canariasahora/sociedad/casa-47-que-es-vivienda-publica-canarias_1_13497640.html", r"viviendas|parque"),
    ("press: Público 2026-10-03", "https://www.publico.es/internacional/vivienda-social-especulacion-doble-desafio-europa-crisis-habitacional.html", r"España|1,[67]|%|media"),
]


def get(url, name, accept=None):
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        return "cached", path
    try:
        st, final = polite.fetch(url, path, accept)
        return st, (path if os.path.exists(path) else None)
    except PermissionError:
        return "skipped-robots", None
    except Exception as e:
        return f"error:{type(e).__name__}", None


def safe(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s)[:80]


def main():
    rows, now = [], time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for q in SCHOLAR_Q:
        u = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query": q, "rows": 20, "select": "DOI,title,issued,container-title"})
        st, p = get(u, f"crossref_{safe(q)}.json", "application/json")
        hits, top = "", ""
        if p:
            try:
                its = json.load(open(p, encoding="utf-8"))["message"]["items"]
                hits = len(its)
                top = " || ".join(f"{(i.get('title') or [''])[0][:110]} ({i.get('DOI')})" for i in its)
            except Exception as e:
                top = f"parse error {e}"
        rows.append({"date": now, "source": "Crossref", "query": q, "url": u, "status": st, "hits": hits, "screened_titles": top})
        u = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": q, "per-page": 25})
        st, p = get(u, f"openalex_{safe(q)}.json", "application/json")
        hits, top = "", ""
        if p:
            try:
                d = json.load(open(p, encoding="utf-8"))
                hits = d.get("meta", {}).get("count", "")
                top = " || ".join(f"{(w.get('title') or '')[:110]} ({w.get('publication_year')}; {w.get('doi') or w.get('id')})" for w in d.get("results", []))
            except Exception as e:
                top = f"parse error {e}"
        rows.append({"date": now, "source": "OpenAlex", "query": q, "url": u, "status": st, "hits": hits, "screened_titles": top})
        print("scholar", q, flush=True)
    for q in NEWS_Q:
        u = "https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": q, "format": "rss", "setlang": "es"})
        st, p = get(u, f"bingnews_{safe(q)}.xml", "application/rss+xml")
        hits, top = "", ""
        if p:
            x = open(p, encoding="utf-8", errors="replace").read()
            items = re.findall(r"<item>(.*?)</item>", x, re.S)
            hits = len(items)

            def tag(it, t):
                m = re.search(rf"<{t}>(.*?)</{t}>", it, re.S)
                return H.unescape(m.group(1)).strip() if m else ""
            top = " || ".join(f"{tag(it, 'pubDate')[:16]}: {tag(it, 'title')[:110]} <{tag(it, 'link')[:200]}>" for it in items[:30])
        rows.append({"date": now, "source": "Bing News RSS", "query": q, "url": u, "status": st, "hits": hits, "screened_titles": top})
        print("bing", q, st, hits, flush=True)
    for src, u, pat in PAGES:
        st, p = get(u, f"page_{safe(src)}" + (".pdf" if u.endswith(".pdf") else ".html"))
        hits, top = "", ""
        if p:
            if p.endswith(".pdf"):
                from s23lib import pdf_text
                t = re.sub(r"\s+", " ", pdf_text(p))
            else:
                t = re.sub(r"\s+", " ", html_text(p))
            ms = [t[max(0, m.start() - 120): m.end() + 120] for m in re.finditer(pat, t)]
            hits, top = len(ms), " || ".join(ms[:12])
        rows.append({"date": now, "source": src, "query": f"page grep /{pat}/", "url": u, "status": st, "hits": hits, "screened_titles": top})
        print("page", src, st, hits, flush=True)
    with open(os.path.join(DATA, "prior_work_search.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
