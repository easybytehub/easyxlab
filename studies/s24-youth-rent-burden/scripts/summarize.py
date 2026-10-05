#!/usr/bin/env python3
"""S24: collect the headline numbers from data/*.csv into data/summary.json (read by check_headlines.py)."""
from __future__ import annotations

import csv
import json
import math
import sys

from s24lib import D


def load(name):
    with open(D / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def one(rows, **kw):
    out = [r for r in rows if all(str(r[k]) == str(v) for k, v in kw.items())]
    if len(out) != 1:
        raise SystemExit(f"expected one row for {kw}, got {len(out)}")
    return out[0]


def F(x):
    return float(x)


def main():
    S = {}
    yb = load("young_burden.csv")
    boot = load("bootstrap.csv")
    for band in ("18-34", "18-29"):
        for y in (2019, 2021, 2023, 2025):
            r = one(yb, year=y, age_band=band, unit="persons_emancipated", tenure="market_rent")
            S[f"young_tenants_{band}_{y}"] = {k: (F(r[k]) if k not in ("n", "households", "pop") else int(r[k]))
                                             for k in ("n", "households", "pop", "median_rent", "median_income",
                                                       "median_rent_to_income_pct", "median_burden_pct", "overburden_pct")}
        r = one(yb, year=2025, age_band=band, unit="persons_emancipated_age_end_of_income_year", tenure="market_rent")
        S[f"young_tenants_{band}_2025_age_end"] = {"overburden_pct": F(r["overburden_pct"]), "n": int(r["n"])}
        r = one(yb, year=2025, age_band=band, unit="households_young_reference_person", tenure="market_rent")
        S[f"young_ref_households_{band}_2025"] = {"overburden_pct": F(r["overburden_pct"]), "n": int(r["households"]),
                                                  "median_burden_pct": F(r["median_burden_pct"])}
    B = {(r["year"], r["estimate"]): r for r in boot}
    S["bootstrap"] = {f"{y}_{e}": {k: F(B[(y, e)][k]) for k in ("point", "se", "ci95_low", "ci95_high")}
                      for (y, e) in B}
    a, b = B[("2021", "young_tenants_18_34_overburden")], B[("2025", "young_tenants_18_34_overburden")]
    d = F(b["point"]) - F(a["point"]); se = math.hypot(F(a["se"]), F(b["se"]))
    S["young_18_34_change_2021_2025"] = {"pp": round(d, 1), "ci95_low": round(d - 1.96 * se, 1), "ci95_high": round(d + 1.96 * se, 1)}
    for key, est in (("market_tenants", "market_tenants_overburden"), ("tenants_35_49", "tenants_35_49_overburden"),
                     ("tenants_50_64", "tenants_50_64_overburden"), ("young_18_29", "young_tenants_18_29_overburden")):
        a, b = B[("2021", est)], B[("2025", est)]
        d = F(b["point"]) - F(a["point"]); se = math.hypot(F(a["se"]), F(b["se"]))
        S[f"{key}_change_2021_2025"] = {"pp": round(d, 1), "se": round(se, 1), "ci95_low": round(d - 1.96 * se, 1),
                                        "ci95_high": round(d + 1.96 * se, 1)}
    S["young_18_34_change_2021_2025"]["se"] = round(math.hypot(F(B[("2021", "young_tenants_18_34_overburden")]["se"]),
                                                               F(B[("2025", "young_tenants_18_34_overburden")]["se"])), 1)
    dy, d35 = S["young_18_34_change_2021_2025"], S["tenants_35_49_change_2021_2025"]
    se = math.hypot(dy["se"], d35["se"])
    S["young_minus_35_49_change"] = {"pp": round(dy["pp"] - d35["pp"], 1), "se": round(se, 1),
                                     "ci95_low": round(dy["pp"] - d35["pp"] - 1.96 * se, 1), "ci95_high": round(dy["pp"] - d35["pp"] + 1.96 * se, 1)}

    rep = load("eurostat_replication.csv")
    c = [r for r in rep if r["table"] == "ilc_lvho07c" and r["diff"] != ""]
    a = [r for r in rep if r["table"] == "ilc_lvho07a" and r["diff"] != ""]
    ai = [r for r in rep if r["table"] == "ilc_lvho07a (age at interview)" and r["diff"] != ""]
    S["replication"] = {"lvho07c_max_abs_diff": max(abs(F(r["diff"])) for r in c), "lvho07c_cells": len(c),
                        "lvho07c_exact": sum(1 for r in c if abs(F(r["diff"])) < 0.05),
                        "lvho07a_exact": sum(1 for r in a if abs(F(r["diff"])) < 0.05),
                        "lvho07a_interview_age_max_abs_diff": max(abs(F(r["diff"])) for r in ai),
                        "lvho07a_max_abs_diff": max(abs(F(r["diff"])) for r in a), "lvho07a_cells": len(a),
                        "rent_mkt_2025_ours": F(one(rep, year=2025, group="RENT_MKT")["ours"]),
                        "rent_mkt_2025_eurostat": F(one(rep, year=2025, group="RENT_MKT")["eurostat"]),
                        "rent_mkt_2021_ours": F(one(rep, year=2021, group="RENT_MKT")["ours"]),
                        "rent_mkt_2021_eurostat": F(one(rep, year=2021, group="RENT_MKT")["eurostat"]),
                        "rent_mkt_2019_eurostat": F(one(rep, year=2019, group="RENT_MKT")["eurostat"])}
    lwp = load("living_with_parents.csv")
    def lw(y, band, d="interview"):
        return F(one(lwp, year=y, age_band=band, age_definition=d)["living_with_parent_pct"])
    S["living_with_parents"] = {"18-34_2025": lw(2025, "18-34"), "18-34_2021": lw(2021, "18-34"), "18-34_2019": lw(2019, "18-34"),
                                "18-34_2008": lw(2008, "18-34"), "18-34_2025_age_end": lw(2025, "18-34", "end_of_income_year"),
                                "eurostat_18-34_2025": F(one(lwp, year=2025, age_band="18-34", age_definition="interview")["eurostat_ilc_lvps08"]),
                                "16-29_emancipated_2025": round(100 - lw(2025, "16-29"), 2),
                                "16-29_emancipated_2024": round(100 - lw(2024, "16-29"), 2),
                                "16-29_emancipated_2025_age_end": round(100 - lw(2025, "16-29", "end_of_income_year"), 2),
                                "16-29_emancipated_2024_age_end": round(100 - lw(2024, "16-29", "end_of_income_year"), 2),
                                "16-29_min_year_interview": min(range(2004, 2026), key=lambda y: 100 - lw(y, "16-29")),
                                "16-29_min_year_age_end": min(range(2004, 2026), key=lambda y: 100 - lw(y, "16-29", "end_of_income_year"))}
    lv = [r for r in lwp if r["age_band"] == "18-34" and r["age_definition"] == "interview" and r["eurostat_ilc_lvps08"] != ""
          and int(r["year"]) >= 2008]                      # base-2013 files; 2004-2007 (base 2004) differ by up to 7 points
    S["living_with_parents"]["lvps08_years"] = len(lv)
    S["living_with_parents"]["lvps08_exact"] = sum(1 for r in lv if round(F(r["living_with_parent_pct"]), 1) == F(r["eurostat_ilc_lvps08"]))
    S["living_with_parents"]["lvps08_max_abs_diff"] = round(max(abs(F(r["living_with_parent_pct"]) - F(r["eurostat_ilc_lvps08"])) for r in lv), 2)
    dec = load("decomposition.csv")
    def dd(**kw):
        r = one(dec, **kw)
        return {k: (F(r[k]) if r[k] != "" else None) for k in ("overburden_from", "overburden_to", "change_pp", "composition_pp",
                                                              "within_pp", "composition_share_of_change_pct")}
    S["decomposition"] = {
        "young_18_34_2021_2025": dd(age_band="18-34", **{"from": 2021, "to": 2025}, cells="income_group"),
        "young_18_34_2021_2025_age": dd(age_band="18-34", **{"from": 2021, "to": 2025}, cells="income_group_x_age"),
        "young_18_34_2019_2025": dd(age_band="18-34", **{"from": 2019, "to": 2025}, cells="income_group"),
        "young_18_29_2021_2025": dd(age_band="18-29", **{"from": 2021, "to": 2025}, cells="income_group"),
        "all_by_age_2021_2025": dd(age_band="all_ages", **{"from": 2021, "to": 2025}, cells="age_group_of_market_tenants"),
        "all_by_quintile_2021_2025": dd(age_band="all_ages", **{"from": 2021, "to": 2025}, cells="national_income_quintile_of_market_tenants"),
        "all_by_quintile_2019_2025": dd(age_band="all_ages", **{"from": 2019, "to": 2025}, cells="national_income_quintile_of_market_tenants"),
    }
    for g in ("18-34_emancipated", "35-49", "50-64", "65_plus"):
        S["decomposition"][f"within_{g}_2021_2025"] = dd(age_band="all_ages", **{"from": 2021, "to": 2025}, cells=f"within_contribution:{g}")
    bd = load("selection_bound.csv")
    S["bound"] = {}
    for r in bd:
        if r["age_band"] == "18-29" and r["from"] == "2021":
            key = "tenancy_rate_all_ob" if "current tenancy rate, all" in r["scenario"] else (
                "all_rent_all_ob" if "all extra stayers" in r["scenario"] else None)
            if key:
                S["bound"][f"18-29_2021_{key}"] = {"young_share_of_fall_explained_pct": F(r["young_share_of_fall_explained_pct"])}
        if r["age_band"] == "18-34" and r["from"] in ("2021", "2019"):
            key = {"channel bound: extra stayers rent at the current tenancy rate, all overburdened": "tenancy_rate_all_ob",
                   "channel bound: all extra stayers rent, all overburdened": "all_rent_all_ob"}.get(
                r["scenario"], "low_income_final" if "final year" in r["scenario"] else "low_income_base")
            S["bound"][f"{r['from']}_{key}"] = {k: F(r[k]) for k in ("living_with_parents_from_pct", "living_with_parents_to_pct",
                                                                     "extra_stayers", "added_tenants", "young_counterfactual",
                                                                     "young_share_of_fall_explained_pct", "all_tenants_counterfactual",
                                                                     "all_share_of_fall_explained_pct")}
    dr = load("drivers.csv")
    S["drivers"] = {r["year"]: {k: F(v) for k, v in r.items() if k not in ("year", "group") and v != ""} for r in dr}
    cf = load("income_counterfactual.csv")
    S["income_counterfactual"] = {}
    for r in cf:
        key = r["from"].replace(" ", "_") if r["from"] != "lag" else "lag_" + r["median_housing_cost_growth_pct"]
        S["income_counterfactual"][key] = {k: F(v) for k, v in r.items() if k not in ("from", "to", "note") and v != ""}
    ct = load("continuing_tenants.csv")
    S["continuing_tenants"] = {r["transition"]: {k: F(r[k]) for k in ("households_n", "overburden_t_pct", "overburden_t1_pct",
                                                                    "median_income_growth_pct", "median_rent_growth_pct",
                                                                    "mean_rent_growth_pct", "share_rent_unchanged_pct", "same_members_n",
                                                                    "same_members_overburden_t_pct", "same_members_overburden_t1_pct")
                                                 if r[k] != ""} for r in ct}
    chain = [S["continuing_tenants"][f"{t}->{t + 1}"] for t in range(2021, 2025)]
    S["continuing_chain_2021_2025_pp"] = round(sum(c["overburden_t1_pct"] - c["overburden_t_pct"] for c in chain), 1)
    tba = load("tenants_by_age.csv")
    def tb(y, g, k):
        return F(one(tba, year=y, age_group=g)[k])
    S["age_costs"] = {}
    for g, lab in (("18-34_emancipated", "young"), ("35-64 (comparison, not in the split)", "35-64")):
        S["age_costs"][lab] = {k: round(100 * (tb(2025, g, k) / tb(2021, g, k) - 1), 1)
                               for k in ("median_housing_cost", "median_rent", "median_household_income")}
        S["age_costs"][lab]["overburden_2021"] = tb(2021, g, "overburden_pct")
        S["age_costs"][lab]["overburden_2025"] = tb(2025, g, "overburden_pct")
    lv = load("leavers.csv")
    S["leavers"] = {f"{r['period_file']}|{r['personal_income_group']}": {"at_risk_n": int(r["at_risk_n"]), "left_n": int(r["left_n"]),
                    "rate": F(r["leaving_rate_pct"])} for r in lv if r["transition"] == "pooled"}
    cj = load("cje_reconciliation.csv")
    S["cje"] = {f"{r['age_band']}|{r['step']}|{r['measure']}": {k: (F(r[k]) if r[k] not in ("",) and r[k] != "nan" else None)
                for k in ("numerator_eur_month", "denominator_eur_month", "value_pct", "n_persons", "n_households")} for r in cj}
    own = load("cje_own_ecv_figures.csv")
    S["cje_own"] = [{k: r[k] for k in r} for r in own]
    ep = load("epa_emancipation.csv")
    S["epa"] = {f"{r['source']}|{r['period']}": F(r["emancipated_pct"]) for r in ep}
    fw = load("fieldwork.csv")
    S["fieldwork"] = {r["year"]: {k: F(r[k]) for k in ("mean_interview_month", "months_from_mid_income_year", "share_sep_dec_pct")} for r in fw}
    ip = load("ipva.csv")
    def ipv(series, y):
        return F(one(ip, table="59004", series=series, year=y)["value"])
    S["ipva"] = {"new_2021": ipv("Total Nacional. Índice. Nuevo contrato.", 2021), "new_2024": ipv("Total Nacional. Índice. Nuevo contrato.", 2024),
                 "existing_2021": ipv("Total Nacional. Índice. Contrato existente.", 2021), "existing_2024": ipv("Total Nacional. Índice. Contrato existente.", 2024)}
    S["ipva"]["new_growth_2021_2024_pct"] = round(100 * (S["ipva"]["new_2024"] / S["ipva"]["new_2021"] - 1), 1)
    S["ipva"]["existing_growth_2021_2024_pct"] = round(100 * (S["ipva"]["existing_2024"] / S["ipva"]["existing_2021"] - 1), 1)
    w = {r["year"]: F(r["value"]) for r in ip if r["table"] == "59008" and r["series"].startswith("Total Nacional. Ponderación. Nuevo")}
    S["ipva"]["new_contract_weight_2021"] = w["2021"] / 10
    S["ipva"]["new_contract_weight_2024"] = w["2024"] / 10
    sz = [r for r in ip if r["table"] == "59063" and r["year"] == "2024" and "Total." not in r["series"]]
    S["ipva"]["size_weights_2024"] = {r["series"].split(". ")[1]: F(r["value"]) / 10 for r in sz}
    mod = load("module_2025.csv")
    S["module"] = {f"{r['age_band']}|{r['personal_income_group']}": {k: F(v) for k, v in r.items() if k.endswith("_pct") and v != ""}
                   for r in mod}
    sel = load("selection_cells.csv")
    S["selection_cells"] = {f"{r['year']}|{r['age_band']}|{r['personal_income_group']}": {k: F(r[k]) for k in
                            ("emancipated_pct", "market_tenant_pct", "share_of_young_tenants_pct", "tenants_overburden_pct")
                            if r[k] != ""} for r in sel
                            if r["year"] in ("2008", "2019", "2021", "2025")}
    with open(D / "summary.json", "w", encoding="utf-8") as f:
        json.dump(S, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("summary.json written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
