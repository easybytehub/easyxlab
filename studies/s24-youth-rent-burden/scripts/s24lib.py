"""S24 shared constants and helpers (standard library only)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

R = Path(__file__).resolve().parent.parent
D = R / "data"
RAW = D / "raw"            # git-ignored: INE microdata and other downloads, never published
WORK = R / "work"          # git-ignored scratch
UA = "EasyxLab-research/1.0 (+https://github.com/easybytehub/easyxlab)"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def locked_inputs() -> list[dict]:
    with open(R / "scripts" / "locked_inputs.json", encoding="utf-8") as f:
        return json.load(f)["files"]


def wquantile(values, weights, q):
    """Weighted quantile (lower step function: smallest x with cumulative weight share >= q)."""
    pairs = sorted((v, w) for v, w in zip(values, weights) if w > 0)
    if not pairs:
        return float("nan")
    tot = sum(w for _, w in pairs)
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= q * tot - 1e-9:
            return v
    return pairs[-1][0]


def wmedian(values, weights):
    """Weighted median as Eurostat/INE compute it for EU-SILC: the mean of the two middle values when the
    cumulative weight hits exactly one half, otherwise the first value past one half."""
    pairs = sorted((v, w) for v, w in zip(values, weights) if w > 0)
    if not pairs:
        return float("nan")
    tot = sum(w for _, w in pairs)
    acc = 0.0
    for i, (v, w) in enumerate(pairs):
        acc += w
        if abs(acc - tot / 2) < 1e-9 * tot and i + 1 < len(pairs):
            return (v + pairs[i + 1][0]) / 2
        if acc > tot / 2:
            return v
    return pairs[-1][0]


def wmean(values, weights):
    sw = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / sw if sw else float("nan")


def wshare(flags, weights):
    sw = sum(weights)
    return 100.0 * sum(w for f, w in zip(flags, weights) if f) / sw if sw else float("nan")
