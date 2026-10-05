# S19 — What the maps did not show: dwellings inside the observed extent of the October 2024 DANA in Valencia, and the official flood maps
*EasyxLab · study S19 · Copernicus EMS EMSR773, the Generalitat's flood footprint, Catastro INSPIRE of August 2026, and the ARPSI hazard maps and PATRICOVA as served on 4 October 2026 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s19/paper/](https://easybyte.es/lab/studies/s19/paper/) · [PDF](https://easybyte.es/lab/studies/s19/paper.pdf)

## Abstract

**The question.** How many dwellings lay inside the observed extent of the DANA of 29 October 2024
in the province of Valencia? How many of them lay outside the official flood maps? And how many
were built after Real Decreto 638/2016 limited building in flood zones?
- **The official maps.** The State's hazard maps for the areas of significant potential flood
  risk (ARPSI, RD 903/2010; 10, 100 and 500 years) and the Generalitat's PATRICOVA.

**The answer.** Of the 84,789 dwellings inside the flood extent mapped by Copernicus EMS, the
EU's emergency management service, 43,359 (51.1%) lay outside every official flood zone under the
reference rule. The figure depends on which extent and which rule is used, so we also give it as a
range: about **39–62% of the dwellings inside the observed extent were outside every official flood
zone** across the two flood extents and the three rules, and up to 66% with the Copernicus product
versions, edge buffers and the building's centroid tested against the extent.

| | Copernicus EMS extent | Generalitat's footprint |
|---|---|---|
| dwellings inside the extent | 84,789 dwellings (78 of the 115 municipalities it touches) | 138,217 (66 municipalities) |
| outside every zone: footprint touches the zone envelope (reference) | 43,359 (51.1%) | 53,801 (38.9%) |
| outside every zone: centroid in the zone envelope | 61.9% | 48.6% |
| outside every zone: footprint touches the depth grid as drawn | 53.1% | 40.8% |

**The rules.**
- **The zone envelope.** The hazard map's water-depth grid, with the dry holes that it leaves at
  buildings closed up to 2 ha. PATRICOVA polygons are used as published.
- **The ARPSI maps alone.** 67.4% of the Copernicus-extent dwellings were outside them under the
  reference rule. 8,435 lay inside the 100-year zone.

**The extent matters most.**
- **Coverage.** The Copernicus extent was delineated from satellite and aerial images. The
  Generalitat's footprint covers only the Magro and the Poyo, Saleta and Picassent ravines, yet
  holds 1.6 times as many dwellings. With their union (158,044 dwellings) the reference share is
  42.8%.
- **Like for like.** In the same 66 municipalities, the share outside every zone is 51.6% with the
  Copernicus extent and 40.8% with the Generalitat's footprint (footprint on the depth grid; 49.4%
  and 38.9% under the reference rule).
- **Robustness.** Copernicus product versions, ±10/±25 m edge buffers and testing the building's
  footprint or centroid against the extent move the reference figure only within 50.1–53.9%. Leaving out one municipality gives 47.7–54.9%.
- **Places.** The figures differ a lot by town:
  - 71.9% outside in Paiporta, 95.8% in Picanya and 100.0% in Sedaví;
  - at least 98% inside an ARPSI zone in Beniparrell and Massanassa;
  - l'Alcúdia mapped almost only by PATRICOVA's geomorphological level, which has no return
    period.

**Built after 2016.**
- **How many.** 1,776 dwellings in the Copernicus extent are in buildings that the Catastro dates
  to 2017–2024.
- **Map status.** 874 of them lay outside every official zone, and 735 inside an ARPSI zone (156
  inside its 100-year zone).
- **2025 or later.** Another 410 are dated 2025 or later: rebuilding and new building, without
  distinction.
- **No illegality.** These are counts of **exposure**, not of illegality. RDPH arts. 9 ter and 14
  bis allow building in flood zones on land already urbanised on 30 December 2016, under
  conditions that open data do not show.

