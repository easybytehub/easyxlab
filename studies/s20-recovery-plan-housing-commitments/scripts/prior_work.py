#!/usr/bin/env python3
"""Prior-work search, logged query by query in data/prior_work_search.csv (date, source,
query, URL, status, hits, top titles). Raw responses and documents go to data/raw/prior/ (not published).

Sources: Crossref and OpenAlex (scholarly), the GDELT DOC 2.0 API (news, rolling window of
about three months), and a fixed list of institutional pages that are fetched and grepped
(ECA, AIReF, Commission, European Parliament research service, Bruegel, Fundación
Alternativas). robots.txt is read for every host; a disallowed URL is logged, not fetched.
Resumable: an existing response file is reused. Run: python3 scripts/prior_work.py
"""
import csv, json, os, re, sys, time, urllib.parse
from s20lib import DATA, RAW
import polite

OUT = RAW / "prior"   # third-party responses and documents: raw, never published
OUT.mkdir(parents=True, exist_ok=True)
SCHOLAR_Q = [
    "Spain recovery and resilience plan social housing",
    "Spain recovery and resilience plan amendment milestones targets",
    "recovery and resilience facility plan amendments milestones targets",
    "recovery and resilience facility housing investment",
    "Plan de Recuperación Transformación y Resiliencia vivienda",
    "Plan de Recuperación vivienda social alquiler",
    "NextGenerationEU vivienda España",
    "ICO vivienda social préstamos",
]
NEWS_Q = [
    '"15.718 viviendas"', '"17.365 viviendas"', '"15.718" viviendas', '"17.365" viviendas',
    '"línea ICO" vivienda social', '"568 millones" vivienda ICO', '"567 millones" vivienda ICO',
    '"750 millones" "línea ICO" vivienda', '"adenda de cierre" vivienda', '"adenda de simplificación" vivienda',
    '"Plan de Recuperación" "vivienda social" recorte', '"recovery plan" Spain "social housing"',
]
PAGES = [  # (source, url, grep pattern)
    ("ECA", "https://www.eca.europa.eu/en/publications?type=SpecialReport", r"recovery|RRF|housing"),
    ("ECA", "https://www.eca.europa.eu/en/publications/SR-2024-13", r"housing|amend|milestone"),
    ("AIReF", "https://www.airef.es/es/politicas/acceso-a-la-vivienda-y-fomento-de-la-edificacion/", r"vivienda|PRTR|Plan de Recuperación"),
    ("AIReF", "https://www.airef.es/es/?s=plan+de+recuperacion+vivienda", r"vivienda|PRTR|Recuperación"),
    ("Bruegel", "https://www.bruegel.org/search?keys=recovery%20and%20resilience%20housing", r"housing|recovery"),
    ("Fundación Alternativas", "https://fundacionalternativas.org/?s=plan+de+recuperacion+vivienda", r"vivienda|Recuperación"),
    ("EPRS", "https://www.europarl.europa.eu/thinktank/en/research/advanced-search?textualSearch=Spain%20recovery%20and%20resilience%20plan", r"Spain|recovery"),
    ("Commission", "https://commission.europa.eu/business-economy-euro/economic-recovery/recovery-and-resilience-facility/recovery-and-resilience-scoreboard_en", r"housing|amend"),
    # press articles found through Bing News RSS, fetched and grepped for the figures
    ("press: Okdiario 2026-08-09", "https://okdiario.com/espana/espana-admite-bruselas-que-no-cumplira-sus-promesas-vivienda-social-fondos-europeos-19132571", r"inflaci|1\.330|17 de diciembre"),
    ("press: El Confidencial 2026-09-06", "https://www.elconfidencial.com/economia/2026-09-06/gobierno-admite-bruselas-fracaso-construccion-25-000-viviendas_4418134/", r"15\.718|17\.365|568|certificado|Ley del Suelo|falta de demanda|AIReF"),
    ("press: talent24h.okdiario 2026-09-23", "https://talent24h.okdiario.com/el-boe-recorta-de-4-000-a-750-millones-la-financiacion-para-vivienda-social/", r"750|375|31 de julio"),
    ("press: Vozpópuli 2026-09-30", "https://www.vozpopuli.com/economia/inmobiliario/el-fiasco-de-los-avales-ico-para-vivienda-social-el-gobierno-recorta-un-86-la-financiacion-prevista.html", r"86|567|España Crece"),
    ("press: El Debate 2026-09-30", "https://www.eldebate.com/economia/20260930/gobierno-recorto-21-construccion-vivienda-alquiler-social-fondos-ue-dias-antes-caso-maricarmen_464232.html", r"15\.718|17\.365|20\.000|21 %"),
]


