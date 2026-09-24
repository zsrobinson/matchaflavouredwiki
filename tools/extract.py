#!/usr/bin/env python3
"""Extract Matcha Flavoured source data into build/data.json.

Reads the official pack (source/matcha-flavoured) and vanilla 26.x data
(source/vanilla-data, source/vanilla-assets) and normalises everything the
wiki needs: an item registry keyed by English display name, recipes, villager
trades, loot tables, enchantments and advancements.

Every generated wiki fact traces back to a file path recorded here as `src`.

Exits 3 when the source uses a format this file doesn't know (see "format guard" below), or when the
vanilla data is for a different Minecraft version than the pack. --allow-unknown reports and continues.
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'source', 'matcha-flavoured')
DP = os.path.join(SRC, 'MF_datapack', 'data')
RP = os.path.join(SRC, 'MF_resourcepack', 'assets')
VDATA = os.path.join(ROOT, 'source', 'vanilla-data', 'data', 'minecraft')
VASSETS = os.path.join(ROOT, 'source', 'vanilla-assets', 'assets', 'minecraft')
OUT = os.path.join(ROOT, 'build', 'data.json')


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def rel(path):
    return os.path.relpath(path, SRC)


# ---------------------------------------------------------------- format guard
# This file reads specific keys. When the pack or a new Minecraft version changes a file format
# (26.3 renames loot "functions" to "modifier" and "conditions" to "condition"), the new keys would be
# skipped without a word and the wiki would quietly lose drop counts, conditions and item identities.
# So every key, type and function name read below is checked against this list of what the extractor
# knows. Anything new fails the run (exit 3). Handle it, or add it here if it really doesn't matter.
KNOWN = {
    'loot table': {'type', 'pools', 'random_sequence', 'functions'},
    'loot pool': {'rolls', 'bonus_rolls', 'entries', 'conditions', 'functions'},
    'loot entry': {'type', 'name', 'weight', 'quality', 'functions', 'conditions', 'children', 'value', 'expand',
                   ''},  # '': a stray empty key in the pack's redstone_ore.json
    'loot entry type': {'minecraft:item', 'minecraft:loot_table', 'minecraft:empty', 'minecraft:alternatives',
                        'minecraft:group', 'minecraft:sequence', 'minecraft:tag', 'minecraft:dynamic'},
    # functions the wiki doesn't show (enchanting, damage, map decorations) are known and ignored
    'loot function': {'minecraft:set_count', 'minecraft:set_components', 'minecraft:set_name', 'minecraft:set_lore',
                      'minecraft:set_potion', 'minecraft:enchant_with_levels', 'minecraft:enchant_randomly',
                      'minecraft:exploration_map', 'minecraft:set_damage', 'minecraft:set_ominous_bottle_amplifier',
                      'minecraft:set_instrument', 'minecraft:set_contents', 'minecraft:apply_bonus',
                      'minecraft:explosion_decay', 'minecraft:set_enchantments', 'minecraft:limit_count',
                      'minecraft:enchanted_count_increase', 'minecraft:furnace_smelt', 'minecraft:set_stew_effect',
                      'minecraft:copy_components', 'minecraft:copy_state', 'minecraft:filtered', 'minecraft:discard'},
    # loot_enchantments(): what enchant_randomly, enchant_with_levels and set_enchantments give (Enchantment tables)
    'loot enchant function': {'function', 'conditions', 'options', 'levels', 'only_compatible', 'enchantments', 'add',
                              'include_additional_cost_component'},
    # generate.py: cond_notes() turns these into drop-table notes and chances
    'condition': {'minecraft:location_check', 'minecraft:entity_properties', 'minecraft:block_state_property',
                  'minecraft:match_tool', 'minecraft:survives_explosion', 'minecraft:random_chance',
                  'minecraft:any_of', 'minecraft:all_of', 'minecraft:inverted', 'minecraft:table_bonus',
                  'minecraft:killed_by_player', 'minecraft:random_chance_with_enchanted_bonus',
                  'minecraft:damage_source_properties', 'minecraft:reference', 'minecraft:weather_check',
                  'minecraft:time_check', 'minecraft:value_check', 'minecraft:entity_scores'},
    'recipe type': {'minecraft:crafting_shaped', 'minecraft:crafting_shapeless', 'minecraft:smelting',
                    'minecraft:smoking', 'minecraft:blasting', 'minecraft:campfire_cooking',
                    'minecraft:stonecutting', 'minecraft:smithing_transform',
                    # special recipes with no fixed output: not listed on the wiki
                    'minecraft:crafting_dye', 'minecraft:crafting_imbue', 'minecraft:crafting_transmute',
                    'minecraft:crafting_decorated_pot', 'minecraft:smithing_trim',
                    'minecraft:crafting_special_bookcloning', 'minecraft:crafting_special_mapextending',
                    'minecraft:crafting_special_firework_rocket', 'minecraft:crafting_special_shielddecoration',
                    'minecraft:crafting_special_bannerduplicate', 'minecraft:crafting_special_firework_star',
                    'minecraft:crafting_special_firework_star_fade', 'minecraft:crafting_special_repairitem'},
    'recipe': {'type', 'category', 'group', 'result', 'show_notification', 'key', 'pattern', 'ingredients',
               'ingredient', 'cookingtime', 'experience', 'template', 'base', 'addition'},
    'item stack': {'id', 'count', 'components'},
    # summarise_components() keeps these for the infoboxes, tooltips and tables
    'component': {'minecraft:' + c for c in (
        'attribute_modifiers', 'banner_patterns', 'block_state', 'blocks_attacks', 'bundle_contents', 'consumable',
        'custom_data', 'custom_model_data', 'custom_name', 'damage', 'death_protection', 'enchantment_glint_override',
        'enchantments', 'entity_data', 'equippable', 'food', 'instrument', 'item_model', 'item_name',
        'jukebox_playable', 'lore', 'max_damage', 'max_stack_size', 'potion_contents', 'provides_trim_material',
        'rarity', 'repairable', 'stored_enchantments', 'tool', 'tooltip_display', 'unbreakable', 'use_remainder')},
    'villager trade': {'wants', 'additional_wants', 'gives', 'given_item_modifiers', 'max_uses', 'xp',
                       'reputation_discount', 'price_multiplier', 'merchant_predicate'},
    'trade set': {'amount', 'random_sequence', 'trades', 'allow_duplicates'},
    'enchantment': {'description', 'max_level', 'weight', 'anvil_cost', 'slots', 'supported_items', 'primary_items',
                    'exclusive_set', 'effects', 'min_cost', 'max_cost'},
    'advancement': {'parent', 'criteria', 'display', 'requirements', 'rewards', 'sends_telemetry_event'},
    'advancement display': {'title', 'description', 'icon', 'frame', 'hidden', 'announce_to_chat', 'show_toast',
                            'background'},
    'tag': {'values', 'replace'},
    'tag entry': {'id', 'required'},
    # assets/minecraft/texts/ in the resource pack: splashes.txt is one splash per line. The pack
    # replacing another of vanilla's texts (end.txt, postcredits.txt, credits.json) is new content.
    'resource pack text': {'splashes.txt'},
    # mob_predicate(): the matcha:mob_checks predicates that pick which mobs a difficulty changes
    'mob predicate': {'condition', 'entity', 'predicate'},
    'mob predicate test': {'minecraft:entity_type', 'minecraft:flags'},
    'mob predicate flag': {'is_baby'},
}
UNKNOWN = defaultdict(set)  # (kind, key) -> files it was seen in


def expect(kind, keys, src):
    for k in keys:
        if k not in KNOWN[kind]:
            UNKNOWN[(kind, k)].add(src)


def expect_conditions(conds, src):
    for c in conds or []:
        if not isinstance(c, dict) or 'condition' not in c:
            UNKNOWN[('condition', 'without a "condition" key')].add(src)
            continue
        expect('condition', [norm_ns(c['condition'])], src)
        expect_conditions(c.get('terms'), src)
        if c.get('term'):
            expect_conditions([c['term']], src)


def norm_ns(i):
    return i if ':' in i else 'minecraft:' + i


# ---------------------------------------------------------------- language
VANILLA_LANG = load(os.path.join(VASSETS, 'lang', 'en_us.json'))
PACK_LANG = load(os.path.join(RP, 'minecraft', 'lang', 'en_us.json'))
LANG = dict(VANILLA_LANG)
LANG.update(PACK_LANG)

# Private-use glyphs from assets/minecraft/font/default.json (custom_emojis.png).
# Named from the lang keys that use them, so lore renders as readable text.
GLYPHS = {
    '': 'Water', '': 'Warding', '': 'Electrum', '': 'Cooldown',
    '': 'Apotropaic', '': 'Cleanse', '': 'Armor toughness',
    '': 'Step height', '': 'Luck', '': 'Nausea', '': 'Slow falling',
    '': 'Attack speed', '': 'Knockback', '': 'Fire resistance',
    '': 'Night vision', '': 'Invisibility', '': 'Weakness',
    '': 'Weaving', '': 'Glowing', '': 'Infested', '': "Dolphin's Grace",
    '': 'Slowness', '': 'Matcha', '': 'Oozing', '': 'Wind charged',
    '': 'Speed', '': 'Knockback resistance', '': 'Jump boost',
    '': 'Levitation', '': 'Safe fall distance', '': 'Reach',
    '': 'Smelting', '': 'Warping', '': 'Health', '': 'Half heart',
    '': 'Aura', '': 'Mining speed', '': 'Attack damage',
    '': 'Throwable', '': 'Armor', '': 'Poison', '': 'Fortune',
    '': 'Doom', '': 'Doom', '': 'Magic protection',
}


MISSING_LANG = set()


def strip_codes(s):
    return re.sub('§.', '', s)


def glyph_text(s):
    """Replace custom-font glyphs with {{G|name}} markers."""
    out = []
    for ch in s:
        if 0xE000 <= ord(ch) <= 0xF8FF:
            out.append('⟦%s⟧' % GLYPHS.get(ch, 'U+%04X' % ord(ch)))
        else:
            out.append(ch)
    return strip_codes(''.join(out))


def render_text(comp):
    """Render a JSON text component to plain text (glyphs → ⟦name⟧)."""
    if comp is None:
        return ''
    if isinstance(comp, str):
        return glyph_text(comp)
    if isinstance(comp, list):
        return ''.join(render_text(c) for c in comp)
    s = ''
    if 'text' in comp:
        s += comp['text']
    if 'translate' in comp:
        key = comp['translate']
        tpl = LANG.get(key, comp.get('fallback'))
        if tpl is None:
            # untranslated pack key (a bug in the pack's lang file): use a readable form of the id
            tpl = key.split('.')[-1].replace('_', ' ').title() if key.startswith(('item.kleispack.', 'block.kleispack.')) else key
            MISSING_LANG.add(key)
        args = [render_text(w) for w in comp.get('with', [])]
        tpl = tpl.replace('%%', '\x00')
        i = 0

        def sub(m):
            nonlocal i
            if m.group(1):
                idx = int(m.group(1)) - 1
            else:
                idx = i
                i += 1
            return args[idx] if idx < len(args) else ''
        tpl = re.sub(r'%(?:(\d+)\$)?s', sub, tpl).replace('\x00', '%')
        s += tpl
    for e in comp.get('extra', []):
        s += render_text(e)
    return glyph_text(s)


MC_COLORS = {
    'black': '000000', 'dark_blue': '0000AA', 'dark_green': '00AA00', 'dark_aqua': '00AAAA',
    'dark_red': 'AA0000', 'dark_purple': 'AA00AA', 'gold': 'FFAA00', 'gray': 'AAAAAA',
    'dark_gray': '555555', 'blue': '5555FF', 'green': '55FF55', 'aqua': '55FFFF',
    'red': 'FF5555', 'light_purple': 'FF55FF', 'yellow': 'FFFF55', 'white': 'FFFFFF',
}
CODE_COLORS = dict(zip('0123456789abcdef', MC_COLORS.values()))
LORE_STYLE = {'color': 'AA00AA', 'italic': True}  # the game's default for lore lines


def color_hex(c):
    if not isinstance(c, str):
        return None
    if c.startswith('#'):
        return c[1:].upper()
    return MC_COLORS.get(c)


def rich_text(comp, style=None):
    """Render a JSON text component as styled runs for tooltips: [[text, 'RRGGBB' or '', 'i'/'b'
    flags], ...]. Custom-font glyphs stay as their private-use characters; § codes are applied."""
    style = dict(style or {})
    out = []

    def emit(text, st):
        cur, buf, i = dict(st), '', 0
        while i < len(text):
            if text[i] == '§' and i + 1 < len(text):
                code = text[i + 1].lower()
                if buf:
                    out.append((buf, dict(cur)))
                    buf = ''
                if code in CODE_COLORS:
                    cur = {'color': CODE_COLORS[code]}  # a colour code also resets formatting
                elif code == 'o':
                    cur['italic'] = True
                elif code == 'l':
                    cur['bold'] = True
                elif code == 'r':
                    cur = dict(st)
                i += 2
                continue
            buf += text[i]
            i += 1
        if buf:
            out.append((buf, cur))

    def walk(c, st):
        if c is None:
            return
        if isinstance(c, str):
            emit(c, st)
            return
        if isinstance(c, list):
            # a list is a component whose first element is the parent of the rest
            if c:
                first = c[0] if isinstance(c[0], dict) else {'text': str(c[0])}
                walk(dict(first, extra=list(first.get('extra', [])) + list(c[1:])), st)
            return
        st = dict(st)
        if 'color' in c and color_hex(c['color']):
            st['color'] = color_hex(c['color'])
        for k in ('italic', 'bold'):
            if k in c:
                st[k] = bool(c[k])
        if 'text' in c:
            emit(str(c['text']), st)
        if 'translate' in c:
            key = c['translate']
            tpl = LANG.get(key, c.get('fallback'))
            if tpl is None:
                tpl = key.split('.')[-1].replace('_', ' ').title() if key.startswith(('item.kleispack.', 'block.kleispack.')) else key
            args = c.get('with', [])
            n = 0
            for part in re.split(r'(%(?:\d+\$)?s|%%)', tpl):
                if part == '%%':
                    emit('%', st)
                elif part and part.startswith('%') and part.endswith('s'):
                    m = re.match(r'%(\d+)\$s', part)
                    idx = int(m.group(1)) - 1 if m else n
                    n += 0 if m else 1
                    if idx < len(args):
                        walk(args[idx] if not isinstance(args[idx], (int, float)) else str(args[idx]), st)
                elif part:
                    emit(part, st)
        for e in c.get('extra', []):
            walk(e, st)

    walk(comp, style)
    runs = []
    for text, st in out:
        flags = ('i' if st.get('italic') else '') + ('b' if st.get('bold') else '')
        run = [text, st.get('color') or '', flags]
        if runs and runs[-1][1:] == run[1:]:
            runs[-1][0] += text
        else:
            runs.append(run)
    return runs


def ingame_name(item_id):
    """The name the game shows for a (possibly renamed) vanilla item id."""
    iid = item_id.split(':', 1)[-1] if ':' in item_id else item_id
    for k in ('item.minecraft.' + iid, 'block.minecraft.' + iid):
        if k in LANG:
            return strip_codes(LANG[k]).strip()
    return iid.replace('_', ' ').title()


def distinct_names(lang):
    """Page names for vanilla items that share one in-game name with other item ids.

    Every armor trim template and the netherite upgrade are "Smithing Template", and every banner
    pattern is "Banner Pattern". The tooltip line under the name tells them apart (the ".new" lang
    key, e.g. "Flow Armor Trim", "Globe Banner Pattern"); where that line doesn't already say what the
    item is, the shared name is added, as minecraft.wiki names them: "Flow Armor Trim Smithing
    Template". Music discs are named by their song elsewhere (stack_name)."""
    groups = defaultdict(list)
    for f in sorted(os.listdir(os.path.join(VASSETS, 'items'))):
        iid = f[:-5]
        k = next((k for k in ('item.minecraft.' + iid, 'block.minecraft.' + iid) if k in lang), None)
        if k:
            groups[strip_codes(lang[k]).strip()].append(iid)
    out = {}
    for shared, ids in groups.items():
        if len(ids) < 2:
            continue
        for iid in ids:
            desc = lang.get('item.minecraft.%s.new' % iid)
            if iid.startswith('music_disc_') or not desc:
                continue
            desc = strip_codes(desc).strip()
            words = desc.lower().split()
            out[iid] = desc if all(w in words for w in shared.lower().split()) else '%s %s' % (desc, shared)
    return out


