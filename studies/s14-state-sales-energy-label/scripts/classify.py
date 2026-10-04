#!/usr/bin/env python3
"""S14 rule-based classifier (frozen rules: METHOD.md §1). Pure functions, unit-tested.

notice_kind(title, text)      -> offer | direct_named | lease | result | correction |
                                 annulment | not_real_estate | other
seller(title, department)     -> (group, body)
energy_status(text)           -> dict(status, letters, evidence)
    status: rating | exempt_declared | pending | no_certificate_stated | certificate_reference | none
lot_type(text)                -> one of TYPES
scope(text, type, energy)     -> (scope, reason): covered | excluded | undeterminable
"""
import re

from lots import fold, cadastral_refs

# ---------------------------------------------------------------------------- notice kind

K_CORRECTION = re.compile(r"\b(correccion de (errores|errata|error)|rectificacion|se corrige|modificacion del anuncio)\b")
K_ANNUL = re.compile(r"\b(anulacion|se anula|anular|suspension|se suspende|suspender|desistimiento|deja(r)? sin efecto|revocacion|aplazamiento|cancelacion)\b")
K_RESULT = re.compile(r"\b(adjudicacion definitiva|resultado de la subasta|se declara desierta|declaracion de (subasta )?desierta|"
                      r"formalizacion de la (venta|enajenacion|compraventa)|por la que se adjudica|se adjudica)\b")
K_DIRECT_NAMED = re.compile(r"\b(incoacion|inicio) del? (procedimiento|expediente) de (enajenacion|venta) directa|"
                            r"enajenacion directa (a favor|a la entidad|al ayuntamiento|a la comunidad)|"
                            r"venta directa a favor|(enajenacion|venta) directa de .{0,120} a favor de")
K_LEASE = re.compile(r"\b(arrendamiento|alquiler|arrendar)\b")
K_SALE = re.compile(r"\b(subasta|subastas|enajenacion|enajenaciones|enajenar|venta|ventas|concurso publico|"
                    r"adjudicacion directa|licitacion)\b")
K_NOT_RE = re.compile(r"\b(bienes muebles|vehiculos?|automoviles|acciones|participacion(es)? (accionarial|social)|"
                      r"participacion del .{1,40} en (la|el) (sociedad|capital)|capital social|aprovechamiento|madera|"
                      r"pastos|chatarra|material(es)? (inservible|sobrante|de desecho)|embarcacion|buque|draga|efectos|"
                      r"mobiliario|equipos|semovientes|ganado|derechos de emision|concesion|cotos?|caza|aeronave|"
                      r"maquinaria|lotes? de (bienes|material)|venta automatica|maquinas expendedoras|cafeteria|"
                      r"servicio de (cafeteria|limpieza|mantenimiento|vigilancia|seguridad|restaurante)|suministro de|obras de)\b")
K_PROPERTY = re.compile(r"\b(inmueble|inmuebles|finca|fincas|vivienda|viviendas|local|locales|edificio|edificios|"
                        r"solar|solares|parcela|parcelas|terreno|terrenos|garaje|garajes|trastero|nave|naves|piso|pisos|"
                        r"casa|propiedades|bienes inmuebles|urbana|rustica|cuartel|acuartelamiento)\b")


def notice_kind(title, text=""):
    t = fold(title)
    if re.match(r"anuncio de (licitacion|formalizacion|adjudicacion|correccion)", t) and \
            not re.search(r"objeto: (la |el )?(enajenacion|venta|subasta)", t):
        return "other"   # section V-A public-procurement notices that are not sales
    if K_CORRECTION.search(t):
        return "correction"
    if K_ANNUL.search(t):
        return "annulment"
    if K_RESULT.search(t) and "adjudicacion directa" not in t:
        return "result"
    if K_DIRECT_NAMED.search(t) or K_DIRECT_NAMED.search(fold(text)[:1500]):
        return "direct_named"
    prop = K_PROPERTY.search(t) or K_PROPERTY.search(fold(text)[:3000])
    if K_NOT_RE.search(t) and not K_PROPERTY.search(t):
        return "not_real_estate"
    if K_LEASE.search(t) and not re.search(r"\b(enajenacion|venta|subasta de (la )?propiedad)\b", t):
        return "lease" if prop else "other"
    if K_SALE.search(t) and prop:
        return "offer"
    if K_SALE.search(t) and K_PROPERTY.search(fold(text)[:3000]):
        return "offer"
    return "other"


