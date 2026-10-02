import sys,json,urllib.request,urllib.parse; sys.path.insert(0,sys.argv[1]); from wd import *
r=q('SELECT (COUNT(*) AS ?all) (SUM(IF(REGEX(?v,"^[A-Z][0-9][0-9]([0-9]?)[0-9][0-9]?\\\\.?$") && REGEX(?v,"([0-9][0-9])\\\\1\\\\.$"),1,0)) AS ?bad) WHERE { ?i wdt:P494 ?v }')
print("P494 values:",r[0]["all"]["value"],"pattern XNNNN. (dup digits + dot):",r[0]["bad"]["value"])
ex=q('SELECT ?i ?v WHERE { ?i wdt:P494 ?v FILTER(REGEX(?v,"([0-9][0-9])\\\\1\\\\.$")) } LIMIT 8')
print("examples:",[(e["i"]["value"].split("/")[-1],e["v"]["value"]) for e in ex])
A="https://www.wikidata.org/w/api.php?"
def api(**p):
    p["format"]="json"; req=urllib.request.Request(A+urllib.parse.urlencode(p),headers={"User-Agent":"EasyByteLab-research/0.1"})
    return json.load(urllib.request.urlopen(req,timeout=60))
items={"metformin":"Q19484","aspirin":"Q18216","warfarin":"Q113368879","levothyroxine":"Q773449","salbutamol":"Q410358","HIV/AIDS":"Q12199","hypertension":"Q41861","asthma":"Q35869","epilepsy":"Q41571","T2D":"Q3025883","peanut":"Q37383","penicillin":"Q12190"}
tot=0;rev=0
for n,i in items.items():
    d=api(action="query",prop="revisions",titles=i,rvlimit=500,rvprop="timestamp|tags|user|comment",rvstart="2026-10-02T00:00:00Z",rvend="2023-10-01T00:00:00Z")
    rv=list(d["query"]["pages"].values())[0].get("revisions",[])
    reverted=[x for x in rv if "mw-reverted" in x.get("tags",[])]
    undo=[x for x in rv if any(t in x.get("tags",[]) for t in ("mw-undo","mw-rollback","mw-manual-revert"))]
    lab=[x for x in reverted if "label" in x.get("comment","").lower()]
    tot+=len(rv);rev+=len(reverted)
    print(f"{n:13} edits3y={len(rv):3} reverted={len(reverted):2} (label/desc reverted={len(lab)}) reverts={len(undo)}", (reverted[0]["timestamp"][:10]+" "+reverted[0]["comment"][:80]) if reverted else "")
print("TOTAL",tot,"reverted",rev)
d=api(action="query",prop="revisions",titles="Q12199",rvlimit=500,rvprop="timestamp|user|comment")
rv=list(d["query"]["pages"].values())[0]["revisions"]
print([ (x["timestamp"][:10],x["user"],x["comment"][:90]) for x in rv if "P494" in x.get("comment","")][:4])