DISTINCT = distinct_names(LANG)  # with the pack's lang: the upgrade template is "Smithing Upgrade Template"
DISTINCT_VANILLA = distinct_names(VANILLA_LANG)


def vname(item_id):
    """Wiki name of a (possibly renamed) vanilla item id: its in-game name, or the distinct name
    of an item that shares its in-game name with others."""
    iid = item_id.split(':', 1)[-1] if ':' in item_id else item_id
    return DISTINCT.get(iid) or ingame_name(item_id)


def vanilla_name(item_id):
    iid = item_id.split(':', 1)[-1]
    if iid in DISTINCT_VANILLA:
        return DISTINCT_VANILLA[iid]
    for k in ('item.minecraft.' + iid, 'block.minecraft.' + iid):
        if k in VANILLA_LANG:
            return VANILLA_LANG[k]
    return iid.replace('_', ' ').title()


def norm_id(i):
    return i if ':' in i else 'minecraft:' + i


# ---------------------------------------------------------------- items
ITEMS = {}  # key -> item record
MODEL_OWNER = {}  # item_model -> key of the named (custom) item that uses it


EFFECT_NAMES = {v for k, v in VANILLA_LANG.items() if k.startswith('effect.minecraft.') and k.count('.') == 2}


def stack_name(stack):
    comps = stack.get('components', {}) or {}
    for key in ('minecraft:custom_name', 'minecraft:item_name'):
        if key in comps:
            n = render_text(comps[key]).strip()
            base = norm_id(stack['id']).split(':')[-1]
            if base in ('splash_potion', 'lingering_potion', 'potion') and n in EFFECT_NAMES:
                n = '%s of %s' % (ingame_name(base), n)  # e.g. the Chemist's "Darkness" splash potion
            return n
    sid = norm_id(stack['id']).split(':')[-1]
    if sid.startswith('music_disc_') and not comps:
        song = LANG.get('jukebox_song.minecraft.' + sid[len('music_disc_'):])
        if song:
            return '%s (%s)' % (ingame_name(sid), strip_codes(song).strip())  # vanilla discs all share one name
    pc = comps.get('minecraft:potion_contents')
    if isinstance(pc, dict) and pc.get('custom_name'):
        base = norm_id(stack['id']).split(':')[-1]
        k = 'item.minecraft.%s.effect.%s' % (base, pc['custom_name'])
        if k in LANG:
            return strip_codes(LANG[k]).strip()
    return ingame_name(stack['id'])


def item_key(stack):
    comps = stack.get('components', {}) or {}
    name = stack_name(stack)
    named = comps.get('minecraft:item_name') or comps.get('minecraft:custom_name')
    model = comps.get('minecraft:item_model')
    if not named and model and model in MODEL_OWNER:
        name = MODEL_OWNER[model]  # model-only stack (e.g. a trade asking for an electrum item)
    model = comps.get('minecraft:item_model')
    return name, model


def variant_key(name, comps, sid=None):
    """Items that share one name in-game but are distinct (blessings, clay fetishes, smithing
    templates, banner patterns)."""
    lore = comps.get('minecraft:lore') or []
    named = comps.get('minecraft:item_name') or comps.get('minecraft:custom_name')
    if sid and not named and name == ingame_name(sid) and sid.split(':')[-1] in DISTINCT:
        return DISTINCT[sid.split(':')[-1]]
    if name == 'Blessing' and lore:
        return render_text(lore[0])
    song = comps.get('minecraft:jukebox_playable')
    if name == 'Music Disc' and isinstance(song, str):
        return 'Music Disc (%s)' % song.split(':')[-1].replace('_', ' ').title()
    if name == 'Clay Fetish' and lore:
        return 'Clay Fetish (%s)' % render_text(lore[0])
    return name


