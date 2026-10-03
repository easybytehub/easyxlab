"""netex-lint core: streaming consistency checks for NeTEx datasets.

Every rule here is derived from open sources only:
  * the open NeTEx XSD (GPL-3.0, github.com/TransmodelEcosystem/NeTEx) for structure,
  * W3C XML 1.0 for encoding,
  * the open text of national profiles (Nordic NeTEx Profile by Entur; Profil NeTEx France
    on normes.transport.data.gouv.fr), quoted in RULES.md,
  * Delegated Regulation (EU) 2017/1926 as amended by (EU) 2024/490, Art. 6 (data updates).
No rule is taken from the paid CEN specification of EPIP.
"""
import gzip
import io
import re
import zipfile
from collections import Counter, defaultdict

from lxml import etree

NS = "http://www.netex.org.uk/netex"
MOJIBAKE = re.compile(r"Ã[\u0080-¿]|Â[\u0080-¿]|â€[\u0099\u009c\u009d\u0093\u0094™œ]")
REPLACEMENT = re.compile("\ufffd")
VALIDITY_CONTAINERS = {"ValidBetween", "AvailabilityCondition"}
# short open source per rule; full quotes in RULES.md
SOURCES = {
    "REF-UNRESOLVED-VERSIONED": "NeTEx XSD keyrefs on (@ref, @version); Nordic profile 'Versioning in references'; Profil NeTEx France VersionOfObjectRef",
    "REF-VERSION-MISMATCH": "NeTEx XSD keys on (@id, @version)",
    "ID-DUPLICATE-IN-FILE": "NeTEx XSD *_AnyVersionedKey identity constraints",
    "ID-REDUNDANT-ACROSS-FILES": "Nordic profile, General information (common file 'to avoid redundancy of unique objects')",
    "VALIDITY-EXPIRED": "Delegated Regulation (EU) 2017/1926 as amended, Art. 6(1)",
    "CALENDAR-IN-PAST": "Delegated Regulation (EU) 2017/1926 as amended, Art. 6(1)",
    "ENCODING-NOT-UTF8": "W3C XML 1.0 §4.3.3",
    "ENCODING-NO-DECLARATION": "W3C XML 1.0 §4.3.3 (no declaration = UTF-8/UTF-16)",
    "ENCODING-BOM": "W3C XML 1.0 §4.3.3",
    "ENCODING-MOJIBAKE": "heuristic (double-encoded UTF-8)",
    "ENCODING-REPLACEMENT-CHAR": "heuristic (U+FFFD = character lost before publication)",
    "VERSION-MISSING": "NeTEx XSD (attribute optional); reported as a fact",
    "XML-NOT-WELL-FORMED": "W3C XML 1.0",
    "NORDIC-ID-FORMAT": "Nordic NeTEx Profile, General information, 'Structure of ID's'",
    "NORDIC-ID-TYPE": "Nordic NeTEx Profile, General information, 'Structure of ID's'",
    "NORDIC-REF-UNVERSIONED-INTERNAL": "Nordic NeTEx Profile, General information, 'Versioning in references'",
    "FR-ID-NOT-PROPOSED-FORMAT": "Profil NeTEx France, Éléments communs (codification 'proposée'; other structures allowed)",
    "FR-ID-TYPE-NOT-TAG": "Profil NeTEx France, Éléments communs (codification 'proposée')",
    "FR-REF-UNVERSIONED-INTERNAL": "Profil NeTEx France, Éléments communs, VersionOfObjectRef",
}
DATE_PARENTS_VALIDITY = {"ValidBetween", "AvailabilityCondition"}
DATE_PARENTS_CALENDAR = {"OperatingPeriod", "UicOperatingPeriod", "ServiceCalendar"}
COUNTED = ("ServiceJourney", "Line", "StopPlace", "Quay", "ScheduledStopPoint", "Route",
           "JourneyPattern", "ServiceJourneyPattern", "DayType", "Operator", "Authority")
