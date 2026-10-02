#!/usr/bin/env python3
"""Runs the whole S2 pipeline. The mapping from public labels (site-a, site-b, site-c) to
real domains and log files is private: it is read from private/sites.json, or from the file
named in $S2_SITES. Nothing in the outputs carries a domain name."""
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sites = json.loads(Path(os.environ.get("S2_SITES", ROOT / "private" / "sites.json")).read_text())
withhold = Path(os.environ.get("S2_WITHHOLD_ASNS", ROOT / "private" / "withhold-asns.txt"))
excl = ROOT / "data" / "raw" / "exclude-ips.txt"
cache = ROOT / "data" / "raw" / "cache"
tool = [sys.executable, str(ROOT / "scripts" / "ai_bot_verify.py")]
common = ["--cache-dir", str(cache), "--exclude-ip-file", str(excl), "--withhold-asn-file", str(withhold)]
for label, s in sites.items():
    log = str(ROOT / s["log"])
    subprocess.run(tool + [log, "--site", label, "--asn", "--out", str(ROOT / "data" / "logs" / label)] + common, check=True)
    subprocess.run(tool + [log, "--site", label, "--since", "2026-09-02T02:00:00",
                           "--out", str(ROOT / "data" / "raw" / "cmp" / label)] + common, check=True, stdout=subprocess.DEVNULL)
mp = ROOT / "data" / "raw" / "site-map.json"
mp.write_text(json.dumps({s["domain"]: label for label, s in sites.items()}))
env_file = os.environ.get("S2_CF_ENV")
if env_file:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "cf_declared_bots.py"), "--env", env_file,
                    "--zones", *[s["domain"] for s in sites.values()], "--site-map", str(mp),
                    "--days", "30", "--out", str(ROOT / "data" / "cloudflare"),
                    "--cache-dir", str(cache), "--exclude-ip-file", str(excl),
                    "--withhold-asn-file", str(withhold)], check=True, stdout=subprocess.DEVNULL)
subprocess.run([sys.executable, str(ROOT / "scripts" / "aggregate.py")], check=True)
