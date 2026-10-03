#!/usr/bin/env python3
"""(c) Is the error already in the cited page, or does the synthesis introduce it?

No one reads the pages: this script fetches each cited URL (at most 6 per answer) of every confirmed error
(final verdict outdated/mixed/incorrect, scored facts) and of a random control sample of `current` answers,
strips it to text and applies the SAME regular expressions and context rule as classify.py:
  page_current / page_old / page_mixed / page_silent / fetch_failed
Answer-level attribution (outdated/mixed answers only):
  in_source       strict: at least one cited page states only the superseded rule (page_old);
                  loose (`attribution_loose`): page_old or page_mixed
  synthesis       pages were read, none states the superseded rule
  unverifiable    no cited page could be read
Pages are read today, not when Google built the answer: a page corrected since then makes `synthesis`
more likely than it was (METHOD.md §6). Only aggregates and URLs are stored; page text is not kept.

robots.txt as a text-and-data-mining reservation (METHOD.md §8). This script mines the text of the pages it
fetches, so before each request (redirect hops included) it reads the host's robots.txt once and skips URLs it
disallows for the product token `EasyxLab` (RFC 9309 matching: rules of a group naming it, else of `*`; longest match
wins; 4xx other than 429 = no rules; 429, 5xx or a network error = disallow all). A skipped URL is left out of
page_checks and of the attribution, and is listed on stdout. The first run of 3 October 2026 did not read
robots.txt; the six URLs it fetched against it were removed from the published files afterwards, and --reattribute
rebuilt the attribution.

Usage: check_pages.py [--reading 1] [--control 20] [--seed 7]
       check_pages.py --reattribute --reading N   offline: rebuild data/error_attribution_rN.csv from
                                                  data/page_checks_rN.csv (answer list from the existing file)
"""
import argparse, csv, html, json, random, re, sys, threading, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify import norm, hits, contextual  # noqa: E402
import robots9309  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; EasyxLab-S7/0.1; research; +https://github.com/easybytehub/easyxlab)"
TOKEN = "EasyxLab"          # RFC 9309 product token (letters, "_" and "-" only)
MAX_HOPS = 5
DISALLOW_ALL = "User-agent: *\nDisallow: /\n"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None         # 3xx surfaces as HTTPError; fetch() checks robots.txt for the target first


_OPENER = urllib.request.build_opener(_NoRedirect)
_ROBOTS, _ROBOTS_LOCK = {}, threading.Lock()


def robots_allowed(url):
    """RFC 9309 decision for url; each host's robots.txt is read once."""
    p = urlsplit(url)
    origin = f"{p.scheme}://{p.netloc}".lower()
    with _ROBOTS_LOCK:
        if origin not in _ROBOTS:
            try:
                req = urllib.request.Request(origin + "/robots.txt", headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=20) as r:          # follows redirects (RFC 9309: >= 5)
                    _ROBOTS[origin] = robots9309.parse(r.read(robots9309.PARSE_LIMIT))
            except urllib.error.HTTPError as e:
                _ROBOTS[origin] = [] if 400 <= e.code < 500 and e.code != 429 else robots9309.parse(DISALLOW_ALL)
            except Exception:
                _ROBOTS[origin] = robots9309.parse(DISALLOW_ALL)
        groups = _ROBOTS[origin]
    return robots9309.allowed(groups, TOKEN, url)


def fetch(url):
    try:
        for _ in range(MAX_HOPS + 1):
            if not robots_allowed(url):
                return None, "robots_disallow"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
                with _OPENER.open(req, timeout=20) as r:
                    ct = r.headers.get("Content-Type", "")
                    if "html" not in ct and "text" not in ct:
                        return None, f"content-type {ct[:40]}"
                    raw = r.read(3_000_000).decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                loc = e.headers.get("Location") if e.code in (301, 302, 303, 307, 308) else None
                if not loc:
                    raise
                url = urljoin(url, loc)
                continue
            break
        else:
            return None, "too_many_redirects"
    except Exception as e:
        return None, type(e).__name__
    raw = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    t = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return t, "ok"


def page_state(fact, text):
    t = norm(text)
    cur = hits(t, fact["cur_patterns"])
    old = [(s, e) for s, e in hits(t, fact["old_patterns"]) if not contextual(t, s, e)]
    if cur and old:
        return "page_mixed"
    if old:
        return "page_old"
    if cur:
        return "page_current"
    return "page_silent"


