"""Minimal, polite Wikidata Query Service client (stdlib only).

- Identifiable User-Agent (WDQS policy).
- HTTP 429 / 503: waits exactly what Retry-After says (default 60 s), max 5 attempts.
- 1 s pause between queries; POST so long VALUES blocks fit.
"""
import json, time, urllib.request, urllib.parse, urllib.error, sys

ENDPOINT = "https://query.wikidata.org/sparql"
UA = "EasyByteLab-research/0.1 (contact: contact@easybyte.es)"
LANGS = ["en", "es", "fr", "de", "it", "pt", "pl", "ru", "uk", "tr",
         "ar", "fa", "ur", "hi", "bn", "zh", "ja", "ko", "sw", "am"]
LF = ",".join(f'"{l}"' for l in LANGS)
PAUSE = 1.0
_last = [0.0]


def q(query, attempts=5):
    for k in range(attempts):
        wait = PAUSE - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        data = urllib.parse.urlencode({"query": query}).encode()
        req = urllib.request.Request(ENDPOINT, data=data, headers={
            "User-Agent": UA, "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                _last[0] = time.time()
                return json.load(r)["results"]["bindings"]
        except urllib.error.HTTPError as e:
            _last[0] = time.time()
            if e.code in (429, 503, 502, 504):
                ra = e.headers.get("Retry-After")
                s = int(ra) if ra and ra.isdigit() else 60 * (k + 1)
                print(f"[wd] HTTP {e.code}; Retry-After={ra}; sleeping {s}s", file=sys.stderr)
                time.sleep(s)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"[wd] {e}; retry in 30s", file=sys.stderr)
            time.sleep(30)
    raise RuntimeError("WDQS: too many failures")


def qid(uri):
    return uri.rsplit("/", 1)[-1]


def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]
