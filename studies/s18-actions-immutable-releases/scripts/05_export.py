"""Step 5: raw API data -> published tables in data/, with personal repositories protected.

- data/repos.csv: one row per population repository with aggregate counts only. Repositories owned by
  individual users get a random pseudonym and no rank, no star band.
- data/references.csv: one row per remote reference from an organisation-owned population repository
  to an organisation-owned action. References to actions owned by individual users (or no longer
  resolvable) are only counted, per repository (repos.csv) and per pseudonymised action (actions.csv).
- data/actions.csv: one row per action repository (merged across rename/transfer redirects); actions
  owned by individual users carry a random pseudonym and no release tag.
- data/ref_resolution.csv: what GitHub said about each (organisation action repository, ref).
Pseudonyms are drawn with a system random generator; the mapping stays in data/raw/pseudonyms.json
(not published). Needs data/raw/.
"""
from __future__ import annotations

import collections
import csv
import json
import random
import re

from common import DATA, RAW, sha256_file
from uses_check import classify, extract_uses, parse_repo_node, parse_uses

SBOM_RE = re.compile(r"sbom|\.spdx|spdx\.json|\.cdx\.|cyclonedx|bom\.json|bom\.xml", re.I)
VERSION_COMMENT = re.compile(r"\bv?\d+(\.\d+)*\b")
FIRST_PARTY = {"actions", "github"}
REUSABLE_LOCAL = re.compile(r"^\./\.github/workflows/[^/]+\.ya?ml$")
MUT = ("major", "minor", "full", "other")


def band(pop: str, stars: int) -> str:
    if pop == "A":
        for lo, lab in ((100000, ">=100k"), (50000, "50k-100k"), (30000, "30k-50k")):
            if stars >= lo:
                return lab
        return "20k-30k"
    return "1k-2k" if stars < 2000 else "2k-3k" if stars < 3000 else "3k-5k"


def yaml_uses(text: str):
    """`uses:` values under `jobs` found by a full YAML parse, counting each written mapping once
    (aliases are not expanded twice) and descending into nested step lists such as `parallel:`."""
    import yaml
    try:
        root = yaml.compose(text)
    except Exception:
        return None
    if not isinstance(root, yaml.MappingNode):
        return []
    out, seen = [], set()

    def walk(node, under_jobs):
        if id(node) in seen:
            return
        seen.add(id(node))
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                key = getattr(k, "value", None)
                if under_jobs and key == "uses" and isinstance(v, yaml.ScalarNode):
                    out.append(v.value.strip())
                else:
                    walk(v, under_jobs or key == "jobs")
        elif isinstance(node, yaml.SequenceNode):
            for v in node.value:
                walk(v, under_jobs)

    walk(root, False)
    return out


