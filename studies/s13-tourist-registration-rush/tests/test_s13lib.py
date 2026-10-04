"""Unit tests for scripts/s13lib.py (python3 -m unittest discover -s tests). Every registration
number and address below is synthetic: none of the numbers exists in the registry copies."""
import datetime as dt
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from s13lib import (unit_kind, building_text, parse_signatura, parse_hist_signatura, counter_of, days, nonworking, excess,
                    contrast_ci, ratio_of_means, ratio_of_ratios, gaps, order_lags, rank_desc)

D = dt.date


class TestUnitKind(unittest.TestCase):
    def test_whole_parcel(self):
        self.assertEqual(unit_kind("CL EJEMPLO 1, 1, ES:T PL:OD PT:OS"), "whole_parcel")

    def test_in_building(self):
        self.assertEqual(unit_kind("AV EJEMPLO 2, 2, ES:1 PL:03 PT:B"), "in_building")
        self.assertEqual(unit_kind("CL EJEMPLO 3, 3, PL:BJ PT:2"), "in_building")
        self.assertEqual(unit_kind("cl ejemplo 4, 4, es:2 pl:01 pt:04"), "in_building")   # case

    def test_unknown(self):
        self.assertEqual(unit_kind("PARTIDA EJEMPLO 5"), "unknown")
        self.assertEqual(unit_kind(""), "unknown")
        self.assertEqual(unit_kind(None), "unknown")

    def test_od_alone_is_not_whole(self):
        # only the pair PL:OD PT:OS marks an undivided property
        self.assertEqual(unit_kind("CL EJEMPLO 6, ES:T PL:OD PT:2"), "in_building")


class TestBuildingText(unittest.TestCase):
    def test_same_building(self):
        a = building_text("CL EJEMPLO DE LA MAR, 12, ES:1 PL:03 PT:B")
        b = building_text("CL EJEMPLO DE LA MAR 12 ES:2 PL:05 PT:A (NOTA 1.2)")
        self.assertEqual(a, b)
        self.assertEqual(a, "CL EJEMPLO DE LA MAR 12")

    def test_leading_zeros_and_other_number(self):
        self.assertEqual(building_text("AV EJEMPLO, 07, ES:2 PL:1 PT:4"), "AV EJEMPLO 7")
        self.assertNotEqual(building_text("AV EJEMPLO, 7"), building_text("AV EJEMPLO, 9"))

    def test_no_number(self):
        self.assertEqual(building_text("PARTIDA EJEMPLO"), "PARTIDA EJEMPLO")


class TestSignatura(unittest.TestCase):
    def test_current(self):
        self.assertEqual(parse_signatura("CV-VUT0999901-A"), (999901, "A"))
        self.assertEqual(parse_signatura("CV-VUT0099902-CS"), (99902, "CS"))
        self.assertIsNone(parse_signatura("CV-AT0001-V"))

    def test_historical(self):
        self.assertEqual(parse_hist_signatura("VT-999904A"), (999904, "A"))
        self.assertEqual(parse_hist_signatura("VT-999905BM"), (999905, "BM"))
        self.assertIsNone(parse_hist_signatura("BL999906A"))

    def test_counter(self):
        self.assertEqual(counter_of(514102, "A"), "A")
        self.assertEqual(counter_of(33, "A"), "A-old")
        self.assertEqual(counter_of(46200, "CS"), "CS")


class TestDays(unittest.TestCase):
    def test_nonworking(self):
        hol = {D(2025, 4, 18)}
        self.assertTrue(nonworking(D(2025, 4, 5), hol))     # Saturday
        self.assertTrue(nonworking(D(2025, 4, 18), hol))    # holiday
        self.assertFalse(nonworking(D(2025, 4, 2), hol))    # Wednesday

    def test_days_inclusive(self):
        self.assertEqual(len(days(D(2025, 1, 1), D(2025, 1, 31))), 31)


