#!/usr/bin/env python3
"""Step 4 — every table and headline figure of S6, from data/ only (stdlib only).

Inputs: data/sample.csv, data/sample_categories.csv (flags), data/results.jsonl,
data/results_followup.jsonl, data/category_tree.csv.
Outputs: data/per_file.csv, data/validation_failures.csv, data/summary.md,
data/headline.json (the numbers quoted in README.md and paper.md; checked by
scripts/check_headlines.py).

Validity is reported two ways:
  * "0.1.0" — ai-mark-lint 0.1.0 as released (no EKU list: the defect this study found);
  * "0.1.1" — the corrected rule, emulated from the recorded reader outputs: c2pa-rs's
    default EKU list passed (configuration `none_eku`), and `signingCredential.expired`
    dropped when the time-stamp is present but its TSA is untrusted
    (`timeStamp.untrusted`), which ai-mark-lint 0.1.1 reports as a trust question
    (C2PA-003) instead of an invalid manifest. The result figures use 0.1.1.
Estimates: stratified by month (domain sizes N_h·d_h/n_h), Wilson intervals on the Kish
effective n, no finite-population correction (inference is about the upload process),
Newcombe for differences, and a cluster bootstrap with upload day as the primary
sampling unit within month (2,000 replicates, seed 20261003) for the comparisons.
"""

from __future__ import annotations

import csv
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
Z = 1.959964
B = 2000
SEED = 20261003
AI = re.compile(r"trainedalgorithmicmedia|compositesynthetic|algorithmicmedia|compositewithtrainedalgorithmicmedia", re.I)
SIGNERS = ("OpenAI", "Google", "Truepic", "Adobe", "Microsoft", "Samsung", "Canva", "Anthropic", "ByteDance", "xAI")


# ---------------------------------------------------------------- loading
def signer_org(s: str) -> str:
    if "grok" in s.lower() or "xai" in s.lower():
        return "xAI"
    for k in SIGNERS:
        if k.lower() in s.lower():
            return k
    return s or "(none)"


def core(codes) -> list[str]:
    return [c for c in codes if c and not c.endswith(".untrusted") and not c.startswith("cawg.")]


def v011(x: dict | None) -> tuple[str, list[str]] | None:
    """ai-mark-lint 0.1.1's verdict from one recorded reader configuration."""
    if not x or "error" in x:
        return None
    fail = [f[0] for f in x.get("failure", [])]
    info = {f[0] for f in x.get("informational", [])}
    c = core(fail)
    if "signingCredential.expired" in c and "timeStamp.untrusted" in info:
        c = [k for k in c if k != "signingCredential.expired"]
    if c or (x.get("state") == "Invalid" and not fail):
        return "invalid", c
    return ("trusted" if x.get("state") == "Trusted" else "valid"), c


