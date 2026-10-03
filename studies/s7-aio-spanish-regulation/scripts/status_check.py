#!/usr/bin/env python3
"""Status of every fact's BOE sources as in force on the reading day (2026-10-02).

For each primary BOE id: the document page (boe.es/buscar/doc.php?id=…) lists the BOE's own "Referencias
posteriores" (later amendments, repeals, annulments by court rulings, validations of decree-laws) and the
"Fecha de derogación". We keep every later reference published from 2025 onwards. We also list every item of
the BOE issues of 2026-10-02 and 2026-10-03 (ordinary and extraordinary) and the Last-Modified time of each
issue's PDF, to date what was in the BOE at each reading. Output: data/fact_status.json (+ raw pages in
data/raw/boe/doc/). Stdlib only."""
import html, json, re, sys, time, urllib.request
from pathlib import Path
R = Path(__file__).resolve().parent.parent
OUT = R / "data/raw/boe/doc"; OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "EasyxLab-S7/0.2 (research; https://github.com/easybytehub/easyxlab)"}
SOURCES = {  # fact ids -> primary BOE ids whose later references are checked
 "F01": ["BOE-A-2026-3815"], "F02 F03 F04 F05": ["BOE-A-2015-11430"], "F06 F07 F08 F14": ["BOE-A-2026-7296"],
 "F09 F10 F11 F12": ["BOE-A-2026-2548"], "F13": ["BOE-A-2015-11724"], "F15": ["BOE-A-2024-26931"],
 "F16": ["BOE-A-2026-6545", "BOE-A-2026-20266"], "F17": ["BOE-A-2026-8872"], "F18 F19": ["BOE-A-2025-76"],
 "F20 F21 F22": ["BOE-A-2025-26698", "BOE-A-2007-20555"], "F23": ["BOE-A-2021-4194"], "F24": ["BOE-A-2025-15424"],
 "F25": ["BOE-A-2025-24545"], "F26 F27": ["BOE-A-2023-24840", "BOE-A-2025-24446"], "F28": ["BOE-A-2026-7295"]}
def get(url, head=False):
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/json" if "datosabiertos" in url else "text/html"},
                                 method="HEAD" if head else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return (dict(r.headers) if head else r.read().decode("utf-8", "replace"))
def plain(s):
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s); s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s))
res = {"retrieved_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()), "sources": {}, "issues": {}}
for facts, ids in SOURCES.items():
    for i in ids:
        f = OUT / f"{i}.txt"
        t = f.read_text() if f.exists() else plain(get(f"https://www.boe.es/buscar/doc.php?id={i}"))
        f.write_text(t); time.sleep(1)
        derog = re.search(r"Fecha de derogación:\s*([\d/]+)", t)
        post = t.split("Referencias posteriores", 1)[1].split("Referencias anteriores", 1)[0] if "Referencias posteriores" in t else ""
        items = [x.strip() for x in re.split(r"(?=\b(?:SE [A-ZÁÉÍÓÚ]+|CORRECCIÓN|Se [a-z]+)\b)", post) if re.search(r"BOE-A-202[56]-\d+", x)]
        res["sources"][i] = {"facts": facts.split(), "derogation_date": derog.group(1) if derog else None,
                             "derogada_header": "[Disposición derogada]" in t, "later_refs_2025_2026": items}
for day in ("20261002", "20261003"):
    try:
        d = json.loads(get(f"https://www.boe.es/datosabiertos/api/boe/sumario/{day}"))["data"]["sumario"]
    except Exception as e:
        res["issues"][day] = {"error": f"{type(e).__name__}: {e} (issue not available at retrieval time)"}
        continue
    for diario in d["diario"] if isinstance(d["diario"], list) else [d["diario"]]:
        num = diario.get("numero"); pdf = (diario.get("sumario_diario") or {}).get("url_pdf", {})
        pdf = pdf.get("texto") if isinstance(pdf, dict) else pdf
        lm = None
        try: lm = get(pdf, head=True).get("Last-Modified") if pdf else None
        except Exception as e: lm = f"ERR {e}"
        titles = []
        def walk(o):
            if isinstance(o, dict):
                if "identificador" in o and "titulo" in o: titles.append(f"{o['identificador']} {o['titulo'][:230]}")
                for v in o.values(): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(diario)
        res["issues"][f"{day}-{num}"] = {"pdf": pdf, "last_modified": lm, "n_items": len(titles), "items": titles}
(R / "data/fact_status.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
for i, v in res["sources"].items():
    print(f"== {i} {v['facts']} derog={v['derogation_date']} hdr={v['derogada_header']}")
    for x in v["later_refs_2025_2026"]:
        if re.search(r"BOE-A-202[56]", x): print("   ", x[:260])
KW = re.compile(r"salario|cotizaci|pensi|permiso|jubilaci|autónom|arrend|alquiler|vivienda|Justicia|instancia|clientela|consumidor|Tráfico|vehícul|movilidad|factura|Real Decreto-ley|derogación|convalidación", re.I)
for k, v in res["issues"].items():
    if "error" in v:
        print("## issue", k, v["error"]); continue
    print(f"## issue {k} items={v['n_items']} pdf_last_modified={v['last_modified']}")
    for x in v["items"]:
        if KW.search(x): print("   ", x[:240])
