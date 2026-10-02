# S9 — Protocol: verified crawlers over time, and whether they respect `Disallow`

EasyxLab · study S9 · **protocol written on 2026-10-02/03 and registered by its first commit,
before any data of the prospective period exists and before any change is deployed.** Later changes
are listed, dated, in §13 ("Deviations"); nothing above §13 is edited after registration except to
fix typos.

Companion of study S2 (`../s2-spoofed-ai-crawlers/`), whose verification code S9 imports
unchanged. Same three sites, same anonymised labels: Site A (a calculator site), Sites B and C
(niche tool sites launched in September 2026). All times UTC.

## 1. Research questions

- **RQ1 (longitudinal).** Week by week, what share of requests that claim to be a search or AI
  crawler is spoofed, per site, operator, crawler and purpose (training, search index, user fetch,
  search engine)? Does it drift, and does it rise as the two new sites age?
- **RQ2 (longitudinal).** How does the *verified* crawler volume of each operator change over the
  weeks, and which new crawler names appear?
- **RQ3 (trap).** Do verified crawlers whose operators say they obey `robots.txt` actually stay out
  of a path that `robots.txt` disallows, when the path is linked from every page of the site?
- **RQ4 (trap).** Do user-initiated fetchers behave as their operators say? Some operators say these
  fetchers may ignore `robots.txt` (OpenAI, Perplexity, Google, Amazon); Anthropic and Mistral say
  site owners can control theirs through `robots.txt` (§4). The design labels the two separately.
  **Not tested in this run**: testing it needs manual sessions with each assistant, which were
  descoped before registration (§6, H2); passive observations are reported descriptively.
- **RQ5 (trap).** Who reads `Disallow` lines as a map: which agents request a path whose only
  public mention is the `Disallow` line itself?

## 2. Sites and data

| site | role in S9 | origin log available since | change made for S9 |
|---|---|---|---|
| Site A | longitudinal + robots-only arm | 2026-07-27 | one `Disallow` line in `robots.txt` (no HTML change) |
| Site B | longitudinal + full trap | 2026-09-24 | `Disallow` lines, two small pages served by the web server, one footer line |
| Site C | longitudinal + full trap | 2026-09-26 | same as Site B |

Stack (unchanged from S2): Cloudflare (free plan) → reverse proxy → nginx in a container; nginx
logs the real client IP from `CF-Connecting-IP`; the log lives on a host volume that survives
container rebuilds and deploys. A monthly rotation was installed on the host on 2026-10-01/02
(copy and truncate on the 1st of each month at 03:41 UTC, first run 2026-11-01, 12 months kept); the
collector reads the current and the rotated files.

Two views per site and week: the **origin log** (complete for what reaches nginx) and the
**Cloudflare edge** (GraphQL Analytics, sampled, includes requests answered or blocked at the edge).

Site A runs its own experiment with monthly evaluation points in November and December 2026. S9
makes no HTML change there. The only change is one `Disallow` line for a path that does not exist, is not linked anywhere
and is not a prefix of any existing URL (checked against every URL of the live sitemaps on
2026-10-02, and by an evaluator that compares the verdict of every known URL under the old and new
`robots.txt` with a longest-match RFC 9309 parser and with a first-match parser: no verdict changes).

## 3. Trap design

### 3.1 Paths

Each site gets a folder whose name is a random string, different on each site (so a crawler that
learned the folder on one site and tries it on another is detectable). Under it, up to three
**arms**, each a random path segment: nothing in a path says which arm it is, so neither a crawler nor
an agent that reasons about URLs gets a hint, and the paths cannot be found by searching for words.
The arms are:

| arm | in `robots.txt` | linked from the site | served as | sites |
|---|---|---|---|---|
| `allowed` (control) | not mentioned, so allowed by `Allow: /` | yes, footer of every page | the study page | B, C |
| `disallowed` | `Disallow:` | yes, footer of every page, same markup as the control | the study page | B, C |
| `robots-only` | `Disallow:` | **no**: its only public mention is the `Disallow` line | the study page (B, C); a normal 404 (A) | A, B, C |

The exact paths, and the exact texts served on the sites (study page, footer line, `robots.txt`
comments), are **not published, during or after the study**: they would let anyone find the sites
(archived copies of `robots.txt` and of pages are searchable) and undo the anonymisation, and during
the study they would let third parties link to the paths and contaminate the arms. They are committed
by hash; the files will be shown to a reviewer on request so the commitment can be checked:

