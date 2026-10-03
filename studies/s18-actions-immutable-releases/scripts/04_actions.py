"""Step 4 (network): resolve every action repository and every non-SHA ref used against it.

Reads data/raw/repos.jsonl, extracts the remote `uses:` references with uses_check, and runs the
GraphQL query of uses_check.build_repo_query() in batches. Writes data/raw/actions.jsonl
(not published). Resumable.
"""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

from common import RAW, gql
from uses_check import build_repo_query, extract_uses, parse_uses, ref_form

BATCH = 6
WORKERS = 3   # requests still start at most one per second (common._pace)
OUT = RAW / "actions.jsonl"


def wanted() -> dict:
    want: dict[str, dict] = {}
    for line in open(RAW / "repos.jsonl", encoding="utf-8"):
        d = json.loads(line)
        node = d["node"] or {}
        for e in ((node.get("wf") or {}).get("entries") or []):
            if not e["name"].endswith((".yml", ".yaml")) or e["type"] != "blob":
                continue
            text = (e.get("object") or {}).get("text")
            if not text:
                continue
            for u in extract_uses(text):
                p = parse_uses(u["value"])
                if p.kind != "remote":
                    continue
                w = want.setdefault(p.slug, {"owner": p.owner, "repo": p.repo, "refs": set()})
                if ref_form(p.ref) != "sha":
                    w["refs"].add(p.ref)
    return want


def main() -> None:
    want = wanted()
    done: dict[str, set] = {}
    if OUT.exists():  # a slug is re-queried if new refs appeared for it (later lines win in 05_export)
        for x in open(OUT, encoding="utf-8"):
            d = json.loads(x)
            done[d["slug"]] = set(d["refs"])
    todo = sorted(s for s in want if s not in done or not want[s]["refs"] <= done[s])
    print("action repositories:", len(want), "to resolve:", len(todo), flush=True)
    lock = threading.Lock()
    f = open(OUT, "a", encoding="utf-8", newline="\n")
    progress = [0]

    def work(chunk):
        frags = [build_repo_query(f"a{i}", want[s]["owner"], want[s]["repo"], sorted(want[s]["refs"]))
                 for i, s in enumerate(chunk)]
        js = gql("{\n" + "\n".join(frags) + "\n}")
        data = js.get("data")
        if data is None:
            # retry one by one so that one bad repository does not sink the batch
            data = {}
            for i, slug in enumerate(chunk):
                w = want[slug]
                j1 = gql("{\n" + build_repo_query("a0", w["owner"], w["repo"], sorted(w["refs"])) + "\n}")
                data[f"a{i}"] = (j1.get("data") or {}).get("a0")
        lines = [json.dumps({"slug": slug, "owner": want[slug]["owner"], "repo": want[slug]["repo"],
                             "refs": sorted(want[slug]["refs"]), "node": data.get(f"a{i}")}) + "\n"
                 for i, slug in enumerate(chunk)]
        with lock:
            f.writelines(lines)
            f.flush()
            progress[0] += len(chunk)
            if progress[0] % 150 < len(chunk):
                print(f"  {progress[0]}/{len(todo)}", flush=True)

    chunks = [todo[k:k + BATCH] for k in range(0, len(todo), BATCH)]
    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(work, chunks))
    f.close()

if __name__ == "__main__":
    main()
