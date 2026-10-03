"""Collect: for every register row (cohort first, then the rest), fetch the registered URL politely, follow at most one
hop to linked documents, classify every document, keep only ESMA-format iXBRL files (for 03_validate.py).

Outputs (work/, never published):
  work/collect/urls.jsonl   one line per registered URL: fetch result, class, one-hop candidates and their results
  work/docs/<sha256>.xhtml  iXBRL files awaiting validation (deleted by 03_validate.py)
Resumable: URLs already in urls.jsonl are skipped.
"""
from __future__ import annotations

import csv
import datetime as dt
import html as htmlmod
import json
import re
import shutil
import sys
import urllib.parse
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch import Fetcher  # noqa: E402
from mica_wp_check import sniff, DOC_CLASSES, instant_redirect  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/sources"
WORK = ROOT / "work"
DOCS = WORK / "docs"
OUT = WORK / "collect/urls.jsonl"
CUTOFF = dt.date(2025, 12, 23)
DOCS_CAP = 650 * 1024 * 1024
MAX_XHTML_CANDIDATES, MAX_PDF_CANDIDATES = 3, 1


DATE_FORMATS = ("%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d")  # the register mixes them (D7)


def parse_date(s: str):
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime((s or "").strip(), fmt).date()
        except ValueError:
            continue
    return None


def is_header_row(r: dict) -> bool:
    """OTHER.csv repeats its header line inside the file (D7): such lines are parsing artefacts, not rows."""
    return r.get("ae_homeMemberState", "").strip() == "ae_homeMemberState" or r.get("wp_lastupdate", "").strip() == "wp_lastupdate"


def split_urls(field: str) -> list[str]:
    """The register field is free text: split multi-valued entries and add a scheme where missing."""
    out = []
    for tok in re.split(r"[\s|;,]+", (field or "").strip()):
        tok = tok.strip().strip("\"'()<>")
        if not tok or tok.lower() in ("emt_no_wp", "emt_crin", "accessible", "via:", "via"):
            continue
        if not re.match(r"^https?://", tok, re.I):
            if re.match(r"^(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)+(/.*)?$", tok, re.I):
                tok = "https://" + tok
            else:
                continue
        out.append(tok)
    return list(dict.fromkeys(out))[:3]


def load_rows() -> list[dict]:
    rows = []
    for reg in ("OTHER", "EMTWP"):
        with open(RAW / f"{reg}.csv", encoding="utf-8-sig", newline="") as f:
            for i, r in enumerate(csv.DictReader(f)):
                r = {k: (v or "").strip() for k, v in r.items() if k}
                if is_header_row(r):
                    continue
                r["_register"] = reg
                r["_row"] = i + 2  # line in the CSV (header = 1)
                d = parse_date(r.get("wp_lastupdate", ""))
                r["_date"] = d.isoformat() if d else ""
                r["_cohort"] = bool(d and d >= CUTOFF)
                r["_urls"] = split_urls(r.get("wp_url", ""))
                rows.append(r)
    return rows


LINK_RE = re.compile(r"<(a|iframe|embed|object)\b([^>]*)>(.*?)(?:</\1>|(?=<))", re.I | re.S)
ATTR_RE = re.compile(r"\b(href|src|data)\s*=\s*[\"']([^\"']+)[\"']", re.I)


def candidate_links(body: bytes, base: str) -> list[tuple[str, str]]:
    text = body.decode("utf-8", "replace")
    out = []
    for m in LINK_RE.finditer(text):
        am = ATTR_RE.search(m.group(2))
        if not am:
            continue
        href = htmlmod.unescape(am.group(2)).strip()
        if href.startswith(("mailto:", "javascript:", "#", "tel:")):
            continue
        url = urllib.parse.urljoin(base, href)
        if not url.lower().startswith("http"):
            continue
        anchor = re.sub(r"<[^>]+>|\s+", " ", m.group(3) or "").strip()[:120]
        path = urllib.parse.urlsplit(url).path.lower()
        if re.search(r"\.(xhtml|xhtm|pdf|zip)$", path) or re.search(r"xbrl|xhtml", (url + " " + anchor).lower()):
            out.append((url.split("#")[0], anchor))
    return list(dict.fromkeys(out))


def kind_of(url: str, anchor: str) -> str:
    path = urllib.parse.urlsplit(url).path.lower()
    if path.endswith((".xhtml", ".xhtm")) or re.search(r"xbrl|xhtml", (url + " " + anchor).lower()):
        return "xhtml"
    if path.endswith(".pdf"):
        return "pdf"
    return "zip"


def rank(cands: list[tuple[str, str]], codes: set[str]) -> list[tuple[str, str]]:
    order = {"xhtml": 0, "pdf": 1, "zip": 2}

    def key(ic):
        i, (u, a) = ic
        hit = any(c and c.lower() in u.lower() for c in codes)
        return (0 if hit else 1, order[kind_of(u, a)], i)
    ranked = [c for _, c in sorted(enumerate(cands), key=key)]
    x = [c for c in ranked if kind_of(*c) == "xhtml"][:MAX_XHTML_CANDIDATES]
    p = [c for c in ranked if kind_of(*c) == "pdf"][:MAX_PDF_CANDIDATES]
    z = [c for c in ranked if kind_of(*c) == "zip"][:1] if not x and not p else []
    return x + p + z


