#!/usr/bin/env python3
"""S23: the figures table. Every official (or officially cited) figure for the size of Spain's
public/social/protected housing stock, and the comparison figures we collected: averages for the
EU or Europe (two of them, EU-05 and EU-09, from EU housing texts with no figure for Spain's
public housing stock) and two shares for named countries (EU-13, EU-14). Each row has the literal quotation, the source, the dates,
the definition and the unit.

The rows are written by hand from the downloaded sources; this script checks that every
quotation occurs literally (after whitespace normalisation) in the raw source text and writes
data/figures.csv (Spain) and data/eu_averages.csv (the comparison figures). Exit 1 if a
quotation is not found.

Columns
  id            stable id (ES-nn for Spain, EU-nn for comparison figures)
  publisher     who published the document
  document      the document
  doc_date      date of the document (ISO)
  ref_year      reference year of the figure, as stated or as traced (see 'notes')
  value         the number as printed
  unit          dwellings | % of households (= principal dwellings) | % of total dwellings |
                % of population | text (no number)
  concept       A publicly owned rental stock (survey of owners)
                B tenure survey: rent below market price (households)
                C tenure survey: rent below market price or free (population)
                D mixed: Housing Europe national estimates, weighted by principal dwellings
                E OECD social rental stock (national definitions)
                F protected or regulated housing incl. for sale
                G attributed figure that does not match its cited source
                H qualitative comparison, no number
                I State-side partial figure: programme pipeline, planned transfer or units let (not
                  a count of the State's stock)
  cited_source  the source the document itself gives for the figure ('' = none given)
  quote         literal quotation (language of the source)
  raw           local raw file the quotation was checked against (data/raw/, not published)
  url           public URL of the source
  locator       where in the document
  notes         our notes
"""
import csv, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s23lib import DATA, quote_found

BOE_LEY = "https://www.boe.es/buscar/act.php?id=BOE-A-2023-12203"
BOE_PLAN = "https://www.boe.es/buscar/act.php?id=BOE-A-2026-8872"
OVS20 = "https://publicaciones.transportes.gob.es/observatorio-de-vivienda-y-suelo-boletin-especial-vivienda-social-2020"
OVS24 = "https://publicaciones.transportes.gob.es/observatorio-de-vivienda-y-suelo-boletin-especial-alquiler-residencial-2024"
OECD = "https://webfs.oecd.org/Els-com/Affordable_Housing_Database/PH4-2-Social-rental-housing-stock.pdf"
HE19 = "https://www.housingeurope.eu/wp-content/uploads/2024/11/Publication%202019%20for%20WEB.pdf"
HE21 = "https://www.housingeurope.eu/wp-content/uploads/2024/11/The_State_of_Housing_in_the_EU_2021_digital.pdf"
HE25 = "https://www.housingeurope.eu/wp-content/uploads/2025/10/spain_the_state_of_housing_in_the_eu_2025_digital.pdf"
BDE23 = "https://www.bde.es/f/webbe/SES/Secciones/Publicaciones/PublicacionesAnuales/InformesAnuales/23/Fich/InfAnual_2023_Cap4.pdf"
BDE2432 = "https://www.bde.es/f/webbe/SES/Secciones/Publicaciones/PublicacionesSeriadas/DocumentosOcasionales/24/Fich/do2432.pdf"
INE_ECV = "https://www.ine.es/jaxiT3/Tabla.htm?t=76845"
EUROSTAT = "https://ec.europa.eu/eurostat/databrowser/view/ilc_lvho02/default/table"
INE_CENSO = "https://www.ine.es/censos2021/censos2021_proyecto.pdf"


def eurlex(c):
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{c}"


F = []


def add(**k):
    F.append(k)


# ------------------------------------------------------------------ Spain: the stock
add(id="ES-01", publisher="Cortes Generales (BOE)", document="Ley 12/2023, por el derecho a la vivienda, preamble", doc_date="2023-05-24",
    ref_year="not stated (2019: traced to OVS 2020, ES-03)", value="290,000", unit="dwellings", concept="A",
    cited_source="«últimas estimaciones del Observatorio de Vivienda y Suelo»",
    quote="se puede señalar que en España existe un parque de vivienda social, considerando como tal, exclusivamente, la vivienda en alquiler de titularidad pública, situado en el entorno de las 290.000 viviendas",
    raw="boe/ley12_2023_texto.xml", url=BOE_LEY, locator="Preámbulo, section on Title III",
    notes="Split given in the same paragraph: «unas 180.000 son de titularidad de las comunidades autónomas y entidades dependientes, y otras 110.000 viviendas son de titularidad de los ayuntamientos y entidades dependientes».")