def summarise_components(comps):
    s = {}
    if not comps:
        return s
    for k, v in comps.items():
        k2 = k.split(':')[-1]
        if k2 == 'lore':
            s['lore'] = [render_text(x).strip() for x in v]
            s['lore_rich'] = [rich_text(x, LORE_STYLE) for x in v]
        elif k2 in ('item_name', 'custom_name'):
            if isinstance(v, dict) and color_hex(v.get('color')):
                s['name_color'] = color_hex(v['color'])
            continue
        else:
            s[k2] = v
    return s


def register(stack, src, how):
    """Record an item stack definition seen in the source."""
    if not isinstance(stack, dict) or 'id' not in stack:
        return None
    expect('item stack', stack, src)
    sid = norm_id(stack['id'])
    comps = stack.get('components', {}) or {}
    expect('component', (norm_ns(k.lstrip('!')) for k in comps), src)
    name, model = item_key(stack)
    key = variant_key(name, comps, sid)
    rec = ITEMS.get(key)
    if rec is None:
        rec = ITEMS[key] = {
            'name': name, 'base_id': sid, 'models': [], 'vanilla_name': vanilla_name(sid),
            'renamed_vanilla': not comps.get('minecraft:item_name') and not comps.get('minecraft:custom_name'),
            'components': {}, 'sources': [],
        }
    named = comps.get('minecraft:item_name') or comps.get('minecraft:custom_name')
    if model and named and model not in MODEL_OWNER:
        MODEL_OWNER[model] = key
    # only attach a model if this stack is really this item (not a vanilla item wearing another item's model)
    if model and model not in rec['models'] and (named or not rec['models']) and MODEL_OWNER.get(model, key) == key:
        rec['models'].append(model)
    summ = summarise_components(comps)
    # The crafted item defines the item; loot and trade variants (e.g. the Abbey's enchanted iron
    # swords) must not override it. Among equal sources keep the richest component set.
    rank = {'recipe': 3, 'trade': 2, 'loot': 1}.get(how, 0)
    def richness(c):  # tooltip styling keys don't make a definition richer
        return len([k for k in c if k not in ('lore_rich', 'name_color')])
    if rank > rec.get('_rank', -1) or (rank == rec.get('_rank') and richness(summ) > richness(rec['components'])):
        rec['components'] = summ
        rec['_rank'] = rank
    if len(rec['sources']) < 40:
        rec['sources'].append({'how': how, 'src': src})
    return key


# ---------------------------------------------------------------- loot variants
# Some loot functions and components make a distinct in-game item out of one wiki item: a tipped
# arrow's potion, a goat horn's sound, an ominous bottle's level. The wiki keeps one page for the
# item and labels each source with the variant, as the game names it ("Arrow of Poison").
ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X'}


def potion_label(base, potion):
    """In-game name of a potion item (or tipped arrow) holding one vanilla potion id."""
    p, mod = potion.split(':')[-1], ''
    for m in ('long_', 'strong_'):
        if p.startswith(m):
            p, mod = p[len(m):], m[:-1]
    k = 'item.minecraft.%s.effect.%s' % (base, p)
    if k in LANG:
        return strip_codes(LANG[k]).strip() + (' (%s)' % mod if mod else '')
    effect = LANG.get('effect.minecraft.' + p) or p.replace('_', ' ').title()
    return '%s (%s)' % (ingame_name(base), effect + (', ' + mod if mod else ''))


def instrument_names(options):
    """Sound names ("Ponder") of an instrument id, a list of ids or an #instrument tag."""
    ids = []
    for o in ([options] if isinstance(options, str) else options or []):
        if o.startswith('#'):
            ns, p = o[1:].split(':') if ':' in o else ('minecraft', o[1:])
            for f in (os.path.join(DP, ns, 'tags', 'instrument', p + '.json'),
                      os.path.join(VDATA, 'tags', 'instrument', p + '.json') if ns == 'minecraft' else ''):
                if f and os.path.exists(f):
                    ids += [v if isinstance(v, str) else v['id'] for v in load(f)['values']]
                    break
        else:
            ids.append(o)
    return [strip_codes(LANG.get('instrument.minecraft.' + i.split(':')[-1], i.split(':')[-1].replace('_', ' ').title()))
            for i in ids]


def or_list(names):
    return names[0] if len(names) == 1 else '%s or %s' % (', '.join(names[:-1]), names[-1])


def int_range(n):
    if isinstance(n, (int, float)):
        return int(n), int(n)
    if isinstance(n, dict) and isinstance(n.get('min'), (int, float)) and isinstance(n.get('max'), (int, float)):
        return int(n['min']), int(n['max'])
    return None


def stack_variant(stack, functions=()):
    """Label for a stack that is a distinct in-game variant of its wiki item, or None."""
    sid = norm_id(stack['id'])
    base = sid.split(':')[-1]
    comps = stack.get('components') or {}
    name = stack_name(stack)
    inst = comps.get('minecraft:instrument')
    if isinstance(inst, dict) and inst.get('description'):
        return '%s (%s)' % (name, render_text(inst['description']).strip())  # the clay fetishes
    if isinstance(inst, str) and base == 'goat_horn':
        return '%s (%s)' % (name, or_list(instrument_names(inst)))
    for fn in functions:
        f = fn.get('function', '').split(':')[-1]
        if f == 'set_potion' and fn.get('id'):
            return potion_label(base, fn['id'])
        if f == 'set_instrument' and fn.get('options'):
            names = instrument_names(fn['options'])
            if names:
                return '%s (%s)' % (name, or_list(names))
        if f == 'set_ominous_bottle_amplifier':
            r = int_range(fn.get('amplifier'))
            if r:
                lv = [ROMAN.get(a + 1, str(a + 1)) for a in r]
                effect = strip_codes(LANG.get('effect.minecraft.bad_omen', 'Bad Omen'))
                return '%s (%s %s)' % (name, effect, lv[0] if lv[0] == lv[1] else '%s–%s' % tuple(lv))
        if f == 'set_enchantments':
            names = [strip_codes(LANG.get('enchantment.%s.%s' % tuple(norm_id(e).split(':')), norm_id(e).split(':')[-1]))
                     for e in (fn.get('enchantments') or {})]
            if base == 'enchanted_book':
                return '%s (%s)' % (name, ', '.join(names) if names else 'no enchantments')
            return '%s (enchanted)' % name if names else None
        if f in ('enchant_randomly', 'enchant_with_levels'):
            opt = fn.get('options')
            opts = [opt] if isinstance(opt, str) else opt if isinstance(opt, list) else []
            if base == 'enchanted_book' and f == 'enchant_randomly' and opts and len(opts) <= 6 \
                    and not any(o.startswith('#') for o in opts):
                names = [strip_codes(LANG.get('enchantment.%s.%s' % tuple(norm_id(o).split(':')), norm_id(o).split(':')[-1].replace('_', ' ').title()))
                         for o in opts]  # a fixed short list: name it ("Breach or Density")
                return '%s (%s)' % (name, or_list(names))
            return '%s (%s)' % (name, 'random enchantment' if base == 'enchanted_book' else 'enchanted')
    return None


def display_stack(stack):
    if isinstance(stack, str):
        return {'name': vname(stack), 'id': norm_id(stack), 'count': 1}
    comps = stack.get('components') or {}
    d = {'name': variant_key(item_key(stack)[0], comps, stack['id']), 'id': norm_id(stack['id']), 'count': stack.get('count', 1)}
    if comps.get('minecraft:item_model'):
        d['model'] = comps['minecraft:item_model']
    if comps.get('minecraft:stored_enchantments'):
        d['enchantments'] = comps['minecraft:stored_enchantments']
    if comps.get('minecraft:enchantments'):
        d['enchantments'] = comps['minecraft:enchantments']
    if comps.get('minecraft:stored_enchantments') and comps.get('minecraft:lore'):
        d['lore'] = strip_codes(render_text(comps['minecraft:lore'][0])).strip()  # an Ofuda's prayer
    variant = stack_variant(stack)
    if variant:
        d['variant'] = variant
    if comps.get('minecraft:item_model') and comps.get('minecraft:lore'):
        d['_lore'] = render_text(comps['minecraft:lore'][0])  # see lore_variants()
        d['_lore_rich'] = summarise_components(comps).get('lore_rich')
    return d


# ---------------------------------------------------------------- tags
def load_tags(kind, pack=True):
    """Tags of one registry as the game merges them: vanilla's, then the pack's (pack=False: vanilla only)."""
    tags = {}
    for base, ns_root in ((VDATA, 'minecraft'),):
        for f in glob.glob(os.path.join(base, 'tags', kind, '**', '*.json'), recursive=True):
            t = 'minecraft:' + os.path.relpath(f, os.path.join(base, 'tags', kind))[:-5]
            tags[t] = load(f)['values']
    for f in glob.glob(os.path.join(DP, '*', 'tags', kind, '**', '*.json'), recursive=True) if pack else []:
        ns = os.path.relpath(f, DP).split(os.sep)[0]
        t = ns + ':' + os.path.relpath(f, os.path.join(DP, ns, 'tags', kind))[:-5]
        d = load(f)
        expect('tag', d, rel(f))
        for v in d.get('values', []):
            if not isinstance(v, str):
                expect('tag entry', v, rel(f))
        vals = [v if isinstance(v, str) else v['id'] for v in d['values']]
        if d.get('replace') or t not in tags:
            tags[t] = vals
        else:
            tags[t] = tags[t] + vals
    return tags


ITEM_TAGS = load_tags('item')
ENCH_TAGS = load_tags('enchantment')


