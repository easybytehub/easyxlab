#!/usr/bin/env python3
"""Step 3 — download each sampled file, inspect it, keep the result, delete the file.

For every row of data/sample.csv not yet in data/results.jsonl:
  1. download the original from upload.wikimedia.org (1 request/s, size cap), check its
     SHA-1 against the API value (proves we read the stored original);
  2. run the instrument, ai-mark-lint 0.1.0, as a CLI: `--format json --jurisdiction none`
     (record kept verbatim: marks + rule ids);
  3. if a C2PA manifest is there, characterise the validation result:
       - ai-mark-lint CLI again with `--trust-anchors` = official C2PA Trust List
         (signer list + TSA list, conformance-public @ pinned commit);
       - the c2pa Reader directly (c2pa-python 0.38.0 / c2pa-rs 0.91.0) under four trust
         configurations: none, official, interim (contentcredentials.org list + its EKU
         config), official+interim — keeping every failure code *with its explanation*;
       - c2pa-python 0.10.0 (c2pa-rs 0.55.0, separate venv) and c2patool 0.27.22, default
         settings, for a version comparison;
       - the certificate chain (`c2patool --certs`), saved by fingerprint in data/certs/
         (public certificates; the image itself is never kept);
  4. append one JSON line to data/results.jsonl and DELETE the file.
Never more than one image on disk at a time.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import commons  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DATA, WORK = HERE / "data", HERE / "work"
TMP = WORK / "tmp"
CERTS = DATA / "certs"
LINT = HERE / ".venv" / "bin" / "ai-mark-lint"
PY_OLD = WORK / "venv-old" / "bin" / "python"
C2PATOOL = Path(os.environ.get("C2PATOOL", HERE / "tools" / "c2patool" / "c2patool"))
TRUST = DATA / "trust"
OFFICIAL_BUNDLE = TRUST / "official-bundle.pem"  # signer list + TSA list
CAP = 120 * 1024 * 1024
# = c2pa-rs v0.91.0 sdk/src/crypto/cose/valid_eku_oids.cfg (its built-in default list)
EKU_DEFAULT = "\n".join(["1.3.6.1.5.5.7.3.4", "1.3.6.1.5.5.7.3.36", "1.3.6.1.5.5.7.3.8",
                         "1.3.6.1.5.5.7.3.9", "1.3.6.1.4.1.311.76.59.1.9", "1.3.6.1.4.1.62558.2.1"])
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
       "image/avif": ".avif", "image/heif": ".heif", "image/heic": ".heic"}

OLD_SNIPPET = r"""
import c2pa, json, sys
try:
    r = c2pa.Reader(sys.argv[1])
    d = json.loads(r.json())
    print(json.dumps({"ok": True, "status": d.get("validation_status", []),
                      "state": d.get("validation_state")}))
except Exception as e:
    print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}))
