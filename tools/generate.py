#!/usr/bin/env python3
"""Generate data-driven wiki pages from build/data.json into wiki/generated/.

Everything here is derived from the pack's source files and is regenerated on
every build; hand-written articles transclude these pages through
{{Infobox auto}}, {{Recipes}}, {{Uses}}, {{Sources}} and the table templates.

Outputs (Template namespace unless noted):
  Data/Infobox/<item>      infobox call with stats computed from item components
  Data/Recipes/<item>      every recipe that produces the item, with interfaces
  Data/Uses/<item>         every recipe/trade that consumes the item
  Data/Sources/<item>      loot tables (chests, mobs, fishing, ...) and trades that give it
  Data/Trades/<profession> full trade table per villager profession
  Data/Loot/<table>        drop table for each loot table the pack defines
  Data/Food table, Data/Renamed items, Data/Trim templates, Data/Enchantments
  Data/Advancements/<tab>, Data/Advancements/tabs, Data/Advancements/technical
  Data/Station/<station>   a cooking station's non-food recipes (Mud Kiln, Oven, Blast Furnace, Kindling)
  Data/Fishing/...         the Fishing article's odds: Categories, Luck, Rarity, one per climate table, Special biomes
  Data/Splash texts        the title screen's splashes (and Data/Splash texts/Count)
  Data/Current version, Source/commit
  Module:Inventory slot/Aliases   tag names ("Any Planks") for recipe slots
  Module:Tooltip/Data     each item's in-game tooltip (name colour, lore runs) and glyph widths
  Main/<item>              stub article for every item that has no hand-written page
  Main/<vanilla name>      redirect from each vanilla name to its renamed item
"""
import html
import json
import math
import os
import re
import shutil
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = json.load(open(os.path.join(ROOT, 'build', 'data.json'), encoding='utf-8'))
VSUM = json.load(open(os.path.join(ROOT, 'source', 'vanilla-summary', 'item_components', 'data.min.json')))
GEN_FINAL = os.path.join(ROOT, 'wiki', 'generated')
GEN = GEN_FINAL + '.tmp'
HAND = os.path.join(ROOT, 'wiki', 'pages')
IMAGES = os.path.join(ROOT, 'build', 'images')

ITEMS = DATA['items']
VARIANT_ITEMS = DATA.get('variant_items', {})  # variants with their own look (extract.py: model_variants)
LANG = DATA['lang_pack']


# ------------------------------------------------------------------ helpers
def fname(title):
    return title.replace('/', '%2F') + '.wiki'


def write(ns, title, text):
    d = os.path.join(GEN, ns)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, fname(title) if ns != 'Module' else title.replace('/', '%2F') + '.lua'), 'w',
              encoding='utf-8') as f:
        # Templates must not end in a newline: it would be transcluded with them.
        f.write(text.rstrip() + ('' if ns in ('Template', 'Module') else '\n'))


def hand_exists(ns, title):
    return os.path.exists(os.path.join(HAND, ns, fname(title)))


_ICON_NAMES = None


def has_icon(name):
    """Whether tools/images.py produces an icon for this name. Decided from the data, not the file
    system, so the output is identical on case-insensitive (macOS) and case-sensitive (CI) disks."""
    global _ICON_NAMES
    if _ICON_NAMES is None:
        _ICON_NAMES = {safe(k) for k, it in ITEMS.items() if it.get('icon')}
    return safe(name) in _ICON_NAMES


def safe(name):
    return re.sub(r'[\\/:*?"<>|#\[\]{}]', '', name).strip()


def glyphs(s):
    # unnamed glyphs are extracted as their code point (⟦U+E00F⟧); Template:G takes the bare code (E00F)
    return re.sub(r'⟦(?:U\+)?([^⟧]+)⟧', lambda m: '{{G|%s}}' % m.group(1), s)


def esc(s):
    return str(s).replace('|', '{{!}}')