def load() -> list[dict]:
    sample = {int(r["pageid"]): r for r in csv.DictReader(open(DATA / "sample.csv"))}
    flags = {int(r["pageid"]): r for r in csv.DictReader(open(DATA / "sample_categories.csv"))}
    fu = {}
    p = DATA / "results_followup.jsonl"
    if p.exists():
        for line in p.open():
            x = json.loads(line)
            if x.get("reader"):
                fu[x["pageid"]] = x["reader"]
    out = []
    for line in open(DATA / "results.jsonl"):
        r = json.loads(line)
        s, f = sample[r["pageid"]], flags.get(r["pageid"], {})
        if r.get("reader") and r["pageid"] in fu:
            r["reader"] = {**fu[r["pageid"]], **r["reader"]}
        rec = {"pageid": r["pageid"], "title": r["title"], "page_url": r["page_url"],
               "timestamp": s["timestamp"], "day": s["timestamp"][:10], "month": s["timestamp"][:7],
               "mime": r["mime"], "size": r["size"], "stratum": s["stratum"], "N": int(s["stratum_N"]),
               "in_category_tree": s["in_category_tree"], "in_pd_algorithm": s["in_pd_algorithm"],
               "found_in": s["found_in"], "generator": f.get("generator", "unspecified"),
               "ai_evidence_rule": f.get("ai_evidence_rule", ""),
               "coats_of_arms": f.get("coats_of_arms") == "True", "ai_modified": f.get("ai_modified") == "True",
               "status": r["status"], "error": r.get("error", "")}
        rec["main"] = s["in_category_tree"] == "True" or f.get("ai_evidence") == "True"
        lint, det = r.get("lint") or {}, r.get("details") or {}
        marks = lint.get("marks")
        rec["measured"] = r["status"] == "ok" and bool(marks)
        if not rec["measured"]:
            out.append(rec)
            continue
        rec["sha1_match"] = r.get("sha1_match")
        rec["c2pa"] = marks["c2pa"]
        rec["c2pa_ai"] = bool(marks["c2pa_ai"])
        rec["iptc_dst"] = "|".join(marks.get("iptc-dst") or [])
        rec["iptc_ai"] = bool(AI.search(rec["iptc_dst"]))
        rec["aigc_ai"] = bool(det.get("ai_in_aigc"))
        raw = det.get("aigc") or []
        rec["aigc_present"] = bool(raw)
        rec["aigc_double_encoded"] = any(x.lstrip().startswith('"') and '\\"Label\\"' in x for x in raw)
        rec["signer"] = det.get("signer", "")
        gen = det.get("generator") or []
        rec["claim_generator"] = (gen[0][0] if gen else "")[:80]
        rec["signer_org"] = ("" if rec["c2pa"] == "absent" else "xAI (self-signed)" if "grok" in rec["claim_generator"].lower()
                             else signer_org(rec["signer"]))
        rec["fail_codes"] = "|".join(det.get("c2pa_fail") or [])
        rec["c2pa_dst"] = "|".join(sorted(set((det.get("c2pa_dst") or []) + (det.get("c2pa_dst_ingredients") or []))))
        rec["rules"] = "|".join(sorted({x[0] for x in lint.get("findings", [])}))
        rec["any_ai_mark"] = rec["c2pa_ai"] or rec["iptc_ai"] or rec["aigc_ai"]
        rd = r.get("reader") or {}
        for k in ("official", "interim", "both", "none_eku", "official_eku"):
            x = rd.get(k) or {}
            rec[f"{k}_state"] = x.get("state", "")
            rec[f"{k}_core_fail"] = "|".join(core(f[0] for f in x.get("failure", []))) if x else ""
            rec[f"{k}_trusted"] = x.get("state") == "Trusted"
        rec["has_eku_cfg"] = bool(rd.get("none_eku")) and "error" not in rd.get("none_eku", {})
        # ai-mark-lint 0.1.1 (emulated) and with the official list + EKU list
        if rec["c2pa"] in ("valid", "invalid"):
            a = v011(rd.get("none_eku"))
            if a is None:  # follow-up download failed (one file): EKU list only removes failures
                rem = [c for c in rec["fail_codes"].split("|") if c and c != "signingCredential.invalid"]
                a = ("invalid", rem) if rem else ("valid", [])
            rec["c2pa_011"] = a[0]
            o = v011(rd.get("official_eku"))
            rec["official_011"] = o[0] if o else ""
        else:
            rec["c2pa_011"] = rec["c2pa"]
            rec["official_011"] = ""
        rec["valid_ai_010"] = rec["c2pa_ai"] and rec["c2pa"] == "valid"
        rec["valid_ai_011"] = rec["c2pa_ai"] and rec["c2pa_011"] == "valid"
        rec["trusted_ai_official"] = rec["c2pa_ai"] and rec["official_011"] == "trusted"
        ex = {}
        for x in (rd.get("none") or {}).get("failure", []):
            ex.setdefault(x[0], x[1])
        rec["explanations"] = json.dumps(ex, ensure_ascii=False)
        rec["tsa_time"] = ((rd.get("none") or {}).get("signature_info") or {}).get("time") or ""
        certs = [c for c in (r.get("certs") or []) if "fp" in c]
        if certs:
            rec.update(leaf_issuer=certs[0]["issuer"][:120], leaf_not_before=certs[0]["not_before"][:10],
                       leaf_not_after=certs[0]["not_after"][:10], leaf_eku="|".join(certs[0]["eku"]),
                       root_issuer=certs[-1]["issuer"][:120])
        rec["old_codes"] = ("ERROR" if not (r.get("old_c2pa_python_0_10") or {}).get("ok", True) else
                            "|".join(sorted({v.get("code", "") for v in (r.get("old_c2pa_python_0_10") or {}).get("status", []) or []
                                             if isinstance(v, dict)})))
        rec["c2patool_codes"] = "|".join(sorted({x[0] for x in (r.get("c2patool_0_27_22") or {}).get("failure", []) or []}))
        rec["checked_at"] = r.get("checked_at", "")
        if rec["c2pa"] in ("invalid", "unreadable"):
            rec["failure_class"] = classify(rec)
        src = "none"
        if rec["c2pa_ai"]:
            src = rec["signer_org"] if rec["signer_org"] in ("OpenAI", "Google", "Microsoft") else "other C2PA"
        elif rec["iptc_ai"] or rec["aigc_ai"]:
            src = "IPTC/AIGC only"
        rec["mark_source"] = src
        out.append(rec)
    return out


