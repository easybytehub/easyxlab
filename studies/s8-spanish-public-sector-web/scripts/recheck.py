#!/usr/bin/env python3
"""One-off re-checks made on 2026-10-02 to correct the first measurement (see METHOD.md s. 6).

Runs with scanner version 2's Session: robots.txt honoured for every request (redirect hops
included), at most four resource fetches per host over all phases together (robots.txt
included; the counters are saved in data/raw/recheck_budget.json so that a restart does not
reset them), at most one request per second per host. User-Agent:
EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab).

Phases (each reads the earlier ones' output from data/raw/):
  robots      re-read /robots.txt of every host the first scan or the pilot sent a request to
              -> robots_snapshot.jsonl (parsed rules only, no comments, no body)
  homes       re-fetch the home pages whose identity or accessibility link needs checking
              (name not found, near-empty page, other domain, hosting-panel path, widget link)
              -> recheck_home.jsonl (markers, title, link; no body)
  statements  re-read with extractor v2 the 116 statements whose v1 date v2 rejected on its
              stored sentence -> recheck_statement.jsonl
  sectxt      re-fetch /.well-known/security.txt where the first scan found a file or a
              "soft 404" -> recheck_sectxt.jsonl (booleans only, never Contact values)
  gzip        second look, decoding compressed bodies a server sent unasked, at robots.txt
              files that parsed to no rules and at re-checked pages with no title
Nothing that robots.txt disallows for our token is requested, and nothing is re-fetched for
an entity whose first-scan record is discarded by the robots audit.
"""
import argparse, json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan as S  # noqa: E402
import audit_robots as A  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
SCAN_DATE = date(2026, 10, 2)
BUDGET = os.path.join(RAW, "recheck_budget.json")


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def load_records():
    main = {}
    for r in load_jsonl(os.path.join(RAW, "scan.jsonl")):
        main.setdefault(r["entity_id"], r)       # two REL duplicates: keep the first record
    p2 = {r["entity_id"]: r for r in load_jsonl(os.path.join(RAW, "scan_sec_pass2.jsonl"))}
    return main, p2


def session():
    s = S.Session(S.EASYXLAB_UA)
    if os.path.exists(BUDGET):
        for h, n in json.load(open(BUDGET)).items():
            s.host_state(h).fetches = n
    snap = os.path.join(RAW, "robots_snapshot.jsonl")
    for d in load_jsonl(snap):
        ev = threading.Event()
        ev.set()
        s._robots[d["host"]] = dict(d, event=ev)
    return s


def save_budget(s):
    json.dump({h: st.fetches for h, st in s._hosts.items()}, open(BUDGET, "w"))