add(id="ES-02", publisher="Cortes Generales (BOE)", document="Ley 12/2023, preamble", doc_date="2023-05-24",
    ref_year="not stated", value="1.6", unit="% of households", concept="A", cited_source="as ES-01",
    quote="Este parque de 290.000 viviendas sociales apenas ofrece cobertura a un 1,6 % de los 18,6 millones de hogares que habitan en España",
    raw="boe/ley12_2023_texto.xml", url=BOE_LEY, locator="Preámbulo",
    notes="Denominator: 18.6 million households. The same paragraph compares with «porcentajes sensiblemente superiores al 15 %» in six countries, «considerando el total del parque de vivienda social»; the law gives no EU average.")
add(id="ES-03", publisher="Ministerio de Transportes, Movilidad y Agenda Urbana, Observatorio de Vivienda y Suelo (OVS)",
    document="Boletín Especial Vivienda Social 2020 (NIPO 796-20-148-8)", doc_date="2020-08-11",
    ref_year="2019 (Cuestionario sobre vivienda social 2019)", value="290,000", unit="dwellings", concept="A",
    cited_source="own questionnaire to the 17 regions and municipalities",
    quote="en España existe un parque de vivienda social (vivienda en alquiler de titularidad pública) situado en el entorno de las 290.000 viviendas",
    raw="ovs/OVS_boletin_especial_vivienda_social_2020.pdf", url=OVS20, locator="Introducción, p. 3",
    notes="«basadas en las respuestas aportadas por las 17 comunidades autónomas y en el escalado por población de los datos aportados por un total de 162 municipios que han respondido al cuestionario, y que representan 21,9 millones de habitantes». Regional component (Tabla 2.2): 178,493 dwellings in rental (incl. low-price cession), 239,405 owned in all tenures.")
add(id="ES-04", publisher="OVS (Ministry)", document="Boletín Especial Vivienda Social 2020", doc_date="2020-08-11",
    ref_year="2019", value="1.6", unit="% of households", concept="A", cited_source="own questionnaire",
    quote="Este parque de 290.000 viviendas sociales ofrece cobertura a un 1,6% de los 18,6 millones de hogares que habitan en España",
    raw="ovs/OVS_boletin_especial_vivienda_social_2020.pdf", url=OVS20, locator="Introducción", notes="The law's preamble (ES-01, ES-02) repeats this paragraph almost word for word.")
add(id="ES-05", publisher="OVS (Ministry)", document="Boletín Especial Vivienda Social 2020, Tabla 2.1", doc_date="2020-08-11",
    ref_year="not stated", value="2.5", unit="% of households", concept="D", cited_source="«Fuente: Censo 2011, Eurostat, Housing Europe y elaboración propia»",
    quote="en términos medios, su parque de vivienda social se sitúa en el entorno del 9% con respecto a las viviendas principales, frente al 2,5% de España",
    raw="ovs/OVS_boletin_especial_vivienda_social_2020.pdf", url=OVS20, locator="Cap. 2, Tabla 2.1, p. 31",
    notes="The same bulletin puts Spain at 1.6% (ES-04) in its introduction and at 2.5% (452,040 dwellings) in its EU table. 2.5% is the share Housing Europe 2019 shows for Spain (ES-13). It equals INE's ECV share of households renting below the market price in every year from 2012 to 2016 (2.5); the 2024 edition of the same table fills Spain's cell with the ECV and says so (ES-08).")
add(id="ES-06", publisher="Ministerio de Vivienda y Agenda Urbana (MIVAU), OVS", document="Boletín Especial Vivienda Social 2024 (NIPO 179-24-022-6)",
    doc_date="2025-01-09", ref_year="2023 (Encuesta sobre vivienda social, November 2023)", value="318,000", unit="dwellings", concept="A",
    cited_source="own survey to the regions and main municipalities",
    quote="en España existe un parque de vivienda social situado en el entorno de las 318.000 viviendas. De las cuales, unas 197.000 son de titularidad de las comunidades autónomas y entidades dependientes, y otras 121.000 viviendas son de titularidad de los ayuntamientos y entidades dependientes",
    raw="ovs/OVS_boletin_especial_vivienda_social_2024.pdf", url=OVS24, locator="Introducción, p. 4",
    notes="«basadas en las respuestas aportadas por las 17 comunidades autónomas y en el escalado por población de los datos aportados por un total de 168 municipios que representan 24,5 millones de habitantes». Definition: art. 3 of Ley 12/2023 (publicly owned, rental, cession or other temporary tenure). Dated January 2025 (PDF created 9 January 2025); on the Transparency Portal since 17 February 2025.")
