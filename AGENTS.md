# Working on the Matcha Flavoured Wiki

Read this before changing anything. `README.md` explains how the project works; `wiki/STYLE.md`
covers how to write pages; `AUTOPILOT.md` covers routine updates after upstream changes. This file
holds what isn't obvious from those: decisions, conventions, and the traps that cost real
debugging time.

## Non-negotiables
- **Content lives in git.** Nobody edits through the web; MediaWiki is only a build-time renderer.
  Don't add login, editing or history features to the site. Link to GitHub instead
  (`site/GitLinks.php`: the Edit on GitHub / View source / View history tabs and the footer line).
- **Sources:** the pack's code (`source/matcha-flavoured`, pinned in `tools/source.lock`), the official
  release notes (`source/changelogs`) and the developer's videos (`transcript.txt`, `sources/transcripts/`).
  Never other wikis, forks or third-party videos. Competitors may be read to find gaps (`wiki/AUDIT.md`),
  but every fact must be verified in the primary sources.
- **Look and structure follow minecraft.wiki; the game's widgets look like the pack.** The skin is
  minecraft.wiki's own CSS, vendored in. Templates emit its markup (infobox, navbox, inventory slots,
  minetip tooltips), and the main page uses its main-page CSS and layout. Where the pack reskins
  something the player sees (station screens, inventory colours, hearts, lore), the wiki shows the
  pack's version: see "Pack look" below.
- **Never hand-edit `wiki/generated/`.** It's rebuilt by `tools/generate.py` and committed on purpose:
  `git diff wiki/generated` shows exactly what changed in the data. Hand pages in `wiki/pages/` override
  generated pages of the same title.
- **Commit messages and PRs:** no AI attribution (see the user's global instructions).

## Everyday loop
```sh
docker compose up -d                 # MediaWiki on :8080 (image built from site/Dockerfile)
nohup tools/watch.sh > build/watch.log &   # dev server: imports changed pages every 5 s
python3 tools/preview.py "Title"     # import + check specific pages (errors, red links, missing files)
python3 tools/check_site.py          # every hand-written page; also flags unparsed [[..]] / {{..}}
tools/screenshot.sh "Title" out.png  # headless Chrome render; for dark mode or phone widths use Playwright
python3 tools/export_static.py && npx wrangler dev   # the real static site on :8787
```
`tools/build.sh` does a full rebuild (extract → images → generate → import → upload changed images), and
`tools/sync.sh` imports only changed text. All three share the lock `build/.sync.lock`. `generate.py` has
its own lock and swaps `wiki/generated` atomically, and `build_xml.collect()` retries if it catches
the swap mid-way.

## Traps we already hit (don't rediscover them)
**MediaWiki / wikitext**
- **Templates must not end in a newline.** The newline is transcluded and breaks tables and links. The
  generator writes templates without one; do the same by hand.
- **`{{#if:}}` trims whitespace.** Rows built with `{{!}}-` lose their line break. Build rows with HTML
  (`<tr><th>…</th><td>…</td></tr>`), as `Template:Infobox` and `Template:Navbox` do.
- **No images inside link labels.** `[[Warding|{{G|Warding}} 1]]` renders as literal text. Put glyphs
  outside the link: `{{G|Warding}} [[Warding|1]]`. `check_site.py` catches this.
- **`Module:UI` reads the parent template's parameters,** not the `#invoke` arguments. Wrap it in a
  template whose parameter names match, or the slots render empty. (The recipe templates now use
  `Module:Station`, which takes explicit `#invoke` arguments.)
- **`{{About}}` wraps its link arguments in `[[ ]]`.** For external targets use `{{Hatnote|…}}`.
- **Links are only first-letter case-insensitive.** `[[mud kiln]]` works only because `build_xml.py`
  synthesises a sentence-case redirect for every multi-word title.
- **Titles to files:** the namespace is the folder, `/` becomes `%2F`, Module pages are `.lua`, the
  Project namespace is `Matcha Flavoured Wiki:`.

- **Pages have a 2 MB include limit.** Past it MediaWiki stops expanding templates and prints a bare `Template:…` link
  (crafting grids are the heavy part). `generate.py` drops the grids from recipe tables longer than `COMPACT_AFTER`,
  and `check_site.py` / `preview.py` flag unexpanded templates and missing images.

- **The local wiki never deletes pages.** A page the generator stopped producing still exists locally,
  so local checks can pass while CI, which builds from scratch, finds broken links. Trust the PR check.

**Caches and Docker**
- **Parser cache is off** (`$wgParserCacheType = CACHE_NONE`). **APCu still caches rendered pages,
  messages, gadget definitions and CSS**, so `sync.sh` and `build.sh` run `apache2ctl -k graceful`
  after importing. If a page looks stale, that's the fix. `purgeList` alone does not clear it.
- **Mount directories, not single files.** A single-file bind mount keeps pointing at the old inode after
  `sed -i`. LocalSettings is loaded through `MW_CONFIG_FILE` from the mounted `site/` folder.
- **Scribunto's bundled Lua is x86-only.** `site/Dockerfile` installs `lua5.1`, which makes it work on ARM Macs.
- **MediaWiki 1.45 namespaces its classes** (`\MediaWiki\Title\Title`), so global `Title` in PHP hooks fails.
- **macOS has a case-insensitive filesystem.** Two titles that differ only by case can't both be files.
  Never write case-variant pages to disk. Case redirects are built in memory by `build_xml.py`, and the
  static export serves them from the Worker. This bug once overwrote 1,091 generated pages.

**Skin and theme**
- **Refreshing the skin:** `tools/vendor_mcw_skin.py` re-vendors minecraft.wiki's CSS and images (as
  `Gadget-mcw-*.css` plus `site/assets/mcw/`). It uses curl, because the site's bot protection rejects
  Python's TLS client, and it resolves `filepath://` URLs. Don't edit the vendored files; override in
  `MediaWiki:Common.css` or `Vector.css`.