def ticks(t):
    s = int(round(t / 20))
    return '%d:%02d' % (s // 60, s % 60)


def roman(n):
    return {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X'}.get(n, str(n))


def pct(p):
    if p >= 0.9995:
        return '100%'
    if p >= 0.1:
        return '%.1f%%' % (p * 100)
    if p >= 0.01:
        return '%.2f%%' % (p * 100)
    return '%.3f%%' % (p * 100)


def title_case_effect(eid):
    return eid.split(':')[-1].replace('_', ' ').title().replace("'S", "'s")


EFFECT_NAMES = {'instant_health': 'Instant Health', 'instant_damage': 'Instant Damage', 'jump_boost': 'Jump Boost',
                'fire_resistance': 'Fire Resistance', 'water_breathing': 'Water Breathing',
                'night_vision': 'Night Vision', 'health_boost': 'Health Boost', 'slow_falling': 'Slow Falling',
                'conduit_power': 'Conduit Power', 'dolphins_grace': "Dolphin's Grace", 'bad_omen': 'Bad Omen',
                'hero_of_the_village': 'Hero of the Village', 'mining_fatigue': 'Mining Fatigue'}


def effect_name(eid):
    k = eid.split(':')[-1]
    return EFFECT_NAMES.get(k, title_case_effect(k))


ENCH = DATA['enchantments']
VANILLA_ENCH_NAMES = {}


def ench_name(eid):
    e = ENCH.get(eid)
    if e and e['name']:
        n = re.sub(r'⟦[^⟧]+⟧', '', e['name']).strip()
        return n or eid.split(':')[-1].replace('_', ' ').title()
    return eid.split(':')[-1].replace('_', ' ').title()


INTRINSIC_PAGES = [('warding', 'Warding'), ('adamant_tool', 'Adamant equipment'), ('adamant_weapon', 'Adamant equipment'),
                   ('adamant', 'Doom'), ('electrum_armour', 'Electrum equipment'),
                   ('shakudo_weapon', 'Shakudo equipment'), ('shakudo', 'Set bonus#Shakudo regeneration'), ('electrum_tool', 'Fortune'),
                   ('electrum', 'Warding'), ('cleanse', 'Cleanse'), ('max_magic_protection', 'Magic protection'),
                   ('magic_protection', 'Magic protection'), ('conduit_power', 'Conduit Power'), ('fire_proof', 'Fire Resistance'),
                   ('haste', 'Haste'), ('regeneration', 'Regeneration')]


INTRINSIC_LABELS = {'adamant_tool': 'Auto-smelting', 'adamant_weapon': 'Weakness', 'shakudo_weapon': 'Life steal',
                    'electrum_armour': 'Electrum bonus', 'electrum_tool': 'Fortune bonus'}


def intrinsic_text(eid, lvl):
    """Readable, correctly linked label for an enchantment (including glyph-named intrinsics)."""
    e = ENCH.get(eid) or {}
    raw = e.get('name') or ''
    plain = re.sub(r'⟦[^⟧]+⟧', '', raw).strip()
    maxl = e.get('max_level') or 1
    key = eid.split(':')[-1]
    page = next((p for k, p in INTRINSIC_PAGES if key.startswith(k)), None) if eid.startswith('matcha:') else None
    if page:
        label = glyphs(raw).strip()
        if not raw or 'kleispack.' in raw:  # untranslated key (pack bug): name it from the id
            label = INTRINSIC_LABELS.get(key, key.replace('_', ' ').capitalize())
            if maxl > 1:
                label += ' ' + roman(lvl)  # the level is real even when the name is missing
        elif not re.sub(r'\{\{G\|[^}]*\}\}', '', label).strip(' ()+-:0123456789∞'):
            label = (label + ' ' + INTRINSIC_LABELS.get(key, page.split('#')[-1])).strip()  # glyph-only: add a readable name
        # glyphs are images, and MediaWiki doesn't allow an image inside a link label: keep them outside
        glyph_part = ''.join(re.findall(r'\{\{G\|[^}]*\}\}', label))
        text = re.sub(r'\{\{G\|[^}]*\}\}', '', label).strip() or page.split('#')[-1]
        return ('%s [[%s|%s]]' % (glyph_part, page, text)).strip()
    if plain and not re.fullmatch(r'[0-9+∞\-() :.]*', plain) and not plain.startswith(('ERROR', 'enchantment.')):
        return '[[%s]]%s' % (plain, (' ' + roman(lvl)) if maxl > 1 else '')
    return key.replace('_', ' ').capitalize()


def ench_label(eid, lvl):
    e = ENCH.get(eid)
    name = ench_name(eid)
    raw = e['name'] if e else name
    if e and e.get('max_level', 1) == 1 and not eid.startswith('minecraft:'):
        return glyphs(raw) if raw else name
    return '%s %s' % (glyphs(raw) if raw and '⟦' in raw else name, roman(lvl) if (e and e.get('max_level', 1) > 1) or lvl > 1 else '')


# ------------------------------------------------------------------ item stats
def vdefaults(base_id):
    return VSUM.get(base_id.split(':')[-1], {})


def effective(item):
    """Vanilla default components of the base item, overridden by the pack's components."""
    comps = {k.split(':')[-1]: v for k, v in vdefaults(item['base_id']).items()}
    if not item['renamed_vanilla']:
        for k in ('food', 'consumable'):
            if k not in item['components']:
                comps.pop(k, None)
    for k, v in item['components'].items():
        comps[k] = v
    return comps


def heal_from_effects(effects):
    hp = 0
    others = []
    for e in effects:
        eid = e['id'].split(':')[-1]
        amp = e.get('amplifier', 0)
        dur = e.get('duration', 0)
        if eid == 'regeneration' and (not e.get('show_icon', True) or amp >= 2):
            interval = max(1, 50 >> amp)
            hp += dur // interval
        elif eid == 'instant_health':
            hp += 4 << amp
        else:
            others.append(e)
    return hp, others


def consume_effects(comps):
    out = []
    cons = comps.get('consumable') or {}
    for eff in cons.get('on_consume_effects', []) or []:
        if eff.get('type', '').endswith('apply_effects'):
            for e in eff.get('effects', []):
                e = dict(e)
                e['probability'] = eff.get('probability', 1)
                out.append(e)
    food = comps.get('food')
    return out


def effect_text(e):
    s = '{{EffectLink|%s}}' % effect_name(e['id'])
    amp = e.get('amplifier', 0)
    if amp:
        s += ' ' + roman(amp + 1)
    dur = e.get('duration')
    if dur is not None:
        s += ' (%s)' % ('∞' if dur < 0 else ticks(dur))
    if e.get('probability', 1) < 1:
        s += ' — %d%% chance' % round(e['probability'] * 100)
    return s


def attr_sum(comps, attr, slot=None):
    tot = 0
    found = False
    for m in comps.get('attribute_modifiers', []) or []:
        if m.get('type', '').split(':')[-1] == attr and m.get('operation', 'add_value') == 'add_value':
            if slot is None or m.get('slot') in (slot, 'any', 'hand', 'armor', None):  # no slot means any slot
                tot += m.get('amount', 0)
                found = True
    return (tot, found)


def fmt_num(x):
    x = round(x, 2)
    return str(int(x)) if x == int(x) else str(x)


def mining_speed(tool):
    """A tool component's mining speed on the blocks it is made for (the mineable/ rules), or None."""
    rules = [r for r in tool.get('rules', []) if r.get('speed') and r.get('correct_for_drops') is not False and r.get('speed') < 1000]
    mineable = [r['speed'] for r in rules if isinstance(r.get('blocks'), str) and 'mineable/' in r['blocks']]
    speeds = mineable or [r['speed'] for r in rules if 'cobweb' not in json.dumps(r.get('blocks'))]
    return max(speeds) if speeds else None


def enchant_levels(comps):
    """{enchantment id: level} of an item's enchantments and stored enchantments (the pack's intrinsics)."""
    ench = {}
    for k in ('enchantments', 'stored_enchantments'):
        v = comps.get(k) or {}
        if isinstance(v, dict) and 'levels' in v:
            v = v['levels']
        ench.update(v)
    return ench


BLOCK_ITEMS = set()
try:
    BLOCKS = json.load(open(os.path.join(ROOT, 'source', 'vanilla-summary', 'blocks', 'data.min.json')))
    BLOCK_ITEMS = set(BLOCKS.keys())
except Exception:
    BLOCKS = {}


def item_type(item, comps):
    if comps.get('food') or (comps.get('consumable') and consume_effects(comps) and 'death_protection' not in comps):
        return 'Food'
    eq = comps.get('equippable') or {}
    if eq.get('slot') in ('head', 'chest', 'legs', 'feet') and ('armor' in json.dumps(comps.get('attribute_modifiers', [])) or 'elytra' in item['name'].lower() or eq.get('slot')):
        return 'Armor' if 'elytra' not in item['name'].lower() else 'Equipment'
    tool = comps.get('tool')
    if tool:
        # swords, maces and tridents carry a tool component too (for cobwebs and bamboo), but
        # it mines nothing a tool would; they are weapons
        blocks = json.dumps([r.get('blocks') for r in tool.get('rules', [])])
        if 'mineable/' in blocks or 'shears' in blocks or 'weapon' not in comps:
            return 'Tool'
    if comps.get('weapon') or attr_sum(comps, 'attack_damage')[1]:
        return 'Weapon'
    if item['base_id'].split(':')[-1] in BLOCK_ITEMS:
        return 'Block'
    return 'Item'


def vanilla_tag(tag):
    ns, p = tag.lstrip('#').split(':') if ':' in tag else ('minecraft', tag.lstrip('#'))
    for base in (os.path.join(ROOT, 'source', 'matcha-flavoured', 'MF_datapack', 'data', ns, 'tags', 'item', p + '.json'),
                 os.path.join(ROOT, 'source', 'vanilla-data', 'data', ns, 'tags', 'item', p + '.json')):
        if os.path.exists(base):
            out = []
            for v in json.load(open(base))['values']:
                v = v if isinstance(v, str) else v['id']
                out += vanilla_tag(v) if v.startswith('#') else [v]
            return out
    return []


def item_link_list(ids_or_tag):
    if isinstance(ids_or_tag, str):
        if ids_or_tag.startswith('#'):
            ids = vanilla_tag(ids_or_tag)
            return ', '.join(link_for_id(i) for i in ids) if ids else '<code>%s</code>' % ids_or_tag
        return link_for_id(ids_or_tag)
    return ', '.join(link_for_id(i) for i in ids_or_tag)


def id_name(i):
    i = i if ':' in i else 'minecraft:' + i
    k = i.split(':')[-1]
    if k in DATA['distinct_names']:
        return DATA['distinct_names'][k]  # e.g. "Flow Armor Trim Smithing Template", not "Smithing Template"
    for key in ('item.minecraft.' + k, 'block.minecraft.' + k):
        if key in LANG:
            return re.sub('§.', '', LANG[key]).strip()
    vl = VANILLA_LANG.get('item.minecraft.' + k) or VANILLA_LANG.get('block.minecraft.' + k)
    return vl or k.replace('_', ' ').title()


VANILLA_LANG = json.load(open(os.path.join(ROOT, 'source', 'vanilla-assets', 'assets', 'minecraft', 'lang', 'en_us.json')))


def link_for_id(i):
    return '[[%s]]' % id_name(i)


def infobox(item):
    c = effective(item)
    name = item.get('_key', item['name'])
    f = {}
    t = item_type(item, c)
    f['type'] = t
    vn = item['vanilla_name']
    if item['renamed_vanilla'] and vn != name:
        f['vanilla'] = '{{MCW|%s}}' % vn
    rar = c.get('rarity')
    if rar and rar != 'common':
        f['rarity'] = rar.title()
    mss = c.get('max_stack_size', 64)
    f['stackable'] = 'Yes (%d)' % mss if mss > 1 else 'No'
    effs = consume_effects(c)
    if effs:
        hp, others = heal_from_effects(effs)
        if hp:
            f['heals'] = '{{Hp|%d}}' % hp
        if others:
            f['effects'] = '<br />'.join(effect_text(e) for e in others)
        cs = (c.get('consumable') or {}).get('consume_seconds', 1.6)
        f['eat_time'] = '%s seconds' % fmt_num(cs)
    dp = c.get('death_protection')
    if dp:
        f['effects'] = (f.get('effects', '') + '<br />' if f.get('effects') else '') + "Prevents death when held, like a [[Totem of Undying]]"
    if 'unbreakable' in c:
        f['durability'] = 'Unbreakable'
    elif c.get('max_damage'):
        f['durability'] = str(c['max_damage'])
    dmg, has = attr_sum(c, 'attack_damage', 'mainhand')
    if has:
        f['damage'] = '%s ({{Hp|%s}})' % (fmt_num(1 + dmg), fmt_num(1 + dmg)) if False else '{{Hp|%s}}' % fmt_num(1 + dmg)
    spd, has = attr_sum(c, 'attack_speed', 'mainhand')
    if has:
        f['attackspeed'] = fmt_num(4 + spd)
    tool = c.get('tool')
    if tool and mining_speed(tool) is not None:
        f['miningspeed'] = fmt_num(mining_speed(tool))
    for attr, key in (('armor', 'armor'), ('armor_toughness', 'toughness'), ('knockback_resistance', 'knockbackres')):
        v, has = attr_sum(c, attr)
        if has and v:
            f[key] = fmt_num(v if attr != 'knockback_resistance' else v * 10)
    rep = c.get('repairable')
    if rep and rep.get('items') and c.get('max_damage') and not c.get('unbreakable'):
        f['repair'] = item_link_list(rep['items'])
    ench = enchant_levels(c)
    if ench and item['base_id'] != 'minecraft:enchanted_book':
        f['intrinsics'] = '<br />'.join(intrinsic_text(e, l) for e, l in ench.items())
    elif ench:
        f['effects'] = ('%s<br />' % f['effects'] if f.get('effects') else '') + 'Stores: ' + ', '.join(
            intrinsic_text(e, l) for e, l in ench.items())
    if any(item['components'].get('lore_rich') or []):
        # the item's in-game tooltip, drawn under its inventory slot (Module:Tooltip)
        f['tooltipbox'] = '{{Tooltip|%s}}' % safe(name)
    model = (item['models'] or [None])[0]
    f['id'] = '<code>%s</code>' % (model or item['base_id'])
    if model:
        f['base'] = '<code>%s</code>' % item['base_id']
    srcs = []
    for s in item['sources']:
        if s['src'] not in srcs and s['how'] in ('recipe', 'loot', 'trade'):
            srcs.append(s['src'])
    if srcs:
        f['source'] = '{{Source|%s|%s}}' % (srcs[0], os.path.basename(srcs[0]))
    lines = ['{{Infobox', '|title={{#if:{{{title|}}}|{{{title}}}|%s}}' % name]
    if has_icon(name):
        # large render plus the inventory slot, like minecraft.wiki's item infoboxes
        lines.append('|image={{#if:{{{image|}}}|{{{image}}}|%s.png}}' % safe(name))
        lines.append('|imagesize=160px')
        lines.append('|invimage=%s' % safe(name))
    for k in ('caption', 'extrarows', 'bonus'):
        lines.append('|%s={{{%s|}}}' % (k, k))
    for k in ('type', 'intrinsics', 'renewable'):
        if k in f:
            lines.append('|%s={{#if:{{{%s|}}}|{{{%s}}}|%s}}' % (k, k, k, f.pop(k)))
        else:
            lines.append('|%s={{{%s|}}}' % (k, k))
    for k, v in f.items():
        lines.append('|%s=%s' % (k, v))
    lines.append('}}')
    return '<includeonly>' + '\n'.join(lines) + '</includeonly><noinclude>Generated from the pack source by <code>tools/generate.py</code>. Do not edit.\n[[Category:Generated data]]</noinclude>'


# ------------------------------------------------------------------ recipes
ALIASES = {}


def alias_for(tag, names):
    pretty = tag.split(':')[-1].split('/')[-1].replace('_', ' ')
    pretty = 'Any ' + pretty.title()
    uniq = []
    for n in names:
        if n not in uniq:
            uniq.append(n)
    ALIASES[pretty] = uniq
    return pretty


def slot_text(ing):
    if ing is None:
        return ''
    names = []
    for n in ing['names']:
        if n not in names:
            names.append(n)
    if ing.get('tag') and len(names) > 1:
        return alias_for(ing['tag'], names)
    return ';'.join(safe(n) for n in names)


def ing_links(ing):
    if ing is None:
        return ''
    if ing.get('tag') and len(set(ing['names'])) > 1:
        members = []
        for n in ing['names']:
            if n not in members:
                members.append(n)
        return '<span class="explain" title="%s">Any %s</span>' % (
            ', '.join(members).replace('"', ''), ing['tag'].split(':')[-1].split('/')[-1].replace('_', ' '))
    names = []
    for n in ing['names']:
        if n not in names:
            names.append(n)
    return ' or '.join('[[%s]]' % n for n in names)


def slot_name(s):
    """The name an inventory slot shows a stack under: a variant with its own look (a Smithing Trim
    Color's material, a Cooking Recipe's dish) has its own icon and tooltip under its label, and
    the label redirects to the item's page."""
    return s['variant'] if s.get('variant') in VARIANT_ITEMS else s['name']


def out_text(o):
    return safe(slot_name(o)) + (',%d' % o['count'] if o.get('count', 1) > 1 else '')


def cook_ticks(r):
    """A cooking recipe's time in ticks (the recipe type's default when the file gives none)."""
    return r.get('cookingtime') or {'smelting': 200, 'smoking': 100, 'blasting': 100,
                                    'campfire_cooking': 600}[r['type'].split(':')[-1]]


def recipe_ui(r):
    t = r['type'].split(':')[-1]
    if t == 'crafting_shaped':
        args = {}
        pattern = r['pattern']
        for y, row in enumerate(pattern):
            for x, ch in enumerate(row):
                if ch == ' ':
                    continue
                args['ABC'[x] + str(y + 1)] = slot_text(r['key'][ch])
        a = '|'.join('%s=%s' % (k, v) for k, v in sorted(args.items()))
        return '{{Crafting|%s|Output=%s}}' % (a, out_text(r['output']))
    if t == 'crafting_shapeless':
        slots = ['A1', 'B1', 'C1', 'A2', 'B2', 'C2', 'A3', 'B3', 'C3']
        a = '|'.join('%s=%s' % (slots[i], slot_text(g)) for i, g in enumerate(r['ingredients'][:9]))
        return '{{Crafting|%s|Output=%s|shapeless=1}}' % (a, out_text(r['output']))
    if t in ('smelting', 'smoking', 'blasting', 'campfire_cooking'):
        secs = cook_ticks(r) / 20
        note = '%s s' % fmt_num(secs)
        if r.get('experience'):
            note += ', %s XP' % fmt_num(r['experience'])
        return '{{Cooking|station=%s|Input=%s|Output=%s|time=%s|note=%s}}' % (
            r['station'], slot_text(r['input']), out_text(r['output']), fmt_num(secs), note)
    if t == 'stonecutting':
        return '{{Stonecutter|Input=%s|Output=%s}}' % (slot_text(r['input']), out_text(r['output']))
    if t == 'smithing_transform':
        return '{{Smithing|Template=%s|Base=%s|Addition=%s|Output=%s}}' % (
            slot_text(r.get('template')), slot_text(r['base']), slot_text(r['addition']), out_text(r['output']))
    return ''


def recipe_ingredients(r):
    t = r['type'].split(':')[-1]
    counts = []
    if t == 'crafting_shaped':
        tally = defaultdict(int)
        order = []
        for row in r['pattern']:
            for ch in row:
                if ch != ' ':
                    if ch not in order:
                        order.append(ch)
                    tally[ch] += 1
        for ch in order:
            counts.append((ing_links(r['key'][ch]), tally[ch]))
    elif t == 'crafting_shapeless':
        tally = defaultdict(int)
        order = []
        for g in r['ingredients']:
            k = ing_links(g)
            if k not in order:
                order.append(k)
            tally[k] += 1
        counts = [(k, tally[k]) for k in order]
    elif t in ('smelting', 'smoking', 'blasting', 'campfire_cooking', 'stonecutting'):
        counts = [(ing_links(r['input']), 1)]
    elif t == 'smithing_transform':
        for k in ('template', 'base', 'addition'):
            if r.get(k):
                counts.append((ing_links(r[k]), 1))
    return ' +<br />'.join(('%d × %s' % (n, s)) if n > 1 else s for s, n in counts)


def all_ingredient_names(r):
    t = r['type'].split(':')[-1]
    ings = []
    if t == 'crafting_shaped':
        ings = [r['key'][ch] for row in r['pattern'] for ch in row if ch != ' ']
    elif t == 'crafting_shapeless':
        ings = r['ingredients']
    elif t in ('smelting', 'smoking', 'blasting', 'campfire_cooking', 'stonecutting'):
        ings = [r['input']]
    elif t == 'smithing_transform':
        ings = [r.get('template'), r['base'], r['addition']]
    names = set()
    for g in ings:
        if g:
            names.update(g['names'])
    return names


COMPACT_AFTER = 40


def recipe_table(recipes, first_col):
    if not recipes:
        return ''
    # Past ~40 recipes the crafting grids push the page over MediaWiki's 2 MB include limit (the table
    # then doesn't render at all) and make it very heavy, so long lists name the ingredients only.
    grids = len(recipes) <= COMPACT_AFTER
    rows = []
    for r in recipes:
        origin = '' if r['origin'] == 'pack' else ' <small>(vanilla recipe)</small>'
        first = first_col(r)
        if grids:
            rows.append('|-\n| %s%s\n| %s\n| %s' % (first, origin, recipe_ingredients(r), recipe_ui(r)))
        else:
            rows.append('|-\n| %s%s\n| %s' % (first, origin, recipe_ingredients(r)))
    collapsible = ' mw-collapsible' if len(recipes) > 12 else ''
    head = '{| class="wikitable recipe-table%s"\n! %s !! Ingredients%s' % (collapsible, 'Name', ' !! Recipe' if grids else '')
    return head + '\n' + '\n'.join(rows) + '\n|}'


def station_heading(r):
    return {'Crafting Table': 'Crafting', 'Oven': 'Cooking', 'Mud Kiln': 'Cooking', 'Blast Furnace': 'Blasting',
            'Kindling': 'Cooking', 'Stonecutter': 'Stonecutting', 'Smithing Table': 'Smithing'}.get(r['station'], r['station'])


ALL_RECIPES = DATA['recipes']
VANILLA_KEPT = DATA['vanilla_recipes_kept']
PACK_OUTPUT_IDS = set(r['output']['id'] for r in ALL_RECIPES)


def producing(name):
    rs = [r for r in ALL_RECIPES if r['output']['name'] == name]
    vs = [r for r in VANILLA_KEPT if r['output']['name'] == name]
    return rs + vs


USES = defaultdict(list)
for r in ALL_RECIPES + VANILLA_KEPT:
    if r['id'].startswith('debug:'):
        continue  # developer recipes (they need a command block); shown only on the debug items' own pages
    for n in all_ingredient_names(r):
        USES[n].append(r)
# Recipes match ingredients by item id only, so a custom item also works in every recipe
# that accepts its base item (e.g. custom fish are cod or salmon underneath).
_BASE_NAME = {}
for _n, _it in ITEMS.items():
    if _it['renamed_vanilla'] and _it['vanilla_name']:
        _BASE_NAME.setdefault(_it['base_id'], _n)
for _n, _it in ITEMS.items():
    if not _it['renamed_vanilla']:
        _b = _BASE_NAME.get(_it['base_id'])
        # only when both are the same kind of thing (a fish is still food; a gem built on a
        # renamed food item is not meant to be cooked), to avoid listing quirks as uses
        if _b and _b != _n and item_type(_it, effective(_it)) == item_type(ITEMS[_b], effective(ITEMS[_b])):
            for r in USES.get(_b, []):
                if r not in USES[_n] and r['output']['name'] != _n:
                    USES[_n].append(r)


def out_link(o):
    """Link to a recipe's output, naming its variant where one item has several ("Cooking Recipe (Gnocchi)")."""
    return '[[%s|%s]]' % (o['name'], esc(o['variant'])) if o.get('variant') else '[[%s]]' % o['name']


def recipes_page(name):
    rs = producing(name)
    if not rs:
        return None
    groups = defaultdict(list)
    for r in rs:
        groups[station_heading(r)].append(r)
    parts = []
    for g in ('Crafting', 'Cooking', 'Blasting', 'Smithing', 'Stonecutting'):
        if g in groups:
            if len(groups) > 1:
                parts.append("'''%s'''" % g)
            parts.append(recipe_table(groups[g], lambda r: out_link(r['output'])))
    return '<includeonly>' + '\n'.join(parts) + '</includeonly><noinclude>Generated from the pack source by <code>tools/generate.py</code>. Do not edit.\n[[Category:Generated data]]</noinclude>'


# ------------------------------------------------------------------ loot
LOOT = DATA['loot']


def count_range(c):
    if c is None:
        return (1, 1)
    if isinstance(c, (int, float)):
        return (c, c)
    if isinstance(c, dict):
        t = c.get('type', '').split(':')[-1]
        if t == 'uniform' or ('min' in c and 'max' in c):
            lo = c.get('min', 1)
            hi = c.get('max', 1)
            lo = lo if isinstance(lo, (int, float)) else 1
            hi = hi if isinstance(hi, (int, float)) else 1
            return (lo, hi)
        if t == 'constant':
            return (c.get('value', 1), c.get('value', 1))
        if t == 'binomial':
            return (0, c.get('n', 1))
    return (1, 1)


def rolls_avg(r):
    lo, hi = count_range(r)
    return (lo + hi) / 2, lo, hi


# The pack's fishing biome tags, named as the Fishing article's sections (and the Angler's Almanac) name them
BIOME_GROUPS = {'freshwater_cold': 'Cold freshwater', 'freshwater_cool': 'Cool freshwater',
                'freshwater_temperate': 'Temperate freshwater', 'freshwater_hot_dry': 'Arid freshwater',
                'freshwater_hot_wet': 'Tropical freshwater', 'swamps': 'Brackish water',
                'saltwater_cold': 'Cold saltwater', 'saltwater_cool': 'Cool saltwater',
                'saltwater_temperate': 'Temperate saltwater', 'saltwater_warm': 'Warm saltwater',
                'saltwater_hot': 'Hot saltwater', 'unused': 'Other biomes'}


def biome_note(b):
    """Readable biome condition: "#minecraft:saltwater_warm" -> "warm saltwater biomes", ids -> in-game names."""
    out = []
    for x in ([b] if isinstance(b, str) else b):
        key = x.split(':')[-1]
        if x.startswith('#') and key in BIOME_GROUPS:
            g = BIOME_GROUPS[key]
            out.append('[[Fishing#%s|%s]]' % (g, g[0].lower() + g[1:] + ('' if key == 'unused' else ' biomes')))
        else:
            out.append(key.replace('_', ' ').title().replace(' Of ', ' of ').replace(' The ', ' the '))
    return 'only in ' + ', '.join(out)


BIOMES = DATA['biomes']  # biome id -> in-game name
BIOME_TAGS = DATA['biome_tags']  # biome tag -> biome ids


def entry_biome_list(e):
    """The biome ids where a loot entry's location checks pass, in the order its tags list them, or None
    when it has no biome condition."""
    out = None
    for c in e.get('conditions') or []:
        pred = c.get('predicate') or {}
        b = pred.get('biomes') or pred.get('biome')
        if c.get('condition', '').split(':')[-1] != 'location_check' or not b:
            continue
        ids = []
        for x in ([b] if isinstance(b, str) else b):
            ids += BIOME_TAGS.get(x[1:], []) if x.startswith('#') else [x if ':' in x else 'minecraft:' + x]
        ids = list(dict.fromkeys(ids))
        out = ids if out is None else [i for i in out if i in ids]
    return out


def entry_biomes(e):
    b = entry_biome_list(e)
    return None if b is None else set(b)


def cond_notes(conds):
    notes = []
    mult = 1.0
    for c in conds or []:
        t = c.get('condition', '').split(':')[-1]
        if t == 'killed_by_player':
            notes.append('player kill')
        elif t == 'random_chance':
            ch = c.get('chance', 1)
            if isinstance(ch, (int, float)):
                mult *= ch
            else:
                notes.append('random chance')
        elif t == 'random_chance_with_enchanted_bonus':
            ch = c.get('unenchanted_chance', 1)
            if isinstance(ch, (int, float)):
                mult *= ch
            notes.append('Looting increases chance')
        elif t == 'location_check':
            b = (c.get('predicate') or {}).get('biomes') or (c.get('predicate') or {}).get('biome')
            if b:
                notes.append(biome_note(b))
            else:
                notes.append('location')
        elif t == 'entity_properties':
            pred = c.get('predicate') or {}
            et = pred.get('entity_tags')
            if et and et.get('none_of') == ['NoDrops'] and len(pred) == 1:
                continue
            if 'flags' in pred and pred['flags'].get('is_baby'):
                notes.append('baby')
            elif 'type_specific' in json.dumps(pred) and 'in_open_water' in json.dumps(pred):
                notes.append('open water')
            else:
                notes.append('entity condition')
        elif t == 'match_tool':
            p = c.get('predicate') or {}
            if 'enchantments' in json.dumps(p) and 'silk_touch' in json.dumps(p):
                notes.append('Silk Touch')
            elif 'items' in p:
                it = p['items']
                notes.append('tool: %s' % (id_name(it) if isinstance(it, str) and not it.startswith('#') else it))
            else:
                notes.append('specific tool')
        elif t == 'inverted':
            inner = cond_notes([c.get('term')])[1]
            if inner:
                notes.append('not ' + inner[0])
        elif t == 'survives_explosion':
            continue
        elif t == 'table_bonus':
            ch = c.get('chances') or [1]
            mult *= ch[0]
            notes.append('Fortune increases chance')
        elif t in ('any_of', 'all_of', 'alternative'):
            m2, n2 = cond_notes(c.get('terms'))
            notes += n2
        elif t == 'reference':
            notes.append('predicate %s' % c.get('name'))
        elif t == 'weather_check':
            notes.append('weather')
        elif t == 'time_check':
            notes.append('time of day')
        elif t == 'value_check':
            notes.append('scoreboard/value check')
        elif t == 'entity_scores':
            notes.append('score check')
        elif t == 'damage_source_properties':
            notes.append('damage source')
        elif t == 'enchantment_active_check':
            notes.append('enchantment active')
        else:
            notes.append(t.replace('_', ' '))
    return mult, notes


def flatten(table_id, prob=1.0, notes=(), depth=0, seen=(), where=None):
    """Yield (item, per-roll prob of this entry in context, count range, notes, rolls, table, variant)
    for a table. The variant labels a stack that a loot function makes distinct ("Arrow of Poison").
    where: the biomes the rolling entry was limited to; entries for other biomes can't apply."""
    t = LOOT.get(table_id)
    out = []
    if not t or depth > 6 or table_id in seen:
        return out
    pools = defaultdict(list)
    root = (seen or (table_id,))[0]
    for e in t['entries']:
        # "caught in open water" needs a fishing hook: never true when a chest or mob rolls the fishing table
        if not root.startswith('minecraft:gameplay/fishing') and 'in_open_water' in json.dumps(e.get('conditions') or []):
            continue
        if where is not None and entry_biomes(e) is not None and not (entry_biomes(e) & where):
            continue  # e.g. the swamps' frogs in the junk that only #minecraft:unused biomes add
        pools[e['pool']].append(e)
    for pi, ents in pools.items():
        e0 = ents[0]
        pmult, pnotes = cond_notes(e0.get('pool_conditions'))
        # Entries gated by a location (biome) check are weighed against the unconditioned entries and the
        # gated entries that also apply wherever they do (also_there); others are for other biomes.
        def is_loc(e):
            return any((c.get('condition', '').split(':')[-1] == 'location_check') for c in (e.get('conditions') or []))
        # children of one alternatives/group entry share that entry's single weighted slot
        slots = {}
        for e in ents:
            slots.setdefault(e.get('slot') or id(e), e)
        uncond = sum(e['weight'] for e in slots.values() if not is_loc(e))
        locw = [e['weight'] for e in slots.values() if is_loc(e)]

        def also_there(e):
            """Weight of the other biome-gated entries that apply wherever e does: the Deep Dark's own fishing
            entry is always rolled together with the #minecraft:unused fallback junk, which contains it."""
            be = entry_biomes(e)
            me = e.get('slot') or id(e)
            return sum(f['weight'] for f in slots.values() if (f.get('slot') or id(f)) != me and is_loc(f) and be is not None
                       and entry_biomes(f) is not None and be <= entry_biomes(f))
        earlier = defaultdict(list)  # alternatives slot -> condition notes of the children before this one
        ravg, rlo, rhi = rolls_avg(e0['rolls'])
        for e in ents:
            emult, enotes = cond_notes(e.get('conditions'))
            if e.get('slot_kind') == 'alternatives':
                prior = earlier[e['slot']]
                earlier[e['slot']] = prior + enotes
                if prior and not enotes:
                    enotes = ['without ' + ', '.join(dict.fromkeys(prior))]  # the fallback branch
            total = (uncond + e['weight'] + also_there(e)) if is_loc(e) else (uncond + (max(locw) if locw else 0))
            p = e['weight'] / (total or 1) * emult * pmult
            if e.get('empty'):
                continue
            n = list(notes) + pnotes + enotes
            if 'loot_table' in e:
                sub = e['loot_table']
                if isinstance(sub, dict):
                    continue
                override = count_range(e['count']) if e.get('count') is not None else None
                inner = flatten(sub, 1.0, (), depth + 1, seen + (table_id,), narrower(where, entry_biomes(e)))
                for (it, p2, cnt, n2, r2, tid, var) in inner:
                    # nested table: chance per roll of this entry times the nested chance (per nested roll)
                    if override:
                        cnt, p2 = override, p2 * positive_share(override)
                    out.append((it, p * p2 * prob, cnt, n + n2, (rlo, rhi), table_id, var))
            elif 'item' in e and e['item']:
                cr = count_range(e.get('count'))
                out.append((e['item'], p * prob * positive_share(cr), cr, n, (rlo, rhi), table_id, e.get('variant')))
    return out


def narrower(a, b):
    """The biomes both limits allow (None means any biome)."""
    return b if a is None else a if b is None else a & b


def positive_share(cnt):
    """Share of rolls whose count is at least 1 (set_count with a uniform integer range can roll 0)."""
    lo, hi = cnt
    if lo >= 1 or hi < 1:
        return 1.0 if lo >= 1 else 0.0
    lo_i, hi_i = int(math.ceil(lo)), int(math.floor(hi))
    total = hi_i - lo_i + 1
    return max(0, hi_i - max(lo_i, 1) + 1) / total if total > 0 else 1.0


def chance_at_least_one(p, rolls):
    lo, hi = rolls
    lo, hi = int(lo), int(hi)
    if hi < lo:
        hi = lo
    vals = [1 - (1 - min(p, 1)) ** n for n in range(lo, hi + 1)]
    return sum(vals) / len(vals)


def loot_category(lid):
    ns, p = lid.split(':')
    if ns != 'minecraft':
        return None  # matcha:* tables are item definitions and sub-tables, not world sources
    if p.startswith('chests/'):
        return 'Chest loot'
    if p.startswith('entities/'):
        return 'Mob drops'
    if p.startswith('gameplay/fishing'):
        return 'Fishing'
    if p.startswith('archaeology/'):
        return 'Archaeology'
    if p.startswith('blocks/'):
        return 'Block drops'
    if p.startswith('gameplay/'):
        return 'Gameplay'
    if p.startswith('shearing/'):
        return 'Shearing'
    if p.startswith('spawners/'):
        return 'Trial spawners'
    if p.startswith('dispensers/'):
        return 'Dispensers'
    if p.startswith('pots/'):
        return 'Decorated pots'
    if p.startswith('equipment/'):
        return 'Mob equipment'
    if p.startswith('harvest/'):
        return 'Harvesting'
    return None  # matcha:* item definition tables and similar


def loot_label(lid):
    ns, p = lid.split(':')
    base = p.split('/', 1)[-1]
    return base.replace('/', ' / ').replace('_', ' ')


def loot_table_page(lid):
    rows = flatten(lid)
    if not rows:
        return None
    agg = {}
    for it, p, cnt, notes, rolls, src, var in rows:
        key = (it, var, cnt, tuple(notes))
        if key in agg:
            agg[key][0] += p
        else:
            agg[key] = [p, rolls]
    lines = ['{| class="wikitable sortable loot-table"', '! Item !! Stack size !! Chance per roll !! Chance per table !! Notes']
    for (it, var, cnt, notes), (p, rolls) in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        c = ('%s–%s' % (fmt_num(cnt[0]), fmt_num(cnt[1]))) if cnt[0] != cnt[1] else fmt_num(cnt[0])
        lines.append('|-\n| %s || %s || %s || %s || %s' % (
            il(it, var), c, pct(p), pct(chance_at_least_one(p, rolls)), ', '.join(dict.fromkeys(notes))))
    lines.append('|}')
    t = LOOT[lid]
    rl = set()
    for e in t['entries']:
        lo, hi = count_range(e['rolls'])
        rl.add((lo, hi))
    rolls_txt = '; '.join(('%s–%s' % (fmt_num(a), fmt_num(b))) if a != b else fmt_num(a) for a, b in sorted(rl))
    head = "<small>Loot table <code>%s</code> ({{Source|%s|source}}); pools roll %s time(s).%s</small>\n" % (
        lid, t['src'], rolls_txt, ' Overrides the vanilla table.' if t.get('overrides_vanilla') else '')
    return '<includeonly>' + head + '\n'.join(lines) + '</includeonly><noinclude>Generated from the pack source by <code>tools/generate.py</code>. Do not edit.\n[[Category:Generated data]]</noinclude>'


REFERENCED = set()  # tables rolled by another table of the same category (e.g. fishing -> fishing/treasure)
for _lid, _t in LOOT.items():
    for _e in _t['entries']:
        _sub = _e.get('loot_table')
        if isinstance(_sub, str) and _sub in LOOT and loot_category(_sub) == loot_category(_lid):
            REFERENCED.add(_sub)
SOURCES = defaultdict(list)  # item -> [(category, label, lid, p, cnt, notes, rolls, variant)]
ROLLED = {_e['loot_table'] for _t in LOOT.values() for _e in _t['entries'] if isinstance(_e.get('loot_table'), str)}
for lid in LOOT:
    cat = loot_category(lid)
    if not cat or lid in REFERENCED:
        continue  # sub-tables are counted through the table that rolls them
    if lid.startswith('minecraft:gameplay/fishing/') and lid not in ROLLED:
        continue  # vanilla fishing sub-table the pack's fishing table no longer rolls
    for it, p, cnt, notes, rolls, src, var in flatten(lid):
        SOURCES[it].append((cat, loot_label(lid), lid, p, cnt, notes, rolls, var))


# ------------------------------------------------------------------ trades
TRADES = DATA['trades']
PROF = DATA['professions']


PAGES_HERE = None


def page_exists(name):
    """True if the wiki will have a page (hand-written, generated stub or redirect) for name."""
    global PAGES_HERE
    if PAGES_HERE is None:
        PAGES_HERE = set()
        for root, _, files in os.walk(os.path.join(HAND, 'Main')):
            PAGES_HERE.update(f[:-5].replace('%2F', '/') for f in files if f.endswith('.wiki'))
        for k, it in ITEMS.items():
            if is_pack_relevant(k, it) or group_redirect(k, vanilla=True):
                PAGES_HERE.add(safe(k))
            if it['renamed_vanilla'] and it['vanilla_name'] != k:
                PAGES_HERE.add(safe(it['vanilla_name']))
    return safe(name) in PAGES_HERE


def PAGES_HERE_RESET():
    global PAGES_HERE
    PAGES_HERE = None


def il(name, text=None):
    """{{ItemLink}} that falls back to minecraft.wiki for vanilla items without a page here. The
    text, if given, names a variant of the item ("Arrow of Poison" for a tipped arrow)."""
    label = ('|%s' % esc(text)) if text and text != safe(name) else ''
    if page_exists(name):
        return '{{ItemLink|%s%s}}' % (safe(name), label)
    it = ITEMS.get(name)
    return '{{ItemLink|%s%s|mcw=%s}}' % (safe(name), label, (it or {}).get('vanilla_name') or name)


def stack_cell(s):
    if not s:
        return ''
    ench = ''
    if s.get('enchantments'):
        ench = '<br /><small>%s</small>' % ', '.join(intrinsic_text(e, l) for e, l in s['enchantments'].items())
    return '%s%s%s' % ('%d × ' % s['count'] if s.get('count', 1) > 1 else '', il(s['name'], s.get('variant')), ench)


def trade_ui(t):
    """The offer as the villager's trading screen lists it ({{Trade}})."""
    def st(s):
        return (safe(slot_name(s)) + (',%d' % s['count'] if s.get('count', 1) > 1 else '')) if s else ''
    return '{{Trade|%s|%s|%s}}' % (st(t.get('wants')), st(t.get('additional_wants')), st(t.get('gives')))


def trades_page(prof):
    levels = TRADES[prof]
    names = {'level_1': 'Novice', 'level_2': 'Apprentice', 'level_3': 'Journeyman', 'level_4': 'Expert', 'level_5': 'Master',
             'buying': 'Special offers', 'common': 'Common offers', 'uncommon': 'Uncommon offers'}
    lines = ['{| class="wikitable trade-table"', '! Level !! Offer !! Villager wants !! Villager gives !! Uses !! Villager XP']
    for lk in sorted(k for k in levels if not k.endswith('_meta')):
        ts = levels[lk]
        meta = levels.get(lk + '_meta', {})
        amt = meta.get('amount')
        first = True
        for t in ts:
            want = stack_cell(t['wants'])
            if t.get('additional_wants'):
                want += ' +<br />' + stack_cell(t['additional_wants'])
            lvl = ''
            if first:
                lvl = '! rowspan="%d" | %s%s\n' % (len(ts), names.get(lk, lk), ('<br /><small>%s of %d offered</small>' % (fmt_num(amt), len(ts))) if amt and amt < len(ts) else '')
                first = False
            uses = t.get('max_uses')
            gives = stack_cell(t['gives'])
            if t.get('biome'):
                b = t['biome'] if isinstance(t['biome'], str) else ', '.join(t['biome'])
                gives += '<br /><small>only in %s biomes</small>' % b.replace('#minecraft:', '').replace('spawns_', '').replace('_variant_farm_animals', '').replace('_', ' ')
            lines.append('|-\n%s| %s || %s || %s || %s || %s' % (lvl, trade_ui(t), want, gives,
                                         uses or '', t.get('xp') or ''))
    lines.append('|}')
    return '<includeonly>' + '\n'.join(lines) + '</includeonly><noinclude>Generated from the pack source by <code>tools/generate.py</code>. Do not edit.\n[[Category:Generated data]]</noinclude>'


TRADE_GIVES = defaultdict(list)
TRADE_WANTS = defaultdict(list)
for prof, levels in TRADES.items():
    for lk, ts in levels.items():
        if lk.endswith('_meta'):
            continue
        for t in ts:
            if t['gives']:
                TRADE_GIVES[t['gives']['name']].append((prof, lk, t))
            for k in ('wants', 'additional_wants'):
                if t.get(k):
                    TRADE_WANTS[t[k]['name']].append((prof, lk, t))

LEVEL_NAMES = {'level_1': 'Novice', 'level_2': 'Apprentice', 'level_3': 'Journeyman', 'level_4': 'Expert', 'level_5': 'Master', 'buying': 'Special offer', 'common': 'Common offer', 'uncommon': 'Uncommon offer'}


def prof_link(prof):
    n = PROF.get(prof, prof)
    return '[[%s]]' % n if prof != 'wandering_trader' else '[[Wandering Trader]]'


def sources_page(name):
    parts = []
    srcs = SOURCES.get(name, [])
    if srcs:
        by_cat = defaultdict(list)
        for s in srcs:
            by_cat[s[0]].append(s)
        for cat in ('Chest loot', 'Mob drops', 'Fishing', 'Archaeology', 'Trial spawners', 'Dispensers', 'Decorated pots', 'Mob equipment', 'Gameplay', 'Shearing', 'Harvesting', 'Block drops'):
            if cat not in by_cat:
                continue
            parts.append("\n'''%s'''" % cat)
            # a Variant column when loot functions make distinct items of this one (a tipped arrow's potion)
            variants = any(s[7] for s in srcs)
            parts.append('{| class="wikitable sortable loot-table"\n! Source%s !! Stack size !! Chance !! Notes' % (
                ' !! Variant' if variants else ''))
            agg = {}
            for _, label, lid, p, cnt, notes, rolls, var in by_cat[cat]:
                k = (label, lid, var or '', cnt, tuple(notes))
                agg.setdefault(k, [0, rolls])
                agg[k][0] += p
            plain = ITEMS.get(name, {}).get('name', name)  # the in-game name of a stack with no variant
            for (label, lid, var, cnt, notes), (p, rolls) in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][2])):
                c = ('%s–%s' % (fmt_num(cnt[0]), fmt_num(cnt[1]))) if cnt[0] != cnt[1] else fmt_num(cnt[0])
                parts.append('|-\n| %s%s || %s || %s || %s' % (
                    label.capitalize(), (' || %s' % esc(var or plain)) if variants else '', c,
                    pct(chance_at_least_one(p, rolls)), ', '.join(dict.fromkeys(notes))))
            parts.append('|}')
    tg = TRADE_GIVES.get(name, [])
    if tg:
        parts.append("\n'''Trading'''")
        parts.append('{| class="wikitable trade-table"\n! Villager !! Level !! Offer !! Price !! Quantity')
        for prof, lk, t in tg:
            price = stack_cell(t['wants']) + ((' + ' + stack_cell(t['additional_wants'])) if t.get('additional_wants') else '')
            offer = trade_ui(t) + ('<br /><small>%s</small>' % esc(t['gives']['variant']) if t['gives'].get('variant') else '')
            parts.append('|-\n| %s || %s || %s || %s || %d' % (prof_link(prof), LEVEL_NAMES.get(lk, '—'), offer, price, t['gives'].get('count', 1)))
        parts.append('|}')
    if not parts:
        return None
    note = ('<div style="font-size:90%;margin:0.5em 0">Chance is the probability that a single chest, mob or catch yields at least one, '
            'assuming no Looting, Luck or Fortune.</div>\n') if srcs else ''  # loot tables only, not for trades
    return ('<includeonly>\n' + note + '\n'.join(parts) +
            '</includeonly><noinclude>Generated from the pack source by <code>tools/generate.py</code>. Do not edit.\n[[Category:Generated data]]</noinclude>')


