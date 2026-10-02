"""Classify projects that stopped attesting, with explicit rules.
Evidence: the version pattern, and the publishing workflow named by the last attestation, read at the
repository's HEAD (raw.githubusercontent.com), following reusable workflows, local composite actions,
`make <target>` (Makefile) and `python|uv run <script>.py`; plus every commit touching that workflow file
since the last attested release (GitHub Atom feed: date, commit id, title; author fields are not kept).
Offline (OFFLINE=1) the evidence columns of the published data/pypi_regressions.csv are reused."""
import csv, json, os, re
from common import http_get, cache_read, cache_write, DATA, OFFLINE, OfflineMiss
from pypi_versions import versions

PYPA = re.compile(r"uses:\s*['\"]?pypa/gh-action-pypi-publish@([^\s'\"]+)([^\n]*)")
OTHER = {"uv publish": r"\buv\s+publish\b|[\"']uv[\"']\s*,\s*[\"']publish[\"']", "twine upload": r"\btwine\s+upload\b", "poetry publish": r"\bpoetry\s+publish\b",
         "hatch publish": r"\bhatch\s+publish\b", "flit publish": r"\bflit\s+publish\b", "pdm publish": r"\bpdm\s+publish\b",
         "maturin upload": r"\bmaturin\s+(upload|publish)\b|command:\s*['\"]?(upload|publish)", "rye publish": r"\brye\s+publish\b"}
GENERATOR = {"astral-sh/attest-action": r"astral-sh/attest-action@", "pypi-attestations sign": r"pypi-attestations\s+sign", "actions/attest": r"\bactions/attest@"}
LOCAL_REUSE = re.compile(r"uses:\s*['\"]?\./(\.github/(?:workflows/[^\s'\"@]+|actions/[^\s'\"@]+))")
REMOTE_REUSE = re.compile(r"uses:\s*['\"]?([\w.-]+/[\w.-]+)/(\.github/workflows/[^\s'\"@]+)@([^\s'\"]+)")
MAKE = re.compile(r"\bmake\s+(?:-\S+\s+)*([A-Za-z][\w.-]*)")
SCRIPT = re.compile(r"\b(?:python3?|uv\s+run(?:\s+python3?)?)\s+((?:\./)?[\w./-]+\.py)\b")
SCRUB = re.compile(r"\b[Pp][Rr]\s*\d+/[^/\s]+/|@[A-Za-z0-9-]+")
PRIOR = {}
if os.path.exists(os.path.join(DATA, "pypi_regressions.csv")):
    PRIOR = {r["project"]: r for r in csv.DictReader(open(os.path.join(DATA, "pypi_regressions.csv")))}


def raw(repo, ref, path):
    key = f"{repo}@{ref}:{path}"
    c = cache_read("gh_raw", key)
    if c is None:
        st, body, _ = http_get(f"https://raw.githubusercontent.com/{repo}/{ref}/{path}", rate=4)
        c = {"status": st, "text": body.decode("utf-8", "replace") if body else None}
        cache_write("gh_raw", key, c)
    return c


def gh_final(repo):
    c = cache_read("gh_redirect", repo)
    if c is None:
        st, _, final = http_get(f"https://github.com/{repo}", rate=2, method="HEAD", timeout=30)
        c = {"status": st, "final": final}
        cache_write("gh_redirect", repo, c)
    m = re.match(r"https://github.com/([^/]+/[^/?#]+)", c["final"] or "")
    return m.group(1).lower() if m and c["status"] == 200 else None


def atom(repo, path, since):
    key = f"{repo}:{path}"
    c = cache_read("gh_atom2", key)
    if c is None:
        st, body, _ = http_get(f"https://github.com/{repo}/commits/HEAD/{path}.atom", rate=2)
        ents = []
        if body:
            for e in re.findall(r"(?s)<entry>(.*?)</entry>", body.decode("utf-8", "replace")):
                d = re.search(r"<updated>([^<]+)</updated>", e); ti = re.search(r"(?s)<title>\s*(.*?)\s*</title>", e)
                sha = re.search(r"/commit/([0-9a-f]{7,40})", e)
                if d and ti:
                    ents.append({"date": d.group(1)[:10], "sha": sha.group(1)[:12] if sha else "", "title": SCRUB.sub(" ", re.sub(r"\s+", " ", ti.group(1)))[:140]})
        c = {"status": st, "entries": ents}
        cache_write("gh_atom2", key, c)
    return [e for e in c["entries"] if e["date"] >= since and not e["title"].startswith("Merge pull request")]


