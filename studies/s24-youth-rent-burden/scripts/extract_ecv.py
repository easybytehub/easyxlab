#!/usr/bin/env python3
"""S24: read INE's ECV cross-sectional microdata (data/raw/ecv/*.zip) and write one unit-level file per
year with the variables this study uses: data/raw/derived/ecv_persons_<year>.csv.

The derived files hold microdata and stay in data/raw/ (git-ignored). Nothing unit-level is published.

Files per year (EU-SILC layout, as INE distributes them):
  D  household register     DB030 id, DB040 region (NUTS-2), DB090 household weight, DB100 urbanisation
  H  household data         HY020 disposable income (previous calendar year), HY070G housing allowances,
                            HH021 tenure (HH020 before 2010), HH060 current monthly rent, HH070 total
                            monthly housing cost, HH030 rooms, HX040 size, HX240 consumption units
  R  personal register      RB030 id, RB050 weight, RB080 birth year, RB081/RB082 ages (2021+),
                            RB070 birth month (before 2021), RB090 sex, RB220/RB230 father/mother id,
                            RB240 partner id
  P  adults 16+             PB040 weight, PY*N net personal income components, PL031/PL032 activity,
                            PMG4/PMG8 (2025 module on difficulties of access to housing)

Base-2013 files 2008-2025; base-2004 files 2004-2007 (income not comparable with base 2013: used for
living arrangements only). The 2008 archive is 7-Zip: it is read with `tar` (bsdtar/libarchive, as on
macOS); without it, 2008 is skipped with a message.

    python3 scripts/extract_ecv.py            all years present in data/raw/ecv/
    python3 scripts/extract_ecv.py 2025 2024  only these years
"""
from __future__ import annotations

import csv
import io
import re
import subprocess
import sys
import zipfile

from s24lib import RAW

OUT = RAW / "derived"
INC = ["PY010N", "PY020N", "PY050N", "PY080N", "PY090N", "PY100N", "PY110N", "PY120N", "PY130N", "PY140N"]
FIELDS = ["year", "hh", "pid", "w_pers", "w_adult", "w_hh", "region", "urb", "sex", "birth_year",
          "age_end", "age_int", "father", "mother", "partner", "is_resp", "hh_size", "cu", "hy020", "hy070g",
          "vhrentaa", "tenure", "rent", "hcost", "rooms", "interview_month", "py010n", "py010g", "pers_inc",
          "econ", "pmg4", "pmg8", "rb200"]


def _members(z: zipfile.ZipFile, depth=0):
    """Yield (name, opener) for every CSV/TAB inside z, descending into nested zip and 7z archives."""
    for n in z.namelist():
        low = n.lower()
        if low.endswith(".zip") and depth < 3:
            yield from _members(zipfile.ZipFile(io.BytesIO(z.read(n))), depth + 1)
        elif low.endswith(".7z"):
            data = z.read(n)
            tmp = OUT / "_tmp.7z"
            OUT.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(data)
            try:
                lst = subprocess.run(["tar", "-tf", str(tmp)], capture_output=True, text=True, check=True).stdout.split()
            except Exception as e:  # no libarchive tar
                print(f"  cannot open {n} ({e}); skipped", file=sys.stderr)
                continue
            for m in lst:
                if m.lower().endswith(".csv"):
                    yield m, (lambda m=m, tmp=tmp: subprocess.run(["tar", "-xOf", str(tmp), m], capture_output=True,
                                                                   check=True).stdout)
        elif re.search(r"\.(csv|tab)$", low):
            yield n, (lambda z=z, n=n: z.read(n))


def find_files(year: int):
    """Return {kind: bytes} for D, R, H, P. Prefer INE's ECV_T?_<year> file, else the Eurostat-layout esudb."""
    p = RAW / "ecv" / (f"datos_{year}.zip" if year >= 2008 else f"ecvb04_{year}.zip")
    if not p.exists():
        return None
    found: dict[str, tuple[int, object]] = {}
    yy = f"{year % 100:02d}"
    for name, opener in _members(zipfile.ZipFile(p)):
        base = name.rsplit("/", 1)[-1].lower()
        for kind in "drhp":
            if re.fullmatch(rf"ecv_t{kind}_{year}\.(csv|tab)", base):
                rank = 0
            elif re.fullmatch(rf"esudb{yy}{kind}\.csv", base):
                rank = 1
            else:
                continue
            if kind not in found or rank < found[kind][0]:
                found[kind] = (rank, opener)
    if set(found) != set("drhp"):
        print(f"  {year}: files found {sorted(found)}", file=sys.stderr)
        return None
    return {k: v[1]() for k, v in found.items()}


