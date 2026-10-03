#!/usr/bin/env python3
"""uses_check: what does each `uses:` in a GitHub Actions workflow actually pin?

Usage:
    uses_check.py PATH [PATH ...] [--offline] [--json]

PATH is a workflow file or a directory (typically `.github/workflows`). For every `uses:` that
references a remote action or reusable workflow (`owner/repo[/path]@ref`) it prints one verdict:

    sha              pinned by a full 40-character commit SHA
    sha-unresolvable a full SHA that is not a commit of the action repository (online mode), e.g. a
                     deleted commit or the id of an annotated tag object
    immutable-tag    a tag whose GitHub release is immutable: the tag cannot be moved or deleted
    mutable-tag      a tag that is not the tag of an immutable release (form: major, minor, full, other)
    branch           a branch
    unresolved       the repository or the ref was not found (or the ref is a short SHA)

and, for a mutable tag, the immutable release tag (if any) that points to the same commit, i.e. the
protected tag you could switch to without changing the code that runs. With --offline only the
syntactic form of the ref is reported. Online mode uses the GitHub GraphQL API and reads a token
from $GITHUB_TOKEN, $GH_TOKEN or `gh auth token`.

Note: GitHub's documentation recommends that action authors keep major version tags (`v1`) movable;
a mutable major tag is the documented, intended usage, not a defect of the action or of the caller.

Part of EasyxLab study S18. Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

USER_AGENT = "EasyxLab-uses-check/0.1 (+https://easybyte.es/lab/)"

# ---------------------------------------------------------------- extraction

_KEY_RE = re.compile(r"""^(?P<indent>\s*)(?P<dash>-\s+)?(?P<q>["']?)(?P<key>[A-Za-z_][\w-]*)(?P=q)\s*:(?:\s+(?P<val>.*))?$""")
_BLOCK_RE = re.compile(r"^[|>][-+0-9]*\s*(?:#.*)?$")


def _strip_comment(v: str) -> tuple[str, str]:
    """Split a plain or quoted YAML scalar from a trailing ` # comment`."""
    v = v.strip()
    if v[:1] in ("'", '"'):
        q = v[0]
        end = v.find(q, 1)
        while q == "'" and end != -1 and v[end + 1:end + 2] == "'":  # '' escape
            end = v.find(q, end + 2)
        if end != -1:
            rest = v[end + 1:].strip()
            return v[1:end].replace("''", "'") if q == "'" else v[1:end], rest[1:].strip() if rest.startswith("#") else ""
    m = re.search(r"\s#", v)
    if m:
        return v[:m.start()].strip(), v[m.end():].strip()
    return v, ""


_ANCHOR_DEF = re.compile(r"""^\s*(?:-\s+)?["']?[A-Za-z_][\w-]*["']?\s*:\s+&([^\s,\[\]{}]+)\s+(.+)$""")


def extract_uses(text: str) -> list[dict]:
    """Return every `uses:` value in a workflow file: [{line, value, comment}].

    YAML-aware enough for workflow files: skips comments and the contents of block scalars
    (`run: |` scripts), handles `- uses:`, quoted keys/values, steps nested under `parallel:`,
    scalar anchors (`uses: &co actions/checkout@v4`) and aliases (`uses: *co`) defined in the file.
    """
    anchors = {}
    for line in text.splitlines():
        m = _ANCHOR_DEF.match(line)
        if m:
            anchors[m.group(1)] = _strip_comment(m.group(2))[0]
    out = []
    lines = text.splitlines()
    block_parent = None   # indentation of the key that opened a block scalar
    block_indent = None   # indentation of the block content (set by its first non-empty line)
    pending = None        # (line, key column) of a `uses:` whose value starts on the next line
    for no, line in enumerate(lines, 1):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if pending is not None and stripped and not stripped.startswith("#"):
            if indent > pending[1]:
                value, comment = _strip_comment(stripped)
                out.append({"line": pending[0], "value": value, "comment": comment})
                pending = None
                continue
            pending = None
        if block_parent is not None:
            if not stripped:
                continue
            if block_indent is None:
                if indent > block_parent:
                    block_indent = indent
                    continue
            elif indent >= block_indent:
                continue
            block_parent = block_indent = None
        if not stripped or stripped.startswith("#"):
            continue
        m = _KEY_RE.match(line)
        if not m:
            continue
        val = m.group("val") or ""
        key_col = len(m.group("indent")) + len(m.group("dash") or "")
        if _BLOCK_RE.match(val.strip()):
            block_parent, block_indent = key_col, None
            continue
        if m.group("key") == "uses" and not val.strip():
            pending = (no, key_col)
            continue
        if m.group("key") == "uses" and val.strip():
            v = val.strip()
            am = re.match(r"&[^\s,\[\]{}]+\s+", v)
            if am:  # anchor on the value: drop the anchor
                v = v[am.end():]
            value, comment = _strip_comment(v)
            if value.startswith("*") and value[1:] in anchors:  # alias to a scalar anchored in this file
                value = anchors[value[1:]]
            out.append({"line": no, "value": value, "comment": comment})
    return out


# ---------------------------------------------------------------- parsing

SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
SHORT_HEX = re.compile(r"^[0-9a-f]{7,39}$")
MAJOR = re.compile(r"^v?\d+$")
MINOR = re.compile(r"^v?\d+\.\d+$")
FULL = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.+-]+)?$")
_REMOTE = re.compile(r"^(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)/(?P<repo>[A-Za-z0-9._-]+)"
                     r"(?P<path>(?:/[^@\s]*)?)@(?P<ref>\S+)$")