FR_ID = re.compile(r"^[^:\s]+:[A-Za-z][A-Za-z0-9]*:[^:\s]+:[^:\s]*$")
# Profil NeTEx France, "Codification des identifiants d'arrêt" (form "actuellement envisagée"):
# [Code PAYS]:[Code commune INSEE]:[ZE|LMO|PM|LMU|AC]:[Code arrêt spécifique]:[Code émetteur ou LOC]
FR_STOP_ID = re.compile(r"^[A-Z]{2}:[0-9AB]{5}(-[0-9]{1,2})?:(ZE|LMO|PM|LMU|AC):[^:\s]+:[^:\s]*$")
NORDIC_ID = re.compile(r"^[A-Z]{3}:[A-Za-z]+:[0-9A-Za-z_-]+$")
# Nordic stop-registry objects are shared from the central registry (NSR) and keep its ids
NORDIC_ID_EXEMPT_PREFIX = ("NSR:",)
# declared once per XML document by design (each document lists the codespaces it uses)
PER_DOCUMENT = {"Codespace"}
# packaging objects that one-file-per-line exports legitimately repeat in every document
PACKAGING = {"ValueSet", "DataSource", "ResponsibilitySet", "Codespace"}


def is_packaging(tag):
    return tag in PACKAGING or tag.endswith("Frame") or tag.startswith("TypeOf")


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def iter_members(path, max_bytes=None):
    """Yield (member_name, uncompressed_size_or_None, opener) for each XML document."""
    with open(path, "rb") as fh:
        head = fh.read(4)
    if head[:2] == b"PK":
        zf = zipfile.ZipFile(path)
        for zi in zf.infolist():
            if zi.is_dir() or not zi.filename.lower().endswith(".xml"):
                continue
            yield zi.filename, zi.file_size, (lambda zi=zi: zf.open(zi))
    elif head[:2] == b"\x1f\x8b":
        with open(path, "rb") as fh:          # ISIZE trailer = uncompressed size mod 2^32
            fh.seek(-4, 2); isize = int.from_bytes(fh.read(4), "little")
        yield path.rsplit("/", 1)[-1], isize, (lambda: gzip.open(path, "rb"))
    else:
        import os
        yield path.rsplit("/", 1)[-1], os.path.getsize(path), (lambda: open(path, "rb"))


def sniff_prolog(fobj):
    """Return (has_bom, declared_encoding) from the first bytes of a document."""
    first = fobj.read(256)
    bom = first.startswith(b"\xef\xbb\xbf")
    m = re.search(rb"<\?xml[^>]*encoding=[\"']([A-Za-z0-9._-]+)[\"']", first)
    return bom, (m.group(1).decode().upper() if m else None)


class MemberScan:
    def __init__(self, name):
        self.name = name
        self.ids = defaultdict(set)          # id -> set(version)
        self.defs = Counter()                # (tag, id, version) -> count
        self.refs = []                       # (tag, ref, version|None, versionRef|None)
        self.root_tag = None
        self.root_version = None
        self.participant = None
        self.codespaces = set()
        self.type_of_frame = Counter()
        self.validity_to = []                # ToDate of ValidBetween/AvailabilityCondition
        self.validity_from = []
        self.calendar_dates = []             # OperatingDay/CalendarDate + period ends
        self.counts = Counter()
        self.mojibake = 0
        self.replacement = 0
        self.replacement_examples = []
        self.validity_open = 0               # ValidBetween/AvailabilityCondition without ToDate
        self.frame_validity_to = []          # ToDate of validity conditions attached to a *Frame
        self.frame_validity_open = 0
        self.mojibake_examples = []
        self.bom = False
        self.encoding_decl = None
        self.parse_error = None


