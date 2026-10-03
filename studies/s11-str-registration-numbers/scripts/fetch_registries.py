#!/usr/bin/env python3
"""Download the official registries used by S11 and keep ONLY the columns needed to match a
registration number (number, type, municipality, province, dates, status). Columns with
personal data (holders' names, e-mails, phones, tax ids) or exact addresses are never written to
disk: the files are filtered while streaming. Output: data/raw/registries/*_min.csv (git-ignored)
and data/sources_registries.json (publishable metadata: URL, fetch time, rows, sha256).

    python3 scripts/fetch_registries.py [rtc gva rta ose]
"""
import csv, io, json, os, sys, time, hashlib, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import polite
csv.field_size_limit(10**9)
OUT = "data/raw/registries"
META = "data/sources_registries.json"
os.makedirs(OUT, exist_ok=True)
FIELDS = ["number", "type", "municipality", "municipality_code", "province", "date", "status", "extra"]


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def write(name, rows, meta):
    path = f"{OUT}/{name}_min.csv"
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: (r.get(k) or "") for k in FIELDS}); n += 1
    meta.update({"file": path, "rows": n, "sha256": sha(path)})
    try:
        allm = json.load(open(META))
    except Exception:
        allm = {}
    allm[name] = meta
    json.dump(allm, open(META, "w"), indent=1, ensure_ascii=False)
    print(name, n, "rows")


def rtc():
    """Registre de Turisme de Catalunya (Socrata t2h3-cgys), selected columns only."""
    cols = "tipus_establiment,n_mero_inscripci,d_git_de_control,estat,municipi,codi_municipi_idescat,prov_ncia,unitat_d_allotjament,total_places"
    url = ("https://analisi.transparenciacatalunya.cat/resource/t2h3-cgys.csv?$select=" + cols +
           "&$limit=500000&$order=:id")
    view = "https://analisi.transparenciacatalunya.cat/api/views/t2h3-cgys.json"
    polite.fetch(view, "work/rtc_view.json")
    v = json.load(open("work/rtc_view.json"))
    t = now()
    resp = polite.open_stream(url)
    rd = csv.DictReader(io.TextIOWrapper(resp, encoding="utf-8", newline=""))

    def rows():
        for r in rd:
            yield {"number": r["n_mero_inscripci"], "type": r["tipus_establiment"], "municipality": r["municipi"],
                   "municipality_code": r["codi_municipi_idescat"], "province": r["prov_ncia"],
                   "status": r["estat"], "extra": r["d_git_de_control"]}
    write("rtc", rows(), {"name": v.get("name"), "url": url, "fetched_utc": t,
                          "rows_updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(v.get("rowsUpdatedAt", 0))),
                          "licence_metadata": v.get("license", {}).get("name"), "licence_link": v.get("attributionLink"),
                          "attribution": v.get("attribution"),
                          "columns_kept": cols, "extra": "dígit de control"})


def gva():
    """Viviendas turísticas, Comunitat Valenciana (CKAN tur-gestur-vt), selected columns only."""
    url = ("https://dadesobertes.gva.es/dataset/758f8f8e-c5af-4622-b268-a6c591710a51/resource/"
           "b1bdc28e-9813-422a-ab7a-63c21290493d/download/lista-de-viviendas-turisticas.csv")
    t = now()
    resp = polite.open_stream(url)
    rd = csv.DictReader(io.TextIOWrapper(resp, encoding="utf-8-sig", newline=""), delimiter=";")

    def rows():
        for r in rd:
            d = r["fecha_alta"].strip()
            m = re.match(r"(\d{2})/(\d{2})/(\d{4})", d)
            yield {"number": r["signatura"], "type": "VUT", "municipality": r["municipio"],
                   "municipality_code": r["cod_municipio"], "province": r["provincia"],
                   "date": f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else d}
    write("gva", rows(), {"name": "Viviendas turísticas de la Comunitat Valenciana (tur-gestur-vt)", "url": url,
                          "fetched_utc": t, "licence_metadata": "cc-by (CKAN license_id; license_url http://www.opendefinition.org/licenses/cc-by)",
                          "columns_kept": "signatura,cod_municipio,municipio,provincia,fecha_alta"})