_REUSABLE = re.compile(r"(?:^|/)\.github/workflows/[^/]+\.ya?ml$")


def ref_form(ref: str) -> str:
    if SHA40.match(ref):
        return "sha"
    if MAJOR.match(ref):
        return "major"
    if MINOR.match(ref):
        return "minor"
    if FULL.match(ref):
        return "full"
    if SHORT_HEX.match(ref) and re.search(r"\d", ref) and re.search(r"[a-f]", ref):
        return "short-hex"
    return "other"


@dataclass
class UsesRef:
    value: str
    kind: str                      # remote | local | self | docker | expression | invalid
    owner: str = ""
    repo: str = ""
    path: str = ""
    ref: str = ""
    reusable_workflow: bool = False
    form: str = ""                 # sha | major | minor | full | short-hex | other

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}".lower()


def parse_uses(value: str) -> UsesRef:
    v = value.strip()
    if v.startswith("./") or v.startswith(".\\") or v in (".", ".."):
        return UsesRef(v, "local")
    if v.startswith("$/"):  # self-repository syntax (changelog 2026-07-30): same repo, running commit
        return UsesRef(v, "self")
    if v.startswith("docker://"):
        return UsesRef(v, "docker")
    if "${{" in v:
        return UsesRef(v, "expression")
    m = _REMOTE.match(v)
    if not m:
        return UsesRef(v, "invalid")
    path = m.group("path").strip("/")
    return UsesRef(v, "remote", m.group("owner"), m.group("repo"), path, m.group("ref"),
                   bool(_REUSABLE.search(path)), ref_form(m.group("ref")))


# ---------------------------------------------------------------- resolution data

def _semver_key(tag: str):
    nums = re.findall(r"\d+", tag)
    return tuple(int(n) for n in nums[:4]) + (0 if "-" in tag else 1,)


@dataclass
class RepoInfo:
    """What GitHub says about one action repository and the refs callers use."""
    exists: bool = True
    archived: bool = False
    owner_type: str = ""
    latest_release_tag: str | None = None
    latest_release_immutable: bool | None = None
    any_immutable_release: bool = False
    releases_seen: int = 0
    tags: dict = field(default_factory=dict)        # ref -> peeled commit oid (None if unknown)
    branches: dict = field(default_factory=dict)    # ref -> commit oid
    release_of: dict = field(default_factory=dict)  # ref -> {"immutable": bool, "commit": oid}
    immutable_by_commit: dict = field(default_factory=dict)  # commit oid -> [immutable release tags]
    shas: dict = field(default_factory=dict)        # full SHA (lowercase) -> True if GitHub resolves it


