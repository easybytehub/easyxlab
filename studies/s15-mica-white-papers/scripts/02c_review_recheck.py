"""Corrections after the independent review (METHOD.md, deviations D8-D10). Network; run once.

Phase A (D8, robots on document hosts): fetch robots.txt again for every host that served a document request of the
  collection, parse it as RFC 9309 (`*`, `$`, longest match, any Content-Type) and re-evaluate every such request
  (registered URL, one-hop candidate, every step of a redirect chain). A request that is disallowed for our
  User-Agent is reclassified `robots`, links read from a disallowed landing page are dropped, and any validation
  record kept from it is deleted.
Phase B (D9, instant client-side redirects): re-fetch every landing page that was classified `html`; when it is an
  instant redirect (meta refresh <= 1 s, or a trivial JavaScript location redirect), the registered URL is processed
  again following it like an HTTP 3xx. The previous record is kept under "pre_review" for the frozen-rule figure.
Phase C (D10, Inline XBRL version): re-download every Inline XBRL file reached and record which Inline XBRL
  namespace it declares (2013 = 1.1, 2008 = 1.0) -> work/namespaces.json.
"""
import importlib
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fetch  # noqa: E402
import robots9309  # noqa: E402
from mica_wp_check import sniff  # noqa: E402

collect = importlib.import_module("02_collect")
ROOT = Path(__file__).resolve().parent.parent
OUT = collect.OUT
STATE = ROOT / "work/review_recheck.json"
NONDOC = {"www.esma.europa.eu", "publications.europa.eu", "web.archive.org", "api.gleif.org", "api.openalex.org",
          "api.crossref.org", "export.arxiv.org", "api.github.com"}
REVIEW_START = "2026-10-03T11:50:00Z"  # requests after this are the review's own


def host(u):
    return urllib.parse.urlsplit(u).netloc.lower()


def save(recs):
    tmp = OUT.with_suffix(".tmp")
    with tmp.open("w") as fh:
        for d in recs:
            fh.write(json.dumps(d) + "\n")
    tmp.replace(OUT)


