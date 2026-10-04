import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from s22lib import parse_number, region, segment  # noqa: E402


class Numbers(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(parse_number("1.376", "Centros"), (1376.0, ""))
        self.assertEqual(parse_number("34.145", "Número medio de plazas ocupadas"), (34145.0, ""))
        self.assertEqual(parse_number("360", "Centros"), (360.0, ""))

    def test_comma_thousands(self):
        # INE table 75683 (2024) writes «1,092» for 1,092 dwellings
        self.assertEqual(parse_number("1,092", "Número de viviendas"), (1092.0, "comma_thousands"))

    def test_shares(self):
        self.assertEqual(parse_number("26,2", "%"), (26.2, ""))
        self.assertEqual(parse_number("85,6", "Ratio de ocupación total %"), (85.6, ""))
        self.assertEqual(parse_number("100", "%"), (100.0, ""))

    def test_missing(self):
        for t in ("..", ".", "", "-"):
            self.assertEqual(parse_number(t, "Centros"), (None, "missing"))


class Labels(unittest.TestCase):
    def test_regions(self):
        self.assertEqual(region("01 Andalucía"), "Andalucía")
        self.assertEqual(region("Balears, Illes"), "Balearic Islands")
        self.assertEqual(region("Total nacional"), "Spain")
        self.assertEqual(region("Madrid, Comunidad de"), "Madrid")
        self.assertIsNone(region("Atlántida"))

    def test_segments(self):
        self.assertEqual(segment("Especializado en inmigrantes"), "IMM")
        self.assertEqual(segment("Total de centros de alojamiento"), "ALL")
        self.assertEqual(segment("Sin especialización/Otra especialización"), "OTH")


class Decomposition(unittest.TestCase):
    def test_shapley_exact(self):
        from analyse import shapley
        c0, c1, o0, o1 = 589, 653, 12479 / 589, 14932 / 653
        a, b = shapley(c0, c1, o0, o1)
        self.assertAlmostEqual(a + b, 14932 - 12479, places=6)

    def test_segments_add_up(self):
        p = ROOT / "data" / "specialisation.csv"
        if not p.exists():
            self.skipTest("data/specialisation.csv not built")
        with open(p, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for ed in ("2020", "2022", "2024"):
            r = {x["segment"]: x for x in rows if x["edition"] == ed}
            for k in ("centres", "accommodation_centres", "places_mean", "occupied_mean"):
                s = sum(int(r[g][k]) for g in ("IMM", "GBV", "OTH"))
                self.assertLessEqual(abs(s - int(r["ALL"][k])), 2, (ed, k))


class Orderings(unittest.TestCase):
    def test_orderings_bracket_shapley(self):
        from analyse import orderings, shapley
        c0, c1, o0, o1 = 229, 346, 8045 / 229, 18173 / 346
        (a1, b1), (a2, b2) = orderings(c0, c1, o0, o1)
        a, b = shapley(c0, c1, o0, o1)
        self.assertAlmostEqual(a1 + b1, 18173 - 8045, places=6)
        self.assertAlmostEqual(a2 + b2, 18173 - 8045, places=6)
        self.assertAlmostEqual(a, (a1 + a2) / 2, places=6)
        self.assertLess(min(a1, a2), a)
        self.assertGreater(max(a1, a2), a)


class ExactValues(unittest.TestCase):
    """Guards for headline numbers that a substring check alone cannot tell apart."""

    def setUp(self):
        p = ROOT / "data" / "summary.json"
        if not p.exists():
            self.skipTest("data/summary.json not built")
        import json
        with open(p, encoding="utf-8") as f:
            self.s = json.load(f)

    def test_headline(self):
        h = self.s["headline"]
        self.assertEqual((h["total_0"], h["total_1"], h["IMM_0"], h["IMM_1"]), (21684, 34145, 8045, 18173))
        self.assertAlmostEqual(h["IMM_share_of_change_pct"], 81.278, places=2)
        self.assertAlmostEqual(h["core_growth_pct"], 17.113, places=2)
        self.assertAlmostEqual(h["core_centres_growth_pct"], 11.887, places=2)
        self.assertAlmostEqual(h["core_per_centre_growth_pct"], 4.671, places=2)
        self.assertAlmostEqual(h["all_centres_growth_pct"], 17.106, places=2)

    def test_split_and_ranges(self):
        h = self.s["headline"]
        for k, v in {"split_IMM_centres": 5127.77, "split_IMM_per_centre": 5000.23, "split_core_centres": 1659.14,
                     "split_core_per_centre": 674.86, "IMM_centres_term_min": 4110.33, "IMM_centres_term_max": 6145.17,
                     "IMM_per_centre_term_min": 3982.83, "IMM_per_centre_term_max": 6017.67,
                     "core_centres_term_by_segment": 1603.46, "core_per_centre_term_by_segment": 730.54}.items():
            self.assertAlmostEqual(h[k], v, places=1, msg=k)
        self.assertAlmostEqual(100 * (h["GBV_per_centre_1"] / h["GBV_per_centre_0"] - 1), -24.62, places=1)
        self.assertAlmostEqual(100 * (h["OTH_per_centre_1"] / h["OTH_per_centre_0"] - 1), 7.92, places=1)

    def test_revision_and_context(self):
        r = self.s["revision_split"]
        self.assertAlmostEqual(r["added_to_centres_term"] + r["added_to_per_centre_term"], 387, places=6)
        self.assertAlmostEqual(r["added_to_per_centre_term"], 286.94, places=1)
        self.assertAlmostEqual(self.s["canary"]["share_of_jun_dec_gap_pct"], 40.49, places=1)
        cov = {row["edition"]: row for row in self.s["strategy"]["rows"]}
        self.assertAlmostEqual(cov[2020]["coverage_december_pct"], 70.72, places=1)
        self.assertAlmostEqual(cov[2024]["coverage_december_pct"], 148.06, places=1)
        self.assertAlmostEqual(cov[2024]["coverage_mean_without_imm_pct"], 65.11, places=1)
        rc = self.s["reception"]["coverage_pct"]
        self.assertAlmostEqual(rc["2024"], 37.39, places=1)


if __name__ == "__main__":
    unittest.main()