# ---------------------------------------------------------------------------- seller

SELLERS = [
    ("TGSS", re.compile(r"tesoreria general de la seguridad social")),
    ("Patrimonio del Estado (DEH)", re.compile(r"(delegacion (especial )?de economia y hacienda|direccion general del patrimonio del estado|"
                                               r"subdireccion general del patrimonio del estado|delegacion de hacienda)")),
    ("INVIED (Defensa)", re.compile(r"(instituto de vivienda,? infraestructura y equipamiento de la defensa|invied)")),
    ("GIESE (Interior)", re.compile(r"gerencia de infraestructuras y equipamiento de la seguridad del estado")),
    ("ADIF / Renfe", re.compile(r"\b(adif|administrador de infraestructuras ferroviarias|renfe)\b")),
    ("Port authorities", re.compile(r"autoridad portuaria|puertos del estado")),
    ("SEPES / Casa 47", re.compile(r"\b(sepes|entidad publica empresarial de suelo|casa 47)\b")),
    ("FOGASA", re.compile(r"fondo de garantia salarial|fogasa")),
    ("Mutuas (Seguridad Social)", re.compile(r"\bmutua\b")),
]


def seller(title, department=""):
    t = fold(title)
    for g, rx in SELLERS:
        if rx.search(t):
            return g, _body(title)
    return "Other public bodies", _body(title)


def _body(title):
    m = re.match(r"^\s*(?:Anuncio|Resolución|Edicto|Acuerdo)\s+(?:de \d{1,2} de \w+ de \d{4},?\s+)?(?:del?|de la|de los)\s+(.*?)(?:,)?\s+(?:por (?:el|la) que|sobre|para|de (?:subasta|convocatoria|enajenación)|relativ|en relación|que anuncia|por medio)", title)
    return (m.group(1).strip() if m else title[:120]).rstrip(",")


# ---------------------------------------------------------------------------- energy statement

ENERGY_WORD = re.compile(r"(?i)(energ[eé]tic|eficiencia energ|kw\s?h|co2|co₂|emisiones)")
# door, floor and similar letters that are not ratings ("vivienda letra D", "puerta B", "bloque C")
DOOR = re.compile(r"(?i)\b(letra|puerta|pta|piso|planta|bloque|portal|escalera|esc|bajo|n[ºo°]|n\.º|numero|"
                  r"tipo|modelo|zona|sector|manzana|parcela|nave|local|apartado|anexo|polígono|poligono|grupo|fase|"
                  r"edificio|torre|portería|porteria)\.?\s*[A-G]\b")
LETTER = re.compile(r"(?<![A-Za-zÁÉÍÓÚÑáéíóúñ0-9/._-])([A-G])(?![A-Za-zÁÉÍÓÚÑáéíóúñ/_-])")
R_EXEMPT = re.compile(r"\b(exent[oa]s?|exencion|exceptuad[oa]|exclu[iy]d[oa]s? (del|de su|de la) (ambito|aplicacion|obligacion)|"
                      r"no (es|resulta|sera|son|resultan) (necesari[oa]s?|obligatori[oa]s?|exigibles?|preceptiv[oa]s?|precis[oa]s?|de aplicacion|aplicables?)|"
                      r"no (requiere|requieren|precisa|precisan|necesita|necesitan|procede|aplica|le es de aplicacion|les es de aplicacion)|"
                      r"no (esta|estan) (obligad[oa]s?|sujet[oa]s?)|no sujet[oa]s?|sin obligacion|no exigible)")
R_PENDING = re.compile(r"\b(en (tramite|tramitacion|proceso de (obtencion|emision|elaboracion|registro|tramitacion)|curso)|"
                       r"pendiente(s)? de|se (esta|estan|encuentra|encuentran) (tramitando|elaborando|en tramite|en tramitacion|en elaboracion)|"
                       r"(ha sido|han sido) solicitad[oa]s?|se (aportara|facilitara|entregara) (con|antes|en el momento))\b")
R_NOCERT = re.compile(r"\b((no|ni) (dispone|disponen|tiene|tienen|cuenta|cuentan|consta|constan|posee|poseen) (de )?(de )?(certificad|calificacion|etiqueta)|"
                      r"carece(n)? de (certificad|calificacion|etiqueta)|sin (certificad|calificacion|etiqueta) (de eficiencia )?energetic|"
                      r"(calificacion|certificado|etiqueta)( de eficiencia)?( energetic[oa])?\s*:\s*(no (disponible|consta|tiene)|sin calificar|carece))")
