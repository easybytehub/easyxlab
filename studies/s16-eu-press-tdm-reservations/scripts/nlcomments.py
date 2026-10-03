#!/usr/bin/env python3
"""Two detectors for natural-language statements in robots.txt comments.

RFC 9309 s. 2.2: comments ("#" to end of line) carry no rules, so a conforming parser ignores
them. Publishers nevertheless write two kinds of statements there, and S16 needs both:

  prohibition(text)  -> the comment forbids robots / automated access or collection in general
                        ("the use of programs or robots ... is prohibited"). S16 makes NO further
                        request to such a host (coordinator decision 2). Tuned for recall: a false
                        positive only costs a home page we do not read.
  reservation(text)  -> the comment reserves text-and-data mining or AI use ("expressly reserves
                        the right ... text and data mining (s. 44b UrhG)"). This is the
                        "comment-only" channel of the classification.

Both work on comment *blocks*: runs of consecutive comment lines (blank lines and rule lines end
a block), so that a sentence wrapped over several "#" lines is read as one sentence.
Standard library only. Precision of both detectors is audited in data/comment_audit.csv.

Version 2 (2026-10-03, after the scan; deviation D2 in METHOD.md): dots inside domain names and
abbreviations no longer end the sentence window ("access taz.de or ... is strictly prohibited"
was missed); the forbid-then-agent window is 160 characters instead of 80; "is not to be used",
"(does) not permit" added. Version 1 is kept as VERSION=1 for the audit comparison.
"""
import re

# ------------------------------------------------------------------ comment extraction
def comment_blocks_meta(body):
    """List of (block text, inline) from a robots.txt body (str or bytes). inline=True for a
    comment written after a rule on the same line ("Disallow: / # ..."): it qualifies that rule."""
    if isinstance(body, bytes):
        body = body[:512 * 1024].decode("utf-8", "replace")
    blocks, cur = [], []
    for raw in re.split(r"\r\n|\r|\n", body):
        if "#" in raw:
            before, c = raw.split("#", 1)
            c = c.strip(" #\t")
            if before.strip():               # trailing comment after a rule: its own block
                if cur:
                    blocks.append((" ".join(cur), False)); cur = []
                if c:
                    blocks.append((c, True))
                continue
            if c:
                cur.append(c)
            continue
        if cur:
            blocks.append((" ".join(cur), False)); cur = []
    if cur:
        blocks.append((" ".join(cur), False))
    return [(re.sub(r"\s+", " ", b).strip(), il) for b, il in blocks if b.strip()]


def comment_blocks(body):
    """List of comment blocks (str) from a robots.txt body (str or bytes)."""
    return [b for b, _ in comment_blocks_meta(body)]


# ------------------------------------------------------------------ vocabulary (EU languages seen in the pilot + major ones)
_AGENT = (r"(?:automat\w*|robot\w*|programs?|programmes?|programm\w*|software|spiders?|crawl\w*|scrap\w*|"
          r"harvest\w*|bots?\b|aspirat\w*|extracti?\w*|extrak\w*|indexing|data[- ]?min\w*|"
          r"Roboter\w*|Programme\w*|automatiz\w*|automatis\w*|zautomatyzowan\w*|geautomatiseerd\w*|"
          r"automatick\w*|automatizovan\w*|automaattis\w*|automatisk\w*|αυτοματοποιημέν\w*)")
_FORBID = (r"(?:prohibit\w*|forbid\w*|not\s+(?:be\s+)?(?:permitted|allowed|authori[sz]ed)|"
           r"(?:is|are)\s+(?:strictly\s+)?(?:prohibited|forbidden|not\s+allowed|not\s+permitted)|"
           r"without\s+(?:\w+\s+){0,4}(?:permission|consent|authori[sz]ation|licen[cs]e)|"
           r"untersagt|nicht\s+(?:gestattet|erlaubt|zulässig)|verboten|unzulässig|ohne\s+(?:\w+\s+){0,3}(?:Zustimmung|Genehmigung|Einwilligung)|"
           r"interdit\w*|n'est\s+pas\s+autoris\w*|sans\s+(?:\w+\s+){0,3}(?:autorisation|accord|consentement)|"
           r"vietat\w*|proibit\w*|non\s+(?:è\s+)?(?:consentit\w*|autorizzat\w*)|senza\s+(?:\w+\s+){0,3}(?:autorizzazione|consenso)|"
           r"prohibid\w*|no\s+(?:está\s+)?(?:permitid\w*|autorizad\w*)|sin\s+(?:\w+\s+){0,3}(?:autorización|consentimiento)|"
           r"proibid\w*|não\s+(?:é\s+)?permitid\w*|"
           r"verboden|niet\s+toegestaan|zonder\s+(?:\w+\s+){0,3}toestemming|"
           r"zabronion\w*|niedozwolon\w*|bez\s+(?:\w+\s+){0,3}zgody|"
           r"zakázan\w*|nepovolen\w*|förbjud\w*|forbudt|ikke\s+tilladt|kielletty|"
           r"tilos|interzis\w*|забранен\w*|απαγορεύ\w*|prepovedan\w*|zabranjen\w*|draudžiam\w*|aizliegt\w*|keelatud)")
