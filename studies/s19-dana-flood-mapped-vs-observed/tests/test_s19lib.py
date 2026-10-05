"""Tests for scripts/s19lib.py and the masking helper of scripts/classify.py
(run: .venv/bin/python -m unittest discover -s tests). All inputs are synthetic: the GML snippet
below follows the Catastro INSPIRE BU schema but describes no real building."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import s19lib as L

GML = b"""<?xml version="1.0" encoding="UTF-8"?>
<gml:FeatureCollection xmlns:gml="http://www.opengis.net/gml/3.2"
  xmlns:bu-core2d="http://inspire.jrc.ec.europa.eu/schemas/bu-core2d/2.0"
  xmlns:bu-ext2d="http://inspire.jrc.ec.europa.eu/schemas/bu-ext2d/2.0"
  xmlns:xlink="http://www.w3.org/1999/xlink">
 <gml:featureMember>
  <bu-ext2d:Building gml:id="ES.SDGC.BU.TEST0001">
   <bu-core2d:conditionOfConstruction>functional</bu-core2d:conditionOfConstruction>
   <bu-core2d:dateOfConstruction><bu-core2d:DateOfEvent>
     <bu-core2d:beginning>2018-01-01T00:00:00</bu-core2d:beginning>
     <bu-core2d:end>2019-01-01T00:00:00</bu-core2d:end>
   </bu-core2d:DateOfEvent></bu-core2d:dateOfConstruction>
   <bu-ext2d:geometry><bu-core2d:BuildingGeometry><bu-core2d:geometry>
    <gml:Surface><gml:patches><gml:PolygonPatch><gml:exterior><gml:LinearRing>
     <gml:posList srsDimension="2" count="5">0 0 10 0 10 10 0 10 0 0</gml:posList>
    </gml:LinearRing></gml:exterior></gml:PolygonPatch></gml:patches></gml:Surface>
   </bu-core2d:geometry></bu-core2d:BuildingGeometry></bu-ext2d:geometry>
   <bu-ext2d:currentUse>1_residential</bu-ext2d:currentUse>
   <bu-ext2d:numberOfBuildingUnits>13</bu-ext2d:numberOfBuildingUnits>
   <bu-ext2d:numberOfDwellings>12</bu-ext2d:numberOfDwellings>
  </bu-ext2d:Building>
 </gml:featureMember>
 <gml:featureMember>
  <bu-ext2d:Building gml:id="ES.SDGC.BU.TEST0002">
   <bu-core2d:dateOfConstruction><bu-core2d:DateOfEvent>
     <bu-core2d:end>1971-01-01T00:00:00</bu-core2d:end>
   </bu-core2d:DateOfEvent></bu-core2d:dateOfConstruction>
   <bu-ext2d:geometry><bu-core2d:BuildingGeometry><bu-core2d:geometry>
    <gml:Surface><gml:patches>
     <gml:PolygonPatch><gml:exterior><gml:LinearRing>
      <gml:posList srsDimension="2" count="5">20 0 30 0 30 10 20 10 20 0</gml:posList>
     </gml:LinearRing></gml:exterior><gml:interior><gml:LinearRing>
      <gml:posList srsDimension="2" count="5">22 2 28 2 28 8 22 8 22 2</gml:posList>
     </gml:LinearRing></gml:interior></gml:PolygonPatch>
     <gml:PolygonPatch><gml:exterior><gml:LinearRing>
      <gml:posList srsDimension="2" count="5">40 0 45 0 45 5 40 5 40 0</gml:posList>
     </gml:LinearRing></gml:exterior></gml:PolygonPatch>
    </gml:patches></gml:Surface>
   </bu-core2d:geometry></bu-core2d:BuildingGeometry></bu-ext2d:geometry>
   <bu-ext2d:currentUse>3_industrial</bu-ext2d:currentUse>
   <bu-ext2d:numberOfDwellings>0</bu-ext2d:numberOfDwellings>
  </bu-ext2d:Building>
 </gml:featureMember>
