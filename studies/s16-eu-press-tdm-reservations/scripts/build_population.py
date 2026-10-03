#!/usr/bin/env python3
"""S16 population frame: EU-27 news publishers from Wikidata, filtered by the Chrome UX Report
(CrUX) top list of their own country.

  python3 scripts/build_population.py fetch   # QLever (Wikidata) + 27 CrUX country lists -> data/raw/
  python3 scripts/build_population.py build   # data/raw/ -> data/frame.csv, data/exclusions.csv

Every request goes through politefetch (robots.txt first). query.wikidata.org is NOT used: its
robots.txt says "Disallow: /sparql". The same Wikidata graph is queried at QLever (University of
Freiburg), whose host serves no robots.txt (404 = no restrictions, RFC 9309 s. 2.3.1.3).
"""
import csv
import gzip
import io
import json
import os
import re
import sys
import urllib.parse
from collections import defaultdict

import politefetch as P

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data", "raw")
DATA = os.path.join(ROOT, "data")

EU27 = {  # Wikidata QID -> ISO 3166-1 alpha-2 (lower case, as in the CrUX country lists)
    "Q40": "at", "Q31": "be", "Q219": "bg", "Q224": "hr", "Q229": "cy", "Q213": "cz", "Q35": "dk",
    "Q191": "ee", "Q33": "fi", "Q142": "fr", "Q183": "de", "Q41": "gr", "Q28": "hu", "Q27": "ie",
    "Q38": "it", "Q211": "lv", "Q37": "lt", "Q32": "lu", "Q233": "mt", "Q55": "nl", "Q36": "pl",
    "Q45": "pt", "Q218": "ro", "Q214": "sk", "Q215": "si", "Q29": "es", "Q34": "se"}
CRUX_MONTH = "202608"          # latest monthly list in zakird/crux-top-lists on 2026-10-03
RANK_MAX = 100_000             # frame: origin in the top-100K bucket (or better) of its own country
QLEVER = "https://qlever.cs.uni-freiburg.de/api/wikidata"

