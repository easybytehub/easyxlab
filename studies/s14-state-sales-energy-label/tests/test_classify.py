"""Unit tests for the S14 classifier (scripts/classify.py). Run: python3 -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import classify as C  # noqa: E402


class TestEnergy(unittest.TestCase):
    def st(self, t):
        e = C.energy_status(t)
        return e["status"], e["letters"]

    def test_ratings(self):
        cases = {
            "De acuerdo con el Certificado de Eficiencia Energética el inmueble ha obtenido la calificación: "
            "consumo de energía KW h/m² año:207E; emisiones Kg CO2 /m² año: 43E.": "E",
            "Calificación de eficiencia energética: Calificación (G) Consumo 169,24 kWh/m2año; (F) Emisiones 35,13 CO2/m2año": "FG",
            "Calificación energética: Etiqueta Eficiencia Energética. Consumo de energía 271.8 Kwh/m2 año. G y Emisiones 48.0 Kg CO2/m² año. E": "EG",
            "CERTIFICADO DE EFICIENCIA ENERGÉTICA: el inmueble ha obtenido la calificación:\n"
            "Consumo Energía Primaria KWh/m2/año | Letra | Emisiones KgCO2/m2/año | Letra\n92.56 KWh | F | 15.97 Kg | F": "F",
            "- Consumo de energía (kwh/m² año): 254 D": "D",
        }
        for t, letters in cases.items():
            self.assertEqual(self.st(t), ("rating", letters), t)

    def test_both_indicators(self):
        self.assertTrue(C.energy_status("Calificación de eficiencia energética: (G) Consumo 169 kWh/m2año; (F) Emisiones 35 CO2/m2año")["both_indicators"])
        self.assertFalse(C.energy_status("Calificación energética: G.")["both_indicators"])

    def test_door_letters_are_not_ratings(self):
        self.assertEqual(self.st("Vivienda letra E, planta 2. Dispone de certificado de eficiencia energética.")[0],
                         "certificate_reference")
        self.assertEqual(self.st("VIVIENDA SEGUNDO LETRA D, en planta segunda. Calificación energética: en tramitación.")[0],
                         "pending")

    def test_other_statuses(self):
        self.assertEqual(self.st("Calificación energética: Inmueble excluido del ámbito de aplicación del R.D 235/2013")[0],
                         "exempt_declared")
        self.assertEqual(self.st("Calificación de eficiencia energética: Exento según el artículo 3.2.e) del Real Decreto 390/2021.")[0],
                         "exempt_declared")
        self.assertEqual(self.st("El inmueble no dispone de certificado de eficiencia energética.")[0], "no_certificate_stated")
        self.assertEqual(self.st("El certificado de eficiencia energética se encuentra a disposición de los interesados.")[0],
                         "certificate_reference")
        self.assertEqual(self.st("A efectos de la calificación energética, el certificado está en el pliego.")[0],
                         "certificate_reference")
        self.assertEqual(self.st("Local comercial en planta baja. Tipo de licitación: 30.000 euros.")[0], "none")
        # urban zoning "calificación" is not an energy statement
        self.assertEqual(self.st("Calificación urbanística: residencial, zona B.")[0], "none")


class TestTypeScope(unittest.TestCase):
    def test_types(self):
        cases = {
            "Lote 1: Piso sito en Polígono Sur, Nº 6 – 4º - C, Villanueva": "residential",
            '1.- " Local en calle Mayor, 2, bajo derecha", en Villanueva': "commercial",
            "Lote 2 - Expediente 1. Parcela 800 del polígono 5, paraje Pedregal": "land",
            "LOTE 21: Finca rústica: parcela 189, polígono 4, regadío": "land",
            "-LOTE Nº 2: PLAZA DE GARAJE Nº 41 DEL EDIFICIO SITO EN C/MAYOR": "garage",
            "Lote número 6: Unidad de almacenamiento Villanueva": "industrial_agricultural",
            "Lote 3. Edificio en ruinas en calle Mayor": "ruin",
            "Local situado en la avenida X. Urbana: nave industrial sobre la parcela de terreno": "industrial_agricultural",
            "18 | Villanueva | Urbana | C/ Mayor, 47 P2 Pta. 2 | 97.173,48 €": "unit_in_building",
            "9 | Villanueva | 1 | 3 | 00-57-60 | 44444A001000030000FF | 2.764,80 €": "land",
            "22 | Villanueva | Polígono 1, Parcela 14 | 55555A001000140000GG y 55555A001000140001HH": "rural_with_construction",
        }
        for t, want in cases.items():
            self.assertEqual(C.lot_type(t), want, t)

    def test_garage_from_context(self):
        self.assertEqual(C.lot_type("LOTE 1.- Plaza nº 1 con número de finca registral 11427/C1.",
                                    context="subasta de plazas de garaje del edificio"), "garage")

    def test_scope(self):
        none = {"status": "none", "letters": "", "evidence": ""}
        rating = {"status": "rating", "letters": "E", "evidence": ""}
        exempt = {"status": "exempt_declared", "letters": "", "evidence": ""}
        self.assertEqual(C.scope("Vivienda en calle X", "residential", none), ("covered", ""))
        self.assertEqual(C.scope("Solar en calle X", "land", none)[0], "excluded")
        self.assertEqual(C.scope("Vivienda en calle X", "residential", exempt)[0], "excluded")
        self.assertEqual(C.scope("Una tercera parte indivisa de la vivienda", "residential", none)[0], "undeterminable")
        self.assertEqual(C.scope("Vivienda tipo G. Cuota de participación: 2,5%", "residential", none)[0], "covered")
        self.assertEqual(C.scope("Edificio catalogado con protección integral", "building", none)[0], "undeterminable")
        self.assertEqual(C.scope("Finca urbana en calle X", "unknown", none)[0], "undeterminable")
        self.assertEqual(C.scope("Finca urbana en calle X", "unknown", rating)[0], "covered")
        self.assertEqual(C.scope("Caseta aislada de 30 m2", "building", none)[0], "excluded")
        self.assertEqual(C.scope("Local comercial en bruto en planta baja", "commercial", none)[0], "excluded")
        self.assertEqual(C.scope("Edificio en ruinas", "ruin", none)[0], "undeterminable")
        self.assertEqual(C.scope("Plaza de garaje", "garage", none)[0], "excluded")

    def test_compliance(self):
        rating = {"status": "rating"}
        ref = {"status": "certificate_reference"}
        pend = {"status": "pending"}
        none = {"status": "none"}
        self.assertEqual(C.compliance("covered", rating), "yes")
        self.assertEqual(C.compliance("covered", ref), "no")
        self.assertEqual(C.compliance("covered", ref, "lenient"), "yes")
        self.assertEqual(C.compliance("covered", pend, "lenient"), "yes")
        self.assertEqual(C.compliance("covered", none, "lenient"), "no")
        self.assertEqual(C.compliance("excluded", none), "n/a")


class TestNoticeKindSeller(unittest.TestCase):
    def test_kind(self):
        k = C.notice_kind
        self.assertEqual(k("Resolución de la Delegación de Economía y Hacienda en Cádiz por la que se convoca subasta pública para la enajenación de bienes inmuebles."), "offer")
        self.assertEqual(k("Corrección de errores del anuncio de la Delegación de Economía y Hacienda de Cuenca de subasta pública de varias fincas urbanas."), "correction")
        self.assertEqual(k("Anuncio de la Delegación de Economía y Hacienda de Valencia, por la que se suspende el procedimiento de enajenación del lote número 2"), "annulment")
        self.assertEqual(k("Anuncio de la Delegación de Economía y Hacienda en Melilla, de Acuerdo de incoación de procedimiento de enajenación directa de finca titularidad del Patrimonio del Estado."), "direct_named")
        self.assertEqual(k("Anuncio de licitación de: Junta de Contratación. Objeto: Servicio de cafetería, restaurante y venta automática en el edificio."), "other")
        self.assertEqual(k("Anuncio de Aena S.M.E., S.A. por el que se convoca la subasta pública de bienes muebles no aptos para el servicio."), "not_real_estate")
        self.assertEqual(k("Resolución de la Autoridad Portuaria de Tarragona por la que se anuncia la enajenación mediante subasta pública de su participación del treinta y cinco por ciento en la Sociedad Anónima Nautic Tarragona, SA."), "not_real_estate")

    def test_seller(self):
        self.assertEqual(C.seller("Resolución de la Dirección Provincial de la Tesorería General de la Seguridad Social de Madrid por la que se anuncia subasta")[0], "TGSS")
        self.assertEqual(C.seller("Anuncio de la Delegación de Economía y Hacienda en Girona, por la que se convoca subasta")[0], "Patrimonio del Estado (DEH)")
        self.assertEqual(C.seller("Resolución del organismo autónomo Instituto de Vivienda, Infraestructura y Equipamiento de la Defensa, por la que se anuncian subastas")[0], "INVIED (Defensa)")


if __name__ == "__main__":
    unittest.main()
