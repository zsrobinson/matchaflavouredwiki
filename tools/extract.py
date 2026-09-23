#!/usr/bin/env python3
"""Extract Matcha Flavoured source data into build/data.json.

Reads the official pack (source/matcha-flavoured) and vanilla 26.x data
(source/vanilla-data, source/vanilla-assets) and normalises everything the
wiki needs: an item registry keyed by English display name, recipes, villager
trades, loot tables, enchantments and advancements.

Every generated wiki fact traces back to a file path recorded here as `src`.
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


def vname(item_id):
    """English name of a (possibly renamed) vanilla item id."""
    iid = item_id.split(':', 1)[-1] if ':' in item_id else item_id
    for k in ('item.minecraft.' + iid, 'block.minecraft.' + iid):
        if k in LANG:
            return strip_codes(LANG[k]).strip()
    return iid.replace('_', ' ').title()


def vanilla_name(item_id):
    iid = item_id.split(':', 1)[-1]
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
                n = '%s of %s' % (vname(base), n)  # e.g. the Chemist's "Darkness" splash potion
            return n
    sid = norm_id(stack['id']).split(':')[-1]
    if sid.startswith('music_disc_') and not comps:
        song = LANG.get('jukebox_song.minecraft.' + sid[len('music_disc_'):])
        if song:
            return '%s (%s)' % (vname(sid), strip_codes(song).strip())  # vanilla discs all share one name
    pc = comps.get('minecraft:potion_contents')
    if isinstance(pc, dict) and pc.get('custom_name'):
        base = norm_id(stack['id']).split(':')[-1]
        k = 'item.minecraft.%s.effect.%s' % (base, pc['custom_name'])
        if k in LANG:
            return strip_codes(LANG[k]).strip()
    return vname(stack['id'])


def item_key(stack):
    comps = stack.get('components', {}) or {}
    name = stack_name(stack)
    named = comps.get('minecraft:item_name') or comps.get('minecraft:custom_name')
    model = comps.get('minecraft:item_model')
    if not named and model and model in MODEL_OWNER:
        name = MODEL_OWNER[model]  # model-only stack (e.g. a trade asking for an electrum item)
    model = comps.get('minecraft:item_model')
    return name, model


def variant_key(name, comps):
    """Items that share one name in-game but are distinct (blessings, clay fetishes)."""
    lore = comps.get('minecraft:lore') or []
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
    sid = norm_id(stack['id'])
    comps = stack.get('components', {}) or {}
    name, model = item_key(stack)
    key = variant_key(name, comps)
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


def display_stack(stack):
    if isinstance(stack, str):
        return {'name': vname(stack), 'id': norm_id(stack), 'count': 1}
    comps = stack.get('components') or {}
    d = {'name': variant_key(item_key(stack)[0], comps), 'id': norm_id(stack['id']), 'count': stack.get('count', 1)}
    if comps.get('minecraft:item_model'):
        d['model'] = comps['minecraft:item_model']
    if comps.get('minecraft:stored_enchantments'):
        d['enchantments'] = comps['minecraft:stored_enchantments']
    if comps.get('minecraft:enchantments'):
        d['enchantments'] = comps['minecraft:enchantments']
    return d


# ---------------------------------------------------------------- tags
def load_tags(kind):
    tags = {}
    for base, ns_root in ((VDATA, 'minecraft'),):
        for f in glob.glob(os.path.join(base, 'tags', kind, '**', '*.json'), recursive=True):
            t = 'minecraft:' + os.path.relpath(f, os.path.join(base, 'tags', kind))[:-5]
            tags[t] = load(f)['values']
    for f in glob.glob(os.path.join(DP, '*', 'tags', kind, '**', '*.json'), recursive=True):
        ns = os.path.relpath(f, DP).split(os.sep)[0]
        t = ns + ':' + os.path.relpath(f, os.path.join(DP, ns, 'tags', kind))[:-5]
        d = load(f)
        vals = [v if isinstance(v, str) else v['id'] for v in d['values']]
        if d.get('replace') or t not in tags:
            tags[t] = vals
        else:
            tags[t] = tags[t] + vals
    return tags


ITEM_TAGS = load_tags('item')


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
    r = {'type': t, 'station': STATION.get(t, t), 'src': src, 'origin': origin, 'id': None}
    res = d.get('result')
    if isinstance(res, str):
        res = {'id': res}
    if res is None:
        return None
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

# ---------------------------------------------------------------- loot tables
def walk_entries(entries, pool_ctx, out, src):
    for e in entries:
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
            key = register(stack, src, 'loot')
            out.append({'item': key, 'id': norm_id(e['name']), 'weight': e.get('weight', 1),
                        'quality': e.get('quality'), 'count': count,
                        'conditions': e.get('conditions'), 'functions': [f.get('function') for f in e.get('functions', [])],
                        **pool_ctx})
        elif t == 'loot_table':
            # set_count on a loot_table entry applies to every stack the nested table yields
            count = next((fn.get('count') for fn in e.get('functions', [])
                          if fn.get('function', '').split(':')[-1] == 'set_count' and not fn.get('add')), None)
            out.append({'loot_table': e.get('value') if isinstance(e.get('value'), str) else e.get('name'),
                        'count': count, 'weight': e.get('weight', 1), 'quality': e.get('quality'),
                        'conditions': e.get('conditions'), **pool_ctx})
        elif t in ('alternatives', 'group', 'sequence'):
            # the children share the parent's single weighted slot in the pool (an alternatives entry
            # gives only its first child whose conditions pass, e.g. Silk Touch or else the normal drop)
            start = len(out)
            walk_entries(e.get('children', []), pool_ctx, out, src)
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
    for i, p in enumerate(d.get('pools', [])):
        ents = p.get('entries', [])
        total = sum(e.get('weight', 1) for e in ents)
        ctx = {'pool': i, 'rolls': p.get('rolls', 1), 'bonus_rolls': p.get('bonus_rolls', 0),
               'pool_total_weight': total, 'pool_conditions': p.get('conditions')}
        walk_entries(ents, ctx, out, src)
    return out


LOOT = {}
for f in sorted(glob.glob(os.path.join(DP, '*', 'loot_table', '**', '*.json'), recursive=True)):
    ns = os.path.relpath(f, DP).split(os.sep)[0]
    lid = ns + ':' + os.path.relpath(f, os.path.join(DP, ns, 'loot_table'))[:-5]
    d = load(f)
    LOOT[lid] = {'id': lid, 'src': rel(f), 'type': d.get('type'), 'entries': parse_loot(d, rel(f)),
                 'overrides_vanilla': ns == 'minecraft' and os.path.exists(
                     os.path.join(VDATA, 'loot_table', os.path.relpath(f, os.path.join(DP, ns, 'loot_table'))))}

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
        mods = t.get('given_item_modifiers') or []
        if any(m.get('function', '').split(':')[-1] == 'discard' for m in mods):
            continue  # placeholder trade the game throws away (levels with no real trades)
        for m in mods:
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
    van = os.path.join(VDATA, 'enchantment', os.path.basename(f))
    ENCH[eid] = {'id': eid, 'src': rel(f), 'name': render_text(d.get('description')),
                 'max_level': d.get('max_level'), 'weight': d.get('weight'), 'anvil_cost': d.get('anvil_cost'),
                 'slots': d.get('slots'), 'supported_items': d.get('supported_items'),
                 'primary_items': d.get('primary_items'), 'exclusive_set': d.get('exclusive_set'),
                 'effects': d.get('effects'), 'data': d,
                 'vanilla': load(van) if ns == 'minecraft' and os.path.exists(van) else None}

# ---------------------------------------------------------------- advancements
ADV = {}
for f in sorted(glob.glob(os.path.join(DP, '*', 'advancement', '**', '*.json'), recursive=True)):
    ns = os.path.relpath(f, DP).split(os.sep)[0]
    aid = ns + ':' + os.path.relpath(f, os.path.join(DP, ns, 'advancement'))[:-5]
    d = load(f)
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
    for ref in refs:
        f = resolve_item_model(ref)
        if not f:
            continue
        m = first_model(load(f).get('model', {}))
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
                                      if not v.startswith('#') and texture_path(v)}}
    return None


# ---------------------------------------------------------------- write
for k, it in ITEMS.items():
    it['icon'] = icon_for(it)

pack_meta = load(os.path.join(SRC, 'MF_datapack', 'pack.mcmeta'))
version_text = render_text(pack_meta['pack']['description'])
git_head = os.popen('git -C "%s" rev-parse HEAD' % SRC).read().strip()
git_date = os.popen('git -C "%s" log -1 --format=%%cI' % SRC).read().strip()

data = {
    'meta': {'pack_description': version_text, 'git_head': git_head, 'git_date': git_date,
             'pack_format': pack_meta['pack'].get('min_format')},
    'lang_pack': PACK_LANG,
    'renames': {k: {'vanilla': VANILLA_LANG.get(k), 'pack': strip_codes(v)} for k, v in PACK_LANG.items()
                if k in VANILLA_LANG and VANILLA_LANG[k] != v},
    'items': ITEMS,
    'recipes': RECIPES,
    'vanilla_recipes_kept': VANILLA_RECIPES_KEPT,
    'blocked_vanilla': sorted(BLOCKED),
    'loot': LOOT,
    'trades': {p: dict(v) for p, v in TRADES.items()},
    'professions': PROF_NAME,
    'enchantments': ENCH,
    'advancements': ADV,
    'functions': FUNCTIONS,
    'missing_lang': sorted(MISSING_LANG),
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=1, ensure_ascii=False)
print('items', len(ITEMS), 'recipes', len(RECIPES), 'vanilla kept', len(VANILLA_RECIPES_KEPT),
      'loot', len(LOOT), 'enchantments', len(ENCH), 'advancements', len(ADV), 'functions', len(FUNCTIONS),
      'no icon', sum(1 for i in ITEMS.values() if not i['icon']), file=sys.stderr)
