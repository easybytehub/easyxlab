#!/usr/bin/env python3
"""S10 step 1 — census of NeTEx datasets published by national access points (NAPs).

Queries every NAP catalogue that is reachable without registration, keeps the raw
catalogue responses in work/raw_catalogs/ (not published: they contain contact details) and writes one row per NeTEx resource to
data/catalogue_netex.csv. Sizes come from the catalogue when it states them; otherwise
from an HTTP HEAD (or a GET whose body is not read) on the download URL.

Licence is recorded only when the catalogue exposes it in machine-readable form.
"""
import csv, json, re, sys, time, os
import requests

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# raw responses contain third-party contact details (incl. personal e-mails): kept out of data/,
# never published; only derived, contact-free CSVs go to data/
RAW = os.path.join(S, "work", "raw_catalogs")
os.makedirs(RAW, exist_ok=True)
UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
H = {"User-Agent": UA}
sess = requests.Session(); sess.headers.update(H)
rows, probes = [], []


def get(url, name=None, **kw):
    time.sleep(0.5)
    r = sess.get(url, timeout=90, **kw)
    if name:
        with open(os.path.join(RAW, name), "wb") as f:
            f.write(r.content)
    return r


def head_size(url):
    """Content-Length of the download, without downloading the body."""
    time.sleep(0.3)
    try:
        r = sess.head(url, allow_redirects=True, timeout=30)
        cl = r.headers.get("Content-Length")
        if r.status_code < 400 and cl and int(cl) > 0:
            return int(cl), r.status_code, r.headers.get("Last-Modified", "")
        r = sess.get(url, allow_redirects=True, timeout=30, stream=True)
        cl = r.headers.get("Content-Length"); r.close()
        return (int(cl) if cl else None), r.status_code, r.headers.get("Last-Modified", "")
    except Exception as e:
        return None, f"ERR {type(e).__name__}", ""


def add(**kw):
    base = dict(country="", nap="", dataset_id="", title="", publisher="", licence="",
                updated="", size_bytes="", size_source="", http_status="", url="", note="")
    base.update(kw); rows.append(base)


# ---------- France: transport.data.gouv.fr ----------
fr = get("https://transport.data.gouv.fr/api/datasets", "fr_transport_data_gouv.json").json()
seen = set()
for d in fr:
    pub = d.get("publisher") or {}
    pubname = pub.get("name") if isinstance(pub, dict) else str(pub)
    for r in d["resources"]:
        if (r.get("format") or "").lower() != "netex":
            continue
        key = r.get("original_url") or r["url"]
        if key in seen:
            continue
        seen.add(key)
        size, st, lm = head_size(r["url"])
        add(country="FR", nap="transport.data.gouv.fr", dataset_id=f"{d['id']}/{r['id']}",
            title=f"{d['title']} — {r.get('title','')}"[:200], publisher=pubname or "",
            licence=d.get("licence") or "", updated=(r.get("updated") or "")[:10],
            size_bytes=size or "", size_source="http-head" if size else "", http_status=st,
            url=r["url"], note=f"type={d.get('type')};available={r.get('is_available')}")
print("FR", sum(1 for x in rows if x["country"] == "FR"), file=sys.stderr)

# ---------- Norway (EEA): Entur public bucket ----------
no = get("https://storage.googleapis.com/storage/v1/b/marduk-production/o?prefix=outbound/netex/&maxResults=1000",
         "no_entur_bucket.json").json()
for o in no.get("items", []):
    add(country="NO", nap="Entur (data.entur.no)", dataset_id=o["name"], title=o["name"].split("/")[-1],
        publisher="Entur / codespace " + o["name"].split("/")[-1].split("-")[0].replace("rb_", "").upper(),
        licence="", updated=o["updated"][:10], size_bytes=o["size"], size_source="catalogue",
        url=o["mediaLink"], note="licence not machine-readable in bucket listing")

# ---------- Netherlands: NDOV Loket ----------
UNIT = {"": 1, "K": 1e3, "M": 1e6, "G": 1e9}
root = get("https://data.ndovloket.nl/netex/", "nl_ndovloket_root.html").text
for sub in re.findall(r'href="([a-z0-9_-]+/)"', root):
    html = get("https://data.ndovloket.nl/netex/" + sub).text
    with open(os.path.join(RAW, f"nl_ndovloket_{sub.strip('/')}.html"), "w") as f:
        f.write(html)
    flat = re.sub(r"\s+", " ", html)
    for name, date, num, unit in re.findall(
            r'<a class="link" href="([^"]+)">[^<]*</a> </td> <td> <span class="date">([^<]+)</span> </td> '
            r'<td class="size"> <span class="size">([\d.]+)</span><span class="unit">\.?([\d]*[KMG]?)</span>', flat):
        if name.endswith("/") or not re.search(r"(?i)netex", name):
            continue
        u = unit[-1] if unit and unit[-1] in "KMG" else ""
        frac = unit[:-1] if u else unit
        val = float(num + ("." + frac if frac else ""))
        add(country="NL", nap="NDOV Loket", dataset_id=sub + name, title=name, publisher=sub.strip("/").upper(),
            updated=time.strftime("%Y-%m-%d", time.strptime(date, "%d-%b-%Y %H:%M")),
            size_bytes=int(val * UNIT[u]), size_source="catalogue (rounded)",
            url="https://data.ndovloket.nl/netex/" + sub + name, note="licence not machine-readable")

