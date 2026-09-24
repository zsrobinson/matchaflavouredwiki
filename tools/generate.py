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
  Data/Food table, Data/Renamed items, Data/Trim templates, Data/Advancements/<tab>
  Data/Enchantments, Data/Enchantments/New, Data/Enchantments/Vanilla   enchantment lists (notes by enchantment id)
  Data/Blessings, Data/Ofuda, Data/Intrinsic items/<page>   enchanted books and the items that carry intrinsics
  Data/Current version, Source/commit
  Module:Inventory slot/Aliases   tag names ("Any Planks") for recipe slots
  Module:Tooltip/Data     each item's in-game tooltip (name colour, lore runs) and glyph widths
  Main/<item>              stub article for every item that has no hand-written page
  Main/<vanilla name>      redirect from each vanilla name to its renamed item
"""
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
    return re.sub(r'⟦([^⟧]+)⟧', lambda m: '{{G|%s}}' % m.group(1), s)


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
    if tool:
        rules = [r for r in tool.get('rules', []) if r.get('speed') and r.get('correct_for_drops') is not False and r.get('speed') < 1000]
        mineable = [r['speed'] for r in rules if isinstance(r.get('blocks'), str) and 'mineable/' in r['blocks']]
        speeds = mineable or [r['speed'] for r in rules if 'cobweb' not in json.dumps(r.get('blocks'))]
        if speeds:
            f['miningspeed'] = fmt_num(max(speeds))
    for attr, key in (('armor', 'armor'), ('armor_toughness', 'toughness'), ('knockback_resistance', 'knockbackres')):
        v, has = attr_sum(c, attr)
        if has and v:
            f[key] = fmt_num(v if attr != 'knockback_resistance' else v * 10)
    rep = c.get('repairable')
    if rep and rep.get('items') and c.get('max_damage') and not c.get('unbreakable'):
        f['repair'] = item_link_list(rep['items'])
    ench = {}
    for k in ('enchantments', 'stored_enchantments'):
        v = c.get(k) or {}
        if isinstance(v, dict) and 'levels' in v:
            v = v['levels']
        ench.update(v)
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
        secs = (r.get('cookingtime') or {'smelting': 200, 'smoking': 100, 'blasting': 100, 'campfire_cooking': 600}[t]) / 20
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


def flatten(table_id, prob=1.0, notes=(), depth=0, seen=()):
    """Yield (item, per-roll prob of this entry in context, count range, notes, rolls, table, variant)
    for a table. The variant labels a stack that a loot function makes distinct ("Arrow of Poison")."""
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
        pools[e['pool']].append(e)
    for pi, ents in pools.items():
        e0 = ents[0]
        pmult, pnotes = cond_notes(e0.get('pool_conditions'))
        # Entries gated by a location (biome) check are mutually exclusive: only one applies
        # at a time, so each is weighed against the unconditioned entries alone.
        def is_loc(e):
            return any((c.get('condition', '').split(':')[-1] == 'location_check') for c in (e.get('conditions') or []))
        # children of one alternatives/group entry share that entry's single weighted slot
        slots = {}
        for e in ents:
            slots.setdefault(e.get('slot') or id(e), e)
        uncond = sum(e['weight'] for e in slots.values() if not is_loc(e))
        locw = [e['weight'] for e in slots.values() if is_loc(e)]
        earlier = defaultdict(list)  # alternatives slot -> condition notes of the children before this one
        ravg, rlo, rhi = rolls_avg(e0['rolls'])
        for e in ents:
            emult, enotes = cond_notes(e.get('conditions'))
            if e.get('slot_kind') == 'alternatives':
                prior = earlier[e['slot']]
                earlier[e['slot']] = prior + enotes
                if prior and not enotes:
                    enotes = ['without ' + ', '.join(dict.fromkeys(prior))]  # the fallback branch
            total = (uncond + e['weight']) if is_loc(e) else (uncond + (max(locw) if locw else 0))
            p = e['weight'] / (total or 1) * emult * pmult
            if e.get('empty'):
                continue
            n = list(notes) + pnotes + enotes
            if 'loot_table' in e:
                sub = e['loot_table']
                if isinstance(sub, dict):
                    continue
                override = count_range(e['count']) if e.get('count') is not None else None
                for (it, p2, cnt, n2, r2, tid, var) in flatten(sub, 1.0, (), depth + 1, seen + (table_id,)):
                    # nested table: chance per roll of this entry times the nested chance (per nested roll)
                    if override:
                        cnt, p2 = override, p2 * positive_share(override)
                    out.append((it, p * p2 * prob, cnt, n + n2, (rlo, rhi), table_id, var))
            elif 'item' in e and e['item']:
                cr = count_range(e.get('count'))
                out.append((e['item'], p * prob * positive_share(cr), cr, n, (rlo, rhi), table_id, e.get('variant')))
    return out


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


# ------------------------------------------------------------------ enchantment tables
# Data/Enchantments/New (the pack's own enchantments), Data/Enchantments/Vanilla (what the pack changed
# and where each one comes from) and Data/Enchantments (every enchantment file, intrinsics and old ids
# included). Hand-written text the code can't give (what an enchantment does, remarks on a change) is
# passed by the page as a note keyed by enchantment id: {{Data/Enchantments/New|matcha:reach=...}}.
ENCH_UPDATES = {k: e['updated_to'] for k, e in ENCH.items() if e.get('updated_to')}  # old id -> the id it becomes
EQUIPMENT_KINDS = ['sword', 'spear', 'axe', 'pickaxe', 'shovel', 'hoe', 'helmet', 'chestplate', 'leggings', 'boots']
ARMOR_KINDS = {'helmet', 'chestplate', 'leggings', 'boots'}
RANDOM_BOOKS = {'#minecraft:on_random_loot': '[[Enchanting#Other sources|Random chest and fishing books]]'}
LOOT_PLACES = [('chests/abbey/', '[[Abbey]] chests'), ('chests/ancient_city', '[[Ancient City|Ancient city]] chests'),
               ('chests/bastion_', '[[Bastion Remnant|Bastion]] chests'),
               ('chests/trial_chambers/reward_ominous', '[[Trial Chambers|Ominous vaults]]'),
               ('chests/trial_chambers/reward', '[[Trial Chambers|Trial chamber vaults]]'),
               ('gameplay/piglin_bartering', '{{MCW|Bartering|Piglin bartering}}'), ('gameplay/fishing', '[[Fishing]]')]


def item_enchantments(item):
    """An item's enchantments. Equipment keeps them as stored_enchantments until it reaches an inventory
    (matcha:mechanics/intrinsic_enchants makes them real enchantments)."""
    c = item.get('components') or {}
    return dict(c.get('stored_enchantments') or {}, **(c.get('enchantments') or {}))


def is_intrinsic(eid):
    key = eid.split(':')[-1]
    return eid.startswith('matcha:') and any(key.startswith(k) for k, _ in INTRINSIC_PAGES)


def ench_article(name):
    """The wiki's own article about an enchantment, if it has one (not a redirect to this list)."""
    f = os.path.join(HAND, 'Main', fname(name))
    return os.path.exists(f) and not open(f, encoding='utf-8').read().lstrip().upper().startswith('#REDIRECT')


