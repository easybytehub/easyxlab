"""Shared helpers for S20: paths, the version list, Cellar SPARQL through the polite fetcher."""
import csv, json, os, re, sys, urllib.parse
from pathlib import Path

R = Path(__file__).resolve().parent.parent
RAW = R / "data" / "raw"
DATA = R / "data"
WORK = R / "work"
sys.path.insert(0, str(R / "scripts"))

SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
CELLAR = "http://publications.europa.eu/resource"

# Every Commission proposal for a Council Implementing Decision (CID) approving or amending the
# assessment of Spain's recovery and resilience plan found in Cellar on 2026-10-04 (SPARQL in
# fetch.py). "v" is our version label; "adopted" is filled from the evidence in data/adoption.csv.
VERSIONS = [
    # label, CELEX of the proposal, COM reference, date of the proposal
    ("v0-2021", "52021PC0322", "COM(2021) 322", "2021-06-16"),
    ("v1-2023", "52023PC0576", "COM(2023) 576", "2023-10-02"),
    ("v2-2024a", "52024PC0185", "COM(2024) 185", "2024-04-22"),
    ("v3-2024b", "52024PC0592", "COM(2024) 592", "2024-12-18"),
    ("v4-2025a", "52025PC0177", "COM(2025) 177", "2025-04-11"),
    ("v5-2025b", "52025PC0271", "COM(2025) 271", "2025-05-26"),
    ("v6-2025c", "52025PC0556", "COM(2025) 556", "2025-09-19"),
    ("v7-2025d", "52025PC0794", "COM(2025) 794", "2025-12-17"),
    ("v8-2026a", "52026PC0257", "COM(2026) 257", "2026-05-20"),
    ("v9-2026b", "52026PC0435", "COM(2026) 435", "2026-08-07"),
]


def sparql_url(query):
    return SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "text/csv"})


def fetch(url, out, accept=None, extra=None, refetch=False):
    """Polite download (robots.txt, <=1 req/s/host, fixed UA, logged). Skips existing files."""
    import polite
    out = str(out)
    if os.path.exists(out) and not refetch:
        return 200, url
    return polite.fetch(url, out, accept, extra=extra)


def sparql(query, out, refetch=False):
    st, _ = fetch(sparql_url(query), out, accept="text/csv", refetch=refetch)
    if st != 200:
        raise RuntimeError(f"SPARQL HTTP {st}")
    return list(csv.DictReader(open(out, encoding="utf-8")))


def manifestations(branch_xml):
    """From a Cellar branch notice: {manifestation type: [item URLs]} for the expression."""
    s = open(branch_xml, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"<MANIFESTATION\b.*?</MANIFESTATION>", s, flags=re.S):
        b = m.group(0)
        t = re.search(r"<MANIFESTATION_TYPE[^>]*>.*?<VALUE>([^<]*)", b, flags=re.S)
        items = sorted(set(re.findall(r"http://publications\.europa\.eu/resource/cellar/[0-9a-f-]+\.\d+\.\d+/DOC_\d+", b)))
        if t and items:
            out.setdefault(t.group(1), [])
            for i in items:
                if i not in out[t.group(1)]:
                    out[t.group(1)].append(i)
    return out


def read_xhtml(path):
    """Text of an XHTML item, or None if Cellar served something else (the 2021 proposal's
    DOC_2 and DOC_4 are scanned JPEG pages)."""
    b = open(path, "rb").read()
    if not b.lstrip()[:1] == b"<":
        return None
    return b.decode("utf-8")


def version_docs(celex):
    """[(doc name, xhtml text)] for one proposal, XML items only, in DOC order."""
    import glob
    out = []
    for f in sorted(glob.glob(str(RAW / "cellar" / celex / "DOC_*.xhtml")), key=lambda p: int(re.search(r"DOC_(\d+)", p).group(1))):
        t = read_xhtml(f)
        if t is not None:
            out.append((os.path.basename(f).split(".")[0], t))
    return out
