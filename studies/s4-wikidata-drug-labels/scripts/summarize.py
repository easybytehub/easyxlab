#!/usr/bin/env python3
"""Write data/summary.json: every figure that claims.csv checks, computed from the published files.

Offline, standard library only, run after 05_metrics.py and 06_corrections.py (scripts/run.sh).
Shares and precisions are fractions at full precision: the error estimate uses the exact
precision TP / (TP + FP), not the 3-decimal value printed in metrics.json, and the Wilson bound
is not rounded either.

Inputs: data/flags.csv, data/label_counts.json, data/validation_sample.csv,
data/validation_verdicts.csv, data/validation_disease_script.csv, data/earlier_check.csv,
data/frozen/{extract_meta.json,drugs.jsonl}, corrections.csv, and the lists of the earlier
exploratory review in scripts/legacy/ (drugs.py, diseases.py).

data/earlier_check.csv transcribes paper §5.5 by hand; its verdicts were checked against
data/frozen/drugs.jsonl and data/flags.csv on 2026-10-05 (all seven: Q113368879 fr «Coumaphène»,
Q408535 fa «seroquel», Q240642 hi «valporic acid» and fa «والپروات سدیم», Q18216 ur «Aspirin»,
Q773449 zh «左旋甲狀腺素鈉», f_doubled «B2424.» and «I10-I1515.»).
"""
from __future__ import annotations

import ast
import collections
import csv
import json
import math
from pathlib import Path

S = Path(__file__).resolve().parent.parent
D = S / "data"
LANGS = ["en", "es", "fr", "de", "it", "pt", "pl", "ru", "uk", "tr", "ar", "fa", "ur", "hi", "bn",
         "zh", "ja", "ko", "sw", "am"]  # = 05_metrics.LANGS
NAMED_FOUR = ["ur", "fa", "ru", "hi"]  # the languages the abstracts name as where errors concentrate
LATIN_MAJOR = ["es", "fr", "de", "it", "pt", "pl"]  # major Latin-script languages, English excluded
ERR_A = {"a_latin", "a_other", "a_nonlatin"}  # = 05_metrics.ERR_A
VALPROATE = "Q240642"


def rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def wilson_low(k: int, n: int, z: float = 1.96) -> float:
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h)


def wilson_high(k: int, n: int, z: float = 1.96) -> float:
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return min(1.0, c + h)


def prec(tp: int, fp: int) -> dict:
    n = tp + fp
    return {"tp": tp, "decided": n, "precision": tp / n, "ci95_low": wilson_low(tp, n), "ci95_high": wilson_high(tp, n)}


def legacy_list_len(name: str, var: str) -> int:
    tree = ast.parse((S / "scripts" / "legacy" / name).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == var for t in node.targets):
            return len(ast.literal_eval(node.value))
    raise KeyError(f"{var} not in scripts/legacy/{name}")


