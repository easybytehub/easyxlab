"""Publisher identity (Integrity API) for attested PyPI projects.
For each project: first and last attested versions; if their publisher differs, bisect the attested
versions to locate each change. Only publisher fields are kept (kind, repository/project, workflow,
environment); certificates, claims and any actor field are dropped."""
import concurrent.futures as cf, csv, json, os
from common import http_get, cache_read, cache_write, DATA, norm
from pypi_versions import versions
from datetime import datetime, timezone
SNAP = datetime(2026, 10, 1, 12, 40, tzinfo=timezone.utc)

ACCEPT = "application/vnd.pypi.integrity.v1+json"
KEEP = ("kind", "repository", "workflow", "workflow_filepath", "environment", "project", "organization")
import csv as _csv
top = [{"project": r["project"]} for r in _csv.DictReader(open(os.path.join(DATA, "compact", "projects.csv")))]


def pick(r):
    pf = sorted(r.get("pf", []))
    sd = [f for f in pf if f.endswith(".tar.gz")]
    return (sd or pf)[0]


def publisher(project, r):
    fn = pick(r); key = f"{project}/{r['vs']}/{fn}"
    c = cache_read("integrity", key)
    if c is None:
        st, body, _ = http_get(f"https://pypi.org/integrity/{project}/{r['vs']}/{fn}/provenance", ACCEPT)
        c = {"status": st, "publishers": []}
        if body:
            for b in json.loads(body).get("attestation_bundles", []):
                pub = {k: v for k, v in (b.get("publisher") or {}).items() if k in KEEP}
                if pub.get("kind") == "Google" and "email" in (b.get("publisher") or {}):
                    pub["email_domain"] = b["publisher"]["email"].split("@")[-1]
                c["publishers"].append(pub)
        cache_write("integrity", key, c)
    pubs = c["publishers"]
    return pubs[0] if pubs else {"kind": f"ERR{c['status']}"}


def ident(p):
    return (p.get("kind"), (p.get("repository") or p.get("project") or p.get("email_domain") or "").lower(),
            p.get("workflow") or p.get("workflow_filepath") or "")


def scan(project):
    st, vs = versions(project)
    A = sorted([r for r in vs if r["att"]], key=lambda r: (r["t_att"], r["v"]))  # ordered by attested-file time
    if not A:
        return None
    memo = {}
    def P(i):
        if i not in memo:
            memo[i] = publisher(project, A[i])
        return memo[i]
    trans = []
    def bis(i, j):
        if ident(P(i)) == ident(P(j)):
            return
        if j == i + 1:
            trans.append((i, j)); return
        m = (i + j) // 2
        bis(i, m); bis(m, j)
    bis(0, len(A) - 1)
    first, last = P(0), P(len(A) - 1)
    out = {"project": project, "n_attested": len(A), "n_checked": len(memo),
           "first_version": A[0]["vs"], "first_kind": first.get("kind"), "first_repo": first.get("repository") or first.get("project") or first.get("email_domain"),
           "first_workflow": first.get("workflow") or first.get("workflow_filepath"), "first_env": first.get("environment"),
           "last_version": A[-1]["vs"], "last_kind": last.get("kind"), "last_repo": last.get("repository") or last.get("project") or last.get("email_domain"),
           "last_workflow": last.get("workflow") or last.get("workflow_filepath"), "last_env": last.get("environment"),
           "transitions": json.dumps([{"from_version": A[i]["vs"], "to_version": A[j]["vs"], "date": A[j]["t_att"].date().isoformat(),
                                        "from": "|".join(map(str, ident(P(i)))), "to": "|".join(map(str, ident(P(j))))} for i, j in trans])}
    ki = [ident(P(i)) for i, _ in trans] + [ident(P(j)) for _, j in trans]
    out["n_transitions"] = len(trans)
    out["changed_kind"] = any(ident(P(i))[0] != ident(P(j))[0] for i, j in trans)
    out["changed_repo"] = any(ident(P(i))[1] != ident(P(j))[1] for i, j in trans)
    out["changed_workflow_only"] = bool(trans) and not out["changed_repo"] and not out["changed_kind"]
    out["env_differs_first_last"] = (first.get("environment") or "") != (last.get("environment") or "")
    return out


if __name__ == "__main__":
    projects = [norm(r["project"]) for r in top]
    rank = {p: i + 1 for i, p in enumerate(projects)}
    res = []
    with cf.ThreadPoolExecutor(16) as ex:
        for r in ex.map(scan, projects):
            if r:
                r["rank"] = rank[r["project"]]; res.append(r)
    res.sort(key=lambda r: r["rank"])
    fields = ["rank", "project", "n_attested", "n_checked", "first_version", "first_kind", "first_repo", "first_workflow", "first_env",
              "last_version", "last_kind", "last_repo", "last_workflow", "last_env", "n_transitions", "changed_kind", "changed_repo",
              "changed_workflow_only", "env_differs_first_last", "transitions"]
    with open(os.path.join(DATA, "pypi_publishers.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fields); w.writeheader(); [w.writerow(r) for r in res]
    print("attested projects:", len(res), "(changes are lower bounds: bisection misses A->B->A inside an interval)", "with transitions:", sum(r["n_transitions"] > 0 for r in res),
          "repo changes:", sum(r["changed_repo"] for r in res), "workflow-only:", sum(r["changed_workflow_only"] for r in res),
          "kind changes:", sum(r["changed_kind"] for r in res), "calls:", sum(r["n_checked"] for r in res))