def ench_link(eid):
    """An enchantment's name, linked to its article here or, for vanilla ones without one, to minecraft.wiki."""
    if eid in ENCH_UPDATES:
        return '%s (old id)' % ench_link(ENCH_UPDATES[eid])
    if is_intrinsic(eid):
        return intrinsic_text(eid, 1)
    name = ench_name(eid)
    return '[[%s]]' % name if ench_article(name) or not eid.startswith('minecraft:') else '{{MCW|%s}}' % name


def level_text(eid, lvl):
    e = ENCH.get(ENCH_UPDATES.get(eid, eid)) or {}
    return ' (%s)' % roman(lvl) if eid.startswith('minecraft:') or (e.get('max_level') or 1) > 1 else ''


def item_kind(iid):
    k = iid.split(':')[-1]
    return next((x for x in EQUIPMENT_KINDS if k.endswith('_' + x)), None)


def item_ref(iid):
    """A link to a vanilla item id's page here, or to minecraft.wiki when the wiki has none."""
    name = id_name(iid)
    return '[[%s]]' % name if page_exists(name) else '{{MCW|%s}}' % name


def and_list(parts):
    return parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + ' and ' + parts[-1]


def applies_to(ids, limit=None):
    """Item ids as readable groups: "Swords (not golden) and stick". None when there are more than limit groups."""
    parts = []
    for kind in EQUIPMENT_KINDS:
        have = sorted(i.split(':')[-1] for i in ids if item_kind(i) == kind)
        if not have:
            continue
        every = sorted(k for k in VSUM if item_kind(k) == kind)
        plural = kind if kind.endswith('s') else kind + 's'
        missing = [k[:-len(kind) - 1].replace('_', ' ') for k in every if k not in have]
        if not missing:
            parts.append(plural)
        elif len(missing) <= 3 and len(missing) < len(have):
            parts.append('%s (not %s)' % (plural, ' or '.join(missing)))
        else:
            parts.append('%s %s' % (and_list([k[:-len(kind) - 1].replace('_', ' ') for k in have]), plural))
    parts += [id_name(i).lower() for i in ids if not item_kind(i)]
    if not parts or (limit and len(parts) > limit):
        return None
    s = and_list(parts)
    return s[0].upper() + s[1:]


