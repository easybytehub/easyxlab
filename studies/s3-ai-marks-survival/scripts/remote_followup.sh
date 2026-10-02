#!/usr/bin/env bash
# Follow-up for the remote/sidecar case: is a surviving *reference* worth anything
# once the pixels were re-encoded? Validate derivatives against the original's
# sidecar manifest (--external-manifest), offline. Writes data/remote_followup.csv
set -eu
S="$1"; C="$S/tools/c2patool/c2patool"; W="$S/work/remote"; rm -rf "$W"; mkdir -p "$W"
echo "case,derivative,validation_state,failures" > "$S/data/remote_followup.csv"
for ext in jpg png webp; do
  src="$S/fixtures/img/$ext-none.$ext"
  "$C" "$src" -m "$S/scripts/c2pa_manifest.json" -s -o "$W/side.$ext" -f >/dev/null 2>&1
  node -e "
    const sharp=require('sharp');
    sharp('$W/side.$ext').resize(400).keepMetadata().toFile('$W/side-resized.$ext');
  " 2>/dev/null || node --input-type=module -e "
    import sharp from 'sharp'; await sharp('$W/side.$ext').resize(400).keepMetadata().toFile('$W/side-resized.$ext');"
  for f in side side-resized; do
    "$C" "$W/$f.$ext" --external-manifest "$W/side.c2pa" 2>&1 | python3 -c "
import sys,json
s=sys.stdin.read()
try:
  d=json.loads(s); fl=sorted({x['code'] for x in d['validation_results']['activeManifest']['failure']})
  print('$ext-sidecar,$f.$ext,'+str(d.get('validation_state'))+','+'|'.join(fl))
except Exception: print('$ext-sidecar,$f.$ext,error,'+s.strip().splitlines()[-1][:120].replace(',',';'))
" >> "$S/data/remote_followup.csv"
  done
done
cat "$S/data/remote_followup.csv"
