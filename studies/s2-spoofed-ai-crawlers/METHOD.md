# S2 — Method

Study: *Spoofed AI crawlers: how much traffic claiming to be an AI or search bot is real?*
Data collected 2026-10-02. All times UTC.

## 1. Data sources

| source | what it is | window | requests claiming a known bot |
|---|---|---|---|
| origin log, Site A (a calculator site, online since mid-2026) | nginx `access.log` behind Cloudflare → reverse proxy → nginx; real client IP restored from `CF-Connecting-IP` | 2026-07-27 12:45 → 2026-10-02 15:22 (68 calendar days) | 14,637 |
| origin log, Site B (a niche tool site launched in September 2026) | same stack | 2026-09-24 13:45 → 2026-10-02 15:22 (9 calendar days) | 1,481 |
| origin log, Site C (a niche tool site launched in September 2026) | same stack | 2026-09-26 09:02 → 2026-10-02 15:16 (7 calendar days) | 430 |
| Cloudflare edge, the same three zones | GraphQL Analytics `httpRequestsAdaptiveGroups`, grouped by `userAgent, clientIP, clientRequestPath, edgeResponseStatus, securityAction` | 2026-09-02 02:00 → 2026-10-02 (30 d, the plan's retention limit is 4w3d) | 22,864 sampled rows |

The three logs are the complete files present on the server (no rotated copies existed; the
oldest line of each file is the start of logging for that site). Our own monitoring hosts
were excluded by IP before any counting (list kept in `data/raw/`, not published). Sites are
referred to only as `site-a`, `site-b`, `site-c`; the mapping to domains and log files lives in
`private/sites.json` (git-ignored) or in the file named by `$S2_SITES`.

Log format (shared nginx `log_format`, identical on the three sites):
`$remote_addr - [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent" cf_ray=$http_cf_ray`.
The parser also accepts the standard nginx/Apache *combined* format.

**Third-party services.**
- *Operators' IP-range files* (OpenAI, Anthropic, Perplexity, Google, Bing, Apple, Common Crawl, DuckDuckGo,
  Mistral; the URLs are in `scripts/ai_bot_verify.py`): plain HTTPS GET with the User-Agent `ai-bot-verify/0.1.0`,
  one request per file, cached for 24 h. The operators publish them for this check (§3).
- *Team Cymru IP-to-ASN whois* (`whois.cymru.com`, TCP 43), a free public service: its documented bulk mode
  (`begin` / `verbose` / IPs / `end`), one connection per batch of up to 5,000 IPs, for the non-verified IPs only (§6).
- *Cloudflare GraphQL Analytics API*: our own account's API token, our own zones; serial requests, up to three
  attempts 3 s apart.
- *DNS*: reverse and forward lookups through the system resolver.

## 2. Which requests are in scope

A request is in scope when its User-Agent contains the token of a crawler in the registry
(`scripts/ai_bot_verify.py`, `BOTS`). Matching is case-insensitive, left-bounded, and ordered
from specific to generic (e.g. `OAI-SearchBot` before anything containing `SearchBot`).
23 canonical bots from 13 operators; Google's crawlers are split into `Googlebot` (common
crawlers), `Google-special` (AdsBot, Mediapartners…) and `Google-fetcher` (user-triggered).

## 3. Verification: one verdict per request

Each operator's own documentation was downloaded with curl on 2026-10-02 and the method it
describes was implemented literally. Quotes (verbatim):

