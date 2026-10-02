import sys; sys.path.insert(0,sys.argv[1]); from wd import *
import json
ATC={"metformin":"A10BA02","insulin human":"A10AB01","insulin glargine":"A10AE04","insulin aspart":"A10AB05","gliclazide":"A10BB09","sitagliptin":"A10BH01","empagliflozin":"A10BK03","amlodipine":"C08CA01","losartan":"C09CA01","enalapril":"C09AA02","ramipril":"C09AA05","lisinopril":"C09AA03","valsartan":"C09CA03","hydrochlorothiazide":"C03AA03","furosemide":"C03CA01","spironolactone":"C03DA01","bisoprolol":"C07AB07","atenolol":"C07AB03","metoprolol":"C07AB02","atorvastatin":"C10AA05","simvastatin":"C10AA01","rosuvastatin":"C10AA07","aspirin":"B01AC06","clopidogrel":"B01AC04","warfarin":"B01AA03","apixaban":"B01AF02","rivaroxaban":"B01AF01","digoxin":"C01AA05","levothyroxine":"H03AA01","salbutamol":"R03AC02","budesonide":"R03BA02","beclometasone":"R03BA01","tiotropium":"R03BB04","montelukast":"R03DC03","valproate":"N03AG01","carbamazepine":"N03AF01","levetiracetam":"N03AX14","lamotrigine":"N03AX09","phenytoin":"N03AB02","phenobarbital":"N03AA02","tenofovir DF":"J05AF07","lamivudine":"J05AF05","dolutegravir":"J05AJ03","dolutegravir(old)":"J05AX12","efavirenz":"J05AG03","sertraline":"N06AB06","fluoxetine":"N06AB03","escitalopram":"N06AB10","amitriptyline":"N06AA09","olanzapine":"N05AH03","risperidone":"N05AX08","quetiapine":"N05AH04","haloperidol":"N05AD01","lithium":"N05AN01","omeprazole":"A02BC01","allopurinol":"M04AA01","prednisone":"H02AB07","methotrexate":"L04AX03","hydroxycarbamide":"L01XX05","paracetamol":"N02BE01"}
vals=" ".join(f'"{c}"' for c in ATC.values())
rows=q(f'''SELECT ?atc ?item ?sl ?lang ?label WHERE {{ VALUES ?atc {{ {vals} }} ?item wdt:P267 ?atc; wikibase:sitelinks ?sl.
 OPTIONAL {{ ?item rdfs:label ?label. BIND(LANG(?label) AS ?lang) FILTER(?lang IN ({LF})) }} }}''')
by={}
for r in rows:
    a=r["atc"]["value"]; it=r["item"]["value"].split("/")[-1]; sl=int(r["sl"]["value"])
    d=by.setdefault(a,{}).setdefault(it,{"sl":sl,"lab":{}})
    if "lang" in r: d["lab"][r["lang"]["value"]]=r["label"]["value"]
best={}
for name,a in ATC.items():
    if a not in by: print("MISSING",name,a); continue
    it,d=max(by[a].items(),key=lambda x:x[1]["sl"])
    if len(by[a])>1: print("multi",name,a,[(k,v["sl"]) for k,v in by[a].items()])
    best[name]=(it,d)
json.dump({k:[v[0],v[1]] for k,v in best.items()},open(sys.argv[1]+"/drugs.json","w"),ensure_ascii=False)
names=[n for n in best if n!="dolutegravir(old)" or "dolutegravir" not in best]
print("N drugs:",len(names))
for l in LANGS:
    have=[n for n in names if l in best[n][1]["lab"]]
    miss=[n for n in names if l not in best[n][1]["lab"]]
    print(f"{l}: {len(have)}/{len(names)}", ("missing: "+", ".join(miss[:12])) if miss and len(miss)<=12 else (f"missing {len(miss)}" if miss else ""))
