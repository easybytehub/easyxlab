#!/usr/bin/env python3
"""Polite fetcher for S13 (copied from S11): robots.txt (RFC 9309) checked before every request, at most one
request per second per host (or the host's Crawl-delay, if larger), a fixed User-Agent, and a
log of every request.

The per-host clock is shared by all processes under a file lock; robots.txt is cached on disk
for 24 hours; the robots.txt request waits like any other; a declared Crawl-delay is
remembered across processes; the log records the time each request is sent, in milliseconds.

    python3 scripts/polite.py URL OUT_PATH [--accept MIME]

robots.txt handling (RFC 9309 s. 2.3.1): 2xx -> parse whatever the Content-Type (an HTML page
with no parseable rules allows everything; one that does contain rules is followed);
4xx -> no restrictions; 5xx or network error -> complete disallow. Redirects are followed
(up to 5) and robots.txt is checked again on every host the redirect reaches.
Standard library only (robots9309.py is copied from study S8).
"""
import os, sys, time, json, fcntl, urllib.request, urllib.error
from urllib.parse import urlsplit, urljoin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import robots9309 as R

UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
TOKEN = "EasyxLab-research"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(HERE, "work", "fetch_log.jsonl")
STATE = os.path.join(HERE, "work", ".last_request.json")   # per-host last-request time, shared by processes
LOCK = STATE + ".lock"
RCACHE = os.path.join(HERE, "work", "robots_cache")
RCACHE_TTL = 24 * 3600


def _now():
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t)) + f".{int(t % 1 * 1000):03d}" + time.strftime("%z")
_robots = {}
_delay = {}


def crawl_delay(body, token=TOKEN):
    """Crawl-delay for our token (else '*'), read leniently; RFC 9309 does not define it, but
    sites state it and we honour it."""
    import re
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    agents, in_rules, found = [], False, {}
    for raw in re.split(r"\r\n|\r|\n", text):
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = [x.strip() for x in line.split(":", 1)]
        k = k.lower()
        if k == "user-agent":
            if in_rules:
                agents, in_rules = [], False
            agents.append(R.product_token(v))
        else:
            in_rules = True
            if k == "crawl-delay":
                try:
                    for a in agents:
                        found[a] = float(v)
                except ValueError:
                    pass
    t = token.lower()
    return found.get(t, found.get("*", 0.0))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(NoRedirect)


def _wait(host):
    """Block until this host may be contacted again; the clock is shared by every process."""
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(LOCK, "a+") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            st = json.load(open(STATE))
        except Exception:
            st = {}
        delays = st.setdefault("_crawl_delay", {})
        if host in _delay:
            delays[host] = _delay[host]
        gap = max(1.05, _delay.get(host, 0.0), float(delays.get(host, 0.0)))
        d = time.time() - float(st.get(host, 0))
        if d < gap:
            time.sleep(gap - d)
        st[host] = time.time()
        tmp = STATE + ".tmp"
        json.dump(st, open(tmp, "w"))
        os.replace(tmp, STATE)


def _log(rec):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


_t_start = None


def _raw(url, accept=None, timeout=120, extra=None):
    global _t_start
    host = urlsplit(url).netloc
    _wait(host)
    _t_start = _now()   # the time the request is sent: this is what the log records
    h = {"User-Agent": UA, "Accept": accept or "*/*"}
    h.update(extra or {})
    req = urllib.request.Request(url, headers=h)
    try:
        r = _opener.open(req, timeout=timeout)
        return r.status, {k.lower(): v for k, v in r.headers.items()}, r
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e


def _robots_from(status, body, netloc):
    if isinstance(status, int) and 200 <= status < 300:
        groups = R.parse(body); verdict = "parsed"
        cd = crawl_delay(body)
        if cd:
            _delay[netloc] = cd
    elif isinstance(status, int) and 400 <= status < 500:
        groups = []; verdict = "4xx-allow-all"
    else:
        groups = None; verdict = "unreachable-disallow-all"
    return groups, verdict


