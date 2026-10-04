#!/usr/bin/env python3
"""S22: download the locked inputs into data/raw/ and check them against scripts/locked_inputs.json.

One request at a time, User-Agent EasyxLab-research/1.0, at least 1.2 s between requests to the same
host, 120 s timeout. robots.txt is read first for each host; a disallowed path or a 401/403 on
robots.txt stops that host. A file whose SHA-256 differs from the locked one is kept as
data/raw/<name>.new and reported: INE replaces its tables in place when it revises them (the 2024
tables were «revisados y modificados con fecha 17/10/2025»), so a changed file is a different vintage.
The INE press release page is live and may also change; the Wayback capture should not.
"""
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

from s22lib import RAW, UA, locked_inputs, sha256

_last: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser] = {}


def _wait(host):
    d = time.monotonic() - _last.get(host, -1e9)
    if d < 1.2:
        time.sleep(1.2 - d)
    _last[host] = time.monotonic()


def allowed(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            _wait(p.netloc)
            with urllib.request.urlopen(urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA}),
                                        timeout=120) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                rp.disallow_all = True
            else:
                rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url)


def main() -> int:
    bad = 0
    for item in locked_inputs():
        dest = RAW / item["local"]
        if dest.exists() and sha256(dest) == item["sha256"]:
            print(f"ok      {item['local']}")
            continue
        if not allowed(item["url"]):
            print(f"ROBOTS  {item['local']}: robots.txt does not allow {item['url']}")
            bad += 1
            continue
        _wait(urllib.parse.urlsplit(item["url"]).netloc)
        with urllib.request.urlopen(urllib.request.Request(item["url"], headers={"User-Agent": UA}), timeout=120) as r:
            body = r.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".new")
        tmp.write_bytes(body)
        if sha256(tmp) == item["sha256"]:
            tmp.replace(dest)
            print(f"fetched {item['local']}")
        else:
            bad += 1
            print(f"CHANGED {item['local']}: no longer matches the locked vintage; kept as {tmp.name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
