#!/usr/bin/env bash
# exiftool + ffmpeg pipelines. Usage: transform_cli.sh <study_dir> <out_dir> <input>...
# Output name: <input_stem>__<transform>.<ext>
set -u
S="$1"; OUT="$2"; shift 2
mkdir -p "$OUT"
ET=(exiftool -config "$S/scripts/exiftool-tc260.config" -q -q)
FF=(ffmpeg -y -hide_banner -loglevel error)
for IN in "$@"; do
  b=$(basename "$IN"); stem="${b%.*}"; ext="${b##*.}"
  o() { echo "$OUT/${stem}__$1.${2:-$ext}"; }
  case "$ext" in
    jpg|png|webp|mp4|m4a)
      # 1) edit one unrelated metadata field in place (typical CMS/DAM "add title/credit")
      cp "$IN" "$(o exiftool_edit_title)"; "${ET[@]}" -overwrite_original -XMP-dc:Title="edited by pipeline" "$(o exiftool_edit_title)"
      # 2) privacy scrub: delete all metadata exiftool can delete
      cp "$IN" "$(o exiftool_strip_all)"; "${ET[@]}" -overwrite_original -all= "$(o exiftool_strip_all)"
      # 3) round trip: copy all tags from the original back onto a stripped copy
      cp "$(o exiftool_strip_all)" "$(o exiftool_restore_all)"; "${ET[@]}" -overwrite_original -tagsFromFile "$IN" -all:all "$(o exiftool_restore_all)"
      ;;
  esac
  case "$ext" in
    jpg|png|webp)
      # remediation: re-sign the processed derivative with the original as parent ingredient
      d="$OUT/${stem}__sharp_resize_keepMetadata.$ext"
      [ -f "$d" ] && "$S/tools/c2patool/c2patool" "$d" -p "$IN" -m "$S/scripts/c2pa_manifest_resize.json" \
        -o "$(o sharp_resize_keepMetadata_then_c2pa_resign)" -f >/dev/null 2>&1 || echo "resign failed for $stem" >&2
      ;;
    mp4|m4a)
      "${FF[@]}" -export_xmp 1 -i "$IN" -c copy -map_metadata 0 -movflags use_metadata_tags "$(o ffmpeg_remux_exportxmp)"
      "${FF[@]}" -i "$IN" -c copy "$(o ffmpeg_remux)"
      "${FF[@]}" -i "$IN" -c copy -map_metadata -1 "$(o ffmpeg_remux_nometa)"
      "${FF[@]}" -i "$IN" -c copy -movflags +faststart "$(o ffmpeg_faststart)"
      "${FF[@]}" -i "$IN" -map_metadata 0 -movflags use_metadata_tags -c copy "$(o ffmpeg_remux_usemeta)"
      if [ "$ext" = mp4 ]; then
        "${FF[@]}" -i "$IN" -c:v libx264 -crf 32 -c:a aac "$(o ffmpeg_reencode)"
        "${FF[@]}" -i "$IN" -c:v libx264 -crf 32 -c:a aac -map_metadata 0 -movflags use_metadata_tags "$(o ffmpeg_reencode_usemeta)"
        "${FF[@]}" -i "$IN" -vf scale=160:-2 -c:v libx264 -crf 32 -c:a aac "$(o ffmpeg_scale)"
        "${FF[@]}" -i "$IN" -c:v libvpx-vp9 -b:v 200k -c:a libopus "$(o ffmpeg_to_webm webm)"
      else
        "${FF[@]}" -i "$IN" -c:a aac -b:a 48k "$(o ffmpeg_reencode)"
        "${FF[@]}" -i "$IN" -c:a aac -b:a 48k -map_metadata 0 -movflags use_metadata_tags "$(o ffmpeg_reencode_usemeta)"
        "${FF[@]}" -i "$IN" -c:a libmp3lame -b:a 64k "$(o ffmpeg_to_mp3 mp3)"
      fi ;;
    wav|mp3)
      "${FF[@]}" -i "$IN" -c copy "$(o ffmpeg_remux)"
      "${FF[@]}" -i "$IN" -c copy -map_metadata -1 "$(o ffmpeg_remux_nometa)"
      if [ "$ext" = wav ]; then "${FF[@]}" -i "$IN" -ar 8000 "$(o ffmpeg_reencode)"; else "${FF[@]}" -i "$IN" -c:a libmp3lame -b:a 48k "$(o ffmpeg_reencode)"; fi
      "${FF[@]}" -i "$IN" -c:a aac -b:a 48k "$(o ffmpeg_to_m4a m4a)"
      # exiftool cannot write WAV/MP3 tags; strip test only where supported
      ;;
  esac
done