# ---------- Belgium: transportdata.be (CKAN) ----------
be = get("https://www.transportdata.be/api/3/action/package_search?q=netex&rows=100", "be_transportdata.json").json()
for p in be["result"]["results"]:
    for r in p.get("resources", []):
        fmt = (r.get("format") or "") + " " + (r.get("name") or "") + " " + (r.get("url") or "")
        if not re.search(r"(?i)netex", fmt + p["name"]):
            continue
        size = r.get("size"); src = "catalogue" if size else ""
        st = ""
        if not size and r.get("url", "").startswith("http"):
            size, st, _ = head_size(r["url"]); src = "http-head" if size else ""
        add(country="BE", nap="transportdata.be", dataset_id=f"{p['name']}/{r.get('id','')}",
            title=f"{p['title']} — {r.get('name','')}"[:200], publisher=(p.get("organization") or {}).get("title", ""),
            licence=p.get("license_id") or p.get("license_title") or "",
            updated=(r.get("last_modified") or r.get("metadata_modified") or p.get("metadata_modified") or "")[:10],
            size_bytes=size or "", size_source=src, http_status=st, url=r.get("url", ""),
            note=f"format={r.get('format')}")

# ---------- Luxembourg: data.public.lu (udata) ----------
lu = get("https://data.public.lu/api/1/datasets/?q=netex&page_size=50", "lu_data_public.json").json()
for d in lu["data"]:
    for r in d["resources"]:
        add(country="LU", nap="data.public.lu (mobiliteit.lu)", dataset_id=f"{d['id']}/{r['id']}",
            title=f"{d['title']} — {r['title']}"[:200], publisher=(d.get("organization") or {}).get("name", ""),
            licence=d.get("license", ""), updated=(r.get("last_modified") or "")[:10],
            size_bytes=r.get("filesize") or "", size_source="catalogue", url=r["url"], note=f"format={r.get('format')}")

# ---------- Germany: Mobilithek (free-text search, no registration) ----------
de = sess.post("https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search",
               json={"searchString": "NeTEx"}, timeout=90)
open(os.path.join(RAW, "de_mobilithek_search.json"), "wb").write(de.content)
for o in de.json()["dataOffers"]["content"]:
    add(country="DE", nap="Mobilithek", dataset_id=o["publicationId"], title=o["title"],
        publisher=o["agents"]["publisher"]["name"], licence=o.get("rights", "").split("#")[-1],
        updated=(o.get("modified") or o.get("created") or "")[:10], size_bytes="", size_source="",
        url="https://mobilithek.info/offers/" + o["publicationId"],
        note=f"category={o.get('dataCategory','').split('#')[-1]};brokering={o.get('mdpBrokering')}")

# ---------- access probes for NAPs without an anonymous catalogue ----------
for country, nap, url in [
    ("ES", "nap.transportes.gob.es", "https://nap.transportes.gob.es/api/Fichero/GetList"),
    ("FI", "finap.fi", "https://finap.fi/api/service-search?text=netex"),
    ("SE", "Trafiklab / Samtrafiken", "https://opendata.samtrafiken.se/netex-sweden/sweden.zip"),
    ("AT", "mobilitydata.gv.at", "https://www.mobilitydata.gv.at/api/3/action/package_search?q=netex"),
    ("CH", "opentransportdata.swiss", "https://opentransportdata.swiss/api/3/action/package_search?q=netex"),
    ("EU", "data.europa.eu (format facet 'netex')",
     'https://data.europa.eu/api/hub/search/search?filter=dataset&limit=1&facets={"format":["netex"]}'),
]:
    try:
        r = get(url); st = r.status_code
        extra = ""
        if country == "EU" and st == 200:
            res = r.json()["result"]
            cc = [f"{i['id']}:{i['count']}" for f in res["facets"] if f["id"] == "country" for i in f["items"]]
            extra = f"count={res['count']};countries={'|'.join(cc)}"
    except Exception as e:
        st, extra = f"ERR {type(e).__name__}", ""
    probes.append(dict(country=country, nap=nap, url=url, http_status=st, note=extra))

cols = list(rows[0].keys())
with open(os.path.join(S, "data", "catalogue_netex.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
with open(os.path.join(S, "data", "nap_access_probes.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["country", "nap", "url", "http_status", "note"]); w.writeheader(); w.writerows(probes)
print(f"{len(rows)} NeTEx resources; probes: {[(p['country'], p['http_status']) for p in probes]}", file=sys.stderr)