| private file | SHA-256 at registration |
|---|---|
| trap paths (site label, arm, path) | `09147408f2bba9886aadc5716f072d52db448b7555fd25a225a516564de341e0` |
| served texts (study page HTML, footer lines, `robots.txt` comments) | `d7ed1199a1bc58da23f6c3653fd7c9637e48ec506e45c78e7db0f3bad8138cd3` |

### 3.2 `robots.txt`

All three sites have a single `User-agent: *` group today (no group names any crawler) and
Cloudflare's managed `robots.txt` is off on all three zones (read through the API on 2026-10-02).
The `Disallow` lines go **inside that group and before `Allow: /`**. Order does not matter to
longest-match parsers (RFC 9309, Google, Bing), but older first-match parsers (the 1996 draft, and
Python's `urllib.robotparser`) would let `Allow: /` win if it came first; with the `Disallow` lines
first, both families reach the same verdict.

**No per-crawler groups.** RFC 9309 and Google say a crawler obeys only the most specific group
that names it ("Only one group is valid for a particular crawler"). A named group would therefore
hide from that crawler everything in `*`, including the sites' usage policy (`Content-Signal`), and
Site C's own test suite forbids named groups that do not `Disallow: /` for exactly that reason.
Operators also resolve groups in non-standard ways (Apple: "If robots instructions don't mention
Applebot but mention Googlebot, the Apple robot will follow Googlebot instructions"; Amazon:
Amzn-SearchBot follows "the robots.txt directives given to other search bots"). Testing group
resolution would turn S9 into a parser study confounded with compliance. It is left for a separate
protocol.

### 3.3 Discovery and the control

A crawler that never fetches the disallowed page might be complying, or might simply never have
found the link. The **allowed control** separates the two: it is linked from the same footer, with
the same markup (plain `<a>`, no `rel`), and its only difference is that `robots.txt` allows it.
The two footer links carry neutral, numbered labels that say nothing about which is which; on Site B
the first link is the control, on Site C the second is (counterbalanced, in case a crawler follows
only the first of two links). A crawler that fetches the control but never the disallowed page is evidence of compliance;
a crawler that fetches neither has not been tested.

### 3.4 The study page

One honest, static page, the **same bytes for every visitor and every User-Agent** (no cloaking),
served by nginx with `Cache-Control: no-store` (so every request reaches the origin log) and
`X-Robots-Tag: noindex`. English text, no scripts, no ads, no analytics, one link back to the home
page, nothing a crawler can get stuck in. It says, in plain words, that the page is part of a
measurement of how automated agents follow `robots.txt`; that some addresses in its folder are listed
as disallowed in the site's `robots.txt` and some are not; that every visitor receives the same page,
which contains nothing else; and that no data is collected beyond the site's normal server log. It
**names no organisation, person or project and links to no other site**, so it does not tie the site
to this study (the sites are anonymised). The `robots.txt` comments that accompany the `Disallow`
lines are equally neutral. Exact texts: private file above.

### 3.5 Deployment in two phases

1. **Phase R** (`robots.txt` only, all three sites). The time `T_R` of each site is the first moment
   a plain (non-cache-busted) request to `/robots.txt` at the Cloudflare edge returns the new file,
   after purging the edge copy. Recording the verification time, not the commit time, makes `T_R`
   slightly late, which can only *reduce* the number of requests counted as violations.
2. **Phase L** (study pages + footer links, Sites B and C), no earlier than `T_R + 72 h`, at `T_L`.

Because the disallowed path appears in `robots.txt` at least 72 hours before any link to it exists,
any crawler that learns about the page from the link has had more than three times the 24-hour
caching limit to see the `Disallow`.

## 4. What the operators say (literal text, retrieved with `curl` on 2026-10-02)

| crawler(s) | operator statement (verbatim) | class used in S9 |
|---|---|---|
| (all) | RFC 9309 §2.4: "Crawlers SHOULD NOT use the cached version for more than 24 hours, unless the robots.txt file is unreachable." | grace basis |
| Googlebot and other common crawlers | "They always obey robots.txt rules when crawling automatically." Caching: "Google generally caches the contents of robots.txt file for up to 24 hours, but may cache it longer in situations where refreshing the cached version isn't possible (for example, due to timeouts or 5xx errors)." | obeys |
| AdsBot-Google, Mediapartners-Google, APIs-Google | "The global user agent ( * ) is ignored." | ignores `*` (exempt) |
| Google-Safety | "The Google-Safety user agent ignores robots.txt rules." | ignores (exempt) |
| Google user-triggered fetchers | "Because the fetch was requested by a user, these fetchers generally ignore robots.txt rules." | may ignore |
| GPTBot, OAI-SearchBot | "OpenAI uses OAI-SearchBot and GPTBot robots.txt tags to enable webmasters to manage how their sites and content work with AI." "…it can take ~24 hours from a site's robots.txt update for our systems to adjust." | obeys |
| ChatGPT-User | "Because these actions are initiated by a user, robots.txt rules may not apply." | may ignore |
| ClaudeBot, Claude-SearchBot, Claude-User | "Anthropic's Bots respect “do not crawl” signals by honoring industry standard directives in robots.txt." For Claude-User: "Claude-User allows site owners to control which sites can be accessed through these user-initiated requests. Disabling Claude-User on your site prevents our system from retrieving your content in response to a user query". | obeys (including Claude-User) |
| PerplexityBot | "we recommend allowing PerplexityBot in your site's robots.txt file"; "it may take up to 24 hours for our systems to reflect changes." | obeys |
| Perplexity-User | "Since a user requested the fetch, this fetcher generally ignores robots.txt rules." | may ignore |
| Applebot | "Applebot respects standard robots.txt directives in general search crawls that are targeted at Applebot." | obeys |
| CCBot | "To prevent Common Crawl from crawling your website, include the following in your robots.txt : User-agent: CCBot Disallow: /" | obeys |
| MistralAI-User | "MistralAI-User governs which sites these user requests can be made to." | obeys |
| DuckAssistBot | "…the change will take effect after 72 hours and DuckAssistBot will stop crawling your site." | obeys (72 h grace) |
| Amazonbot, Amzn-SearchBot | "Automated crawling from these listed user agents respects the Robots Exclusion Protocol… They will fetch host-level robots.txt files or use a cached copy from the last 30 days." | obeys (30-day grace; not verifiable, §5) |
| Amzn-User | "Because actions taken by Amzn-User can be initiated by a user, it may not follow all robots.txt directives." | may ignore |
| Bingbot, YandexBot, DuckDuckBot, Meta, Bytespider | no statement retrieved as text on 2026-10-02 (pages rendered client-side, refused, or silent) | no stated policy (exploratory only) |

Two corrections to the brief this study started from: not all user-initiated fetchers are declared
exempt (Anthropic and Mistral say theirs are controlled by `robots.txt`), and some *non*-user
crawlers are declared exempt (Google's ads crawlers ignore `*` by design). S9 judges each crawler
against its own operator's statement, not against a generic rule.

## 5. Verification and classification of each request

- **Verification** is S2's, imported unchanged (`ai_bot_verify.py`, version and SHA-256 recorded in
  every weekly manifest): published IP-range JSON files and forward-confirmed reverse DNS; verdicts
  `verified`, `spoofed`, `unverifiable`, `indeterminate`. Amazon's lists are not machine-readable,
  so Amazon is always `indeterminate` and cannot test any hypothesis.
- **Ranges are applied as of the week.** The prospective collector runs every Monday for the ISO
  week just ended, with range files downloaded that day (S2 applied 2 October's lists to 68 days of
  history; S9 removes that limitation for the prospective weeks). Weeks computed more than 8 days
  after they ended are marked `retroactive` and are exploratory.
- **Trap arm** of a request: exact path match (query string ignored, case-sensitive, trailing slash
  required, as in `robots.txt` matching). A request under the prefix that matches no arm (for
  example the disallowed path without its trailing slash, which the `Disallow` line does not cover)
  is `other-under-prefix` and is never a violation.
- **Phase** of a request to a disallowed arm: `pre` (before `T_R`), `grace` (from `T_R` to
  `T_R + grace`), `active`, `post` (after removal). **Grace** = 24 h (RFC 9309, Google, OpenAI,
  Perplexity), or the operator's own longer figure when it states one (DuckDuckGo 72 h, Amazon 30
  days). The allowed control is `active` from `T_L`.