- **Dark mode:** it uses minecraft.wiki's classes (`body.wgl-theme-dark`). `site/theme-boot.js` is inlined
  in `<head>` to avoid a light flash. `MediaWiki:Gadget-mfwShell.js` (theme toggle `#pt-dm-toggle`,
  collapsible sidebar) is shared by the live wiki and the static export. Glyph images are drawn dark and
  inverted in dark mode.
- **Mobile is CSS on the same pages, not a second skin.** Up to 720px, the phone section at the end of
  `MediaWiki:Vector.css` restyles Vector like minecraft.wiki's mobile site (its Minerva skin). You get the
  grass header, the sidebar as a menu drawer, icon page actions beside the title, scrolling tables and a
  stone footer. `Gadget-mfwShell.js` adds the header buttons and the drawer's dark-mode entry, and on
  phones makes sections collapsible. Legacy Vector declares itself non-responsive, so without the
  `$wgValidSkinNames` override in `LocalSettings.php` phones get `width=1120` and show the desktop page
  zoomed out. Keep desktop (over 720px) pixel-identical: scope every mobile rule to the media query.
- **Icons:**
  - Item icons are `File:<Item Name>.png`, upscaled 8× nearest-neighbour.
  - Blocks are rendered as true isometric cubes (horizontal step = cos 30°); don't go back to 2:1.
  - Foliage textures are tinted.
  - Tooltip glyphs are `File:Glyph E0xx.png`, named in `Template:G`, and explained on the "Tooltip" page.

**Pack look** (`MediaWiki:Gadget-mfw-ui.css`)
- **Station screens:** `{{Crafting}}`, `{{Cooking}}`, `{{Smithing}}` and `{{Stonecutter}}` call
  `Module:Station`, which draws the pack's own screen art and places each slot at the game's pixel
  coordinates (the pack moves no slot). `tools/images.py` cuts the art from the resource pack into
  `site/assets/gui/` at 2× (committed; served as `/assets/gui/`). Each cooking station has its own
  screen, title (the pack's names: Oven, Mud Kiln) and progress sprites; the arrow fills over the
  recipe's cooking time. A campfire has no screen in the game, so Kindling gets one in the pack's
  palette with the item resting on the animated fire. `{{Trade}}` draws a villager offer the same way.
- **Tooltips:** every slot carries its item's in-game tooltip as a hidden `.mf-tip` (`Module:Tooltip`,
  data generated into `Module:Tooltip/Data` from the item components: name colour or rarity, lore runs
  with their colours, glyph widths). `MediaWiki:Gadget-mfwTooltip.js` shows it on hover, in the live
  wiki and in the static export. `{{Tooltip|item}}` draws it in place (item infoboxes). Glyphs are CSS
  masks over `glyphs.png` filled with the text colour, the way the game tints the font's white glyphs.
- **Palette:** slots and panels use the pack's brown inventory colours, and `{{Hp}}` uses its HUD hearts.

