#!/usr/bin/env python3
"""The single HTTP helper every S16 request goes through (scan, population, sources, provider docs).

Rules enforced in code, not left to the operator:
  * robots.txt (RFC 9309) is read before ANY other request to a host; every request, redirect hops
    included, is checked against the robots.txt of the host it enters. The body is parsed whatever
    Content-Type it is served with (s. 2.3.1.1); 4xx = no restrictions (s. 2.3.1.3); 5xx or no
    answer = complete disallow (s. 2.3.1.4).
  * If the robots.txt comments forbid robots / automated access in natural language
    (nlcomments.prohibition), NO further request is made to that host (state 'nl_prohibition').
  * At most one request per second per host; a per-host budget of resource fetches.
  * Hosts in NEVER_FETCH are never requested by script (contentsignals.org: its robots.txt objects).

Adapted from the Session class of EasyxLab study S8 (scripts/scan.py), Apache-2.0. Standard library only.
"""
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import nlcomments
import robots9309 as R

UA = "EasyxLab-research/0.1 (+https://easybyte.es/lab/; contact@easybyte.es)"
TIMEOUT = 15
MAX_HOPS = 5
MIN_INTERVAL = 1.0
REDIRECTS = (301, 302, 303, 307, 308)
NEVER_FETCH = {"contentsignals.org", "www.contentsignals.org"}


def product_token_of(ua):
    m = re.match(r"[A-Za-z_-]+", ua.strip())
    if not m:
        raise SystemExit("the User-Agent must start with a product token")
    return m.group(0)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_ctx = ssl.create_default_context()
_opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=_ctx))


def authority(url):
    p = urlsplit(url)
    h = (p.hostname or "").lower().rstrip(".")
    try:
        port = p.port
    except ValueError:
        port = None
    if port and not ((p.scheme == "http" and port == 80) or (p.scheme == "https" and port == 443)):
        return f"{h}:{port}"
    return h


