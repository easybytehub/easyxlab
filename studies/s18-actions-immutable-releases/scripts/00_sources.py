"""Step 0: fetch the documentation and announcements the study relies on, through the API only.

- GitHub Docs pages from the github/docs repository (contents API) with the date and id of the
  last commit that touched each file;
- GitHub changelog and blog entries from github.blog's WordPress REST API (robots.txt: allow all);
- the zizmor audit documentation and the pinact README (contents API);
- a search of github/docs and of the changelog for workflow-level dependency locking.
Pages go to data/raw/src/ (not published); literal excerpts to data/sources/excerpts.json.
With OFFLINE=1 (default) and no saved pages, the published excerpts are left untouched.
"""
from __future__ import annotations

import base64
import html
import json
import re
import urllib.parse

from common import DATA, OFFLINE, RAW, api, fetch

SRC = RAW / "src"
OUT = DATA / "sources" / "excerpts.json"

DOCS = {
    "docs_actions_immutable": "content/actions/how-tos/create-and-publish-actions/using-immutable-releases-and-tags-to-manage-your-actions-releases.md",
    "docs_concept_immutable": "content/code-security/concepts/supply-chain-security/immutable-releases.md",
    "docs_prevent_release_changes": "content/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes.md",
    "docs_release_and_maintain": "content/actions/how-tos/create-and-publish-actions/release-and-maintain-actions.md",
    "docs_manage_custom_actions": "content/actions/how-tos/create-and-publish-actions/manage-custom-actions.md",
    "docs_secure_use": "content/actions/reference/security/secure-use.md",
    "docs_aup": "content/site-policy/acceptable-use-policies/github-acceptable-use-policies.md",
}
REPO_FILES = {
    "zizmor_audits": ("zizmorcore/zizmor", "docs/audits.md"),
    "pinact_readme": ("suzuki-shunsuke/pinact", "README.md"),
}
BLOG = "https://github.blog/wp-json/wp/v2/"


def text_of(html_s: str) -> str:
    t = re.sub(r"<[^>]+>", " ", html_s)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def get_repo_file(repo: str, path: str) -> dict:
    s, js = api(f"/repos/{repo}/contents/{urllib.parse.quote(path)}")
    assert s == 200, (repo, path, s)
    body = base64.b64decode(js["content"]).decode("utf-8")
    s, commits = api(f"/repos/{repo}/commits?per_page=1&path={urllib.parse.quote(path)}")
    c = commits[0]
    return {"repo": repo, "path": path, "blob_sha": js["sha"], "last_commit": c["sha"],
            "last_commit_date": c["commit"]["committer"]["date"], "text": body}


def blog(endpoint: str, **params) -> list:
    url = BLOG + endpoint + "?" + urllib.parse.urlencode(params)
    s, _, b = fetch(url)
    assert s == 200, (url, s)
    return json.loads(b)


# (source key, literal substring that must be found in the saved page) -> quoted in METHOD/paper
QUOTES = [
    ("docs_actions_immutable", "If you are ready to share an unchangeable version of your action, create a release"),
    ("docs_actions_immutable", "If you want to be able to update the Git tag of a release later, do not create a release"),
    ("docs_actions_immutable", "If your release contains breaking changes for existing workflows, create a major version tag (for example, `v1`)."),
    ("docs_actions_immutable", "For a major version, update the tag to point to the Git ref of the latest related minor version or patch version."),
    ("docs_concept_immutable", "Once an immutable release is published, its associated Git tag is locked to a specific commit, cannot be changed, and cannot be deleted while the release exists."),
    ("docs_concept_immutable", "Only the assets and tag are locked."),
    ("docs_concept_immutable", "If you delete the immutable release, you can delete the tag, but you cannot reuse the same tag name."),
    ("docs_actions_immutable", "create a major version tag (for example, `v1`)"),
    ("docs_prevent_release_changes", "Be aware that immutability will only apply to future releases."),
    ("docs_manage_custom_actions", "Instead, you can recommend that your users specify a major version when using your action"),
    ("docs_manage_custom_actions", "Move the major version tag (for example, `v1`) to point to the Git ref of the current release."),
    ("docs_secure_use", "Pinning an action to a full-length commit SHA is currently the only way to use an action as an immutable release."),
    ("docs_aup", "Researchers may use public, non-personal information from the Service for research purposes, only if any publications resulting from that research are [open access]"),
    ("docs_aup", "Scraping does not refer to the collection of information through our API."),
    ("zizmor_audits", "GitHub does not have immutable\nbranches or tags"),
    ("pinact_readme", "Pinning an action to a full length commit SHA is currently the only way to use an action as an immutable release."),
    ("cl_immutable", "Tag protection : Tags for new immutable releases are protected and can’t be deleted or moved."),
    ("cl_immutable", "Existing releases remain mutable unless you republish them."),
    ("cl_immutable", "GitHub recommends that workflows pin dependency versions to a specific commit SHA"),
    ("post_roadmap", "We’re introducing a dependencies: section in workflow YAML that locks all direct and transitive dependencies with the commits SHA"),
    ("post_roadmap", "Our current milestones for lock files are as follows: Milestones: Phase Target Public preview 3-6 months General availability 6 months"),
    ("post_roadmap", "we’re moving away from mutable references and towards immutable releases with stricter release requirements"),
]


