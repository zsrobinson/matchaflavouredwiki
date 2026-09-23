# Brief for review agents

You are reviewing and improving pages that other agents already wrote. The goal is an
encyclopedia as good as minecraft.wiki: every fact right, the writing consistent, nothing
missing. Read `wiki/AGENT_BRIEF.md` and `wiki/STYLE.md` first. The same sources, tools and
rules apply.

## What to check on every page in your areas
1. **Accuracy.** Re-verify every number and behavioral claim against the source files
   (`source/matcha-flavoured/...`), not against the other pages. Fix anything wrong. Where the
   page says "the code does X", open the file and confirm it. Cited files must exist; check
   `{{Source|...}}` paths.
2. **Completeness.** Compare the page with what the code actually has. Look for items,
   recipes, mechanics, edge cases, difficulty differences and history entries the page misses.
   Check that every item in the area has a real article or a deliberate redirect (no leftover
   generated `{{Stub}}` for a pack-relevant item: `grep -l "{{Stub}}" wiki/generated/Main/*`).
3. **Generated tables.** The generator was fixed after the first pass. `{{Recipes}}`, `{{Uses}}`,
   `{{Sources}}`, `{{Data/Trades/<Profession>}}` and `{{Data/Loot/...}}` are now reliable:
   - discard placeholder trades are gone, map names are shown and biome limits are listed;
   - custom items built on a vanilla base (fish on cod, electrum on netherite) are named correctly;
   - intrinsic names and links are right;
   - drop chances account for counts of 0, Fortune bonuses and biome-exclusive fishing tables;
   - vanilla loot tables the pack leaves alone are included.

   Where a page hand-copied a table *only* to work around those bugs, replace it with the
   generated template, unless the hand table adds real information. First check the generated
   output (`python3 tools/preview.py "Template:Data/Trades/Farmer"`), and report anything still wrong.
4. **Style and consistency** (STYLE.md):
   - the lead sentence format, lowercase item names in prose, and no "you";
   - section order;
   - `{{Infobox auto}}` overrides used sensibly;
   - navbox at the bottom, categories, `{{History|...}}` tables and references.
   Make terms consistent across the wiki: one name per concept, as the pack spells it.
5. **Links.** Link the first mention of every concept that has a page. `[[mud kiln]]` style
   lowercase links work: every title has a sentence-case redirect. Don't link vanilla-only
   things that have no page. Use `{{MCW|...}}` for those.

## How to work
- Edit only pages in your assigned areas (listed in `wiki/PAGES.md`), plus their navbox
  templates. If a fact on another area's page is wrong, say so in your report instead.
- Check each page with `python3 tools/preview.py "Title"` (0 errors, no unplanned red links).
  Screenshot a few with `tools/screenshot.sh`.
- Don't run build/sync scripts and don't commit.
- Final report: what you changed (by page), factual errors you corrected, and anything still
  uncertain.
