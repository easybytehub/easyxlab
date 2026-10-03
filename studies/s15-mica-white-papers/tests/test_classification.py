"""Tests for the classification logic of mica_wp_check and the URL/link rules of 02_collect (synthetic inputs only)."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from mica_wp_check import sniff, lei_checksum_ok, all_dtis, all_leis  # noqa: E402

collect = importlib.import_module("02_collect")

ESMA = "https://www.esma.europa.eu/taxonomy/mica/2025-03-31/mica_entry_table_2.xsd"


def ixbrl(schema=ESMA, decl=True):
    return (('<?xml version="1.0" encoding="UTF-8"?>' if decl else "") +
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" '
            'xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">'
            '<head><title>White paper</title></head><body><div style="display:none"><ix:header><ix:references>'
            f'<link:schemaRef xlink:type="simple" xlink:href="{schema}"/></ix:references></ix:header></div>'
            '<ix:nonNumeric name="mica:X" contextRef="c">x</ix:nonNumeric></body></html>').encode()


def test_ixbrl_esma():
    i = sniff(ixbrl(), "application/xhtml+xml", "wp.xhtml")
    assert i.doc_class == "ixbrl-esma" and i.esma_table == "2"
    assert i.is_xml_wellformed and i.root == "{http://www.w3.org/1999/xhtml}html"
    assert i.ix_fact_count == 1


def test_ixbrl_other_taxonomy():
    assert sniff(ixbrl("https://example.org/tax/entry.xsd")).doc_class == "ixbrl-other"


def test_ixbrl_other_esma_version_is_not_esma_2025():
    assert sniff(ixbrl("https://www.esma.europa.eu/taxonomy/mica/2024-01-01/mica_entry_table_2.xsd")).doc_class == "ixbrl-other"


def test_xhtml_without_ixbrl_by_name_and_type():
    page = b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>MiCA Whitepaper Inline XBRL</title></head><body>x</body></html>'
    assert sniff(page, "text/html", "x.xhtml").doc_class == "xhtml-no-ixbrl"
    assert sniff(page, "application/xhtml+xml", "x").doc_class == "xhtml-no-ixbrl"
    # same bytes without XML declaration, served as HTML under a non-xhtml name: an HTML page
    page2 = page.replace(b'<?xml version="1.0"?>', b"")
    assert sniff(page2, "text/html", "x.html").doc_class == "html"


def test_ix_namespace_without_schemaref_is_not_ixbrl():
    page = b'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>x</body></html>'
    assert sniff(page, "text/html", "a.html").doc_class == "html"


def test_pdf_zip_empty_other():
    assert sniff(b"%PDF-1.7\n...").doc_class == "pdf"
    assert sniff(b"   ").doc_class == "empty"
    assert sniff(b"PK\x03\x04garbage").doc_class == "other"
    assert sniff(b'<?xml version="1.0"?><Error><Code>NoSuchKey</Code></Error>').doc_class == "other"


def test_antibot():
    page = b"<html><head><title>x</title></head><body><script src='/_Incapsula_Resource?SWJIYLWA=1'></script></body></html>"
    i = sniff(page, "text/html", "a")
    assert i.antibot and i.doc_class == "html"


def test_lei_checksum():
    assert lei_checksum_ok("506700GE1G29325QX363")  # GLEIF's own LEI
    assert not lei_checksum_ok("506700GE1G29325QX364")
    assert not lei_checksum_ok("506700GE1G29325QX36")


def test_identifier_extraction():
    v = {"lei_facts": {"OfferorsLegalEntityIdentifier": ["506700GE1G29325QX363", ""]},
         "context_identifiers": [["http://standards.iso.org/iso/17442", "506700GE1G29325QX363"], ["other", "X"]],
         "dti_facts": {"OtherTokenDigitalTokenIdentifierCode": ["NKK8ZTL3N|ABCDFGHJK"]}}
    assert all_leis(v) == {"506700GE1G29325QX363"}
    assert all_dtis(v) == {"NKK8ZTL3N", "ABCDFGHJK"}


def test_split_urls():
    s = collect.split_urls
    assert s("WWW.EXAMPLE.IO") == ["https://WWW.EXAMPLE.IO"]
    assert s("https://a.org/x.xhtml; accessible via: https://a.org/doc") == ["https://a.org/x.xhtml", "https://a.org/doc"]
    assert s("https://a.org/1\nhttps://b.org/2") == ["https://a.org/1", "https://b.org/2"]
    assert s("EMT_NO_WP") == [] and s("") == [] and s("n/a") == []


def test_candidate_links_and_rank():
    page = (b'<html><body><a href="/en/other">Other</a><a href="docs/WP-ABCDFGHJK.xhtml">XHTML</a>'
            b'<a href="https://cdn.x.org/wp.pdf">PDF</a><a href="/files/one.xhtml">XHTML 2</a>'
            b'<a href="mailto:x@y.z">m</a><iframe src="/viewer?file=report-xbrl"></iframe></body></html>')
    c = collect.candidate_links(page, "https://x.org/en/page")
    urls = [u for u, _ in c]
    assert "https://x.org/en/docs/WP-ABCDFGHJK.xhtml" in urls and "https://cdn.x.org/wp.pdf" in urls
    assert "https://x.org/en/other" not in urls and not any(u.startswith("mailto") for u in urls)
    r = collect.rank(c, {"ABCDFGHJK"})
    assert r[0][0].endswith("WP-ABCDFGHJK.xhtml")
    assert sum(1 for u, a in r if collect.kind_of(u, a) == "pdf") <= 1
    assert len([1 for u, a in r if collect.kind_of(u, a) == "xhtml"]) <= 3


# ---- regression tests for the review blockers (B1-B4) ----
import fetch  # noqa: E402
import robots9309  # noqa: E402
from mica_wp_check import instant_redirect  # noqa: E402


def test_b1_dates_and_header_rows():
    import datetime as dt
    assert collect.parse_date("17.08.2026") == dt.date(2026, 8, 17)
    assert collect.parse_date("23/12/2025") == dt.date(2025, 12, 23)
    assert collect.parse_date("23-12-2025") == dt.date(2025, 12, 23)
    assert collect.parse_date("") is None and collect.parse_date("wp_lastupdate") is None
    assert collect.is_header_row({"ae_homeMemberState": "ae_homeMemberState", "wp_lastupdate": "wp_lastupdate"})
    assert not collect.is_header_row({"ae_homeMemberState": "LV", "wp_lastupdate": "09.07.2026"})


def test_b2_inline_xbrl_1_0_is_its_own_class():
    d = ixbrl().replace(b"http://www.xbrl.org/2013/inlineXBRL", b"http://www.xbrl.org/2008/inlineXBRL")
    i = sniff(d, "application/xhtml+xml", "wp.xhtml")
    assert i.ix_version == "1.0" and i.doc_class == "ixbrl-1.0"
    assert sniff(ixbrl()).ix_version == "1.1"


def test_b3_robots_parsed_by_syntax_and_rfc9309_wildcards():
    info = fetch.RobotsInfo(host="export.example.org", status="ok")
    info.groups = robots9309.parse("User-agent: *\nDisallow: /\n")  # served as text/html: still rules
    assert not info.allows("https://export.example.org/api/query?x=1")
    info.groups = robots9309.parse("User-agent: *\nDisallow: /*/*/commits/\n")
    assert not info.allows("https://github.com/org/repo/commits/main/wp.pdf")
    assert info.allows("https://github.com/org/repo/blob/main/wp.pdf")
    info.groups = robots9309.parse("<!doctype html><html><body>Home</body></html>")
    assert info.allows("https://x.org/anything")
    assert fetch.crawl_delay("User-agent: *\nCrawl-delay: 15\n", fetch.UA_TOKEN) == 15.0


def test_b4_instant_client_redirects():
    page = b'<html><head><title>Redirecting&hellip;</title><meta http-equiv="refresh" content="0; url=../x/index.html"></head></html>'
    assert instant_redirect(page) == "../x/index.html"
    assert instant_redirect(b'<meta content="1;URL=\'/y\'" http-equiv="refresh">') == "/y"
    assert instant_redirect(b'<meta http-equiv="refresh" content="10; url=/later">') is None
    assert instant_redirect(b"<html><body><script>location.replace('/en/')</script></body></html>") == "/en/"
    long_page = b"<html><body>" + b"<p>text</p>" * 200 + b"<script>window.location.href='/x'</script></body></html>"
    assert instant_redirect(long_page) is None
