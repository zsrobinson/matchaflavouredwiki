# Matcha Flavoured Wiki: style guide

The wiki follows the [Minecraft Wiki](https://minecraft.wiki/) closely. That covers
organization (which pages exist and how they are sectioned), tone and wording. If you're
unsure how to write something, find the equivalent vanilla page on minecraft.wiki and
copy its shape. The design (skin, CSS, main page) is copied from
[matchaflavoured.wiki](https://matchaflavoured.wiki/).

## Where facts come from

Every statement has to be checkable against a primary source. In priority order:

1. **The pack's code** in `source/matcha-flavoured/` (datapack JSON, `.mcfunction`
   files, resource pack lang and models). This always wins.
2. **Official release notes**: `source/changelogs/*.md` (Modrinth) and
   `source/matcha-flavoured/changelog.md` (the in-development changelog).
3. **The developer's videos**: `transcript.txt` (the design video) and `sources/transcripts/`. Use it
   for intent, design reasoning and history, never for numbers the code contradicts.
   The transcript is auto-generated, so names in it are misspelled ("Shikudo" is
   Shakudo, "delabre/Maddox" are dolabra/mattock, "Benzene" is correct).
4. Vanilla data in `source/vanilla-*` is only used to describe what the pack
   *changed*.

Never use other fan wikis, unofficial ports, forks or videos by third parties. If the code
and a changelog disagree, describe the code and mention the discrepancy in a note.

Cite non-obvious facts with a `<ref>` pointing at the file:
`<ref>{{Source|MF_datapack/data/matcha/function/mechanics/heart_container/death.mcfunction}}</ref>`.
Pages that use refs end with `== References ==` and `{{reflist}}`.

## Language

- **American English**, as on minecraft.wiki ("armor", "color", "favor"), except in
  proper names that the pack spells otherwise. **Item names are exactly the in-game
  `en_us` names** (e.g. *Divine Favor*, *Stabilized Estus*, *Sack*), even where the
  pack's own prose says "armour".
- Encyclopedic third person and present tense. Write "the player", never "you",
  "we" or "I". No exclamation marks, jokes, hype or opinion ("very useful", "amazing").
  Keep the pack author's personality in quotations and trivia, not in the article voice.
- The lead sentence bolds the page subject and says what it is:
  `A '''pumpkin empanada''' is a [[food]] item that grants [[Resistance]] and heals 4 hearts.`
  `'''Death''' in Matcha Flavoured costs the player a heart of maximum health instead of their items.`
- **Item names are lowercase in running text**, like on minecraft.wiki: "a pumpkin empanada",
  "craft a crystal heart", "with an [[oven]]". Keep capitals for proper nouns (Prayer of
  Demeter, The Divine Comedy, the Ender Dragon, the Wither, the Abbey) and at the start of a
  sentence. Links are first-letter case-insensitive: `[[oven]]` works.
- Link the first mention of each concept in an article, not every mention.
- Numbers: use digits for game values ("8 minutes", "4 hearts", "Resistance I"). Health is
  shown with `{{Hp|8}}`, which renders as "8 (♥ × 4)". Durations are written like "8:00"
  in tables and "8 minutes" in prose.
- **An item's own numbers come from the data.** When a sentence states an item's heal amount,
  effect level or duration, eating or cooking time, damage, attack speed, mining speed, durability,
  armor or toughness, write `{{Value|<item>|<field>}}` instead of typing it, so the prose changes
  with the pack like the infobox does: "heals {{Value|Canned Golden Apples|heals}} and grants
  {{EffectLink|Absorption}} {{Value|Canned Golden Apples|level|effect=Absorption}} for
  {{Value|Canned Golden Apples|duration|effect=Absorption}}". `format=` picks the form ("2:00" is
  `format=clock`; [[Template:Value]] lists them). Keep typing numbers you worked out (sums,
  comparisons, "twice as long"), chances, vanilla values and anything historical (History sections,
  version pages, quotes).
- Name the vanilla thing a renamed item replaces once, with `{{MCW|...}}`. For example,
  "Obols replace {{MCW|Emerald|emeralds}}." Then use the pack's name everywhere else.
- Refer to the pack as "Matcha Flavoured" (the official spelling), and in vanilla
  comparisons use "vanilla" or "vanilla ''Minecraft''".

## Page types and sections

