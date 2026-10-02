"""Group PyPI files into versions (PEP 440).

Two readers that must agree (01b_export_compact.py asserts it):
- raw_versions(): from the request cache data/raw/simple/ (not published);
- versions():     from the published compact tables in data/compact/ (what every analysis step uses).

Attestation is dated per FILE: `t_att` is the earliest upload time of an attested file of the version, so a
wheel added (attested) in 2024-12 to a version first released in 2023 is dated 2024-12, not 2023."""
import csv, gzip, os, re
from datetime import datetime, timezone
from packaging.utils import parse_wheel_filename, parse_sdist_filename, canonicalize_name
from packaging.version import Version, InvalidVersion
from common import cache_read, DATA

SNAP = datetime(2026, 10, 1, 12, 40, 51, tzinfo=timezone.utc)  # hugovk list last_update; later files ignored
SPLIT = datetime(2024, 9, 1, tzinfo=timezone.utc)                # files from here on are published one by one
EXT = re.compile(r"\.(tar\.gz|tar\.bz2|tar\.xz|tgz|zip|egg|exe|msi|rpm|dmg|tar)$", re.I)


def file_version(fn, project):
    try:
        if fn.endswith(".whl"):
            return parse_wheel_filename(fn)[1]
        if fn.endswith(".tar.gz") or fn.endswith(".zip"):
            return parse_sdist_filename(fn)[1]
    except Exception:
        pass
    base = EXT.sub("", fn)
    if fn.endswith(".egg"):
        base = base.rsplit("-py", 1)[0]
    if fn.endswith(".exe") or fn.endswith(".msi"):
        base = re.sub(r"\.(win32|win-amd64|linux-x86_64|macosx[^-]*)(-py\d\.\d+)?$", "", base)
    parts = base.split("-")
    for i in range(1, len(parts)):
        if canonicalize_name("-".join(parts[:i])) == project:
            try:
                return Version("-".join(parts[i:]))
            except InvalidVersion:
                return None
    return None


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _new(v, vs):
    return {"v": v, "vs": vs, "files": 0, "live": 0, "prov": 0, "t": None, "t_last": None, "t_att": None, "pf": []}


def _add(r, t, live_n, prov_n, n=1, t_last=None, fn=None):
    r["files"] += n
    r["t"] = t if r["t"] is None or t < r["t"] else r["t"]
    tl = t_last or t
    r["t_last"] = tl if r["t_last"] is None or tl > r["t_last"] else r["t_last"]
    r["live"] += live_n
    r["prov"] += prov_n
    if prov_n and fn:
        r["pf"].append(fn)
        r["t_att"] = t if r["t_att"] is None or t < r["t_att"] else r["t_att"]


def _finish(by):
    out = []
    for r in by.values():
        if r["live"] == 0:
            continue  # fully yanked version
        r["pre"] = r["v"].is_prerelease or r["v"].is_devrelease
        r["att"] = r["prov"] > 0
        r["att_all"] = r["prov"] == r["live"]
        out.append(r)
    out.sort(key=lambda r: (r["t"], r["v"]))
    return out


def raw_files(project, cutoff=SNAP):
    """Yield (version, version_string, filename, upload datetime, provenance, yanked) from the raw cache."""
    d = cache_read("simple", project)
    if d is None or d.get("status") != 200:
        return (d or {}).get("status"), []
    vmap = {}
    for s in d.get("versions", []):
        try:
            vmap.setdefault(Version(s), s)
        except InvalidVersion:
            pass
    rows = []
    for f in d.get("files", []):
        if not f.get("t"):
            continue
        t = ts(f["t"])
        if t > cutoff:
            continue
        v = file_version(f["f"], project)
        if v is None:
            continue
        rows.append((v, vmap.get(v, str(v)), f["f"], t, bool(f["p"]), bool(f["y"])))
    return 200, rows


def raw_versions(project, cutoff=SNAP):
    status, rows = raw_files(project, cutoff)
    by = {}
    for v, vs, fn, t, p, y in rows:
        r = by.setdefault(v, _new(v, vs))
        _add(r, t, 0 if y else 1, 1 if (p and not y) else 0, fn=fn)
    return status, _finish(by)


_C = None
import threading
_LOCK = threading.Lock()


def _compact():
    global _C
    with _LOCK:
        if _C is None:
            _C = _load()
    return _C


def _load():
    if True:
        _C = {"files": {}, "old": {}}
        with gzip.open(os.path.join(DATA, "compact", "pypi_files.csv.gz"), "rt", newline="") as f:
            for r in csv.DictReader(f):
                _C["files"].setdefault(r["project"], []).append(r)
        with gzip.open(os.path.join(DATA, "compact", "pypi_old_versions.csv.gz"), "rt", newline="") as f:
            for r in csv.DictReader(f):
                _C["old"].setdefault(r["project"], []).append(r)
        return _C


def versions(project, cutoff=SNAP):
    """Versions of a project from the published compact tables (same result as raw_versions)."""
    c = _compact()
    if project not in c["files"] and project not in c["old"]:
        return None, []
    by = {}
    for r in c["old"].get(project, []):
        v = Version(r["version"])
        x = by.setdefault(v, _new(v, r["version"]))
        _add(x, ts(r["first_upload"]), int(r["live_files"]), 0, n=int(r["live_files"]) + int(r["yanked_files"]), t_last=ts(r["last_upload"]))
    for r in c["files"].get(project, []):
        t = ts(r["upload_time"])
        if t > cutoff:
            continue
        v = Version(r["version"])
        x = by.setdefault(v, _new(v, r["version"]))
        y = r["yanked"] == "1"
        _add(x, t, 0 if y else 1, 1 if (r["provenance"] == "1" and not y) else 0, fn=r["filename"])
    return 200, _finish(by)


def highest_stable(vs):
    st = [r for r in vs if not r["pre"]]
    return max(st or vs, key=lambda r: r["v"]) if vs else None