**The pilot.** For Paiporta we recompute the scouting pilot: 11,987 of 11,988 dwellings inside the
first delineation (the pilot had 11,986) and 624 dwellings in 99 buildings dated 2017 or later.

**Caveats.**
- **Map version.** The ARPSI maps read are the version of 20 December 2024, after the flood.
  Internet Archive captures show that the version in force on the day was dated 5 July 2022. What
  changed is not known.
- **Depth maps, not polygons.** The SNCZI zone polygons and the preferential flow zone could not
  be obtained: their download sits behind an ALTCHA challenge, which we did not pass. The ARPSI
  depth maps were read as rendered 2 m masks.
- **Prior counts not searched.** Press and institutional counts of damaged dwellings could not be
  searched.

**Prior work.**
- **Closest work.** Camarasa-Belmonte et al. (2025) found 14.1% of the flooded **area** outside
  the combined official map. With the same Universitat de València flood map, which the
  Generalitat's footprint starts from, the share of **dwellings** outside is 40.8%. They also note
  that the Copernicus extent «presentaba importantes problemas en áreas urbanas».
- **Possible overlap.** A UPC master's thesis on exposed dwellings in the metropolitan area is
  under embargo until 2030.
- **Novelty claim.** It is limited to the academic literature and the sources listed in
  [the paper](https://easybyte.es/lab/studies/s19/paper/) §3.

## Layout

| path | what it is |
|---|---|
| `scripts/polite.py`, `scripts/robots9309.py`, `scripts/htmltext.py` | fetcher (copied from S11/S14): fixed User-Agent, ≤ 1 request/s per host, robots.txt read (RFC 9309), every request logged |
| `scripts/fetch_ems.py`, `fetch_patricova.py`, `fetch_municipalities.py`, `fetch_gva_dana.py`, `fetch_catastro.py`, `fetch_snczi.py` | downloads: Copernicus EMS, PATRICOVA (ICV), IGN boundaries, Generalitat DANA layers, Catastro INSPIRE buildings, ARPSI hazard-map tiles |
| `scripts/build_extent.py` | the observed extent in 10 variants, and the municipalities each touches |
| `scripts/parse_buildings.py`, `scripts/s19lib.py` | streams each `building.gml`, keeps the buildings that meet any extent (no identifiers kept) |
| `scripts/classify.py`, `scripts/check_nesting.py`, `scripts/qa_holes.py` | flags each building against the ARPSI maps (depth grid and envelopes of 0.5, 2 and 5 ha; footprint and centroid) and PATRICOVA; checks T10 ⊂ T100 ⊂ T500; measures the dry holes the depth grid leaves at buildings |
| `scripts/analyse.py`, `scripts/disclosure.py` | every published table, with suppression of cells under 5 buildings and complementary suppression |
| `scripts/make_sources.py` | `data/sources.json`: inputs with SHA-256 |
| `scripts/check_headlines.py` | asserts every headline number in this README (and in [the paper](https://easybyte.es/lab/studies/s19/paper/), when present) against `data/` |
| `scripts/check_disclosure.py` | tests the published files: no cell under 5 buildings, no small count in `summary.json`, no withheld value recoverable from the published relations (null-space test) |
| `scripts/run.sh` | `run.sh` (fetches first if there is no local copy), `run.sh fetch`, `run.sh check` |
| `tests/test_s19lib.py` | tests of the building parser, year bands, classes, cell formatting, masks, hole filling and the disclosure engine (synthetic inputs) |
| `data/dwellings_in_extent.csv` | municipality × map status (ARPSI 10- and 100-year zones merged) × year band (2016 or earlier, 2017–2024, 2025 or later): buildings with dwellings and dwellings inside the extent, reference scenario |
| `data/municipalities.csv` | per municipality: flooded area, Catastro dwellings, dwellings in the extent and outside every zone (reference and centroid-in-envelope rules), built 2017–2024, and the same for the Generalitat's footprint |
| `data/by_year.csv`, `data/by_use.csv`, `data/zone_overlap.csv` | province: year band × status; use × status; ARPSI × PATRICOVA overlap |
| `data/sensitivity.csv`, `data/leave_one_out.csv`, `data/extent_variants.csv`, `data/extent_comparison.csv` | every extent × building rule × zone rule × unit; the headline without each municipality; extent areas; Copernicus against the Generalitat's footprint |
| `data/summary.json`, `data/snczi_nesting.json`, `data/qa_holes.json` | headline numbers, ranges and the matched comparison; nesting of the zones; dry holes at buildings |
| `data/municipality_codes.csv`, `data/sources.json`, `data/prior_work_search.csv` | Catastro ↔ INE codes; source URLs and SHA-256; every prior-work query |
| [paper](https://easybyte.es/lab/studies/s19/paper/) (web) | the paper (not in the public package; read it at https://easybyte.es/lab/studies/s19/paper/) |
| `data/raw/`, `work/`, `private/` | git-ignored: downloads, building-level working files, logs. Never published. |

## How to run

Python ≥ 3.10 with shapely 2, pyproj, pyogrio (GDAL), lxml, numpy, Pillow and SciPy:

```bash
python3 -m venv .venv && .venv/bin/pip install shapely pyproj pyogrio lxml numpy pillow scipy
bash scripts/run.sh         # in a fresh clone: fetches the public sources, then builds and checks
bash scripts/run.sh fetch   # Copernicus EMS (~620 MB), Catastro (~230 MB), PATRICOVA, IGN, GVA,
                            # ARPSI hazard-map tiles (1,153 requests); about an hour at one request per second
bash scripts/run.sh check   # only the headline and disclosure checks
```

Everything comes from public sources, and nothing depends on files private to the authors. The
heavy steps need about 1.5 GB of RAM. Set `EASYXLAB_HEAVY` to the lab's `heavy.sh` to serialise
them.

Two caveats on rerunning:
- **The Catastro changes.** The published numbers come from the packages of 21 August 2026. Their
  SHA-256 is in `data/sources.json`; a new fetch gives the current packages.
- **The hazard-map tiles.** They are requested only around the buildings found, and the view
  service may change.

The requests are at most one per second per host, with one exception: a robots.txt request may be
followed by the first request to that host in under a second.

## Licences

- Code (`scripts/`, `tests/`): Apache-2.0, see [`../../LICENSE`](../../LICENSE).
- Our data and text: CC BY 4.0, see [`../../LICENSE-DATA`](../../LICENSE-DATA).
- Third-party data are not redistributed. `data/` holds only counts derived from them. No published
  cell represents fewer than 5 buildings, and no withheld value can be recovered from the files
  (`scripts/check_disclosure.py`).
  - Copernicus Emergency Management Service (© 2024 European Union), EMSR773. Free, full and open
    access under Regulation (EU) 2021/696.
  - Fuente: Dirección General del Catastro. The Catastro INSPIRE feed reads: «This service can be
    used free of charge in every instance, as long as that the D. G. of the Cadastre (Ministry of
    Finance) is mentioned as author and owner of the information».
  - ARPSI hazard maps (SNCZI): «© Ministerio para la Transición Ecológica y el Reto Demográfico» (CC BY 4.0).
  - PATRICOVA: Peligrosidad por Inundación CC BY 4.0, Generalitat.
  - Municipal boundaries: © Instituto Geográfico Nacional (CC BY 4.0).
  - Generalitat Valenciana, Institut Cartogràfic Valencià, «Zona inundada por la DANA del 29 de
    octubre de 2024» (CC BY-NC-ND 4.0). Used only for counts; we publish no geometry and no derived
    geometry.
- None of these sources endorses this study.

Cite as: EasyxLab (2026). What the maps did not show: dwellings inside the observed extent of the
October 2024 DANA in Valencia, and the official flood maps. Study S19. EasyByte Hub S. Coop. Mad.
https://github.com/easybytehub/easyxlab

---
EasyxLab · a research lab by [EasyByte](https://easybyte.es)