def resolve(ref, tags, seen=None):
    """Ids a registry reference names: an id, a #tag (expanded) or a list of either, in order, once each."""
    seen = set() if seen is None else seen
    out = []
    for v in ([ref] if isinstance(ref, str) else ref or []):
        v = v if isinstance(v, str) else v['id']
        if v.startswith('#'):
            if v[1:] not in seen:
                seen.add(v[1:])
                out += resolve(tags.get(v[1:], []), tags, seen)
        else:
            out.append(norm_id(v))
    return list(dict.fromkeys(out))


def expand_tag(tag, seen=None):
    seen = seen or set()
    out = []
    for v in ITEM_TAGS.get(tag, []):
        if isinstance(v, dict):
            v = v['id']
        if v.startswith('#'):
            if v[1:] not in seen:
                seen.add(v[1:])
                out += expand_tag(v[1:], seen)
        else:
            out.append(norm_id(v))
    return out


def ingredient(ing):
    """Normalise a recipe ingredient to {'names': [...], 'tag': ...}."""
    if ing is None:
        return None
    if isinstance(ing, list):
        names = []
        for x in ing:
            names += ingredient(x)['names']
        return {'names': names}
    if isinstance(ing, dict):
        if 'item' in ing:
            return {'names': [vname(ing['item'])]}
        if 'tag' in ing:
            ing = '#' + ing['tag']
    if isinstance(ing, str):
        if ing.startswith('#'):
            ids = expand_tag(ing[1:])
            return {'names': [vname(i) for i in ids], 'tag': ing[1:]}
        return {'names': [vname(ing)]}
    return {'names': ['?']}


# ---------------------------------------------------------------- recipes
STATION = {
    'minecraft:crafting_shaped': 'Crafting Table', 'minecraft:crafting_shapeless': 'Crafting Table',
    'minecraft:smelting': 'Oven', 'minecraft:smoking': 'Mud Kiln', 'minecraft:blasting': 'Blast Furnace',
    'minecraft:campfire_cooking': 'Kindling', 'minecraft:stonecutting': 'Stonecutter',
    'minecraft:smithing_transform': 'Smithing Table',
}


def blocked_vanilla_paths():
    mc = load(os.path.join(SRC, 'MF_datapack', 'pack.mcmeta'))
    out = set()
    for b in mc.get('filter', {}).get('block', []):
        if b.get('namespace') == 'minecraft':
            out.add(b['path'])
    return out


BLOCKED = blocked_vanilla_paths()


def is_blocked(path_in_ns):
    for b in BLOCKED:
        if path_in_ns == b or path_in_ns.startswith(b.rstrip('/') + '/'):
            return True
    return False


def parse_recipe(d, src, origin):
    t = d.get('type')
    expect('recipe type', [t], src)
    if t in STATION:
        expect('recipe', d, src)
    r = {'type': t, 'station': STATION.get(t, t), 'src': src, 'origin': origin, 'id': None}
    res = d.get('result')
    if isinstance(res, str):
        res = {'id': res}
    if res is None or (isinstance(res, dict) and 'id' not in res):
        return None  # special recipes (26.3's smithing_trim has an empty result)
    r['output'] = display_stack(res)
    register(res, src, 'recipe')
    if t == 'minecraft:crafting_shaped':
        key = {k: ingredient(v) for k, v in d['key'].items()}
        r['pattern'] = d['pattern']
        r['key'] = key
        grid = []
        for row in d['pattern']:
            grid.append([key[c]['names'] if c != ' ' else None for c in row])
        r['grid'] = grid
    elif t == 'minecraft:crafting_shapeless':
        r['ingredients'] = [ingredient(i) for i in d['ingredients']]
    elif t in ('minecraft:smelting', 'minecraft:smoking', 'minecraft:blasting',
               'minecraft:campfire_cooking'):
        r['input'] = ingredient(d['ingredient'])
        r['cookingtime'] = d.get('cookingtime')
        r['experience'] = d.get('experience')
    elif t == 'minecraft:stonecutting':
        r['input'] = ingredient(d['ingredient'])
    elif t == 'minecraft:smithing_transform':
        r['template'] = ingredient(d.get('template')) if d.get('template') else None
        r['base'] = ingredient(d['base'])
        r['addition'] = ingredient(d['addition'])
    else:
        return None
    return r


RECIPES = []
for f in sorted(glob.glob(os.path.join(DP, '*', 'recipe', '**', '*.json'), recursive=True)):
    ns = os.path.relpath(f, DP).split(os.sep)[0]
    d = load(f)
    r = parse_recipe(d, rel(f), 'pack')
    if r:
        r['id'] = ns + ':' + os.path.relpath(f, os.path.join(DP, ns, 'recipe'))[:-5]
        r['folder'] = os.path.dirname(os.path.relpath(f, os.path.join(DP, ns, 'recipe')))
        RECIPES.append(r)

VANILLA_RECIPES_KEPT = []
for f in sorted(glob.glob(os.path.join(VDATA, 'recipe', '*.json'))):
    name = os.path.basename(f)
    if is_blocked('recipe/' + name):
        continue
    d = load(f)
    r = parse_recipe(d, 'vanilla:recipe/' + name, 'vanilla')
    if r:
        r['id'] = 'minecraft:' + name[:-5]
        VANILLA_RECIPES_KEPT.append(r)

BLOCKED_RECIPES = sorted(b[len('recipe/'):-5] for b in BLOCKED if b.startswith('recipe/'))

# The vanilla recipes the filter hides, for the Removed features list (generate.py: Data/Blocked vanilla).
# Only what the list shows is read: nothing here registers an item source, since the recipes don't exist.
BLOCKED_RECIPE_INFO = []
for f in sorted(glob.glob(os.path.join(VDATA, 'recipe', '*.json'))):
    name = os.path.basename(f)
    if not is_blocked('recipe/' + name):
        continue
    d = load(f)
    res = d.get('result')
    BLOCKED_RECIPE_INFO.append({
        'id': 'minecraft:' + name[:-5], 'type': norm_id(d.get('type', '')), 'category': d.get('category', 'misc'),
        'output': display_stack(res) if res and (isinstance(res, str) or 'id' in res) else None})
# The vanilla advancement folders it hides, with how many advancements each held.
BLOCKED_ADVANCEMENTS = {b[len('advancement/'):]: len(glob.glob(os.path.join(VDATA, b, '**', '*.json'), recursive=True))
                        for b in sorted(BLOCKED) if b.startswith('advancement/')}

# ---------------------------------------------------------------- loot tables
def pool_count(pool_fns):
    """The count a pool's own set_count gives every stack it yields (pool functions run after the
    entry's, so it replaces the entry's count), or None."""
    for fn in pool_fns:
        if fn.get('function', '').split(':')[-1] == 'set_count' and not fn.get('add'):
            return fn.get('count')
    return None


def loot_enchantments(ent, comps, fns, src):
    """What a loot entry enchants its stack with (generate.py: the Enchantment tables): the fixed
    enchantments it sets ('enchantments'), or the ids a random enchanting function picks from
    ('enchant_options', with 'enchant_from' the #tag or list the table names)."""
    fixed = dict(comps.get('minecraft:stored_enchantments') or comps.get('minecraft:enchantments') or {})
    for fn in fns:
        f = fn.get('function', '').split(':')[-1]
        if f not in ('enchant_randomly', 'enchant_with_levels', 'set_enchantments'):
            continue
        expect('loot enchant function', fn, src)
        if f == 'set_enchantments':
            if not fn.get('add'):
                fixed = {}
            for k, v in (fn.get('enchantments') or {}).items():
                if isinstance(v, (int, float)):
                    fixed[norm_id(k)] = fixed.get(norm_id(k), 0) + int(v)
        elif fn.get('options') is not None:
            ent['enchant_from'] = fn['options']
            ent['enchant_options'] = resolve(fn['options'], ENCH_TAGS)
        else:
            ent['enchant_from'] = 'any'  # no options: every enchantment that fits the item
    if fixed:
        ent['enchantments'] = {norm_id(k): v for k, v in fixed.items() if v > 0}


def walk_entries(entries, pool_ctx, out, src, pool_fns=()):
    for e in entries:
        expect('loot entry', e, src)
        expect('loot entry type', [norm_ns(e.get('type', ''))], src)
        expect('loot function', (norm_ns(fn.get('function', '')) for fn in e.get('functions', [])), src)
        for fn in e.get('functions', []):
            expect_conditions(fn.get('conditions'), src)
        expect_conditions(e.get('conditions'), src)
        t = e.get('type', '').split(':')[-1]
        if t == 'item':
            stack = {'id': e['name'], 'components': {}}
            count = None
            for fn in e.get('functions', []):
                fname = fn.get('function', '').split(':')[-1]
                if fname == 'set_components':
                    stack['components'].update(fn.get('components', {}))
                elif fname == 'set_name':
                    stack['components']['minecraft:item_name' if fn.get('target') == 'item_name' else 'minecraft:custom_name'] = fn.get('name')
                elif fname == 'set_count':
                    count = fn.get('count')
                elif fname == 'set_lore':
                    stack['components']['minecraft:lore'] = fn.get('lore')
            if pool_count(pool_fns) is not None:
                count = pool_count(pool_fns)
            fns = e.get('functions', []) + list(pool_fns)  # pool functions apply to every entry
            fnames = {fn.get('function', '').split(':')[-1] for fn in fns}
            if fnames & {'enchant_randomly', 'enchant_with_levels', 'set_enchantments'} and norm_id(stack['id']) == 'minecraft:book':
                stack['id'] = 'minecraft:enchanted_book'  # enchanting a book turns it into an enchanted book
            if 'exploration_map' in fnames and norm_id(stack['id']) == 'minecraft:map':
                stack['id'] = 'minecraft:filled_map'  # the function turns an empty map into a filled explorer map
            key = register(stack, src, 'loot')
            ent = {'item': key, 'id': norm_id(stack['id']), 'weight': e.get('weight', 1),
                   'quality': e.get('quality'), 'count': count,
                   'conditions': e.get('conditions'), 'functions': [f.get('function') for f in e.get('functions', [])],
                   **pool_ctx}
            variant = stack_variant(stack, fns)
            if variant:
                ent['variant'] = variant
            comps = stack['components']
            if comps.get('minecraft:item_model'):
                ent['model'] = comps['minecraft:item_model']
            if comps.get('minecraft:item_model') and comps.get('minecraft:lore'):
                ent['_lore'] = render_text(comps['minecraft:lore'][0])  # see lore_variants()
                ent['_lore_rich'] = summarise_components(comps).get('lore_rich')
            if comps.get('minecraft:enchantments'):
                ent['_ench'] = comps['minecraft:enchantments']  # see enchanted_variants()
            loot_enchantments(ent, comps, fns, src)
            out.append(ent)
        elif t == 'loot_table':
            # set_count on a loot_table entry applies to every stack the nested table yields
            count = next((fn.get('count') for fn in e.get('functions', [])
                          if fn.get('function', '').split(':')[-1] == 'set_count' and not fn.get('add')), None)
            if pool_count(pool_fns) is not None:
                count = pool_count(pool_fns)  # e.g. the sweet berry bush: 2-3 berries from matcha:food/sweet_berries
            out.append({'loot_table': e.get('value') if isinstance(e.get('value'), str) else e.get('name'),
                        'count': count, 'weight': e.get('weight', 1), 'quality': e.get('quality'),
                        'conditions': e.get('conditions'), **pool_ctx})
        elif t in ('alternatives', 'group', 'sequence'):
            # the children share the parent's single weighted slot in the pool (an alternatives entry
            # gives only its first child whose conditions pass, e.g. Silk Touch or else the normal drop)
            start = len(out)
            walk_entries(e.get('children', []), pool_ctx, out, src, pool_fns)
            slot = '%s/%d' % (pool_ctx.get('pool'), start)
            for child in out[start:]:  # nested alternatives flatten into the outer slot, in order
                child['slot'], child['slot_kind'], child['weight'] = slot, t, e.get('weight', 1)
                if e.get('conditions'):
                    child['conditions'] = (e.get('conditions') or []) + (child.get('conditions') or [])
        elif t == 'tag':
            out.append({'tag': e.get('name'), 'weight': e.get('weight', 1), 'conditions': e.get('conditions'), **pool_ctx})
        elif t == 'empty':
            out.append({'empty': True, 'weight': e.get('weight', 1), 'conditions': e.get('conditions'), **pool_ctx})