**Static export and deploy**
- **Page files:** pages are `dist/w/<Title>.html`, with `html_handling: auto-trailing-slash` in `wrangler.jsonc`.
- **The Worker (`src/worker.js`):**
  - 301s every other hostname to `https://matchaflavou.red`;
  - serves redirect pages and wrong-case URLs as real 301s from `src/redirects.json`, which the export writes.
- **What the export keeps and strips:** it removes MediaWiki's scripts except the theme boot, and keeps the `ca-mfw-*` GitHub tabs.
  It also replaces legacy Vector's fixed `width=1120` viewport with `device-width`, so phones get the vendored narrow-screen layout.
  Its `site.js` is `Gadget-mfwShell.js` and `Gadget-mfwTooltip.js` (plain DOM, no jQuery) plus `SITE_JS`.
- **Search** is Pagefind (Component UI searchbox and the `/search/` page).
- **SEO** lives in `tools/seo.py`: canonical URLs, descriptions from the lead, Open Graph, JSON-LD, the
  sitemap with git dates, and `noindex` for generated-only pages. Keep a lead sentence on every article;
  it becomes the search snippet.
- **Deploy:** CI (`.github/workflows/deploy.yml`) builds everything and runs `wrangler deploy` on push
  to `main`, which takes about 20 minutes. A newer push cancels a running deploy. PRs run `check.yml`.
- **Cloudflare:** the account is `5ac179a21ac475108b47f1269748424b`. The zones are matchaflavou.red
  (primary), matchaflavo.red and matchaflavoured.org. After DNS changes, test with
  `curl --resolve host:443:$(dig +short @1.1.1.1 host)`, because local resolvers cache NXDOMAIN.

## Facts about the pack's data (the generator relies on these)
- **Custom items reuse vanilla item IDs.** For example, foods are poisonous potatoes with components, and
  alloys are renamed vanilla items. Identity comes from `item_name`, `item_model` or lore
  (`extract.py: variant_key`):
  - Blessings are named by their prayer (lore).
  - Clay Fetishes are named by their variant.
  - Music discs are named by their song.
  - Potions named like an effect become "Splash Potion of X".
- **Recipes match ingredients by item ID only,** so a custom item also works in recipes for its base item.
  The generator lists those uses only when both are the same kind of item (food with food).
- **Healing is a hidden Regeneration III:** 1 HP per 12 ticks. Hunger is pinned by a function.
  Heal amounts are computed from the effect duration.
- **Loot chances** account for rolls, weights, biome-exclusive entries (fishing), counts that can roll 0,
  and `table_bonus`.
- **Trades are data-driven** (26.2 `trade_set` → tags → `villager_trade`). Trades ending in `discard` are
  placeholders and are skipped. Map names come from `set_name`, and biome limits from `merchant_predicate`.
- **Intrinsics are enchantments,** stored as `stored_enchantments` on armor and tools. Their names are
  glyph-only, so `generate.py: INTRINSIC_PAGES` and `INTRINSIC_LABELS` give them pages and readable labels.
- **Pack bugs** go on the "Known bugs" page. Don't write workarounds that hide them.
  `build/data.json` lists `missing_lang` keys.

## Sources worth knowing
- **Developer's videos (YouTube channel Klei_Wright):**
  - design video `zyRH8W58fRI` (`transcript.txt`);
  - appendix `wavOi0ULYpQ`;
  - trailer `0yf9G_vfi-U` (music only, no captions).

  The channel RSS feed returns 404, so `yt-dlp` is used instead. Most of the channel is unrelated essays,
  and `tools/fetch_transcripts.py` keeps only pack videos.
- **Vanilla data** comes from misode/mcmeta tags (`<ver>-data-json`, `-assets`, `-summary`).
  `vanilla-summary/item_components` gives each vanilla item's default components.
- **Modrinth versions API** provides the release notes (`source/changelogs`).
  **The Modrinth description says there is no official wiki:** never present this site as official.

## Delegating to agents
Writer and reviewer briefs are in `wiki/AGENT_BRIEF.md` and `wiki/REVIEW_BRIEF.md`, and the page plan
(which titles exist and who owns them) is in `wiki/PAGES.md`. Agents should:
- save each page as they finish it (runs have been cut off by usage limits);
- check their pages with `tools/preview.py`;
- never run build or sync scripts or commit; the coordinator does that.

Two lessons from past runs:
- First passes by agents were accurate. Review passes still caught about one factual error in every
  few pages, so always run a review pass.
- When a task is blocked by the permission classifier (renaming the repo, deploying), don't work around
  it. Report the exact commands instead.
