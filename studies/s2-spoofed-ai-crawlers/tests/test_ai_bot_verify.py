"""Offline tests for ai-bot-verify. Run: python3 -m unittest discover -s tests -v
All addresses are from the documentation ranges (RFC 5737 / RFC 3849)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ai_bot_verify as abv  # noqa: E402

UA = {
    "gptbot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.3; +https://openai.com/gptbot)",
    "chatgpt": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot",
    "claude": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "googlebot": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "gext": "Mozilla/5.0 (compatible; Google-Extended/1.0)",
    "bytespider": "Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)",
    "bing": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) Chrome/116.0.1938.76 Safari/537.36",
    "searchbot": "Mozilla/5.0 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)",
    "claude_search": "Mozilla/5.0 (compatible; Claude-SearchBot/1.0; +https://www.anthropic.com)",
    "human": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
}


def line(ip, path, ua, status=200, ts="02/Oct/2026:10:15:00 +0000", ray="8c1f2a3b4c5d6e7f-MAD"):
    return f'{ip} - [{ts}] "GET {path} HTTP/1.1" {status} 512 "-" "{ua}" cf_ray={ray}'


class FakeResolver(abv.Resolver):
    def __init__(self, ptr, fwd):
        super().__init__(reverse=lambda ip: ptr.get(ip, ""), forward=lambda n: fwd.get(n, set()))


def ranges_dir():
    d = Path(tempfile.mkdtemp())
    files = {
        "openai-gptbot": ["192.0.2.0/28"],
        "openai-searchbot": ["192.0.2.32/28"],
        "openai-chatgpt-user": ["192.0.2.16/28"],
        "anthropic": ["198.51.100.0/26", "2001:db8:a::/48"],
        "google-common": ["198.51.100.64/27"],
        "bing": ["198.51.100.128/27"],
    }
    for k, prefs in files.items():
        (d / f"{k}.json").write_text(json.dumps({"creationTime": "2026-10-01", "prefixes": [
            {"ipv6Prefix" if ":" in p else "ipv4Prefix": p} for p in prefs]}))
    return d


class TestMatching(unittest.TestCase):
    def test_specific_before_generic(self):
        self.assertEqual(abv.match_bot(UA["searchbot"]).name, "OAI-SearchBot")
        self.assertEqual(abv.match_bot(UA["claude_search"]).name, "Claude-SearchBot")
        self.assertEqual(abv.match_bot(UA["chatgpt"]).name, "ChatGPT-User")
        self.assertEqual(abv.match_bot(UA["gext"]).name, "Google-Extended")
        self.assertEqual(abv.match_bot(UA["googlebot"]).name, "Googlebot")
        self.assertIsNone(abv.match_bot(UA["human"]))

    def test_no_match_inside_other_word(self):
        self.assertIsNone(abv.match_bot("Mozilla/5.0 (compatible; NotGPTBotX)") and None)
        self.assertEqual(abv.match_bot("foo myccbot bar"), None)


class TestParsing(unittest.TestCase):
    def test_parse_cf_format(self):
        r = abv.parse_line(line("192.0.2.1", "/a?b=1", UA["gptbot"]))
        self.assertEqual((r.ip, r.path, r.status, r.via_cdn), ("192.0.2.1", "/a?b=1", 200, True))
        r = abv.parse_line(line("192.0.2.1", "/", UA["gptbot"], ray="-"))
        self.assertFalse(r.via_cdn)

    def test_parse_plain_combined(self):
        r = abv.parse_line('2001:db8::5 - - [02/Oct/2026:10:15:00 +0000] "GET / HTTP/2.0" 301 0 "-" "x"')
        self.assertEqual((r.ip, r.status, r.via_cdn), ("2001:db8::5", 301, None))

    def test_garbage(self):
        self.assertIsNone(abv.parse_line("not a log line"))
        self.assertIsNone(abv.parse_line('999.1.1.1 - [02/Oct/2026:10:15:00 +0000] "GET / HTTP/1.1" 200 1 "-" "x"'))


class TestPaths(unittest.TestCase):
    def test_categories(self):
        c = abv.path_category
        self.assertEqual(c("/robots.txt"), "robots.txt")
        self.assertEqual(c("/.env"), "vuln-probe")
        self.assertEqual(c("/api/.env.production"), "vuln-probe")
        self.assertEqual(c("/wp-login.php"), "vuln-probe")
        self.assertEqual(c("/.git/config"), "vuln-probe")
        self.assertEqual(c("/secrets.json"), "vuln-probe")
        self.assertEqual(c("/sitemap-index.xml"), "sitemap")
        self.assertEqual(c("/llms.txt"), "llms.txt")
        self.assertEqual(c("/_astro/x.css"), "asset")
        self.assertEqual(c("/"), "home")
        self.assertEqual(c("/fiscal/calculadora-nomina/"), "page")
        self.assertEqual(c("/terraform.tfstate"), "vuln-probe")
        self.assertEqual(c("/@fs/proc/self/environ"), "vuln-probe")

    def test_normalise_removes_ids_and_ips(self):
        self.assertEqual(abv.normalise_path("/x/123456/y?q=1"), "/x/{n}/y")
        self.assertEqual(abv.normalise_path("/proxy/192.0.2.7/a"), "/proxy/{ip}/a")


class TestVerdicts(unittest.TestCase):
    def setUp(self):
        self.ranges = abv.RangeStore(Path(tempfile.mkdtemp()), ranges_dir())
        self.res = FakeResolver(
            ptr={"203.0.113.5": "msnbot-203-0-113-5.search.msn.com",
                 "203.0.113.6": "msnbot-fake.search.msn.com",
                 "203.0.113.7": "host.example.net"},
            fwd={"msnbot-203-0-113-5.search.msn.com": {"203.0.113.5"},
                 "msnbot-fake.search.msn.com": {"203.0.113.99"}})

    def v(self, name, ip):
        return abv.verdict_for(abv.bot_by_name(name), ip, self.ranges, self.res)

    def test_ranges(self):
        self.assertEqual(self.v("GPTBot", "192.0.2.3"), "verified")
        self.assertEqual(self.v("GPTBot", "192.0.2.20"), "spoofed")       # ChatGPT-User range, not GPTBot
        self.assertEqual(self.v("ChatGPT-User", "192.0.2.20"), "verified")
        self.assertEqual(self.v("ClaudeBot", "2001:db8:a::1"), "verified")
        self.assertEqual(self.v("Claude-User", "198.51.100.10"), "verified")  # one list for all Anthropic bots
        self.assertEqual(self.v("ClaudeBot", "203.0.113.50"), "spoofed")

    def test_fcrdns(self):
        self.assertEqual(self.v("Bingbot", "198.51.100.130"), "verified")   # in JSON
        self.assertEqual(self.v("Bingbot", "203.0.113.5"), "verified")      # FCrDNS ok
        self.assertEqual(self.v("Bingbot", "203.0.113.6"), "spoofed")       # PTR forged, forward mismatch
        self.assertEqual(self.v("Bingbot", "203.0.113.7"), "spoofed")       # wrong domain

    def test_fcrdns_transient_is_indeterminate(self):
        res = abv.Resolver(reverse=lambda ip: None, forward=lambda n: set())
        self.assertEqual(abv.verdict_for(abv.bot_by_name("YandexBot"), "203.0.113.8", self.ranges, res),
                         "indeterminate")

    def test_never_a_ua_and_unverifiable(self):
        self.assertEqual(self.v("Google-Extended", "198.51.100.70"), "spoofed")
        self.assertEqual(self.v("Bytespider", "203.0.113.9"), "unverifiable")
        self.assertEqual(self.v("Amazonbot", "203.0.113.9"), "indeterminate")

    def test_missing_range_file_is_indeterminate_not_spoofed(self):
        empty = abv.RangeStore(Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()))
        self.assertEqual(abv.verdict_for(abv.bot_by_name("PerplexityBot"), "203.0.113.9", empty, None),
                         "indeterminate")


class TestEndToEnd(unittest.TestCase):
    def test_report_and_privacy(self):
        logs = [
            line("192.0.2.3", "/robots.txt", UA["gptbot"]),
            line("192.0.2.3", "/page/", UA["gptbot"]),
            line("203.0.113.50", "/.env", UA["claude"], status=444, ts="02/Oct/2026:03:00:00 +0000"),
            line("203.0.113.50", "/secrets.json", UA["claude"], status=404),
            line("203.0.113.51", "/", UA["chatgpt"]),
            line("198.51.100.70", "/", UA["googlebot"]),
            line("203.0.113.60", "/", UA["bytespider"]),
            line("203.0.113.61", "/", UA["human"]),
        ]
        ranges = abv.RangeStore(Path(tempfile.mkdtemp()), ranges_dir())
        agg = abv.analyse(logs, ranges, FakeResolver({}, {}))
        asn = {"203.0.113.50": {"asn": 64500, "cc": "ZZ", "as_name": "EXAMPLE-HOSTING, ZZ"},
               "203.0.113.51": {"asn": 64501, "cc": "ZZ", "as_name": "EXAMPLE TELECOM"},
               "203.0.113.60": {"asn": 64502, "cc": "ZZ", "as_name": "BYTEDANCE"}}
        rep = abv.build_report(agg, "test", asn, ranges)
        s = rep["summary"]
        self.assertEqual(s["declared_bot_requests"], 7)
        self.assertEqual(s["verdict_totals"], {"verified": 3, "spoofed": 3, "unverifiable": 1})
        claude = next(r for r in rep["by_bot"] if r["bot"] == "ClaudeBot")
        self.assertEqual((claude["verdict"], claude["unique_ips"], claude["ips_with_vuln_probe"]),
                         ("spoofed", 1, 1))
        gpt = next(r for r in rep["by_bot"] if r["bot"] == "GPTBot")
        self.assertEqual(gpt["ips_robots_first"], 1)
        asn_rows = {r["asn"]: r for r in rep["by_asn"]}
        self.assertEqual(asn_rows[64500]["net_type"], "cloud/hosting")
        self.assertEqual(asn_rows[64501]["net_type"], "isp/residential")
        # privacy: no client IP anywhere in the serialised report
        out = Path(tempfile.mkdtemp())
        abv.write_outputs(rep, out, known_ips=abv.seen_ips(agg))
        blob = "".join(p.read_text() for p in out.iterdir())
        for ip in ("192.0.2.3", "203.0.113.50", "203.0.113.51", "198.51.100.70", "203.0.113.60"):
            self.assertNotIn(ip, blob)
        # UA version numbers ("Chrome/131.0.0.0") must not trip the guard
        abv.assert_no_ips({"ua": UA["googlebot"]}, abv.seen_ips(agg))

    def test_guard_blocks_leak(self):
        with self.assertRaises(ValueError):
            abv.assert_no_ips({"x": "seen from 203.0.113.50"}, {"203.0.113.50"})


class TestNetType(unittest.TestCase):
    def test_heuristic(self):
        self.assertEqual(abv.net_type("DIGITALOCEAN-ASN, US"), "cloud/hosting")
        self.assertEqual(abv.net_type("M247, RO"), "vpn/proxy")
        self.assertEqual(abv.net_type("T-MOBILE-AS21928, US"), "mobile")
        self.assertEqual(abv.net_type("COMCAST-7922, US"), "isp/residential")
        self.assertEqual(abv.net_type("SOMETHING ODD"), "unknown")


if __name__ == "__main__":
    unittest.main()
