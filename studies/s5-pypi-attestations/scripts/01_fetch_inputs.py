"""Download the pinned population inputs into data/raw/ (they are NOT redistributed by this study).
- hugovk/top-pypi-packages: top-pypi-packages.min.json at a pinned commit, checked by SHA-256
  (the repository declares no licence, so the list is fetched, never copied into data/);
- npm-high-impact 1.13.0 (MIT): registry tarball, checked against the registry's sha512 integrity;
- Trail of Bits are-we-pep740-yet results.json (BSD-2-Clause): a page regenerated daily, so it cannot be
  pinned; the 2026-10-02 snapshot used here is identified by its SHA-256 and last_update."""
import base64, hashlib, io, json, os, tarfile
from common import http_get, RAW

HUGOVK_COMMITS = ["e6b5b398c1fc", "d4256d0301bb"]  # 2026-10-01 "Fix data for September" / deploy
HUGOVK_SHA256 = "55fee05ed02b628f05350a51780ec436efae39ea0810df5d5419e15b850c7041"
TOB_SHA256_2026_10_02 = None  # filled in METHOD.md; printed below

if __name__ == "__main__":
    os.makedirs(RAW, exist_ok=True)
    dst = os.path.join(RAW, "top-pypi-packages.min.json")
    if not (os.path.exists(dst) and hashlib.sha256(open(dst, "rb").read()).hexdigest() == HUGOVK_SHA256):
        for c in HUGOVK_COMMITS:
            st, body, _ = http_get(f"https://raw.githubusercontent.com/hugovk/top-pypi-packages/{c}/top-pypi-packages.min.json", rate=2)
            if body and hashlib.sha256(body).hexdigest() == HUGOVK_SHA256:
                open(dst, "wb").write(body); print("hugovk list OK at commit", c); break
            print("commit", c, "status", st, "sha256", hashlib.sha256(body or b"").hexdigest()[:16], "(no match)")
        else:
            raise SystemExit("pinned hugovk list not found; see METHOD.md")
    else:
        print("hugovk list present, SHA-256 OK")
    pkg = os.path.join(RAW, "npm", "package", "lib", "top-download.js")
    if not os.path.exists(pkg):
        st, body, _ = http_get("https://registry.npmjs.org/npm-high-impact/1.13.0")
        dist = json.loads(body)["dist"]
        st, tgz, _ = http_get(dist["tarball"])
        algo, b64 = dist["integrity"].split("-", 1)
        assert base64.b64encode(hashlib.new(algo, tgz).digest()).decode() == b64, "integrity mismatch"
        tarfile.open(fileobj=io.BytesIO(tgz)).extractall(os.path.join(RAW, "npm"), filter="data")
        print("npm-high-impact 1.13.0 OK", dist["integrity"][:30])
    else:
        print("npm-high-impact present")
    tob = os.path.join(RAW, "src", "tob_results_2026-10-02.json")
    if os.path.exists(tob):
        print("ToB snapshot sha256", hashlib.sha256(open(tob, "rb").read()).hexdigest())
    else:
        print("ToB 2026-10-02 snapshot not available; the comparison in metrics.json is kept as published")