def main():
    recs = [json.loads(l) for l in OUT.open()]
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    f = fetch.Fetcher(ROOT / "work/requests.log")

    # ---------------- Phase A ----------------
    if "A" not in state:
        log = [json.loads(l) for l in (ROOT / "work/requests.log").open()]
        log = [e for e in log if e["t"] < REVIEW_START and e["kind"] in ("get", "redirect", "skip")]
        redirect = {e["url"]: e["to"] for e in log if e["kind"] == "redirect"}
        doc_urls = {e["url"] for e in log if host(e["url"]) not in NONDOC} | \
                   {e.get("to") for e in log if e["kind"] == "redirect" and host(e.get("to") or "") not in NONDOC}
        doc_urls.discard(None)
        hosts = sorted({fetch.Fetcher.origin(u) for u in doc_urls})
        print("phase A:", len(doc_urls), "document requests on", len(hosts), "hosts", flush=True)
        robots = {}
        for scheme, h in hosts:
            info = f.robots_for(f"{scheme}://{h}/")
            robots[f"{scheme}://{h}"] = {"status": info.status, "http": info.http_status,
                                         "html": info.served_as_html, "body": info.body}
        disallowed = []
        for u in sorted(doc_urls):
            sch, h = fetch.Fetcher.origin(u)
            info = f.robots[f"{sch}://{h}"]
            if info.status == "ok" and info.groups and not robots9309.allowed(info.groups, fetch.UA_TOKEN, u):
                disallowed.append(u)
        print("disallowed under RFC 9309:", len(disallowed), flush=True)
        dset = set(disallowed)

        def chain(u):
            seen = [u]
            while u in redirect and len(seen) < 8:
                u = redirect[u]
                seen.append(u)
            return seen
        changed = []
        val_dir = ROOT / "work/validate"
        for d in recs:
            for part, res in [("main", d["main"])] + [("hop", h) for h in d.get("hops", [])]:
                steps = set(chain(res["url"])) | {res.get("final_url") or res["url"]}
                if steps & dset and res.get("outcome") != "robots":
                    changed.append({"record": d["url"], "part": part, "url": res["url"], "was": res.get("outcome"),
                                    "sha256": res.get("sha256")})
                    if res.get("sha256"):
                        (val_dir / f"{res['sha256']}.json").unlink(missing_ok=True)
                    for k in ("doc", "sha256", "size", "ctype", "status", "saved"):
                        res.pop(k, None)
                    res["outcome"], res["reason"] = "robots", "robots:disallowed-rfc9309-recheck"
                    if part == "main":
                        d["hops_dropped_robots"] = len(d.get("hops", []))
                        d["hops"] = []
        state["A"] = {"document_requests": len(doc_urls), "hosts": len(hosts), "disallowed": disallowed,
                      "results_changed": changed,
                      "robots_status": {k: {kk: vv for kk, vv in v.items() if kk != "body"} for k, v in robots.items()}}
        (ROOT / "work/robots_recheck_bodies.json").write_text(json.dumps({k: v["body"] for k, v in robots.items()}))
        save(recs)
        STATE.write_text(json.dumps(state, indent=1))
        print("phase A done:", len(changed), "results reclassified", flush=True)

    # ---------------- Phase B ----------------
    if "B" not in state:
        codes, _ = collect.url_codes(collect.load_rows())
        todo = [d for d in recs if d["main"].get("outcome") == "html"]
        print("phase B:", len(todo), "landing pages to re-check", flush=True)
        redirected = []
        byurl = {d["url"]: i for i, d in enumerate(recs)}
        for n, d in enumerate(todo, 1):
            res = collect.fetch_doc(f, d["url"])
            res.pop("_body", None)
            if res.get("instant_redirect"):
                new = collect.process_url(f, d["url"], codes[d["url"]])
                new["cohort"] = d.get("cohort")
                new["pre_review"] = {k: d[k] for k in ("main", "hops", "frozen") if k in d}
                recs[byurl[d["url"]]] = new
                redirected.append({"url": d["url"], "target": res["instant_redirect"],
                                   "was": d["main"].get("outcome"), "now": new["main"].get("outcome"),
                                   "hops_now": [h.get("outcome") for h in new.get("hops", [])]})
            if n % 50 == 0:
                print(n, flush=True)
        state["B"] = {"rechecked": len(todo), "instant_redirects": redirected}
        save(recs)
        STATE.write_text(json.dumps(state, indent=1))
        print("phase B done:", len(redirected), "instant redirects", flush=True)

    # ---------------- Phase C (resumable, in batches: --limit N) ----------------
    if "C" not in state:
        nsp = ROOT / "work/namespaces.json"
        ns = json.loads(nsp.read_text()) if nsp.exists() else {}
        targets = {}
        for d in recs:
            for res in [d["main"]] + d.get("hops", []):
                if res.get("outcome") in ("ixbrl-esma", "ixbrl-other", "ixbrl-1.0") and res.get("sha256"):
                    targets.setdefault(res["sha256"], res.get("final_url") or res["url"])
        todo = [(k, u) for k, u in targets.items() if k not in ns][:LIMIT]
        print("phase C:", len(targets), "files,", len(targets) - len(ns), "left; this run", len(todo), flush=True)
        for sha, u in todo:
            r = f.get(u)
            if r["body"] is None:
                ns[sha] = {"status": r["status"], "reason": r["reason"]}
            else:
                i = sniff(r["body"], r["ctype"], r["final_url"])
                ns[sha] = {"status": r["status"], "same_hash": r["sha256"] == sha, "ix_version": i.ix_version,
                           "doc_class_now": i.doc_class}
            nsp.write_text(json.dumps(ns, indent=1))
        if all(k in ns for k in targets):
            state["C"] = {"files": len(targets)}
            STATE.write_text(json.dumps(state, indent=1))
            print("phase C done", flush=True)


LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10**9

if __name__ == "__main__":
    main()
