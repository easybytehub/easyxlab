# S19 — Method

*EasyxLab · study S19 · working draft*

The analysis plan in §1 was written on 2026-10-04, after the extent variants had been built and
the buildings that meet them had been selected (so the number of municipalities and buildings
involved was known), and **before any building was compared with an official flood map**. The
scouting pilot for Paiporta (11,986 of 11,988 dwellings inside the extent, 624 built in 2017 or
later) and one rendered SNCZI tile over Paiporta (the T100 zone there is the ravine channel)
were known. The plan's SHA-256 is recorded in `STATUS.md`. Later changes are listed in §9.

<!-- FROZEN-PLAN-START -->
## 1. Analysis plan (frozen)

### 1.1 Question and unit

- **Q1.** How many Catastro dwellings lay inside the observed extent of the flood of 29 October
  2024 in the province of Valencia?
- **Q2.** How many of them lay inside each official flood map, and how many outside all of them?
- **Q3.** How many were in buildings whose Catastro construction year is 2017 or later, after
  Real Decreto 638/2016 (in force since 30 December 2016) added the land-use limits of the
  Reglamento del Dominio Público Hidráulico (RDPH) arts. 9 bis, 9 ter and 14 bis?
- **Unit.** Dwellings: the `numberOfDwellings` of each Catastro INSPIRE building (BU). Buildings
  with dwellings and all buildings are reported as sensitivity units.

### 1.2 The observed extent

- **Source.** Copernicus EMS Rapid Mapping activation EMSR773, every product package delivered
  for an area of interest (AOI) in the province of Valencia: AOI01-04 and AOI07-36 except those
  with no package. AOI05 (Letur, Albacete), AOI06 (Castellón) and AOI15 (Alhaurín de la Torre,
  Málaga) are outside the study area.
- **Primary extent (`all`).** The union of the `observedEventA` polygons with event type
  `5-Flood` and notation `Flooded area` or `Flood trace`, from the latest version of every
  product (first delivery and monitoring), plus the AOI01 `maximumFloodExtentA` of the last
  monitoring product (MONIT04), which Copernicus defines as cumulative.
- **Study area.** The municipalities of the province of Valencia (IGN boundaries) that the
  primary extent or any variant touches.

### 1.3 Official flood maps

- **SNCZI** (MITECO): the fluvial hazard maps for return periods of 10, 100 and 500 years,
  read from the INSPIRE view service as 2 m masks (`scripts/fetch_snczi.py` explains why).
  The preferential flow zone (*zona de flujo preferente*) could not be obtained (§8).
- **PATRICOVA** (Generalitat Valenciana): hazard levels 1-6 (return periods of 25, 100 and 500
  years by depth) and the geomorphological hazard (level 7).
- **Map status** of a building, mutually exclusive, in this order: SNCZI T10; SNCZI T100 (not
  T10); SNCZI T500 (not T100); PATRICOVA levels 1-6 only; PATRICOVA geomorphological only;
  outside every official zone.

### 1.4 Rules

- **Flooded.** A building is inside the extent when its footprint intersects it (`fp`).
- **In a zone.** A building is in a zone when its footprint meets it (`fp`): for SNCZI, at
  least one 2 m pixel centre inside the footprint is in the zone; for PATRICOVA, the footprint
  intersects a zone polygon.
- **Construction year.** `dateOfConstruction/end` (else `beginning`). Bands: 1985 or earlier;
  1986-2007; 2008-2016; 2017-2024; 2025 or later; unknown. 2017 or later is "after RD
  638/2016". 2025 or later is reported apart: it mixes rebuilding after the flood with new
  building.
- **Use.** `currentUse` as published (residential, agriculture, industrial, office, retail,
  public services).

### 1.5 Headline

- **H1.** Dwellings inside the primary extent (Q1), with the number of municipalities.
- **H2.** The share of those dwellings outside every official zone (Q2), with its uncertainty:
  the range over the sensitivity scenarios of §1.6 and over leaving out one municipality at a
  time. The census has no sampling error; a binomial interval is shown only as a descriptive
  bound and is not the uncertainty we claim.
- **H3.** Dwellings built in 2017 or later inside the extent (Q3), by map status.

### 1.6 Sensitivity

- **Extent product and version.**
  - `first`: first deliveries only, no monitoring.
  - `aoi01_first`: AOI01 DEL_PRODUCT v1 only (Sentinel-2 and Landsat-8, 30-31 October): the
    pilot's extent.
  - `flooded_only`: without `Flood trace`.
  - `earlier_versions`: version 1 of the products re-issued with a changed delineation
    (AOI03 GRA, whose v2 corrects that "not all flood traces were delineated").
  - `gva_footprint`: the Generalitat Valenciana's own footprint (ICV), an independent product.
