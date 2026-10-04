#!/usr/bin/env python3
"""Download the text of every candidate notice.

    python3 scripts/fetch_notices.py work/candidates_study.csv

For each id, requests https://www.boe.es/diario_boe/txt.php?id=<id> (the HTML rendering of
the notice, allowed by www.boe.es/robots.txt) through scripts/polite.py and stores it
gzip-compressed in data/raw/notices/<id>.html.gz. Ids that robots.txt excludes one by one are
skipped and listed in data/raw/notices/_robots_skipped.txt. We do not use
/diario_boe/xml.php, which robots.txt disallows for all agents.
"""
import csv
import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data", "raw", "notices")
URL = "https://www.boe.es/diario_boe/txt.php?id={}"


def main(cand):
    os.makedirs(OUT, exist_ok=True)
    skipped_path = os.path.join(OUT, "_robots_skipped.txt")
    skipped = set(open(skipped_path).read().split()) if os.path.exists(skipped_path) else set()
    ids = [r["id"] for r in csv.DictReader(open(cand, encoding="utf-8"))]
    got = have = rob = err = 0
    for i in ids:
        gz = os.path.join(OUT, i + ".html.gz")
        if os.path.exists(gz):
            have += 1
            continue
        if i in skipped:
            rob += 1
            continue
        tmp = os.path.join(OUT, i + ".html")
        try:
            status, _ = polite.fetch(URL.format(i), tmp, accept="text/html")
        except PermissionError:
            skipped.add(i)
            open(skipped_path, "w").write("\n".join(sorted(skipped)) + "\n")
            rob += 1
            continue
        except Exception as e:  # network timeout etc.: leave for the next run
            err += 1
            print(f"{i}: {type(e).__name__} {e}", file=sys.stderr)
            continue
        if status == 200:
            with open(tmp, "rb") as f, gzip.open(gz, "wb") as g:
                g.write(f.read())
            os.remove(tmp)
            got += 1
        else:
            err += 1
            print(f"{i}: HTTP {status}", file=sys.stderr)
    print(f"fetched {got}, already present {have}, skipped by robots.txt {rob}, errors {err}")


if __name__ == "__main__":
    main(sys.argv[1])
