# Matcha Flavoured Wiki

An encyclopedia for [Matcha Flavoured](https://modrinth.com/datapack/matcha-flavoured), the
Minecraft datapack by Klei Wright. It's a MediaWiki site laid out and written like the
[Minecraft Wiki](https://minecraft.wiki/), styled after
[matchaflavoured.wiki](https://matchaflavoured.wiki/), and written entirely from the pack's
**source code, official release notes and the developer's design video**. No other wiki was
used as a source.

**All content lives in this git repository.** MediaWiki is only the renderer: nobody logs
in or edits through the web, and the site is rebuilt from the repo.

## Quick start

Requirements: Docker (Docker Desktop or colima), Python 3 with Pillow, and git.

```sh
tools/fetch_sources.sh            # clone the pack (pinned commit) + vanilla data into source/
docker compose up -d --build      # MediaWiki 1.45 on http://localhost:8080
docker exec matcha-wiki php maintenance/run.php installPreConfigured   # first time only
tools/build.sh                    # extract → images → generate → import (≈6 min first time)
```

Then open <http://localhost:8080/w/Main_Page>.

**Live preview while editing:** run `tools/watch.sh` (e.g. `nohup tools/watch.sh > build/watch.log &`).
It polls `wiki/pages` every 5 seconds and imports whatever changed, so http://localhost:8080
tracks the working tree.

When you only changed text: `tools/sync.sh` imports just the pages that changed (seconds).
To preview single pages while writing: `python3 tools/preview.py "Title" ...`. It reports
template errors and red links. `tools/screenshot.sh "Title" out.png` renders a PNG with
headless Chrome.

## Deploying (static)

The public site doesn't need MediaWiki, PHP or a database. `python3 tools/export_static.py`
renders every page into `dist/` as plain HTML (URLs unchanged: `/w/Page_title`), with static
CSS, images, a small script for the interactive bits (animated recipe slots, dark mode,
sortable and collapsible tables) and client-side search over `search.json`. Upload `dist/`
to any static host.

`.github/workflows/deploy.yml` does this automatically: on every push to `main` it fetches the
sources at the pinned commit, builds the wiki in Docker, exports it and publishes to GitHub
Pages (enable Pages with source "GitHub Actions" in the repository settings). The same
commands work for Cloudflare Pages or Netlify (`dist/_redirects` is included). Test locally
with `python3 -m http.server -d dist 8090`.

## How it works

```
source/                 (gitignored) inputs, fetched by tools/fetch_sources.sh
  matcha-flavoured/     the official repo at the commit in tools/source.lock
  changelogs/           official release notes per version (Modrinth API)
  vanilla-data/ vanilla-assets/ vanilla-summary/   vanilla 26.x data for diffs (misode/mcmeta)
transcript.txt          the developer's introduction video, used for design intent and history
tools/
  extract.py            source → build/data.json (items, recipes, loot, trades, enchantments, advancements)
  images.py             textures → build/images (item icons, isometric block icons, tooltip glyphs)
  generate.py           data.json → wiki/generated (infobox/recipe/usage/drop/trade tables, stubs, redirects)
  build_xml.py          wiki/pages + wiki/generated → build/import.xml
  build.sh / sync.sh    full rebuild / fast incremental import
  preview.py            import + check specific pages
  query.py              look up anything in data.json while writing
wiki/
  pages/<Namespace>/<Title>.wiki   hand-written pages (articles, templates, CSS, Lua modules)
  generated/                       generated from source; never edit by hand, but do commit it
  STYLE.md                         the writing and layout rules (read before editing)
  PAGES.md                         the planned page set and what each page covers
  AGENT_BRIEF.md                   instructions for agents writing pages
site/                   MediaWiki config (LocalSettings.php, Dockerfile, rewrite rules, skin assets)
```

Hand-written articles keep their numbers current by transcluding generated data:
`{{Infobox auto}}`, `{{Recipes}}`, `{{Uses}}`, `{{Sources}}`, `{{Data/Trades/<Profession>}}`,
`{{Data/Loot/...}}`, `{{Data/Food table}}` and similar. When the pack updates, rerunning the
generator refreshes every recipe, stat, drop chance and trade automatically. The prose is
what needs a human (or an agent) to review.

Any hand-written page replaces the generated stub with the same title. `wiki/generated` is
committed on purpose: after a pack update, `git diff wiki/generated` is an exact list of what
changed in the data.

Editing: change files under `wiki/pages/`, run `tools/sync.sh`, check the page, and commit.
Title ↔ file name: the namespace is the folder, and a `/` in a title is written as `%2F`.

## Updating the wiki after a new Matcha Flavoured release

Give the following prompt to a coding agent in this repository, or follow it yourself.

````text
Matcha Flavoured has released a new version. Update this wiki (a git repo; read README.md,
wiki/STYLE.md, wiki/PAGES.md and wiki/AGENT_BRIEF.md first) so that it documents the new
version completely and accurately. Use only the pack's source code, its official release
notes and transcript.txt as sources.

1. Refresh the sources.
   - Note the old pinned commit: OLD=$(cat tools/source.lock)
   - Run tools/fetch_sources.sh --update. It moves the pack to origin/main, rewrites
     tools/source.lock and refetches the release notes into source/changelogs/.
   - If MF_datapack/pack.mcmeta now names a new Minecraft version ("x for 26.y"), put that
     version in tools/mc_version.txt, delete the matching source/vanilla-* folders and rerun
     tools/fetch_sources.sh so vanilla diffs use the right version. (Check that misode/mcmeta
     has the "<ver>-data-json", "<ver>-assets" and "<ver>-summary" tags.)
2. Understand what changed.
   - Read every new file in source/changelogs/ and the diff of the pack's changelog.md.
   - Run git -C source/matcha-flavoured log --oneline $OLD..HEAD and
     git -C source/matcha-flavoured diff --stat $OLD..HEAD, then read the actual diffs of
     changed functions, recipes, loot tables, enchantments, advancements, trades, worldgen and lang.
     Changelogs are incomplete; the code diff is the truth.
3. Regenerate and see the data diff.
   - docker compose up -d, then tools/build.sh.
   - git diff --stat wiki/generated, then git diff wiki/generated: new, removed and changed items,
     recipes, drops, trades, stats and advancements.
   - If the extractor or generator fails or misreads a new data format (e.g. a new component
     or recipe type), fix tools/extract.py or tools/generate.py rather than working around it.
4. Update the hand-written pages (wiki/pages/Main).
   - For every change found in step 2 or 3, find the affected pages (grep -ril "<item or mechanic>" wiki/pages)
     and update the prose: numbers, behavior, progression advice, tables written by hand.
     Grep for old values that changed (durations, damage, chances) to catch stale mentions.
   - New items, mechanics, structures or mobs: write full articles following STYLE.md
     (replacing the generated stubs) and add them to wiki/PAGES.md, the relevant overview
     pages and the navboxes.
   - Removed features: keep the article, mark the item as removed in the lead ("was an item
     … removed in <version>"), add it to "Removed features", and keep its History.
     Redirect only if it was renamed or merged.
   - Add a {{History line|<version>|...}} to the History section of every affected page.
5. Version pages.
   - Create "Matcha Flavoured <version>" (wiki/pages/Main/Matcha Flavoured <version>.wiki), modeled on
     the existing version pages, add it to "Version history", update "Upcoming features"
     (move shipped items out), and update "Changes from vanilla" and "Matcha Flavoured" if anything
     major changed. {{Current version}} updates itself from pack.mcmeta.
6. Check.
   - tools/sync.sh --all, then python3 tools/check_site.py. Fix every template or Lua error, and
     every red link that isn't a planned page.
   - Screenshot the main page and a few changed pages with tools/screenshot.sh and look at them.
7. Commit: git add -A && git commit -m "Update for Matcha Flavoured <version>". Include the
   pinned commit in the message.
````

## Licence

The wiki's text is released under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/),
the same licence as Matcha Flavoured. Textures and icons come from the Matcha Flavoured resource
pack (CC BY-NC-SA 4.0, by Klei Wright and contributors) and from vanilla *Minecraft* where the pack
does not replace them. The skin styling, Lua modules and interface images are adapted from
matchaflavoured.wiki and the Minecraft Wiki. This is an unofficial fan project and is not
affiliated with Mojang or with the pack's author.
