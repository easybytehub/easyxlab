#!/usr/bin/env python3
"""Download the BOE daily summaries (sumario API, open data) for a date range.

    python3 scripts/fetch_sumarios.py 2025-01-01 2026-09-30

Each summary is requested from https://www.boe.es/datosabiertos/api/boe/sumario/AAAAMMDD
with `Accept: application/xml` through scripts/polite.py (robots.txt, <= 1 request/s per host,
fixed User-Agent, logged) and stored gzip-compressed in data/raw/sumarios/AAAAMMDD.xml.gz.
Days without a BOE issue (Sundays, some holidays) answer 404 and are recorded in
data/raw/sumarios/_missing.txt. Files already present are not requested again.
"""
import datetime as dt
import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data", "raw", "sumarios")
API = "https://www.boe.es/datosabiertos/api/boe/sumario/{}"


def main(start, end):
    os.makedirs(OUT, exist_ok=True)
    missing_path = os.path.join(OUT, "_missing.txt")
    missing = set()
    if os.path.exists(missing_path):
        missing = set(open(missing_path).read().split())
    d = dt.date.fromisoformat(start)
    stop = dt.date.fromisoformat(end)
    got = skipped = absent = 0
    while d <= stop:
        key = d.strftime("%Y%m%d")
        gz = os.path.join(OUT, key + ".xml.gz")
        if os.path.exists(gz) or key in missing:
            skipped += 1
            d += dt.timedelta(days=1)
            continue
        tmp = os.path.join(OUT, key + ".xml")
        try:
            status, _ = polite.fetch(API.format(key), tmp, accept="application/xml")
        except Exception as e:  # network timeout etc.: leave for the next run
            print(f"{key}: {type(e).__name__} {e}", file=sys.stderr)
            d += dt.timedelta(days=1)
            continue
        if status == 200:
            with open(tmp, "rb") as f, gzip.open(gz, "wb") as g:
                g.write(f.read())
            os.remove(tmp)
            got += 1
        else:
            for p in (tmp + f".http{status}",):
                if os.path.exists(p):
                    os.remove(p)
            if status == 404:
                missing.add(key)
                with open(missing_path, "w") as f:
                    f.write("\n".join(sorted(missing)) + "\n")
                absent += 1
            else:
                print(f"{key}: HTTP {status}", file=sys.stderr)
        d += dt.timedelta(days=1)
    print(f"fetched {got}, already present {skipped}, no issue (404) {absent}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
