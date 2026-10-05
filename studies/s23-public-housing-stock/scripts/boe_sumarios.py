#!/usr/bin/env python3
"""S23: read every BOE daily summary from the day Ley 12/2023 entered into force (26 May 2023)
to 3 October 2026 through the BOE open-data API, keep only the item titles (with id, section,
department, epigraph) in data/raw/boe/sumarios.jsonl.gz, and list every title that mentions the
public housing stock or an art. 32-style inventory/report. Writes data/boe_title_hits.csv.

Polite: one request per second (polite.py), resumable (days already read are skipped).
Run it in the background: nohup python3 scripts/boe_sumarios.py > work/boe_sumarios.log 2>&1 &
"""
import csv, datetime, gzip, json, os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite
from s23lib import RAW, DATA

START, END = datetime.date(2023, 5, 26), datetime.date(2026, 10, 3)
OUT = os.path.join(RAW, "boe", "sumarios.jsonl.gz")
API = "https://www.boe.es/datosabiertos/api/boe/sumario/{}"
PAT = re.compile(r"parque (público|publico|social)|vivienda(s)? social(es)?|inventario[^.]{0,80}vivienda|"
                 r"memoria(?! Democr)[^.]{0,80}vivienda|vivienda[^.]{0,80}memoria(?! Democr)|mapa de la vivienda|"
                 r"vivienda[^.]{0,40}titularidad pública|artículo 32 de la Ley 12/2023", re.I)


def items(d):
    def walk(x, ctx):
        if isinstance(x, dict):
            if "titulo" in x and "identificador" in x:
                yield dict(ctx, id=x["identificador"], titulo=x["titulo"])
            for k, v in x.items():
                c = dict(ctx)
                if k == "seccion" or k == "departamento" or k == "epigrafe":
                    pass
                if isinstance(v, (dict, list)):
                    if isinstance(x.get("nombre"), str) and "codigo" in x and k in ("departamento", "epigrafe"):
                        c["seccion" if k == "departamento" else "departamento"] = x["nombre"]
                    if isinstance(x.get("nombre"), str) and k == "item":
                        c["epigrafe"] = x["nombre"]
                    yield from walk(v, c)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v, ctx)
    yield from walk(d, {})


def done_days():
    s = set()
    if os.path.exists(OUT):
        with gzip.open(OUT, "rt", encoding="utf-8") as f:
            for line in f:
                s.add(json.loads(line)["fecha"])
    return s


def crawl():
    done = done_days()
    d = START
    while d <= END:
        k = d.strftime("%Y%m%d")
        if k not in done:
            tmp = os.path.join(tempfile.gettempdir(), f"s23_sumario_{k}.json")
            try:
                st, _ = polite.fetch(API.format(k), tmp, "application/json")
            except Exception as e:
                print("ERROR", k, type(e).__name__, e, flush=True); st = None
            rec = {"fecha": k, "status": st, "items": []}
            if st == 200:
                rec["items"] = list(items(json.load(open(tmp, encoding="utf-8"))))
            if st in (200, 404):          # 404: no BOE that day (Sundays before 2008 etc.)
                with gzip.open(OUT, "at", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            for p in (tmp, tmp + f".http{st}"):
                if os.path.exists(p):
                    os.remove(p)
            print(k, st, len(rec["items"]), flush=True)
        d += datetime.timedelta(days=1)


def hits():
    rows, n_days, n_items = [], 0, 0
    with gzip.open(OUT, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line); n_days += 1; n_items += len(r["items"])
            for it in r["items"]:
                if PAT.search(it["titulo"]):
                    rows.append({"fecha": r["fecha"], "id": it["id"], "seccion": it.get("seccion", ""),
                                 "departamento": it.get("departamento", ""), "titulo": it["titulo"]})
    with open(os.path.join(DATA, "boe_title_hits.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["fecha", "id", "seccion", "departamento", "titulo"])
        w.writeheader(); w.writerows(rows)
    print(f"{n_days} days, {n_items} items, {len(rows)} title hits")


if __name__ == "__main__":
    if "--hits-only" not in sys.argv:
        crawl()
    hits()
