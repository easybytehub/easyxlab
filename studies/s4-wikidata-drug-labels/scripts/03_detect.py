#!/usr/bin/env python3
"""Step 3 - automatic detectors (one explicit rule each). Reads data/frozen + data/reference,
writes data/flags.csv and data/label_counts.json (denominators per language/domain).

a  script      label in a non-Latin-script language contains no letter of that script
               (a_latin: only Latin letters; a_other: another non-Latin script); or a
               Latin-script language label contains Cyrillic/Arabic/CJK/Indic/Ethiopic
               letters (a_nonlatin). Development codes (^[A-Z]{1,6}[- ]?\\d{2,}) excluded.
               Mixed labels (expected script + Latin run >=3) -> a_mixed (informational).
b  brand       normalised label == an RxNorm Prescribable brand name (tty=BN) that is not
               also an RxNorm ingredient name (IN/PIN/MIN) nor the item's own en label/INN.
c  salt        c_salt_on_parent: en label has no salt/ester term but the label does;
               c_parent_on_salt: en label has a salt/ester term but the label has none.
d  duplicate   same normalised label, same language, >=2 drug items.
e  INN         en/fr/es (and ru/ar/zh as extension) label differs from every same-language
               WHO INN (P2275) value after case/space normalisation; subtypes by relation.
f  ICD         P494 value not matching Wikidata's own format regex (P1793) for ICD-10
               [A-Z]\\d{2}(\\.\\d{1,2})?  -> f_range (block range), f_cm (ICD-10-CM style),
               f_corrupt (anything else); P7329 value not matching the ICD-11 regex.
g  ATC         g_format (P1793 regex), g_obsolete (code listed as "previous" in the WHO ATC
               alterations list; g_obsolete_split when the note says the change was partial),
               g_dup (same level-5 code, normal/preferred rank, on >=2 items).
"""
import csv, json, os, re, sys, unicodedata, collections

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
sys.path.insert(0, os.path.dirname(__file__))
from wd import LANGS

drugs = [json.loads(l) for l in open(os.path.join(BASE, "frozen", "drugs.jsonl"))]
dis = [json.loads(l) for l in open(os.path.join(BASE, "frozen", "diseases.jsonl"))]
rx = json.load(open(os.path.join(BASE, "reference", "rxnorm_prescribable.json")))
alt = json.load(open(os.path.join(BASE, "reference", "atc_alterations_codes.json")))


