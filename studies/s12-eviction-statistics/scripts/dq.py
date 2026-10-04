"""S12 step 2: data-quality checks DQ1-DQ8, DQ10, DQ11 (PROTOCOL.md §9). DQ9 is written by analyse.py.

Writes data/dq_*.csv and data/dq_summary.json (aggregates only).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

from s12lib import (load_json, CEUTA_MELILLA_HOST, DATA, PRESS_Q1_2026, RAW, RELEASES, TSJ_OF_PROVINCE, TSJ_SHEETS, WORK,
                    canon, old_court_types, q_from_cgpj, q_index, q_label, read_release_provinces,
                    read_tsj_release_block, province_key, write_csv, write_json)

TYPES = ("P-TOT", "P-HIP", "P-LAU", "P-OTR")
D1KEY = {"P-TOT": "tot", "P-HIP": "hip", "P-LAU": "lau", "P-OTR": "otr"}
ICAM_PHASE2 = ["Fuengirola", "Marbella", "Torremolinos", "San Bartolomé de Tirajana", "Telde", "Arona",
               "San Cristóbal de La Laguna", "Badalona", "L'Hospitalet de Llobregat", "Alcobendas",
               "Fuenlabrada", "Torrejón de Ardoz", "Denia", "Torrent", "Inca", "Manacor"]


def quarters(a, b):
    return [q_label(i) for i in range(q_index(a), q_index(b) + 1)]


def main():
    P = load_json(WORK / "panel.json")
    S = P["province_series"]
    districts = P["districts"]
    summary = {}

    # DQ1 ---------------------------------------------------------------------------------
    import openpyxl  # noqa: F401  (the D1 detail already sits in panel.json)
    d1_prov = defaultdict(lambda: defaultdict(float))
    d1_prov_own = defaultdict(lambda: defaultdict(float))
    from s12lib import read_district_file
    d1 = read_district_file()
    by_name = {r["district"]: r for r in districts}
    for name, rec in d1.items():
        r = by_name[name]
        for y, vals in rec.items():
            for sid, k in D1KEY.items():
                v = vals.get(k) or 0.0
                d1_prov[(r["series_province"], y)][sid] += v
                d1_prov_own[(r["province"], y)][sid] += v
    dq1 = []
    for (p, y), vals in sorted(d1_prov.items()):
        for sid in TYPES:
            ser = sum((S[sid][p].get(f"{y}Q{k}") or 0.0) for k in range(1, 5))
            diff = vals[sid] - ser
            if abs(diff) > 0.5:
                dq1.append({"province": p, "year": y, "series": sid, "district_file": vals[sid],
                            "province_series": ser, "difference": diff})
    nat = []
    for y in range(2013, 2026):
        for sid in TYPES:
            a = sum(v[sid] for (p, yy), v in d1_prov.items() if yy == y)
            b = sum((S[sid]["TOTAL"].get(f"{y}Q{k}") or 0.0) for k in range(1, 5))
            nat.append({"year": y, "series": sid, "district_file": a, "province_series_total": b, "difference": a - b})
    write_csv(DATA / "dq1_district_vs_province.csv", dq1)
    write_csv(DATA / "dq1_national_by_year.csv", nat)
    write_csv(DATA / "dq1_outliers.csv", P["dq1_outliers"])
    # where are Ceuta and Melilla counted? compare Cadiz/Malaga with and without them
    cm = {}
    for host, extra in (("CADIZ", "CEUTA"), ("MALAGA", "MELILLA")):
        diffs_with = sum(abs(d1_prov[(host, y)]["P-TOT"] - sum(S["P-TOT"][host][f"{y}Q{k}"] or 0 for k in range(1, 5)))
                         for y in range(2013, 2025))
        diffs_without = sum(abs(d1_prov_own[(host, y)]["P-TOT"] - sum(S["P-TOT"][host][f"{y}Q{k}"] or 0 for k in range(1, 5)))
                            for y in range(2013, 2025))
        cm[extra] = {"host": host, "abs_diff_2013_2024_if_included": diffs_with,
                     "abs_diff_2013_2024_if_excluded": diffs_without}
    summary["DQ1"] = {
        "province_year_type_differences": len(dq1),
        "years_with_differences": sorted({r["year"] for r in dq1}),
        "national_P_TOT_difference_by_year": {r["year"]: r["difference"] for r in nat if r["series"] == "P-TOT"},
        "national_P_LAU_difference_by_year": {r["year"]: r["difference"] for r in nat if r["series"] == "P-LAU"},
        "outliers": P["dq1_outliers"],
        "ceuta_melilla": cm,
    }

    # DQ2: first vintage (release 'Provincias') vs latest vintage (series file) -----------
    dq2 = []
    first = {}
    for q, fname in RELEASES:
        rp = read_release_provinces(RAW / fname)
        first[q] = rp
        for name, vals in rp.items():
            p = "TOTAL" if name.upper() == "TOTAL" else province_key(name)
            for sid, v in vals.items():
                if sid not in S or v is None:
                    continue
                latest = S[sid][p].get(q)
                if latest is None:
                    continue
                d = latest - v
                rel = d / v if v else (0.0 if d == 0 else float("inf"))
                dq2.append({"quarter": q, "province": p, "series": sid, "first_vintage": v,
                            "latest_vintage": latest, "revision": d, "relative": rel,
                            "listed": int(abs(rel) >= 0.05 and abs(d) >= 10)})
    write_csv(DATA / "dq2_vintages.csv", [r for r in dq2 if r["revision"] != 0])
    summary["DQ2"] = {
        "province_quarter_series_revised": sum(1 for r in dq2 if r["revision"] != 0 and r["province"] != "TOTAL"),
        "listed_(>=5%_and_>=10)": sum(1 for r in dq2 if r["listed"] and r["province"] != "TOTAL"),
        "national_revisions": [{k: r[k] for k in ("quarter", "series", "first_vintage", "latest_vintage", "revision")}
                               for r in dq2 if r["province"] == "TOTAL" and r["revision"] != 0],
    }

    # DQ3: flags as published ---------------------------------------------------------------
    from s12lib import read_csv
    nn = read_csv(DATA / "cgpj_notes.csv")
    summary["DQ3"] = {
        q: {"districts": sum(1 for n in nn if n["release"] == q),
            "by_phase": {ph: sum(1 for n in nn if n["release"] == q and n["phase"] == ph) for ph in ("1", "2", "3")},
            "provinces": sorted({n["series_province"] for n in nn if n["release"] == q})}
        for q in ("2025Q3", "2025Q4", "2026Q1")}

    # DQ4: identities ---------------------------------------------------------------------
    T = P["tsj_series"]
    fails, checks = [], 0
    provs = [p for p in S["P-TOT"] if p != "TOTAL"]
    for q in quarters("2013Q1", "2026Q1"):
        for p in provs + ["TOTAL"]:
            vals = [S[s][p].get(q) for s in TYPES]
            if None in vals:
                continue
            checks += 1
            if abs(vals[0] - sum(vals[1:])) > 0.5:
                fails.append({"check": "total=hip+lau+otr", "unit": p, "quarter": q,
                              "lhs": vals[0], "rhs": sum(vals[1:])})
        for sid in TYPES + ("SC-REC", "SC-POS"):
            s = sum((S[sid][p].get(q) or 0.0) for p in provs)
            tot = S[sid]["TOTAL"].get(q)
            if tot is None:
                continue
            checks += 1
            if abs(s - tot) > 0.5:
                fails.append({"check": "sum provinces=TOTAL", "unit": sid, "quarter": q, "lhs": s, "rhs": tot})
            tsj_sum = defaultdict(float)
            for p in provs:
                tsj_sum[TSJ_OF_PROVINCE[p]] += S[sid][p].get(q) or 0.0
            for tname, tv in T.get(sid, {}).items():
                if tname.upper() == "TOTAL" or tv.get(q) is None:
                    continue
                checks += 1
                if abs(tsj_sum[tname] - tv[q]) > 0.5:
                    fails.append({"check": "sum provinces=TSJ", "unit": f"{sid} {tname}", "quarter": q,
                                  "lhs": tsj_sum[tname], "rhs": tv[q]})
    press = {}
    for sid, (level, change) in PRESS_Q1_2026.items():
        v, v0 = S[sid]["TOTAL"]["2026Q1"], S[sid]["TOTAL"]["2025Q1"]
        press[sid] = {"published": level, "series": v, "published_change": change,
                      "series_change": round(v / v0 - 1, 4), "match": v == level and abs((v / v0 - 1) - change) < 0.0006}
    # the type split of Q1-2026 in the release's own 'Provincias' sheet
    rel = first["2026Q1"]
    split = {sid: {"release_provincias_sheet": rel["TOTAL"][sid], "series_file": S[sid]["TOTAL"]["2026Q1"],
                   "madrid_release": rel["MADRID"][sid], "madrid_series": S[sid]["MADRID"]["2026Q1"]}
             for sid in TYPES}
    write_csv(DATA / "dq4_identity_failures.csv", fails)
    province_quarters = len(provs) * len(quarters("2013Q1", "2026Q1"))
    pq_fail = len({(f["unit"], f["quarter"]) for f in fails if f["check"] == "total=hip+lau+otr" and f["unit"] != "TOTAL"})
    summary["DQ4"] = {"checks": checks, "failures": len(fails),
                      "province_quarters_failing_type_identity": pq_fail,
                      "share_province_quarters_failing": pq_fail / province_quarters,
                      "press_figures": press, "q1_2026_type_split": split}

    # DQ5: labels of the TSJ quarter blocks in each release ---------------------------------
    dq5 = []
    for q, fname in RELEASES:
        for sid, sh in TSJ_SHEETS.items():
            if sid.startswith("SC"):
                continue
            block, labels = read_tsj_release_block(RAW / fname, sh)
            n = len(labels)
            expected = quarters(q_label(q_index(q) - n + 1), q)
            for pos, (lab, exp) in enumerate(zip(labels, expected)):
                if q_from_cgpj(lab) != exp or "*" in str(lab):
                    dq5.append({"release": q, "sheet": sh.strip(), "position": pos + 1, "label": lab,
                                "expected": exp, "issue": "label differs" if q_from_cgpj(lab) != exp else "starred"})
    write_csv(DATA / "dq5_labels.csv", dq5, ["release", "sheet", "position", "label", "expected", "issue"])
    summary["DQ5"] = dq5

    # DQ6 / DQ7: phases -----------------------------------------------------------------------
    m = P["matching"]
    bad_types = []
    mixed = re.compile(r"(1\s*[Aª]\.?\s*INS|PRIMERA INSTANCIA).*E\s*INSTRUC", re.I)
    first = re.compile(r"(1\s*[Aª]\.?\s*INST|PRIMERA INSTANCIA)", re.I)
    instr = re.compile(r"INSTRUCCI", re.I)
    viol = re.compile(r"VIOLENCIA", re.I)
    for ph in (1, 2):
        for seat, names in old_court_types(ph).items():
            for n in names:
                if not re.match(r"^JDO", n, re.I):
                    continue
                ok = (mixed.search(n) or viol.search(n)) if ph == 1 else \
                     (first.search(n) or instr.search(n) or viol.search(n)) and not mixed.search(n)
                note = "pilot tribunal de instancia before the reform" if re.search(r"PILOTO", n, re.I) else ""
                if not ok or note:
                    bad_types.append({"phase": ph, "seat": f"{seat[1]} ({seat[0]})", "former_court": n,
                                      "note": note})
    bad_types.sort(key=lambda b: (b["phase"], b["seat"], b["former_court"]))
    write_csv(DATA / "dq6_court_types.csv", bad_types, ["phase", "seat", "former_court", "note"])
    phase2 = sorted(r["district"] for r in districts if r["phase"] == 2)
    icam = sorted(canon(x) for x in ICAM_PHASE2)
    xls2 = sorted(r["district_key"] for r in districts if r["phase"] == 2)
    summary["DQ6"] = {"phase_counts": m["phase_counts"], "expected": {"1": 315, "2": 16, "3": 100},
                      "unmatched_district_file": m["unmatched_d1"], "seat_problems": m["seat_problems"],
                      "mju_phase3_seats_in_remainder": m["mju_phase3_seats"],
                      "former_courts_outside_DT1_types": sum(1 for b in bad_types if not b["note"]),
                      "pilot_seats": sorted({b["seat"] for b in bad_types if b["note"]})}
    summary["DQ7"] = {"phase2_xls": phase2, "matches_madrid_bar_list": icam == sorted(canon(x) for x in
                      [r["district"] for r in districts if r["phase"] == 2]) or icam == xls2}

    # DQ8: seasonality ------------------------------------------------------------------------
    nat = S["P-TOT"]["TOTAL"]
    dq8 = []
    for y in range(2022, 2026):
        dq8.append({"year": y, "Q3_over_Q2": nat[f"{y}Q3"] / nat[f"{y}Q2"],
                    "Q1_next_over_Q4": nat[f"{y + 1}Q1"] / nat[f"{y}Q4"] if f"{y + 1}Q1" in nat else None})
    write_csv(DATA / "dq8_seasonality.csv", dq8)
    summary["DQ8"] = dq8

    # DQ10: common-service coverage ------------------------------------------------------------
    qs = quarters("2024Q1", "2026Q1")
    nocov = [p for p in provs if any((S["SC-REC"][p].get(q) or 0) <= 0 for q in qs)]
    summary["DQ10"] = {"provinces_without_SC_receipts_in_some_quarter_2024Q1_2026Q1": nocov}

    # DQ11: the record-low claim, literally ----------------------------------------------------
    hist = {q: v for q, v in nat.items() if "2013Q1" <= q <= "2025Q4" and v is not None}
    qmin = min(hist, key=hist.get)
    q1 = {q: v for q, v in hist.items() if q.endswith("Q1")}
    q1min = min(q1, key=q1.get)
    lower = sorted(q for q, v in hist.items() if v <= nat["2026Q1"])
    summary["DQ11"] = {"q1_2026": nat["2026Q1"], "previous_minimum_quarter": qmin, "previous_minimum": hist[qmin],
                       "previous_minimum_first_quarter": q1min, "previous_minimum_first_quarter_value": q1[q1min],
                       "earlier_quarters_at_or_below_q1_2026": lower}

    # gate for the confirmatory tests (PROTOCOL.md §10) ------------------------------------------
    unmatched = len(m["unmatched_d1"])
    summary["gate"] = {"unmatched_districts": unmatched, "unmatched_limit": 22,
                       "type_identity_failure_share": summary["DQ4"]["share_province_quarters_failing"],
                       "failure_share_limit": 0.10,
                       "confirmatory_tests_allowed": unmatched <= 22 and summary["DQ4"]["share_province_quarters_failing"] <= 0.10}
    write_json(DATA / "dq_summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("gate", "DQ6", "DQ11")}, ensure_ascii=False, default=str)[:1500])


if __name__ == "__main__":
    main()
