# S14 — Do public sellers show the energy label when they announce property sales in Spain's Official Gazette? A lot-by-lot audit of BOE notices, January 2025 – September 2026
*EasyxLab · study S14 · BOE notices of 1 January 2025 – 30 September 2026, read on 4 October 2026 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s14/paper/](https://easybyte.es/lab/studies/s14/paper/) · [PDF](https://easybyte.es/lab/studies/s14/paper.pdf)

## Abstract

Spain's Royal Decree 390/2021 requires that the energy-efficiency label «se incluirá en toda
oferta, promoción y publicidad dirigida a la venta o arrendamiento del edificio o de parte del
mismo» (art. 15.2). Anyone who publishes information on a sale «estará obligada a incluir la
información relativa a su calificación de eficiencia energética» (art. 17.3). The General State
Administration must publish the call for the sale of its property in the Boletín Oficial del
Estado (BOE) (Ley 33/2003, art. 138.3); other public sellers also announce sales there.

We read every candidate property-sale notice the BOE published between 1 January 2025 and
30 September 2026: 361 candidate notices from its open-data summaries. We kept the 254 sale notices that
offer property to the public and split them into 2,833 lots. Each lot was classified against the
Royal Decree's scope (art. 3, the exclusions of art. 3.2, art. 2.h, and the ministry's FAQ). An AI
agent reviewed the lots without the label, the uncertain lots and the excluded lots other than
land, plus random samples, and an independent AI agent re-read 40 of them (40 of 40 agreed).

**144 of 306 covered lots announced in the BOE in the period (47.1%, 95% CI 41.5–52.7%) did not
include the energy rating.** With the lot parser as frozen, before a fix to how lots were split,
the figure is 92 of 255 (36.1%). The fix added 52 lots without the rating, all of them INVIED
premises that the frozen parser had merged. The other 2,527 lots were land, garages, low-demand
industrial buildings, lots the seller declared exempt, or lots whose scope the notice does not let
us determine.

By seller (notice content only; see the caveat below):

- Tesorería General de la Seguridad Social (TGSS): 14 of 160 (8.8%). TGSS states the rating in
  all covered lots of 89 of its 96 notices with covered lots.
- Delegaciones de Economía y Hacienda (Patrimonio del Estado): 17 of 33 (51.5%), with the rating
  in all covered lots of 12 of its 24 notices.
- INVIED (Ministry of Defence): 86 of 86 (100.0%), mostly commercial premises. INVIED's own website
  lists the certificate of its premises on sale as «En tramitación».
- GIESE (Ministry of the Interior), former Guardia Civil and police buildings: 21 of 21 (100.0%).
- FOGASA: 5 of 5. One port authority: 1 of 1.

At notice level, 135 notices with at least one covered lot were published; 33 of them include
the rating for none of their covered lots.

**Caveat.** Whether a BOE notice is «oferta, promoción y publicidad» has not been settled by any
authority. These figures describe what the notices say, not a legal finding about any body. The
paper sets out both readings: for coverage, the words «toda oferta» and «publique … información
sobre la venta», and the patrimony law's own reference to «otros medios de publicidad»; against,
the notice's nature as a mandatory publication of an administrative act.

Other points:

- **Exemptions.** Land, garages, storage rooms, shell premises and low-demand industrial
  buildings are outside the Royal Decree's scope and are not counted. So are 23 lots that the
  seller declared exempt. 9 of them invoke the demolition-or-reform exclusion (art. 3.2.e), 7 of
  them for a flat or part of a building. The regulation gives that declaration to «el propietario
  del edificio o de parte del edificio», so we accept it. The ministry's non-binding FAQ reads it
  as whole buildings only.
- **How the rules were made.** The classification rules were written on 2024 notices and frozen
  before this study read the study period. A pilot by the lab had already read the same period the
  day before, so the freeze was not blind, and its evidence is local.

The result under other rules:

- requiring both letters, for consumption and emissions (the press-ad minimum of the recognised
  document to which art. 17.3 refers): 149 of 306;
- counting a statement that a certificate exists, or is being obtained, as stating the rating:
  143 of 306;
- the FAQ's reading of art. 3.2.e: 151 of 313;
- also counting declared exemptions with no valid ground: 157 of 319;
- counting a property announced several times once: 123 of 250.

## Headline table (covered lots, primary rule)

Notice content, not compliance: whether a BOE notice is «oferta, promoción y publicidad»
(art. 15.2) is unsettled.

| seller | covered lots | without the rating | % | 95% CI |
|---|---|---|---|---|
| all public sellers | 306 | 144 | 47.1 | 41.5–52.7 |
| TGSS | 160 | 14 | 8.8 | 5.3–14.2 |
| Patrimonio del Estado (Delegaciones de Economía y Hacienda) | 33 | 17 | 51.5 | 35.2–67.5 |
| INVIED (Defence) | 86 | 86 | 100.0 | 95.7–100.0 |
| GIESE (Interior) | 21 | 21 | 100.0 | 84.5–100.0 |
| FOGASA | 5 | 5 | — | — |
| port authorities | 1 | 1 | — | — |
| all, frozen lot parser (before the fix) | 255 | 92 | 36.1 | 30.4–42.1 |

The lots are the whole population of sale notices in the period, not a sample. The interval
describes the uncertainty of a rate produced by the same process. Lots announced more than once
(re-auctions) count once per notice; the distinct-property figure is above.

## Layout

