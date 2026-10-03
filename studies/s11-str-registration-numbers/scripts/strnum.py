"""strnum: parse and normalise the short-term-rental registration numbers shown on listings.

Reusable module of EasyxLab study S11 (Apache-2.0). Standard library only.

Two layers:

1. ``split_license(raw)`` splits the free-text licence field as Inside Airbnb publishes it
   (Airbnb's labelled blocks "Spain - National registration number<br />…<br /><br />
   Barcelona - Regional registration number<br />…", or an unlabelled value as in New York)
   into a national part, a regional part and their "Exempt" statements.
2. ``parse_regional(value, region)`` and ``parse_national(value)`` turn one value into a
   ``Parsed`` record with a status:

   - ``ok``          well-formed for the region; ``key`` is the canonical form used to match
                     the registry, ``kind`` the establishment type the prefix denotes;
   - ``placeholder`` well-formed shape but a dummy number (all zeros, e.g. "VT-0");
   - ``malformed``   something is there but it is not a number in any format we know
                     for the region (free text, a tax id, a number from another region…);
   - ``exempt``      an "Exempt …" statement instead of a number;
   - ``empty``       nothing.

Formats (see METHOD.md for the legal sources and the evidence behind each mapping):

- Catalonia (Registre de Turisme de Catalunya): ``<PREFIX>-<6 digits>``; the prefix gives the
  type and the province (HUTB = habitatge d'ús turístic, Barcelona; HUTG Girona, HUTT
  Tarragona, HUTL Lleida, HUTCC, HUTTE, HUTVA for the later territorial codes; HB/HG… hotels;
  PB/PG… rural tourism; LLB/LLG… llars compartides; ATB… apartments; KB… campsites). A trailing
  "-NN" is read as the RTC control digit and kept apart.
- Comunitat Valenciana (Registro de Turismo de la Comunitat Valenciana, viviendas turísticas):
  current ``CV-VUT<7 digits>-<V|A|CS>``; the older ``VT-<digits>-<V|A|CS>`` is mapped to the
  current form by zero-padding the digits (an assumption tested empirically, METHOD.md).
- Andalucía (Registro de Turismo de Andalucía): ``<TYPE>/<prov>/<digits>``; VFT (viviendas con
  fines turísticos, the term of Decreto 28/2016) and VUT (viviendas de uso turístico, the label
  the open registry now uses for all of them) are matched as the same series, an equivalence
  supported by the data (METHOD.md §6); "VTF" is accepted as a transposition of VFT.
- Comunidad de Madrid: ``VT-<digits>`` (viviendas de uso turístico); AM/HM/TR… other types.
  There is no open registry we may download, so only the format is checked.
- New York City (Local Law 18): ``OSE-STRREG-<7 digits>``.
- Spain's national number (Real Decreto 1312/2024, annulled in this respect by the Supreme
  Court in May–June 2026): 53 characters beginning ``ES`` + FC|HF + TU|NT; TU = tourist,
  NT = non-tourist (as designated by the host).
"""
import re
import unicodedata
from dataclasses import dataclass, field

__all__ = ["Parsed", "split_license", "parse_regional", "parse_national", "norm_text",
           "CAT_PREFIXES", "REGIONS"]

REGIONS = ("catalonia", "valencia", "andalucia", "madrid", "nyc")


@dataclass
class Parsed:
    status: str                 # ok | placeholder | malformed | exempt | empty
    key: str = ""               # canonical matching key (status ok/placeholder)
    kind: str = ""              # establishment type denoted by the prefix
    tourist_dwelling: bool = False   # the number is of the tourist-dwelling series
    registry_open: bool = False      # an open registry exists for this kind (S11's sources)
    province: str = ""          # province code read from the number, if any
    extra: str = ""             # e.g. Catalan control digit, Valencian old-format flag
    note: str = ""
    raw: str = ""