add(id="ES-07", publisher="MIVAU, OVS", document="Boletín Especial Vivienda Social 2024", doc_date="2025-01-09",
    ref_year="2023", value="1.72", unit="% of households", concept="A", cited_source="Census (households)",
    quote="Este parque de 318.000 viviendas sociales ofrece cobertura a un 1,72% de los 18,5 millones de hogares que habitan en España según los datos del último Censo",
    raw="ovs/OVS_boletin_especial_vivienda_social_2024.pdf", url=OVS24, locator="Introducción, p. 4", notes="Denominator: 18.5 million households, Census 2021.")
add(id="ES-08", publisher="MIVAU, OVS", document="Boletín Especial Vivienda Social 2024", doc_date="2025-01-09",
    ref_year="2023 (ECV 2023)", value="3.3", unit="% of households", concept="B", cited_source="INE, Encuesta de Condiciones de Vida 2023",
    quote="Si se considera el parque de vivienda en alquiler social en sentido amplio, más allá del parque de titularidad pública, se puede estimar que éste representa un 3,3% del parque de viviendas principales u hogares en España",
    raw="ovs/OVS_boletin_especial_vivienda_social_2024.pdf", url=OVS24, locator="Introducción, p. 4; Tabla 2.1",
    notes="Tabla 2.1: «En el caso de España el porcentaje de alquiler social se ha estimado a partir de la Encuesta de condiciones de vida del INE, correspondiéndose con la categoría de alquiler inferior al precio de mercado».")
add(id="ES-09", publisher="Gobierno de España (BOE)", document="Real Decreto 326/2026, Plan Estatal de Vivienda 2026-2030, preamble", doc_date="2026-04-22",
    ref_year="not stated (2023: traced to OVS 2024, ES-06)", value="318,000", unit="dwellings", concept="A", cited_source="",
    quote="el parque de vivienda de titularidad pública, de ámbito autonómico y municipal, apenas alcanza las 318.000 viviendas, lo que ofrece cobertura a alrededor del 1,7 % de los hogares",
    raw="boe/rd326_2026_texto.xml", url=BOE_PLAN, locator="Preámbulo", notes="1.7% of households.")
add(id="ES-10", publisher="Gobierno de España (BOE)", document="Real Decreto 326/2026, preamble", doc_date="2026-04-22",
    ref_year="2025 (ECV 2025)", value="3.5", unit="% of households", concept="B", cited_source="«Encuesta de Condiciones de Vida publicada por el Instituto Nacional de Estadística en 2025»",
    quote="se puede estimar que todo el parque de alquiler social en España (inferior a precio de mercado) suma el 3,5 %, situando a España lejos de la media de la Unión Europea del 9 %",
    raw="boe/rd326_2026_texto.xml", url=BOE_PLAN, locator="Preámbulo", notes="Compared in the same sentence with an EU average of 9% (EU-07).")
add(id="ES-11", publisher="INE", document="Encuesta de Condiciones de Vida, tabla 76845 (households by tenure)", doc_date="2026",
    ref_year="2025", value="3.5", unit="% of households", concept="B", cited_source="",
    quote="Total Nacional;Alquiler inferior al precio de mercado;2025;3,5",
    raw="ine/ecv_76845.csv", url=INE_ECV, locator="Total Nacional, 2025",
    notes="Same table: «Cesión» 6.5 (2025); below-market rent 2.5 (each year 2012-2016), 2.7 (2019), 3.3 (2023), 3.4 (2024). ECV is the Spanish part of EU-SILC.")
add(id="ES-12", publisher="Eurostat", document="EU-SILC, ilc_lvho02 (population by tenure status)", doc_date="2026-09-17",
    ref_year="2025", value="9.0", unit="% of population", concept="C", cited_source="",
    quote="Tenant, rent at reduced price or free",
    raw="eurostat/ilc_lvho02_ES_EU27.json", url=EUROSTAT, locator="geo=ES, tenure=RENT_FR, hhcomp=TOTAL, rskpovth=TOTAL",
    notes="Values read from the JSON: ES 8.0 (2019), 8.8 (2023), 9.0 (2025). The category includes free accommodation (INE's 'Cesión'), which INE's 3.5% excludes. Unit is persons, not households.")
add(id="ES-13", publisher="Housing Europe", document="The State of Housing in the EU 2019, country profile Spain", doc_date="2019-10-01",
    ref_year="2017", value="250,000 / 2.5", unit="dwellings / % of occupied stock", concept="D", cited_source="",
    quote="of total occupied housing",
    raw="housingeurope/Publication_2019_for_WEB.pdf", url=HE19, locator="Spain profile, key figures box, p. 84",
    notes="The box prints 250,000 next to «Public rental housing» and, as graphic text, 2,5 % next to the quoted words. 250,000 is about 1.1-1.4% of the occupied stock; the box names no source for 2.5%, which equals INE's ECV below-market-rent share for 2012-2016.")
