"""S12 step 5 (added 2026-10-05, after the freeze): the descriptive numbers the text quotes, into data/summary.json.

The registered results in data/summary.json are written by the frozen scripts/analyse.py and are not
touched: this script appends one block, `descriptive`, at the end of the file, and replaces only that
block when it is run again. Everything above it stays byte for byte what analyse.py wrote (checked
below). Nothing here is a registered test.

Reads the locked series file (data/raw/, as build.py does), data/districts.csv, data/dq_summary.json,
data/h5_years.csv, data/review_checks.json, data/dq1_district_vs_province.csv and data/summary.json.
Dates and the two figures of the CGPJ's activity note are constants, with their source beside them.
"""
from __future__ import annotations

import csv
import json
from datetime import date, timedelta

from s12lib import DATA, RAW, SERIES_SHEETS, load_json, read_series, write_json

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")


def day_month(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"


def long_date(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def rows(name: str) -> list[dict]:
    with open(DATA / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def whole(x: float) -> int:
    assert float(x).is_integer(), x
    return int(x)


def main() -> None:
    path = DATA / "summary.json"
    text = path.read_text(encoding="utf-8")
    summary = json.loads(text)
    summary.pop("descriptive", None)
    frozen = dict(summary)

    series_file = RAW / "series_provincias_1T2026_revisado.xlsx"
    level = {sid: {q: whole(v) for q, v in read_series(series_file, SERIES_SHEETS[sid])["TOTAL"].items()}
             for sid in ("P-TOT", "SC-REC", "SC-POS")}
    ptot = level["P-TOT"]
    quarters = sorted(ptot)
    q1 = {int(q[:4]): v for q, v in ptot.items() if q.endswith("Q1")}
    earlier_q1 = {y: v for y, v in q1.items() if y < 2026}
    others = {q: v for q, v in ptot.items() if q not in ("2026Q1", "2020Q2")}

    review = load_json(DATA / "review_checks.json")
    dq = load_json(DATA / "dq_summary.json")
    h5_2024 = next(r for r in rows("h5_years.csv") if r["year"] == "2024")
    districts = rows("districts.csv")
    dq1 = [r for r in rows("dq1_district_vs_province.csv") if r["year"] == "2025" and float(r["difference"]) != 0]
    vintage = next(v for v in dq["DQ2"]["national_revisions"] if v["quarter"] == "2025Q3" and v["series"] == "P-TOT")
    rent = None
    for k, v in dq.items():
        if isinstance(v, dict) and "q1_2026_type_split" in v:
            rent = v["q1_2026_type_split"]
    assert rent is not None, "q1_2026_type_split not found in dq_summary.json"
    madrid = review["province_detail"]["MADRID"]["SC-POS"]
    ribadavia = next(r for r in districts if r["district"] == "RIBADAVIA")
    outlier = next(o for o in dq["DQ1"]["outliers"] if o["district"] == "RIBADAVIA" and o["year"] == 2025)

    # Suspension of evictions (RDL 11/2020 art. 1; paper §2.3): in force 1-27 January and 5-27 February 2026.
    q1_days = [date(2026, 1, 1) + timedelta(d) for d in range((date(2026, 4, 1) - date(2026, 1, 1)).days)]
    lapse1, restored, lapse2 = date(2026, 1, 28), date(2026, 2, 5), date(2026, 2, 28)
    in_force = [d for d in q1_days if d < lapse1 or restored <= d < lapse2]

    descriptive = {
        "note": ("Added 2026-10-05 by scripts/summarize.py, after the freeze: descriptive figures quoted by "
                 "the text. Not registered results; the keys above this block are analyse.py's, unchanged."),
        "series_first_quarter": quarters[0],
        "series_first_year": int(quarters[0][:4]),
        "series_quarters": len(quarters),
        "latest_quarter": quarters[-1],
        "national_level": level,
        "q1_level_P-TOT": {str(y): v for y, v in sorted(q1.items())},
        "lowest_q1_before_2026": min(earlier_q1.values()),
        "lowest_q1_before_2026_year": min(earlier_q1, key=earlier_q1.get),
        "lowest_quarter_level": min(ptot.values()),
        "lowest_quarter": min(ptot, key=ptot.get),
        "quarters_below_2026Q1": sum(v < ptot["2026Q1"] for v in ptot.values()),
        "lowest_quarter_excl_2020Q2_2026Q1": min(others.values()),
        "lowest_quarter_excl_2020Q2_2026Q1_label": min(others, key=others.get),
        "fall_2026Q1": -summary["national_yoy"]["P-TOT"]["2026Q1"],
        "out_of_sample_quarter": "Q2-2026",
        "madrid_sc_pos": {q: whole(madrid[q]) for q in ("2024Q4", "2025Q4", "2026Q1")},
        "S3_registered": {k: review["S3_registered"][k] for k in ("b", "se_hc3", "n", "p_one_sided", "p_perm")},
        "q1_2026_only_slopes": {t: review["delta_g_split"][t]["g_2026Q1"] for t in ("H2", "H3")},
        "placebo_2025Q4_P_TOT": review["placebo_2025Q4_exploratory"]["P-TOT"],
        "sc_rec_yoy_pooled_2025Q4_2026Q1": review["national_yoy_pooled_Q4_Q1"]["SC-REC"],
        "h5_rho1_2024": float(h5_2024["rho1"]),
        "dq1_2025": {"provinces_differing": len({r["province"] for r in dq1}),
                     "provinces": len({r["series_province"] for r in districts})},
        "q3_2025_estimated": {"districts": dq["DQ3"]["2025Q3"]["districts"],
                              "phase1": dq["DQ3"]["2025Q3"]["by_phase"]["1"]},
        # districts the CGPJ lists without data for Q1-2026, and how many are phase 3 (closing review)
        "q1_2026_no_data": {"districts": dq["DQ3"]["2026Q1"]["districts"],
                            "phase3": dq["DQ3"]["2026Q1"]["by_phase"]["3"],
                            "phases": sorted(int(p) for p, k in dq["DQ3"]["2026Q1"]["by_phase"].items() if k)},
        "p_tot_2025Q3_vintages": {"first": whole(vintage["first_vintage"]), "latest": whole(vintage["latest_vintage"])},
        "q1_2026_rent": {"release_sheet": whole(rent["P-LAU"]["release_provincias_sheet"]),
                         "series": whole(rent["P-LAU"]["series_file"]),
                         "madrid_non_mortgage": whole(rent["P-TOT"]["madrid_series"] - rent["P-HIP"]["madrid_series"]),
                         "madrid_rent_release": whole(rent["P-LAU"]["madrid_release"]),
                         "madrid_rent_series": whole(rent["P-LAU"]["madrid_series"])},
        "ribadavia": {"y2025": int(ribadavia["tot_2025"]), "max_earlier": whole(outlier["max_earlier"])},
        "phase_districts": {**{p: dq["DQ6"]["phase_counts"][p] for p in ("1", "2", "3")}, "total": len(districts)},
        "phase_dates": {"1": long_date(date(2025, 7, 1)), "2": day_month(date(2025, 10, 1)),
                        "3": day_month(date(2025, 12, 31))},  # Organic Law 1/2025, DT 1.ª
        "pooled_parameters_at_bound_n": len(summary["pooled_parameters_at_bound"]["used"]),
        # The CGPJ's activity note for Q1-2026, quoted in paper §6: «un 13,7 % negativo», civil «un 22,3 % menos».
        "cgpj_note_q1_2026": {"resolved_all": -0.137, "resolved_civil": -0.223},
        "suspension_q1_2026": {"quarter": "Q1-2026", "days": len(q1_days), "days_in_force": len(in_force),
                               "lapse1_start": day_month(lapse1), "lapse1_end": day_month(restored - timedelta(1)),
                               "final_lapse": day_month(lapse2)},
        "dates": {"protocol_registered": long_date(date(2026, 10, 4)),   # commit ee3ef6c
                  "q2_2026_release": long_date(date(2026, 10, 16)),      # CGPJ release calendar
                  "pre_filing_negotiation_from": "April 2025"},          # LO 1/2025, in force 3 April 2025
    }
    summary["descriptive"] = descriptive
    write_json(path, summary)

    # The frozen part must be what analyse.py wrote: re-serialise it alone and compare.
    after = path.read_text(encoding="utf-8")
    probe = DATA.parent / "work" / "summary_frozen_probe.json"
    write_json(probe, frozen)
    head = probe.read_text(encoding="utf-8")
    probe.unlink()
    assert after.startswith(head[:-3]), "the frozen part of summary.json changed"
    print(f"data/summary.json: descriptive block written ({len(descriptive)} keys); frozen keys unchanged")


if __name__ == "__main__":
    main()