def decode_body(body, hdrs):
    enc = hdrs.get("content-encoding", "").lower()
    if body[:2] == b"\x1f\x8b" or "gzip" in enc or "deflate" in enc:
        for wbits in (16 + zlib.MAX_WBITS, zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                return zlib.decompressobj(wbits).decompress(body, 8_000_000)
            except zlib.error:
                continue
    return body


class _Host:
    def __init__(self):
        self.lock = threading.Lock()
        self.last = 0.0
        self.fetches = 0
        self.requests = 0


class Session:
    def __init__(self, user_agent=UA, per_host=8, min_interval=MIN_INTERVAL, extra_headers=None):
        self.ua = user_agent
        self.token = product_token_of(user_agent)
        self.per_host = per_host
        self.min_interval = min_interval
        self.extra = extra_headers or {}
        self._hosts, self._robots = {}, {}
        self._lock = threading.Lock()
        self.log = []          # (utc, method, url, status|error) for every request sent

    def _host(self, h):
        with self._lock:
            if h not in self._hosts:
                self._hosts[h] = _Host()
            return self._hosts[h]

    def _reserve(self, h):
        st = self._host(h)
        with st.lock:
            if st.fetches >= self.per_host:
                return False
            st.fetches += 1
            return True

    def _pace(self, h):
        st = self._host(h)
        with st.lock:
            wait = st.last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            st.last = time.monotonic()
            st.requests += 1

    def max_requests_per_host(self):
        return max((s.requests for s in self._hosts.values()), default=0)

    def _one(self, url, method, limit, headers, decode=True):
        h = {"User-Agent": self.ua, "Accept": "*/*", "Accept-Language": "en;q=0.8,*;q=0.5"}
        h.update(self.extra)
        h.update(headers or {})
        req = urllib.request.Request(url, headers=h, method=method)
        try:
            r = _opener.open(req, timeout=TIMEOUT)
        except urllib.error.HTTPError as e:
            r = e
        body = b""
        try:
            if method != "HEAD" and r.fp:
                body = r.read(limit)
        except Exception:  # noqa: BLE001
            pass
        hdrs = {}
        for k, v in (r.headers.items() if r.headers else []):
            k = k.lower()
            hdrs[k] = (hdrs[k] + ", " + v) if k in hdrs else v
        status = getattr(r, "status", None) or r.code
        return status, hdrs, (decode_body(body, hdrs) if decode else body)

    def get(self, url, limit=1_000_000, robots=True, method="GET", headers=None, decode=True):
        """GET (or HEAD) with redirects followed by us; every hop is checked against robots.txt of
        the host it enters (fetched first if needed). robots=False only for /robots.txt itself."""
        out = dict(url=url, status=None, final_url=url, hops=0, error=None, headers={}, body=b"")
        cur, entered = url, set()
        for hop in range(MAX_HOPS + 1):
            h = authority(cur)
            if not h or h in NEVER_FETCH:
                out.update(error="never_fetch" if h else "bad_url", final_url=cur)
                return out
            # robots=False exempts only the first host (its own /robots.txt); a redirect to another
            # host is checked against that host's robots.txt like any other request
            if (robots or h != authority(url)) and not self.allowed(h, cur):
                out.update(error="robots_disallowed", final_url=cur)
                return out
            if h not in entered:
                if not self._reserve(h):
                    out.update(error="host_budget", final_url=cur)
                    return out
                entered.add(h)
            self._pace(h)
            t0 = datetime.now(timezone.utc).isoformat(timespec="seconds")   # request start, for the log
            try:
                st, hd, body = self._one(cur, method, limit, headers, decode)
            except urllib.error.URLError as e:
                out["error"] = "URLError:" + (type(e.reason).__name__ if not isinstance(e.reason, str) else e.reason)[:60]
                self.log.append((t0, method, cur, out["error"]))
                return out
            except (socket.timeout, TimeoutError):
                out["error"] = "timeout"
                self.log.append((t0, method, cur, "timeout"))
                return out
            except Exception as e:  # noqa: BLE001
                out["error"] = type(e).__name__
                self.log.append((t0, method, cur, out["error"]))
                return out
            self.log.append((t0, method, cur, st))
            out.update(status=st, headers=hd, body=body, final_url=cur, hops=hop)
            if st in REDIRECTS and hd.get("location"):
                cur = urljoin(cur, hd["location"].strip())
                continue
            return out
        out["error"] = "too_many_redirects"
        return out

    # ------------------------------------------------------------ robots.txt
    def robots_for(self, h):
        with self._lock:
            rb = self._robots.get(h)
            owner = rb is None
            if owner:
                rb = self._robots[h] = {"event": threading.Event()}
        if not owner:
            rb["event"].wait(600)
            return rb
        try:
            rb.update(self._fetch_robots(h))
        finally:
            rb["event"].set()
        return rb

    def _fetch_robots(self, h):
        d = dict(state="unreachable", status=None, error=None, content_type="", body=b"", groups=[],
                 final_url="", fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 nl={}, scheme=None)
        res = self.get(f"https://{h}/robots.txt", limit=R.PARSE_LIMIT, robots=False)
        d["scheme"] = "https"
        if res["error"] and res["error"] not in ("host_budget", "never_fetch"):
            res = self.get(f"http://{h}/robots.txt", limit=R.PARSE_LIMIT, robots=False)
            d["scheme"] = "http"
        st = res["status"]
        d.update(status=st, error=res["error"], final_url=res["final_url"],
                 content_type=res["headers"].get("content-type", "")[:80])
        if res["error"] or st is None:
            d["state"] = "unreachable"
        elif 200 <= st < 300:
            d["body"] = res["body"]
            d["groups"] = R.parse(res["body"])
            d["nl"] = nlcomments.scan(res["body"])
            d["state"] = "nl_prohibition" if d["nl"]["nl_prohibition"] else "ok"
        elif 400 <= st < 500:
            d["state"] = "unavailable"
        else:
            d["state"] = "unreachable"
        return d

    def allowed(self, h, url):
        rb = self.robots_for(h)
        if rb.get("state") == "ok":
            return R.allowed(rb["groups"], self.token, url)
        return rb.get("state") == "unavailable"


def text_of(res):
    b = res["body"] or b""
    ct = res["headers"].get("content-type", "")
    m = re.search(r"charset=([\w-]+)", ct, re.I)
    enc = m.group(1) if m else None
    if not enc:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', b[:4000], re.I)
        enc = m.group(1).decode() if m else "utf-8"
    try:
        return b.decode(enc, "replace")
    except LookupError:
        return b.decode("utf-8", "replace")


if __name__ == "__main__":
    import sys
    s = Session()
    for host in sys.argv[1:]:
        rb = s.robots_for(host)
        print(host, rb["state"], rb["status"], rb["error"], "allowed /:", s.allowed(host, f"https://{host}/"),
              "| nl:", (rb.get("nl") or {}).get("nl_prohibition_evidence", ""))
