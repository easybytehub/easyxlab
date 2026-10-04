# S14 — Method

*EasyxLab · study S14 · working draft*

**The freeze was not blind, and it is self-attested.** Read this before §1.

- The rules below were developed on notices of a separate development period (2024-07-01 →
  2024-12-31), which is not part of the results. Their SHA-256, and copies of the rule scripts,
  were recorded at 2026-10-04T12:41:09Z (`STATUS.md`). At that time this study's session had
  downloaded the summaries (titles) of the study period, but no notice text.
- **The study period had already been read.** The lab's scouting pilot of 2026-10-03, which
  proposed this study, ran a notice-level keyword pass over exactly the same period (2025-01-01
  → 2026-09-30, 318 notices). It reported per-seller rates: 58 of 162 notices for buildings
  (35.8%) with no energy rating; TGSS with the rating in 93 of 108; INVIED in 0 of 9; FOGASA,
  GIESE and others in 0 of 11. It also described the TGSS's fixed sentence. The rules were
  therefore written with prior knowledge of the study period's pattern. The development/study
  split protects the code from tuning on study-period lots. It does not make the rules blind to
  the study period, and the heading of §1 («frozen before the study period was read») is true
  of this session only.
- **The freeze evidence is local.** The hash and the frozen copies sit in the git-ignored
  `private/` folder. Their only timestamps are file times and a request log written by the same
  process. Nothing was committed, published or timestamped by a third party at the time.

Any change after the freeze is listed in §9 "Deviations from the frozen rules", with the reason.

<!-- FROZEN-RULES-START -->
## 1. Classification rules (frozen before the study period was read)

Code: `scripts/select_notices.py` (selection), `scripts/lots.py` (notice parsing and lot
splitting), `scripts/classify.py` (notice kind, seller, lot type, scope, energy statement,
compliance), `scripts/build_lots.py` (applies them). Tests: `tests/`.

### 1.1 Population

- **Notices**: every item of sections V-A, V-B and V-C of the BOE published from 2025-01-01 to
  2026-09-30, read from the daily summary API, whose title matches the selection filter
  (`is_candidate`): a sale word (subasta, enajenación, venta, adjudicación directa…) and either a
  property word (inmueble, finca, vivienda, local, solar, parcela, garaje, nave, lote, urbana,
  rústica…) or a known seller (TGSS, Delegación de Economía y Hacienda, Patrimonio del Estado,
  INVIED). The filter is deliberately wide; the notice text decides.
- **Notice kind** (`notice_kind`, first rule that applies): public-procurement notices of
  section V-A that are not a sale (`other`); correction; annulment, suspension or postponement;
  result (award, void auction); direct sale to a named party (`direct_named`: the notice
  announces a sale to a specific buyer, not an offer to the public); not real estate (movable
  goods, shares, harvests, concessions…); lease (reported separately, not in the headline);
  **offer** (an auction, tender or sale offered to the public). Only **offer** notices enter
  the lot population.
- **Seller**: the body named in the title. Groups: TGSS; Patrimonio del Estado (Delegaciones
  de Economía y Hacienda and the Dirección General del Patrimonio del Estado); INVIED (Defence);
  GIESE (Interior); ADIF/Renfe; port authorities; SEPES/Casa 47; FOGASA; Mutuas; other public
  bodies. Notices of private sellers (if any appear in section V-C) are reported apart and are
  not in the headline.

### 1.2 Lots (`split_lots`)

A paragraph that contains a new sentence starting with a lot header is first split there. Then,
in this order:

1. **Lot headers**: "Lote 1", "LOTE Nº 2", "Lote núm. 3", "Lote número 4", roman numerals
   ("Lote II"), "Lote único", and "Finca/Inmueble/Bien/Propiedad nº N". "Lotes 5 y 6" stays one
   lot (label `multi:…`). When the same label appears more than once (a description section
   and a price section), the segments are merged into one lot.
2. **Numbered items** ("1.- \"Local en …\"", "2) …", "3. …") when there are no lot headers:
   the consecutive run 1, 2, 3…, accepted when the first item and at least half of the items
   name a property or a cadastral reference in the item or the next two paragraphs.
3. **Table rows** that start with a lot number and name a property or a cadastral reference.
4. Otherwise one lot (`single`), unless the text holds two or more cadastral references
   (`unsplit`: one record, resolved in the review) or describes no property at all
   (`not_described`: no cadastral reference and no address, or "relacionados en los anexos").