def world_loot_entries():
    """(world table, entry) for every item entry a world loot table can yield, nested tables included."""
    out = []

    def walk(lid, root, seen):
        for e in LOOT.get(lid, {}).get('entries', []):
            sub = e.get('loot_table')
            if isinstance(sub, str):
                if sub not in seen:
                    walk(sub, root, seen | {sub})
            elif e.get('item'):
                out.append((root, e))
    for lid in LOOT:
        if not loot_category(lid) or lid in REFERENCED or (lid.startswith('minecraft:gameplay/fishing/') and lid not in ROLLED):
            continue  # the same world tables the Sources lists use
        walk(lid, lid, {lid})
    return out


def loot_place(lid):
    p = lid.split(':')[-1]
    label = next((label for pre, label in LOOT_PLACES if p.startswith(pre)), None)
    if label:
        return label
    s = p.split('/')[-1].replace('_', ' ')
    return s[0].upper() + s[1:] + (' chests' if p.startswith('chests/') else '')


def family_key(name):
    return name.rsplit(' ', 1)[0] if ' ' in name else None


def family_members(key):
    return {n for n, it in ITEMS.items() if n.startswith(key + ' ') and item_kind(it['base_id'])}


def gear_text(entries, always_level):
    """Equipment that comes with an enchantment, as [(item, level, suffix)]. Items of one family ("Adamant
    Helmet", "Adamant Boots"...) are merged into one entry linked to the family's article."""
    def lv(levels):
        levels = sorted(set(levels))
        if not always_level and all(l == 1 for l in levels):
            return ''
        return ' (%s)' % (roman(levels[0]) if len(levels) == 1 else '%s–%s' % (roman(levels[0]), roman(levels[-1])))
    fams = defaultdict(list)
    for name, l, suffix in entries:
        if not suffix and family_key(name) and len([1 for n, _, s in entries if not s and family_key(n) == family_key(name)]) > 1:
            fams[family_key(name)].append((name, l))
    out = []
    for key, members in sorted(fams.items()):
        names = {n for n, _ in members}
        page = next((c for p in (key + ' equipment', key + ' armor') for c in (p, p[0] + p[1:].lower())
                     if os.path.exists(os.path.join(HAND, 'Main', fname(c)))), None)
        kinds = {item_kind(ITEMS[n]['base_id']) for n in names}
        if kinds == ARMOR_KINDS and len(names) == 4:
            text = '%s armor' % key
        elif names == family_members(key):
            text = '%s equipment' % key
        else:
            text = None
        if text:
            text = text[0] + text[1:].lower()
            out.append(('[[%s]]' % page if page == text else '[[%s|%s]]' % (page, text) if page else text) + lv(l for _, l in members))
        else:
            pieces = and_list([n[len(key) + 1:].lower() for n in sorted(names)])
            out.append('%s %s' % ('[[%s|%s]]' % (page, key) if page else key, pieces) + lv(l for _, l in members))
    for name, l, suffix in sorted(entries):
        if not suffix and family_key(name) in fams:
            continue
        out.append('[[%s]]%s%s' % (name, lv([l]), suffix))
    return list(dict.fromkeys(out))


