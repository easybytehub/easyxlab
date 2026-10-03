"""Unit tests for the S16 parsers (stdlib unittest; run: python3 -m unittest discover -s tests)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import nlcomments as N  # noqa: E402
import optout_check as O  # noqa: E402
import robots9309 as R  # noqa: E402


def res(status=200, body=b"", ct="application/json", error=None):
    return {"status": status, "body": body, "headers": {"content-type": ct}, "error": error, "final_url": "x"}


class Robots(unittest.TestCase):
    def test_rfc9309_selftest_cases(self):
        g = R.parse("User-agent: *\nDisallow: /\nAllow: /$\n")
        self.assertTrue(R.allowed(g, "x", "/"))
        g = R.parse("User-agent: GPTBot\nUser-agent: ClaudeBot\n\n# AI\n\nDisallow: /\n")
        self.assertTrue(R.blocks_root(g, "GPTBot") and not R.blocks_root(g, O.UNNAMED))

    def test_unnamed_crawler_falls_to_star(self):
        g = R.parse("User-agent: Googlebot\nAllow: /\n\nUser-agent: *\nDisallow: /\n")
        self.assertTrue(R.blocks_root(g, O.UNNAMED))
        self.assertFalse(R.blocks_root(g, "Googlebot"))

    def test_extras_grouping(self):
        body = ("User-Agent: *\nContent-signal: search=yes, ai-train=no\nAllow: /\n\n"
                "User-agent: ExampleBot\nContent-Usage: train-ai=y\n\n"
                "User-Agent: *\nContent-Usage: train-ai=n\nContent-Usage: /ai-ok/ train-ai=y\n")
        ex = O.parse_extras(body)
        self.assertEqual(ex["groups"][0]["content_signal"], ["search=yes, ai-train=no"])
        self.assertEqual(O.usage_for_root(ex, O.UNNAMED), "n")
        self.assertEqual(O.usage_for_root(ex, "ExampleBot"), "y")

    def test_signal_and_usage_values(self):
        self.assertEqual(O.parse_signal("search=yes, ai-train=no, ai-input=no")["ai-train"], "no")
        self.assertEqual(O.parse_usage_rule("/ai-ok/ train-ai=y"), ("/ai-ok/", {"train-ai": "y"}))
        self.assertEqual(O.parse_usage_rule("train-ai=n, search=y"), (None, {"train-ai": "n", "search": "y"}))

    def test_usage_path_not_covering_root_is_ignored(self):
        ex = O.parse_extras("User-agent: *\nContent-Usage: /archive/ train-ai=n\n")
        self.assertIsNone(O.usage_for_root(ex, O.UNNAMED))


class TDMRep(unittest.TestCase):
    def test_file_root(self):
        d = O.parse_tdmrep(res(body=b'[{"location": "/", "tdm-reservation": 1, "tdm-policy": "https://x/p.json"}]'))
        self.assertEqual((d["state"], d["root"], d["any_reservation"], d["has_policy"]), ("ok", 1, True, True))

    def test_file_partial(self):
        d = O.parse_tdmrep(res(body=b'[{"location": "/a/", "tdm-reservation": 1}, {"location": "/b/*.jpg", "tdm-reservation": 0}]'))
        self.assertEqual((d["root"], d["any_reservation"], d["any_zero"]), (None, True, True))

    def test_soft404_and_invalid(self):
        self.assertEqual(O.parse_tdmrep(res(body=b"<!doctype html><p>not found", ct="text/html"))["state"], "soft404")
        self.assertEqual(O.parse_tdmrep(res(body=b"<html>", ct="application/json"))["state"], "soft404")
        self.assertEqual(O.parse_tdmrep(res(body=b"{oops"))["state"], "invalid")
        self.assertEqual(O.parse_tdmrep(res(status=404, body=b"nope"))["state"], "absent")

    def test_meta(self):
        html = ('<html><head><meta charset="utf-8"><meta content="1" name="tdm-reservation">'
                '<meta name="robots" content="index, follow, noai, noimageai"></head><body>'
                '<meta name="tdm-reservation" content="0"></body></html>')
        m = O.head_meta(html)
        self.assertIn(("tdm-reservation", "1"), m)
        self.assertNotIn(("tdm-reservation", "0"), m)          # after <body>: ignored
        self.assertTrue(O.noai_in("index, noai"))
        self.assertFalse(O.noai_in("index, follow, max-image-preview:large"))
        self.assertEqual(O.tdm_value(" 1 "), 1)
        self.assertIsNone(O.tdm_value("yes please"))


class Comments(unittest.TestCase):
    def test_blocks(self):
        b = N.comment_blocks("# line one\n# line two\n\nUser-agent: *  # trailing\n# other\n")
        self.assertEqual(b, ["line one line two", "trailing", "other"])

    def test_prohibition_positive(self):
        for t in ["The use of programs or robots to access this site is prohibited without our consent.",
                  "Automated retrieval of content is not permitted.",
                  "Die automatisierte Erfassung unserer Inhalte ist untersagt.",
                  "L'utilisation de robots est interdite sans autorisation préalable.",
                  "Scraping is strictly prohibited."]:
            self.assertTrue(N.prohibition(t), t)

    def test_prohibition_negative(self):
        for t in ["robots.txt for www.example.org", "Block AI crawlers", "Sitemaps", "Last updated 2025-01-01",
                  "Disallow internal search pages"]:
            self.assertFalse(N.prohibition(t), t)

    def test_reservation(self):
        self.assertTrue(N.reservation("The publisher expressly reserves the right to use its content for text and data mining (§ 44b UrhG)."))
        self.assertTrue(N.reservation("We reserve all rights under Article 4 of the Copyright Directive (EU) 2019/790."))
        self.assertTrue(N.reservation("Any use of our content to train AI models is prohibited."))
        self.assertFalse(N.reservation("AI crawlers"))
        self.assertFalse(N.reservation("Block AI bots below"))
        self.assertFalse(N.reservation("ANY RESTRICTIONS EXPRESSED VIA CONTENT SIGNALS ARE EXPRESS RESERVATIONS OF "
                                       "RIGHTS UNDER ARTICLE 4 OF THE EUROPEAN UNION DIRECTIVE 2019/790"))


class CommentsV3(unittest.TestCase):
    def test_inline_rule_comment_is_not_general(self):
        d = N.scan("User-agent: Yandex\nDisallow: / # prohibits crawling for the entire site\n", 3)
        self.assertFalse(d["nl_prohibition"])

    def test_label_and_single_robot(self):
        self.assertFalse(N.prohibition("Not allowed bots", 3))
        self.assertFalse(N.prohibition("Pagination interdite a ce seul robot ; articles restent accessibles.", 3))

    def test_purpose_specific_is_reservation_not_prohibition(self):
        t = "Scraping is not allowed for training AI language models, or selling to AI companies"
        self.assertFalse(N.prohibition(t, 3))
        self.assertTrue(N.reservation(t, 3))
        t = ("The use of any automated system or software to extract data from this website, particularly for "
             "the training of any software including machine learning, is expressly prohibited.")
        self.assertTrue(N.prohibition(t, 3))          # general, with a 'particularly' marker

    def test_domain_is_not_ai(self):
        self.assertFalse(N.reservation("ExaSearchBot (exa.ai) : pagination interdite", 3))

    def test_list_style_notice_across_blocks(self):
        body = ("# Conformement aux CGU il est interdit :\n\n# - d'utiliser tout systeme logiciel automatise, robots "
                "ou programme visant a extraire des donnees\n# - d'extraire des oeuvres aux fins de fouille de textes\n")
        d = N.scan(body, 3)
        self.assertTrue(d["nl_prohibition"] and d["nl_reservation"])

    def test_general_prohibition_with_domain(self):
        self.assertTrue(N.prohibition("The use of robots or other automated means to access taz.de or collect data "
                                      "without the express permission of taz.de is strictly prohibited.", 3))


class CommentsV4(unittest.TestCase):
    MH = ("All content of this website is not to be used for the purposes of text and data mining, extraction, "
          "scraping and/or the use of programs or robots for automatic data collection and/or extraction of digital "
          "data, whether for machine learning or artificial intelligence purposes or otherwise.")

    def test_open_clause_makes_purpose_ban_general(self):
        self.assertFalse(N.prohibition(self.MH, 3))
        self.assertTrue(N.prohibition(self.MH, 4))
        t = ("Prohibited uses include but are not limited to: (1) text and data mining activities; "
             "(2) the development of any AI; and/or (4) any commercial purposes.")
        self.assertTrue(N.prohibition(t, 4))

    def test_purpose_only_ban_stays_reservation(self):
        t = "Scraping is not allowed for training AI language models, or selling to AI companies"
        self.assertFalse(N.prohibition(t, 4))
        self.assertTrue(N.reservation(t, 4))
        t = "The automated collection of content for the purpose of training, fine-tuning, or otherwise developing AI is strictly prohibited."
        self.assertFalse(N.prohibition(t, 4))

    def test_heading_is_not_reservation(self):
        h = "Google AI Models (Opt-out, does not affect Googlebot)"
        self.assertTrue(N.reservation(h, 3))
        self.assertFalse(N.reservation(h, 4))


class Verdict(unittest.TestCase):
    def rec(self, **kw):
        r = {"robots": dict(state="ok", unnamed_blocked_root=False, ai_blocked_root=[], content_signal_ai_train=[],
                            content_usage_unnamed_root=None, nl_reservation=False, nl_prohibition=False),
             "tdmrep_file": dict(state="absent"), "home": {}, "read": {"reason": ""}}
        for k, v in kw.items():
            r[k].update(v)
        return r

    def test_classes(self):
        self.assertEqual(O.verdict(self.rec())["class_"], "none_stated")
        self.assertEqual(O.verdict(self.rec(robots={"nl_reservation": True}))["class_"], "comment_only")
        self.assertEqual(O.verdict(self.rec(robots={"ai_blocked_root": ["GPTBot"], "nl_reservation": True}))["class_"],
                         "named_bots_only")
        for kw in [dict(robots={"unnamed_blocked_root": True}), dict(robots={"content_signal_ai_train": ["no"]}),
                   dict(robots={"content_usage_unnamed_root": "n"}), dict(home={"meta_tdm_reservation": "1"}),
                   dict(home={"hdr_tdm_reservation": "1"}), dict(tdmrep_file={"state": "ok", "any_reservation": True}),
                   dict(home={"hdr_content_usage": "train-ai=n"})]:
            self.assertEqual(O.verdict(self.rec(**kw))["class_"], "agnostic_reservation", kw)

    def test_contradiction(self):
        v = O.verdict(self.rec(robots={"content_signal_ai_train": ["yes"]}, home={"meta_tdm_reservation": "1"}))
        self.assertTrue(v["contradiction"])
        self.assertEqual(v["class_"], "agnostic_reservation")
        v = O.verdict(self.rec(robots={"content_signal_ai_train": ["no"]}, home={"meta_tdm_reservation": "1"}))
        self.assertFalse(v["contradiction"])
        # robots access rules are not use preferences: no contradiction with ai-train=yes
        v = O.verdict(self.rec(robots={"content_signal_ai_train": ["yes"], "ai_blocked_root": ["GPTBot"]}))
        self.assertFalse(v["contradiction"])
        self.assertEqual(v["class_"], "named_bots_only")

    def test_unreachable(self):
        self.assertEqual(O.verdict(self.rec(robots={"state": "unreachable"}))["class_"], "robots_unreachable")


if __name__ == "__main__":
    unittest.main()
