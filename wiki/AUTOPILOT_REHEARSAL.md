# Autopilot rehearsal: a simulated 1.12.2-beta release (September 2026)

The daily routine follows `AUTOPILOT.md`, but until now it had never handled a real release. This
rehearsal ran the procedure for real, in a cloud session like the routine's, on an update whose right
answer was already known. The wiki was rolled back to 1.12.1-alpha (`tools/source.lock` = `027108ab`,
with the two 1.12.2-beta Modrinth versions removed from `tools/upstream.json`), and the procedure then
ran steps 0 to 5, the Monday port rehearsal and step 6's watchdog. Pushing, the PR, labelling, merging
and `check_upstream.py --record` were skipped. The rolled-back state was never committed.

Since the pages already described 1.12.2-beta, the ideal page diff was nearly empty. Every page the
procedure had to change was a real error or gap, and every tool problem was a procedure bug.

## What ran, and how long it took
| Step | Time | Result |
|---|---|---|
| 0: `pip install`, `check_upstream.py` | 7 s | status 10: two new releases, no videos, description unchanged |
| 2: fetch, extract, `--snapshot`, `--update` | 50 s | `release_commit.py`: 1.12.2-beta = `f6c6094c`, all 6,735 files identical |
| 2: `images.py`, `generate.py`, `diagrams.py` | 30 s | `wiki/generated` and `wiki/diagrams` byte-identical to the known answer |
| 2: `render.py` (all 85, as a changed `source.lock` forces) | 6 min | all byte-identical |
| 3: `update_report.py` | 12–30 s | 2,911 lines at first; 701 after the fixes below |
| 4: six writer agents, one per heading (in parallel) | 5–12 min | 65 pages corrected (below) |
| 4a: three review agents (in parallel) | 4–8 min | 10 further corrections, no claim removed |
| 4b: `render.py --audit`, transcript citations | 1 s | pass; both transcripts cited |
| 5: `lint_pages.py`, `build_xml.py` | 2 s | 0 problems |
| Monday: `dry_run.sh main`, `dry_run.sh 26.3` | 15 s, 44 s | as `wiki/PORT_26_3.md` says (6 dead citations on 26.3) |
| 6: `watchdog.py` against https://matchaflavou.red | 2 s | passes; there is no build stamp until PR #23 deploys |

The whole update took about 45 minutes of wall time. The nine agents used about 1.8 million tokens:
writers about 175–275k each, reviewers about 150k each. Nothing needed Docker. Every network call
worked through the session's proxy: Modrinth, YouTube (`yt-dlp`), GitHub, misode/mcmeta and the live site.

## What broke, and the fix
- **`extract.py` crashed on a plain-number pack format** (`"min_format": 88.0`, as 1.12.1-alpha wrote it).
  The version guard compared one-element lists, and Minecraft's own `[107, 1]` form would have failed
  it too. Fixed with `mcformat.pack_format()`, with tests.
- **The update report was 2,911 lines (673 KB).** Most of it was noise from this release's reorganisation:
  - `main:` → `matcha:` for 2,100 IDs and every reference to them. Now compared under the new IDs.
  - Item models moved to `matcha:`. Handled the same way.
  - git's rename limit: 8,713 changed files turned renames into deletions plus additions. Now `-l0`, and
    unchanged moves get no line.
  - Tooltip glyphs changed (`🛡 3` → `⟦Armor⟧ 3`). Lore is now compared without glyphs.
  - History citations pinned with `at=` counted as stale. They don't any more.

  The report is now 701 lines. Without its collapsed sections it is 149 KB, so step 5's fallback still
  applies: the headings go in the PR body and the lines go in PR comments.
- **Step 0's `git checkout main`** fails in a session whose clone has only its assigned branch. It now
  runs `git fetch origin main && git checkout -B main origin/main`.
- **Parallel writers overwrote each other.** One agent ran `git checkout` on a page to undo its own
  edit, which discarded another agent's edit (it was put back by hand). `AGENT_BRIEF.md` and step 4 now
  forbid resetting pages.