def scan_member(name, opener):
    """Single streaming pass over one XML document; memory stays bounded."""
    s = MemberScan(name)
    with opener() as f:
        s.bom, s.encoding_decl = sniff_prolog(f)
    stack = []
    vstack = []                              # one flag per open ValidBetween: has it a ToDate?
    try:
        with opener() as f:
            for ev, el in etree.iterparse(f, events=("start", "end"), huge_tree=True,
                                          resolve_entities=False, no_network=True):
                tag = local(el.tag)
                if ev == "start":
                    if s.root_tag is None:
                        s.root_tag, s.root_version = tag, el.get("version")
                    a = el.attrib
                    if "id" in a and not tag.endswith("Ref"):
                        s.ids[a["id"]].add(a.get("version"))
                        s.defs[(tag, a["id"], a.get("version"))] += 1
                    if tag.endswith("Ref") and "ref" in a:
                        s.refs.append((tag, a["ref"], a.get("version"), a.get("versionRef")))
                        if tag == "TypeOfFrameRef":
                            s.type_of_frame[a["ref"]] += 1
                    if tag in COUNTED:
                        s.counts[tag] += 1
                    if tag in VALIDITY_CONTAINERS:
                        vstack.append(False)
                    stack.append(tag)
                    continue
                stack.pop()
                parent = stack[-1] if stack else ""
                if tag in VALIDITY_CONTAINERS and vstack:
                    closed = vstack.pop()
                    at_frame = len(stack) >= 2 and stack[-1] == "validityConditions" and stack[-2].endswith("Frame")
                    if not closed:
                        s.validity_open += 1
                        if at_frame:
                            s.frame_validity_open += 1
                    elif at_frame and s.validity_to:
                        s.frame_validity_to.append(s.validity_to[-1])
                elif tag == "ToDate" and parent in VALIDITY_CONTAINERS and vstack:
                    vstack[-1] = True
                txt = el.text
                if txt and txt.strip():
                    t = txt.strip()
                    if tag in ("FromDate", "ToDate") and parent in DATE_PARENTS_VALIDITY:
                        (s.validity_to if tag == "ToDate" else s.validity_from).append(t[:10])
                    elif tag == "ToDate" and parent in DATE_PARENTS_CALENDAR:
                        s.calendar_dates.append(t[:10])
                    elif tag == "CalendarDate" and parent == "OperatingDay":
                        s.calendar_dates.append(t[:10])
                    elif tag == "ParticipantRef":
                        s.participant = t
                    elif tag == "Xmlns" and parent == "Codespace":
                        s.codespaces.add(t)
                    if MOJIBAKE.search(t):
                        s.mojibake += 1
                        if len(s.mojibake_examples) < 3:
                            s.mojibake_examples.append(t[:80])
                    if REPLACEMENT.search(t):
                        s.replacement += 1
                        if len(s.replacement_examples) < 3:
                            s.replacement_examples.append(t[:80])
                for v in el.attrib.values():
                    if MOJIBAKE.search(v):
                        s.mojibake += 1
                    if REPLACEMENT.search(v):
                        s.replacement += 1
                el.clear(keep_tail=False)
                if len(stack) > 1:
                    while el.getprevious() is not None:
                        del el.getparent()[0]
    except etree.XMLSyntaxError as e:
        s.parse_error = str(e)[:300]
    return s


def codespace_of(identifier):
    return identifier.split(":", 1)[0] if ":" in identifier else ""


def detect_profile(scans):
    sig = " ".join(filter(None, [x.root_version or "" for x in scans] + list(
        k for x in scans for k in x.type_of_frame)))
    if re.search(r"FR[1-9]?[-_:]|NETEX_FRANCE|FR-NETEX|NETEX_LIGNE|NETEX_ARRET|NETEX_COMMUN", sig):
        return "fr"
    if re.search(r"NO-NeTEx|NO_NeTEx|RBV:TypeOfFrame|EU_PI_LINE_OFFER.*NO", sig) or re.search(r"\bNO-", sig):
        return "nordic"
    if re.search(r"EU_PI_|epip", sig, re.I):
        return "epip"
    if re.search(r"NL:BISON|^ntx:|\bntx:", sig):
        return "nl"
    return "unknown"


