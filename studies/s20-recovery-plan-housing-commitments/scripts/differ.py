#!/usr/bin/env python3
"""Word-level diff of two versions of a CID text (a milestone/target row or a measure
description) and a rule-based classification of what changed.

Categories (a change can have several):
  amount      a euro amount was added, removed or changed ("EUR 4 000 000 000" -> "EUR 750 000 000")
  quantity    the goal or baseline cell changed, or a non-money number in the text changed
              (dwellings, percentages, counts)
  deadline    the quarter or year cell changed, or a calendar date in the text changed
  definition  words other than numbers changed: what counts, what is required, where, how
              it is verified; also the name, the indicator and the unit
  editorial   the text changed in any other way: spacing ("80 %" -> "80%", "1.Description" ->
              "1. Description"), case, punctuation or spelling. Every textual change is recorded.
  added / removed   the row or measure exists in only one of the two versions

The rules are deliberately mechanical; every classification is published with the literal
old and new text so that a reader can check it. Standard library only.
"""
import difflib, re, unicodedata

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
EUR_RE = re.compile(r"EUR\s?\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|EUR\s?\d+(?:[.,]\d+)?(?:\s?(?:billion|million))?", re.I)
DATE_RE = re.compile(r"\b\d{1,2}\s(?:%s)(?:\s\d{4})?\b|\bQ[1-4]\s?\d{4}\b" % MONTHS)
NUM_RE = re.compile(r"\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s?%?")
TOKEN_RE = re.compile(r"EUR\s?\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?%?|\w+|[^\w\s]", re.U)


def norm_space(s):
    s = unicodedata.normalize("NFC", s or "").replace("\xa0", " ").replace(" ", " ")
    s = re.sub(r"(\d)\s+%", r"\1%", s)          # "80 %" and "80%" are the same
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokens(s):
    return TOKEN_RE.findall(norm_space(s))


def eur_amounts(s):
    """Euro amounts in a text, as integers (or floats) in euros."""
    out = []
    for m in EUR_RE.finditer(norm_space(s)):
        raw = m.group(0)[3:].strip()
        scale = 1
        if raw.lower().endswith("billion"):
            scale, raw = 10 ** 9, raw[:-7].strip()
        elif raw.lower().endswith("million"):
            scale, raw = 10 ** 6, raw[:-7].strip()
        raw = raw.replace(" ", "").replace(" ", "")
        if scale == 1 and re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw):
            raw = re.sub(r"[.,]", "", raw)
        v = float(raw.replace(",", ".")) * scale
        out.append(int(v) if v == int(v) else v)
    return out


def dates(s):
    return DATE_RE.findall(norm_space(s))


def other_numbers(s):
    """Numbers that are neither euro amounts nor parts of dates nor footnote-like references
    to legal acts (e.g. 'Royal Decree 853/2021', 'Annex VI')."""
    t = norm_space(s)
    t = EUR_RE.sub(" ", t)
    t = DATE_RE.sub(" ", t)
    t = re.sub(r"\b\d+/\d{4}\b|\b\d{4}/\d+\b|\(\d{4}/C\d+/\d+\)", " ", t)   # act numbers
    t = re.sub(r"\b(?:19|20)\d{2}\b", " ", t)                               # bare years
    t = re.sub(r"\b[A-Z]{1,3}\d+[a-z]?\b|\bC\d+\.[RI]\d+\b", " ", t)       # ids like L6, C2.I7, HE0
    return [n.strip().replace(" ", " ") for n in NUM_RE.findall(t)]


def word_diff(a, b):
    """[(op, old_text, new_text)] for the non-equal opcodes of a word-level diff."""
    ta, tb = tokens(a), tokens(b)
    sm = difflib.SequenceMatcher(a=ta, b=tb, autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "equal":
            out.append((op, " ".join(ta[i1:i2]), " ".join(tb[j1:j2])))
    return out


def _editorial_pair(x, y):
    """True if two word runs differ only by case, punctuation or a small spelling fix."""
    wx = [w for w in re.findall(r"\w+", x.lower())]
    wy = [w for w in re.findall(r"\w+", y.lower())]
    if wx == wy:
        return True
    if len(wx) != len(wy):
        return False
    return all(difflib.SequenceMatcher(a=p, b=q).ratio() >= 0.8 for p, q in zip(wx, wy))


def classify(old, new):
    """Classify the change between two versions of a row or text.

    old, new: dicts with any of the keys name, qual_indicator, unit, baseline, goal, quarter,
    year, description (rows) or name, description (measures); None when absent."""
    if old is None and new is None:
        return []
    if old is None:
        return ["added"]
    if new is None:
        return ["removed"]
    cats = set()
    g = lambda d, k: norm_space(d.get(k) or "")
    full_o = " ".join(g(old, k) for k in ("name", "qual_indicator", "unit", "description"))
    full_n = " ".join(g(new, k) for k in ("name", "qual_indicator", "unit", "description"))
    if sorted(map(str, eur_amounts(full_o))) != sorted(map(str, eur_amounts(full_n))):
        cats.add("amount")
    if g(old, "goal") != g(new, "goal") or g(old, "baseline") != g(new, "baseline"):
        cats.add("quantity")
    elif set(other_numbers(full_o)) != set(other_numbers(full_n)):     # a number repeated is not a new number
        cats.add("quantity")
    if g(old, "quarter") != g(new, "quarter") or g(old, "year") != g(new, "year"):
        cats.add("deadline")
    elif set(dates(full_o)) != set(dates(full_n)):
        cats.add("deadline")
    # words: strip every number, then compare
    strip = lambda s: re.sub(r"\s+", " ", NUM_RE.sub(" ", EUR_RE.sub(" EUR ", DATE_RE.sub(" ", s)))).strip()
    ops = word_diff(strip(full_o), strip(full_n))
    substantive = [o for o in ops if not _editorial_pair(o[1], o[2])]
    if substantive:
        cats.add("definition")
    raw = lambda d: re.sub(r"\s+", " ", " ".join(str(d.get(k) or "") for k in sorted(d)).replace("\xa0", " ")).strip()
    if not cats and raw(old) != raw(new):   # any other textual change, spacing included, is editorial
        cats.add("editorial")
    return sorted(cats)


def render(ops, width=None):
    """Human-readable diff: [-old-] {+new+}."""
    parts = []
    for op, a, b in ops:
        if a:
            parts.append(f"[-{a}-]")
        if b:
            parts.append(f"{{+{b}+}}")
    s = " ".join(parts)
    return s if width is None else s[:width]


if __name__ == "__main__":
    import sys
    a, b = open(sys.argv[1], encoding="utf-8").read(), open(sys.argv[2], encoding="utf-8").read()
    print(classify({"description": a}, {"description": b}))
    print(render(word_diff(a, b)))
