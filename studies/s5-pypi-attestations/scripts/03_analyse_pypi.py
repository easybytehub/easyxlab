"""Per-project table, rank-band aggregates, monthly series and 'stopped attesting' flags for PyPI.
Reads only the published compact tables (data/compact/). Counts are stored as integers; percentages
are computed once, from the counts, in 09_tables.py."""
import csv, json, os
from datetime import datetime, timezone
from common import DATA
from pypi_versions import versions, highest_stable, SNAP

UTC = timezone.utc
CUT = datetime(2024, 10, 1, tzinfo=UTC)  # PyPI attestations: first attested file in the data is 2024-10-03
BANDS = [(1, 100), (101, 500), (501, 1000), (1001, 2500), (2501, 5000), (5001, 10000), (10001, 15000)]
MONTHS = [(y, m) for y in (2024, 2025, 2026) for m in range(1, 13) if (2024, 10) <= (y, m) <= (2026, 9)]
HALVES = [("2024H2", datetime(2024, 7, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC)), ("2025H1", datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 7, 1, tzinfo=UTC)),
          ("2025H2", datetime(2025, 7, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)), ("2026H1", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 7, 1, tzinfo=UTC)),
          ("2026H2*", datetime(2026, 7, 1, tzinfo=UTC), SNAP)]
month_end = lambda y, m: datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=UTC)
d10 = lambda t: t.date().isoformat() if t else ""


def mainline(vs, r):
    """Stable version that was the highest stable release when its attested file was uploaded (not a backport)."""
    return not r["pre"] and not any((not x["pre"]) and x["v"] > r["v"] and x["t"] < r["t_att"] for x in vs)


projects = list(csv.DictReader(open(os.path.join(DATA, "compact", "projects.csv"))))
rows, hist = [], {}
earliest = None
for pr in projects:
    rank, p = int(pr["rank"]), pr["project"]
    _, vs = versions(p)
    rec = {"rank": rank, "project": p, "n_versions": len(vs)}
    if not vs:
        rec["note"] = ("simple index HTTP " + pr["index_status"]) if pr["index_status"] != "200" else (
            "no files in the index" if pr["n_files_index"] == "0" else "no files uploaded by the list date" if pr["n_files_by_list_date"] == "0"
            else "all files yanked or unparseable")
        rows.append(rec); continue
    hist[p] = vs
    att = sorted([r for r in vs if r["att"]], key=lambda r: r["t_att"])
    att_st = [r for r in att if not r["pre"]]
    att_main = [r for r in att_st if mainline(vs, r)]
    if att:
        earliest = att[0]["t_att"] if earliest is None or att[0]["t_att"] < earliest else earliest
    lat, newest = highest_stable(vs), vs[-1]
    last = att[-1] if att else None
    lm = att_main[-1] if att_main else None
    rec.update(
        latest_version=lat["vs"], latest_upload=d10(lat["t"]), latest_only_prerelease=all(r["pre"] for r in vs),
        latest_attested=lat["att"], latest_fully_attested=lat["att_all"], latest_attested_files=lat["prov"], latest_live_files=lat["live"],
        ever_attested=bool(att), n_attested_versions=len(att), n_attested_stable=len(att_st), n_attested_mainline=len(att_main),
        first_attested_version=att[0]["vs"] if att else "", first_attested_date=d10(att[0]["t_att"]) if att else "",
        last_attested_version=last["vs"] if last else "", last_attested_date=d10(last["t_att"]) if last else "",
        last_attested_mainline_version=lm["vs"] if lm else "", last_attested_mainline_date=d10(lm["t_att"]) if lm else "",
        newest_upload_version=newest["vs"], newest_upload_date=d10(newest["t"]), newest_attested=newest["att"], newest_is_prerelease=newest["pre"],
    )
    ref = lm or last
    after = [r for r in vs if ref and r["t"] > ref["t_att"] and not r["att"]]
    rec["n_unattested_after_last_attested"] = len(after)
    rec["n_unattested_after_prerelease"] = sum(r["pre"] for r in after)
    rec["only_prereleases_attested"] = bool(att) and not att_st
    rec["stopped_newest"] = bool(att) and not newest["att"] and any(r["t_att"] < newest["t"] for r in att)
    # pip-default: the line pip installs had an attested release (a stable, non-backport one) and its latest version is not attested
    rec["stopped_pip_default"] = (not lat["att"]) and any(r["t_att"] < lat["t"] for r in att_main)
    rec["stopped_pip_default_incl_backports"] = (not lat["att"]) and any(r["t_att"] < lat["t"] for r in att_st)
    rows.append(rec)