def check_dataset(scans, today, profile="auto"):
    """Dataset-level rules over all member scans. Returns (summary dict, findings list)."""
    if profile == "auto":
        profile = detect_profile(scans)
    ids = defaultdict(set)
    for s in scans:
        for k, v in s.ids.items():
            ids[k] |= v
    own_cs = set()
    for s in scans:
        own_cs |= {codespace_of(i) for i in s.ids}
    findings = []
    unresolved = Counter(); unresolved_versioned = Counter(); version_mismatch = Counter()
    unresolved_same_cs = 0; n_refs = 0; internal_unversioned = 0; internal_refs = 0; profile_types = 0; internal_unversioned_ds = 0; typeof_versioned = 0
    examples = defaultdict(list)
    for s in scans:
        for tag, ref, ver, vref in s.refs:
            n_refs += 1
            versioned = ver not in (None, "any")
            if ref in ids:
                internal_refs += 1
                if ver is None and vref is None:
                    internal_unversioned_ds += 1
                    if len(examples["fr_unversioned"]) < 5:
                        examples["fr_unversioned"].append(f"{s.name}: <{tag} ref=\"{ref}\"/> (defined in the dataset)")
                if ver is None and ref in s.ids:   # Nordic rule is about the same XML file
                    internal_unversioned += 1
                if versioned and ver not in ids[ref] and "any" not in ids[ref] and None not in ids[ref]:
                    version_mismatch[tag] += 1
                    if len(examples["version_mismatch"]) < 5:
                        examples["version_mismatch"].append(f"{tag} {ref} v{ver} (defined: {sorted(map(str, ids[ref]))[:3]})")
                continue
            unresolved[tag] += 1
            if codespace_of(ref) in own_cs:
                unresolved_same_cs += 1
            if tag.startswith("TypeOf"):
                # TypeOfFrame/TypeOfService... values are usually defined by the profile, not the dataset
                profile_types += 1
                if versioned:
                    typeof_versioned += 1
                continue
            if versioned:
                unresolved_versioned[tag] += 1
                if len(examples["unresolved_versioned"]) < 5:
                    examples["unresolved_versioned"].append(f"{tag} ref={ref} version={ver}")
    dup = Counter(); dup_in_file = Counter()
    defs = Counter(); files_of = Counter()
    for s in scans:
        defs.update(s.defs)
        files_of.update(s.defs.keys())
        for (tag, i, v), c in s.defs.items():
            if c > 1 and tag not in PER_DOCUMENT:
                dup_in_file[tag] += c - 1
                if len(examples["duplicate_in_file"]) < 5:
                    examples["duplicate_in_file"].append(f"{s.name}: {tag} id={i} version={v} x{c}")
    for (tag, i, v), n in files_of.items():
        if n > 1 and not is_packaging(tag):
            dup[tag] += n - 1
            if len(examples["duplicate_definition"]) < 5:
                examples["duplicate_definition"].append(f"{tag} id={i} version={v} in {n} files")
    vt = sorted(d for s in scans for d in s.validity_to)
    vf = sorted(d for s in scans for d in s.validity_from)
    cal = sorted(d for s in scans for d in s.calendar_dates)
    enc = Counter((s.encoding_decl or "NONE") for s in scans)
    bom = sum(s.bom for s in scans)
    moj = sum(s.mojibake for s in scans)
    roots = Counter(s.root_tag for s in scans)
    versions = Counter(s.root_version for s in scans)
    tof = Counter()
    for s in scans:
        tof.update(s.type_of_frame)
    counts = Counter()
    for s in scans:
        counts.update(s.counts)

    def add(rule, severity, n, msg, ex=None):
        if n:
            findings.append({"rule": rule, "severity": severity, "count": n, "message": msg,
                             "examples": (ex or [])[:5], "source": SOURCES.get(rule, "")})

    add("REF-UNRESOLVED-VERSIONED", "error", sum(unresolved_versioned.values()),
        "Reference carries a version (not 'any') but no object with that id exists in the dataset; "
        "under the Nordic and French profiles a versioned reference points inside the dataset. "
        "TypeOf...Ref (profile-defined types) and version='any' are not counted here.",
        examples["unresolved_versioned"])
    add("REF-VERSION-MISMATCH", "warning", sum(version_mismatch.values()),
        "Referenced id exists, but not in the version the reference asks for.", examples["version_mismatch"])
    add("ID-DUPLICATE-IN-FILE", "error", sum(dup_in_file.values()),
        "Same element, id and version defined twice in one document (the NeTEx XSD keys forbid it).",
        examples["duplicate_in_file"])
    add("ID-REDUNDANT-ACROSS-FILES", "info", sum(dup.values()),
        "Same object (not a frame or packaging object) defined in several documents of the dataset; "
        "consumers must deduplicate (the Nordic profile puts shared objects in one common file).",
        examples["duplicate_definition"])
    vopen = sum(s.validity_open for s in scans)
    fvt = sorted(d for s in scans for d in s.frame_validity_to)
    fopen = sum(s.frame_validity_open for s in scans)
    if fvt or fopen:   # frame-level validity decides: it is what the publisher declares for the delivery
        if fopen == 0 and fvt[-1] < today:
            add("VALIDITY-EXPIRED", "error", 1, f"Every frame-level validity condition has ended; the latest ends {fvt[-1]}, before {today}.")
    elif vt and max(vt) < today and vopen == 0:   # object level: an open-ended validity never expires
        add("VALIDITY-EXPIRED", "error", 1, f"Every ValidBetween/AvailabilityCondition has a ToDate and the latest is {max(vt)}, before {today}.")
    if cal and max(cal) < today:
        add("CALENDAR-IN-PAST", "error", 1, f"Latest operating date in the calendar is {max(cal)}, before {today}.")
    non_utf8 = sum(c for e, c in enc.items() if e not in ("UTF-8", "UTF8", "NONE"))
    add("ENCODING-NOT-UTF8", "warning", non_utf8, f"Documents declaring an encoding other than UTF-8: {dict(enc)}")
    add("ENCODING-NO-DECLARATION", "info", enc.get("NONE", 0),
        "Documents without an XML declaration (read as UTF-8 by default; not an error).")
    add("ENCODING-BOM", "info", bom, "Documents starting with a UTF-8 byte-order mark.")
    add("ENCODING-MOJIBAKE", "warning", moj, "Text looks double-encoded (UTF-8 read as Latin-1).",
        [e for s in scans for e in s.mojibake_examples])
    add("ENCODING-REPLACEMENT-CHAR", "warning", sum(s.replacement for s in scans),
        "Text contains U+FFFD: a character was lost before publication.", [e for s in scans for e in s.replacement_examples])
    if any(v is None for v in versions):
        add("VERSION-MISSING", "info", versions.get(None, 0),
            "PublicationDelivery has no version attribute (optional in the XSD; reported as a fact).")
    add("XML-NOT-WELL-FORMED", "error", sum(1 for s in scans if s.parse_error),
        "Document is not well-formed XML.", [f"{s.name}: {s.parse_error}" for s in scans if s.parse_error])
    # profile-specific, open-text rules
    id_bad = 0; id_tot = 0; id_ex = []; type_bad = 0; type_ex = []
    if profile in ("fr", "nordic"):
        rx = FR_ID if profile == "fr" else NORDIC_ID
        seen = set()
        for (tag, i, _v) in defs:
            if (tag, i) in seen:
                continue
            seen.add((tag, i))
            if profile == "fr" and FR_STOP_ID.match(i):
                id_tot += 1          # valid under the stop codification; type part is ZE/LMO/...
                continue
            if tag in PER_DOCUMENT or (profile == "nordic" and i.startswith(NORDIC_ID_EXEMPT_PREFIX)):
                continue
            id_tot += 1
            if not rx.match(i):
                id_bad += 1
                if len(id_ex) < 5:
                    id_ex.append(f"{tag} id={i}")
            parts = i.split(":")
            if len(parts) >= 3 and parts[1] != tag:
                type_bad += 1
                if len(type_ex) < 5:
                    type_ex.append(f"{tag} id={i}")
        if profile == "fr":   # the French codification is "proposée"; "d'autres structures peuvent être utilisée"
            add("FR-ID-NOT-PROPOSED-FORMAT", "info", id_bad,
                f"{id_bad} of {id_tot} ids do not follow the codification the French profile proposes "
                "(other structures are allowed if ids stay unique nationally).", id_ex)
            add("FR-ID-TYPE-NOT-TAG", "info", type_bad,
                "Second part of the id is not the XML element name, as the proposed French codification suggests.", type_ex)
        else:
            add("NORDIC-ID-FORMAT", "warning", id_bad,
                f"{id_bad} of {id_tot} ids do not follow the Nordic [codespace]:[type]:[identification] structure.", id_ex)
            add("NORDIC-ID-TYPE", "warning", type_bad,
                "Second part of the id is not the NeTEx type name, as the Nordic profile requires.", type_ex)
    if profile == "fr":
        add("FR-REF-UNVERSIONED-INTERNAL", "warning", internal_unversioned_ds,
            f"Profil NeTEx France: {internal_unversioned_ds} of {internal_refs} references to objects present in the "
            "dataset carry neither 'version' nor 'versionRef' ('any' is allowed).", examples["fr_unversioned"])
    if profile == "nordic":
        add("NORDIC-REF-UNVERSIONED-INTERNAL", "warning", internal_unversioned,
            "Nordic profile: a reference to an object defined in the same PublicationDelivery must be versioned.")
    summary = {
        "profile": profile, "members": len(scans), "root_elements": dict(roots),
        "declared_versions": {str(k): v for k, v in versions.items()},
        "type_of_frame_top": dict(tof.most_common(8)), "counts": dict(counts),
        "ids": len(ids), "refs": n_refs, "refs_internal": internal_refs,
        "refs_unresolved": sum(unresolved.values()), "refs_unresolved_same_codespace": unresolved_same_cs,
        "refs_unresolved_by_tag": dict(unresolved.most_common(10)),
        "refs_unresolved_versioned": sum(unresolved_versioned.values()),
        "refs_unresolved_profile_types": profile_types,
        "refs_internal_unversioned_same_file": internal_unversioned,
        "refs_unresolved_versioned_by_tag": dict(unresolved_versioned.most_common(10)),
        "version_mismatch": sum(version_mismatch.values()),
        "duplicate_definitions": sum(dup.values()), "duplicate_in_file": sum(dup_in_file.values()),
        "validity_from_min": vf[0] if vf else None, "validity_to_max": vt[-1] if vt else None,
        "calendar_min": cal[0] if cal else None, "calendar_max": cal[-1] if cal else None,
        "encodings": dict(enc), "bom": bom, "mojibake": moj,
        "replacement_chars": sum(s.replacement for s in scans), "validity_open_ended": vopen,
        "frame_validity_to_max": fvt[-1] if fvt else None, "frame_validity_open_ended": fopen,
        "refs_unresolved_typeof_versioned": typeof_versioned,
        "id_format_checked": id_tot, "id_format_bad": id_bad, "id_type_bad": type_bad,
        "refs_internal_unversioned": internal_unversioned_ds,
        "codespaces_declared": sorted(set().union(*[s.codespaces for s in scans]))[:10],
    }
    return summary, findings


