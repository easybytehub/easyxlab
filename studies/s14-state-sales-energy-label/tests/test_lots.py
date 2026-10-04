"""Unit tests for the S14 lot parser (scripts/lots.py). Run: python3 -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import lots as L  # noqa: E402

HTML = """<html><h3 class="documento-tit">Resolución de la Dirección Provincial de la Tesorería General de la
Seguridad Social de Madrid por la que se anuncia subasta pública de bienes inmuebles.</h3>
<dl><dt>Publicado en:</dt><dd>«BOE» núm. 1</dd><dt>Sección:</dt><dd>V. Anuncios<span> - B. Otros anuncios oficiales</span></dd>
<dt>Departamento:</dt><dd>Ministerio de Inclusión</dd><dt>Referencia:</dt><dd>BOE-B-2024-00001</dd></dl>
<div id="textoxslt">
<p class="parrafo">Acordada su enajenación, se convoca subasta pública de los inmuebles:</p>
<p class="parrafo">Lote 1: Finca urbana situada en la calle A nº 8, 1º Izq. Referencia catastral:1111111AA1111A0001AA.</p>
<p class="parrafo">De acuerdo con el Certificado de Eficiencia Energética el inmueble ha obtenido la calificación: consumo de energía KW h/m² año:207E; emisiones Kg CO2 /m² año: 43E.</p>
<p class="parrafo">Lote 2:: Finca urbana situada en la calle A nº 8, 2º Izq. Referencia catastral:1111111AA1111A0002BB.</p>
<table><tr><td>Consumo</td><td>Letra</td></tr><tr><td>215 kWh</td><td>E</td></tr></table>
<p class="parrafo">La subasta pública tendrá lugar el día 17 de octubre de 2024.</p>
<p class="parrafo_2">Madrid, 18 de julio de 2024.- El Director Provincial.</p>
</div>
<!-- #textoxslt --></html>"""


class TestNotice(unittest.TestCase):
    def test_metadata_and_paragraphs(self):
        n = L.parse_notice(HTML)
        self.assertTrue(n["title"].startswith("Resolución de la Dirección Provincial"))
        self.assertEqual(n["reference"], "BOE-B-2024-00001")
        self.assertIn("B. Otros anuncios oficiales", n["section"])
        self.assertIn("215 kWh | E", n["paragraphs"])

    def test_split_lote_headers_and_tail(self):
        n = L.parse_notice(HTML)
        pre, lots, tail, method = L.split_lots(n["paragraphs"])
        self.assertEqual(method, "lote_header")
        self.assertEqual([lab for lab, _ in lots], ["1", "2"])
        self.assertEqual(len(pre), 1)
        self.assertTrue(any("tendrá lugar" in p for p in tail))
        self.assertTrue(any("215 kWh | E" in p for p in lots[1][1]))


class TestHeaders(unittest.TestCase):
    def label(self, p):
        f = L.fold(p)
        return L._lot_label(p) if (L.LOT_HEADER.match(f) or L.LOT_MULTI.match(f)) else None

    def test_variants(self):
        cases = {"Lote 1: Finca": "1", "LOTE Nº 2: PLAZA": "2", "Lote núm. 3 - En tercera": "3",
                 "Lote número 4. Vivienda": "4", "LOTE II.– FINCA URBANA": "2", "Lote único": "1",
                 "Finca nº 1. Expediente CIBI": "1", "- Lote 1: 3.409 €": "1"}
        for p, want in cases.items():
            self.assertEqual(self.label(p), want, p)

    def test_non_headers(self):
        for p in ("Finca 77870", "Lote 12,5 ha de secano", "Los lotes se adjudicarán", "Finca urbana en Madrid",
                  "Finca número 6, al tomo 2575, libro 1", "- Finca nº 64, tomo 1990, libro 286",
                  "Finca número 19.732, al tomo 2.137"):
            self.assertIsNone(self.label(p), p)

    def test_multi(self):
        self.assertEqual(self.label("Lotes 5 y 6: plazas"), "multi:5y6")


