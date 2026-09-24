# Port to Minecraft 26.3: rehearsal (September 2026)

The pack's `26.3` branch (`17c4de16`, 60 commits past the release `f6c6094c`) ports it to Minecraft
26.3. This file records what was rehearsed against it before any release came from it, what already
works, and what the autopilot still has to do when the release lands. None of the 26.3 output is
committed: `main` still describes the 1.12.2-beta release.

## What works now
`tools/extract.py` reads both formats and exits 0 on the 26.3 branch. `tools/mcformat.py` translates
each 26.3 file to the 26.2 names as it's loaded, so `data.json` and `generate.py` see one shape:

| 26.3 | read as (26.2) |
|---|---|
| loot `modifier`: one function, a list, or a `minecraft:sequence` | `functions`: a flat list |
| `condition`: one predicate, a list, or one `all_of` | `conditions`: a list |
| predicates' and functions' `type` | `condition` / `function` |
| a predicate named by ID (`"minecraft:tool/can_silk_touch"`) | that predicate file, inlined |
| `match_block` with `blocks` and `state` | `block_state_property` with `block` and `properties` |
| tag entries' `items: "#tag"` | `name: "tag"` |
| trades' `given_item_modifier` | `given_item_modifiers` |
| criteria: long-form entity predicates, single predicates, `recipes` | short form, lists, `recipe_id` / `recipe` |

Other 26.3 changes that are handled:
- **Cooking times.** 26.3 moves the blast furnace's and smoker's double speed from the recipes to
  the fuel (`cooking_fuel` → `speed_multiplier` 2 in `block/fast_cooking`), and every recipe's
  `cookingtime` doubles to match. `extract.py` records each station's speed with vanilla fuel
  (`cooking_speed`, 26.3 only) and `generate.py: cook_ticks()` divides by it as the game does
  (`ceil(cookingtime / speed)`), so blast furnace and Mud Kiln times stay the real times. The
  update report compares real times too.
- **The Seagull Egg's `chicken/variant` component** is in `KNOWN`: it says which chicken hatches
  from the egg, which the page says in prose. No table shows it.
- **A call to a function that doesn't exist** used to crash `extract.py`. It is now printed as
  `extract.py: pack bug: …` and the build continues. On the branch, `timers/2s/timer.mcfunction`
  calls `matcha:timers/2s/traverse`, but the file is `traversal`.
- `update_report.py` treats spellings that mean the same thing as equal (an empty `conditions`
  that was left out, a uniform count's explicit `type`, a one-item entity predicate list). The
  report only lists real changes.
- `entity_models.py` sends its own User-Agent. The JDK download refused Python's default one (403).

**Proof.** For the pinned commit, `build/data.json` and `wiki/generated` are byte-identical before
and after (the Check workflow enforces the second). On the 26.3 branch, the data keeps every kind of
fact that the old extractor lost: 787 drop counts, 292 entry conditions, 1,100 pool conditions
(26.2: 710, 269, 1,043) and the "Silk Touch" and "Fortune increases chance" notes. The loot-named items
Fish Bones, Tallow, Sulfur Goo, Fox Pelt and the new Seagull Egg are all there. The 16 placeholder
trades are still skipped, and the explorer maps keep their names. `tests/test_mcformat.py` checks each
translation on the pack's own files.

## What a 26.3 release still needs
1. **The structure renderer** (`tools/render/src/structure.js`). 26.3 renames a processor rule's
   `output_state.Name` / `Properties` to `id` / `properties`, so 23 renders (every Abbey and Papal
   Outpost piece that runs a processor list) fail with `reading 'includes'`. The fix is one line:
   ```js
   name = nsid(r.output_state.Name ?? r.output_state.id); props = r.output_state.Properties ?? r.output_state.properties ?? {}
   ```
   It isn't committed yet because any renderer change redraws all 85 renders. The port redraws them
   anyway, because `tools/source.lock` changes. With the fix, 83 of 85 renders are pixel-identical to
   26.2's. The Abbey isometric view and Papal Outpost tent1 differ by 27 and 61 pixels (small texture
   changes).
2. **`render.py --audit`** needs a picture or a `skip` for the new Seagull Roost
   (`template:matcha:seagull_roost/small_1`).
3. **`entity_models.py`** for 26.3 gives 361 layers. Three are new (Poplar Boat, Poplar Chest Boat,
   Cushion), and the ender dragon's model changed. The Ender Dragon render still comes out identical.
   Commit the JSON with the port.
4. **Icons:** `images.py` draws all 1,882 with no fallbacks. There are 122 new icons (poplar wood,
   cushions, wool and concrete slabs and stairs, Seagull Egg, camp maps). Of the existing icons, 22
   change, all expected: vanilla 26.3's map textures, and Chocolate, whose texture upstream fixed.
5. **`lint_pages.py`** flags 6 pages whose `{{Source}}` files are gone: Biomes and Hellspore
   (`configured_feature/nether_wart.json`), Dungeon and Spawner (`monster_room.json`), Chocolate and
   Known bugs (`models/item/mushroom_stew.json`).
6. **The update report** has 237 lines to work through. Another 607 are folded away because no
   hand-written page depends on them.

   | Heading | Lines | Folded |
   |---|---|---|
   | Items (123 new, 13 changed, 1 removed) | 137 | |
   | Recipes | 21 | 478 (477 new) |
   | Loot tables | 1 | 94 |
   | Enchantments | 18 | 28 |
   | Advancements | 5 | 4 |
   | Source files the generator doesn't read | 51 | |
   | Pages citing deleted or moved files | 3 | |
   | changelog.md | 1 | |
   | Names (lang) | | 3 |

   New folders to decide on: `chicken_variant` and `chicken_sound_variant` (Seagull and Bobwhite
   chickens), `worldgen/feature`, the Seagull Roost structure, and `favorite_food/food_trades`.
   `wiki/generated` changes in 907 files (297 changed, 610 new or removed).
7. **Pack bug to report** if the release ships with it: the `traverse` / `traversal` call above.
   If it ships, put it on "Known bugs".

## Steps for the autopilot when the 26.3 release lands
1. Step 0 as usual. `fetch_sources.sh --update` moves `tools/source.lock` to the release and
   `tools/mc_version.txt` to 26.3, and fetches vanilla 26.3.
2. `python3 tools/extract.py` must exit 0. If it exits 3, the release has a format change the branch
   didn't. Handle it in `tools/mcformat.py`, with a test in `tests/test_mcformat.py`.
3. Apply the `structure.js` line above, then run `python3 tools/entity_models.py`,
   `python3 tools/render.py` and `python3 tools/render.py --audit`. Add the Seagull Roost render or skip.
   Commit `entity_models.json`, `wiki/renders/` and `tools/renders.json`.
4. `python3 tools/generate.py`, `python3 tools/lint_pages.py` (fix the 6 citations) and
   `python3 tools/update_report.py`. It is a big update, so split the report by heading between agents
   (AUTOPILOT.md, step 4).
5. Add "Known bugs" entries for any pack bug `extract.py` prints.
