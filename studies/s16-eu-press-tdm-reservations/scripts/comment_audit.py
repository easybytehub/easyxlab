#!/usr/bin/env python3
"""Comment-detector audit (METHOD.md s. 6). The sample is drawn by draw_audit_sample.py (seed
20261003) from the detector-v1 flags: 60 of 215 flagged hosts and 40 of 578 hosts with comments
and no flag. LABELS below were assigned by the AI agent that ran the study, reading the comment
blocks of each sampled host (work/audit_sample.txt), with these definitions:
  reservation = a comment reserves TDM or AI/ML use (explicit reference to text and data mining,
                data mining, AI/ML training or the national TDM provision); section labels such as
                "AI crawlers" or "Training crawlers - blocked" do not count;
  prohibition = a comment forbids robots, scraping or automated collection IN GENERAL (not only
                for AI training or by AI systems), i.e. one that also covers a research crawler.
Writes data/comment_audit.csv (host, stratum, v1 and v2 detector flags, labels; no comment text).
"""
import base64
import csv
import json
import os

import nlcomments as N

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# host: (reservation, prohibition, note)
LABELS = {
    "bnn.de": (1, 1, "TDM reserved (s. 44b UrhG); any automated access prohibited"),
    "diena.lv": (1, 0, "AI training crawlers not permitted; purpose-specific"),
    "taz.de": (1, 1, "TDM reserved; use of robots prohibited"),
    "www.aachener-zeitung.de": (1, 1, "group text: Art. 4 CDSM; no TDM, scraping or programs/robots for automatic collection"),
    "www.aamuposti.fi": (1, 0, "group text: scraping not allowed for training AI; purpose-specific"),
    "www.bblat.se": (1, 1, "group text: TDM reserved (Art. 4); scraping not authorised prohibited"),
    "www.blick-aktuell.de": (1, 1, "TDM reserved; use of robots prohibited"),
    "www.dagensmedia.se": (1, 1, "group text as bblat.se"),
    "www.di.se": (1, 1, "group text as bblat.se"),
    "www.dnn.de": (1, 1, "TDM reserved; use of robots prohibited"),
    "www.dvhn.nl": (1, 1, "group text as aachener-zeitung.de"),
    "www.esaimaa.fi": (1, 0, "group text as aamuposti.fi"),
    "www.ess.fi": (1, 0, "group text as aamuposti.fi"),
    "www.furche.at": (1, 0, "TDM (s. 42h(6) UrhG AT) not permitted for AI training; purpose-specific"),
    "www.gd.se": (1, 1, "group text as bblat.se"),
    "www.gooieneemlander.nl": (1, 1, "group text as aachener-zeitung.de"),
    "www.hbl.fi": (1, 1, "group text as bblat.se"),
    "www.heinavedenlehti.fi": (1, 0, "group text as aamuposti.fi"),
    "www.hessenschau.de": (1, 0, "TDM reserved (s. 44b(3) UrhG); automated collection for AI training prohibited; purpose-specific"),
    "www.iisalmensanomat.fi": (1, 0, "group text as aamuposti.fi"),
    "www.kaarina-lehti.fi": (1, 0, "group text as aamuposti.fi"),
    "www.karjalainen.fi": (1, 0, "group text as aamuposti.fi"),
    "www.keskilaakso.fi": (1, 0, "group text as aamuposti.fi"),
    "www.kidsweek.nl": (0, 1, "group text: all rights reserved, no scraping or other automated collection; no TDM/AI term"),
    "www.kleinezeitung.at": (1, 0, "group text as furche.at"),
    "www.koillis-savo.fi": (1, 0, "group text as aamuposti.fi"),
    "www.kouvolansanomat.fi": (1, 0, "group text as aamuposti.fi"),
    "www.kreiszeitung.de": (1, 1, "TDM reserved; use of robots prohibited"),
    "www.ksml.fi": (1, 0, "group text as aamuposti.fi"),
    "www.kuntsari.fi": (1, 0, "group text as aamuposti.fi"),
    "www.kurier.de": (1, 1, "TDM reserved; use of robots prohibited"),
    "www.lansivayla.fi": (1, 0, "group text as aamuposti.fi"),
    "www.lavoixdunord.fr": (0, 0, "section label 'Not allowed bots'"),
    "www.leidschdagblad.nl": (1, 1, "group text as aachener-zeitung.de"),
    "www.lest-eclair.fr": (0, 0, "section label 'Not allowed bots'"),
    "www.maz-online.de": (1, 1, "TDM reserved; use of robots prohibited"),
    "www.milanotoday.it": (1, 1, "automated data mining or scraping prohibited without permission; Art. 4 cited"),
    "www.nextpit.de": (1, 0, "TDM reserved; automated access by AI systems prohibited; purpose-specific"),
    "www.nn.de": (1, 1, "TDM reserved; use of robots prohibited"),
    "www.nordbayern.de": (1, 1, "as nn.de"),
    "www.noz.de": (1, 1, "TDM reserved; use of robots prohibited"),
    "www.nu.nl": (0, 1, "group text as kidsweek.nl"),
    "www.nw.de": (1, 1, "TDM reserved (s. 44b UrhG); crawling bots and scrapers prohibited"),
    "www.parool.nl": (0, 1, "group text as kidsweek.nl"),
    "www.rd.nl": (1, 1, "scraping, harvesting, text/data mining, ML and AI uses prohibited"),
    "www.saechsische.de": (1, 1, "TDM reserved; use of robots prohibited"),
    "www.savonsanomat.fi": (1, 0, "group text as aamuposti.fi"),
    "www.skd.se": (1, 1, "group text as bblat.se"),
    "www.skovdenyheter.se": (1, 1, "group text as bblat.se"),
    "www.sn.at": (1, 0, "group text as furche.at"),
    "www.sss.fi": (1, 0, "group text as aamuposti.fi"),
    "www.standaard.be": (1, 1, "group text as aachener-zeitung.de"),
    "www.sydsvenskan.se": (1, 1, "group text as bblat.se"),
    "www.tagesspiegel.de": (1, 1, "TDM reserved; use of robots prohibited"),
    "www.tt.com": (1, 1, "any automated extraction ('scraping') prohibited, incl. for ML/AI"),
    "www.uudenkaupunginsanomat.fi": (1, 0, "group text as aamuposti.fi"),
    "www.uusimaa.fi": (1, 0, "group text as aamuposti.fi"),
    "www.virgule.lu": (1, 1, "group text as aachener-zeitung.de"),
    "www.volkskrant.nl": (0, 1, "group text as kidsweek.nl"),
    "www.wort.lu": (1, 1, "group text as aachener-zeitung.de"),
    # unflagged stratum: only the non-zero labels are listed; every other sampled host is (0, 0)
    "www.aftonbladet.se": (1, 0, "does not permit unlicensed use for training LLMs; explicitly disallows TDM"),
    "www.hln.be": (0, 1, "group text: no scraping or other automated collection (longer sentence than kidsweek.nl)"),
    "www.svd.se": (1, 0, "as aftonbladet.se"),
}


