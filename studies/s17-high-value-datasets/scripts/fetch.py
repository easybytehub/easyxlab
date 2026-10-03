# SPDX-License-Identifier: Apache-2.0
"""Single fetch helper for S17. Every network request of the study goes through `get()`.

Rules enforced in code (house standard, rule 2):
  * robots.txt of the host is read BEFORE the first request to that host, and honoured
    (urllib.robotparser, our User-Agent). A robots.txt served as HTML, or one whose comments
    forbid robots in natural language, is flagged and the host is skipped.
  * <= 1 request/second per host (the robots.txt fetch counts).
  * Optional Range (<= 2 KB) or HEAD; responses are never read beyond `max_bytes`.
Every request is logged (timestamp, method, url, status) to work/requests.log.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field

UA = "EasyxLab-research/0.1 (+https://easybyte.es/lab/; contact@easybyte.es)"
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(os.path.dirname(HERE), "work")
os.makedirs(WORK, exist_ok=True)
LOG = os.path.join(WORK, "requests.log")

_ROBOTS: dict[str, "RobotsState"] = {}
_LAST: dict[str, float] = {}
_HOSTLOCK: dict[str, threading.Lock] = {}
_GLOBAL = threading.Lock()
_LOGLOCK = threading.Lock()
MIN_INTERVAL = 1.0
NL_FORBID = re.compile(r"#.*\b(no|not|forbid|prohibit|disallow)\w*\b.*\b(robot|crawl|scrap|bot|automat)", re.I)

_CTX = ssl.create_default_context()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # redirects are followed by get(), so every hop is checked against robots.txt


_OPENER = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=_CTX))


@dataclass
class Resp:
    url: str
    status: int | None
    headers: dict = field(default_factory=dict)
    body: bytes = b""
    error: str | None = None
    final_url: str | None = None
    skipped: str | None = None  # 'robots' | 'robots-unavailable' | 'nl-reservation'


@dataclass
class RobotsState:
    parser: urllib.robotparser.RobotFileParser | None
    status: int | None
    note: str  # 'ok' | 'absent' | 'html' | 'nl-reservation' | 'error:<x>' | 'server-error'


def _log(method, url, status, extra=""):
    with _LOGLOCK, open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\t{method}\t{status}\t{url}\t{extra}\n")


def _hostkey(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return f"{p.scheme}://{p.netloc}".lower()


def _pace(host: str):
    with _GLOBAL:
        lock = _HOSTLOCK.setdefault(host, threading.Lock())
    lock.acquire()
    try:
        wait = MIN_INTERVAL - (time.time() - _LAST.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _LAST[host] = time.time()
    finally:
        lock.release()


def _raw(url, method="GET", headers=None, max_bytes=2048, timeout=20, data=None):
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    req = urllib.request.Request(url, method=method, headers=h, data=data)
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            body = r.read(max_bytes) if method != "HEAD" and max_bytes else b""
            return Resp(url, r.status, dict(r.headers), body, None, r.geturl())
    except urllib.error.HTTPError as e:
        try:
            body = e.read(max_bytes) if max_bytes else b""
        except Exception:
            body = b""
        return Resp(url, e.code, dict(e.headers or {}), body, None, url)
    except Exception as e:  # DNS, TLS, timeout, connection reset
        return Resp(url, None, {}, b"", f"{type(e).__name__}: {str(e)[:160]}", url)


def robots_for(url: str) -> RobotsState:
    host = _hostkey(url)
    with _GLOBAL:
        st = _ROBOTS.get(host)
    if st:
        return st
    # RFC 9309 2.3.1.2: follow at least five consecutive redirects for robots.txt (added after the
    # 2026-10-03 run, deviation D5; before, a 3xx robots.txt was parsed as allow-all).
    url = host + "/robots.txt"
    for _ in range(6):
        _pace(_hostkey(url))
        r = _raw(url, max_bytes=512 * 1024, timeout=20)
        _log("GET", url, r.status, r.error or "robots")
        loc = r.headers.get("Location") or r.headers.get("location")
        if r.status in (301, 302, 303, 307, 308) and loc:
            url = urllib.parse.urljoin(url, loc)
            continue
        break
    else:
        r = Resp(url, None, error="robots-too-many-redirects")
    rp = urllib.robotparser.RobotFileParser()
    text = r.body.decode("utf-8", "replace")
    if r.status is None:
        st = RobotsState(None, None, f"error:{r.error}")
    elif 400 <= r.status < 500:
        rp.parse([])  # RFC 9309 2.3.1.3: unavailable -> MAY access
        st = RobotsState(rp, r.status, "absent")
    elif r.status >= 500:
        st = RobotsState(None, r.status, "server-error")  # RFC 9309: assume complete disallow
    elif "<html" in text[:500].lower() or "<!doctype" in text[:200].lower():
        rp.parse([])
        st = RobotsState(rp, r.status, "html")
    else:
        lines = text.splitlines()
        if any(NL_FORBID.search(l) for l in lines if l.strip().startswith("#")):
            st = RobotsState(None, r.status, "nl-reservation")
        else:
            rp.parse(lines)
            st = RobotsState(rp, r.status, "ok")
    with _GLOBAL:
        _ROBOTS[host] = st
    return st


def allowed(url: str) -> tuple[bool, str]:
    st = robots_for(url)
    if st.parser is None:
        if st.note.startswith("error"):
            return False, "robots-unavailable"
        if st.note == "server-error":
            return False, "robots-unavailable"
        return False, st.note
    return (st.parser.can_fetch(UA, url) and st.parser.can_fetch("*", url)), "robots"


def get(url, method="GET", headers=None, max_bytes=2048, timeout=20, data=None, check_robots=True,
        max_redirects=5) -> Resp:
    """The only way the study touches the network. Redirects are followed here, hop by hop,
    and every hop goes through the robots.txt check of its own host."""
    first = url
    hops = []
    for _ in range(max_redirects + 1):
        if check_robots:
            ok, why = allowed(url)
            if not ok:
                _log(method, url, "SKIP", why)
                r = Resp(first, None, skipped=why, final_url=url)
                r.headers["x-hops"] = json.dumps(hops)
                return r
        _pace(_hostkey(url))
        r = _raw(url, method, headers, max_bytes, timeout, data)
        _log(method, url, r.status, r.error or "")
        if r.status in (301, 302, 303, 307, 308) and (r.headers.get("Location") or r.headers.get("location")):
            loc = r.headers.get("Location") or r.headers.get("location")
            hops.append([r.status, url])
            url = urllib.parse.urljoin(url, loc)
            if r.status == 303:
                method = "GET" if method != "HEAD" else "HEAD"
            continue
        r.url = first
        r.final_url = url
        r.headers["x-hops"] = json.dumps(hops)
        return r
    return Resp(first, None, error="too-many-redirects", final_url=url)


def get_json(url, max_bytes=200 * 1024 * 1024, timeout=120):
    r = get(url, headers={"Accept": "application/json"}, max_bytes=max_bytes, timeout=timeout)
    if r.status != 200:
        raise RuntimeError(f"{url}: {r.status} {r.error} {r.skipped}")
    return json.loads(r.body)
