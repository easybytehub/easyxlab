"""Build the published compact dataset (data/compact/) from the request cache, and check that the
compact reader reproduces the cache exactly.
- pypi_files.csv.gz: every file uploaded since 2024-09-01 (no earlier file carries provenance): project,
  version, filename, upload time, provenance, yanked, and the publisher identity where the Integrity API
  was queried;
- pypi_old_versions.csv.gz: for files before 2024-09-01, one aggregate row per version, kept only where
  the analysis needs it (versions that also have newer files, and per project the highest stable, highest
  overall and most recently first-uploaded older version);
- projects.csv: rank and name of each project analysed (no download counts), live version count;
- npm_sample.csv, npm_versions.csv.gz: the npm sample, per version provenance flag, publish time and
  provenance repository/workflow where read;
- evidence.jsonl.gz: the reduced records of the other caches (Integrity API publishers, npm, GitHub
  redirects, commit lists, PyPI project URLs). Workflow file contents are NOT included."""
import csv, glob, gzip, json, os
from common import RAW, DATA, cache_read, norm, COMPACT_KINDS
import pypi_versions as pv

OUT = os.path.join(DATA, "compact"); os.makedirs(OUT, exist_ok=True)
top = json.load(open(os.path.join(RAW, "top-pypi-packages.min.json")))["rows"]
iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

projects, files, old = [], [], []
for rank, row in enumerate(top, 1):
    p = norm(row["project"])
    status, rows = pv.raw_files(p)
    full = pv.raw_versions(p)[1]
    d = cache_read("simple", p) or {}
    projects.append({"rank": rank, "project": p, "index_status": status, "n_versions_live": len(full),
                     "n_files_index": len(d.get("files", [])), "n_files_by_list_date": len(rows)})
    new_v = set()
    oldagg = {}
    for v, vs, fn, t, prov, y in rows:
        if t >= pv.SPLIT:
            ent = cache_read("integrity", f"{p}/{vs}/{fn}") if prov else None
            pub = ""
            if ent and ent.get("publishers"):
                b = ent["publishers"][0]
                pub = "|".join(str(b.get(k) or "") for k in ("kind", "repository", "workflow", "environment")) if b.get("kind") != "Google" \
                    else f"Google|{b.get('email_domain', '')}||"
            files.append({"rank": rank, "project": p, "version": vs, "filename": fn, "upload_time": iso(t),
                          "provenance": int(prov), "yanked": int(y), "publisher": pub})
            new_v.add(v)
        else:
            assert not prov, (p, fn)
            a = oldagg.setdefault(v, {"vs": vs, "first": t, "last": t, "live": 0, "yanked": 0})
            a["first"] = min(a["first"], t); a["last"] = max(a["last"], t)
            a["yanked" if y else "live"] += 1
    oldonly = [r for r in full if r["v"] not in new_v]
    keep = set(new_v)
    if oldonly:
        st = [r for r in oldonly if not r["pre"]]
        if st: keep.add(max(st, key=lambda r: r["v"])["v"])
        keep.add(max(oldonly, key=lambda r: r["v"])["v"])
        keep.add(max(oldonly, key=lambda r: (r["t"], r["v"]))["v"])
    for v, a in oldagg.items():
        if v in keep:
            old.append({"rank": rank, "project": p, "version": a["vs"], "first_upload": iso(a["first"]), "last_upload": iso(a["last"]),
                        "live_files": a["live"], "yanked_files": a["yanked"]})

def wcsv(name, rows, gz=True):
    op = gzip.open if gz else open
    with op(os.path.join(OUT, name), "wt", newline="") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)

wcsv("pypi_files.csv.gz", files); wcsv("pypi_old_versions.csv.gz", old); wcsv("projects.csv", projects, gz=False)

# npm
nhi = os.path.join(RAW, "npm", "package", "lib", "top-download.js")
import importlib.util
spec = importlib.util.spec_from_file_location("s07", os.path.join(os.path.dirname(__file__), "07_npm.py")); s07 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s07)
sample = s07.load_list()
wcsv("npm_sample.csv", [{"rank": r, "package": n} for r, n in sample], gz=False)
nv = []
for rank, n in sample:
    d = cache_read("npm_corgi", n) or {}
    tm = (cache_read("npm_time", n) or {}).get("time", {})
    lt = (d.get("dist_tags") or {}).get("latest")
    for v, m in (d.get("versions") or {}).items():
        a = cache_read("npm_att", f"{n}@{v}") or {}
        nv.append({"rank": rank, "package": n, "version": v, "provenance": int(m["prov"]), "deprecated": int(m["dep"]), "is_latest": int(v == lt),
                   "publish_time": tm.get(v, ""), "prov_repo": a.get("repo") or "", "prov_path": a.get("path") or ""})
wcsv("npm_versions.csv.gz", nv)

# evidence bundle
with gzip.open(os.path.join(OUT, "evidence.jsonl.gz"), "wt") as f:
    n = 0
    for kind in COMPACT_KINDS:
        for path in sorted(glob.glob(os.path.join(RAW, kind, "*.json.gz"))):
            key = os.path.basename(path)[:-len(".json.gz")].replace("__", "/")
            if kind == "gh_redirect":
                key = key.lower()
            with gzip.open(path, "rt") as g:
                obj = json.load(g)
            # the cache file name maps "/" to "__", which is lossy for npm names such as @types/babel__core:
            # take the key from the record itself where it carries one
            key = obj.get("key") or obj.get("name") or key if kind.startswith("npm_") else key
            f.write(json.dumps({"kind": kind, "key": key, "obj": obj}, separators=(",", ":")) + "\n"); n += 1

# self-check: compact reader == raw reader
def sig(vs):
    hs = pv.highest_stable(vs)
    keyv = lambda r: (r["vs"], r["t"], r["att"], r["att_all"], r["pre"], r["t_att"], tuple(sorted(r["pf"])))
    return (keyv(hs) if hs else None, keyv(vs[-1]) if vs else None,
            tuple(keyv(r) for r in vs if r["t"] >= pv.SPLIT or r["att"]))
bad = [p["project"] for p in projects if sig(pv.raw_versions(p["project"])[1]) != sig(pv.versions(p["project"])[1])]
print(f"files {len(files):,}  old-version rows {len(old):,}  npm versions {len(nv):,}  evidence records {n:,}  mismatches {len(bad)} {bad[:5]}")
for x in os.listdir(OUT): print(" ", x, os.path.getsize(os.path.join(OUT, x)) // 1024, "KB")
