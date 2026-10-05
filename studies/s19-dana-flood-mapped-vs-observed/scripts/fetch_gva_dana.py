#!/usr/bin/env python3
"""Download three layers of the Generalitat Valenciana's DANA 2024 WFS (Institut Cartogràfic
Valencià, https://terramapas.icv.gva.es/00_DANA2024) as GeoPackage:

- DANA2024.ZonasInundadas.HuellaInundacion: the Generalitat's flood footprint (CC BY-NC-ND 4.0;
  used only for one sensitivity count and never redistributed);
- DANA2024.AVSRE.MunicipiosAfectados: municipalities declared affected (Decreto 164/2024), CC BY 4.0;
- DANA2024.AVSRE.NivelRiesgoMunicipal: municipal flood-risk level, CC BY 4.0.

    python3 scripts/fetch_gva_dana.py     # -> data/raw/gva/<layer>.gpkg (skips files on disk)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polite

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WFS = "https://terramapas.icv.gva.es/00_DANA2024"
LAYERS = ["DANA2024.ZonasInundadas.HuellaInundacion", "DANA2024.AVSRE.MunicipiosAfectados",
          "DANA2024.AVSRE.NivelRiesgoMunicipal"]


def main():
    out = os.path.join(R, "data", "raw", "gva")
    os.makedirs(out, exist_ok=True)
    for t in LAYERS:
        dst = os.path.join(out, f"{t}.gpkg")
        if os.path.exists(dst):
            continue
        st, _ = polite.fetch(f"{WFS}?request=GetFeature&service=WFS&version=2.0.0&typename={t}&outputformat=gpkg", dst)
        print(st, t)


if __name__ == "__main__":
    main()
