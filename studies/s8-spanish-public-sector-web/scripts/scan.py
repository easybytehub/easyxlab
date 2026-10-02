#!/usr/bin/env python3
"""S8 scanner: what a machine can verify on a public-sector website.

Version 2 (corrected after the adversarial review of 2026-10-02). Differences from the version
that took the published measurement are listed in METHOD.md s. 7.

Politeness, for every entity URL in data/population.csv:
  * robots.txt (RFC 9309) is read before ANY other request to a host, and every request,
    redirect hops included, is checked against the robots.txt of the host it goes to. The body
    is parsed whatever Content-Type it is served with (RFC 9309 s. 2.3.1.1). A 4xx robots.txt
    means no restrictions (s. 2.3.1.3); a 5xx, a network error or more than five redirects
    means complete disallow (s. 2.3.1.4). Nothing is exempt: not the home page, not
    /.well-known/security.txt, not /llms.txt, not the accessibility statement.
  * at most four resource fetches per host over the whole run, robots.txt and fallbacks
    included (a redirect hop into another host costs one fetch of that host);
  * at most one request per second per host, redirect hops and TLS retries included.

Privacy: no response body is written to disk. From security.txt only booleans and metadata are
kept, never the Contact values. From a home page only booleans, the extracted link and a short
page title are kept.

The User-Agent must identify whoever runs the scan: pass --user-agent "Name/1.0 (+URL)" or set
S8_USER_AGENT. EasyxLab's runs use "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)".

Python >= 3.10, standard library only.
"""
import argparse, csv, hashlib, html, json, os, re, socket, ssl, sys, threading, time, unicodedata, zlib
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from urllib.parse import urljoin, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import robots9309 as R  # noqa: E402

SCANNER_VERSION = "2"
EASYXLAB_UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
TIMEOUT = 15
MAX_HOPS = 5
PER_HOST_FETCHES = 4
MIN_INTERVAL = 1.0
SCAN_DATE = date.today()

AI_TOKENS = ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot",            # the four headline tokens
             "anthropic-ai", "Applebot-Extended", "Bytespider", "meta-externalagent", "cohere-ai",
             "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Claude-SearchBot", "Claude-User"]


def ai_key(t):
    return "ai_" + re.sub(r"[^a-z0-9]", "_", t.lower())


def product_token_of(ua):
    m = re.match(r"[A-Za-z_-]+", ua.strip())
    if not m:
        raise SystemExit("the User-Agent must start with a product token (letters, '-' or '_')")
    return m.group(0)


# ---------------------------------------------------------------- polite HTTP session
class HostState:
    def __init__(self):
        self.lock = threading.Lock()
        self.last = 0.0
        self.fetches = 0      # resource fetches started on this host (budget)
        self.requests = 0     # HTTP requests incl. redirect hops and TLS retries


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_ctx_ok = ssl.create_default_context()
_ctx_insecure = ssl.create_default_context()
_ctx_insecure.check_hostname = False
_ctx_insecure.verify_mode = ssl.CERT_NONE
_openers = {
    True: urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=_ctx_ok)),
    False: urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=_ctx_insecure)),
}
REDIRECTS = (301, 302, 303, 307, 308)


def authority(url):
    """host[:port] of a URL, lower-case, without a default port (so that 'https://vigo.gal:443/'
    and 'https://vigo.gal/' are the same site). Budget, pacing and robots.txt are per authority."""
    p = urlsplit(url)
    h = (p.hostname or "").lower()
    try:
        port = p.port
    except ValueError:
        port = None
    if port and not ((p.scheme == "http" and port == 80) or (p.scheme == "https" and port == 443)):
        return f"{h}:{port}"
    return h


