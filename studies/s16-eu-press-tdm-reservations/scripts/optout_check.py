#!/usr/bin/env python3
"""optout_check — what a text-and-data-mining (TDM) crawler can read on one website.

    python3 scripts/optout_check.py example.org            # JSON on stdout
    python3 scripts/optout_check.py example.org --brief    # one line

Reads, in this order and only where robots.txt allows it for our user agent:
  1. /robots.txt (RFC 9309): groups and rules, named AI crawlers blocked at the root, whether a
     crawler with a NEW name would be blocked (the '*' group), Content-Signal lines and IETF AI
     Preferences 'Content-Usage' rules (draft-ietf-aipref-attach-05 / vocab-08), and comments
     (natural-language reservations and prohibitions, scripts/nlcomments.py).
     If the comments forbid robots or automated access, nothing else is requested.
  2. /.well-known/tdmrep.json (W3C TDMRep, Community Group Final Report 2024-05-10).
  3. the home page: 'tdm-reservation' / 'tdm-policy' / 'Content-Usage' / 'X-Robots-Tag' headers and
     <meta name="tdm-reservation|tdm-policy|robots"> (incl. the non-standard 'noai' values).
  4. /llms.txt (context only; not a reservation mechanism).

Verdict (frozen in METHOD.md before the S16 collection):
  agnostic_reservation  a reservation any crawler can read whatever its name: TDMRep reservation
                        in any channel; Content-Signal ai-train=no; Content-Usage train-ai=n for an
                        unnamed crawler (or as an HTTP header); or the '*' group disallowing '/'.
  named_bots_only       no agnostic reservation, but at least one named AI crawler blocked at '/'.
  comment_only          neither of the above, but a natural-language reservation or prohibition
                        in robots.txt comments (which RFC 9309 parsers ignore).
  none_stated           none of the above.
  *_robots_only_partial the same three classes for a host read on robots.txt only (natural-language
                        prohibition in its comments): its TDMRep, headers and <meta> are unknown.
  + contradiction       two explicit machine-readable use-preference channels disagree
                        (TDMRep 1 vs 0 / Content-Signal ai-train / Content-Usage train-ai).

Legal frame: Directive (EU) 2019/790 Art. 4(3) (reservation "in an appropriate manner, such as
machine-readable means"); Regulation (EU) 2024/1689 Art. 53(1)(c) (GPAI providers must identify and
comply with such reservations); GPAI Code of Practice, Copyright chapter, Measure 1.3. The output
states what a crawler can read; it is not a legal assessment of the site. Standard library only.
"""
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser

import politefetch as P
import robots9309 as R

CHECKER_VERSION = "1.0"
UNNAMED = "s16-unnamed-crawler"      # a product token nobody names: what a NEW crawler would read
AI_TOKENS = [
    # training / dataset crawlers
    "GPTBot", "ClaudeBot", "anthropic-ai", "Google-Extended", "CCBot", "Applebot-Extended", "Bytespider",
    "meta-externalagent", "FacebookBot", "cohere-training-data-crawler", "cohere-ai", "Diffbot", "Timpibot",
    "omgili", "Omgilibot", "ImagesiftBot", "Amazonbot",
    # AI search / assistant fetchers
    "OAI-SearchBot", "ChatGPT-User", "Claude-SearchBot", "Claude-User", "Claude-Web", "PerplexityBot",
    "Perplexity-User", "MistralAI-User", "meta-externalfetcher",
]
HEADLINE4 = ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot"]
LEGAL_BASIS = [
    "Directive (EU) 2019/790, Art. 4(3): TDM exception applies unless use has been 'expressly reserved by "
    "their rightholders in an appropriate manner, such as machine-readable means in the case of content made "
    "publicly available online'.",
    "Regulation (EU) 2024/1689 (AI Act), Art. 53(1)(c): GPAI providers shall 'identify and comply with, "
    "including through state-of-the-art technologies, a reservation of rights expressed pursuant to Article "
    "4(3) of Directive (EU) 2019/790' (applies from 2 August 2025).",
    "General-Purpose AI Code of Practice, Copyright chapter, Measure 1.3: follow robots.txt (RFC 9309) and "
    "'other appropriate machine-readable protocols ... widely adopted by rightsholders'.",
]