def uses_page(name):
    parts = []
    rs = [r for r in USES.get(name, []) if r['output']['name'] != name or True]
    if rs:
        parts.append(recipe_table(rs, lambda r: out_link(r['output'])))
    tw = TRADE_WANTS.get(name, [])
    if tw:
        parts.append("\n'''Trading'''")
        parts.append('{| class="wikitable trade-table"\n! Villager !! Level !! Offer !! Wants !! Gives')
        for prof, lk, t in tw:
            want = stack_cell(t['wants']) + ((' + ' + stack_cell(t['additional_wants'])) if t.get('additional_wants') else '')
            parts.append('|-\n| %s || %s || %s || %s || %s' % (prof_link(prof), LEVEL_NAMES.get(lk, '—'), trade_ui(t), want, stack_cell(t['gives'])))
        parts.append('|}')
    if not parts:
        return None
    return '<includeonly>' + '\n'.join(parts) + '</includeonly><noinclude>Generated from the pack source by <code>tools/generate.py</code>. Do not edit.\n[[Category:Generated data]]</noinclude>'


# ------------------------------------------------------------------ tables
def food_table():
    rows = []
    for name, it in sorted(ITEMS.items()):
        c = effective(it)
        if not c.get('food') and not (c.get('consumable') and consume_effects(c)):
            continue
        if item_type(it, c) != 'Food':
            continue
        effs = consume_effects(c)
        hp, others = heal_from_effects(effs)
        station = ', '.join(sorted(set(r['station'] for r in producing(name)))) or '—'
        rows.append('|-\n| {{ItemLink|%s}} || data-sort-value="%d" | %s || %s || %s || %s' % (
            safe(name), hp, '{{Hp|%d}}' % hp if hp else '—', '<br />'.join(effect_text(e) for e in others) or '—',
            fmt_num((c.get('consumable') or {}).get('consume_seconds', 1.6)), station))
    return ('<includeonly>{| class="wikitable sortable"\n! Food !! Heals !! Effects !! Eating time (s) !! Made with\n' +
            '\n'.join(rows) + '\n|}</includeonly><noinclude>Generated. [[Category:Generated data]]</noinclude>')


