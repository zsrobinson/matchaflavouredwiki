#!/usr/bin/env bash
# Full rebuild: extract data from source, generate pages and images, import into the running wiki.
#   ./tools/build.sh            everything
#   ./tools/build.sh --no-images  skip image upload (faster when only text changed)
set -euo pipefail
cd "$(dirname "$0")/.."

python3 tools/extract.py
python3 tools/images.py
python3 tools/generate.py
python3 tools/build_xml.py

C=matcha-wiki
docker exec "$C" php maintenance/run.php importDump --no-updates /build/import.xml
if [[ "${1:-}" != "--no-images" ]]; then
  docker exec "$C" php maintenance/run.php importImages --skip-dupes --overwrite \
    --comment "Texture from the Matcha Flavoured resource pack (CC BY-NC-SA 4.0)" /build/images png gif
fi
docker exec "$C" php maintenance/run.php rebuildrecentchanges >/dev/null
docker exec "$C" php maintenance/run.php initSiteStats --update >/dev/null
docker exec "$C" php maintenance/run.php refreshLinks >/dev/null 2>&1 || true
docker exec "$C" php maintenance/run.php purgeList --all-namespaces >/dev/null 2>&1 || true
docker exec "$C" php maintenance/run.php runJobs --quiet >/dev/null 2>&1 || true
docker exec "$C" chown -R www-data:www-data /var/www/data /var/www/html/images
echo "Done: http://localhost:8080/w/Main_Page"
