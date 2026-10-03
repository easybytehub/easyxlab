# S3 — Method

## 1. Research question

For each kind of machine-readable AI mark (embedded C2PA manifest, XMP IPTC `DigitalSourceType`, XMP `TC260:AIGC`), we ask which common transformations and libraries keep it, which break it (present but invalid), and which remove it. We also ask whether any trace remains after removal.

## 2. Tools and versions (last run: `data/versions.json`)

| tool | version | how obtained | why not the obvious alternative |
|---|---|---|---|
| c2patool | 0.27.22 (c2pa-rs 0.90.22) | official GitHub release binary (universal macOS) | the brew formula would have upgraded `openssl@4` |
| ExifTool | 13.55 | `brew install exiftool` (no dependencies) | – |
| Pillow | 12.3.0 (AVIF and WebP built in) | `.venv` | – |
| c2pa-python | 0.38.0 | `.venv` (installed, not needed in the end: c2patool covered signing and reading) | – |
| sharp | 0.35.5, bundling libvips 8.18.7 | local `node_modules` | sharp *is* the libvips most web stacks run, so no separate vips CLI was installed (the brew `vips` formula pulls poppler, gnupg and ~25 other dependencies) |
| ImageMagick | 7.1.2-32 Q8, official `@imagemagick/magick-wasm` 0.0.44 (wasm32) | local `node_modules` | the brew formula would have upgraded `x265`, whose soname the installed ffmpeg links against |
| ffmpeg | 8.1.2 | pre-installed (Homebrew) | – |

We read the Next.js image optimizer from the published package `next@16.3.8/dist/server/image-optimizer.js` (`optimizeImage()`), fetched from unpkg. We did not install it.

## 3. Corpus (`scripts/gen_corpus.py`)

- **Base image:** 800×600 RGB, a gradient plus 25 random discs (seed 42) and a text label. It is deterministic.
- **Image variants per format** (JPEG q90, PNG, WebP q85):
  - `none`
  - `xmp-dst`: ExifTool `-XMP-iptcExt:DigitalSourceType=http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia`
  - `aigc`: ExifTool with `scripts/exiftool-tc260.config`, `-XMP-TC260:AIGC={"Label":"1","ContentProducer":"EasyByteLabS3-TEST",...}`
  - `c2pa`: c2patool with `scripts/c2pa_manifest.json`, one `c2pa.created` action with `digitalSourceType=…/trainedAlgorithmicMedia`, ES256 test certificate from `tools/c2patool/sample/`, no TSA
  - `all`: XMP marks first, then C2PA, so the claim hashes the XMP
  - `all-remote`: as `all` plus `-r https://example.invalid/s3/manifests/remote-test.c2pa`, which embeds the manifest *and* writes `dcterms:provenance` into XMP
- **AV:**
  - `mp4-all`: 2 s testsrc2 320×240 H.264 + AAC, XMP marks + C2PA (BMFF)
  - `m4a-all`: 3 s AAC, same marks
  - `wav-c2pa`, `mp3-c2pa`: C2PA only (ExifTool cannot write RIFF/ID3)
- **Public:** `CA.jpg` from c2pa-rs test fixtures, pinned commit (MIT OR Apache-2.0). Other candidates (`mars.webp`, `sample1.webp`, `sample1.avif`, `libpng-test.png`) carry no manifest and were discarded. The `c2pa-org/public-testfiles` set is CC-BY-SA-4.0 and legacy 1.x, so we did not use it.

**Matrix inputs:** `jpg|png|webp-all-remote`, `mp4-all`, `m4a-all`, `wav-c2pa`, `mp3-c2pa`, `pub-CA`. Each input is also copied unchanged as the `identity` control. A mark is evaluated on an input's outputs only if the identity control carries it.

## 4. Transformations

**Pillow** (`scripts/transform_pillow.py`):
- `pil_resave`: `Image.open` → `save(same format)` with no kwargs.
- `pil_resave_keep`: same, with `exif=im.info["exif"]` and `xmp=im.info["xmp"]` when present. These are the documented save parameters.
- `pil_thumbnail`, `pil_thumbnail_keep`: `thumbnail((400,400))`, without and with the keep kwargs.
- `pil_to_webp(_keep)`, `pil_to_avif(_keep)`, `pil_to_jpeg`: format conversions, without and with the keep kwargs.
- `pil_resave_png_itxt`: PNG only, with `pnginfo` holding the iTXt `XML:com.adobe.xmp`.

**sharp** (`scripts/transform_node.mjs`):
- `sharp_resize` (400 px wide, same format) and its variants `_keepMetadata`, `_withMetadata`, `_keepXmp`, `_keepExif`.
- `sharp_to_webp(_keepMetadata)` and `sharp_to_avif(_keepMetadata)`.
- `nextimage_webp`: `rotate().resize(640, undefined, {withoutEnlargement:true}).webp({quality:75})`.
- `nextimage_avif`: as above but `.avif({quality: round(75*50/80), effort:3})`. Both are byte-for-byte the call chain in `optimizeImage()`, with Next's default quality of 75.

