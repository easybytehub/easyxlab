"""S24 unit tests (standard library). Integration checks are skipped when data/ has not been built."""
from __future__ import annotations

import csv
import io
import json
import math
import sys
import unittest
import zipfile
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "scripts"))

from s24lib import wmedian, wquantile  # noqa: E402
import analyse  # noqa: E402
import extract_ecv  # noqa: E402

D = R / "data"
HAVE = (D / "summary.json").exists()


def person(**kw):
    p = {"hc": 500.0, "inc": 20000.0, "al": 0.0, "rent": 400.0, "w": 1.0}
    p.update(kw)
    return p


class Weighted(unittest.TestCase):
    def test_median_odd_even_weights(self):
        self.assertEqual(wmedian([1, 2, 3], [1, 1, 1]), 2)
        self.assertEqual(wmedian([1, 2, 3, 4], [1, 1, 1, 1]), 2.5)      # exact half: mean of the two middle values
        self.assertEqual(wmedian([1, 2, 3], [1, 1, 5]), 3)
        self.assertTrue(math.isnan(wmedian([], [])))

    def test_quantile(self):
        self.assertEqual(wquantile([10, 20, 30, 40], [1, 1, 1, 1], 0.25), 10)
        self.assertEqual(wquantile([10, 20, 30, 40], [1, 1, 1, 1], 0.26), 20)


class Burden(unittest.TestCase):
    def test_eurostat_formula_nets_allowances(self):
        # (12*hc - allowance) / (income - allowance)
        self.assertAlmostEqual(analyse.burden(person(hc=500, inc=20000, al=1200)), (6000 - 1200) / (20000 - 1200))

    def test_threshold_is_strict(self):
        p = person(hc=1000, inc=30000)          # exactly 40%
        self.assertAlmostEqual(analyse.burden(p), 0.4)
        self.assertEqual(analyse.ob_share([p]), 0.0)

    def test_zero_or_negative_income_counts_as_overburdened(self):
        self.assertEqual(analyse.burden(person(inc=0)), math.inf)
        self.assertEqual(analyse.ob_share([person(inc=-5)]), 100.0)

    def test_missing_cost_is_excluded(self):
        self.assertIsNone(analyse.burden(person(hc=None)))
        self.assertEqual(analyse.ob_share([person(hc=None), person(hc=100)]), 0.0)

    def test_rent_ratio(self):
        self.assertAlmostEqual(analyse.rent_ratio(person(rent=500, inc=24000)), 0.25)


class Shapley(unittest.TestCase):
    def test_parts_add_up(self):
        c0 = {"a": (60.0, 30.0), "b": (40.0, 4.0)}
        c1 = {"a": (30.0, 9.0), "b": (70.0, 7.0)}
        O0, O1, comp, within = analyse.shapley(c0, c1)
        self.assertAlmostEqual(O0, 34.0)
        self.assertAlmostEqual(O1, 16.0)
        self.assertAlmostEqual(comp + within, O1 - O0)

    def test_pure_composition(self):
        c0 = {"a": (50.0, 25.0), "b": (50.0, 5.0)}
        c1 = {"a": (20.0, 10.0), "b": (80.0, 8.0)}
        _, _, comp, within = analyse.shapley(c0, c1)
        self.assertAlmostEqual(within, 0.0)


class Reader(unittest.TestCase):
    def test_rows_tab_and_comma(self):
        tab = b'"HB010"\t"HB030"\n2025\t17\n'
        com = b"HB010,HB030\n2013,5\n"
        self.assertEqual(list(extract_ecv.rows(tab)), [{"HB010": "2025", "HB030": "17"}])
        self.assertEqual(list(extract_ecv.rows(com)), [{"HB010": "2013", "HB030": "5"}])

    def test_nested_zip_members(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as z:
            z.writestr("CSV/ECV_Th_2030.tab", "x\n")
            z.writestr("CSV/esudb30h.csv", "y\n")
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as z:
            z.writestr("ECV_Th_2030.zip", inner.getvalue())
        names = sorted(n for n, _ in extract_ecv._members(zipfile.ZipFile(outer)))
        self.assertEqual(names, ["CSV/ECV_Th_2030.tab", "CSV/esudb30h.csv"])


class CJE(unittest.TestCase):
    def test_reproduce_98_7(self):
        c = analyse.CJE
        self.assertEqual(round(100 * c["asking_rent"] / (c["salary_annual"] / 12), 1), 98.7)
        self.assertEqual(round(100 * 12 * c["asking_rent"] / c["household_income_annual"], 1), 45.3)


@unittest.skipUnless(HAVE, "data/ not built")
class Results(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.S = json.load(open(D / "summary.json", encoding="utf-8"))

    def test_eurostat_replicated(self):
        r = self.S["replication"]
        self.assertLessEqual(r["lvho07c_max_abs_diff"], 0.3)
        self.assertGreaterEqual(r["lvho07c_exact"], 70)
        self.assertEqual(r["rent_mkt_2025_ours"], r["rent_mkt_2025_eurostat"])
        self.assertEqual(r["rent_mkt_2021_ours"], r["rent_mkt_2021_eurostat"])
        lw = self.S["living_with_parents"]
        self.assertEqual(round(lw["18-34_2025"], 1), lw["eurostat_18-34_2025"])

    def test_headline_young_tenants(self):
        y = self.S["young_tenants_18-34_2025"]
        self.assertEqual((y["n"], y["households"]), (1048, 783))
        self.assertEqual(y["overburden_pct"], 31.5)
        self.assertEqual(y["median_rent_to_income_pct"], 24.7)

    def test_decomposition_adds_up(self):
        for k, d in self.S["decomposition"].items():
            if d.get("composition_pp") is not None:
                self.assertAlmostEqual(d["composition_pp"] + d["within_pp"], d["change_pp"], delta=0.15, msg=k)

    def test_cje_own_figure_bracketed(self):
        rng = [r for r in self.S["cje_own"] if r["measure"].startswith("range of our mean HH070")][0]["ours"]
        lo, hi = (float(x) for x in rng.split("-"))
        self.assertTrue(lo <= 780.0 <= hi)

    def test_small_cells_suppressed(self):
        for name in ("young_burden.csv", "young_tenants_breakdown.csv"):
            with open(D / name, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    if int(r["households"]) < 10:
                        self.assertTrue(all(r[k] == "" for k in ("median_rent", "median_income", "median_burden_pct",
                                                                  "overburden_pct")), (name, r["year"], r.get("value")))
                        self.assertNotEqual(r["suppressed"], "")

    def test_quotes_found(self):
        with open(D / "quotes.csv", encoding="utf-8") as f:
            bad = [r["quote"][:60] for r in csv.DictReader(f) if r["found_in_locked_file"] != "True"]
        self.assertEqual(bad, [])

    def test_no_unit_level_data_in_data_dir(self):
        for p in D.glob("*.csv"):
            with open(p, encoding="utf-8") as f:
                head = [h.strip().lower() for h in f.readline().split(",")]
            for col in ("pid", "hh", "rb030", "hb030", "db030", "pb030"):
                self.assertNotIn(col, head, p.name)

    def test_bound_scenarios_present(self):
        b = self.S["bound"]
        for k in ("2021_tenancy_rate_all_ob", "2021_all_rent_all_ob", "2021_low_income_final", "2021_low_income_base"):
            self.assertIn(k, b)
        # for young tenants the channel bound cannot rule out that selection explains their whole fall
        self.assertGreater(b["2021_all_rent_all_ob"]["young_share_of_fall_explained_pct"], 100)


if __name__ == "__main__":
    unittest.main()
