#!/usr/bin/env python3
"""Pillow pipelines. Usage: transform_pillow.py <out_dir> <input>...
Output name: <input_stem>__<transform>.<ext>"""
import sys
from pathlib import Path

from PIL import Image, PngImagePlugin

FMT = {".jpg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "AVIF": "avif"}


def keep(im):
    """What a developer does to 'preserve metadata' with Pillow's documented
    save parameters: pass exif= and xmp= from im.info."""
    kw = {}
    if im.info.get("exif"):
        kw["exif"] = im.info["exif"]
    if im.info.get("xmp"):
        kw["xmp"] = im.info["xmp"]
    return kw


def png_xmp(im):
    """PNG: Pillow's PNG writer ignores xmp=; XMP must go in an iTXt chunk
    keyed 'XML:com.adobe.xmp' through pnginfo=."""
    pi = PngImagePlugin.PngInfo()
    if im.info.get("xmp"):
        x = im.info["xmp"]
        pi.add_itxt("XML:com.adobe.xmp", x.decode() if isinstance(x, bytes) else x)
    return {"pnginfo": pi}


def thumb(im):
    im = im.copy()
    im.thumbnail((400, 400))
    return im


# name -> (image op, target format or None=same, kwargs builder)
TRANSFORMS = {
    "pil_resave": (lambda im: im, None, lambda im: {}),
    "pil_resave_keep": (lambda im: im, None, keep),
    "pil_thumbnail": (thumb, None, lambda im: {}),
    "pil_thumbnail_keep": (thumb, None, keep),
    "pil_to_webp": (lambda im: im, "WEBP", lambda im: {}),
    "pil_to_webp_keep": (lambda im: im, "WEBP", keep),
    "pil_to_avif": (lambda im: im, "AVIF", lambda im: {}),
    "pil_to_avif_keep": (lambda im: im, "AVIF", keep),
    "pil_resave_png_itxt": (lambda im: im, "PNG", png_xmp),
    "pil_to_jpeg": (lambda im: im.convert("RGB"), "JPEG", lambda im: {}),
}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for inp in map(Path, sys.argv[2:]):
        for name, (op, tfmt, kwb) in TRANSFORMS.items():
            src = Image.open(inp)
            src.load()
            fmt = tfmt or FMT[inp.suffix.lower()]
            if name == "pil_to_jpeg" and fmt == FMT[inp.suffix.lower()]:
                continue  # same as pil_resave
            if name == "pil_resave_png_itxt" and inp.suffix.lower() != ".png":
                continue
            im = op(src)
            kw = kwb(src)
            # thumbnail() keeps .info on the copy; kwargs are taken from the source
            dst = out / f"{inp.stem}__{name}.{EXT[fmt]}"
            try:
                im.save(dst, fmt, **kw)
            except Exception as e:  # record, don't hide
                print(f"ERROR {dst.name}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
