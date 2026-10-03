#!/usr/bin/env python3
"""Collect Google AI Overview and AI Mode answers for the S7 queries through DataForSEO.

One "reading" = every query in data/queries.csv sent once to each surface:
  aio  : POST /v3/serp/google/organic/live/advanced  (depth 10, load_async_ai_overview=true)
  mode : POST /v3/serp/google/ai_mode/live/advanced
Location "Spain", language "es", desktop. Raw responses go gzipped to data/raw/reading<N>/ (git-ignored);
the extracted answer text and cited references go to data/raw/responses/reading<N>.jsonl (not redistributed).

Spend control. If EasyByte's in-house client (EasyByte-Vault/scripts/serp-api.py, private) is present it is used:
it reads the credentials from the vault .env (never printed or copied), estimates each request, refuses to exceed
its per-run cap and records the REAL cost DataForSEO returns. Otherwise a minimal stdlib client is used, with
credentials from the environment. On top of that this script keeps a
study-wide ledger (data/spend.json) and refuses to start, or stops mid-run, when the study total would pass
--budget (default 4.50 USD).

Usage: probe.py --reading N [--surfaces aio,mode] [--only F01-Q1,...] [--limit K] [--workers 6] [--budget 4.5]
"""
import argparse, csv, gzip, importlib.util, json, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data/spend.json"
INHOUSE = Path.home() / "Documents/EasyByte/EasyByte-Vault/scripts/serp-api.py"   # EasyByte's own client, if present


class _MiniClient:
    """Minimal DataForSEO client used when the in-house one is not available (anyone re-running the study).
    Credentials from the environment: DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD. Never printed or written."""
    def __init__(self):
        import base64, os
        lg, pw = os.environ.get("DATAFORSEO_LOGIN"), os.environ.get("DATAFORSEO_PASSWORD")
        if not (lg and pw):
            sys.exit("Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD (API credentials from app.dataforseo.com/api-access).")
        self.h = {"Authorization": "Basic " + base64.b64encode(f"{lg}:{pw}".encode()).decode(), "Content-Type": "application/json"}

    def fijar_tope(self, usd=None, dia=None):
        pass                                   # the study-wide ledger below is the brake

    def pedir(self, route, payload=None):
        import urllib.request
        req = urllib.request.Request("https://api.dataforseo.com/v3" + route, data=json.dumps(payload).encode(), headers=self.h)
        d = json.loads(urllib.request.urlopen(req, timeout=180).read())
        if d.get("status_code") != 20000:
            raise RuntimeError(f"API status {d.get('status_code')}: {d.get('status_message')}")
        return d


def client():
    if INHOUSE.exists():
        spec = importlib.util.spec_from_file_location("sa", str(INHOUSE))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m
    return _MiniClient()


sa = None   # set in main(): importing this module (or --help) no longer needs any private file

EST = {"aio": 0.004, "mode": 0.004}        # per-request estimate (USD); replaced by observed cost after the pilot
LOCK = threading.Lock()


def ledger():
    try:
        return json.loads(LEDGER.read_text())
    except (OSError, ValueError):
        return {"budget_usd": None, "total_usd": 0.0, "runs": []}


def payload(surface, q):
    if surface == "aio":
        return [{"keyword": q, "location_name": "Spain", "language_code": "es", "device": "desktop",
                 "depth": 10, "load_async_ai_overview": True}]
    return [{"keyword": q, "location_name": "Spain", "language_code": "es"}]


ROUTE = {"aio": "/serp/google/organic/live/advanced", "mode": "/serp/google/ai_mode/live/advanced"}


def refs_of(item):
    out, seen = [], set()
    cand = list(item.get("references") or [])
    for el in item.get("items") or []:
        cand.extend(el.get("references") or [])
    for r in cand:
        k = (r.get("domain"), r.get("url"))
        if k in seen:
            continue
        seen.add(k)
        out.append({"domain": r.get("domain"), "url": r.get("url"), "title": r.get("title"), "source": r.get("source")})
    return out


def text_of(item):
    if item.get("markdown"):
        return item["markdown"]
    parts = [item.get("text") or ""]
    for el in item.get("items") or []:
        parts.append(el.get("title") or "")
        parts.append(el.get("text") or el.get("markdown") or "")
    return "\n".join(p for p in parts if p).strip()


