#!/usr/bin/env bash
# Fast text-only sync: regenerate data pages and import only pages that changed.
#   ./tools/sync.sh            regenerate + import changed pages
#   ./tools/sync.sh --all      reimport every page
set -euo pipefail
cd "$(dirname "$0")/.."
C=matcha-wiki
python3 tools/generate.py >/dev/null
if [[ "${1:-}" == "--all" ]]; then python3 tools/build_xml.py; else python3 tools/build_xml.py --changed; fi
if grep -q "<page>" build/import.xml; then
  docker exec "$C" php maintenance/run.php importDump --no-updates /build/import.xml >/dev/null
  mv build/import_hashes.json.pending build/import_hashes.json
  # Purge changed titles so templates re-render
  grep -o "<title>[^<]*</title>" build/import.xml | sed 's/<title>//; s/<\/title>//' | python3 -c "import sys,html;print('\n'.join(html.unescape(l.strip()) for l in sys.stdin))" > build/changed_titles.txt
  docker exec -i "$C" php maintenance/run.php purgeList < build/changed_titles.txt >/dev/null 2>&1 || true
  docker exec "$C" php maintenance/run.php runJobs --quiet >/dev/null 2>&1 || true
  docker exec "$C" chown -R www-data:www-data /var/www/data
  echo "imported $(wc -l < build/changed_titles.txt | tr -d ' ') page(s)"
else
  rm -f build/import_hashes.json.pending
  echo "nothing changed"
fi
