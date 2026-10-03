#!/usr/bin/env python3
"""Rule-based classification of every AI Overview / AI Mode answer (S7).

The rules were written by an AI agent (see METHOD.md §5) and are deterministic:

(a) VERDICT per answer, against the fact's current and superseded rule (data/facts.json):
    text is normalised (markdown links and citation markers removed, thousands separators removed,
    lower case); then the fact's `cur_patterns` and `old_patterns` are searched.
    An `old` hit is CONTEXTUAL when a past/negation marker (antes, en 2025, pasa de, se aplazó, ya no,
    derogado, no se aprobó, …) occurs within 90 characters before or 40 after it — i.e. the answer
    mentions the old rule as history, not as the rule in force.
      current     current rule stated, no non-contextual old hit
      mixed       current rule stated AND a non-contextual old hit
      outdated    no current rule, at least one non-contextual old hit
      not_stated  an answer exists but states neither
      no_answer   the surface returned no AI answer for the query
(b) DOMAIN TYPE per cited reference: rules on the domain, then data/domain_types_agent.csv for the
    domains no rule covers (typed by the AI agent from the domain name and, where unclear, the site).

Reads data/raw/responses/ (full answers, not redistributed). Writes data/answers.csv (published: ids, query,
verdicts, short extract for flagged/confirmed answers), data/citations.csv (domain, type, URL; social-network
paths withheld) and data/raw/classified_full.jsonl (with snippets; not published).
Usage: classify.py [--readings 1,2,3]
"""
import argparse, csv, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PAST = re.compile(
    r"(antes|anterior|anteriormente|previo|previa|hasta ahora|hasta (el )?(31 de diciembre de )?2025|en 2025|"
    r"(año|ejercicio|durante|para|del) (de )?2025|año pasado|año anterior|pas(a|ó|aba|ará|an|aron|ando) de|sube de|subió de|frente a|respecto (a|de|al)|"
    r"desde (los|el|las) |inicialmente|inicial|estaba(n)? (previst|fijad|programad)|aplaz|retras|pospu|pospon|prorrog|"
    r"ya no|dej(ó|a|an|aron) de|derog|convalid|deca|tumb|rechaz|no (se )?(ha )?(sido )?aprob|no sali|propuesta|"
    r"proyecto|anteproyecto|pretend|planteab|en lugar de|en vez de|sustitu|reemplaz|elimin|no prosper|suprim|"
    r"original|primer(a|o)s? (fecha|calendario|plazo)|anula|ampli(a|ó|ado|ación) de|de las anteriores|de los anteriores|"
    r"antigu|ya no es|hasta el 1 de|hasta 2025|hasta el año 2025|en vigor hasta|vigente hasta|histór|"
    r"(^|[|•\-(]\s*)202[345]\s*[:|)]|evita|fin de la|si la empresa|sin cumplir|no puede|no tiene|convenio|inferior|"
    r"complementari|adicional|además de|no es (algo )?autom|carece|sectorial|"
    r"\banul|nulidad|\bnulo|previsibl|estimad|aproximad|si la orden|en caso de que)")
# negation inside the hit itself ("la extinción dejó de ser automática")
NEG_IN_HIT = re.compile(r"(ya no|dej(ó|a|an|aron) de|no (es|ser[aá]|se|opera)|sin )")
LINK = re.compile(r"\[\[\d+\]\]\([^)]*\)|\[([^\]]*)\]\([^)]*\)")


def norm(t):
    t = LINK.sub(lambda m: m.group(1) or "", t or "")
    t = re.sub(r"[*_`#>$]|\\", " ", t)
    t = re.sub(r"(?<=\d)[.   ](?=\d{3}\b)", "", t)        # 1.221 / 1 221 -> 1221
    t = re.sub(r"(?<=\d)[.   ](?=\d{3}\b)", "", t)        # twice for 1.000.000
    t = t.replace("‑", "-").replace("–", "-")
    return re.sub(r"\s+", " ", t).lower()


def hits(t, pats):
    out = []
    for p in pats:
        for m in re.finditer(p, t, re.I):
            out.append((m.start(), m.end()))
    return sorted(set(out))