The general text before the first lot and after the last one (from the first paragraph that
starts the general conditions, or the signature) is the notice's **general text**.

### 1.3 Lot type (`lot_type`)

From the first ~350 characters of the lot; if they say nothing, from 350 characters after the
first description cue; then (for single, unsplit and not-described notices) from the title;
then from the notice's opening paragraphs. Types: residential (vivienda, piso, casa, chalet…),
commercial (local, oficina), building (edificio, hotel, residencia, cuartel…), unit in a
building (floor or door marks such as "2º B", "planta primera", "Pta. 2" with no other type),
garage, storage room, industrial/agricultural (nave, almacén, cuadra, granja, silo, "unidad de
almacenamiento"; also any lot described as "nave industrial" or "uso industrial"), land
(solar, parcela, terreno, rústica, crop and pasture words; or only rustic cadastral references,
all with 0000 in characters 15-18), ruin, rural estate with a construction (land words together with a
house, building or farm construction; or a rustic cadastral reference whose characters 15-18
are not 0000), unknown.

### 1.4 Scope (`scope`)

RD 390/2021 applies to «edificios o partes de edificios existentes que se vendan o alquilen a
un nuevo arrendatario» (art. 3.1.b). Art. 2.h defines «edificio» as «construcción techada con
paredes en la que se emplea energía para acondicionar el ambiente interior». Art. 3.2 excludes
(a) protected buildings, only where any improvement would unacceptably alter them; (b)
provisional constructions of two years or less; (c) industrial, defence and agricultural
non-residential buildings or parts of low energy demand; (d) independent buildings under 50 m²;
(e) buildings bought for demolition or major reform. Each lot gets one scope, first rule that
applies:

| rule | scope | basis |
|---|---|---|
| the lot (or the notice's general text) states that it is exempt, excluded, or that the certificate is not required | excluded (declared) | the seller's own statement; its ground is recorded in the review |
| land | excluded | not a building (art. 2.h) |
| ruin | undeterminable | no official guidance; may fall outside art. 2.h |
| stated demolition or ruin declaration | excluded | art. 3.2.e |
| industrial or agricultural | excluded | art. 3.2.c; MITECO FAQ v6.0 nos. 16-17 |
| garage or storage room | excluded | MITECO FAQ v6.0 no. 14 |
| commercial / unit / unknown described as shell ("en bruto", "sin acondicionar") | excluded | MITECO FAQ v6.0 no. 19 |
| undivided share, bare ownership, usufruct, surface right | undeterminable | the sale is of a right in a building, not of a building or part; no guidance |
| protected building (BIC, catalogued, protection level) | undeterminable | art. 3.2.a applies only conditionally |
| unfinished building | undeterminable | no energy use yet |
| rural estate with a construction of unstated use | undeterminable | could be a dwelling or a farm building |
| unknown type, no rating stated | undeterminable | |
| residential or building of under 50 m² described as isolated or independent | excluded | art. 3.2.d |
| everything else | **covered** | art. 3.1.b |

A lot of unknown type whose text states a rating is **covered**: a registered certificate shows
that the seller holds it to be a building in scope. This rule can only add compliant lots.
Lots of `not_described` notices are undeterminable.

### 1.5 Energy statement (`energy_status`)

Windows: every paragraph of the lot that mentions energy (energético/a, eficiencia
energética, kWh, CO2, emisiones), from 60 characters before the first such word to 300
after, joined to the next two paragraphs when they are short (≤ 120 characters) or table rows.
In each window, after blanking door and floor letters ("letra D", "puerta B", "bloque C",
"tipo G", "2º B"…), a **rating** is an isolated capital letter A–G (not the preposition "A"
before a lower-case word, not "D." before a name), or a letter A–G right after a figure that
follows kWh, CO2, año or m². Statuses, in order of precedence:

1. `rating` — a rating letter is stated;
2. `exempt_declared` — exento, excluido del ámbito, no es obligatorio/necesario, no requiere…;
3. `pending` — en trámite, en tramitación, pendiente de…, solicitado;
4. `no_certificate_stated` — no dispone de / carece de / sin certificado o calificación;
5. `certificate_reference` — the certificate or the energy rating is mentioned without a
   letter (for instance "a disposición de los interesados", "consta en el expediente");
6. `none` — no energy statement at all.

The lot's own text decides. When it says nothing (`none`), a statement in the notice's
general text applies to every lot, and the level is recorded as `notice`.

`both_indicators` is set when a rating window names both consumption and emissions or holds two
or more letters (the official minimum for press advertisements is the letter for each of the
two indicators: MITECO FAQ v6.0 no. 42).

### 1.6 Compliance

For covered lots only (n/a otherwise):

- **Primary rule (decided in advance)**: the lot complies when its notice states the energy
  rating (status `rating`, at lot or notice level). A statement that a certificate exists, is
  being obtained, or is available on request, in the tender file or in the specifications
  (`certificate_reference`, `pending`) does **not** comply: art. 15.2 requires that the label
  «se incluirá en toda oferta, promoción y publicidad», and art. 17.3 that whoever publishes
  information on the sale «estará obligada a incluir la información relativa a su calificación
  de eficiencia energética». A letter in the text is accepted as the label: the BOE prints
  text, and the official guidance accepts the letters alone in press advertisements.
- **Lenient rule (sensitivity)**: `certificate_reference` and `pending` also comply.
- **Two indicators (secondary)**: a rating complies only with `both_indicators`.
- **Strict on declared exemptions (sensitivity)**: a declared exemption whose stated ground
  is not an exclusion of art. 3.2, not land, and not an official-guidance exclusion (or states
  no ground) counts as a covered lot that does not comply. The ground is recorded in the review.

### 1.7 Review, lot by lot

The rule-based result is followed by a one-by-one review by the study agent (an AI agent). It
reads the lot's text and the notice's general text and records, for each lot it reviews, the
final scope (with reason), the final energy status, and a reason code for any change. The
reviewed values are final; the agreement between the classifier and the review is reported.
Review sets:

- **R1**: every covered lot that does not comply under the primary rule (all of them);
- **R2**: a random sample of 60 covered lots that comply (seed 14; all of them if fewer);
- **R3**: every undeterminable lot (to resolve it where the text allows);
- **R4**: every excluded lot except land, and a random sample of 60 land lots (seed 14).

Lots of `unsplit` notices are split in the review where the text allows; each resulting lot is
reviewed. Notices that the review finds are not offers by a public body to the public are
removed, with the reason recorded.

### 1.8 Measures

- **Headline**: among the reviewed covered lots of offer notices by public sellers, the number
  and share whose notice does not include the energy rating (primary rule), with a Wilson 95%
  interval, overall and by seller group. The lots are the whole population of the period, not a
  sample; the interval describes the uncertainty of a rate produced by the same process.
- **Notice level**: offer notices with at least one covered lot, and how many of them include
  the rating for all, some or none of their covered lots.
- **Sensitivities**: lenient rule; two indicators; strict on declared exemptions; distinct
  properties (a lot announced again in a later notice counts once, matched by its set of
  cadastral references; lots without a reference count as distinct); excluding the lots of
  sellers outside the State's general administration and its bodies.
- **Diagnostics**: lots by type, scope and reason; energy statements by status and level;
  review changes by reason.

### 1.9 Publication rules

Published per lot: BOE identifier, lot label, date, section, seller group and body, lot type,
scope and reason, energy status and level, letters stated, compliance under each rule, and the
review's codes. Not published: the notice text, addresses, cadastral references, prices, or any
name of a person (notices are signed by officials and some name the deceased whose estate the
State inherited). Citing a notice by its BOE identifier lets anyone read it at boe.es.
<!-- FROZEN-RULES-END -->

## 2. Sources and access

All requests went through `scripts/polite.py` (copied from S11) unless stated: User-Agent
`EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`; at most one request per
second per host, on a clock shared by every process; robots.txt (RFC 9309) read before the first
request to a host and checked for every URL; every request logged. In the log, one pair of
consecutive requests to www.boe.es was 0.96 s apart; all others were at least 1 s apart.

| source | host and path | access | requests | terms |
|---|---|---|---|---|
| BOE daily summaries | `www.boe.es/datosabiertos/api/boe/sumario/AAAAMMDD`, `Accept: application/xml` | documented open-data API | 638 dates of the study period (89 without an issue, HTTP 404) and 184 of the development period | AEBOE conditions of reuse, licencia tipo of 27 June 2024 |
| BOE notices | `www.boe.es/diario_boe/txt.php?id=BOE-B-…` (the notice's HTML rendering) | allowed by robots.txt; the per-document exclusions in robots.txt were checked for every id, and none of our candidates was excluded | 361 (study, 361 distinct) and 132 (development, 116 distinct; 16 repeats after a timeout) | same |
| BOE consolidated law | `www.boe.es/datosabiertos/api/legislacion-consolidada/id/<id>/…` | documented open-data API | RD 390/2021 and the norms in [the paper](https://easybyte.es/lab/studies/s14/paper/) §2 | same; consolidated texts are informative, not official |
| EU law | `publications.europa.eu` (Cellar) | content negotiation | 9 | EU reuse policy |
| Official guidance, consumer campaigns, audit reports | `www.miteco.gob.es`, `www.dsca.gob.es`, `www.tcu.es` and others | `polite.py` | listed in `work/legal/` and `work/prior/` | each site's terms; quoted, not redistributed |
| INVIED's sale pages | `www.defensa.gob.es/invied/02-ventas-inmuebles/subastas-en-curso/` (the address the INVIED notices themselves give); robots.txt disallows only `/_config_/` and `/zOtros/` | `polite.py`, 4 October 2026 | 18 (index pages and the 12 premises pages of the current auction) | site terms; quoted, not redistributed |
| Scholarly search | `api.crossref.org`, `api.openalex.org` | public APIs | 32 requests (31 logged searches) and 33 requests (29 searches and 3 look-ups) | — |
| arXiv | `export.arxiv.org/api/query` | 12 queries on 2026-10-04, ≥ 3.5 s apart, our User-Agent. `export.arxiv.org/robots.txt` is `Disallow: /` for all agents. The API Terms of Use (https://info.arxiv.org/help/api/tou.html, read 2026-10-04, copy in `data/raw/terms/`) say: «When using the legacy APIs (including OAI-PMH, RSS, and the arXiv API), make no more than one request every three seconds, and limit requests to a single connection at a time». Under the lab's legal-minimum rule (documented APIs used within their terms) the queries were sent. The prior-work agent's earlier 29 arXiv queries were refused by `polite.py` and never sent | 12 | arXiv API Terms of Use |
| Press and grey literature | `www.bing.com/news/search?…&format=rss` (allowed by robots.txt), `html.duckduckgo.com` (answered HTTP 202, a challenge page: an access control, not bypassed), `api.gdeltproject.org` (HTTP 429 on 4 of 5 queries), site searches of civio.es, eldiario.es and newtral.es; then the relevant articles and the Observatorio del Alquiler's report pages, where robots.txt allows | `polite.py`, 4 October 2026 | 25 Bing News, 12 DuckDuckGo, 5 GDELT, 5 site searches; about 15 articles | each site's terms; quoted, not redistributed |
| Web discovery (first round) | Claude Code WebSearch tool | used only to find URLs, never quoted; 30 run, 2 not run (budget exhausted) | 32 | — |
| GitHub | `gh search repos`, `gh search code` (GitHub CLI, its own User-Agent, authenticated) | ≥ 7 s between code searches | 28 | GitHub terms |

Not used:

- `www.boe.es/diario_boe/xml.php` (the notice in XML), which the summary API links to: robots.txt
  disallows it for all agents («# Descartar xml»). The HTML rendering carries the same notice.
- `subastas.boe.es` (the Portal de Subastas): robots.txt `Disallow: /`.
- `invied.es` and `energia.gob.es`: robots.txt unreachable, which our fetcher treats as a full
  disallow. INVIED's live sale pages are under `www.defensa.gob.es/invied/`, which was used.
- GIESE's specifications (`oagiese.ses.mir.es`): robots.txt redirects to a page that answers 403.

**Personal data.** Some notices name private persons (officials who sign, deceased persons whose
estate the State inherited, boundary neighbours, the interested buyer in a direct sale). The
notices were processed locally, only to classify lots; the raw files and review excerpts stay in
the git-ignored `data/raw/`, `work/` and `private/`, and no name, address, cadastral reference or
text is published (Regulation (EU) 2016/679, as the BOE's reuse conditions require).

## 3. Counts

| step | n |
|---|---|
| BOE summaries with section V, study period | 538 |
| section-V items read | 59,211 |
| candidate notices (title filter) | 361 (352 in V-B, 9 in V-A) |
| notice kinds (classifier) | offer 313, other 16, direct sale to a named party 11, annulment or suspension 8, not real estate 8, correction 4, result 1 |
| offer notices removed in the review: not an offer of property to the public | 59: 36 direct adjudications to a party who showed interest (art. 137.4 LPAP, all in Valencia and Castellón) and 4 expropriation notices that the classifier had missed (§9 D4); 19 others found in the first review (harvest, timber and grazing rights; withdrawals; numbered conditions; direct sales; expropriations) |
| offer notices in the results | 254 |
| lots of offer notices (classifier, after deviation D1) | 2,626 (2,431 with the frozen parser) |
| lots in the results (after drops and splits) | 2,833: covered 306, excluded 2,487 (land 2,386; garages and storage rooms 75; declared exempt 15; industrial, agricultural or defence of low demand 11), undeterminable 40 |

## 4. Review procedure, as run

The review was done by the study agent, an AI agent, in two passes. It should be read as what
it was, not as a careful reading of every lot.

**First pass (14:54–15:08 local time, 4 October 2026).** The agent printed each lot of the
review sets with the classifier's values, an excerpt of 230–700 characters, the energy windows
of the lot and of the notice's general text, and the notice title, and read the full text of a
lot only when the excerpt did not settle it. It recorded verdicts through
`scripts/review_record.py` in nine batches written over about seven minutes (about 490 verdicts),
plus a correction at 15:08. Confirmations used standard notes: all 60 R2 notes are «rating
letter(s) stated in the lot; confirmed», and 55 of the 114 R4 notes are «land (rustic or unbuilt
plot); confirmed». Sizes: R1 185, R2 60, R3 137, R4 114 (496 lots); with 3 extra rows from split
records and 2 verdicts outside the sets, 501 rows.

**Independent check.** An independent AI agent re-read 40 lots from the live BOE (a stratified
random sample: 20 covered without the rating, 10 covered with it, 10 excluded or undeterminable)
and every INVIED and GIESE notice in full. It agreed with 40 of 40 outcomes. Its report also
found the gaps that the second pass addresses.

**Second pass (after the independent review, 15:42–15:46).**

- The 40 notices that the frozen rules exclude but the classifier kept (36 direct adjudications,
  4 expropriations) were dropped by rule, one verdict per lot (D4).
- The 10 multi-property (`unsplit`) records not yet reviewed were read in full. 8 TGSS records are
  one premises made of several registered properties; 2 Hacienda records in Huelva were split
  into 9 and 7 lots.
- Four Cuenca notices that list rustic plots in a table were read as one lot each; they were
  split into 278 rows, one per plot (67, 78, 75 and 58).
- A targeted search of the unreviewed land lots for words that indicate a building («construida»,
  «edificado», «vivienda», «nave», «ruinoso», «alturas»…, boundary descriptions excluded) found
  31 lots. 26 were false hits (office addresses in the conditions, place names). The other 5 were
  reclassified: 4 undeterminable (D6), 1 agricultural shed kept excluded.
- Industrial and defence lots were re-checked against the «de baja demanda energética» condition
  of art. 3.2.c (D7).
- The nine declared exemptions under art. 3.2.e were recorded with their ground (D8).

The R2 sample (60 of 147 covered lots with a rating) and the R4 land sample (60 lots) changed no
outcome. A random sample of land lots cannot find the few built lots typed as land; the targeted
search above is the check for that, and its rule is the grep described, not a reading of all
2,386 land lots.

## 9. Deviations from the frozen rules

1. **D1, parser (2026-10-04, after the freeze, before the review).** A check of the study
   period's notices for lots split wrongly (more cadastral references than lots, or first lot
   label other than 1) found two parser faults. The check looked at the split, not at any
   compliance result.
   - (a) A land-registry number such as «Finca número 6, al tomo …» or «Finca número 19.732, …»
     was read as a lot header. «Finca/Inmueble/Bien/Propiedad nº N» is now a header only when
     followed by «.», «:» or a dash and not by a digit. This affected 4 INVIED notices and 1 TGSS
     notice.
   - (b) Numbered rows written with a semicolon («1; 10/01/2025; Rústica …») were not
     recognised. This affected 2 Hacienda notices of 60 and 66 rustic lots.

   D1 corrects lot extraction only: no type, scope, energy or compliance rule changed
   (`classify.py` is byte-identical to the frozen copy). Its effect falls almost entirely on one
   seller:
   - In the classifier's output, before the review, covered lots without the rating rose from
     126 to 185: INVIED +59 (38 → 97), Hacienda +1, TGSS −1.
   - After the review, with the frozen parser's lots, the headline would be **92 of 255 (36.1%,
     95% CI 30.4–42.1%)** instead of 144 of 306. INVIED would have 34 covered lots, all without
     the rating, instead of 86; D1 adds 52 lots without the rating, all INVIED.
   - The frozen parser is published as `scripts/lots_frozen.py` (byte-identical to the frozen
     copy), and `data/d1_comparison.csv` and `data/d1_frozen_lots.csv` give the computation.
     Each frozen-parser lot of a notice that D1 re-split takes the reviewed outcome of the lots
     it contains: covered if any is covered, without the rating if any covered lot lacks it.
   - Under the frozen review rule («a record holding several properties became one row per
     property») the review might have split those records anyway, so the frozen-method figure is
     a bound, not a certainty.
2. **D2, review field.** `exempt_ground` records the ground of a declared exemption as the
   notice states it or, when it states none, as the lot's description makes evident (an
   industrial building → 3.2.c; a garage → the FAQ); `none_stated` when neither. Values `ruin`
   and `3.2.e_part` were added.
3. **D3, analysis.** For the distinct-property sensitivity, a lot without a cadastral reference
   is keyed by the normalised opening of its description (the frozen text named only cadastral
   references). The sensitivity is approximate.
4. **D4, notices the rules exclude.** The frozen rule §1.1 removes direct sales to a named party
   and notices that are not sales. The classifier kept 36 notices of the Delegación de Economía y
   Hacienda in Valencia and Castellón that open a direct adjudication «a que se refiere el
   artículo 137.4» of Ley 33/2003, prompted by the interest of a named person, and 4 expropriation
   notices. All 40 lots were excluded land; none was covered. They were dropped in the second
   pass, with the reason in each verdict; two notices of the same kind (BOE-B-2026-14342 and
   BOE-B-2026-18464) had already been dropped in the first.
5. **D5, `unsplit` records.** Frozen rule §1.7 says these records are split in the review. The
   first pass split them only where they fell in a review set; the second pass reviewed the
   remaining 10 (§4).
6. **D6, built lots typed as land.** Found by the targeted search (§4):
   - a two-storey 60 m² building in Grañén with no stated use;
   - a former military works depot in Murcia (1,252 m² built);
   - the Garrucha lighthouse plot (349 m² built);
   - a ruinous house in Sóller.

   All four are now undeterminable: the frozen rule makes a building of unstated use, or a
   ruin, undeterminable. None states a rating.
7. **D7, art. 3.2.c.** The frozen rule excluded any industrial or agricultural lot. Art. 3.2.c
   excludes only the parts «de baja demanda energética», and FAQ no. 17 requires offices of
   50 m² or more in industrial buildings to be certified.
   - Three TGSS lots of one industrial unit (ground floor and mezzanine, re-auctioned three
     times) state a registered rating. Consistently with §1.4 (a stated rating shows the seller
     holds the lot in scope), they are now covered, with the rating.
   - A FOGASA industrial complex with a 204 m² front pavilion of unstated use is now
     undeterminable.
   - A FOGASA «nave» valued as unbuilt land is now land.
   - Workshops, warehouses, silos, ammunition depots and agricultural sheds stay excluded.
8. **D8, art. 3.2.e.** The headline accepts every exemption a seller declares under art. 3.2.e,
   including the 7 for a flat, premises or part of a house. Art. 3.2.e gives the declaration to
   «el propietario del edificio o de parte del edificio, según corresponda», and the public
   seller is the owner. The non-binding MITECO FAQ no. 7 reads the exclusion as whole buildings
   only. That reading is the sensitivity `faq_3_2_e`: the 7 lots count as covered without the
   rating (151 of 313).
9. **D9, rules reported.** Besides the frozen primary rule (one letter suffices), the paper
   reports the stricter rule `two_letters`: both letters, for consumption and emissions. That
   is the press-advertisement minimum of the recognised document to which art. 17.3 refers.
   `strict_exempt` now also counts declared exemptions on the `ruin` and `3.2.e_part` grounds.
   The per-lot columns are named `rating_stated_<rule>`: they say whether the notice states the
   rating, not whether a law was breached.
10. **Known classifier faults, corrected in the review and not by changing the rules.**
    - Ratings written «– letra D» were blanked as door letters (TGSS Navarra notices: 8 lots).
    - «eximido» and «No cuenta con certificado» were not recognised.
    - The type fallback took «Vivienda» from the INVIED's own name, and construction words
      from place names («Casas de Don Gómez», «La Granja», «Pajares»).
    - Sales of harvest, timber or grazing rights whose title names a «finca», expropriation
      notices, direct adjudications and one withdrawal notice were classified as offers.

    `data/classifier_vs_review.csv` gives the counts.
11. The «state bodies only» sensitivity equals the headline, because no covered lot came from a
    body outside the State's general administration and its agencies.