def trim_templates_table():
    """The armor trim templates (all "Smithing Template" in-game), for the Trims article: where the
    pack's loot gives each one and how it is duplicated."""
    rows = []
    for name in sorted(k for k in ITEMS if group_page(k) == 'Trims#Templates'):
        icon = ('<span class="sprite-inline">[[File:%s.png|16px|link=|%s]]</span>&nbsp;' % (safe(name), safe(name))
                if has_icon(name) else '')
        found = {}
        for cat, label, lid, p, cnt, notes, rolls, var in SOURCES.get(name, []):
            k = (label, tuple(dict.fromkeys(notes)))  # conditions such as "player kill" stay with the chance
            found.setdefault(k, [0, rolls])
            found[k][0] += p
        where = ', '.join('%s (%s)' % (label.capitalize(), ', '.join((pct(chance_at_least_one(p, rolls)),) + notes))
                          for (label, notes), (p, rolls) in sorted(found.items())) or '—'
        dup = '<br />'.join(' + '.join(x for x in recipe_ingredients(r).split(' +<br />') if x != '[[%s]]' % name) +
                            (' <small>(pack recipe)</small>' if r['origin'] == 'pack' else '')
                            for r in producing(name)) or '—'  # the template itself is the other ingredient
        rows.append('|-\n| %s%s || %s || %s' % (icon, name, where, dup))
    return ('<includeonly>{| class="wikitable sortable"\n! Template !! Found in (chance per chest or mob) !! Duplicated with\n' +
            '\n'.join(rows) + '\n|}</includeonly><noinclude>Generated. [[Category:Generated data]]</noinclude>')


def renamed_table():
    rows = []
    seen = set()
    for k, v in sorted(DATA['renames'].items(), key=lambda kv: kv[1]['vanilla'] or ''):
        if not (k.startswith('item.minecraft.') or k.startswith('block.minecraft.') or k.startswith('entity.minecraft.villager.')):
            continue
        rid = k.split('.', 2)[-1]
        if not k.startswith('entity.') and ('.' in rid or (rid not in VSUM and rid not in BLOCK_ITEMS)):
            continue  # interface strings such as smithing-template slot descriptions
        if rid.endswith('_spawn_egg'):
            continue  # custom items that borrow a spawn egg id are not renames of the egg
        van, pk = v['vanilla'], v['pack']
        if not pk or (van, pk) in seen or not van:
            continue
        seen.add((van, pk))
        kind = k.split('.')[0].replace('entity', 'villager profession')
        icon = '{{ItemLink|%s}}' % safe(pk) if has_icon(pk) else '[[%s]]' % pk
        rows.append('|-\n| %s || {{MCW|%s}} || <code>%s</code> || %s' % (icon, van, k.split('.', 2)[-1], kind))
    return ('<includeonly>{| class="wikitable sortable"\n! Matcha Flavoured name !! Vanilla name !! ID !! Kind\n' +
            '\n'.join(rows) + '\n|}</includeonly><noinclude>Generated. [[Category:Generated data]]</noinclude>')


def enchantment_table():
    rows = []
    for eid, e in sorted(ENCH.items(), key=lambda kv: ench_name(kv[0])):
        d = e['data']
        van = e.get('vanilla')
        changed = []
        if van:
            for k in ('max_level', 'weight', 'anvil_cost', 'supported_items', 'primary_items', 'exclusive_set', 'slots', 'effects', 'min_cost', 'max_cost'):
                if json.dumps(van.get(k), sort_keys=True) != json.dumps(d.get(k), sort_keys=True):
                    changed.append(k.replace('_', ' '))
        items = d.get('supported_items')
        items_t = ('<code>%s</code>' % items) if isinstance(items, str) else ('%d items' % len(items) if items else '—')
        rows.append('|-\n| %s || <code>%s</code> || %s || %s || %s || %s' % (
            intrinsic_text(eid, 1), eid, d.get('max_level'), ', '.join(d.get('slots', [])), items_t,
            ('Changed: ' + ', '.join(changed)) if changed else ('Unchanged' if van else "'''New'''")))
    return ('<includeonly>{| class="wikitable sortable"\n! Enchantment !! ID !! Max level !! Slots !! Applies to !! Compared with vanilla\n' +
            '\n'.join(rows) + '\n|}</includeonly><noinclude>Generated. [[Category:Generated data]]</noinclude>')


# ------------------------------------------------------------------ equipment comparison tables
# The equipment tiers in the order the Tools, Weapons and Armor pages list them: (item-name prefix, family page).
# Tools and weapons are found by name ("<prefix> <type>"); armor sets by their shared equipment asset.
EQUIPMENT_TIERS = [('Wooden', 'Wooden equipment'), ('Copper', 'Copper equipment'), ('Iron', 'Iron equipment'),
                   ('Steel', 'Steel equipment'), ('Golden', 'Golden equipment'), ('Diamond', 'Diamond equipment'),
                   ('Shakudo', 'Shakudo equipment'), ('Hepatizon', 'Hepatizon equipment'),
                   ('Electrum', 'Electrum equipment'), ('Adamant', 'Adamant equipment'),
                   ('Leather', 'Leather armor'), ('Sturdy Leather', 'Sturdy leather armor'), ('Chainmail', 'Chainmail armor')]
TOOL_TYPES = ['Pickaxe', 'Axe', 'Shovel', 'Hoe', 'Mattock', 'Dolabra']
WEAPON_TYPES = ['Sword', 'Spear', 'Claymore']
ARMOR_SLOTS = [('head', 'Helmet'), ('chest', 'Chestplate'), ('legs', 'Leggings'), ('feet', 'Boots')]
OTHER_ATTRS = {'movement_speed': 'Speed', 'safe_fall_distance': 'Safe fall', 'step_height': 'Step height'}
TOOL_HEAD = '! Item !! Durability !! Mining speed !! Obsidian !! Damage !! Attack speed !! Intrinsics'
WEAPON_HEAD = '! Item !! Durability !! Damage !! Attack speed !! Knockback !! Intrinsics'
ARMOR_HEAD = '! Item !! Durability !! Armor !! Toughness !! Knockback res. !! Other !! Intrinsics'
_BLOCK_TAGS = {}


def block_tag(tag):
    """Block IDs in a block tag: the pack's file merged with vanilla's, unless the pack's replaces it."""
    if tag not in _BLOCK_TAGS:
        ns, p = tag.lstrip('#').split(':') if ':' in tag else ('minecraft', tag.lstrip('#'))
        _BLOCK_TAGS[tag] = out = []
        for base in (os.path.join(ROOT, 'source', 'matcha-flavoured', 'MF_datapack', 'data', ns, 'tags', 'block', p + '.json'),
                     os.path.join(ROOT, 'source', 'vanilla-data', 'data', ns, 'tags', 'block', p + '.json')):
            if os.path.exists(base):
                d = json.load(open(base))
                for v in d['values']:
                    v = v if isinstance(v, str) else v['id']
                    out += block_tag(v) if v.startswith('#') else [v if ':' in v else 'minecraft:' + v]
                if d.get('replace'):
                    break
    return _BLOCK_TAGS[tag]


def obsidian_text(tool):
    """How a tool mines obsidian. The first rule that lists obsidian decides, as in the game."""
    for r in tool.get('rules', []):
        b = r.get('blocks')
        ids = [x for v in ([b] if isinstance(b, str) else b or []) for x in (block_tag(v) if v.startswith('#') else [v])]
        if 'minecraft:obsidian' in ids or 'obsidian' in ids:
            if not r.get('speed') and not r.get('correct_for_drops'):
                break  # only denies drops (a vanilla incorrect_for_* tag): mined like any block the tool isn't for
            speed = fmt_num(r.get('speed') or tool.get('default_mining_speed', 1))
            return 'data-sort-value="%s" | %s' % (speed, speed if r.get('correct_for_drops') else speed + ' (no drops)')
    return 'data-sort-value="0" | —'


def zero_dash(x):
    return fmt_num(x) if x else '—'


def names_link(names):
    """Links for a list of item names; a whole family ("Oak Planks", "Birch Planks", ...) becomes one link."""
    names = list(dict.fromkeys(names))
    if len(names) > 2 and len({n.split()[-1] for n in names}) == 1:
        return '[[%s]]' % names[0].split()[-1]
    return ', '.join('[[%s]]' % n for n in names)