| path | |
|---|---|
| `METHOD.md` | how the rules were made (not blind), frozen classification rules (§1), sources and access (§2), counts (§3), the review as run (§4), deviations from the frozen rules (§9) |
| `scripts/select_notices.py` | candidate notices from the BOE daily summaries (sections V-A, V-B, V-C) |
| `scripts/lots.py`, `scripts/lots_frozen.py` | notice parser and lot splitter (lot headers, numbered items, table rows, single lots); `lots_frozen.py` is the parser as frozen, before deviation D1 |
| `scripts/classify.py` | notice kind, seller, lot type, scope under RD 390/2021, energy statement |
| `scripts/build_lots.py` | applies the parser and classifier; writes the row-level table to `work/` (not published) |
| `scripts/review_queue.py`, `scripts/review_record.py` | review sets R1–R4 and the recorder of the review verdicts |
| `scripts/analyse.py` | merges classifier and review; applies the rules; writes every table in `data/` |
| `scripts/check_headlines.py` | asserts the headline numbers in this README (and in [the paper](https://easybyte.es/lab/studies/s14/paper/), when present) against `data/` |
| `scripts/fetch_sumarios.py`, `scripts/fetch_notices.py`, `scripts/polite.py`, `scripts/robots9309.py`, `scripts/htmltext.py` | downloads: fixed User-Agent, at most one request per second per host, robots.txt read before every request, every request logged |
| `scripts/run.sh` | `run.sh` (offline: tests, lots with both parsers, review queue, analysis, check), `run.sh fetch`, `run.sh check` |
| `tests/` | unit tests of the parser and the classifier (`python3 -m unittest discover -s tests`) |
| `data/lots.csv` | one row per lot: BOE identifier, lot, date, seller, type, scope and reason, energy statement, letters, `rating_stated_<rule>` for each rule, classifier and review values |
| `data/notices.csv` | one row per candidate notice: kind, seller, split method, lots, covered lots with the rating |
| `data/review_verdicts.csv`, `data/review.csv`, `data/review_agreement.csv`, `data/classifier_vs_review.csv` | the review and its agreement with the classifier |
| `data/by_seller.csv`, `data/by_body.csv`, `data/by_seller_distinct.csv`, `data/notice_label_by_seller.csv` | results by seller group, selling body and notice |
| `data/sensitivity.csv`, `data/d1_comparison.csv`, `data/d1_frozen_lots.csv` | other rules, and the headline with the frozen parser |
| `data/declared_exemptions.csv`, `data/without_label_statements.csv`, `data/scope_reasons.csv`, `data/energy_status.csv`, `data/lots_by_type.csv` | diagnostics |
| `data/summary.json` | headline numbers |
| `data/prior_work_search.csv` | every prior-work and press search run, with query, date and hits (GitHub owners withheld) |
| [paper](https://easybyte.es/lab/studies/s14/paper/) (web) | the paper (not in the public package; read it at https://easybyte.es/lab/studies/s14/paper/) |
| `data/raw/`, `work/`, `private/` | git-ignored: downloads, row-level extracts, review excerpts, logs, frozen copies. Never published. |

**Data dictionary note.** The columns `rating_stated_<rule>` (`yes`, `no`, `n/a`) say whether the
notice states the energy rating for a covered lot under each rule:

- `primary`: one letter suffices;
- `two_letters`: consumption and emissions;
- `lenient`: a certificate reference or «en trámite» counts;
- `faq_3_2_e` and `strict_exempt`: declared exemptions read more strictly.

They describe notice content. They are not findings of non-compliance, because whether a BOE
notice is «oferta, promoción y publicidad» is unsettled.

## How to run

Python ≥ 3.10, standard library only.

```bash
bash scripts/run.sh fetch   # ~640 summary requests and 361 notice requests to www.boe.es, at most 1 per second
bash scripts/run.sh         # tests, lot tables, review queue, analysis, headline check; offline
```

The review verdicts in `data/review_verdicts.csv` are an input: the study agent (an AI agent)
wrote them, and they are not regenerated. `analyse.py` stops if a verdict does not match a lot. A
new `fetch` reads the same notices, which the BOE does not change after publication.

## Licences

- Code (`scripts/`, `tests/`): Apache-2.0, see [`../../LICENSE`](../../LICENSE).
- Our data and text: CC BY 4.0, see [`../../LICENSE-DATA`](../../LICENSE-DATA).
- BOE content: basado en datos de la Agencia Estatal Boletín Oficial del Estado
  ([www.boe.es](https://www.boe.es)), reused under its conditions of reuse (licencia tipo of
  27 June 2024).
  - We do not redistribute the notices' text. `data/` holds our classification of each lot, a
    derived work identified as such. Each row gives the notice's BOE identifier and date, so
    anyone can read the original at boe.es.
  - Legal texts were read from the BOE's consolidated-legislation API. Those texts are
    consolidated texts of a merely informative character, not the official texts.
- None of the sources, including the Agencia Estatal Boletín Oficial del Estado, takes part in,
  sponsors or endorses this study.

Cite as: EasyxLab (2026). Do public sellers show the energy label when they announce property
sales in Spain's Official Gazette? A lot-by-lot audit of BOE notices, January 2025 – September
2026. Study S14. EasyByte Hub S. Coop. Mad. https://github.com/easybytehub/easyxlab

---
EasyxLab · a research lab by [EasyByte](https://easybyte.es)
