#!/usr/bin/env bash
# S6 — Do AI-generated images on Wikimedia Commons carry provenance marks?
#   scripts/run.sh            # setup (idempotent) + enumerate + sample + measure + analyze
#   scripts/run.sh analyze    # only rebuild the tables and check the headlines from data/ (offline, no setup)
# Requirements: python3 >= 3.11, curl, unzip. Network: Commons API + upload.wikimedia.org
# (1 request/s, read-only), GitHub (pinned tool and trust-list downloads).
# Disk: ~170 MB of local tooling; at most one image (<= 120 MB) on disk at any time.
# Time: enumeration ~25 min, measurement ~1.5-2 h for the default sample.
set -euo pipefail
S="$(cd "$(dirname "$0")/.." && pwd)"
cd "$S"
if [ "${1:-}" = "analyze" ]; then   # tables + headline check from data/ only: stdlib, offline, no setup
  python3 scripts/analyze.py > /dev/null && python3 scripts/check_headlines.py
  exit $?
fi
C2PA_VER=0.27.22
LINT_URL="https://github.com/easybytehub/ai-mark-lint/releases/download/v0.1.0/ai_mark_lint-0.1.0-py3-none-any.whl"
LINT_SHA256="1b5a2ae6b8660a55f99ce7df48b38bc3df305f25778c83bdd7450e478018e1f9"
TRUST_REF="3573be509a793a989f093df4f86744a3632f6155"   # c2pa-org/conformance-public, 2026-10-01

# ---------- setup (idempotent) ----------
mkdir -p tools work data/trust
if [ ! -x tools/c2patool/c2patool ]; then
  (cd tools
   case "$(uname -s)" in
     Darwin) asset="c2patool-v${C2PA_VER}-universal-apple-darwin.zip" ;;
     *) asset="c2patool-v${C2PA_VER}-x86_64-unknown-linux-gnu.tar.gz" ;;
   esac
   curl -sfL -o "$asset" "https://github.com/contentauth/c2pa-rs/releases/download/c2patool-v${C2PA_VER}/${asset}"
   case "$asset" in *.zip) unzip -oq "$asset" ;; *) tar xzf "$asset" ;; esac
   rm -f "$asset")
fi
if [ ! -x .venv/bin/ai-mark-lint ]; then
  curl -sfL -o tools/ai_mark_lint-0.1.0-py3-none-any.whl "$LINT_URL"
  echo "$LINT_SHA256  tools/ai_mark_lint-0.1.0-py3-none-any.whl" | shasum -a 256 -c -
  python3 -m venv .venv
  .venv/bin/pip install -q tools/ai_mark_lint-0.1.0-py3-none-any.whl "c2pa-python==0.38.0"
fi
[ -x work/venv-old/bin/python ] || { python3 -m venv work/venv-old && work/venv-old/bin/pip install -q "c2pa-python==0.10.0"; }
T=https://raw.githubusercontent.com/c2pa-org/conformance-public/${TRUST_REF}/trust-list
[ -f data/trust/official-C2PA-TRUST-LIST.pem ] || curl -sfL -o data/trust/official-C2PA-TRUST-LIST.pem "$T/C2PA-TRUST-LIST.pem"
[ -f data/trust/official-C2PA-TSA-TRUST-LIST.pem ] || curl -sfL -o data/trust/official-C2PA-TSA-TRUST-LIST.pem "$T/C2PA-TSA-TRUST-LIST.pem"
[ -f data/trust/official-C2PA-TRUST-LIST.json ] || curl -sfL -o data/trust/official-C2PA-TRUST-LIST.json "$T/C2PA-TRUST-LIST.json"
cat data/trust/official-C2PA-TRUST-LIST.pem data/trust/official-C2PA-TSA-TRUST-LIST.pem > data/trust/official-bundle.pem
# Interim list (frozen; served by verify.contentauthenticity.org). Kept in data/trust/ as fetched on 2026-10-02.
[ -f data/trust/interim-anchors.pem ] || curl -sfL -o data/trust/interim-anchors.pem https://contentcredentials.org/trust/anchors.pem
[ -f data/trust/interim-store.cfg ] || curl -sfL -o data/trust/interim-store.cfg https://contentcredentials.org/trust/store.cfg

if [ "${1:-}" != "analyze" ]; then
  # ---------- 1. population (metadata only) ----------
  [ -f data/population.csv.gz ] || .venv/bin/python scripts/enumerate.py 6
  # ---------- 2. stratified sample + categories of sampled files ----------
  [ -f data/sample.csv ] || .venv/bin/python scripts/sample.py
  # categories drift daily: fetch once, then only re-derive flags offline
  if [ -f work/sample_categories_full.csv ]; then .venv/bin/python scripts/fetch_meta.py derive; else .venv/bin/python scripts/fetch_meta.py; fi
  # ---------- 3. download one by one -> ai-mark-lint -> result -> delete (resumable) ----------
  .venv/bin/python scripts/measure.py
  .venv/bin/python scripts/measure.py --followup   # no-op when every C2PA record already has all six configurations
  .venv/bin/python scripts/sanitize.py             # idempotent: traces, paths, device certificates, user-named categories
fi
# ---------- 4. tables + headline check ----------
python3 scripts/analyze.py > /dev/null
python3 scripts/check_headlines.py