def main() -> None:
    flags = rows(D / "flags.csv")
    counts = json.loads((D / "label_counts.json").read_text(encoding="utf-8"))
    meta = json.loads((D / "frozen" / "extract_meta.json").read_text(encoding="utf-8"))
    sample = {r["sample_id"]: r for r in rows(D / "validation_sample.csv")}
    verd = {r["sample_id"]: r["verdict"] for r in rows(D / "validation_verdicts.csv")}
    dis_script = rows(D / "validation_disease_script.csv")

    by_det, by_sub = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for sid, s in sample.items():
        by_det[s["detector"]][verd.get(sid, "UNREVIEWED")] += 1
        by_sub[s["subtype"]][verd.get(sid, "UNREVIEWED")] += 1
    assert not any(c["UNREVIEWED"] for c in by_det.values())
    P = {k: prec(c["TP"], c["FP"]) for k, c in by_det.items()}
    icd10_fmt = collections.Counter()
    for sub, c in by_sub.items():
        if sub.startswith("f_") and sub != "f_icd11":
            icd10_fmt.update(c)
    dsc = collections.Counter(r["verdict"] for r in dis_script)

    drug_flags = [f for f in flags if f["domain"] == "drug"]
    est = est_low = 0.0
    rate = {}
    for lang in LANGS:
        e = e_low = 0.0
        for det in "abce":
            n_flags = len({f["qid"] for f in drug_flags if f["lang"] == lang and f["detector"] == det
                           and (det != "a" or f["subtype"] in ERR_A)})
            e += n_flags * P[det]["precision"]
            e_low += n_flags * P[det]["ci95_low"]
        est, est_low = est + e, est_low + e_low
        rate[lang] = 1000 * e / counts["drug"][lang]
    labels = sum(counts["drug"][lang] for lang in LANGS)

    fa_a = {(f["qid"], f["value"]) for f in drug_flags if f["lang"] == "fa" and f["subtype"] in ERR_A}
    fa_a_qids = {q for q, _ in fa_a}
    fa_atc_qids = {q for q, v in fa_a if "ATC" in v}
    d_flags = [f for f in flags if f["subtype"] == "d_diff_en"]
    icd10_bad = [f for f in flags if f["detector"] == "f" and f["reference"] == "P494" and f["subtype"] != "f_range"]
    doubled = [f for f in flags if f["subtype"] == "f_doubled"]
    obsolete = [f for f in flags if f["subtype"] == "g_obsolete"]
    corr = rows(S / "corrections.csv")
    early = rows(D / "earlier_check.csv")
    valproate = next(json.loads(ln) for ln in open(D / "frozen" / "drugs.jsonl", encoding="utf-8")
                     if f'"qid": "{VALPROATE}"' in ln)

    out = {
        "drug_items": meta["n_drug_items"],
        "drug_items_counts": counts["drug_items"],
        "disease_items": counts["disease_items"],
        "languages": len(LANGS),
        "detectors": len({f["detector"] for f in flags}),
        "labels": labels,
        "sample": {"flags": len(sample), "disease_script": len(dis_script), "total": len(sample) + len(dis_script)},
        "precision": {
            **P,
            "disease_script": prec(dsc["TP"], dsc["FP"]),
            "icd10_format": prec(icd10_fmt["TP"], icd10_fmt["FP"]),
            "g_obsolete": prec(by_sub["g_obsolete"]["TP"], by_sub["g_obsolete"]["FP"]),
            "g_dup": prec(by_sub["g_dup"]["TP"], by_sub["g_dup"]["FP"]),
            "f_icd11": prec(by_sub["f_icd11"]["TP"], by_sub["f_icd11"]["FP"]),
            "g_format": prec(by_sub["g_format"]["TP"], by_sub["g_format"]["FP"]),
            "g_obsolete_split": prec(by_sub["g_obsolete_split"]["TP"], by_sub["g_obsolete_split"]["FP"]),
        },
        "est_errors": est,
        "est_errors_low": est_low,
        "est_share": est / labels,
        "est_share_low": est_low / labels,
        "rate_per_1000": rate,
        "rate_named_four_min": min(rate[lang] for lang in NAMED_FOUR),
        "rate_others_max": max(rate[lang] for lang in LANGS if lang not in NAMED_FOUR),
        "rate_latin_major_min": min(rate[lang] for lang in LATIN_MAJOR),
        "rate_latin_major_max": max(rate[lang] for lang in LATIN_MAJOR),
        "fa_script_flags": len(fa_a_qids),
        "fa_script_flags_atc": len(fa_atc_qids),
        "shared_label_labels": len(d_flags),
        "shared_label_groups": len({f["extra"] for f in d_flags}),
        "icd10_values": counts["icd10_values"],
        "icd10_invalid": len(icd10_bad),
        "icd10_invalid_share": len(icd10_bad) / counts["icd10_values"],
        "icd10_doubled": len(doubled),
        "atc_values": counts["atc_values"],
        "atc_obsolete": len(obsolete),
        "atc_obsolete_share": len(obsolete) / counts["atc_values"],
        "corrections_rows": len(corr),
        "corrections_proposed": sum(r["in_qs"] == "yes" for r in corr),
        "earlier_check": {
            "reported": len(early),
            "confirmed": sum(r["verdict"] == "confirmed" for r in early),
            "not_confirmed": sum(r["verdict"] == "not confirmed" for r in early),
            "drugs_listed": legacy_list_len("drugs.py", "ATC") - 1,  # minus the 'dolutegravir(old)' duplicate
            "diseases_listed": legacy_list_len("diseases.py", "D"),
            "valproate_last_modified": valproate["modified"][:10],
        },
    }
    (D / "summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {D / 'summary.json'}")


if __name__ == "__main__":
    main()
