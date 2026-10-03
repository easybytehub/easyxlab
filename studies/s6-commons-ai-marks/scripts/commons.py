"""Polite, read-only client for the Wikimedia Commons Action API and upload.wikimedia.org.

Rules applied to every request (see METHOD.md, "Access policy"):
- exact User-Agent below, with contact address (Wikimedia User-Agent policy);
- strictly serial requests, at most 1 request per second across API *and* file downloads;
- `maxlag=5` on API calls, gzip, exponential back-off on 429/5xx/maxlag;
- read-only: no login, no edits, no POST.
The uploader's user name is never requested (no `iiprop=user`).
"""

from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
# Enumeration, sampling metadata and the main measurement run (2026-10-02, until the end of
# measure.py's main loop) used "EasyByteLab-research/0.1 (contact: contact@easybyte.es)".
# The lab was renamed EasyxLab during the run; later requests use this agent:
UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
MIN_INTERVAL = 1.0  # seconds between any two requests

_last = 0.0
REQUESTS = {"api": 0, "download": 0, "bytes": 0}


def _wait() -> None:
    global _last
    dt = time.monotonic() - _last
    if dt < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - dt)
    _last = time.monotonic()


def _open(req: urllib.request.Request, timeout: int = 120):
    delay = 5.0
    for attempt in range(8):
        _wait()
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 7:
                ra = exc.headers.get("Retry-After")
                time.sleep(max(delay, float(ra) if ra and ra.isdigit() else 0))
                delay *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt < 7:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("unreachable")


def api(params: dict) -> dict:
    """One GET to the Action API (json, formatversion=2, maxlag=5), with retries."""
    p = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
    url = API + "?" + urllib.parse.urlencode(p)
    delay = 5.0
    for _ in range(10):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
        with _open(req) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
        REQUESTS["api"] += 1
        d = json.loads(raw)
        if "error" in d and d["error"].get("code") == "maxlag":
            time.sleep(delay)
            delay *= 2
            continue
        if "error" in d:
            raise RuntimeError(f"API error: {d['error']}")
        return d
    raise RuntimeError("maxlag persisted")


def query_all(params: dict):
    """Iterate over all continuation batches of an action=query request."""
    cont: dict = {}
    while True:
        d = api({"action": "query", **params, **cont})
        yield d
        if "continue" not in d:
            return
        cont = d["continue"]


def download(url: str, dest: Path, max_bytes: int) -> int:
    """Stream one original file to `dest`. Refuses anything larger than max_bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    n = 0
    with _open(req, timeout=300) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            n += len(chunk)
            if n > max_bytes:
                raise ValueError("file larger than cap")
            f.write(chunk)
    REQUESTS["download"] += 1
    REQUESTS["bytes"] += n
    return n
