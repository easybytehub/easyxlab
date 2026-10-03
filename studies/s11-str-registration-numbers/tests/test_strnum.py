"""Tests for scripts/strnum.py (run: python3 -m unittest discover -s tests). The numbers below
are synthetic: they follow the published formats and were not taken from any listing, but
some round or sequential ones may coincide with real registered numbers."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from strnum import split_license, parse_regional, parse_national, exempt_reason

NAT_TU = "ESFCTU" + "0000" + "08" + "0" * 12 + "1" * 0 + "0" * 18 + "HUTB-000001"


class Split(unittest.TestCase):
    def test_labelled_two_blocks(self):
        raw = ("Spain - National registration number<br />ESFCNT" + "0" * 47 + "<br /><br />"
               "Madrid - Regional registration number<br />Exempt - seasonal rental")
        s = split_license(raw)
        self.assertTrue(s["labelled"])
        self.assertTrue(s["national"].startswith("ESFCNT"))
        self.assertEqual(s["regional"], "Exempt - seasonal rental")
        self.assertEqual(s["regional_label"], "Madrid")

    def test_order_and_single_block(self):
        s = split_license("Barcelona - Regional registration number<br />HUTB-000123")
        self.assertEqual(s["regional"], "HUTB-000123")
        self.assertIsNone(s["national"])

    def test_unlabelled(self):
        s = split_license("OSE-STRREG-0000123")
        self.assertFalse(s["labelled"])
        self.assertEqual(s["unlabelled"], ["OSE-STRREG-0000123"])

    def test_empty(self):
        self.assertEqual(split_license("")["unlabelled"], [])
        self.assertIsNone(split_license(None)["regional"])


class Catalonia(unittest.TestCase):
    def p(self, v):
        return parse_regional(v, "catalonia")

    def test_variants_same_key(self):
        for v in ("HUTB-012345", "HUTB012345", "hutb 12345", "HUTB-0012345", "HUTB–012345", "Nº HUTB-012345"):
            r = self.p(v)
            self.assertEqual((r.status, r.key, r.kind), ("ok", "HUTB-012345", "tourist dwelling"), v)

    def test_control_digit_joined(self):
        r = self.p("HUTG-00432107")
        self.assertEqual((r.status, r.key, r.extra), ("ok", "HUTG-004321", "07"))

    def test_control_digit(self):
        r = self.p("HUTG-004321-07")
        self.assertEqual((r.status, r.key, r.extra, r.province), ("ok", "HUTG-004321", "07", "G"))

    def test_other_types(self):
        self.assertEqual(self.p("HB-001234").kind, "hotel")
        self.assertEqual(self.p("LLB-000010").kind, "shared home")
        r = self.p("AJ000123")
        self.assertEqual((r.status, r.registry_open), ("ok", False))

    def test_placeholder_malformed(self):
        self.assertEqual(self.p("HUTB-000000").status, "placeholder")
        self.assertEqual(self.p("En tràmit").status, "malformed")
        self.assertEqual(self.p("XYZ-12345").status, "malformed")
        self.assertEqual(self.p("HUTB-1234567").status, "malformed")

    def test_exempt_empty(self):
        self.assertEqual(self.p("Exempt - seasonal rental").status, "exempt")
        self.assertEqual(exempt_reason("Exempt - seasonal rental"), "seasonal rental")
        self.assertEqual(exempt_reason("Exempt"), "unspecified")
        self.assertEqual(self.p("  ").status, "empty")


class Valencia(unittest.TestCase):
    def p(self, v):
        return parse_regional(v, "valencia")

    def test_new_and_old(self):
        self.assertEqual(self.p("CV-VUT0012345-V").key, "CV-VUT0012345-V")
        self.assertEqual(self.p("CV-VUT-0012345-V").key, "CV-VUT0012345-V")
        r = self.p("VT-12345-V")
        self.assertEqual((r.key, r.extra), ("CV-VUT0012345-V", "old-format"))
        self.assertEqual(self.p("VT12345V").key, "CV-VUT0012345-V")
        self.assertEqual(self.p("VT-512345-A").key, "CV-VUT0512345-A")
        self.assertEqual(self.p("VT-1234-CS").key, "CV-VUT0001234-CS")
        r = self.p("VUT0012345-V")
        self.assertEqual((r.key, r.extra), ("CV-VUT0012345-V", "variant"))
        self.assertEqual(self.p("CV-VT-0012345-A").key, "CV-VUT0012345-A")
        self.assertEqual(self.p("VUT0012345").status, "malformed")
        self.assertEqual(self.p("ARU-123-V").kind, "rural")

    def test_other(self):
        r = self.p("HV-1234")
        self.assertEqual((r.status, r.kind, r.registry_open), ("ok", "hotel", False))
        self.assertEqual(self.p("AT-12345-V").kind, "tourist apartments")
        self.assertEqual(self.p("VT-0-V").status, "placeholder")
        self.assertEqual(self.p("12345").status, "malformed")


class Andalucia(unittest.TestCase):
    def p(self, v):
        return parse_regional(v, "andalucia")

    def test_series(self):
        for v in ("VFT/MA/12345", "VUT/MA/12345", "VFT-MA-12345", "VTF/MA/12345", "vft/ma/012345", "VFT / MA / 12345"):
            r = self.p(v)
            self.assertEqual((r.status, r.key, r.tourist_dwelling), ("ok", "VUT/MA/12345", True), v)
        self.assertEqual(self.p("VFT/MA/12345").extra, "renamed-VFT")
        self.assertEqual(self.p("A/SE/00123").key, "A/SE/123")
        self.assertEqual(self.p("H/SE/1234").kind, "hotel")

    def test_bad(self):
        self.assertEqual(self.p("VFT/XX/12345").status, "malformed")
        self.assertEqual(self.p("VFT/MA/00000").status, "placeholder")
        r = self.p("CTC-2020123456")
        self.assertEqual((r.status, r.kind, r.registry_open), ("ok", "CTC code", False))
        self.assertEqual(self.p("VUTMA12345").key, "VUT/MA/12345")
        self.assertEqual(self.p("VFT/MA12345").key, "VUT/MA/12345")


class Madrid(unittest.TestCase):
    def test(self):
        p = lambda v: parse_regional(v, "madrid")
        self.assertEqual(p("VT-1234").key, "VT-1234")
        self.assertEqual(p("VT - 01234").key, "VT-1234")
        self.assertEqual(p("VT12345").key, "VT-12345")
        self.assertEqual(p("VT-0").status, "placeholder")
        self.assertEqual(p("En proceso").status, "malformed")
        self.assertEqual(p("AM-1234").kind, "tourist apartments")
        self.assertFalse(p("VT-1234").registry_open)


class NYC(unittest.TestCase):
    def test(self):
        p = lambda v: parse_regional(v, "nyc")
        self.assertEqual(p("OSE-STRREG-0000123").key, "OSE-STRREG-0000123")
        self.assertEqual(p("ose-strreg-0000123").key, "OSE-STRREG-0000123")
        self.assertEqual(p("Exempt").status, "exempt")
        self.assertEqual(p("STR-123").status, "malformed")


class National(unittest.TestCase):
    def test(self):
        tu = "ESFCTU" + "0" * 36 + "HUTB-000001"
        self.assertEqual(len(tu), 53)
        self.assertEqual(parse_national(tu).kind, "national-TU")
        nt = "ESHFNT" + "1" * 47
        self.assertEqual(parse_national(nt).kind, "national-NT")
        self.assertEqual(parse_national("ESLLLL" + "1" * 47).kind, "national-other")
        self.assertEqual(parse_national("Exempt - hotel").status, "exempt")
        self.assertEqual(parse_national("").status, "empty")


if __name__ == "__main__":
    unittest.main()
