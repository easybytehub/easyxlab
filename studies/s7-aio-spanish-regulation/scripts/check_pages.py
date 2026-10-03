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

Usage: check_pages.py [--reading 1] [--control 20] [--seed 7]
"""
import argparse, csv, html, json, random, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify import norm, hits, contextual  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; EasyxLab-S7/0.1; research; +https://github.com/easybytehub/easyxlab)"


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
        with urllib.request.urlopen(req, timeout=20) as r:
            ct = r.headers.get("Content-Type", "")
            if "html" not in ct and "text" not in ct:
                return None, f"content-type {ct[:40]}"
            raw = r.read(3_000_000).decode("utf-8", "replace")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reading", type=int, default=1)
    ap.add_argument("--control", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
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
    rows, att = [], []
    for c in target + control:
        r = resp[(c["qid"], c["surface"])]
        states = []
        for ref in (r.get("refs") or [])[:6]:
            u = ref.get("url")
            if not u:
                continue
            text, status = pages.get(u, (None, "missing"))
            st = page_state(facts[c["fact_id"]], text) if text else "fetch_failed"
            states.append(st)
            rows.append({"reading": a.reading, "qid": c["qid"], "surface": c["surface"], "answer_verdict": c["final_verdict"],
                         "group": "target" if c in target else "control", "url": u, "fetch": status, "page_state": st})
        read = [s for s in states if s != "fetch_failed"]
        # strict: a cited page states ONLY the old rule; loose: also pages that state both (often history
        # tables the context rule does not recognise on long pages)
        if not read:
            a_ = a_loose = "unverifiable"
        else:
            a_ = "in_source" if "page_old" in read else "synthesis"
            a_loose = "in_source" if any(s in ("page_old", "page_mixed") for s in read) else "synthesis"
        att.append({"reading": a.reading, "qid": c["qid"], "fact_id": c["fact_id"], "surface": c["surface"], "answer_verdict": c["final_verdict"],
                    "group": "target" if c in target else "control", "pages_read": len(read),
                    "pages_old_or_mixed": sum(s in ("page_old", "page_mixed") for s in read),
                    "pages_current": sum(s == "page_current" for s in read), "attribution": a_,
                    "attribution_loose": a_loose})
    with open(ROOT / f"data/page_checks_r{a.reading}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(ROOT / f"data/error_attribution_r{a.reading}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(att[0])); w.writeheader(); w.writerows(att)
    from collections import Counter
    for g in ("target", "control"):
        print(g, "strict:", dict(Counter(x["attribution"] for x in att if x["group"] == g)),
              "loose:", dict(Counter(x["attribution_loose"] for x in att if x["group"] == g)))
    print("fetch:", Counter(r["fetch"] for r in rows).most_common(6))


if __name__ == "__main__":
    main()
