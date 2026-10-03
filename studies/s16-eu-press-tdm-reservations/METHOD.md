# METHOD — S16 Text-and-data-mining reservations in the EU-27 press, channel by channel

*EasyxLab · study S16 · method frozen 2026-10-03 before the main collection (sha256 and time in the private status file; deviations are logged at the end of this file)*

> Freeze trail: EasyxLab keeps the frozen text (sha256 `875ec0afcf1de846d252022ed8334bdac38d83d30259d6f427e9056ecc92c6ea`,
> 2026-10-03 11:18 UTC). This file differs from it only in the passages marked *[after the freeze]* and in the
> Deviations section, which then read "(none yet)". Corrections of fact are marked; changes of rule are deviations.

## 1. Question

Among news publishers in the 27 EU Member States, how many websites express a reservation of
text and data mining (TDM) that a machine can read and that binds any crawler whatever its name
("agnostic"), how many only block a list of named AI crawlers, how many state a reservation only in
`robots.txt` comments (which an RFC 9309 parser ignores), how many state none, and how many
contradict themselves across machine-readable channels?

## 2. Population and frame

**Source of outlets: Wikidata (CC0)**, queried on 2026-10-03 through the QLever SPARQL endpoint of
the University of Freiburg (`https://qlever.cs.uni-freiburg.de/api/wikidata`), whose Wikidata copy
is dated 2026-08-12 (the `schema:dateModified` of `wikiba.se/ontology#Dump`). We did **not** use
`query.wikidata.org`: its `robots.txt` contains `Disallow: /sparql`. QLever serves no `robots.txt`
(HTTP 404, which RFC 9309 s. 2.3.1.3 reads as no restriction).

Items selected (query in `scripts/build_population.py`):
- `P31/P279*` newspaper (Q11032, which includes daily, weekly, free and regional newspapers), or
  `P31` online newspaper (Q1153191), news website (Q17232649) or news magazine (Q1684600);
- country (`P17`) or country of origin (`P495`) one of the 27 Member States;
- an official website (`P856`);
- no dissolution date (`P576`) and no discontinued date (`P2669`).

Result: 3,063 item × country × website rows, 2,553 items.

**Frame filter: the Chrome UX Report (CrUX) country top lists** of August 2026 (`202608`), as cached
in `github.com/zakird/crux-top-lists` (`data/country/<cc>/202608.csv.gz`). CrUX buckets origins by
popularity (1,000 / 5,000 / 10,000 / 50,000 / 100,000 / … / 1,000,000) per country. An outlet is in
the frame when its website host (with or without `www.`) is an origin in the **top 100,000 bucket
or better of its own country's list**. The repository declares no licence; its README says "The
data in this repo is all publicly posted by Google to their CrUX dataset in Google BigQuery. This is
simply a cache of that public data." We publish only each frame host's bucket (a fact), never the
lists. The CrUX licence is quoted in the paper from Google's documentation.

**Exclusion rules** (applied in this order; every excluded row is listed in `data/exclusions.csv`):

| rule | excluded |
|---|---|
| E1 | the website value is not an http(s) URL |
| E2 | the host (or a parent domain) is a library, a digitised-newspaper archive, a document or blog platform, a social network or an encyclopaedia (list in `PLATFORM_DOMAINS`, plus hosts containing `biblioteca`, `bibliothek`, `hemeroteca`, `archiv`) |
| E7 | official gazettes and public-sector hosts (`boe.es`, `journal-officiel.gouv.fr`, `gazzettaufficiale.it`, any `gouv.`/`gov.`/`gob.`/`gv.at` host): Wikidata classes gazettes as newspapers, but they are published by public bodies |
| E3 | the website is a page inside a host rather than a site root (any query string, or a path other than `/`, a two-letter language segment, `index.*` or `home`) |
| E4 | the host is not in the top-100,000 CrUX bucket of the outlet's country |
| E5 | one domain per outlet: when an outlet has several qualifying hosts, the best-ranked is kept |
| E6 | one row per host: when several outlets share a host (editions, renamed titles), the item with most Wikipedia sitelinks is kept |