def main():
    s = json.load(open(os.path.join(ROOT, "work", "audit_sample.json")))
    raw = {}
    for line in open(os.path.join(ROOT, "data", "raw", "scan.jsonl")):
        r = json.loads(line)
        raw[r["host"]] = r
    rows = []
    for m in s["sample"]:
        r = raw[m["host"]]
        body = base64.b64decode(r["_raw"]["robots_b64"]) if r["_raw"]["robots_b64"] else b""
        v2 = N.scan(body, 2)
        lab = LABELS.get(m["host"], (0, 0, "")) if m["stratum"] == "unflagged" else LABELS[m["host"]]
        rows.append(dict(host=m["host"], stratum=m["stratum"], nl_reservation=m["nl_reservation"],
                         nl_prohibition=m["nl_prohibition"], v2_reservation=int(v2["nl_reservation"]),
                         v2_prohibition=int(v2["nl_prohibition"]), label_reservation=lab[0],
                         label_prohibition=lab[1], label_note=lab[2]))
    with open(os.path.join(ROOT, "data", "comment_audit.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    def perf(det, lab):
        fl = [r for r in rows if r[det] == 1]
        un = [r for r in rows if r["stratum"] == "unflagged"]
        return dict(flagged=len(fl), tp=sum(r[lab] == 1 for r in fl),
                    misses_flagged_stratum=sum(r[lab] == 1 and r[det] == 0 for r in rows if r["stratum"] == "flagged"),
                    misses_unflagged=sum(r[lab] == 1 and r[det] == 0 for r in un), unflagged=len(un))
    out = {f"{v}_{k}": perf(f"{p}{k}", f"label_{k}") for v, p in (("v1", "nl_"), ("v2", "v2_")) for k in ("reservation", "prohibition")}
    out["note"] = ("author's audit of v1/v2 (AI agent labels); v2 was revised after reading this sample, so its figures "
                   "are optimistic. Independent audits: v1/v2 seed 777 (data/independent_audit_v2.json), v3 seed 4242 "
                   "(data/independent_audit_v3.json). v4 changes only the re-review's two failure modes; no audit claimed.")
    out["population"] = dict(flagged_v1=s["flagged_population"], unflagged_with_comments_v1=s["unflagged_population"], seed=s["seed"])
    json.dump(out, open(os.path.join(ROOT, "data", "comment_audit_summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
