# S6 — Method

## 1. Research questions

1. What fraction of the AI-generated images uploaded to Wikimedia Commons carries a machine-readable AI mark? Of which kind (C2PA manifest, IPTC `DigitalSourceType` in XMP, Chinese `TC260:AIGC` label)? Is the C2PA signature valid, broken, or absent?
2. Did that change once Art. 50(2) of the EU AI Act became applicable (2 August 2026)? We compare uploads of January–July 2026 with August–September 2026, and with 2024–2025.
3. How does it vary by the generator declared on Commons (categories) and by C2PA signer?
4. When a C2PA manifest fails validation, is the failure real (an expired or revoked certificate, a file modified after signing) or a consequence of the validator's configuration (trust lists, EKU list) or library version?

## 2. Why Commons

MediaWiki stores the uploaded file byte for byte and serves it at `upload.wikimedia.org`; only thumbnails are re-encoded. We checked this for every file: the SHA-1 of each download was compared with the `sha1` the API reports for the stored original (§7). This makes Commons one of the few large public collections of AI images whose provenance metadata has *not* been removed by the host. Social networks do remove it: a dataset of 10,217 GPT-image-2 images collected from X in April 2026 reports that "C2PA content credentials are systematically stripped by Twitter's CDN on upload, rendering cryptographic provenance verification infeasible for social-media-sourced AI images" (Zewde et al., arXiv:2604.25370, abstract; fetched 2026-10-02, `work/docs/arxiv-2604.25370.xml`).

## 3. Population (`scripts/enumerate.py`, `scripts/fetch_meta.py`)

The population is the union of two sets, both read from the Commons Action API (`https://commons.wikimedia.org/w/api.php`) on 2026-10-02.

**(a) Category tree.** Every file in `Category:AI-generated images` and its subcategories, visited breadth-first (`generator=categorymembers`, `gcmtype=subcat|file`, `prop=imageinfo|categoryinfo`). Root = depth 0, cap 6,000 categories.

- At depth 6 the code requests files only (`gcmtype=file`), so it does not itself learn whether depth-6 categories have subcategories. The independent reviewer checked the five depth-6 categories on 2026-10-03 (`prop=categoryinfo`): none has subcategories, so the walk is complete at 530 categories.
- Each file keeps the smallest depth at which it was found (`found_in`).
- `data/category_tree.csv` lists every category with its depth and parent. Categories named after a user (named prompters under `AI-generated images by human prompter`, and names containing "user", "uploaded by", "files by", "taken by") appear only as `Category:[user-named category NN]` (`scripts/sanitize.py`).

**(b) Template.** Every file page that transcludes `{{PD-algorithm}}` (`generator=embeddedin`, namespace File). This template also covers older algorithmic works (fractals, plots).

**Main vs union.** Analyses are reported for two populations:

- **union**: everything in (a) or (b);
- **main**: (a), plus the files of (b) whose own categories match the AI pattern of `fetch_meta.py`. The pattern is the word "AI", or one of: "artificial intelligence", "AI-generated", "AI-assisted", generator names, "text-to-image", "generative", "neural", "upscal…", "Deep Dream", "MyHeritage" and similar.

The rule admits AI-generated files, AI-modified ones (upscaled, retouched, colourised photographs) and a few files *about* AI, such as screenshots of AI products. 85 measured files entered "main" this way; `data/summary.md` §4 shows which part of the pattern matched.

The category tree also contains AI-modified photographs: for example `Google Gemini retouched pictures` and `AI-generated coats of arms` redrawn from historical arms. 149 of the 1,585 measured main files carry a category suggesting modification of an existing image (flag `ai_modified`).

`fetch_meta.py` saves the raw category lists of sampled files to `work/` only. They contain user categories and are not published. Only the derived flags go to `data/sample_categories.csv`: `generator`, `ai_evidence`, `ai_evidence_rule`, `coats_of_arms`, `ai_modified`.