def excerpts() -> None:
    meta = json.loads((SRC / "meta.json").read_text())
    out = []
    for key, q in QUOTES:
        q = q.replace("\\n", "\n")
        if key in meta:
            text = (SRC / f"{key}.md").read_text(encoding="utf-8")
            src = {"source": f"github.com/{meta[key]['repo']} {meta[key]['path']}", "last_commit": meta[key]["last_commit"],
                   "last_commit_date": meta[key]["last_commit_date"]}
            found = q in text
        else:
            items = json.loads((SRC / f"{key}.json").read_text())
            hit = [x for x in items if q in x["text"]]
            found = bool(hit)
            src = {"source": hit[0]["link"], "published": hit[0]["date"], "title": hit[0]["title"]} if hit else {}
        out.append({"key": key, "quote": q, "found_verbatim": found, **src})
    (OUT.parent).mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    bad = [o["quote"][:60] for o in out if not o["found_verbatim"]]
    print("excerpts:", len(out), "not found:", bad)


def main() -> None:
    if OFFLINE and not SRC.exists():
        print("00_sources: offline and no saved pages; keeping data/sources/excerpts.json")
        return
    if OFFLINE:
        excerpts()
        return
    SRC.mkdir(parents=True, exist_ok=True)
    meta = {}
    for key, path in DOCS.items():
        d = get_repo_file("github/docs", path)
        (SRC / f"{key}.md").write_text(d.pop("text"), encoding="utf-8")
        meta[key] = d
    for key, (repo, path) in REPO_FILES.items():
        d = get_repo_file(repo, path)
        (SRC / f"{key}.md").write_text(d.pop("text"), encoding="utf-8")
        meta[key] = d
    # changelog entries
    fields = "id,date,link,title,content"
    found = {}
    for key, q, after in (("cl_immutable", "immutable releases", "2025-06-01T00:00:00"),
                          ("cl_sha_pinning", "SHA pinning", "2025-06-01T00:00:00"),
                          ("cl_lock", "lock", "2026-03-26T00:00:00"),
                          ("cl_dependency", "dependencies", "2026-03-26T00:00:00"),
                          ("cl_pin", "pin", "2026-03-26T00:00:00")):
        found[key] = blog("changelogs", search=q, after=after, per_page=50, _fields=fields)
    found["post_roadmap"] = blog("posts", search="Actions security roadmap", after="2026-03-01T00:00:00",
                                 per_page=20, _fields=fields)
    # every changelog title since the roadmap, to look for dependency locking by title
    titles = []
    for page in range(1, 20):
        url = BLOG + "changelogs?" + urllib.parse.urlencode({"after": "2026-03-26T00:00:00", "per_page": 100,
                                                             "page": page, "_fields": "id,date,link,title"})
        s, h, b = fetch(url)
        if s != 200:
            break
        batch = json.loads(b)
        titles += [{"date": x["date"], "link": x["link"], "title": text_of(x["title"]["rendered"])} for x in batch]
        if len(batch) < 100:
            break
    (SRC / "changelog_titles_since_2026-03-26.json").write_text(json.dumps(titles, indent=1))
    for key, items in found.items():
        slim = [{"date": x["date"], "link": x["link"], "title": text_of(x["title"]["rendered"]),
                 "text": text_of(x["content"]["rendered"])} for x in items]
        (SRC / f"{key}.json").write_text(json.dumps(slim, indent=1))
    (SRC / "meta.json").write_text(json.dumps(meta, indent=1))
    excerpts()
    print("saved", len(meta), "repo files,", sum(len(v) for v in found.values()), "blog items,",
          len(titles), "changelog titles")


if __name__ == "__main__":
    main()