def old_action(ref, comment):
    m = re.search(r"v1\.(\d+)", ref) or re.search(r"v1\.(\d+)", comment)
    return bool(m) and int(m.group(1)) < 11


def evidence(repo, wf):
    st = raw(repo, "HEAD", f".github/workflows/{wf}")
    if st["status"] != 200:
        if st["status"] != 404:
            return "fetch_error", []
        return ("missing" if gh_final(repo) else "repo_unreadable"), []
    texts, seen = [st["text"]], set()
    i = 0
    while i < len(texts) and i < 12:
        t = texts[i]; i += 1
        refs = [(repo, "HEAD", p) for p in LOCAL_REUSE.findall(t)] + [(r2, ref, p) for r2, p, ref in REMOTE_REUSE.findall(t)]
        refs += [(repo, "HEAD", p.rstrip("/") + "/action.yml") for _, _, p in refs if "/actions/" in p and not p.endswith((".yml", ".yaml"))]
        if MAKE.search("\n".join(l for l in t.splitlines() if "run:" in l or l.startswith((" ", "\t")))):
            refs.append((repo, "HEAD", "Makefile"))
        refs += [(repo, "HEAD", p.lstrip("./")) for p in SCRIPT.findall(t)]
        for r2, ref, p in refs:
            if (r2, p) in seen or p.endswith("/"):
                continue
            seen.add((r2, p))
            c = raw(r2, ref, p)
            if c["text"]:
                texts.append(c["text"])
    comments = [l.strip() for x in texts for l in x.splitlines() if l.lstrip().startswith("#") and "attest" in l.lower() and "uses:" not in l]
    t = "\n".join(l for x in texts for l in x.splitlines() if not l.lstrip().startswith("#"))
    marks = []
    pypa = PYPA.findall(t)
    if pypa: marks.append("pypa@" + ",".join(sorted({r for r, _ in pypa})))
    for k, rx in OTHER.items():
        if re.search(rx, t): marks.append(k)
    gen = [k for k, rx in GENERATOR.items() if re.search(rx, t)]
    marks += ["generator:" + g for g in gen]
    if re.search(r"attestations:\s*['\"]?false", t): marks.append("attestations:false")
    tok = bool(re.search(r"password:\s*\$\{\{", t)); idt = bool(re.search(r"id-token:\s*write", t))
    lines = t.splitlines()
    steps = [k for k, l in enumerate(lines) if "pypa/gh-action-pypi-publish@" in l]
    every_step_token = bool(steps) and all(any(re.search(r"password:\s*\$\{\{", x) for x in lines[k:k + 9]) for k in steps)
    if tok: marks.append("password-secret")
    if comments: marks.append("comment:" + comments[0][:90])
    if pypa:
        if "attestations:false" in marks: return "attestations_disabled", marks
        if all(old_action(r, c) for r, c in pypa): return "old_action", marks
        if (tok and not idt) or every_step_token: return "token_auth", marks
        return "attesting", marks
    if gen and any(k in marks for k in OTHER): return "attesting_generator", marks
    if any(k in marks for k in OTHER): return "non_attesting_tool", marks
    return "upload_step_not_recognised", marks


