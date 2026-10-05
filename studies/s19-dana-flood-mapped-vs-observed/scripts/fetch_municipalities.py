#!/usr/bin/env python3
"""Municipal boundaries of the province of Valencia (INE province 46) from the IGN's INSPIRE
Administrative Units WFS (www.ign.es/wfs-inspire/unidades-administrativas), as GeoJSON in
EPSG:25830, paged 100 features at a time. The IGN national code of a municipality is
'341046' + its five-digit INE code (e.g. 34104646186 = Paiporta, INE 46186).

    python3 scripts/fetch_municipalities.py      # -> data/raw/ign/municipios_46_pNN.json

Requests go through polite.py (fixed User-Agent, at most 1 request per second per host,
robots.txt read and logged). Resumable: pages already on disk are not fetched again."""
import json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(R, "data", "raw", "ign")
WFS = "https://www.ign.es/wfs-inspire/unidades-administrativas"
FILTER = ('<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0" xmlns:au="http://inspire.ec.europa.eu/schemas/au/4.0">'
          '<fes:PropertyIsLike wildCard="*" singleChar="." escapeChar="!"><fes:ValueReference>au:nationalCode</fes:ValueReference>'
          '<fes:Literal>34104646*</fes:Literal></fes:PropertyIsLike></fes:Filter>')


def main():
    os.makedirs(OUT, exist_ok=True)
    page, start = 0, 0
    while True:
        dst = os.path.join(OUT, f"municipios_46_p{page:02d}.json")
        if not os.path.exists(dst):
            q = urllib.parse.urlencode({"service": "WFS", "version": "2.0.0", "request": "GetFeature",
                                        "typeNames": "au:AdministrativeUnit", "count": "100",
                                        "startIndex": str(start), "outputFormat": "application/geo+json",
                                        "srsName": "EPSG:25830", "FILTER": FILTER})
            st, _ = polite.fetch(f"{WFS}?{q}", dst, accept="application/geo+json")
            print(st, dst, flush=True)
        n = len(json.load(open(dst)).get("features", []))
        print("page", page, "features", n, flush=True)
        if n < 100:
            break
        page += 1
        start += 100


if __name__ == "__main__":
    main()