_TDM = (r"(?:text\s*(?:and|&|und|-)?\s*data[\s-]*min\w*|data[\s-]*min\w*|\bTDM\b|"
        r"fouille\s+de\s+textes|estrazione\s+di\s+testo|minería\s+de\s+textos|"
        r"\bText-?\s*und\s*Data-?\s*Mining|44\s*b\s*UrhG|§\s*44\s*b|"
        r"2019/790|Article\s+4\b|Art(?:\.|ikel|icle|icolo|ículo)?\s*4\s*(?:\(3\)|Abs\.?\s*3|par\.?\s*3)|"
        r"L\.?\s*122-5-3|70\s*(?:ter|quater)|"
        r"machine[\s-]*learning|\bLLMs?\b|large\s+language|artificial\s+intelligence|\bA\.?I\.?\b|\bKI\b|"
        r"künstliche\w*\s+Intelligenz|intelligence\s+artificielle|intelligenza\s+artificiale|"
        r"inteligencia\s+artificial|kunstmatige\s+intelligentie|sztuczn\w*\s+inteligencj\w*|"
        r"(?:model|AI|KI)[\s-]*train\w*|train\w*\s+(?:of\s+)?(?:AI|models?|LLM)|generative)")
_RESERVE = (r"(?:reserv\w*|vorbehalt\w*|vorbehält|réserv\w*|riserv\w*|reservad\w*|voorbeh\w*|zastrzeg\w*|"
            r"vyhrazen\w*|förbeh\w*|forbeh\w*|opt[\s-]*out|opposition|oppose\w*|s'oppose|widersprech\w*|Widerspruch|"
            r"rights?\s+reservation)")


_FORBID_V2 = _FORBID[:-1] + r"|(?:is|are)\s+not\s+to\s+be\s+used|(?:do|does|will)\s+not\s+permit|not\s+permit\b)"
_rx_prohib_v = {
    1: [re.compile(_AGENT + r"[^.;!?]{0,160}?" + _FORBID, re.I),
        re.compile(_FORBID + r"[^.;!?]{0,80}?" + _AGENT, re.I)],
    2: [re.compile(_AGENT + r"[^.;!?]{0,160}?" + _FORBID_V2, re.I),
        re.compile(_FORBID_V2 + r"[^.;!?]{0,160}?" + _AGENT, re.I)],
}
VERSION = 4


def _protect_dots(text):
    """'taz.de', 'e.g.', 'www.example.org', 'Art. 4' -> dots that do not end a sentence become '·'."""
    text = re.sub(r"(?<=\w)\.(?=\w)", "\u00b7", text)
    return re.sub(r"\b(e\.g|i\.e|etc|Art|Abs|para|No|Nr|ca|incl|vs)\.", lambda m: m.group(1) + "\u00b7", text, flags=re.I)
_rx_tdm = re.compile(_TDM, re.I)
_rx_reserve_verb_v = {1: re.compile(_RESERVE + "|" + _FORBID, re.I), 2: None}


def prohibition(text, version=None):
    """First matching span (str) if the text forbids robots / automated access, else ''."""
    v = version or VERSION
    if v >= 3:
        return prohibition_v3(text, v)
    if v >= 2:
        text = _protect_dots(text)
    for rx in _rx_prohib_v[v]:
        m = rx.search(text)
        if m:
            return m.group(0)[:240]
    return ""


# Cloudflare's "Content Signals Policy" boilerplate defines the signals and says that restrictions
# expressed *via content signals* are reservations; it reserves nothing by itself.
_rx_boiler = re.compile(r"RESTRICTIONS\s+EXPRESSED\s+VIA\s+CONTENT\s+SIGNALS|As a condition of accessing this website, you agree to abide by the following content signals", re.I)


