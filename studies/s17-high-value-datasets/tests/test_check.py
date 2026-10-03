# SPDX-License-Identifier: Apache-2.0
import json
import os
import subprocess
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hvd_check  # noqa: E402

PFX = """@prefix dcat: <http://www.w3.org/ns/dcat#> . @prefix dct: <http://purl.org/dc/terms/> .
@prefix dcatap: <http://data.europa.eu/r5r/> . @prefix ex: <http://example.org/> .
"""
GOOD = PFX + """ex:d a dcat:Dataset ; dcatap:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj> ;
  dcatap:hvdCategory <http://data.europa.eu/bna/c_ac64a52d> ; dcat:distribution ex:x .
ex:x a dcat:Distribution ; dct:license <http://publications.europa.eu/resource/authority/licence/CC_BY_4_0> ;
  dcatap:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj> ; dcat:accessService ex:s .
ex:s a dcat:DataService ; dcat:servesDataset ex:d .
"""
BAD = PFX + """ex:d a dcat:Dataset ; dcatap:applicableLegislation <https://eur-lex.europa.eu/eli/reg_impl/2023/138/oj> ;
  dcat:distribution ex:x . ex:x a dcat:Distribution ; dct:license <http://creativecommons.org/licenses/by-nc/4.0/> ;
  dcat:downloadURL <http://example.org/file.csv> .
"""
NONE = PFX + """ex:d a dcat:Dataset ; dcatap:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj> ;
  dcatap:hvdCategory <http://data.europa.eu/bna/c_ac64a52d> ; dcat:distribution ex:x .
ex:x a dcat:Distribution ; dcat:accessURL <http://example.org/geoserver/wms> .
"""


def run(tmp_path, ttl):
    p = tmp_path / "r.ttl"
    p.write_text(ttl)
    g = hvd_check.load(str(p))
    return hvd_check.check_dataset(g, next(iter(g.subjects(hvd_check.RDF.type, hvd_check.DCAT.Dataset))))


def by_art(v):
    return {c["article"]: c["result"] for c in v["checks"]}


def test_good_record_passes(tmp_path):
    v = run(tmp_path, GOOD)
    assert v["verdict"] == "pass" and by_art(v) == {"3(5)": "pass", "4(3)": "pass", "3(1)": "pass"}
    assert v["info"]["distributions_with_eli"] == 1


def test_bad_record_fails_each_article(tmp_path):
    v = run(tmp_path, BAD)
    assert by_art(v) == {"3(5)": "fail", "4(3)": "fail", "3(1)": "fail"}
    assert "malformed" in v["checks"][0]["detail"] and "hvdCategory" in v["checks"][0]["detail"]


def test_no_licence_and_inferable_api(tmp_path):
    v = run(tmp_path, NONE)
    assert by_art(v) == {"3(5)": "pass", "4(3)": "fail", "3(1)": "warn"}


def test_cli_exit_codes(tmp_path):
    for ttl, code in ((GOOD, 0), (BAD, 1)):
        p = tmp_path / "c.ttl"
        p.write_text(ttl)
        r = subprocess.run([sys.executable, os.path.join(HERE, "..", "scripts", "hvd_check.py"), str(p)],
                           capture_output=True, text=True)
        assert r.returncode == code, r.stderr
        assert json.loads(r.stdout)["dataset"] == "http://example.org/d"


def test_catch_all_other_closed_warns_unless_strict(tmp_path):
    ttl = GOOD.replace("http://publications.europa.eu/resource/authority/licence/CC_BY_4_0",
                       "http://dcat-ap.de/def/licenses/other-closed")
    p = tmp_path / "oc.ttl"
    p.write_text(ttl)
    g = hvd_check.load(str(p))
    ds = next(iter(g.subjects(hvd_check.RDF.type, hvd_check.DCAT.Dataset)))
    assert by_art(hvd_check.check_dataset(g, ds))["4(3)"] == "warn"
    assert by_art(hvd_check.check_dataset(g, ds, strict=True))["4(3)"] == "fail"
