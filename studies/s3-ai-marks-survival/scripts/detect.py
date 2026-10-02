#!/usr/bin/env python3
"""Detect every provenance mark in every pipeline output and write data/matrix.csv.
Usage: detect.py <study_dir> <out_dir>

Per output file and per mark carried by its input:
  c2pa            intact | broken | removed | removed_residue
  c2pa_remote_ref survived | removed            (XMP dcterms:provenance URL)
  xmp_dst         survived | removed | residue  (XMP Iptc4xmpExt:DigitalSourceType)
  aigc            survived | removed | residue  (XMP TC260:AIGC)
'intact' tolerates only trust-list failures (our test certificate is, by design,
not on any trust list). Anything else in the failure list (hash mismatch,
missing hard binding...) is 'broken'. A mark is only evaluated if the
unmodified input (transform 'identity') carries it.
"""
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

S = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
C2PATOOL = S / "tools/c2patool/c2patool"
ETCFG = S / "scripts/exiftool-tc260.config"
TRUST_ONLY = {"signingCredential.untrusted", "signingCredential.ocsp.skipped", "timeStamp.untrusted"}
MARKS = ["c2pa", "c2pa_remote_ref", "xmp_dst", "aigc"]


def versions():
    v = {}
    v["c2patool"] = subprocess.run([C2PATOOL, "--version"], capture_output=True, text=True).stdout.strip()
    v["exiftool"] = subprocess.run(["exiftool", "-ver"], capture_output=True, text=True).stdout.strip()
    v["ffmpeg"] = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.split("\n")[0].split(" ")[2]
    import PIL
    v["Pillow"] = PIL.__version__
    pj = lambda p: json.loads((S / "node_modules" / p / "package.json").read_text())["version"]
    v["sharp"] = pj("sharp")
    v["magick-wasm"] = pj("@imagemagick/magick-wasm")
    return v


def library(transform, v):
    if transform == "identity":
        return "-"
    pre = transform.split("_")[0]
    return {
        "pil": f"Pillow {v['Pillow']}",
        "sharp": f"sharp {v['sharp']} (libvips)",
        "nextimage": f"sharp {v['sharp']} via next/image optimizer logic",
        "magick": f"ImageMagick (magick-wasm {v['magick-wasm']})",
        "exiftool": f"ExifTool {v['exiftool']}",
        "ffmpeg": f"ffmpeg {v['ffmpeg']}",
    }.get(pre, pre)


def c2pa_state(path: Path, raw: bytes):
    try:
        r = subprocess.run([C2PATOOL, path], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return "error", "c2patool timeout"
    out = r.stdout.strip()
    if r.returncode == 0 and out.startswith("{"):
        d = json.loads(out)
        fails = sorted({f["code"] for f in (d.get("validation_results") or {}).get("activeManifest", {}).get("failure", [])})
        # legacy flat list as fallback
        if not fails and d.get("validation_status"):
            fails = sorted({s["code"] for s in d["validation_status"] if "untrusted" in s["code"] or "mismatch" in s["code"] or "missing" in s["code"]})
        am = d["manifests"].get(d.get("active_manifest"), {})
        dst = "trainedAlgorithmicMedia" in json.dumps(am.get("assertions", []))
        dst_any = "trainedAlgorithmicMedia" in json.dumps(d["manifests"])
        state = "intact" if set(fails) <= TRUST_ONLY else "broken"
        return state, f"state={d.get('validation_state')}; failures={'|'.join(fails) or '-'}; dst_active={dst}; dst_any_manifest={dst_any}; manifests={len(d['manifests'])}"
    msg = (r.stderr or r.stdout).strip().splitlines()
    msg = msg[-1][:160] if msg else ""
    residue = (b"c2pa.signature" in raw) or (b"c2pa.claim" in raw)
    return ("removed_residue" if residue else "removed"), msg


def main():
    v = versions()
    files = sorted(p for p in OUT.iterdir() if p.is_file() and "__" in p.name)
    et = subprocess.run(["exiftool", "-config", ETCFG, "-j", "-G1",
                         "-XMP-iptcExt:DigitalSourceType", "-XMP-TC260:AIGC", "-XMP-dcterms:Provenance",
                         *map(str, files)], capture_output=True, text=True)
    meta = {Path(d["SourceFile"]).name: d for d in json.loads(et.stdout or "[]")}

    rows, by_input = [], defaultdict(dict)
    for f in files:
        stem, tr = f.stem.split("__", 1)
        raw = f.read_bytes()
        m = meta.get(f.name, {})
        st = {}
        st["c2pa"] = c2pa_state(f, raw)
        st["c2pa_remote_ref"] = ("survived", m["XMP-dcterms:Provenance"]) if "XMP-dcterms:Provenance" in m else \
            (("residue", "provenance string in bytes") if b"example.invalid/s3" in raw else ("removed", ""))
        if "XMP-iptcExt:DigitalSourceType" in m:
            st["xmp_dst"] = ("survived", m["XMP-iptcExt:DigitalSourceType"].rsplit("/", 1)[-1])
        else:
            st["xmp_dst"] = ("residue", "Iptc4xmpExt string in bytes, not parseable") if b"Iptc4xmpExt:DigitalSourceType" in raw or b"<Iptc4xmpExt:DigitalSourceType" in raw else ("removed", "")
        if "XMP-TC260:AIGC" in m:
            st["aigc"] = ("survived", "TC260:AIGC parsed")
        else:
            st["aigc"] = ("residue", "tc260 namespace in bytes, not parseable") if b"tc260.org.cn/ns/AIGC" in raw else ("removed", "")
        by_input[stem][tr] = (f, st)

    for stem, trs in sorted(by_input.items()):
        base = trs.get("identity")
        if not base:
            continue
        carried = [mk for mk in MARKS if base[1][mk][0] in ("intact", "survived")]
        for tr, (f, st) in sorted(trs.items(), key=lambda kv: (kv[0] != "identity", kv[0])):
            for mk in carried:
                res, det = st[mk]
                rows.append({
                    "input": stem,
                    "input_format": base[0].suffix.lstrip("."),
                    "library": library(tr, v),
                    "transform": tr,
                    "output_format": f.suffix.lstrip("."),
                    "output_bytes": f.stat().st_size,
                    "mark": mk,
                    "result": res,
                    "detail": det,
                })
    (S / "data").mkdir(exist_ok=True)
    with open(S / "data/matrix.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (S / "data/versions.json").write_text(json.dumps(v, indent=2) + "\n")
    print(f"{len(rows)} rows, {len(files)} files; versions: {v}")


if __name__ == "__main__":
    main()
