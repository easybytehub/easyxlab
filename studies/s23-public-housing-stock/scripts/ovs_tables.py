#!/usr/bin/env python3
"""S23: extract the stock tables of the Ministry's Observatorio de Vivienda y Suelo (OVS)
'Boletín Especial Vivienda Social' 2020 and 2024 (PDF -> pdftotext -layout), and check their
arithmetic.

Writes:
  data/ovs_eu_table.csv        Tabla 2.1 of both bulletins: country, principal dwellings,
                               social-rental share and count, as printed
  data/ovs_regions.csv         regional (CCAA) public stock by tenure: 2019 (2020 bulletin,
                               Tabla 2.2) and 2023 (2024 bulletin, Tablas 2.2 and 2.3)
  data/ovs_checks.csv          printed totals against the sums of the printed rows
"""
import csv, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s23lib import RAW, DATA

B2020 = os.path.join(RAW, "ovs", "OVS_boletin_especial_vivienda_social_2020.pdf")
B2024 = os.path.join(RAW, "ovs", "OVS_boletin_especial_vivienda_social_2024.pdf")
REGIONS = ["Andalucía", "Aragón", "Asturias", "Balears", "Canarias", "Cantabria", "Castilla y León",
           "Castilla-La Mancha", "Cataluña", "Comunitat Valenciana", "Extremadura", "Galicia", "Madrid",
           "Murcia", "Navarra", "País Vasco", "Rioja", "Ceuta", "Melilla", "TOTAL"]


def layout(pdf):
    return subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", pdf, "-"], capture_output=True, check=True).stdout.decode("utf-8")


def num(s):
    """Spanish-formatted integer ('178.493') or percentage ('9,3%') -> int/float."""
    s = s.strip()
    if s.endswith("%"):
        return float(s[:-1].replace(".", "").replace(",", "."))
    return int(s.replace(".", ""))


def block(text, start, end):
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


def region_of(line):
    for r in REGIONS:
        if line.strip().startswith(r) or (r == "Asturias" and line.strip().startswith("Asturias")):
            return r
    return None


def eu_table(text, year):
    b = block(text, "Tabla 2.1.", "Fuente: Censo 2011")
    out = []
    for line in b.splitlines():
        m = re.match(r"\s*([A-ZÁÉÍÓÚ][A-Za-zÁÉÍÓÚáéíóúñ ]+?|UE ?2[78])\*{0,3}\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d,]+%)\s+([\d.]+)\s", line)
        if m:
            out.append({"bulletin": year, "country": m.group(1).strip(), "population": num(m.group(2)),
                        "dwellings_total": num(m.group(3)), "principal_dwellings": num(m.group(4)),
                        "social_share_of_principal_pct": num(m.group(5)), "social_dwellings": num(m.group(6))})
    return out


def positions(line):
    return [(m.end(), m.group(0)) for m in re.finditer(r"[\d.]+", line)]


def ccaa_2020(text):
    """Tabla 2.2 of the 2020 bulletin: blank cells are possible, so numbers are assigned to the
    nearest column by their right edge, with column edges taken from the TOTAL row."""
    b = block(text, "Tabla 2.2. Parque de vivienda de titularidad", "Fuente: Cuestionario sobre vivienda social 2019")
    lines = [l for l in b.splitlines() if region_of(l)]
    total = [l for l in lines if l.strip().startswith("TOTAL")][0]
    edges = [e for e, _ in positions(total)]
    cols = ["rental", "rent_to_buy", "for_sale", "other", "total"]
    out = []
    for l in lines:
        r = region_of(l)
        name_end = len(l) - len(l.lstrip()) + len(r)
        m = re.match(r"[^(\d]*\([^)]*\)", l[name_end:])
        if m:
            name_end += m.end()
        vals = {}
        for e, tok in positions(l[name_end:]):
            e += name_end
            k = min(range(len(edges)), key=lambda i: abs(edges[i] - e))
            vals[cols[k]] = num(tok)
        out.append({"source": "OVS 2020, Tabla 2.2", "ref_year": 2019, "region": r,
                    **{c: vals.get(c, "") for c in cols}})
    return out