"""


def reader_cfg() -> dict:
    import c2pa

    off = OFFICIAL_BUNDLE.read_text()
    inter = (TRUST / "interim-anchors.pem").read_text()
    eku = (TRUST / "interim-store.cfg").read_text()
    base = {"verify": {"remote_manifest_fetch": False, "ocsp_fetch": False}}
    cfgs = {
        "none": base,
        "official": {**base, "verify": {**base["verify"], "verify_trust": True},
                     "trust": {"trust_anchors": off}},
        "interim": {**base, "verify": {**base["verify"], "verify_trust": True},
                    "trust": {"trust_anchors": inter, "trust_config": eku}},
        "both": {**base, "verify": {**base["verify"], "verify_trust": True},
                 "trust": {"trust_anchors": off + "\n" + inter, "trust_config": eku}},
        # c2pa-rs's own default EKU file (valid_eku_oids.cfg) passed explicitly: isolates
        # the EKU artefact (no trust list) and the official list with a proper EKU set.
        "none_eku": {**base, "trust": {"trust_config": EKU_DEFAULT}},
        "official_eku": {**base, "verify": {**base["verify"], "verify_trust": True},
                         "trust": {"trust_anchors": off, "trust_config": EKU_DEFAULT}},
    }
    return {k: c2pa.Context(c2pa.Settings.from_dict(v)) for k, v in cfgs.items()}


def read_direct(path: Path, ctx) -> dict:
    import c2pa

    try:
        r = c2pa.Reader(str(path), context=ctx)
    except c2pa.C2paError as exc:
        return {"error": f"{type(exc).__name__.lstrip('_')}: {exc}"[:400]}
    d = json.loads(r.json())
    act = (d.get("validation_results") or {}).get("activeManifest") or {}
    man = (d.get("manifests") or {}).get(d.get("active_manifest", ""), {})
    sig = man.get("signature_info") or {}
    out = {
        "state": str(r.get_validation_state() or ""),
        "failure": [[v.get("code"), (v.get("explanation") or "")[:240]] for v in act.get("failure", [])],
        "success": sorted({v.get("code") for v in act.get("success", [])}),
        "informational": [[v.get("code"), (v.get("explanation") or "")[:240]]
                          for v in act.get("informational", [])],
        "signature_info": {k: sig.get(k) for k in
                           ("alg", "issuer", "common_name", "cert_serial_number", "time")},
        "claim_generator": man.get("claim_generator"),
        "claim_generator_info": [
            {k: g.get(k) for k in ("name", "version")} if isinstance(g, dict) else g
            for g in man.get("claim_generator_info", []) or []],
        "claim_version": man.get("claim_version"),
        "n_manifests": len(d.get("manifests") or {}),
    }
    return out


def certs(path: Path) -> list[dict]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization

    try:
        p = subprocess.run([str(C2PATOOL), str(path), "--certs"], capture_output=True,
                           timeout=60, text=True)
    except Exception as exc:  # noqa: BLE001
        return [{"error": str(exc)[:200]}]
    if "BEGIN CERTIFICATE" not in p.stdout:
        return [{"error": (p.stderr or p.stdout)[:200]}]
    out = []
    CERTS.mkdir(exist_ok=True)
    try:
        chain = x509.load_pem_x509_certificates(p.stdout.encode())
    except Exception as exc:  # noqa: BLE001
        return [{"error": f"certificate parse failed: {exc}"[:200]}]
    for c in chain:
        fp = c.fingerprint(hashes.SHA256()).hex()
        f = CERTS / f"{fp[:16]}.pem"
        if not f.exists():
            f.write_bytes(c.public_bytes(serialization.Encoding.PEM))
        try:
            eku = [o.dotted_string for o in
                   c.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value]
        except x509.ExtensionNotFound:
            eku = []
        except Exception as exc:  # noqa: BLE001  e.g. non-canonical DER (xAI Grok Imagine)
            eku = [f"unparsable extensions: {type(exc).__name__}"]
        out.append({"fp": fp[:16], "subject": c.subject.rfc4514_string()[:200],
                    "issuer": c.issuer.rfc4514_string()[:200],
                    "not_before": c.not_valid_before_utc.isoformat(),
                    "not_after": c.not_valid_after_utc.isoformat(), "eku": eku})
    return out


def c2patool_default(path: Path) -> dict:
    try:
        p = subprocess.run([str(C2PATOOL), str(path), "--settings",
                            str(WORK / "c2patool-settings.json")],
                           capture_output=True, timeout=60, text=True)
        d = json.loads(p.stdout)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:200]}
    act = (d.get("validation_results") or {}).get("activeManifest") or {}
    return {"state": d.get("validation_state"),
            "failure": [[v.get("code"), (v.get("explanation") or "")[:200]]
                        for v in act.get("failure", [])] or
                       [[v.get("code"), (v.get("explanation") or "")[:200]]
                        for v in d.get("validation_status", [])]}


def lint(path: Path, anchors: Path | None = None) -> dict:
    cmd = [str(LINT), str(path), "--format", "json", "--jurisdiction", "none"]
    if anchors:
        cmd += ["--trust-anchors", str(anchors)]
    p = subprocess.run(cmd, capture_output=True, timeout=180, text=True)
    try:
        d = json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"exit": p.returncode, "error": (p.stderr or p.stdout)[:300]}
    marks = next(iter((d.get("marks") or {}).values()), None)
    return {"exit": p.returncode, "marks": marks,
            "findings": [[f["rule"], f["severity"], f.get("detail", "")[:300]]
                         for f in d.get("findings", [])]}


def details(path: Path) -> dict:
    """Values the CLI JSON does not print: digitalSourceType values, softwareAgent, signer."""
    from ai_mark_lint import marcas

    try:
        m = marcas.inventaria(path)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"[:300]}
    c = m.c2pa
    return {"format": m.formato, "c2pa_state": c.estado_en, "c2pa_fail": list(c.fallos),
            "c2pa_untrusted": c.no_confiable, "signer": c.firmante,
            "c2pa_dst": list(c.tipos_fuente), "c2pa_dst_ingredients": list(c.tipos_fuente_ingredientes),
            "agents": [list(a) for a in c.agentes][:5], "generator": [list(g) for g in c.generador][:5],
            "sign_time": c.hora_firma, "xmp_dst": [t for _, t in m.tipos_fuente_xmp],
            "aigc": [e.crudo[:300] for e in m.aigc], "ai_in_c2pa": m.ia_en_c2pa,
            "ai_in_xmp": m.ia_en_xmp, "ai_in_aigc": m.ia_en_aigc,
            "anomalies": m.anomalias[:5]}


def followup() -> None:
    """Re-read, under every trust configuration, the C2PA files measured before the
    `none_eku`/`official_eku` configurations were added (same download rules)."""
    out = DATA / "results_followup.jsonl"
    done = {json.loads(x)["pageid"] for x in out.open()} if out.exists() else set()
    url = {int(r["pageid"]): r for r in csv.DictReader(open(DATA / "sample.csv"))}
    todo = []
    for line in open(DATA / "results.jsonl"):
        r = json.loads(line)
        if r.get("reader") and "none_eku" not in r["reader"] and r["pageid"] not in done:
            todo.append(r["pageid"])
    print(f"follow-up: {len(todo)} files", flush=True)
    ctxs = reader_cfg()
    TMP.mkdir(parents=True, exist_ok=True)
    with out.open("a") as fh:
        for pid in todo:
            row = url[pid]
            path = TMP / f"{pid}{EXT.get(row['mime'], '.bin')}"
            rec = {"pageid": pid}
            try:
                commons.download(row["file_url"], path, CAP)
                rec["sha1_match"] = hashlib.sha1(path.read_bytes()).hexdigest() == row["sha1"]
                rec["reader"] = {k: read_direct(path, c) for k, c in ctxs.items()}
            except Exception as exc:  # noqa: BLE001
                rec["error"] = f"{type(exc).__name__}: {exc}"[:300]
            finally:
                path.unlink(missing_ok=True)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
    print("follow-up done", commons.REQUESTS, flush=True)


def main() -> None:
    if "--followup" in sys.argv:
        return followup()
    TMP.mkdir(parents=True, exist_ok=True)
    (WORK / "c2patool-settings.json").write_text(json.dumps(
        {"verify": {"remote_manifest_fetch": False, "ocsp_fetch": False}}))
    out = DATA / "results.jsonl"
    done = set()
    if out.exists():
        done = {json.loads(line)["pageid"] for line in out.open() if line.strip()}
    rows = list(csv.DictReader(open(DATA / "sample.csv")))
    todo = [r for r in rows if int(r["pageid"]) not in done]
    print(f"{len(rows)} sampled, {len(done)} done, {len(todo)} to do", flush=True)
    ctxs = reader_cfg()
    t0 = time.time()
    with out.open("a") as fh:
        for i, r in enumerate(todo, 1):
            rec = {"pageid": int(r["pageid"]), "title": r["title"], "page_url": r["page_url"],
                   "mime": r["mime"], "size": int(r["size"] or 0), "timestamp": r["timestamp"],
                   "stratum": r["stratum"], "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            ext = EXT.get(r["mime"])
            path = TMP / f"{r['pageid']}{ext or '.bin'}"
            try:
                if not ext:
                    rec["status"] = "skipped-unsupported-mime"
                elif int(r["size"] or 0) > CAP:
                    rec["status"] = "skipped-too-large"
                else:
                    commons.download(r["file_url"], path, CAP)
                    sha1 = hashlib.sha1(path.read_bytes()).hexdigest()
                    rec["sha1_match"] = sha1 == r["sha1"]
                    rec["lint"] = lint(path)
                    rec["details"] = details(path)
                    st = (rec["lint"].get("marks") or {}).get("c2pa", "")
                    if st and st != "absent":
                        rec["lint_official"] = lint(path, OFFICIAL_BUNDLE)
                        rec["reader"] = {k: read_direct(path, c) for k, c in ctxs.items()}
                        p = subprocess.run([str(PY_OLD), "-c", OLD_SNIPPET, str(path)],
                                           capture_output=True, timeout=120, text=True)
                        rec["old_c2pa_python_0_10"] = json.loads(p.stdout or '{"ok": false}')
                        rec["c2patool_0_27_22"] = c2patool_default(path)
                        rec["certs"] = certs(path)
                    rec["status"] = "ok"
            except Exception as exc:  # noqa: BLE001
                rec["status"] = "error"
                rec["error"] = f"{type(exc).__name__}: {exc}"[:300]
            finally:
                path.unlink(missing_ok=True)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if i % 25 == 0:
                el = time.time() - t0
                print(f"{i}/{len(todo)} · {el/i:.1f} s/file · {commons.REQUESTS}", flush=True)
    print("done", commons.REQUESTS, flush=True)


if __name__ == "__main__":
    main()
