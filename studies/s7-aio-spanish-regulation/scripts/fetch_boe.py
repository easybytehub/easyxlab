#!/usr/bin/env python3
"""Download BOE texts (diario or consolidated) as plain text into data/raw/boe/<id>.txt.

Usage: fetch_boe.py BOE-A-2026-3815 [BOE-A-2015-11430:con ...] | fetch_boe.py --from-facts
  suffix ':con' = consolidated text via the BOE open-data API (legislacion-consolidada/id/<id>/texto)
  otherwise     = text as published in the Diario (diario_boe/txt.php?id=<id>)
Stdlib only. Polite: one request at a time, 1 s apart.
"""
import html, re, sys, time, urllib.request
from pathlib import Path
OUT = Path(__file__).resolve().parent.parent / "data/raw/boe"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "EasyxLab-S7/0.1 (research; contact via github.com/easybytehub)", "Accept": "application/xml,text/html"}
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read().decode("utf-8", "replace")
def plain(s):
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</tr>|</li>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s)
ARGS = sys.argv[1:]
if ARGS == ["--from-facts"]:          # every reference used in data/facts.json (current and superseded rule)
    import json
    facts = json.load(open(Path(__file__).resolve().parent.parent / "data/facts.json", encoding="utf-8"))
    ARGS = sorted({r["boe_id"] + (":con" if r["consolidated"] else "") for f in facts for r in f["boe"] + f["boe_old"]})
for arg in ARGS:
    ident, _, mode = arg.partition(":")
    f = OUT / (ident + ("-con" if mode == "con" else "") + ".txt")
    if f.exists() and f.stat().st_size > 1000:
        print("cached", f.name); continue
    url = (f"https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/{ident}/texto" if mode == "con"
           else f"https://www.boe.es/diario_boe/txt.php?id={ident}")
    try:
        t = plain(get(url))
        f.write_text(f"SOURCE: {url}\nRETRIEVED: {time.strftime('%Y-%m-%d %H:%M')}\n\n" + t, encoding="utf-8")
        print("ok", f.name, len(t))
    except Exception as e:
        print("ERR", ident, e)
    time.sleep(1)
