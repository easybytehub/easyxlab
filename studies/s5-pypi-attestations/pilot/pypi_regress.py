import json,urllib.request,time,concurrent.futures as cf
from datetime import datetime,timedelta
rows=json.load(open("top.json"))["rows"][:500]
def one(r):
    p=r["project"]
    try:
        s=json.loads(urllib.request.urlopen(urllib.request.Request(f"https://pypi.org/simple/{p}/",headers={"Accept":"application/vnd.pypi.simple.v1+json","User-Agent":"easybyte-lab-pilot/0.1 (contact@easybyte.es)"}),timeout=30).read())
    except Exception as e: return p,None
    fs=[f for f in s["files"] if not f.get("yanked")]
    if not fs: return p,None
    ts=lambda f: datetime.fromisoformat(f["upload-time"].replace("Z","+00:00"))
    newest=max(ts(f) for f in fs)
    batch=[f for f in fs if newest-ts(f)<timedelta(hours=48)]
    older=[f for f in fs if newest-ts(f)>=timedelta(hours=48)]
    return p,dict(latest=any(f.get("provenance") for f in batch),ever_before=any(f.get("provenance") for f in older),newest=newest.date().isoformat())
out={}
with cf.ThreadPoolExecutor(4) as ex:
    for p,d in ex.map(one,rows): out[p]=d
json.dump(out,open("pypi_top500.json","w"))
ok={p:d for p,d in out.items() if d}
lat=sum(d["latest"] for d in ok.values()); reg=[p for p,d in ok.items() if d["ever_before"] and not d["latest"]]
print(f"top-500 ok={len(ok)} latest_attested={lat} ({lat/len(ok):.1%}) ever_attested={sum(d['latest'] or d['ever_before'] for d in ok.values())}")
for band in [(0,100),(100,250),(250,500)]:
    ps=[r["project"] for r in rows[band[0]:band[1]] if out.get(r["project"])]
    print(f"  ranks {band[0]+1}-{band[1]}: {sum(out[p]['latest'] for p in ps)}/{len(ps)}")
print("REGRESSIONS (attested before, latest upload batch without):",len(reg)); print(" ",[(p,ok[p]["newest"]) for p in reg])
