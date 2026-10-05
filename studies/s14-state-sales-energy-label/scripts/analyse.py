#!/usr/bin/env python3
"""Merge the rule-based classification with the lot review and write every published table in
data/ (METHOD.md §1.6-1.9, §9).

    python3 scripts/analyse.py work/auto data/review_verdicts.csv [work/auto_frozen]

The optional third argument is the lot table built with the frozen parser (before deviation D1);
when given, data/d1_comparison.csv reports the headline with and without D1.

Inputs (row level, not published): <auto>/lots_auto.csv, <auto>/notices_auto.csv,
<auto>/review_queue.csv, and the review verdicts. A verdict row holds the final scope and
energy status of one lot; a verdict whose lot_key ends in '#rN' and names `split_from` is a lot
that the review split out of an 'unsplit' or 'not_described' record.

Outputs (published): data/lots.csv, data/notices.csv, data/by_seller.csv,
data/scope_reasons.csv, data/energy_status.csv, data/sensitivity.csv, data/review.csv,
data/review_agreement.csv, data/summary.json.
"""
import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "data")

STATE_GROUPS = ("TGSS", "Patrimonio del Estado (DEH)", "INVIED (Defensa)", "GIESE (Interior)", "FOGASA",
                "ADIF / Renfe", "Port authorities", "SEPES / Casa 47", "Mutuas (Seguridad Social)")
# Rules (METHOD §1.6 and §9). The per-lot columns are named rating_stated_<rule>: they say whether
# the notice states the energy rating for a covered lot. They are not legal findings: whether a
# BOE notice is «oferta, promoción y publicidad» (art. 15.2 RD 390/2021) is unsettled.
RULES = ("primary", "two_letters", "lenient", "faq_3_2_e", "strict_exempt")
# grounds of a declared exemption that count against the seller under each rule
BAD_GROUNDS = {"faq_3_2_e": {"3.2.e_part"},
               "strict_exempt": {"3.2.e_part", "none_stated", "other", "ruin"}}


def clean_body(b):
    """Readable name of the selling body, from the title's wording."""
    import re
    b = re.sub(r"^(la |el |los )", "", b.strip())
    b = re.sub(r"^Resolución (emitida con fecha .*? por (la )?|de (la )?)", "", b)
    b = re.sub(r"^(la |el )", "", b)
    b = re.sub(r"\s+convocando .*$", "", b)
    b = b.replace(" (TGSS)", "").replace(" - ", "-").replace("HUESCA", "Huesca")
    b = re.sub(r"Seguridad Social (en|de) ", "Seguridad Social de ", b)
    b = re.sub(r"Hacienda (en|de) (el )?", "Hacienda en ", b)
    return b[:1].upper() + b[1:]


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1))


def pct(k, n):
    return round(100 * k / n, 1) if n else None


def read(p):
    return list(csv.DictReader(open(p, encoding="utf-8")))