fields = ["rank", "project", "n_versions", "note", "latest_version", "latest_upload", "latest_only_prerelease", "latest_attested", "latest_fully_attested",
          "latest_attested_files", "latest_live_files", "ever_attested", "n_attested_versions", "n_attested_stable", "n_attested_mainline",
          "first_attested_version", "first_attested_date", "last_attested_version", "last_attested_date", "last_attested_mainline_version",
          "last_attested_mainline_date", "newest_upload_version", "newest_upload_date", "newest_attested", "newest_is_prerelease",
          "n_unattested_after_last_attested", "n_unattested_after_prerelease", "only_prereleases_attested", "stopped_newest", "stopped_pip_default", "stopped_pip_default_incl_backports"]
with open(os.path.join(DATA, "pypi_packages.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fields); w.writeheader(); [w.writerow(r) for r in rows]

ok = [r for r in rows if r["n_versions"]]
cnt = lambda L, k: {"n": len(L), "yes": sum(1 for r in L if r.get(k))}
elig = [r for r in ok if r["latest_upload"] >= "2024-10-01"]
agg = {"list": "hugovk top-pypi-packages, last_update 2026-10-01 12:40:51 (30-day downloads); fetched at a pinned commit, not redistributed",
       "snapshot_cutoff": SNAP.isoformat(), "projects_in_list": len(projects), "projects_analysed": len(ok),
       "not_analysed": {r["project"]: r["note"] for r in rows if not r["n_versions"]},
       "earliest_attested_file": earliest.isoformat(), "eligibility_cutoff": "2024-10-01",
       "eligible_definition": "latest (highest stable) version first uploaded on or after 2024-10-01",
       "latest_attested_all": cnt(ok, "latest_attested"), "latest_fully_attested_all": cnt(ok, "latest_fully_attested"),
       "ever_attested_all": cnt(ok, "ever_attested"), "latest_attested_eligible": cnt(elig, "latest_attested"),
       "mixed_latest": sum(1 for r in ok if r["latest_attested"] and not r["latest_fully_attested"]),
       "stopped_newest": sum(r["stopped_newest"] for r in ok), "stopped_pip_default": sum(r["stopped_pip_default"] for r in ok),
       "stopped_pip_default_incl_backports": sum(r["stopped_pip_default_incl_backports"] for r in ok),
       "stopped_union": sum(r["stopped_newest"] or r["stopped_pip_default"] for r in ok),
       "stopped_newest_only_prereleases_attested": sum(r["stopped_newest"] and r["only_prereleases_attested"] for r in ok),
       "stopped_pip_default_single_attested_stable": sum(r["stopped_pip_default"] and r["n_attested_stable"] == 1 for r in ok),
       "bands": []}
for a, b in BANDS:
    L = [r for r in ok if a <= r["rank"] <= b]; E = [r for r in L if r["latest_upload"] >= "2024-10-01"]
    agg["bands"].append({"band": f"{a}-{b}", "latest_attested": cnt(L, "latest_attested"), "eligible_latest_attested": cnt(E, "latest_attested"),
                         "ever_attested": cnt(L, "ever_attested"), "stopped_pip_default": cnt(L, "stopped_pip_default"), "stopped_newest": cnt(L, "stopped_newest")})
# stops per half-year (pip-default set), against projects with an attested stable release by the end of the half
haz = []
for name, s_, e_ in HALVES:
    stops = sum(1 for r in ok if r["stopped_pip_default"] and s_.date().isoformat() <= (r["last_attested_mainline_date"] or r["last_attested_date"]) < e_.date().isoformat())
    risk = sum(1 for p, vs in hist.items() if any(x["att"] and not x["pre"] and x["t_att"] < e_ for x in vs))
    haz.append({"half": name, "stops": stops, "projects_with_attested_stable_by_end": risk})
agg["stops_by_half"] = haz
mon = []
for (y, m) in MONTHS:
    start, end = datetime(y, m, 1, tzinfo=UTC), month_end(y, m)
    rel = att = pk_rel = pk_att = st_n = st_att = 0
    for p, vs in hist.items():
        inm = [r for r in vs if start <= r["t"] < end]
        a = [r for r in inm if r["att"] and r["t_att"] < end]
        rel += len(inm); att += len(a)
        if inm:
            pk_rel += 1; pk_att += bool(a)
        upto = [r for r in vs if r["t"] < end]
        if upto:
            st_n += 1; h = highest_stable(upto); st_att += bool(h["att"] and h["t_att"] < end)
    mon.append({"month": f"{y}-{m:02d}", "versions": rel, "versions_attested": att, "projects_releasing": pk_rel,
                "projects_releasing_with_attestation": pk_att, "projects_existing": st_n, "projects_latest_attested": st_att})
with open(os.path.join(DATA, "pypi_monthly.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, list(mon[0])); w.writeheader(); [w.writerow(r) for r in mon]
json.dump(agg, open(os.path.join(DATA, "pypi_aggregates.json"), "w"), indent=1)
print({k: v for k, v in agg.items() if k not in ("bands", "not_analysed", "stops_by_half")}); print(agg["not_analysed"]); print(haz)
