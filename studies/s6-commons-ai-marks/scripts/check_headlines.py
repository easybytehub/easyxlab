#!/usr/bin/env python3
"""Assert every headline number of README.md and paper.md against data/.

Recomputes everything with analyze.compute() (from data/ only), then checks that
(1) each computed value equals the value written in the documents, and
(2) the formatted string actually appears in README.md and/or paper.md.
Exit 0 if all pass; 1 otherwise. Usage: python3 scripts/check_headlines.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import analyze  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DOCS = {"README": (HERE / "README.md").read_text()}
if (HERE / "paper.md").exists():  # the public package on GitHub ships without the paper
    DOCS["paper"] = (HERE / "paper.md").read_text()


def f1(x: float) -> str:
    return f"{x:.1f}"


def main() -> int:
    H, _, _ = analyze.compute()
    m = lambda name, per: H[f"main|{name}|{per}"]  # noqa: E731
    any_ = "any machine-readable AI mark"
    c = H["cmp|main|any|junjul-janmay"]
    pp = H["cmp|main|any|post-pre"]
    pj = H["cmp|main|any|post-junjul"]
    nc = H["cmp|main excl. coats of arms|any|post-pre"]
    ncj = H["cmp|main excl. coats of arms|any|post-junjul"]
    un_j, un_p = H["cmp|union|any|junjul-janmay"], H["cmp|union|any|post-pre"]
    cfg = H["cfg"]
    checks = [
        # (label, computed, text that must appear, documents)
        ("measured union", H["measured"], "2,084", ("README", "paper")),
        ("measured main", H["main_n"], "1,585", ("README", "paper")),
        ("Jan-May any mark %", m(any_, "janmay")[0], f"{f1(m(any_, 'janmay')[0])}% of January–May uploads (n = {m(any_, 'janmay')[4]})", ("README", "paper")),
        ("Jun-Jul any mark %", m(any_, "junjul")[0], f"{f1(m(any_, 'junjul')[0])}% of June–July uploads (n = {m(any_, 'junjul')[4]})", ("README", "paper")),
        ("June jump pp", c[2], f"+{f1(c[2])} percentage points", ("README", "paper")),
        ("June jump bootstrap", (c[5], c[6]), f"+{f1(c[5])} to +{f1(c[6])}", ("README", "paper")),
        ("June jump table", c, f"| Jun–Jul vs Jan–May | +{f1(c[2])} | +{f1(c[3])}, +{f1(c[4])} | **+{f1(c[5])}, +{f1(c[6])}** |", ("paper",)),
        ("Aug-Sep any mark", m(any_, "post")[0], f"{f1(m(any_, 'post')[0])}% (n = {m(any_, 'post')[4]})" if False else f"August–September (n = {m(any_, 'post')[4]}) shows {f1(m(any_, 'post')[0])}%", ("README", "paper")),
        ("Aug-Sep excl coats of arms", H["exclcoa|any|post"][0], f"{f1(H['exclcoa|any|post'][0])}% without", ("README", "paper")),
        ("pre/post pp", pp[2], f"+{f1(pp[2])} pp (day-cluster bootstrap +{f1(pp[5])} to +{round(pp[6])})", ("README", "paper")),
        ("pre/post table", pp, f"| Aug–Sep vs Jan–Jul | +{f1(pp[2])} | +{f1(pp[3])}, +{f1(pp[4])} | +{f1(pp[5])}, +{f1(pp[6])} |", ("paper",)),
        ("excl coats pre/post", nc[2], f"| same, without coats of arms | +{f1(nc[2])} | +{f1(nc[3])}, +{f1(nc[4])} | +{f1(nc[5])}, +{f1(nc[6])} |", ("paper",)),
        ("excl coats pp in abstract", nc[2], f"the difference is +{f1(nc[2])} pp", ("README", "paper")),
        ("post vs junjul", pj, f"| Aug–Sep vs Jun–Jul | {f1(pj[2]).replace('-', '−')} | {f1(pj[3]).replace('-', '−')}, +{f1(pj[4])} | {f1(pj[5]).replace('-', '−')}, +{f1(pj[6])} |", ("paper",)),
        ("post vs junjul excl", ncj, f"| Aug–Sep vs Jun–Jul, without coats of arms | +{f1(ncj[2])} | {f1(ncj[3]).replace('-', '−')}, +{f1(ncj[4])} | {f1(ncj[5]).replace('-', '−')}, +{f1(ncj[6])} |", ("paper",)),
        ("union june / prepost", (un_j[2], un_p[2]), f"+{f1(un_j[2])} pp for the June jump, +{f1(un_p[2])} pp", ("paper",)),
        ("coats of arms August", H["coa_aug"], f"{H['coa_aug'][0]} of the {H['coa_aug'][1]} sampled main files", ("paper",)),
        ("coats of arms marked", H["coa_aug"][2], f"only {H['coa_aug'][2]} of those {H['coa_aug'][0]} are marked", ("paper",)),
        ("IPTC only share", H["profile"]["IPTC AI only"][1], f"{f1(H['profile']['IPTC AI only'][1])}% of main files", ("README", "paper")),
        ("AIGC readable union", H["aigc"]["readable_union"], "A readable Chinese AIGC label appears on 1 file of the union, and 3 more files carry a double-encoded label", ("README", "paper")),
        ("AIGC double main", H["aigc"]["double_main"], "Three more (one in the main population)", ("paper",)),
        ("readable manifests", H["readable"][0], f"{H['readable'][0]} readable manifests", ("README", "paper")),
        ("0.1.0 failures", H["fails010"][0], f"rejected {H['fails010'][0]} of the {H['readable'][0]}", ("README", "paper")),
        ("class D", H["classes"]["D"][0], f"{H['classes']['D'][0]} of them because no extended-key-usage list", ("README", "paper")),
        ("0.1.1 failures", H["fails011"][0], f"{H['fails011'][0]} manifests ({f1(100 * H['fails011'][0] / H['readable'][0])}%) fail", ("README", "paper")),
        ("trusted official", cfg["ai-mark-lint 0.1.1 rule, official list + TSA list (emulated)"][1],
         f"{cfg['ai-mark-lint 0.1.1 rule, official list + TSA list (emulated)'][1]} of {cfg['ai-mark-lint 0.1.1 rule, official list + TSA list (emulated)'][0]} manifests (72%) are valid and trusted", ("README", "paper")),
        ("only config", H["only_config"][0], f"Of the 302 failures under 0.1.0, {H['only_config'][0]} disappear under 0.1.1", ("paper",)),
        ("class B", H["classes"]["B"][0], f"expired in manifests without a time-stamp ({H['classes']['B'][0]})", ("README", "paper")),
        ("class A", H["classes"]["A"][0], f"content changed after signing ({H['classes']['A'][0]})", ("README", "paper")),
        ("class F", H["classes"]["F"][0], f"first-action rule violations ({H['classes']['F'][0]})", ("README", "paper")),
        ("class E", H["classes"]["E"][0], f"Microsoft Paint manifests ({H['classes']['E'][0]})", ("README", "paper")),
        ("decomp OpenAI", H["decomp"]["OpenAI"], f"| OpenAI-signed | {f1(H['decomp']['OpenAI'][0])}% | {f1(H['decomp']['OpenAI'][1])}% | +{f1(H['decomp']['OpenAI'][2])} pp |", ("paper",)),
        ("decomp Google", H["decomp"]["Google"], f"| Google-signed | {f1(H['decomp']['Google'][0])}% | {f1(H['decomp']['Google'][1])}% | +{f1(H['decomp']['Google'][2])} pp |", ("paper",)),
        ("decomp Microsoft", H["decomp"]["Microsoft"], f"| Microsoft-signed | {f1(H['decomp']['Microsoft'][0])}% | {f1(H['decomp']['Microsoft'][1])}% | +{f1(H['decomp']['Microsoft'][2])} pp |", ("paper",)),
        ("MS batch 8 June", H["ms_batch_0608"], f"{H['ms_batch_0608']} Bing Image Creator files uploaded on 8 June", ("paper",)),
        ("MSA April/May", (H["month"]["2026-04"]["msa"], H["month"]["2026-05"]["msa"]),
         f"already present in April ({H['month']['2026-04']['msa']} files) and May ({H['month']['2026-05']['msa']})", ("paper",)),
        ("1 August", H["aug1_main"], f"the {H['aug1_main'][0]} main files uploaded on 1 August ({H['aug1_main'][1]} marked)", ("paper",)),
        ("signer OpenAI", H["signer"]["OpenAI"], "| OpenAI | 403 | 327 | 76 | 317 |", ("paper",)),
        ("signer Microsoft", H["signer"]["Microsoft"], "| Microsoft | 44 | 25 | 19 | 0 |", ("paper",)),
        ("signer xAI", H["signer"]["xAI (self-signed)"], "| xAI (self-signed) | 2 | 2 | 0 | 0 |", ("paper",)),
    ]
    for name, per, col in (("2024", "2024", 0), ("2025", "2025", 0), ("2026 Jan–May", "janmay", 0), ("2026 Jun–Jul", "junjul", 0), ("2026 Aug–Sep", "post", 0)):
        a = m(any_, per)
        checks.append((f"table 4.1 {name}", a, f"| {name} | {a[4]} | {f1(a[0])}% ({f1(a[1])}–{f1(a[2])}) | {f1(m('C2PA declaring AI (any validity)', per)[0])}% | "
                       f"{f1(m('C2PA declaring AI, valid (ai-mark-lint 0.1.1)', per)[0])}% | {f1(m('C2PA declaring AI, trusted (official list + EKU)', per)[0])}% |", ("paper",)))
    for mo, v in H["month"].items():
        name = ["January", "February", "March", "April", "May", "June", "July", "August", "September"][int(mo[-2:]) - 1]
        checks.append((f"month {mo}", v["pct"], f"| {name} | {f1(v['pct'])}% ({v['n']}) | {f1(v['excl_coa_pct'])}% |", ("paper",)))
    if "paper" not in DOCS:
        print("paper.md is not in the public package: the paper is at https://easybyte.es/lab/studies/s6/paper/")
    checks = [(label, val, text, tuple(d for d in docs if d in DOCS)) for label, val, text, docs in checks]
    checks = [c for c in checks if c[3]]
    bad = 0
    for label, val, text, docs in checks:
        missing = [d for d in docs if text not in DOCS[d]]
        status = "ok  " if not missing else "FAIL"
        bad += bool(missing)
        print(f"{status} {label}: {val}" + (f"  -> not found in {missing}: {text!r}" if missing else ""))
    print(f"\n{len(checks) - bad}/{len(checks)} headline checks pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