def parse_loot(d, src):
    out = []
    expect('loot table', d, src)
    expect('loot function', (norm_ns(fn.get('function', '')) for fn in d.get('functions', [])), src)
    for i, p in enumerate(d.get('pools', [])):
        expect('loot pool', p, src)
        expect('loot function', (norm_ns(fn.get('function', '')) for fn in p.get('functions', [])), src)
        expect_conditions(p.get('conditions'), src)
        ents = p.get('entries', [])
        total = sum(e.get('weight', 1) for e in ents)
        ctx = {'pool': i, 'rolls': p.get('rolls', 1), 'bonus_rolls': p.get('bonus_rolls', 0),
               'pool_total_weight': total, 'pool_conditions': p.get('conditions')}
        walk_entries(ents, ctx, out, src, p.get('functions') or ())
    return out


LOOT = {}
for f in sorted(glob.glob(os.path.join(DP, '*', 'loot_table', '**', '*.json'), recursive=True)):
    ns = os.path.relpath(f, DP).split(os.sep)[0]
    lid = ns + ':' + os.path.relpath(f, os.path.join(DP, ns, 'loot_table'))[:-5]
    d = load(f)
    LOOT[lid] = {'id': lid, 'src': rel(f), 'type': d.get('type'), 'entries': parse_loot(d, rel(f)),
                 'overrides_vanilla': ns == 'minecraft' and os.path.exists(
                     os.path.join(VDATA, 'loot_table', os.path.relpath(f, os.path.join(DP, ns, 'loot_table'))))}
    base = lid.rsplit('/', 1)[-1]
    if lid.startswith('matcha:food/') and os.path.exists(os.path.join(VASSETS, 'items', base + '.json')):
        # the pack's stand-in for a vanilla food, built on another item (the enchanted golden apple
        # is a golden apple with stronger effects): same name in-game, so label it
        for e in LOOT[lid]['entries']:
            if e.get('item') and e['id'] != 'minecraft:' + base and not e.get('variant'):
                e['variant'] = '%s (replaces %s)' % (ITEMS[e['item']]['name'], vanilla_name(base))

# vanilla loot tables the pack leaves alone still produce renamed items (glowstone -> Estus Ash)
for f in sorted(glob.glob(os.path.join(VDATA, 'loot_table', '**', '*.json'), recursive=True)):
    rp = os.path.relpath(f, os.path.join(VDATA, 'loot_table'))[:-5]
    lid = 'minecraft:' + rp
    if lid in LOOT or not rp.startswith(('entities/', 'blocks/', 'chests/', 'gameplay/', 'archaeology/', 'shearing/')):
        continue
    LOOT[lid] = {'id': lid, 'src': 'vanilla:loot_table/' + rp + '.json', 'type': None, 'vanilla': True,
                 'entries': parse_loot(load(f), 'vanilla:loot_table/' + rp + '.json'), 'overrides_vanilla': False}

# ---------------------------------------------------------------- trades
TRADES = defaultdict(lambda: defaultdict(list))
PROF_NAME = {}
for f in sorted(glob.glob(os.path.join(DP, 'minecraft', 'trade_set', '*', '*.json'))):
    prof = os.path.basename(os.path.dirname(f))
    level = os.path.basename(f)[:-5]
    d = load(f)
    expect('trade set', d, rel(f))
    tag = d.get('trades', '')
    ids = []
    if isinstance(tag, str) and tag.startswith('#'):
        ns, p = tag[1:].split(':')
        tf = os.path.join(DP, ns, 'tags', 'villager_trade', p + '.json')
        if os.path.exists(tf):
            ids = load(tf)['values']
    elif isinstance(tag, list):
        ids = tag
    for tid in ids:
        ns, p = tid.split(':')
        tfile = os.path.join(DP, ns, 'villager_trade', p + '.json')
        if not os.path.exists(tfile):
            continue
        t = load(tfile)
        expect('villager trade', t, rel(tfile))
        mods = t.get('given_item_modifiers') or []
        expect('loot function', (norm_ns(m.get('function', '')) for m in mods), rel(tfile))
        expect_conditions([t['merchant_predicate']] if t.get('merchant_predicate') else [], rel(tfile))
        if any(m.get('function', '').split(':')[-1] == 'discard' for m in mods):
            continue  # placeholder trade the game throws away (levels with no real trades)
        for m in mods:
            if m.get('function', '').split(':')[-1] == 'exploration_map' and 'gives' in t and norm_id(t['gives'].get('id', '')) == 'minecraft:map':
                t['gives']['id'] = 'minecraft:filled_map'  # an explorer map is a filled map in-game
            if m.get('function', '').split(':')[-1] == 'set_name' and 'gives' in t:
                t['gives'].setdefault('components', {})['minecraft:item_name' if m.get('target') == 'item_name' else 'minecraft:custom_name'] = m.get('name')
        biome = None
        mp = t.get('merchant_predicate') or {}
        if mp.get('condition', '').endswith('location_check'):
            biome = (mp.get('predicate') or {}).get('biomes')
        for k in ('wants', 'gives', 'additional_wants'):
            if k in t:
                register(t[k], rel(tfile), 'trade')
        TRADES[prof][level].append({
            'id': tid, 'src': rel(tfile), 'amount_offered': d.get('amount'),
            'wants': display_stack(t['wants']) if 'wants' in t else None,
            'additional_wants': display_stack(t['additional_wants']) if 'additional_wants' in t else None,
            'gives': display_stack(t['gives']) if 'gives' in t else None,
            'max_uses': t.get('max_uses'), 'xp': t.get('xp'),
            'price_multiplier': t.get('price_multiplier'), 'reputation_discount': t.get('reputation_discount'),
            'biome': biome,
        })
    TRADES[prof][level + '_meta'] = {'amount': d.get('amount'), 'src': rel(f)}
    PROF_NAME[prof] = strip_codes(LANG.get('entity.minecraft.villager.' + prof, prof.replace('_', ' ').title()))

# ---------------------------------------------------------------- enchantments
ENCH = {}
for f in sorted(glob.glob(os.path.join(DP, '*', 'enchantment', '*.json'))):
    ns = os.path.relpath(f, DP).split(os.sep)[0]
    eid = ns + ':' + os.path.basename(f)[:-5]
    d = load(f)
    expect('enchantment', d, rel(f))
    van = os.path.join(VDATA, 'enchantment', os.path.basename(f))
    ENCH[eid] = {'id': eid, 'src': rel(f), 'name': render_text(d.get('description')),
                 'max_level': d.get('max_level'), 'weight': d.get('weight'), 'anvil_cost': d.get('anvil_cost'),
                 'slots': d.get('slots'), 'supported_items': d.get('supported_items'),
                 'primary_items': d.get('primary_items'), 'exclusive_set': d.get('exclusive_set'),
                 'effects': d.get('effects'), 'data': d,
                 'vanilla': load(van) if ns == 'minecraft' and os.path.exists(van) else None}