def reservation(text, version=None):
    """Matching evidence if the text reserves TDM / AI use: a TDM-or-AI term AND a reservation
    or prohibition verb in the same comment block. Labels such as '# AI crawlers' or
    '# Block AI bots' have no such verb and do not match; Cloudflare's Content Signals Policy
    boilerplate is skipped (it defines signals, it does not set any)."""
    if (version or VERSION) >= 3:
        return reservation_v3(text, version or VERSION)
    if _rx_boiler.search(text):
        return ""
    m = _rx_tdm.search(text)
    if not m:
        return ""
    rx = _rx_reserve_verb_v[version or VERSION]
    if rx is None:
        rx = _rx_reserve_verb_v[2] = re.compile(_RESERVE + "|" + _FORBID_V2, re.I)
    v = rx.search(text)
    if not v:
        return ""
    return (m.group(0) + " | " + v.group(0))[:240]


# ------------------------------------------------------------------ version 3 (deviation D5)
# Coordinator decision of 2026-10-03 after the independent review:
#  * a GENERAL prohibition of robots / automated access stops all further requests (unchanged);
#  * an inline comment on a per-agent rule ("User-agent: Yandex / Disallow: / # prohibits crawling")
#    applies to that agent only: not a general prohibition;
#  * section labels ("Not allowed bots") are not prohibitions;
#  * purpose-specific notices (no TDM, no AI training, "not to be used for the purposes of text and
#    data mining", s. 42h(6) UrhG AT) are RESERVATIONS, not prohibitions of our access (we read only
#    the declared policy channels and store no article content);
#  * list-style notices ("il est interdit :" / "- d'utiliser tout systeme automatise ...") are read
#    across the following comment blocks.
_PURPOSE = (r"(?:text\s*(?:and|&|und|-)?\s*data[\s-]*min\w*|\bTDM\b|fouille\s+de\s+textes|Text-?\s*und\s*Data|"
            r"44\s*b\b|42\s*h\b|2019/790|Article\s+4\b|Art(?:\.|\u00b7|icle|ikel|icolo|ículo)?\s*4\s*(?:\(3\)|Abs|par)|"
            r"machine[\s-]*learning|\bLLMs?\b|language\s+models?|artificial\s+intelligence|"
            r"(?<![\w\u00b7./@-])A[.\u00b7]?I(?![\w\u00b7/-])|\bKI\b|künstliche\w*\s+Intelligenz|intelligence\s+artificielle|"
            r"intelligenza\s+artificiale|inteligencia\s+artificial|kunstmatige\s+intelligentie|sztuczn\w*\s+inteligencj\w*|"
            r"tekoäly\w*|\btrain\w*|\btraining\b|entraîn\w*|addestr\w*|entrenamiento|genAI|generative)")
_GENERAL = (r"(?:\bparticularly\b|\bin\s+particular\b|\binsbesondere\b|\bnotamment\b|\bin\s+particolare\b|"
            r"\bespecially\b|\ben\s+particular\b)")
_SINGLE = (r"(?:\bseul\s+robot\b|\bce\s+robot\b|\bthis\s+(?:one\s+)?(?:bot|robot|crawler)(?:\s+only)?\b|"
           r"\bonly\s+this\s+(?:bot|robot|crawler)\b|\bdiese[rnm]?\s+(?:Bot|Crawler|Roboter)\b)")
_COPULA = r"\b(?:is|are|be|ist|sind|est|sont|è|sono|es|son|está|zijn|jest|są|er|är|on|ovat)\b"
_rx_purpose = re.compile(_PURPOSE, re.I)
_rx_general = re.compile(_GENERAL, re.I)
# Version 4 (deviation D7, after the re-review): a ban that names TDM/AI purposes but ends in an open
# clause covers every purpose, so it is a GENERAL prohibition: "... for machine learning or artificial
# intelligence purposes or otherwise", "for any purpose", "include but are not limited to: ... (4) any
# commercial purposes". A short heading whose only reservation word sits in parentheses ("Google AI
# Models (Opt-out, does not affect Googlebot)") is a label, not a reservation.
_OPEN_V4 = (r"(?:\bor\s+otherwise\s*[)\]]*\s*$|\bfor\s+any\s+purposes?\b|\bnot\s+limited\s+to\b|"
            r"\bany\s+commercial\s+purposes?\b)")
_rx_general_v4 = re.compile(_GENERAL[:-1] + "|" + _OPEN_V4[3:], re.I)
_rx_single = re.compile(_SINGLE, re.I)
_rx_copula = re.compile(_COPULA, re.I)
_rx_tdm_v3 = re.compile(_TDM.replace(r"\bA\.?I\.?\b", r"(?<![\w\u00b7./@-])A[.\u00b7]?I\.?(?![\w\u00b7/-])"), re.I)


def _is_label(text):
    words = re.findall(r"\w+", text)
    return len(words) <= 4 and not _rx_copula.search(text)