def robots_for(url):
    p = urlsplit(url)
    key = f"{p.scheme}://{p.netloc}"
    if key in _robots:
        return _robots[key]
    cf = os.path.join(RCACHE, key.replace("://", "_").replace(":", "_") + ".json")
    try:
        c = json.load(open(cf))
        if time.time() - c["fetched"] < RCACHE_TTL:
            groups, verdict = _robots_from(c["status"], c["body"].encode("utf-8"), p.netloc)
            _robots[key] = (groups, verdict, c["status"])
            return _robots[key]
    except Exception:
        pass
    rurl = key + "/robots.txt"
    status, body, hops = None, b"", 0
    try:
        while hops < 5:
            status, headers, resp = _raw(rurl, timeout=30)
            if status in (301, 302, 303, 307, 308) and headers.get("location"):
                rurl = urljoin(rurl, headers["location"]); hops += 1; continue
            body = resp.read() if status and 200 <= status < 300 else b""
            break
    except Exception as e:
        status = f"error:{type(e).__name__}"
    groups, verdict = _robots_from(status, body, p.netloc)
    _robots[key] = (groups, verdict, status)
    os.makedirs(RCACHE, exist_ok=True)
    json.dump({"fetched": time.time(), "status": status, "body": body.decode("utf-8", "replace")}, open(cf, "w"))
    _log({"t": _t_start, "url": key + "/robots.txt", "status": status,
          "robots": verdict, "has_groups": bool(groups and R.has_groups(groups))})
    return _robots[key]


def allowed(url):
    groups, verdict, status = robots_for(url)
    if groups is None:
        return False, verdict
    return R.allowed(groups, TOKEN, url), verdict


def fetch(url, out, accept=None, max_redirects=5, extra=None):
    """Download url to out. Returns (status, final_url). Raises PermissionError if robots.txt
    does not allow the URL (or any redirect target)."""
    cur = url
    for _ in range(max_redirects + 1):
        ok, verdict = allowed(cur)
        if not ok:
            _log({"t": _now(), "url": cur, "status": "skipped-robots", "robots": verdict})
            raise PermissionError(f"robots.txt does not allow {cur} ({verdict})")
        status, headers, resp = _raw(cur, accept, extra=extra)
        _log({"t": _t_start, "url": cur, "status": status, "robots": verdict})
        if status in (301, 302, 303, 307, 308) and headers.get("location"):
            cur = urljoin(cur, headers["location"]); continue
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        tmp = out + ".part"
        with open(tmp, "wb") as f:
            while True:
                b = resp.read(1 << 20)
                if not b:
                    break
                f.write(b)
        if isinstance(status, int) and 200 <= status < 300:
            os.replace(tmp, out)
        else:
            os.replace(tmp, out + f".http{status}")
        return status, cur
    raise RuntimeError("too many redirects")


if __name__ == "__main__":
    a = sys.argv[1:]
    acc = None
    extra = {}
    while "--header" in a:
        i = a.index("--header"); k, v = a[i + 1].split(":", 1); extra[k.strip()] = v.strip(); del a[i:i + 2]
    if "--accept" in a:
        i = a.index("--accept"); acc = a[i + 1]; del a[i:i + 2]
    try:
        st, final = fetch(a[0], a[1], acc, extra=extra)
        print(st, final)
        sys.exit(0 if isinstance(st, int) and st < 400 else 1)
    except PermissionError as e:
        print("ROBOTS:", e); sys.exit(3)


def open_stream(url, accept=None):
    """Like fetch() but returns the open response (after robots.txt and rate checks) so the
    caller can filter it while streaming, without writing the full body to disk."""
    cur = url
    for _ in range(6):
        ok, verdict = allowed(cur)
        if not ok:
            _log({"t": _now(), "url": cur, "status": "skipped-robots", "robots": verdict})
            raise PermissionError(f"robots.txt does not allow {cur} ({verdict})")
        status, headers, resp = _raw(cur, accept)
        _log({"t": _t_start, "url": cur, "status": status, "robots": verdict, "streamed": True})
        if status in (301, 302, 303, 307, 308) and headers.get("location"):
            cur = urljoin(cur, headers["location"]); continue
        if not (isinstance(status, int) and 200 <= status < 300):
            raise RuntimeError(f"HTTP {status} for {cur}")
        return resp
    raise RuntimeError("too many redirects")
