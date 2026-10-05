#!/usr/bin/env python3
"""Build the version table and the headline numbers from the extracted data.

  data/version_table.csv   one row per version x housing item (measure, milestone/target,
                           component summary): version, proposed, Spain's request, adopted
                           (and status), Council text identical?, amount(s), goal, deadline,
                           literal wording, indicator, scoreboard status (current version
                           only), stated reason (recital, literal first sentence), change
                           categories versus the previous version
  data/summary.json        the headline numbers, recomputed here from the CSVs
"""
import csv, datetime, json, re
from s20lib import DATA, VERSIONS
import differ

CORE = ("C2.I2", "C2.I7", "C2.R3", "C2.R7", "C2.summary")


def rows(name):
    return list(csv.DictReader(open(DATA / name, encoding="utf-8")))


def pct(a, b):
    """Percentage change, at full precision (the text rounds it when it is rendered or quoted)."""
    return 100 * (b - a) / a


def day(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {d:%B} {d.year}"


def month(iso):
    return f"{datetime.date.fromisoformat(iso):%B %Y}"


def timeline(rows, event):
    """The date of the one timeline row whose event starts with `event`."""
    hits = {r["date"] for r in rows if r["event"].startswith(event)}
    assert len(hits) == 1, (event, hits)
    return hits.pop()


# Figures the abstracts quote from outside the study's data (paper §2-§3; references.csv): the
# legal cut-off of the RRF, a Government statement, a quoted requirement and a press report.
TEXT = {
    "rrf_cutoff": "31 August 2026",            # Regulation (EU) 2021/241, art. 18(4)(i)
    "gov_measures_modified_about": 160,         # Referencia del Consejo de Ministros, 9-12-2025
    "l6_climate_share_quoted": 0.53,            # «At least 53%», milestone C2.I7 L6 (CID annex)
    "press_first_report": "6 September 2026",   # El Confidencial, citing AIReF's tracker
    "press_airef_eur_m": 1301,
}


def main():
    hr, hm, rs = rows("housing_rows.csv"), rows("housing_measures.csv"), rows("reasons.csv")
    ad = {r["version"]: r for r in rows("adoption.csv")}
    cv = rows("council_vs_proposal.csv")
    sb = {(r["measure"], r["number"]): r for r in rows("scoreboard_versions.csv")}
    df = [d for d in rows("diffs.csv") if d["comparison"] == "consecutive"]
    costs = {}
    for c in rows("measure_costs.csv"):
        if c["eur_million"]:
            k = (c["version"], c["measure"])
            costs[k] = costs.get(k, 0.0) + float(c["eur_million"])
    labels = [v[0] for v in VERSIONS]
    out = []

    def reason(version, measure):
        x = [r for r in rs if r["version"] == version and r["measure"] == measure]
        return " / ".join(f"recital {r['recital']} [{r['reason_label']}]: {r['first_sentence']}" for r in x)

    def cats(version, measure, number):
        x = [d for d in df if d["to_version"] == version and d["measure"] == measure and d["number"] == number]
        return x[0]["categories"] if x else ""

    def council(version, item):
        x = [c for c in cv if c["version"] == version and (c["item"] == item or c["item"] == "*")]
        if not x:
            return ""
        if x[0]["item"] == "*":
            return "no Council text in Cellar"
        return "identical" if all(c["identical"] in ("yes", "insertions-only") for c in x) else "differs"

    for v in labels:
        a = ad[v]
        base = {"version": v, "com": a["com"], "proposed": a["proposed"], "spain_request": a["spain_request"],
                "adopted": a["adopted"], "adoption_status": a["status"]}
        for m in [x for x in hm if x["version"] == v]:
            out.append({**base, "kind": "measure", "measure": m["measure"], "number": "", "scope": m["scope"],
                        "name": m["name"], "type": "", "unit": "", "baseline": "", "goal": "", "due": "",
                        "eur_amounts": m["eur_amounts"],
                        "swd_estimated_cost_eur_m": (f"{costs[(v, m['measure'])]:g}" if (v, m["measure"]) in costs else ""),
                        "wording": m["description"],
                        "council_text": council(v, m["measure"]),
                        "scoreboard_status": "", "stated_reason": reason(v, m["measure"].split(".summary")[0] if m["measure"] != "C2.summary" else "C2.I2"),
                        "change_vs_previous": cats(v, m["measure"], "")})
        for r in [x for x in hr if x["version"] == v]:
            s = sb.get((r["measure"], r["number"]))
            st = ""
            if s and v in s["cid_versions_with_same_text"].split(";"):
                st = f"{s['status']} (instalment {s['instalment']}, {s['loans_grants'].lower()}; scoreboard {s['scoreboard_last_refresh']})"
            out.append({**base, "kind": "milestone/target", "measure": r["measure"], "number": r["number"], "scope": r["scope"],
                        "name": r["name"], "type": r["type"], "unit": r["unit"] or r["qual_indicator"],
                        "baseline": r["baseline"], "goal": r["goal"], "due": f"{r['quarter']} {r['year']}",
                        "eur_amounts": r["eur_amounts"], "swd_estimated_cost_eur_m": "",
                        "wording": r["description"],
                        "council_text": council(v, f"{r['measure']} {r['number']}"),
                        "scoreboard_status": st, "stated_reason": reason(v, r["measure"]),
                        "change_vs_previous": cats(v, r["measure"], r["number"])})
    with open(DATA / "version_table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    # ---- headline numbers -------------------------------------------------
    def goal(v, measure, number):
        x = [r for r in hr if r["version"] == v and r["measure"] == measure and r["number"] == number]
        return int(x[0]["goal"].replace(" ", "")) if x else None

    def ico(v):
        x = [m for m in hm if m["version"] == v and m["measure"] == "C2.I7"]
        if not x:
            return None
        import re
        mm = re.search(r"aims at initially providing at least (EUR [\d  ]+)", x[0]["description"])
        return differ.eur_amounts(mm.group(1))[0]

    t31 = {v: goal(v, "C2.I2", "31") for v in labels}
    icov = {v: ico(v) for v in labels}
    first_ico = next(v for v in labels if icov[v])
    core_changes = [d for d in df if d["measure"] in CORE]
    by_version = {}
    for d in core_changes:
        by_version.setdefault(d["to_version"], []).append(f"{d['measure']} {d['number']}".strip())
    cat_counts = {}
    for d in core_changes:
        for c in d["categories"].split(";"):
            cat_counts[c] = cat_counts.get(c, 0) + 1
    S = {
        "n_versions": len(labels),
        "versions_adopted_per_commission_recital": sum(1 for v in labels if ad[v]["status"] == "adopted"),
        "core_measures": ["C2.I2", "C2.I7", "C2.R3", "C2.R7"],
        "core_rows_ever": sorted({f"{r['measure']} {r['number']}" for r in hr if r["scope"] == "core"}),
        "n_core_rows_ever": len({(r["measure"], r["number"]) for r in hr if r["scope"] == "core"}),
        "core_changes_consecutive": len(core_changes),
        "core_changes_by_version": by_version,
        "core_change_categories": cat_counts,
        "versions_with_core_changes": sorted(by_version),
        "target31_by_version": t31,
        "target31_first": t31[labels[0]], "target31_dec2025": t31["v7-2025d"], "target31_last": t31[labels[-1]],
        "target31_change_pct": pct(t31[labels[0]], t31[labels[-1]]),
        "target31_dec2025_change_pct": pct(t31["v6-2025c"], t31["v7-2025d"]),
        "target31_aug2026_change_pct": pct(t31["v8-2026a"], t31["v9-2026b"]),
        "ico_by_version": icov,
        "ico_first": icov[first_ico], "ico_dec2025": icov["v7-2025d"], "ico_last": icov[labels[-1]],
        "ico_change_pct": pct(icov[first_ico], icov[labels[-1]]),
        "ico_dec2025_change_pct": pct(icov["v6-2025c"], icov["v7-2025d"]),
        "ico_aug2026_change_pct": pct(icov["v8-2026a"], icov["v9-2026b"]),
        "swd_cost_eur_m": {m: {v: costs.get((v, m)) for v in labels} for m in ("C2.I2", "C2.I7", "C13.I13")},
        "c2i2_cost_per_target_dwelling_eur": {v: round(costs[(v, "C2.I2")] * 1e6 / t31[v]) for v in labels if (v, "C2.I2") in costs},
        "council_core_items_compared": sum(int(ad[v]["core_housing_items_compared"] or 0) for v in labels),
        "council_core_items_identical": sum(int(ad[v]["core_items_identical_in_council_text"] or 0) for v in labels),
        "council_versions_compared": sum(1 for v in labels if ad[v]["core_housing_items_compared"]),
        "adoption": {v: [ad[v]["adopted"], ad[v]["status"]] for v in labels},
        "scoreboard_last_refresh": next(iter(sb.values()))["scoreboard_last_refresh"],
        "scoreboard_t31": sb[("C2.I2", "31")]["goal"], "scoreboard_t31_status": sb[("C2.I2", "31")]["status"],
        "scoreboard_t31_text_version": sb[("C2.I2", "31")]["cid_versions_with_same_text"],
        "scoreboard_L6_text_version": sb[("C2.I7", "L6")]["cid_versions_with_same_text"],
    }
    # unsigned falls, as the text writes them («85.8% below»)
    S["ico_fall_pct"] = -S["ico_change_pct"]
    S["ico_dec2025_fall_from_first_pct"] = -pct(icov[first_ico], icov["v7-2025d"])
    for k in ("first", "dec2025", "last"):
        if S[f"ico_{k}"] % 10**6 == 0:
            S[f"ico_{k}_eur_m"] = S[f"ico_{k}"] // 10**6
    # dates of the versions, the timeline and the scoreboard, written as the text writes them
    vt = {r["version"]: r for r in rows("adoption.csv")}
    tl = rows("timeline.csv")
    council = re.search(r"ST 12355/26 INIT \((\d{4}-\d{2}-\d{2})\)", vt["v9-2026b"]["council_docs"]).group(1)
    sbd = datetime.datetime.strptime(S["scoreboard_last_refresh"], "%d/%m/%Y").date().isoformat()
    t31_due = [r["due"] for r in rows("version_table.csv") if r["version"] == labels[-1] and r["measure"] == "C2.I2" and r["number"] == "31"]
    S["dates"] = {
        "first_month": month(vt[labels[0]]["proposed"]), "sep2025_month": month(vt["v6-2025c"]["proposed"]),
        "ico_first_year": first_ico.split("-")[1][:4], "ico_first_adopted_month": month(vt[first_ico]["adopted"]),
        "dec2025_month": month(vt["v7-2025d"]["proposed"]), "dec2025_proposed": day(vt["v7-2025d"]["proposed"]),
        "dec2025_adopted": day(vt["v7-2025d"]["adopted"]), "dec2025_adopted_month": month(vt["v7-2025d"]["adopted"]),
        "aug2026_month": month(vt["v9-2026b"]["proposed"]), "aug2026_proposed": day(vt["v9-2026b"]["proposed"]),
        "aug2026_council_text": day(council), "aug2026_adopted_reported": day(vt["v9-2026b"]["adopted"]),
        "gov_statement": day(timeline(tl, "Government (Minister of Economy before the Joint Committee for the EU)")),
        "last_payment_request": day(timeline(tl, "Government: seventh and last payment request")),
        "scoreboard_refresh": day(sbd),
        "road_to_2026": day(timeline(tl, "Commission, NextGenerationEU – The road to 2026")),
        "dec2025_spain_request": day(timeline(tl, "Spain's request behind COM(2025) 794")),
        "dec2025_council_of_ministers": day(timeline(tl, "Government: approval of the «Adenda de Simplificación»")),
        "affordable_housing_plan": day(timeline(tl, "European Affordable Housing Plan, COM(2025) 1025")),
        "aug2026_spain_request": day(timeline(tl, "Spain's request behind COM(2026) 435")),
        "target31_due": t31_due[0], "rrf_cutoff": TEXT["rrf_cutoff"],
    }
    S["target31_number"] = "31"
    S["text"] = {k: v for k, v in TEXT.items() if k != "rrf_cutoff"}
    # the annex-wide base rate (baseline.py), with the shares at full precision
    B = json.load(open(DATA / "baseline_summary.json", encoding="utf-8"))
    dm, dt = B["v6-2025c->v7-2025d"]["measures"], B["v6-2025c->v7-2025d"]["milestones_targets"]
    at = B["v8-2026a->v9-2026b"]["milestones_targets"]
    S["baseline"] = {
        "threshold_share_of_words_lost": 0.3,  # baseline.py: a text «lost more than 30%» when new/old < 0.7
        "dec2025_measures": dm["n"], "dec2025_measures_lost": dm["lost_more_than_30pct"],
        "dec2025_measures_share_lost": dm["lost_more_than_30pct"] / dm["n"],
        "housing_measures": len(dm["housing_ratios"]),
        "dec2025_housing_measures_lost": sum(1 for r in dm["housing_ratios"].values() if r < 0.7),
        "dec2025_items": dt["n"], "dec2025_target31_rank_from_most_cut": dt["housing_rank_from_most_cut"]["C2.I2 31"],
        "aug2026_items": at["n"], "aug2026_items_lost": at["lost_more_than_30pct"],
        "aug2026_housing_items_lost": sum(1 for r in at["housing_ratios"].values() if r < 0.7),
    }
    json.dump(S, open(DATA / "summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for k, v in S.items():
        print(k, v)


if __name__ == "__main__":
    main()
