import sys,json,re; sys.path.insert(0,sys.argv[1]); from wd import *
d=json.load(open(sys.argv[1]+"/drugs.json"))
nonlatin={"ar","uk","ru","fa","ps","ti","am","bn","ur","hi","zh"}
for n,(it,v) in d.items():
    for l,lab in v["lab"].items():
        if l in nonlatin and re.search(r"[A-Za-z]{3,}",lab): print("LATIN-in",l,n,it,repr(lab))
        if l in ("es","fr","de","pt","pl","tr","sw") and re.search(r"[^\x00-ɏ\s\-\(\),'’]",lab): print("ODD",l,n,repr(lab))
for n in ["metformin","valproate","aspirin","warfarin","tenofovir DF","levothyroxine","salbutamol"]:
    it,v=d[n]; print(n,it,{l:v["lab"].get(l) for l in ["es","fr","ar","uk","fa","ps","sw","bn","ur","zh"]})
# global stats over all items with ATC
tot=q("SELECT (COUNT(DISTINCT ?i) AS ?n) WHERE { ?i wdt:P267 ?a }")[0]["n"]["value"]
print("items with P267:",tot)
rows=q(f'SELECT ?lang (COUNT(DISTINCT ?i) AS ?n) WHERE {{ ?i wdt:P267 ?a; rdfs:label ?l. BIND(LANG(?l) AS ?lang) FILTER(?lang IN ({LF})) }} GROUP BY ?lang')
print(sorted([(r["lang"]["value"],int(r["n"]["value"])) for r in rows],key=lambda x:-x[1]))
inn=q("SELECT ?lang (COUNT(DISTINCT ?i) AS ?n) WHERE { ?i p:P2275/ps:P2275 ?v. BIND(LANG(?v) AS ?lang) } GROUP BY ?lang")
print("P2275 INN by lang:",sorted([(r["lang"]["value"],int(r["n"]["value"])) for r in inn],key=lambda x:-x[1]))