def run_parallel(items, fn, out_path, workers=48):
    done = {json.loads(l)["key"] for l in open(out_path)} if os.path.exists(out_path) else set()
    todo = [x for x in items if x[0] not in done]
    print(f"{len(todo)} to do ({len(done)} done) -> {os.path.basename(out_path)}", file=sys.stderr)
    lock, t0 = threading.Lock(), time.time()
    with open(out_path, "a", encoding="utf-8") as f, ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fn, x): x for x in todo}
        for i, fu in enumerate(as_completed(futs), 1):
            x = futs[fu]
            try:
                r = fu.result()
            except Exception as exc:  # noqa: BLE001
                r = {"error": f"exception:{type(exc).__name__}"}
            r.update(key=x[0], checked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            with lock:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
                f.flush()
            if i % 500 == 0:
                print(f"  {i}/{len(todo)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


# ---------------------------------------------------------------- phase 1: robots.txt
def pilot_hosts():
    p = os.path.join(ROOT, "pilot", "muni_sample.json")
    return json.load(open(p)) if os.path.exists(p) else []


def phase_robots(s):
    main, p2 = load_records()
    hosts = set()
    for eid, r in main.items():
        hosts.add(r["host"])
        for _, h, _ in A.requests_of(r, p2.get(eid)):
            hosts.add(h)
    for r in load_jsonl(os.path.join(RAW, "scan_test.jsonl")):
        hosts.add(r["host"])
        for _, h, _ in A.requests_of(r):
            hosts.add(h)
    hosts.update(h.lower() for h in pilot_hosts())
    hosts.discard("")
    out = os.path.join(RAW, "robots_snapshot.jsonl")

    def go(x):
        d = s.robots_for(x[0])
        return {k: v for k, v in d.items() if k != "event"} | {"host": x[0]}
    run_parallel([(h,) for h in sorted(hosts)], go, out)
    save_budget(s)


# ---------------------------------------------------------------- audit helpers
def snapshot():
    return {d["host"]: d for d in load_jsonl(os.path.join(RAW, "robots_snapshot.jsonl"))}


def kept(rec, p2, snap):
    """record kinds that survive the robots audit"""
    a = A.audit(rec, p2, snap)
    return a, a.get("home", "allowed") == "allowed"


def reg(h):
    h = (h or "").split(":")[0]
    parts = h.split(".")
    k = 3 if len(parts) >= 3 and parts[-2] in ("gob", "com", "org", "edu", "nom", "net") else 2
    return ".".join(parts[-k:])


# ---------------------------------------------------------------- phase 2: home pages
def home_targets(main, p2, snap):
    out = []
    for eid, r in main.items():
        if not (r.get("home_status") == 200 and r.get("home_html")):
            continue
        a, ok = kept(r, p2.get(eid), snap)
        if not ok:
            continue
        acc_host = A.host_of(r.get("acc_url"))
        why = []
        if not r.get("home_name_match"):
            why.append("name_not_found")
        if r.get("home_js_shell"):
            why.append("small_page")
        if reg(A.host_of(r.get("home_final"))) != reg(r["host"]):
            why.append("other_domain")
        if re.search(r"login_up\.php|:\d+/", r.get("home_final", "")):
            why.append("panel_path")
        if acc_host and S.ACC_VENDOR.search(acc_host):
            why.append("widget_link")
        if why:
            out.append((eid, r, why))
    return out


def home_check(s, eid, r, why, name):
    res = s.get(r["url"].replace("http://", "https://", 1) if r.get("home_https") else r["url"])
    d = dict(entity_id=eid, why=why, status=res["status"], error=res["error"], final_url=res["final_url"],
             blocked_host=res["blocked_host"], decompressed=res["headers"].get("x-s8-decompressed") == "1")
    if res["status"] == 200 and S.is_html(res):
        page = S.text(res)
        t = S.norm(S.page_text(page))
        runs = S.name_runs(name)
        d.update(S.page_markers(page, res["final_url"]),
                 name_match=S.homepage_name_match(page, name),
                 name_in_text=S.name_in_text(t, runs), name_in_url=S.name_in_url(res["final_url"], runs),
                 js_shell=S.is_shell(page), text_len=len(S.page_text(page).strip()))
        acc, says = S.find_accessibility_link(page, res["final_url"])
        d.update(acc_link=bool(acc), acc_url=acc or "", acc_link_says_statement=says)
    return d


def phase_homes(s, population):
    main, p2 = load_records()
    snap = snapshot()
    names = {p["entity_id"]: p["name"] for p in population}
    targets = home_targets(main, p2, snap)

    def go(x):
        return home_check(s, x[1], x[2], x[3], names.get(x[1], ""))
    run_parallel([(t[0], t[0], t[1], t[2]) for t in targets], go, os.path.join(RAW, "recheck_home.jsonl"))
    save_budget(s)


def phase_gzip(s, population):
    """Second look, with compressed bodies decoded, at (a) robots.txt files that parsed to no
    rules although not HTML, and (b) re-checked home pages with no title and no council word:
    some servers send gzip without being asked, which the first passes read as binary."""
    names = {p["entity_id"]: p["name"] for p in population}
    sp = os.path.join(RAW, "robots_snapshot.jsonl")
    snap = load_jsonl(sp)
    changed = 0
    for d in snap:
        if d["state"] == "ok" and not d["has_groups"] and not d["html_typed"] and s.host_state(d["host"]).fetches < 4:
            res = s.get(f"http://{d['host']}/robots.txt", limit=S.R.PARSE_LIMIT, robots=False)
            if res["headers"].get("x-s8-decompressed") == "1" and res["status"] and 200 <= res["status"] < 300:
                g = S.R.parse(res["body"])
                d.update(groups=g, has_groups=S.R.has_groups(g), gzip=True)
                changed += 1
    with open(sp, "w", encoding="utf-8") as f:
        for d in snap:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"robots.txt decoded from unrequested gzip: {changed}", file=sys.stderr)
    hp = os.path.join(RAW, "recheck_home.jsonl")
    rows = load_jsonl(hp)
    main, _ = load_records()
    n = 0
    for i, d in enumerate(rows):
        if d.get("status") == 200 and not d.get("home_title") and not d.get("home_council_word"):
            host = (urlsplit(d["final_url"]).hostname or "").lower()
            if s.host_state(host).fetches >= 4:
                continue
            e = d["entity_id"]
            nd = home_check(s, e, main[e], d["why"], names.get(e, ""))
            nd.update(key=d["key"], checked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), second_look=True)
            rows[i] = nd
            n += 1
    with open(hp, "w", encoding="utf-8") as f:
        for d in rows:
            f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
    print(f"home pages looked at again: {n}; decompressed: {sum(1 for d in rows if d.get('decompressed'))}", file=sys.stderr)
    save_budget(s)