class TestExcess(unittest.TestCase):
    def flat(self, wd, we, a, b):
        return {x: (we if x.weekday() >= 5 else wd) for x in days(a, b)}

    def test_no_excess_on_flat_series(self):
        s = self.flat(10, 2, D(2024, 12, 1), D(2025, 4, 30))
        x = excess(s, D(2025, 4, 2), set())
        self.assertAlmostEqual(x["ratio"], 1.0)
        self.assertEqual(x["O"], 10 * 10 + 2 * 4)            # 14 days ending Wed 2 Apr: 10 working, 4 weekend

    def test_spike(self):
        s = self.flat(10, 2, D(2024, 12, 1), D(2025, 4, 30))
        s[D(2025, 4, 2)] = 110
        x = excess(s, D(2025, 4, 2), set())
        self.assertAlmostEqual(x["O"] - x["E"], 100)

    def test_holiday_uses_nonworking_mean(self):
        s = self.flat(10, 0, D(2024, 12, 1), D(2025, 4, 30))
        s[D(2025, 3, 19)] = 0                              # a holiday inside the window
        x = excess(s, D(2025, 4, 2), {D(2025, 3, 19)})
        self.assertAlmostEqual(x["ratio"], 1.0)

    def test_baseline_offsets(self):
        # the baseline is end-87 .. end-34: a spike outside it and outside the window changes nothing
        s = self.flat(10, 2, D(2024, 12, 1), D(2025, 4, 30))
        s[D(2025, 3, 1)] = 500                             # end-32: neither baseline nor window
        self.assertAlmostEqual(excess(s, D(2025, 4, 2), set())["ratio"], 1.0)


class TestRatios(unittest.TestCase):
    def test_ratio_of_means(self):
        r = ratio_of_means([50] * 12, [100] * 12)
        self.assertAlmostEqual(r["ratio"], 0.5)
        self.assertAlmostEqual(r["lo"], 0.5)               # no variance -> degenerate CI

    def test_ratio_of_ratios(self):
        a = ratio_of_means([40, 60], [100, 100])
        b = ratio_of_means([80, 80], [100, 100])
        r = ratio_of_ratios(a, b)
        self.assertAlmostEqual(r["ratio"], 0.625)
        self.assertLess(r["lo"], 0.625)
        self.assertGreater(r["hi"], 0.625)

    def test_contrast_ci(self):
        a = {"O": 100, "E": 50, "B": 200, "ratio": 2.0}
        b = {"O": 50, "E": 50, "B": 200, "ratio": 1.0}
        rr, lo, hi = contrast_ci(a, b, scaled=False)
        self.assertAlmostEqual(rr, 2.0)
        se = math.sqrt(1 / 100 + 1 / 200 + 1 / 50 + 1 / 200)
        self.assertAlmostEqual(lo, 2.0 * math.exp(-1.96 * se))
        rr2, lo2, hi2 = contrast_ci(a, b, scaled=True)
        self.assertLess(lo2, lo)                            # the frozen variance is wider


class TestGapsAndLags(unittest.TestCase):
    def test_gaps(self):
        ent = [(10, D(2025, 1, 1)), (11, D(2025, 1, 1)), (14, D(2025, 1, 2)), (15, D(2025, 1, 3))]
        self.assertEqual(gaps(ent, 10), [(D(2025, 1, 1), 2)])
        self.assertEqual(gaps(ent, 12), [])                # numbers below start ignored

    def test_order_lags(self):
        ent = [(1, D(2025, 4, 2)), (2, D(2025, 4, 10)), (3, D(2025, 4, 2)), (4, D(2025, 4, 11))]
        lags = {n: l for n, _, l in order_lags(ent, D(2025, 1, 1))}
        self.assertEqual(lags, {1: 0, 2: 0, 3: 8, 4: 0})   # no. 3 was numbered after a file of 10 April

    def test_rank(self):
        self.assertEqual(rank_desc([5, 9, 3, 9], 9), 1)
        self.assertEqual(rank_desc([5, 9, 3, 9], 5), 3)


if __name__ == "__main__":
    unittest.main()