**Frame: 1,533 hosts** in 27 countries at the freeze; **1,511** after deviation D6 (`data/frame.csv`).
Country sizes are uneven (Malta 1, Cyprus 4 … Spain 182, France 196 after D6; Spain 190, France 197
at the freeze *[after the freeze, correction: the frozen text said 191 and 198, counted before rule E7
was added]*); results are reported by country only with their n, and percentages with intervals only
for countries with n ≥ 30. Country bands: **large** (n ≥ 100),
**medium** (30 ≤ n < 100), **small** (n < 30).

## 3. Access rules (enforced in code: `scripts/politefetch.py`)

- Every request goes through one helper. For every host, `robots.txt` is fetched first (HTTPS,
  then HTTP if HTTPS fails) and parsed with the RFC 9309 parser of EasyxLab study S8
  (`scripts/robots9309.py`, copied unchanged). Every other URL — `/.well-known/tdmrep.json`, the
  home page, `/llms.txt`, and every redirect hop — is requested only if that host's `robots.txt`
  allows it for our product token `EasyxLab-research`. 4xx on `robots.txt` = no restriction;
  5xx, timeouts or network errors = complete disallow (RFC 9309 s. 2.3.1.4): nothing else is
  requested and the host is reported as "robots.txt unreachable".
- **Natural-language prohibition.** If the comments of a host's `robots.txt` forbid robots or
  automated access (`nlcomments.prohibition`, tuned for recall), **no further request** is made to
  that host. It is reported as "not read: natural-language prohibition" and classified on its
  `robots.txt` alone (a lower bound: its TDMRep file, headers and `<meta>` are unknown).
- User-Agent `EasyxLab-research/0.1 (+https://easybyte.es/lab/; contact@easybyte.es)`; at most one
  request per second per host; at most 8 resource fetches per host; 15 s timeout. *[after the freeze, correction: a fetch can take several requests through redirects; the most requests any host
  received was 10, an official gazette later excluded under D6]*
- *[after the freeze, D5]* **What we read, and why a purpose-specific notice is not a prohibition of
  this reading** (decision of the study's coordinating AI agent): beyond `robots.txt` we read only the channels a site declares for
  machines (`/.well-known/tdmrep.json`, the response headers and `<meta>` elements of the home page,
  `/llms.txt`) and store no article content. A comment that forbids robots or automated access in
  general stops us. A notice that forbids TDM or AI training (purpose-specific), a section label
  ("Not allowed bots") or an inline comment on one agent's rule (`Disallow: / # prohibits crawling`
  under `User-agent: Yandex`) does not; a purpose-specific notice is counted as a reservation.
- `contentsignals.org` is never requested by script (its `robots.txt` objects to automated
  collection).
- The home page body is parsed for `<meta>` elements in `<head>` only; no page content is stored.

## 4. Channels read per host

| channel | what is read | source of the syntax |
|---|---|---|
| robots.txt groups | for each of 26 AI-related product tokens (list in `optout_check.AI_TOKENS`), whether a group naming it disallows `/`; whether a crawler with an unknown name (`s16-unnamed-crawler`, i.e. the `*` group) is disallowed `/` | RFC 9309 |
| Content-Signal | `Content-Signal:` lines (any group); the `ai-train` value | Cloudflare documentation (managed robots.txt) |
| Content-Usage (robots.txt) | `Content-Usage:` rules; the `train-ai` value applying to `/` for an unnamed crawler (rules of the `*` group, longest matching path) | draft-ietf-aipref-attach-05 (2026-08-19), draft-ietf-aipref-vocab-08 (2026-09-14) |
| comments | natural-language reservation of TDM/AI use (`nlcomments.reservation`) and prohibition of automated access (`nlcomments.prohibition`), per comment block | — |
| TDMRep file | `/.well-known/tdmrep.json`: valid JSON array; any rule with `tdm-reservation: 1`; the rule covering `/`; `tdm-policy`. A 200 response that is HTML (or starts with `<`) is a **soft 404 = absent** | W3C TDMRep CG Final Report, 2024-05-10 |
| TDMRep header | `tdm-reservation` / `tdm-policy` HTTP headers of the home page | idem, s. 6.2 |
| TDMRep meta | `<meta name="tdm-reservation">` / `tdm-policy` in the home page `<head>` | idem, s. 6.3 |
| Content-Usage header | `Content-Usage` HTTP header of the home page | attach-05 s. 2 |
| noai | `noai`/`noimageai` in `<meta name="robots">` or `X-Robots-Tag` (non-standard; reported separately) | — |
| llms.txt | `/llms.txt` present (200, not HTML); context only, not a reservation | — |

