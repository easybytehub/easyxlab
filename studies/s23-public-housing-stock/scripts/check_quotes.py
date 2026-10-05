#!/usr/bin/env python3
"""S23: check that every «quotation» in README.md and paper.md (when present), and every
block quotation (lines starting with '>') in paper.md, occurs literally in a downloaded source
text (data/raw/, after whitespace normalisation). Single search terms listed in TERMS are
exempt. Exit 1 if a quotation is not found."""
import glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s23lib import RAW, source_text, qnorm

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERMS = {"memoria", "inventario", "Cesión", "Anualmente", "78.588", "9 %", "9%", "quotation"}
SKIP = re.compile(r"(sumarios\.jsonl\.gz|\.xlsx|sitemap|\.http\d+$|/cat_|/catalogues/|/regions/|post-sitemap|page-sitemap)")


def sources():
    out = []
    for p in sorted(glob.glob(os.path.join(RAW, "**", "*"), recursive=True)):
        rel = os.path.relpath(p, RAW)
        if os.path.isdir(p):
            if glob.glob(os.path.join(p, "DOC_*.xhtml")):
                out.append(rel)
            continue
        if SKIP.search(rel) and not rel.endswith("http403.html"):
            continue
        if rel.split("/")[0] == "eu" and "/DOC_" in rel:
            continue
        if rel.endswith((".pdf", ".xml", ".html", ".xhtml", ".csv", ".json", ".htm")):
            out.append(rel)
    return out


def quotes(path):
    t = open(path, encoding="utf-8").read()
    qs = [q for q in re.findall(r"«([^»]+)»", t)]
    if path.endswith("paper.md"):
        blocks, cur = [], []
        for line in t.splitlines():
            if line.startswith(">"):
                x = line[1:].strip()
                if x:
                    cur.append(x)
                elif cur:
                    blocks.append(" ".join(cur)); cur = []
            elif cur:
                blocks.append(" ".join(cur)); cur = []
        if cur:
            blocks.append(" ".join(cur))
        qs += [re.sub(r"^\d+\. ", "", b) for b in blocks]
    return qs


def main():
    srcs = sources()
    texts = []
    for s in srcs:
        try:
            texts += source_text(s)
        except Exception as e:
            print("cannot read", s, e)
    bad, n = [], 0
    for doc in ("README.md", "paper.md"):
        p = os.path.join(R, doc)
        if not os.path.exists(p):
            print(f"{doc} not present: skipped")
            continue
        for q in quotes(p):
            if q in TERMS:
                continue
            n += 1
            qq = qnorm(q)
            if not any(qq in t for t in texts):
                bad.append(f"{doc}: «{q[:90]}»")
    print(f"{n} quotations checked against {len(srcs)} source files; {len(bad)} not found")
    for b in bad:
        print(" -", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
