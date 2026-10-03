"""Minimal tests for netex-lint rules. Run: python -m unittest discover -s tests"""
import os, sys, tempfile, unittest, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netex_lint.cli import lint

HEAD = '<?xml version="1.0" encoding="{enc}"?>\n<PublicationDelivery xmlns="http://www.netex.org.uk/netex" version="{ver}">\n<PublicationTimestamp>2026-10-01T00:00:00</PublicationTimestamp><ParticipantRef>T</ParticipantRef><dataObjects>\n'
TAIL = '</dataObjects></PublicationDelivery>\n'


def doc(body, enc="UTF-8", ver="1.15:NO-NeTEx-networktimetable:1.5"):
    return (HEAD.format(enc=enc, ver=ver) + body + TAIL)


def frame(members, valid_to="2027-01-01", fid="TST:CompositeFrame:1"):
    return (f'<CompositeFrame id="{fid}" version="1"><validityConditions><ValidBetween>'
            f'<FromDate>2026-01-01T00:00:00</FromDate><ToDate>{valid_to}T00:00:00</ToDate></ValidBetween>'
            f'</validityConditions><frames><ServiceFrame id="{fid.replace('CompositeFrame', 'ServiceFrame')}" version="1"><lines>{members}</lines>'
            f'</ServiceFrame></frames></CompositeFrame>')


