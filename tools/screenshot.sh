#!/usr/bin/env bash
# Screenshot a wiki page with headless Chrome: tools/screenshot.sh "Page_title" out.png [width] [height]
set -euo pipefail
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size="${3:-1400},${4:-1800}" \
  --screenshot="$2" "http://localhost:8080/w/$1" >/dev/null 2>&1
