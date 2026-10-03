#!/usr/bin/env python3
"""S10 step 3 — download one sampled dataset at a time, validate, check, delete.

For every dataset in data/sample.csv:
  1. download to work/dl/ (abort above 300 MB);
  2. streaming consistency scan of every XML document (prototype/netex_lint/core.py);
  3. full XSD validation of each document <= MAX_XSD_BYTES against
     (a) NeTEx 1.3.2 (TransmodelEcosystem/NeTEx tag v1.3.2 = 4f42794, NeTEx_publication.xsd),
     (b) NeTEx 2.0.0 (tag v2.0.0 = a94e5e1) and
     (c) EPIP (TransmodelEcosystem/NeTEx-Profile-EPIP, NeTEx_publication_EPIP.xsd, commit e5eaf83);
  4. write data/per_dataset/<slug>.json and delete the download.
Disk use of work/dl is logged after each download (data/disk_log.csv).
Usage: 03_validate.py [slug ...]   (default: all not yet done)
"""
import csv, json, os, shutil, sys, time
from collections import Counter

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(S, "prototype"))
import requests
from netex_lint.core import iter_members, scan_member, check_dataset, load_schema, xsd_validate

TODAY = os.environ.get("SNAPSHOT_DATE", "2026-10-02")
MAX_DL = 300_000_000
MAX_XSD_BYTES = int(os.environ.get("MAX_XSD_BYTES", 150_000_000))
MAX_XSD_MEMBERS = int(os.environ.get("MAX_XSD_MEMBERS", 400))
# XSD validation is the slow part (~1.5 s per MB of XML for three schemas): per dataset and schema,
# validate documents in name order until this many uncompressed bytes have been checked.
RULES_VERSION = 4   # bump when prototype/netex_lint/core.py rules change; CHECKS_ONLY=1 re-runs them
XSD_BUDGET = int(os.environ.get("XSD_BUDGET", 150_000_000))


def avail_bytes():
    """free + inactive + speculative memory (macOS vm_stat); None elsewhere."""
    try:
        import re, subprocess
        out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        page = int(re.search(r"page size of (\d+)", out).group(1))
        pages = sum(int(re.search(rf"{k}:\s+(\d+)", out).group(1)) for k in ("Pages free", "Pages inactive", "Pages speculative"))
        return pages * page
    except Exception:
        return None
UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
DL = os.path.join(S, "work", "dl"); os.makedirs(DL, exist_ok=True)
OUT = os.path.join(S, "data", "per_dataset"); os.makedirs(OUT, exist_ok=True)
XSD = {
    "netex_1_3_2": os.path.join(S, "work", "xsd", "NeTEx-1.3.2", "xsd", "NeTEx_publication.xsd"),
    "netex_2_0_0": os.path.join(S, "work", "xsd", "NeTEx-2.0.0", "xsd", "NeTEx_publication.xsd"),
    "epip": os.path.join(S, "work", "xsd", "epip", "NeTEx_publication_EPIP.xsd"),
}


def du(path):
    return sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(path) for f in fs)


def download(url, dest):
    with requests.get(url, headers={"User-Agent": UA}, stream=True, timeout=120, allow_redirects=True) as r:
        r.raise_for_status()
        n = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                n += len(chunk)
                if n > MAX_DL:
                    raise RuntimeError("larger than 300 MB")
                f.write(chunk)
        return n, r.status_code, r.headers.get("Content-Type", "")


