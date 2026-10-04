#!/usr/bin/env python3
"""S22: build the aggregates in data/ from the locked INE tables and the transcribed series.

Outputs (all aggregates, no unit-level data):
  data/national_series.csv     one row per edition 2012-2024 (centres, accommodation centres, places, occupied)
  data/ine_chart_2006_2024.csv INE's own series of places and occupied places, as charted in the 2024 release
  data/specialisation.csv      2020, 2022, 2024 by «especialización» (immigrants / gender violence / other)
  data/reference_dates.csv     places and occupied places at INE's two reference dates, by type of centre
  data/regions.csv             editions 2016-2024 by region (places, occupied, centres, immigrant-only centres)
  data/situations.csv          centres oriented to «Inmigración/Solicitud de protección internacional»
  data/revision_2024.csv       the 2024 release as first published (26-Sep-2025) and as revised (17-Oct-2025)
  data/explanatory.csv         asylum applications (Eurostat), reception places and arrivals (official reports)
"""
from __future__ import annotations

import csv
import gzip
import html
import json
import re

from s22lib import DATA, RAW, read_table, region, segment

EDS = (2012, 2014, 2016, 2018, 2020, 2022, 2024)


def write(name, rows, fields):
    with open(DATA / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})
    print(f"wrote data/{name} ({len(rows)} rows)")


def is_total(s: str) -> bool:
    s = s.strip().lower()
    return s in ("", "total", "total nacional") or s.startswith("total de centros")


def pick(ed, table, where, indicator=None):
    """Return the single value of `table` whose columns satisfy `where` (col-index -> predicate)."""
    h, rows = read_table(ed, table)
    hits = []
    for r in rows:
        cells = [r[c] for c in h[:-1]]
        if all(pred(cells[i]) for i, pred in where.items()):
            if indicator is None or indicator(cells[-1] if len(cells) else ""):
                hits.append(r["value"])
    if len(hits) != 1:
        raise ValueError(f"{ed}/{table}: {len(hits)} matches for {where}")
    return hits[0]


T = lambda s: is_total(s)
EQ = lambda v: (lambda s: s == v)
HAS = lambda v: (lambda s: v.lower() in s.lower())

# ---------------------------------------------------------------------------- national series
CENTRES = {2012: (9737, {0: T, 1: T}), 2014: (14038, {0: T, 1: T, 2: T}), 2016: (25819, {0: T, 1: T, 2: T}),
           2018: (32377, {0: T, 1: T, 2: T}), 2020: (49454, {0: T, 1: T, 2: T}),
           2022: (59698, {0: T, 1: T, 2: T}), 2024: (75637, {0: T, 1: T, 2: T})}
ACCOM = {2012: 9711, 2014: 14047, 2016: 25828, 2018: 32386, 2020: 49467, 2022: 59711, 2024: 75650}
PLACES = {2014: 14049, 2016: 25830, 2018: 32388, 2020: 49469, 2022: 59713, 2024: 75652}
RESPONSE = {  # «nivel de respuesta», literal from each release's methodological note / IME
    2018: (77.8, "INE, nota de prensa ECAPSH 2018: «obteniéndose un nivel de respuesta del 77,8%»"),
    2020: (79.5, "INE, nota de prensa ECAPSH 2020: «obteniéndose un nivel de respuesta del 79,5%»"),
    2024: (80.0, "INE, metodología/nota 2024: «nivel de respuesta del 80,0 %»; IME: «la tasa de respuesta fue el 79,9%»"),
}


def accom_centres(ed):
    h, rows = read_table(ed, ACCOM[ed])
    tot = 0.0
    for r in rows:
        if r[h[0]].lower().startswith("lunes a viernes") and r[h[2]] == "Centros" and not is_total(r[h[1]]):
            tot += r["value"] or 0
    return tot


def places_mean(ed):
    """(places, occupied) national mean; 2012 from the regional table 9743."""
    if ed == 2012:
        p = pick(2012, 9743, {0: EQ("Total"), 1: EQ("2012: Capacidad (plazas medias)")})
        o = pick(2012, 9743, {0: EQ("Total"), 1: EQ("2012: Ocupación (plazas medias)")})
        return p, o
    if ed in (2014, 2016, 2018):
        w = {0: T}
    else:
        w = {0: T, 1: T}
    p = pick(ed, PLACES[ed], {**w, len(w): HAS("plazas existentes")})
    o = pick(ed, PLACES[ed], {**w, len(w): lambda s: s.lower().startswith("número medio de plazas ocupadas") and "mujeres" not in s.lower()})
    return p, o


