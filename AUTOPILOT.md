# Autopilot: keep the wiki current, unattended

This file is the complete instruction set for a scheduled agent (for example a daily Claude Code
routine). Run it from the repository root. It must be safe to run every day: when nothing
changed upstream it finishes in under a minute without touching anything.

The wiki is derived entirely from upstream sources: the pack's code, its release notes and the
developer's videos. The job is to notice when they change and bring the wiki back in line.

## Requirements
`git`, `gh` (authenticated, with push rights to this repo), `python3` + `pillow`, `yt-dlp`, `node`/`npx`.
Docker is optional: without it the agent can't render pages locally, and the **Check** workflow on
the pull request does the rendering and validation instead.

## Step 0: is there anything to do?
```sh
git checkout main && git pull --ff-only
python3 tools/check_upstream.py > /tmp/upstream.json; status=$?
```
- `status = 0`: nothing changed. **Stop here.** Don't commit, don't open a PR.
- `status = 2`: a source couldn't be reached. Stop and try again tomorrow.
- `status = 10`: read `/tmp/upstream.json` and continue. It lists `new_commits` (with `from_commit`/`to_commit`),
  `new_releases` (Modrinth) and `new_videos` (YouTube).

Also stop if an open pull request from a previous autopilot run exists
(`gh pr list --label autopilot --state open`), and report it instead of stacking a second one.

## Step 1: branch
```sh
git checkout -b autopilot/$(date -u +%Y-%m-%d)
```

## Step 2: bring in the new sources
- **New commits or releases:** `tools/fetch_sources.sh --update`. This moves the pack to the latest `main`,
  rewrites `tools/source.lock` and refetches the release notes into `source/changelogs/`.
  If `MF_datapack/pack.mcmeta` names a new Minecraft version, put it in `tools/mc_version.txt`,
  delete the matching `source/vanilla-*` folders and run `tools/fetch_sources.sh` again.
- **New videos:** `python3 tools/fetch_transcripts.py <ids from new_videos>`. It saves transcripts of
  videos about the pack to `sources/transcripts/` and ignores unrelated ones.
- Regenerate the data: `python3 tools/extract.py && python3 tools/images.py && python3 tools/generate.py`.
  If extraction fails or misreads a new format (a new component, recipe type or file layout), fix
  `tools/extract.py` or `tools/generate.py` properly. Never hand-edit `wiki/generated/`.

## Step 3: understand what changed
- `git -C source/matcha-flavoured log --oneline <from_commit>..HEAD` and
  `git -C source/matcha-flavoured diff --stat <from_commit>..HEAD`. Then read the real diffs of
  changed functions, recipes, loot tables, enchantments, advancements, trades, worldgen and lang.
  **The code diff is the truth.** Changelogs are incomplete.
- New release notes: read every new file in `source/changelogs/`, and the diff of the pack's `changelog.md`.
- New transcripts: read them in full, looking for design intent, history and announced changes.
- `git diff --stat wiki/generated` then `git diff wiki/generated`: every data change the wiki now shows.

## Step 4: update the written pages
Read `wiki/STYLE.md`, `wiki/AGENT_BRIEF.md` and `wiki/PAGES.md` first; they are the rules.
- For every change found in step 3, find the affected pages (`grep -ril "<item or mechanic>" wiki/pages`)
  and correct the prose: numbers, behavior, progression advice, hand-written tables. Grep for old values
  that changed, to catch stale mentions.
- **New items, mechanics, structures or mobs:** write full articles (they replace the generated pages).
  Add them to `wiki/PAGES.md`, the overview pages and the navboxes.
- **Removed features:** keep the article, say it was removed and in which version, add it to
  "Removed features", and keep its History.
- **History:** add `{{History line|<version>|...}}` rows. Changes that are on `main` but not in a
  Modrinth release are marked with `{{Upcoming}}` or an "Upcoming" history row. Promote them to the
  version number when the release comes out.
- **A new release:** create the `Matcha Flavoured <version>` page modeled on the existing version pages,
  add it to "Version history", update "Upcoming features", "Changes from vanilla" and the main page
  highlight (`wiki/pages/Main/Matcha Flavoured Wiki.wiki`: name, features, tag). `{{Current version}}`
  updates itself.
- **New video:** add design reasoning and history it provides, cited with
  `{{Cite video|id=<id>|title=<title>|quote=...}}`. The code still wins over anything said in a video.
- Add newly found pack bugs to "Known bugs".
- Sources are only the pack's code, its release notes and the developer's videos. Never other wikis.

## Step 5: record, commit, pull request
```sh
python3 tools/check_upstream.py --record          # the wiki now matches upstream
python3 tools/build_xml.py >/dev/null             # sanity check that every page file parses into a title
git add -A
git commit -m "Autopilot: update for <what changed: commit range / release / video>"
git push -u origin HEAD
gh pr create --fill --label autopilot --body "<summary of upstream changes and of the pages you changed>"
```
If Docker is available, run `tools/build.sh && python3 tools/check_site.py` before pushing and fix every
error and red link.

## Step 6: merge when the check passes
```sh
gh pr checks --watch --fail-fast
```
- **Green:** `gh pr merge --squash --delete-branch`. The **Build and deploy** workflow then publishes to
  https://matchaflavou.red automatically.
- **Red:** read the failing log (`gh run view --log-failed`), fix the pages or tools, push again and watch
  again. After three failed attempts, leave the PR open and comment with what's failing.

## Periodically (weekly is enough)
- `python3 tools/fetch_transcripts.py --all` catches videos whose captions appeared late.
- `python3 tools/check_site.py` against a fresh build, to confirm nothing has rotted.
- Re-read `wiki/AUDIT.md` (the competitor audit) and its "prevention" checks.
