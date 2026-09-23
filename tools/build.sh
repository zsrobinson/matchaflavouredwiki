#!/usr/bin/env bash
# Full rebuild: extract data from source, generate pages and images, import into the running wiki.
#   ./tools/build.sh            everything
#   ./tools/build.sh --no-images  skip image upload (faster when only text changed)
set -euo pipefail
cd "$(dirname "$0")/.."
# serialise with tools/sync.sh and the dev watcher (they share build/import.xml)
mkdir -p build
until mkdir build/.sync.lock 2>/dev/null; do sleep 1; done
trap 'rmdir build/.sync.lock' EXIT

python3 tools/extract.py
python3 tools/images.py
python3 tools/generate.py
python3 tools/build_xml.py

C=matcha-wiki
docker exec "$C" php maintenance/run.php importDump --no-updates /build/import.xml
mv build/import_hashes.json.pending build/import_hashes.json
if [[ "${1:-}" != "--no-images" ]]; then
  # Upload only images whose bytes changed since the last upload (all of them the first time).
  python3 - <<'PY'
import hashlib, json, os, shutil
src, dst, cache = 'build/images', 'build/images_changed', 'build/image_hashes.json'
old = json.load(open(cache)) if os.path.exists(cache) else {}
shutil.rmtree(dst, ignore_errors=True); os.makedirs(dst)
new = {}
for f in sorted(os.listdir(src)):
    h = hashlib.sha1(open(os.path.join(src, f), 'rb').read()).hexdigest()
    new[f] = h
    if old.get(f) != h:
        shutil.copy(os.path.join(src, f), os.path.join(dst, f))
json.dump(new, open(cache + '.pending', 'w'))
print('images to upload:', len(os.listdir(dst)))
PY
  if [[ -n "$(ls build/images_changed)" ]]; then
    docker exec "$C" php maintenance/run.php importImages --overwrite \
      --comment "Texture from the Matcha Flavoured resource pack (CC BY-NC-SA 4.0)" /build/images_changed png gif
  fi
  mv build/image_hashes.json.pending build/image_hashes.json
fi
docker exec "$C" php maintenance/run.php rebuildrecentchanges >/dev/null
docker exec "$C" php maintenance/run.php refreshLinks >/dev/null 2>&1 || true
docker exec "$C" php maintenance/run.php purgeList --all-namespaces >/dev/null 2>&1 || true
docker exec "$C" php maintenance/run.php runJobs --quiet >/dev/null 2>&1 || true
# after refreshLinks: the article count ($wgArticleCountMethod = link) reads the pagelinks table
docker exec "$C" php maintenance/run.php initSiteStats --update >/dev/null
docker exec "$C" chown -R www-data:www-data /var/www/data /var/www/html/images
docker exec "$C" apache2ctl -k graceful >/dev/null 2>&1 || true  # drop APCu-cached renders
echo "Done: http://localhost:8080/w/Main_Page"
