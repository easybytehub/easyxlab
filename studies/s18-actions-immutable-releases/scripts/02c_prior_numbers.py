"""Step 2c: the prior-work figures compared in the paper, in one file (data/sources/prior_work_numbers.json).

Literal figures from the papers (read in their open-access PDFs, data/raw/prior/, not published) and
figures recomputed from datosh/pinned-actions' published archive `frontend/results-april-2026.json.tar.gz`
(MIT licence; fetched through the GitHub contents API, kept in data/raw/prior/). Offline: keeps the file.
"""
from __future__ import annotations

import base64
import json
import tarfile

from common import DATA, OFFLINE, RAW, api

OUT = DATA / "sources" / "prior_work_numbers.json"
ARCHIVE = RAW / "prior" / "datosh_results-april-2026.json.tar.gz"
LITERAL = {
    "koishybayev_usenix22": {"third_party_refs": 601338, "tag_pct": 78.8, "branch_pct": 20, "commit_hash": 6539,
                             "commit_hash_pct_table": 1, "commit_hash_pct_text": 0.1,
                             "repos_following_guideline": "less than 2%"},
    "decan_icsme22": {"other_repo_steps_version_tag": 258647, "version_tag_pct": 93.0, "branch_or_tag_pct": 5.3,
                      "commit_sha": 4601, "commit_sha_pct": 1.7},
    "huang_lin_icpc25": {"workflows": 18938, "repositories": 5246, "unverified_unpinned_issues_2024": 16439},
    "kubo_ndss26": {"repositories": 338812, "p4_target": 233124, "p4_implemented": 37693, "p4_pct": 16.2,
                    "p4_definition": "every third-party action referenced by a full 40-character SHA, or by a tag of a creator with a verified badge"},
    "chaiwut_secdev25": {"actions": "over 23K", "months": 4},
    "datosh_page": {"fully_pinned_pct_stated": 7, "top_repos": 10000, "updated": "April 2026"},
}


def main() -> None:
    if OFFLINE and not ARCHIVE.exists():
        print("02c: offline and no archive; keeping", OUT.name)
        return
    if not ARCHIVE.exists():
        s, js = api("/repos/datosh/pinned-actions/contents/frontend/results-april-2026.json.tar.gz")
        s, blob = api(js["git_url"])
        ARCHIVE.write_bytes(base64.b64decode(blob["content"]))
    d = json.load(tarfile.open(ARCHIVE).extractfile("result.json"))
    use = [x for x in d if x["actions_total"] > 0]
    full = [x for x in use if x["actions_pinned"] == x["actions_total"]]
    u1 = [x for x in d[:1000] if x["actions_total"] > 0]
    f1 = [x for x in u1 if x["actions_pinned"] == x["actions_total"]]
    out = dict(LITERAL)
    out["datosh_archive_april_2026"] = {
        "entries": len(d), "using_actions": len(use), "fully_pinned": len(full),
        "fully_pinned_pct": round(100 * len(full) / len(use), 1),
        "first_1000_using_actions": len(u1), "first_1000_fully_pinned": len(f1),
        "first_1000_pct": round(100 * len(f1) / len(u1), 1),
        "fields": sorted(d[0]), "note": "no immutability field in this archive; pinned = 40-hex SHA or sha256 image digest"}
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(out["datosh_archive_april_2026"])


if __name__ == "__main__":
    main()