- **Label** of an active-phase request to a disallowed arm:

| request | label |
|---|---|
| verified, operator says it obeys | **violation** |
| verified, operator says it may ignore `robots.txt` (user fetchers of OpenAI, Perplexity, Google, Amazon) | permitted-user-fetch |
| verified, operator says it ignores `*` (Google ads/APIs/safety crawlers) | permitted-ignores-wildcard |
| verified, no stated policy | fetch-no-stated-policy (exploratory) |
| claims a crawler name, not verified | unverified-claim |
| no known crawler name | undeclared (by client class: browser-like, HTTP library, other bot, empty) |

- **Exposure.** A crawler is *tested on the linked arm* of a site if it made at least one verified
  request to the allowed control after `T_L`; *tested on the robots-only arm* if it made at least one
  verified request to `/robots.txt` of that site after `T_R` (origin or edge). Both are reported per
  site and operator.
- **"Respects Disallow"** for a crawler: tested on at least one arm and **zero** verified
  active-phase requests to any disallowed arm on any site. **"Violates"**: at least one. **"Not
  tested"**: neither. With `n` control fetches and zero violations, the exact 95% upper bound on the
  per-opportunity violation probability, `1 − 0.05^(1/n)`, is reported.
- **Our own requests** to the studied sites (weekly live checks, deploy verification) use a
  **neutral User-Agent** that does not name the lab or the study, with a random marker kept in the
  private configuration; they come from known monitoring addresses, and both the marker and the
  addresses are excluded before counting. Requests that never touch the sites (Cloudflare's API, the
  operators' IP lists, Team Cymru) are unaffected. A few dozen design-phase requests on 2026-10-02 used
  a User-Agent naming the lab (§13); they are excluded too and fall before any observation window. Requests to the trap prefix are excluded from the
  longitudinal tables (RQ1–RQ2) and analysed only in the trap tables.

## 6. Hypotheses (fixed 2026-10-02)

**H1 — Stated compliance holds.** For each operator that says its automated crawlers or its user
fetcher obey `robots.txt` (Google common crawlers; OpenAI GPTBot and OAI-SearchBot; Anthropic
ClaudeBot, Claude-SearchBot and Claude-User; Perplexity PerplexityBot; Apple Applebot; Common Crawl
CCBot; Mistral; DuckDuckGo DuckAssistBot), the number of verified active-phase requests to
disallowed arms is zero.
*Falsified for an operator* by one or more such requests (each reported with crawler, arm, site
label and hours after `T_R`; never the IP). *Not tested* for an operator with no exposure (§5).

**H2 — User fetchers behave as declared. Not tested in this run** (it requires manual sessions with
each assistant; descoped before registration, 2026-10-03). The prediction is recorded so that a later
run cannot be fitted to its results: asked by a person to open each study page, ChatGPT-User and
Perplexity-User would fetch the disallowed page; Claude-User and MistralAI-User would fetch the allowed
page and not the disallowed one. If sessions are ever run, their results are **exploratory only**.
Verified user-fetcher requests seen passively are reported descriptively with their labels (§5).

**H3 — Impostors ignore `Disallow`.** Among active-phase requests to the two linked arms on Sites B
and C, the share going to the disallowed arm is higher for unverified crawler claims than for
verified crawlers of operators that say they obey.
*Test:* Fisher's exact test on the 2-by-2 table (rows: verified-obeying, unverified-claim; columns:
allowed, disallowed), one-sided, α = 0.05. *Supported* if p ≤ 0.05 in that direction; *falsified* if the
unverified share is not higher; *insufficient* if there are fewer than 10 unverified-claim requests
to the linked arms.