add(id="ES-14", publisher="Housing Europe", document="The State of Housing in Europe 2021, country profile Spain", doc_date="2021",
    ref_year="2019 (housing stock note: «2019 data»)", value="290,000 (1.1%)", unit="dwellings / % of total dwellings", concept="A",
    cited_source="Ministerio de Transportes (Boletín especial vivienda social 2020)",
    quote="Thus, the social rental stock covers 1.6% of the 18.6 million primary residences in",
    raw="housingeurope/The_State_of_Housing_in_the_EU_2021_digital.pdf", url=HE21, locator="Spain profile, pp. 90-93",
    notes="The profile table shows housing stock 25,793,323 in a cell labelled 2020, with a footnote reading «2019 data», and «290,000 (1.1%)»; the text gives 1.6% of 18.6 million primary residences. Same numerator, two denominators.")
add(id="ES-15", publisher="Housing Europe (data from AVS)", document="The State of Housing in Europe 2025, country profile Spain", doc_date="2025-12-18",
    ref_year="2021 (Census) / not stated", value="318,000 (1.7%)", unit="dwellings / % of households", concept="A",
    cited_source="«Estimates based on: INE Census 2021: Estimates of social rental housing from AVS»",
    quote="Included within this estimate, public housing represents about 1.7% of Spain's housing stock",
    raw="housingeurope/spain_the_state_of_housing_in_the_eu_2025_digital.pdf", url=HE25, locator="Spain profile, p. 1",
    notes="The table divides 318,000 by 18,539,223 (Census 2021 total of the tenure table) = 1.7%; the text calls this a share of the «housing stock». Also: «protected housing should represent overall around 3.4% of the housing stock», attributed to «estimates by the Spanish government»; 3.4 equals INE's ECV below-market-rent share for 2024. Note: «The census data does not distinguish between social and private rental.»")
add(id="ES-16", publisher="OECD", document="Affordable Housing Database, indicator PH4.2 Social rental housing stock (last updated 24 Nov 2025)", doc_date="2025-11-24",
    ref_year="2019", value="290,000 (1.13%)", unit="dwellings / % of total dwellings", concept="E",
    cited_source="OECD QuASH (previous rounds for Spain)",
    quote="The social housing stock is smallest in Colombia, Estonia, Israel, Latvia, Lithuania, Portugal, and Spain, where it accounts for less than 2% of the total housing stock",
    raw="oecd/PH4-2-Social-rental-housing-stock.pdf", url=OECD, locator="Key findings; Table PH4.2.A1 (xlsx)",
    notes="xlsx: Spain 290000, 1.1308203126523195, 2019. Note: «For Spain, the figures may also contain other types of reduced rent housing, e.g. employer-provided dwellings.» Implied denominator 25.6 million dwellings.")
add(id="ES-17", publisher="Banco de España", document="Informe Anual 2023, cap. 4 (published 30 Apr 2024)", doc_date="2024-04-30",
    ref_year="not stated", value="300,000 (1.5%)", unit="dwellings / % of principal dwellings", concept="A", cited_source="",
    quote="con una cifra estimada de este tipo de viviendas en torno a las 300.000 unidades (1,5 % de las viviendas principales)",
    raw="bde/InfAnual_2023_Cap4.pdf", url=BDE23, locator="Cap. 4, section 2.2",
    notes="Gráfico 4.28 note b in the same chapter: «290.000 viviendas, en las que residirían un 1,6 % de los hogares».")
add(id="ES-18", publisher="Banco de España", document="Documento Ocasional 2432, El mercado del alquiler de vivienda residencial en España (Oct 2024)", doc_date="2024-10-16",
    ref_year="2023", value="300,000 (1.5% / 1%)", unit="dwellings / % of principal dwellings / % of total dwellings", concept="A", cited_source="",
    quote="con una cifra estimada en 2023 de este tipo de viviendas situada alrededor de las 300.000 unidades, que representan en torno al 1,5 % de las viviendas principales y el 1 % del stock total de viviendas",
    raw="bde/do2432.pdf", url=BDE2432, locator="Section 3, p. 32",
    notes="Footnote 34: its definition of social rent also counts dwellings let by the public sector at reduced prices such as affordable rent.")
add(id="ES-19", publisher="European Commission", document="SWD(2025) 209, 2025 Country Report - Spain", doc_date="2025-06-04",
    ref_year="not stated", value="1.5", unit="% of total dwellings (as stated)", concept="G",
    cited_source="Banco de España, El mercado del alquiler de vivienda residencial en España, 2024 (= ES-18, footnote 4)",
    quote="Spain’s social rental housing stock represents just 1.5% the total stock, compared to the EU average of 9%",
    raw="eu/52025SC0209", url=eurlex("52025SC0209"), locator="Section 1, footnote 4",
    notes="The cited source gives 1.5% of principal dwellings and 1% of the total stock (ES-18), and an EU/OECD average of about 7% (EU-04); it gives no 9%. The Commission names no other source for 9%.")
