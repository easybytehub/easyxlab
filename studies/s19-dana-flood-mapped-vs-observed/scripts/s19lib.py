"""Shared helpers for S19: the Copernicus EMS extent, Catastro INSPIRE buildings, construction-year
bands and map-status classes. Pure functions where possible, so tests can exercise them with
synthetic inputs (tests/test_s19lib.py).

Coordinates are EPSG:25830 (ETRS89 / UTM 30N) throughout, the CRS of Catastro INSPIRE, IGN
municipal boundaries in our request, PATRICOVA and the SNCZI WMS requests."""
import datetime as dt
import io
import json
import os
import re
import zipfile

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------------------- Copernicus EMS
# AOIs of EMSR773 outside the province of Valencia, left out of the study area:
# AOI05 Letur (Albacete), AOI06 Castellón province, AOI15 Alhaurín de la Torre (Málaga).
NON_VALENCIA_AOIS = {5, 6, 15}
FLOOD_NOTATIONS = {"Flooded area", "Flood trace"}

YEAR_BANDS = [  # (label, first year, last year); RD 638/2016 entered into force on 30-12-2016
    ("1985 or earlier", None, 1985),   # before the Water Act 1985 and RDPH 1986
    ("1986-2007", 1986, 2007),         # RDPH 1986, before RD 9/2008 defined the preferential flow zone
    ("2008-2016", 2008, 2016),         # RD 9/2008 in force, before RD 638/2016
    ("2017-2024", 2017, 2024),         # after RD 638/2016, before the DANA
    ("2025 or later", 2025, None),     # after the DANA: rebuilding or new building
]


def product_name(path):
    """'EMSR773_AOI03_GRA_PRODUCT_v2.zip' -> dict(aoi=3, type='GRA', kind='PRODUCT', version=2)."""
    m = re.match(r"EMSR773_AOI(\d+)_(DEL|GRA)_(PRODUCT|MONIT\d+)_v(\d+)\.zip$", os.path.basename(path))
    if not m:
        raise ValueError(path)
    return {"aoi": int(m.group(1)), "type": m.group(2), "kind": m.group(3), "version": int(m.group(4))}


def year_band(year):
    if year is None:
        return "unknown"
    for label, a, b in YEAR_BANDS:
        if (a is None or year >= a) and (b is None or year <= b):
            return label
    return "unknown"


USE_LABELS = {
    "1_residential": "residential",
    "2_agriculture": "agriculture",
    "3_industrial": "industrial",
    "4_1_office": "office",
    "4_2_retail": "retail",
    "4_3_publicServices": "public services",
}


def use_label(code):
    if not code:
        return "unknown"
    code = code.rsplit("/", 1)[-1]
    return USE_LABELS.get(code, code)


# --------------------------------------------------------------------------- map status
STATUS_ORDER = [
    "SNCZI T10",
    "SNCZI T100 (not T10)",
    "SNCZI T500 (not T100)",
    "PATRICOVA levels 1-6 only",
    "PATRICOVA geomorphological only",
    "outside every official zone",
]


def map_status(flags):
    """Mutually exclusive class from boolean flags t10, t100, t500 (SNCZI fluvial hazard maps),
    pat16 (PATRICOVA hazard levels 1-6) and patgeo (PATRICOVA geomorphological hazard). The
    SNCZI zones are nested in principle (T10 within T100 within T500); a building flagged T10
    but not T500 still counts as T10. The order follows the return period, then PATRICOVA."""
    if flags.get("t10"):
        return STATUS_ORDER[0]
    if flags.get("t100"):
        return STATUS_ORDER[1]
    if flags.get("t500"):
        return STATUS_ORDER[2]
    if flags.get("pat16"):
        return STATUS_ORDER[3]
    if flags.get("patgeo"):
        return STATUS_ORDER[4]
    return STATUS_ORDER[5]


# --------------------------------------------------------------------------- Catastro INSPIRE
NS = {
    "bu-core2d": "http://inspire.jrc.ec.europa.eu/schemas/bu-core2d/2.0",
    "bu-ext2d": "http://inspire.jrc.ec.europa.eu/schemas/bu-ext2d/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
}


def _year(text):
    if not text:
        return None
    m = re.match(r"\s*(\d{4})", text)
    if not m:
        return None
    y = int(m.group(1))
    return y if 1000 <= y <= 2100 else None


def _rings(surface_el):
    """Exterior and interior rings of every gml:PolygonPatch / gml:Polygon under an element."""
    from lxml import etree  # noqa: F401
    polys = []
    for patch in surface_el.iter("{http://www.opengis.net/gml/3.2}PolygonPatch", "{http://www.opengis.net/gml/3.2}Polygon"):
        ext, ints = None, []
        for tag, target in (("exterior", "ext"), ("interior", "int")):
            for ring in patch.iter("{http://www.opengis.net/gml/3.2}" + tag):
                pl = ring.find(".//{http://www.opengis.net/gml/3.2}posList")
                if pl is None or not pl.text:
                    continue
                v = [float(x) for x in pl.text.split()]
                dim = int(pl.get("srsDimension", "2"))
                pts = [(v[i], v[i + 1]) for i in range(0, len(v) - dim + 1, dim)]
                if target == "ext":
                    ext = pts
                else:
                    ints.append(pts)
        if ext and len(ext) >= 4:
            polys.append((ext, ints))
    return polys


