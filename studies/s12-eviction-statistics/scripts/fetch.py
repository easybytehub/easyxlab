"""S12: download the locked inputs into data/raw/ and check them against PROTOCOL.md §3.3.

Only the files of the vintage lock are fetched (never a later release). One request at a time,
User-Agent EasyxLab-research/1.0, 5 s between requests to poderjudicial.es (its robots.txt asks
Crawl-delay: 5) and at least 1 s to other hosts. A file whose hash differs from the registered one is
kept as data/raw/<name>.new and reported: the CGPJ replaces files in place, and a changed file is a
new vintage, not the one this study registered.
"""
from __future__ import annotations

import sys
import time
import urllib.parse
import urllib.request

from s12lib import LOCKED, RAW, SUPPORT, UA, sha256

DELAY = {"www.poderjudicial.es": 5.0}


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    last = {}
    bad = 0
    for name, (url, digest) in {**LOCKED, **SUPPORT}.items():
        dest = RAW / name
        if dest.exists() and sha256(dest) == digest:
            print(f"ok      {name}")
            continue
        parts = urllib.parse.urlsplit(url)
        quoted = urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(parts.path)))
        host = parts.netloc
        wait = DELAY.get(host, 1.0) - (time.monotonic() - last.get(host, -1e9))
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(quoted, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
        last[host] = time.monotonic()
        tmp = dest.with_suffix(dest.suffix + ".new")
        tmp.write_bytes(body)
        if sha256(tmp) == digest:
            tmp.replace(dest)
            print(f"fetched {name}")
        else:
            bad += 1
            print(f"CHANGED {name}: the published file no longer matches the registered vintage; kept as {tmp.name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
