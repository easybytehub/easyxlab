#!/usr/bin/env bash
# Regenerates the S3 corpus and the full survival matrix.
#   scripts/run.sh            # setup (idempotent) + corpus + pipelines + matrix
# Requirements: macOS/Linux with python3, node>=18, ffmpeg, exiftool (brew install exiftool).
set -euo pipefail
S="$(cd "$(dirname "$0")/.." && pwd)"
cd "$S"
C2PA_VER=0.27.22

# ---------- setup (idempotent) ----------
if [ ! -x tools/c2patool/c2patool ]; then
  mkdir -p tools && cd tools
  case "$(uname -s)" in
    Darwin) asset="c2patool-v${C2PA_VER}-universal-apple-darwin.zip" ;;
    *) asset="c2patool-v${C2PA_VER}-x86_64-unknown-linux-gnu.tar.gz" ;;
  esac
  curl -sfL -o "$asset" "https://github.com/contentauth/c2pa-rs/releases/download/c2patool-v${C2PA_VER}/${asset}"
  case "$asset" in *.zip) unzip -oq "$asset" ;; *) tar xzf "$asset" ;; esac
  rm -f "$asset"; cd "$S"
fi
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q "Pillow==12.3.0" "c2pa-python==0.38.0"; }
[ -d node_modules/sharp ] || npm install --no-audit --no-fund "sharp@0.35.5" "@imagemagick/magick-wasm@0.0.44"
command -v exiftool >/dev/null || { echo "exiftool missing (brew install exiftool)"; exit 1; }
command -v ffmpeg  >/dev/null || { echo "ffmpeg missing"; exit 1; }

# ---------- 1. corpus ----------
.venv/bin/python scripts/gen_corpus.py "$S"
# public C2PA sample files (c2pa-rs test fixtures, MIT OR Apache-2.0), pinned commit
PUB_REF="${PUB_REF:-518fe03a4a09dd38b68c1c5215d572fb1116bb66}"
mkdir -p fixtures/public
for f in CA.jpg; do
  [ -f "fixtures/public/pub-$f" ] || curl -sfL -o "fixtures/public/pub-$f" \
    "https://raw.githubusercontent.com/contentauth/c2pa-rs/${PUB_REF}/sdk/tests/fixtures/$f"
done

# ---------- 2. pipelines ----------
OUT=work/out; rm -rf "$OUT"; mkdir -p "$OUT"
IMG=(fixtures/img/jpg-all-remote.jpg fixtures/img/png-all-remote.png fixtures/img/webp-all-remote.webp fixtures/public/pub-CA.jpg)
AV=(fixtures/av/mp4-all.mp4 fixtures/av/m4a-all.m4a fixtures/av/wav-c2pa.wav fixtures/av/mp3-c2pa.mp3)
for f in "${IMG[@]}" "${AV[@]}"; do b=$(basename "$f"); cp "$f" "$OUT/${b%.*}__identity.${b##*.}"; done
.venv/bin/python scripts/transform_pillow.py "$OUT" "${IMG[@]}"
node scripts/transform_node.mjs "$OUT" "${IMG[@]}"
bash scripts/transform_cli.sh "$S" "$OUT" "${IMG[@]}" "${AV[@]}"

# ---------- 3. detection -> data/matrix.csv ----------
.venv/bin/python scripts/detect.py "$S" "$OUT"
.venv/bin/python scripts/summarize.py "$S"

# ---------- 4. remote/sidecar follow-up -> data/remote_followup.csv ----------
NODE_PATH="$S/node_modules" bash scripts/remote_followup.sh "$S"

# ---------- 5. derived fixtures (before/after pairs for ai-mark-lint --antes/--despues) ----------
DER=fixtures/derived; rm -rf "$DER"; mkdir -p "$DER"
for f in \
  jpg-all-remote__exiftool_edit_title.jpg \
  jpg-all-remote__sharp_resize.jpg \
  jpg-all-remote__sharp_resize_keepMetadata.jpg \
  jpg-all-remote__sharp_resize_keepMetadata_then_c2pa_resign.jpg \
  jpg-all-remote__nextimage_webp.webp \
  jpg-all-remote__magick_resize.jpg \
  jpg-all-remote__exiftool_restore_all.jpg \
  png-all-remote__pil_resave_keep.png \
  png-all-remote__pil_resave_png_itxt.png \
  webp-all-remote__pil_to_avif_keep.avif \
  mp4-all__ffmpeg_remux.mp4 \
  mp4-all__ffmpeg_remux_exportxmp.mp4 \
  mp4-all__exiftool_edit_title.mp4 ; do
  cp "work/out/$f" "$DER/$f"
done
du -sh fixtures
