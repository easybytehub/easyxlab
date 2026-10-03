#!/usr/bin/env python3
"""S10 step 2 — justified, deterministic sample of NeTEx datasets for validation.

Rules (see METHOD.md §3):
  FR  15 public-transit resources, 5 per size tercile, random.Random(20261002), HTTP 200, <= 300 MB.
  NO  6 Entur codespaces: the 3 largest regional authorities (RUT, SKY, INN) and the 3 rail
      operators with timetable files >= 1 MB (VYG Vy, SJN SJ Norge, GOA Go-Ahead Nordic) —
      rail is the TEN-T-relevant part. The national aggregate is the union of the codespaces.
  NL  the newest file of every NDOV Loket operator directory (except 'test').
  BE  every transportdata.be NeTEx resource with a direct download URL.
  LU  the newest weekly snapshot.
  DE/ES/SE/FI/IT/AT: no anonymous download -> not sampled (documented in nap_access_probes.csv).
"""
import csv, os, random, re
S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = list(csv.DictReader(open(os.path.join(S, "data", "catalogue_netex.csv"))))
out = []
def slug(x): return re.sub(r"[^A-Za-z0-9]+", "_", x)[:60].strip("_")
def pick(x, stratum, reason, s=None):
    out.append(dict(slug=s or slug(x["country"] + "_" + x["dataset_id"]), country=x["country"], nap=x["nap"],
                    dataset_id=x["dataset_id"], title=x["title"][:120], licence=x["licence"], updated=x["updated"],
                    size_bytes=x["size_bytes"], url=x["url"], stratum=stratum, reason=reason))
fr = [x for x in rows if x["country"] == "FR" and "public-transit" in x["note"] and x["size_bytes"]
      and str(x["http_status"]) == "200" and int(x["size_bytes"]) <= 300e6]
fr.sort(key=lambda x: int(x["size_bytes"]))
rng = random.Random(20261002); n = len(fr)
for i, name in enumerate(["small", "medium", "large"]):
    for x in rng.sample(fr[i * n // 3:(i + 1) * n // 3], 5):
        pick(x, f"FR-{name}", "random within size tercile")
want = {"rut": "regional, largest", "sky": "regional, 2nd", "inn": "regional, 3rd",
        "vyg": "rail (Vy)", "sjn": "rail (SJ Norge)", "goa": "rail (Go-Ahead Nordic)"}
for x in rows:
    m = re.match(r"rb_([a-z]+)-aggregated", x["title"])
    if x["country"] == "NO" and m and m.group(1) in want:
        pick(x, "NO", want[m.group(1)], s="NO_" + m.group(1))
latest = {}
for x in rows:
    if x["country"] == "NL":
        op = x["dataset_id"].split("/")[0]
        if op != "test" and (op not in latest or (x["updated"], x["dataset_id"]) > (latest[op]["updated"], latest[op]["dataset_id"])):
            latest[op] = x
for op, x in sorted(latest.items()):
    pick(x, "NL", "newest file of operator directory", s="NL_" + op)
for x in rows:
    if x["country"] == "BE" and re.search(r"\.(zip|xml)(\?|$)|/netex", x["url"]) and "data.html" not in x["url"]:
        pick(x, "BE", "all direct NeTEx downloads")
lu = sorted([x for x in rows if x["country"] == "LU"], key=lambda x: (x["updated"], x["title"]))[-1]
pick(lu, "LU", "newest weekly snapshot", s="LU_latest")
with open(os.path.join(S, "data", "sample.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
print(len(out), "datasets;", round(sum(int(x["size_bytes"] or 0) for x in out) / 1e6), "MB to download in total")
