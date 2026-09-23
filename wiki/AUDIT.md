# Competitor audit (2026-09-23)

What other unofficial Matcha Flavoured wikis and guides cover that we don't, and why. Every
gap closed here was checked in, and cited to, the pack's code (pinned commit), the release
notes, or the developer's videos (`transcript.txt` and `sources/transcripts/`). Nothing was
copied from a competitor.

## Competitors

| Site | Kind | Size / coverage | Notable features we lacked |
|---|---|---|---|
| [matchaflavoured.wiki](https://matchaflavoured.wiki/) | MediaWiki, hand-written, 45 users | 475 articles, 1,144 pages | One page per advancement; British spellings (Armour, Jewellery, Divine Favour, Stabilised Estus); alternate titles (Hypothermia, Hearts, Axes, Prayers…); a Discord link |
| [JeremyVyska/Matcha_wiki](https://jeremyvyska.github.io/Matcha_wiki/) | Static site, fully generated | 1,076 recipes, 356 items, 290 trades, 244 advancements, 292 loot tables, 356 disabled vanilla things | Search across everything; complete "disabled vanilla" list; tooltip symbol legend; tags, sounds, **splash texts**; per-file version diff; secret recipes behind a spoiler toggle |
| [peterbax117/…-wiki-generator](https://github.com/peterbax117/minecraft-matcha-flavored-datapack-wiki-generator) | Offline generated site | Recipes (forward and reverse), trades, structures, archaeology, fishing | **Progression-safe spoiler modes**; reverse recipe lookup; hash-verified comparison between releases |
| [julianfere/…-recipebook](https://github.com/julianfere/mincraft-matchaflavored-recipebook) | Single-file recipe book (Spanish/English) | All recipes and trades | **Crafting tree** (click an ingredient to follow the chain to raw materials) |
| [AriesAlex/matcha-wiki](https://matcha.ariex.ru) | Nuxt site plus a fixed fork of 1.03 (Russian) | 18 long articles, item/recipe catalogue | **Step-by-step guides** past the early game (Hell, End, after the dragon); known-issues page |
| [Evansch0/MatchaFlavouredWiki](https://evansch0.github.io/MatchaFlavouredWiki/) | Generated "field wiki" | Catalogue from recipes, items, advancements, trades, release notes | Checks Modrinth every 30 minutes; new recipes stay hidden until reviewed (spoiler control) |
| [matchaflavored.org](https://matchaflavored.org/) | Guide site | About 15 guide pages: install, start, recipes, smithing routes, food, fishing, advancements, health, **troubleshooting** | Symptom-based troubleshooting; low-spoiler framing |
| [Fandom: matcha-flavoured-datapack](https://matcha-flavoured-datapack.fandom.com/) | Fandom wiki | Small: Getting Started, First Steps, Installing (page list blocked, HTTP 402) | Nothing we lack, as far as could be seen |

Not wikis (skipped): mpetrites' Bedrock port, the Fabric port, forks and modpacks, imtlx's in-game fish encyclopedia add-on.

## Gaps

| # | Gap (seen at) | Result | Root cause |
|---|---|---|---|
| 1 | **The developer's second video** "How Criticism changed Matcha Flavoured" (wavOi0ULYpQ, 2026-08-14). None of the competitors use it either. | **Closed.** Design reasoning added and cited with `{{Cite video\|id=wavOi0ULYpQ…}}` on: Crystal Heart (cheaper to encourage engagement), Death (the "too easy" criticism rejected), Difficulty (added for a frustrated first-time player), Abbey (silver was added after feedback), Bookshelf (a player's idea), Riposte (nearly removed, kept after seeing PvP use), Elegy of Hyacinthus, Prayer of Lu Ban, Mouthpiece (religions pointing to the dead god), Abandoned village (why villages were removed), Hell (darkness kept as taste), Advancements (unexplained on purpose), Matcha Flavoured → Reception (a summary, and regret over rushed patches). Each claim was cross-checked against the 1.10/1.12 release notes where they cover it. | **Source not considered**: the wiki watched only the intro video, not the developer's other official videos. |
| 2 | Mid- and late-game walkthrough (AriesAlex: Hell, End, after the dragon; matchaflavored.org) | **Closed.** Guide for new players, steps 9–12: magic materials and Hell, blessings and warding, the End, after the dragon (Divine Favor loop, Wither, adamant). Cited to recipes and functions. | **Page plan / format**: the guide was scoped to the Tutorial tab; the facts existed only on detail pages. |
| 3 | Advancement names as titles (MFW has around 70 advancement pages) | **Closed.** Row anchors (`<span id>`) on every visible advancement in Advancements, plus 73 redirects (`Brazier` → `Advancements#Brazier`). | **Tooling**: the generator makes redirects for items and vanilla names but not for advancement titles. |
| 4 | Spelling variants and alternate names (MFW: Armour, Jewellery, Divine Favour, Stabilised Estus, Hypothermia, Hearts, Axes/Pickaxes/Shovels/Hoes/Swords, Mattocks, Dolabras, Prayers, Blessings, Cleansing, Clay Fetish (Lament/Rejoice), Echo Fish/Pale Fish = internal model ids, Sundried Tomatoes, Golden Baked Apple) | **Closed.** 25 hand-written redirects. | **Style gap**: STYLE.md mandates American spelling but nothing adds redirects from the pack's own British spelling. **Tooling**: plural and internal-id redirects aren't generated. |
| 5 | Splash texts (JeremyVyska) | **Closed.** New page [[Splash texts]]: all 50, with history from 0.7-alpha, 1.03 and 1.10. | **Extractor**: `extract.py` ignores `MF_resourcepack/assets/minecraft/texts/`. |
| 6 | Tooltip symbol legend (JeremyVyska "Symbols") | **Closed.** New page [[Tooltip]]: stat, intrinsic, effect and advancement symbols. Derived from the lang file and the lore in recipes; several example items were corrected against the source while writing. | **Page plan**: `{{G}}` was used everywhere but no page explained the symbols. |
| 7 | Symptom-based troubleshooting (matchaflavored.org) | **Closed.** Installation → Troubleshooting table. | **Format gap** (how-to/question style). |
| 8 | Complete disabled-vanilla list (JeremyVyska, 356 entries) | **Left for tooling.** Removed features summarizes it in prose. `data.json` already has `blocked_vanilla`; the generator should emit `Template:Data/Blocked vanilla` for Removed features to transclude. | **Tooling** (generator output missing). |
| 9 | Recipe search, reverse lookup, crafting tree (julianfere, peterbax, JeremyVyska) | **Left for tooling.** Suggested: a static `/recipes/` page in `export_static.py` built from `data.json` (search by output or ingredient, click to expand ingredient chains). Pagefind search covers text only. | **Feature gap**: the site is article-only. |
| 10 | Progression-safe spoiler mode (peterbax, Evansch0, JeremyVyska) | **Left for tooling.** We warn with `{{Spoiler}}` only. Possible: tag spoiler sections with a class and add a site-wide "hide spoilers" toggle in the skin script. | **Feature gap**. |
| 11 | Per-file version diff (JeremyVyska, peterbax) | **Rejected as a page**; covered by version pages plus `git diff wiki/generated`. Could publish that diff summary on each version page. | — |
| 12 | Tags, sounds, function lists (JeremyVyska) | **Rejected**: developer-facing and not encyclopedic. | — |
| 13 | "Sleep sometimes doesn't work after the first join until `/reload`" (AriesAlex, citing the Modrinth description) | **Left open.** Not verifiable from the code or release notes; the Modrinth description isn't among our sources. | **Source not considered**: the Modrinth project description (and gallery) isn't fetched. |

## Competitor claims that are wrong or outdated (not added)

- **MFW "Prayer of Mithra"** (Protection III, traded for the Avesta): no such prayer is in the code or lang. The Avesta now gives the Prayer of The God-King (Efficiency II, Unbreaking I). Outdated or wrong.
- **MFW "Wandering Traveller" selling a "refugee application"**: the pack's names are Wandering Trader and Asylum Seeker. Outdated or wrong.
- **MFW "Golden Baked Apple"**: the in-game name is Baked Golden Apple. **"Sundried Tomatotes"** is a typo; its recipe and "Strength II for 5 minutes" were not verified.
- **MFW Hypothermia**: "1 damage every tick". The code applies it every tick, but damage cooldown limits how often it lands (our Freezing water page says so).
- **AriesAlex: smithing overwrites existing enchantments** of the same type. True of 1.03, but fixed in 1.12.1-alpha: the code merges them and keeps the higher level (see Smithing).
- **AriesAlex fork-specific behavior** (for example, re-checking already-spawned mobs after the dragon) describes their fork, not the pack.
- Unverified and left out: AriesAlex's "deepslate iron ore drops 2 raw iron" and "copper cannot mine redstone".
- **MFW "Squid Ink Pasta"**: correct that it was removed in 1.10; we already list it in Removed features.

## Why the gaps existed (summary)

1. **Sources not considered**: only one of the developer's videos; the Modrinth description and gallery; community Discord announcements (in the appendix video the developer asks fans to send a link to an existing community Discord rather than running one).
2. **Extractor coverage**: resource pack `texts/` (splashes), and the font glyphs weren't mapped to meanings.
3. **Generator coverage**: no redirects for advancement titles, plurals, British spellings or internal model ids; no table for `blocked_vanilla`.
4. **Page plan scope**: PAGES.md had no Tooltip or Splash texts page, and the guide stopped at smithing.
5. **Format**: no question- or symptom-shaped content (troubleshooting); no interactive data views.

## Prevention: changes to the daily update loop

1. **Watch every official channel** (the coordinator reports this is now in place for YouTube):
   - Fetch transcripts of new videos on the developer's channel into `sources/transcripts/`, and flag any video not yet cited by `{{Cite video|id=…}}` anywhere in `wiki/pages`.
   - Snapshot the Modrinth project description and gallery captions (`/v2/project/matcha-flavoured`) into `source/modrinth_project.md`, and diff it daily. Treat it as a primary source, like the release notes.
   - The in-repo `README.md`, `my_current_and_future_plans.md` and `changelog.md` are already covered by `git diff $OLD..HEAD`.
2. **Extractor coverage test**: have `extract.py` list every file under `MF_datapack/data/**` and `MF_resourcepack/assets/**` whose directory type it doesn't handle (for example `texts/`, `font/`, `sounds.json`), and fail the check if a new directory type appears. Extract `texts/splashes.txt` and generate `Template:Data/Splashes`, so the Splash texts page can transclude it instead of holding a hand-copied list.
3. **Title coverage check** in `check_site.py`: every advancement title, every `en_us` item name, the plural of every tool type, every `item_model` id (`matcha:echo_fish`) and every British/American variant (`our`/`or`, `ise`/`ize`, `ll`/`l`) must resolve to a page or redirect. Better: generate these redirects in `generate.py`, and generate advancement row anchors, so hand-written redirects aren't needed.
4. **Glyph coverage check**: every private-use character used in `en_us.json` must be named in `Template:G` and appear on the Tooltip page.
5. **Weekly competitor diff step**: pull `matchaflavoured.wiki`'s `allpages` list (API) and the READMEs or feature lists of the repos above. Diff the titles against ours (after lowercasing and resolving redirects), and write new unmatched titles to `build/competitor_gaps.txt` for the agent to triage. Verify only against primary sources; record claims that can't be verified here under "wrong or outdated".
6. **Guide freshness**: when a version adds a progression step (a new structure, boss or material tier), the update agent must check that `Guide for new players` and `Progression` mention it.
