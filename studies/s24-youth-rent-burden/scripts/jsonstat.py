import json, itertools, sys
def rows(fn):
    d=json.load(open(fn))
    ids=d['id']; size=d['size']; dims=d['dimension']
    cats=[]
    for k in ids:
        idx=dims[k]['category']['index']
        inv=sorted(idx.items(), key=lambda x:x[1])
        cats.append([c for c,_ in inv])
    vals=d['value']; st=d.get('status',{})
    out=[]
    for n,combo in enumerate(itertools.product(*cats)):
        s=str(n)
        if s in vals or s in st:
            out.append(dict(zip(ids,combo),value=vals.get(s),flag=st.get(s,'')))
    return d,out
if __name__=='__main__':
    d,out=rows(sys.argv[1])
    print(d.get('label'), d.get('updated'))
    for k in d['id']:
        print(k, list(d['dimension'][k]['category']['label'].items())[:40])
