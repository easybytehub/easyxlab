// sharp (libvips) + ImageMagick (official WASM build) pipelines.
// Usage: node transform_node.mjs <out_dir> <input>...
// Output name: <input_stem>__<transform>.<ext>
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import sharp from 'sharp';
import { initializeImageMagick, ImageMagick, MagickFormat } from '@imagemagick/magick-wasm';

const require = createRequire(import.meta.url);
const [, , outDir, ...inputs] = process.argv;
fs.mkdirSync(outDir, { recursive: true });

const fmtOf = (p) => ({ '.jpg': 'jpeg', '.png': 'png', '.webp': 'webp' })[path.extname(p).toLowerCase()];
const extOf = (f) => ({ jpeg: 'jpg', png: 'png', webp: 'webp', avif: 'avif' })[f];

// Each sharp transform: (sharpInstance, inputFormat) => [instance, outFormat]
const SHARP = {
  sharp_resize: (s, f) => [s.resize(400), f],
  sharp_resize_keepMetadata: (s, f) => [s.resize(400).keepMetadata(), f],
  sharp_resize_withMetadata: (s, f) => [s.resize(400).withMetadata(), f],
  sharp_resize_keepXmp: (s, f) => [s.resize(400).keepXmp(), f],
  sharp_resize_keepExif: (s, f) => [s.resize(400).keepExif(), f],
  sharp_to_webp: (s) => [s.webp(), 'webp'],
  sharp_to_webp_keepMetadata: (s) => [s.webp().keepMetadata(), 'webp'],
  sharp_to_avif: (s) => [s.avif(), 'avif'],
  sharp_to_avif_keepMetadata: (s) => [s.avif().keepMetadata(), 'avif'],
  // Exact replica of next/image's optimizeImage() (next@16.3.8,
  // dist/server/image-optimizer.js): rotate(), resize(w,{withoutEnlargement}),
  // webp({quality}) / avif({quality: q*50/80, effort: 3}); default quality 75.
  nextimage_webp: (s) => [s.rotate().resize(640, undefined, { withoutEnlargement: true }).webp({ quality: 75 }), 'webp'],
  nextimage_avif: (s) => [s.rotate().resize(640, undefined, { withoutEnlargement: true }).avif({ quality: Math.max(Math.round(75 * (50 / 80)), 1), effort: 3 }), 'avif'],
};

const wasm = fs.readFileSync(path.join(path.dirname(require.resolve('@imagemagick/magick-wasm')), 'x86', 'magick.wasm'));
await initializeImageMagick(wasm);
const MF = { jpeg: MagickFormat.Jpeg, png: MagickFormat.Png, webp: MagickFormat.WebP };

// ImageMagick transforms: (image, inFmt) => outFmt
const MAGICK = {
  magick_resave: (img, f) => f,
  magick_resize: (img, f) => { img.resize(400, 0); return f; },
  magick_strip: (img, f) => { img.strip(); return f; },
  magick_strip_resize: (img, f) => { img.strip(); img.resize(400, 0); return f; },
  magick_to_webp: (img) => 'webp',
};

for (const inp of inputs) {
  const stem = path.basename(inp, path.extname(inp));
  const inFmt = fmtOf(inp);
  const buf = fs.readFileSync(inp);
  for (const [name, fn] of Object.entries(SHARP)) {
    try {
      const [inst, outFmt] = fn(sharp(buf), inFmt);
      await inst.toFile(path.join(outDir, `${stem}__${name}.${extOf(outFmt)}`));
    } catch (e) { console.error(`ERROR ${stem}__${name}: ${e.message}`); }
  }
  for (const [name, fn] of Object.entries(MAGICK)) {
    try {
      ImageMagick.read(buf, (img) => {
        const outFmt = fn(img, inFmt);
        img.write(MF[outFmt], (data) => fs.writeFileSync(path.join(outDir, `${stem}__${name}.${extOf(outFmt)}`), data));
      });
    } catch (e) { console.error(`ERROR ${stem}__${name}: ${e.message}`); }
  }
}
