#!/usr/bin/env python3
"""Parse every candidate notice into lots and apply the frozen rule-based classifier.

    python3 scripts/build_lots.py work/candidates_study.csv work/auto
    python3 scripts/build_lots.py work/candidates_study.csv work/auto_frozen --frozen-parser

With --frozen-parser the lots are split by scripts/lots_frozen.py, the parser as frozen before
deviation D1 (METHOD.md §9), byte-identical to the frozen copy; everything else is the same.

Writes (row level, kept in work/, not published as such):
  <out>/notices_auto.csv  one row per candidate notice: kind, seller, split method, n_lots
  <out>/lots_auto.csv     one row per lot of every 'offer' notice: type, scope, energy status,
                          compliance under the primary and lenient rules, evidence snippet
  <out>/lots_text/<BOE id>.json  the lot texts, for the one-by-one review

Energy status of a lot (METHOD.md §1.5): the lot's own text decides; when the lot says nothing,
a statement in the notice's general text (before the first lot or after the last one) applies,
and the level is recorded as 'notice'.
"""
import csv
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classify as C  # noqa: E402
if "--frozen-parser" in sys.argv:
    import lots_frozen as LT  # noqa: E402
    sys.argv.remove("--frozen-parser")
else:
    import lots as LT  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOT = os.path.join(HERE, "data", "raw", "notices")


def lot_rows(cand):
    p = os.path.join(NOT, cand["id"] + ".html.gz")
    if not os.path.exists(p):
        return None, []
    n = LT.parse_notice(gzip.open(p).read().decode("utf-8", "replace"))
    title = n["title"] or cand["title"]
    text = "\n".join(n["paragraphs"])
    kind = C.notice_kind(title, text)
    group, body = C.seller(title, cand.get("department", ""))
    pre, lots, tail, method = LT.split_lots(n["paragraphs"], title)
    general = "\n".join(pre + tail)
    gen = C.energy_status(general)
    notice = dict(boe_id=cand["id"], date=cand["date"], section=cand["section"], department=cand["department"],
                  seller_group=group, seller_body=body, kind=kind, split_method=method, n_lots=len(lots),
                  general_energy=gen["status"], title=title)
    rows, texts = [], []
    if kind != "offer":
        return notice, []
    ctx = "\n".join(pre[:6]) + " " + title
    for label, ps in lots:
        t = "\n".join(ps)
        e = C.energy_status(t)
        level = "lot"
        if e["status"] == "none" and gen["status"] != "none":
            e, level = dict(gen), "notice"
        ty = C.lot_type(t, title if method in ("single", "unsplit", "not_described") else "", ctx)
        if method == "not_described":
            sc, why = "undeterminable", "properties not described in the notice"
        else:
            sc, why = C.scope(t, ty, e)
        refs = LT.cadastral_refs(t)
        rows.append(dict(
            lot_key=f"{cand['id']}#{label}", boe_id=cand["id"], date=cand["date"], section=cand["section"],
            seller_group=group, seller_body=body, split_method=method, lot=label, n_lots=len(lots),
            lot_type=ty, scope=sc, scope_reason=why, energy_status=e["status"], energy_level=level,
            letters=e["letters"], both_indicators=int(bool(e.get("both_indicators"))), compliant_primary=C.compliance(sc, e, "primary"),
            compliant_lenient=C.compliance(sc, e, "lenient"), n_cadastral_refs=len(refs),
            cadastral_refs=" ".join(refs), surface_m2=C.surface_m2(t) or "",
            evidence=e["evidence"].replace("\n", " ")[:300]))
        texts.append({"lot_key": f"{cand['id']}#{label}", "text": t})
    if texts:
        os.makedirs(os.path.join(OUTDIR, "lots_text"), exist_ok=True)
        json.dump({"boe_id": cand["id"], "title": title, "general": general, "lots": texts},
                  open(os.path.join(OUTDIR, "lots_text", cand["id"] + ".json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
    return notice, rows


def main(cand_csv, out):
    global OUTDIR
    OUTDIR = out
    os.makedirs(out, exist_ok=True)
    cands = list(csv.DictReader(open(cand_csv, encoding="utf-8")))
    notices, lots, missing = [], [], 0
    for c in cands:
        n, rows = lot_rows(c)
        if n is None:
            missing += 1
            notices.append(dict(boe_id=c["id"], date=c["date"], section=c["section"], department=c["department"],
                                seller_group="", seller_body="", kind="not_fetched", split_method="", n_lots=0,
                                general_energy="", title=c["title"]))
            continue
        notices.append(n)
        lots += rows
    for name, rows in (("notices_auto.csv", notices), ("lots_auto.csv", lots)):
        with open(os.path.join(out, name), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    print(f"{len(cands)} candidate notices ({missing} not fetched), {sum(n['kind'] == 'offer' for n in notices)} offers, {len(lots)} lots -> {out}")


OUTDIR = None
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