R_CERTREF = re.compile(r"(certificad[oa]s? (de (la )?eficiencia )?energetic|certificad[oa]s? de eficiencia|certificacion (de (la )?eficiencia )?energetica|"
                       r"calificacion (de (la )?eficiencia )?energetica|etiqueta (de eficiencia )?energetica|eficiencia energetica)")


def energy_windows(text):
    """Each paragraph that mentions energy, from its first energy word, up to 300 characters,
    joined to the next two paragraphs when they are short (<= 120 characters) or table rows."""
    paras = [p for p in text.split("\n")]
    out = []
    for i, p in enumerate(paras):
        m = ENERGY_WORD.search(p)
        if not m:
            continue
        w = p[max(0, m.start() - 60):m.start() + 300]
        for q in paras[i + 1:i + 3]:
            if len(q) <= 120 or " | " in q:
                w += " \n " + q[:200]
            else:
                break
        out.append(w)
    return out


DIGIT_RATING = re.compile(r"(?i:kw\s?h|co2|co₂|a[nñ]o|m2|m²)[^|\n]{0,25}?\d\s?([A-G])(?![A-Za-zÁÉÍÓÚÑáéíóúñ/])")


def rating_letters(window):
    """Energy-class letters (A-G) in a window, after blanking door/floor letters and the
    Spanish preposition 'A' followed by a lower-case word."""
    letters = [m.group(1) for m in DIGIT_RATING.finditer(window)]
    w = DOOR.sub(" ", window)
    for m in LETTER.finditer(w):
        c = m.group(1)
        after = w[m.end():m.end() + 3]
        if c == "A" and re.match(r"\s[a-záéíóúñ]", after):
            continue
        if c == "D" and re.match(r"\.\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ]", w[m.end():m.end() + 4]):
            continue   # "D. Nombre"
        letters.append(c)
    return letters


def energy_status(text):
    ev, letters = {}, []
    for w in energy_windows(text):
        f = fold(w)
        ls = rating_letters(w)
        if ls:
            letters += ls
            ev.setdefault("rating", w)
        if R_EXEMPT.search(f):
            ev.setdefault("exempt_declared", w)
        if R_PENDING.search(f):
            ev.setdefault("pending", w)
        if R_NOCERT.search(f):
            ev.setdefault("no_certificate_stated", w)
        if R_CERTREF.search(f):
            ev.setdefault("certificate_reference", w)
    for st in ("rating", "exempt_declared", "pending", "no_certificate_stated", "certificate_reference"):
        if st in ev:
            both = st == "rating" and (len(letters) >= 2 or bool(re.search(r"consumo", fold(ev[st])) and re.search(r"emision", fold(ev[st]))))
            return {"status": st, "letters": "".join(sorted(set(letters))) if st == "rating" else "",
                    "both_indicators": both, "evidence": re.sub(r"\s+", " ", ev[st])[:400]}
    return {"status": "none", "letters": "", "both_indicators": False, "evidence": ""}


# ---------------------------------------------------------------------------- lot type

T_GARAGE = re.compile(r"\b(plazas? de (garaje|aparcamiento)|garajes?|aparcamientos?|cochera)\b")
T_STORAGE = re.compile(r"\b(trasteros?|cuarto trastero)\b")
T_RES = re.compile(r"\b(viviendas?|pisos?|apartamentos?|casas?|chalets?|duplex|aticos?|estudio|unifamiliar(es)?|adosad[oa]s?|cortijo|masia|caserio|bungalow)\b")
T_COMM = re.compile(r"\b(local(es)?|oficinas?|comercial(es)?|despacho)\b")
T_BUILDING = re.compile(r"\b(edificios?|inmueble urbano|edificacion(es)?|hotel|residencia|colegio|escuela|cuartel|acuartelamiento|"
                        r"casa cuartel|pabellon(es)?|centro|naves? y edificios)\b")
T_INDAGRI = re.compile(r"\b(silos?|unidad(es)? de almacenamiento|naves?|almacen(es)?|cuadras?|establos?|granjas?|corral(es)?|pajar(es)?|taller(es)?|industrial(es)?|"
                       r"agricolas?|ganader[oa]s?|bodegas?|secadero|invernadero|porqueriza|aprisco|tinada|majada)\b")