def norm(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip().casefold()


def strip_acc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# ---------------- scripts ----------------
RANGES = {
    "latin": [(0x41, 0x5A), (0x61, 0x7A), (0xC0, 0x24F), (0x1E00, 0x1EFF)],
    "cyr": [(0x400, 0x52F)],
    "arab": [(0x600, 0x6FF), (0x750, 0x77F), (0x8A0, 0x8FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "deva": [(0x900, 0x97F)],
    "beng": [(0x980, 0x9FF)],
    "han": [(0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF)],
    "kana": [(0x3040, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9F)],
    "hang": [(0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF)],
    "ethi": [(0x1200, 0x139F)],
}


def script_of(c):
    o = ord(c)
    for k, rs in RANGES.items():
        if any(a <= o <= b for a, b in rs):
            return k
    return None


EXPECTED = {"ru": {"cyr"}, "uk": {"cyr"}, "ar": {"arab"}, "fa": {"arab"}, "ur": {"arab"},
            "hi": {"deva"}, "bn": {"beng"}, "zh": {"han"}, "ja": {"han", "kana"},
            "ko": {"hang", "han"}, "am": {"ethi"}}
LATIN_LANGS = {"en", "es", "fr", "de", "it", "pt", "pl", "tr", "sw"}
DEVCODE = re.compile(r"^[A-Z]{1,6}[- ]?\d{2,}")


def detect_script(lang, lab):
    counts = collections.Counter(script_of(c) for c in lab if c.isalpha())
    counts.pop(None, None)
    if lang in EXPECTED:
        exp = EXPECTED[lang]
        if not any(counts[s] for s in exp):
            if not counts:
                return None
            if DEVCODE.match(lab):
                return "a_devcode"
            return "a_latin" if set(counts) == {"latin"} else "a_other"
        if re.search(r"[A-Za-z]{3,}", lab) and not DEVCODE.match(lab):
            return "a_mixed"
    elif lang in LATIN_LANGS:
        if any(s != "latin" for s in counts):
            return "a_nonlatin"
    return None


# ---------------- salt / ester lexicon ----------------
SALT = {  # Latin-script terms (whole word, case-insensitive), tested in every language
    "latin": r"sodium|sodique|sodio|sódio|sódico|sódica|sodico|sodica|natrium|sodu|sodyum|sodiamu|"
             r"potassium|potassique|potasio|potássio|potásico|potásica|potassico|potassica|kalium|potasu|potasyum|"
             r"calcium|calcique|calcio|cálcio|cálcico|cálcica|calcico|kalzium|wapnia|kalsiyum|"
             r"magnesium|magnésium|magnesio|magnésio|magnezu|"
             r"hydrochloride|hydrochlorid|chlorhydrate|clorhidrato|hidrocloruro|cloridrato|chlorowodorek|hidroklorür|hidroklorid|"
             r"hydrobromide|bromhidrato|bromhydrate|"
             r"sulfate|sulphate|sulfato|solfato|sulfat|siarczan|sülfat|"
             r"phosphate|phosphat|fosfato|fosforan|fosfat|"
             r"mesylate|mesilate|mésilate|mesilato|mesilat|mezylan|"
             r"maleate|maléate|maleato|maleat|maleinian|"
             r"acetate|acétate|acetato|acetat|octan|"
             r"tartrate|tartrato|tartrat|winian|bitartrate|"
             r"citrate|citrato|citrat|cytrynian|"
             r"fumarate|fumarato|fumarat|fumaran|"
             r"succinate|succinato|succinat|bursztynian|"
             r"besylate|besilate|bésilate|besilato|besilat|"
             r"tosylate|tosilate|tosilato|hyclate|hiclato|"
             r"propionate|dipropionate|propionato|dipropionato|propionat|dipropionat|"
             r"valerate|valérate|valerato|valerat|"
             r"palmitate|palmitato|palmitat|decanoate|décanoate|decanoato|decanoat|"
             r"furoate|furoato|furoat|enanthate|enantato",
    "ru": r"натрия|натрий|калия|кальция|магния|гидрохлорид|сульфат|фосфат|мезилат|малеат|ацетат|тартрат|"
          r"цитрат|фумарат|сукцинат|безилат|пропионат|валерат|пальмитат|деканоат|фуроат",
    "uk": r"натрію|натрій|калію|кальцію|магнію|гідрохлорид|сульфат|фосфат|мезилат|малеат|ацетат|тартрат|"
          r"цитрат|фумарат|сукцинат|безилат|пропіонат|валерат|пальмітат|деканоат|фуроат",
    "ar": r"صوديوم|الصوديوم|بوتاسيوم|كالسيوم|مغنيسيوم|هيدروكلوريد|كبريتات|فوسفات|ميسيلات|ماليات|أسيتات|"
          r"سترات|سيترات|فومارات|سكسينات|بروبيونات",
    "fa": r"سدیم|پتاسیم|کلسیم|منیزیم|هیدروکلراید|هیدروکلرید|سولفات|فسفات|مزیلات|مالئات|استات|سیترات|فومارات|"
          r"سوکسینات|پروپیونات",
    "ur": r"سوڈیم|پوٹاشیم|کیلشیم|ہائیڈروکلورائیڈ|ہائیڈروکلورائڈ|سلفیٹ|فاسفیٹ",
    "hi": r"सोडियम|पोटैशियम|पोटेशियम|कैल्शियम|हाइड्रोक्लोराइड|सल्फेट|फॉस्फेट|फास्फेट|मेसिलेट|मैलिएट|एसीटेट|साइट्रेट",
    "bn": r"সোডিয়াম|পটাশিয়াম|ক্যালসিয়াম|হাইড্রোক্লোরাইড|সালফেট|ফসফেট",
    "zh": r"钠|鈉|钾|鉀|钙|鈣|镁|鎂|盐酸|鹽酸|硫酸|磷酸|甲磺酸|马来酸|馬來酸|醋酸|乙酸|酒石酸|枸橼酸|柠檬酸|"
          r"富马酸|富馬酸|琥珀酸|苯磺酸|丙酸|戊酸|棕榈酸|癸酸|糠酸",
    "ja": r"ナトリウム|カリウム|カルシウム|マグネシウム|塩酸|硫酸|リン酸|メシル酸|マレイン酸|酢酸|酒石酸|クエン酸|"
          r"フマル酸|コハク酸|ベシル酸|プロピオン酸|吉草酸|パルミチン酸|デカン酸|フランカルボン酸",
    "ko": r"나트륨|소듐|칼륨|포타슘|칼슘|마그네슘|염산|황산|인산|메실산|말레산|말레인산|아세트산|초산|타르타르산|"
          r"시트르산|푸마르산|숙신산|베실산|프로피온산|발레르산",
    "am": r"ሶዲየም|ፖታሲየም|ካልሲየም",
}
SALT["latin"] += r"|potassio|natrii|kalii|magnezyum"
SALT["bn"] += r"|ম্যাগনেসিয়াম"
SALT["ja"] = SALT["ja"].replace("リン酸", "(?<![゠-ヿ])リン酸")
# en reference side: substring match, plus the parent acids, so that compounds whose *identity*
# contains the ion/acid (bisphosphate, hydrochloric acid, biscoumacetate...) never count as "parent"
EN_ACIDS = r"|hydrochloric|sulfuric|sulphuric|phosphoric|acetic|citric|tartaric|fumaric|succinic|maleic|" \
           r"propionic|valeric|palmitic|phosph|phate|sulf|nitrate|carbonate|chloride|bromide|iodide|oxide|hydroxide"
LATIN_WB = re.compile(r"(?<![\w])(" + SALT["latin"] + r")(?![\w])", re.I)   # whole word
LATIN_SUB = re.compile(r"(" + SALT["latin"] + r")", re.I)                     # substring
EN_SUB = re.compile(r"(" + SALT["latin"] + EN_ACIDS + r")", re.I)
OWN_RE = {l: re.compile(SALT[l], re.I) for l in SALT if l != "latin"}


# inorganic compounds / elements: "salt vs parent" does not apply (zinc sulfate, borax, potassium...)
INORGANIC = set("""zinc iron copper cupric cuprous ferrous ferric magnesium calcium sodium potassium lithium aluminium
aluminum silver gold selenium selenate selenite carbonate bicarbonate hydrogen dihydrogen chloride bromide iodide fluoride
oxide hydroxide peroxide nitrate nitrite permanganate borate tetraborate borax thiosulfate sulfide ammonium barium bismuth
strontium cobalt chromium manganese molybdate tin stannous stannic mercury mercuric mercurous lead gallium cerium
lanthanum technetium iodine fluorine sulfur sulphur phosphorus phosphoric hydrochloric acid ii iii iv""".split())


def is_inorganic(en):
    toks = [t for t in re.split(r"[^a-z]+", en.lower()) if t]
    rest = [t for t in toks if not LATIN_WB.fullmatch(t) and t not in INORGANIC]
    return not rest


def salt_terms(lang, lab, loose=False):
    """loose=False: whole-word Latin terms (German: substring, it compounds); used to claim a
    salt IS named. loose=True: substring everywhere; used to claim a salt is NOT named."""
    rx_ = LATIN_SUB if (loose or lang == "de") else LATIN_WB
    found = [m.group(1).lower() for m in rx_.finditer(lab)]
    if lang in OWN_RE:
        found += OWN_RE[lang].findall(lab)
    return found


# ---------------- brand list ----------------
ingredients = {norm(x) for t in ("IN", "PIN", "MIN") for x in rx[t]}
brands = {norm(x): x for x in rx["BN"] if norm(x) not in ingredients and len(norm(x)) >= 4}

# ---------------- ICD / ATC regexes (Wikidata P1793, retrieved 2026-10-02) ----------------
RE_ICD10 = re.compile(r"[A-Z]\d{2}(\.\d{1,2})?")
RE_ICD10_RANGE = re.compile(r"[A-Z]\d{2}(\.\d{1,2})?[-–][A-Z]\d{2}(\.\d{1,2})?")
RE_ICD10_CM = re.compile(r"[A-Z]\d{2}\.?[0-9A-Z]{1,4}")
RE_ICD11 = re.compile(r"((^|[/&])[1-9A-X^IO][A-Z^IO][0-9][0-9A-Z^IO](\.?[0-9A-Z^IO][0-9A-Z^IO]?)?)+")
RE_ATC = re.compile(r"[ABCDGHJLMNPRSV]([0-9][0-9]([A-Z]([A-Z]([0-9][0-9])?)?)?)?")
alt_prev = collections.defaultdict(list)
for r in alt:
    alt_prev[r["previous"]].append(r)
alt_new = {r["new"] for r in alt}

flags = []


def flag(det, sub, domain, it, lang, value, ref="", extra=""):
    flags.append({"detector": det, "subtype": sub, "domain": domain, "qid": it["qid"], "lang": lang,
                  "value": value, "en_label": it["labels"].get("en", it["labels"].get("mul", "")),
                  "reference": ref, "extra": extra, "lastrevid": it["lastrevid"]})


counts = {"drug": collections.Counter(), "disease": collections.Counter(), "chronic": collections.Counter(),
          "drug_class_items": 0}

# ---------------- drugs ----------------
byq_all = {d["qid"]: d for d in drugs}
atc_items = collections.defaultdict(set)
for d in drugs:
    for a in d["atc"]:
        atc_items[a["code"]].add(d["qid"])
dup = collections.defaultdict(set)
for it in drugs:
    en = it["labels"].get("en") or it["labels"].get("mul") or ""
    en_salt = [m.group(1).lower() for m in EN_SUB.finditer(en)]
    inorganic = is_inorganic(en)
    sib = sorted({byq_all[o]["labels"].get("en", o) for a in it["atc"] for o in atc_items[a["code"]]
                  if o != it["qid"]})
    own_names = {norm(en)} | {norm(x) for v in it["inn"].values() for x in v}
    for lang in LANGS:
        lab = it["labels"].get(lang)
        if not lab:
            continue
        counts["drug"][lang] += 1
        s = detect_script(lang, lab)
        if s:
            flag("a", s, "drug", it, lang, lab, ref=it["wiki"].get(lang, ""))
        nl = norm(lab)
        if nl in brands and nl not in own_names:
            flag("b", "b_rxnorm_bn", "drug", it, lang, lab, ref=f"RxNorm BN: {brands[nl]}")
        if lang != "en" and en and not inorganic:
            st = salt_terms(lang, lab)
            if st and not en_salt:
                flag("c", "c_salt_on_parent", "drug", it, lang, lab, ref=f"en: {en}",
                     extra="|".join(st) + " ; atc-siblings: " + "; ".join(sib)[:120])
            elif en_salt and not salt_terms(lang, lab, loose=True) and LATIN_WB.search(en):
                flag("c", "c_parent_on_salt", "drug", it, lang, lab, ref=f"en: {en}",
                     extra="|".join(en_salt) + " ; atc-siblings: " + "; ".join(sib)[:120])
        dup[(lang, nl)].add(it["qid"])
        if lang in ("en", "fr", "es", "ru", "ar", "zh") and it["inn"].get(lang):
            inns = it["inn"][lang]
            if nl not in {norm(x) for x in inns}:
                a = strip_acc(nl).replace("-", "").replace(" ", "")
                cands = [strip_acc(norm(x)).replace("-", "").replace(" ", "") for x in inns]
                if a in cands:
                    sub = "e_typographic"
                elif any(c in a or a in c for c in cands):
                    sub = "e_contains"
                else:
                    sub = "e_different"
                flag("e", sub, "drug", it, lang, lab, ref="INN: " + " / ".join(inns))
    # ATC
    for a in it["atc"]:
        c = a["code"]
        if not RE_ATC.fullmatch(c):
            flag("g", "g_format", "drug", it, "", c)
        if a["rank"] != "deprecated" and "end" not in a and c in alt_prev and c not in alt_new:
            rows = alt_prev[c]
            split = any("split" in r["note"].lower() or "only" in r["note"].lower() for r in rows)
            has_new = any(r["new"] in {x["code"] for x in it["atc"]} for r in rows)
            flag("g", "g_obsolete_split" if split else "g_obsolete", "drug", it, "", c,
                 ref="; ".join(f"{r['substance']} -> {r['new']} ({r['year']})" for r in rows),
                 extra="item also has new code" if has_new else "")

for (lang, nl), qs in dup.items():
    if len(qs) > 1:
        byq = {d["qid"]: d for d in drugs if d["qid"] in qs}
        for q in sorted(qs):
            it = byq[q]
            others = sorted(qs - {q})
            enl = {byq[o]["labels"].get("en", "") for o in others}
            flag("d", "d_same_en" if enl == {it["labels"].get("en", "")} else "d_diff_en", "drug", it, lang,
                 it["labels"][lang], ref=" ".join(others), extra=f"group={lang}:{nl}")

codes = collections.defaultdict(set)
for it in drugs:
    for a in it["atc"]:
        if a["rank"] != "deprecated" and "end" not in a and len(a["code"]) == 7:
            codes[a["code"]].add(it["qid"])
byq = {d["qid"]: d for d in drugs}
for c, qs in codes.items():
    if len(qs) > 1:
        for q in sorted(qs):
            flag("g", "g_dup", "drug", byq[q], "", c, ref=" ".join(sorted(qs - {q})),
                 extra=" | ".join(byq[o]["labels"].get("en", "?") for o in sorted(qs - {q})))

# ---------------- diseases ----------------
P31 = json.load(open(os.path.join(BASE, "frozen", "disease_p31.json")))
DISEASE_CLS = {"Q112193867", "Q929833", "Q112965645", "Q42303753", "Q2057971", "Q1441305", "Q169872", "Q12135",
               "Q12136", "Q1931388", "Q7189713", "Q30897648", "Q639907", "Q130487634", "Q54928607", "Q44702685",
               "Q130753312", "Q179630", "Q140421694", "Q63345803", "Q18965518", "Q18123741", "Q42303753"}
NON_DISEASE = {"Q16521": "taxon", "Q55983715": "taxon", "Q11266439": "template", "Q11753321": "template",
               "Q4167836": "category"}


def kind(it):
    cl = set(P31.get(it["qid"], []))
    for c, k in NON_DISEASE.items():
        if c in cl:
            return k
    if it["chronic"] or cl & DISEASE_CLS:
        return "disease"
    return "other"   # anatomy (ICD-11 X-chapter), organisms without taxon class, procedures...


RE_DOUBLED = re.compile(r"[A-Z](\d{2}(?:\.\d{1,2})?)\1\.?(?=$|[-–,/ ])")
counts["disease_kinds"] = collections.Counter(kind(d) for d in dis)
for it in dis:
    k = kind(it)
    for lang in LANGS:
        if k != "disease":
            break
        lab = it["labels"].get(lang)
        if not lab:
            continue
        counts["disease"][lang] += 1
        if it["chronic"]:
            counts["chronic"][lang] += 1
        s = detect_script(lang, lab)
        if s:
            flag("a", s, "chronic" if it["chronic"] else "disease", it, lang, lab)
    for v in it["icd10"]:
        x = v["v"]
        if not RE_ICD10.fullmatch(x):
            sub = ("f_doubled" if RE_DOUBLED.search(x) else
                   "f_range" if RE_ICD10_RANGE.fullmatch(x) else
                   "f_cm" if RE_ICD10_CM.fullmatch(x) else "f_corrupt")
            flag("f", sub, "chronic" if it["chronic"] else "disease", it, "", x, ref="P494",
                 extra=f"{v['rank']}; kind={k}")
    for v in it["icd11"]:
        if not RE_ICD11.fullmatch(v["v"]):
            flag("f", "f_icd11", "chronic" if it["chronic"] else "disease", it, "", v["v"], ref="P7329",
                 extra=f"{v['rank']}; kind={k}")

counts["drug_items"] = len(drugs)
counts["drug_class_items"] = sum(1 for d in drugs if not any(len(a["code"]) == 7 for a in d["atc"]))
counts["disease_items"] = len(dis)
counts["chronic_items"] = sum(1 for d in dis if d["chronic"])
counts["icd10_values"] = sum(len(d["icd10"]) for d in dis)
counts["icd11_values"] = sum(len(d["icd11"]) for d in dis)
counts["atc_values"] = sum(len(d["atc"]) for d in drugs)
counts["inn_labels_checked"] = {l: sum(1 for d in drugs if d["inn"].get(l) and d["labels"].get(l))
                                for l in ("en", "fr", "es", "ru", "ar", "zh")}
counts["rxnorm_brand_terms_used"] = len(brands)
json.dump(counts, open(os.path.join(BASE, "label_counts.json"), "w"), indent=1, ensure_ascii=False)

for i, f in enumerate(flags, 1):
    f["flag_id"] = f"F{i:05d}"
cols = ["flag_id", "detector", "subtype", "domain", "qid", "lang", "value", "en_label", "reference", "extra",
        "lastrevid"]
with open(os.path.join(BASE, "flags.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(flags)
c = collections.Counter((f["domain"], f["detector"], f["subtype"]) for f in flags)
for k in sorted(c):
    print(*k, c[k])
print("total flags", len(flags))
