# Autopilot: keep the wiki current, unattended

This file is the complete instruction set for the daily Claude Code routine (a cloud session). Run it
from the repository root. It must be safe to run every day: when nothing changed upstream it finishes
in under a minute without touching anything.

The wiki is derived entirely from upstream sources: the pack's code, its release notes and the
developer's videos. The job is to notice when they change and bring the wiki back in line.

## Environment
- `git`, `python3` and `node` are preinstalled; step 0 installs `pillow` and `yt-dlp`.
- There is no `gh` CLI. Do everything on GitHub (listing, opening, labelling and merging PRs, reading
  check runs) with the GitHub connector tools.
- The session assigns one branch to push to. Use it for the PR; never push anywhere else.
- Rendering and link checks happen in the **Check** workflow on the PR, not locally.

## Step 0: is there anything to do?
```sh
pip install --quiet --upgrade pillow yt-dlp     # --upgrade: YouTube changes break old yt-dlp versions
git checkout main && git pull --ff-only
python3 tools/check_upstream.py > /tmp/upstream.json; status=$?
```
- `status = 0`: nothing changed. On Mondays (`date -u +%u` is 1), first run
  `python3 tools/fetch_transcripts.py --all`, which catches videos whose captions appeared late; if it saved
  a new transcript, continue as for a new video. Otherwise **stop here.** Don't commit, don't open a PR,
  don't notify.
- `status = 2`: a source couldn't be checked (network, or `yt-dlp` didn't install).
  Stop and notify with the error from `/tmp/upstream.json`.
- `status = 10`: read `/tmp/upstream.json` and continue. It lists `new_commits` (with `from_commit`/`to_commit`),
  `new_releases` (Modrinth) and `new_videos` (YouTube).

Also stop if a PR labelled `autopilot` is still open, and notify about it instead of stacking a second one.

## Step 1: branch
Start the assigned branch fresh from `main`: `git checkout -B <assigned branch> origin/main`.

## Step 2: bring in the new sources
- **New commits or releases:** `tools/fetch_sources.sh --update`. This moves the pack to the latest `main`,
  rewrites `tools/source.lock` and refetches the release notes into `source/changelogs/`.
  If `MF_datapack/pack.mcmeta` names a new Minecraft version, put it in `tools/mc_version.txt`,
  delete the matching `source/vanilla-*` folders and run `tools/fetch_sources.sh` again.
- **New videos:** `python3 tools/fetch_transcripts.py <ids from new_videos>`. It saves transcripts of
  videos about the pack to `sources/transcripts/` and ignores unrelated ones.
- After new commits or releases, regenerate the data: `python3 tools/extract.py && python3 tools/images.py && python3 tools/generate.py`.
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

## Step 4b: coverage checks (from the coverage review, wiki/AUDIT.md)
- Every transcript in `sources/transcripts/` is cited at least once (`grep -rl "<video id>" wiki/pages`).
  If one isn't, mine it for design reasoning and history.
- New kinds of source files: `git -C source/matcha-flavoured diff --stat <from>..HEAD` shows a directory
  that `tools/extract.py` doesn't read (as `texts/` splash texts once was)? Extend the extractor.
- New tooltip glyphs in the lang file or lore get a name in `Template:G` and a row on the "Tooltip" page.
- New progression steps (new tutorial advancements, new tiers) are reflected in "Guide for new players"
  and "Progression".
- New visible advancements get an anchor and a redirect, as the existing ones have (see "Advancements").

## Step 5: record, commit, pull request
```sh
python3 tools/check_upstream.py --record          # the wiki now matches upstream
python3 tools/build_xml.py >/dev/null             # sanity check that every page file parses into a title
git add -A && git status --short                  # source/ and build/ are gitignored; nothing else unexpected
git commit -m "Autopilot: update for <what changed: commit range / release / video>"
git push --force-with-lease -u origin HEAD        # the branch is reused, so it still holds squash-merged commits
```
Open a PR to `main` with the connector, with a body summarising the upstream changes and the pages you
changed, and add the `autopilot` label.

## Step 6: merge when the check passes
Subscribe to the PR's activity and end the turn; the **Check** workflow result wakes the session.
- **Green:** squash-merge with the connector. Keep the branch; the routine reuses it. The
  **Build and deploy** workflow then publishes to https://matchaflavou.red.
- **Red:** read the failing job log, fix the pages or tools, push again. After three failed attempts,
  leave the PR open, comment with what's failing, and notify.