def enchantment_relations():
    """What each enchantment applies to and can't be combined with, in the pack and in vanilla, with
    the tags expanded (the pack changes tags as well as enchantment files: Looting's item tag gains
    shears, the mining exclusive set gains the electrum tool intrinsic). Two enchantments conflict when
    either one's exclusive set holds the other, as the game checks it. Also records which id the
    pack's update item modifiers turn an old enchantment into ('updated_to': main:reach -> matcha:reach)."""
    vitem, vench = load_tags('item', pack=False), load_tags('enchantment', pack=False)
    vdefs = {'minecraft:' + os.path.basename(f)[:-5]: load(f) for f in glob.glob(os.path.join(VDATA, 'enchantment', '*.json'))}
    pack = dict(vdefs, **{k: e['data'] for k, e in ENCH.items()})

    def incompatible(defs, tags):
        excl = {k: set(resolve(d.get('exclusive_set'), tags)) for k, d in defs.items()}
        return {k: sorted(o for o in defs if o != k and (o in excl[k] or k in excl[o])) for k in defs}
    now, before = incompatible(pack, ENCH_TAGS), incompatible(vdefs, vench)
    for k, e in ENCH.items():
        e['items'] = resolve(e['supported_items'], ITEM_TAGS)
        e['incompatible'] = now[k]
        if e['vanilla']:
            e['vanilla_items'] = resolve(e['vanilla'].get('supported_items'), vitem)
            e['vanilla_incompatible'] = before.get(k, [])
    for f in glob.glob(os.path.join(DP, '*', 'item_modifier', '**', '*.json'), recursive=True):
        def walk(x):
            if isinstance(x, list):
                for y in x:
                    walk(y)
            elif isinstance(x, dict):
                if x.get('function', '').split(':')[-1] == 'set_enchantments' and x.get('add'):
                    ench = {norm_id(k): v for k, v in (x.get('enchantments') or {}).items()}
                    old = [k for k, v in ench.items() if v == -1]
                    new = [k for k, v in ench.items() if v == 1]
                    if len(old) == 1 and len(new) == 1 and old[0] in ENCH:
                        ENCH[old[0]]['updated_to'] = new[0]
                        ENCH[old[0]]['update_src'] = rel(f)
                for y in x.values():
                    walk(y)
        walk(load(f))


enchantment_relations()

# ---------------------------------------------------------------- advancements
ADV = {}
for f in sorted(glob.glob(os.path.join(DP, '*', 'advancement', '**', '*.json'), recursive=True)):
    ns = os.path.relpath(f, DP).split(os.sep)[0]
    aid = ns + ':' + os.path.relpath(f, os.path.join(DP, ns, 'advancement'))[:-5]
    d = load(f)
    expect('advancement', d, rel(f))
    expect('advancement display', d.get('display') or {}, rel(f))
    disp = d.get('display')
    rec = {'id': aid, 'src': rel(f), 'parent': d.get('parent'), 'criteria': list(d.get('criteria', {}).keys()),
           'criteria_raw': d.get('criteria'), 'rewards': d.get('rewards'), 'requirements': d.get('requirements')}
    if disp:
        icon = disp.get('icon', {})
        # icons are display-only: don't register them (they would add foreign models to items)
        rec.update({'title': render_text(disp.get('title')).strip(), 'description': render_text(disp.get('description')).strip(),
                    'frame': disp.get('frame', 'task'), 'hidden': disp.get('hidden', False),
                    'show_toast': disp.get('show_toast', True), 'announce': disp.get('announce_to_chat', True),
                    'icon': display_stack(icon) if icon else None, 'background': disp.get('background')})
    ADV[aid] = rec

# ---------------------------------------------------------------- functions: /give and /loot item stacks
GIVE_RE = re.compile(r'\b(?:give\s+\S+|item\s+replace\s+\S+\s+\S+\s+\S+\s+with)\s+([a-z0-9_:.]+)(\[[^\n]*\])?')
FUNCTIONS = {}
for f in sorted(glob.glob(os.path.join(DP, '*', 'function', '**', '*.mcfunction'), recursive=True)):
    ns = os.path.relpath(f, DP).split(os.sep)[0]
    fid = ns + ':' + os.path.relpath(f, os.path.join(DP, ns, 'function'))[:-11]
    with open(f, encoding='utf-8', errors='replace') as fh:
        FUNCTIONS[fid] = {'src': rel(f), 'lines': sum(1 for _ in fh)}

# ---------------------------------------------------------------- functions: difficulty and equipment timers
# mcfunction has no schema, so these parsers accept only the exact command shapes listed below. Any other
# command in the files they read goes to the format guard (UNKNOWN) instead of being skipped.
def fn_file(fid):
    ns, p = fid.split(':', 1)
    return os.path.join(DP, ns, 'function', p + '.mcfunction')


def fn_commands(fid):
    """A function's commands, without blank lines and comments."""
    with open(fn_file(fid), encoding='utf-8') as fh:
        return [s for s in (raw.strip() for raw in fh) if s and not s.startswith('#')]


def unknown_command(kind, fid, line):
    UNKNOWN[(kind, line if len(line) <= 90 else line[:87] + '...')].add(rel(fn_file(fid)))


def num(s):
    x = float(s)
    return int(x) if x == int(x) else x


ENTITY_TAGS = load_tags('entity_type')


def expand_entity_tag(tag, seen=()):
    out = []
    for v in ENTITY_TAGS.get(tag, []):
        v = v['id'] if isinstance(v, dict) else v
        if v.startswith('#'):
            if v[1:] not in seen:
                out += expand_entity_tag(v[1:], seen + (v[1:],))
        else:
            out.append(norm_ns(v))
    return out


def mob_predicate(pid):
    """A matcha:mob_checks predicate: the entity types it matches and whether it tests for babies."""
    ns, p = pid.split(':', 1)
    path = os.path.join(DP, ns, 'predicate', p + '.json')
    d, src = load(path), rel(path)
    expect('mob predicate', d.keys(), src)
    if d.get('condition') != 'minecraft:entity_properties' or d.get('entity') != 'this':
        UNKNOWN[('mob predicate', '%s on %s' % (d.get('condition'), d.get('entity')))].add(src)
    test = d.get('predicate', {})
    expect('mob predicate test', test.keys(), src)
    out = {'src': src}
    t = test.get('minecraft:entity_type')
    if isinstance(t, str):
        out['entity_type'] = t
        out['entities'] = expand_entity_tag(t[1:]) if t.startswith('#') else [norm_ns(t)]
    elif t is not None:
        UNKNOWN[('mob predicate', 'entity_type that is not one ID or tag')].add(src)
    if 'minecraft:flags' in test:
        expect('mob predicate flag', test['minecraft:flags'].keys(), src)
        out['baby'] = test['minecraft:flags'].get('is_baby')
    return out


# The changes a modify_<mob> function makes to the mob it runs as.
MOB_COMMANDS = [
    ('attribute', re.compile(r'attribute @s (minecraft:[a-z_]+) base set (-?[\d.]+)$')),
    ('health', re.compile(r'data merge entity @s \{Health:([\d.]+)f?\}$')),
    ('effect', re.compile(r'effect give @s (minecraft:[a-z_]+) (infinite|\d+) (\d+) (true|false)$')),
    ('mainhand', re.compile(r'data merge entity @s \{equipment:\{mainhand:\{id:"(minecraft:[a-z_]+)",count:1,components:'
                            r'\{"minecraft:enchantments":\{((?:"minecraft:[a-z_]+":\d+,?)*)\}\}\}\},'
                            r'drop_chances:\{mainhand:([\d.]+)f?\}\}$')),
    # clear_drop_chances.mcfunction targets the nearest mundane hostile (@n), not the mob being checked
    ('drop_chances', re.compile(r'data merge entity (@s|@n\[type=#matcha:mundane_hostiles\]) '
                                r'\{drop_chances:\{((?:[a-z]+:[\d.]+f?,?)+)\}\}$')),
]


def mob_changes(fid):
    out = []
    for line in fn_commands(fid):
        m = kind = None
        for kind, rx in MOB_COMMANDS:
            m = rx.match(line)
            if m:
                break
        if not m:
            unknown_command('mob modification', fid, line)
            continue
        if kind == 'attribute':
            out.append({'kind': kind, 'attribute': m[1], 'value': num(m[2])})
        elif kind == 'health':
            out.append({'kind': kind, 'value': num(m[1])})
        elif kind == 'effect':
            out.append({'kind': kind, 'effect': m[1], 'seconds': None if m[2] == 'infinite' else int(m[2]),
                        'amplifier': int(m[3]), 'hide_particles': m[4] == 'true'})
        elif kind == 'mainhand':
            ench = {e: int(lvl) for e, lvl in re.findall(r'"(minecraft:[a-z_]+)":(\d+)', m[2])}
            out.append({'kind': kind, 'item': m[1], 'enchantments': ench, 'drop_chance': num(m[3])})
        else:
            chances = {k: num(v.rstrip('f')) for k, v in (kv.split(':') for kv in m[2].split(','))}
            out.append({'kind': kind, 'target': 'self' if m[1] == '@s' else 'nearest mundane hostile',
                        'drop_chances': chances})
    return out


SPAWN_FN = 'matcha:mechanics/spawn_mechanic/'
SPAWN_DIR = os.path.join(DP, 'matcha', 'function', 'mechanics', 'spawn_mechanic')
DIFFICULTY_RE = re.compile(r'execute if score current_world_settings_difficulty difficulty_score matches ([123]) '
                           r'run function ([a-z0-9_:/]+)$')
RULE_RE = re.compile(r'execute as @s((?: (?:if|unless) predicate [a-z0-9_:/]+)+) run function ([a-z0-9_:/]+)$')


def mob_modifications():
    """How mobs are changed when they spawn, per difficulty: modify_mob picks a check_type function by the
    difficulty (1 easy, 2 normal, 3 hard, read with /difficulty when the pack loads), and its lines apply
    modify_<mob> functions to the mobs that match their predicates, in order."""
    out = {'difficulties': {}, 'predicates': {}, 'functions': {}}
    ticking = SPAWN_FN + 'ticking'
    checked = set(re.findall(r'@e\[type=#([a-z0-9_:/]+),tag=!SpawnChecked\]', ' '.join(fn_commands(ticking))))
    if len(checked) != 1:
        unknown_command('spawn check', ticking, 'not exactly one entity tag checked on spawn: %s' % sorted(checked))
    out['checked_tag'] = next(iter(sorted(checked)), None)
    out['checked_entities'] = expand_entity_tag(out['checked_tag']) if checked else []
    for line in fn_commands(SPAWN_FN + 'modify_mob'):
        m = DIFFICULTY_RE.match(line)
        if not m:
            unknown_command('mob modification', SPAWN_FN + 'modify_mob', line)
            continue
        name = {'1': 'easy', '2': 'normal', '3': 'hard'}[m[1]]
        rules = []
        for rline in fn_commands(m[2]):
            r = RULE_RE.match(rline)
            if not r:
                unknown_command('mob modification', m[2], rline)
                continue
            conds = re.findall(r'(if|unless) predicate ([a-z0-9_:/]+)', r[1])
            for _, pid in conds:
                if pid not in out['predicates']:
                    out['predicates'][pid] = mob_predicate(pid)
            rules.append({'if': [p for k, p in conds if k == 'if'], 'unless': [p for k, p in conds if k == 'unless'],
                          'function': r[2]})
        out['difficulties'][name] = {'function': m[2], 'src': rel(fn_file(m[2])), 'rules': rules}
    # every function in the difficulty folders is read, including ones no check_type calls
    fids = {r['function'] for d in out['difficulties'].values() for r in d['rules']}
    for f in glob.glob(os.path.join(SPAWN_DIR, '*_modifications', '*.mcfunction')):
        fid = SPAWN_FN + os.path.relpath(f, SPAWN_DIR)[:-len('.mcfunction')].replace(os.sep, '/')
        if not fid.endswith('/check_type'):
            fids.add(fid)
    for fid in sorted(fids):
        out['functions'][fid] = {'src': rel(fn_file(fid)), 'changes': mob_changes(fid),
                                 'used_on': [d for d, v in out['difficulties'].items()
                                             if any(r['function'] == fid for r in v['rules'])]}
    return out


