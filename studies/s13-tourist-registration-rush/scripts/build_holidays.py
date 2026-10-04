#!/usr/bin/env python3
"""Build data/holidays.csv from the BOE resolutions of the Dirección General de Trabajo that list
the non-working days of each year by autonomous community (saved in data/raw/legal/; fetch them
with `python3 scripts/polite.py https://www.boe.es/diario_boe/txt.php?id=<ID> <file>`).

Regions written: ES (days marked for every community), CV, CAT, AND, PV, IB. Local holidays
are not included. Adapted from the parser in work/legal/parse_fiestas.py.

    python3 scripts/build_holidays.py
"""
import csv, html, os, re
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES = {2023: "BOE-A-2022-16755_fiestas2023.html", 2024: "BOE-A-2023-22014_fiestas2024.html",
         2025: "BOE-A-2024-21316_fiestas2025.html", 2026: "BOE-A-2025-21667_fiestas2026.html"}
REGIONS = {"CV": "Comunitat Valenciana", "CAT": "Cataluña", "AND": "Andalucía", "PV": "País Vasco",
           "IB": "Illes Balears"}
MES = {m: i + 1 for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre "
                                      "octubre noviembre diciembre".split())}


def parse(path, year):
    s = open(path, encoding="utf-8", errors="replace").read()
    t = s[s.find("<table"):s.find("</table>")]
    heads = [html.unescape(re.sub(r"<[^>]+>", "", h)).strip()
             for h in re.findall(r'<th[^>]*axis="comunidad"[^>]*>(.*?)</th>', t, re.S)]
    out, month = [], None
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if not cells:
            continue
        if cells[0].lower() in MES:
            month = MES[cells[0].lower()]
            continue
        m = re.match(r"(\d+)\s+(.*)", cells[0])
        if not m or month is None:
            continue
        day, name = int(m.group(1)), m.group(2).rstrip(".").strip()
        marks = dict(zip(heads, cells[1:]))
        date = f"{year}-{month:02d}-{day:02d}"
        if marks and all(v for v in marks.values()):
            out.append(("ES", date, name))
        for code, label in REGIONS.items():
            col = [h for h in heads if h.startswith(label)]
            if col and marks.get(col[0]):
                out.append((code, date, name))
    return out


def main():
    rows = []
    for y, f in FILES.items():
        rows += parse(os.path.join("data", "raw", "legal", f), y)
    with open("data/holidays.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["region", "date", "name"])
        for r in sorted(set(rows), key=lambda r: (r[1], r[0])):
            w.writerow(r)
    print(len(rows), "rows")


if __name__ == "__main__":
    main()
