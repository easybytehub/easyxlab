# S11 — Do the registration numbers on Airbnb listings exist in the official registries? Spain and New York around 20 May 2026
*EasyxLab · study S11 · snapshots of 16–31 March and 14–30 June 2026 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s11/paper/](https://easybyte.es/lab/studies/s11/paper/) · [PDF](https://easybyte.es/lab/studies/s11/paper.pdf)

## Abstract

Since 20 May 2026, Regulation (EU) 2024/1028 requires every short-term rental listed on a
platform in an area with a registration procedure to show its registration number. In May
and June 2026 Spain's Supreme Court annulled the national registration number, so in Spain
the number that can still be checked is the regional tourist-registry number. We parsed the
licence field of 227,224 Airbnb listings in Inside Airbnb snapshots (CC BY 4.0) taken just
before and just after 20 May, in Barcelona, Girona, València, Málaga, Sevilla, Madrid and
New York City. We then matched every well-formed number against the open registries of
Catalonia, the Comunitat Valenciana and Andalucía and against New York's Local Law 18
registry file of 25 June 2025, a year older than the listings.

**In June 2026, in the five Spanish areas with an open registry, 2,066 of 31,222 active
listings that showed a well-formed tourist-dwelling number (6.6%, 95% CI 6.3–6.9%) showed
one that we could not trace to any registered dwelling.** A further 557 (1.8%, CI 1.6–1.9%)
showed a registered dwelling of their municipality written in a recognisable wrong form:
- leading zeros dropped and the Catalan control digit appended;
- the Barcelona province code where the Girona one is registered;
- an extra digit (Málaga).

About 45 of those 557 would match these patterns by chance. Another 538 (1.7%) showed a
number registered in a different municipality. Barcelona had the highest residual share:
642 of 6,080 (10.6%, CI 9.8–11.4%), plus 168 (2.8%) in a wrong form. 388 of the 642 are
listings for a private room, while Catalan law requires tourist dwellings to be let whole.
This is an observation about listing type and licence type, not about any host: the room type
is the host's own description, and a room may be let under another kind of licence. The wrong-form category was defined after an independent review, when the rules
had already been frozen. Under the frozen rules the not-found figures were 2,623 of 31,222
(8.4%) and, in Barcelona, 810 of 6,080 (13.3%). The rates were similar across 20 May
(March: 1,736 of 27,230, 6.4%; 2,211, 8.1%, under the frozen rules).

What changed was the labelling. Across the six Spanish areas, the active listings whose only
number was the national tourist number, the one the Supreme Court annulled, fell from 1,897 of
52,938 (3.6%) in March to 840 of 59,395 (1.4%) in June. "Exempt" statements in the regional
field rose from 797 (1.5%) to 9,848 (16.6%), almost all of them "Exempt - seasonal rental".
In Madrid the registry cannot be downloaded. There, 6,634 of 15,782 active listings (42.0%)
show a national number of the "non-tourist" category and no regional number; 4,916 of them
(74.1%) accept stays of 1–4 nights. In New York, 1,776 of 4,184 active short-stay listings
(42.4%) show "Exempt". Of the listings that New York's registry file links to a registration,
1,866 of 1,871 show that same number.

A number missing from a registry is not proof that a listing is illegal. The entry may have
been cancelled between the scrape and our copy of the registry; the number may be a
registered one written in a form we do not recognise, or a typo; the series may be exempt;
or Inside Airbnb may place a Girona-area listing in the wrong municipality. We publish
aggregates only.

## Headline table (June 2026, active listings showing a well-formed tourist-dwelling number)

| area | registry | shown | in registry, same municipality | other municipality | registered, wrong form | not found (95% CI) |
|---|---|---|---|---|---|---|
| Barcelona | RTC (Catalonia) | 6,080 | 5,217 (85.8%) | 53 (0.9%) | 168 (2.8%) | 642 (10.6%, 9.8–11.4) |
| Girona area | RTC (Catalonia) | 11,597 | 10,564 (91.1%) | 313 (2.7%) | 184 (1.6%) | 536 (4.6%, 4.3–5.0) |
| València | GVA | 3,117 | 2,762 (88.6%) | 61 (2.0%) | 0 (0.0%) | 294 (9.4%, 8.5–10.5) |
| Málaga | OpenRTA | 5,651 | 5,103 (90.3%) | 104 (1.8%) | 205 (3.6%) | 239 (4.2%, 3.7–4.8) |
| Sevilla | OpenRTA | 4,777 | 4,415 (92.4%) | 7 (0.1%) | 0 (0.0%) | 355 (7.4%, 6.7–8.2) |

Wrong-form rules were applied only where they have power: Catalonia (control digit, province
code) and Málaga (extra digit). Rule by rule, in June:

| rule | matched | expected by chance |
|---|---|---|
| Catalan control digit | 197 | ≈ 7 |
| province code | 155 | ≈ 9 |
| Málaga extra digit | 205 | ≈ 29 |

**How much a "found" proves: the in-range chance match.** Take a random number below the
highest number the registry has issued in the series. In Sevilla it would be registered to a
dwelling in the city 61% of the time, so the test there catches few wrong numbers. In
Barcelona and Málaga that chance is 12–13%, and in València and the Girona area 1–3%. Over
the whole range the format allows, the chances are much lower (Sevilla 9.5%, Barcelona
1.1%). Details are in the paper, §5.4, at https://easybyte.es/lab/studies/s11/paper/.

## Layout

| path | |
|---|---|
| `METHOD.md` | sources and licences, snapshot dates, frozen classification rules, matching per region, denominators, deviations, what was not possible |
| `scripts/strnum.py` | reusable parser and normaliser of licence fields and registration-number formats (ES national; Catalonia, Comunitat Valenciana, Andalucía, Madrid; NYC) |
| `tests/test_strnum.py` | unit tests for the parser (`python3 -m unittest discover -s tests`) |
| `scripts/download_listings.py`, `scripts/snapshots.py` | the 14 Inside Airbnb snapshots used and their download |
| `scripts/fetch_registries.py` | downloads the registries and keeps only number, type, municipality and status; the Spanish files are filtered while streaming, the NYC xlsx (which has street addresses but no names) is written to a temporary file in `work/` and deleted after filtering |
| `scripts/polite.py`, `scripts/robots9309.py` | fetcher: fixed User-Agent, ≤ 1 request/s per host (shared across processes), declared Crawl-delay honoured, robots.txt read (RFC 9309), every request logged |
| `scripts/htmltext.py` | plain text from saved HTML, used to grep legal texts literally |
| `scripts/extract_listings.py` | parses each snapshot into a private row-level extract (`work/`, not published) |
| `scripts/analyse.py` | matching and every published table |
| `scripts/check_headlines.py` | asserts every headline number in this README (and in [the paper](https://easybyte.es/lab/studies/s11/paper/), when present) against `data/` |
| `scripts/run.sh` | `run.sh` (offline: tests, extract, analyse, check), `run.sh fetch`, `run.sh check` |
| `data/categories.csv` | listings by area × snapshot × population (all, active, NYC active short-stay) × category, with n, denominator, % and Wilson 95% CI |
| `data/h1_tourist_numbers.csv`, `data/h1_by_series.csv` | registry match of tourist-dwelling numbers; and of every series with an open registry |
| `data/national_numbers.csv`, `data/exempt_reasons.csv` | national numbers (TU/NT) and "Exempt" statements by field and reason |
| `data/signals.csv` | minimum nights and reviews for non-tourist, exempt and other categories |
| `data/nyc.csv`, `data/duplicates.csv`, `data/transitions.csv` | New York detail; numbers shown on several listings; category changes of listings present in both snapshots |
| `data/diagnostics.json`, `data/summary.json`, `data/sources.json` | in-range chance-match rates, wrong-form rule counts, format checks; headline numbers; snapshot URLs and SHA-256, registry metadata |
| `data/prior_work_search.csv` | every prior-work search run, with query, date and hits (GitHub owners withheld) |
| [paper](https://easybyte.es/lab/studies/s11/paper/) (web) | the paper (not in the public package; read it at https://easybyte.es/lab/studies/s11/paper/) |
| `data/raw/`, `work/`, `private/` | git-ignored: downloads, row-level extracts, logs. Never published. |

## How to run

Python ≥ 3.10; standard library only, plus `openpyxl` for the New York registry file.

```bash
bash scripts/run.sh fetch   # downloads ~116 MB of snapshots and the registries (registries change daily)
bash scripts/run.sh         # tests, extraction, analysis, headline check; offline
```

A new `fetch` reads today's registries, so the counts will move a little.
`data/sources.json` records the SHA-256 of the snapshots and of the registry extracts we
used.

## Licences

- Code (`scripts/`, `tests/`): Apache-2.0, see [`../../LICENSE`](../../LICENSE).
- Our data and text: CC BY 4.0, see [`../../LICENSE-DATA`](../../LICENSE-DATA).
- Third-party data are not redistributed. `data/` holds only counts derived from them.
  - Listings: [Inside Airbnb](https://insideairbnb.com/get-the-data/), "Creative Commons
    Attribution 4.0 International License". Inside Airbnb asks that its data "be attributed
    and cited appropriately": data from Inside Airbnb, snapshots of March and June 2026.
  - Registries:
    - Registre de Turisme de Catalunya (Generalitat de Catalunya, Departament d'Empresa i
      Treball), via analisi.transparenciacatalunya.cat. The dataset metadata says "See Terms
      of Use" and links to a licence page whose robots.txt does not allow our client, so the
      licence is **not verified**. We redistribute only counts.
    - Viviendas turísticas de la Comunitat Valenciana (Generalitat Valenciana), CC BY.
    - OpenRTA, Registro de Turismo de Andalucía (Junta de Andalucía), CC BY 4.0.
    - NYC Office of Special Enforcement short-term rental registration dataset as of 25 June
      2025, read from the Internet Archive's copy.
- None of these sources endorses this study.

Cite as: EasyxLab (2026). Do the registration numbers on Airbnb listings exist in the
official registries? Spain and New York around 20 May 2026. Study S11. EasyByte Hub S. Coop. Mad. https://github.com/easybytehub/easyxlab

---
EasyxLab · a research lab by [EasyByte](https://easybyte.es)