def write_csv(name: str, rows: list[dict]) -> None:
    with open(DATA / name, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def pseudonyms(user_repos: list[str], user_actions: list[str], missing_actions: list[str]) -> dict:
    """Random labels, stable across re-runs through data/raw/pseudonyms.json (never published)."""
    path = RAW / "pseudonyms.json"
    m = json.loads(path.read_text()) if path.exists() else {"repos": {}, "actions": {}}
    rng = random.SystemRandom()
    for kind, keys, prefix in (("repos", user_repos, "user-repo"), ("actions", user_actions, "user-action"),
                               ("actions", missing_actions, "missing-action")):
        new = [k for k in keys if k not in m[kind]]
        used = {int(v.rsplit("-", 1)[1]) for v in m[kind].values() if v.startswith(prefix)}
        free = [n for n in range(1, len(keys) + len(used) + 1) if n not in used]
        rng.shuffle(free)
        for k, n in zip(new, free):
            m[kind][k] = f"{prefix}-{n:04d}"
    path.write_text(json.dumps(m, indent=0, sort_keys=True))
    return m


def main() -> None:
    pop = json.loads((RAW / "population.json").read_text())
    frame = {}
    for fr in ("frame_a", "frame_b"):
        for line in open(RAW / f"{fr}.jsonl", encoding="utf-8"):
            r = json.loads(line)
            frame[r["id"]] = r
    raw_repos = {(d["pop"], d["id"]): d for d in map(json.loads, open(RAW / "repos.jsonl", encoding="utf-8"))}
    actions_raw = {}
    for d in map(json.loads, open(RAW / "actions.jsonl", encoding="utf-8")):
        actions_raw[d["slug"]] = d  # later lines win (re-queries)
    shas_raw = {d["slug"]: d for d in map(json.loads, open(RAW / "shas.jsonl", encoding="utf-8"))}

    # action repositories: resolution per written slug, identity per canonical (post-redirect) name
    infos, canon = {}, {}
    for s, d in actions_raw.items():
        i = parse_repo_node(d["node"], d["refs"])
        i.shas = dict((shas_raw.get(s) or {}).get("shas") or {})
        infos[s] = i
        canon[s] = d["node"]["nameWithOwner"].lower() if d["node"] else s
    ctype = {}
    for s, c in canon.items():
        ctype[c] = infos[s].owner_type if infos[s].exists else "missing"
    user_actions = sorted(c for c, t in ctype.items() if t not in ("Organization", "missing"))
    missing_actions = sorted(c for c, t in ctype.items() if t == "missing")
    user_repos = []
    for p in ("A", "B"):
        for rid in pop[p]:
            node = (raw_repos.get((p, rid)) or {}).get("node") or {}
            if (node.get("owner") or {}).get("__typename", frame[rid]["owner_type"]) != "Organization":
                user_repos.append(f"{p}:{rid}")
    ps = pseudonyms(user_repos, user_actions, missing_actions)
    alabel = {c: ps["actions"].get(c, c) for c in ctype}
    public_action = {c: ctype[c] == "Organization" for c in ctype}

    repos_rows, ref_rows = [], []
    per_action = collections.defaultdict(lambda: collections.Counter())
    action_repos = collections.defaultdict(set)
    ycheck = {"files": 0, "pyyaml_unparsable": 0, "agree": 0, "disagree": 0, "extra_in_scanner": 0,
              "missing_in_scanner": 0}
    try:
        import yaml  # noqa: F401
        have_yaml = True
    except ImportError:
        have_yaml = False
    for p in ("A", "B"):
        for rank, rid in enumerate(pop[p], 1):
            fr = frame[rid]
            node = (raw_repos.get((p, rid)) or {}).get("node")
            owner_type = ((node or {}).get("owner") or {}).get("__typename") or fr["owner_type"]
            org = owner_type == "Organization"
            label = (node or {}).get("nameWithOwner") or fr["full_name"] if org else ps["repos"][f"{p}:{rid}"]
            status = "ok"
            if node is None or "_error" in (node or {}):
                status = "not-found"
            elif node.get("isFork"):
                status = "excluded-fork"
            elif node.get("isArchived"):
                status = "excluded-archived"
            c = collections.Counter()
            row = {"pop": p, "repo": label, "owner_type": owner_type,
                   "rank": rank if (org and p == "A") else "", "stars_band": band(p, fr["stars"]) if org else "",
                   "status": status, "workflows_dir": False, "latest_release_immutable": "",
                   "latest_release_sbom_asset": ""}
            if status == "ok":
                lr = node.get("latestRelease")
                if lr:
                    row["latest_release_immutable"] = bool(lr["immutable"])
                    names = [a["name"] for a in (lr.get("releaseAssets") or {}).get("nodes") or []]
                    row["latest_release_sbom_asset"] = any(SBOM_RE.search(n) for n in names)
                entries = (node.get("wf") or {}).get("entries")
                row["workflows_dir"] = entries is not None
                files = sorted((e for e in (entries or []) if e["type"] == "blob"
                                and e["name"].endswith((".yml", ".yaml"))), key=lambda e: e["name"])
                c["workflow_files"] = len(files)
                for fno, e in enumerate(files, 1):
                    obj = e.get("object") or {}
                    text = obj.get("text")
                    if text is None or obj.get("isTruncated") or obj.get("isBinary"):
                        c["unreadable_files"] += 1
                        continue
                    uses = extract_uses(text)
                    if have_yaml:
                        y = yaml_uses(text)
                        ycheck["files"] += 1
                        if y is None:
                            ycheck["pyyaml_unparsable"] += 1
                        else:
                            a, b = collections.Counter(u["value"] for u in uses), collections.Counter(y)
                            if a == b:
                                ycheck["agree"] += 1
                            else:
                                ycheck["disagree"] += 1
                                ycheck["extra_in_scanner"] += sum((a - b).values())
                                ycheck["missing_in_scanner"] += sum((b - a).values())
                    for u in uses:
                        c["uses_total"] += 1
                        pu = parse_uses(u["value"])
                        if pu.kind != "remote":
                            c[pu.kind] += 1
                            if pu.kind == "local" and not REUSABLE_LOCAL.match(pu.value):
                                c["local_actions_unread"] += 1
                            continue
                        cn = canon.get(pu.slug, pu.slug)
                        info = infos.get(pu.slug)
                        v = classify(pu, info)
                        fp = (cn.split("/")[0] if info and info.exists else pu.owner.lower()) in FIRST_PARTY
                        pinned = v.verdict in ("sha", "sha-unresolvable")
                        c["remote"] += 1
                        c["reusable_workflow"] += pu.reusable_workflow
                        c["ambiguous"] += v.ambiguous
                        if v.verdict == "mutable-tag":
                            c[f"mutable_{v.form}"] += 1
                        else:
                            c[v.verdict.replace("-", "_")] += 1
                        c["immutable_tag_major"] += v.verdict == "immutable-tag" and v.form == "major"
                        c["first_party"] += fp
                        c["third_party"] += not fp
                        c["third_party_sha"] += (not fp) and pinned
                        c["sha_with_version_comment"] += pinned and bool(VERSION_COMMENT.search(u["comment"] or ""))
                        is_tag = v.verdict in ("immutable-tag", "mutable-tag")
                        prot = v.verdict == "immutable-tag"
                        alt = bool(v.immutable_alternative)
                        for key, pub in (("h1", info is not None and info.latest_release_immutable is True),
                                         ("h1any", info is not None and info.any_immutable_release)):
                            if is_tag and pub:
                                c[f"{key}_n"] += 1
                                c[f"{key}_protected"] += prot
                                c[f"{key}_alt"] += (not prot) and alt
                        pa = per_action[cn]
                        pa[f"refs_{p}"] += 1
                        action_repos[(cn, p)].add(label)
                        pa[f"immutable_tag_{p}"] += prot
                        if is_tag and info is not None and info.latest_release_immutable is True and not prot:
                            pa[f"h1_unprotected_{p}"] += 1
                        pa[f"sha_unresolvable_{p}"] += v.verdict == "sha-unresolvable"
                        if not public_action[cn]:
                            # never published per reference: in a public workflow the one unlisted line would
                            # reveal which action a pseudonym stands for
                            c["refs_to_user_actions"] += 1
                        elif org:
                            ref_rows.append({
                                "pop": p, "repo": label, "file_no": fno, "line": u["line"],
                                "kind": "reusable-workflow" if pu.reusable_workflow else "action",
                                "action_repo": alabel[cn], "first_party": fp, "ref": pu.ref, "form": pu.form,
                                "verdict": v.verdict, "ambiguous": v.ambiguous,
                                "immutable_alternative": v.immutable_alternative or "",
                                "version_comment": bool(VERSION_COMMENT.search(u["comment"] or "")),
                            })
            cols = ["workflow_files", "unreadable_files", "uses_total", "remote", "local", "local_actions_unread",
                    "self", "docker", "expression", "invalid", "sha", "sha_unresolvable", "immutable_tag",
                    "immutable_tag_major"] + [f"mutable_{f}" for f in MUT] + [
                    "branch", "unresolved", "ambiguous", "reusable_workflow", "first_party", "third_party",
                    "third_party_sha", "sha_with_version_comment", "refs_to_user_actions", "h1_n", "h1_protected", "h1_alt",
                    "h1any_n", "h1any_protected", "h1any_alt"]
            row.update({k: c.get(k, 0) for k in cols})
            repos_rows.append(row)
    repos_rows.sort(key=lambda r: (r["pop"], r["owner_type"] != "Organization", r["repo"].lower()))
    ref_rows.sort(key=lambda r: (r["pop"], r["repo"].lower(), str(r["file_no"]).zfill(4), str(r["line"]).zfill(6),
                                 r["action_repo"]))

    # one row per canonical action repository
    rep = {}
    for s, c in sorted(canon.items()):
        rep.setdefault(c, s)
    act_rows, res_rows = [], []
    for c in sorted(ctype, key=lambda c: alabel[c]):
        group = [s for s in canon if canon[s] == c]
        i = infos[rep[c]]
        pub = public_action[c]
        pa = per_action[c]
        act_rows.append({
            "action_repo": alabel[c], "owner_type": i.owner_type if pub else ("missing" if not i.exists else "User"),
            "first_party": pub and c.split("/")[0] in FIRST_PARTY,
            "exists": i.exists, "archived": i.archived, "written_names": len(group),
            "latest_release_tag": (i.latest_release_tag or "") if pub else "",
            "latest_release_immutable": "" if i.latest_release_immutable is None else i.latest_release_immutable,
            "any_immutable_release": any(infos[s].any_immutable_release for s in group),
            "releases_seen": i.releases_seen if pub else "",
            "refs_A": pa["refs_A"], "repos_A": len(action_repos[(c, "A")]),
            "refs_B": pa["refs_B"], "repos_B": len(action_repos[(c, "B")]),
            "immutable_tag_A": pa["immutable_tag_A"], "immutable_tag_B": pa["immutable_tag_B"],
            "h1_unprotected_A": pa["h1_unprotected_A"], "h1_unprotected_B": pa["h1_unprotected_B"],
            "sha_unresolvable_A": pa["sha_unresolvable_A"], "sha_unresolvable_B": pa["sha_unresolvable_B"]})
        if not pub:
            continue
        seen = set()
        for s in group:
            ii = infos[s]
            for r in actions_raw[s]["refs"]:
                if r in seen:
                    continue
                seen.add(r)
                rel = ii.release_of.get(r)
                commit = ii.tags.get(r) if r in ii.tags else ii.branches.get(r)
                alt = (ii.immutable_by_commit.get(commit) or [""])[0] if commit else ""
                res_rows.append({"action_repo": alabel[c], "ref": r, "is_tag": r in ii.tags, "is_branch": r in ii.branches,
                                 "release": "" if rel is None else ("immutable" if rel["immutable"] else "mutable"),
                                 "immutable_at_same_commit": alt, "sha_is_commit": ""})
            for sha, ok in sorted(ii.shas.items()):
                if sha not in seen:
                    seen.add(sha)
                    res_rows.append({"action_repo": alabel[c], "ref": sha, "is_tag": False, "is_branch": False,
                                     "release": "", "immutable_at_same_commit": "", "sha_is_commit": ok})
    write_csv("repos.csv", repos_rows)
    write_csv("references.csv", ref_rows)
    write_csv("actions.csv", act_rows)
    write_csv("ref_resolution.csv", res_rows)
    pub = {k: pop[k] for k in ("frame_sizes", "a_cutoff_stars", "seed", "pushed_since", "qualifiers", "enumerated_utc")}
    pub["population_sizes"] = {"A": len(pop["A"]), "B": len(pop["B"])}
    pub["frame_files_sha256"] = {f: sha256_file(RAW / f"{f}.jsonl") for f in ("frame_a", "frame_b")}
    pub["frame_b_sample_note"] = "population B is stored sorted by repository id, not in random.sample() order"
    pub["sha_pins"] = {"distinct_action_sha_pairs": sum(len(d["shas"]) for d in shas_raw.values()),
                       "not_a_commit": sum(1 for d in shas_raw.values() for ok in d["shas"].values() if not ok)}
    (DATA / "population.json").write_text(json.dumps(pub, indent=1) + "\n")
    ycheck["pyyaml"] = have_yaml
    (DATA / "extractor_check.json").write_text(json.dumps(ycheck, indent=1) + "\n")
    print("repos", len(repos_rows), "org references", len(ref_rows), "action repositories", len(act_rows), "yaml", ycheck)


if __name__ == "__main__":
    main()
