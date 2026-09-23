#!/usr/bin/env bash
# Fetch/refresh everything the wiki is built from into source/ (gitignored):
#   source/matcha-flavoured  official repo (kleiwright/matcha-flavoured), for code + changelog.md
#   source/vanilla-data      vanilla data for the pack's Minecraft version (misode/mcmeta), for diffs
#   source/vanilla-assets    vanilla assets (lang, textures, models)
#   source/changelogs/       official Modrinth release notes, one file per version
# Usage:
#   tools/fetch_sources.sh            check out the pack at the commit pinned in tools/source.lock
#   tools/fetch_sources.sh --update   move to the latest origin/main and rewrite tools/source.lock
# The Minecraft version for vanilla data is read from tools/mc_version.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
UPDATE=0; [[ "${1:-}" == "--update" ]] && UPDATE=1
MC="$(cat tools/mc_version.txt)"
mkdir -p source source/changelogs

if [[ -d source/matcha-flavoured/.git ]]; then
  git -C source/matcha-flavoured fetch -q origin
else
  git clone -q https://github.com/kleiwright/matcha-flavoured.git source/matcha-flavoured
fi
if [[ $UPDATE == 1 ]]; then
  git -C source/matcha-flavoured checkout -q --detach origin/main
  git -C source/matcha-flavoured rev-parse HEAD > tools/source.lock
else
  git -C source/matcha-flavoured checkout -q --detach "$(cat tools/source.lock)"
fi

for kind in data-json:vanilla-data assets:vanilla-assets summary:vanilla-summary; do
  tag="$MC-${kind%%:*}"; dir="source/${kind##*:}"
  have="$(cat "$dir/.mcmeta-tag" 2>/dev/null || true)"
  if [[ "$have" != "$tag" ]]; then
    rm -rf "$dir"
    git clone -q --depth 1 --branch "$tag" https://github.com/misode/mcmeta.git "$dir"
    echo "$tag" > "$dir/.mcmeta-tag"
  fi
done

curl -fsSL "https://api.modrinth.com/v2/project/matcha-flavoured/version" -o source/modrinth_versions.json
python3 - <<'PY'
import json
for v in json.load(open('source/modrinth_versions.json')):
    rp = '-rp' if v['loaders'] == ['minecraft'] else ''
    fn = 'source/changelogs/%s_%s%s.md' % (v['date_published'][:10], v['version_number'], rp)
    open(fn, 'w').write('# %s — %s\nPublished: %s\nType: %s\nGame versions: %s\nLoaders: %s\nFiles: %s\n\n%s' % (
        v['version_number'], v['name'], v['date_published'], v['version_type'], v['game_versions'],
        v['loaders'], [f['filename'] for f in v['files']], v.get('changelog') or ''))
PY
echo "matcha-flavoured @ $(git -C source/matcha-flavoured rev-parse --short HEAD); vanilla $MC; $(ls source/changelogs | wc -l | tr -d ' ') changelogs"
