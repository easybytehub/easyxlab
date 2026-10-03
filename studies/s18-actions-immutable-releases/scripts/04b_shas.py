"""Step 4b (network, added after the review): does every full-SHA pin resolve in its action repository?

For each action repository and each distinct 40-hex ref used against it, GraphQL
`repository { object(oid:) { oid } }` (batched, about 80 objects per query). Writes
data/raw/shas.jsonl (not published). A SHA that is not a commit (missing, or the id of an annotated
tag object) is classified `sha-unresolvable`.
Note: GitHub resolves objects across a repository's fork network, so an "impostor" commit from a fork
would still count as resolvable.
"""
from __future__ import annotations

import json

from common import RAW, gql
from uses_check import extract_uses, parse_uses, ref_form

OUT = RAW / "shas.jsonl"
PER_QUERY = 80


def wanted() -> dict:
    want: dict[str, dict] = {}
    for line in open(RAW / "repos.jsonl", encoding="utf-8"):
        node = json.loads(line)["node"] or {}
        for e in ((node.get("wf") or {}).get("entries") or []):
            text = (e.get("object") or {}).get("text")
            if e["type"] != "blob" or not e["name"].endswith((".yml", ".yaml")) or not text:
                continue
            for u in extract_uses(text):
                p = parse_uses(u["value"])
                if p.kind == "remote" and ref_form(p.ref) == "sha":
                    want.setdefault(p.slug, {"owner": p.owner, "repo": p.repo, "shas": set()})["shas"].add(p.ref.lower())
    return want


def main() -> None:
    want = wanted()
    done = {json.loads(x)["slug"] for x in open(OUT, encoding="utf-8")} if OUT.exists() else set()
    todo = sorted(s for s in want if s not in done)
    print("action repositories with SHA pins:", len(want), "distinct (repo, sha):",
          sum(len(w["shas"]) for w in want.values()), "to query:", len(todo), flush=True)
    batch: list[str] = []

    def flush(batch):
        frags, keys = [], []
        for i, slug in enumerate(batch):
            w = want[slug]
            shas = sorted(w["shas"])
            objs = " ".join(f"s{k}: object(oid: {json.dumps(x)}) {{ __typename oid }}" for k, x in enumerate(shas))
            frags.append(f"a{i}: repository(owner: {json.dumps(w['owner'])}, name: {json.dumps(w['repo'])}) {{ {objs} }}")
            keys.append((slug, shas))
        js = gql("{\n" + "\n".join(frags) + "\n}")
        data = js.get("data") or {}
        with open(OUT, "a", encoding="utf-8", newline="\n") as f:
            for i, (slug, shas) in enumerate(keys):
                node = data.get(f"a{i}")
                res = {x: (node.get(f"s{k}") or {}).get("__typename") == "Commit" for k, x in enumerate(shas)} if node else {x: False for x in shas}
                f.write(json.dumps({"slug": slug, "exists": node is not None, "shas": res}) + "\n")

    n = 0
    for slug in todo:
        k = len(want[slug]["shas"])
        if batch and n + k > PER_QUERY:
            flush(batch)
            batch, n = [], 0
        batch.append(slug)
        n += k
    if batch:
        flush(batch)


if __name__ == "__main__":
    main()
