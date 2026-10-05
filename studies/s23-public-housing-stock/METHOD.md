# S23 — Method

*EasyxLab · study S23 · working draft*

## 1. Sources

Everything was downloaded on 4 October 2026, except the sources added after review (the
electronic office, the two court rulings, CASA 47, and seven prior-work pages), downloaded on 5
October 2026. Third-party files stay in `data/raw/` (not
published). `data/` holds the literal passages, the numbers we extracted and our
calculations.

| source | host and access | what we took | licence or terms |
|---|---|---|---|
| Ley 12/2023 (consolidated text, metadata, amendment record); RD 326/2026, RD 42/2022, RD 106/2018 and RD 233/2013 (state housing plans); RDL 26/2026 | `www.boe.es`, legislation open-data API (`/datosabiertos/api/legislacion-consolidada/id/{id}/texto`) | preambles, art. 3, arts. 27–33, final provisions | legal texts are not protected by copyright (art. 13 LPI); BOE reuse conditions |
| Constitutional Court rulings STC 79/2024 and STC 190/2025 | `www.boe.es/buscar/doc.php?id=…` (allowed by robots.txt; the `/diario_boe/xml.php` path is disallowed and was not used) | the passages on art. 32 | not protected by copyright (art. 13 LPI) |
| The Ministry's electronic office (sede electrónica), the venue art. 32.2 names | `mivau.sede.gob.es`: home page, site map, procedure search (robots.txt answers 404) | the site's structure; search results for «memoria», «inventario», «parque», «vivienda social» | — |
| CASA 47, Entidad Estatal de Vivienda (the State housing entity, formerly SEPES) | `www.casa47.es`: transparency page, Plan Anual de Actuación 2026, Informe de gestión 2024, evaluation of the annual plan, pages on the Sareb transfer and the rental portal | statements on the State's housing stock | public-sector information; quoted and cited |
| BOE daily summaries, 26 May 2023 – 3 October 2026 | `www.boe.es`, open-data API (`/datosabiertos/api/boe/sumario/{YYYYMMDD}`), one request per day | the title of every item | as above |
| Observatorio de Vivienda y Suelo (OVS), *Boletín Especial Vivienda Social* 2020 (NIPO 796-20-148-8) and 2024 (NIPO 179-24-022-6); the ministry's publications catalogue | `publicaciones.transportes.gob.es` (the ministries' publications centre), free download | introductions, Tablas 2.1–2.3 and 2.8; titles of the catalogue | public-sector information (Ley 37/2007); quoted and cited |
| Stock estimate (dwellings and principal dwellings by province) | `cdn.mivau.gob.es`, CSV `VDP002_01` (listed on datos.gob.es under publisher E05233601) | national totals 2019–2025, as denominators | the datos.gob.es record states no licence |
| INE, Encuesta de Condiciones de Vida, table 76845; Census 2021 project document | `www.ine.es` (`/jaxiT3/files/...csv`; `/censos2021/`) | households by tenure; the census tenure categories | INE terms: reuse with attribution |
| Eurostat, EU-SILC `ilc_lvho02` | `ec.europa.eu/eurostat/api/dissemination` (JSON) | population by tenure, ES and EU-27 | Commission reuse policy (Decision 2011/833/EU) |
| OECD Affordable Housing Database, PH4.2 (PDF and workbook, updated 24 Nov 2025) | `webfs.oecd.org` | Spain's figure, the EU and OECD averages, the country values | OECD terms; quoted and cited |
| Housing Europe, *The State of Housing* 2019, 2021 and 2025 (Spain profile) | `www.housingeurope.eu`, `stateofhousing.eu` | Spain's profile | © Housing Europe; quoted and cited |
| Banco de España, Informe Anual 2023 ch. 4; Documento Ocasional 2432 (2024); Informe Anual 2024 | `www.bde.es` | the stock figure and the averages it uses | quoted and cited |
| European Commission and Council: Council recommendations to Spain 2019–2026, country reports on Spain 2019–2026, COM(2025) 1025, SWD(2025) 1053 | Cellar (`publications.europa.eu`): SPARQL to list the country reports, then the English XHTML of each work | every sentence on social or public housing with a number | Commission reuse policy (Decision 2011/833/EU) |
| datos.gob.es | `/apidata/` linked-data API | 20 title searches; all datasets of the housing ministry's publisher code | — |
| Transparency Portal | `transparencia.gob.es` sitemap and four housing pages | housing pages | — |
| Regional open data | Catalonia (`analisi.transparenciacatalunya.cat`, Socrata API), Andalusia (`juntadeandalucia.es` CKAN API) | catalogue searches; the Generalitat's asset inventory, aggregated by query | — |
| Prior work | Crossref, OpenAlex, Bing News RSS (`/news/search?format=rss`), press pages | see `data/prior_work_search.csv` | — |