def get(url, name, accept=None):
    path = OUT / name
    if path.exists():
        return "cached", path
    try:
        st, final = polite.fetch(url, str(path), accept)
        if not os.path.exists(path):
            return st, None
        return st, path
    except PermissionError:
        return "skipped-robots", None
    except Exception as e:
        return f"error:{type(e).__name__}", None


def safe(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s)[:80]


def main():
    rows = []
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for q in SCHOLAR_Q:
        u = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query": q, "rows": 20, "select": "DOI,title,issued,container-title"})
        st, p = get(u, f"crossref_{safe(q)}.json", "application/json")
        hits, top = "", ""
        if p:
            try:
                d = json.load(open(p, encoding="utf-8"))
                items = d["message"]["items"]
                hits = d["message"].get("total-results", len(items))
                top = " || ".join(f"{(i.get('title') or [''])[0][:90]} ({i.get('DOI')})" for i in items[:20])
            except Exception as e:
                st = f"parse-error:{e}"
        rows.append({"date": now, "source": "Crossref", "query": q, "url": u, "status": st, "hits": hits, "screened_titles": top})
        u = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": q, "per-page": 25})
        st, p = get(u, f"openalex_{safe(q)}.json", "application/json")
        hits, top = "", ""
        if p:
            try:
                d = json.load(open(p, encoding="utf-8"))
                hits = d["meta"]["count"]
                top = " || ".join(f"{(w.get('title') or '')[:90]} ({w.get('doi')}, {w.get('publication_year')})" for w in d["results"][:25])
            except Exception as e:
                st = f"parse-error:{e}"
        rows.append({"date": now, "source": "OpenAlex", "query": q, "url": u, "status": st, "hits": hits, "screened_titles": top})
        print("scholar", q, flush=True)
    for q in NEWS_Q:
        u = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(
            {"query": q, "mode": "artlist", "format": "json", "maxrecords": 75, "timespan": "3months", "sort": "datedesc"})
        st, p = get(u, f"gdelt_{safe(q)}.json", "application/json")
        for _ in range(0):           # GDELT answered 429 to almost every query on 2026-10-04; no retries
            if st != 429:
                break
            time.sleep(20)
            st, p = get(u, f"gdelt_{safe(q)}.json", "application/json")
        hits, top = "", ""
        if p:
            try:
                txt = open(p, encoding="utf-8").read().strip()
                d = json.loads(txt) if txt.startswith("{") else {"articles": []}
                arts = d.get("articles", [])
                hits = len(arts)
                top = " || ".join(f"{a.get('seendate','')[:8]} {a.get('domain')}: {a.get('title','')[:100]} <{a.get('url')}>" for a in arts[:75])
                if not txt.startswith("{"):
                    st = f"non-json: {txt[:80]}"
            except Exception as e:
                st = f"parse-error:{e}"
        rows.append({"date": now, "source": "GDELT DOC 2.0", "query": q, "url": u, "status": st, "hits": hits, "screened_titles": top})
        print("news", q, st, hits, flush=True)
        time.sleep(4)   # GDELT asks for no more than one query every few seconds
    for q in NEWS_Q:
        u = "https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": q, "format": "rss", "setlang": "es"})
        st, p = get(u, f"bingnews_{safe(q)}.xml", "application/rss+xml")
        hits, top = "", ""
        if p:
            import html as H
            x = open(p, encoding="utf-8", errors="replace").read()
            items = re.findall(r"<item>(.*?)</item>", x, re.S)
            hits = len(items)
            def tag(it, t):
                m = re.search(rf"<{t}>(.*?)</{t}>", it, re.S)
                return H.unescape(m.group(1)).strip() if m else ""
            top = " || ".join(f"{tag(it, 'pubDate')[:16]}: {tag(it, 'title')[:110]} <{tag(it, 'link')[:160]}>" for it in items[:30])
        rows.append({"date": now, "source": "Bing News RSS", "query": q, "url": u, "status": st, "hits": hits, "screened_titles": top})
        print("bing", q, st, hits, flush=True)
    for src, u, pat in PAGES:
        st, p = get(u, f"page_{safe(src + '_' + u)}.html")
        hits, top = "", ""
        if p:
            import htmltext
            t = re.sub(r"\s+", " ", htmltext.text(str(p)))
            ms = [t[max(0, m.start() - 80): m.end() + 80] for m in re.finditer(pat, t)]
            hits = len(ms)
            top = " || ".join(ms[:10])
            if src.startswith("press"):
                # the article's own dateline (not the feed's pubDate, which is in UTC and can be a day off)
                raw = open(p, encoding="utf-8", errors="replace").read()
                d = re.search(r'"datePublished"\s*:\s*"([^"]+)"|article:published_time"\s+content="([^"]+)"', raw)
                if d:
                    top = f"datePublished {d.group(1) or d.group(2)} || " + top
        rows.append({"date": now, "source": src, "query": f"page grep /{pat}/", "url": u, "status": st, "hits": hits, "screened_titles": top})
        print("page", src, st, hits, flush=True)
    # ECA works in Cellar (author ECA, since 2022, titles on the RRF or housing)
    from s20lib import sparql
    q = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?date ?title WHERE {
  ?w cdm:work_created_by_agent <http://publications.europa.eu/resource/authority/corporate-body/ECA> ;
     cdm:work_date_document ?date .
  FILTER(?date >= "2022-01-01"^^<http://www.w3.org/2001/XMLSchema#date>)
  ?e cdm:expression_belongs_to_work ?w ; cdm:expression_title ?title ;
     cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> .
  FILTER(CONTAINS(LCASE(STR(?title)), "recovery") || CONTAINS(LCASE(STR(?title)), "housing") || CONTAINS(LCASE(STR(?title)), "rrf"))
} ORDER BY ?date"""
    try:
        eca = sparql(q, OUT / "cellar_eca_rrf.csv")
        titles = sorted({r["title"][:120] for r in eca if r["title"].startswith("Special report")})
        rows.append({"date": now, "source": "Cellar (ECA works)", "query": "author ECA, since 2022, title ~ recovery|housing|rrf",
                     "url": "https://publications.europa.eu/webapi/rdf/sparql", "status": 200, "hits": len(titles),
                     "screened_titles": " || ".join(titles)})
    except Exception as e:
        rows.append({"date": now, "source": "Cellar (ECA works)", "query": "author ECA", "url": "", "status": f"error:{e}", "hits": "", "screened_titles": ""})
    # ECA special reports located through Cellar (author ECA; titles on the RRF or housing):
    # downloaded and converted to text for grepping and for the quotation check
    import subprocess
    for sr, pat in [("SR-2023-26", r"housing"), ("SR-2024-13", r"lowering targets|Spain"), ("SR-2026-20", r"social housing|Spain")]:
        u = f"https://www.eca.europa.eu/ECAPublications/{sr}/{sr}_EN.pdf"
        st, p = get(u, f"eca_{sr}.pdf", "application/pdf")
        hits, top = "", ""
        if p:
            txt = OUT / f"eca_{sr}.txt"
            if not txt.exists():
                subprocess.run(["pdftotext", "-enc", "UTF-8", str(p), str(txt)], check=True, timeout=240)
            t = re.sub(r"\s+", " ", open(txt, encoding="utf-8").read())
            ms = [t[max(0, m.start() - 100): m.end() + 100] for m in re.finditer(pat, t)]
            hits, top = len(ms), " || ".join(ms[:8])
        rows.append({"date": now, "source": "ECA", "query": f"{sr} grep /{pat}/", "url": u, "status": st, "hits": hits, "screened_titles": top})
    with open(DATA / "prior_work_search.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