Section headings are sentence case (`== Obtaining ==`, `=== Chest loot ===`). Use only
the sections that have content, in this order.

**Item / block** (e.g. [[Pumpkin Empanada]], [[Oven]])
```
{{Vanilla|Furnace}}              (only for renamed/changed vanilla things)
{{Infobox auto}}
Lead paragraph.
== Obtaining ==
=== Crafting ===   {{Recipes}}       (or === Cooking ===, === Smithing === ...)
=== Chest loot === / === Mob loot === / === Fishing === / === Trading ===   {{Sources}}
=== Natural generation ===
== Usage ==
=== Food === / === Crafting ingredient === ({{Uses}}) / === Smithing === / === Trading ===
== Behavior ==  (blocks and mechanics that need explaining)
== Advancements ==
== History ==     {{History|...}}
== Trivia ==
== See also ==
== References ==
{{Navbox ...}}
[[Category:...]]
```
`{{Recipes}}`, `{{Uses}}` and `{{Sources}}` transclude tables generated from the code, so
write them once and they stay current. Add prose around them for anything the tables
can't express (hidden mechanics, why something matters, notes on progression).

**Mechanic** (e.g. [[Death]], [[Warding]], [[Hunger]]): the lead, then `== Mechanics ==`
(or topic-specific sections), then `== Difficulty ==` if it varies, then `== History ==`,
`== Trivia ==`, `== See also ==` and `== References ==`.

**Mob** ([[Zombie]]): `== Spawning ==`, `== Drops ==`, `== Behavior ==`,
`== Difficulty ==`, then History and the rest. Describe only what the pack changes, and
link `{{Vanilla}}` for everything else.

**Villager profession** ([[Farmer]]): the lead (including which vanilla profession it
replaces and its job site block), `== Trades ==` with `{{Data/Trades/Farmer}}`, notes on
trade mechanics, and `== History ==`.

**Structure** ([[Abbey]]): `== Generation ==`, `== Structure ==`, `== Loot ==` (with the
`{{Data/Loot/minecraft/chests/...}}` tables), `== Mobs ==` and `== History ==`.

**List / overview pages** ([[Food]], [[Armor]], [[Tools]], [[Enchanting]]): short intro,
sortable wikitables, and `{{Main|...}}` hatnotes into each detail page.

## Templates

