# Brief for agents writing wiki pages

You are writing part of the Matcha Flavoured Wiki: a MediaWiki encyclopedia for the
Matcha Flavoured datapack, meant to become the go-to reference for the pack at the quality
of minecraft.wiki. The repository root is `/Users/zsrobinson/code/matcha-wiki`.

## Read first
1. `wiki/STYLE.md`: language, page structure and templates. Follow it exactly. Matching
   minecraft.wiki's tone and organization is the most important requirement after accuracy.
2. `wiki/PAGES.md`: the page plan and which area owns what. Write only your area's pages.
   Link to other areas' pages by their planned titles.
3. `transcript.txt` and `sources/transcripts/*.txt`: the developer's videos about the pack (design
   intent, history). Cite them with `{{Cite video|id=<video id>|title=<title>|quote=...}}`.

## Sources (only these)
- `source/matcha-flavoured/`: the official repository, checked out at the synced commit.
  `MF_datapack/data/**` holds the logic (functions, recipes, loot tables, enchantments,
  advancements, predicates, tags, worldgen). `MF_resourcepack/assets/minecraft/lang/en_us.json`
  holds the names and descriptions. `changelog.md` covers the in-development changes, and
  `README.md` and `my_current_and_future_plans.md` hold the developer's notes.
- `source/changelogs/*.md`: official release notes for every version (from Modrinth).
- `source/vanilla-data`, `source/vanilla-summary`, `source/vanilla-assets`: vanilla 26.2,
  used only to say what the pack changed.
- `build/data.json`: everything already extracted from the source. `python3 tools/query.py`
  searches it. Examples: `tools/query.py item "Steel Pickaxe"`, `tools/query.py search curry`,
  `tools/query.py loot minecraft:entities/zombie`, `tools/query.py ench matcha:warding_1`,
  `tools/query.py adv search heart`, `tools/query.py trades farmer`, `tools/query.py renames`.

Never use the web, other fan wikis, forks or ports. Read the actual `.mcfunction` and JSON
files behind every mechanic you describe. Grep widely: most mechanics are spread across
`function/`, `advancement/` (used as triggers), `predicate/`, `enchantment/` and
`tags/`. State exact numbers (durations in ticks → seconds, chances, damage, ranges, scores) and
cite the file with `<ref>{{Source|<path relative to source/matcha-flavoured>}}</ref>`. Where the
code and the release notes or video disagree, go with the code and add a note. If you can't
determine something from the source, leave it out. Don't guess.

## Writing
- Create or overwrite files in `wiki/pages/Main/<Title>.wiki` (a `/` in a title is written as
  `%2F`). You may create navbox templates for your area as
  `wiki/pages/Template/Navbox <area-topic>.wiki` (e.g. `Navbox food.wiki`) and use them on
  every page in your area.
- Don't edit `tools/`, `wiki/generated/`, `MediaWiki:` pages, shared templates or pages owned by
  other areas. If a shared template or the generator is wrong or missing something, say so in
  your final report. You may add a new small template prefixed with your area name if you truly need one.
- Item articles: use `{{Infobox auto}}` plus `{{Recipes}}`, `{{Uses}}` and `{{Sources}}` (all
  generated from code) and write the prose around them: what the item is for, how it fits
  progression, exact behavior, history and trivia. Every item in your area should get a real article,
  not the generated stub. Small closely-related items can share one article. Make the others
  redirects (`#REDIRECT [[Main article#Section]]`), the way minecraft.wiki does.
- History sections: go through every changelog in `source/changelogs/` (and `changelog.md`
  for unreleased work) for mentions of your topics, and write `{{History|...}}` tables. The
  release date is in each changelog file's name.
- Add categories: `[[Category:Food]]`, `[[Category:Armor]]`, `[[Category:Mechanics]]`,
  `[[Category:Mobs]]` and so on, following minecraft.wiki's category names.

## Checking your work
- `python3 tools/preview.py "Title" "Other Title" ...` imports your pages into the local wiki
  (http://localhost:8080) and reports template/Lua errors, red links and missing files. Fix
  every error. Red links are fine only for titles in `wiki/PAGES.md`.
- `tools/screenshot.sh "Title" /tmp/x.png 1400 1800` renders a page to PNG. Look at a
  few important pages to check layout.
- Don't run `tools/build.sh` or `tools/sync.sh` and don't commit. The coordinator does that.

## Final report
Reply with: the pages you wrote (titles), any facts you couldn't pin down, any contradictions
between code and release notes, and any bugs or gaps you found in the generated data or
shared templates.
