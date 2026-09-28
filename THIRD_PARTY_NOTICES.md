# Third-party notices

Third-party material retains its original licenses. The site's CC BY-NC-SA 4.0
notice for original article text does not relicense these components. Attribution
links below identify source pages and their contributor histories. This inventory
records known provenance, not a certification that every imported file has been verified.

## Minecraft Wiki styling and media

`wiki/pages/MediaWiki/Gadget-mcw-*.css` is adapted from Minecraft Wiki contributors'
stylesheets by `tools/vendor_mcw_skin.py`. Source page names remain in the file headers.
The script rewrites image URLs to local assets and combines stylesheets; local overrides
live in `Common.css` and `Vector.css`. The default license is
[CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/), subject to
source-specific exceptions in the [host's licensing policy](https://meta.weirdgloop.org/w/Licensing).

[The source manifest](tools/vendor_mcw_sources.json) maps each vendored stylesheet
and media file to source URLs and a SHA-256 digest of the local copy. Historical
upstream revisions were not recorded and are marked unknown. Future vendor runs
also record the requested URLs and response hashes; a hash identifies a snapshot,
not an upstream revision number.

`site/assets/mcw/*` includes interface images and `Minecraft.woff2`. **Individual
media licenses remain to be verified on their linked File pages.** The stylesheet
license is not a blanket license for those images or that font. Preserve any
file-specific attribution and license when updating them.

## Shared Lua modules and animation script

The Lua modules in `wiki/pages/Module/` were originally obtained through
[matchaflavoured.wiki](https://matchaflavoured.wiki/), which itself imported common
Minecraft Wiki / RuneScape Wiki Scribunto helper modules. On 2026-09-27 every module still in
use was re-verified directly against the wiki that hosts it — fetching its current
`action=raw` text straight from minecraft.wiki or runescape.wiki (not through
matchaflavoured.wiki) and diffing it line-by-line against the local copy — so provenance below
reflects the real upstream text, not a re-statement of an old header comment.

That check also found that seven previously-imported modules had no remaining use anywhere in
this repository (`wiki/pages`, `wiki/generated` or `tools/`); they have been deleted, and their
content and history remain in git (see the removal list below). `Paramtest.lua` in particular had
no original-source header at all (only an unverifiable matchaflavoured.wiki copy) and no on-wiki
use, so removing it also retires a license claim this project could not verify, rather than
resolving it.

**Removed as unused (2026-09-27):** `Addcommas.lua`, `Array.lua`, `Mainonly.lua`,
`Mw.html extension.lua`, `Paramtest.lua`, `Round.lua`, `Yesno.lua`. None were called from any
template (`#invoke`), required by any remaining module, or referenced by `tools/generate.py`'s
output. (`Round.lua` required `Addcommas.lua`, but nothing required `Round.lua` itself, so both
were dead code together.) One note for the record, now moot since the file is gone: the RuneScape
Wiki revision `Mainonly.lua` carried (11872581, 2014-11-22) predates that wiki's 1 October 2018
CC BY-NC-SA fork date, so it was actually under CC BY-SA 3.0, not CC BY-NC-SA — a reminder that a
revision date matters as much as the wiki's current default license. Another note for the record:
`Yesno.lua`'s header read "Based on &lt;https://runescape.wiki/w/Module:Yesno&gt;", but its body was
byte-identical to the current RuneScape Wiki module, whose *own* header instead reads "Based on
&lt;https://en.wikipedia.org/wiki/Module:Yesno&gt;" — i.e. this copy had quietly replaced the
original Wikipedia attribution with the immediate (RuneScape Wiki) source at some point. That
attribution error is now moot along with the rest of the file, but it is the kind of mistake worth
watching for elsewhere: an immediate source is not the same as the original one.

**Kept and verified (2026-09-27), all hosted by Weird Gloop under CC BY-NC-SA 3.0 per
[the host's licensing policy](https://meta.weirdgloop.org/w/Licensing) unless noted:**

| Local module | Direct upstream source | Verified revision | Local modifications |
| --- | --- | --- | --- |
| `AnimateSprite.lua` | [minecraft.wiki: Module:AnimateSprite](https://minecraft.wiki/w/Module:AnimateSprite) | [oldid 3056609](https://minecraft.wiki/index.php?title=Module:AnimateSprite&oldid=3056609), 2025-07-11 | None — byte-identical to upstream apart from the `-- from <url>` attribution line. |
| `Hatnote.lua` | [runescape.wiki: Module:Hatnote](https://runescape.wiki/w/Module:Hatnote) | [oldid 37167399](https://runescape.wiki/index.php?title=Module:Hatnote&oldid=37167399), 2026-08-31 | None — byte-identical to upstream apart from the attribution line. The RuneScape Wiki module's own header additionally credits an [older Wikipedia revision](https://en.wikipedia.org/w/index.php?title=Module:Hatnote&oldid=1063743122) it was repurposed from; that revision's text is under Wikipedia's CC BY-SA 4.0 and its attribution is preserved unchanged, as written in the RuneScape Wiki copy. |
| `Inventory slot.lua` | [minecraft.wiki: Module:Inventory slot](https://minecraft.wiki/w/Module:Inventory_slot) | [oldid 3694235](https://minecraft.wiki/index.php?title=Module:Inventory_slot&oldid=3694235), 2026-07-29 | Substantial, verified by diff against the oldid above: (1) removed multi-mod ("legacy mod") support, not needed since this wiki documents a single pack; (2) removed the random starting frame for animated/"Any \*" slots, which this wiki's byte-for-byte-reproducible static export (see `CLAUDE.md`, "Exports are reproducible") cannot allow; (3) changed the fallback image-filename pattern from `Invicon $1` / `Grid $1` to `$1`, matching this wiki's own `File:<Item Name>.png` upload convention; (4) added a call into this project's own `Module:Tooltip` so every slot carries its item's in-game tooltip; (5) added a lookup into this project's own `Module:Inventory slot/Offsite` so vanilla items with no local page link to minecraft.wiki instead. (4) and (5) are marked inline `-- Matcha Flavoured:` and are this project's own additions, not matchaflavoured.wiki's; (1)–(3) predate this repository's history (present in the first imported commit) and most likely came from matchaflavoured.wiki's own copy, though that cannot be confirmed against matchaflavoured.wiki's own page history. |
| `ProcessArgs.lua` | [minecraft.wiki: Module:ProcessArgs](https://minecraft.wiki/w/Module:ProcessArgs) | [oldid 1540751](https://minecraft.wiki/index.php?title=Module:ProcessArgs&oldid=1540751), 2020-04-04 | None — byte-identical to upstream apart from the attribution line. |
| `SpriteFile.lua` | [minecraft.wiki: Module:SpriteFile](https://minecraft.wiki/w/Module:SpriteFile) | [oldid 3765979](https://minecraft.wiki/index.php?title=Module:SpriteFile&oldid=3765979), 2026-09-09 | One line simplified: dropped a minecraft.wiki-specific `.jpg` extension case for a `Dungeons2AchievementSprite` file that never occurs in this wiki's data (that wiki also documents Minecraft Dungeons and Minecraft Legends; this one does not). Functionally equivalent for every sprite this wiki generates. |
| `TSLoader.lua` | [minecraft.wiki: Module:TSLoader](https://minecraft.wiki/w/Module:TSLoader) | [oldid 3185977](https://minecraft.wiki/index.php?title=Module:TSLoader&oldid=3185977), 2025-10-06 | None — byte-identical to upstream apart from the attribution line. |
| `UI.lua` | [minecraft.wiki: Module:UI](https://minecraft.wiki/w/Module:UI) | [oldid 3634115](https://minecraft.wiki/index.php?title=Module:UI&oldid=3634115), 2026-06-18 | None — byte-identical to upstream apart from the attribution line. Its `require` calls point at this wiki's own `Module:Inventory slot`, `Module:AnimateSprite` and `Module:TSLoader`, as they must on every wiki that runs this module. |

"Verified revision" is the `oldid` that was live when each module was fetched directly on
2026-09-27; these are ordinary wiki pages that can change, so this table records a point-in-time
check, not a permanent guarantee. Re-run the same fetch (`curl` the module's `?action=raw` URL)
and diff against the local copy to check for drift. A previous version of this table listed
`Hatnote.lua` and `Paramtest.lua`'s license as needing verification; that has been resolved above
(the Wikipedia-derived portion of `Hatnote.lua` and its BY-SA terms specifically), and `Paramtest.lua`
is now removed rather than left unverified.

`wiki/pages/MediaWiki/Gadget-animatedIcons.js` was originally introduced through
matchaflavoured.wiki as what its own header called a copy of Minecraft Wiki's
`Gadget-site.js`. That attribution was wrong: `Gadget-site.js` does not contain this code today,
and it does not appear to ever have — searching minecraft.wiki located the real match in the
"Element animator" section of
[`MediaWiki:Common.js`](https://minecraft.wiki/w/MediaWiki:Common.js)
([oldid 3728808](https://minecraft.wiki/index.php?title=MediaWiki:Common.js&oldid=3728808),
2026-08-19, CC BY-NC-SA 3.0), confirmed by comparing this repository's first-imported version of
the gadget (commit `99419741`) against that section: they matched byte-for-byte apart from an
outer jQuery-ready wrapper. This project has since rewritten the gadget from jQuery to plain DOM
and from a per-element timer to one shared `tick` counter driving every `.animated` slot, so
slots with the same frame set never fall out of sync (PR #21, "Keep cycling slots in step");
see the file's own header comment for the reasoning. The header comment has been corrected to
cite `Common.js` instead of `Gadget-site.js`.

## Matcha Flavoured and Minecraft

Pack artwork and data come from [Klei Wright and contributors](https://github.com/kleiwright/matcha-flavoured),
under the pack's [CC BY-NC-SA 4.0 license](https://github.com/kleiwright/matcha-flavoured/blob/main/LICENSE).
`tools/source.lock` records the pack revision. `tools/images.py` adapts textures into
icons and station screens (`site/assets/gui/`), and renders the title-screen panorama.
`wiki/renders/` and `wiki/diagrams/` are generated representations of pack/game data.
The pack's own credits are reproduced on the wiki's Credits page.

Vanilla Minecraft assets and entity models are Mojang Studios' material, obtained
through the [mcmeta archive](https://github.com/misode/mcmeta) and the game client.
`tools/mc_version.txt` records the game version. They are not relicensed by this
project; see the [Minecraft usage guidelines](https://www.minecraft.net/usage-guidelines).

## Other components

- MediaWiki and its installed skins/extensions retain their distributed licenses.
  See `site/Dockerfile` and [MediaWiki's copyright information](https://www.mediawiki.org/wiki/Copyright).
- JavaScript dependencies retain their package licenses; see `tools/render/package.json`
  and its lockfile for the rendering dependencies.
- `site/assets/cc-by-nc-sa.png` is a Creative Commons license badge. Its original
  download URL was not recorded; provenance remains to be verified.
- `site/assets/Wiki.png` is the maintainer's supplied pixel-art logo, replacing the
  former community-wiki logo. Generated site icons and share-card branding use it.

## Updating this inventory

For new imports, record local paths, the direct source and contributor history,
upstream revision where available, exact license and exceptions, and modifications.
Keep existing notices. Check each media file's description page separately, and
resolve the outstanding items above before describing this inventory as fully verified.
