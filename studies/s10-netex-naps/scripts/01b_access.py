#!/usr/bin/env python3
"""S10 step 1b — access table: what each probe actually showed (data/nap_access.csv).

Inputs: data/nap_access_probes.csv (01_catalogues.py) and the two Swiss requests made on 2026-10-03
(1: CKAN package_search -> work/docs/ch_package_search.json; 2: 1 kB Range GET on the timetable
permalink -> work/docs/ch_range_headers.txt). Re-making them: `01b_access.py --fetch`
(two requests, the second downloads 1,024 bytes)."""
import csv, os, re, subprocess, sys
S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(S, "work", "docs")
UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"
if "--fetch" in sys.argv:
    subprocess.run(["curl", "-s", "-A", UA, "-o", f"{DOC}/ch_package_search.json",
                    "https://data.opentransportdata.swiss/api/3/action/package_search?q=netex&rows=50"])
    subprocess.run(["curl", "-sL", "-A", UA, "-r", "0-1023", "-D", f"{DOC}/ch_range_headers.txt", "-o", f"{DOC}/ch_range_1k.bin",
                    "https://data.opentransportdata.swiss/dataset/timetablenetex_2026/permalink"])
probes = {r["country"]: r for r in csv.DictReader(open(os.path.join(S, "data", "nap_access_probes.csv")))}
h = open(os.path.join(DOC, "ch_range_headers.txt")).read()
cr = re.search(r"(?i)content-range: bytes 0-1023/(\d+)", h)
st = re.findall(r"HTTP/[\d.]+ (\d+)", h)
fn = re.search(r"/download/([^\s?]+\.zip)", h)
ch_api = "403" if "403 Forbidden" in open(os.path.join(DOC, "ch_package_search.json")).read() else "?"
rows = [
    ("ES", "nap.transportes.gob.es", probes["ES"]["url"], probes["ES"]["http_status"], "file-list API answers 401",
     "registration required; lawful under Art. 4(4) ('where relevant subject to registration')"),
    ("SE", "Trafiklab / Samtrafiken", probes["SE"]["url"], probes["SE"]["http_status"], "national NeTEx file answers 403 without a key",
     "API key (registration) required; lawful under Art. 4(4)"),
    ("FI", "finap.fi", probes["FI"]["url"], probes["FI"]["http_status"], "internal search API answers 401 'Invalid cookie'",
     "not assessed: a session cookie on an internal API is not evidence of a registration wall"),
    ("AT", "mobilitydata.gv.at", probes["AT"]["url"], probes["AT"]["http_status"], "guessed CKAN path returned an HTML 'not found' page",
     "not assessed: wrong endpoint, not a refusal"),
    ("CH", "opentransportdata.swiss", probes["CH"]["url"], probes["CH"]["http_status"], "guessed CKAN path returned an HTML 'not found' page",
     "wrong endpoint, not a refusal (see next rows)"),
    ("CH", "opentransportdata.swiss", "https://data.opentransportdata.swiss/api/3/action/package_search?q=netex", ch_api,
     "CKAN API answers 403 to an anonymous client", "API needs a key"),
    ("CH", "opentransportdata.swiss", "https://data.opentransportdata.swiss/dataset/timetablenetex_2026/permalink",
     "->".join(st), f"anonymous 1 kB Range GET: {fn.group(1) if fn else '?'}; total size {cr.group(1) if cr else '?'} bytes",
     "the national NeTEx timetable is anonymously downloadable; larger than the 300 MB limit of this study, so it would not have been sampled"),
    ("DE", "Mobilithek", "offers/search + offer detail", "200", "metadata anonymous; no download URL without an account and contract offer",
     "registration required for files; lawful under Art. 4(4)"),
    ("EU", "data.europa.eu", probes["EU"]["url"], probes["EU"]["http_status"], probes["EU"]["note"],
     "format metadata not harmonised: the 'netex' facet finds French datasets only"),
]
with open(os.path.join(S, "data", "nap_access.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["country", "nap", "probe", "http_status", "observed", "interpretation"]); w.writerows(rows)
print("CH zip bytes:", cr.group(1) if cr else None, "statuses:", st)