def equipment_cells(name, kind):
    """The comparison-table cells for one tool, weapon or armor piece, from its components."""
    c = effective(ITEMS[name])
    dur = 'Unbreakable' if 'unbreakable' in c else str(c['max_damage']) if c.get('max_damage') else '—'
    intr = '<br />'.join(intrinsic_text(e, lvl) for e, lvl in enchant_levels(c).items()) or '—'
    if kind == 'armor':
        others = []
        for m in c.get('attribute_modifiers', []) or []:
            attr = m.get('type', '').split(':')[-1]
            if attr in ('armor', 'armor_toughness', 'knockback_resistance') or not m.get('amount'):
                continue
            op = m.get('operation', 'add_value')
            val = ('+' if m['amount'] > 0 else '') + fmt_num(m['amount']) if op == 'add_value' else '%+d%%' % round(m['amount'] * 100)
            others.append('%s %s' % (OTHER_ATTRS.get(attr, attr.replace('_', ' ').capitalize()), val))
        vals = [attr_sum(c, a)[0] for a in ('armor', 'armor_toughness', 'knockback_resistance')]
        return [dur] + [zero_dash(v) for v in vals] + ['<br />'.join(others) or '—', intr], vals
    dmg = fmt_num(1 + attr_sum(c, 'attack_damage', 'mainhand')[0])
    spd = fmt_num(4 + attr_sum(c, 'attack_speed', 'mainhand')[0])
    if kind == 'tool':
        tool = c.get('tool') or {}
        mine = mining_speed(tool)
        return [dur, fmt_num(mine) if mine is not None else '—', obsidian_text(tool), dmg, spd, intr], None
    kb = attr_sum(c, 'attack_knockback', 'mainhand')[0]
    return [dur, dmg, spd, ('+' + fmt_num(kb)) if kb else '—', intr], None


def equipment_row(name, kind):
    # a hand-written note for the row (e.g. a <ref>) is passed to the table as |<item name>=...
    return '|-\n| {{ItemLink|%s}}{{{%s|}}} || %s' % (safe(name), safe(name), ' || '.join(equipment_cells(name, kind)[0]))


def equipment_table(head, rows, extra=''):
    return ('<includeonly>{| class="wikitable sortable"\n' + head + '\n' + '\n'.join(rows) + extra +
            '\n|}</includeonly><noinclude>Generated from the items\' components by <code>tools/generate.py</code>. '
            'A hand-written note for a row is passed under the row\'s name (<code>|Steel Helmet=...</code>). '
            '[[Category:Generated data]]</noinclude>')


def armor_sets():
    """{name prefix: [piece names, head to feet]}: armor pieces sharing an equipment asset that cover all four
    slots, in tier order. The prefix is what the pieces' names share ("Leather" for Hood, Pauldron, Pants, Boots)."""
    by_asset = defaultdict(list)
    for name, it in ITEMS.items():
        eq = effective(it).get('equippable') or {}
        if eq.get('slot') in dict(ARMOR_SLOTS) and eq.get('asset_id'):
            by_asset[eq['asset_id']].append((eq['slot'], name))
    order = [s for s, _ in ARMOR_SLOTS]
    sets = {}
    for asset, pieces in by_asset.items():
        if {s for s, _ in pieces} == set(order):
            prefix = ' '.join(os.path.commonprefix([n.split() for _, n in pieces])) or asset.split(':')[-1].title()
            sets[prefix] = [n for _, n in sorted(pieces, key=lambda p: (order.index(p[0]), p[1]))]
    rank = [p for p, _ in EQUIPMENT_TIERS]
    return dict(sorted(sets.items(), key=lambda kv: (rank.index(kv[0]) if kv[0] in rank else len(rank), kv[0])))


def tier_link(prefix):
    page = dict(EQUIPMENT_TIERS).get(prefix)
    return '[[%s|%s]]' % (page, page.rsplit(' ', 1)[0]) if page else prefix


def tiers_table():
    """Tools page: each tier, what its tools are made from (its pickaxe's recipe) and repaired with."""
    rows = []
    for prefix, page in EQUIPMENT_TIERS:
        name = prefix + ' Pickaxe'
        if name not in ITEMS:
            continue
        made = []
        for r in producing(name)[:1]:
            if r['type'].endswith('smithing_transform'):
                base = r['base']['names'][0]
                made.append(' + '.join([base.rsplit(' ', 1)[0] + ' tool'] + [names_link(r[k]['names']) for k in ('template', 'addition') if r.get(k)]))
            else:
                made += [names_link(v['names']) for v in (r.get('key') or {}).values() if v['names'] != ['Stick']]
        rep = (effective(ITEMS[name]).get('repairable') or {}).get('items') or []
        ids = vanilla_tag(rep) if isinstance(rep, str) else rep
        rows.append('|-\n| %s{{{%s|}}} || %s || %s' % (tier_link(prefix), prefix, ', '.join(made) or '—', names_link([id_name(i) for i in ids]) or '—'))
    return equipment_table('! Tier !! Made from !! Repaired with', rows)


def equipment_tables(n):
    """Template:Data/Tools|Weapons|Armor/<type, slot or tier>, Data/Tools/Tiers and Data/Armor/Sets: the stat
    comparisons on the Tools, Weapons, Armor and equipment family pages."""
    def named(prefix, kind_type):
        name = '%s %s' % (prefix, kind_type)
        return name if name in ITEMS and item_type(ITEMS[name], effective(ITEMS[name])) in ('Tool', 'Weapon') else None
    for types, kind, folder, head in ((TOOL_TYPES, 'tool', 'Tools', TOOL_HEAD), (WEAPON_TYPES, 'weapon', 'Weapons', WEAPON_HEAD)):
        for t in types:
            rows = [equipment_row(nm, kind) for nm in (named(p, t) for p, _ in EQUIPMENT_TIERS) if nm]
            write('Template', 'Data/%s/%s' % (folder, t), equipment_table(head, rows)); n['equipment tables'] += 1
        for p, _ in EQUIPMENT_TIERS:
            rows = [equipment_row(nm, kind) for nm in (named(p, t) for t in types) if nm]
            if rows:
                write('Template', 'Data/%s/%s' % (folder, p), equipment_table(head, rows)); n['equipment tables'] += 1
    write('Template', 'Data/Tools/Tiers', tiers_table())
    sets = armor_sets()
    for i, (slot, label) in enumerate(ARMOR_SLOTS):
        rows = [equipment_row(pieces[i], 'armor') for pieces in sets.values()]
        write('Template', 'Data/Armor/' + label, equipment_table(ARMOR_HEAD, rows)); n['equipment tables'] += 1
    set_rows = []
    for prefix, pieces in sets.items():
        totals = [sum(x) for x in zip(*(equipment_cells(nm, 'armor')[1] for nm in pieces))]
        write('Template', 'Data/Armor/' + prefix, equipment_table(ARMOR_HEAD, [equipment_row(nm, 'armor') for nm in pieces],
              '\n|- class="sortbottom"\n! Full set !! !! %s !! %s !! %s !! colspan="2" |' % tuple(zero_dash(v) for v in totals)))
        n['equipment tables'] += 1
        # the notes column is hand-written: what the set is for, which the numbers don't say
        set_rows.append('|-\n| %s || %s || %s || {{{%s|}}}' % (tier_link(prefix), zero_dash(totals[0]), zero_dash(totals[1]), prefix))
    write('Template', 'Data/Armor/Sets', equipment_table('! Set !! Armor !! Toughness !! Notes', set_rows))


ADV = DATA['advancements']


def adv_tab(aid):
    ns, p = aid.split(':')
    return p.split('/')[0]


# Advancement-only icons: models or stacks that no item uses, so there is no icon file for them. The
# table shows the item each one stands for instead.
ADV_ICON_STANDINS = {'matcha:tutorial/cook_secret_food': 'Steamed Golden Carrots',   # model secret_ingredient
                     'matcha:tutorial/cook_secret_meal': 'Golden Carrot Cupcake',    # model secret_meal
                     'matcha:tutorial/preserve_everything': 'Pickled Carrots',       # model pickle_everything
                     'matcha:tutorial/catch_everything': 'Carp',                     # model gay_fish
                     'matcha:tutorial/smith_warding_shield': 'Warding Shield'}       # a shield with banner patterns
# Reward functions in words. None: not a reward for the player (the root's setup is described in prose).
ADV_FUNCTION_REWARDS = {'matcha:mechanics/heart_container/decrease_minimum_hearts': 'Minimum hearts −1',
                        'matcha:mechanics/first_dragon_killed_reward': 'a {{ItemLink|Divine Favor}} and a safe [[surface]]',
                        'matcha:setup/first_load': None}
# Tabs (folders) in the order and under the section titles of the "Advancements" page; a new tab goes last.
ADV_TAB_NAMES = {'tutorial': 'Tutorial', 'hell': 'Hell', 'end': 'The End', 'anglers_almanac': "Angler's Almanac"}


_EXTRA_ICONS = None


def extra_icon(name):
    """Whether tools/images.py draws an icon for name from tools/extra_textures.txt (Elytra, End Portal
    Frame...: vanilla items the pack doesn't define)."""
    global _EXTRA_ICONS
    if _EXTRA_ICONS is None:
        path = os.path.join(ROOT, 'tools', 'extra_textures.txt')
        lines = open(path, encoding='utf-8').read().splitlines() if os.path.exists(path) else []
        _EXTRA_ICONS = {l.partition('=')[2].strip()[:-4] for l in lines if '=' in l and not l.startswith('#')}
    return name in _EXTRA_ICONS


def adv_icon(a):
    icon = a.get('icon') or {}
    name = ADV_ICON_STANDINS.get(a['id']) or icon.get('name', '')
    if icon.get('model') and a['id'] not in ADV_ICON_STANDINS:  # icon drawn with a custom model: the item that owns it
        name = next((k for k, it in ITEMS.items() if icon['model'] in it['models']), None) or name
    return ('{{Slot|%s|link=none}}' % safe(name)) if name and (has_icon(name) or extra_icon(name)) else ''


def adv_rewards(a):
    """The reward cell: loot as "3 {{ItemLink|Obol}}", functions in words (ADV_FUNCTION_REWARDS)."""
    rw = a.get('rewards') or {}
    out = []
    for lid in rw.get('loot') or []:
        rows = flatten(lid)
        if rows and all(p == 1.0 and cnt[0] == cnt[1] for _, p, cnt, *_ in rows):
            out += ['%s %s' % (fmt_num(cnt[0]), il(it, var)) for it, _, cnt, _, _, _, var in rows]
        else:
            out.append('<code>%s</code>' % lid)  # a random reward: name the table
    if rw.get('experience'):
        out.append('%d XP' % rw['experience'])
    if rw.get('recipes'):
        out.append('%d recipe%s' % (len(rw['recipes']), '' if len(rw['recipes']) == 1 else 's'))
    f = rw.get('function')
    if f:
        label = ADV_FUNCTION_REWARDS.get(f, 'runs <code>%s</code>' % f)
        if label:
            out.append(label)
    return '; '.join(out)


def adv_tree_order(advs):
    """Depth-first through a tab's tree, so each branch stays together under its parent. Larger
    branches (the main progression line) come first, ties by title."""
    byid = {a['id']: a for a in advs}
    kids = defaultdict(list)
    for a in advs:
        kids[a.get('parent') if a.get('parent') in byid else None].append(a)
    size = {}

    def count(a):
        if a['id'] not in size:
            size[a['id']] = 1 + sum(count(k) for k in kids[a['id']])
        return size[a['id']]
    out = []

    def walk(parent):
        for a in sorted(kids[parent], key=lambda a: (-count(a), a['title'])):
            out.append(a)
            walk(a['id'])
    walk(None)
    return out


def advancement_tables():
    """Data/Advancements/<tab>: one row per visible advancement, anchored by its title. What the code
    can't say in words (the actual requirements) is a hand note the page passes by advancement ID."""
    tabs = defaultdict(list)
    for aid, a in ADV.items():
        if 'title' in a:
            tabs[adv_tab(aid)].append(a)
    pages = {}
    for tab, advs in tabs.items():
        rows = []
        for a in adv_tree_order(advs):
            parent = ADV.get(a.get('parent') or '', {}).get('title', '')
            kind = a.get('frame', 'task').title()
            if not a.get('parent'):
                kind += ' (root)'
            elif a.get('hidden'):
                kind += ' (hidden)'
            desc = glyphs(esc(a['description'].replace('\n', ' '))).strip()
            rows.append("|-\n| %s || <span id=\"%s\"></span>'''%s''' || %s || %s || {{{%s|}}} || %s || %s{{{%s reward|}}}" % (
                adv_icon(a), html.escape(a['title']), glyphs(esc(a['title'])), desc or '—', esc(parent) or '—',
                a['id'], kind, adv_rewards(a) or '—', a['id']))
        pages[tab] = ('<includeonly>{| class="wikitable sortable"\n'
                      '! Icon !! Advancement !! In-game description !! Parent !! Actual requirements !! Type !! Reward\n' +
                      '\n'.join(rows) + '\n|}</includeonly><noinclude>Generated from the advancement files. The actual '
                      'requirements are notes passed by advancement ID, and "<ID> reward" is appended to the reward: '
                      '<code><nowiki>{{Data/Advancements/%s|matcha:%s/root=...}}</nowiki></code>. '
                      '[[Category:Generated data]]</noinclude>' % (tab, tab))
    return pages


# ------------------------------------------------------------------ stonecutter
# The Stonecutter article lists every stonecutter recipe in groups: the pack's own, then the vanilla ones it keeps.
# Wood types in the article's order; the first is shown expanded, the others collapsed (their sets are near copies).
STONECUTTING_WOODS = ['Oak', 'Spruce', 'Birch', 'Jungle', 'Acacia', 'Dark Oak', 'Mangrove', 'Cherry', 'Pale Oak',
                      'Crimson', 'Warped', 'Bamboo']
STONECUTTING_GROUPS = ['Stone and other', 'Glass', 'Iron and steel', 'Copper', 'Any wood'] + STONECUTTING_WOODS
STONECUTTING_TAG_LABELS = {'minecraft:logs': 'Any log, wood, stem or hyphae'}  # tags too broad to spell out


def stonecutting_wood(name):
    """The wood type a name belongs to, longest match first ("Dark Oak Planks" is Dark Oak, not Oak)."""
    found = [w for w in STONECUTTING_WOODS if re.search(r'(^| )%s( |$)' % w, name)]
    return max(found, key=len) if found else None


def stonecutting_group(r):
    out, ins = r['output']['name'], r['input']['names']
    names = [out] + ins
    if 'Glass' in out:
        return 'Glass'
    if any('Copper' in n for n in names) or 'Lightning Rod' in out:
        return 'Copper'
    if any('Iron' in n or 'Steel' in n for n in names):
        return 'Iron and steel'
    woods = {stonecutting_wood(n) for n in names} - {None}
    if len(woods) == 1:
        return woods.pop()
    if woods:
        return 'Any wood'  # an input tag covering every wood type (barrel, ladder)
    return 'Stone and other'


def stonecutting_rows(recipes):
    """(group, input tag, [input names], output name, count, [recipe ids]). Recipes identical in input, output and count
    (the pack has a few duplicate files) are one row; every duplicate's ID still takes a note."""
    rows = {}
    for r in recipes:
        if r['id'].startswith('debug:'):
            continue
        ins = []
        for n in r['input']['names']:
            if n not in ins:
                ins.append(n)
        key = (tuple(ins), r['output']['name'], r['output'].get('count', 1))
        rows.setdefault(key, (stonecutting_group(r), r.get('input', {}).get('tag'), []))[2].append(r['id'])
    return [(g, tag, ins, out, cnt, sorted(ids)) for (ins, out, cnt), (g, tag, ids) in rows.items()]


