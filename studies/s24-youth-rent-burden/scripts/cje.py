#!/usr/bin/env python3
"""S24: reconcile the CJE's «98,7 % de su salario» with what young tenants pay, ECV 2025.

The CJE's figure (Observatorio de Emancipación 2025) divides an asking rent, 1.176 EUR a month
(Idealista's asking price per m2 x 80 m2 built), by the median net salary of a young wage earner aged
16-29, 14.292,22 EUR a year (1.191,02 a month). It answers: could a young wage earner rent a whole
80 m2 flat alone, at today's asking price, on a median salary? This script measures, for the young
people who do rent at market price (emancipated, 16-29 and 18-34, ECV 2025):

  rent paid (HH060) instead of the asking rent;
  their own net personal income, then their household's disposable income, instead of the median salary;
  who they live with (alone, couple, shared);
  new tenancies (moved in the last 12 months, module variable PMG4) against sitting tenants.

It also recomputes, under eight definitions, the CJE's own ECV-based figures for young renter households
(mean «gasto en alquiler» 780 EUR; 48,9 % spending more than 40 % of income on housing), and the share of
all young people, and of young wage earners, whose own income would keep the asking rent within 30 % or
40 % of it. It sets beside it the CJE's own shared-flat ratio (a 400 EUR room, 33,6 % of the salary).

Writes data/cje_reconciliation.csv and data/cje_own_ecv_figures.csv. The ratio-of-medians chain is an
accounting device, not a model: each step swaps one CJE input for the measured value.
"""
from __future__ import annotations

import csv
import math
import sys

from analyse import CJE, TEN, burden, households, in_band, load, ob_share, rent_ratio
from s24lib import D, wmean, wmedian


def wmed(ps, key):
    v = [(key(p), p["w"]) for p in ps if key(p) is not None and p["w"] > 0]
    return wmedian(*zip(*v)) if v else float("nan")