QUERY = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
SELECT ?item ?country ?website ?sitelinks (SAMPLE(?lbl) AS ?label) WHERE {
  { ?item wdt:P31/wdt:P279* wd:Q11032 }          # newspaper, incl. daily, weekly, free... (subclasses)
  UNION { ?item wdt:P31 wd:Q1153191 }             # online newspaper
  UNION { ?item wdt:P31 wd:Q17232649 }            # news website
  UNION { ?item wdt:P31 wd:Q1684600 }             # news magazine
  { ?item wdt:P17 ?country } UNION { ?item wdt:P495 ?country }
  VALUES ?country { %s }
  ?item wdt:P856 ?website .
  FILTER NOT EXISTS { ?item wdt:P576 ?d1 }         # dissolved, abolished or demolished date
  FILTER NOT EXISTS { ?item wdt:P2669 ?d2 }        # discontinued date
  OPTIONAL { ?item wikibase:sitelinks ?sitelinks }
  OPTIONAL { ?item rdfs:label ?lbl . FILTER(LANG(?lbl) = "en") }
} GROUP BY ?item ?country ?website ?sitelinks""" % " ".join("wd:" + q for q in EU27)

SNAPSHOT_QUERY = """PREFIX schema: <http://schema.org/>
SELECT ?d WHERE { <http://wikiba.se/ontology#Dump> schema:dateModified ?d }"""

# Hosts that are not an outlet's own site: libraries and digitised-newspaper archives, document
# and blog platforms, social networks, encyclopaedias. Matched on the host or any parent domain.
PLATFORM_DOMAINS = {
    # libraries / digitised archives
    "onb.ac.at", "bnf.fr", "retronews.fr", "delpher.nl", "kb.nl", "kb.se", "nb.no", "bne.es",
    "deutsche-digitale-bibliothek.de", "digitale-sammlungen.de", "staatsbibliothek-berlin.de",
    "europeana.eu", "archive.org", "kansalliskirjasto.fi", "dlib.si", "polona.pl", "arcanum.com",
    "e-newspaperarchives.ch", "uni-heidelberg.de", "ub.uni-koeln.de", "difmoe.eu", "digitalniknihovna.cz",
    "kramerius.cz", "mzk.cz", "nkp.cz", "bl.uk", "nli.ie", "irishnewsarchive.com", "chroniclingamerica.loc.gov",
    "loc.gov", "hemerotecadigital.bne.es", "csic.es", "periodicos.ufsc.br", "dlibra.pl", "fbc.pionier.net.pl",
    "pbc.gda.pl", "sbc.org.pl", "ebuh.uni.opole.pl", "jbc.bj.uj.edu.pl", "rcin.org.pl", "digar.ee", "periodika.lv",
    "epaveldas.lt", "eluxemburgensia.lu", "anno.onb.ac.at", "zefys.staatsbibliothek-berlin.de",
    "nebis.ch", "dnb.de", "bsb-muenchen.de", "mdz-nbn-resolving.de", "slub-dresden.de", "ulb.tu-darmstadt.de",
    "digi.ub.uni-heidelberg.de", "bibliotecadigital", "hemeroteca", "biblioteca", "bibliothek",
    # platforms
    "issuu.com", "calameo.com", "yumpu.com", "wikipedia.org", "wikimedia.org", "facebook.com", "twitter.com",
    "x.com", "instagram.com", "youtube.com", "linkedin.com", "google.com", "blogspot.com", "wordpress.com",
    "medium.com", "substack.com", "tumblr.com", "wix.com", "t.me", "telegram.me", "tiktok.com",
}
# Official gazettes are classed under "newspaper" in Wikidata but are published by public bodies,
# not by news publishers.
GAZETTE_HOSTS = {"www.boe.es", "boe.es", "www.journal-officiel.gouv.fr", "www.gazzettaufficiale.it",
                 "gazzettaufficiale.it"}
# Deviation D6 (2026-10-03, after the independent review): the frozen rule E7 was implemented with
# the hand list above only. It is now completed with (a) every Wikidata item of class "government
# gazette" (Q2065227, incl. subclasses) with an EU-27 country, from a QLever query run on 2026-10-03
# (data/raw/gazette_class_query.json), (b) the Staatscourant, whose item lacks that class, and
# (c) Das Parlament, published by the German Bundestag (a public body).
D6_HOSTS = {
    "bop.dipsoria.es", "diariodarepublica.pt", "docm.jccm.es", "dogc.gencat.cat", "dogv.gva.es",
    "legilux.public.lu", "magyarkozlony.hu", "monitoruloficial.ro", "www.boa.aragon.es", "www.bocm.es",
    "www.bodacc.fr", "www.boplaspalmas.net", "www.borm.es", "www.ejustice.just.fgov.be", "www.irisoifigiuil.ie",
    "www.recht.bund.de", "www.staatsanzeiger.de", "www.statstidende.dk", "www.uradni-list.si",
    "www.virallinenlehti.fi",                                    # (a) class Q2065227
    "www.officielebekendmakingen.nl",                            # (b) Staatscourant
    "www.das-parlament.de",                                      # (c) Deutscher Bundestag
}
GOV = re.compile(r"(?:^|\.)(?:gouv|gov|gob)\.[a-z]{2,3}$|\.gov$|(?:^|\.)gv\.at$")
LANG_SEG = re.compile(r"^/(?:[a-z]{2}(?:[-_][a-z]{2})?|index\.\w+|home(?:page)?)?/?$", re.I)


def fetch():
    os.makedirs(RAW, exist_ok=True)
    s = P.Session(per_host=60)
    r = s.get(QLEVER + "?query=" + urllib.parse.quote(SNAPSHOT_QUERY),
              headers={"Accept": "application/sparql-results+json"})
    snap = json.loads(r["body"])["results"]["bindings"]
    r = s.get(QLEVER + "?query=" + urllib.parse.quote(QUERY), limit=200_000_000,
              headers={"Accept": "application/sparql-results+json"})
    if r["status"] != 200:
        raise SystemExit(f"QLever: {r['status']} {r['error']} {r['body'][:300]!r}")
    res = json.loads(r["body"])
    res["_snapshot"] = snap
    res["_query"] = QUERY
    with open(os.path.join(RAW, "wikidata_news_eu27.json"), "w") as f:
        json.dump(res, f)
    print("wikidata rows:", len(res["results"]["bindings"]), "snapshot:", snap, file=sys.stderr)
    # CrUX: keep only origins at rank <= 1M of each EU-27 country (stream, never stored whole)
    out = gzip.open(os.path.join(RAW, "crux_eu27.csv.gz"), "wt", newline="")
    w = csv.writer(out)
    w.writerow(["country", "origin", "rank"])
    for cc in sorted(set(EU27.values())):
        url = f"https://raw.githubusercontent.com/zakird/crux-top-lists/main/data/country/{cc}/{CRUX_MONTH}.csv.gz"
        r = s.get(url, limit=60_000_000, decode=False)
        if r["status"] != 200:
            raise SystemExit(f"CrUX {cc}: {r['status']} {r['error']}")
        body = r["body"]
        try:
            body = gzip.decompress(body)
        except OSError:
            pass                    # politefetch already decompressed a gzip-encoded body
        n = 0
        for row in csv.reader(io.StringIO(body.decode("utf-8", "replace"))):
            if len(row) >= 2 and row[0].startswith("http"):
                w.writerow([cc, row[0], row[-1]])
                n += 1
        print(cc, n, file=sys.stderr)
        del body
    out.close()


def host_of(url):
    try:
        return P.authority(url.strip())
    except Exception:  # noqa: BLE001
        return ""


def platform(host):
    parts = host.split(".")
    parents = {".".join(parts[i:]) for i in range(len(parts))}
    if parents & PLATFORM_DOMAINS:
        return True
    return any(k in host for k in ("bibliotecadigital", "hemeroteca", "biblioteca", "bibliothek", "archiv"))


def build():
    res = json.load(open(os.path.join(RAW, "wikidata_news_eu27.json")))
    snap = max((x["d"]["value"] for x in res.get("_snapshot", [])), default="")
    crux = {}                                  # (cc, host) -> best rank
    for row in csv.DictReader(gzip.open(os.path.join(RAW, "crux_eu27.csv.gz"), "rt")):
        h = host_of(row["origin"])
        k = (row["country"], h)
        r = int(row["rank"])
        if k not in crux or r < crux[k]:
            crux[k] = r
    excl = []
    cand = defaultdict(list)                   # item -> [(rank, cc, host, website)]
    meta = {}
    items_seen = set()
    for b in res["results"]["bindings"]:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        cqid = b["country"]["value"].rsplit("/", 1)[-1]
        cc = EU27.get(cqid)
        web = b["website"]["value"]
        items_seen.add(qid)
        meta[qid] = (b.get("label", {}).get("value", ""), int(b.get("sitelinks", {}).get("value", 0) or 0))
        h = host_of(web)
        path = urllib.parse.urlsplit(web).path
        q = urllib.parse.urlsplit(web).query
        if not h or not web.lower().startswith("http"):
            excl.append((qid, cc, web, "E1 website is not an http(s) URL")); continue
        if platform(h):
            excl.append((qid, cc, web, "E2 host is a library, archive or third-party platform")); continue
        if h in GAZETTE_HOSTS or GOV.search(h):
            excl.append((qid, cc, web, "E7 official gazette or public-sector host")); continue
        if q or not LANG_SEG.match(path or "/"):
            excl.append((qid, cc, web, "E3 website is a page inside a host, not a site root")); continue
        variants = {h, "www." + h if not h.startswith("www.") else h[4:]}
        best = None
        for v in variants:
            r = crux.get((cc, v))
            if r is not None and r <= RANK_MAX and (best is None or (r, v) < best[:2]):
                best = (r, v)
        if best is None:
            excl.append((qid, cc, web, f"E4 not in the top {RANK_MAX:,} CrUX origins of its country ({CRUX_MONTH})")); continue
        if best[1] in D6_HOSTS:
            excl.append((qid, cc, web, "E7 official gazette or public-sector publisher (completed list, deviation D6)")); continue
        cand[qid].append((best[0], cc, best[1], web))
    # one host per outlet (best rank), then one outlet per host (most sitelinks)
    per_item = {}
    for qid, lst in cand.items():
        lst.sort()
        per_item[qid] = lst[0]
        for other in lst[1:]:
            if other[2] != lst[0][2]:
                excl.append((qid, other[1], other[3], "E5 outlet has a better-ranked website (one domain per outlet)"))
    by_host = defaultdict(list)
    for qid, (r, cc, h, web) in per_item.items():
        by_host[h].append((-meta[qid][1], qid, r, cc, web))
    frame = []
    for h, lst in by_host.items():
        lst.sort()
        _, qid, r, cc, web = lst[0]
        frame.append(dict(host=h, country=cc.upper(), wikidata=qid, label=meta[qid][0], sitelinks=meta[qid][1],
                          crux_rank_bucket=r, website=web))
        for _, q2, _, cc2, web2 in lst[1:]:
            excl.append((q2, cc2, web2, f"E6 same host as {qid} (one row per host)"))
    frame.sort(key=lambda d: (d["country"], d["crux_rank_bucket"], d["host"]))
    with open(os.path.join(DATA, "frame.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(frame[0]), lineterminator="\n")
        w.writeheader(); w.writerows(frame)
    excl.sort(key=lambda x: (x[3][:2], x[1] or "", x[0]))
    with open(os.path.join(DATA, "exclusions.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["wikidata", "country", "website", "rule"])
        for qid, cc, web, rule in excl:
            w.writerow([qid, (cc or "").upper(), web, rule])
    by_cc = defaultdict(int)
    for d in frame:
        by_cc[d["country"]] += 1
    rules = defaultdict(int)
    for x in excl:
        rules[x[3][:2]] += 1
    meta_out = dict(wikidata_snapshot=snap, crux_month=CRUX_MONTH, rank_max=RANK_MAX,
                    wikidata_rows=len(res["results"]["bindings"]), wikidata_items=len(items_seen),
                    frame_hosts=len(frame), by_country=dict(sorted(by_cc.items())),
                    exclusions_by_rule=dict(sorted(rules.items())))
    json.dump(meta_out, open(os.path.join(DATA, "frame_meta.json"), "w"), indent=1)
    print(json.dumps(meta_out, indent=1))


if __name__ == "__main__":
    {"fetch": fetch, "build": build}[sys.argv[1]]()
