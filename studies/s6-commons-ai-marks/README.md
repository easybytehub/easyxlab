# S6 — Do AI-generated images on Wikimedia Commons carry provenance marks?

*EasyxLab · study S6 · data collected 2026-10-02 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s6/paper/](https://easybyte.es/lab/studies/s6/paper/) · [PDF](https://easybyte.es/lab/studies/s6/paper.pdf)

## Abstract

Wikimedia Commons stores uploaded files byte for byte. It therefore shows which AI provenance marks reach a public archive when the host does not strip them. We enumerated every file Commons labels as AI-generated: the `Category:AI-generated images` tree (530 categories) and `{{PD-algorithm}}`, 8,971 files in total. We then inspected 2,084 originals from a month-stratified sample with ai-mark-lint, downloading, checking and deleting each one.

Two populations are reported. The *main* population is the category tree plus `{{PD-algorithm}}` files with AI evidence in their categories (1,585 measured files); some of these images are AI-modified rather than AI-generated. The *union* adds the other `{{PD-algorithm}}` files (2,084 measured).

**Marks in the main population.** The share of files with a machine-readable AI mark rose sharply in **June 2026**: from 25.8% of January–May uploads (n = 532) to 50.2% of June–July uploads (n = 313). That is +24.4 percentage points; a bootstrap that resamples upload days gives +14.7 to +33.6. August–September (n = 461) shows 43.4%, or 53.3% without one large unmarked batch of coats of arms.

**Before and after 2 August.** The comparison of January–July with August–September gives +8.4 pp (day-cluster bootstrap +0.2 to +17). 2 August 2026 is when Art. 50(2) of the EU AI Act began to apply to new systems; under Art. 111(4) as amended, systems already on the market have until 2 December 2026. The comparison depends on one batch: without it, the difference is +17.8 pp. Neither comparison can be attributed to the AI Act.

**Kinds of mark.** Almost every mark is a C2PA manifest, mostly from OpenAI and Google. The IPTC `DigitalSourceType` alone marks 1.5% of main files. A readable Chinese AIGC label appears on 1 file of the union, and 3 more files carry a double-encoded label.

**Validation.** We found a defect in our own validator: ai-mark-lint 0.1.0 rejected 302 of the 625 readable manifests (union), 187 of them because no extended-key-usage list was configured. The defect is fixed in 0.1.1. With the corrected rule, 117 manifests (18.7%) fail, for these reasons:

- certificates that have expired in manifests without a time-stamp (85);
- content changed after signing (32);
- C2PA first-action rule violations (26);
- Microsoft Paint manifests (12).

With the official C2PA Trust List, 452 of 624 manifests (72%) are valid and trusted.

**Competing interests:** ai-mark-lint, the instrument of this study, is developed by the authors' organisation; this study found and fixed two defects in it.

*EasyxLab, study S6 · a research lab by EasyByte · October 2026*

## Layout

| path | content |
|---|---|
| [paper](https://easybyte.es/lab/studies/s6/paper/) (web) | the paper: prior work, method, results, competing interests, limitations, automation and review |
| `METHOD.md` | population, sample and stop rule, measurement, access policy, statistics |
| `scripts/run.sh` | setup → enumerate → sample → measure (resumable) → follow-up → sanitize → tables → headline check |
| `scripts/analyze.py` | every table and number in README and paper, from `data/` only (`python3 scripts/analyze.py`, stdlib only) |
| `scripts/check_headlines.py` | asserts every headline number against `data/` and the text |
| `scripts/` (other) | `enumerate.py`, `sample.py`, `fetch_meta.py`, `measure.py`, `sanitize.py`, `prior_work.py`, `commons.py` (polite API client) |
| `data/per_file.csv` | one row per inspected file: Commons title and page URL, month, marks, signer, ai-mark-lint 0.1.0 and 0.1.1 verdicts, failure codes under each configuration |
| `data/summary.md`, `data/headline.json` | all tables; the headline numbers |
| `data/results.jsonl`, `data/results_followup.jsonl` | raw per-file records |
| `data/validation_failures.csv` | every manifest that fails under 0.1.0, with its class and its 0.1.1 verdict |
| `data/population.csv.gz`, `data/category_tree.csv`, `data/population_by_month.csv`, `data/sample.csv`, `data/sample_categories.csv` | population, sample and derived category flags; categories named after users appear only as placeholders |
| `data/trust/`, `data/certs/` | trust lists used (official C2PA list @ `3573be5`, interim list); public certificate chains seen (device-specific certificates removed) |

## Run

```bash
python3 scripts/analyze.py && python3 scripts/check_headlines.py   # tables + checks from data/ (stdlib, offline, ~10 s)
scripts/run.sh analyze                                              # the same, via run.sh
scripts/run.sh                                                      # full re-run: setup (~170 MB), Commons at 1 request/s, hours
```

`.venv/`, `tools/` and `work/` are local only. At most one image is on disk at any time, and it is deleted after inspection. Images are never redistributed. Nothing is edited on Commons.

## Cite

EasyxLab (2026). Do AI-generated images on Wikimedia Commons carry provenance marks? Study S6. EasyByte Hub S. Coop. Mad. https://github.com/easybytehub/easyxlab

Code: Apache-2.0. Data and text: CC BY 4.0. The Commons titles and URLs in `data/` point to public pages; the images keep their own licences on Commons.