# ------------------------------------------------------------------ robots.txt extras
def parse_extras(body):
    """Content-Signal and Content-Usage lines with the group they belong to (same grouping as
    robots9309.parse; both count as rules for grouping). Returns
    {'groups': [{'agents': [...], 'content_signal': [...], 'content_usage': [...]}],
     'outside': {'content_signal': [...], 'content_usage': [...]}}"""
    if isinstance(body, bytes):
        body = body[:R.PARSE_LIMIT].decode("utf-8", "replace")
    if body.startswith("﻿"):
        body = body[1:]
    groups, cur, in_rules = [], None, False
    outside = {"content_signal": [], "content_usage": []}
    for raw in re.split(r"\r\n|\r|\n", body):
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip().lower(), val.strip()
        if key in R.UA_KEYS:
            if cur is None or in_rules:
                cur = {"agents": [], "content_signal": [], "content_usage": []}
                groups.append(cur)
                in_rules = False
            tok = R.product_token(val)
            if tok:
                cur["agents"].append(tok)
        elif key in R.DISALLOW_KEYS or key in R.ALLOW_KEYS:
            if cur is not None:
                in_rules = True
        elif key in ("content-signal", "content-signals", "content_signal"):
            (cur["content_signal"] if cur is not None else outside["content_signal"]).append(val)
            if cur is not None:
                in_rules = True
        elif key == "content-usage":
            (cur["content_usage"] if cur is not None else outside["content_usage"]).append(val)
            if cur is not None:
                in_rules = True
    return {"groups": groups, "outside": outside}


def parse_signal(val):
    """'search=yes, ai-train=no' -> {'search': 'yes', 'ai-train': 'no'} (lower case)."""
    out = {}
    for part in re.split(r"[,;]", val):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().lower()] = v.strip().strip('"').lower()
    return out


def parse_usage_rule(val):
    """Content-Usage rule value -> (path, {label: 'y'|'n'|other}) per attach-05 s. 3.2."""
    path = None
    if val.startswith("/"):
        m = re.match(r"(\S+)\s+(.*)$", val)
        if m:
            path, val = m.group(1), m.group(2)
        else:
            path, val = val, ""
    prefs = {}
    for part in val.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            prefs[k.strip()] = v.strip().split(";")[0].strip().strip('"')
        else:
            prefs[part.split(";")[0]] = "?1"
    return path, prefs


def usage_for_root(extras, token):
    """train-ai preference that applies to '/' for a crawler with this product token: the rules of
    the groups naming it, else of the '*' groups (RFC 9309 s. 2.2.1); longest matching path."""
    t = token.lower()
    named = [g for g in extras["groups"] if t in g["agents"]]
    groups = named or [g for g in extras["groups"] if "*" in g["agents"]]
    best_len, val = -1, None
    for g in groups:
        for rule in g["content_usage"]:
            path, prefs = parse_usage_rule(rule)
            if "train-ai" not in prefs:
                continue
            p = path or ""
            if p and not R._pattern_regex(p).match("/"):
                continue
            n = len(p)
            v = prefs["train-ai"]
            if n > best_len or (n == best_len and v == "n"):
                best_len, val = n, v
    return val


# ------------------------------------------------------------------ HTML <head> meta
class _Meta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = []
        self.done = False

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            name = (a.get("name") or a.get("http-equiv") or a.get("property") or "").strip().lower()
            if name:
                self.meta.append((name, a.get("content", "").strip()))
        elif tag == "body":
            self.done = True

    def handle_endtag(self, tag):
        if tag == "head":
            self.done = True


def head_meta(html_text):
    p = _Meta()
    try:
        p.feed(html_text[:600_000])
    except Exception:  # noqa: BLE001
        pass
    return p.meta


def tdm_value(v):
    v = (v or "").strip().strip('"').lower()
    if v in ("1", "true"):
        return 1
    if v in ("0", "false"):
        return 0
    return None


def noai_in(v):
    return bool(re.search(r"\bno-?(?:image)?ai\b", v or "", re.I))


# ------------------------------------------------------------------ tdmrep.json
def parse_tdmrep(res):
    """-> dict(state=absent|soft404|invalid|ok, rules=[...], root=1|0|None, any_reservation=bool)"""
    d = dict(state="absent", status=res.get("status"), rules=0, root=None, any_reservation=False,
             any_zero=False, has_policy=False)
    st = res.get("status")
    if res.get("error") or st is None:
        d["state"] = "not_fetched:" + (res.get("error") or "no_status")
        return d
    if st != 200:
        return d
    body = (res.get("body") or b"").lstrip()
    ct = res["headers"].get("content-type", "").lower()
    if "html" in ct or body[:1] == b"<":
        d["state"] = "soft404"
        return d
    try:
        j = json.loads(body.decode("utf-8-sig", "replace"))
    except ValueError:
        d["state"] = "invalid"
        return d
    if isinstance(j, dict):
        j = [j]                               # tolerated (spec: MUST be an array); flagged
        d["not_array"] = True
    if not isinstance(j, list) or not all(isinstance(x, dict) for x in j):
        d["state"] = "invalid"
        return d
    d["state"] = "ok"
    d["rules"] = len(j)
    best_len = -1
    for rule in j:
        v = tdm_value(str(rule.get("tdm-reservation", "")))
        loc = str(rule.get("location", ""))
        if rule.get("tdm-policy"):
            d["has_policy"] = True
        if v == 1:
            d["any_reservation"] = True
        if v == 0:
            d["any_zero"] = True
        if v is None or not loc:
            continue
        pat = loc if loc.startswith(("/", "*")) else "/" + loc
        if R._pattern_regex(pat).match("/") and len(pat) >= best_len:
            if len(pat) > best_len or v == 1:
                d["root"] = v
            best_len = len(pat)
    return d