add(id="ES-20", publisher="European Commission", document="SWD(2025) 209, 2025 Country Report - Spain", doc_date="2025-06-04",
    ref_year="not stated", value="3.3", unit="% (base not stated)", concept="B", cited_source="Provivienda, Observatorio de Vivienda (footnote 242)",
    quote="Spain’s social housing stock is among the lowest in Europe (3.3% vs 8% EU average)",
    raw="eu/52025SC0209", url=eurlex("52025SC0209"), locator="Annex 11 (also in the executive summary)",
    notes="3.3% and 8% match the OVS 2024 broad figure and its EU-27 average (ES-08, EU-02); we could not check what Provivienda cites, because its page is behind a CAPTCHA. The same document also uses 1.5% vs 9% (ES-19).")
add(id="ES-21", publisher="Council of the EU", document="Council Recommendation of 8 July 2025 on the economic, social, employment, structural and budgetary policies of Spain", doc_date="2025-07-08",
    ref_year="not stated", value="1.5", unit="% of total dwellings (as stated)", concept="G", cited_source="«According to the Bank of Spain»",
    quote="According to the Bank of Spain, the stock of social rental housing is only 1,5 % of the total housing stock, well below the EU average of 9 %",
    raw="eu/32025H03983", url=eurlex("32025H03983"), locator="Recital (34)", notes="Attributes the figure to «the Bank of Spain» without naming a document. Same mismatch as ES-19.")
add(id="ES-22", publisher="European Commission", document="SWD(2026) 209, 2026 Country Report - Spain", doc_date="2026-06-03",
    ref_year="not stated", value="318,000 (1.5-1.7%)", unit="dwellings / % of households", concept="A", cited_source="",
    quote="There are over 318 000 publicly owned rental dwellings, covering only 1.5-1.7% of households",
    raw="eu/52026SC0209", url=eurlex("52026SC0209"), locator="Annex on housing (footnotes 335-337)",
    notes="Same paragraph: 197,000 regional and 121,000 municipal (= OVS 2024), and «Broader estimates that include all protected or regulated housing (rental and sale) ( 336 ) raise the share to around 2.5-3.4% of the total social housing stock. This remains well below the EU average of 6-7%.»")
add(id="ES-23", publisher="European Commission", document="SWD(2026) 209, 2026 Country Report - Spain", doc_date="2026-06-03",
    ref_year="not stated", value="2.5-3.4", unit="% (base not stated)", concept="F", cited_source="footnote 336: art. 3 of Ley 12/2023 (a definition, not a data source)",
    quote="raise the share to around 2.5-3.4% of the total social housing stock",
    raw="eu/52026SC0209", url=eurlex("52026SC0209"), locator="Annex on housing",
    notes="Described as protected or regulated housing, rental and sale; as worded, a share «of the total social housing stock». Both bounds equal values of INE's ECV below-market-rent share (2.5 in 2012-2016, 3.4 in 2024), which measures households paying a below-market rent, not protected housing.")
add(id="ES-24", publisher="Council of the EU", document="Council Recommendation of 10 July 2026 on the economic, social, employment, structural and budgetary policies of Spain", doc_date="2026-07-10",
    ref_year="not stated", value="<2", unit="% of total dwellings («total housing supply»)", concept="A", cited_source="",
    quote="Spain has one of the lowest stocks of social housing across the EU, representing less than 2 % of the total housing supply compared to an EU average of roughly 7 %",
    raw="eu/32026H03922", url=eurlex("32026H03922"), locator="Recital (34)",
    notes="Consistent with 318,000 / 27.0 million dwellings = 1.2%.")
add(id="ES-25", publisher="European Commission", document="SWD(2024) 609, 2024 Country Report - Spain", doc_date="2024-06-19",
    ref_year="not stated", value="", unit="text (no number)", concept="H", cited_source="",
    quote="The share of social housing stock is less than one third of the EU average.",
    raw="eu/52024SC0609", url=eurlex("52024SC0609"), locator="Annex", notes="")
add(id="ES-26", publisher="European Commission", document="SWD(2022) 610, 2022 Country Report - Spain", doc_date="2022-05-23",
    ref_year="not stated", value="", unit="text (no number)", concept="H", cited_source="",
    quote="a significantly larger social housing stock (currently only a small fraction of the EU average)",
    raw="eu/52022SC0610", url=eurlex("52022SC0610"), locator="Annex", notes="")
