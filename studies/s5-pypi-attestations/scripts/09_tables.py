"""Merge aggregates and the agent review into data/metrics.json and data/tables.md.
Percentages are computed once, from integer counts, rounded half-up to one decimal (no double rounding)."""
import csv, json, os
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from common import DATA, RAW, norm

def pct(yes, n):
    return float((Decimal(yes) * 100 / Decimal(n)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) if n else None
fmt = lambda d: f"{d['yes']:,}/{d['n']:,} ({pct(d['yes'], d['n'])}%)" if d and d.get("n") else "–"
L = lambda f: list(csv.DictReader(open(os.path.join(DATA, f)))) if os.path.exists(os.path.join(DATA, f)) else []
pa = json.load(open(os.path.join(DATA, "pypi_aggregates.json")))
na = json.load(open(os.path.join(DATA, "npm_aggregates.json")))
old = json.load(open(os.path.join(DATA, "metrics.json"))) if os.path.exists(os.path.join(DATA, "metrics.json")) else {}
pk = {r["project"]: r for r in L("pypi_packages.csv")}
reg = L("pypi_regressions.csv"); rev = {r["project"]: r for r in L("pypi_regressions_reviewed.csv")}
pch = L("pypi_publisher_changes.csv"); pub = L("pypi_publishers.csv"); prev = {r["project"]: r for r in L("pypi_publisher_changes_reviewed.csv")}
npm = L("npm_packages.csv"); nrev = {r["package"]: r for r in L("npm_regressions_reviewed.csv")}
mon = L("pypi_monthly.csv")

# Trail of Bits comparison: only recomputed when the (non-redistributed) snapshot is present locally
tobf = os.path.join(RAW, "src", "tob_results_2026-10-02.json")
if os.path.exists(tobf):
    tob = json.load(open(tobf)); cmp = Counter()
    for p in tob["data"]:
        r = pk.get(norm(p["name"]))
        ours = "n/a" if not r or not r.get("latest_version") else ("attested" if r["latest_attested"] == "True" else "not")
        cmp[(p["css_class"], ours)] += 1
    tobm = {"tob_last_update": tob["last_update"], "tob_total": len(tob["data"]), "tob_green": sum(p["css_class"] == "success" for p in tob["data"]),
            "matrix": {f"{a}|{b}": n for (a, b), n in sorted(cmp.items())},
            "disagreements": sorted(p["name"] for p in tob["data"] if (p["css_class"] == "success") != (pk.get(norm(p["name"]), {}).get("latest_attested") == "True"))}
else:
    tobm = old.get("tob_comparison", {})

for r in reg:
    v = rev.get(r["project"], {})
    r["reviewed_class"] = v.get("reviewed_class") or r["rule_class"]
    r["review_note"] = v.get("review_note", "")
pip = [r for r in reg if r["stopped_pip_default"] == "True"]
ever = pa["ever_attested_all"]["yes"]
m = {"pypi": pa, "npm": na, "tob_comparison": tobm,
     "headline": {
         "latest_attested": pa["latest_attested_all"], "latest_attested_pct": pct(pa["latest_attested_all"]["yes"], pa["latest_attested_all"]["n"]),
         "latest_not_attested": pa["latest_attested_all"]["n"] - pa["latest_attested_all"]["yes"],
         "never_attested": pa["ever_attested_all"]["n"] - ever, "never_attested_pct": pct(pa["ever_attested_all"]["n"] - ever, pa["ever_attested_all"]["n"]),
         "eligible_pct": pct(pa["latest_attested_eligible"]["yes"], pa["latest_attested_eligible"]["n"]),
         "ever_attested": ever, "ever_attested_pct": pct(ever, pa["ever_attested_all"]["n"]),
         "stopped_newest": pa["stopped_newest"], "stopped_pip_default": pa["stopped_pip_default"],
         "stopped_pip_default_pct_of_ever": pct(pa["stopped_pip_default"], ever),
         "bands_latest_pct": {b["band"]: pct(b["latest_attested"]["yes"], b["latest_attested"]["n"]) for b in pa["bands"]},
         "state_share_first_last": [(mon[1]["month"], pct(int(mon[1]["projects_latest_attested"]), int(mon[1]["projects_existing"]))),
                                    (mon[-1]["month"], pct(int(mon[-1]["projects_latest_attested"]), int(mon[-1]["projects_existing"])))],
         "npm_latest_top1000_pct": pct(na["latest_attested_top1000"]["yes"], na["latest_attested_top1000"]["n"]),
         "npm_regression": na["regression"], "npm_attested_packages": na["attested_packages"],
         "npm_regression_pct_of_ever": pct(na["regression"], na["attested_packages"])},
     "pypi_stopped": {"classified": len(reg), "pip_default": len(pip),
                      "pip_default_rule_classes": Counter(r["rule_class"] for r in pip), "pip_default_reviewed_classes": Counter(r["reviewed_class"] for r in pip),
                      "pip_default_workflow_at_head": Counter(r["workflow_at_head"] for r in pip if r["reviewed_class"] == "tool_or_workflow_change"),
                      "pip_default_uv_publish": sum(1 for r in pip if r["reviewed_class"] == "tool_or_workflow_change" and "uv publish" in r["workflow_markers"]),
                      "broad_only_classes": Counter(r["reviewed_class"] for r in reg if r["stopped_pip_default"] != "True"),
                      "stops_by_half": [dict(h, rate_pct=pct(h["stops"], h["projects_with_attested_stable_by_end"])) for h in pa["stops_by_half"]],
                      "median_unattested_after": sorted(int(r["n_unattested_after_last_attested"]) for r in pip)[len(pip) // 2] if pip else None},
     "review_sample": {"n": len(rev), "in_pip_default": sum(1 for r in pip if r["project"] in rev),
                       "agree_with_rule": sum(1 for r in reg if r["project"] in rev and r["rule_class"] == rev[r["project"]]["reviewed_class"])},
     "pypi_publishers": {"attested_projects": len(pub), "kinds_last": Counter(r["last_kind"] for r in pub),
                         "projects_with_change_at_least": sum(int(r["n_transitions"]) > 0 for r in pub), "changes_at_least": len(pch),
                         "change_types": Counter(r["change"] for r in pch), "rules": Counter(r["rule"] for r in pch),
                         "cross_repo_or_kind": sum(r["change"] != "workflow_changed_same_repo" for r in pch),
                         "cross_confirmed": sum(r["change"] != "workflow_changed_same_repo" and r["rule"].startswith("confirmed") for r in pch),
                         "cross_metadata": sum(r["rule"].startswith("consistent") for r in pch),
                         "projects_not_confirmed": sorted({r["project"] for r in pch if r["rule"].startswith("not confirmed")}),
                         "environment_only_projects": sum(1 for r in pub if r["env_differs_first_last"] == "True" and r["n_transitions"] == "0"),
                         "integrity_requests": sum(int(r["n_checked"]) for r in pub)}}
json.dump(m, open(os.path.join(DATA, "metrics.json"), "w"), indent=1)

T = ["## T1. PyPI: latest version attested, by popularity band", "", "| rank band | latest attested | eligible¹ latest attested | ever attested | stopped (pip-default) |", "|---|---|---|---|---|"]
for b in pa["bands"]:
    T.append(f"| {b['band']} | {fmt(b['latest_attested'])} | {fmt(b['eligible_latest_attested'])} | {fmt(b['ever_attested'])} | {b['stopped_pip_default']['yes']} |")
T.append(f"| **all** | {fmt(pa['latest_attested_all'])} | {fmt(pa['latest_attested_eligible'])} | {fmt(pa['ever_attested_all'])} | {pa['stopped_pip_default']} |")
T += ["", "¹ latest (highest stable) version first uploaded on or after 2024-10-01.", ""]
T += ["## T2. PyPI: monthly series (projects in the 2026-10-01 top-15,000)", "", "| month | versions | versions attested | projects releasing that attested | projects whose latest is attested |", "|---|---|---|---|---|"]
for r in mon:
    T.append(f"| {r['month']} | {int(r['versions']):,} | {pct(int(r['versions_attested']), int(r['versions']))}% | {pct(int(r['projects_releasing_with_attestation']), int(r['projects_releasing']))}% | {pct(int(r['projects_latest_attested']), int(r['projects_existing']))}% |")
T += ["", "## T3. PyPI projects that stopped attesting", "", "| rank | project | pip-default | last attested (date) | latest | unattested since | workflow at HEAD | rule class | reviewed class | evidence / note |", "|---|---|---|---|---|---|---|---|---|---|"]
for r in reg:
    T.append(f"| {r['rank']} | {r['project']} | {'yes' if r['stopped_pip_default'] == 'True' else 'no'} | {r['last_attested_mainline_version'] or r['last_attested_version']} ({r['last_attested_mainline_date'] or r['last_attested_date']}) | {r['latest_version']} | {r['n_unattested_after_last_attested']} | {r['workflow_at_head']} | {r['rule_class']} | {r['reviewed_class']} | {(r['review_note'] or r['rule_reason']).replace('|', '/')} |")
T += ["", "## T4. PyPI publisher changes between attested versions (lower bounds)", "", "| change | rule | n |", "|---|---|---|"]
for (a, b), n in sorted(Counter((r["change"], r["rule"]) for r in pch).items(), key=lambda x: -x[1]):
    T.append(f"| {a} | {b} | {n} |")
T += ["", "## T5. npm sample vs PyPI by rank band", "", "| rank band | npm latest with provenance | PyPI latest attested (same band) |", "|---|---|---|"]
pyb = {b["band"]: b for b in pa["bands"]}
for b in na["bands"]:
    py = pyb.get(b["band"]); T.append(f"| {b['band']} | {fmt(b['latest_attested'])} | {fmt(py['latest_attested']) if py else '(PyPI list has 15,000)'} |")
T += ["", "### npm: SemVer candidates", "", "| rank | package | latest (date) | last attested (date) | confirmed by time | rule class | reviewed class | note |", "|---|---|---|---|---|---|---|---|"]
for r in npm:
    if r.get("regression_semver") == "True":
        v = nrev.get(r["package"], {})
        T.append(f"| {r['rank']} | {r['package']} | {r['latest_version']} ({r['latest_date']}) | {r['last_attested_by_time']} ({r['last_attested_date']}) | {r['regression_time_confirmed']} | {r['rule_class']} | {v.get('reviewed_class', r['rule_class'])} | {v.get('review_note', '')} |")
if tobm:
    T += ["", "## T6. Comparison with Trail of Bits, *Are we PEP 740 yet?*", "", f"ToB `last_update`: {tobm.get('tob_last_update')}; green: {tobm.get('tob_green')}/{tobm.get('tob_total')}; disagreements: {', '.join(tobm.get('disagreements', [])) or 'none'}.", ""]
open(os.path.join(DATA, "tables.md"), "w").write("# S5 tables (generated by scripts/09_tables.py)\n\n" + "\n".join(T) + "\n")
print(json.dumps({k: m[k] for k in ("headline", "pypi_stopped", "review_sample", "pypi_publishers")}, indent=1, default=str))
