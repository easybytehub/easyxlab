#!/usr/bin/env python3
"""Check that every quotation in paper.md and README.md is literal.

Quotations are text in «…» (paper and README) and, in the README, also text in straight
double quotes "…" of three words or more. Each quotation is split at «…» and at editorial
insertions in square brackets; every fragment of three words or more must occur in one of the
downloaded source texts, after collapsing whitespace:
  * Commission proposals, staff working documents and EU frame texts (data/raw/cellar, frame);
  * Council PDFs (data/raw/council, others), converted with pdftotext;
  * Spanish Government pages (data/raw/prtr);
  * prior-work documents: ECA reports (PDF), press pages and news-feed headlines
    (data/raw/prior).
Everything is read from data/raw/, so the check runs offline after `run.sh fetch`; it is
skipped with a message if data/raw/ is absent. Exit 1 if a fragment is not found.
"""
import glob, re, subprocess, sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "scripts"))
RAW = R / "data" / "raw"
CACHE = R / "work" / "quote_corpus"
MIN_WORDS = 3


def norm(s):
    s = s.replace("\xa0", " ").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"(\d)\s+%", r"\1%", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def pdf(path):
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / (re.sub(r"[^A-Za-z0-9]+", "_", str(Path(path).relative_to(RAW))) + ".txt")
    if not out.exists():
        subprocess.run(["pdftotext", "-enc", "UTF-8", str(path), str(out)], check=True, timeout=240)
    return out.read_text(encoding="utf-8", errors="replace")


def corpus():
    from cidparse import plain_text
    texts = []
    for f in glob.glob(str(RAW / "cellar" / "*" / "DOC_*.xhtml")) + glob.glob(str(RAW / "frame" / "*" / "DOC_*.xhtml")):
        b = open(f, "rb").read()
        if b.lstrip().startswith(b"<"):
            texts.append(plain_text(b.decode("utf-8")))
    for f in glob.glob(str(RAW / "prtr" / "*.html")) + glob.glob(str(RAW / "prior" / "**" / "*.html"), recursive=True):
        texts.append(plain_text(open(f, encoding="utf-8", errors="replace").read()))
    import html as H
    for f in glob.glob(str(RAW / "prior" / "bingnews_*.xml")):     # news-feed headlines
        texts.append(H.unescape(open(f, encoding="utf-8", errors="replace").read()))
    for f in (glob.glob(str(RAW / "council" / "*" / "*.pdf")) + glob.glob(str(RAW / "others" / "*" / "*.pdf"))
              + glob.glob(str(RAW / "prior" / "*.pdf"))):
        texts.append(pdf(f))
    return norm(" \n ".join(texts))


def quotations(doc, text):
    text = re.sub(r"(?m)^>\s?", "", text)                  # blockquote markers
    text = re.sub(r"`[^`]*`", " ", text)                    # code spans are not quotations
    text = re.sub(r"\s+", " ", text)
    qs = re.findall(r"«([^»]+)»", text)
    if doc == "README.md":
        qs += re.findall(r'"([^"]+)"', text)
    return qs


def main():
    if not RAW.exists():
        print("data/raw/ is absent: quotations not checked (run scripts/run.sh fetch)")
        return 0
    big = corpus()
    bad, n = [], {}
    for doc in ("paper.md", "README.md"):
        p = R / doc
        if not p.exists():
            continue
        n[doc] = 0
        for q in quotations(doc, p.read_text(encoding="utf-8")):
            for frag in re.split(r"…|\[[^\]]*\]", q):
                frag = frag.strip(" ,.;:")
                if len(frag.split()) < MIN_WORDS:
                    continue
                n[doc] += 1
                if norm(frag) not in big:
                    bad.append(f"{doc}: «{frag[:120]}»")
    print("quotation fragments checked:", n)
    for b in bad:
        print("NOT FOUND", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