**H4 — No trend on the established site.** On Site A, the weekly spoofed share of testable claims
(origin log, prospective weeks) has no monotone trend: two-sided Mann–Kendall p > 0.05. Sen's slope
is reported with it. A non-significant result over 8–12 weeks is weak evidence and will be
described as such. *Falsified* by p ≤ 0.05.

**H5 — Spoofing grows with exposure on the new sites.** On Sites B and C (launched in September), the
spoofed share of testable claims rises over the prospective weeks. *Supported* if at least one of
the two sites has a one-sided Mann–Kendall p ≤ 0.05 for an increase **and** the pooled B+C share of
the last four prospective weeks exceeds that of the first four by at least 10 percentage points.
*Falsified* if both sites have Mann–Kendall S ≤ 0. Otherwise *inconclusive*. Spoofed volume (not
only share) and the edge view are reported alongside, because nginx does not log a list of scanner
paths (S2 §6).

**H6 — Verified crawling grows on the new sites.** The weekly number of verified crawler requests
rises on Site B and on Site C (one-sided Mann–Kendall p ≤ 0.05 for each site, evaluated
separately).

RQ2's new crawler names, the range-file changes, the edge/origin ratio and the robots-only arm (RQ5)
are **exploratory**: described, not tested.

## 7. Procedure

