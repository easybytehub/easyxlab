#!/usr/bin/env python3
"""ai-bot-verify — is the "GPTBot" in your access.log really OpenAI?

Reads web-server access logs (nginx/Apache "combined" format, or any format whose first
field is the client IP and that ends with "referer" "user-agent"), finds every request whose
User-Agent claims to be a known AI or search crawler, and checks the source IP against the
operator's OWN published verification method:

  * published IP-range JSON files (OpenAI, Anthropic, Perplexity, Google, Bing, Apple,
    Common Crawl, DuckDuckGo, Mistral), and/or
  * forward-confirmed reverse DNS (FCrDNS) against the hostname suffix the operator
    documents (Google, Bing, Apple, Common Crawl, Yandex).

Every request gets exactly one verdict:

  verified      the IP is inside the operator's published ranges, or passes FCrDNS
  spoofed       the operator publishes a method and the IP fails it; also any request whose
                UA is a robots.txt-only token the operator says is never sent as a UA
                (Google-Extended, Applebot-Extended)
  unverifiable  the operator publishes no verification method (e.g. Bytespider)
  indeterminate a method exists but could not be applied (range file unreachable, DNS
                timeout)

Output is AGGREGATED ONLY (CSV + JSON): per bot, per verdict, per ASN / network type, per
normalised path category, per hour. No individual IP address is ever written: the tool
checks its own output for IP-shaped strings and refuses to write if it finds one.

Standard library only (Python >= 3.10). Network access is needed to download the range
files (cached for 24 h), for reverse DNS, and — only with --asn — for Team Cymru's public
IP-to-ASN whois service (whois.cymru.com:43), which receives the list of NON-verified IPs.

Usage:
    ai-bot-verify access.log [more.log ...] [--site NAME] [--asn] [--out DIR]
    ai-bot-verify --site example.com --asn --out results/ /var/log/nginx/access.log*

License: Apache-2.0. Part of EasyxLab study S2 ("Spoofed AI crawlers").
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import gzip
import ipaddress
import json
import os
import re
import socket
import statistics
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.1.0"

# --------------------------------------------------------------------------------------
# Registry. Every entry cites the operator's own documentation (checked 2026-10-02).
# --------------------------------------------------------------------------------------

DOCS = {
    "OpenAI": "https://platform.openai.com/docs/bots",
    "Anthropic": "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler",
    "Perplexity": "https://docs.perplexity.ai/guides/bots",
    "Google": "https://developers.google.com/search/docs/crawling-indexing/verifying-googlebot",
    "Microsoft": "https://www.bing.com/toolbox/bingbot.json",
    "Apple": "https://support.apple.com/en-us/119829",
    "Common Crawl": "https://commoncrawl.org/ccbot",
    "DuckDuckGo": "https://duckduckgo.com/duckduckgo-help-pages/results/duckduckbot",
    "Mistral": "https://docs.mistral.ai/robots/",
    "Yandex": "https://yandex.com/support/webmaster/robot-workings/check-yandex-robots.html",
    "Amazon": "https://developer.amazon.com/amazonbot",
    "ByteDance": "",
    "Meta": "https://developers.facebook.com/docs/sharing/webmasters/web-crawlers/",
}

RANGE_URLS = {
    "openai-gptbot": "https://openai.com/gptbot.json",
    "openai-searchbot": "https://openai.com/searchbot.json",
    "openai-chatgpt-user": "https://openai.com/chatgpt-user.json",
    "openai-adsbot": "https://openai.com/adsbot.json",
    "anthropic": "https://claude.com/crawling/bots.json",
    "perplexity-bot": "https://www.perplexity.ai/perplexitybot.json",
    "perplexity-user": "https://www.perplexity.ai/perplexity-user.json",
    "google-common": "https://developers.google.com/static/crawling/ipranges/common-crawlers.json",
    "google-special": "https://developers.google.com/static/crawling/ipranges/special-crawlers.json",
    "google-user-fetchers": "https://developers.google.com/static/crawling/ipranges/user-triggered-fetchers.json",
    "google-user-fetchers-google": "https://developers.google.com/static/crawling/ipranges/user-triggered-fetchers-google.json",
    "google-user-agents": "https://developers.google.com/static/crawling/ipranges/user-triggered-agents.json",
    "bing": "https://www.bing.com/toolbox/bingbot.json",
    "apple": "https://search.developer.apple.com/applebot.json",
    "commoncrawl": "https://index.commoncrawl.org/ccbot.json",
    "duckduckbot": "https://duckduckgo.com/duckduckbot.json",
    "duckassistbot": "https://duckduckgo.com/duckassistbot.json",
    "mistral-user": "https://mistral.ai/mistralai-user-ips.json",
    "mistral-index": "https://mistral.ai/mistralai-index-ips.json",
}

GOOGLE_ALL = ("google-common", "google-special", "google-user-fetchers",
              "google-user-fetchers-google", "google-user-agents")


@dataclass(frozen=True)
class Bot:
    name: str          # canonical name used in reports
    pattern: str       # regex searched (case-insensitive) in the User-Agent
    operator: str
    purpose: str       # training | search-index | user-fetch | search-engine | other
    ranges: tuple = ()           # keys of RANGE_URLS
    rdns: tuple = ()             # accepted PTR suffixes for FCrDNS
    never_a_ua: bool = False     # robots.txt-only token: any request carrying it is spoofed


# ORDER MATTERS: first match wins, so the more specific tokens come first.
BOTS: list[Bot] = [
    # robots.txt-only tokens. Google: "Google-Extended doesn't have a separate HTTP request
    # user agent string." Apple: "Applebot-Extended does not crawl webpages."
    Bot("Google-Extended", r"google-extended", "Google", "training", never_a_ua=True),
    Bot("Applebot-Extended", r"applebot-extended", "Apple", "training", never_a_ua=True),
    # OpenAI
    Bot("GPTBot", r"gptbot", "OpenAI", "training", ("openai-gptbot",)),
    Bot("OAI-SearchBot", r"oai-searchbot", "OpenAI", "search-index", ("openai-searchbot",)),
    Bot("ChatGPT-User", r"chatgpt-user", "OpenAI", "user-fetch", ("openai-chatgpt-user",)),
    Bot("OAI-AdsBot", r"oai-adsbot", "OpenAI", "other", ("openai-adsbot",)),
    # Client-side agents send the operator's token from the END USER's machine (e.g. Claude
    # Code's WebFetch: "Claude-User (claude-code/x.y; ...)"). They can never match an operator
    # list, so they are "unverifiable", not "spoofed".
    Bot("Claude-Code(client)", r"claude-code", "Anthropic", "client-side"),
    # Anthropic publishes ONE list for all its bots.
    Bot("Claude-SearchBot", r"claude-searchbot", "Anthropic", "search-index", ("anthropic",)),
    Bot("Claude-User", r"claude-user", "Anthropic", "user-fetch", ("anthropic",)),
    Bot("ClaudeBot", r"claudebot|claude-web|anthropic-ai", "Anthropic", "training", ("anthropic",)),
    # Perplexity
    Bot("Perplexity-User", r"perplexity-user", "Perplexity", "user-fetch", ("perplexity-user",)),
    Bot("PerplexityBot", r"perplexitybot", "Perplexity", "search-index", ("perplexity-bot",)),
    # Mistral
    Bot("MistralAI-User", r"mistralai-user", "Mistral", "user-fetch", ("mistral-user",)),
    Bot("MistralAI-Index", r"mistralai-index", "Mistral", "search-index", ("mistral-index",)),
    # DuckDuckGo
    Bot("DuckAssistBot", r"duckassistbot", "DuckDuckGo", "user-fetch", ("duckassistbot",)),
    Bot("DuckDuckBot", r"duckduckbot", "DuckDuckGo", "search-engine", ("duckduckbot",)),
    # Common Crawl (training corpus for most LLMs)
    Bot("CCBot", r"ccbot", "Common Crawl", "training", ("commoncrawl",), (".commoncrawl.org",)),
    # Apple
    Bot("Applebot", r"applebot", "Apple", "search-engine", ("apple",), (".applebot.apple.com",)),
    # Google (the special crawlers are matched before Googlebot)
    Bot("Google-special", r"adsbot-google|mediapartners-google|apis-google|google-safety",
        "Google", "other", GOOGLE_ALL, (".google.com", ".googlebot.com")),
    Bot("Google-fetcher", r"feedfetcher-google|google-site-verification|google-read-aloud|"
        r"googleproducer|google-pagerenderer|google-agent", "Google", "user-fetch", GOOGLE_ALL,
        (".google.com", ".googlebot.com")),
    Bot("Googlebot", r"googlebot|google-inspectiontool|googleother|storebot-google|"
        r"google-cloudvertexbot", "Google", "search-engine", GOOGLE_ALL,
        (".googlebot.com", ".google.com")),
    # Microsoft
    Bot("Bingbot", r"bingbot|bingpreview|msnbot|adidxbot", "Microsoft", "search-engine",
        ("bing",), (".search.msn.com",)),
    # Yandex: reverse DNS only.
    Bot("YandexBot", r"yandex(?:bot|images|mobilebot|accessibilitybot|renderresourcesbot|"
        r"additional)", "Yandex", "search-engine", (), (".yandex.ru", ".yandex.net", ".yandex.com")),
    # Published lists that are not machine-readable over plain HTTP (JavaScript page):
    # kept as their own category, never as "spoofed".
    Bot("Amazonbot", r"amazonbot|amzn-searchbot|amzn-user", "Amazon", "search-index"),
    # No published verification method -> "unverifiable".
    Bot("Bytespider", r"bytespider", "ByteDance", "training"),
    Bot("Meta-ExternalAgent", r"meta-externalagent|meta-externalfetcher|facebookbot",
        "Meta", "training"),
]
# Soft signal only (NOT verification): does a non-verified request come from an AS whose
# registered name is the operator's own? Shared clouds (AWS, GCP, Azure) are rentable by
# anyone, so the Amazon match is weak by construction.
OPERATOR_AS_NAME = {"Meta": r"facebook|meta platforms", "ByteDance": r"bytedance|byteplus",
                    "Amazon": r"amazon", "Anthropic": r"anthropic", "OpenAI": r"openai|microsoft",
                    "Google": r"^google - ", "Microsoft": r"microsoft"}

# Operators whose method exists but this tool cannot apply automatically.
NOT_MACHINE_READABLE = {"Amazon"}

_COMPILED = [(b, re.compile(r"(?<![a-z0-9])(?:%s)" % b.pattern, re.I)) for b in BOTS]


def match_bot(ua: str) -> Bot | None:
    for bot, rx in _COMPILED:
        if rx.search(ua or ""):
            return bot
    return None


# --------------------------------------------------------------------------------------
# Log parsing
# --------------------------------------------------------------------------------------

# IP ... [time] "METHOD PATH PROTO" STATUS BYTES "referer" "user-agent" (anything after)
LINE_RX = re.compile(
    r'^(?P<ip>[0-9a-fA-F:.]+)\s+\S+\s+(?:\S+\s+)?\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>[A-Z]+|-)\s?(?P<path>\S*)[^"]*"\s+(?P<status>\d{3})\s+(?P<bytes>\S+)'
    r'(?:\s+"(?P<ref>(?:[^"\\]|\\.)*)"\s+"(?P<ua>(?:[^"\\]|\\.)*)")?(?P<rest>.*)$'
)
TIME_FMT = "%d/%b/%Y:%H:%M:%S %z"


@dataclass
class Request:
    ip: str
    ts: datetime
    method: str
    path: str
    status: int
    ua: str
    via_cdn: bool | None   # True/False when the log has a cf_ray field, else None


def parse_line(line: str) -> Request | None:
    m = LINE_RX.match(line.strip())
    if not m:
        return None
    try:
        ipaddress.ip_address(m["ip"])
        ts = datetime.strptime(m["time"], TIME_FMT)
    except ValueError:
        return None
    rest = m["rest"] or ""
    via = None
    cm = re.search(r"cf_ray=(\S+)", rest)
    if cm:
        via = cm.group(1) not in ("-", "")
    return Request(m["ip"], ts, m["method"], m["path"] or "", int(m["status"]),
                   (m["ua"] or "").replace('\\"', '"'), via)


def read_lines(paths: list[str]):
    for p in paths:
        opener = gzip.open if p.endswith(".gz") else open
        with opener(p, "rt", errors="replace") as fh:
            yield from fh


# --------------------------------------------------------------------------------------
# Path normalisation and classification (what does the client ask for?)
# --------------------------------------------------------------------------------------

PROBE_RX = re.compile(
    r"(?:^|/)(?:\.env|\.git|\.svn|\.hg|\.aws|\.ssh|\.docker|\.vscode|\.claude|\.htpasswd|"
    r"\.htaccess|\.ds_store|wp-|wordpress|xmlrpc\.php|phpmyadmin|pma|adminer|"
    r"admin(?:\.php|istrator)?(?:/|$)|login\.php|config(?:\.|/|uration)|settings\.(?:py|json|php)|"
    r"secrets?(?:\.|/)|credentials|private[-_]?key|id_rsa|key\.(?:json|pem)|.*\.pem$|"
    r"firebase|api/(?:env|config|v\d+/(?:settings|config))|env\.js|runtime-config|"
    r"application\.(?:properties|ya?ml)|actuator|server-status|server-info|telescope|"
    r"_profiler|debug|swagger|openapi|graphql|\.well-known/(?!security\.txt|llms)|"
    r"cgi-bin|shell|backup|dump|\.sql|\.bak|\.old|vendor/phpunit|boaform|hnap1|"
    r"autodiscover|owa/|ecp/|remote/login|sftp-config|docker-compose|package\.json|"
    r"composer\.(?:json|lock)|web\.config|info\.php|phpinfo|test\.php|ajax|jwks|"
    r"service[-_]?account|serviceaccountkey|terraform|\.tfstate|serverless\.ya?ml|proc/self|"
    r"@fs/|__vite|userfiles|app-config|index\.php|\.npmrc|\.pypirc|kube|\.kube)",
    re.I,
)
ASSET_RX = re.compile(r"\.(?:css|js|mjs|map|png|jpe?g|gif|webp|avif|svg|ico|woff2?|ttf|"
                      r"otf|mp4|webm|pdf)$|^/_astro/", re.I)
IP_IN_TEXT = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])|"
                        r"(?<![0-9a-f:])(?:[0-9a-f]{1,4}:){2,7}[0-9a-f]{0,4}(?![0-9a-f:])", re.I)


def normalise_path(path: str) -> str:
    p = path.split("?", 1)[0].split("#", 1)[0] or "/"
    if not p.startswith("/"):
        p = "/" + re.sub(r"^[a-z]+://[^/]*", "", p, flags=re.I) if "://" in p else "/" + p
    p = IP_IN_TEXT.sub("{ip}", p)
    p = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "{uuid}", p, flags=re.I)
    p = re.sub(r"(?<=/)[0-9a-f]{16,}(?=/|$|\.)", "{hex}", p, flags=re.I)
    p = re.sub(r"(?<=/)\d{4,}(?=/|$|\.)", "{n}", p)
    p = re.sub(r"/{2,}", "/", p)
    return p[:120]


def path_category(path: str) -> str:
    p = normalise_path(path).lower()
    if p == "/robots.txt":
        return "robots.txt"
    if p in ("/llms.txt", "/llms-full.txt") or p.endswith("/llms.txt"):
        return "llms.txt"
    if "sitemap" in p and p.endswith(".xml"):
        return "sitemap"
    if PROBE_RX.search(p):
        return "vuln-probe"
    if p in ("/rss.xml", "/feed", "/feed/", "/atom.xml", "/rss/"):
        return "feed"
    if ASSET_RX.search(p):
        return "asset"
    if p == "/":
        return "home"
    return "page"


# --------------------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------------------

class RangeStore:
    """Downloads and caches the published range files. A file that cannot be obtained is
    recorded as missing, so its bots end up 'indeterminate' instead of 'spoofed'."""

    def __init__(self, cache_dir: Path, offline_dir: Path | None = None, ttl: int = 86400):
        self.cache_dir = cache_dir
        self.offline_dir = offline_dir
        self.ttl = ttl
        self.nets: dict[str, list] = {}
        self.meta: dict[str, dict] = {}
        self.warnings: list[str] = []

    @staticmethod
    def parse(data: dict) -> list:
        nets = []
        for p in data.get("prefixes", []):
            pref = p.get("ipv4Prefix") or p.get("ipv6Prefix")
            if pref:
                try:
                    nets.append(ipaddress.ip_network(pref, strict=False))
                except ValueError:
                    pass
        return nets

    def load(self, key: str) -> list | None:
        if key in self.nets:
            return self.nets[key]
        url = RANGE_URLS[key]
        data = None
        if self.offline_dir is not None:
            f = self.offline_dir / f"{key}.json"
            if f.exists():
                data = json.loads(f.read_text())
        else:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache = self.cache_dir / f"{key}.json"
            if cache.exists() and time.time() - cache.stat().st_mtime < self.ttl:
                try:
                    data = json.loads(cache.read_text())
                except json.JSONDecodeError:
                    data = None
            if data is None:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": f"ai-bot-verify/{VERSION}"})
                    with urllib.request.urlopen(req, timeout=20) as r:
                        data = json.loads(r.read().decode("utf-8"))
                    cache.write_text(json.dumps(data))
                except Exception as e:  # noqa: BLE001
                    if cache.exists():
                        data = json.loads(cache.read_text())
                        self.warnings.append(f"{key}: using stale cache ({type(e).__name__})")
                    else:
                        self.warnings.append(f"{key}: range file unavailable ({type(e).__name__})")
        if data is None:
            self.nets[key] = None
            return None
        nets = self.parse(data)
        self.nets[key] = nets
        self.meta[key] = {"url": url, "creationTime": data.get("creationTime"), "prefixes": len(nets)}
        return nets


def in_nets(ip: str, nets) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(a.version == n.version and a in n for n in nets)


class Resolver:
    """FCrDNS with three outcomes: True (confirmed), False (definitely not), None (lookup
    failed transiently). Injectable for tests."""

    def __init__(self, reverse=None, forward=None):
        self.reverse = reverse or self._reverse
        self.forward = forward or self._forward
        self.cache: dict[tuple, bool | None] = {}

    @staticmethod
    def _reverse(ip: str):
        try:
            return socket.gethostbyaddr(ip)[0]
        except socket.herror as e:
            # errno 1 HOST_NOT_FOUND = no PTR (definitive); 2 TRY_AGAIN = transient
            return None if getattr(e, "errno", 1) == 2 else ""
        except OSError:
            return None

    @staticmethod
    def _forward(name: str):
        try:
            infos = socket.getaddrinfo(name, None)
            return {i[4][0] for i in infos}
        except socket.gaierror as e:
            return None if e.errno in (socket.EAI_AGAIN,) else set()
        except OSError:
            return None

    def fcrdns(self, ip: str, suffixes: tuple) -> bool | None:
        key = (ip, suffixes)
        if key in self.cache:
            return self.cache[key]
        name = self.reverse(ip)
        if name is None:
            res = None
        elif not name or not name.lower().rstrip(".").endswith(suffixes):
            res = False
        else:
            ips = self.forward(name)
            if ips is None:
                res = None
            else:
                norm = {str(ipaddress.ip_address(x.split("%")[0])) for x in ips if x}
                res = str(ipaddress.ip_address(ip)) in norm
        self.cache[key] = res
        return res


def verdict_for(bot: Bot, ip: str, ranges: RangeStore, resolver: Resolver | None) -> str:
    if bot.never_a_ua:
        return "spoofed"
    if not bot.ranges and not bot.rdns:
        return "indeterminate" if bot.operator in NOT_MACHINE_READABLE else "unverifiable"
    any_list = False
    for key in bot.ranges:
        nets = ranges.load(key)
        if nets is None:
            continue
        any_list = True
        if in_nets(ip, nets):
            return "verified"
    if bot.rdns:
        if resolver is None:
            return "indeterminate" if not any_list else "spoofed"
        r = resolver.fcrdns(ip, bot.rdns)
        if r is True:
            return "verified"
        if r is None:
            return "indeterminate"
        return "spoofed"
    return "spoofed" if any_list else "indeterminate"


# --------------------------------------------------------------------------------------
# ASN lookup (Team Cymru bulk whois) and network-type heuristic
# --------------------------------------------------------------------------------------

def cymru_asn(ips: list[str], timeout: int = 60) -> dict[str, dict]:
    """IP -> {asn, cc, as_name}. One TCP connection for the whole batch."""
    out: dict[str, dict] = {}
    if not ips:
        return out
    for i in range(0, len(ips), 5000):
        chunk = ips[i:i + 5000]
        payload = "begin\nverbose\n" + "\n".join(chunk) + "\nend\n"
        try:
            with socket.create_connection(("whois.cymru.com", 43), timeout=timeout) as s:
                s.sendall(payload.encode())
                buf = b""
                while True:
                    d = s.recv(65536)
                    if not d:
                        break
                    buf += d
        except OSError:
            continue
        for line in buf.decode(errors="replace").splitlines():
            parts = [x.strip() for x in line.split("|")]
            if len(parts) >= 7 and parts[0].isdigit():
                out[parts[1]] = {"asn": int(parts[0]), "cc": parts[3], "as_name": parts[6]}
            elif len(parts) >= 7 and parts[0] == "NA":
                out[parts[1]] = {"asn": None, "cc": parts[3], "as_name": "unannounced"}
    return out


NET_TYPES = [
    ("vpn/proxy", r"\bvpn\b|m247|datacamp|packethub|tefincom|nordvpn|expressvpn|surfshark|"
                  r"private internet access|proton|mullvad|cdn77|zenlayer|ipxo|"
                  r"tzulo|clouvider|hostroyale|proxy"),
    ("cloud/hosting", r"amazon|aws|google|microsoft|azure|digitalocean|ovh|hetzner|linode|"
                      r"akamai|vultr|choopa|contabo|leaseweb|alibaba|aliyun|tencent|huawei|"
                      r"oracle|ionos|1&1|scaleway|online s\.a\.s|hostinger|hosting|host|"
                      r"server|cloud|data ?cent|datacenter|colo|ihor|selectel|timeweb|"
                      r"cherry|kamatera|netcup|psychz|quadranet|serverion|hydra|stark|"
                      r"pfcloud|aeza|ucloud|chinanet-idc|idc|vps|dedicated|limestone|"
                      r"cogent|hurricane|internet utilities|bytedance|byteplus|facebook|"
                      r"meta platforms|apple|cloudflare|fastly|anthropic|openai|perplexity"),
    ("mobile", r"mobile|wireless|cellular|\blte\b|\b[345]g\b|t-mobile|vodafone|"
               r"telcel|claro|tim celular|jio"),
    ("isp/residential", r"telecom|telekom|telefonica|comcast|charter|verizon|at&t|att-|"
                        r"cox|spectrum|broadband|cable|fiber|fibre|dsl|orange|movistar|"
                        r"bt-|british telecom|kpn|swisscom|chinanet|china unicom|"
                        r"china mobile|vietnam|viettel|vnpt|airtel|bharti|rostelecom|"
                        r"\bisp\b|internet service|communications|net ltda|telecomunica"),
]
_NET_RX = [(t, re.compile(rx, re.I)) for t, rx in NET_TYPES]


def net_type(as_name: str) -> str:
    for t, rx in _NET_RX:
        if rx.search(as_name or ""):
            return t
    return "unknown"


# --------------------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------------------

VERDICTS = ("verified", "spoofed", "unverifiable", "indeterminate")


@dataclass
class Agg:
    requests: Counter = field(default_factory=Counter)        # (bot, verdict)
    ips: dict = field(default_factory=lambda: defaultdict(set))  # (bot, verdict) -> ips (memory only)
    paths: Counter = field(default_factory=Counter)           # (bot, verdict, category, norm path)
    cats: Counter = field(default_factory=Counter)            # (bot, verdict, category)
    hours: Counter = field(default_factory=Counter)           # (operator, verdict, hour)
    days: Counter = field(default_factory=Counter)            # (date, bot, verdict)
    status: Counter = field(default_factory=Counter)          # (bot, verdict, status class)
    uas: Counter = field(default_factory=Counter)             # (bot, verdict, ua)
    via: Counter = field(default_factory=Counter)             # (verdict, via_cdn)
    ip_first: dict = field(default_factory=dict)              # (bot, verdict, ip) -> first category
    ip_cats: dict = field(default_factory=lambda: defaultdict(set))
    ip_reqs: Counter = field(default_factory=Counter)         # (bot, verdict, ip)
    ip_bots: dict = field(default_factory=lambda: defaultdict(set))  # ip -> claimed bots (non-verified)
    ip_req_total: Counter = field(default_factory=Counter)    # ip -> requests (non-verified)
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    lines: int = 0
    parsed: int = 0
    declared: int = 0


def analyse(lines, ranges: RangeStore, resolver: Resolver | None, exclude_ips=frozenset(),
            since=None, until=None) -> Agg:
    agg = Agg()
    pending: list[tuple[Request, Bot]] = []
    for line in lines:
        agg.lines += 1
        r = parse_line(line)
        if r is None:
            continue
        agg.parsed += 1
        if since and r.ts < since or until and r.ts >= until:
            continue
        if r.ip in exclude_ips:
            continue
        agg.first_ts = r.ts if agg.first_ts is None or r.ts < agg.first_ts else agg.first_ts
        agg.last_ts = r.ts if agg.last_ts is None or r.ts > agg.last_ts else agg.last_ts
        bot = match_bot(r.ua)
        if bot is None:
            continue
        agg.declared += 1
        pending.append((r, bot))

    # Resolve FCrDNS in parallel for the (ip, bot) pairs that need it.
    if resolver is not None:
        need = set()
        for r, bot in pending:
            if bot.rdns and not bot.never_a_ua:
                inside = any(ranges.load(k) and in_nets(r.ip, ranges.load(k)) for k in bot.ranges)
                if not inside:
                    need.add((r.ip, bot.rdns))
        with cf.ThreadPoolExecutor(max_workers=32) as ex:
            list(ex.map(lambda t: resolver.fcrdns(*t), need))

    for r, bot in sorted(pending, key=lambda t: t[0].ts):
        v = verdict_for(bot, r.ip, ranges, resolver)
        k = (bot.name, v)
        cat = path_category(r.path)
        agg.requests[k] += 1
        agg.ips[k].add(r.ip)
        agg.cats[(bot.name, v, cat)] += 1
        agg.paths[(bot.name, v, cat, normalise_path(r.path))] += 1
        agg.hours[(bot.operator, v, r.ts.astimezone(timezone.utc).hour)] += 1
        agg.days[(r.ts.astimezone(timezone.utc).date().isoformat(), bot.name, v)] += 1
        agg.status[(bot.name, v, f"{r.status // 100}xx" if r.status < 444 or r.status > 444 else "444")] += 1
        agg.uas[(bot.name, v, r.ua[:200])] += 1
        agg.via[(v, r.via_cdn)] += 1
        ik = (bot.name, v, r.ip)
        agg.ip_first.setdefault(ik, cat)
        agg.ip_cats[ik].add(cat)
        agg.ip_reqs[ik] += 1
        if v != "verified":
            agg.ip_bots[r.ip].add(bot.name)
            agg.ip_req_total[r.ip] += 1
    return agg


def bot_by_name(name: str) -> Bot:
    return next(b for b in BOTS if b.name == name)


WITHHELD_AS_NAME = "a small AS registered to an individual"


def build_report(agg: Agg, site: str, asn_map: dict | None, ranges: RangeStore,
                 withhold_asns=frozenset()) -> dict:
    """Everything that leaves this function is aggregated. IPs are only used as keys
    for counting and never copied into the result."""
    rows_bot = []
    for (name, v), n in sorted(agg.requests.items(), key=lambda kv: (-kv[1], kv[0])):
        b = bot_by_name(name)
        per_ip = [agg.ip_reqs[(name, v, ip)] for ip in agg.ips[(name, v)]]
        ipset = agg.ips[(name, v)]
        rows_bot.append({
            "site": site, "bot": name, "operator": b.operator, "purpose": b.purpose,
            "method": ("never-a-UA" if b.never_a_ua else
                       "+".join(x for x in (("ranges" if b.ranges else ""), ("fcrdns" if b.rdns else "")) if x)
                       or ("list-not-machine-readable" if b.operator in NOT_MACHINE_READABLE else "none")),
            "verdict": v, "requests": n, "unique_ips": len(ipset),
            "median_req_per_ip": statistics.median(per_ip) if per_ip else 0,
            "ips_fetching_robots": sum(1 for ip in ipset if "robots.txt" in agg.ip_cats[(name, v, ip)]),
            "ips_robots_first": sum(1 for ip in ipset if agg.ip_first[(name, v, ip)] == "robots.txt"),
            "ips_with_vuln_probe": sum(1 for ip in ipset if "vuln-probe" in agg.ip_cats[(name, v, ip)]),
            "doc_url": DOCS.get(b.operator, ""),
        })
    totals = Counter()
    for (name, v), n in agg.requests.items():
        totals[v] += n
    rows_cat = [{"site": site, "bot": b, "verdict": v, "category": c, "requests": n}
                for (b, v, c), n in sorted(agg.cats.items())]
    # top normalised paths per (verdict, category); content paths are the site's own pages
    # Only scanner/credential-probe paths are published verbatim. A site's own paths would
    # identify the site, so every other request is grouped as "(site page)".
    top_paths = Counter()
    for (b, v, c, p), n in agg.paths.items():
        top_paths[(v, c, p if c == "vuln-probe" else "(site page)")] += n
    rows_paths = [{"site": site, "verdict": v, "category": c, "path": p, "requests": n}
                  for (v, c, p), n in top_paths.most_common() if n >= 2][:400]
    rows_hours = [{"site": site, "operator": o, "verdict": v, "hour_utc": h, "requests": n}
                  for (o, v, h), n in sorted(agg.hours.items())]
    rows_days = [{"site": site, "date": d, "bot": b, "verdict": v, "requests": n}
                 for (d, b, v), n in sorted(agg.days.items())]
    rows_status = [{"site": site, "bot": b, "verdict": v, "status": s, "requests": n}
                   for (b, v, s), n in sorted(agg.status.items())]
    # UA strings: only those seen >= 3 times, to avoid publishing one-off fingerprints
    rows_ua = [{"site": site, "bot": b, "verdict": v, "user_agent": ua, "requests": n}
               for (b, v, ua), n in agg.uas.most_common() if n >= 3][:200]
    rows_asn = []
    if asn_map is not None:
        by_asn: dict = defaultdict(lambda: {"requests": 0, "ips": 0, "bots": Counter(), "verdicts": Counter()})
        for (name, v), ipset in agg.ips.items():
            if v == "verified":
                continue
            for ip in ipset:
                info = asn_map.get(ip, {"asn": None, "cc": "", "as_name": "lookup-failed"})
                key = (info["asn"], info["as_name"], info["cc"])
                n = agg.ip_reqs[(name, v, ip)]
                by_asn[key]["requests"] += n
                by_asn[key]["bots"][name] += n
                by_asn[key]["verdicts"][v] += n
        ip_count: Counter = Counter()
        for ip in agg.ip_bots:
            info = asn_map.get(ip, {"asn": None, "cc": "", "as_name": "lookup-failed"})
            ip_count[(info["asn"], info["as_name"], info["cc"])] += 1
        for key, d in sorted(by_asn.items(), key=lambda kv: -kv[1]["requests"]):
            asn, name, cc = key
            if asn is not None and str(asn) in withhold_asns:
                # holder is a natural person: AS number, name and country are not published
                asn, name, cc = "withheld", WITHHELD_AS_NAME, ""
            rows_asn.append({
                "site": site, "asn": asn, "as_name": name, "country": cc, "net_type": net_type(name),
                "requests": d["requests"], "unique_ips": ip_count[key],
                "spoofed_requests": d["verdicts"]["spoofed"],
                "unverifiable_requests": d["verdicts"]["unverifiable"],
                "indeterminate_requests": d["verdicts"]["indeterminate"],
                "claimed_bots": ";".join(f"{b}:{n}" for b, n in d["bots"].most_common()),
            })
    # Behaviour of each source, computed per IP in memory and published as counts only.
    ops_by_ip: dict = defaultdict(set)
    for (name, v), ipset in agg.ips.items():
        for ip in ipset:
            ops_by_ip[ip].add(bot_by_name(name).operator)
    beh: dict = defaultdict(Counter)
    for (name, v), ipset in agg.ips.items():
        for ip in ipset:
            cats = agg.ip_cats[(name, v, ip)]
            n = agg.ip_reqs[(name, v, ip)]
            cls = ("probe" if "vuln-probe" in cats else
                   "content-only" if cats <= {"page", "home", "asset", "robots.txt", "sitemap", "llms.txt", "feed"}
                   else "other")
            multi = len(ops_by_ip[ip]) >= 2
            beh[(name, v)][f"ips_{cls}"] += 1
            beh[(name, v)][f"req_{cls}"] += n
            if multi:
                beh[(name, v)]["ips_multi_operator"] += 1
                beh[(name, v)]["req_multi_operator"] += n
    keys = ["ips_probe", "req_probe", "ips_content-only", "req_content-only", "ips_other", "req_other",
            "ips_multi_operator", "req_multi_operator"]
    rows_beh = [{"site": site, "bot": b, "verdict": v, **{k: beh[(b, v)][k] for k in keys}}
                for (b, v) in sorted(beh, key=lambda t: -agg.requests[t])]
    rows_opas = []
    if asn_map is not None:
        cnt: dict = defaultdict(Counter)
        for (name, v), ipset in agg.ips.items():
            if v == "verified":
                continue
            op = bot_by_name(name).operator
            rx = OPERATOR_AS_NAME.get(op)
            for ip in ipset:
                asn_name = asn_map.get(ip, {}).get("as_name", "")
                hit = bool(rx and re.search(rx, asn_name, re.I))
                cnt[(name, v)]["from_operator_as" if hit else "from_other_as"] += agg.ip_reqs[(name, v, ip)]
        rows_opas = [{"site": site, "bot": b, "verdict": v, "from_operator_as": c["from_operator_as"],
                      "from_other_as": c["from_other_as"]} for (b, v), c in sorted(cnt.items())]
    via = {f"{v}|{'cdn' if c else ('direct' if c is False else 'unknown')}": n for (v, c), n in agg.via.items()}
    summary = {
        "tool": f"ai-bot-verify {VERSION}", "site": site,
        "window_utc": [agg.first_ts.astimezone(timezone.utc).isoformat() if agg.first_ts else None,
                       agg.last_ts.astimezone(timezone.utc).isoformat() if agg.last_ts else None],
        "log_lines": agg.lines, "parsed_lines": agg.parsed, "declared_bot_requests": agg.declared,
        "verdict_totals": dict(totals),
        "unique_ips_by_verdict": {v: len({ip for (b, vv), s in agg.ips.items() if vv == v for ip in s})
                                  for v in VERDICTS},
        "via_cdn": via,
        "range_files": ranges.meta, "warnings": ranges.warnings,
    }
    return {"summary": summary, "by_bot": rows_bot, "by_category": rows_cat, "paths": rows_paths,
            "hours": rows_hours, "days": rows_days, "status": rows_status, "user_agents": rows_ua,
            "by_asn": rows_asn, "behaviour": rows_beh, "operator_as": rows_opas}


def assert_no_ips(obj, known_ips) -> None:
    """Privacy guard: refuse to write if any client IP seen in the logs appears anywhere in
    the output (a generic IP regex is useless here: UA strings carry "Chrome/131.0.0.0")."""
    text = json.dumps(obj, ensure_ascii=False)
    tokens = set(re.findall(r"[0-9a-fA-F:.]{7,}", text))
    leaked = [ip for ip in known_ips if ip in tokens or (":" in ip and ip in text)]
    if leaked:
        raise ValueError(f"privacy guard: {len(leaked)} client IP(s) found in output; nothing written")


def seen_ips(agg: "Agg") -> set:
    s = set(agg.ip_bots)
    for ipset in agg.ips.values():
        s |= ipset
    return s


def write_outputs(report: dict, out: Path, prefix: str = "", known_ips=frozenset()) -> None:
    assert_no_ips(report, known_ips)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{prefix}summary.json").write_text(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    for key in ("by_bot", "by_category", "paths", "hours", "days", "status", "user_agents", "by_asn", "behaviour", "operator_as"):
        rows = report[key]
        if not rows:
            continue
        with open(out / f"{prefix}{key}.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


def print_table(report: dict) -> None:
    s = report["summary"]
    print(f"{s['site']}  window {s['window_utc'][0]} -> {s['window_utc'][1]}")
    print(f"  declared-bot requests: {s['declared_bot_requests']}  verdicts: {s['verdict_totals']}")
    print(f"  {'bot':<20}{'verdict':<15}{'req':>7}{'ips':>6}  robots-1st probe-ips")
    for r in report["by_bot"]:
        print(f"  {r['bot']:<20}{r['verdict']:<15}{r['requests']:>7}{r['unique_ips']:>6}"
              f"  {r['ips_robots_first']:>10} {r['ips_with_vuln_probe']:>9}")
    for w in s["warnings"]:
        print("  warning:", w)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ai-bot-verify", description=__doc__.splitlines()[0])
    ap.add_argument("logs", nargs="+", help="access log files (.gz accepted)")
    ap.add_argument("--site", default="site", help="label for this log set")
    ap.add_argument("--out", type=Path, help="directory for aggregated CSV/JSON (default: print only)")
    ap.add_argument("--prefix", default="", help="filename prefix for outputs")
    ap.add_argument("--asn", action="store_true",
                    help="look up ASN of NON-verified IPs via whois.cymru.com (sends those IPs to Team Cymru)")
    ap.add_argument("--no-dns", action="store_true", help="skip reverse DNS (rDNS-only bots -> indeterminate)")
    ap.add_argument("--ranges-dir", type=Path, help="use local <key>.json range files instead of downloading")
    ap.add_argument("--cache-dir", type=Path, default=Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ai-bot-verify")
    ap.add_argument("--exclude-ip-file", type=Path, help="file with IPs to ignore (your own monitors)")
    ap.add_argument("--withhold-asn-file", type=Path,
                    help="ASNs (one per line) whose number/name/country must not be published")
    ap.add_argument("--since", help="ISO date/time (UTC) lower bound")
    ap.add_argument("--until", help="ISO date/time (UTC) upper bound (exclusive)")
    args = ap.parse_args(argv)

    excl = frozenset()
    if args.exclude_ip_file:
        excl = frozenset(x.strip() for x in args.exclude_ip_file.read_text().split() if x.strip())
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc) if args.since else None
    until = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc) if args.until else None
    ranges = RangeStore(args.cache_dir, args.ranges_dir)
    resolver = None if args.no_dns else Resolver()
    agg = analyse(read_lines(args.logs), ranges, resolver, excl, since, until)
    asn_map = None
    if args.asn:
        asn_map = cymru_asn(sorted(agg.ip_bots))
    withhold = frozenset()
    if args.withhold_asn_file:
        withhold = frozenset(x.strip() for x in args.withhold_asn_file.read_text().splitlines()
                             if x.strip() and not x.startswith("#"))
    report = build_report(agg, args.site, asn_map, ranges, withhold)
    print_table(report)
    if args.out:
        write_outputs(report, args.out, args.prefix, seen_ips(agg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
