#!/usr/bin/env python3
"""Download PATRICOVA layers (Generalitat Valenciana, Institut Cartogràfic Valencià) as
shapefiles, the way the ICV download page linked from dadesobertes.gva.es does it: the page
submits a job to the public ArcGIS geoprocessing service
carto.icv.gva.es/arcgis/rest/services/utils/descargas/GPServer/tarea_descarga_datos,
polls it and downloads the resulting ZIP. We do the same calls, through polite.py
(fixed User-Agent, at most 1 request per second per host, robots.txt read and logged).

    python3 scripts/fetch_patricova.py      # -> data/raw/patricova/<layer>.zip
"""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(R, "data", "raw", "patricova")
GP = "http://carto.icv.gva.es/arcgis/rest/services/utils/descargas/GPServer/tarea_descarga_datos"
LAYERS = ["orde_patricova_peligrosidad_inun"]   # the hazard layer (peligrosidad 1-6 + geomorphological)


def get_json(url, name):
    p = os.path.join(R, "work", "patricova", name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    polite.fetch(url, p, accept="application/json")
    return json.load(open(p))


def main(layers=LAYERS):
    os.makedirs(OUT, exist_ok=True)
    for lay in layers:
        dst = os.path.join(OUT, lay + ".zip")
        if os.path.exists(dst):
            print("have", dst); continue
        capas = '["/home/carto_tema/datos/vectorial/infraestructuras.gdb/%s"]' % lay
        q = urllib.parse.urlencode({"Capas": capas, "Formato_Salida": "Shapefile - SHP - .shp", "f": "json"},
                                   quote_via=urllib.parse.quote)
        job = get_json(f"{GP}/submitJob?{q}", f"{lay}_submit.json")["jobId"]
        for i in range(600):
            st = get_json(f"{GP}/jobs/{job}?f=json", f"{lay}_status.json")
            if st["jobStatus"] in ("esriJobSucceeded", "esriJobFailed", "esriJobCancelled"):
                break
            time.sleep(4)
        print(lay, st["jobStatus"])
        if st["jobStatus"] != "esriJobSucceeded":
            print(json.dumps(st)[:2000]); continue
        res = get_json(f"{GP}/jobs/{job}/results/Fichero_Salida?f=json", f"{lay}_result.json")
        url = res["value"]["url"] if isinstance(res["value"], dict) else res["value"]
        print("download", url)
        polite.fetch(url, dst)
        json.dump({"layer": lay, "job": job, "result_url": url, "status": st}, open(dst + ".meta.json", "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:] or LAYERS)