def build_repo_query(alias: str, owner: str, name: str, refs: list[str], shas: list[str] = ()) -> str:
    """GraphQL fragment for one action repository, the non-SHA refs and the full SHAs used against it."""
    j = json.dumps
    parts = [f"{alias}: repository(owner: {j(owner)}, name: {j(name)}) {{",
             "nameWithOwner isArchived owner { __typename }",
             "latestRelease { tagName immutable tagCommit { oid } }",
             "releases(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) "
             "{ totalCount nodes { tagName immutable isDraft tagCommit { oid } } }"]
    for i, r in enumerate(refs):
        parts.append(f"t{i}: ref(qualifiedName: {j('refs/tags/' + r)}) {{ target {{ __typename oid "
                     f"... on Tag {{ target {{ __typename oid ... on Tag {{ target {{ oid }} }} }} }} }} }}")
        parts.append(f"h{i}: ref(qualifiedName: {j('refs/heads/' + r)}) {{ target {{ oid }} }}")
        parts.append(f"r{i}: release(tagName: {j(r)}) {{ immutable isDraft tagCommit {{ oid }} }}")
    for i, sha in enumerate(shas):
        parts.append(f"s{i}: object(oid: {j(sha.lower())}) {{ __typename oid }}")
    parts.append("}")
    return "\n".join(parts)


def _peel(target: dict | None) -> str | None:
    depth = 0
    while target and target.get("__typename") == "Tag" and depth < 3:
        target = target.get("target")
        depth += 1
    if not target:
        return None
    return target.get("oid") if target.get("__typename", "Commit") != "Tag" else None


def parse_repo_node(node: dict | None, refs: list[str], shas: list[str] = ()) -> RepoInfo:
    if not node:
        return RepoInfo(exists=False, shas={x.lower(): False for x in shas})
    info = RepoInfo(archived=node.get("isArchived", False), owner_type=(node.get("owner") or {}).get("__typename", ""))
    lr = node.get("latestRelease")
    if lr:
        info.latest_release_tag, info.latest_release_immutable = lr["tagName"], bool(lr["immutable"])
    rels = (node.get("releases") or {}).get("nodes") or []
    info.releases_seen = len(rels)
    for rel in rels:
        if rel.get("immutable"):
            info.any_immutable_release = True
            oid = (rel.get("tagCommit") or {}).get("oid")
            if oid:
                info.immutable_by_commit.setdefault(oid, []).append(rel["tagName"])
    for oid in info.immutable_by_commit:
        info.immutable_by_commit[oid].sort(key=_semver_key, reverse=True)
    for i, r in enumerate(refs):
        t = node.get(f"t{i}")
        if t:
            info.tags[r] = _peel(t.get("target"))
        h = node.get(f"h{i}")
        if h:
            info.branches[r] = (h.get("target") or {}).get("oid")
        rel = node.get(f"r{i}")
        if rel and not rel.get("isDraft"):
            oid = (rel.get("tagCommit") or {}).get("oid")
            info.release_of[r] = {"immutable": bool(rel.get("immutable")), "commit": oid}
            if rel.get("immutable"):
                info.any_immutable_release = True
                if oid and r not in info.immutable_by_commit.get(oid, []):
                    info.immutable_by_commit.setdefault(oid, []).append(r)
    for i, sha in enumerate(shas):
        if f"s{i}" in node:
            info.shas[sha.lower()] = (node.get(f"s{i}") or {}).get("__typename") == "Commit"
    return info


# ---------------------------------------------------------------- classification

@dataclass
class Verdict:
    verdict: str                    # sha | immutable-tag | mutable-tag | branch | unresolved | not-remote
    form: str = ""
    ambiguous: bool = False         # a tag and a branch share the name
    immutable_alternative: str | None = None  # immutable release tag at the same commit (mutable tags)
    note: str = ""