For each file we keep the page id, title, page URL, original URL, MIME type, size, SHA-1 and the timestamp of the **current file version** (the bytes we analyse). We never request the uploader (`iiprop=user` is not used).

## 4. Sample (`scripts/sample.py`)

**Frame.** The population restricted to raster formats ai-mark-lint reads: JPEG, PNG, WebP, AVIF/HEIF. That is 7,090 of 8,971 files; SVG, GIF, audio, video and PDF are counted in `data/population_by_month.csv` only.

**Planned sample** (seed `20261002`, strata = calendar month of the current file version), 3,429 files:

- a **census of January–September 2026** (2,369);
- 40 per month for 2024–2025 (960);
- 100 before 2024;
- the 2 days of October 2026 are not sampled.

**Processing order.** Downloads ran at about 0.3–0.7 MB/s at one request per second, against roughly 5 GB planned. Files were therefore processed in rounds:

1. a quota per month: 250 for August and September, 70 for each of January–July, 15 for each month of 2024–2025, 25 before 2024;
2. the rest of the 2026 census;
3. the rest.

Within each round the order is the seeded shuffle. Any prefix of the order therefore contains, for every month, the first *k* files of that month's random permutation. This was checked at each restart, and by the reviewer, with 0 violations. Given a stop rule that does not depend on the outcomes, that is a simple random subsample within each month.

**Stop rule.** The agent fixed the time budget at about 23:25 CEST on 2 October (stop at 00:15 CEST on 3 October) and the run was stopped then, during round 2. The agent had already looked at interim results (STATUS.md, "hallazgos provisionales"). The stop is therefore not formally independent of the data. Through download time it also depends weakly on file size, which correlates with the generator. Both effects are small, but the subsample is not exactly simple random.

**Result.** 2,091 rows inspected and 2,084 measured:

- January–July 2026: 1,107 of 1,530;
- August–September 2026: 592 of 839;
- 2024–2025: 360;
- before 2024: 25.

**Non-response.** Seven September 2026 files returned HTTP 404, deleted between enumeration and download. They are treated as missing at random.

Two September files were measured by ai-mark-lint, but our certificate-extraction step raised an error: `cryptography` rejects a non-canonical DER `BasicConstraints` in xAI Grok Imagine's self-signed certificate. An earlier draft excluded them. `scripts/sanitize.py` restores them, and `measure.py` now catches the error per certificate.

## 5. Measurement (`scripts/measure.py`)

For each sampled file, one at a time:

1. Download the original from `upload.wikimedia.org` into `work/tmp/` (cap 120 MB) and compare its SHA-1 with the API value.
2. Run the instrument, **ai-mark-lint 0.1.0** (the wheel attached to the GitHub release `v0.1.0`, SHA-256 `1b5a2ae6…e1f9`; it bundles c2pa-python 0.38.0 = c2pa-rs 0.91.0), as `ai-mark-lint FILE --format json --jurisdiction none`. We keep its `marks` object (`c2pa`: absent / valid / invalid / unreadable / remote-reference-only; `c2pa_ai`; `iptc-dst`; `aigc`) and the rule ids it reports. Its library API (`ai_mark_lint.marcas.inventaria`) is called on the same file to record values the CLI does not print: the `digitalSourceType` URIs, `softwareAgent`, claim generator, signer and the failure codes.
3. If a C2PA manifest is present, we characterise its validation (question 4):
   - ai-mark-lint again with `--trust-anchors` = the **official C2PA Trust List** (signer list + TSA list from `c2pa-org/conformance-public`, commit `3573be5`, list issued 2026-08-05);
   - the c2pa `Reader` directly, keeping each failure code **with its explanation**, under six configurations: none; official; interim (the frozen list served by contentcredentials.org / verify.contentauthenticity.org, with its EKU file `store.cfg`); official + interim; `none_eku` (no trust list, c2pa-rs's own default EKU list `valid_eku_oids.cfg` passed as `trust_config`); `official_eku` (official signer + TSA lists + that EKU list). The last two were added after the first 908 files had been measured, once the EKU artefact was found: `measure.py --followup` re-downloaded the 260 earlier C2PA files (SHA-1 re-checked) and validated them under all six; `analyze.py` merges both files;
   - two other validator builds with default settings: **c2pa-python 0.10.0** (c2pa-rs 0.55.0, May 2025) in a separate virtual environment, and **c2patool 0.27.22** (c2pa-rs 0.90.22);
   - the certificate chain (`c2patool --certs`): subject, issuer, validity window and EKUs of each certificate. The public certificates are kept in `data/certs/` by fingerprint.
   No configuration fetches anything from the network (remote manifests and OCSP are disabled), so revocation is **not** checked.
4. Append one JSON line to `data/results.jsonl` and **delete the file**. There is never more than one image on disk.

**Two validator verdicts.**

- **ai-mark-lint 0.1.0** as released: the CLI run above. It builds its c2pa context without an EKU list, which is the defect described in paper §4.4.
- **ai-mark-lint 0.1.1** (released 2026-10-03), *emulated* in `analyze.py` from the recorded reader outputs:
  - take the `none_eku` configuration (c2pa-rs's default EKU list passed);
  - drop `signingCredential.expired` when `timeStamp.untrusted` is among the informational codes (0.1.1 reports that case as a trust question, C2PA-003);
  - treat a manifest as invalid if any core failure code remains, or if the library state is `Invalid` with no failure code at all (as ai-mark-lint does);
  - for the 0.1.1 verdict with the official list, apply the same rule to `official_eku`.

The reviewer re-ran ai-mark-lint 0.1.1 on 13 files of every class and found the emulation matches.

**Sanitising (`scripts/sanitize.py`, once, after measurement).**

- Remove Python traces and machine paths from `results*.jsonl`.
- Restore the two Grok records.
- Reduce Samsung device-attestation certificates (per-device hash, phone model, attestation UID) to their issuing organisation.
- Replace user-named categories with placeholders.
- Delete certificates that are device-specific, test, or referenced by no record.

**Mark definitions.** *Any machine-readable AI mark* = a readable C2PA manifest whose actions (or whose ingredients' actions) declare an AI `digitalSourceType` (`trainedAlgorithmicMedia`, `compositeSynthetic`, `algorithmicMedia`, `compositeWithTrainedAlgorithmicMedia`), **or** an IPTC `DigitalSourceType` with one of those values in XMP, **or** a readable `TC260:AIGC` label. A C2PA manifest counts as *valid* when it has no failure code other than `*.untrusted` and `cawg.*` (ai-mark-lint's rule; trust is a property of the verifier, not of the file).

## 6. Access policy

- User-Agent. Enumeration, sample categories and the main measurement run (2026-10-02 20:58 → 2026-10-03 00:15 CEST) sent `EasyByteLab-research/0.1 (contact: contact@easybyte.es)`. The lab was renamed EasyxLab during the run, so the trust follow-up and the prior-work search (2026-10-03) sent `EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)`. The Wikimedia Foundation User-Agent Policy says: "If you operate a bot, please send a User-Agent header identifying the bot in a way that isn't going to be confused with many other bots, and supplying some way of contacting you, the operator" and "The contact information should be given as an email address, a website, or a wiki user" (foundation.wikimedia.org, `Policy:Wikimedia Foundation User-Agent Policy`, fetched 2026-10-02, `work/docs/ua-policy.json`). It also suggests ("please consider") including the string "bot"; we kept the agent name fixed by the study protocol and say so here.
- Strictly serial requests and at most **one request per second** across the API and file downloads, `maxlag=5`, gzip, exponential back-off on 429/5xx — following API:Etiquette: "Making your requests in series rather than in parallel, by waiting for one request to finish before sending a new request, should result in a safe request rate", and "If your task is not interactive … you should use the maxlag parameter" (mediawiki.org, fetched 2026-10-02).
- robots.txt. `commons.wikimedia.org/robots.txt` has `User-agent: *` / `Disallow: /w/`, a rule for crawlers of rendered pages; the Action API under `/w/api.php` is the interface the Foundation documents for scripts (the User-Agent policy names "scripts (bots) accessing Wikimedia websites … via api.php"). We crawl no HTML pages. `upload.wikimedia.org/robots.txt` disallows only `/wikipedia/commons/archive/` (old file versions), which we never request. Both files are kept in `work/docs/`.
- Read-only: no login, no edits, no POST. Images are not redistributed. Results are published per file with the Commons title and page URL (public), **without the uploader's name**.

## 7. Analysis (`scripts/analyze.py`; checked by `scripts/check_headlines.py`)

**Month level.** Proportions per month are simple random-sample proportions with **Wilson** 95% intervals.

**Period level.** Periods (2024, 2025, January–May, June–July, January–July and August–September 2026) use the stratified domain estimator $\hat p = \sum_h w_h \hat p_h$:

- the weights are $w_h \propto N_h d_h / n_h$, where $N_h$ is the month's frame size, $n_h$ the files measured in the month and $d_h$ those in the domain (main or union);
- the variance is $\sum_h w_h^2\, \hat p_h(1-\hat p_h)/(n_h-1)$, **without** a finite-population correction, because the claims concern the upload process (a superpopulation), not the files on Commons on 2 October;
- the Wilson interval is computed on the Kish effective $n = \hat p(1-\hat p)/\widehat{\mathrm{Var}}$.

**Clustering.** Uploads come in batches: the same uploader, day and category. Comparisons are reported two ways:

- **Newcombe**'s hybrid score interval (method 10), which treats files as independent;
- a **day-cluster bootstrap**: within each 2026 month, upload days are resampled with replacement, keeping all files of a day together; the estimator is recomputed, 2,000 replicates (seed `20261003`), percentile interval.

The bootstrap is the interval to use. A sensitivity analysis removes the `AI-generated coats of arms` branch (flag `coats_of_arms`), a single large batch that dominates August 2026.

**Decomposition.** The June jump is decomposed by mark source (OpenAI-, Google-, Microsoft-signed, other C2PA, IPTC/AIGC only) as weighted shares of main files.

**Unweighted tables.** Generator and signer tables are unweighted and describe the sample.

**Output.** Every number in README and paper is produced here, collected in `data/headline.json` and asserted by `check_headlines.py`.

## 8. Prior-work search (`scripts/prior_work.py`)

Run on 2026-10-02/03 (`--extra` for the post-review pass: four more arXiv queries, arXiv:2503.18156, Semantic Scholar retry). Raw responses are in `work/docs/prior/` (local only, not published). Sources:

- arXiv API, 4 queries;
- Crossref, 2;
- Semantic Scholar Graph API, 3 queries (HTTP 429 on the first attempt; 2 retried);
- `gh search repos`, 4;
- Commons search API over the project, help and template namespaces, 4 queries;
- wikitext of `Commons:AI-generated media`, `Commons:Signs of AI media` and two Village pump archives;
- Phabricator Conduit `maniphest.search`, which refused anonymous access ("Session key is not present").

The exact queries and results are in `paper.md` §2.

## 9. Known limitations of the design

See `paper.md` §7. In short: Commons uploaders are a self-selected group; a file without a mark may never have had one or may have lost it before upload (we cannot tell which); invisible watermarks (SynthID and others) are not examined; revocation is not checked (no network); the category tree is cut at depth 6 and `{{PD-algorithm}}` also covers non-AI algorithmic works; the timestamp is that of the current file version, which for re-uploaded files is later than the first upload.