# ---------------------------------------------------------------- phase 3: v1-rejected statements
def v1_rejected(main, p2, snap):
    order = [json.loads(l)["entity_id"] for l in open(os.path.join(RAW, "scan.jsonl"), encoding="utf-8")]
    first_run = set(order[:586])
    out = []
    for eid, r in main.items():
        if eid in first_run or r.get("stmt_extractor") == "v2" or not r.get("stmt_date_context"):
            continue
        if S.statement_dates(r["stmt_date_context"], SCAN_DATE):
            continue
        a, ok = kept(r, p2.get(eid), snap)
        if ok and a.get("stmt", "allowed") == "allowed":
            out.append((eid, r))
    return out


def phase_statements(s):
    main, p2 = load_records()
    snap = snapshot()
    targets = v1_rejected(main, p2, snap)

    def go(x):
        eid, r = x[1], x[2]
        res = s.get(r["acc_url"])
        d = dict(entity_id=eid, error=res["error"], final_url=res["final_url"])
        if res["error"] not in ("robots_disallowed", "host_budget"):
            d.update(S.check_statement(res, SCAN_DATE))
        return d
    run_parallel([(t[0], t[0], t[1]) for t in targets], go, os.path.join(RAW, "recheck_statement.jsonl"))
    save_budget(s)


# ---------------------------------------------------------------- phase 4: security.txt
def phase_sectxt(s):
    main, p2 = load_records()
    snap = snapshot()
    hosts = {}
    for eid, r in main.items():
        src = r
        if p2.get(eid) and "sectxt_status" in p2[eid] and "sectxt_present" not in r:
            src = p2[eid]
        if not (src.get("sectxt_present") or src.get("sectxt_soft404")):
            continue
        a, ok = kept(r, p2.get(eid), snap)
        kind = "sectxt_pass2" if src is not r else "sectxt"
        if (src is r and not ok) or a.get(kind, "allowed") != "allowed":
            continue
        hosts.setdefault(src.get("sectxt_host") or r["host"], []).append(eid)

    def go(x):
        h = x[0]
        res = s.get(f"https://{h}/.well-known/security.txt", limit=64_000)
        d = dict(host=h, entities=x[1], error=res["error"], http_status=res["status"])
        if res["error"] not in ("robots_disallowed", "host_budget"):
            d.update(S.check_security_txt(res))
        return d
    run_parallel(sorted(hosts.items()), go, os.path.join(RAW, "recheck_sectxt.jsonl"))
    save_budget(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["robots", "homes", "statements", "sectxt", "gzip"])
    a = ap.parse_args()
    import csv
    population = list(csv.DictReader(open(os.path.join(ROOT, "data", "population.csv"), encoding="utf-8")))
    s = session()
    if a.phase == "robots":
        phase_robots(s)
    elif a.phase == "homes":
        phase_homes(s, population)
    elif a.phase == "statements":
        phase_statements(s)
    elif a.phase == "gzip":
        phase_gzip(s, population)
    else:
        phase_sectxt(s)
    hosts, mx, mr = s.stats()
    print(f"hosts touched {hosts}; max fetches/host {mx}; max requests/host this process {mr}", file=sys.stderr)


if __name__ == "__main__":
    main()