def enchantment_sources():
    """eid -> {'books': [...], 'gear': [(item, level, suffix)], 'found': [...]}: the crafted and traded
    books that hold each enchantment, the equipment that comes with it and the loot books it is found in.
    A book holding an old id (main:reach, see ENCH_UPDATES) counts for the enchantment it turns into."""
    src = defaultdict(lambda: {'books': [], 'gear': [], 'found': []})

    def add(stack, how):
        for eid, lvl in (stack.get('enchantments') or {}).items():
            target = ENCH_UPDATES.get(eid, eid)
            if stack['id'] == 'minecraft:enchanted_book':
                label = '[[%s]]' % stack['name'] + (': %s' % stack['lore'] if how != 'recipe' and stack.get('lore') else '')
                old = ' ([[Blessing#Old enchantment ids|as <code>%s</code>]])' % eid if eid != target else ''
                src[target]['books'].append(label + level_text(target, lvl) + old)
            else:
                src[target]['gear'].append((stack['name'], lvl, how))
    for r in ALL_RECIPES:
        add(r['output'], 'recipe')
    for prof, levels in TRADES.items():
        for lk, ts in levels.items():
            for t in ts if isinstance(ts, list) else []:
                if t.get('gives'):
                    add(t['gives'], ' from the %s' % prof_link(prof))
    for name, it in ITEMS.items():  # equipment no recipe or trade makes (defined by loot alone)
        for eid, lvl in (item_enchantments(it) if it['base_id'] != 'minecraft:enchanted_book' else {}).items():
            if not any(n == name for n, _, _ in src[ENCH_UPDATES.get(eid, eid)]['gear']):
                src[ENCH_UPDATES.get(eid, eid)]['gear'].append((name, lvl, 'recipe'))
    for root, e in world_loot_entries():
        if e['id'] == 'minecraft:enchanted_book':
            frm = e.get('enchant_from')
            for eid in e.get('enchant_options') or []:
                src[eid]['found'].append((isinstance(frm, str) and RANDOM_BOOKS.get(frm)) or loot_place(root))
            for eid in e.get('enchantments') or {}:
                src[eid]['found'].append(loot_place(root))
        else:
            own = item_enchantments(ITEMS.get(e['item'], {}))
            for eid, lvl in (e.get('enchantments') or {}).items():
                if own.get(eid) != lvl:  # a loot variant (the Abbey's iron swords with Anemos)
                    src[eid]['gear'].append((e['item'], lvl, ' in %s' % loot_place(root)))
    for s in src.values():
        s['books'] = list(dict.fromkeys(s['books']))
        s['gear'] = [(n, l, '' if h == 'recipe' else h) for n, l, h in dict.fromkeys(s['gear'])]
        s['found'] = sorted(set(s['found']), key=lambda x: (x not in RANDOM_BOOKS.values(), x))
    return src


def num(x):
    """JSON with integral floats as ints, so 3.0 and 3 compare equal."""
    if isinstance(x, float) and x == int(x):
        return int(x)
    if isinstance(x, dict):
        return {k: num(v) for k, v in x.items()}
    if isinstance(x, list):
        return [num(v) for v in x]
    return x


def ench_ref(eid):
    """An enchantment named in running text; an intrinsic also says which equipment carries it."""
    if not is_intrinsic(eid):
        return ench_link(eid)
    carriers = sorted(n for n, it in ITEMS.items() if eid in item_enchantments(it) and it['base_id'] != 'minecraft:enchanted_book')
    if not carriers:
        return ench_link(eid)
    keys = sorted({family_key(n) or n for n in carriers})
    kinds = {item_kind(ITEMS[n]['base_id']) for n in carriers}
    what = 'armor' if kinds <= ARMOR_KINDS else 'tools' if kinds <= {'axe', 'pickaxe', 'shovel', 'hoe'} else 'equipment'
    owners = (and_list([k.lower() for k in keys]) + ' ' + what) if len(carriers) > 1 else and_list([c.lower() for c in carriers])
    return '%s (%s)' % (ench_link(eid), owners)