def extract(surface, d):
    t = (d.get("tasks") or [{}])[0]
    res = (t.get("result") or [None])[0] or {}
    items = res.get("items") or []
    ai = [it for it in items if it.get("type") == "ai_overview"]
    if surface == "mode" and not ai:
        # AI Mode answers are returned as a list of items; keep every textual one
        ai = [it for it in items if it.get("type") not in ("organic", "related_searches", "people_also_ask")]
    text = "\n\n".join(text_of(it) for it in ai).strip()
    refs = []
    for it in ai:
        refs.extend(refs_of(it))
    return {"task_status": t.get("status_code"), "task_message": t.get("status_message"),
            "item_types": sorted({it.get("type") for it in items}), "has_answer": bool(text),
            "text": text, "refs": refs, "cost": d.get("cost"), "check_url": res.get("check_url")}


def one(surface, row, reading, raw_dir):
    q = row["query"]
    t0 = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        d = sa.pedir(ROUTE[surface], payload(surface, q))
    except BaseException as e:      # serp-api exits via SystemExit on API errors; TopeDeGasto on cap
        return {"qid": row["qid"], "fact_id": row["fact_id"], "query": q, "surface": surface, "reading": reading,
                "fetched_at": t0, "error": f"{type(e).__name__}: {e}"[:300], "has_answer": None, "cost": 0.0}
    with gzip.open(raw_dir / f"{row['qid']}_{surface}.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
    ex = extract(surface, d)
    return {"qid": row["qid"], "fact_id": row["fact_id"], "query": q, "surface": surface, "reading": reading,
            "fetched_at": t0, **ex}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reading", type=int, required=True)
    ap.add_argument("--surfaces", default="aio,mode")
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--budget", type=float, default=4.50)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    global sa
    sa = client()

    rows = list(csv.DictReader(open(ROOT / "data/queries.csv", encoding="utf-8")))
    if a.only:
        keep = set(a.only.split(","))
        rows = [r for r in rows if r["qid"] in keep]
    if a.limit:
        rows = rows[:a.limit]
    surfaces = a.surfaces.split(",")
    L = ledger()
    obs = L.get("observed_cost", {})
    est = sum(obs.get(s, EST[s]) for s in surfaces) * len(rows)
    remaining = a.budget - L["total_usd"]
    print(f"reading {a.reading}: {len(rows)} queries × {surfaces} · estimate {est:.3f} USD · "
          f"study spend so far {L['total_usd']:.4f} / budget {a.budget:.2f}")
    if est > remaining:
        sys.exit(f"REFUSED: estimate {est:.3f} > remaining budget {remaining:.3f}")
    sa.fijar_tope(usd=min(remaining, est * 1.5 + 0.05))   # in-house per-run cap as a second brake

    raw_dir = ROOT / f"data/raw/reading{a.reading}"; raw_dir.mkdir(parents=True, exist_ok=True)
    out = ROOT / f"data/raw/responses/reading{a.reading}{a.tag}.jsonl"   # full answers: not redistributed; out.parent.mkdir(parents=True, exist_ok=True)
    spent, n_ok, n_err, results = 0.0, 0, 0, []
    jobs = [(s, r) for r in rows for s in surfaces]
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ThreadPoolExecutor(max_workers=a.workers) as ex, open(out, "a", encoding="utf-8") as fh:
        futs = {ex.submit(one, s, r, a.reading, raw_dir): (s, r) for s, r in jobs}
        for f in as_completed(futs):
            res = f.result()
            with LOCK:
                c = float(res.get("cost") or 0.0)
                spent += c
                if res.get("error"):
                    n_err += 1
                else:
                    n_ok += 1
                fh.write(json.dumps(res, ensure_ascii=False) + "\n"); fh.flush()
                results.append(res)
                if L["total_usd"] + spent > a.budget:
                    print("BUDGET REACHED — cancelling remaining jobs", file=sys.stderr)
                    for g in futs:
                        g.cancel()
    per = {}
    for s in surfaces:
        cs = [float(r.get("cost") or 0) for r in results if r["surface"] == s and not r.get("error")]
        if cs:
            per[s] = round(sum(cs) / len(cs), 6)
    L = ledger()
    L["budget_usd"] = a.budget
    L["total_usd"] = round(L["total_usd"] + spent, 6)
    L.setdefault("observed_cost", {}).update(per)
    L["runs"].append({"reading": a.reading, "tag": a.tag, "started_utc": started,
                      "ended_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "requests_ok": n_ok, "requests_error": n_err, "usd": round(spent, 6), "per_request": per})
    LEDGER.write_text(json.dumps(L, indent=1))
    ans = {s: sum(1 for r in results if r["surface"] == s and r.get("has_answer")) for s in surfaces}
    print(f"done: ok={n_ok} err={n_err} spent={spent:.4f} USD · study total {L['total_usd']:.4f} USD · answers {ans}")


if __name__ == "__main__":
    main()