add(id="ES-27", publisher="Council of the EU", document="Council Recommendation of 14 July 2023 on the 2023 National Reform Programme of Spain", doc_date="2023-07-14",
    ref_year="not stated", value="", unit="text (no number)", concept="H", cited_source="",
    quote="The supply of affordable and social housing remains constrained and is significantly lower than the Union average.",
    raw="eu/32023H0901(09)", url=eurlex("32023H0901(09)"), locator="Recitals", notes="")
add(id="ES-28", publisher="INE", document="Censos de Población y Viviendas 2021, project document", doc_date="2021",
    ref_year="2021", value="", unit="text (no number)", concept="H", cited_source="",
    quote="se proponen estas tres categorías, coincidentes con las especificadas en el actual Reglamento",
    raw="ine/censos2021_proyecto.pdf", url=INE_CENSO, locator="8.5.1 Régimen de tenencia",
    notes="The three tenure categories: owned, rented, other tenure. The census does not separate social from market rent; Housing Europe 2025 says the same (ES-15).")

add(id="ES-29", publisher="Banco de España", document="Informe Anual 2023, cap. 4 (published 30 Apr 2024)", doc_date="2024-04-30",
    ref_year="July 2023", value="47,000 / 14,000 / 10,000", unit="dwellings (available or in development)", concept="I", cited_source="«las cifras públicas disponibles a julio de 2023»",
    quote="unas 47.000 viviendas para alquiler social disponibles o en desarrollo por parte del Ministerio de Vivienda y Agenda Urbana, además de 14.000 de la Sareb y unas 10.000 del Fondo Social de Viviendas en alquiler",
    raw="bde/InfAnual_2023_Cap4.pdf", url=BDE23, locator="Cap. 4, section on public measures",
    notes="A pipeline of State-side programmes (available or in development), not a count of State-owned dwellings.")
add(id="ES-30", publisher="CASA 47 (Entidad Estatal de Vivienda, formerly SEPES)", document="Web page «Traspaso vivienda y suelo» (Acuerdo del Consejo de Ministros de 1 de julio de 2025)", doc_date="2025-07-01",
    ref_year="2025", value="40,000", unit="dwellings (identified for transfer from Sareb)", concept="I", cited_source="information provided by Sareb",
    quote="se han identificado de forma preliminar más de 40.000 viviendas y cerca de 2.400 suelos",
    raw="casa47/traspaso-vivienda-y-suelo.html", url="https://www.casa47.es/traspaso-vivienda-y-suelo", locator="Incorporación de viviendas y suelos de Sareb",
    notes="Dwellings to be transferred from Sareb to the State entity; a planned addition, not a stock count.")
add(id="ES-31", publisher="CASA 47", document="News item: El presidente de Gobierno presenta el portal de vivienda asequible de Casa 47", doc_date="2026-09-07",
    ref_year="2026", value="816", unit="dwellings offered for affordable rent in two calls", concept="I", cited_source="",
    quote="suman 816 viviendas en alquiler asequible que Casa 47 ha impulsado entre ambas convocatorias",
    raw="casa47/w_el-presidente-de-gobierno-presenta-el-portal-de-vivienda-asequible-de-casa-47.html",
    url="https://www.casa47.es/w/el-presidente-de-gobierno-presenta-el-portal-de-vivienda-asequible-de-casa-47", locator="Body",
    notes="Same page: «El portal de vivienda de Casa 47 cuenta ya con más de 800 viviendas». Units offered on the State entity's portal, not its whole stock.")
add(id="ES-32", publisher="CASA 47", document="Plan Anual de Actuación 2026", doc_date="2026",
    ref_year="2026", value="", unit="text (no number)", concept="H", cited_source="",
    quote="Costes asociados al mantenimiento y gestión del parque estatal de viviendas",
    raw="casa47/plan_anual_2026.pdf", url="https://www.casa47.es/planificacion-actuaciones-y-resultados", locator="Programa de Actuación Plurianual",
    notes="The plan refers to a «parque estatal de vivienda» and budgets for it, but gives no count of the dwellings in it.")

# ------------------------------------------------------------------ comparison figures (EU-13, EU-14: named countries)
E = []


def eu(**k):
    E.append(k)


eu(id="EU-01", publisher="OVS (Ministry)", document="Boletín Especial Vivienda Social 2020, Tabla 2.1", doc_date="2020-08-11",
   ref_year="not stated (2017 or latest Housing Europe shares; Census 2011 dwellings)", value="9.3 («en el entorno del 9%»)", unit="% of households (principal dwellings)",
   scope="EU-28 incl. United Kingdom", method="weighted: sum of national social dwellings / sum of principal dwellings",
   cited_source="«Fuente: Censo 2011, Eurostat, Housing Europe y elaboración propia»",
   quote="en términos medios, su parque de vivienda social se sitúa en el entorno del 9% con respecto a las viviendas principales",
   raw="ovs/OVS_boletin_especial_vivienda_social_2020.pdf", url=OVS20, locator="Tabla 2.1, p. 31",
   notes="UE 28 row: 18,969,954 social dwellings / 204,934,814 principal dwellings = 9.3%. The United Kingdom alone contributes 4,627,402.")
