#!/usr/bin/env python3
"""S24: download the inputs listed in scripts/locked_inputs.json into data/raw/ and check their SHA-256.

INE's terms for its anonymised microdata do not expressly allow redistributing the files, so this
study does not re-host them: this script downloads them from ine.es. Rules: User-Agent
EasyxLab-research/1.0, robots.txt read first for each host (a disallowed path or a 401/403 on
robots.txt stops that host), at least 1.2 s between requests to a host, curl with --max-time 120 per
attempt and resume (-C -) across attempts, so a large file arrives in several polite pieces.
A file whose SHA-256 differs from the locked one is kept as <name>.new, never under its normal name, and
the script exits 1: INE replaces microdata files in place (the 2022 household file was updated in March
2026), so a changed file is a different vintage. `--verify` checks the files on disk without downloading;
`run.sh` runs it before any analysis and stops on a missing or changed file.

    python3 scripts/fetch.py            all locked inputs
    python3 scripts/fetch.py --only ecv only names containing 'ecv'
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

from s24lib import RAW, UA, locked_inputs, sha256

_last: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser] = {}


def _wait(host: str) -> None:
    d = time.monotonic() - _last.get(host, -1e9)
    if d < 1.2:
        time.sleep(1.2 - d)
    _last[host] = time.monotonic()


def allowed(url: str) -> bool:
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            _wait(p.netloc)
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                rp.disallow_all = True
            else:
                rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url)


def download(url: str, dest, attempts: int = 12) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    host = urllib.parse.urlsplit(url).netloc
    for _ in range(attempts):
        _wait(host)
        rc = subprocess.run(["curl", "-s", "-f", "-L", "--max-time", "120", "-C", "-", "-A", UA,
                             "-o", str(part), url]).returncode
        if rc == 0:
            part.replace(dest)
            return True
        if rc not in (18, 28, 56, 52, 33):   # partial, timeout, recv error, empty reply, range error
            print(f"  curl exit {rc} for {url}")
            if rc == 33 and part.exists():
                part.unlink()
            else:
                return False
    return False


def verify() -> int:
    """Check every locked input on disk against its SHA-256; run.sh calls this before any analysis."""
    bad = 0
    for item in locked_inputs():
        p = RAW / item["local"]
        if not p.exists():
            print(f"MISSING {item['local']} (run: bash scripts/run.sh fetch)")
            bad += 1
        elif item.get("sha256") and sha256(p) != item["sha256"]:
            print(f"CHANGED {item['local']}: not the locked vintage")
            bad += 1
    print(f"verified {len(locked_inputs()) - bad} of {len(locked_inputs())} locked inputs")
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    if "--verify" in argv:
        return verify()
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    bad = 0
    for item in locked_inputs():
        if only and only not in item["local"]:
            continue
        dest = RAW / item["local"]
        if dest.exists() and (not item.get("sha256") or sha256(dest) == item["sha256"]):
            print(f"ok      {item['local']}")
            continue
        if not allowed(item["url"]):
            print(f"ROBOTS  {item['local']}: robots.txt does not allow {item['url']}")
            bad += 1
            continue
        target = dest if not dest.exists() else dest.with_name(dest.name + ".new")
        if not download(item["url"], target):
            print(f"FAILED  {item['local']}")
            bad += 1
            continue
        got = sha256(target)
        if item.get("sha256") and got != item["sha256"]:
            # never let a new vintage take the locked file's place: keep it aside and fail
            if target == dest:
                newp = dest.with_name(dest.name + ".new")
                dest.replace(newp)
                target = newp
            print(f"CHANGED {item['local']}: sha256 {got} (locked {item['sha256']}); kept as {target.name}, not used")
            bad += 1
        else:
            print(f"fetched {item['local']} {got}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
