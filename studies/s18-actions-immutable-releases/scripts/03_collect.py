"""Step 3 (network): read the workflow files and the latest release of every population repository.

GraphQL, batches of BATCH repositories (`object(expression: "HEAD:.github/workflows")`).
Writes data/raw/repos.jsonl (not published: contains workflow texts). Resumable.
"""
from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from common import RAW, api, gql

BATCH = 8
WORKERS = 3   # requests still start at most one per second (common._pace)
OUT = RAW / "repos.jsonl"
FIELDS = """databaseId nameWithOwner isFork isArchived isPrivate stargazerCount pushedAt owner { __typename }
defaultBranchRef { name target { oid } }
wf: object(expression: "HEAD:.github/workflows") { ... on Tree { entries { name type
    object { ... on Blob { byteSize isBinary isTruncated text } } } } }
latestRelease { tagName immutable publishedAt releaseAssets(first: 100) { totalCount nodes { name } } }"""


def frag(alias: str, full_name: str) -> str:
    owner, name = full_name.split("/", 1)
    return f"{alias}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{ {FIELDS} }}"


def run_batch(items: list[tuple[str, dict]]) -> dict:
    q = "{\n" + "\n".join(frag(f"p{i}", r["full_name"]) for i, (_, r) in enumerate(items)) + "\n}"
    js = gql(q)
    if "data" not in js or js["data"] is None:
        raise RuntimeError(str(js.get("errors"))[:300])
    return js["data"]


def main() -> None:
    pop = json.loads((RAW / "population.json").read_text())
    frame = {}
    for fr in ("frame_a", "frame_b"):
        for line in open(RAW / f"{fr}.jsonl", encoding="utf-8"):
            r = json.loads(line)
            frame[r["id"]] = r
    todo = [("A", frame[i]) for i in pop["A"]] + [("B", frame[i]) for i in pop["B"]]
    done = set()
    if OUT.exists():
        done = {(d["pop"], d["id"]) for d in map(json.loads, open(OUT, encoding="utf-8"))}
    todo = [(p, r) for p, r in todo if (p, r["id"]) not in done]
    print("to collect:", len(todo), flush=True)
    lock = threading.Lock()
    f = open(OUT, "a", encoding="utf-8", newline="\n")
    progress = [0]

    def work(chunk):
        try:
            data = run_batch(chunk)
            results = [(chunk[i], data.get(f"p{i}")) for i in range(len(chunk))]
        except RuntimeError as e:
            print("batch failed, retrying one by one:", e, flush=True)
            results = []
            for item in chunk:
                try:
                    results.append((item, run_batch([item]).get("p0")))
                except RuntimeError as e2:
                    results.append((item, {"_error": str(e2)[:300]}))
        lines = []
        for (p, r), node in results:
            if node is None:  # renamed or deleted since enumeration: look up by id
                s, js = api(f"/repositories/{r['id']}")
                if s == 200 and js["full_name"].lower() != r["full_name"].lower():
                    try:
                        node = run_batch([(p, {"full_name": js["full_name"]})]).get("p0")
                    except RuntimeError:
                        node = None
            lines.append(json.dumps({"pop": p, "id": r["id"], "full_name": r["full_name"], "node": node}) + "\n")
        with lock:
            f.writelines(lines)
            f.flush()
            progress[0] += len(chunk)
            if progress[0] % 80 < len(chunk):
                print(f"  {progress[0]}/{len(todo)}", flush=True)

    chunks = [todo[k:k + BATCH] for k in range(0, len(todo), BATCH)]
    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(work, chunks))
    f.close()

if __name__ == "__main__":
    sys.exit(main())
