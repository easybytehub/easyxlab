"""Shared helpers for study S5: polite HTTP with a global rate limit, gzip cache."""
import gzip, json, os, re, threading, time, urllib.request, urllib.error

UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")


class RateLimiter:
    """Global token spacing shared by all threads (default 7 requests/s, below PyPI's ~8/s ask)."""
    def __init__(self, per_second=7.0):
        self.interval = 1.0 / per_second
        self.lock = threading.Lock()
        self.next = time.monotonic()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.interval
        d = t - time.monotonic()
        if d > 0:
            time.sleep(d)


LIMITERS = {}


def limiter(host, rate):
    if host not in LIMITERS:
        LIMITERS[host] = RateLimiter(rate)
    return LIMITERS[host]


OFFLINE = os.environ.get("OFFLINE") == "1"
COMPACT = os.path.join(DATA, "compact")
COMPACT_KINDS = ("integrity", "npm_corgi", "npm_time", "npm_att", "gh_redirect", "pypi_json", "gh_atom2")
_EVID = None


class OfflineMiss(RuntimeError):
    pass


_ELOCK = threading.Lock()


def _evidence():
    """Published compact evidence (data/compact/evidence.jsonl.gz): reduced records keyed by (kind, key)."""
    global _EVID
    with _ELOCK:
        if _EVID is None:
            _EVID = _load_evidence()
    return _EVID


def _load_evidence():
    if True:
        _EVID = {}
        p = os.path.join(COMPACT, "evidence.jsonl.gz")
        if os.path.exists(p):
            with gzip.open(p, "rt") as f:
                for line in f:
                    r = json.loads(line)
                    _EVID[(r["kind"], r["key"])] = r["obj"]
        return _EVID


def http_get(url, accept=None, rate=7.0, timeout=60, retries=4, method="GET"):
    """Return (status, bytes or None, final_url). Retries 429/5xx honouring Retry-After.
    With OFFLINE=1 any attempt to reach the network raises OfflineMiss (nothing is fetched or cached)."""
    if OFFLINE:
        raise OfflineMiss(url)
    host = url.split("/")[2]
    h = {"User-Agent": UA}
    if accept:
        h["Accept"] = accept
    for attempt in range(retries):
        limiter(host, rate).wait()
        req = urllib.request.Request(url, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                ra = e.headers.get("Retry-After")
                time.sleep(float(ra) if ra and ra.isdigit() else 2 ** attempt * 2)
                continue
            return e.code, None, url
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            return -1, None, url
    return -1, None, url


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def cache_path(kind, key):
    d = os.path.join(RAW, kind)
    os.makedirs(d, exist_ok=True)
    key = key.replace("/", "__")
    return os.path.join(d, key + ".json.gz")


def cache_read(kind, key):
    p = os.path.join(RAW, kind, key.replace("/", "__") + ".json.gz")
    if os.path.exists(p):
        with gzip.open(p, "rt") as f:
            return json.load(f)
    if kind in COMPACT_KINDS:
        # GitHub repository names are case-insensitive (and so is the macOS cache): match redirects case-insensitively
        return _evidence().get((kind, key.lower() if kind == "gh_redirect" else key))
    return None


def cache_write(kind, key, obj):
    p = cache_path(kind, key)
    with gzip.open(p + ".tmp", "wt") as f:
        json.dump(obj, f, separators=(",", ":"))
    os.replace(p + ".tmp", p)