def iter_buildings(fileobj):
    """Stream bu-ext2d:Building elements from a Catastro INSPIRE building.gml. Yields dicts with
    use, dwellings, units, year (dateOfConstruction/end, else beginning), condition and the
    polygon(s) as lists of rings. The cadastral reference is read only to deduplicate within the
    file and is never returned."""
    from lxml import etree
    from shapely.geometry import Polygon, MultiPolygon
    tag = "{%s}Building" % NS["bu-ext2d"]
    seen = set()
    for _, el in etree.iterparse(fileobj, events=("end",), tag=tag, huge_tree=True):
        gid = el.get("{http://www.opengis.net/gml/3.2}id")
        if gid in seen:
            el.clear(); continue
        seen.add(gid)
        def txt(path):
            x = el.find(path, NS)
            return x.text if x is not None else None
        use = txt("bu-ext2d:currentUse")
        dw = txt("bu-ext2d:numberOfDwellings")
        units = txt("bu-ext2d:numberOfBuildingUnits")
        end = txt("bu-core2d:dateOfConstruction/bu-core2d:DateOfEvent/bu-core2d:end")
        beg = txt("bu-core2d:dateOfConstruction/bu-core2d:DateOfEvent/bu-core2d:beginning")
        cond = txt("bu-core2d:conditionOfConstruction")
        cond_href = None
        c = el.find("bu-core2d:conditionOfConstruction", NS)
        if c is not None:
            cond_href = c.get("{http://www.w3.org/1999/xlink}href") or c.text
        geom_el = el.find("bu-ext2d:geometry", NS)
        polys = _rings(geom_el) if geom_el is not None else []
        shp = []
        for ext, ints in polys:
            try:
                p = Polygon(ext, ints)
                if not p.is_valid:
                    p = p.buffer(0)
                if not p.is_empty:
                    shp.append(p)
            except Exception:
                pass
        geom = None
        if len(shp) == 1:
            geom = shp[0]
        elif shp:
            geom = MultiPolygon([g for s in shp for g in (s.geoms if hasattr(s, "geoms") else [s])])
        use_el = el.find("bu-ext2d:currentUse", NS)
        if use_el is not None and not use:
            use = use_el.get("{http://www.w3.org/1999/xlink}href")
        yield {
            "use": use_label(use),
            "dwellings": int(dw) if dw and dw.strip().isdigit() else 0,
            "units": int(units) if units and units.strip().isdigit() else 0,
            "year": _year(end) or _year(beg),
            "condition": (cond_href or cond or "").rsplit("/", 1)[-1],
            "geom": geom,
        }
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]


def open_building_gml(zip_path):
    """Open the building.gml member of a Catastro BU zip as a binary stream."""
    z = zipfile.ZipFile(zip_path)
    name = [n for n in z.namelist() if n.lower().endswith(".building.gml")]
    if not name:
        raise FileNotFoundError(f"no building.gml in {zip_path}")
    return z.open(name[0])


# --------------------------------------------------------------------------- small-cell rule
def suppress(n, k=5):
    """Published cells under k are suppressed (returned as None, written as '<5')."""
    return None if 0 < n < k else n


def fmt_cell(n, k=5):
    s = suppress(n, k)
    return "<5" if s is None else str(s)


def wilson(k, n, z=1.959964):
    """Wilson score interval for a proportion (used only as a descriptive sampling bound)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (c - h, c + h)


# --------------------------------------------------------------------------- IGN municipalities
def load_municipalities():
    """INE code -> (name, shapely geometry in EPSG:25830) for the province of Valencia. The IGN
    WFS answered our EPSG:25830 request in longitude/latitude (CRS84), so coordinates within
    +/-180 are reprojected."""
    import glob
    import numpy as np
    import shapely
    from pyproj import Transformer
    t = Transformer.from_crs(4326, 25830, always_xy=True)
    out = {}
    for f in sorted(glob.glob(os.path.join(R, "data", "raw", "ign", "municipios_46_p*.json"))):
        for ft in json.load(open(f))["features"]:
            g = shapely.geometry.shape(ft["geometry"])
            if abs(g.bounds[0]) <= 180 and abs(g.bounds[1]) <= 90:
                g = shapely.transform(g, lambda xy: np.column_stack(t.transform(xy[:, 0], xy[:, 1])))
            code = ft["properties"]["nationalCode"][-5:]
            name = ft["properties"]["name"]["GeographicalName"]["spelling"]["SpellingOfName"]["text"]
            out[code] = (name, shapely.make_valid(g))
    return out