def main():
    sample = list(csv.DictReader(open(os.path.join(S, "data", "sample.csv"))))
    only = set(sys.argv[1:])
    if os.environ.get("REVERSE"):          # a second worker can walk the sample from the end
        sample.reverse()
    t0 = time.time()
    schemas = {k: load_schema(v) for k, v in XSD.items()}
    print(f"schemas compiled in {time.time()-t0:.0f}s", flush=True)
    disk_log = open(os.path.join(S, "data", "disk_log.csv"), "a")
    for row in sample:
        slug = row["slug"]
        if only and slug not in only:
            continue
        outp = os.path.join(OUT, slug + ".json")
        lock = outp + ".lock"
        recheck = os.environ.get("CHECKS_ONLY") and os.path.exists(outp)
        if (os.path.exists(outp) or os.path.exists(lock)) and not only and not recheck:
            continue
        if os.environ.get("CHECKS_ONLY") and not os.path.exists(outp):
            continue
        if recheck and json.load(open(outp)).get("rules_version") == RULES_VERSION:
            continue
        open(lock, "w").close()
        res = {k: row[k] for k in ("slug", "country", "nap", "dataset_id", "title", "licence", "updated", "url", "stratum")}
        res["snapshot_date"] = TODAY
        res["xsd_params"] = {"xsd_budget": XSD_BUDGET, "max_xsd_bytes": MAX_XSD_BYTES,
                             "errors_categorised_per_document": 20000, "source": "recorded by 03_validate.py"}
        dest = os.path.join(DL, slug + ".bin")
        t = time.time()
        try:
            size, st, ctype = download(row["url"], dest)
            res.update(download_bytes=size, http_status=st, content_type=ctype)
            disk_log.write(f"{time.strftime('%H:%M:%S')},{slug},{du(os.path.join(S, 'work'))}\n"); disk_log.flush()
            members = list(iter_members(dest))
            res["xml_members"] = len(members)
            res["uncompressed_bytes"] = sum(m[1] or 0 for m in members) or None
            scans = [scan_member(n, o) for n, _, o in members]
            summary, findings = check_dataset(scans, TODAY)
            res["summary"], res["findings"] = summary, findings
            res["rules_version"] = RULES_VERSION
            if recheck:   # keep the XSD results, refresh only the consistency checks
                prev = json.load(open(outp))
                prev.update(summary=summary, findings=findings, rules_version=RULES_VERSION, download_bytes=size,
                            rechecked_at=time.strftime("%Y-%m-%d %H:%M"))
                res = prev
                raise StopIteration
            xres = {}
            members_sorted = sorted(members, key=lambda m: m[0])
            for key, schema in schemas.items():
                cats, msgs = Counter(), Counter()
                nvalid = nchecked = nskipped = nerr = 0; used = 0; total = 0; mem_skipped = 0
                for i, (name, usize, opener) in enumerate(members_sorted):
                    sz = usize or os.path.getsize(dest); total += sz
                    if i >= MAX_XSD_MEMBERS or sz > MAX_XSD_BYTES or used + sz > XSD_BUDGET:
                        nskipped += 1; continue
                    av = avail_bytes()
                    if av is not None and av < 6 * sz + 1_000_000_000:   # lxml tree ~ 5-6x the XML size
                        nskipped += 1; mem_skipped += 1; continue
                    used += sz
                    try:
                        ok, c, m, n = xsd_validate(opener, schema)
                    except Exception as e:  # not well-formed
                        ok, c, m, n = False, Counter({"not-well-formed": 1}), Counter({str(e)[:200]: 1}), 1
                    nchecked += 1; nvalid += ok; nerr += n; cats.update(c); msgs.update(m)
                xres[key] = {"documents_checked": nchecked, "documents_valid": nvalid, "documents_skipped": nskipped,
                             "dataset_valid": nchecked > 0 and nvalid == nchecked and nskipped == 0,
                             "checked_valid": nchecked > 0 and nvalid == nchecked,
                             "coverage_bytes": round(used / total, 3) if total else None,
                             "skipped_memory_guard": mem_skipped,
                             "errors": nerr, "by_category": dict(cats.most_common()),
                             "top_messages": dict(msgs.most_common(15))}
            res["xsd"] = xres
        except StopIteration:
            pass
        except Exception as e:
            res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        finally:
            if os.path.exists(dest):
                os.remove(dest)
        if not recheck:
            res["seconds"] = round(time.time() - t, 1)
        json.dump(res, open(outp, "w"), indent=1, ensure_ascii=False, default=str)
        if os.path.exists(lock):
            os.remove(lock)
        x = res.get("xsd", {})
        print(f"{slug}: {res.get('error','ok')} members={res.get('xml_members')} "
              f"netex={x.get('netex_1_3_2',{}).get('documents_valid')}/{x.get('netex_1_3_2',{}).get('documents_checked')} "
              f"netex2={x.get('netex_2_0_0',{}).get('documents_valid')} "
              f"epip={x.get('epip',{}).get('documents_valid')}/{x.get('epip',{}).get('documents_checked')} "
              f"{res['seconds']}s", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
