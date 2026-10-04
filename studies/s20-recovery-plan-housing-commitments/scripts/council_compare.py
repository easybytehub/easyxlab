#!/usr/bin/env python3
"""Compare the housing texts of each Commission proposal with the Council's text of the same
version (the ST document prepared for adoption, English PDF from Cellar).

pdftotext (poppler) does not keep the cells of a table row together: on some pages it emits
the description column first and the number, measure and goal columns later. So we compare
field by field, each as a contiguous token run, not row by row:
  * the description of each milestone/target and of each measure, and the component-2
    summary sentence: aligned in order from an anchor (their first tokens);
  * the name of each milestone/target: searched as a contiguous run;
  * the goal of each target: searched as a run (e.g. "15 718").
Both texts are reduced to lower-case alphanumeric tokens, hyphens dropped (pdftotext rejoins
words split at line ends); the Council page footers and repeated table headers are removed.
Output: data/council_vs_proposal.csv, one line per version x item, with the share of tokens
found in order and the differing runs.
"""
import csv, difflib, re, subprocess
from s20lib import DATA, RAW, WORK, VERSIONS

ANNEX = {  # version -> Council document holding the annex as prepared for adoption
    "v0-2021": "ST_10150_2021_ADD_1_REV_2", "v1-2023": "ST_13695_2023_ADD_1_REV_1",
    "v2-2024a": "ST_9303_2024_ADD_1", "v3-2024b": "ST_17099_2024_ADD_1",
    "v4-2025a": "ST_8053_2025_ADD_1", "v5-2025b": "ST_9583_2025_ADD_1",
    "v6-2025c": "ST_13075_2025_ADD_1", "v8-2026a": "ST_9518_2026_ADD_1",
    "v9-2026b": "ST_12355_2026_ADD_1",
}
FOOTER = re.compile(r"\n\d{4,5}/\d{2}(?: ADD \d+)?(?: REV \d+)?(?: COR \d+)?\s*\n(?:\s*\d+\s*\n)?"
                    r"(?:\s*[A-Za-z]{2,4}/[a-z]{1,4}\s*\n)?\s*(?:ECOMP|ECOFIN)[ .0-9A-Z]*\n\s*EN\s*\n")
HEADER = ("number measure milestone target name qualitative indicator for milestones quantitative "
          "indicator for target unit baseline goal time description of each milestone and target q year").split()


def pdf_text(doc):
    out = WORK / "council_txt" / f"{doc}.txt"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["pdftotext", "-enc", "UTF-8", str(RAW / "council" / doc / "DOC_1.pdf"), str(out)],
                       check=True, timeout=240)
    return out.read_text(encoding="utf-8")


def ntok(s):
    s = (s or "").lower().replace("\xad", "").replace("-", "").replace("‐", "").replace("’", "'")
    toks = re.findall(r"[a-z0-9]+", s)
    # a footnote call-out printed against the word in the PDF ("use5"): drop the digits
    return [re.sub(r"^([a-z]{3,})\d{1,3}$", r"\1", t) for t in toks]


def subseq_in_window(seq, sub, slack=3):
    """True if sub occurs in order (not necessarily contiguous) inside a window of
    slack*len(sub) tokens: pdftotext interleaves the lines of neighbouring narrow cells."""
    n = len(sub)
    for s in find_all(seq, sub[:2] if n > 1 else sub, 2000):
        j = 0
        for t in seq[s: s + slack * n + 5]:
            if t == sub[j]:
                j += 1
                if j == n:
                    return True
    return False


def council_tokens(doc):
    t = ntok(FOOTER.sub("\n", pdf_text(doc)))
    # drop the table header repeated on every page (pdftotext may split it, so drop the
    # longest run that matches its start)
    out, i, h = [], 0, len(HEADER)
    while i < len(t):
        if t[i] == HEADER[0] and t[i:i + 4] == HEADER[:4]:
            k = 0
            while k < h and i + k < len(t) and t[i + k] == HEADER[k]:
                k += 1
            i += k
            continue
        out.append(t[i]); i += 1
    return out


def find_all(seq, sub, limit=300):
    n = len(sub)
    if not n:
        return []
    first = sub[0]
    return [i for i in range(len(seq) - n + 1) if seq[i] == first and seq[i:i + n] == sub][:limit]


def align(prop, council):
    """Ordered alignment of prop against the council tokens, anchored on prop's first tokens
    (or later ones if the first are not found). Returns (coverage, differing runs)."""
    if not prop:
        return 1.0, []
    best = (0.0, [])
    for off in (0, 8, 16, 32):
        anchor = prop[off: off + 8]
        if len(anchor) < min(8, len(prop)):
            break
        for s in find_all(council, anchor, 50):
            s0 = max(0, s - off - 5)
            win = council[s0: s0 + int(len(prop) * 1.5) + off + 300]
            sm = difflib.SequenceMatcher(a=prop, b=win, autojunk=False)
            m = sum(b.size for b in sm.get_matching_blocks())
            cov = m / len(prop)
            if cov > best[0]:
                ops = [(op, " ".join(prop[i1:i2]), " ".join(win[j1:j2]))
                       for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
                # leading/trailing insertions are just the neighbouring text in the Council document
                while ops and ops[0][0] == "insert":
                    ops.pop(0)
                while ops and ops[-1][0] == "insert":
                    ops.pop()
                best = (cov, ops)
        if best[0] == 1.0:
            break
    return best


def verdict(cov, ops):
    """yes: every token found in order, nothing else; insertions-only: the Council text has
    extra runs inside the item (page footers, footnote texts printed at the foot of the page);
    no: some proposal token is missing or replaced."""
    if cov == 1.0 and not ops:
        return "yes"
    if cov == 1.0 and all(op == "insert" for op, a, b in ops):
        return "insertions-only"
    return "no"


def fmt(ops):
    return " | ".join(f"{op}: «{a}» → «{b}»" for op, a, b in ops)[:1500]


def main():
    rows = list(csv.DictReader(open(DATA / "housing_rows.csv", encoding="utf-8")))
    meas = list(csv.DictReader(open(DATA / "housing_measures.csv", encoding="utf-8")))
    out = []
    for label, celex, com, date in VERSIONS:
        doc = ANNEX.get(label)
        if not doc:
            out.append({"version": label, "council_doc": "", "item": "*", "field": "",
                        "coverage": "", "n_tokens": "", "identical": "",
                        "differences": "no Council text of this version in Cellar"})
            continue
        ct = council_tokens(doc)
        for r in [x for x in rows if x["version"] == label]:
            item = f"{r['measure']} {r['number']}"
            for field in ("name", "goal", "description"):
                prop = ntok(r[field])
                if not prop:
                    continue
                if field == "description":
                    cov, ops = align(prop, ct)
                else:
                    cov, ops = (1.0, []) if subseq_in_window(ct, prop) else (0.0, [("missing", r[field], "")])
                out.append({"version": label, "council_doc": doc, "item": item, "field": field,
                            "coverage": f"{cov:.4f}", "n_tokens": len(prop),
                            "identical": verdict(cov, ops), "differences": fmt(ops)})
        for m in [x for x in meas if x["version"] == label]:
            prop = ntok(m["description"])
            cov, ops = align(prop, ct)
            out.append({"version": label, "council_doc": doc, "item": m["measure"], "field": "description",
                        "coverage": f"{cov:.4f}", "n_tokens": len(prop),
                        "identical": verdict(cov, ops), "differences": fmt(ops)})
        print(label, doc, flush=True)
    with open(DATA / "council_vs_proposal.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)


if __name__ == "__main__":
    main()