def national():
    out = []
    for ed in EDS:
        t, w = CENTRES[ed]
        centres = pick(ed, t, {**w, len(w): EQ("Centros")})
        p, o = places_mean(ed)
        rr = RESPONSE.get(ed, (None, ""))
        out.append({"edition": ed, "centres": int(centres), "accommodation_centres": int(accom_centres(ed)),
                    "places_mean": int(p), "occupied_mean": int(o), "occupancy_pct": round(100 * o / p, 1),
                    "occupied_scope": "18+" if ed >= 2022 else "all ages",
                    "response_rate_pct": rr[0], "response_rate_source": rr[1]})
    write("national_series.csv", out, list(out[0].keys()))
    return out


# ---------------------------------------------------------------------------- INE's chart series
def ine_chart():
    t = (RAW / "ine_press" / "ECAPSH2024.htm").read_text(encoding="utf-8")
    for m in re.finditer(r'\{\s*"mode".*?\n\}', t, flags=re.S):
        s = m.group(0)
        if "Plazas existentes" in s:
            ticks = re.findall(r'"(\d{4})"', re.search(r'"ticks":\s*\[(.*?)\]', s, re.S).group(1))
            vals = re.search(r'"values":\s*\[(.*)\]\s*,\s*"ratio', s, re.S).group(1)
            series = [re.findall(r'"(\d+)"', v) for v in re.findall(r"\[(.*?)\]", vals, re.S)]
            rows = [{"edition": int(y), "places_chart": int(series[0][i]), "occupied_chart": int(series[1][i])}
                    for i, y in enumerate(ticks)]
            write("ine_chart_2006_2024.csv", rows, ["edition", "places_chart", "occupied_chart"])
            return rows
    raise ValueError("chart not found in the 2024 press release")


# ---------------------------------------------------------------------------- specialisation
SPEC = {2020: (49454, 49456, 49469), 2022: (59698, 59700, 59713), 2024: (75637, 75639, 75652)}


def specialisation():
    out = []
    for ed, (tc, ts, tp) in SPEC.items():
        h, rows = read_table(ed, tc)
        centres = {segment(r[h[0]]): r["value"] for r in rows
                   if is_total(r[h[1]]) and is_total(r[h[2]]) and r[h[3]] == "Centros"}
        h, rows = read_table(ed, ts)
        accom = {segment(r[h[1]]): r["value"] for r in rows if r[h[0]] == "Alojamiento" and r[h[2]] == "Centros"}
        h, rows = read_table(ed, tp)
        pl = {}
        for r in rows:
            seg, own, ind = segment(r[h[0]]), r[h[1]], r[h[2]].lower()
            key = {"total": "all", "titularidad pública": "public", "titularidad privada": "private"}.get(own.lower())
            if key is None:
                continue
            if ind.startswith("número medio de plazas existentes"):
                pl[(seg, key, "places")] = r["value"]
            elif ind == "número medio de plazas ocupadas":
                pl[(seg, key, "occupied")] = r["value"]
            elif ind == "número medio de plazas ocupadas por mujeres":
                pl[(seg, key, "occupied_women")] = r["value"]
        for seg in ("ALL", "IMM", "GBV", "OTH"):
            out.append({"edition": ed, "segment": seg, "centres": int(centres[seg]),
                        "accommodation_centres": int(accom[seg]),
                        "places_mean": int(pl[(seg, "all", "places")]),
                        "occupied_mean": int(pl[(seg, "all", "occupied")]),
                        "occupied_women_mean": int(pl[(seg, "all", "occupied_women")]),
                        "places_public": int(pl[(seg, "public", "places")]),
                        "occupied_public": int(pl[(seg, "public", "occupied")]),
                        "places_private": int(pl[(seg, "private", "places")]),
                        "occupied_private": int(pl[(seg, "private", "occupied")]),
                        "occupied_scope": "18+" if ed >= 2022 else "all ages"})
    write("specialisation.csv", out, list(out[0].keys()))
    # identity checks: segments add up to the total (INE rounds means; allow ±2)
    for ed in SPEC:
        rs = {r["segment"]: r for r in out if r["edition"] == ed}
        for k in ("centres", "accommodation_centres", "places_mean", "occupied_mean"):
            s = sum(rs[x][k] for x in ("IMM", "GBV", "OTH"))
            assert abs(s - rs["ALL"][k]) <= 2, (ed, k, s, rs["ALL"][k])
    return out