| operator | method | documentation and literal text |
|---|---|---|
| OpenAI (GPTBot, OAI-SearchBot, ChatGPT-User) | published JSON ranges, one per bot | platform.openai.com/docs/bots — "Published IP addresses: https://openai.com/gptbot.json"; "…allowing requests from our published IP ranges below." |
| Anthropic (ClaudeBot, Claude-User, Claude-SearchBot) | one JSON for all bots | support.claude.com/en/articles/8896518 — "If a crawler has a source IP address on this list, it indicates that the crawler is coming from Anthropic." The link points to `https://claude.com/crawling/bots.json` (creationTime 2026-08-18, 26 prefixes). |
| Perplexity | JSON per bot | docs.perplexity.ai/guides/bots — "Always use the most current IP ranges from the official JSON endpoints." |
| Google | JSON (+ reverse DNS) | developers.google.com/search/docs/crawling-indexing/google-common-crawlers — "The common crawlers generally crawl from the IP ranges published in the common-crawlers.json object, and the reverse DNS mask of their hostname matches crawl-\*\*\*-\*\*\*-\*\*\*-\*\*\*.googlebot.com…"; "Caution: The HTTP user agent string can be spoofed." |
| Google-Extended | **never sent as a UA** | same page — "Google-Extended doesn't have a separate HTTP request user agent string. Crawling is done with existing Google user agent strings; the robots.txt user-agent token is used in a control capacity." |
| Apple (Applebot) | JSON + FCrDNS | support.apple.com/en-us/119829 — "Another way is to match the IP address with a CIDR prefix contained in the following JSON file: Applebot IP CIDRs." |
| Applebot-Extended | **never sent as a UA** | same page — "Applebot-Extended does not crawl webpages." |
| Common Crawl (CCBot) | JSON + FCrDNS | commoncrawl.org/ccbot — "These IP ranges (v4 and v6) are also provided as JSON at https://index.commoncrawl.org/ccbot.json." |
| Microsoft (Bingbot) | JSON `bing.com/toolbox/bingbot.json` + FCrDNS `*.search.msn.com` | the help page is rendered client-side and returned no text to curl; the JSON itself is served by bing.com. |
| DuckDuckGo | JSON | duckduckgo.com/duckduckgo-help-pages/results/duckduckbot — "…originates from these IP addresses (also available in JSON at https://duckduckgo.com/duckduckbot.json)". |
| Mistral | JSON | docs.mistral.ai/robots — "All published IP addresses: MistralAI-User IP addresses" (→ mistralai-user-ips.json). |
| Yandex | FCrDNS | yandex.com/support/webmaster/robot-workings/check-yandex-robots.html — "You can check the authenticity of a robot using a reverse DNS lookup." |
| Amazon (Amazonbot, Amzn-SearchBot, Amzn-User) | lists exist but are rendered by JavaScript | developer.amazon.com/amazonbot — "Published IP Addresses: https://developer.amazon.com/amazonbot/ip-addresses/". Not machine-readable to a plain HTTP client → **indeterminate**. |
| ByteDance (Bytespider) | none found | → **unverifiable** |
| Meta (meta-externalagent) | page mentions "user agent strings or the IP addresses (more secure)" but the IP list was not retrievable as text | → **unverifiable** |

Verdicts:

- **verified**: IP inside one of the operator's published prefixes, or passes forward-confirmed
  reverse DNS (PTR ends in a documented suffix AND that name resolves back to the same IP).
- **spoofed**: the operator publishes a method and the IP fails it (not in any of its lists
  and, where rDNS is documented, PTR missing/foreign or forward lookup mismatched); or the UA
  carries a robots-only token (Google-Extended, Applebot-Extended).
- **unverifiable**: the operator publishes no method (Bytespider, Meta), or the UA is a
  client-side tool that by design runs on the end user's machine (`claude-code`).
- **indeterminate**: a method exists but could not be applied (Amazon's JS-only lists; DNS
  timeouts; a range file that failed to download — none failed in this run).

For Google, a request claiming any Google crawler is verified against the union of Google's
five published files (common, special, user-triggered ×3), plus FCrDNS to `googlebot.com` /
`google.com`.

The range files are those current on 2026-10-02 (metadata and hashes in
`data/range_files_used.csv`). They were applied retroactively to the whole window; see
limitations.

## 4. What is measured for each (bot, verdict)

All computed in memory per IP and published only as counts:

- requests, unique IPs, median requests per IP;
- IPs whose first request was `/robots.txt`, IPs that fetched it at all;
- path category of each request: `robots.txt`, `llms.txt`, `sitemap`, `vuln-probe`
  (regex of credential/config/admin paths: `.env`, `.git`, `wp-`, `config.json`,
  `secrets.*`, `service-account*.json`, `terraform.tfstate`, `/proc/self/environ`…), `asset`,
  `home`, `page`. Normalised paths (query string dropped; numbers, hex, UUIDs and IP-like
  segments replaced by placeholders; kept only if seen ≥ 2 times) are published **only for the
  `vuln-probe` category**; every other request is grouped as `(site page)`, because a site's own
  paths would identify it;
