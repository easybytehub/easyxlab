"""Prior-work search (run 2026-10-03): OpenAlex, Crossref, arXiv, GitHub repository search. Raw answers in work/prior/."""
import json, sys, urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from fetch import Fetcher
f = Fetcher(Path("work/requests.log"))
OUT = Path("work/prior"); OUT.mkdir(parents=True, exist_ok=True)
Q = ["MiCA white paper XBRL", "crypto-asset white paper machine-readable", "MiCA white paper iXBRL",
     "crypto-asset white papers MiCA empirical", "MiCAR white paper register ESMA", "Markets in Crypto-Assets white paper disclosure analysis"]
res = {}
for q in Q:
    e = urllib.parse.quote(q)
    for name, url in [("openalex", f"https://api.openalex.org/works?search={e}&per-page=10&sort=relevance_score:desc"),
                      ("crossref", f"https://api.crossref.org/works?query={e}&rows=10&select=title,DOI,issued,container-title"),
                      ("arxiv", f"https://export.arxiv.org/api/query?search_query=all:%22{e}%22&max_results=10"),
                      ("github", f"https://api.github.com/search/repositories?q={e}&per_page=10")]:
        r = f.get(url, headers={"Accept": "application/json"} if name != "arxiv" else None)
        res.setdefault(q, {})[name] = {"status": r["status"], "reason": r["reason"]}
        (OUT / f"{name}_{abs(hash(q))%10**8}.raw").write_bytes(r["body"] or b"")
        b = r["body"] or b""
        try:
            if name == "openalex":
                items = [(w.get("title"), w.get("publication_year"), w.get("doi")) for w in json.loads(b)["results"]]
            elif name == "crossref":
                items = [((w.get("title") or [""])[0], (w.get("issued", {}).get("date-parts") or [[None]])[0][0], w.get("DOI")) for w in json.loads(b)["message"]["items"]]
            elif name == "github":
                items = [(w["full_name"], w["created_at"][:10], w.get("description")) for w in json.loads(b)["items"]]
            else:
                import re
                items = re.findall(r"<entry>.*?<id>(.*?)</id>.*?<title>(.*?)</title>", b.decode("utf-8", "replace"), re.S)
        except Exception as ex:
            items = [f"parse error {ex}"]
        res[q][name]["items"] = items
Path("work/prior/summary.json").write_text(json.dumps(res, indent=1, default=str))
for q in Q:
    print("##", q)
    for name in res[q]:
        print("  ", name, res[q][name]["status"], [str(i)[:110] for i in res[q][name]["items"][:6]])