def enchantment_changes(eid):
    """What the pack changed in a vanilla enchantment: [(short name, line)], substantive changes in bold."""
    e = ENCH[eid]
    d, van = num(e['data']), num(e['vanilla'])
    lines = []
    if d.get('anvil_cost') != van.get('anvil_cost'):
        lines.append(('anvil cost', 'Anvil cost %s → %s' % (van.get('anvil_cost'), d.get('anvil_cost'))))
    if d.get('max_level') != van.get('max_level'):
        lines.append(('max level', "'''Maximum level %s → %s'''" % (roman(van.get('max_level')), roman(d.get('max_level')))))
    for ids, other, text in ((e['items'], e['vanilla_items'], 'Also applies to %s'), (e['vanilla_items'], e['items'], 'No longer applies to %s')):
        extra = [i for i in ids if i not in other]
        if extra:
            lines.append(('supported items', "'''%s'''" % text % and_list([item_ref(i) for i in extra])))
    for ids, other, text in ((e['incompatible'], e['vanilla_incompatible'], 'Also incompatible with %s'),
                             (e['vanilla_incompatible'], e['incompatible'], 'No longer incompatible with %s')):
        extra = [i for i in ids if i not in other]
        if extra:
            lines.append(('incompatibilities', "'''%s'''" % text % and_list([ench_ref(i) for i in extra])))
    if json.dumps(d.get('effects'), sort_keys=True) != json.dumps(van.get('effects'), sort_keys=True):
        lines.append(('effects', "'''Effects changed'''"))
    known = {'anvil_cost', 'max_level', 'supported_items', 'exclusive_set', 'effects', 'description'}
    other = [k.replace('_', ' ') for k in sorted(set(d) | set(van)) if k not in known and d.get(k) != van.get(k)]
    if other:
        lines.append((', '.join(other), 'Changed: %s' % ', '.join(other)))
    return lines


def note(eid):
    """A hand-written note the page passes for this row, on a line of its own (tools/lint_pages.py
    checks that the page passes notes only for rows that exist)."""
    return '{{#if:{{{%s|}}}|<br />{{{%s}}}}}' % (eid, eid)


def stored_text(ench):
    """A book's enchantments as its tooltip lists them, linked; an old id (see ENCH_UPDATES) is named
    as the enchantment it turns into."""
    out = []
    for eid, lvl in ench.items():
        target = ENCH_UPDATES.get(eid, eid)
        e = ENCH.get(target) or {}
        if is_intrinsic(target):
            out.append(intrinsic_text(target, lvl) + (' ' + roman(lvl) if (e.get('max_level') or 1) > 1 else ''))
            continue
        old = ' ([[Blessing#Old enchantment ids|as <code>%s</code>]])' % eid if eid != target else ''
        out.append(ench_link(target) + (' ' + roman(lvl) if (e.get('max_level') or 1) > 1 else '') + old)
    return ', '.join(out)


def book_tables():
    """Data/Blessings (every book crafted around a Hell-Bound Book) and Data/Ofuda (every enchanted
    book a villager sells), with the enchantments each one stores."""
    rows = []
    for r in sorted(ALL_RECIPES, key=lambda r: r['output']['name']):
        o = r['output']
        t = r['type'].split(':')[-1]
        if o['id'] != 'minecraft:enchanted_book' or not o.get('enchantments') or t not in ('crafting_shaped', 'crafting_shapeless'):
            continue
        ings = [r['key'][ch] for row in r['pattern'] for ch in row if ch != ' '] if t == 'crafting_shaped' else r['ingredients']
        book = next((g for g in ings if g['names'] == ['Hell-Bound Book']), None)
        if not book:
            continue
        ings.remove(book)
        tally = defaultdict(int)
        for g in ings:
            tally[ing_links(g)] += 1
        parts = ['%s%s' % ('%d × ' % n if n > 1 else '', s) for s, n in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))]
        rows.append('|-\n| %s || %s || %s' % (il(o['name']), stored_text(o['enchantments']), ', '.join(parts)))
    end = '\n|}</includeonly><noinclude>Generated by <code>tools/generate.py</code>. [[Category:Generated data]]</noinclude>'
    blessings = ('<includeonly>{| class="wikitable sortable"\n! Blessing !! Stored enchantments !! Ingredients around the book\n' +
                 '\n'.join(rows) + end)
    rows = []
    for prof, levels in TRADES.items():
        for lk, ts in sorted(levels.items()):
            for t in ts if isinstance(ts, list) else []:
                g = t.get('gives') or {}
                if g.get('id') != 'minecraft:enchanted_book' or not g.get('enchantments'):
                    continue
                price = ' + '.join(('%d × ' % s['count'] if s.get('count', 1) > 1 else '') + il(s['name'])
                                   for s in (t.get('wants'), t.get('additional_wants')) if s)
                rows.append('|-\n| %s || %s || %s || %s || %s' % (prof_link(prof), LEVEL_NAMES.get(lk, '—'), price,
                                                                  g.get('lore') or '—', stored_text(g['enchantments'])))
    ofuda = ('<includeonly>{| class="wikitable"\n! Villager !! Level !! Price !! Prayer !! Stored enchantments\n' + '\n'.join(rows) + end)
    return {'Data/Blessings': blessings, 'Data/Ofuda': ofuda}