class T(unittest.TestCase):
    def run_lint(self, files, profile="auto", encoding="utf-8"):
        d = tempfile.mkdtemp()
        if isinstance(files, str):
            p = os.path.join(d, "a.xml"); open(p, "wb").write(files.encode(encoding))
        else:
            p = os.path.join(d, "a.zip")
            with zipfile.ZipFile(p, "w") as z:
                for n, c in files.items():
                    z.writestr(n, c)
        r = lint(p, "2026-10-02", profile)
        return {f["rule"]: f["count"] for f in r["findings"]}, r["summary"]

    def test_versioned_ref_missing_is_error(self):
        f, _ = self.run_lint(doc(frame('<Line id="TST:Line:1" version="1"><OperatorRef ref="TST:Operator:9" version="1"/></Line>')))
        self.assertEqual(f.get("REF-UNRESOLVED-VERSIONED"), 1)

    def test_unversioned_external_ref_is_fine(self):
        f, s = self.run_lint(doc(frame('<Line id="TST:Line:1" version="1"><OperatorRef ref="XXX:Operator:9"/></Line>')))
        self.assertNotIn("REF-UNRESOLVED-VERSIONED", f)
        self.assertEqual(s["refs_unresolved"], 1)

    def test_version_mismatch(self):
        f, _ = self.run_lint(doc(frame('<Line id="TST:Line:1" version="1"><Presentation/></Line>'
                                       '<Line id="TST:Line:2" version="1"><LineRef ref="TST:Line:1" version="7"/></Line>')))
        self.assertEqual(f.get("REF-VERSION-MISMATCH"), 1)

    def test_expired_validity(self):
        f, s = self.run_lint(doc(frame('<Line id="TST:Line:1" version="1"/>', valid_to="2026-06-30")))
        self.assertIn("VALIDITY-EXPIRED", f)
        self.assertEqual(s["validity_to_max"], "2026-06-30")

    def test_mojibake_and_non_utf8(self):
        f, _ = self.run_lint(doc(frame('<Line id="TST:Line:1" version="1"><Name>GÃ¤vle</Name></Line>')))
        self.assertEqual(f.get("ENCODING-MOJIBAKE"), 1)
        f, _ = self.run_lint(doc(frame('<Line id="TST:Line:1" version="1"><Name>Gävle</Name></Line>'), enc="ISO-8859-1"),
                             encoding="latin-1")
        self.assertIn("ENCODING-NOT-UTF8", f)
        self.assertNotIn("ENCODING-MOJIBAKE", f)

    def test_duplicate_across_files(self):
        a = doc(frame('<Line id="TST:Line:1" version="1"/>'))
        b = doc(frame('<Line id="TST:Line:1" version="1"/>', fid="TST:CompositeFrame:2"))
        f, _ = self.run_lint({"a.xml": a, "b.xml": b})
        self.assertEqual(f.get("ID-REDUNDANT-ACROSS-FILES"), 1)

    def test_nordic_same_file_ref_must_be_versioned(self):
        f, _ = self.run_lint(doc(frame('<Line id="TST:Line:1" version="1"/>'
                                       '<Line id="TST:Line:2" version="1"><LineRef ref="TST:Line:1"/></Line>')))
        self.assertEqual(f.get("NORDIC-REF-UNVERSIONED-INTERNAL"), 1)

    def test_nordic_id_format_and_type(self):
        f, _ = self.run_lint(doc(frame('<Line id="TST:Line:a.b" version="1"/><Line id="TST:Route:2" version="1"/>')))
        self.assertGreaterEqual(f.get("NORDIC-ID-FORMAT", 0), 1)
        self.assertEqual(f.get("NORDIC-ID-TYPE"), 1)

    def test_french_rules(self):
        body = frame('<Line id="X:Line:1:LOC" version="1"/><Line id="X:Line:2" version="1">'
                     '<LineRef ref="X:Line:1:LOC"/></Line>', fid="X:CompositeFrame:1:LOC")
        f, s = self.run_lint(doc(body, ver="1.09:FR-NETEX-2.1-1.0"))
        self.assertEqual(s["profile"], "fr")
        self.assertEqual(f.get("FR-REF-UNVERSIONED-INTERNAL"), 1)
        self.assertGreaterEqual(f.get("FR-ID-NOT-PROPOSED-FORMAT", 0), 1)   # X:Line:2 lacks the 4th part

    def test_open_ended_validity_is_not_expired(self):
        body = ('<Line id="TST:Line:1" version="1"><validityConditions><ValidBetween><FromDate>2018-01-01T00:00:00'
                '</FromDate><ToDate>2018-01-31T00:00:00</ToDate></ValidBetween></validityConditions></Line>'
                '<Line id="TST:Line:2" version="1"><validityConditions><ValidBetween><FromDate>2018-01-01T00:00:00'
                '</FromDate></ValidBetween></validityConditions></Line>')
        d = doc('<CompositeFrame id="TST:CompositeFrame:1" version="1"><frames><ServiceFrame id="TST:ServiceFrame:1" '
                'version="1"><lines>' + body + '</lines></ServiceFrame></frames></CompositeFrame>')
        f, s = self.run_lint(d)
        self.assertNotIn("VALIDITY-EXPIRED", f)
        self.assertEqual(s["validity_open_ended"], 1)

    def test_closed_frame_validity_expires_despite_open_objects(self):
        body = ('<Line id="TST:Line:2" version="1"><validityConditions><ValidBetween><FromDate>2018-01-01T00:00:00'
                '</FromDate></ValidBetween></validityConditions></Line>')
        f, s = self.run_lint(doc(frame(body, valid_to="2018-12-08")))
        self.assertIn("VALIDITY-EXPIRED", f)
        self.assertEqual(s["frame_validity_to_max"], "2018-12-08")

    def test_no_xml_declaration_is_not_non_utf8(self):
        d = doc(frame('<Line id="TST:Line:1" version="1"/>')).split("\n", 1)[1]   # drop <?xml ...?>
        f, s = self.run_lint(d)
        self.assertNotIn("ENCODING-NOT-UTF8", f)
        self.assertEqual(f.get("ENCODING-NO-DECLARATION"), 1)

    def test_version_any_unresolved_is_not_flagged(self):
        f, s = self.run_lint(doc(frame('<Line id="TST:Line:1" version="1"><OperatorRef ref="TST:Operator:9" version="any"/></Line>')))
        self.assertNotIn("REF-UNRESOLVED-VERSIONED", f)
        self.assertEqual(s["refs_unresolved"], 1)

    def test_typeof_ref_excluded_but_counted(self):
        f, s = self.run_lint(doc(frame('<Line id="TST:Line:1" version="1"><TypeOfServiceRef ref="X:TypeOfService:a" version="9.3.0"/></Line>')))
        self.assertNotIn("REF-UNRESOLVED-VERSIONED", f)
        self.assertEqual(s["refs_unresolved_typeof_versioned"], 1)

    def test_french_stop_codification_accepted(self):
        body = frame('<Line id="X:Line:1:LOC" version="1"/><StopPlace id="FR:78297:LMO:12345:LOC" version="1"/>',
                     fid="X:CompositeFrame:1:LOC")
        f, s = self.run_lint(doc(body.replace("TST:ServiceFrame:1", "X:ServiceFrame:1:LOC").replace(
            "X:ServiceFrame:1", "X:ServiceFrame:1:LOC") , ver="1.09:FR-NETEX-2.1-1.0"))
        self.assertEqual(s["profile"], "fr")
        self.assertNotIn("FR-ID-TYPE-NOT-TAG", f)

    def test_replacement_char_is_separate_from_mojibake(self):
        f, _ = self.run_lint(doc(frame('<Line id="TST:Line:1" version="1"><Name>Port Z\ufffdlande</Name></Line>')))
        self.assertEqual(f.get("ENCODING-REPLACEMENT-CHAR"), 1)
        self.assertNotIn("ENCODING-MOJIBAKE", f)


if __name__ == "__main__":
    unittest.main()
