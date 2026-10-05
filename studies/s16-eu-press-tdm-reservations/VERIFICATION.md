# VERIFICATION — S16

Everything below runs offline from the published `data/` with Python ≥ 3.10 and the standard
library only.

## 1. What `run.sh` and `check_headline.py` do

`./run.sh` rebuilds `data/summary.json` and `data/by_country.csv` from `data/records.csv` (and, in
EasyxLab's private copy, `data/records.csv` from the raw scan), runs the unit tests and then
`scripts/check_headline.py`.

`check_headline.py` builds a fixed list of phrases from `data/`: about 45 for the README abstract
(counts with denominators and percentages, Wilson intervals, fully-read and all-site denominators,
"at least"/"at most" figures, the frozen-rule sensitivity, contradictions under each rule, the TDMRep
channel split, band figures, breach counts D1/D2/D4/D7, the three detector audits, the provider
panel) and about 45 for [the paper](https://easybyte.es/lab/studies/s16/paper/) when present (the same headline phrases plus the class table
rows, all-site figures, frozen-rule figures, France and Poland with CIs, the three bands with CIs,
"403 sites block all four", llms.txt, `noai`, CrUX buckets, comment counts, D2/D5/D7/D8). Each phrase
must occur in the text. Inside the studies repository it also checks five phrases of the study's row
in the root `README.md`, and it fails if any of three phrases that the third review (2026-10-05)
found false returns to the README, the paper or that row ("would meet no machine-readable
reservation" and its variants: 23 of the 480 state a reservation in `noai` or `Content-Usage: ai=n`). Matching respects number boundaries, so "0
contradictions" cannot match "10 contradictions". The script exits 1 if any phrase is missing.

It does **not** check numbers in the text that are not on its list, nor whether the words around
a number are right ("at least" against "at most", or which denominator applies). Those were checked
by the independent review and are listed in section 2 for anyone to recompute.

```bash
./run.sh
python3 scripts/check_headline.py
python3 -m unittest discover -s tests       # 25 parser tests (robots extras, TDMRep, meta, detectors v1–v4, verdict)
```

## 2. The headline figures by hand

`ok` = sites that answered for `robots.txt` (1,510). `full` = `ok` without a `read_reason` (1,356).
The frozen-rule sensitivity is `full` without the rows where `rescan_d5` = 1 (1,282).

```bash
python3 - <<'PY'
import csv, collections
R = list(csv.DictReader(open('data/records.csv')))
ok = [r for r in R if r['robots_state'] in ('ok', 'unavailable', 'nl_prohibition')]
full = [r for r in ok if not r['read_reason']]
named = lambda L: [r for r in L if int(r['ai_blocked_root_n']) > 0]
print('frame', len(R), 'ok', len(ok), 'full', len(full))
print('classes (full)', collections.Counter(r['class'] for r in full))
print('named (full)', len(named(full)), 'of them without agnostic', sum(r['class'] != 'agnostic_reservation' for r in named(full)))
N = [r for r in full if r['class'] == 'named_bots_only']
print('named only: comments', sum(r['nl_reservation'] == '1' for r in N), 'ai=n', sum(r['content_usage_values'] == 'ai=n' for r in N),
      'noai', sum(r['noai'] == '1' for r in N), 'none of the three', sum(r['nl_reservation'] != '1' and r['content_usage_values'] != 'ai=n' and r['noai'] != '1' for r in N))
print('agnostic (full) only through a * group disallowing /', sum(r['class'] == 'agnostic_reservation' and r['agnostic_channels'] == 'robots_star_disallow_root' for r in full))
print('all sites: agnostic at least', sum(r['class'] == 'agnostic_reservation' for r in ok),
      '; named', len(named(ok)), 'without agnostic at most', sum(r['class'] != 'agnostic_reservation' for r in named(ok)))
T = [r for r in full if 'tdmrep' in r['agnostic_channels']]
print('TDMRep', len(T), 'meta', sum('tdmrep_meta' in r['agnostic_channels'] for r in T),
      'header', sum('tdmrep_header' in r['agnostic_channels'] for r in T), 'file', sum('tdmrep_file' in r['agnostic_channels'] for r in T),
      'France', sum(r['country'] == 'FR' for r in T), 'of', sum(r['country'] == 'FR' for r in full))
print('contradictions (full)', [r['host'] for r in full if r['contradiction'] == '1'])
print('Content-Usage ai=n', sum('ai=n' in r['content_usage_values'].replace(' ', '') for r in ok))
print('comment statements', sum(r['nl_reservation'] == '1' or r['nl_prohibition'] == '1' for r in ok), 'of', len(ok))
fz = [r for r in full if r['rescan_d5'] != '1']
print('frozen rule: full', len(fz), 'agnostic', sum(r['class'] == 'agnostic_reservation' for r in fz), 'contradictions', sum(r['contradiction'] == '1' for r in fz))
print('robots-only', collections.Counter(r['deleted_after_collection'] or 'stopped in scan' for r in ok if r['read_reason']))
PY
python3 -c "import json; [print(n, json.load(open('data/'+n))) for n in ('deviation_d2.json','deviation_d4.json','deviation_d5.json','deviation_d7.json','independent_audit_v3.json','independent_audit_v2.json','comment_audit_summary.json')]" | cut -c1-400
```

Wilson 95% intervals are computed by `aggregate.wilson` (z = 1.96).

## 3. Checking a single site

`python3 scripts/optout_check.py <host>` re-reads one site live (robots.txt first) and prints every
channel and the verdict. Sites change their files; each published record has `checked_utc`.

## 4. What cannot be re-checked from the public package

- Raw `robots.txt` bodies and provider documents (third-party text) stay in EasyxLab's private copy;
  the documents' sha256 are in `data/sources_manifest.csv`, and bodies can be re-read live.
- Our audit labels (in `scripts/comment_audit.py`) are an AI agent's reading. The independent
  reviewer's labels are in its report; `data/independent_audit_v2.json` gives its figures.
- `data/request_audit.json` was computed from the private request log, in which the response
  status of the D2, D4 and D7 requests has been removed; it counts those requests by URL and time
  (`breach_requests_by_deviation`).
