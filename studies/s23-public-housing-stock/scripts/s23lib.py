"""Shared helpers for S23: plain text of BOE consolidated XML, PDF and HTML sources."""
import os, re, subprocess, html, gzip
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(HERE, "data", "raw")
DATA = os.path.join(HERE, "data")


def norm(s):
    """Collapse whitespace (incl. no-break spaces) to single spaces."""
    return re.sub(r"[\s  ]+", " ", s).strip()


def boe_blocks(path):
    """{block id: [(id_norma, fecha_vigencia, title, text), ...]} from a BOE consolidated XML."""
    t = ET.parse(path).getroot()
    out = {}
    for b in t.iter("bloque"):
        vs = []
        for v in b.findall("version"):
            paras = [norm("".join(p.itertext())) for p in v.iter("p")]
            vs.append((v.get("id_norma"), v.get("fecha_vigencia"), b.get("titulo"), "\n".join(x for x in paras if x)))
        out[b.get("id")] = vs
    return out


def boe_current(path, block):
    """Text of the latest version of one block."""
    return boe_blocks(path)[block][-1][3]


def pdf_text(path, layout=False):
    args = ["pdftotext", "-enc", "UTF-8"] + (["-layout"] if layout else []) + [path, "-"]
    return subprocess.run(args, capture_output=True, check=True).stdout.decode("utf-8", "replace")


def html_text(path):
    b = open(path, "rb").read()
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    s = b.decode("utf-8", "replace")
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</h\d>|</li>|</div>|</tr>|</td>|</th>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t ]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s)


def flat(s):
    """Whitespace-collapsed text, soft hyphens removed, typographic quotes kept."""
    s = s.replace("­", "")
    return norm(s)


_TEXT = {}


def source_text(rel):
    """Whitespace-normalised plain text of a raw source (path relative to data/raw/), for
    checking literal quotations. PDFs are read in both reading-order and layout modes; a
    quotation counts as found if it occurs in either. Line-end hyphenation is not repaired:
    quotations are chosen so that they do not straddle a hyphenated line break."""
    if rel in _TEXT:
        return _TEXT[rel]
    p = os.path.join(RAW, rel)
    if os.path.isdir(p):                       # a Cellar work: every DOC_n.xhtml
        import glob
        t = " ".join(html_text(f) for f in sorted(glob.glob(os.path.join(p, "DOC_*.xhtml"))))
        out = [t]
    elif p.endswith(".pdf"):
        out = [pdf_text(p), pdf_text(p, layout=True)]
    elif p.endswith(".xml") and "/boe/" in p:
        blocks = boe_blocks(p)
        out = ["\n".join(v[3] for vs in blocks.values() for v in vs)]
    elif p.endswith((".html", ".xhtml", ".htm")):
        out = [html_text(p)]
    else:
        out = [open(p, encoding="utf-8-sig", errors="replace").read()]
    _TEXT[rel] = [qnorm(x) for x in out]
    return _TEXT[rel]


def qnorm(s):
    """Normalisation used for quotation checks: soft hyphens and ligatures out, typographic
    quotes and dashes unified, whitespace collapsed."""
    s = s.replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return norm(s)


def quote_found(quote, rel):
    q = qnorm(quote)
    return any(q in t for t in source_text(rel))