STOPWATCH_RE = re.compile(r'execute if stopwatch (minecraft:[a-z0-9_.]+) ([\d.]+)\.\. run function ([a-z0-9_:/]+)$')
RESET_RE = re.compile(r'scoreboard players set @a ([A-Za-z0-9_]+) 0$')
RESTART_RE = re.compile(r'stopwatch restart (minecraft:[a-z0-9_.]+)$')
CALL_RE = re.compile(r'function ([a-z0-9_:/]+)$')
SCORE_EFFECT_RE = re.compile(r'execute as @a\[scores=\{([A-Za-z0-9_]+)=(\d+)\}\] at @s run effect give @s '
                             r'(minecraft:[a-z_]+) (\d+) (\d+) (true|false)$')
SCORE_CALL_RE = re.compile(r'execute as @a\[scores=\{([A-Za-z0-9_]+)=(\d+)\}\] at @s run function ([a-z0-9_:/]+)$')


def equipment_timers():
    """Effects that equipment gives on a timer (set bonuses, shakudo regeneration). Worn pieces add to
    per-player scores that stopwatches.mcfunction resets every tick; each stopwatch runs its timer
    function every so many seconds, which gives an effect to players with a given score. Commands in the
    timer functions that name one of those scores must have one of the shapes below."""
    root = 'matcha:stopwatches'
    lines = fn_commands(root)
    scores = [RESET_RE.match(l)[1] for l in lines if RESET_RE.match(l)]
    effects, calls = [], []

    def walk(fid, sw, every, restarted, seen):
        if fid in seen:
            return
        seen.add(fid)
        for line in fn_commands(fid):
            m = RESTART_RE.match(line)
            if m:
                if m[1] != sw:
                    unknown_command('timer', fid, line)
                restarted.append(fid)
                continue
            m = CALL_RE.match(line)
            if m:
                walk(m[1], sw, every, restarted, seen)
                continue
            m = SCORE_EFFECT_RE.match(line)
            if m and m[1] in scores:
                effects.append({'score': m[1], 'value': int(m[2]), 'effect': m[3], 'seconds': int(m[4]),
                                'amplifier': int(m[5]), 'hide_particles': m[6] == 'true', 'every': every,
                                'stopwatch': sw, 'src': rel(fn_file(fid))})
                continue
            m = SCORE_CALL_RE.match(line)
            if m and m[1] in scores:
                calls.append({'score': m[1], 'value': int(m[2]), 'function': m[3], 'every': every,
                              'stopwatch': sw, 'src': rel(fn_file(fid))})
                continue
            if any(re.search(r'\b%s\b' % s, line) for s in scores):
                unknown_command('timer', fid, line)
            # other timer work (particles, warding) doesn't involve the equipment scores

    for line in lines:
        m = STOPWATCH_RE.match(line)
        if m:
            restarted = []
            walk(m[3], m[1], num(m[2]), restarted, set())
            if not restarted:
                unknown_command('timer', m[3], 'stopwatch %s is never restarted' % m[1])
        elif not RESET_RE.match(line):
            unknown_command('timer', root, line)
    return {'scores': scores, 'effects': effects, 'functions': calls, 'src': rel(fn_file(root))}


MOB_MODIFICATIONS = mob_modifications()
EQUIPMENT_TIMERS = equipment_timers()

# ---------------------------------------------------------------- textures (item model -> png)
def resolve_item_model(model_ref):
    """matcha:foo -> path of an item definition json in the resource pack or vanilla."""
    ns, p = model_ref.split(':') if ':' in model_ref else ('minecraft', model_ref)
    for base in (os.path.join(RP, ns, 'items', p + '.json'), os.path.join(VASSETS, 'items', p + '.json') if ns == 'minecraft' else ''):
        if base and os.path.exists(base):
            return base
    return None


def first_model(node):
    if isinstance(node, dict):
        t = node.get('type', '')
        if t.endswith('model') and 'model' in node and isinstance(node['model'], str):
            return node['model']
        if t.endswith('special') and isinstance(node.get('base'), str):
            return node['base']  # entity-rendered item: use its base model's particle texture
        if t.endswith('select') and node.get('property', '').endswith('display_context'):
            for case in node.get('cases', []):
                when = case.get('when')
                when = when if isinstance(when, list) else [when]
                if 'gui' in when:
                    m = first_model(case.get('model'))
                    if m:
                        return m
            if node.get('fallback'):
                return first_model(node['fallback'])
        for k in ('fallback', 'model', 'on_false', 'on_true', 'cases', 'entries'):
            if k in node:
                m = first_model(node[k])
                if m:
                    return m
        for v in node.values():
            m = first_model(v)
            if m:
                return m
    elif isinstance(node, list):
        for v in node:
            m = first_model(v)
            if m:
                return m
    return None


def gui_node(node):
    """The node of an item definition that the game draws in the inventory: the `gui` case of a
    display_context select, otherwise the default branch (as first_model). Returns a `model`,
    `special` or `composite` node, which tools/images.py renders."""
    if not isinstance(node, dict):
        return None
    t = node.get('type', '').replace('minecraft:', '')
    if t in ('model', 'special'):
        return node
    if t == 'composite':
        return dict(node, models=[m for m in (gui_node(x) for x in node.get('models', [])) if m])
    if t == 'select' and node.get('property', '').endswith('display_context'):
        for case in node.get('cases', []):
            when = case.get('when')
            if 'gui' in (when if isinstance(when, list) else [when]):
                return gui_node(case.get('model'))
    for k in ('fallback', 'on_false', 'on_true'):
        m = gui_node(node.get(k))
        if m:
            return m
    for k in ('cases', 'entries'):
        for case in node.get(k, []):
            m = gui_node(case.get('model'))
            if m:
                return m
    return None


def model_textures(model_ref, depth=0):
    ns, p = model_ref.split(':') if ':' in model_ref else ('minecraft', model_ref)
    for base in (os.path.join(RP, ns, 'models', p + '.json'), os.path.join(VASSETS, 'models', p + '.json') if ns == 'minecraft' else ''):
        if base and os.path.exists(base):
            d = load(base)
            tex = {k: (v.get('sprite') if isinstance(v, dict) else v) for k, v in d.get('textures', {}).items()}
            tex = {k: v for k, v in tex.items() if isinstance(v, str)}
            if 'parent' in d and depth < 8:
                parent_tex, parent = model_textures(d['parent'], depth + 1)
                parent_tex.update(tex)
                tex = parent_tex
                return tex, d.get('parent') if not parent else parent
            return tex, d.get('parent')
    return {}, None


def texture_path(tex_ref):
    ns, p = tex_ref.split(':') if ':' in tex_ref else ('minecraft', tex_ref)
    for base in (os.path.join(RP, ns, 'textures', p + '.png'), os.path.join(VASSETS, 'textures', p + '.png') if ns == 'minecraft' else ''):
        if base and os.path.exists(base):
            return base
    return None


def icon_for(item):
    refs = list(item['models']) or [item['base_id']]
    own = item['components'].get('item_model')  # the model the item really wears comes first
    if isinstance(own, str) and own in refs:
        refs.remove(own)
        refs.insert(0, own)
    for ref in refs:
        f = resolve_item_model(ref)
        if not f:
            continue
        definition = load(f).get('model', {})
        m = first_model(definition)
        if not m:
            continue
        tex, parent = model_textures(m)
        order = ['layer0', 'all', 'side', 'front', 'top', 'wall', 'wool', 'pattern', 'texture', 'end', 'cross', 'plant', 'particle']
        for k in order:
            if k in tex and not tex[k].startswith('#'):
                p = texture_path(tex[k])
                if p:
                    return {'texture': os.path.relpath(p, ROOT), 'kind': 'item' if k == 'layer0' else 'block',
                            'faces': {kk: os.path.relpath(texture_path(v), ROOT) for kk, v in tex.items()
                                      if not v.startswith('#') and texture_path(v)},
                            'model': m, 'gui': gui_node(definition)}
    return None


# ---------------------------------------------------------------- variants named by lore
def lore_variants():
    """Custom items that share one name but differ by model, with the first lore line saying which
    one it is (each cooking recipe names its dish, each smithing trim color its material): label
    every stack of them with that line, "Cooking Recipe (Gnocchi)"."""
    stacks = [(r['output'], r['output']['name']) for r in RECIPES + VANILLA_RECIPES_KEPT]
    for levels in TRADES.values():
        for ts in levels.values():
            for t in ts if isinstance(ts, list) else []:
                stacks += [(t[k], t[k]['name']) for k in ('wants', 'additional_wants', 'gives') if t.get(k)]
    stacks += [(e, e['item']) for t in LOOT.values() for e in t['entries'] if e.get('item')]
    stacks += [(a['icon'], a['icon']['name']) for a in ADV.values() if a.get('icon')]
    lines = defaultdict(set)
    for d, key in stacks:
        if d.get('_lore') and d.get('model'):
            lines[key].add((d['model'], d['_lore']))
    for d, key in stacks:
        line = re.sub(r'⟦[^⟧]*⟧', '', d.pop('_lore', '')).strip()
        if len(lines[key]) > 1 and len({m for m, _ in lines[key]}) > 1 and len({l for _, l in lines[key]}) > 1 \
                and line and not d.get('variant'):
            d['variant'] = '%s (%s)' % (ITEMS[key]['name'] if key in ITEMS else key, line)


