"""Recompute every headline number from data/ and assert that README.md and paper.md state it.
Exit 1 on any mismatch."""
import csv, json, os, re, sys
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
D = lambda f: os.path.join(ROOT, "data", f)
pct = lambda y, n: f"{(Decimal(y) * 100 / Decimal(n)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"
m = json.load(open(D("metrics.json"))); pa = m["pypi"]; na = m["npm"]
reg = list(csv.DictReader(open(D("pypi_regressions.csv")))); rev = {r["project"]: r for r in csv.DictReader(open(D("pypi_regressions_reviewed.csv")))}
for r in reg: r["rc"] = rev.get(r["project"], {}).get("reviewed_class") or r["rule_class"]
pip = [r for r in reg if r["stopped_pip_default"] == "True"]
cls = Counter(r["rc"] for r in pip)
tool = [r for r in pip if r["rc"] == "tool_or_workflow_change"]
uv = sum(1 for r in tool if "uv publish" in r["workflow_markers"] and r["workflow_at_head"] == "non_attesting_tool")
wf = Counter(r["workflow_at_head"] for r in tool)
override = sum(1 for r in tool if r["rule_class"] != "tool_or_workflow_change")
other = wf["non_attesting_tool"] - uv
unk = Counter(r["workflow_at_head"] for r in pip if r["rc"] == "indeterminate")
mon = {r["month"]: r for r in csv.DictReader(open(D("pypi_monthly.csv")))}
la, ev, el = pa["latest_attested_all"], pa["ever_attested_all"], pa["latest_attested_eligible"]
never = ev["n"] - ev["yes"]
ph = pa["stopped_newest"]; pp = pa["stopped_pip_default"]
pub = m["pypi_publishers"]; rules = pub["rules"]
both = [f"{la['yes']:,} of {la['n']:,}", f"({pct(la['yes'], la['n'])})", f"{never:,}", f"({pct(never, ev['n'])})", pct(el["yes"], el["n"]),
        pct(pa["bands"][0]["latest_attested"]["yes"], pa["bands"][0]["latest_attested"]["n"]),
        pct(pa["bands"][-1]["latest_attested"]["yes"], pa["bands"][-1]["latest_attested"]["n"]),
        pct(int(mon["2024-11"]["projects_latest_attested"]), int(mon["2024-11"]["projects_existing"])),
        pct(int(mon["2026-09"]["projects_latest_attested"]), int(mon["2026-09"]["projects_existing"])),
        f"{ph} projects", f"For {pp},", f"{pct(pp, ev['yes'])} of the {ev['yes']:,} projects",
        f"| tool or workflow change | {cls['tool_or_workflow_change']} |", f"| {cls['isolated_upload']} |", f"| {cls['restored_at_head']} |", f"| unknown | {cls['indeterminate']} |",
        f"At least {pub['projects_with_change_at_least']}", f"{pub['cross_repo_or_kind']} changes", f"{pub['cross_confirmed']}", f"{pub['cross_metadata']}",
        f"{rules.get('not confirmed by public data', 0)}, in {len(pub['projects_not_confirmed'])} projects",
        pct(na["latest_attested_top1000"]["yes"], na["latest_attested_top1000"]["n"]), f"{na['regression']} of {na['attested_packages']}", f"({pct(na['regression'], na['attested_packages'])})",
        f"{sum(m['tob_comparison']['matrix'].get(k, 0) for k in ('success|attested', 'warning|not', 'default|not', 'unsupported|not'))} of its {m['tob_comparison']['tob_total']}"]
paper_only = [f"{uv} publishing workflows now run `uv publish`", f"{uv} workflows at `HEAD` run `uv publish`", f"{wf['missing']} attesting workflows were deleted",
              f"{wf['attestations_disabled']} set `attestations: false`", f"{wf['token_auth']} authenticate with an API token", f"{other} use other uploaders",
              f"{override} are agent overrides", f"{unk['repo_unreadable']} have publishing repositories that are not publicly readable",
              f"{unk['upload_step_not_recognised']} have upload steps our patterns do not recognise",
              f"{pa['stopped_pip_default_single_attested_stable']} of the {pp} had only one attested stable release", f"A median of {m['pypi_stopped']['median_unattested_after']} unattested",
              ", ".join(str(h["stops"]) for h in m["pypi_stopped"]["stops_by_half"][:3]) + f" and {m['pypi_stopped']['stops_by_half'][3]['stops']}",
              ", ".join(f"{h['rate_pct']}%" for h in m["pypi_stopped"]["stops_by_half"][:3]) + f" and {m['pypi_stopped']['stops_by_half'][3]['rate_pct']}%",
              f"In {pa['mixed_latest']} projects only part", f"GitHub for {pub['kinds_last']['GitHub']:,} projects, Google for {pub['kinds_last']['Google']} and",
              f"{pub['changes_at_least']} changes in all; {pub['environment_only_projects']} other projects", f"**{pub['change_types']['workflow_changed_same_repo']} changes**",
              f"{rules.get('confirmed: same owner', 0)} keep the same owner and {rules.get('confirmed: same repository after GitHub redirects', 0)} resolve",
              f"{m['review_sample']['n']} of the 57 are still in the set", f"agree with the rules in {m['review_sample']['agree_with_rule']}",
              f"({el['yes']:,} of {el['n']:,})",
              f"{cls['tool_or_workflow_change']} of the {pp} stops coincide with a change of release tooling and {cls['indeterminate']} have no known cause"]
for b in pa["bands"]:
    a, z = b["band"].split("-")
    paper_only.append(f"| {int(a):,}–{int(z):,} | {pct(b['latest_attested']['yes'], b['latest_attested']['n'])} | {pct(b['eligible_latest_attested']['yes'], b['eligible_latest_attested']['n'])} | {pct(b['ever_attested']['yes'], b['ever_attested']['n'])} |")
for mo in ("2024-11", "2025-06", "2025-12", "2026-06", "2026-09"):
    r = mon[mo]
    paper_only.append(f"| {mo} | {int(r['versions']):,} | {pct(int(r['versions_attested']), int(r['versions']))} | {pct(int(r['projects_releasing_with_attestation']), int(r['projects_releasing']))} | {pct(int(r['projects_latest_attested']), int(r['projects_existing']))} |")
pyb = {b["band"]: b for b in pa["bands"]}
for b in na["bands"][:3]:
    a, z = b["band"].split("-"); py = pyb[b["band"]]["latest_attested"]
    paper_only.append(f"| {int(a):,}–{int(z):,} | {pct(b['latest_attested']['yes'], b['latest_attested']['n'])} | {pct(py['yes'], py['n'])} |")
docs = [f for f in ("README.md", "paper.md") if os.path.exists(os.path.join(ROOT, f))]
if "paper.md" not in docs:  # the public package on GitHub ships without the paper
    print("paper.md is not in the public package: the paper is at https://easybyte.es/lab/studies/s5/paper/")
    paper_only = []
txt = {f: re.sub(r"\s+", " ", open(os.path.join(ROOT, f)).read()) for f in docs}
bad = [(f, s) for s in both for f in txt if s not in txt[f]] + [("paper.md", s) for s in paper_only if s not in txt["paper.md"]]
for f, s in bad:
    print("MISSING in", f, ":", s)
print(f"headline check: {len(both) * len(txt) + len(paper_only) - len(bad)} passed, {len(bad)} failed")
sys.exit(1 if bad else 0)
