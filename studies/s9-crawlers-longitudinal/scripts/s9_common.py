"""Shared code for EasyxLab study S9 (verified crawlers over time + robots.txt trap routes).

Verification is NOT reimplemented here: it is imported, unchanged, from study S2's
`ai_bot_verify.py` (../../s2-spoofed-ai-crawlers/scripts/, MIT, EasyxLab). The file that was
actually loaded, its VERSION and its SHA-256 are written into every weekly manifest, so a result can
always be traced to the exact verifier. Search order for that file:

  1. $S9_ABV_PATH (a directory containing ai_bot_verify.py), for deployments that copy scripts;
  2. ../../s2-spoofed-ai-crawlers/scripts relative to this file (the repository layout);
  3. this directory (a vendored copy, which must be byte-identical to S2's: the hash tells).

What S9 adds on top of S2: ISO-week windows, the trap arm / phase / label of each request, what
each operator SAYS about robots.txt (quoted in PROTOCOL.md §4), client classes for undeclared
agents, and the extraction of unregistered crawler names. Standard library only (Python >= 3.10).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

S9_VERSION = "0.1.0"
HERE = Path(__file__).resolve().parent
# Our own requests to the studied sites (live checks, deploy verification) must not identify the lab:
# they use a NEUTRAL User-Agent whose marker comes from the private configuration (`check_ua`,
# `check_marker`), and requests carrying it are excluded from every count. The default below is only
# for tests. LEGACY_CHECK_MARKERS covers the design-phase requests of 2026-10-02 (PROTOCOL §13).
LEGACY_CHECK_MARKERS = ("EasyxLab-S9-check",)
DEFAULT_CHECK_UA = "Mozilla/5.0 (compatible; uptime-check/1.0)"
_CHECK = {"ua": DEFAULT_CHECK_UA, "marker": "uptime-check/1.0"}


def configure_check(ua: str | None = None, marker: str | None = None) -> None:
    if ua:
        _CHECK["ua"] = ua
        _CHECK["marker"] = marker or ua


def check_ua() -> str:
    return _CHECK["ua"]


def _load_abv():
    cands = []
    if os.environ.get("S9_ABV_PATH"):
        cands.append(Path(os.environ["S9_ABV_PATH"]))
    cands += [HERE.parents[1] / "s2-spoofed-ai-crawlers" / "scripts", HERE]
    for d in cands:
        f = d / "ai_bot_verify.py"
        if f.exists():
            spec = importlib.util.spec_from_file_location("ai_bot_verify", f)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["ai_bot_verify"] = mod     # cf_declared_bots.py imports it by this name
            spec.loader.exec_module(mod)
            return mod, f
    raise SystemExit("S9: ai_bot_verify.py (study S2) not found; set S9_ABV_PATH to its directory")


abv, ABV_FILE = _load_abv()
ABV_SHA256 = hashlib.sha256(ABV_FILE.read_bytes()).hexdigest()


def load_cf_module():
    """S2's Cloudflare GraphQL helpers (same directory as the verifier that was loaded)."""
    f = ABV_FILE.parent / "cf_declared_bots.py"
    spec = importlib.util.spec_from_file_location("cf_declared_bots", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------------------------------------
# What each operator says about robots.txt (PROTOCOL.md §4; literal text retrieved 2026-10-02).
# Keys are S2's canonical bot names (ai_bot_verify.BOTS).
#   obeys             the operator says this crawler follows robots.txt
#   may-ignore        the operator says it may not follow robots.txt (user-initiated fetchers)
#   ignores-wildcard  the operator says it ignores the `*` group (must be named explicitly)
#   unstated          no statement could be retrieved as text
#   n/a               not a crawler that could be tested (robots-only tokens, client-side tools)
# ----------------------------------------------------------------------------------------------
CLAIMS = {
    "Google-Extended": "n/a", "Applebot-Extended": "n/a", "Claude-Code(client)": "n/a",
    "GPTBot": "obeys", "OAI-SearchBot": "obeys", "ChatGPT-User": "may-ignore", "OAI-AdsBot": "unstated",
    "ClaudeBot": "obeys", "Claude-SearchBot": "obeys", "Claude-User": "obeys",
    "PerplexityBot": "obeys", "Perplexity-User": "may-ignore",
    "MistralAI-User": "obeys", "MistralAI-Index": "obeys",
    "DuckAssistBot": "obeys", "DuckDuckBot": "unstated",
    "CCBot": "obeys", "Applebot": "obeys",
    "Google-special": "ignores-wildcard", "Google-fetcher": "may-ignore", "Googlebot": "obeys",
    "Bingbot": "unstated", "YandexBot": "unstated",
    # S2 groups Amazonbot, Amzn-SearchBot and Amzn-User under one name; Amazon cannot be verified
    # anyway (lists only behind JavaScript), so it never reaches the "verified" branch.
    "Amazonbot": "obeys", "Bytespider": "unstated", "Meta-ExternalAgent": "unstated",
}

# Operators whose documentation gives a robots.txt refresh delay longer than 24 h (hours).
GRACE_HOURS_DEFAULT = 24
GRACE_HOURS_BY_OPERATOR = {"DuckDuckGo": 72, "Amazon": 720}

# Operators covered by H1 (they say their crawler, or user fetcher, obeys robots.txt).
H1_BOTS = {
    "Google": ["Googlebot"], "OpenAI": ["GPTBot", "OAI-SearchBot"],
    "Anthropic": ["ClaudeBot", "Claude-SearchBot", "Claude-User"], "Perplexity": ["PerplexityBot"],
    "Apple": ["Applebot"], "Common Crawl": ["CCBot"], "Mistral": ["MistralAI-User", "MistralAI-Index"],
    "DuckDuckGo": ["DuckAssistBot"],
}

ARMS_DISALLOWED = ("disallowed", "robots-only")
ARMS = ("allowed",) + ARMS_DISALLOWED


def claim_of(bot_name: str | None) -> str:
    return CLAIMS.get(bot_name or "", "unstated")


def grace_for(operator: str | None, override_hours: int | None = None) -> timedelta:
    if override_hours is not None:
        return timedelta(hours=override_hours)
    return timedelta(hours=max(GRACE_HOURS_DEFAULT, GRACE_HOURS_BY_OPERATOR.get(operator or "", 0)))


# ----------------------------------------------------------------------------------------------
# Time windows
# ----------------------------------------------------------------------------------------------

def parse_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def week_window(week: str) -> tuple[datetime, datetime]:
    """'2026-W41' -> [Monday 00:00 UTC, next Monday 00:00 UTC)."""
    m = re.fullmatch(r"(\d{4})-W(\d{2})", week)
    if not m:
        raise ValueError(f"bad ISO week {week!r} (expected YYYY-Www)")
    start = datetime.fromisocalendar(int(m[1]), int(m[2]), 1).replace(tzinfo=timezone.utc)
    return start, start + timedelta(days=7)


def week_of(ts: datetime) -> str:
    y, w, _ = ts.astimezone(timezone.utc).isocalendar()
    return f"{y}-W{w:02d}"


def last_complete_week(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return week_of(now - timedelta(days=7))


def weeks_between(first: str, last: str) -> list[str]:
    out, (s, _) = [], week_window(first)
    end, _ = week_window(last)
    while s <= end:
        out.append(week_of(s))
        s += timedelta(days=7)
    return out


# ----------------------------------------------------------------------------------------------
# Site configuration (private/sites.json; see scripts/sites.example.json)
# ----------------------------------------------------------------------------------------------

@dataclass
class Site:
    label: str
    domain: str = ""
    log: dict = field(default_factory=dict)
    arms: dict = field(default_factory=dict)          # exact path -> arm
    prefix: str = ""
    t_robots: datetime | None = None
    t_link: datetime | None = None
    t_end: datetime | None = None
    footer_hrefs: list = field(default_factory=list)  # hrefs expected in the home page after t_link
    cf_zone: str = ""


def site_from_dict(label: str, d: dict) -> Site:
    arms = {p: a for a, p in (d.get("arms") or {}).items()}
    for p, a in arms.items():
        if a not in ARMS:
            raise ValueError(f"{label}: unknown arm {a!r}")
        if not p.startswith("/") or not p.endswith("/"):
            raise ValueError(f"{label}: trap path must start and end with '/': {p!r}")
    prefix = d.get("prefix") or (os.path.commonprefix(list(arms)) if arms else "")
    if prefix and not prefix.endswith("/"):
        prefix = prefix[: prefix.rfind("/") + 1]
    return Site(label=label, domain=d.get("domain", ""), log=d.get("log") or {}, arms=arms, prefix=prefix,
                t_robots=parse_utc(d.get("t_robots")), t_link=parse_utc(d.get("t_link")),
                t_end=parse_utc(d.get("t_end")),
                footer_hrefs=[p for p, a in arms.items() if a in ("allowed", "disallowed")],
                cf_zone=d.get("cf_zone") or d.get("domain", ""))


def load_config(path: Path) -> dict:
    cfg = json.loads(Path(path).read_text())
    cfg["_sites"] = {k: site_from_dict(k, v) for k, v in cfg["sites"].items()}
    configure_check(cfg.get("check_ua"), cfg.get("check_marker"))
    return cfg


# ----------------------------------------------------------------------------------------------
# Trap classification (pure functions; tested in tests/test_s9.py)
# ----------------------------------------------------------------------------------------------

def trap_arm(site: Site, path: str) -> str | None:
    """Arm of a request path, or None if it is not under the site's trap prefix.
    Matching follows robots.txt: case-sensitive prefix semantics, query string ignored. Only the
    exact arm path counts as that arm; anything else under the prefix (e.g. the disallowed path
    WITHOUT its trailing slash, which the Disallow line does not cover) is 'other-under-prefix'."""
    if not site.prefix:
        return None
    p = (path or "").split("?", 1)[0].split("#", 1)[0]
    if "://" in p:                                   # absolute-form request line
        p = re.sub(r"^[a-z][a-z0-9+.-]*://[^/]*", "", p, flags=re.I) or "/"
    if p in site.arms:
        return site.arms[p]
    if p.startswith(site.prefix) or p == site.prefix.rstrip("/"):
        return "other-under-prefix"
    return None


def trap_phase(site: Site, arm: str, ts: datetime, operator: str | None = None,
               grace_override_hours: int | None = None) -> str:
    if site.t_end and ts >= site.t_end:
        return "post"
    if arm == "allowed":
        return "active" if site.t_link and ts >= site.t_link else "pre"
    if arm in ARMS_DISALLOWED:
        if not site.t_robots or ts < site.t_robots:
            return "pre"
        if ts < site.t_robots + grace_for(operator, grace_override_hours):
            return "grace"
        return "active"
    return "n/a"


def trap_label(arm: str | None, phase: str, bot, verdict: str | None, ua: str = "") -> str | None:
    """One label per request under the trap prefix (PROTOCOL.md §5)."""
    if arm is None:
        return None
    if arm == "other-under-prefix":
        return "other-under-prefix"
    if phase in ("pre", "post", "n/a"):
        return phase
    if arm == "allowed":
        return "control"
    if phase == "grace":
        return "in-grace"
    if bot is None:
        return "undeclared:" + ua_class(ua)
    if verdict != "verified":
        return "unverified-claim"
    return {"obeys": "violation", "may-ignore": "permitted-user-fetch",
            "ignores-wildcard": "permitted-ignores-wildcard",
            "unstated": "fetch-no-stated-policy"}.get(claim_of(bot.name), "unverified-claim")


_LIB = re.compile(r"curl|wget|python|go-http|java/|okhttp|libwww|httpclient|axios|node-fetch|undici|"
                  r"scrapy|aiohttp|httpx|ruby|php|guzzle|postman|insomnia|powershell", re.I)
_BOTISH = re.compile(r"bot|crawl|spider|fetch|scan|slurp|archiv|preview|monitor|check", re.I)


def ua_class(ua: str) -> str:
    u = (ua or "").strip()
    if not u or u == "-":
        return "empty"
    if _LIB.search(u):
        return "http-library"
    if _BOTISH.search(u):
        return "other-bot"
    if u.lower().startswith("mozilla/"):
        return "browser-like"
    return "other"


_TOKEN = re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9._-]{1,40}?(?:bot|crawler|spider|fetcher))(?=[/;\s),]|$)",
                    re.I)


def unregistered_tokens(ua: str) -> set[str]:
    """Crawler-like names in a User-Agent that S2's registry does not know (lower-case)."""
    if not ua or abv.match_bot(ua) is not None:
        return set()
    out = set()
    for t in _TOKEN.findall(ua):
        t = t.lower().strip("._-")
        if t not in ("bot", "robot", "crawler", "spider", "fetcher") and len(t) >= 4:
            out.add(t)
    return out


def is_own_check(ua: str) -> bool:
    u = (ua or "").lower()
    return _CHECK["marker"].lower() in u or any(m.lower() in u for m in LEGACY_CHECK_MARKERS)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
