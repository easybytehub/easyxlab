#!/usr/bin/env python3
"""Status of Spain's housing milestones and targets on the Commission's Recovery and
Resilience Scoreboard.

The scoreboard page (ec.europa.eu/economy_finance/recovery-and-resilience-scoreboard/) reads
its data from a public, anonymous Qlik Sense app. We query that app the way the page does:
an anonymous session on the public hub, a CSRF token, then the Qlik engine JSON-RPC over a
websocket, with the field and hypercube definitions copied from the page's own scripts
(milestoneTableDef.js, last_refresh_date.js). No login, no key. Same User-Agent and
one-request-per-second rule as every other fetch; every request is logged.

Output: data/raw/scoreboard/spain_milestones.json (all of Spain's rows, raw), and
data/scoreboard.csv (the housing measures only). Run: python3 scripts/scoreboard.py
"""
import http.cookiejar, json, os, random, sys, time, urllib.request
from s20lib import DATA, RAW
import polite

HOST = "dashboard.tech.ec.europa.eu"
BASE = f"https://{HOST}/qs_digit_dashboard_mt/public"
APP = "67047f98-760d-49e0-b6a9-31b7b2a66fb1"
HOUSING = ("C2.I2", "C2.I7", "C2.R3", "C2.R7", "C13.I13")

DIMS = [  # label, field definition (from milestoneTableDef.js, export version)
    ("country", "[Country]"),
    ("measure", "=[Measure Reference]"),
    ("measure_name", "=[Measure Title $(v.Lang)]"),
    ("mt_ref", "=[Milestone/Target Reference]"),
    ("mt_name", "=[Milestone/Target Name $(v.Lang)]"),
    ("mt_description", "=[Milestone/Target Description]"),
    ("m_or_t", "Milestone or Target"),
    ("loans_grants", "=[Loans/Grants]"),
    ("due", "=[Completion Year-Quarter]"),
    ("unit", "=[Unit of Measure $(v.Lang)]"),
    ("baseline", "Baseline"),
    ("goal", "Goal"),
    ("status", "=[Assessment Status $(v.Lang)]"),
    ("instalment", "=[Milestone/Target Instalment Nr]"),
    ("disbursement_date", "=[Disbursement Date]"),
]


def http_get(opener, url, headers=None):
    ok, verdict = polite.allowed(url)
    if not ok:
        raise PermissionError(url)
    polite._wait(HOST)
    t = polite._now()
    h = {"User-Agent": polite.UA}
    h.update(headers or {})
    r = opener.open(urllib.request.Request(url, headers=h), timeout=120)
    polite._log({"t": t, "url": url, "status": r.status, "robots": verdict})
    return r


