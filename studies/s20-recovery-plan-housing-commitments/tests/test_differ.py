"""Unit tests for scripts/differ.py (python3 -m unittest discover -s tests)."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import differ as D

# Literal fragments of target 31 (C2.I2) and of measure C2.I7, as in the CID annexes.
T31_2021 = {"name": "New dwellings built for social rental or at affordable prices compliant with energy efficient criteria",
            "unit": "Number", "baseline": "0", "goal": "20 000", "quarter": "Q2", "year": "2026",
            "description": "At least 20 000 dwellings built for social rental or at affordable prices compliant with energy efficient criteria."}
T31_2024 = dict(T31_2021, description="At least EUR 950 000 000 of grants awarded leading to the completion of at least 20 000 dwellings for social rental or at affordable prices compliant with energy efficient criteria.")
T31_2025 = {"name": "Provision of dwellings", "unit": "Number", "baseline": "0", "goal": "17 365", "quarter": "Q2", "year": "2026",
            "description": "Provision of a total of 17 365 dwellings under the Programme to support the construction of social rental housing in energy-efficient buildings."}
T31_2026 = {"name": "Construction or rehabilitation of dwellings", "unit": "Number", "baseline": "0", "goal": "15 718", "quarter": "Q2", "year": "2026",
            "description": "Construction or rehabilitation of a total of 15 718 dwellings under programmes to support social rental housing in energy efficient buildings."}


class TestParsing(unittest.TestCase):
    def test_eur_amounts(self):
        self.assertEqual(D.eur_amounts("Spain shall transfer EUR 4 000 000 000 to the ICO Facility."), [4000000000])
        self.assertEqual(D.eur_amounts("at least EUR 567 854 983 of financing"), [567854983])
        self.assertEqual(D.eur_amounts("EUR 750 million and EUR 1.5 billion"), [750000000, 1500000000])
        self.assertEqual(D.eur_amounts("no money here, 20 000 dwellings"), [])

    def test_dates_and_numbers(self):
        self.assertEqual(D.dates("shall be completed by 30 June 2026 (Q3 2026)"), ["30 June 2026", "Q3 2026"])
        self.assertEqual(D.other_numbers("at least 20 000 dwellings, 80 % of the limit, Royal Decree 853/2021"), ["20 000", "80%"])
        self.assertEqual(D.other_numbers("EUR 950 000 000 of grants by 30 June 2026"), [])

    def test_tokens_keep_grouped_numbers(self):
        self.assertIn("20 000", D.tokens("at least 20 000 new dwellings"))
        self.assertIn("EUR 4 000 000 000", D.tokens("transfer EUR 4 000 000 000 to"))


class TestClassify(unittest.TestCase):
    def test_amount_added_same_goal(self):
        # Dec-2024: EUR 950 million added to target 31, quantity unchanged (the new text
        # repeats "20 000": a repeated number is not a new quantity)
        c = D.classify(T31_2021, T31_2024)
        self.assertEqual(c, ["amount", "definition"])

    def test_quantity_and_definition(self):
        c = D.classify(T31_2024, T31_2025)
        self.assertEqual(c, ["amount", "definition", "quantity"])

    def test_definition_and_quantity_2026(self):
        c = D.classify(T31_2025, T31_2026)
        self.assertEqual(c, ["definition", "quantity"])

    def test_deadline(self):
        old = {"name": "x", "goal": "100%", "quarter": "Q3", "year": "2026", "description": "Legal agreements."}
        new = dict(old, quarter="Q2")
        self.assertEqual(D.classify(old, new), ["deadline"])

    def test_editorial_only(self):
        old = {"description": "managed by Instituto de Crédito Official (ICO), at least 80 % below"}
        new = {"description": "managed by Instituto de Crédito Oficial (ICO), at least 80% below"}
        self.assertEqual(D.classify(old, new), ["editorial"])

    def test_spacing_only_is_editorial(self):
        # milestone 30, COM(2026) 257 -> COM(2026) 435: "80 % of the limit" -> "80% of the limit"
        old = {"description": "to limit the value of non-renewable primary energy consumption to 80 % of the limit set in section HE 0"}
        new = {"description": "to limit the value of non-renewable primary energy consumption to 80% of the limit set in section HE 0"}
        self.assertEqual(D.classify(old, new), ["editorial"])
        # C2.I7, COM(2025) 177 -> COM(2025) 271: "1.Description" -> "1. Description"
        self.assertEqual(D.classify({"description": "content: 1.Description of"}, {"description": "content: 1. Description of"}), ["editorial"])

    def test_identical(self):
        self.assertEqual(D.classify(T31_2021, dict(T31_2021)), [])

    def test_added_removed(self):
        self.assertEqual(D.classify(None, T31_2021), ["added"])
        self.assertEqual(D.classify(T31_2021, None), ["removed"])

    def test_word_diff_render(self):
        ops = D.word_diff("build at least 20 000 new dwellings", "build at least 15 718 new dwellings")
        self.assertEqual(ops, [("replace", "20 000", "15 718")])
        self.assertEqual(D.render(ops), "[-20 000-] {+15 718+}")


if __name__ == "__main__":
    unittest.main()
