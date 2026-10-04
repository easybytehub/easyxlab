#!/usr/bin/env python3
"""Download today's copy of the Comunitat Valenciana tourist-dwelling registry (GVA open data,
dataset tur-gestur-vt, CC BY) and keep ONLY non-personal columns.

The source CSV also carries the dwelling's name (sometimes a person's name), street address
with floor and door, cadastral reference and website. Those columns are dropped while
streaming: they never reach the disk. Three non-identifying fields are derived from them in
memory first (see unit_kind() and METHOD.md):
  unit_kind   whole_parcel | in_building | unknown, from the cadastral-style unit part of the
              address ("ES:<stair> PL:<floor> PT:<door>"); "PL:OD PT:OS" marks a property that
              is not divided into units
  cargo0001   1 if the cadastral reference's unit number (characters 15-18) is 0001
  parcel_n    how many dwellings in this copy of the registry share the 14-character cadastral
              parcel (0 if the reference is missing)
  bkey        a salted hash of municipality + address without its unit part (the building).
              The salt is random for every run and never stored, so the key only says which
              dwellings of one copy share a building; it cannot be reversed or linked
  has_ref     1 if the cadastral reference is filled in

Output (git-ignored): data/raw/registries/gva_min_<YYYY-MM-DD>.csv
Publishable metadata: data/sources.json (URL, fetch time, rows, SHA-256 of the minimal file).

    python3 scripts/fetch_gva.py              today's copy from dadesobertes.gva.es
    python3 scripts/fetch_gva.py wayback      every copy of the CSV held by the Internet Archive
                                              (found with the CDX API), same column filter
    python3 scripts/fetch_gva.py sidecar DAY  bkey and has_ref, from today's file, for the dwellings
                                              of an older copy that lacks them (written to
                                              gva_bkey_<DAY>.csv)
"""
import csv, gzip, io, json, os, re, sys, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import polite
from s13lib import unit_kind, building_text

URL = ("https://dadesobertes.gva.es/dataset/758f8f8e-c5af-4622-b268-a6c591710a51/resource/"
       "b1bdc28e-9813-422a-ab7a-63c21290493d/download/lista-de-viviendas-turisticas.csv")
KEEP = ["signatura", "cod_provincia", "cod_municipio", "municipio", "provincia", "fecha_alta",
        "plazas_totales", "rural"]
DERIVED = ["unit_kind", "cargo0001", "parcel_n", "bkey", "has_ref"]

OUTDIR = "data/raw/registries"


def iso(d):
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", d.strip())
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else d.strip()


def bkey(salt, r):
    return hashlib.sha256(salt + ((r.get("municipio") or "") + "|" + building_text(r.get("direccion"))).encode()).hexdigest()[:16]


def reader(url):
    resp = io.BufferedReader(polite.open_stream(url), 1 << 20)
    if resp.peek(2)[:2] == b"\x1f\x8b":      # the Internet Archive serves the stored gzip body
        resp = gzip.GzipFile(fileobj=resp)
    return csv.DictReader(io.TextIOWrapper(resp, encoding="utf-8-sig", newline=""), delimiter=";")


def ingest(url, day, source, t):
    os.makedirs(OUTDIR, exist_ok=True)
    out = f"{OUTDIR}/gva_min_{day}.csv"
    salt = os.urandom(16)
    rd = reader(url)
    cols = rd.fieldnames
    rows, parcels = [], {}
    for r in rd:                                   # personal columns live only in this loop
        row = [r.get(k, "") or "" for k in KEEP]
        row[KEEP.index("fecha_alta")] = iso(row[KEEP.index("fecha_alta")])
        ref = (r.get("ref_catastral") or "").strip().upper()
        p14 = ref[:14] if len(ref) >= 14 else ""
        if p14:
            parcels[p14] = parcels.get(p14, 0) + 1
        rows.append((row, unit_kind(r.get("direccion")), int(ref[14:18] == "0001"), p14, bkey(salt, r), int(bool(ref))))
    n = 0
    with open(out + ".part", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(KEEP + DERIVED)
        for row, uk, c1, p14, bk, hr in rows:
            w.writerow(row + [uk, c1, parcels.get(p14, 0), bk, hr])
            n += 1
    del rows, parcels
    os.replace(out + ".part", out)
    sha = hashlib.sha256(open(out, "rb").read()).hexdigest()
    try:
        meta = json.load(open("data/sources.json"))
    except Exception:
        meta = {}
    meta.setdefault("gva_snapshots", {})[day] = {
        "source": source, "url": url, "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", t), "rows": n,
        "source_columns": cols, "columns_kept": KEEP, "columns_derived": DERIVED, "sha256_minimal_file": sha,
        "licence": "Creative Commons Attribution (CKAN license_id cc-by), dadesobertes.gva.es"}
    json.dump(meta, open("data/sources.json", "w"), indent=1, ensure_ascii=False)
    print(out, n, "rows", sha)


def wayback():
    """Copies of the CSV in the Internet Archive (CDX API), read through the raw 'id_' URL."""
    q = ("https://web.archive.org/cdx/search/cdx?url=" + URL.replace("https://", "") +
         "&output=json&fl=timestamp,statuscode,digest&filter=statuscode:200")
    os.makedirs("work", exist_ok=True)
    polite.fetch(q, "work/cdx_gva_csv.json")
    rows = json.load(open("work/cdx_gva_csv.json"))[1:]
    for ts, _, _ in rows:
        day = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        ingest(f"https://web.archive.org/web/{ts}id_/{URL}", day, f"Internet Archive capture {ts}", time.gmtime())


def sidecar(day):
    """bkey and has_ref for the dwellings of the copy gva_min_<day>.csv, read from today's file."""
    want = {r["signatura"] for r in csv.DictReader(open(f"{OUTDIR}/gva_min_{day}.csv", encoding="utf-8"))}
    salt = os.urandom(16)
    out = f"{OUTDIR}/gva_bkey_{day}.csv"
    n = 0
    with open(out + ".part", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["signatura", "bkey", "has_ref"])
        for r in reader(URL):
            if r["signatura"] in want:
                w.writerow([r["signatura"], bkey(salt, r), int(bool((r.get("ref_catastral") or "").strip()))])
                n += 1
    os.replace(out + ".part", out)
    print(out, n, "of", len(want), "dwellings matched")


if __name__ == "__main__":
    if sys.argv[1:] == ["wayback"]:
        wayback()
    elif sys.argv[1:2] == ["sidecar"]:
        sidecar(sys.argv[2])
    else:
        t = time.gmtime()
        ingest(URL, time.strftime("%Y-%m-%d", t), "dadesobertes.gva.es", t)