def docs_size() -> int:
    return sum(p.stat().st_size for p in DOCS.glob("*.xhtml"))


def fetch_doc(f: Fetcher, url: str) -> dict:
    r = f.get(url)
    res = {k: r[k] for k in ("url", "status", "final_url", "ctype", "size", "sha256", "reason")}
    body = r["body"]
    if r["reason"] and r["reason"].startswith("robots"):
        res["outcome"] = "robots"
        return res
    if r["reason"] == "too-slow":
        res["outcome"] = "net-error"
        return res
    if r["reason"] == "too-large":
        res["outcome"] = "other"
        return res
    if body is None:
        res["outcome"] = "net-error" if (r["reason"] or "").startswith("net:") else "net-error"
        return res
    info = sniff(body, r["ctype"], r["final_url"])
    res["doc"] = {k: getattr(info, k) for k in ("doc_class", "is_xml_wellformed", "root", "has_ix_namespace",
                                                 "schema_refs", "esma_table", "ix_fact_count", "title", "antibot",
                                                 "ix_version")}
    if info.antibot:
        res["outcome"] = "anti-bot"
    elif r["status"] and r["status"] >= 400:
        res["outcome"] = "http-error"
    else:
        res["outcome"] = info.doc_class
    if res["outcome"] == "html":
        tgt = instant_redirect(body)
        if tgt:
            res["instant_redirect"] = urllib.parse.urljoin(r["final_url"] or url, tgt)
    if res["outcome"] in ("ixbrl-esma", "ixbrl-1.0", "ixbrl-other"):
        p = DOCS / f"{r['sha256']}.xhtml"
        if not p.exists():
            if docs_size() + len(body) > DOCS_CAP:
                res["deferred"] = "disk-cap"
            else:
                p.write_bytes(body)
        res["saved"] = p.exists()
    res["_body"] = body if res["outcome"] == "html" else None
    return res


def url_codes(rows) -> tuple[dict, dict]:
    """URL -> DTI codes of all rows listing it (for ranking one-hop candidates); URL -> in cohort."""
    codes = defaultdict(set)
    first_seen = {}
    for r in sorted(rows, key=lambda r: (not r["_cohort"], r["_register"], r["_row"])):
        for u in r["_urls"]:
            codes[u] |= {c for c in re.split(r"[|\s]+", r.get("ae_DTI", "") + "|" + r.get("ae_DTI_FFG", "")) if c}
            first_seen.setdefault(u, r["_cohort"])
    return codes, first_seen


def process_url(f: Fetcher, u: str, codes: set) -> dict:
    rec = {"url": u}
    main_res = fetch_doc(f, u)
    body = main_res.pop("_body", None)
    # An instant client-side redirect (meta refresh <= 1 s, trivial JS) is a redirect, not a hop (D9): follow <= 5.
    chain = []
    while main_res.get("instant_redirect") and len(chain) < 5:
        chain.append({k: main_res.get(k) for k in ("url", "final_url", "status", "instant_redirect")})
        main_res = fetch_doc(f, main_res["instant_redirect"])
        body = main_res.pop("_body", None)
    if chain:
        rec["client_redirects"] = chain
        main_res["url"] = u
    rec["main"] = main_res
    rec["hops"] = []
    if main_res.get("outcome") == "html" and body:
        base = main_res.get("final_url") or u
        cands = candidate_links(body, base)
        rec["n_candidates"] = len(cands)
        rec["n_candidates_xhtml"] = sum(1 for c in cands if kind_of(*c) == "xhtml")
        for cu, anchor in rank(cands, codes):
            h = fetch_doc(f, cu)
            h.pop("_body", None)
            h["anchor"] = anchor[:80]
            rec["hops"].append(h)
    return rec


def main(argv):
    only_cohort = "--cohort-only" in argv
    DOCS.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        for line in OUT.open():
            done.add(json.loads(line)["url"])
    rows = load_rows()
    codes, first_seen = url_codes(rows)
    urls = [u for u in first_seen if u not in done and (first_seen[u] or not only_cohort)]
    # Round-robin by host so that the 1 s/host wait overlaps with other hosts' latency.
    byhost = defaultdict(list)
    for u in urls:
        byhost[urllib.parse.urlsplit(u).netloc.lower()].append(u)
    ordered = []
    cohort_first = sorted(byhost.values(), key=lambda l: (not first_seen[l[0]], -len(l)))
    while any(cohort_first):
        for l in cohort_first:
            if l:
                ordered.append(l.pop(0))
    ordered.sort(key=lambda u: not first_seen[u])  # stable: cohort URLs first, round-robin inside each group
    f = Fetcher(WORK / "requests.log")
    print(f"{len(ordered)} URLs to fetch ({sum(first_seen[u] for u in ordered)} cohort)", flush=True)
    for n, u in enumerate(ordered, 1):
        rec = process_url(f, u, codes[u])
        rec["cohort"] = first_seen[u]
        with OUT.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        if n % 25 == 0:
            print(n, "done", flush=True)
    print("finished", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
