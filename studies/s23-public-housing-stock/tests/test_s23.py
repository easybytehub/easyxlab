"""Unit tests for the S23 parsers and checks (python3 -m unittest discover -s tests).
They run offline on literal fragments of the sources."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import ovs_tables as O
import s23lib as L
import robots9309 as R


class TestNumbers(unittest.TestCase):
    def test_spanish_numbers(self):
        self.assertEqual(O.num("178.493"), 178493)
        self.assertEqual(O.num("9,3%"), 9.3)
        self.assertEqual(O.num("0"), 0)
        self.assertEqual(O.num("1.660.122"), 1660122)

    def test_region_names(self):
        self.assertEqual(O.region_of("  Asturias (Principado de)           10.464 "), "Asturias")
        self.assertEqual(O.region_of(" TOTAL                          161.922 "), "TOTAL")
        self.assertIsNone(O.region_of("   Fuente: Encuesta sobre vivienda social"))


class TestTables(unittest.TestCase):
    # literal lines (pdftotext -layout) of the 2024 bulletin, Tabla 2.2 and Tabla 2.8
    T22 = ("Tabla 2.2. Parque de vivienda de titularidad de las comunidades\n"
           " Andalucía                      48.834        67%           0          0%        48.834        67%             0             0%         18.522     25%     5.708     8%      73.064\n"
           " Asturias (Principado de)        8.817        100%          0          0%         8.817        100%            0             0%            0       0%        0       0%       8.817\n"
           " TOTAL                          161.922       64%       34.920         14%       196.842       78%           6.427           3%         34.258     14%     14.410    6%      251.937\n"
           "Fuente: Encuesta sobre vivienda social 2023\n")
    T28 = ("Tabla 2.8. Parque de vivienda de titularidad de los ayuntamientos de más de 20.000 habitantes\n"
           "ANDALUCÍA\n"
           "   Adra                              25.195\n"
           "   Almería*                         200.578          -         -        -         -        62      69%       18      20%        10       11%       0       0%         90\n"
           "COMUNITAT VALENCIANA\n"
           "   Alacant/Alicante                 349.282          746     100%      0%           746     100%       0       0%       0       0%       0       0%       746\n"
           "   Cádiz                             111.811       1.962      93%       0        0%       1.962     93%     138       7%        0         0%       0       0%       2.100\n")

    def test_regional_table(self):
        rows = O.ccaa_2024_t22(self.T22)
        self.assertEqual([r["region"] for r in rows], ["Andalucía", "Asturias", "TOTAL"])
        self.assertEqual(rows[0]["rental"], 48834)
        self.assertEqual(rows[1]["total"], 8817)          # "(Principado de)" must not shift columns
        self.assertEqual(rows[2]["rental_ppp"], 34920)

    def test_municipal_table(self):
        rows = O.municipal_2024(self.T28)
        by = {r["municipality"]: r for r in rows}
        self.assertEqual(by["Adra"]["has_data"], "")
        self.assertEqual(by["Almería"]["data_from_2019_survey"], "yes")
        self.assertEqual(by["Almería"]["rental"], 62)
        self.assertEqual(by["Almería"]["total"], 90)
        self.assertEqual(by["Alacant/Alicante"]["rental_ppp"], "")   # a bare "0%" with no units cell
        self.assertEqual(by["Alacant/Alicante"]["rental"], 746)
        self.assertEqual(by["Cádiz"]["rental_public"], 1962)
        self.assertEqual(by["Cádiz"]["total"], 2100)
        self.assertEqual(by["Cádiz"]["region_heading"], "COMUNITAT VALENCIANA")

    def test_eu_table(self):
        t = ("Tabla 2.1. Parque de vivienda\n"
             "    España          46.815.910   25.206.525     18.081.595        2,5%           452.040        2,59            1,39              2,5\n"
             "    UE 28          502.830.942   243.603.708    204.934.814       9,3%          18.969.954      2,45            1,19              9,3\n"
             " Fuente: Censo 2011, Eurostat\n")
        rows = O.eu_table(t, 2020)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["country"], "UE 28")
        self.assertEqual(rows[1]["social_dwellings"], 18969954)
        self.assertAlmostEqual(rows[1]["social_dwellings"] / rows[1]["principal_dwellings"] * 100, 9.257, places=2)


class TestQuotes(unittest.TestCase):
    def test_normalisation(self):
        self.assertEqual(L.qnorm("Spain’s  social\nhousing – stock"), "Spain's social housing - stock")
        self.assertEqual(L.qnorm("vivien­da"), "vivienda")


class TestRobots(unittest.TestCase):
    def test_rfc9309(self):
        g = R.parse("User-agent: *\nDisallow: /\n\nUser-agent: Googlebot\nDisallow: /api/\n")
        self.assertFalse(R.allowed(g, "EasyxLab-research", "/dataset/x.csv"))   # datos.comunidad.madrid pattern
        g = R.parse("User-agent: *\nDisallow: /search\n")
        self.assertTrue(R.allowed(g, "EasyxLab-research", "/news/search?q=x&format=rss"))  # Bing News RSS
        self.assertFalse(R.allowed(g, "EasyxLab-research", "/search?q=x"))


if __name__ == "__main__":
    unittest.main()