def contextual(t, s, e):
    # the hit itself is excluded, so an old-rule pattern such as "proyecto de ley" cannot excuse itself
    return bool(PAST.search(t[max(0, s - 90):s]) or PAST.search(t[e:min(len(t), e + 40)])
                or NEG_IN_HIT.search(t[s:e]))


def verdict(fact, text, has_answer):
    if not has_answer or not (text or "").strip():
        return "no_answer", [], []
    t = norm(text)
    cur = hits(t, fact["cur_patterns"])
    old = hits(t, fact["old_patterns"])
    old_live = [(s, e) for s, e in old if not contextual(t, s, e)]
    snip = lambda xs: [t[max(0, s - 60):e + 30] for s, e in xs[:3]]
    if cur and not old_live:
        v = "current"
    elif cur and old_live:
        v = "mixed"
    elif old_live:
        v = "outdated"
    else:
        v = "not_stated"
    return v, snip(cur), snip(old_live)


# ---------------------------------------------------------------- domain types
PRESS = ("elpais", "elmundo", "abc.es", "lavanguardia", "20minutos", "eldiario", "elconfidencial", "expansion.com",
         "cincodias", "eleconomista", "larazon", "rtve", "antena3", "lasexta", "cadenaser", "cope.es", "ondacero",
         "huffingtonpost", "elperiodico", "publico.es", "newtral", "maldita", "infobae", "europapress", "efe.com",
         "heraldo", "lavozdegalicia", "elcorreo", "diariodesevilla", "okdiario", "elespanol", "vozpopuli",
         "libertaddigital", "telecinco", "cuatro.com", "eitb", "3cat", "ccma", "elnortedecastilla", "ideal.es",
         "laverdad", "lasprovincias", "levante-emv", "farodevigo", "lne.es", "diariovasco", "elcomercio", "hoy.es",
         "theobjective", "elplural", "eldebate", "epdata", "bolsamania", "invertia", "xataka", "genbeta",
         "computerhoy", "businessinsider", "forbes.es", "autopista.es", "motorpasion", "noticiastrabajo",
         "diarioarea", "economiadigital", "lainformacion", "merca2", "elindependiente", "eleconomista",
         "cronicaglobal", "el-economista", "telemadrid", "canalsur", "atresmedia", "niusdiario", "elperiodic",
         "lavozdeasturias", "diariodenavarra", "diariodemallorca", "laopiniondemurcia", "informacion.es",
         "diariodeleon", "elcorreogallego", "noticias.juridicas", "confilegal", "lawyerpress", "economistjurist",
         "diariolaley", "eleconomista.es", "periodistadigital", "lavozdelsur", "andaluciainformacion",
         "telecinco", "mundodeportivo", "sport.es", "marca.com", "as.com", "elnacional", "naiz", "ara.cat",
         "elperiodicodearagon", "elperiodicoextremadura", "diariodecadiz", "europasur", "huelvainformacion",
         "granadahoy", "malagahoy", "diariodejerez", "almeriahoy", "eldiariomontanes", "lasprovincias",
         "diariosur", "ultimahora", "laopinioncoruna", "laprovincia", "eldia.es", "canarias7", "cuatro",
         "diariodeavisos", "consumidorglobal", "infosalus", "vandal", "huffpost", "cnnespanol", "bbc.com", "dw.com")
FORUM = ("reddit", "forocoches", "quora", "facebook", "instagram", "youtube", "tiktok", "x.com", "twitter",
         "linkedin", "rankia.com", "threads.net", "pinterest", "spotify", "ivoox", "medium.com")
SOCIAL = ("facebook", "instagram", "tiktok", "youtube", "x.com", "twitter", "linkedin", "threads.net", "pinterest")
SOFTWARE = ("taxdown", "holded", "quipu", "sage.com", "cegid", "factorial", "sesametime", "endalia", "kenjo",
            "personio", "billin", "facturadirecta", "cuentica", "declarando", "quaderno", "anfix", "contasimple",
            "landoo", "facturaone", "caisoft", "innoqubit", "odoo", "bizneo", "nominasol", "edicom", "docuten",
            "b2brouter", "invoiceninja", "payfit", "billage", "a3software", "a3innuva",
            "verifactu", "stel-order", "stelorder", "teamleader", "zoho", "sumup", "glop", "revo.works", "camerfirma",
            "nominaplus", "dexterhr", "woffu", "cezanne", "visma", "seresnet", "ekon", "facturascripts", "cloudbilling",
            "plandeempresa", "getquipu", "factorialhr", "anfix", "taxfix", "bnfix", "kobrux", "facturae", "facturasaas", "holdedapp")
