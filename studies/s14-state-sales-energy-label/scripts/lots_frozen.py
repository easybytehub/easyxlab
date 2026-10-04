#!/usr/bin/env python3
"""S14 lot parser: BOE notice HTML (txt.php) -> metadata, paragraphs, lots.

Pure functions, standard library only, unit-tested in tests/test_lots.py.

    notice = parse_notice(html)          # dict: title, department, section, date, paragraphs
    pre, lots, tail = split_lots(notice["paragraphs"], notice["title"])

A lot is (label, [paragraphs]). The splitter recognises, in this order:
  1. explicit lot headers ("Lote 1", "LOTE Nº 2", "Lote núm. 3 -", "Lote número 4", "Lotes 5 y 6"
     is NOT split, it stays one lot and is flagged);
  2. numbered property items ("1.- \"Local en …\"", "2) Vivienda …", "3. Finca urbana …") when no
     lot header exists and at least two numbered items look like property descriptions;
  3. table rows (cells joined with " | ") that start with a lot number, when the notice has no
     header of type 1 or 2;
  4. otherwise the whole body is one lot (single-property notice), unless the text holds two or
     more distinct cadastral references, in which case the notice is flagged "unsplit".
"""
import html as _html
import re
import unicodedata


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# ---------------------------------------------------------------------------- notice

def _cell_text(fragment):
    t = re.sub(r"<br\s*/?>", " ", fragment)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", _html.unescape(t)).strip()