CLASS = {
    "A": "A. content changed after signing (hash mismatch) — real",
    "B": "B. certificate expired, no time-stamp — real (C2PA 2.2 §15.8.2)",
    "B'": "B′. certificate expired; time-stamp present, TSA on no list we used — configuration-dependent",
    "C": "C. certificate expired; time-stamp present, TSA on the official C2PA TSA list — configuration-dependent",
    "D": "D. `signingCredential.invalid` 'missing required EKU' — validator defect (ai-mark-lint 0.1.0)",
    "E": "E. `signingCredential.invalid` 'certificate params incorrect' (Microsoft Paint) — real",
    "F": "F. first action not created/opened (C2PA 2.2 §18.14.2) — real",
    "G": "G. other: manifest.update.invalid / claim.malformed — real",
}


def classify(r: dict) -> str:
    if r["c2pa"] == "unreadable":
        return "unreadable"
    d = set(filter(None, r["fail_codes"].split("|")))
    best = set(filter(None, r.get("official_eku_core_fail", "").split("|")))
    out = []
    if any(c.endswith("mismatch") for c in d):
        out.append("A")
    if "signingCredential.expired" in d:
        if not r["tsa_time"]:
            out.append("B")
        elif r.get("official_eku_state") and "signingCredential.expired" not in best:
            out.append("C")
        else:
            out.append("B'")
    if "signingCredential.invalid" in d:
        ex = json.loads(r["explanations"]).get("signingCredential.invalid", "")
        out.append("D" if "EKU" in ex else "E")
    if "assertion.action.malformed" in d:
        out.append("F")
    if d & {"manifest.update.invalid", "claim.malformed"}:
        out.append("G")
    return "+".join(out) or "?"


# ---------------------------------------------------------------- statistics
def wilson(k: float, n: float) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def skey(r: dict) -> str:
    return "early" if r["stratum"] == "early" else r["month"]


def point(rows: list[dict], pred, n_all: dict) -> float:
    by = defaultdict(list)
    for r in rows:
        by[skey(r)].append(r)
    Nd = {s: v[0]["N"] * len(v) / n_all[s] for s, v in by.items()}
    T = sum(Nd.values())
    return sum(Nd[s] / T * sum(1 for r in v if pred(r)) / len(v) for s, v in by.items()) if T else float("nan")


def estimate(rows: list[dict], pred, n_all: dict) -> tuple[float, float, float, int, int]:
    """Stratified domain estimate, Wilson on Kish n_eff (no FPC)."""
    by = defaultdict(list)
    for r in rows:
        by[skey(r)].append(r)
    Nd = {s: v[0]["N"] * len(v) / n_all[s] for s, v in by.items()}
    T = sum(Nd.values())
    p = var = 0.0
    k_raw = n_raw = 0
    for s, v in by.items():
        n, k = len(v), sum(1 for r in v if pred(r))
        k_raw, n_raw = k_raw + k, n_raw + n
        w, ph = Nd[s] / T, k / n
        p += w * ph
        var += w * w * ph * (1 - ph) / max(n - 1, 1)
    neff = p * (1 - p) / var if var > 0 else n_raw
    lo, hi = wilson(p * neff, neff)
    return p, lo, hi, k_raw, n_raw


def newcombe(a, b) -> tuple[float, float, float]:
    d = b[0] - a[0]
    return d, d - math.sqrt((b[0] - b[1]) ** 2 + (a[2] - a[0]) ** 2), d + math.sqrt((b[2] - b[0]) ** 2 + (a[0] - a[1]) ** 2)


def pct(x: float) -> str:
    return "–" if x != x else f"{100 * x:.1f}%"


def pp(x: float) -> str:
    return f"{100 * x:+.1f}"


# ---------------------------------------------------------------- main
PER = {
    "2024": lambda m: "2024-01" <= m <= "2024-12",
    "2025": lambda m: "2025-01" <= m <= "2025-12",
    "2024-25": lambda m: "2024-01" <= m <= "2025-12",
    "pre": lambda m: "2026-01" <= m <= "2026-07",
    "janmay": lambda m: "2026-01" <= m <= "2026-05",
    "junjul": lambda m: "2026-06" <= m <= "2026-07",
    "post": lambda m: "2026-08" <= m <= "2026-09",
}
COMPARE = [("post", "pre"), ("junjul", "janmay"), ("post", "junjul")]