**ImageMagick** (`scripts/transform_node.mjs`, magick-wasm):
- `magick_resave`: read, then write in the same format.
- `magick_resize`: `resize(400,0)`.
- `magick_strip`: `strip()`.
- `magick_strip_resize`: `strip()` then `resize`.
- `magick_to_webp`: write as WebP.

**ExifTool** (`scripts/transform_cli.sh`):
- `exiftool_edit_title`: `-XMP-dc:Title="edited by pipeline"`, in place.
- `exiftool_strip_all`: `-all=`.
- `exiftool_restore_all`: `-tagsFromFile <original> -all:all` applied onto the stripped copy.

**ffmpeg** (`scripts/transform_cli.sh`):
- MP4/M4A:
  - `ffmpeg_remux`: `-c copy`.
  - `_remux_nometa`: adds `-map_metadata -1`.
  - `_faststart`: `-movflags +faststart`.
  - `_remux_usemeta`: `-map_metadata 0 -movflags use_metadata_tags`.
  - `_remux_exportxmp`: `-export_xmp 1` on input, plus `use_metadata_tags`.
  - `_reencode`, `_reencode_usemeta`: re-encode with libx264/AAC.
  - `_scale`, `_to_webm` (VP9/Opus), `_to_mp3`.
- WAV/MP3: `_remux`, `_remux_nometa`, `_reencode`, `_to_m4a`.

**Remediation:** `sharp_resize_keepMetadata_then_c2pa_resign` runs c2patool on the sharp `keepMetadata()` output with `-p <original>` (parent ingredient) and `scripts/c2pa_manifest_resize.json` (action `c2pa.resized`).

**Remote follow-up** (`scripts/remote_followup.sh`): sign `*-none` with `-s`, which writes a sidecar `.c2pa` and embeds nothing. Resize with sharp `keepMetadata()`. Validate both the original and the derivative with `--external-manifest <sidecar>`, offline.

## 5. Detection and classification (`scripts/detect.py`)

- **C2PA.** We run `c2patool <file>`. If it returns JSON, we read the failure codes from `validation_results.activeManifest.failure`.
  - **intact:** the failures are a subset of {`signingCredential.untrusted`, `signingCredential.ocsp.skipped`, `timeStamp.untrusted`}. These are expected with a test certificate.
  - **broken:** any other failure.
  - **removed:** no JSON.
  - **removed_residue:** no JSON, but the raw bytes still contain `c2pa.signature` or `c2pa.claim`.
  - The detail column also records whether `trainedAlgorithmicMedia` appears in the active manifest (`dst_active`) and in any manifest (`dst_any_manifest`, which covers ingredients).
- **XMP marks.** One batched ExifTool call per run with the TC260 config, reading `XMP-iptcExt:DigitalSourceType`, `XMP-TC260:AIGC` and `XMP-dcterms:Provenance`.
  - **survived:** the tag parses.
  - **residue:** the tag does not parse, but the namespace or property string is still in the bytes.
  - **removed:** neither.
- **Network.** c2patool tries to fetch remote manifests. The only URL in our corpus is under `.invalid` (RFC 2606), so the fetch fails at DNS and nothing leaves the machine. We did not use `ta_url` (TSA) or OCSP.

## 6. Documentary evidence (section 5 of the report)

We fetched official pages with `curl` on 2026-10-02 into `work/docs/` (not versioned), converted them to text with a minimal HTML stripper, and copied quotes **literally** from that text. Each page was requested once, between 17:30 and 17:32 CEST, with curl's default User-Agent (`curl/8.7.1`):
- Cloudflare Images "Preserve Content Credentials" and "Transform via URL → metadata".
- `WordPress/wordpress-develop` trunk `class-wp-image-editor-imagick.php`.
- Pillow image-file-formats handbook.
- Meta newsroom, February 2024.
- TikTok newsroom, May 2024.
- California SB 942 and AB 853: one request each to their bill pages on `leginfo.legislature.ca.gov`.
- AI Act Art. 50, from artificialintelligenceact.eu, because EUR-Lex blocked the automated fetch.

None of these behaviours was measured.

## 7. Threats to validity

- **Version drift:** each library is pinned to a single version.
- **ImageMagick:** the WASM build stands in for the CLI and PHP Imagick.
- **Corpus:** synthetic, with one image.
- **Certificate:** the test certificate means "intact" is never "trusted".
- **Scope:** soft bindings (watermarks, fingerprints) are not tested.
- **TC260:** the serialisation follows open-source implementations, not the standard's official text.
