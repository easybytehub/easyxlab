#!/usr/bin/env python3
"""Write data/summary.json: every figure that claims.csv checks, from the published data/.

Offline, standard library only; run after 09_tables.py (run.sh). Shares are fractions at full
precision (0.2320..., not 23.2): claims.csv rounds them with its `fmt` column.

Inputs: data/metrics.json, data/pypi_monthly.csv, data/pypi_packages.csv.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

S = Path(__file__).resolve().parent.parent
D = S / "data"


def rows(name: str) -> list[dict]:
    with open(D / name, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def month_text(iso: str) -> str:
    """'2024-11' or '2024-11-30…' -> 'November 2024'."""
    months = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
              "October", "November", "December")  # not strftime: independent of the locale
    return f"{months[int(iso[5:7]) - 1]} {int(iso[:4])}"


def band_text(band: str) -> str:
    """'10001-15000' -> '10,001–15,000' (en dash, as printed)."""
    a, b = band.split("-")
    return f"{int(a):,}–{int(b):,}"


def main() -> None:
    m = json.loads((D / "metrics.json").read_text(encoding="utf-8"))
    py, npm, pub, stop = m["pypi"], m["npm"], m["pypi_publishers"], m["pypi_stopped"]
    analysed = py["projects_analysed"]
    ever = py["ever_attested_all"]["yes"]
    latest = py["latest_attested_all"]["yes"]
    elig = py["latest_attested_eligible"]

    # eligibility recomputed from the per-project table: latest version first uploaded ON OR AFTER the cut-off
    pk = rows("pypi_packages.csv")
    cut = py["eligibility_cutoff"]
    elig_rows = [r for r in pk if r["latest_upload"] and r["latest_upload"] >= cut]
    stopped_rows = [r for r in pk if r["stopped_pip_default"] == "True"]

    monthly = {r["month"]: r for r in rows("pypi_monthly.csv")}
    first_m, last_m = (x[0] for x in m["headline"]["state_share_first_last"])
    share_m = {k: int(monthly[k]["projects_latest_attested"]) / int(monthly[k]["projects_existing"])
               for k in (first_m, last_m)}

    reviewed = stop["pip_default_reviewed_classes"]
    rules = pub["rules"]
    tob = m["tob_comparison"]
    bands = [{"label": band_text(b["band"]), "n": b["latest_attested"]["n"],
              "share": b["latest_attested"]["yes"] / b["latest_attested"]["n"]} for b in py["bands"]]

    out = {
        "list_date": py["snapshot_cutoff"][:10],
        "projects_in_list": py["projects_in_list"],
        "analysed": analysed,
        "first_attested_month": month_text(py["earliest_attested_file"]),
        "never_attested": analysed - ever,
        "never_share": (analysed - ever) / analysed,
        "ever_attested": ever,
        "latest_attested": latest,
        "latest_share": latest / analysed,
        "eligibility_cutoff": cut,
        "eligible_n": elig["n"],
        "eligible_recount_on_or_after": len(elig_rows),
        "eligible_on_cutoff_day": sum(r["latest_upload"] == cut for r in elig_rows),
        "eligible_share": elig["yes"] / elig["n"],
        "bands": bands,
        "trend": {"first_month": month_text(first_m), "last_month": month_text(last_m),
                  "first_share": share_m[first_m], "last_share": share_m[last_m],
                  "first_projects": int(monthly[first_m]["projects_existing"])},
        "tob": {"total": tob["tob_total"], "disagree": len(tob["disagreements"]),
                "agree": tob["tob_total"] - len(tob["disagreements"])},
        "stopped_newest": py["stopped_newest"],
        "stopped_pip_default": py["stopped_pip_default"],
        "stopped_pip_default_latest_attested": sum(r["latest_attested"] == "True" for r in stopped_rows),
        "stopped_other": py["stopped_newest"] - py["stopped_pip_default"],
        "stopped_prerelease_or_secondary": stop["broad_only_classes"]["prerelease_or_secondary_pipeline"],
        "stopped_share_of_ever": py["stopped_pip_default"] / ever,
        "reviewed_classes": reviewed,
        "reviewed_total": sum(reviewed.values()),
        "uv_publish": stop["pip_default_uv_publish"],
        "workflow_at_head_attesting": stop["pip_default_workflow_at_head"]["attesting"],
        "publishers": {
            "attested_projects": pub["attested_projects"],
            "kinds_total": sum(pub["kinds_last"].values()),
            "projects_with_change": pub["projects_with_change_at_least"],
            "changes": pub["changes_at_least"],
            "cross": pub["cross_repo_or_kind"],
            "cross_confirmed": pub["cross_confirmed"],
            "cross_confirmed_by_rules": sum(v for k, v in rules.items() if k.startswith("confirmed:")
                                            and k != "confirmed: same repository"),
            "cross_metadata": pub["cross_metadata"],
            "not_confirmed": rules["not confirmed by public data"],
            "not_confirmed_projects": len(pub["projects_not_confirmed"]),
        },
        "npm": {
            "sample": npm["n"],
            "top_n": npm["latest_attested_top1000"]["n"],
            "top_share": npm["latest_attested_top1000"]["yes"] / npm["latest_attested_top1000"]["n"],
            "ever": npm["attested_packages"],
            "stopped": npm["regression"],
            "stopped_share": npm["regression"] / npm["attested_packages"],
        },
    }
    (D / "summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {D / 'summary.json'}")


if __name__ == "__main__":
    main()