### 7.1 Weekly collection (all sites)

A collector runs every Monday at 06:05 Europe/Madrid on the automation server for the ISO week just
ended (Monday 00:00 to Monday 00:00 UTC). It streams the origin logs over SSH (raw lines are held in
memory only, never written to disk), runs S2's verifier on the week, adds the trap tables, pulls the
edge view for the same week from Cloudflare, checks that the live `robots.txt`, study pages, footer
links and Cloudflare bot settings are still as deployed, and writes **aggregates only** to
`data/weekly/<YYYY-Www>/<site>/`. A week already written is never overwritten (the first, as-of-week
computation is canonical); the run is idempotent. A deviation (a `Disallow` line missing, a study
page not served, a footer link gone, Cloudflare blocking AI bots or managing `robots.txt`) makes the
run exit with status 2 and is logged in §13 with its dates; affected days are excluded from the trap
analysis.

### 7.2 Backfill

The weeks before the prospective period (Site A from 2026-W31, Sites B and C from 2026-W39) are
computed once with the range files of the day they are computed, marked `retroactive`, and used only
descriptively.

### 7.3 Active arm: not run

Descoped before registration (operator time). The collector can still attribute a fetch to a manual
session if one is ever recorded in the private configuration (15-minute window after its start), but
any such result is exploratory (H2).

## 8. Measures

Per site, ISO week, crawler, operator, purpose and verdict: requests and unique sources (counted in
memory; only the count is written). Verified/spoofed shares with Wilson 95% intervals. Behaviour of
non-verified sources (credential probing, multiple identities) as in S2. Edge counts (raw sampled
rows) and Cloudflare security actions. Trap: requests and unique sources per arm, phase, label,
crawler and verdict; exposure per crawler; robots-only arm requests by client class. Weekly manifest:
window, run time, retroactive flag, S2 module version and hash, every range file's URL, creation time,
prefix count and SHA-256.

## 9. Analysis plan

- Series: one row per site and week (prospective weeks for H4–H6), the share being
  `spoofed / (verified + spoofed)`; weeks with fewer than 20 testable claims on a site are reported
  but excluded from that site's trend tests.
- Trend tests: Mann–Kendall S with the exact null distribution when there are no ties (n ≤ 50), normal
  approximation with tie correction otherwise; Sen's slope.
- Trap: pooled over the observation period; per crawler and per operator; Fisher's exact test for H3;
  zero-event upper bounds for H1.
- No other hypothesis tests are planned. Everything else is descriptive. All code is in `scripts/`
  (`s9_analyse.py` applies the rules above mechanically and writes the verdict of each hypothesis).

## 10. Stopping rule

- **Longitudinal (H4–H6):** 12 prospective ISO weeks, 2026-W41 to 2026-W52. Early stop only for a
  §11 harm condition; then the available weeks are analysed if there are at least 8, and only
  described otherwise.
- **Trap (H1, H3):** observation starts at `T_L`. Checkpoint at the end of the 8th complete ISO week
  after `T_L`: if at least 3 operators are *tested on the linked arm* and the allowed controls have
  received at least 10 verified requests in total, the trap observation ends there; otherwise it
  continues to the end of the 12th complete week. Hard end on 2027-01-15 in any case.
- **Removal:** the footer links first (end of observation), then, 7 days later, the study pages and
  the `Disallow` lines (requests in those 7 days are reported as `post`).

## 11. Threats to validity

- **Discovery is not compliance.** Handled with the allowed control and the exposure rule; a crawler
  that never fetches the control is not tested, whatever its record on the disallowed page.
- **`robots.txt` caching**, by crawlers and by the CDN. The edge copy is purged at deploy and `T_R`
  is the verified edge time; grace windows follow each operator's own figure; the linked arm starts
  at least 72 h after `T_R`. Amazon's 30-day cache is respected but Amazon cannot be verified.
