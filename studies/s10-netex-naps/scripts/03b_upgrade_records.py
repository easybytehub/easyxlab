#!/usr/bin/env python3
"""S10 step 3b — bookkeeping for records produced before the last rule/parameter changes.

1. XSD parameters: records written before `xsd_params` was stored get them from the run logs
   (work/validate*.log): the 16 datasets finished before the interruption of 2026-10-02 ~22:06 ran
   with XSD_BUDGET=300 MB and MAX_XSD_BYTES=400 MB; all others with 150 MB / 150 MB.
2. Rules v3 changes that can be derived from the stored summary without re-scanning:
   no XML declaration is no longer "non-UTF-8"; U+FFFD is split from double encoding (exact when
   all occurrences are among the stored examples); VERSION-MISSING becomes info; source per finding.
   Records whose v3 result needs a re-scan (French-profile rules, open-ended validity) are re-scanned
   by `CHECKS_ONLY=1 03_validate.py <slug>` instead (see STATUS.md) and are left untouched here.
"""
import glob, json, os, sys
S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(S, "prototype"))
from netex_lint.core import SOURCES

FIRST16 = {"FR_5cec026c634f415f64fc9715_83580", "FR_5e3836e88b4c41404eb3d9aa_81423", "FR_63b4c3d2998fd84635a80dca_80466",
           "FR_63b4c3d22989785f7e9dde9c_82389", "FR_658626a9e96365230bac182c_81473", "FR_66985b97b0421c1296444b0c_82320",
           "FR_6038d0cdcb69d16225b11e23_83176", "FR_63b4c3d25c38a3ee979dde9c_80464", "FR_63b4c3d35e8da006139dde9c_80426",
           "FR_66ce6955a79183f15b22771c_82156", "FR_668d09dea847603d391cbe9b_81935", "FR_63b4c3d2d7857ab0c49dde9a_83711",
           "FR_6853c089b3ed5781f6adfdf7_83195", "LU_latest", "BE_indigo_open_data_be_d47e59fd_cd09_4e61_b4e8_36abbaea186e",
           "BE_interparking_belgium_car_park_locations_and_number_of_spa"}
for p in sorted(glob.glob(os.path.join(S, "data", "per_dataset", "*.json"))):
    r = json.load(open(p)); ch = False
    if "xsd_params" not in r:
        big = r["slug"] in FIRST16
        r["xsd_params"] = {"xsd_budget": 300_000_000 if big else 150_000_000,
                           "max_xsd_bytes": 400_000_000 if big else 150_000_000,
                           "errors_categorised_per_document": 20000, "source": "inferred from run logs by 03b"}
        ch = True
    if r.get("rules_version") == 2 and "summary" in r:
        f = [x for x in r["findings"] if x["rule"] not in ("ENCODING-NOT-UTF8", "ENCODING-MOJIBAKE")]
        enc = r["summary"].get("encodings", {})
        non = sum(c for e, c in enc.items() if e not in ("UTF-8", "UTF8", "NONE"))
        if non:
            f.append({"rule": "ENCODING-NOT-UTF8", "severity": "warning", "count": non,
                      "message": f"Documents declaring an encoding other than UTF-8: {enc}", "examples": []})
        if enc.get("NONE"):
            f.append({"rule": "ENCODING-NO-DECLARATION", "severity": "info", "count": enc["NONE"],
                      "message": "Documents without an XML declaration (read as UTF-8 by default; not an error).", "examples": []})
        old = next((x for x in r["findings"] if x["rule"] == "ENCODING-MOJIBAKE"), None)
        if old:
            rep = [e for e in old["examples"] if "�" in e]; moj = [e for e in old["examples"] if "�" not in e]
            exact = old["count"] <= len(old["examples"])
            if moj or not exact:
                f.append({"rule": "ENCODING-MOJIBAKE", "severity": "warning", "count": len(moj) if exact else old["count"] - len(rep),
                          "message": "Text looks double-encoded (UTF-8 read as Latin-1)." + ("" if exact else " (split from U+FFFD approximate)"),
                          "examples": moj})
            if rep:
                f.append({"rule": "ENCODING-REPLACEMENT-CHAR", "severity": "warning", "count": len(rep),
                          "message": "Text contains U+FFFD: a character was lost before publication.", "examples": rep})
        for x in f:
            if x["rule"] == "VERSION-MISSING":
                x["severity"] = "info"
            x["source"] = SOURCES.get(x["rule"], "")
        r["findings"] = f
        r["rules_version"] = "3-upgraded-from-2"
        ch = True
    if ch:
        json.dump(r, open(p, "w"), indent=1, ensure_ascii=False, default=str)
        print("updated", r["slug"], r.get("rules_version"))
