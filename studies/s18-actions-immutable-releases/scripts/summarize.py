#!/usr/bin/env python3
"""Write data/summary.json: every number of the study's claims.csv, at full precision, from the published data/.

Offline, standard library only. Reuses `compute()` of scripts/06_analyse.py for the counts (so both files share
one definition), and recomputes at full precision what 06_analyse.py rounds: shares, the cluster-bootstrap
intervals (same seed and replicates) and the leave-one-repository-out range. It asserts that the rounded values
equal those of data/metrics.json.

Added here, not in metrics.json:
- `A.H1.mutable_major_lower_bound`: a lower bound on the H1 references in A that use a movable major tag.
  data/references.csv omits the references of user-owned repositories and to user-owned actions (1,502 of the
  6,586 unprotected H1 references), so their forms are bounded per repository with the form counts of
  data/repos.csv: the omitted non-major ones are at most min(omitted unprotected H1 references, omitted
  non-major mutable tags).
- `dates`: from data/sources/excerpts.json (changelog and roadmap publication dates) and data/population.json;
  the public-preview date (2025-08-26), the roadmap's "Public preview 3-6 months" and the month
  ensure-immutable-actions started (2025-11) are constants read from the sources cited in paper.md.
- `prior`: data/sources/prior_work_numbers.json, as published.

    python3 scripts/summarize.py
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import importlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
an = importlib.import_module("06_analyse")
DATA = an.DATA


def boot_full(pairs: dict, seed: int = an.SEED, reps: int = an.REPS) -> list[float]:
    """an.cluster_boot without rounding: the same resamples, the percentiles in percent."""
    items = [v for v in pairs.values() if v[1] > 0]
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
    return [100 * stats[int(0.025 * reps)], 100 * stats[int(0.975 * reps) - 1]]


def r1(xs):
    return [round(x, 1) for x in xs]


def main() -> None:
    m = an.compute()
    published = json.loads((DATA / "metrics.json").read_text(encoding="utf-8"))
    repos = an.load("repos.csv")
    an.ints(repos)
    refs = [r for r in an.load("references.csv")]
    actions = {a["action_repo"]: a for a in an.load("actions.csv")}
    excerpts = json.loads((DATA / "sources/excerpts.json").read_text(encoding="utf-8"))
    prior = json.loads((DATA / "sources/prior_work_numbers.json").read_text(encoding="utf-8"))
    pop = m["population"]
    collected = pop["enumerated_utc"][:10]

    def published_on(key: str) -> str:
        return next(e["published"][:10] for e in excerpts if e["key"] == key and e.get("published"))

    out: dict = {
        "_about": "S18 figures from data/ (scripts/summarize.py, reusing 06_analyse.compute); full precision",
        "dates": {
            "ga": next(e["published"][:10] for e in excerpts
                       if e["key"] == "cl_immutable" and "immutable-releases-are-now-generally-available" in e["source"]),
            "public_preview": "2025-08-26",
            "roadmap": published_on("post_roadmap"),
            "roadmap_preview_window": "3-6 months",
            "ensure_immutable_actions_since": "2025-11",
            # datosh/pinned-actions commit dc9f22657c of 2026-04-27, «feat: add ImmutableReleasesAnalyzer»
            # (GitHub API, checked 2026-10-05; paper.md §2): a constant, not in data/
            "datosh_immutability_check": "April 2026",
            "collection": collected,
        },
        "population": {
            "a_cutoff_stars": pop["a_cutoff_stars"],
            "seed": pop["seed"],
            "frame_sizes": pop["frame_sizes"],
            "population_sizes": pop["population_sizes"],
            "pushed_since": pop["pushed_since"],
            "recent_days": (dt.date.fromisoformat(collected) - dt.date.fromisoformat(pop["pushed_since"])).days,
            "b_stars_min": 1000,
            "b_stars_max": 5000,
        },
    }

    for p in ("A", "B"):
        mp, pp = m[p], published[p]
        ok = [r for r in repos if r["pop"] == p and r["status"] == "ok"]
        W = [r for r in ok if r["remote"] > 0]
        Hr = [r for r in ok if r["h1_n"] > 0]
        h1pairs = {r["repo"]: (r["h1_protected"], r["h1_n"]) for r in Hr}
        altpairs = {r["repo"]: (r["h1_alt"], r["h1_n"] - r["h1_protected"]) for r in Hr}
        pin = {r["repo"]: (r["sha"] + r["sha_unresolvable"], r["remote"]) for r in W}
        H1 = mp["H1"]
        xp, n = H1["protected"], H1["n"]
        loo = [100 * (xp - v[0]) / (n - v[1]) for v in h1pairs.values() if n - v[1] > 0]
        h1_ci, alt_ci, sha_ci = boot_full(h1pairs), boot_full(altpairs), boot_full(pin)
        assert r1(h1_ci) == pp["H1"]["ci95_boot"] and r1(alt_ci) == pp["H1"]["alt_ci95_boot"], p
        assert r1(sha_ci) == pp["sha_share"]["ci95_boot"], p
        assert [round(min(loo), 1), round(max(loo), 1)] == pp["H1"]["leave_one_repo_out_pct"], p
        shares = [v[0] / v[1] for v in pin.values()]
        remote = mp["uses"]["remote"]
        sx, sn = mp["sha_share"]["x"], mp["sha_share"]["n"]
        top1 = mp["sha_share_without_top1"]
        H3 = mp["H3"]
        q = {
            "repos": {"with_remote_refs": mp["repos"]["with_remote_refs"]},
            "uses": {"remote": remote},
            "verdicts": {k.replace("-", "_"): v for k, v in mp["verdicts"].items()},
            "immutable_tag_share": mp["verdicts"]["immutable-tag"] / remote,
            "H1": {
                "protected": xp, "n": n, "share": xp / n,
                "ci95_lo_pct": h1_ci[0], "ci95_hi_pct": h1_ci[1],
                "mutable": H1["mutable"],
                "alt": H1["mutable_with_immutable_alternative"],
                "alt_share": H1["mutable_with_immutable_alternative"] / H1["mutable"],
                "alt_ci95_lo_pct": alt_ci[0], "alt_ci95_hi_pct": alt_ci[1],
                "top_contributor_protected": H1["top_contributor"]["protected"],
                "loo_min_pct": min(loo), "loo_max_pct": max(loo),
            },
            "sha_share": {"x": sx, "n": sn, "share": sx / sn, "ci95_lo_pct": sha_ci[0], "ci95_hi_pct": sha_ci[1]},
            "sha_share_without_top1": {"x": top1["x"], "n": top1["n"], "share": top1["x"] / top1["n"],
                                       "dropped_refs": top1["dropped_refs"], "dropped_named": top1["dropped_named"]},
            "sha_share_per_repo_median": an.median(shares),
            "H3": {"all_sha": H3["all_sha"], "n": H3["n"], "share": H3["all_sha"] / H3["n"],
                   "with_unread_local_actions": H3["with_unread_local_actions"],
                   "lower_bound": H3["lower_bound"], "lower_share": H3["lower_bound"] / H3["n"]},
        }
        if p == "A":
            # lower bound on the H1 references that use a movable major tag (see the docstring)
            h1refs = collections.defaultdict(list)
            nonmajor_pub = collections.Counter()
            for r in refs:
                if r["pop"] != p:
                    continue
                if r["verdict"] == "mutable-tag" and r["form"] != "major":
                    nonmajor_pub[r["repo"]] += 1
                a = actions.get(r["action_repo"])
                if r["verdict"] in ("immutable-tag", "mutable-tag") and a and a["latest_release_immutable"] is True:
                    h1refs[r["repo"]].append(r)
            published_h1 = sum(len(v) for v in h1refs.values())
            nonmajor_ub = 0
            for r in Hr:
                pu = [x for x in h1refs.get(r["repo"], []) if x["verdict"] == "mutable-tag"]
                omitted = (r["h1_n"] - r["h1_protected"]) - len(pu)
                nonmajor_all = r["mutable_minor"] + r["mutable_full"] + r["mutable_other"]
                nonmajor_ub += sum(x["form"] != "major" for x in pu) + min(omitted, nonmajor_all - nonmajor_pub[r["repo"]])
            q["H1"]["published_refs"] = published_h1
            q["H1"]["mutable_nonmajor_upper_bound"] = nonmajor_ub
            q["H1"]["mutable_major_lower_bound"] = H1["mutable"] - nonmajor_ub
        out[p] = q

    H2 = m["H2"]
    out["H2"] = {
        "top": H2["top"], "latest_immutable": H2["latest_immutable"], "share": H2["latest_immutable"] / H2["top"],
        "action_repos_referenced_A": m["A"]["action_repos"]["referenced"],
        "first_party_all_n": H2["first_party_all"]["n"],
    }
    for owner in ("actions", "github"):
        fp = H2[f"first_party_{owner}"]
        out["H2"][f"first_party_{owner}"] = {"x": fp["x"], "n": fp["n"], "share": fp["x"] / fp["n"],
                                             "immutable": fp["immutable"], "mutable": fp["mutable"]}
    da = prior["datosh_archive_april_2026"]
    out["prior"] = prior
    out["prior_derived"] = {
        "datosh_share": da["fully_pinned"] / da["using_actions"],
        "datosh_first_1000_share": da["first_1000_fully_pinned"] / da["first_1000_using_actions"],
        "kubo_ndss26_share": prior["kubo_ndss26"]["p4_implemented"] / prior["kubo_ndss26"]["p4_target"],
    }
    (DATA / "summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"data/summary.json: H1 A {out['A']['H1']['protected']} of {out['A']['H1']['n']}, "
          f"major lower bound {out['A']['H1']['mutable_major_lower_bound']} of {out['A']['H1']['mutable']} unprotected")


if __name__ == "__main__":
    main()
