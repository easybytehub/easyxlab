#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""hvd_check — per-record checker for high-value datasets (Implementing Regulation (EU) 2023/138).

Usage:
    hvd_check.py <dataset-id-on-data.europa.eu | DCAT-AP file (.ttl .rdf .xml .jsonld .nt)> [--strict]

Prints one JSON verdict per dcat:Dataset, citing the article each rule comes from:
  * Art. 3(5)  tagging: dcatap:applicableLegislation = the ELI of 2023/138 and >= 1 dcatap:hvdCategory
               (DCAT-AP HVD 3.0.0, both 1..*);
  * Art. 4(3)  licence: every distribution under CC0, CC BY 4.0 or an equivalent/less restrictive
               open licence (EasyxLab S17 licence classes A/B; see METHOD.md section 5);
  * Art. 3(1)  API: a Data Service modelled as DCAT-AP HVD says (dcat:accessService on a distribution, or a
               dcat:DataService with dcat:servesDataset = the dataset).
Exit code: 0 all pass, 1 any fail, 2 input error. `--strict` applies the licence rules exactly as frozen
for the study; the default adds the post-hoc spellings of deviation D1 and treats the catch-all value
dcat-ap.de/def/licenses/other-closed as unspecific (class E, "warn") rather than closed.
This is a metadata check, not a legal opinion: a dataset may be exempt from the API rule under the Annex,
and only the publisher can say which Annex item a dataset implements.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hvd_rules as R  # noqa: E402

try:
    from rdflib import Graph, URIRef, BNode, Namespace, RDF
except ImportError:  # pragma: no cover
    sys.exit("hvd_check needs rdflib (pip install rdflib)")

DCAT = Namespace("http://www.w3.org/ns/dcat#")
DCT = Namespace("http://purl.org/dc/terms/")
DCATAP = Namespace("http://data.europa.eu/r5r/")
REPO = "https://data.europa.eu/api/hub/repo/datasets/"
FORMATS = {".ttl": "turtle", ".rdf": "xml", ".xml": "xml", ".jsonld": "json-ld", ".json": "json-ld", ".nt": "nt",
           ".n3": "n3"}


def load(arg: str) -> Graph:
    g = Graph()
    if os.path.exists(arg):
        g.parse(arg, format=FORMATS.get(os.path.splitext(arg)[1].lower(), "turtle"))
        return g
    import fetch  # network only when an ID is given; robots.txt and rate limit enforced there
    r = fetch.get(REPO + urllib.parse.quote(arg, safe="~-._") + ".ttl", headers={"Accept": "text/turtle"},
                  max_bytes=50_000_000, timeout=60)
    if r.status != 200:
        raise SystemExit(f"cannot fetch {arg}: HTTP {r.status} {r.error or ''} {r.skipped or ''}")
    g.parse(data=r.body.decode("utf-8", "replace"), format="turtle")
    return g


def _vals(g, s, p):
    return [o for o in g.objects(s, p)]


def _licence_values(g, node):
    """A licence may be an IRI, or a node that points to licences (Czech terms of use, skos matches)."""
    if isinstance(node, URIRef):
        ctx = [str(o) for _, o in g.predicate_objects(node) if isinstance(o, URIRef) and _ != RDF.type]
        return str(node), ctx
    ctx = [str(o) for _, o in g.predicate_objects(node) if isinstance(o, URIRef) and _ != RDF.type]
    return (ctx[0] if ctx else ""), ctx