T_LAND = re.compile(r"\b(solar(es)?|parcelas?|terrenos?|rusticas?|suelo|monte|erial|labor|labradio|secano|regadio|olivar|"
                    r"vina|vinedo|huerta|huerto|prados?|pastos?|tierras?|era|eras|dehesa|pinar|matorral|improductivo|"
                    r"cereal|frutal(es)?|almendr(os|al)|arable|pradera|sembradura|yermo|cultivo)\b")
T_RUIN = re.compile(r"\b(ruinas?|ruinos[oa]s?|derruid[oa]s?|derrumbad[oa]s?|sin cubierta|semiderruid[oa]|en estado de abandono)\b")
T_SHARE = re.compile(r"\b(cuota indivisa|participacion(es)? indivisa|partes? indivisas?|proindivis[oa]|pro indivis[oa]|mitad indivisa|"
                     r"\d+[.,]?\d*\s?(%|por ciento) (de|del) (una|la|un|el) (vivienda|local|finca|inmueble|casa|piso|edificio)|"
                     r"(una|la) (tercera|cuarta|quinta|sexta|septima|octava|novena|decima) parte indivisa|"
                     r"\d+[.,]?\d*\s?(%|por ciento) (de|del|en) (la )?(plena propiedad|pleno dominio|nuda propiedad|propiedad)|"
                     r"(una|la) (mitad|tercera parte|cuarta parte|sexta parte|octava parte) indivisa|"
                     r"nuda propiedad|usufructo|derecho de superficie)\b")
T_PROTECTED = re.compile(r"\b(bien de interes cultural|\bbic\b|proteccion integral|proteccion estructural|catalogad[oa]|"
                         r"conjunto historico|monumento|patrimonio historico|elemento protegido|edificio protegido|"
                         r"nivel de proteccion|grado de proteccion)\b")
T_UNFINISHED = re.compile(r"\b(en construccion|obra (inacabada|sin terminar|paralizada)|sin terminar|inacabad[oa]|"
                          r"en estructura|estructura de hormigon)\b")
T_SHELL = re.compile(r"\b(en bruto|sin acondicionar|no acondicionad[oa]|diafan[oa] sin instalaciones)\b")
T_DEMOLITION = re.compile(r"\b(para su demolicion|orden de demolicion|debera ser demolid|a demoler|declarad[oa] en ruina)\b")

TYPES = ("residential", "commercial", "building", "unit_in_building", "garage", "storage", "industrial_agricultural",
         "land", "ruin", "rural_with_construction", "unknown")


RUSTIC_REF = re.compile(r"^\d{5}[A-Z]\d{8}")
DESC_CUE = re.compile(r"\b(descripcion|finca urbana|finca rustica|urbana[:.]|rustica[:.]|inmueble|vivienda|local|parcela|solar|"
                      r"piso|edificio|nave|casa|terreno|garaje|plaza de|trastero)\b")


def _type_of(head):
    if re.search(r"\b(silos?|unidad(es)? de almacenamiento)\b", head[:200]):
        return "industrial_agricultural"
    land = bool(T_LAND.search(head))
    h120 = head[:120]
    if (T_GARAGE.search(h120) or T_STORAGE.search(h120)) and not (T_RES.search(h120) or T_COMM.search(h120)):
        return "garage" if T_GARAGE.search(h120) else "storage"
    if T_RUIN.search(head):
        return "ruin"
    res, comm, bld = T_RES.search(head), T_COMM.search(head), T_BUILDING.search(head)
    gar, sto, ind = T_GARAGE.search(head), T_STORAGE.search(head), T_INDAGRI.search(head)
    if land and (res or bld or ind):
        # an estate with a house or other construction on it
        if re.search(r"\b(rustica|rusticas|paraje)\b", head) or re.search(r"\bpoligono\b.{0,40}\bparcela\b", head):
            return "rural_with_construction"
    if res:
        return "residential"
    if comm:
        return "commercial"
    if ind and not bld:
        return "industrial_agricultural"
    if bld:
        return "building"
    if gar:
        return "garage"
    if sto:
        return "storage"
    if land:
        return "land"
    return "unknown"


