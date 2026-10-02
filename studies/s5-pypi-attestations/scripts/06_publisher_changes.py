"""Publisher changes between attested versions, checked against public data.
Rules, first match wins: (1) same repository (workflow file changed); (2) same owner; (3) old and new
repository resolve to the same GitHub repository today (rename/transfer, chained moves included);
(4) the new repository - directly or after GitHub redirects - is the one declared in the project_urls/
home_page of the last attested version: 'consistent with the project's own metadata' (self-declared, so
not independent confirmation); otherwise 'not confirmed by public data'."""
import csv, importlib.util, json, os, re
from common import http_get, cache_read, cache_write, DATA
spec = importlib.util.spec_from_file_location("s05", os.path.join(os.path.dirname(__file__), "05_regressions.py")); s05 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s05)
gh_final = s05.gh_final


def declared(project, version):
    c = cache_read("pypi_json", f"{project}@{version}")
    if c is None:
        st, body, _ = http_get(f"https://pypi.org/pypi/{project}/{version}/json")
        info = json.loads(body)["info"] if body else {}
        c = {"status": st, "urls": list((info.get("project_urls") or {}).values()) + [info.get("home_page") or ""]}
        cache_write("pypi_json", f"{project}@{version}", c)
    slugs = set()
    for u in c["urls"]:
        m = re.match(r"https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+)", u or "")
        if m:
            slugs.add(f"{m.group(1)}/{re.sub(r'\.git$', '', m.group(2))}".lower())
    return slugs


if __name__ == "__main__":
    rows = [r for r in csv.DictReader(open(os.path.join(DATA, "pypi_publishers.csv"))) if int(r["n_transitions"]) > 0]
    out = []
    for r in rows:
        for t in json.loads(r["transitions"]):
            fk, frepo, fwf = t["from"].split("|"); tk, trepo, twf = t["to"].split("|")
            gh = fk == "GitHub" and tk == "GitHub"
            if fk == tk and frepo == trepo:
                kind, rule = "workflow_changed_same_repo", "confirmed: same repository"
            else:
                kind = "repository_changed" if fk == tk else "publisher_kind_changed"
                fr, tr = (gh_final(frepo) if fk == "GitHub" else None), (gh_final(trepo) if tk == "GitHub" else None)
                decl = declared(r["project"], r["last_version"])
                if fk == tk and frepo.split("/")[0] == trepo.split("/")[0]:
                    rule = "confirmed: same owner"
                elif gh and fr and fr == tr:
                    rule = "confirmed: same repository after GitHub redirects"
                elif trepo in decl or (tr and tr in {gh_final(s) for s in decl}):
                    rule = "consistent with the project's own metadata"
                else:
                    rule = "not confirmed by public data"
            out.append({"rank": r["rank"], "project": r["project"], "from_version": t["from_version"], "to_version": t["to_version"],
                        "date": t["date"], "from": t["from"], "to": t["to"], "change": kind, "rule": rule})
    with open(os.path.join(DATA, "pypi_publisher_changes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(out[0])); w.writeheader(); [w.writerow(x) for x in out]
    from collections import Counter
    print(len(out), Counter(x["change"] for x in out), Counter(x["rule"] for x in out))
    print(sorted({x["project"] for x in out if x["rule"].startswith("not confirmed")}))