# ---------------------------------------------------------------------------- reference dates
DATES = {2016: 25829, 2018: 32387, 2020: 49468, 2022: 59712, 2024: 75651}
TYPE = {"albergues, residencias, centros de acogida": "collective", "pisos o apartamentos": "flats",
        "pensiones o establecimientos hoteleros": "hostels_hotels"}


def reference_dates():
    out = []
    for ed, t in DATES.items():
        h, rows = read_table(ed, t)
        acc = {}
        for r in rows:
            typ = "total" if is_total(r[h[0]]) else TYPE.get(r[h[0]].lower())
            if typ is None or not is_total(r[h[1]]):
                continue
            ind = r[h[3]].lower()
            if ind in ("existentes", "plazas existentes"):
                k = "places"
            elif ind in ("ocupadas", "plazas ocupadas. ambos sexos"):
                k = "occupied"
            else:
                continue
            acc.setdefault((typ, r[h[2]]), {})[k] = r["value"]
        for (typ, date), v in sorted(acc.items()):
            out.append({"edition": ed, "date": date, "type": typ, "places": int(v["places"]),
                        "occupied": int(v["occupied"]) if v.get("occupied") is not None else None})
    write("reference_dates.csv", out, ["edition", "date", "type", "places", "occupied"])
    return out


# ---------------------------------------------------------------------------- regions
RPLACES = {2016: 25859, 2018: 32417, 2020: 49499, 2022: 59743, 2024: 75682}
RCENTRES = {2016: 25846, 2018: 32404, 2020: 49485, 2022: 59729, 2024: 75668}
RSPEC = {2020: 49486, 2022: 59730, 2024: 75669}


def regions():
    acc = {}
    for ed, t in RPLACES.items():
        h, rows = read_table(ed, t)
        rc = [c for c in h if "omunidad" in c][0]
        for r in rows:
            reg = region(r[rc])
            ind = r[h[-2]].lower()
            if reg is None:
                continue
            if ind.startswith("número medio de plazas existentes"):
                acc.setdefault((ed, reg), {})["places_mean"] = r["value"]
            elif ind == "número medio de plazas ocupadas":
                acc.setdefault((ed, reg), {})["occupied_mean"] = r["value"]
    for ed, t in RCENTRES.items():
        h, rows = read_table(ed, t)
        rc = [c for c in h if "omunidad" in c][0]
        others = [c for c in h[:-2] if c != rc and c != "Total Nacional"]
        for r in rows:
            reg = region(r[rc])
            if reg and all(is_total(r[c]) for c in others) and r[h[-2]] == "Centros":
                acc.setdefault((ed, reg), {})["centres"] = r["value"]
    for ed, t in RSPEC.items():
        h, rows = read_table(ed, t)
        seg = {}
        for r in rows:
            reg = region(r[h[0]])
            if reg and r[h[2]] == "Centros":
                seg[(reg, segment(r[h[1]]))] = r["value"]
        for reg in {k[0] for k in seg}:
            v = seg.get((reg, "IMM"))
            if v is None:  # INE prints «.» where the other segments already add up to the total
                v = seg[(reg, "ALL")] - (seg.get((reg, "GBV")) or 0) - (seg.get((reg, "OTH")) or 0)
                assert v == 0, (ed, reg, v)
            acc.setdefault((ed, reg), {})["centres_imm"] = v
    out = []
    for (ed, reg), v in sorted(acc.items(), key=lambda x: (x[0][0], x[0][1] != "Spain", x[0][1])):
        out.append({"edition": ed, "region": reg, **{k: (None if v.get(k) is None else int(v[k]))
                    for k in ("places_mean", "occupied_mean", "centres", "centres_imm")}})
    write("regions.csv", out, ["edition", "region", "places_mean", "occupied_mean", "centres", "centres_imm"])
    for ed in RPLACES:
        rs = [r for r in out if r["edition"] == ed and r["region"] != "Spain" and r["occupied_mean"] is not None]
        nat = [r for r in out if r["edition"] == ed and r["region"] == "Spain"][0]
        assert len(rs) == 19, (ed, len(rs))
        assert abs(sum(r["occupied_mean"] for r in rs) - nat["occupied_mean"]) <= 12, ed
    return out


RDATES = {2022: 59742, 2024: 75681}


def region_dates():
    """Places and occupied places by region at each reference date (2022, 2024)."""
    out = []
    for ed, t in RDATES.items():
        h, rows = read_table(ed, t)
        rc = [c for c in h if "omunidad" in c][0]
        for r in rows:
            reg = region(r[rc])
            m = re.match(r"Plazas (existentes|ocupadas) a (.+)$", r[h[-2]])
            if reg is None or m is None:
                continue
            out.append({"edition": ed, "region": reg, "date": m.group(2),
                        "indicator": "places" if m.group(1) == "existentes" else "occupied",
                        "value": None if r["value"] is None else int(r["value"])})
    write("region_dates.csv", out, ["edition", "region", "date", "indicator", "value"])
    return out