def main():
    ps = load(2025)
    for p in ps:
        p["tg"] = TEN.get(p["ten"], "missing")
    S = CJE["salary_annual"] / 12
    A = CJE["asking_rent"]
    ROOM = 400.0                         # CJE 2025: «Renta mediana alquiler habitación (euros/mes) 400,00»
    adults = {}
    for p in ps:
        if p["age"] is not None and p["age"] >= 16:
            adults[p["hh"]] = adults.get(p["hh"], 0) + 1
    rows = []
    for band in ("16-29", "18-34"):
        T = [p for p in ps if in_band(p, band) and not p["par"] and p["tg"] == "market_rent" and p["rent"] is not None
             and p["inc"] is not None and p["w"] > 0]
        R = wmed(T, lambda p: p["rent"])
        Iown = wmed(T, lambda p: (p["pinc"] or 0.0) / 12)
        Ihh = wmed(T, lambda p: p["inc"] / 12)
        med_ratio = wmed(T, lambda p: rent_ratio(p))
        med_b = wmed(T, lambda p: burden(p))
        alone = [p for p in T if p["htype"] == "alone"]
        movers = [p for p in T if p["pmg4"] == "6"]
        stayers = [p for p in T if p["pmg4"] == "1"]
        young_all = [p for p in ps if in_band(p, band) and p["w"] > 0 and p["age"] >= 16]
        def share_able(threshold):
            need = 12 * A / threshold
            tw = sum(p["w"] for p in young_all)
            return 100 * sum(p["w"] for p in young_all if (p["pinc"] or 0) >= need) / tw
        emp = [p for p in ps if in_band(p, band) and p["w"] > 0 and p.get("pinc") is not None]
        earners = [p for p in emp if (p.get("py010n") or 0) > 0]
        E = wmed(earners, lambda p: p["py010n"] / 12)      # ECV benchmark: median net employee income of young earners
        steps = [
            ("CJE: asking rent / median young net salary", A, S, 100 * A / S, "CJE 2025 report"),
            ("rent paid by young market tenants / median young net salary", R, S, 100 * R / S, "ECV 2025 HH060; CJE salary"),
            ("rent paid / median net employee income of young earners in the ECV (PY010N > 0)", R, E, 100 * R / E, "ECV 2025 HH060, PY010N"),
            ("rent paid / the tenants' own net personal income", R, Iown, 100 * R / Iown, "ECV 2025 HH060, PY*N"),
            ("rent paid / the tenants' household disposable income", R, Ihh, 100 * R / Ihh, "ECV 2025 HH060, HY020"),
            ("median of each tenant's rent / household income", "", "", 100 * med_ratio, "ECV 2025"),
            ("median housing cost burden (Eurostat definition)", "", "", 100 * med_b, "ECV 2025 HH070, HY020, HY070G"),
            ("share overburdened (>40%, Eurostat definition)", "", "", ob_share(T), "ECV 2025"),
        ]
        for i, (lab, num, den, val, src) in enumerate(steps):
            rows.append({"age_band": band, "step": i, "measure": lab, "numerator_eur_month": round(num, 2) if num != "" else "",
                         "denominator_eur_month": round(den, 2) if den != "" else "", "value_pct": round(val, 1), "source": src,
                         "n_persons": len(T), "n_households": len({p["hh"] for p in T})})
        # log-point accounting of the gap between the CJE ratio and rent paid / household income
        gap = math.log(A / S) - math.log(R / Ihh)
        for lab, x in (("asking rent vs rent paid", math.log(A / R)),
                       ("median young salary vs the tenants' own income", math.log(Iown / S)),
                       ("own income vs household income (sharing)", math.log(Ihh / Iown))):
            rows.append({"age_band": band, "step": "gap", "measure": f"share of the log gap: {lab}", "value_pct": round(100 * x / gap, 1),
                         "source": f"log gap {gap:.3f}", "n_persons": len(T)})
        # the same accounting with an ECV benchmark instead of the CJE's ETCL-based salary
        gap2 = math.log(A / E) - math.log(R / Ihh)
        rows.append({"age_band": band, "step": "gap_ecv", "measure": "asking rent / median ECV young earner income",
                     "numerator_eur_month": A, "denominator_eur_month": round(E, 2), "value_pct": round(100 * A / E, 1),
                     "source": "CJE asking rent; ECV 2025 PY010N", "n_persons": len(earners)})
        for lab, x in (("asking rent vs rent paid", math.log(A / R)),
                       ("median ECV young earner vs the tenants' own income", math.log(Iown / E)),
                       ("own income vs household income (sharing)", math.log(Ihh / Iown))):
            rows.append({"age_band": band, "step": "gap_ecv", "measure": f"share of the log gap: {lab}", "value_pct": round(100 * x / gap2, 1),
                         "source": f"log gap {gap2:.3f}", "n_persons": len(T)})
        # the CJE's own shared-flat ratio, and what young tenants who share pay per adult
        sharers = [p for p in T if p["htype"] == "shared_or_other" and adults.get(p["hh"], 0) >= 2]
        per_adult = lambda p: p["rent"] / adults[p["hh"]]
        rows += [
            {"age_band": band, "step": "shared", "measure": "CJE: median room asking rent (400 EUR) / median young net salary", "numerator_eur_month": ROOM,
             "denominator_eur_month": round(S, 2), "value_pct": round(100 * ROOM / S, 1), "source": "CJE 2025 report"},
            {"age_band": band, "step": "shared", "measure": "young tenants sharing with flatmates or relatives: median rent per adult", "numerator_eur_month": round(wmed(sharers, per_adult), 1),
             "n_persons": len(sharers), "n_households": len({p["hh"] for p in sharers})},
            {"age_band": band, "step": "shared", "measure": "the same: median of rent per adult / own net personal income", "value_pct": round(100 * wmed([p for p in sharers if (p["pinc"] or 0) > 0], lambda p: 12 * per_adult(p) / p["pinc"]), 1),
             "n_persons": len([p for p in sharers if (p["pinc"] or 0) > 0])},
        ]
        # who they live with
        tw = sum(p["w"] for p in T)
        for ht in ("alone", "couple", "couple_with_children", "single_parent", "shared_or_other", "other"):
            g = [p for p in T if p["htype"] == ht]
            rows.append({"age_band": band, "step": "household_type", "measure": f"share living as: {ht}",
                         "value_pct": round(100 * sum(p["w"] for p in g) / tw, 1), "n_persons": len(g)})
        # renting alone: the CJE scenario, among those who do it
        rows += [
            {"age_band": band, "step": "alone", "measure": "living alone: median rent paid", "numerator_eur_month": round(wmed(alone, lambda p: p["rent"]), 1), "n_persons": len(alone)},
            {"age_band": band, "step": "alone", "measure": "living alone: median own net income per month", "denominator_eur_month": round(wmed(alone, lambda p: p["inc"] / 12), 1), "n_persons": len(alone)},
            {"age_band": band, "step": "alone", "measure": "living alone: median rent / income", "value_pct": round(100 * wmed(alone, lambda p: rent_ratio(p)), 1), "n_persons": len(alone)},
            {"age_band": band, "step": "alone", "measure": "living alone: overburdened (>40%)", "value_pct": round(ob_share(alone), 1), "n_persons": len(alone)},
            {"age_band": band, "step": "movers", "measure": "moved in the last 12 months: median rent paid", "numerator_eur_month": round(wmed(movers, lambda p: p["rent"]), 1), "n_persons": len(movers)},
            {"age_band": band, "step": "movers", "measure": "same dwelling 12 months ago: median rent paid", "numerator_eur_month": round(wmed(stayers, lambda p: p["rent"]), 1), "n_persons": len(stayers)},
            {"age_band": band, "step": "movers", "measure": "moved in the last 12 months: median rent / income", "value_pct": round(100 * wmed(movers, lambda p: rent_ratio(p)), 1), "n_persons": len(movers)},
            {"age_band": band, "step": "movers", "measure": "moved in the last 12 months: overburdened (>40%)", "value_pct": round(ob_share(movers), 1), "n_persons": len(movers)},
            {"age_band": band, "step": "able", "measure": "all young people whose own net income keeps the asking rent at or below 30%", "value_pct": round(share_able(0.30), 1), "n_persons": len(young_all)},
            {"age_band": band, "step": "able", "measure": "all young people whose own net income keeps the asking rent at or below 40%", "value_pct": round(share_able(0.40), 1), "n_persons": len(young_all)},
            {"age_band": band, "step": "able", "measure": "young wage earners (PY010N > 0) whose own net income keeps the asking rent at or below 40%",
             "value_pct": round(100 * sum(p["w"] for p in earners if (p["pinc"] or 0) >= 12 * A / 0.4) / sum(p["w"] for p in earners), 2), "n_persons": len(earners)},
            {"age_band": band, "step": "able", "measure": "young wage earners whose net wage alone keeps the asking rent at or below 40%",
             "value_pct": round(100 * sum(p["w"] for p in earners if p["py010n"] >= 12 * A / 0.4) / sum(p["w"] for p in earners), 2), "n_persons": len(earners)},
            {"age_band": band, "step": "ecv_salary", "measure": "median net employee cash income (PY010N > 0), all young people, per month", "denominator_eur_month": round(wmed([p for p in emp if (p.get('py010n') or 0) > 0], lambda p: p['py010n'] / 12), 1) if any('py010n' in p for p in emp) else "", "n_persons": len(emp)},
        ]
    with open(D / "cje_reconciliation.csv", "w", newline="", encoding="utf-8") as f:
        keys = ["age_band", "step", "measure", "numerator_eur_month", "denominator_eur_month", "value_pct", "source",
                "n_persons", "n_households"]
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})

    # the CJE's own ECV-based figures for young renter households (tenure 3 or 4). The CJE's «gasto medio
    # en alquiler» is total housing cost (HH070: rent plus community fees and utilities), as its method
    # note says. Two household definitions: an emancipated member aged 16-29 (the CJE's «hogar joven»),
    # or a responsible person (HB080) aged 16-29.
    def cje_ob(p):
        if p["hc"] is None or p["inc"] is None:
            return None
        return 12 * p["hc"] > 0.4 * p["inc"] if p["inc"] > 0 else True
    own = []
    variants = []
    for hlab, kind in (("an emancipated member aged 16-29", "emancipated"), ("a responsible person aged 16-29", "responsible")):
        for agekey, alab in (("age", "age at interview"), ("age_end", "age at end of income year")):
            for tens, tlab in (((3, 4), "tenure 3 or 4"), ((3,), "tenure 3 only")):
                hh = {}
                for p in ps:
                    young = in_band(p, "16-29", agekey) and ((not p["par"]) if kind == "emancipated" else p["is_resp"])
                    if young and p["ten"] in tens and p["wh"] > 0 and p["hc"] is not None and p["inc"] is not None:
                        hh.setdefault(p["hh"], p)
                H = list(hh.values())
                wts = [p["wh"] for p in H]
                mean_hc = wmean([p["hc"] for p in H], wts)
                variants.append(mean_hc)
                own.append({"households": hlab, "variant": f"{alab}; {tlab}",
                            "measure": "mean monthly housing cost HH070 (the CJE's «gasto medio en alquiler»)",
                            "cje": CJE["mean_rent_renter_households"], "ours": round(mean_hc, 1), "n_households": len(H)})
                own.append({"households": hlab, "variant": f"{alab}; {tlab}",
                            "measure": "share with 12 x HH070 > 40% of HY020 (CJE definition)", "cje": CJE["overburden_renter_households"],
                            "ours": round(100 * sum(w for p, w in zip(H, wts) if cje_ob(p)) / sum(wts), 1), "n_households": len(H)})
                if kind == "emancipated" and agekey == "age" and tens == (3, 4):
                    own.append({"households": hlab, "variant": f"{alab}; {tlab}", "measure": "mean monthly rent HH060",
                                "cje": "", "ours": round(wmean([p["rent"] for p in H if p["rent"] is not None],
                                                               [p["wh"] for p in H if p["rent"] is not None]), 1), "n_households": len(H)})
                    own.append({"households": hlab, "variant": f"{alab}; {tlab}",
                                "measure": "the CJE's 30%: its 780 EUR x 12 / its own median young household income (31.167,83); arithmetic, not a test",
                                "cje": CJE["pct_income_renter_households"],
                                "ours": round(100 * 12 * CJE["mean_rent_renter_households"] / CJE["household_income_annual"], 1), "n_households": ""})
    own.append({"households": "", "variant": "", "measure": "range of our mean HH070 over the eight variants",
                "cje": CJE["mean_rent_renter_households"], "ours": f"{min(variants):.1f}-{max(variants):.1f}", "n_households": ""})
    own.append({"households": "", "variant": "", "measure": "asking rent x 12 / CJE median young household income", "cje": CJE["pct_household"],
                "ours": round(100 * 12 * A / CJE["household_income_annual"], 1), "n_households": ""})
    with open(D / "cje_own_ecv_figures.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["households", "variant", "measure", "cje", "ours", "n_households"])
        w.writeheader()
        w.writerows(own)
    print("written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