def write(name, rows, fields=None):
    fields = fields or (list(rows[0].keys()) if rows else ["empty"])
    with open(os.path.join(D, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def comply(scope, energy, both, ground, rule):
    """yes / no / n/a: does the notice state the rating for this lot, under one rule.
    primary: one letter suffices; two_letters: both consumption and emissions letters (the
    recognised document's press-ad minimum, to which art. 17.3 refers); lenient: a reference to a
    certificate or «en trámite» also counts; faq_3_2_e: declarations of art. 3.2.e for a part of a
    building count as covered lots without the rating (the non-binding FAQ no. 7 reading);
    strict_exempt: as faq_3_2_e, plus declared exemptions with no valid ground."""
    if rule in BAD_GROUNDS and scope == "excluded" and energy == "exempt_declared" and ground in BAD_GROUNDS[rule]:
        return "no"
    if scope != "covered":
        return "n/a"
    if energy == "rating":
        if rule == "two_letters" and not both:
            return "no"
        return "yes"
    if rule == "lenient" and energy in ("certificate_reference", "pending"):
        return "yes"
    return "no"


def col(rule):
    return f"rating_stated_{rule}"


def norm(t):
    return " ".join(t.split())


def d1_comparison(frozen_dir, lots, final, kept, texts):
    """Headline with the frozen parser's lots. Notices whose lots are the same under both
    parsers keep their reviewed outcomes. In the notices D1 re-split, each frozen-parser lot is
    one record: it is covered if any D1 lot it contains is covered, and without the rating if any
    covered lot it contains lacks it; D1 lots that the frozen parser left in the general text are
    not lots at all."""
    flots = read(os.path.join(frozen_dir, "lots_auto.csv"))
    ftexts = {}
    for fn in os.listdir(os.path.join(frozen_dir, "lots_text")):
        for l in json.load(open(os.path.join(frozen_dir, "lots_text", fn), encoding="utf-8"))["lots"]:
            ftexts[l["lot_key"]] = norm(l["text"])
    by_notice_d1 = defaultdict(list)
    for r in lots:
        by_notice_d1[r["boe_id"]].append(r["lot_key"])
    by_notice_fr = defaultdict(list)
    for r in flots:
        by_notice_fr[r["boe_id"]].append(r["lot_key"])
    changed = sorted(b for b in set(by_notice_d1) | set(by_notice_fr)
                     if sorted(by_notice_d1.get(b, [])) != sorted(by_notice_fr.get(b, []))
                     or any(ftexts.get(k) != norm(texts.get(k, "")) for k in by_notice_fr.get(b, [])))
    out = []
    for x in kept:
        if x["boe_id"] not in changed:
            out.append((x["seller_group"], x["scope"], x["c_primary"]))
    detail = []
    for b in changed:
        d1_keys = by_notice_d1.get(b, [])
        for fk in by_notice_fr.get(b, []):
            ft = ftexts[fk]
            inside = [k for k in d1_keys if norm(texts.get(k, ""))[:150] and
                      (norm(texts.get(k, ""))[:150] in ft or ft[:150] in norm(texts.get(k, "")))]
            rows = [y for k in inside for y in kept if y.get("_parent") == k]
            if not rows:
                continue
            cov = [y for y in rows if y["scope"] == "covered"]
            if cov:
                sc, c = "covered", ("no" if any(y["c_primary"] == "no" for y in cov) else "yes")
            elif any(y["scope"] == "undeterminable" for y in rows):
                sc, c = "undeterminable", "n/a"
            else:
                sc, c = "excluded", "n/a"
            out.append((rows[0]["seller_group"], sc, c))
            detail.append(dict(boe_id=b, frozen_lot=fk, d1_lots_inside=len(inside), scope=sc, rating_stated_primary=c))
    cov = [o for o in out if o[1] == "covered"]
    no = sum(1 for o in cov if o[2] == "no")
    lo, hi = wilson(no, len(cov))
    with_fix = [x for x in kept if x["scope"] == "covered"]
    rows = [dict(parser="with D1 (headline)", covered=len(with_fix), without_label=sum(x["c_primary"] == "no" for x in with_fix),
                 pct_without=pct(sum(x["c_primary"] == "no" for x in with_fix), len(with_fix)),
                 ci_low=wilson(sum(x["c_primary"] == "no" for x in with_fix), len(with_fix))[0],
                 ci_high=wilson(sum(x["c_primary"] == "no" for x in with_fix), len(with_fix))[1]),
            dict(parser="frozen parser (without D1)", covered=len(cov), without_label=no, pct_without=pct(no, len(cov)), ci_low=lo, ci_high=hi)]
    by = Counter()
    for g, sc, c in out:
        if sc == "covered":
            by[(g, c)] += 1
    for g in sorted({g for g, _ in by}):
        rows.append(dict(parser=f"frozen parser: {g}", covered=by[(g, "yes")] + by[(g, "no")], without_label=by[(g, "no")],
                         pct_without=pct(by[(g, "no")], by[(g, "yes")] + by[(g, "no")]), ci_low="", ci_high=""))
    write("d1_comparison.csv", rows)
    write("d1_frozen_lots.csv", detail)
    added = Counter(x["seller_group"] for x in with_fix if x["c_primary"] == "no") - Counter(g for g, sc, c in out if sc == "covered" and c == "no")
    return dict(changed_notices=changed, frozen_covered=len(cov), frozen_without=no, frozen_pct=pct(no, len(cov)),
                frozen_ci=[lo, hi], added_without_by_seller=dict(added),
                added_covered=len(with_fix) - len(cov), added_without=sum(x["c_primary"] == "no" for x in with_fix) - no)


def main(auto, verdicts_path, frozen_dir=None):
    lots = read(os.path.join(auto, "lots_auto.csv"))
    notices = read(os.path.join(auto, "notices_auto.csv"))
    queue = {q["lot_key"]: q["review_set"] for q in read(os.path.join(auto, "review_queue.csv"))}
    verdicts = read(verdicts_path) if os.path.exists(verdicts_path) else []
    vby = {v["lot_key"]: v for v in verdicts}
    keys = {r["lot_key"] for r in lots}
    orphans = [v["lot_key"] for v in verdicts if (v.get("split_from") or v["lot_key"]) not in keys]
    if orphans:
        raise SystemExit(f"{len(orphans)} review verdicts do not match any lot (parser changed?): {orphans[:5]}")
    splits = defaultdict(list)
    for v in verdicts:
        if v.get("split_from"):
            splits[v["split_from"]].append(v)

    final = []
    for r in lots:
        base = dict(r)
        children = splits.get(r["lot_key"])
        targets = [(c["lot_key"], c) for c in children] if children else [(r["lot_key"], vby.get(r["lot_key"]))]
        for key, v in targets:
            x = dict(base)
            x["lot_key"] = key
            x["lot"] = key.split("#", 1)[1]
            x["review_set"] = (v.get("review_set") if v and v.get("review_set") not in ("", None) else queue.get(r["lot_key"], ""))
            x["_parent"] = r["lot_key"]
            x["seller_body"] = clean_body(r["seller_body"])
            x["reviewed"] = "yes" if v else "no"
            x["auto_scope"], x["auto_energy"] = r["scope"], r["energy_status"]
            if v:
                x["scope"] = v["scope_final"]
                x["scope_reason"] = v["scope_reason_final"] or (r["scope_reason"] if v["scope_final"] == r["scope"] else "")
                x["energy_status"] = v["energy_final"]
                x["letters"] = v.get("letters_final", x["letters"]) if v["energy_final"] == "rating" else ""
                if v.get("both_final") not in (None, ""):
                    x["both_indicators"] = v["both_final"]
                if v.get("lot_type_final"):
                    x["lot_type"] = v["lot_type_final"]
                x["exempt_ground"] = v.get("exempt_ground", "")
                x["review_note"] = v.get("note", "")
                x["change"] = v.get("change", "")
            else:
                x["exempt_ground"], x["review_note"], x["change"] = "", "", ""
            if x["scope"] == "drop":
                x["dropped"] = "yes"
            else:
                x["dropped"] = "no"
            for rule in RULES:
                x[col(rule)] = comply(x["scope"], x["energy_status"], x["both_indicators"] in ("1", 1, True, "True"),
                                      x["exempt_ground"], rule)
            x["c_primary"] = x[col("primary")]
            final.append(x)
    kept = [x for x in final if x["dropped"] == "no"]

    # ---- published per-lot table
    pub_fields = ["lot_key", "boe_id", "lot", "date", "section", "seller_group", "seller_body", "split_method",
                  "lot_type", "scope", "scope_reason", "energy_status", "energy_level", "letters", "both_indicators",
                  "label_included"] + [col(r) for r in RULES] + [
                  "auto_scope", "auto_energy", "reviewed", "review_set", "exempt_ground", "change", "review_note"]
    for x in final:
        x["label_included"] = {"yes": "yes", "no": "no"}.get(x["c_primary"], "excluded" if x["scope"] == "excluded"
                                                             else ("undeterminable" if x["scope"] == "undeterminable" else "dropped"))
    write("lots.csv", [{k: x.get(k, "") for k in pub_fields} for x in sorted(final, key=lambda z: (z["date"], z["lot_key"]))], pub_fields)

    # ---- by seller (primary rule) and overall
    def block(rows, rule="primary"):
        cov = [x for x in rows if x["scope"] == "covered"]
        no = sum(1 for x in cov if x[f"c_{rule}"] == "no")
        lo, hi = wilson(no, len(cov))
        return dict(lots=len(rows), covered=len(cov), excluded=sum(x["scope"] == "excluded" for x in rows),
                    undeterminable=sum(x["scope"] == "undeterminable" for x in rows),
                    without_label=no, with_label=len(cov) - no, pct_without=pct(no, len(cov)), ci_low=lo, ci_high=hi)
    groups = sorted(set(x["seller_group"] for x in kept), key=lambda g: -sum(1 for x in kept if x["seller_group"] == g and x["scope"] == "covered"))
    by = []
    for g in ["ALL"] + groups:
        rows = kept if g == "ALL" else [x for x in kept if x["seller_group"] == g]
        b = block(rows)
        b["seller_group"] = g
        b["notices"] = len(set(x["boe_id"] for x in rows))
        by.append(b)
    write("by_seller.csv", by, ["seller_group", "notices", "lots", "covered", "excluded", "undeterminable",
                                "with_label", "without_label", "pct_without", "ci_low", "ci_high"])

    # ---- by body within the main groups (covered lots only)
    bodies = defaultdict(lambda: Counter())
    for x in kept:
        if x["scope"] == "covered":
            bodies[(x["seller_group"], x["seller_body"])][x["c_primary"]] += 1
    write("by_body.csv", [dict(seller_group=g, seller_body=b, covered=c["yes"] + c["no"], with_label=c["yes"], without_label=c["no"])
                          for (g, b), c in sorted(bodies.items(), key=lambda kv: (kv[0][0], -sum(kv[1].values())))])

    # ---- scope reasons and energy statuses
    sr = Counter((x["scope"], x["scope_reason"]) for x in kept)
    write("scope_reasons.csv", [dict(scope=s, reason=r, lots=n) for (s, r), n in sorted(sr.items(), key=lambda kv: (kv[0][0], -kv[1]))])
    es = Counter((x["seller_group"], x["energy_status"], x["energy_level"]) for x in kept if x["scope"] == "covered")
    write("energy_status.csv", [dict(seller_group=g, energy_status=s, level=l, covered_lots=n) for (g, s, l), n in sorted(es.items())])

    # ---- sensitivities
    sens = []
    for rule in RULES:
        cov = [x for x in kept if x["scope"] == "covered" or x[col(rule)] == "no"]
        no = sum(1 for x in cov if x[col(rule)] == "no")
        lo, hi = wilson(no, len(cov))
        sens.append(dict(measure=rule, covered=len(cov), without_label=no, pct_without=pct(no, len(cov)), ci_low=lo, ci_high=hi))
    # distinct properties: a lot announced again later counts once. Key: its set of cadastral
    # references; for a lot without one, the opening of its description (lot label, numbers and
    # prices removed). Lots split in the review use the review note.
    import re as _re
    import unicodedata as _ud
    texts = {}
    tdir = os.path.join(auto, "lots_text")
    for fn in os.listdir(tdir):
        for l in json.load(open(os.path.join(tdir, fn), encoding="utf-8"))["lots"]:
            texts[l["lot_key"]] = l["text"]
    refs = {r["lot_key"]: r["cadastral_refs"] for r in lots}

    def pkey(x):
        if refs.get(x["lot_key"]):
            return "ref:" + refs[x["lot_key"]]
        t = texts.get(x["lot_key"]) or x["review_note"]
        t = "".join(c for c in _ud.normalize("NFKD", t.lower()) if not _ud.combining(c))
        t = _re.sub(r"^\W*(lote|finca)?\s*(n[ºo°.]*)?\s*\w{0,4}\s*[-.:;)]+", " ", t)
        t = _re.sub(r"[^a-z ]+", " ", t)
        t = _re.sub(r"\b(antigu[oa]s?|lote|unico|subasta|primera|segunda|tercera|cuarta|tipo|licitacion)\b", " ", t)
        return x["seller_group"] + ":" + " ".join(t.split())[:60]
    seen, distinct = set(), []
    for x in sorted((x for x in kept if x["scope"] == "covered"), key=lambda z: (z["date"], z["lot_key"])):
        k = pkey(x)
        if k in seen:
            continue
        seen.add(k)
        distinct.append(x)
    no = sum(1 for x in distinct if x["c_primary"] == "no")
    lo, hi = wilson(no, len(distinct))
    sens.append(dict(measure="distinct_properties", covered=len(distinct), without_label=no, pct_without=pct(no, len(distinct)), ci_low=lo, ci_high=hi))
    dbs = []
    for g in groups:
        d = [x for x in distinct if x["seller_group"] == g]
        if d:
            dbs.append(dict(seller_group=g, distinct_covered=len(d), without_label=sum(x["c_primary"] == "no" for x in d)))
    write("by_seller_distinct.csv", dbs)
    st = [x for x in kept if x["scope"] == "covered" and x["seller_group"] in STATE_GROUPS]
    no = sum(1 for x in st if x["c_primary"] == "no")
    lo, hi = wilson(no, len(st))
    sens.append(dict(measure="state_bodies_only", covered=len(st), without_label=no, pct_without=pct(no, len(st)), ci_low=lo, ci_high=hi))
    write("sensitivity.csv", sens)

    # ---- notices
    nl = defaultdict(list)
    for x in kept:
        nl[x["boe_id"]].append(x)
    pubn = []
    for n in notices:
        ls = nl.get(n["boe_id"], [])
        cov = [x for x in ls if x["scope"] == "covered"]
        yes = sum(x["c_primary"] == "yes" for x in cov)
        n2 = {k: n[k] for k in ("boe_id", "date", "section", "seller_group", "seller_body", "kind", "split_method")}
        n2["seller_body"] = clean_body(n2["seller_body"])
        n2["n_lots"] = len(ls)
        n2["covered_lots"] = len(cov)
        n2["covered_with_label"] = yes
        n2["notice_label"] = "" if not cov else ("all" if yes == len(cov) else ("none" if yes == 0 else "some"))
        n2["dropped_in_review"] = "yes" if n["kind"] == "offer" and n["boe_id"] in {x["boe_id"] for x in final if x["dropped"] == "yes"} and not ls else "no"
        pubn.append(n2)
    write("notices.csv", pubn)

    # ---- review table and agreement
    rev = [dict(lot_key=x["lot_key"], review_set=x["review_set"], auto_scope=x["auto_scope"], scope=x["scope"],
                auto_energy=x["auto_energy"], energy=x["energy_status"], exempt_ground=x["exempt_ground"],
                change=x["change"], note=x["review_note"]) for x in final if x["reviewed"] == "yes"]
    write("review.csv", rev)
    agree = []
    for s in ("R1", "R2", "R3", "R4"):
        rr = [x for x in final if x["reviewed"] == "yes" and x["review_set"] == s]
        same_scope = sum(x["auto_scope"] == x["scope"] for x in rr)
        same_energy = sum(x["auto_energy"] == x["energy_status"] for x in rr)
        same_comp = sum((comply(x["auto_scope"], x["auto_energy"], False, "", "primary") == x["c_primary"]) for x in rr)
        agree.append(dict(review_set=s, reviewed=len(rr), same_scope=same_scope, same_energy=same_energy,
                          same_primary_outcome=same_comp, dropped=sum(x["dropped"] == "yes" for x in rr)))
    write("review_agreement.csv", agree)

    # ---- notice level by seller
    nb = []
    for g in ["ALL"] + groups:
        ns = [n for n in pubn if n["notice_label"] and (g == "ALL" or n["seller_group"] == g)]
        c = Counter(n["notice_label"] for n in ns)
        nb.append(dict(seller_group=g, notices_with_covered_lots=len(ns), label_in_all=c["all"], label_in_some=c["some"],
                       label_in_none=c["none"]))
    write("notice_label_by_seller.csv", nb)

    # ---- what the notices say for covered lots without the label
    st = Counter((x["seller_group"], x["energy_status"]) for x in kept if x["scope"] == "covered" and x["c_primary"] == "no")
    write("without_label_statements.csv", [dict(seller_group=g, energy_status=e, lots=n) for (g, e), n in sorted(st.items())])

    # ---- declared exemptions
    ex = [x for x in kept if x["energy_status"] == "exempt_declared"]
    de = Counter((x["seller_group"], x["scope"], x["exempt_ground"] or "") for x in ex)
    write("declared_exemptions.csv", [dict(seller_group=g, scope=sc, ground=gr, lots=n) for (g, sc, gr), n in sorted(de.items())])

    # ---- lots by type and scope
    ts = Counter((x["lot_type"], x["scope"]) for x in kept)
    write("lots_by_type.csv", [dict(lot_type=t, scope=sc, lots=n) for (t, sc), n in sorted(ts.items())])

    # ---- classifier against the review (reviewed lots that the classifier called covered)
    cv = Counter()
    for x in final:
        if x["reviewed"] != "yes" or x["auto_scope"] != "covered":
            continue
        a = comply("covered", x["auto_energy"], False, "", "primary")
        b = "dropped" if x["dropped"] == "yes" else (x["c_primary"] if x["scope"] == "covered" else "not covered")
        cv[(x["review_set"], a, b)] += 1
    write("classifier_vs_review.csv", [dict(review_set=r, classifier=a, review=b, lots=n) for (r, a, b), n in sorted(cv.items())])

    # ---- D1: the headline with the frozen parser (no lot-extraction fix)
    d1 = None
    if frozen_dir and os.path.exists(os.path.join(frozen_dir, "lots_auto.csv")):
        d1 = d1_comparison(frozen_dir, lots, final, kept, texts)

    # ---- summary
    allb = by[0]
    off = [n for n in notices if n["kind"] == "offer"]
    S = dict(
        period=["2025-01-01", "2026-09-30"],
        candidate_notices=len(notices), offer_notices=len(off),
        notice_kinds=dict(Counter(n["kind"] for n in notices)),
        lots_total=len(final), lots_kept=len(kept), lots_dropped=len(final) - len(kept),
        covered=allb["covered"], excluded=allb["excluded"], undeterminable=allb["undeterminable"],
        headline=dict(without_label=allb["without_label"], covered=allb["covered"], pct=allb["pct_without"],
                      ci=[allb["ci_low"], allb["ci_high"]]),
        by_seller={b["seller_group"]: dict(covered=b["covered"], without_label=b["without_label"], pct=b["pct_without"],
                                          notices=b["notices"]) for b in by[1:]},
        notices_with_covered=sum(1 for n in pubn if n["notice_label"]),
        notices_label=dict(Counter(n["notice_label"] for n in pubn if n["notice_label"])),
        sensitivity={s["measure"]: dict(covered=s["covered"], without_label=s["without_label"], pct=s["pct_without"]) for s in sens},
        reviewed=len(rev),
        notice_label_by_seller={n["seller_group"]: {k: n[k] for k in ("notices_with_covered_lots", "label_in_all", "label_in_some", "label_in_none")} for n in nb},
        declared_exemptions=len(ex),
        declared_exemptions_32e_part_of_building=sum(1 for x in ex if x["exempt_ground"] == "3.2.e_part"),
        declared_exemptions_32e=sum(1 for x in ex if x["exempt_ground"].startswith("3.2.e")),
        scope_reasons={f"{s} | {r}": n for (s, r), n in sr.items()},
        review_sets=dict(Counter(x["review_set"] or "none" for x in final if x["reviewed"] == "yes")),
        offer_notices_kept=len({x["boe_id"] for x in kept}),
        offer_notices_removed_in_review=len(off) - len({x["boe_id"] for x in kept}),
        d1=d1,
    )
    # ---- added 2026-10-05 for claims.csv: the abstract's dates and the figures that had no key
    def long_date(iso, day=True):
        y, m, d_ = (int(v) for v in iso.split("-"))
        month = ("January February March April May June July August September October November December").split()[m - 1]
        return f"{d_} {month} {y}" if day else f"{month} {y}"
    S["period_long"] = dict(start=long_date(S["period"][0]), end=long_date(S["period"][1]))
    S["period_months"] = dict(start=long_date(S["period"][0], False), end=long_date(S["period"][1], False))
    S["lots_not_covered"] = len(kept) - S["covered"]
    S["declared_exemptions_by_scope"] = dict(Counter(x["scope"] for x in ex))
    S["covered_land_garage_storage"] = sum(1 for x in kept if x["scope"] == "covered" and x["lot_type"] in ("land", "garage", "storage"))
    # added 2026-10-05 (closing review): covered lots in any category the README abstract calls out of scope. Land,
    # garages and storage rooms; industrial or agricultural lots not checked by the review against «de baja demanda
    # energética» (deviation D7: only the reviewed lots moved from excluded to covered, with a stated rating); and
    # shell premises (MITECO FAQ no. 19), counted by their scope reason
    S["covered_with_exclusion_category"] = sum(
        1 for x in kept if x["scope"] == "covered" and (
            x["lot_type"] in ("land", "garage", "storage")
            or (x["lot_type"] == "industrial_agricultural"
                and not (x["reviewed"] == "yes" and x["change"] == "scope excluded>covered"))
            or "no. 19" in x["scope_reason"]))
    S["lots_shell_premises"] = sum(1 for x in kept if "no. 19" in x["scope_reason"])
    # covered lots by seller and lot type, for «mostly commercial premises» (closing review 2, 2026-10-05)
    S["covered_by_seller_lot_type"] = {g: dict(Counter(x["lot_type"] for x in kept if x["scope"] == "covered"
                                                       and x["seller_group"] == g).most_common())
                                       for g in sorted({x["seller_group"] for x in kept if x["scope"] == "covered"})}
    # process figures, not in data/: the independent agent's re-reading (METHOD.md, «Independent check») and the
    # year of the development notices on which the rules were written (paper.md §3, July-December 2024)
    S["independent_recheck"] = dict(lots=40, agreed=40)
    S["rules_development_year"] = 2024
    json.dump(S, open(os.path.join(D, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(S["headline"]), json.dumps(S["by_seller"], ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
