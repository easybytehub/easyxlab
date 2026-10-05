#!/usr/bin/env python3
"""Match the parsed licence numbers (work/extract/, private) against the official registries
(data/raw/registries/*_min.csv) and write the published aggregates to data/.

Only aggregates leave this script: counts per area x snapshot x category. No listing id, host
id, licence number or address is written to data/.

    python3 scripts/analyse.py
"""
import csv, json, math, os, re, sys, statistics, unicodedata, hashlib
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from snapshots import SNAPSHOTS, REGION, url, raw_path
from strnum import parse_regional
csv.field_size_limit(10**9)
D = "data"
EXT = "work/extract"
CATS = ["in_registry", "in_registry_other_municipality", "registered_wrong_form", "not_found", "after_registry_date",
        "no_open_registry", "placeholder", "malformed", "national_tu_only", "non_tourist",
        "national_other_only", "exempt", "empty"]
AREAS = [a for a, *_ in SNAPSHOTS]
AND_PARTIAL = ("tourist apartments", "rural house", "rural complex")


def wilson_full(k, n, z=1.96):
    """Wilson 95% interval in percent, unrounded (wilson() below rounds to one decimal)."""
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1))


def pct(k, n):
    return round(100 * k / n, 1) if n >= 10 else None


def row_share(k, n):
    lo, hi = wilson(k, n) if n >= 10 else (None, None)
    return {"n": k, "denominator": n, "pct": pct(k, n), "ci95_low": lo, "ci95_high": hi}


# Deviation 1 (METHOD.md §9): municipalities whose current official name (as in the RTC)
# differs from the name Inside Airbnb uses for the neighbourhood polygon, after merger or renaming.
MUNI_ALIAS = {"castell platja aro": "castell aro platja aro s agaro", "calonge": "calonge sant antoni",
              "boadella emporda": "boadella escaules", "masarac": "masarac vilarnadal",
              "brunyola": "brunyola sant marti sapresa",
              "brunyola sant marti sapresa sant marti sapresa": "brunyola sant marti sapresa",
              "saus": "saus camallera llampaies"}


