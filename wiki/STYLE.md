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
3. **The developer's introduction video**: `transcript.txt` in the repo root. Use it
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
| `{{Main|X}}`, `{{See also|X}}`, `{{About|...}}`, `{{Distinguish|X}}` | Hatnotes. |
| `{{Vanilla}}` / `{{Vanilla|Emerald}}` | Links the vanilla page on minecraft.wiki. |
| `{{MCW|Page|text}}` | Inline link to minecraft.wiki. |
| `{{Source|path|label}}` | Link to a file in the pack repository at the synced commit. |
| `{{Cite video|quote=...}}`, `{{Cite changelog|1.10|quote=...}}` | References to the developer's video and release notes. |
| `{{History|{{History line|1.0|...}}{{History line|1.10|...}}}}` | Version history table. |
| `{{Version|1.10}}` | Link to a version page. |
| `{{Spoiler}}` | Put before sections about secrets (hidden recipes, lore, horror). The wiki documents them, but warns first. |
| `{{Upcoming}}` / `{{Planned}}` | Content that is only in `changelog.md` or the developer's plans. |
| `{{Navbox|title=|group1=|list1={{Nav item|X}}...}}` | Navigation boxes at the bottom of pages. |
| Generated tables | `{{Data/Food table}}`, `{{Data/Renamed items}}`, `{{Data/Enchantments}}`, `{{Data/Trades/<Profession>}}`, `{{Data/Loot/<namespace>/<path>}}`, `{{Data/Advancements/<tab>}}`, `{{Current version}}`. |

## Versions

The documented version is the latest release, currently `{{Current version}}`. Wherever the
repository's `main` branch already differs from that release (bug fixes after
1.12.2-beta), describe `main`, since that is what the next download will contain, and
note the difference in History. Version pages are titled `Matcha Flavoured <version>`
(e.g. "Matcha Flavoured 1.10") and history lines link to them.

## Files

Pages live in `wiki/pages/<Namespace>/<Title>.wiki`. A `/` in a title is written as `%2F`
in the file name, and Lua modules end in `.lua`. Never edit `wiki/generated/`. It is
rebuilt from source by `tools/generate.py`, and a hand-written page with the same title
replaces the generated stub.
