#!/usr/bin/env python3
"""S10 step 5: assert every headline number of README.md and paper.md against data/.

Each number is recomputed here from the raw records (data/per_dataset/*.json, data/*.csv),
independently of 04_aggregate.py, and compared with the value the text states. The literal text
must also appear in the named file(s). Exit 1 on any mismatch.
"""
import csv, glob, json, os, statistics, sys
from collections import Counter

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(S, "data")
R = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(D, "per_dataset", "*.json")))]
CAT = list(csv.DictReader(open(os.path.join(D, "catalogue_netex.csv"))))
TXT = {f: open(os.path.join(S, f)).read() for f in ("README.md", "paper.md") if os.path.exists(os.path.join(S, f))}
if "paper.md" not in TXT:  # the public package on GitHub ships without the paper
    print("paper.md is not in the public package: the paper is at https://easybyte.es/lab/studies/s10/paper/")


def content(r):
    s = r["summary"]; c = s.get("counts", {}); tof = " ".join(s.get("type_of_frame_top", {})).upper()
    if "PARKING" in tof: return "parking"
    if "voiapp" in r["url"]: return "scooter"
    if c.get("ServiceJourney", 0): return "timetable"
    if c.get("StopPlace", 0) + c.get("Quay", 0): return "stops"
    return "other"


def verdict(x):
    if not x or x.get("documents_checked", 0) == 0: return "not-checked"
    if x["documents_valid"] < x["documents_checked"]: return "invalid"
    return "valid" if x.get("documents_skipped", 0) == 0 else "partial"


def best(r):
    o = ["valid", "partial", "invalid", "not-checked"]
    return min(verdict(r["xsd"].get("netex_1_3_2")), verdict(r["xsd"].get("netex_2_0_0")), key=o.index)


def feed(x):
    return {"LU": "LU", "NL": "NL:" + x["dataset_id"].split("/")[0]}.get(x["country"], x["country"] + x["dataset_id"])


tt = [r for r in R if content(r) == "timetable"]
tv = Counter(best(r) for r in tt)
part = sorted(r["xsd"]["netex_1_3_2"].get("coverage_bytes") or 0 for r in R if best(r) == "partial")
tpt = [r for r in R if any("TimetabledPassingTime': The attribute 'id' is required" in m
                           for m in r["xsd"].get("netex_2_0_0", {}).get("top_messages", {}))]
nl_inv = [r for r in R if r["country"] == "NL" and verdict(r["xsd"].get("netex_2_0_0")) == "invalid"]
nl_kr = [r for r in nl_inv if set(r["xsd"]["netex_2_0_0"]["by_category"]) == {"keyref-unresolved"}
         and sum(r["xsd"]["netex_2_0_0"]["by_category"].values()) == r["xsd"]["netex_2_0_0"]["errors"]]
epip_checked = [r for r in R if r["xsd"].get("epip", {}).get("documents_checked")]
fr = [r for r in R if r["summary"].get("profile") == "fr" and r["country"] == "FR"]
fr_small = [r for r in fr if r["summary"]["id_format_bad"] / r["summary"]["id_format_checked"] <= 0.01]
fr_refs = sum(r["summary"]["refs_internal_unversioned"] for r in fr)
fr_max = max(r["summary"]["refs_internal_unversioned"] for r in fr)
others = [r["summary"]["refs_internal_unversioned"] / r["summary"]["refs_internal"] for r in fr
          if r["summary"]["refs_internal_unversioned"] != fr_max]
moj = sum(f["count"] for r in R for f in r["findings"] if f["rule"] == "ENCODING-MOJIBAKE")
rep = sum(f["count"] for r in R for f in r["findings"] if f["rule"] == "ENCODING-REPLACEMENT-CHAR")
stale = [r["slug"] for r in R if any(f["rule"] == "VALIDITY-EXPIRED" for f in r["findings"])]
e200 = sum(r["xsd"].get("netex_2_0_0", {}).get("errors", 0) for r in R)
c200 = sum(sum(r["xsd"].get("netex_2_0_0", {}).get("by_category", {}).values()) for r in R)
acc = {(a["country"], a["probe"][-30:]): a for a in csv.DictReader(open(os.path.join(D, "nap_access.csv")))}
ch_bytes = next(a["observed"] for a in acc.values() if "Range" in a["observed"]).split("total size ")[1].split(" ")[0]
sample = list(csv.DictReader(open(os.path.join(D, "sample.csv"))))
gf = sum(1 for r in R if any(m.startswith("Element 'GeneralFrame': This element is not expected")
                             for m in r["xsd"].get("epip", {}).get("top_messages", {})))