def norm_text(s):
    """Upper-case, strip accents, unify dashes and spaces."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("–", "-").replace("—", "-").replace("‐", "-").replace("‑", "-")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip().upper()


# ---------------------------------------------------------------- licence field splitting

_LABEL = re.compile(r"^(?P<who>.+?)\s*-\s*(?P<lvl>National|Regional) registration number$", re.I)


def split_license(raw):
    """Split Inside Airbnb's ``license`` field.

    Returns a dict with keys: national, regional, regional_label, unlabelled (list), and
    labelled (bool). Values are stripped strings or None."""
    out = {"national": None, "regional": None, "regional_label": None, "unlabelled": [], "labelled": False}
    raw = (raw or "").strip()
    if not raw:
        return out
    for seg in re.split(r"(?:<br\s*/?>\s*){2,}", raw):
        parts = re.split(r"<br\s*/?>", seg, maxsplit=1)
        m = _LABEL.match(parts[0].strip()) if len(parts) == 2 else None
        if m:
            out["labelled"] = True
            val = parts[1].strip()
            if m.group("lvl").lower() == "national":
                out["national"] = val
            else:
                out["regional"] = val
                out["regional_label"] = m.group("who").strip()
        else:
            v = re.sub(r"<br\s*/?>", " ", seg).strip()
            if v:
                out["unlabelled"].append(v)
    return out


def is_exempt(v):
    return bool(re.match(r"^\s*exempt\b", v or "", re.I))


def exempt_reason(v):
    """'Exempt - seasonal rental' -> 'seasonal rental'; bare 'Exempt' -> 'unspecified'."""
    m = re.match(r"^\s*exempt\s*(?:-\s*(.*))?$", v or "", re.I | re.S)
    r = (m.group(1) or "").strip().lower() if m else ""
    return r or "unspecified"


# ---------------------------------------------------------------- national number

_NAT = re.compile(r"^ES(FC|HF)(TU|NT)")


def parse_national(value):
    v = norm_text(value).replace(" ", "")
    if not v:
        return Parsed("empty", raw=value or "")
    if is_exempt(value):
        return Parsed("exempt", note=exempt_reason(value), raw=value)
    m = _NAT.match(v)
    if m and len(v) == 53:
        return Parsed("ok", key=v, kind="national-" + m.group(2), raw=value,
                      extra=m.group(1))
    if v.startswith("ES") and len(v) >= 20:
        return Parsed("ok", key=v, kind="national-other", raw=value,
                      note="ES prefix but not ES(FC|HF)(TU|NT) of 53 characters")
    return Parsed("malformed", raw=value)


def looks_national(v):
    return bool(re.match(r"^ES[A-Z]{4}\d", norm_text(v).replace(" ", "")))


# ---------------------------------------------------------------- Catalonia

# prefixes present in the Registre de Turisme de Catalunya (open data), by type
CAT_PREFIXES = {
    "HUT": "tourist dwelling", "HB": "hotel", "HG": "hotel", "HT": "hotel", "HL": "hotel",
    "HCC": "hotel", "HTE": "hotel", "HVA": "hotel",
    "PB": "rural tourism", "PG": "rural tourism", "PT": "rural tourism", "PL": "rural tourism",
    "PCC": "rural tourism", "PTE": "rural tourism", "PVA": "rural tourism",
    "LLB": "shared home", "LLG": "shared home", "LLT": "shared home", "LLL": "shared home",
    "LLCC": "shared home", "LLTE": "shared home", "LLVA": "shared home",
    "ATB": "tourist apartments", "ATG": "tourist apartments", "ATT": "tourist apartments",
    "ATL": "tourist apartments", "ATCC": "tourist apartments", "ATTE": "tourist apartments",
    "ATVA": "tourist apartments",
    "KB": "campsite", "KG": "campsite", "KT": "campsite", "KL": "campsite", "KCC": "campsite",
    "KTE": "campsite", "KVA": "campsite", "AAG": "motorhome area", "AAL": "motorhome area",
    "AAT": "motorhome area",
}
CAT_HUT_PROV = ("B", "G", "T", "L", "CC", "TE", "VA")
# Catalan series that exist but are not in the RTC open data (youth hostels: Registre d'albergs)
CAT_OTHER = {"AJ": "youth hostel", "HU": "tourist dwelling (old municipal code)"}

_CAT = re.compile(r"^(?P<p>[A-Z]{1,5})\s*[-_./ ]?\s*(?P<n>\d{1,8})(?:\s*[-/ ]\s*(?P<c>\d{1,2}))?$")


def _cat(v, raw):
    m = _CAT.match(v)
    if not m:
        return Parsed("malformed", raw=raw)
    p, n, c = m.group("p"), m.group("n"), m.group("c") or ""
    if not c and len(n) == 8 and (p.startswith("HUT") or p in CAT_PREFIXES):
        n, c = n[:6], n[6:]          # number and control digit written without separator
    if len(n.lstrip("0")) > 6:
        return Parsed("malformed", raw=raw, note="more than 6 significant digits")
    if p.startswith("HUT") and p[3:] in CAT_HUT_PROV:
        kind, prov = "tourist dwelling", p[3:]
    elif p in CAT_PREFIXES:
        kind, prov = CAT_PREFIXES[p], ""
    elif p in CAT_OTHER:
        num = int(n)
        return Parsed("placeholder" if num == 0 else "ok", key=f"{p}-{num:06d}", kind=CAT_OTHER[p],
                      registry_open=False, raw=raw, extra=c)
    else:
        return Parsed("malformed", raw=raw, note=f"unknown prefix {p}")
    num = int(n)
    st = "placeholder" if num == 0 else "ok"
    return Parsed(st, key=f"{p}-{num:06d}", kind=kind, tourist_dwelling=(kind == "tourist dwelling"),
                  registry_open=True, province=prov, extra=c, raw=raw)


# ---------------------------------------------------------------- Comunitat Valenciana

_VAL_NEW = re.compile(r"^CV\s*-?\s*VUT\s*-?\s*(?P<n>\d{1,8})\s*-?\s*(?P<p>V|A|CS|C)$")
_VAL_VAR = re.compile(r"^(?:VUT|CV-?VT)\s*-?\s*(?P<n>\d{1,8})\s*-?\s*(?P<p>V|A|CS|C)$")
_VAL_OLD = re.compile(r"^VT\s*-?\s*(?P<n>\d{1,8})\s*-?\s*(?P<p>V|A|CS|C)$")
_VAL_OTHER = re.compile(r"^(?P<t>HV|HA|HCS|AT|AV|ACS|ARU|CV-?HV|CV-?H|CV-?AT|CV-?AP|CV-?ARU|AP|CR|CV-?CR)\s*-?\s*(?P<n>\d{1,8})(?:\s*-?\s*(V|A|CS|C))?$")


def _val(v, raw):
    v2 = v.replace(" ", "")
    for rx, old in ((_VAL_NEW, False), (_VAL_OLD, True), (_VAL_VAR, None)):
        m = rx.match(v2)
        if m:
            num = int(m.group("n"))
            prov = "CS" if m.group("p") in ("CS", "C") else m.group("p")
            if len(str(num)) > 7:
                return Parsed("malformed", raw=raw, note="more than 7 digits")
            st = "placeholder" if num == 0 else "ok"
            return Parsed(st, key=f"CV-VUT{num:07d}-{prov}", kind="tourist dwelling", tourist_dwelling=True,
                          registry_open=True, province=prov,
                          extra={True: "old-format", False: "", None: "variant"}[old], raw=raw)
    m = _VAL_OTHER.match(v2)
    if m:
        t = m.group("t").replace("CV-", "").replace("CV", "")
        kind = {"H": "hotel", "HV": "hotel", "HA": "hotel", "HCS": "hotel", "AT": "tourist apartments", "AP": "tourist apartments",
                "AV": "tourist apartments", "ACS": "tourist apartments", "CR": "rural", "ARU": "rural"}.get(t, "other")
        num = int(m.group("n"))
        return Parsed("placeholder" if num == 0 else "ok", key=f"{t}-{num}", kind=kind, registry_open=False, raw=raw)
    return Parsed("malformed", raw=raw)


# ---------------------------------------------------------------- Andalucía

_AND_PROV = ("AL", "CA", "CO", "GR", "HU", "JA", "MA", "SE")
_AND = re.compile(r"^(?P<t>VFT|VUT|VTF|VFU|VTAR|A|H|HS|CR|CTR|AT|P|CM|AP|HA|CT)\s*[/\-. ]?\s*(?P<p>[A-Z]{2})\s*[/\-. ]?\s*(?P<n>\d{1,6})$")
_AND_CTC = re.compile(r"^CTC\s*-?\s*(?P<n>\d{6,12})$")
_AND_KIND = {"VFT": "tourist dwelling", "VUT": "tourist dwelling", "VTF": "tourist dwelling",
             "VFU": "tourist dwelling", "VTAR": "rural tourist dwelling", "A": "tourist apartments",
             "AT": "tourist apartments", "AP": "tourist apartments", "H": "hotel", "HS": "hotel",
             "HA": "hotel", "P": "hotel", "CR": "rural house", "CTR": "rural complex",
             "CM": "campsite", "CT": "other"}
# kinds whose series appear in OpenRTA (see METHOD.md): VUT (incl. renamed VFT), VTAR, A, H, CR, CTR
_AND_SERIES = {"VFT": "VUT", "VUT": "VUT", "VTF": "VUT", "VFU": "VUT", "VTAR": "VTAR", "A": "A",
               "AT": "A", "H": "H", "HS": "H", "CR": "CR", "CTR": "CTR"}


def _and(v, raw):
    m = _AND.match(v.replace(" ", "") if "/" in v or "-" in v else v)
    if not m:
        c = _AND_CTC.match(v.replace(" ", ""))
        if c:
            return Parsed("ok", key="CTC-" + c.group("n"), kind="CTC code", registry_open=False, raw=raw)
        return Parsed("malformed", raw=raw)
    t, p, n = m.group("t"), m.group("p"), int(m.group("n"))
    if p not in _AND_PROV:
        return Parsed("malformed", raw=raw, note=f"province {p} is not Andalusian")
    series = _AND_SERIES.get(t)
    kind = _AND_KIND.get(t, "other")
    st = "placeholder" if n == 0 else "ok"
    return Parsed(st, key=f"{series or t}/{p}/{n}", kind=kind, tourist_dwelling=(series == "VUT"),
                  registry_open=series is not None, province=p,
                  extra=("renamed-VFT" if t in ("VFT", "VTF", "VFU") else ""), raw=raw)


# ---------------------------------------------------------------- Comunidad de Madrid

_MAD = re.compile(r"^(?P<t>VT|VUT|AM|HM|HSM|HSRM|TR|AT|CR|AR|HR|H|PM)\s*[-_./ ]?\s*(?P<n>\d{1,6})$")
_MAD_KIND = {"VT": "tourist dwelling", "VUT": "tourist dwelling", "AM": "tourist apartments",
             "AT": "tourist apartments", "HM": "hotel", "HSM": "hotel", "HSRM": "hotel", "H": "hotel",
             "HR": "hotel", "PM": "hotel", "TR": "rural tourism", "CR": "rural tourism", "AR": "rural tourism"}


def _mad(v, raw):
    m = _MAD.match(v)
    if not m:
        return Parsed("malformed", raw=raw)
    t, n = m.group("t"), int(m.group("n"))
    kind = _MAD_KIND[t]
    tag = "VT" if t in ("VT", "VUT") else t
    return Parsed("placeholder" if n == 0 else "ok", key=f"{tag}-{n}", kind=kind,
                  tourist_dwelling=(kind == "tourist dwelling"), registry_open=False, raw=raw)


# ---------------------------------------------------------------- New York City

_NYC = re.compile(r"^OSE\s*-?\s*STRREG\s*-?\s*(?P<n>\d{1,7})$")


def _nyc(v, raw):
    m = _NYC.match(v.replace(" ", ""))
    if not m:
        return Parsed("malformed", raw=raw)
    n = int(m.group("n"))
    return Parsed("placeholder" if n == 0 else "ok", key=f"OSE-STRREG-{n:07d}", kind="registration",
                  tourist_dwelling=True, registry_open=True, raw=raw)


_PARSERS = {"catalonia": _cat, "valencia": _val, "andalucia": _and, "madrid": _mad, "nyc": _nyc}


def parse_regional(value, region):
    """Parse one regional (or, in NYC, the only) licence value for ``region``."""
    if region not in _PARSERS:
        raise ValueError(f"unknown region {region}")
    raw = value or ""
    if not raw.strip():
        return Parsed("empty", raw=raw)
    if is_exempt(raw):
        return Parsed("exempt", note=exempt_reason(raw), raw=raw)
    v = norm_text(raw)
    # strip common decorations: "Nº", "N.º", "Licencia:", "Registro", trailing dots
    v = re.sub(r"^(N\s*[.ºO°]*\s*|NUM(ERO)?\.?\s*|LICEN[CS]IA\s*:?\s*|REGISTRO\s*:?\s*|REG\.?\s*:?\s*)", "", v)
    v = v.strip(" .:;,")
    # several numbers in one field: parse the first and say so
    parts = re.split(r"\s*(?:,|;| Y | AND )\s*", v)
    p = _PARSERS[region](parts[0], raw)
    if len(parts) > 1 and p.status == "ok":
        p.note = (p.note + "; " if p.note else "") + "several values; first used"
    return p