SLOT_TEXT = {'mainhand': 'Main hand', 'offhand': 'Off hand', 'hand': 'Main hand or off hand', 'armor': 'Worn',
             'head': 'Worn', 'chest': 'Worn', 'legs': 'Worn', 'feet': 'Worn', 'body': 'Worn', 'any': 'Held or worn'}


def intrinsic_item_tables():
    """Data/Intrinsic items/<page>: the items that come with each intrinsic documented on that page
    (INTRINSIC_PAGES), with the level their tooltip shows and where the item must be to work."""
    pages = defaultdict(list)
    for name, it in ITEMS.items():
        if it['base_id'] == 'minecraft:enchanted_book':
            continue
        ench = item_enchantments(it)
        for eid, lvl in ench.items():
            key = eid.split(':')[-1]
            page = next((p for k, p in INTRINSIC_PAGES if key.startswith(k)), None) if is_intrinsic(eid) else None
            if not page:
                continue
            e = ENCH.get(eid) or {}
            where = ' or '.join(dict.fromkeys(SLOT_TEXT.get(s, s) for s in e.get('slots') or []))
            where = 'Main hand or off hand' if where == 'Main hand or Off hand' else where
            others = [stored_text({o: l}) for o, l in ench.items() if o != eid]
            raw = e.get('name') or ''
            label = glyphs(raw).strip() if raw and 'kleispack.' not in raw else INTRINSIC_LABELS.get(key, key.replace('_', ' ').capitalize())
            label += ' ' + roman(lvl) if (e.get('max_level') or 1) > 1 else ''  # the tooltip line
            pages[page.split('#')[0]].append(((e.get('max_level') or 1, key, name), '|-\n| %s || %s%s || %s' % (
                il(name), label, ' (and %s)' % and_list(others) if others else '', where)))
    end = '\n|}</includeonly><noinclude>Generated by <code>tools/generate.py</code>. [[Category:Generated data]]</noinclude>'
    return {'Data/Intrinsic items/' + page: '<includeonly>{| class="wikitable sortable"\n! Item !! Intrinsic !! Where it works\n' +
            '\n'.join(r for _, r in sorted(rows)) + end for page, rows in pages.items()}