- **Building against dwelling.** The share outside every zone counted in dwellings, in
  buildings with dwellings and in all buildings.
- **Edge.** The primary extent buffered by +/-10 m and +/-25 m; and the centroid rule (`ct`)
  instead of the footprint rule, for the extent and for the zones.

### 1.7 Framing

Building in a flood zone after 2016 is not, by itself, a breach of anything: RDPH arts. 9 ter and
14 bis allow new building on land that was already *urbanizado* on 30 December 2016, under
conditions, and the land's legal situation on that date is not open data. Every count of
post-2016 dwellings is reported as **exposure**, never as illegality.
<!-- FROZEN-PLAN-END -->

## 2. Sources

| source | host and access | what we took | licence and attribution |
|---|---|---|---|
| Copernicus EMS Rapid Mapping, EMSR773 | `rapidmapping.emergency.copernicus.eu` public dashboard API (`/backend/dashboard-api/public-activations/?code=EMSR773`) and product ZIPs (redirected to `rapidmapping.s3.amazonaws.com`) | activation record; 38 product packages (latest versions, 551 MB) and 2 earlier versions (AOI03 GRA v1, AOI02 DEL v1); AOI17 GRA v1 answered 404 | users «shall have a free, full and open access to Copernicus Service Information» (Reg. (EU) 2021/696, CEMS terms page); attribution «Copernicus Emergency Management Service (© 2024 European Union), EMSR773» |
| Generalitat's flood footprint | ICV WFS `terramapas.icv.gva.es/00_DANA2024`, layer `DANA2024.ZonasInundadas.HuellaInundacion` (Magro and Poyo, Saleta and Picassent systems; lineage «partiendo de la cartografía de la Universitat de València») | one multipolygon | CC BY-NC-ND 4.0: used only for counts; no geometry or derived geometry published |
| Catastro INSPIRE Buildings | `www.catastro.hacienda.gob.es/INSPIRE/buildings/46/ES.SDGC.bu.atom_46.xml` and one ZIP per municipality, dated 21 August 2026; no Cl@ve; the server omits the FNMT intermediate certificate (AC Componentes Informáticos / AC Servidores Seguros Tipo2), which we added from the FNMT's own AIA URLs, with verification on | 121 municipalities, 226 MB | free use «as long as that the D. G. of the Cadastre (Ministry of Finance) is mentioned as author and owner of the information» (feed `<rights>`); licence of July 2016 allows public use of transformed data. Author: Dirección General del Catastro |
| ARPSI fluvial hazard maps, RD 903/2010 (MITECO, published through the SNCZI) | INSPIRE WMS `servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones`, layers NZ.Flood.FluvialT10/T100/T500 (water-depth maps), 2,048 m tiles at 2 m per pixel | T500: 441 tiles; T100: 278 (skipped where the T500 tile is empty); T10: 434 (skipped only where a T100 tile exists and is empty) | CC BY 4.0 (MITECO catalogue); «© Ministerio para la Transición Ecológica y el Reto Demográfico». Product page «Actualización 20/12/2024»; Internet Archive captures of 14-8-2024 and 11-11-2024 read «05/07/2022» |
| PATRICOVA, peligrosidad de inundación | ICV geoprocessing service `carto.icv.gva.es/arcgis/rest/services/utils/descargas/GPServer/tarea_descarga_datos` (the call the ICV download page makes), 4 October 2026 | layer `orde_patricova_peligrosidad_inun`, 8,415 polygons | CC BY 4.0; «PATRICOVA: Peligrosidad por Inundación CC BY 4.0, Generalitat» |
| Municipal boundaries | IGN INSPIRE WFS `www.ign.es/wfs-inspire/unidades-administrativas`, filter on national code `34104646*` | 266 municipalities of the province of Valencia | CC BY 4.0, «© Instituto Geográfico Nacional» |
| Other Generalitat DANA layers | ICV WFS `terramapas.icv.gva.es/00_DANA2024` | `MunicipiosAfectados` (Decreto 164/2024), `NivelRiesgoMunicipal` | CC BY 4.0 (not used in the counts) |
| Legal texts | BOE open-data API (consolidated texts, block versions) and `www.boe.es/diario_boe/txt.php`; DOGV | RDPH (BOE-A-1986-10638) arts. 9, 9 bis, 9 ter, 14, 14 bis as in force; RD 638/2016; RD 665/2023; RD 903/2010 | public legal texts |

