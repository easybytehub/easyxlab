# SPDX-License-Identifier: Apache-2.0
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import hvd_rules as R  # noqa: E402


def test_eli_exact_and_variants():
    assert R.eli_status([R.ELI])[0] == "exact"
    assert R.eli_status(["https://eur-lex.europa.eu/eli/reg_impl/2023/138/oj"]) == (
        "malformed", ["https://eur-lex.europa.eu/eli/reg_impl/2023/138/oj"])
    assert R.eli_status(["http://data.europa.eu/eli/reg_impl/2023/138/o"])[0] == "malformed"
    assert R.eli_status(["http://data.europa.eu/eli/reg/2023/138"])[0] == "malformed"
    assert R.eli_status(["http://example.org/other"])[0] == "absent"
    assert R.eli_status(None)[0] == "absent"


def test_licence_named_class_a():
    for v in ["http://publications.europa.eu/resource/authority/licence/CC_BY_4_0", "CC_BY_4_0",
              "https://creativecommons.org/licenses/by/4.0/legalcode", "http://dcat-ap.de/def/licenses/cc-zero",
              "http://creativecommons.org/publicdomain/zero/1.0/", "http://spdx.org/licenses/CC-BY-4.0"]:
        assert R.licence_class(v) == "A", v


def test_licence_equivalent_class_b():
    for v in ["http://dcat-ap.de/def/licenses/dl-by-de/2.0", "http://dcat-ap.de/def/licenses/dl-zero-de/2.0",
              "http://www.etalab.gouv.fr/licence-ouverte-open-licence",
              "http://data.vlaanderen.be/id/licentie/modellicentie-gratis-hergebruik/v1.0",
              "http://data.gov.hr/id/licence/otvorena-dozvola-rh", "http://creativecommons.org/licenses/by/3.0/es"]:
        assert R.licence_class(v) == "B", v


def test_licence_restrictive_classes_win_over_a():
    assert R.licence_class("http://creativecommons.org/licenses/by-nc/4.0") == "D"
    assert R.licence_class("http://dcat-ap.de/def/licenses/cc-by-nc-de/3.0") == "D"
    assert R.licence_class("http://dcat-ap.de/def/licenses/other-closed") == "D"
    assert R.licence_class("http://creativecommons.org/licenses/by-sa/4.0") == "C"
    assert R.licence_class("http://dcat-ap.de/def/licenses/odbl") == "C"
    assert R.licence_class("http://spdx.org/licenses/cc-by-nc-sa-4.0") == "D"


def test_licence_unspecific_and_none():
    assert R.licence_class("http://dcat-ap.de/def/licenses/other-open") == "E"
    assert R.licence_class("http://www.ine.es/aviso_legal") == "E"
    assert R.licence_class("") == "N"
    assert R.licence_class(None) == "N"


def test_strict_vs_d1():
    v = "http://dcat-ap.de/def/licenses/cc-by-de/3.0"
    assert R.licence_class(v) == "E" and R.licence_class(v, strict=False) == "B"
    v = "creative-commons-namensnennung-4-0-international-cc-by-4-0-"
    assert R.licence_class(v) == "E" and R.licence_class(v, strict=False) == "A"


def test_czech_terms_of_use_need_context():
    v = "https://data.gov.cz/zdroj/datove-sady/1/distribuce/2/podminky-uziti"
    assert R.licence_class(v) == "E"
    assert R.licence_class(v, ["https://creativecommons.org/licenses/by/4.0/"]) == "B"
    assert R.licence_class(v, ["https://creativecommons.org/licenses/by-sa/4.0/"]) == "C"
    accented = "https://data.gov.cz/zdroj/x/podmínky-užití"
    assert R.licence_class(accented, ["https://creativecommons.org/licenses/by/4.0/"]) == "E"  # frozen rule
    assert R.licence_class(accented, ["https://creativecommons.org/licenses/by/4.0/"], strict=False) == "B"


def test_dataset_verdict():
    assert R.dataset_licence_verdict(["A", "B"]) == "pass"
    assert R.dataset_licence_verdict(["A", "D"]) == "fail"
    assert R.dataset_licence_verdict(["N", "N"]) == "none"
    assert R.dataset_licence_verdict([]) == "none"
    assert R.dataset_licence_verdict(["A", "E"]) == "unclear"
    assert R.dataset_licence_verdict(["A", "N"]) == "unclear"


def test_api_inference_and_getcapabilities():
    assert R.inferable_api("WMS", [])
    assert R.inferable_api(None, ["https://x.example/geoserver/wfs?service=WFS"])
    assert R.inferable_api(None, ["https://x.example/api/v1/data"])
    assert not R.inferable_api("CSV", ["https://x.example/data/file.csv"])
    assert R.getcapabilities_url("https://x.example/wms") == "https://x.example/wms?SERVICE=WMS&REQUEST=GetCapabilities"
    assert R.getcapabilities_url("https://x.example/ows?service=WFS&request=GetFeature&typeName=a") == \
        "https://x.example/ows?service=WFS&typeName=a&REQUEST=GetCapabilities"
    assert R.getcapabilities_url("https://x/wms?SERVICE=WMS&REQUEST=GetCapabilities").endswith("GetCapabilities")


def test_catch_all_other_closed():
    v = "http://dcat-ap.de/def/licenses/other-closed"
    assert R.licence_class(v) == "D"  # frozen rule
    assert R.licence_class(v, strict=False) == "D"  # D1 does not change it
    assert R.licence_class(v, strict=False, catch_all_as_e=True) == "E"
    assert R.licence_class("http://creativecommons.org/licenses/by-nc/4.0", catch_all_as_e=True) == "D"