def rta():
    """OpenRTA, Registro de Turismo de Andalucía. The CSV mixes two row layouts: 72 fields that
    follow the header, and 92 fields that do not (positions identified by value patterns, see
    METHOD.md). Holders, e-mails, phones and addresses are dropped while streaming."""
    url = "https://datos.juntadeandalucia.es/api/v0/openrta/all?format=csv"
    t = now()
    try:
        polite.fetch("https://datos.juntadeandalucia.es/api/v0/openrta/search/lastUpdateData", "work/rta_last_update.json")
        last = open("work/rta_last_update.json").read()[:200]
    except Exception as e:
        last = f"error {e}"
    resp = polite.open_stream(url)
    rd = csv.reader(io.TextIOWrapper(resp, encoding="utf-8", newline=""), delimiter="|")
    hdr = next(rd)
    H = {k: i for i, k in enumerate(hdr)}
    shapes = {"72": 0, "92": 0, "other": 0}

    def rows():
        for r in rd:
            if len(r) == len(hdr):
                shapes["72"] += 1
                yield {"number": r[H["registration_code"]], "type": r[H["objects_type_id"]],
                       "municipality": r[H["municipalities"]], "province": r[H["provinces"]], "extra": r[H["group"]]}
            elif len(r) == 92:
                shapes["92"] += 1
                yield {"number": r[69], "type": r[60], "municipality": r[51], "province": r[67], "extra": r[17]}
            else:
                shapes["other"] += 1
    write("rta", rows(), {"name": "OpenRTA, Registro de Turismo de Andalucía", "url": url, "fetched_utc": t,
                          "last_update_endpoint": last,
                          "licence_metadata": "CC BY 4.0 (CKAN: http://creativecommons.org/licenses/by/4.0/deed.es_ES)",
                          "columns_kept": "registration_code, object type, municipality, province, group",
                          "row_layouts": shapes})


def ose():
    """NYC Office of Special Enforcement STR registration dataset as of 25 June 2025 (the most
    recent copy we could obtain: nyc.gov answers 403 to our User-Agent, so the file comes from the
    Internet Archive capture of 2025-11-08). Street address, unit and BIN are dropped."""
    import openpyxl
    url = ("https://web.archive.org/web/20251108004747id_/https://www.nyc.gov/assets/specialenforcement/"
           "downloads/excel/June_25_2025_STR_Registration_Dataset.xlsx")
    raw = "work/ose_June_25_2025.xlsx"
    t = now()
    polite.fetch(url, raw)
    wb = openpyxl.load_workbook(raw, read_only=True)
    ws = wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    title = next(it)[0]
    hdr = next(it)

    def rows():
        cur = None
        for r in it:
            d = dict(zip(hdr, r))
            if d.get("Registration Number"):
                cur = {"number": str(d["Registration Number"]).strip(), "status": d.get("STRR Status"),
                       "province": d.get("Borough"), "municipality_code": str(d.get("Zip Code") or ""),
                       "date": str(d.get("Registration Expiration Date") or "")}
                yield dict(cur, type="registration", extra="")
            if cur and d.get("Listing URL or Listing Number"):
                yield {"number": cur["number"], "type": "listing:" + str(d.get("Booking service") or ""),
                       "extra": str(d["Listing URL or Listing Number"]).strip()}
    write("ose", rows(), {"name": title, "url": url, "fetched_utc": t,
                          "original_url": "https://www.nyc.gov/assets/specialenforcement/downloads/excel/June_25_2025_STR_Registration_Dataset.xlsx",
                          "note": "rows of type 'registration' carry number, status, borough, zip, expiration date; rows of type 'listing:<service>' carry the listing number OSE associates with that registration",
                          "columns_dropped": "Street Address, Unit Number, BIN"})
    os.remove(raw)


if __name__ == "__main__":
    todo = sys.argv[1:] or ["rtc", "gva", "rta", "ose"]
    for name in todo:
        globals()[name]()