def attribute(meta, states):
    """Answer-level attribution from the page states of its cited pages (robots-disallowed pages excluded)."""
    read = [s for s in states if s != "fetch_failed"]
    # strict: a cited page states ONLY the old rule; loose: also pages that state both (often history
    # tables the context rule does not recognise on long pages)
    if not read:
        a_ = a_loose = "unverifiable"
    else:
        a_ = "in_source" if "page_old" in read else "synthesis"
        a_loose = "in_source" if any(s in ("page_old", "page_mixed") for s in read) else "synthesis"
    return {**meta, "pages_read": len(read), "pages_old_or_mixed": sum(s in ("page_old", "page_mixed") for s in read),
            "pages_current": sum(s == "page_current" for s in read), "attribution": a_, "attribution_loose": a_loose}


def write(name, rows):
    with open(ROOT / "data" / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def report(att, rows):
    from collections import Counter
    for g in ("target", "control"):
        print(g, "strict:", dict(Counter(x["attribution"] for x in att if x["group"] == g)),
              "loose:", dict(Counter(x["attribution_loose"] for x in att if x["group"] == g)))
    print("fetch:", Counter(r["fetch"] for r in rows).most_common(6))


def reattribute(n):
    """Offline: rebuild error_attribution_rN.csv from page_checks_rN.csv, keeping the answer list and its order."""
    old = list(csv.DictReader(open(ROOT / f"data/error_attribution_r{n}.csv", encoding="utf-8")))
    rows = list(csv.DictReader(open(ROOT / f"data/page_checks_r{n}.csv", encoding="utf-8")))
    states = {}
    for r in rows:
        states.setdefault((r["qid"], r["surface"], r["group"]), []).append(r["page_state"])
    keys = ("reading", "qid", "fact_id", "surface", "answer_verdict", "group")
    att = [attribute({k: x[k] for k in keys}, states.get((x["qid"], x["surface"], x["group"]), [])) for x in old]
    write(f"error_attribution_r{n}.csv", att)
    report(att, rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reading", type=int, default=1)
    ap.add_argument("--control", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--reattribute", action="store_true", help="offline: rebuild the attribution from page_checks")
    a = ap.parse_args()
    if a.reattribute:
        return reattribute(a.reading)
    facts = {f["id"]: f for f in json.load(open(ROOT / "data/facts.json", encoding="utf-8"))}
    resp = {}
    for line in open(ROOT / f"data/raw/responses/reading{a.reading}.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if not r.get("error"):
            resp[(r["qid"], r["surface"])] = r
    cls = [json.loads(l) for l in open(ROOT / "data/raw/classified_full.jsonl", encoding="utf-8")]
    cls = [c for c in cls if c["reading"] == a.reading and c["fact_id"] != "F16"]
    target = [c for c in cls if c["final_verdict"] in ("outdated", "mixed", "incorrect")]
    rnd = random.Random(a.seed)
    cur = [c for c in cls if c["final_verdict"] == "current"]
    control = rnd.sample(cur, min(a.control, len(cur)))
    jobs = []
    for c in target + control:
        r = resp[(c["qid"], c["surface"])]
        for ref in (r.get("refs") or [])[:6]:
            if ref.get("url"):
                jobs.append((c, ref["url"]))
    urls = sorted({u for _, u in jobs})
    print(f"answers: {len(target)} outdated/mixed + {len(control)} control · {len(urls)} distinct URLs")
    with ThreadPoolExecutor(max_workers=8) as ex:
        pages = dict(zip(urls, ex.map(fetch, urls)))
    disallowed = sorted(u for u, (_, st) in pages.items() if st == "robots_disallow")
    rows, att = [], []
    for c in target + control:
        r = resp[(c["qid"], c["surface"])]
        states = []
        for ref in (r.get("refs") or [])[:6]:
            u = ref.get("url")
            if not u:
                continue
            text, status = pages.get(u, (None, "missing"))
            if status == "robots_disallow":
                continue                                # not fetched, not part of the analysis
            st = page_state(facts[c["fact_id"]], text) if text else "fetch_failed"
            states.append(st)
            rows.append({"reading": a.reading, "qid": c["qid"], "surface": c["surface"], "answer_verdict": c["final_verdict"],
                         "group": "target" if c in target else "control", "url": u, "fetch": status, "page_state": st})
        meta = {"reading": a.reading, "qid": c["qid"], "fact_id": c["fact_id"], "surface": c["surface"],
                "answer_verdict": c["final_verdict"], "group": "target" if c in target else "control"}
        att.append(attribute(meta, states))
    write(f"page_checks_r{a.reading}.csv", rows)
    write(f"error_attribution_r{a.reading}.csv", att)
    report(att, rows)
    print(f"robots.txt disallowed {len(disallowed)} URL(s), not fetched:", *disallowed, sep="\n  ")


if __name__ == "__main__":
    main()