def classify(u: UsesRef, info: RepoInfo | None) -> Verdict:
    if u.kind != "remote":
        return Verdict("not-remote", note=u.kind)
    if u.form == "sha":
        if info is not None and (not info.exists or info.shas.get(u.ref.lower()) is False):
            return Verdict("sha-unresolvable", "sha", note="commit not found in the action repository")
        return Verdict("sha", "sha")
    if info is None:
        return Verdict("unknown", u.form, note="offline: form only")
    if not info.exists:
        return Verdict("unresolved", u.form, note="repository not found")
    is_tag, is_branch = u.ref in info.tags, u.ref in info.branches
    if is_tag:
        rel = info.release_of.get(u.ref)
        if rel and rel["immutable"]:
            return Verdict("immutable-tag", u.form, is_branch)
        commit = info.tags.get(u.ref)
        alt = (info.immutable_by_commit.get(commit) or [None])[0] if commit else None
        return Verdict("mutable-tag", u.form, is_branch, alt)
    if is_branch:
        commit = info.branches.get(u.ref)
        alt = (info.immutable_by_commit.get(commit) or [None])[0] if commit else None
        return Verdict("branch", u.form, False, alt)
    return Verdict("unresolved", u.form, note="short SHA (not resolved by Actions)" if u.form == "short-hex"
                   else "ref not found")


# ---------------------------------------------------------------- CLI

def _token() -> str | None:
    for k in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(k):
            return os.environ[k]
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _default_post(query: str) -> dict:
    tok = _token()
    if not tok:
        raise SystemExit("no GitHub token: set GITHUB_TOKEN, or use --offline")
    req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps({"query": query}).encode(),
                                 headers={"Authorization": f"Bearer {tok}", "User-Agent": USER_AGENT,
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def resolve(refs_by_repo: dict[tuple[str, str], set[str]], post=_default_post, batch: int = 6) -> dict:
    """{(owner, repo): {refs}} -> {slug: RepoInfo}. `post(query) -> GraphQL JSON`."""
    out: dict[str, RepoInfo] = {}
    items = sorted(refs_by_repo.items())
    for k in range(0, len(items), batch):
        chunk = items[k:k + batch]
        frags, keys = [], []
        for i, ((owner, repo), refs) in enumerate(chunk):
            rl = sorted(r for r in refs if ref_form(r) != "sha")
            sl = sorted({r.lower() for r in refs if ref_form(r) == "sha"})
            frags.append(build_repo_query(f"a{i}", owner, repo, rl, sl))
            keys.append(((owner, repo), rl, sl))
        js = post("{\n" + "\n".join(frags) + "\n}")
        data = js.get("data") or {}
        for i, ((owner, repo), rl, sl) in enumerate(keys):
            out[f"{owner}/{repo}".lower()] = parse_repo_node(data.get(f"a{i}"), rl, sl)
    return out


def _files(paths: list[str]) -> list[Path]:
    fs = []
    for p in map(Path, paths):
        if p.is_dir():
            fs += sorted(x for x in p.iterdir() if x.suffix in (".yml", ".yaml") and x.is_file())
        elif p.is_file():
            fs.append(p)
    return fs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="+", help="workflow files or .github/workflows directories")
    ap.add_argument("--offline", action="store_true", help="no network: report the syntactic form only")
    ap.add_argument("--json", action="store_true", help="JSON lines output")
    a = ap.parse_args(argv)
    rows = []
    for f in _files(a.paths):
        for u in extract_uses(f.read_text(encoding="utf-8", errors="replace")):
            rows.append((f, u, parse_uses(u["value"])))
    infos = {}
    if not a.offline:
        want: dict[tuple[str, str], set[str]] = {}
        for _, _, p in rows:
            if p.kind == "remote":
                want.setdefault((p.owner, p.repo), set()).add(p.ref)
        infos = resolve(want)
    counts: dict[str, int] = {}
    for f, u, p in rows:
        v = classify(p, None if a.offline else infos.get(p.slug))
        counts[v.verdict] = counts.get(v.verdict, 0) + 1
        if a.json:
            print(json.dumps({"file": str(f), "line": u["line"], "uses": p.value, **asdict(v)}))
        else:
            extra = f" -> immutable {v.immutable_alternative} at the same commit" if v.immutable_alternative else ""
            form = f" ({v.form})" if v.form and v.verdict not in ("sha",) else ""
            note = f" [{v.note}]" if v.note else ""
            print(f"{f}:{u['line']}\t{p.value}\t{v.verdict}{form}{extra}{note}")
    if not a.json:
        print("# " + ", ".join(f"{k}: {n}" for k, n in sorted(counts.items())), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
