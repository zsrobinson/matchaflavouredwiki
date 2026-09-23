#!/usr/bin/env bash
# Fetch/refresh everything the wiki is built from into source/ (gitignored):
#   source/matcha-flavoured  official repo (kleiwright/matcha-flavoured), for code + changelog.md
#   source/vanilla-data      vanilla data for the pack's Minecraft version (misode/mcmeta), for diffs
#   source/vanilla-assets    vanilla assets (lang, textures, models)
#   source/changelogs/       official Modrinth release notes, one file per version
# Usage:
#   tools/fetch_sources.sh              check out the pack at the commit pinned in tools/source.lock
#   tools/fetch_sources.sh --update     move to the latest origin/main and rewrite tools/source.lock
#   tools/fetch_sources.sh --ref <ref>  the same for another branch or commit (tools/dry_run.sh uses it)
# The Minecraft version for vanilla data is read from tools/mc_version.txt. --update and --ref rewrite it
# from the pack's pack.mcmeta ("1.12.2 for 26.3"), so a port to a new Minecraft version is picked up.
set -euo pipefail
cd "$(dirname "$0")/.."
UPDATE=0; REF=origin/main
[[ "${1:-}" == "--update" ]] && UPDATE=1
[[ "${1:-}" == "--ref" ]] && { UPDATE=1; REF="${2:?--ref needs a branch or commit}"; }
mkdir -p source source/changelogs

if [[ -d source/matcha-flavoured/.git ]]; then
  git -C source/matcha-flavoured fetch -q origin
else
  git clone -q https://github.com/kleiwright/matcha-flavoured.git source/matcha-flavoured
fi
if [[ $UPDATE == 1 ]]; then
  git -C source/matcha-flavoured rev-parse -q --verify "origin/$REF^{commit}" >/dev/null && REF="origin/$REF"
  git -C source/matcha-flavoured -c advice.detachedHead=false checkout -q --detach "$REF"
  git -C source/matcha-flavoured rev-parse HEAD > tools/source.lock
  mc="$(python3 -c 'import json, re, sys
d = json.load(open(sys.argv[1]))["pack"]["description"]
text = "".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in (d if isinstance(d, list) else [d]))
m = re.search(r"for (\d+\.\d+(?:\.\d+)?)", text)
print(m.group(1) if m else "")' source/matcha-flavoured/MF_datapack/pack.mcmeta)"
  if [[ -n "$mc" && "$mc" != "$(cat tools/mc_version.txt)" ]]; then
    echo "The pack is now for Minecraft $mc (was $(cat tools/mc_version.txt)): tools/mc_version.txt updated."
    echo "$mc" > tools/mc_version.txt
  fi
else
  git -C source/matcha-flavoured -c advice.detachedHead=false checkout -q --detach "$(cat tools/source.lock)"
fi

MC="$(cat tools/mc_version.txt)"
for kind in data-json:vanilla-data assets:vanilla-assets summary:vanilla-summary; do
  tag="$MC-${kind%%:*}"; dir="source/${kind##*:}"
  have="$(cat "$dir/.mcmeta-tag" 2>/dev/null || true)"
  if [[ "$have" != "$tag" ]]; then
    rm -rf "$dir"
    git -c advice.detachedHead=false clone -q --depth 1 --branch "$tag" https://github.com/misode/mcmeta.git "$dir"
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