## 5. Classification (frozen)

Per host, exactly one class, in this order of precedence:

1. **agnostic reservation** — any of: a TDMRep reservation (`tdm-reservation` = 1) in the file
   (any rule), header or meta; `Content-Signal` with `ai-train=no`; `Content-Usage` `train-ai=n`
   applying to an unnamed crawler at `/` or sent as an HTTP header; or the `*` group disallowing
   `/` (a crawler with a new name cannot fetch anything).
2. **named-bot only** — no agnostic reservation, but at least one of the 26 named AI tokens is
   disallowed `/` by a group that names it.
3. **comment-only** — neither, but a natural-language reservation of TDM/AI use or a prohibition of
   automated access in the `robots.txt` comments.
4. **none stated** — none of the above.

Flag, independent of the class: **contradiction** — two explicit machine-readable use-preference
channels disagree: one says reserve (`tdm-reservation` 1, `ai-train=no`, `train-ai=n`) and another
says allow (`tdm-reservation` 0, `ai-train=yes`, `train-ai=y`). Access rules (Allow/Disallow) are
not use preferences and do not enter this flag.

Hosts read on `robots.txt` alone (natural-language prohibition) get the same class with the suffix
`_robots_only_partial` (`named_bots_robots_only_partial`: "named bots in robots.txt; other channels
not read"), since their TDMRep, headers and `<meta>` are unknown *[after the freeze, B1]*. Hosts whose `robots.txt` is unreachable are reported separately and are outside the denominator of
the class shares. Hosts not read because of a natural-language prohibition stay in the denominator,
classified on `robots.txt` (marked "partial").

**Headline denominator:** frame hosts whose `robots.txt` was obtained or answered 4xx.
**Secondary figures:** shares among hosts that block at least one named AI crawler; TDMRep by
channel; `noai` as a sensitivity variant (counted as agnostic); per-country and per-band tables.
Intervals: Wilson 95%.

## 6. Comment-detector audit (frozen plan)

After the scan, a sample is drawn with a fixed seed (`20261003`): **all** hosts flagged by either
detector if there are ≤ 60, otherwise 60 at random, plus 40 random hosts with at least one comment
block and no flag. The comment blocks of each sampled host are read by the AI agent that ran the
study and labelled: does a comment (a) reserve TDM/AI use, (b) prohibit robots or automated
access in general? Reported: precision of each detector on its flagged hosts, and the misses found
among the unflagged hosts (an estimate of recall in that stratum).

## 7. Published data

`data/frame.csv` (outlet, Wikidata QID, host, country, CrUX bucket), `data/exclusions.csv`,
`data/records.csv` (one row per host: channel values and verdict), aggregates in `data/summary.json`
and `data/*.csv`, `data/comment_audit.csv` (labels and detector outputs, no comment text), and
`data/sources_manifest.csv` (each legal/technical/provider document with URL, date and sha256).
Raw `robots.txt` bodies and documents stay in `data/raw/` (not published).

## Sources at a glance *[after the freeze, re-review 2026-10-03]*

| source | host | access | rate | licence / condition |
|---|---|---|---|---|
| Wikidata | qlever.cs.uni-freiburg.de | SPARQL API (no robots.txt: 404) | 1 req/s | CC0; `query.wikidata.org` not used: `Disallow: /sparql` |
| CrUX country lists | raw.githubusercontent.com (zakird/crux-top-lists) | file download (no robots.txt) | 1 req/s | CrUX CC BY 4.0; repository declares no licence |
| EU law | publications.europa.eu (Cellar) | document download | 1 req/s | EU legal texts |
| Code of Practice | code-of-practice.ai | page | 1 req/s | unofficial transcription; official PDF path disallowed by ec.europa.eu |
| W3C, IETF, Cloudflare docs | www.w3.org, www.ietf.org, developers.cloudflare.com | pages | 1 req/s | as published |
| Provider documentation | 14 hosts (`data/sources_manifest.csv`) | pages, where robots.txt allows | 1 req/s | short quotes only |
| Press sites | 1,511 frame hosts | robots.txt, then declared policy channels only | 1 req/s per host | robots.txt and comment prohibitions obeyed (s. 3) |

All requests: User-Agent `EasyxLab-research/0.1 (+https://easybyte.es/lab/; contact@easybyte.es)`,
through `scripts/politefetch.py`. EasyxLab's lab-wide rule of 3 October 2026 treats `robots.txt` as
binding at the legal minimum. S16 keeps the stricter rule of s. 3 on purpose, because its subject is
those reservations.

## Deviations (logged after the freeze)

**D1 — a redirect hop to a third host before its `robots.txt` (scan, 2026-10-03).** The
`robots.txt` of two frame hosts redirected to a single-sign-on host of their publishing platform
(`sso.worldoftulo.com`). The helper followed `robots.txt` redirects without checking the new
host (RFC 9309 s. 2.3.1.2 asks crawlers to follow them), so 7 requests reached that host before
its own `robots.txt` was read. That host answers 404 for `/robots.txt` (no restriction), and the
two frame hosts ended as "robots.txt unreachable" (redirect loop) or were read normally. The code
now checks every cross-host hop, including those of a `robots.txt` fetch
(`politefetch.get`). Found by `scripts/audit_requests.py` (`data/request_audit.json`).

**D0 — the scouting pilot (before the study).** The pilot that proposed S16 read the home pages
of up to 14 hosts whose `robots.txt` comments prohibit "the use of programs or robots". Those
requests breached the access rule this study adopted. The pilot's records were deleted with its
scratch and nothing from them is used.

**D2 — comment detector version 2 and deleted data (after the scan, before any analysis).**
Reading the audit sample showed that detector v1 missed natural-language prohibitions when the
sentence contained a domain name ("access taz.de or collect … is strictly prohibited": the dot
ended the window), when the forbidding words came more than 80 characters before the agent
words, and in the phrasing "is not to be used … programs or robots". Version 2
(`nlcomments.VERSION = 2`) fixes these three points and nothing else. Because the frozen access
rule says no request beyond `robots.txt` to such hosts, the D2 step (now in `scripts/apply_detectors.py`) re-ran the
detectors over the stored `robots.txt` bodies (no new request) and **deleted** the TDMRep-file,
home-page and `llms.txt` data of the **92 hosts** that v2 newly flags; they had received **245
requests** beyond `robots.txt` (`data/deviation_d2.json`). They are classified on `robots.txt`
alone, like the 135 hosts v1 had already stopped at. These 245 requests breached the study's own
access rule. Their response status was also removed from the request log; URL and time are kept as
the accountability record. 26 of the 92 are not general prohibitions under D5 and were re-read in
the D5 re-scan; their D2 data were not restored. The audit sample was drawn on the v1 flags as
planned; v2's figures on that sample are optimistic, because v2 was revised after reading part of it.

**D3 — request log timestamps.** The scan's request log recorded the time each response
completed, not when the request started, so the log cannot demonstrate the one-second pacing
(which `politefetch._pace` enforces before every request). The log now records start times.

**D4 — actu.fr (found by the independent review).** Its comments say "il est interdit : - d'utiliser
tout système logiciel automatisé, robots ou programme … visant à extraire des données", a general
prohibition written as a list, which detectors v1 and v2 missed because the forbidding phrase and
the list item sit in different comment blocks. The scan read its TDMRep file, home page and
`llms.txt` (3 requests, 2026-10-03 11:21 UTC), in breach of the access rule. Every field beyond
`robots.txt` was deleted from `data/`, the response status of those requests was removed from the
log, and the site is classified on `robots.txt` alone (`data/deviation_d4.json`).

**D5 — detector v3 and a targeted re-scan (decision of the study's coordinating AI agent after the review).** v3 applies
the access rule as stated in s. 3: general prohibitions stop us; inline comments on one agent's
rule, section labels (≤ 4 words, no verb) and purpose-specific notices (a TDM/AI term in the
prohibiting clause, without "particularly"/"in particular") do not, and the latter count as
reservations. It also reads list-style notices across comment blocks and no longer lets a domain
name ("exa.ai") match the "AI" pattern. Applied to the stored bodies, v3 newly flags one host that
had been read (actu.fr, D4) and no longer flags 98 hosts (47 of one Finnish group's purpose-specific
text, 23 Mediahuis, 11 section labels, 2 inline comments on Corriere's Yandex rule, Austrian and
Swedish purpose-specific notices; the full list with evidence is `data/d5_status_changes.csv`).
Those 98 were re-read once under the frozen fetch rules (robots.txt first, 1 request/s/host) on
2026-10-03, 11:55:54–11:56:15 UTC (`data/deviation_d5.json`); their new records replace the old ones.
D2 hosts that v3 still flags, and actu.fr, stay robots-only.

**D6 — official gazettes (found by the independent review).** The frozen rule E7 excludes official
gazettes and public-sector publishers, but its implementation matched a hand list and `gov`-type
domains only. It is completed with every EU-27 Wikidata item of class "government gazette"
(Q2065227, with subclasses; QLever query of 2026-10-03), the Staatscourant (its item lacks the class)
and Das Parlament (published by the German Bundestag): 22 hosts. The frame goes from 1,533 to 1,511;
their scan records are kept in EasyxLab's raw data but are outside every figure.

**D5 — correction (re-review, 2026-10-03).** D5 was a change of the access rule made after
collection, on the decision of the study's coordinating AI agent. The frozen rule stopped at any comment the detector
flagged. D5 decided which texts count as a general prohibition, and so freed 98 hosts. Only the
fetch mechanics were unchanged (robots.txt first, 1 request/s/host). The re-scan's requests ran from
11:55:54 to 11:56:18 UTC. It also fetched `https://login.mediahuis.com/robots.txt`, a redirect target,
and nothing else on that host. Figures that depend on D5 are reported with the frozen-rule
sensitivity beside them (fully read 1,282; agnostic 93, 7.3%; contradictions 0).

**D7 — general prohibitions read in the D5 re-scan (re-review, 2026-10-03).** Two kinds of notice
were read in the re-scan although they are general prohibitions:
- The 23 Mediahuis notices say content "is not to be used for the purposes of text and data mining,
  extraction, scraping and/or the use of programs or robots for automatic data collection … whether
  for machine learning or artificial intelligence purposes or otherwise".
- fd.nl prohibits scraping and harvesting with an open list of uses ("include but are not limited to
  … (4) any commercial purposes").

The study's own instructions had classed the Mediahuis notice as purpose-specific: the D5 decision
quoted a shortened excerpt. That misclassification came from the study's coordination, not from the
sites, and is stated here as such. D2 and D0 had already read the same notice as a general
prohibition.

The D5 re-scan sent these 24 hosts 96 requests, 72 of them beyond `robots.txt`. That breached the
study's own access rule. Detector v4 (`nlcomments.VERSION = 4`) changes exactly two things:
- a ban that names TDM/AI purposes but ends in an open clause ("or otherwise", "for any purpose",
  "not limited to", "any commercial purposes") is general;
- a short heading whose only reservation word is in parentheses is a label (this fixes
  kristeligt-dagblad.dk's reservation flag).

Applied to the stored bodies, v4 changes the status of exactly these 25 hosts. Every field beyond
`robots.txt` of the 24 was deleted from `data/`, and the response status of the 72 requests was
removed from the log, keeping URL and time. The 24 are classified on `robots.txt` alone
(`data/deviation_d7.json`). Fully read sites go from 1,380 to 1,356.
