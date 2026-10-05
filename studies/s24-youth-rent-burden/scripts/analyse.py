#!/usr/bin/env python3
"""S24: housing cost burden of young people in Spain from INE's ECV microdata, 2004-2025.

Reads data/raw/derived/ecv_persons_<year>.csv (written by extract_ecv.py; unit-level, git-ignored) and
writes aggregates only to data/:

  eurostat_replication.csv   our overburden rates vs Eurostat ilc_lvho07c / ilc_lvho07a
  living_with_parents.csv    share of young people living with a parent, by age band, 2004-2025
  young_burden.csv           burden of young people and young households by tenure, 2008-2025
  young_tenants_breakdown.csv young market tenants by national income quintile and household type
  tenants_by_age.csv         market-rent overburden by age group (is the fall specific to the young?)
  selection_cells.csv        emancipation and tenancy by personal-income group among all young people
  decomposition.csv          shift-share split of the change in young tenants' overburden
  selection_bound.csv        worst-case bound: extra stayers counted as overburdened tenants
  drivers.csv                rents and incomes of market tenants; income-growth counterfactual
  fieldwork.csv              interview months and the lag between income year and interview
  cje_reconciliation.csv     from the CJE's 98.7% to the burden young tenants pay
  module_2025.csv            ECV 2025 module: main reason for living with a parent, by income group
  bootstrap.csv              household-cluster bootstrap intervals for headline estimates
  summary.json               headline numbers (read by check_headlines.py)

Definitions (Eurostat, ilc_lvho07 metadata): housing cost burden = (12*HH070 - HY070G) / (HY020 - HY070G);
overburdened when > 40%; a household with HY020 - HY070G <= 0 counts as overburdened. Tenure from HH021.
"Young" = age at interview (RB082; before 2021 from birth year and month and the interview month).
"Emancipated" = no father and no mother in the household (RB220 and RB230 empty).
Weights: RB050 for persons, DB090 for households. Income refers to the calendar year before the survey.
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import defaultdict

from s24lib import D, RAW, wmean, wmedian, wquantile

YEARS = list(range(2004, 2026))
INC_YEARS = list(range(2008, 2026))        # base-2013 income
BANDS = {"18-29": (18, 29), "18-34": (18, 34), "16-29": (16, 29)}
TEN = {1: "owner_outright", 2: "owner_mortgage", 3: "market_rent", 4: "reduced_or_free", 5: "reduced_or_free",
       0: "owner"}
CJE = {"asking_rent": 1176.0, "salary_annual": 14292.22, "household_income_annual": 31167.83,
       "pct_salary": 98.7, "pct_household": 45.3, "mean_rent_renter_households": 780.0,
       "pct_income_renter_households": 30.0, "overburden_renter_households": 48.9, "emancipation_2025": 14.5}
random.seed(20261004)


def fl(x):
    return float(x) if x not in ("", None) else None


def load(year):
    path = RAW / "derived" / f"ecv_persons_{year}.csv"
    out = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p = {
                "hh": r["hh"], "pid": r["pid"], "w": fl(r["w_pers"]) or 0.0, "wh": fl(r["w_hh"]) or 0.0,
                "region": r["region"], "age": int(r["age_int"]) if r["age_int"] else None,
                "age_end": int(r["age_end"]) if r["age_end"] else None,
                "par": r["father"] != "" or r["mother"] != "", "partner": r["partner"] != "",
                "father": r["father"], "mother": r["mother"], "is_resp": r["is_resp"] == "1",
                "size": int(float(r["hh_size"])) if r["hh_size"] else None, "cu": fl(r["cu"]),
                "inc": fl(r["hy020"]), "al": fl(r["hy070g"]) or 0.0,
                "ten": int(r["tenure"]) if r["tenure"] != "" else None,
                "rent": fl(r["rent"]), "hc": fl(r["hcost"]), "rooms": fl(r["rooms"]),
                "month": int(r["interview_month"]) if r["interview_month"] else None,
                "pinc": fl(r["pers_inc"]), "py010n": fl(r["py010n"]), "pmg4": r["pmg4"], "pmg8": r["pmg8"],
            }
            out.append(p)
    # household composition flags
    byhh = defaultdict(list)
    for p in out:
        byhh[p["hh"]].append(p)
    for hh, mem in byhh.items():
        ids = {int(float(m["pid"])) for m in mem}
        parents_of = defaultdict(int)
        for m in mem:
            for k in ("father", "mother"):
                if m[k] != "":
                    parents_of[int(float(m[k]))] += 1
        for m in mem:
            mid = int(float(m["pid"]))
            m["has_child"] = parents_of.get(mid, 0) > 0
            others = len(mem) - 1 - (1 if m["partner"] else 0)
            if (m["size"] == 1) if m["size"] is not None else len(mem) == 1:
                m["htype"] = "alone"
            elif m["partner"] and len(mem) == 2:
                m["htype"] = "couple"
            elif m["partner"] and m["has_child"] and not m["par"]:
                m["htype"] = "couple_with_children"
            elif not m["partner"] and m["has_child"] and not m["par"]:
                m["htype"] = "single_parent"
            elif not m["partner"] and not m["has_child"] and not m["par"] and others >= 1:
                m["htype"] = "shared_or_other"      # flatmates, siblings or other relatives
            else:
                m["htype"] = "other"
    return out


def burden(p):
    """Eurostat housing cost burden; None when costs or income are missing; inf when net income <= 0."""
    if p["hc"] is None or p["inc"] is None:
        return None
    den = p["inc"] - p["al"]
    if den <= 0:
        return math.inf
    return max(12 * p["hc"] - p["al"], 0.0) / den


def rent_ratio(p):
    if p["rent"] is None or p["inc"] is None:
        return None
    return math.inf if p["inc"] <= 0 else 12 * p["rent"] / p["inc"]


def ob_share(ps, wk="w"):
    num = den = 0.0
    for p in ps:
        b = burden(p)
        if b is None:
            continue
        den += p[wk]
        num += p[wk] * (b > 0.4)
    return 100 * num / den if den else float("nan")


def households(ps):
    seen = {}
    for p in ps:
        seen.setdefault(p["hh"], p)
    return list(seen.values())


def in_band(p, band, agekey="age"):
    lo, hi = BANDS[band]
    a = p[agekey]
    return a is not None and lo <= a <= hi


def eq_quintiles(ps):
    """National quintile cut-offs of equivalised disposable income over persons (RB050)."""
    vals, ws = [], []
    for p in ps:
        if p["inc"] is not None and p["cu"]:
            vals.append(p["inc"] / p["cu"]); ws.append(p["w"])
    return [wquantile(vals, ws, q) for q in (0.2, 0.4, 0.6, 0.8)]


def quint(p, cuts):
    if p["inc"] is None or not p["cu"]:
        return None
    x = p["inc"] / p["cu"]
    return 1 + sum(x > c for c in cuts)


MIN_HH = 10   # statistics from fewer households are not published (a median of a few is one household's value)


def stats(ps, wk="w"):
    """Weighted summary for a group of persons (wk='w') or households (wk='wh'). Cells with fewer than
    MIN_HH households keep their counts and are flagged; their medians and rates are left blank."""
    ps = [p for p in ps if p[wk] > 0]
    if not ps:
        return None
    nh = len({p["hh"] for p in ps})
    if nh < MIN_HH:
        return {"n": len(ps), "households": nh, "pop": round(sum(p[wk] for p in ps)), "median_rent": "", "mean_rent": "",
                "median_housing_cost": "", "median_income": "", "median_rent_to_income_pct": "", "median_burden_pct": "",
                "overburden_pct": "", "suppressed": f"fewer than {MIN_HH} households"}
    w = [p[wk] for p in ps]
    b = [(burden(p), p[wk]) for p in ps if burden(p) is not None]
    rr = [(rent_ratio(p), p[wk]) for p in ps if rent_ratio(p) is not None]
    rents = [(p["rent"], p[wk]) for p in ps if p["rent"] is not None]
    hcs = [(p["hc"], p[wk]) for p in ps if p["hc"] is not None]
    incs = [(p["inc"], p[wk]) for p in ps if p["inc"] is not None]
    return {
        "n": len(ps), "households": len({p["hh"] for p in ps}), "pop": round(sum(w)),
        "median_rent": round(wmedian(*zip(*rents)), 1) if rents else "",
        "mean_rent": round(wmean(*zip(*rents)), 1) if rents else "",
        "median_housing_cost": round(wmedian(*zip(*hcs)), 1) if hcs else "",
        "median_income": round(wmedian(*zip(*incs))) if incs else "",
        "median_rent_to_income_pct": round(100 * wmedian(*zip(*rr)), 1) if rr else "",
        "median_burden_pct": round(100 * wmedian(*zip(*b)), 1) if b else "",
        "overburden_pct": round(ob_share(ps, wk), 1), "suppressed": "",
    }


def weighted_quartile_groups(vals_w):
    """Cut-offs (25/50/75%) of positive personal income."""
    pos = [(v, w) for v, w in vals_w if v is not None and v > 0]
    if not pos:
        return [0, 0, 0]
    v, w = zip(*pos)
    return [wquantile(v, w, q) for q in (0.25, 0.5, 0.75)]


def pgroup(p, cuts):
    if p["pinc"] is None or p["pinc"] <= 0:
        return "G0_none"
    return ("G1", "G2", "G3", "G4")[sum(p["pinc"] > c for c in cuts)]


def shapley(cells0, cells1):
    """cells: {key: (weight, overburdened weight)}. Exact two-factor split of the change in the rate."""
    keys = set(cells0) | set(cells1)
    T0 = sum(v[0] for v in cells0.values()); T1 = sum(v[0] for v in cells1.values())
    O0 = sum(v[1] for v in cells0.values()) / T0; O1 = sum(v[1] for v in cells1.values()) / T1
    comp = within = 0.0
    for k in keys:
        w0, b0 = cells0.get(k, (0.0, 0.0)); w1, b1 = cells1.get(k, (0.0, 0.0))
        s0, s1 = w0 / T0, w1 / T1
        o0 = b0 / w0 if w0 else O0
        o1 = b1 / w1 if w1 else O1
        comp += (s1 - s0) * (o0 + o1) / 2
        within += (o1 - o0) * (s0 + s1) / 2
    return 100 * O0, 100 * O1, 100 * comp, 100 * within


def write(name, rows, fields=None):
    fields = fields or list(rows[0].keys())
    with open(D / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})


def eurostat(name):
    sys.path.insert(0, str(D.parent / "scripts"))
    from jsonstat import rows as jrows
    _, rows = jrows(RAW / "eurostat" / f"{name}.json")
    return rows


def boot_households(ps, B=200):
    """Household-cluster bootstrap within region (DB040). Yields resampled person lists (with replicates)."""
    byreg = defaultdict(lambda: defaultdict(list))
    for p in ps:
        byreg[p["region"]][p["hh"]].append(p)
    regs = {r: list(h.values()) for r, h in byreg.items()}
    for _ in range(B):
        out = []
        for r, hhs in regs.items():
            n = len(hhs)
            for _k in range(n):
                out.extend(hhs[random.randrange(n)])
        yield out


def main():
    E07c = {(r["tenure"], r["time"]): r["value"] for r in eurostat("ilc_lvho07c") if r["geo"] == "ES"}
    E07a = {(r["age"], r["time"]): r["value"] for r in eurostat("ilc_lvho07a")
            if r["geo"] == "ES" and r["sex"] == "T" and r["rskpovth"] == "TOTAL"}
    Elps = {(r["age"], r["time"]): r["value"] for r in eurostat("ilc_lvps08") if r["geo"] == "ES" and r["sex"] == "T"}

    rep, lwp, yb, brk, tba, selc, fwk, drv, mod = [], [], [], [], [], [], [], [], []
    cells = {}          # (year, band) -> {cell: (w, ob)}
    cells_age = {}      # (year, band) -> {cell incl. age subgroup}
    tenants_age = {}    # year -> {agegroup: (w, ob)}
    tenants_q = {}      # year -> {national quintile: (w, ob)}, market tenants of all ages
    pops = {}           # (year, band) -> dict for the bound
    summary = {"years": {}}
    boot_rows = []

    for y in YEARS:
        ps = load(y)
        has_income = y >= 2008
        # --- living with parents (all years) ---------------------------------------------------
        for band in ("18-29", "18-34", "16-29"):
            for agekey in ("age", "age_end"):
                g = [p for p in ps if in_band(p, band, agekey) and p["w"] > 0]
                tot = sum(p["w"] for p in g)
                lw = sum(p["w"] for p in g if p["par"])
                lwp.append({"year": y, "age_band": band, "age_definition": "interview" if agekey == "age" else
                            "end_of_income_year", "n": len(g), "pop": round(tot),
                            "living_with_parent_pct": round(100 * lw / tot, 2),
                            "emancipated_pct": round(100 - 100 * lw / tot, 2),
                            "eurostat_ilc_lvps08": Elps.get(("Y" + band, str(y)), "") if agekey == "age" else ""})
        # --- fieldwork timing -------------------------------------------------------------------
        hh = households(ps)
        mon = [(p["month"], p["wh"]) for p in hh if p["month"]]
        if mon:
            tw = sum(w for _, w in mon)
            mean_m = sum(m * w for m, w in mon) / tw
            fwk.append({"year": y, "households": len(hh), "first_month": min(m for m, _ in mon),
                        "last_month": max(m for m, _ in mon), "mean_interview_month": round(mean_m, 1),
                        "months_from_mid_income_year": round(12 + mean_m - 7, 1),
                        "share_sep_dec_pct": round(100 * sum(w for m, w in mon if m >= 9) / tw, 1)})
        if not has_income:
            continue
        cuts = eq_quintiles(ps)
        for p in ps:
            p["q"] = quint(p, cuts)
            p["tg"] = TEN.get(p["ten"], "missing")
        # --- replication of Eurostat ------------------------------------------------------------
        allp = [p for p in ps if p["w"] > 0]
        for tg, code in (("all", "TOTAL"), ("market_rent", "RENT_MKT"), ("reduced_or_free", "RENT_FR"),
                         ("owner_mortgage", "OWN_L"), ("owner_outright", "OWN_NL")):
            g = allp if tg == "all" else [p for p in allp if p["tg"] == tg]
            if not g:
                continue
            ours = ob_share(g)
            eu = E07c.get((code, str(y)))
            rep.append({"year": y, "table": "ilc_lvho07c", "group": code, "ours": round(ours, 1), "eurostat": eu,
                        "diff": round(ours - eu, 1) if eu is not None else ""})
        for agekey, tname in (("age_end", "ilc_lvho07a"), ("age", "ilc_lvho07a (age at interview)")):
            for lab, lo, hi in (("Y15-29", 15, 29), ("Y18-24", 18, 24), ("Y25-29", 25, 29)):
                g = [p for p in allp if p[agekey] is not None and lo <= p[agekey] <= hi]
                ours = ob_share(g)
                eu = E07a.get((lab, str(y)))
                rep.append({"year": y, "table": tname, "group": lab, "ours": round(ours, 1), "eurostat": eu,
                            "diff": round(ours - eu, 1) if eu is not None else ""})
        # --- young burden by tenure and unit ----------------------------------------------------
        for band in BANDS:
            em = [p for p in allp if in_band(p, band) and not p["par"]]
            hh_cje = {}
            for p in em:
                hh_cje.setdefault(p["hh"], p)
            hh_ref = [p for p in allp if p["is_resp"] and in_band(p, band)]
            for unit, group, wk in (("persons_emancipated", em, "w"), ("households_with_emancipated_young",
                                    list(hh_cje.values()), "wh"), ("households_young_reference_person", hh_ref, "wh")):
                for tg in ("all", "market_rent", "reduced_or_free", "owner_mortgage", "owner_outright"):
                    g = group if tg == "all" else [p for p in group if p["tg"] == tg]
                    s = stats(g, wk)
                    if s:
                        yb.append({"year": y, "age_band": band, "unit": unit, "tenure": tg, **s})
            # sensitivity: age at the end of the income year
            em_end = [p for p in allp if in_band(p, band, "age_end") and not p["par"] and p["tg"] == "market_rent"]
            s = stats(em_end)
            if s:
                yb.append({"year": y, "age_band": band, "unit": "persons_emancipated_age_end_of_income_year",
                           "tenure": "market_rent", **s})
            # young market tenants: breakdowns
            ten = [p for p in em if p["tg"] == "market_rent"]
            for q in (1, 2, 3, 4, 5):
                s = stats([p for p in ten if p["q"] == q])
                if s:
                    brk.append({"year": y, "age_band": band, "breakdown": "national_income_quintile", "value": q, **s})
            for ht in ("alone", "couple", "couple_with_children", "single_parent", "shared_or_other", "other"):
                s = stats([p for p in ten if p["htype"] == ht])
                if s:
                    s["share_of_young_tenants_pct"] = round(100 * s["pop"] / sum(p["w"] for p in ten), 1)
                    brk.append({"year": y, "age_band": band, "breakdown": "household_type", "value": ht, **s})
            # --- selection: personal-income groups among ALL young people ---------------------
            allyoung = [p for p in allp if in_band(p, band)]
            pcuts = weighted_quartile_groups([(p["pinc"], p["w"]) for p in allyoung])
            for p in allyoung:
                p["pg"] = pgroup(p, pcuts)
                p["ag"] = "18-24" if p["age"] <= 24 else ("25-29" if p["age"] <= 29 else "30-34")
            totw = sum(p["w"] for p in allyoung)
            for gname in ("G0_none", "G1", "G2", "G3", "G4"):
                g = [p for p in allyoung if p["pg"] == gname]
                gw = sum(p["w"] for p in g)
                emw = sum(p["w"] for p in g if not p["par"])
                tnt = [p for p in g if not p["par"] and p["tg"] == "market_rent"]
                tw_ = sum(p["w"] for p in tnt)
                selc.append({"year": y, "age_band": band, "personal_income_group": gname,
                             "cut_low": "" if gname in ("G0_none", "G1") else round(pcuts[int(gname[1]) - 2]),
                             "n": len(g), "share_of_young_pct": round(100 * gw / totw, 1),
                             "emancipated_pct": round(100 * emw / gw, 1) if gw else "",
                             "market_tenant_pct": round(100 * tw_ / gw, 1) if gw else "",
                             "share_of_young_tenants_pct": round(100 * tw_ / sum(p["w"] for p in ten), 1),
                             "tenants_n": len(tnt), "tenants_overburden_pct": round(ob_share(tnt), 1) if tnt else "",
                             "median_personal_income": round(wmedian([p["pinc"] or 0 for p in g], [p["w"] for p in g]))})
            c1, c2 = defaultdict(lambda: [0.0, 0.0]), defaultdict(lambda: [0.0, 0.0])
            for p in ten:
                b = burden(p)
                if b is None:
                    continue
                for c, key in ((c1, p["pg"]), (c2, (p["pg"], p["ag"]))):
                    c[key][0] += p["w"]; c[key][1] += p["w"] * (b > 0.4)
            cells[(y, band)] = {k: tuple(v) for k, v in c1.items()}
            cells_age[(y, band)] = {k: tuple(v) for k, v in c2.items()}
            pops[(y, band)] = {"young": totw, "with_parents": sum(p["w"] for p in allyoung if p["par"]),
                               "emancipated": sum(p["w"] for p in allyoung if not p["par"]),
                               "tenants": sum(p["w"] for p in ten), "tenants_ob": ob_share(ten),
                               "tenants_ob_G0G1": ob_share([p for p in ten if p["pg"] in ("G0_none", "G1")])}
        # --- market tenants by age group ------------------------------------------------------
        mk = [p for p in allp if p["tg"] == "market_rent" and p["age"] is not None]
        groups = {"18-34_emancipated": lambda p: 18 <= p["age"] <= 34 and not p["par"],
                  "18-34_with_parents": lambda p: 18 <= p["age"] <= 34 and p["par"],
                  "under_18": lambda p: p["age"] < 18, "35-49": lambda p: 35 <= p["age"] <= 49,
                  "50-64": lambda p: 50 <= p["age"] <= 64, "65_plus": lambda p: p["age"] >= 65}
        tenants_age[y] = {}
        cq = defaultdict(lambda: [0.0, 0.0])
        for p in mk:
            b = burden(p)
            if b is not None and p["q"] is not None:
                cq[p["q"]][0] += p["w"]; cq[p["q"]][1] += p["w"] * (b > 0.4)
        tenants_q[y] = {k: tuple(v) for k, v in cq.items()}
        totmk = sum(p["w"] for p in mk)
        def wmed_of(g, key):
            v = [(key(p), p["w"]) for p in g if key(p) is not None]
            return round(wmedian(*zip(*v)), 1) if v else ""
        extra = {"35-64 (comparison, not in the split)": lambda p: 35 <= p["age"] <= 64}
        for gname, fn in list(groups.items()) + list(extra.items()):
            g = [p for p in mk if fn(p)]
            obw = sum(p["w"] for p in g if burden(p) is not None and burden(p) > 0.4)
            gw = sum(p["w"] for p in g if burden(p) is not None)
            if gname in groups:
                tenants_age[y][gname] = (gw, obw)
            tba.append({"year": y, "age_group": gname, "n": len(g), "share_of_market_tenants_pct": round(100 * sum(p["w"] for p in g) / totmk, 1),
                        "overburden_pct": round(100 * obw / gw, 1) if gw else "",
                        "median_burden_pct": round(100 * wmedian([burden(p) for p in g if burden(p) is not None],
                                                                 [p["w"] for p in g if burden(p) is not None]), 1),
                        "median_housing_cost": wmed_of(g, lambda p: p["hc"]), "median_rent": wmed_of(g, lambda p: p["rent"]),
                        "median_household_income": wmed_of(g, lambda p: p["inc"])})
        # --- drivers for market-tenant households ----------------------------------------------
        mh = [p for p in households(allp) if p["tg"] == "market_rent"]
        ah = households(allp)
        drv.append({"year": y, "group": "market_rent_households", "n": len(mh),
                    "median_rent": round(wmedian([p["rent"] for p in mh if p["rent"] is not None], [p["wh"] for p in mh if p["rent"] is not None]), 1),
                    "median_housing_cost": round(wmedian([p["hc"] for p in mh if p["hc"] is not None], [p["wh"] for p in mh if p["hc"] is not None]), 1),
                    "median_income": round(wmedian([p["inc"] for p in mh], [p["wh"] for p in mh])),
                    "median_income_all_households": round(wmedian([p["inc"] for p in ah], [p["wh"] for p in ah])),
                    "share_households_market_rent_pct": round(100 * sum(p["wh"] for p in mh) / sum(p["wh"] for p in ah), 1),
                    "overburden_persons_pct": round(ob_share([p for p in allp if p["tg"] == "market_rent"]), 1),
                    "overburden_households_pct": round(ob_share(mh, "wh"), 1)})
        # --- 2025 module ------------------------------------------------------------------------
        if y == 2025:
            reasons = {"1": "not_considered", "2": "cannot_afford_rent", "3": "cannot_afford_deposit_to_buy",
                       "4": "cannot_get_mortgage", "5": "saving_to_rent_or_buy", "6": "can_afford_prefers_parents", "7": "other"}
            ally = [p for p in allp if p["age"] is not None and 18 <= p["age"] <= 34]
            pcuts = weighted_quartile_groups([(p["pinc"], p["w"]) for p in ally])
            for sub, lo, hi in (("18-34", 18, 34), ("18-25", 18, 25), ("26-34", 26, 34)):
                g = [p for p in ally if lo <= p["age"] <= hi and p["par"] and p["pmg8"] in reasons]
                for gname in ("all", "G0_none", "G1", "G2", "G3", "G4"):
                    gg = g if gname == "all" else [p for p in g if pgroup(p, pcuts) == gname]
                    tw_ = sum(p["w"] for p in gg)
                    row = {"age_band": sub, "personal_income_group": gname, "n": len(gg)}
                    for code, lab in reasons.items():
                        row[lab + "_pct"] = round(100 * sum(p["w"] for p in gg if p["pmg8"] == code) / tw_, 1) if tw_ else ""
                    row["affordability_reasons_pct"] = round(sum(row[r + "_pct"] for r in ("cannot_afford_rent", "cannot_afford_deposit_to_buy", "cannot_get_mortgage")), 1) if tw_ else ""
                    mod.append(row)
        # --- bootstrap of headline estimates ----------------------------------------------------
        if y in (2019, 2021, 2023, 2025):
            def headline(sample):
                t = [p for p in sample if in_band(p, "18-34") and not p["par"] and p["tg"] == "market_rent"]
                t29 = [p for p in t if p["age"] <= 29]
                mkt = [p for p in sample if p["tg"] == "market_rent"]
                b = [(burden(p), p["w"]) for p in t if burden(p) is not None]
                rr = [(rent_ratio(p), p["w"]) for p in t if rent_ratio(p) is not None]
                young = [p for p in sample if in_band(p, "18-34")]
                m3549 = [p for p in mkt if p["age"] is not None and 35 <= p["age"] <= 49]
                m5064 = [p for p in mkt if p["age"] is not None and 50 <= p["age"] <= 64]
                return {"young_tenants_18_34_overburden": ob_share(t), "young_tenants_18_29_overburden": ob_share(t29),
                        "tenants_35_49_overburden": ob_share(m3549), "tenants_50_64_overburden": ob_share(m5064),
                        "young_tenants_18_34_median_burden": 100 * wmedian(*zip(*b)),
                        "young_tenants_18_34_median_rent_to_income": 100 * wmedian(*zip(*rr)),
                        "market_tenants_overburden": ob_share(mkt),
                        "living_with_parents_18_34": 100 * sum(p["w"] for p in young if p["par"]) / sum(p["w"] for p in young)}
            point = headline(allp)
            reps = defaultdict(list)
            for s in boot_households(allp, B=200):
                for k, v in headline(s).items():
                    reps[k].append(v)
            for k, v in point.items():
                vs = sorted(reps[k])
                se = (sum((x - sum(vs) / len(vs)) ** 2 for x in vs) / (len(vs) - 1)) ** 0.5
                # normal interval from the bootstrap SE (200 replicates are thin for 2.5/97.5 percentiles);
                # the percentile interval is kept for comparison
                boot_rows.append({"year": y, "estimate": k, "point": round(v, 2), "se": round(se, 2),
                                  "ci95_low": round(v - 1.96 * se, 2), "ci95_high": round(v + 1.96 * se, 2),
                                  "pctl_2_5": round(vs[5], 2), "pctl_97_5": round(vs[194], 2), "replicates": len(vs)})
        print(f"{y} done", flush=True)

    # --- decomposition of the change in young tenants' overburden ----------------------------------
    dec = []
    for band in ("18-34", "18-29"):
        for b0, b1 in ((2021, 2025), (2019, 2025), (2022, 2023), (2014, 2025), (2008, 2025)):
            for label, src in (("income_group", cells), ("income_group_x_age", cells_age)):
                O0, O1, comp, within = shapley(src[(b0, band)], src[(b1, band)])
                dec.append({"age_band": band, "from": b0, "to": b1, "cells": label, "overburden_from": round(O0, 1),
                            "overburden_to": round(O1, 1), "change_pp": round(O1 - O0, 1),
                            "composition_pp": round(comp, 1), "within_pp": round(within, 1),
                            "composition_share_of_change_pct": round(100 * comp / (O1 - O0), 1) if O1 != O0 else ""})
    # market tenants of all ages by age group (who drives the fall?)
    for b0, b1 in ((2021, 2025), (2019, 2025)):
        O0, O1, comp, within = shapley(tenants_age[b0], tenants_age[b1])
        dec.append({"age_band": "all_ages", "from": b0, "to": b1, "cells": "age_group_of_market_tenants",
                    "overburden_from": round(O0, 1), "overburden_to": round(O1, 1), "change_pp": round(O1 - O0, 1),
                    "composition_pp": round(comp, 1), "within_pp": round(within, 1),
                    "composition_share_of_change_pct": round(100 * comp / (O1 - O0), 1)})
        # contribution of the young emancipated group's own change
        tot0 = sum(v[0] for v in tenants_age[b0].values()); tot1 = sum(v[0] for v in tenants_age[b1].values())
        for gname in tenants_age[b1]:
            w0, o0 = tenants_age[b0][gname]; w1, o1 = tenants_age[b1][gname]
            s0, s1 = w0 / tot0, w1 / tot1
            dec.append({"age_band": "all_ages", "from": b0, "to": b1, "cells": f"within_contribution:{gname}",
                        "overburden_from": round(100 * o0 / w0, 1), "overburden_to": round(100 * o1 / w1, 1),
                        "change_pp": round(100 * (o1 / w1 - o0 / w0), 1), "composition_pp": "",
                        "within_pp": round(100 * (o1 / w1 - o0 / w0) * (s0 + s1) / 2, 1),
                        "composition_share_of_change_pct": ""})

    for b0, b1 in ((2021, 2025), (2019, 2025), (2022, 2023)):
        O0, O1, comp, within = shapley(tenants_q[b0], tenants_q[b1])
        dec.append({"age_band": "all_ages", "from": b0, "to": b1, "cells": "national_income_quintile_of_market_tenants",
                    "overburden_from": round(O0, 1), "overburden_to": round(O1, 1), "change_pp": round(O1 - O0, 1),
                    "composition_pp": round(comp, 1), "within_pp": round(within, 1),
                    "composition_share_of_change_pct": round(100 * comp / (O1 - O0), 1)})
        tot0 = sum(v[0] for v in tenants_q[b0].values()); tot1 = sum(v[0] for v in tenants_q[b1].values())
        for q in sorted(tenants_q[b1]):
            w0, o0 = tenants_q[b0][q]; w1, o1 = tenants_q[b1][q]
            dec.append({"age_band": "all_ages", "from": b0, "to": b1, "cells": f"quintile_{q}",
                        "overburden_from": round(100 * o0 / w0, 1), "overburden_to": round(100 * o1 / w1, 1),
                        "change_pp": round(100 * (o1 / w1 - o0 / w0), 1), "composition_pp": "", "within_pp": "",
                        "composition_share_of_change_pct": "",
                        "share_of_tenants_from_pct": round(100 * w0 / tot0, 1), "share_of_tenants_to_pct": round(100 * w1 / tot1, 1)})

    # --- worst-case selection bound ------------------------------------------------------------------
    bound = []
    mkt_all = {r["year"]: r for r in drv}
    for band in ("18-34", "18-29"):
        for b0, b1 in ((2021, 2025), (2019, 2025), (2008, 2025)):
            P0, P1 = pops[(b0, band)], pops[(b1, band)]
            p0 = P0["with_parents"] / P0["young"]; p1 = P1["with_parents"] / P1["young"]
            extra = max(0.0, (p1 - p0) * P1["young"])
            tau = P1["tenants"] / P1["emancipated"]
            O0, O1 = P0["tenants_ob"], P1["tenants_ob"]
            T1 = P1["tenants"]
            # all-age market tenants (persons)
            A1 = sum(v[0] for v in tenants_age[b1].values()); AO1 = 100 * sum(v[1] for v in tenants_age[b1].values()) / A1
            AO0 = 100 * sum(v[1] for v in tenants_age[b0].values()) / sum(v[0] for v in tenants_age[b0].values())
            # The bound caps one channel only: fewer young people leaving home changing who is a tenant.
            for scen, X, rate in (("channel bound: extra stayers rent at the current tenancy rate, all overburdened", extra * tau, 100.0),
                                  ("channel bound: all extra stayers rent, all overburdened", extra, 100.0),
                                  ("variant: tenancy rate, overburdened like the two lowest income groups of young tenants in the final year", extra * tau, P1["tenants_ob_G0G1"]),
                                  ("variant: tenancy rate, overburdened like the two lowest income groups of young tenants in the base year", extra * tau, P0["tenants_ob_G0G1"])):
                Ostar = (O1 * T1 + rate * X) / (T1 + X)
                AOstar = (AO1 * A1 + rate * X) / (A1 + X)
                bound.append({"age_band": band, "from": b0, "to": b1, "scenario": scen,
                              "living_with_parents_from_pct": round(100 * p0, 1), "living_with_parents_to_pct": round(100 * p1, 1),
                              "extra_stayers": round(extra), "added_tenants": round(X), "tenants_to": round(T1),
                              "young_tenant_overburden_from": round(O0, 1), "young_tenant_overburden_to": round(O1, 1),
                              "young_counterfactual": round(Ostar, 1),
                              "young_share_of_fall_explained_pct": round(100 * (Ostar - O1) / (O0 - O1), 1) if O0 > O1 else "",
                              "all_tenants_overburden_from": round(AO0, 1), "all_tenants_overburden_to": round(AO1, 1),
                              "all_tenants_counterfactual": round(AOstar, 1),
                              "all_share_of_fall_explained_pct": round(100 * (AOstar - AO1) / (AO0 - AO1), 1)})

    # --- income-growth counterfactual for market tenants ---------------------------------------------
    cf = []
    for b0 in (2019, 2021):
        for b1 in (2025,):
            r0 = [r for r in drv if r["year"] == b0][0]; r1 = [r for r in drv if r["year"] == b1][0]
            g_inc = r1["median_income"] / r0["median_income"]
            g_cost = r1["median_housing_cost"] / r0["median_housing_cost"]
            ps = load(b1)
            mk = [p for p in ps if TEN.get(p["ten"]) == "market_rent" and p["w"] > 0]
            ym = [p for p in mk if p["age"] is not None and 18 <= p["age"] <= 34 and not p["par"]]
            for p in mk:
                p["inc"] = p["inc"] * g_cost / g_inc if p["inc"] is not None else None
            cf.append({"from": b0, "to": b1, "median_income_growth_pct": round(100 * (g_inc - 1), 1),
                       "median_housing_cost_growth_pct": round(100 * (g_cost - 1), 1),
                       "overburden_from": r0["overburden_persons_pct"], "overburden_to": r1["overburden_persons_pct"],
                       "overburden_to_if_incomes_had_grown_like_housing_costs": round(ob_share(mk), 1),
                       "young_tenants_18_34_if_so": round(ob_share(ym), 1)})

    # within-household income growth: chain the median income growth of continuing market-tenant
    # households (data/continuing_tenants.csv, longitudinal.py) over the same transitions
    ctp = D / "continuing_tenants.csv"
    if ctp.exists():
        with open(ctp, encoding="utf-8") as f:
            ct = {r["transition"]: float(r["median_income_growth_pct"]) for r in csv.DictReader(f) if r["median_income_growth_pct"] != ""}
        for b0 in (2019, 2021):
            b1 = 2025
            g_panel = 1.0
            for t in range(b0, b1):
                g_panel *= 1 + ct[f"{t}->{t + 1}"] / 100
            r0 = [r for r in drv if r["year"] == b0][0]; r1 = [r for r in drv if r["year"] == b1][0]
            g_cost = r1["median_housing_cost"] / r0["median_housing_cost"]
            g_inc = r1["median_income"] / r0["median_income"]
            ps = load(b1)
            mk = [p for p in ps if TEN.get(p["ten"]) == "market_rent" and p["w"] > 0]
            ym = [p for p in mk if p["age"] is not None and 18 <= p["age"] <= 34 and not p["par"]]
            for p in mk:   # take out only the income growth the same households saw beyond cost growth
                p["inc"] = p["inc"] * g_cost / g_panel if p["inc"] is not None else None
            cf.append({"from": f"{b0} panel", "to": b1, "median_income_growth_pct": round(100 * (g_panel - 1), 1),
                       "median_housing_cost_growth_pct": round(100 * (g_cost - 1), 1),
                       "overburden_from": r0["overburden_persons_pct"], "overburden_to": r1["overburden_persons_pct"],
                       "overburden_to_if_incomes_had_grown_like_housing_costs": round(ob_share(mk), 1),
                       "young_tenants_18_34_if_so": round(ob_share(ym), 1),
                       "note": "income growth = chained median growth within continuing tenant households, instead of the cross-section's"})

    # --- fieldwork-lag sensitivity: measure 2025 housing costs as if interviews had come as late after
    # the income year as in 2021, letting costs grow at the IPVA rate for existing contracts (2.8% in 2024)
    lag = {r["year"]: r["months_from_mid_income_year"] for r in fwk}
    extra_months = lag[2021] - lag[2025]
    ps = load(2025)
    mk = [p for p in ps if TEN.get(p["ten"]) == "market_rent" and p["w"] > 0]
    ym = [p for p in mk if p["age"] is not None and 18 <= p["age"] <= 34 and not p["par"]]
    base_all, base_young = ob_share(mk), ob_share(ym)
    for g in (0.028, 0.05):
        f_ = (1 + g) ** (extra_months / 12)
        for p in mk:
            p["hc0"] = p.get("hc0", p["hc"])
            p["hc"] = p["hc0"] * f_ if p["hc0"] is not None else None
        cf.append({"from": "lag", "to": 2025, "median_income_growth_pct": "", "median_housing_cost_growth_pct": round(100 * (f_ - 1), 1),
                   "overburden_from": round(base_all, 1), "overburden_to": round(base_all, 1),
                   "overburden_to_if_incomes_had_grown_like_housing_costs": round(ob_share(mk), 1),
                   "young_tenants_18_34_if_so": round(ob_share(ym), 1),
                   "note": f"costs x{f_:.4f}: {extra_months:.1f} more months at {100 * g:.1f}% a year (2021 lag vs 2025 lag)"})

    # --- write ---------------------------------------------------------------------------------------
    write("eurostat_replication.csv", rep)
    write("living_with_parents.csv", lwp)
    write("young_burden.csv", yb)
    write("young_tenants_breakdown.csv", brk, ["year", "age_band", "breakdown", "value", "n", "households", "pop",
                                                "share_of_young_tenants_pct", "median_rent", "mean_rent",
                                                "median_housing_cost", "median_income", "median_rent_to_income_pct",
                                                "median_burden_pct", "overburden_pct", "suppressed"])
    write("tenants_by_age.csv", tba)
    write("selection_cells.csv", selc)
    write("decomposition.csv", dec, ["age_band", "from", "to", "cells", "overburden_from", "overburden_to", "change_pp",
                                     "composition_pp", "within_pp", "composition_share_of_change_pct",
                                     "share_of_tenants_from_pct", "share_of_tenants_to_pct"])
    write("selection_bound.csv", bound)
    write("drivers.csv", drv)
    write("income_counterfactual.csv", cf, ["from", "to", "median_income_growth_pct", "median_housing_cost_growth_pct",
                                             "overburden_from", "overburden_to",
                                             "overburden_to_if_incomes_had_grown_like_housing_costs",
                                             "young_tenants_18_34_if_so", "note"])
    write("fieldwork.csv", fwk)
    write("module_2025.csv", mod)
    write("bootstrap.csv", boot_rows)
    print("written")


if __name__ == "__main__":
    main()
