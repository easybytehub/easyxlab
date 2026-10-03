# SPDX-License-Identifier: Apache-2.0
"""Rules of S17 (METHOD.md §3-§6), as pure functions on plain values.

Used both by the census analysis (search-index JSON) and by the per-record checker
`hvd_check.py` (DCAT-AP RDF), so that the study and the tool apply the same rules.
"""
from __future__ import annotations

import re
import unicodedata

ELI = "http://data.europa.eu/eli/reg_impl/2023/138/oj"
_ELI_HINT = re.compile(r"2023/138|32023r0138|2023_138", re.I)
HVD_CATEGORY_NS = "http://data.europa.eu/bna/"


def eli_status(values) -> tuple[str, list[str]]:
    """'exact' if the exact ELI is among the values; 'malformed' if only a variant that
    mentions the regulation is present; 'absent' otherwise. Returns (status, variants)."""
    vals = [str(v).strip() for v in (values or []) if v]
    if ELI in vals:
        return "exact", [v for v in vals if v != ELI and _ELI_HINT.search(v)]
    variants = [v for v in vals if _ELI_HINT.search(v)]
    return ("malformed" if variants else "absent"), variants


def hvd_categories(values) -> list[str]:
    out = []
    for v in values or []:
        s = str(v).strip()
        if not s:
            continue
        if s.startswith("c_"):
            s = HVD_CATEGORY_NS + s
        out.append(s)
    return out


# ---- licences (METHOD.md §5) -------------------------------------------------------------

def normalise_licence(v: str) -> str:
    s = str(v or "").strip().lower()
    s = s.replace("https://", "http://")
    s = re.sub(r"(/legalcode(\.[a-z]{2})?|\.html?|/deed\.[a-z]{2}|/)+$", "", s)
    return s


_D = re.compile(r"(-nc\b|_nc\b|-nc-|_nc_|bync|by-nc|-nd\b|_nd\b|-nd-|bynd|by-nd|other-closed|\bclosed\b|restricted|dl-de-by-nc|dl-by-nc)")
_C = re.compile(r"(-sa\b|_sa\b|-sa-|bysa|by-sa|odbl|iodl/1\.0|iodl_1_0|iodl-1\.0)")
_A = re.compile(
    r"(\bcc0\b|cc-zero|cc_zero|publicdomain/zero|cc-by-4\.0|cc_by_4_0|cc-by/4\.0|licenses/by/4\.0|cc-by_4\.0)"
)
_B = re.compile(
    r"(publicdomain/mark|pddl|odc-by|odc_by|dl-de-zero|dl-zero-de|dl_de_zero|dl-de-by-2\.0|dl-by-de/2\.0|"
    r"dl_de_by_2_0|dl-de-by|etalab|licence-ouverte|lo_ol|lo-2\.0|lov2|licence_ouverte|iodl/2\.0|iodl_2_0|"
    r"iodl-2\.0|modellicentie-gratis-hergebruik|gratis-hergebruik|otvorena-dozvola|otvorena_dozvola|"
    r"cc-by/3\.0|cc-by-3\.0|licenses/by/3\.0|licenses/by/2\.5|licenses/by/2\.0|cc_by_3_0|cc-by_3\.0|"
    r"com_reuse|2011/833)"
)
_CZ_TERMS = re.compile(r"ofn/podminky-uziti|podminky-uziti")
# Post-hoc additions (METHOD.md §9, deviation D1): used only when strict=False (sensitivity analysis
# and the hvd-lint tool). They cover spellings of class A/B licences that the frozen list missed.
_A2 = re.compile(r"(cc-by-4-0|namensnennung-4-0|cc_by_4\.0)")
_B2 = re.compile(r"(cc-by-de/3\.0|dl-de/zero-2-0|dl-de/by-2-0|opendefinition\.org/licenses/cc-by|"
                 r"(^|/)cc-by$|(^|/)cc_by$|geonutz|noconditionsapply)")
_E_GENERIC = re.compile(r"(other-open|other-at|other-pd|other-nc|notspecified|not-specified|\bunknown\b|^other$)")


