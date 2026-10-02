"""npm comparison: latest-version provenance by rank band, regressions (semver order, confirmed with
publish times), cause rules, and source-repository changes between first and latest attested versions."""
import csv, importlib.util, json, os, re
from collections import Counter
from common import DATA, cache_read, OFFLINE
PRIOR = {r["package"]: r for r in csv.DictReader(open(os.path.join(DATA, "npm_packages.csv")))} if os.path.exists(os.path.join(DATA, "npm_packages.csv")) else {}
spec = importlib.util.spec_from_file_location("s07", os.path.join(os.path.dirname(__file__), "07_npm.py")); s07 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s07)
spec = importlib.util.spec_from_file_location("s05", os.path.join(os.path.dirname(__file__), "05_regressions.py")); s05 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s05)
spec = importlib.util.spec_from_file_location("s06", os.path.join(os.path.dirname(__file__), "06_publisher_changes.py")); s06 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s06)
skey = s07.skey
BANDS = [(1, 100), (101, 500), (501, 1000), (1001, 15916)]
PROV_MARK = {"--provenance": r"--provenance\b", "NPM_CONFIG_PROVENANCE": r"NPM_CONFIG_PROVENANCE", "provenance: true": r"provenance:\s*true",
             "id-token:write": r"id-token:\s*write", "NODE_AUTH_TOKEN/NPM_TOKEN": r"NODE_AUTH_TOKEN|NPM_TOKEN", "changesets/action": r"changesets/action",
             "semantic-release": r"semantic-release", "npm publish": r"\bnpm\s+publish\b", "pnpm publish": r"\bpnpm\s+(-r\s+)?publish\b",
             "yarn npm publish": r"\byarn\s+npm\s+publish\b", "lerna publish": r"\blerna\s+publish\b"}


def nrepo(u):
    u = (u or "").lower().replace("git+", "")
    u = re.sub(r"\.git$", "", u)
    return re.sub(r"^https?://github\.com/", "", u)


sample = s07.load_list()
rows = []
for rank, n in sample:
    d = cache_read("npm_corgi", n) or {}
    vs = d.get("versions") or {}
    lt = (d.get("dist_tags") or {}).get("latest")
    rec = {"rank": rank, "package": n, "status": d.get("status"), "n_versions": len(vs), "latest_version": lt}
    if not vs or lt not in vs or not skey(lt):
        rows.append(rec); continue
    ordered = sorted([v for v in vs if skey(v)], key=skey)
    att = [v for v in ordered if vs[v]["prov"]]
    rec.update(latest_attested=vs[lt]["prov"], ever_attested=bool(att), n_attested_versions=len(att),
               first_attested_version=att[0] if att else "", last_attested_version=att[-1] if att else "")
    below = [v for v in att if skey(v) < skey(lt)]
    rec["regression_semver"] = bool(below) and not vs[lt]["prov"]
    higher_pre = [v for v in ordered if skey(v) > skey(lt)]
    rec["secondary_channel_unattested"] = vs[lt]["prov"] and any(not vs[v]["prov"] for v in higher_pre[-3:])
    if rec["regression_semver"]:
        tm = s07.times(n)["time"]
        lat_t = tm.get(lt, "")
        att_t = [(tm.get(v, ""), v) for v in att]
        last_att = max(att_t)
        rec["regression_time_confirmed"] = last_att[0] < lat_t
        rec["regression"] = rec["regression_time_confirmed"]
        rec["last_attested_by_time"] = last_att[1]; rec["last_attested_date"] = last_att[0][:10]; rec["latest_date"] = lat_t[:10]
        after = [v for v in vs if tm.get(v, "") > last_att[0] and v in vs]
        rec["n_after_last_attested"] = len(after)
        rec["n_after_prerelease"] = sum(1 for v in after if skey(v) and skey(v)[3] != (1,))
        pv = s07.provenance(n, last_att[1])
        repo = nrepo(pv.get("repo")); path = pv.get("path") or ""
        rec["publisher"] = f"{repo}:{path}"
        prior = PRIOR.get(n, {})
        if repo and "/" in repo and path and OFFLINE and prior.get("workflow_at_head"):
            rec["workflow_at_head"] = prior["workflow_at_head"]; rec["workflow_markers"] = prior.get("workflow_markers", "")
            rec["workflow_commits_since"] = prior.get("workflow_commits_since", "")
        elif repo and "/" in repo and path:
            st = s05.raw(repo, "HEAD", path)
            if st["status"] != 200:
                rec["workflow_at_head"] = "missing" if st["status"] == 404 else "fetch_error"; marks = []
            else:
                rec["workflow_at_head"] = "present"
                marks = [k for k, rx in PROV_MARK.items() if re.search(rx, st["text"])]
            rec["workflow_markers"] = " ".join(marks)
            rec["workflow_commits_since"] = " || ".join(f"{c['date']} {c['title']}" for c in s05.atom(repo, path, rec["last_attested_date"])[:6])
        else:
            rec["workflow_at_head"] = "na"
        n_after = rec["n_after_last_attested"]
        if not rec["regression_time_confirmed"]:
            rec["rule_class"] = "not_regression_attested_line_published_later"
        elif rec["workflow_at_head"] == "missing":
            rec["rule_class"] = "tool_or_workflow_change"
        elif rec["workflow_at_head"] == "present" and n_after == 1:
            rec["rule_class"] = "isolated_upload"
        else:
            rec["rule_class"] = "indeterminate"
    if att:
        a, b = s07.provenance(n, att[0]), s07.provenance(n, att[-1])
        rec["first_publisher"] = f"{nrepo(a.get('repo'))}:{a.get('path')}"; rec["last_publisher"] = f"{nrepo(b.get('repo'))}:{b.get('path')}"
        rec["repo_changed"] = nrepo(a.get("repo")) != nrepo(b.get("repo")) and bool(a.get("repo")) and bool(b.get("repo"))
        rec["workflow_changed_same_repo"] = not rec["repo_changed"] and (a.get("path") or "") != (b.get("path") or "")
        if rec["repo_changed"]:
            fr, tr = nrepo(a.get("repo")), nrepo(b.get("repo"))
            rec["repo_change_rule"] = ("same owner" if fr.split("/")[0] == tr.split("/")[0] else
                                       "old repository redirects to new (rename/transfer)" if s06.gh_final(fr) == tr else
                                       "not verifiable from public metadata")
    rows.append(rec)