ADVISORY = ("asesor", "gestor", "abogad", "legal", "laboral", "despacho", "bufete", "consult", "jurid", "lefebvre",
            "aranzadi", "iberley", "wolterskluwer", "infoautonomos", "garrigues", "cuatrecasas", "uria", "pwc", "deloitte", "kpmg", "ey.com", "grupo2000",
            "conceptosjuridicos", "tuabogadodefensor", "fiscal", "tributa", "contabil", "nomina", "rrhh", "abogados",
            "economist", "ejaso", "lexgo", "legalitas", "arriaga", "jurista", "derecho", "procurador", "notari")
OTHER = ("caixabank", "bbva", "santander", "bancsabadell", "ing.es", "openbank", "bankinter", "kutxabank", "unicaja",
         "abanca", "ibercaja", "mapfre", "axa", "allianz", "lineadirecta", "mutua", "generali", "zurich", "rastreator",
         "acierto", "ccoo", "ugt", "cgt", "csif", "uso.es", "ocu.org", "facua", "asufin", "ceoe", "cepyme", "ata.es",
         "upta", "uatae", "wikipedia", "idealista", "fotocasa", "habitaclia", "pisos.com", "racc", "race.es",
         "autoescuela", "helpmycash", "kelisto", "selectra", "roams", "universidad", "uned", ".edu", "unir.net",
         "cajamar", "mutuamadrilena", "segurosbilbao", "verti", "reale", "pelayo", "fiatc", "sanitas", "adeslas",
         "dkv", "asisa", "imq", "cofares", "farmacia", "cuidum", "inforesidencias", "mapfre", "catalanaoccidente")
PUBLIC_EXACT = ("lamoncloa.gob.es", "sepe.es", "dgt.es", "imserso.es", "poderjudicial.es", "congreso.es", "senado.es",
                "ine.es", "cnmc.es", "bde.es", "policia.es", "guardiacivil.es", "comunidad.madrid", "madrid.es",
                "gencat.cat", "euskadi.eus", "xunta.gal", "navarra.es", "carm.es", "jcyl.es", "castillalamancha.es",
                "aragon.es", "larioja.org", "asturias.es", "cantabria.es", "caib.es", "gobiernodecanarias.org",
                "juntaex.es", "juntadeandalucia.es", "gva.es", "europa.eu", "060.es", "administracion.gob.es",
                "fogasa.es", "fundae.es", "ipyme.org", "sede.gob.es", "mutuacolaboradora", "consumo.gob.es",
                "notariado.org", "registradores.org", "abogacia.es", "cgpj.es", "boe.es", "bocm.es", "dgt.gob.es",
                "revista.dgt.es", "redtrabaja", "pap.hacienda.gob.es", "hacienda.gob.es", "mivau.gob.es")


def _match(d, keys):
    """Label match, not substring: a key with a dot must equal the domain or be its suffix after a dot;
    a key without a dot must equal one label of the domain."""
    labels = d.split(".")
    return any((d == k or d.endswith("." + k)) if "." in k else (k in labels) for k in keys)


def load_manual():
    f = ROOT / "data/domain_types_agent.csv"
    if not f.exists():
        return {}
    return {r["domain"]: r["type"] for r in csv.DictReader(open(f, encoding="utf-8"))}


MANUAL = load_manual()


def domain_type(d):
    d = (d or "").lower().removeprefix("www.")
    if not d:
        return "unknown"
    if d in MANUAL:
        return MANUAL[d]
    if d == "boe.es" or d.endswith(".boe.es"):
        return "boe"
    if "agenciatributaria" in d.split("."):
        return "aeat"
    if _match(d, ("seg-social.es", "seg-social.gob.es", "inclusion.gob.es")) or "importass" in d.split("."):
        return "social_security"
    if d.endswith(".gob.es") or _match(d, PUBLIC_EXACT):
        return "other_public"
    if _match(d, FORUM):
        return "forum_social"
    if _match(d, PRESS):
        return "press"
    if _match(d, SOFTWARE):
        return "software"
    if _match(d, OTHER):
        return "other"
    if any(k in d for k in ADVISORY):
        return "advisory"
    return "unclassified"