| Template | Use |
|---|---|
| `{{Infobox auto}}` | Infobox for an item. Override with `|type=`, `|intrinsics=`, `|bonus=`, `|renewable=`, `|caption=`. |
| `{{Infobox|title=|invimage=|...}}` | Manual infobox for mechanics, mobs, structures, effects, enchantments (see Template:Infobox for fields). |
| `{{Recipes}}`, `{{Uses}}`, `{{Sources}}` | Generated recipe, usage and source tables. They take an item name when it differs from the page name. |
| `{{Crafting|A1=..|Output=..}}`, `{{Cooking|station=Oven|Input=|Output=}}`, `{{Smithing|...}}`, `{{Stonecutter|...}}` | Hand-placed interfaces. |
| `{{Slot|Item}}`, `{{ItemLink|Item}}`, `{{EffectLink|Resistance}}` | Icons. Item icons are `File:<Item Name>.png`. |
| `{{G|Warding}}` | The pack's tooltip glyphs (Health, Warding, Doom, Cleanse, Magic protection, Armor, ...). |
| `{{Hp|8}}` | Health points, drawn as hearts. |
| `{{Value|Item|field}}` | One of an item's own numbers in prose, from the data: `heals`, `damage`, `attackspeed`, `miningspeed`, `durability`, `armor`, `toughness`, `eat_time`, `level`/`duration` with `effect=`, `cook_time` (with `station=` where stations differ); `format=` for other forms. `tools/values.py "Item"` lists them. |
| `{{Diagram|Warding|caption=...}}` | A diagram from `tools/diagrams.py` (see "Diagrams"); `align=right|width=360` for small ones. |
| `{{Main|X}}`, `{{See also|X}}`, `{{About|...}}`, `{{Distinguish|X}}` | Hatnotes. |
| `{{Vanilla}}` / `{{Vanilla|Emerald}}` | Links the vanilla page on minecraft.wiki. |
| `{{MCW|Page|text}}` | Inline link to minecraft.wiki. |
| `{{Source|path|label}}` | Link to a file in the pack repository at the synced commit. |
| `{{Cite video|quote=...}}`, `{{Cite changelog|1.10|quote=...}}` | References to the developer's video and release notes. |
| `{{History|{{History line|1.0|...}}{{History line|1.10|...}}}}` | Version history table. |
| `{{Version|1.10}}` | Link to a version page. |
| `{{Spoiler}}` | Put before sections about secrets (hidden recipes, lore, horror). The wiki documents them, hidden until clicked. It covers the rest of its section (see "Spoilers" below). |
| `{{Upcoming}}` / `{{Planned}}` | Content that is only in `changelog.md` or the developer's plans. |
| `{{Navbox|title=|group1=|list1={{Nav item|X}}...}}` | Navigation boxes at the bottom of pages. |
| Generated tables | `{{Data/Food table}}`, `{{Data/Renamed items}}`, `{{Data/Enchantments}}` (and `/New`, `/Vanilla`, which take notes by enchantment id: `{{Data/Enchantments/New|matcha:reach=...}}`), `{{Data/Blessings}}`, `{{Data/Ofuda}}`, `{{Data/Intrinsic items/<page>}}`, `{{Data/Trades/<Profession>}}`, `{{Data/Loot/<namespace>/<path>}}`, `{{Data/Advancements/<tab>}}`, `{{Data/Station/<station>}}`, `{{Data/Fishing/...}}`, `{{Data/Splash texts}}`, `{{Current version}}`. |
| Difficulty and set bonus data | `{{Data/Difficulty}}` (all mob changes), `{{Data/Difficulty/<Mob>}}` (one mob's table), `{{Data/Difficulty/<Mob>/Infobox|max_health}}` (one attribute in a line, for infoboxes), `{{Data/Set bonus/<score>}}` (a table per equipment score) and `{{Data/Set bonus|adamant_armour=4}}` ("Absorption I (2 extra hearts) for 31 seconds every 30 seconds"; `show=every` or `show=lasts` gives just the seconds), all generated from the pack's functions. A note for one row of a table goes in a parameter named by the row ID: `{{Data/Difficulty/Zombie|max_health/baby=...}}`. |

## Spoilers

Spoilers are hidden until the reader clicks them, unless the reader turned that off (the eye beside
the dark-mode toggle; the switch in the phone menu). What is hidden:
- **What a `{{Spoiler}}` box covers:** the rest of its section, up to the next heading of the same or a
  higher level. A box in the lead covers the rest of the page, so put it where the secret starts: after
  the infobox and hatnotes of a page that is a secret as a whole, under the heading of a section that is.
- **Every mention of a secret:** its links, and the table rows that link or name it. A secret is what the
  pack itself marks as secret, and nothing else (`generate.py: secret_items()` writes the list to
  `MediaWiki:Mfw-secrets`, so a release that adds one updates it):
  - the items named by the two secret-cooking advancements, "Hidden Flavors" ("Cook a secret
    Ingredient") and "Wait, you can make that?" ("Cook a secret Meal");
  - the dishes only a Cooking Recipe unlocks (`advancement/cooking_recipes/`), and those Cooking Recipes;
  - hidden advancements (`"hidden": true`), which the game shows only once earned: their titles, and
    their rows in `{{Data/Advancements/<tab>}}`. Not the Angler's Almanac, whose entries are a catch log
    hidden only until that catch is made (its fish are documented on the fishing pages).

  A recipe missing from the recipe book is not a secret by itself: slab reversals, campfire cooking and
  the like are never unlocked either. The developer also mentions secret tool, armor and shield recipes,
  but the pack's files don't mark any, so none are treated as secret.

Links are caught automatically; words are not. Outside a `{{Spoiler}}` box, don't name a secret in plain
text or in a heading: link it, move the sentence under the box, or, for one sentence or list item that
describes a secret, wrap it in `<span class="mfw-spoiler">`. A section about a secret gets a neutral
heading ("Secret recipe", not the dish's name). `tools/lint_pages.py` and `tools/check_site.py` fail on
a secret a reader would see.

Be conservative: a spoiler is something the pack hides on purpose (a secret recipe or ingredient, a hidden
advancement, a secret in a structure). Ordinary mechanics, drops and recipes the recipe book shows are not
spoilers, even if a player might not know them yet. Other markup can use `class="mfw-spoiler"` (a row or
an inline span is blacked out, as minecraft.wiki's inline spoilers are), but prefer `{{Spoiler}}`.

## Versions

The documented version is the latest release, currently `{{Current version}}`: the download
players have. The data and every `{{Source|...}}` link come from the commit that release was made
from (`tools/source.lock`). Where the repository's `main` branch already differs (bug fixes and
features after the release), describe the release in the body and the difference as upcoming:
`{{Upcoming|type=section}}` (or `type=page`) above content that exists only on `main`, and a
`{{History line|Upcoming|2=...}}` row. Cite that code at a commit on `main`:
`{{Source|path|at=<commit>}}`. Version pages are titled `Matcha Flavoured <version>`
(e.g. "Matcha Flavoured 1.10") and history lines link to them.

## Pictures

Pictures are drawn from the pack's files (`tools/renders.json`, drawn by `tools/render.py`); nobody
takes screenshots. Every render is a true isometric view, as on minecraft.wiki: seen from a corner and
from above at the angle that makes a cube's three faces equal (`tools/render/src/camera.js`); a render
only chooses which corner. A page gets one when it is about something whose look an icon or a slot can't show:

- **Structure** pages: the whole structure in the infobox (`File:<Structure> isometric view.png`),
  or its defining piece when the whole doesn't read at infobox size; and every template the page
  describes, in a `<gallery>` under the section that describes it. A page about a vanilla structure
  whose piece the pack replaces shows that piece.
- **Mob** and **villager profession** pages: a render in the infobox (`File:<Mob> render.png`), with the
  pack's texture where it has one.
- **Armor set** pages: the full set without a body, as a thumb at the top of `=== Armor ===`
  (`File:<Material> armor render.png`).

Nothing else gets one. Items and blocks have their icon and slots, and mechanics and overview pages
would need diagrams, which are a different thing. When a page qualifies but can't have its picture yet
(a mob whose animation the renderer lacks) or a template isn't worth showing (an invisible road connector), put it in
the `skip` list of `tools/renders.json` with the reason. `python3 tools/render.py --audit` lists every
gap; it passes when each one is rendered or skipped.

## Diagrams

Diagrams are drawn from the pack's data by `tools/diagrams.py` (one function per diagram, in
`tools/diagram_defs/`) and committed in `wiki/diagrams/`, so a pack update redraws them. A page shows
one with `{{Diagram|<Name>|caption=...}}`, which picks the light or dark drawing to match the theme.

Draw a diagram only when the picture is quicker to take in than the sentence it replaces. A good one
makes a reader think "oh, that's easier than reading all that"; a bad one makes them decode a chart to
get a fact the text could have stated plainly. The ones that earn their place:

- places and shapes: where ores generate by Y level, a radius drawn to scale, a cross-section of where
  mobs spawn;
- time: the day cycle, a schedule, the moon's phases, a release timeline, two effects overlapping;
- overviews rich in icons: a progression, a crafting chain, the tiers of a set of equipment.

Don't draw:

- a flowchart of a rule that fits in one or two sentences (the checks a spawn runs, how a level is
  chosen);
- a table redrawn as a picture: if it's rows and columns, make it a wikitable, generated from the data
  when it can be (the mining levels table on the Tools page);
- a chart that needs a legend of more than a few entries to read, or bars for three or four numbers
  (effect durations, odds, sleep speeds).

A small spatial picture (one radius, one structure's area) goes beside the text as an aside
(`width=360|align=right`), at the top of the section it illustrates. A large one that spans time or
places runs full width under its section's opening paragraph.

One diagram per section at most, with a one-sentence caption saying what it shows. The numbers come
from the pack's files at draw time, never typed in; the look comes from `tools/diagrams.py`, so every diagram matches the others: the pack's brown
inventory panel (like the station screens), the Minecraft font with its shadow, boxes as recessed
slots, item icons and HUD hearts, and areas drawn on a block grid (one cell per block, a heavier line
every 16). Ranges the game measures as a distance (`distance=..N`) are circles over that grid, because
that's the shape the game uses. Full width is 760px; a small one floats right at about 360px
(`align=right`).

## Files

Pages live in `wiki/pages/<Namespace>/<Title>.wiki`. A `/` in a title is written as `%2F`
in the file name, and Lua modules end in `.lua`. Never edit `wiki/generated/`. It is
rebuilt from source by `tools/generate.py`, and a hand-written page with the same title
replaces the generated stub.
