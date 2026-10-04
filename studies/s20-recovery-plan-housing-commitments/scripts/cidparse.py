"""Parser for the annexes of Council Implementing Decisions (CID) on recovery and resilience
plans, as published in Cellar in XHTML (converted from Word by the Commission).

Three things are read from an annex:
  * milestone and target rows: every table row whose first cell is a milestone/target number and
    whose second cell is a measure id (C2.I2, C2.R3...);
  * measure descriptions: the paragraphs from "Investment 2 (C2.I2) – <name>" (or "Reform 3
    (C2.R3) – ...") to the next measure heading or section heading;
  * money sentences in descriptions ("EUR 4 000 000 000").

Standard library only. The text of a cell is normalised: tags removed, entities decoded,
whitespace collapsed, soft hyphen and zero-width characters dropped. Nothing else is changed,
so quotations stay literal.
"""
import html, re
from html.parser import HTMLParser

ZW = dict.fromkeys(map(ord, "­​‌‍﻿"), None)


def norm(s):
    s = html.unescape(s).translate(ZW).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


class _Tables(HTMLParser):
    """Collect every table as a list of rows; each row a list of cell texts. Nested tables
    are flattened into the cell of the outer table (they are rare in these annexes)."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.tables, self.stack = [], []   # stack of [rows, current_row, current_cell, depth]
        self.in_cell = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.stack.append([[], None, None])
        elif not self.stack:
            return
        elif tag == "tr":
            self.stack[-1][1] = []
        elif tag in ("td", "th"):
            self.stack[-1][2] = []
        elif tag in ("p", "br", "li", "div") and self.stack[-1][2] is not None:
            self.stack[-1][2].append(" ")

    def handle_endtag(self, tag):
        if not self.stack:
            return
        t = self.stack[-1]
        if tag in ("td", "th") and t[2] is not None:
            if t[1] is None:
                t[1] = []
            t[1].append(norm("".join(t[2])))
            t[2] = None
        elif tag == "tr" and t[1] is not None:
            t[0].append(t[1])
            t[1] = None
        elif tag == "table":
            rows = self.stack.pop()[0]
            self.tables.append(rows)
            if self.stack and self.stack[-1][2] is not None:   # nested: flatten into outer cell
                self.stack[-1][2].append(" " + " ".join(" ".join(r) for r in rows) + " ")

    def handle_data(self, d):
        if self.stack and self.stack[-1][2] is not None:
            self.stack[-1][2].append(d)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")


FOOTREF_RE = re.compile(r'<span class="FootnoteReference">.*?</span>', re.S)


def strip_footnote_refs(xhtml):
    """Footnote call-outs (superscript numbers linking to a footnote) are not part of the text."""
    return FOOTREF_RE.sub("", xhtml)


def tables(xhtml):
    p = _Tables()
    p.feed(strip_footnote_refs(xhtml))
    p.close()
    return p.tables


MEASURE_RE = re.compile(r"^C\d{1,2}\.\s?[RI]\s?\d{1,2}(?:\.\d+)?$")
NUMBER_RE = re.compile(r"^(?:L\s?)?\d{1,4}(?:\s?[a-z])?$")


def clean_measure(s):
    return re.sub(r"\s+", "", s)


def mt_rows(xhtml):
    """Milestone/target rows. Returns dicts with the raw cells and a best-effort split.

    The CID tables have 10 columns after the header rows: number, related measure, M/T,
    name, qualitative indicator, unit, baseline, goal, quarter, year, description. Some rows
    drop or merge cells; we keep the raw cells and fill the fields only when the row has the
    expected 11 cells (or 10, without a qualitative-indicator cell)."""
    out = []
    for ti, t in enumerate(tables(xhtml)):
        for ri, row in enumerate(t):
            cells = [c for c in row]
            if len(cells) < 6:
                continue
            num, meas = cells[0], clean_measure(cells[1])
            if not NUMBER_RE.match(num) or not MEASURE_RE.match(meas):
                continue
            rec = {"table": ti, "row": ri, "number": num.replace(" ", ""), "measure": meas,
                   "cells": cells}
            if len(cells) == 11:
                keys = ["number", "measure", "type", "name", "qual_indicator", "unit", "baseline",
                        "goal", "quarter", "year", "description"]
                for k, v in zip(keys[2:], cells[2:]):
                    rec[k] = v
            out.append(rec)
    return out


def plain_text(xhtml):
    """Text as a browser would render it: block elements end a line, table cells are
    separated by a space, inline tags (span, a) are removed without adding spaces (the
    Commission's XHTML splits words across spans), footnote call-outs are dropped."""
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", xhtml, flags=re.S | re.I)
    s = strip_footnote_refs(s)
    s = re.sub(r"\s+", " ", s)                       # source line breaks are spaces in HTML
    s = re.sub(r"<br\s*/?>|</?(?:p|h\d|li|div|tr|table|dl|dd|dt)\b[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"</t[dh]>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).translate(ZW).replace("\xa0", " ")
    s = re.sub(r"[ \t\r]+", " ", s)
    return "\n".join(x.strip() for x in s.split("\n") if x.strip())


HEAD_RE = re.compile(r"^(Investment|Reform|Sub-investment|Subinvestment)\s+\d+[a-z]?\s*\((C\s?\d{1,2}\s?\.\s?[RI]\s?\d{1,2}(?:\.\d+)?)\)\s*[–\-:]\s*(.+)$")
STOP_RE = re.compile(r"^([A-Z]{1,2}\.\d+\.|[A-Z]{1,2}\. COMPONENT|[A-Z]{1,2}\. Component|Investment\s+\d|Reform\s+\d|Sub-investment\s+\d)")


def descriptions(xhtml):
    """{measure id: (heading name, description text)} for every measure heading in the annex.
    A measure can appear twice (grant part and loan part); both texts are kept, joined."""
    lines = plain_text(xhtml).split("\n")
    out = {}
    i = 0
    while i < len(lines):
        m = HEAD_RE.match(lines[i])
        if not m:
            i += 1
            continue
        mid = clean_measure(m.group(2))
        name = m.group(3).strip()
        body = []
        j = i + 1
        while j < len(lines) and not STOP_RE.match(lines[j]):
            body.append(lines[j])
            j += 1
        prev = out.get(mid)
        text = " ".join(body)
        out[mid] = (name, text) if not prev else (prev[0], prev[1] + " || " + text)
        i = j
    return out


EUR_RE = re.compile(r"EUR\s?(\d{1,3}(?:[   .,]\d{3})+|\d+(?:[.,]\d+)?)\s*(billion|million)?", re.I)


def eur_amounts(text):
    """Every 'EUR <amount>' in a text, as floats in euros, with the matched string."""
    out = []
    for m in EUR_RE.finditer(text):
        raw, scale = m.group(1), (m.group(2) or "").lower()
        digits = re.sub(r"[   ]", "", raw)
        if scale:
            v = float(digits.replace(",", "."))
            v *= 1e9 if scale == "billion" else 1e6
        else:
            if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", digits):
                digits = re.sub(r"[.,]", "", digits)
            v = float(digits.replace(",", "."))
        out.append((v, m.group(0)))
    return out