def decode_body(body, hdrs):
    """Some servers send a gzip/deflate body although the request carries no Accept-Encoding.
    Decompress it (as much as was read) instead of reading binary as text."""
    enc = hdrs.get("content-encoding", "").lower()
    if body[:2] == b"\x1f\x8b" or "gzip" in enc or "deflate" in enc:
        for wbits in (16 + zlib.MAX_WBITS, zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                out = zlib.decompressobj(wbits).decompress(body, 4_000_000)
                hdrs["x-s8-decompressed"] = "1"
                return out
            except zlib.error:
                continue
    return body


class Session:
    """Per-host budget, pacing and robots.txt, shared by all worker threads."""

    def __init__(self, user_agent, per_host=PER_HOST_FETCHES, min_interval=MIN_INTERVAL):
        self.ua = user_agent
        self.token = product_token_of(user_agent)
        self.per_host = per_host
        self.min_interval = min_interval
        self._hosts, self._robots = {}, {}
        self._lock = threading.Lock()

    # budget and pacing
    def host_state(self, h):
        with self._lock:
            if h not in self._hosts:
                self._hosts[h] = HostState()
            return self._hosts[h]

    def reserve(self, h):
        st = self.host_state(h)
        with st.lock:
            if st.fetches >= self.per_host:
                return False
            st.fetches += 1
            return True

    def pace(self, h):
        st = self.host_state(h)
        with st.lock:
            wait = st.last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            st.last = time.monotonic()
            st.requests += 1

    def stats(self):
        return (len(self._hosts), max((s.fetches for s in self._hosts.values()), default=0),
                max((s.requests for s in self._hosts.values()), default=0))

    # one HTTP request
    def _one(self, url, verify, limit):
        req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept": "*/*",
                                                   "Accept-Language": "es,en;q=0.5"})
        try:
            r = _openers[verify].open(req, timeout=TIMEOUT)
        except urllib.error.HTTPError as e:
            r = e
        body = b""
        try:
            body = r.read(limit) if r.fp else b""
        except Exception:
            pass
        hdrs = {k.lower(): v for k, v in (r.headers.items() if r.headers else [])}
        return (r.status if hasattr(r, "status") and r.status else r.code), hdrs, decode_body(body, hdrs)

    def _request(self, url, h, limit):
        """Paced request; on a certificate error (raised in the TLS handshake, before any HTTP
        request is sent) repeat once without verification, also paced."""
        self.pace(h)
        try:
            st, hd, body = self._one(url, True, limit)
            return st, hd, body, False
        except urllib.error.URLError as e:
            if not isinstance(e.reason, ssl.SSLCertVerificationError):
                raise
        self.pace(h)
        st, hd, body = self._one(url, False, limit)
        return st, hd, body, True

    def get(self, url, limit=600_000, robots=True):
        """GET with redirects followed by us. Every host the request enters costs one fetch of
        that host's budget; with robots=True every hop is checked against that host's
        robots.txt first (fetching it if needed). robots=False only for /robots.txt itself."""
        out = dict(url=url, status=None, final_url=url, hops=0, error=None, cert_invalid=False,
                   headers={}, body=b"", https_final=False, blocked_host=None)
        cur, entered = url, set()
        for hop in range(MAX_HOPS + 1):
            h = authority(cur)
            if not h:
                out["error"] = "bad_url"
                return out
            if robots and not self.allowed(h, cur):
                out.update(error="robots_disallowed", blocked_host=h, final_url=cur)
                return out
            if h not in entered:
                if not self.reserve(h):
                    out.update(error="host_budget", blocked_host=h, final_url=cur)
                    return out
                entered.add(h)
            try:
                st, hd, body, bad_cert = self._request(cur, h, limit)
            except urllib.error.URLError as e:
                out["error"] = type(e.reason).__name__ if not isinstance(e.reason, str) else "URLError"
                return out
            except (socket.timeout, TimeoutError):
                out["error"] = "timeout"
                return out
            except Exception as e:  # noqa: BLE001
                out["error"] = type(e).__name__
                return out
            out["cert_invalid"] = out["cert_invalid"] or bad_cert
            out.update(status=st, headers=hd, body=body, final_url=cur, hops=hop,
                       https_final=cur.lower().startswith("https://"))
            if st in REDIRECTS and hd.get("location"):
                cur = urljoin(cur, hd["location"].strip())
                continue
            return out
        out["error"] = "too_many_redirects"
        return out

    # robots.txt
    def robots_for(self, h):
        """robots.txt state of host h, fetched once per run (RFC 9309 s. 2.4 allows caching)."""
        with self._lock:
            rb = self._robots.get(h)
            owner = rb is None
            if owner:
                rb = self._robots[h] = {"event": threading.Event()}
        if not owner:
            rb["event"].wait(900)
            return rb
        try:
            rb.update(self._fetch_robots(h))
        finally:
            rb["event"].set()
        return rb

    def _fetch_robots(self, h):
        d = dict(state="unreachable", status=None, error=None, content_type="", html_typed=False,
                 groups=[], has_groups=False, http_upgrades=None, final_url="",
                 fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        # plain HTTP first on purpose: whether the server upgrades to HTTPS is read from this
        res = self.get(f"http://{h}/robots.txt", limit=R.PARSE_LIMIT, robots=False)
        d["http_upgrades"] = bool(res["status"] and res["https_final"]) if not res["error"] else None
        if res["error"] and res["error"] != "host_budget":
            res = self.get(f"https://{h}/robots.txt", limit=R.PARSE_LIMIT, robots=False)
        st = res["status"]
        ct = res["headers"].get("content-type", "")
        d.update(status=st, error=res["error"], final_url=res["final_url"], content_type=ct[:80],
                 html_typed="html" in ct.lower())
        if res["error"] or st is None:
            d["state"] = "unreachable"          # s. 2.3.1.4 (also budget, >5 redirects)
        elif 200 <= st < 300:
            # a successful download (s. 2.3.1.1): parse it whatever the Content-Type. A 2xx bot
            # challenge page (e.g. 202 + HTML) simply contains no rules.
            d["groups"] = R.parse(res["body"])
            d["has_groups"] = R.has_groups(d["groups"])
            d["state"] = "ok"
        elif 400 <= st < 500:
            d["state"] = "unavailable"          # s. 2.3.1.3: no restrictions
        else:
            d["state"] = "unreachable"          # 5xx, or an unresolved 3xx
        return d

    def allowed(self, h, url):
        rb = self.robots_for(h)
        if rb.get("state") == "ok":
            return R.allowed(rb["groups"], self.token, url)
        return rb.get("state") == "unavailable"


def is_html(res):
    ct = res["headers"].get("content-type", "").lower()
    head = res["body"][:300].lstrip().lower()
    return "html" in ct or head.startswith(b"<!doctype") or head.startswith(b"<html") or head.startswith(b"<")


def text(res):
    b = res["body"]
    ct = res["headers"].get("content-type", "")
    m = re.search(r"charset=([\w-]+)", ct, re.I)
    enc = m.group(1) if m else None
    if not enc:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', b[:3000], re.I)
        enc = m.group(1).decode() if m else "utf-8"
    try:
        return b.decode(enc, "replace")
    except LookupError:
        return b.decode("utf-8", "replace")


# ---------------------------------------------------------------- robots-derived indicators
def robots_fields(rb):
    """Indicators read from a robots.txt state (published per entity)."""
    d = dict(robots_state=rb.get("state"), robots_status=rb.get("status"), robots_error=rb.get("error"),
             robots_html_typed=rb.get("html_typed"), robots_has_groups=rb.get("has_groups"),
             http_upgrades_to_https=rb.get("http_upgrades"))
    if rb.get("state") == "ok":
        g = rb["groups"]
        d["robots_star_blocks_root"] = R.blocks_root(g, "*") if any("*" in x["agents"] for x in g) else False
        for t in AI_TOKENS:
            d[ai_key(t) + "_named"] = R.named(g, t)
            d[ai_key(t) + "_blocked"] = R.blocks_root(g, t)
    elif rb.get("state") == "unavailable":
        d["robots_star_blocks_root"] = False
        for t in AI_TOKENS:
            d[ai_key(t) + "_named"] = False
            d[ai_key(t) + "_blocked"] = False
    return d


# ---------------------------------------------------------------- security.txt (RFC 9116)
# lenient: what the first version accepted, plus lowercase "t"/"z" (RFC 3339 s. 5.6 note)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}(:\d{2}(\.\d+)?)?([Zz]|[+-]\d{2}:?\d{2})$")
# strict RFC 3339 date-time: seconds required, offset with a colon
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")
URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:\S+$")
FIELD = re.compile(r"^([A-Za-z0-9!#$%&'*+.^_`|~-]+):\s*(.*?)\s*$")
WEB_URI_FIELDS = ("contact", "encryption", "acknowledgments", "canonical", "policy", "hiring")


def _parse_expires(e):
    e = e.strip()
    if not ISO.match(e):
        return None
    e = re.sub(r"[Zz]$", "+00:00", e).replace("t", "T")
    e = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", e)
    try:
        dt = datetime.fromisoformat(e)
    except ValueError:
        return None
    return dt if dt.tzinfo else None


def check_security_txt(res):
    d = dict(sectxt_status=res["status"], sectxt_present=False, sectxt_soft404=False,
             sectxt_https=res["https_final"], sectxt_text_plain=False, sectxt_utf8=False,
             sectxt_contact=False, sectxt_contact_mailto=False, sectxt_contact_https=False,
             sectxt_contact_tel=False, sectxt_expires=False, sectxt_expires_parse=False,
             sectxt_expires_once=False, sectxt_expired=None, sectxt_expires_gt_1y=None,
             sectxt_signed=False, sectxt_policy=False, sectxt_canonical=False,
             sectxt_canonical_match=None, sectxt_pref_lang=False,
             sectxt_required_ok=False, sectxt_strict_ok=False)
    if res["status"] != 200 or res["error"]:
        return d
    raw = res["body"]
    t = text(res)
    lines = t.splitlines()
    fields = {}
    for ln in lines:
        m = FIELD.match(ln)
        if m and not ln.startswith("#"):
            fields.setdefault(m.group(1).lower(), []).append(m.group(2))
    contacts, exp = fields.get("contact", []), fields.get("expires", [])
    if not contacts and not exp:
        # an HTML page, or a text file without any security.txt field: a "soft 404"
        d["sectxt_soft404"] = True
        return d
    ct = res["headers"].get("content-type", "")
    mime = ct.split(";")[0].strip().lower()
    charset = (re.search(r"charset\s*=\s*\"?([\w-]+)", ct, re.I) or [None, ""])[1].lower()
    try:
        raw.decode("utf-8")
        utf8_body = True
    except UnicodeDecodeError:
        utf8_body = False
    signed = "-----BEGIN PGP SIGNED MESSAGE-----" in t
    # every non-empty line must be a comment or a field (outside the OpenPGP armour)
    body_lines, in_sig = [], False
    for ln in lines:
        s = ln.strip()
        if s.startswith("-----BEGIN PGP SIGNATURE"):
            in_sig = True
        if in_sig or s.startswith("-----BEGIN PGP SIGNED MESSAGE") or s.lower().startswith("hash:"):
            continue
        if s.startswith("- "):
            s = s[2:]
        body_lines.append(s)
    lines_ok = all((not s) or s.startswith("#") or FIELD.match(s) for s in body_lines)
    dt = _parse_expires(exp[0]) if exp else None
    now = datetime.now(timezone.utc)
    d.update(sectxt_present=True, sectxt_text_plain=mime == "text/plain", sectxt_utf8=charset == "utf-8",
             sectxt_contact=bool(contacts),
             sectxt_contact_mailto=any(c.lower().startswith("mailto:") for c in contacts),
             sectxt_contact_https=any(c.lower().startswith("https:") for c in contacts),
             sectxt_contact_tel=any(c.lower().startswith("tel:") for c in contacts),
             sectxt_contact_all_uri=bool(contacts) and all(URI.match(c) for c in contacts),
             sectxt_web_uris_https=all(not v.lower().startswith("http:") for f in WEB_URI_FIELDS
                                       for v in fields.get(f, [])),
             sectxt_expires=bool(exp), sectxt_expires_once=len(exp) == 1,
             sectxt_expires_parse=dt is not None,
             sectxt_expires_rfc3339=bool(exp) and bool(RFC3339.match(exp[0].strip())),
             sectxt_body_utf8=utf8_body, sectxt_lines_ok=lines_ok,
             sectxt_pref_lang_once=len(fields.get("preferred-languages", [])) <= 1,
             sectxt_signed=signed, sectxt_policy=bool(fields.get("policy")),
             sectxt_canonical=bool(fields.get("canonical")),
             sectxt_pref_lang=bool(fields.get("preferred-languages")))
    if fields.get("canonical"):
        d["sectxt_canonical_match"] = any(c.strip().rstrip("/") == res["final_url"].rstrip("/")
                                          for c in fields["canonical"])
    if dt is not None:
        d.update(sectxt_expired=dt < now, sectxt_expires_gt_1y=(dt - now).days > 366)
    # level 1: the two required fields, served over HTTPS, Expires a date in the future
    d["sectxt_required_ok"] = bool(d["sectxt_https"] and contacts and len(exp) == 1 and dt is not None
                                   and dt >= now)
    # level 2: every RFC 9116 MUST this scanner can test (signatures are not verified)
    d["sectxt_strict_ok"] = bool(d["sectxt_required_ok"] and d["sectxt_text_plain"] and d["sectxt_utf8"]
                                 and utf8_body and d["sectxt_contact_all_uri"] and d["sectxt_web_uris_https"]
                                 and d["sectxt_expires_rfc3339"] and d["sectxt_pref_lang_once"] and lines_ok)
    d["sectxt_valid"] = d["sectxt_required_ok"]       # name used by the first version
    return d


def check_llms(res):
    d = dict(llms_status=res["status"], llms_present=False, llms_soft404=False, llms_h1=False)
    if res["status"] == 200 and not res["error"]:
        if is_html(res) or not res["body"].strip():
            d["llms_soft404"] = True
        else:
            d["llms_present"] = True
            d["llms_h1"] = text(res).lstrip().startswith("# ")
    return d


def hsts(hd):
    v = hd.get("strict-transport-security", "")
    m = re.search(r"max-age\s*=\s*\"?(\d+)", v, re.I)
    age = int(m.group(1)) if m else None
    return dict(hsts=bool(age), hsts_max_age=age, hsts_subdomains="includesubdomains" in v.lower(),
                hsts_preload="preload" in v.lower(), hsts_1y=bool(age and age >= 31536000))


# ---------------------------------------------------------------- accessibility link
ACC_WORD = re.compile(r"accesib|accessib|acessib|irisgarri", re.I)
STATEMENT_WORD = re.compile(r"declaraci[oó]n?|declaraci[oó]|adierazpen|declara", re.I)
BADGE = re.compile(r"w3\.org|tawdis|accesibilidad\.gob\.es/|webaim|wcag", re.I)
# accessibility widget / plug-in vendors: their links are credits or tools, not a statement
ACC_VENDOR = re.compile(r"(^|\.)(accessibility-helper\.co\.il|dj-extensions\.com|pluginsmarket\.com|"
                        r"inclusite\.com|userway\.org|accessibe\.com|equalweb\.com|"
                        r"accessiblewebsites\.eu|reciteme\.com|insuit\.net)$", re.I)
CREDIT = re.compile(r"accessibility by|powered by|plugin|plug-in|widget|desarrollado por|developed by", re.I)
A_TAG = re.compile(r"<a\b([^>]*)>(.*?)</a\s*>", re.I | re.S)
HREF = re.compile(r"href\s*=\s*[\"']([^\"']+)[\"']", re.I)
TITLE = re.compile(r"title\s*=\s*[\"']([^\"']*)[\"']", re.I)


def find_accessibility_link(page, base):
    best = None
    for attrs, inner in A_TAG.findall(page):
        hm = HREF.search(attrs)
        if not hm:
            continue
        href = html.unescape(hm.group(1).strip())
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        label = html.unescape(re.sub(r"<[^>]+>", " ", inner))
        tm = TITLE.search(attrs)
        label += " " + (html.unescape(tm.group(1)) if tm else "")
        alt = " ".join(re.findall(r"alt\s*=\s*[\"']([^\"']*)", inner, re.I))
        hay = label + " " + alt
        if BADGE.search(href):
            continue
        full = urljoin(base, href)
        if ACC_VENDOR.search(urlsplit(full).hostname or "") or CREDIT.search(hay):
            continue
        score = 0
        short = len(re.sub(r"\s+", " ", hay).strip()) <= 60
        if ACC_WORD.search(hay):
            score += 3 if short else 1
            if STATEMENT_WORD.search(hay) and short:
                score += 2
        if ACC_WORD.search(href):
            score += 2
            if STATEMENT_WORD.search(href):
                score += 1
        if score < 2:
            continue      # a long label that merely mentions accessibility is not a link to the statement
        if best is None or score > best[0]:
            best = (score, full, bool(STATEMENT_WORD.search(hay + href)))
    if not best:
        return None, False
    return best[1], best[2]


# ---------------------------------------------------------------- statement dates (extractor v2)
MONTHS = {
    # es, ca, gl, eu, en, va
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "gener": 1, "febrer": 2, "març": 3, "maig": 5, "juny": 6, "juliol": 7, "agost": 8,
    "setembre": 9, "octubre_ca": 10, "novembre": 11, "desembre": 12,
    "xaneiro": 1, "febreiro": 2, "marzo_gl": 3, "maio": 5, "xuño": 6, "xullo": 7,
    "outubro": 10, "novembro": 11, "decembro": 12,
    "urtarril": 1, "otsail": 2, "martxo": 3, "apiril": 4, "maiatz": 5, "ekain": 6, "uztail": 7,
    "abuztu": 8, "irail": 9, "urri": 10, "azaro": 11, "abendu": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
MONTH_RX = "|".join(sorted((k.split("_")[0] for k in MONTHS), key=len, reverse=True))
D_NUM = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
D_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
D_TXT = re.compile(r"\b(\d{1,2})(?:º|\.)?\s+(?:de\s+|d'|d’)?(" + MONTH_RX + r")\w*\s+(?:de\s+|del\s+)?(\d{4})\b", re.I)
D_EU = re.compile(r"\b(\d{4})(?:ko|eko)?\s+(" + MONTH_RX + r")\w*\s+(\d{1,2})", re.I)
# Extractor v2 (from the 2026-10-02 inspection of v1): only participles/nouns that refer to
# preparing or reviewing the statement itself. Generic page words ("fecha", "data", "última",
# "Darrera actualització: 23.05.2024 | 13:36" CMS footers, "Data i hora oficials" clocks) are out.
# Unchanged in scanner version 2, so that all published dates come from one extractor.
DATE_CONTEXT = re.compile(r"preparad[ao]|preparada|preparat|preparación|preparació|preparou|"
                          r"revisad[ao]|revisada|revisió|revisión|revisión|revisado|revisou|"
                          r"elaborad[ao]|elaboració|elaboración|actualizad[ao]|actualitzada|"
                          r"berrikus|eguneratu|prestatu|egin zen|prepared|reviewed|updated on", re.I)
NOT_STATEMENT = re.compile(r"darrera actualització\s*:|data i hora oficials|última actualización\s*:\s*\d", re.I)


def _mk(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def statement_dates(t, scan_date=None):
    """Dates that appear within 160 characters after a preparation/review keyword."""
    scan_date = scan_date or SCAN_DATE
    out = []
    for m in DATE_CONTEXT.finditer(t):
        win = t[m.start(): m.start() + 160]
        if NOT_STATEMENT.search(t[max(0, m.start() - 40): m.start() + 40]):
            continue
        for rx, order in ((D_NUM, "dmy"), (D_ISO, "ymd"), (D_TXT, "dMy"), (D_EU, "yMd")):
            for g in rx.finditer(win):
                a, b, c = g.groups()
                if order == "dmy":
                    dt = _mk(c, b, a)
                elif order == "ymd":
                    dt = _mk(a, b, c)
                elif order == "dMy":
                    dt = _mk(c, MONTHS.get(b.lower(), MONTHS.get(b.lower().rstrip("a"), 0)) or 0, a)
                else:
                    dt = _mk(a, MONTHS.get(b.lower(), 0) or 0, c)
                if dt and date(2018, 9, 1) <= dt <= scan_date:
                    out.append((dt, win[:160]))
    return out


STATEMENT_TEXT = re.compile(
    r"declaraci[oó]n de accesibilidad|declaració d.accessibilitat|declaración de accesibilidade|"
    r"declaración de accesibilidade|declaraci[oó]n|irisgarritasun[- ]adierazpen|Real Decreto 1112/2018|"
    r"RD 1112/2018|1112/2018", re.I)


def page_text(raw_html):
    t = html.unescape(re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw_html, flags=re.S | re.I))
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


def check_statement(res, scan_date=None):
    scan_date = scan_date or SCAN_DATE
    d = dict(stmt_extractor="v2", stmt_status=res["status"], stmt_ok=False, stmt_html=False,
             stmt_about_accessibility=False, stmt_has_date=False, stmt_latest_date=None,
             stmt_age_days=None, stmt_fresh_1y=None)
    if res["status"] != 200 or res["error"]:
        return d
    if not is_html(res):
        # PDF or other document: existence only
        d.update(stmt_ok=True, stmt_format=res["headers"].get("content-type", "")[:40])
        return d
    t = page_text(text(res))
    d.update(stmt_ok=True, stmt_html=True)
    d["stmt_about_accessibility"] = bool(ACC_WORD.search(t)) and bool(STATEMENT_TEXT.search(t))
    ds = statement_dates(t, scan_date)
    if ds:
        last, ctx = max(ds, key=lambda x: x[0])
        age = (scan_date - last).days
        # the public sentence the date came from, kept for auditing the extractor
        d.update(stmt_has_date=True, stmt_latest_date=last.isoformat(), stmt_age_days=age,
                 stmt_fresh_1y=age <= 365, stmt_n_dates=len(ds), stmt_date_context=ctx)
    return d


# ---------------------------------------------------------------- is this the entity's site?
def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", " ", s)


def name_tokens(name):
    out = []
    for part in re.split(r"/", name):
        part = part.strip()
        m = re.match(r"^(.*), (.+)$", part)
        if m:
            part = m.group(2) + " " + m.group(1)
        n = re.sub(r"\s+", " ", norm(part)).strip()
        if n:
            out.append(n)
    return out


def homepage_name_match(page, name):
    # version 1 did not unescape HTML entities ("&Aacute;vila"), so names with accents written
    # as entities were missed
    t = re.sub(r"\s+", " ", norm(html.unescape(re.sub(r"<[^>]+>", " ", page[:400_000]))))
    return any(tok in t for tok in name_tokens(name))


# Lenient name evidence, used only to decide whether a page is the municipality's own site.
# A "run" is any sequence of consecutive words of the name (both "Solana, La" orders, each
# part of a bilingual "A/B" name) that is at least 5 letters long once spaces are removed,
# does not start or end with an article/preposition, and is not made only of generic
# place-name words ("villa", "santa", "torre", ...), which alone would match other towns.
STOP = {"de", "del", "la", "las", "el", "los", "l", "d", "i", "y", "e", "s", "o", "a", "os", "as", "en",
        "les", "els", "sa", "ses", "es", "lo", "da", "do", "dos", "das", "con", "al", "eta", "n"}
GENERIC = {"villa", "valle", "vall", "santa", "santo", "sant", "san", "puebla", "pobla", "torre", "torres",
           "fuente", "fuentes", "font", "castillo", "castell", "sierra", "nueva", "nuevo", "nou", "nova",
           "real", "campo", "camp", "monte", "mont", "vega", "ribera", "villar", "aldea", "pinares",
           "frontera", "arriba", "abajo", "rio", "mayor", "alta", "alto", "baja", "bajo", "cerro",
           "barrio", "puerto", "port", "iglesia", "casas", "pueblo", "ciudad", "vila", "villanueva",
           "vilanova", "marina", "ayuntamiento", "navas", "palacios", "quintana", "quintanilla", "campos",
           "llano", "molina", "molinos", "majadas", "hoyos", "pozo", "pozuelo", "cuevas", "cueva",
           "castro", "castrillo", "villafranca", "villalba", "villamayor", "villaverde", "prado",
           "robledo", "valdes", "ribas", "olivares", "cabezas", "condado", "tierra", "arenas",
           # region and province names, which pages of other towns mention too
           "aragon", "castilla", "leon", "navarra", "galicia", "asturias", "cantabria", "murcia",
           "valencia", "rioja", "mancha", "extremadura", "andalucia", "catalunya", "cataluna",
           "canarias", "balears", "baleares", "madrid", "toledo", "burgos", "soria", "segovia",
           "avila", "zamora", "teruel", "huesca", "lleida", "girona", "tarragona", "alicante",
           "castellon", "albacete", "cuenca", "guadalajara", "palencia", "salamanca", "valladolid",
           "zaragoza", "granada", "malaga", "sevilla", "cordoba", "huelva", "cadiz", "almeria",
           "badajoz", "caceres", "orense", "ourense", "lugo", "coruna", "pontevedra", "bizkaia",
           "gipuzkoa", "alava", "araba", "cantabria", "oviedo", "mallorca", "menorca", "ibiza"}


def name_runs(name):
    variants = set()
    for part in re.split(r"/", name or ""):
        part = part.strip()
        variants.add(norm(part))
        m = re.match(r"^(.*), (.+)$", part)
        if m:
            variants.add(norm(m.group(2) + " " + m.group(1)))
            variants.add(norm(m.group(1)))
    runs = {re.sub(r"\s+", " ", v).strip() for v in variants if len(v.replace(" ", "")) >= 5}
    for v in variants:
        w = v.split()
        for i in range(len(w)):
            for j in range(i + 1, len(w) + 1):
                span = w[i:j]
                if span[0] in STOP or span[-1] in STOP:
                    continue
                if all(x in GENERIC or x in STOP for x in span):
                    continue
                if len("".join(span)) >= 5:
                    runs.add(" ".join(span))
    return runs


def name_in_text(text_norm, runs):
    t = " " + re.sub(r"\s+", " ", text_norm) + " "
    return any(" " + r + " " in t for r in runs)


def name_in_url(url, runs):
    p = urlsplit(url or "")
    compact = re.sub(r"[^a-z0-9]", "", norm((p.hostname or "") + " " + (p.path or "")))
    return any(r.replace(" ", "") in compact for r in runs)


TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title\s*>", re.I | re.S)
PANEL = re.compile(r"plesk|cpanel|webmin|ispconfig|directadmin|login_up\.php|defaultwebpage\.cgi", re.I)
DEFAULT_PAGE = re.compile(r"apache2 (ubuntu|debian) default page|welcome to nginx|iis windows server|"
                          r"test page for the (apache|nginx)|^index of /|domain default page|"
                          r"default web site page|web server.s default page|future home of something|"
                          r"site under construction|this site is under construction|"
                          r"(sitio|p[aá]gina|web) en construcci[oó]n", re.I)
# placeholders recognised in the <title> only (in body text these words are too common)
PLACEHOLDER_TITLE = re.compile(r"^\W*(coming soon|site is created successfully|pr[oó]ximamente|under construction|"
                               r"en construcci[oó]n|site en construction|web en mantenimiento|"
                               r"site is undergoing maintenance)\b|\W(coming soon|site is created successfully)\W*$", re.I)
PARKING = re.compile(r"domain (is|may be) for sale|this domain is for sale|buy this domain|domain for sale|"
                     r"dominio (est[aá] )?(a la |en )venta|este dominio (puede estar|est[aá]) en venta|"
                     r"parked (free|domain)|domain parking|sedoparking|parkingcrew|is parked|"
                     r"dominio en reserva|domain (is )?reserved|domain expired|dominio caducado", re.I)
COUNCIL = re.compile(r"ayuntamiento|ajuntament|concello|udala|udaletxea|aiuntamentu|\bconcejo\b|"
                     r"\bayto\b|casa consistorial|alcald|consistori|corporaci[oó]n municipal|"
                     r"pleno municipal|sede electr[oó]nica|seu electr[oò]nica|municipio|\bmunicipi\b|"
                     r"\bcouncil\b|\bconcell\b|\bcomune\b", re.I)


def is_shell(page):
    """Near-empty static page (content added by JavaScript). Version 1 measured the HTML without
    <script> blocks (< 3000 characters), which large inline CSS defeats; version 2 measures the
    visible text."""
    return len(page_text(page).strip()) < 400


def page_markers(page, final_url):
    """Short public signals about what a home page is (kept to audit the exclusion rules)."""
    tm = TITLE_TAG.search(page[:200_000])
    title = re.sub(r"\s+", " ", html.unescape(tm.group(1))).strip()[:120] if tm else ""
    head = (title + " " + page_text(page[:200_000])[:5000])
    return dict(home_title=title,
                home_panel=bool(PANEL.search(title) or PANEL.search(urlsplit(final_url).path)),
                home_default_page=bool(DEFAULT_PAGE.search(title) or DEFAULT_PAGE.search(head[:600])
                                       or PLACEHOLDER_TITLE.search(title)),
                home_parking=bool(PARKING.search(head)),
                home_council_word=bool(COUNCIL.search(head)))


# ---------------------------------------------------------------- per-entity job
def arm_of(host):
    """Deterministic 1-in-5 assignment: arm L spends the 4th fetch on /llms.txt even when an
    on-host accessibility statement could have been fetched. Gives an unbiased llms.txt rate."""
    return "L" if int(hashlib.sha256(host.encode()).hexdigest(), 16) % 5 == 0 else "S"


class Scanner:
    def __init__(self, session):
        self.S = session
        self._cache, self._lock = {}, threading.Lock()

    def _once(self, key, fn):
        """Run fn once per key (shared host files); other threads wait for the result."""
        with self._lock:
            c = self._cache.get(key)
            owner = c is None
            if owner:
                c = self._cache[key] = {"event": threading.Event(), "d": {}}
        if owner:
            try:
                c["d"] = fn()
            finally:
                c["event"].set()
        else:
            c["event"].wait(900)
        return c["d"]

    def security_txt(self, h):
        def go():
            res = self.S.get(f"https://{h}/.well-known/security.txt", limit=64_000)
            if res["error"] in ("robots_disallowed", "host_budget"):
                return {"sectxt_status": res["error"]}
            return check_security_txt(res)
        return dict(self._once("sec:" + h, go), sectxt_host=h)

    def llms(self, h, scheme):
        def go():
            res = self.S.get(f"{scheme}://{h}/llms.txt", limit=64_000)
            if res["error"] in ("robots_disallowed", "host_budget"):
                return {"llms_status": res["error"]}
            return check_llms(res)
        return self._once("llms:" + h, go)

    def scan_entity(self, e):
        S = self.S
        url = e["url"]
        p = urlsplit(url)
        host = authority(url)
        r = dict(entity_id=e["entity_id"], host=host, url=url, arm=arm_of(host), notes="",
                 scanner_version=SCANNER_VERSION, user_agent=S.ua)
        r.update(robots_fields(S.robots_for(host)))
        path = (p.path or "/") + (("?" + p.query) if p.query else "")
        hr = S.get(f"https://{host}{path}")
        if hr["error"] and hr["status"] is None and hr["error"] not in ("robots_disallowed", "host_budget"):
            # HTTPS failed below HTTP: try plain HTTP (a separate fetch, reserved and paced)
            r["https_home_error"] = hr["error"]
            hr2 = S.get(f"http://{host}{path}")
            if hr2["status"] is not None or hr2["error"] in ("robots_disallowed", "host_budget"):
                hr = hr2
        if hr["error"] in ("robots_disallowed", "host_budget"):
            r.update(home_status=hr["error"], home_blocked_host=hr["blocked_host"])
            # the home page is not fetched; security.txt may still be allowed on the entity's host
            r.update(self.security_txt(host))
            return r
        r.update(home_status=hr["status"] or hr["error"], home_final=hr["final_url"], home_hops=hr["hops"],
                 home_https=hr["https_final"], https_cert_invalid=hr["cert_invalid"])
        r.update(hsts(hr["headers"]) if hr["https_final"] else dict(hsts=False))
        final_host = authority(hr["final_url"]) or host
        r["home_final_host"] = final_host
        page = text(hr) if hr["status"] == 200 and is_html(hr) else ""
        r["home_html"] = bool(page)
        acc_url, acc_is_stmt = (None, False)
        if page:
            r["home_name_match"] = homepage_name_match(page, e.get("name", ""))
            acc_url, acc_is_stmt = find_accessibility_link(page, hr["final_url"])
            r["home_js_shell"] = is_shell(page)
            r.update(page_markers(page, hr["final_url"]))
        r.update(acc_link=bool(acc_url), acc_link_says_statement=acc_is_stmt, acc_url=acc_url or "")
        # security.txt on the host that actually serves the site (always https, RFC 9116 s. 3)
        r.update(self.security_txt(final_host))
        # accessibility statement or llms.txt
        acc_host = authority(acc_url) if acc_url else None
        off_host = bool(acc_url) and acc_host not in (final_host, host)
        if acc_url and (r["arm"] == "S" or off_host):
            sr = S.get(acc_url)
            if sr["error"] in ("robots_disallowed", "host_budget"):
                r["stmt_status"] = sr["error"]
            else:
                r.update(check_statement(sr))
            r["stmt_off_host"] = off_host
        if not acc_url or r["arm"] == "L" or off_host:
            r.update(self.llms(final_host, "https" if r.get("home_https") else "http"))
        return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--population", default="data/population.csv")
    ap.add_argument("--out", default="data/raw/scan.jsonl")
    ap.add_argument("--workers", type=int, default=48)
    ap.add_argument("--only", help="comma-separated entity_ids")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--user-agent", default=os.environ.get("S8_USER_AGENT"),
                    help="identify yourself, e.g. 'MyLab-research/1.0 (+https://example.org/scan)'")
    a = ap.parse_args()
    if not a.user_agent:
        raise SystemExit("set --user-agent or S8_USER_AGENT to a string that identifies you and a URL "
                         "describing your scan; EasyxLab's own runs use: " + EASYXLAB_UA)
    session = Session(a.user_agent)
    scanner = Scanner(session)
    ents = [x for x in csv.DictReader(open(a.population, encoding="utf-8")) if x["url"]]
    if a.only:
        keep = set(a.only.split(","))
        ents = [x for x in ents if x["entity_id"] in keep]
    if a.limit:
        ents = ents[: a.limit]
    done = set()
    if os.path.exists(a.out):
        for ln in open(a.out, encoding="utf-8"):
            try:
                done.add(json.loads(ln)["entity_id"])
            except Exception:
                pass
    todo = [x for x in ents if x["entity_id"] not in done]
    if done:
        print("WARNING: resuming; the per-host counters restart, so a host shared by finished and "
              "unfinished entities can exceed the per-host budget over the whole run", file=sys.stderr)
    # big entities first so that the shared-host budget goes to the entity the host belongs to
    todo.sort(key=lambda x: -(int(x["population"]) if x["population"] else 10**9))
    print(f"{len(todo)} entities to scan ({len(done)} already done); UA {a.user_agent!r}", file=sys.stderr)
    lock = threading.Lock()
    t0 = time.time()
    with open(a.out, "a", encoding="utf-8") as f, ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(scanner.scan_entity, e): e for e in todo}
        for i, fu in enumerate(as_completed(futs), 1):
            e = futs[fu]
            try:
                r = fu.result()
            except Exception as exc:  # noqa: BLE001
                r = dict(entity_id=e["entity_id"], host=authority(e["url"]), url=e["url"],
                         notes=f"scanner_exception:{type(exc).__name__}")
            r["scanned_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            with lock:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
                f.flush()
            if i % 250 == 0:
                print(f"{i}/{len(todo)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
    hosts, mx, mr = session.stats()
    print(f"done; hosts touched {hosts}; max fetches/host {mx}; max requests/host incl. hops {mr}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
