#!/usr/bin/env python3
"""S10 step 0a — validator landscape: GitHub repository metadata (gh api) + Greenlight Docker image date.
Writes data/validator_landscape.csv. Needs the `gh` CLI (authenticated) and network."""
import csv, json, os, subprocess, urllib.request
S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPOS = [("skinkie/DATA4PTTools", "Greenlight (DATA4PT), EPIP-oriented XSD + rules"),
         ("entur/netex-validator-java", "Nordic profile library"), ("entur/antu", "Nordic validation service"),
         ("entur/udug", "frontend for Nordic validation reports"),
         ("tmfg/digitraffic-tis-vaco", "Fintraffic: GTFS + NeTEx Nordic profile"),
         ("enroute-mobi/chouette-core", "French profile, data-management suite"),
         ("enroute-mobi/netex-cli-validator", "XSD only"),
         ("theoremus-urban-solutions/netex-validator", "Go, claims 'the EU NeTEx Profile'"),
         ("aschmid-code/netex-validator", "NeTEx 2.0 XSD only (Swiss microservice)"),
         ("Muspah/netex-belgium", "validates the whole-Belgium EPIP export (data.gtfs.be)"),
         ("ciaranmccormick/transidate", "TransXChange + NeTEx validator"),
         ("hfjelstad/NeTEx-Nordic", "Nordic profile proof of concept"),
         ("etalab/transport-site", "French NAP; calls enRoute Chouette Valid for NeTEx"),
         ("napcore-tools/web-awesome_napcore_tools", "NAPCORE tool catalogue")]
rows = []
for repo, scope in REPOS:
    m = json.loads(subprocess.run(["gh", "api", f"repos/{repo}"], capture_output=True, text=True).stdout)
    c = json.loads(subprocess.run(["gh", "api", f"repos/{repo}/commits?per_page=1"], capture_output=True, text=True).stdout)
    rows.append(dict(repo=repo, scope=scope, licence=(m.get("license") or {}).get("spdx_id") or "none",
                     archived=m.get("archived"), stars=m.get("stargazers_count"), pushed=(m.get("pushed_at") or "")[:10],
                     last_commit=c[0]["commit"]["committer"]["date"][:10] if isinstance(c, list) and c else ""))
req = urllib.request.Request("https://hub.docker.com/v2/repositories/lekojson/greenlight/",
                             headers={"User-Agent": "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"})
d = json.load(urllib.request.urlopen(req, timeout=30))
rows.append(dict(repo="docker:lekojson/greenlight", scope="Greenlight Docker image", licence="", archived="", stars="",
                 pushed=d.get("last_updated", "")[:10], last_commit=""))
with open(os.path.join(S, "data", "validator_landscape.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
for r in rows:
    print(r)
