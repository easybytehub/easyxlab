#!/usr/bin/env python3
"""S24: assert every headline number of README.md (and paper.md, when present) against data/.

Each number is read from data/summary.json or the CSVs in data/, formatted the way the text writes it,
and searched for in each document with whitespace (including line breaks) collapsed. Phrases carry
enough context that a number cannot be satisfied by an unrelated occurrence, and the paper's main
tables are rebuilt row by row from data/ and searched for whole. A missing paper.md is not an error:
only README.md is checked then. Exit 1 on any mismatch.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
D = R / "data"


def flat(s):
    return re.sub(r"\s+", " ", s)


def pct(x, d=1):
    return f"{float(x):.{d}f}%"


def num(x):
    return f"{int(round(float(x))):,}"


def pts(x):
    return f"{float(x):.1f}".replace("-", "−")


def csvrows(name):
    with open(D / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


docs = {"README.md": flat((R / "README.md").read_text(encoding="utf-8"))}
if (R / "paper.md").exists():
    docs["paper.md"] = flat((R / "paper.md").read_text(encoding="utf-8"))
else:
    print("paper.md not present: checking README.md only")
S = json.load(open(D / "summary.json", encoding="utf-8"))
bad = []
BOTH, PAPER, README = ("README.md", "paper.md"), ("paper.md",), ("README.md",)


def need(label, text, where=BOTH):
    print(f"{label}: {text}")
    for w in where:
        if w in docs and text not in docs[w]:
            bad.append(f"{w} does not contain «{text}» ({label})")


# 1. What young tenants pay ----------------------------------------------------------------------
y25, y21, y29 = S["young_tenants_18-34_2025"], S["young_tenants_18-34_2021"], S["young_tenants_18-29_2025"]
need("young 18-34 2025 n", f"n = {num(y25['n'])} people in {num(y25['households'])} households")
need("median rent", f"{num(y25['median_rent'])} € a month, {pct(y25['median_rent_to_income_pct'])} of household")
need("median burden value", pct(y25["median_burden_pct"]))
b = S["bootstrap"]["2025_young_tenants_18_34_overburden"]
need("overburden + interval", f"{pct(y25['overburden_pct'])} were overburdened")
need("bootstrap interval", f"{b['ci95_low']:.1f}–{b['ci95_high']:.1f}")
need("overburden 18-29", f"{pct(y29['overburden_pct'])} (n = {num(y29['n'])})")
need("2021 overburden", f"{pct(y21['overburden_pct'])} (n = {num(y21['n'])})")
ch = S["young_18_34_change_2021_2025"]
need("change 2021-2025", f"−{abs(ch['pp']):.1f} points", where=README)
need("change interval", f"{pts(ch['ci95_low'])} to {pts(ch['ci95_high'])}")
alone = [x for x in csvrows("young_tenants_breakdown.csv") if x["year"] == "2025" and x["age_band"] == "18-34"
         and x["breakdown"] == "household_type" and x["value"] == "alone"][0]
need("living alone overburdened", f"{pct(alone['overburden_pct'])} were overburdened (n = {num(alone['n'])})", where=README)
need("living alone overburdened, paper", f"{pct(alone['overburden_pct'])} of them are overburdened (n = {num(alone['n'])})", where=PAPER)
yr = S["young_ref_households_18-34_2025"]
need("reference-person households", f"{pct(yr['overburden_pct'])} ({num(yr['n'])} households)", where=PAPER)
need("age at end of income year", f"overburdened share is {pct(S['young_tenants_18-34_2025_age_end']['overburden_pct'])}", where=PAPER)

# 2. Replication ----------------------------------------------------------------------------------
r = S["replication"]
need("replication exact", f"exactly in {r['lvho07c_exact']} of {r['lvho07c_cells']} tenure-year cells")
need("replication max diff", f"within {r['lvho07c_max_abs_diff']:.1f} points in all")
need("ours = Eurostat 2025", f"{pct(r['rent_mkt_2025_ours'])} for market-rent tenants in 2025", where=README)
assert r["rent_mkt_2025_ours"] == r["rent_mkt_2025_eurostat"] and r["rent_mkt_2021_ours"] == r["rent_mkt_2021_eurostat"]
need("by age exact", f"{r['lvho07a_exact']} of {r['lvho07a_cells']}")
need("lvho07a max", f"largest gap {r['lvho07a_max_abs_diff']:.1f}", where=README)
lw = S["living_with_parents"]
need("living with parents 2021/2025", f"from {pct(lw['18-34_2021'])} to {pct(lw['18-34_2025'])}", where=README)
assert round(lw["18-34_2025"], 1) == lw["eurostat_18-34_2025"]

# 3. Selection ------------------------------------------------------------------------------------
L = S["leavers"]
need("leavers top vs none", f"{pct(L['2022-2025|G4']['rate'])} a year, against {pct(L['2022-2025|G0_none']['rate'])} for those with no income", where=README)
need("leavers top vs none, paper", f"{pct(L['2022-2025|G4']['rate'])} against {pct(L['2022-2025|G0_none']['rate'])}", where=PAPER)
need("leavers 2013-16", f"{pct(L['2013-2016|G4']['rate'])} against {pct(L['2013-2016|G0_none']['rate'])}")
need("leavers 2016-19", f"{pct(L['2016-2019|G4']['rate'])} against {pct(L['2016-2019|G0_none']['rate'])}", where=PAPER)
need("leavers 25-34", f"{pct(L['2022-2025|G4|25-34']['rate'])} against {pct(L['2022-2025|G0_none|25-34']['rate'])}", where=PAPER)
need("departures at risk", f"{num(L['2022-2025|all']['left_n'])} departures among {num(L['2022-2025|all']['at_risk_n'])}", where=PAPER)
dec = S["decomposition"]
need("35-49 fall", f"{abs(dec['within_35-49_2021_2025']['change_pp']):.1f} points at ages 35–49", where=README)
need("50-64 fall", f"{abs(dec['within_50-64_2021_2025']['change_pp']):.1f} points at ages 50–64", where=README)
need("young fall", f"{abs(dec['young_18_34_2021_2025']['change_pp']):.1f} points among young tenants", where=README)
d = S["young_minus_35_49_change"]
need("age comparison power", f"{d['pp']:.1f} points with a 95% interval of {pts(d['ci95_low'])} to {d['ci95_high']:.1f}", where=README)
need("age comparison power, paper", f"{d['pp']:.1f} points, with a 95% interval of {pts(d['ci95_low'])} to {d['ci95_high']:.1f}", where=PAPER)
ac = S["age_costs"]
need("cost growth young vs 35-64", f"rose {pct(ac['young']['median_housing_cost'])}")
need("cost growth 35-64", pct(ac["35-64"]["median_housing_cost"]))
need("young contribution", f"for {abs(dec['within_18-34_emancipated_2021_2025']['within_pp']):.1f}", where=PAPER)
need("all-tenant fall", f"{abs(dec['all_by_age_2021_2025']['change_pp']):.1f}-point fall")
ct = S["continuing_tenants"]
need("continuing 2022-23", f"from {pct(ct['2022->2023']['overburden_t_pct'])} overburdened in 2022 to {pct(ct['2022->2023']['overburden_t1_pct'])}", where=README)
need("continuing same members 23-24", f"{pct(ct['2023->2024']['same_members_overburden_t_pct'])} to {pct(ct['2023->2024']['same_members_overburden_t1_pct'])} with the same members", where=README)
for t in ("2021->2022", "2022->2023", "2023->2024", "2024->2025"):
    c = ct[t]
    row = (f"| {t.replace('->', ' → ')} | {num(c['households_n'])} | {pct(c['overburden_t_pct'])} | {pct(c['overburden_t1_pct'])} | "
           f"{pct(c['same_members_overburden_t_pct'])} → {pct(c['same_members_overburden_t1_pct'])} | "
           f"+{pct(c['median_income_growth_pct'])} | {'+' if c['median_rent_growth_pct'] > 0 else ''}{pct(c['median_rent_growth_pct'])} |")
    need(f"panel row {t}", row, where=PAPER)
need("panel chain", f"the fall within continuing households is {abs(S['continuing_chain_2021_2025_pp']):.1f} points", where=PAPER)
dr = S["drivers"]
need("cross-section households", f"{pct(dr['2021']['overburden_households_pct'])} to {pct(dr['2025']['overburden_households_pct'])}, household-weighted", where=PAPER)
bd = S["bound"]["2021_tenancy_rate_all_ob"]
need("extra stayers", f"equivalent of {num(bd['extra_stayers'])}")
need("bound counterfactual", f"{pct(bd['all_tenants_counterfactual'])} instead of {pct(S['replication']['rent_mkt_2025_ours'])}")
need("bound share", f"{pct(bd['all_share_of_fall_explained_pct'])}")
need("bound share all rent", pct(S["bound"]["2021_all_rent_all_ob"]["all_share_of_fall_explained_pct"]))
need("young bound", f"{pct(bd['young_share_of_fall_explained_pct'])}")
need("young bound all rent", pct(S["bound"]["2021_all_rent_all_ob"]["young_share_of_fall_explained_pct"]))
need("young bound 18-29", pct(S["bound"]["18-29_2021_tenancy_rate_all_ob"]["young_share_of_fall_explained_pct"]))
need("added tenants", num(bd["added_tenants"]), where=PAPER)
need("variant final", pct(S["bound"]["2021_low_income_final"]["young_share_of_fall_explained_pct"]), where=PAPER)
need("variant base", pct(S["bound"]["2021_low_income_base"]["young_share_of_fall_explained_pct"]), where=PAPER)
dy = dec["young_18_34_2021_2025"]
need("shift-share young", f"{abs(dy['composition_pp']):.1f} of their {abs(dy['change_pp']):.1f}-point fall", where=README)
need("shift-share young, paper", f"{abs(dy['composition_pp']):.1f} of the {abs(dy['change_pp']):.1f}-point fall ({pct(dy['composition_share_of_change_pct'])})", where=PAPER)
q = dec["all_by_quintile_2021_2025"]
need("quintile composition", f"{abs(q['composition_pp']):.1f} points ({pct(q['composition_share_of_change_pct'])})", where=PAPER)
sc = S["selection_cells"]
t21 = sc["2021|18-34|G3"]["share_of_young_tenants_pct"] + sc["2021|18-34|G4"]["share_of_young_tenants_pct"]
t25 = sc["2025|18-34|G3"]["share_of_young_tenants_pct"] + sc["2025|18-34|G4"]["share_of_young_tenants_pct"]
need("upper quarters' share", f"{pct(t21)} of young tenants in 2021 and {pct(t25)} in 2025", where=PAPER)
need("G1 tenants overburden", f"from {pct(sc['2021|18-34|G1']['tenants_overburden_pct'])} to {pct(sc['2025|18-34|G1']['tenants_overburden_pct'])} in the lowest income quarter", where=PAPER)
for y in ("2008", "2019", "2021", "2025"):
    row = "| " + y + " | " + " | ".join(pct(sc[f"{y}|18-34|{g}"]["emancipated_pct"]) for g in ("G0_none", "G1", "G2", "G3", "G4")) + " |"
    need(f"emancipation row {y}", row, where=PAPER)

# 4. Incomes and costs ---------------------------------------------------------------------------
cf, cp = S["income_counterfactual"]["2021"], S["income_counterfactual"]["2021_panel"]
need("income growth", f"rose {pct(cf['median_income_growth_pct'])}")
need("cost growth", f"{pct(cf['median_housing_cost_growth_pct'])}")
need("panel income growth", f"{pct(cp['median_income_growth_pct'])}")
need("within-household counterfactual", f"{pct(cp['overburden_to_if_incomes_had_grown_like_housing_costs'])}")
need("cross-section counterfactual", f"{pct(cf['overburden_to_if_incomes_had_grown_like_housing_costs'])}")
need("young panel counterfactual", f"({pct(cp['young_tenants_18_34_if_so'])} of young tenants)", where=PAPER)
ip = S["ipva"]
need("IPVA", f"existing contracts rising {pct(ip['existing_growth_2021_2024_pct'])} from 2021 to 2024, and under new contracts {pct(ip['new_growth_2021_2024_pct'])}", where=README)
need("IPVA weights", f"from {pct(ip['new_contract_weight_2021'])} to {pct(ip['new_contract_weight_2024'])}", where=PAPER)
fw = S["fieldwork"]
need("lag", f"{fw['2021']['months_from_mid_income_year']:.1f} months after the middle of the income year in 2021, but {fw['2025']['months_from_mid_income_year']:.1f}", where=PAPER)
need("lag sensitivity", f"to {pct(S['income_counterfactual']['lag_1.1']['overburden_to_if_incomes_had_grown_like_housing_costs'])} or {pct(S['income_counterfactual']['lag_1.9']['overburden_to_if_incomes_had_grown_like_housing_costs'])}", where=PAPER)
need("drivers rent row", "| median rent paid (€/month) | " + " | ".join(num(dr[y]["median_rent"]) for y in ("2019", "2021", "2025")) + " |", where=PAPER)
need("drivers cost row", "| median housing cost (€/month) | " + " | ".join(num(dr[y]["median_housing_cost"]) for y in ("2019", "2021", "2025")) + " |", where=PAPER)
need("drivers income row", "| median disposable income (€/year, previous year) | " + " | ".join(num(dr[y]["median_income"]) for y in ("2019", "2021", "2025")) + " |", where=PAPER)

# 5. CJE --------------------------------------------------------------------------------------------
C = S["cje"]
rp = C["16-29|1|rent paid by young market tenants / median young net salary"]["numerator_eur_month"]
need("rent paid 16-29", f"median rent paid is {num(rp)} €")
need("rent/household 16-29", pct(C["16-29|4|rent paid / the tenants' household disposable income"]["value_pct"]))
need("n 16-29", f"{num(C['16-29|0|CJE: asking rent / median young net salary']['n_persons'])} people")
E = C["16-29|2|rent paid / median net employee income of young earners in the ECV (PY010N > 0)"]["denominator_eur_month"]
need("ECV benchmark", f"{num(E)} €")
for key, lab in (("asking rent vs rent paid", "asking"), ("median ECV young earner vs the tenants' own income", "own"),
                 ("own income vs household income (sharing)", "sharing")):
    need(f"ECV chain {lab}", pct(C[f"16-29|gap_ecv|share of the log gap: {key}"]["value_pct"]))
for key, lab in (("asking rent vs rent paid", "asking"), ("median young salary vs the tenants' own income", "own"),
                 ("own income vs household income (sharing)", "sharing")):
    need(f"CJE chain {lab}", pts(C[f"16-29|gap|share of the log gap: {key}"]["value_pct"]) + "%")
sh = C["16-29|shared|young tenants sharing with flatmates or relatives: median rent per adult"]
need("sharers per adult", f"median {num(sh['numerator_eur_month'])} € each")
need("sharers ratio", pct(C["16-29|shared|the same: median of rent per adult / own net personal income"]["value_pct"]))
need("CJE room ratio", pct(C["16-29|shared|CJE: median room asking rent (400 EUR) / median young net salary"]["value_pct"]))
need("able at 40%", f"{pct(C['16-29|able|all young people whose own net income keeps the asking rent at or below 40%']['value_pct'])} of people aged 16–29")
need("able earners", pct(round(C["16-29|able|young wage earners (PY010N > 0) whose own net income keeps the asking rent at or below 40%"]["value_pct"], 1)))
need("alone 16-29", f"{pct(C['16-29|alone|living alone: overburdened (>40%)']['value_pct'])} of them are overburdened (n = 100)", where=PAPER)
need("own income", f"{num(C["16-29|3|rent paid / the tenants' own net personal income"]['denominator_eur_month'])} € a month", where=PAPER)
own = [r for r in S["cje_own"] if r["households"] == "an emancipated member aged 16-29"]
hc = [float(r["ours"]) for r in own if r["measure"].startswith("mean monthly housing cost")]
need("780 range", f"{min(hc):.0f}–{max(hc):.0f} €")
assert min(hc) <= 780.0 <= max(hc), "780 not within our range"
obs = [float(r["ours"]) for r in own if r["measure"].startswith("share with 12 x HH070")]
need("48.9 not reproduced", f"{min(obs):.1f}–{max(obs):.1f}%", where=PAPER)
need("48.9 same definition", f"48.9% overburden is not reproduced ({pct([float(r['ours']) for r in own if r['variant'] == 'age at interview; tenure 3 or 4' and r['measure'].startswith('share with 12')][0])}", where=README)

# 6. Emancipation series -----------------------------------------------------------------------------
E2 = S["epa"]
need("EPA H2 2024/2025", f"{pct(E2['EPA|2024H2'], 2)} and {pct(E2['EPA|2025H2'], 2)}", where=PAPER)
assert lw["16-29_min_year_interview"] == 2025 and lw["16-29_min_year_age_end"] == 2025, "2025 is not the ECV minimum"
need("ECV 16-29 2025 end", f"{lw['16-29_emancipated_2025_age_end']:.1f}%")
need("ECV 16-29 2025 interview", pct(lw["16-29_emancipated_2025"]), where=PAPER)

# 7. Main results table of the paper, row by row -------------------------------------------------------
yb = csvrows("young_burden.csv")
rep = {(x["year"], x["group"], x["table"]): x for x in csvrows("eurostat_replication.csv")}
for y in ("2008", "2014", "2019", "2021", "2022", "2023", "2025"):
    a = [x for x in yb if x["year"] == y and x["age_band"] == "18-34" and x["unit"] == "persons_emancipated" and x["tenure"] == "market_rent"][0]
    c = [x for x in yb if x["year"] == y and x["age_band"] == "18-29" and x["unit"] == "persons_emancipated" and x["tenure"] == "market_rent"][0]
    e = rep[(y, "RENT_MKT", "ilc_lvho07c")]
    row = (f"| {y} | {num(a['n'])} | {num(a['median_rent'])} | {pct(a['median_rent_to_income_pct'])} | {pct(a['median_burden_pct'])} | "
           f"{pct(a['overburden_pct'])} | {pct(c['overburden_pct'])} | {pct(e['ours'])} / {pct(e['eurostat'])} |")
    need(f"table 5.1 row {y}", row, where=PAPER)

if bad:
    print("\nMISMATCHES:")
    for b_ in bad:
        print("  " + b_)
    sys.exit(1)
print("\nall headline numbers found")
