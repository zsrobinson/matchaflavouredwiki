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

## Deploying (static, Cloudflare Workers)

The public site doesn't need MediaWiki, PHP or a database. MediaWiki is only the renderer
used at build time. `python3 tools/export_static.py` writes every page to `dist/` as plain HTML.
URLs stay the same as on the live wiki (`/w/Page_title`, served from `dist/w/Page_title.html`).
The export includes:
- static CSS and images;
- the same shell script the live wiki uses: dark mode (applied before first paint) and
  collapsible sidebar sections;
- small static replacements for animated recipe slots and sortable or collapsible tables;
- **Pagefind** full-text search. The header search box is Pagefind's `<pagefind-searchbox>`
  Component UI, and `/search/?q=…` is the full results page with category filters and item icons.

Deploy with Cloudflare Workers. The configuration is in `wrangler.jsonc`: static assets from `dist/`
behind a tiny Worker (`src/worker.js`). The site is served at **https://matchaflavou.red**, and
`www.matchaflavou.red`, `matchaflavo.red` and `matchaflavoured.org` (plus their `www`) 301-redirect to it,
keeping the path and query:

```sh
python3 tools/export_static.py        # needs the local wiki running and built
npx wrangler dev                      # preview exactly as Cloudflare serves it (http://localhost:8787)
npx wrangler deploy
```

`.github/workflows/deploy.yml` does all of this on every push to `main`: it fetches the sources at
the pinned commit, builds the wiki in Docker, checks it, exports it and runs `wrangler deploy`.
Add the repository secrets `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`. The token is a custom token with
Account › Workers Scripts: Edit, plus Zone › Workers Routes: Edit, Zone: Read and DNS: Edit for the three zones. Other static hosts
(Cloudflare Pages, Netlify, GitHub Pages) can serve `dist/` as is (`_redirects` and `404.html` are included).

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

## Keeping the wiki current (autopilot)

The wiki is derived entirely from upstream sources, so a scheduled agent keeps it current:

- `tools/check_upstream.py` compares three sources with `tools/upstream.json`: the pack's GitHub
  commits, Modrinth releases and the developer's YouTube uploads. It exits `0` when nothing changed,
  which is the usual case and takes seconds.
- When something changed, the agent follows **[AUTOPILOT.md](AUTOPILOT.md)**:
  1. fetch the sources and transcripts;
  2. regenerate the data pages;
  3. read the code diff, release notes and new transcripts;
  4. update the written pages;
  5. open a pull request labelled `autopilot`;
  6. merge it once the **Check** workflow passes. **Build and deploy** then publishes the site.
- Video transcripts are primary sources and are kept in `sources/transcripts/` (the first design
  video is also `transcript.txt`). `tools/fetch_transcripts.py` adds new ones.

To run it on a schedule, point a daily agent (for example a Claude Code scheduled routine) at this
repository with the prompt "Follow AUTOPILOT.md". To update by hand, follow the same file.

## Licence

The wiki's text is released under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/),
the same licence as Matcha Flavoured. Textures and icons come from the Matcha Flavoured resource
pack (CC BY-NC-SA 4.0, by Klei Wright and contributors) and from vanilla *Minecraft* where the pack
does not replace them. The skin styling, Lua modules and interface images are adapted from
matchaflavoured.wiki and the Minecraft Wiki. This is an unofficial fan project and is not
affiliated with Mojang or with the pack's author.