def stonecutting_tables(recipes, vanilla, exists):
    """Level-4 sections, one table per group. Every row prints {{{<recipe id>|}}} after its output, so the
    article can add a note to a recipe by its ID. exists(name) says whether the wiki has a page to link."""
    def link(n):
        return '[[%s]]' % n if exists(n) else n

    def inputs(tag, ins):
        if tag in STONECUTTING_TAG_LABELS:
            return STONECUTTING_TAG_LABELS[tag]
        return ' or '.join(link(n) for n in ins)
    groups = defaultdict(list)
    for g, tag, ins, out, cnt, ids in stonecutting_rows(recipes):
        groups[g].append((ins[0], inputs(tag, ins), out, cnt, ids))
    parts = []
    for g in STONECUTTING_GROUPS + sorted(set(groups) - set(STONECUTTING_GROUPS)):
        if g not in groups:
            continue
        collapsed = vanilla or (g in STONECUTTING_WOODS and g != STONECUTTING_WOODS[0])
        lines = ['==== %s ====' % g, '{| class="wikitable sortable%s"' % (' mw-collapsible mw-collapsed' if collapsed else ''),
                 '! Input !! Output !! Count']
        for _, inp, out, cnt, ids in sorted(groups[g], key=lambda x: (
                x[1] not in STONECUTTING_TAG_LABELS.values(), x[0], x[2], x[3], x[1])):  # by first input, then output
            lines.append('|-\n| %s || %s%s || %d' % (inp, link(out), ''.join('{{{%s|}}}' % i for i in ids), cnt))
        lines.append('|}')
        parts.append('\n'.join(lines))
    return ('<includeonly>' + '\n'.join(parts) + '</includeonly><noinclude>Every stonecutter recipe %s, grouped for the '
            '[[Stonecutter]] article. A note for a recipe goes in a parameter named by its ID. Generated from the pack '
            'source by <code>tools/generate.py</code>. Do not edit.\n[[Category:Generated data]]</noinclude>' % (
                'kept from vanilla' if vanilla else 'the pack adds'))


def stonecutting_counts():
    """{{Data/Stonecutting/Count|pack}} and friends: the numbers and the duplicate list the article's prose states."""
    pack = [r for r in ALL_RECIPES if r['station'] == 'Stonecutter' and not r['id'].startswith('debug:')]
    rows = stonecutting_rows(pack)
    dup = sorted(out for g, tag, ins, out, cnt, ids in rows if len(ids) > 1)
    links = ['[[%s|%s]]' % (d, d.lower()) for d in dup]
    dup_text = ' and '.join([', '.join(links[:-1]), links[-1]] if len(links) > 1 else links)
    vals = {'pack': len(pack), 'vanilla': len([r for r in VANILLA_KEPT if r['station'] == 'Stonecutter']),
            'listed': len(rows), 'duplicates': len(pack) - len(rows), 'duplicated': dup_text}
    return ('<includeonly>{{#switch:{{{1|}}}%s}}</includeonly><noinclude>Stonecutter recipe counts for the [[Stonecutter]] '
            'article: <code>pack</code> (recipes the pack adds), <code>vanilla</code> (vanilla recipes kept), '
            '<code>listed</code> (rows in the pack\'s tables, duplicates merged), <code>duplicates</code> (recipes merged '
            'away) and <code>duplicated</code> (the outputs with duplicate recipes, linked). Generated.\n'
            '[[Category:Generated data]]</noinclude>' % ''.join('|%s=%s' % kv for kv in vals.items()))


def advancement_tabs_table():
    """Data/Advancements/tabs: the visible tabs with their roots and sizes. "Unlocked by" is a note
    passed by the root's ID."""
    rows = []
    order = list(ADV_TAB_NAMES)
    roots = [a for a in ADV.values() if 'title' in a and not a.get('parent')]
    for root in sorted(roots, key=lambda a: (order.index(adv_tab(a['id'])) if adv_tab(a['id']) in order else len(order), a['id'])):
        tab = adv_tab(root['id'])
        members = [a for a in ADV.values() if 'title' in a and adv_tab(a['id']) == tab]  # the root counts, as in game
        hidden = sum(1 for a in members if a.get('hidden'))
        size = '%d%s' % (len(members), ' (all hidden)' if hidden and hidden == len(members) else
                         ' (%d hidden)' % hidden if hidden else '')
        name = ADV_TAB_NAMES.get(tab, tab.replace('_', ' ').capitalize())
        bg = re.sub(r'_(bottom|top|side|front)$', '', (root.get('background') or '').split('/')[-1])
        rows.append('|-\n| [[#%s|%s]] || %s %s || %s || {{{%s|}}} || %s' % (
            name, name, adv_icon(root), esc(root['title']), id_name(bg) if bg else '—', root['id'], size))
    return ('<includeonly>{| class="wikitable"\n! Tab !! Root !! Background !! Unlocked by !! Advancements\n' +
            '\n'.join(rows) + '\n|}</includeonly><noinclude>Generated. "Unlocked by" is a note passed by the '
            "root's ID. [[Category:Generated data]]</noinclude>")


def technical_advancements_table():
    """Data/Advancements/technical: advancements without a display (event triggers), counted by
    folder. Each folder's purpose is a note passed by the folder's ID (matcha:recipe_unlocks)."""
    groups = defaultdict(int)
    for aid, a in ADV.items():
        if 'title' not in a:
            ns, p = aid.split(':')
            groups[ns + ':' + p.split('/')[0]] += 1
    rows = []
    for g, n in sorted(groups.items(), key=lambda kv: (-kv[1], kv[0])):
        rows.append('|-\n| <code>%s</code> || %d || {{{%s|}}}' % (g.split(':', 1)[1] if g.startswith('matcha:') else g, n, g))
    total = sum(groups.values())
    rows.append("|-\n| '''Total''' || '''%d''' || Of %d advancement files; the other %d are the visible advancements."
                % (total, len(ADV), len(ADV) - total))
    return ('<includeonly>{| class="wikitable"\n! Folder !! Files !! Purpose\n' + '\n'.join(rows) +
            '\n|}</includeonly><noinclude>Generated. Each folder\'s purpose is a note passed by its ID '
            '(<code>matcha:recipe_unlocks</code>). [[Category:Generated data]]</noinclude>')
# Template:Data/Station/<station>: what a cooking station makes besides food (the articles describe the
# food in prose around {{Recipes}} and the Cooking page).
DYE_COLORS = ('Light Blue', 'Light Gray', 'White', 'Gray', 'Black', 'Brown', 'Red', 'Orange', 'Yellow', 'Lime',
              'Green', 'Cyan', 'Blue', 'Purple', 'Magenta', 'Pink')  # two-word names first


def uncolored(name):
    """'Light Blue Glazed Terracotta' -> 'Glazed Terracotta'; None when the name starts with no dye color."""
    for c in DYE_COLORS:
        if name.startswith(c + ' '):
            return name[len(c) + 1:]
    return None


def pct2(p):
    """A share to two decimals, as the fishing tables give it: 84.85%, 10%, 3.57%."""
    return ('%.2f' % (p * 100)).rstrip('0').rstrip('.') + '%' if p else '—'


def input_cell(ing, most=4):
    """A recipe input in a table cell: item links, a tag's name, or the first few names of a long list."""
    if ing.get('tag') and len(set(ing['names'])) > 1:
        return ing_links(ing)
    names = list(dict.fromkeys(ing['names']))
    if len(names) <= most:
        return ' or '.join(il(n) for n in names)
    rest = names[most - 1:]
    return '%s and <span class="explain" title="%s">%d more</span>' % (
        ', '.join(il(n) for n in names[:most - 1]), ', '.join(rest).replace('"', ''), len(rest))


def station_table(station):
    """Every recipe of one cooking station whose result isn't food, one row each (the row ID, for a hand note,
    is the recipe ID). The same recipe for each dye color (glazed terracotta) collapses into one row."""
    rs = []
    for r in ALL_RECIPES + VANILLA_KEPT:
        out = ITEMS.get(r['output']['name'])
        if r['station'] != station or r['id'].startswith('debug:') or not r.get('input'):
            continue
        if out and item_type(out, effective(out)) == 'Food':
            continue
        rs.append(r)
    if not rs:
        return None
    families = defaultdict(list)
    for r in rs:
        names = set(r['input']['names'])
        base_in = uncolored(r['input']['names'][0]) if len(names) == 1 else None
        base_out = uncolored(r['output']['name'])
        key = (base_in, base_out, cook_ticks(r), r.get('experience'), r['origin'], r['output'].get('count', 1))
        families[key if base_in and base_out else id(r)].append(r)
    rows = []
    for fam in families.values():
        r = fam[0]
        notes = ''.join('{{{%s|}}}' % x['id'] for x in fam)
        if len(fam) >= 8:  # "Any dyed terracotta" -> "the matching glazed terracotta"
            ins = [x['input']['names'][0] for x in fam]
            outs = [x['output']['name'] for x in fam]
            src = '<span class="explain" title="%s">Any dyed %s</span>' % (', '.join(ins), uncolored(ins[0]).lower())
            res = '<span class="explain" title="%s">The matching %s</span>' % (', '.join(outs), uncolored(outs[0]).lower())
            sort = uncolored(outs[0])
        else:
            src = input_cell(r['input'])
            o = r['output']
            res = ('%d × ' % o['count'] if o.get('count', 1) > 1 else '') + il(o['name'], o.get('variant'))
            sort = o['name']
        if r['origin'] != 'pack':
            res += ' <small>(vanilla recipe)</small>'
        t = cook_ticks(r)
        rows.append((sort, src, '|-\n| %s || %s%s || data-sort-value="%d" | %s s || %s' % (
            src, res, notes, t, fmt_num(t / 20), fmt_num(r.get('experience') or 0))))
    rows.sort(key=lambda x: (x[0], x[1]))
    return ('<includeonly>{| class="wikitable sortable"\n! Input !! Output !! Time !! Experience\n' +
            '\n'.join(x[2] for x in rows) + '\n|}</includeonly><noinclude>Generated from the pack source by '
            '<code>tools/generate.py</code>. Do not edit. Hand notes go after the output, keyed by recipe ID: '
            '<code><nowiki>{{Data/Station/%s|%s=...}}</nowiki></code>.\n[[Category:Generated data]]</noinclude>' % (station, rs[0]['id']))


# ------------------------------------------------------------------ splash texts
def splash_key(text):
    """A splash's key for a hand note on the Splash texts page: the text itself, minus the characters a
    template parameter name can't hold."""
    return re.sub(r'[=|{}\[\]<>]', '', text).strip()


def splash_table():
    """The title screen's splashes in file order (Template:Data/Splash texts). A note for a row is passed
    under the splash's text: {{Data/Splash texts|Check out Waxmuffin!=...}}; notes= names the column."""
    sp = DATA.get('splashes')
    if not sp:
        return None
    rows = []
    for i, line in enumerate(sp['lines'], 1):
        text = re.sub('§.', '', line)  # formatting codes (vanilla's rainbow "Colormatic")
        rows.append('|-\n| %d || <nowiki>%s</nowiki> || {{{%s|}}}' % (i, text, splash_key(text)))
    return ('<includeonly>{| class="wikitable sortable"\n! # !! Splash !! {{{notes|Notes}}}\n' + '\n'.join(rows) +
            '\n|}</includeonly><noinclude>Generated from <code>%s</code> by <code>tools/generate.py</code>. Do not edit.\n'
            '[[Category:Generated data]]</noinclude>' % sp['src'])


# ------------------------------------------------------------------ fishing odds (the Fishing article)
# Each catch rolls minecraft:gameplay/fishing once. Its entries are junk, treasure (open water only) and, by
# the biome at the bobber, that biome's own table; Luck of the Sea adds quality × level to each weight.
FISHING = 'minecraft:gameplay/fishing'


def fishing_kind(e):
    """What a top-level fishing entry rolls: 'junk', 'treasure' or 'table' (a biome's own catch)."""
    return {FISHING + '/junk': 'junk', FISHING + '/treasure': 'treasure'}.get(e.get('loot_table'), 'table')


def open_water_only(e):
    return 'in_open_water' in json.dumps(e.get('conditions') or [])


def luck_weight(e, luck):
    """An entry's weight at a luck level, as the game computes it: weight + quality × luck, rounded down, at least 0."""
    return max(int(math.floor(e['weight'] + (e.get('quality') or 0) * luck)), 0)


def fishing_entries():
    ents = [e for e in LOOT[FISHING]['entries'] if not e.get('empty')]
    for e in ents:
        # the odds below know only these; anything else has to be taught to them, not skipped
        other = [c.get('condition') for c in e.get('conditions') or []
                 if c.get('condition', '').split(':')[-1] != 'location_check' and not open_water_only({'conditions': [c]})]
        if other or e.get('pool') != 0 or e.get('rolls') != 1 or e.get('pool_conditions'):
            raise SystemExit('generate.py: %s changed shape (%s); update the fishing odds' % (FISHING, other or 'pools'))
    return ents


def fishing_groups():
    """Biomes grouped by which top-level fishing entries apply in them: [(biome ids, entries)]."""
    ents = fishing_entries()
    groups = defaultdict(list)
    for b in sorted(BIOMES):
        groups[tuple(i for i, e in enumerate(ents) if entry_biomes(e) is None or b in entry_biomes(e))].append(b)
    return [(bs, [ents[i] for i in key]) for key, bs in groups.items()]


def fishing_shapes():
    """fishing_groups() merged where the odds are the same (every climate has junk 10, treasure 5, table 85):
    [(biome ids, entries of one of them)], biomes with a table of their own first."""
    shapes = {}
    for bs, ents in fishing_groups():
        k = tuple(sorted((fishing_kind(e), e['weight'], e.get('quality') or 0, open_water_only(e),
                          entry_biomes(e) is not None) for e in ents))
        shapes.setdefault(k, [[], ents])[0].extend(bs)
    return sorted(shapes.values(), key=lambda s: (not any(fishing_kind(e) == 'table' for e in s[1]), -len(s[0])))


def fishing_odds(entries, luck=0, open_water=True):
    """The share of catches per kind ('junk', 'treasure', 'table') where these entries apply."""
    w = defaultdict(int)
    for e in entries:
        if open_water or not open_water_only(e):
            w[fishing_kind(e)] += luck_weight(e, luck)
    total = sum(w.values()) or 1
    return {k: w[k] / total for k in ('junk', 'treasure', 'table')}


def raw_biomes(e):
    for c in e.get('conditions') or []:
        b = (c.get('predicate') or {}).get('biomes')
        if b:
            return [b] if isinstance(b, str) else b
    return []


def fishing_group_label(bs, ents):
    names = sorted(BIOMES[b] for b in bs)
    if len(bs) <= 3:
        return ', '.join(names)
    if any(fishing_kind(e) == 'table' for e in ents):
        text = 'Biomes with a table of their own'
    else:
        text = 'Other biomes in ' + ', '.join('<code>%s</code>' % r for e in ents for r in raw_biomes(e))
    return '<span class="explain" title="%s">%s</span> (%d)' % (', '.join(names), text, len(bs))


def fishing_luck_table():
    """Junk, treasure and the biome's table per Luck of the Sea level, in and out of open water, for each
    group of biomes with the same odds (Template:Data/Fishing/Luck)."""
    levels = (ENCH.get('minecraft:luck_of_the_sea') or {}).get('data', {}).get('max_level') or 3
    rows = []
    for bs, ents in fishing_shapes():
        for luck in range(levels + 1):
            o, c = fishing_odds(ents, luck), fishing_odds(ents, luck, open_water=False)
            head = ('! rowspan="%d" | %s\n' % (levels + 1, fishing_group_label(bs, ents))) if luck == 0 else ''
            rows.append('|-\n%s| %s || %s || %s || %s || %s || %s' % (
                head, roman(luck) if luck else 'None', pct2(o['junk']), pct2(o['treasure']), pct2(o['table']),
                pct2(c['junk']), pct2(c['table'])))
    return ('<includeonly>{| class="wikitable"\n! rowspan="2" | Biomes !! rowspan="2" | Luck of the Sea !! '
            'colspan="3" | Bobber in open water !! colspan="2" | Not in open water\n|-\n'
            "! Junk !! Treasure !! Biome's table !! Junk !! Biome's table\n" + '\n'.join(rows) +
            '\n|}</includeonly><noinclude>Generated. [[Category:Generated data]]</noinclude>')


