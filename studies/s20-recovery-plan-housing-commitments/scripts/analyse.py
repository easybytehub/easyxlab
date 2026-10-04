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
import csv, json
from s20lib import DATA, VERSIONS
import differ

CORE = ("C2.I2", "C2.I7", "C2.R3", "C2.R7", "C2.summary")


def rows(name):
    return list(csv.DictReader(open(DATA / name, encoding="utf-8")))


def pct(a, b):
    """Percentage change, rounded half away from zero to one decimal."""
    from decimal import Decimal, ROUND_HALF_UP
    return float((Decimal(100) * (Decimal(b) - Decimal(a)) / Decimal(a)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


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
    json.dump(S, open(DATA / "summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for k, v in S.items():
        print(k, v)


if __name__ == "__main__":
    main()
