import json, random, time, urllib.request, urllib.parse, re, sys
UA={"User-Agent":"easybyte-lab-pilot/0.1 (research; research@easybyte.es)"}
def get(url, accept=None):
    h=dict(UA); 
    if accept: h["Accept"]=accept
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=20) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, None
    except Exception as e: return -1, None
rows=json.load(open("top.json"))["rows"]
random.seed(42)
sample=[(i+1,r["project"]) for i,r in enumerate(rows[:25])]+sorted(random.sample([(i+1,r["project"]) for i,r in enumerate(rows[4999:15000],start=4999)],25))
out=[]
for rank,p in sample:
    st,s=get(f"https://pypi.org/simple/{p}/","application/vnd.pypi.simple.v1+json")
    if not s: out.append((rank,p,"ERR",st)); continue
    files=s["files"]; vers=s.get("versions",[])
    # latest version from JSON API
    st2,j=get(f"https://pypi.org/pypi/{p}/json"); v=j["info"]["version"]
    latest=[f for f in files if f"-{v}" in f["filename"] or f"_{v}" in f["filename"]]
    lat_prov=sum(1 for f in latest if f.get("provenance"))
    any_prov=sum(1 for f in files if f.get("provenance"))
    first=min((f["upload-time"] for f in files if f.get("provenance")),default=None)
    pub=None; repo_match=None
    if lat_prov:
        f=[f for f in latest if f.get("provenance")][0]
        st3,pr=get(f["provenance"],"application/vnd.pypi.integrity.v1+json")
        if pr:
            b=pr["attestation_bundles"][0]["publisher"]; pub=(b.get("kind"),b.get("repository") or b.get("project"))
            urls=" ".join((j["info"].get("project_urls") or {}).values()).lower()+" "+(j["info"].get("home_page") or "").lower()
            repo_match = (pub[1] or "").lower() in urls
    out.append((rank,p,v,len(latest),lat_prov,any_prov,len(files),first[:10] if first else None,pub,repo_match))
    time.sleep(0.25)
for o in out: print(o)
top=[o for o in out if o[0]<=25 and o[2]!="ERR"]; tail=[o for o in out if o[0]>25 and o[2]!="ERR"]
f=lambda L: sum(1 for o in L if o[4]>0)
print(f"\nTop-25: latest release attested {f(top)}/{len(top)} | ranks 5000-15000 sample: {f(tail)}/{len(tail)}")
m=[o for o in out if len(o)>8 and o[8]]
print("publisher kinds:",{k:sum(1 for o in m if o[8][0]==k) for k in set(o[8][0] for o in m)}, "| repo declared in metadata matches publisher:",sum(1 for o in m if o[9]),"/",len(m))
