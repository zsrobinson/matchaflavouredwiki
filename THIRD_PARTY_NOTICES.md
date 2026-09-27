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

The following files in `wiki/pages/Module/` were imported through
[matchaflavoured.wiki](https://matchaflavoured.wiki/). Credit belongs to the original
contributors as well as subsequent contributors there. Source links below are
retained from the imported headers; exact imported revisions are unknown except
where an `oldid` is explicitly linked. Local changes are recorded in this repository's
file histories (including inventory-slot integration).

| Local module | Recorded upstream attribution |
| --- | --- |
| `Addcommas.lua` | [source](https://runescape.wiki/w/Module:Addcommas) |
| `AnimateSprite.lua` | [source](https://minecraft.wiki/w/Module:AnimateSprite) |
| `Array.lua` | [source](https://runescape.wiki/w/Module:Array) |
| `Hatnote.lua` | [source](https://runescape.wiki/w/Module:Hatnote); [source](https://en.wikipedia.org/w/index.php?title=Module:Hatnote&oldid=1063743122) |
| `Inventory slot.lua` | [source](https://minecraft.wiki/w/Module:Inventory_slot) |
| `Mainonly.lua` | [source](https://runescape.wiki/w/Module:Mainonly) |
| `Mw.html extension.lua` | [source](https://runescape.wiki/w/Module:Mw.html%20extension) |
| `Paramtest.lua` | [immediate source](https://matchaflavoured.wiki/w/Module:Paramtest) — original source unverified |
| `ProcessArgs.lua` | [source](https://minecraft.wiki/w/Module:ProcessArgs) |
| `Round.lua` | [source](https://runescape.wiki/w/Module:Round) |
| `SpriteFile.lua` | [source](https://minecraft.wiki/w/Module:SpriteFile) |
| `TSLoader.lua` | [source](https://minecraft.wiki/w/Module:TSLoader) |
| `UI.lua` | [source](https://minecraft.wiki/w/Module:UI) |
| `Yesno.lua` | [source](https://runescape.wiki/w/Module:Yesno) |

Minecraft Wiki and RuneScape Wiki currently default to CC BY-NC-SA 3.0, but
[their policy](https://meta.weirdgloop.org/w/Licensing) preserves exceptions for
prior licenses. **Module-specific license chains still need verification**, notably
`Hatnote.lua`, whose header identifies a Wikipedia revision, and `Paramtest.lua`,
which has no original-source header. Wikipedia-derived CC BY-SA material must retain
its applicable BY-SA terms; this site's noncommercial notice does not override them.

`wiki/pages/MediaWiki/Gadget-animatedIcons.js` derives from
[Minecraft Wiki's Gadget-site.js](https://minecraft.wiki/w/MediaWiki:Gadget-site.js),
obtained through matchaflavoured.wiki. It has been adapted to plain DOM operations
and a shared animation clock. The recorded source's default is CC BY-NC-SA 3.0;
the exact imported revision and any code-specific exception remain unverified.

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