class TestSplitting(unittest.TestCase):
    def test_numbered_items(self):
        ps = ["Se acuerda la venta en subastas públicas de las propiedades:",
              '1.- "Local en calle X, 2, bajo derecha", en Villanueva.', "Finca número 29699. Referencia catastral: 5555555EE5555E0001GG.",
              '2.- "Campamento El Monte", en Villanueva (León)', "Finca número 24719, Referencia catastral: 33333A111150010000EE",
              '3.- "Vivienda en calle Y, 7", en Villavieja.', "Finca número 64140."]
        pre, lots, tail, method = L.split_lots(ps)
        self.assertEqual(method, "numbered")
        self.assertEqual([lab for lab, _ in lots], ["1", "2", "3"])

    def test_semicolon_rows(self):
        ps = ["- Relación de inmuebles a subastar:", "Lote; Acuerdo; Descripción; Tipo",
              "1; 10/01/2025; Rústica: parcela n.º 43 del polígono 513, paraje Monte", "Referencia Catastral: 22222A513000430000CC",
              "2; 10/01/2025; Rústica: parcela n.º 60 del polígono 513", "Referencia Catastral: 22222A513000600000DD"]
        pre, lots, tail, method = L.split_lots(ps)
        self.assertEqual((method, [lab for lab, _ in lots]), ("numbered", ["1", "2"]))

    def test_numbered_conditions_are_not_lots(self):
        ps = ["La información básica:", "1. Entidad adjudicadora.", "2. Objeto.", "3. Tramitación."]
        pre, lots, tail, method = L.split_lots(ps)
        self.assertNotEqual(method, "numbered")

    def test_inner_lot_sentences_and_merge(self):
        ps = ["Se subastan plazas de garaje:",
              "Lote 1 - Plaza nº 1: 3333333CC3333C0001DD. Lote 2 - Plaza nº 9: 3333333CC3333C0009EE.",
              "Tipos de licitación:", "- Lote 1: 3.409 €.", "- Lote 2: 3.099 €."]
        pre, lots, tail, method = L.split_lots(ps)
        self.assertEqual([lab for lab, _ in lots], ["1", "2"])
        self.assertTrue(any("3.409" in p for p in lots[0][1]))
        self.assertTrue(any("3333333CC3333C0001DD" in p for p in lots[0][1]))

    def test_table_rows(self):
        ps = ["Lote | Municipio | Polígono | Parcela | Referencia catastral",
              "1 | Villanueva | 1 | 919 | 11111A001000010000AA | 7.511,40 €",
              "2 | Villavieja | 1 | 49 | 11111A001000020000BB | 274,08 €"]
        pre, lots, tail, method = L.split_lots(ps)
        self.assertEqual(method, "table")
        self.assertEqual([lab for lab, _ in lots], ["1", "2"])

    def test_single_and_unsplit_and_not_described(self):
        single = ["El Ministerio autoriza a enajenar el inmueble:", "Local situado en la avenida X, nº 274, de Villanueva, referencia catastral 2222222BB2222B0001CC."]
        self.assertEqual(L.split_lots(single)[3], "single")
        unsplit = ["Se subastan:", "Local en calle X, referencia 2222222BB2222B0001CC y vivienda en calle Y, referencia 1111111AA1111A0001AA."]
        self.assertEqual(L.split_lots(unsplit)[3], "unsplit")
        nd = ["Descripción del objeto: Inmuebles relacionados en los Anexos núm. 1 de los Pliegos de Condiciones."]
        self.assertEqual(L.split_lots(nd)[3], "not_described")


class TestCadastre(unittest.TestCase):
    def test_refs(self):
        self.assertEqual(L.cadastral_refs("ref 1111111AA1111A0001AA y 11111A001000010000AA"),
                         ["1111111AA1111A0001AA", "11111A001000010000AA"])
        self.assertEqual(L.cadastral_refs("Referencia catastral: 4444444DD4444D0029FF."), ["4444444DD4444D0029FF"])
        self.assertEqual(L.cadastral_refs("teléfono 952619541"), [])


if __name__ == "__main__":
    unittest.main()
