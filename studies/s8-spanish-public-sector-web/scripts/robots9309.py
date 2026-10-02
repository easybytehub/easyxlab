#!/usr/bin/env python3
"""robots.txt parsing and matching as specified by RFC 9309 (Robots Exclusion Protocol).

Why not urllib.robotparser: it matches rules in file order instead of by the most specific
(longest) match (RFC 9309 s. 2.2.2), does not expand "*" or "$" inside paths (s. 2.2.3), and
ends a group at a blank line, which the RFC grammar allows inside a group (s. 2.2).

The body is parsed whatever Content-Type it was served with: s. 2.3.1.1 says "If the crawler
successfully downloads the robots.txt file, the crawler MUST follow the parseable rules", and
s. 2.3.1.5 "Crawlers MUST try to parse each line of the robots.txt file. Crawlers MUST use the
parseable rules." An HTML page served at /robots.txt simply has no parseable rules, unless it
does contain user-agent/allow/disallow lines, in which case they are followed.

Standard library only.
"""
import re
from urllib.parse import quote, urlsplit

UNRESERVED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
# common misspellings accepted (RFC 9309 s. 2.2.4 allows leniency for other records; for these
# keys we follow what large crawlers document accepting)
UA_KEYS = {"user-agent", "useragent", "user agent"}
DISALLOW_KEYS = {"disallow", "dissallow", "dissalow", "disalow", "diasllow", "disallaw"}
ALLOW_KEYS = {"allow"}
PARSE_LIMIT = 512 * 1024      # s. 2.5: "The parsing limit MUST be at least 500 kibibytes"


def _norm_path(p):
    """Percent-encode non-ASCII and reserved-unsafe octets, decode encoded unreserved ASCII,
    upper-case hex digits (s. 2.2.2, Figure 4). '*' and '$' are left alone for patterns."""
    p = quote(p, safe="/?=&;:@!$'()*+,%#[]~-._")

    def fix(m):
        c = chr(int(m.group(1), 16))
        return c if c in UNRESERVED else "%" + m.group(1).upper()
    return re.sub(r"%([0-9A-Fa-f]{2})", fix, p)


def product_token(value):
    """The product-token part of a user-agent line value ('Googlebot/2.1' -> 'googlebot')."""
    v = value.strip()
    if v.startswith("*"):
        return "*"
    m = re.match(r"[A-Za-z_-]+", v)
    return m.group(0).lower() if m else ""


def parse(body):
    """Return a list of groups: [{'agents': [tokens], 'rules': [(allow:bool, pattern)]}].
    body: str or bytes."""
    if isinstance(body, bytes):
        body = body[:PARSE_LIMIT].decode("utf-8", "replace")
    else:
        body = body[:PARSE_LIMIT]
    if body.startswith("﻿"):
        body = body[1:]
    groups, cur, in_rules = [], None, False
    for raw in re.split(r"\r\n|\r|\n", body):
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip().lower(), val.strip()
        if key in UA_KEYS:
            if cur is None or in_rules:
                cur = {"agents": [], "rules": []}
                groups.append(cur)
                in_rules = False
            tok = product_token(val)
            if tok:
                cur["agents"].append(tok)
        elif key in DISALLOW_KEYS or key in ALLOW_KEYS:
            if cur is None:
                continue                      # s. 2.2.2: rules outside any group are ignored
            in_rules = True
            if val == "":
                continue                      # empty pattern: matches nothing
            if not val.startswith("/") and not val.startswith("*"):
                continue                      # not a path pattern
            cur["rules"].append((key in ALLOW_KEYS, val))
        # other records (sitemap, crawl-delay, host, ...) neither start nor end a group (s. 2.2.4)
    return groups


def has_groups(groups):
    return any(g["agents"] for g in groups)


def rules_for(groups, token):
    """Rules that apply to a product token: all groups naming it (merged, s. 2.2.1), else all
    '*' groups (merged), else none."""
    t = token.lower()
    named = [r for g in groups if t in g["agents"] for r in g["rules"]]
    if any(t in g["agents"] for g in groups):
        return named, True
    star = [r for g in groups if "*" in g["agents"] for r in g["rules"]]
    return star, False