def ccaa_2024_t22(text):
    b = block(text, "Tabla 2.2. Parque de vivienda de titularidad", "Fuente: Encuesta sobre vivienda social 2023")
    out = []
    for l in b.splitlines():
        r = region_of(l)
        if not r:
            continue
        rest = re.sub(r"^[^(\d]*\([^)]*\)", " ", l[l.index(r) + len(r):])   # "(Principado de)" etc.
        toks = re.findall(r"[\d.,]+%|[\d.]+", rest)
        nums = [t for t in toks if not t.endswith("%")]
        if len(nums) != 7:
            continue
        rental_public, rental_ppp, rental, rent_to_buy, for_sale, other, total = [num(x) for x in nums]
        out.append({"source": "OVS 2024, Tabla 2.2", "ref_year": 2023, "region": r, "rental_public": rental_public,
                    "rental_ppp": rental_ppp, "rental": rental, "rent_to_buy": rent_to_buy, "for_sale": for_sale,
                    "other": other, "total": total})
    return out


def ccaa_2024_t23(text):
    b = block(text, "Tabla 2.3. Evolución del parque de vivienda", "(*) El porcentaje no resulta")
    out = []
    for l in b.splitlines():
        r = region_of(l)
        if not r:
            continue
        rest = re.sub(r"^[^(\d]*\([^)]*\)", " ", l[l.index(r) + len(r):])   # "(Princip. de)" etc.
        rest = re.sub(r"[<>] ?100% ?\(\*\)", " PCT ", rest)
        toks = re.findall(r"-?[\d.]+%|PCT|-?[\d.]+|(?<=\s)-(?=\s)", rest)
        # five groups of (2019, 2024, var uds, var %)
        groups = [toks[i:i + 4] for i in range(0, 20, 4)]
        if len(toks) < 20:
            continue
        row = {"source": "OVS 2024, Tabla 2.3", "region": r}
        for name, g in zip(["rental", "rent_to_buy", "for_sale", "other", "total"], groups):
            row[f"{name}_2019"] = num(g[0]); row[f"{name}_2023"] = num(g[1])
            row[f"{name}_var_printed"] = g[2]
        out.append(row)
    return out


def municipal_2024(text):
    """Tabla 2.8 of the 2024 bulletin: municipalities over 20,000 inhabitants, population 2023,
    stock by tenure; '*' marks a municipality whose figures come from the 2019 survey."""
    i = text.index("Tabla 2.8. Parque de vivienda de titularidad de los ayuntamientos")
    seg = text[i:]
    k = re.search(r"Tabla 2\.9|\n\s*3\. INVERSI", seg)
    seg = seg[:k.start()] if k else seg
    out, region = [], ""
    for l in seg.splitlines():
        h = re.match(r"([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ,.()-]{3,})\s*$", l.strip())
        if h and not re.search(r"\d", l) and not re.match(r"(SECRETAR|DIRECCI|OBSERVATORIO|TABLA)", h.group(1)):
            region = h.group(1).strip()
            continue
        m = re.match(r"\s{2,}([^\d\s][^\d]*?)(\*?)\s{2,}(\d{1,3}(?:\.\d{3})+)\s*(.*)$", l)
        if not m:
            continue
        name, star, pop, rest = m.group(1).strip(), m.group(2), num(m.group(3)), m.group(4)
        toks = re.findall(r"n\.d\.|-?[\d.]+%|[\d.]+|-", rest)
        vals = []
        it = iter(toks)
        pending = list(toks)
        # six (units, percent) pairs and a total; a missing units cell shows as a bare percent
        pos = 0
        for _ in range(6):
            if pos < len(pending) and not pending[pos].endswith("%"):
                u = pending[pos]; pos += 1
            else:
                u = ""
            if pos < len(pending) and (pending[pos].endswith("%") or pending[pos] == "-"):
                pos += 1
            vals.append(u)
        total = pending[pos] if pos < len(pending) else ""
        def v(x):
            return num(x) if re.fullmatch(r"[\d.]+", x or "") else ""
        out.append({"region_heading": region, "municipality": name, "data_from_2019_survey": "yes" if star else "",
                    "population_2023": pop, "rental_public": v(vals[0]), "rental_ppp": v(vals[1]), "rental": v(vals[2]),
                    "rent_to_buy": v(vals[3]), "for_sale": v(vals[4]), "other": v(vals[5]), "total": v(total),
                    "has_data": "yes" if toks else ""})
    return out