fields = ["rank", "package", "status", "n_versions", "latest_version", "latest_attested", "ever_attested", "n_attested_versions", "first_attested_version",
          "last_attested_version", "regression_semver", "regression_time_confirmed", "last_attested_by_time", "last_attested_date", "latest_date",
          "n_after_last_attested", "n_after_prerelease", "secondary_channel_unattested", "publisher", "workflow_at_head", "workflow_markers",
          "workflow_commits_since", "rule_class", "first_publisher", "last_publisher", "repo_changed", "repo_change_rule", "workflow_changed_same_repo", "regression"]
with open(os.path.join(DATA, "npm_packages.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fields, extrasaction="ignore"); w.writeheader(); [w.writerow(r) for r in rows]
ok = [r for r in rows if "latest_attested" in r]
def share(L, k):
    a = sum(1 for r in L if r.get(k)); return {"n": len(L), "yes": a, "share": round(a / len(L), 4) if L else None}
agg = {"sample": "npm-high-impact 1.13.0 top-download: ranks 1-1000 + 500 random from 1001-15916 (seed 20261002)", "n": len(ok),
       "latest_attested_top1000": share([r for r in ok if r["rank"] <= 1000], "latest_attested"),
       "latest_attested_tail_sample": share([r for r in ok if r["rank"] > 1000], "latest_attested"),
       "ever_attested_top1000": share([r for r in ok if r["rank"] <= 1000], "ever_attested"),
       "bands": [{"band": f"{a}-{b}", "latest_attested": share([r for r in ok if a <= r["rank"] <= b], "latest_attested"),
                  "ever_attested": share([r for r in ok if a <= r["rank"] <= b], "ever_attested"),
                  "regression": share([r for r in ok if a <= r["rank"] <= b], "regression")} for a, b in BANDS],
       "regression_semver": sum(1 for r in ok if r.get("regression_semver")),
       "regression_time_confirmed": sum(1 for r in ok if r.get("regression_time_confirmed")),
       "regression": sum(1 for r in ok if r.get("regression")),
       "repo_change_rules": Counter(r["repo_change_rule"] for r in ok if r.get("repo_change_rule")),
       "rule_classes": Counter(r["rule_class"] for r in ok if r.get("rule_class")),
       "secondary_channel_unattested": sum(1 for r in ok if r.get("secondary_channel_unattested")),
       "repo_changed": sum(1 for r in ok if r.get("repo_changed")), "workflow_changed_same_repo": sum(1 for r in ok if r.get("workflow_changed_same_repo")),
       "attested_packages": sum(1 for r in ok if r.get("ever_attested"))}
json.dump(agg, open(os.path.join(DATA, "npm_aggregates.json"), "w"), indent=1)
print(json.dumps(agg, indent=1))