- **Verification errors.** IP lists change (applied as of the week); Anthropic publishes one list for
  all its crawlers, so a request from its list carrying the wrong Anthropic name cannot be told apart;
  reverse DNS can fail transiently (`indeterminate`, never `spoofed`).
- **Small sample.** Three small sites of one publisher on one stack. New sites receive little crawling:
  some operators may never be tested. That is reported as "not tested", not as compliance.
- **Interference from automated maintenance.** The sites are edited and redeployed by automated
  routines that are allowed to edit `robots.txt`. Mitigations: tests in each site's build that fail
  if the S9 lines disappear before 2027-01-15, a rule in the routines' shared instructions, and the
  weekly live check (§7.1).
- **CDN settings.** If Cloudflare's AI-bot blocking or managed `robots.txt` were switched on, crawlers
  would be stopped or told something else at the edge. The weekly run reads those settings (read-only)
  and treats a change as a deviation.
- **Logging gaps.** nginx does not log some scanner paths (they get status 444 without a log line); the
  trap paths are not among them. The monthly log rotation copies and truncates the file, which can
  lose the few requests that arrive during the copy, once a month at 03:41 UTC.
- **Header trust.** The client IP comes from `CF-Connecting-IP`, trusted only from the proxy network.
- **Ongoing SEO experiments** on Sites B and C compare page batches with control pages in the same
  window; a footer line on every page affects both groups equally.
- **Reactivity.** The study page and a comment in `robots.txt` say what the paths are for. Automated
  crawlers are not expected to adapt within weeks; a human at an operator could.
- **Contamination by publication.** The paths are never published (§3.1); links from elsewhere to the
  study pages would add discovery routes, and inbound referrers to the trap are reported.
- **Spoofers may never crawl links.** S2 found that impostors mostly probe credential paths, so H3 may
  end `insufficient`; that is an acceptable result.

## 12. Ethics and privacy

- **No deception of people, no cloaking.** The links are visible, plainly labelled, and lead to a page
  that says what it is. Every visitor and every User-Agent gets the same bytes.
- **No harm to crawlers.** One small static page per arm, no link loops, no slow responses, no
  blocking, no altered content, no `Crawl-delay` games. Crawlers that obey `robots.txt` lose nothing.
- **Operators, never individuals.** Results name crawler operators (companies) and network operators
  (autonomous systems); an AS registered to a natural person is withheld, as in S2. No IP address,
  domain name, server or repository name of the studied sites, trap path or served text is ever
  published (§3.1); nothing served on the sites names the lab, the study or the company.
- **Logs stay on the server.** They are streamed into memory for counting; outputs are aggregates
  behind S2's privacy guard (the tool refuses to write if any client IP seen in the input appears in
  the output). The IPs of non-verified sources are sent to Team Cymru's public whois to obtain their AS,
  as in S2. The sites' 12-month log retention is not changed.
- **Before publication**, each operator named as violating its own statement will be offered the
  evidence (crawler, times, paths and its own source addresses) and time to reply; that decision and
  its timing belong to the study coordinator.
- **No active arm** in this run: no assistant is asked to visit the sites on our behalf.

## 13. Deviations and dated events

| date (UTC) | event |
|---|---|
| 2026-10-02 | Protocol drafted. Nothing deployed. During design, the three sites' sitemaps, home pages and `robots.txt` were fetched (a few dozen requests) with a User-Agent naming the lab; they appear only in our own logs, before any observation window, and are excluded by marker. |
| 2026-10-02 | Before registration was committed: every operator quote in §3.2 and §4 checked verbatim against the downloaded page (`data/operator_docs.csv`); the `robots.txt` change evaluated against every known URL of the three sites (0 verdict changes, both parser families); collector validated on 9 past weeks of Site A (one week cross-checked against S2: identical counts). |
| 2026-10-03 | Before registration, on the study coordinator's decisions: H2 descoped (not tested in this run); the served texts (study page, footer line, `robots.txt` comments) made anonymous, with no name of the lab, the study or the company and no outside link; trap paths regenerated as random strings with no meaning (hashes in §3.1 replace the earlier one); our own requests switched to a neutral User-Agent; Site A's single `Disallow` line approved. The `robots.txt` verdict check was re-run on the new paths: 0 changes on any known URL of the three sites. |
