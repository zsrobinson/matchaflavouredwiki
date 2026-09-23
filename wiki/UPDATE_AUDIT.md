# Audit: keeping the wiki current (September 2026)

How well does the update process hold up, and what would it miss? This audit traced every step from
"the pack changed" to "the site is deployed". It then tested the process on the largest update in
sight: the pack's `26.3` branch, a port to Minecraft 26.3 that is 49 commits ahead of `main` and touches
1,521 files.

## Short answer
The design is right. The wiki is built from the pack's code, `wiki/generated` is committed so every data
change shows in a diff, and CI rebuilds everything from scratch. Two things were weak:

1. **Silent data loss on format changes.** The extractor read keys it knew and skipped the rest without a
   word. On the 26.3 branch it finished without an error, but every drop count (707), drop condition
   (269) and pool condition (1,043) was gone, along with the custom items named by loot tables (Fish Bones,
   Tallow, Sulfur Goo, Fox Pelt…). Every build check would still have passed.
2. **Big updates rely on the agent's diligence.** The port changes about 2,500 generated files. The
   old instructions said to read `git diff wiki/generated` and grep for affected pages. At that size
   nothing guarantees that every change reaches the prose, and changes outside what the generator reads
   (functions, worldgen, structures) produce no diff at all.

Both are fixed below, and the fixes were tested on the 26.3 branch.

## What was fixed
| Finding | What it would have caused | Fix |
|---|---|---|
| The extractor skips unknown keys silently | 26.3 renames loot `functions` → `modifier` and `conditions` → `condition`, and trade `given_item_modifiers` → `given_item_modifier`. Drop tables would show "1, always" everywhere, the 17 placeholder trades would come back, and explorer maps would lose their names. | `extract.py` checks every key, entry type, loot function, condition, recipe type and item component against `KNOWN` and exits 3 on anything new. On the 26.3 branch it names all eight changes. |
| A vanilla data version mismatch goes unnoticed | Recipes and names would be read from the wrong Minecraft version. | `extract.py` compares the pack's `pack.mcmeta` format with the vanilla data's `version.json`. `fetch_sources.sh --update` reads the Minecraft version from `pack.mcmeta` and fetches that vanilla data. This used to be a manual step. |
| `check_upstream.py --record` saved upstream's state at the *end* of the run | Commits pushed while the agent was working (upstream makes about 10 a day) were marked as seen and never processed. | The pack commit is compared with `tools/source.lock` (what the wiki was really built from). `--record REPORT` marks only the releases and videos that step 0 found. |
| No complete list of what an update changes | Changes that no grep found were missed, especially in areas the generator doesn't read. | `tools/update_report.py`: a checklist with one line per change and the hand-written pages that depend on it. It uses the 2,116 `{{Source}}` citations as a file → page index, and it flags new source folders. For the 26.3 port it gives 629 lines, grouped by heading so that they can be split between agents. Another 1,994 changes are folded away because no hand-written page depends on them. |
| Data templates fail quietly | After a rename or removal, `{{Infobox auto}}` falls back to an empty infobox and `{{Recipes}}` says "None.". The render check can't tell that from a real "none". | `tools/lint_pages.py`, now in the Check workflow, checks every data template and `{{Source}}` path against the pack. On the 26.3 branch it flags 15 pages, including Fish Bones, Tallow and Sulfur Goo, and four pages that cite deleted worldgen files. |
| Ports are only noticed when they land | The biggest update arrives with no warning, all at once. | `check_upstream.py` lists upstream's other branches. On Mondays the autopilot runs `tools/dry_run.sh <branch>` and prepares the extractor in its own PR. |
| No review pass in the autopilot | Review passes have caught about one factual error in every few pages. | New step 4a: a review agent with `REVIEW_BRIEF.md` checks every changed article. |
| Pool-level `set_count` ignored | Sweet berry bushes showed 1 berry. They drop 2–3 when fully grown and 1–2 at stage 2. | Handled in `extract.py`. The generated tables are corrected. |
| Two dead source citations | "Popped Chorus Fruit" and "Natural Lapis Lazuli" linked to files that don't exist. | Fixed. `lint_pages.py` keeps it at zero. |
| `AGENT_BRIEF.md` points agents at a macOS path | Cloud agents are told the repository is somewhere it isn't. | Uses the repository root, and mentions `lint_pages.py` for sessions without a local wiki. |

## How much is generated
- Item facts are well covered. 489 of the articles use `{{Infobox auto}}`, and only 8 pages keep
  hand-typed infoboxes for items that have generated data (the vanilla fish, Splash Potion, two arrows
  and Fox Pelt, each for a reason). 549 of the 694 articles transclude at least one generated table.
- **Hand-typed data tables are the main remaining risk.** These tables copy data the extractor already
  has, so they are correct only until the pack changes:

  | Page | Hand-typed rows | Data it copies |
  |---|---|---|
  | Stonecutter | 344 (of 348 recipes; the page explains the 4 duplicates) | stonecutting recipes |
  | Advancements | about 100 | advancement titles, descriptions, parents |
  | Tools, Armor | about 125 | durability, damage, speed, armor points (item components) |
  | Enchantment | about 50 | enchantment levels, weights and slots |
  | Fish, Favorite food | about 90 | loot tables, food components |
  | Splash texts | 51 | `texts/splashes.txt` (not extracted) |

  `update_report.py` now points at these pages whenever their data changes, so they won't be forgotten.
  Generating them would remove the risk altogether. Each would become a `Template:Data/...` table from
  `generate.py`, the way `{{Data/Food table}}` already works.
- **Numbers in prose** can't be checked mechanically: 486 `{{Hp}}` heal amounts, about 770 percentages
  and about 350 durations in seconds. The update report lists every page that mentions a changed item,
  and the review pass re-checks the numbers. A lasting fix would be small inline data templates
  (for example a generated `{{Data/Heal|Baked Potato}}`) for the most common numbers: heal amounts,
  effect durations, cooking times.
- **Areas the generator doesn't read:** functions, worldgen, structures, predicates, dimension types,
  timelines, trim materials, banner patterns, instruments, jukebox songs and item modifiers. They are
  covered only by prose and `{{Source}}` citations. The update report lists every changed file in them,
  with the pages that cite it.

## Recommendations, in order
1. **Prepare the extractor for 26.3 now,** while the port is still a branch. `tools/dry_run.sh 26.3`
   lists the eight format changes. Read both the old and the new format. CI proves the output for
   `main` stays the same. The Monday rehearsal does this unattended.
2. **Generate the tables above,** starting with Stonecutter and Advancements. Their data is already
   extracted, so this is only `generate.py` and page work.
3. **Add inline data templates** for the numbers most often repeated in prose.
4. **Extract the splash texts** (`texts/splashes.txt`) and the new `item_modifier` folder (upstream
   commit `ac3ccbd8`, pending) if pages come to depend on them.

## Tested
- Guarded extractor at the pinned commit: exit 0 and identical generated output (apart from the
  sweet berry fix). On the 26.3 branch: exit 3 with all eight format changes named, and exit 3 on a
  vanilla version mismatch.
- `update_report.py` on the real pending update (`5bf7c3e2..ac3ccbd8`): one line, the new
  `item_modifier` folder, flagged as a folder the extractor doesn't read. On 26.3: 629 lines.
- `lint_pages.py` on `main`: 0 problems after the two citation fixes. Against 26.3: 15.
- `check_upstream.py` against live upstream: it sees the new commit and the `26.3` branch.
  `--record` refuses to run without a report.