eu(id="EU-02", publisher="MIVAU, OVS", document="Boletín Especial Vivienda Social 2024, Tabla 2.1", doc_date="2025-01-09",
   ref_year="2023 (2017 for ten countries; Census 2011 dwellings)", value="8.0", unit="% of households (principal dwellings)",
   scope="EU-27", method="weighted, as EU-01", cited_source="«Fuente: Censo 2011, Eurostat, Housing Europe y elaboración propia»",
   quote="por encima de la media de la Unión Europea que se sitúa en el 8% de viviendas en alquiler social",
   raw="ovs/OVS_boletin_especial_vivienda_social_2024.pdf", url=OVS24, locator="Introducción, p. 5; Tabla 2.1, p. 30",
   notes="UE 27 row: 14,244,330 / 178,642,759 = 8.0%. Spain's row in the same table uses the ECV below-market-rent share (3.3%), not the publicly owned stock.")
eu(id="EU-03", publisher="OECD", document="Affordable Housing Database PH4.2 (last updated 24 Nov 2025)", doc_date="2025-11-24",
   ref_year="2022 or latest", value="7 (OECD) / 8 (EU)", unit="% of total dwellings", scope="OECD countries with data / EU countries with data",
   method="unweighted mean of the countries plotted in Figure PH4.2.1: 19 EU members (EU); all 31 countries, Colombia included (OECD); both reproduced exactly", cited_source="OECD QuASH 2016-2023",
   quote="Social housing represents close to 28 million dwellings and accounts on average for 7% of the total housing stock in the OECD (8% in the EU)",
   raw="oecd/PH4-2-Social-rental-housing-stock.pdf", url=OECD, locator="Key findings",
   notes="xlsx Figure PH4.2.1: EU 7.990085845290703, OECD 7.072980149567512.")
eu(id="EU-04", publisher="Banco de España", document="Documento Ocasional 2432 (Oct 2024)", doc_date="2024-10-16",
   ref_year="2020 or latest", value="about 7", unit="% of total dwellings", scope="«economías europeas» and OECD", method="OECD (2024)",
   cited_source="OCDE (2024)",
   quote="se sitúa, en ambos casos, en torno al 7 % del parque de viviendas",
   raw="bde/do2432.pdf", url=BDE2432, locator="Section 3, p. 32", notes="This is the document the Commission cites for its EU average of 9% (EU-06).")
eu(id="EU-05", publisher="European Commission", document="COM(2025) 1025, European Affordable Housing Plan", doc_date="2025-12-16",
   ref_year="not stated", value="6-7", unit="% of total dwellings («EU housing stock»)", scope="EU", method="«according to the OECD»",
   cited_source="OECD (footnote 24: OECD definition of social rental housing)",
   quote="according to the OECD the average share of social housing today represents only roughly 6-7% of the EU housing stock",
   raw="eu/52025DC1025", url=eurlex("52025DC1025"), locator="Section on social housing, footnote 24", notes="")
eu(id="EU-06", publisher="European Commission", document="SWD(2025) 209, 2025 Country Report - Spain", doc_date="2025-06-04",
   ref_year="not stated", value="9 and 8", unit="% (base not stated)", scope="EU", method="",
   cited_source="Banco de España DO 2432 (for 9%); Provivienda (for 8%)",
   quote="compared to the EU average of 9%",
   raw="eu/52025SC0209", url=eurlex("52025SC0209"), locator="Section 1; Annex 11",
   notes="Two EU averages in one document: 9% (with Spain at 1.5%), attributed to the Banco de España paper, which gives about 7%; and 8% (with Spain at 3.3%), cited to Provivienda. No other origin is stated for 9%.")
eu(id="EU-07", publisher="Gobierno de España (BOE)", document="Real Decreto 326/2026, preamble", doc_date="2026-04-22",
   ref_year="not stated", value="9", unit="% (base not stated)", scope="EU", method="", cited_source="",
   quote="situando a España lejos de la media de la Unión Europea del 9 %",
   raw="boe/rd326_2026_texto.xml", url=BOE_PLAN, locator="Preámbulo",
   notes="No source stated. The 9% values we could trace are the OVS 2020 EU-28 average (EU-01, 9.3%) and Eurostat's EU-27 share of persons renting at a reduced price or free in 2018-2019 (EU-12, 9.3% and 9.1%). The Observatory's 2024 bulletin, dated January 2025, gives 8.0% for the EU-27 (EU-02).")