def norm_muni_raw(s):
    """norm_muni without the alias table (used only to report deviation 1)."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[’'`´]", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(l|la|el|les|els|los|las|d|de|del|i|y)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_muni(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[’'`´]", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(l|la|el|les|els|los|las|d|de|del|i|y)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return MUNI_ALIAS.get(s, s)


# ------------------------------------------------------------------ registries

def load_registries():
    reg = {"catalonia": {}, "valencia": {}, "andalucia": {}, "nyc": {}}
    meta = {}
    for r in csv.DictReader(open("data/raw/registries/rtc_min.csv", encoding="utf-8")):
        reg["catalonia"][r["number"].strip().upper()] = {"muni": norm_muni(r["municipality"]), "type": r["type"],
                                                        "control": r["extra"], "prov": r["province"]}
    for r in csv.DictReader(open("data/raw/registries/gva_min.csv", encoding="utf-8")):
        reg["valencia"][r["number"].strip().upper()] = {"muni": norm_muni(r["municipality"]), "type": "VUT",
                                                       "date": r["date"]}
    skipped = Counter()
    for r in csv.DictReader(open("data/raw/registries/rta_min.csv", encoding="utf-8")):
        p = parse_regional(r["number"], "andalucia")
        if p.status in ("ok", "placeholder") and p.registry_open:
            reg["andalucia"][p.key] = {"muni": norm_muni(r["municipality"]), "type": r["type"], "group": r["extra"]}
        else:
            skipped[re.sub(r"[\d]", "9", r["number"])[:8]] += 1
    meta["rta_rows_not_keyed"] = sum(skipped.values())
    ose_listing = defaultdict(set)
    for r in csv.DictReader(open("data/raw/registries/ose_min.csv", encoding="utf-8")):
        if r["type"] == "registration":
            reg["nyc"][r["number"].upper()] = {"muni": norm_muni(r["province"]), "status": r["status"]}
        elif r["type"].startswith("listing:Airbnb"):
            m = re.search(r"(\d{4,})", r["extra"])
            if m:
                ose_listing[m.group(1)].add(r["number"].upper())
    nyc_max = max(int(k[-7:]) for k in reg["nyc"])
    meta["nyc_registry_max_number"] = nyc_max
    meta["nyc_registry_registrations"] = len(reg["nyc"])
    meta["nyc_registry_status"] = dict(Counter(v["status"] for v in reg["nyc"].values()))
    meta["nyc_registry_airbnb_listing_links"] = sum(len(v) for v in ose_listing.values())
    for k in ("catalonia", "valencia", "andalucia"):
        meta[f"{k}_registry_keys"] = len(reg[k])
    return reg, ose_listing, nyc_max, meta


# ------------------------------------------------------------------ wrong-form rules (post-review)

# Deviation 5 (METHOD.md §9): rules added AFTER the adversarial review, i.e. after the freeze. A
# number that is not in the registry as written, but is a registered dwelling of the listing's
# municipality written in one of three recognisable wrong forms, is "registered_wrong_form".
#   R1  Catalonia: leading zeros dropped and the RTC control digit appended
#       (HUTB-00abcd with control ef shown as HUTB-abcdef).
#   R2  Catalonia: wrong province code in a HUT prefix (e.g. HUTB-n shown where HUTG-n is
#       registered in the listing's municipality).
#   R3  Málaga: a registered VUT number with one extra trailing digit (a six-digit number above
#       the series maximum whose first five digits are registered in the municipality). Not
#       applied in Sevilla, where 61% of numbers below the series maximum are registered in the
#       city, so a match would carry almost no evidence.
WF_AREAS = {"R1": {"barcelona", "girona"}, "R2": {"barcelona", "girona"}, "R3": {"malaga"}}
HUT_PREFIXES = ("HUTB", "HUTG", "HUTT", "HUTL", "HUTCC", "HUTTE", "HUTVA")


class WrongForm:
    def __init__(self, reg):
        self.cat = reg["catalonia"]
        self.cat_muni, self.cat_top = defaultdict(set), Counter()
        ctl = defaultdict(Counter)
        for k, v in self.cat.items():
            p, n = k.split("-")
            self.cat_muni[(p, v["muni"])].add(int(n))
            self.cat_top[p] = max(self.cat_top[p], int(n))
            ctl[p][v["control"]] += 1
        # probability that a two-digit string equals the control digit of a given entry by chance
        self.ctl_chance = {p: sum((x / sum(c.values())) ** 2 for x in c.values()) for p, c in ctl.items()}
        self.and_muni, self.and_top = defaultdict(set), Counter()
        for k, v in reg["andalucia"].items():
            t, pp, n = k.split("/")
            self.and_muni[(f"{t}/{pp}", v["muni"])].add(int(n))
            self.and_top[f"{t}/{pp}"] = max(self.and_top[f"{t}/{pp}"], int(n))

    def check(self, r):
        """(rule matched or None, {rule: chance probability} for each rule this listing was
        eligible for). Called only for listings whose number is not found as written."""
        area, key, muni = r["area"], r["reg_key"], norm_muni(r["municipality"])
        chance = {}
        if r["region"] == "catalonia" and area in WF_AREAS["R1"]:
            p, n = key.split("-")
            cand, ctl = int(n[:4]), n[4:6]
            if cand and cand in self.cat_muni[(p, muni)]:
                chance["R1"] = self.ctl_chance.get(p, 0.0)
                reg_ctl = self.cat.get(f"{p}-{cand:06d}", {}).get("control", "")
                if reg_ctl != "" and int(reg_ctl) == int(ctl):
                    return "R1", chance
        if r["region"] == "catalonia" and area in WF_AREAS["R2"] and key.split("-")[0] in HUT_PREFIXES:
            p, n = key.split("-")
            n = int(n)
            chance["R2"] = sum(len(self.cat_muni[(q, muni)]) / self.cat_top[q] for q in HUT_PREFIXES
                               if q != p and self.cat_top[q])
            for q in HUT_PREFIXES:
                if q != p and n in self.cat_muni[(q, muni)]:
                    return "R2", chance
        if r["region"] == "andalucia" and area in WF_AREAS["R3"] and r["reg_tourist"] == "1":
            t, pp, n = key.split("/")
            ser, n = f"{t}/{pp}", int(n)
            if n >= 100000 and n > self.and_top[ser]:
                five = [x for x in self.and_muni[(ser, muni)] if 10000 <= x <= 99999]
                chance["R3"] = len(five) / 90000
                if n // 10 in self.and_muni[(ser, muni)]:
                    return "R3", chance
        return None, chance


# ------------------------------------------------------------------ classification

def classify(r, reg, nyc_max, wf=None):
    """Primary category of one extracted listing row (METHOD.md §1.5) and match detail."""
    region = r["region"]
    st = r["reg_status"]
    detail = {}
    if st == "ok":
        # Deviation 2 (METHOD.md §9): OpenRTA lists only 178 tourist-apartment establishments and
        # 51 rural houses for all of Andalucía, so those series are treated as having no usable registry.
        if region == "andalucia" and r["reg_kind"] in AND_PARTIAL:
            return "no_open_registry", detail
        if r["reg_open"] == "1":
            key = r["reg_key"]
            if region == "nyc" and int(key[-7:]) > nyc_max:
                return "after_registry_date", detail
            hit = reg[region].get(key)
            if hit is None:
                if wf is not None:
                    rule, chance = wf.check(r)
                    detail = {"rule": rule, "chance": chance}
                    if rule:
                        return "registered_wrong_form", detail
                return "not_found", detail
            detail = hit
            if hit["muni"] == norm_muni(r["municipality"]):
                return "in_registry", detail
            return "in_registry_other_municipality", detail
        return "no_open_registry", detail
    if st == "placeholder":
        return "placeholder", detail
    if st == "malformed":
        return "malformed", detail
    nk = r["nat_kind"]
    if r["nat_status"] == "ok":
        if nk == "national-TU":
            return "national_tu_only", detail
        if nk == "national-NT":
            return "non_tourist", detail
        return "national_other_only", detail
    if st == "exempt" or r["nat_status"] == "exempt":
        return "exempt", detail
    if r["nat_status"] == "malformed":
        return "malformed", detail
    return "empty", detail


def num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def main():
    reg, ose_listing, nyc_max, regmeta = load_registries()
    wf = WrongForm(reg)
    rows_all = {}
    for area, path, before, after in SNAPSHOTS:
        for d in (before, after):
            rows = list(csv.DictReader(open(f"{EXT}/{area}_{d}.csv", encoding="utf-8")))
            for r in rows:
                r["cat"], r["_hit"] = classify(r, reg, nyc_max, wf)
                # the category under the frozen rules (no wrong-form rules), kept for reporting
                r["cat_frozen"] = "not_found" if r["cat"] == "registered_wrong_form" else r["cat"]
                r["short"] = int((num(r["minimum_nights"], 999) or 999) < 30)
            rows_all[(area, d)] = rows

    snap_label = {}
    for area, path, before, after in SNAPSHOTS:
        snap_label[(area, before)] = "before"
        snap_label[(area, after)] = "after"

    # ---------------- categories.csv
    out = []
    for (area, d), rows in rows_all.items():
        pops = {"all": rows, "active": [r for r in rows if r["active"] == "1"]}
        if area == "nyc":
            pops["active_short_stay"] = [r for r in rows if r["active"] == "1" and r["short"] == 1]
        for pop, rs in pops.items():
            c = Counter(r["cat"] for r in rs)
            for cat in CATS:
                if area != "nyc" and cat == "after_registry_date":
                    continue
                out.append(dict(area=area, region=REGION[area], snapshot=d, period=snap_label[(area, d)],
                                population=pop, category=cat, **row_share(c.get(cat, 0), len(rs))))
    write_csv(f"{D}/categories.csv", out)

    # ---------------- h1: tourist-dwelling numbers vs registry (Spain), and all open series
    h1, h1s = [], []
    for (area, d), rows in rows_all.items():
        if area in ("madrid", "nyc"):
            continue
        act = [r for r in rows if r["active"] == "1" and r["reg_status"] == "ok" and r["reg_open"] == "1"]
        td = [r for r in act if r["reg_tourist"] == "1"]
        c = Counter(r["cat"] for r in td)
        n = len(td)
        rec = dict(area=area, region=REGION[area], snapshot=d, period=snap_label[(area, d)], shown=n)
        for cat in ("in_registry", "in_registry_other_municipality", "registered_wrong_form", "not_found"):
            s = row_share(c.get(cat, 0), n)
            rec[cat] = s["n"]; rec[cat + "_pct"] = s["pct"]
            rec[cat + "_ci95"] = f"{s['ci95_low']}–{s['ci95_high']}" if s["ci95_low"] is not None else ""
        # the frozen rule had no wrong-form category: its "not found" = wrong form + not found
        s = row_share(c.get("registered_wrong_form", 0) + c.get("not_found", 0), n)
        rec["not_found_frozen_rule"] = s["n"]; rec["not_found_frozen_rule_pct"] = s["pct"]
        rec["not_found_frozen_rule_ci95"] = f"{s['ci95_low']}–{s['ci95_high']}" if s["ci95_low"] is not None else ""
        wfr = Counter(r["_hit"].get("rule") for r in td if r["cat"] == "registered_wrong_form")
        exp, elig = Counter(), Counter()
        for r in td:
            if r["cat"] in ("registered_wrong_form", "not_found"):
                for rule, pr in r["_hit"].get("chance", {}).items():
                    exp[rule] += pr
                    elig[rule] += 1
        for rule in ("R1", "R2", "R3"):
            rec[f"wrong_form_{rule}_eligible"] = elig.get(rule, 0)
            rec[f"wrong_form_{rule}"] = wfr.get(rule, 0)
            rec[f"wrong_form_{rule}_expected_by_chance"] = round(exp.get(rule, 0.0), 1)
        rec["wrong_form_expected_by_chance"] = round(sum(exp.values()), 1)
        found_any = c.get("in_registry", 0) + c.get("in_registry_other_municipality", 0)
        rec["found_any_municipality"] = found_any
        dn = {r["reg_key"] for r in td}
        dnf = {r["reg_key"] for r in td if r["cat"] == "not_found"}
        rec["distinct_numbers"] = len(dn)
        rec["distinct_not_found"] = len(dnf)
        rec["distinct_not_found_pct"] = pct(len(dnf), len(dn))
        h1.append(rec)
        kinds = Counter((r["reg_kind"], r["cat"]) for r in act)
        for kind in sorted({k for k, _ in kinds}):
            tot = sum(v for (k, _), v in kinds.items() if k == kind)
            for cat in ("in_registry", "in_registry_other_municipality", "registered_wrong_form", "not_found"):
                h1s.append(dict(area=area, snapshot=d, series=kind, category=cat, **row_share(kinds.get((kind, cat), 0), tot)))
    write_csv(f"{D}/h1_tourist_numbers.csv", h1)
    write_csv(f"{D}/h1_by_series.csv", h1s)

    # ---------------- national numbers
    nat = []
    for (area, d), rows in rows_all.items():
        if area == "nyc":
            continue
        act = [r for r in rows if r["active"] == "1"]
        n = len(act)
        shows = [r for r in act if r["nat_status"] == "ok"]
        rec = dict(area=area, snapshot=d, period=snap_label[(area, d)], active=n,
                   shows_national=len(shows), shows_national_pct=pct(len(shows), n),
                   national_TU=sum(r["nat_kind"] == "national-TU" for r in shows),
                   national_NT=sum(r["nat_kind"] == "national-NT" for r in shows),
                   national_other_prefix=sum(r["nat_kind"] == "national-other" for r in shows),
                   national_only_TU=sum(r["cat"] == "national_tu_only" for r in act),
                   non_tourist=sum(r["cat"] == "non_tourist" for r in act),
                   regional_exempt_statement=sum(r["reg_status"] == "exempt" for r in act),
                   regional_exempt_seasonal=sum(r["reg_status"] == "exempt" and r["reg_exempt_reason"] == "seasonal rental" for r in act),
                   nt_with_regional_exempt=sum(r["nat_kind"] == "national-NT" and r["reg_status"] == "exempt" for r in act))
        nat.append(rec)
    write_csv(f"{D}/national_numbers.csv", nat)

    # ---------------- signals of tourist use
    sig = []
    for (area, d), rows in rows_all.items():
        act = [r for r in rows if r["active"] == "1"]
        groups = {c: [r for r in act if r["cat"] == c] for c in ("non_tourist", "exempt", "in_registry", "not_found", "national_tu_only", "empty")}
        # addition (METHOD.md §9): every active listing that shows a national NT number, whatever its regional field
        groups["shows_NT_number"] = [r for r in act if r["nat_kind"] == "national-NT"]
        if area == "nyc":
            groups = {c: [r for r in act if r["cat"] == c] for c in ("exempt", "in_registry", "empty", "after_registry_date")}
        for c, rs in groups.items():
            n = len(rs)
            mn = [num(r["minimum_nights"], None) for r in rs]
            ltm = [int(r["reviews_ltm"]) for r in rs]
            le4 = sum(1 for x in mn if x is not None and x <= 4)
            le31 = sum(1 for x in mn if x is not None and x <= 31)
            ge12 = sum(1 for x in ltm if x >= 12)
            ent = sum(r["room_type"] == "Entire home/apt" for r in rs)
            rec = dict(area=area, snapshot=d, period=snap_label[(area, d)], category=c, n=n,
                       min_nights_le4=le4, min_nights_le4_pct=pct(le4, n), min_nights_le4_ci95=ci(le4, n),
                       min_nights_le31=le31, min_nights_le31_pct=pct(le31, n),
                       reviews_ltm_ge12=ge12, reviews_ltm_ge12_pct=pct(ge12, n),
                       median_reviews_ltm=statistics.median(ltm) if ltm else None,
                       entire_home=ent, entire_home_pct=pct(ent, n))
            sig.append(rec)
    write_csv(f"{D}/signals.csv", sig)

    # ---------------- NYC specifics
    nyc = []
    for d in [x for (a, x) in rows_all if a == "nyc"]:
        rows = rows_all[("nyc", d)]
        act = [r for r in rows if r["active"] == "1" and r["short"] == 1]
        shown = [r for r in act if r["reg_status"] == "ok"]
        testable = [r for r in shown if r["cat"] != "after_registry_date"]
        st = Counter(r["_hit"].get("status") for r in testable if r["cat"].startswith("in_registry"))
        # OSE associates some Airbnb listing numbers with a registration (as of 2025-06-25)
        linked = [r for r in shown if r["id"] in ose_listing]
        agree = sum(r["reg_key"] in ose_listing[r["id"]] for r in linked)
        ent = sum(r["room_type"] == "Entire home/apt" for r in shown)
        nyc.append(dict(snapshot=d, period=snap_label[("nyc", d)], active_short_stay=len(act),
                        shows_ose_number=len(shown), testable=len(testable),
                        found=sum(r["cat"].startswith("in_registry") for r in testable),
                        found_same_borough=sum(r["cat"] == "in_registry" for r in testable),
                        not_found=sum(r["cat"] == "not_found" for r in testable),
                        after_registry_date=len(shown) - len(testable),
                        found_registered=st.get("Registered", 0), found_expired=st.get("Expired", 0),
                        found_terminated=st.get("Terminated", 0),
                        listings_linked_by_ose=len(linked), linked_same_number=agree,
                        shown_entire_home=ent,
                        exempt=sum(r["cat"] == "exempt" for r in act), empty=sum(r["cat"] == "empty" for r in act),
                        malformed=sum(r["cat"] == "malformed" for r in act)))
    write_csv(f"{D}/nyc.csv", nyc)

    # ---------------- "Exempt" statements by field and reason
    ex = []
    for (area, d), rows in rows_all.items():
        act = [r for r in rows if r["active"] == "1"]
        c = Counter()
        for r in act:
            if r["reg_status"] == "exempt":
                c[("regional" if area != "nyc" else "licence", r["reg_exempt_reason"])] += 1
            if r["nat_status"] == "exempt":
                c[("national", r["nat_exempt_reason"])] += 1
        for (fld, why), v in sorted(c.items()):
            ex.append(dict(area=area, snapshot=d, period=snap_label[(area, d)], field=fld, reason=why, **row_share(v, len(act))))
    write_csv(f"{D}/exempt_reasons.csv", ex)

    # ---------------- transitions (listings present in both snapshots)
    tr = []
    for area, path, before, after in SNAPSHOTS:
        b = {r["id"]: r for r in rows_all[(area, before)]}
        a = {r["id"]: r for r in rows_all[(area, after)]}
        both = set(a) & set(b)
        c = Counter((b[i]["cat"], a[i]["cat"]) for i in both)
        for (x, y), v in sorted(c.items()):
            tr.append(dict(area=area, before=before, after=after, category_before=x, category_after=y, n=v))
        tr.append(dict(area=area, before=before, after=after, category_before="(only before)", category_after="", n=len(set(b) - set(a))))
        tr.append(dict(area=area, before=before, after=after, category_before="", category_after="(only after)", n=len(set(a) - set(b))))
    write_csv(f"{D}/transitions.csv", tr)

    # ---------------- diagnostics
    diag = {"registries": regmeta}
    # In-range chance match (MAJOR 1.1 of the review): for each listing showing a tourist-series
    # number, the share of the numbers below the highest number the registry has issued in that
    # series that are registered in the listing's municipality, i.e. the probability that a random
    # number BELOW THE REGISTRY'S HIGHEST NUMBER would be "found" there; averaged over listings.
    # For comparison, the same share over the whole range the format allows (all 6-digit HUT
    # numbers, 7-digit CV-VUT and OSE numbers, 5-digit VUT numbers or the series maximum if higher).
    def series_of(region, key):
        if region == "catalonia":
            return key.split("-")[0], int(key.split("-")[1])
        if region == "valencia":
            return "CV-VUT", int(key[6:13])
        if region == "andalucia":
            t, pp, n = key.split("/")
            return f"{t}/{pp}", int(n)
        return "OSE", int(key[-7:])
    FORMAT_MAX = {"catalonia": 999999, "valencia": 9999999, "andalucia": 99999, "nyc": 9999999}
    dens = defaultdict(Counter); top = Counter()
    for region in ("catalonia", "valencia", "andalucia", "nyc"):
        for k, v in reg[region].items():
            try:
                ser, n = series_of(region, k)
            except (ValueError, IndexError):
                continue
            dens[(region, ser)][v["muni"]] += 1
            top[(region, ser)] = max(top[(region, ser)], n)
    cm = {}
    for (area, d), rows in rows_all.items():
        if area == "madrid":
            continue
        td = [r for r in rows if r["active"] == "1" and r["reg_status"] == "ok" and r["reg_tourist"] == "1" and r["reg_open"] == "1"]
        vals, fvals, beyond, nf, beyond_fr, nf_fr = [], [], 0, 0, 0, 0
        for r in td:
            ser, n = series_of(r["region"], r["reg_key"])
            t = top.get((r["region"], ser), 0)
            k = dens[(r["region"], ser)].get(norm_muni(r["municipality"]), 0)
            vals.append(k / t if t else 0)
            fvals.append(k / max(FORMAT_MAX[r["region"]], t) if t else 0)
            if r["cat"] == "not_found":
                nf += 1
                beyond += int(n > t)
            if r["cat_frozen"] == "not_found":
                nf_fr += 1
                beyond_fr += int(n > t)
        cm[f"{area} {d}"] = {"listings": len(td),
                             "in_range_chance_match_pct": round(100 * sum(vals) / len(vals), 1) if vals else None,
                             "full_format_chance_match_pct": round(100 * sum(fvals) / len(fvals), 1) if fvals else None,
                             "not_found": nf, "not_found_above_highest_registry_number": beyond,
                             "not_found_frozen_rule": nf_fr, "not_found_frozen_rule_above_highest_registry_number": beyond_fr}
    diag["chance_match"] = cm
    # Catalan control digit
    cd = Counter()
    for (area, d), rows in rows_all.items():
        if REGION[area] != "catalonia":
            continue
        for r in rows:
            if r["active"] == "1" and r["reg_status"] == "ok" and r["reg_extra"] and r["cat"].startswith("in_registry"):
                hit = r["_hit"]
                cd[(d, "agree" if hit.get("control", "").lstrip("0") == r["reg_extra"].lstrip("0") else "differ")] += 1
    diag["catalan_control_digit"] = {f"{k[0]} {k[1]}": v for k, v in sorted(cd.items())}
    # Valencian old format vs current; Andalusian VFT vs VUT
    vm, am = Counter(), Counter()
    for (area, d), rows in rows_all.items():
        for r in rows:
            if r["active"] != "1" or r["reg_status"] != "ok" or r["reg_tourist"] != "1":
                continue
            found = r["cat"].startswith("in_registry")
            if area == "valencia":
                vm[(d, r["reg_extra"] or "current", found)] += 1
            if area in ("malaga", "sevilla"):
                am[(area, d, r["reg_extra"] or "VUT", found)] += 1
    diag["valencia_format_vs_found"] = {f"{k[0]} {k[1]} found={k[2]}": v for k, v in sorted(vm.items())}
    diag["andalucia_series_vs_found"] = {f"{k[0]} {k[1]} {k[2]} found={k[3]}": v for k, v in sorted(am.items())}
    # duplicates among active listings
    dup = []
    for (area, d), rows in rows_all.items():
        act = [r for r in rows if r["active"] == "1" and r["reg_status"] == "ok"]
        by = defaultdict(list)
        for r in act:
            by[r["reg_key"]].append(r)
        multi = {k: v for k, v in by.items() if len(v) > 1}
        multihost = {k: v for k, v in multi.items() if len({r["host_id"] for r in v}) > 1}
        dup.append(dict(area=area, snapshot=d, period=snap_label[(area, d)], active_with_number=len(act),
                        distinct_numbers=len(by), numbers_on_2plus_listings=len(multi),
                        listings_sharing_a_number=sum(len(v) for v in multi.values()),
                        numbers_on_2plus_hosts=len(multihost),
                        listings_sharing_across_hosts=sum(len(v) for v in multihost.values())))
    write_csv(f"{D}/duplicates.csv", dup)
    # evidence for deviations 1 and 2 (METHOD.md §9), recomputed on every run
    dev = {}
    for (area, d), rows in rows_all.items():
        if area == "girona":
            td = [r for r in rows if r["active"] == "1" and r["reg_status"] == "ok" and r["reg_tourist"] == "1" and r["reg_open"] == "1"]
            other_raw = sum(1 for r in td if r["cat"].startswith("in_registry")
                            and r["_hit"]["muni"] != norm_muni_raw(r["municipality"]))
            dev[f"girona {d} other municipality without aliases"] = [other_raw, len(td)]
        if area in ("malaga", "sevilla"):
            pr = [r for r in rows if r["active"] == "1" and r["reg_status"] == "ok" and r["reg_kind"] in AND_PARTIAL]
            dev[f"{area} {d} apartment/rural numbers found in OpenRTA"] = [sum(r["reg_key"] in reg["andalucia"] for r in pr), len(pr)]
    dev["openrta establishments by type"] = dict(Counter(v["type"] for v in reg["andalucia"].values()))
    diag["deviations_evidence"] = dev

    # room type of listings showing a tourist-dwelling number, by H1 category (review 5.1/5.2)
    rt = {}
    for (area, d), rows in rows_all.items():
        if area in ("madrid", "nyc"):
            continue
        c = Counter((r["cat"], r["room_type"]) for r in rows if r["active"] == "1" and r["reg_status"] == "ok"
                    and r["reg_tourist"] == "1" and r["reg_open"] == "1")
        rt[f"{area} {d}"] = {f"{k[0]} | {k[1]}": v for k, v in sorted(c.items())}
    diag["room_type_by_h1_category"] = rt

    # paired listings (present in both snapshots), Spain
    pair = {}
    ex_b = ex_a = both_active = 0
    for area, path, before, after in SNAPSHOTS:
        if area == "nyc":
            continue
        b = {r["id"]: r for r in rows_all[(area, before)]}
        a = {r["id"]: r for r in rows_all[(area, after)]}
        ids = set(a) & set(b)
        # H1 scope: tourist-dwelling number not found (residual) in March
        nf = [i for i in ids if b[i]["cat"] == "not_found" and b[i]["reg_tourist"] == "1"]
        same = sum(1 for i in nf if a[i]["reg_key"] == b[i]["reg_key"] and a[i]["cat"] == "not_found")
        pair[area] = {"in_both": len(ids), "h1_not_found_before": len(nf), "same_number_still_not_found_after": same}
        act = [i for i in ids if a[i]["active"] == "1" and b[i]["active"] == "1"]
        both_active += len(act)
        ex_b += sum(b[i]["reg_status"] == "exempt" for i in act)
        ex_a += sum(a[i]["reg_status"] == "exempt" for i in act)
        pair[area].update({"active_in_both": len(act), "regional_exempt_before": sum(b[i]["reg_status"] == "exempt" for i in act),
                           "regional_exempt_after": sum(a[i]["reg_status"] == "exempt" for i in act)})
    pair["spain"] = {"active_in_both": both_active, "regional_exempt_before": ex_b, "regional_exempt_after": ex_a}
    # composition of the June NT listings: present in March or new (review 6.2)
    for area, path, before, after in SNAPSHOTS:
        if area == "nyc":
            continue
        ids_b = {r["id"] for r in rows_all[(area, before)]}
        act = [r for r in rows_all[(area, after)] if r["active"] == "1"]
        nt = [r for r in act if r["nat_kind"] == "national-NT"]
        le4 = lambda rs: sum(1 for r in rs if (num(r["minimum_nights"], 999) or 999) <= 4)
        old_ = [r for r in nt if r["id"] in ids_b]
        new_ = [r for r in nt if r["id"] not in ids_b]
        pair[area].update({"active_after_not_in_before_file": sum(r["id"] not in ids_b for r in act),
                           "nt_after_in_before_file": len(old_), "nt_after_in_before_file_le4": le4(old_),
                           "nt_after_new": len(new_), "nt_after_new_le4": le4(new_)})
    diag["paired"] = pair

    # how the national number reads: letters after the 6-character prefix (review 3.2)
    lt = Counter()
    for (area, d), rows in rows_all.items():
        if area == "nyc":
            continue
        for r in rows:
            if r["active"] == "1" and r["nat_kind"] in ("national-TU", "national-NT"):
                raw = r["license_raw"]
                m = re.search(r"(ES(?:FC|HF)(?:TU|NT)[0-9A-Za-z/\-]+)", raw)
                tail = m.group(1)[6:] if m else ""
                lt[(r["nat_kind"], "letters after prefix" if re.search(r"[A-Za-z]", tail) else "digits only")] += 1
    diag["national_number_tail"] = {f"{k[0]} {k[1]}": v for k, v in sorted(lt.items())}

    # Catalan regional number embedded at the end of national TU numbers, clean subset only:
    # tail "HUT<prov>-" + 7 digits (first six read as the number) or + 6 digits and a suffix
    emb = Counter()
    for (area, d), rows in rows_all.items():
        if REGION[area] != "catalonia":
            continue
        for r in rows:
            if not (r["active"] == "1" and r["nat_kind"] == "national-TU" and r["reg_status"] == "ok"
                    and r["reg_tourist"] == "1"):
                continue
            m = re.search(r"ES(?:FC|HF)TU[0-9A-Za-z/\-]*?(HUT[A-Z]{1,2})-?(\d{7}|\d{6}-\d{1,3})(?:<|$)", r["license_raw"])
            if not m:
                continue
            k = f"{m.group(1)}-{int(m.group(2)[:6]):06d}"
            group = {"in_registry": "found", "registered_wrong_form": "wrong form", "not_found": "not found"}.get(r["cat"], "other")
            if k == r["reg_key"]:
                rel = "embeds the number shown"
            elif k in reg["catalonia"] and reg["catalonia"][k]["muni"] == norm_muni(r["municipality"]):
                rel = "embeds a different number registered in the municipality"
            else:
                rel = "embeds a different number not registered there"
            emb[(area, d, group, rel)] += 1
    diag["catalan_number_embedded_in_national_TU"] = {" | ".join(k): v for k, v in sorted(emb.items())}
    # Málaga extra-digit cases (R3): does the national number end with the same six digits?
    r3 = Counter()
    for (area, d), rows in rows_all.items():
        for r in rows:
            if r["active"] == "1" and r.get("_hit", {}).get("rule") == "R3":
                digits = r["reg_key"].split("/")[-1]
                m = re.search(r"ES(?:FC|HF)(?:TU|NT)[0-9A-Za-z/\-]*", r["license_raw"])
                r3[(area, d, "national number ends with the same six digits" if m and re.search(r"\D" + digits + "$", m.group(0)) else "other")] += 1
    diag["malaga_extra_digit_in_national_number"] = {" | ".join(k): v for k, v in sorted(r3.items())}
    json.dump(diag, open(f"{D}/diagnostics.json", "w"), indent=1, ensure_ascii=False)

    # ---------------- sources.json (snapshots)
    src = {}
    for area, path, before, after in SNAPSHOTS:
        for d in (before, after):
            p = raw_path(area, d)
            src[f"{area} {d}"] = {"url": url(path, d), "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(),
                                  "listings": len(rows_all[(area, d)]),
                                  "active": sum(r["active"] == "1" for r in rows_all[(area, d)])}
    json.dump({"insideairbnb": src, "registries": json.load(open(f"{D}/sources_registries.json"))},
              open(f"{D}/sources.json", "w"), indent=1, ensure_ascii=False)

    # ---------------- summary.json (headline numbers)
    S = {"h1": {}, "categories_active": {}, "non_tourist_signals": {}, "nyc": nyc,
         "diagnostics": {"chance_match": cm, "paired": pair}}
    for rec in h1:
        S["h1"][f"{rec['area']} {rec['snapshot']}"] = rec
    for rec in out:
        if rec["population"] in ("active", "active_short_stay"):
            S["categories_active"].setdefault(f"{rec['area']} {rec['snapshot']} {rec['population']}", {})[rec["category"]] = [rec["n"], rec["denominator"], rec["pct"], rec["ci95_low"], rec["ci95_high"]]
    for rec in sig:
        S["non_tourist_signals"][f"{rec['area']} {rec['snapshot']} {rec['category']}"] = rec
    # pooled Spain (June): tourist numbers with open registry
    for period in ("before", "after"):
        tot = Counter()
        for rec in h1:
            if rec["period"] == period:
                for k in ("shown", "in_registry", "in_registry_other_municipality", "registered_wrong_form",
                          "not_found", "not_found_frozen_rule", "wrong_form_R1", "wrong_form_R2", "wrong_form_R3"):
                    tot[k] += rec[k]
                tot["wrong_form_expected_by_chance"] += rec["wrong_form_expected_by_chance"]
        S[f"h1_pooled_{period}"] = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in tot.items()}
        for k in ("not_found", "in_registry", "registered_wrong_form", "not_found_frozen_rule", "in_registry_other_municipality"):
            S[f"h1_pooled_{period}"][k + "_ci95"] = wilson(tot[k], tot["shown"])
    # pooled Spain, active listings, before and after: annulled-national-only, any national, exempt statements
    for period in ("before", "after"):
        act = [r for (a, d), rows in rows_all.items() if a not in ("nyc",) and snap_label[(a, d)] == period for r in rows if r["active"] == "1"]
        act5 = [r for r in act if r["area"] != "madrid"]
        S[f"spain_{period}"] = {
            "areas": "barcelona girona valencia malaga sevilla madrid", "active": len(act),
            "national_tu_only": row_share(sum(r["cat"] == "national_tu_only" for r in act), len(act)),
            "shows_national": row_share(sum(r["nat_status"] == "ok" for r in act), len(act)),
            "regional_exempt_statement": row_share(sum(r["reg_status"] == "exempt" for r in act), len(act)),
            "five_areas_active": len(act5),
            "five_areas_national_tu_only": row_share(sum(r["cat"] == "national_tu_only" for r in act5), len(act5))}
    S["listings_total"] = sum(len(v) for v in rows_all.values())
    S["listings_total_active"] = sum(sum(r["active"] == "1" for r in v) for v in rows_all.values())
    # ---------------- figures the abstract quotes (added 2026-10-05; full precision)
    for period in ("before", "after"):
        P = S[f"h1_pooled_{period}"]
        P["not_found_share"] = P["not_found"] / P["shown"]
        P["not_found_ci95_full"] = list(wilson_full(P["not_found"], P["shown"]))
        P["wrong_form_expected_by_chance_full"] = sum(rec["wrong_form_expected_by_chance"] for rec in h1
                                                      if rec["period"] == period)
    S["spain_after"]["regional_exempt_seasonal"] = sum(int(r["n"]) for r in ex if r["period"] == "after"
                                                       and r["field"] == "regional" and r["reason"] == "seasonal rental")
    bcn_after = next(f"{a} {d}" for a, d in snap_label if a == "barcelona" and snap_label[(a, d)] == "after")
    S["barcelona_after"] = {"snapshot": bcn_after.split()[1], "not_found": S["h1"][bcn_after]["not_found"],
                            "not_found_private_room": rt[bcn_after].get("not_found | Private room", 0)}
    pa = [v for v in pair.values() if "h1_not_found_before" in v]
    S["paired_not_found"] = {"areas": len(pa), "before": sum(v["h1_not_found_before"] for v in pa),
                             "same_number_still_not_found_after": sum(v["same_number_still_not_found_after"] for v in pa)}
    spain = [(a, d) for a, d in snap_label if a != "nyc"]
    before_max = max(d for a, d in spain if snap_label[(a, d)] == "before")
    after_min = min(d for a, d in spain if snap_label[(a, d)] == "after")
    after_max = max(d for a, d in spain if snap_label[(a, d)] == "after")
    after_month = {d[:7] for a, d in spain if snap_label[(a, d)] == "after" and a != "madrid"}
    assert after_month == {"2026-06"}, after_month
    S["snapshots"] = {"before_max_ymd": int(before_max.replace("-", "")), "after_min_ymd": int(after_min.replace("-", "")),
                      "after_month": "June 2026", "after_max_ymd": int(after_max.replace("-", ""))}
    # legal dates (paper §2) and the New York registry file (data/sources_registries.json, «as of June 25, 2025»)
    S["dates"] = {"reg_2024_1028_applies": "20 May 2026", "reg_2024_1028_applies_day": "20 May",
                  "reg_2024_1028_applies_ymd": 20260520, "reg_2024_1028": "2024/1028",
                  "ts_judgments_months": "May and June 2026", "ts_judgments": ["19 May", "21 May", "1 June 2026"],
                  "rd_1312_2024_effect": "1 July 2025", "nyc_registry_file": "25 June 2025"}
    # the date of each Spanish registry copy (data/sources_registries.json): the publisher's
    # «rows updated» date where it gives one (RTC), else the API's last update (OpenRTA), else the
    # download (the GVA file is regenerated daily). Added 2026-10-05: «one registry copy serves both
    # snapshots» is checked against these, not read off the prose.
    srcs = json.load(open(f"{D}/sources_registries.json"))
    def copy_ymd(m):
        if m.get("rows_updated_utc"):
            t = m["rows_updated_utc"]
        elif m.get("last_update_endpoint"):
            t = json.loads(m["last_update_endpoint"])["date"]
        else:
            t = m["fetched_utc"]
        return int(t[:10].replace("-", ""))
    S["dates"]["registry_copy_ymd"] = {k: copy_ymd(srcs[k]) for k in ("rtc", "gva", "rta")}
    S["dates"]["registry_copy_min_ymd"] = min(S["dates"]["registry_copy_ymd"].values())
    json.dump(S, open(f"{D}/summary.json", "w"), indent=1, ensure_ascii=False)
    print("ok")


def ci(k, n):
    lo, hi = wilson(k, n) if n >= 10 else (None, None)
    return f"{lo}–{hi}" if lo is not None else ""


def write_csv(path, rows):
    if not rows:
        return
    keys = list(rows[0].keys())
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