All requests: User-Agent `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`,
robots.txt read before each host (RFC 9309 parser copied from S8), every request logged with its
time (`work/fetch_log.jsonl`, not published). Requests to a host are at most one per second (the
host's Crawl-delay if larger), except that the first request to a host can follow its robots.txt
request in under a second (six such pairs in the log). Access exceptions and refusals are in §7.

## 3. Processing

1. `scripts/build_extent.py` reprojects every `observedEventA` / `maximumFloodExtentA` layer from
   WGS 84 to ETRS89 / UTM 30N (EPSG:25830), unions it per product and per variant, and lists the
   municipalities each variant touches. The Generalitat's footprint is read as a variant.
2. `scripts/fetch_catastro.py` pairs Catastro and INE municipality codes (they differ for 40 of
   266 municipalities) by name similarity among overlapping bounding boxes
   (`data/municipality_codes.csv`) and downloads the touched municipalities.
3. `scripts/parse_buildings.py` streams each `building.gml` and keeps the buildings that meet any
   extent variant, with use, dwellings, construction year, condition and footprint. It drops the
   cadastral reference while reading.
4. `scripts/fetch_snczi.py` requests the hazard-map tiles that contain a kept building.
   `scripts/check_nesting.py` checks the nesting of the zones on the tiles where both layers were
   fetched: 0.9% of T100 pixels and 0.3% of T10 pixels fall outside the T500 grid, and in 1 of 434
   tiles the T500 grid is empty while the T10 grid is not (`data/snczi_nesting.json`).
5. `scripts/classify.py` flags each kept building against the ARPSI maps and PATRICOVA:
   footprint and centroid, on the depth grid as drawn and on envelopes that close the dry holes
   the grid encloses, up to 0.5, 2 and 5 ha (holes are found on the 3 x 3 mosaic of neighbouring
   tiles). A pixel is in the zone when its alpha is above 0. The style is a depth ramp with an
   alpha fade on the shallowest class.
6. `scripts/qa_holes.py` measures how the depth grid treats buildings (`data/qa_holes.json`).
7. `scripts/analyse.py` writes the published aggregates, applying the disclosure control of §5
   (`scripts/disclosure.py`), and `data/summary.json`.
8. `scripts/check_headlines.py` recomputes the headline numbers from `data/` and checks them in
   README and paper. `scripts/check_disclosure.py` tests the published files (§5).

## 4. What the published tables contain

All counts are for the reference scenario (Copernicus extent `all`, footprint intersects the
extent, footprint touches the 2-ha zone envelope) unless the column says otherwise.

- `flooded_dwellings.csv`: municipality × map status (5 classes: ARPSI 100-year zone including
  the 10-year zone; 500-year zone; PATRICOVA levels 1–6 only; PATRICOVA geomorphological only;
  outside every zone) × year band (2016 or earlier, or unknown; 2017–2024; 2025 or later):
  buildings with dwellings and dwellings.
- `municipalities.csv`: per municipality:
  - flooded area;
  - Catastro dwellings;
  - dwellings in the extent and outside every zone, under the reference rule and under the
    centroid-in-envelope rule;
  - dwellings built 2017–2024, and those outside every zone;
  - the same counts for the Generalitat's footprint.
- `by_year.csv`: province, 5 year bands (the 2 dwellings of unknown year are in the oldest band) ×
  5 map statuses.
- `by_use.csv`: province, use × map status: all buildings, buildings with dwellings, dwellings.
- `zone_overlap.csv`: dwellings by ARPSI × PATRICOVA 1–6 × PATRICOVA geomorphological.
- `extent_comparison.csv`: per municipality, dwellings in the Copernicus extent, in the
  Generalitat's footprint, in both, in either.
- `sensitivity.csv`: every extent variant × extent rule × zone rule (8) × unit, province totals.
- `leave_one_out.csv`: the reference share with each municipality of 5 or more buildings left
  out, rounded to 0.1 points.
- `summary.json`: headline numbers, the matched comparison, the ranges, the pilot.
- `sources.json`: inputs with SHA-256.
- `qa_holes.json`, `snczi_nesting.json`: QA of the hazard-map masks.

No table has addresses, cadastral references or building rows.

## 5. Disclosure control

- **Primary suppression.** A cell is withheld (`<5`, every column of the cell) when it represents
  1–4 buildings: buildings with dwellings, or all buildings in `by_use.csv`.
- **Complementary suppression** (`scripts/disclosure.py`). The published files imply many linear
  relations:
  - municipal totals are sums of cells, and municipal cells add up to province cells;
  - province status and band totals add up to the grand total, as do the uses and the zone
    overlap;
  - in the extent comparison, 'either' = 'copernicus' + 'gva' − 'both';
  - province totals of the centroid rule and of the Generalitat's footprint are in
    `sensitivity.csv`.

  First, every relation with a single withheld value gets a second one withheld, preferring a
  cell of the same municipality and the smallest, often a zero. Then a value is still recoverable
  when it is fixed by the published values, which we test with the null space of the relations:
  if every null-space vector has a zero in that value's position, the value is fixed. While any
  value is recoverable, one more cell is withheld. The run ends with 271 primary and 69
  complementary withheld cells.
- **Shares.** Shares appear only where both counts are published.
- **Leave-one-out.** Shares are rounded to 0.1 points, without counts.
- **summary.json.** It has no count below 5.
- **Coarser categories.** To keep the number of withheld cells low, the municipal table merges the
  ARPSI 10-year zone into the 100-year zone and uses three year bands. The province table uses
  five bands, and the 10-year zone appears only as a province total.
- **Independent test.** `scripts/check_disclosure.py` rebuilds the relations from the files as
  published, independently of `analyse.py`, and fails if any cell represents 1–4 buildings, if
  `summary.json` holds a count of 1–4, if a share is published next to a withheld count, or if any
  withheld value is fixed by the published ones.
- **Working files.** `work/buildings/` and `work/flags/` keep footprints, use, dwellings and year
  per building, without cadastral reference. They are git-ignored and never published.

## 6. Validation

- **Pilot.** With the AOI01 first delineation, Paiporta gives 11,987 of 11,988 dwellings (pilot:
  11,986) and 624 dwellings in 99 buildings dated 2017 or later (pilot: the same).
- **Code pairing.** 266 Catastro feed entries map to 266 distinct INE codes. The two weakest name
  matches are bilingual names (Sagunt/Sagunto, Novetlè).
- **Hazard-map masks:**
  - the nesting check (§3, step 4);
  - a visual check of the densest tile (Catarroja and Alfafar), with building outlines over the
    T500 grid, filled and unfilled (`work/qa/t500_tile.png`, not published);
  - `qa_holes.py`: in Paiporta, Alfafar, Catarroja, Sedaví, Massanassa and Algemesí, the median
    building inside the extent that touches the T500 grid has 9% of its footprint pixels in the
    grid; 97% of the buildings that touch a PATRICOVA 1–6 polygon lie wholly inside it.
- **Independent review.** An independent reviewer re-derived the flags from the building files
  with the published code (0 differences on 61,174 buildings) and recomputed the headline numbers
  with its own code.
- **Tests.** `tests/test_s19lib.py`: building parser (holes, multi-patch surfaces, no identifier
  returned), year bands, status order, cell formatting, pixel sampling, hole filling at several
  limits, and the disclosure engine.

## 7. Robots.txt and access controls

- **robots.txt.** It is read before every host and followed where it can work as a reservation
  (RFC 9309 parser). `catalogo.datosabiertos.miteco.gob.es` answers 403, and `www.ign.es`, two
  Copernicus hosts and three ICV hosts answer 404 on `/robots.txt`: no restriction (RFC 9309, 4xx).
- **Unreadable robots.txt on open geodata hosts.** RFC 9309 would read an unreachable robots.txt as
  "disallow all". We follow robots.txt to the legal minimum, and four hosts that serve openly
  licensed public geodata are therefore treated as open (`OPEN_LICENCE_HOSTS` in `polite.py`, as
  in S14):
  - `gis.miteco.gob.es` and `servicios.idee.es` reset the connection on `/robots.txt`, and only
    there, also without a User-Agent. 1 and 1,155 requests were made.
  - `wmts-snczi.idee.es` answered 502 on `/robots.txt`; one request (the WMTS capabilities) was
    made 21 s later.
  - `wms-snczi.idee.es` is listed but was never requested.
- **Access controls:**
  - The ALTCHA challenge in front of the SNCZI shapefiles is an access control. The log has one
    GET of the page and no POST.
  - The Consorcio de Compensación de Seguros allows `/noticias*` in its robots.txt but disallows
    `/documents/*`, where its DANA claim notes are published as PDFs. We read the news page and not
    the notes.
- **Refusals.** Newspaper search pages that refused us (El País 403, Levante-EMV 406) were not
  retried with other headers.

## 8. Known gaps

- **Map version.** The ARPSI hazard maps read are the version dated 20 December 2024, after the
  flood. The version in force on 29 October 2024 (dated 5 July 2022 on the product page) could not
  be obtained.
- **Zone polygons.** The SNCZI flood-zone polygons and the preferential flow zone could not be
  obtained without passing the ALTCHA challenge. The MITECO WMS of the polygons failed with a
  server error on every request on 2026-10-04 (`work/snczi/zfp_probe.txt`). The polygons may
  include stretches and geomorphological zones with no depth grid: if so, our share outside is too
  high.
- **The preferential flow zone.** It is defined from the 100-year flood (RDPH art. 9.2), so a
  building in it is normally inside the 100-year hazard zone. If so, the omission changes the split
  between zones and not the count outside every zone; we could not check it.
- **Resolution.** The CNIG distributes the same hazard maps as 1 m GeoTIFFs; the WMS is resampled
  to 2 m. Not tested.
- **Press and institutional counts.** Counts of damaged dwellings (insurance claims, building
  inspections, property-tax relief, press data desks) were not searched.

## 9. Changes after the plan was frozen

1. **Envelope rules.** After the plan was frozen we saw that the hazard maps are water-depth grids
   in which buildings, and often whole blocks, are dry holes. The planned centroid rule on the grid
   therefore misplaces buildings that stand inside a flooded block. We added envelopes: every hole
   the zone encloses, up to 0.5, 2 or 5 ha, is closed (on the 3 x 3 mosaic of neighbouring tiles),
   and the building is tested with its footprint or its centroid. PATRICOVA polygons have no such
   holes. Closing holes can only add zone pixels, so it can only lower the share outside. Whether
   the official zone polygons fill urban blocks could not be checked.
2. **Union of extents (`all_or_gva`).** The Generalitat's footprint covers only the Magro and the
   Poyo, Saleta and Picassent systems and disagrees strongly with Copernicus inside them, so we
   added their union. Its flags are derived from the existing ones: a footprint meets a union iff
   it meets either part.
3. **Reference rule changed after review (coordinator decision).** The independent review showed
   that the frozen primary rule (footprint on the depth grid, 53.1%) is not the most favourable to
   the maps: the footprint touching the 2-ha envelope gives 51.1% (Copernicus) and 38.9%
   (Generalitat footprint). The reference figure is now that rule, given for both extents, and the
   abstract leads with the range over the two extents and the three rules (about 39–62% in
   dwellings; up to 66% with the Copernicus product versions, edge buffers and the building's
   centroid tested against the extent). Until the second review the abstract gave 39–66% for the
   two extents and three rules, which includes those variants.
4. **Frozen-plan range.** §1.5 asked for the range over all scenarios of §1.6, which is
   40.8–87.6%. We report it, and we report the range in parts because two scenarios measure
   something else:
   - `flooded_only`: only the water still standing in the image (3,173 dwellings);
   - the centroid zone rule on the unfilled grid, an artefact of the holes.
5. **Matched comparison.** The Copernicus extent and the Generalitat's footprint are compared in
   the 66 municipalities where the footprint has dwellings (`summary.json`, `matched_comparison`).
6. **Disclosure control rebuilt after review.** Suppression is now by building count with
   complementary suppression and an independent recoverability test (§5). To keep it workable, the
   municipal table uses 5 map statuses and 3 year bands, and the province table 5 statuses and 5
   bands. The year-band and status breakdowns of `summary.json` were reduced to totals that the
   tables support.
7. **Added tables.** `extent_comparison.csv`, `qa_holes.json`, and the Generalitat-footprint and
   centroid columns of `municipalities.csv`.
8. **Share precision.** Shares in `sensitivity.csv` are stored to six decimals, so that the
   one-decimal figures in the text round correctly.
9. **Classifier rerun.** `classify.py` now recomputes when it is newer than its flags, and the
   published flags come from the published code (forced rerun on 2026-10-04).
10. **Ranges in `summary.json` (second review, 2026-10-05).** `ranges.headline_dwellings` is the
    headline range (two extents, footprint meets the extent, three rules: 38.9–61.9%);
    `ranges.with_variants_dwellings` adds the Copernicus product versions, edge buffers, the union
    and the centroid tested against the extent (38.9–66.0%). The former `reported_dwellings`,
    which also includes the 0.5 and 5 ha envelopes (38.9–70.1%), is now
    `all_envelope_thresholds_dwellings`. No flag or count changed; the values were derived from
    `sensitivity.csv`, as `analyse.py` now does.