# ---------------------------------------------------------------------------- situations
SIT = {2014: 14037, 2016: 25818, 2018: 32376, 2020: 49457, 2022: 59701, 2024: 75640}


def situations():
    out = []
    for ed, t in SIT.items():
        h, rows = read_table(ed, t)
        imm = tot = None
        for r in rows:
            if not (all(is_total(r[c]) for c in h[1:-2]) and r[h[-2]] == "Centros"):
                continue
            lab = r[h[0]]
            if lab.lower().startswith("inmigraci"):
                imm = r["value"]
            elif lab.upper().startswith("TOTAL"):
                tot = r["value"]
        out.append({"edition": ed, "centres_oriented_any": int(tot), "centres_oriented_immigration_ip": int(imm),
                    "share_of_oriented_pct": round(100 * imm / tot, 1)})
    write("situations.csv", out, list(out[0].keys()))
    return out


# ---------------------------------------------------------------------------- revision of the 2024 release
ORIGINAL = {  # Wayback capture 2025-09-26 13:25:24 UTC of https://www.ine.es/dyngs/Prensa/ECAPSH2024.htm
    "occupied_mean": ("33.758", "Una media de 33.758 personas mayores de 18 años se alojó diariamente"),
    "occupied_change_pct": ("55,7", "(un 55,7% más que en 2022)"),
    "centres": ("1.375", "De los 1.375 centros de atención a personas sin hogar en 2024"),
    "accommodation_centres": ("1.119", "1.119 ofrecieron servicios de alojamiento"),
    "imm_places_mean": ("20.911", "ofrecieron una media diaria de 20.911 plazas de alojamiento"),
    "imm_occupied_mean": ("17.786", "con una media de 17.786 plazas ocupadas"),
    "imm_share_centres_pct": ("26,1", "El 26,1% de los centros atendió exclusivamente a personas inmigrantes"),
    "meals_per_day": ("70.343", "sirvieron de media al día 70.343 servicios"),
}
REVISED = {
    "occupied_mean": ("34.145", "Una media de 34.145 personas mayores de 18 años se alojó diariamente"),
    "occupied_change_pct": ("57,5", "57,5 % más que en 2022"),
    "centres": ("1.376", "De los 1.376 centros de atención a personas sin hogar en 2024"),
    "accommodation_centres": ("1.120", "1.120 ofrecieron servicios de alojamiento"),
    "imm_places_mean": ("21.298", "ofrecieron una media diaria de 21.298 plazas de alojamiento"),
    "imm_occupied_mean": ("18.173", "con una media de 18.173 plazas ocupadas"),
    "imm_share_centres_pct": ("26,2", "26,2 % de los centros atendió exclusivamente a personas inmigrantes"),
    "meals_per_day": ("71.121", "sirvieron de media al día 71.121 servicios"),
}


