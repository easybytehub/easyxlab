#!/usr/bin/env python3
"""S10 step 4 — aggregates: catalogue census, XSD results, consistency findings, tables.md."""
import csv, glob, json, os, statistics
from collections import Counter, defaultdict
from datetime import date

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(S, "data")
SNAP = date(2026, 10, 2)
cat = list(csv.DictReader(open(os.path.join(D, "catalogue_netex.csv"))))
res = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(D, "per_dataset", "*.json")))]
out = {}


def days(d):
    try:
        return (SNAP - date.fromisoformat(d[:10])).days
    except Exception:
        return None


def feed(x):
    c = x["country"]
    if c == "LU":
        return "LU:netex"
    if c == "NL":
        return "NL:" + x["dataset_id"].split("/")[0]
    return c + ":" + x["dataset_id"]


# ---------- catalogue census ----------
by = defaultdict(list)
for x in cat:
    by[x["country"]].append(x)
crow = []
for c, xs in sorted(by.items()):
    feeds = defaultdict(list)
    for x in xs:
        feeds[feed(x)].append(x)
    newest = [max(v, key=lambda r: r["updated"]) for v in feeds.values()]
    sizes = [int(float(r["size_bytes"])) for r in newest if r["size_bytes"]]
    ages = [days(r["updated"]) for r in newest if days(r["updated"]) is not None]
    lic = Counter(r["licence"] or "(none in API)" for r in newest)
    crow.append(dict(country=c, nap=xs[0]["nap"], resources=len(xs), feeds=len(feeds),
                     feeds_with_size=len(sizes), total_mb=round(sum(sizes) / 1e6, 1),
                     median_mb=round(statistics.median(sizes) / 1e6, 2) if sizes else "",
                     max_mb=round(max(sizes) / 1e6, 1) if sizes else "",
                     feeds_under_10kb=sum(s < 10_000 for s in sizes),
                     updated_le_7d=sum(a <= 7 for a in ages), updated_le_30d=sum(a <= 30 for a in ages),
                     updated_gt_365d=sum(a > 365 for a in ages), oldest=min(r["updated"] for r in newest),
                     licence_machine_readable=sum(1 for r in newest if r["licence"] and r["licence"] not in ("notspecified", "Not specified", "NO_LICENSE")),
                     licences="; ".join(f"{k}:{v}" for k, v in lic.most_common())))
