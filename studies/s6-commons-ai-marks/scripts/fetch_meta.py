#!/usr/bin/env python3
"""Step 2b — categories of every sampled file, reduced to the flags the analysis uses.

`fetch` (default): one API call per 50 sampled files (`prop=categories`), raw category
lists saved to work/sample_categories_full.csv (LOCAL ONLY: the raw lists contain
categories named after users, e.g. "Files uploaded by …", which are not published).
Then `derive` writes the published data/sample_categories.csv with derived flags only:

  pageid, generator, ai_evidence, ai_evidence_rule, coats_of_arms, ai_modified

This module is the single definition of those rules; analyze.py reads the flags.
Run `fetch_meta.py derive` to rebuild the flags offline from the saved raw lists.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DATA, WORK = HERE / "data", HERE / "work"
FULL = WORK / "sample_categories_full.csv"

# Generator named in the categories. First match wins; more specific before more generic.
GENERATORS = [
    ("DALL-E", r"dall[\s·\-_]?e(?![\s\-]?mini)"),
    ("OpenAI GPT-4o / gpt-image / ChatGPT", r"gpt[\s\-]?4o|gpt[\s\-]?image|chatgpt|sora|openai"),
    ("Midjourney", r"midjourney"),
    ("Stable Diffusion", r"stable[\s\-]?diffusion|sdxl|stability ai|dreamstudio"),
    ("Flux", r"\bflux\b|black forest labs"),
    ("Google (Gemini / Imagen / Nano Banana)", r"gemini|imagen|nano[\s\-]?banana|google|bard|whisk"),
    ("Adobe Firefly", r"firefly|adobe"),
    ("Microsoft (Bing Image Creator / Designer / Copilot)", r"bing|microsoft designer|copilot|microsoft"),
    ("Grok / xAI", r"grok|\bxai\b|aurora"),
    ("Ideogram", r"ideogram"),
    ("Leonardo", r"leonardo\.?ai|leonardo ai"),
    ("Craiyon / DALL-E mini", r"craiyon|dall[\s\-]?e[\s\-]?mini"),
    ("Meta AI", r"meta ai|imagine with meta"),
    ("Other named generator", r"qwen|hunyuan|kling|seedream|doubao|kolors|recraft|playground ai|"
                              r"nightcafe|artbreeder|wombo|dream by wombo|runway|krea|canva|"
                              r"perchance|deepai|starryai|lexica|mage\.space|novelai|pixai"),
]
# "AI evidence" for {{PD-algorithm}} files outside the AI category tree. It admits
# AI-generated, AI-modified (upscaled, retouched, colourised) and AI-related files
# (e.g. screenshots of AI products): see METHOD.md §3 and the breakdown in summary.md.
AI_WORD = re.compile(r"\bAI\b|\bA\.I\.")
AI_RX = re.compile(r"artificial intelligence|ai[\s\-]generated|ai[\s\-]assisted|dall[\s·\-]?e|midjourney|"
                   r"stable diffusion|chatgpt|gpt[\s\-]?4o|gpt[\s\-]image|gemini|imagen|nano banana|firefly|"
                   r"\bflux\b|grok|ideogram|craiyon|leonardo|image creator|copilot|novelai|sora\b|"
                   r"text[\s\-]to[\s\-]image|generative|neural|upscal|deep ?dream|artbreeder|nightcafe|"
                   r"wombo|thispersondoesnotexist|myheritage", re.I)
AI_MODIFIED = re.compile(r"retouch|upscal|colou?ri[sz]|modified by AI|restored|enhanced|myheritage", re.I)


def generator(cats: list[str]) -> str:
    found = [name for name, rx in GENERATORS if any(re.search(rx, c, re.I) for c in cats)]
    if not found:
        return "unspecified"
    return found[0] if len(found) == 1 else "multiple: " + " + ".join(found[:3])


def evidence_rule(cats: list[str]) -> str:
    """Which part of the rule matched: '' (none), 'AI-word only', or the first AI_RX hit."""
    s = "|".join(cats)
    m = AI_RX.search(s)
    if m:
        return m.group(0).lower()
    return "AI-word only" if AI_WORD.search(s) else ""


def derive() -> None:
    sample = {r["pageid"]: r for r in csv.DictReader(open(DATA / "sample.csv"))}
    tree = {r["category"]: r["parent"] for r in csv.DictReader(open(DATA / "category_tree.csv"))}

    def in_coa_subtree(cat: str) -> bool:
        while cat:
            if cat == "Category:AI-generated coats of arms":
                return True
            cat = tree.get(cat, "")
        return False

    rows = list(csv.DictReader(open(FULL)))
    with open(DATA / "sample_categories.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pageid", "generator", "ai_evidence", "ai_evidence_rule", "coats_of_arms", "ai_modified"])
        for r in rows:
            cs = [c for c in r["categories"].split("|") if c]
            rule = evidence_rule(cs)
            fi = sample.get(r["pageid"], {}).get("found_in", "")
            coa = in_coa_subtree(fi) or any("coats of arms" in c.lower() for c in cs)
            mod = any(AI_MODIFIED.search(c) for c in cs) or bool(AI_MODIFIED.search(fi or ""))
            w.writerow([r["pageid"], generator(cs), bool(rule), rule, coa, mod])
    print(f"derived flags for {len(rows)} files -> data/sample_categories.csv")


def fetch() -> None:
    sys.path.insert(0, str(Path(__file__).parent))
    import commons  # noqa: PLC0415

    rows = list(csv.DictReader(open(DATA / "sample.csv")))
    cats: dict[int, list[str]] = {int(r["pageid"]): [] for r in rows}
    ids = list(cats)
    for i in range(0, len(ids), 50):
        for d in commons.query_all({"pageids": "|".join(map(str, ids[i:i + 50])),
                                    "prop": "categories", "cllimit": "max"}):
            for p in (d.get("query") or {}).get("pages", []):
                for c in p.get("categories", []) or []:
                    cats[p["pageid"]].append(c["title"].removeprefix("Category:"))
    WORK.mkdir(exist_ok=True)
    with open(FULL, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pageid", "categories"])
        for pid in ids:
            w.writerow([pid, "|".join(sorted(set(cats[pid])))])
    print("fetched", commons.REQUESTS)


if __name__ == "__main__":
    if "derive" not in sys.argv:
        fetch()
    derive()
