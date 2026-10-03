"""Single polite fetch helper for S15. Every network request of the study goes through `Fetcher.get`.

Rules enforced in code (EasyxLab house standard):
  * robots.txt of a host is read BEFORE the first other request to that host, and honoured
    (also when served as HTML or with odd status codes);
  * comments in robots.txt that forbid robots/scraping count as a reservation: the host is skipped;
  * at most 1 request per second per host;
  * fixed, identifying User-Agent;
  * streamed downloads with a size cap; the body is hashed and may be deleted after processing.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import requests

try:
    from . import robots9309  # type: ignore
except ImportError:
    import robots9309  # noqa: E402

UA = "EasyxLab-research/0.1 (+https://easybyte.es/lab/; contact@easybyte.es)"
UA_TOKEN = "EasyxLab-research"
MIN_INTERVAL = 1.0  # seconds between requests to the same host
TIMEOUT = (15, 60)
MAX_SECONDS = 180  # total time for one body
MAX_BYTES = 60 * 1024 * 1024
RFC9309_4XX = True  # deviation D1 (METHOD.md): 4xx on robots.txt = no rules, as RFC 9309; False = frozen rule

# Natural-language reservations in robots.txt comments. Conservative: any hit -> skip host.
RESERVATION_RE = re.compile(
    r"(prohibit|forbid|not (?:be )?(?:allowed|permitted|authori[sz]ed)|unauthori[sz]ed|"
    r"no (?:scraping|crawling|robots|bots)|do not (?:crawl|scrape)|scraping is|crawling is|"
    r"data mining|text and data mining|tdm)",
    re.I,
)


@dataclass
class RobotsInfo:
    host: str
    status: str  # ok | absent | blocked-fetch | error | reserved
    reservation_comments: list[str] = field(default_factory=list)
    http_status: int | None = None
    served_as_html: bool = False

    groups: list | None = None
    body: str | None = None
    crawl_delay: float = 0.0

    def allows(self, url: str) -> bool:
        if self.status in ("reserved", "blocked-fetch", "error"):
            return False
        if self.status == "absent" or not self.groups:
            return True
        return robots9309.allowed(self.groups, UA_TOKEN, url)


def crawl_delay(body: str, token: str) -> float:
    """Crawl-delay of the group that applies to token (named group, else '*'); 0 if none. Not part of RFC 9309,
    honoured anyway (capped at 30 s)."""
    cur, in_rules, groups = None, False, []
    for raw in re.split(r"\r\n|\r|\n", body[:robots9309.PARSE_LIMIT]):
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k in robots9309.UA_KEYS:
            if cur is None or in_rules:
                cur = {"agents": [], "delay": None}
                groups.append(cur)
                in_rules = False
            cur["agents"].append(robots9309.product_token(v))
        elif cur is not None:
            in_rules = True
            if k == "crawl-delay":
                try:
                    cur["delay"] = float(v)
                except ValueError:
                    pass
    t = token.lower()
    for want in (t, "*"):
        ds = [g["delay"] for g in groups if want in g["agents"] and g["delay"] is not None]
        if ds:
            return min(max(ds), 30.0)
    return 0.0


class Fetcher:
    def __init__(self, log_path: Path):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.last: dict[str, float] = {}
        self.robots: dict[str, RobotsInfo] = {}
        self.log_path = log_path
        self.t0 = time.monotonic()
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # -- low level -------------------------------------------------------------------------
    def _wait(self, host: str) -> float:
        """Sleep until >= max(1 s, Crawl-delay) since the previous request to host; return the monotonic start."""
        gap = MIN_INTERVAL
        for k, info in self.robots.items():
            if info.host == host:
                gap = max(gap, info.crawl_delay or 0.0)
        t = self.last.get(host)
        if t is not None:
            d = time.monotonic() - t
            if d < gap:
                time.sleep(gap - d)
        self.last[host] = time.monotonic()
        return round(self.last[host] - self.t0, 3)

    def _log(self, **kw) -> None:
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.log_path.open("a") as f:
            f.write(json.dumps(kw) + "\n")

    @staticmethod
    def origin(url: str) -> tuple[str, str]:
        p = urllib.parse.urlsplit(url)
        return p.scheme.lower(), p.netloc.lower()

    # -- robots ----------------------------------------------------------------------------
    def robots_for(self, url: str) -> RobotsInfo:
        scheme, host = self.origin(url)
        key = f"{scheme}://{host}"
        if key in self.robots:
            return self.robots[key]
        rurl = f"{key}/robots.txt"
        self._wait(host)
        info = RobotsInfo(host=host, status="error")
        try:
            r = self.s.get(rurl, timeout=TIMEOUT, allow_redirects=True)
            info.http_status = r.status_code
            ctype = r.headers.get("content-type", "")
            body = r.text if r.content else ""
            self._log(kind="robots", url=rurl, status=r.status_code, ctype=ctype, bytes=len(r.content))
            if r.status_code in (401, 403) and not RFC9309_4XX:
                # Frozen rule (before deviation D1): a 401/403 on robots.txt made the host not retrievable.
                info.status = "blocked-fetch"
            elif 400 <= r.status_code < 500:
                # RFC 9309 2.3.1.3: robots.txt "unavailable" (4xx) => the crawler MAY access any resource (deviation D1).
                info.status = "absent"
            elif r.status_code >= 500:
                info.status = "error"  # RFC 9309 2.3.1.4: unreachable => assume complete disallow
            else:
                # RFC 9309 2.3.1.1 / 2.3.1.5: parse the body by syntax, whatever its Content-Type (deviation D8).
                looks_html = "html" in ctype.lower() or body.lstrip()[:15].lower().startswith(("<!doctype", "<html"))
                info.served_as_html = looks_html
                info.body = body[:robots9309.PARSE_LIMIT]
                comments = [ln.split("#", 1)[1].strip() for ln in body.splitlines() if "#" in ln]
                hits = [c for c in comments if RESERVATION_RE.search(c)]
                info.reservation_comments = hits[:5]
                info.groups = robots9309.parse(body)
                info.crawl_delay = crawl_delay(body, UA_TOKEN)
                if hits:
                    info.status = "reserved"
                elif looks_html and not robots9309.has_groups(info.groups) and re.search(
                        r"(robots?|crawl|scrap)\w*[^.]{0,80}(prohibit|forbid|not allowed)", re.sub(r"<[^>]+>", " ", body), re.I):
                    info.status = "reserved"
                    info.reservation_comments = ["html-served robots.txt with a reservation"]
                else:
                    info.status = "ok"
        except requests.RequestException as e:
            self._log(kind="robots", url=rurl, error=type(e).__name__)
            info.status = "error"
        self.robots[key] = info
        return info

    # -- main entry ------------------------------------------------------------------------
    def get(self, url: str, dest: Path | None = None, max_bytes: int = MAX_BYTES, method: str = "GET",
            headers: dict | None = None, allow_redirects: bool = True) -> dict:
        """Fetch url politely. Returns a dict with status, final_url, ctype, size, sha256, path, reason.
        Never raises for network errors. If dest is given, the body is streamed to dest."""
        out = {"url": url, "status": None, "final_url": None, "ctype": None, "size": 0,
               "sha256": None, "path": None, "reason": None, "body": None}
        info = self.robots_for(url)
        if not info.allows(url):
            out["reason"] = f"robots:{info.status}" if info.status != "ok" else "robots:disallowed"
            self._log(kind="skip", url=url, reason=out["reason"])
            return out
        _, host = self.origin(url)
        out["t_start"] = self._wait(host)
        try:
            # Redirects are followed manually so robots is honoured on every host in the chain.
            cur = url
            for _ in range(6):
                r = self.s.request(method, cur, timeout=TIMEOUT, stream=True, allow_redirects=False,
                                   headers=headers or {})
                if allow_redirects and r.is_redirect and "location" in r.headers:
                    nxt = urllib.parse.urljoin(cur, r.headers["location"])
                    r.close()
                    self._log(kind="redirect", url=cur, to=nxt, status=r.status_code)
                    ninfo = self.robots_for(nxt)
                    if not ninfo.allows(nxt):
                        out["reason"] = "robots-on-redirect:" + ninfo.status
                        out["final_url"] = nxt
                        return out
                    self._wait(self.origin(nxt)[1])
                    cur = nxt
                    continue
                break
            out["status"] = r.status_code
            out["final_url"] = cur
            out["ctype"] = r.headers.get("content-type")
            h = hashlib.sha256()
            size = 0
            chunks = [] if dest is None else None
            fh = dest.open("wb") if dest is not None else None
            t0 = time.monotonic()
            try:
                for chunk in r.iter_content(65536):
                    if time.monotonic() - t0 > MAX_SECONDS:
                        out["reason"] = "too-slow"
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        out["reason"] = "too-large"
                        break
                    h.update(chunk)
                    if fh:
                        fh.write(chunk)
                    else:
                        chunks.append(chunk)
            finally:
                if fh:
                    fh.close()
                r.close()
            out["size"] = size
            out["sha256"] = h.hexdigest()
            if dest is not None:
                out["path"] = str(dest)
            else:
                out["body"] = b"".join(chunks)
            self._log(kind="get", url=url, final=cur, status=r.status_code, ctype=out["ctype"], bytes=size,
                      t_start_mono=out.get("t_start"))
        except requests.RequestException as e:
            out["reason"] = "net:" + type(e).__name__
            self._log(kind="get", url=url, error=type(e).__name__)
        return out