# ------------------------------------------------------------------ the check
def check(host, session=None):
    s = session or P.Session(per_host=8)
    host = host.strip().lower()
    host = re.sub(r"^https?://", "", host).split("/")[0]
    rec = dict(host=host, checker_version=CHECKER_VERSION, checked_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    rb = s.robots_for(host)
    rec["robots"] = dict(state=rb["state"], status=rb["status"], error=rb["error"], scheme=rb.get("scheme"),
                         final_url=rb["final_url"], content_type=rb["content_type"])
    groups = rb.get("groups") or []
    body = rb.get("body") or b""
    extras = parse_extras(body) if body else {"groups": [], "outside": {"content_signal": [], "content_usage": []}}
    nl = rb.get("nl") or {}
    star_group = any("*" in g["agents"] for g in groups)
    rec["robots"].update(
        has_groups=R.has_groups(groups), star_group=star_group,
        unnamed_blocked_root=R.blocks_root(groups, UNNAMED) if groups else False,
        ai_blocked_root=sorted(t for t in AI_TOKENS if groups and R.named(groups, t) and R.blocks_root(groups, t)),
        ai_named=sorted(t for t in AI_TOKENS if groups and R.named(groups, t)),
        content_signal=[v for g in extras["groups"] for v in g["content_signal"]] + extras["outside"]["content_signal"],
        content_usage=[v for g in extras["groups"] for v in g["content_usage"]] + extras["outside"]["content_usage"],
        content_usage_unnamed_root=usage_for_root(extras, UNNAMED),
        nl_reservation=bool(nl.get("nl_reservation")), nl_reservation_evidence=nl.get("nl_reservation_evidence", ""),
        nl_prohibition=bool(nl.get("nl_prohibition")), nl_prohibition_evidence=nl.get("nl_prohibition_evidence", ""),
        n_comment_blocks=nl.get("n_comment_blocks", 0), bytes=len(body))
    rec["robots"]["headline4_blocked_root"] = [t for t in HEADLINE4 if t in rec["robots"]["ai_blocked_root"]]
    # Content-Signal: ai-train value(s) anywhere in the file
    cs_train = {parse_signal(v).get("ai-train") for v in rec["robots"]["content_signal"]} - {None}
    rec["robots"]["content_signal_ai_train"] = sorted(cs_train)

    base = f"{rb.get('scheme') or 'https'}://{host}"
    if rb.get("scheme") == "http" and rb["state"] in ("ok", "unavailable"):
        base = f"http://{host}"
    rec["read"] = dict(tdmrep=False, home=False, llms=False, reason="")
    if rb["state"] == "nl_prohibition":
        rec["read"]["reason"] = "not read: natural-language prohibition"
    elif rb["state"] == "unreachable":
        rec["read"]["reason"] = "robots.txt unreachable (RFC 9309 s. 2.3.1.4: complete disallow)"
    # 2. tdmrep.json
    tdm = dict(state="not_fetched", root=None, any_reservation=False)
    if not rec["read"]["reason"]:
        u = base + "/.well-known/tdmrep.json"
        if s.allowed(host, u):
            r = s.get(u, limit=300_000, headers={"Accept": "application/json, */*;q=0.5"})
            tdm = parse_tdmrep(r)
            tdm["final_url_same_host"] = P.authority(r["final_url"]) == host
            rec["read"]["tdmrep"] = True
        else:
            tdm["state"] = "robots_disallowed"
    rec["tdmrep_file"] = tdm
    # 3. home page
    home = dict(fetched=False)
    if not rec["read"]["reason"]:
        u = base + "/"
        if s.allowed(host, u):
            r = s.get(u, limit=1_500_000, headers={"Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"})
            hd = r["headers"]
            home = dict(fetched=True, status=r["status"], error=r["error"], final_host=P.authority(r["final_url"]),
                        hdr_tdm_reservation=hd.get("tdm-reservation"), hdr_tdm_policy=hd.get("tdm-policy"),
                        hdr_content_usage=hd.get("content-usage"), hdr_x_robots_tag=hd.get("x-robots-tag"))
            meta = head_meta(P.text_of(r)) if r["body"] else []
            home["meta_tdm_reservation"] = next((v for n, v in meta if n == "tdm-reservation"), None)
            home["meta_tdm_policy"] = next((v for n, v in meta if n == "tdm-policy"), None)
            robots_meta = [v for n, v in meta if n in ("robots", "googlebot", "ccbot", "gptbot")]
            home["meta_robots"] = robots_meta[:4]
            home["meta_noai"] = any(noai_in(v) for v in robots_meta)
            home["hdr_noai"] = noai_in(hd.get("x-robots-tag"))
            rec["read"]["home"] = True
        else:
            home["reason"] = "robots_disallowed"
    rec["home"] = home
    # 4. llms.txt
    llms = dict(state="not_fetched")
    if not rec["read"]["reason"]:
        u = base + "/llms.txt"
        if s.allowed(host, u):
            r = s.get(u, limit=200_000)
            b = (r["body"] or b"").lstrip()
            ct = r["headers"].get("content-type", "").lower()
            if r["status"] == 200 and b and "html" not in ct and b[:1] != b"<":
                llms = dict(state="present", spec_like=b[:2] == b"# ", bytes=len(r["body"]))
            else:
                llms = dict(state="absent" if not r["error"] else "error", status=r["status"])
            rec["read"]["llms"] = True
        else:
            llms["state"] = "robots_disallowed"
    rec["llms_txt"] = llms
    rec["verdict"] = verdict(rec)
    rec["legal_basis"] = LEGAL_BASIS
    return rec


def verdict(rec):
    rb, tdm, home = rec["robots"], rec["tdmrep_file"], rec["home"]
    if rb["state"] == "unreachable":
        return dict(class_="robots_unreachable", agnostic_channels=[], contradiction=False, explicit={})
    # explicit machine-readable use preferences, per channel: 'reserve' | 'allow'
    explicit = {}
    if tdm.get("state") == "ok":
        if tdm.get("any_reservation"):
            explicit["tdmrep_file"] = "reserve"
        elif tdm.get("root") == 0 or tdm.get("any_zero"):
            explicit["tdmrep_file"] = "allow"
    hv = tdm_value(home.get("hdr_tdm_reservation"))
    if hv is not None:
        explicit["tdmrep_header"] = "reserve" if hv == 1 else "allow"
    mv = tdm_value(home.get("meta_tdm_reservation"))
    if mv is not None:
        explicit["tdmrep_meta"] = "reserve" if mv == 1 else "allow"
    cs = set(rb.get("content_signal_ai_train") or [])
    if cs:
        explicit["content_signal"] = "reserve" if "no" in cs else ("allow" if "yes" in cs else None)
        if cs >= {"no", "yes"}:
            explicit["content_signal_internal_conflict"] = True
    cu = rb.get("content_usage_unnamed_root")
    if cu in ("n", "y"):
        explicit["content_usage_robots"] = "reserve" if cu == "n" else "allow"
    hcu = home.get("hdr_content_usage")
    if hcu:
        _, prefs = parse_usage_rule(hcu)
        if prefs.get("train-ai") in ("n", "y"):
            explicit["content_usage_header"] = "reserve" if prefs["train-ai"] == "n" else "allow"
    explicit = {k: v for k, v in explicit.items() if v is not None}
    agn = [k for k, v in explicit.items() if v == "reserve" and k != "content_signal_internal_conflict"]
    if rb.get("unnamed_blocked_root"):
        agn.append("robots_star_disallow_root")
    vals = {v for k, v in explicit.items() if k != "content_signal_internal_conflict"}
    contradiction = vals >= {"reserve", "allow"}
    partial = bool(rec["read"]["reason"])
    if agn:
        c = "agnostic_reservation"
    elif rb.get("ai_blocked_root"):
        # B1: for a host read on robots.txt only, the other channels are unknown
        c = "named_bots_robots_only_partial" if partial else "named_bots_only"
    elif rb.get("nl_reservation") or rb.get("nl_prohibition"):
        c = "comment_only_robots_only_partial" if partial else "comment_only"
    else:
        c = "none_stated_robots_only_partial" if partial else "none_stated"
    return dict(class_=c, agnostic_channels=sorted(agn), contradiction=contradiction, explicit=explicit,
                partial=bool(rec["read"]["reason"]), noai=bool(home.get("meta_noai") or home.get("hdr_noai")))


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    rec = check(a[0])
    if "--brief" in a:
        v = rec["verdict"]
        print(f"{rec['host']}: {v['class_']}{' + contradiction' if v['contradiction'] else ''}"
              f" agnostic={','.join(v['agnostic_channels']) or '-'} named={','.join(rec['robots']['ai_blocked_root']) or '-'}"
              f"{' [' + rec['read']['reason'] + ']' if rec['read']['reason'] else ''}")
    else:
        print(json.dumps(rec, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