def compute() -> tuple[dict, list[str], list[dict]]:
    rows = load()
    allm = [r for r in rows if r["measured"]]
    n_all = Counter(skey(r) for r in allm)
    main = [r for r in allm if r["main"]]
    H: dict = {}
    L = ["# S6 summary (generated by scripts/analyze.py)", ""]

    # ---- accounting
    st = Counter((r["status"], r["error"][:40]) for r in rows)
    H["inspected"], H["measured"], H["main_n"], H["union_n"] = len(rows), len(allm), len(main), len(allm)
    H["http404"] = sum(1 for r in rows if "404" in r["error"])
    H["sha1_ok"] = sum(1 for r in allm if r.get("sha1_match"))
    H["pd_only_noevidence_n"] = len(allm) - len(main)
    L += [f"Inspected {len(rows)} · measured {len(allm)} (main {len(main)}, union {len(allm)}) · not measured: {dict(st)}",
          f"SHA-1 of download = API SHA-1: {H['sha1_ok']}/{len(allm)}", ""]
    per_n = {k: sum(1 for r in main if f(r["month"])) for k, f in PER.items()}
    H["n_main"] = per_n
    H["n_union"] = {k: sum(1 for r in allm if f(r["month"])) for k, f in PER.items()}

    metrics = [
        ("any machine-readable AI mark", lambda r: r["any_ai_mark"]),
        ("C2PA declaring AI (any validity)", lambda r: r["c2pa_ai"]),
        ("C2PA declaring AI, valid (ai-mark-lint 0.1.1)", lambda r: r["valid_ai_011"]),
        ("C2PA declaring AI, trusted (official list + EKU)", lambda r: r["trusted_ai_official"]),
        ("C2PA present, failing (0.1.1)", lambda r: r["c2pa_011"] in ("invalid", "unreadable")),
        ("IPTC DigitalSourceType AI (XMP)", lambda r: r["iptc_ai"]),
        ("no AI mark", lambda r: not r["any_ai_mark"]),
        ("[0.1.0] C2PA declaring AI, valid", lambda r: r["valid_ai_010"]),
        ("[0.1.0] C2PA present, failing", lambda r: r["c2pa"] in ("invalid", "unreadable")),
    ]
    noncoa = [r for r in main if not r["coats_of_arms"]]
    for dom_name, dom in (("main", main), ("union", allm)):
        L += [f"## 1{'a' if dom_name == 'main' else 'b'}. Weighted estimates by period — {dom_name} population", "",
              "| metric | 2024 | 2025 | 2026 Jan-Jul | 2026 Jan-May | 2026 Jun-Jul | 2026 Aug-Sep |", "|---|---|---|---|---|---|---|"]
        for name, pred in metrics:
            cells = []
            for per in ("2024", "2025", "pre", "janmay", "junjul", "post"):
                e = estimate([r for r in dom if PER[per](r["month"])], pred, n_all)
                cells.append(f"{pct(e[0])} [{pct(e[1])}–{pct(e[2])}] ({e[3]}/{e[4]})")
                H[f"{dom_name}|{name}|{per}"] = [round(100 * e[0], 1), round(100 * e[1], 1), round(100 * e[2], 1), e[3], e[4]]
            L.append(f"| {name} | " + " | ".join(cells) + " |")
        L += ["", "Cells: weighted estimate [95% Wilson on effective n, files treated as independent] (raw k/n).", ""]
    e = estimate([r for r in main if PER["2024-25"](r["month"])], metrics[0][1], n_all)
    H["main|any|2024-25"] = [round(100 * e[0], 1), round(100 * e[1], 1), round(100 * e[2], 1), e[3], e[4]]

    # ---- cluster bootstrap (upload day within month)
    rng = random.Random(SEED)
    days = defaultdict(lambda: defaultdict(list))
    for r in allm:
        days[skey(r)][r["day"]].append(r)
    keys = {m: list(d) for m, d in days.items()}
    sets = {"main": lambda r: r["main"], "main excl. coats of arms": lambda r: r["main"] and not r["coats_of_arms"],
            "union": lambda r: True}
    preds = {"any": metrics[0][1], "valid011": metrics[2][1]}
    reps = defaultdict(list)
    for _ in range(B):
        rep = []
        for m, ks in keys.items():
            if not m.startswith("2026"):
                continue
            for k in (rng.choice(ks) for _ in ks):
                rep.extend(days[m][k])
        na = Counter(skey(r) for r in rep)
        for sname, sp in sets.items():
            dom = [r for r in rep if sp(r)]
            for pname, pr in preds.items():
                if sname != "main" and pname != "any":
                    continue
                est_p = {per: point([r for r in dom if PER[per](r["month"])], pr, na) for per in ("pre", "post", "janmay", "junjul")}
                for a, b in COMPARE:
                    reps[(sname, pname, a, b)].append(est_p[a] - est_p[b])

    def boot(key):
        v = sorted(x for x in reps[key] if x == x)
        return v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]

    L += ["## 2. Comparisons (difference in percentage points)", "",
          "Newcombe: files independent. Cluster bootstrap: upload day resampled within month, "
          f"{B} replicates, percentile interval.", "",
          "| domain | metric | comparison | A | B | A − B | Newcombe 95% | day-cluster bootstrap 95% |",
          "|---|---|---|---|---|---|---|---|"]
    for sname, sp in sets.items():
        dom = [r for r in allm if sp(r)]
        for pname, pr in preds.items():
            if sname != "main" and pname != "any":
                continue
            for a, b in COMPARE:
                ea = estimate([r for r in dom if PER[a](r["month"])], pr, n_all)
                eb = estimate([r for r in dom if PER[b](r["month"])], pr, n_all)
                d, lo, hi = newcombe(eb, ea)
                blo, bhi = boot((sname, pname, a, b))
                H[f"cmp|{sname}|{pname}|{a}-{b}"] = [round(100 * ea[0], 1), round(100 * eb[0], 1), round(100 * d, 1),
                                                     round(100 * lo, 1), round(100 * hi, 1), round(100 * blo, 1), round(100 * bhi, 1)]
                L.append(f"| {sname} | {pname} | {a} − {b} | {pct(ea[0])} | {pct(eb[0])} | {pp(d)} | [{pp(lo)}, {pp(hi)}] | [{pp(blo)}, {pp(bhi)}] |")
    L.append("")

    # ---- monthly series + decomposition
    L += ["## 3. Main population by month (2026): share of files with an AI mark, by mark source", "",
          "| month | frame N | n | any AI mark [Wilson] | excl. coats of arms (n) | coats-of-arms files (marked) | OpenAI | Google | Microsoft | other C2PA | IPTC/AIGC only | 'OpenAI Media Service API' files | busiest upload day (files) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    H["month"] = {}
    for m in [f"2026-{i:02d}" for i in range(1, 10)]:
        rs = [r for r in main if r["month"] == m]
        n = len(rs)
        k = sum(r["any_ai_mark"] for r in rs)
        lo, hi = wilson(k, n)
        nc = [r for r in rs if not r["coats_of_arms"]]
        coa = [r for r in rs if r["coats_of_arms"]]
        src = Counter(r["mark_source"] for r in rs)
        msa = sum(1 for r in rs if r["claim_generator"] == "OpenAI Media Service API")
        day, dn = Counter(r["day"] for r in rs).most_common(1)[0]
        H["month"][m] = {"n": n, "k": k, "pct": round(100 * k / n, 1), "excl_coa_pct": round(100 * sum(r["any_ai_mark"] for r in nc) / len(nc), 1),
                         "coa_n": len(coa), "coa_marked": sum(r["any_ai_mark"] for r in coa), "msa": msa,
                         **{s: src[s] for s in ("OpenAI", "Google", "Microsoft", "other C2PA", "IPTC/AIGC only")}}
        L.append(f"| {m} | {rs[0]['N']} | {n} | {k} ({pct(k / n)}) [{pct(lo)}–{pct(hi)}] | {pct(sum(r['any_ai_mark'] for r in nc) / len(nc))} ({len(nc)}) | "
                 f"{len(coa)} ({sum(r['any_ai_mark'] for r in coa)}) | " +
                 " | ".join(f"{src[s]} ({pct(src[s] / n)})" for s in ("OpenAI", "Google", "Microsoft", "other C2PA", "IPTC/AIGC only")) +
                 f" | {msa} | {day} ({dn}) |")
    L.append("")
    L += ["### June jump decomposed (weighted share of main-population files marked, by mark source)", "",
          "| mark source | Jan-May | Jun-Jul | difference (pp) |", "|---|---|---|---|"]
    H["decomp"] = {}
    for s in ("OpenAI", "Google", "Microsoft", "other C2PA", "IPTC/AIGC only"):
        a = point([r for r in main if PER["janmay"](r["month"])], lambda r, s=s: r["mark_source"] == s, n_all)
        b = point([r for r in main if PER["junjul"](r["month"])], lambda r, s=s: r["mark_source"] == s, n_all)
        H["decomp"][s] = [round(100 * a, 1), round(100 * b, 1), round(100 * (b - a), 1)]
        L.append(f"| {s} | {pct(a)} | {pct(b)} | {pp(b - a)} |")
    ms_batch = [r for r in main if r["day"] == "2026-06-08" and r["signer_org"] == "Microsoft"]
    H["ms_batch_0608"] = len(ms_batch)
    msa_first = sorted(r["month"] for r in main if r["claim_generator"] == "OpenAI Media Service API")
    H["msa_first_month"] = msa_first[0] if msa_first else ""
    L += ["", f"Microsoft-signed main files uploaded on 2026-06-08: {len(ms_batch)}. "
          f"First month with an 'OpenAI Media Service API' manifest in the main sample: {H['msa_first_month']}.", ""]
    a1 = [r for r in main if r["day"] == "2026-08-01"]
    H["aug1_main"] = [len(a1), sum(r["any_ai_mark"] for r in a1)]
    coa_aug = [r for r in main if r["month"] == "2026-08"]
    H["coa_aug"] = [sum(r["coats_of_arms"] for r in coa_aug), len(coa_aug), sum(r["coats_of_arms"] and r["any_ai_mark"] for r in coa_aug)]
    for per in ("pre", "post", "junjul"):
        e = estimate([r for r in noncoa if PER[per](r["month"])], metrics[0][1], n_all)
        H[f"exclcoa|any|{per}"] = [round(100 * e[0], 1), round(100 * e[1], 1), round(100 * e[2], 1), e[3], e[4]]

    # ---- mark profile, AIGC
    prof = Counter()
    for r in main:
        if r["c2pa"] == "absent":
            prof["IPTC AI only" if r["iptc_ai"] else "AIGC only" if r["aigc_ai"] else "no AI mark"] += 1
        else:
            prof[f"C2PA {r['c2pa_011']} (0.1.1), " + ("AI declared" if r["c2pa_ai"] else "no AI declaration")] += 1
    L += ["## 4. Mark profile — main population, unweighted (n = %d)" % len(main), "", "| profile | n | share |", "|---|---|---|"]
    L += [f"| {k} | {v} | {pct(v / len(main))} |" for k, v in prof.most_common()]
    H["profile"] = {k: [v, round(100 * v / len(main), 1)] for k, v in prof.items()}
    H["aigc"] = {"readable_union": sum(r["aigc_ai"] for r in allm), "readable_main": sum(r["aigc_ai"] for r in main),
                 "double_union": sum(r["aigc_double_encoded"] for r in allm), "double_main": sum(r["aigc_double_encoded"] for r in main)}
    L += ["", f"AIGC: readable label {H['aigc']['readable_union']} (union) / {H['aigc']['readable_main']} (main); "
          f"double-JSON-encoded label, not parsed by ai-mark-lint 0.1.0–0.1.1: {H['aigc']['double_union']} (union) / {H['aigc']['double_main']} (main).", ""]
    mod = [r for r in main if r["ai_modified"]]
    pd_adm = [r for r in main if r["in_category_tree"] != "True"]
    H["ai_modified_main"] = len(mod)
    H["pd_admitted"] = [len(pd_adm), dict(Counter(("AI-word only" if r["ai_evidence_rule"] == "AI-word only" else r["ai_evidence_rule"]) for r in pd_adm).most_common(6))]
    L += [f"Main files flagged AI-modified (retouched/upscaled/colourised/restored categories): {len(mod)}.",
          f"{{{{PD-algorithm}}}} files admitted to main by category evidence: {len(pd_adm)}; matched rule: {H['pd_admitted'][1]}.", ""]

    # ---- generator (main)
    L += ["## 5. By declared generator (Commons categories) — main population, unweighted", "",
          "| group | n | any AI mark [95% CI] | C2PA+AI | valid 0.1.1 | failing 0.1.1 | IPTC AI only |", "|---|---|---|---|---|---|---|"]
    g = defaultdict(list)
    for r in main:
        g[r["generator"]].append(r)
    H["gen"] = {}
    for k, rs in sorted(g.items(), key=lambda x: -len(x[1])):
        n, a = len(rs), sum(r["any_ai_mark"] for r in rs)
        lo, hi = wilson(a, n)
        H["gen"][k] = [n, round(100 * a / n, 1)]
        L.append(f"| {k} | {n} | {pct(a / n)} [{pct(lo)}–{pct(hi)}] | {sum(r['c2pa_ai'] for r in rs)} | "
                 f"{sum(r['c2pa_ai'] and r['c2pa_011'] == 'valid' for r in rs)} | "
                 f"{sum(r['c2pa_011'] in ('invalid', 'unreadable') for r in rs)} | {sum(r['iptc_ai'] and r['c2pa'] == 'absent' for r in rs)} |")
    L.append("")

    # ---- signers (union and main)
    c2u = [r for r in allm if r["c2pa"] != "absent"]
    H["c2pa_union"], H["c2pa_main"] = len(c2u), sum(1 for r in c2u if r["main"])
    L += ["## 6. By C2PA signer — union (all %d files with a manifest; main in brackets)" % len(c2u), "",
          "| signer | manifests | 0.1.1 valid | 0.1.1 failing | trusted (official+EKU) | valid, not on official list | 0.1.0 valid | 0.1.0 failing | AI declared |",
          "|---|---|---|---|---|---|---|---|---|"]
    g = defaultdict(list)
    for r in c2u:
        g[r["signer_org"] or "(none)"].append(r)
    H["signer"] = {}
    for k, rs in sorted(g.items(), key=lambda x: -len(x[1])):
        mn = [r for r in rs if r["main"]]

        def c(f, rs=rs, mn=mn):
            return f"{sum(1 for r in rs if f(r))} ({sum(1 for r in mn if f(r))})"
        row = [len(rs), sum(r["c2pa_011"] == "valid" for r in rs), sum(r["c2pa_011"] in ("invalid", "unreadable") for r in rs),
               sum(r["official_011"] == "trusted" for r in rs), sum(r["official_011"] == "valid" for r in rs)]
        H["signer"][k] = row
        L.append(f"| {k} | {len(rs)} ({len(mn)}) | {c(lambda r: r['c2pa_011'] == 'valid')} | {c(lambda r: r['c2pa_011'] in ('invalid', 'unreadable'))} | "
                 f"{c(lambda r: r['official_011'] == 'trusted')} | {c(lambda r: r['official_011'] == 'valid')} | {c(lambda r: r['c2pa'] == 'valid')} | "
                 f"{c(lambda r: r['c2pa'] in ('invalid', 'unreadable'))} | {c(lambda r: r['c2pa_ai'])} |")
    L += ["", "'(none)': remote-reference-only manifests (signed by Adobe; stored at cai-manifests.adobe.com, not fetched).", ""]

    # ---- configurations
    leg = [r for r in c2u if r["c2pa"] in ("valid", "invalid")]
    H["readable"] = [len(leg), sum(r["main"] for r in leg)]
    L += ["## 7. Validation under each configuration — readable manifests, union (n = %d; main %d)" % (len(leg), sum(r["main"] for r in leg)), "",
          "| configuration | n with this config | Trusted | Valid, untrusted | core failure | most common core codes |", "|---|---|---|---|---|---|"]
    cfg = {}
    def row(lab, have, trusted, valid, fail, codes):
        cfg[lab] = [have, trusted, valid, fail]
        L.append(f"| {lab} | {have} | {trusted} | {valid} | {fail} | {', '.join(f'{c} ×{v}' for c, v in codes.most_common(4))} |")
    row("ai-mark-lint 0.1.0 default (c2pa-python 0.38.0, no trust list, no EKU list)", len(leg), 0,
        sum(r["c2pa"] == "valid" for r in leg), sum(r["c2pa"] == "invalid" for r in leg),
        Counter(c for r in leg for c in r["fail_codes"].split("|") if c))
    row("ai-mark-lint 0.1.1 rule, no trust list (emulated)", len(leg), 0, sum(r["c2pa_011"] == "valid" for r in leg),
        sum(r["c2pa_011"] == "invalid" for r in leg), Counter())
    row("ai-mark-lint 0.1.1 rule, official list + TSA list (emulated)", sum(1 for r in leg if r["official_011"]),
        sum(r["official_011"] == "trusted" for r in leg), sum(r["official_011"] == "valid" for r in leg),
        sum(r["official_011"] == "invalid" for r in leg), Counter())
    for k, lab in (("none_eku", "reader: no trust list + c2pa-rs default EKU list"),
                   ("official", "reader: official list + TSA list, no EKU list (= 0.1.0 --trust-anchors)"),
                   ("official_eku", "reader: official list + TSA list + default EKU list (strict §15.8.2)"),
                   ("interim", "reader: interim list + its store.cfg"), ("both", "reader: official + interim + store.cfg")):
        have = [r for r in leg if r[f"{k}_state"]]
        row(lab, len(have), sum(r[f"{k}_trusted"] for r in have), sum(r[f"{k}_state"] == "Valid" and not r[f"{k}_core_fail"] for r in have),
            sum(bool(r[f"{k}_core_fail"]) or (r[f"{k}_state"] == "Invalid") for r in have),
            Counter(c for r in have for c in r[f"{k}_core_fail"].split("|") if c))
    for k, lab in (("old_codes", "c2pa-python 0.10.0 (c2pa-rs 0.55.0), defaults"), ("c2patool_codes", "c2patool 0.27.22, defaults")):
        cc = [r for r in leg if r[k] != "ERROR"]
        cnt = Counter(c for r in cc for c in core(r[k].split("|")))
        row(lab + (f"; cannot read {len(leg) - len(cc)}" if len(cc) < len(leg) else ""), len(cc), "–", "–",
            sum(1 for r in cc if core(r[k].split("|"))), cnt)
    H["cfg"] = cfg
    H["old_unreadable"] = dict(Counter(r["signer_org"] for r in leg if r["old_codes"] == "ERROR"))
    L.append("")

    # ---- failure classes (0.1.0 failures)
    fails = [r for r in c2u if r["c2pa"] in ("invalid", "unreadable")]
    only_cfg = [r for r in fails if r["c2pa_011"] == "valid"]
    H["fails010"] = [len(fails), sum(r["main"] for r in fails)]
    H["fails011"] = [sum(r["c2pa_011"] in ("invalid", "unreadable") for r in c2u), sum(r["c2pa_011"] in ("invalid", "unreadable") for r in c2u if r["main"])]
    H["only_config"] = [len(only_cfg), dict(Counter(r["failure_class"] for r in only_cfg))]
    cls = Counter(c for r in fails for c in r["failure_class"].split("+"))
    clm = Counter(c for r in fails if r["main"] for c in r["failure_class"].split("+"))
    H["classes"] = {k: [cls[k], clm[k]] for k in CLASS}
    H["class_D_by_signer"] = dict(Counter(r["signer_org"] for r in fails if "D" in r["failure_class"].split("+")))
    H["class_E_signer"] = dict(Counter(r["signer"] for r in fails if "E" in r["failure_class"].split("+")))
    H["class_F_generator"] = dict(Counter(r["claim_generator"] for r in fails if "F" in r["failure_class"].split("+")))
    L += ["## 8. Why manifests fail under ai-mark-lint 0.1.0 — union (main in brackets)", "",
          f"Failing under 0.1.0: {len(fails)} ({sum(r['main'] for r in fails)}). Failing under the 0.1.1 rule: {H['fails011'][0]} ({H['fails011'][1]}). "
          f"Failing under 0.1.0 only because of configuration (valid under 0.1.1): {len(only_cfg)} — by class {H['only_config'][1]}.", "",
          "| class (a file can have several) | union | main |", "|---|---|---|"]
    L += [f"| {CLASS[k]} | {cls[k]} | {clm[k]} |" for k in CLASS]
    L += ["", f"D by signer: {H['class_D_by_signer']}. E signer: {H['class_E_signer']}. F claim generator: {H['class_F_generator']}.",
          f"c2pa-python 0.10.0 cannot read: {H['old_unreadable']}.", ""]
    return H, L, rows


def main() -> None:
    H, L, rows = compute()
    cols = ["pageid", "title", "page_url", "month", "mime", "size", "stratum", "N", "in_category_tree", "in_pd_algorithm",
            "generator", "ai_evidence_rule", "main", "coats_of_arms", "ai_modified", "status", "sha1_match", "c2pa", "c2pa_011",
            "official_011", "c2pa_ai", "c2pa_dst", "iptc_dst", "iptc_ai", "aigc_ai", "aigc_double_encoded", "any_ai_mark",
            "signer", "signer_org", "claim_generator", "fail_codes", "failure_class", "none_eku_core_fail", "official_core_fail",
            "official_eku_state", "official_eku_core_fail", "interim_core_fail", "both_core_fail", "old_codes", "c2patool_codes",
            "tsa_time", "leaf_issuer", "leaf_not_before", "leaf_not_after", "leaf_eku", "root_issuer", "explanations", "rules", "checked_at"]
    with open(DATA / "per_file.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["month"], r["pageid"])):
            w.writerow(r)
    with open(DATA / "validation_failures.csv", "w", newline="") as fh:
        fc = ["pageid", "title", "page_url", "month", "main", "signer", "claim_generator", "c2pa", "c2pa_011", "fail_codes",
              "failure_class", "explanations", "tsa_time", "leaf_not_before", "leaf_not_after", "leaf_issuer", "leaf_eku",
              "none_eku_core_fail", "official_eku_state", "official_eku_core_fail", "old_codes", "c2patool_codes", "checked_at"]
        w = csv.DictWriter(fh, fieldnames=fc, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            if r.get("c2pa") in ("invalid", "unreadable"):
                w.writerow(r)
    (DATA / "summary.md").write_text("\n".join(L) + "\n")
    (DATA / "headline.json").write_text(json.dumps(H, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
