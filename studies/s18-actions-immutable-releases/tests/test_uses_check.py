"""Tests for the ref parser and the classifier (python3 -m unittest discover -s tests)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from uses_check import (RepoInfo, classify, extract_uses, parse_repo_node, parse_uses,  # noqa: E402
                        ref_form)

WF = """\
name: ci
on: [push]
# uses: commented/out@v1
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: setup
        uses: "actions/setup-node@1d0ff469b7ec7b3cb9d8673fde0c81c44821de2a" # v4.2.0
      - uses: 'docker/build-push-action@v6.9.0'
      - run: |
          echo "uses: not/this@v1"
          cat <<EOF
          uses: nor/this@main
          EOF
        name: after block
      - uses: ./local-action
      - uses: docker://alpine:3.20
      - uses: owner/repo/sub/path@main
      - run: >-
          folded uses: nope/nope@v2
  call:
    uses: org/shared/.github/workflows/build.yml@v2.1
  matrix:
    steps:
      - uses: ${{ matrix.action }}
      -   uses:    tj-actions/changed-files@v47   # trailing
"""


class ExtractTest(unittest.TestCase):
    def test_extract(self):
        vals = [u["value"] for u in extract_uses(WF)]
        self.assertEqual(vals, [
            "actions/checkout@v4",
            "actions/setup-node@1d0ff469b7ec7b3cb9d8673fde0c81c44821de2a",
            "docker/build-push-action@v6.9.0",
            "./local-action",
            "docker://alpine:3.20",
            "owner/repo/sub/path@main",
            "org/shared/.github/workflows/build.yml@v2.1",
            "${{ matrix.action }}",
            "tj-actions/changed-files@v47",
        ])

    def test_comment_kept(self):
        u = extract_uses(WF)[1]
        self.assertEqual(u["comment"], "v4.2.0")
        self.assertEqual(u["line"], 10)

    def test_block_then_sibling_key(self):
        text = "steps:\n  - run: |\n      echo uses: a/b@v1\n    uses: c/d@v2\n"
        self.assertEqual([u["value"] for u in extract_uses(text)], ["c/d@v2"])

    def test_empty_block(self):
        text = "a:\n  b: |\n  uses: x/y@v1\n"
        self.assertEqual([u["value"] for u in extract_uses(text)], ["x/y@v1"])


class ParseTest(unittest.TestCase):
    def test_forms(self):
        cases = {"v4": "major", "4": "major", "v4.2": "minor", "v4.2.1": "full", "1.2.3-rc.1": "full",
                 "main": "other", "release/v1": "other", "v1-beta": "other", "abc1234": "short-hex",
                 "deadbeef": "other", "1d0ff469b7ec7b3cb9d8673fde0c81c44821de2a": "sha",
                 "1D0FF469B7EC7B3CB9D8673FDE0C81C44821DE2A": "sha", "v1.2.3.4": "other"}
        for ref, form in cases.items():
            self.assertEqual(ref_form(ref), form, ref)

    def test_kinds(self):
        self.assertEqual(parse_uses("./x").kind, "local")
        self.assertEqual(parse_uses("docker://a:b").kind, "docker")
        self.assertEqual(parse_uses("${{ x }}").kind, "expression")
        self.assertEqual(parse_uses("actions/checkout").kind, "invalid")
        p = parse_uses("org/shared/.github/workflows/build.yml@v2")
        self.assertTrue(p.reusable_workflow)
        self.assertEqual((p.owner, p.repo, p.path, p.ref), ("org", "shared", ".github/workflows/build.yml", "v2"))
        p = parse_uses("github/codeql-action/init@v3")
        self.assertFalse(p.reusable_workflow)
        self.assertEqual((p.slug, p.path, p.form), ("github/codeql-action", "init", "major"))


C1, C2 = "a" * 40, "b" * 40
NODE = {
    "nameWithOwner": "o/act", "isArchived": False, "owner": {"__typename": "Organization"},
    "latestRelease": {"tagName": "v2.0.1", "immutable": True, "tagCommit": {"oid": C1}},
    "releases": {"totalCount": 3, "nodes": [
        {"tagName": "v2.0.1", "immutable": True, "isDraft": False, "tagCommit": {"oid": C1}},
        {"tagName": "v2.0.0", "immutable": True, "isDraft": False, "tagCommit": {"oid": C2}},
        {"tagName": "v1.9.0", "immutable": False, "isDraft": False, "tagCommit": {"oid": "c" * 40}}]},
    # refs: v2, v2.0.1, v1.9.0, main, v1
    "t0": {"target": {"__typename": "Tag", "oid": "f" * 40, "target": {"__typename": "Commit", "oid": C1}}},
    "h0": None, "r0": None,
    "t1": {"target": {"__typename": "Commit", "oid": C1}}, "h1": None,
    "r1": {"immutable": True, "isDraft": False, "tagCommit": {"oid": C1}},
    "t2": {"target": {"__typename": "Commit", "oid": "c" * 40}}, "h2": None,
    "r2": {"immutable": False, "isDraft": False, "tagCommit": {"oid": "c" * 40}},
    "t3": None, "h3": {"target": {"oid": C2}}, "r3": None,
    "t4": None, "h4": None, "r4": None,
}
REFS = ["v2", "v2.0.1", "v1.9.0", "main", "v1"]


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        self.info = parse_repo_node(NODE, REFS)

    def v(self, ref):
        return classify(parse_uses(f"o/act@{ref}"), self.info)

    def test_repo_info(self):
        self.assertTrue(self.info.latest_release_immutable)
        self.assertTrue(self.info.any_immutable_release)
        self.assertEqual(self.info.tags["v2"], C1)  # annotated tag peeled
        self.assertEqual(self.info.immutable_by_commit[C1], ["v2.0.1"])

    def test_verdicts(self):
        self.assertEqual(self.v(C2).verdict, "sha")
        v = self.v("v2")
        self.assertEqual((v.verdict, v.form, v.immutable_alternative), ("mutable-tag", "major", "v2.0.1"))
        self.assertEqual(self.v("v2.0.1").verdict, "immutable-tag")
        v = self.v("v1.9.0")
        self.assertEqual((v.verdict, v.form, v.immutable_alternative), ("mutable-tag", "full", None))
        v = self.v("main")
        self.assertEqual((v.verdict, v.immutable_alternative), ("branch", "v2.0.0"))
        self.assertEqual(self.v("v1").verdict, "unresolved")
        self.assertEqual(self.v("abc1234").verdict, "unresolved")

    def test_missing_repo_and_offline(self):
        self.assertEqual(classify(parse_uses("x/y@v1"), parse_repo_node(None, ["v1"])).verdict, "unresolved")
        self.assertEqual(classify(parse_uses("x/y@v1"), None).verdict, "unknown")
        self.assertEqual(classify(parse_uses("./a"), None).verdict, "not-remote")

    def test_no_releases(self):
        info = RepoInfo(tags={"v1": C1})
        v = classify(parse_uses("x/y@v1"), info)
        self.assertEqual((v.verdict, v.immutable_alternative), ("mutable-tag", None))


if __name__ == "__main__":
    unittest.main()


class AnchorTest(unittest.TestCase):
    def test_anchor_and_alias(self):
        text = ("env:\n  CO: &co actions/checkout@v4 # v4\n"
                "jobs:\n  a:\n    steps:\n      - uses: &setup actions/setup-node@v5\n"
                "      - uses: *co\n      - uses: *setup\n      - uses: *unknown\n")
        self.assertEqual([u["value"] for u in extract_uses(text)],
                         ["actions/setup-node@v5", "actions/checkout@v4", "actions/setup-node@v5", "*unknown"])

    def test_parallel_steps(self):
        text = "jobs:\n  a:\n    steps:\n      - parallel:\n          - name: x\n            uses: a/b@v1\n"
        self.assertEqual([u["value"] for u in extract_uses(text)], ["a/b@v1"])


class EdgeTest(unittest.TestCase):
    def test_value_on_next_line(self):
        text = "jobs:\n  a:\n    steps:\n      - uses:\n          slack/act@v2  # c\n      - uses: x/y@v1\n"
        self.assertEqual([(u["line"], u["value"]) for u in extract_uses(text)], [(4, "slack/act@v2"), (6, "x/y@v1")])

    def test_self_repository_syntax(self):
        self.assertEqual(parse_uses("$/.github/actions/setup").kind, "self")


class ShaExistenceTest(unittest.TestCase):
    def test_unresolvable_sha(self):
        node = dict(NODE, s0={"__typename": "Commit", "oid": C1}, s1={"__typename": "Tag", "oid": C2})
        info = parse_repo_node(node, REFS, [C1, C2])
        self.assertEqual(classify(parse_uses(f"o/act@{C1}"), info).verdict, "sha")
        self.assertEqual(classify(parse_uses(f"o/act@{C2}"), info).verdict, "sha-unresolvable")
        self.assertEqual(classify(parse_uses(f"o/act@{C2}"), None).verdict, "sha")  # offline
        self.assertEqual(classify(parse_uses(f"x/y@{C2}"), parse_repo_node(None, [], [C2])).verdict, "sha-unresolvable")