def main():
    t20, t24 = layout(B2020), layout(B2024)
    mun = municipal_2024(t24)
    with open(os.path.join(DATA, "ovs_municipal_2023.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(mun[0])); w.writeheader(); w.writerows(mun)
    eu = eu_table(t20, 2020) + eu_table(t24, 2024)
    with open(os.path.join(DATA, "ovs_eu_table.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(eu[0])); w.writeheader(); w.writerows(eu)
    a = ccaa_2020(t20); b = ccaa_2024_t22(t24); c = ccaa_2024_t23(t24)
    fields = ["source", "ref_year", "region", "rental_public", "rental_ppp", "rental", "rent_to_buy", "for_sale", "other", "total"]
    with open(os.path.join(DATA, "ovs_regions.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(a + b)
    with open(os.path.join(DATA, "ovs_regions_t23.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(c[0])); w.writeheader(); w.writerows(c)
    checks = []

    def chk(table, what, printed, computed, note=""):
        checks.append({"table": table, "item": what, "printed": printed, "sum_of_rows": computed,
                       "difference": (printed - computed) if isinstance(printed, int) and isinstance(computed, int) else "",
                       "note": note})
    for rows, tab, cols in [(a, "OVS 2020 Tabla 2.2", ["rental", "rent_to_buy", "for_sale", "other", "total"]),
                            (b, "OVS 2024 Tabla 2.2", ["rental_public", "rental_ppp", "rental", "rent_to_buy", "for_sale", "other", "total"])]:
        tot = [r for r in rows if r["region"] == "TOTAL"][0]
        body = [r for r in rows if r["region"] != "TOTAL"]
        for col in cols:
            chk(tab, f"TOTAL {col}", tot[col], sum(int(r[col] or 0) for r in body))
        for r in body:
            s = sum(int(r[k] or 0) for k in ("rental", "rent_to_buy", "for_sale", "other"))
            if s != r["total"]:
                chk(tab, f"{r['region']}: row total", r["total"], s, "row total differs from the sum of its tenures")
    tot = [r for r in c if r["region"] == "TOTAL"][0]
    body = [r for r in c if r["region"] != "TOTAL"]
    for col in ["rental", "rent_to_buy", "for_sale", "other", "total"]:
        for y in ("2019", "2023"):
            chk("OVS 2024 Tabla 2.3", f"TOTAL {col} {y}", tot[f"{col}_{y}"], sum(r[f"{col}_{y}"] for r in body))
    for r in c:
        exp = r["total_2023"] - r["total_2019"]
        pr = num(r["total_var_printed"]) if re.fullmatch(r"-?[\d.]+", r["total_var_printed"]) else r["total_var_printed"]
        if pr != exp:
            chk("OVS 2024 Tabla 2.3", f"{r['region']}: printed change in total", pr, exp, "printed change differs from 2023 minus 2019")
    t23 = {r["region"]: r for r in c}
    for r in b:
        x = t23.get(r["region"])
        if x and x["rental_2023"] != r["rental"]:
            chk("OVS 2024 Tablas 2.2 vs 2.3", f"{r['region']}: rental 2023", r["rental"], x["rental_2023"], "Tabla 2.2 vs Tabla 2.3")
        if x and x["total_2023"] != r["total"]:
            chk("OVS 2024 Tablas 2.2 vs 2.3", f"{r['region']}: total 2023", r["total"], x["total_2023"], "Tabla 2.2 vs Tabla 2.3")
    t20 = {r["region"]: r for r in a}
    for r in c:
        x = t20.get(r["region"])
        if x and x["total"] != r["total_2019"]:
            chk("OVS 2020 Tabla 2.2 vs OVS 2024 Tabla 2.3", f"{r['region']}: total 2019", x["total"], r["total_2019"], "2019 value as printed in each bulletin")
    with open(os.path.join(DATA, "ovs_checks.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(checks[0])); w.writeheader(); w.writerows(checks)
    for k in checks:
        if k["difference"] not in (0, ""):
            print(k)
        elif k["difference"] == "":
            print(k)
    print(len(eu), "EU rows;", len(a), len(b), len(c), "regional rows;", len(checks), "checks")


if __name__ == "__main__":
    main()