- **History rows for bugs that no release had.** The Cod almanac "fix" was a typo made and fixed on
  `main` between the two releases. Step 4 now says a History row compares the two releases' files.
- **The watchdog checks the checked-out commit.** Run from the PR branch, it reported "main changed 0
  hours ago". Step 6 now checks out `main` first.
- An extractor traceback (a file it reads by name is gone) wasn't covered by step 2, which covered
  only exit 3. It now is.
- `dry_run.sh` printed git's detached-HEAD advice. Silenced.

## Page errors the procedure found
These pages were already on 1.12.2-beta but were wrong or missing something, each checked against both
release commits:
- **Wrong numbers:**
  - Wheat gives 1–4 grain, not 0–3.
  - Carrots give 2–8 with both bonuses.
  - Adamant Dolabra deals 7 damage, Shakudo Mattock 2, and Steel Claymore has attack speed 0.7.
  - Hepatizon movement bonuses were wrong.
- **Wrong claims:**
  - The Mouthpiece's trivia said the 1.12.1 release notes gave the Divine Fragment's price wrongly.
    They were right: the price went from 1 heart to 2 in 1.12.2.
  - Electrum tools didn't "lose Warding". Their levels changed.
  - Cod had a 1.12.2 fix for a bug no release had.
  - Adamant tools smelt cobblestone into limestone, not stone.
  - Poplar recipes "not in the source": they shipped and never worked.
- **Missing 1.12.2 history** on about 50 pages:
  - Warm Saltwater, axolotl and elytra advancements became unlockable.
  - The bulk blocks.
  - The Nazar and Baked Golden Apple swapped base items.
  - The Cleaver rename.
  - Shepherd's Shears changes, the Crook's stats and the pickaxe harvest tags.
  - Sweet berry bushes give 2–3 berries at any age.
  - Naan heals 4.

Lines per heading, and how many needed a page change: Items 258/37, Recipes 99/14, Loot and
Enchantments 110/4, Trades 102/8, Advancements 69/10, Source files 322/0.

## What still needs a human
- **The report's lines are thin for trades and loot.** "Changed (wants)" and "Changed loot table (nested
  tables)" don't show what changed. Agents diffed the raw files, which cost most of their time. Showing
  old → new for the changed fields would help.
- **Renames of enchantment IDs** (`warding0` → `warding_1`) look like level changes. Only the lang file
  tells whether the shown level moved. Comparing display names would fix it.
- **Renamed files and items** (`bronze_*` → `hepatizon_*`, Butcher's Knife → Cleaver) are still listed
  as a removal plus an addition.
- **Rendering was never checked locally** (no MediaWiki in the session). The PR's Check workflow is the
  only render check, as AUTOPILOT.md intends.

## Noticed, not fixed
- About 15 fish pages have a raw line break inside their 1.12.1-alpha `{{History line}}`. It predates
  this update, and pages render it.
- The Mason's bulk malachite trade names `item.kleispack.trade.bulk_prismarine`, which has no English
  text, so the game probably shows the key. It could go on "Known bugs" after checking in game.
- `matcha:mechanics/intrinsic_enchants_obtained` now matches `custom_data` exactly with
  `has_intrinsic_enchants:true`, while the recipes set `1`. If the game treats these as different,
  smithed items never get their intrinsics. This needs checking in game before any page says so.
- `generate.py` shows wheat grain as count 1: binomial bonuses aren't modelled in the Sources tables.

## Confidence
**High** that the next ordinary release goes through unattended: the tools, the renders and the
generated output all reproduced exactly. The remaining costs are time and tokens (about an hour and
2 million tokens for a release this big) and a PR whose checklist has to be split into comments. A
reorganisation like 1.12.2-beta's makes `extract.py` fail loudly (step 2 now says what to do). The 26.3
port is covered by `wiki/PORT_26_3.md`.
