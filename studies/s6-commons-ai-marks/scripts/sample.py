#!/usr/bin/env python3
"""Step 2 — stratified random sample by upload month (of the current file version).

Frame: population rows with a raster MIME type ai-mark-lint reads (JPEG, PNG, WebP, AVIF,
HEIF). Strata = calendar month of `timestamp`. Allocation (see METHOD.md):
  2026-08 and 2026-09 (after AI Act art. 50(2) applies) ... POST_N per month (census if fewer)
  2026-01 .. 2026-07 .......................................... PRE26_N per month
  2024-01 .. 2025-12 .......................................... OLD_N per month
  before 2024 ................................................. EARLY_N in total
  2026-10 (partial month at data collection) .................. not sampled
Fixed seed, so the sample is reproducible from data/population.csv.gz.
Writes data/sample.csv and data/population_by_month.csv.
"""

from __future__ import annotations

import csv
import gzip
import random
from collections import Counter, defaultdict
from pathlib import Path

SEED = 20261002
POST_N, PRE26_N, OLD_N, EARLY_N = 10**6, 10**6, 40, 100  # 2026: census
RASTER = {"image/jpeg", "image/png", "image/webp", "image/avif", "image/heif", "image/heic"}
HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"


def stratum(month: str) -> str:
    if month < "2024-01":
        return "early"
    if month < "2026-01":
        return month
    if month <= "2026-09":
        return month
    return "excluded"


def quota(s: str, n: int) -> int:
    if s == "excluded":
        return 0
    if s == "early":
        return min(n, EARLY_N)
    if s in ("2026-08", "2026-09"):
        return min(n, POST_N)
    if s >= "2026-01":
        return min(n, PRE26_N)
    return min(n, OLD_N)


def round1(s: str) -> int:
    if s == "early":
        return 25
    if s in ("2026-08", "2026-09"):
        return 250
    if s >= "2026-01":
        return 70
    return 15


def main() -> None:
    rows = list(csv.DictReader(gzip.open(DATA / "population.csv.gz", "rt")))
    by_month_all: Counter = Counter()
    by_mime: dict[str, Counter] = defaultdict(Counter)
    frame: dict[str, list] = defaultdict(list)
    for r in rows:
        m = r["timestamp"][:7] or "unknown"
        by_month_all[m] += 1
        by_mime[m][r["mime"]] += 1
        if r["mime"] in RASTER and r["file_url"]:
            frame[stratum(m)].append(r)
    rng = random.Random(SEED)
    sample = []
    for s in sorted(frame):
        pool = sorted(frame[s], key=lambda r: int(r["pageid"]))
        k = quota(s, len(pool))
        for r in rng.sample(pool, k):
            sample.append({**r, "stratum": s, "stratum_N": len(pool), "stratum_n": k})
    rng.shuffle(sample)  # interleave months so a partial run is still balanced
    # Processing order. Downloads run at ~0.3 MB/s, so the full sample (5 GB) may not
    # finish in the time budget. Round 1 takes the first ROUND1(stratum) files of each
    # stratum in the shuffled order; round 2 the rest of the 2026 census; round 3 the rest
    # of 2024-2025 and before 2024. Any prefix of this order is
    # therefore a simple random subsample within every month.
    rank: Counter = Counter()
    for x in sample:
        x["round"] = (1 if rank[x["stratum"]] < round1(x["stratum"])
                      else 2 if x["stratum"].startswith("2026") else 3)
        rank[x["stratum"]] += 1
    sample.sort(key=lambda x: x["round"])  # stable: keeps the shuffled order within rounds
    cols = list(sample[0].keys())
    with open(DATA / "sample.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(sample)
    with open(DATA / "population_by_month.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["month", "all_files", "raster_frame", "stratum", "sampled",
                    "jpeg", "png", "webp", "other_mime"])
        frame_month = Counter(r["timestamp"][:7] for s in frame for r in frame[s])
        for m in sorted(by_month_all):
            s = stratum(m)
            c = by_mime[m]
            other = sum(v for k, v in c.items() if k not in ("image/jpeg", "image/png", "image/webp"))
            w.writerow([m, by_month_all[m], frame_month[m], s,
                        sum(1 for x in sample if x["timestamp"][:7] == m),
                        c["image/jpeg"], c["image/png"], c["image/webp"], other])
    print(f"population {len(rows)} · frame {sum(len(v) for v in frame.values())} · sample {len(sample)}")
    for s in sorted(frame):
        print(f"  {s}: N={len(frame[s])} n={quota(s, len(frame[s]))}")


if __name__ == "__main__":
    main()
