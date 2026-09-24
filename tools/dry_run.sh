#!/usr/bin/env bash
# Rehearse an update before it lands: build the data from another branch of the pack (e.g. the port to
# the next Minecraft version) in a throwaway copy of tools/ and wiki/ (as they are in the working tree,
# so it can be rerun while fixing the extractor) and report what would break. Nothing here changes
# except build/dry-run-<ref>.md.
#   tools/dry_run.sh 26.3
# Runs extract.py (format problems: keys, types or functions it doesn't know), generate.py,
# update_report.py (what the update would change, against the current build/data.json) and
# lint_pages.py (hand-written pages that would go stale). Needs source/ and build/data.json from
# tools/fetch_sources.sh and tools/extract.py.
set -uo pipefail
cd "$(dirname "$0")/.."
REF="${1:?usage: tools/dry_run.sh <branch or commit of the pack>}"
ROOT="$PWD"
DIR="$(mktemp -d "${TMPDIR:-/tmp}/mfw-dry-run.XXXXXX")"
OUT="$ROOT/build/dry-run-${REF//\//-}.md"
trap 'rm -rf "$DIR"' EXIT

[[ -f build/data.json ]] || { echo "run tools/fetch_sources.sh and tools/extract.py first"; exit 2; }
mkdir -p "$DIR/wiki/source" "$DIR/wiki/build"
cp -a tools "$DIR/wiki/"
cp -al wiki "$DIR/wiki/" 2>/dev/null || cp -a wiki "$DIR/wiki/"  # generate.py replaces files, never edits them
cd "$DIR/wiki"
# reuse what is already downloaded: the pack's objects, and vanilla data if the version stays the same
git clone -q --shared "$ROOT/source/matcha-flavoured" source/matcha-flavoured
git -C source/matcha-flavoured remote set-url origin https://github.com/kleiwright/matcha-flavoured.git
for d in vanilla-data vanilla-assets vanilla-summary; do cp -al "$ROOT/source/$d" source/ 2>/dev/null || cp -a "$ROOT/source/$d" source/; done
cp "$ROOT/build/data.json" build/data.before.json
tools/fetch_sources.sh --ref "$REF" >/dev/null || exit 2

{
  echo "# Dry run: pack at $REF ($(cut -c1-8 tools/source.lock)), Minecraft $(cat tools/mc_version.txt)"
  echo
  echo "## tools/extract.py"
  echo '```'
  python3 tools/extract.py --allow-unknown 2>&1
  echo '```'
  echo
  echo "## tools/lint_pages.py"
  echo '```'
  python3 tools/generate.py >/dev/null 2>&1 || echo "generate.py failed"
  python3 tools/lint_pages.py 2>&1
  echo '```'
  echo
  python3 tools/update_report.py >/dev/null && sed 's/^#/##/' build/update-report.md
} > "$OUT"
grep -A30 '^## tools/extract.py' "$OUT" | sed -n '3,30p' | sed '/^```/,$d'
echo "Full report: ${OUT#$ROOT/}"
