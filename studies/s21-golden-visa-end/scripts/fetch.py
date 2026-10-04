#!/usr/bin/env python3
"""Download every public source of S21 into data/raw/ (git-ignored). Resumable: files already
present are skipped unless --force is given.

    python3 scripts/fetch.py [--force] [mivau|wayback|fx|legal|portugal|all]

- mivau     MIVAU «Transacciones inmobiliarias» workbooks (apps.fomento.gob.es/BoletinOnline2/sedal/)
- wayback   Internet Archive copies of tables 1.6 and 1.7 (earlier vintages; table 1.7 keeps one quarter)
- fx        ECB reference rates, quarterly averages, USD, GBP, CNY per euro (ECB Data Portal)
- legal     BOE, La Moncloa, INE (PEN 2026 calendar) and portugal.gov.pt pages quoted in the paper
- portugal  Statistics Portugal indicators 0012785 and 0012786 (scripts/fetch_portugal.py)

Every request goes through polite.py: fixed User-Agent, robots.txt (RFC 9309), at most one request
per second per host, logged to work/fetch_log.jsonl.
"""
import os
import subprocess
import sys
import time

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, "scripts"))
import polite  # noqa: E402

RAW = os.path.join(R, "data", "raw")
SEDAL = "https://apps.fomento.gob.es/BoletinOnline2/sedal/"
MIVAU = ["34010110", "34010120", "340101a0", "340101d0", "340101l0", "34020110", "34020140", "34020150"]
WAYBACK = [("340101d0", "20230530073450"), ("340101d0", "20251006134433"),
           ("340101l0", "20211005195153"), ("340101l0", "20230116105232"),
           ("340101l0", "20230529192926"), ("340101l0", "20251006131616")]
FX = ["USD", "GBP", "CNY"]
LEGAL = {
    "lo1_2025_consolidado.html": "https://www.boe.es/buscar/act.php?id=BOE-A-2025-76",
    "lo1_2025_original.html": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-76",
    "lo1_2025_doc.html": "https://www.boe.es/buscar/doc.php?id=BOE-A-2025-76",
    "ley14_2013_consolidado.html": "https://www.boe.es/buscar/act.php?id=BOE-A-2013-10074",
    "ley14_a63_2015.html": "https://www.boe.es/buscar/act.php?id=BOE-A-2013-10074&b=86&tn=1&p=20150729",
    "ley14_a64_2015.html": "https://www.boe.es/buscar/act.php?id=BOE-A-2013-10074&b=87&tn=1&p=20150729",
    "rdl26_2026.html": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-20266",
    "cat_dleg1_2024_consolidado.html": "https://www.boe.es/buscar/act.php?id=BOE-A-2024-6951",
    "cat_dleg1_2024_a641-1_2024.html": "https://www.boe.es/buscar/act.php?id=BOE-A-2024-6951&b=142&tn=1&p=20240314",
    "mad_dleg1_2010_consolidado.html": "https://www.boe.es/buscar/act.php?id=BOCM-m-2010-90068",
    "trlitpajd_consolidado.html": "https://www.boe.es/buscar/act.php?id=BOE-A-1993-25359",
    "moncloa/080424-sanchez-anuncia-fin-golden-visa.aspx":
        "https://www.lamoncloa.gob.es/presidente/actividades/Paginas/2024/080424-sanchez-anuncia-fin-golden-visa.aspx",
    "moncloa/20240409-referencia-rueda-de-prensa-ministros.aspx":
        "https://www.lamoncloa.gob.es/consejodeministros/referencias/Paginas/2024/20240409-referencia-rueda-de-prensa-ministros.aspx",
    "moncloa/130125-sanchez-foro-vivienda.aspx":
        "https://www.lamoncloa.gob.es/presidente/actividades/Paginas/2025/130125-sanchez-foro-vivienda.aspx",
    "moncloa/20260929-referencia-rueda-de-prensa-ministros.aspx":
        "https://www.lamoncloa.gob.es/consejodeministros/referencias/Paginas/2026/20260929-referencia-rueda-de-prensa-ministros.aspx",
    "ine_pen_calendario2026.pdf": "https://www.ine.es/normativa/leyes/plan/plan_2025-2028/calendario2026.pdf",
    "ine_ioe_25003.html": "https://www.ine.es/dyngs/IOE/operacion.htm?id=1259931132131",
    "ine_etdp_resultados.html": "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736171438&menu=resultados&idp=1254735576757",
    "datosgob_transacciones.html": "https://datos.gob.es/es/catalogo/e05233601-transacciones-inmobiliarias-de-vivienda",
    "pt_cm_2023-02-16.html": "https://portugal.gov.pt/gc23/governo/comunicados-do-conselho-de-ministros/535",
}


def get(url, out, force, tries=3):
    """Download url to out unless present. Server errors (5xx) are retried up to `tries` times,
    30 s apart (the ECB Data Portal answers 504 now and then)."""
    if os.path.exists(out) and not force:
        return
    os.makedirs(os.path.dirname(out), exist_ok=True)
    for i in range(tries):
        try:
            st, final = polite.fetch(url, out)
        except PermissionError as e:
            print("ROBOTS:", e)
            return
        print(st, os.path.relpath(out, R), flush=True)
        if isinstance(st, int) and st < 500:
            if st < 400 and os.path.exists(out + f".http{st}"):
                os.remove(out + f".http{st}")
            return
        if i + 1 < tries:
            time.sleep(30)
    print(f"FAILED after {tries} tries: {url}", flush=True)


def main():
    a = [x for x in sys.argv[1:] if x != "--force"]
    force = "--force" in sys.argv
    what = a[0] if a else "all"
    if what in ("mivau", "all"):
        for t in MIVAU:
            get(SEDAL + f"{t}.XLS", os.path.join(RAW, "mivau", f"{t}.XLS"), force)
    if what in ("wayback", "all"):
        for t, ts in WAYBACK:
            get(f"https://web.archive.org/web/{ts}id_/{SEDAL}{t}.XLS",
                os.path.join(RAW, "wayback", f"{t}_{ts}.XLS"), force)
    if what in ("fx", "all"):
        for c in FX:
            get(f"https://data-api.ecb.europa.eu/service/data/EXR/Q.{c}.EUR.SP00.A?format=csvdata",
                os.path.join(RAW, "fx", f"ecb_EXR_Q.{c}.EUR.SP00.A.csv"), force)
    if what in ("legal", "all"):
        for name, url in LEGAL.items():
            get(url, os.path.join(RAW, "legal", name), force)
    if what in ("portugal", "all"):
        subprocess.run([sys.executable, os.path.join(R, "scripts", "fetch_portugal.py")], check=True)


if __name__ == "__main__":
    main()
