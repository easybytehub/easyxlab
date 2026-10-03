"""Step 6 (offline): every figure of the study, from the published tables in data/.

Re-classifies every reference from data/ref_resolution.csv with uses_check.classify() and checks
that the stored verdicts agree, then writes data/metrics.json and data/tables.md.
`compute()` is also imported by check_headline.py.
"""
from __future__ import annotations

import collections
import csv
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from uses_check import RepoInfo, UsesRef, classify, ref_form  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
SEED, REPS, TOP = 20261003, 2000, 50


def load(name: str) -> list[dict]:
    with open(DATA / name, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            if v in ("True", "False"):
                r[k] = v == "True"
    return rows


def fmt(x: int, n: int) -> str:
    return f"{x:,} of {n:,} ({100 * x / n:.1f}%)" if n else f"{x:,} of 0"


def pct(x: int, n: int) -> float:
    return round(100 * x / n, 1) if n else None


def wilson(x: int, n: int, z: float = 1.959964) -> list:
    if not n:
        return [None, None]
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def cluster_boot(pairs: dict, seed: int = SEED, reps: int = REPS) -> list:
    """pairs: repo -> (x, n). Percentile 95% interval of sum(x)/sum(n), resampling repositories."""
    items = [v for v in pairs.values() if v[1] > 0]
    if not items:
        return [None, None]
    rng = random.Random(seed)
    k = len(items)
    stats = []
    for _ in range(reps):
        sx = sn = 0
        for _ in range(k):
            x, n = items[rng.randrange(k)]
            sx += x
            sn += n
        stats.append(sx / sn)
    stats.sort()
    return [round(100 * stats[int(0.025 * reps)], 1), round(100 * stats[int(0.975 * reps) - 1], 1)]


def rebuild_infos(actions: list[dict], resolution: list[dict]) -> dict:
    infos = {}
    for a in actions:
        infos[a["action_repo"]] = RepoInfo(exists=a["exists"], archived=a["archived"])
    for r in resolution:
        i = infos[r["action_repo"]]
        ref = r["ref"]
        if r["sha_is_commit"] != "":
            i.shas[ref.lower()] = r["sha_is_commit"]
            continue
        if r["is_tag"]:
            i.tags[ref] = "t:" + ref
        if r["is_branch"]:
            i.branches[ref] = "b:" + ref
        if r["release"]:
            i.release_of[ref] = {"immutable": r["release"] == "immutable", "commit": None}
        if r["immutable_at_same_commit"]:
            key = ("t:" if r["is_tag"] else "b:") + ref
            i.immutable_by_commit[key] = [r["immutable_at_same_commit"]]
    return infos


TEXT_COLS = {"ref", "immutable_alternative", "latest_release_tag", "repo", "action_repo", "form", "stars_band"}


def ints(rows: list[dict]) -> None:
    for r in rows:
        for k, v in r.items():
            if k not in TEXT_COLS and isinstance(v, str) and v.isdigit():
                r[k] = int(v)


def median(xs: list[float]) -> float:
    xs = sorted(xs)
    n = len(xs)
    return (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2) if n else None


def compute() -> dict:
    repos, refs = load("repos.csv"), load("references.csv")
    actions, resolution = load("actions.csv"), load("ref_resolution.csv")
    for t in (repos, refs, actions):
        ints(t)
    population = json.loads((DATA / "population.json").read_text())
    act = {a["action_repo"]: a for a in actions}
    infos = rebuild_infos(actions, resolution)

    # 1. offline re-classification of every reference whose ref is published (organisation repos -> organisation actions)
    mismatches = checked = 0
    for r in refs:
        if r["ref"] == "":
            continue
        checked += 1
        u = UsesRef(value="", kind="remote", ref=r["ref"], form=ref_form(r["ref"]))
        v = classify(u, infos.get(r["action_repo"]))
        if v.verdict != r["verdict"] or (v.immutable_alternative or "") != r["immutable_alternative"]:
            mismatches += 1
    # 2. the per-reference rows of organisation repositories must add up to their aggregate counts
    agg = collections.defaultdict(collections.Counter)
    for r in refs:
        agg[(r["pop"], r["repo"])]["remote"] += 1
        agg[(r["pop"], r["repo"])][r["verdict"]] += 1
    inconsistent = 0
    for r in repos:
        if r["owner_type"] == "Organization" and r["status"] == "ok":
            g = agg[(r["pop"], r["repo"])]
            if g["remote"] + r["refs_to_user_actions"] != r["remote"] or (r["refs_to_user_actions"] == 0 and (
                    g["sha"], g["sha-unresolvable"], g["immutable-tag"], g["branch"]) != (
                    r["sha"], r["sha_unresolvable"], r["immutable_tag"], r["branch"])):
                inconsistent += 1
    m: dict = {"reclassification_checked": checked, "reclassification_mismatches": mismatches,
               "aggregate_inconsistencies": inconsistent, "population": population}

    for p in ("A", "B"):
        R = [r for r in repos if r["pop"] == p]
        ok = [r for r in R if r["status"] == "ok"]
        W = [r for r in ok if r["remote"] > 0]
        S = lambda k, rows=ok: sum(r[k] for r in rows)  # noqa: E731
        mp: dict = {}
        mp["repos"] = {"population": len(R), "ok": len(ok),
                       "excluded": dict(collections.Counter(r["status"] for r in R if r["status"] != "ok")),
                       "organisation": sum(r["owner_type"] == "Organization" for r in R),
                       "with_workflow_files": sum(r["workflow_files"] > 0 for r in ok), "with_remote_refs": len(W),
                       "unreadable_files": S("unreadable_files"), "workflow_files": S("workflow_files")}
        mp["uses"] = {k: S(k) for k in ("uses_total", "remote", "local", "local_actions_unread", "self", "docker",
                                         "expression", "invalid", "reusable_workflow")}
        mut = {f: S(f"mutable_{f}") for f in ("major", "minor", "full", "other")}
        mp["verdicts"] = {"sha": S("sha"), "sha-unresolvable": S("sha_unresolvable"), "immutable-tag": S("immutable_tag"),
                          "mutable-tag": sum(mut.values()), "branch": S("branch"), "unresolved": S("unresolved")}
        n_remote = mp["uses"]["remote"]
        mp["verdict_pct"] = {k: pct(v, n_remote) for k, v in mp["verdicts"].items()}
        mp["mutable_tag_forms"] = mut
        mp["immutable_tag_major"] = S("immutable_tag_major")
        mp["ambiguous_tag_branch"] = S("ambiguous")

        # SHA-pinned references (sha + sha-unresolvable): pooled, per repository, and without the largest repositories
        pin = {r["repo"]: (r["sha"] + r["sha_unresolvable"], r["remote"]) for r in W}
        x = sum(v[0] for v in pin.values())
        mp["sha_share"] = {"x": x, "n": n_remote, "text": fmt(x, n_remote), "ci95_boot": cluster_boot(pin)}
        big = sorted(W, key=lambda r: -r["remote"])
        for k in (1, 3):
            drop = big[:k]
            xx = x - sum(pin[r["repo"]][0] for r in drop)
            nn = n_remote - sum(r["remote"] for r in drop)
            mp[f"sha_share_without_top{k}"] = {"x": xx, "n": nn, "text": fmt(xx, nn),
                                                "dropped_refs": [r["remote"] for r in drop],
                                                "dropped_named": [r["repo"] if r["owner_type"] == "Organization" else "(user-owned)" for r in drop]}
        shares = [v[0] / v[1] for v in pin.values()]
        mp["sha_share_per_repo"] = {"median_pct": round(100 * median(shares), 1), "mean_pct": round(100 * sum(shares) / len(shares), 1),
                                    "repos": len(shares)}
        mp["sha_with_version_comment"] = {"x": S("sha_with_version_comment"), "n": x, "text": fmt(S("sha_with_version_comment"), x)}
        mp["repos_with_some_sha"] = sum(v[0] > 0 for v in pin.values())

        def h1(key):
            Hr = [r for r in ok if r[f"{key}_n"] > 0]
            pairs = {r["repo"]: (r[f"{key}_protected"], r[f"{key}_n"]) for r in Hr}
            xp, n = sum(v[0] for v in pairs.values()), sum(v[1] for v in pairs.values())
            alt = sum(r[f"{key}_alt"] for r in Hr)
            altpairs = {r["repo"]: (r[f"{key}_alt"], r[f"{key}_n"] - r[f"{key}_protected"]) for r in Hr}
            top = sorted(Hr, key=lambda r: -r[f"{key}_protected"])
            loo = [100 * (xp - v[0]) / (n - v[1]) for v in pairs.values() if n - v[1] > 0]
            return {"protected": xp, "n": n, "pct": pct(xp, n), "ci95_boot": cluster_boot(pairs), "text": fmt(xp, n),
                    "repos_with_such_refs": len(Hr), "repos_with_unprotected": sum(1 for v in pairs.values() if v[0] < v[1]),
                    "repos_all_protected": sum(1 for v in pairs.values() if v[0] == v[1]),
                    "mutable": n - xp, "mutable_with_immutable_alternative": alt, "alt_text": fmt(alt, n - xp),
                    "alt_ci95_boot": cluster_boot(altpairs),
                    "top_contributor": {"protected": top[0][f"{key}_protected"], "of_its_refs": top[0][f"{key}_n"],
                                        "share_of_protected_pct": pct(top[0][f"{key}_protected"], xp),
                                        "repo": top[0]["repo"] if top[0]["owner_type"] == "Organization" else "(user-owned)"},
                    "top5_protected": sum(r[f"{key}_protected"] for r in top[:5]),
                    "leave_one_repo_out_pct": [round(min(loo), 1), round(max(loo), 1)]}

        mp["H1"] = h1("h1")
        mp["H1_any_immutable"] = h1("h1any")

        # H3: every remote reference SHA-pinned. Upper bound: local actions outside .github/workflows were not read.
        allsha = [r for r in W if r["sha"] + r["sha_unresolvable"] == r["remote"]]
        lower = [r for r in allsha if r["local_actions_unread"] == 0]
        mp["H3"] = {"all_sha": len(allsha), "n": len(W), "pct": pct(len(allsha), len(W)), "text": fmt(len(allsha), len(W)),
                    "with_unread_local_actions": len(allsha) - len(lower),
                    "lower_bound": len(lower), "lower_text": fmt(len(lower), len(W)),
                    "wilson95": wilson(len(allsha), len(W)) if p == "B" else None,
                    "lower_wilson95": wilson(len(lower), len(W)) if p == "B" else None}
        T = [r for r in ok if r["third_party"] > 0]
        x3 = sum(r["third_party_sha"] == r["third_party"] for r in T)
        mp["H3_third_party"] = {"all_sha": x3, "n": len(T), "pct": pct(x3, len(T)), "text": fmt(x3, len(T))}

        rel = [r for r in ok if r["latest_release_immutable"] != ""]
        xi = sum(r["latest_release_immutable"] is True for r in rel)
        xs = sum(r["latest_release_sbom_asset"] is True for r in rel)
        mp["own_latest_release_immutable"] = {"x": xi, "n": len(rel), "text": fmt(xi, len(rel))}
        mp["own_latest_release_sbom_asset"] = {"x": xs, "n": len(rel), "text": fmt(xs, len(rel))}

        used = [a for a in actions if a[f"repos_{p}"] > 0]
        res = [a for a in used if a["exists"]]
        wr = [a for a in res if a["latest_release_immutable"] != ""]
        li = sum(a["latest_release_immutable"] is True for a in res)
        ai = sum(a["any_immutable_release"] is True for a in res)
        mp["action_repos"] = {"referenced": len(used), "resolved": len(res), "with_latest_release": len(wr),
                              "latest_immutable": li, "latest_immutable_text": fmt(li, len(res)),
                              "latest_immutable_of_releasing_text": fmt(li, len(wr)),
                              "any_immutable": ai, "any_immutable_text": fmt(ai, len(res))}
        mp["immutable_tag_by_action"] = sorted(((a["action_repo"], a[f"immutable_tag_{p}"]) for a in used if a[f"immutable_tag_{p}"]),
                                               key=lambda t: (-t[1], t[0]))[:10]
        mp["H1_unprotected_by_action"] = sorted(((a["action_repo"], a[f"h1_unprotected_{p}"]) for a in used if a[f"h1_unprotected_{p}"]),
                                                key=lambda t: (-t[1], t[0]))[:12]
        mp["sha_unresolvable_action_repos"] = sum(1 for a in used if a[f"sha_unresolvable_{p}"])
        m[p] = mp

    usedA = sorted((a for a in actions if a["repos_A"] > 0), key=lambda a: (-a["repos_A"], -a["refs_A"], a["action_repo"]))
    top = usedA[:TOP]
    xt = sum(a["latest_release_immutable"] is True for a in top)
    m["H2"] = {"top": TOP, "latest_immutable": xt, "text": fmt(xt, len(top)),
               "any_immutable": sum(a["any_immutable_release"] is True for a in top),
               "top_first_party": sum(a["first_party"] for a in top),
               "top_first_party_immutable": sum(a["first_party"] and a["latest_release_immutable"] is True for a in top),
               "table": [{k: a[k] for k in ("action_repo", "first_party", "repos_A", "refs_A", "latest_release_tag",
                                            "latest_release_immutable", "any_immutable_release")} for a in top]}
    for owner in ("actions", "github"):
        fp = [a for a in usedA if a["action_repo"].startswith(owner + "/") and a["exists"]]
        x = sum(a["latest_release_immutable"] is True for a in fp)
        m["H2"][f"first_party_{owner}"] = {"x": x, "n": len(fp), "text": fmt(x, len(fp)),
                                           "immutable": sorted(a["action_repo"] for a in fp if a["latest_release_immutable"] is True),
                                           "mutable": sorted(a["action_repo"] for a in fp if a["latest_release_immutable"] is not True)}
    fpall = [a for a in usedA if a["first_party"] and a["exists"]]
    xf = sum(a["latest_release_immutable"] is True for a in fpall)
    m["H2"]["first_party_all"] = {"x": xf, "n": len(fpall), "text": fmt(xf, len(fpall))}
    tp = [a for a in usedA if not a["first_party"] and a["exists"]]
    xt3 = sum(a["latest_release_immutable"] is True for a in tp)
    m["H2"]["third_party_all"] = {"x": xt3, "n": len(tp), "text": fmt(xt3, len(tp))}
    m["action_repos_total"] = {"canonical": len(actions), "resolved": sum(a["exists"] for a in actions)}
    return m


def tables(m: dict) -> str:
    out = ["# S18 — tables (generated by scripts/06_analyse.py)", ""]
    for p, name in (("A", "A: top 1,000 by stars"), ("B", "B: random 500 of the 1k-5k-star frame")):
        mp = m[p]
        out += [f"## {name}", "", f"Repositories: {mp['repos']}", f"`uses:` values: {mp['uses']}", "",
                "| verdict | references | % of remote |", "|---|---:|---:|"]
        for k, v in mp["verdicts"].items():
            out.append(f"| {k} | {v:,} | {mp['verdict_pct'][k]} |")
        out += ["", f"Mutable tags by form: {mp['mutable_tag_forms']}", "",
                f"H1 (tag refs to actions whose latest release is immutable): protected {mp['H1']['text']}, "
                f"95% CI (cluster bootstrap) {mp['H1']['ci95_boot']}; leave-one-repo-out {mp['H1']['leave_one_repo_out_pct']}; "
                f"largest contributor {mp['H1']['top_contributor']}; top five {mp['H1']['top5_protected']}",
                f"H1b (unprotected with an immutable tag at the same commit): {mp['H1']['alt_text']}, CI {mp['H1']['alt_ci95_boot']}",
                f"H1 sensitivity (any immutable release): {mp['H1_any_immutable']['text']}",
                f"H3 (all remote refs SHA-pinned, upper bound): at most {mp['H3']['text']}; excluding the "
                f"{mp['H3']['with_unread_local_actions']} that call unread local actions: {mp['H3']['lower_text']}"
                + (f"; Wilson 95% {mp['H3']['wilson95']} / {mp['H3']['lower_wilson95']}" if mp['H3']['wilson95'] else "")
                + f"; third-party only: {mp['H3_third_party']['text']}",
                f"SHA-pinned share of remote refs: {mp['sha_share']['text']}, CI {mp['sha_share']['ci95_boot']}; without the largest "
                f"repository {mp['sha_share_without_top1']['text']}; without the three largest {mp['sha_share_without_top3']['text']}; "
                f"per-repository median {mp['sha_share_per_repo']['median_pct']}%, mean {mp['sha_share_per_repo']['mean_pct']}%",
                f"SHA pins with a version comment: {mp['sha_with_version_comment']['text']}; SHA pins that are not a commit "
                f"(sha-unresolvable): {mp['verdicts']['sha-unresolvable']}",
                f"Action repositories: {mp['action_repos']}",
                f"Most unprotected (H1): {mp['H1_unprotected_by_action']}",
                f"Most immutable-tag references: {mp['immutable_tag_by_action']}",
                f"Own latest release immutable: {mp['own_latest_release_immutable']['text']}; "
                f"SBOM-like asset: {mp['own_latest_release_sbom_asset']['text']}", ""]
    h2 = m["H2"]
    out += [f"## Most-used action repositories in A (top {h2['top']} by repositories)", "",
            f"Latest release immutable: {h2['text']}; first party in top: {h2['top_first_party']} "
            f"({h2['top_first_party_immutable']} immutable)",
            f"actions/*: {h2['first_party_actions']['text']}; github/*: {h2['first_party_github']['text']}; "
            f"third-party: {h2['third_party_all']['text']}", "",
            "| # | action repository | first party | repos (A) | refs (A) | latest release | immutable |",
            "|---:|---|---|---:|---:|---|---|"]
    for n, a in enumerate(h2["table"], 1):
        out.append(f"| {n} | {a['action_repo']} | {'yes' if a['first_party'] else ''} | {a['repos_A']} | {a['refs_A']} | "
                   f"{a['latest_release_tag'] or '—'} | {'yes' if a['latest_release_immutable'] is True else 'no' if a['latest_release_immutable'] is False else '—'} |")
    out += ["", f"actions/* immutable: {', '.join(h2['first_party_actions']['immutable'])}",
            f"actions/* not immutable: {', '.join(h2['first_party_actions']['mutable'])}",
            f"github/* immutable: {', '.join(h2['first_party_github']['immutable'])}",
            f"github/* not immutable: {', '.join(h2['first_party_github']['mutable'])}", ""]
    return "\n".join(out)


def main() -> None:
    m = compute()
    assert m["reclassification_mismatches"] == 0, f"{m['reclassification_mismatches']} verdicts not reproduced"
    assert m["aggregate_inconsistencies"] == 0, f"{m['aggregate_inconsistencies']} repositories: rows and counts differ"
    (DATA / "metrics.json").write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
    (DATA / "tables.md").write_text(tables(m) + "\n")
    print("reclassified", m["reclassification_checked"], "references offline, 0 mismatches")
    for p in ("A", "B"):
        print(p, "H1", m[p]["H1"]["text"], m[p]["H1"]["ci95_boot"], "| H3 at most", m[p]["H3"]["text"], "| verdicts", m[p]["verdicts"])
    print("H2", m["H2"]["text"], "| actions/*", m["H2"]["first_party_actions"]["text"], "| github/*", m["H2"]["first_party_github"]["text"])


if __name__ == "__main__":
    main()
