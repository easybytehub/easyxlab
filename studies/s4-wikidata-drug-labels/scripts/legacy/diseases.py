import sys,json; sys.path.insert(0,sys.argv[1]); from wd import *
def run(names,tag):
    vals=" ".join(f'"{n}"@en' for n in names)
    rows=q(f'''SELECT ?name ?item ?sl (GROUP_CONCAT(DISTINCT ?lang) AS ?langs) (SAMPLE(?i10) AS ?icd10) (SAMPLE(?i11) AS ?icd11) (SAMPLE(?sn) AS ?snomed) (SAMPLE(?mesh) AS ?m) WHERE {{
     VALUES ?name {{ {vals} }} ?item rdfs:label ?name; wikibase:sitelinks ?sl.
     OPTIONAL {{?item wdt:P494 ?i10}} OPTIONAL {{?item wdt:P7329 ?i11}} OPTIONAL {{?item wdt:P5806 ?sn}} OPTIONAL {{?item wdt:P486 ?mesh}}
     OPTIONAL {{ ?item rdfs:label ?l. BIND(LANG(?l) AS ?lang) FILTER(?lang IN ({LF})) }} }} GROUP BY ?name ?item ?sl''')
    best={}
    for r in rows:
        n=r["name"]["value"]; sl=int(r["sl"]["value"])
        if n not in best or sl>best[n]["sl"]:
            best[n]={"sl":sl,"it":r["item"]["value"].split("/")[-1],"langs":set(r["langs"]["value"].split()),**{k:r[k]["value"] if k in r else None for k in ["icd10","icd11","snomed"]}}
    print(f"== {tag}: found {len(best)}/{len(names)}; missing:",[n for n in names if n not in best])
    for n,b in best.items(): print(f"  {n[:28]:28} {b['it']:10} sl={b['sl']:3} langs={len(b['langs'])}/20 icd10={b['icd10']} icd11={b['icd11']} snomed={b['snomed']}")
    print("  per-lang:",{l:sum(l in b["langs"] for b in best.values()) for l in LANGS})
    print("  with ICD10:",sum(bool(b['icd10']) for b in best.values()),"ICD11:",sum(bool(b['icd11']) for b in best.values()),"SNOMED:",sum(bool(b['snomed']) for b in best.values()))
D=["type 1 diabetes","type 2 diabetes","hypertension","asthma","chronic obstructive pulmonary disease","epilepsy","HIV/AIDS","heart failure","chronic kidney disease","hypothyroidism","major depressive disorder","schizophrenia","sickle cell disease","thalassemia","coronary artery disease","atrial fibrillation","rheumatoid arthritis","Crohn's disease","ulcerative colitis","multiple sclerosis","Parkinson's disease","Alzheimer's disease","cystic fibrosis","haemophilia A","obesity","osteoporosis","psoriasis","gout","bipolar disorder","hepatitis B","hyperthyroidism","migraine","coeliac disease","glaucoma"]
A=["penicillin allergy","peanut allergy","latex allergy","drug allergy","shellfish allergy","egg allergy","milk allergy","tree nut allergy","fish allergy","sesame allergy","wheat allergy","soy allergy","insect sting allergy","sulfonamide allergy","aspirin-exacerbated respiratory disease","food allergy","penicillin","peanut","natural rubber","nonsteroidal anti-inflammatory drug","sulfonamide","shellfish","bee venom"]
run(D,"DISEASES"); run(A,"ALLERGIES/ALLERGENS")
