"""25-municipality pilot that preceded S8 (kept for the record).

As first run, this script fetched each home page, security.txt and llms.txt WITHOUT reading
robots.txt first, with the User-Agent
"Mozilla/5.0 (compatible; easybyte-lab-pilot/0.1; +https://github.com/easybytehub/easybyte-lab)".
On 2026-10-02 the published muni_res.json was cleaned: what the robots.txt of two hosts did not
allow (home page, security.txt and llms.txt of www.murcia.es; security.txt and llms.txt of
www.laspalmasgc.es) was removed and marked in the field "removed".

This version reads robots.txt first and requests nothing it disallows (RFC 9309, via
scripts/robots9309.py). Identify yourself with S8_USER_AGENT. Run from anywhere:
    S8_USER_AGENT="Name/1.0 (+URL)" python3 pilot/muni_pilot.py
"""
import json, os, re, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import robots9309 as R  # noqa: E402

UA = os.environ.get("S8_USER_AGENT") or sys.exit("set S8_USER_AGENT to a User-Agent that identifies you")
TOKEN = re.match(r"[A-Za-z_-]+", UA).group(0)
AI = ["gptbot", "chatgpt-user", "oai-searchbot", "claudebot", "claude-user", "anthropic-ai", "ccbot", "google-extended",
      "perplexitybot", "bytespider", "applebot-extended", "meta-externalagent", "amazonbot"]


def get(url):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=15)
        return r.status, r.headers.get("Content-Type", ""), r.read(400000).decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "", "", ""
    except Exception as e:
        return type(e).__name__, "", "", ""


res = []
for h in json.load(open(os.path.join(HERE, "muni_sample.json"))):
    base = "https://" + h
    rs, rct, rb, _ = get(base + "/robots.txt")
    if not isinstance(rs, int):
        base = "http://" + h
        rs, rct, rb, _ = get(base + "/robots.txt")
    if isinstance(rs, int) and 200 <= rs < 300:
        groups = R.parse(rb)                      # whatever the Content-Type
        ok = lambda path: R.allowed(groups, TOKEN, path)  # noqa: E731
    elif isinstance(rs, int) and 400 <= rs < 500:
        groups, ok = [], (lambda path: True)
    else:
        groups, ok = [], (lambda path: False)     # unreachable robots.txt: complete disallow
    row = dict(host=h, robots=bool(groups), ai_blocked=sorted(t for t in AI if R.has_groups(groups) and R.blocks_root(groups, t)))
    if ok("/"):
        s, ct, body, final = get(base + "/")
        row.update(home=s, acc_link=bool(re.search(r'accesibilidad|irisgarritasun|accessibilitat|accesibilid', body, re.I)) if s == 200 else None)
    if ok("/.well-known/security.txt"):
        ss, sct, sb, _ = get(base + "/.well-known/security.txt")
        sec = ss == 200 and "text/plain" in sct.lower() and re.search(r'^contact:', sb, re.I | re.M) is not None
        row.update(sectxt=sec, sec_expires=sec and re.search(r'^expires:', sb, re.I | re.M) is not None,
                   sec_soft404=ss == 200 and not sec)
    if ok("/llms.txt"):
        ls, lct, lb, _ = get(base + "/llms.txt")
        row.update(llms=ls == 200 and "html" not in lct.lower() and len(lb.strip()) > 0)
    res.append(row)
    print(row, flush=True)
    time.sleep(1)
json.dump(res, open(os.path.join(HERE, "muni_res_rerun.json"), "w"))