eu(id="EU-08", publisher="Council of the EU", document="Council Recommendation of 8 July 2025 (Spain)", doc_date="2025-07-08",
   ref_year="not stated", value="9", unit="% of total dwellings (as stated)", scope="EU", method="", cited_source="«According to the Bank of Spain»",
   quote="well below the EU average of 9 %", raw="eu/32025H03983", url=eurlex("32025H03983"), locator="Recital (34)", notes="See ES-21. No origin stated beyond «the Bank of Spain».")
eu(id="EU-09", publisher="European Commission", document="SWD(2025) 1053, Understanding the housing crisis", doc_date="2025-12-16",
   ref_year="not stated", value="6-7", unit="% of total dwellings", scope="EU", method="", cited_source="ESDE 2024 (footnote 94)",
   quote="Today, the EU average share of social housing is between 6 and 7% of the housing stock, accounting for around 28 million homes.",
   raw="eu/52025SC1053", url=eurlex("52025SC1053"), locator="Section on social housing",
   notes="«around 28 million homes» is the OECD-wide total in PH4.2 (EU-03), for which the OECD gives 7% (OECD) and 8% (EU). The same document: «Specific social housing data is not collected by Eurostat.»")
eu(id="EU-10", publisher="European Commission", document="SWD(2026) 209, 2026 Country Report - Spain", doc_date="2026-06-03",
   ref_year="not stated", value="6-7", unit="% (base not stated)", scope="EU", method="", cited_source="",
   quote="This remains well below the EU average of 6-7%.", raw="eu/52026SC0209", url=eurlex("52026SC0209"), locator="Annex on housing", notes="")
eu(id="EU-11", publisher="Council of the EU", document="Council Recommendation of 10 July 2026 (Spain)", doc_date="2026-07-10",
   ref_year="not stated", value="about 7", unit="% of total dwellings («total housing supply»)", scope="EU", method="", cited_source="",
   quote="compared to an EU average of roughly 7 %", raw="eu/32026H03922", url=eurlex("32026H03922"), locator="Recital (34)", notes="No source stated; the value matches the OECD mean (EU-03).")
eu(id="EU-12", publisher="Eurostat", document="EU-SILC ilc_lvho02", doc_date="2026-09-17",
   ref_year="2019 / 2025", value="9.1 / 10.7", unit="% of population", scope="EU-27 (2020)", method="survey: tenant at reduced price or free",
   cited_source="", quote="Tenant, rent at reduced price or free", raw="eurostat/ilc_lvho02_ES_EU27.json", url=EUROSTAT,
   locator="geo=EU27_2020, tenure=RENT_FR", notes="A tenure share, not a stock count. Spain on the same measure: 8.0 (2019), 9.0 (2025).")
eu(id="EU-13", publisher="Cortes Generales (BOE)", document="Ley 12/2023, preamble", doc_date="2023-05-24",
   ref_year="not stated", value=">15 (six countries)", unit="% (base not stated)", scope="France, UK, Sweden, Netherlands, Austria, Denmark", method="",
   cited_source="", quote="lo que contrasta con los porcentajes sensiblemente superiores al 15 % registrados en algunos de los principales países de nuestro entorno",
   raw="boe/ley12_2023_texto.xml", url=BOE_LEY, locator="Preámbulo", notes="No EU average.")
eu(id="EU-14", publisher="Gobierno de España (BOE)", document="Real Decreto 326/2026, preamble", doc_date="2026-04-22",
   ref_year="not stated", value="about 20 (best-practice countries)", unit="% (base not stated)", scope="Austria, France, Netherlands, Nordic countries", method="",
   cited_source="", quote="donde el parque social ronda el 20 %", raw="boe/rd326_2026_texto.xml", url=BOE_PLAN, locator="Preámbulo", notes="")


def main():
    bad = []
    for rows, name in ((F, "figures.csv"), (E, "eu_averages.csv")):
        for r in rows:
            ok = quote_found(r["quote"], r["raw"])
            r["quote_verified"] = "yes" if ok else "NO"
            if not ok:
                bad.append(f"{r['id']}: quotation not found in {r['raw']}")
            # «...» inside notes and cited_source quote the same source: check them too
            for field in ("notes", "cited_source"):
                for q in re.findall(r"«([^»]+)»", r[field]):
                    if not quote_found(q, r["raw"]):
                        bad.append(f"{r['id']}: «{q[:50]}» in {field} not found in {r['raw']}")
        fields = list(rows[0].keys())
        with open(os.path.join(DATA, name), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader(); w.writerows(rows)
    print(f"{len(F)} Spain figures, {len(E)} comparison figures; {len(bad)} quotations not found")
    for b in bad:
        print(" -", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
