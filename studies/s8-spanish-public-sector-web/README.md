# S8 — What can a machine verify on Spain's public-sector websites?

*EasyxLab · study S8 · data collected 2026-10-02 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s8/paper/](https://easybyte.es/lab/studies/s8/paper/) · [PDF](https://easybyte.es/lab/studies/s8/paper.pdf)

## Abstract

Some obligations and good practices for public websites leave a trace a program can check
without judgement: a `security.txt` file (RFC 9116), an accessibility statement linked from
the site and "actualizada periódicamente, como mínimo una vez al año" (Royal Decree
1112/2018, art. 15.1), HTTPS with HSTS, and a stated policy towards AI crawlers. We checked
them on the websites of 6,648 of Spain's 8,132 municipalities (81.8% of municipalities, 98.9%
of the population) and on the 19 regional governments, 52 provincial and island councils,
50 public universities and 22 ministries. Of 6,272 entities whose home page we could measure,
5,245 (83.6%) returned their own home page (another 458 of the 6,730 in scope were not
measurable because of their `robots.txt`); 179 municipal URLs led to something that is not
the council's site (expired or re-registered domains now used by others, parked domains,
hosting panels). Of the 5,245, 5,130 (97.8%)
served the home page over HTTPS when asked, but **1,688 of those 5,130 (32.9%) send HSTS**.
**Of 5,570 entities whose server answered for `/.well-known/security.txt`, 12 serve a file, 8
have its required fields and 4 are strictly valid under RFC 9116**, while 329 (5.9%) answer
that path with HTTP 200 and something else. **2,492 of 5,245 home pages (47.5%)** carry a link
to the accessibility statement that our detector can see; of 1,247 statements read with an
audited date extractor, 908 (72.8%) show a preparation or review date and **160 (12.8%) show
one from the last 365 days**. Spain's official monitoring already checks, by experts on a sample of
about 63 websites a year, whether a statement is provided and what it says; it does not report
whether home pages link to it or how old its date is, which is what this census adds. The six most frequent dates each occur in a single province and
cover 479 of the 908 dated statements (52.8%), which points to statements produced in bulk for
many municipalities at once; we did not identify by whom. 326 of 6,012 entities (5.4%) block at
least one of GPTBot, ClaudeBot, Google-Extended or CCBot, concentrated in a few regions; a
spec-like `llms.txt` appears on 7 of 1,020 sites in a random subsample (0.7%). There is no
official national list of municipal websites; the URLs come from Wikidata and one regional
directory, and small municipalities are under-covered (3,612 of 4,980 under 1,000 inhabitants,
72.5%, have a known URL). A first version of our scanner fetched the home page of 123 entities,
and `security.txt`, `llms.txt` or the statement of another 722, although their `robots.txt`
did not allow it; those records were deleted, not used, and the 123 are reported as not
measurable. We publish the per-entity table, the cleaned scan records, the scanner and
the method, and propose a free tool, `gov-web-lint`, that any administration could run on its
own site.

## Contents