def norm_text(raw: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S | re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def revision():
    orig = norm_text(gzip.decompress((RAW / "wayback" / "ECAPSH2024_20250926132524.htm").read_bytes())
                     .decode("utf-8", "replace"))
    rev = norm_text((RAW / "ine_press" / "ECAPSH2024.htm").read_text(encoding="utf-8"))
    rev_flat = re.sub(r"\s+", " ", rev)
    out = []
    for k in ORIGINAL:
        o, oq = ORIGINAL[k]
        r, rq = REVISED[k]
        assert oq in orig, f"original release lacks «{oq}»"
        # the live page splits numbers into separate elements: compare with spaces removed
        assert re.sub(r"\s", "", rq) in re.sub(r"\s", "", rev_flat), f"revised release lacks «{rq}»"
        f = lambda s: float(s.replace(".", "").replace(",", "."))
        out.append({"indicator": k, "original_2025_09_26": f(o), "revised_2025_10_17": f(r),
                    "difference": round(f(r) - f(o), 1), "original_quote": oq, "revised_quote": rq})
    write("revision_2024.csv", out, list(out[0].keys()))
    return out


# ---------------------------------------------------------------------------- explanatory series
SPI_URL = ("https://www.lamoncloa.gob.es/serviciosdeprensa/notasprensa/inclusion/Documents/2025/"
           "200625-Informe-Sistema-Proteccion-Internacional-Espanol-jun25.pdf")
# Ministerio de Inclusión, «Informe Sistema de Protección Internacional español», 20-Jun-2025,
# Gráfico 1 (SAPI places) and Gráfico 2 (humanitarian programme places). Year-end values except 2025
# (15 June). Text: «Entre el 31 de diciembre de 2024 y el 15 de junio de 2025, estas aumentaron en
# 4.618 plazas (de 29.444 a 34.062)» and «alcanzando en diciembre del pasado año el total de 27.519 plazas».
SAPI = {2015: 1920, 2016: 4629, 2017: 8729, 2018: 11917, 2019: 12561, 2020: 13826, 2021: 12635,
        2022: 29964, 2023: 28600, 2024: 29444, 2025: 34062}
PAH = {2015: 1264, 2016: 1486, 2017: 2272, 2018: 4359, 2019: 4941, 2020: 17913, 2021: 12891,
       2022: 9835, 2023: 22752, 2024: 27519, 2025: 24532}
# Irregular arrivals by land and sea, as cited by AIDA (ECRE) Spain country reports from the Ministry
# of the Interior; Canary Islands by sea where AIDA states it.
ARRIVALS = {
    2019: (32449, None, "AIDA ES 2020 update: «compared to 2019 (32,449 arrivals)»"),
    2020: (41861, None, "AIDA ES 2020 update: «a total of 41,861 persons arrived in Spain in 2020»"),
    2021: (41945, None, "AIDA ES 2021 update: «a total of 41,945 persons arrived in Spain by land and sea in 2021»"),
    2022: (31219, None, "AIDA ES 2022 update: «In 2022, 31,219 migrants arrived to Spain by land and sea»"),
    2023: (56852, 39910, "AIDA ES 2023 update: «In 2023, 56,852 migrants arrived to Spain by land and sea» … «39,910 persons arrived by sea on the archipelago»"),
    2024: (63970, 46843, "AIDA ES 2024 update: «In 2024, 63,970 migrants arrived in Spain by land and sea» … «46,843 persons arrived by sea on the archipelago» (the 2025 update revises 2024 to 64,019)"),
    2025: (36775, 17788, "AIDA ES 2025 update: «In 2025, 36,775 migrants arrived in Spain by land and sea» … «the Canary Islands, with 17,788 persons reaching the archipelago by sea»"),
}


def eurostat_asylum():
    d = json.loads((RAW / "eurostat" / "migr_asyappctza_ES.json").read_text())
    dims, size = d["id"], d["size"]
    idx = {k: d["dimension"][k]["category"]["index"] for k in dims}
    years = {v: k for k, v in idx["time"].items()}
    out = {}
    for code in ("TOTAL", "FRST"):
        a = idx["applicant"][code]
        for t, y in years.items():
            # row-major flat index over all dimensions; only applicant and time vary here
            pos = 0
            for k, n in zip(dims, size):
                i = a if k == "applicant" else (t if k == "time" else 0)
                pos = pos * n + i
            v = d["value"].get(str(pos))
            if v is not None:
                out[(int(y), code)] = int(v)
    return out, d.get("updated")


def explanatory():
    asy, upd = eurostat_asylum()
    out = []
    for y in range(2014, 2026):
        out.append({"year": y,
                    "asylum_applicants_total": asy.get((y, "TOTAL")),
                    "asylum_applicants_first": asy.get((y, "FRST")),
                    "sapi_places": SAPI.get(y), "humanitarian_places": PAH.get(y),
                    "reception_places_total": (SAPI[y] + PAH[y]) if y in SAPI else None,
                    "arrivals_land_sea": ARRIVALS.get(y, (None,))[0],
                    "arrivals_canary_sea": ARRIVALS.get(y, (None, None))[1]})
    write("explanatory.csv", out, list(out[0].keys()))
    src = [{"series": "asylum_applicants_total / _first", "source": f"Eurostat migr_asyappctza (geo=ES, citizen=TOTAL), updated {upd}", "note": "persons; first-time = FRST"},
           {"series": "sapi_places / humanitarian_places", "source": SPI_URL, "note": "Gráficos 1 y 2; year-end except 2025 = 15 June 2025"},
           *[{"series": f"arrivals {y}", "source": "AIDA (ECRE) country report Spain, citing the Ministry of the Interior", "note": q}
             for y, (_, _, q) in ARRIVALS.items()]]
    write("explanatory_sources.csv", src, ["series", "source", "note"])
    return out


if __name__ == "__main__":
    national()
    ine_chart()
    specialisation()
    reference_dates()
    regions()
    region_dates()
    situations()
    revision()
    explanatory()
