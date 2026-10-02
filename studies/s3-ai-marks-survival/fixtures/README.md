# S3 fixtures

`scripts/run.sh` generates these files (via `scripts/gen_corpus.py`). They are meant to be reused by other tools, in particular **ai-mark-lint** and its `--antes/--despues` mode. Total size is under 3 MB.

**All C2PA manifests are signed with the c2patool *test* certificate** (`es256_certs.pem` shipped with c2patool 0.27.22). Expected validation is therefore `Valid` with exactly one failure, `signingCredential.untrusted`. None of these files is real AI output: they are synthetic test pictures with test labels (`ContentProducer: EasyByteLabS3-TEST`). Signatures and instance IDs change on every regeneration, but the marks do not.

## Mark values

| mark | carrier | value |
|---|---|---|
| C2PA | JPEG APP11 JUMBF · PNG `caBX` · WebP `C2PA` chunk · BMFF `uuid` box · MP3 ID3 · WAV RIFF chunk | action `c2pa.created`, `digitalSourceType = http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia`, claim generator `EasyByte-Lab-S3-corpus 1.0`, claim thumbnail included |
| XMP DST | XMP `Iptc4xmpExt:DigitalSourceType` | `http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia` |
| AIGC | XMP `TC260:AIGC`, ns `http://www.tc260.org.cn/ns/AIGC/1.0/` | `{"Label":"1","ContentProducer":"EasyByteLabS3-TEST","ProduceID":"s3-fixture-0001","ReservedCode1":"","ContentPropagator":"","PropagateID":"","ReservedCode2":""}` |
| Remote ref | XMP `dcterms:provenance` | `https://example.invalid/s3/manifests/remote-test.c2pa` (never resolvable) |

ExifTool 13.55 has no built-in table for TC260. Use `exiftool -config scripts/exiftool-tc260.config -XMP-TC260:AIGC <file>`.

## `img/` — originals (JPEG, PNG, WebP; same 800×600 picture)

| file pattern | C2PA | XMP DST | AIGC | remote ref | use |
|---|---|---|---|---|---|
| `{jpg,png,webp}-none.*` | – | – | – | – | negative control |
| `{…}-xmp-dst.*` | – | ✓ | – | – | XMP-only (IPTC) |
| `{…}-aigc.*` | – | – | ✓ | – | AIGC-only (China) |
| `{…}-c2pa.*` | ✓ valid | – | – | – | C2PA-only |
| `{…}-all.*` | ✓ valid | ✓ | ✓ | – | all three marks |
| `{…}-all-remote.*` | ✓ valid | ✓ | ✓ | ✓ | all marks + remote reference (matrix input) |

Note: `webp-c2pa.webp` is about 278 KB against 18 KB for `webp-none.webp`. c2patool's default claim thumbnail for WebP is itself a large WebP.

## `av/` — originals

| file | C2PA | XMP DST | AIGC |
|---|---|---|---|
| `mp4-none.mp4` | – | – | – |
| `mp4-all.mp4` (2 s, H.264 + AAC) | ✓ valid (BMFF hash) | ✓ | ✓ |
| `m4a-all.m4a` (3 s AAC) | ✓ valid (BMFF hash) | ✓ | ✓ |
| `wav-c2pa.wav` | ✓ valid | – | – |
| `mp3-c2pa.mp3` | ✓ valid | – | – |

## `public/`

| file | source | licence | marks |
|---|---|---|---|
| `pub-CA.jpg` | c2pa-rs `sdk/tests/fixtures/CA.jpg` @ `518fe03a4a09dd38b68c1c5215d572fb1116bb66` | MIT OR Apache-2.0 | third-party C2PA manifest with an ingredient. Valid with an untrusted cert, **no** digitalSourceType |

## `derived/` — pipeline outputs ("after" files)

Name pattern: `<input>__<transform>.<ext>`. The matching "before" file is the input under `img/` or `av/`.

| file | expected marks after the pipeline |
|---|---|
| `jpg-all-remote__exiftool_edit_title.jpg` | C2PA **present but invalid** (`assertion.dataHash.mismatch`); XMP DST, AIGC and remote ref kept |
| `jpg-all-remote__sharp_resize.jpg` | everything removed (sharp default) |
| `jpg-all-remote__sharp_resize_keepMetadata.jpg` | C2PA removed; XMP DST, AIGC and remote ref kept |
| `jpg-all-remote__sharp_resize_keepMetadata_then_c2pa_resign.jpg` | C2PA valid (new manifest `c2pa.resized`, original as ingredient; DST only in the ingredient); XMP marks kept |
| `jpg-all-remote__nextimage_webp.webp` | everything removed (next/image optimizer logic) |
| `jpg-all-remote__magick_resize.jpg` | C2PA removed; XMP marks kept (ImageMagick default) |
| `jpg-all-remote__exiftool_restore_all.jpg` | C2PA and remote ref removed; XMP DST and AIGC restored |
| `png-all-remote__pil_resave_keep.png` | everything removed: Pillow's PNG writer ignores `xmp=` |
| `png-all-remote__pil_resave_png_itxt.png` | C2PA removed; XMP marks kept (iTXt via `pnginfo`) |
| `webp-all-remote__pil_to_avif_keep.avif` | C2PA removed; XMP marks kept in AVIF |
| `mp4-all__ffmpeg_remux.mp4` | everything removed (`-c copy`) |
| `mp4-all__ffmpeg_remux_exportxmp.mp4` | C2PA removed. The XMP packet survives only as a QuickTime `mdta` key `xmp` (residue: not readable as XMP) |
| `mp4-all__exiftool_edit_title.mp4` | C2PA **present but invalid** (`assertion.bmffHash.mismatch`); XMP marks kept |

`data/matrix.csv` holds the authoritative expected result for every output, including the ones not copied here.
