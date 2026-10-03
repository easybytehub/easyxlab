"""Shared helpers for study S18. Every network request goes through `fetch()`.

`fetch()` reads robots.txt of a host before the first request to it (and refuses the request if
robots.txt disallows it, if robots.txt answers 401/403/5xx, or if a robots.txt comment forbids
robots in natural language), paces requests per host and logs every request to work/requests.log.
The GitHub token is read from `gh auth token`, kept in memory and never printed or logged.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlsplit

UA = "EasyxLab-research/0.1 (+https://easybyte.es/lab/; contact@easybyte.es)"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
WORK = ROOT / "work"
CACHE = RAW / "cache"
OFFLINE = os.environ.get("OFFLINE", "1") == "1"

# minimum seconds between two requests to the same host (or endpoint family)
INTERVAL = {"api.github.com": 1.0, "api.github.com/search": 2.2, "api.github.com/graphql": 1.0}
DEFAULT_INTERVAL = 1.0

_robots: dict[str, tuple[urllib.robotparser.RobotFileParser | None, str]] = {}
_last: dict[str, float] = {}
_token: str | None = None
NL_FORBID = re.compile(r"#.*\b(prohibit|forbid|not (?:be )?(?:permitted|allowed)|no (?:robots|crawling|scraping)|"
                       r"do not (?:crawl|scrape)|without (?:prior )?(?:written )?permission)", re.I)


class RobotsRefused(RuntimeError):
    pass


def _log(line: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    with open(WORK / "requests.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


class _RobotsRedirect(urllib.request.HTTPRedirectHandler):
    """Check robots.txt of every redirect target before following it."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        robots_check(newurl)
        _log(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\tREDIRECT\t{newurl}\t{code}\t0")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_RobotsRedirect)


def _raw_get(url: str) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", e.read() or b""


def robots_check(url: str) -> None:
    host = urlsplit(url).netloc
    if host not in _robots:
        robots_url = f"https://{host}/robots.txt"
        status, ctype, body = _raw_get(robots_url)
        _log(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\tGET\t{robots_url}\t{status}\t{len(body)}\trobots")
        text = body.decode("utf-8", "replace")
        if status in (401, 403) or status >= 500:
            _robots[host] = (None, f"robots.txt status {status}: treated as disallow-all")
        elif status >= 400:
            _robots[host] = (urllib.robotparser.RobotFileParser(), f"robots.txt status {status}: allow")
            _robots[host][0].parse([])
        else:
            if NL_FORBID.search(text):
                _robots[host] = (None, "robots.txt comment forbids robots")
            else:
                rp = urllib.robotparser.RobotFileParser()
                # also when served as HTML: parse the lines; directives are what count
                rp.parse(text.splitlines())
                _robots[host] = (rp, f"robots.txt status {status} ({ctype})")
        (RAW / "robots").mkdir(parents=True, exist_ok=True)
        (RAW / "robots" / f"{host}.txt").write_bytes(body)
    rp, note = _robots[host]
    if rp is None or not rp.can_fetch(UA, url):
        raise RobotsRefused(f"{url}: {note}")


_pace_lock = threading.Lock()


def _pace(key: str) -> None:
    """Request *starts* to one host are at least INTERVAL apart, across threads."""
    with _pace_lock:
        iv = INTERVAL.get(key, DEFAULT_INTERVAL)
        wait = _last.get(key, 0) + iv - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[key] = time.time()


def gh_token() -> str:
    global _token
    if _token is None:
        _token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    return _token


def fetch(url: str, *, body: bytes | None = None, headers: dict | None = None, auth: bool = False,
          retries: int = 4) -> tuple[int, dict, bytes]:
    """Single entry point for every request of the study."""
    robots_check(url)
    parts = urlsplit(url)
    key = parts.netloc
    if parts.netloc == "api.github.com" and parts.path.startswith("/search"):
        key = "api.github.com/search"
    elif parts.netloc == "api.github.com" and parts.path == "/graphql":
        key = "api.github.com/graphql"
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    if auth:
        h["Authorization"] = f"Bearer {gh_token()}"
    for attempt in range(retries + 1):
        _pace(key)
        req = urllib.request.Request(url, data=body, headers=h, method="POST" if body is not None else "GET")
        try:
            with _opener.open(req, timeout=60) as r:
                status, rh, data = r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            status, rh, data = e.code, dict(e.headers or {}), e.read() or b""
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            status, rh, data = 0, {}, str(e).encode()
        _log(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\t{'POST' if body else 'GET'}\t{url}\t{status}\t{len(data)}")
        rl_rem = rh.get("X-RateLimit-Remaining") or rh.get("x-ratelimit-remaining")
        if status in (403, 429) and (rh.get("Retry-After") or rh.get("retry-after") or rl_rem == "0"):
            ra = rh.get("Retry-After") or rh.get("retry-after")
            if ra:
                sleep = int(ra) + 1
            else:
                sleep = max(5, int(rh.get("X-RateLimit-Reset") or rh.get("x-ratelimit-reset") or time.time() + 60) - int(time.time()) + 2)
            _log(f"# rate limited, sleeping {sleep}s")
            time.sleep(min(sleep, 3700))
            continue
        if status == 0 or status >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        return status, rh, data
    return status, rh, data


def _cache_path(key: str) -> Path:
    return CACHE / hashlib.sha1(key.encode()).hexdigest()[:2] / (hashlib.sha1(key.encode()).hexdigest() + ".json")


def api(path_or_url: str, *, use_cache: bool = True):
    """GET a GitHub REST path. Returns (status, json-or-None). Cached in data/raw/cache/."""
    url = path_or_url if path_or_url.startswith("http") else "https://api.github.com" + path_or_url
    cp = _cache_path("GET " + url)
    if use_cache and cp.exists():
        d = json.loads(cp.read_text())
        return d["status"], d["json"]
    status, _, data = fetch(url, headers={"Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28"}, auth=True)
    try:
        js = json.loads(data) if data else None
    except json.JSONDecodeError:
        js = None
    if status in (200, 404, 422) and os.environ.get("S18_CACHE") == "1":
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps({"status": status, "json": js}))
    return status, js


def gql(query: str, variables: dict | None = None, *, use_cache: bool = True) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}, sort_keys=True)
    cp = _cache_path("GQL " + payload)
    if use_cache and cp.exists():
        return json.loads(cp.read_text())
    status, _, data = fetch("https://api.github.com/graphql", body=payload.encode(),
                            headers={"Content-Type": "application/json"}, auth=True)
    js = json.loads(data) if data else {"errors": [{"message": f"status {status}"}]}
    if status == 200 and "data" in js and os.environ.get("S18_CACHE") == "1":
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps(js))
    return js


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