# ---------------- XSD validation (optional, needs the open NeTEx / EPIP XSD) ----------------
_NORM = [
    (re.compile(r"\{http://www\.netex\.org\.uk/netex\}"), ""),
    (re.compile(r"\{http://www\.opengis\.net/gml/3\.2\}"), "gml:"),
    (re.compile(r"Expected is.*$"), "Expected is (...)."),
    (re.compile(r"key-sequence \[[^\]]*\]"), "key-sequence [..]"),
    (re.compile(r"The value '[^']*'"), "The value '..'"),
    (re.compile(r"'[^']*' is not a valid value"), "'..' is not a valid value"),
    (re.compile(r"\[facet '([a-zA-Z]+)'\] The value '[^']*'"), r"[facet '\1'] The value '..'"),
]


def categorize(msg):
    if "No match found for key-sequence" in msg:
        return "keyref-unresolved"
    if "Duplicate key-sequence" in msg:
        return "duplicate-key"
    if "This element is not expected" in msg:
        return "unexpected-element"
    if "Missing child element" in msg:
        return "missing-child"
    if "is not a valid value" in msg or "[facet" in msg:
        return "invalid-value"
    if "attribute" in msg and "is not allowed" in msg:
        return "attribute-not-allowed"
    if "attribute" in msg and "is required" in msg:
        return "attribute-missing"
    if "No matching global declaration" in msg:
        return "unknown-root"
    return "other"


def normalize(msg):
    for rx, rep in _NORM:
        msg = rx.sub(rep, msg)
    return msg.strip()


def load_schema(xsd_path):
    return etree.XMLSchema(etree.parse(xsd_path, etree.XMLParser(no_network=True)))


def xsd_validate(opener, schema, max_errors_kept=20000):
    """Full parse + XSD validation of one document. Returns (valid, Counter(cat), Counter(norm_msg), n)."""
    parser = etree.XMLParser(huge_tree=True, no_network=True, resolve_entities=False)
    with opener() as f:
        tree = etree.parse(f, parser)
    ok = schema.validate(tree)
    cats, msgs, n = Counter(), Counter(), 0
    for e in schema.error_log:
        n += 1
        if n <= max_errors_kept:
            cats[categorize(e.message)] += 1
            msgs[normalize(e.message)[:220]] += 1
    del tree
    return ok, cats, msgs, n