def fishing_categories_table():
    """The top-level fishing entries: weight, quality, condition and chance in a climate biome
    (Template:Data/Fishing/Categories)."""
    main = fishing_shapes()[0][1]
    total = sum(e['weight'] for e in main)
    rows = {}
    for e in fishing_entries():
        key = (fishing_kind(e), entry_biomes(e) is not None, e['weight'], e.get('quality') or 0, open_water_only(e))
        rows.setdefault(key, []).append(e)
    out = []
    for (kind, gated, w, q, ow), es in rows.items():
        label = {'junk': '[[Fishing junk|Junk]]', 'treasure': '[[Fishing treasure|Treasure]]',
                 'table': "Fish (the biome's table)"}[kind] + (' (fallback)' if gated and kind == 'junk' else '')
        conds = []
        if ow:
            conds.append('The bobber is in open water')
        if gated and kind == 'table':
            conds.append('The bobber is in a biome that has a table (%d entries)' % len(es))
        elif gated:
            conds.append('The bobber is in a biome of ' + ', '.join('<code>%s</code>' % r for x in es for r in raw_biomes(x)))
        # in a climate biome only one table entry applies at a time
        here = any(any(x is m for m in main) for x in es)
        out.append('|-\n| %s || %d || %s || %s || %s' % (
            label, w, ('+%d' % q) if q > 0 else str(q).replace('-', '−'), '; '.join(conds) or 'Always',
            pct2(w / total) if here else '—'))
    return ('<includeonly>{| class="wikitable"\n! Category !! Weight !! Quality !! Condition !! Chance with no luck<br />'
            '<small>(in a biome with its own table)</small>\n' + '\n'.join(out) +
            '\n|}</includeonly><noinclude>Generated. [[Category:Generated data]]</noinclude>')


def fish_stars(name):
    """A fish's rarity line (⭐⭐☆☆) and its number of stars, from the first lore line; ('', 0) for other catches."""
    lore = ((ITEMS.get(name) or {}).get('components') or {}).get('lore') or []
    return (lore[0], lore[0].count('⭐')) if lore and '⭐' in lore[0] else ('', 0)


def sells_for(name):
    """What villagers pay for a caught item: "12 → 1 Obol (Apprentice)"."""
    out = []
    for prof, lk, t in TRADE_WANTS.get(name, []):
        if t.get('additional_wants') or not t.get('gives') or t['wants']['name'] != name:
            continue
        out.append('%d → %d %s (%s%s)' % (t['wants'].get('count', 1), t['gives'].get('count', 1), il(t['gives']['name']),
                                          LEVEL_NAMES.get(lk, lk), '' if prof == 'fisherman' else ', ' + PROF.get(prof, prof)))
    return '<br />'.join(out) or '—'


def fishing_tables():
    """Each biome's own catch table: {table id: {'biomes': [...], 'climate': picked by a biome tag}}."""
    out = {}
    for e in fishing_entries():
        if fishing_kind(e) != 'table':
            continue
        t = out.setdefault(e['loot_table'], {'biomes': [], 'climate': False})
        t['biomes'] += [b for b in entry_biome_list(e) or [] if b not in t['biomes']]
        t['climate'] |= any(r.startswith('#') for r in raw_biomes(e))
    return out


def table_chances(tid, open_water=True):
    """The chances that a catch comes from table tid, over the biomes that roll it (one value for a climate)."""
    vals = set()
    for bs, ents in fishing_groups():
        use = [e for e in ents if open_water or not open_water_only(e)]
        mine = sum(e['weight'] for e in use if e.get('loot_table') == tid)
        if mine:
            vals.add(round(mine / sum(e['weight'] for e in use), 12))
    return sorted(vals)


def catch_rows(tid):
    """(row id, item, count, variant, weight, share of the table) for each catch in a biome table."""
    ents = [e for e in LOOT[tid]['entries'] if not e.get('empty')]
    total = sum(e['weight'] for e in ents) or 1
    rows = []
    for e in ents:
        if e.get('item'):
            rows.append((e.get('id') or e['item'], e['item'], count_range(e.get('count')), e.get('variant'),
                         e['weight'], e['weight'] / total))
        elif isinstance(e.get('loot_table'), str):
            for it, p2, cnt, _, _, _, var in flatten(e['loot_table']):
                rows.append((e['loot_table'], it, cnt, var, e['weight'], e['weight'] / total * p2))
    return rows


def catch_table(tids, biome_column):
    """A fish table: rarity, weight, share and chance per catch in and out of open water, and the price.
    A hand note goes after the catch, keyed by the entry's loot table or item ID."""
    # rowspans (the biome column) don't survive sorting
    lines = ['{| class="wikitable%s"' % ('' if biome_column else ' sortable'),
             '! %sFish !! Rarity !! Weight !! Share of table !! Per catch (open water) !! '
             'Per catch (other water) !! Sells for' % ('Biome !! ' if biome_column else '')]
    for tid in tids:
        rows = catch_rows(tid)
        chances = (table_chances(tid), table_chances(tid, open_water=False))
        for i, (rid, it, cnt, var, w, share) in enumerate(rows):
            line, stars = fish_stars(it)
            n = ('%s–%s × ' % (fmt_num(cnt[0]), fmt_num(cnt[1]))) if cnt[0] != cnt[1] else (
                '%s × ' % fmt_num(cnt[0]) if cnt[0] != 1 else '')
            per = ['–'.join(pct2(share * v) for v in vals) or '—' for vals in chances]
            head = ''
            if biome_column and i == 0:
                head = '! rowspan="%d" | %s\n' % (len(rows), ', '.join(BIOMES[b] for b in fishing_tables()[tid]['biomes']))
            lines.append('|-\n%s| %s%s{{{%s|}}} || data-sort-value="%d" | %s || %d || %s || %s || %s || %s' % (
                head, n, il(it, var), rid, stars, line or '—', w, pct2(share), per[0], per[1], sells_for(it)))
    lines.append('|}')
    return '\n'.join(lines)


def fishing_rarity_table():
    """How the climates' fish are laid out by rarity (Template:Data/Fishing/Rarity)."""
    per = defaultdict(lambda: defaultdict(set))
    climates = [tid for tid, t in fishing_tables().items() if t['climate']]
    for tid in climates:
        rows = catch_rows(tid)
        total = sum(e['weight'] for e in LOOT[tid]['entries'] if not e.get('empty'))
        count = defaultdict(int)
        for rid, it, cnt, var, w, share in rows:
            line, stars = fish_stars(it)
            if not stars:
                continue
            count[stars] += 1
            d = per[stars]
            d['line'].add(line)
            d['weight'].add('%d of %d' % (w, total))
            d['chance'].update(pct2(share * v) for v in table_chances(tid))
            for prof, lk, t in TRADE_WANTS.get(it, []):
                if t.get('gives') and not t.get('additional_wants'):
                    d['price'].add(str(t['wants'].get('count', 1)))
                    d['level'].add(LEVEL_NAMES.get(lk, lk))
        for s, c in count.items():
            per[s]['count'].add(str(c))
    out = []
    for s in sorted(per):
        d = per[s]
        out.append('|-\n| %s || %s || %s || %s || %s || %s' % tuple(
            ', '.join(sorted(d[k])) or '—' for k in ('line', 'count', 'weight', 'chance', 'price', 'level')))
    return ('<includeonly>{| class="wikitable"\n! Rarity !! Fish per climate !! Weight each !! Chance per catch (each fish) !! '
            'Fish needed for 1 Obol !! Fisherman level\n' + '\n'.join(out) +
            '\n|}</includeonly><noinclude>Generated. [[Category:Generated data]]</noinclude>')


def fishing_pages():
    """Template:Data/Fishing/...: the odds tables of the Fishing article."""
    pages = {'Categories': fishing_categories_table(), 'Luck': fishing_luck_table(), 'Rarity': fishing_rarity_table()}
    tables = fishing_tables()
    for tid, t in tables.items():
        if t['climate']:
            pages[tid.split('/')[-1]] = ("<includeonly>'''Biomes:''' %s.\n%s</includeonly><noinclude>Generated from "
                                         "<code>%s</code>. [[Category:Generated data]]</noinclude>" % (
                                             ', '.join(BIOMES[b] for b in t['biomes']), catch_table([tid], False), tid))
    special = [tid for tid, t in tables.items() if not t['climate']]
    if special:
        pages['Special biomes'] = ('<includeonly>%s</includeonly><noinclude>Generated. [[Category:Generated data]]'
                                   '</noinclude>' % catch_table(special, True))
    return pages


# ------------------------------------------------------------------ stubs & redirects
def is_pack_relevant(name, item):
    comps = item['components']
    if not item['renamed_vanilla']:
        return True  # custom item defined by the pack
    if item['vanilla_name'] != name:
        return True  # renamed vanilla item
    if any(r['origin'] == 'pack' for r in producing(name)):
        return True
    if TRADE_GIVES.get(name):
        return True
    return False


def group_page(name):
    """Article that documents a family of items together (the item gets a redirect)."""
    if name.endswith(' Map'):
        return 'Explorer maps'
    if name.startswith('Bulk '):
        return 'Bulk blocks'
    if name.startswith('Music Disc ('):
        return 'Music Disc'
    if name.endswith(' Armor Trim Smithing Template'):
        return 'Trims#Templates'  # all "Smithing Template" in-game; one table there (Data/Trim templates)
    return None


VANILLA_GROUPS = {'Trims'}  # families whose unchanged vanilla members redirect too (not just the pack's)


def group_redirect(name, vanilla=False):
    """Redirect text to the article that documents name's family, if that article exists."""
    group = group_page(name)
    if group and vanilla and group.split('#')[0] not in VANILLA_GROUPS:
        return None
    if group and hand_exists('Main', group.split('#')[0]):
        return '#REDIRECT [[%s]]\n[[Category:Redirects to lists]]' % group
    return None


def stub_article(name, item):
    c = effective(item)
    t = item_type(item, c)
    article = 'an' if t[0] in 'AEIOU' else 'a'
    kind = ('[[%s|%s]]' % ({'Food': 'Food', 'Armor': 'Armor', 'Tool': 'Tools', 'Weapon': 'Weapons', 'Block': 'Blocks',
                            'Equipment': 'Equipment'}[t], t.lower())) if t != 'Item' else 'item'  # there is no "Items" page
    lead = "'''%s''' is %s %s added by [[Matcha Flavoured]]." % (name, article, kind)
    hat = ''
    if item['renamed_vanilla'] and item['vanilla_name'] != name:
        lead = "'''%s''' is %s %s. It is the vanilla %s, renamed by [[Matcha Flavoured]]." % (
            name, article, t.lower(), '{{MCW|%s}}' % item['vanilla_name'])
        hat = '{{Vanilla|%s}}\n' % item['vanilla_name']
    elif item['renamed_vanilla']:
        lead = ("'''%s''' is %s %s from vanilla ''Minecraft''. [[Matcha Flavoured]] keeps the item but adds or changes "
                "how it is made or found; the tables below list the pack's recipes, sources and uses. See {{MCW|%s}} for everything else." % (
                    name, article, t.lower(), item['vanilla_name'] or name))
        hat = '{{Vanilla}}\n'
        body = [hat + '{{Infobox auto}}', lead, '']
        return finish_stub(name, item, t, body)
    stub = '' if item['renamed_vanilla'] else '{{Stub}}\n'  # renamed vanilla items are fully described by the data
    body = [hat + stub + '{{Infobox auto}}', lead, '']
    return finish_stub(name, item, t, body)


def finish_stub(name, item, t, body):
    if producing(name) or SOURCES.get(name) or TRADE_GIVES.get(name):
        body.append('== Obtaining ==')
        if producing(name):
            body.append('{{Recipes}}')
        if SOURCES.get(name) or TRADE_GIVES.get(name):
            body.append('{{Sources}}')
        body.append('')
    if USES.get(name) or TRADE_WANTS.get(name):
        body.append('== Usage ==\n{{Uses}}\n')
    cat = {'Food': 'Food', 'Armor': 'Armor', 'Tool': 'Tools', 'Weapon': 'Weapons', 'Block': 'Blocks', 'Equipment': 'Equipment', 'Item': 'Items'}[t]
    body.append('[[Category:%s]]' % cat)
    if item['renamed_vanilla'] and item['vanilla_name'] != name:
        body.append('[[Category:Renamed items]]')
    return '\n'.join(body)


# ------------------------------------------------------------------ status effects
def effect_sources():
    src = defaultdict(list)  # effect name -> [(kind, item/enchantment, level, duration text, sort)]
    for name, it in ITEMS.items():
        c = effective(it)
        effs = consume_effects(c)
        if effs:
            hp, others = heal_from_effects(effs)
            for e in others:
                d = e.get('duration', 0)
                src[effect_name(e['id'])].append(('Food' if item_type(it, c) == 'Food' else 'Consumable', name,
                                                  e.get('amplifier', 0) + 1, ticks(d) if d >= 0 else '∞', d, e.get('probability', 1)))
    for eid, e in ENCH.items():
        blob = json.dumps(e.get('effects') or {})
        for m in re.finditer(r'"to_apply": "([a-z_:]+)"', blob):
            key = eid.split(':')[-1]
            intrinsic = eid.startswith('matcha:') and any(key.startswith(k) for k, _ in INTRINSIC_PAGES)
            # intrinsics have glyph-only names and no page of their own: link them like the infobox does
            src[effect_name(m.group(1))].append(('Intrinsic' if intrinsic else 'Enchantment', intrinsic_text(eid, 1) if intrinsic else '[[%s]]' % ench_name(eid),
                                                 None, 'while active', 10 ** 9, 1))
    return src


def effect_pages(n):
    src = effect_sources()
    overview = ['{| class="wikitable sortable"', '! Effect !! Sources in Matcha Flavoured']
    for eff, rows in sorted(src.items()):
        lines = ['{| class="wikitable sortable"', '! Source !! Kind !! Level !! Duration']
        seen = set()
        for kind, what, lvl, dur, sortv, prob in sorted(rows, key=lambda r: (r[0], -r[4], r[1])):
            key = (kind, what, lvl, dur)
            if key in seen:
                continue
            seen.add(key)
            link = what if kind in ('Enchantment', 'Intrinsic') else '{{ItemLink|%s}}' % safe(what)
            lines.append('|-\n| %s || %s || %s || data-sort-value="%d" | %s%s' % (
                link, kind, roman(lvl) if lvl else '—', sortv, dur, (' (%d%% chance)' % round(prob * 100)) if prob < 1 else ''))
        lines.append('|}')
        write('Template', 'Data/Effect/' + eff, '<includeonly>' + '\n'.join(lines) + '</includeonly><noinclude>Generated. [[Category:Generated data]]</noinclude>')
        overview.append('|-\n| {{EffectLink|%s}} || %d' % (eff, len(seen)))
        n['effects'] += 1
        if not hand_exists('Main', eff):
            write('Main', eff, (
                '{{Vanilla}}\n{{Infobox|title=%s|image=Effect %s.png|imagesize=64px|type=[[Effect|Status effect]]}}\n'
                "'''%s''' is a [[effect|status effect]]. In [[Matcha Flavoured]] it is granted by the following foods, "
                'items and [[intrinsic]]s.\n\n== Sources ==\n{{Data/Effect/%s}}\n\n[[Category:Effects]]') % (eff, eff, eff, eff))
    overview.append('|}')
    write('Template', 'Data/Effects', '<includeonly>' + '\n'.join(overview) + '</includeonly><noinclude>Generated. [[Category:Generated data]]</noinclude>')


