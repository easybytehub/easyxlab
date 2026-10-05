# S2 — Spoofed AI crawlers

*EasyxLab · study S2 · data as of 2026-10-02 · status: working draft, not peer-reviewed*

**Paper:** [easybyte.es/lab/studies/s2/paper/](https://easybyte.es/lab/studies/s2/paper/) · [PDF](https://easybyte.es/lab/studies/s2/paper.pdf)

## Abstract

Many site owners count "GPTBot", "ClaudeBot" or "ChatGPT-User" in their access logs as evidence
that AI systems read or cite them. The User-Agent is free text. We checked every request
claiming to be one of 23 AI or search crawlers on three small production websites (16,548
requests in origin logs: one of 68 days and two of 7–9 days; plus a separate 30-day Cloudflare
edge view) against each
operator's own published verification method — IP-range JSON files and forward-confirmed
reverse DNS. **39.3% of the claims were spoofed** (44.3% of those that could be tested), 49.5%
verified, 11.3% unverifiable or indeterminate. User-initiated fetchers, the names many site owners
read as an "AI citation" signal, were the worst: 67.8% spoofed, and Claude-User,
Perplexity-User, MistralAI-User and DuckAssistBot were 0–4.2% genuine. Google-Extended, a token
Google says is never sent as a User-Agent, appeared 371 times. All spoofing came from at most
54 addresses; 81% of spoofed requests came from cloud/hosting networks (one cloud provider's
customer space alone: 66%);
97% of spoofed requests came from sources that also probed for credentials (`.env`,
`config.json`, `service-account.json`) and 92% from sources that rotated through several operators'
identities. On the main site, at the CDN edge, the spoofed volume was at least three times what the origin logged; free-plan
defaults blocked 0.7% of it. We release `ai-bot-verify`, a dependency-free verifier for
nginx/Apache-style access logs that outputs aggregates only and refuses to write IP addresses.

**Competing interests:** the three sites are run by the authors' organisation, which also
publishes `ai-bot-verify`.

## Contents

| file | |
|---|---|
| [paper](https://easybyte.es/lab/studies/s2/paper/) (web) | paper-style draft (EN) |
| `METHOD.md` | data sources, verification rules with literal operator documentation, privacy |
| `scripts/ai_bot_verify.py`, `scripts/ai-bot-verify` | the verifier (Python ≥ 3.10, stdlib only) |
| `scripts/cf_declared_bots.py` | same checks on Cloudflare GraphQL analytics |
| `scripts/aggregate.py` | builds the study tables in `data/` |
| `scripts/run_study.py` | runs the whole pipeline; reads the private site mapping |
| `tests/` | 15 offline tests (`python3 -m unittest discover -s tests`) |
| `data/` | aggregated CSV/JSON only — no IP addresses |
| `data/raw/`, `private/` | git-ignored: raw logs, range-file cache, run logs, site mapping, withheld ASNs. Never published. |

## Quick use

```bash
scripts/ai-bot-verify /var/log/nginx/access.log* --site example.com --out results/
scripts/ai-bot-verify access.log --asn        # also ASN of non-verified sources (asks Team Cymru)
```

Verdicts: `verified` (in the operator's published ranges or passes FCrDNS), `spoofed`
(operator publishes a method and the IP fails it, or a robots-only token used as a UA),
`unverifiable` (no published method), `indeterminate` (method exists but could not be applied).

## Headline table (origin logs, three sites pooled)

| crawler | requests | % genuine (of testable) |
|---|---|---|
| Bingbot | 1,902 | 94.1 |
| Googlebot | 2,548 | 67.5 |
| ClaudeBot | 1,808 | 63.0 |
| OAI-SearchBot | 1,569 | 56.8 |
| ChatGPT-User | 1,713 | 48.7 |
| GPTBot | 979 | 45.8 |
| PerplexityBot | 839 | 38.7 |
| CCBot | 452 | 18.6 |
| Claude-User | 318 | 3.5 |
| Perplexity-User | 309 | 0.0 |
| Google-Extended | 371 | 0.0 (never a real UA) |

Sites are anonymised as Site A (a calculator site) and Sites B and C (two niche tool sites
launched in September 2026). The work was done by AI agents and checked by an independent AI
reviewer; [the paper](https://easybyte.es/lab/studies/s2/paper/) §9 says exactly what was automated.

Licences: code Apache-2.0 ([LICENSE](../../LICENSE)); data and text CC BY 4.0
([LICENSE-DATA](../../LICENSE-DATA)).

---

EasyxLab · a research lab by [EasyByte](https://easybyte.es)
