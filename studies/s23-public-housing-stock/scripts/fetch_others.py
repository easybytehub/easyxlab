#!/usr/bin/env python3
"""S23: download the non-legal sources into data/raw/ (git-ignored): the Ministry's Observatorio
de Vivienda y Suelo bulletins and its publications catalogue, OECD, Housing Europe, Banco de
España, INE, Eurostat, the MIVAU stock estimate, the Transparency Portal, the national and
regional open-data catalogues used for the art. 32 and regional checks, and OpenAlex records
of prior work. Resumable: existing files are kept. Every request goes through polite.py.

    python3 scripts/fetch_others.py
"""
import os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite
from s23lib import RAW

PUB = "https://publicaciones.transportes.gob.es"
HE = "https://www.housingeurope.eu"
BDE = "https://www.bde.es/f/webbe/SES/Secciones/Publicaciones"
S = [  # (local path under data/raw, url, accept)
    ("ovs/OVS_boletin_especial_vivienda_social_2020.pdf", f"{PUB}/downloadcustom/sample/1078", None),
    ("ovs/OVS_boletin_especial_vivienda_social_2024.pdf", f"{PUB}/downloadcustom/sample/3749", None),
    ("ovs/bevs2020_page.html", f"{PUB}/observatorio-de-vivienda-y-suelo-boletin-especial-vivienda-social-2020", None),
    ("ovs/bevs2024_page.html", f"{PUB}/observatorio-de-vivienda-y-suelo-boletin-especial-alquiler-residencial-2024", None),
    ("ovs/publicaciones_sitemap.xml", f"{PUB}/sitemap.xml", None),
    ("ovs/cat_mivau_p1.html", f"{PUB}/arquitectura-vivienda-y-suelo-mivau", None),
]
S += [(f"ovs/cat_mivau_p{n}.html", f"{PUB}/arquitectura-vivienda-y-suelo-mivau?pagenumber={n}", None) for n in range(2, 9)]
S += [(f"ovs/cat_avs_p{n}.html", f"{PUB}/arquitectura-vivienda-y-suelo?pagenumber={n}", None) for n in range(1, 46)]
S += [
    ("oecd/PH4-2-Social-rental-housing-stock.pdf", "https://webfs.oecd.org/Els-com/Affordable_Housing_Database/PH4-2-Social-rental-housing-stock.pdf", None),
    ("oecd/PH4-2-Social-rental-housing-stock.xlsx", "https://webfs.oecd.org/Els-com/Affordable_Housing_Database/PH4-2-Social-rental-housing-stock.xlsx", None),
    ("housingeurope/spain_the_state_of_housing_in_the_eu_2025_digital.pdf", f"{HE}/wp-content/uploads/2025/10/spain_the_state_of_housing_in_the_eu_2025_digital.pdf", None),
    ("housingeurope/The_State_of_Housing_in_the_EU_2025.pdf", "https://www.stateofhousing.eu/", None),
    ("housingeurope/The_State_of_Housing_in_the_EU_2021_digital.pdf", f"{HE}/wp-content/uploads/2024/11/The_State_of_Housing_in_the_EU_2021_digital.pdf", None),
    ("housingeurope/Publication_2019_for_WEB.pdf", f"{HE}/wp-content/uploads/2024/11/Publication%202019%20for%20WEB.pdf", None),
    ("housingeurope/home.html", f"{HE}/", None),
    ("housingeurope/soh2025_page.html", f"{HE}/state-of-housing-in-europe-2025-trends-in-a-nutshell/", None),
    ("housingeurope/sitemap_index.xml", f"{HE}/sitemaps.xml", None),
    ("housingeurope/post-sitemap1.xml", f"{HE}/post-sitemap1.xml", None),
    ("housingeurope/the-state-of-housing-in-europe-2023.html", f"{HE}/the-state-of-housing-in-europe-2023/", None),
    ("bde/do2432.pdf", f"{BDE}/PublicacionesSeriadas/DocumentosOcasionales/24/Fich/do2432.pdf", None),
    ("bde/do2433.pdf", f"{BDE}/PublicacionesSeriadas/DocumentosOcasionales/24/Fich/do2433.pdf", None),
    ("bde/InfAnual_2023_Cap4.pdf", f"{BDE}/PublicacionesAnuales/InformesAnuales/23/Fich/InfAnual_2023_Cap4.pdf", None),
    ("bde/InfAnual_2024.pdf", f"{BDE}/PublicacionesAnuales/InformesAnuales/24/Fich/InfAnual_2024.pdf", None),
    ("ine/ecv_76845.csv", "https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/76845.csv", None),
    ("ine/ecv_76845.html", "https://www.ine.es/jaxiT3/Tabla.htm?t=76845", None),
    ("ine/censos2021_proyecto.pdf", "https://www.ine.es/censos2021/censos2021_proyecto.pdf", None),
    ("eurostat/ilc_lvho02_ES_EU27.json", "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/ilc_lvho02?format=JSON&lang=EN&geo=ES&geo=EU27_2020", "application/json"),
    ("mivau/VDP002_01.csv", "https://cdn.mivau.gob.es/portal-web-mivau/Datos_MIVAU/CSV/VDP002_01.csv", None),
    ("mivau/boletinonline2_33000000.html", "https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=33000000", None),
    ("transparencia/sitemap.xml", "https://transparencia.gob.es/sitemap.xml", None),
    ("transparencia/observatorioviviendasueloboletinespecialviviendasocial.html", "https://transparencia.gob.es/masinformacion/informes-de-interes/vivienda/observatorioviviendasueloboletinespecialviviendasocial", None),
    ("transparencia/observatorioviviendasuelo2023.html", "https://transparencia.gob.es/masinformacion/informes-de-interes/vivienda/observatorioviviendasuelo2023", None),
    ("transparencia/observatorioviviendasuelo.html", "https://transparencia.gob.es/masinformacion/informes-de-interes/vivienda/observatorioviviendasuelo", None),
    ("transparencia/iv-plan-9-11-1-vivienda-suelo.html", "https://transparencia.gob.es/gobierno-abierto/planes-accion/seguimiento-iv-plan/seguimiento_c9/9-11-1-vivienda-suelo", None),
    ("catalogues/datosgob_publisher_E05233601.json", "https://datos.gob.es/apidata/catalog/dataset/publisher/E05233601.json?_pageSize=200", "application/json"),
    ("regions/cat_catalog_habitatge_public.json", "https://analisi.transparenciacatalunya.cat/api/catalog/v1?q=habitatge%20p%C3%BAblic&limit=50", "application/json"),
    ("regions/cat_catalog_parc_habitatge.json", "https://analisi.transparenciacatalunya.cat/api/catalog/v1?q=parc%20habitatge&limit=50", "application/json"),
    ("regions/cat_inventari_count.json", "https://analisi.transparenciacatalunya.cat/resource/nh2x-3jq4.json?" + urllib.parse.urlencode({"$select": "count(*) as n"}), "application/json"),
    ("regions/cat_inventari_habitatge_groups.json", "https://analisi.transparenciacatalunya.cat/resource/nh2x-3jq4.json?" + urllib.parse.urlencode(
        {"$select": "departament_entitat, tipus_dret, tipus_us, count(*) as n", "$where": "upper(espai) like '%HABITATGE%'",
         "$group": "departament_entitat, tipus_dret, tipus_us", "$order": "n DESC", "$limit": "200"}), "application/json"),
    ("regions/and_ckan_avra.json", "https://www.juntadeandalucia.es/datosabiertos/portal/api/3/action/package_search?q=AVRA&rows=50", "application/json"),
    # robots.txt of datos.comunidad.madrid disallows every agent: this request is logged as skipped, not made
    ("regions/madrid_viviendas_avs.csv", "https://datos.comunidad.madrid/dataset/93394a3c-0777-4216-8978-cc316017526c/resource/4c7087ed-23ec-4e3f-8d96-934e820de369/download/viviendas_avs.csv", None),
]
# added after review: the electronic office named by art. 32.2, the Constitutional Court rulings
# (from /buscar/doc.php, which robots.txt allows) and CASA 47, the State housing entity
S += [
    ("sede/home.html", "https://mivau.sede.gob.es/", None),
    ("sede/sitemap.html", "https://mivau.sede.gob.es/sitemap", None),
] + [(f"sede/search_{t.replace(' ', '_')}.html", "https://mivau.sede.gob.es/procedimientos?search=" + urllib.parse.quote(t), None)
     for t in ("memoria", "inventario", "parque", "vivienda social")] + [
    ("boe/stc_79_2024.html", "https://www.boe.es/buscar/doc.php?id=BOE-A-2024-12808", None),
    ("boe/stc_190_2025.html", "https://www.boe.es/buscar/doc.php?id=BOE-A-2026-1756", None),
    ("casa47/home.html", "https://www.casa47.es/", None),
    ("casa47/planificacion-actuaciones-y-resultados.html", "https://www.casa47.es/planificacion-actuaciones-y-resultados", None),
    ("casa47/traspaso-vivienda-y-suelo.html", "https://www.casa47.es/traspaso-vivienda-y-suelo", None),
    ("casa47/w_el-presidente-de-gobierno-presenta-el-portal-de-vivienda-asequible-de-casa-47.html",
     "https://www.casa47.es/w/el-presidente-de-gobierno-presenta-el-portal-de-vivienda-asequible-de-casa-47", None),
    ("casa47/plan_anual_2026.pdf", "https://www.casa47.es/documents/36596/58792/Plan+Anual+de+Actuaci%C3%B3n+2026.pdf/efc80772-385d-caaa-d59d-b47d632c61ff?t=1767944096524", None),
    ("casa47/informe_gestion_2024.pdf", "https://www.casa47.es/documents/36596/59059/Informe+de+Gestion+2024.pdf/2e946cd5-a9e4-7518-5d5d-6dbae15b4051?t=1776240796390", None),
    ("casa47/evaluacion_plan_anual.pdf", "https://www.casa47.es/documents/36596/58792/Evaluaci%C3%B3n+grado+de+cumplimiento+y+resultados+del+Plan+Anual.pdf/4b3ef04d-7dc8-9912-e45e-b052c9328d3f?t=1775539349217", None),
]
for w in ["W3169283453", "W7162701372", "doi:10.69810/ekz.1036", "doi:10.13060/23362839.2017.4.1.331", "doi:10.69810/ekz.1529",
          "doi:10.1002/9781118412367.ch13", "doi:10.32796/ice.2026.942.7969"]:
    S.append((f"prior/openalex_work_{w.replace(':', '_').replace('/', '_')}.json", f"https://api.openalex.org/works/{w}", "application/json"))


def main():
    ok = bad = 0
    for path, url, acc in S:
        out = os.path.join(RAW, path)
        if os.path.exists(out):
            continue
        try:
            st, _ = polite.fetch(url, out, acc)
            print(st, path, flush=True)
            ok += 1
        except PermissionError as e:
            print("ROBOTS", path, e, flush=True); bad += 1
        except Exception as e:
            print("ERROR", path, type(e).__name__, e, flush=True); bad += 1
    print(f"done: {ok} fetched, {bad} not fetched")


if __name__ == "__main__":
    main()
