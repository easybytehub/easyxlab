"""Unit tests for scripts/s21lib.py, on synthetic numbers (python3 -m unittest discover -s tests)."""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import s21lib as L  # noqa: E402


class Territories(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(L.province_code("Madrid (Comunidad de)"), "28")
        self.assertEqual(L.province_code("Balears (Illes)"), "07")
        self.assertEqual(L.province_code("Alicante/Alacant"), "03")
        self.assertEqual(L.province_code("Palmas (Las)"), "35")
        self.assertIsNone(L.province_code("Andalucía"))
        self.assertIsNone(L.province_code("TOTAL NACIONAL"))

    def test_52_provinces(self):
        self.assertEqual(len(L.CODE_LABEL), 52)
        self.assertTrue(set(L.OFFICIAL_SIX) <= set(L.CODE_LABEL))


class Quarters(unittest.TestCase):
    def test_range_and_shift(self):
        self.assertEqual(L.qrange("2023Q3", "2024Q2"), ["2023Q3", "2023Q4", "2024Q1", "2024Q2"])
        self.assertEqual(L.qshift("2025Q1", -1), "2024Q4")
        self.assertEqual(L.qshift("2024Q4", 4), "2025Q4")
        self.assertEqual(L.sheet_quarter("2t 2026"), "2026Q2")

    def test_window_sum_missing(self):
        s = {"2024Q1": 3, "2024Q2": 4}
        self.assertEqual(L.window_sum(s, ["2024Q1", "2024Q2"]), 7)
        self.assertIsNone(L.window_sum(s, ["2024Q1", "2024Q3"]))


class Measures(unittest.TestCase):
    def test_pct_and_relative(self):
        self.assertAlmostEqual(L.pct(50, 100), -50.0)
        # treated halves, comparison unchanged -> -50%; both halve -> 0%
        self.assertAlmostEqual(L.rel_change(50, 100, 10, 10), -50.0)
        self.assertAlmostEqual(L.rel_change(50, 100, 5, 10), 0.0)

    def test_rank_p(self):
        plac = [1, 2, 3, 4]
        self.assertAlmostEqual(L.rank_p(0, plac, "lower"), 1 / 5)
        self.assertAlmostEqual(L.rank_p(5, plac, "upper"), 1 / 5)
        self.assertAlmostEqual(L.rank_p(2.5, plac, "lower"), 3 / 5)
        self.assertAlmostEqual(L.rank_p(-4, plac, "two"), 2 / 5)

    def test_quantile(self):
        self.assertAlmostEqual(L.quantile([0, 10], 0.5), 5)
        self.assertAlmostEqual(L.quantile(list(range(11)), 0.9), 9)

    def test_poisson_ci_contains_ratio(self):
        r, lo, hi = L.poisson_ratio_ci(100, 200)
        self.assertAlmostEqual(r, 0.5)
        self.assertTrue(lo < 0.5 < hi)


class Regression(unittest.TestCase):
    def test_wls_recovers_slope_with_fixed_effects(self):
        rng = random.Random(1)
        y, X, g1, g2, w = [], [], [], [], []
        for u in range(8):
            for t in range(10):
                x = rng.random()
                y.append(2.0 * x + u * 0.7 + t * 0.3)
                X.append([x])
                g1.append(u)
                g2.append(t)
                w.append(1.0 + u)
        beta, se = L.wls_fe(y, X, [g1, g2], w, cluster=g1)
        self.assertAlmostEqual(beta[0], 2.0, places=6)
        self.assertLess(se[0], 1e-6)

    def test_wslope_and_permutation(self):
        xs = [0, 1, 2, 3, 4]
        ys = [1, 3, 5, 7, 9]
        self.assertAlmostEqual(L.wslope(xs, ys, [1] * 5), 2.0)
        perms = L.permute_slopes(xs, ys, [1] * 5, n=200, seed=3)
        self.assertEqual(len(perms), 200)
        self.assertTrue(max(abs(p) for p in perms) <= 2.0 + 1e-12)


class Prediction(unittest.TestCase):
    def test_share_from_relative_level(self):
        # r = log(u) - log(N - u); share = e^r / (1 + e^r)
        u, n = 150, 12000
        r = math.log(u) - math.log(n - u)
        self.assertAlmostEqual(math.exp(r) / (1 + math.exp(r)), u / n)


if __name__ == "__main__":
    unittest.main()
