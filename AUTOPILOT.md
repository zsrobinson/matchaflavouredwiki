# Autopilot: keep the wiki current, unattended

This file is the complete instruction set for the daily Claude Code routine (a cloud session). Run it
from the repository root. It must be safe to run every day: when nothing changed upstream it finishes
in under a minute without touching anything.

The wiki is derived entirely from upstream sources: the pack's code, its release notes and the
developer's videos. The job is to notice when they change and bring the wiki back in line.

**The wiki describes the latest Modrinth release**, the version players download, not the newest commit
on the repository's `main`. Upstream commits to `main` almost every day, but that is unreleased work.
Releases aren't tagged in git, so `tools/release_commit.py` finds the commit a release was made from by
comparing every file in its zips with the repository. `tools/source.lock` holds that commit. Content that
is on `main` but not yet released is marked `{{Upcoming}}` (see step 4).

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
- `status = 0`: nothing changed. Unless it is Monday (below), **stop here.** Don't commit, don't open a
  PR, don't notify.
- `status = 2`: a source couldn't be checked (network, or `yt-dlp` didn't install).
  Stop and notify with the error from `/tmp/upstream.json`.
- `status = 10`: read `/tmp/upstream.json` and continue. It lists `new_releases` (Modrinth) and `new_videos`
  (YouTube), and `pinned_commit` (`tools/source.lock`). Keep the file: step 5 records exactly what it lists
  as done.

Also stop if a PR labelled `autopilot` is still open, and notify about it instead of stacking a second one.

**On Mondays** (`date -u +%u` is 1), whatever the status:
- `python3 tools/fetch_transcripts.py --all` catches videos whose captions appeared late. A new transcript
  counts as a new video.
- Do the **port rehearsal** at the end of this file.

## Step 1: branch
Start the assigned branch fresh from `main`: `git checkout -B <assigned branch> origin/main`.

## Step 2: bring in the new sources
- **A new release:**
  ```sh
  tools/fetch_sources.sh && python3 tools/extract.py      # the data as it is now (pinned commit)
  python3 tools/update_report.py --snapshot               # keep it as the baseline
  tools/fetch_sources.sh --update                         # move to the commit of the newest release
  python3 tools/extract.py && python3 tools/images.py && python3 tools/generate.py
  ```
  `--update` runs `tools/release_commit.py`, rewrites `tools/source.lock`, refetches the release notes into
  `source/changelogs/`, and, when `pack.mcmeta` names a new Minecraft version, updates
  `tools/mc_version.txt` and fetches that vanilla data.
- **No commit matches the release** (`release_commit.py` exits 1 and lists the closest commits): the
  developer released files that were never committed. Don't guess. Stop and notify with its output.
- **`extract.py` exits 3** when the source uses a key, type or function it has never seen (a new Minecraft
  version renames things). It would otherwise skip them silently and the wiki would lose drop counts,
  conditions or item names without any error. Teach `tools/extract.py` (and `generate.py` if needed) the new
  format. Add something to `KNOWN` only if the wiki really doesn't need it, and say which in the PR.
  Never hand-edit `wiki/generated/`.
- **New videos:** `python3 tools/fetch_transcripts.py <ids from new_videos>`. It saves transcripts of
  videos about the pack to `sources/transcripts/` and ignores unrelated ones.

## Step 3: the checklist
```sh
python3 tools/update_report.py          # writes build/update-report.md
```
The report is the to-do list for the update, one checklist line per change, each with the hand-written
pages that depend on it:
- data changes (items added, removed, renamed or changed; names and texts; recipes; loot; trades;
  enchantments; advancements), with the pages titled after the thing, citing its file or mentioning it;
- every changed source file the generator doesn't read (functions, worldgen, structures, predicates...),
  by folder, with the pages that cite those files, and a flag on folders that are new;
- pages citing files that were deleted or moved.

Changes no hand-written page depends on are folded away: the generated tables already show them.
Also read the code: `git -C source/matcha-flavoured log --oneline <old source.lock>..HEAD` and the real diffs
behind each line. **The code diff is the truth.** Changelogs are incomplete. Read every new release note
in `source/changelogs/`, the diff of the pack's `changelog.md`, and new transcripts in full.

## Step 4: update the written pages
Read `wiki/STYLE.md`, `wiki/AGENT_BRIEF.md` and `wiki/PAGES.md` first; they are the rules.
- Work through **every line** of `build/update-report.md`: correct the pages it names (numbers, behavior,
  progression advice, hand-written tables), or confirm they are still right, and tick it. Grep for old
  values that changed, to catch stale mentions the report can't see.