CHECKS = [  # (name, recomputed, expected, literal text, files)
    # the five NAPs; Mobilithek (DE) is listed apart, from its metadata only
    ("feeds", len({feed(x) for x in CAT if x["country"] != "DE"}), 266, "266 NeTEx feeds", ["README.md", "paper.md"]),
    ("files", sum(1 for x in CAT if x["country"] != "DE"), 621, "(621 files)", ["README.md", "paper.md"]),
    ("de_offers", sum(1 for x in CAT if x["country"] == "DE"), 18, "18 more offers in Germany's Mobilithek metadata", ["README.md", "paper.md"]),
    ("validated", len(R), 41, "41 of 44", ["README.md", "paper.md"]),
    ("sample", len(sample), 44, "41 of 44", ["README.md", "paper.md"]),
    ("timetables", len(tt), 34, "34 timetable", ["README.md", "paper.md"]),
    ("tt_valid", tv["valid"], 8, "| Timetable | 34 | 8 | 6 | 16 | 4 |", ["paper.md"]),
    ("tt_partial", tv["partial"], 6, "6 are valid on the part checked", ["README.md", "paper.md"]),
    ("tt_invalid", tv["invalid"], 16, "16 are invalid and 4 were not checked", ["README.md", "paper.md"]),
    ("tt_notchecked", tv["not-checked"], 4, "16 are invalid and 4 were not checked", ["README.md", "paper.md"]),
    ("tt_valid_all_FR", sum(1 for r in tt if best(r) == "valid" and r["country"] == "FR"), 8, "8 are fully valid", ["README.md", "paper.md"]),
    ("coverage_min_pct", round(part[0] * 100, 1), 2.4, "2.4 %", ["README.md", "paper.md"]),
    ("coverage_max_pct", round(part[-1] * 100), 66, "66 %", ["README.md", "paper.md"]),
    ("tpt_datasets", len(tpt), 11, "rejects 11 French timetables", ["README.md", "paper.md"]),
    ("tpt_all_FR", sum(1 for r in tpt if r["country"] == "FR"), 11, "11 French timetables", ["README.md", "paper.md"]),
    ("tpt_valid_132", sum(1 for r in tpt if verdict(r["xsd"]["netex_1_3_2"]) == "valid"), 7, "7 of them are fully valid against 1.3.2", ["README.md", "paper.md"]),
    ("tpt_partial_132", sum(1 for r in tpt if verdict(r["xsd"]["netex_1_3_2"]) == "partial"), 2, "and 2 more on the part checked", ["README.md", "paper.md"]),
    ("nl_invalid_200", len(nl_inv), 11, "Ten of eleven Dutch", ["README.md", "paper.md"]),
    ("nl_keyref_only", len(nl_kr), 10, "Ten of eleven Dutch", ["README.md", "paper.md"]),
    ("epip_checked", len(epip_checked), 36, "0 of 36", ["README.md", "paper.md"]),
    ("epip_valid", sum(1 for r in epip_checked if verdict(r["xsd"]["epip"]) == "valid"), 0, "0 of 36", ["README.md", "paper.md"]),
    ("epip_generalframe", gf, 18, "`GeneralFrame` (18 datasets", ["paper.md"]),
    ("stale", stale, ["NL_avv"], "One feed is stale", ["README.md", "paper.md"]),
    ("mojibake", moj, 6, "Six strings are double-encoded", ["README.md", "paper.md"]),
    ("replacement", rep, 1, "one character was lost", ["README.md", "paper.md"]),
    ("fr_tested", len(fr), 14, "14 French datasets", ["README.md", "paper.md"]),
    ("fr_ids_ge99", len(fr_small), 11, "11 of 14", ["README.md", "paper.md"]),
    ("fr_refs", fr_refs, 248286, "248,286", ["README.md", "paper.md"]),
    ("fr_refs_top_share_pct", round(100 * fr_max / fr_refs), 81, "81 %", ["README.md", "paper.md"]),
    ("fr_refs_median_others_pct", round(100 * statistics.median(others), 1), 2.9, "2.9 % in the other 13", ["paper.md"]),
    ("errors_200_total", e200, 3357691, "3,357,691", ["paper.md"]),
    ("errors_200_categorised", c200, 928920, "928,920", ["paper.md"]),
    ("ch_bytes", int(ch_bytes), 663744713, "663,744,713 bytes", ["paper.md"]),
    ("calendar_extracted", sum(1 for r in R if r["summary"].get("calendar_max")), 12, "12 yield a calendar end date", ["paper.md"]),
    ("fr_frame", sum(1 for x in CAT if x["country"] == "FR" and "public-transit" in x["note"] and x["size_bytes"]
                     and x["http_status"] == "200" and int(x["size_bytes"]) <= 300e6), 131, "131 eligible", ["paper.md"]),
    ("tests", sum(open(p).read().count("    def test_") for p in glob.glob(os.path.join(S, "prototype", "tests", "test_*.py"))), 16, "16 in total", ["paper.md"]),
]
bad = 0
for name, got, exp, text, files in CHECKS:
    files = [f for f in files if f in TXT]
    missing = [f for f in files if text not in TXT[f]]
    ok = got == exp and not missing
    bad += not ok
    print(f"{'OK  ' if ok else 'FAIL'} {name}: data={got} text={exp}" + (f" — text '{text}' missing in {missing}" if missing else ""))
print(f"{len(CHECKS) - bad}/{len(CHECKS)} headline checks pass")
sys.exit(1 if bad else 0)