- status class, hour of day, day;
- behaviour class of each source: *probe* (asked for ≥ 1 vuln-probe path), *content-only*,
  and *multi-operator* (the same IP claimed to be bots of ≥ 2 different operators in the window);
- ASN, AS name, country and a **heuristic** network type for every non-verified IP, from Team
  Cymru's bulk IP-to-ASN whois (`whois.cymru.com:43`). Network type is assigned from keywords in
  the registered AS name (cloud/hosting, vpn/proxy, mobile, isp/residential, unknown); every AS
  is listed with its class in `data/spoofing_by_asn.csv` so the classification can be audited;
- a soft "operator AS" signal for unverifiable bots: share of their requests coming from an AS
  registered to the operator (e.g. `FACEBOOK` for meta-externalagent). This is **not**
  verification — shared clouds are rentable by anyone.

## 5. Edge (Cloudflare) pass

`scripts/cf_declared_bots.py` pulls every request group for each zone and day, unfiltered,
and applies the same matcher and verdict function. Two traps found and fixed during the study:

1. `userAgent_like` in Cloudflare's GraphQL is **case-sensitive**: a `%googlebot%` filter
   returned 0 rows for `Googlebot` while `%gptbot%` "worked" only because GPTBot's UA contains the
   lowercase URL `openai.com/gptbot`. A first run with server-side filters silently dropped
   Googlebot, ChatGPT-User, OAI-SearchBot, CCBot, Bytespider and Mistral. The final run fetches
   unfiltered groups (splitting windows at the 10,000-group limit) and matches locally.
2. Free-plan zones refuse `clientAsn`, `clientASNDescription` and `botScore`; ASN is therefore
   looked up via Team Cymru as in the log pass.

Adaptive sampling: 11,064 of the 20,648 bot rows for Site A came from groups with
`sampleInterval > 1`. Edge figures are raw sampled counts (a lower bound); multiplying by the
sample interval gives a much larger, unreliable upper bound, so it is not used.

## 6. Privacy

- Logs never leave the server except into `data/raw/` (git-ignored) on the analyst's machine.
- No IP address is written to `data/`, the report or the scripts' outputs. `ai-bot-verify`
  refuses to write if any client IP seen in the input appears in its output (`assert_no_ips`).
  An independent check over all 7,781 client IPs in the raw logs found none in any published file.
- Only aggregates by bot, verdict, ASN, network type, path category and hour are published.
- User-Agent strings are published only when seen ≥ 3 times; normalised paths only when ≥ 2.
- One spoofing AS is registered to a natural person (per its whois record, read by an AI agent);
  its number, name and country are not published and it appears as "a small AS registered to an
  individual". The list of withheld ASNs is private (`private/withhold-asns.txt` or
  `$S2_WITHHOLD_ASNS`).
- No domain name of the studied sites appears in any published file; Cloudflare zones are
  relabelled before writing.
- The IPs of non-verified requests were sent to Team Cymru's public whois to obtain the ASN.

## 7. Notes on the data files

- `data/logs/<site>/behaviour.csv`: `ips_*` columns count unique IPs **per (bot, verdict)** in
  that site. `data/behaviour_by_verdict.csv` sums them across bots and sites, so its columns are
  named `site_bot_ip_triples_*` (one IP claiming five bots counts five times); the number of
  distinct IPs per verdict, summed over sites (an upper bound), is `distinct_ips_upper_bound`.
- `data/spoofing_by_asn.csv`: `unique_ips_summed_over_sites` is likewise an upper bound.
- Edge files (`data/cloudflare/`) cover the 30 days before the run; re-running moves the window.
- Who did the work: see [the paper](https://easybyte.es/lab/studies/s2/paper/) §8 ("Automation and review"). All checks described here were
  performed by AI agents.

## 8. Reproducing

```bash
python3 -m unittest discover -s tests            # 15 offline tests
S2_CF_ENV=/path/.env python3 scripts/run_study.py # whole pipeline, reads private/sites.json
scripts/ai-bot-verify access.log --site mysite --asn --out results/
python3 scripts/cf_declared_bots.py --env .env --zones example.com --site-map map.json --days 30 --out data/cloudflare
python3 scripts/aggregate.py                      # study-level tables in data/
```

Python ≥ 3.10, standard library only. Network access needed for range files, DNS and (with
`--asn`) Team Cymru.
