#!/usr/bin/env bash
# Dev server: keep http://localhost:8080 in sync with the working tree.
# Polls wiki/pages (and tools/generate.py) every few seconds and imports changed pages.
#   tools/watch.sh [interval-seconds]
set -uo pipefail
cd "$(dirname "$0")/.."
INTERVAL="${1:-5}"
docker compose up -d >/dev/null 2>&1
last=""
while true; do
  cur="$( (find wiki/pages -type f -newer build/.watch-stamp 2>/dev/null; find tools/generate.py -newer build/.watch-stamp 2>/dev/null) | head -1)"
  if [[ ! -f build/.watch-stamp || -n "$cur" ]]; then
    touch build/.watch-stamp
    out="$(tools/sync.sh 2>&1 | tail -1)"
    echo "[$(date +%H:%M:%S)] $out"
  fi
  sleep "$INTERVAL"
done