def named(groups, token):
    return any(token.lower() in g["agents"] for g in groups)


def _pattern_regex(pat):
    end = pat.endswith("$")
    if end:
        pat = pat[:-1]
    pat = _norm_path(pat)
    rx = "".join(".*" if c == "*" else re.escape(c) for c in pat)
    return re.compile(rx + ("$" if end else ""), re.S)


_rx_cache = {}


def _match_len(pat, path):
    """Octet length of the pattern if it matches the start of path, else -1."""
    rx = _rx_cache.get(pat)
    if rx is None:
        rx = _rx_cache[pat] = _pattern_regex(pat)
    return len(pat) if rx.match(path) else -1


def allowed(groups, token, url_or_path):
    """RFC 9309 decision for one URL or path. The most specific (longest) matching rule wins;
    on a tie between allow and disallow, allow wins. /robots.txt is always allowed."""
    if url_or_path.startswith(("http://", "https://")):
        p = urlsplit(url_or_path)
        path = (p.path or "/") + (("?" + p.query) if p.query else "")
    else:
        path = url_or_path or "/"
    if path == "/robots.txt":
        return True
    path = _norm_path(path)
    rules, _ = rules_for(groups, token)
    best_len, best_allow = -1, True
    for is_allow, pat in rules:
        n = _match_len(pat, path)
        if n < 0:
            continue
        if n > best_len or (n == best_len and is_allow):
            best_len, best_allow = n, is_allow
    return best_allow if best_len >= 0 else True


def blocks_root(groups, token):
    return not allowed(groups, token, "/")


if __name__ == "__main__":
    # self-test with the RFC's own examples and the cases met in this study
    g = parse("User-agent: ExampleBot\ndisallow: /foo\ndisallow: /bar\n\nuser-agent: ExampleBot\ndisallow: /baz\n")
    assert not allowed(g, "ExampleBot", "/baz/x") and allowed(g, "Other", "/baz")
    g = parse("user-agent: *\ndisallow: /foo\ndisallow: /bar\n\nuser-agent: BazBot\ndisallow: /baz\n")
    assert not allowed(g, "ExampleBot", "/foo") and allowed(g, "ExampleBot", "/baz")
    # longest match, allow wins ties
    g = parse("User-agent: *\nDisallow: /\nAllow: /$\n")
    assert allowed(g, "x", "/") and not allowed(g, "x", "/a")
    g = parse("User-agent: *\nAllow: /p\nDisallow: /\n")
    assert allowed(g, "x", "/page") and not allowed(g, "x", "/other")
    # wildcard: robotparser reads "Disallow: /*" as a literal path; RFC 9309 blocks everything
    g = parse("User-agent: *\nDisallow: /*\n")
    assert not allowed(g, "x", "/")
    g = parse("User-agent: *\nDisallow: /*.txt$\n")
    assert not allowed(g, "x", "/llms.txt") and allowed(g, "x", "/llms.txt?x") and allowed(g, "x", "/")
    # allow-list for search engines only (the Castello platform, calig.es)
    g = parse("User-agent: googlebot\nUser-agent: bingbot\nCrawl-delay: 10\n\n# Directories\nDisallow: /core/\n\n\nUser-agent: *\nDisallow: /\n")
    assert blocks_root(g, "EasyByteLab-research") and not blocks_root(g, "googlebot")
    # blank lines and comments between user-agent lines and rules (unavarra.es)
    g = parse("User-agent: GPTBot\nUser-agent: ClaudeBot\n\n# AI crawlers\n\nDisallow: /\n")
    assert blocks_root(g, "GPTBot") and blocks_root(g, "claudebot") and not blocks_root(g, "other")
    # rules before any user-agent line are ignored; empty disallow allows
    g = parse("Disallow: /\nUser-agent: *\nDisallow:\n")
    assert allowed(g, "x", "/")
    # HTML soft-404 has no groups
    g = parse("<!doctype html><html><body>Not found</body></html>")
    assert not has_groups(g) and allowed(g, "x", "/")
    # percent-encoding equivalence
    g = parse("User-agent: *\nDisallow: /foo/bar/%62%61%7A\n")
    assert not allowed(g, "x", "/foo/bar/baz")
    print("robots9309 self-test passed")
