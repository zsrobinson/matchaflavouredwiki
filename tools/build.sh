#!/usr/bin/env bash
# Full rebuild: extract data from source, generate pages and images, import into the running wiki.
#   ./tools/build.sh            everything
#   ./tools/build.sh --no-images  skip image upload (faster when only text changed)
# With MFW_BUILD_MODE=ci (a fresh wiki that is exported once, see LocalSettings.php) it skips the
# steps that only matter for browsing the local wiki.
set -euo pipefail
cd "$(dirname "$0")/.."
# serialise with tools/sync.sh and the dev watcher (they share build/import.xml)
mkdir -p build
until mkdir build/.sync.lock 2>/dev/null; do sleep 1; done
trap 'rmdir build/.sync.lock' EXIT
CI_BUILD=$([[ "${MFW_BUILD_MODE:-}" == ci ]] && echo 1 || true)
T=$SECONDS
step() { echo "[build] $1: $((SECONDS - T))s"; T=$SECONDS; }

python3 tools/extract.py; step extract
python3 tools/images.py; step images
python3 tools/generate.py; step generate
python3 tools/build_xml.py

C=matcha-wiki
docker exec "$C" php maintenance/run.php importDump --no-updates /build/import.xml
mv build/import_hashes.json.pending build/import_hashes.json
step "import pages"
if [[ "${1:-}" != "--no-images" ]]; then
  # Upload only images whose bytes changed since the last upload (all of them the first time).
  python3 - <<'PY'
import hashlib, json, os, shutil
src, dst, cache = 'build/images', 'build/images_changed', 'build/image_hashes.json'
old = json.load(open(cache)) if os.path.exists(cache) else {}
shutil.rmtree(dst, ignore_errors=True); os.makedirs(dst)
new = {}
for f in sorted(os.listdir(src)):
    if f.startswith('.'):  # tools/images.py's .inputs stamp
        continue
    h = hashlib.sha1(open(os.path.join(src, f), 'rb').read()).hexdigest()
    new[f] = h
    if old.get(f) != h:
        shutil.copy(os.path.join(src, f), os.path.join(dst, f))
json.dump(new, open(cache + '.pending', 'w'))
print('images to upload:', len(os.listdir(dst)))
PY
  if [[ -n "$(ls build/images_changed)" ]]; then
    docker exec "$C" php maintenance/run.php importImages --overwrite \
      --comment "Texture from the Matcha Flavoured resource pack (CC BY-NC-SA 4.0)" /build/images_changed png gif svg | sed "/^Importing .*done\.$/d"
  fi
  mv build/image_hashes.json.pending build/image_hashes.json
  # full-size renders for the image viewer (Gadget-mfwZoom.js): plain files, not uploads
  docker exec "$C" bash -c 'rm -rf /var/www/html/images/full && cp -r /build/images_full /var/www/html/images/full'
  step "import images"
fi
# Links tables (categories, the article count) and, in CI, the parser cache: one parse per page,
# one process per core. This is most of the build; refreshLinks.php did it on a single core.
N=$(docker exec "$C" nproc)
seq 0 $((N - 1)) | xargs -P "$N" -I{} docker exec "$C" php maintenance/run.php /var/www/site/renderPages.php --shard {} --shards "$N"
step "render pages"
if [[ -z "$CI_BUILD" ]]; then
  # the local wiki keeps its history and job queue; the static export has neither.
  # (purgeList would also invalidate the CI parser cache that renderPages.php just filled)
  docker exec "$C" php maintenance/run.php rebuildrecentchanges >/dev/null
  docker exec "$C" php maintenance/run.php purgeList --all-namespaces >/dev/null 2>&1 || true
  docker exec "$C" php maintenance/run.php runJobs --quiet >/dev/null 2>&1 || true
  step "recent changes, purge, jobs"
fi
# after the links tables: the article count ($wgArticleCountMethod = link) reads pagelinks
docker exec "$C" php maintenance/run.php initSiteStats --update >/dev/null
docker exec "$C" chown -R www-data:www-data /var/www/data /var/www/html/images
docker exec "$C" apache2ctl -k graceful >/dev/null 2>&1 || true  # drop APCu-cached renders
echo "Done: http://localhost:8080/w/Main_Page"
