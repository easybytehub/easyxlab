"""Offline tests for EasyxLab S9. Run: python3 -m unittest discover -s tests -v
Addresses are from the documentation ranges (RFC 5737 / RFC 3849); domains are .example."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import s9_common as c  # noqa: E402
import s9_stats as st  # noqa: E402
import s9_collect as col  # noqa: E402
import s9_analyse as an  # noqa: E402

abv = c.abv
UTC = timezone.utc
T_R = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
T_L = datetime(2026, 10, 8, 10, 0, tzinfo=UTC)
P = "/qz7kxm/"                         # random folder; arm segments are random too (no meaning in the path)
ALW, DIS, ROB = P + "a4hn2w/", P + "t9pe3r/", P + "m6cv8d/"
SITE_CFG = {"domain": "site-b.example", "log": {"files": []},
            "arms": {"allowed": ALW, "disallowed": DIS, "robots-only": ROB},
            "t_robots": "2026-10-05T10:00:00Z", "t_link": "2026-10-08T10:00:00Z", "t_end": None}
UA = {
    "gptbot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.3; +https://openai.com/gptbot)",
    "chatgpt": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot",
    "claudeuser": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +Claude-User@anthropic.com)",
    "adsbot": "AdsBot-Google (+http://www.google.com/adsbot.html)",
    "bing": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) Chrome/116.0.1938.76 Safari/537.36",
    "duckassist": "DuckAssistBot/1.2; (+http://duckduckgo.com/duckassistbot.html)",
    "amazon": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot) Chrome/119.0.6045.214 Safari/537.36",
    "human": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "curl": "curl/8.7.1",
    "newbot": "Mozilla/5.0 (compatible; ShinyNewCrawler/0.3; +https://crawler.example/about)",
}


def site():
    return c.site_from_dict("site-b", SITE_CFG)


def bot(key):
    return abv.match_bot(UA[key])


class TestArm(unittest.TestCase):
    def test_exact_paths(self):
        s = site()
        self.assertEqual(c.trap_arm(s, ALW), "allowed")
        self.assertEqual(c.trap_arm(s, DIS + "?utm=x"), "disallowed")
        self.assertEqual(c.trap_arm(s, ROB), "robots-only")
        self.assertEqual(c.trap_arm(s, "https://site-b.example" + DIS), "disallowed")

    def test_not_covered_by_disallow_is_never_a_violation_arm(self):
        s = site()
        # robots.txt matching is a prefix match on "/folder/segment/": without the slash it is NOT covered
        self.assertEqual(c.trap_arm(s, DIS.rstrip("/")), "other-under-prefix")
        self.assertEqual(c.trap_arm(s, P), "other-under-prefix")
        self.assertEqual(c.trap_arm(s, P.rstrip("/")), "other-under-prefix")
        self.assertIsNone(c.trap_arm(s, DIS.upper()))   # case-sensitive, like robots.txt
        self.assertIsNone(c.trap_arm(s, "/mm-to-inches/"))

    def test_s2_does_not_call_trap_paths_probes(self):
        for p in (ALW, DIS, ROB):
            self.assertEqual(abv.path_category(p), "page")

    def test_prefix_inferred(self):
        self.assertEqual(site().prefix, P)
        self.assertEqual(site().footer_hrefs, [ALW, DIS])


class TestPhase(unittest.TestCase):
    def test_disallowed_phases(self):
        s = site()
        self.assertEqual(c.trap_phase(s, "disallowed", T_R - timedelta(minutes=1), "OpenAI"), "pre")
        self.assertEqual(c.trap_phase(s, "disallowed", T_R + timedelta(hours=23), "OpenAI"), "grace")
        self.assertEqual(c.trap_phase(s, "disallowed", T_R + timedelta(hours=24), "OpenAI"), "active")

    def test_operator_specific_grace(self):
        s = site()
        self.assertEqual(c.trap_phase(s, "robots-only", T_R + timedelta(hours=48), "DuckDuckGo"), "grace")
        self.assertEqual(c.trap_phase(s, "robots-only", T_R + timedelta(hours=72), "DuckDuckGo"), "active")
        self.assertEqual(c.trap_phase(s, "robots-only", T_R + timedelta(days=20), "Amazon"), "grace")
        self.assertEqual(c.trap_phase(s, "robots-only", T_R + timedelta(days=30), "Amazon"), "active")
        self.assertEqual(c.trap_phase(s, "robots-only", T_R + timedelta(hours=30), "OpenAI", 72), "grace")

    def test_control_and_end(self):
        s = site()
        self.assertEqual(c.trap_phase(s, "allowed", T_L - timedelta(seconds=1)), "pre")
        self.assertEqual(c.trap_phase(s, "allowed", T_L), "active")
        s.t_end = T_L + timedelta(days=80)
        self.assertEqual(c.trap_phase(s, "disallowed", T_L + timedelta(days=81), "OpenAI"), "post")


class TestLabel(unittest.TestCase):
    def lab(self, arm, phase, key, verdict="verified", ua=None):
        b = bot(key) if key else None
        return c.trap_label(arm, phase, b, verdict if b else None, ua or (UA[key] if key else ""))

    def test_violation_only_for_verified_crawlers_that_say_they_obey(self):
        self.assertEqual(self.lab("disallowed", "active", "gptbot"), "violation")
        self.assertEqual(self.lab("robots-only", "active", "duckassist"), "violation")
        # Anthropic says Claude-User is controlled by robots.txt: a verified fetch is a violation
        self.assertEqual(self.lab("disallowed", "active", "claudeuser"), "violation")

    def test_declared_exemptions(self):
        self.assertEqual(self.lab("disallowed", "active", "chatgpt"), "permitted-user-fetch")
        self.assertEqual(self.lab("disallowed", "active", "adsbot"), "permitted-ignores-wildcard")
        self.assertEqual(self.lab("disallowed", "active", "bing"), "fetch-no-stated-policy")

    def test_unverified_and_undeclared(self):
        self.assertEqual(self.lab("disallowed", "active", "gptbot", "spoofed"), "unverified-claim")
        self.assertEqual(self.lab("disallowed", "active", "amazon", "indeterminate"), "unverified-claim")
        self.assertEqual(self.lab("disallowed", "active", None, ua=UA["curl"]), "undeclared:http-library")
        self.assertEqual(self.lab("disallowed", "active", None, ua=UA["human"]), "undeclared:browser-like")
        self.assertEqual(self.lab("disallowed", "active", None, ua="-"), "undeclared:empty")

    def test_phases_and_control(self):
        self.assertEqual(self.lab("disallowed", "grace", "gptbot"), "in-grace")
        self.assertEqual(self.lab("disallowed", "pre", "gptbot"), "pre")
        self.assertEqual(self.lab("allowed", "active", "gptbot"), "control")
        self.assertEqual(self.lab("other-under-prefix", "n/a", "gptbot"), "other-under-prefix")
        self.assertIsNone(c.trap_label(None, "n/a", None, None))

    def test_every_registry_bot_has_a_claim(self):
        for b in abv.BOTS:
            self.assertIn(b.name, c.CLAIMS, b.name)


class TestTokensAndClasses(unittest.TestCase):
    def test_unregistered_tokens(self):
        self.assertEqual(c.unregistered_tokens(UA["newbot"]), {"shinynewcrawler"})
        self.assertEqual(c.unregistered_tokens(UA["gptbot"]), set())
        self.assertEqual(c.unregistered_tokens(UA["human"]), set())

    def test_own_check_marker_is_neutral_and_configurable(self):
        self.assertTrue(c.is_own_check(c.check_ua()))
        self.assertNotRegex(c.check_ua().lower(), "easyxlab|easybyte|github")   # never identifies the lab
        self.assertTrue(c.is_own_check("Mozilla/5.0 (compatible; EasyxLab-S9-check/0.1)"))  # design-phase requests
        saved = dict(c._CHECK)
        try:
            c.configure_check("Mozilla/5.0 (compatible; uptime-check/1.0; id=k3x9)", "id=k3x9")
            self.assertTrue(c.is_own_check("Mozilla/5.0 (compatible; uptime-check/1.0; id=k3x9)"))
            self.assertFalse(c.is_own_check(UA["human"]))
        finally:
            c._CHECK.update(saved)


class TestWeeks(unittest.TestCase):
    def test_windows(self):
        s, e = c.week_window("2026-W41")
        self.assertEqual((s, e), (datetime(2026, 10, 5, tzinfo=UTC), datetime(2026, 10, 12, tzinfo=UTC)))
        self.assertEqual(c.last_complete_week(datetime(2026, 10, 12, 4, 5, tzinfo=UTC)), "2026-W41")
        self.assertEqual(c.week_window("2026-W53")[0], datetime(2026, 12, 28, tzinfo=UTC))
        self.assertEqual(c.weeks_between("2026-W52", "2027-W01"), ["2026-W52", "2026-W53", "2027-W01"])
        with self.assertRaises(ValueError):
            c.week_window("2026-41")


class TestStats(unittest.TestCase):
    def test_wilson(self):
        lo, hi = st.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.2366, places=3)
        self.assertAlmostEqual(hi, 0.7634, places=3)
        self.assertAlmostEqual(st.wilson(0, 10)[1], 0.2775, places=3)

    def test_zero_event(self):
        self.assertAlmostEqual(st.zero_event_upper(10), 0.2589, places=3)
        self.assertEqual(st.zero_event_upper(0), 1.0)

    def test_mann_kendall_exact(self):
        mk = st.mann_kendall([1, 2, 3, 4, 5])
        self.assertEqual((mk["S"], mk["method"]), (10, "exact"))
        self.assertAlmostEqual(mk["p_increase"], 1 / 120)
        self.assertAlmostEqual(mk["p_two"], 2 / 120)
        self.assertAlmostEqual(st.mann_kendall([5, 4, 3, 2, 1])["p_increase"], 1.0)
        # S = 8 for n = 5 occurs with exactly one inversion: P(S >= 8) = (1 + 4) / 120
        self.assertAlmostEqual(st.mann_kendall([2, 1, 3, 4, 5])["p_increase"], 5 / 120)

    def test_mann_kendall_ties(self):
        mk = st.mann_kendall([1, 1, 2, 3, 3, 4, 5, 5])
        self.assertEqual(mk["method"], "normal-ties")
        self.assertLess(mk["p_increase"], 0.01)

    def test_sens_slope(self):
        self.assertAlmostEqual(st.sens_slope([0, 2, 4, 6, 100]), 2.0)

    def test_fisher(self):
        f = st.fisher_exact(3, 1, 1, 3)
        self.assertAlmostEqual(f["p_two"], 0.4857, places=4)
        self.assertAlmostEqual(f["p_greater"], 0.2429, places=4)


class TestLiveChecks(unittest.TestCase):
    """The weekly deviation alarm, with HTTP stubbed (no network)."""
    def run_with(self, robots, pages_ok=True, footer=True):
        home = f'<a href="{ALW}">page 1</a> <a href="{DIS}">page 2</a>' if footer else "<p></p>"
        def fake(url, method="GET", timeout=30):
            if "/robots.txt" in url:
                return 200, {"cf-cache-status": "HIT"}, robots
            if P in url:
                return (200, {"x-robots-tag": "noindex"}, "") if pages_ok else (404, {}, "")
            return 200, {}, home
        orig, col.http = col.http, fake
        try:
            return col.live_checks(site(), T_L + timedelta(days=3))
        finally:
            col.http = orig

    GOOD = (f"User-agent: *\nContent-Signal: search=yes\nDisallow: {DIS}\n"
            f"Disallow: {ROB}\nAllow: /\n")

    def test_all_deployed(self):
        r = self.run_with(self.GOOD)
        self.assertEqual(r["deviations"], [])
        self.assertTrue(r["robots_plain_ok"] and r["study_pages_ok"] and r["footer_links_ok"])

    def test_each_missing_piece_is_a_deviation(self):
        self.assertEqual(len(self.run_with("User-agent: *\nAllow: /\n")["deviations"]), 1)
        self.assertEqual(len(self.run_with(self.GOOD, pages_ok=False)["deviations"]), 1)
        self.assertEqual(len(self.run_with(self.GOOD, footer=False)["deviations"]), 1)


class TestRobotsCheck(unittest.TestCase):
    BASE = "License: https://site-b.example/rsl.xml\n\nUser-agent: *\nContent-Signal: search=yes, ai-input=yes, ai-train=no\n"

    def test_disallow_before_allow_in_star_group(self):
        ok = self.BASE + f"Disallow: {DIS}\nDisallow: {ROB}\nAllow: /\n\nSitemap: x\n"
        self.assertTrue(col.robots_has_trap(ok, [DIS, ROB]))

    def test_order_and_group_matter(self):
        after = self.BASE + f"Allow: /\nDisallow: {DIS}\n"
        self.assertFalse(col.robots_has_trap(after, [DIS]))
        named = self.BASE + "Allow: /\n\nUser-agent: GPTBot\nDisallow: " + P + "disallowed/\n"
        self.assertFalse(col.robots_has_trap(named, [DIS]))
        self.assertFalse(col.robots_has_trap(self.BASE + "Allow: /\n", [DIS]))


def log_line(ip, ts, path, ua, ref="-"):
    return f'{ip} - [{ts.strftime("%d/%b/%Y:%H:%M:%S +0000")}] "GET {path} HTTP/1.1" 200 512 "{ref}" "{ua}" cf_ray=8c1f2a3b4c5d6e7f-MAD'


def ranges_dir():
    d = Path(tempfile.mkdtemp())
    files = {"openai-gptbot": ["192.0.2.0/28"], "openai-chatgpt-user": ["192.0.2.16/28"],
             "anthropic": ["198.51.100.0/26"], "google-common": ["198.51.100.64/27"]}
    for k, prefs in files.items():
        (d / f"{k}.json").write_text(json.dumps({"creationTime": "2026-10-01", "prefixes": [{"ipv4Prefix": p} for p in prefs]}))
    return d


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        t = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)   # 2026-W42, after T_R + 72 h and after T_L
        lines = [
            log_line("192.0.2.3", t, "/robots.txt", UA["gptbot"]),
            log_line("192.0.2.3", t, "/mm-to-inches/", UA["gptbot"]),
            log_line("192.0.2.3", t, ALW, UA["gptbot"], ref="https://site-b.example/"),
            log_line("192.0.2.4", t, DIS, UA["gptbot"]),                # verified violation
            log_line("192.0.2.20", t, DIS, UA["chatgpt"]),              # permitted user fetch
            log_line("203.0.113.50", t, DIS, UA["gptbot"]),             # spoofed
            log_line("203.0.113.50", t, "/.env", UA["gptbot"]),                       # spoofed probe (longitudinal)
            log_line("203.0.113.51", t, ROB, UA["curl"]),              # robots.txt miner
            log_line("203.0.113.51", t, DIS, UA["curl"]),
            log_line("203.0.113.52", t, P + "disallowed", UA["gptbot"]),              # no slash: not covered
            log_line("203.0.113.53", t, "/w8rj5n/x2c7v9/", UA["human"]),             # site-a's trap folder, asked on site-b
            log_line("203.0.113.60", t, "/", UA["newbot"]),
            log_line("203.0.113.60", t, "/a/", UA["newbot"]),
            log_line("203.0.113.60", t, "/b/", UA["newbot"]),
            log_line("198.51.100.200", t, DIS, c.check_ua()),            # our own check: excluded
            log_line("192.0.2.3", t - timedelta(days=9), "/x/", UA["gptbot"]),        # previous week
        ]
        self.log = self.tmp / "access.log"
        self.log.write_text("\n".join(lines) + "\n")
        self.log_a = self.tmp / "access-a.log"
        self.log_a.write_text(log_line("192.0.2.3", t, "/", UA["gptbot"]) + "\n")
        cfg = {"study_end": "2027-01-15T00:00:00Z",
               "sites": {"site-b": {**SITE_CFG, "log": {"files": [str(self.log)]}},
                         "site-a": {"domain": "site-a.example", "log": {"files": [str(self.log_a)]},
                                    "arms": {"robots-only": "/w8rj5n/x2c7v9/"}}},
               "active_sessions": [{"id": "s1", "assistant": "ChatGPT", "site": "site-b", "arm": "disallowed",
                                    "t": "2026-10-13T11:55:00Z"}]}
        self.cfg = self.tmp / "sites.json"
        self.cfg.write_text(json.dumps(cfg))
        self.out = self.tmp / "weekly"
        self.argv = ["--config", str(self.cfg), "--week", "last", "--out", str(self.out), "--ranges-dir",
                     str(ranges_dir()), "--cache-dir", str(self.tmp / "cache"), "--no-dns", "--no-live-checks",
                     "--now", "2026-10-19T06:00:00Z"]

    def run_collect(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = col.main(self.argv)
        return rc, buf.getvalue()

    def test_week_outputs_labels_and_privacy(self):
        rc, _ = self.run_collect()
        self.assertEqual(rc, 0)
        wd = self.out / "2026-W42"
        trap = an.rows(wd / "site-b" / "trap.csv")
        got = {(r["arm"], r["label"], r["bot"], r["verdict"]): int(r["requests"]) for r in trap}
        self.assertEqual(got[("disallowed", "violation", "GPTBot", "verified")], 1)
        self.assertEqual(got[("disallowed", "permitted-user-fetch", "ChatGPT-User", "verified")], 1)
        self.assertEqual(got[("disallowed", "unverified-claim", "GPTBot", "spoofed")], 1)
        self.assertEqual(got[("allowed", "control", "GPTBot", "verified")], 1)
        self.assertEqual(got[("robots-only", "undeclared:http-library", "(undeclared)", "-")], 1)
        self.assertEqual(got[("other-under-prefix", "other-under-prefix", "GPTBot", "spoofed")], 1)
        self.assertEqual(got[("foreign-prefix:site-a", "foreign-prefix", "(undeclared)", "-")], 1)
        miner = next(r for r in trap if r["arm"] == "disallowed" and r["bot"] == "(undeclared)")
        self.assertEqual(int(miner["sources_also_in_robots_only"]), 1)
        self.assertEqual(sum(int(r["requests"]) for r in trap), 8)      # 9 trap lines, own check excluded
        ctrl = next(r for r in trap if r["label"] == "control")
        self.assertEqual(ctrl["referer"], "same-site")
        exp = {(r["bot"], r["verdict"]): r for r in an.rows(wd / "site-b" / "exposure.csv")}
        g = exp[("GPTBot", "verified")]
        self.assertEqual((int(g["control_active"]), int(g["disallowed_active"]), int(g["robots_after_t_robots"]),
                          int(g["html_after_t_link"])), (1, 1, 1, 1))
        # S2's longitudinal table: trap prefix excluded, the probe counted
        by_bot = {(r["bot"], r["verdict"]): int(r["requests"]) for r in an.rows(wd / "site-b" / "by_bot.csv")}
        self.assertEqual(by_bot[("GPTBot", "verified")], 2)
        self.assertEqual(by_bot[("GPTBot", "spoofed")], 1)
        tokens = an.rows(wd / "site-b" / "new_tokens.csv")
        self.assertEqual([(r["token"], r["requests"]) for r in tokens], [("shinynewcrawler", "3")])
        act = an.rows(wd / "site-b" / "active_arm.csv")[0]
        self.assertEqual((act["verified_disallowed"], act["unverified_disallowed"]), ("2", "1"))
        m = json.loads((wd / "MANIFEST.json").read_text())
        self.assertFalse(m["retroactive"])
        self.assertEqual(m["abv_sha256"], c.ABV_SHA256)
        blob = "".join(p.read_text() for p in wd.rglob("*") if p.is_file())
        for secret in ("192.0.2.3", "203.0.113.50", "198.51.100.200", "site-b.example", "site-a.example", "qz7kxm",
                       "a4hn2w", "t9pe3r", "m6cv8d", "w8rj5n"):
            self.assertNotIn(secret, blob)

    def test_idempotent(self):
        self.run_collect()
        f = self.out / "2026-W42" / "MANIFEST.json"
        before = f.read_text()
        rc, out = self.run_collect()
        self.assertEqual(rc, 0)
        self.assertIn("already collected", out)
        self.assertEqual(f.read_text(), before)

    def test_retroactive_flag_and_guard(self):
        self.argv[self.argv.index("--now") + 1] = "2026-11-30T06:00:00Z"
        self.argv[self.argv.index("last")] = "2026-W42"
        self.run_collect()
        self.assertTrue(json.loads((self.out / "2026-W42" / "MANIFEST.json").read_text())["retroactive"])
        # the publication guard refuses a directory carrying a studied domain
        d = Path(tempfile.mkdtemp())
        (d / "x.csv").write_text("a,site-b.example\n")
        self.assertTrue(col.check_dir(d, set(), ["site-b.example"]))

    def test_zero_lines_is_a_deviation_for_the_current_week(self):
        self.log.write_text("")                     # site-b silent, site-a still logging
        rc, out = self.run_collect()
        self.assertEqual(rc, 2)
        self.assertIn("DEVIATION", out)


class TestHypotheses(unittest.TestCase):
    def test_h1(self):
        rows = [{"bot": "GPTBot", "verdict": "verified", "disallowed_active": 0, "robots_only_active": 0,
                 "control_active": 10, "tested_linked": True, "tested_robots": False},
                {"bot": "ClaudeBot", "verdict": "verified", "disallowed_active": 1, "robots_only_active": 0,
                 "control_active": 3, "tested_linked": True, "tested_robots": True}]
        h = an.h1(rows)
        self.assertEqual(h["OpenAI"]["verdict"], "not falsified")
        self.assertAlmostEqual(h["OpenAI"]["upper95_violation_prob"], 0.2589, places=3)
        self.assertEqual(h["Anthropic"]["verdict"], "falsified")
        self.assertEqual(h["Apple"]["verdict"], "not tested")

    def test_h2_descoped(self):
        h = an.h2([])
        self.assertTrue(all(r["verdict"].startswith("not tested in this run") for r in h.values()))
        one = [{"assistant": "ChatGPT", "requested_arm": "disallowed", "verified_disallowed": "1", "verified_allowed": "0"}] * 3
        self.assertTrue(an.h2(one)["ChatGPT"]["verdict"].startswith("exploratory only"))

    def test_h3(self):
        def r(arm, verdict, claim, n):
            return {"site": "site-b", "arm": arm, "phase": "active", "bot": "GPTBot", "verdict": verdict,
                    "operator_claim": claim, "requests": n}
        few = [r("allowed", "spoofed", "obeys", 2), r("disallowed", "spoofed", "obeys", 3)]
        self.assertTrue(an.h3(few)["verdict"].startswith("insufficient"))
        many = [r("allowed", "spoofed", "obeys", 5), r("disallowed", "spoofed", "obeys", 15),
                r("allowed", "verified", "obeys", 30), r("disallowed", "verified", "obeys", 0)]
        self.assertEqual(an.h3(many)["verdict"], "supported")
        same = [r("allowed", "spoofed", "obeys", 20), r("disallowed", "spoofed", "obeys", 0),
                r("allowed", "verified", "obeys", 30)]
        self.assertEqual(an.h3(same)["verdict"], "falsified")

    def test_h4_h5(self):
        weeks = [f"2026-W{w}" for w in range(41, 53)]
        flat = [{"site": "site-a", "week": w, "prospective": True, "testable": 100, "spoofed": 40 + (i % 2),
                 "verified": 60, "spoofed_share": (40 + (i % 2)) / 100} for i, w in enumerate(weeks)]
        self.assertTrue(an.h4(flat)["verdict"].startswith("not falsified"))
        rising = []
        for s in ("site-b", "site-c"):
            rising += [{"site": s, "week": w, "prospective": True, "testable": 100, "spoofed": 5 + 5 * i,
                        "verified": 100 - 5 * i, "spoofed_share": (5 + 5 * i) / 100} for i, w in enumerate(weeks)]
        self.assertEqual(an.h5(rising)["verdict"], "supported")
        self.assertEqual(an.h6(rising)["site-b"]["verdict"], "not supported")
        self.assertTrue(an.h4(flat[:5])["verdict"].startswith("insufficient"))


if __name__ == "__main__":
    unittest.main()
