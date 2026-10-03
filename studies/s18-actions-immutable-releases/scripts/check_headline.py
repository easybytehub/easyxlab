"""Check the numbers of README.md (Abstract) and paper.md (Abstract and sections 4, 6, 7) against data/.

Two checks, both on whitespace-normalised text:
1. Required fragments: every headline sentence fragment listed in `fragments()` (recomputed from data/
   with 06_analyse.compute(); metrics.json is not read) must appear with number boundaries, so that
   "312 of 6,898" does not match inside "1312 of 6,898".
2. Number accounting: every number in the checked sections must be one the data produce (any figure in
   compute()'s output, frame-query count), a prior-work figure in data/sources/prior_work_numbers.json,
   or a listed constant (sizes and thresholds of the design). A changed number that is not in that set
   fails even if no fragment covers it.
Prior-work section (paper §2) numbers are quotations; they are listed in prior_work_numbers.json but
not otherwise checked here. The check shares compute() with the analysis: it is a consistency check of
the texts against the published data, not an independent re-analysis. Exit 1 on any failure.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location("analyse", HERE / "06_analyse.py")
analyse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyse)

CONSTANTS = {"1,000", "5,000", "10,000", "20,000", "2,000", "90", "100", "50", "95", "40", "25",
             "20261003", "2022", "2025", "2026", "2027"} | {str(i) for i in range(0, 13)}


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t)


def has(fragment: str, text: str) -> bool:
    return re.search(r"(?<![\d.,])" + re.escape(norm(fragment)) + r"(?![\d])", text) is not None


def ci(c) -> str:
    return f"{c[0]}–{c[1]}%"


def p1(x, n) -> str:
    return f"{100 * x / n:.1f}"


def fragments(m: dict, prior: dict) -> tuple[dict, dict]:
    A, B, H2 = m["A"], m["B"], m["H2"]
    pop = m["population"]
    d = prior["datosh_archive_april_2026"]
    both = {
        "top A": "top 1,000 repositories by stars", "cut-off": f"{pop['a_cutoff_stars']:,} stars",
        "frame B": f"{pop['frame_sizes']['B']:,}", "remote A": f"{A['uses']['remote']:,} remote `uses:` references",
        "remote B": f"{B['uses']['remote']:,} in B", "H1 A": A["H1"]["text"], "H1 B": B["H1"]["text"],
        "H1 A CI": ci(A["H1"]["ci95_boot"]), "H1b A": A["H1"]["alt_text"], "H2": H2["text"],
        "H2 actions": H2["first_party_actions"]["text"], "H2 github": H2["first_party_github"]["text"],
        "SHA A": A["sha_share"]["text"], "SHA B": B["sha_share"]["text"],
        "median A": f"{A['sha_share_per_repo']['median_pct']}%",
        "H3 A": f"at most {A['H3']['text']}", "H3 B": B["H3"]["text"],
        "immutable share": f"Immutable tags: {A['verdict_pct']['immutable-tag']}% of references in A, "
                           f"{B['verdict_pct']['immutable-tag']}% in B",
    }
    t1b = B["sha_share_without_top1"]
    readme = dict(both, **{
        "H1 top": f"one repository holds {A['H1']['top_contributor']['protected']} of the {A['H1']['protected']}",
        "H1 LOO": f"gives {ci(A['H1']['leave_one_repo_out_pct'])}", "H1b CI": f"interval {ci(A['H1']['alt_ci95_boot'])}",
        "SHA A CI": f"interval {ci(A['sha_share']['ci95_boot'])}", "SHA B CI": f"interval {ci(B['sha_share']['ci95_boot'])}",
        "B w/o top": f"{p1(t1b['x'], t1b['n'])}% without its largest repository, {t1b['dropped_named'][0]}, which holds "
                     f"{t1b['dropped_refs'][0]:,} references",
        "median B": f"{B['sha_share_per_repo']['median_pct']}% in B", "H3 A lower": A["H3"]["lower_text"],
        "H3 unread": f"the {A['H3']['with_unread_local_actions']} that also call local actions",
        "H3 B lower": B["H3"]["lower_text"],
        "datosh": f"{d['fully_pinned']} of {d['using_actions']:,} repositories using Actions, {d['fully_pinned_pct']}%",
        "datosh 1000": f"{d['first_1000_fully_pinned']} of {d['first_1000_using_actions']} ({d['first_1000_pct']}%)",
        "NDSS": f"{prior['kubo_ndss26']['p4_pct']}% of repositories",
    })
    rows = []
    for key, lab in (("sha", "sha"), ("sha-unresolvable", "sha-unresolvable"), ("immutable-tag", "immutable-tag"),
                     ("mutable-tag", "mutable-tag"), ("branch", "branch"), ("unresolved", "unresolved")):
        rows.append(f"| {lab} | {A['verdicts'][key]:,} | {A['verdict_pct'][key]} | {B['verdicts'][key]:,} | {B['verdict_pct'][key]} |")
    fa, fb = A["mutable_tag_forms"], B["mutable_tag_forms"]
    rows += [f"| · major (`v7`) | {fa['major']:,} | | {fb['major']:,} | |", f"| · full (`v7.0.1`) | {fa['full']:,} | | {fb['full']:,} | |",
             f"| · minor and other | {fa['minor'] + fa['other']:,} | | {fb['minor'] + fb['other']:,} | |",
             f"| **remote references** | **{A['uses']['remote']:,}** | | **{B['uses']['remote']:,}** | |"]
    t3 = A["sha_share_without_top3"]
    ar = A["action_repos"]
    paper = dict(both, **{f"table {i}": r for i, r in enumerate(rows)}, **{
        "frame A": f"{pop['frame_sizes']['A']:,} public", "frame B 2": f"{pop['frame_sizes']['B']:,} such repositories",
        "queries": f"{m['frame_queries']} search-API queries",
        "wf A": f"{A['repos']['workflow_files']:,} files in {A['repos']['with_workflow_files']} repositories of A",
        "wf B": f"{B['repos']['workflow_files']:,} files in {B['repos']['with_workflow_files']} of B",
        "actions": f"{m['action_repos_total']['canonical']:,} distinct repositories ({m['action_repos_total']['resolved']:,} resolved)",
        "shas": f"{pop['sha_pins']['distinct_action_sha_pairs']:,} distinct pinned SHAs",
        "SHA A CI p": f"(interval {ci(A['sha_share']['ci95_boot'])})", "SHA B CI p": f"({ci(B['sha_share']['ci95_boot'])})",
        "w/o top3": f"A gives {t3['text']}", "w/o top1 B": f"B gives {t1b['text']}",
        "medians": f"median SHA share is {A['sha_share_per_repo']['median_pct']}% in A (mean {A['sha_share_per_repo']['mean_pct']}%) "
                   f"and {B['sha_share_per_repo']['median_pct']}% in B (mean {B['sha_share_per_repo']['mean_pct']}%)",
        "unres": f"{A['verdicts']['sha-unresolvable']} SHA pins in A, to {A['sha_unresolvable_action_repos']} action repositories",
        "comment": f"In {p1(A['sha_with_version_comment']['x'], A['sha_with_version_comment']['n'])}% of SHA pins in A",
        "reusable": f"{A['uses']['reusable_workflow']} references in A and {B['uses']['reusable_workflow']} in B call reusable",
        "H1 A CI p": f"protected tag in A ({ci(A['H1']['ci95_boot'])})", "H1 B CI p": f"in B ({ci(B['H1']['ci95_boot'])})",
        "H1any": f"gives {A['H1_any_immutable']['text']} and {B['H1_any_immutable']['text']}",
        "conc A": f"holds {A['H1']['top_contributor']['protected']} of the {A['H1']['protected']} and the top five repositories {A['H1']['top5_protected']}",
        "loo A": f"leaving out any one repository gives {ci(A['H1']['leave_one_repo_out_pct'])}",
        "conc B": f"holds {B['H1']['top_contributor']['protected']} of the {B['H1']['protected']} and the top five {B['H1']['top5_protected']}",
        "loo B": f"leaving one out gives {ci(B['H1']['leave_one_repo_out_pct'])}",
        "unprot repos": f"{A['H1']['repos_with_unprotected']} of the {A['H1']['repos_with_such_refs']} repositories",
        "alt A": f"{A['H1']['alt_text']} in A ({ci(A['H1']['alt_ci95_boot'])})", "alt B": f"{B['H1']['alt_text']} in B ({ci(B['H1']['alt_ci95_boot'])})",
        "imm major": f"{A['immutable_tag_major']} immutable-tag references in A",
        "act A": f"{ar['resolved']:,} resolved action repositories referenced in A, {ar['latest_immutable']} ({p1(ar['latest_immutable'], ar['resolved'])}%)",
        "act rel": f"{ar['latest_immutable']} of the {ar['with_latest_release']:,} that have any release ({p1(ar['latest_immutable'], ar['with_latest_release'])}%)",
        "third": f"Third party: {H2['third_party_all']['text']}", "first": f"first party: {H2['first_party_all']['text']}",
        "top fp": f"{H2['top_first_party_immutable']} of the {H2['top_first_party']} first-party",
        "H3 unread p": f"{A['H3']['with_unread_local_actions']} of those {A['H3']['all_sha']}", "H3 lower p": f"the figure is {A['H3']['lower_text']}",
        "H3 B p": f"at most {B['H3']['text'].replace(')', '')}, Wilson {ci(B['H3']['wilson95'])})",
        "H3 B low p": f"or {B['H3']['lower_text'].replace(')', '')}, {ci(B['H3']['lower_wilson95'])})",
        "H3 tp": f"{A['H3_third_party']['text']} and {B['H3_third_party']['text']}",
        "some sha": f"{A['repos_with_some_sha']} repositories of A and {B['repos_with_some_sha']}",
        "own": f"{A['own_latest_release_immutable']['text']} in A and {B['own_latest_release_immutable']['text']} in B",
        "sbom": f"{A['own_latest_release_sbom_asset']['text']} and {B['own_latest_release_sbom_asset']['text']}",
        "movable share": f"go to the movable tag {round(100 * A['H1']['mutable'] / A['H1']['n'])}% of the time",
    })
    return readme, paper


def section(text: str, title: str) -> str:
    mm = re.search(rf"^## {re.escape(title)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    body = mm.group(1) if mm else ""
    return "\n".join(line for line in body.splitlines() if not line.startswith("#"))  # drop sub-headings


def numbers(text: str) -> list[str]:
    t = re.sub(r"`[^`]*`|https?://\S+|\b\d{4}-\d{2}(-\d{2})?\b|\bv\d+(\.\d+)*\b|§\d+(\.\d+)*|doi:\S+|\b\d{1,2} [A-Z][a-z]+ \d{4}\b", " ", text)
    return re.findall(r"(?<![\w.,])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w])|(?<![\w.,])\d+(?:\.\d+)?(?![\w,])", t)


def allowed(m: dict, prior: dict) -> set:
    out = set(CONSTANTS)

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, int):
            out.update({f"{x:,}", str(x)})
        elif isinstance(x, float):
            out.update({f"{x:.1f}", str(x)})
            if x == int(x):
                out.add(str(int(x)))
        elif isinstance(x, str):
            out.update(numbers(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
    walk(m)
    walk(prior)
    return out


def first_party_lists(text: str, m: dict) -> list[str]:
    errs = []
    mm = re.search(r"for `actions/\*` \(yes:(.*?); no:(.*?)\)", text, re.S)
    if not mm:
        return ["README abstract: first-party yes/no list not found"]
    fp = m["H2"]["first_party_actions"]
    for names, ok_list, label in ((mm.group(1), fp["immutable"], "yes"), (mm.group(2), fp["mutable"], "no")):
        for n in re.findall(r"`([\w.-]+)`", names):
            if f"actions/{n}" not in ok_list:
                errs.append(f"README abstract: actions/{n} listed under '{label}' but data disagree")
    return errs


def main() -> int:
    m = analyse.compute()
    with open(ROOT / "data" / "frame_queries.csv", encoding="utf-8") as f:
        m["frame_queries"] = sum(1 for _ in csv.DictReader(f))
    prior = json.loads((ROOT / "data" / "sources" / "prior_work_numbers.json").read_text())
    errors = []
    if m["reclassification_mismatches"] or m["aggregate_inconsistencies"]:
        errors.append("stored verdicts or aggregates are not reproduced by the classifier")
    readme_req, paper_req = fragments(m, prior)
    ok_numbers = allowed(m, prior) | {n for f in list(readme_req.values()) + list(paper_req.values()) for n in numbers(f)}
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if not readme.startswith("# S18 — "):
        errors.append("README line 1 must start with '# S18 — '")
    abstract = norm(section(readme, "Abstract"))
    errors += [f"README abstract: {k}: expected '{s}'" for k, s in readme_req.items() if not has(s, abstract)]
    errors += first_party_lists(abstract, m)
    errors += [f"README abstract: number {n} is not produced by data/ or listed" for n in numbers(abstract) if n not in ok_numbers]
    n_checked = len(readme_req)
    paper = ROOT / "paper.md"
    if paper.exists():
        pt = paper.read_text(encoding="utf-8")
        checked = norm(" ".join(section(pt, t) for t in ("Abstract", "4. Data", "6. Results", "7. Discussion")))
        errors += [f"paper.md: {k}: expected '{s}'" for k, s in paper_req.items() if not has(s, checked)]
        errors += [f"paper.md: number {n} is not produced by data/ or listed" for n in numbers(checked) if n not in ok_numbers]
        n_checked += len(paper_req)
    else:
        print("paper.md is not in the public package: the paper is at https://easybyte.es/lab/studies/s18/paper/")
    for e in errors:
        print("MISMATCH:", e)
    if errors:
        return 1
    print(f"check_headline: {n_checked} fragments and every number of the checked sections verified against data/"
          + (" (README.md and paper.md)" if paper.exists() else " (README.md)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
