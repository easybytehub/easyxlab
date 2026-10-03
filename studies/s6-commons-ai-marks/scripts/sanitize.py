#!/usr/bin/env python3
"""Step 3c — make data/ publishable (idempotent; run once after measurement).

1. results*.jsonl: drop Python `trace` fields and machine paths.
2. Two September 2026 records (xAI Grok Imagine manifests) were fully measured by
   ai-mark-lint but marked `error` because *our* certificate-extraction step raised
   (`cryptography` rejects a non-canonical DER BasicConstraints in their self-signed
   certificate). They are restored to `ok`; their `certs` field records the failure.
   measure.py now catches this per certificate.
3. Samsung device-attestation certificates (subject with a per-device hash, phone model
   and attestation UID) are reduced to their issuing organisation.
4. Categories named after users are never published: the raw category lists stay in
   work/ (see fetch_meta.py); in category_tree.csv, population.csv.gz and sample.csv
   such categories are replaced by "Category:[user-named category NN]".
5. data/certs/: delete PEMs that are Samsung device certificates, test certificates, or
   referenced by no record.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DATA, WORK = HERE / "data", HERE / "work"
PATH_RX = re.compile(r"/(?:Users|home|private|tmp)/[^\s\"']+")
DEVICE_RX = re.compile(r"SAK_V2|DC=SM-|UID=", re.I)
CERT_FAIL = "certificate extraction failed (cryptography: non-canonical DER BasicConstraints)"
GENERIC_PROMPTER = {"Category:AI-generated images by human prompter", "Category:AI-generated images by Commons users",
                    "Category:Midjourney works by Commons users", "Category:Stable Diffusion works by Commons users",
                    "Category:Deep Dream Generator works by Commons users", "Category:AI-generated videos by Commons users"}
USER_RX = re.compile(r"\buser\b|uploaded by|\bfiles by\b|taken by", re.I)


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items() if k != "trace"}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, str):
        return PATH_RX.sub(lambda m: Path(m.group(0)).name, o)
    return o


def redact_cert(c: dict) -> dict:
    if any(DEVICE_RX.search(c.get(k, "")) for k in ("subject", "issuer")):
        org = "Samsung" if "samsung" in json.dumps(c).lower() or "SM-" in json.dumps(c) else "device"
        return {"fp": "redacted", "subject": f"[{org} device attestation certificate, redacted]",
                "issuer": f"O={org} (redacted)", "not_before": c.get("not_before", ""),
                "not_after": c.get("not_after", ""), "eku": c.get("eku", [])}
    return c


def jsonl(path: Path) -> None:
    if not path.exists():
        return
    out = []
    for line in path.open():
        r = clean(json.loads(line))
        if r.get("status") == "error" and (r.get("lint") or {}).get("marks") and "asn1" in r.get("error", ""):
            r["status"] = "ok"
            r["certs"] = [{"error": CERT_FAIL}]
            r["note"] = "restored by sanitize.py: measured by ai-mark-lint; only certificate extraction failed"
            r.pop("error", None)
        if r.get("certs"):
            r["certs"] = [redact_cert(c) for c in r["certs"]]
        out.append(json.dumps(r, ensure_ascii=False))
    path.write_text("\n".join(out) + "\n")


def user_categories() -> dict[str, str]:
    tree = list(csv.DictReader(open(DATA / "category_tree.csv")))
    parent = {r["category"]: r["parent"] for r in tree}

    def under_prompter(c: str) -> bool:
        while c:
            if c == "Category:AI-generated images by human prompter":
                return True
            c = parent.get(c, "")
        return False

    names = [r["category"] for r in tree if (under_prompter(r["category"]) and r["category"] not in GENERIC_PROMPTER)
             or USER_RX.search(r["category"])]
    return {c: f"Category:[user-named category {i:02d}]" for i, c in enumerate(sorted(names), 1)}


def main() -> None:
    for f in ("results.jsonl", "results_followup.jsonl"):
        jsonl(DATA / f)
    mapping = user_categories()
    if mapping:
        rows = list(csv.DictReader(open(DATA / "category_tree.csv")))
        with open(DATA / "category_tree.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            for r in rows:
                r["category"] = mapping.get(r["category"], r["category"])
                r["parent"] = mapping.get(r["parent"], r["parent"])
                w.writerow(r)
        for path, opener in ((DATA / "population.csv.gz", lambda p, m: gzip.open(p, m + "t", newline="")),
                             (DATA / "sample.csv", lambda p, m: open(p, m, newline=""))):
            rows = list(csv.DictReader(opener(path, "r")))
            with opener(path, "w") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                for r in rows:
                    r["found_in"] = mapping.get(r["found_in"], r["found_in"])
                    w.writerow(r)
    # sample_categories.csv must hold flags only (fetch_meta.py derive)
    head = open(DATA / "sample_categories.csv").readline()
    assert "categories" not in head.split(","), "run fetch_meta.py derive first"
    # certificates
    refs = set()
    for line in (DATA / "results.jsonl").open():
        for c in json.loads(line).get("certs") or []:
            refs.add(c.get("fp"))
    removed = []
    for pem in (DATA / "certs").glob("*.pem"):
        txt = pem.read_text()
        try:
            from cryptography import x509
            subj = x509.load_pem_x509_certificate(txt.encode()).subject.rfc4514_string()
        except Exception:  # noqa: BLE001
            subj = ""
        if pem.stem not in refs or DEVICE_RX.search(subj) or "TESTING_ONLY" in subj or "Test Signing" in subj:
            pem.unlink()
            removed.append((pem.stem, subj[:60]))
    print(f"user-named categories redacted: {len(mapping)}; certificates removed: {len(removed)}")
    for r in removed:
        print("   ", r)


if __name__ == "__main__":
    main()