def rows(b: bytes):
    text = b.decode("latin-1")
    first = text.split("\n", 1)[0]
    delim = "\t" if "\t" in first else ","
    rd = csv.reader(io.StringIO(text), delimiter=delim)
    head = [h.strip().strip('"').upper() for h in next(rd)]
    for r in rd:
        if r:
            yield dict(zip(head, (x.strip().strip('"') for x in r)))


def f(x):
    try:
        return float(x.replace(",", ".")) if x not in ("", None) else None
    except ValueError:
        return None


def i(x):
    v = f(x)
    return int(v) if v is not None else None


def extract(year: int) -> int:
    files = find_files(year)
    if files is None:
        return 0
    D = {r["DB030"]: r for r in rows(files["d"])}
    H = {r["HB030"]: r for r in rows(files["h"])}
    P = {r["PB030"]: r for r in rows(files["p"])}
    R = list(rows(files["r"]))
    # members by household, for the composition variables
    out = []
    for r in R:
        # RB200: 1 «Vive actualmente en el hogar», 2 «Ausente temporalmente». Eurostat's household
        # population keeps both; so do we (the first draft kept only 1, see METHOD §3).
        if r.get("RB200", "1") not in ("1", "2", ""):
            continue
        pid = r["RB030"]
        hh = str(int(float(pid)) // 100)
        h, d, p = H.get(hh), D.get(hh), P.get(pid, {})
        if h is None or d is None:
            continue
        by = i(r.get("RB080"))
        if "RB081" in r and r.get("RB081", "") != "":
            age_end, age_int = i(r["RB081"]), i(r.get("RB082"))
        else:
            age_end = year - 1 - by if by is not None else None
            bm, im = i(r.get("RB070")), i(h.get("HB050"))
            age_int = (year - by - (1 if (bm and im and bm > im) else 0)) if by is not None else None
        ten = i(h.get("HH021"))
        if ten is None and h.get("HH020", "") != "":
            ten = {1: 0, 2: 3, 3: 4, 4: 5}.get(i(h["HH020"]))       # 0 = owner (mortgage not recorded)
        pinc = None
        if p:
            vals = [f(p.get(k, "")) for k in INC]
            pinc = sum(v for v in vals if v is not None)
        econ = p.get("PL032") or p.get("PL031") or ""
        out.append({
            "year": year, "hh": hh, "pid": pid, "w_pers": f(r.get("RB050")), "w_adult": f(p.get("PB040", "")),
            "w_hh": f(d.get("DB090")), "region": d.get("DB040", ""), "urb": d.get("DB100", ""),
            "sex": r.get("RB090", ""), "birth_year": by, "age_end": age_end, "age_int": age_int,
            "father": i(r.get("RB220")) or "", "mother": i(r.get("RB230")) or "", "partner": i(r.get("RB240")) or "",
            "is_resp": int(h.get("HB080", "") != "" and i(h.get("HB080")) == i(pid)),
            "hh_size": i(h.get("HX040")), "cu": f(h.get("HX240", "")), "hy020": f(h.get("HY020")),
            "hy070g": f(h.get("HY070G", "")), "vhrentaa": f(h.get("VHRENTAA", "")), "tenure": ten if ten is not None else "",
            "rent": f(h.get("HH060", "")), "hcost": f(h.get("HH070", "")), "rooms": f(h.get("HH030", "")),
            "interview_month": i(h.get("HB050")), "py010n": f(p.get("PY010N", "")), "py010g": f(p.get("PY010G", "")),
            "pers_inc": pinc, "econ": econ, "pmg4": p.get("PMG4", ""), "pmg8": p.get("PMG8", ""),
            "rb200": r.get("RB200", ""),
        })
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"ecv_persons_{year}.csv", "w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=FIELDS)
        w.writeheader()
        for o in out:
            w.writerow({k: ("" if o[k] is None else o[k]) for k in FIELDS})
    return len(out)


def main(argv):
    years = [int(a) for a in argv] or list(range(2004, 2026))
    for y in years:
        n = extract(y)
        print(f"{y}: {n} persons", flush=True)
    tmp = OUT / "_tmp.7z"
    if tmp.exists():
        tmp.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