with open(os.path.join(D, "catalogue_summary.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(crow[0].keys())); w.writeheader(); w.writerows(crow)
out["catalogue"] = crow

# ---------- per-dataset validation table ----------
def verdict(x):
    """valid = all documents checked and valid; valid-partial = all checked valid but some skipped;
    invalid = at least one checked document invalid; not-checked = nothing checked (size budget)."""
    if not x or x.get("documents_checked", 0) == 0:
        return "not-checked"
    if x["documents_valid"] < x["documents_checked"]:
        return "invalid"
    return "valid" if x.get("documents_skipped", 0) == 0 else "valid-partial"


def best(a, b):
    order = ["valid", "valid-partial", "invalid", "not-checked"]
    return min(a, b, key=order.index)

vrows = []
for r in res:
    s = r.get("summary", {}); x = r.get("xsd", {})
    fr = {f["rule"]: f["count"] for f in r.get("findings", [])}
    def xv(k, f):
        return x.get(k, {}).get(f, "")
    vrows.append(dict(
        slug=r["slug"], country=r["country"], stratum=r["stratum"], error=r.get("error", ""),
        download_mb=round(r.get("download_bytes", 0) / 1e6, 2), uncompressed_mb=round((r.get("uncompressed_bytes") or 0) / 1e6, 1),
        documents=r.get("xml_members", ""), profile=s.get("profile", ""),
        declared_versions="|".join(sorted(s.get("declared_versions", {}))),
        netex132_valid=xv("netex_1_3_2", "documents_valid"), netex132_checked=xv("netex_1_3_2", "documents_checked"),
        netex132_skipped=xv("netex_1_3_2", "documents_skipped"), netex132_ok=xv("netex_1_3_2", "dataset_valid"),
        netex200_valid=xv("netex_2_0_0", "documents_valid"), netex200_ok=xv("netex_2_0_0", "dataset_valid"),
        epip_valid=xv("epip", "documents_valid"), epip_ok=xv("epip", "dataset_valid"),
        either_netex_ok=bool(xv("netex_1_3_2", "dataset_valid") or xv("netex_2_0_0", "dataset_valid")),
        netex132_verdict=verdict(x.get("netex_1_3_2")), netex200_verdict=verdict(x.get("netex_2_0_0")),
        epip_verdict=verdict(x.get("epip")),
        best_netex_verdict=best(verdict(x.get("netex_1_3_2")), verdict(x.get("netex_2_0_0"))),
        xsd_coverage=x.get("netex_1_3_2", {}).get("coverage_bytes", 1.0 if xv("netex_1_3_2", "documents_skipped") == 0 else ""),
        netex132_errors=xv("netex_1_3_2", "errors"), netex200_errors=xv("netex_2_0_0", "errors"), epip_errors=xv("epip", "errors"),
        service_journeys=s.get("counts", {}).get("ServiceJourney", 0), ids=s.get("ids", ""), refs=s.get("refs", ""),
        refs_unresolved=s.get("refs_unresolved", ""), refs_unresolved_versioned=s.get("refs_unresolved_versioned", ""),
        version_mismatch=s.get("version_mismatch", ""), duplicate_definitions=s.get("duplicate_definitions", ""),
        validity_to_max=s.get("validity_to_max", ""), calendar_max=s.get("calendar_max", ""),
        validity_expired="VALIDITY-EXPIRED" in fr, calendar_in_past="CALENDAR-IN-PAST" in fr,
        encodings="|".join(f"{k}:{v}" for k, v in s.get("encodings", {}).items()), bom=s.get("bom", ""),
        mojibake=s.get("mojibake", ""), id_format_bad=s.get("id_format_bad", ""), id_format_checked=s.get("id_format_checked", ""),
        id_type_bad=s.get("id_type_bad", ""),
        rules="|".join(f"{k}:{v}" for k, v in sorted(fr.items())), seconds=r.get("seconds", "")))
if vrows:
    with open(os.path.join(D, "validation_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(vrows[0].keys())); w.writeheader(); w.writerows(vrows)
ok = [v for v in vrows if not v["error"]]
out["validated"] = len(ok); out["failed_download"] = [v["slug"] + ": " + v["error"] for v in vrows if v["error"]]
for k in ("netex132_ok", "netex200_ok", "either_netex_ok", "epip_ok", "validity_expired", "calendar_in_past"):
    out[k] = sum(1 for v in ok if v[k] is True)
for k in ("netex132_verdict", "netex200_verdict", "epip_verdict", "best_netex_verdict"):
    out[k] = dict(Counter(v[k] for v in ok))
out["by_country"] = {}
for c in sorted({v["country"] for v in ok}):
    vs = [v for v in ok if v["country"] == c]
    out["by_country"][c] = {k: sum(1 for v in vs if v[k] is True) for k in
                            ("netex132_ok", "netex200_ok", "either_netex_ok", "epip_ok", "validity_expired", "calendar_in_past")}
    out["by_country"][c]["n"] = len(vs)
    out["by_country"][c]["best_netex_verdict"] = dict(Counter(v["best_netex_verdict"] for v in vs))
    out["by_country"][c]["epip_verdict"] = dict(Counter(v["epip_verdict"] for v in vs))
    out["by_country"][c]["profiles"] = dict(Counter(v["profile"] for v in vs))
out["profiles"] = dict(Counter(v["profile"] for v in ok))
out["declared_versions"] = dict(Counter(dv for v in ok for dv in v["declared_versions"].split("|") if dv))

# ---------- XSD error categories and messages ----------
crows, mrows = [], []
for key in ("netex_1_3_2", "netex_2_0_0", "epip"):
    cats, cds, msgs, mds = Counter(), Counter(), Counter(), Counter()
    for r in res:
        x = r.get("xsd", {}).get(key)
        if not x:
            continue
        for c, n in x["by_category"].items():
            cats[c] += n; cds[c] += 1
        for m, n in x["top_messages"].items():
            msgs[m] += n; mds[m] += 1
    for c in cats:
        crows.append(dict(schema=key, category=c, datasets=cds[c], errors=cats[c]))
    for m, _ in mds.most_common(25):
        mrows.append(dict(schema=key, message=m, datasets=mds[m], errors=msgs[m]))
crows.sort(key=lambda r: (r["schema"], -r["datasets"]))
for name, rows in (("xsd_error_categories.csv", crows), ("xsd_top_messages.csv", mrows)):
    if rows:
        with open(os.path.join(D, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# ---------- consistency findings ----------
frows = defaultdict(lambda: {"datasets": 0, "total": 0, "countries": Counter()})
for r in res:
    for f in r.get("findings", []):
        e = frows[f["rule"]]; e["datasets"] += 1; e["total"] += f["count"]; e["countries"][r["country"]] += 1
fr_out = [dict(rule=k, severity=next(f["severity"] for r in res for f in r.get("findings", []) if f["rule"] == k),
               datasets=v["datasets"], total=v["total"], countries="|".join(f"{c}:{n}" for c, n in sorted(v["countries"].items())))
          for k, v in sorted(frows.items(), key=lambda kv: -kv[1]["datasets"])]
if fr_out:
    with open(os.path.join(D, "findings_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fr_out[0].keys())); w.writeheader(); w.writerows(fr_out)
out["findings"] = fr_out
# denominators for profile rules
out["profile_rule_denominators"] = {p: sum(1 for v in ok if v["profile"] == p) for p in ("fr", "nordic", "nl", "epip", "unknown")}
# disk
try:
    peak = max(int(l.strip().split(",")[2]) for l in open(os.path.join(D, "disk_log.csv")) if l.strip())
except Exception:
    peak = None
out["peak_work_dir_bytes"] = peak

# ---------- review fixes: content class, coverage, keyref-only, shares, totals, headline ----------
def content_class(r):
    s = r.get("summary", {}); c = s.get("counts", {}); tof = " ".join(s.get("type_of_frame_top", {})).upper()
    if "PARKING" in tof:
        return "parking"
    if "voiapp" in r.get("url", ""):
        return "scooter-sharing"
    if c.get("ServiceJourney", 0) > 0:
        return "timetable"
    if c.get("StopPlace", 0) + c.get("Quay", 0) > 0:
        return "stops"
    if "CODESPACE" in tof:
        return "codespace-list"
    return "other"


def keyref_only(x):
    if not x or x.get("documents_checked", 0) == 0 or x["documents_valid"] == x["documents_checked"]:
        return None
    cats = x["by_category"]; n = sum(cats.values())
    if n != x["errors"]:
        return "unknown (error list truncated)"
    return set(cats) == {"keyref-unresolved"}


rmap = {r["slug"]: r for r in res}
for v in vrows:
    r = rmap[v["slug"]]; x = r.get("xsd", {})
    v["content"] = content_class(r)
    v["netex200_keyref_only"] = keyref_only(x.get("netex_2_0_0"))
    v["netex132_keyref_only"] = keyref_only(x.get("netex_1_3_2"))
    v["xsd_budget_mb"] = r.get("xsd_params", {}).get("xsd_budget", 0) // 1_000_000
    v["max_xsd_doc_mb"] = r.get("xsd_params", {}).get("max_xsd_bytes", 0) // 1_000_000
if vrows:
    with open(os.path.join(D, "validation_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(vrows[0].keys())); w.writeheader(); w.writerows(vrows)
ok = [v for v in vrows if not v["error"]]
out["by_content"] = {}
for cl in sorted({v["content"] for v in ok}):
    vs = [v for v in ok if v["content"] == cl]
    out["by_content"][cl] = {"n": len(vs), "best_netex_verdict": dict(Counter(v["best_netex_verdict"] for v in vs)),
                             "slugs": [v["slug"] for v in vs]}
out["valid_partial_coverage"] = {v["slug"]: v["xsd_coverage"] for v in ok if v["best_netex_verdict"] == "valid-partial"}
out["not_checked"] = {v["slug"]: v["uncompressed_mb"] for v in ok if v["best_netex_verdict"] == "not-checked"}
out["nl_invalid_keyref_only_200"] = [v["slug"] for v in ok if v["country"] == "NL" and v["netex200_keyref_only"] is True]
out["nl_invalid_200"] = [v["slug"] for v in ok if v["country"] == "NL" and v["netex200_verdict"] == "invalid"]
# error totals vs categorised (20,000 per document)
tot = {}
for key in ("netex_1_3_2", "netex_2_0_0", "epip"):
    e = sum(r.get("xsd", {}).get(key, {}).get("errors", 0) for r in res)
    c = sum(sum(r.get("xsd", {}).get(key, {}).get("by_category", {}).values()) for r in res)
    tot[key] = {"errors": e, "categorised": c}
out["xsd_error_totals"] = tot
# datasets per (merged) message variant
def merge(m):
    return m.replace(" Expected is (...).", "").rstrip(".")
msgsets = defaultdict(set)
for r in res:
    for key, x in r.get("xsd", {}).items():
        for m in x.get("top_messages", {}):
            msgsets[(key, merge(m))].add(r["slug"])
out["datasets_per_message"] = {f"{k}|{m}": len(v) for (k, m), v in sorted(msgsets.items(), key=lambda kv: -len(kv[1])) if len(v) >= 3}
tpt = msgsets.get(("netex_2_0_0", "Element 'TimetabledPassingTime': The attribute 'id' is required but missing"), set())
out["tpt_id_missing_200"] = {"datasets": len(tpt), "countries": dict(Counter(rmap[s]["country"] for s in tpt)),
                             "also_valid_132": sum(1 for s in tpt if next(v for v in ok if v["slug"] == s)["netex132_verdict"] in ("valid", "valid-partial"))}
# French-profile shares
fr = []
for v in ok:
    r = rmap[v["slug"]]; s_ = r["summary"]
    if s_.get("profile") == "fr":
        fr.append(dict(slug=v["slug"], content=v["content"], ids_checked=s_.get("id_format_checked", 0), ids_not_proposed=s_.get("id_format_bad", 0),
                       share_ids=round(s_.get("id_format_bad", 0) / s_["id_format_checked"], 4) if s_.get("id_format_checked") else None,
                       refs_internal=s_.get("refs_internal", 0), refs_internal_unversioned=s_.get("refs_internal_unversioned", 0),
                       share_refs=round(s_.get("refs_internal_unversioned", 0) / s_["refs_internal"], 4) if s_.get("refs_internal") else None,
                       rules_version=r.get("rules_version")))
if fr:
    with open(os.path.join(D, "french_profile_shares.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fr[0].keys())); w.writeheader(); w.writerows(fr)
out["fr_profile"] = {"n": len(fr), "n_FR": sum(1 for x in fr if x["slug"].startswith("FR_")),
                     "ids_share_le_1pct": sum(1 for x in fr if x["share_ids"] is not None and x["share_ids"] <= 0.01),
                     "ids_share_ge_50pct": sum(1 for x in fr if x["share_ids"] is not None and x["share_ids"] >= 0.5),
                     "refs_unversioned_total": sum(x["refs_internal_unversioned"] for x in fr),
                     "refs_unversioned_max_dataset": max((x["refs_internal_unversioned"] for x in fr), default=0)}
# validity / calendar / encoding facts
out["validity_expired_slugs"] = [v["slug"] for v in ok if v["validity_expired"]]
out["calendar_extracted"] = sum(1 for v in ok if v["calendar_max"])
out["mojibake_total"] = sum(f["count"] for r in res for f in r.get("findings", []) if f["rule"] == "ENCODING-MOJIBAKE")
out["replacement_total"] = sum(f["count"] for r in res for f in r.get("findings", []) if f["rule"] == "ENCODING-REPLACEMENT-CHAR")
out["non_utf8_slugs"] = [r["slug"] for r in res if any(f["rule"] == "ENCODING-NOT-UTF8" for f in r.get("findings", []))]
out["version_missing_slugs"] = [r["slug"] for r in res if any(f["rule"] == "VERSION-MISSING" for f in r.get("findings", []))]
out["typeof_versioned_unresolved"] = sum(r.get("summary", {}).get("refs_unresolved_typeof_versioned", 0) or 0 for r in res)
out["rules_versions"] = dict(Counter(str(r.get("rules_version")) for r in res))
# census details
no_agg = [x for x in cat if x["country"] == "NO" and "rb_norway-aggregated" in x["title"]]
out["no_aggregate_mb"] = round(sum(int(x["size_bytes"]) for x in no_agg) / 1e6, 1)
out["fr_public_transit"] = sum(1 for x in cat if x["country"] == "FR" and "public-transit" in x["note"])
out["fr_frame"] = sum(1 for x in cat if x["country"] == "FR" and "public-transit" in x["note"] and x["size_bytes"]
                      and str(x["http_status"]) == "200" and int(x["size_bytes"]) <= 300e6)
out["de_categories"] = dict(Counter(x["note"].split(";")[0].replace("category=", "") for x in cat if x["country"] == "DE"))
out["de_siri_offers"] = sum(1 for x in cat if x["country"] == "DE" and "SIRI" in x["title"])

sample = list(csv.DictReader(open(os.path.join(D, "sample.csv"))))
done = {r["slug"] for r in res}
out["sample_size"] = len(sample)
out["not_completed"] = [x["slug"] for x in sample if x["slug"] not in done]
out["download_mb_total"] = round(sum(r.get("download_bytes", 0) for r in res) / 1e6, 1)
out["uncompressed_mb_total"] = round(sum((r.get("uncompressed_bytes") or 0) for r in res) / 1e6, 1)
json.dump(out, open(os.path.join(D, "summary.json"), "w"), indent=1, ensure_ascii=False)


# ---------- tables.md ----------
def md(rows, cols):
    s = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    for r in rows:
        s += "| " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n"
    return s


T = "# S10 tables (generated by scripts/04_aggregate.py)\n\n## Catalogue census\n\n"
T += md(crow, ["country", "nap", "resources", "feeds", "total_mb", "median_mb", "max_mb", "feeds_under_10kb",
               "updated_le_30d", "updated_gt_365d", "licence_machine_readable", "licences"])
T += "\n## Validation per dataset\n\n" + md(vrows, ["slug", "country", "profile", "declared_versions", "documents",
                                                  "uncompressed_mb", "xsd_coverage", "netex132_verdict", "netex200_verdict",
                                                  "epip_verdict", "refs_unresolved_versioned", "duplicate_definitions",
                                                  "validity_to_max", "calendar_max", "mojibake", "error"])
T += "\n## XSD error categories\n\n" + md(crows, ["schema", "category", "datasets", "errors"])
T += "\n## Most frequent XSD messages\n\n" + md(mrows, ["schema", "message", "datasets", "errors"])
T += "\n## Consistency findings\n\n" + md(fr_out, ["rule", "severity", "datasets", "total", "countries"])
open(os.path.join(D, "tables.md"), "w").write(T)
print(json.dumps({k: out[k] for k in out if k not in ("catalogue", "findings")}, indent=1, ensure_ascii=False))