# ---------------------------------------------------------------- outputs
EXCLUDED = set()   # v2: no fact is excluded; F16 is reported separately as a case study (aggregate.py)


def load_review():
    """Every answer the rules flag, and every answer of the facts whose sheet was corrected in v2, was re-read by
    the AI agent; its verdict and a short extract are in data/review_agent.csv."""
    f = ROOT / "data/review_agent.csv"
    if not f.exists():
        return {}
    return {(int(r["reading"]), r["qid"], r["surface"]): r for r in csv.DictReader(open(f, encoding="utf-8"))}


def redact(url, domain):
    """Social-network post URLs identify accounts: publish the domain only."""
    return f"https://{domain}/ (path withheld)" if _match(domain, SOCIAL) else url


def main():
    REVIEW = load_review()
    ap = argparse.ArgumentParser()
    ap.add_argument("--readings", default="1,2,3")
    a = ap.parse_args()
    facts = {f["id"]: f for f in json.load(open(ROOT / "data/facts.json", encoding="utf-8"))}
    full, pub, cites = [], [], []
    for n in a.readings.split(","):
        f = ROOT / f"data/raw/responses/reading{n}.jsonl"     # full Google answers: not redistributed
        if not f.exists():
            continue
        seen = {}
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            if not r.get("error"):
                seen[(r["qid"], r["surface"])] = r
        for (qid, surf), r in sorted(seen.items()):
            fa = facts[r["fact_id"]]
            v, ch, oh = verdict(fa, r.get("text"), r.get("has_answer"))
            rv = REVIEW.get((int(n), qid, surf))
            final = rv["agent_verdict"] if rv else v
            types = [domain_type(x.get("domain")) for x in r.get("refs") or []]
            o = {"reading": int(n), "qid": qid, "fact_id": r["fact_id"], "area": fa["area"], "query": r["query"],
                 "surface": surf, "fetched_at": r.get("fetched_at"), "has_answer": bool(r.get("has_answer")),
                 "n_refs": len(r.get("refs") or []), "rule_verdict": v, "final_verdict": final,
                 "agent_reviewed": bool(rv), "cites_boe": "boe" in types,
                 "cites_official": any(t in ("boe", "aeat", "social_security", "other_public") for t in types)}
            ext = (rv or {}).get("extract") or ""
            if not ext and v in ("outdated", "mixed"):
                ext = (oh[0] if oh else "")[:300]
            o["extract"] = ext[:300] if (v in ("outdated", "mixed") or final in ("outdated", "mixed")) else ""
            pub.append(o)
            full.append({**o, "cur_snippets": ch, "old_snippets": oh, "ref_types": types})
            for x, t in zip(r.get("refs") or [], types):
                dom = (x.get("domain") or "").lower().removeprefix("www.")
                cites.append({"reading": n, "qid": qid, "fact_id": r["fact_id"], "surface": surf, "final_verdict": final,
                              "domain": dom, "type": t, "url": redact(x.get("url"), dom)})
    with open(ROOT / "data/raw/classified_full.jsonl", "w", encoding="utf-8") as fh:
        for o in full:
            fh.write(json.dumps(o, ensure_ascii=False) + "\n")
    with open(ROOT / "data/answers.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pub[0])); w.writeheader(); w.writerows(pub)
    with open(ROOT / "data/citations.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["reading", "qid", "fact_id", "surface", "final_verdict", "domain", "type", "url"])
        w.writeheader(); w.writerows(cites)
    from collections import Counter
    for n in sorted({o["reading"] for o in pub}):
        for s_ in ("aio", "mode"):
            print(f"reading {n} {s_}: rule {dict(Counter(o['rule_verdict'] for o in pub if o['reading'] == n and o['surface'] == s_))}"
                  f" | final {dict(Counter(o['final_verdict'] for o in pub if o['reading'] == n and o['surface'] == s_))}")
    unc = Counter(c["domain"] for c in cites if c["type"] == "unclassified")
    print(f"answers={len(pub)} citations={len(cites)} unclassified_domains={len(unc)} (refs {sum(unc.values())})")
    print(" ".join(d for d, _ in unc.most_common()))


if __name__ == "__main__":
    main()