def enchantment_tables():
    """Template title -> text for the three enchantment tables."""
    src = enchantment_sources()
    new, vanilla, full = [], [], []
    def order(kv):  # by name, each old id after the enchantment it becomes; intrinsics (glyph names) last
        eid = ENCH_UPDATES.get(kv[0], kv[0])
        return is_intrinsic(eid), eid.split(':')[-1] if is_intrinsic(eid) else ench_name(eid), kv[0] in ENCH_UPDATES
    for eid, e in sorted(ENCH.items(), key=order):
        s = src.get(eid, {'books': [], 'gear': [], 'found': []})
        maxl = roman(e['max_level'])
        if e.get('vanilla'):
            changes = enchantment_changes(eid)
            vanilla.append('|-\n| <span id="%s"></span>%s || %s || %s%s || %s || %s || %s' % (
                ench_name(eid), ench_link(eid), maxl, '<br />'.join(t for _, t in changes) or 'None', note(eid),
                '<br />'.join(s['books']) or "''None''", '<br />'.join(gear_text(s['gear'], True)) or '—',
                '<br />'.join(s['found']) or '—'))
            compared = ('Changed: ' + ', '.join(k for k, _ in changes)) if changes else 'Unchanged'
        else:
            compared = "'''New'''"
            if eid.startswith('matcha:') and not is_intrinsic(eid):
                got = s['books'] + gear_text(s['gear'], e['max_level'] > 1) + s['found']
                new.append('|-\n| %s || %s || %s || %s || %s' % (
                    ench_link(eid), maxl, applies_to(e['items']) or '—', '{{{%s|}}}' % eid, '<br />'.join(got) or '—'))
        full.append('|-\n| %s || <code>%s</code> || %s || %s || %s || %s' % (
            ench_link(eid), eid, e['max_level'], ', '.join(e.get('slots') or []),
            applies_to(e['items'], 6) or '<code>%s</code>' % e['supported_items'], compared))
    end = '\n|}</includeonly><noinclude>Generated by <code>tools/generate.py</code>. Notes are passed by enchantment id. [[Category:Generated data]]</noinclude>'
    return {
        'Data/Enchantments/New': '<includeonly>{| class="wikitable sortable"\n! Enchantment !! Max level !! Applies to !! Effect !! Obtained from\n' + '\n'.join(new) + end,
        'Data/Enchantments/Vanilla': ('<includeonly>{| class="wikitable sortable"\n! Enchantment !! Max level !! Changes from vanilla !! Crafted or traded as '
                                      '!! Comes on !! Found as\n' + '\n'.join(vanilla) + end),
        'Data/Enchantments': ('<includeonly>{| class="wikitable sortable"\n! Enchantment !! ID !! Max level !! Slots !! Applies to !! Compared with vanilla\n' +
                              '\n'.join(full) + end),
    }


ADV = DATA['advancements']


def adv_tab(aid):
    ns, p = aid.split(':')
    return p.split('/')[0]


def advancement_tables():
    tabs = defaultdict(list)
    for aid, a in ADV.items():
        if 'title' not in a:
            continue
        tabs[adv_tab(aid)].append(a)
    pages = {}
    for tab, advs in tabs.items():
        byid = {a['id']: a for a in advs}

        def depth(a, d=0):
            p = a.get('parent')
            return depth(byid[p], d + 1) if p in byid and d < 50 else d
        rows = []
        for a in sorted(advs, key=lambda a: (depth(a), a['title'])):
            icon = a.get('icon') or {}
            iname = safe(icon.get('name', '')) if icon else ''
            if icon.get('model'):  # icon drawn with a custom model: find the item that owns it
                owner = next((k for k, it in ITEMS.items() if icon['model'] in it['models']), None)
                if owner:
                    iname = safe(owner)
            parent = ADV.get(a.get('parent') or '', {}).get('title', '')
            frame = a.get('frame', 'task')
            rw = a.get('rewards') or {}
            rtxt = []
            if rw.get('loot'):
                rtxt.append(', '.join('<code>%s</code>' % l for l in rw['loot']))
            if rw.get('experience'):
                rtxt.append('%d XP' % rw['experience'])
            if rw.get('recipes'):
                rtxt.append('%d recipe(s)' % len(rw['recipes']))
            if rw.get('function'):
                rtxt.append('runs <code>%s</code>' % rw['function'])
            rows.append('|-\n| %s || %s || %s || %s || %s || %s || %s' % (
                ('{{Slot|%s|link=none}}' % iname) if iname and has_icon(icon.get('name', '')) else '',
                "'''%s'''" % esc(glyphs(a['title'])), esc(glyphs(a['description']).replace('\n', ' ')), esc(parent), frame.title(),
                'Yes' if a.get('hidden') else '', '; '.join(rtxt)))
        pages[tab] = ('<includeonly>{| class="wikitable sortable"\n! Icon !! Advancement !! Description !! Parent !! Frame !! Hidden !! Reward\n' +
                      '\n'.join(rows) + '\n|}</includeonly><noinclude>Generated. [[Category:Generated data]]</noinclude>')
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
    for title, text in list(enchantment_tables().items()) + list(book_tables().items()) + list(intrinsic_item_tables().items()):
        write('Template', title, text)
    for tab, page in advancement_tables().items():
        write('Template', 'Data/Advancements/' + tab, page); n['advancement tabs'] += 1
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