- **A big update** (more than about 40 lines, e.g. a port to a new Minecraft version): give each heading of
  the report to its own agent with `wiki/AGENT_BRIEF.md` and its lines. Agents save each page as they
  finish it and don't commit; you collect their reports.
- **New items, mechanics, structures or mobs:** write full articles (they replace the generated pages).
  Add them to `wiki/PAGES.md`, the overview pages and the navboxes.
- **Removed features:** keep the article, say it was removed and in which version, add it to
  "Removed features", and keep its History.
- **History:** add `{{History line|<version>|...}}` rows for the new release. Pages may also describe what
  is on `main` but not yet released, marked `{{Upcoming}}` (a message box) or with an "Upcoming" history row,
  citing that code with `{{Source|path|at=<a commit on main>}}`. When a release comes out, promote every
  one of them that the release contains (`grep -rl "Upcoming" wiki/pages`): the text becomes the current
  behavior, the history row gets the version, and the citation loses its `at=`.
- **A new release:** create the `Matcha Flavoured <version>` page modeled on the existing version pages,
  add it to "Version history", update "Upcoming features", "Changes from vanilla" and the main page
  highlight (`wiki/pages/Main/Matcha Flavoured Wiki.wiki`: name, features, tag). `{{Current version}}`
  updates itself.
- **New video:** add design reasoning and history it provides, cited with
  `{{Cite video|id=<id>|title=<title>|quote=...}}`. The code still wins over anything said in a video.
- Add newly found pack bugs to "Known bugs".
- Sources are only the pack's code, its release notes and the developer's videos. Never other wikis.

## Step 4a: review
First passes are accurate, but review passes have always found about one factual error in every few pages.
Give the changed articles (`git diff --name-only wiki/pages`) to a review agent with `wiki/REVIEW_BRIEF.md`;
for a big update, one reviewer per heading. It re-checks every number and claim against the source.

## Step 4b: coverage checks (from the competitor audit, wiki/AUDIT.md)
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
python3 tools/lint_pages.py                       # must pass: no page for a vanished item, no dead citation
python3 tools/check_upstream.py --record /tmp/upstream.json   # marks what step 0 found as done
python3 tools/build_xml.py >/dev/null             # sanity check that every page file parses into a title
git add -A && git status --short                  # source/ and build/ are gitignored; nothing else unexpected
git commit -m "Autopilot: update for <what changed: commit range / release / video>"
git push --force-with-lease -u origin HEAD        # the branch is reused, so it still holds squash-merged commits
```
Open a PR to `main` with the connector, with a body summarising the upstream changes and the pages you
changed, then the ticked checklist from `build/update-report.md` (collapsed sections can stay out; if it
is longer than GitHub's 65,000 characters, put the headings with their counts in the body and the lines
in PR comments). Add the `autopilot` label.

## Step 6: merge when the check passes
Subscribe to the PR's activity and end the turn; the **Check** workflow result wakes the session.
- **Green:** squash-merge with the connector. Keep the branch; the routine reuses it. The
  **Build and deploy** workflow then publishes to https://matchaflavou.red.
- **Red:** read the failing job log, fix the pages or tools, push again. After three failed attempts,
  leave the PR open, comment with what's failing, and notify.

## Port rehearsal (Mondays, whatever step 0 found)
The next release will be made from `main`, and the pack is ported to each new Minecraft version on a branch
(`branches` in `/tmp/upstream.json`, e.g. `26.3`). A port is the biggest update the wiki gets, so rehearse
both while they are unreleased:
```sh
tools/fetch_sources.sh && python3 tools/extract.py
tools/dry_run.sh main
tools/dry_run.sh <branch>          # for every branch named like a Minecraft version
```
`build/dry-run-<branch>.md` lists what `extract.py` doesn't understand yet, the pages `lint_pages.py`
would flag, and the update report. If `extract.py` reports format problems, teach it the new format while
still reading the old one. The Check workflow proves the change is safe: `wiki/generated` must come out
unchanged for the pinned commit. If today also has an update, put the extractor change in that PR and say
so in its body. Otherwise open a PR "Autopilot: prepare the extractor for <branch>" (label `autopilot`),
unless an `autopilot` PR is already open. Don't change pages yet; that happens when the release comes out.
