#!/usr/bin/env python3
"""Step 1 — enumerate the population (metadata only, no file downloads).

Population = union of
  (a) files in "Category:AI-generated images" and its subcategories, breadth-first,
      down to MAX_DEPTH levels (root = depth 0), capped at MAX_CATS categories;
  (b) files that transclude {{PD-algorithm}} (namespace File:).

Writes
  data/category_tree.csv     category, depth (first seen), parent, files, subcats
  data/population.csv.gz     one row per file: pageid, title, page URL, file URL, mime,
                             size, sha1, timestamp of the current file version,
                             min category depth (or blank), in_category_tree, in_pd_algorithm,
                             first category in which it was found
The uploader is never requested.
"""

from __future__ import annotations

import csv
import gzip
import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import commons  # noqa: E402

ROOT = "Category:AI-generated images"
TEMPLATE = "Template:PD-algorithm"
MAX_DEPTH = int(sys.argv[1]) if len(sys.argv) > 1 else 6
MAX_CATS = 6000
HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
CK = HERE / "work" / "enumerate_checkpoint.json"

files: dict[int, dict] = {}


def add_file(p: dict, depth: int | None, cat: str | None, pd: bool) -> None:
    ii = (p.get("imageinfo") or [{}])[0]
    f = files.get(p["pageid"])
    if f is None:
        f = files[p["pageid"]] = {
            "pageid": p["pageid"],
            "title": p["title"],
            "page_url": ii.get("descriptionurl", ""),
            "file_url": ii.get("url", ""),
            "mime": ii.get("mime", ""),
            "size": ii.get("size", ""),
            "sha1": ii.get("sha1", ""),
            "timestamp": ii.get("timestamp", ""),
            "min_depth": depth,
            "in_category_tree": depth is not None,
            "in_pd_algorithm": pd,
            "found_in": cat or "",
        }
    else:
        if ii and not f["file_url"]:
            f.update(page_url=ii.get("descriptionurl", ""), file_url=ii.get("url", ""),
                     mime=ii.get("mime", ""), size=ii.get("size", ""), sha1=ii.get("sha1", ""),
                     timestamp=ii.get("timestamp", ""))
        if depth is not None:
            f["in_category_tree"] = True
            if f["min_depth"] is None or depth < f["min_depth"]:
                f["min_depth"], f["found_in"] = depth, cat
        if pd:
            f["in_pd_algorithm"] = True


def main() -> None:
    DATA.mkdir(exist_ok=True)
    tree: dict[str, dict] = {ROOT: {"depth": 0, "parent": "", "files": 0, "subcats": 0}}
    queue = deque([ROOT])
    n = 0
    while queue:
        cat = queue.popleft()
        depth = tree[cat]["depth"]
        types = "subcat|file" if depth < MAX_DEPTH else "file"
        for d in commons.query_all({
            "generator": "categorymembers", "gcmtitle": cat, "gcmtype": types,
            "gcmlimit": "500", "prop": "imageinfo|categoryinfo",
            "iiprop": "timestamp|url|mime|size|sha1",
        }):
            for p in (d.get("query") or {}).get("pages", []):
                if p.get("ns") == 14:
                    tree[cat]["subcats"] += 1
                    if p["title"] not in tree and len(tree) < MAX_CATS:
                        ci = p.get("categoryinfo") or {}
                        tree[p["title"]] = {"depth": depth + 1, "parent": cat,
                                            "files": 0, "subcats": 0,
                                            "declared_files": ci.get("files", "")}
                        queue.append(p["title"])
                elif p.get("ns") == 6:
                    if "imageinfo" in p:
                        tree[cat]["files"] += 1
                    add_file(p, depth, cat, False)
        n += 1
        if n % 50 == 0:
            print(f"[cats] {n} done, {len(queue)} queued, {len(tree)} seen, "
                  f"{len(files)} files, {commons.REQUESTS['api']} API calls", flush=True)
    print(f"[cats] finished: {len(tree)} categories, {len(files)} files", flush=True)

    m = 0
    for d in commons.query_all({
        "generator": "embeddedin", "geititle": TEMPLATE, "geinamespace": "6",
        "geilimit": "500", "prop": "imageinfo", "iiprop": "timestamp|url|mime|size|sha1",
    }):
        for p in (d.get("query") or {}).get("pages", []):
            add_file(p, None, None, True)
        m += 1
        if m % 20 == 0:
            print(f"[pd] {m} batches, {len(files)} files", flush=True)
    print(f"[pd] finished, {len(files)} files total", flush=True)

    with open(DATA / "category_tree.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["category", "depth", "parent", "files_listed", "subcats_listed"])
        for c, t in tree.items():
            w.writerow([c, t["depth"], t["parent"], t["files"], t["subcats"]])
    cols = ["pageid", "title", "page_url", "file_url", "mime", "size", "sha1", "timestamp",
            "min_depth", "in_category_tree", "in_pd_algorithm", "found_in"]
    with gzip.open(DATA / "population.csv.gz", "wt", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for f in sorted(files.values(), key=lambda x: x["pageid"]):
            w.writerow({k: ("" if f[k] is None else f[k]) for k in cols})
    CK.parent.mkdir(exist_ok=True)
    CK.write_text(json.dumps({"max_depth": MAX_DEPTH, "categories": len(tree),
                              "files": len(files), "requests": commons.REQUESTS}))
    print("done", commons.REQUESTS, flush=True)


if __name__ == "__main__":
    main()