def classify(r, wf, commits):
    n = int(r["n_unattested_after_last_attested"])
    if r["stopped_pip_default"] != "True":
        if r["only_prereleases_attested"] == "True":
            return "prerelease_or_secondary_pipeline", "only pre-releases were ever attested"
        return "prerelease_or_secondary_pipeline", "the pip-default version is attested; the unattested newest upload is a " + ("pre-release" if r["newest_is_prerelease"] == "True" else "lower (maintenance) version")
    if r["n_attested_mainline"] == "0":
        return "prerelease_or_secondary_pipeline", "only maintenance-line (backport) releases were ever attested"
    # a commit that (re)adds PEP 740 attestations after the latest release; GitHub artifact attestations
    # (actions/attest-build-provenance) are a different mechanism and do not count
    restored = [c for c in commits if "attest" in c["title"].lower() and "attest-build-provenance" not in c["title"].lower() and c["date"] > r["latest_upload"]]
    if wf in ("attesting", "attesting_generator") and restored:
        return "restored_at_head", f"attestation step (re)added {restored[0]['date']} ({restored[0]['sha']}), after the latest release"
    if wf == "missing":
        return "tool_or_workflow_change", "the attesting workflow file no longer exists (repository readable)"
    if wf in ("non_attesting_tool", "attestations_disabled", "token_auth", "old_action"):
        return "tool_or_workflow_change", f"workflow at HEAD: {wf}"
    if wf in ("attesting", "attesting_generator") and n == 1:
        return "isolated_upload", "one unattested release; the workflow at HEAD still attests"
    return "indeterminate", {"repo_unreadable": "publishing repository not publicly readable", "upload_step_not_recognised": "upload step not recognised by our patterns",
                             "na": "non-GitHub publisher", "fetch_error": "workflow could not be read"}.get(wf, f"{n} unattested releases; the workflow at HEAD still attests")


if __name__ == "__main__":
    pk = {r["project"]: r for r in csv.DictReader(open(os.path.join(DATA, "pypi_packages.csv")))}
    pub = {r["project"]: r for r in csv.DictReader(open(os.path.join(DATA, "pypi_publishers.csv")))}
    out = []
    for p, r in pk.items():
        if r.get("stopped_newest") != "True" and r.get("stopped_pip_default") != "True":
            continue
        pb = pub.get(p, {})
        since = r["last_attested_mainline_date"] or r["last_attested_date"]
        try:
            if pb.get("last_kind") == "GitHub":
                wf, marks = evidence(pb["last_repo"], pb["last_workflow"])
                commits = atom(pb["last_repo"], f".github/workflows/{pb['last_workflow']}", since)
            else:
                wf, marks, commits = "na", [], []
            ev = {"workflow_at_head": wf, "workflow_markers": " ".join(marks),
                  "workflow_commits_since": " || ".join(f"{c['date']} {c['sha']} {c['title']}" for c in commits)}
        except OfflineMiss:
            ev = {k: PRIOR.get(p, {}).get(k, "") for k in ("workflow_at_head", "workflow_markers", "workflow_commits_since")}
            commits = [dict(zip(("date", "sha", "title"), (c.split(" ", 2) + ["", ""])[:3])) for c in ev["workflow_commits_since"].split(" || ") if c]
            wf = ev["workflow_at_head"]
        cls, why = classify(r, wf, commits)
        out.append({"rank": r["rank"], "project": p, "stopped_newest": r["stopped_newest"], "stopped_pip_default": r["stopped_pip_default"],
                    "last_attested_version": r["last_attested_version"], "last_attested_date": r["last_attested_date"],
                    "last_attested_mainline_version": r["last_attested_mainline_version"], "last_attested_mainline_date": r["last_attested_mainline_date"],
                    "n_attested_stable": r["n_attested_stable"], "latest_version": r["latest_version"], "latest_upload": r["latest_upload"],
                    "newest_upload_version": r["newest_upload_version"], "n_unattested_after_last_attested": r["n_unattested_after_last_attested"],
                    "publisher": f"{pb.get('last_kind')}:{pb.get('last_repo')}:{pb.get('last_workflow')}", **ev, "rule_class": cls, "rule_reason": why})
    out.sort(key=lambda r: int(r["rank"]))
    with open(os.path.join(DATA, "pypi_regressions.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(out[0])); w.writeheader(); [w.writerow(r) for r in out]
    from collections import Counter
    pip = [r for r in out if r["stopped_pip_default"] == "True"]
    print(len(out), "pip-default", len(pip), Counter(r["rule_class"] for r in pip), Counter(r["workflow_at_head"] for r in pip))