</gml:FeatureCollection>"""


class Buildings(unittest.TestCase):
    def setUp(self):
        self.rows = list(L.iter_buildings(io.BytesIO(GML)))

    def test_fields(self):
        a, b = self.rows
        self.assertEqual(a["use"], "residential")
        self.assertEqual(a["dwellings"], 12)
        self.assertEqual(a["units"], 13)
        self.assertEqual(a["year"], 2019)          # dateOfConstruction/end first
        self.assertEqual(a["condition"], "functional")
        self.assertAlmostEqual(a["geom"].area, 100.0)
        self.assertEqual(b["use"], "industrial")
        self.assertEqual(b["dwellings"], 0)
        self.assertEqual(b["year"], 1971)

    def test_holes_and_multipatch(self):
        b = self.rows[1]
        self.assertEqual(b["geom"].geom_type, "MultiPolygon")
        self.assertAlmostEqual(b["geom"].area, 100 - 36 + 25)

    def test_no_identifier_returned(self):
        for r in self.rows:
            self.assertFalse(any("TEST" in str(v) for k, v in r.items() if k != "geom"))


class Bands(unittest.TestCase):
    def test_edges(self):
        self.assertEqual(L.year_band(1985), "1985 or earlier")
        self.assertEqual(L.year_band(1986), "1986-2007")
        self.assertEqual(L.year_band(2016), "2008-2016")
        self.assertEqual(L.year_band(2017), "2017-2024")
        self.assertEqual(L.year_band(2024), "2017-2024")
        self.assertEqual(L.year_band(2025), "2025 or later")
        self.assertEqual(L.year_band(None), "unknown")

    def test_year_parse(self):
        self.assertEqual(L._year("2017-01-01T00:00:00"), 2017)
        self.assertIsNone(L._year("0201-01-01"))
        self.assertIsNone(L._year(""))


class Status(unittest.TestCase):
    def test_order(self):
        self.assertEqual(L.map_status({"t10": True, "t500": True}), "SNCZI T10")
        self.assertEqual(L.map_status({"t100": True, "pat16": True}), "SNCZI T100 (not T10)")
        self.assertEqual(L.map_status({"t500": True}), "SNCZI T500 (not T100)")
        self.assertEqual(L.map_status({"pat16": True, "patgeo": True}), "PATRICOVA levels 1-6 only")
        self.assertEqual(L.map_status({"patgeo": True}), "PATRICOVA geomorphological only")
        self.assertEqual(L.map_status({}), "outside every official zone")

    def test_products(self):
        self.assertEqual(L.product_name("EMSR773_AOI03_GRA_PRODUCT_v2.zip"),
                         {"aoi": 3, "type": "GRA", "kind": "PRODUCT", "version": 2})
        self.assertEqual(L.product_name("x/EMSR773_AOI01_DEL_MONIT04_v1.zip")["kind"], "MONIT04")
        with self.assertRaises(ValueError):
            L.product_name("EMSR773_AOI01.zip")


class Cells(unittest.TestCase):
    def test_suppression(self):
        self.assertEqual(L.fmt_cell(0), "0")
        self.assertEqual(L.fmt_cell(1), "<5")
        self.assertEqual(L.fmt_cell(4), "<5")
        self.assertEqual(L.fmt_cell(5), "5")

    def test_wilson(self):
        lo, hi = L.wilson(50, 100)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)


class Mask(unittest.TestCase):
    def test_pixel_centres_and_lookup(self):
        import numpy as np
        import shapely
        import classify as C
        g = shapely.box(1, 1, 9, 5)
        xs, ys = C.pixel_centres(g)
        # 2 m pixel centres at x = 1, 3, 5, 7 and y = 1, 3; those on the boundary (x = 1 or
        # y = 1) are not strictly inside, so (3, 3), (5, 3) and (7, 3) remain
        self.assertEqual(sorted(zip(xs.tolist(), ys.tolist())), [(3.0, 3.0), (5.0, 3.0), (7.0, 3.0)])
        tiny = shapely.box(0.2, 0.2, 0.6, 0.6)    # smaller than a pixel: representative point
        xs2, _ = C.pixel_centres(tiny)
        self.assertEqual(len(xs2), 1)
        m = np.zeros((1024, 1024), bool)
        m[1023, 0] = True                          # bottom-left pixel of tile (0, 0)
        C.mask.cache_clear()
        orig = C.mask
        try:
            C.mask = lambda layer, a, b: m if (a, b) == (0, 0) else None
            got = C.in_mask("x", np.array([1.0, 3.0, 1.0]), np.array([1.0, 1.0, 3.0]))
            self.assertEqual(got.tolist(), [True, False, False])
        finally:
            C.mask = orig


class Filled(unittest.TestCase):
    def test_small_enclosed_hole_filled_large_not(self):
        import numpy as np
        import classify as C
        n = C.PX_N
        m = np.zeros((n, n), bool)
        m[100:200, 100:200] = True            # a flooded square ...
        m[140:160, 140:160] = False           # ... with a 20 x 20 px dry building (1,600 m2)
        big = np.zeros((n, n), bool)
        big[300:500, 300:500] = True
        big[310:490, 310:490] = False         # a 180 x 180 px dry island (13 ha): stays dry
        tiles = {(0, 0): m | big}
        orig = C.mask
        try:
            C.mask = lambda layer, a, b: tiles.get((a, b))
            C._holes.cache_clear()
            f = C.mask_filled("x", 0, 0)                     # 2 ha
            self.assertTrue(f[150, 150])
            self.assertFalse(f[400, 400])
            self.assertTrue(f[105, 105])
            self.assertFalse(C.mask_filled("x", 0, 0, 300)[150, 150])    # 0.12 ha cap: the 400-px building stays a hole
            self.assertTrue(C.mask_filled("x", 0, 0, 40000)[400, 400])   # 16 ha: island filled
            self.assertTrue((C.mask_filled("x", 0, 0) >= tiles[(0, 0)]).all())   # never removes zone
        finally:
            C.mask = orig
            C._holes.cache_clear()


class Disclosure(unittest.TestCase):
    def table(self):
        from disclosure import Registry
        reg = Registry(k=5)
        cells = {("c", "A", 1): (3, 30), ("c", "A", 2): (20, 40), ("c", "A", 3): (0, 0),
                 ("c", "B", 1): (10, 15), ("c", "B", 2): (12, 30), ("c", "B", 3): (8, 9)}
        for g, (b, d) in cells.items():
            reg.add(g, b=b, d=d)
        for m in ("A", "B"):     # row totals
            reg.add(("m", m), b=sum(cells[("c", m, k)][0] for k in (1, 2, 3)), d=sum(cells[("c", m, k)][1] for k in (1, 2, 3)))
            reg.total(("m", m), [("c", m, k) for k in (1, 2, 3)])
        for k in (1, 2, 3):      # column totals
            reg.add(("p", k), b=cells[("c", "A", k)][0] + cells[("c", "B", k)][0], d=cells[("c", "A", k)][1] + cells[("c", "B", k)][1])
            reg.total(("p", k), [("c", m, k) for m in ("A", "B")])
        return reg

    def test_primary_and_complementary(self):
        reg = self.table()
        n1, n2 = reg.run()
        self.assertEqual(n1, 1)                              # the 3-building cell
        self.assertTrue(reg.groups[("c", "A", 1)]["supp"])
        self.assertGreaterEqual(n2, 1)                       # it cannot stand alone in its row
        self.assertEqual(reg.determined(), set())            # nothing recoverable at the end
        self.assertEqual(reg.fmt(("c", "A", 1), "d"), "<5")

    def test_single_suppression_is_recoverable(self):
        reg = self.table()
        reg.primary()
        self.assertIn(("c", "A", 1), reg.determined())       # row total minus the others


if __name__ == "__main__":
    unittest.main()
