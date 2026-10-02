"""Fetch the PEP 691 JSON simple index for every project in the frozen top list.
Stores a REDUCED copy (filename, upload-time, provenance present, yanked) in data/raw/simple/.
Hashes, sizes and other fields are dropped; PyPI's simple API carries no uploader identity."""
import concurrent.futures as cf, json, os, sys, time
from common import http_get, cache_read, cache_write, norm, DATA

ACCEPT = "application/vnd.pypi.simple.v1+json"
top = json.load(open(os.path.join(DATA, "top-pypi-packages-2026-10-01.json")))["rows"]


def one(row):
    name = norm(row["project"])
    c = cache_read("simple", name)
    if c is not None:
        return name, c.get("status")
    st, body, _ = http_get(f"https://pypi.org/simple/{name}/", ACCEPT)
    obj = {"name": name, "status": st, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if body:
        s = json.loads(body)
        obj["api_version"] = s.get("meta", {}).get("api-version")
        obj["versions"] = s.get("versions", [])
        obj["files"] = [{"f": f["filename"], "t": f.get("upload-time"),
                         "p": bool(f.get("provenance")), "y": bool(f.get("yanked"))}
                        for f in s.get("files", [])]
    cache_write("simple", name, obj)
    return name, st


if __name__ == "__main__":
    t0 = time.time(); n = 0; bad = {}
    with cf.ThreadPoolExecutor(int(os.environ.get("THREADS", "24"))) as ex:
        for name, st in ex.map(one, top):
            n += 1
            if st != 200:
                bad[name] = st
            if n % 1000 == 0:
                print(f"{n} done, {time.time()-t0:.0f}s, non-200: {len(bad)}", flush=True)
    print("finished", n, "non-200:", bad)
