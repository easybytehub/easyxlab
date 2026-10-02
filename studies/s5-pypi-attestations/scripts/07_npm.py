"""npm comparison sample: top-1,000 by weekly downloads + 500 random from ranks 1,001-15,916
(npm-high-impact 1.13.0, published 2026-06-08). Reads the abbreviated packument (corgi), which
carries dist.attestations per version. Stores only version -> has-provenance (no maintainer or
publisher-user fields). For attested packages, fetches the provenance attestation of the first and
latest attested versions to read the source repository and workflow path."""
import base64, concurrent.futures as cf, json, os, random, re, time
from common import http_get, cache_read, cache_write, DATA, RAW

NHI = os.path.join(RAW, "npm", "package", "lib", "top-download.js")
SEED = 20261002


def load_list():
    """Sample of the frozen list. The list itself (MIT, npm-high-impact 1.13.0) is fetched by 01_fetch_inputs.py
    into data/raw/ and not redistributed; without it, the published sample (data/compact/npm_sample.csv) is used."""
    if not os.path.exists(NHI):
        import csv
        return [(int(r["rank"]), r["package"]) for r in csv.DictReader(open(os.path.join(DATA, "compact", "npm_sample.csv")))]
    names = re.findall(r"'([^']+)'", open(NHI).read())
    rnd = random.Random(SEED)
    tail = rnd.sample(range(1000, len(names)), 500)
    return [(i + 1, names[i]) for i in list(range(1000)) + sorted(tail)]


def corgi(name):
    c = cache_read("npm_corgi", name)
    if c is not None:
        return c
    st, body, _ = http_get("https://registry.npmjs.org/" + name.replace("/", "%2F"), "application/vnd.npm.install-v1+json")
    obj = {"name": name, "status": st}
    if body:
        d = json.loads(body)
        obj["dist_tags"] = d.get("dist-tags", {})
        obj["versions"] = {v: {"prov": bool(((m.get("dist") or {}).get("attestations") or {}).get("provenance")),
                               "dep": bool(m.get("deprecated"))} for v, m in d.get("versions", {}).items()}
    cache_write("npm_corgi", name, obj)
    return obj


def times(name):
    """Full packument, only for regression candidates: keep the per-version publish time only."""
    c = cache_read("npm_time", name)
    if c is not None:
        return c
    st, body, _ = http_get("https://registry.npmjs.org/" + name.replace("/", "%2F"))
    obj = {"name": name, "status": st, "time": {}}
    if body:
        d = json.loads(body)
        obj["time"] = {k: v for k, v in d.get("time", {}).items() if k not in ("created", "modified")}
    cache_write("npm_time", name, obj)
    return obj


def provenance(name, version):
    key = f"{name}@{version}"
    c = cache_read("npm_att", key)
    if c is not None:
        return c
    st, body, _ = http_get(f"https://registry.npmjs.org/-/npm/v1/attestations/{name.replace('/', '%2F')}@{version}")
    obj = {"key": key, "status": st}
    if body:
        for a in json.loads(body).get("attestations", []):
            env = (a.get("bundle") or {}).get("dsseEnvelope")
            if not env or "slsa.dev/provenance" not in a.get("predicateType", ""):
                continue
            p = json.loads(base64.b64decode(env["payload"])).get("predicate", {})
            if "buildDefinition" in p:  # SLSA v1
                w = p["buildDefinition"].get("externalParameters", {}).get("workflow", {})
                obj.update(repo=w.get("repository"), path=w.get("path"), builder=p.get("runDetails", {}).get("builder", {}).get("id"))
            else:  # SLSA v0.2
                inv = p.get("invocation", {}).get("configSource", {})
                obj.update(repo=inv.get("uri", "").split("@")[0], path=inv.get("entryPoint"), builder=p.get("builder", {}).get("id"))
    cache_write("npm_att", key, obj)
    return obj


SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+.*)?$")


def skey(v):
    m = SEMVER.match(v)
    if not m:
        return None
    pre = m.group(4)
    prek = (1,) if pre is None else (0,) + tuple((0, int(x), "") if x.isdigit() else (1, 0, x) for x in pre.split("."))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) + (prek,)


if __name__ == "__main__":
    sample = load_list()
    with cf.ThreadPoolExecutor(16) as ex:
        docs = dict(zip([n for _, n in sample], ex.map(corgi, [n for _, n in sample])))
    # first and latest attested version per attested package -> provenance identity
    jobs = []
    for _, n in sample:
        d = docs[n]
        vs = sorted([v for v, m in d.get("versions", {}).items() if m["prov"] and skey(v)], key=skey)
        if vs:
            jobs += [(n, vs[0]), (n, vs[-1])]
            lt = d["dist_tags"].get("latest")
            if lt and lt in d["versions"] and d["versions"][lt]["prov"]:
                jobs.append((n, lt))
    with cf.ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda j: provenance(*j), set(jobs)))
    print("npm corgi:", len(docs), "attestation lookups:", len(set(jobs)))
