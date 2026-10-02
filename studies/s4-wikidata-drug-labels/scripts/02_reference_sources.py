#!/usr/bin/env python3
"""Step 2 - external reference lists used by the detectors.

1. RxNorm Prescribable subset (public domain, no UMLS licence needed), via RxNav:
   brand names (tty=BN) and ingredient names (IN, PIN, MIN). Ingredient names are used
   to *exclude* brand names that coincide with a generic name (precision guard).
2. DrugBank Open Data Vocabulary (CC0): attempted; the download endpoint answers HTTP 403
   without an account (checked 2026-10-02), so it is recorded as unavailable.
3. WHO ATC alterations list (cumulative): only the (previous code, substance, new code, year,
   note) facts needed to flag obsolete codes. Used for checking, not redistributed beyond the
   codes that appear in our flags (the ATC/DDD index itself may not be redistributed).
Outputs: data/reference/rxnorm_prescribable.json, data/reference/atc_alterations_codes.json,
         data/reference/sources_meta.json
"""
import json, os, re, sys, time, html, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(__file__))
from wd import UA

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "reference")
os.makedirs(OUT, exist_ok=True)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.status, r.read()


meta = {"retrieved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

# 1. RxNorm Prescribable
rx = {}
for tty in ("BN", "IN", "PIN", "MIN"):
    url = f"https://rxnav.nlm.nih.gov/REST/Prescribe/allconcepts.json?tty={tty}"
    st, body = get(url)
    rx[tty] = sorted({c["name"] for c in json.loads(body)["minConceptGroup"]["minConcept"]})
    meta[f"rxnorm_{tty}"] = {"url": url, "n": len(rx[tty])}
    time.sleep(1)
json.dump(rx, open(os.path.join(OUT, "rxnorm_prescribable.json"), "w"), ensure_ascii=False)

# 2. DrugBank vocabulary
url = "https://go.drugbank.com/releases/latest/downloads/all-drugbank-vocabulary"
try:
    st, _ = get(url)
    meta["drugbank_vocabulary"] = {"url": url, "status": st, "used": False,
                                   "note": "downloaded but not parsed in this version"}
except urllib.error.HTTPError as e:
    meta["drugbank_vocabulary"] = {"url": url, "status": e.code, "used": False,
                                   "note": "not downloadable without registration"}

# 3. ATC alterations
url = "https://atcddd.fhi.no/atc_ddd_alterations__cumulative/atc_alterations/"
st, body = get(url)
t = body.decode("utf-8", "replace")
notes = {m.group(1): html.unescape(re.sub(r"\s+", " ", m.group(2))).strip()
         for m in re.finditer(r'href="#n(\d+)_\d+" title="([^"]*)"', t)}
rows = []
for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
    tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
    if len(tds) != 4:
        continue
    note_m = re.search(r'title="([^"]*)"', tds[0])
    clean = [html.unescape(re.sub(r"<[^>]+>", "", x)).replace("\xa0", " ").strip() for x in tds]
    prev = re.match(r"[A-Z][0-9A-Z]*", clean[0])
    if not prev:
        continue
    rows.append({"previous": prev.group(0), "substance": clean[1], "new": clean[2].split()[0] if clean[2] else "",
                 "year": clean[3], "note": html.unescape(note_m.group(1)).strip() if note_m else ""})
json.dump(rows, open(os.path.join(OUT, "atc_alterations_codes.json"), "w"), ensure_ascii=False, indent=0)
meta["atc_alterations"] = {"url": url, "n_rows": len(rows)}
json.dump(meta, open(os.path.join(OUT, "sources_meta.json"), "w"), indent=2)
print(json.dumps(meta, indent=2))