def check_dataset(g: Graph, ds, strict=False) -> dict:
    checks = []
    # Art. 3(5)
    leg = [str(o) for o in _vals(g, ds, DCATAP.applicableLegislation)]
    eli, variants = R.eli_status(leg)
    cats = [str(o) for o in _vals(g, ds, DCATAP.hvdCategory)]
    if eli == "exact" and cats:
        res, det = "pass", f"ELI present; {len(cats)} HVD categor{'y' if len(cats) == 1 else 'ies'}"
    else:
        probs = []
        if eli == "absent":
            probs.append("no applicableLegislation with the ELI " + R.ELI)
        if eli == "malformed":
            probs.append("ELI malformed: " + ", ".join(variants))
        if not cats:
            probs.append("no dcatap:hvdCategory")
        res, det = "fail", "; ".join(probs)
    checks.append({"article": "3(5)", "rule": "denoted as HVD in metadata (DCAT-AP HVD: applicable legislation "
                   "+ HVD category)", "result": res, "detail": det})
    # Art. 4(3)
    dists = _vals(g, ds, DCAT.distribution)
    ds_lic = _vals(g, ds, DCT.license)
    ds_rights = _vals(g, ds, DCT.rights)
    per = []
    for d in dists:
        lics = _vals(g, d, DCT.license) or ds_lic
        if not lics:
            per.append({"distribution": str(d), "class": "N",
                        "rights_statement": bool(_vals(g, d, DCT.rights) or ds_rights)})
            continue
        v, ctx = _licence_values(g, lics[0])
        per.append({"distribution": str(d), "licence": v,
                    "class": R.licence_class(v, ctx, strict=strict, catch_all_as_e=not strict)})
    verdict = R.dataset_licence_verdict([p["class"] for p in per])
    res = {"pass": "pass", "fail": "fail", "none": "fail", "unclear": "warn"}[verdict]
    det = {"pass": "every distribution under CC0 / CC BY 4.0 or an equivalent open licence",
           "fail": "a distribution is under a share-alike, non-commercial, no-derivatives or closed licence"
                   if verdict == "fail" else "",
           "none": "no licence on any distribution or on the dataset" +
                   (" (only a rights statement)" if any(p.get("rights_statement") for p in per) else ""),
           "unclear": "some licence values name no specific licence (e.g. a catch-all such as "
                      "dcat-ap.de other-closed, typed UnknownIPR by the portal); check them by hand"}[verdict]
    checks.append({"article": "4(3)", "rule": "CC0, CC BY 4.0 or equivalent/less restrictive open licence",
                   "result": res, "detail": det, "distributions": per})
    # Art. 3(1)
    served = any(True for _ in g.subjects(DCAT.servesDataset, ds))
    access = any(_vals(g, d, DCAT.accessService) for d in dists)
    if served or access:
        res, det = "pass", "Data Service modelled (" + ("servesDataset" if served else "accessService") + ")"
    else:
        urls = [str(u) for d in dists for p in (DCAT.accessURL, DCAT.downloadURL) for u in _vals(g, d, p)]
        fmts = [str(f).rsplit("/", 1)[-1] for d in dists for f in _vals(g, d, DCT.format)]
        inf = any(R.inferable_api(f, urls) for f in (fmts or [None]))
        res = "warn" if inf else "fail"
        det = ("no Data Service modelled; a distribution URL or format looks like an API" if inf else
               "no Data Service modelled and no API-like distribution") + \
              " (the Annex exempts some datasets from the API requirement)"
    checks.append({"article": "3(1)", "rule": "available via API (DCAT-AP HVD: associated Data Service)",
                   "result": res, "detail": det})
    n_eli = sum(R.eli_status([str(o) for o in _vals(g, d, DCATAP.applicableLegislation)])[0] == "exact"
                for d in dists)
    info = {"distributions": len(dists), "distributions_with_eli": n_eli}
    overall = "fail" if any(c["result"] == "fail" for c in checks) else (
        "warn" if any(c["result"] == "warn" for c in checks) else "pass")
    return {"dataset": str(ds), "verdict": overall, "checks": checks, "info": info,
            "standard": {"regulation": R.ELI, "profile": "DCAT-AP HVD 3.0.0 (SEMIC, 2024-10-25)"}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target", help="dataset ID on data.europa.eu, or a DCAT-AP file")
    ap.add_argument("--strict", action="store_true", help="licence rules exactly as frozen for EasyxLab S17")
    a = ap.parse_args(argv)
    try:
        g = load(a.target)
    except SystemExit:
        raise
    except Exception as e:  # parse errors
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        return 2
    datasets = sorted(set(g.subjects(RDF.type, DCAT.Dataset)), key=str)
    if not datasets:
        print(json.dumps({"error": "no dcat:Dataset in input"}))
        return 2
    out = [check_dataset(g, d, strict=a.strict) for d in datasets]
    print(json.dumps(out[0] if len(out) == 1 else out, indent=1, ensure_ascii=False))
    return 1 if any(o["verdict"] == "fail" for o in out) else 0


if __name__ == "__main__":
    sys.exit(main())