class Engine:
    def __init__(self, ws):
        self.ws, self.i = ws, 0

    def call(self, method, handle, params):
        self.i += 1
        polite._wait(HOST)
        self.ws.send(json.dumps({"jsonrpc": "2.0", "id": self.i, "method": method, "handle": handle, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.i:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg["result"]


def main():
    import websocket
    out_raw = RAW / "scoreboard" / "spain_milestones.json"
    out_raw.parent.mkdir(parents=True, exist_ok=True)
    if not out_raw.exists() or "--refetch" in sys.argv:
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        http_get(opener, BASE + "/hub/").read()
        xrf = "".join(random.choice("0123456789ABCDEF") for _ in range(16))
        r = http_get(opener, BASE + f"/qps/csrftoken?xrfkey={xrf}", {"X-Qlik-Xrfkey": xrf})
        token = r.headers.get("qlik-csrf-token")
        cookie = "; ".join(f"{c.name}={c.value}" for c in jar)
        url = f"wss://{HOST}/qs_digit_dashboard_mt/public/app/{APP}/engineData?qlik-csrf-token={urllib.parse.quote(token or '')}"
        polite._wait(HOST)
        polite._log({"t": polite._now(), "url": url.split("?")[0], "status": "websocket", "robots": "4xx-allow-all"})
        ws = websocket.create_connection(url, header=[f"User-Agent: {polite.UA}", f"Cookie: {cookie}"], timeout=90)
        e = Engine(ws)
        doc = e.call("OpenDoc", -1, [APP])["qReturn"]["qHandle"]
        # last refresh of the scoreboard data
        lr = e.call("CreateSessionObject", doc, [{"qInfo": {"qType": "lr"}, "qHyperCubeDef": {"qDimensions": [], "qMeasures": [
            {"qDef": {"qDef": "Max([Load Date])", "qLabel": "Last Updated on:"}}]}}])["qReturn"]["qHandle"]
        lrd = e.call("GetHyperCubeData", lr, ["/qHyperCubeDef", [{"qTop": 0, "qLeft": 0, "qWidth": 1, "qHeight": 1}]])
        last_refresh = lrd["qDataPages"][0]["qMatrix"][0][0]["qText"]
        fld = e.call("GetField", doc, ["Country"])["qReturn"]["qHandle"]
        e.call("SelectValues", fld, [[{"qText": "Spain"}], False, False])
        hc = {"qInfo": {"qType": "mt"}, "qHyperCubeDef": {
            "qDimensions": [{"qDef": {"qFieldDefs": [d], "qFieldLabels": [k]}, "qNullSuppression": k == "country"} for k, d in DIMS],
            "qMeasures": [], "qInitialDataFetch": [], "qSuppressMissing": True}}
        h = e.call("CreateSessionObject", doc, [hc])["qReturn"]["qHandle"]
        layout = e.call("GetLayout", h, [])["qLayout"]
        n = layout["qHyperCube"]["qSize"]["qcy"]
        w = len(DIMS)
        rows = []
        step = 9000 // w
        for top in range(0, n, step):
            page = e.call("GetHyperCubeData", h, ["/qHyperCubeDef", [{"qTop": top, "qLeft": 0, "qWidth": w, "qHeight": min(step, n - top)}]])
            for row in page["qDataPages"][0]["qMatrix"]:
                rows.append({k: c.get("qText", "") for (k, _), c in zip(DIMS, row)})
        ws.close()
        json.dump({"fetched": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "last_refresh": last_refresh, "n": n, "rows": rows},
                  open(out_raw, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print("rows", n, "last refresh", last_refresh, flush=True)
    data = json.load(open(out_raw, encoding="utf-8"))
    import csv
    import re
    def mid(ref):   # "ES-C[C2]-I[I7]" -> "C2.I7"
        m = re.match(r"ES-C\[(C\d+)\]-([RI])\[([RI]\d+)\]", ref.replace(" ", ""))
        return f"{m.group(1)}.{m.group(3)}" if m else ref
    def mtn(ref):   # "ES-C[C2]-I[I2]-T[31]" -> "31"
        m = re.search(r"-[MT]\[([^\]]+)\]$", ref)
        return m.group(1) if m else ""
    seen, keep = set(), []
    for r in data["rows"]:
        if mid(r["measure"]) not in HOUSING:
            continue
        r = dict(r, measure_id=mid(r["measure"]), number=mtn(r["mt_ref"]))
        k = tuple(sorted(r.items()))
        if k not in seen:
            seen.add(k); keep.append(r)
    with open(DATA / "scoreboard.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=["scoreboard_last_refresh", "fetched", "measure_id", "number"] + [k for k, _ in DIMS])
        wr.writeheader()
        for r in keep:
            wr.writerow({"scoreboard_last_refresh": data["last_refresh"], "fetched": data["fetched"], **r})
    print("housing rows", len(keep))


if __name__ == "__main__":
    import urllib.parse
    main()


def match_versions():
    """For each housing milestone/target on the scoreboard: which CID versions have exactly the
    same description and goal (lower-case alphanumeric tokens). Output: data/scoreboard_versions.csv"""
    import csv, re
    tok = lambda s: re.findall(r"[a-z0-9]+", re.sub(r"(?<=\d)[  ](?=\d{3}\b)", "", (s or "")).lower().replace("-", ""))
    sb = list(csv.DictReader(open(DATA / "scoreboard.csv", encoding="utf-8")))
    hr = list(csv.DictReader(open(DATA / "housing_rows.csv", encoding="utf-8")))
    out, seen = [], set()
    for r in sb:
        key = (r["measure_id"], r["number"])
        if key in seen:
            continue
        seen.add(key)
        same = [h["version"] for h in hr if (h["measure"], h["number"]) == key
                and tok(h["description"]) == tok(r["mt_description"])
                and tok(h["goal"]).__eq__(tok(r["goal"] if r["goal"] != "-" else ""))]
        out.append({"measure": key[0], "number": key[1], "m_or_t": r["m_or_t"], "due": r["due"], "goal": r["goal"],
                    "status": r["status"], "instalment": r["instalment"], "loans_grants": r["loans_grants"],
                    "disbursement_dates": ";".join(sorted({x["disbursement_date"] for x in sb if (x["measure_id"], x["number"]) == key} - {"-"})),
                    "cid_versions_with_same_text": ";".join(same),
                    "scoreboard_last_refresh": r["scoreboard_last_refresh"]})
    with open(DATA / "scoreboard_versions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    for o in out:
        print(o["measure"], o["number"], o["status"], o["instalment"], o["disbursement_dates"], "| same text as:", o["cid_versions_with_same_text"])


if __name__ == "__main__" and "--match" in sys.argv:
    match_versions()