# ------------------------------------------------------------------ case redirects
def case_redirects(n):
    """MediaWiki only ignores the case of a title's first letter, so prose links written in
    lowercase ("[[mud kiln]]", as minecraft.wiki style asks) need "Mud kiln" -> "Mud Kiln"."""
    titles = set()
    for base in (os.path.join(GEN, 'Main'), os.path.join(HAND, 'Main')):
        if os.path.isdir(base):
            titles.update(f[:-5].replace('%2F', '/') for f in os.listdir(base) if f.endswith('.wiki'))
    lower = {t.lower() for t in titles}
    for t in sorted(titles):
        if ' ' not in t or '/' in t:
            continue
        variant = t[0] + t[1:].lower()
        if variant == t or variant in titles:
            continue
        if variant.lower() in lower and variant not in titles and sum(1 for x in titles if x.lower() == variant.lower()) > 1:
            continue  # ambiguous: two pages differ only by case
        write('Main', variant, '#REDIRECT [[%s]]\n[[Category:Redirects from other capitalisations]]' % t)
        titles.add(variant)
        n['case redirects'] += 1


# ------------------------------------------------------------------ categories
CATEGORY_TEXT = {
    'Generated data': 'Data pages generated from the pack source by <code>tools/generate.py</code>. They are transcluded into articles and are not meant to be read on their own.',
    'Stubs': 'Articles generated from the pack data that have no written description yet.',
    'Redirects from vanilla names': 'Vanilla names that redirect to the renamed item in Matcha Flavoured.',
    'Renamed items': 'Vanilla items and blocks that Matcha Flavoured renames.',
    'Redirects from variants': 'Variants of an item that look different in game (a Smithing Trim Color\'s material, a Cooking Recipe\'s dish), redirecting to the item.',
}


def category_pages(n):
    cats = set()
    for base in (GEN, HAND):
        for root, _, files in os.walk(base):
            for f in files:
                try:
                    txt = open(os.path.join(root, f), encoding='utf-8').read()
                except Exception:
                    continue
                for m in re.finditer(r'\[\[Category:([^\]|]+)', txt):
                    cats.add(m.group(1).strip())
    for c in sorted(cats):
        if '{' in c or hand_exists('Category', c):
            continue
        text = CATEGORY_TEXT.get(c, 'This category contains pages about %s in [[Matcha Flavoured]].' % (c[0].lower() + c[1:]))
        write('Category', c, text + '\n__EXPECTUNUSEDCATEGORY__')
        n['categories'] += 1


# ------------------------------------------------------------------ tooltips
RARITY_COLORS = {'uncommon': 'FFFF55', 'rare': '55FFFF', 'epic': 'FF55FF'}


def lua_str(s):
    return json.dumps(s, ensure_ascii=False)


def tooltip_data():
    """Module:Tooltip/Data: what each item's in-game tooltip shows. Name colour (explicit, else the
    rarity's), the in-game name where it differs from the page, and the lore lines as styled runs,
    glyphs included. Plus each custom-font glyph's width, as the game measures bitmap glyphs."""
    import images  # the glyph metrics come from the same font texture the images are cut from
    def desc_line(iid):
        # the grey line under the name of items that share it (smithing templates, banner patterns)
        k = 'item.minecraft.%s.new' % iid.split(':')[-1]
        if iid.split(':')[-1] in DATA['distinct_names'] and (LANG.get(k) or VANILLA_LANG.get(k)):
            return [[re.sub('§.', '', LANG.get(k) or VANILLA_LANG.get(k)).strip(), 'AAAAAA', '']]
        return None
    entries = {}
    for key, it in ITEMS.items():
        c = effective(it)
        own = it['components']
        color = own.get('name_color') or RARITY_COLORS.get(c.get('rarity'), '')
        lines = [[r for r in line if r[0]] for line in own.get('lore_rich') or []]
        if not own.get('lore_rich') and it['renamed_vanilla'] and desc_line(it['base_id']):
            lines = [desc_line(it['base_id'])]
        title = it['name'] if it['name'] != key else ''
        if color or title or any(lines):
            entries[safe(key)] = (title, color, lines)
    for label, v in VARIANT_ITEMS.items():  # each variant's own lore under its label (slot_name)
        own = v['components']
        color = own.get('name_color') or RARITY_COLORS.get(effective(ITEMS[v['item']]).get('rarity'), '')
        lines = [[r for r in line if r[0]] for line in own.get('lore_rich') or []]
        entries[safe(label)] = (ITEMS[v['item']]['name'], color, lines)
    for iid, comps in VSUM.items():
        color = RARITY_COLORS.get(comps.get('minecraft:rarity'), '')
        name = safe(id_name(iid))
        if (color or desc_line(iid)) and name not in entries:
            title = re.sub('§.', '', VANILLA_LANG.get('item.minecraft.' + iid, '')) if desc_line(iid) else ''
            entries[name] = (title if title != name else '', color, [desc_line(iid)] if desc_line(iid) else [])
    out = ['-- Generated by tools/generate.py from item components in the pack\'s source. Do not edit.',
           '-- items[name] = { t = in-game name if not the page name, c = name colour, l = lore lines of',
           '--   { text, colour, flags } runs }; glyphs[codepoint] = width in font pixels.',
           'return {', '\titems = {']
    for name in sorted(entries):
        title, color, lines = entries[name]
        parts = []
        if title:
            parts.append('t = %s' % lua_str(title))
        if color:
            parts.append('c = %s' % lua_str(color))
        if lines:
            parts.append('l = { %s }' % ', '.join(
                '{ %s }' % ', '.join('{ %s, %s, %s }' % (lua_str(t), lua_str(col), lua_str(fl)) for t, col, fl in line)
                for line in lines))
        out.append('\t\t[%s] = { %s },' % (lua_str(name), ', '.join(parts)))
    out.append('\t},')
    out.append('\tglyphs = { %s },' % ', '.join('[%d] = %d' % kv for kv in sorted(images.glyph_widths().items())))
    out.append('}')
    return '\n'.join(out)


# ------------------------------------------------------------------ main
def main():
    if os.path.isdir(GEN):
        shutil.rmtree(GEN)
    os.makedirs(GEN)
    n = defaultdict(int)
    for name, item in ITEMS.items():
        title = safe(name)
        if not title or title.startswith('item.kleispack') or title.startswith('adv.'):
            continue
        item['_key'] = name
        write('Template', 'Data/Infobox/' + title, infobox(item)); n['infobox'] += 1
        p = recipes_page(name)
        if p:
            write('Template', 'Data/Recipes/' + title, p); n['recipes'] += 1
        p = uses_page(name)
        if p:
            write('Template', 'Data/Uses/' + title, p); n['uses'] += 1
        p = sources_page(name)
        if p:
            write('Template', 'Data/Sources/' + title, p); n['sources'] += 1
        if is_pack_relevant(name, item) and not hand_exists('Main', title):
            if group_redirect(name):
                write('Main', title, group_redirect(name)); n['group redirects'] += 1
            else:
                write('Main', title, stub_article(name, item)); n['stubs'] += 1
    # ingredients that only ever appear inside recipes (never as an item stack) still get a Uses table
    for name in list(USES):
        title = safe(name)
        if name in ITEMS or not title or title.startswith(('Any ', 'item.')):
            continue
        p = uses_page(name)
        if p:
            write('Template', 'Data/Uses/' + title, p); n['ingredient-only uses'] += 1
            if not hand_exists('Main', title):
                write('Main', title, '{{Vanilla}}\n' + ("'''%s''' is an item from vanilla ''Minecraft'' that [[Matcha Flavoured]] does not change. "
                      "See {{MCW|%s}} on the Minecraft Wiki; this page lists only where the pack uses it.\n\n== Usage ==\n{{Uses}}\n\n[[Category:Vanilla items]]") % (name, name))
                n['vanilla pages'] += 1

    # vanilla items the pack uses but doesn't change: a short page pointing at minecraft.wiki,
    # with the pack's own recipes and uses (so every link in a recipe table goes somewhere)
    for name, item in ITEMS.items():
        title = safe(name)
        if not title or hand_exists('Main', title) or is_pack_relevant(name, item) or title.startswith(('item.', 'adv.')):
            continue
        if group_redirect(name, vanilla=True):
            write('Main', title, group_redirect(name, vanilla=True)); n['group redirects'] += 1
            continue
        if not (producing(name) or USES.get(name) or SOURCES.get(name) or TRADE_GIVES.get(name) or TRADE_WANTS.get(name)):
            continue
        body = ['{{Vanilla}}\n{{Infobox auto}}',
                "'''%s''' is an item from vanilla ''Minecraft'' that [[Matcha Flavoured]] does not change. "
                "See {{MCW|%s}} on the Minecraft Wiki for everything about it; this page lists only where it appears in the pack." % (
                    name, item['vanilla_name'] or name), '']
        if producing(name):
            body.append('== Obtaining ==\n{{Recipes}}\n')
        if SOURCES.get(name) or TRADE_GIVES.get(name):
            if not producing(name):
                body.append('== Obtaining ==')
            body.append('{{Sources}}\n')
        if USES.get(name) or TRADE_WANTS.get(name):
            body.append('== Usage ==\n{{Uses}}\n')
        body.append('[[Category:Vanilla items]]')
        write('Main', title, '\n'.join(body)); n['vanilla pages'] += 1
    PAGES_HERE_RESET()

    # redirects: vanilla name -> renamed item
    for name, item in ITEMS.items():
        vn = item['vanilla_name']
        if item['renamed_vanilla'] and vn != name and safe(vn) and safe(vn).lower() != safe(name).lower() and not hand_exists('Main', safe(vn)) and safe(vn) not in ITEMS:
            write('Main', safe(vn), '#REDIRECT [[%s]]\n[[Category:Redirects from vanilla names]]' % safe(name)); n['redirects'] += 1
    for prof in TRADES:
        write('Template', 'Data/Trades/' + PROF.get(prof, prof.replace('_', ' ').title()), trades_page(prof)); n['trades'] += 1
    for lid in LOOT:
        # every table gets a data page (articles may show any of them); only the Sources lists
        # are limited to world sources by loot_category()
        if True:
            p = loot_table_page(lid)
            if p:
                write('Template', 'Data/Loot/' + lid.replace(':', '/'), p); n['loot'] += 1
    write('Template', 'Data/Food table', food_table())
    write('Template', 'Data/Renamed items', renamed_table())
    write('Template', 'Data/Trim templates', trim_templates_table())
    write('Template', 'Data/Enchantments', enchantment_table())
    equipment_tables(n)
    cooking = ('smelting', 'smoking', 'blasting', 'campfire_cooking')
    for station in sorted({r['station'] for r in ALL_RECIPES if r['type'].split(':')[-1] in cooking}):
        p = station_table(station)
        if p:
            write('Template', 'Data/Station/' + station, p); n['station tables'] += 1
    p = splash_table()
    if p:
        write('Template', 'Data/Splash texts', p)
        write('Template', 'Data/Splash texts/Count', '<includeonly>%d</includeonly><noinclude>Number of splash texts '
              'in the resource pack. Generated.</noinclude>' % len(DATA['splashes']['lines']))
    for k, page in fishing_pages().items():
        write('Template', 'Data/Fishing/' + k, page); n['fishing tables'] += 1
    for tab, page in advancement_tables().items():
        write('Template', 'Data/Advancements/' + tab, page); n['advancement tabs'] += 1
    write('Template', 'Data/Advancements/tabs', advancement_tabs_table())
    write('Template', 'Data/Advancements/technical', technical_advancements_table())
    m = DATA['meta']
    ver = re.search(r'(\d+(?:\.\d+)+)', m['pack_description'].replace('Matcha Flavoured DP', ''))
    write('Template', 'Data/Current version', '<includeonly>%s</includeonly><noinclude>Pack version in <code>pack.mcmeta</code> at the synced commit. Generated.</noinclude>' % (ver.group(1) if ver else '?'))
    write('Template', 'Source/commit', '<includeonly>%s</includeonly><noinclude>Commit of kleiwright/matcha-flavoured this wiki was generated from (%s). Generated.</noinclude>' % (m['git_head'], m['git_date']))
    # aliases module: static + tag aliases collected while rendering recipes
    lua = ['-- Generated by tools/generate.py from item tags used in the pack\'s recipes. Do not edit.', 'local aliases = {']
    for k in sorted(ALIASES):
        lua.append('\t[%s] = { %s },' % (json.dumps(k), ', '.join(json.dumps(safe(x)) for x in ALIASES[k])))
    lua.append('}\nreturn aliases')
    write('Module', 'Inventory slot/Aliases', '\n'.join(lua))
    write('Module', 'Tooltip/Data', tooltip_data())
    # One redirect per tag; the sentence-case variant is synthesised by build_xml.collect. Existence is
    # checked case-insensitively so Linux and macOS (case-insensitive) produce the same files.
    taken = {f.lower() for f in os.listdir(os.path.join(GEN, 'Main'))} | {f.lower() for f in os.listdir(os.path.join(HAND, 'Main'))}
    for k, members in sorted(ALIASES.items()):
        t = k[len('Any '):]
        if members and fname(t).lower() not in taken:
            write('Main', t, '#REDIRECT [[%s]]\n[[Category:Redirects from item tags]]' % safe(members[0]))
            taken.add(fname(t).lower())
            n['tag redirects'] += 1
    # a variant with its own look is shown in slots under its label (slot_name), which leads to its item
    for label, v in sorted(VARIANT_ITEMS.items()):
        if fname(label).lower() not in taken:
            write('Main', label, '#REDIRECT [[%s]]\n[[Category:Redirects from variants]]' % safe(v['item']))
            taken.add(fname(label).lower())
            n['variant redirects'] += 1
    effect_pages(n)
    category_pages(n)  # (capitalisation redirects are synthesised by build_xml.collect, not written as files)
    # after every article and redirect is written, so the tables link exactly the names that have a page
    titles = {f[:-5].replace('%2F', '/') for d in (os.path.join(GEN, 'Main'), os.path.join(HAND, 'Main'))
              for f in os.listdir(d) if f.endswith('.wiki')}
    write('Template', 'Data/Stonecutting/Pack', stonecutting_tables(
        [r for r in ALL_RECIPES if r['station'] == 'Stonecutter'], False, titles.__contains__))
    write('Template', 'Data/Stonecutting/Vanilla', stonecutting_tables(
        [r for r in VANILLA_KEPT if r['station'] == 'Stonecutter'], True, titles.__contains__))
    write('Template', 'Data/Stonecutting/Count', stonecutting_counts())
    # swap in the new tree in one step so concurrent readers never see a half-written folder
    old = GEN_FINAL + '.old'
    if os.path.isdir(old):
        shutil.rmtree(old)
    if os.path.isdir(GEN_FINAL):
        os.rename(GEN_FINAL, old)
    os.rename(GEN, GEN_FINAL)
    shutil.rmtree(old, ignore_errors=True)
    print(dict(n))


if __name__ == '__main__':
    import fcntl
    os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
    with open(os.path.join(ROOT, 'build', '.generate.lock'), 'w') as _lock:
        fcntl.flock(_lock, fcntl.LOCK_EX)  # the dev watcher and manual runs must not overlap
        main()
