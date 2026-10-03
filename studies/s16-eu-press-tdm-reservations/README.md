# S16 — Text-and-data-mining reservations in the EU-27 press, channel by channel

*EasyxLab · study S16 · data collected 2026-10-03 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s16/paper/](https://easybyte.es/lab/studies/s16/paper/) · [PDF](https://easybyte.es/lab/studies/s16/paper.pdf)

## Abstract

Since 2 August 2025 the AI Act (Art. 53(1)(c)) has required providers of general-purpose AI models
to identify and comply with reservations of text and data mining expressed under Art. 4(3) of
Directive (EU) 2019/790, "such as machine-readable means" for content online. Models placed on the
market before that date have until 2 August 2027 (Art. 111(3)). The Commission can fine providers
from 2 August 2026.

We read what a crawler can read on 1,511 news websites in 27 Member States: newspapers and news
sites from Wikidata whose host is in the top 100,000 of their country's Chrome UX Report list,
with official gazettes excluded. The channels were `robots.txt` (RFC 9309), TDMRep (file, HTTP
header, `<meta>`), Content-Signal, the IETF `Content-Usage` rule, `noai` and `llms.txt`. We
requested a URL only where `robots.txt` allowed it.

**On the 1,356 sites we could read in full, 99 of 1,356 (7.3%), 95% CI 6.0–8.8%, state a
reservation that binds a crawler whatever its name.**
- 558 of 1,356 (41.2%) block at least one named AI crawler at the root. Of those, 480 of 558
  (86.0%), CI 82.9–88.7%, state nothing that a crawler with a new name would read.
- 777 of 1,356 (57.3%) state no reservation in any channel we read.
- Across all 1,510 sites that answered for `robots.txt`, the agnostic count is at least
  110 of 1,510 (7.3%). Named blockers without an agnostic reservation are at most 621 of 699 (88.8%).
- By country band, agnostic among fully read sites: large countries 74 of 800 (9.2%), medium
  15 of 431 (3.5%), small 10 of 125 (8.0%).
- **Sensitivity to our own rule change (D5).** Under the access rule frozen before collection,
  without the D5 re-scan, the result is 93 of 1,282 (7.3%), CI 6.0–8.8%, fully read sites with an
  agnostic reservation, and 0 contradictions.

**Channels.**
- TDMRep is on 71 of 1,356 (5.2%), CI 4.2–6.6%. For 58 of the 71 it is only in a header or a
  `<meta>` element (meta 41, header 22, file 13). 53 of 192 fully read French sites (27.6%) use it.
- Content-Signal `ai-train=no` appears on 18 sites. The IETF `train-ai=n` appears on 0.
- 17 sites send `Content-Usage: ai=n`. That is the AI-training label of draft-ietf-aipref-vocab-01;
  the current draft dropped it, so parsers must ignore it. Read as a training reservation, it would
  raise the agnostic share to 116 of 1,356 (8.6%).
- Contradictions: 2 contradictions among the 1,356 under the current rule, 0 under the frozen
  rule. Both are Corriere della Sera sites, which were read only in the D5 re-scan. Each sends
  Content-Signal `ai-train=yes` together with a TDMRep `<meta>` reservation.
- 218 of 1,510 (14.4%) write a reservation or a general prohibition in `robots.txt` comments,
  which an RFC 9309 parser discards.

**Access, and what we got wrong.** For 154 sites we read `robots.txt` only, because a deliberately
conservative detector flags their comments as a general prohibition of automated access. The
study broke its own access rule five times; every breach is declared and its data deleted:
- D0: the scouting pilot.
- D1: 7 requests to a host before its `robots.txt`.
- D2: 245 requests to 92 sites.
- D4: 3 requests to one site.
- D7: 72 requests to 24 sites.

The D7 requests were sent in a re-scan (D5) made after collection, after the study's coordinating AI agent changed
the rule for what counts as a prohibition. The study's instructions misclassified the 23 Mediahuis
sites' notice as purpose-specific. EasyxLab's lab-wide rule (3 October 2026) treats `robots.txt` as
binding at the legal minimum. S16 deliberately keeps a stricter rule, because its subject is those
reservations.

**Detector audits (all by AI agents).**
- Author's own sample, detectors v1/v2: the reservation detector was right on 54 of 54 flags; the
  v2 prohibition detector was right on 35 of 62.
- First independent reviewer, v1/v2, 44 other sites: prohibition right on 15 of 21 flags and found
  15 of 15; reservation right on 20 of 20 flags and found 20 of 21.
- Re-reviewer, v3, 43 further sites: prohibition 15 of 15 in the sample, but about 84% recall
  (130 of 154) once the 24 D7 misses are counted; reservation 15 of 16.
- v4 changes exactly those two failure modes. No audit of v4 is claimed.

**Providers.** We could read the crawler documentation of 8 of 14 providers on 2026-10-03; all 8
name robots.txt. None names TDMRep, Content-Signal, Content-Usage or `noai`.

Per-site results state what each site's files say. They are not an assessment of the site: the
obligation is on AI providers. The checker is `scripts/optout_check.py <domain>`, which may become
the free tool `optout-lint`.

## Limitations and deviations

- **Partial reading.** 154 of 1,510 sites were read on `robots.txt` alone. Their TDMRep, headers
  and `<meta>` are unknown, so they are classed `*_robots_only_partial`. Over all sites, agnostic and
  TDMRep counts are therefore minima, and the "named bots only" share is a maximum.
  - The headline uses the 1,356 fully read sites, the frame on 2026-10-03, not "the EU press".
  - On 12 of those sites the home page itself was not observed (timeout, error, or disallowed).
- **D0 (breach).** Before the study, a scouting pilot read the home pages of up to 14 hosts whose
  comments prohibit robots. Records deleted.
- **D1 (breach).** 7 requests reached a sign-on host through a `robots.txt` redirect before its
  own `robots.txt` was read (a 404). The code now checks every cross-host hop.
- **D2 (breach).** Detector v1 missed general prohibitions written around a domain name.
  - 92 such sites had received 245 requests beyond `robots.txt`.
  - Their data and the requests' response statuses were deleted; URL and time are kept.
- **D3.** The main scan's log recorded completion times, so it cannot show the one-second pacing
  that the code enforces. The re-scan log records start times and shows no gap under 1 s.
- **D4 (breach).** actu.fr's list-style prohibition was missed, and 3 requests read it. Data deleted.
- **D5 (rule change after collection).** On the decision of the study's coordinating AI agent, detector v3 stopped
  treating inline comments on one agent's rule, section labels and purpose-specific notices as
  prohibitions. The 98 sites it freed were re-read on 2026-10-03 at 11:55:54–11:56:18 UTC. The
  re-scan also fetched the `robots.txt` of one redirect target. Figures that depend on D5 have the
  frozen-rule sensitivity beside them.
- **D6.** 22 official gazettes and public-sector publishers were excluded under the frozen rule E7
  (frame 1,533 → 1,511).
- **D7 (breach).** In D5, 24 of the freed sites carry a general prohibition with an open clause:
  - the 23 Mediahuis sites ("… whether for machine learning or artificial intelligence purposes
    or otherwise");
  - fd.nl, whose list of prohibited uses is open-ended.
  - The study's instructions had wrongly classed the Mediahuis notice as purpose-specific.
  - The re-scan sent them 96 requests, 72 beyond `robots.txt`. Data and statuses were deleted.
  - Detector v4 classes such notices as general.
- **Other limits.** We read only the home page. Channels we did not read: `ai.txt` pointers in
  comments, the `notdm` directive and Content-Signal `use=`. The frame depends on Wikidata and
  Chrome popularity, and we give no country shares below n = 30. The figures are a snapshot. Whether
  a channel is an "appropriate manner" under Art. 4(3) is for courts to decide.

## Automation and review

AI agents did the whole study:
- A scouting agent proposed it after a pilot.
- A coordinating agent selected it, verified the legal quotes and decided the D5 and D7 rules.
- The builder agent wrote the code, built the frame, ran the collection and re-scan, labelled its
  own audit sample, analysed the data and wrote the text. It also found D2 and D3.

An independent AI reviewer re-computed every figure and re-read 40 sites. It found D4, D6 and the
detector errors behind D5. A second independent AI reviewer audited v3 and found D7.
`scripts/check_headline.py` checks a list of headline phrases against `data/` (see
`VERIFICATION.md` for what it does and does not check).

## Contents

| file | |
|---|---|
| `METHOD.md` | sources, frame, access rules, channels, frozen classification, audit plan, deviations D0–D7 |
| `VERIFICATION.md` | what `check_headline.py` checks, and how to recompute each figure by hand |
| `run.sh` | rebuilds every figure from `data/`, runs the tests and the headline check (offline) |
| `scripts/optout_check.py` | the per-site checker: `python3 scripts/optout_check.py example.org` → JSON |
| `scripts/politefetch.py` | the only HTTP helper: robots.txt first, natural-language prohibition stop, 1 req/s per host |
| `scripts/robots9309.py` | RFC 9309 parser, copied from EasyxLab study S8 |
| `scripts/nlcomments.py` | comment detectors v1–v4 (reservations; general prohibitions) |
| `scripts/build_population.py` | Wikidata (via QLever) × CrUX country lists → `data/frame.csv` |
| `scripts/scan.py`, `scripts/apply_detectors.py`, `scripts/aggregate.py` | collection and re-scan, deviations D2/D4/D5/D7, aggregates |
| `scripts/comment_audit.py`, `scripts/draw_audit_sample.py` | the authors' detector audit (labels in the code) |
| `scripts/fetch_sources.py`, `scripts/providers_panel.py`, `scripts/prior_work_search.py` | legal, technical, provider and prior-work documents |
| `scripts/audit_requests.py` | checks the request log against the access rules |
| `scripts/check_headline.py` | checks a fixed list of headline phrases (README abstract; paper when present) against `data/`, with number boundaries |
| `tests/test_parsers.py` | unit tests (`python3 -m unittest discover -s tests`) |
| `data/frame.csv`, `data/exclusions.csv`, `data/frame_meta.json` | frame (1 row per host), every excluded Wikidata row with its rule, sizes |
| `data/records.csv` | one row per site: each channel and the verdict |
| `data/summary.json`, `data/by_country.csv` | aggregates with Wilson 95% intervals |
| `data/comment_audit.csv`, `data/comment_audit_summary.json`, `data/independent_audit_v2.json`, `data/independent_audit_v3.json` | detector audits (no comment text) |
| `data/d5_status_changes.csv`, `data/deviation_d2.json`, `data/deviation_d4.json`, `data/deviation_d5.json`, `data/deviation_d7.json`, `data/request_audit.json` | deviations and request-log audit |
| `data/providers_panel.csv`, `data/sources_manifest.csv`, `data/prior_work_search.json` | provider documents; every document fetched (URL, time, sha256); prior-work queries |

## Licences

- Code: Apache-2.0. Data and text: CC BY 4.0 (repository `LICENSE` and `LICENSE-DATA`).
- `data/frame.csv` contains Wikidata identifiers and labels (CC0) and each host's Chrome UX Report
  rank bucket. Google's CrUX methodology page (read 2026-10-03) says: "CrUX datasets by Google are
  licensed under a Creative Commons Attribution 4.0 International License". We used the August 2026
  country lists as cached in `github.com/zakird/crux-top-lists`, which declares no licence of its
  own. Attribution: Chrome UX Report, Google.
- `data/providers_panel.csv` quotes at most 220 characters of each provider document as evidence.
  `data/d5_status_changes.csv` quotes at most 120 characters of the detector evidence from each
  site's public `robots.txt`. No `robots.txt` bodies, page content or third-party documents are
  published.