lore_variants()


# ---------------------------------------------------------------- enchanted loot
def ench_name(eid, level):
    """An enchantment as the tooltip names it: "Anemos", "Power I", "Feather Falling III"."""
    eid = norm_id(eid)
    e = ENCH.get(eid)
    if e:
        name, top = e['name'], e.get('max_level')
    else:  # vanilla enchantments the pack leaves alone
        ns, p = eid.split(':')
        van = os.path.join(VDATA, 'enchantment', p + '.json')
        name = strip_codes(VANILLA_LANG.get('enchantment.%s.%s' % (ns, p), p.replace('_', ' ').title()))
        top = load(van).get('max_level') if os.path.exists(van) else None
    name = re.sub(r'⟦([^⟧]*)⟧', r'\1', name).strip()
    return name if level == 1 and top == 1 else '%s %s' % (name, ROMAN.get(level, str(level)))


def enchanted_variants():
    """Loot that sets an item's enchantments directly (set_components) makes a variant when they
    differ from the item's own: the Abbey's iron sword with Anemos, its Power I compound bow (the
    crafted one has Power II), the tannery's sturdy leather. Label those sources with them."""
    for t in LOOT.values():
        for e in t['entries']:
            ench = e.pop('_ench', None)
            if not ench or e.get('variant') or e.get('item') not in ITEMS:
                continue
            item = ITEMS[e['item']]
            if (item['components'].get('enchantments') or {}) != ench:
                e['variant'] = '%s (%s)' % (item['name'], ', '.join(ench_name(k, v) for k, v in ench.items()))


enchanted_variants()


# ---------------------------------------------------------------- variants with their own model
def model_variants():
    """Variants that look different in game (each Smithing Trim Color its material, each Cooking
    Recipe its dish, the two Clay Fetishes) get their own icon and tooltip, drawn and generated
    under the variant's label; generate.py uses the label in inventory slots and redirects it to
    the item's page. Returns {label: {item, name, base_id, models, components}}."""
    stacks = [r['output'] for r in RECIPES + VANILLA_RECIPES_KEPT]
    for levels in TRADES.values():
        for ts in levels.values():
            for t in ts if isinstance(ts, list) else []:
                stacks += [t[k] for k in ('wants', 'additional_wants', 'gives') if t.get(k)]
    stacks += [e for t in LOOT.values() for e in t['entries'] if e.get('item')]
    models = defaultdict(dict)  # item -> {label: (model, lore_rich)}
    for d in stacks:
        key = d.get('item') or d.get('name')
        if d.get('variant') and d.get('model') and key in ITEMS:
            models[key].setdefault(d['variant'], (d['model'], d.get('_lore_rich')))
    out = {}
    for key, labels in models.items():
        if len({m for m, _ in labels.values()}) < 2:
            continue  # one look for every variant (e.g. enchanted gear): the item's own icon is right
        for label, (model, rich) in labels.items():
            comps = dict(ITEMS[key]['components'])
            comps['item_model'] = model
            if rich:
                comps['lore_rich'] = rich
            out[label] = {'item': key, 'name': label, 'base_id': ITEMS[key]['base_id'], 'models': [model],
                          'components': comps}
    for d in stacks:
        d.pop('_lore_rich', None)
    return out


VARIANT_ITEMS = model_variants()


# ---------------------------------------------------------------- biomes (fishing climates)
# Every biome with its in-game name, and every biome tag expanded to biome ids: the
# fishing table picks its catch by these tags, so generate.py works out each biome's odds from them.
BIOMES = {}
for base in [VDATA] + sorted(glob.glob(os.path.join(DP, '*'))):
    ns = 'minecraft' if base == VDATA else os.path.basename(base)
    for f in glob.glob(os.path.join(base, 'worldgen', 'biome', '*.json')):
        bid = ns + ':' + os.path.basename(f)[:-5]
        key = 'biome.%s.%s' % (ns, bid.split(':')[1])
        BIOMES[bid] = strip_codes(LANG.get(key) or bid.split(':')[1].replace('_', ' ').title())
_BIOME_TAGS = load_tags('worldgen/biome')


def expand_biome_tag(tag, seen=()):
    out = []
    for v in _BIOME_TAGS.get(tag, []):
        v = v if isinstance(v, str) else v['id']
        if v.startswith('#'):
            if v[1:] not in seen:
                out += expand_biome_tag(v[1:], seen + (tag,))
        else:
            out.append(norm_ns(v))
    return out


BIOME_TAGS = {t: expand_biome_tag(t) for t in sorted(_BIOME_TAGS)}  # vanilla's and the pack's


# ---------------------------------------------------------------- splash texts
# The title screen's splashes: assets/minecraft/texts/splashes.txt, one per line (the game trims each
# line). The pack's file replaces vanilla's whole list.
_texts = os.path.join(RP, 'minecraft', 'texts')
for f in sorted(os.listdir(_texts)) if os.path.isdir(_texts) else []:
    expect('resource pack text', [f], rel(os.path.join(_texts, f)))
if not os.path.exists(os.path.join(VASSETS, 'texts', 'splashes.txt')):
    UNKNOWN[('resource pack text', 'vanilla has no texts/splashes.txt any more')].add('source/vanilla-assets')
SPLASHES = None
if os.path.exists(os.path.join(_texts, 'splashes.txt')):
    with open(os.path.join(_texts, 'splashes.txt'), encoding='utf-8') as f:
        lines = [ln.strip() for ln in f.read().splitlines()]
    while lines and not lines[-1]:
        lines.pop()  # a trailing newline is not an empty splash
    SPLASHES = {'src': rel(os.path.join(_texts, 'splashes.txt')), 'lines': lines}


# ---------------------------------------------------------------- write
for k, it in ITEMS.items():
    it['icon'] = icon_for(it)
for k, it in VARIANT_ITEMS.items():
    it['icon'] = icon_for(it)

pack_meta = load(os.path.join(SRC, 'MF_datapack', 'pack.mcmeta'))
version_text = render_text(pack_meta['pack']['description'])
git_head = os.popen('git -C "%s" rev-parse HEAD' % SRC).read().strip()
git_date = os.popen('git -C "%s" log -1 --format=%%cI' % SRC).read().strip()

data = {
    'meta': {'pack_description': version_text, 'git_head': git_head, 'git_date': git_date,
             'pack_format': pack_meta['pack'].get('min_format')},
    'lang_pack': PACK_LANG,
    'distinct_names': DISTINCT,
    'renames': {k: {'vanilla': VANILLA_LANG.get(k), 'pack': strip_codes(v)} for k, v in PACK_LANG.items()
                if k in VANILLA_LANG and VANILLA_LANG[k] != v},
    'items': ITEMS,
    'variant_items': VARIANT_ITEMS,
    'recipes': RECIPES,
    'vanilla_recipes_kept': VANILLA_RECIPES_KEPT,
    'blocked_vanilla': sorted(BLOCKED),
    'blocked_recipes': BLOCKED_RECIPE_INFO,
    'blocked_advancements': BLOCKED_ADVANCEMENTS,
    'loot': LOOT,
    'trades': {p: dict(v) for p, v in TRADES.items()},
    'professions': PROF_NAME,
    'enchantments': ENCH,
    'advancements': ADV,
    'functions': FUNCTIONS,
    'biomes': BIOMES,
    'biome_tags': BIOME_TAGS,
    'splashes': SPLASHES,
    'mob_modifications': MOB_MODIFICATIONS,
    'equipment_timers': EQUIPMENT_TIMERS,
    'missing_lang': sorted(MISSING_LANG),
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=1, ensure_ascii=False)
print('items', len(ITEMS), 'recipes', len(RECIPES), 'vanilla kept', len(VANILLA_RECIPES_KEPT),
      'loot', len(LOOT), 'enchantments', len(ENCH), 'advancements', len(ADV), 'functions', len(FUNCTIONS),
      'no icon', sum(1 for i in ITEMS.values() if not i['icon']), file=sys.stderr)

# ---------------------------------------------------------------- is the input what this file understands?
problems = []
# the vanilla data must be the Minecraft version the pack is written for (tools/mc_version.txt)
vanilla_version = load(os.path.join(ROOT, 'source', 'vanilla-data', 'version.json'))
vanilla_format = [vanilla_version['data_pack_version'] + vanilla_version.get('data_pack_version_minor', 0) / 10]
pack_min, pack_max = pack_meta['pack'].get('min_format'), pack_meta['pack'].get('max_format')
if pack_min and not (pack_min <= vanilla_format <= (pack_max or pack_min)):
    problems.append('The pack targets data pack format %s-%s ("%s"), but source/vanilla-data is Minecraft %s '
                    '(format %s). Put the pack\'s Minecraft version in tools/mc_version.txt and rerun '
                    'tools/fetch_sources.sh.' % (pack_min, pack_max, version_text.strip().splitlines()[-1],
                                                 vanilla_version['id'], vanilla_format))
if UNKNOWN:
    problems.append('The source uses keys, types or functions this extractor has never seen. It would skip '
                    'them silently, so handle each one (or list it in KNOWN if it really doesn\'t matter):')
    for (kind, key), files in sorted(UNKNOWN.items()):
        ex = sorted(files)
        problems.append('  %-20s %-40r in %d file(s), e.g. %s' % (kind, key, len(ex), ex[0]))
if problems:
    print('\n'.join(['', 'extract.py: the source format changed.'] + problems), file=sys.stderr)
    if '--allow-unknown' not in sys.argv:  # still wrote data.json, for inspection
        sys.exit(3)