def _sentences(text):
    """Sentences and list items; an item that follows an intro ending in ':' is read with it."""
    segs = []
    for s in re.split(r"[.;!?]+(?:\s|$)", _protect_dots(text)):
        segs += [x.strip(" -\u2013\u2022*") for x in re.split(r"(?:^|\s)[-\u2013\u2022*]\s", s)]
    out, intro = [], ""
    for s in segs:
        if not s:
            continue
        out.append((intro + " " + s).strip() if intro else s)
        if s.rstrip().endswith(":"):
            intro = s
    return out


def prohibition_v3(text, version=3):
    """General prohibition in one (non-inline) text: a sentence that forbids robots / automated
    access and is neither purpose-specific (TDM/AI terms without a 'particularly'-type marker),
    nor about a single named robot, nor a short section label."""
    if _is_label(text):
        return ""
    for s in _sentences(text):
        for rx in _rx_prohib_v[2]:
            m = rx.search(s)
            if not m:
                continue
            if _rx_single.search(s):
                continue
            # purpose qualifiers are looked for in the prohibition itself, the rest of the sentence and
            # the three words before it ("AI training crawlers are not permitted"), not in an earlier
            # clause ("... (s. 44 b UrhG) The use of robots ... is strictly prohibited" stays general)
            start = m.start()
            span = s[m.start():m.end()]
            fms = list(re.finditer(_FORBID_V2, span, re.I))
            if fms and rx is _rx_prohib_v[2][0]:       # agent ... forbid: take the agent word nearest the forbid word
                ags = [a for a in re.finditer(_AGENT, span, re.I) if a.end() <= fms[-1].start()]
                if ags:
                    start = m.start() + ags[-1].start()
            ctx = " ".join(s[:start].split()[-3:]) + " " + s[start:]
            gen = _rx_general_v4 if version >= 4 else _rx_general
            if _rx_purpose.search(ctx) and not gen.search(s):
                continue
            return m.group(0)[:240]
    return ""


def _is_heading_v4(text):
    words = re.findall(r"\w+", text)
    outside = re.sub(r"\([^)]*\)", " ", text)
    return len(words) <= 10 and "(" in text and not re.search(_RESERVE + "|" + _FORBID_V2, outside, re.I)


def reservation_v3(text, version=3):
    """As reservation(version=2), but dots inside domain names cannot produce an 'AI' match
    ('exa.ai'), and section labels are not reservations."""
    if _rx_boiler.search(text) or _is_label(text) or (version >= 4 and _is_heading_v4(text)):
        return ""
    pt = _protect_dots(text)
    m = _rx_tdm_v3.search(pt)
    if not m:
        return ""
    if _rx_reserve_verb_v[2] is None:
        _rx_reserve_verb_v[2] = re.compile(_RESERVE + "|" + _FORBID_V2, re.I)
    v = _rx_reserve_verb_v[2].search(pt)
    if not v:
        return ""
    return (m.group(0) + " | " + v.group(0))[:240]


def _units_v3(body):
    """Texts examined by v3: every non-inline block, plus each block that ends with ':' joined
    with the blocks that follow it (up to 4), for list-style notices. Inline blocks are kept apart."""
    meta = comment_blocks_meta(body)
    units = [(b, il) for b, il in meta]
    for i, (b, il) in enumerate(meta):
        if not il and b.rstrip().endswith(":"):
            nxt = [x for x, l2 in meta[i + 1:i + 5] if not l2]
            if nxt:
                units.append((b + " - " + " - ".join(x.lstrip("-\u2013\u2022* ") for x in nxt), False))
    return units


def scan(body, version=None):
    """Detector results over all comment blocks of a robots.txt body."""
    v = version or VERSION
    if v >= 3:
        units = _units_v3(body)
        blocks = [b for b, _ in comment_blocks_meta(body)]
        pro = [(b, "" if il else prohibition_v3(b, v)) for b, il in units]
        res = [(b, reservation_v3(b, v)) for b, il in units]
    else:
        blocks = comment_blocks(body)
        pro = [(b, prohibition(b, version)) for b in blocks]
        res = [(b, reservation(b, version)) for b in blocks]
    return {
        "detector_version": version or VERSION,
        "n_comment_blocks": len(blocks),
        "nl_prohibition": any(e for _, e in pro),
        "nl_prohibition_evidence": next((e for _, e in pro if e), ""),
        "nl_reservation": any(e for _, e in res),
        "nl_reservation_evidence": next((e for _, e in res if e), ""),
        "blocks_flagged": [b[:600] for b, e in pro + res if e],
    }
