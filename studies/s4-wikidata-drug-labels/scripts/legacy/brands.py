import sys; sys.path.insert(0,sys.argv[1]); from wd import *
r=q('SELECT (COUNT(DISTINCT ?i) AS ?n) WHERE { ?i wdt:P3781 ?ing }'); print("items with P3781 has active ingredient:",r[0]["n"]["value"])
r=q('SELECT (COUNT(DISTINCT ?i) AS ?n) WHERE { ?i wdt:P3781 ?ing; wdt:P17 ?c }'); print("  ...with country (P17):",r[0]["n"]["value"])
for b in ["Glucophage","Dianben","Sintrom","Coumadin","Eutirox","Ventolin","Depakine","Norvasc"]:
    rr=q(f'SELECT ?i ?d (GROUP_CONCAT(?ingL) AS ?ings) WHERE {{ ?i rdfs:label|skos:altLabel "{b}"@en. OPTIONAL{{?i schema:description ?d FILTER(LANG(?d)="en")}} OPTIONAL{{?i wdt:P3781 ?ing. ?ing rdfs:label ?ingL FILTER(LANG(?ingL)="en")}} }} GROUP BY ?i ?d LIMIT 5')
    print(b,[(x["i"]["value"].split("/")[-1],x.get("d",{}).get("value","")[:40],x["ings"]["value"]) for x in rr])