**Client.** Every request carried the User-Agent
`EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`. `scripts/polite.py` (copied from
S20) reads robots.txt first (RFC 9309), allows at most one request per second per host through a
clock shared by all processes, and logs every request to `work/fetch_log.jsonl`. The timeout is
120 seconds. Python could not verify the TLS chain of `publicaciones.transportes.gob.es`, which
does not send its intermediate certificate. For that case the fetcher falls back to
`curl --max-time 120`, which verifies the chain against the system store. TLS was never
disabled. By 5 October 2026, 1,792 requests were logged, 1,253 of them to the BOE.

**Not used, and why.**
- **`www.mivau.gob.es`** (the Ministry of Housing) answers HTTP 403 with a page titled «Página web
  bloqueada», to robots.txt and to its home page alike. We did not try to get round it. (Its
  electronic office is a different host, `mivau.sede.gob.es`, which we read; a first attempt used
  a wrong hostname, `sede.mivau.gob.es`.)
- **`datos.comunidad.madrid`**: its robots.txt disallows every agent. The Madrid social-housing
  agency's stock dataset is there, so we did not read it.
- **`data.europa.eu`**: its robots.txt disallows the search API.
- **`servicios.ine.es`** (INE's API) reset every connection. We used the CSV files on
  `www.ine.es` instead.
- **`www.oecd.org`** answers 403. The OECD's 2025 Economic Survey of Spain, whose figure the
  press quotes, could not be opened.
- **`provivienda.org`** and **`fundacionalternativas.org`** answered with a CAPTCHA page (HTTP
  202). `www.elperiodico.com` answered 406.
- **`app.bde.es`** (the Banco de España's redirector for some files) has an unreachable
  robots.txt, which we treat as a full disallow.

## 2. The figures table

`scripts/figures.py` holds one row per figure: 32 for Spain and 14 EU averages, from the
documents above. Each row gives:
- the publisher and the document;
- the document date and the reference year, as stated or as traced;
- the value as printed and its unit;
- the concept (A–I, defined in the script; I marks State-side partial figures);
- the source the document itself cites;
- a literal quotation, the raw file it was checked against, the URL and a locator.

The script checks every quotation, and every «quotation» inside the notes, against the text
of the raw file. Whitespace is collapsed, soft hyphens are removed and typographic quotes are
unified first. PDFs are read in both reading order and layout mode. The script stops if any
quotation is missing. Output: `data/figures.csv` and `data/eu_averages.csv`.

Inclusion rule: a figure is included if an official Spanish or EU text gives it for the size of
Spain's public, social or protected housing stock or for the EU average it is compared with,
or if an official text cites it (OECD, Housing Europe, Banco de España, INE, Eurostat).
Statements without a number (2022–2024 country reports, 2023 recommendation) are included as
concept H, because they show when numbers entered the EU texts.

## 3. Tables of the Ministry's bulletins

`scripts/ovs_tables.py` reads the two bulletins with `pdftotext -layout` and extracts:
- **Tabla 2.1** of both bulletins (the EU comparison): population, dwellings, principal
  dwellings, share and number of social dwellings, by country;
- **the regional tables**: Tabla 2.2 of 2020 (stock owned by the regions in 2019, by tenure),
  Tabla 2.2 of 2024 (2023) and Tabla 2.3 of 2024 (2019 against 2023);
  Tabla 2.3 heads its second column «2024»; the rest of the bulletin dates those figures to
  2023, and so do we.
- **Tabla 2.8 of 2024**: the 409 municipalities of over 20,000 inhabitants, with population
  and stock by tenure. An asterisk marks figures carried over from the 2019 survey.

In the 2020 regional table, empty cells are assigned to columns by position. The script then
compares every printed total with the sum of the printed rows, and every printed change with
the difference of the printed levels (`data/ovs_checks.csv`). Seven unit tests cover the
parsers on literal lines.

## 4. Reconciliation

`scripts/analysis.py`:
- **Denominators** (`data/denominators.csv`): the Ministry's stock estimate (all dwellings and
  principal dwellings, 2019–2025, summed over 51 provinces); Census households (18,539,223);
  the households stated by the law (18.6 million); the stock implied by the OECD figure.
- **Shares** (`data/shares_recomputed.csv`): each stock count over each denominator.
- **OECD averages** (`data/oecd_average_check.csv`): the EU and OECD averages recomputed from
  the OECD workbook. The printed values are the unweighted means of the countries plotted in
  Figure PH4.2.1: the 19 EU members (EU) and all 31 countries, Colombia included (OECD). One
  row of that sheet carries the notes in its label cell; its value is Belgium's, matched to
  Table A1. Weighted means are given for comparison.
- **EU averages of the Ministry's bulletins**: recomputed from Tabla 2.1, with and without the
  United Kingdom.
- **The municipal component**: the observed municipal rental stock, scaled by population as
  the bulletin describes, over our sample (181 municipalities, 24.0 million people) and over the
  bulletin's stated base (24.5 million).
- **The ECV series** 2012–2025, to test which published shares equal a year of it.
- **`data/reconciliation.csv`**: 17 differences, each with figures, explanation, category and
  a numerical check. Categories:
  - denominator;
  - reference year or survey round;
  - definition;
  - scope;
  - method;
  - attribution that does not match the cited source;
  - arithmetic error in the source;
  - unexplained.

  Each difference also gets a status:
  - **explained**: every number in the row reproduces from published data;
  - **partly explained**: the concept is clear, but at least one number does not reproduce;
  - **error in a source**: an attribution or arithmetic error;
  - **not explained**.

  A figure repeated in several documents (the Commission's and the Council's 9%) is counted
  once. A statement about coverage, such as the absence of the State's own stock from the
  national counts, is not a difference between figures and is not in the table.

## 5. The art. 32 report

`scripts/art32.py` writes the article and the related final provisions literally
(`data/art32_text.csv`, from the consolidated text) and records each route we used
(`data/art32_search.csv`):
1. **The amendment record** of Ley 12/2023: any change to art. 32.
2. **The Constitutional Court.** STC 79/2024 and STC 190/2025, read from `/buscar/doc.php`, for
   what they say about art. 32 and its scope.
3. **The Ministry's electronic office** (`mivau.sede.gob.es`), the venue art. 32.2 names: home
   page, site map, and the procedure search for «memoria», «inventario», «parque» and
   «vivienda social».
4. **The Ministry's main website** (`www.mivau.gob.es`): HTTP 403.
5. **CASA 47**, the State housing entity: its transparency page and planning documents.
6. **Every BOE issue** from 26 May 2023 to 3 October 2026 (`scripts/boe_sumarios.py`): 1,227
   days, 1,054 issues. Item titles are matched against a pattern for the public or social
   housing stock, inventories, annual reports, the "mapa de la vivienda" and art. 32
   (`data/boe_title_hits.csv`). False positives such as «Memoria Democrática» are excluded.
7. **datos.gob.es**: 20 title searches, and every dataset of the housing ministry's publisher
   code.
8. **The publications catalogue**: every title in the housing categories, including all the
   housing ministry's publications since 2023.
9. **The Transparency Portal**: its sitemap and its housing pages.
10. **La Moncloa.**
11. **Bing News RSS.**
12. **The text of the ministry's 2024 social-housing bulletin.**

A report published only on the ministry's main website, which is closed to us, cannot be
excluded.

## 6. Prior work

`scripts/prior_work.py` ran:
- 10 queries each on Crossref (top 20) and OpenAlex (top 25);
- 24 Bing News RSS queries;
- greps of three institutional pages (OECD policy brief, Fundación Alternativas, AIReF);
- site searches of Funcas, Housing Europe and Newtral, for an existing reconciliation;
- one Funcas article and two Newtral fact checks;
- 12 press articles (11 read, one answered HTTP 406).

It logs each with date, URL, status, hits and screened titles (`data/prior_work_search.csv`).
We also read the OpenAlex records of seven works found this way.

## 7. What could not be done

- **The art. 32 report on the ministry's main site.** We checked the electronic office that the
  law names, but the main site (`https://www.mivau.gob.es/`) answers 403 to our client, and we
  did not check it any other way. A report published only there cannot be excluded.
- **The OECD Economic Survey of Spain 2025.** The press quotes it as putting social rent at
  «tan solo el 3% del parque inmobiliario». We could not open it (`www.oecd.org`, 403).
- **Regional agencies' own figures cannot be summed.**
  - Madrid's agency publishes a stock dataset, but on a portal whose robots.txt disallows us.
  - Catalonia's asset inventory (13,552 items) does not itemise the housing agency's stock.
  - Andalusia's catalogue has no stock dataset.
  - The Basque datasets are contract registers.
- **The Ministry's municipal scaling.** The bulletin does not publish it. Our sample (181
  municipalities, 24.0 million people) gives 120,805; the bulletin's stated base (168
  municipalities, 24.5 million) gives 118,419; the printed figure is 121,000.
- **Provivienda's figures** (cited by the Commission) are behind a CAPTCHA.
- **The Census 2021 tenure tables.** INE's API was unreachable. We rely on the Census project
  document and on Housing Europe's note that the Census does not separate social rent.
