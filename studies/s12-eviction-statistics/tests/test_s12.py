import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from s12lib import RAW, canon, q_from_cgpj, q_index, q_label  # noqa: E402


class Labels(unittest.TestCase):
    def test_quarters(self):
        self.assertEqual(q_from_cgpj("26-T1"), "2026Q1")
        self.assertEqual(q_from_cgpj("13-T3(1)"), "2013Q3")
        self.assertEqual(q_from_cgpj("25-T3*"), "2025Q3")
        self.assertIsNone(q_from_cgpj("Total 2025"))
        self.assertEqual(q_label(q_index("2025Q4") + 1), "2026Q1")


class Names(unittest.TestCase):
    def test_canon(self):
        self.assertEqual(canon("Hospitalet de Llobregat, L'"), canon("L'HOSPITALET DE LLOBREGAT"))
        self.assertEqual(canon("Línea de la Concepción, La"), canon("LA LINEA DE LA CONCEPCION"))
        self.assertEqual(canon("MAO-MAHON"), canon("MAHON"))
        self.assertEqual(canon("Vila-real"), canon("VILLARREAL/VILA-REAL"))
        self.assertEqual(canon("Dénia"), canon("DENIA"))


class Regression(unittest.TestCase):
    def test_wls_hc3(self):
        from s12lib import wls
        x = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        y = 1.0 - 2.0 * x
        beta, se, df = wls(y, np.column_stack([np.ones(5), x]), np.array([1, 2, 3, 4, 5.0]))
        self.assertAlmostEqual(beta[1], -2.0)
        self.assertEqual(df, 3)
        self.assertTrue(np.all(se < 1e-6))

    def test_wls_hc3_value(self):
        from s12lib import wls
        rng = np.random.default_rng(1)
        x = rng.normal(size=40)
        y = 0.5 * x + rng.normal(size=40)
        X = np.column_stack([np.ones(40), x])
        beta, se, _ = wls(y, X, np.ones(40))
        # HC3 by hand
        XtXi = np.linalg.inv(X.T @ X)
        e = y - X @ beta
        h = np.sum(X @ XtXi * X, axis=1)
        V = XtXi @ (X.T * (e / (1 - h)) ** 2) @ X @ XtXi
        self.assertAlmostEqual(se[1], float(np.sqrt(V[1, 1])))


@unittest.skipUnless((RAW / "lexnet_numo_fases.xls").exists(), "locked inputs not downloaded")
class LockedInputs(unittest.TestCase):
    def test_phase_seats(self):
        from s12lib import read_phase_xls
        ph = read_phase_xls()
        self.assertEqual(len(ph[1]), 315)
        self.assertEqual(len({canon(m) for _, m in ph[2]}), 16)
        self.assertEqual(len(ph[3]), 30)


if __name__ == "__main__":
    unittest.main()