UNIT_CUE = re.compile(r"(\b\d{1,2}\s?º\s?[a-z]?\b|\bplanta (baja|primera|segunda|tercera|cuarta|quinta|sexta|\d)|\bpta\.?\s?\d|"
                      r"\bpuerta \d|\bp\d\b|\bentresuelo\b|\b(izq|izqda|dcha)\b\.?|\b(piso|planta) \d)")


def lot_type(text, title="", context=""):
    """Type from the opening of the lot description (first ~350 characters); if that says
    nothing, from 350 characters after the first description cue; then from the title. A lot
    whose cadastral references are all rustic and that names no construction is land."""
    f = fold(text)
    t = _type_of(f[:350])
    if t == "unknown":
        m = DESC_CUE.search(f)
        if m:
            t = _type_of(f[m.start():m.start() + 350])
    if re.match(r"^\W*(lote\s*\S{0,6}\s*)?[-.:– ]*plazas? (n|num)", f[:60]) and \
            (T_GARAGE.search(fold(title)) or T_GARAGE.search(fold(context)) or T_GARAGE.search(f)):
        return "garage"
    if t == "unknown" and title:
        t = _type_of(fold(title))
    if t == "unknown" and context:
        t = _type_of(fold(context)[:600])
    if t in ("commercial", "building", "unknown") and re.search(r"\b(nave industrial|naves industriales|uso industrial|edificio industrial)\b", f[:1500]):
        t = "industrial_agricultural"
    refs = cadastral_refs(text)
    if t in ("unknown", "land") and refs and all(RUSTIC_REF.match(r) for r in refs):
        # rustic reference: characters 15-18 are 0000 for bare land, another value for a construction
        t = "rural_with_construction" if any(r[14:18] != "0000" for r in refs) else "land"
    if t == "unknown" and UNIT_CUE.search(f[:400]) and not T_LAND.search(f[:400]):
        t = "unit_in_building"
    return t


def surface_m2(text):
    """Largest surface figure stated in the lot (m2), or None."""
    f = fold(text)
    vals = []
    for m in re.finditer(r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?)\s*(m2|m²|metros cuadrados|mts2|m\.2)", f):
        v = m.group(1).replace(".", "").replace(",", ".")
        try:
            vals.append(float(v))
        except ValueError:
            pass
    return max(vals) if vals else None


def scope(text, ltype, energy):
    """Frozen scope rule (METHOD.md §1.4). energy = energy_status(...)."""
    f = fold(text)
    if energy["status"] == "exempt_declared":
        return "excluded", "declared exempt by the seller"
    if ltype == "land":
        return "excluded", "land: not a building (art. 2.h)"
    if ltype == "ruin":
        return "undeterminable", "ruin (no official guidance; may fall outside art. 2.h)"
    if T_DEMOLITION.search(f):
        return "excluded", "stated demolition (art. 3.2.e)"
    if ltype == "industrial_agricultural":
        return "excluded", "industrial/agricultural non-residential (art. 3.2.c)"
    if ltype in ("garage", "storage"):
        return "excluded", "garage or storage room (MITECO FAQ v6.0 no. 14)"
    if ltype in ("commercial", "unit_in_building", "unknown") and T_SHELL.search(f[:800]):
        return "excluded", "shell premises not fit for use (MITECO FAQ v6.0 no. 19)"
    if T_SHARE.search(f[:600]):
        return "undeterminable", "undivided share or limited right"
    if T_PROTECTED.search(f):
        return "undeterminable", "protected building (art. 3.2.a applies only conditionally)"
    if T_UNFINISHED.search(f[:600]):
        return "undeterminable", "unfinished building or shell"
    if ltype == "rural_with_construction":
        return "undeterminable", "rural estate with a construction of unstated use"
    if ltype == "unknown" and energy["status"] != "rating":
        return "undeterminable", "type not stated"
    s = surface_m2(text)
    if ltype in ("residential", "building") and s is not None and s < 50 and re.search(r"\b(aislad|independiente|caseta|casilla)\b", f[:400]):
        return "excluded", "independent building under 50 m2 (art. 3.2.d)"
    return "covered", ""


def compliance(scope_value, energy, rule="primary"):
    """yes | no | n/a. primary: only a stated rating complies. lenient: a reference to an
    existing certificate (or one being processed) also complies."""
    if scope_value != "covered":
        return "n/a"
    st = energy["status"]
    if st == "rating":
        return "yes"
    if rule == "lenient" and st in ("certificate_reference", "pending"):
        return "yes"
    return "no"