| file | |
|---|---|
| [paper](https://easybyte.es/lab/studies/s8/paper/) (web) | the full report |
| `METHOD.md` | sources, fetch budget, every check and denominator, what went wrong, privacy |
| `run.sh` | rebuilds `data/` from the scan records and checks the figures; `--new-measurement` scans again |
| `scripts/fetch_sources.sh` | downloads REL, INE, Wikidata and the Castilla-La Mancha directory |
| `scripts/build_population.py` | entity list (REL, de-duplicated and checked against INE) and the URL to test for each |
| `scripts/scan.py` | the scanner, version 2 (Python ≥ 3.10, stdlib only) |
| `scripts/robots9309.py` | `robots.txt` parser and matcher following RFC 9309 |
| `scripts/audit_robots.py`, `scripts/recheck.py` | the robots.txt audit and the same-evening re-checks of 2026-10-02 |
| `scripts/build_records.py` | builds `data/records.jsonl.gz` from the raw records |
| `scripts/aggregate.py` | builds every table in `data/` |
| `scripts/draw_audit_sample.py` | drew the date-audit sample (run once) |
| `scripts/check_numbers.py` | asserts the figures in this README and [the paper](https://easybyte.es/lab/studies/s8/paper/) against `data/summary.json` |
| `data/records.jsonl.gz` | cleaned per-entity scan records: the input of `aggregate.py` |
| `data/population.csv` | the 8,275 entities and the URL tested for each, with its source |
| `data/entities.csv` | one row per entity (8,275), all indicators, public URLs only |
| `data/exclusions.csv` | every URL judged not to be the entity's own site, with the rule |
| `data/summary_by_type.csv`, `summary_by_region.csv`, `summary_by_size.csv` | counts, denominators, % (blank when the denominator is under 10) |
| `data/coverage.csv` | municipal URL coverage by region and size |
| `data/summary.json` | headline numbers with 95% Wilson intervals |
| `data/build_meta.json` | counts of the `robots.txt` re-read and the re-checks (from the raw files) |
| `data/date_audit_v2.csv` | audit of the statement-date extractor, with a verdict per case (not regenerated) |
| `data/other_entities.csv`, `data/url_overrides.csv` | curated inputs |
| `pilot/` | 25-municipality pilot that preceded the study |
| `data/raw/`, `private/` | git-ignored: downloads, raw scan records, logs. Never published. |

## Headline table

Each cell is a percentage of the denominator given below it in `data/summary_by_type.csv`.

| | municipalities | prov. councils | universities | regional gov. | ministries |
|---|---|---|---|---|---|
| home page reachable (of entities in scope) | 77.7% of 6,588 | 84.6% of 52 | 92.0% of 50 | 88.9% of 18 | 81.8% of 22 |
| served over HTTPS (of reachable) | 97.8% of 5,121 | 100% of 44 | 100% of 46 | 100% of 16 | 100% of 18 |
| HSTS (of served over HTTPS) | 32.3% of 5,006 | 56.8% of 44 | 54.3% of 46 | 43.8% of 16 | 77.8% of 18 |
| security.txt with the required fields (entities) | 7 | 1 | 0 | 0 | 0 |
| security.txt strictly valid (entities) | 4 | 0 | 0 | 0 | 0 |
| link to accessibility statement (of reachable) | 46.6% of 5,121 | 84.1% of 44 | 82.6% of 46 | 81.2% of 16 | 88.9% of 18 |
| blocks ≥ 1 of 4 AI crawlers (of robots.txt read) | 5.2% of 5,874 | 18.8% of 48 | 18.0% of 50 | 11.1% of 18 | 4.5% of 22 |

Statement dates by type are not in this table: for the non-municipal entities and the largest
municipalities they were read only by the first, unaudited version of the date extractor and
are left out ([the paper](https://easybyte.es/lab/studies/s8/paper/) §6.4).

## Reading `data/entities.csv`

- One row describes what one client saw on 2026-10-02: the scan ran 19:08–19:20 UTC, the
  re-checks 21:45–22:06 UTC, from one Spanish residential IP. Sites change; a row is not a
  verdict on a body.
- `reachable = 0` covers very different things, told apart by `home_outcome`: a dead domain,
  a server error, a refusal of our client (some refusals depend on the User-Agent: the reviewer
  saw two ministries answer 200 to a browser-like User-Agent and 403 to the study's), a
  `robots.txt` that does not allow us (`robots_disallow`), a URL that is not the entity's site
  (`not_entity_site`, rule in `data/exclusions.csv`).
- `acc_link = 0` means no link our detector can see in the static HTML; a link added by
  JavaScript is not seen.
- `stmt_*` fields describe the page the home page links to; `stmt_dates_statements = 1` marks
  the statements that enter the date figures.

## Automation and review

The study was run by AI agents: source search, code, scan, re-checks, analysis and writing. An
independent AI reviewer then checked it adversarially — recomputing the figures, re-fetching a
sample of sites and checking every quotation — and its findings were addressed in this version
([the paper](https://easybyte.es/lab/studies/s8/paper/) §11), and `scripts/check_numbers.py` re-checks every quoted figure against the data. No
administration was contacted.

## Licence

Code (`scripts/`, `pilot/*.py`, `run.sh`): Apache-2.0, see [`../../LICENSE`](../../LICENSE).
Data and text: CC BY 4.0, see [`../../LICENSE-DATA`](../../LICENSE-DATA). The data derive from:
Wikidata (CC0); the Registro de Entidades Locales (Ministerio de Política Territorial); INE's
list of municipality codes; and the Junta de Comunidades de Castilla-La Mancha's *Directorio de
Entidades Locales*, June 2025 edition, CC BY 4.0 — "Fuente de datos: Junta de Comunidades de
Castilla-La Mancha"; we used only its municipality, province, EATIM and website columns, joined
to INE codes. Neither source endorses this study.

Cite as: EasyxLab (2026). What can a machine verify on Spain's public-sector websites? Study
S8. EasyByte Hub S. Coop. Mad. https://github.com/easybytehub/easyxlab

---

EasyxLab · a research lab by [EasyByte](https://easybyte.es)