def parse_notice(html):
    """Metadata and body paragraphs of a txt.php page. Table rows become one paragraph each,
    cells joined with ' | '."""
    meta = {}
    m = re.search(r'<h3 class="documento-tit">(.*?)</h3>', html, re.S)
    meta["title"] = _cell_text(m.group(1)) if m else ""
    for k, lab in (("department", "Departamento:"), ("section", "Sección:"), ("published", "Publicado en:"),
                   ("reference", "Referencia:")):
        m = re.search(r"<dt>" + re.escape(lab) + r"</dt>\s*<dd>(.*?)</dd>", html, re.S)
        meta[k] = _cell_text(m.group(1)) if m else ""
    m = re.search(r'<div id="textoxslt">(.*?)<!-- #textoxslt -->', html, re.S)
    body = m.group(1) if m else ""
    paras = []
    pos = 0
    for tm in re.finditer(r"<table.*?</table>", body, re.S):
        paras += _paras(body[pos:tm.start()])
        for row in re.findall(r"<tr.*?</tr>", tm.group(0), re.S):
            cells = [_cell_text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
            cells = [c for c in cells if c]
            if cells:
                paras.append(" | ".join(cells))
        pos = tm.end()
    paras += _paras(body[pos:])
    meta["paragraphs"] = paras
    return meta


def _paras(fragment):
    out = []
    for p in re.findall(r"<(p|li|h\d)[^>]*>(.*?)</\1>", fragment, re.S):
        t = _cell_text(p[1])
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------- lots

# 20-character cadastral references: urban 7 digits + 2 letters + 4 digits + letter + 4 digits +
# 2 control letters; rustic 5 digits (province, municipality) + sector letter + 3 digits (polygon)
# + 5 digits (parcel) + 4 digits + 2 control letters. Optional single spaces between groups.
CATASTRO = re.compile(r"(?<![0-9A-Z])(\d{7} ?[A-Z]{2} ?\d{4} ?[A-Z] ?\d{4} ?[A-Z]{2}|\d{5} ?[A-Z] ?\d{3} ?\d{5} ?\d{4} ?[A-Z]{2})(?![0-9A-Z])")


def cadastral_refs(text):
    """Distinct cadastral references in the text, spaces removed, sorted."""
    return sorted(set(m.group(1).replace(" ", "") for m in CATASTRO.finditer((text or "").upper())))


_NUM_MARK = r"(?:n\.?\s*[ºo°]\.?|num(?:ero)?\.?|nº|n°)"
_LABEL = r"(\d{1,3}|[ivxl]{1,6}|unico)"
_NOT_AFTER = r"(?!\s*(?:%|por ciento|m2|m²|euros|€|ha\b))(?!\s*(?:y|,)\s*\d)"
LOT_HEADER = re.compile(
    r"^\s*(?:[-–•*]\s*)?(?:lote\s*" + _NUM_MARK + r"?|(?:finca|inmueble|bien|propiedad)\s*" + _NUM_MARK + r")\s*:?\s*"
    + _LABEL + r"\b" + _NOT_AFTER, re.I)
LOT_MULTI = re.compile(r"^\s*lotes\s+(?:n\.?\s*[ºo°]\.?\s*)?\d", re.I)
NUM_ITEM = re.compile(r"^\s*(\d{1,3})\s*(?:\.-|\.–|\.\s*-|-\.|\)|\.(?=\s)|\s*-(?=\s))\s*(.*)$")
PROPERTY_WORDS = re.compile(
    r"\b(vivienda|piso|local|finca|parcela|solar|edificio|nave|garaje|aparcamiento|trastero|"
    r"casa|inmueble|urbana|rustica|terreno|apartamento|oficina|chalet|almacen|edificacion|"
    r"porcion|suelo|cuartel|acuartelamiento|plaza)\b")
TABLE_ROW_NUM = re.compile(r"^\s*(?:lote\s*)?(\d{1,3})\s*\|")


def _looks_property(text):
    f = fold(text)
    return bool(PROPERTY_WORDS.search(f) or cadastral_refs(text))


INNER_LOT = re.compile(r"(?<=[.;])\s+(?=(?:LOTE|Lote)\s*(?:n\.?\s*[ºo°]\.?|núm(?:ero)?\.?|nº|n°)?\s*:?\s*\d{1,3}\s*[-.:–])")


def presplit(paragraphs):
    """Split a paragraph where a new sentence starts with a lot header ("… Lote 2 - Plaza …")."""
    out = []
    for p in paragraphs:
        if " | " in p:
            out.append(p)
            continue
        out += [q for q in INNER_LOT.split(p) if q.strip()]
    return out


def merge_same_label(lots):
    """Lots whose label repeats (a description section and a price section) become one lot,
    in order of first appearance. Returns (lots, n_repeated_labels)."""
    order, body = [], {}
    for lab, ps in lots:
        if lab not in body:
            order.append(lab)
            body[lab] = []
        body[lab] += ps
    return [(lab, body[lab]) for lab in order], len(lots) - len(order)


def split_lots(paragraphs, title=""):
    """Returns (preamble, lots, tail, method). lots = list of (label, [paragraphs]).
    method in {'lote_header', 'numbered', 'table', 'single', 'unsplit', 'not_described', 'none'}."""
    if not paragraphs:
        return [], [], [], "none"
    paragraphs = presplit(paragraphs)
    # 1. explicit headers
    idx = [i for i, p in enumerate(paragraphs) if LOT_HEADER.match(fold(p)) or LOT_MULTI.match(fold(p))]
    if idx:
        pre, lots, tail, method = _cut(paragraphs, idx, lambda p: _lot_label(p), "lote_header")
        lots, _ = merge_same_label(lots)
        return pre, lots, tail, method
    # 2. numbered property items: a consecutive run 1, 2, 3 … of which at least half look
    #    like property (item text or the next two paragraphs name a property or a cadastral ref)
    cand = [(i, int(NUM_ITEM.match(p).group(1))) for i, p in enumerate(paragraphs) if NUM_ITEM.match(p)]
    run, expect = [], 1
    for i, n in cand:
        if n == expect:
            run.append(i)
            expect += 1
    if len(run) >= 2:
        def prop(i):
            return _looks_property(NUM_ITEM.match(paragraphs[i]).group(2)[:200] + " " + " ".join(paragraphs[i + 1:i + 3])[:400])
        if sum(prop(i) for i in run) >= len(run) / 2 and prop(run[0]):
            return _cut(paragraphs, run, lambda p: NUM_ITEM.match(p).group(1), "numbered")
    # 3. table rows that start with a number
    idx = [i for i, p in enumerate(paragraphs) if " | " in p and TABLE_ROW_NUM.match(fold(p)) and _looks_property(p)]
    if len(idx) >= 1:
        pre = paragraphs[:idx[0]]
        lots = [(TABLE_ROW_NUM.match(fold(paragraphs[i])).group(1), [paragraphs[i]]) for i in idx]
        tail = paragraphs[idx[-1] + 1:]
        return pre, lots, tail, "table"
    # 4. single property, or unsplit
    joined = " ".join(paragraphs)
    refs = cadastral_refs(joined)
    if not refs and re.search(r"(relacionad|detallad|describ|indicad|recogid|incluid)[oa]s en (el|los) anexos?", fold(joined)):
        return [], [("?", list(paragraphs))], [], "not_described"
    if len(refs) >= 2:
        return [], [("?", list(paragraphs))], [], "unsplit"
    if not refs and not re.search(r"\b(calle|c/|avenida|avda|plaza|paseo|camino|carretera|paraje|poligono|parcela|"
                                  r"finca registral|registro de la propiedad|sito|sita|situad[oa]|ubicad[oa])\b", fold(joined)):
        return [], [("?", list(paragraphs))], [], "not_described"
    return [], [("1", list(paragraphs))], [], "single"


def _lot_label(p):
    f = fold(p)
    m = LOT_HEADER.match(f)
    if m:
        lab = m.group(1)
        return "1" if lab == "unico" else (str(_roman(lab)) if re.fullmatch(r"[ivxl]+", lab) else lab)
    m = re.match(r"^\s*lotes\s+(?:n\.?\s*[ºo°]\.?\s*)?([\d ,y-]+)", f)
    return ("multi:" + re.sub(r"\s+", "", m.group(1))) if m else "?"


def _roman(r):
    v = {"i": 1, "v": 5, "x": 10, "l": 50}
    total = 0
    for i, c in enumerate(r):
        n = v[c]
        total += -n if i + 1 < len(r) and v[r[i + 1]] > n else n
    return total


TAIL_START = re.compile(
    r"^\s*(el plazo|plazo de presentacion|los interesados|las ofertas|la documentacion|la subasta (publica )?(tendra|se celebrara)|"
    r"lugar|fecha (y hora )?(de|del)|presentacion de (ofertas|proposiciones)|el acto|la apertura|"
    r"el pliego|los pliegos|pliego de condiciones|para (mas|cualquier) informacion|informacion:|"
    r"podran (consultarse|obtenerse)|dicho pliego|garantia:|deposito:|las proposiciones|"
    r"se podra|condiciones generales|normas comunes|disposiciones comunes)")


def _cut(paragraphs, idx, labeler, method):
    pre = paragraphs[:idx[0]]
    lots = []
    for k, i in enumerate(idx):
        end = idx[k + 1] if k + 1 < len(idx) else len(paragraphs)
        lots.append((labeler(paragraphs[i]), paragraphs[i:end]))
    # the last lot runs until the general conditions start
    tail = []
    if lots:
        label, body = lots[-1]
        for j in range(1, len(body)):
            if TAIL_START.match(fold(body[j])) or re.match(r"^\s*[^,]{2,40}, \d{1,2} de [a-z]+ de \d{4}\.?\s*-", fold(body[j])):
                tail = body[j:]
                body = body[:j]
                break
        lots[-1] = (label, body)
    return pre, lots, tail, method