def _fold(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def licence_class(v: str | None, context: list[str] | None = None, strict: bool = True,
                  catch_all_as_e: bool = False) -> str:
    """Class A/B/C/D/E/N for one licence value (METHOD.md §5). `context` = other licence or
    rights values of the same record (e.g. what a Czech terms-of-use node points to).
    strict=True applies the rules exactly as frozen; strict=False adds deviation D1."""
    if v is None or str(v).strip() == "":
        return "N"
    s = normalise_licence(v)
    if not strict:
        s = _fold(s)
    if catch_all_as_e and (s.endswith("licenses/other-closed") or s == "other-closed"):
        # DCAT-AP.de catch-all "other closed licence"; the European portal types it adms UnknownIPR
        # (review M2). Used by hvd_check and the sensitivity analysis, not by the frozen rules.
        return "E"
    if _D.search(s):
        return "D"
    if _C.search(s):
        return "C"
    if _A.search(s) or (not strict and _A2.search(s)):
        return "A"
    if not strict and _B2.search(s):
        return "B"
    if _CZ_TERMS.search(s):
        ctx = [normalise_licence(c) for c in (context or [])]
        if not ctx:
            return "E"
        sub = [licence_class(c, strict=strict) for c in ctx]
        if any(x in ("C", "D") for x in sub):
            return max(sub, key="CD".find)
        return "B" if all(x in ("A", "B") for x in sub) else "E"
    if _B.search(s):
        return "B"
    return "E"


def dataset_licence_verdict(dist_classes: list[str]) -> str:
    """'pass' if every distribution is A/B; 'none' if all are N (or no distribution);
    'fail' if any is C/D; 'unclear' otherwise (some E, or a mix with N)."""
    if not dist_classes or all(c == "N" for c in dist_classes):
        return "none"
    if all(c in ("A", "B") for c in dist_classes):
        return "pass"
    if any(c in ("C", "D") for c in dist_classes):
        return "fail"
    return "unclear"


# ---- API signal (METHOD.md §6) ------------------------------------------------------------

_API_FORMATS = {
    "wms", "wfs", "wcs", "wmts", "wms_srvc", "wfs_srvc", "csw", "sos", "ogc api", "api", "rest",
    "sparql", "json_ld api",
}
_API_URL = re.compile(
    r"(service=(wms|wfs|wcs|wmts|csw|sos)\b|getcapabilities|/wms\b|/wfs\b|/wcs\b|/wmts\b|/ogc/|/ogcapi|"
    r"/collections\b|/api/|/api\?|/sparql|/rest/|/services/|arcgis/rest|mapserver|/odata)",
    re.I,
)


def inferable_api(fmt: str | None, urls: list[str]) -> bool:
    f = (fmt or "").strip().lower()
    if f in _API_FORMATS:
        return True
    if f.endswith("/wms_srvc") or f.endswith("/wfs_srvc"):
        return True
    return any(_API_URL.search(u or "") for u in urls)


_OGC = re.compile(r"(service=(wms|wfs|wcs|wmts)\b|/wms\b|/wfs\b|/wcs\b|/wmts\b)", re.I)


def is_ogc_service(url: str) -> bool:
    return bool(_OGC.search(url or ""))


def getcapabilities_url(url: str) -> str:
    """Turn an OGC service URL into a GetCapabilities request (METHOD.md §7)."""
    low = url.lower()
    if "request=getcapabilities" in low:
        return url
    m = re.search(r"service=(wms|wfs|wcs|wmts)", low)
    svc = m.group(1).upper() if m else next(
        (s.upper() for s in ("wmts", "wms", "wfs", "wcs") if re.search(rf"/{s}\b", low)), "WMS")
    base = re.sub(r"(?i)([?&])request=[^&]*&?", r"\1", url).rstrip("?&")
    sep = "&" if "?" in base else "?"
    if "service=" in base.lower():
        return f"{base}{sep}REQUEST=GetCapabilities"
    return f"{base}{sep}SERVICE={svc}&REQUEST=GetCapabilities"
