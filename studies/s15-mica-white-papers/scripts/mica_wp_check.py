#!/usr/bin/env python3
"""mica_wp_check — is this a MiCA crypto-asset white paper in the format of Implementing Regulation (EU) 2024/2984?

Usage:
    mica_wp_check.py <file-or-url> [--package mica_taxonomy_2025.zip] [--no-validate]
                     [--lei LEI] [--dti DTI ...]

Prints a JSON verdict. Every finding cites the rule it comes from:
  * MiCA = Regulation (EU) 2023/1114, Art. 6(10) / 19(9) / 51(9): "shall be made available in a machine-readable format";
  * ITS  = Commission Implementing Regulation (EU) 2024/2984, Art. 2(1) (XHTML + Inline XBRL 1.1; (a) a single XHTML
           file; (b)/(c) ISO 17442 LEI where available) and Art. 2(2) (the taxonomy/elements of Tables 2-4);
  * ESMA = ESMA MiCA XBRL taxonomy 2025 (published 5 August 2025), validated with Arelle incl. its formula assertions.

A URL is fetched through the polite fetcher (robots.txt honoured, 1 request/second per host). Part of EasyxLab study
S15; Apache-2.0.
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

IX_NS = "http://www.xbrl.org/2013/inlineXBRL"
IX_NS_OLD = "http://www.xbrl.org/2008/inlineXBRL"
XHTML_NS = "http://www.w3.org/1999/xhtml"
ESMA_ENTRY_RE = re.compile(r"^https?://www\.esma\.europa\.eu/taxonomy/mica/2025-03-31/mica_entry_table_([234])\.xsd$")
ESMA_ANY_MICA_RE = re.compile(r"esma\.europa\.eu/taxonomy/mica/", re.I)
TABLE_TYPE = {"2": "other (Title II)", "3": "ART (Title III)", "4": "EMT (Title IV)"}
LEI_RE = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")
DTI_RE = re.compile(r"^[0-9BCDFGHJKLMNPQRSTVWXZ]{9}$")  # ISO 24165: 9 chars, no vowels except digits

# Concepts (local names) of the ESMA MiCA taxonomy that carry identifiers we cross-check.
LEI_CONCEPTS = {
    "OfferorsLegalEntityIdentifier", "IssuersLegalEntityIdentifier", "OperatorsLegalEntityIdentifier",
    "EmoneyTokenIssuersLegalEntityIdentifier", "AssetreferencedTokenIssuersLegalEntityIdentifier",
    "OtherTokenServiceProviderIdentifier", "OtherTokenServiceProviderIdentifierForAssetreferencedToken",
}
DTI_CONCEPTS = {
    "OtherTokenDigitalTokenIdentifierCode", "OtherTokenFunctionallyFungibleGroupDigitalTokenIdentifier",
    "EmoneyTokenDigitalTokenIdentifierCode", "EmoneyTokenFunctionallyFungibleGroupDigitalTokenIdentifier",
    "AssetreferencedTokenDigitalTokenIdentifierCode", "AssetreferencedTokenFunctionallyFungibleGroupDigitalTokenIdentifier",
}
DATE_CONCEPTS = {
    "DateOfNotificationForOtherTokenWhitePaper", "DateOfNotificationForEmoneyTokenWhitePaper",
    "DateOfNotificationForAssetreferencedTokenWhitePaper", "OtherTokenWhitePaperPublicationDate",
    "EmoneyTokenWhitePaperPublicationDate", "AssetreferencedTokenWhitePaperPublicationDate",
}

ANTIBOT_MARKERS = re.compile(
    rb"(_Incapsula_Resource|Incapsula incident|cf-chl-|challenge-platform|Just a moment\.\.\.|Attention Required! \| Cloudflare"
    rb"|captcha-delivery|DataDome|px-captcha|Access Denied</h1>.{0,200}akamai|Request unsuccessful\. Incapsula)",
    re.I | re.S,
)

# Document classes, from best to worst for the question "is the ITS-format file here?"
DOC_CLASSES = ["ixbrl-esma", "ixbrl-1.0", "ixbrl-other", "xhtml-no-ixbrl", "pdf", "html", "zip-other", "other", "empty"]


META_REFRESH_RE = re.compile(
    rb"<meta[^>]+http-equiv\s*=\s*[\"']?refresh[\"']?[^>]*content\s*=\s*[\"']\s*(\d+(?:\.\d+)?)\s*[;,]\s*(?:url\s*=\s*)?[\"']?([^\"'>]+)",
    re.I)
META_REFRESH_RE2 = re.compile(  # content before http-equiv
    rb"<meta[^>]+content\s*=\s*[\"']\s*(\d+(?:\.\d+)?)\s*[;,]\s*(?:url\s*=\s*)?[\"']?([^\"'>]+)[\"']?[\"'][^>]*http-equiv\s*=\s*[\"']?refresh", re.I)
JS_REDIRECT_RE = re.compile(
    rb"(?:window\.|document\.|top\.)?location(?:\.href)?\s*(?:=|\.replace\(|\.assign\()\s*[\"']([^\"']+)[\"']", re.I)


def instant_redirect(data: bytes) -> str | None:
    """Target of an instant client-side redirect: <meta http-equiv="refresh"> with delay <= 1 s, or a trivial
    JavaScript location redirect on a page with (almost) no visible text. None otherwise."""
    head = data[:200000]
    for rx in (META_REFRESH_RE, META_REFRESH_RE2):
        m = rx.search(head)
        if m and float(m.group(1)) <= 1:
            return m.group(2).decode("utf-8", "replace").strip()
    text = re.sub(rb"<script.*?</script>|<style.*?</style>|<[^>]+>|\s+", b" ", head, flags=re.S | re.I).strip()
    if len(text) < 300:
        m = JS_REDIRECT_RE.search(head)
        if m:
            return m.group(1).decode("utf-8", "replace").strip()
    return None


def lei_checksum_ok(lei: str) -> bool:
    """ISO 17442 / ISO 7064 MOD 97-10."""
    lei = lei.strip().upper()
    if not LEI_RE.match(lei):
        return False
    num = "".join(str(int(c, 36)) for c in lei)
    return int(num) % 97 == 1


@dataclass
class DocInfo:
    doc_class: str
    size: int = 0
    is_xml_wellformed: bool | None = None
    root: str | None = None
    has_ix_namespace: bool = False
    schema_refs: list[str] = field(default_factory=list)
    esma_table: str | None = None
    ix_fact_count: int = 0
    ix_references_count: int = 0
    title: str | None = None
    antibot: bool = False
    zip_members: list[str] = field(default_factory=list)
    ix_version: str | None = None  # "1.1" (2013 namespace), "1.0" (2008 namespace only) or None


def _title(head: bytes) -> str | None:
    m = re.search(rb"<title[^>]*>(.*?)</title>", head, re.I | re.S)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1).decode("utf-8", "replace")).strip()[:200]


def sniff(data: bytes, ctype: str | None = None, name: str | None = None) -> DocInfo:
    """Classify a document from its bytes (no network, no Arelle)."""
    size = len(data)
    if not data.strip():
        return DocInfo("empty", size)
    head = data[:4096]
    if data[:5] == b"%PDF-":
        return DocInfo("pdf", size)
    if data[:4] == b"PK\x03\x04":
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
            members = zf.namelist()
        except zipfile.BadZipFile:
            return DocInfo("other", size)
        info = DocInfo("zip-other", size, zip_members=members[:50])
        return info
    if ANTIBOT_MARKERS.search(data[:200000]):
        return DocInfo("html", size, antibot=True, title=_title(data[:200000]))
    text_like = b"<" in head and (b"<html" in data[:200000].lower() or b"<?xml" in head[:100] or b"<!doctype" in head.lower())
    if not text_like:
        return DocInfo("other", size)
    info = DocInfo("html", size, title=_title(data[:500000]))
    has_11, has_10 = IX_NS.encode() in data, IX_NS_OLD.encode() in data
    has_ix = has_11 or has_10
    info.has_ix_namespace = has_ix
    info.ix_version = "1.1" if has_11 else "1.0" if has_10 else None
    info.schema_refs = sorted(set(m.decode("utf-8", "replace") for m in re.findall(
        rb"<(?:[A-Za-z0-9_.-]+:)?schemaRef\b[^>]*?(?:xlink:)?href=[\"']([^\"']+)[\"']", data)))
    info.ix_fact_count = len(re.findall(rb"<(?:[A-Za-z0-9_.-]+:)?(?:nonNumeric|nonFraction)\b", data))
    info.ix_references_count = len(re.findall(rb"<(?:[A-Za-z0-9_.-]+:)?references\b", data))
    # XML well-formedness and root element (XHTML must be XML).
    try:
        from lxml import etree
        root = etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True))
        info.is_xml_wellformed = True
        info.root = root.tag
    except Exception:
        info.is_xml_wellformed = False
    for ref in info.schema_refs:
        m = ESMA_ENTRY_RE.match(ref)
        if m:
            info.esma_table = m.group(1)
    is_xhtml_name = bool(name and re.search(r"\.xhtml?$", name.split("?")[0], re.I))
    is_xhtml_type = bool(ctype and "xhtml" in ctype.lower())
    is_xhtml_root = info.root == f"{{{XHTML_NS}}}html"
    root_local = (info.root or "").split("}")[-1].lower()
    if info.is_xml_wellformed and root_local != "html" and not has_ix:
        info.doc_class = "other"  # e.g. an S3/XML error document
    elif has_ix and info.schema_refs:
        # ITS Art. 2(1) requires Inline XBRL 1.1: a file in the 1.0 (2008) namespace only is its own class.
        info.doc_class = ("ixbrl-1.0" if info.ix_version == "1.0" else
                          "ixbrl-esma" if info.esma_table else "ixbrl-other")
    elif is_xhtml_name or is_xhtml_type or (is_xhtml_root and b"<?xml" in head[:100]):
        info.doc_class = "xhtml-no-ixbrl"
    else:
        info.doc_class = "html"
    return info


# ---------------------------------------------------------------------------------------------------------------
# Arelle validation
# ---------------------------------------------------------------------------------------------------------------
def arelle_validate(path: Path, package: Path, formulas: bool = True, validate: bool = True) -> dict:
    """Validate an Inline XBRL file with Arelle against the pinned ESMA taxonomy package (offline).
    Returns counts of messages by level and code family, facts and the identifiers found."""
    import logging
    from arelle import RuntimeOptions
    from arelle.api.Session import Session

    records: list[dict] = []

    class H(logging.Handler):
        def emit(self, rec):
            code = getattr(rec, "messageCode", None) or ""
            records.append({"level": rec.levelname, "code": code, "msg": str(rec.getMessage())[:300]})

    opts = RuntimeOptions.RuntimeOptions(
        entrypointFile=str(path), packages=[str(package)], validate=validate,
        formulaAction="run" if formulas else "none", internetConnectivity="offline",
        formulaAsserResultCounts=formulas, logFormat="[%(messageCode)s] %(message)s",
        keepOpen=True,  # keep the model so that facts can be read after validation
    )
    out: dict = {"loaded": False}
    with Session() as s:
        s.run(opts, logHandler=H())
        models = s.get_models()
        if models:
            m = models[0]
            out["loaded"] = m.modelDocument is not None
            facts = list(m.factsInInstance) if out["loaded"] else []
            out["fact_count"] = len(facts)
            leis, dtis, dates, ctx_ids = {}, {}, {}, set()
            for f in facts:
                ln = f.qname.localName if f.qname is not None else ""
                v = (f.xValue if f.xValid else f.value) if hasattr(f, "xValue") else f.value
                v = str(v).strip() if v is not None else ""
                if ln in LEI_CONCEPTS:
                    leis.setdefault(ln, []).append(v.upper())
                elif ln in DTI_CONCEPTS:
                    dtis.setdefault(ln, []).append(v.upper())
                elif ln in DATE_CONCEPTS:
                    dates.setdefault(ln, []).append(v[:10])
            for c in (m.contexts.values() if out["loaded"] else []):
                try:
                    ctx_ids.add((c.entityIdentifier[0], c.entityIdentifier[1].upper()))
                except Exception:
                    pass
            out["lei_facts"] = leis
            out["dti_facts"] = dtis
            out["date_facts"] = dates
            out["context_identifiers"] = sorted(ctx_ids)
    # Arelle reports unsatisfied assertions with the assertion's id (or 'formula:assertionUnsatisfied') as code.
    errs = [r for r in records if r["level"] in ("ERROR", "ERROR-SEMANTIC", "CRITICAL", "INCONSISTENCY")]
    warns = [r for r in records if r["level"] == "WARNING"]
    def family(code: str) -> str:
        c = code or ""
        if c.startswith(("xbrlfe", "xbrlvarinste", "xbrlve", "xbrlce", "xbrlcae", "formula", "err:", "xfie", "xffe")):
            return "formula-processing"
        if c.startswith(("ix11", "ix", "ixe")):
            return "inline-xbrl"
        if c.startswith(("xbrl.", "xbrl", "xmlSchema", "xml", "xbrldte", "xbrldie", "xbrl21", "lrr", "utr")):
            return "xbrl-core"
        if c.startswith(("IOerror", "FileNotLoadable", "arelle:", "webCache")):
            return "load"
        return "assertion"
    out["errors"] = len(errs)
    out["warnings"] = len(warns)
    fam: dict[str, int] = {}
    codes: dict[str, int] = {}
    for r in errs:
        fam[family(r["code"])] = fam.get(family(r["code"]), 0) + 1
        codes[r["code"]] = codes.get(r["code"], 0) + 1
    out["error_families"] = fam
    out["error_codes"] = dict(sorted(codes.items(), key=lambda kv: -kv[1])[:25])
    asr = re.compile(r"(\w+) Assertion (\S+) evaluations : (\d+) satisfied, (\d+) not satisfied")
    per: dict[str, tuple[int, int]] = {}
    for r in records:
        m = asr.search(r["msg"])
        if m:
            per[m.group(2)] = (int(m.group(3)), int(m.group(4)))
    out["assertions_evaluated"] = len(per)
    out["assertions_failed"] = sorted(k for k, (s_, u_) in per.items() if u_ > 0)
    out["log_codes"] = sorted({r["code"] for r in records})[:30]
    return out


# ---------------------------------------------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------------------------------------------
def all_leis(v: dict) -> set[str]:
    s = {x for vals in v.get("lei_facts", {}).values() for x in vals}
    s |= {i for scheme, i in v.get("context_identifiers", []) if "17442" in scheme}
    return {x for x in s if x}


def all_dtis(v: dict) -> set[str]:
    out = set()
    for vals in v.get("dti_facts", {}).values():
        for x in vals:
            out |= {p.strip().upper() for p in re.split(r"[|,;\s]+", x) if p.strip()}
    return out


def verdict(data: bytes, ctype: str | None = None, name: str | None = None, package: Path | None = None,
            validate: bool = True, tmpdir: Path | None = None, lei: str | None = None,
            dtis: list[str] | None = None) -> dict:
    info = sniff(data, ctype, name)
    findings: list[dict] = []

    def add(rule: str, ok: bool, detail: str):
        findings.append({"rule": rule, "ok": ok, "detail": detail})

    add("ITS 2024/2984 Art. 2(1) — XHTML with Inline XBRL 1.1", info.doc_class in ("ixbrl-esma", "ixbrl-other"),
        f"document class: {info.doc_class}; Inline XBRL version: {info.ix_version}" + (" (anti-bot page)" if info.antibot else ""))
    if info.doc_class in ("ixbrl-esma", "ixbrl-1.0", "ixbrl-other", "xhtml-no-ixbrl"):
        add("ITS 2024/2984 Art. 2(1)(a) — single XHTML file (well-formed XML, XHTML root)",
            bool(info.is_xml_wellformed and info.root == f"{{{XHTML_NS}}}html"),
            f"well-formed XML: {info.is_xml_wellformed}; root: {info.root}")
    if info.doc_class in ("ixbrl-esma", "ixbrl-1.0", "ixbrl-other"):
        add("ITS 2024/2984 Art. 2(2) — ESMA MiCA taxonomy entry point (Tables 2-4)", info.doc_class == "ixbrl-esma",
            f"schemaRef: {info.schema_refs[:3]}")
    result = {"doc": asdict(info), "findings": findings, "validation": None, "identifiers": None}
    if info.doc_class == "ixbrl-esma" and validate and package is not None:
        import tempfile
        d = Path(tmpdir or tempfile.mkdtemp())
        p = d / "wp.xhtml"
        p.write_bytes(data)
        try:
            v = arelle_validate(p, package)
        finally:
            p.unlink(missing_ok=True)
        result["validation"] = v
        add("ESMA MiCA taxonomy — Arelle: XBRL / Inline XBRL / formula assertions, no errors",
            v.get("loaded") and v.get("errors", 1) == 0,
            f"errors: {v.get('errors')} {v.get('error_families')}; warnings: {v.get('warnings')}; facts: {v.get('fact_count')}")
        leis = all_leis(v)
        bad = sorted(x for x in leis if not lei_checksum_ok(x))
        add("ITS 2024/2984 Art. 2(1)(b)-(c) — ISO 17442 LEI present and well-formed", bool(leis) and not bad,
            f"{len(leis)} LEI value(s); malformed: {len(bad)}")
        ids = {"leis": sorted(leis), "dtis": sorted(all_dtis(v)), "dates": v.get("date_facts")}
        if lei:
            ids["register_lei_in_document"] = lei.upper() in leis
        if dtis:
            ids["register_dti_in_document"] = bool({d.upper() for d in dtis} & set(ids["dtis"]))
        result["identifiers"] = ids
    result["available_in_its_format"] = info.doc_class == "ixbrl-esma"
    result["valid"] = bool(result["validation"] and result["validation"].get("loaded") and result["validation"].get("errors") == 0)
    return result


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("target", help="file path or http(s) URL of the white paper")
    ap.add_argument("--package", default=str(Path(__file__).resolve().parent.parent / "data/raw/taxonomy/mica_taxonomy_2025.zip"),
                    help="ESMA MiCA taxonomy package (mica_taxonomy_2025.zip)")
    ap.add_argument("--no-validate", action="store_true")
    ap.add_argument("--lei", help="LEI expected (e.g. from ESMA's register)")
    ap.add_argument("--dti", nargs="*", help="DTI code(s) expected")
    a = ap.parse_args(argv)
    ctype = None
    if re.match(r"^https?://", a.target):
        sys.path.insert(0, str(Path(__file__).parent))
        from fetch import Fetcher
        r = Fetcher(Path("work/requests.log")).get(a.target)
        if r["body"] is None:
            print(json.dumps({"target": a.target, "fetch": {k: r[k] for k in ("status", "reason", "final_url")}}, indent=1))
            return 2
        data, ctype, name = r["body"], r["ctype"], r["final_url"]
    else:
        data, name = Path(a.target).read_bytes(), a.target
    pkg = Path(a.package)
    out = verdict(data, ctype, name, pkg if pkg.exists() else None, not a.no_validate, lei=a.lei, dtis=a.dti)
    out["target"] = a.target
    print(json.dumps(out, indent=1, default=str))
    return 0 if out["valid"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
